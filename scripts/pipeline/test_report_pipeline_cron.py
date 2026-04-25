#!/usr/bin/env python3
from pathlib import Path


WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "report-pipeline-cron.yml"


def test_report_pipeline_workflow_prevents_overlap_and_uses_unified_watcher():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "concurrency:" in workflow
    assert "group: report-pipeline-cron-${{ github.ref }}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "python3 watch_drafts.py --type \"$REPORT_TYPE\"" in workflow
    assert "python3 -m playwright install --with-deps chromium" in workflow
    assert "Validate workflow secrets and runtime prerequisites" in workflow
    assert "from playwright.sync_api import sync_playwright" in workflow
    assert "browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])" in workflow
    assert "version = browser.version" in workflow
    assert 'if not version.strip()' in workflow
    assert 'Validated Playwright Chromium launch: {version}' in workflow
    assert "CMC_API_KEY=${{ secrets.COINMARKETCAP_API_KEY }}" in workflow
    assert "scripts/pipeline/fonts/*.ttf" in workflow
    assert "p.chromium.executable_path" not in workflow
    assert "if not executable_path.exists()" not in workflow
    assert "chromium_headless_shell-*/chrome-linux/headless_shell" not in workflow
    assert "chromium-*/chrome-linux/chrome" not in workflow


def run_all_tests() -> int:
    tests = [
        test_report_pipeline_workflow_prevents_overlap_and_uses_unified_watcher,
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

    print(f"report-pipeline-cron tests: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all_tests())
