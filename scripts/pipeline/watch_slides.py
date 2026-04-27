#!/usr/bin/env python3
"""
Slide Pipeline Watcher — BCE-1085

Scans the GDrive Slide/{TYPE}/{slug}/ subtree for *.pdf files whose stem is a
supported language code, converts each new/changed PDF into a self-contained
HTML viewer, uploads it to Supabase Storage, and merges the public URL into
`project_reports.slide_html_urls_by_lang`.

Designed to be invoked from a GitHub Actions cron, mirroring watch_for_drafts.py.

Usage:
    python watch_slides.py                      # all types (econ, mat, for)
    python watch_slides.py --type econ          # one report type only
    python watch_slides.py --slug humanity-protocol --type econ
    python watch_slides.py --dry-run            # scan-only, no uploads
    python watch_slides.py --force              # ignore manifest, reprocess all
"""
from __future__ import annotations

import argparse
import json
import os
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


# ═══════════════════════════════════════════
# GDrive helpers (mirror ingest_for._get_drive_service)
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


def _list_subfolders(service, parent_id: str) -> List[Dict]:
    query = (
        f"'{parent_id}' in parents "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    out: List[Dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields='nextPageToken, files(id, name, modifiedTime)',
            pageToken=page_token,
            pageSize=1000,
        ).execute()
        out.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def _list_pdfs(service, parent_id: str) -> List[Dict]:
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
# Manifest helpers
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
# Slug resolution & DB lookup (mirror ingest_for._resolve_project_slug)
# ═══════════════════════════════════════════

def _resolve_project(sb, raw_slug: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (project_id, canonical_slug) or (None, None)."""
    raw_slug = unicodedata.normalize('NFC', raw_slug)
    fields = 'id, slug, name, symbol'

    proj = sb.table('tracked_projects').select(fields).eq('slug', raw_slug).execute()
    if proj.data:
        p = proj.data[0]
        return p['id'], p['slug']

    symbol_candidate = raw_slug.split('-')[0].upper()
    if symbol_candidate:
        proj = sb.table('tracked_projects').select(fields).eq('symbol', symbol_candidate).execute()
        if proj.data:
            p = proj.data[0]
            return p['id'], p['slug']

    name_part = raw_slug.split('-')[0]
    if name_part:
        proj = sb.table('tracked_projects').select(fields).ilike('name', f'%{name_part}%').execute()
        if proj.data:
            p = proj.data[0]
            return p['id'], p['slug']

    return None, None


def _find_report_for_lang(sb, project_id: str, db_type: str, lang: str) -> Tuple[Optional[str], Optional[int]]:
    """Find the latest published project_reports row for (project, type, language) and infer
    a version for the storage path. Returns (report_id, version_or_None).

    project_reports rows are scoped per (project, type, language); without the
    language filter, the URL for one language would be merged into another
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

    # Optional: refine version via report_versions
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
    """Merge {lang: public_url} into project_reports.slide_html_urls_by_lang."""
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
    """Compress → HTML → upload. Returns {'latest_url', 'versioned_url'}."""
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

def _iter_targets(service, types: Iterable[str], filter_slug: Optional[str]):
    """Yield (rtype, slug, slug_folder_id, pdf_info) for every candidate PDF."""
    for rtype in types:
        type_folder = TYPE_FOLDER_IDS.get(rtype)
        if not type_folder:
            continue
        slug_folders = _list_subfolders(service, type_folder)
        for sf in slug_folders:
            slug = unicodedata.normalize('NFC', sf['name']).strip()
            if filter_slug and slug != filter_slug:
                continue
            pdfs = _list_pdfs(service, sf['id'])
            for pdf in pdfs:
                stem = Path(pdf['name']).stem.lower()
                if stem not in SUPPORTED_LANGS:
                    print(f"  [SKIP] {rtype}/{slug}/{pdf['name']}: stem '{stem}' not a supported language")
                    continue
                yield rtype, slug, sf['id'], pdf, stem


def process(
    types: List[str],
    *,
    filter_slug: Optional[str],
    dry_run: bool,
    force: bool,
) -> Tuple[List[Dict], List[Dict]]:
    """Returns (scanned, processed)."""
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
        sb = storage_client  # supabase client also gives DB access

    for rtype, slug, _slug_folder_id, pdf, lang in _iter_targets(service, types, filter_slug):
        file_id = pdf['id']
        modified = pdf.get('modifiedTime', '')
        record = {
            'rtype': rtype,
            'slug': slug,
            'lang': lang,
            'file_id': file_id,
            'name': pdf['name'],
            'modifiedTime': modified,
            'size': pdf.get('size'),
        }
        scanned.append(record)

        prev = manifest.get(file_id) or {}
        if (
            not force
            and prev.get('status') == 'published'
            and prev.get('modifiedTime') == modified
        ):
            print(f"  [SKIP] {rtype}/{slug}/{pdf['name']}: unchanged since {modified}")
            continue

        print(f"\n  [PROCESS] {rtype}/{slug}/{pdf['name']} (modified={modified})")
        if dry_run:
            print("    DRY-RUN: would download → convert → upload → DB merge")
            processed.append({**record, 'status': 'dry_run'})
            continue

        manifest[file_id] = {
            **prev,
            'status': 'processing',
            'rtype': rtype,
            'slug': slug,
            'lang': lang,
            'modifiedTime': modified,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'retry_count': prev.get('retry_count', 0) + (1 if prev.get('status') == 'processing' else 0),
        }
        _save_manifest(manifest)

        result = {**record, 'status': 'processing'}
        try:
            project_id, canonical_slug = _resolve_project(sb, slug)
            if not project_id:
                msg = f"slug '{slug}' not found in tracked_projects"
                print(f"    [WARN] {msg} — skipping DB update; skipping file")
                manifest[file_id].update({
                    'status': 'skipped_no_project',
                    'error': msg,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                })
                _save_manifest(manifest)
                result['status'] = 'skipped_no_project'
                result['error'] = msg
                processed.append(result)
                continue

            db_type = DB_REPORT_TYPE[rtype]
            report_id, version = _find_report_for_lang(sb, project_id, db_type, lang)

            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp_path = tmp.name
            try:
                _download_file(service, file_id, tmp_path)
                upload_result = _convert_and_upload(
                    tmp_path,
                    rtype=rtype,
                    slug=canonical_slug or slug,
                    lang=lang,
                    version=version,
                    storage_client=storage_client,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            public_url = upload_result['latest_url']

            if report_id:
                _merge_slide_url(sb, report_id, lang, public_url)
                print(f"    ✓ DB merged: project_reports[{report_id}].slide_html_urls_by_lang.{lang}")
            else:
                print(f"    [WARN] No project_reports row for ({canonical_slug}, {db_type}); URL uploaded but DB not updated")

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
            result.update({'status': 'published', 'public_url': public_url, 'report_id': report_id})
            processed.append(result)
            print(f"    ✓ {public_url}")

        except Exception as e:
            err = str(e)[:300]
            manifest[file_id].update({
                'status': 'failed',
                'error': err,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            })
            _save_manifest(manifest)
            result.update({'status': 'failed', 'error': err})
            processed.append(result)
            print(f"    ✗ failed: {err}")

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

    lines = [
        f"# Slide Pipeline Run — {scan_time}",
        "",
        f"- Types: {', '.join(types)}",
        f"- Files scanned: {len(scanned)}",
        f"- Skipped (unchanged): {skipped_unchanged}",
        f"- Processed: {len(processed)}",
        f"- Published: {published}",
        f"- Failed: {failed}",
        "",
        "## Scanned",
        "",
    ]
    if scanned:
        for r in scanned:
            lines.append(
                f"- `{r['rtype']}/{r['slug']}/{r['name']}` "
                f"(lang={r['lang']}, modified={r['modifiedTime']})"
            )
    else:
        lines.append("*No matching slide PDFs found.*")

    lines += ["", "## Processed", ""]
    if processed:
        for r in processed:
            extra = r.get('public_url') or r.get('error') or ''
            lines.append(
                f"- [{r.get('status')}] `{r['rtype']}/{r['slug']}/{r['name']}` (lang={r['lang']}) — {extra}"
            )
    else:
        lines.append("*No files needed processing.*")

    lines += ["", "---", "*Generated by BCE-1085 Slide Pipeline Watcher*"]
    log_file.write_text('\n'.join(lines), encoding='utf-8')
    print(f"\n✓ Run log: {log_file}")
    return str(log_file)


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description='Slide pipeline watcher (BCE-1085)')
    parser.add_argument('--type', default='all', choices=['all', 'econ', 'mat', 'for'],
                        help='Report type to process (default: all)')
    parser.add_argument('--slug', default=None, help='Process a single slug only')
    parser.add_argument('--dry-run', action='store_true', help='Scan only — no download/upload/DB')
    parser.add_argument('--force', action='store_true', help='Reprocess even if manifest is up-to-date')
    args = parser.parse_args()

    types = ['econ', 'mat', 'for'] if args.type == 'all' else [args.type]
    scan_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    print('=' * 60)
    print('Slide Pipeline Watcher — BCE-1085')
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
    print(f"DONE: scanned={len(scanned)} processed={len(processed)}  "
          f"published={sum(1 for r in processed if r.get('status') == 'published')}  "
          f"failed={sum(1 for r in processed if r.get('status') == 'failed')}")
    print('=' * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
