#!/usr/bin/env python3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gen_report_card


def test_generate_econ_report_card_sets_rating():
    with tempfile.TemporaryDirectory() as tmpdir:
        ko_path = Path(tmpdir) / "bitcoin_econ_v1_ko.md"
        en_path = Path(tmpdir) / "bitcoin_econ_v1_en.md"
        ko_path.write_text("## Executive Summary\n요약입니다.\n\n## 10.4 Overall Rating\n**Overall Rating: A**\n", encoding="utf-8")
        en_path.write_text("## Executive Summary\nEnglish summary.\n\n**Overall Rating: A**\n", encoding="utf-8")

        result = gen_report_card.generate_econ_report_card(
            ko_md_path=str(ko_path),
            en_md_path=str(en_path),
            project_name="Bitcoin",
            symbol="BTC",
            slug="bitcoin",
            output_dir=tmpdir,
        )

    assert result["card_data"]["rating"] == "A"
    assert result["card_data"]["report_type"] == "econ"


def test_generate_mat_report_card_sets_maturity_score():
    with tempfile.TemporaryDirectory() as tmpdir:
        ko_path = Path(tmpdir) / "hyperliquid_mat_v1_ko.md"
        en_path = Path(tmpdir) / "hyperliquid_mat_v1_en.md"
        ko_path.write_text("## Executive Summary\n요약입니다.\n\n**Maturity Score: 82.5 | Stage: MATURE**\n", encoding="utf-8")
        en_path.write_text("## Executive Summary\nEnglish summary.\n\n**Maturity Score: 82.5 | Stage: MATURE**\n", encoding="utf-8")

        result = gen_report_card.generate_mat_report_card(
            ko_md_path=str(ko_path),
            en_md_path=str(en_path),
            project_name="Hyperliquid",
            symbol="HYPE",
            slug="hyperliquid",
            output_dir=tmpdir,
        )

    assert result["card_data"]["maturity_score"] == 82.5
    assert result["card_data"]["maturity_stage"] == "MATURE"
    assert result["card_data"]["report_type"] == "mat"


OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def test_econ_pillar_scores_aave_real_report():
    text = (OUTPUT_DIR / "aave_econ_v1_ko.md").read_text(encoding="utf-8") if (OUTPUT_DIR / "aave_econ_v1_ko.md").exists() else ""
    if not text:
        return
    scores = gen_report_card.parse_econ_pillar_scores(text)
    assert len(scores) >= 4, f"expected >=4 pillar scores, got {scores}"
    assert all(0 <= s <= 10 for s in scores), f"scores out of range: {scores}"


def test_econ_pillar_scores_synthetic_table():
    text = (
        "| **Value System** | **9.5 / 10** | basis |\n"
        "| **Reward System** | **9.0 / 10** | basis |\n"
        "| **Compensation System** | **8.5 / 10** | basis |\n"
        "| **Bootstrapping** | **9.5 / 10** | basis |\n"
    )
    assert gen_report_card.parse_econ_pillar_scores(text) == [9.5, 9.0, 8.5, 9.5]


def test_econ_pillar_scores_handles_escaped_bold():
    text = "| Value | \\*\\*9.0 / 10\\*\\* | basis |"
    assert gen_report_card.parse_econ_pillar_scores(text) == [9.0]


def test_econ_pillar_scores_no_false_positive_on_prose():
    text = "We rate this E for excellent, with Token T as treasury."
    assert gen_report_card.parse_econ_pillar_scores(text) == []


def test_mat_overall_score_explicit_phrase():
    text = "**최종 진행률 평가 결과: 76.25%**"
    assert gen_report_card.parse_mat_overall_score(text) == 76.25


def test_mat_overall_score_table_row():
    text = "| **총 달성률** | **100%** |  |  |  | **78.28%** |"
    assert gen_report_card.parse_mat_overall_score(text) == 78.28


def test_mat_overall_score_handles_escaped_bold_inline():
    text = r"진행률은 \*\*80.75%\*\*로 평가된다."
    assert gen_report_card.parse_mat_overall_score(text) == 80.75


def test_mat_overall_score_returns_none_when_absent():
    text = "본 보고서는 평가 기준을 제시한다."
    assert gen_report_card.parse_mat_overall_score(text) is None


def test_mat_overall_score_real_reports():
    samples = (
        ("hyperliquid_mat_v1_ko.md", 70.0, 100.0),
        ("chainlink_mat_v1_ko.md", 50.0, 100.0),
        ("bitcoin_mat_v1_ko.md", 50.0, 100.0),
        ("cardano_mat_v1_ko.md", 50.0, 100.0),
        ("binancecoin_mat_v1_ko.md", 50.0, 100.0),
    )
    checked = 0
    for filename, lower, upper in samples:
        path = OUTPUT_DIR / filename
        if not path.exists():
            continue
        score = gen_report_card.parse_mat_overall_score(path.read_text(encoding="utf-8"))
        assert score is not None, f"{filename}: parse returned None"
        assert lower <= score <= upper, f"{filename}: score {score} not in [{lower}, {upper}]"
        checked += 1
    if checked < 3:
        # Need enough real samples to consider this a meaningful regression guard.
        raise AssertionError(f"only {checked} real MAT report samples found; expected ≥3")


def test_mat_stage_korean_with_english_label():
    text = "현재 \\*\\*'성숙(Mature)'\\*\\* 단계로 평가된다."
    assert gen_report_card.parse_mat_stage(text) == "성숙"


def run_all_tests():
    tests = [
        test_generate_econ_report_card_sets_rating,
        test_generate_mat_report_card_sets_maturity_score,
        test_econ_pillar_scores_aave_real_report,
        test_econ_pillar_scores_synthetic_table,
        test_econ_pillar_scores_handles_escaped_bold,
        test_econ_pillar_scores_no_false_positive_on_prose,
        test_mat_overall_score_explicit_phrase,
        test_mat_overall_score_table_row,
        test_mat_overall_score_handles_escaped_bold_inline,
        test_mat_overall_score_returns_none_when_absent,
        test_mat_overall_score_real_reports,
        test_mat_stage_korean_with_english_label,
    ]
    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as exc:
            print(f"✗ {test_func.__name__} FAILED: {exc}")
            failed += 1
        except Exception as exc:
            print(f"✗ {test_func.__name__} ERROR: {exc}")
            failed += 1

    print(f"gen_report_card tests: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all_tests())
