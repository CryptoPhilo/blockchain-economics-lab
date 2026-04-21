"""
BCE Lab Report Production Pipeline — Configuration
"""
import os

# ═══════════════════════════════════════════
# BRANDING
# ═══════════════════════════════════════════
ORG_NAME = "BCE Lab"
ORG_FULL = "Blockchain Economics Research"
DOMAIN = "bcelab.xyz"
COPYRIGHT_YEAR = 2026

# ═══════════════════════════════════════════
# SUPPORTED LANGUAGES (STR-002)
# ═══════════════════════════════════════════
LANGUAGES = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh']
MASTER_LANGUAGES = ['en', 'ko']       # Written by researchers
TRANSLATION_LANGUAGES = ['fr', 'es', 'de', 'ja', 'zh']  # Translated from EN

LANGUAGE_NAMES = {
    'en': 'English', 'ko': '한국어', 'fr': 'Français',
    'es': 'Español', 'de': 'Deutsch', 'ja': '日本語', 'zh': '中文'
}

# ═══════════════════════════════════════════
# REPORT TYPES (STR-002 §2)
# ═══════════════════════════════════════════
REPORT_TYPES = {
    'econ': {
        'code': 'RPT-ECON',
        'name_en': 'AI Agent Economy Design Analysis',
        'name_ko': 'AI 에이전트 경제 설계분석 보고서',
        'name_fr': "Analyse de Conception Économique d'Agent IA",
        'name_es': 'Análisis de Diseño Económico de Agente IA',
        'name_de': 'KI-Agenten Wirtschaftsdesign-Analyse',
        'name_ja': 'AIエージェント経済設計分析',
        'name_zh': 'AI代理经济设计分析',
        'min_pages': 15,
        'max_pages': 25,
        'update_cycle_months': 6,
        'confidential': False,
    },
    'mat': {
        'code': 'RPT-MAT',
        'name_en': 'Project Maturity Report',
        'name_ko': '프로젝트 성숙도 보고서',
        'name_fr': 'Rapport de Maturité du Projet',
        'name_es': 'Informe de Madurez del Proyecto',
        'name_de': 'Projekt-Reifebericht',
        'name_ja': 'プロジェクト成熟度レポート',
        'name_zh': '项目成熟度报告',
        'min_pages': 10,
        'max_pages': 15,
        'update_cycle_months': 3,
        'confidential': False,
    },
    'for': {
        'code': 'RPT-FOR',
        'name_en': 'Forensic Report',
        'name_ko': '포렌식 보고서',
        'name_fr': 'Rapport Forensique',
        'name_es': 'Informe Forense',
        'name_de': 'Forensischer Bericht',
        'name_ja': 'フォレンジックレポート',
        'name_zh': '取证报告',
        'min_pages': 8,
        'max_pages': 15,
        'update_cycle_months': None,  # Event-based
        'confidential': True,
    },
}

# ═══════════════════════════════════════════
# MATURITY LEVELS (report-production-process §1.2)
# ═══════════════════════════════════════════
MATURITY_LEVELS = {
    'nascent':     (0, 30,  'Nascent',     '초기 단계'),
    'growing':     (31, 60, 'Growing',     '성장 단계'),
    'mature':      (61, 85, 'Mature',      '성숙 단계'),
    'established': (86, 100,'Established', '확립 단계'),
}

# ═══════════════════════════════════════════
# FORENSIC TRIGGERS (STR-002 §3.2, CRO-002 개정)
# ═══════════════════════════════════════════
# v2: 시장 평균 대비 상대 변동률(relative deviation) 기반
# 개별 토큰 변동률에서 전체 암호화폐 시총 변동률(BTC+ETH+전체)을
# 차감한 "초과 변동률"이 임계값을 초과하면 트리거 발동
#
# 예) 시장 평균 -5%, 토큰 -18% → 초과 하락 = -13% → 트리거 (≥10%)
# 예) 시장 평균 +10%, 토큰 +12% → 초과 상승 = +2% → 트리거 안 됨
FORENSIC_TRIGGERS = {
    'relative_deviation_24h_pct': 10.0,   # |토큰 변동 - 시장 평균| ≥ 10%
    'volume_ratio_7d_avg': 3.0,           # 거래량 ≥ 7일 평균의 3배
    'whale_movement_supply_pct': 1.0,     # 고래 이동 ≥ 유통 공급의 1%
    'exchange_netflow_supply_pct': 0.5,   # 거래소 순유입 ≥ 유통 공급의 0.5%
    'report_validity_days': 7,            # FOR 보고서 유효 기간 (일) - BCE-481
}

# 시장 평균 산출 기준
MARKET_BENCHMARK = {
    'method': 'total_market_cap_change_24h',   # CoinGecko global data 기반
    'fallback': 'btc_weighted',                # 실패 시 BTC 70% + ETH 30% 가중 평균
}

# ═══════════════════════════════════════════
# COLORS (Tiger Research + BCE Lab branding)
# ═══════════════════════════════════════════
COLORS = {
    # Typography (Tiger Research inspired)
    'primary_text':      '#1A1A1A',       # Near-black for titles, main text
    'body_text':         '#333333',       # Dark gray for body
    'accent':            '#2D8F5E',       # BCE Lab green — brand identity
    'accent_coral':      '#E8724A',       # Tiger Research coral — captions, highlights
    'section_divider_bg': '#2D8F5E',      # Green for dividers and section markers

    # Table styling (Tiger Research + functional)
    'table_header_bg':   '#3D3D3D',       # Dark gray header
    'table_alt_row':     '#F8F8F8',       # Very light gray alternating rows
    'table_border':      '#E0E0E0',       # Light gray borders

    # Neutrals & support
    'white':             '#FFFFFF',
    'light_gray':        '#E0E0E0',
    'mid_gray':          '#999999',
    'slate_50':          '#F8FAFC',

    # Semantic text colors (3-color hierarchy)
    'score_green':       '#2D8F5E',       # Scores, positive labels (평가, 장점, 결론 label)
    'risk_red':          '#C0392B',       # Risk/warning labels (한계, 리스크)
    'conclusion_bg':     '#F5F7F5',       # Conclusion box background

    # Legacy semantic colors
    'forensic_red':      '#DC2626',       # High contrast red for forensic reports
    'green':             '#16A34A',
    'red':               '#DC2626',
    'amber':             '#D97706',
    'blue':              '#2563EB',

    # Legacy/fallback (kept for backward compatibility)
    'indigo':            '#4F46E5',
    'accent_green':      '#2D8F5E',       # Maps to new primary accent
    'dark_bg':           '#1B2631',
    'cover_strip':       '#2C3E50',
    'slate_800':         '#1E293B',
    'slate_700':         '#334155',
    'slate_600':         '#475569',
    'slate_100':         '#F1F5F9',
    'table_header':      '#3D3D3D',
}

# ═══════════════════════════════════════════
# RATING SYSTEM (legacy)
# ═══════════════════════════════════════════
RATINGS = ['S', 'A', 'B', 'C', 'D']

# ═══════════════════════════════════════════
# BCE UNIVERSAL RATINGS (OPS-002)
# ═══════════════════════════════════════════
BCE_GRADES = ['A', 'B', 'C', 'D', 'F', 'UR']

BCE_GRADE_THRESHOLDS = {
    'A':  (80, 100),
    'B':  (65, 79),
    'C':  (50, 64),
    'D':  (35, 49),
    'F':  (0, 34),
    # UR is assigned when transparency_score < 10, regardless of total
}

TRANSPARENCY_LABELS = {
    'OPEN':    (26, 30),  # 🟢
    'MOSTLY':  (19, 25),  # 🔵
    'PARTIAL': (13, 18),  # 🟡
    'LIMITED': (7, 12),   # 🟠
    'OPAQUE':  (0, 6),    # 🔴
}

# Report eligibility thresholds
# v2: C등급(50-64) → 3종 리포트, D등급(35-49) → ECON+MAT
REPORT_DECISIONS = {
    'FULL':       {'min_total': 80, 'min_transparency': 19},  # ECON + MAT + FOR (A/B등급 고투명)
    'STANDARD':   {'min_total': 50, 'min_transparency': 0},   # ECON + MAT + FOR (C등급+)
    'MINIMAL':    {'min_total': 35, 'min_transparency': 0},   # ECON + MAT (D등급)
    'SCAN_ONLY':  {'min_total': 20, 'min_transparency': 0},   # Grade only
    'UNRATABLE':  {'min_total': 0,  'min_transparency': 0},   # UR
}

# Transparency score < this → always UNRATABLE
UNRATABLE_TRANSPARENCY_THRESHOLD = 10

# Maturity scoring weights
MATURITY_WEIGHTS = {
    'exchange_listings': 15,  # 0-15: number of CEX listings
    'volume_ratio':      15,  # 0-15: vol/mcap ratio (healthy: 5-30%)
    'derivatives':       10,  # 0-10: futures market exists
    'market_cap':        10,  # 0-10: log-scale market cap
    'holder_count':      10,  # 0-10: on-chain holder count
    'project_age':       10,  # 0-10: time since genesis
}

# Forensic auto-trigger thresholds (자동 리포트 생성 기준, 수동보다 엄격)
# v2: 상대 변동률 기반 — 시장 평균 차감 후 판정
FORENSIC_AUTO_TRIGGERS = {
    'relative_deviation_24h_pct': 15.0,  # |토큰 변동 - 시장 평균| ≥ 15% (자동 FOR 리포트)
    'volume_spike_ratio':   5.0,         # > 5× 7-day average
    'whale_supply_pct':     2.0,         # > 2% of supply in 24h
    'exchange_netflow_pct': 1.0,         # > 1% of supply to exchanges
}


def get_forensic_scan_deviation_threshold() -> float:
    """
    Threshold for scanner/monitor candidate detection.

    This is the broader gate used to surface projects for review and register
    `coming_soon` forensic work when the market-relative move is large enough.
    """
    return float(FORENSIC_TRIGGERS.get('relative_deviation_24h_pct', 10.0))


def get_forensic_auto_deviation_threshold() -> float:
    """
    Threshold for automatic FOR generation.

    This intentionally stays stricter than the scan threshold so the system can
    surface 10%+ candidates without auto-triggering full FOR generation until
    the move reaches the auto-FOR threshold.
    """
    return float(FORENSIC_AUTO_TRIGGERS.get('relative_deviation_24h_pct', 15.0))

# Daily pipeline schedule (UTC)
DAILY_PIPELINE_SCHEDULE = {
    'phase_a_token_list':     '06:00',
    'phase_b_market_data':    '07:00',
    'phase_c_transparency':   '08:00',
    'phase_d_triage':         '09:00',
    'phase_e_report_queue':   '09:30',
    'phase_f_publish':        '10:00',
}

# Rotation: scan 1/5 of tokens per day for transparency (API quota management)
TRANSPARENCY_SCAN_ROTATION_DAYS = 5

# ═══════════════════════════════════════════
# DATA SOURCES (CRO-001)
# ═══════════════════════════════════════════
# CoinGecko (primary — free tier, no API key)
COINGECKO_BATCH_SIZE = 250  # max 250 per /coins/markets call
COINGECKO_RATE_LIMIT_SLEEP = 2.5  # seconds between requests

# CoinMarketCap (secondary — free Basic tier)
# Set CMC_API_KEY environment variable or leave empty to skip
CMC_API_KEY = os.environ.get('CMC_API_KEY', '')
CMC_BATCH_SIZE = 5000  # max per /listings/latest call
CMC_RATE_LIMIT_SLEEP = 2.0  # seconds between requests
CMC_MONTHLY_CREDIT_LIMIT = 10000  # free tier budget
CMC_DAILY_CREDIT_BUDGET = 300  # ~10K/month ÷ 30 days, conservative

# Data source priority (Phase A token list)
TOKEN_LIST_SOURCES = ['coingecko', 'coinmarketcap']  # Order = priority for dedup
TOKEN_LIST_PRIMARY = 'coingecko'  # Takes precedence on symbol conflicts

# Max reports to generate per day (API/compute budget)
MAX_DAILY_REPORTS = 10

# ═══════════════════════════════════════════
# FILE NAMING (report-production-process §3.5)
# {project_slug}_{report_type}_v{version}_{language}.pdf
# ═══════════════════════════════════════════
def report_filename(project_slug: str, report_type: str, version: int, lang: str) -> str:
    return f"{project_slug}_{report_type}_v{version}_{lang}.pdf"

def report_storage_path(project_slug: str, report_type: str, version: int, lang: str) -> str:
    return f"reports/{project_slug}/{report_type}/v{version}/{lang}.pdf"

# ═══════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PIPELINE_DIR, 'output')
TEMPLATE_DIR = os.path.join(PIPELINE_DIR, 'templates')

os.makedirs(OUTPUT_DIR, exist_ok=True)
