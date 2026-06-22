import importlib.util
import json
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
        if self.name == "tracked_projects" and self.action == "select":
            slug = next((value for column, value in self.filters if column == "slug"), None)
            row = self.supabase.tracked_projects.get(slug)
            return FakeExecuteResult([row] if row else [])
        if self.name == "report_summary_jobs" and self.action == "select":
            key = next((value for column, value in self.filters if column == "idempotency_key"), None)
            row = self.supabase.existing_jobs.get(key)
            return FakeExecuteResult([row] if row else [])
        return FakeExecuteResult([])


class FakeSupabase:
    def __init__(self, existing_jobs=None, tracked_projects=None):
        self.operations = []
        self.existing_jobs = existing_jobs or {}
        self.tracked_projects = (
            {"solana": {"id": "project-solana", "slug": "solana"}}
            if tracked_projects is None
            else tracked_projects
        )

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
    result = module.process_candidate(local_candidate(module), agent_payload=valid_payload())

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
    result = module.process_candidate(local_candidate(module), agent_payload=valid_payload())
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
    result = module.process_candidate(local_candidate(module), agent_payload=valid_payload())
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


def test_upsert_job_rejects_untracked_project_slug_without_writing():
    module = load_candidate_pipeline()
    result = module.process_candidate(local_candidate(module), agent_payload=valid_payload())
    sb = FakeSupabase(tracked_projects={})

    assert module.upsert_job(sb, result, force=True, dry_run=False) == {
        "status": "project_slug_not_tracked",
        "job_id": None,
    }
    assert not any(op[0] == "report_summary_jobs" and op[1] in {"insert", "update"} for op in sb.operations)


def test_telemetry_uses_existing_supabase_column_contract(tmp_path):
    module = load_candidate_pipeline()
    result = module.process_candidate(local_candidate(module), agent_payload=valid_payload())
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


def test_require_agent_output_fails_without_paperclip_agent_json(monkeypatch):
    module = load_candidate_pipeline()
    monkeypatch.setattr(module, "get_supabase_client", lambda: None)

    assert module.main([
        "--type",
        "econ",
        "--slug",
        "solana",
        "--source-path",
        str(Path(tempfile.gettempdir()) / "missing_agent_output_fixture.md"),
        "--require-agent-output",
        "--dry-run",
    ]) == 2


def test_agent_output_json_file_is_used_without_remote_llm(tmp_path):
    module = load_candidate_pipeline()
    candidate = local_candidate(module)
    payload_path = tmp_path / "paperclip-agent-output.json"
    payload_path.write_text(json.dumps(valid_payload(), ensure_ascii=False), encoding="utf-8")

    payload = module.load_llm_payload_from_file(str(payload_path))
    result = module.process_candidate(candidate, agent_payload=payload)

    assert result.status == "valid"
    assert result.payload["model"] == "test-model"
    assert result.patch["card_data"]["summary_quality"]["model"] == "test-model"


def test_slug_filtered_drive_scan_excludes_unrelated_natural_language_names(monkeypatch):
    module = load_candidate_pipeline()
    monkeypatch.setattr(module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        module,
        "fetch_project",
        lambda _sb, _slug, **_kwargs: {"slug": "re-protocol", "name": "Re", "symbol": "RE"},
    )
    monkeypatch.setattr(module, "_source_folder_ids_for_report_type", lambda *args, **kwargs: ["folder"])
    monkeypatch.setattr(
        module,
        "_list_drive_markdown_sources_with_revision",
        lambda _service, _folder: [
            {
                "id": "blur-file",
                "name": "BLUR 시장 무결성 및 심층 포렌식 리스크 보고서.md",
                "headRevisionId": "blur-rev",
                "modifiedTime": "2026-06-19T04:01:00.000Z",
            },
            {
                "id": "re-file",
                "name": "RE 시장 무결성 및 심층 포렌식 리스크 보고서.md",
                "headRevisionId": "re-rev",
                "modifiedTime": "2026-06-19T03:57:12.000Z",
            },
        ],
    )
    monkeypatch.setattr(module, "_download_drive_text", lambda _service, file_id: f"# source for {file_id}\n")

    candidates = module.list_drive_candidates(
        report_type="for",
        slug="re-protocol",
        source_scope="all",
        service=object(),
    )

    assert [candidate.source.drive_file_id for candidate in candidates] == ["re-file"]
    assert candidates[0].source.slug == "re-protocol"


def test_drive_scan_prioritizes_latest_changed_candidate_for_slug(monkeypatch):
    module = load_candidate_pipeline()
    monkeypatch.setattr(module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        module,
        "fetch_project",
        lambda _sb, _slug, **_kwargs: {"slug": "banana-for-scale", "name": "Banana For Scale", "symbol": "BANANAS31"},
    )
    monkeypatch.setattr(module, "_source_folder_ids_for_report_type", lambda *args, **kwargs: ["folder"])
    monkeypatch.setattr(
        module,
        "_list_drive_markdown_sources_with_revision",
        lambda _service, _folder: [
            {
                "id": "older-high-score",
                "name": "Banana For Scale 크립토이코노미 설계 분석 보고서.md",
                "headRevisionId": "older-rev",
                "modifiedTime": "2026-06-14T09:00:00.000Z",
            },
            {
                "id": "newer-lower-score",
                "name": "banana-for-scale(BANANAS31)_v1_MAT.md",
                "headRevisionId": "newer-rev",
                "modifiedTime": "2026-06-14T10:32:18.113Z",
            },
        ],
    )
    monkeypatch.setattr(module, "_download_drive_text", lambda _service, file_id: f"# source for {file_id}\n")

    candidates = module.list_drive_candidates(
        report_type="mat",
        slug="banana-for-scale",
        source_scope="all",
        service=object(),
    )

    assert [candidate.source.drive_file_id for candidate in candidates] == ["newer-lower-score", "older-high-score"]


def test_indexed_candidate_selection_builds_candidate_from_safe_cached_text(monkeypatch, tmp_path):
    module = load_candidate_pipeline()
    text_path = tmp_path / "solana.txt"
    text_path.write_text(
        "# Solana ECON\n\n"
        "Solana는 수수료 수요와 검증자 보상 구조가 결합되어 네트워크 활동 증가 시 "
        "토큰 가치 포착 가능성이 커지지만, 유동성 사이클 둔화는 지속성 리스크로 남는다.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module,
        "select_index_candidates",
        lambda *args, **kwargs: [
            {
                "file": {
                    "file_id": "drive-1",
                    "name": "Solana ECON.md",
                    "modified_time": "2026-06-21T00:00:00Z",
                    "source_root": "analysis2",
                    "metadata": {"webViewLink": "https://drive.example/drive-1"},
                },
                "content": {
                    "file_id": "drive-1",
                    "revision_id": "rev-1",
                    "text_sha256": "hash-1",
                    "extracted_text_path": str(text_path),
                },
                "mapping": {
                    "file_id": "drive-1",
                    "revision_id": "rev-1",
                    "project_slug": "solana",
                },
            }
        ],
    )

    candidates = module.list_indexed_drive_candidates(
        sb=FakeSupabase(),
        report_type="econ",
        slug="solana",
        limit=1,
    )

    assert len(candidates) == 1
    assert candidates[0].source_identity == "drive:drive-1:rev-1"
    assert candidates[0].source_folder == "analysis2/ECON"
    assert candidates[0].source.text.startswith("# Solana ECON")
