import importlib.util
from pathlib import Path

import yaml


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "forensic-rapid-change-scan.yml"
)


def load_bridge():
    path = Path(__file__).resolve().parent / "sudden_movers_card_anchor.py"
    spec = importlib.util.spec_from_file_location("sudden_movers_card_anchor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def workflow_step(name):
    workflow = load_workflow()
    steps = workflow["jobs"]["scan"]["steps"]
    return next(step for step in steps if step.get("name") == name)


def candidate(slug="solana", observed_at="2026-05-09T01:30:00Z"):
    return {
        "symbol": "SOL",
        "name": "Solana",
        "slug": slug,
        "rank": 3,
        "price": 200.0,
        "market_average_change_24h": 2.047619,
        "token_change_24h": 16.0,
        "relative_deviation": 13.952381,
        "signed_relative_deviation": 13.952381,
        "direction": "up",
        "observed_at": observed_at,
        "source": {
            "name": "coinmarketcap",
            "source_timestamp": "2026-05-09T01:00:00.000Z",
            "cmc_id": 5426,
        },
    }


def scan_payload(*candidates):
    return {
        "status": "ok",
        "observed_at": "2026-05-09T01:30:00Z",
        "threshold_pct_points": 10.0,
        "warnings": [],
        "candidates": list(candidates),
    }


def test_workflow_validates_telemetry_secrets_before_scan():
    step = workflow_step("Validate required secrets")

    assert step["env"]["CMC_API_KEY"] == "${{ secrets.COINMARKETCAP_API_KEY }}"
    assert step["env"]["SUPABASE_URL"] == "${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}"
    assert step["env"]["SUPABASE_SERVICE_KEY"] == "${{ secrets.SUPABASE_SERVICE_KEY }}"
    assert "for name in CMC_API_KEY SUPABASE_URL SUPABASE_SERVICE_KEY" in step["run"]


def test_workflow_passes_supabase_telemetry_env_to_bridge():
    step = workflow_step("Run default-off sudden movers bridge")

    assert step["env"]["CMC_API_KEY"] == "${{ secrets.COINMARKETCAP_API_KEY }}"
    assert step["env"]["SUPABASE_URL"] == "${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}"
    assert step["env"]["NEXT_PUBLIC_SUPABASE_URL"] == "${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}"
    assert step["env"]["SUPABASE_SERVICE_KEY"] == "${{ secrets.SUPABASE_SERVICE_KEY }}"
    assert step["env"]["FORENSIC_RAPID_CHANGE_SCAN_ARTIFACT_PATH"] == (
        "scripts/pipeline/output/sudden_movers_card_anchor_${{ github.run_id }}.json"
    )


class FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, supabase, name):
        self.supabase = supabase
        self.name = name

    def insert(self, payload):
        self.supabase.operations.append((self.name, "insert", payload))
        self.payload = payload
        return self

    def execute(self):
        if self.name == "pipeline_runs":
            return FakeExecuteResult([{"id": "run-123"}])
        return FakeExecuteResult([])


class FakeSupabase:
    def __init__(self):
        self.operations = []

    def table(self, name):
        return FakeTable(self, name)


def test_feature_flag_off_preserves_current_pipeline_behavior(tmp_path):
    bridge = load_bridge()

    result = bridge.run_card_anchor_bridge(
        enabled=False,
        dry_run=True,
        state_path=tmp_path / "state.json",
        output_path=tmp_path / "anchors.jsonl",
        scanner=lambda **_: scan_payload(candidate()),
    )

    assert result["status"] == "disabled"
    assert result["anchors"] == []
    assert not (tmp_path / "state.json").exists()
    assert not (tmp_path / "anchors.jsonl").exists()


def test_enabled_dry_run_emits_card_anchor_contract_without_writes(tmp_path):
    bridge = load_bridge()

    result = bridge.run_card_anchor_bridge(
        enabled=True,
        dry_run=True,
        state_path=tmp_path / "state.json",
        output_path=tmp_path / "anchors.jsonl",
        scanner=lambda **_: scan_payload(candidate()),
    )

    assert result["status"] == "ok"
    assert result["dry_run"] is True
    assert result["anchors"][0]["anchor_id"] == "solana:2026-05-09T01Z"
    assert result["anchors"][0]["target"] == {
        "surface": "forensic_card_generation",
        "report_type": "forensic",
        "legacy_generator": "_legacy/pipeline/gen_for_card.py",
    }
    assert result["anchors"][0]["trigger_data"]["price_change_24h"] == 16.0
    assert result["anchors"][0]["card_data_patch"]["source_node"] == "candidate.for.sudden_movers_scanner"
    assert result["handoff_contracts"][0]["registration"]["tables"]["project_reports"]["status"] == "coming_soon"
    assert result["handoff_contracts"][0]["human_source_request"]["draft_name"] == "solana_for_v1_en.md"
    assert result["handoff_contracts"][0]["slide_intake"]["args"] == ["--type", "for", "--slug", "solana"]
    assert not (tmp_path / "state.json").exists()
    assert not (tmp_path / "anchors.jsonl").exists()


def test_write_mode_dedupes_slug_and_observation_window(tmp_path):
    bridge = load_bridge()
    state_path = tmp_path / "state.json"
    output_path = tmp_path / "anchors.jsonl"

    first = bridge.run_card_anchor_bridge(
        enabled=True,
        dry_run=False,
        state_path=state_path,
        output_path=output_path,
        scanner=lambda **_: scan_payload(candidate()),
    )
    second = bridge.run_card_anchor_bridge(
        enabled=True,
        dry_run=False,
        state_path=state_path,
        output_path=output_path,
        scanner=lambda **_: scan_payload(candidate()),
    )

    assert [anchor["anchor_id"] for anchor in first["anchors"]] == ["solana:2026-05-09T01Z"]
    assert [contract["source"]["anchor_id"] for contract in first["handoff_contracts"]] == ["solana:2026-05-09T01Z"]
    assert second["anchors"] == []
    assert second["handoff_contracts"] == []
    assert [anchor["anchor_id"] for anchor in second["duplicates"]] == ["solana:2026-05-09T01Z"]
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 1


def test_handoff_contract_preserves_legacy_registration_and_intake_identity():
    bridge = load_bridge()

    contract = bridge.candidate_to_intake_handoff_contract(candidate(slug="near"))

    assert contract["activation"] == {
        "feature_flag": "ENABLE_SUDDEN_MOVERS_CARD_ANCHOR",
        "default": "off",
        "write_mode": "requires --write and feature flag",
    }
    assert contract["registration"]["legacy_contract"] == "_legacy/pipeline/scan_forensic.py::register_coming_soon"
    assert contract["registration"]["tables"]["forensic_triggers"]["slug"] == "near"
    assert contract["registration"]["tables"]["forensic_triggers"]["status"] == "detected"
    assert contract["registration"]["tables"]["project_reports"]["report_type"] == "forensic"
    assert contract["registration"]["tables"]["project_reports"]["status"] == "coming_soon"
    assert contract["registration"]["tables"]["project_reports"]["trigger_data"]["handoff_contract"] == {
        "slug": "near",
        "rtype": "for",
        "db_report_type": "forensic",
        "source_draft_name": "near_for_v1_en.md",
        "slide_pdf_hint": "Slide/for/near/near_for_v1_en.pdf",
    }
    assert contract["human_source_request"]["required_slug"] == "near"
    assert contract["slide_intake"]["expected_source_draft_name"] == "near_for_v1_en.md"


def test_rapid_change_scan_metrics_capture_success_dedupe_and_registration():
    bridge = load_bridge()

    result = {
        "status": "ok",
        "enabled": True,
        "dry_run": False,
        "anchors": [{"anchor_id": "fresh"}],
        "duplicates": [{"anchor_id": "dupe"}],
        "handoff_contracts": [{"source": {"anchor_id": "fresh"}}],
        "scanner": {
            "observed_at": "2026-05-09T01:30:00Z",
            "threshold_pct_points": 10.0,
            "warnings": [],
            "candidate_count": 2,
        },
    }

    assert bridge.build_rapid_change_scan_metrics(result) == {
        "scan_attempted": 1,
        "successful_scans": 1,
        "failed_scans": 0,
        "skipped_scans": 0,
        "candidate_count": 2,
        "fresh_candidates": 1,
        "deduped_candidates": 1,
        "registered_count": 1,
        "email_required_count": 0,
        "email_sent_count": 0,
        "email_failed_count": 0,
    }


def test_rapid_change_scan_telemetry_writes_run_nodes_and_event(monkeypatch):
    bridge = load_bridge()
    fake_supabase = FakeSupabase()
    telemetry = bridge.RapidChangeScanTelemetry()
    telemetry.enabled = True
    telemetry._supabase = fake_supabase
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "77")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Forensic Rapid Change Scan")
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    telemetry.record(
        {
            "status": "ok",
            "enabled": True,
            "dry_run": True,
            "anchors": [bridge.candidate_to_card_anchor(candidate())],
            "duplicates": [],
            "handoff_contracts": [bridge.candidate_to_intake_handoff_contract(candidate())],
            "scanner": {
                "observed_at": "2026-05-09T01:30:00Z",
                "threshold_pct_points": 10.0,
                "warnings": [],
                "candidate_count": 1,
            },
        }
    )

    run_insert = fake_supabase.operations[0]
    node_insert = fake_supabase.operations[1]
    event_insert = fake_supabase.operations[2]

    assert run_insert[0:2] == ("pipeline_runs", "insert")
    assert run_insert[2]["pipeline_name"] == "forensic-rapid-change-scan"
    assert run_insert[2]["paperclip_pipeline_name"] == "Forensic Rapid Change Scan"
    assert run_insert[2]["report_type"] == "for"
    assert run_insert[2]["status"] == "dry_run"
    assert run_insert[2]["project_slug"] == "forensic-rapid-change-scan"
    assert run_insert[2]["metrics"]["candidate_count"] == 1
    assert run_insert[2]["metrics"]["registered_count"] == 0
    assert run_insert[2]["artifact_path"] == "scripts/pipeline/output/sudden_movers_card_anchor_12345.json"
    assert run_insert[2]["github_sha"] == "abc123"

    assert node_insert[0:2] == ("pipeline_node_runs", "insert")
    assert [row["node_key"] for row in node_insert[2]] == [
        "candidate_scan",
        "card_anchor_bridge",
        "scan_result_artifact",
    ]
    assert all(row["pipeline_run_id"] == "run-123" for row in node_insert[2])

    assert event_insert[0:2] == ("pipeline_events", "insert")
    assert event_insert[2]["event_type"] == "forensic_rapid_change_scan.completed"
    assert event_insert[2]["details"]["emailNotificationResult"]["status"] == "not_applicable"
