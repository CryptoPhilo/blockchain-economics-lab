"""
Unified Report Ingest Pipeline — BCE-732

Replaces the FOR-only ingest_for.py with a report-type-agnostic pipeline.
Handles ECON, MAT, and FOR reports through a single code path:

    drafts/{TYPE}/{slug}_{type}_v{N}.md (한국어 초안)
        ↓ Download
    [1] 종목 확정 (파일명 + 본문 분석)
    [2] 번역 (ko → en)
    [3] PDF 생성 (타입별 PDF 생성기)
    [4] QA 검증
    [5] GDrive 업로드 ({slug}/{type}/)
    [6] Supabase: 'coming_soon' → 'published'

Usage:
    python ingest_report.py --type for              # FOR 전체
    python ingest_report.py --type econ --slug bitcoin
    python ingest_report.py --type mat --dry-run
    python ingest_report.py --type for --force      # 재처리
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import signal
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline_env import bootstrap_environment

bootstrap_environment()

from config import LANGUAGES, OUTPUT_DIR, INGEST_CONFIG
from translate_md import translate_md_file
from qa_verify import verify_pdf, QASeverity
from qa_verify_md import verify_markdown
from gdrive_storage import GDriveStorage
from gdrive_drafts import (
    download_markdown_text,
    ensure_drafts_type_folder,
    find_or_create_folder,
    scan_markdown_drafts,
)
from pipeline_state import PipelineState

TERMINAL_CONTENT_STATUS = 'content_failed_terminal'
RETRIABLE_PROCESSING_STATUS = 'processing_error'
TERMINAL_STATUSES = {TERMINAL_CONTENT_STATUS}


class TerminalContentError(RuntimeError):
    pass


class ProcessingInterruptedError(RuntimeError):
    pass


_LAST_TERMINATION_SIGNAL = None


def _is_qa_strict_enabled() -> bool:
    """Whether strict QA mode is enabled from environment."""
    value = os.environ.get('QA_STRICT', '0').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


def _required_publish_languages() -> list[str]:
    """
    Languages that must complete before a report can be published.

    Default is the current operational publish set from config. Operators can
    override the set explicitly if the policy changes.
    """
    raw = os.environ.get('INGEST_REQUIRED_PUBLISH_LANGUAGES', '').strip()
    if not raw:
        return list(LANGUAGES)

    required = []
    for lang in raw.split(','):
        normalized = lang.strip()
        if normalized and normalized in LANGUAGES and normalized not in required:
            required.append(normalized)
    return required or list(LANGUAGES)


def _next_retry_count(existing_run: dict | None) -> int:
    if not existing_run:
        return 0

    retry_count = int(existing_run.get('retry_count', 0) or 0)
    status = existing_run.get('status')
    if status in TERMINAL_STATUSES or status in {'done', 'published', 'dry_run', 'pending', None}:
        return retry_count
    return retry_count + 1


def _termination_signal_handler(signum, _frame):
    global _LAST_TERMINATION_SIGNAL
    _LAST_TERMINATION_SIGNAL = signum
    signal_name = signal.Signals(signum).name
    raise ProcessingInterruptedError(f'Interrupted by {signal_name}')


def _register_signal_handlers():
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _termination_signal_handler)


def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    sa_file = os.environ.get('GDRIVE_SERVICE_ACCOUNT_FILE', '').strip()
    sa_json = os.environ.get('GDRIVE_SERVICE_ACCOUNT_JSON', '').strip()
    if sa_json:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa_json),
            scopes=['https://www.googleapis.com/auth/drive'],
        )
    elif sa_file:
        creds = service_account.Credentials.from_service_account_file(
            sa_file, scopes=['https://www.googleapis.com/auth/drive'])
    else:
        raise RuntimeError('GDrive credentials not configured. Set GDRIVE_SERVICE_ACCOUNT_FILE or GDRIVE_SERVICE_ACCOUNT_JSON.')
    delegate = os.environ.get('GDRIVE_DELEGATE_EMAIL', '').strip()
    if delegate:
        creds = creds.with_subject(delegate)
    return build('drive', 'v3', credentials=creds)


def _get_supabase_client():
    url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def _normalize_slug_token(s: str | None) -> str:
    if not s:
        return ''
    s = unicodedata.normalize('NFC', s)
    s = s.lower().strip().replace(' ', '-')
    s = re.sub(r'[^a-z0-9가-힣ぁ-んァ-ヶ一-龥\-]', '', s)
    return re.sub(r'-+', '-', s).strip('-')


# Korean project name → canonical English slug.
# Mirrors the KNOWN_NAMES_KO mapping in ingest_gdoc.py. Drafts authored with
# Korean filenames (e.g. "카르다노-프로젝트-진행률-평가-보고서_mat_v1.md") would
# otherwise reach Supabase publish with a Korean slug that has no row in
# tracked_projects. We translate the leading Korean term to its canonical
# English slug before lookup.
KO_NAME_TO_SLUG: dict[str, str] = {
    '비트코인': 'bitcoin', '이더리움': 'ethereum', '솔라나': 'solana',
    '카르다노': 'cardano', '리플': 'ripple', '폴카닷': 'polkadot',
    '체인링크': 'chainlink', '아발란체': 'avalanche-2', '니어': 'near',
    '아비트럼': 'arbitrum', '유니스왑': 'uniswap', '아베': 'aave',
    '트론': 'tron', '도지코인': 'dogecoin', '바이낸스코인': 'binancecoin',
    '인터넷컴퓨터': 'internet-computer', '폴리곤': 'matic-network',
    '비트코인-캐시': 'bitcoin-cash', '비트코인캐시': 'bitcoin-cash',
    '스텔라': 'stellar', '앱토스': 'aptos',
    '리도-파이낸스': 'lido-dao', '리도파이낸스': 'lido-dao',
    '알고랜드': 'algorand',
    '플레어-네트워크': 'flare-networks', '플레어네트워크': 'flare-networks',
    '온도-파이낸스': 'ondo-finance', '온도파이낸스': 'ondo-finance',
    '테더': 'tether', '헤데라': 'hedera-hashgraph',
    '모네로': 'monero', '하이퍼리퀴드': 'hyperliquid',
    '스토리-프로토콜': 'story-protocol', '스토리프로토콜': 'story-protocol',
    '월렛커넥트': 'walletconnect',
    '페이팔': 'paypal-usd', '페이팔-usd': 'paypal-usd', 'pyusd': 'paypal-usd',
    '라이트코인': 'litecoin', '메이커다오': 'maker',
    '스카이-프로토콜': 'maker', '스카이프로토콜': 'maker',
    '칸톤-네트워크': 'canton-network', '칸톤네트워크': 'canton-network', '칸톤': 'canton-network',
    '월드-리버티-파이낸셜': 'world-liberty-financial',
    '리버-프로토콜': 'river-protocol', '리버프로토콜': 'river-protocol',
    '크로스': 'cross-crypto',
    '맨틀-네트워크': 'mantle', '맨틀네트워크': 'mantle', '맨틀': 'mantle',
    '테더-골드': 'tether-gold', '테더골드': 'tether-gold',
    '크로노스': 'cronos',
    '파이-네트워크': 'pi-network', '파이네트워크': 'pi-network',
    '게이트체인': 'gatechain', '코스모스': 'cosmos', '카스파': 'kaspa',
    '렌더': 'render-token', '파일코인': 'filecoin',
    '이더리움클래식': 'ethereum-classic', '이더리움-클래식': 'ethereum-classic',
    '비트겟': 'bitget-token', '페페': 'pepe',
}


def _korean_slug_to_canonical(raw_slug: str) -> str | None:
    """Translate a slug that begins with a known Korean project name to the
    canonical English slug. Returns None when no Korean prefix matches.

    Examples:
        "카르다노-프로젝트-진행률-평가-보고서" → "cardano"
        "비트코인-캐시" → "bitcoin-cash"
        "cardano" → None  (already canonical)
    """
    if not raw_slug:
        return None
    needle = unicodedata.normalize('NFC', raw_slug).lower()
    # Longer keys first so "비트코인-캐시" wins over "비트코인".
    for ko_name, en_slug in sorted(
        KO_NAME_TO_SLUG.items(), key=lambda kv: -len(kv[0])
    ):
        ko = unicodedata.normalize('NFC', ko_name).lower()
        if needle == ko or needle.startswith(ko + '-'):
            return en_slug
    return None


def _resolve_project_slug(sb, raw_slug: str) -> tuple:
    _fields = 'id, slug, name, symbol'
    raw_slug = unicodedata.normalize('NFC', raw_slug)

    # Build the ordered candidate list. If the slug starts with a known Korean
    # project name, try the canonical English slug first so MAT/ECON drafts
    # named in Korean still resolve in Supabase tracked_projects.
    candidates: list[str] = []
    canonical_from_korean = _korean_slug_to_canonical(raw_slug)
    if canonical_from_korean:
        candidates.append(canonical_from_korean)
    if raw_slug not in candidates:
        candidates.append(raw_slug)

    for slug_attempt in candidates:
        proj = sb.table('tracked_projects').select(_fields).eq('slug', slug_attempt).execute()
        if proj.data:
            p = proj.data[0]
            return p['id'], p['slug'], p.get('name'), p.get('symbol')

    for slug_attempt in candidates:
        symbol_candidate = slug_attempt.split('-')[0].upper()
        # Only treat ASCII tokens as ticker symbols; Korean text upper-cases
        # to itself and would otherwise hit the DB pointlessly.
        if symbol_candidate and re.match(r'^[A-Z0-9]+$', symbol_candidate):
            proj = sb.table('tracked_projects').select(_fields).eq('symbol', symbol_candidate).execute()
            if proj.data:
                p = proj.data[0]
                return p['id'], p['slug'], p.get('name'), p.get('symbol')

    for slug_attempt in candidates:
        name_part = slug_attempt.split('-')[0]
        if name_part:
            proj = sb.table('tracked_projects').select(_fields).ilike('name', f'%{name_part}%').execute()
            if proj.data:
                p = proj.data[0]
                return p['id'], p['slug'], p.get('name'), p.get('symbol')
    return None, None, None, None


def _load_pdf_generator(report_type: str):
    cfg = INGEST_CONFIG[report_type]
    mod_name, func_name = cfg['pdf_generator'].rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name)


def _load_card_generator(report_type: str):
    cfg = INGEST_CONFIG[report_type]
    if not cfg.get('card_generator'):
        return None
    mod_name, func_name = cfg['card_generator'].rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name)


# ═══════════════════════════════════════════
# Equation Image Stripper (from ingest_for.py)
# ═══════════════════════════════════════════

_IMG_REF_RE = re.compile(r'!\[([^\]]*)\]\[image\d+\]')
_IMG_DEF_RE = re.compile(r'^\[image\d+\]:\s*<data:image/[^>]+>$', re.MULTILINE)


def _strip_equation_images(md_text: str) -> tuple[str, int]:
    refs = _IMG_REF_RE.findall(md_text)
    cleaned = _IMG_REF_RE.sub('', md_text)
    cleaned = _IMG_DEF_RE.sub('', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned, len(refs)


# ═══════════════════════════════════════════
# GDrive Scanning
# ═══════════════════════════════════════════

def scan_drafts(report_type: str, filter_slug: str = None, force: bool = False,
                pipeline_state: PipelineState = None) -> list[dict]:
    """Scan GDrive drafts/{TYPE}/ for new .md files."""
    cfg = INGEST_CONFIG[report_type]
    service = _get_drive_service()
    root_id = os.environ.get('GDRIVE_ROOT_FOLDER_ID', '')
    if not root_id:
        print("[ERROR] GDRIVE_ROOT_FOLDER_ID not set")
        return []

    type_folder_id = ensure_drafts_type_folder(service, root_id, report_type)
    ps = pipeline_state
    if ps is None:
        try:
            ps = PipelineState(report_type)
        except Exception as exc:
            print(f"  [WARN] PipelineState unavailable: {exc}")

    files = scan_markdown_drafts(service, type_folder_id)
    filter_slug = _normalize_slug_token(filter_slug)

    sb = None
    try:
        sb = _get_supabase_client()
    except Exception as exc:
        print(f"  [WARN] Supabase client unavailable during slug resolution: {exc}")

    print(f"  [SCAN] Found {len(files)} total files in drafts/{cfg['gdrive_folder']}/")
    for f in files:
        mt = f.get('mimeType', 'unknown')
        gdoc = ' (Google Doc)' if f.get('_gdoc') else ''
        print(f"    • {f['name']} [{mt}]{gdoc} id={f['id'][:8]}...")

    filename_re = re.compile(cfg['filename_pattern'], re.IGNORECASE)
    new_files = []
    for f in files:
        fid = f['id']
        name = f['name']
        if not name.endswith('.md'):
            continue

        slug_match = filename_re.match(name)
        if not slug_match:
            print(f"    [SKIP] {name} — filename doesn't match pattern")
            continue
        raw_slug = _normalize_slug_token(slug_match.group(1))
        canonical_slug = None
        project_name = None
        symbol = None
        if sb:
            try:
                _, canonical_slug, project_name, symbol = _resolve_project_slug(sb, raw_slug)
            except Exception as exc:
                print(f"    [WARN] slug resolution failed for {name}: {exc}")

        if filter_slug:
            normalized_filter = _normalize_slug_token(filter_slug)
            slug_to_check = canonical_slug or raw_slug
            if normalized_filter not in (raw_slug, canonical_slug or '', (symbol or '').lower()):
                continue

        slug = canonical_slug or raw_slug

        # Check state via PipelineState
        existing_run = None
        retry_count = 0
        if ps:
            should, existing_run = ps.should_process(fid, force=force)
            if not should:
                skip_status = existing_run.get('status', '?') if existing_run else '?'
                print(f"    [SKIP] {name} — {skip_status}")
                continue
            retry_count = _next_retry_count(existing_run)

        is_retry = existing_run is not None and existing_run.get('status') not in (None, 'dry_run', 'pending')
        if is_retry:
            old_status = existing_run.get('status', '?')
            print(f"    [RETRY] {name} (was: {old_status}, attempt #{retry_count})")

        new_files.append({
            'file_id': fid,
            'name': name,
            'slug': slug,
            'source_slug': raw_slug,
            'canonical_slug': canonical_slug,
            'project_name': project_name,
            'symbol': symbol,
            'size': int(f.get('size', 0)),
            'modified': f.get('modifiedTime'),
            '_gdoc': f.get('_gdoc', False),
            '_retry_count': retry_count,
        })

    return new_files


# ═══════════════════════════════════════════
# Report Processing
# ═══════════════════════════════════════════

def process_report(report_type: str, file_info: dict, dry_run: bool = False) -> dict:
    """Process a single report: download → translate → PDF → QA → upload → publish"""
    cfg = INGEST_CONFIG[report_type]
    slug = file_info['slug']
    fid = file_info['file_id']
    version = 1
    result = {'slug': slug, 'file_id': fid, 'status': 'started', 'report_type': report_type}

    print(f"\n{'─'*50}")
    print(f"Processing [{report_type.upper()}]: {file_info['name']} → {slug}")
    print(f"{'─'*50}")

    # Resolve project metadata
    if not file_info.get('project_name') or not file_info.get('symbol'):
        try:
            _sb = _get_supabase_client()
            if _sb:
                _pid, _cslug, _pname, _psym = _resolve_project_slug(_sb, slug)
                if _pname and not file_info.get('project_name'):
                    file_info['project_name'] = _pname
                if _psym and not file_info.get('symbol'):
                    file_info['symbol'] = _psym
                if _pname or _psym:
                    print(f"  ✓ Project resolved: {_pname} ({_psym})")
        except Exception as e:
            print(f"  [WARN] Project metadata lookup failed: {e}")

    # 1. Download
    master_lang = cfg['master_lang']
    md_path = os.path.join(OUTPUT_DIR, f'{slug}_{report_type}_v{version}_{master_lang}.md')
    is_gdoc = file_info.get('_gdoc', False)
    print(f"[1/6] 다운로드{' (Google Doc export)' if is_gdoc else ''}...")
    try:
        service = _get_drive_service()
        content = download_markdown_text(service, fid, is_gdoc=is_gdoc)
        Path(md_path).write_text(content, encoding='utf-8')
        print(f"  ✓ {md_path} ({Path(md_path).stat().st_size:,} bytes)")
    except Exception as e:
        result['status'] = 'download_error'
        result['error'] = str(e)[:200]
        print(f"  ✗ 다운로드 실패: {e}")
        return result

    # 1b. Strip equation images
    try:
        raw_md = Path(md_path).read_text(encoding='utf-8')
        if '![][image' in raw_md:
            print("[1b/6] 수식 이미지 제거...")
            cleaned_md, eq_count = _strip_equation_images(raw_md)
            if eq_count > 0:
                Path(md_path).write_text(cleaned_md, encoding='utf-8')
                result['equation_images_stripped'] = eq_count
        else:
            print("[1b/6] 수식 이미지 없음 — 건너뜀")
    except Exception as e:
        print(f"  [WARN] 수식 이미지 제거 실패 (계속 진행): {e}")

    # 1c. Pre-translation markdown QA
    try:
        md_qa = verify_markdown(md_path, lang=master_lang)
        md_fails = [c for c in md_qa.checks if c.severity == QASeverity.FAIL]
        if md_fails:
            fail_names = [c.name for c in md_fails]
            print(f"  ⚠ Markdown QA FAIL: {fail_names}")
            result['md_qa_fail'] = fail_names
            # BCE-867: section_markers FAIL means body has zero ## headings,
            # which produces a 3-page cover-only PDF. Abort before wasting
            # translation/PDF cycles instead of failing later in qa_verify.
            if 'md.structure.section_markers' in fail_names:
                raise TerminalContentError(
                    'md.structure.section_markers FAIL — '
                    'source markdown has no H2 sections; '
                    'PDF body would be empty (BCE-867)'
                )
        else:
            print(f"  ✓ Markdown QA passed")
    except TerminalContentError:
        raise
    except Exception as e:
        print(f"  [WARN] Markdown QA error (계속 진행): {e}")

    if dry_run:
        result['status'] = 'dry_run'
        print("  [DRY RUN] 다운로드만 완료")
        return result

    # 2. Translate
    target_langs = [l for l in LANGUAGES if l != master_lang]
    print(f"[2/6] 번역 ({master_lang} → {', '.join(target_langs)}) — parallel mode...")
    translated = {master_lang: md_path}
    google_request_count_total = 0

    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

    def _translate_one(lang):
        started = time.time()
        out_path, meta = translate_md_file(
            md_path,
            target_lang=lang,
            output_dir=OUTPUT_DIR,
            backend='google_cloud',
            strict=True,
        )
        return lang, out_path, meta, time.time() - started

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_translate_one, lang): lang for lang in target_langs}
        pending = set(futures)
        try:
            while pending:
                done, pending = wait(pending, timeout=30, return_when=FIRST_COMPLETED)
                if not done:
                    still_running = ', '.join(sorted(futures[f] for f in pending))
                    print(f"  … 번역 진행 중 (30s 경과): {still_running}")
                    continue
                for future in done:
                    lang = futures[future]
                    try:
                        lang, out_path, meta, elapsed = future.result()
                        translated[lang] = out_path
                        google_request_count_total += int(meta.get('google_request_count', 0) or 0)
                        words = meta.get('word_count_target', '?')
                        google_requests = int(meta.get('google_request_count', 0) or 0)
                        print(f"  ✓ {lang}: {words} words ({elapsed:.1f}s, google_requests={google_requests})")
                    except Exception as e:
                        print(f"  ✗ {lang}: {e}")
        except BaseException:
            executor.shutdown(wait=False, cancel_futures=True)
            raise

    result['translated_langs'] = list(translated.keys())
    result['translation_failed_langs'] = [
        lang for lang in target_langs if lang not in translated
    ]
    result['google_request_count_total'] = google_request_count_total
    print(f"  ✓ 번역 Google 요청 합계: {google_request_count_total}")

    # 3. PDF generation
    print(f"[3/6] PDF 생성...")
    try:
        generate_pdf = _load_pdf_generator(report_type)
    except (ImportError, AttributeError) as e:
        print(f"  [WARN] {report_type} PDF generator not found, using econ fallback: {e}")
        from gen_pdf_econ import generate_pdf_econ as generate_pdf

    pdf_paths = {}
    for lang, lang_md_path in translated.items():
        pdf_path = os.path.join(OUTPUT_DIR, f'{slug}_{report_type}_v{version}_{lang}.pdf')
        meta = {
            'project_slug': slug,
            'project_name': file_info.get('project_name', slug),
            'token_symbol': file_info.get('symbol', slug.upper()),
            'slug': slug, 'version': version, 'lang': lang,
        }
        if report_type == 'for':
            meta['risk_level'] = file_info.get('risk_level', 'warning')
            meta['trigger_reason'] = file_info.get('trigger_reason', 'Market Analysis Alert')
        try:
            generate_pdf(lang_md_path, meta, lang=lang, output_path=pdf_path)
            pdf_paths[lang] = pdf_path
            print(f"  ✓ {lang}: {pdf_path}")
        except Exception as e:
            print(f"  ✗ {lang}: {e}")

    result['pdf_count'] = len(pdf_paths)

    # 4. QA verification
    print(f"[4/6] QA 검증...")
    qa_pass = {}
    qa_strict = _is_qa_strict_enabled()

    for lang, pdf_path in pdf_paths.items():
        try:
            meta = {'project_slug': slug, 'slug': slug, 'version': version, 'lang': lang}
            qa = verify_pdf(pdf_path, lang=lang, report_type=report_type, metadata=meta)
            fails = [c for c in qa.checks if c.severity == QASeverity.FAIL]
            warns = [c for c in qa.checks if c.severity == QASeverity.WARN]

            if fails:
                print(f"  ❌ {lang}: QA FAIL — {'; '.join(f'{c.name}({c.detail})' for c in fails[:4])}")
                if qa_strict:
                    raise TerminalContentError(
                        f"QA FAIL blocked upload: {lang} — {'; '.join(c.name for c in fails)}")
                else:
                    print(f"  ⚠ {lang}: QA FAIL but QA_STRICT=0, skipping upload")
                    continue

            if warns:
                print(f"  ⚠ {lang}: QA WARN — {'; '.join(c.name for c in warns[:4])}")

            qa_pass[lang] = pdf_path
            print(f"  ✓ {lang}: {qa.page_count} pages (QA: {qa.severity.value})")
        except TerminalContentError:
            raise
        except Exception as e:
            print(f"  ✗ {lang} QA error: {e}")
            if qa_strict:
                raise
            print(f"  ⚠ {lang}: QA crashed but QA_STRICT=0, skipping upload")

    result['qa_pass_count'] = len(qa_pass)
    result['qa_pass_langs'] = list(qa_pass.keys())

    required_publish_langs = _required_publish_languages()
    missing_publish_langs = [
        lang for lang in required_publish_langs if lang not in qa_pass
    ]
    result['required_publish_langs'] = required_publish_langs
    result['missing_publish_langs'] = missing_publish_langs
    if missing_publish_langs:
        result['status'] = RETRIABLE_PROCESSING_STATUS
        result['uploaded_count'] = 0
        result['error'] = (
            "Publish blocked: incomplete language set after translation/QA. "
            f"missing={','.join(missing_publish_langs)}"
        )[:200]
        print(
            "  ⚠ 게시 보류: 필수 언어 집합 미충족 "
            f"(required={', '.join(required_publish_langs)}; "
            f"missing={', '.join(missing_publish_langs)})"
        )
        return result

    # 4.5 Card metadata (all types)
    print(f"[4.5/6] 카드 메타데이터 생성...")
    card_result = None
    try:
        generate_card = _load_card_generator(report_type)
        if generate_card:
            trigger_info = {}
            if cfg['has_trigger_data']:
                trigger_info = _resolve_trigger_data(slug, file_info)

            en_md = translated.get('en')
            card_result = generate_card(
                ko_md_path=md_path,
                en_md_path=en_md,
                trigger_data=trigger_info,
                project_name=file_info.get('project_name', slug),
                symbol=file_info.get('symbol', slug.upper()),
                slug=slug,
                output_dir=OUTPUT_DIR,
            )
            result['card_data'] = card_result.get('card_data')
            card_data = card_result['card_data']
            key_field = (
                f"risk_score={card_data.get('risk_score')}"
                if 'risk_score' in card_data else
                f"rating={card_data.get('rating')}"
                if 'rating' in card_data else
                f"maturity_score={card_data.get('maturity_score')}"
                if 'maturity_score' in card_data else
                'no primary card metric'
            )
            print(f"  ✓ Card metadata generated ({key_field})")
    except Exception as e:
        print(f"  ⚠ Card generation failed (non-blocking): {e}")

    # 5. GDrive upload
    print(f"[5/6] GDrive 업로드...")
    gd = GDriveStorage()
    gdrive_urls = {}
    folder_id = gd.ensure_folder_path(slug, report_type)
    for lang, pdf_path in qa_pass.items():
        try:
            f = gd.upload_file(pdf_path, folder_id=folder_id)
            file_id = (f or {}).get('id')
            if not file_id:
                print(f"  ✗ {lang}: upload returned no file ID")
                continue
            url = (f or {}).get('webViewLink') or \
                f'https://drive.google.com/file/d/{file_id}/view'
            gdrive_urls[lang] = url
            print(f"  ✓ {lang}: {url[:60]}...")
        except Exception as e:
            print(f"  ✗ {lang}: {e}")

    result['uploaded_count'] = len(gdrive_urls)

    # 6. Supabase publish
    print(f"[6/6] Supabase 게시...")
    try:
        card_db = None
        if card_result:
            cd = card_result['card_data']
            sbl = cd.get('summary_by_lang', {})
            card_db = {
                'card_keywords': cd.get('keywords'),
                'card_summary_en': sbl.get('en') or cd.get('summary_en'),
                'card_summary_ko': sbl.get('ko') or cd.get('summary_ko'),
                'card_summary_fr': sbl.get('fr'),
                'card_summary_es': sbl.get('es'),
                'card_summary_de': sbl.get('de'),
                'card_summary_ja': sbl.get('ja'),
                'card_summary_zh': sbl.get('zh'),
                'card_data': cd,
                'card_qa_status': 'pending',
            }
            if 'risk_score' in cd:
                card_db['card_risk_score'] = cd.get('risk_score')

            if report_type == 'for':
                try:
                    from gen_report_title import generate_titles
                    titles = generate_titles(
                        card_data=cd,
                        project_name=file_info.get('project_name', slug),
                        symbol=file_info.get('symbol', slug.upper()),
                        summary_en=cd.get('summary_en'),
                        summary_ko=cd.get('summary_ko'),
                    )
                    card_db['title_en'] = titles['title_en']
                    card_db['title_ko'] = titles['title_ko']
                    print(f"  ✓ Title: {titles['title_en']}")
                except Exception as e:
                    print(f"  ⚠ Title generation failed: {e}")

        _publish_supabase(slug, report_type, version, gdrive_urls, card_db=card_db,
                          db_report_type=cfg['db_report_type'])
        result['status'] = 'published'
        print(f"  ✓ published")
    except Exception as e:
        result['status'] = 'upload_done_db_error'
        result['error'] = str(e)[:200]
        print(f"  ✗ Supabase: {e}")

    return result


def _resolve_trigger_data(slug: str, file_info: dict) -> dict:
    """Resolve forensic trigger data for FOR reports."""
    trigger_info = file_info.get('trigger_data', {})
    if trigger_info:
        return trigger_info
    try:
        _sb = _get_supabase_client()
        if not _sb:
            return {}
        _symbol = file_info.get('symbol', slug.split('-')[0]).upper()
        _pid, _cslug, _, _ = _resolve_project_slug(_sb, slug)

        if _pid:
            _cs = _sb.table('project_reports').select('trigger_data') \
                .eq('project_id', _pid).eq('report_type', 'forensic') \
                .eq('status', 'coming_soon').limit(1).execute()
            if _cs.data and _cs.data[0].get('trigger_data'):
                td = _cs.data[0]['trigger_data']
                if isinstance(td, str):
                    td = json.loads(td)
                return td

        for _q_field, _q_val in [('slug', slug), ('symbol', _symbol)]:
            _ft = _sb.table('forensic_triggers').select('*') \
                .eq(_q_field, _q_val).order('created_at', desc=True).limit(1).execute()
            if _ft.data:
                return _ft.data[0]

        if _pid:
            _ft = _sb.table('forensic_triggers').select('*') \
                .eq('project_id', _pid).order('created_at', desc=True).limit(1).execute()
            if _ft.data:
                return _ft.data[0]
    except Exception as e:
        print(f"  ⚠ trigger_data lookup failed: {e}")
    return {}


def _get_master_report_language(gdrive_urls: dict) -> str:
    if 'ko' in gdrive_urls:
        return 'ko'
    if 'en' in gdrive_urls:
        return 'en'
    return sorted(gdrive_urls.keys())[0]


def _select_existing_project_reports(sb, project_id: str, db_report_type: str, version: int):
    try:
        result = sb.table('project_reports').select('id, status, language, published_at') \
            .eq('project_id', project_id) \
            .eq('report_type', db_report_type) \
            .eq('version', version) \
            .execute()
        return result.data or [], True
    except Exception as exc:
        if 'language' not in str(exc).lower():
            raise

    fallback = sb.table('project_reports').select('id, status, published_at') \
        .eq('project_id', project_id) \
        .eq('report_type', db_report_type) \
        .eq('version', version) \
        .execute()
    return fallback.data or [], False


def _mark_forensic_triggers_published(sb, project_id: str, report_ids: list[str] | None = None):
    active_statuses = ['detected', 'notified', 'draft_pending', 'processing']

    for report_id in report_ids or []:
        sb.table('forensic_triggers').update({'status': 'published'}) \
            .eq('report_id', report_id) \
            .in_('status', active_statuses) \
            .execute()

    sb.table('forensic_triggers').update({'status': 'published'}) \
        .eq('project_id', project_id) \
        .in_('status', active_statuses) \
        .execute()


def _publish_supabase(slug, report_type, version, gdrive_urls, card_db=None, db_report_type=None):
    """Publish report rows to Supabase, preserving the legacy FOR contract."""
    sb = _get_supabase_client()
    if not sb:
        raise RuntimeError("Supabase client unavailable")

    db_rtype = db_report_type or INGEST_CONFIG.get(report_type, {}).get('db_report_type', report_type)

    _pid, _cslug, _, _ = _resolve_project_slug(sb, slug)
    if not _pid:
        raise RuntimeError(f"Project not found: {slug}")

    translation_status = {lang: 'published' for lang in gdrive_urls}
    now = datetime.now(timezone.utc).isoformat()
    master_lang = _get_master_report_language(gdrive_urls)
    existing_rows, has_language_column = _select_existing_project_reports(
        sb,
        _pid,
        db_rtype,
        version,
    )

    if not has_language_column:
        row = {
            'project_id': _pid,
            'report_type': db_rtype,
            'version': version,
            'status': 'published',
            'published_at': now,
            'gdrive_urls_by_lang': gdrive_urls,
            'translation_status': translation_status,
        }
        if gdrive_urls:
            row['gdrive_url'] = gdrive_urls.get('ko') or gdrive_urls.get('en') or next(iter(gdrive_urls.values()))
        if card_db:
            row.update(card_db)

        if existing_rows:
            report_id = existing_rows[0]['id']
            if existing_rows[0].get('status') == 'published':
                row.pop('published_at', None)
            sb.table('project_reports').update(row).eq('id', report_id).execute()
            if db_rtype == 'forensic':
                _mark_forensic_triggers_published(sb, _pid, report_ids=[report_id])
        else:
            sb.table('project_reports').insert(row).execute()
            if db_rtype == 'forensic':
                _mark_forensic_triggers_published(sb, _pid)
    else:
        existing_by_language = {
            row.get('language'): row for row in existing_rows if row.get('language')
        }
        published_ids = []

        for language, language_url in gdrive_urls.items():
            row = {
                'project_id': _pid,
                'report_type': db_rtype,
                'version': version,
                'language': language,
                'status': 'published',
                'published_at': now,
                'gdrive_urls_by_lang': gdrive_urls,
                'translation_status': translation_status,
                'gdrive_url': language_url,
                'file_url': language_url,
            }
            if language == master_lang and len(gdrive_urls) > 1:
                free_url = gdrive_urls.get('en') or gdrive_urls.get('ko')
                if free_url:
                    row['gdrive_url_free'] = free_url
            if card_db:
                row.update(card_db)

            existing_report = existing_by_language.get(language)
            if existing_report:
                if existing_report.get('status') == 'published':
                    row.pop('published_at', None)
                sb.table('project_reports').update(row).eq('id', existing_report['id']).execute()
                published_ids.append(existing_report['id'])
                continue

            upsert_result = sb.table('project_reports').upsert(
                row, on_conflict='project_id,report_type,version,language'
            ).execute()
            if upsert_result.data:
                published_ids.extend(
                    report_row['id'] for report_row in upsert_result.data if report_row.get('id')
                )

        if db_rtype == 'forensic' and (published_ids or existing_by_language.get(master_lang)):
            _mark_forensic_triggers_published(sb, _pid, report_ids=published_ids)

    # Update tracked_projects timestamp
    ts_field = {
        'econ': 'last_econ_report_at',
        'maturity': 'last_maturity_report_at',
        'forensic': 'last_forensic_report_at',
    }.get(db_rtype)
    if ts_field:
        tracked_project_slug = _cslug or slug
        sb.table('tracked_projects').update(
            {ts_field: datetime.now(timezone.utc).isoformat()}
        ).eq('slug', tracked_project_slug).execute()


def _terminal_failure_result(file_info: dict, error: Exception) -> dict:
    return {
        'slug': file_info['slug'],
        'file_id': file_info['file_id'],
        'status': TERMINAL_CONTENT_STATUS,
        'error': str(error)[:200],
    }


def _retriable_failure_result(file_info: dict, error: Exception) -> dict:
    return {
        'slug': file_info['slug'],
        'file_id': file_info['file_id'],
        'status': RETRIABLE_PROCESSING_STATUS,
        'error': str(error)[:200],
    }


def _update_run_state(ps, run_id, result):
    status = result.get('status', 'processing_error')
    error = result.get('error')
    if ps and run_id:
        try:
            ps.update_status(run_id, status, error=error)
        except Exception as exc:
            print(f"  [WARN] pipeline_runs update failed: {exc}")


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main():
    _register_signal_handlers()
    parser = argparse.ArgumentParser(description='Unified Report Ingest Pipeline (BCE-732)')
    parser.add_argument('--type', required=True, choices=['econ', 'mat', 'for'],
                        help='Report type')
    parser.add_argument('--dry-run', action='store_true', help='Download only')
    parser.add_argument('--slug', type=str, help='Process specific slug only')
    parser.add_argument('--force', action='store_true', help='Force re-process')
    args = parser.parse_args()

    report_type = args.type
    cfg = INGEST_CONFIG[report_type]

    print(f"\n{'='*60}")
    print(f"{report_type.upper()} Report Pipeline — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    ps = None
    try:
        ps = PipelineState(report_type)
        print("  [STATE] Supabase pipeline_runs 사용")
    except Exception as exc:
        print(f"  [STATE] Supabase 불가: {exc}")

    print(f"[SCAN] GDrive drafts/{cfg['gdrive_folder']}/ 스캔 중...")
    new_files = scan_drafts(report_type, filter_slug=args.slug, force=args.force, pipeline_state=ps)

    if not new_files:
        print("  새로운 .md 파일 없음")
        return 0

    print(f"  {len(new_files)}개 새 파일 발견:")
    for f in new_files:
        print(f"    • {f['name']} ({f['slug']}) — {f['size']:,} bytes")

    results = []
    for f in new_files:
        retry_count = f.get('_retry_count', 0)
        run_id = None
        if ps:
            try:
                run = ps.start_run(
                    f['slug'],
                    source_file_id=f['file_id'],
                    source_filename=f['name'],
                    retry_count=retry_count,
                )
                run_id = run['id']
            except Exception as exc:
                print(f"  [WARN] pipeline_runs insert failed: {exc}")

        try:
            result = process_report(report_type, f, dry_run=args.dry_run)
        except TerminalContentError as e:
            result = _terminal_failure_result(f, e)
            print(f"  [TERMINAL] {f['name']} — {e}")
        except ProcessingInterruptedError as e:
            result = _retriable_failure_result(f, e)
            print(f"  [INTERRUPTED] {f['name']} — {e}")
            _update_run_state(ps, run_id, result)
            results.append(result)
            break
        except Exception as e:
            result = _retriable_failure_result(f, e)
            print(f"  [ERROR] {f['name']} — {e}")

        _update_run_state(ps, run_id, result)
        results.append(result)

    published = sum(1 for r in results if r['status'] == 'published')
    terminal_failures = sum(1 for r in results if r['status'] == TERMINAL_CONTENT_STATUS)
    retriable_failures = sum(1 for r in results if r['status'] == RETRIABLE_PROCESSING_STATUS)
    print(f"\n{'='*60}")
    print(f"DONE: {published}/{len(results)} published")
    if terminal_failures or retriable_failures:
        print(f"FAILED: terminal={terminal_failures}, retriable={retriable_failures}")
    print(f"{'='*60}")

    summary_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    os.makedirs(summary_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    summary_path = os.path.join(summary_dir, f'ingest_{report_type}_{ts}.json')
    with open(summary_path, 'w') as fp:
        json.dump({'report_type': report_type, 'results': results,
                   'timestamp': datetime.now(timezone.utc).isoformat()},
                  fp, ensure_ascii=False, indent=2)
    print(f"요약: {summary_path}")
    return 1 if terminal_failures or retriable_failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
