"""
Pipeline State — Supabase-based run tracking for ECON/MAT/FOR pipelines (BCE-732)

Replaces the legacy local JSON tracker with a shared Supabase table,
enabling cross-CI state synchronization and per-language progress tracking.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env.local')
if os.path.exists(_env_path):
    for line in open(_env_path).read().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

STALE_PROCESSING_MINUTES = 30
MAX_RETRIES = 3

TERMINAL_STATUSES = frozenset({'content_failed_terminal', 'done', 'published'})
RETRIABLE_STATUSES = frozenset({
    'processing_error', 'download_error', 'upload_done_db_error', 'failed_timeout',
})


def _normalize_status(status: str) -> str:
    return 'done' if status == 'published' else status


def _get_client():
    url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL / SUPABASE_SERVICE_KEY not set')
    from supabase import create_client
    return create_client(url, key)


class PipelineState:
    """Supabase-backed pipeline run state tracker."""

    def __init__(self, report_type: str, *, client=None):
        self.report_type = report_type
        self._sb = client or _get_client()

    def get_run_by_source(self, source_file_id: str) -> dict | None:
        result = self._sb.table('pipeline_runs').select('*') \
            .eq('report_type', self.report_type) \
            .eq('source_file_id', source_file_id) \
            .order('created_at', desc=True) \
            .limit(1).execute()
        return result.data[0] if result.data else None

    def get_run(self, project_slug: str, version: int = 1) -> dict | None:
        result = self._sb.table('pipeline_runs').select('*') \
            .eq('report_type', self.report_type) \
            .eq('project_slug', project_slug) \
            .eq('version', version) \
            .order('created_at', desc=True) \
            .limit(1).execute()
        return result.data[0] if result.data else None

    def list_active(self) -> list[dict]:
        result = self._sb.table('pipeline_runs').select('*') \
            .eq('report_type', self.report_type) \
            .not_.in_('status', list(TERMINAL_STATUSES)) \
            .order('created_at', desc=True) \
            .execute()
        return result.data or []

    def start_run(
        self,
        project_slug: str,
        *,
        version: int = 1,
        source_file_id: str | None = None,
        source_filename: str | None = None,
        retry_count: int = 0,
    ) -> dict:
        row = {
            'report_type': self.report_type,
            'project_slug': project_slug,
            'version': version,
            'status': 'processing',
            'source_file_id': source_file_id,
            'source_filename': source_filename,
            'retry_count': retry_count,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'languages_completed': {},
        }
        result = self._sb.table('pipeline_runs').insert(row).execute()
        return result.data[0]

    def update_status(self, run_id: str, status: str, *, error: str | None = None) -> dict:
        status = _normalize_status(status)
        update = {'status': status}
        if error is not None:
            update['error_detail'] = error[:500]
        if status in TERMINAL_STATUSES:
            update['completed_at'] = datetime.now(timezone.utc).isoformat()
        result = self._sb.table('pipeline_runs').update(update) \
            .eq('id', run_id).execute()
        return result.data[0] if result.data else {}

    def update_language(self, run_id: str, lang: str, lang_status: str) -> dict:
        run = self._sb.table('pipeline_runs').select('languages_completed') \
            .eq('id', run_id).execute()
        langs = (run.data[0]['languages_completed'] or {}) if run.data else {}
        langs[lang] = lang_status
        result = self._sb.table('pipeline_runs').update({'languages_completed': langs}) \
            .eq('id', run_id).execute()
        return result.data[0] if result.data else {}

    def increment_retry(self, run_id: str) -> dict:
        run = self._sb.table('pipeline_runs').select('retry_count') \
            .eq('id', run_id).execute()
        count = (run.data[0]['retry_count'] or 0) if run.data else 0
        result = self._sb.table('pipeline_runs').update({'retry_count': count + 1}) \
            .eq('id', run_id).execute()
        return result.data[0] if result.data else {}

    def should_process(self, source_file_id: str, *, force: bool = False) -> tuple[bool, dict | None]:
        """Check if a source file should be processed. Returns (should_process, existing_run)."""
        existing = self.get_run_by_source(source_file_id)
        if not existing:
            return True, None
        if force:
            return True, existing

        status = existing.get('status', '')
        retry_count = int(existing.get('retry_count', 0) or 0)

        if status in TERMINAL_STATUSES:
            return False, existing
        if status == 'dry_run':
            return True, existing

        # Retry cap applies uniformly to every non-terminal, non-dry-run path.
        # Without this guard, stale 'processing' rows could spawn unlimited
        # reruns because the stale-recovery branch previously skipped the cap.
        if retry_count >= MAX_RETRIES:
            return False, existing

        if status == 'processing':
            return self._is_stale(existing), existing
        if status in RETRIABLE_STATUSES:
            return True, existing
        return True, existing

    def _is_stale(self, run: dict) -> bool:
        started = run.get('started_at')
        if not started:
            return True
        try:
            started_dt = datetime.fromisoformat(str(started).replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - started_dt).total_seconds() / 60
            return elapsed > STALE_PROCESSING_MINUTES
        except Exception:
            return True
