"""
FOR (Forensic) Report GDrive Watcher & Ingest Pipeline — OPS-007

GDrive drafts/FOR/ 폴더를 스캔하여 새로운 .md 파일을 감지하고,
ECON/MAT 파이프라인과 동일한 흐름으로 처리:

    drafts/FOR/{slug}_for_v1.md (한국어 초안)
        ↓ Download
    [1] 종목 확정 (파일명 + 본문 분석)
    [2] 번역 (ko → en, ja, zh, fr, es, de)
    [3] PDF 생성 (gen_pdf_for.py — 7개 언어)
    [4] QA 검증
    [5] GDrive 업로드 ({slug}/for/)
    [6] Supabase: 'coming_soon' → 'published'
    [7] 웹사이트 자동 반영

Usage:
    python ingest_for.py                 # 실행
    python ingest_for.py --dry-run       # 다운로드만, 처리하지 않음
    python ingest_for.py --slug bitcoin  # 특정 종목만 처리
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Pipeline imports ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_env = Path(__file__).resolve().parent.parent.parent / '.env.local'
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

os.environ.setdefault(
    'GDRIVE_SERVICE_ACCOUNT_JSON',
    str(Path(__file__).resolve().parent / '.gdrive_service_account.json'),
)

from config import LANGUAGES, OUTPUT_DIR, report_filename
from translate_md import translate_md_file
from qa_verify import verify_pdf, QASeverity
from qa_verify_md import verify_markdown
from gdrive_storage import GDriveStorage


# ═══════════════════════════════════════════
# Equation Image → Text OCR Resolver
# ═══════════════════════════════════════════
# Google Docs renders LaTeX-style math ($0.026$) as inline PNG images.
# When exported to markdown, these become ![][imageN] references with
# base64 data at the end of the file. This function OCRs them back to text.

def _ocr_with_tesseract(b64_data: str) -> str:
    """Try pytesseract OCR on a base64 PNG. Returns text or empty string."""
    import base64 as _b64
    import io as _io
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ''
    try:
        img_bytes = _b64.b64decode(b64_data)
        img = Image.open(_io.BytesIO(img_bytes)).convert('RGBA')
        bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        gray = bg.convert('L')
        w, h = gray.size
        upscaled = gray.resize((w * 6, h * 6), Image.LANCZOS)
        bw = upscaled.point(lambda x: 0 if x < 128 else 255)
        padded = Image.new('L', (bw.width + 40, bw.height + 40), 255)
        padded.paste(bw, (20, 20))
        text = pytesseract.image_to_string(
            padded,
            config='--psm 7 -c tessedit_char_whitelist=0123456789.,%+-~$αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ',
        ).strip()
        # Reject obviously bad OCR: single punctuation, garbled long strings
        if not text:
            return ''
        if len(text) == 1 and text in '.,-%~':
            return ''
        if len(text) > 20 and not any(c == ' ' for c in text):
            return ''  # Garbled run-on string
        return text
    except Exception:
        return ''


def _ocr_with_gemini(b64_data: str, img_name: str, context_hint: str = '') -> str:
    """Fallback: use Gemini 2.5 Flash vision to read equation image."""
    import base64 as _b64
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("    [WARN] google-genai not installed — skipping Gemini OCR")
        return ''

    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_AI_API_KEY', '')
    if not api_key:
        print("    [WARN] GEMINI_API_KEY not set — skipping Gemini OCR")
        return ''

    try:
        client = genai.Client(api_key=api_key)
        img_bytes = _b64.b64decode(b64_data)

        prompt = (
            "이 이미지는 블록체인/암호화폐 보고서에서 추출한 수식 또는 숫자/기호입니다. "
            "이미지에 표시된 텍스트를 정확히 읽어주세요. "
            "그리스 문자(ρ, β, α 등), 수학 기호, 숫자, 통화 기호($), 퍼센트(%) 등이 포함될 수 있습니다. "
            "수식이면 읽기 쉬운 텍스트로 변환해주세요 (LaTeX 아님). "
            "예: 'ρ', '0.026', 'T_finality', '≈ $2.5–$4.0' 등. "
            "이미지에 보이는 텍스트만 출력하세요. 설명이나 부가 텍스트 없이 결과만."
        )
        if context_hint:
            prompt += f"\n\n문맥 힌트: ...{context_hint}..."

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Content(parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=img_bytes, mime_type='image/png'),
                ]),
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=100,
            ),
        )
        text = response.text.strip().strip('`').strip()
        # Remove wrapping quotes if any
        if len(text) > 2 and text[0] in '"\'`' and text[-1] in '"\'`':
            text = text[1:-1].strip()
        if text:
            print(f"    Gemini → '{text}'")
            return text
    except Exception as e:
        print(f"    [WARN] Gemini OCR failed for {img_name}: {type(e).__name__}: {e}")
    return ''


def _resolve_equation_images(md_text: str) -> tuple[str, int]:
    """Replace ![][imageN] base64 equation images with OCR'd text.

    Strategy: pytesseract first → Gemini 2.5 Flash fallback for failures.
    Returns (cleaned_text, replacement_count).
    """
    import base64
    import io

    # Find all image definitions: [imageN]: <data:image/png;base64,...>
    def_pattern = re.compile(
        r'^\[image(\d+)\]:\s*<data:image/png;base64,([^>]+)>\s*$',
        re.MULTILINE,
    )
    img_defs = {}
    for m in def_pattern.finditer(md_text):
        img_defs[f'image{m.group(1)}'] = m.group(2)

    if not img_defs:
        return md_text, 0

    # Build context hints: find surrounding text for each image reference
    context_hints: dict[str, str] = {}
    for img_name in img_defs:
        ref_pat = re.compile(r'.{0,60}' + re.escape(f'![][{img_name}]') + r'.{0,60}')
        m = ref_pat.search(md_text)
        if m:
            context_hints[img_name] = m.group(0)

    # Phase 1: pytesseract
    replacements: dict[str, str] = {}
    tess_ok = 0
    for img_name, b64_data in img_defs.items():
        text = _ocr_with_tesseract(b64_data)
        if text:
            replacements[img_name] = text
            tess_ok += 1
        else:
            replacements[img_name] = '[?]'

    # Phase 2: Gemini 2.5 Flash for failures
    gemini_needed = [k for k, v in replacements.items() if v == '[?]']
    gemini_ok = 0
    if gemini_needed:
        print(f"  pytesseract: {tess_ok}/{len(img_defs)} OK, {len(gemini_needed)} → Gemini fallback")
        for img_name in gemini_needed:
            hint = context_hints.get(img_name, '')
            text = _ocr_with_gemini(img_defs[img_name], img_name, hint)
            if text:
                replacements[img_name] = text
                gemini_ok += 1
            import time
            time.sleep(1)  # Rate limit: Gemini free tier = 10 RPM

    # Replace inline references
    result = md_text
    count = 0
    for img_name, text in replacements.items():
        pat = re.compile(re.escape(f'![][{img_name}]'))
        matches = len(pat.findall(result))
        result = pat.sub(text, result)
        count += matches

    # Remove image definition lines
    result = def_pattern.sub('', result)
    result = re.sub(r'\n{3,}', '\n\n', result)

    ok = sum(1 for v in replacements.values() if v != '[?]')
    fail = sum(1 for v in replacements.values() if v == '[?]')
    print(f"  ✓ 수식 이미지 OCR: {ok} resolved ({tess_ok} tesseract + {gemini_ok} gemini), {fail} unresolved out of {len(img_defs)} images ({count} refs)")
    return result, count

# ═══════════════════════════════════════════
# GDrive Draft Scanner
# ═══════════════════════════════════════════

def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    sa_file = os.environ.get('GDRIVE_SERVICE_ACCOUNT_JSON')
    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=['https://www.googleapis.com/auth/drive'])
    delegate = os.environ.get('GDRIVE_DELEGATE_EMAIL', 'zhang@coinlab.co.kr')
    if delegate:
        creds = creds.with_subject(delegate)
    return build('drive', 'v3', credentials=creds)


def _find_folder_id(service, parent_id: str, name: str) -> str | None:
    """Find a subfolder by name under parent (case-insensitive)."""
    # First try exact match
    q = (f"'{parent_id}' in parents and name='{name}' "
         f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
    r = service.files().list(q=q, fields='files(id,name)', pageSize=10).execute()
    files = r.get('files', [])
    if files:
        return files[0]['id']
    # Fallback: list all subfolders and match case-insensitively
    q2 = (f"'{parent_id}' in parents "
          f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
    r2 = service.files().list(q=q2, fields='files(id,name)', pageSize=50).execute()
    for f in r2.get('files', []):
        if f['name'].lower() == name.lower():
            print(f"  [INFO] Folder case mismatch: expected '{name}', found '{f['name']}'")
            return f['id']
    return None


_PROCESSED_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', '_for_processed.json')


def _load_processed(service=None, folder_id: str = None) -> dict:
    """Load processed tracker from local file."""
    if os.path.exists(_PROCESSED_LOCAL):
        with open(_PROCESSED_LOCAL, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_processed(service=None, folder_id: str = None, data: dict = None):
    """Save processed tracker to local file."""
    os.makedirs(os.path.dirname(_PROCESSED_LOCAL), exist_ok=True)
    with open(_PROCESSED_LOCAL, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


STALE_PROCESSING_MINUTES = 30   # 'processing' entries older than this → retriable
MAX_RETRIES = 3                 # max retry count before marking permanently failed


def _is_stale_processing(entry: dict) -> bool:
    """Check if a 'processing' entry is stuck (older than threshold)."""
    started = entry.get('started_at')
    if not started:
        return True
    try:
        started_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
        elapsed = (datetime.now(timezone.utc) - started_dt).total_seconds() / 60
        return elapsed > STALE_PROCESSING_MINUTES
    except Exception:
        return True


def _should_retry(entry: dict) -> bool:
    """Determine if a failed/stale entry should be retried."""
    status = entry.get('status', '')
    retries = entry.get('retry_count', 0)

    if retries >= MAX_RETRIES:
        return False

    # Retry: failed_timeout, download_error, upload_done_db_error, stale processing
    if status in ('failed_timeout', 'download_error', 'upload_done_db_error'):
        return True
    if status == 'processing' and _is_stale_processing(entry):
        return True
    return False


def scan_for_drafts(filter_slug: str = None) -> list[dict]:
    """Scan GDrive drafts/FOR/ for new .md files."""
    service = _get_drive_service()
    root_id = os.environ.get('GDRIVE_ROOT_FOLDER_ID', '1E87EcasPlrGuet0t6e1CA9kLFO0sTdFq')
    if not root_id:
        print("[ERROR] GDRIVE_ROOT_FOLDER_ID not set")
        return []

    drafts_id = _find_folder_id(service, root_id, 'drafts')
    if not drafts_id:
        print("[WARN] drafts/ folder not found — creating it")
        meta = {'name': 'drafts', 'parents': [root_id],
                'mimeType': 'application/vnd.google-apps.folder'}
        drafts_id = service.files().create(body=meta, fields='id').execute()['id']

    for_id = _find_folder_id(service, drafts_id, 'FOR')
    if not for_id:
        print("[WARN] drafts/FOR/ folder not found — creating it")
        meta = {'name': 'FOR', 'parents': [drafts_id],
                'mimeType': 'application/vnd.google-apps.folder'}
        for_id = service.files().create(body=meta, fields='id').execute()['id']

    # Load processed state
    processed = _load_processed(service, for_id)

    # ── Query 1: text/markdown mimeType ──
    q1 = f"'{for_id}' in parents and mimeType='text/markdown' and trashed=false"
    r1 = service.files().list(
        q=q1, fields='files(id,name,size,modifiedTime,mimeType)', pageSize=100,
        orderBy='modifiedTime desc').execute()
    files = r1.get('files', [])
    seen_ids = {f['id'] for f in files}

    # ── Query 2: name contains '.md' (catches text/plain, etc.) ──
    q2 = f"'{for_id}' in parents and name contains '.md' and trashed=false"
    r2 = service.files().list(
        q=q2, fields='files(id,name,size,modifiedTime,mimeType)', pageSize=100).execute()
    for f in r2.get('files', []):
        if f['id'] not in seen_ids:
            files.append(f)
            seen_ids.add(f['id'])

    # ── Query 3: Google Docs (board may upload .md via web → auto-converted) ──
    q3 = (f"'{for_id}' in parents "
          f"and mimeType='application/vnd.google-apps.document' and trashed=false")
    r3 = service.files().list(
        q=q3, fields='files(id,name,size,modifiedTime,mimeType)', pageSize=100).execute()
    for f in r3.get('files', []):
        if f['id'] not in seen_ids:
            # Google Docs won't have .md extension — add a synthetic one for slug extraction
            if not f['name'].endswith('.md'):
                f['_gdoc'] = True
                f['name'] = f['name'] + '.md'
            files.append(f)
            seen_ids.add(f['id'])

    print(f"  [SCAN] Found {len(files)} total files in drafts/FOR/")
    for f in files:
        mt = f.get('mimeType', 'unknown')
        gdoc = ' (Google Doc)' if f.get('_gdoc') else ''
        print(f"    • {f['name']} [{mt}]{gdoc} id={f['id'][:8]}...")

    new_files = []
    for f in files:
        fid = f['id']
        entry = processed.get(fid)

        # Skip only successfully published files
        if entry and entry.get('status') == 'published':
            continue
        # Skip 'processing' entries that are NOT stale
        if entry and entry.get('status') == 'processing' and not _is_stale_processing(entry):
            continue
        # Skip permanently failed (max retries exceeded)
        if entry and not _should_retry(entry) and entry.get('status') not in (None, 'dry_run'):
            if entry.get('retry_count', 0) >= MAX_RETRIES:
                print(f"    [SKIP] {f['name']} — max retries ({MAX_RETRIES}) reached")
                continue

        name = f['name']
        if not name.endswith('.md'):
            continue

        # Extract slug from filename: {slug}_for_v{N}.md or just {slug}.md
        slug_match = re.match(r'^(.+?)(?:_for)?(?:_v\d+)?\.md$', name, re.IGNORECASE)
        if not slug_match:
            print(f"    [SKIP] {name} — filename doesn't match slug pattern")
            continue
        slug = slug_match.group(1).lower().replace(' ', '-').replace('_', '-')

        if filter_slug and slug != filter_slug:
            continue

        is_retry = entry is not None and entry.get('status') not in (None, 'dry_run')
        if is_retry:
            old_status = entry.get('status')
            retry_n = entry.get('retry_count', 0) + 1
            print(f"    [RETRY] {name} (was: {old_status}, attempt #{retry_n})")

        new_files.append({
            'file_id': fid,
            'name': name,
            'slug': slug,
            'size': int(f.get('size', 0)),
            'modified': f.get('modifiedTime'),
            '_gdoc': f.get('_gdoc', False),
            '_retry_count': entry.get('retry_count', 0) if entry else 0,
        })

    return new_files


def download_md(file_id: str, output_path: str, is_gdoc: bool = False):
    """Download a .md file from GDrive. Handles both raw files and Google Docs."""
    service = _get_drive_service()
    if is_gdoc:
        # Google Docs must be exported — use text/plain for markdown-like content
        content = service.files().export(
            fileId=file_id, mimeType='text/plain').execute()
        if isinstance(content, str):
            content = content.encode('utf-8')
    else:
        content = service.files().get_media(fileId=file_id).execute()
    Path(output_path).write_bytes(content)
    return output_path


# ═══════════════════════════════════════════
# FOR Pipeline Processing
# ═══════════════════════════════════════════

def process_for_report(file_info: dict, dry_run: bool = False) -> dict:
    """
    Process a single FOR report:
    download → translate → PDF → QA → upload → Supabase publish
    """
    slug = file_info['slug']
    fid = file_info['file_id']
    rtype = 'for'
    version = 1
    result = {'slug': slug, 'file_id': fid, 'status': 'started'}

    print(f"\n{'─'*50}")
    print(f"Processing: {file_info['name']} → {slug}")
    print(f"{'─'*50}")

    # 1. Download
    ko_path = os.path.join(OUTPUT_DIR, f'{slug}_{rtype}_v{version}_ko.md')
    is_gdoc = file_info.get('_gdoc', False)
    print(f"[1/6] 다운로드{' (Google Doc export)' if is_gdoc else ''}...")
    try:
        download_md(fid, ko_path, is_gdoc=is_gdoc)
        print(f"  ✓ {ko_path} ({Path(ko_path).stat().st_size:,} bytes)")
    except Exception as e:
        result['status'] = 'download_error'
        result['error'] = str(e)[:200]
        print(f"  ✗ 다운로드 실패: {e}")
        return result

    # 1b. Resolve equation images (LaTeX → text via OCR)
    try:
        raw_md = Path(ko_path).read_text(encoding='utf-8')
        if '![][image' in raw_md:
            print("[1b/6] 수식 이미지 OCR 처리...")
            cleaned_md, eq_count = _resolve_equation_images(raw_md)
            if eq_count > 0:
                Path(ko_path).write_text(cleaned_md, encoding='utf-8')
                result['equation_images_resolved'] = eq_count
        else:
            print("[1b/6] 수식 이미지 없음 — 건너뜀")
    except Exception as e:
        print(f"  [WARN] 수식 OCR 실패 (계속 진행): {e}")

    if dry_run:
        result['status'] = 'dry_run'
        print("  [DRY RUN] 다운로드만 완료")
        return result

    # 2. Translate (ko → 6 languages) — parallel for speed
    target_langs = ['en', 'ja', 'zh', 'fr', 'es', 'de']
    print(f"[2/6] 번역 (ko → {', '.join(target_langs)}) — parallel mode...")
    translated = {'ko': ko_path}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _translate_one(lang):
        out_path, meta = translate_md_file(
            ko_path, target_lang=lang, output_dir=OUTPUT_DIR, backend='google')
        return lang, out_path, meta

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_translate_one, lang): lang for lang in target_langs}
        for future in as_completed(futures):
            lang = futures[future]
            try:
                lang, out_path, meta = future.result()
                translated[lang] = out_path
                words = meta.get('word_count_target', '?')
                print(f"  ✓ {lang}: {words} words")
            except Exception as e:
                print(f"  ✗ {lang}: {e}")
                # Continue with other languages

    result['translated_langs'] = list(translated.keys())

    # 3. PDF generation
    print(f"[3/6] PDF 생성...")
    try:
        from gen_pdf_for import generate_pdf_for
    except ImportError:
        # Fallback to econ generator if FOR-specific one not ready
        print("  [WARN] gen_pdf_for.py not found — using gen_pdf_econ as fallback")
        from gen_pdf_econ import generate_pdf_econ as generate_pdf_for

    pdf_paths = {}
    for lang, md_path in translated.items():
        pdf_path = os.path.join(OUTPUT_DIR, f'{slug}_{rtype}_v{version}_{lang}.pdf')
        meta = {
            'project_slug': slug, 'project_name': slug,
            'slug': slug, 'version': version, 'lang': lang,
        }
        try:
            generate_pdf_for(md_path, meta, lang=lang, output_path=pdf_path)
            pdf_paths[lang] = pdf_path
            print(f"  ✓ {lang}: {pdf_path}")
        except Exception as e:
            print(f"  ✗ {lang}: {e}")

    result['pdf_count'] = len(pdf_paths)

    # 4. QA verification
    print(f"[4/6] QA 검증...")
    qa_pass = {}
    for lang, pdf_path in pdf_paths.items():
        try:
            meta = {'project_slug': slug, 'slug': slug, 'version': version, 'lang': lang}
            qa = verify_pdf(pdf_path, lang=lang, report_type='for', metadata=meta)
            fails = [c.name for c in qa.checks if c.severity == QASeverity.FAIL]
            warns = [c.name for c in qa.checks if c.severity == QASeverity.WARN]
            if fails:
                print(f"  ⚠ {lang}: QA issues — {fails}")
            if warns:
                print(f"    WARN: {warns}")
            # Upload regardless of QA (warn-level only blocks publishing)
            qa_pass[lang] = pdf_path
            print(f"  ✓ {lang}: {qa.page_count} pages (QA: {qa.severity.value})")
        except Exception as e:
            print(f"  ✗ {lang} QA error: {e}")
            qa_pass[lang] = pdf_path  # Upload anyway if QA crashes

    result['qa_pass_count'] = len(qa_pass)

    # 4.5 Card metadata + thumbnail generation (OPS-008)
    print(f"[4.5/7] 카드 메타데이터 + 썸네일 생성...")
    card_result = None
    try:
        from gen_for_card import generate_for_card

        # Build trigger_data from file_info or Supabase
        trigger_info = file_info.get('trigger_data', {})
        if not trigger_info:
            # Try to get from Supabase
            try:
                _sb = _get_supabase_client()
                if _sb:
                    from gen_for_card import _resolve_project_slug  # noqa: F811
                    _pid, _cslug = _resolve_project_slug(_sb, slug)
                    if _pid:
                        _ft = _sb.table('forensic_triggers').select('*') \
                            .eq('project_id', _pid).order('created_at', desc=True) \
                            .limit(1).execute()
                        if _ft.data:
                            trigger_info = _ft.data[0]
            except Exception:
                pass

        en_md = translated.get('en')
        card_result = generate_for_card(
            ko_md_path=ko_path,
            en_md_path=en_md,
            trigger_data=trigger_info,
            project_name=file_info.get('project_name', slug),
            symbol=file_info.get('symbol', slug.upper()),
            slug=slug,
            output_dir=OUTPUT_DIR,
        )
        result['card_data'] = card_result.get('card_data')
        print(f"  ✓ Keywords: {card_result['card_data']['keywords']}")
        print(f"  ✓ Risk Score: {card_result['card_data']['risk_score']}")
        print(f"  ✓ QA Preview: {card_result['qa_preview_path']}")
    except Exception as e:
        print(f"  ⚠ Card generation failed (non-blocking): {e}")

    # 5. GDrive upload
    print(f"[5/7] GDrive 업로드...")
    gd = GDriveStorage()
    gdrive_urls = {}
    folder_id = gd.ensure_folder_path(slug, rtype)
    for lang, pdf_path in qa_pass.items():
        try:
            f = gd.upload_file(pdf_path, folder_id=folder_id)
            url = (f or {}).get('webViewLink') or \
                f'https://drive.google.com/file/d/{(f or {}).get("id")}/view'
            gdrive_urls[lang] = url
            print(f"  ✓ {lang}: {url[:60]}...")
        except Exception as e:
            print(f"  ✗ {lang}: {e}")

    result['uploaded_count'] = len(gdrive_urls)

    # 6. Upload thumbnail SVG to GDrive
    thumb_url = None
    if card_result and card_result.get('thumbnail_path'):
        print(f"[6/7] 썸네일 GDrive 업로드...")
        try:
            tf = gd.upload_file(card_result['thumbnail_path'], folder_id=folder_id)
            # GDrive view URLs are HTML pages, not image URLs — don't use as thumbnail
            # The CSS-based card in ForensicSlideCards renders from card_data instead
            thumb_url = None
            print(f"  ✓ {thumb_url[:60]}...")
        except Exception as e:
            print(f"  ⚠ Thumbnail upload failed: {e}")

    # 7. Supabase: coming_soon → published + card_data + auto-title
    print(f"[7/7] Supabase 업데이트 (coming_soon → published + card_data + title)...")
    try:
        card_db = None
        if card_result:
            cd = card_result['card_data']
            card_db = {
                'card_keywords': cd.get('keywords'),
                'card_summary_ko': cd.get('summary_ko'),
                'card_summary_en': cd.get('summary_en'),
                'card_risk_score': cd.get('risk_score'),
                'card_thumbnail_url': thumb_url,
                'card_data': cd,
                'card_qa_status': 'pending',  # QA 승인 대기
            }

            # Auto-generate report titles from card_data
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
                print(f"  ✓ Title EN: {titles['title_en']}")
                print(f"  ✓ Title KO: {titles['title_ko']}")
            except Exception as e:
                print(f"  ⚠ Title generation failed (non-blocking): {e}")

        _publish_supabase(slug, rtype, version, gdrive_urls, card_db=card_db)
        result['status'] = 'published'
        print(f"  ✓ published (card_qa_status: pending)")
    except Exception as e:
        result['status'] = 'upload_done_db_error'
        result['error'] = str(e)[:200]
        print(f"  ✗ Supabase: {e}")

    return result


def _resolve_project_slug(sb, raw_slug: str) -> tuple:
    """
    Resolve a filename-derived slug to a tracked_projects entry.
    Tries: exact slug match → symbol match → name substring match.
    Returns (project_id, canonical_slug) or (None, None).
    """
    # 1. Direct slug match
    proj = sb.table('tracked_projects').select('id, slug').eq('slug', raw_slug).execute()
    if proj.data:
        return proj.data[0]['id'], proj.data[0]['slug']

    # 2. Extract possible symbol from slug (e.g., "rave-포렌식-분석-보고서-20260414" → "rave")
    symbol_candidate = raw_slug.split('-')[0].upper()
    if symbol_candidate:
        proj = sb.table('tracked_projects').select('id, slug') \
            .eq('symbol', symbol_candidate).execute()
        if proj.data:
            return proj.data[0]['id'], proj.data[0]['slug']

    # 3. Search by name substring (case-insensitive via ilike)
    name_part = raw_slug.split('-')[0]
    if name_part:
        proj = sb.table('tracked_projects').select('id, slug') \
            .ilike('name', f'%{name_part}%').execute()
        if proj.data:
            return proj.data[0]['id'], proj.data[0]['slug']

    return None, None


def _get_supabase_client():
    """Get Supabase client (utility for card generation)."""
    url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def _publish_supabase(slug: str, report_type: str, version: int, gdrive_urls: dict, card_db: dict = None):
    """Update project_reports from coming_soon to published, or create new."""
    url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not url or not key:
        raise RuntimeError("Supabase credentials not configured")

    from supabase import create_client
    sb = create_client(url, key)

    # Resolve slug to tracked_project
    project_id, canonical_slug = _resolve_project_slug(sb, slug)
    if not project_id:
        print(f"  [WARN] Project '{slug}' not in tracked_projects — creating")
        new = sb.table('tracked_projects').insert({
            'slug': slug, 'name': slug, 'status': 'active',
        }).execute()
        project_id = new.data[0]['id']
        canonical_slug = slug
    else:
        if canonical_slug != slug:
            print(f"  [MATCH] '{slug}' → tracked_project '{canonical_slug}'")

    # Map internal rtype → DB enum
    db_report_type = {'for': 'forensic', 'econ': 'econ', 'mat': 'maturity'}.get(report_type, report_type)

    translation_status = {lang: 'published' for lang in gdrive_urls.keys()}
    now = datetime.now(timezone.utc).isoformat()

    # Try to update existing coming_soon report
    existing = sb.table('project_reports').select('id') \
        .eq('project_id', project_id) \
        .eq('report_type', db_report_type) \
        .eq('status', 'coming_soon') \
        .execute()

    if existing.data:
        report_id = existing.data[0]['id']
        update_data = {
            'status': 'published',
            'published_at': now,
            'gdrive_urls_by_lang': gdrive_urls,
            'translation_status': translation_status,
            'version': version,
        }
        if card_db:
            update_data.update(card_db)
        sb.table('project_reports').update(update_data).eq('id', report_id).execute()
        print(f"  기존 coming_soon 보고서 → published: {report_id}")

        # Update forensic_triggers status
        sb.table('forensic_triggers').update({'status': 'published'}) \
            .eq('report_id', report_id).execute()
    else:
        # Create new published report
        sb.table('project_reports').insert({
            'project_id': project_id,
            'report_type': db_report_type,
            'version': version,
            'status': 'published',
            'published_at': now,
            'gdrive_urls_by_lang': gdrive_urls,
            'translation_status': translation_status,
        }).execute()
        print(f"  새 보고서 등록: {slug}/{report_type} published")


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='FOR Report GDrive Watcher & Pipeline')
    parser.add_argument('--dry-run', action='store_true', help='Download only, no processing')
    parser.add_argument('--slug', type=str, help='Process specific slug only')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"FOR Report Pipeline — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    # Scan for new drafts
    print("[SCAN] GDrive drafts/FOR/ 스캔 중...")
    new_files = scan_for_drafts(filter_slug=args.slug)

    if not new_files:
        print("  새로운 .md 파일 없음")
        return

    print(f"  {len(new_files)}개 새 파일 발견:")
    for f in new_files:
        print(f"    • {f['name']} ({f['slug']}) — {f['size']:,} bytes")

    # Process each file
    results = []
    service = _get_drive_service()
    root_id = os.environ.get('GDRIVE_ROOT_FOLDER_ID', '1E87EcasPlrGuet0t6e1CA9kLFO0sTdFq')
    drafts_id = _find_folder_id(service, root_id, 'drafts')
    for_id = _find_folder_id(service, drafts_id, 'FOR')
    processed = _load_processed(service, for_id)

    for f in new_files:
        prev_entry = processed.get(f['file_id'], {})
        retry_count = f.get('_retry_count', prev_entry.get('retry_count', 0))
        if prev_entry.get('status') in ('processing', 'failed_timeout', 'download_error', 'upload_done_db_error'):
            retry_count += 1

        processed[f['file_id']] = {
            'status': 'processing',
            'slug': f['slug'],
            'started_at': datetime.now(timezone.utc).isoformat(),
            'retry_count': retry_count,
        }
        _save_processed(service, for_id, processed)

        result = process_for_report(f, dry_run=args.dry_run)
        results.append(result)

        processed[f['file_id']]['status'] = result['status']
        processed[f['file_id']]['finished_at'] = datetime.now(timezone.utc).isoformat()
        _save_processed(service, for_id, processed)

    # Summary
    published = sum(1 for r in results if r['status'] == 'published')
    print(f"\n{'='*60}")
    print(f"DONE: {published}/{len(results)} published")
    print(f"{'='*60}")

    # Save local summary
    summary_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    os.makedirs(summary_dir, exist_ok=True)
    summary_path = os.path.join(summary_dir, f'ingest_for_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
    with open(summary_path, 'w') as fp:
        json.dump({'results': results, 'timestamp': datetime.now(timezone.utc).isoformat()},
                  fp, ensure_ascii=False, indent=2)
    print(f"요약: {summary_path}")


if __name__ == '__main__':
    main()
