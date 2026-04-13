"""
Google Docs → Markdown Ingestion Pipeline (v1)

Scans GDrive drafts folder for new Korean Google Docs reports,
converts them to Markdown, translates to 6 languages, generates PDFs,
uploads to GDrive, and registers in Supabase.

Pipeline:
    GDrive /drafts/econ/ (Korean Google Docs)
        ↓  Google Docs Export API → text/plain or text/html
        ↓  HTML → Markdown (headings + tables + text preserved)
    Local .md (Korean)
        ↓  Google Translate (paragraph-chunked)
    Local .md × 6 languages (en, ja, zh, fr, es, de)
        ↓  gen_pdf_econ.py / gen_pdf_mat.py
    Local .pdf × 7 languages
        ↓  GDrive upload + Supabase registration

Trigger: Manual — COO runs `python ingest_gdoc.py --type econ`

Folder convention:
    BCE Lab Reports/
        drafts/
            econ/   ← Korean Google Docs dropped here
            mat/    ← Korean Google Docs dropped here
        <project-slug>/
            econ/   ← Final PDFs delivered here
            mat/

Naming convention for Google Docs:
    <project-slug>_econ_v<N>.gdoc   (e.g., "bitcoin_econ_v1")
    <project-slug>_mat_v<N>.gdoc    (e.g., "ethereum_mat_v1")
    Title parsing: split on '_' → slug, type, version

Processing state tracking:
    A file "drafts/_processed.json" in the drafts folder tracks
    which Google Doc file IDs have been processed to avoid re-processing.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# ── Google API ──
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io
except ImportError:
    print("ERROR: google-api-python-client required. pip install google-api-python-client google-auth")
    sys.exit(1)

# ── HTML → Markdown ──
try:
    import html2text
except ImportError:
    html2text = None

# ── Local pipeline modules ──
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import config as pipeline_config  # branding, report types, etc.

# Lazy import — gdrive_storage may not always be available
try:
    from gdrive_storage import GDriveStorage, get_gdrive
except ImportError:
    GDriveStorage = None
    get_gdrive = None

# ── Constants ──
LANGS = ['en', 'ja', 'zh', 'fr', 'es', 'de']
OUTPUT_DIR = SCRIPT_DIR / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)

SA_FILE = os.environ.get(
    'GDRIVE_SERVICE_ACCOUNT_FILE',
    str(SCRIPT_DIR / '.gdrive_service_account.json')
)
ROOT_FOLDER_ID = os.environ.get('GDRIVE_ROOT_FOLDER_ID', '1E87EcasPlrGuet0t6e1CA9kLFO0sTdFq')
DELEGATE_EMAIL = os.environ.get('GDRIVE_DELEGATE_EMAIL', 'zhang@coinlab.co.kr')

PROCESSED_TRACKER_NAME = '_processed.json'


# ═══════════════════════════════════════════════════════
# Google Drive Authentication
# ═══════════════════════════════════════════════════════

def get_drive_service():
    """Authenticate and return Google Drive service.

    Uses service account credentials directly (shared folder access).
    Domain-wide delegation (with_subject) is NOT required since the
    BCE Lab Reports folder is shared with the service account.
    """
    SCOPES = [
        'https://www.googleapis.com/auth/drive',
    ]
    creds = service_account.Credentials.from_service_account_file(SA_FILE, scopes=SCOPES)
    # Note: with_subject delegation removed — service account has direct access
    # to the shared BCE Lab Reports folder.

    drive = build('drive', 'v3', credentials=creds)
    return drive, creds


# ═══════════════════════════════════════════════════════
# Folder Management
# ═══════════════════════════════════════════════════════

def ensure_drafts_folder(drive, report_type: str) -> str:
    """Ensure drafts/<report_type> folder exists under ROOT. Returns folder ID."""
    # Find or create 'drafts'
    drafts_id = _find_or_create_folder(drive, 'drafts', ROOT_FOLDER_ID)
    # Find or create 'drafts/econ' or 'drafts/mat'
    type_id = _find_or_create_folder(drive, report_type, drafts_id)
    return type_id


def _find_or_create_folder(drive, name: str, parent_id: str) -> str:
    """Find a folder by name under parent, or create it."""
    q = (f"name='{name}' and '{parent_id}' in parents "
         f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
    results = drive.files().list(q=q, fields='files(id,name)', spaces='drive').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    # Create
    meta = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }
    folder = drive.files().create(body=meta, fields='id').execute()
    print(f"  Created folder: {name} ({folder['id']})")
    return folder['id']


# ═══════════════════════════════════════════════════════
# Scan for New Google Docs
# ═══════════════════════════════════════════════════════

def load_processed_tracker(drive, folder_id: str) -> dict:
    """Load _processed.json from the drafts folder."""
    q = (f"name='{PROCESSED_TRACKER_NAME}' and '{folder_id}' in parents "
         f"and trashed=false")
    results = drive.files().list(q=q, fields='files(id)').execute()
    files = results.get('files', [])
    if not files:
        return {'processed': {}}

    file_id = files[0]['id']
    content = drive.files().get_media(fileId=file_id).execute()
    return json.loads(content.decode('utf-8'))


def save_processed_tracker(drive, folder_id: str, tracker: dict):
    """Save _processed.json to the drafts folder."""
    q = (f"name='{PROCESSED_TRACKER_NAME}' and '{folder_id}' in parents "
         f"and trashed=false")
    results = drive.files().list(q=q, fields='files(id)').execute()
    files = results.get('files', [])

    content = json.dumps(tracker, indent=2, ensure_ascii=False).encode('utf-8')

    from googleapiclient.http import MediaInMemoryUpload
    media = MediaInMemoryUpload(content, mimetype='application/json')

    if files:
        drive.files().update(fileId=files[0]['id'], media_body=media).execute()
    else:
        meta = {
            'name': PROCESSED_TRACKER_NAME,
            'parents': [folder_id],
            'mimeType': 'application/json',
        }
        drive.files().create(body=meta, media_body=media).execute()


def scan_new_docs(drive, folder_id: str, tracker: dict) -> list:
    """Find Google Docs in folder that haven't been processed yet."""
    q = (f"'{folder_id}' in parents "
         f"and mimeType='application/vnd.google-apps.document' "
         f"and trashed=false")
    results = drive.files().list(
        q=q,
        fields='files(id,name,modifiedTime)',
        orderBy='modifiedTime desc',
    ).execute()

    docs = results.get('files', [])
    new_docs = [d for d in docs if d['id'] not in tracker.get('processed', {})]
    return new_docs


# ═══════════════════════════════════════════════════════
# Google Docs → Markdown Conversion
# ═══════════════════════════════════════════════════════

def parse_doc_name(name: str) -> dict:
    """
    Parse document name into components.
    Expected: "bitcoin_econ_v1" or "ethereum_mat_v2"
    Fallback: use full name as slug.
    """
    # Remove common suffixes
    clean = re.sub(r'\.(gdoc|docx?)$', '', name, flags=re.IGNORECASE).strip()

    # Try pattern: slug_type_vN
    m = re.match(r'^(.+?)_(econ|mat|for)_v(\d+)$', clean, re.IGNORECASE)
    if m:
        return {
            'slug': m.group(1).lower().replace(' ', '-'),
            'report_type': m.group(2).lower(),
            'version': int(m.group(3)),
            'raw_name': name,
        }

    # Fallback: try to extract slug from name
    parts = clean.split('_')
    return {
        'slug': parts[0].lower().replace(' ', '-'),
        'report_type': 'econ',
        'version': 1,
        'raw_name': name,
    }


def export_gdoc_to_markdown(drive, file_id: str) -> str:
    """Export a Google Doc as HTML, then convert to Markdown."""
    # Export as HTML (preserves headings, tables, bold/italic)
    html_content = drive.files().export(
        fileId=file_id,
        mimeType='text/html',
    ).execute().decode('utf-8')

    # Convert HTML → Markdown
    if html2text:
        converter = html2text.HTML2Text()
        converter.body_width = 0  # No line wrapping
        converter.protect_links = True
        converter.unicode_snob = True
        converter.ignore_images = True  # Text + tables + headings only
        converter.ignore_emphasis = False
        md = converter.handle(html_content)
    else:
        # Fallback: basic HTML tag stripping
        md = _basic_html_to_md(html_content)

    return md.strip()


def _basic_html_to_md(html: str) -> str:
    """Minimal HTML→MD fallback without html2text."""
    import re
    text = html
    # Headings
    for i in range(1, 7):
        text = re.sub(rf'<h{i}[^>]*>(.*?)</h{i}>', rf'{"#" * i} \1\n', text, flags=re.DOTALL)
    # Bold / Italic
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<em>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
    # Line breaks
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Clean whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ═══════════════════════════════════════════════════════
# Translation (Korean → 6 languages)
# ═══════════════════════════════════════════════════════

def translate_md_chunked(md_text: str, target_lang: str, chunk_size: int = 4500) -> str:
    """Translate Markdown text paragraph-by-paragraph using Google Translate."""
    from deep_translator import GoogleTranslator

    # Map our lang codes to Google Translate codes
    LANG_MAP = {
        'en': 'en', 'ja': 'ja', 'zh': 'zh-CN',
        'fr': 'fr', 'es': 'es', 'de': 'de',
    }
    gt_lang = LANG_MAP.get(target_lang, target_lang)
    translator = GoogleTranslator(source='ko', target=gt_lang)

    paragraphs = md_text.split('\n\n')
    translated_parts = []
    buffer = ''

    for para in paragraphs:
        # Skip empty or heading-only lines
        if not para.strip():
            translated_parts.append('')
            continue

        if len(buffer) + len(para) + 2 > chunk_size:
            if buffer:
                try:
                    translated_parts.append(translator.translate(buffer.strip()))
                except Exception as e:
                    print(f"    Translation error, keeping original: {e}")
                    translated_parts.append(buffer.strip())
                time.sleep(0.3)
            buffer = para + '\n\n'
        else:
            buffer += para + '\n\n'

    # Flush remaining
    if buffer.strip():
        try:
            translated_parts.append(translator.translate(buffer.strip()))
        except Exception as e:
            translated_parts.append(buffer.strip())

    return '\n\n'.join(translated_parts)


# ═══════════════════════════════════════════════════════
# PDF Generation
# ═══════════════════════════════════════════════════════

def generate_pdf(md_path: Path, project_slug: str, report_type: str, version: int, lang: str) -> Path:
    """Generate branded PDF from markdown file."""
    pdf_path = md_path.with_suffix('.pdf')

    if report_type == 'econ':
        from gen_pdf_econ import generate_econ_pdf
        generate_econ_pdf(str(md_path), str(pdf_path), {
            'project_slug': project_slug,
            'version': version,
            'lang': lang,
        })
    elif report_type == 'mat':
        from gen_pdf_mat import generate_mat_pdf
        generate_mat_pdf(str(md_path), str(pdf_path), {
            'project_slug': project_slug,
            'version': version,
            'lang': lang,
        })
    else:
        # Fallback: use econ PDF generator
        from gen_pdf_econ import generate_econ_pdf
        generate_econ_pdf(str(md_path), str(pdf_path), {
            'project_slug': project_slug,
            'version': version,
            'lang': lang,
        })

    return pdf_path


# ═══════════════════════════════════════════════════════
# Main Pipeline
# ═══════════════════════════════════════════════════════

def process_single_doc(drive, gd: GDriveStorage, doc: dict, report_type: str, dry_run: bool = False):
    """Process a single Google Doc through the full pipeline."""
    info = parse_doc_name(doc['name'])
    slug = info['slug']
    version = info['version']
    rtype = info.get('report_type', report_type)

    print(f"\n{'='*60}")
    print(f"Processing: {doc['name']}")
    print(f"  Project: {slug} | Type: {rtype} | Version: v{version}")
    print(f"  GDrive ID: {doc['id']}")
    print(f"{'='*60}")

    # Step 1: Export Google Doc → Markdown (Korean)
    print("\n[1/5] Exporting Google Doc → Markdown (Korean)...")
    ko_md = export_gdoc_to_markdown(drive, doc['id'])
    ko_path = OUTPUT_DIR / f"{slug}_{rtype}_v{version}_ko.md"
    ko_path.write_text(ko_md, encoding='utf-8')
    print(f"  Saved: {ko_path} ({len(ko_md):,} chars)")

    if dry_run:
        print("  [DRY RUN] Skipping translation, PDF, upload.")
        return {'slug': slug, 'status': 'dry_run', 'ko_path': str(ko_path)}

    # Step 2: Translate Korean → 6 languages
    print("\n[2/5] Translating to 6 languages...")
    md_paths = {'ko': ko_path}
    for lang in LANGS:
        print(f"  → {lang}...", end=' ', flush=True)
        translated = translate_md_chunked(ko_md, lang)
        lang_path = OUTPUT_DIR / f"{slug}_{rtype}_v{version}_{lang}.md"
        lang_path.write_text(translated, encoding='utf-8')
        md_paths[lang] = lang_path
        print(f"done ({len(translated):,} chars)")
        time.sleep(0.5)

    # Step 3: Generate PDFs for all 7 languages
    print("\n[3/5] Generating PDFs...")
    pdf_paths = {}
    for lang, md_path in md_paths.items():
        print(f"  → {lang} PDF...", end=' ', flush=True)
        try:
            pdf_path = generate_pdf(md_path, slug, rtype, version, lang)
            pdf_paths[lang] = pdf_path
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

    # Step 4: Upload PDFs to GDrive
    print("\n[4/5] Uploading PDFs to GDrive...")
    gdrive_urls = {}
    if gd and gd.connected:
        for lang, pdf_path in pdf_paths.items():
            print(f"  → {lang}...", end=' ', flush=True)
            try:
                result = gd.upload_report(
                    local_path=str(pdf_path),
                    project_slug=slug,
                    report_type=rtype,
                    version=version,
                    lang=lang,
                )
                gdrive_urls[lang] = result.get('url', '')
                print(f"done → {result.get('url', 'no url')}")
            except Exception as e:
                print(f"FAILED: {e}")
    else:
        print("  [SKIP] GDrive storage not available. PDFs saved locally only.")
        for lang, pdf_path in pdf_paths.items():
            gdrive_urls[lang] = f"local://{pdf_path}"

    # Step 5: Register in Supabase
    print("\n[5/5] Registering in Supabase...")
    try:
        _register_supabase(slug, rtype, version, gdrive_urls)
        print("  done")
    except Exception as e:
        print(f"  FAILED: {e}")

    return {
        'slug': slug,
        'type': rtype,
        'version': version,
        'status': 'completed',
        'languages': list(gdrive_urls.keys()),
        'gdrive_urls': gdrive_urls,
    }


def _register_supabase(slug: str, report_type: str, version: int, gdrive_urls: dict):
    """Register or update report in Supabase."""
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not supabase_url or not supabase_key:
        print("  Supabase credentials not available, skipping DB registration")
        return

    try:
        from supabase import create_client
        sb = create_client(supabase_url, supabase_key)
    except ImportError:
        print("  supabase-py not installed, skipping")
        return

    # Find project
    proj = sb.table('tracked_projects').select('id').eq('slug', slug).execute()
    if not proj.data:
        print(f"  Project '{slug}' not found in tracked_projects, skipping")
        return
    project_id = proj.data[0]['id']

    # Build translation status
    translation_status = {lang: 'published' for lang in gdrive_urls.keys()}

    # Upsert report
    report_data = {
        'project_id': project_id,
        'report_type': report_type,
        'version': version,
        'status': 'published',
        'published_at': datetime.now(timezone.utc).isoformat(),
        'gdrive_urls_by_lang': gdrive_urls,
        'translation_status': translation_status,
        'title_en': f"{slug.replace('-', ' ').title()} — {report_type.upper()} Report v{version}",
        'title_ko': f"{slug.replace('-', ' ').title()} — {report_type.upper()} 보고서 v{version}",
    }

    # Check existing
    existing = sb.table('project_reports').select('id').eq(
        'project_id', project_id
    ).eq('report_type', report_type).eq('version', version).execute()

    if existing.data:
        sb.table('project_reports').update(report_data).eq('id', existing.data[0]['id']).execute()
        print(f"  Updated existing report {existing.data[0]['id']}")
    else:
        sb.table('project_reports').insert(report_data).execute()
        print(f"  Inserted new report")


# ═══════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Ingest Korean Google Docs → Multilingual PDFs')
    parser.add_argument('--type', choices=['econ', 'mat'], default='econ',
                        help='Report type to process (default: econ)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Only export Markdown, skip translation/PDF/upload')
    parser.add_argument('--slug', type=str, default=None,
                        help='Process only this project slug (optional filter)')
    parser.add_argument('--reprocess', action='store_true',
                        help='Reprocess all docs, ignoring processed tracker')
    args = parser.parse_args()

    print(f"═══ BCE Lab Google Docs Ingestion Pipeline ═══")
    print(f"Report type: {args.type}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Authenticate
    print("[Init] Authenticating with Google Drive...")
    drive, creds = get_drive_service()

    # Ensure drafts folder
    print(f"[Init] Ensuring drafts/{args.type} folder...")
    drafts_folder_id = ensure_drafts_folder(drive, args.type)
    print(f"  Folder ID: {drafts_folder_id}")

    # Load tracker
    tracker = {} if args.reprocess else load_processed_tracker(drive, drafts_folder_id)

    # Scan for new docs
    print("\n[Scan] Looking for new Google Docs...")
    new_docs = scan_new_docs(drive, drafts_folder_id, tracker)

    # Filter by slug if specified
    if args.slug:
        new_docs = [d for d in new_docs if args.slug in d['name'].lower()]

    if not new_docs:
        print("  No new documents found. Done.")
        return

    print(f"  Found {len(new_docs)} new document(s):")
    for d in new_docs:
        print(f"    - {d['name']} (modified: {d['modifiedTime']})")

    # Initialize GDrive storage for uploads
    gd = get_gdrive() if get_gdrive else None

    # Process each document
    results = []
    for doc in new_docs:
        try:
            result = process_single_doc(drive, gd, doc, args.type, dry_run=args.dry_run)
            results.append(result)

            # Mark as processed
            if 'processed' not in tracker:
                tracker['processed'] = {}
            tracker['processed'][doc['id']] = {
                'name': doc['name'],
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'status': result.get('status', 'unknown'),
            }
        except Exception as e:
            print(f"\n  ERROR processing {doc['name']}: {e}")
            import traceback
            traceback.print_exc()

    # Save tracker
    if not args.dry_run:
        print("\n[Save] Updating processed tracker...")
        save_processed_tracker(drive, drafts_folder_id, tracker)

    # Summary
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"  Processed: {len(results)}/{len(new_docs)} documents")
    for r in results:
        langs = r.get('languages', [])
        print(f"  - {r['slug']}: {r['status']} ({len(langs)} languages)")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
