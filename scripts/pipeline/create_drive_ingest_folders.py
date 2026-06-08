#!/usr/bin/env python3
"""Create the active Google Drive ingest folder tree for the slide pipeline.

The watcher scans these active folders by default:

  BCE Lab Reports/
    Slide2/ECON
    Slide2/MAT
    Slide2/FOR
    analysis2/ECON
    analysis2/MAT
    analysis2/FOR

The historical Drive folders remain available through explicit legacy/backfill
pipeline runs.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional

PIPELINE_DIR = Path(__file__).resolve().parent

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from watch_slides import GDRIVE_FOLDER_MIME, _drive_literal, _get_drive_service


def _find_child_folder(service, parent_id: str, name: str) -> Optional[Dict]:
    query = (
        f"'{parent_id}' in parents "
        f"and name = '{_drive_literal(name)}' "
        f"and mimeType = '{GDRIVE_FOLDER_MIME}' "
        f"and trashed = false"
    )
    resp = service.files().list(
        q=query,
        fields="files(id, name, webViewLink)",
        pageSize=10,
        corpora="allDrives",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files") or []
    return files[0] if files else None


def _ensure_child_folder(service, parent_id: str, name: str, *, dry_run: bool) -> Dict:
    if dry_run:
        return {"id": f"DRY_RUN_{parent_id}_{name}", "name": name, "created": True}
    existing = _find_child_folder(service, parent_id, name)
    if existing:
        return {**existing, "created": False}
    created = service.files().create(
        body={
            "name": name,
            "mimeType": GDRIVE_FOLDER_MIME,
            "parents": [parent_id],
        },
        fields="id, name, webViewLink",
        supportsAllDrives=True,
    ).execute()
    return {**created, "created": True}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create BCE active Drive ingest folders.")
    parser.add_argument(
        "--parent-folder-id",
        default=os.environ.get("GDRIVE_ROOT_FOLDER_ID", ""),
        help="Parent Drive folder id. Defaults to GDRIVE_ROOT_FOLDER_ID.",
    )
    parser.add_argument(
        "--root-name",
        default=os.environ.get("BCE_ACTIVE_INGEST_PARENT_FOLDER_NAME", "BCE Lab Reports"),
        help="Top-level ingest folder name to create or reuse.",
    )
    parser.add_argument(
        "--slide-root-name",
        default=os.environ.get("BCE_ACTIVE_SLIDE_ROOT_FOLDER_NAME", "Slide2"),
    )
    parser.add_argument(
        "--analysis-root-name",
        default=os.environ.get("BCE_ACTIVE_ANALYSIS_ROOT_FOLDER_NAME", "analysis2"),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.parent_folder_id:
        raise SystemExit("Error: --parent-folder-id or GDRIVE_ROOT_FOLDER_ID is required")

    service = None if args.dry_run else _get_drive_service()
    root = _ensure_child_folder(
        service,
        args.parent_folder_id,
        args.root_name,
        dry_run=args.dry_run,
    )
    slide = _ensure_child_folder(service, root["id"], args.slide_root_name, dry_run=args.dry_run)
    analysis = _ensure_child_folder(service, root["id"], args.analysis_root_name, dry_run=args.dry_run)

    created: Dict[str, Dict] = {"root": root, "slide": slide, "analysis": analysis}
    for report_type in ("econ", "mat", "for"):
        created[f"slide_{report_type}"] = _ensure_child_folder(
            service,
            slide["id"],
            report_type.upper(),
            dry_run=args.dry_run,
        )
        created[f"analysis_{report_type}"] = _ensure_child_folder(
            service,
            analysis["id"],
            report_type.upper(),
            dry_run=args.dry_run,
        )

    for key, folder in created.items():
        action = "created" if folder.get("created") else "existing"
        print(f"{key}: {folder.get('id')} ({action}) {folder.get('name')}")

    print("\nGitHub secrets / .env.local values:")
    print(f"BCE_SLIDE_ACTIVE_ECON_FOLDER_ID={created['slide_econ']['id']}")
    print(f"BCE_SLIDE_ACTIVE_MAT_FOLDER_ID={created['slide_mat']['id']}")
    print(f"BCE_SLIDE_ACTIVE_FOR_FOLDER_ID={created['slide_for']['id']}")
    print(f"BCE_MARKETING_ACTIVE_ECON_SOURCE_FOLDER_ID={created['analysis_econ']['id']}")
    print(f"BCE_MARKETING_ACTIVE_MAT_SOURCE_FOLDER_ID={created['analysis_mat']['id']}")
    print(f"BCE_MARKETING_ACTIVE_FOR_SOURCE_FOLDER_ID={created['analysis_for']['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
