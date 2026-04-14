"""
gen_report_title.py — 포렌식 보고서 제목 자동 생성

card_data(요약, 가격변동, 키워드)로부터 한/영 제목을 자동 생성한다.
사용자가 읽고 클릭하고 싶은 제목을 만드는 것이 목표.

예시 출력:
  EN: "ENJ Surges 45%: Short Squeeze Drives Inorganic Rally"
  KO: "ENJ 45% 급등: 숏스퀴즈가 이끄는 비유기적 상승"

Usage:
    # 단독 실행 (기존 보고서 백필)
    python gen_report_title.py --backfill

    # 파이프라인에서 호출
    from gen_report_title import generate_titles
    titles = generate_titles(card_data, project_name, symbol)
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


# ── 제목 생성 메인 함수 ──

def generate_titles(
    card_data: dict,
    project_name: str,
    symbol: str,
    summary_en: str = None,
    summary_ko: str = None,
) -> dict:
    """
    card_data와 프로젝트 정보로 한/영 제목을 생성한다.

    Returns:
        {
            'title_en': 'ENJ Surges 45%: Short Squeeze Drives Rally',
            'title_ko': 'ENJ 45% 급등: 숏스퀴즈가 이끄는 비유기적 상승',
        }
    """
    change = card_data.get('price_change_24h', 0) or 0
    change = float(change)
    pct = f"{abs(change):.1f}"

    keywords_ko = card_data.get('keywords_ko') or card_data.get('keywords') or []
    keywords_en = card_data.get('keywords_en') or []

    s_en = summary_en or card_data.get('summary') or card_data.get('summary_en') or ''
    s_ko = summary_ko or card_data.get('summary_ko') or ''

    # 방향 부분
    dk = _direction_key(change)

    ko_head = _KO_DIRECTION[dk].format(symbol=symbol, pct=pct)
    en_head = _EN_DIRECTION[dk].format(symbol=symbol, pct=pct)

    # 핵심 발견 부분
    ko_finding = _pick_ko_finding(keywords_ko, s_ko)
    en_finding = _pick_en_finding(keywords_en, s_en)

    # 조합
    if dk == 'flat':
        # 횡보일 때는 콜론 없이 핵심 발견만
        title_ko = f"{ko_head} 중 {ko_finding}"
        title_en = f"{en_head}: {en_finding}"
    else:
        title_ko = f"{ko_head}: {ko_finding}"
        title_en = f"{en_head}: {en_finding}"

    return {
        'title_en': title_en,
        'title_ko': title_ko,
    }


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
        print(f"    EN: {titles['title_en']}")
        print(f"    KO: {titles['title_ko']}")

        sb.table('project_reports').update({
            'title_en': titles['title_en'],
            'title_ko': titles['title_ko'],
        }).eq('id', row['id']).execute()

        print(f"    ✓ 업데이트 완료\n")

    print("Done!")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill', action='store_true', help='기존 보고서 제목 백필')
    args = parser.parse_args()

    if args.backfill:
        backfill_titles()
    else:
        # Demo
        demo = generate_titles(
            card_data={
                'price_change_24h': 45.2,
                'keywords_ko': ['고래활동', '내부자거래', '조작의심'],
                'keywords_en': ['whale activity', 'insider trading', 'manipulation suspected'],
                'summary': 'Market manipulation detected with 80-98% supply control.',
            },
            project_name='RaveDAO',
            symbol='RAVE',
        )
        print(f"EN: {demo['title_en']}")
        print(f"KO: {demo['title_ko']}")
