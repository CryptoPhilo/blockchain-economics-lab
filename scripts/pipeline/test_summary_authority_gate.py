import importlib.util
import sys
from pathlib import Path

import pytest


def load_gate():
    path = Path(__file__).resolve().parent / "summary_authority_gate.py"
    spec = importlib.util.spec_from_file_location("summary_authority_gate", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, supabase, name):
        self.supabase = supabase
        self.name = name
        self.action = None
        self.payload = None
        self.filters = []

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        self.supabase.operations.append((self.name, self.action, payload))
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        self.supabase.operations.append((self.name, self.action, payload))
        return self

    def select(self, payload):
        self.action = "select"
        self.payload = payload
        self.supabase.operations.append((self.name, self.action, payload))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, tuple(values)))
        return self

    def limit(self, _value):
        return self

    def order(self, column, desc=False):
        self.filters.append(("order", column, desc))
        return self

    def execute(self):
        if self.name == "report_summary_promotion_locks" and self.action == "insert":
            key = (
                self.payload["project_slug"],
                self.payload["report_type"],
                self.payload["locale"],
            )
            if key in self.supabase.active_locks:
                raise RuntimeError("duplicate lock")
            self.supabase.active_locks.add(key)
            return FakeExecuteResult([self.payload])
        if self.name == "report_summary_promotion_locks" and self.action == "update":
            job_id = _filter_value(self.filters, "job_id")
            job = self.supabase.jobs.get(job_id)
            if job:
                self.supabase.active_locks.discard((job["project_slug"], job["report_type"], job.get("locale", "ko")))
            return FakeExecuteResult([])
        if self.name == "report_summary_jobs" and self.action == "select":
            job_id = _filter_value(self.filters, "id")
            key = _filter_value(self.filters, "idempotency_key")
            if job_id:
                row = self.supabase.jobs.get(job_id)
                return FakeExecuteResult([row] if row else [])
            if key:
                row = next((job for job in self.supabase.jobs.values() if job.get("idempotency_key") == key), None)
                return FakeExecuteResult([row] if row else [])
        if self.name == "report_summary_jobs" and self.action == "update":
            job_id = _filter_value(self.filters, "id")
            self.supabase.jobs[job_id].update(self.payload)
            return FakeExecuteResult([self.supabase.jobs[job_id]])
        if self.name == "tracked_projects" and self.action == "select":
            slug = _filter_value(self.filters, "slug")
            row = self.supabase.projects.get(slug)
            return FakeExecuteResult([row] if row else [])
        if self.name == "project_reports" and self.action == "select":
            project_id = _filter_value(self.filters, "project_id")
            report_type = _filter_value(self.filters, "report_type")
            language = _filter_value(self.filters, "language")
            version = _filter_value(self.filters, "version")
            rows = [
                row
                for row in self.supabase.reports.values()
                if row["project_id"] == project_id
                and row["report_type"] == report_type
                and row["language"] == language
                and row["status"] in set(_filter_value(self.filters, "status") or ())
                and (version is None or row["version"] == version)
            ]
            for kind, column, desc in self.filters:
                if kind == "order":
                    rows = sorted(rows, key=lambda row: row[column], reverse=desc)
            return FakeExecuteResult(rows[:1])
        if self.name == "project_reports" and self.action == "update":
            report_id = _filter_value(self.filters, "id")
            self.supabase.reports[report_id].update(self.payload)
            return FakeExecuteResult([self.supabase.reports[report_id]])
        return FakeExecuteResult([])


class FakeRpc:
    def __init__(self, supabase, name, params):
        self.supabase = supabase
        self.name = name
        self.params = params

    def execute(self):
        self.supabase.operations.append(("rpc", self.name, self.params))
        if self.name != "promote_report_summary_job":
            return FakeExecuteResult([])
        if self.supabase.fail_rpc:
            raise RuntimeError(self.supabase.fail_rpc)
        job_id = self.params["p_job_id"]
        job = dict(self.supabase.jobs[job_id])
        key = (job["project_slug"], job["report_type"], job.get("locale", "ko"))
        if key in self.supabase.active_locks:
            raise RuntimeError("active promotion lock exists")
        project_id = self.supabase.projects[job["project_slug"]]["id"]
        visible_statuses = {"published", "coming_soon", "in_review"}
        candidate_version = job["candidate_patch"].get("card_data", {}).get("source_md", {}).get("version")
        locale = job.get("locale", "ko")
        locale_rows = [
            row
            for row in self.supabase.reports.values()
            if row["project_id"] == project_id
            and row["report_type"] == job["report_type"]
            and row["language"] == locale
            and row["status"] in visible_statuses
        ]
        target = next((row for row in locale_rows if row["version"] == candidate_version), None)
        if target is None:
            target = sorted(locale_rows, key=lambda row: row["version"], reverse=True)[0]
        report_patch = {
            "card_summary_ko": job["candidate_patch"].get("card_summary_ko"),
            "card_summary_en": job["candidate_patch"].get("card_summary_en"),
            "marketing_content_by_lang": job["candidate_patch"]["marketing_content_by_lang"],
        }
        job_patch = {
            "authority_state": "promoted",
            "promotion_actor": self.params["p_actor"],
            "promotion_decision": "promote",
            "promotion_decision_reason": self.params["p_reason"],
            "promoted_project_report_id": target["id"],
            "promotion_audit": {"updated_project_report_count": 0},
        }
        if self.supabase.fail_after_report_patch:
            raise RuntimeError("injected transaction failure after project report patch")
        updated = 0
        latest_visible_ids_by_language = {}
        for report in sorted(self.supabase.reports.values(), key=lambda row: row["version"], reverse=True):
            if (
                report["project_id"] == project_id
                and report["report_type"] == job["report_type"]
                and report["status"] in visible_statuses
            ):
                latest_visible_ids_by_language.setdefault(report["language"], report["id"])
        for report in self.supabase.reports.values():
            if report["id"] in set(latest_visible_ids_by_language.values()):
                report.update({
                    **report_patch,
                    "card_data": {
                        **report.get("card_data", {}),
                        **job["candidate_patch"]["card_data"],
                        "summary_authority": {
                            "mode": self.params["p_authority_mode"],
                            "job_id": job_id,
                            "source_identity": job["source_identity"],
                            "idempotency_key": job["idempotency_key"],
                        },
                    },
                })
                updated += 1
        job_patch["promotion_audit"]["updated_project_report_count"] = updated
        self.supabase.jobs[job_id].update(job_patch)
        self.supabase.operations.append(("project_reports", "update", report_patch))
        self.supabase.operations.append(("report_summary_jobs", "update", job_patch))
        self.supabase.operations.append(("pipeline_events", "insert", {"event_type": "summary_authority_gate.promoted"}))
        return FakeExecuteResult([{
            "job_id": job_id,
            "project_report_id": target["id"],
            "updated_project_report_count": updated,
            "authority_state": "promoted",
        }])


def _filter_value(filters, column):
    for kind, filter_column, value in filters:
        if kind in {"eq", "in"} and filter_column == column:
            return value
    return None


class FakeSupabase:
    def __init__(self, job):
        self.operations = []
        self.jobs = {job["id"]: dict(job)}
        self.projects = {"solana": {"id": "project-1", "slug": "solana"}}
        self.reports = {
            "report-1": {
                "id": "report-1",
                "project_id": "project-1",
                "report_type": "econ",
                "version": 1,
                "language": "ko",
                "status": "published",
                "card_data": {"legacy": True},
            },
            "report-2": {
                "id": "report-2",
                "project_id": "project-1",
                "report_type": "econ",
                "version": 1,
                "language": "en",
                "status": "published",
                "card_data": {"legacy_en": True},
            }
        }
        self.active_locks = set()
        self.fail_rpc = None
        self.fail_after_report_patch = False

    def table(self, name):
        return FakeTable(self, name)

    def rpc(self, name, params):
        return FakeRpc(self, name, params)


def valid_job(**overrides):
    job = {
        "id": "job-1",
        "source_identity": "drive:file-1:rev-1",
        "source_drive_file_id": "file-1",
        "source_revision_id": "rev-1",
        "source_sha256": "hash-1",
        "source_name": "solana_econ_v1_ko.md",
        "project_slug": "solana",
        "report_type": "econ",
        "report_code": "econ",
        "locale": "ko",
        "idempotency_key": "econ:solana:ko:file-1:rev-1:prompt:schema",
        "summarizer_model": "test-model",
        "prompt_version": "prompt",
        "schema_version": "schema",
        "validation_status": "valid",
        "validation_errors": [],
        "authority_state": "validation_passed",
        "authority_mode": "llm_candidate",
        "validator_result": {"validation_status": "valid"},
        "candidate_patch": {
            "card_summary_ko": "검증된 요약",
            "card_summary_en": "Validated summary",
            "marketing_content_by_lang": {"ko": "투자 관점", "en": "Investment view"},
            "card_data": {
                "source_md": {"version": 1},
                "summary_by_lang": {"ko": "검증된 요약", "en": "Validated summary"},
                "summary_quality": {"contract": "card_summary_v2"},
            },
        },
        "promotion_audit": {},
    }
    job.update(overrides)
    return job


def test_transition_rules_allow_expected_path_and_reject_invalid():
    module = load_gate()

    module.validate_transition("validation_passed", "promotion_pending")
    module.validate_transition("promotion_pending", "promoted")

    with pytest.raises(module.GateError):
        module.validate_transition("validation_failed", "promoted")


def test_idempotency_key_matches_contract_and_lookup_is_noop():
    module = load_gate()
    job = valid_job(idempotency_key=None)
    expected = "econ:solana:ko:file-1:rev-1:prompt:schema"

    assert module.build_idempotency_key(job) == expected

    sb = FakeSupabase(valid_job(idempotency_key=expected))
    assert module.find_job_by_idempotency_key(sb, expected)["id"] == "job-1"


def test_legacy_and_candidate_modes_keep_legacy_active_summary():
    module = load_gate()
    sb = FakeSupabase(valid_job())

    decision = module.promote_job(sb, sb.jobs["job-1"], actor="agent", authority_mode="llm_candidate", dry_run=False)

    assert decision.action == "fallback"
    assert not any(op[0] == "project_reports" and op[1] == "update" for op in sb.operations)
    assert sb.jobs["job-1"]["authority_state"] == "fallback_script"


def test_validation_failed_candidate_never_promotes_to_project_reports():
    module = load_gate()
    sb = FakeSupabase(valid_job(authority_state="validation_failed", validation_status="invalid"))

    decision = module.promote_job(sb, sb.jobs["job-1"], actor="agent", authority_mode="llm_active", dry_run=False)

    assert decision.action == "blocked"
    assert not any(op[0] == "project_reports" and op[1] == "update" for op in sb.operations)
    assert sb.jobs["job-1"]["authority_state"] == "validation_failed"


def test_llm_active_valid_candidate_promotes_language_siblings_with_lock():
    module = load_gate()
    sb = FakeSupabase(valid_job())

    decision = module.promote_job(sb, sb.jobs["job-1"], actor="agent", authority_mode="llm_active", dry_run=False)

    assert decision.action == "promote"
    assert decision.project_report_id == "report-1"
    assert sb.jobs["job-1"]["authority_state"] == "promoted"
    assert sb.reports["report-1"]["card_summary_ko"] == "검증된 요약"
    assert sb.reports["report-1"]["card_data"]["legacy"] is True
    assert sb.reports["report-1"]["card_data"]["summary_authority"]["job_id"] == "job-1"
    assert sb.reports["report-2"]["card_summary_en"] == "Validated summary"
    assert sb.reports["report-2"]["card_data"]["legacy_en"] is True
    assert sb.reports["report-2"]["card_data"]["summary_by_lang"]["en"] == "Validated summary"
    assert sb.jobs["job-1"]["promotion_audit"]["updated_project_report_count"] == 2
    rpc_calls = [op for op in sb.operations if op[0] == "rpc" and op[1] == "promote_report_summary_job"]
    assert len(rpc_calls) == 1
    report_updates = [op for op in sb.operations if op[0] == "project_reports" and op[1] == "update"]
    assert len(report_updates) == 1


def test_dry_run_uses_latest_visible_target_when_candidate_version_is_stale():
    module = load_gate()
    sb = FakeSupabase(valid_job())
    sb.reports["report-1"]["status"] = "cancelled"
    sb.reports["report-2"]["status"] = "cancelled"
    sb.reports["report-3"] = {
        "id": "report-3",
        "project_id": "project-1",
        "report_type": "econ",
        "version": 3,
        "language": "ko",
        "status": "published",
        "card_data": {"latest": True},
    }

    decision = module.promote_job(sb, sb.jobs["job-1"], actor="agent", authority_mode="llm_active", dry_run=True)

    assert decision.action == "promote"
    assert decision.project_report_id == "report-3"
    assert decision.reason == "dry-run promotion would call atomic DB RPC"


def test_write_promotion_updates_latest_visible_language_siblings_under_version_skew():
    module = load_gate()
    sb = FakeSupabase(valid_job())
    sb.reports["report-2"]["status"] = "coming_soon"
    sb.reports["report-3"] = {
        "id": "report-3",
        "project_id": "project-1",
        "report_type": "econ",
        "version": 2,
        "language": "en",
        "status": "published",
        "card_data": {"latest_en": True},
        "card_summary_en": "Stale latest English summary",
    }

    decision = module.promote_job(sb, sb.jobs["job-1"], actor="agent", authority_mode="llm_active", dry_run=False)

    assert decision.action == "promote"
    assert decision.project_report_id == "report-1"
    assert sb.reports["report-1"]["card_summary_ko"] == "검증된 요약"
    assert "card_summary_en" not in sb.reports["report-2"]
    assert sb.reports["report-3"]["card_summary_en"] == "Validated summary"
    assert sb.reports["report-3"]["card_data"]["latest_en"] is True
    assert sb.reports["report-3"]["card_data"]["summary_authority"]["job_id"] == "job-1"
    assert sb.jobs["job-1"]["promotion_audit"]["updated_project_report_count"] == 2


def test_duplicate_promotion_lock_blocks_concurrent_active_summary_update():
    module = load_gate()
    job = valid_job()
    sb = FakeSupabase(job)
    sb.active_locks.add(("solana", "econ", "ko"))

    decision = module.promote_job(sb, sb.jobs["job-1"], actor="agent", authority_mode="llm_active", dry_run=False)

    assert decision.action == "blocked"
    assert decision.reason == "active promotion lock exists"
    assert not any(op[0] == "project_reports" and op[1] == "update" for op in sb.operations)


def test_atomic_promotion_failure_does_not_leave_pending_or_project_update():
    module = load_gate()
    sb = FakeSupabase(valid_job())
    sb.fail_after_report_patch = True

    with pytest.raises(RuntimeError, match="injected transaction failure"):
        module.promote_job(sb, sb.jobs["job-1"], actor="agent", authority_mode="llm_active", dry_run=False)

    assert sb.jobs["job-1"]["authority_state"] == "validation_passed"
    assert "card_summary_ko" not in sb.reports["report-1"]
    assert not any(op[0] == "report_summary_jobs" and op[1] == "update" for op in sb.operations)
