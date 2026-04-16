"""
gen_report_title.py — 포렌식 보고서 제목 자동 생성 (2단계)

■ Phase 1: coming_soon 단계 — 트리거 사유 기반 제목
  분석 대상으로 선정된 이유(가격 이상 변동, 거래량 급증 등)를 제목에 반영.
  예: "RAVE 87.8% 급등 감지: 포렌식 분석 개시"

■ Phase 2: published 단계 — 보고서 내용 기반 제목
  card_data(요약, 가격변동, 키워드)로부터 최종 제목을 생성.
  예: "ENJ 45% 급등: 숏스퀴즈가 이끄는 비유기적 상승"

Usage:
    # Phase 1: 트리거 기반 제목 (coming_soon)
    from gen_report_title import generate_trigger_titles
    titles = generate_trigger_titles(trigger_data, symbol)

    # Phase 2: 보고서 기반 제목 (published)
    from gen_report_title import generate_titles
    titles = generate_titles(card_data, project_name, symbol)

    # 백필
    python gen_report_title.py --backfill
"""
from __future__ import annotations

import os
import re
import sys

# ── 가격 변동 방향 표현 ──

_KO_DIRECTION = {
    'big_up':   '{symbol} {pct}% 급등',
    'up':       '{symbol} {pct}% 상승',
    'small_up': '{symbol} {pct}% 소폭 상승',
    'flat':     '{symbol} 횡보',
    'small_dn': '{symbol} {pct}% 소폭 하락',
    'down':     '{symbol} {pct}% 하락',
    'big_dn':   '{symbol} {pct}% 급락',
}

_EN_DIRECTION = {
    'big_up':   '{symbol} Surges {pct}%',
    'up':       '{symbol} Rallies {pct}%',
    'small_up': '{symbol} Up {pct}%',
    'flat':     '{symbol} Holds Steady',
    'small_dn': '{symbol} Dips {pct}%',
    'down':     '{symbol} Falls {pct}%',
    'big_dn':   '{symbol} Plunges {pct}%',
}

_JA_DIRECTION = {
    'big_up':   '{symbol} {pct}%急騰',
    'up':       '{symbol} {pct}%上昇',
    'small_up': '{symbol} {pct}%小幅上昇',
    'flat':     '{symbol} 横ばい',
    'small_dn': '{symbol} {pct}%小幅下落',
    'down':     '{symbol} {pct}%下落',
    'big_dn':   '{symbol} {pct}%暴落',
}

_ZH_DIRECTION = {
    'big_up':   '{symbol} 暴涨{pct}%',
    'up':       '{symbol} 上涨{pct}%',
    'small_up': '{symbol} 小幅上涨{pct}%',
    'flat':     '{symbol} 横盘',
    'small_dn': '{symbol} 小幅下跌{pct}%',
    'down':     '{symbol} 下跌{pct}%',
    'big_dn':   '{symbol} 暴跌{pct}%',
}

_FR_DIRECTION = {
    'big_up':   '{symbol} en hausse de {pct}%',
    'up':       '{symbol} en hausse de {pct}%',
    'small_up': '{symbol} en légère hausse de {pct}%',
    'flat':     '{symbol} stable',
    'small_dn': '{symbol} en légère baisse de {pct}%',
    'down':     '{symbol} en baisse de {pct}%',
    'big_dn':   '{symbol} en chute de {pct}%',
}

_ES_DIRECTION = {
    'big_up':   '{symbol} sube {pct}%',
    'up':       '{symbol} sube {pct}%',
    'small_up': '{symbol} sube ligeramente {pct}%',
    'flat':     '{symbol} estable',
    'small_dn': '{symbol} baja ligeramente {pct}%',
    'down':     '{symbol} cae {pct}%',
    'big_dn':   '{symbol} cae {pct}%',
}

_DE_DIRECTION = {
    'big_up':   '{symbol} steigt {pct}%',
    'up':       '{symbol} steigt {pct}%',
    'small_up': '{symbol} leicht gestiegen {pct}%',
    'flat':     '{symbol} stabil',
    'small_dn': '{symbol} leicht gefallen {pct}%',
    'down':     '{symbol} fällt {pct}%',
    'big_dn':   '{symbol} stürzt {pct}% ab',
}

_DIRECTION_BY_LANG = {
    'ko': _KO_DIRECTION, 'en': _EN_DIRECTION,
    'ja': _JA_DIRECTION, 'zh': _ZH_DIRECTION,
    'fr': _FR_DIRECTION, 'es': _ES_DIRECTION, 'de': _DE_DIRECTION,
}

_FINDING_FALLBACK = {
    'ko': '포렌식 리스크 분석', 'en': 'Forensic Risk Analysis',
    'ja': 'フォレンジックリスク分析', 'zh': '取证风险分析',
    'fr': 'Analyse de risque forensique', 'es': 'Análisis de riesgo forense',
    'de': 'Forensische Risikoanalyse',
}


def _direction_key(change: float) -> str:
    """가격 변동 폭에 따라 방향 키를 반환."""
    abs_c = abs(change)
    if abs_c < 1:
        return 'flat'
    elif change > 0:
        if abs_c >= 20:
            return 'big_up'
        elif abs_c >= 5:
            return 'up'
        else:
            return 'small_up'
    else:
        if abs_c >= 20:
            return 'big_dn'
        elif abs_c >= 5:
            return 'down'
        else:
            return 'small_dn'


# ── 핵심 발견(서브타이틀) 추출 ──

# 한국어 키워드 → 핵심 메시지 매핑
_KO_KEYWORD_PHRASES = {
    '숏스퀴즈':     '숏스퀴즈 감지',
    '고래분배':     '고래 분배 임박',
    '고래매집':     '고래 매집 포착',
    '자전거래':     '자전거래 의심',
    '내부자거래':   '내부자 거래 포착',
    '조작의심':     '시세 조종 의심',
    '대규모청산':   '대규모 청산 위험',
    '펀딩비이상':   '펀딩비 이상 신호',
    '거래소유출':   '거래소 대량 유출',
    'OI급등':       'OI 사상 최고치',
    'RSI과매수':    'RSI 과매수 영역',
    '파생상품과열': '파생상품 과열',
    '스푸핑':       '스푸핑 패턴 감지',
    '락업해제':     '락업 해제 임박',
    '기관자금유입': '기관 자금 유입',
    '분산단계':     '분산 단계 진입',
}

_EN_KEYWORD_PHRASES = {
    'short squeeze':          'Short Squeeze Detected',
    'whale distribution':     'Whale Distribution Imminent',
    'whale accumulation':     'Whale Accumulation Detected',
    'wash trading':           'Wash Trading Suspected',
    'insider trading':        'Insider Trading Detected',
    'manipulation suspected': 'Market Manipulation Suspected',
    'mass liquidation':       'Mass Liquidation Risk',
    'funding rate anomaly':   'Funding Rate Anomaly',
    'exchange outflow':       'Major Exchange Outflows',
    'oi spike':               'OI Hits All-Time High',
    'rsi overbought':         'RSI in Overbought Territory',
    'derivatives overheating':'Derivatives Market Overheating',
    'spoofing':               'Spoofing Pattern Detected',
    'lock-up release':        'Lock-up Release Approaching',
    'institutional flow':     'Institutional Inflows Detected',
    'distribution phase':     'Distribution Phase Entered',
    'whale activity':         'Whale Activity Surge',
}


def _pick_ko_finding(keywords: list[str], summary_ko: str) -> str:
    """카드 키워드에서 가장 임팩트 있는 한국어 핵심 발견을 추출."""
    for kw in keywords:
        if kw in _KO_KEYWORD_PHRASES:
            return _KO_KEYWORD_PHRASES[kw]
    # 키워드 매칭 실패 시, 요약 첫 문장 사용
    if summary_ko:
        first = summary_ko.split('.')[0].split('。')[0]
        if len(first) > 30:
            first = first[:28] + '...'
        return first
    return '포렌식 리스크 분석'


def _pick_en_finding(keywords_en: list[str], summary_en: str) -> str:
    """Pick the most impactful English key finding from keywords."""
    for kw in keywords_en:
        kw_lower = kw.lower()
        if kw_lower in _EN_KEYWORD_PHRASES:
            return _EN_KEYWORD_PHRASES[kw_lower]
    # Fallback: first sentence of summary
    if summary_en:
        first = summary_en.split('.')[0]
        if len(first) > 50:
            first = first[:48] + '...'
        return first
    return 'Forensic Risk Analysis'


# ── Phase 1: 트리거 사유 기반 제목 (coming_soon 단계) ──

_TRIGGER_SUFFIX = {
    'ko': {
        'big_up':   '급등 감지: 포렌식 분석 개시',
        'up':       '상승 감지: 포렌식 분석 개시',
        'small_up': '이상 변동 감지: 포렌식 분석 개시',
        'flat':     '이상 징후 감지: 포렌식 분석 개시',
        'small_dn': '이상 변동 감지: 포렌식 분석 개시',
        'down':     '하락 감지: 포렌식 분석 개시',
        'big_dn':   '급락 감지: 포렌식 분석 개시',
    },
    'en': {
        'big_up':   'Surge Detected: Forensic Analysis Initiated',
        'up':       'Rally Detected: Forensic Analysis Initiated',
        'small_up': 'Anomaly Detected: Forensic Analysis Initiated',
        'flat':     'Anomaly Detected: Forensic Analysis Initiated',
        'small_dn': 'Anomaly Detected: Forensic Analysis Initiated',
        'down':     'Drop Detected: Forensic Analysis Initiated',
        'big_dn':   'Plunge Detected: Forensic Analysis Initiated',
    },
    'ja': {
        'big_up':   '急騰検出：フォレンジック分析開始',
        'up':       '上昇検出：フォレンジック分析開始',
        'small_up': '異常検出：フォレンジック分析開始',
        'flat':     '異常検出：フォレンジック分析開始',
        'small_dn': '異常検出：フォレンジック分析開始',
        'down':     '下落検出：フォレンジック分析開始',
        'big_dn':   '暴落検出：フォレンジック分析開始',
    },
    'zh': {
        'big_up':   '暴涨检测：取证分析启动',
        'up':       '上涨检测：取证分析启动',
        'small_up': '异常检测：取证分析启动',
        'flat':     '异常检测：取证分析启动',
        'small_dn': '异常检测：取证分析启动',
        'down':     '下跌检测：取证分析启动',
        'big_dn':   '暴跌检测：取证分析启动',
    },
    'fr': {
        'big_up':   'Hausse détectée : Analyse forensique initiée',
        'up':       'Hausse détectée : Analyse forensique initiée',
        'small_up': 'Anomalie détectée : Analyse forensique initiée',
        'flat':     'Anomalie détectée : Analyse forensique initiée',
        'small_dn': 'Anomalie détectée : Analyse forensique initiée',
        'down':     'Baisse détectée : Analyse forensique initiée',
        'big_dn':   'Chute détectée : Analyse forensique initiée',
    },
    'es': {
        'big_up':   'Alza detectada: Análisis forense iniciado',
        'up':       'Alza detectada: Análisis forense iniciado',
        'small_up': 'Anomalía detectada: Análisis forense iniciado',
        'flat':     'Anomalía detectada: Análisis forense iniciado',
        'small_dn': 'Anomalía detectada: Análisis forense iniciado',
        'down':     'Caída detectada: Análisis forense iniciado',
        'big_dn':   'Desplome detectado: Análisis forense iniciado',
    },
    'de': {
        'big_up':   'Anstieg erkannt: Forensische Analyse gestartet',
        'up':       'Anstieg erkannt: Forensische Analyse gestartet',
        'small_up': 'Anomalie erkannt: Forensische Analyse gestartet',
        'flat':     'Anomalie erkannt: Forensische Analyse gestartet',
        'small_dn': 'Anomalie erkannt: Forensische Analyse gestartet',
        'down':     'Rückgang erkannt: Forensische Analyse gestartet',
        'big_dn':   'Absturz erkannt: Forensische Analyse gestartet',
    },
}


def generate_trigger_titles(
    trigger_data: dict,
    symbol: str,
) -> dict:
    """
    Phase 1: 트리거 데이터로부터 coming_soon 단계 제목을 7개 언어로 생성한다.

    trigger_data should contain:
        - price_change_24h: float
        - relative_deviation: float (optional)
        - risk_level: str (optional)

    Returns:
        {
            'title_en': 'RAVE 87.8% Surge Detected: Forensic Analysis Initiated',
            'title_ko': 'RAVE 87.8% 급등 감지: 포렌식 분석 개시',
            'title_ja': ..., 'title_zh': ..., 'title_fr': ..., 'title_es': ..., 'title_de': ...,
        }
    """
    symbol = _clean_symbol(symbol)
    change = float(trigger_data.get('price_change_24h', 0) or 0)
    pct = f"{abs(change):.1f}"
    dk = _direction_key(change)

    titles = {}
    for lang, suffix_map in _TRIGGER_SUFFIX.items():
        suffix = suffix_map[dk]
        if dk == 'flat':
            # QA: flat은 가격 데이터 누락일 수 있음 — "이상 징후" 계열 사용
            titles[f'title_{lang}'] = f"{symbol} {suffix_map['flat']}"
        else:
            titles[f'title_{lang}'] = f"{symbol} {pct}% {suffix}"

    return titles


# ── Phase 2: 제목 생성 메인 함수 (published 단계) ──

def _clean_symbol(raw_symbol: str) -> str:
    """Strip Korean/Chinese slug fragments from symbol. E.g. 'LDO-포렌식-분석-보고서' → 'LDO'."""
    # If it contains non-ASCII, take only the leading ASCII part
    import re as _re
    m = _re.match(r'^([A-Z0-9]+)', raw_symbol)
    if m and len(m.group(1)) >= 1:
        return m.group(1)
    return raw_symbol


def generate_titles(
    card_data: dict,
    project_name: str,
    symbol: str,
    summary_en: str = None,
    summary_ko: str = None,
) -> dict:
    """
    card_data와 프로젝트 정보로 7개 언어 제목을 생성한다.

    Returns:
        {
            'title_en': 'ENJ Surges 45%: Short Squeeze Detected',
            'title_ko': 'ENJ 45% 급등: 숏스퀴즈 감지',
            'title_ja': 'ENJ 45%急騰：ショートスクイーズ検出',
            'title_zh': 'ENJ 暴涨45%：空头挤压检测',
            'title_fr': 'ENJ en hausse de 45% : Short squeeze détecté',
            'title_es': 'ENJ sube 45%: Short squeeze detectado',
            'title_de': 'ENJ steigt 45%: Short Squeeze erkannt',
        }
    """
    symbol = _clean_symbol(symbol)
    change = card_data.get('price_change_24h', 0) or 0
    change = float(change)
    pct = f"{abs(change):.1f}"

    keywords_ko = card_data.get('keywords_ko') or card_data.get('keywords') or []
    keywords_en = card_data.get('keywords_en') or []

    s_en = summary_en or card_data.get('summary') or card_data.get('summary_en') or ''
    s_ko = summary_ko or card_data.get('summary_ko') or ''

    dk = _direction_key(change)

    # Generate ko/en findings
    ko_finding = _pick_ko_finding(keywords_ko, s_ko)
    en_finding = _pick_en_finding(keywords_en, s_en)

    # ── QA: price_change가 0이면 방향 없이 "심볼: 키워드 발견" 형식 ──
    # 포렌식 보고서가 가격 변동 0%로 "횡보"라고 나오는 건 데이터 누락이므로
    # 방향 표시를 생략하고 키워드 기반 제목만 생성한다.
    if dk == 'flat':
        _FLAT_PREFIX = {
            'ko': f'{symbol} 포렌식 분석',
            'en': f'{symbol} Forensic Analysis',
            'ja': f'{symbol} フォレンジック分析',
            'zh': f'{symbol} 取证分析',
            'fr': f'{symbol} Analyse forensique',
            'es': f'{symbol} Análisis forense',
            'de': f'{symbol} Forensische Analyse',
        }
        titles = {}
        for lang in _DIRECTION_BY_LANG:
            finding = ko_finding if lang == 'ko' else en_finding
            sep = ' : ' if lang == 'fr' else ': '
            titles[f'title_{lang}'] = f"{_FLAT_PREFIX[lang]}{sep}{finding}"
        return titles

    # Build all 7 titles (normal — price change available)
    titles = {}
    for lang, dir_map in _DIRECTION_BY_LANG.items():
        head = dir_map[dk].format(symbol=symbol, pct=pct)
        # ko uses Korean finding, all others use English finding
        finding = ko_finding if lang == 'ko' else en_finding
        sep = ' : ' if lang == 'fr' else ': '
        titles[f'title_{lang}'] = f"{head}{sep}{finding}"

    return titles


# ── 백필: 기존 DB의 title이 NULL인 보고서에 제목 자동 생성 ──

def backfill_titles():
    """Supabase에서 title이 NULL인 포렌식 보고서를 찾아 제목을 생성하고 업데이트한다."""
    _env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env.local')
    if os.path.exists(_env):
        for line in open(_env).read().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not url or not key:
        print("[ERROR] Supabase credentials not found")
        return

    from supabase import create_client
    sb = create_client(url, key)

    # Fetch forensic reports with card_data but no title
    res = sb.table('project_reports').select(
        'id, card_data, card_summary_en, card_summary_ko, card_keywords, title_en, title_ko, '
        'tracked_projects!inner(name, symbol)'
    ).eq('report_type', 'forensic') \
     .is_('title_en', 'null') \
     .not_.is_('card_data', 'null') \
     .execute()

    if not res.data:
        print("제목이 없는 포렌식 보고서가 없습니다.")
        return

    print(f"{len(res.data)}개 보고서에 제목 생성 중...\n")

    for row in res.data:
        tp = row['tracked_projects']
        if isinstance(tp, list):
            tp = tp[0]
        name = tp.get('name', '?')
        symbol = tp.get('symbol', '?')
        cd = row['card_data'] or {}

        titles = generate_titles(
            card_data=cd,
            project_name=name,
            symbol=symbol,
            summary_en=row.get('card_summary_en'),
            summary_ko=row.get('card_summary_ko'),
        )

        print(f"  {name} ({symbol}):")
        for lang in ['ko', 'en', 'ja', 'zh', 'fr', 'es', 'de']:
            print(f"    {lang.upper()}: {titles[f'title_{lang}']}")

        sb.table('project_reports').update(titles).eq('id', row['id']).execute()

        print(f"    ✓ 7개 언어 업데이트 완료\n")

    print("Done!")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill', action='store_true', help='기존 보고서 제목 백필')
    args = parser.parse_args()

    if args.backfill:
        backfill_titles()
    else:
        # Demo: Phase 1 (trigger-based, coming_soon)
        print("=== Phase 1: Trigger-based title (coming_soon) ===")
        trigger_demo = generate_trigger_titles(
            trigger_data={
                'price_change_24h': 87.8,
                'relative_deviation': 83.25,
                'risk_level': 'high',
            },
            symbol='RAVE',
        )
        for lang in ['ko', 'en', 'ja', 'zh', 'fr', 'es', 'de']:
            print(f"  {lang.upper()}: {trigger_demo[f'title_{lang}']}")

        # Demo: Phase 2 (report-based, published)
        print("\n=== Phase 2: Report-based title (published) ===")
        report_demo = generate_titles(
            card_data={
                'price_change_24h': 45.2,
                'keywords_ko': ['고래활동', '내부자거래', '조작의심'],
                'keywords_en': ['whale activity', 'insider trading', 'manipulation suspected'],
                'summary': 'Market manipulation detected with 80-98% supply control.',
            },
            project_name='RaveDAO',
            symbol='RAVE',
        )
        for lang in ['ko', 'en', 'ja', 'zh', 'fr', 'es', 'de']:
            print(f"  {lang.upper()}: {report_demo[f'title_{lang}']}")
