#!/usr/bin/env python3
"""Durable Google Drive source index for analysis PDF/Markdown summary input."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PIPELINE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PIPELINE_DIR / "output" / "drive_source_index"
TEXT_CACHE_DIR = OUTPUT_DIR / "extracted_text"

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from marketing_content_pipeline import (  # noqa: E402
    REPORT_TYPE_TO_DB,
    _download_drive_text,
    _get_drive_service,
    _normalize_source_scope,
    _parse_markdown_name,
    _source_folder_ids_for_report_type,
    score_drive_source_for_project,
)


DRIVE_MD_MIME = "text/markdown"
DRIVE_PLAIN_TEXT_MIME = "text/plain"
DRIVE_PDF_MIME = "application/pdf"
SUPPORTED_MIME_TYPES = {DRIVE_MD_MIME, DRIVE_PLAIN_TEXT_MIME, DRIVE_PDF_MIME}
PIPELINE_NAME = "drive-source-index"
DRIVE_SOURCE_INDEX_TABLES = (
    "drive_file_index",
    "drive_file_content_index",
    "analysis_source_map",
    "analysis_report_source_index",
    "drive_source_sync_state",
)


@dataclass(frozen=True)
class DriveIndexedFile:
    file_id: str
    folder_scope: str
    source_root: str
    report_type: str
    folder_id: str
    path: str
    name: str
    mime_type: str
    modified_time: Optional[str]
    revision_id: str
    size: Optional[int]
    trashed: bool
    web_view_link: Optional[str]


@dataclass(frozen=True)
class ContentIndex:
    file_id: str
    revision_id: str
    text_sha256: Optional[str]
    extraction_status: str
    page_count: Optional[int]
    extracted_text_path: Optional[str]
    error: Optional[str] = None
    cached: bool = False


@dataclass(frozen=True)
class SourceMapping:
    file_id: str
    revision_id: str
    report_type: str
    project_slug: Optional[str]
    subject: Optional[str]
    report_version: Optional[int]
    source_language: Optional[str]
    mapping_confidence: int
    mapping_status: str
    mapping_evidence: Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").replace("\r\n", "\n").replace("\r", "\n").strip().encode("utf-8")).hexdigest()


def _source_root_name(folder_scope: str) -> str:
    if folder_scope == "legacy":
        return os.environ.get("BCE_LEGACY_ANALYSIS_ROOT_FOLDER_NAME", "analysis")
    return os.environ.get("BCE_ACTIVE_ANALYSIS_ROOT_FOLDER_NAME", "analysis2")


def _file_revision_id(row: Dict[str, Any]) -> str:
    return str(row.get("headRevisionId") or row.get("md5Checksum") or row.get("modifiedTime") or row.get("id"))


def list_drive_source_files(
    service: Any,
    *,
    report_type: str,
    drive_root_scope: str,
    modified_after: Optional[str] = None,
    checkpoint_resolver: Optional[Any] = None,
    full_rescan: bool = False,
) -> List[DriveIndexedFile]:
    rows: List[DriveIndexedFile] = []
    for folder_scope, source_root, folder_id in _folder_keys_for_scope(report_type, drive_root_scope, service):
        checkpoint = None
        if not full_rescan:
            checkpoint = modified_after
            if checkpoint is None and checkpoint_resolver:
                checkpoint = checkpoint_resolver(source_root, folder_scope, report_type, folder_id)
        for item in _list_source_files_in_folder(service, folder_id, modified_after=checkpoint):
            mime_type = str(item.get("mimeType") or "")
            if mime_type not in SUPPORTED_MIME_TYPES and not str(item.get("name") or "").lower().endswith((".md", ".pdf")):
                continue
            rows.append(DriveIndexedFile(
                file_id=str(item["id"]),
                folder_scope=folder_scope,
                source_root=source_root,
                report_type=report_type,
                folder_id=folder_id,
                path=f"{source_root}/{report_type.upper()}/{item.get('name') or ''}",
                name=str(item.get("name") or ""),
                mime_type=mime_type or _mime_from_name(str(item.get("name") or "")),
                modified_time=item.get("modifiedTime"),
                revision_id=_file_revision_id(item),
                size=int(item["size"]) if str(item.get("size") or "").isdigit() else None,
                trashed=bool(item.get("trashed") or False),
                web_view_link=item.get("webViewLink"),
            ))
    return rows


def _folder_keys_for_scope(report_type: str, drive_root_scope: str, service: Any) -> Iterable[Tuple[str, str, str]]:
    for folder_scope, folder_ids in _folder_sets_for_scope(report_type, drive_root_scope, service):
        source_root = _source_root_name(folder_scope)
        for folder_id in folder_ids:
            yield folder_scope, source_root, folder_id


def _folder_sets_for_scope(report_type: str, drive_root_scope: str, service: Any) -> Iterable[Tuple[str, List[str]]]:
    normalized = _normalize_source_scope(drive_root_scope)
    scopes = ("active", "legacy") if normalized == "all" else (normalized,)
    for scope in scopes:
        yield scope, _source_folder_ids_for_report_type(report_type, source_scope=scope, service=service)


def _mime_from_name(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".pdf"):
        return DRIVE_PDF_MIME
    if lower.endswith(".md"):
        return DRIVE_MD_MIME
    return "application/octet-stream"


def _list_source_files_in_folder(service: Any, folder_id: str, *, modified_after: Optional[str]) -> List[Dict[str, Any]]:
    filters = [
        f"'{folder_id}' in parents",
        "trashed = false",
        "(name contains '.md' or name contains '.pdf')",
    ]
    if modified_after:
        filters.append(f"modifiedTime > '{modified_after}'")
    query = " and ".join(filters)
    rows: List[Dict[str, Any]] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields=(
                "nextPageToken, files("
                "id, name, mimeType, modifiedTime, size, webViewLink, headRevisionId, md5Checksum, trashed)"
            ),
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        rows.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            return rows


def extract_content(service: Any, indexed: DriveIndexedFile, *, cache_dir: Path = TEXT_CACHE_DIR) -> ContentIndex:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{indexed.file_id}_{indexed.revision_id}.txt"
    if cache_path.exists():
        text = cache_path.read_text(encoding="utf-8")
        return ContentIndex(indexed.file_id, indexed.revision_id, sha256_text(text), "extracted", None, str(cache_path))
    try:
        if indexed.mime_type == DRIVE_PDF_MIME or indexed.name.lower().endswith(".pdf"):
            text, page_count = _extract_drive_pdf_text(service, indexed.file_id)
        else:
            text, page_count = _download_drive_text(service, indexed.file_id), None
        cache_path.write_text(text, encoding="utf-8")
        return ContentIndex(indexed.file_id, indexed.revision_id, sha256_text(text), "extracted", page_count, str(cache_path))
    except Exception as exc:
        return ContentIndex(indexed.file_id, indexed.revision_id, None, "failed", None, None, str(exc))


def _extract_drive_pdf_text(service: Any, file_id: str) -> Tuple[str, int]:
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    out = io.BytesIO()
    downloader = MediaIoBaseDownload(out, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    try:
        import fitz
    except Exception as exc:
        raise RuntimeError("pymupdf_unavailable") from exc
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp:
        temp.write(out.getvalue())
        temp.flush()
        doc = fitz.open(temp.name)
        try:
            parts = [doc.load_page(i).get_text() or "" for i in range(doc.page_count)]
            return "\n".join(parts), int(doc.page_count)
        finally:
            doc.close()


def map_source_file(indexed: DriveIndexedFile, projects: Sequence[Dict[str, Any]]) -> SourceMapping:
    parsed = _parse_markdown_name(indexed.name)
    evidence: Dict[str, Any] = {"name": indexed.name, "path": indexed.path, "candidates": []}
    if parsed:
        slug, parsed_type, version, lang = parsed
        evidence["parsed"] = {"slug": slug, "report_type": parsed_type, "version": version, "lang": lang}
        if parsed_type != indexed.report_type:
            return SourceMapping(
                indexed.file_id,
                indexed.revision_id,
                indexed.report_type,
                slug,
                slug,
                version,
                lang,
                0,
                "skipped",
                evidence,
            )
        return SourceMapping(
            indexed.file_id,
            indexed.revision_id,
            indexed.report_type,
            slug,
            slug,
            version,
            lang,
            100,
            "safe",
            evidence,
        )

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for project in projects:
        score = score_drive_source_for_project(indexed.name, project)
        if score >= 60:
            scored.append((score, project))
    scored.sort(key=lambda item: item[0], reverse=True)
    evidence["candidates"] = [
        {"slug": item.get("slug"), "name": item.get("name"), "symbol": item.get("symbol"), "score": score}
        for score, item in scored[:5]
    ]
    if not scored:
        return SourceMapping(indexed.file_id, indexed.revision_id, indexed.report_type, None, None, None, None, 0, "unmatched", evidence)
    top_score, top_project = scored[0]
    if len(scored) > 1 and scored[1][0] >= top_score - 10:
        return SourceMapping(
            indexed.file_id,
            indexed.revision_id,
            indexed.report_type,
            str(top_project.get("slug") or ""),
            str(top_project.get("name") or top_project.get("slug") or ""),
            None,
            None,
            top_score,
            "ambiguous",
            evidence,
        )
    return SourceMapping(
        indexed.file_id,
        indexed.revision_id,
        indexed.report_type,
        str(top_project.get("slug") or ""),
        str(top_project.get("name") or top_project.get("slug") or ""),
        None,
        None,
        top_score,
        "safe",
        evidence,
    )


def fetch_projects(sb: Any, slug: Optional[str] = None) -> List[Dict[str, Any]]:
    if not sb:
        return [{"slug": slug}] if slug else []
    query = sb.table("tracked_projects").select("id, slug, name, symbol, aliases")
    if slug:
        query = query.eq("slug", slug)
    return query.execute().data or []


def select_index_candidates(
    sb: Any,
    *,
    report_type: str,
    slug: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    try:
        rows = _select_report_source_index_candidates(sb, report_type=report_type, slug=slug, limit=limit)
    except Exception as exc:
        if not _is_missing_drive_index_schema_error(exc):
            raise
        return _select_index_candidates_legacy(sb, report_type=report_type, slug=slug, limit=limit)
    if rows:
        return rows
    return _select_index_candidates_legacy(sb, report_type=report_type, slug=slug, limit=limit)


def _select_report_source_index_candidates(
    sb: Any,
    *,
    report_type: str,
    slug: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    query = (
        sb.table("analysis_report_source_index")
        .select("*")
        .eq("report_type", report_type)
        .eq("mapping_status", "safe")
        .eq("extraction_status", "extracted")
    )
    if slug:
        query = query.eq("project_slug", slug)
    rows = query.execute().data or []
    selected: List[Dict[str, Any]] = []
    for row in rows:
        file_id = str(row.get("file_id") or "")
        revision_id = str(row.get("revision_id") or "")
        if not file_id or not revision_id:
            continue
        if _source_has_summary_job(sb, file_id=file_id, revision_id=revision_id):
            continue
        selected.append(_candidate_row_from_report_source(row))
    selected.sort(
        key=lambda row: (
            row["mapping"].get("report_version") or 0,
            str(row["file"].get("modified_time") or ""),
        ),
        reverse=True,
    )
    return selected[: max(1, limit)]


def _candidate_row_from_report_source(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "file": {
            "file_id": row.get("file_id"),
            "revision_id": row.get("revision_id"),
            "folder_scope": row.get("folder_scope"),
            "source_root": row.get("source_root"),
            "report_type": row.get("report_type"),
            "folder_id": row.get("folder_id"),
            "path": row.get("path"),
            "name": row.get("name"),
            "mime_type": row.get("mime_type"),
            "modified_time": row.get("modified_time"),
            "size": row.get("size"),
            "metadata": {"webViewLink": row.get("web_view_link")} if row.get("web_view_link") else {},
        },
        "content": {
            "file_id": row.get("file_id"),
            "revision_id": row.get("revision_id"),
            "text_sha256": row.get("text_sha256"),
            "extraction_status": row.get("extraction_status"),
            "page_count": row.get("page_count"),
            "extracted_text_path": row.get("extracted_text_path"),
        },
        "mapping": {
            "file_id": row.get("file_id"),
            "revision_id": row.get("revision_id"),
            "report_type": row.get("report_type"),
            "project_slug": row.get("project_slug"),
            "subject": row.get("subject"),
            "report_version": row.get("report_version"),
            "source_language": row.get("source_language"),
            "mapping_status": row.get("mapping_status"),
            "mapping_confidence": row.get("mapping_confidence"),
            "mapping_evidence": row.get("mapping_evidence") or {},
        },
    }


def _select_index_candidates_legacy(
    sb: Any,
    *,
    report_type: str,
    slug: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    query = (
        sb.table("analysis_source_map")
        .select("file_id, revision_id, report_type, project_slug, subject, mapping_status, mapping_confidence, mapping_evidence")
        .eq("report_type", report_type)
        .eq("mapping_status", "safe")
    )
    if slug:
        query = query.eq("project_slug", slug)
    maps = query.execute().data or []
    selected: List[Dict[str, Any]] = []
    for source_map in maps:
        file_id = source_map.get("file_id")
        revision_id = source_map.get("revision_id")
        files = sb.table("drive_file_index").select("*").eq("file_id", file_id).limit(1).execute().data or []
        contents = (
            sb.table("drive_file_content_index")
            .select("*")
            .eq("file_id", file_id)
            .eq("revision_id", revision_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not files or not contents or contents[0].get("extraction_status") != "extracted":
            continue
        if _source_has_summary_job(sb, file_id=str(file_id), revision_id=str(revision_id)):
            continue
        selected.append({"file": files[0], "content": contents[0], "mapping": source_map})
    selected.sort(key=lambda row: str(row["file"].get("modified_time") or ""), reverse=True)
    return selected[: max(1, limit)]


def _source_has_summary_job(sb: Any, *, file_id: str, revision_id: str) -> bool:
    source_identity = f"drive:{file_id}:{revision_id}"
    rows = (
        sb.table("report_summary_jobs")
        .select("id")
        .eq("source_identity", source_identity)
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def sync_index(
    sb: Any,
    service: Any,
    *,
    report_type: str,
    drive_root_scope: str,
    slug: Optional[str],
    dry_run: bool,
    modified_after: Optional[str] = None,
    full_rescan: bool = False,
) -> Dict[str, Any]:
    projects = fetch_projects(sb, slug)
    folder_keys = list(_folder_keys_for_scope(report_type, drive_root_scope, service))
    checkpoint_resolver = None
    if sb and not modified_after and not full_rescan:
        checkpoint_resolver = lambda source_root, folder_scope, report_type, folder_id: _sync_state_checkpoint(
            sb,
            source_root=source_root,
            folder_scope=folder_scope,
            report_type=report_type,
            folder_id=folder_id,
        )
    indexed_files = list_drive_source_files(
        service,
        report_type=report_type,
        drive_root_scope=drive_root_scope,
        modified_after=modified_after,
        checkpoint_resolver=checkpoint_resolver,
        full_rescan=full_rescan,
    )
    metrics = {
        "seen": len(indexed_files),
        "changed": 0,
        "unchanged": 0,
        "metadata_upserts": 0,
        "content_extracted": 0,
        "content_cached": 0,
        "content_failed": 0,
        "safe": 0,
        "ambiguous": 0,
        "unmatched": 0,
        "skipped": 0,
        "dry_run": dry_run,
        "full_rescan": full_rescan,
        "modified_after": modified_after,
        "sync_state_used": bool(checkpoint_resolver),
        "sync_state_upserts": 0,
        "report_source_upserts": 0,
        "no_op": False,
    }
    seen_by_folder: Dict[Tuple[str, str, str, str], int] = {}
    changed_by_folder: Dict[Tuple[str, str, str, str], int] = {}
    for indexed in indexed_files:
        folder_key = (indexed.source_root, indexed.folder_scope, indexed.report_type, indexed.folder_id)
        seen_by_folder[folder_key] = seen_by_folder.get(folder_key, 0) + 1
        existing_file = _existing_file_row(sb, indexed.file_id) if sb else None
        existing_content = _existing_content_row(sb, indexed.file_id, indexed.revision_id) if sb else None
        existing_mapping = _existing_mapping_row(sb, indexed.file_id, indexed.revision_id, report_type) if sb else None
        existing_report_source = _existing_report_source_row(sb, indexed.file_id, indexed.revision_id, report_type) if sb else None
        if _is_unchanged(indexed, existing_file, existing_content, existing_mapping, existing_report_source):
            metrics["unchanged"] += 1
            metrics["content_cached"] += 1
            continue

        metrics["changed"] += 1
        changed_by_folder[folder_key] = changed_by_folder.get(folder_key, 0) + 1
        content = _content_from_existing(indexed, existing_content) or extract_content(service, indexed)
        mapping = map_source_file(indexed, projects)
        metrics[mapping.mapping_status] += 1
        if content.cached:
            metrics["content_cached"] += 1
        else:
            metrics["content_extracted" if content.extraction_status == "extracted" else "content_failed"] += 1
        if dry_run or not sb:
            continue
        sb.table("drive_file_index").upsert(_file_row(indexed), on_conflict="file_id").execute()
        sb.table("drive_file_content_index").upsert(_content_row(content), on_conflict="file_id,revision_id").execute()
        sb.table("analysis_source_map").upsert(_mapping_row(mapping), on_conflict="file_id,revision_id,report_type").execute()
        sb.table("analysis_report_source_index").upsert(
            _report_source_row(indexed, content, mapping),
            on_conflict="file_id,revision_id,report_type",
        ).execute()
        metrics["metadata_upserts"] += 1
        metrics["report_source_upserts"] += 1
    if not dry_run and sb:
        for folder_scope, source_root, folder_id in folder_keys:
            key = (source_root, folder_scope, report_type, folder_id)
            _upsert_sync_state(
                sb,
                source_root=source_root,
                folder_scope=folder_scope,
                report_type=report_type,
                folder_id=folder_id,
                seen_count=seen_by_folder.get(key, 0),
                changed_count=changed_by_folder.get(key, 0),
            )
            metrics["sync_state_upserts"] += 1
    metrics["no_op"] = metrics["changed"] == 0
    return metrics


def _sync_state_checkpoint(
    sb: Any,
    *,
    source_root: str,
    folder_scope: str,
    report_type: str,
    folder_id: str,
) -> Optional[str]:
    try:
        rows = (
            sb.table("drive_source_sync_state")
            .select("last_success_at")
            .eq("source_root", source_root)
            .eq("folder_scope", folder_scope)
            .eq("report_type", report_type)
            .eq("folder_id", folder_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        _raise_missing_drive_index_schema(exc)
        raise
    if not rows:
        return None
    return rows[0].get("last_success_at")


def _upsert_sync_state(
    sb: Any,
    *,
    source_root: str,
    folder_scope: str,
    report_type: str,
    folder_id: str,
    seen_count: int,
    changed_count: int,
) -> None:
    now = utc_now()
    sb.table("drive_source_sync_state").upsert(
        {
            "source_root": source_root,
            "folder_scope": folder_scope,
            "report_type": report_type,
            "folder_id": folder_id,
            "last_sync_at": now,
            "last_success_at": now,
            "last_seen_count": seen_count,
            "last_changed_count": changed_count,
            "updated_at": now,
        },
        on_conflict="source_root,folder_scope,report_type,folder_id",
    ).execute()


def _existing_file_row(sb: Any, file_id: str) -> Optional[Dict[str, Any]]:
    try:
        rows = sb.table("drive_file_index").select("*").eq("file_id", file_id).limit(1).execute().data or []
    except Exception as exc:
        _raise_missing_drive_index_schema(exc)
        raise
    return rows[0] if rows else None


def _existing_content_row(sb: Any, file_id: str, revision_id: str) -> Optional[Dict[str, Any]]:
    try:
        rows = (
            sb.table("drive_file_content_index")
            .select("*")
            .eq("file_id", file_id)
            .eq("revision_id", revision_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        _raise_missing_drive_index_schema(exc)
        raise
    return rows[0] if rows else None


def _existing_mapping_row(sb: Any, file_id: str, revision_id: str, report_type: str) -> Optional[Dict[str, Any]]:
    try:
        rows = (
            sb.table("analysis_source_map")
            .select("*")
            .eq("file_id", file_id)
            .eq("revision_id", revision_id)
            .eq("report_type", report_type)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        _raise_missing_drive_index_schema(exc)
        raise
    return rows[0] if rows else None


def _existing_report_source_row(sb: Any, file_id: str, revision_id: str, report_type: str) -> Optional[Dict[str, Any]]:
    try:
        rows = (
            sb.table("analysis_report_source_index")
            .select("file_id, revision_id, report_type")
            .eq("file_id", file_id)
            .eq("revision_id", revision_id)
            .eq("report_type", report_type)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        _raise_missing_drive_index_schema(exc)
        raise
    return rows[0] if rows else None


def _raise_missing_drive_index_schema(exc: Exception) -> None:
    if not _is_missing_drive_index_schema_error(exc):
        return
    raise RuntimeError(
        "Drive Source Index tables are not available in Supabase. "
        "Apply supabase/migrations/20260621043000_add_drive_source_index.sql "
        "and supabase/migrations/20260623010000_add_analysis_report_source_index.sql, "
        "then refresh the PostgREST schema cache before running persisted or "
        "checkpoint-backed drive_source_index.py syncs."
    ) from exc


def _is_missing_drive_index_schema_error(exc: Exception) -> bool:
    message = str(exc)
    return "PGRST205" in message or any(table in message for table in DRIVE_SOURCE_INDEX_TABLES)


def _is_unchanged(
    indexed: DriveIndexedFile,
    existing_file: Optional[Dict[str, Any]],
    existing_content: Optional[Dict[str, Any]],
    existing_mapping: Optional[Dict[str, Any]],
    existing_report_source: Optional[Dict[str, Any]],
) -> bool:
    if not existing_file or not existing_content or not existing_mapping or not existing_report_source:
        return False
    return (
        str(existing_file.get("revision_id") or "") == indexed.revision_id
        and str(existing_content.get("extraction_status") or "") == "extracted"
        and str(existing_content.get("revision_id") or "") == indexed.revision_id
    )


def _content_from_existing(indexed: DriveIndexedFile, row: Optional[Dict[str, Any]]) -> Optional[ContentIndex]:
    if not row or row.get("extraction_status") != "extracted":
        return None
    return ContentIndex(
        indexed.file_id,
        indexed.revision_id,
        row.get("text_sha256"),
        "extracted",
        row.get("page_count"),
        row.get("extracted_text_path"),
        row.get("error"),
        True,
    )


def _file_row(indexed: DriveIndexedFile) -> Dict[str, Any]:
    now = utc_now()
    return {
        "file_id": indexed.file_id,
        "folder_scope": indexed.folder_scope,
        "source_root": indexed.source_root,
        "report_type": indexed.report_type,
        "folder_id": indexed.folder_id,
        "path": indexed.path,
        "name": indexed.name,
        "mime_type": indexed.mime_type,
        "modified_time": indexed.modified_time,
        "revision_id": indexed.revision_id,
        "size": indexed.size,
        "trashed": indexed.trashed,
        "last_seen_at": now,
        "updated_at": now,
        "metadata": {"webViewLink": indexed.web_view_link},
    }


def _content_row(content: ContentIndex) -> Dict[str, Any]:
    now = utc_now()
    return {
        "file_id": content.file_id,
        "revision_id": content.revision_id,
        "text_sha256": content.text_sha256,
        "extraction_status": content.extraction_status,
        "page_count": content.page_count,
        "extracted_text_path": content.extracted_text_path,
        "error": content.error,
        "extracted_at": now if content.extraction_status == "extracted" else None,
        "updated_at": now,
    }


def _mapping_row(mapping: SourceMapping) -> Dict[str, Any]:
    return {
        "file_id": mapping.file_id,
        "revision_id": mapping.revision_id,
        "report_type": mapping.report_type,
        "project_slug": mapping.project_slug,
        "subject": mapping.subject,
        "report_version": mapping.report_version,
        "source_language": mapping.source_language,
        "mapping_confidence": mapping.mapping_confidence,
        "mapping_status": mapping.mapping_status,
        "mapping_evidence": mapping.mapping_evidence,
        "mapped_at": utc_now(),
        "updated_at": utc_now(),
    }


def _report_source_row(indexed: DriveIndexedFile, content: ContentIndex, mapping: SourceMapping) -> Dict[str, Any]:
    now = utc_now()
    return {
        "file_id": indexed.file_id,
        "revision_id": indexed.revision_id,
        "report_type": indexed.report_type,
        "project_slug": mapping.project_slug,
        "subject": mapping.subject,
        "report_version": mapping.report_version,
        "source_language": mapping.source_language,
        "source_identity": f"drive:{indexed.file_id}:{indexed.revision_id}",
        "folder_scope": indexed.folder_scope,
        "source_root": indexed.source_root,
        "folder_id": indexed.folder_id,
        "path": indexed.path,
        "name": indexed.name,
        "mime_type": indexed.mime_type,
        "modified_time": indexed.modified_time,
        "size": indexed.size,
        "web_view_link": indexed.web_view_link,
        "text_sha256": content.text_sha256,
        "extraction_status": content.extraction_status,
        "page_count": content.page_count,
        "extracted_text_path": content.extracted_text_path,
        "mapping_confidence": mapping.mapping_confidence,
        "mapping_status": mapping.mapping_status,
        "mapping_evidence": mapping.mapping_evidence,
        "last_seen_at": now,
        "updated_at": now,
    }


def get_supabase_client() -> Any:
    try:
        from marketing_content_pipeline import _get_supabase_client
        return _get_supabase_client()
    except Exception:
        return None


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", required=True, choices=sorted(REPORT_TYPE_TO_DB.keys()))
    parser.add_argument("--slug")
    parser.add_argument("--drive-root-scope", default="active", choices=sorted({"active", "legacy", "all"}))
    parser.add_argument("--modified-after")
    parser.add_argument("--full-rescan", action="store_true", help="Ignore drive_source_sync_state and scan the selected folders without a checkpoint.")
    parser.add_argument("--bootstrap-full-rescan", action="store_true", help="Alias for --full-rescan for first-run/operator recovery.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    sb = get_supabase_client()
    metrics = sync_index(
        sb,
        _get_drive_service(),
        report_type=args.type,
        drive_root_scope=args.drive_root_scope,
        slug=args.slug,
        dry_run=args.dry_run,
        modified_after=args.modified_after,
        full_rescan=args.full_rescan or args.bootstrap_full_rescan,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = OUTPUT_DIR / f"drive_source_index_{args.type}_{args.slug or 'all'}.json"
    artifact.write_text(json.dumps({"generated_at": utc_now(), "metrics": metrics}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"metrics={json.dumps(metrics, ensure_ascii=False, sort_keys=True)}")
    print(f"artifact={artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
