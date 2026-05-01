import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline_state
from pipeline_state import MAX_RETRIES, STALE_PROCESSING_MINUTES, PipelineState


def _build_state(existing: dict | None) -> PipelineState:
    client = MagicMock()
    state = PipelineState('econ', client=client)
    state.get_run_by_source = MagicMock(return_value=existing)
    return state


def _stale_started_at() -> str:
    return (
        datetime.now(timezone.utc)
        - timedelta(minutes=STALE_PROCESSING_MINUTES + 5)
    ).isoformat()


def _fresh_started_at() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShouldProcessTests(unittest.TestCase):
    def test_no_existing_run_proceeds(self):
        state = _build_state(None)
        should, existing = state.should_process('file-1')
        self.assertTrue(should)
        self.assertIsNone(existing)

    def test_terminal_status_blocks_reprocess(self):
        for status in pipeline_state.TERMINAL_STATUSES:
            with self.subTest(status=status):
                state = _build_state({'status': status, 'retry_count': 0})
                should, _ = state.should_process('file-1')
                self.assertFalse(should)

    def test_dry_run_always_proceeds(self):
        state = _build_state({'status': 'dry_run', 'retry_count': 99})
        should, _ = state.should_process('file-1')
        self.assertTrue(should)

    def test_fresh_processing_does_not_reprocess(self):
        state = _build_state({
            'status': 'processing',
            'retry_count': 0,
            'started_at': _fresh_started_at(),
        })
        should, _ = state.should_process('file-1')
        self.assertFalse(should)

    def test_stale_processing_under_cap_reprocesses(self):
        state = _build_state({
            'status': 'processing',
            'retry_count': MAX_RETRIES - 1,
            'started_at': _stale_started_at(),
        })
        should, _ = state.should_process('file-1')
        self.assertTrue(should)

    def test_stale_processing_at_cap_blocks_reprocess(self):
        # Regression for BCE-1051: stale 'processing' rows previously bypassed
        # the retry cap, allowing unbounded retries.
        state = _build_state({
            'status': 'processing',
            'retry_count': MAX_RETRIES,
            'started_at': _stale_started_at(),
        })
        should, _ = state.should_process('file-1')
        self.assertFalse(should)

    def test_stale_processing_above_cap_blocks_reprocess(self):
        state = _build_state({
            'status': 'processing',
            'retry_count': MAX_RETRIES + 4,
            'started_at': _stale_started_at(),
        })
        should, _ = state.should_process('file-1')
        self.assertFalse(should)

    def test_retriable_status_under_cap_reprocesses(self):
        for status in pipeline_state.RETRIABLE_STATUSES:
            with self.subTest(status=status):
                state = _build_state({'status': status, 'retry_count': MAX_RETRIES - 1})
                should, _ = state.should_process('file-1')
                self.assertTrue(should)

    def test_retriable_status_at_cap_blocks_reprocess(self):
        for status in pipeline_state.RETRIABLE_STATUSES:
            with self.subTest(status=status):
                state = _build_state({'status': status, 'retry_count': MAX_RETRIES})
                should, _ = state.should_process('file-1')
                self.assertFalse(should)

    def test_force_overrides_retry_cap(self):
        state = _build_state({
            'status': 'processing',
            'retry_count': MAX_RETRIES + 10,
            'started_at': _stale_started_at(),
        })
        should, _ = state.should_process('file-1', force=True)
        self.assertTrue(should)


if __name__ == '__main__':
    unittest.main()
