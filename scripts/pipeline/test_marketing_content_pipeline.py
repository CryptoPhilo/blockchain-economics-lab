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
    monkeypatch.setattr(mcp, "MAT_SOURCE_FOLDER_ID", "drive-active-mat-folder")

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
    monkeypatch.setattr(mcp, "ECON_SOURCE_FOLDER_ID", "drive-active-econ-folder")

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


def test_score_drive_source_for_project_supports_flare_alias(mcp):
    project = {"slug": "flare-networks", "name": "Flare Network", "symbol": "FLR", "aliases": []}

    score = mcp.score_drive_source_for_project(
        "Flare의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md",
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


def test_derive_content_skips_forensic_source_provenance_for_card_summary(mcp):
    source = mcp.MarkdownSource(
        slug="ub",
        report_type="for",
        db_report_type="forensic",
        version=1,
        lang="ko",
        name="ub_for_v1_ko.md",
        text=(
            "# UB 포렌식 보고서\n\n"
            "분석 기준은 사용자가 제공한 KuCoin UB/USDT 15분봉 차트 이미지와, "
            "업로드된 분석 지침 파일의 포렌식 보고서 구조를 따랐습니다. "
            "UB는 단기 급등 이후 체결 강도가 약화되며 매수 추격 구간의 손실 위험이 커진 상태다. "
            "거래량은 가격 상승 구간에서 집중됐지만 후속 매수 유입은 제한적이어서 유동성 공백 리스크가 남아 있다. "
            "핵심 리스크는 고점 부근 변동성 확대와 되돌림 구간의 매도 압력이다."
        ),
    )

    content = mcp.derive_content(source, translate=False)

    assert content.summary_ko.startswith("UB는 단기 급등")
    assert "분석 기준" not in content.summary_ko
    assert "사용자가 제공한" not in content.summary_ko
    assert "업로드된 분석 지침" not in content.summary_ko
    assert "차트 이미지" not in content.summary_ko
    assert "포렌식 보고서 구조" not in content.summary_ko


def test_derive_card_copy_prefers_econ_identity_and_risk_judgment(mcp):
    source = mcp.MarkdownSource(
        slug="ethereum",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="ethereum_econ_v1_ko.md",
        text=(
            "# Ethereum 보고서\n\n"
            "본 보고서는 투자 조언이 아니며 가격 예측을 제공하지 않는다. "
            "Ethereum은 스마트컨트랙트와 롤업 생태계 수요를 ETH 수수료 소각 및 스테이킹 보상 구조로 연결하는 범용 결제 레이어다. "
            "핵심 리스크는 롤업 수수료 하락 이후 기본 레이어 수익성과 검증자 집중도 사이의 균형이다. "
            "분석 목적은 방법론을 설명하는 것이다."
        ),
    )

    card = mcp.derive_card_copy(source, project={"slug": "ethereum", "name": "Ethereum", "symbol": "ETH"})

    assert card.summary.startswith("Ethereum은 스마트컨트랙트")
    assert "본 보고서는" not in card.summary
    assert "분석 목적" not in card.summary
    assert card.quality_reasons == ()
    assert card.confidence >= 0.9


def test_derive_card_copy_prefers_maturity_stage_and_strength_weakness(mcp):
    source = mcp.MarkdownSource(
        slug="bitcoin",
        report_type="mat",
        db_report_type="maturity",
        version=1,
        lang="ko",
        name="bitcoin_mat_v1_ko.md",
        text=(
            "# Bitcoin MAT\n\n"
            "프로젝트 기본 정보: 항목 상세 내용 프로젝트 이름 Bitcoin. "
            "Bitcoin은 성숙 단계에 진입한 가치저장 네트워크로 높은 보안성과 브랜드 신뢰를 강점으로 가진다. "
            "약점은 수수료 시장의 장기 지속성과 채굴 보상 감소 이후의 보안 예산 불확실성이다."
        ),
    )

    card = mcp.derive_card_copy(source, project={"slug": "bitcoin", "name": "Bitcoin", "symbol": "BTC"})

    assert "성숙 단계" in card.summary
    assert "강점" in card.summary
    assert "약점" in card.summary
    assert "프로젝트 기본 정보" not in card.summary
    assert card.quality_reasons == ()


def test_card_summary_quality_gate_rejects_forbidden_and_table_fragments(mcp):
    source = mcp.MarkdownSource(
        slug="awe-network",
        report_type="mat",
        db_report_type="maturity",
        version=1,
        lang="ko",
        name="awe-network_mat_v1_ko.md",
        text="# AWE\n\n본문",
    )

    reasons = mcp.validate_card_summary(
        "본 보고서는 투자 조언이 아니며 | 항목 | 상세 내용 | 을 설명한다.",
        locale="ko",
        source=source,
        project={"slug": "awe-network", "name": "AWE Network", "symbol": "AWE"},
    )

    assert "forbidden_phrase" in reasons
    assert "table_or_list_fragment" in reasons


def test_card_summary_quality_gate_rejects_latex_formula_fragments(mcp):
    source = mcp.MarkdownSource(
        slug="hyperliquid",
        report_type="mat",
        db_report_type="maturity",
        version=1,
        lang="ko",
        name="hyperliquid_mat_v1_ko.md",
        text="# Hyperliquid\n\n본문",
    )

    reasons = mcp.validate_card_summary(
        r"$$ px i = round(px {i-1} \times 1.003) $$ 각 level 간격은 약 0.3% 전략은 최소 3초마다 조정된다.",
        locale="ko",
        source=source,
        project={"slug": "hyperliquid", "name": "Hyperliquid", "symbol": "HYPE"},
    )

    assert "raw_format_fragment" in reasons
    assert "table_or_list_fragment" in reasons


def test_card_summary_quality_gate_rejects_state_mapping_and_numbered_fragments(mcp):
    source = mcp.MarkdownSource(
        slug="bitcoin",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="bitcoin_econ_v1_ko.md",
        text="# Bitcoin\n\n본문",
    )

    state_reasons = mcp.validate_card_summary(
        "UTXO 온체인 state 매핑 : 존재. Bitcoin은 계정 잔고 대신 출력 집합을 사용한다.",
        locale="ko",
        source=source,
        project={"slug": "bitcoin", "name": "Bitcoin", "symbol": "BTC"},
    )
    numbered_reasons = mcp.validate_card_summary(
        "Bitcoin은 출력 집합으로 소유권을 표현한다. 경제 기능 : 이중지불 방지와 병렬 검증이다. 2.",
        locale="ko",
        source=source,
        project={"slug": "bitcoin", "name": "Bitcoin", "symbol": "BTC"},
    )
    ordinal_reasons = mcp.validate_card_summary(
        "Ethereum은 상태 전이 규칙으로 자원 비용을 계산한다. 둘째, gas 기반 자원 가격화 다.",
        locale="ko",
        source=source,
        project={"slug": "ethereum", "name": "Ethereum", "symbol": "ETH"},
    )

    assert "forbidden_phrase" in state_reasons
    assert "forbidden_phrase" in numbered_reasons
    assert "table_or_list_fragment" in numbered_reasons
    assert "forbidden_phrase" in ordinal_reasons
    assert "table_or_list_fragment" in ordinal_reasons


def test_dogecoin_bad_card_fragments_fail_semantic_gate(mcp):
    source = mcp.MarkdownSource(
        slug="dogecoin",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="dogecoin_econ_v1_ko.md",
        text="# Dogecoin ECON\n\n본문",
    )

    econ_reasons = mcp.validate_card_summary(
        "UTXO 잔액, 트랜잭션 출력, 블록 보상. 정의: 온체인 state 매핑 기능: 결제 처리.",
        locale="ko",
        source=source,
        project={"slug": "dogecoin", "name": "Dogecoin", "symbol": "DOGE"},
    )
    mat_reasons = mcp.validate_card_summary(
        "요청 템플릿의 예상 가격 항목은 투자 조언이 아니며 Dogecoin의 가격 예측을 제공하지 않는다.",
        locale="ko",
        source=source,
        project={"slug": "dogecoin", "name": "Dogecoin", "symbol": "DOGE"},
    )

    assert "forbidden_phrase" in econ_reasons
    assert "table_or_list_fragment" in econ_reasons
    assert "forbidden_phrase" in mat_reasons


def test_dogecoin_good_card_copy_keeps_actual_investment_insight(mcp):
    source = mcp.MarkdownSource(
        slug="dogecoin",
        report_type="mat",
        db_report_type="maturity",
        version=1,
        lang="ko",
        name="dogecoin_mat_v1_ko.md",
        text=(
            "# Dogecoin MAT\n\n"
            "Dogecoin은 결제 네트워크와 밈 프리미엄을 결합한 오래된 공개 블록체인이다. "
            "Dogecoin은 브랜드 인지도와 거래소 유동성을 강점으로 유지하지만, 무제한 발행 구조와 개발 지속성은 실사용 전환을 확인해야 하는 핵심 리스크다. "
            "요청 템플릿의 예상 가격 항목은 내부 작성 흔적이다."
        ),
    )

    content = mcp.derive_content(
        source,
        translate=False,
        project={"slug": "dogecoin", "name": "Dogecoin", "symbol": "DOGE"},
    )

    assert "밈 프리미엄" in content.summary_ko
    assert "무제한 발행" in content.summary_ko
    assert "개발 지속성" in content.summary_ko
    assert "요청 템플릿" not in content.summary_ko
    assert "예상 가격" not in " ".join(content.marketing_by_lang.values())
    assert content.marketing_by_lang["ko"].startswith("Dogecoin은 브랜드 인지도")


def test_card_summary_quality_gate_detects_locale_script_mismatch(mcp):
    source = mcp.MarkdownSource(
        slug="starknet",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="starknet_econ_v1_ko.md",
        text="# Starknet\n\n본문",
    )

    reasons = mcp.validate_card_summary(
        "Starknet is a rollup ecosystem with sequencer decentralization risk.",
        locale="ko",
        source=source,
        project={"slug": "starknet", "name": "Starknet", "symbol": "STRK"},
    )

    assert "locale_script_mismatch" in reasons


def test_derive_card_copy_skips_citation_prefix_and_incomplete_fragments(mcp):
    source = mcp.MarkdownSource(
        slug="ethereum",
        report_type="econ",
        db_report_type="econ",
        version=4,
        lang="ko",
        name="ethereum_econ_v4_ko.md",
        text=(
            "# Ethereum ECON\n\n"
            "(Bitpanda) Ethereum의 수수료 시장은 롤업 확장 이후 L1 정산 수요와 ETH 소각 구조를 함께 반영한다. "
            "다만 L2 확장이 L1 실행 수수료를 낮추면, L1 수익은 execution gas보다 "
            "Ethereum의 핵심 리스크는 롤업 데이터 수요가 약해질 때 ETH 소각과 검증자 보상 간 균형이 흔들릴 수 있다는 점이다."
        ),
    )

    card = mcp.derive_card_copy(source, project={"slug": "ethereum", "name": "Ethereum", "symbol": "ETH"})

    assert "Ethereum의 수수료 시장" in card.summary
    assert not card.summary.startswith("(")
    assert not card.summary.endswith("보다")
    assert "execution gas보다" not in card.summary
    assert card.quality_reasons == ()


def test_card_summary_quality_gate_rejects_incomplete_trailing_phrase(mcp):
    source = mcp.MarkdownSource(
        slug="ethereum",
        report_type="econ",
        db_report_type="econ",
        version=4,
        lang="ko",
        name="ethereum_econ_v4_ko.md",
        text="# Ethereum\n\n본문",
    )

    reasons = mcp.validate_card_summary(
        "Ethereum의 L1 수익은 execution gas보다",
        locale="ko",
        source=source,
        project={"slug": "ethereum", "name": "Ethereum", "symbol": "ETH"},
    )

    assert "sentence_fragment" in reasons


def test_card_summary_quality_gate_counts_cited_sentence_boundaries(mcp):
    source = mcp.MarkdownSource(
        slug="ethereum",
        report_type="econ",
        db_report_type="econ",
        version=4,
        lang="ko",
        name="ethereum_econ_v4_ko.md",
        text="# Ethereum\n\n본문",
    )

    reasons = mcp.validate_card_summary(
        "Ethereum은 정산 계층으로 작동한다.[1][2] ETH는 수수료와 보상에 쓰인다.[3] 추가 한계도 있다.",
        locale="ko",
        source=source,
        project={"slug": "ethereum", "name": "Ethereum", "symbol": "ETH"},
    )

    assert "too_many_sentences" in reasons


def test_derive_content_omits_invalid_investment_view_formula(mcp):
    source = mcp.MarkdownSource(
        slug="hyperliquid",
        report_type="mat",
        db_report_type="maturity",
        version=1,
        lang="ko",
        name="hyperliquid_mat_v1_ko.md",
        text=(
            "# Hyperliquid MAT\n\n"
            "Hyperliquid는 자체 L1과 온체인 주문장 구조를 결합한 파생상품 거래 인프라로, 높은 실행 속도와 커뮤니티 중심 운영을 강점으로 가진다. "
            r"투자 관점: $$ px i = round(px {i-1} \times 1.003) $$ 각 level 간격은 약 0.3% 전략은 최소 3초마다 조정된다."
        ),
    )

    content = mcp.derive_content(source, translate=False, project={"slug": "hyperliquid", "name": "Hyperliquid", "symbol": "HYPE"})

    assert content.summary_ko.startswith("Hyperliquid는 자체 L1")
    assert content.marketing_by_lang == {}


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


def test_matching_row_includes_website_visible_in_review_status(mcp):
    source = mcp.MarkdownSource(
        slug="awe-network",
        report_type="econ",
        db_report_type="econ",
        version=1,
        lang="ko",
        name="awe-network_econ_v1_ko.md",
        text="AWE Network 본문",
    )
    sb = FakeSupabase({
        "tracked_projects": [{"id": "p1", "slug": "awe-network"}],
        "project_reports": [{
            "id": "r1",
            "project_id": "p1",
            "report_type": "econ",
            "version": 1,
            "language": "ko",
            "status": "in_review",
            "slide_html_urls_by_lang": {"ko": "https://example.com/awe-ko.html"},
        }],
    })

    assert mcp.find_matching_korean_slide_row(sb, source)["id"] == "r1"


def test_backfill_drive_source_selection_includes_in_review_and_keeps_slug_scope(monkeypatch, mcp):
    spec = importlib.util.spec_from_file_location(
        "backfill_card_summaries",
        Path(__file__).with_name("backfill_card_summaries.py"),
    )
    backfill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backfill)

    sb = FakeSupabase({
        "tracked_projects": [
            {"id": "p-awe", "slug": "awe-network", "name": "AWE Network", "symbol": "AWE"},
            {"id": "p-btc", "slug": "bitcoin", "name": "Bitcoin", "symbol": "BTC"},
        ],
        "project_reports": [
            {
                "id": "r-awe",
                "project_id": "p-awe",
                "report_type": "econ",
                "version": 1,
                "language": "ko",
                "status": "in_review",
                "slide_html_urls_by_lang": {"ko": "https://example.com/awe-ko.html"},
                "updated_at": "2026-06-01T00:00:00Z",
            },
            {
                "id": "r-btc",
                "project_id": "p-btc",
                "report_type": "econ",
                "version": 1,
                "language": "ko",
                "status": "in_review",
                "slide_html_urls_by_lang": {"ko": "https://example.com/btc-ko.html"},
                "updated_at": "2026-06-01T00:00:00Z",
            },
        ],
    })
    calls = []

    def fake_find_drive_source_for_project(project, *, report_type, version, source_scope="legacy"):
        calls.append((project["slug"], report_type, version, source_scope))
        return SimpleNamespace(slug=project["slug"], report_type=report_type, version=version)

    monkeypatch.setattr(backfill, "_get_supabase_client", lambda: sb)
    monkeypatch.setattr(backfill, "find_drive_source_for_project", fake_find_drive_source_for_project)

    sources = backfill.load_drive_sources_for_slugs(
        ["awe-network"],
        report_type="econ",
        version=None,
        limit=None,
    )

    assert [source.slug for source in sources] == ["awe-network"]
    assert calls == [("awe-network", "econ", 1, "legacy")]


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
        text=(
            "# Bitcoin\n\n"
            "Bitcoin은 가치저장 수요와 수수료 시장을 결합한 성숙한 결제 네트워크다. "
            "핵심 리스크는 채굴 보상 감소 이후 보안 예산과 유동성 지속성을 함께 점검해야 한다는 점이다."
        ),
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
