#!/usr/bin/env python3
"""
Gmail Inbox Monitor for BCE Lab.

Polls Gmail directly via the Gmail REST API, filters recent work-instruction
emails, deduplicates by thread id against local state and existing Paperclip
issues, routes the new issue to an assignee by category, then marks the Gmail
thread as processed.
"""

from __future__ import annotations

import argparse
import math
import fcntl
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable

import requests


SCRIPT_DIR = Path(__file__).parent
PROCESSED_FILE = SCRIPT_DIR / "processed_gmail_threads.json"
LOG_FILE = SCRIPT_DIR / "gmail_monitor.log"

DEFAULT_GOAL_ID = "176cc80b-f108-4098-ad4c-bac14515d346"
DEFAULT_PROJECT_ID = "c99a905c-51d4-41a7-9635-b14c5537d9ab"
DEFAULT_MAILBOX = "philoskor@gmail.com"
DEFAULT_PROCESSED_LABEL = "Paperclip/Processed"
DEFAULT_MONITOR_INTERVAL_MINUTES = 30
DEFAULT_SINCE_HOURS = DEFAULT_MONITOR_INTERVAL_MINUTES / 60
MIN_SINCE_HOURS = DEFAULT_MONITOR_INTERVAL_MINUTES / 60
MAX_SINCE_HOURS = 24

ACTION_PATTERNS = ["할 것", "지시", "요청", "보고", "확인", "만들", "생성", "검토", "분석", "작성", "해줘", "하라", "해라"]
SKIP_SUBJECT_PATTERNS = [
    re.compile(r"테스트", re.IGNORECASE),
    re.compile(r"test", re.IGNORECASE),
    re.compile(r"fwd:", re.IGNORECASE),
    re.compile(r"re:\s*깃헙", re.IGNORECASE),
]
URGENCY_RULES = [
    ("critical", ["즉시", "긴급", "asap", "urgent", "바로"]),
    ("high", ["오늘", "빠르게", "중요", "우선", "금일"]),
]
CATEGORY_RULES = {
    "technical": ["개발", "엔지니어", "기술", "버그", "api", "서버", "프론트", "백엔드", "코드", "배포", "인프라"],
    "marketing": ["마케팅", "홍보", "광고", "캠페인", "브랜딩", "sns", "newsletter", "seo"],
    "revenue": ["매출", "revenue", "sales", "영업", "세일즈", "리드", "고객", "파트너십", "deal", "dealflow"],
    "operations": ["운영", "프로세스", "자동화", "정산", "업로드", "파이프라인", "일정", "관리", "물류", "logistics", "배송", "출고"],
    "research": ["리서치", "연구", "분석", "시장", "토큰", "온체인", "보고서", "거시"],
}
DEFAULT_ROUTING = {
    "technical": "CTO",
    "marketing": "CMO",
    "operations": "COO",
    "revenue": "CRO",
    "research": "CRO",
    "other": "CEO",
}

PAPERCLIP_AGENT_ID = os.environ.get("PAPERCLIP_AGENT_ID")
PAPERCLIP_API_URL = os.environ.get("PAPERCLIP_API_URL")
PAPERCLIP_API_KEY = os.environ.get("PAPERCLIP_API_KEY")
PAPERCLIP_COMPANY_ID = os.environ.get("PAPERCLIP_COMPANY_ID")
PAPERCLIP_RUN_ID = os.environ.get("PAPERCLIP_RUN_ID", "manual")

GMAIL_CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN")
@dataclass
class MonitorConfig:
    preflight: bool
    dry_run: bool
    since_hours: float
    max_results: int
    processed_label: str
    goal_id: str
    project_id: str


@dataclass
class ThreadCandidate:
    thread_id: str
    subject: str
    sender: str
    received_at: datetime
    body: str
    snippet: str


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def require_env(name: str, value: str | None) -> str:
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Run ./run_gmail_inbox_monitor.sh --preflight for a full readiness check "
            "and provision the missing monitor secrets from BCE-522 before live runs."
        )
    return value


def load_processed_threads() -> dict[str, dict]:
    if not PROCESSED_FILE.exists():
        return {}

    with open(PROCESSED_FILE, "r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return {}
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_processed_thread(thread_id: str, issue_id: str, subject: str, metadata: dict | None = None) -> None:
    lock_file = PROCESSED_FILE.with_suffix(".lock")
    with open(lock_file, "w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            processed = load_processed_threads()
            processed[thread_id] = {
                "issue_id": issue_id,
                "subject": subject,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "run_id": PAPERCLIP_RUN_ID,
                **(metadata or {}),
            }
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=PROCESSED_FILE.parent,
                delete=False,
                suffix=".tmp",
                encoding="utf-8",
            ) as temp_handle:
                json.dump(processed, temp_handle, indent=2, ensure_ascii=False)
                tmp_path = temp_handle.name
            os.replace(tmp_path, PROCESSED_FILE)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def load_json_response(response: requests.Response) -> dict:
    response.raise_for_status()
    return response.json()


def paperclip_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {require_env('PAPERCLIP_API_KEY', PAPERCLIP_API_KEY)}",
        "Content-Type": "application/json",
        "X-Paperclip-Run-Id": PAPERCLIP_RUN_ID,
    }


def gmail_access_token() -> str:
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": require_env("GMAIL_CLIENT_ID", GMAIL_CLIENT_ID),
            "client_secret": require_env("GMAIL_CLIENT_SECRET", GMAIL_CLIENT_SECRET),
            "refresh_token": require_env("GMAIL_REFRESH_TOKEN", GMAIL_REFRESH_TOKEN),
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"Gmail OAuth token exchange failed: HTTP {response.status_code} {response.reason}. "
            f"{_describe_oauth_error(response)}"
        )
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("OAuth token response did not include access_token")
    return token


def _describe_oauth_error(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        text = (response.text or "").strip()
        return f"Non-JSON body: {text[:300]}" if text else "Empty body"
    error = body.get("error") or "unknown_error"
    description = body.get("error_description") or "(no description)"
    return f"Google: error={error}, error_description={description}"


def gmail_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def get_gmail_monitor_user() -> str:
    return os.environ.get("GMAIL_MONITOR_USER", DEFAULT_MAILBOX)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        pass

    for parser in (
        lambda raw: datetime.fromisoformat(raw.replace("Z", "+00:00")),
        parsedate_to_datetime,
    ):
        try:
            parsed = parser(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue

    return None


def extract_header(headers: Iterable[dict], name: str) -> str:
    target = name.lower()
    for header in headers:
        if header.get("name", "").lower() == target:
            return header.get("value", "")
    return ""


def choose_latest_message(messages: list[dict]) -> dict:
    def sort_key(message: dict) -> int:
        internal_date = message.get("internalDate")
        try:
            return int(internal_date)
        except (TypeError, ValueError):
            return 0

    return max(messages, key=sort_key) if messages else {}


def extract_plaintext(payload: dict) -> str:
    if payload.get("mimeType", "").startswith("text/plain"):
        body = payload.get("body", {}).get("data")
        if body:
            return decode_base64_urlsafe(body)

    parts = payload.get("parts") or []
    for part in parts:
        text = extract_plaintext(part)
        if text:
            return text
    return ""


def decode_base64_urlsafe(data: str) -> str:
    import base64

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")


def clamp_since_hours(value: float) -> float:
    if not math.isfinite(value):
        raise RuntimeError("GMAIL_SINCE_HOURS must be a finite number")
    if value <= 0:
        raise RuntimeError("GMAIL_SINCE_HOURS must be greater than 0")
    return min(max(value, MIN_SINCE_HOURS), MAX_SINCE_HOURS)


def build_search_query(processed_label: str, since_hours: float, now: datetime | None = None) -> str:
    window_end = now or datetime.now(timezone.utc)
    window_start = window_end - timedelta(hours=clamp_since_hours(since_hours))
    label_query = f'-label:"{processed_label}"' if processed_label else ""
    after_query = f"after:{int(window_start.timestamp())}"
    return " ".join(part for part in ["in:inbox", after_query, label_query] if part)


def list_recent_thread_ids(access_token: str, config: MonitorConfig) -> list[str]:
    url = f"https://gmail.googleapis.com/gmail/v1/users/{get_gmail_monitor_user()}/messages"
    response = requests.get(
        url,
        headers=gmail_headers(access_token),
        params={
            "q": build_search_query(config.processed_label, config.since_hours),
            "maxResults": config.max_results,
        },
        timeout=30,
    )
    payload = load_json_response(response)
    thread_ids = []
    seen = set()
    for message in payload.get("messages", []):
        thread_id = message.get("threadId")
        if thread_id and thread_id not in seen:
            seen.add(thread_id)
            thread_ids.append(thread_id)
    return thread_ids


def get_thread(access_token: str, thread_id: str) -> dict:
    url = f"https://gmail.googleapis.com/gmail/v1/users/{get_gmail_monitor_user()}/threads/{thread_id}"
    response = requests.get(
        url,
        headers=gmail_headers(access_token),
        params={"format": "full"},
        timeout=30,
    )
    return load_json_response(response)


def thread_candidate_from_payload(thread_payload: dict) -> ThreadCandidate | None:
    messages = thread_payload.get("messages") or []
    latest = choose_latest_message(messages)
    payload = latest.get("payload") or {}
    headers = payload.get("headers") or []
    subject = extract_header(headers, "Subject") or "(no subject)"
    sender = extract_header(headers, "From") or "unknown"
    received_at = (
        parse_datetime(latest.get("internalDate"))
        or parse_datetime(extract_header(headers, "Date"))
        or datetime.now(timezone.utc)
    )
    body = extract_plaintext(payload)
    snippet = latest.get("snippet") or ""
    thread_id = thread_payload.get("id")
    if not thread_id:
        return None
    return ThreadCandidate(
        thread_id=thread_id,
        subject=subject,
        sender=sender,
        received_at=received_at,
        body=body.strip(),
        snippet=snippet.strip(),
    )


def is_recent_enough(candidate: ThreadCandidate, config: MonitorConfig) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.since_hours)
    return candidate.received_at >= cutoff


def is_actionable_email(subject: str, body: str) -> tuple[bool, str]:
    for pattern in SKIP_SUBJECT_PATTERNS:
        if pattern.search(subject):
            return False, f"matched skip pattern: {pattern.pattern}"

    haystack = f"{subject}\n{body}"
    if any(keyword in haystack for keyword in ACTION_PATTERNS):
        return True, "matched action keywords"
    return False, "no actionable keywords"


def classify_category(subject: str, body: str) -> str:
    haystack = f"{subject}\n{body}".lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            return category
    return "other"


def infer_priority(subject: str, body: str) -> str:
    haystack = f"{subject}\n{body}".lower()
    for priority, keywords in URGENCY_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return priority
    return "medium"


def summarize_body(body: str, snippet: str, limit: int = 400) -> str:
    source = body or snippet or ""
    compact = re.sub(r"\s+", " ", source).strip()
    return compact[:limit]


def resolve_agent_map() -> dict[str, str]:
    url = f"{require_env('PAPERCLIP_API_URL', PAPERCLIP_API_URL)}/api/companies/{require_env('PAPERCLIP_COMPANY_ID', PAPERCLIP_COMPANY_ID)}/agents"
    response = requests.get(url, headers=paperclip_headers(), timeout=30)
    agents = load_json_response(response)
    by_name = {agent.get("name"): agent.get("id") for agent in agents}
    by_url_key = {agent.get("urlKey"): agent.get("id") for agent in agents}
    resolved = {}
    for category, owner in DEFAULT_ROUTING.items():
        resolved[category] = by_name.get(owner) or by_url_key.get(owner.lower())
    return resolved


def select_assignee_agent_id(category: str, assignee_map: dict[str, str]) -> str | None:
    return assignee_map.get(category) or assignee_map.get("other")


def find_existing_issue_for_thread(thread_id: str, project_id: str) -> dict | None:
    url = f"{require_env('PAPERCLIP_API_URL', PAPERCLIP_API_URL)}/api/companies/{require_env('PAPERCLIP_COMPANY_ID', PAPERCLIP_COMPANY_ID)}/issues"
    marker = f"Gmail Thread ID: {thread_id}"
    legacy_marker = f"Thread ID: {thread_id}"
    response = requests.get(
        url,
        headers=paperclip_headers(),
        params={"q": f"\"{marker}\"", "limit": 10},
        timeout=30,
    )
    issues = load_json_response(response)
    for issue in issues:
        if issue.get("projectId") != project_id:
            continue
        description = issue.get("description") or ""
        if marker in description or legacy_marker in description:
            return issue
    return None


def create_paperclip_issue(candidate: ThreadCandidate, category: str, priority: str, assignee_agent_id: str | None, config: MonitorConfig) -> dict:
    summary = summarize_body(candidate.body, candidate.snippet)
    url = f"{require_env('PAPERCLIP_API_URL', PAPERCLIP_API_URL)}/api/companies/{require_env('PAPERCLIP_COMPANY_ID', PAPERCLIP_COMPANY_ID)}/issues"
    payload = {
        "title": candidate.subject,
        "description": format_issue_description(candidate, summary, category),
        "status": "todo",
        "priority": priority,
        "goalId": config.goal_id,
        "projectId": config.project_id,
    }
    if assignee_agent_id:
        payload["assigneeAgentId"] = assignee_agent_id

    response = requests.post(url, headers=paperclip_headers(), json=payload, timeout=30)
    return load_json_response(response)


def format_issue_description(candidate: ThreadCandidate, summary: str, category: str) -> str:
    received = candidate.received_at.isoformat()
    body_preview = candidate.body[:1200] if candidate.body else candidate.snippet[:1200]
    return f"""**Email Source**: {candidate.sender}
**Received At**: {received}
**Subject**: {candidate.subject}
**Category**: {category}
**Gmail Thread ID**: {candidate.thread_id}
**Summary**: {summary}

**Content Preview**:
{body_preview}

---
_Auto-created from Gmail inbox monitoring (Gmail Thread ID: {candidate.thread_id})_"""


def find_label_id(access_token: str, label_name: str) -> str | None:
    if not label_name:
        return None

    url = f"https://gmail.googleapis.com/gmail/v1/users/{get_gmail_monitor_user()}/labels"
    response = requests.get(url, headers=gmail_headers(access_token), timeout=30)
    labels = load_json_response(response).get("labels", [])
    for label in labels:
        if label.get("name") == label_name:
            return label.get("id")
    return None


def ensure_label_id(access_token: str, label_name: str) -> str | None:
    existing_label_id = find_label_id(access_token, label_name)
    if existing_label_id:
        return existing_label_id

    create_response = requests.post(
        f"https://gmail.googleapis.com/gmail/v1/users/{get_gmail_monitor_user()}/labels",
        headers=gmail_headers(access_token),
        json={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
        timeout=30,
    )
    created = load_json_response(create_response)
    return created.get("id")


def mark_thread_processed_remote(access_token: str, thread_id: str, label_id: str | None) -> None:
    if not label_id:
        return

    url = f"https://gmail.googleapis.com/gmail/v1/users/{get_gmail_monitor_user()}/threads/{thread_id}/modify"
    response = requests.post(
        url,
        headers=gmail_headers(access_token),
        json={"addLabelIds": [label_id]},
        timeout=30,
    )
    response.raise_for_status()


def parse_args(argv: list[str]) -> MonitorConfig:
    since_hours_default = DEFAULT_SINCE_HOURS
    env_since_hours = os.environ.get("GMAIL_SINCE_HOURS")
    if env_since_hours:
        try:
            since_hours_default = clamp_since_hours(float(env_since_hours))
        except ValueError:
            raise RuntimeError("Invalid GMAIL_SINCE_HOURS value, must be a number")

    parser = argparse.ArgumentParser(description="Monitor Gmail inbox and create Paperclip issues")
    parser.add_argument("--preflight", action="store_true", help="Validate runtime configuration and API access without creating issues or modifying Gmail labels")
    parser.add_argument("--dry-run", action="store_true", help="Log intended actions without creating issues or modifying Gmail labels")
    parser.add_argument(
        "--since-hours",
        type=float,
        default=since_hours_default,
        help="Only process emails received within the last N hours",
    )
    parser.add_argument("--max-results", type=int, default=50, help="Maximum Gmail messages to inspect per run")
    parser.add_argument("--processed-label", default=os.environ.get("GMAIL_PROCESSED_LABEL", DEFAULT_PROCESSED_LABEL))
    parser.add_argument("--goal-id", default=os.environ.get("PAPERCLIP_GOAL_ID", DEFAULT_GOAL_ID))
    parser.add_argument("--project-id", default=os.environ.get("PAPERCLIP_PROJECT_ID", DEFAULT_PROJECT_ID))
    args = parser.parse_args(argv)
    since_hours = clamp_since_hours(args.since_hours)
    return MonitorConfig(
        preflight=args.preflight,
        dry_run=args.dry_run,
        since_hours=since_hours,
        max_results=args.max_results,
        processed_label=args.processed_label,
        goal_id=args.goal_id,
        project_id=args.project_id,
    )


def run_preflight(config: MonitorConfig) -> int:
    log("Running Gmail monitor preflight")

    required_env_names = [
        "PAPERCLIP_API_URL",
        "PAPERCLIP_API_KEY",
        "PAPERCLIP_COMPANY_ID",
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
    ]
    for env_name in required_env_names:
        require_env(env_name, os.environ.get(env_name))

    log(
        "Preflight config: "
        f"mailbox={get_gmail_monitor_user()}, "
        f"processed_label={config.processed_label or '(disabled)'}, "
        f"since_hours={config.since_hours}, "
        f"max_results={config.max_results}, "
        f"project_id={config.project_id}, "
        f"goal_id={config.goal_id}"
    )
    log(f"Preflight Gmail search query: {build_search_query(config.processed_label, config.since_hours)}")

    access_token = gmail_access_token()
    log("Preflight OAuth refresh succeeded")

    assignee_map = resolve_agent_map()
    unresolved_categories = [
        category for category, owner in DEFAULT_ROUTING.items() if owner and not assignee_map.get(category)
    ]
    if unresolved_categories:
        raise RuntimeError(f"Preflight failed to resolve assignee routing for: {', '.join(unresolved_categories)}")
    log("Preflight assignee routing resolved for all categories")

    existing_label_id = find_label_id(access_token, config.processed_label)
    if config.processed_label:
        if existing_label_id:
            log(f"Preflight processed label exists: {config.processed_label} ({existing_label_id})")
        else:
            log(f"Preflight processed label missing and will be created at runtime: {config.processed_label}")

    thread_ids = list_recent_thread_ids(access_token, config)
    log(f"Preflight Gmail list access succeeded ({len(thread_ids)} recent thread candidates)")
    log("Gmail monitor preflight completed")
    return 0


def process_thread(candidate: ThreadCandidate, access_token: str, label_id: str | None, assignee_map: dict[str, str], config: MonitorConfig) -> None:
    processed = load_processed_threads()
    if candidate.thread_id in processed:
        log(f"Thread {candidate.thread_id} already processed locally, skipping")
        return

    if not is_recent_enough(candidate, config):
        log(f"Thread {candidate.thread_id} is older than {config.since_hours}h window, skipping")
        return

    actionable, reason = is_actionable_email(candidate.subject, candidate.body)
    if not actionable:
        log(f"Thread {candidate.thread_id} skipped: {reason}")
        return

    existing_issue = find_existing_issue_for_thread(candidate.thread_id, config.project_id)
    if existing_issue:
        existing_identifier = existing_issue.get("identifier") or existing_issue.get("id") or "unknown"
        log(f"Thread {candidate.thread_id} already mapped to existing issue {existing_identifier}")
        save_processed_thread(candidate.thread_id, existing_identifier, candidate.subject, {"source": "existing_issue"})
        if not config.dry_run:
            mark_thread_processed_remote(access_token, candidate.thread_id, label_id)
        return

    category = classify_category(candidate.subject, candidate.body)
    priority = infer_priority(candidate.subject, candidate.body)
    assignee_agent_id = select_assignee_agent_id(category, assignee_map)

    if config.dry_run:
        log(
            f"DRY RUN: would create issue for {candidate.thread_id} "
            f"(category={category}, priority={priority}, assignee={assignee_agent_id})"
        )
        return

    issue = create_paperclip_issue(candidate, category, priority, assignee_agent_id, config)
    issue_identifier = issue.get("identifier") or issue.get("id") or "unknown"
    save_processed_thread(
        candidate.thread_id,
        issue_identifier,
        candidate.subject,
        {"category": category, "priority": priority, "assigneeAgentId": assignee_agent_id},
    )
    mark_thread_processed_remote(access_token, candidate.thread_id, label_id)
    log(f"Created issue {issue_identifier} for thread {candidate.thread_id}")


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv or sys.argv[1:])
    if config.preflight:
        return run_preflight(config)

    log("Starting Gmail inbox monitor")

    access_token = gmail_access_token()
    label_id = None if config.dry_run else ensure_label_id(access_token, config.processed_label)
    assignee_map = resolve_agent_map()
    thread_ids = list_recent_thread_ids(access_token, config)
    log(f"Found {len(thread_ids)} Gmail thread candidates")

    for thread_id in thread_ids:
        thread_payload = get_thread(access_token, thread_id)
        candidate = thread_candidate_from_payload(thread_payload)
        if not candidate:
            log("Skipping malformed thread payload without id")
            continue
        process_thread(candidate, access_token, label_id, assignee_map, config)

    log("Gmail inbox monitor completed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log(f"ERROR: {exc}")
        sys.exit(1)
