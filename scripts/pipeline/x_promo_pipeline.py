#!/usr/bin/env python3
"""
Generate manual-approval X promo drafts from published report marketing copy.

The module consumes report rows that already contain `marketing_content_by_lang`
and writes a file-based approval queue. It never sends posts directly; every
generated draft starts in `pending_manual_approval`.
"""
from __future__ import annotations

import argparse
import base64
import hmac
import hashlib
import json
import os
import re
import secrets
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence
from urllib import parse, request


PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent.parent

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

try:
    from pipeline_env import bootstrap_environment
    bootstrap_environment(PIPELINE_DIR)
except Exception:
    pass

try:
    from collectors.warehouse import get_warehouse
    HAS_WAREHOUSE = True
except Exception:
    HAS_WAREHOUSE = False


X_MAX_CHARS = 280
DEFAULT_REPORT_URL_BASE = "https://bcelab.xyz/reports"
DEFAULT_QUEUE_DIR = REPO_ROOT / "data" / "x-approval-queue"
DEFAULT_POST_LOG = REPO_ROOT / "data" / "x-post-attempts.jsonl"
DEFAULT_X_CREATE_TWEET_URL = "https://api.x.com/2/tweets"
SUPPORTED_LANGUAGES = ("ko", "en", "fr", "es", "de", "ja", "zh")
DEFAULT_TEMPLATES = ("insight-first", "chart-report-first", "risk-opportunity-first")
REQUIRED_POST_ENV = (
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_TOKEN_SECRET",
)

TONE_RULES: Dict[str, Dict[str, str]] = {
    "ko": {
        "brand": "BCE Lab",
        "cta": "리포트 보기",
        "insight": "데이터가 먼저 말합니다",
        "chart": "새 리포트 공개",
        "risk": "리스크와 기회를 함께 봅니다",
    },
    "en": {
        "brand": "BCE Lab",
        "cta": "Read the report",
        "insight": "Data first",
        "chart": "New report",
        "risk": "Risk and opportunity, side by side",
    },
    "fr": {
        "brand": "BCE Lab",
        "cta": "Lire le rapport",
        "insight": "Les donnees d'abord",
        "chart": "Nouveau rapport",
        "risk": "Risques et opportunites, ensemble",
    },
    "es": {
        "brand": "BCE Lab",
        "cta": "Leer el informe",
        "insight": "Primero los datos",
        "chart": "Nuevo informe",
        "risk": "Riesgo y oportunidad, juntos",
    },
    "de": {
        "brand": "BCE Lab",
        "cta": "Bericht lesen",
        "insight": "Daten zuerst",
        "chart": "Neuer Bericht",
        "risk": "Risiko und Chance zusammen",
    },
    "ja": {
        "brand": "BCE Lab",
        "cta": "レポートを読む",
        "insight": "データを起点に",
        "chart": "新レポート公開",
        "risk": "リスクと機会を同時に見る",
    },
    "zh": {
        "brand": "BCE Lab",
        "cta": "阅读报告",
        "insight": "以数据为先",
        "chart": "新报告发布",
        "risk": "同时审视风险与机会",
    },
}


@dataclass(frozen=True)
class XPromoReport:
    id: str
    slug: str
    report_type: str
    version: int
    marketing_content_by_lang: Dict[str, str]
    card_summary_by_lang: Optional[Dict[str, str]] = None
    title_by_lang: Optional[Dict[str, str]] = None
    published_at: Optional[str] = None
    report_url_by_lang: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class XPromoDraft:
    duplicate_key: str
    report_id: str
    slug: str
    report_type: str
    version: int
    language: str
    template: str
    status: str
    text: str
    char_count: int
    report_url: str
    audit: Dict[str, Any]


@dataclass(frozen=True)
class XCredentials:
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str
    bearer_token: Optional[str] = None

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "XCredentials":
        source = env or os.environ
        missing = [name for name in REQUIRED_POST_ENV if not source.get(name)]
        if missing:
            raise RuntimeError(
                "Missing X credentials for --post: "
                + ", ".join(missing)
                + ". Dry-run does not require credentials."
            )
        return cls(
            api_key=str(source["X_API_KEY"]),
            api_secret=str(source["X_API_SECRET"]),
            access_token=str(source["X_ACCESS_TOKEN"]),
            access_token_secret=str(source["X_ACCESS_TOKEN_SECRET"]),
            bearer_token=source.get("X_BEARER_TOKEN"),
        )


@dataclass(frozen=True)
class XPostResult:
    post_id: str
    text: str
    raw: Dict[str, Any]


class XPoster(Protocol):
    def post_tweet(self, text: str) -> XPostResult:
        ...


class XApiClient:
    def __init__(
        self,
        credentials: XCredentials,
        *,
        create_tweet_url: str = DEFAULT_X_CREATE_TWEET_URL,
        timeout: int = 30,
    ) -> None:
        self.credentials = credentials
        self.create_tweet_url = create_tweet_url
        self.timeout = timeout

    def post_tweet(self, text: str) -> XPostResult:
        body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.create_tweet_url,
            data=body,
            headers={
                "Authorization": self._oauth_header("POST", self.create_tweet_url),
                "Content-Type": "application/json",
                "User-Agent": "bce-lab-x-manual-poster/1.0",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))

        data = payload.get("data") or {}
        post_id = str(data.get("id") or "")
        if not post_id:
            raise RuntimeError(f"X API response did not include a post id: {payload}")
        return XPostResult(post_id=post_id, text=str(data.get("text") or text), raw=payload)

    def _oauth_header(self, method: str, url: str) -> str:
        oauth_params = {
            "oauth_consumer_key": self.credentials.api_key,
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.credentials.access_token,
            "oauth_version": "1.0",
        }
        signature = _oauth1_signature(
            method,
            url,
            oauth_params,
            self.credentials.api_secret,
            self.credentials.access_token_secret,
        )
        signed_params = {**oauth_params, "oauth_signature": signature}
        return "OAuth " + ", ".join(
            f'{_percent_encode(key)}="{_percent_encode(value)}"'
            for key, value in sorted(signed_params.items())
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_text(value: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", value or "")
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"\[([^\]]*?)\]\([^)]*?\)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _percent_encode(value: Any) -> str:
    return parse.quote(str(value), safe="~-._")


def _oauth1_signature(
    method: str,
    url: str,
    oauth_params: Dict[str, str],
    api_secret: str,
    access_token_secret: str,
) -> str:
    parsed = parse.urlsplit(url)
    normalized_url = parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    query_params = dict(parse.parse_qsl(parsed.query, keep_blank_values=True))
    signature_params = {**query_params, **oauth_params}
    normalized_params = "&".join(
        f"{_percent_encode(key)}={_percent_encode(value)}"
        for key, value in sorted(signature_params.items())
    )
    base = "&".join([
        method.upper(),
        _percent_encode(normalized_url),
        _percent_encode(normalized_params),
    ])
    signing_key = f"{_percent_encode(api_secret)}&{_percent_encode(access_token_secret)}"
    digest = hmac.new(signing_key.encode("utf-8"), base.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _truncate_to_limit(value: str, limit: int) -> str:
    value = _clean_text(value)
    if len(value) <= limit:
        return value
    if limit <= 1:
        return "…"[:limit]

    shortened = value[: limit - 1].rstrip()
    last_space = shortened.rfind(" ")
    if last_space >= max(16, int(limit * 0.55)):
        shortened = shortened[:last_space].rstrip()
    return shortened.rstrip(".,;:") + "…"


def _title_for(report: XPromoReport, language: str) -> str:
    titles = report.title_by_lang or {}
    return (
        titles.get(language)
        or titles.get("en")
        or titles.get("ko")
        or report.slug.replace("-", " ").title()
    )


def _report_url(report: XPromoReport, language: str, base_url: str) -> str:
    urls = report.report_url_by_lang or {}
    if urls.get(language):
        return urls[language]
    if urls.get("en"):
        return urls["en"]
    return f"{base_url.rstrip('/')}/{report.slug}"


def _content_for(report: XPromoReport, language: str) -> Optional[tuple[str, str]]:
    content = report.marketing_content_by_lang or {}
    card_summaries = report.card_summary_by_lang or {}
    candidates = [
        (content.get(language), "project_reports.marketing_content_by_lang"),
        (card_summaries.get(language), f"project_reports.card_summary_{language}"),
        (content.get("en"), "project_reports.marketing_content_by_lang"),
        (card_summaries.get("en"), "project_reports.card_summary_en"),
        (content.get("ko"), "project_reports.marketing_content_by_lang"),
        (card_summaries.get("ko"), "project_reports.card_summary_ko"),
    ]
    for raw, source_field in candidates:
        if isinstance(raw, str) and raw.strip():
            return _clean_text(raw), source_field
    return None


def _render_template(
    *,
    template: str,
    language: str,
    title: str,
    content: str,
    url: str,
) -> str:
    tone = TONE_RULES.get(language, TONE_RULES["en"])
    if template == "insight-first":
        prefix = f"{tone['insight']}: "
        suffix = f" {tone['cta']}: {url}"
    elif template == "chart-report-first":
        prefix = f"{tone['chart']} - {title}. "
        suffix = f" {url}"
    elif template == "risk-opportunity-first":
        prefix = f"{tone['risk']}: "
        suffix = f" {tone['brand']} | {url}"
    else:
        raise ValueError(f"Unsupported X promo template: {template}")

    available = X_MAX_CHARS - len(prefix) - len(suffix)
    if available < 24:
        raise ValueError(f"Report URL leaves too little room for X copy: {url}")
    body = _truncate_to_limit(content, available)
    return f"{prefix}{body}{suffix}"


def _duplicate_key(report: XPromoReport, language: str, template: str, url: str) -> str:
    stable = "|".join([
        report.id,
        report.slug,
        report.report_type,
        str(report.version),
        language,
        template,
        url,
    ])
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]


def generate_x_promo_drafts(
    reports: Sequence[XPromoReport],
    *,
    languages: Sequence[str] = ("ko", "en"),
    templates: Sequence[str] = DEFAULT_TEMPLATES,
    report_url_base: str = DEFAULT_REPORT_URL_BASE,
    generated_at: Optional[str] = None,
) -> List[XPromoDraft]:
    generated = generated_at or _now_iso()
    drafts: List[XPromoDraft] = []
    seen_keys = set()

    for report in reports:
        for language in languages:
            if language not in SUPPORTED_LANGUAGES:
                raise ValueError(f"Unsupported language for X promo copy: {language}")
            copy_source = _content_for(report, language)
            if not copy_source:
                continue
            content, source_field = copy_source

            title = _title_for(report, language)
            url = _report_url(report, language, report_url_base)
            for template in templates:
                text = _render_template(
                    template=template,
                    language=language,
                    title=title,
                    content=content,
                    url=url,
                )
                key = _duplicate_key(report, language, template, url)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                drafts.append(XPromoDraft(
                    duplicate_key=key,
                    report_id=report.id,
                    slug=report.slug,
                    report_type=report.report_type,
                    version=report.version,
                    language=language,
                    template=template,
                    status="pending_manual_approval",
                    text=text,
                    char_count=len(text),
                    report_url=url,
                    audit={
                        "generated_at": generated,
                        "source_field": source_field,
                        "published_at": report.published_at,
                        "approval_default": "manual",
                    },
                ))
    return drafts


def _draft_to_json(draft: XPromoDraft) -> Dict[str, Any]:
    return asdict(draft)


def _draft_from_json(row: Dict[str, Any]) -> XPromoDraft:
    return XPromoDraft(
        duplicate_key=str(row["duplicate_key"]),
        report_id=str(row["report_id"]),
        slug=str(row["slug"]),
        report_type=str(row["report_type"]),
        version=int(row.get("version") or 1),
        language=str(row["language"]),
        template=str(row["template"]),
        status=str(row.get("status") or "pending_manual_approval"),
        text=str(row["text"]),
        char_count=int(row.get("char_count") or len(str(row["text"]))),
        report_url=str(row["report_url"]),
        audit=dict(row.get("audit") or {}),
    )


def load_approval_queue(path: Path) -> List[XPromoDraft]:
    drafts: List[XPromoDraft] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            drafts.append(_draft_from_json(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"Invalid approval queue row {path}:{line_number}: {exc}") from exc
    return drafts


def _read_post_log(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid X post log row {path}:{line_number}: {exc}") from exc
    return rows


def has_successful_post(duplicate_key: str, *, log_path: Path = DEFAULT_POST_LOG) -> bool:
    return any(
        row.get("duplicate_key") == duplicate_key and row.get("status") == "posted"
        for row in _read_post_log(log_path)
    )


def append_post_log(entry: Dict[str, Any], *, log_path: Path = DEFAULT_POST_LOG) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def select_approved_drafts(
    drafts: Sequence[XPromoDraft],
    *,
    confirm_slug: Optional[str],
    confirm_key: Optional[str] = None,
) -> List[XPromoDraft]:
    approved = [draft for draft in drafts if draft.status == "approved"]
    if confirm_slug:
        approved = [draft for draft in approved if draft.slug == confirm_slug]
    if confirm_key:
        approved = [draft for draft in approved if draft.duplicate_key == confirm_key]
    return approved


def validate_single_post_selection(
    selected: Sequence[XPromoDraft],
    *,
    confirm_slug: Optional[str],
    confirm_key: Optional[str],
    allow_multiple: bool = False,
) -> None:
    selector = confirm_key or confirm_slug or "<none>"
    if not selected:
        raise RuntimeError(f"No approved X promo drafts found for confirmed selector: {selector}")
    if not allow_multiple and len(selected) != 1:
        raise RuntimeError(
            "Refusing to post multiple approved X promo drafts in one command: "
            f"matched {len(selected)} rows for {selector}. "
            "Use --confirm-key <duplicate_key> to select exactly one approved draft."
        )


def send_approved_drafts(
    drafts: Sequence[XPromoDraft],
    *,
    poster: XPoster,
    confirm_slug: Optional[str],
    confirm_key: Optional[str] = None,
    allow_multiple: bool = False,
    log_path: Path = DEFAULT_POST_LOG,
) -> List[Dict[str, Any]]:
    selected = select_approved_drafts(drafts, confirm_slug=confirm_slug, confirm_key=confirm_key)
    validate_single_post_selection(
        selected,
        confirm_slug=confirm_slug,
        confirm_key=confirm_key,
        allow_multiple=allow_multiple,
    )

    results: List[Dict[str, Any]] = []
    for draft in selected:
        if has_successful_post(draft.duplicate_key, log_path=log_path):
            result = {
                "duplicate_key": draft.duplicate_key,
                "slug": draft.slug,
                "language": draft.language,
                "template": draft.template,
                "status": "duplicate_skipped",
                "attempted_at": _now_iso(),
            }
            append_post_log(result, log_path=log_path)
            results.append(result)
            continue

        attempt = {
            "duplicate_key": draft.duplicate_key,
            "slug": draft.slug,
            "language": draft.language,
            "template": draft.template,
            "status": "attempting",
            "attempted_at": _now_iso(),
            "char_count": draft.char_count,
            "report_url": draft.report_url,
        }
        append_post_log(attempt, log_path=log_path)
        try:
            posted = poster.post_tweet(draft.text)
        except Exception as exc:
            failure = {**attempt, "status": "failed", "error": str(exc)}
            append_post_log(failure, log_path=log_path)
            raise

        success = {
            **attempt,
            "status": "posted",
            "posted_at": _now_iso(),
            "x_post_id": posted.post_id,
        }
        append_post_log(success, log_path=log_path)
        results.append(success)
    return results


def write_approval_queue(
    drafts: Sequence[XPromoDraft],
    *,
    output_dir: Path = DEFAULT_QUEUE_DIR,
    run_id: Optional[str] = None,
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = output_dir / f"x-promo-approval-{stamp}.jsonl"
    markdown_path = output_dir / f"x-promo-approval-{stamp}.md"

    with jsonl_path.open("w", encoding="utf-8") as out:
        for draft in drafts:
            out.write(json.dumps(_draft_to_json(draft), ensure_ascii=False, sort_keys=True) + "\n")

    lines = [
        "# X Promo Approval Queue",
        "",
        f"- Run ID: `{stamp}`",
        f"- Draft count: {len(drafts)}",
        "- Default status: `pending_manual_approval`",
        "- Reviewer action: change status to `approved` or `rejected` in the JSONL queue before any sender consumes it.",
        "",
    ]
    for draft in drafts:
        lines.extend([
            f"## {draft.slug} / {draft.language} / {draft.template}",
            "",
            f"- Duplicate key: `{draft.duplicate_key}`",
            f"- Characters: {draft.char_count}/280",
            f"- URL: {draft.report_url}",
            "",
            "```text",
            draft.text,
            "```",
            "",
        ])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")

    return {"jsonl": str(jsonl_path), "markdown": str(markdown_path)}


def load_reports_from_json(path: Path) -> List[XPromoReport]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("reports", [])
    reports: List[XPromoReport] = []
    for row in rows:
        reports.append(XPromoReport(
            id=str(row["id"]),
            slug=str(row["slug"]),
            report_type=str(row["report_type"]),
            version=int(row.get("version") or 1),
            marketing_content_by_lang=dict(row.get("marketing_content_by_lang") or {}),
            card_summary_by_lang={
                lang: row.get(f"card_summary_{lang}")
                for lang in SUPPORTED_LANGUAGES
                if row.get(f"card_summary_{lang}")
            },
            title_by_lang=dict(row.get("title_by_lang") or {}),
            published_at=row.get("published_at"),
            report_url_by_lang=dict(row.get("report_url_by_lang") or {}),
        ))
    return reports


def _get_supabase_client():
    if not HAS_WAREHOUSE:
        return None
    wh = get_warehouse()
    if not getattr(wh, "connected", False):
        return None
    return getattr(wh, "sb", None) or getattr(wh, "client", None)


def load_reports_from_supabase(limit: int) -> List[XPromoReport]:
    sb = _get_supabase_client()
    if sb is None:
        raise RuntimeError("Supabase warehouse client is not available")

    res = sb.table("project_reports").select(
        "id, report_type, version, marketing_content_by_lang, published_at, "
        "card_summary_ko, card_summary_en, card_summary_fr, card_summary_es, "
        "card_summary_de, card_summary_ja, card_summary_zh, "
        "title_en, title_ko, title_fr, title_es, title_de, title_ja, title_zh, "
        "project:tracked_projects(slug)"
    ).in_("status", ["published", "approved", "coming_soon"]) \
        .order("published_at", desc=True) \
        .limit(limit) \
        .execute()

    reports: List[XPromoReport] = []
    for row in res.data or []:
        marketing_content = row.get("marketing_content_by_lang")
        if not isinstance(marketing_content, dict):
            marketing_content = {}
        card_summary_by_lang = {
            lang: row.get(f"card_summary_{lang}")
            for lang in SUPPORTED_LANGUAGES
            if row.get(f"card_summary_{lang}")
        }
        if not marketing_content and not card_summary_by_lang:
            continue
        project = row.get("project") or {}
        slug = project.get("slug")
        if not slug:
            continue
        reports.append(XPromoReport(
            id=str(row["id"]),
            slug=str(slug),
            report_type=str(row["report_type"]),
            version=int(row.get("version") or 1),
            marketing_content_by_lang=dict(marketing_content),
            card_summary_by_lang=card_summary_by_lang,
            title_by_lang={
                lang: row.get(f"title_{lang}")
                for lang in SUPPORTED_LANGUAGES
                if row.get(f"title_{lang}")
            },
            published_at=row.get("published_at"),
        ))
    return reports


def _split_csv(values: Sequence[str]) -> List[str]:
    selected: List[str] = []
    for value in values:
        selected.extend([part.strip() for part in value.split(",") if part.strip()])
    return selected


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate, dry-run, or manually post approved X promo copy.")
    parser.add_argument("--source", choices=["json", "supabase"], default="json")
    parser.add_argument("--input-json", type=Path, help="Local JSON report rows for --source json.")
    parser.add_argument("--queue-jsonl", type=Path, help="Approved JSONL queue to dry-run or post.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum Supabase rows to load.")
    parser.add_argument("--language", action="append", help="Language or comma list. Repeatable.")
    parser.add_argument("--template", action="append", help="Template or comma list. Repeatable.")
    parser.add_argument("--report-url-base", default=DEFAULT_REPORT_URL_BASE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_QUEUE_DIR)
    parser.add_argument("--run-id", help="Stable output filename suffix for auditability.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned drafts/posts. This is the default unless --post is set.")
    parser.add_argument("--write-queue", action="store_true", help="Write manual approval queue files for generated drafts.")
    parser.add_argument("--post", action="store_true", help="Actually post one approved queue row to X. Requires --queue-jsonl and --confirm or --confirm-key.")
    parser.add_argument("--confirm", help="Slug that the operator explicitly approves for --post.")
    parser.add_argument("--confirm-key", help="Exact duplicate_key that the operator explicitly approves for --post.")
    parser.add_argument("--allow-multiple-posts", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--post-log", type=Path, default=DEFAULT_POST_LOG, help="JSONL post attempt/result log.")
    parser.add_argument("--x-create-tweet-url", default=DEFAULT_X_CREATE_TWEET_URL, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.post and not args.queue_jsonl:
        raise SystemExit("--post requires --queue-jsonl")
    if args.post and not (args.confirm or args.confirm_key):
        raise SystemExit("--post requires --confirm <slug> or --confirm-key <duplicate_key>")
    if args.confirm and not re.fullmatch(r"[A-Za-z0-9._~:-]+", args.confirm):
        raise SystemExit("--confirm must be a single slug without spaces or shell metacharacters")
    if args.confirm_key and not re.fullmatch(r"[A-Za-z0-9._~:-]+", args.confirm_key):
        raise SystemExit("--confirm-key must be a single duplicate_key without spaces or shell metacharacters")

    if args.queue_jsonl:
        drafts = load_approval_queue(args.queue_jsonl)
        selected = select_approved_drafts(
            drafts,
            confirm_slug=args.confirm,
            confirm_key=args.confirm_key,
        )
        if args.post:
            validate_single_post_selection(
                selected,
                confirm_slug=args.confirm,
                confirm_key=args.confirm_key,
                allow_multiple=args.allow_multiple_posts,
            )
            credentials = XCredentials.from_env()
            poster = XApiClient(credentials, create_tweet_url=args.x_create_tweet_url)
            result = send_approved_drafts(
                drafts,
                poster=poster,
                confirm_slug=args.confirm,
                confirm_key=args.confirm_key,
                allow_multiple=args.allow_multiple_posts,
                log_path=args.post_log,
            )
            print(json.dumps({"posted": len([row for row in result if row["status"] == "posted"]), "results": result}, ensure_ascii=False, indent=2))
            return 0

        print(json.dumps({
            "dry_run": True,
            "approved_candidates": len(selected),
            "requires_post_flags": "--post --confirm-key <duplicate_key>",
            "posts": [_draft_to_json(draft) for draft in selected],
        }, ensure_ascii=False, indent=2))
        return 0

    if args.source == "json":
        if args.input_json is None:
            raise SystemExit("--input-json is required with --source json")
        reports = load_reports_from_json(args.input_json)
    else:
        reports = load_reports_from_supabase(args.limit)

    drafts = generate_x_promo_drafts(
        reports[: args.limit],
        languages=_split_csv(args.language or ["ko,en"]),
        templates=_split_csv(args.template or [",".join(DEFAULT_TEMPLATES)]),
        report_url_base=args.report_url_base,
    )

    if args.write_queue:
        result = write_approval_queue(drafts, output_dir=args.output_dir, run_id=args.run_id)
        print(json.dumps({"drafts": len(drafts), **result}, ensure_ascii=False, indent=2))
        return 0

    if args.dry_run or not args.write_queue:
        print(json.dumps([_draft_to_json(draft) for draft in drafts], ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
