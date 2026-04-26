import os
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gmail_monitor
from gmail_monitor import (
    DEFAULT_MAILBOX,
    DEFAULT_SINCE_HOURS,
    DEFAULT_PROCESSED_LABEL,
    DEFAULT_ROUTING,
    MAX_SINCE_HOURS,
    MIN_SINCE_HOURS,
    MonitorConfig,
    ThreadCandidate,
    build_search_query,
    clamp_since_hours,
    classify_category,
    find_existing_issue_for_thread,
    format_issue_description,
    get_gmail_monitor_user,
    infer_priority,
    is_actionable_email,
    is_recent_enough,
    parse_args,
    run_preflight,
    select_assignee_agent_id,
    summarize_body,
)


class GmailMonitorLogicTests(unittest.TestCase):
    def test_find_existing_issue_for_thread_uses_thread_marker_query_and_project_filter(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return [
                    {
                        "id": "wrong-project",
                        "projectId": "other-project",
                        "description": "Gmail Thread ID: thread-123",
                    },
                    {
                        "id": "right-project",
                        "projectId": "project-1",
                        "description": "Gmail Thread ID: thread-123",
                    },
                ]

        with (
            patch.object(gmail_monitor, "PAPERCLIP_API_URL", "https://paperclip.example.com"),
            patch.object(gmail_monitor, "PAPERCLIP_COMPANY_ID", "company-1"),
            patch.object(gmail_monitor, "PAPERCLIP_API_KEY", "secret"),
            patch.object(gmail_monitor.requests, "get", return_value=FakeResponse()) as mock_get,
        ):
            issue = find_existing_issue_for_thread("thread-123", "project-1")

        self.assertIsNotNone(issue)
        self.assertEqual(issue["id"], "right-project")
        self.assertEqual(
            mock_get.call_args.kwargs["params"],
            {"q": '"Gmail Thread ID: thread-123"', "limit": 10},
        )

    def test_actionable_email_detects_required_keywords(self):
        actionable, reason = is_actionable_email("시장 분석 요청", "내일까지 보고할 것")
        self.assertTrue(actionable)
        self.assertIn("matched", reason)

    def test_actionable_email_skips_test_subject(self):
        actionable, reason = is_actionable_email("테스트 메일", "요청이 있습니다")
        self.assertFalse(actionable)
        self.assertIn("skip", reason)

    def test_category_classification_supports_revenue_keywords(self):
        category = classify_category("파트너십 매출 확대 요청", "sales 파이프라인과 deal 정리가 필요합니다")
        self.assertEqual(category, "revenue")

    def test_revenue_category_routes_to_cro(self):
        assignee = select_assignee_agent_id("revenue", {"revenue": "agent-cro", "other": "agent-ceo"})
        self.assertEqual(assignee, "agent-cro")

    def test_uncategorized_mail_routes_to_ceo(self):
        category = classify_category("일반 전달", "카테고리 키워드가 없는 공지입니다")
        assignee = select_assignee_agent_id(category, {"technical": "agent-cto", "other": "agent-ceo"})
        self.assertEqual(category, "other")
        self.assertEqual(assignee, "agent-ceo")

    def test_category_classification_prefers_technical_keywords(self):
        category = classify_category("배포 오류 수정 요청", "서버 배포와 API 수정이 필요합니다")
        self.assertEqual(category, "technical")

    def test_defaults_align_with_issue_requirements(self):
        self.assertEqual(DEFAULT_PROCESSED_LABEL, "Paperclip/Processed")
        self.assertEqual(DEFAULT_MAILBOX, "philoskor@gmail.com")
        self.assertEqual(DEFAULT_SINCE_HOURS, 0.5)
        self.assertEqual(DEFAULT_ROUTING["other"], "CEO")
        self.assertEqual(DEFAULT_ROUTING["revenue"], "CRO")

    def test_workflow_schedule_and_defaults_are_30_minute_anchored(self):
        workflow_path = Path(__file__).resolve().parent.parent / ".github/workflows/gmail-inbox-monitor.yml"
        content = workflow_path.read_text(encoding="utf-8")
        self.assertIn('cron: "*/30 * * * *"', content)
        self.assertIn("GMAIL_SINCE_HOURS: \"0.5\"", content)

    def test_format_issue_description_includes_explicit_gmail_thread_marker(self):
        candidate = ThreadCandidate(
            "thread-123",
            "제목",
            "sender@example.com",
            datetime.now(timezone.utc),
            "본문",
            "snippet",
        )
        description = format_issue_description(candidate, "요약", "operations")
        self.assertIn("**Gmail Thread ID**: thread-123", description)
        self.assertIn("Gmail Thread ID: thread-123", description)

    def test_parse_args_uses_updated_defaults(self):
        config = parse_args([])
        self.assertIsInstance(config, MonitorConfig)
        self.assertFalse(config.preflight)
        self.assertEqual(config.processed_label, "Paperclip/Processed")
        self.assertEqual(config.since_hours, 0.5)

    def test_parse_args_supports_preflight_flag(self):
        config = parse_args(["--preflight"])
        self.assertTrue(config.preflight)

    def test_parse_args_supports_preflight_with_half_hour_window(self):
        config = parse_args(["--preflight", "--since-hours", "0.5"])
        self.assertTrue(config.preflight)
        self.assertEqual(config.since_hours, 0.5)

    def test_parse_args_allows_processed_label_env_override(self):
        with patch.dict("os.environ", {"GMAIL_PROCESSED_LABEL": "Paperclip/Processed"}, clear=False):
            config = parse_args([])
        self.assertEqual(config.processed_label, "Paperclip/Processed")

    def test_parse_args_allows_since_hours_env_override(self):
        with patch.dict("os.environ", {"GMAIL_SINCE_HOURS": "2"}, clear=False):
            config = parse_args([])
        self.assertEqual(config.since_hours, 2)

    def test_parse_args_clamps_since_hours_env_override_to_max_window(self):
        with patch.dict("os.environ", {"GMAIL_SINCE_HOURS": "72"}, clear=False):
            config = parse_args([])
        self.assertEqual(config.since_hours, MAX_SINCE_HOURS)

    def test_parse_args_rejects_non_positive_since_hours(self):
        with self.assertRaisesRegex(RuntimeError, "greater than 0"):
            parse_args(["--since-hours", "0"])

    def test_gmail_monitor_user_allows_env_override(self):
        with patch.dict("os.environ", {"GMAIL_MONITOR_USER": "ops@example.com"}, clear=False):
            mailbox = get_gmail_monitor_user()
        self.assertEqual(mailbox, "ops@example.com")

    def test_priority_inference_marks_urgent_mail_highest(self):
        priority = infer_priority("긴급 확인 요청", "이건 ASAP으로 처리해주세요")
        self.assertEqual(priority, "critical")

    def test_recent_window_filters_old_threads(self):
        config = MonitorConfig(
            preflight=False,
            dry_run=True,
            since_hours=1,
            max_results=10,
            processed_label="Paperclip/Processed",
            goal_id="goal",
            project_id="project",
        )
        recent = ThreadCandidate("t1", "제목", "sender", datetime.now(timezone.utc) - timedelta(minutes=20), "본문", "snippet")
        old = ThreadCandidate("t2", "제목", "sender", datetime.now(timezone.utc) - timedelta(hours=3), "본문", "snippet")
        self.assertTrue(is_recent_enough(recent, config))
        self.assertFalse(is_recent_enough(old, config))

    def test_summary_is_compacted_and_truncated(self):
        summary = summarize_body("A   B\nC" * 100, "", limit=20)
        self.assertLessEqual(len(summary), 20)
        self.assertNotIn("\n", summary)

    def test_clamp_since_hours_enforces_minimum_window(self):
        self.assertEqual(clamp_since_hours(0.001), MIN_SINCE_HOURS)

    def test_build_search_query_uses_epoch_window_boundary(self):
        now = datetime(2026, 4, 19, 8, 0, 0, tzinfo=timezone.utc)
        query = build_search_query("Paperclip/Processed", 2, now=now)
        self.assertEqual(query, 'in:inbox after:1776578400 -label:"Paperclip/Processed"')

    def test_run_preflight_validates_access_without_writes(self):
        config = MonitorConfig(
            preflight=True,
            dry_run=False,
            since_hours=1,
            max_results=10,
            processed_label="Paperclip/Processed",
            goal_id="goal",
            project_id="project",
        )

        with (
            patch.dict(
                "os.environ",
                {
                    "PAPERCLIP_API_URL": "https://paperclip.example.com",
                    "PAPERCLIP_API_KEY": "secret",
                    "PAPERCLIP_COMPANY_ID": "company-1",
                    "GMAIL_CLIENT_ID": "gmail-client",
                    "GMAIL_CLIENT_SECRET": "gmail-secret",
                    "GMAIL_REFRESH_TOKEN": "refresh-token",
                },
                clear=False,
            ),
            patch.object(gmail_monitor, "gmail_access_token", return_value="access-token") as mock_token,
            patch.object(gmail_monitor, "resolve_agent_map", return_value={key: f"agent-{key}" for key in DEFAULT_ROUTING}) as mock_agents,
            patch.object(gmail_monitor, "find_label_id", return_value="label-1") as mock_label,
            patch.object(gmail_monitor, "list_recent_thread_ids", return_value=["thread-1"]) as mock_list,
        ):
            result = run_preflight(config)

        self.assertEqual(result, 0)
        mock_token.assert_called_once_with()
        mock_agents.assert_called_once_with()
        mock_label.assert_called_once_with("access-token", "Paperclip/Processed")
        mock_list.assert_called_once_with("access-token", config)

    def test_run_preflight_fails_when_routing_is_unresolved(self):
        config = MonitorConfig(
            preflight=True,
            dry_run=False,
            since_hours=1,
            max_results=10,
            processed_label="Paperclip/Processed",
            goal_id="goal",
            project_id="project",
        )

        with (
            patch.dict(
                "os.environ",
                {
                    "PAPERCLIP_API_URL": "https://paperclip.example.com",
                    "PAPERCLIP_API_KEY": "secret",
                    "PAPERCLIP_COMPANY_ID": "company-1",
                    "GMAIL_CLIENT_ID": "gmail-client",
                    "GMAIL_CLIENT_SECRET": "gmail-secret",
                    "GMAIL_REFRESH_TOKEN": "refresh-token",
                },
                clear=False,
            ),
            patch.object(gmail_monitor, "gmail_access_token", return_value="access-token"),
            patch.object(gmail_monitor, "resolve_agent_map", return_value={"other": "agent-other"}),
        ):
            with self.assertRaisesRegex(RuntimeError, "failed to resolve assignee routing"):
                run_preflight(config)

    def test_gmail_access_token_surfaces_google_error_body(self):
        class FakeErrorResponse:
            ok = False
            status_code = 401
            reason = "Unauthorized"
            text = '{"error":"invalid_grant","error_description":"Bad Request"}'

            def json(self):
                return {"error": "invalid_grant", "error_description": "Bad Request"}

        with (
            patch.object(gmail_monitor, "GMAIL_CLIENT_ID", "cid"),
            patch.object(gmail_monitor, "GMAIL_CLIENT_SECRET", "csec"),
            patch.object(gmail_monitor, "GMAIL_REFRESH_TOKEN", "rtok"),
            patch.object(gmail_monitor.requests, "post", return_value=FakeErrorResponse()),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                gmail_monitor.gmail_access_token()

        message = str(ctx.exception)
        self.assertIn("HTTP 401", message)
        self.assertIn("Unauthorized", message)
        self.assertIn("invalid_grant", message)
        self.assertIn("Bad Request", message)
        self.assertNotIn("cid", message)
        self.assertNotIn("csec", message)
        self.assertNotIn("rtok", message)

    def test_gmail_access_token_falls_back_to_text_when_body_is_not_json(self):
        class FakePlainErrorResponse:
            ok = False
            status_code = 502
            reason = "Bad Gateway"
            text = "<html>upstream timeout</html>"

            def json(self):
                raise ValueError("not json")

        with (
            patch.object(gmail_monitor, "GMAIL_CLIENT_ID", "cid"),
            patch.object(gmail_monitor, "GMAIL_CLIENT_SECRET", "csec"),
            patch.object(gmail_monitor, "GMAIL_REFRESH_TOKEN", "rtok"),
            patch.object(gmail_monitor.requests, "post", return_value=FakePlainErrorResponse()),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                gmail_monitor.gmail_access_token()

        message = str(ctx.exception)
        self.assertIn("HTTP 502", message)
        self.assertIn("Non-JSON body", message)
        self.assertIn("upstream timeout", message)

    def test_run_wrapper_accepts_preflight_flag_and_returns_actionable_missing_secret_error(self):
        root_dir = Path(__file__).resolve().parent.parent
        script_path = root_dir / "run_gmail_inbox_monitor.sh"
        env = {**os.environ, "PATH": os.environ.get("PATH", "")}
        for key in (
            "PAPERCLIP_API_URL",
            "PAPERCLIP_API_KEY",
            "PAPERCLIP_COMPANY_ID",
            "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET",
            "GMAIL_REFRESH_TOKEN",
        ):
            env.pop(key, None)

        result = subprocess.run(
            [str(script_path), "--preflight", "--since-hours", "0.5"],
            cwd=root_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        combined_output = f"{result.stdout}\n{result.stderr}"
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("unrecognized arguments: --preflight", combined_output)
        self.assertIn("Missing required environment variable", combined_output)
        self.assertIn("run_gmail_inbox_monitor.sh --preflight", combined_output)


if __name__ == "__main__":
    unittest.main()
