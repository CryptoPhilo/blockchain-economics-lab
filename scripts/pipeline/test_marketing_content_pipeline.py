"""Tests for BCE-1791 marketing and summary content pipeline."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="module")
def mcp():
    spec = importlib.util.spec_from_file_location(
        "marketing_content_pipeline",
        Path(__file__).with_name("marketing_content_pipeline.py"),
    )
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_korean_markdown_source_filename(mcp):
    parsed = mcp._parse_markdown_name("bitcoin_econ_v2_ko.md")

    assert parsed == ("bitcoin", "econ", 2, "ko")


def test_score_drive_source_for_project_prefers_exact_natural_mat_name(mcp):
    project = {"slug": "bitcoin", "name": "Bitcoin", "symbol": "BTC", "aliases": []}

    bitcoin = mcp.score_drive_source_for_project(
        "Bitcoin의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2008-2026.md",
        project,
    )
    bitcoin_cash = mcp.score_drive_source_for_project(
        "Bitcoin Cash의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017-2026.md",
        project,
    )

    assert bitcoin == 100
    assert bitcoin > bitcoin_cash


def test_find_drive_source_for_project_supports_natural_mat_filename(monkeypatch, mcp):
    project = {"slug": "tether", "name": "Tether", "symbol": "USDT", "aliases": []}

    monkeypatch.setattr(
        mcp,
        "_list_drive_markdown_sources",
        lambda _service, _folder_id: [{
            "id": "drive-source-1",
            "name": "Tether의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2014 - 2026.md",
            "modifiedTime": "2026-05-05T08:30:56.000Z",
        }],
    )
    monkeypatch.setattr(mcp, "_download_drive_text", lambda _service, _file_id: "# Tether\n\n본문")

    source = mcp.find_drive_source_for_project(
        project,
        report_type="mat",
        version=1,
        service=object(),
    )

    assert source is not None
    assert source.slug == "tether"
    assert source.report_type == "mat"
    assert source.drive_file_id == "drive-source-1"


def test_find_drive_source_for_project_uses_econ_folder(monkeypatch, mcp):
    project = {"slug": "pax-gold", "name": "PAX Gold", "symbol": "PAXG", "aliases": []}
    captured = []

    def fake_list_sources(_service, folder_id):
        captured.append(folder_id)
        if folder_id != mcp.ECON_SOURCE_FOLDER_ID:
            return []
        return [{
            "id": "drive-econ-1",
            "name": "PAXG 크립토이코노미 분석 보고서.md",
            "modifiedTime": "2026-05-07T08:30:56.000Z",
        }]

    monkeypatch.setattr(mcp, "_list_drive_markdown_sources", fake_list_sources)
    monkeypatch.setattr(mcp, "_download_drive_text", lambda _service, _file_id: "# PAXG\n\n본문")

    source = mcp.find_drive_source_for_project(
        project,
        report_type="econ",
        version=1,
        service=object(),
    )

    assert mcp.ECON_SOURCE_FOLDER_ID in captured
    assert source is not None
    assert source.report_type == "econ"
    assert source.drive_file_id == "drive-econ-1"


def test_find_drive_source_for_project_uses_for_folder(monkeypatch, mcp):
    project = {"slug": "bitcoin", "name": "Bitcoin", "symbol": "BTC", "aliases": []}
    captured = []
    monkeypatch.setattr(mcp, "FOR_SOURCE_FOLDER_ID", "drive-for-folder")

    def fake_list_sources(_service, folder_id):
        captured.append(folder_id)
        if folder_id != mcp.FOR_SOURCE_FOLDER_ID:
            return []
        return [{
            "id": "drive-for-1",
            "name": "bitcoin_for_v1_ko.md",
            "modifiedTime": "2026-05-07T08:30:56.000Z",
        }]

    monkeypatch.setattr(mcp, "_list_drive_markdown_sources", fake_list_sources)
    monkeypatch.setattr(mcp, "_download_drive_text", lambda _service, _file_id: "# Bitcoin FOR\n\n본문")

    source = mcp.find_drive_source_for_project(
        project,
        report_type="for",
        version=1,
        service=object(),
    )

    assert mcp.FOR_SOURCE_FOLDER_ID in captured
    assert source is not None
    assert source.report_type == "for"
    assert source.drive_file_id == "drive-for-1"


def test_score_drive_source_for_project_supports_registered_korean_alias(mcp):
    project = {"slug": "polkadot", "name": "Polkadot", "symbol": "DOT", "aliases": []}

    score = mcp.score_drive_source_for_project(
        "폴카닷 크립토 이코노미 보고서.md",
        project,
    )

    assert score >= 90


def test_score_drive_source_for_project_supports_venice_ai_alias(mcp):
    project = {"slug": "venice-token", "name": "Venice Token", "symbol": "VVV", "aliases": []}

    econ_score = mcp.score_drive_source_for_project(
        "Venice.ai 크립토 이코노미 분석 보고서.md",
        project,
    )
    mat_score = mcp.score_drive_source_for_project(
        "Venice.ai의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024-2026.md",
        project,
    )

    assert econ_score >= 90
    assert mat_score >= 90


def test_score_drive_source_for_project_supports_polygon_alias_for_matic(mcp):
    project = {"slug": "matic-network", "name": "Polygon", "symbol": "POL", "aliases": []}

    score = mcp.score_drive_source_for_project(
        "폴리곤 네트워크(Polygon 2.0) 크립토 이코노미 심층 분석 보고서.md",
        project,
    )

    assert score >= 90


def test_score_drive_source_for_project_prefers_world_alias_possessive(mcp):
    project = {"slug": "worldcoin", "name": "Worldcoin", "symbol": "WLD", "aliases": []}

    world = mcp.score_drive_source_for_project(
        "World의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2019-2026.md",
        project,
    )
    world_liberty = mcp.score_drive_source_for_project(
        "World Liberty Financial의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024-2026.md",
        project,
    )

    assert world == 100
    assert world > world_liberty


def test_derive_content_limits_korean_copy_to_100_words(mcp):
    sentence = " ".join(f"단어{i}" for i in range(140)) + "."
    source = mcp.MarkdownSource(
        slug="bitcoin",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="bitcoin_econ_v1_ko.md",
        text=f"# Bitcoin 보고서\n\n{sentence}",
    )

    content = mcp.derive_content(source, translate=False)

    assert mcp._word_count(content.summary_ko) <= 100
    assert mcp._word_count(content.marketing_ko) <= 100
    assert content.summary_by_lang == {"ko": content.summary_ko}


def test_translate_text_uses_google_free_endpoint_first(monkeypatch, mcp):
    calls = []

    def fake_request_json(url, *, method="GET", payload=None):
        calls.append((url, method, payload))
        return [[["English summary", "한국어 요약", None, None]]]

    monkeypatch.setattr(mcp, "_request_json", fake_request_json)
    monkeypatch.setattr(
        mcp,
        "_translate_with_google_cloud",
        lambda *_args, **_kwargs: pytest.fail("paid Google fallback should not run when free succeeds"),
    )

    translated = mcp._translate_text("한국어 요약", "en")

    assert translated == "English summary"
    assert calls[0][1:] == ("GET", None)
    assert calls[0][0].startswith("https://translate.googleapis.com/translate_a/single?")
    assert "client=gtx" in calls[0][0]
    assert "sl=ko" in calls[0][0]
    assert "tl=en" in calls[0][0]


def test_translate_text_uses_google_cloud_when_free_endpoint_fails(monkeypatch, mcp):
    monkeypatch.setattr(
        mcp,
        "_request_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("free endpoint unavailable")),
    )
    monkeypatch.setattr(mcp, "_translate_with_google_cloud", lambda text, target: f"paid {target}: {text}")

    assert mcp._translate_text("한국어 요약", "en") == "paid en: 한국어 요약"


def test_translate_texts_raises_when_free_endpoint_fails(monkeypatch, mcp):
    monkeypatch.setattr(
        mcp,
        "_request_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("free endpoint unavailable")),
    )
    monkeypatch.setattr(
        mcp,
        "_translate_with_google_cloud",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("paid endpoint unavailable")),
    )

    with pytest.raises(RuntimeError, match="Google translation failed"):
        mcp._translate_texts({"summary": "한국어 요약"}, ["en"])

    assert not hasattr(mcp, "_get_translate_client")


def test_derive_content_skips_report_boilerplate_for_card_summary(mcp):
    source = mcp.MarkdownSource(
        slug="the-open-network",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="the-open-network_econ_v1_ko.md",
        text=(
            "# TON 크립토이코노미 분석 보고서\n\n"
            "## 1. 개요 및 개념 정의\n\n"
            "본 보고서는 '크립토 이코노미 설계 방법론'과 '분석 보고서 작성 방법'에 의거하여 "
            "The Open Network (TON)의 경제 구조를 기술적, 경제적 관점에서 심층 분석한다. "
            "TON은 텔레그램 메신저와의 강력한 통합을 기반으로 수퍼앱 생태계를 지향하는 레이어 1 블록체인이다. "
            "본 분석은 TON의 백서, 기술 문서, 온체인 데이터를 종합한다. "
            "TON의 핵심 리스크는 텔레그램 의존성과 검증자 집중도에 있다."
        ),
    )

    content = mcp.derive_content(source, translate=False)

    assert content.summary_ko.startswith("TON은 텔레그램")
    assert "개요 및 개념 정의" not in content.summary_ko
    assert "크립토 이코노미 설계 방법론" not in content.summary_ko
    assert "본 보고서는" not in content.summary_ko


def test_derive_content_skips_project_metadata_lists(mcp):
    source = mcp.MarkdownSource(
        slug="tether",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="tether_econ_v1_ko.md",
        text=(
            "# Tether 보고서\n\n"
            "프로젝트 이름: Tether (초기 명칭: Realcoin) 1 메인넷: 멀티체인 배포 "
            "(Ethereum, Tron, Solana, Avalanche, Omni[Legacy], TON 등 14개 이상의 블록체인 지원) 1 "
            "프로젝트 분류: 법정화폐 담보형 스테이블코인, RWA 토큰화 플랫폼, 디지털 결제 인프라 4 "
            "1.2 개념 정의 목록 [크립토 이코노미 설계 방법론 기준]\n\n"
            "테더는 달러 표시 부채와 준비자산을 연결해 거래소 유동성과 온체인 결제 수요를 동시에 흡수하는 스테이블코인 네트워크다. "
            "핵심 리스크는 준비자산 투명성, 발행사 거버넌스, 멀티체인 운영 리스크에 집중된다."
        ),
    )

    content = mcp.derive_content(source, translate=False)

    assert content.summary_ko.startswith("테더는 달러 표시 부채")
    assert "프로젝트 이름" not in content.summary_ko
    assert "메인넷" not in content.summary_ko
    assert "프로젝트 분류" not in content.summary_ko
    assert "개념 정의 목록" not in content.summary_ko


def test_derive_content_strips_numbered_basic_info_section_from_summary(mcp):
    source = mcp.MarkdownSource(
        slug="bitcoin",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="bitcoin_econ_v1_ko.md",
        text=(
            "# Bitcoin 보고서\n\n"
            "## 1.1 프로젝트 기본 정보 및 분류\n\n"
            "항목 상세 내용 프로젝트 이름 비트코인 (Bitcoin) "
            "메인넷 비트코인 블록체인 (Bitcoin Blockchain) "
            "프로젝트 분류 단일 가치 제공 메인넷 (결제 및 가치 저장 수단) "
            "상태 성숙 단계 (Maturity Phase) 진입 "
            "비트코인은 크립토 경제 시스템의 분류상 단일 가치 제공 메인넷으로 가치 저장과 결제를 중심으로 작동한다. "
            "핵심 리스크는 채굴 인센티브와 수수료 시장의 장기 지속성이다."
        ),
    )

    content = mcp.derive_content(source, translate=False)

    assert content.summary_ko.startswith("비트코인은")
    assert "1.1" not in content.summary_ko
    assert "프로젝트 기본 정보" not in content.summary_ko
    assert "프로젝트 이름" not in content.summary_ko
    assert "메인넷 비트코인 블록체인" not in content.summary_ko
    assert "프로젝트 분류" not in content.summary_ko
    assert "상태 성숙 단계" not in content.summary_ko


def test_strip_markdown_removes_operational_notes_and_table_dividers(mcp):
    cleaned = mcp._strip_markdown(
        "# 제목\n"
        "NOTE: 복구 작업 중 남긴 운영 메모입니다.\n"
        "| 항목 | 점수 |\n"
        "| :---- | ----: |\n"
        "| 위험 | 7 |\n"
        "\\- 실제 본문입니다."
    )

    assert "NOTE" not in cleaned
    assert ":----" not in cleaned
    assert "----:" not in cleaned
    assert "실제 본문입니다" in cleaned


def test_strip_markdown_removes_table_rows_from_summary_source(mcp):
    cleaned = mcp._strip_markdown(
        "| 개념 명칭 | 온체인 State 매핑 여부 | 설명 |\n"
        "| :---- | :---- | :---- |\n"
        "| Masterchain | Yes | Config Contract: -1:555 |\n"
        "TON은 텔레그램 통합을 기반으로 수퍼앱 생태계를 지향한다."
    )

    assert "Masterchain" not in cleaned
    assert "Config Contract" not in cleaned
    assert "TON은 텔레그램" in cleaned


def test_derive_content_skips_section_heading_fragments(mcp):
    source = mcp.MarkdownSource(
        slug="the-open-network",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="the-open-network_econ_v1_ko.md",
        text=(
            "# TON 보고서\n\n"
            "## 2. 가치 시스템 분석 (Value System Analysis)\n\n"
            "TON의 가치 시스템은 텔레그램이라는 거대 소셜 플랫폼의 백엔드 인프라 역할을 수행하는 데 초점을 맞추고 있다. "
            "2.1 가치 시스템 구조 및 서사 TON이 제공하려는 핵심 가치는 수십억 사용자에게 도달 가능한 고성능 상태 머신이다."
        ),
    )

    content = mcp.derive_content(source, translate=False)

    assert content.summary_ko.startswith("TON의 가치 시스템")
    assert "가치 시스템 분석" not in content.summary_ko
    assert "2.1 가치 시스템 구조" not in content.summary_ko


def test_translate_texts_uses_google_free_endpoint(monkeypatch, mcp):
    calls = []

    def fake_request_json(url, *, method="GET", payload=None):
        calls.append({"url": url, "method": method, "payload": payload})
        return [[["English ", None, None, None], ["summary", None, None, None]]]

    monkeypatch.setattr(mcp, "_request_json", fake_request_json)
    monkeypatch.setattr(
        mcp,
        "_translate_with_google_cloud",
        lambda *_args, **_kwargs: pytest.fail("paid Google fallback should not run when free succeeds"),
    )

    translated = mcp._translate_texts({"summary": "한국어 요약"}, ["en"])

    assert translated["summary"]["en"] == "English summary"
    assert calls[0]["method"] == "GET"
    assert calls[0]["payload"] is None
    assert calls[0]["url"].startswith("https://translate.googleapis.com/translate_a/single?")
    assert "client=gtx" in calls[0]["url"]
    assert "sl=ko" in calls[0]["url"]
    assert "tl=en" in calls[0]["url"]


def test_translate_texts_uses_google_cloud_when_free_endpoint_fails(monkeypatch, mcp):
    monkeypatch.setattr(
        mcp,
        "_request_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("free endpoint unavailable")),
    )
    monkeypatch.setattr(mcp, "_translate_with_google_cloud", lambda text, target: f"{target} paid translation")

    translated = mcp._translate_texts({"summary": "한국어 요약"}, ["en"])

    assert translated["summary"]["en"] == "en paid translation"


def test_translate_does_not_require_google_cloud_client(monkeypatch, mcp):
    def fake_request_json(_url, *, method="GET", payload=None):
        return [[["English summary", None, None, None]]]

    monkeypatch.setattr(mcp, "_request_json", fake_request_json)
    monkeypatch.setattr(
        mcp,
        "_translate_with_google_cloud",
        lambda *_args, **_kwargs: pytest.fail("paid Google fallback should not run when free succeeds"),
    )

    translated = mcp._translate_texts({"summary": "한국어 요약"}, ["en"])

    assert translated["summary"]["en"] == "English summary"
    assert not hasattr(mcp, "_get_translate_client")


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self

    def in_(self, field, values):
        self.rows = [row for row in self.rows if row.get(field) in values]
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(list(self.tables[name]))


def test_matching_row_requires_korean_slide_url(mcp):
    source = mcp.MarkdownSource(
        slug="bitcoin",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="bitcoin_econ_v1_ko.md",
        text="본문",
    )
    sb = FakeSupabase({
        "tracked_projects": [{"id": "p1", "slug": "bitcoin"}],
        "project_reports": [{
            "id": "r1",
            "project_id": "p1",
            "report_type": "econ",
            "version": 1,
            "language": "ko",
            "status": "published",
            "slide_html_urls_by_lang": {"en": "https://example.com/en.html"},
        }],
    })

    assert mcp.find_matching_korean_slide_row(sb, source) is None

    sb.tables["project_reports"][0]["slide_html_urls_by_lang"]["ko"] = "https://example.com/ko.html"
    assert mcp.find_matching_korean_slide_row(sb, source)["id"] == "r1"


def test_load_local_sources_refuses_generated_output_directory(tmp_path, monkeypatch, capsys, mcp):
    output_dir = tmp_path / "pipeline" / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "solana_econ_v1_ko.md").write_text("# Solana\n\n본문", encoding="utf-8")
    monkeypatch.setattr(mcp, "BLOCKED_LOCAL_SOURCE_DIRS", (output_dir,))

    sources = mcp.load_local_sources([str(output_dir)])

    assert sources == []
    assert "Refusing legacy/generated local source path" in capsys.readouterr().err


def test_persist_skips_source_when_markdown_project_name_mismatches_slug(monkeypatch, mcp):
    source = mcp.MarkdownSource(
        slug="solana",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="solana_econ_v1_ko.md",
        text=(
            "# 솔라나 크립토이코노미 분석 보고서\n\n"
            "| 항목 | 내용 |\n"
            "| :---- | :---- |\n"
            "| **프로젝트 이름** | 주피터 (Jupiter Aggregator) |\n"
            "주피터는 솔라나 생태계의 DEX 애그리게이터다."
        ),
    )
    sb = FakeSupabase({
        "tracked_projects": [{"id": "p1", "slug": "solana", "name": "Solana", "symbol": "SOL"}],
        "project_reports": [{
            "id": "r1",
            "project_id": "p1",
            "report_type": "econ",
            "version": 1,
            "language": "ko",
            "status": "published",
            "slide_html_urls_by_lang": {"ko": "https://example.com/ko.html"},
        }],
    })

    monkeypatch.setattr(mcp, "_get_supabase_client", lambda: sb)
    monkeypatch.setattr(mcp, "persist_content", lambda *_args, **_kwargs: pytest.fail("mismatch wrote data"))

    stats = mcp.run_pipeline([source], persist=True, translate=False, dry_run=False)

    assert stats["seen"] == 1
    assert stats["matched"] == 0
    assert stats["updated"] == 0
    assert stats["skipped"] == 1
    assert stats["items"][0]["status"] == "skipped_subject_mismatch"
    assert stats["items"][0]["project_report_id"] == "r1"


def test_patch_contains_summary_and_marketing_provenance(mcp):
    source = mcp.MarkdownSource(
        slug="bitcoin",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="bitcoin_econ_v1_ko.md",
        text="본문",
        drive_file_id="drive-md-1",
    )
    content = mcp.DerivedContent(
        title="Bitcoin",
        summary_ko="한국어 요약",
        marketing_ko="한국어 마케팅",
        summary_by_lang={"ko": "한국어 요약", "en": "English summary"},
        marketing_by_lang={"ko": "한국어 마케팅", "en": "English marketing"},
    )

    patch = mcp.build_project_report_patch(
        source,
        content,
        archived_drive_file={"id": "archive-1", "webViewLink": "https://drive.example/archive-1"},
    )

    assert patch["card_summary_ko"] == "한국어 요약"
    assert patch["card_summary_en"] == "English summary"
    assert patch["marketing_content_by_lang"]["en"] == "English marketing"
    assert patch["summary_source_md_file_id"] == "drive-md-1"
    assert patch["card_data"]["source_md"]["archived_drive_file_id"] == "archive-1"


def test_persist_dry_run_matches_without_update(monkeypatch, mcp):
    source = mcp.MarkdownSource(
        slug="bitcoin",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="bitcoin_econ_v1_ko.md",
        text="# Bitcoin\n\n시장은 성장 기회와 리스크를 함께 보여준다. 투자자는 유동성과 평가 변화를 점검해야 한다.",
    )
    sb = FakeSupabase({
        "tracked_projects": [{"id": "p1", "slug": "bitcoin"}],
        "project_reports": [{
            "id": "r1",
            "project_id": "p1",
            "report_type": "econ",
            "version": 1,
            "language": "ko",
            "status": "published",
            "slide_html_urls_by_lang": {"ko": "https://example.com/ko.html"},
        }],
    })

    monkeypatch.setattr(mcp, "_get_supabase_client", lambda: sb)
    monkeypatch.setattr(mcp, "persist_content", lambda *_args, **_kwargs: pytest.fail("dry-run wrote data"))

    stats = mcp.run_pipeline([source], persist=True, translate=False, dry_run=True)

    assert stats["seen"] == 1
    assert stats["matched"] == 1
    assert stats["updated"] == 0
    assert stats["items"][0]["status"] == "matched_dry_run"
    assert stats["items"][0]["project_report_id"] == "r1"


def test_filter_sources_supports_slug_report_type_version_and_limit(mcp):
    sources = [
        mcp.MarkdownSource("bitcoin", "econ", "econ", 1, "ko", "bitcoin_econ_v1_ko.md", "본문"),
        mcp.MarkdownSource("bitcoin", "mat", "maturity", 1, "ko", "bitcoin_mat_v1_ko.md", "본문"),
        mcp.MarkdownSource("ethereum", "econ", "econ", 2, "ko", "ethereum_econ_v2_ko.md", "본문"),
    ]

    selected = mcp._filter_sources(
        sources,
        slugs=["bitcoin"],
        report_type="econ",
        version=1,
        limit=1,
    )

    assert [source.name for source in selected] == ["bitcoin_econ_v1_ko.md"]
