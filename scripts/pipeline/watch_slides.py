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
import base64
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
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

import watch_slides_inspection as _inspection_helpers
from watch_slides_inspection import (
    SUPPORTED_LANGS,
    _cjk_script_counts,
    _cjk_script_signature,
    _detect_language_content_mismatch,
    _extract_pdf_meta_and_text,
    _is_han_dominant_zh,
    _lang_from_filename,
    _lang_from_metadata,
    _lang_from_text,
    _pdf_page_profile,
    _resolve_lang,
)
from watch_slides_matching import (
    _detect_slug_content_mismatch,
    _explicit_report_project_prefix,
    _match_project_by_text,
    _normalize_signal_text,
    _project_signal,
    _resolve_slug,
)
from watch_slides_telemetry import (
    PIPELINE_BLOCKED_STATUSES,
    PIPELINE_FAILURE_STATUSES,
    PIPELINE_NODE_STAGES,
    PIPELINE_NAMES,
    PIPELINE_SUCCESS_STATUSES,
    RemotePipelineState,
    _pipeline_counts_for_type,
    _pipeline_name_from_env,
    _pipeline_status_for_counts,
    _pipeline_utc_now,
    build_pipeline_event_payload,
    build_pipeline_node_run_payload,
    build_pipeline_run_payload,
    PAPERCLIP_NODE_STAGES,
    PaperclipTelemetry,
    _paperclip_counts_for_type,
    _paperclip_status_for_counts,
    build_paperclip_event_payload,
    build_paperclip_run_payload,
)

_TESSERACT_AVAILABLE: Optional[bool] = None


def _ocr_first_page_text(pdf_path: str, max_pages: int = _inspection_helpers.PDF_TEXT_PAGES) -> str:
    """Compatibility wrapper around the extracted OCR helper."""
    global _TESSERACT_AVAILABLE
    _inspection_helpers.shutil = shutil
    _inspection_helpers._TESSERACT_AVAILABLE = _TESSERACT_AVAILABLE
    text = _inspection_helpers._ocr_first_page_text(pdf_path, max_pages)
    _TESSERACT_AVAILABLE = _inspection_helpers._TESSERACT_AVAILABLE
    return text


# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════

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

# NotebookLM slide decks are 16:9 landscape. Legacy PDF reports are portrait
# documents and must not be published as slide HTML.
STALE_PROCESSING_AFTER_MINUTES = int(os.environ.get('SLIDE_PIPELINE_STALE_PROCESSING_MINUTES', '30'))
BLOCKED_RECHECK_AFTER_MINUTES = int(os.environ.get('SLIDE_PIPELINE_BLOCKED_RECHECK_MINUTES', '720'))

TRACKED_PROJECT_GUARD_FIELDS = (
    'id, slug, name, symbol, status, '
    'last_econ_report_at, last_maturity_report_at, last_forensic_report_at, '
    'next_econ_due_at, next_maturity_due_at'
)


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
GDRIVE_PDF_MIME = 'application/pdf'


def _is_pdf_drive_file(file_info: Dict[str, Any]) -> bool:
    """Treat Drive files named .pdf as PDFs even when Drive MIME metadata is stale."""
    name = str(file_info.get('name') or '').strip().lower()
    return file_info.get('mimeType') == GDRIVE_PDF_MIME or name.endswith('.pdf')


def _list_pdfs_direct(service, parent_id: str, modified_since: Optional[datetime] = None) -> List[Dict]:
    """List PDFs in `parent_id` only (no subfolder traversal)."""
    modified_filter = ''
    if modified_since is not None:
        cutoff = modified_since.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        modified_filter = f"and modifiedTime >= '{cutoff}' "
    query = (
        f"'{parent_id}' in parents "
        f"and mimeType != '{GDRIVE_FOLDER_MIME}' "
        f"{modified_filter}"
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
            corpora='allDrives',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(file_info for file_info in resp.get('files', []) if _is_pdf_drive_file(file_info))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def _list_pdfs_direct_for_scope(
    service,
    parent_id: str,
    modified_since: Optional[datetime],
) -> List[Dict]:
    if modified_since is None:
        return _list_pdfs_direct(service, parent_id)
    return _list_pdfs_direct(service, parent_id, modified_since)


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
            corpora='allDrives',
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
            corpora='allDrives',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def _drive_pdf_name_search_terms(filter_slug: Optional[str], projects: List[Dict[str, Any]]) -> Set[str]:
    if not filter_slug:
        return set()
    terms: Set[str] = set()
    project = _project_by_slug(projects, filter_slug)
    if project:
        for value in (project.get('slug'), project.get('name'), project.get('symbol')):
            if value:
                raw = str(value).strip()
                terms.add(raw)
                terms.add(raw.replace('-', ' '))
                terms.add(raw.replace('-', '_'))
    terms.update(_slug_hint_tokens(filter_slug, projects))
    return {term for term in terms if len(term.strip()) >= 2}


def _search_pdfs_by_name(
    service,
    search_terms: Iterable[str],
    modified_since: Optional[datetime] = None,
) -> List[Dict]:
    """Find accessible PDF-like files by filename when direct parent listing misses them."""
    if not hasattr(service, 'files'):
        return []
    modified_filter = ''
    if modified_since is not None:
        cutoff = modified_since.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        modified_filter = f"and modifiedTime >= '{cutoff}' "
    out: List[Dict] = []
    seen_file_ids: Set[str] = set()
    for term in sorted({str(value).strip() for value in search_terms if str(value).strip()}):
        query = (
            f"name contains '{_drive_literal(term)}' "
            f"and mimeType != '{GDRIVE_FOLDER_MIME}' "
            f"{modified_filter}"
            f"and trashed = false"
        )
        page_token = None
        while True:
            resp = service.files().list(
                q=query,
                fields='nextPageToken, files(id, name, mimeType, modifiedTime, size, parents)',
                pageToken=page_token,
                pageSize=100,
                corpora='allDrives',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            for file_info in resp.get('files', []):
                file_id = file_info.get('id')
                if file_id and file_id in seen_file_ids:
                    continue
                if not _is_pdf_drive_file(file_info):
                    continue
                if file_id:
                    seen_file_ids.add(file_id)
                out.append(file_info)
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
            corpora='allDrives',
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


def _blocked_manifest_diagnostic(
    manifest_entry: Dict[str, Any],
    *,
    now: datetime,
    recheck_after_minutes: int = BLOCKED_RECHECK_AFTER_MINUTES,
) -> Optional[Dict[str, Any]]:
    status = manifest_entry.get('status')
    blocked_statuses = set(PIPELINE_BLOCKED_STATUSES) | {
        'language_mismatch',
        'skipped_legacy_portrait_pdf',
    }
    if status not in blocked_statuses:
        return None
    updated_at_raw = manifest_entry.get('updated_at') or manifest_entry.get('processed_at')
    updated_at = _parse_manifest_datetime(updated_at_raw)
    if updated_at is None:
        return {
            'should_recheck': True,
            'status': status,
            'updated_at': updated_at_raw,
            'age_minutes': None,
            'recheck_after_minutes': recheck_after_minutes,
            'reason': 'missing_or_invalid_updated_at',
        }
    age_minutes = max(0, int((now.astimezone(timezone.utc) - updated_at).total_seconds() // 60))
    return {
        'should_recheck': age_minutes >= recheck_after_minutes,
        'status': status,
        'updated_at': updated_at.isoformat(),
        'age_minutes': age_minutes,
        'recheck_after_minutes': recheck_after_minutes,
        'reason': 'age_exceeded_threshold' if age_minutes >= recheck_after_minutes else 'within_backoff',
    }


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
            'file_urls_by_lang',
            'file_url',
            'gdrive_file_id',
        )
    )


def _is_for_coming_soon_placeholder_without_asset(row: Dict[str, Any]) -> bool:
    return (
        _rtype_for_db_type(row.get('report_type')) == 'for'
        and row.get('status') == 'coming_soon'
        and not _report_row_has_slide_html(row)
        and not _report_row_has_legacy_pdf_url(row)
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
# DB lookup helpers
# ═══════════════════════════════════════════

def _source_identity_part(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip())


def _build_report_source_identity(
    *,
    project: Dict[str, Any],
    db_type: str,
    lang: str,
    pdf_file_id: str,
    pdf_modified_time: Optional[str],
    pdf_size: Optional[Any],
    pdf_name: str,
    checksum: Optional[str] = None,
) -> str:
    """Return the stable source/version identity for a Drive-backed report."""
    parts = [
        'gdrive',
        _source_identity_part(project.get('id')),
        _source_identity_part(project.get('slug')),
        _source_identity_part(db_type),
        _source_identity_part(lang),
        _source_identity_part(pdf_file_id),
        _source_identity_part(pdf_modified_time),
        _source_identity_part(pdf_size),
        _source_identity_part(checksum),
        _source_identity_part(pdf_name),
    ]
    return '|'.join(parts)


def _report_source_patch(
    *,
    project: Dict[str, Any],
    db_type: str,
    lang: str,
    pdf_file_id: str,
    pdf_modified_time: Optional[str],
    pdf_size: Optional[Any],
    pdf_name: str,
    checksum: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        'source_identity': _build_report_source_identity(
            project=project,
            db_type=db_type,
            lang=lang,
            pdf_file_id=pdf_file_id,
            pdf_modified_time=pdf_modified_time,
            pdf_size=pdf_size,
            pdf_name=pdf_name,
            checksum=checksum,
        ),
        'source_file_id': pdf_file_id,
        'source_modified_time': pdf_modified_time,
        'source_size': int(pdf_size) if str(pdf_size or '').isdigit() else None,
        'source_checksum': checksum,
        'source_filename': pdf_name,
    }


def _find_report_for_source_identity(
    sb,
    *,
    project_id: str,
    db_type: str,
    lang: str,
    source_identity: str,
    pdf_file_id: str,
) -> Optional[Dict[str, Any]]:
    """Find the report row for an already-ingested Drive PDF source."""
    select_cols = 'id, version, status, source_identity, source_file_id, gdrive_file_id'
    try:
        res = sb.table('project_reports').select(select_cols) \
            .eq('project_id', project_id) \
            .eq('report_type', db_type) \
            .eq('language', lang) \
            .eq('source_identity', source_identity) \
            .limit(1) \
            .execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass

    try:
        res = sb.table('project_reports').select(select_cols) \
            .eq('project_id', project_id) \
            .eq('report_type', db_type) \
            .eq('language', lang) \
            .eq('source_file_id', pdf_file_id) \
            .limit(1) \
            .execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass

    try:
        res = sb.table('project_reports').select('id, version, status, gdrive_file_id') \
            .eq('project_id', project_id) \
            .eq('report_type', db_type) \
            .eq('language', lang) \
            .eq('gdrive_file_id', pdf_file_id) \
            .limit(1) \
            .execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return None


def _latest_report_row_for_lang(sb, project_id: str, db_type: str, lang: str) -> Optional[Dict[str, Any]]:
    rep = sb.table('project_reports').select(
        'id, version, status, published_at, updated_at, is_latest'
    ) \
        .eq('project_id', project_id) \
        .eq('report_type', db_type) \
        .eq('language', lang) \
        .in_('status', [PUBLICATION_PUBLISHED_STATUS, 'coming_soon', PUBLICATION_APPROVED_STATUS, REVIEW_READY_STATUS]) \
        .order('is_latest', desc=True) \
        .order('version', desc=True) \
        .order('updated_at', desc=True) \
        .limit(1) \
        .execute()
    if not rep.data:
        return None
    return rep.data[0]


def _find_report_for_lang(sb, project_id: str, db_type: str, lang: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """Find the latest published project_reports row for (project, type, language).

    project_reports rows are scoped per (project, type, language); without the
    language filter the URL for one language would be merged into another
    language's row.
    """
    latest = _latest_report_row_for_lang(sb, project_id, db_type, lang)
    if not latest:
        return None, None, None
    report_id = latest['id']
    version = latest.get('version')
    status = latest.get('status')

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


def _resolve_report_version_target(
    sb,
    *,
    project: Dict[str, Any],
    db_type: str,
    lang: str,
    source_patch: Dict[str, Any],
) -> Tuple[Optional[str], int, Optional[str], Optional[str], bool]:
    """Resolve idempotent source row or allocate the next report version."""
    project_id = project.get('id')
    existing = _find_report_for_source_identity(
        sb,
        project_id=project_id,
        db_type=db_type,
        lang=lang,
        source_identity=source_patch['source_identity'],
        pdf_file_id=source_patch['source_file_id'],
    )
    if existing:
        return (
            existing.get('id'),
            int(existing.get('version') or 1),
            existing.get('status'),
            None,
            True,
        )

    try:
        latest = _latest_report_row_for_lang(sb, project_id, db_type, lang)
    except Exception:
        latest_report_id, latest_version, latest_status = _find_report_for_lang(
            sb,
            project_id,
            db_type,
            lang,
        )
        if not latest_report_id:
            return None, 1, None, None, False
        return (
            latest_report_id,
            int(latest_version or 1),
            latest_status,
            None,
            True,
        )
    if not latest:
        return None, 1, None, None, False
    next_version = int(latest.get('version') or 1) + 1
    return None, next_version, latest.get('status'), latest.get('id'), False


def _create_report_row_for_slide(
    sb,
    *,
    project_id: str,
    db_type: str,
    slug: str,
    lang: str,
    pdf_file_id: str,
    pdf_name: str,
    public_url: Optional[str],
    version: Optional[int],
    project_name: Optional[str] = None,
    cover_url: Optional[str] = None,
    status: str = PUBLICATION_PUBLISHED_STATUS,
    source_patch: Optional[Dict[str, Any]] = None,
    previous_report_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[int]]:
    """Create a project_reports row when a slide PDF has no report shell yet."""
    now = datetime.now(timezone.utc).isoformat()
    resolved_version = version or 1
    if status == REVIEW_READY_STATUS:
        status = PUBLICATION_PUBLISHED_STATUS
    gdrive_url = f"https://drive.google.com/file/d/{pdf_file_id}/view?usp=drivesdk"
    row = {
        'project_id': project_id,
        'report_type': db_type,
        'version': resolved_version,
        'language': lang,
        'status': status,
        'review_at': None,
        'published_at': now if status == PUBLICATION_PUBLISHED_STATUS else None,
        'file_url': gdrive_url,
        'gdrive_url': gdrive_url,
        'gdrive_file_id': pdf_file_id,
        'gdrive_urls_by_lang': {lang: gdrive_url},
        'slide_html_urls_by_lang': {lang: public_url} if public_url else {},
        'cover_image_urls_by_lang': {lang: cover_url} if cover_url else {},
        'translation_status': {lang: status},
        'card_data': {
            'report_type': 'econ' if db_type == 'econ' else db_type,
            'slug': slug,
            'generated_at': now,
        },
        'previous_report_id': previous_report_id,
        'is_latest': True,
        'updated_at': now,
    }
    if source_patch:
        row.update(source_patch)
    title_col = f"title_{lang}"
    if lang in SUPPORTED_LANGS:
        row[title_col] = project_name or slug or Path(pdf_name).stem.replace('_', ' ')

    if previous_report_id:
        sb.table('project_reports').update({
            'is_latest': False,
            'updated_at': now,
        }) \
            .eq('project_id', project_id) \
            .eq('report_type', db_type) \
            .eq('language', lang) \
            .execute()

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
    """Treat an active Drive Slide PDF as the publication trigger."""
    return PUBLICATION_PUBLISHED_STATUS


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
    cover_url: Optional[str] = None,
    published_at: Optional[str] = None,
) -> None:
    publish_ts = published_at or datetime.now(timezone.utc).isoformat()
    if status in {REVIEW_READY_STATUS, PUBLICATION_APPROVED_STATUS}:
        status = PUBLICATION_PUBLISHED_STATUS
    current = sb.table('project_reports').select(
        'slide_html_urls_by_lang, cover_image_urls_by_lang, card_data, project_id, report_type'
    ) \
        .eq('id', report_id).single().execute()
    row = current.data or {}
    # project_reports rows are language-scoped; do not carry over stale
    # sibling-language URLs left by older cross-language fallback merges.
    urls = {lang: public_url}
    cover_urls = row.get('cover_image_urls_by_lang') or {}
    if not isinstance(cover_urls, dict):
        cover_urls = {}
    if cover_url:
        cover_urls = {**cover_urls, lang: cover_url}
    card_data = row.get('card_data')
    if isinstance(card_data, dict):
        card_data = {**card_data, 'generated_at': publish_ts}
    update_payload = {
        'slide_html_urls_by_lang': urls,
        'cover_image_urls_by_lang': cover_urls,
        'status': status,
        'updated_at': publish_ts,
    }
    if status == PUBLICATION_PUBLISHED_STATUS:
        update_payload['published_at'] = publish_ts
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
        source_md = patch_card_data.get('source_md') if isinstance(patch_card_data.get('source_md'), dict) else {}
        lang = getattr(source, 'lang', None) or 'ko'
        canonical_title = project.get('name') or project.get('slug')
        patch['card_data'] = {
            **existing_card_data,
            **patch_card_data,
            'slug': project.get('slug'),
            'report_type': 'econ' if rtype == 'econ' else DB_REPORT_TYPE[rtype],
            'source_md': {
                **source_md,
                'slug': project.get('slug'),
                'report_type': rtype,
                'version': version or getattr(source, 'version', None) or 1,
                'language': lang,
            },
        }
        if lang in SUPPORTED_LANGS:
            patch[f'title_{lang}'] = canonical_title
        sb.table('project_reports').update(patch).eq('id', report_id).execute()
        print(
            f"    ✓ {report_label} summary generated from Drive source: "
            f"{source.name} ({source.drive_file_id})"
        )
        return True
    except Exception as e:
        print(f"    [WARN] {report_label} summary generation failed after slide publish: {e}")
        return False


MATURITY_SCORE_PATTERNS = (
    re.compile(r'(?:Overall|Final)?\s*Maturity\s*Score\s*:?\s*\**\s*(\d+(?:\.\d+)?)\s*(?:/100|%)?', re.I),
    re.compile(r'성숙도\s*점수\s*:?\s*\**\s*(\d+(?:\.\d+)?)\s*(?:/100|%)?', re.I),
    re.compile(r'종합\s*성숙도\s*:?\s*\**\s*(\d+(?:\.\d+)?)\s*(?:/\s*100|%)?', re.I),
    re.compile(r'종합\s*점수\s*:?\s*\**\s*(\d+(?:\.\d+)?)\s*(?:/\s*100|%)?', re.I),
    re.compile(r'최종\s*점수\s*:?\s*\**\s*(\d+(?:\.\d+)?)\s*(?:/\s*100|%)?', re.I),
    re.compile(r'합계\s*달성률.*?(\d+(?:\.\d+)?)\s*%', re.I | re.S),
    re.compile(r'종합\s*진행률.*?(\d+(?:\.\d+)?)\s*%', re.I | re.S),
    re.compile(r'최종\s*합계.*?(\d+(?:\.\d+)?)\s*%', re.I | re.S),
    re.compile(r'\*\*(\d+(?:\.\d+)?)%\*\*로\s*(?:평가|산출)', re.I),
)

MATURITY_STAGE_PATTERNS = (
    re.compile(r'(?:Maturity\s*)?Stage\s*:?\s*\**\s*([A-Za-z][A-Za-z _-]{2,30})', re.I),
    re.compile(r'단계\s*:?\s*\**\s*([A-Za-z가-힣][A-Za-z가-힣 _-]{1,30})', re.I),
)

MATURITY_STAGE_ALIASES = {
    'nascent': 'nascent',
    'bootstrap': 'nascent',
    '초기': 'nascent',
    'growing': 'growing',
    'growth': 'growing',
    '성장': 'growing',
    'mature': 'mature',
    'maturity': 'mature',
    '성숙': 'mature',
    'established': 'established',
    '확립': 'established',
}


def _classify_maturity_stage(score: float) -> str:
    if score < 25:
        return 'nascent'
    if score < 50:
        return 'growing'
    if score < 75:
        return 'mature'
    return 'established'


def _extract_maturity_score_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    for pattern in MATURITY_SCORE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            score = float(match.group(1))
        except (TypeError, ValueError):
            continue
        if 0 <= score <= 100:
            return score
    return None


def _extract_maturity_stage_from_text(text: str, score: float) -> str:
    for pattern in MATURITY_STAGE_PATTERNS:
        match = pattern.search(text or '')
        if not match:
            continue
        raw = (match.group(1) or '').strip().lower()
        raw = re.sub(r'[^a-z가-힣_-]+.*$', '', raw)
        normalized = MATURITY_STAGE_ALIASES.get(raw)
        if normalized:
            return normalized
    return _classify_maturity_stage(score)


def _persist_maturity_score_from_source(
    sb,
    *,
    project: Dict[str, Any],
    source: Optional[Any],
) -> bool:
    """Persist MAT score from the required analysis/MAT source after slide publication."""
    if not source or not getattr(source, 'text', None):
        return False

    score = _extract_maturity_score_from_text(source.text)
    if score is None:
        print(f"    [WARN] MAT score not found in analysis/MAT source: {getattr(source, 'name', 'unknown')}")
        return False

    project_id = project.get('id')
    if not project_id:
        print("    [WARN] MAT score not persisted: project id missing")
        return False

    stage = _extract_maturity_stage_from_text(source.text, score)
    patch = {
        'maturity_score': score,
        'maturity_stage': stage,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    sb.table('tracked_projects').update(patch).eq('id', project_id).execute()
    print(
        f"    ✓ tracked_projects.maturity_score updated from analysis/MAT: "
        f"{project.get('slug')}={score:.2f} ({stage})"
    )
    return True


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
    pdf_modified_time: Optional[str] = None,
    pdf_size: Optional[Any] = None,
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
    source_patch = _report_source_patch(
        project=project or {},
        db_type=db_type,
        lang=lang,
        pdf_file_id=pdf_file_id,
        pdf_modified_time=pdf_modified_time,
        pdf_size=pdf_size,
        pdf_name=pdf_name,
    )
    report_id, resolved_version, current_status, previous_report_id, existing_source = _resolve_report_version_target(
        sb,
        project=project or {},
        db_type=db_type,
        lang=lang,
        source_patch=source_patch,
    )
    resolved_version = resolved_version or version
    target_status = _target_publication_status(current_status)

    if report_id:
        _merge_slide_url(sb, report_id, lang, public_url, status=target_status)
        return report_id, resolved_version, 'published_existing_source' if existing_source else 'published'

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
        project_name=(project or {}).get('name'),
        status=target_status,
        source_patch=source_patch,
        previous_report_id=previous_report_id,
    )
    return report_id, created_version or resolved_version, 'published_created' if report_id else 'create_failed'


def _remove_slide_url_if_matches(sb, report_id: str, lang: str, public_url: str) -> bool:
    """Remove a stale slide URL only when DB still points at that exact object."""
    if not report_id or not lang or not public_url:
        return False
    current = sb.table('project_reports').select('slide_html_urls_by_lang, cover_image_urls_by_lang') \
        .eq('id', report_id).single().execute()
    urls = (current.data or {}).get('slide_html_urls_by_lang') or {}
    if not isinstance(urls, dict) or urls.get(lang) != public_url:
        return False
    updated = dict(urls)
    updated.pop(lang, None)
    cover_urls = (current.data or {}).get('cover_image_urls_by_lang') or {}
    if isinstance(cover_urls, dict):
        cover_urls = dict(cover_urls)
        cover_urls.pop(lang, None)
    else:
        cover_urls = {}
    sb.table('project_reports').update({
        'slide_html_urls_by_lang': updated,
        'cover_image_urls_by_lang': cover_urls,
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


def _active_drive_report_inventory(
    service,
    types: Iterable[str],
    projects: List[Dict[str, Any]],
) -> Tuple[Set[Tuple[str, str, str]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return active Slide/{TYPE} report keys plus resolved Drive PDF metadata."""
    pairs: Set[Tuple[str, str, str]] = set()
    resolved_rows: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    for rtype, pdf in _iter_active_slide_targets(service, types, projects=projects):
        project = _match_drive_pdf_project(pdf, projects)
        lang = _lang_from_filename(pdf.get('name') or '')
        db_type = DB_REPORT_TYPE.get(rtype)
        slug = (project or {}).get('slug')
        if db_type and slug and lang:
            pairs.add((db_type, slug, lang))
            resolved_rows.append({
                'rtype': rtype,
                'db_type': db_type,
                'slug': slug,
                'lang': lang,
                'project': project,
                'pdf': pdf,
            })
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
    return pairs, resolved_rows, unresolved


def _active_drive_report_pairs(
    service,
    types: Iterable[str],
    projects: List[Dict[str, Any]],
) -> Tuple[Set[Tuple[str, str, str]], List[Dict[str, Any]]]:
    """Return active Slide/{TYPE} report keys as (db_type, slug, lang)."""
    pairs, _resolved_rows, unresolved = _active_drive_report_inventory(service, types, projects)
    return pairs, unresolved


def _compact_project_signal(value: Any) -> str:
    return re.sub(r'[^a-z0-9]+', '', _normalize_signal_text(str(value or '')))


RECONCILE_FILENAME_PREFIX_ALIASES: Dict[str, str] = {
    'convex': 'convex-finance',
    'deepbook': 'deepbook-protocol',
    'golemnetwork': 'golem-network-tokens',
    'mexc': 'mx-token',
    'story': 'story-protocol',
}


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
    explicit_prefix = _explicit_report_project_prefix(name)
    compact_prefix = _compact_project_signal(explicit_prefix or '')
    alias_slug = RECONCILE_FILENAME_PREFIX_ALIASES.get(compact_prefix)
    if alias_slug:
        for project in projects:
            if (project.get('slug') or '').lower() == alias_slug:
                return project

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
    drive_pairs, drive_rows, unresolved = _active_drive_report_inventory(service, types, projects)
    results.extend(unresolved)
    db_types = {DB_REPORT_TYPE[rtype] for rtype in types if rtype in DB_REPORT_TYPE}
    project_by_id = {p.get('id'): p for p in projects}

    report_rows = [
        row for row in _fetch_all_table_rows(
            sb,
            'project_reports',
            (
                'id, project_id, report_type, language, status, published_at, '
                'updated_at, created_at, gdrive_urls_by_lang, gdrive_url, file_url, '
                'file_urls_by_lang, gdrive_file_id, slide_html_urls_by_lang'
            ),
        )
        if row.get('report_type') in db_types
    ]

    now = datetime.now(timezone.utc).isoformat()
    active_slugs_by_type: Dict[str, Set[str]] = {}
    for db_type, slug, _lang in drive_pairs:
        active_slugs_by_type.setdefault(db_type, set()).add(slug)

    visible_keys = {
        (
            row.get('report_type'),
            (project_by_id.get(row.get('project_id')) or {}).get('slug'),
            row.get('language'),
        )
        for row in report_rows
        if row.get('status') in VISIBLE_REPORT_STATUSES
    }
    for drive_row in drive_rows:
        project = drive_row.get('project') or {}
        pdf = drive_row.get('pdf') or {}
        key = (drive_row.get('db_type'), drive_row.get('slug'), drive_row.get('lang'))
        if key in visible_keys:
            continue
        status = 'dry_run_db_reconcile_materialize' if dry_run else 'db_reconcile_materialized'
        report_id = None
        if not dry_run:
            report_id, _version = _create_report_row_for_slide(
                sb,
                project_id=project.get('id'),
                db_type=drive_row.get('db_type'),
                slug=drive_row.get('slug'),
                lang=drive_row.get('lang'),
                pdf_file_id=pdf.get('id'),
                pdf_name=pdf.get('name') or '',
                public_url=None,
                version=None,
                project_name=project.get('name'),
                status=PUBLICATION_PUBLISHED_STATUS,
            )
        results.append({
            'rtype': drive_row.get('rtype'),
            'slug': drive_row.get('slug'),
            'lang': drive_row.get('lang'),
            'status': status,
            'report_id': report_id,
            'error': 'active Drive Slide PDF materialized as website-visible PDF-backed report row',
        })
        visible_keys.add(key)
        if not dry_run:
            gdrive_url = f"https://drive.google.com/file/d/{pdf.get('id')}/view?usp=drivesdk"
            report_rows.append({
                'id': report_id,
                'project_id': project.get('id'),
                'report_type': drive_row.get('db_type'),
                'language': drive_row.get('lang'),
                'status': PUBLICATION_PUBLISHED_STATUS,
                'published_at': now,
                'updated_at': now,
                'created_at': now,
                'gdrive_urls_by_lang': {drive_row.get('lang'): gdrive_url},
                'gdrive_url': gdrive_url,
                'file_url': gdrive_url,
                'file_urls_by_lang': None,
                'gdrive_file_id': pdf.get('id'),
                'slide_html_urls_by_lang': {},
            })

    for row in report_rows:
        project = project_by_id.get(row.get('project_id')) or {}
        key = (row.get('report_type'), project.get('slug'), row.get('language'))
        if row.get('status') not in VISIBLE_REPORT_STATUSES or key in drive_pairs:
            continue
        is_for = _rtype_for_db_type(row.get('report_type')) == 'for'
        if _is_for_coming_soon_placeholder_without_asset(row):
            status = (
                'dry_run_db_reconcile_for_placeholder_without_active_slide_pdf'
                if dry_run
                else 'db_reconcile_for_placeholder_without_active_slide_pdf'
            )
            results.append({
                'rtype': 'for',
                'slug': project.get('slug'),
                'lang': row.get('language'),
                'status': status,
                'report_id': row.get('id'),
                'error': (
                    'FOR coming_soon placeholder has no active Drive Slide PDF yet; '
                    'retained as a rapid-change pre-slide placeholder'
                ),
            })
            continue
        if is_for:
            status = (
                'dry_run_db_reconcile_cancel_missing_active_slide_pdf'
                if dry_run
                else 'db_reconcile_cancelled_missing_active_slide_pdf'
            )
        else:
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
            'error': 'website-visible report row has no matching active Drive Slide PDF',
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
        if (
            not _lang_map_has_value(row.get('slide_html_urls_by_lang'))
            and not _report_row_has_legacy_pdf_url(row)
        ):
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


def run_db_reconcile_only(types: Iterable[str], *, dry_run: bool) -> List[Dict[str, Any]]:
    """Run the Drive-vs-DB availability reconciliation without slide conversion.

    This is an operational repair path for cases where the manifest/processed
    tracker is already up to date but the website-visible `project_reports`
    state is missing or stale. It intentionally skips PDF download, HTML
    rendering, and Supabase Storage writes.
    """
    service = _get_drive_service()
    from supabase_storage import get_supabase_storage_client

    sb = get_supabase_storage_client()
    projects = _load_tracked_projects(sb)
    return _reconcile_visible_reports_with_drive(
        sb,
        service,
        types=types,
        projects=projects,
        dry_run=dry_run,
    )


# ═══════════════════════════════════════════
# Conversion + upload
# ═══════════════════════════════════════════

_EMBEDDED_IMAGE_RE = re.compile(
    rb'data:(image/(?:jpeg|jpg|png|webp));base64,([A-Za-z0-9+/=]+)'
)


def _cover_extension_for_mime(mime: str) -> str:
    if mime in {'image/jpeg', 'image/jpg'}:
        return 'jpg'
    if mime == 'image/webp':
        return 'webp'
    return 'png'


def _extract_first_embedded_image(html_bytes: bytes) -> Optional[Tuple[str, bytes, str]]:
    match = _EMBEDDED_IMAGE_RE.search(html_bytes)
    if not match:
        return None
    mime = match.group(1).decode('ascii').lower()
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except Exception:
        return None
    return mime, raw, _cover_extension_for_mime(mime)


def _upload_cover_image(
    storage_client,
    *,
    rtype: str,
    slug: str,
    lang: str,
    image: Tuple[str, bytes, str],
) -> str:
    from supabase_storage import upload_html

    mime, raw, ext = image
    cover_key = f'{rtype}/{slug}/latest/{lang}-cover.{ext}'
    return upload_html(
        storage_client,
        BUCKET_NAME,
        cover_key,
        raw,
        content_type=mime,
    )


def _convert_and_upload(
    pdf_local_path: str,
    *,
    rtype: str,
    slug: str,
    lang: str,
    version: Optional[int],
    storage_client,
) -> Dict[str, str]:
    from pdf_to_html_slides import (
        DEFAULT_IMAGE_FORMAT,
        DEFAULT_JPEG_QUALITY,
        DEFAULT_RENDER_DPI,
        build_viewer_html_from_sources,
        convert_pdf_to_html_slides,
        extract_pages_images,
    )
    from supabase_storage import upload_html

    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, f'{lang}.html')
        # Preserve the Drive PDF as the visual source of truth. Pre-compressing
        # here lowered slide HTML resolution even when the original PDF was sharp.
        convert_pdf_to_html_slides(pdf_local_path, output_path=html_path, title=slug, lang=lang)
        html_bytes = Path(html_path).read_bytes()

    version_segment = str(version) if version else 'latest'
    versioned_key = f'{rtype}/{slug}/{version_segment}/{lang}.html'
    latest_key = f'{rtype}/{slug}/latest/{lang}.html'

    cover_image = _extract_first_embedded_image(html_bytes)

    try:
        versioned_url = upload_html(storage_client, BUCKET_NAME, versioned_key, html_bytes)
    except Exception as e:
        if 'Payload too large' not in str(e) and '413' not in str(e):
            raise
        print(
            "    [RETRY] slide HTML exceeded storage object limit; "
            "uploading uncompressed page images as separate assets"
        )
        asset_prefix = f'{rtype}/{slug}/{version_segment}/{lang}_assets'
        page_images = extract_pages_images(
            pdf_local_path,
            dpi=DEFAULT_RENDER_DPI,
            fmt=DEFAULT_IMAGE_FORMAT,
            quality=DEFAULT_JPEG_QUALITY,
        )
        image_sources: List[str] = []
        cover_image = page_images[0] + (_cover_extension_for_mime(page_images[0][0]),) if page_images else None
        for index, (mime, raw) in enumerate(page_images, start=1):
            ext = 'jpg' if mime == 'image/jpeg' else 'png'
            image_key = f'{asset_prefix}/page-{index:03d}.{ext}'
            image_sources.append(
                upload_html(
                    storage_client,
                    BUCKET_NAME,
                    image_key,
                    raw,
                    content_type=mime,
                )
            )
        html_bytes = build_viewer_html_from_sources(
            image_sources,
            title=slug,
            lang=lang,
        ).encode('utf-8')
        versioned_url = upload_html(storage_client, BUCKET_NAME, versioned_key, html_bytes)
    if version_segment != 'latest':
        latest_url = upload_html(storage_client, BUCKET_NAME, latest_key, html_bytes)
    else:
        latest_url = versioned_url

    cover_url = _upload_cover_image(
        storage_client,
        rtype=rtype,
        slug=slug,
        lang=lang,
        image=cover_image,
    ) if cover_image else ''

    return {'versioned_url': versioned_url, 'latest_url': latest_url, 'cover_url': cover_url}


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
    modified_since: Optional[datetime] = None,
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
        root_matched = False
        for pdf in _list_pdfs_direct_for_scope(service, type_folder, modified_since):
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
            root_matched = True
            yield target_rtype, _with_source_metadata(
                pdf,
                parent_folder=root_folder,
                source_path=f"Slide/{root_rtype}",
                depth=0,
            )
        if filter_slug and not root_matched and scan_mode != 'full':
            search_terms = _drive_pdf_name_search_terms(filter_slug, projects or [])
            search_folder = {'id': 'drive-name-search', 'name': 'Drive filename search'}
            for pdf in _search_pdfs_by_name(service, search_terms, modified_since):
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
                if target_rtype != root_rtype or target_rtype not in requested_types:
                    continue
                file_id = pdf.get('id')
                if file_id and file_id in seen_file_ids:
                    continue
                if file_id:
                    seen_file_ids.add(file_id)
                root_matched = True
                pdf = {
                    **pdf,
                    'drive_search_fallback': True,
                    'expected_slide_parent_id': type_folder,
                }
                yield target_rtype, _with_source_metadata(
                    pdf,
                    parent_folder=search_folder,
                    source_path=f"Drive/search/{root_rtype}",
                    depth=0,
                )
        if scan_mode != 'full':
            continue
        scan_requested_root = root_rtype in requested_types or len(requested_types) == len(TYPE_FOLDER_IDS)
        stack: List[Tuple[Dict, str, int]] = [
            (folder, f"Slide/{root_rtype}/{folder.get('name', '')}", 1)
            for folder in _list_child_folders(service, type_folder)
            if scan_requested_root or _folder_matches_slug_hint(
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

            for pdf in _list_pdfs_direct_for_scope(service, folder_id, modified_since):
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
                root_matched = True
                yield target_rtype, _with_source_metadata(
                    pdf,
                    parent_folder=folder,
                    source_path=source_path,
                    depth=depth,
                )

            for child in _list_child_folders(service, folder_id):
                if not scan_requested_root and hint_tokens and not (
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
        if filter_slug and not root_matched:
            search_terms = _drive_pdf_name_search_terms(filter_slug, projects or [])
            search_folder = {'id': 'drive-name-search', 'name': 'Drive filename search'}
            for pdf in _search_pdfs_by_name(service, search_terms, modified_since):
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
                if target_rtype != root_rtype or target_rtype not in requested_types:
                    continue
                file_id = pdf.get('id')
                if file_id and file_id in seen_file_ids:
                    continue
                if file_id:
                    seen_file_ids.add(file_id)
                pdf = {
                    **pdf,
                    'drive_search_fallback': True,
                    'expected_slide_parent_id': type_folder,
                }
                yield target_rtype, _with_source_metadata(
                    pdf,
                    parent_folder=search_folder,
                    source_path=f"Drive/search/{root_rtype}",
                    depth=0,
                )


def _iter_targets(
    service,
    types: Iterable[str],
    *,
    filter_slug: Optional[str] = None,
    projects: Optional[List[Dict[str, Any]]] = None,
    modified_since: Optional[datetime] = None,
):
    """Yield (rtype, pdf_info) for active Slide roots only."""
    for rtype, pdf in _iter_active_slide_targets(
        service,
        types,
        filter_slug=filter_slug,
        projects=projects,
        modified_since=modified_since,
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
    modified_since: Optional[datetime] = None,
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

    target_iter = _iter_targets(
        service,
        types,
        filter_slug=filter_slug,
        projects=projects,
        modified_since=modified_since,
    )

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
        blocked_diag = _blocked_manifest_diagnostic(prev, now=now)
        if (
            blocked_diag
            and prev.get('modifiedTime') == modified
            and not force
            and not blocked_diag.get('should_recheck')
        ):
            age = blocked_diag.get('age_minutes')
            threshold = blocked_diag.get('recheck_after_minutes')
            print(
                f"  [SKIP] {rtype}/{pdf['name']}: manifest status={blocked_diag.get('status')} "
                f"within blocked backoff ({age}min < {threshold}min)"
            )
            scanned.append({
                **record,
                'slug': prev.get('slug'),
                'lang': prev.get('lang'),
                'status': 'blocked_backoff',
                'blocked_status': blocked_diag.get('status'),
                'blocked_age_minutes': age,
                'blocked_updated_at': blocked_diag.get('updated_at'),
                'recheck_after_minutes': threshold,
            })
            continue
        if (
            blocked_diag
            and prev.get('modifiedTime') == modified
            and not force
            and blocked_diag.get('should_recheck')
        ):
            print(
                f"  [RECHECK] {rtype}/{pdf['name']}: manifest status={blocked_diag.get('status')} "
                f"backoff elapsed (age={blocked_diag.get('age_minutes')}min, "
                f"threshold={blocked_diag.get('recheck_after_minutes')}min)"
            )
            record['blocked_recheck'] = blocked_diag
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
                            pdf_modified_time=modified,
                            pdf_size=pdf.get('size'),
                            version=prev.get('version'),
                        )
                        if report_id:
                            print(
                                f"    ✓ DB repaired from unchanged manifest ({repair_status}): "
                                f"project_reports[{report_id}].slide_html_urls_by_lang.{lang}"
                            )
                            if rtype == 'mat' and project:
                                analysis_source = _find_analysis_source_for_slide(
                                    service,
                                    project=project,
                                    rtype=rtype,
                                    version=version,
                                )
                                _persist_maturity_score_from_source(
                                    sb,
                                    project=project,
                                    source=analysis_source,
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
            source_patch = _report_source_patch(
                project=project,
                db_type=db_type,
                lang=lang,
                pdf_file_id=file_id,
                pdf_modified_time=modified,
                pdf_size=pdf.get('size'),
                pdf_name=pdf['name'],
            )
            report_id, version, current_status, previous_report_id, existing_source = _resolve_report_version_target(
                sb,
                project=project,
                db_type=db_type,
                lang=lang,
                source_patch=source_patch,
            )
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
            if existing_source:
                print(
                    f"    [VERSION] existing Drive source identity reused: "
                    f"project_reports[{report_id}] v{version}"
                )
            else:
                print(
                    f"    [VERSION] new Drive source identity: "
                    f"{slug}/{db_type}/{lang} -> v{version}"
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
                cover_url = upload_result.get('cover_url') or None

                if report_id:
                    _merge_slide_url(sb, report_id, lang, public_url, status=target_status, cover_url=cover_url)
                    print(f"    ✓ DB published from Drive Slide PDF: project_reports[{report_id}].slide_html_urls_by_lang.{lang}")
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
                        project_name=project.get('name'),
                        cover_url=cover_url,
                        status=target_status,
                        source_patch=source_patch,
                        previous_report_id=previous_report_id,
                    )
                    if report_id:
                        print(
                            f"    ✓ DB created and published from Drive Slide PDF: project_reports[{report_id}] "
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
                if rtype == 'mat':
                    _persist_maturity_score_from_source(
                        sb,
                        project=project,
                        source=analysis_source,
                    )

                manifest[file_id].update({
                    'status': 'published',
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
                    'status': 'published',
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
            try:
                reconcile_results = _reconcile_visible_reports_with_drive(
                    sb,
                    service,
                    types=types,
                    projects=projects,
                    dry_run=dry_run,
                )
                processed.extend(reconcile_results)
            except Exception as e:
                print(f"  [WARN] DB availability reconcile skipped: {e}")
                processed.append({
                    'rtype': ','.join(types),
                    'slug': None,
                    'lang': None,
                    'status': 'db_reconcile_skipped',
                    'error': str(e)[:300],
                })

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
    skipped_blocked_backoff = sum(1 for r in scanned if r.get('status') == 'blocked_backoff')
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
        f"- Skipped (blocked backoff): {skipped_blocked_backoff}",
        f"- Processed: {len(processed)}",
        f"- Published: {published}",
        f"- Unresolved: {unresolved}",
        f"- Failed: {failed}",
        f"- Stale processing recovered: {recovered_stale_processing}",
        f"- Active processing skipped: {active_processing}",
        "",
        "## Remote Pipeline State",
        "",
        f"- Warnings: {len(telemetry_warnings or [])}",
    ]
    if telemetry_warnings:
        for warning in telemetry_warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("*No remote pipeline state warnings.*")
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
    blocked_backoff_records = [
        r for r in scanned
        if r.get('status') == 'blocked_backoff' or r.get('blocked_recheck')
    ]
    lines += [
        "",
        "## Blocked Recheck Backoff",
        "",
    ]
    if blocked_backoff_records:
        for row in blocked_backoff_records:
            path = _record_log_path(row)
            diag = row.get('blocked_recheck') or {}
            status = 'blocked_recheck' if diag else row.get('status')
            age = diag.get('age_minutes', row.get('blocked_age_minutes'))
            threshold = diag.get('recheck_after_minutes', row.get('recheck_after_minutes'))
            blocked_status = diag.get('status', row.get('blocked_status'))
            updated_at = diag.get('updated_at', row.get('blocked_updated_at'))
            lines.append(
                f"- [{status}] `{path}` "
                f"(blocked_status={blocked_status}, slug={row.get('slug')}, lang={row.get('lang')}, "
                f"updated_at={updated_at}, age_minutes={age}, threshold_minutes={threshold})"
            )
    else:
        lines.append("*No blocked manifest entries were skipped or rechecked by backoff.*")
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
        marker = "## Remote Pipeline State"
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
        print(f"  [WARN] Remote pipeline state log warning append failed: {e}")


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
    parser.add_argument(
        '--modified-since-minutes',
        type=int,
        default=None,
        help='Only scan Drive PDFs modified within this many minutes; disables full DB reconciliation by default.',
    )
    parser.add_argument(
        '--reconcile-only',
        action='store_true',
        help='Only reconcile active Drive Slide PDFs with website-visible DB report rows; skip conversion/upload.',
    )
    args = parser.parse_args()

    types = ['econ', 'mat', 'for'] if args.type == 'all' else [args.type]
    if args.reconcile_only and args.slug:
        print('Error: --reconcile-only cannot be combined with --slug; run it per type or full tree.', file=sys.stderr)
        return 2
    try:
        language_overrides = _parse_language_overrides(args.language_override)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    scan_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    modified_since = None
    if args.modified_since_minutes is not None:
        if args.modified_since_minutes <= 0:
            print('Error: --modified-since-minutes must be greater than 0', file=sys.stderr)
            return 2
        modified_since = datetime.now(timezone.utc) - timedelta(minutes=args.modified_since_minutes)

    print('=' * 60)
    print('Slide Pipeline Watcher — BCE-1085/1099')
    print(f'Scan Time: {scan_time}')
    print(f'Types: {types}  Slug filter: {args.slug or "(none)"}  '
          f'Dry-run: {args.dry_run}  Force: {args.force}  '
          f'Language overrides: {len(language_overrides)}  '
          f'Modified since: {modified_since.isoformat() if modified_since else "(none)"}')
    print('=' * 60)

    remote_pipeline_state = RemotePipelineState()
    remote_pipeline_state.start_runs(
        types,
        scan_time=scan_time,
        dry_run=args.dry_run,
        force=args.force,
        slug=args.slug,
    )

    if args.reconcile_only:
        print('\n[RECONCILE] DB availability repair only; skipping PDF conversion/upload')
        scanned = []
        try:
            processed = run_db_reconcile_only(types, dry_run=args.dry_run)
        except Exception as e:
            print(f"  [WARN] DB availability reconcile-only failed: {e}")
            processed = [{
                'rtype': ','.join(types),
                'slug': None,
                'lang': None,
                'status': 'db_reconcile_only_failed',
                'error': str(e)[:300],
            }]
    else:
        scanned, processed = process(
            types,
            filter_slug=args.slug,
            filter_file_ids=None,
            dry_run=args.dry_run,
            force=args.force,
            reconcile_db=not args.skip_db_reconcile and modified_since is None,
            language_overrides=language_overrides,
            modified_since=modified_since,
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
        telemetry_warnings=remote_pipeline_state.warnings,
    )
    remote_pipeline_state.complete_runs(
        types,
        scanned=scanned,
        processed=processed,
        log_path=log_path,
    )
    append_telemetry_warnings_to_run_log(log_path, remote_pipeline_state.warnings)

    print('\n' + '=' * 60)
    print(
        f"DONE: scanned={len(scanned)} processed={len(processed)}  "
        f"published={sum(1 for r in processed if r.get('status') == 'published')}  "
        f"unresolved={sum(1 for r in processed if r.get('status') == 'unresolved')}  "
        f"failed={sum(1 for r in processed if r.get('status') == 'failed')}  "
        f"guard_candidates={len(guard_results)}  "
        f"source_slide_gaps={len(source_diagnostics)}"
    )
    print('=' * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
