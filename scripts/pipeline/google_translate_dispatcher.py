from __future__ import annotations

import contextlib
import fcntl
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class GoogleTranslateDispatcherConfig:
    min_interval_seconds: float
    rate_limit_cooldown_seconds: int
    state_path: Path
    lock_path: Path
    progress_dir: Path
    language_order: tuple[str, ...]
    batch_max_chars: int
    batch_max_items: int
    single_text_max_chars: int
    policy_version: int = 3
    progress_unit: str = 'document_then_language_batch'
    document_order: str = 'sequential'


class GoogleTranslateDispatcher:
    def __init__(self, config: GoogleTranslateDispatcherConfig):
        self._config = config
        self._rate_limit_lock = threading.Lock()
        self._next_request_ts = 0.0

    def update_config(self, config: GoogleTranslateDispatcherConfig) -> None:
        self._config = config

    @property
    def next_request_ts(self) -> float:
        return self._next_request_ts

    @next_request_ts.setter
    def next_request_ts(self, value: float) -> None:
        self._next_request_ts = float(value or 0.0)

    def policy(self) -> Dict[str, Any]:
        return {
            'policy_version': self._config.policy_version,
            'progress_unit': self._config.progress_unit,
            'document_order': self._config.document_order,
            'language_order': list(self._config.language_order),
            'min_interval_seconds': self._config.min_interval_seconds,
            'batch_max_chars': self._config.batch_max_chars,
            'batch_max_items': self._config.batch_max_items,
            'single_text_max_chars': self._config.single_text_max_chars,
            'rate_limit_cooldown_seconds': self._config.rate_limit_cooldown_seconds,
            'state_path': str(self._config.state_path),
            'progress_dir': str(self._config.progress_dir),
        }

    def checkpoint_path(self, job_id: str) -> Path:
        return self._config.progress_dir / f'{job_id}.json'

    def load_rate_limit_state(self) -> Dict[str, Any]:
        try:
            if self._config.state_path.exists():
                return json.loads(self._config.state_path.read_text(encoding='utf-8'))
        except Exception:
            return {}
        return {}

    @contextlib.contextmanager
    def file_lock(self):
        self._config.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config.lock_path, 'a+', encoding='utf-8') as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield handle
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def save_rate_limit_state(
        self,
        next_request_ts: float,
        reason: str = '',
        *,
        scheduler: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = self.load_rate_limit_state()
        payload.update({
            'next_request_ts': next_request_ts,
            'reason': reason,
            'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'scheduler_policy': self.policy(),
        })
        if scheduler is not None:
            payload['scheduler'] = scheduler
        try:
            self._config.state_path.parent.mkdir(parents=True, exist_ok=True)
            self._config.state_path.write_text(
                json.dumps(payload, ensure_ascii=True, indent=2),
                encoding='utf-8',
            )
        except Exception:
            return

    def load_checkpoint(self, job_id: str) -> Dict[str, Any]:
        path = self.checkpoint_path(job_id)
        try:
            if path.exists():
                return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {}
        return {}

    def save_checkpoint(self, job_id: str, payload: Dict[str, Any]) -> Path:
        path = self.checkpoint_path(job_id)
        try:
            self._config.progress_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            return path
        return path

    def save_scheduler_status(
        self,
        *,
        next_request_ts: float,
        reason: str,
        status: str,
        job_id: str = '',
        target_lang: str = '',
        source_lang: str = '',
        completed_units: int = 0,
        total_units: int = 0,
        current_unit: str = '',
        checkpoint_path: str = '',
    ) -> None:
        scheduler = {
            'status': status,
            'job_id': job_id,
            'target_lang': target_lang,
            'source_lang': source_lang,
            'completed_units': completed_units,
            'total_units': total_units,
            'current_unit': current_unit,
            'checkpoint_path': checkpoint_path,
            'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        }
        self.save_rate_limit_state(next_request_ts, reason=reason, scheduler=scheduler)

    def reserve_slot(self, *, remaining_units: int = 0) -> Dict[str, float]:
        with self._rate_limit_lock:
            with self.file_lock():
                persisted_state = self.load_rate_limit_state()
                now = time.time()
                next_request_ts = max(
                    now,
                    self._next_request_ts,
                    float(persisted_state.get('next_request_ts', 0.0) or 0.0),
                )
                wait = max(next_request_ts - now, 0.0)
                reserved_next_request_ts = next_request_ts + self._config.min_interval_seconds
                self._next_request_ts = reserved_next_request_ts
                self.save_rate_limit_state(reserved_next_request_ts, reason='reserved_pre_request_slot')
        return {
            'scheduled_request_ts': next_request_ts,
            'reserved_next_request_ts': reserved_next_request_ts,
            'wait_seconds': wait,
            'remaining_units': float(remaining_units),
        }

    def apply_rate_limit_cooldown(self, *, wait_seconds: float, now: Optional[float] = None) -> float:
        with self._rate_limit_lock:
            with self.file_lock():
                persisted_state = self.load_rate_limit_state()
                next_request_ts = max(
                    self._next_request_ts,
                    float(persisted_state.get('next_request_ts', 0.0) or 0.0),
                    float(now if now is not None else time.time()) + wait_seconds,
                )
                self._next_request_ts = next_request_ts
                self.save_rate_limit_state(next_request_ts, reason='google_rate_limit')
        return next_request_ts
