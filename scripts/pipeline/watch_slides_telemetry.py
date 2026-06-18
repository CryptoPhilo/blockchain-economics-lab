"""Supabase-first telemetry helpers for the slide watcher.

Paperclip REST telemetry is intentionally a secondary, explicit opt-in sink.
GitHub Actions must not depend on a local Paperclip API to record report
pipeline state.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

PAPERCLIP_PIPELINE_NAMES: Dict[str, str] = {
    'econ': 'ECON Report Publishing',
    'mat': 'MAT Report Publishing',
    'for': 'FOR Report Publishing',
}

PAPERCLIP_NODE_STAGES: List[Tuple[str, str]] = [
    ('source_collection', 'Slide PDF intake'),
    ('research_synthesis', 'Analysis source confirmation'),
    ('draft_report', 'Summary and marketing extraction'),
    ('summary_marketing_localization', '7-language summary and marketing localization'),
    ('editorial_review', 'Publication review'),
    ('website_publish', 'Website publishing'),
    ('post_publish_monitoring', 'Post-publish monitoring'),
]

PAPERCLIP_SUCCESS_STATUSES = {
    'published',
    'review_ready',
    'review_ready_created',
    'unchanged',
    'dry_run',
    'pruned_stale_languages',
    'pruned_stale_storage',
    'db_reconcile_ok',
    'db_reconcile_cancelled',
    'db_reconcile_cancelled_missing_active_slide_pdf',
    'db_reconcile_for_placeholder_without_active_slide_pdf',
    'db_reconcile_materialized',
    'db_reconcile_timestamp_synced',
    'db_reconcile_timestamp_cleared',
    'dry_run_db_reconcile_cancel',
    'dry_run_db_reconcile_cancel_missing_active_slide_pdf',
    'dry_run_db_reconcile_for_placeholder_without_active_slide_pdf',
    'dry_run_db_reconcile_materialize',
    'dry_run_db_reconcile_timestamp_sync',
    'dry_run_db_reconcile_timestamp_clear',
}

PAPERCLIP_FAILURE_STATUSES = {'failed'}

PAPERCLIP_BLOCKED_STATUSES = {
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


def _paperclip_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy_env(name: str) -> bool:
    return (os.environ.get(name) or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _supabase_url() -> Optional[str]:
    return os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')


def _supabase_service_key() -> Optional[str]:
    return os.environ.get('SUPABASE_SERVICE_KEY')


def _supabase_configured() -> bool:
    return bool(_supabase_url() and _supabase_service_key())


def _supabase_client():
    url = _supabase_url()
    key = _supabase_service_key()
    if not url or not key:
        raise RuntimeError('SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY are required')
    from supabase import create_client
    return create_client(url, key)


def _paperclip_configured() -> bool:
    return bool(
        _truthy_env('PAPERCLIP_TELEMETRY_SECONDARY_ENABLED')
        and
        os.environ.get('PAPERCLIP_API_URL')
        and (
            os.environ.get('PAPERCLIP_API_KEY')
            or os.environ.get('PAPERCLIP_AGENT_TOKEN')
            or os.environ.get('PAPERCLIP_TOKEN')
        )
    )


def _paperclip_auth_token() -> Optional[str]:
    return (
        os.environ.get('PAPERCLIP_API_KEY')
        or os.environ.get('PAPERCLIP_AGENT_TOKEN')
        or os.environ.get('PAPERCLIP_TOKEN')
    )


def _paperclip_pipeline_id_from_env(rtype: str) -> Optional[str]:
    suffix = rtype.upper()
    return (
        os.environ.get(f'PAPERCLIP_{suffix}_PIPELINE_ID')
        or os.environ.get(f'PAPERCLIP_PIPELINE_ID_{suffix}')
        or os.environ.get(f'PAPERCLIP_PIPELINE_{suffix}_ID')
    )


def _paperclip_pipeline_name_from_env(rtype: str) -> str:
    suffix = rtype.upper()
    return (
        os.environ.get(f'PAPERCLIP_{suffix}_PIPELINE_NAME')
        or os.environ.get(f'PAPERCLIP_PIPELINE_NAME_{suffix}')
        or PAPERCLIP_PIPELINE_NAMES[rtype]
    )


def build_paperclip_run_payload(
    *,
    rtype: str,
    scan_time: str,
    dry_run: bool,
    force: bool,
    slug: Optional[str],
) -> Dict[str, Any]:
    return {
        'status': 'running',
        'triggerType': 'schedule' if os.environ.get('GITHUB_ACTIONS') else 'manual',
        'startedAt': _paperclip_utc_now(),
        'summary': f"{rtype.upper()} slide watcher started",
        'metadata': {
            'reportType': rtype,
            'scanTime': scan_time,
            'dryRun': dry_run,
            'force': force,
            'slug': slug,
            'githubRunId': os.environ.get('GITHUB_RUN_ID'),
            'githubRunNumber': os.environ.get('GITHUB_RUN_NUMBER'),
            'githubWorkflow': os.environ.get('GITHUB_WORKFLOW'),
            'githubSha': os.environ.get('GITHUB_SHA'),
        },
    }


def build_paperclip_node_run_payload(
    *,
    pipeline_run_id: str,
    node_id: str,
    rtype: str,
    stage_key: str,
    stage_name: str,
    status: str,
    metrics: Dict[str, int],
    log_path: Optional[str],
) -> Dict[str, Any]:
    now = _paperclip_utc_now()
    return {
        'runId': pipeline_run_id,
        'nodeId': node_id,
        'status': status,
        'startedAt': now,
        'finishedAt': now,
        'summary': f"{stage_name}: {status}",
        'metadata': {
            'reportType': rtype,
            'nodeKey': stage_key,
            'nodeName': stage_name,
            'metrics': metrics,
            'logArtifactPath': log_path,
            'source': 'watch_slides.py',
        },
    }


def build_paperclip_event_payload(
    *,
    pipeline_run_id: str,
    rtype: str,
    status: str,
    metrics: Dict[str, int],
    log_path: Optional[str],
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        'runId': pipeline_run_id,
        'eventType': 'slide_watcher.completed',
        'severity': 'error' if status == 'failed' else 'warning' if status == 'waiting_manual' else 'info',
        'message': (
            f"{rtype.upper()} slide watcher completed: "
            f"scanned={metrics['scanned']} processed={metrics['processed']} "
            f"review_ready={metrics['review_ready']} unresolved={metrics['unresolved']} "
            f"failed={metrics['failed']}"
        ),
        'occurredAt': _paperclip_utc_now(),
        'artifactRef': log_path,
        'details': {
            'reportType': rtype,
            'status': status,
            'metrics': metrics,
            'logArtifactPath': log_path,
            'warnings': warnings or [],
            'source': 'watch_slides.py',
        },
    }


def build_supabase_run_row(
    *,
    rtype: str,
    scan_time: str,
    dry_run: bool,
    force: bool,
    slug: Optional[str],
) -> Dict[str, Any]:
    payload = build_paperclip_run_payload(
        rtype=rtype,
        scan_time=scan_time,
        dry_run=dry_run,
        force=force,
        slug=slug,
    )
    metadata = payload['metadata']
    return {
        'pipeline_name': 'slide-pipeline',
        'paperclip_pipeline_name': _paperclip_pipeline_name_from_env(rtype),
        'report_type': rtype,
        'project_slug': slug,
        'version': 1,
        'status': 'running',
        'trigger_type': payload['triggerType'],
        'summary': payload['summary'],
        'started_at': payload['startedAt'],
        'dry_run': dry_run,
        'force': force,
        'slug_filter': slug,
        'source_filename': None,
        'retry_count': 0,
        'languages_completed': {},
        'metadata': metadata,
        'github_run_id': metadata.get('githubRunId'),
        'github_run_number': metadata.get('githubRunNumber'),
        'github_workflow': metadata.get('githubWorkflow'),
        'github_sha': metadata.get('githubSha'),
    }


def build_supabase_node_run_row(
    *,
    pipeline_run_id: str,
    rtype: str,
    stage_key: str,
    stage_name: str,
    status: str,
    metrics: Dict[str, int],
    log_path: Optional[str],
) -> Dict[str, Any]:
    payload = build_paperclip_node_run_payload(
        pipeline_run_id=pipeline_run_id,
        node_id=stage_key,
        rtype=rtype,
        stage_key=stage_key,
        stage_name=stage_name,
        status=status,
        metrics=metrics,
        log_path=log_path,
    )
    return {
        'pipeline_run_id': pipeline_run_id,
        'node_key': stage_key,
        'node_name': stage_name,
        'report_type': rtype,
        'status': status,
        'started_at': payload['startedAt'],
        'finished_at': payload['finishedAt'],
        'summary': payload['summary'],
        'metrics': metrics,
        'artifact_path': log_path,
        'metadata': payload['metadata'],
    }


def build_supabase_event_row(
    *,
    pipeline_run_id: str,
    rtype: str,
    status: str,
    metrics: Dict[str, int],
    log_path: Optional[str],
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    payload = build_paperclip_event_payload(
        pipeline_run_id=pipeline_run_id,
        rtype=rtype,
        status=status,
        metrics=metrics,
        log_path=log_path,
        warnings=warnings,
    )
    return {
        'pipeline_run_id': pipeline_run_id,
        'event_type': payload['eventType'],
        'severity': payload['severity'],
        'message': payload['message'],
        'occurred_at': payload['occurredAt'],
        'artifact_path': payload['artifactRef'],
        'details': payload['details'],
    }


def _paperclip_counts_for_type(
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
        'review_ready': sum(1 for r in processed_for_type if r.get('status') == 'review_ready'),
        'unresolved': sum(1 for r in processed_for_type if r.get('status') == 'unresolved'),
        'failed': sum(1 for r in processed_for_type if r.get('status') in PAPERCLIP_FAILURE_STATUSES),
        'blocked': sum(1 for r in processed_for_type if r.get('status') in PAPERCLIP_BLOCKED_STATUSES),
    }


def _paperclip_status_for_counts(metrics: Dict[str, int]) -> str:
    if metrics.get('failed', 0) > 0:
        return 'failed'
    if metrics.get('blocked', 0) > 0 or metrics.get('unresolved', 0) > 0:
        return 'waiting_manual'
    return 'succeeded'


class PaperclipTelemetry:
    def __init__(self) -> None:
        self.enabled = _supabase_configured()
        self.supabase_enabled = self.enabled
        self.paperclip_secondary_enabled = _paperclip_configured()
        self._supabase = None
        self.api_url = (os.environ.get('PAPERCLIP_API_URL') or '').rstrip('/')
        self.company_id = os.environ.get('PAPERCLIP_COMPANY_ID')
        self.token = _paperclip_auth_token()
        self.pipeline_ids: Dict[str, str] = {}
        self.node_ids: Dict[str, Dict[str, str]] = {}
        self.run_ids: Dict[str, str] = {}
        self.paperclip_run_ids: Dict[str, str] = {}
        self.warnings: List[str] = []

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"  [WARN] Slide telemetry: {message}")

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = _supabase_client()
        return self._supabase

    def _url_for_path(self, path: str) -> str:
        if self.api_url.endswith('/api') and path.startswith('/api/'):
            return f"{self.api_url}{path[4:]}"
        return f"{self.api_url}{path}"

    def _request_once(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Any], Optional[str]]:
        if not self.paperclip_secondary_enabled:
            return None, None
        body = None
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.token}',
        }
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        run_id = os.environ.get('PAPERCLIP_RUN_ID')
        if run_id:
            headers['X-Paperclip-Run-Id'] = run_id
        url = self._url_for_path(path)
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8')
                if not raw:
                    return {}, None
                content_type = resp.headers.get('content-type', '')
                if 'application/json' not in content_type:
                    raise RuntimeError(f"non-JSON response from {path}: {content_type}")
                return json.loads(raw), None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, json.JSONDecodeError) as e:
            return None, str(e)

    def request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        paths = [path]
        if not path.startswith('/api/'):
            paths.append(f'/api{path}')
        last_error = None
        for candidate in paths:
            response, error = self._request_once(method, candidate, payload)
            if error is None:
                return response
            last_error = error
        self.warn(f"{method} {path} failed: {last_error}")
        return None

    def resolve_pipeline_id(self, rtype: str) -> Optional[str]:
        configured_id = _paperclip_pipeline_id_from_env(rtype)
        if configured_id:
            self.resolve_pipeline_nodes(configured_id, rtype)
            return configured_id
        if not self.company_id:
            self.warn(f"{rtype.upper()} pipeline id not configured and PAPERCLIP_COMPANY_ID is missing")
            return None
        response = self.request('GET', f'/api/companies/{self.company_id}/pipelines')
        if not isinstance(response, list):
            self.warn(f"{rtype.upper()} pipeline lookup returned no pipeline list")
            return None
        expected_name = _paperclip_pipeline_name_from_env(rtype)
        for pipeline in response:
            if (pipeline.get('name') or '').strip() == expected_name:
                pipeline_id = pipeline.get('id')
                if pipeline_id:
                    self.resolve_pipeline_nodes(pipeline_id, rtype)
                return pipeline_id
        self.warn(f"{rtype.upper()} pipeline not found by name: {expected_name}")
        return None

    def resolve_pipeline_nodes(self, pipeline_id: str, rtype: str) -> None:
        response = self.request('GET', f'/api/pipelines/{pipeline_id}')
        if not isinstance(response, dict):
            self.warn(f"{rtype.upper()} pipeline detail lookup failed for node ids")
            return
        nodes = response.get('nodes')
        if not isinstance(nodes, list):
            self.warn(f"{rtype.upper()} pipeline detail did not include nodes")
            return
        node_ids = {
            str(node.get('nodeKey')): str(node.get('id'))
            for node in nodes
            if node.get('nodeKey') and node.get('id')
        }
        missing = [stage_key for stage_key, _stage_name in PAPERCLIP_NODE_STAGES if stage_key not in node_ids]
        if missing:
            self.warn(f"{rtype.upper()} pipeline missing node keys: {', '.join(missing)}")
        self.node_ids[rtype] = node_ids

    def start_runs(self, types: List[str], *, scan_time: str, dry_run: bool, force: bool, slug: Optional[str]) -> None:
        for rtype in types:
            run_id = None
            if self.supabase_enabled:
                try:
                    response = self.supabase.table('pipeline_runs').insert(
                        build_supabase_run_row(
                            rtype=rtype,
                            scan_time=scan_time,
                            dry_run=dry_run,
                            force=force,
                            slug=slug,
                        )
                    ).execute()
                    row = (response.data or [{}])[0]
                    run_id = row.get('id')
                    if run_id:
                        self.run_ids[rtype] = run_id
                    else:
                        self.warn(f"{rtype.upper()} Supabase run insert returned no id")
                except Exception as e:
                    self.warn(f"{rtype.upper()} Supabase run insert failed: {e}")

            if not self.paperclip_secondary_enabled:
                continue

            pipeline_id = self.resolve_pipeline_id(rtype)
            if pipeline_id:
                self.pipeline_ids[rtype] = pipeline_id
                payload = build_paperclip_run_payload(
                    rtype=rtype,
                    scan_time=scan_time,
                    dry_run=dry_run,
                    force=force,
                    slug=slug,
                )
                response = self.request('POST', f'/pipelines/{pipeline_id}/runs', payload)
                paperclip_run_id = (response or {}).get('id') or (response or {}).get('runId')
                if paperclip_run_id:
                    self.paperclip_run_ids[rtype] = paperclip_run_id
                    if not run_id:
                        self.run_ids[rtype] = paperclip_run_id
                else:
                    self.warn(f"{rtype.upper()} secondary Paperclip run was not created")

    def complete_runs(
        self,
        types: List[str],
        *,
        scanned: List[Dict[str, Any]],
        processed: List[Dict[str, Any]],
        log_path: Optional[str],
    ) -> None:
        for rtype in types:
            run_id = self.run_ids.get(rtype)
            if not run_id:
                continue
            metrics = _paperclip_counts_for_type(rtype, scanned, processed)
            status = _paperclip_status_for_counts(metrics)
            summary = (
                f"{rtype.upper()} slide watcher completed: "
                f"scanned={metrics['scanned']} processed={metrics['processed']} "
                f"review_ready={metrics['review_ready']} unresolved={metrics['unresolved']} "
                f"failed={metrics['failed']}"
            )

            if self.supabase_enabled:
                try:
                    rows = [
                        build_supabase_node_run_row(
                            pipeline_run_id=run_id,
                            rtype=rtype,
                            stage_key=stage_key,
                            stage_name=stage_name,
                            status=status,
                            metrics=metrics,
                            log_path=log_path,
                        )
                        for stage_key, stage_name in PAPERCLIP_NODE_STAGES
                    ]
                    self.supabase.table('pipeline_node_runs').insert(rows).execute()
                    self.supabase.table('pipeline_events').insert(
                        build_supabase_event_row(
                            pipeline_run_id=run_id,
                            rtype=rtype,
                            status=status,
                            metrics=metrics,
                            log_path=log_path,
                            warnings=self.warnings,
                        )
                    ).execute()
                    self.supabase.table('pipeline_runs').update({
                        'status': status,
                        'completed_at': _paperclip_utc_now(),
                        'summary': summary,
                        'metrics': metrics,
                        'artifact_path': log_path,
                        'error_detail': '; '.join(self.warnings)[:500] if self.warnings else None,
                        'metadata': {
                            'reportType': rtype,
                            'metrics': metrics,
                            'logArtifactPath': log_path,
                            'telemetryWarnings': self.warnings,
                            'source': 'watch_slides.py',
                        },
                    }).eq('id', run_id).execute()
                except Exception as e:
                    self.warn(f"{rtype.upper()} Supabase completion write failed: {e}")

            if not self.paperclip_secondary_enabled:
                continue

            pipeline_id = self.pipeline_ids.get(rtype)
            paperclip_run_id = self.paperclip_run_ids.get(rtype)
            if not pipeline_id or not paperclip_run_id:
                continue
            node_ids = self.node_ids.get(rtype, {})
            for stage_key, stage_name in PAPERCLIP_NODE_STAGES:
                node_id = node_ids.get(stage_key)
                if not node_id:
                    self.warn(f"{rtype.upper()} secondary Paperclip node run skipped; missing node id for {stage_key}")
                    continue
                self.request(
                    'POST',
                    f'/pipeline-runs/{paperclip_run_id}/node-runs',
                    build_paperclip_node_run_payload(
                        pipeline_run_id=paperclip_run_id,
                        node_id=node_id,
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
                f'/pipelines/{pipeline_id}/events',
                build_paperclip_event_payload(
                    pipeline_run_id=paperclip_run_id,
                    rtype=rtype,
                    status=status,
                    metrics=metrics,
                    log_path=log_path,
                    warnings=self.warnings,
                ),
            )
            self.request(
                'PATCH',
                f'/pipeline-runs/{paperclip_run_id}',
                {
                    'status': status,
                    'finishedAt': _paperclip_utc_now(),
                    'summary': summary,
                    'metadata': {
                        'reportType': rtype,
                        'metrics': metrics,
                        'logArtifactPath': log_path,
                        'telemetryWarnings': self.warnings,
                        'source': 'watch_slides.py',
                    },
                },
            )
