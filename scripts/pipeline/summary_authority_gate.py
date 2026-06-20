#!/usr/bin/env python3
"""Default-off Summary Authority Gate for report summary candidates.

The candidate pipeline writes ``report_summary_jobs`` only. This gate is the
single promotion path from a validated candidate job into active
``project_reports`` summary fields, and it only writes when ``--write`` is set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


PIPELINE_DIR = Path(__file__).resolve().parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from marketing_content_pipeline import WEBSITE_VISIBLE_REPORT_STATUSES, _get_supabase_client  # noqa: E402


PIPELINE_NAME = "analysis-md-summary-candidate"
PROMOTION_NODE_KEY = "summary_authority_gate"
ALLOWED_STATES = {
    "detected",
    "llm_candidate",
    "validation_failed",
    "validation_passed",
    "promotion_pending",
    "promoted",
    "rejected",
    "fallback_script",
}
TERMINAL_STATES = {"promoted", "rejected", "fallback_script"}


class GateError(RuntimeError):
    pass


@dataclass(frozen=True)
class GateDecision:
    action: str
    state: str
    wrote_project_report: bool
    reason: str
    project_report_id: Optional[str] = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_transition(current_state: str, next_state: str) -> None:
    if current_state not in ALLOWED_STATES:
        raise GateError(f"unknown current authority state: {current_state}")
    if next_state not in ALLOWED_STATES:
        raise GateError(f"unknown next authority state: {next_state}")
    allowed = {
        "detected": {"llm_candidate", "validation_failed", "validation_passed"},
        "llm_candidate": {"validation_failed", "validation_passed"},
        "validation_failed": {"rejected", "fallback_script"},
        "validation_passed": {"promotion_pending", "rejected", "fallback_script"},
        "promotion_pending": {"promoted", "rejected", "fallback_script"},
        "promoted": set(),
        "rejected": set(),
        "fallback_script": set(),
    }
    if next_state not in allowed[current_state]:
        raise GateError(f"invalid authority transition: {current_state} -> {next_state}")


def build_idempotency_key(job: Dict[str, Any]) -> str:
    prompt_version = str(job.get("prompt_version") or "")
    schema_version = str(job.get("schema_version") or "")
    source_hash = str(job.get("source_sha256") or job.get("source_identity") or "")
    source_version = str(job.get("source_revision_id") or source_hash)
    source_file = str(job.get("source_drive_file_id") or "local")
    return ":".join((
        str(job.get("report_code") or job.get("report_type") or ""),
        str(job.get("project_slug") or ""),
        str(job.get("locale") or "ko"),
        source_file,
        source_version,
        prompt_version,
        schema_version,
    ))


def find_job_by_idempotency_key(sb: Any, key: str) -> Optional[Dict[str, Any]]:
    rows = (
        sb.table("report_summary_jobs")
        .select("*")
        .eq("idempotency_key", key)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def fetch_job(sb: Any, job_id: str) -> Dict[str, Any]:
    rows = sb.table("report_summary_jobs").select("*").eq("id", job_id).limit(1).execute().data or []
    if not rows:
        raise GateError(f"report_summary_jobs row not found: {job_id}")
    return rows[0]


def update_job_state(
    sb: Any,
    job: Dict[str, Any],
    *,
    next_state: str,
    actor: str,
    decision: str,
    reason: str,
    dry_run: bool,
    project_report_id: Optional[str] = None,
) -> None:
    current_state = str(job.get("authority_state") or "detected")
    validate_transition(current_state, next_state)
    if dry_run:
        return
    now = utc_now()
    audit = dict(job.get("promotion_audit") or {})
    audit.update({
        "source_identity": job.get("source_identity"),
        "source_sha256": job.get("source_sha256"),
        "source_revision_id": job.get("source_revision_id"),
        "summarizer_model": job.get("summarizer_model"),
        "prompt_version": job.get("prompt_version"),
        "schema_version": job.get("schema_version"),
        "validator_result": job.get("validator_result") or {
            "validation_status": job.get("validation_status"),
            "validation_errors": job.get("validation_errors") or [],
        },
        "actor": actor,
        "decision": decision,
        "decision_reason": reason,
        "project_report_id": project_report_id,
        "decided_at": now,
    })
    patch: Dict[str, Any] = {
        "authority_state": next_state,
        "promotion_actor": actor,
        "promotion_decision": decision,
        "promotion_decision_reason": reason,
        "promotion_audit": audit,
        "updated_at": now,
    }
    if next_state == "promotion_pending":
        patch["promotion_started_at"] = now
    elif next_state == "promoted":
        patch["promoted_at"] = now
        patch["promoted_project_report_id"] = project_report_id
    elif next_state == "rejected":
        patch["rejected_at"] = now
    elif next_state == "fallback_script":
        patch["fallback_at"] = now
    sb.table("report_summary_jobs").update(patch).eq("id", job["id"]).execute()
    job.update(patch)


def emit_event(
    sb: Any,
    *,
    event_type: str,
    severity: str,
    message: str,
    job: Dict[str, Any],
    details: Dict[str, Any],
    dry_run: bool,
) -> None:
    if dry_run:
        return
    sb.table("pipeline_events").insert({
        "pipeline_run_id": None,
        "event_type": event_type,
        "severity": severity,
        "message": message,
        "details": {
            "pipeline": PIPELINE_NAME,
            "node": PROMOTION_NODE_KEY,
            "job_id": job.get("id"),
            "project_slug": job.get("project_slug"),
            "report_type": job.get("report_type"),
            "locale": job.get("locale") or "ko",
            **details,
        },
        "occurred_at": utc_now(),
    }).execute()


def _candidate_version(job: Dict[str, Any]) -> Optional[int]:
    patch = job.get("candidate_patch") if isinstance(job.get("candidate_patch"), dict) else {}
    card_data = patch.get("card_data") if isinstance(patch.get("card_data"), dict) else {}
    source_md = card_data.get("source_md") if isinstance(card_data.get("source_md"), dict) else {}
    try:
        return int(source_md["version"])
    except Exception:
        return None


def find_target_report(sb: Any, job: Dict[str, Any]) -> Dict[str, Any]:
    project_rows = (
        sb.table("tracked_projects")
        .select("id, slug")
        .eq("slug", job["project_slug"])
        .limit(1)
        .execute()
        .data
        or []
    )
    if not project_rows:
        raise GateError(f"tracked project not found: {job['project_slug']}")
    def target_query() -> Any:
        return (
            sb.table("project_reports")
            .select("id, project_id, report_type, version, language, status, card_data")
            .eq("project_id", project_rows[0]["id"])
            .eq("report_type", job["report_type"])
            .eq("language", job.get("locale") or "ko")
            .in_("status", list(WEBSITE_VISIBLE_REPORT_STATUSES))
        )

    version = _candidate_version(job)
    if version is not None:
        rows = target_query().eq("version", version).limit(1).execute().data or []
        if rows:
            return rows[0]
    rows = target_query().order("version", desc=True).limit(1).execute().data or []
    if not rows:
        raise GateError(
            f"website-visible project_reports target not found: "
            f"{job['project_slug']}/{job['report_type']}/{job.get('locale') or 'ko'}"
        )
    return rows[0]


def build_project_report_update(job: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    candidate_patch = job.get("candidate_patch")
    if not isinstance(candidate_patch, dict) or not candidate_patch:
        raise GateError("candidate_patch is empty; cannot promote")
    patch = dict(candidate_patch)
    existing_card = target.get("card_data") if isinstance(target.get("card_data"), dict) else {}
    candidate_card = patch.get("card_data") if isinstance(patch.get("card_data"), dict) else {}
    patch["card_data"] = {
        **existing_card,
        **candidate_card,
        "summary_authority": {
            "mode": "llm_active",
            "job_id": job.get("id"),
            "source_identity": job.get("source_identity"),
            "idempotency_key": job.get("idempotency_key") or build_idempotency_key(job),
            "promoted_at": utc_now(),
        },
    }
    patch["updated_at"] = utc_now()
    return patch


def promote_job_atomically(
    sb: Any,
    job: Dict[str, Any],
    *,
    actor: str,
    authority_mode: str,
) -> Dict[str, Any]:
    response = sb.rpc(
        "promote_report_summary_job",
        {
            "p_job_id": job["id"],
            "p_actor": actor,
            "p_authority_mode": authority_mode,
            "p_reason": "validated candidate promoted to project_reports",
        },
    ).execute()
    data = response.data
    if isinstance(data, list):
        if not data:
            raise GateError("promotion RPC returned no result")
        result = data[0]
    elif isinstance(data, dict):
        result = data
    else:
        raise GateError("promotion RPC returned an unexpected result")
    if result.get("authority_state"):
        job.update({
            "authority_state": result.get("authority_state"),
            "promoted_project_report_id": result.get("project_report_id"),
        })
    return result


def promote_job(
    sb: Any,
    job: Dict[str, Any],
    *,
    actor: str,
    authority_mode: str,
    dry_run: bool,
) -> GateDecision:
    state = str(job.get("authority_state") or "detected")
    if state in TERMINAL_STATES:
        return GateDecision("noop", state, False, f"job already terminal: {state}", job.get("promoted_project_report_id"))
    if authority_mode != "llm_active":
        update_job_state(
            sb,
            job,
            next_state="fallback_script",
            actor=actor,
            decision="fallback",
            reason=f"authority mode {authority_mode} keeps legacy active summary",
            dry_run=dry_run,
        )
        emit_event(
            sb,
            event_type="summary_authority_gate.fallback",
            severity="info",
            message="Summary Authority Gate kept legacy active summary",
            job=job,
            details={"authority_mode": authority_mode},
            dry_run=dry_run,
        )
        return GateDecision("fallback", "fallback_script", False, "legacy active summary retained")
    if state != "validation_passed" or job.get("validation_status") not in (None, "valid"):
        emit_event(
            sb,
            event_type="summary_authority_gate.promotion_blocked",
            severity="warning",
            message="Summary Authority Gate blocked invalid candidate promotion",
            job=job,
            details={"authority_state": state, "validation_status": job.get("validation_status")},
            dry_run=dry_run,
        )
        return GateDecision("blocked", state, False, "candidate is not validation_passed")
    if dry_run:
        target = find_target_report(sb, job)
        build_project_report_update(job, target)
        return GateDecision("promote", "promoted", False, "dry-run promotion would call atomic DB RPC", target["id"])
    try:
        result = promote_job_atomically(sb, job, actor=actor, authority_mode=authority_mode)
    except Exception as exc:
        message = str(exc)
        if "active promotion lock exists" in message:
            return GateDecision("blocked", state, False, "active promotion lock exists")
        raise
    return GateDecision(
        "promote",
        str(result.get("authority_state") or "promoted"),
        True,
        "validated candidate promoted",
        result.get("project_report_id"),
    )


def reject_job(sb: Any, job: Dict[str, Any], *, actor: str, reason: str, dry_run: bool) -> GateDecision:
    update_job_state(sb, job, next_state="rejected", actor=actor, decision="reject", reason=reason, dry_run=dry_run)
    emit_event(
        sb,
        event_type="summary_authority_gate.rejected",
        severity="info",
        message="Summary Authority Gate rejected candidate",
        job=job,
        details={"reason": reason},
        dry_run=dry_run,
    )
    return GateDecision("reject", "rejected", False, reason)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--action", choices=("promote", "reject"), default="promote")
    parser.add_argument("--authority-mode", choices=("legacy_script", "llm_candidate", "llm_active"), default=os.environ.get("BCE_SUMMARY_AUTHORITY_MODE", "legacy_script"))
    parser.add_argument("--actor", default=os.environ.get("PAPERCLIP_AGENT_ID", "local-operator"))
    parser.add_argument("--reason", default="")
    parser.add_argument("--write", action="store_true", help="Apply DB writes. Omit for default-off dry-run.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    sb = _get_supabase_client()
    if sb is None:
        raise GateError("Supabase warehouse client is not available")
    job = fetch_job(sb, args.job_id)
    dry_run = not args.write
    if args.action == "reject":
        decision = reject_job(
            sb,
            job,
            actor=args.actor,
            reason=args.reason or "candidate rejected by authority gate",
            dry_run=dry_run,
        )
    else:
        decision = promote_job(
            sb,
            job,
            actor=args.actor,
            authority_mode=args.authority_mode,
            dry_run=dry_run,
        )
    print(json.dumps({
        "job_id": args.job_id,
        "dry_run": dry_run,
        "decision": decision.__dict__,
    }, ensure_ascii=False, indent=2))
    return 0 if decision.action in {"promote", "fallback", "reject", "noop"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
