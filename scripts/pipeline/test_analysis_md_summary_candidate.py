import importlib.util
import sys
import tempfile
from pathlib import Path


def load_candidate_pipeline():
    path = Path(__file__).resolve().parent / "analysis_md_summary_candidate.py"
    spec = importlib.util.spec_from_file_location("analysis_md_summary_candidate", path)
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
        self.filters.append((column, value))
        return self

    def limit(self, _value):
        return self

    def execute(self):
        if self.name == "pipeline_runs" and self.action == "insert":
            return FakeExecuteResult([{"id": "run-123"}])
        if self.name == "report_summary_jobs" and self.action == "select":
            key = next((value for column, value in self.filters if column == "idempotency_key"), None)
            row = self.supabase.existing_jobs.get(key)
            return FakeExecuteResult([row] if row else [])
        return FakeExecuteResult([])


class FakeSupabase:
    def __init__(self, existing_jobs=None):
        self.operations = []
        self.existing_jobs = existing_jobs or {}

    def table(self, name):
        return FakeTable(self, name)


def local_candidate(module, text=None):
    source_text = text or (
        "# Solana ECON\n\n"
        "Solana는 수수료 수요와 검증자 보상 구조가 결합되어 네트워크 활동 증가 시 "
        "토큰 가치 포착 가능성이 커지지만, 유동성 사이클 둔화는 지속성 리스크로 남는다.\n"
    )
    path = Path(tempfile.gettempdir()) / "fixture_solana_econ_v1_ko.md"
    path.write_text(source_text, encoding="utf-8")
    return module.load_local_candidate(str(path), report_type="econ", slug="solana")


def valid_payload():
    source_sentence = (
        "Solana는 수수료 수요와 검증자 보상 구조가 결합되어 네트워크 활동 증가 시 "
        "토큰 가치 포착 가능성이 커지지만, 유동성 사이클 둔화는 지속성 리스크로 남는다."
    )
    return {
        "schema_version": "analysis_md_summary_candidate.v1",
        "prompt_version": "analysis_md_summary_candidate.prompt.v1",
        "model": "test-model",
        "summary_by_lang": {
            "ko": "Solana는 수수료 수요와 검증자 보상 구조가 결합되어 가치 포착 가능성이 커진다.",
            "en": "Solana links fee demand with validator rewards, making value capture more plausible when network activity grows.",
            "fr": "Solana relie la demande de frais aux recompenses des validateurs, ce qui soutient la capture de valeur.",
            "es": "Solana une la demanda de comisiones con recompensas de validadores y mejora la captura de valor.",
            "de": "Solana verbindet Gebuehrennachfrage mit Validatorbelohnungen und staerkt so moegliche Werterfassung.",
            "ja": "Solanaは手数料需要とバリデータ報酬を結びつけ、活動増加時の価値獲得を強める。",
            "zh": "Solana将手续费需求与验证者奖励结合，网络活动增长时价值捕获能力增强。",
        },
        "marketing_by_lang": {
            "ko": "투자 관점에서는 수수료 수요 성장과 유동성 둔화 리스크를 함께 관찰해야 한다.",
            "en": "Investors should monitor fee demand growth together with liquidity cycle slowdown risk.",
            "fr": "Les investisseurs doivent suivre la demande de frais et le risque de ralentissement de liquidite.",
            "es": "Los inversores deben vigilar la demanda de comisiones y el riesgo de menor liquidez.",
            "de": "Investoren sollten Gebuehrennachfrage und das Risiko schwaecherer Liquiditaet beobachten.",
            "ja": "投資家は手数料需要の成長と流動性鈍化リスクをあわせて継続確認すべき局面にある。",
            "zh": "投资者应同时关注手续费需求增长和流动性周期放缓风险及其持续性变化趋势确认。",
        },
        "source_sentence_ids": [0],
        "source_sentences": [source_sentence],
        "confidence": 0.86,
    }


def test_source_identity_prefers_drive_revision_then_hash():
    module = load_candidate_pipeline()

    assert module.source_identity(drive_file_id="file-1", revision_id="rev-2", source_hash="hash") == "drive:file-1:rev-2"
    assert module.source_identity(drive_file_id="file-1", revision_id=None, source_hash="hash") == "sha256:hash"


def test_valid_payload_builds_candidate_patch_with_summary_quality_metadata():
    module = load_candidate_pipeline()
    result = module.process_candidate(local_candidate(module), llm_payload=valid_payload())

    assert result.status == "valid"
    assert result.validation_reasons == ()
    assert result.patch["card_data"]["source_md"]["source_identity"].startswith("sha256:")
    quality = result.patch["card_data"]["summary_quality"]
    assert quality["contract"] == "card_summary_v2"
    assert quality["model"] == "test-model"
    assert quality["validation_status"] == "candidate_valid"


def test_validation_fails_missing_languages_and_ungrounded_source_sentence():
    module = load_candidate_pipeline()
    payload = valid_payload()
    payload["summary_by_lang"] = {"ko": payload["summary_by_lang"]["ko"]}
    payload["source_sentences"] = ["This sentence is not present in the Markdown source and should fail grounding."]

    reasons = module.validate_llm_payload(payload, source=local_candidate(module).source, project={"slug": "solana"})

    assert "summary_by_lang_missing_languages:en,fr,es,de,ja,zh" in reasons
    assert "source_sentences.0.not_in_source" in reasons


def test_upsert_job_skips_existing_identity_without_force_and_updates_with_force():
    module = load_candidate_pipeline()
    result = module.process_candidate(local_candidate(module), llm_payload=valid_payload())
    key = module.summary_job_idempotency_key(
        report_code=result.candidate.source.db_report_type,
        report_slug=result.candidate.source.slug,
        locale=result.candidate.source.lang or "ko",
        drive_file_id=result.candidate.source.drive_file_id,
        revision_id=result.candidate.revision_id,
        source_hash=result.candidate.source_sha256,
        prompt_version=result.payload["prompt_version"],
        schema_version=result.payload["schema_version"],
    )
    sb = FakeSupabase(existing_jobs={key: {"id": "job-1", "idempotency_key": key, "source_identity": result.candidate.source_identity}})

    assert module.upsert_job(sb, result, force=False, dry_run=False) == {
        "status": "skipped_existing",
        "job_id": "job-1",
    }
    assert not any(op[0] == "report_summary_jobs" and op[1] == "update" for op in sb.operations)

    assert module.upsert_job(sb, result, force=True, dry_run=False) == {
        "status": "updated_existing",
        "job_id": "job-1",
    }
    update = next(op for op in sb.operations if op[0] == "report_summary_jobs" and op[1] == "update")
    assert update[2]["source_identity"] == result.candidate.source_identity
    assert update[2]["idempotency_key"] == key
    assert update[2]["status"] == "candidate_ready"


def test_upsert_job_allows_same_source_identity_with_new_prompt_version():
    module = load_candidate_pipeline()
    result = module.process_candidate(local_candidate(module), llm_payload=valid_payload())
    old_key = module.summary_job_idempotency_key(
        report_code=result.candidate.source.db_report_type,
        report_slug=result.candidate.source.slug,
        locale=result.candidate.source.lang or "ko",
        drive_file_id=result.candidate.source.drive_file_id,
        revision_id=result.candidate.revision_id,
        source_hash=result.candidate.source_sha256,
        prompt_version="previous.prompt",
        schema_version=result.payload["schema_version"],
    )
    sb = FakeSupabase(existing_jobs={
        old_key: {
            "id": "job-old",
            "idempotency_key": old_key,
            "source_identity": result.candidate.source_identity,
        }
    })

    assert module.upsert_job(sb, result, force=False, dry_run=False) == {
        "status": "inserted",
        "job_id": None,
    }
    inserts = [op for op in sb.operations if op[0] == "report_summary_jobs" and op[1] == "insert"]
    assert len(inserts) == 1
    assert inserts[0][2]["source_identity"] == result.candidate.source_identity
    assert inserts[0][2]["idempotency_key"] != old_key


def test_telemetry_uses_existing_supabase_column_contract(tmp_path):
    module = load_candidate_pipeline()
    result = module.process_candidate(local_candidate(module), llm_payload=valid_payload())
    sb = FakeSupabase()

    run_id = module.start_telemetry(sb, report_type="econ", dry_run=True, slug="solana")
    module.complete_telemetry(sb, run_id, results=[result], artifact_path=str(tmp_path / "artifact.json"))

    run_insert = next(op for op in sb.operations if op[0] == "pipeline_runs" and op[1] == "insert")
    assert run_insert[2]["report_type"] == "econ"
    assert run_insert[2]["project_slug"] == "solana"

    node_insert = next(op for op in sb.operations if op[0] == "pipeline_node_runs")
    assert "finished_at" in node_insert[2][0]
    assert "completed_at" not in node_insert[2][0]
    assert node_insert[2][0]["report_type"] == "econ"

    event_insert = next(op for op in sb.operations if op[0] == "pipeline_events")
    assert "details" in event_insert[2]
    assert "metadata" not in event_insert[2]
