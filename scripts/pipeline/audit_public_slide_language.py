#!/usr/bin/env python3
"""Audit published slide HTML for locale/content mismatches.

This command is intentionally conservative:
- identical HTML across sibling language slots is always a repair candidate;
- direct text or optional OCR that contradicts a CJK route locale is a repair
  candidate;
- missing URLs are reported but do not imply wrong-language content.

Use `--fixture` in tests or incident reproduction. Without a fixture, the
command reads `project_reports.slide_html_urls_by_lang` from Supabase.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import ssl
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from urllib.request import Request, urlopen

try:
    import certifi
except Exception:  # pragma: no cover - certifi is present in pipeline envs
    certifi = None  # type: ignore[assignment]

PIPELINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPELINE_DIR))

from pipeline_env import bootstrap_environment  # noqa: E402
from watch_slides_inspection import _detect_language_content_mismatch  # noqa: E402


LANGS = ("ko", "en", "ja", "zh")
REPORT_TYPES = ("econ", "maturity", "forensic")
TYPE_TO_STORAGE = {
    "econ": "econ",
    "maturity": "mat",
    "forensic": "for",
}
DATA_IMAGE_RE = re.compile(
    r"data:(image/(?:png|jpe?g|webp));base64,([A-Za-z0-9+/=\n\r]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SlideEntry:
    slug: str
    report_type: str
    lang: str
    url: str
    rank: int | None = None
    report_id: str | None = None
    project_id: str | None = None

    @property
    def group_key(self) -> tuple[str, str]:
        return self.slug, self.report_type


def _env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _supabase_client():
    bootstrap_environment(PIPELINE_DIR)
    url = _env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
    key = _env("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
    from supabase import create_client

    return create_client(url, key)


def _latest_market_ranks(sb, rank_limit: int | None) -> dict[str, int]:
    if not rank_limit:
        return {}
    latest_res = (
        sb.table("market_data_daily")
        .select("recorded_at")
        .order("recorded_at", desc=True)
        .limit(1)
        .execute()
    )
    latest_rows = latest_res.data or []
    if not latest_rows:
        return {}
    recorded_at = latest_rows[0]["recorded_at"]
    rows: list[dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        res = (
            sb.table("market_data_daily")
            .select("slug, cmc_rank")
            .eq("recorded_at", recorded_at)
            .not_.is_("cmc_rank", "null")
            .lte("cmc_rank", rank_limit)
            .order("cmc_rank")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    ranks: dict[str, int] = {}
    for row in rows:
        slug = str(row.get("slug") or "")
        try:
            rank = int(row.get("cmc_rank"))
        except Exception:
            continue
        if slug:
            ranks[slug] = rank
    return ranks


def _iter_report_rows(sb) -> Iterable[dict[str, Any]]:
    cols = (
        "id,project_id,report_type,language,status,is_latest,"
        "slide_html_urls_by_lang,published_at,updated_at"
    )
    offset = 0
    page_size = 1000
    while True:
        res = (
            sb.table("project_reports")
            .select(cols)
            .in_("report_type", list(REPORT_TYPES))
            .eq("is_latest", True)
            .not_.is_("slide_html_urls_by_lang", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = res.data or []
        yield from batch
        if len(batch) < page_size:
            break
        offset += page_size


def _load_project_slugs(sb) -> dict[str, str]:
    rows: list[dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        res = (
            sb.table("tracked_projects")
            .select("id,slug")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return {
        str(row["id"]): str(row["slug"])
        for row in rows
        if row.get("id") and row.get("slug")
    }


def _entries_from_supabase(rank_limit: int | None, slugs: set[str] | None) -> list[SlideEntry]:
    sb = _supabase_client()
    ranks = _latest_market_ranks(sb, rank_limit)
    project_slugs = _load_project_slugs(sb)
    entries: list[SlideEntry] = []
    for row in _iter_report_rows(sb):
        slug = project_slugs.get(str(row.get("project_id") or ""))
        if not slug:
            continue
        if slugs and slug not in slugs:
            continue
        if ranks and slug not in ranks:
            continue
        urls = row.get("slide_html_urls_by_lang")
        if not isinstance(urls, dict):
            continue
        for lang, url in urls.items():
            if lang not in LANGS or not isinstance(url, str) or not url.startswith("http"):
                continue
            entries.append(
                SlideEntry(
                    slug=slug,
                    report_type=str(row.get("report_type") or ""),
                    lang=lang,
                    url=url,
                    rank=ranks.get(slug),
                    report_id=str(row.get("id") or ""),
                    project_id=str(row.get("project_id") or ""),
                )
            )
    return entries


def _entries_from_fixture(path: Path) -> list[SlideEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("entries", raw if isinstance(raw, list) else [])
    entries: list[SlideEntry] = []
    for row in rows:
        entries.append(
            SlideEntry(
                slug=str(row["slug"]),
                report_type=str(row["report_type"]),
                lang=str(row["lang"]),
                url=str(row["url"]),
                rank=row.get("rank"),
                report_id=row.get("report_id"),
                project_id=row.get("project_id"),
            )
        )
    return entries


def _build_conventional_entries(slugs: Iterable[str], report_types: Iterable[str], base_url: str) -> list[SlideEntry]:
    entries: list[SlideEntry] = []
    for slug in sorted(set(slugs)):
        for report_type in report_types:
            storage_type = TYPE_TO_STORAGE[report_type]
            for lang in LANGS:
                url = f"{base_url.rstrip('/')}/{storage_type}/{slug}/latest/{lang}.html"
                entries.append(SlideEntry(slug=slug, report_type=report_type, lang=lang, url=url))
    return entries


def _fetch_url(url: str, timeout: int = 30) -> bytes:
    if url.startswith("file://"):
        return Path(url[7:]).read_bytes()
    context = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()
    req = Request(url, headers={"User-Agent": "bcelab-slide-language-audit/1.0"})
    with urlopen(req, timeout=timeout, context=context) as response:
        return response.read()


def _decode_html(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _direct_text(html: str) -> str:
    no_scripts = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    no_styles = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", no_scripts, flags=re.IGNORECASE)
    return re.sub(r"<[^>]+>", " ", no_styles)


def _first_data_images(html: str, max_images: int) -> list[bytes]:
    images: list[bytes] = []
    for _mime, payload in DATA_IMAGE_RE.findall(html):
        try:
            images.append(base64.b64decode(re.sub(r"\s+", "", payload), validate=False))
        except Exception:
            continue
        if len(images) >= max_images:
            break
    return images


def _ocr_image_bytes(image_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return ""
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        return pytesseract.image_to_string(image, lang="eng+kor+jpn+chi_sim") or ""
    except Exception:
        return ""


def _audit_entry(entry: SlideEntry, raw: bytes, *, ocr: bool, max_images: int) -> dict[str, Any]:
    html = _decode_html(raw)
    text = _direct_text(html)
    image_bytes = _first_data_images(html, max_images=max_images)
    ocr_text = ""
    if ocr:
        ocr_text = "\n".join(_ocr_image_bytes(blob) for blob in image_bytes)
    mismatch = _detect_language_content_mismatch(entry.lang, text, ocr_text, "audit")
    sha = hashlib.sha256(raw).hexdigest()
    return {
        "slug": entry.slug,
        "rank": entry.rank,
        "report_type": entry.report_type,
        "lang": entry.lang,
        "url": entry.url,
        "report_id": entry.report_id,
        "project_id": entry.project_id,
        "status": "ok",
        "sha256": sha,
        "content_length": len(raw),
        "embedded_image_count": len(image_bytes),
        "language_mismatch": mismatch,
    }


def _duplicate_groups(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
    for row in results:
        if row.get("status") != "ok":
            continue
        key = (
            str(row["slug"]),
            str(row["report_type"]),
            str(row["sha256"]),
            int(row["content_length"]),
        )
        by_group.setdefault(key, []).append(row)
    duplicate_groups = []
    for (slug, report_type, sha, content_length), rows in sorted(by_group.items()):
        langs = sorted({str(row["lang"]) for row in rows})
        if len(langs) <= 1:
            continue
        duplicate_groups.append({
            "slug": slug,
            "report_type": report_type,
            "langs": langs,
            "sha256": sha,
            "content_length": content_length,
            "urls": {str(row["lang"]): row["url"] for row in rows},
        })
    return duplicate_groups


def _repair_candidates(results: list[dict[str, Any]], duplicate_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in results:
        mismatch = row.get("language_mismatch")
        if mismatch:
            candidates.append({
                "reason": "language_mismatch",
                "slug": row["slug"],
                "report_type": row["report_type"],
                "lang": row["lang"],
                "url": row["url"],
                "mismatch": mismatch,
            })
    for group in duplicate_groups:
        candidates.append({
            "reason": "duplicate_html_across_languages",
            **group,
        })
    return candidates


def run_audit(entries: list[SlideEntry], *, ocr: bool = False, max_images: int = 1) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for entry in entries:
        try:
            raw = _fetch_url(entry.url)
            results.append(_audit_entry(entry, raw, ocr=ocr, max_images=max_images))
        except Exception as exc:
            results.append({
                "slug": entry.slug,
                "rank": entry.rank,
                "report_type": entry.report_type,
                "lang": entry.lang,
                "url": entry.url,
                "report_id": entry.report_id,
                "project_id": entry.project_id,
                "status": "fetch_error",
                "error": str(exc),
            })
    duplicate_groups = _duplicate_groups(results)
    candidates = _repair_candidates(results, duplicate_groups)
    summary = {
        "entry_count": len(entries),
        "ok": sum(1 for row in results if row.get("status") == "ok"),
        "fetch_error": sum(1 for row in results if row.get("status") == "fetch_error"),
        "language_mismatch": sum(1 for row in results if row.get("language_mismatch")),
        "duplicate_groups": len(duplicate_groups),
        "repair_candidates": len(candidates),
    }
    return {
        "summary": summary,
        "repair_candidates": candidates,
        "duplicate_groups": duplicate_groups,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit public slide HTML language consistency")
    parser.add_argument("--fixture", type=Path, help="JSON fixture with entries [{slug,report_type,lang,url}]")
    parser.add_argument("--slug", action="append", default=[], help="Slug to audit; repeatable")
    parser.add_argument("--report-type", choices=REPORT_TYPES, action="append", default=[])
    parser.add_argument("--rank-limit", type=int, help="Only audit latest market-data rows up to this CMC rank")
    parser.add_argument("--base-url", default="https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/slides")
    parser.add_argument("--conventional-urls", action="store_true", help="Build storage URLs from --slug instead of Supabase")
    parser.add_argument("--ocr", action="store_true", help="OCR embedded slide images with tesseract for CJK mismatch checks")
    parser.add_argument("--max-images", type=int, default=1)
    parser.add_argument("--output", default="scripts/pipeline/output/slide_language_audit.json")
    parser.add_argument("--fail-on-findings", action="store_true")
    args = parser.parse_args()

    report_types = args.report_type or list(REPORT_TYPES)
    slugs = set(args.slug) if args.slug else None
    if args.fixture:
        entries = _entries_from_fixture(args.fixture)
    elif args.conventional_urls:
        if not slugs:
            raise SystemExit("--conventional-urls requires at least one --slug")
        entries = _build_conventional_entries(slugs, report_types, args.base_url)
    else:
        entries = _entries_from_supabase(args.rank_limit, slugs)
        if args.report_type:
            entries = [entry for entry in entries if entry.report_type in report_types]

    output = run_audit(entries, ocr=args.ocr, max_images=max(1, args.max_images))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**output["summary"], "output": str(output_path)}, ensure_ascii=False, indent=2))
    if args.fail_on_findings and output["summary"]["repair_candidates"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
