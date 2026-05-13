"""Tests for current slide-pipeline daily operations reporting taxonomy."""

import builtins
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def daily_report():
    spec = importlib.util.spec_from_file_location(
        'daily_pipeline_report',
        Path(__file__).with_name('daily_pipeline_report.py'),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_daily_report_with_blocked_telemetry_import(monkeypatch):
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == 'watch_slides_telemetry':
            raise ImportError('forced fallback path')
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', blocked_import)
    spec = importlib.util.spec_from_file_location(
        'daily_pipeline_report_fallback',
        Path(__file__).with_name('daily_pipeline_report.py'),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iso(minutes_ago=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def test_slide_operations_summary_groups_statuses_by_report_type(daily_report):
    processed = {
        'econ-published': {
            'rtype': 'econ',
            'slug': 'bitcoin',
            'lang': 'en',
            'name': 'Bitcoin_ECON_en.pdf',
            'status': 'published',
            'updated_at': _iso(),
        },
        'mat-blocked': {
            'rtype': 'mat',
            'slug': 'cosmos-hub',
            'lang': 'ko',
            'name': 'cosmos_MAT_ko.pdf',
            'status': 'unresolved',
            'error': 'no matching active project',
            'updated_at': _iso(),
        },
        'for-reconcile': {
            'rtype': 'for',
            'slug': 'constellation',
            'lang': 'zh',
            'name': 'DAG_FOR_cn.pdf',
            'status': 'db_reconcile_timestamp_synced',
            'updated_at': _iso(),
        },
        'econ-stale': {
            'rtype': 'econ',
            'slug': 'filecoin',
            'lang': 'en',
            'name': 'filecoin_ECON_en.pdf',
            'status': 'processing',
            'started_at': _iso(minutes_ago=90),
            'updated_at': _iso(),
        },
        'for-failed': {
            'rtype': 'for',
            'slug': 'aave',
            'lang': 'ko',
            'name': 'AAVE_FOR_ko.pdf',
            'status': 'failed',
            'updated_at': _iso(),
        },
    }

    summary = daily_report.summarize_slide_operations(processed, days=1)

    assert summary['totals'] == {
        'success': 1,
        'failed': 1,
        'blocked': 1,
        'stale': 1,
        'reconcile': 1,
        'total': 5,
    }
    assert summary['by_type']['econ']['success'] == 1
    assert summary['by_type']['econ']['stale'] == 1
    assert summary['by_type']['mat']['blocked'] == 1
    assert summary['by_type']['for']['failed'] == 1
    assert summary['by_type']['for']['reconcile'] == 1


def test_fallback_success_statuses_include_drive_materialization(monkeypatch):
    fallback_report = _load_daily_report_with_blocked_telemetry_import(monkeypatch)

    assert 'db_reconcile_materialized' in fallback_report.PAPERCLIP_SUCCESS_STATUSES
    assert 'dry_run_db_reconcile_materialize' in fallback_report.PAPERCLIP_SUCCESS_STATUSES
    assert fallback_report._status_bucket({
        'status': 'db_reconcile_materialized',
    }) == 'reconcile'
    assert fallback_report._status_bucket({
        'status': 'dry_run_db_reconcile_materialize',
    }) == 'reconcile'


def test_daily_report_success_statuses_match_watch_slides_telemetry(daily_report):
    spec = importlib.util.spec_from_file_location(
        'watch_slides_telemetry',
        Path(__file__).with_name('watch_slides_telemetry.py'),
    )
    telemetry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(telemetry)

    assert daily_report.PAPERCLIP_SUCCESS_STATUSES == telemetry.PAPERCLIP_SUCCESS_STATUSES


def test_generated_report_names_current_manifest_and_legacy_tracker(daily_report):
    processed = {
        'mat-blocked': {
            'rtype': 'mat',
            'slug': 'cosmos-hub',
            'lang': 'ko',
            'name': 'cosmos_MAT_ko.pdf',
            'source_path': 'Slide/mat/cosmos_MAT_ko.pdf',
            'status': 'unresolved',
            'error': 'no matching active project',
            'updated_at': _iso(),
        },
        'for-reconcile': {
            'rtype': 'for',
            'slug': 'constellation',
            'lang': 'zh',
            'name': 'DAG_FOR_cn.pdf',
            'status': 'db_reconcile_timestamp_synced',
            'updated_at': _iso(),
        },
    }
    summary = daily_report.summarize_slide_operations(processed, days=1)

    report = daily_report.generate_report(
        {},
        [],
        [],
        [],
        days=1,
        slide_summary=summary,
    )

    assert 'Slide Publish Pipeline (ECON/MAT/FOR)' in report
    assert '`watch_slides.py` + `_slide_processed.json`' in report
    assert 'Report Type Status Matrix' in report
    assert 'Operational Attention Queue' in report
    assert 'Legacy FOR Tracker' in report
    assert 'historical/reproduction-only' in report
    assert 'db_reconcile_timestamp_synced' in report
    assert 'unresolved' in report


def test_legacy_failure_categorizer_still_reports_stale_elapsed_minutes(daily_report):
    processed = {
        'for-processing': {
            'slug': 'legacy-for',
            'name': 'legacy_for.pdf',
            'status': 'processing',
            'started_at': _iso(minutes_ago=45),
            'updated_at': _iso(),
        },
    }

    failures_by_category, active_failures, stale_processing, recent_successes = (
        daily_report.categorize_failures(processed, days=1)
    )

    assert active_failures == []
    assert recent_successes == []
    assert failures_by_category['processing'][0]['slug'] == 'legacy-for'
    assert stale_processing[0]['elapsed_minutes'] >= 30
