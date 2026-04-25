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


def run_all_tests():
    tests = [
        test_generate_econ_report_card_sets_rating,
        test_generate_mat_report_card_sets_maturity_score,
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
