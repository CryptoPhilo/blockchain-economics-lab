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
  3. Optional Anthropic LLM fallback (skipped if ANTHROPIC_API_KEY missing)

Language detection:
  1. PDF metadata `/Title` or `/Subject` keyword scan
  2. langdetect on extracted text

Usage:
    python watch_slides.py                      # all types (econ, mat, for)
    python watch_slides.py --type econ          # one report type only
    python watch_slides.py --slug bitcoin       # post-resolution filter
    python watch_slides.py --dry-run            # scan-only, no uploads
    python watch_slides.py --force              # ignore manifest, reprocess all
"""
from __future__ import annotations

import argparse
import base64
import io
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
# Max characters of extracted text passed to the LLM fallback.
LLM_TEXT_BUDGET = 2000

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


def _render_first_page_png(pdf_path: str, max_dim: int = 1280) -> Optional[bytes]:
    """Render the first page as a PNG (downscaled). Returns None on failure.

    Used for NotebookLM-style raster PDFs that have no text layer
    (see project memory: project_notebooklm_pdf_full_page_raster.md).
    """
    try:
        import fitz  # pymupdf
    except Exception:
        return None
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            doc.close()
            return None
        page = doc.load_page(0)
        rect = page.rect
        scale = min(max_dim / max(rect.width, rect.height, 1), 2.0)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        png_bytes = pix.tobytes('png')
        doc.close()
        return png_bytes
    except Exception:
        return None


# ═══════════════════════════════════════════
# Slug resolution (filename → text → LLM)
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
    """Return lowercase tokens that identify a project."""
    sigs: List[str] = []
    for key in ('slug', 'name', 'symbol'):
        v = (project.get(key) or '').strip().lower()
        if v:
            sigs.append(v)
    # also explode hyphenated slug into tokens
    slug = (project.get('slug') or '').lower()
    if slug:
        sigs.extend([p for p in slug.split('-') if len(p) >= 3])
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


def _llm_classify_project(text: str, projects: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Anthropic fallback. Returns matched project dict or None."""
    if not text:
        return None
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    try:
        import anthropic
    except Exception:
        return None

    candidate_lines = [
        f"- slug={p['slug']} | name={p['name']} | symbol={p['symbol']}"
        for p in projects if p.get('slug')
    ]
    prompt = (
        "You are classifying a slide deck PDF to one project from this catalog.\n"
        "Respond with EXACTLY one slug from the catalog, or the literal string NONE.\n"
        "No other text.\n\n"
        f"Catalog:\n" + '\n'.join(candidate_lines) + "\n\n"
        f"Document text (first {LLM_TEXT_BUDGET} chars):\n"
        f"-----\n{text[:LLM_TEXT_BUDGET]}\n-----\n"
        "Answer:"
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=os.environ.get('ANTHROPIC_CLASSIFY_MODEL', 'claude-haiku-4-5-20251001'),
            max_tokens=32,
            messages=[{'role': 'user', 'content': prompt}],
        )
        answer = ''.join(
            blk.text for blk in msg.content if getattr(blk, 'type', None) == 'text'
        ).strip()
    except Exception as e:
        print(f"    [WARN] LLM classify failed: {e}")
        return None

    answer = answer.strip().splitlines()[0].strip().lower() if answer else ''
    if not answer or answer == 'none':
        return None
    for proj in projects:
        if proj.get('slug', '').lower() == answer:
            return proj
    return None


def _resolve_slug(
    pdf_name: str,
    pdf_text: str,
    projects: List[Dict[str, str]],
) -> Tuple[Optional[Dict[str, str]], str]:
    """Return (project, source) where source ∈ {'filename','pdf_text','llm','none'}."""
    proj = _match_project_by_text(pdf_name, projects)
    if proj:
        return proj, 'filename'
    proj = _match_project_by_text(pdf_text, projects)
    if proj:
        return proj, 'pdf_text'
    proj = _llm_classify_project(pdf_text, projects)
    if proj:
        return proj, 'llm'
    return None, 'none'


def _vision_classify(
    page_png: Optional[bytes],
    projects: List[Dict[str, str]],
) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """Classify (slug, lang) from the rendered first page using a vision model.

    Used as the final fallback when text extraction fails (NotebookLM raster
    PDFs). Returns (project_or_None, lang_or_None).
    """
    if not page_png:
        return None, None
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None, None
    try:
        import anthropic
    except Exception:
        return None, None

    candidate_lines = [
        f"- {p['slug']} ({p.get('name') or ''} / {p.get('symbol') or ''})"
        for p in projects if p.get('slug')
    ]
    catalog = '\n'.join(candidate_lines)
    supported = ', '.join(sorted(SUPPORTED_LANGS))
    prompt = (
        "You are classifying the first slide of a slide-deck PDF.\n"
        "Identify (1) which blockchain project the deck is about and (2) the "
        "primary language of the visible text.\n\n"
        f"Project catalog (use the slug column, exact value):\n{catalog}\n\n"
        f"Languages (use one ISO code, exact value): {supported}\n\n"
        "Reply with EXACTLY one JSON object on a single line, no prose, like:\n"
        '{"slug": "<slug-or-NONE>", "lang": "<code-or-NONE>"}\n'
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=os.environ.get('ANTHROPIC_VISION_MODEL', 'claude-haiku-4-5-20251001'),
            max_tokens=128,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': 'image/png',
                            'data': base64.b64encode(page_png).decode('ascii'),
                        },
                    },
                    {'type': 'text', 'text': prompt},
                ],
            }],
        )
        answer = ''.join(
            blk.text for blk in msg.content if getattr(blk, 'type', None) == 'text'
        ).strip()
    except Exception as e:
        print(f"    [WARN] vision classify failed: {e}")
        return None, None

    parsed_slug: Optional[str] = None
    parsed_lang: Optional[str] = None
    try:
        # Strip code fences/whitespace then locate the JSON object.
        text = answer.strip().strip('`')
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            parsed_slug = (data.get('slug') or '').strip().lower() or None
            parsed_lang = (data.get('lang') or '').strip().lower() or None
    except Exception as e:
        print(f"    [WARN] vision response parse failed ({e}): {answer[:200]!r}")
        return None, None

    project: Optional[Dict[str, str]] = None
    if parsed_slug and parsed_slug != 'none':
        for p in projects:
            if (p.get('slug') or '').lower() == parsed_slug:
                project = p
                break
    if parsed_lang in (None, '', 'none') or parsed_lang not in SUPPORTED_LANGS:
        parsed_lang = None
    return project, parsed_lang


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


def _resolve_lang(meta: Dict[str, str], text: str) -> Tuple[Optional[str], str]:
    code = _lang_from_metadata(meta)
    if code:
        return code, 'metadata'
    code = _lang_from_text(text)
    if code:
        return code, 'langdetect'
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
            project, slug_source = _resolve_slug(pdf['name'], pdf_text, projects)
            lang, lang_source = _resolve_lang(meta, pdf_text)

            # Vision fallback for raster-only NotebookLM PDFs (no text layer).
            if (not project or not lang) and projects:
                page_png = _render_first_page_png(tmp_path)
                vision_project, vision_lang = _vision_classify(page_png, projects)
                if not project and vision_project:
                    project = vision_project
                    slug_source = 'vision'
                if not lang and vision_lang:
                    lang = vision_lang
                    lang_source = 'vision'

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
                    print(
                        f"    [WARN] No project_reports row for ({slug}, {db_type}, {lang}); "
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
