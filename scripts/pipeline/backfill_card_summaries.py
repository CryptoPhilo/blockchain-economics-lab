#!/usr/bin/env python3
"""Audit/apply report card summary backfills.

Default behavior is a production-safe dry-run that emits a diff artifact for
the BCE-1933 sample set. Use --apply only from an approved remote write path.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from marketing_content_pipeline import (
    DB_TYPE_TO_SHORT,
    REPORT_TYPE_TO_DB,
    WEBSITE_VISIBLE_REPORT_STATUSES,
    _get_supabase_client,
    find_drive_source_for_project,
    load_drive_sources,
    load_local_sources,
    report_row_supports_locale,
    run_pipeline,
)


DEFAULT_SAMPLE_SLUGS = ("awe-network", "bitcoin", "ethereum", "starknet", "vision-token")
DEFAULT_OUTPUT = Path("scripts/pipeline/output/card_summary_backfill_audit.json")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or apply card summary backfills.")
    parser.add_argument("--source", choices=["drive", "local"], default="drive")
    parser.add_argument("--source-folder-id", help="Google Drive source folder id override.")
    parser.add_argument(
        "--source-scope",
        choices=["active", "legacy", "all"],
        default="legacy",
        help="Drive analysis roots to scan when --source-folder-id is omitted. Backfills default to legacy analysis/*.",
    )
    parser.add_argument("--local-path", action="append", default=[])
    parser.add_argument("--slug", action="append", default=[], help="Project slug to process. Defaults to BCE-1933 samples.")
    parser.add_argument("--report-type", choices=["econ", "mat", "for"], help="Only process one report type.")
    parser.add_argument("--version", type=int, help="Only process one report version.")
    parser.add_argument("--limit", type=int, help="Maximum sources after filters.")
    parser.add_argument("--apply", action="store_true", help="Persist updates. Requires approved remote production-write path.")
    parser.add_argument("--no-translate", action="store_true", help="Only derive Korean summaries.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="JSON audit artifact path.")
    return parser.parse_args(argv)


def filter_sources(sources, *, slugs, report_type, version, limit):
    slug_set = set(slugs)
    selected = []
    for source in sources:
        if slug_set and source.slug not in slug_set:
            continue
        if report_type and source.report_type != report_type:
            continue
        if version is not None and source.version != version:
            continue
        selected.append(source)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def _latest_report_rows_for_project(sb, project_id: str, *, report_type: Optional[str], version: Optional[int]):
    query = (
        sb.table("project_reports")
        .select(
            "id, project_id, report_type, version, language, status, "
            "gdrive_url, file_url, gdrive_urls_by_lang, file_urls_by_lang, "
            "slide_html_urls_by_lang, updated_at, published_at"
        )
        .eq("project_id", project_id)
        .eq("language", "ko")
        .in_("status", list(WEBSITE_VISIBLE_REPORT_STATUSES))
    )
    if report_type:
        query = query.eq("report_type", REPORT_TYPE_TO_DB[report_type])
    if version is not None:
        query = query.eq("version", version)
    rows = query.execute().data or []
    rows = [
        row for row in rows
        if report_row_supports_locale(row, "ko")
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("report_type") or ""),
            int(row.get("version") or 0),
            str(row.get("published_at") or row.get("updated_at") or ""),
        ),
        reverse=True,
    )
    latest_by_type = {}
    for row in rows:
        latest_by_type.setdefault(row.get("report_type"), row)
    return list(latest_by_type.values())


def load_drive_sources_for_slugs(
    slugs,
    *,
    report_type: Optional[str],
    version: Optional[int],
    limit: Optional[int],
    source_scope: str = "legacy",
):
    sb = _get_supabase_client()
    if sb is None:
        raise RuntimeError("Supabase warehouse client is not available")

    sources = []
    for slug in slugs:
        project_rows = (
            sb.table("tracked_projects")
            .select("id, slug, name, symbol")
            .eq("slug", slug)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not project_rows:
            print(f"[SKIP] tracked project not found for slug={slug}")
            continue
        project = project_rows[0]
        for row in _latest_report_rows_for_project(sb, project["id"], report_type=report_type, version=version):
            short_type = DB_TYPE_TO_SHORT.get(row.get("report_type"))
            if not short_type:
                continue
            source = find_drive_source_for_project(
                project,
                report_type=short_type,
                version=int(row.get("version") or 1),
                source_scope=source_scope,
            )
            if source is None:
                print(f"[SKIP] Drive source not found for slug={slug} type={short_type} version={row.get('version')}")
                continue
            sources.append(source)
            if limit is not None and len(sources) >= limit:
                return sources
    return sources


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    slugs = args.slug or list(DEFAULT_SAMPLE_SLUGS)
    if args.source == "drive":
        if args.source_folder_id:
            sources = load_drive_sources(args.source_folder_id)
        else:
            sources = load_drive_sources_for_slugs(
                slugs,
                report_type=args.report_type,
                version=args.version,
                limit=args.limit,
                source_scope=args.source_scope,
            )
    else:
        sources = load_local_sources(args.local_path)
    if args.source != "drive" or args.source_folder_id:
        sources = filter_sources(
            sources,
            slugs=slugs,
            report_type=args.report_type,
            version=args.version,
            limit=args.limit,
        )
    stats = run_pipeline(
        sources,
        persist=True,
        translate=not args.no_translate,
        dry_run=not args.apply,
    )
    stats["mode"] = "apply" if args.apply else "dry_run"
    stats["sample_slugs"] = slugs

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"[AUDIT] wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
