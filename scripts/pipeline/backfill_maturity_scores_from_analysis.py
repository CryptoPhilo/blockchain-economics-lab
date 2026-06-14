#!/usr/bin/env python3
"""Backfill tracked project MAT scores from active analysis2/MAT Markdown files."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


PIPELINE_DIR = Path(__file__).resolve().parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pipeline_env import bootstrap_environment

bootstrap_environment(PIPELINE_DIR)

from marketing_content_pipeline import (
    _active_analysis_source_folder_ids,
    _download_drive_text,
    _get_drive_service,
    _list_drive_markdown_sources,
    _parse_markdown_name,
    score_drive_source_for_project,
)
from watch_slides import (
    _extract_maturity_score_from_text,
    _extract_maturity_stage_from_text,
)


DEFAULT_MIN_MATCH_SCORE = 90
DEFAULT_PAGE_SIZE = 1000
DEFAULT_DIAGNOSTIC_LIMIT = 20


@dataclass(frozen=True)
class MatSourceMatch:
    score: int
    item: Dict[str, Any]
    reason: str


def _split_slugs(raw_values: Sequence[str]) -> List[str]:
    slugs: List[str] = []
    seen = set()
    for raw in raw_values:
        for part in re.split(r"[\s,]+", raw or ""):
            slug = part.strip().lower()
            if not slug:
                continue
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
                raise ValueError(f"invalid slug: {slug}")
            if slug in seen:
                continue
            seen.add(slug)
            slugs.append(slug)
    return slugs


def _source_match_for_project(
    project: Dict[str, Any],
    md_items: Iterable[Dict[str, Any]],
    *,
    min_score: int = DEFAULT_MIN_MATCH_SCORE,
) -> Optional[MatSourceMatch]:
    scored: List[MatSourceMatch] = []
    slug = str(project.get("slug") or "").strip().lower()

    for item in md_items:
        name = str(item.get("name") or "")
        parsed = _parse_markdown_name(name)
        if parsed:
            parsed_slug, parsed_type, _version, _lang = parsed
            if parsed_slug.lower() == slug and parsed_type == "mat":
                scored.append(MatSourceMatch(110, item, "exact_structured_name"))
                continue

        score = score_drive_source_for_project(name, project)
        if score >= min_score:
            scored.append(MatSourceMatch(score, item, "natural_filename_score"))

    if not scored:
        return None

    scored.sort(
        key=lambda match: (
            match.score,
            str(match.item.get("modifiedTime") or ""),
            str(match.item.get("name") or ""),
        ),
        reverse=True,
    )
    return scored[0]


def _diagnostic_candidates_for_project(
    project: Dict[str, Any],
    md_items: Iterable[Dict[str, Any]],
    *,
    limit: int = DEFAULT_DIAGNOSTIC_LIMIT,
) -> List[MatSourceMatch]:
    candidates: List[MatSourceMatch] = []
    slug = str(project.get("slug") or "").strip().lower()

    for item in md_items:
        name = str(item.get("name") or "")
        parsed = _parse_markdown_name(name)
        if parsed:
            parsed_slug, parsed_type, _version, _lang = parsed
            if parsed_slug.lower() == slug and parsed_type == "mat":
                candidates.append(MatSourceMatch(110, item, "exact_structured_name"))
                continue

        candidates.append(MatSourceMatch(
            score_drive_source_for_project(name, project),
            item,
            "natural_filename_score",
        ))

    candidates.sort(
        key=lambda match: (
            match.score,
            str(match.item.get("modifiedTime") or ""),
            str(match.item.get("name") or ""),
        ),
        reverse=True,
    )
    return candidates[:limit]


def _env(name: str, *fallbacks: str) -> str:
    for key in (name, *fallbacks):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    return ""


def _get_supabase_client():
    url = _env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
    key = _env("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    if not url:
        raise RuntimeError("SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL is required")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY is required")
    from supabase import create_client

    return create_client(url, key)


def _load_projects(sb, slugs: Sequence[str]) -> List[Dict[str, Any]]:
    columns = "id, slug, name, symbol, aliases, maturity_score, maturity_stage"
    projects: List[Dict[str, Any]] = []
    if slugs:
        for offset in range(0, len(slugs), 100):
            chunk = list(slugs[offset : offset + 100])
            res = sb.table("tracked_projects").select(columns).in_("slug", chunk).execute()
            projects.extend(res.data or [])
        by_slug = {str(project.get("slug") or "").lower(): project for project in projects}
        missing = [slug for slug in slugs if slug not in by_slug]
        for slug in missing:
            print(f"SKIP {slug}: project_not_found")
        return [by_slug[slug] for slug in slugs if slug in by_slug]

    offset = 0
    while True:
        res = (
            sb.table("tracked_projects")
            .select(columns)
            .range(offset, offset + DEFAULT_PAGE_SIZE - 1)
            .execute()
        )
        rows = res.data or []
        projects.extend(rows)
        if len(rows) < DEFAULT_PAGE_SIZE:
            break
        offset += DEFAULT_PAGE_SIZE
    return projects


def backfill_maturity_scores(
    *,
    sb: Any,
    drive_service: Any,
    slugs: Sequence[str],
    dry_run: bool,
    overwrite: bool,
    min_score: int,
    diagnose_no_match: bool = False,
) -> Dict[str, int]:
    folder_ids = _active_analysis_source_folder_ids(drive_service)
    mat_folder_id = folder_ids.get("mat")
    if not mat_folder_id:
        raise RuntimeError("active analysis2/MAT folder not found")

    md_items = _list_drive_markdown_sources(drive_service, mat_folder_id)
    projects = _load_projects(sb, slugs)

    stats = {
        "projects": len(projects),
        "md_files": len(md_items),
        "updated": 0,
        "dry_run_updates": 0,
        "skipped_existing": 0,
        "skipped_no_md": 0,
        "skipped_no_score": 0,
    }
    print(f"analysis2/MAT folder: {mat_folder_id}")
    print(f"analysis2/MAT md files: {len(md_items)}")
    print(f"target projects: {len(projects)}")

    for project in projects:
        slug = str(project.get("slug") or "").lower()
        existing_score = project.get("maturity_score")
        if existing_score is not None and not overwrite:
            stats["skipped_existing"] += 1
            print(f"SKIP {slug}: existing_score={existing_score}")
            continue

        match = _source_match_for_project(project, md_items, min_score=min_score)
        if not match:
            stats["skipped_no_md"] += 1
            print(f"SKIP {slug}: no_analysis2_mat_md")
            if diagnose_no_match:
                for candidate in _diagnostic_candidates_for_project(project, md_items):
                    print(
                        f"    candidate score={candidate.score} "
                        f"source={candidate.item.get('name')}"
                    )
            continue

        text = _download_drive_text(drive_service, str(match.item["id"]))
        maturity_score = _extract_maturity_score_from_text(text)
        if maturity_score is None:
            stats["skipped_no_score"] += 1
            print(f"SKIP {slug}: score_not_found source={match.item.get('name')}")
            continue

        stage = _extract_maturity_stage_from_text(text, maturity_score)
        patch = {
            "maturity_score": maturity_score,
            "maturity_stage": stage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if dry_run:
            stats["dry_run_updates"] += 1
            action = "DRY_RUN"
        else:
            sb.table("tracked_projects").update(patch).eq("id", project["id"]).execute()
            stats["updated"] += 1
            action = "UPDATED"

        print(
            f"{action} {slug}: score={maturity_score:g} stage={stage} "
            f"match={match.score}/{match.reason} source={match.item.get('name')}"
        )

    print("summary:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    return stats


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill tracked_projects.maturity_score from active analysis2/MAT Markdown files.",
    )
    parser.add_argument(
        "--slugs",
        action="append",
        default=[],
        help="Project slugs separated by comma, whitespace, or newlines. Omit to scan all projects.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print changes without updating Supabase.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite projects that already have maturity_score.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=DEFAULT_MIN_MATCH_SCORE,
        help="Minimum natural filename match score for unstructured md names.",
    )
    parser.add_argument(
        "--diagnose-no-match",
        action="store_true",
        help="Print best analysis2/MAT filename candidates when a slug has no match.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        slugs = _split_slugs(args.slugs)
        sb = _get_supabase_client()
        drive_service = _get_drive_service()
        backfill_maturity_scores(
            sb=sb,
            drive_service=drive_service,
            slugs=slugs,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            min_score=args.min_score,
            diagnose_no_match=args.diagnose_no_match,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
