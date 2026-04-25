#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import watch_drafts


def test_process_type_passes_slug_dry_run_and_force():
    completed = mock.Mock(returncode=0, stdout="published\n", stderr="")

    with mock.patch("watch_drafts.subprocess.run", return_value=completed) as run_mock:
        published, failed = watch_drafts.process_type(
            "econ",
            dry_run=True,
            slug="bitcoin",
            force=True,
        )

    assert published == 1
    assert failed == 0
    args = run_mock.call_args.args[0]
    assert "--type" in args
    assert "econ" in args
    assert "--slug" in args
    assert "bitcoin" in args
    assert "--dry-run" in args
    assert "--force" in args


def test_process_type_marks_nonzero_exit_as_failure():
    completed = mock.Mock(returncode=1, stdout="DONE: 0/1 published\n", stderr="boom")

    with mock.patch("watch_drafts.subprocess.run", return_value=completed):
        published, failed = watch_drafts.process_type("mat")

    assert published == 1
    assert failed == 1


def test_main_uses_unified_scan_and_force_flag():
    fake_files = [{"file_id": "123", "name": "bitcoin_econ_v1.md", "slug": "bitcoin"}]

    with mock.patch.dict(os.environ, {"GDRIVE_ROOT_FOLDER_ID": "root"}):
        with mock.patch.object(watch_drafts, "scan_type", return_value=fake_files) as scan_mock:
            with mock.patch.object(watch_drafts, "process_type", return_value=(1, 0)) as process_mock:
                with mock.patch.object(watch_drafts, "write_scan_log", return_value="/tmp/log.md"):
                    with mock.patch.object(
                        sys,
                        "argv",
                        ["watch_drafts.py", "--type", "econ", "--force", "--slug", "bitcoin"],
                    ):
                        rc = watch_drafts.main()

    assert rc == 0
    scan_mock.assert_called_once_with("econ", slug="bitcoin", force=True)
    process_mock.assert_called_once_with("econ", dry_run=False, slug="bitcoin", force=True)


def test_main_still_processes_force_rerun_when_scan_resolves_matching_slug():
    fake_files = [{"file_id": "file-zro", "name": "ZRO 포렌식 분석 보고서.md", "slug": "layerzero"}]

    with mock.patch.dict(os.environ, {"GDRIVE_ROOT_FOLDER_ID": "root"}):
        with mock.patch.object(watch_drafts, "scan_type", return_value=fake_files) as scan_mock:
            with mock.patch.object(watch_drafts, "process_type", return_value=(1, 0)) as process_mock:
                with mock.patch.object(watch_drafts, "write_scan_log", return_value="/tmp/log.md"):
                    with mock.patch.object(
                        sys,
                        "argv",
                        ["watch_drafts.py", "--type", "for", "--slug", "layerzero", "--force", "--dry-run"],
                    ):
                        rc = watch_drafts.main()

    assert rc == 0
    scan_mock.assert_called_once_with("for", slug="layerzero", force=True)
    process_mock.assert_called_once_with("for", dry_run=True, slug="layerzero", force=True)


def run_all_tests():
    tests = [
        test_process_type_passes_slug_dry_run_and_force,
        test_process_type_marks_nonzero_exit_as_failure,
        test_main_uses_unified_scan_and_force_flag,
        test_main_still_processes_force_rerun_when_scan_resolves_matching_slug,
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

    print(f"watch_drafts tests: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all_tests())
