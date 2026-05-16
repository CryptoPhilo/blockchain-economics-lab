#!/usr/bin/env python3
"""Default-off bridge from sudden-mover scan output to FOR card anchors."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

try:
    from scripts.pipeline.candidates.sudden_movers_scanner import (
        DEFAULT_LIMIT,
        run_candidate_scan,
    )
except ModuleNotFoundError:
    from candidates.sudden_movers_scanner import DEFAULT_LIMIT, run_candidate_scan


ENABLE_ENV = "ENABLE_SUDDEN_MOVERS_CARD_ANCHOR"
STATE_PATH_ENV = "SUDDEN_MOVERS_CARD_ANCHOR_STATE"
OUTPUT_PATH_ENV = "SUDDEN_MOVERS_CARD_ANCHOR_OUTPUT"
DEFAULT_STATE_PATH = Path("scripts/pipeline/output/sudden_movers_card_anchor_state.json")
DEFAULT_OUTPUT_PATH = Path("scripts/pipeline/output/sudden_movers_card_anchors.jsonl")
DEFAULT_OBSERVATION_WINDOW = "24h"
DEFAULT_HANDOFF_LANG = "en"
DEFAULT_HANDOFF_VERSION = 1
PIPELINE_NAME = "forensic-rapid-change-scan"
PAPERCLIP_PIPELINE_NAME = "Forensic Rapid Change Scan"
REPORT_TYPE = "for"
PIPELINE_PROJECT_SLUG = "forensic-rapid-change-scan"
TELEMETRY_NODES: List[Tuple[str, str]] = [
    ("candidate_scan", "Sudden mover candidate scan"),
    ("card_anchor_bridge", "Default-off FOR card anchor bridge"),
    ("scan_result_artifact", "Rapid-change scan evidence artifact"),
]


def is_enabled(env: Optional[Dict[str, str]] = None) -> bool:
    value = (env or os.environ).get(ENABLE_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _supabase_url() -> Optional[str]:
    return os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")


def _supabase_service_key() -> Optional[str]:
    return os.environ.get("SUPABASE_SERVICE_KEY")


def _supabase_configured() -> bool:
    return bool(_supabase_url() and _supabase_service_key())


def _supabase_client():
    url = _supabase_url()
    key = _supabase_service_key()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
    from supabase import create_client

    return create_client(url, key)


def _scan_artifact_path() -> Optional[str]:
    configured = os.environ.get("FORENSIC_RAPID_CHANGE_SCAN_ARTIFACT_PATH")
    if configured:
        return configured
    github_run_id = os.environ.get("GITHUB_RUN_ID")
    if github_run_id:
        return f"scripts/pipeline/output/sudden_movers_card_anchor_{github_run_id}.json"
    return None


def _telemetry_status(result: Dict[str, Any]) -> str:
    if result.get("status") == "failed":
        return "processing_error"
    if result.get("dry_run", True):
        return "dry_run"
    return "done"


def build_rapid_change_scan_metrics(result: Dict[str, Any]) -> Dict[str, int]:
    scanner = result.get("scanner") if isinstance(result.get("scanner"), dict) else {}
    anchors = result.get("anchors") if isinstance(result.get("anchors"), list) else []
    duplicates = result.get("duplicates") if isinstance(result.get("duplicates"), list) else []
    handoff_contracts = (
        result.get("handoff_contracts") if isinstance(result.get("handoff_contracts"), list) else []
    )
    status = result.get("status")
    candidate_count = int(scanner.get("candidate_count") or len(anchors) + len(duplicates))

    return {
        "scan_attempted": 1 if status != "disabled" else 0,
        "successful_scans": 1 if status == "ok" else 0,
        "failed_scans": 1 if status == "failed" else 0,
        "skipped_scans": 1 if status == "disabled" else 0,
        "candidate_count": candidate_count,
        "fresh_candidates": len(anchors),
        "deduped_candidates": len(duplicates),
        "registered_count": len(handoff_contracts) if result.get("enabled") and not result.get("dry_run") else 0,
        "email_required_count": 0,
        "email_sent_count": 0,
        "email_failed_count": 0,
    }


def build_rapid_change_scan_metadata(
    result: Dict[str, Any],
    *,
    artifact_path: Optional[str] = None,
) -> Dict[str, Any]:
    scanner = result.get("scanner") if isinstance(result.get("scanner"), dict) else {}
    return {
        "pipelineKey": PIPELINE_NAME,
        "reportType": REPORT_TYPE,
        "enabled": result.get("enabled"),
        "dryRun": result.get("dry_run"),
        "thresholdPctPoints": scanner.get("threshold_pct_points"),
        "observedAt": scanner.get("observed_at"),
        "warnings": scanner.get("warnings", []),
        "statePath": result.get("state_path"),
        "outputPath": result.get("output_path"),
        "artifactPath": artifact_path,
        "githubRunId": os.environ.get("GITHUB_RUN_ID"),
        "githubRunNumber": os.environ.get("GITHUB_RUN_NUMBER"),
        "githubWorkflow": os.environ.get("GITHUB_WORKFLOW"),
        "githubSha": os.environ.get("GITHUB_SHA"),
        "emailNotificationResult": {
            "required": False,
            "status": "not_applicable",
            "detail": "Current rapid-change runtime emits candidate/card-anchor evidence only; legacy email registration is not invoked.",
        },
        "source": "scripts/pipeline/sudden_movers_card_anchor.py",
    }


class RapidChangeScanTelemetry:
    def __init__(self) -> None:
        self.enabled = _supabase_configured()
        self._supabase = None
        self.warnings: List[str] = []

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = _supabase_client()
        return self._supabase

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"  [WARN] Rapid-change telemetry: {message}")

    def record(self, result: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        artifact_path = _scan_artifact_path()
        result_status = result.get("status")
        status = _telemetry_status(result)
        metrics = build_rapid_change_scan_metrics(result)
        metadata = build_rapid_change_scan_metadata(result, artifact_path=artifact_path)
        now = _utc_now()
        summary = (
            "Forensic rapid-change scan completed: "
            f"status={status} candidates={metrics['candidate_count']} "
            f"fresh={metrics['fresh_candidates']} deduped={metrics['deduped_candidates']} "
            f"registered={metrics['registered_count']}"
        )
        if result_status == "failed":
            summary = f"Forensic rapid-change scan failed: {result.get('error') or 'unknown error'}"
        elif result_status == "disabled":
            summary = "Forensic rapid-change scan skipped: card-anchor bridge disabled"

        try:
            response = self.supabase.table("pipeline_runs").insert(
                {
                    "pipeline_name": PIPELINE_NAME,
                    "paperclip_pipeline_name": PAPERCLIP_PIPELINE_NAME,
                    "report_type": REPORT_TYPE,
                    "project_slug": PIPELINE_PROJECT_SLUG,
                    "version": 1,
                    "status": status,
                    "trigger_type": "workflow_dispatch" if os.environ.get("GITHUB_ACTIONS") else "manual",
                    "summary": summary,
                    "started_at": now,
                    "completed_at": now,
                    "languages_completed": {},
                    "error_detail": str(result.get("error") or "")[:500] if result_status == "failed" else None,
                    "metrics": metrics,
                    "artifact_path": artifact_path,
                    "dry_run": bool(result.get("dry_run", True)),
                    "force": False,
                    "slug_filter": None,
                    "metadata": metadata,
                    "github_run_id": metadata.get("githubRunId"),
                    "github_run_number": metadata.get("githubRunNumber"),
                    "github_workflow": metadata.get("githubWorkflow"),
                    "github_sha": metadata.get("githubSha"),
                }
            ).execute()
            row = (response.data or [{}])[0]
            run_id = row.get("id")
            if not run_id:
                self.warn("Supabase pipeline run insert returned no id")
                return

            self.supabase.table("pipeline_node_runs").insert(
                [
                    {
                        "pipeline_run_id": run_id,
                        "node_key": node_key,
                        "node_name": node_name,
                        "report_type": REPORT_TYPE,
                        "status": status,
                        "started_at": now,
                        "finished_at": now,
                        "summary": f"{node_name}: {status}",
                        "metrics": metrics,
                        "artifact_path": artifact_path,
                        "metadata": {**metadata, "nodeKey": node_key, "nodeName": node_name},
                    }
                    for node_key, node_name in TELEMETRY_NODES
                ]
            ).execute()
            self.supabase.table("pipeline_events").insert(
                {
                    "pipeline_run_id": run_id,
                    "event_type": "forensic_rapid_change_scan.completed",
                    "severity": "error" if result_status == "failed" else "info",
                    "message": summary,
                    "occurred_at": now,
                    "artifact_path": artifact_path,
                    "details": {
                        **metadata,
                        "status": status,
                        "metrics": metrics,
                        "telemetryWarnings": self.warnings,
                        "error": result.get("error"),
                    },
                }
            ).execute()
        except Exception as e:
            self.warn(f"Supabase telemetry write failed: {e}")


def observation_window_id(candidate: Dict[str, Any]) -> str:
    source = candidate.get("source") if isinstance(candidate.get("source"), dict) else {}
    raw = source.get("source_timestamp") or source.get("last_updated") or candidate.get("observed_at")
    parsed = _parse_time(raw)
    if parsed:
        return parsed.strftime("%Y-%m-%dT%HZ")
    return str(raw or DEFAULT_OBSERVATION_WINDOW)


def anchor_id_for_candidate(candidate: Dict[str, Any]) -> str:
    return f"{candidate.get('slug')}:{observation_window_id(candidate)}"


def candidate_to_card_anchor(candidate: Dict[str, Any]) -> Dict[str, Any]:
    observed_at = candidate.get("observed_at")
    relative_deviation = float(candidate.get("relative_deviation") or 0)
    token_change = float(candidate.get("token_change_24h") or 0)
    risk_level = "critical" if relative_deviation >= 25 else "high"
    slug = candidate.get("slug")
    anchor_id = anchor_id_for_candidate(candidate)

    trigger_data = {
        "slug": slug,
        "symbol": candidate.get("symbol"),
        "name": candidate.get("name"),
        "cmc_rank": candidate.get("rank"),
        "price": candidate.get("price"),
        "price_change_24h": token_change,
        "market_avg_change_24h": candidate.get("market_average_change_24h"),
        "relative_deviation": relative_deviation,
        "direction": candidate.get("direction"),
        "risk_level": risk_level,
        "scan_timestamp": observed_at,
        "source": candidate.get("source"),
    }

    return {
        "anchor_id": anchor_id,
        "observation_window": observation_window_id(candidate),
        "target": {
            "surface": "forensic_card_generation",
            "report_type": "forensic",
            "legacy_generator": "_legacy/pipeline/gen_for_card.py",
        },
        "slug": slug,
        "symbol": candidate.get("symbol"),
        "observed_at": observed_at,
        "trigger_data": trigger_data,
        "card_data_patch": {
            "report_type": "for",
            "slug": slug,
            "symbol": candidate.get("symbol"),
            "project_name": candidate.get("name"),
            "price_change_24h": token_change,
            "market_avg_change_24h": candidate.get("market_average_change_24h"),
            "relative_deviation": relative_deviation,
            "direction": candidate.get("direction"),
            "risk_level": risk_level,
            "source_node": "candidate.for.sudden_movers_scanner",
            "source_observed_at": observed_at,
        },
    }


def _trigger_reason_from_candidate(candidate: Dict[str, Any]) -> str:
    direction = "surged" if candidate.get("direction") == "up" else "dropped"
    symbol = candidate.get("symbol") or candidate.get("slug")
    return (
        f"{symbol} {direction} {float(candidate.get('token_change_24h') or 0):+.1f}% "
        f"over 24h versus market average "
        f"{float(candidate.get('market_average_change_24h') or 0):+.1f}%; "
        f"relative deviation {float(candidate.get('relative_deviation') or 0):.1f}pp."
    )


def candidate_to_intake_handoff_contract(
    candidate: Dict[str, Any],
    *,
    lang: str = DEFAULT_HANDOFF_LANG,
    version: int = DEFAULT_HANDOFF_VERSION,
) -> Dict[str, Any]:
    """Build the default-off scanner -> human source -> Slide PDF intake contract."""
    slug = str(candidate.get("slug") or "").strip().lower()
    if not slug:
        raise ValueError("candidate slug is required for intake handoff")
    if not lang:
        raise ValueError("handoff language is required")

    anchor = candidate_to_card_anchor(candidate)
    draft_name = f"{slug}_for_v{version}_{lang}.md"
    slide_pdf_hint = f"Slide/for/{slug}/{slug}_for_v{version}_{lang}.pdf"
    observed_at = candidate.get("observed_at")
    trigger_reason = _trigger_reason_from_candidate(candidate)

    return {
        "contract_version": 1,
        "status": "draft_request_pending",
        "activation": {
            "feature_flag": ENABLE_ENV,
            "default": "off",
            "write_mode": "requires --write and feature flag",
        },
        "source": {
            "node_id": "candidate.for.sudden_movers_scanner",
            "anchor_id": anchor["anchor_id"],
            "observed_at": observed_at,
            "candidate": candidate,
        },
        "card_generation": anchor,
        "registration": {
            "legacy_contract": "_legacy/pipeline/scan_forensic.py::register_coming_soon",
            "tables": {
                "forensic_triggers": {
                    "slug": slug,
                    "symbol": candidate.get("symbol"),
                    "scan_timestamp": observed_at,
                    "status": "detected",
                    "triggered": True,
                    "risk_level": anchor["trigger_data"]["risk_level"],
                    "trigger_reasons": [trigger_reason],
                },
                "project_reports": {
                    "report_type": "forensic",
                    "version": version,
                    "language": lang,
                    "status": "coming_soon",
                    "trigger_reason": trigger_reason,
                    "trigger_data": {
                        **anchor["trigger_data"],
                        "handoff_contract": {
                            "slug": slug,
                            "rtype": "for",
                            "db_report_type": "forensic",
                            "source_draft_name": draft_name,
                            "slide_pdf_hint": slide_pdf_hint,
                        },
                    },
                },
            },
        },
        "human_source_request": {
            "recipient_role": "forensic_source_author",
            "action": "write_source_draft",
            "draft_name": draft_name,
            "draft_path": f"BCE Research Source Drafts/{draft_name}",
            "required_slug": slug,
            "required_rtype": "for",
            "required_report_type": "forensic",
            "required_lang": lang,
        },
        "slide_intake": {
            "watcher": "scripts/pipeline/watch_slides.py",
            "args": ["--type", "for", "--slug", slug],
            "expected_db_report_type": "forensic",
            "expected_source_draft_name": draft_name,
            "expected_slide_pdf_hint": slide_pdf_hint,
            "diagnostic_status_if_missing": "source_waiting_for_slide_pdf",
        },
    }


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"emitted_anchor_ids": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"emitted_anchor_ids": []}
    if not isinstance(data, dict):
        return {"emitted_anchor_ids": []}
    emitted = data.get("emitted_anchor_ids")
    if not isinstance(emitted, list):
        data["emitted_anchor_ids"] = []
    return data


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dedupe_anchors(
    anchors: Iterable[Dict[str, Any]],
    state: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    emitted = set(state.get("emitted_anchor_ids") or [])
    fresh: List[Dict[str, Any]] = []
    duplicate: List[Dict[str, Any]] = []
    seen_this_run = set()

    for anchor in anchors:
        anchor_id = str(anchor.get("anchor_id") or "")
        if not anchor_id or anchor_id in emitted or anchor_id in seen_this_run:
            duplicate.append({**anchor, "dedupe_status": "duplicate"})
            continue
        seen_this_run.add(anchor_id)
        fresh.append({**anchor, "dedupe_status": "new"})

    return fresh, duplicate


def append_anchors(path: Path, anchors: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for anchor in anchors:
            fh.write(json.dumps(anchor, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def run_card_anchor_bridge(
    *,
    enabled: Optional[bool] = None,
    dry_run: bool = True,
    limit: int = DEFAULT_LIMIT,
    threshold_pct_points: Optional[float] = None,
    state_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    scanner: Callable[..., Dict[str, Any]] = run_candidate_scan,
) -> Dict[str, Any]:
    active = is_enabled() if enabled is None else enabled
    resolved_state_path = state_path or Path(os.environ.get(STATE_PATH_ENV, DEFAULT_STATE_PATH))
    resolved_output_path = output_path or Path(os.environ.get(OUTPUT_PATH_ENV, DEFAULT_OUTPUT_PATH))
    telemetry = RapidChangeScanTelemetry()

    if not active:
        result = {
            "status": "disabled",
            "enabled": False,
            "dry_run": dry_run,
            "anchors": [],
            "duplicates": [],
            "handoff_contracts": [],
            "message": f"{ENABLE_ENV} is not enabled; current FOR publishing behavior is unchanged.",
        }
        telemetry.record(result)
        return result

    try:
        scan = scanner(limit=limit, threshold_pct_points=threshold_pct_points)
    except Exception as e:
        result = {
            "status": "failed",
            "enabled": True,
            "dry_run": dry_run,
            "anchors": [],
            "duplicates": [],
            "handoff_contracts": [],
            "error": str(e),
        }
        telemetry.record(result)
        return result

    if scan.get("status") != "ok":
        result = {
            "status": "failed",
            "enabled": True,
            "dry_run": dry_run,
            "anchors": [],
            "duplicates": [],
            "handoff_contracts": [],
            "scanner": scan,
            "error": scan.get("error"),
        }
        telemetry.record(result)
        return result

    anchors = [candidate_to_card_anchor(candidate) for candidate in scan.get("candidates", [])]
    handoff_contracts = [
        candidate_to_intake_handoff_contract(candidate)
        for candidate in scan.get("candidates", [])
    ]
    state = load_state(resolved_state_path)
    fresh, duplicates = dedupe_anchors(anchors, state)
    fresh_anchor_ids = {anchor["anchor_id"] for anchor in fresh}
    fresh_handoff_contracts = [
        contract
        for contract in handoff_contracts
        if contract["source"]["anchor_id"] in fresh_anchor_ids
    ]

    if not dry_run and fresh:
        append_anchors(resolved_output_path, fresh)
        emitted = list(state.get("emitted_anchor_ids") or [])
        emitted.extend(anchor["anchor_id"] for anchor in fresh)
        state["emitted_anchor_ids"] = sorted(set(emitted))
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(resolved_state_path, state)

    result = {
        "status": "ok",
        "enabled": True,
        "dry_run": dry_run,
        "state_path": str(resolved_state_path),
        "output_path": str(resolved_output_path),
        "anchors": fresh,
        "duplicates": duplicates,
        "handoff_contracts": fresh_handoff_contracts,
        "scanner": {
            "observed_at": scan.get("observed_at"),
            "threshold_pct_points": scan.get("threshold_pct_points"),
            "warnings": scan.get("warnings", []),
            "candidate_count": len(scan.get("candidates", [])),
        },
    }
    telemetry.record(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Default-off sudden movers FOR card anchor bridge.")
    parser.add_argument("--enable", action="store_true", help=f"Activate this run without setting {ENABLE_ENV}.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="No state/output writes. Default.")
    parser.add_argument("--write", action="store_true", help="Write new anchors and update dedupe state.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = run_card_anchor_bridge(
        enabled=args.enable or None,
        dry_run=not args.write,
        limit=args.limit,
        threshold_pct_points=args.threshold,
        state_path=args.state,
        output_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ok", "disabled"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
