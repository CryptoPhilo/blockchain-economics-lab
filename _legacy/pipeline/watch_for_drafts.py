#!/usr/bin/env python3
"""
DEPRECATED FOR draft watcher — do not run in production.

This archived watcher scans the obsolete GDrive drafts/FOR/ folder. Current
operations use BCE Research Source Drafts as source material and publish slide
PDFs through scripts/pipeline/watch_slides.py. It exits before any Drive scan
unless ALLOW_LEGACY_DRAFT_WATCHER=1 is set for historical reproduction.

Usage:
    ALLOW_LEGACY_DRAFT_WATCHER=1 python watch_for_drafts.py --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

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

# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════

# Log directory
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "for_pipeline"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ALLOW_LEGACY_ENV = 'ALLOW_LEGACY_DRAFT_WATCHER'
CURRENT_PIPELINE_GUIDANCE = (
    "This legacy FOR draft watcher is disabled. It scans obsolete drafts/FOR "
    "content and must not be used for current operations.\n"
    "Current source path: GDrive 'BCE Research Source Drafts' "
    "(example: shiba-inu_econ_v1_en.md).\n"
    "Current publish watcher: python scripts/pipeline/watch_slides.py "
    "--type for --slug <slug> --dry-run\n"
    f"Historical override only: {ALLOW_LEGACY_ENV}=1"
)


# ═══════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════

def load_processed_snapshot() -> Dict[str, Dict]:
    """Load the shared ingest_for tracker snapshot used by the watcher."""
    from ingest_for import _PROCESSED_LOCAL

    tracker_path = Path(_PROCESSED_LOCAL)
    if not tracker_path.exists():
        return {}
    try:
        return json.loads(tracker_path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def guard_legacy_watcher() -> bool:
    if os.environ.get(ALLOW_LEGACY_ENV) == '1':
        return True
    print(CURRENT_PIPELINE_GUIDANCE, file=sys.stderr)
    return False


def process_draft_file(file_info: Dict, dry_run: bool = False) -> bool:
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

    file_name = file_info['name']

    print(f"\n  Processing: {file_name}")

    # Extract slug from filename: {slug}_for_v{N}.md or just {slug}.md
    slug = file_info.get('slug')
    if not slug:
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

    cmd = [sys.executable, str(ingest_script), '--slug', slug]
    if dry_run:
        cmd.append('--dry-run')

    print(f"    Executing: {' '.join([Path(cmd[0]).name, ingest_script.name, '--slug', slug] + (['--dry-run'] if dry_run else []))}")

    try:
        result = subprocess.run(
            cmd,
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
            file_id = f.get('id') or f.get('file_id', 'N/A')
            modified = f.get('modifiedTime') or f.get('modified') or 'N/A'
            content += f"- **{f['name']}**\n"
            content += f"  - ID: `{file_id}`\n"
            content += f"  - Modified: {modified}\n"
            content += f"  - Size: {f.get('size', 'N/A')} bytes\n"
            content += f"  - Link: {f.get('webViewLink', 'N/A')}\n\n"
    else:
        content += "*No new files detected in this scan.*\n"

    content += f"\n---\n*Generated by deprecated legacy FOR draft watcher (BCE-112 archive)*\n"

    with open(log_file, 'w') as f:
        f.write(content)

    print(f"\n✓ Scan log written: {log_file}")
    return str(log_file)


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='DEPRECATED legacy FOR draft watcher — archive only')
    parser.add_argument('--scan-only', action='store_true', help='Only scan, do not process')
    parser.add_argument('--dry-run', action='store_true', help='Test mode, no actual processing')
    args = parser.parse_args()

    if not guard_legacy_watcher():
        return 2

    scan_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    print("=" * 60)
    print("FOR Draft Watcher — BCE-112")
    print(f"Scan Time: {scan_time}")
    print("=" * 60)

    print("\n[1/4] Loading shared ingest tracker snapshot...")
    processed_snapshot = load_processed_snapshot()
    print(f"  ✓ Loaded {len(processed_snapshot)} tracked item(s)")

    print("\n[2/4] Scanning for new .md files via ingest_for.scan_for_drafts()...")
    from ingest_for import scan_for_drafts

    new_files = scan_for_drafts()
    print(f"  ✓ Found {len(new_files)} new file(s)")

    if new_files:
        for f in new_files:
            print(f"    - {f['name']} (modified: {f.get('modified', 'N/A')})")

    print("\n[3/4] Shared scan complete")

    # Step 4: Process new files (if not scan-only)
    processed_count = 0
    if new_files and not args.scan_only:
        print("\n[4/4] Processing new files...")
        for file_info in new_files:
            success = process_draft_file(file_info, dry_run=args.dry_run)
            if success:
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
