#!/usr/bin/env python3
"""
Batch Google Drive Upload — uploads all pending report files and records
metadata in Supabase.

Reads project_reports without gdrive_file_id, matches them to local
output files, and uploads via GDriveStorage.

Usage:
    python batch_gdrive_upload.py [--dry-run] [--type econ|maturity|forensic] [--limit N]
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Load env from both .env.local (Supabase) and pipeline .env (GDrive)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env.local')
    load_dotenv(Path(__file__).resolve().parent / '.env')
except ImportError:
    pass

# Set default SA file if not set
if not os.environ.get('GDRIVE_SERVICE_ACCOUNT_FILE'):
    sa_path = Path(__file__).resolve().parent / '.gdrive_service_account.json'
    if sa_path.exists():
        os.environ['GDRIVE_SERVICE_ACCOUNT_FILE'] = str(sa_path)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gdrive_storage import GDriveStorage

OUTPUT_DIR = Path(__file__).resolve().parent / 'output'

# DB report_type → file prefix mapping
TYPE_TO_FILE_PREFIX = {
    'econ': 'econ',
    'maturity': 'mat',
    'forensic': 'for',
}

ALL_LANGUAGES = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh']


def find_report_file(slug: str, report_type: str, version: int, lang: str, ext: str = '.pdf') -> Path | None:
    """Find the output file for a report."""
    prefix = TYPE_TO_FILE_PREFIX.get(report_type, report_type)
    filename = f"{slug}_{prefix}_v{version}_{lang}{ext}"
    path = OUTPUT_DIR / filename
    return path if path.exists() else None


def find_all_language_files(slug: str, report_type: str, version: int, ext: str = '.pdf') -> list[dict]:
    """Find all language variants of a report file."""
    files = []
    for lang in ALL_LANGUAGES:
        path = find_report_file(slug, report_type, version, lang, ext)
        if path:
            files.append({'path': str(path), 'lang': lang})
    return files


def get_pending_reports(gd: GDriveStorage, report_type: str = None, limit: int = None) -> list[dict]:
    """Query Supabase for reports without gdrive_file_id."""
    query = gd.supabase.table('project_reports').select(
        'id, report_type, language, version, status, project_id'
    ).is_('gdrive_file_id', 'null').in_('status', ['published', 'coming_soon'])

    if report_type:
        query = query.eq('report_type', report_type)

    query = query.order('created_at')

    if limit:
        query = query.limit(limit)

    result = query.execute()
    return result.data if result.data else []


def get_project_slug(gd: GDriveStorage, project_id: str) -> str | None:
    """Get project slug from tracked_projects."""
    result = gd.supabase.table('tracked_projects').select('slug').eq('id', project_id).single().execute()
    return result.data.get('slug') if result.data else None


def get_word_count(filepath: Path) -> int | None:
    """Count words in a markdown file."""
    md_path = filepath.with_suffix('.md')
    if not md_path.exists():
        return None
    content = md_path.read_text(encoding='utf-8')
    # CJK chars count as 1 word each
    import re
    cjk = len(re.findall(r'[\u3000-\u9fff\uac00-\ud7af]', content))
    latin = len([w for w in re.sub(r'[\u3000-\u9fff\uac00-\ud7af]', ' ', content).split() if w.strip()])
    return cjk + latin


def main():
    parser = argparse.ArgumentParser(description='Batch upload reports to Google Drive')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--type', choices=['econ', 'maturity', 'forensic'], help='Filter by report type')
    parser.add_argument('--limit', type=int, help='Max reports to process')
    parser.add_argument('--all-langs', action='store_true', help='Upload all language variants')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  BCE Lab — Batch Google Drive Upload")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  Type: {args.type or 'all'}")
    print(f"  Limit: {args.limit or 'none'}")
    print(f"{'='*60}\n")

    gd = GDriveStorage()
    if not gd.connected:
        print("ERROR: Google Drive not connected. Check credentials.")
        sys.exit(1)
    if not gd.has_db:
        print("ERROR: Supabase not connected. Check SUPABASE_URL/SUPABASE_SERVICE_KEY.")
        sys.exit(1)

    print(f"  GDrive: connected")
    print(f"  Supabase: connected")

    # Fetch pending reports
    reports = get_pending_reports(gd, report_type=args.type, limit=args.limit)
    print(f"\n  Pending reports: {len(reports)}")

    if not reports:
        print("  Nothing to upload.")
        return

    # Cache slug lookups
    slug_cache: dict[str, str | None] = {}
    uploaded = 0
    failed = 0
    skipped = 0

    for i, report in enumerate(reports):
        project_id = report['project_id']
        if project_id not in slug_cache:
            slug_cache[project_id] = get_project_slug(gd, project_id)

        slug = slug_cache[project_id]
        if not slug:
            print(f"  [{i+1}/{len(reports)}] SKIP — no slug for project {project_id[:8]}")
            skipped += 1
            continue

        report_type = report['report_type']
        version = report['version']
        lang = report['language']

        # Find file
        pdf_path = find_report_file(slug, report_type, version, lang, '.pdf')
        if not pdf_path:
            # Try markdown
            pdf_path = find_report_file(slug, report_type, version, lang, '.md')

        if not pdf_path:
            print(f"  [{i+1}/{len(reports)}] SKIP — no file for {slug}_{TYPE_TO_FILE_PREFIX.get(report_type, report_type)}_v{version}_{lang}")
            skipped += 1
            continue

        word_count = get_word_count(pdf_path)
        prefix = TYPE_TO_FILE_PREFIX.get(report_type, report_type)

        print(f"  [{i+1}/{len(reports)}] {'DRY' if args.dry_run else 'UPLOAD'}: {slug}_{prefix}_v{version}_{lang}{pdf_path.suffix} ({word_count or '?'} words)")

        if args.dry_run:
            uploaded += 1
            continue

        try:
            if args.all_langs:
                # Upload all language variants
                files = find_all_language_files(slug, report_type, version, pdf_path.suffix)
                if files:
                    results = gd.upload_report_bundle(
                        files=files,
                        project_slug=slug,
                        report_type=prefix,
                        version=version,
                        report_id=report['id'],
                        change_summary=f'Batch upload — {len(files)} languages',
                        word_count=word_count,
                        generator_version='batch-upload-v1',
                        created_by='cto-pipeline',
                    )
                    if results:
                        uploaded += 1
                        print(f"    → {len(results)} languages uploaded")
                    else:
                        failed += 1
            else:
                # Upload primary language only
                result = gd.upload_report(
                    local_path=str(pdf_path),
                    project_slug=slug,
                    report_type=prefix,
                    version=version,
                    lang=lang,
                    report_id=report['id'],
                    change_summary='Batch upload — initial GDrive integration',
                    word_count=word_count,
                    generator_version='batch-upload-v1',
                    created_by='cto-pipeline',
                )
                if result:
                    uploaded += 1
                    print(f"    → {result['url']}")
                else:
                    failed += 1
                    print(f"    → FAILED")

        except Exception as e:
            failed += 1
            print(f"    → ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"  Results:")
    print(f"    Uploaded: {uploaded}")
    print(f"    Failed:   {failed}")
    print(f"    Skipped:  {skipped}")
    print(f"    Total:    {len(reports)}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
