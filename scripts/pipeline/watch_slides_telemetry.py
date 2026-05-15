"""Remote pipeline state helpers for the slide watcher.

GitHub Actions must not call a local Paperclip instance. The watcher writes
runtime state to Supabase tables, and Paperclip can read that remote state.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

PIPELINE_NAMES: Dict[str, str] = {
    'econ': 'ECON Report Publishing',
    'mat': 'MAT Report Publishing',
    'for': 'FOR Report Publishing',
}

PIPELINE_NODE_STAGES: List[Tuple[str, str]] = [
    ('source_collection', 'Slide PDF intake'),
    ('research_synthesis', 'Analysis source confirmation'),
    ('draft_report', 'Summary and marketing extraction'),
    ('summary_marketing_localization', '7-language summary and marketing localization'),
    ('editorial_review', 'Publication review'),
    ('website_publish', 'Website publishing'),
    ('post_publish_monitoring', 'Post-publish monitoring'),
]

PIPELINE_SUCCESS_STATUSES = {
    'published',
    'published_created',
    'unchanged',
    'dry_run',
    'pruned_stale_languages',
    'pruned_stale_storage',
    'db_reconcile_ok',
    'db_reconcile_cancelled',
    'db_reconcile_timestamp_synced',
    'db_reconcile_timestamp_cleared',
    'dry_run_db_reconcile_cancel',
    'dry_run_db_reconcile_timestamp_sync',
    'dry_run_db_reconcile_timestamp_clear',
}

PIPELINE_FAILURE_STATUSES = {'failed'}

PIPELINE_BLOCKED_STATUSES = {
    'unresolved',
    'mismatch',
    'language_mismatch',
    'blocked_missing_analysis_source',
    'prune_skipped_no_publishable_pdf',
    'prune_skipped_no_project_id',
    'prune_skipped_no_supabase',
    'prune_storage_failed',
    'db_reconcile_skipped',
}


def _pipeline_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_store_url() -> str:
    return (os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or '').rstrip('/')


def _state_store_key() -> str:
    return (
        os.environ.get('SUPABASE_SERVICE_KEY')
        or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
        or ''
    )


def _state_store_configured() -> bool:
    return bool(
        _state_store_url()
        and _state_store_key()
    )


def _pipeline_name_from_env(rtype: str) -> str:
    suffix = rtype.upper()
    return (
        os.environ.get(f'PIPELINE_{suffix}_NAME')
        or PIPELINE_NAMES[rtype]
    )


def build_pipeline_run_payload(
    *,
    rtype: str,
    scan_time: str,
    dry_run: bool,
    force: bool,
    slug: Optional[str],
) -> Dict[str, Any]:
    return {
        'pipeline_name': _pipeline_name_from_env(rtype),
        'report_type': rtype,
        'project_slug': slug,
        'status': 'processing',
        'trigger_type': 'schedule' if os.environ.get('GITHUB_ACTIONS') else 'manual',
        'started_at': _pipeline_utc_now(),
        'dry_run': dry_run,
        'force': force,
        'github_run_id': os.environ.get('GITHUB_RUN_ID'),
        'github_run_number': os.environ.get('GITHUB_RUN_NUMBER'),
        'github_workflow': os.environ.get('GITHUB_WORKFLOW'),
        'github_sha': os.environ.get('GITHUB_SHA'),
        'metadata': {
            'reportType': rtype,
            'scanTime': scan_time,
            'dryRun': dry_run,
            'force': force,
            'slug': slug,
            'source': 'watch_slides.py',
        },
    }


def build_pipeline_node_run_payload(
    *,
    pipeline_run_id: str,
    rtype: str,
    stage_key: str,
    stage_name: str,
    status: str,
    metrics: Dict[str, int],
    log_path: Optional[str],
) -> Dict[str, Any]:
    now = _pipeline_utc_now()
    return {
        'pipeline_run_id': pipeline_run_id,
        'pipeline_name': _pipeline_name_from_env(rtype),
        'node_key': stage_key,
        'node_name': stage_name,
        'status': status,
        'started_at': now,
        'completed_at': now,
        'metrics': metrics,
        'metadata': {
            'reportType': rtype,
            'logArtifactPath': log_path,
            'source': 'watch_slides.py',
        },
    }


def build_pipeline_event_payload(
    *,
    pipeline_run_id: str,
    rtype: str,
    status: str,
    metrics: Dict[str, int],
    log_path: Optional[str],
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        'pipeline_run_id': pipeline_run_id,
        'pipeline_name': _pipeline_name_from_env(rtype),
        'event_type': 'slide_watcher.completed',
        'severity': 'error' if status == 'failed' else 'warning' if status == 'waiting_manual' else 'info',
        'message': (
            f"{rtype.upper()} slide watcher completed: "
            f"scanned={metrics['scanned']} processed={metrics['processed']} "
            f"published={metrics['published']} unresolved={metrics['unresolved']} "
            f"failed={metrics['failed']}"
        ),
        'occurred_at': _pipeline_utc_now(),
        'artifact_ref': log_path,
        'details': {
            'reportType': rtype,
            'status': status,
            'metrics': metrics,
            'logArtifactPath': log_path,
            'warnings': warnings or [],
            'source': 'watch_slides.py',
        },
    }


def _pipeline_counts_for_type(
    rtype: str,
    scanned: List[Dict[str, Any]],
    processed: List[Dict[str, Any]],
) -> Dict[str, int]:
    scanned_for_type = [r for r in scanned if r.get('rtype') == rtype]
    processed_for_type = [r for r in processed if r.get('rtype') == rtype]
    return {
        'scanned': len(scanned_for_type),
        'processed': len(processed_for_type),
        'published': sum(1 for r in processed_for_type if r.get('status') == 'published'),
        'unresolved': sum(1 for r in processed_for_type if r.get('status') == 'unresolved'),
        'failed': sum(1 for r in processed_for_type if r.get('status') in PIPELINE_FAILURE_STATUSES),
        'blocked': sum(1 for r in processed_for_type if r.get('status') in PIPELINE_BLOCKED_STATUSES),
    }


def _pipeline_status_for_counts(metrics: Dict[str, int]) -> str:
    if metrics.get('failed', 0) > 0:
        return 'failed'
    if metrics.get('blocked', 0) > 0 or metrics.get('unresolved', 0) > 0:
        return 'waiting_manual'
    return 'published'


class RemotePipelineState:
    def __init__(self) -> None:
        self.enabled = _state_store_configured()
        self.api_url = _state_store_url()
        self.key = _state_store_key()
        self.run_ids: Dict[str, str] = {}
        self.warnings: List[str] = []

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"  [WARN] Pipeline state store: {message}")

    def _url_for_table(self, table: str, query: str = '') -> str:
        suffix = f"/rest/v1/{table}{query}"
        return f"{self.api_url}{suffix}"

    def _request_once(
        self,
        method: str,
        table: str,
        payload: Optional[Any] = None,
        query: str = '',
    ) -> Tuple[Optional[Any], Optional[str]]:
        if not self.enabled:
            return None, None
        body = None
        headers = {
            'Accept': 'application/json',
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Prefer': 'return=representation',
        }
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        url = self._url_for_table(table, query)
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8')
                if not raw:
                    return {}, None
                content_type = resp.headers.get('content-type', '')
                if 'application/json' not in content_type:
                    raise RuntimeError(f"non-JSON response from {table}: {content_type}")
                return json.loads(raw), None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, json.JSONDecodeError) as e:
            return None, str(e)

    def request(self, method: str, table: str, payload: Optional[Any] = None, query: str = '') -> Optional[Any]:
        response, error = self._request_once(method, table, payload, query)
        if error is None:
            return response
        self.warn(f"{method} {table}{query} failed: {error}")
        return None

    def start_runs(self, types: List[str], *, scan_time: str, dry_run: bool, force: bool, slug: Optional[str]) -> None:
        if not self.enabled:
            self.warn('disabled; set SUPABASE_URL and SUPABASE_SERVICE_KEY to publish pipeline state')
            return
        for rtype in types:
            payload = build_pipeline_run_payload(
                rtype=rtype,
                scan_time=scan_time,
                dry_run=dry_run,
                force=force,
                slug=slug,
            )
            response = self.request('POST', 'pipeline_runs', payload)
            row = response[0] if isinstance(response, list) and response else response
            run_id = (row or {}).get('id')
            if run_id:
                self.run_ids[rtype] = run_id
            else:
                self.warn(f"{rtype.upper()} remote run was not created")

    def complete_runs(
        self,
        types: List[str],
        *,
        scanned: List[Dict[str, Any]],
        processed: List[Dict[str, Any]],
        log_path: Optional[str],
    ) -> None:
        if not self.enabled:
            return
        for rtype in types:
            run_id = self.run_ids.get(rtype)
            if not run_id:
                continue
            metrics = _pipeline_counts_for_type(rtype, scanned, processed)
            status = _pipeline_status_for_counts(metrics)
            for stage_key, stage_name in PIPELINE_NODE_STAGES:
                self.request(
                    'POST',
                    'pipeline_node_runs',
                    build_pipeline_node_run_payload(
                        pipeline_run_id=run_id,
                        rtype=rtype,
                        stage_key=stage_key,
                        stage_name=stage_name,
                        status=status,
                        metrics=metrics,
                        log_path=log_path,
                    ),
                )
            self.request(
                'POST',
                'pipeline_events',
                build_pipeline_event_payload(
                    pipeline_run_id=run_id,
                    rtype=rtype,
                    status=status,
                    metrics=metrics,
                    log_path=log_path,
                    warnings=self.warnings,
                ),
            )
            self.request(
                'PATCH',
                'pipeline_runs',
                {
                    'status': status,
                    'completed_at': _pipeline_utc_now(),
                    'languages_completed': metrics,
                    'log_artifact_path': log_path,
                    'error_detail': None if status == 'published' else (
                        f"scanned={metrics['scanned']} processed={metrics['processed']} "
                        f"unresolved={metrics['unresolved']} failed={metrics['failed']}"
                    ),
                    'metadata': {
                        'reportType': rtype,
                        'metrics': metrics,
                        'logArtifactPath': log_path,
                        'telemetryWarnings': self.warnings,
                        'source': 'watch_slides.py',
                    },
                },
                query=f'?id=eq.{run_id}',
            )


PAPERCLIP_PIPELINE_NAMES = PIPELINE_NAMES
PAPERCLIP_NODE_STAGES = PIPELINE_NODE_STAGES
PAPERCLIP_SUCCESS_STATUSES = PIPELINE_SUCCESS_STATUSES
PAPERCLIP_FAILURE_STATUSES = PIPELINE_FAILURE_STATUSES
PAPERCLIP_BLOCKED_STATUSES = PIPELINE_BLOCKED_STATUSES
PaperclipTelemetry = RemotePipelineState
build_paperclip_run_payload = build_pipeline_run_payload
build_paperclip_node_run_payload = build_pipeline_node_run_payload
build_paperclip_event_payload = build_pipeline_event_payload
_paperclip_counts_for_type = _pipeline_counts_for_type
_paperclip_status_for_counts = _pipeline_status_for_counts
_paperclip_utc_now = _pipeline_utc_now
_paperclip_configured = _state_store_configured
_paperclip_auth_token = _state_store_key
_paperclip_pipeline_name_from_env = _pipeline_name_from_env


def _paperclip_pipeline_id_from_env(rtype: str) -> Optional[str]:
    return None
