#!/usr/bin/env python3
"""Candidate pipeline for Drive analysis Markdown based report summaries.

This entrypoint is deliberately separate from ``watch_slides.py``. It produces
validated summary candidates and optional ``report_summary_jobs`` rows, but it
does not publish into ``project_reports``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent.parent

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from marketing_content_pipeline import (  # noqa: E402
    DB_TYPE_TO_SHORT,
    LANGUAGES,
    REPORT_TYPE_TO_DB,
    TARGET_LANGUAGES,
    CardCopy,
    DerivedContent,
    MarkdownSource,
    _download_drive_text,
    _get_drive_service,
    _limit_words,
    _list_drive_markdown_sources,
    _normalize_source_scope,
    _parse_markdown_name,
    _source_folder_ids_for_report_type,
    build_project_report_patch,
    derive_card_copy,
    derive_content,
    score_drive_source_for_project,
    validate_card_summary,
)


PIPELINE_NAME = "analysis-md-summary-candidate"
NODE_KEYS = (
    "analysis_md_source_scan",
    "summary_candidate_generation",
    "candidate_validation",
    "candidate_job_upsert",
)
SCHEMA_VERSION = "analysis_md_summary_candidate.v1"
PROMPT_VERSION = "analysis_md_summary_candidate.prompt.v1"
DEFAULT_MODEL = os.environ.get("BCE_ANALYSIS_MD_SUMMARY_MODEL", "configured-llm")
OUTPUT_DIR = PIPELINE_DIR / "output"
NON_BLOCKING_CARD_SUMMARY_REASONS = {
    "subject_missing_or_mismatch",
    "insight_missing",
    "no_insight_candidate",
}


@dataclass(frozen=True)
class AnalysisMdCandidate:
    source: MarkdownSource
    source_identity: str
    source_sha256: str
    revision_id: Optional[str]
    web_view_link: Optional[str]
    project: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class CandidateResult:
    candidate: AnalysisMdCandidate
    status: str
    validation_reasons: Tuple[str, ...]
    patch: Dict[str, Any]
    payload: Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_markdown(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip() + "\n"


def markdown_sha256(text: str) -> str:
    return hashlib.sha256(normalize_markdown(text).encode("utf-8")).hexdigest()


def source_identity(*, drive_file_id: Optional[str], revision_id: Optional[str], source_hash: str) -> str:
    if drive_file_id and revision_id:
        return f"drive:{drive_file_id}:{revision_id}"
    return f"sha256:{source_hash}"


def summary_job_idempotency_key(
    *,
    report_code: str,
    report_slug: str,
    locale: str,
    drive_file_id: Optional[str],
    revision_id: Optional[str],
    source_hash: str,
    prompt_version: str,
    schema_version: str,
) -> str:
    source_version = revision_id or source_hash
    source_file = drive_file_id or "local"
    return ":".join((
        report_code,
        report_slug,
        locale,
        source_file,
        source_version,
        prompt_version,
        schema_version,
    ))


def load_llm_payload_from_file(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def _llm_contract_body(source: MarkdownSource, *, project: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "promptVersion": PROMPT_VERSION,
        "reportType": source.report_type,
        "project": project or {"slug": source.slug},
        "languages": list(LANGUAGES),
        "markdown": source.text,
    }


def _openai_compatible_chat_body(
    contract_body: Dict[str, Any],
    *,
    endpoint: str,
) -> Dict[str, Any]:
    model = os.environ.get("BCE_ANALYSIS_MD_SUMMARY_MODEL", "").strip()
    if not model and "models.github.ai" in endpoint:
        model = "openai/gpt-4.1"
    if not model:
        model = DEFAULT_MODEL
    return {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You produce validated BCELab report-card summary JSON only. "
                    "Return a single JSON object with summary_by_lang and marketing_by_lang "
                    "for ko,en,fr,es,de,ja,zh; source_sentence_ids or exact source_sentences; "
                    "confidence; model; schema_version; prompt_version. Do not include markdown fences."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(contract_body, ensure_ascii=False),
            },
        ],
    }


def call_configured_llm(source: MarkdownSource, *, project: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    endpoint = os.environ.get("BCE_ANALYSIS_MD_LLM_ENDPOINT", "").strip()
    if not endpoint:
        return None
    contract_body = _llm_contract_body(source, project=project)
    is_chat_completions = endpoint.rstrip("/").endswith("/chat/completions")
    body = _openai_compatible_chat_body(contract_body, endpoint=endpoint) if is_chat_completions else contract_body
    token = (
        os.environ.get("BCE_ANALYSIS_MD_LLM_BEARER_TOKEN", "").strip()
        or os.environ.get("GITHUB_TOKEN", "").strip()
    )
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "bce-analysis-md-summary-candidate/1.0",
    }
    if "models.github.ai" in endpoint:
        headers["Accept"] = "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    if not is_chat_completions:
        return response_payload
    choices = response_payload.get("choices") or []
    content = (((choices[0] or {}).get("message") or {}).get("content") or "") if choices else ""
    payload = _extract_json_object(content)
    payload["model"] = payload.get("model") or body.get("model") or DEFAULT_MODEL
    return payload


def deterministic_payload(source: MarkdownSource, *, project: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    content = derive_content(source, translate=True, dry_run=False, project=project)
    card = derive_card_copy(source, project=project)
    return {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": "deterministic-marketing-content-pipeline",
        "summary_by_lang": content.summary_by_lang,
        "marketing_by_lang": content.marketing_by_lang,
        "source_sentence_ids": list(card.source_sentence_ids),
        "source_sentences": list(card.source_sentences),
        "confidence": card.confidence,
    }


def payload_to_content(payload: Dict[str, Any]) -> DerivedContent:
    summary_by_lang = dict(payload.get("summary_by_lang") or {})
    marketing_by_lang = dict(payload.get("marketing_by_lang") or {})
    return DerivedContent(
        title=str(payload.get("title") or ""),
        summary_ko=str(summary_by_lang.get("ko") or ""),
        marketing_ko=str(marketing_by_lang.get("ko") or ""),
        summary_by_lang={lang: str(summary_by_lang.get(lang) or "") for lang in LANGUAGES},
        marketing_by_lang={lang: str(marketing_by_lang.get(lang) or "") for lang in LANGUAGES},
    )


def validate_llm_payload(
    payload: Dict[str, Any],
    *,
    source: MarkdownSource,
    project: Optional[Dict[str, Any]],
) -> List[str]:
    reasons: List[str] = []
    if not isinstance(payload, dict):
        return ["schema_not_object"]

    for field in ("summary_by_lang", "marketing_by_lang"):
        value = payload.get(field)
        if not isinstance(value, dict):
            reasons.append(f"{field}_missing")
            continue
        missing = [lang for lang in LANGUAGES if not str(value.get(lang) or "").strip()]
        if missing:
            reasons.append(f"{field}_missing_languages:{','.join(missing)}")

    if not payload.get("source_sentence_ids") and not payload.get("source_sentences"):
        reasons.append("source_evidence_missing")

    source_text = normalize_markdown(source.text).lower()
    source_sentences = payload.get("source_sentences") or ()
    if not isinstance(source_sentences, list):
        reasons.append("source_sentences_not_array")
        source_sentences = ()
    for index, sentence in enumerate(source_sentences):
        text = normalize_markdown(str(sentence)).strip().lower()
        if len(text) >= 24 and text not in source_text:
            reasons.append(f"source_sentences.{index}.not_in_source")

    for field in ("summary_by_lang", "marketing_by_lang"):
        value = payload.get(field)
        if not isinstance(value, dict):
            continue
        for lang in LANGUAGES:
            text = str(value.get(lang) or "").strip()
            if not text:
                continue
            field_reasons = validate_card_summary(text, locale=lang, source=source, project=project)
            blocking = [reason for reason in field_reasons if reason not in NON_BLOCKING_CARD_SUMMARY_REASONS]
            reasons.extend(f"{field}.{lang}.{reason}" for reason in blocking)

    return sorted(set(reasons))


def build_candidate_patch(
    candidate: AnalysisMdCandidate,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    content = payload_to_content(payload)
    card = CardCopy(
        summary=content.summary_ko,
        source_sentences=tuple(str(item) for item in payload.get("source_sentences") or ()),
        source_sentence_ids=tuple(int(item) for item in payload.get("source_sentence_ids") or ()),
        confidence=float(payload.get("confidence") or 0.0),
        quality_reasons=tuple(),
    )
    patch = build_project_report_patch(candidate.source, content, project=candidate.project, card_copy=card)
    card_data = patch.get("card_data") if isinstance(patch.get("card_data"), dict) else {}
    source_md = card_data.get("source_md") if isinstance(card_data.get("source_md"), dict) else {}
    summary_quality = card_data.get("summary_quality") if isinstance(card_data.get("summary_quality"), dict) else {}
    patch["card_data"] = {
        **card_data,
        "source_md": {
            **source_md,
            "source_identity": candidate.source_identity,
            "source_sha256": candidate.source_sha256,
            "revision_id": candidate.revision_id,
            "web_view_link": candidate.web_view_link,
            "source_folder": f"analysis2/{candidate.source.report_type.upper()}",
        },
        "summary_quality": {
            **summary_quality,
            "contract": "card_summary_v2",
            "schema_version": payload.get("schema_version") or SCHEMA_VERSION,
            "prompt_version": payload.get("prompt_version") or PROMPT_VERSION,
            "model": payload.get("model") or DEFAULT_MODEL,
            "generated_at": utc_now(),
            "validation_status": "candidate_valid",
        },
    }
    return patch


def list_drive_candidates(
    *,
    report_type: str,
    slug: Optional[str],
    source_scope: str,
    service: Any,
) -> List[AnalysisMdCandidate]:
    folder_ids = _source_folder_ids_for_report_type(report_type, source_scope=source_scope, service=service)
    items: List[Dict[str, Any]] = []
    for folder_id in folder_ids:
        items.extend(_list_drive_markdown_sources_with_revision(service, folder_id))

    project = fetch_project(None, slug) if slug else None
    candidates: List[Tuple[int, AnalysisMdCandidate]] = []
    for item in items:
        name = str(item.get("name") or "")
        parsed = _parse_markdown_name(name)
        inferred_slug = slug or ""
        version = 1
        if parsed:
            parsed_slug, parsed_type, parsed_version, lang = parsed
            if parsed_type != report_type or lang != "ko":
                continue
            inferred_slug = parsed_slug
            version = parsed_version
        if slug and inferred_slug and inferred_slug != slug:
            score = score_drive_source_for_project(name, project or {"slug": slug})
            if score < 60:
                continue
        if slug and not inferred_slug:
            inferred_slug = slug

        text = _download_drive_text(service, item["id"])
        source_hash = markdown_sha256(text)
        revision_id = item.get("headRevisionId") or item.get("md5Checksum")
        source = MarkdownSource(
            slug=inferred_slug,
            report_type=report_type,
            db_report_type=REPORT_TYPE_TO_DB[report_type],
            version=version,
            lang="ko",
            name=name,
            text=text,
            drive_file_id=item["id"],
            modified_time=item.get("modifiedTime"),
        )
        candidate = AnalysisMdCandidate(
            source=source,
            source_identity=source_identity(
                drive_file_id=item["id"],
                revision_id=revision_id,
                source_hash=source_hash,
            ),
            source_sha256=source_hash,
            revision_id=revision_id,
            web_view_link=item.get("webViewLink"),
            project=project,
        )
        candidates.append((score_drive_source_for_project(name, project or {"slug": inferred_slug}), candidate))

    return [candidate for _score, candidate in sorted(candidates, key=lambda pair: pair[0], reverse=True)]


def _list_drive_markdown_sources_with_revision(service: Any, folder_id: str) -> List[Dict[str, Any]]:
    query = f"'{folder_id}' in parents and name contains '.md' and trashed = false"
    rows: List[Dict[str, Any]] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields=(
                "nextPageToken, "
                "files(id, name, mimeType, modifiedTime, size, webViewLink, headRevisionId, md5Checksum)"
            ),
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        rows.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return rows


def load_local_candidate(path: str, *, report_type: str, slug: str) -> AnalysisMdCandidate:
    text = Path(path).read_text(encoding="utf-8")
    parsed = _parse_markdown_name(Path(path).name)
    version = parsed[2] if parsed else 1
    source_hash = markdown_sha256(text)
    source = MarkdownSource(
        slug=slug,
        report_type=report_type,
        db_report_type=REPORT_TYPE_TO_DB[report_type],
        version=version,
        lang="ko",
        name=Path(path).name,
        text=text,
        local_path=path,
    )
    return AnalysisMdCandidate(
        source=source,
        source_identity=source_identity(drive_file_id=None, revision_id=None, source_hash=source_hash),
        source_sha256=source_hash,
        revision_id=None,
        web_view_link=None,
        project={"slug": slug, "name": slug.replace("-", " ").title(), "symbol": None},
    )


def fetch_project(sb: Any, slug: Optional[str]) -> Optional[Dict[str, Any]]:
    if not sb or not slug:
        return {"slug": slug} if slug else None
    res = sb.table("tracked_projects").select("id, slug, name, symbol, aliases").eq("slug", slug).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else {"slug": slug}


def existing_job(sb: Any, idempotency_key: str) -> Optional[Dict[str, Any]]:
    res = (
        sb.table("report_summary_jobs")
        .select("id, idempotency_key, source_identity, status, validation_status")
        .eq("idempotency_key", idempotency_key)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def upsert_job(sb: Any, result: CandidateResult, *, force: bool, dry_run: bool) -> Dict[str, Optional[str]]:
    if dry_run:
        return {"status": "dry_run", "job_id": None}
    idempotency_key = summary_job_idempotency_key(
        report_code=result.candidate.source.db_report_type,
        report_slug=result.candidate.source.slug,
        locale=result.candidate.source.lang or "ko",
        drive_file_id=result.candidate.source.drive_file_id,
        revision_id=result.candidate.revision_id,
        source_hash=result.candidate.source_sha256,
        prompt_version=result.payload.get("prompt_version") or PROMPT_VERSION,
        schema_version=result.payload.get("schema_version") or SCHEMA_VERSION,
    )
    existing = existing_job(sb, idempotency_key)
    if existing and not force:
        return {"status": "skipped_existing", "job_id": existing.get("id")}

    row = {
        "source_identity": result.candidate.source_identity,
        "source_drive_file_id": result.candidate.source.drive_file_id,
        "source_revision_id": result.candidate.revision_id,
        "source_sha256": result.candidate.source_sha256,
        "source_name": result.candidate.source.name,
        "source_web_view_link": result.candidate.web_view_link,
        "project_slug": result.candidate.source.slug,
        "report_type": result.candidate.source.db_report_type,
        "summarizer_model": result.payload.get("model") or DEFAULT_MODEL,
        "prompt_version": result.payload.get("prompt_version") or PROMPT_VERSION,
        "schema_version": result.payload.get("schema_version") or SCHEMA_VERSION,
        "generated_at": utc_now(),
        "validation_status": "valid" if result.status == "valid" else "invalid",
        "status": "candidate_ready" if result.status == "valid" else "validation_failed",
        "report_code": result.candidate.source.db_report_type,
        "locale": result.candidate.source.lang or "ko",
        "idempotency_key": idempotency_key,
        "authority_state": "validation_passed" if result.status == "valid" else "validation_failed",
        "authority_mode": "llm_candidate",
        "validator_result": {
            "validation_status": "valid" if result.status == "valid" else "invalid",
            "validation_errors": list(result.validation_reasons),
            "schema_version": result.payload.get("schema_version") or SCHEMA_VERSION,
            "prompt_version": result.payload.get("prompt_version") or PROMPT_VERSION,
        },
        "validation_errors": list(result.validation_reasons),
        "candidate_patch": result.patch,
        "llm_output": {
            "summary_by_lang": result.payload.get("summary_by_lang"),
            "marketing_by_lang": result.payload.get("marketing_by_lang"),
            "source_sentence_ids": result.payload.get("source_sentence_ids"),
            "confidence": result.payload.get("confidence"),
        },
    }
    if existing:
        sb.table("report_summary_jobs").update(row).eq("id", existing["id"]).execute()
        return {"status": "updated_existing", "job_id": existing.get("id")}
    response = sb.table("report_summary_jobs").insert(row).execute()
    rows = response.data or []
    job_id = rows[0].get("id") if rows else None
    return {"status": "inserted", "job_id": job_id}


def start_telemetry(sb: Any, *, report_type: str, dry_run: bool, slug: Optional[str]) -> Optional[str]:
    if not sb:
        return None
    try:
        response = sb.table("pipeline_runs").insert({
            "pipeline_name": PIPELINE_NAME,
            "status": "running",
            "report_type": REPORT_TYPE_TO_DB[report_type],
            "project_slug": slug,
            "started_at": utc_now(),
            "summary": f"{PIPELINE_NAME} {report_type}",
            "dry_run": dry_run,
            "slug_filter": slug,
            "metadata": {
                "reportType": report_type,
                "slug": slug,
                "source": "analysis_md_summary_candidate.py",
            },
        }).execute()
        rows = response.data or []
        return rows[0].get("id") if rows else None
    except Exception:
        return None


def complete_telemetry(
    sb: Any,
    run_id: Optional[str],
    *,
    results: Sequence[CandidateResult],
    artifact_path: Optional[str],
) -> None:
    if not sb or not run_id:
        return
    metrics = {
        "seen": len(results),
        "valid": sum(1 for item in results if item.status == "valid"),
        "invalid": sum(1 for item in results if item.status != "valid"),
    }
    status = "success" if metrics["invalid"] == 0 else "warning"
    now = utc_now()
    try:
        sb.table("pipeline_node_runs").insert([
            {
                "pipeline_run_id": run_id,
                "node_key": key,
                "node_name": key.replace("_", " ").title(),
                "report_type": results[0].candidate.source.db_report_type if results else "",
                "status": status,
                "started_at": now,
                "finished_at": now,
                "metrics": metrics,
                "artifact_path": artifact_path,
            }
            for key in NODE_KEYS
        ]).execute()
        sb.table("pipeline_events").insert({
            "pipeline_run_id": run_id,
            "event_type": "analysis_md_summary_candidate.completed",
            "severity": "info" if status == "success" else "warning",
            "message": f"{PIPELINE_NAME} completed",
            "details": {"metrics": metrics, "artifactPath": artifact_path},
            "artifact_path": artifact_path,
            "occurred_at": now,
        }).execute()
        sb.table("pipeline_runs").update({
            "status": status,
            "completed_at": now,
            "summary": f"{PIPELINE_NAME}: seen={metrics['seen']} valid={metrics['valid']} invalid={metrics['invalid']}",
            "metrics": metrics,
            "artifact_path": artifact_path,
        }).eq("id", run_id).execute()
    except Exception:
        return


def get_supabase_client() -> Any:
    try:
        from marketing_content_pipeline import _get_supabase_client
        return _get_supabase_client()
    except Exception:
        return None


def process_candidate(
    candidate: AnalysisMdCandidate,
    *,
    agent_payload: Optional[Dict[str, Any]],
) -> CandidateResult:
    payload = agent_payload or call_configured_llm(candidate.source, project=candidate.project)
    if payload is None:
        payload = deterministic_payload(candidate.source, project=candidate.project)
    payload = {
        **payload,
        "schema_version": payload.get("schema_version") or SCHEMA_VERSION,
        "prompt_version": payload.get("prompt_version") or PROMPT_VERSION,
        "model": payload.get("model") or DEFAULT_MODEL,
    }
    validation_reasons = validate_llm_payload(payload, source=candidate.source, project=candidate.project)
    patch = build_candidate_patch(candidate, payload) if not validation_reasons else {}
    return CandidateResult(
        candidate=candidate,
        status="valid" if not validation_reasons else "invalid",
        validation_reasons=tuple(validation_reasons),
        patch=patch,
        payload=payload,
    )


def write_artifact(
    results: Sequence[CandidateResult],
    *,
    report_type: str,
    slug: Optional[str],
    write_results: Sequence[Dict[str, Optional[str]]] = (),
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug_part = slug or "all"
    path = OUTPUT_DIR / f"analysis_md_summary_candidate_{report_type}_{slug_part}.json"
    write_results_by_index = list(write_results)
    path.write_text(json.dumps({
        "pipeline": PIPELINE_NAME,
        "generated_at": utc_now(),
        "results": [
            {
                "job_id": write_results_by_index[index].get("job_id") if index < len(write_results_by_index) else None,
                "upsert_result": write_results_by_index[index].get("status") if index < len(write_results_by_index) else None,
                "source_identity": item.candidate.source_identity,
                "source_name": item.candidate.source.name,
                "slug": item.candidate.source.slug,
                "report_type": item.candidate.source.report_type,
                "status": item.status,
                "validation_reasons": list(item.validation_reasons),
                "candidate_patch_keys": sorted(item.patch.keys()),
            }
            for index, item in enumerate(results)
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", required=True, choices=sorted(REPORT_TYPE_TO_DB.keys()))
    parser.add_argument("--slug", required=True)
    parser.add_argument("--drive-root-scope", default="active", choices=sorted({"active", "legacy", "all"}))
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--force", action="store_true", default=False)
    parser.add_argument("--source-path", help="Local Korean analysis Markdown for development dry-runs")
    parser.add_argument(
        "--agent-output-json",
        help="Paperclip local agent JSON output to validate and persist as a summary candidate",
    )
    parser.add_argument(
        "--llm-output-json",
        help="Deprecated alias for --agent-output-json, retained for older fixtures",
    )
    parser.add_argument(
        "--require-agent-output",
        action="store_true",
        help="Fail if no Paperclip agent JSON output is available",
    )
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Deprecated alias for --require-agent-output",
    )
    parser.add_argument("--limit", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    source_scope = _normalize_source_scope(args.drive_root_scope)
    sb = get_supabase_client()
    agent_output_json = args.agent_output_json or args.llm_output_json
    agent_payload = load_llm_payload_from_file(agent_output_json) if agent_output_json else None
    require_agent_output = args.require_agent_output or args.require_llm
    if require_agent_output and agent_payload is None and not os.environ.get("BCE_ANALYSIS_MD_LLM_ENDPOINT", "").strip():
        print("error=require_agent_output_or_llm_endpoint_missing", file=sys.stderr)
        return 2

    if args.source_path:
        candidates = [load_local_candidate(args.source_path, report_type=args.type, slug=args.slug)]
    else:
        service = _get_drive_service()
        candidates = list_drive_candidates(
            report_type=args.type,
            slug=args.slug,
            source_scope=source_scope,
            service=service,
        )
    candidates = candidates[: max(1, args.limit)]

    run_id = start_telemetry(sb, report_type=args.type, dry_run=args.dry_run, slug=args.slug)
    results: List[CandidateResult] = []
    write_results: List[Dict[str, Optional[str]]] = []
    for candidate in candidates:
        result = process_candidate(candidate, agent_payload=agent_payload)
        if sb:
            write_result = upsert_job(sb, result, force=args.force, dry_run=args.dry_run)
        else:
            write_result = {"status": "no_supabase", "job_id": None}
        print(
            f"{candidate.source.slug}/{candidate.source.report_type} "
            f"{result.status} identity={candidate.source_identity} write={write_result['status']}"
        )
        if write_result.get("job_id"):
            print(f"job_id={write_result['job_id']}")
        if result.validation_reasons:
            print("validation_reasons=" + ",".join(result.validation_reasons))
        results.append(result)
        write_results.append(write_result)

    artifact = write_artifact(results, report_type=args.type, slug=args.slug, write_results=write_results)
    complete_telemetry(sb, run_id, results=results, artifact_path=str(artifact))
    print(f"artifact={artifact}")
    return 0 if all(item.status == "valid" for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
