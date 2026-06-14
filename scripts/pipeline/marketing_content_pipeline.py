#!/usr/bin/env python3
"""
Marketing and summary content pipeline for published BCE reports.

The pipeline uses Korean Markdown reports as the source of truth, but only
publishes derived copy when a matching Korean slide report is already present
in `project_reports`. This keeps website summaries and marketing snippets
aligned with the published slide deck instead of re-OCRing PDFs.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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


LANGUAGES = ("ko", "en", "fr", "es", "de", "ja", "zh")
TARGET_LANGUAGES = ("en", "fr", "es", "de", "ja", "zh")
REPORT_TYPE_TO_DB = {
    "econ": "econ",
    "mat": "maturity",
    "for": "forensic",
}
DB_TYPE_TO_SHORT = {value: key for key, value in REPORT_TYPE_TO_DB.items()}

DEFAULT_SOURCE_FOLDER_ID = "1E87EcasPlrGuet0t6e1CA9kLFO0sTdFq"
SOURCE_FOLDER_ID = os.environ.get("BCE_MARKETING_SOURCE_FOLDER_ID", DEFAULT_SOURCE_FOLDER_ID)
DEFAULT_ECON_SOURCE_FOLDER_ID = "1vcSHC1Z2cbOKJvWTpw535JsGJPrffOtd"
ECON_SOURCE_FOLDER_ID = os.environ.get("BCE_MARKETING_ECON_SOURCE_FOLDER_ID", DEFAULT_ECON_SOURCE_FOLDER_ID)
DEFAULT_LEGACY_ECON_SOURCE_FOLDER_ID = "1iWkUkurWZtJ5pwGiuR3sQiiyANBJ9ZIc"
LEGACY_ECON_SOURCE_FOLDER_ID = os.environ.get(
    "BCE_MARKETING_LEGACY_ECON_SOURCE_FOLDER_ID",
    DEFAULT_LEGACY_ECON_SOURCE_FOLDER_ID,
)
DEFAULT_MAT_SOURCE_FOLDER_ID = "1-K4nMQcG3U-L1ro6YqBguCk2JUExlNcc"
MAT_SOURCE_FOLDER_ID = os.environ.get("BCE_MARKETING_MAT_SOURCE_FOLDER_ID", DEFAULT_MAT_SOURCE_FOLDER_ID)
DEFAULT_FOR_SOURCE_FOLDER_ID = "1eLyL9VSkwMM9TShea4Yd4WiveQuJfwKS"
FOR_SOURCE_FOLDER_ID = os.environ.get("BCE_MARKETING_FOR_SOURCE_FOLDER_ID") or DEFAULT_FOR_SOURCE_FOLDER_ID
ARCHIVE_FOLDER_ID = os.environ.get("BCE_MARKETING_ARCHIVE_FOLDER_ID", "")

MAX_WORDS = int(os.environ.get("BCE_MARKETING_MAX_WORDS", "100"))
BLOCKED_LOCAL_SOURCE_DIRS = (PIPELINE_DIR / "output",)
SOURCE_ALIAS_REGISTRY = {
    "bittensor": ("비텐서",),
    "cosmos-hub": ("cosmos",),
    "hedera-hashgraph": ("헤데라",),
    "humanity-protocol": ("humanity",),
    "mantle": ("맨틀",),
    "matic-network": ("polygon", "폴리곤"),
    "monero": ("모네로",),
    "polkadot": ("폴카닷",),
    "shiba-inu": ("시바이누",),
    "stellar": ("스텔라",),
    "tether-gold": ("테더골드", "tether gold"),
    "venice-token": ("venice.ai", "venice ai", "venice_ai"),
    "worldcoin": ("world",),
    "world-liberty-financial": ("wlf", "wlfi"),
}

FILENAME_RE = re.compile(r"^(?P<slug>.+)_(?P<type>econ|mat|for)_v(?P<version>\d+)_(?P<lang>[a-z]{2})\.md$", re.I)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$", re.M)
SUMMARY_BOILERPLATE_RE = re.compile(
    r"("
    r"개요\s*및\s*개념\s*정의|"
    r"개념\s*정의\s*목록|"
    r"Concept Definition List|"
    r"참조\s*방법론|"
    r"작성일\s*:|"
    r"분석\s*대상\s*:|"
    r"프로젝트\s*이름\s*:|"
    r"프로젝트\s*명칭\s*:|"
    r"메인넷\s*:|"
    r"프로젝트\s*분류\s*:|"
    r"핵심\s*비전\s*:|"
    r"온체인\s*매핑\s*여부|"
    r"온체인\s*State\s*매핑\s*여부|"
    r"크립토\s*이코노미\s*설계\s*방법론|"
    r"분석\s*보고서\s*작성\s*방법"
    r")",
    re.I,
)
LEADING_PROJECT_METADATA_RE = re.compile(
    r"^\s*.*?프로젝트\s*(?:이름|명칭)\s*:.*?"
    r"(?:\d+(?:\.\d+)*\s*)?개념\s*정의\s*목록(?:\s*\[[^\]]*\])?\s*",
    re.I | re.S,
)
LEADING_SECTION_FRAGMENT_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s*)?"
    r"(?:가치\s*시스템\s*(?:구조\s*및\s*서사|분석)?|보상\s*시스템\s*분석|"
    r"화폐\s*시스템\s*분석|부트스트래핑\s*전략|개념\s*정의(?:\s*목록)?)"
    r"(?:\s*\([^)]*\))?\s*",
    re.I,
)
DESCRIPTIVE_SENTENCE_START_RE = re.compile(
    r"(?:^|\s)([A-Za-z가-힣0-9][A-Za-z가-힣0-9()·._-]{1,60}(?:은|는|이|가)\s)",
    re.I,
)
PROJECT_METADATA_LABEL_RE = re.compile(
    r"("
    r"프로젝트\s*기본\s*정보|"
    r"프로젝트\s*(?:이름|명칭|분류)|"
    r"메인넷|"
    r"상태"
    r")\s*:?",
    re.I,
)
DESCRIPTIVE_SUBJECT_RE = re.compile(
    r"(?:^|\s)(?P<subject>[A-Za-z0-9가-힣][A-Za-z0-9가-힣().·+/\-]{0,40}(?:은|는))\s+"
)
PROJECT_NAME_VALUE_RE = re.compile(
    r"(?:\|\s*)?(?:\*\*)?프로젝트\s*(?:이름|명칭)(?:\*\*)?\s*(?:\||:|：)\s*(?P<value>[^|\n]+)",
    re.I,
)


@dataclass(frozen=True)
class MarkdownSource:
    slug: str
    report_type: str
    db_report_type: str
    version: int
    lang: str
    name: str
    text: str
    drive_file_id: Optional[str] = None
    modified_time: Optional[str] = None
    local_path: Optional[str] = None


@dataclass(frozen=True)
class DerivedContent:
    title: str
    summary_ko: str
    marketing_ko: str
    summary_by_lang: Dict[str, str]
    marketing_by_lang: Dict[str, str]


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value or "")


def _slug_parts(slug: str) -> List[str]:
    return [part for part in re.split(r"[-_\s]+", _normalize_text(slug).lower()) if part]


def _source_folder_id_for_report_type(report_type: str) -> str:
    if report_type == "econ":
        return ECON_SOURCE_FOLDER_ID
    if report_type == "mat":
        return MAT_SOURCE_FOLDER_ID
    if report_type == "for":
        if not FOR_SOURCE_FOLDER_ID:
            raise RuntimeError("BCE_MARKETING_FOR_SOURCE_FOLDER_ID must point to Google Drive analysis/FOR")
        return FOR_SOURCE_FOLDER_ID
    raise ValueError(f"Unsupported report_type: {report_type}")


def _source_folder_ids_for_report_type(report_type: str) -> List[str]:
    if report_type == "econ":
        return [
            folder_id
            for folder_id in (ECON_SOURCE_FOLDER_ID, LEGACY_ECON_SOURCE_FOLDER_ID)
            if folder_id
        ]
    return [_source_folder_id_for_report_type(report_type)]


def score_drive_source_for_project(file_name: str, project: Dict[str, Any]) -> int:
    """Score whether a natural-language Drive source filename belongs to a project."""
    file_lower = _normalize_text(file_name).lower()
    score = 0

    for raw_value in (project.get("name"), project.get("symbol")):
        value = _normalize_text(str(raw_value or "")).strip()
        if not value:
            continue
        value_lower = value.lower()
        if file_lower.startswith(f"{value_lower}의"):
            score = max(score, 100)
        elif file_lower.startswith(f"{value_lower} "):
            score = max(score, 90)
        elif re.search(rf"(?<![a-z0-9]){re.escape(value_lower)}(?![a-z0-9])", file_lower):
            score = max(score, 60)

    slug = str(project.get("slug") or "")
    parts = _slug_parts(slug)
    if parts and all(part in file_lower for part in parts):
        score = max(score, 70)

    aliases = project.get("aliases") or []
    if isinstance(aliases, list):
        for alias in aliases:
            alias_lower = _normalize_text(str(alias or "")).strip().lower()
            if not alias_lower:
                continue
            if file_lower.startswith(f"{alias_lower} ") or file_lower.startswith(f"{alias_lower}의"):
                score = max(score, 90)
            elif re.search(rf"(?<![a-z0-9가-힣]){re.escape(alias_lower)}(?![a-z0-9가-힣])", file_lower):
                score = max(score, 65)

    for alias in SOURCE_ALIAS_REGISTRY.get(slug, ()):
        alias_lower = _normalize_text(alias).lower()
        if file_lower.startswith(f"{alias_lower}의"):
            score = max(score, 100)
        elif file_lower.startswith(f"{alias_lower} "):
            score = max(score, 90)
        elif re.search(rf"(?<![a-z0-9가-힣]){re.escape(alias_lower)}(?![a-z0-9가-힣])", file_lower):
            score = max(score, 65)

    return score


def _parse_markdown_name(name: str) -> Optional[Tuple[str, str, int, str]]:
    match = FILENAME_RE.match(_normalize_text(name))
    if not match:
        return None
    slug = match.group("slug")
    report_type = match.group("type").lower()
    version = int(match.group("version"))
    lang = match.group("lang").lower()
    return slug, report_type, version, lang


def _word_count(text: str) -> int:
    return len([part for part in re.split(r"\s+", text.strip()) if part])


def _limit_words(text: str, max_words: int = MAX_WORDS) -> str:
    parts = [part for part in re.split(r"\s+", text.strip()) if part]
    if len(parts) <= max_words:
        return " ".join(parts)
    return " ".join(parts[:max_words]).rstrip(".,;:") + "..."


def _strip_markdown(markdown: str) -> str:
    text = _normalize_text(markdown)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^\s*>?\s*NOTE:\s+.*$", " ", text, flags=re.M | re.I)
    text = re.sub(r"^\s*>.*(?:오염 원본|quarantine|격리).*$", " ", text, flags=re.M | re.I)
    text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.M)
    text = re.sub(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", " ", text, flags=re.M)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+.+$", " ", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|])", r"\1", text)
    text = re.sub(r"[*_~>|]", " ", text)
    text = re.sub(r"\s*:?-{3,}:?\s*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _trim_leading_project_metadata(chunk: str) -> str:
    first_subject = DESCRIPTIVE_SUBJECT_RE.search(chunk)
    if first_subject and first_subject.start("subject") == 0:
        return chunk

    labels = list(PROJECT_METADATA_LABEL_RE.finditer(chunk))
    if not labels or labels[0].start() > 80:
        return chunk

    tail = chunk[labels[-1].end():].strip()
    match = DESCRIPTIVE_SUBJECT_RE.search(tail)
    if match:
        return tail[match.start("subject"):].strip()
    return ""


def _extract_title(markdown: str, fallback_slug: str) -> str:
    match = HEADING_RE.search(_normalize_text(markdown))
    if match:
        title = re.sub(r"[*_`]+", "", match.group("title")).strip()
        if title:
            return title
    return fallback_slug.replace("-", " ").title()


def _normalize_subject_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = _normalize_text(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9가-힣]+", " ", text)
    return " ".join(text.split())


def _source_subject_matches_project(source: MarkdownSource, project: Dict[str, Any]) -> bool:
    candidates = [
        _normalize_subject_token(match.group("value"))
        for match in PROJECT_NAME_VALUE_RE.finditer(source.text)
    ]
    candidates = [candidate for candidate in candidates if candidate]
    if not candidates:
        return True

    expected_tokens = {
        token
        for token in (
            _normalize_subject_token(project.get("name")),
            _normalize_subject_token(project.get("symbol")),
            _normalize_subject_token(project.get("slug")),
            _normalize_subject_token(source.slug),
        )
        if len(token) >= 2
    }

    if not expected_tokens:
        return True

    for candidate in candidates:
        if any(token in candidate or candidate in token for token in expected_tokens):
            return True
    return False


def _strip_leading_basic_info(chunk: str) -> str:
    if not re.search(r"프로젝트\s*(?:이름|명칭)", chunk, re.I):
        return chunk
    if not any(token in chunk for token in ("메인넷", "프로젝트 분류", "상태", "항목 상세 내용")):
        return chunk

    markers = [
        "프로젝트 이름",
        "프로젝트 명칭",
        "메인넷",
        "프로젝트 분류",
        "상태",
        "항목 상세 내용",
    ]
    last_marker_end = 0
    for marker in markers:
        match = re.search(re.escape(marker), chunk, re.I)
        if match:
            last_marker_end = max(last_marker_end, match.end())

    for match in DESCRIPTIVE_SENTENCE_START_RE.finditer(chunk):
        if match.start(1) > last_marker_end:
            return chunk[match.start(1):].strip()
    return ""


def _candidate_sentences(markdown: str) -> List[str]:
    clean = _strip_markdown(markdown)
    if not clean:
        return []
    chunks = re.split(r"(?<=[.!?。！？다요음임함됨됨니다])\s+", clean)
    sentences = []
    for chunk in chunks:
        chunk = chunk.strip()
        chunk = LEADING_PROJECT_METADATA_RE.sub("", chunk).strip()
        chunk = LEADING_SECTION_FRAGMENT_RE.sub("", chunk).strip()
        chunk = _strip_leading_basic_info(chunk).strip()
        chunk = _trim_leading_project_metadata(chunk)
        if len(chunk) < 24:
            continue
        if chunk.lower().startswith(("table ", "chapter ", "section ")):
            continue
        if chunk.startswith(("본 보고서는", "본 분석은")):
            continue
        if SUMMARY_BOILERPLATE_RE.search(chunk):
            continue
        if chunk.count(":") >= 3:
            continue
        sentences.append(chunk)
    return sentences


def _derive_korean_copy(source: MarkdownSource) -> Tuple[str, str, str]:
    title = _extract_title(source.text, source.slug)
    sentences = _candidate_sentences(source.text)
    if not sentences:
        fallback = _limit_words(_strip_markdown(source.text), MAX_WORDS)
        return title, fallback, fallback

    summary = _limit_words(" ".join(sentences[:3]), MAX_WORDS)

    marketing_candidates = [
        sentence for sentence in sentences
        if any(token in sentence for token in ("기회", "리스크", "투자", "시장", "성장", "평가", "결론", "전략"))
    ]
    marketing_base = " ".join((marketing_candidates or sentences)[-3:])
    marketing = _limit_words(marketing_base, MAX_WORDS)
    return title, summary, marketing


def _request_json(url: str, *, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Any:
    data = None
    headers = {"User-Agent": "bce-marketing-content-pipeline/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def _translate_with_google_free_endpoint(text: str, target: str) -> str:
    query = urllib.parse.urlencode({
        "client": "gtx",
        "sl": "ko",
        "tl": target,
        "dt": "t",
        "q": text,
    })
    result = _request_json(
        f"https://translate.googleapis.com/translate_a/single?{query}",
        method="GET",
    )
    if not isinstance(result, list) or not result or not isinstance(result[0], list):
        raise RuntimeError("Google free translation response had an unexpected shape")

    parts: List[str] = []
    for item in result[0]:
        if isinstance(item, list) and item and isinstance(item[0], str):
            parts.append(item[0])
    translated = "".join(parts).strip()
    if not translated:
        raise RuntimeError("Google free translation response did not include translated text")
    return translated


def _translate_with_google_cloud(text: str, target: str) -> str:
    project_id = os.environ.get("GOOGLE_CLOUD_TRANSLATE_PROJECT_ID", "").strip()
    location = os.environ.get("GOOGLE_CLOUD_TRANSLATE_LOCATION", "global").strip() or "global"
    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_TRANSLATE_PROJECT_ID is not configured")

    from google.cloud import translate_v3 as translate

    client = translate.TranslationServiceClient()
    parent = f"projects/{project_id}/locations/{location}"
    response = client.translate_text(
        request={
            "parent": parent,
            "contents": [text],
            "mime_type": "text/plain",
            "source_language_code": "ko",
            "target_language_code": target,
        }
    )
    translations = getattr(response, "translations", None) or []
    if not translations or not getattr(translations[0], "translated_text", ""):
        raise RuntimeError("Google Cloud Translation response did not include translated text")
    return translations[0].translated_text


def _translate_text(value: str, target: str) -> str:
    try:
        return _translate_with_google_free_endpoint(value, target)
    except Exception as free_exc:
        try:
            return _translate_with_google_cloud(value, target)
        except Exception as paid_exc:
            raise RuntimeError(
                f"Google translation failed for target language '{target}' "
                "(free endpoint failed, then Google Cloud Translation failed)"
            ) from paid_exc


def _translate_texts(texts: Dict[str, str], targets: Sequence[str], *, dry_run: bool = False) -> Dict[str, Dict[str, str]]:
    translated: Dict[str, Dict[str, str]] = {key: {"ko": value} for key, value in texts.items()}
    if dry_run:
        for key, value in texts.items():
            for lang in targets:
                translated[key][lang] = value
        return translated

    for key, value in texts.items():
        for lang in targets:
            translated[key][lang] = _translate_text(value, lang)
    return translated


def derive_content(source: MarkdownSource, *, translate: bool = True, dry_run: bool = False) -> DerivedContent:
    title, summary_ko, marketing_ko = _derive_korean_copy(source)
    if translate:
        translated = _translate_texts(
            {"summary": summary_ko, "marketing": marketing_ko},
            TARGET_LANGUAGES,
            dry_run=dry_run,
        )
        summary_by_lang = {lang: _limit_words(text, MAX_WORDS) for lang, text in translated["summary"].items()}
        marketing_by_lang = {lang: _limit_words(text, MAX_WORDS) for lang, text in translated["marketing"].items()}
    else:
        summary_by_lang = {"ko": summary_ko}
        marketing_by_lang = {"ko": marketing_ko}
    return DerivedContent(
        title=title,
        summary_ko=summary_ko,
        marketing_ko=marketing_ko,
        summary_by_lang=summary_by_lang,
        marketing_by_lang=marketing_by_lang,
    )


def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_file = os.environ.get(
        "GDRIVE_SERVICE_ACCOUNT_FILE",
        str(PIPELINE_DIR / ".gdrive_service_account.json"),
    )
    if not sa_file or not os.path.exists(sa_file):
        raise RuntimeError(f"GDRIVE_SERVICE_ACCOUNT_FILE missing or not found: {sa_file}")

    creds = service_account.Credentials.from_service_account_file(
        sa_file,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    delegate = os.environ.get("GDRIVE_DELEGATE_EMAIL", "zhang@coinlab.co.kr")
    if delegate:
        creds = creds.with_subject(delegate)
    return build("drive", "v3", credentials=creds)


def _list_drive_markdown_sources(service, folder_id: str) -> List[Dict[str, Any]]:
    query = (
        f"'{folder_id}' in parents "
        "and name contains '.md' "
        "and trashed = false"
    )
    rows: List[Dict[str, Any]] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, webViewLink)",
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        rows.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return rows


def _download_drive_text(service, file_id: str) -> str:
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    out = io.BytesIO()
    downloader = MediaIoBaseDownload(out, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return out.getvalue().decode("utf-8")


def _copy_drive_file(service, file_id: str, name: str, archive_folder_id: str) -> Optional[Dict[str, Any]]:
    if not archive_folder_id:
        return None
    return service.files().copy(
        fileId=file_id,
        body={"name": name, "parents": [archive_folder_id]},
        fields="id, name, webViewLink",
        supportsAllDrives=True,
    ).execute()


def load_drive_sources(folder_id: str = SOURCE_FOLDER_ID) -> List[MarkdownSource]:
    service = _get_drive_service()
    sources: List[MarkdownSource] = []
    for item in _list_drive_markdown_sources(service, folder_id):
        parsed = _parse_markdown_name(item.get("name", ""))
        if not parsed:
            continue
        slug, report_type, version, lang = parsed
        if lang != "ko":
            continue
        sources.append(MarkdownSource(
            slug=slug,
            report_type=report_type,
            db_report_type=REPORT_TYPE_TO_DB[report_type],
            version=version,
            lang=lang,
            name=item["name"],
            text=_download_drive_text(service, item["id"]),
            drive_file_id=item["id"],
            modified_time=item.get("modifiedTime"),
        ))
    return sources


def find_drive_source_for_project(
    project: Dict[str, Any],
    *,
    report_type: str,
    version: int,
    folder_id: Optional[str] = None,
    service: Any = None,
    min_score: int = 60,
    source_scope: str = "legacy",
) -> Optional[MarkdownSource]:
    """Find a Drive Markdown source for a project, including natural MAT filenames."""
    drive_service = service or _get_drive_service()
    source_folder_ids = [folder_id] if folder_id else _source_folder_ids_for_report_type(report_type)
    candidates: List[Dict[str, Any]] = []
    for source_folder_id in source_folder_ids:
        candidates.extend(_list_drive_markdown_sources(drive_service, source_folder_id))
    scored: List[Tuple[int, Dict[str, Any]]] = []

    for item in candidates:
        parsed = _parse_markdown_name(item.get("name", ""))
        if parsed:
            slug, parsed_type, parsed_version, lang = parsed
            if (
                slug == project.get("slug")
                and parsed_type == report_type
                and parsed_version == version
                and lang == "ko"
            ):
                scored.append((110, item))
                continue

        scored.append((score_drive_source_for_project(item.get("name", ""), project), item))

    scored = [(score, item) for score, item in scored if score >= min_score]
    if not scored:
        return None

    scored.sort(key=lambda pair: pair[0], reverse=True)
    item = scored[0][1]
    return MarkdownSource(
        slug=str(project.get("slug") or ""),
        report_type=report_type,
        db_report_type=REPORT_TYPE_TO_DB[report_type],
        version=version,
        lang="ko",
        name=item["name"],
        text=_download_drive_text(drive_service, item["id"]),
        drive_file_id=item["id"],
        modified_time=item.get("modifiedTime"),
    )


def build_project_report_patch_from_drive_source(
    source: MarkdownSource,
    *,
    translate: bool = True,
    source_web_view_link: Optional[str] = None,
) -> Dict[str, Any]:
    content = derive_content(source, translate=translate, dry_run=False)
    patch = build_project_report_patch(source, content)
    if source_web_view_link:
        patch["summary_source_md_archived_url"] = source_web_view_link
    card_data = patch.get("card_data") if isinstance(patch.get("card_data"), dict) else {}
    source_md = card_data.get("source_md") if isinstance(card_data.get("source_md"), dict) else {}
    patch["card_data"] = {
        **card_data,
        "summary": content.summary_by_lang.get("ko") or content.summary_ko,
        "summary_ko": content.summary_by_lang.get("ko") or content.summary_ko,
        "source_md": {
            **source_md,
            "source_folder": f"analysis/{source.report_type.upper()}",
        },
    }
    return patch


def load_local_sources(paths: Iterable[str]) -> List[MarkdownSource]:
    sources: List[MarkdownSource] = []
    for raw in paths:
        path = Path(raw)
        try:
            resolved_path = path.resolve()
        except OSError:
            resolved_path = path.absolute()
        if any(
            resolved_path == blocked.resolve() or blocked.resolve() in resolved_path.parents
            for blocked in BLOCKED_LOCAL_SOURCE_DIRS
        ):
            print(
                f"[SKIP] Refusing legacy/generated local source path: {path}. "
                "Use --source drive for production backfills.",
                file=sys.stderr,
            )
            continue
        if path.is_dir():
            candidates = sorted(path.glob("*_ko.md"))
        else:
            candidates = [path]
        for candidate in candidates:
            parsed = _parse_markdown_name(candidate.name)
            if not parsed:
                continue
            slug, report_type, version, lang = parsed
            if lang != "ko":
                continue
            sources.append(MarkdownSource(
                slug=slug,
                report_type=report_type,
                db_report_type=REPORT_TYPE_TO_DB[report_type],
                version=version,
                lang=lang,
                name=candidate.name,
                text=candidate.read_text(encoding="utf-8"),
                local_path=str(candidate),
            ))
    return sources


def _get_supabase_client():
    if not HAS_WAREHOUSE:
        return None
    wh = get_warehouse()
    if not getattr(wh, "connected", False):
        return None
    return getattr(wh, "sb", None) or getattr(wh, "client", None)


def assert_marketing_schema_available(sb) -> None:
    try:
        sb.table("project_reports").select(
            "id, marketing_content_by_lang, summary_source_md_file_id, "
            "summary_source_md_name, summary_source_md_archived_url, summary_generated_at"
        ).limit(1).execute()
    except Exception as exc:
        raise RuntimeError(
            "project_reports marketing metadata columns are not available. "
            "Apply supabase/migrations/20260505_add_marketing_content_metadata.sql "
            "and refresh the Supabase PostgREST schema cache before running a persisted backfill."
        ) from exc


def _as_bool_slide_present(value: Any) -> bool:
    if isinstance(value, dict):
        ko_value = value.get("ko")
        return isinstance(ko_value, str) and bool(ko_value.strip())
    return False


def find_matching_korean_slide_row(sb, source: MarkdownSource) -> Optional[Dict[str, Any]]:
    project_res = sb.table("tracked_projects").select("id, slug, name, symbol").eq("slug", source.slug).limit(1).execute()
    project_rows = project_res.data or []
    if not project_rows:
        return None

    project_id = project_rows[0]["id"]
    res = sb.table("project_reports").select(
        "id, project_id, report_type, version, language, status, "
        "slide_html_urls_by_lang, card_data, card_summary_ko"
    ).eq("project_id", project_id) \
        .eq("report_type", source.db_report_type) \
        .eq("version", source.version) \
        .eq("language", "ko") \
        .in_("status", ["published", "approved", "coming_soon"]) \
        .limit(1) \
        .execute()
    rows = res.data or []
    if not rows:
        return None

    row = rows[0]
    if not _as_bool_slide_present(row.get("slide_html_urls_by_lang")):
        return None
    row["_matched_project"] = project_rows[0]
    return row


def build_project_report_patch(
    source: MarkdownSource,
    content: DerivedContent,
    *,
    archived_drive_file: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    card_data = {
        "source_md": {
            "name": source.name,
            "slug": source.slug,
            "report_type": source.report_type,
            "version": source.version,
            "language": "ko",
            "drive_file_id": source.drive_file_id,
            "archived_drive_file_id": (archived_drive_file or {}).get("id"),
            "archived_drive_url": (archived_drive_file or {}).get("webViewLink"),
            "modified_time": source.modified_time,
        },
        "summary_by_lang": content.summary_by_lang,
        "marketing_by_lang": content.marketing_by_lang,
        "marketing_generated_at": datetime.now(timezone.utc).isoformat(),
    }

    patch: Dict[str, Any] = {
        "card_data": card_data,
        "marketing_content_by_lang": content.marketing_by_lang,
        "summary_source_md_file_id": source.drive_file_id,
        "summary_source_md_name": source.name,
        "summary_source_md_archived_url": (archived_drive_file or {}).get("webViewLink"),
        "summary_generated_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    for lang, summary in content.summary_by_lang.items():
        patch[f"card_summary_{lang}"] = summary
    return {key: value for key, value in patch.items() if value is not None}


def persist_content(sb, row: Dict[str, Any], source: MarkdownSource, content: DerivedContent, archived: Optional[Dict[str, Any]]) -> None:
    existing_card = row.get("card_data") if isinstance(row.get("card_data"), dict) else {}
    patch = build_project_report_patch(source, content, archived_drive_file=archived)
    patch["card_data"] = {
        **existing_card,
        **patch["card_data"],
        "summary": content.summary_by_lang.get("ko") or content.summary_ko,
    }
    sb.table("project_reports").update(patch).eq("id", row["id"]).execute()


def _archive_source_if_needed(source: MarkdownSource) -> Optional[Dict[str, Any]]:
    if not source.drive_file_id or not ARCHIVE_FOLDER_ID:
        return None
    service = _get_drive_service()
    return _copy_drive_file(service, source.drive_file_id, source.name, ARCHIVE_FOLDER_ID)


def run_pipeline(
    sources: Sequence[MarkdownSource],
    *,
    persist: bool,
    translate: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    sb = None if not persist else _get_supabase_client()
    if persist and sb is None:
        raise RuntimeError("Supabase warehouse client is not available")
    if sb is not None:
        assert_marketing_schema_available(sb)

    stats = {"seen": 0, "matched": 0, "updated": 0, "skipped": 0, "items": []}
    for source in sources:
        stats["seen"] += 1
        content = derive_content(source, translate=translate, dry_run=dry_run)
        item = {
            "source": source.name,
            "slug": source.slug,
            "report_type": source.report_type,
            "version": source.version,
            "summary_words_ko": _word_count(content.summary_ko),
            "marketing_words_ko": _word_count(content.marketing_ko),
            "status": "derived",
        }

        row = None if sb is None else find_matching_korean_slide_row(sb, source)
        if persist and sb is not None and row is None:
            item["status"] = "skipped_no_matching_korean_slide"
            stats["skipped"] += 1
            stats["items"].append(item)
            continue

        if row is not None:
            if not _source_subject_matches_project(source, row.get("_matched_project") or {}):
                item["status"] = "skipped_subject_mismatch"
                item["project_report_id"] = row.get("id")
                stats["skipped"] += 1
                stats["items"].append(item)
                continue

            stats["matched"] += 1
            item["project_report_id"] = row.get("id")

        if persist and sb is not None:
            if dry_run:
                item["status"] = "matched_dry_run"
            else:
                archived = _archive_source_if_needed(source)
                persist_content(sb, row, source, content, archived)
                stats["updated"] += 1
                item["status"] = "updated"
                if archived:
                    item["archived_drive_file_id"] = archived.get("id")

        stats["items"].append(item)
    return stats


def _filter_sources(
    sources: Sequence[MarkdownSource],
    *,
    slugs: Sequence[str],
    report_type: Optional[str],
    version: Optional[int],
    limit: Optional[int],
) -> List[MarkdownSource]:
    selected: List[MarkdownSource] = []
    slug_set = {_normalize_text(slug) for slug in slugs}
    for source in sources:
        if slug_set and source.slug not in slug_set:
            continue
        if report_type and source.report_type != report_type:
            continue
        if version is not None and source.version != version:
            continue
        selected.append(source)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate website summary and marketing copy from Korean report Markdown.")
    parser.add_argument("--source", choices=["drive", "local"], default="drive")
    parser.add_argument("--source-folder-id", default=SOURCE_FOLDER_ID)
    parser.add_argument("--local-path", action="append", default=[])
    parser.add_argument("--slug", action="append", default=[], help="Only process this project/report slug. Repeatable.")
    parser.add_argument("--report-type", choices=["econ", "mat", "for"], help="Only process one report type.")
    parser.add_argument("--version", type=int, help="Only process one report version.")
    parser.add_argument("--limit", type=int, help="Maximum number of sources to process after filters.")
    parser.add_argument("--no-translate", action="store_true")
    parser.add_argument("--persist", action="store_true", help="Update matching project_reports rows.")
    parser.add_argument("--dry-run", action="store_true", help="Derive and, with --persist, match rows without writing updates.")
    args = parser.parse_args(argv)

    if args.source == "drive":
        sources = load_drive_sources(args.source_folder_id)
    else:
        sources = load_local_sources(args.local_path)
    sources = _filter_sources(
        sources,
        slugs=args.slug,
        report_type=args.report_type,
        version=args.version,
        limit=args.limit,
    )

    stats = run_pipeline(
        sources,
        persist=args.persist,
        translate=not args.no_translate,
        dry_run=args.dry_run,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
