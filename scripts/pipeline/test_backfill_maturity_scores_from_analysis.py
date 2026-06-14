"""Tests for MAT score backfill from active analysis2/MAT Markdown files."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def backfill():
    spec = importlib.util.spec_from_file_location(
        "backfill_maturity_scores_from_analysis",
        Path(__file__).with_name("backfill_maturity_scores_from_analysis.py"),
    )
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeSupabase:
    def __init__(self, projects):
        self.projects = projects

    def table(self, name):
        assert name == "tracked_projects"
        return FakeTable(self)


class FakeTable:
    def __init__(self, sb):
        self.sb = sb
        self._slugs = None
        self._patch = None
        self._eq_id = None

    def select(self, _columns):
        return self

    def in_(self, column, values):
        assert column == "slug"
        self._slugs = set(values)
        return self

    def range(self, _start, _end):
        return self

    def update(self, patch):
        self._patch = patch
        return self

    def eq(self, column, value):
        assert column == "id"
        self._eq_id = value
        return self

    def execute(self):
        if self._patch is not None:
            for project in self.sb.projects:
                if project["id"] == self._eq_id:
                    project.update(self._patch)
                    return type("Response", (), {"data": [project]})()
            return type("Response", (), {"data": []})()

        rows = self.sb.projects
        if self._slugs is not None:
            rows = [project for project in rows if project["slug"] in self._slugs]
        return type("Response", (), {"data": rows})()


def test_split_slugs_validates_input(backfill):
    assert backfill._split_slugs(["bitcoin, ethereum\nsolana"]) == [
        "bitcoin",
        "ethereum",
        "solana",
    ]
    with pytest.raises(ValueError):
        backfill._split_slugs(["bad/slug"])


def test_source_match_prefers_structured_mat_name(backfill):
    project = {"slug": "velvet", "name": "Velvet", "symbol": "VELVET", "aliases": []}
    match = backfill._source_match_for_project(
        project,
        [
            {"id": "low", "name": "Velvet random source.md", "modifiedTime": "2026-06-01T00:00:00Z"},
            {"id": "exact", "name": "velvet_mat_v1_en.md", "modifiedTime": "2026-06-01T00:00:00Z"},
        ],
    )

    assert match is not None
    assert match.item["id"] == "exact"
    assert match.reason == "exact_structured_name"


def test_source_match_rejects_substring_symbol_collision(backfill):
    project = {"slug": "usx", "name": "Solstice USX", "symbol": "USX", "aliases": []}
    match = backfill._source_match_for_project(
        project,
        [
            {
                "id": "eusx",
                "name": "Solstice eUSX의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025 - 2026.md",
                "modifiedTime": "2026-06-01T00:00:00Z",
            },
        ],
    )

    assert match is None


def test_diagnostic_candidates_include_zero_score_names(backfill):
    project = {"slug": "deepbook-protocol", "name": "DeepBook Protocol", "symbol": "DEEP", "aliases": []}
    candidates = backfill._diagnostic_candidates_for_project(
        project,
        [
            {"id": "one", "name": "unrelated_mat_v1_ko.md", "modifiedTime": "2026-06-01T00:00:00Z"},
            {"id": "two", "name": "another unrelated report.md", "modifiedTime": "2026-06-02T00:00:00Z"},
        ],
        limit=2,
    )

    assert len(candidates) == 2
    assert [candidate.score for candidate in candidates] == [0, 0]


def test_backfill_updates_only_projects_with_mat_md_and_score(monkeypatch, backfill):
    projects = [
        {
            "id": "p-undeads",
            "slug": "undeads-games",
            "name": "Undeads Games",
            "symbol": "UDS",
            "aliases": [],
            "maturity_score": None,
        },
        {
            "id": "p-missing",
            "slug": "missing-project",
            "name": "Missing Project",
            "symbol": "MISS",
            "aliases": [],
            "maturity_score": None,
        },
    ]
    items = [
        {
            "id": "md-undeads",
            "name": "Undeads Games MAT report.md",
            "modifiedTime": "2026-06-13T00:00:00Z",
        },
    ]
    monkeypatch.setattr(backfill, "_active_analysis_source_folder_ids", lambda _service: {"mat": "mat-folder"})
    monkeypatch.setattr(backfill, "_list_drive_markdown_sources", lambda _service, _folder_id: items)
    monkeypatch.setattr(
        backfill,
        "_download_drive_text",
        lambda _service, _file_id: "**Overall Maturity Score: 57.4**\n\nStage: Mature\n",
    )

    stats = backfill.backfill_maturity_scores(
        sb=FakeSupabase(projects),
        drive_service=object(),
        slugs=["undeads-games", "missing-project"],
        dry_run=False,
        overwrite=False,
        min_score=60,
    )

    assert stats["updated"] == 1
    assert stats["skipped_no_md"] == 1
    assert projects[0]["maturity_score"] == 57.4
    assert projects[0]["maturity_stage"] == "mature"
    assert projects[1]["maturity_score"] is None
