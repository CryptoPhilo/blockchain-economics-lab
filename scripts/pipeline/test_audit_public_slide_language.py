import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_public_slide_language as audit


def _html(path: Path, body: str) -> str:
    path.write_text(f"<html><body><main>{body}</main></body></html>", encoding="utf-8")
    return f"file://{path}"


def test_audit_flags_route_locale_text_mismatch(tmp_path):
    fixture_path = tmp_path / "fixture.json"
    ko_url = _html(
        tmp_path / "bitcoin-ko.html",
        (
            "本报告分析比特币加密经济设计、稀缺数字资产、工作量证明、"
            "去中心化发行、链上结算网络、矿工激励以及长期安全预算。"
        )
        * 4,
    )
    fixture_path.write_text(
        json.dumps({
            "entries": [{
                "slug": "bitcoin",
                "report_type": "econ",
                "lang": "ko",
                "url": ko_url,
            }]
        }),
        encoding="utf-8",
    )

    entries = audit._entries_from_fixture(fixture_path)
    result = audit.run_audit(entries)

    assert result["summary"]["language_mismatch"] == 1
    assert result["summary"]["repair_candidates"] == 1
    assert result["repair_candidates"][0] == {
        "reason": "language_mismatch",
        "slug": "bitcoin",
        "report_type": "econ",
        "lang": "ko",
        "url": ko_url,
        "mismatch": {
            "resolved_lang": "ko",
            "detected_lang": "zh",
            "source": "text",
        },
    }


def test_audit_flags_identical_html_across_language_slots(tmp_path):
    shared_html = _html(
        tmp_path / "shared.html",
        "Bitcoin cryptoeconomic design analysis proof of work security budget.",
    )
    entries = [
        audit.SlideEntry("bitcoin", "econ", "ko", shared_html),
        audit.SlideEntry("bitcoin", "econ", "zh", shared_html),
        audit.SlideEntry("bitcoin", "econ", "en", _html(tmp_path / "en.html", "English report")),
    ]

    result = audit.run_audit(entries)

    assert result["summary"]["duplicate_groups"] == 1
    assert result["summary"]["repair_candidates"] == 1
    duplicate = result["duplicate_groups"][0]
    assert duplicate["slug"] == "bitcoin"
    assert duplicate["report_type"] == "econ"
    assert duplicate["langs"] == ["ko", "zh"]
    assert result["repair_candidates"][0]["reason"] == "duplicate_html_across_languages"
