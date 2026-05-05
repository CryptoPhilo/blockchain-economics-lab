"""Tests for BCE-1795 X promo copy generation and approval queue."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def xpromo():
    spec = importlib.util.spec_from_file_location(
        "x_promo_pipeline",
        Path(__file__).with_name("x_promo_pipeline.py"),
    )
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample_reports(xpromo):
    return [
        xpromo.XPromoReport(
            id=f"r{i}",
            slug=f"project-{i}",
            report_type="econ",
            version=1,
            marketing_content_by_lang={
                "en": f"Project {i} shows improving liquidity, but valuation risk still needs disciplined monitoring before position sizing.",
                "ko": f"프로젝트 {i}는 유동성 개선을 보이지만, 포지션 확대 전 밸류에이션 리스크를 함께 점검해야 합니다.",
            },
            title_by_lang={"en": f"Project {i} Economic Report", "ko": f"프로젝트 {i} 경제 리포트"},
        )
        for i in range(1, 6)
    ]


def test_generates_three_templates_for_five_sample_reports(xpromo):
    drafts = xpromo.generate_x_promo_drafts(
        _sample_reports(xpromo),
        languages=["en"],
        generated_at="2026-05-05T00:00:00+00:00",
    )

    assert len(drafts) == 15
    assert {draft.template for draft in drafts} == set(xpromo.DEFAULT_TEMPLATES)
    assert {draft.status for draft in drafts} == {"pending_manual_approval"}
    assert all(draft.char_count <= 280 for draft in drafts)
    assert all(draft.report_url.endswith(draft.slug) for draft in drafts)


def test_duplicate_key_is_stable_and_distinct_by_template(xpromo):
    reports = _sample_reports(xpromo)[:1]

    first = xpromo.generate_x_promo_drafts(reports, languages=["en"])
    second = xpromo.generate_x_promo_drafts(reports, languages=["en"])

    assert [draft.duplicate_key for draft in first] == [draft.duplicate_key for draft in second]
    assert len({draft.duplicate_key for draft in first}) == 3


def test_long_copy_is_truncated_with_url_inside_limit(xpromo):
    report = xpromo.XPromoReport(
        id="long-1",
        slug="long-project",
        report_type="forensic",
        version=2,
        marketing_content_by_lang={"en": " ".join(["market structure risk"] * 80)},
    )

    drafts = xpromo.generate_x_promo_drafts([report], languages=["en"])

    assert all(draft.char_count <= 280 for draft in drafts)
    assert all("https://bcelab.xyz/reports/long-project" in draft.text for draft in drafts)
    assert any("…" in draft.text for draft in drafts)


def test_writes_jsonl_and_markdown_review_queue(tmp_path, xpromo):
    drafts = xpromo.generate_x_promo_drafts(
        _sample_reports(xpromo)[:1],
        languages=["ko"],
        templates=["insight-first"],
        generated_at="2026-05-05T00:00:00+00:00",
    )

    paths = xpromo.write_approval_queue(drafts, output_dir=tmp_path, run_id="test-run")

    jsonl = Path(paths["jsonl"])
    markdown = Path(paths["markdown"])
    rows = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines()]

    assert jsonl.name == "x-promo-approval-test-run.jsonl"
    assert markdown.name == "x-promo-approval-test-run.md"
    assert rows[0]["status"] == "pending_manual_approval"
    assert rows[0]["audit"]["source_field"] == "project_reports.marketing_content_by_lang"
    assert "Reviewer action" in markdown.read_text(encoding="utf-8")


def test_card_summary_fallback_generates_draft_when_marketing_content_is_empty(xpromo):
    report = xpromo.XPromoReport(
        id="summary-1",
        slug="summary-project",
        report_type="econ",
        version=1,
        marketing_content_by_lang={},
        card_summary_by_lang={
            "en": "Card summary fallback explains the core liquidity signal when marketing copy is not yet populated.",
        },
        title_by_lang={"en": "Summary Project Economic Report"},
    )

    drafts = xpromo.generate_x_promo_drafts(
        [report],
        languages=["en"],
        templates=["insight-first"],
        generated_at="2026-05-05T00:00:00+00:00",
    )

    assert len(drafts) == 1
    assert "Card summary fallback" in drafts[0].text
    assert drafts[0].audit["source_field"] == "project_reports.card_summary_en"


def test_queue_dry_run_requires_no_x_credentials(tmp_path, monkeypatch, capsys, xpromo):
    for name in xpromo.REQUIRED_POST_ENV:
        monkeypatch.delenv(name, raising=False)

    draft = xpromo.generate_x_promo_drafts(
        _sample_reports(xpromo)[:1],
        languages=["en"],
        templates=["insight-first"],
    )[0]
    approved = {**xpromo._draft_to_json(draft), "status": "approved"}
    queue = tmp_path / "queue.jsonl"
    queue.write_text(json.dumps(approved, ensure_ascii=False) + "\n", encoding="utf-8")

    assert xpromo.main(["--queue-jsonl", str(queue), "--confirm", "project-1"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["dry_run"] is True
    assert payload["approved_candidates"] == 1
    assert payload["posts"][0]["slug"] == "project-1"


def test_post_requires_x_credentials(tmp_path, monkeypatch, xpromo):
    for name in xpromo.REQUIRED_POST_ENV:
        monkeypatch.delenv(name, raising=False)

    draft = xpromo.generate_x_promo_drafts(
        _sample_reports(xpromo)[:1],
        languages=["en"],
        templates=["insight-first"],
    )[0]
    approved = {**xpromo._draft_to_json(draft), "status": "approved"}
    queue = tmp_path / "queue.jsonl"
    queue.write_text(json.dumps(approved, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Missing X credentials"):
        xpromo.main(["--queue-jsonl", str(queue), "--post", "--confirm", "project-1"])


def test_duplicate_guard_skips_previously_posted_key(tmp_path, xpromo):
    class FakePoster:
        def __init__(self):
            self.calls = []

        def post_tweet(self, text):
            self.calls.append(text)
            return xpromo.XPostResult(post_id="x-1", text=text, raw={"data": {"id": "x-1", "text": text}})

    draft = xpromo.generate_x_promo_drafts(
        _sample_reports(xpromo)[:1],
        languages=["en"],
        templates=["insight-first"],
    )[0]
    approved = xpromo._draft_from_json({**xpromo._draft_to_json(draft), "status": "approved"})
    log = tmp_path / "x-post-log.jsonl"
    xpromo.append_post_log(
        {"duplicate_key": approved.duplicate_key, "status": "posted", "x_post_id": "already"},
        log_path=log,
    )

    poster = FakePoster()
    results = xpromo.send_approved_drafts(
        [approved],
        poster=poster,
        confirm_slug=approved.slug,
        log_path=log,
    )

    assert poster.calls == []
    assert results[0]["status"] == "duplicate_skipped"


def test_post_refuses_multiple_approved_drafts_for_same_slug(tmp_path, xpromo):
    class FakePoster:
        def __init__(self):
            self.calls = []

        def post_tweet(self, text):
            self.calls.append(text)
            return xpromo.XPostResult(post_id="x-1", text=text, raw={"data": {"id": "x-1", "text": text}})

    drafts = xpromo.generate_x_promo_drafts(
        _sample_reports(xpromo)[:1],
        languages=["en"],
        templates=["insight-first", "chart-report-first"],
    )
    approved = [
        xpromo._draft_from_json({**xpromo._draft_to_json(draft), "status": "approved"})
        for draft in drafts
    ]

    poster = FakePoster()
    with pytest.raises(RuntimeError, match="Refusing to post multiple"):
        xpromo.send_approved_drafts(
            approved,
            poster=poster,
            confirm_slug="project-1",
            log_path=tmp_path / "x-post-log.jsonl",
        )

    assert poster.calls == []


def test_rejects_unsupported_language(xpromo):
    with pytest.raises(ValueError, match="Unsupported language"):
        xpromo.generate_x_promo_drafts(_sample_reports(xpromo)[:1], languages=["it"])
