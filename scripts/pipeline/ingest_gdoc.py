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
import unicodedata
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
    'bitcoin-cash': '비트코인 캐시', 'zcash': 'Zcash', 'stellar': '스텔라',
    'sui': 'Sui', 'aptos': '앱토스', 'ethena': 'Ethena',
    'lido-dao': '리도 파이낸스', 'algorand': '알고랜드',
    'flare-networks': '플레어 네트워크', 'ondo-finance': '온도 파이낸스',
    'tether': '테더', 'hedera-hashgraph': '헤데라',
    'the-open-network': 'TON', 'yearn-finance': 'Yearn Finance',
    'monero': '모네로', 'hyperliquid': '하이퍼리퀴드',
    'story-protocol': '스토리 프로토콜', 'walletconnect': '월렛커넥트',
    'official-trump': '$TRUMP', 'degen-base': 'DEGEN',
    # ── 2026-04-13 추가: GDrive 신규 프로젝트 ──
    'paypal-usd': '페이팔 USD', 'litecoin': '라이트코인',
    'maker': 'Sky 프로토콜', 'leo-token': 'UNUS SED LEO',
    'canton-network': '칸톤 네트워크', 'usd-coin': 'USDC',
    'orderly-network': 'Orderly Network',
    'world-liberty-financial': '월드 리버티 파이낸셜',
    'chutes-ai': 'Chutes.ai', 'synfutures': 'SynFutures',
    'soon-network': 'SOON Network', 'kaito-ai': 'Kaito AI',
    'spacecoin': 'SpaceCoin', 'river-protocol': '리버 프로토콜',
    'cross-crypto': '크로스', 'unitas-protocol': 'Unitas',
    'usdg': 'USDG', 'mantle': '맨틀 네트워크',
    'tether-gold': '테더 골드', 'cronos': '크로노스',
    'memecore': 'MemeCore',
    'pi-network': '파이 네트워크', 'okx': 'OKX',
    # ── 2026-04-16 추가: econ pipeline 신규 프로젝트 ──
    'dexe': 'DeXe', 'filecoin': '파일코인', 'morpho': 'Morpho',
    'gatechain': '게이트체인', 'cosmos': '코스모스', 'kaspa': '카스파',
    'render-token': '렌더', 'quant-network': 'QNT', 'kcc': 'KCC',
    'ethereum-classic': '이더리움클래식', 'rlusd': 'RLUSD',
    'bitget-token': '비트겟', 'pepe': '페페', 'usdd': 'USDD',
    'astar': 'Aster', 'ravedao': 'RaveDAO',
    'unstoppable-domains': 'UD',
}

# 한글명 → slug 역매핑 (파일명에서 한글 종목명 추출에 사용)
KNOWN_NAMES_KO = {v: k for k, v in KNOWN_PROJECTS.items()}
# 추가 한글 매핑 (파일명에 나타나는 다양한 표현)
KNOWN_NAMES_KO.update({
    '비트코인': 'bitcoin', '이더리움': 'ethereum', '솔라나': 'solana',
    '카르다노': 'cardano', '리플': 'ripple', '폴카닷': 'polkadot',
    '체인링크': 'chainlink', '아발란체': 'avalanche-2', '니어': 'near',
    '아비트럼': 'arbitrum', '유니스왑': 'uniswap', '아베': 'aave',
    '트론': 'tron', '도지코인': 'dogecoin', '바이낸스코인': 'binancecoin',
    '인터넷컴퓨터': 'internet-computer', '폴리곤': 'matic-network',
    '비트코인 캐시': 'bitcoin-cash', '스텔라': 'stellar',
    '앱토스': 'aptos', '리도 파이낸스': 'lido-dao',
    '알고랜드': 'algorand', '플레어 네트워크': 'flare-networks',
    '온도 파이낸스': 'ondo-finance', '테더': 'tether', '헤데라': 'hedera-hashgraph',
    '모네로': 'monero', '하이퍼리퀴드': 'hyperliquid',
    '스토리 프로토콜': 'story-protocol', '월렛커넥트': 'walletconnect',
    # ── 2026-04-13 추가 ──
    '페이팔': 'paypal-usd', '페이팔 USD': 'paypal-usd', 'PYUSD': 'paypal-usd',
    '라이트코인': 'litecoin', '메이커다오': 'maker', 'MakerDAO': 'maker',
    'Sky 프로토콜': 'maker', '칸톤 네트워크': 'canton-network', '칸톤': 'canton-network',
    '월드 리버티 파이낸셜': 'world-liberty-financial', 'WLFI': 'world-liberty-financial',
    '리버 프로토콜': 'river-protocol', '크로스': 'cross-crypto',
    '맨틀 네트워크': 'mantle', '맨틀': 'mantle',
    '테더 골드': 'tether-gold', '크로노스': 'cronos',
    '파이 네트워크': 'pi-network', '파이네트워크': 'pi-network',
    # ── 2026-04-16 추가 ──
    '게이트체인': 'gatechain', '코스모스': 'cosmos', '카스파': 'kaspa',
    '렌더': 'render-token', '파일코인': 'filecoin',
    '이더리움클래식': 'ethereum-classic', '비트겟': 'bitget-token',
    '페페': 'pepe',
})

# 영문명 역매핑 (본문/파일명에서 영문으로 언급하는 경우)
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
    'bitcoin cash': 'bitcoin-cash', 'bch': 'bitcoin-cash',
    'zcash': 'zcash', 'zec': 'zcash',
    'stellar': 'stellar', 'xlm': 'stellar',
    'sui': 'sui', 'aptos': 'aptos', 'apt': 'aptos',
    'ethena': 'ethena', 'ena': 'ethena',
    'lido': 'lido-dao', 'ldo': 'lido-dao',
    'algorand': 'algorand', 'algo': 'algorand',
    'flare': 'flare-networks', 'flr': 'flare-networks',
    'ondo': 'ondo-finance', 'tether': 'tether', 'usdt': 'tether',
    'hedera': 'hedera-hashgraph', 'hbar': 'hedera-hashgraph',
    'ton': 'the-open-network', 'toncoin': 'the-open-network',
    'yearn': 'yearn-finance', 'yfi': 'yearn-finance',
    'monero': 'monero', 'xmr': 'monero',
    'hyperliquid': 'hyperliquid', 'hype': 'hyperliquid',
    'walletconnect': 'walletconnect', 'wct': 'walletconnect',
    'degen': 'degen-base', 'trump': 'official-trump',
    'story protocol': 'story-protocol',
    'heyelsaai': 'heyelsaai', 'heyelsa': 'heyelsaai', 'elsa': 'elsaai',
    # ── 2026-04-13 추가 ──
    'paypal usd': 'paypal-usd', 'pyusd': 'paypal-usd', 'paypal': 'paypal-usd',
    'litecoin': 'litecoin', 'ltc': 'litecoin',
    'maker': 'maker', 'makerdao': 'maker', 'sky': 'maker', 'mkr': 'maker',
    'leo': 'leo-token', 'unus sed leo': 'leo-token',
    'canton': 'canton-network', 'canton network': 'canton-network',
    'usdc': 'usd-coin', 'usd coin': 'usd-coin',
    'orderly': 'orderly-network', 'orderly network': 'orderly-network',
    'world liberty financial': 'world-liberty-financial', 'wlfi': 'world-liberty-financial',
    'chutes': 'chutes-ai', 'chutes.ai': 'chutes-ai',
    'synfutures': 'synfutures',
    'soon': 'soon-network', 'soon network': 'soon-network',
    'kaito': 'kaito-ai', 'kaito ai': 'kaito-ai',
    'spacecoin': 'spacecoin', 'space coin': 'spacecoin',
    'river': 'river-protocol', 'river protocol': 'river-protocol',
    'cross': 'cross-crypto',
    'unitas': 'unitas-protocol',
    'usdg': 'usdg', 'mantle': 'mantle', 'mnt': 'mantle', 'mantle network': 'mantle',
    'tether gold': 'tether-gold', 'xaut': 'tether-gold',
    'cronos': 'cronos', 'cro': 'cronos',
    'memecore': 'memecore',
    'pi network': 'pi-network', 'pi': 'pi-network',
    'okx': 'okx', 'okb': 'okx', 'okex': 'okx',
    # ── 2026-04-16 추가 ──
    'dexe': 'dexe', 'filecoin': 'filecoin', 'fil': 'filecoin',
    'morpho': 'morpho', 'gatechain': 'gatechain', 'gate': 'gatechain', 'gt': 'gatechain',
    'cosmos': 'cosmos', 'atom': 'cosmos',
    'kaspa': 'kaspa', 'kas': 'kaspa',
    'render': 'render-token', 'rndr': 'render-token',
    'quant': 'quant-network', 'qnt': 'quant-network',
    'kcc': 'kcc', 'kucoin': 'kcc',
    'ethereum classic': 'ethereum-classic', 'etc': 'ethereum-classic',
    'rlusd': 'rlusd', 'ripple usd': 'rlusd',
    'bitget': 'bitget-token', 'bgb': 'bitget-token',
    'pepe': 'pepe',
    'usdd': 'usdd',
    'aster': 'astar', 'astar': 'astar', 'astr': 'astar',
    'ravedao': 'ravedao', 'rave': 'ravedao',
    'unstoppable domains': 'unstoppable-domains', 'ud': 'unstoppable-domains',
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
# Equation Image Stripper (from ingest_for.py)
# ═══════════════════════════════════════════════════════

def _strip_equation_images(md_text: str) -> tuple[str, int]:
    """Remove base64 equation image definitions and their inline references.

    Google Docs renders LaTeX-style math ($0.026$) as inline PNG images.
    When exported to markdown, these become ![][imageN] references with
    base64 data at the end of the file. We strip them (no OCR).

    Returns (cleaned_text, stripped_count).
    """
    def_pattern = re.compile(
        r'^\[image(\d+)\]:\s*<data:image/png;base64,[^>]+>\s*$',
        re.MULTILINE,
    )
    img_names = {f'image{m.group(1)}' for m in def_pattern.finditer(md_text)}

    if not img_names:
        return md_text, 0

    result = md_text
    count = 0

    for img_name in img_names:
        pat = re.compile(re.escape(f'![][{img_name}]'))
        matches = len(pat.findall(result))
        result = pat.sub('', result)
        count += matches

    result = def_pattern.sub('', result)
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result, count


# ═══════════════════════════════════════════════════════
# Citation & Reference Post-Processor (BCE-603)
# ═══════════════════════════════════════════════════════

def _normalize_citations(md_text: str) -> tuple[str, int]:
    """Convert bare footnote-style citations to bracket format.

    Deep Research outputs citations as bare numbers appended to text,
    e.g. "한다.1" or "있다.13". This converts them to "[1]" / "[13]".

    Targets Korean sentence endings followed by bare numbers:
    - 한다.1 → 한다.[1]
    - 있다.13 → 있다.[13]
    - 된다).9 → 된다).[9]

    Avoids false positives: version numbers (v3.1), percentages (25%),
    years (2026), table data, etc.

    Returns (cleaned_text, conversion_count).
    """
    # Match bare numbers after Korean text endings (다, 음, 임, 됨, etc.)
    # or after closing punctuation that follows Korean text
    pattern = re.compile(
        r'(?<=[가-힣])(\.)(\d{1,3})(?=\s|$|\n|[,\;\:])'
        r'|'
        r'(?<=[가-힣]\))(\.)(\d{1,3})(?=\s|$|\n|[,\;\:])',
        re.MULTILINE,
    )

    seen_nums: set[str] = set()
    for m in pattern.finditer(md_text):
        num = m.group(2) or m.group(4)
        if num:
            seen_nums.add(num)

    if len(seen_nums) < 3:
        return md_text, 0

    max_num = max(int(n) for n in seen_nums)
    if max_num > 200:
        return md_text, 0

    count = 0

    def _replace(m: re.Match) -> str:
        nonlocal count
        dot = m.group(1) or m.group(3)
        num = m.group(2) or m.group(4)
        count += 1
        return f'{dot}[{num}]'

    result = pattern.sub(_replace, md_text)
    return result, count


def _ensure_references_heading(md_text: str) -> str:
    """Ensure a '참고문헌' heading exists if bracket citations are present.

    If citations like [1], [2] exist but no references section is found,
    append a placeholder heading so downstream QA can flag it.
    """
    if not re.search(r'\[\d{1,3}\]', md_text):
        return md_text

    ref_patterns = [
        r'^#{1,3}\s*참고\s*문헌',
        r'^#{1,3}\s*References',
        r'^#{1,3}\s*출처',
        r'^#{1,3}\s*참조',
    ]
    for pat in ref_patterns:
        if re.search(pat, md_text, re.MULTILINE | re.IGNORECASE):
            return md_text

    md_text = md_text.rstrip() + '\n\n---\n\n## 참고문헌\n\n> ⚠️ 참고문헌 목록이 원본에 누락되어 있습니다. 수동 검토가 필요합니다.\n'
    return md_text


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
    """Find .md files and Google Docs in folder that haven't been processed yet."""
    # Query 1: .md files (text/markdown, text/plain, etc.)
    q_md = (f"'{folder_id}' in parents "
            f"and (name contains '.md') "
            f"and trashed=false")
    results_md = drive.files().list(
        q=q_md,
        fields='files(id,name,modifiedTime,size,mimeType)',
        orderBy='modifiedTime desc',
    ).execute()
    docs = results_md.get('files', [])
    seen_ids = {d['id'] for d in docs}

    # Query 2: Google Docs (may be uploaded via web without .md extension)
    q_gdocs = (f"'{folder_id}' in parents "
               f"and mimeType='application/vnd.google-apps.document' "
               f"and trashed=false")
    results_gdocs = drive.files().list(
        q=q_gdocs,
        fields='files(id,name,modifiedTime,size,mimeType)',
        orderBy='modifiedTime desc',
    ).execute()
    gdocs = results_gdocs.get('files', [])

    # Add Google Docs to the list (mark them as _gdoc for later handling)
    for doc in gdocs:
        if doc['id'] not in seen_ids:
            doc['_gdoc'] = True
            # Add synthetic .md extension if missing for slug parsing
            if not doc['name'].endswith('.md'):
                doc['name'] = doc['name'] + '.md'
            docs.append(doc)
            seen_ids.add(doc['id'])

    # Filter: only unprocessed files
    new_docs = [
        d for d in docs
        if d['id'] not in tracker.get('processed', {})
    ]
    return new_docs



def download_md_file(drive, file_id: str, is_gdoc: bool = False) -> str:
    """Download a .md file's content from GDrive. Handles both raw files and Google Docs."""
    if is_gdoc:
        # Google Docs must be exported — use text/plain for markdown-like content
        content = drive.files().export(fileId=file_id, mimeType='text/plain').execute()
        if isinstance(content, str):
            content = content.encode('utf-8')
    else:
        content = drive.files().get_media(fileId=file_id).execute()
    return content.decode('utf-8')


# ═══════════════════════════════════════════════════════
# 1. 종목 확정 (Project Identification)
# ═══════════════════════════════════════════════════════

def parse_md_filename(name: str) -> dict:
    """
    Parse .md filename into components.

    Handles multiple naming conventions:
    1. Standard: "bitcoin_econ_v1.md"
    2. Korean title: "비트코인 크립토 이코노미 분석 보고서.md"
    3. Korean title with English: "아비트럼(Arbitrum) 크립토 이코노미 심층 분석 보고서.md"
    4. English title: "TRON 크립토 이코노미 분석 보고서.md"
    """
    clean = re.sub(r'\.md$', '', name, flags=re.IGNORECASE).strip()

    # ── Pattern A: Standard slug_type_vN ──
    m = re.match(r'^(.+?)_(econ|mat|for)_v(\d+)$', clean, re.IGNORECASE)
    if m:
        return {
            'slug': unicodedata.normalize('NFC', m.group(1).lower().replace(' ', '-')),
            'report_type': m.group(2).lower(),
            'version': int(m.group(3)),
            'raw_name': name,
        }

    # ── Pattern B: slug_type (no version) ──
    m2 = re.match(r'^(.+?)_(econ|mat|for)$', clean, re.IGNORECASE)
    if m2:
        return {
            'slug': unicodedata.normalize('NFC', m2.group(1).lower().replace(' ', '-')),
            'report_type': m2.group(2).lower(),
            'version': 1,
            'raw_name': name,
        }

    # ── Pattern C: Korean/English title → extract project name ──
    # Try to match known Korean project names in the filename
    slug_from_title = _extract_slug_from_title(clean)
    if slug_from_title:
        # Determine report type from filename keywords
        rtype = 'econ'
        cl = clean.lower()
        if ('시장분석' in clean or 'mat' in cl
                or '진행률' in clean or '성숙도' in clean
                or '평가 보고서' in clean or '평가보고서' in clean):
            rtype = 'mat'

        # Extract version if present (e.g., "v2" or "20260108")
        ver_match = re.search(r'v(\d+)', clean, re.IGNORECASE)
        version = int(ver_match.group(1)) if ver_match else 1

        return {
            'slug': slug_from_title,
            'report_type': rtype,
            'version': version,
            'raw_name': name,
        }

    # ── Fallback: use first meaningful part as slug ──
    parts = clean.split('_')
    return {
        'slug': unicodedata.normalize('NFC', parts[0].lower().replace(' ', '-')),
        'report_type': 'econ',
        'version': 1,
        'raw_name': name,
    }


def _extract_slug_from_title(title: str) -> str | None:
    """
    Extract project slug from a Korean/English title.

    Tries:
    1. Known Korean names (longest match first)
    2. English name in parentheses: "아비트럼(Arbitrum)"
    3. Leading English word: "TRON 크립토..."
    4. Known English names
    """
    # 1. Match known Korean names (longest first to avoid partial matches)
    #    Normalize both sides (NFC) to handle GDrive NFD filenames
    title_nfc = unicodedata.normalize('NFC', title)
    for ko_name in sorted(KNOWN_NAMES_KO.keys(), key=len, reverse=True):
        ko_nfc = unicodedata.normalize('NFC', ko_name)
        if ko_nfc in title_nfc:
            return KNOWN_NAMES_KO[ko_name]

    # 2. English name in parentheses: "앱토스(Aptos)" or "Ethena (ENA)"
    paren_match = re.search(r'[\(（]([A-Za-z][A-Za-z0-9\s\.\-]+?)[\)）]', title)
    if paren_match:
        en_name = paren_match.group(1).strip().lower()
        if en_name in KNOWN_NAMES_EN:
            return KNOWN_NAMES_EN[en_name]
        # Try as CoinGecko-style slug
        return en_name.replace(' ', '-')

    # 3. Leading English word(s) before Korean text
    lead_match = re.match(r'^([A-Za-z][A-Za-z0-9\.\-\s]*?)[\s_]', title)
    if lead_match:
        en_name = lead_match.group(1).strip().lower()
        if en_name in KNOWN_NAMES_EN:
            return KNOWN_NAMES_EN[en_name]
        if len(en_name) >= 2:
            return en_name.replace(' ', '-')

    # 4. Any known English name anywhere in the title
    title_lower = title.lower()
    for en_name in sorted(KNOWN_NAMES_EN.keys(), key=len, reverse=True):
        if len(en_name) >= 3 and en_name in title_lower:
            return KNOWN_NAMES_EN[en_name]

    return None


def identify_project(slug: str, md_text: str) -> dict:
    """
    Identify the target project from filename slug + content analysis.
    Returns dict with 'slug', 'name_ko', 'name_en', 'confidence'.

    Priority:
      1. Exact slug match in KNOWN_PROJECTS → high confidence
      2. Clean English slug from filename (not a Korean fallback) → medium confidence
         (trusted over content analysis which tends to pick 'ethereum' for all reports)
      3. Content-based keyword counting → only for ambiguous/Korean fallback slugs
      4. Fallback: slug as-is → low confidence
    """
    # 1) Direct slug match in KNOWN_PROJECTS
    if slug in KNOWN_PROJECTS:
        name_ko = KNOWN_PROJECTS[slug]
        name_en = slug.replace('-', ' ').title()
        return {
            'slug': slug,
            'name_ko': name_ko,
            'name_en': name_en,
            'confidence': 'high',
        }

    # 2) If slug is a clean English identifier from filename parsing, trust it.
    #    Content-based detection is unreliable — common tokens like "ethereum"
    #    appear in nearly every crypto report and dominate keyword counts.
    _is_clean_english_slug = (
        slug
        and len(slug) <= 40
        and re.match(r'^[a-z0-9][a-z0-9\-]*$', slug)
    )
    if _is_clean_english_slug:
        name_en = slug.replace('-', ' ').title()
        return {
            'slug': slug,
            'name_ko': name_en,
            'name_en': name_en,
            'confidence': 'medium',
        }

    # 3) Content-based detection (for Korean/ambiguous slugs only)
    text_lower = md_text.lower()
    scores = {}
    for keyword, proj_slug in KNOWN_NAMES_EN.items():
        count = len(re.findall(rf'\b{re.escape(keyword)}\b', text_lower))
        if count > 0:
            scores[proj_slug] = scores.get(proj_slug, 0) + count

    # Also check Korean names
    for proj_slug, name_ko in KNOWN_PROJECTS.items():
        count = md_text.count(name_ko)
        if count > 0:
            scores[proj_slug] = scores.get(proj_slug, 0) + count * 2

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

    # 4) Fallback: use slug as-is
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
        title = f"{name_ko} 프로젝트 진행률 평가 보고서"
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

def _translate_with_retry(translator, text: str, max_retries: int = 3) -> str:
    """Translate text with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            result = translator.translate(text)
            if result:
                return result
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 2  # 2s, 4s, 6s
                print(f"    Retry {attempt+1}/{max_retries} after {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"    Translation failed after {max_retries} retries: {e}")
                raise
    return text


def _split_long_text(text: str, max_len: int) -> list:
    """Split text that exceeds max_len into smaller pieces by newline or sentence."""
    if len(text) <= max_len:
        return [text]
    # Try splitting by newline first
    lines = text.split('\n')
    if len(lines) > 1:
        chunks = []
        buf = ''
        for line in lines:
            if len(buf) + len(line) + 1 > max_len:
                if buf:
                    chunks.append(buf)
                # If single line is still too long, split by sentence
                if len(line) > max_len:
                    chunks.extend(_split_by_sentence(line, max_len))
                else:
                    buf = line
                continue
            buf = buf + '\n' + line if buf else line
        if buf:
            chunks.append(buf)
        return chunks
    # Single block, split by sentence
    return _split_by_sentence(text, max_len)


def _split_by_sentence(text: str, max_len: int) -> list:
    """Split text by sentence boundaries (. ! ?)."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    buf = ''
    for sent in sentences:
        if len(buf) + len(sent) + 1 > max_len:
            if buf:
                chunks.append(buf)
            if len(sent) > max_len:
                # Last resort: hard split
                for i in range(0, len(sent), max_len):
                    chunks.append(sent[i:i+max_len])
                buf = ''
            else:
                buf = sent
        else:
            buf = buf + ' ' + sent if buf else sent
    if buf:
        chunks.append(buf)
    return chunks


def translate_md_chunked(md_text: str, target_lang: str, chunk_size: int = 2000) -> str:
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
    fail_count = 0

    def flush_buffer(buf):
        """Translate and flush buffer content, handling oversized buffers."""
        nonlocal fail_count
        if not buf.strip():
            return
        pieces = _split_long_text(buf.strip(), chunk_size)
        for piece in pieces:
            try:
                translated_parts.append(_translate_with_retry(translator, piece))
            except Exception as e:
                print(f"    Translation error, keeping original: {e}")
                translated_parts.append(piece)
                fail_count += 1
            time.sleep(0.5)

    for para in paragraphs:
        if not para.strip():
            translated_parts.append('')
            continue

        if len(buffer) + len(para) + 2 > chunk_size:
            if buffer:
                flush_buffer(buffer)
            buffer = para + '\n\n'
        else:
            buffer += para + '\n\n'

    if buffer.strip():
        flush_buffer(buffer)

    if fail_count > 0:
        print(f"    Warning: {fail_count} chunk(s) kept in original Korean")

    return '\n\n'.join(translated_parts)


# ═══════════════════════════════════════════════════════
# 6. PDF Generation
# ═══════════════════════════════════════════════════════

def _extract_mat_score(md_text: str):
    """Extract total maturity score from a MAT Korean markdown body.

    Looks for the summary row of the achievement-rate table (row labelled
    '합계 달성률' / '최종 합계 진행률' / '종합 진행률') and picks the rightmost
    numeric value that isn't 100 (the weight-sum column). Falls back to prose.
    """
    import re as _re
    summary_row_re = _re.compile(
        r'\|\s*\*{0,2}\s*(?:최종\s*)?(?:합계(?:\s*달성률|\s*진행률)?|종합\s*진행률|종합)\s*\*{0,2}\s*\|[^\n]*'
    )
    def _pick(row):
        nums = _re.findall(r'\*{0,2}\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*\*{0,2}', row)
        for n in reversed(nums):
            try:
                v = float(n)
                if v != 100.0 and 0 < v <= 100:
                    return v
            except ValueError:
                continue
        return None
    for m in summary_row_re.finditer(md_text):
        v = _pick(m.group(0))
        if v is not None:
            return v
    for pat in [
        r'전체\s*달성률[은이]?\s*\\?\*{0,2}\s*([0-9]+\.?[0-9]*)\s*%',
        r'종합\s*진행률[은이]?\s*\\?\*{0,2}\s*([0-9]+\.?[0-9]*)\s*%',
        r'진행률[은이]?\s*\\?\*{0,2}\s*([0-9]+\.?[0-9]*)\s*%\s*로\s*(?:평가|산출)',
    ]:
        m = _re.search(pat, md_text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _classify_stage(score):
    if score is None: return 'growing'
    if score >= 85:   return 'established'
    if score >= 60:   return 'mature'
    if score >= 30:   return 'growing'
    return 'nascent'


def generate_pdf(md_path: Path, project_slug: str, report_type: str,
                 version: int, lang: str) -> Path:
    """Generate branded PDF from markdown file."""
    pdf_path = md_path.with_suffix('.pdf')

    metadata = {
        'project_slug': project_slug,
        'project_name': project_slug.replace('-', ' ').title(),
        'slug': project_slug,
        'version': version,
        'lang': lang,
    }

    # MAT: pull canonical score + stage from the KO source
    if report_type == 'mat':
        try:
            ko_path = md_path.parent / md_path.name.replace(f'_{lang}.', '_ko.')
            src = ko_path if ko_path.exists() else md_path
            score = _extract_mat_score(src.read_text(encoding='utf-8'))
            if score is not None:
                metadata['total_maturity_score'] = score
                metadata['maturity_stage'] = _classify_stage(score)
        except Exception as e:
            print(f"    Warning: MAT score extraction failed: {e}")

    if report_type == 'econ':
        from gen_pdf_econ import generate_pdf_econ
        generate_pdf_econ(str(md_path), metadata, lang=lang, output_path=str(pdf_path))
    elif report_type == 'mat':
        from gen_pdf_mat import generate_pdf_mat
        generate_pdf_mat(str(md_path), metadata, lang=lang, output_path=str(pdf_path))
    else:
        from gen_pdf_econ import generate_pdf_econ
        generate_pdf_econ(str(md_path), metadata, lang=lang, output_path=str(pdf_path))

    # ── QA verification gate ────────────────────────────────────────────
    # Run automated inspection BEFORE returning the PDF so the caller can
    # decide whether to upload. Environment flag QA_STRICT=1 raises on FAIL.
    try:
        from qa_verify import verify_pdf, QASeverity
        import os as _os
        qa = verify_pdf(pdf_path, lang=lang,
                        report_type=('mat' if report_type == 'mat' else report_type),
                        metadata=metadata)
        fails = [c for c in qa.checks if c.severity == QASeverity.FAIL]
        warns = [c for c in qa.checks if c.severity == QASeverity.WARN]
        if fails:
            print(f"    [QA][FAIL] {pdf_path.name}: "
                  + "; ".join(f"{c.name}({c.detail})" for c in fails[:4]))
            if _os.environ.get('QA_STRICT') == '1':
                raise RuntimeError(f"QA FAIL on {pdf_path.name}: "
                                   + "; ".join(c.name for c in fails))
        elif warns:
            print(f"    [QA][WARN] {pdf_path.name}: "
                  + "; ".join(c.name for c in warns[:4]))
        else:
            print(f"    [QA][PASS] {pdf_path.name} ({qa.page_count}p)")
    except Exception as _qa_err:
        # Never block pipeline on QA itself crashing; surface the error.
        print(f"    [QA] verifier error (non-fatal): {_qa_err}")

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
    # Folder-scoped report_type is authoritative (drafts/econ vs drafts/mat)
    rtype = report_type or info.get('report_type', 'econ')

    print(f"\n{'='*60}")
    print(f"Processing: {doc['name']}")
    print(f"  Parsed: slug={slug} | type={rtype} | version=v{version}")
    print(f"  GDrive ID: {doc['id']}")
    print(f"{'='*60}")

    # ── Step 0: Download .md from GDrive ──
    is_gdoc = doc.get('_gdoc', False)
    print(f"\n[0/7] GDrive에서 파일 다운로드{' (Google Doc export)' if is_gdoc else ''}...")
    ko_md_raw = download_md_file(drive, doc['id'], is_gdoc=is_gdoc)
    print(f"  다운로드 완료: {len(ko_md_raw):,} chars")

    # ── Step 0b: Strip equation images (no OCR — just remove base64 refs) ──
    if '![][image' in ko_md_raw:
        print("\n[0b] 수식 이미지 제거 (strip)...")
        try:
            ko_md_raw, eq_count = _strip_equation_images(ko_md_raw)
            if eq_count > 0:
                print(f"  제거 완료: {eq_count}개 수식 이미지")
        except Exception as e:
            print(f"  [WARN] 수식 이미지 제거 실패 (계속 진행): {e}")

    # ── Step 0c: Normalize citations (bare footnote → bracket) ──
    print("\n[0c] 인용 형식 정규화...")
    try:
        ko_md_raw, cite_count = _normalize_citations(ko_md_raw)
        if cite_count > 0:
            print(f"  변환 완료: {cite_count}개 footnote → [N] 형식")
        else:
            print("  변환 대상 없음 (이미 정상 형식)")
    except Exception as e:
        print(f"  [WARN] 인용 형식 정규화 실패 (계속 진행): {e}")

    # ── Step 0d: Ensure references section exists ──
    ko_md_raw = _ensure_references_heading(ko_md_raw)

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

    # ── Step 3.5: Pre-translation markdown QA (catch unresolved OCR markers) ──
    try:
        from qa_verify_md import verify_markdown as _verify_md
        from qa_verify import QASeverity as _QASev
        _md_qa = _verify_md(str(ko_path), lang='ko')
        _md_fails = [c for c in _md_qa.checks if c.severity == _QASev.FAIL]
        if _md_fails:
            _fail_names = [c.name for c in _md_fails]
            print(f"  ⚠ Markdown QA FAIL: {_fail_names}")
            if any('unresolved_ocr' in c.name for c in _md_fails):
                print(f"  ⚠ [?] markers detected in markdown")
        else:
            print(f"  ✓ Markdown QA passed")
    except Exception as e:
        print(f"  [WARN] Markdown QA check error (계속 진행): {e}")

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

    # MAT: Persist maturity score with QA validation
    if rtype == 'maturity':
        try:
            _persist_maturity_score_gdoc(slug, ko_md)
        except Exception as e:
            print(f"  MAT score persistence 실패: {e}")

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
# MAT Score Persistence with QA
# ═══════════════════════════════════════════════════════

def _persist_maturity_score_gdoc(slug: str, ko_text: str):
    """
    Extract maturity score from Korean markdown and persist to tracked_projects.
    Includes QA validation to prevent bad data.
    """
    import re as _re, json as _json

    print(f"\n  [MAT Score] 점수 추출 및 DB 기록...")

    score = _extract_mat_score(ko_text)
    if score is None:
        print("  [SKIP] 점수 추출 실패 — 합계 달성률 패턴 미발견")
        return

    # ── QA-1: Range check ──
    if not (0 < score <= 100):
        print(f"  ✗ QA ERROR: 점수 {score}이(가) 유효 범위(0-100)를 벗어남")
        return

    stage = _classify_stage(score)

    # ── Extract axis data from evaluation table ──
    axes = []
    lines = ko_text.split('\n')
    in_eval_table = False
    for line in lines:
        if '|' in line and any(kw in line for kw in ['가중치', '비중']) and any(kw in line for kw in ['달성률', '달성도', '달성']):
            in_eval_table = True
            continue
        if in_eval_table and '|' in line and ':----' in line:
            continue
        if in_eval_table and '|' in line:
            # Check for total row → stop
            if any(kw in line for kw in ['합계', '종합', '최종']):
                in_eval_table = False
                continue
            cells = [c.strip().strip('*') for c in line.split('|')]
            cells = [c for c in cells if c]
            if len(cells) >= 3:
                name = cells[0]
                # Extract weight and achievement from remaining cells
                nums = _re.findall(r'(\d+\.?\d+)', '|'.join(cells[1:3]))
                if len(nums) >= 2:
                    weight = float(nums[0])
                    achievement = float(nums[1])
                    # QA: validate ranges
                    if 0 <= weight <= 100 and 0 <= achievement <= 100:
                        axes.append({'name': name, 'weight': round(weight, 1), 'achievement': round(achievement, 1)})
        elif in_eval_table and '|' not in line:
            in_eval_table = False

    # ── QA-2: Cross-check score from axes ──
    if axes:
        total_w = sum(a['weight'] for a in axes)
        if total_w > 0:
            recalc = sum(a['weight'] * a['achievement'] / total_w for a in axes)
            diff = abs(round(recalc, 2) - score)
            if diff > 5.0:
                print(f"  ⚠ QA WARN: 재계산 점수({recalc:.1f})와 보고서 점수({score})의 차이가 {diff:.1f}점")

    print(f"  ✓ QA 통과 — score={score}, stage={stage}, axes={len(axes)}")

    # ── Write to DB ──
    supabase_url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not supabase_url or not supabase_key:
        print("  [SKIP] Supabase 인증정보 없음")
        return

    from supabase import create_client
    sb = create_client(supabase_url, supabase_key)

    update_data = {'maturity_score': score, 'maturity_stage': stage}
    if axes:
        update_data['maturity_axes'] = _json.dumps(axes, ensure_ascii=False)

    sb.table('tracked_projects').update(update_data).eq('slug', slug).execute()
    print(f"  ✓ tracked_projects 업데이트: maturity_score={score} ({stage}), axes={len(axes)}")


# ═══════════════════════════════════════════════════════
# Supabase Registration
# ═══════════════════════════════════════════════════════

def _register_supabase(slug: str, report_type: str, version: int,
                       title_ko: str, gdrive_urls: dict):
    """Register or update report in Supabase."""
    supabase_url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
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
