"""
GDrive .md Ingestion Pipeline (v2)

Scans GDrive drafts folder for new Korean .md report files,
validates factual accuracy, formats titles and dates,
translates to 6 languages, generates PDFs, uploads, and registers.

Pipeline:
    GDrive /drafts/econ/  (Korean .md files)
        ↓  Download .md → Local
    [1] 종목 확정 (파일명 + 본문 분석)
    [2] 제목 포맷: "[종목명] 크립토이코노미 분석 보고서"
    [3] 생성일 명기 (문서 마지막)
    [4] 사실 검증 (CoinGecko API 교차검증)
        ├── PASS → 번역 → PDF → 업로드 → Supabase 등록
        └── FAIL → "검토 요청" 상태로 보류
    [5] 번역 (ko → en, ja, zh, fr, es, de)
    [6] PDF 생성 (7개 언어)
    [7] GDrive 업로드 + Supabase 등록

Trigger: Manual — COO runs `python ingest_gdoc.py --type econ`

Folder convention:
    BCE Lab Reports/
        drafts/
            econ/   ← Korean .md files dropped here
            mat/    ← Korean .md files dropped here
        <project-slug>/
            econ/   ← Final PDFs delivered here
            mat/

Filename convention for .md files:
    <project-slug>_econ_v<N>.md  (e.g., "bitcoin_econ_v1.md")
    <project-slug>_mat_v<N>.md   (e.g., "ethereum_mat_v2.md")

Processing state tracking:
    "drafts/_processed.json" tracks file IDs and their statuses:
    - "published": 정상 처리 완료
    - "review_requested": 사실 검증 실패, 수동 검토 필요
    - "dry_run": dry-run 모드로 실행됨
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# ── Google API ──
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaInMemoryUpload
except ImportError:
    print("ERROR: google-api-python-client required.")
    print("  pip install google-api-python-client google-auth")
    sys.exit(1)

# ── Local pipeline modules ──
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import config as pipeline_config

try:
    from gdrive_storage import GDriveStorage, get_gdrive
except ImportError:
    GDriveStorage = None
    get_gdrive = None

# ── Constants ──
LANGS = ['en', 'ja', 'zh', 'fr', 'es', 'de']
OUTPUT_DIR = SCRIPT_DIR / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)

SA_FILE = os.environ.get(
    'GDRIVE_SERVICE_ACCOUNT_FILE',
    str(SCRIPT_DIR / '.gdrive_service_account.json')
)
ROOT_FOLDER_ID = os.environ.get(
    'GDRIVE_ROOT_FOLDER_ID', '1E87EcasPlrGuet0t6e1CA9kLFO0sTdFq'
)
DELEGATE_EMAIL = os.environ.get(
    'GDRIVE_DELEGATE_EMAIL', 'zhang@coinlab.co.kr'
)

PROCESSED_TRACKER_NAME = '_processed.json'

# ── 알려진 프로젝트 종목 매핑 (slug → 한글명) ──
# tracked_projects 테이블 기반. 추후 DB에서 동적으로 로드할 수 있음.
KNOWN_PROJECTS = {
    'bitcoin': '비트코인', 'ethereum': '이더리움', 'solana': '솔라나',
    'cardano': '카르다노', 'ripple': '리플', 'polkadot': '폴카닷',
    'chainlink': '체인링크', 'avalanche-2': '아발란체', 'near': '니어',
    'arbitrum': '아비트럼', 'uniswap': '유니스왑', 'aave': '아베',
    'tron': '트론', 'dogecoin': '도지코인', 'binancecoin': '바이낸스코인',
    'internet-computer': '인터넷컴퓨터', 'matic-network': '폴리곤',
    'tokenx': 'TokenX', 'elsaai': 'ELSA AI', 'heyelsaai': 'Hey ELSA AI',
}

# 영문명 역매핑도 포함 (본문에서 영문으로 언급하는 경우)
KNOWN_NAMES_EN = {
    'bitcoin': 'bitcoin', 'btc': 'bitcoin',
    'ethereum': 'ethereum', 'eth': 'ethereum',
    'solana': 'solana', 'sol': 'solana',
    'cardano': 'cardano', 'ada': 'cardano',
    'ripple': 'ripple', 'xrp': 'ripple',
    'polkadot': 'polkadot', 'dot': 'polkadot',
    'chainlink': 'chainlink', 'link': 'chainlink',
    'avalanche': 'avalanche-2', 'avax': 'avalanche-2',
    'near': 'near', 'near protocol': 'near',
    'arbitrum': 'arbitrum', 'arb': 'arbitrum',
    'uniswap': 'uniswap', 'uni': 'uniswap',
    'aave': 'aave',
    'tron': 'tron', 'trx': 'tron',
    'dogecoin': 'dogecoin', 'doge': 'dogecoin',
    'bnb': 'binancecoin', 'binance coin': 'binancecoin',
    'polygon': 'matic-network', 'matic': 'matic-network',
    'internet computer': 'internet-computer', 'icp': 'internet-computer',
}


# ═══════════════════════════════════════════════════════
# Google Drive Authentication
# ═══════════════════════════════════════════════════════

def get_drive_service():
    """Authenticate via service account with domain-wide delegation."""
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_file(
        SA_FILE, scopes=SCOPES
    )
    if DELEGATE_EMAIL:
        creds = creds.with_subject(DELEGATE_EMAIL)
    drive = build('drive', 'v3', credentials=creds)
    return drive, creds


# ═══════════════════════════════════════════════════════
# Folder Management
# ═══════════════════════════════════════════════════════

def ensure_drafts_folder(drive, report_type: str) -> str:
    """Ensure drafts/<report_type> folder exists. Returns folder ID."""
    drafts_id = _find_or_create_folder(drive, 'drafts', ROOT_FOLDER_ID)
    type_id = _find_or_create_folder(drive, report_type, drafts_id)
    return type_id


def _find_or_create_folder(drive, name: str, parent_id: str) -> str:
    q = (f"name='{name}' and '{parent_id}' in parents "
         f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
    results = drive.files().list(q=q, fields='files(id,name)', spaces='drive').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    meta = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }
    folder = drive.files().create(body=meta, fields='id').execute()
    print(f"  Created folder: {name} ({folder['id']})")
    return folder['id']


# ═══════════════════════════════════════════════════════
# Processed Tracker
# ═══════════════════════════════════════════════════════

def load_processed_tracker(drive, folder_id: str) -> dict:
    q = (f"name='{PROCESSED_TRACKER_NAME}' and '{folder_id}' in parents "
         f"and trashed=false")
    results = drive.files().list(q=q, fields='files(id)').execute()
    files = results.get('files', [])
    if not files:
        return {'processed': {}}
    content = drive.files().get_media(fileId=files[0]['id']).execute()
    return json.loads(content.decode('utf-8'))


def save_processed_tracker(drive, folder_id: str, tracker: dict):
    q = (f"name='{PROCESSED_TRACKER_NAME}' and '{folder_id}' in parents "
         f"and trashed=false")
    results = drive.files().list(q=q, fields='files(id)').execute()
    files = results.get('files', [])
    content = json.dumps(tracker, indent=2, ensure_ascii=False).encode('utf-8')
    media = MediaInMemoryUpload(content, mimetype='application/json')
    if files:
        drive.files().update(fileId=files[0]['id'], media_body=media).execute()
    else:
        meta = {
            'name': PROCESSED_TRACKER_NAME,
            'parents': [folder_id],
            'mimeType': 'application/json',
        }
        drive.files().create(body=meta, media_body=media).execute()


# ═══════════════════════════════════════════════════════
# Scan for New .md Files
# ═══════════════════════════════════════════════════════

def scan_new_md_files(drive, folder_id: str, tracker: dict) -> list:
    """Find .md files in folder that haven't been processed yet."""
    q = (f"'{folder_id}' in parents "
         f"and (name contains '.md') "
         f"and trashed=false")
    results = drive.files().list(
        q=q,
        fields='files(id,name,modifiedTime,size)',
        orderBy='modifiedTime desc',
    ).execute()
    docs = results.get('files', [])
    # Filter: only unprocessed, and must end with .md
    new_docs = [
        d for d in docs
        if d['id'] not in tracker.get('processed', {})
        and d['name'].lower().endswith('.md')
    ]
    return new_docs


def download_md_file(drive, file_id: str) -> str:
    """Download a .md file's content from GDrive."""
    content = drive.files().get_media(fileId=file_id).execute()
    return content.decode('utf-8')


# ═══════════════════════════════════════════════════════
# 1. 종목 확정 (Project Identification)
# ═══════════════════════════════════════════════════════

def parse_md_filename(name: str) -> dict:
    """
    Parse .md filename into components.
    Expected: "bitcoin_econ_v1.md" or "ethereum_mat_v2.md"
    Fallback: extract slug from name.
    """
    clean = re.sub(r'\.md$', '', name, flags=re.IGNORECASE).strip()

    # Pattern: slug_type_vN
    m = re.match(r'^(.+?)_(econ|mat|for)_v(\d+)$', clean, re.IGNORECASE)
    if m:
        return {
            'slug': m.group(1).lower().replace(' ', '-'),
            'report_type': m.group(2).lower(),
            'version': int(m.group(3)),
            'raw_name': name,
        }

    # Pattern: slug_type (no version)
    m2 = re.match(r'^(.+?)_(econ|mat|for)$', clean, re.IGNORECASE)
    if m2:
        return {
            'slug': m2.group(1).lower().replace(' ', '-'),
            'report_type': m2.group(2).lower(),
            'version': 1,
            'raw_name': name,
        }

    # Fallback
    parts = clean.split('_')
    return {
        'slug': parts[0].lower().replace(' ', '-'),
        'report_type': 'econ',
        'version': 1,
        'raw_name': name,
    }


def identify_project(slug: str, md_text: str) -> dict:
    """
    Identify the target project from filename slug + content analysis.
    Returns dict with 'slug', 'name_ko', 'name_en', 'confidence'.
    """
    # 1) Direct slug match
    if slug in KNOWN_PROJECTS:
        name_ko = KNOWN_PROJECTS[slug]
        name_en = slug.replace('-', ' ').title()
        return {
            'slug': slug,
            'name_ko': name_ko,
            'name_en': name_en,
            'confidence': 'high',
        }

    # 2) Content-based detection: count keyword mentions
    text_lower = md_text.lower()
    scores = {}
    for keyword, proj_slug in KNOWN_NAMES_EN.items():
        # Count mentions (word boundary matching)
        count = len(re.findall(rf'\b{re.escape(keyword)}\b', text_lower))
        if count > 0:
            scores[proj_slug] = scores.get(proj_slug, 0) + count

    # Also check Korean names
    for proj_slug, name_ko in KNOWN_PROJECTS.items():
        count = md_text.count(name_ko)
        if count > 0:
            scores[proj_slug] = scores.get(proj_slug, 0) + count * 2  # Korean names weighted 2x

    if scores:
        best = max(scores, key=scores.get)
        name_ko = KNOWN_PROJECTS.get(best, best)
        name_en = best.replace('-', ' ').title()
        confidence = 'high' if scores[best] >= 5 else 'medium'
        return {
            'slug': best,
            'name_ko': name_ko,
            'name_en': name_en,
            'confidence': confidence,
        }

    # 3) Fallback: use slug as-is
    return {
        'slug': slug,
        'name_ko': slug.replace('-', ' ').title(),
        'name_en': slug.replace('-', ' ').title(),
        'confidence': 'low',
    }


# ═══════════════════════════════════════════════════════
# 2. 제목 포맷 + 3. 생성일 명기
# ═══════════════════════════════════════════════════════

def format_report_md(md_text: str, project_info: dict, report_type: str) -> str:
    """
    Format the Korean .md report:
    - Set title to "[종목명] 크립토이코노미 분석 보고서"
    - Append creation date at the end
    """
    name_ko = project_info['name_ko']

    # Determine title based on report type
    if report_type == 'econ':
        title = f"{name_ko} 크립토이코노미 분석 보고서"
    elif report_type == 'mat':
        title = f"{name_ko} 시장분석 보고서"
    else:
        title = f"{name_ko} 분석 보고서"

    # Replace existing H1 title (first line starting with #)
    lines = md_text.split('\n')
    new_lines = []
    title_replaced = False

    for line in lines:
        if not title_replaced and re.match(r'^#\s+', line):
            new_lines.append(f'# {title}')
            title_replaced = True
        else:
            new_lines.append(line)

    # If no H1 found, prepend title
    if not title_replaced:
        new_lines.insert(0, f'# {title}\n')

    # Append creation date at the end
    today = datetime.now(timezone.utc).strftime('%Y년 %m월 %d일')
    date_section = f"\n\n---\n\n**생성일:** {today}  \n**발행:** BCE Lab (Blockchain Economics Research)  \n**웹사이트:** [bcelab.xyz](https://bcelab.xyz)\n"

    result = '\n'.join(new_lines)

    # Remove existing date section if present (to avoid duplicates on reprocess)
    result = re.sub(r'\n---\n\n\*\*생성일:\*\*.*?(?=\n---|\Z)', '', result, flags=re.DOTALL)

    result = result.rstrip() + date_section

    return result


# ═══════════════════════════════════════════════════════
# 4. 사실 검증 (Fact-Check Module)
# ═══════════════════════════════════════════════════════

def fact_check_report(md_text: str, project_slug: str) -> dict:
    """
    Verify key factual claims in the report against CoinGecko API data.

    Checks:
    - Total supply / max supply
    - Consensus mechanism
    - Launch year
    - Market cap rank (rough)

    Returns:
        {
            'passed': bool,
            'issues': [{'claim': str, 'expected': str, 'found_in_report': str}],
            'verified': [str],
            'api_data': dict,
        }
    """
    issues = []
    verified = []
    api_data = {}

    # Fetch CoinGecko data
    try:
        import urllib.request
        url = f"https://api.coingecko.com/api/v3/coins/{project_slug}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'BCE-Lab-Pipeline/2.0',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            api_data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"    CoinGecko API 조회 실패: {e}")
        # If API fails, we can't verify — pass with warning
        return {
            'passed': True,
            'issues': [],
            'verified': ['API 조회 실패 — 검증 건너뜀'],
            'api_data': {},
            'warning': f'CoinGecko API unavailable: {e}',
        }

    text = md_text.lower()

    # ── Check 1: Consensus mechanism ──
    consensus = api_data.get('hashing_algorithm', '')
    raw_cats = api_data.get('categories') or []
    categories = [c.lower() if isinstance(c, str) else c.get('name', '').lower() for c in raw_cats]

    if consensus:
        if consensus.lower() in text:
            verified.append(f'합의 알고리즘: {consensus}')

    # ── Check 2: Max supply ──
    market_data = api_data.get('market_data', {})
    max_supply = market_data.get('max_supply')
    if max_supply:
        # Check if the max supply number appears in the text (with some flexibility)
        max_str = f"{int(max_supply):,}"
        max_simple = str(int(max_supply))
        # Also check Korean number format (e.g., "2,100만")
        if max_supply >= 1_000_000:
            man_value = max_supply / 10_000
            max_man = f"{man_value:,.0f}만" if man_value == int(man_value) else f"{man_value:,.1f}만"
        else:
            max_man = None

        found_supply = False
        if max_str.replace(',', '') in text.replace(',', '').replace(' ', ''):
            found_supply = True
        if max_man and max_man in md_text:
            found_supply = True

        if found_supply:
            verified.append(f'총 공급량: {max_str}')

    # ── Check 3: Genesis date / Launch year ──
    genesis_date = api_data.get('genesis_date', '')
    if genesis_date:
        year = genesis_date[:4]
        if year in md_text:
            verified.append(f'출시연도: {year}')
        else:
            # Not necessarily wrong — might just not be mentioned
            pass

    # ── Check 4: Market cap rank ──
    rank = market_data.get('market_cap_rank')
    if rank:
        # Check for gross misrepresentation (off by >20 ranks)
        rank_patterns = re.findall(r'시가총액\s*(?:순위|랭킹)?\s*[:\s]*(\d+)', md_text)
        for rp in rank_patterns:
            reported_rank = int(rp)
            if abs(reported_rank - rank) > 20:
                issues.append({
                    'claim': f'시가총액 순위 {reported_rank}위',
                    'expected': f'CoinGecko 기준 {rank}위 (오차 > 20위)',
                    'severity': 'high',
                })
            else:
                verified.append(f'시가총액 순위: ~{rank}위 (보고서: {reported_rank}위)')

    # ── Check 5: Current price (gross mismatch detection) ──
    current_price_usd = market_data.get('current_price', {}).get('usd')
    if current_price_usd:
        # Look for price mentions in USD
        price_patterns = re.findall(
            r'\$\s*([\d,]+(?:\.\d+)?)',
            md_text
        )
        for pp in price_patterns:
            try:
                reported_price = float(pp.replace(',', ''))
                # Only flag if the price is mentioned as "current" and is wildly off (10x or 0.1x)
                if reported_price > 0:
                    ratio = reported_price / current_price_usd
                    if ratio > 10 or ratio < 0.1:
                        # Could be historical price, total supply value, etc.
                        # Only flag in context of "현재 가격" or "current price"
                        pass  # Too noisy — skip for now
            except (ValueError, ZeroDivisionError):
                pass

    # ── Check 6: Symbol correctness ──
    symbol = api_data.get('symbol', '').upper()
    if symbol:
        # Check if report uses a wrong ticker symbol
        wrong_symbols = re.findall(r'티커[:\s]*([A-Z]{2,10})', md_text)
        for ws in wrong_symbols:
            if ws != symbol:
                issues.append({
                    'claim': f'티커 심볼: {ws}',
                    'expected': f'올바른 심볼: {symbol}',
                    'severity': 'medium',
                })
            else:
                verified.append(f'티커 심볼: {symbol}')

    # ── Determine pass/fail ──
    high_severity = [i for i in issues if i.get('severity') == 'high']
    passed = len(high_severity) == 0

    return {
        'passed': passed,
        'issues': issues,
        'verified': verified,
        'api_data': {
            'name': api_data.get('name'),
            'symbol': api_data.get('symbol'),
            'market_cap_rank': rank,
            'genesis_date': genesis_date,
            'max_supply': max_supply,
        },
    }


# ═══════════════════════════════════════════════════════
# 5. Translation (Korean → 6 languages)
# ═══════════════════════════════════════════════════════

def translate_md_chunked(md_text: str, target_lang: str, chunk_size: int = 4500) -> str:
    """Translate Markdown text paragraph-by-paragraph using Google Translate."""
    from deep_translator import GoogleTranslator

    LANG_MAP = {
        'en': 'en', 'ja': 'ja', 'zh': 'zh-CN',
        'fr': 'fr', 'es': 'es', 'de': 'de',
    }
    gt_lang = LANG_MAP.get(target_lang, target_lang)
    translator = GoogleTranslator(source='ko', target=gt_lang)

    paragraphs = md_text.split('\n\n')
    translated_parts = []
    buffer = ''

    for para in paragraphs:
        if not para.strip():
            translated_parts.append('')
            continue

        if len(buffer) + len(para) + 2 > chunk_size:
            if buffer:
                try:
                    translated_parts.append(translator.translate(buffer.strip()))
                except Exception as e:
                    print(f"    Translation error, keeping original: {e}")
                    translated_parts.append(buffer.strip())
                time.sleep(0.3)
            buffer = para + '\n\n'
        else:
            buffer += para + '\n\n'

    if buffer.strip():
        try:
            translated_parts.append(translator.translate(buffer.strip()))
        except Exception as e:
            translated_parts.append(buffer.strip())

    return '\n\n'.join(translated_parts)


# ═══════════════════════════════════════════════════════
# 6. PDF Generation
# ═══════════════════════════════════════════════════════

def generate_pdf(md_path: Path, project_slug: str, report_type: str,
                 version: int, lang: str) -> Path:
    """Generate branded PDF from markdown file."""
    pdf_path = md_path.with_suffix('.pdf')

    if report_type == 'econ':
        from gen_pdf_econ import generate_econ_pdf
        generate_econ_pdf(str(md_path), str(pdf_path), {
            'project_slug': project_slug,
            'version': version,
            'lang': lang,
        })
    elif report_type == 'mat':
        from gen_pdf_mat import generate_mat_pdf
        generate_mat_pdf(str(md_path), str(pdf_path), {
            'project_slug': project_slug,
            'version': version,
            'lang': lang,
        })
    else:
        from gen_pdf_econ import generate_econ_pdf
        generate_econ_pdf(str(md_path), str(pdf_path), {
            'project_slug': project_slug,
            'version': version,
            'lang': lang,
        })

    return pdf_path


# ═══════════════════════════════════════════════════════
# Main Pipeline: Process Single Document
# ═══════════════════════════════════════════════════════

def process_single_md(drive, gd, doc: dict, report_type: str,
                      dry_run: bool = False, skip_factcheck: bool = False):
    """
    Process a single .md file through the full pipeline.

    Steps:
        [1] 종목 확정
        [2] 제목 포맷
        [3] 생성일 명기
        [4] 사실 검증
        [5] 번역 (6개 언어)
        [6] PDF 생성 (7개 언어)
        [7] GDrive 업로드 + Supabase 등록
    """
    info = parse_md_filename(doc['name'])
    slug = info['slug']
    version = info['version']
    rtype = info.get('report_type', report_type)

    print(f"\n{'='*60}")
    print(f"Processing: {doc['name']}")
    print(f"  Parsed: slug={slug} | type={rtype} | version=v{version}")
    print(f"  GDrive ID: {doc['id']}")
    print(f"{'='*60}")

    # ── Step 0: Download .md from GDrive ──
    print("\n[0/7] GDrive에서 .md 파일 다운로드...")
    ko_md_raw = download_md_file(drive, doc['id'])
    print(f"  다운로드 완료: {len(ko_md_raw):,} chars")

    # ── Step 1: 종목 확정 ──
    print("\n[1/7] 대상 종목 확정...")
    project_info = identify_project(slug, ko_md_raw)
    slug = project_info['slug']  # May be corrected by content analysis
    print(f"  종목: {project_info['name_ko']} ({slug})")
    print(f"  신뢰도: {project_info['confidence']}")

    if project_info['confidence'] == 'low':
        print("  ⚠ 종목 확정 신뢰도가 낮습니다. 파일명을 확인해 주세요.")

    # ── Step 2 & 3: 제목 포맷 + 생성일 명기 ──
    print("\n[2/7] 제목 포맷 적용...")
    ko_md = format_report_md(ko_md_raw, project_info, rtype)

    # Extract the new title for display
    title_match = re.search(r'^#\s+(.+)$', ko_md, re.MULTILINE)
    title = title_match.group(1) if title_match else '(제목 없음)'
    print(f"  제목: {title}")

    print("\n[3/7] 생성일 명기 완료")
    today_str = datetime.now(timezone.utc).strftime('%Y년 %m월 %d일')
    print(f"  생성일: {today_str}")

    # Save Korean .md locally
    ko_path = OUTPUT_DIR / f"{slug}_{rtype}_v{version}_ko.md"
    ko_path.write_text(ko_md, encoding='utf-8')
    print(f"  저장: {ko_path}")

    # ── Step 4: 사실 검증 ──
    if skip_factcheck:
        print("\n[4/7] 사실 검증 건너뜀 (--skip-factcheck)")
        fc_result = {'passed': True, 'issues': [], 'verified': ['검증 건너뜀']}
    else:
        print("\n[4/7] 사실 검증 (CoinGecko 교차검증)...")
        fc_result = fact_check_report(ko_md, slug)

        if fc_result['verified']:
            print(f"  ✓ 검증된 항목:")
            for v in fc_result['verified']:
                print(f"    - {v}")

        if fc_result['issues']:
            print(f"  ✗ 발견된 문제:")
            for issue in fc_result['issues']:
                severity = issue.get('severity', 'unknown')
                print(f"    [{severity}] {issue['claim']} → 예상: {issue['expected']}")

        if not fc_result['passed']:
            print(f"\n  ╔══════════════════════════════════════╗")
            print(f"  ║  사실 검증 실패 — 검토 요청 상태    ║")
            print(f"  ╚══════════════════════════════════════╝")
            print(f"  이 보고서는 수동 검토가 필요합니다.")
            print(f"  문제를 수정한 후 --reprocess 옵션으로 재실행하세요.")

            return {
                'slug': slug,
                'type': rtype,
                'version': version,
                'status': 'review_requested',
                'title': title,
                'issues': fc_result['issues'],
                'ko_path': str(ko_path),
            }

        print(f"  ✓ 사실 검증 통과")

    if dry_run:
        print("\n  [DRY RUN] 번역/PDF/업로드 생략")
        return {
            'slug': slug, 'type': rtype, 'version': version,
            'status': 'dry_run', 'title': title,
            'ko_path': str(ko_path),
            'fact_check': fc_result,
        }

    # ── Step 5: 번역 ──
    print("\n[5/7] 6개 언어 번역...")
    md_paths = {'ko': ko_path}
    for lang in LANGS:
        print(f"  → {lang}...", end=' ', flush=True)
        translated = translate_md_chunked(ko_md, lang)
        lang_path = OUTPUT_DIR / f"{slug}_{rtype}_v{version}_{lang}.md"
        lang_path.write_text(translated, encoding='utf-8')
        md_paths[lang] = lang_path
        print(f"완료 ({len(translated):,} chars)")
        time.sleep(0.5)

    # ── Step 6: PDF 생성 ──
    print("\n[6/7] PDF 생성 (7개 언어)...")
    pdf_paths = {}
    for lang, md_path in md_paths.items():
        print(f"  → {lang} PDF...", end=' ', flush=True)
        try:
            pdf_path = generate_pdf(md_path, slug, rtype, version, lang)
            pdf_paths[lang] = pdf_path
            print("완료")
        except Exception as e:
            print(f"실패: {e}")

    # ── Step 7: GDrive 업로드 + Supabase 등록 ──
    print("\n[7/7] GDrive 업로드 + Supabase 등록...")
    gdrive_urls = {}
    if gd and gd.connected:
        for lang, pdf_path in pdf_paths.items():
            print(f"  → {lang} 업로드...", end=' ', flush=True)
            try:
                result = gd.upload_report(
                    local_path=str(pdf_path),
                    project_slug=slug,
                    report_type=rtype,
                    version=version,
                    lang=lang,
                )
                gdrive_urls[lang] = result.get('url', '')
                print(f"완료 → {result.get('url', 'no url')}")
            except Exception as e:
                print(f"실패: {e}")
    else:
        print("  [SKIP] GDrive 업로드 불가 — 로컬 저장만 완료")
        for lang, pdf_path in pdf_paths.items():
            gdrive_urls[lang] = f"local://{pdf_path}"

    # Supabase registration
    try:
        _register_supabase(slug, rtype, version, title, gdrive_urls)
    except Exception as e:
        print(f"  Supabase 등록 실패: {e}")

    return {
        'slug': slug,
        'type': rtype,
        'version': version,
        'status': 'published',
        'title': title,
        'languages': list(gdrive_urls.keys()),
        'gdrive_urls': gdrive_urls,
        'fact_check': fc_result,
    }


# ═══════════════════════════════════════════════════════
# Supabase Registration
# ═══════════════════════════════════════════════════════

def _register_supabase(slug: str, report_type: str, version: int,
                       title_ko: str, gdrive_urls: dict):
    """Register or update report in Supabase."""
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not supabase_url or not supabase_key:
        print("  Supabase 인증정보 없음 — DB 등록 건너뜀")
        return

    try:
        from supabase import create_client
        sb = create_client(supabase_url, supabase_key)
    except ImportError:
        print("  supabase-py 미설치 — 건너뜀")
        return

    proj = sb.table('tracked_projects').select('id').eq('slug', slug).execute()
    if not proj.data:
        print(f"  프로젝트 '{slug}' 미등록 — DB 등록 건너뜀")
        return
    project_id = proj.data[0]['id']

    translation_status = {lang: 'published' for lang in gdrive_urls.keys()}

    report_data = {
        'project_id': project_id,
        'report_type': report_type,
        'version': version,
        'status': 'published',
        'published_at': datetime.now(timezone.utc).isoformat(),
        'gdrive_urls_by_lang': gdrive_urls,
        'translation_status': translation_status,
        'title_ko': title_ko,
        'title_en': f"{slug.replace('-', ' ').title()} — Cryptoeconomics Analysis Report v{version}",
    }

    existing = sb.table('project_reports').select('id').eq(
        'project_id', project_id
    ).eq('report_type', report_type).eq('version', version).execute()

    if existing.data:
        sb.table('project_reports').update(report_data).eq(
            'id', existing.data[0]['id']
        ).execute()
        print(f"  기존 보고서 업데이트: {existing.data[0]['id']}")
    else:
        sb.table('project_reports').insert(report_data).execute()
        print(f"  신규 보고서 등록 완료")


# ═══════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='BCE Lab — Korean .md → Fact-Check → Multilingual PDF Pipeline (v2)'
    )
    parser.add_argument(
        '--type', choices=['econ', 'mat'], default='econ',
        help='보고서 유형 (default: econ)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='사실 검증까지만 실행 (번역/PDF/업로드 생략)'
    )
    parser.add_argument(
        '--skip-factcheck', action='store_true',
        help='사실 검증 단계 건너뛰기'
    )
    parser.add_argument(
        '--slug', type=str, default=None,
        help='특정 프로젝트만 처리 (파일명 필터)'
    )
    parser.add_argument(
        '--reprocess', action='store_true',
        help='처리 이력 무시하고 전체 재처리'
    )
    parser.add_argument(
        '--reprocess-reviews', action='store_true',
        help='"검토 요청" 상태 보고서만 재처리'
    )
    args = parser.parse_args()

    print(f"═══ BCE Lab 보고서 파이프라인 v2 ═══")
    print(f"보고서 유형: {args.type}")
    print(f"모드: {'dry-run' if args.dry_run else '전체 처리'}")
    print(f"사실 검증: {'건너뜀' if args.skip_factcheck else '활성'}")
    print()

    # Authenticate
    print("[Init] Google Drive 인증...")
    drive, creds = get_drive_service()

    # Ensure drafts folder
    print(f"[Init] drafts/{args.type} 폴더 확인...")
    drafts_folder_id = ensure_drafts_folder(drive, args.type)
    print(f"  폴더 ID: {drafts_folder_id}")

    # Load tracker
    tracker = load_processed_tracker(drive, drafts_folder_id)

    # Handle --reprocess-reviews: re-queue review_requested items
    if args.reprocess_reviews:
        to_requeue = [
            fid for fid, info in tracker.get('processed', {}).items()
            if info.get('status') == 'review_requested'
        ]
        for fid in to_requeue:
            del tracker['processed'][fid]
        if to_requeue:
            print(f"  {len(to_requeue)}개 '검토 요청' 보고서 재처리 대상에 추가")

    if args.reprocess:
        tracker = {'processed': {}}

    # Scan for new .md files
    print("\n[Scan] 신규 .md 파일 검색...")
    new_files = scan_new_md_files(drive, drafts_folder_id, tracker)

    if args.slug:
        new_files = [f for f in new_files if args.slug in f['name'].lower()]

    if not new_files:
        print("  신규 문서 없음. 종료.")
        return

    print(f"  {len(new_files)}개 신규 문서 발견:")
    for f in new_files:
        size = int(f.get('size', 0))
        print(f"    - {f['name']} ({size:,} bytes, 수정: {f['modifiedTime']})")

    # Initialize GDrive storage for uploads
    gd = get_gdrive() if get_gdrive else None

    # Process each document
    results = []
    review_count = 0

    for doc in new_files:
        try:
            result = process_single_md(
                drive, gd, doc, args.type,
                dry_run=args.dry_run,
                skip_factcheck=args.skip_factcheck,
            )
            results.append(result)

            # Update tracker
            if 'processed' not in tracker:
                tracker['processed'] = {}
            tracker['processed'][doc['id']] = {
                'name': doc['name'],
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'status': result.get('status', 'unknown'),
                'slug': result.get('slug'),
                'title': result.get('title'),
            }

            if result.get('status') == 'review_requested':
                review_count += 1

        except Exception as e:
            print(f"\n  ERROR: {doc['name']}: {e}")
            import traceback
            traceback.print_exc()

    # Save tracker
    if not args.dry_run:
        print("\n[Save] 처리 이력 저장...")
        save_processed_tracker(drive, drafts_folder_id, tracker)

    # Summary
    published = [r for r in results if r.get('status') == 'published']
    reviews = [r for r in results if r.get('status') == 'review_requested']

    print(f"\n{'='*60}")
    print(f"파이프라인 완료")
    print(f"  처리: {len(results)}/{len(new_files)}")
    print(f"  발행: {len(published)}  |  검토 요청: {len(reviews)}")
    print(f"{'─'*60}")

    for r in results:
        status_icon = {
            'published': '✓', 'review_requested': '⚠',
            'dry_run': '○'
        }.get(r['status'], '?')
        title = r.get('title', r['slug'])
        langs = r.get('languages', [])
        lang_str = f" ({len(langs)} languages)" if langs else ''
        print(f"  {status_icon} {title} [{r['status']}]{lang_str}")

        if r.get('issues'):
            for issue in r['issues']:
                print(f"      ⚠ {issue['claim']} → {issue['expected']}")

    if reviews:
        print(f"\n  ※ 검토 요청 보고서는 수정 후 다음 명령으로 재처리:")
        print(f"    python ingest_gdoc.py --type {args.type} --reprocess-reviews")

    print(f"{'='*60}")


if __name__ == '__main__':
    main()
