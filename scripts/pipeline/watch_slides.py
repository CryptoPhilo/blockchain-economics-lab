#!/usr/bin/env python3
"""
Slide Pipeline Watcher — BCE-1085 / BCE-1099

Scans `Slide/{TYPE}/` for PDF files (no subfolders, no filename convention),
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
    python watch_slides.py --slug bitcoin       # post-resolution filter
    python watch_slides.py --dry-run            # scan-only, no uploads
    python watch_slides.py --force              # ignore manifest, reprocess all
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

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

# Internal type → DB enum (project_reports.report_type)
DB_REPORT_TYPE: Dict[str, str] = {
    'econ': 'econ',
    'mat':  'maturity',
    'for':  'forensic',
}

BUCKET_NAME = 'slides'

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent.parent
MANIFEST_PATH = PIPELINE_DIR / 'output' / '_slide_processed.json'
LOG_DIR = REPO_ROOT / 'logs' / 'slide_pipeline'

# Pages to extract for content-based identification (cheap; first page already
# contains the title in NotebookLM exports).
PDF_TEXT_PAGES = 3

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


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or '')]


def _load_tracked_projects(sb) -> List[Dict[str, str]]:
    """Fetch all tracked_projects (id, slug, name, symbol)."""
    out: List[Dict[str, str]] = []
    page_size = 1000
    offset = 0
    while True:
        res = sb.table('tracked_projects').select('id, slug, name, symbol') \
            .range(offset, offset + page_size - 1).execute()
        rows = res.data or []
        out.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def _project_signal(project: Dict[str, str]) -> List[str]:
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
    return list({s for s in sigs if s})


def _match_project_by_text(text: str, projects: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Match `text` against project signals. Prefer longer/more specific signals."""
    if not text:
        return None
    t = text.lower()
    tokens = set(_tokenize(text))
    best: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        score = 0
        for sig in _project_signal(proj):
            if not sig:
                continue
            # prefer multi-word/symbol exact-token match; fall back to substring
            if ' ' in sig or '-' in sig:
                if sig in t:
                    score = max(score, len(sig) * 2)
            else:
                if sig in tokens:
                    score = max(score, len(sig) * 2)
                elif len(sig) >= 4 and sig in t:
                    score = max(score, len(sig))
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
    tokens = set(_tokenize(text))
    score = 0
    for sig in _project_signal(proj):
        if not sig:
            continue
        if ' ' in sig or '-' in sig:
            if sig in t:
                score = max(score, len(sig) * 2)
        else:
            if sig in tokens:
                score = max(score, len(sig) * 2)
            elif len(sig) >= 4 and sig in t:
                score = max(score, len(sig))
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

    Heuristic: only blocks when (a) the body has an interpretable text layer,
    (b) some other project's score is at least 12 (covers most slug/name
    tokens >=6 chars), and (c) that score is strictly higher than the resolved
    project's body score. Empty-text-layer PDFs (e.g. NotebookLM raster) are
    skipped to avoid false positives.
    """
    if resolved_project is None:
        return None
    body = (pdf_text or '') + '\n' + (ocr_text or '')
    if len(body.strip()) < 200:
        return None  # not enough body text to decide reliably
    expected_score = _score_project_in_text(body, resolved_project)
    expected_slug = (resolved_project.get('slug') or '').lower()
    best_other: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        if (proj.get('slug') or '').lower() == expected_slug:
            continue
        score = _score_project_in_text(body, proj)
        if score >= 12 and (best_other is None or score > best_other[0]):
            best_other = (score, proj)
    if best_other and best_other[0] > expected_score:
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


def _lang_from_text(text: str) -> Optional[str]:
    if not text or len(text.strip()) < 30:
        return None
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        code = detect(text[:4000])
    except Exception:
        return None
    # langdetect returns codes like 'zh-cn'; normalize to our 2-letter set
    code = code.split('-')[0].lower()
    return code if code in SUPPORTED_LANGS else None


def _resolve_lang(meta: Dict[str, str], text: str, ocr_text: str) -> Tuple[Optional[str], str]:
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


# ═══════════════════════════════════════════
# DB lookup helpers
# ═══════════════════════════════════════════

def _find_report_for_lang(sb, project_id: str, db_type: str, lang: str) -> Tuple[Optional[str], Optional[int]]:
    """Find the latest published project_reports row for (project, type, language).

    project_reports rows are scoped per (project, type, language); without the
    language filter the URL for one language would be merged into another
    language's row.
    """
    rep = sb.table('project_reports').select('id, version, status, published_at') \
        .eq('project_id', project_id) \
        .eq('report_type', db_type) \
        .eq('language', lang) \
        .in_('status', ['published', 'coming_soon']) \
        .order('published_at', desc=True) \
        .limit(1) \
        .execute()
    if not rep.data:
        return None, None
    report_id = rep.data[0]['id']
    version = rep.data[0].get('version')

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

    return report_id, version


def _find_any_report_id(sb, project_id: str, db_type: str) -> Optional[str]:
    """Fallback row when no (project, type, language) match exists.

    The frontend merges `slide_html_urls_by_lang` across every language row of
    the same (project, type), so writing the URL into any sibling row keeps the
    new language available via the cross-row fallback chain.
    """
    rep = sb.table('project_reports').select('id') \
        .eq('project_id', project_id) \
        .eq('report_type', db_type) \
        .in_('status', ['published', 'coming_soon']) \
        .order('published_at', desc=True) \
        .limit(1) \
        .execute()
    return rep.data[0]['id'] if rep.data else None


def _merge_slide_url(sb, report_id: str, lang: str, public_url: str) -> None:
    current = sb.table('project_reports').select('slide_html_urls_by_lang') \
        .eq('id', report_id).single().execute()
    urls = (current.data or {}).get('slide_html_urls_by_lang') or {}
    if not isinstance(urls, dict):
        urls = {}
    urls[lang] = public_url
    sb.table('project_reports').update({
        'slide_html_urls_by_lang': urls,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', report_id).execute()


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

def _iter_targets(service, types: Iterable[str]):
    """Yield (rtype, pdf_info) for every direct-child PDF of Slide/<TYPE>/."""
    for rtype in types:
        type_folder = TYPE_FOLDER_IDS.get(rtype)
        if not type_folder:
            continue
        for pdf in _list_pdfs_direct(service, type_folder):
            yield rtype, pdf


def process(
    types: List[str],
    *,
    filter_slug: Optional[str],
    dry_run: bool,
    force: bool,
) -> Tuple[List[Dict], List[Dict]]:
    service = _get_drive_service()
    manifest = _load_manifest()

    scanned: List[Dict] = []
    processed: List[Dict] = []

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

    for rtype, pdf in _iter_targets(service, types):
        file_id = pdf['id']
        modified = pdf.get('modifiedTime', '')
        record = {
            'rtype': rtype,
            'file_id': file_id,
            'name': pdf['name'],
            'modifiedTime': modified,
            'size': pdf.get('size'),
        }

        prev = manifest.get(file_id) or {}
        if (
            not force
            and prev.get('status') == 'published'
            and prev.get('modifiedTime') == modified
        ):
            scanned.append({**record, 'slug': prev.get('slug'), 'lang': prev.get('lang')})
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
                    'status': 'failed',
                    'error': err[:300],
                    'modifiedTime': modified,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
                _save_manifest(manifest)
                scanned.append({**record, 'slug': None, 'lang': None})
                processed.append({**record, 'slug': None, 'lang': None, 'status': 'failed', 'error': err})
                continue

            meta, pdf_text = _extract_pdf_meta_and_text(tmp_path)

            # Filename match alone often resolves the slug; only invoke OCR
            # (slow) when text-layer extraction can't determine slug or lang.
            filename_match = _match_project_by_text(pdf['name'], projects)
            text_lang = _lang_from_metadata(meta) or _lang_from_text(pdf_text)
            ocr_text = ''
            if not filename_match or not text_lang:
                pdf_text_match = _match_project_by_text(pdf_text, projects)
                if not (filename_match or pdf_text_match) or not text_lang:
                    ocr_text = _ocr_first_page_text(tmp_path)

            project, slug_source = _resolve_slug(pdf['name'], pdf_text, ocr_text, projects)
            lang, lang_source = _resolve_lang(meta, pdf_text, ocr_text)

            slug = (project or {}).get('slug')
            project_id = (project or {}).get('id')
            record.update({'slug': slug, 'lang': lang})
            scanned.append(record.copy())

            if filter_slug and slug != filter_slug:
                print(f"  [SKIP] {rtype}/{pdf['name']}: slug='{slug}' != filter '{filter_slug}'")
                continue

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
                    'status': 'unresolved',
                    'slug': slug,
                    'lang': lang,
                    'slug_source': slug_source,
                    'lang_source': lang_source,
                    'error': msg,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
                _save_manifest(manifest)
                processed.append({**record, 'status': 'unresolved', 'error': msg})
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
                        'status': 'mismatch',
                        'slug': slug,
                        'lang': lang,
                        'slug_source': slug_source,
                        'lang_source': lang_source,
                        'error': msg,
                        'mismatch': mismatch,
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }
                    _save_manifest(manifest)
                    processed.append({**record, 'status': 'mismatch', 'error': msg})
                    continue

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
                'status': 'processing',
                'started_at': datetime.now(timezone.utc).isoformat(),
                'retry_count': prev.get('retry_count', 0) + (1 if prev.get('status') == 'processing' else 0),
            }
            _save_manifest(manifest)

            db_type = DB_REPORT_TYPE[rtype]
            report_id, version = _find_report_for_lang(sb, project_id, db_type, lang)

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
                    _merge_slide_url(sb, report_id, lang, public_url)
                    print(f"    ✓ DB merged: project_reports[{report_id}].slide_html_urls_by_lang.{lang}")
                else:
                    fallback_id = _find_any_report_id(sb, project_id, db_type)
                    if fallback_id:
                        _merge_slide_url(sb, fallback_id, lang, public_url)
                        report_id = fallback_id
                        print(
                            f"    ✓ DB merged (cross-lang fallback): "
                            f"project_reports[{fallback_id}].slide_html_urls_by_lang.{lang} "
                            f"(no row for {slug}/{db_type}/{lang}; using sibling row)"
                        )
                    else:
                        print(
                            f"    [WARN] No project_reports row for ({slug}, {db_type}, *); "
                            f"URL uploaded but DB not updated"
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
                processed.append({**record, 'status': 'published', 'public_url': public_url, 'report_id': report_id})
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

    return scanned, processed


# ═══════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════

def write_run_log(
    scan_time: str,
    types: List[str],
    scanned: List[Dict],
    processed: List[Dict],
) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = LOG_DIR / f'{timestamp}.md'

    published = sum(1 for r in processed if r.get('status') == 'published')
    skipped_unchanged = len(scanned) - len(processed)
    failed = sum(1 for r in processed if r.get('status') == 'failed')
    unresolved = sum(1 for r in processed if r.get('status') == 'unresolved')

    lines = [
        f"# Slide Pipeline Run — {scan_time}",
        "",
        f"- Types: {', '.join(types)}",
        f"- Files scanned: {len(scanned)}",
        f"- Skipped (unchanged): {skipped_unchanged}",
        f"- Processed: {len(processed)}",
        f"- Published: {published}",
        f"- Unresolved: {unresolved}",
        f"- Failed: {failed}",
        "",
        "## Scanned",
        "",
    ]
    if scanned:
        for r in scanned:
            lines.append(
                f"- `{r['rtype']}/{r['name']}` "
                f"(slug={r.get('slug')}, lang={r.get('lang')}, modified={r['modifiedTime']})"
            )
    else:
        lines.append("*No matching slide PDFs found.*")

    lines += ["", "## Processed", ""]
    if processed:
        for r in processed:
            extra = r.get('public_url') or r.get('error') or ''
            lines.append(
                f"- [{r.get('status')}] `{r['rtype']}/{r['name']}` "
                f"(slug={r.get('slug')}, lang={r.get('lang')}) — {extra}"
            )
    else:
        lines.append("*No files needed processing.*")

    lines += ["", "---", "*Generated by BCE-1085/1099 Slide Pipeline Watcher*"]
    log_file.write_text('\n'.join(lines), encoding='utf-8')
    print(f"\n✓ Run log: {log_file}")
    return str(log_file)


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
    args = parser.parse_args()

    types = ['econ', 'mat', 'for'] if args.type == 'all' else [args.type]
    scan_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    print('=' * 60)
    print('Slide Pipeline Watcher — BCE-1085/1099')
    print(f'Scan Time: {scan_time}')
    print(f'Types: {types}  Slug filter: {args.slug or "(none)"}  '
          f'Dry-run: {args.dry_run}  Force: {args.force}')
    print('=' * 60)

    scanned, processed = process(
        types,
        filter_slug=args.slug,
        dry_run=args.dry_run,
        force=args.force,
    )

    write_run_log(scan_time, types, scanned, processed)

    print('\n' + '=' * 60)
    print(
        f"DONE: scanned={len(scanned)} processed={len(processed)}  "
        f"published={sum(1 for r in processed if r.get('status') == 'published')}  "
        f"unresolved={sum(1 for r in processed if r.get('status') == 'unresolved')}  "
        f"failed={sum(1 for r in processed if r.get('status') == 'failed')}"
    )
    print('=' * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
