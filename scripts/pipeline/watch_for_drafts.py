#!/usr/bin/env python3
"""
FOR Draft Watcher — BCE-112

30분마다 실행되는 루틴. GDrive drafts/FOR/ 폴더를 스캔하여 새로운 .md 파일을 감지하고 처리.

실행 절차:
1. GDrive drafts/FOR/ 폴더 스캔
2. 신규 .md 파일 감지
3. 발견 시: ingest → 번역 → PDF 생성 → QA → GDrive 업로드 → Supabase 발행
4. 스캔 결과를 for_pipeline_run_{timestamp}.md 로그 파일에 기록

Usage:
    python watch_for_drafts.py              # 스캔 + 자동 처리
    python watch_for_drafts.py --scan-only  # 스캔만 (처리 안 함)
    python watch_for_drafts.py --dry-run    # 테스트 (실제 처리 안 함)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load environment variables from .env.local
_env = Path(__file__).resolve().parent.parent.parent / '.env.local'
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Set default GDrive service account path and root folder
os.environ.setdefault(
    'GDRIVE_SERVICE_ACCOUNT_FILE',
    str(Path(__file__).resolve().parent / '.gdrive_service_account.json'),
)
os.environ.setdefault(
    'GDRIVE_ROOT_FOLDER_ID',
    '1E87EcasPlrGuet0t6e1CA9kLFO0sTdFq',  # BCE Lab Reports folder
)

from gdrive_storage import GDriveStorage


# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════

DRAFTS_FOLDER_NAME = "drafts"
FOR_FOLDER_NAME = "FOR"

# Log directory
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "for_pipeline"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Processed files tracking
PROCESSED_LOG = LOG_DIR / "processed_files.json"


# ═══════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════

def load_processed_files() -> Dict[str, str]:
    """Load record of previously processed files."""
    if not PROCESSED_LOG.exists():
        return {}
    try:
        with open(PROCESSED_LOG, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_processed_file(file_id: str, file_name: str, processed_at: str):
    """Record a file as processed."""
    processed = load_processed_files()
    processed[file_id] = {
        'name': file_name,
        'processed_at': processed_at,
    }
    with open(PROCESSED_LOG, 'w') as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)


def find_drafts_for_folder(gdrive: GDriveStorage) -> Optional[str]:
    """
    Find the drafts/FOR/ folder ID by navigating from root.
    Returns folder_id or None if not found.
    """
    if not gdrive._connected:
        print("[ERROR] Google Drive not connected")
        return None

    # Navigate: root → drafts → FOR
    root_id = gdrive.root_folder_id
    if not root_id:
        print("[ERROR] GDRIVE_ROOT_FOLDER_ID not configured")
        return None

    # Find 'drafts' folder
    drafts_id = gdrive._find_folder(DRAFTS_FOLDER_NAME, root_id)
    if not drafts_id:
        print(f"[ERROR] '{DRAFTS_FOLDER_NAME}' folder not found in root")
        return None

    # Find 'FOR' folder inside drafts
    for_id = gdrive._find_folder(FOR_FOLDER_NAME, drafts_id)
    if not for_id:
        print(f"[ERROR] '{FOR_FOLDER_NAME}' folder not found in drafts/")
        return None

    return for_id


def scan_for_new_drafts(gdrive: GDriveStorage, folder_id: str) -> List[Dict]:
    """
    Scan the drafts/FOR/ folder for new .md files.
    Returns list of new files to process.
    """
    processed = load_processed_files()
    all_files = gdrive.list_folder(folder_id)

    # Filter for .md files
    md_files = [f for f in all_files if f.get('name', '').endswith('.md')]

    # Filter out already processed
    new_files = [
        f for f in md_files
        if f['id'] not in processed
    ]

    return new_files


def process_draft_file(gdrive: GDriveStorage, file_info: Dict, dry_run: bool = False) -> bool:
    """
    Process a single draft file through the FOR pipeline:
    1. Download from GDrive
    2. Ingest with ingest_for.py
    3. Translate to 7 languages
    4. Generate PDFs
    5. Upload back to GDrive
    6. Publish to Supabase

    Returns True if successful.
    """
    import re
    import subprocess

    file_id = file_info['id']
    file_name = file_info['name']

    print(f"\n  Processing: {file_name}")

    if dry_run:
        print(f"    [DRY RUN] Would call: python ingest_for.py --slug <slug>")
        return True

    # Extract slug from filename: {slug}_for_v{N}.md or just {slug}.md
    slug_match = re.match(r'^(.+?)(?:_for)?(?:_v\d+)?\.md$', file_name, re.IGNORECASE)
    if not slug_match:
        print(f"    [ERROR] Cannot extract slug from filename: {file_name}")
        return False

    slug = slug_match.group(1).lower().replace(' ', '-').replace('_', '-')
    print(f"    Extracted slug: {slug}")

    # Call ingest_for.py with the specific slug
    ingest_script = Path(__file__).parent / 'ingest_for.py'
    if not ingest_script.exists():
        print(f"    [ERROR] ingest_for.py not found at {ingest_script}")
        return False

    print(f"    Executing: python {ingest_script.name} --slug {slug}")

    try:
        result = subprocess.run(
            [sys.executable, str(ingest_script), '--slug', slug],
            cwd=ingest_script.parent,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )

        # Print output
        if result.stdout:
            print("    --- Pipeline Output ---")
            for line in result.stdout.splitlines():
                print(f"    {line}")

        if result.returncode == 0:
            print(f"    ✓ Pipeline completed successfully for {slug}")
            return True
        else:
            print(f"    ✗ Pipeline failed with exit code {result.returncode}")
            if result.stderr:
                print("    --- Error Output ---")
                for line in result.stderr.splitlines():
                    print(f"    {line}")
            return False

    except subprocess.TimeoutExpired:
        print(f"    ✗ Pipeline timed out after 30 minutes")
        return False
    except Exception as e:
        print(f"    ✗ Exception running pipeline: {e}")
        return False


def write_scan_log(scan_time: str, new_files: List[Dict], processed_count: int):
    """Write scan results to timestamped log file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"for_pipeline_run_{timestamp}.md"

    content = f"""# FOR Draft Watcher Scan Log

**Scan Time:** {scan_time}
**New Files Found:** {len(new_files)}
**Successfully Processed:** {processed_count}

## Detected Files

"""

    if new_files:
        for f in new_files:
            content += f"- **{f['name']}**\n"
            content += f"  - ID: `{f['id']}`\n"
            content += f"  - Modified: {f.get('modifiedTime', 'N/A')}\n"
            content += f"  - Size: {f.get('size', 'N/A')} bytes\n"
            content += f"  - Link: {f.get('webViewLink', 'N/A')}\n\n"
    else:
        content += "*No new files detected in this scan.*\n"

    content += f"\n---\n*Generated by BCE-112 FOR Draft Watcher*\n"

    with open(log_file, 'w') as f:
        f.write(content)

    print(f"\n✓ Scan log written: {log_file}")
    return str(log_file)


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='FOR Draft Watcher — scan and process drafts')
    parser.add_argument('--scan-only', action='store_true', help='Only scan, do not process')
    parser.add_argument('--dry-run', action='store_true', help='Test mode, no actual processing')
    args = parser.parse_args()

    scan_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    print("=" * 60)
    print("FOR Draft Watcher — BCE-112")
    print(f"Scan Time: {scan_time}")
    print("=" * 60)

    # Step 1: Initialize GDrive connection
    print("\n[1/4] Connecting to Google Drive...")
    gdrive = GDriveStorage()
    if not gdrive._connected:
        print("  ✗ Google Drive connection failed")
        return 1

    print("  ✓ Connected")

    # Step 2: Find drafts/FOR/ folder
    print(f"\n[2/4] Locating {DRAFTS_FOLDER_NAME}/{FOR_FOLDER_NAME}/ folder...")
    for_folder_id = find_drafts_for_folder(gdrive)
    if not for_folder_id:
        print("  ✗ Folder not found")
        return 1

    print(f"  ✓ Found: {for_folder_id}")

    # Step 3: Scan for new .md files
    print("\n[3/4] Scanning for new .md files...")
    new_files = scan_for_new_drafts(gdrive, for_folder_id)
    print(f"  ✓ Found {len(new_files)} new file(s)")

    if new_files:
        for f in new_files:
            print(f"    - {f['name']} (modified: {f.get('modifiedTime', 'N/A')})")

    # Step 4: Process new files (if not scan-only)
    processed_count = 0
    if new_files and not args.scan_only:
        print("\n[4/4] Processing new files...")
        for file_info in new_files:
            success = process_draft_file(gdrive, file_info, dry_run=args.dry_run)
            if success and not args.dry_run:
                save_processed_file(
                    file_info['id'],
                    file_info['name'],
                    datetime.now(timezone.utc).isoformat()
                )
                processed_count += 1
    else:
        print("\n[4/4] Processing skipped (scan-only mode or no new files)")

    # Write scan log
    log_file = write_scan_log(scan_time, new_files, processed_count)

    # Summary
    print("\n" + "=" * 60)
    print(f"SCAN COMPLETE")
    print(f"  New files: {len(new_files)}")
    print(f"  Processed: {processed_count}")
    print(f"  Log: {log_file}")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
