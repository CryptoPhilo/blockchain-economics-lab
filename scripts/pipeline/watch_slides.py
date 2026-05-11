#!/usr/bin/env python3
"""
Slide Pipeline Watcher — BCE-1085 / BCE-1099

Scans `Slide/{TYPE}/` and child folders for landscape slide PDFs,
plus explicitly supported legacy report folders at
`BCE Lab Reports/{slug}/{TYPE}/`,
identifies (slug, lang) from PDF content, converts to a self-contained HTML
viewer, uploads it to Supabase Storage, and merges the public URL into
`project_reports.slide_html_urls_by_lang`.

Identification strategy (BCE-1099):
  1. Filename keyword match against tracked_projects (name/slug/symbol)
  2. PDF first-pages text match against tracked_projects
  3. OCR (tesseract) on first page → text match (for raster-only NotebookLM PDFs)

Language detection:
  1. PDF metadata `/Title` or `/Subject` keyword scan
  2. langdetect on extracted text
  3. langdetect on OCR text

Usage:
    python watch_slides.py                      # all types (econ, mat, for)
    python watch_slides.py --type econ          # one report type only
    python watch_slides.py --slug bitcoin       # targeted filename/folder hint filter
    python watch_slides.py --dry-run            # scan-only, no uploads
    python watch_slides.py --force              # ignore manifest, reprocess all
    python watch_slides.py --skip-db-reconcile  # do not cancel stale DB rows after full scan
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load env from .env.local (matches watch_for_drafts.py)
_env = Path(__file__).resolve().parent.parent.parent / '.env.local'
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

os.environ.setdefault(
    'GDRIVE_SERVICE_ACCOUNT_FILE',
    str(Path(__file__).resolve().parent / '.gdrive_service_account.json'),
)


# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════

SUPPORTED_LANGS = {'ko', 'en', 'fr', 'es', 'de', 'ja', 'zh'}

# GDrive root folder per type (provided in BCE-1085 spec)
TYPE_FOLDER_IDS: Dict[str, str] = {
    'econ': '19VNGRg8eHAvoWH4SPyeQdtAfJNTmRwJn',
    'mat':  '18ZhiiFRHEgYFkEHKpoEYR0nLdT_X29t6',
    'for':  '1LZ2J4qvQoKuva74wlvgcwjCGG5kHEzex',
}

# Legacy report PDFs sometimes live outside the active Slide/{TYPE} roots.
# They are still scanned so the watcher can either publish a landscape deck or
# record an explicit portrait-report skip instead of leaving the DB state silent.
LEGACY_REPORTS_ROOT_FOLDER_NAME = 'BCE Lab Reports'
LEGACY_REPORTS_ROOT_FOLDER_ENV = 'BCE_LAB_REPORTS_FOLDER_ID'
LEGACY_REPORTS_TYPE_FOLDER_NAMES: Dict[str, Set[str]] = {
    'econ': {'econ', 'economic', 'economics'},
    'mat': {'mat', 'maturity'},
    'for': {'for', 'forensic'},
}

SOURCE_DRAFTS_ROOT_FOLDER_NAME = 'BCE Research Source Drafts'
SOURCE_DRAFTS_ROOT_FOLDER_ENV = 'BCE_RESEARCH_SOURCE_DRAFTS_FOLDER_ID'

# Internal type → DB enum (project_reports.report_type)
DB_REPORT_TYPE: Dict[str, str] = {
    'econ': 'econ',
    'mat':  'maturity',
    'for':  'forensic',
}

BUCKET_NAME = 'slides'
REVIEW_READY_STATUS = 'in_review'
PUBLICATION_APPROVED_STATUS = 'approved'
PUBLICATION_PUBLISHED_STATUS = 'published'

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent.parent
MANIFEST_PATH = PIPELINE_DIR / 'output' / '_slide_processed.json'
LOG_DIR = REPO_ROOT / 'logs' / 'slide_pipeline'

# Pages to extract for content-based identification (cheap; first page already
# contains the title in NotebookLM exports).
PDF_TEXT_PAGES = 3

# NotebookLM slide decks are 16:9 landscape. Legacy PDF reports are portrait
# documents and must not be published as slide HTML.
MIN_SLIDE_ASPECT_RATIO = 1.25
STALE_PROCESSING_AFTER_MINUTES = int(os.environ.get('SLIDE_PIPELINE_STALE_PROCESSING_MINUTES', '30'))

# Tesseract trained-data codes per supported language. Used both for OCR of
# raster-only PDFs and to control which language packs to install in CI.
TESSERACT_LANG_CODES: Dict[str, str] = {
    'ko': 'kor',
    'en': 'eng',
    'fr': 'fra',
    'es': 'spa',
    'de': 'deu',
    'ja': 'jpn',
    'zh': 'chi_sim',
}
_TESSERACT_AVAILABLE: Optional[bool] = None

# Hints used when guessing language from PDF metadata strings.
LANG_HINTS: List[Tuple[str, str]] = [
    ('korean', 'ko'), ('한국어', 'ko'), ('한글', 'ko'),
    ('english', 'en'),
    ('français', 'fr'), ('francais', 'fr'), ('french', 'fr'),
    ('español', 'es'), ('espanol', 'es'), ('spanish', 'es'),
    ('deutsch', 'de'), ('german', 'de'),
    ('日本語', 'ja'), ('japanese', 'ja'),
    ('中文', 'zh'), ('简体', 'zh'), ('繁體', 'zh'), ('chinese', 'zh'),
]

FILENAME_LANG_HINTS: List[Tuple[str, str]] = [
    ('ko', 'ko'), ('kor', 'ko'), ('kr', 'ko'),
    ('en', 'en'), ('eng', 'en'),
    ('fr', 'fr'), ('fre', 'fr'), ('fra', 'fr'),
    ('es', 'es'), ('spa', 'es'),
    ('de', 'de'), ('ger', 'de'), ('deu', 'de'),
    ('ja', 'ja'), ('jp', 'ja'), ('jpn', 'ja'),
    ('zh', 'zh'), ('cn', 'zh'), ('chn', 'zh'),
]

# Explicit watcher-only project aliases. These are intentionally narrow: aliases
# may resolve a slug, but the existing content mismatch guard still blocks
# publication when the PDF body points to another tracked project.
PROJECT_ALIAS_REGISTRY: Dict[str, List[str]] = {
    'ripple': ['xrpl', 'xrp ledger'],
    'world-liberty-financial': ['wlf intelligence briefing', 'wlf economic architecture'],
    'okx': ['x layer economic blueprint', 'x layer money chain analysis', 'x layer economic analysis'],
    'ethereum': ['programmable trust blueprint'],
    'bitcoin-cash': ['bch'],
    'cardano': ['ada'],
    'tether-gold': ['xaut'],
    'global-dollar': ['usdg', 'global dollar usd'],
    'mantle': ['mnt'],
    'uniswap': ['uni'],
    'polkadot': ['dot'],
    'pi-network': ['pi'],
    'cosmos-hub': ['cosmos'],
    'worldcoin': ['world'],
    'siren': ['sirenai', 'siren ai'],
    'gate': ['gatechain', 'gate chain'],
    'venice-token': ['venice ai', 'venice_ai'],
}

TRACKED_PROJECT_GUARD_FIELDS = (
    'id, slug, name, symbol, status, '
    'last_econ_report_at, last_maturity_report_at, last_forensic_report_at, '
    'next_econ_due_at, next_maturity_due_at'
)

PAPERCLIP_PIPELINE_NAMES: Dict[str, str] = {
    'econ': 'ECON Report Publishing',
    'mat': 'MAT Report Publishing',
    'for': 'FOR Report Publishing',
}

PAPERCLIP_NODE_STAGES: List[Tuple[str, str]] = [
    ('source_collection', 'Slide PDF intake'),
    ('research_synthesis', 'Analysis source confirmation'),
    ('draft_report', 'Summary and marketing extraction'),
    ('summary_marketing_localization', '7-language summary and marketing localization'),
    ('editorial_review', 'Publication review'),
    ('website_publish', 'Website publishing'),
    ('post_publish_monitoring', 'Post-publish monitoring'),
]

PAPERCLIP_SUCCESS_STATUSES = {
    'published',
    'review_ready',
    'review_ready_created',
    'unchanged',
    'dry_run',
    'pruned_stale_languages',
    'pruned_stale_storage',
    'db_reconcile_ok',
    'db_reconcile_cancelled',
    'db_reconcile_timestamp_synced',
    'db_reconcile_timestamp_cleared',
    'dry_run_db_reconcile_cancel',
    'dry_run_db_reconcile_timestamp_sync',
    'dry_run_db_reconcile_timestamp_clear',
}

PAPERCLIP_FAILURE_STATUSES = {'failed'}

PAPERCLIP_BLOCKED_STATUSES = {
    'unresolved',
    'mismatch',
    'language_mismatch',
    'blocked_missing_analysis_source',
    'prune_skipped_no_publishable_pdf',
    'prune_skipped_no_project_id',
    'prune_skipped_no_supabase',
    'prune_storage_failed',
    'db_reconcile_skipped',
}


# ═══════════════════════════════════════════
# GDrive helpers
# ═══════════════════════════════════════════

def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    sa_file = os.environ.get('GDRIVE_SERVICE_ACCOUNT_FILE')
    if not sa_file or not os.path.exists(sa_file):
        raise RuntimeError(f"GDRIVE_SERVICE_ACCOUNT_FILE missing or not found: {sa_file}")
    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=['https://www.googleapis.com/auth/drive']
    )
    delegate = os.environ.get('GDRIVE_DELEGATE_EMAIL', 'zhang@coinlab.co.kr')
    if delegate:
        creds = creds.with_subject(delegate)
    return build('drive', 'v3', credentials=creds)


GDRIVE_FOLDER_MIME = 'application/vnd.google-apps.folder'


def _list_pdfs_direct(service, parent_id: str) -> List[Dict]:
    """List PDFs in `parent_id` only (no subfolder traversal)."""
    query = (
        f"'{parent_id}' in parents "
        f"and mimeType = 'application/pdf' "
        f"and trashed = false"
    )
    out: List[Dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields='nextPageToken, files(id, name, modifiedTime, size)',
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def _list_child_folders(service, parent_id: str) -> List[Dict]:
    """List immediate child folders in `parent_id`."""
    query = (
        f"'{parent_id}' in parents "
        f"and mimeType = '{GDRIVE_FOLDER_MIME}' "
        f"and trashed = false"
    )
    out: List[Dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields='nextPageToken, files(id, name)',
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def _list_non_folder_files_direct(service, parent_id: str) -> List[Dict]:
    """List non-folder files in `parent_id` only."""
    query = (
        f"'{parent_id}' in parents "
        f"and mimeType != '{GDRIVE_FOLDER_MIME}' "
        f"and trashed = false"
    )
    out: List[Dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields='nextPageToken, files(id, name, mimeType, modifiedTime, size)',
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def _drive_literal(value: str) -> str:
    return (value or '').replace('\\', '\\\\').replace("'", "\\'")


def _find_folders_by_name(service, name: str) -> List[Dict]:
    """Find Drive folders by exact name across accessible drives."""
    query = (
        f"name = '{_drive_literal(name)}' "
        f"and mimeType = '{GDRIVE_FOLDER_MIME}' "
        f"and trashed = false"
    )
    out: List[Dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields='nextPageToken, files(id, name)',
            pageToken=page_token,
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def _download_file(service, file_id: str, dest_path: str) -> None:
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


# ═══════════════════════════════════════════
# Manifest helpers (file_id keyed)
# ═══════════════════════════════════════════

def _load_manifest() -> Dict[str, Dict]:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_manifest(data: Dict[str, Dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding='utf-8',
    )


def _parse_manifest_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith('Z'):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _processing_manifest_diagnostic(
    manifest_entry: Dict[str, Any],
    *,
    now: datetime,
    stale_after_minutes: int = STALE_PROCESSING_AFTER_MINUTES,
) -> Optional[Dict[str, Any]]:
    if manifest_entry.get('status') != 'processing':
        return None
    started_at_raw = manifest_entry.get('started_at')
    started_at = _parse_manifest_datetime(started_at_raw)
    if started_at is None:
        return {
            'is_stale': True,
            'started_at': started_at_raw,
            'age_minutes': None,
            'stale_after_minutes': stale_after_minutes,
            'reason': 'missing_or_invalid_started_at',
        }
    age_minutes = max(0, int((now.astimezone(timezone.utc) - started_at).total_seconds() // 60))
    return {
        'is_stale': age_minutes >= stale_after_minutes,
        'started_at': started_at.isoformat(),
        'age_minutes': age_minutes,
        'stale_after_minutes': stale_after_minutes,
        'reason': 'age_exceeded_threshold' if age_minutes >= stale_after_minutes else 'within_threshold',
    }


# ═══════════════════════════════════════════
# PDF text + metadata extraction
# ═══════════════════════════════════════════

def _extract_pdf_meta_and_text(pdf_path: str, max_pages: int = PDF_TEXT_PAGES) -> Tuple[Dict[str, str], str]:
    """Return (metadata, first-pages text). Best-effort; returns ({}, "") on failure."""
    try:
        import fitz  # pymupdf
    except Exception:
        return {}, ''
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return {}, ''
    meta = dict(doc.metadata or {})
    text_parts: List[str] = []
    try:
        for i in range(min(max_pages, doc.page_count)):
            try:
                text_parts.append(doc.load_page(i).get_text() or '')
            except Exception:
                continue
    finally:
        doc.close()
    return meta, '\n'.join(text_parts)


def _pdf_page_profile(pdf_path: str) -> Dict[str, float | int | bool]:
    """Return basic first-page dimensions used to reject legacy portrait reports."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
    except Exception:
        return {'page_count': 0, 'width': 0.0, 'height': 0.0, 'aspect_ratio': 0.0, 'is_landscape_slide': False}
    try:
        if doc.page_count <= 0:
            return {'page_count': 0, 'width': 0.0, 'height': 0.0, 'aspect_ratio': 0.0, 'is_landscape_slide': False}
        rect = doc.load_page(0).rect
        width = float(rect.width)
        height = float(rect.height)
        aspect = width / height if height else 0.0
        return {
            'page_count': doc.page_count,
            'width': width,
            'height': height,
            'aspect_ratio': aspect,
            'is_landscape_slide': aspect >= MIN_SLIDE_ASPECT_RATIO,
        }
    finally:
        doc.close()


def _ocr_first_page_text(pdf_path: str, max_pages: int = PDF_TEXT_PAGES) -> str:
    """Render the first pages and OCR them with tesseract. Returns "" on failure.

    Used for NotebookLM-style raster PDFs that have no text layer
    (see project memory: project_notebooklm_pdf_full_page_raster.md).
    Tesseract loads all supported language packs in one pass so script
    detection works for mixed/Asian scripts. If tesseract or pytesseract
    is unavailable, returns "" silently.
    """
    try:
        import fitz  # pymupdf
        import pytesseract
        from PIL import Image
    except Exception as e:
        print(f"    [WARN] OCR deps unavailable: {e}")
        return ''
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is None:
        _TESSERACT_AVAILABLE = shutil.which('tesseract') is not None
        if not _TESSERACT_AVAILABLE:
            print("    [WARN] OCR binary unavailable: tesseract is not installed or not in PATH")
    if not _TESSERACT_AVAILABLE:
        return ''
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return ''

    pages_to_ocr = min(max_pages, doc.page_count)
    if pages_to_ocr <= 0:
        doc.close()
        return ''

    tess_langs = '+'.join(TESSERACT_LANG_CODES[c] for c in sorted(SUPPORTED_LANGS))
    text_parts: List[str] = []
    try:
        for i in range(pages_to_ocr):
            try:
                page = doc.load_page(i)
                # 200 DPI is enough for tesseract on cover-style slides
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
                img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                text_parts.append(pytesseract.image_to_string(img, lang=tess_langs) or '')
            except Exception as e:
                print(f"    [WARN] OCR page {i} failed: {e}")
                continue
    finally:
        doc.close()
    return '\n'.join(text_parts)


# ═══════════════════════════════════════════
# Slug resolution (filename → text → OCR)
# ═══════════════════════════════════════════

_TOKEN_RE = re.compile(r'[A-Za-z0-9]+')
_ASCII_ONLY_RE = re.compile(r'^[a-z0-9 ]+$')
_SIGNAL_SEPARATOR_RE = re.compile(r'[^a-z0-9]+')


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or '')]


def _normalize_signal_text(text: str) -> str:
    return f" {_SIGNAL_SEPARATOR_RE.sub(' ', (text or '').lower()).strip()} "


def _is_ascii_signal(sig: str) -> bool:
    return bool(_ASCII_ONLY_RE.match(sig))


def _score_signal_in_text(sig: str, t: str, normalized_text: str, tokens: Set[str]) -> int:
    """Score one signal without allowing ASCII substring false positives."""
    if not sig:
        return 0

    normalized_sig = _normalize_signal_text(sig)
    normalized_sig_body = normalized_sig.strip()
    ascii_signal = _is_ascii_signal(normalized_sig_body)
    has_phrase_separator = bool(re.search(r'[\s-]', sig))

    if ascii_signal:
        if has_phrase_separator:
            return len(sig) * 2 if normalized_sig in normalized_text else 0
        return len(sig) * 2 if sig in tokens else 0

    if has_phrase_separator and normalized_sig_body and normalized_sig in normalized_text:
        return len(sig) * 2
    if sig in tokens:
        return len(sig) * 2
    if len(sig) >= 2 and sig in t:
        return len(sig) * 2
    return 0


def _load_tracked_projects(sb) -> List[Dict[str, Any]]:
    """Fetch all tracked_projects (id, slug, name, symbol, aliases)."""
    out: List[Dict[str, Any]] = []
    page_size = 1000
    offset = 0
    while True:
        res = sb.table('tracked_projects').select('id, slug, name, symbol, aliases') \
            .range(offset, offset + page_size - 1).execute()
        rows = res.data or []
        out.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def _lang_map_has_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_lang_map_has_value(v) for v in value.values())
    if isinstance(value, list):
        return any(_lang_map_has_value(v) for v in value)
    return False


def _report_row_has_slide_html(row: Dict[str, Any]) -> bool:
    return _lang_map_has_value(row.get('slide_html_urls_by_lang'))


def _report_row_has_legacy_pdf_url(row: Dict[str, Any]) -> bool:
    return any(
        _lang_map_has_value(row.get(field))
        for field in (
            'gdrive_urls_by_lang',
            'gdrive_url',
            'file_url',
            'gdrive_file_id',
        )
    )


def _missing_report_backlog_reason(report_rows: List[Dict[str, Any]]) -> str:
    if any(_report_row_has_legacy_pdf_url(row) for row in report_rows):
        return 'legacy_pdf_only_no_slide_html'
    if report_rows:
        return 'project_report_no_slide_html'
    return 'no_project_report_slide_state'


def find_active_projects_missing_report_backlog(sb) -> List[Dict[str, Any]]:
    """Find active projects missing current slide production state.

    Legacy ECON rows with only Google Drive/PDF URLs are report history, but they
    are not evidence that the slide pipeline has produced HTML. The guard should
    therefore count only rows with slide_html_urls_by_lang, plus explicit future
    schedule markers, as satisfying the slide backlog state.
    """
    projects_result = (
        sb.table('tracked_projects')
        .select(TRACKED_PROJECT_GUARD_FIELDS)
        .eq('status', 'active')
        .execute()
    )
    projects = projects_result.data or []
    if not projects:
        return []

    project_ids = [p['id'] for p in projects if p.get('id')]
    slide_reported_project_ids: Set[str] = set()
    report_rows_by_project_id: Dict[str, List[Dict[str, Any]]] = {}
    if project_ids:
        reports_result = (
            sb.table('project_reports')
            .select(
                'project_id, gdrive_urls_by_lang, gdrive_url, file_url, '
                'gdrive_file_id, slide_html_urls_by_lang'
            )
            .in_('project_id', project_ids)
            .execute()
        )
        for row in reports_result.data or []:
            project_id = row.get('project_id')
            if project_id:
                report_rows_by_project_id.setdefault(project_id, []).append(row)
        slide_reported_project_ids = {
            row.get('project_id')
            for row in (reports_result.data or [])
            if row.get('project_id') and _report_row_has_slide_html(row)
        }

    projects_with_report_state: Set[str] = set(slide_reported_project_ids)
    active_report_state_symbols: Set[str] = set()
    for project in projects:
        marker_values = [
            project.get('next_econ_due_at'),
            project.get('next_maturity_due_at'),
        ]
        if project.get('id') in slide_reported_project_ids or any(marker_values):
            projects_with_report_state.add(project.get('id'))
            symbol = (project.get('symbol') or '').strip().upper()
            if symbol:
                active_report_state_symbols.add(symbol)

    missing = []
    for project in projects:
        if project.get('id') in slide_reported_project_ids:
            continue
        marker_values = [
            project.get('next_econ_due_at'),
            project.get('next_maturity_due_at'),
        ]
        if any(marker_values):
            continue
        symbol = (project.get('symbol') or '').strip().upper()
        if (
            symbol
            and symbol in active_report_state_symbols
            and project.get('id') not in projects_with_report_state
        ):
            continue
        reason = _missing_report_backlog_reason(
            report_rows_by_project_id.get(project.get('id'), [])
        )
        missing.append({
            'id': project.get('id'),
            'slug': project.get('slug'),
            'name': project.get('name'),
            'symbol': project.get('symbol'),
            'status': 'missing_slide_html',
            'reason': reason,
        })

    return sorted(missing, key=lambda p: p.get('slug') or '')


def run_active_project_backlog_guard() -> List[Dict[str, Any]]:
    """Run the backlog guard from the current slide watcher path."""
    try:
        from supabase_storage import get_supabase_storage_client
        sb = get_supabase_storage_client()
    except Exception as e:
        print(f"\n[GUARD] Unable to create Supabase client: {e}")
        return []

    try:
        missing = find_active_projects_missing_report_backlog(sb)
    except Exception as e:
        print(f"\n[GUARD] Unable to check active project backlog: {e}")
        return []

    if missing:
        print("\n[GUARD] Active projects missing report backlog:")
        for project in missing:
            symbol = project.get('symbol') or '?'
            name = project.get('name') or project.get('slug') or '?'
            reason = project.get('reason') or 'unknown'
            status = project.get('status') or 'missing'
            print(f"  - {project.get('slug')} ({symbol}) — {name} [{status}: {reason}]")
    else:
        print("\n[GUARD] No active projects missing report backlog")
    return missing


# ═══════════════════════════════════════════
# Optional Paperclip telemetry
# ═══════════════════════════════════════════

def _paperclip_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _paperclip_configured() -> bool:
    return bool(
        os.environ.get('PAPERCLIP_API_URL')
        and (
            os.environ.get('PAPERCLIP_API_KEY')
            or os.environ.get('PAPERCLIP_AGENT_TOKEN')
            or os.environ.get('PAPERCLIP_TOKEN')
        )
    )


def _paperclip_auth_token() -> Optional[str]:
    return (
        os.environ.get('PAPERCLIP_API_KEY')
        or os.environ.get('PAPERCLIP_AGENT_TOKEN')
        or os.environ.get('PAPERCLIP_TOKEN')
    )


def _paperclip_pipeline_id_from_env(rtype: str) -> Optional[str]:
    suffix = rtype.upper()
    return (
        os.environ.get(f'PAPERCLIP_{suffix}_PIPELINE_ID')
        or os.environ.get(f'PAPERCLIP_PIPELINE_ID_{suffix}')
        or os.environ.get(f'PAPERCLIP_PIPELINE_{suffix}_ID')
    )


def _paperclip_pipeline_name_from_env(rtype: str) -> str:
    suffix = rtype.upper()
    return (
        os.environ.get(f'PAPERCLIP_{suffix}_PIPELINE_NAME')
        or os.environ.get(f'PAPERCLIP_PIPELINE_NAME_{suffix}')
        or PAPERCLIP_PIPELINE_NAMES[rtype]
    )


def build_paperclip_run_payload(
    *,
    rtype: str,
    scan_time: str,
    dry_run: bool,
    force: bool,
    slug: Optional[str],
) -> Dict[str, Any]:
    return {
        'status': 'running',
        'triggerType': 'schedule' if os.environ.get('GITHUB_ACTIONS') else 'manual',
        'startedAt': _paperclip_utc_now(),
        'summary': f"{rtype.upper()} slide watcher started",
        'metadata': {
            'reportType': rtype,
            'scanTime': scan_time,
            'dryRun': dry_run,
            'force': force,
            'slug': slug,
            'githubRunId': os.environ.get('GITHUB_RUN_ID'),
            'githubRunNumber': os.environ.get('GITHUB_RUN_NUMBER'),
            'githubWorkflow': os.environ.get('GITHUB_WORKFLOW'),
            'githubSha': os.environ.get('GITHUB_SHA'),
        },
    }


def build_paperclip_node_run_payload(
    *,
    pipeline_run_id: str,
    node_id: str,
    rtype: str,
    stage_key: str,
    stage_name: str,
    status: str,
    metrics: Dict[str, int],
    log_path: Optional[str],
) -> Dict[str, Any]:
    now = _paperclip_utc_now()
    return {
        'runId': pipeline_run_id,
        'nodeId': node_id,
        'status': status,
        'startedAt': now,
        'finishedAt': now,
        'summary': f"{stage_name}: {status}",
        'metadata': {
            'reportType': rtype,
            'nodeKey': stage_key,
            'nodeName': stage_name,
            'metrics': metrics,
            'logArtifactPath': log_path,
            'source': 'watch_slides.py',
        },
    }


def build_paperclip_event_payload(
    *,
    pipeline_run_id: str,
    rtype: str,
    status: str,
    metrics: Dict[str, int],
    log_path: Optional[str],
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        'runId': pipeline_run_id,
        'eventType': 'slide_watcher.completed',
        'severity': 'error' if status == 'failed' else 'warning' if status == 'waiting_manual' else 'info',
        'message': (
            f"{rtype.upper()} slide watcher completed: "
            f"scanned={metrics['scanned']} processed={metrics['processed']} "
            f"review_ready={metrics['review_ready']} unresolved={metrics['unresolved']} "
            f"failed={metrics['failed']}"
        ),
        'occurredAt': _paperclip_utc_now(),
        'artifactRef': log_path,
        'details': {
            'reportType': rtype,
            'status': status,
            'metrics': metrics,
            'logArtifactPath': log_path,
            'warnings': warnings or [],
            'source': 'watch_slides.py',
        },
    }


def _paperclip_counts_for_type(
    rtype: str,
    scanned: List[Dict[str, Any]],
    processed: List[Dict[str, Any]],
) -> Dict[str, int]:
    scanned_for_type = [r for r in scanned if r.get('rtype') == rtype]
    processed_for_type = [r for r in processed if r.get('rtype') == rtype]
    return {
        'scanned': len(scanned_for_type),
        'processed': len(processed_for_type),
        'published': sum(1 for r in processed_for_type if r.get('status') == 'published'),
        'review_ready': sum(1 for r in processed_for_type if r.get('status') == 'review_ready'),
        'unresolved': sum(1 for r in processed_for_type if r.get('status') == 'unresolved'),
        'failed': sum(1 for r in processed_for_type if r.get('status') in PAPERCLIP_FAILURE_STATUSES),
        'blocked': sum(1 for r in processed_for_type if r.get('status') in PAPERCLIP_BLOCKED_STATUSES),
    }


def _paperclip_status_for_counts(metrics: Dict[str, int]) -> str:
    if metrics.get('failed', 0) > 0:
        return 'failed'
    if metrics.get('blocked', 0) > 0 or metrics.get('unresolved', 0) > 0:
        return 'waiting_manual'
    return 'succeeded'


class PaperclipTelemetry:
    def __init__(self) -> None:
        self.enabled = _paperclip_configured()
        self.api_url = (os.environ.get('PAPERCLIP_API_URL') or '').rstrip('/')
        self.company_id = os.environ.get('PAPERCLIP_COMPANY_ID')
        self.token = _paperclip_auth_token()
        self.pipeline_ids: Dict[str, str] = {}
        self.node_ids: Dict[str, Dict[str, str]] = {}
        self.run_ids: Dict[str, str] = {}
        self.warnings: List[str] = []

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"  [WARN] Paperclip telemetry: {message}")

    def _url_for_path(self, path: str) -> str:
        if self.api_url.endswith('/api') and path.startswith('/api/'):
            return f"{self.api_url}{path[4:]}"
        return f"{self.api_url}{path}"

    def _request_once(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Any], Optional[str]]:
        if not self.enabled:
            return None, None
        body = None
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.token}',
        }
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        run_id = os.environ.get('PAPERCLIP_RUN_ID')
        if run_id:
            headers['X-Paperclip-Run-Id'] = run_id
        url = self._url_for_path(path)
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8')
                if not raw:
                    return {}, None
                content_type = resp.headers.get('content-type', '')
                if 'application/json' not in content_type:
                    raise RuntimeError(f"non-JSON response from {path}: {content_type}")
                return json.loads(raw), None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, json.JSONDecodeError) as e:
            return None, str(e)

    def request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        paths = [path]
        if not path.startswith('/api/'):
            paths.append(f'/api{path}')
        last_error = None
        for candidate in paths:
            response, error = self._request_once(method, candidate, payload)
            if error is None:
                return response
            last_error = error
        self.warn(f"{method} {path} failed: {last_error}")
        return None

    def resolve_pipeline_id(self, rtype: str) -> Optional[str]:
        configured_id = _paperclip_pipeline_id_from_env(rtype)
        if configured_id:
            self.resolve_pipeline_nodes(configured_id, rtype)
            return configured_id
        if not self.company_id:
            self.warn(f"{rtype.upper()} pipeline id not configured and PAPERCLIP_COMPANY_ID is missing")
            return None
        response = self.request('GET', f'/api/companies/{self.company_id}/pipelines')
        if not isinstance(response, list):
            self.warn(f"{rtype.upper()} pipeline lookup returned no pipeline list")
            return None
        expected_name = _paperclip_pipeline_name_from_env(rtype)
        for pipeline in response:
            if (pipeline.get('name') or '').strip() == expected_name:
                pipeline_id = pipeline.get('id')
                if pipeline_id:
                    self.resolve_pipeline_nodes(pipeline_id, rtype)
                return pipeline_id
        self.warn(f"{rtype.upper()} pipeline not found by name: {expected_name}")
        return None

    def resolve_pipeline_nodes(self, pipeline_id: str, rtype: str) -> None:
        response = self.request('GET', f'/api/pipelines/{pipeline_id}')
        if not isinstance(response, dict):
            self.warn(f"{rtype.upper()} pipeline detail lookup failed for node ids")
            return
        nodes = response.get('nodes')
        if not isinstance(nodes, list):
            self.warn(f"{rtype.upper()} pipeline detail did not include nodes")
            return
        node_ids = {
            str(node.get('nodeKey')): str(node.get('id'))
            for node in nodes
            if node.get('nodeKey') and node.get('id')
        }
        missing = [stage_key for stage_key, _stage_name in PAPERCLIP_NODE_STAGES if stage_key not in node_ids]
        if missing:
            self.warn(f"{rtype.upper()} pipeline missing node keys: {', '.join(missing)}")
        self.node_ids[rtype] = node_ids

    def start_runs(self, types: List[str], *, scan_time: str, dry_run: bool, force: bool, slug: Optional[str]) -> None:
        if not self.enabled:
            self.warn('disabled; set PAPERCLIP_API_URL and PAPERCLIP_API_KEY to publish pipeline telemetry')
            return
        for rtype in types:
            pipeline_id = self.resolve_pipeline_id(rtype)
            if not pipeline_id:
                continue
            self.pipeline_ids[rtype] = pipeline_id
            payload = build_paperclip_run_payload(
                rtype=rtype,
                scan_time=scan_time,
                dry_run=dry_run,
                force=force,
                slug=slug,
            )
            response = self.request('POST', f'/pipelines/{pipeline_id}/runs', payload)
            run_id = (response or {}).get('id') or (response or {}).get('runId')
            if run_id:
                self.run_ids[rtype] = run_id
            else:
                self.warn(f"{rtype.upper()} run was not created")

    def complete_runs(
        self,
        types: List[str],
        *,
        scanned: List[Dict[str, Any]],
        processed: List[Dict[str, Any]],
        log_path: Optional[str],
    ) -> None:
        if not self.enabled:
            return
        for rtype in types:
            pipeline_id = self.pipeline_ids.get(rtype)
            run_id = self.run_ids.get(rtype)
            if not pipeline_id or not run_id:
                continue
            metrics = _paperclip_counts_for_type(rtype, scanned, processed)
            status = _paperclip_status_for_counts(metrics)
            node_ids = self.node_ids.get(rtype, {})
            for stage_key, stage_name in PAPERCLIP_NODE_STAGES:
                node_id = node_ids.get(stage_key)
                if not node_id:
                    self.warn(f"{rtype.upper()} node run skipped; missing node id for {stage_key}")
                    continue
                self.request(
                    'POST',
                    f'/pipeline-runs/{run_id}/node-runs',
                    build_paperclip_node_run_payload(
                        pipeline_run_id=run_id,
                        node_id=node_id,
                        rtype=rtype,
                        stage_key=stage_key,
                        stage_name=stage_name,
                        status=status,
                        metrics=metrics,
                        log_path=log_path,
                    ),
                )
            self.request(
                'POST',
                f'/pipelines/{pipeline_id}/events',
                build_paperclip_event_payload(
                    pipeline_run_id=run_id,
                    rtype=rtype,
                    status=status,
                    metrics=metrics,
                    log_path=log_path,
                    warnings=self.warnings,
                ),
            )
            self.request(
                'PATCH',
                f'/pipeline-runs/{run_id}',
                {
                    'status': status,
                    'finishedAt': _paperclip_utc_now(),
                    'summary': (
                        f"{rtype.upper()} slide watcher completed: "
                        f"scanned={metrics['scanned']} processed={metrics['processed']} "
                        f"review_ready={metrics['review_ready']} unresolved={metrics['unresolved']} "
                        f"failed={metrics['failed']}"
                    ),
                    'metadata': {
                        'reportType': rtype,
                        'metrics': metrics,
                        'logArtifactPath': log_path,
                        'telemetryWarnings': self.warnings,
                        'source': 'watch_slides.py',
                    },
                },
            )


def _project_signal(project: Dict[str, Any]) -> List[str]:
    """Return lowercase tokens that identify a project.

    Uses only the full slug/name/symbol strings; hyphenated slug parts are
    NOT exploded into independent tokens because generic fragments like
    `protocol` or `network` cause cross-project false positives.
    """
    sigs: List[str] = []
    for key in ('slug', 'name', 'symbol'):
        v = (project.get(key) or '').strip().lower()
        if v:
            sigs.append(v)
    aliases = project.get('aliases') or []
    if isinstance(aliases, list):
        sigs.extend(
            alias.strip().lower()
            for alias in aliases
            if isinstance(alias, str) and alias.strip()
        )
    sigs.extend(PROJECT_ALIAS_REGISTRY.get((project.get('slug') or '').lower(), []))
    return list({s for s in sigs if s})


def _match_project_by_text(text: str, projects: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Match `text` against project signals. Prefer longer/more specific signals."""
    if not text:
        return None
    t = text.lower()
    normalized_text = _normalize_signal_text(text)
    tokens = set(_tokenize(text))
    best: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        score = 0
        for sig in _project_signal(proj):
            score = max(score, _score_signal_in_text(sig, t, normalized_text, tokens))
        if score and (best is None or score > best[0]):
            best = (score, proj)
    return best[1] if best else None


def _resolve_slug(
    pdf_name: str,
    pdf_text: str,
    ocr_text: str,
    projects: List[Dict[str, str]],
) -> Tuple[Optional[Dict[str, str]], str]:
    """Return (project, source) where source ∈ {'filename','pdf_text','ocr','none'}."""
    proj = _match_project_by_text(pdf_name, projects)
    if proj:
        return proj, 'filename'
    proj = _match_project_by_text(pdf_text, projects)
    if proj:
        return proj, 'pdf_text'
    proj = _match_project_by_text(ocr_text, projects)
    if proj:
        return proj, 'ocr'
    return None, 'none'


def _score_project_in_text(text: str, proj: Dict[str, str]) -> int:
    """Return the per-project match score used by _match_project_by_text."""
    if not text:
        return 0
    t = text.lower()
    normalized_text = _normalize_signal_text(text)
    tokens = set(_tokenize(text))
    score = 0
    for sig in _project_signal(proj):
        score = max(score, _score_signal_in_text(sig, t, normalized_text, tokens))
    return score


def _detect_slug_content_mismatch(
    resolved_project: Optional[Dict[str, str]],
    pdf_text: str,
    ocr_text: str,
    projects: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    """Publish guard — flag PDFs whose body contradicts the filename-resolved slug.

    Catches cases like a Bittensor PDF saved as bitcoin_*.pdf, where filename
    matching alone would mis-publish content under the wrong project. Returns
    a mismatch descriptor if body content matches a *different* project with
    a meaningfully higher score than the resolved slug; returns None otherwise.

    Heuristic: text-layer bodies keep the existing strict guard. OCR-only
    bodies use a higher threshold because NotebookLM raster exports can produce
    generic or noisy project signals.
    """
    if resolved_project is None:
        return None
    body = (pdf_text or '') + '\n' + (ocr_text or '')
    if len(body.strip()) < 200:
        return None  # not enough body text to decide reliably
    has_interpretable_text_layer = len((pdf_text or '').strip()) >= 200
    min_other_score = 12 if has_interpretable_text_layer else 24
    min_score_margin = 1 if has_interpretable_text_layer else 12
    expected_score = _score_project_in_text(body, resolved_project)
    expected_slug = (resolved_project.get('slug') or '').lower()
    best_other: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        if (proj.get('slug') or '').lower() == expected_slug:
            continue
        score = _score_project_in_text(body, proj)
        if score >= min_other_score and (best_other is None or score > best_other[0]):
            best_other = (score, proj)
    if best_other and best_other[0] >= expected_score + min_score_margin:
        other_slug = (best_other[1].get('slug') or '').lower()
        return {
            'expected_slug': expected_slug,
            'expected_score': expected_score,
            'detected_slug': other_slug,
            'detected_score': best_other[0],
        }
    return None


# ═══════════════════════════════════════════
# Language resolution
# ═══════════════════════════════════════════

def _lang_from_metadata(meta: Dict[str, str]) -> Optional[str]:
    haystack = ' '.join(
        (meta.get(k) or '') for k in ('title', 'Title', 'subject', 'Subject', 'keywords', 'Keywords')
    ).lower()
    if not haystack:
        return None
    for hint, code in LANG_HINTS:
        if hint in haystack:
            return code
    return None


def _lang_from_filename(pdf_name: str) -> Optional[str]:
    """Resolve explicit filename language tokens before content heuristics.

    NotebookLM slide filenames often carry the intended target locale as a
    suffix (`_en`, `_ko`, `_cn2`). The rendered PDF text/OCR can be sparse or
    image-heavy, so statistical language detection can mislabel those decks and
    overwrite the wrong storage object.
    """
    stem = Path(pdf_name).stem.lower()
    tokens = [t for t in re.split(r'[^a-z0-9]+', stem) if t]
    for token in reversed(tokens):
        normalized = re.sub(r'\d+$', '', token)
        for hint, code in FILENAME_LANG_HINTS:
            if normalized == hint:
                return code
    return None


def _cjk_script_counts(text: str) -> Dict[str, int]:
    """Count CJK script families in a bounded sample."""
    sample = (text or '')[:8000]
    return {
        'kana': sum(1 for ch in sample if '぀' <= ch <= 'ヿ'),
        'hangul': sum(1 for ch in sample if '가' <= ch <= '힯'),
        'han': sum(1 for ch in sample if '一' <= ch <= '鿿'),
    }


def _cjk_script_signature(text: str) -> Optional[str]:
    """High-confidence CJK script detection by Unicode block counts.

    Hiragana/katakana uniquely identify Japanese, hangul uniquely identifies
    Korean, and han-only text (no kana/hangul) is treated as Chinese. This
    runs before langdetect because short OCR text with mixed scripts
    (image-heavy slides where OCR yields a brief title) often gets
    misclassified by statistical detectors — e.g. a Japanese cover slide
    fingerprinted as English.
    """
    counts = _cjk_script_counts(text)
    hiragana_katakana = counts['kana']
    hangul = counts['hangul']
    han = counts['han']
    if hiragana_katakana >= 4:
        return 'ja'
    if hangul >= 4:
        return 'ko'
    if han >= 10 and hiragana_katakana == 0 and hangul == 0:
        return 'zh'
    return None


def _is_han_dominant_zh(counts: Dict[str, int]) -> bool:
    """Return true when Chinese Han text clearly outweighs OCR kana noise."""
    han = counts.get('han', 0)
    kana = counts.get('kana', 0)
    hangul = counts.get('hangul', 0)
    return hangul == 0 and han >= 20 and (kana == 0 or han >= kana * 4)


def _lang_from_text(text: str) -> Optional[str]:
    if not text or len(text.strip()) < 30:
        # Even on short text, kana/hangul presence is decisive enough.
        return _cjk_script_signature(text or '')
    cjk = _cjk_script_signature(text)
    if cjk:
        return cjk
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        code = detect(text[:4000])
    except Exception:
        return None
    # langdetect returns codes like 'zh-cn'; normalize to our 2-letter set
    code = code.split('-')[0].lower()
    return code if code in SUPPORTED_LANGS else None


def _resolve_lang(
    pdf_name: str,
    meta: Dict[str, str],
    text: str,
    ocr_text: str,
) -> Tuple[Optional[str], str]:
    code = _lang_from_filename(pdf_name)
    if code:
        return code, 'filename'
    code = _lang_from_metadata(meta)
    if code:
        return code, 'metadata'
    code = _lang_from_text(text)
    if code:
        return code, 'langdetect'
    code = _lang_from_text(ocr_text)
    if code:
        return code, 'ocr_langdetect'
    return None, 'none'


def _detect_language_content_mismatch(
    resolved_lang: Optional[str],
    pdf_text: str,
    ocr_text: str,
    lang_source: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Flag high-confidence CJK body text that contradicts resolved language.

    PDF metadata is useful but not authoritative: mislabeled NotebookLM exports
    can say "Japanese" while the slide body is Chinese. Use only the deterministic
    CJK script signature here so Latin-script reports are not blocked by noisy
    statistical language detection.
    """
    if not resolved_lang:
        return None
    if resolved_lang not in {'ko', 'ja', 'zh'}:
        return None

    for source, text in (('text', pdf_text), ('ocr', ocr_text)):
        if source == 'ocr' and lang_source == 'filename':
            continue
        counts = _cjk_script_counts(text or '')
        if resolved_lang == 'ja' and counts['hangul'] >= 4:
            return {
                'resolved_lang': resolved_lang,
                'detected_lang': 'ko',
                'source': source,
                'reason': 'mixed_cjk_script',
            }
        if resolved_lang == 'zh':
            if counts['hangul'] >= 4:
                return {
                    'resolved_lang': resolved_lang,
                    'detected_lang': 'ko',
                    'source': source,
                    'reason': 'mixed_cjk_script',
                }
            if counts['kana'] >= 4:
                if not _is_han_dominant_zh(counts):
                    return {
                        'resolved_lang': resolved_lang,
                        'detected_lang': 'ja',
                        'source': source,
                        'reason': 'mixed_cjk_script',
                    }
        if resolved_lang == 'ko' and counts['kana'] >= 4:
            return {
                'resolved_lang': resolved_lang,
                'detected_lang': 'ja',
                'source': source,
                'reason': 'mixed_cjk_script',
            }

        detected = _cjk_script_signature(text or '')
        if resolved_lang == 'zh' and detected == 'ja' and _is_han_dominant_zh(counts):
            continue
        if detected and detected != resolved_lang:
            return {
                'resolved_lang': resolved_lang,
                'detected_lang': detected,
                'source': source,
            }

    return None


# ═══════════════════════════════════════════
# DB lookup helpers
# ═══════════════════════════════════════════

def _find_report_for_lang(sb, project_id: str, db_type: str, lang: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """Find the latest published project_reports row for (project, type, language).

    project_reports rows are scoped per (project, type, language); without the
    language filter the URL for one language would be merged into another
    language's row.
    """
    rep = sb.table('project_reports').select('id, version, status, published_at, updated_at') \
        .eq('project_id', project_id) \
        .eq('report_type', db_type) \
        .eq('language', lang) \
        .in_('status', [PUBLICATION_PUBLISHED_STATUS, 'coming_soon', PUBLICATION_APPROVED_STATUS, REVIEW_READY_STATUS]) \
        .order('updated_at', desc=True) \
        .limit(1) \
        .execute()
    if not rep.data:
        return None, None, None
    report_id = rep.data[0]['id']
    version = rep.data[0].get('version')
    status = rep.data[0].get('status')

    try:
        rv = sb.table('report_versions').select('version') \
            .eq('report_id', report_id) \
            .eq('language', lang) \
            .order('version', desc=True) \
            .limit(1) \
            .execute()
        if rv.data:
            version = rv.data[0].get('version') or version
    except Exception:
        pass

    return report_id, version, status


def _create_report_row_for_slide(
    sb,
    *,
    project_id: str,
    db_type: str,
    slug: str,
    lang: str,
    pdf_file_id: str,
    pdf_name: str,
    public_url: str,
    version: Optional[int],
    status: str = REVIEW_READY_STATUS,
) -> Tuple[Optional[str], Optional[int]]:
    """Create a project_reports row when a slide PDF has no report shell yet."""
    now = datetime.now(timezone.utc).isoformat()
    resolved_version = version or 1
    gdrive_url = f"https://drive.google.com/file/d/{pdf_file_id}/view?usp=drivesdk"
    row = {
        'project_id': project_id,
        'report_type': db_type,
        'version': resolved_version,
        'language': lang,
        'status': status,
        'review_at': now if status == REVIEW_READY_STATUS else None,
        'published_at': now if status == PUBLICATION_PUBLISHED_STATUS else None,
        'file_url': gdrive_url,
        'gdrive_url': gdrive_url,
        'gdrive_file_id': pdf_file_id,
        'gdrive_urls_by_lang': {lang: gdrive_url},
        'slide_html_urls_by_lang': {lang: public_url},
        'translation_status': {lang: status},
        'card_data': {
            'report_type': 'econ' if db_type == 'econ' else db_type,
            'slug': slug,
            'generated_at': now,
        },
        'updated_at': now,
    }
    title_col = f"title_{lang}"
    if lang in SUPPORTED_LANGS:
        row[title_col] = Path(pdf_name).stem.replace('_', ' ')

    result = sb.table('project_reports').upsert(
        row,
        on_conflict='project_id,report_type,version,language',
    ).execute()
    data = result.data or []
    report_id = data[0].get('id') if data else None

    timestamp_field = _tracked_timestamp_field(db_type)
    if timestamp_field and status in {PUBLICATION_PUBLISHED_STATUS, 'coming_soon'}:
        sb.table('tracked_projects').update({
            timestamp_field: now,
            'updated_at': now,
        }).eq('id', project_id).execute()

    return report_id, resolved_version


def _target_publication_status(current_status: Optional[str]) -> str:
    """Keep generated assets in review until an editor approves publication."""
    if current_status == PUBLICATION_APPROVED_STATUS:
        return PUBLICATION_PUBLISHED_STATUS
    return REVIEW_READY_STATUS


def _tracked_timestamp_field(report_type: str) -> Optional[str]:
    if report_type == 'econ':
        return 'last_econ_report_at'
    if report_type == 'maturity':
        return 'last_maturity_report_at'
    if report_type == 'forensic':
        return 'last_forensic_report_at'
    return None


def _merge_slide_url(
    sb,
    report_id: str,
    lang: str,
    public_url: str,
    status: str,
    published_at: Optional[str] = None,
) -> None:
    publish_ts = published_at or datetime.now(timezone.utc).isoformat()
    current = sb.table('project_reports').select(
        'slide_html_urls_by_lang, card_data, project_id, report_type'
    ) \
        .eq('id', report_id).single().execute()
    row = current.data or {}
    # project_reports rows are language-scoped; do not carry over stale
    # sibling-language URLs left by older cross-language fallback merges.
    urls = {lang: public_url}
    card_data = row.get('card_data')
    if isinstance(card_data, dict):
        card_data = {**card_data, 'generated_at': publish_ts}
    update_payload = {
        'slide_html_urls_by_lang': urls,
        'status': status,
        'updated_at': publish_ts,
    }
    if status == PUBLICATION_PUBLISHED_STATUS:
        update_payload['published_at'] = publish_ts
    elif status == REVIEW_READY_STATUS:
        update_payload['review_at'] = publish_ts
        update_payload['published_at'] = None
    if isinstance(card_data, dict):
        update_payload['card_data'] = card_data
    sb.table('project_reports').update(update_payload).eq('id', report_id).execute()

    timestamp_field = _tracked_timestamp_field(str(row.get('report_type') or ''))
    project_id = row.get('project_id')
    if timestamp_field and project_id and status in {PUBLICATION_PUBLISHED_STATUS, 'coming_soon'}:
        sb.table('tracked_projects').update({
            timestamp_field: publish_ts,
            'updated_at': publish_ts,
        }).eq('id', project_id).execute()


def _generate_summary_after_slide_publish(
    sb,
    drive_service,
    *,
    project: Dict[str, Any],
    rtype: str,
    report_id: Optional[str],
    version: Optional[int],
    source: Optional[Any] = None,
) -> bool:
    """Generate website card copy after a slide deck is published."""
    if rtype not in {'econ', 'mat', 'for'} or not report_id:
        return False
    report_label = rtype.upper()

    try:
        from marketing_content_pipeline import build_project_report_patch_from_drive_source

        if source is None:
            source = _find_analysis_source_for_slide(
                drive_service,
                project=project,
                rtype=rtype,
                version=version,
            )
        if not source:
            print(
                f"    [WARN] {report_label} summary skipped: no Drive analysis/{report_label} source "
                f"for {project.get('slug')}"
            )
            return False

        current = sb.table('project_reports').select('card_data').eq('id', report_id).single().execute()
        row = current.data or {}
        existing_card_data = row.get('card_data') if isinstance(row.get('card_data'), dict) else {}
        patch = build_project_report_patch_from_drive_source(source, translate=True)
        patch_card_data = patch.get('card_data') if isinstance(patch.get('card_data'), dict) else {}
        patch['card_data'] = {**existing_card_data, **patch_card_data}
        sb.table('project_reports').update(patch).eq('id', report_id).execute()
        print(
            f"    ✓ {report_label} summary generated from Drive source: "
            f"{source.name} ({source.drive_file_id})"
        )
        return True
    except Exception as e:
        print(f"    [WARN] {report_label} summary generation failed after slide publish: {e}")
        return False


def _find_analysis_source_for_slide(
    drive_service,
    *,
    project: Dict[str, Any],
    rtype: str,
    version: Optional[int],
) -> Optional[Any]:
    """Find the required analysis/{TYPE} Markdown source for a slide publication."""
    if rtype not in {'econ', 'mat', 'for'}:
        return None
    try:
        from marketing_content_pipeline import find_drive_source_for_project

        return find_drive_source_for_project(
            project,
            report_type=rtype,
            version=version or 1,
            service=drive_service,
        )
    except Exception as e:
        print(f"    [WARN] {rtype.upper()} analysis source lookup failed: {e}")
        return None


def _repair_unchanged_manifest_publication(
    sb,
    *,
    rtype: str,
    project: Optional[Dict[str, Any]],
    slug: Optional[str],
    lang: Optional[str],
    public_url: Optional[str],
    pdf_file_id: str,
    pdf_name: str,
    version: Optional[int],
) -> Tuple[Optional[str], Optional[int], str]:
    """Repair DB publication state for an unchanged already-converted PDF.

    The manifest can be up to date while `project_reports` is missing the slide
    JSON or even the entire report shell. Prefer live DB lookup over a stale
    manifest report_id so deleted rows are recreated instead of silently skipped.
    """
    if not slug or not lang:
        return None, version, 'missing_slug_or_lang'
    if not public_url:
        return None, version, 'missing_public_url_reprocess_required'
    project_id = (project or {}).get('id')
    if not project_id:
        return None, version, 'missing_project_id'

    db_type = DB_REPORT_TYPE[rtype]
    report_id, db_version, current_status = _find_report_for_lang(sb, project_id, db_type, lang)
    resolved_version = db_version or version
    target_status = _target_publication_status(current_status)

    if report_id:
        _merge_slide_url(sb, report_id, lang, public_url, status=target_status)
        return report_id, resolved_version, 'published' if target_status == PUBLICATION_PUBLISHED_STATUS else 'review_ready'

    report_id, created_version = _create_report_row_for_slide(
        sb,
        project_id=project_id,
        db_type=db_type,
        slug=slug,
        lang=lang,
        pdf_file_id=pdf_file_id,
        pdf_name=pdf_name,
        public_url=public_url,
        version=resolved_version,
        status=target_status,
    )
    return report_id, created_version or resolved_version, 'review_ready_created' if report_id else 'create_failed'


def _remove_slide_url_if_matches(sb, report_id: str, lang: str, public_url: str) -> bool:
    """Remove a stale slide URL only when DB still points at that exact object."""
    if not report_id or not lang or not public_url:
        return False
    current = sb.table('project_reports').select('slide_html_urls_by_lang') \
        .eq('id', report_id).single().execute()
    urls = (current.data or {}).get('slide_html_urls_by_lang') or {}
    if not isinstance(urls, dict) or urls.get(lang) != public_url:
        return False
    updated = dict(urls)
    updated.pop(lang, None)
    sb.table('project_reports').update({
        'slide_html_urls_by_lang': updated,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', report_id).execute()
    return True


def _project_by_slug(projects: List[Dict[str, str]], slug: str) -> Optional[Dict[str, str]]:
    slug_lc = (slug or '').lower()
    for project in projects:
        if (project.get('slug') or '').lower() == slug_lc:
            return project
    return None


def _pruned_lang_map(value: Any, current_langs: Set[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Return a JSON map with languages outside current_langs removed."""
    if not isinstance(value, dict):
        return {}, []
    stale = sorted(lang for lang in value.keys() if lang not in current_langs)
    if not stale:
        return dict(value), []
    updated = dict(value)
    for lang in stale:
        updated.pop(lang, None)
    return updated, stale


def _remove_latest_slide_objects(storage_client, rtype: str, slug: str, langs: Iterable[str]) -> List[str]:
    """Remove only latest slide HTML objects; versioned slide paths are preserved."""
    keys = [f'{rtype}/{slug}/latest/{lang}.html' for lang in sorted(set(langs))]
    if not keys:
        return []
    storage_client.storage.from_(BUCKET_NAME).remove(keys)
    return keys


def _prune_stale_languages_for_pair(
    sb,
    storage_client,
    *,
    rtype: str,
    slug: str,
    project_id: str,
    current_langs: Set[str],
    dry_run: bool,
) -> List[Dict[str, Any]]:
    """Prune DB JSON language keys and latest Storage objects absent from this Drive scan."""
    if not current_langs:
        print(f"  [WARN] stale language prune skipped for {rtype}/{slug}: no current publishable PDFs")
        return [{
            'rtype': rtype,
            'slug': slug,
            'lang': None,
            'status': 'prune_skipped_no_publishable_pdf',
            'error': 'no current publishable PDFs',
        }]
    if sb is None:
        print(f"  [WARN] stale language prune skipped for {rtype}/{slug}: supabase client unavailable")
        return [{
            'rtype': rtype,
            'slug': slug,
            'lang': None,
            'status': 'prune_skipped_no_supabase',
            'error': 'supabase client unavailable',
        }]

    db_type = DB_REPORT_TYPE[rtype]
    rows = sb.table('project_reports').select(
        'id, gdrive_urls_by_lang, slide_html_urls_by_lang'
    ).eq('project_id', project_id).eq('report_type', db_type).execute().data or []

    results: List[Dict[str, Any]] = []
    stale_storage_langs: Set[str] = set()
    for row in rows:
        report_id = row.get('id')
        gdrive_urls, stale_gdrive = _pruned_lang_map(row.get('gdrive_urls_by_lang'), current_langs)
        slide_urls, stale_slide = _pruned_lang_map(row.get('slide_html_urls_by_lang'), current_langs)
        stale_langs = sorted(set(stale_gdrive) | set(stale_slide))
        if not stale_langs:
            continue

        stale_storage_langs.update(stale_langs)
        status = 'dry_run_prune' if dry_run else 'pruned_stale_languages'
        if dry_run:
            print(
                f"  [DRY-RUN] would prune {rtype}/{slug} report {report_id}: "
                f"stale_langs={stale_langs}, current_langs={sorted(current_langs)}"
            )
        else:
            sb.table('project_reports').update({
                'gdrive_urls_by_lang': gdrive_urls,
                'slide_html_urls_by_lang': slide_urls,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }).eq('id', report_id).execute()
            print(
                f"  [PRUNE] project_reports[{report_id}] {rtype}/{slug}: "
                f"removed stale_langs={stale_langs}"
            )
        results.append({
            'rtype': rtype,
            'slug': slug,
            'lang': None,
            'status': status,
            'report_id': report_id,
            'current_langs': sorted(current_langs),
            'stale_langs': stale_langs,
        })

    if stale_storage_langs:
        keys = [f'{rtype}/{slug}/latest/{lang}.html' for lang in sorted(stale_storage_langs)]
        if dry_run:
            print(f"  [DRY-RUN] would prune Storage latest objects: {keys}")
            results.append({
                'rtype': rtype,
                'slug': slug,
                'lang': None,
                'status': 'dry_run_prune_storage',
                'current_langs': sorted(current_langs),
                'stale_langs': sorted(stale_storage_langs),
                'storage_keys': keys,
            })
        else:
            if storage_client is None:
                print(f"  [WARN] Storage prune skipped for {rtype}/{slug}: storage client unavailable")
                results.append({
                    'rtype': rtype,
                    'slug': slug,
                    'lang': None,
                    'status': 'prune_storage_skipped_no_client',
                    'current_langs': sorted(current_langs),
                    'stale_langs': sorted(stale_storage_langs),
                    'storage_keys': keys,
                    'error': 'storage client unavailable',
                })
            else:
                try:
                    removed_keys = _remove_latest_slide_objects(storage_client, rtype, slug, stale_storage_langs)
                    print(f"  [PRUNE] Storage latest objects removed: {removed_keys}")
                    results.append({
                        'rtype': rtype,
                        'slug': slug,
                        'lang': None,
                        'status': 'pruned_stale_storage',
                        'current_langs': sorted(current_langs),
                        'stale_langs': sorted(stale_storage_langs),
                        'storage_keys': removed_keys,
                    })
                except Exception as e:
                    print(f"  [WARN] Storage prune failed for {rtype}/{slug}: {e}")
                    results.append({
                        'rtype': rtype,
                        'slug': slug,
                        'lang': None,
                        'status': 'prune_storage_failed',
                        'current_langs': sorted(current_langs),
                        'stale_langs': sorted(stale_storage_langs),
                        'storage_keys': keys,
                        'error': str(e)[:300],
                    })

    return results


VISIBLE_REPORT_STATUSES = {
    PUBLICATION_PUBLISHED_STATUS,
    PUBLICATION_APPROVED_STATUS,
    REVIEW_READY_STATUS,
    'coming_soon',
}


def _fetch_all_table_rows(sb, table_name: str, columns: str) -> List[Dict[str, Any]]:
    """Fetch rows in pages to avoid Supabase's default 1k result cap."""
    rows: List[Dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        res = sb.table(table_name).select(columns).range(offset, offset + page_size - 1).execute()
        data = res.data or []
        rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    return rows


def _active_drive_report_pairs(
    service,
    types: Iterable[str],
    projects: List[Dict[str, Any]],
) -> Tuple[Set[Tuple[str, str, str]], List[Dict[str, Any]]]:
    """Return active Slide/{TYPE} report keys as (db_type, slug, lang)."""
    pairs: Set[Tuple[str, str, str]] = set()
    unresolved: List[Dict[str, Any]] = []
    for rtype, pdf in _iter_active_slide_targets(service, types, projects=projects):
        project = _match_drive_pdf_project(pdf, projects)
        lang = _lang_from_filename(pdf.get('name') or '')
        db_type = DB_REPORT_TYPE.get(rtype)
        slug = (project or {}).get('slug')
        if db_type and slug and lang:
            pairs.add((db_type, slug, lang))
            continue
        unresolved.append({
            'rtype': rtype,
            'name': pdf.get('name'),
            'source_path': pdf.get('source_path'),
            'slug': slug,
            'lang': lang,
            'status': 'db_reconcile_unresolved_drive_pdf',
            'error': 'Drive PDF could not be reduced to (report_type, slug, lang)',
        })
    return pairs, unresolved


def _compact_project_signal(value: Any) -> str:
    return re.sub(r'[^a-z0-9]+', '', _normalize_signal_text(str(value or '')))


def _match_drive_pdf_project(pdf: Dict[str, Any], projects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Resolve a Drive PDF to a project without downloading the PDF body.

    The final reconcile step must be conservative: active Drive files are the
    source of truth, and common filename spellings like `pumpfun` vs `pump-fun`
    should not make the guard hide a real report. Prefer the normal resolver,
    then fall back to compact slug/name/alias matching and symbol tokens.
    """
    name = pdf.get('name') or ''
    source_path = pdf.get('source_path') or ''
    matched = _match_project_by_text(f'{name} {source_path}', projects)
    if matched:
        return matched

    stem = Path(name).stem
    compact_stem = _compact_project_signal(stem)
    token_text = _normalize_signal_text(stem)
    token_set = set(token_text.split())
    candidates: List[Tuple[int, Dict[str, Any]]] = []
    for project in projects:
        slug_signal = _compact_project_signal(project.get('slug'))
        name_signal = _compact_project_signal(project.get('name'))
        aliases = project.get('aliases') or []
        alias_signals = [
            _compact_project_signal(alias)
            for alias in aliases
            if _compact_project_signal(alias)
        ]
        for signal in [slug_signal, name_signal, *alias_signals]:
            if len(signal) >= 5 and signal in compact_stem:
                candidates.append((len(signal), project))
        symbol = str(project.get('symbol') or '').lower()
        if symbol and len(symbol) <= 8 and symbol in token_set:
            candidates.append((len(symbol), project))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _rtype_for_db_type(db_type: Optional[str]) -> Optional[str]:
    return next((rtype for rtype, mapped in DB_REPORT_TYPE.items() if mapped == db_type), None)


def _reconcile_visible_reports_with_drive(
    sb,
    service,
    *,
    types: Iterable[str],
    projects: List[Dict[str, Any]],
    dry_run: bool,
) -> List[Dict[str, Any]]:
    """Keep website-visible report rows aligned with current active Slide folders."""
    if sb is None:
        return [{
            'rtype': None,
            'slug': None,
            'lang': None,
            'status': 'db_reconcile_skipped',
            'error': 'supabase client unavailable',
        }]

    results: List[Dict[str, Any]] = []
    drive_pairs, unresolved = _active_drive_report_pairs(service, types, projects)
    results.extend(unresolved)
    db_types = {DB_REPORT_TYPE[rtype] for rtype in types if rtype in DB_REPORT_TYPE}
    project_by_id = {p.get('id'): p for p in projects}

    report_rows = [
        row for row in _fetch_all_table_rows(
            sb,
            'project_reports',
            (
                'id, project_id, report_type, language, status, published_at, '
                'updated_at, created_at, slide_html_urls_by_lang'
            ),
        )
        if row.get('report_type') in db_types
    ]

    now = datetime.now(timezone.utc).isoformat()
    active_slugs_by_type: Dict[str, Set[str]] = {}
    for db_type, slug, _lang in drive_pairs:
        active_slugs_by_type.setdefault(db_type, set()).add(slug)

    for row in report_rows:
        project = project_by_id.get(row.get('project_id')) or {}
        key = (row.get('report_type'), project.get('slug'), row.get('language'))
        if row.get('status') not in VISIBLE_REPORT_STATUSES or key in drive_pairs:
            continue
        status = 'dry_run_db_reconcile_cancel' if dry_run else 'db_reconcile_cancelled'
        if not dry_run:
            sb.table('project_reports').update({
                'status': 'cancelled',
                'updated_at': now,
            }).eq('id', row.get('id')).execute()
        results.append({
            'rtype': _rtype_for_db_type(row.get('report_type')),
            'slug': project.get('slug'),
            'lang': row.get('language'),
            'status': status,
            'report_id': row.get('id'),
            'error': 'website-visible report row is absent from active Drive Slide folder',
        })

    latest_by_type_slug: Dict[Tuple[str, str], str] = {}
    for row in report_rows:
        project = project_by_id.get(row.get('project_id')) or {}
        slug = project.get('slug')
        key = (row.get('report_type'), slug, row.get('language'))
        if key not in drive_pairs:
            continue
        if row.get('status') not in VISIBLE_REPORT_STATUSES:
            continue
        if not _lang_map_has_value(row.get('slide_html_urls_by_lang')):
            continue
        ts = row.get('published_at') or row.get('updated_at') or row.get('created_at')
        if not ts or not slug:
            continue
        latest_key = (str(row.get('report_type')), str(slug))
        if latest_key not in latest_by_type_slug or ts > latest_by_type_slug[latest_key]:
            latest_by_type_slug[latest_key] = ts

    tracked_rows = _fetch_all_table_rows(
        sb,
        'tracked_projects',
        'id, slug, last_econ_report_at, last_maturity_report_at, last_forensic_report_at',
    )
    for project in tracked_rows:
        slug = project.get('slug')
        project_id = project.get('id')
        for db_type in sorted(db_types):
            timestamp_field = _tracked_timestamp_field(db_type)
            if not timestamp_field:
                continue
            active_slugs = active_slugs_by_type.get(db_type, set())
            current_value = project.get(timestamp_field)
            latest = latest_by_type_slug.get((db_type, slug))
            if slug not in active_slugs:
                if not current_value:
                    continue
                status = 'dry_run_db_reconcile_timestamp_clear' if dry_run else 'db_reconcile_timestamp_cleared'
                if not dry_run and project_id:
                    sb.table('tracked_projects').update({
                        timestamp_field: None,
                        'updated_at': now,
                    }).eq('id', project_id).execute()
                results.append({
                    'rtype': _rtype_for_db_type(db_type),
                    'slug': slug,
                    'lang': None,
                    'status': status,
                    'error': f'{timestamp_field} cleared because no active Drive Slide report exists',
                })
            elif latest and latest != current_value:
                status = 'dry_run_db_reconcile_timestamp_sync' if dry_run else 'db_reconcile_timestamp_synced'
                if not dry_run and project_id:
                    sb.table('tracked_projects').update({
                        timestamp_field: latest,
                        'updated_at': now,
                    }).eq('id', project_id).execute()
                results.append({
                    'rtype': _rtype_for_db_type(db_type),
                    'slug': slug,
                    'lang': None,
                    'status': status,
                    'error': f'{timestamp_field} synced from active Drive-backed report rows',
                })

    if not results:
        results.append({
            'rtype': None,
            'slug': None,
            'lang': None,
            'status': 'db_reconcile_ok',
            'error': 'visible DB report availability already matches active Drive Slide folders',
        })
    return results


# ═══════════════════════════════════════════
# Conversion + upload
# ═══════════════════════════════════════════

def _convert_and_upload(
    pdf_local_path: str,
    *,
    rtype: str,
    slug: str,
    lang: str,
    version: Optional[int],
    storage_client,
) -> Dict[str, str]:
    from pdf_to_html_slides import compress_slide_pdf, convert_pdf_to_html_slides
    from supabase_storage import upload_html

    with tempfile.TemporaryDirectory() as tmp:
        compressed = os.path.join(tmp, 'compressed.pdf')
        try:
            compress_slide_pdf(pdf_local_path, compressed)
            source_pdf = compressed
        except Exception as e:
            print(f"    ⚠ compress_slide_pdf failed ({e}); using original PDF")
            source_pdf = pdf_local_path

        html_path = os.path.join(tmp, f'{lang}.html')
        convert_pdf_to_html_slides(source_pdf, output_path=html_path, title=slug, lang=lang)
        html_bytes = Path(html_path).read_bytes()

    version_segment = str(version) if version else 'latest'
    versioned_key = f'{rtype}/{slug}/{version_segment}/{lang}.html'
    latest_key = f'{rtype}/{slug}/latest/{lang}.html'

    versioned_url = upload_html(storage_client, BUCKET_NAME, versioned_key, html_bytes)
    if version_segment != 'latest':
        latest_url = upload_html(storage_client, BUCKET_NAME, latest_key, html_bytes)
    else:
        latest_url = versioned_url

    return {'versioned_url': versioned_url, 'latest_url': latest_url}


# ═══════════════════════════════════════════
# Scan + processing
# ═══════════════════════════════════════════

def _with_source_metadata(pdf: Dict, *, parent_folder: Dict, source_path: str, depth: int) -> Dict:
    return {
        **pdf,
        'parent_folder_id': parent_folder.get('id'),
        'parent_folder_name': parent_folder.get('name'),
        'source_path': f"{source_path}/{pdf.get('name', '')}",
        'source_depth': depth,
    }


def _legacy_reports_root_folders(service) -> List[Dict]:
    configured = [
        folder_id.strip()
        for folder_id in (os.environ.get(LEGACY_REPORTS_ROOT_FOLDER_ENV) or '').split(',')
        if folder_id.strip()
    ]
    if configured:
        return [{'id': folder_id, 'name': LEGACY_REPORTS_ROOT_FOLDER_NAME} for folder_id in configured]
    try:
        return _find_folders_by_name(service, LEGACY_REPORTS_ROOT_FOLDER_NAME)
    except Exception as e:
        print(f"  [WARN] legacy report root lookup failed: {e}")
        return []


def _legacy_report_type_for_folder(folder_name: str, requested_types: Set[str]) -> Optional[str]:
    normalized = (folder_name or '').strip().lower()
    for rtype in requested_types:
        if normalized in LEGACY_REPORTS_TYPE_FOLDER_NAMES.get(rtype, set()):
            return rtype
    return None


def _iter_legacy_report_targets(
    service,
    types: Iterable[str],
    *,
    filter_slug: Optional[str] = None,
):
    """Yield PDFs under BCE Lab Reports/{slug}/{type}/."""
    requested_types = set(types)
    roots = _legacy_reports_root_folders(service)
    if not roots:
        return
    seen_file_ids: Set[str] = set()
    for root in roots:
        root_id = root.get('id')
        root_name = root.get('name') or LEGACY_REPORTS_ROOT_FOLDER_NAME
        if not root_id:
            continue
        try:
            slug_folders = _list_child_folders(service, root_id)
        except Exception as e:
            print(f"  [WARN] legacy report slug folder scan failed for {root_name}: {e}")
            continue
        for slug_folder in slug_folders:
            slug_folder_id = slug_folder.get('id')
            slug_name = slug_folder.get('name') or ''
            if not slug_folder_id:
                continue
            if filter_slug and slug_name != filter_slug:
                continue
            try:
                type_folders = _list_child_folders(service, slug_folder_id)
            except Exception as e:
                print(f"  [WARN] legacy report type folder scan failed for {root_name}/{slug_name}: {e}")
                continue
            for type_folder in type_folders:
                rtype = _legacy_report_type_for_folder(type_folder.get('name') or '', requested_types)
                if not rtype:
                    continue
                type_folder_id = type_folder.get('id')
                if not type_folder_id:
                    continue
                source_path = f"{root_name}/{slug_name}/{type_folder.get('name', '')}"
                try:
                    pdfs = _list_pdfs_direct(service, type_folder_id)
                except Exception as e:
                    print(f"  [WARN] legacy report PDF scan failed for {source_path}: {e}")
                    continue
                for pdf in pdfs:
                    file_id = pdf.get('id')
                    if file_id and file_id in seen_file_ids:
                        continue
                    if file_id:
                        seen_file_ids.add(file_id)
                    yield rtype, {
                        **_with_source_metadata(
                            pdf,
                            parent_folder=type_folder,
                            source_path=source_path,
                            depth=2,
                        ),
                        'source_kind': 'legacy_report',
                        'legacy_slug_hint': slug_name,
                    }


def _source_drafts_root_folders(service) -> List[Dict]:
    configured = [
        folder_id.strip()
        for folder_id in (os.environ.get(SOURCE_DRAFTS_ROOT_FOLDER_ENV) or '').split(',')
        if folder_id.strip()
    ]
    if configured:
        return [{'id': folder_id, 'name': SOURCE_DRAFTS_ROOT_FOLDER_NAME} for folder_id in configured]
    try:
        return _find_folders_by_name(service, SOURCE_DRAFTS_ROOT_FOLDER_NAME)
    except Exception as e:
        print(f"  [WARN] source draft root lookup failed: {e}")
        return []


def _parse_source_draft_name(name: str, requested_types: Set[str]) -> Optional[Dict[str, Any]]:
    stem = Path(name or '').stem
    match = re.match(
        r'^(?P<slug>[a-z0-9][a-z0-9-]*)_(?P<rtype>econ|mat|maturity|for|forensic)_v(?P<version>\d+)(?:_(?P<lang>[a-z]{2,3}))?$',
        stem,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    raw_rtype = match.group('rtype').lower()
    rtype = {
        'maturity': 'mat',
        'forensic': 'for',
    }.get(raw_rtype, raw_rtype)
    if rtype not in requested_types:
        return None
    lang = (match.group('lang') or '').lower() or None
    if lang == 'cn':
        lang = 'zh'
    return {
        'slug': match.group('slug').lower(),
        'rtype': rtype,
        'version': int(match.group('version')),
        'lang': lang,
    }


def validate_source_slide_handoff_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Executable guard for scanner/card/source-draft/Slide intake handoffs."""
    source_request = contract.get('human_source_request') or {}
    slide_intake = contract.get('slide_intake') or {}
    registration = ((contract.get('registration') or {}).get('tables') or {}).get('project_reports') or {}

    draft_name = source_request.get('draft_name') or slide_intake.get('expected_source_draft_name')
    parsed = _parse_source_draft_name(str(draft_name or ''), {'for'})
    if not parsed:
        return {
            'status': 'failed',
            'code': 'invalid_source_draft_name',
            'message': 'source draft name does not match {slug}_{type}_v{version}_{lang}.md',
        }

    expected_slug = source_request.get('required_slug')
    expected_rtype = source_request.get('required_rtype') or 'for'
    expected_lang = source_request.get('required_lang')
    expected_db_type = (
        slide_intake.get('expected_db_report_type')
        or source_request.get('required_report_type')
        or registration.get('report_type')
    )

    mismatches = []
    if expected_slug and parsed['slug'] != expected_slug:
        mismatches.append({'field': 'slug', 'draft': parsed['slug'], 'expected': expected_slug})
    if expected_rtype and parsed['rtype'] != expected_rtype:
        mismatches.append({'field': 'rtype', 'draft': parsed['rtype'], 'expected': expected_rtype})
    if expected_lang and parsed.get('lang') != expected_lang:
        mismatches.append({'field': 'lang', 'draft': parsed.get('lang'), 'expected': expected_lang})

    db_report_type = DB_REPORT_TYPE.get(parsed['rtype'])
    if expected_db_type and db_report_type != expected_db_type:
        mismatches.append({
            'field': 'db_report_type',
            'draft': db_report_type,
            'expected': expected_db_type,
        })
    if registration.get('report_type') and registration.get('report_type') != db_report_type:
        mismatches.append({
            'field': 'registration.report_type',
            'draft': db_report_type,
            'expected': registration.get('report_type'),
        })

    watcher_args = slide_intake.get('args') or []
    if '--slug' in watcher_args:
        slug_index = watcher_args.index('--slug') + 1
        watcher_slug = watcher_args[slug_index] if slug_index < len(watcher_args) else None
        if watcher_slug != parsed['slug']:
            mismatches.append({'field': 'watcher_args.slug', 'draft': parsed['slug'], 'expected': watcher_slug})
    if '--type' in watcher_args:
        type_index = watcher_args.index('--type') + 1
        watcher_type = watcher_args[type_index] if type_index < len(watcher_args) else None
        if watcher_type != parsed['rtype']:
            mismatches.append({'field': 'watcher_args.type', 'draft': parsed['rtype'], 'expected': watcher_type})

    if mismatches:
        return {
            'status': 'failed',
            'code': 'handoff_contract_mismatch',
            'source_draft': parsed,
            'mismatches': mismatches,
        }

    return {
        'status': 'ok',
        'source_draft': parsed,
        'db_report_type': db_report_type,
        'watcher_args': watcher_args,
    }


def _iter_source_draft_records(
    service,
    types: Iterable[str],
    *,
    filter_slug: Optional[str] = None,
):
    """Yield source draft records from BCE Research Source Drafts.

    This is diagnostics only; source drafts are not converted or published here.
    """
    requested_types = set(types)
    roots = _source_drafts_root_folders(service)
    if not roots:
        return
    seen_file_ids: Set[str] = set()
    for root in roots:
        root_id = root.get('id')
        root_name = root.get('name') or SOURCE_DRAFTS_ROOT_FOLDER_NAME
        if not root_id:
            continue
        try:
            files = _list_non_folder_files_direct(service, root_id)
        except Exception as e:
            print(f"  [WARN] source draft scan failed for {root_name}: {e}")
            continue
        for file_info in files:
            file_id = file_info.get('id')
            if file_id and file_id in seen_file_ids:
                continue
            parsed = _parse_source_draft_name(file_info.get('name') or '', requested_types)
            if not parsed:
                continue
            if filter_slug and parsed['slug'] != filter_slug:
                continue
            if file_id:
                seen_file_ids.add(file_id)
            yield {
                **file_info,
                **parsed,
                'source_path': f"{root_name}/{file_info.get('name', '')}",
                'source_kind': 'source_draft',
            }


def _infer_rtype_from_file_name(
    name: str,
    types: Iterable[str],
    *,
    default_single_type: bool = True,
) -> Optional[str]:
    requested_types = list(types)
    if default_single_type and len(requested_types) == 1:
        return requested_types[0]
    normalized = _normalize_signal_text(Path(name or '').stem)
    for rtype in requested_types:
        tokens = LEGACY_REPORTS_TYPE_FOLDER_NAMES.get(rtype, {rtype})
        if any(f" {token} " in normalized for token in tokens):
            return rtype
    return None


def _slug_hint_tokens(filter_slug: Optional[str], projects: List[Dict[str, Any]]) -> Set[str]:
    if not filter_slug:
        return set()
    slug = filter_slug.lower()
    tokens = {slug, slug.replace('-', ' '), slug.replace('-', '_')}
    project = _project_by_slug(projects, slug)
    if project:
        tokens.update(_project_signal(project))
    return {token.lower() for token in tokens if token}


def _name_matches_slug_hint(
    name: str,
    hint_tokens: Set[str],
    *,
    filter_slug: Optional[str] = None,
    projects: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    if not hint_tokens:
        return True

    if filter_slug and projects:
        matched_project = _match_project_by_text(name or '', projects)
        if matched_project:
            return (matched_project.get('slug') or '').lower() == filter_slug.lower()

    normalized = _normalize_signal_text(Path(name or '').stem)
    for token in hint_tokens:
        if not token:
            continue
        token_norm = _normalize_signal_text(token)
        if token_norm in normalized:
            return True
    return False


def _folder_matches_slug_hint(
    folder_name: str,
    hint_tokens: Set[str],
    *,
    filter_slug: Optional[str] = None,
    projects: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    return _name_matches_slug_hint(
        folder_name,
        hint_tokens,
        filter_slug=filter_slug,
        projects=projects,
    )


def _root_scan_mode(root_rtype: str, requested_types: Set[str], hint_tokens: Set[str]) -> str:
    """Return scan mode for a Slide root.

    Requested roots are fully scanned. Sibling roots are checked only at the
    direct PDF level so a misfiled PDF with an explicit type token can still be
    recovered without traversing unrelated folder trees during targeted runs.
    """
    if root_rtype in requested_types:
        return 'full'
    if len(requested_types) == len(TYPE_FOLDER_IDS):
        return 'full'
    if hint_tokens:
        return 'skip'
    return 'direct'


def _iter_active_slide_targets(
    service,
    types: Iterable[str],
    *,
    filter_slug: Optional[str] = None,
    projects: Optional[List[Dict[str, Any]]] = None,
):
    """Yield (rtype, pdf_info) for active Slide roots only."""
    requested_types = set(types)
    hint_tokens = _slug_hint_tokens(filter_slug, projects or [])
    seen_file_ids: Set[str] = set()
    for root_rtype, type_folder in TYPE_FOLDER_IDS.items():
        if not type_folder:
            continue
        scan_mode = _root_scan_mode(root_rtype, requested_types, hint_tokens)
        if scan_mode == 'skip':
            continue
        root_folder = {'id': type_folder, 'name': root_rtype}
        for pdf in _list_pdfs_direct(service, type_folder):
            if not _name_matches_slug_hint(
                pdf.get('name') or '',
                hint_tokens,
                filter_slug=filter_slug,
                projects=projects,
            ):
                continue
            target_rtype = (
                _infer_rtype_from_file_name(
                    pdf.get('name') or '',
                    requested_types,
                    default_single_type=False,
                )
                or root_rtype
            )
            if target_rtype not in requested_types:
                continue
            file_id = pdf.get('id')
            if file_id:
                seen_file_ids.add(file_id)
            yield target_rtype, _with_source_metadata(
                pdf,
                parent_folder=root_folder,
                source_path=f"Slide/{root_rtype}",
                depth=0,
            )
        if scan_mode != 'full':
            continue
        stack: List[Tuple[Dict, str, int]] = [
            (folder, f"Slide/{root_rtype}/{folder.get('name', '')}", 1)
            for folder in _list_child_folders(service, type_folder)
            if _folder_matches_slug_hint(
                folder.get('name') or '',
                hint_tokens,
                filter_slug=filter_slug,
                projects=projects,
            )
        ]
        seen: set[str] = set()
        while stack:
            folder, source_path, depth = stack.pop(0)
            folder_id = folder.get('id')
            if not folder_id or folder_id in seen:
                continue
            seen.add(folder_id)

            for pdf in _list_pdfs_direct(service, folder_id):
                if not _name_matches_slug_hint(
                    pdf.get('name') or '',
                    hint_tokens,
                    filter_slug=filter_slug,
                    projects=projects,
                ):
                    continue
                target_rtype = (
                    _infer_rtype_from_file_name(
                        pdf.get('name') or '',
                        requested_types,
                        default_single_type=False,
                    )
                    or root_rtype
                )
                if target_rtype not in requested_types:
                    continue
                file_id = pdf.get('id')
                if file_id and file_id in seen_file_ids:
                    continue
                if file_id:
                    seen_file_ids.add(file_id)
                yield target_rtype, _with_source_metadata(
                    pdf,
                    parent_folder=folder,
                    source_path=source_path,
                    depth=depth,
                )

            for child in _list_child_folders(service, folder_id):
                if hint_tokens and not (
                    _folder_matches_slug_hint(
                        child.get('name') or '',
                        hint_tokens,
                        filter_slug=filter_slug,
                        projects=projects,
                    )
                    or _folder_matches_slug_hint(
                        source_path,
                        hint_tokens,
                        filter_slug=filter_slug,
                        projects=projects,
                    )
                ):
                    continue
                stack.append((child, f"{source_path}/{child.get('name', '')}", depth + 1))


def _iter_targets(
    service,
    types: Iterable[str],
    *,
    filter_slug: Optional[str] = None,
    projects: Optional[List[Dict[str, Any]]] = None,
):
    """Yield (rtype, pdf_info) for active Slide roots only."""
    for rtype, pdf in _iter_active_slide_targets(
        service,
        types,
        filter_slug=filter_slug,
        projects=projects,
    ):
        yield rtype, pdf


def _parse_language_overrides(values: Iterable[str]) -> Dict[str, str]:
    """Parse FILE_ID=lang overrides for human-confirmed raster PDFs."""
    overrides: Dict[str, str] = {}
    for raw in values:
        if '=' not in raw:
            raise ValueError(f"invalid language override '{raw}' (expected FILE_ID=lang)")
        file_id, lang = [part.strip() for part in raw.split('=', 1)]
        if not file_id:
            raise ValueError(f"invalid language override '{raw}' (missing file id)")
        if lang not in SUPPORTED_LANGS:
            raise ValueError(
                f"invalid language override '{raw}' (lang must be one of {sorted(SUPPORTED_LANGS)})"
            )
        overrides[file_id] = lang
    return overrides


def _has_verified_landscape_profile(manifest_entry: Dict[str, Any]) -> bool:
    page_profile = manifest_entry.get('page_profile')
    return isinstance(page_profile, dict) and page_profile.get('is_landscape_slide') is True


def process(
    types: List[str],
    *,
    filter_slug: Optional[str],
    filter_file_ids: Optional[set[str]] = None,
    dry_run: bool,
    force: bool,
    reconcile_db: bool = True,
    language_overrides: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict], List[Dict]]:
    if filter_file_ids:
        raise ValueError('--file-id targets are disabled; place PDFs under Slide/{TYPE} and use --slug/--type filters')

    service = _get_drive_service()
    manifest = _load_manifest()
    language_overrides = language_overrides or {}

    scanned: List[Dict] = []
    processed: List[Dict] = []
    prune_candidate_pairs: Set[Tuple[str, str]] = set()
    current_langs_by_pair: Dict[Tuple[str, str], Set[str]] = {}
    active_slide_seen_types: Set[str] = set()
    active_slide_missing_diag_types: Set[str] = set()

    storage_client = None
    sb = None
    if not dry_run:
        from supabase_storage import ensure_bucket, get_supabase_storage_client
        storage_client = get_supabase_storage_client()
        ensure_bucket(storage_client, BUCKET_NAME, public=True)
        sb = storage_client
    else:
        # dry-run still needs Supabase for tracked_projects lookup
        try:
            from supabase_storage import get_supabase_storage_client
            sb = get_supabase_storage_client()
        except Exception as e:
            print(f"  [WARN] supabase client unavailable in dry-run: {e}")
            sb = None

    projects: List[Dict[str, str]] = []
    if sb is not None:
        try:
            projects = _load_tracked_projects(sb)
        except Exception as e:
            print(f"  [WARN] tracked_projects fetch failed: {e}")
            projects = []

    target_iter = _iter_targets(service, types, filter_slug=filter_slug, projects=projects)

    for rtype, pdf in target_iter:
        file_id = pdf['id']
        if filter_file_ids and file_id not in filter_file_ids:
            continue
        modified = pdf.get('modifiedTime', '')
        if pdf.get('source_kind') == 'legacy_report':
            if (
                filter_slug
                and rtype not in active_slide_seen_types
                and rtype not in active_slide_missing_diag_types
            ):
                diag = {
                    'rtype': rtype,
                    'slug': filter_slug,
                    'lang': None,
                    'status': 'no_active_slide_pdf_for_slug',
                    'error': 'active_slide_pdf_missing',
                    'source_path': f"Slide/{rtype}",
                    'source_kind': 'active_slide_diagnostic',
                }
                print(
                    f"  [DIAG] {diag['status']}: "
                    f"{diag['source_path']} has no active PDF for slug '{filter_slug}'"
                )
                scanned.append(diag)
                active_slide_missing_diag_types.add(rtype)
        else:
            active_slide_seen_types.add(rtype)
        record = {
            'rtype': rtype,
            'file_id': file_id,
            'name': pdf['name'],
            'modifiedTime': modified,
            'size': pdf.get('size'),
            'parent_folder_id': pdf.get('parent_folder_id'),
            'parent_folder_name': pdf.get('parent_folder_name'),
            'source_path': pdf.get('source_path'),
            'source_depth': pdf.get('source_depth'),
        }
        if pdf.get('source_kind'):
            record['source_kind'] = pdf.get('source_kind')
        if pdf.get('legacy_slug_hint'):
            record['legacy_slug_hint'] = pdf.get('legacy_slug_hint')
        if (
            filter_slug
            and pdf.get('legacy_slug_hint')
            and pdf.get('legacy_slug_hint') != filter_slug
        ):
            continue

        prev = manifest.get(file_id) or {}
        now = datetime.now(timezone.utc)
        processing_diag = _processing_manifest_diagnostic(prev, now=now)
        if (
            processing_diag
            and prev.get('modifiedTime') == modified
            and not force
            and not processing_diag.get('is_stale')
        ):
            age = processing_diag.get('age_minutes')
            threshold = processing_diag.get('stale_after_minutes')
            print(
                f"  [SKIP] {rtype}/{pdf['name']}: manifest status=processing "
                f"for {age}min (< stale threshold {threshold}min)"
            )
            scanned.append({
                **record,
                'slug': prev.get('slug'),
                'lang': prev.get('lang'),
                'status': 'processing_in_progress',
                'processing_age_minutes': age,
                'processing_started_at': processing_diag.get('started_at'),
                'stale_after_minutes': threshold,
            })
            continue
        stale_processing_diag = (
            processing_diag
            if processing_diag
            and prev.get('modifiedTime') == modified
            and processing_diag.get('is_stale')
            else None
        )
        if stale_processing_diag and not force:
            print(
                f"  [RECOVER] {rtype}/{pdf['name']}: stale manifest status=processing "
                f"(started_at={stale_processing_diag.get('started_at')}, "
                f"age={stale_processing_diag.get('age_minutes')}min, "
                f"threshold={stale_processing_diag.get('stale_after_minutes')}min); reprocessing"
            )
            record['stale_processing'] = stale_processing_diag
        override_lang = language_overrides.get(file_id)
        override_changes_manifest_lang = bool(override_lang and prev.get('lang') != override_lang)
        unchanged_manifest_published = (
            prev.get('status') == 'published'
            and prev.get('modifiedTime') == modified
        )
        unchanged_missing_publication_url = unchanged_manifest_published and not prev.get('public_url')
        if unchanged_missing_publication_url and not dry_run and not force:
            print(
                f"  [REPAIR] {rtype}/{pdf['name']}: unchanged manifest has no public_url; "
                "reprocessing slide HTML"
            )
        if (
            not force
            and not override_changes_manifest_lang
            and unchanged_manifest_published
            and (dry_run or not unchanged_missing_publication_url)
        ):
            unchanged_slug = prev.get('slug')
            unchanged_lang = override_lang or prev.get('lang')
            unchanged_lang_source = 'manual_verified' if override_lang else prev.get('lang_source')

            if not _has_verified_landscape_profile(prev):
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_handle:
                    tmp_path = tmp_handle.name
                downloaded = False
                try:
                    try:
                        _download_file(service, file_id, tmp_path)
                        downloaded = True
                    except Exception as e:
                        err = f"download failed during unchanged page-profile recheck: {e}"
                        print(f"    ✗ {rtype}/{pdf['name']}: {err}")
                        manifest[file_id] = {
                            **prev,
                            'rtype': rtype,
                            'name': pdf['name'],
                            'parent_folder_id': pdf.get('parent_folder_id'),
                            'parent_folder_name': pdf.get('parent_folder_name'),
                            'source_path': pdf.get('source_path'),
                            'source_depth': pdf.get('source_depth'),
                            'status': 'failed',
                            'error': err[:300],
                            'modifiedTime': modified,
                            'updated_at': datetime.now(timezone.utc).isoformat(),
                        }
                        _save_manifest(manifest)
                        scanned.append({**record, 'slug': unchanged_slug, 'lang': unchanged_lang, 'status': 'failed'})
                        processed.append({**record, 'slug': unchanged_slug, 'lang': unchanged_lang, 'status': 'failed', 'error': err})
                        continue

                    page_profile = _pdf_page_profile(tmp_path)
                    if not page_profile.get('is_landscape_slide'):
                        removed_stale_url = False
                        if not dry_run:
                            try:
                                removed_stale_url = _remove_slide_url_if_matches(
                                    sb,
                                    prev.get('report_id'),
                                    unchanged_lang,
                                    prev.get('public_url'),
                                )
                                if removed_stale_url:
                                    print(
                                        f"    [REPAIR] removed stale portrait URL for "
                                        f"{unchanged_slug}/{unchanged_lang}"
                                    )
                            except Exception as e:
                                print(f"    [WARN] stale portrait URL cleanup failed: {e}")
                        msg = (
                            "legacy portrait PDF is not publishable as slide HTML "
                            f"(aspect={page_profile.get('aspect_ratio', 0):.3f})"
                        )
                        pdf_path_label = pdf.get('source_path') or f"{rtype}/{pdf['name']}"
                        print(f"  [SKIP] {pdf_path_label}: {msg}")
                        manifest[file_id] = {
                            **prev,
                            'rtype': rtype,
                            'name': pdf['name'],
                            'modifiedTime': modified,
                            'parent_folder_id': pdf.get('parent_folder_id'),
                            'parent_folder_name': pdf.get('parent_folder_name'),
                            'source_path': pdf.get('source_path'),
                            'source_depth': pdf.get('source_depth'),
                            'lang': unchanged_lang,
                            'lang_source': unchanged_lang_source,
                            'page_profile': page_profile,
                            'status': 'skipped_legacy_portrait_pdf',
                            'error': msg,
                            'stale_url_removed': removed_stale_url,
                            'updated_at': datetime.now(timezone.utc).isoformat(),
                        }
                        _save_manifest(manifest)
                        scanned.append({
                            **record,
                            'slug': unchanged_slug,
                            'lang': unchanged_lang,
                            'status': 'skipped_legacy_portrait_pdf',
                        })
                        continue

                    prev = {
                        **prev,
                        'page_profile': page_profile,
                    }
                finally:
                    if downloaded:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass

            if not dry_run:
                public_url = prev.get('public_url')
                lang = unchanged_lang
                slug = unchanged_slug
                report_id = prev.get('report_id')
                version = prev.get('version')
                should_repair = not filter_slug or slug == filter_slug
                if should_repair and public_url and lang:
                    try:
                        project = _project_by_slug(projects, slug or '')
                        report_id, version, repair_status = _repair_unchanged_manifest_publication(
                            sb,
                            rtype=rtype,
                            project=project,
                            slug=slug,
                            lang=lang,
                            public_url=public_url,
                            pdf_file_id=file_id,
                            pdf_name=pdf['name'],
                            version=prev.get('version'),
                        )
                        if report_id:
                            print(
                                f"    ✓ DB repaired from unchanged manifest ({repair_status}): "
                                f"project_reports[{report_id}].slide_html_urls_by_lang.{lang}"
                            )
                        else:
                            print(
                                f"    [WARN] DB repair skipped for unchanged manifest: "
                                f"{repair_status} ({slug}/{DB_REPORT_TYPE[rtype]}/{lang})"
                            )
                    except Exception as e:
                        print(f"    [WARN] DB repair from unchanged manifest failed: {e}")
                manifest[file_id] = {
                    **prev,
                    'report_id': report_id,
                    'version': version,
                    'parent_folder_id': pdf.get('parent_folder_id'),
                    'parent_folder_name': pdf.get('parent_folder_name'),
                    'source_path': pdf.get('source_path'),
                    'source_depth': pdf.get('source_depth'),
                    'lang': unchanged_lang,
                    'lang_source': unchanged_lang_source,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
                _save_manifest(manifest)
            if unchanged_slug and (not filter_slug or unchanged_slug == filter_slug):
                prune_candidate_pairs.add((rtype, unchanged_slug))
                if unchanged_lang and prev.get('status') == 'published':
                    current_langs_by_pair.setdefault((rtype, unchanged_slug), set()).add(unchanged_lang)
            scanned.append({**record, 'slug': unchanged_slug, 'lang': unchanged_lang, 'status': 'unchanged'})
            print(f"  [SKIP] {rtype}/{pdf['name']}: unchanged since {modified}")
            continue

        # Need PDF content to identify (slug, lang). Download once, reuse for upload.
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_handle:
            tmp_path = tmp_handle.name
        downloaded = False
        try:
            try:
                _download_file(service, file_id, tmp_path)
                downloaded = True
            except Exception as e:
                err = f"download failed: {e}"
                print(f"    ✗ {rtype}/{pdf['name']}: {err}")
                manifest[file_id] = {
                    **prev,
                    'rtype': rtype,
                    'name': pdf['name'],
                    'parent_folder_id': pdf.get('parent_folder_id'),
                    'parent_folder_name': pdf.get('parent_folder_name'),
                    'source_path': pdf.get('source_path'),
                    'source_depth': pdf.get('source_depth'),
                    'status': 'failed',
                    'error': err[:300],
                    'modifiedTime': modified,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
                _save_manifest(manifest)
                scanned.append({**record, 'slug': None, 'lang': None})
                processed.append({**record, 'slug': None, 'lang': None, 'status': 'failed', 'error': err})
                continue

            page_profile = _pdf_page_profile(tmp_path)
            if not page_profile.get('is_landscape_slide'):
                skipped_slug = prev.get('slug') or pdf.get('legacy_slug_hint')
                skipped_lang = prev.get('lang') or _lang_from_filename(pdf['name'])
                removed_stale_url = False
                if not dry_run and prev.get('status') == 'published':
                    try:
                        removed_stale_url = _remove_slide_url_if_matches(
                            sb,
                            prev.get('report_id'),
                            prev.get('lang'),
                            prev.get('public_url'),
                        )
                        if removed_stale_url:
                            print(
                                f"    [REPAIR] removed stale portrait URL for "
                                f"{prev.get('slug')}/{prev.get('lang')}"
                            )
                    except Exception as e:
                        print(f"    [WARN] stale portrait URL cleanup failed: {e}")
                msg = (
                    "legacy portrait PDF is not publishable as slide HTML "
                    f"(aspect={page_profile.get('aspect_ratio', 0):.3f})"
                )
                pdf_path_label = pdf.get('source_path') or f"{rtype}/{pdf['name']}"
                print(f"  [SKIP] {pdf_path_label}: {msg}")
                manifest[file_id] = {
                    **prev,
                    'rtype': rtype,
                    'name': pdf['name'],
                    'modifiedTime': modified,
                    'parent_folder_id': pdf.get('parent_folder_id'),
                    'parent_folder_name': pdf.get('parent_folder_name'),
                    'source_path': pdf.get('source_path'),
                    'source_depth': pdf.get('source_depth'),
                    'page_profile': page_profile,
                    'status': 'skipped_legacy_portrait_pdf',
                    'slug': skipped_slug,
                    'lang': skipped_lang,
                    'error': msg,
                    'stale_url_removed': removed_stale_url,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
                _save_manifest(manifest)
                scanned.append({
                    **record,
                    'slug': skipped_slug,
                    'lang': skipped_lang,
                    'status': 'skipped_legacy_portrait_pdf',
                })
                continue

            meta, pdf_text = _extract_pdf_meta_and_text(tmp_path)

            # Filename match alone often resolves the slug; only invoke OCR
            # (slow) when text-layer extraction can't determine slug or lang.
            filename_match = _match_project_by_text(pdf['name'], projects)
            text_lang = _lang_from_filename(pdf['name']) or _lang_from_metadata(meta) or _lang_from_text(pdf_text)
            ocr_text = ''
            if not filename_match or not text_lang:
                pdf_text_match = _match_project_by_text(pdf_text, projects)
                if not (filename_match or pdf_text_match) or not text_lang:
                    ocr_text = _ocr_first_page_text(tmp_path)

            project, slug_source = _resolve_slug(pdf['name'], pdf_text, ocr_text, projects)
            lang, lang_source = _resolve_lang(pdf['name'], meta, pdf_text, ocr_text)

            # Raster NotebookLM exports can have trustworthy-looking metadata
            # while the actual slide image is another CJK language. Force OCR for
            # CJK rows when the PDF text layer has no decisive script signal.
            if (
                lang in {'ko', 'ja', 'zh'}
                and not _cjk_script_signature(pdf_text)
                and not ocr_text
            ):
                ocr_text = _ocr_first_page_text(tmp_path)
            if not lang and prev.get('lang') and prev.get('modifiedTime') == modified:
                lang = prev.get('lang')
                lang_source = 'manifest'
            if file_id in language_overrides:
                override_lang = language_overrides[file_id]
                if lang and lang != override_lang:
                    print(
                        f"    [WARN] language override for {pdf['name']}: "
                        f"{lang} ({lang_source}) → {override_lang}"
                    )
                lang = override_lang
                lang_source = 'manual_verified'

            slug = (project or {}).get('slug')
            project_id = (project or {}).get('id')
            record.update({'slug': slug, 'lang': lang})
            scanned.append(record.copy())

            if filter_slug and slug != filter_slug:
                print(f"  [SKIP] {rtype}/{pdf['name']}: slug='{slug}' != filter '{filter_slug}'")
                continue

            if slug:
                prune_candidate_pairs.add((rtype, slug))

            if not slug or not lang:
                msg = (
                    f"unresolved (slug={slug or '?'} via {slug_source}; "
                    f"lang={lang or '?'} via {lang_source})"
                )
                print(f"  [UNRESOLVED] {rtype}/{pdf['name']}: {msg}")
                manifest[file_id] = {
                    **prev,
                    'rtype': rtype,
                    'name': pdf['name'],
                    'modifiedTime': modified,
                    'parent_folder_id': pdf.get('parent_folder_id'),
                    'parent_folder_name': pdf.get('parent_folder_name'),
                    'source_path': pdf.get('source_path'),
                    'source_depth': pdf.get('source_depth'),
                    'status': 'unresolved',
                    'slug': slug,
                    'lang': lang,
                    'slug_source': slug_source,
                    'lang_source': lang_source,
                    'error': msg,
                    'public_url': None,
                    'versioned_url': None,
                    'report_id': None,
                    'version': None,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
                _save_manifest(manifest)
                processed.append({**record, 'status': 'unresolved', 'error': msg})
                continue

            lang_mismatch = _detect_language_content_mismatch(lang, pdf_text, ocr_text, lang_source)
            if lang_mismatch:
                msg = (
                    f"language/content mismatch — resolved '{lang_mismatch['resolved_lang']}' "
                    f"via {lang_source} but {lang_mismatch['source']} body script indicates "
                    f"'{lang_mismatch['detected_lang']}'"
                )
                print(f"  [BLOCKED] {rtype}/{pdf['name']}: {msg}")
                manifest[file_id] = {
                    **prev,
                    'rtype': rtype,
                    'name': pdf['name'],
                    'modifiedTime': modified,
                    'status': 'language_mismatch',
                    'slug': slug,
                    'lang': lang,
                    'slug_source': slug_source,
                    'lang_source': lang_source,
                    'error': msg,
                    'language_mismatch': lang_mismatch,
                    'public_url': None,
                    'versioned_url': None,
                    'report_id': None,
                    'version': None,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
                _save_manifest(manifest)
                processed.append({**record, 'status': 'language_mismatch', 'error': msg})
                continue

            # Publish guard (BCE-1699): when slug came from filename, sanity-check
            # that the PDF body doesn't strongly identify a *different* project.
            # Prevents Bittensor-content-saved-as-bitcoin_*.pdf style contamination.
            if slug_source == 'filename':
                mismatch = _detect_slug_content_mismatch(project, pdf_text, ocr_text, projects)
                if mismatch:
                    msg = (
                        f"slug/content mismatch — filename resolved '{mismatch['expected_slug']}' "
                        f"(body score {mismatch['expected_score']}) but body strongly matches "
                        f"'{mismatch['detected_slug']}' (score {mismatch['detected_score']})"
                    )
                    print(f"  [BLOCKED] {rtype}/{pdf['name']}: {msg}")
                    manifest[file_id] = {
                        **prev,
                        'rtype': rtype,
                        'name': pdf['name'],
                        'modifiedTime': modified,
                        'parent_folder_id': pdf.get('parent_folder_id'),
                        'parent_folder_name': pdf.get('parent_folder_name'),
                        'source_path': pdf.get('source_path'),
                        'source_depth': pdf.get('source_depth'),
                        'status': 'mismatch',
                        'slug': slug,
                        'lang': lang,
                        'slug_source': slug_source,
                        'lang_source': lang_source,
                        'error': msg,
                        'mismatch': mismatch,
                        'public_url': None,
                        'versioned_url': None,
                        'report_id': None,
                        'version': None,
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }
                    _save_manifest(manifest)
                    processed.append({**record, 'status': 'mismatch', 'error': msg})
                    continue

            current_langs_by_pair.setdefault((rtype, slug), set()).add(lang)

            print(
                f"\n  [PROCESS] {rtype}/{pdf['name']} "
                f"→ slug={slug} ({slug_source}), lang={lang} ({lang_source}), modified={modified}"
            )
            if dry_run:
                print("    DRY-RUN: would convert → upload → DB merge")
                processed.append({**record, 'status': 'dry_run'})
                continue

            manifest[file_id] = {
                **prev,
                'rtype': rtype,
                'slug': slug,
                'lang': lang,
                'slug_source': slug_source,
                'lang_source': lang_source,
                'name': pdf['name'],
                'modifiedTime': modified,
                'parent_folder_id': pdf.get('parent_folder_id'),
                'parent_folder_name': pdf.get('parent_folder_name'),
                'source_path': pdf.get('source_path'),
                'source_depth': pdf.get('source_depth'),
                'page_profile': page_profile,
                'status': 'processing',
                'started_at': datetime.now(timezone.utc).isoformat(),
                'retry_count': prev.get('retry_count', 0) + (1 if prev.get('status') == 'processing' else 0),
            }
            if stale_processing_diag:
                manifest[file_id].update({
                    'recovered_stale_processing_at': datetime.now(timezone.utc).isoformat(),
                    'previous_processing_started_at': prev.get('started_at'),
                    'stale_processing_age_minutes': stale_processing_diag.get('age_minutes'),
                    'stale_processing_threshold_minutes': stale_processing_diag.get('stale_after_minutes'),
                })
            _save_manifest(manifest)

            db_type = DB_REPORT_TYPE[rtype]
            report_id, version, current_status = _find_report_for_lang(sb, project_id, db_type, lang)
            target_status = _target_publication_status(current_status)
            analysis_source = _find_analysis_source_for_slide(
                service,
                project=project,
                rtype=rtype,
                version=version,
            )
            if not analysis_source:
                print(
                    f"    [WARN] analysis/{rtype.upper()} Markdown source missing for "
                    f"{slug}/{DB_REPORT_TYPE[rtype]}/v{version or 1}; "
                    "continuing because Slide PDF presence is the publication trigger"
                )

            try:
                upload_result = _convert_and_upload(
                    tmp_path,
                    rtype=rtype,
                    slug=slug,
                    lang=lang,
                    version=version,
                    storage_client=storage_client,
                )
                public_url = upload_result['latest_url']

                if report_id:
                    _merge_slide_url(sb, report_id, lang, public_url, status=target_status)
                    if target_status == PUBLICATION_PUBLISHED_STATUS:
                        print(f"    ✓ DB published after editorial approval: project_reports[{report_id}].slide_html_urls_by_lang.{lang}")
                    else:
                        print(f"    ✓ DB prepared for editorial review: project_reports[{report_id}].slide_html_urls_by_lang.{lang}")
                else:
                    report_id, version = _create_report_row_for_slide(
                        sb,
                        project_id=project_id,
                        db_type=db_type,
                        slug=slug,
                        lang=lang,
                        pdf_file_id=file_id,
                        pdf_name=pdf['name'],
                        public_url=public_url,
                        version=version,
                        status=target_status,
                    )
                    if report_id:
                        print(
                            f"    ✓ DB created for editorial review: project_reports[{report_id}] "
                            f"for ({slug}, {db_type}, {lang})"
                        )
                    else:
                        print(
                            f"    [WARN] No project_reports row for ({slug}, {db_type}, {lang}); "
                            f"URL uploaded but DB not updated"
                        )

                _generate_summary_after_slide_publish(
                    sb,
                    service,
                    project=project,
                    rtype=rtype,
                    report_id=report_id,
                    version=version,
                    source=analysis_source,
                )

                manifest[file_id].update({
                    'status': 'published' if target_status == PUBLICATION_PUBLISHED_STATUS else 'review_ready',
                    'public_url': public_url,
                    'versioned_url': upload_result['versioned_url'],
                    'report_id': report_id,
                    'version': version,
                    'finished_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'error': None,
                })
                _save_manifest(manifest)
                processed.append({
                    **record,
                    'status': 'published' if target_status == PUBLICATION_PUBLISHED_STATUS else 'review_ready',
                    'public_url': public_url,
                    'report_id': report_id,
                })
                print(f"    ✓ {public_url}")
            except Exception as e:
                err = str(e)[:300]
                manifest[file_id].update({
                    'status': 'failed',
                    'error': err,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                })
                _save_manifest(manifest)
                processed.append({**record, 'status': 'failed', 'error': err})
                print(f"    ✗ failed: {err}")
        finally:
            if downloaded:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    if filter_slug and not filter_file_ids:
        for rtype in types:
            if rtype in active_slide_seen_types or rtype in active_slide_missing_diag_types:
                continue
            diag = {
                'rtype': rtype,
                'slug': filter_slug,
                'lang': None,
                'status': 'no_active_slide_pdf_for_slug',
                'error': 'active_slide_pdf_missing',
                'source_path': f"Slide/{rtype}",
                'source_kind': 'active_slide_diagnostic',
            }
            print(
                f"  [DIAG] {diag['status']}: "
                f"{diag['source_path']} has no active PDF for slug '{filter_slug}'"
            )
            scanned.append(diag)

    if filter_file_ids:
        if prune_candidate_pairs or current_langs_by_pair:
            print("  [SKIP] stale language prune skipped during file-id filtered run")
        return scanned, processed

    prune_pairs = sorted(prune_candidate_pairs | set(current_langs_by_pair.keys()))
    for rtype, slug in prune_pairs:
        current_langs = current_langs_by_pair.get((rtype, slug), set())
        if not current_langs:
            print(f"  [WARN] stale language prune skipped for {rtype}/{slug}: no current publishable PDFs")
            processed.append({
                'rtype': rtype,
                'slug': slug,
                'lang': None,
                'status': 'prune_skipped_no_publishable_pdf',
                'error': 'no current publishable PDFs',
            })
            continue

        project = _project_by_slug(projects, slug)
        project_id = (project or {}).get('id')
        if not project_id:
            print(f"  [WARN] stale language prune skipped for {rtype}/{slug}: project id unavailable")
            processed.append({
                'rtype': rtype,
                'slug': slug,
                'lang': None,
                'status': 'prune_skipped_no_project_id',
                'error': 'project id unavailable',
            })
            continue

        processed.extend(_prune_stale_languages_for_pair(
            sb,
            storage_client,
            rtype=rtype,
            slug=slug,
            project_id=project_id,
            current_langs=current_langs,
            dry_run=dry_run,
        ))

    if reconcile_db:
        if filter_slug:
            print("  [SKIP] DB availability reconcile skipped during slug-filtered run")
        elif sb is None or not projects:
            print("  [SKIP] DB availability reconcile skipped: Supabase/projects unavailable")
        else:
            reconcile_results = _reconcile_visible_reports_with_drive(
                sb,
                service,
                types=types,
                projects=projects,
                dry_run=dry_run,
            )
            processed.extend(reconcile_results)

    return scanned, processed


def _publishable_slide_keys(scanned: List[Dict], processed: List[Dict]) -> Set[Tuple[str, str]]:
    keys: Set[Tuple[str, str]] = set()
    non_publishable_statuses = {
        'skipped_legacy_portrait_pdf',
        'unresolved',
        'mismatch',
        'language_mismatch',
        'failed',
        'prune_skipped_no_publishable_pdf',
        'prune_skipped_no_project_id',
        'prune_skipped_no_supabase',
    }
    for record in list(scanned) + list(processed):
        rtype = record.get('rtype')
        slug = record.get('slug')
        if not rtype or not slug:
            continue
        status = record.get('status')
        if status in non_publishable_statuses:
            continue
        keys.add((rtype, slug))
    return keys


def build_source_slide_diagnostics(
    source_records: List[Dict[str, Any]],
    scanned: List[Dict],
    processed: List[Dict],
) -> List[Dict[str, Any]]:
    """Find source drafts whose active Slide PDF is missing or non-publishable."""
    publishable_keys = _publishable_slide_keys(scanned, processed)
    diagnostics: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, Optional[str]]] = set()
    for source in source_records:
        key = (source.get('rtype'), source.get('slug'))
        if not key[0] or not key[1]:
            continue
        lang = source.get('lang')
        dedupe_key = (key[0], key[1], lang)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        if key in publishable_keys:
            continue
        diagnostics.append({
            'rtype': key[0],
            'slug': key[1],
            'lang': lang,
            'status': 'source_waiting_for_slide_pdf',
            'source_path': source.get('source_path'),
            'source_file_id': source.get('id'),
            'message': 'source draft exists but no publishable active Slide PDF was found',
        })
    return sorted(
        diagnostics,
        key=lambda row: (row.get('rtype') or '', row.get('slug') or '', row.get('lang') or ''),
    )


def run_source_slide_diagnostics(
    types: List[str],
    *,
    filter_slug: Optional[str],
    scanned: List[Dict],
    processed: List[Dict],
) -> List[Dict[str, Any]]:
    """Run source-vs-slide visibility diagnostics for the current watcher run."""
    try:
        service = _get_drive_service()
        source_records = list(_iter_source_draft_records(service, types, filter_slug=filter_slug))
    except Exception as e:
        print(f"\n[DIAG] Unable to scan source drafts: {e}")
        return []

    diagnostics = build_source_slide_diagnostics(source_records, scanned, processed)
    if diagnostics:
        print("\n[DIAG] Source drafts waiting for publishable Slide PDFs:")
        for row in diagnostics:
            lang = row.get('lang') or '?'
            print(
                f"  - {row.get('slug')} {row.get('rtype')} {lang}: "
                f"{row.get('source_path')} → slide generation pending/missing"
            )
    else:
        print("\n[DIAG] No source drafts missing publishable Slide PDFs for this run scope")
    return diagnostics


# ═══════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════

def _record_log_path(record: Dict) -> str:
    """Return a stable display path for file and non-file run result records."""
    if record.get('source_path'):
        return str(record['source_path'])
    if record.get('name'):
        return f"{record.get('rtype')}/{record['name']}"
    slug = record.get('slug') or '?'
    return f"{record.get('rtype')}/{slug}"


def write_run_log(
    scan_time: str,
    types: List[str],
    scanned: List[Dict],
    processed: List[Dict],
    guard_results: Optional[List[Dict[str, Any]]] = None,
    source_diagnostics: Optional[List[Dict[str, Any]]] = None,
    telemetry_warnings: Optional[List[str]] = None,
) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = LOG_DIR / f'{timestamp}.md'

    published = sum(1 for r in processed if r.get('status') == 'published')
    skipped_unchanged = sum(1 for r in scanned if r.get('status') == 'unchanged')
    skipped_legacy = sum(1 for r in scanned if r.get('status') == 'skipped_legacy_portrait_pdf')
    failed = sum(1 for r in processed if r.get('status') == 'failed')
    unresolved = sum(1 for r in processed if r.get('status') == 'unresolved')
    stale_processing_records = [
        r for r in list(scanned) + list(processed)
        if r.get('stale_processing') or r.get('status') == 'processing_in_progress'
    ]
    recovered_stale_processing = sum(1 for r in stale_processing_records if r.get('stale_processing'))
    active_processing = sum(1 for r in stale_processing_records if r.get('status') == 'processing_in_progress')

    lines = [
        f"# Slide Pipeline Run — {scan_time}",
        "",
        f"- Types: {', '.join(types)}",
        f"- Files scanned: {len(scanned)}",
        f"- Skipped (unchanged): {skipped_unchanged}",
        f"- Skipped (legacy portrait PDFs): {skipped_legacy}",
        f"- Processed: {len(processed)}",
        f"- Published: {published}",
        f"- Unresolved: {unresolved}",
        f"- Failed: {failed}",
        f"- Stale processing recovered: {recovered_stale_processing}",
        f"- Active processing skipped: {active_processing}",
        "",
        "## Paperclip Telemetry",
        "",
        f"- Warnings: {len(telemetry_warnings or [])}",
    ]
    if telemetry_warnings:
        for warning in telemetry_warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("*No Paperclip telemetry warnings.*")
    lines += [
        "",
        "## Active Project Backlog Guard",
        "",
        f"- Missing report backlog candidates: {len(guard_results or [])}",
    ]
    for project in guard_results or []:
        symbol = project.get('symbol') or '?'
        name = project.get('name') or project.get('slug') or '?'
        slug = project.get('slug') or '?'
        lines.append(f"  - {slug} ({symbol}) - {name}")
    lines += [
        "",
        "## Source vs Slide Diagnostics",
        "",
        f"- Source drafts waiting for Slide PDFs: {len(source_diagnostics or [])}",
    ]
    if source_diagnostics:
        for row in source_diagnostics:
            lang = row.get('lang') or '?'
            lines.append(
                f"- [source_waiting_for_slide_pdf] `{row.get('source_path')}` "
                f"(slug={row.get('slug')}, type={row.get('rtype')}, lang={lang}) - "
                "slide generation pending/missing"
            )
    else:
        lines.append("*No source drafts missing publishable Slide PDFs for this run scope.*")
    lines += [
        "",
        "## Processing Manifest Health",
        "",
    ]
    if stale_processing_records:
        for row in stale_processing_records:
            path = _record_log_path(row)
            diag = row.get('stale_processing') or {}
            status = 'stale_processing_reprocessed' if diag else row.get('status')
            age = diag.get('age_minutes', row.get('processing_age_minutes'))
            threshold = diag.get('stale_after_minutes', row.get('stale_after_minutes'))
            started_at = diag.get('started_at', row.get('processing_started_at'))
            lines.append(
                f"- [{status}] `{path}` "
                f"(slug={row.get('slug')}, lang={row.get('lang')}, "
                f"started_at={started_at}, age_minutes={age}, threshold_minutes={threshold})"
            )
    else:
        lines.append("*No processing manifest entries were stale or active-in-progress.*")
    lines += [
        "",
        "## Scanned",
        "",
    ]
    if scanned:
        for r in scanned:
            status = r.get('status') or 'target'
            path = _record_log_path(r)
            lines.append(
                f"- [{status}] `{path}` "
                f"(slug={r.get('slug')}, lang={r.get('lang')}, modified={r.get('modifiedTime')})"
            )
    else:
        lines.append("*No matching slide PDFs found.*")

    lines += ["", "## Processed", ""]
    if processed:
        for r in processed:
            extra = r.get('public_url') or r.get('error') or ''
            path = _record_log_path(r)
            lines.append(
                f"- [{r.get('status')}] `{path}` "
                f"(slug={r.get('slug')}, lang={r.get('lang')}) — {extra}"
            )
    else:
        lines.append("*No files needed processing.*")

    lines += ["", "---", "*Generated by BCE-1085/1099 Slide Pipeline Watcher*"]
    log_file.write_text('\n'.join(lines), encoding='utf-8')
    print(f"\n✓ Run log: {log_file}")
    return str(log_file)


def append_telemetry_warnings_to_run_log(log_path: str, telemetry_warnings: List[str]) -> None:
    if not telemetry_warnings:
        return
    try:
        path = Path(log_path)
        existing = path.read_text(encoding='utf-8')
        marker = "## Paperclip Telemetry"
        if marker not in existing:
            return
        lines = existing.splitlines()
        start = lines.index(marker)
        end = start + 1
        while end < len(lines) and not lines[end].startswith('## '):
            end += 1
        replacement = [
            marker,
            "",
            f"- Warnings: {len(telemetry_warnings)}",
            *[f"- {warning}" for warning in telemetry_warnings],
            "",
        ]
        path.write_text('\n'.join(lines[:start] + replacement + lines[end:]) + '\n', encoding='utf-8')
    except Exception as e:
        print(f"  [WARN] Paperclip telemetry log warning append failed: {e}")


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description='Slide pipeline watcher (BCE-1085/1099)')
    parser.add_argument('--type', default='all', choices=['all', 'econ', 'mat', 'for'],
                        help='Report type to process (default: all)')
    parser.add_argument('--slug', default=None,
                        help='Process only files resolving to this slug (post-resolution filter)')
    parser.add_argument('--dry-run', action='store_true', help='Scan only — no download/upload/DB')
    parser.add_argument('--force', action='store_true', help='Reprocess even if manifest is up-to-date')
    parser.add_argument(
        '--skip-db-reconcile',
        action='store_true',
        help='Skip final Drive-vs-DB availability reconciliation for full type scans',
    )
    parser.add_argument(
        '--language-override',
        action='append',
        default=[],
        metavar='FILE_ID=LANG',
        help='Human-confirmed language for a specific Drive PDF file id; repeatable',
    )
    args = parser.parse_args()

    types = ['econ', 'mat', 'for'] if args.type == 'all' else [args.type]
    try:
        language_overrides = _parse_language_overrides(args.language_override)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    scan_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    print('=' * 60)
    print('Slide Pipeline Watcher — BCE-1085/1099')
    print(f'Scan Time: {scan_time}')
    print(f'Types: {types}  Slug filter: {args.slug or "(none)"}  '
          f'Dry-run: {args.dry_run}  Force: {args.force}  '
          f'Language overrides: {len(language_overrides)}')
    print('=' * 60)

    paperclip_telemetry = PaperclipTelemetry()
    paperclip_telemetry.start_runs(
        types,
        scan_time=scan_time,
        dry_run=args.dry_run,
        force=args.force,
        slug=args.slug,
    )

    scanned, processed = process(
        types,
        filter_slug=args.slug,
        filter_file_ids=None,
        dry_run=args.dry_run,
        force=args.force,
        reconcile_db=not args.skip_db_reconcile,
        language_overrides=language_overrides,
    )

    guard_results = run_active_project_backlog_guard()
    source_diagnostics = run_source_slide_diagnostics(
        types,
        filter_slug=args.slug,
        scanned=scanned,
        processed=processed,
    )

    log_path = write_run_log(
        scan_time,
        types,
        scanned,
        processed,
        guard_results=guard_results,
        source_diagnostics=source_diagnostics,
        telemetry_warnings=paperclip_telemetry.warnings,
    )
    paperclip_telemetry.complete_runs(
        types,
        scanned=scanned,
        processed=processed,
        log_path=log_path,
    )
    append_telemetry_warnings_to_run_log(log_path, paperclip_telemetry.warnings)

    print('\n' + '=' * 60)
    print(
        f"DONE: scanned={len(scanned)} processed={len(processed)}  "
        f"published={sum(1 for r in processed if r.get('status') == 'published')}  "
        f"review_ready={sum(1 for r in processed if r.get('status') == 'review_ready')}  "
        f"unresolved={sum(1 for r in processed if r.get('status') == 'unresolved')}  "
        f"failed={sum(1 for r in processed if r.get('status') == 'failed')}  "
        f"guard_candidates={len(guard_results)}  "
        f"source_slide_gaps={len(source_diagnostics)}"
    )
    print('=' * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
