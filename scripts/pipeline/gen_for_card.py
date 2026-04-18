"""
BCE Lab — FOR Card Generator (OPS-008)

FOR 보고서 마크다운에서 카드형 메타데이터를 추출하고 썸네일 그래픽을 생성.
QA 리뷰를 위한 HTML 프리뷰도 함께 생성하여, 키워드와 썸네일을 사람이
확인(approve)한 후에만 웹사이트에 반영되도록 파이프라인을 구성한다.

Pipeline stage: gen_pdf_for → gen_for_card → QA review → publish

Input:
  - {slug}_for_v{ver}_ko.md (한국어 원본)
  - {slug}_for_v{ver}_en.md (영어 번역본)
  - trigger_data from Supabase (risk level, deviation, etc.)

Output:
  - card_data.json (keywords, summary, risk_score, indicators)
  - thumbnail_{slug}.svg (카드 썸네일 그래픽)
  - qa_preview_{slug}.html (QA 리뷰용 브라우저 프리뷰)
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')


# ═══════════════════════════════════════════
# 1. KEYWORD EXTRACTION
# ═══════════════════════════════════════════

# Forensic-domain keyword taxonomy (ko → display)
KEYWORD_TAXONOMY = {
    # Manipulation patterns
    '시세 조종': '시세조종',
    '펌프앤덤프': '펌프앤덤프',
    'pump.?and.?dump': 'Pump&Dump',
    '워시 트레이딩': '워시트레이딩',
    'wash.?trad': 'Wash Trading',
    '스푸핑': '스푸핑',
    'spoofing': 'Spoofing',
    '숏 스퀴즈': '숏스퀴즈',
    'short.?squeeze': 'Short Squeeze',
    '롱 스퀴즈': '롱스퀴즈',
    '유동성 덫': '유동성덫',

    # Market signals
    '급등': '급등',
    '급락': '급락',
    '과열': '과열',
    '폭락': '폭락',
    'blow.?off.?top': 'Blow-off Top',
    '고래': '고래활동',
    'whale': '고래활동',
    '내부자': '내부자거래',
    'insider': '내부자거래',

    # Technical
    '청산': '대규모청산',
    'liquidat': '대규모청산',
    '펀딩비': '펀딩비이상',
    'funding.?rate': '펀딩비이상',
    '레버리지': '고레버리지',
    '디커플링': '디커플링',

    # Risk
    '조작': '조작의심',
    'manipulat': '조작의심',
    '러그풀': '러그풀위험',
    'rug.?pull': '러그풀위험',
    '폰지': '폰지구조',
    '분산.*단계': '분산단계',
    'distribution': '분산단계',
}

# ── Multilingual keyword dictionaries ──────────────────────────
# Each maps Korean display keyword → localized display keyword

KEYWORD_JA = {
    '시세조종': '相場操縦', '펌프앤덤프': 'パンプ＆ダンプ', 'Pump&Dump': 'パンプ＆ダンプ',
    '워시트레이딩': 'ウォッシュトレーディング', 'Wash Trading': 'ウォッシュトレーディング',
    '스푸핑': 'スプーフィング', 'Spoofing': 'スプーフィング',
    '숏스퀴즈': 'ショートスクイーズ', 'Short Squeeze': 'ショートスクイーズ',
    '롱스퀴즈': 'ロングスクイーズ', '유동성덫': '流動性トラップ',
    '급등': '急騰', '급락': '急落', '과열': '過熱', '폭락': '暴落',
    'Blow-off Top': 'ブローオフトップ',
    '고래활동': 'クジラ活動', '내부자거래': 'インサイダー取引',
    '대규모청산': '大規模清算', '펀딩비이상': 'ファンディングレート異常',
    '고레버리지': '高レバレッジ', '디커플링': 'デカップリング',
    '조작의심': '操作疑惑', '러그풀위험': 'ラグプルリスク',
    '폰지구조': 'ポンジ構造', '분산단계': '分散段階',
}

KEYWORD_ZH = {
    '시세조종': '市场操纵', '펌프앤덤프': '拉高出货', 'Pump&Dump': '拉高出货',
    '워시트레이딩': '洗售交易', 'Wash Trading': '洗售交易',
    '스푸핑': '欺骗挂单', 'Spoofing': '欺骗挂单',
    '숏스퀴즈': '空头挤压', 'Short Squeeze': '空头挤压',
    '롱스퀴즈': '多头挤压', '유동성덫': '流动性陷阱',
    '급등': '暴涨', '급락': '暴跌', '과열': '过热', '폭락': '崩盘',
    'Blow-off Top': '吹顶', '고래활동': '巨鲸活动', '내부자거래': '内幕交易',
    '대규모청산': '大规模清算', '펀딩비이상': '资金费率异常',
    '고레버리지': '高杠杆', '디커플링': '脱钩',
    '조작의심': '操纵嫌疑', '러그풀위험': '跑路风险',
    '폰지구조': '庞氏结构', '분산단계': '分发阶段',
}

KEYWORD_FR = {
    '시세조종': 'Manipulation de marché', '펌프앤덤프': 'Pump & Dump', 'Pump&Dump': 'Pump & Dump',
    '워시트레이딩': 'Wash Trading', 'Wash Trading': 'Wash Trading',
    '스푸핑': 'Spoofing', 'Spoofing': 'Spoofing',
    '숏스퀴즈': 'Short Squeeze', 'Short Squeeze': 'Short Squeeze',
    '롱스퀴즈': 'Long Squeeze', '유동성덫': 'Piège de liquidité',
    '급등': 'Hausse soudaine', '급락': 'Chute brutale', '과열': 'Surchauffe', '폭락': 'Effondrement',
    'Blow-off Top': 'Blow-off Top', '고래활동': 'Activité de baleine', '내부자거래': 'Délit d\'initié',
    '대규모청산': 'Liquidation massive', '펀딩비이상': 'Anomalie du taux de financement',
    '고레버리지': 'Levier élevé', '디커플링': 'Découplage',
    '조작의심': 'Manipulation suspectée', '러그풀위험': 'Risque de rug pull',
    '폰지구조': 'Structure Ponzi', '분산단계': 'Phase de distribution',
}

KEYWORD_ES = {
    '시세조종': 'Manipulación de mercado', '펌프앤덤프': 'Pump & Dump', 'Pump&Dump': 'Pump & Dump',
    '워시트레이딩': 'Wash Trading', 'Wash Trading': 'Wash Trading',
    '스푸핑': 'Spoofing', 'Spoofing': 'Spoofing',
    '숏스퀴즈': 'Short Squeeze', 'Short Squeeze': 'Short Squeeze',
    '롱스퀴즈': 'Long Squeeze', '유동성덫': 'Trampa de liquidez',
    '급등': 'Alza repentina', '급락': 'Caída brusca', '과열': 'Sobrecalentamiento', '폭락': 'Desplome',
    'Blow-off Top': 'Blow-off Top', '고래활동': 'Actividad de ballena', '내부자거래': 'Tráfico de información',
    '대규모청산': 'Liquidación masiva', '펀딩비이상': 'Anomalía de tasa de financiación',
    '고레버리지': 'Alto apalancamiento', '디커플링': 'Desacoplamiento',
    '조작의심': 'Manipulación sospechada', '러그풀위험': 'Riesgo de rug pull',
    '폰지구조': 'Estructura Ponzi', '분산단계': 'Fase de distribución',
}

KEYWORD_DE = {
    '시세조종': 'Marktmanipulation', '펌프앤덤프': 'Pump & Dump', 'Pump&Dump': 'Pump & Dump',
    '워시트레이딩': 'Wash Trading', 'Wash Trading': 'Wash Trading',
    '스푸핑': 'Spoofing', 'Spoofing': 'Spoofing',
    '숏스퀴즈': 'Short Squeeze', 'Short Squeeze': 'Short Squeeze',
    '롱스퀴즈': 'Long Squeeze', '유동성덫': 'Liquiditätsfalle',
    '급등': 'Kursanstieg', '급락': 'Kurseinbruch', '과열': 'Überhitzung', '폭락': 'Absturz',
    'Blow-off Top': 'Blow-off Top', '고래활동': 'Wal-Aktivität', '내부자거래': 'Insiderhandel',
    '대규모청산': 'Massenliquidation', '펀딩비이상': 'Finanzierungsratenanomalie',
    '고레버리지': 'Hoher Hebel', '디커플링': 'Entkopplung',
    '조작의심': 'Manipulationsverdacht', '러그풀위험': 'Rug-Pull-Risiko',
    '폰지구조': 'Ponzi-Struktur', '분산단계': 'Verteilungsphase',
}

# Consolidated lookup by language code
KEYWORD_I18N = {
    'en': None,  # Uses KEYWORD_EN below
    'ja': KEYWORD_JA, 'zh': KEYWORD_ZH,
    'fr': KEYWORD_FR, 'es': KEYWORD_ES, 'de': KEYWORD_DE,
}

# English display versions for card_summary_en
KEYWORD_EN = {
    '시세조종': 'Market Manipulation',
    '펌프앤덤프': 'Pump & Dump',
    'Pump&Dump': 'Pump & Dump',
    '워시트레이딩': 'Wash Trading',
    'Wash Trading': 'Wash Trading',
    '스푸핑': 'Spoofing',
    'Spoofing': 'Spoofing',
    '숏스퀴즈': 'Short Squeeze',
    'Short Squeeze': 'Short Squeeze',
    '롱스퀴즈': 'Long Squeeze',
    '유동성덫': 'Liquidity Trap',
    '급등': 'Surge',
    '급락': 'Crash',
    '과열': 'Overheated',
    '폭락': 'Collapse',
    'Blow-off Top': 'Blow-off Top',
    '고래활동': 'Whale Activity',
    '내부자거래': 'Insider Trading',
    '대규모청산': 'Mass Liquidation',
    '펀딩비이상': 'Funding Rate Anomaly',
    '고레버리지': 'High Leverage',
    '디커플링': 'Decoupling',
    '조작의심': 'Manipulation Suspected',
    '러그풀위험': 'Rug Pull Risk',
    '폰지구조': 'Ponzi Structure',
    '분산단계': 'Distribution Phase',
}


def extract_keywords(ko_md: str, en_md: str = None, max_keywords: int = 6) -> list[str]:
    """
    FOR 마크다운에서 도메인 특화 키워드를 추출.
    빈도수 + 섹션 가중치(Executive Summary에서 발견된 키워드 2배 가중).
    """
    scores: dict[str, float] = {}
    text = ko_md + '\n' + (en_md or '')

    # Split into sections for weighting
    sections = re.split(r'^##\s+', text, flags=re.MULTILINE)
    exec_summary = sections[1] if len(sections) > 1 else ''
    rest = '\n'.join(sections[2:]) if len(sections) > 2 else text

    for pattern, keyword in KEYWORD_TAXONOMY.items():
        # Count in executive summary (weight 3x)
        exec_count = len(re.findall(pattern, exec_summary, re.IGNORECASE))
        rest_count = len(re.findall(pattern, rest, re.IGNORECASE))
        total = exec_count * 3 + rest_count

        if total > 0:
            scores[keyword] = scores.get(keyword, 0) + total

    # Sort by score, deduplicate
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    seen = set()
    keywords = []
    for kw, _ in ranked:
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)
            if len(keywords) >= max_keywords:
                break

    return keywords


# ═══════════════════════════════════════════
# 2. CARD SUMMARY EXTRACTION
# ═══════════════════════════════════════════

def extract_summary(md_text: str, lang: str = 'ko', max_chars: int = 200) -> str:
    """Extract 2-sentence summary from Executive Summary section."""
    sections = re.split(r'^##\s+', md_text, flags=re.MULTILINE)
    exec_text = ''
    for s in sections[1:]:
        if 'executive' in s[:50].lower() or 'summary' in s[:50].lower():
            exec_text = s
            break
    if not exec_text and len(sections) > 1:
        exec_text = sections[1]

    # Remove header line
    lines = exec_text.strip().split('\n')
    prose = '\n'.join(lines[1:]).strip()

    # Remove markdown formatting
    prose = re.sub(r'\*\*(.*?)\*\*', r'\1', prose)
    prose = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', prose)
    prose = re.sub(r'[\d]+\s*$', '', prose, flags=re.MULTILINE)

    # Get first 2 sentences
    sentences = re.split(r'(?<=[.。])\s+', prose)
    summary = ' '.join(sentences[:2]).strip()

    if len(summary) > max_chars:
        summary = summary[:max_chars - 3] + '...'

    return summary


# ═══════════════════════════════════════════
# 3. RISK SCORE COMPUTATION
# ═══════════════════════════════════════════

def compute_risk_score(trigger_data: dict, keywords: list[str]) -> int:
    """
    0-100 종합 리스크 점수.
    trigger_data의 변동폭 + 키워드 심각도 기반.
    """
    score = 0

    # Deviation contribution (max 50 points)
    deviation = trigger_data.get('relative_deviation', 0)
    if deviation >= 50:
        score += 50
    elif deviation >= 20:
        score += 35
    elif deviation >= 10:
        score += 20

    # Keyword severity contribution (max 50 points)
    severe_keywords = {'조작의심', '러그풀위험', '폰지구조', '시세조종', '펌프앤덤프', 'Pump&Dump',
                       '내부자거래', '워시트레이딩', 'Wash Trading'}
    moderate_keywords = {'숏스퀴즈', 'Short Squeeze', '대규모청산', '유동성덫', '분산단계',
                         '고래활동', '고레버리지'}

    severe_count = sum(1 for k in keywords if k in severe_keywords)
    moderate_count = sum(1 for k in keywords if k in moderate_keywords)

    score += min(severe_count * 12, 36)
    score += min(moderate_count * 5, 14)

    return min(score, 100)


# ═══════════════════════════════════════════
# 4. SVG THUMBNAIL GENERATOR
# ═══════════════════════════════════════════

def generate_thumbnail_svg(
    project_name: str,
    symbol: str,
    risk_score: int,
    keywords: list[str],
    price_change: float = None,
    risk_level: str = 'high',
    width: int = 600,
    height: int = 340,
) -> str:
    """
    FOR 보고서 카드 썸네일을 SVG로 생성.
    다크 배경 + 레드 액센트 + 리스크 게이지 + 키워드 pill 배지.
    """
    # Color palette
    bg = '#0D0D0D'
    bg_gradient = '#1A0A0A'
    red_primary = '#DC2626'
    red_glow = '#EF4444'
    text_white = '#F5F5F5'
    text_gray = '#9CA3AF'
    text_muted = '#6B7280'

    # Risk level colors
    risk_colors = {
        'critical': ('#DC2626', '#FCA5A5'),
        'high': ('#EF4444', '#FCA5A5'),
        'elevated': ('#F97316', '#FDBA74'),
        'moderate': ('#EAB308', '#FDE047'),
        'low': ('#22C55E', '#86EFAC'),
    }
    risk_color, risk_light = risk_colors.get(risk_level, risk_colors['high'])

    # Risk gauge angle (0-100 → 0-180 degrees)
    gauge_angle = risk_score * 1.8

    # Price change display
    if price_change is not None:
        change_str = f'{price_change:+.1f}%'
        change_color = red_primary if price_change > 0 else '#3B82F6'
        arrow = '▲' if price_change > 0 else '▼'
    else:
        change_str = ''
        change_color = text_gray
        arrow = ''

    # Keyword pills (max 4 for thumbnail)
    display_kw = keywords[:4]

    # Build keyword pills SVG
    kw_pills = ''
    kw_x = 24
    for i, kw in enumerate(display_kw):
        pill_w = len(kw) * 14 + 20  # Rough width estimate for CJK
        if kw_x + pill_w > width - 24:
            break
        kw_pills += f'''
        <rect x="{kw_x}" y="252" width="{pill_w}" height="26" rx="13"
              fill="{red_primary}" fill-opacity="0.15" stroke="{red_primary}" stroke-opacity="0.4" stroke-width="1"/>
        <text x="{kw_x + pill_w//2}" y="269" text-anchor="middle"
              font-family="system-ui, -apple-system, sans-serif" font-size="12" fill="{red_glow}">{kw}</text>
        '''
        kw_x += pill_w + 8

    # Risk gauge arc
    import math
    cx, cy, r = width - 80, 120, 50
    start_angle = math.radians(180)
    end_angle = math.radians(180 + gauge_angle)
    x1, y1 = cx + r * math.cos(start_angle), cy + r * math.sin(start_angle)
    x2, y2 = cx + r * math.cos(end_angle), cy + r * math.sin(end_angle)
    large_arc = 1 if gauge_angle > 180 else 0

    gauge_svg = f'''
    <!-- Gauge background -->
    <path d="M {cx-r} {cy} A {r} {r} 0 1 1 {cx+r} {cy}"
          fill="none" stroke="{text_muted}" stroke-width="8" stroke-linecap="round" opacity="0.3"/>
    <!-- Gauge fill -->
    <path d="M {x1:.1f} {y1:.1f} A {r} {r} 0 {large_arc} 1 {x2:.1f} {y2:.1f}"
          fill="none" stroke="{risk_color}" stroke-width="8" stroke-linecap="round"/>
    <!-- Score text -->
    <text x="{cx}" y="{cy + 8}" text-anchor="middle"
          font-family="system-ui, monospace" font-size="28" font-weight="bold" fill="{risk_light}">{risk_score}</text>
    <text x="{cx}" y="{cy + 24}" text-anchor="middle"
          font-family="system-ui, sans-serif" font-size="10" fill="{text_gray}">RISK SCORE</text>
    '''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{bg}"/>
      <stop offset="100%" stop-color="{bg_gradient}"/>
    </linearGradient>
    <linearGradient id="redline" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{red_primary}" stop-opacity="0"/>
      <stop offset="50%" stop-color="{red_primary}"/>
      <stop offset="100%" stop-color="{red_primary}" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" rx="16" fill="url(#bg)"/>

  <!-- Top red accent line -->
  <rect x="0" y="0" width="{width}" height="3" rx="1.5" fill="url(#redline)"/>

  <!-- Alert badge -->
  <rect x="24" y="20" width="120" height="28" rx="14" fill="{red_primary}" fill-opacity="0.2"
        stroke="{red_primary}" stroke-opacity="0.5" stroke-width="1"/>
  <text x="84" y="39" text-anchor="middle"
        font-family="system-ui, sans-serif" font-size="12" font-weight="600" fill="{red_glow}" filter="url(#glow)">⚠ FORENSIC ALERT</text>

  <!-- BCE Lab watermark -->
  <text x="{width - 24}" y="39" text-anchor="end"
        font-family="system-ui, sans-serif" font-size="11" fill="{text_muted}">BCE Lab</text>

  <!-- Project name + symbol -->
  <text x="24" y="90" font-family="system-ui, -apple-system, sans-serif" font-size="28" font-weight="bold" fill="{text_white}">{project_name}</text>
  <text x="24" y="118" font-family="system-ui, monospace" font-size="16" fill="{text_gray}">${symbol}</text>

  <!-- Price change -->
  <text x="24" y="150" font-family="system-ui, monospace" font-size="36" font-weight="bold" fill="{change_color}" filter="url(#glow)">{arrow} {change_str}</text>

  <!-- Risk level badge -->
  <rect x="24" y="170" width="{len(risk_level)*10 + 24}" height="24" rx="12"
        fill="{risk_color}" fill-opacity="0.2" stroke="{risk_color}" stroke-opacity="0.6" stroke-width="1"/>
  <text x="{24 + (len(risk_level)*10 + 24)//2}" y="186" text-anchor="middle"
        font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="{risk_light}">{risk_level.upper()}</text>

  <!-- 24h marker -->
  <text x="24" y="225" font-family="system-ui, sans-serif" font-size="12" fill="{text_muted}">24h vs Market Average</text>

  {gauge_svg}

  <!-- Keyword pills -->
  {kw_pills}

  <!-- Bottom line -->
  <rect x="24" y="{height - 40}" width="{width - 48}" height="1" fill="{text_muted}" opacity="0.2"/>
  <text x="24" y="{height - 16}" font-family="system-ui, sans-serif" font-size="10" fill="{text_muted}">Blockchain Cryptoeconomics Lab · Forensic Analysis Division</text>
  <text x="{width - 24}" y="{height - 16}" text-anchor="end"
        font-family="system-ui, sans-serif" font-size="10" fill="{text_muted}">{datetime.now(timezone.utc).strftime('%Y-%m-%d')}</text>
</svg>'''

    return svg


# ═══════════════════════════════════════════
# 5. QA PREVIEW HTML
# ═══════════════════════════════════════════

def generate_qa_preview(
    slug: str,
    card_data: dict,
    svg_content: str,
    ko_summary: str,
    en_summary: str,
) -> str:
    """QA 검토용 HTML 프리뷰 생성. 키워드와 썸네일을 사람이 확인할 수 있도록."""
    keywords = card_data.get('keywords', [])
    keywords_en = [KEYWORD_EN.get(k, k) for k in keywords]

    kw_pills_html = ' '.join(
        f'<span class="pill">{k}</span>' for k in keywords
    )
    kw_en_pills_html = ' '.join(
        f'<span class="pill-en">{k}</span>' for k in keywords_en
    )

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<title>FOR Card QA — {slug}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #111; color: #eee; padding: 40px; max-width: 800px; margin: 0 auto; }}
  h1 {{ color: #EF4444; font-size: 24px; }}
  h2 {{ color: #9CA3AF; font-size: 16px; margin-top: 32px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
  .thumbnail {{ background: #000; border-radius: 16px; padding: 16px; margin: 20px 0; text-align: center; }}
  .thumbnail svg {{ max-width: 100%; height: auto; }}
  .pill {{ display: inline-block; background: rgba(220,38,38,0.15); color: #EF4444; border: 1px solid rgba(220,38,38,0.4); border-radius: 20px; padding: 4px 14px; margin: 4px; font-size: 14px; }}
  .pill-en {{ display: inline-block; background: rgba(59,130,246,0.15); color: #60A5FA; border: 1px solid rgba(59,130,246,0.3); border-radius: 20px; padding: 4px 14px; margin: 4px; font-size: 13px; }}
  .summary {{ background: #1A1A1A; border-left: 3px solid #EF4444; padding: 16px; margin: 12px 0; border-radius: 0 8px 8px 0; line-height: 1.7; }}
  .metric {{ display: inline-block; background: #1A1A1A; border-radius: 12px; padding: 12px 20px; margin: 6px; text-align: center; }}
  .metric .value {{ font-size: 24px; font-weight: bold; }}
  .metric .label {{ font-size: 11px; color: #6B7280; margin-top: 4px; }}
  .actions {{ margin-top: 40px; padding: 20px; background: #1A1A1A; border-radius: 12px; }}
  .btn {{ display: inline-block; padding: 10px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-right: 12px; text-decoration: none; }}
  .btn-approve {{ background: #22C55E; color: #000; }}
  .btn-reject {{ background: #EF4444; color: #FFF; }}
  .btn-edit {{ background: #3B82F6; color: #FFF; }}
  .note {{ color: #6B7280; font-size: 12px; margin-top: 8px; }}
</style>
</head>
<body>
<h1>⚠ FOR Card QA Review — {slug}</h1>
<p style="color: #6B7280;">Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

<h2>📊 Thumbnail Preview</h2>
<div class="thumbnail">
{svg_content}
</div>

<h2>🏷 Keywords (KO)</h2>
<div>{kw_pills_html}</div>

<h2>🏷 Keywords (EN)</h2>
<div>{kw_en_pills_html}</div>

<h2>📝 Card Summary (KO)</h2>
<div class="summary">{ko_summary}</div>

<h2>📝 Card Summary (EN)</h2>
<div class="summary">{en_summary}</div>

<h2>📈 Metrics</h2>
<div>
  <div class="metric">
    <div class="value" style="color: #EF4444;">{card_data.get('risk_score', 0)}</div>
    <div class="label">RISK SCORE</div>
  </div>
  <div class="metric">
    <div class="value" style="color: {'#EF4444' if card_data.get('price_change_24h', 0) > 0 else '#3B82F6'};">{card_data.get('price_change_24h', 0):+.1f}%</div>
    <div class="label">24H CHANGE</div>
  </div>
  <div class="metric">
    <div class="value">{card_data.get('relative_deviation', 0):.1f}%</div>
    <div class="label">VS MARKET AVG</div>
  </div>
  <div class="metric">
    <div class="value">{card_data.get('risk_level', 'N/A').upper()}</div>
    <div class="label">RISK LEVEL</div>
  </div>
</div>

<div class="actions">
  <h2 style="margin-top: 0;">✅ QA Decision</h2>
  <p>이 카드의 키워드, 썸네일, 요약이 적절한지 검토해주세요.</p>
  <p class="note">승인하면 웹사이트 홈에 카드가 표시되고 이메일 게이트를 통해 PDF 다운로드가 가능해집니다.</p>
</div>

<script>
// card_data embedded for programmatic access
window.__CARD_DATA__ = {json.dumps(card_data, ensure_ascii=False)};
</script>
</body>
</html>'''


# ═══════════════════════════════════════════
# 6. MAIN: Generate card package
# ═══════════════════════════════════════════

def generate_for_card(
    ko_md_path: str,
    en_md_path: str = None,
    trigger_data: dict = None,
    project_name: str = None,
    symbol: str = None,
    slug: str = None,
    output_dir: str = None,
) -> dict:
    """
    FOR 카드 메타데이터 + 썸네일 + QA 프리뷰 생성.

    Returns:
        dict with keys: keywords, summary_ko, summary_en, risk_score,
                        thumbnail_path, qa_preview_path, card_data
    """
    output_dir = output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Read markdowns
    ko_md = Path(ko_md_path).read_text(encoding='utf-8')
    en_md = Path(en_md_path).read_text(encoding='utf-8') if en_md_path and os.path.exists(en_md_path) else ''

    trigger_data = trigger_data or {}
    slug = slug or 'unknown'
    symbol = symbol or slug.upper()
    project_name = project_name or slug.replace('-', ' ').title()

    # 1. Extract keywords
    keywords = extract_keywords(ko_md, en_md)
    print(f"  Keywords: {keywords}")

    # 2. Extract summaries
    summary_ko = extract_summary(ko_md, lang='ko')
    summary_en = extract_summary(en_md, lang='en') if en_md else ''
    print(f"  Summary KO: {summary_ko[:80]}...")

    # 3. Compute risk score
    risk_score = compute_risk_score(trigger_data, keywords)
    risk_level = trigger_data.get('risk_level', 'high')
    if risk_score >= 80:
        risk_level = 'critical'
    elif risk_score >= 60:
        risk_level = 'high'
    elif risk_score >= 40:
        risk_level = 'elevated'
    print(f"  Risk: {risk_score}/100 ({risk_level})")

    # 3.5 Extract summaries from all available translated files
    summary_by_lang = {'ko': summary_ko, 'en': summary_en}
    keywords_by_lang = {
        'ko': keywords,
        'en': [KEYWORD_EN.get(k, k) for k in keywords],
    }
    trans_langs = ['ja', 'zh', 'fr', 'es', 'de']
    if output_dir:
        for tl in trans_langs:
            tl_path = Path(output_dir) / f"{slug}_for_v{trigger_data.get('version', 1)}_{tl}.md"
            if not tl_path.exists():
                # Also try without version
                candidates = list(Path(output_dir).glob(f"{slug}*_for_*_{tl}.md"))
                tl_path = candidates[0] if candidates else None
            if tl_path and tl_path.exists():
                tl_md = tl_path.read_text(encoding='utf-8')
                summary_by_lang[tl] = extract_summary(tl_md, lang=tl)
                # Map keywords to localized versions
                kw_dict = KEYWORD_I18N.get(tl)
                if kw_dict:
                    keywords_by_lang[tl] = [kw_dict.get(k, k) for k in keywords]
                print(f"  Summary {tl.upper()}: {summary_by_lang[tl][:60]}...")

    # 4. Build card_data — QA gate: price_change_24h must not be 0 for forensic reports
    raw_price_change = trigger_data.get('price_change_24h', 0)
    if raw_price_change is None or float(raw_price_change) == 0:
        print(f"  ⚠ QA WARNING: price_change_24h is {raw_price_change} — "
              "this likely means trigger data was not properly passed. "
              "Attempting to resolve from forensic_triggers table...")
        # Attempt resolution from Supabase if available
        _resolved = False
        try:
            import os as _os
            _url = _os.environ.get('SUPABASE_URL') or _os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
            _key = _os.environ.get('SUPABASE_SERVICE_KEY') or _os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
            if _url and _key:
                from supabase import create_client as _sc
                _sb = _sc(_url, _key)
                _ft = None
                for _qf, _qv in [('slug', slug), ('symbol', symbol)]:
                    _ft = _sb.table('forensic_triggers').select('price_change_24h, relative_deviation') \
                        .eq(_qf, _qv).order('created_at', desc=True).limit(1).execute()
                    if _ft.data and _ft.data[0].get('price_change_24h'):
                        print(f"  ✓ QA: forensic_triggers matched via {_qf}={_qv}")
                        break
                if _ft and _ft.data and _ft.data[0].get('price_change_24h'):
                    raw_price_change = float(_ft.data[0]['price_change_24h'])
                    trigger_data['relative_deviation'] = float(_ft.data[0].get('relative_deviation', 0))
                    print(f"  ✓ QA RESOLVED: price_change_24h = {raw_price_change:+.1f}% from forensic_triggers")
                    _resolved = True
        except Exception as e:
            print(f"  ✗ QA resolution failed: {str(e)[:100]}")

        if not _resolved:
            raise ValueError(
                f"QA BLOCKED: price_change_24h is 0 for {symbol} ({slug}). "
                "Cannot generate card without valid price data. "
                "Pass trigger_data with 'price_change_24h' or ensure forensic_triggers has data."
            )

    card_data = {
        'slug': slug,
        'project_name': project_name,
        'symbol': symbol,
        'keywords': keywords,
        'keywords_en': [KEYWORD_EN.get(k, k) for k in keywords],
        'keywords_by_lang': keywords_by_lang,
        'summary_ko': summary_ko,
        'summary_en': summary_en,
        'summary_by_lang': summary_by_lang,
        'risk_score': risk_score,
        'risk_level': risk_level,
        'price_change_24h': float(raw_price_change),
        'relative_deviation': trigger_data.get('relative_deviation', 0),
        'market_avg_change_24h': trigger_data.get('market_avg_change_24h', 0),
        'direction': trigger_data.get('direction', 'up'),
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }

    # 5. Generate SVG thumbnail
    svg_content = generate_thumbnail_svg(
        project_name=project_name,
        symbol=symbol,
        risk_score=risk_score,
        keywords=keywords,
        price_change=trigger_data.get('price_change_24h'),
        risk_level=risk_level,
    )
    thumb_path = os.path.join(output_dir, f'thumbnail_{slug}.svg')
    Path(thumb_path).write_text(svg_content, encoding='utf-8')
    print(f"  Thumbnail: {thumb_path}")

    # 6. Generate QA preview HTML
    qa_html = generate_qa_preview(slug, card_data, svg_content, summary_ko, summary_en)
    qa_path = os.path.join(output_dir, f'qa_preview_{slug}.html')
    Path(qa_path).write_text(qa_html, encoding='utf-8')
    print(f"  QA Preview: {qa_path}")

    # 7. Save card_data JSON
    data_path = os.path.join(output_dir, f'card_data_{slug}.json')
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(card_data, f, ensure_ascii=False, indent=2)
    print(f"  Card Data: {data_path}")

    return {
        'card_data': card_data,
        'thumbnail_path': thumb_path,
        'qa_preview_path': qa_path,
        'card_data_path': data_path,
    }


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate FOR card metadata + thumbnail')
    parser.add_argument('ko_md', help='Path to Korean FOR markdown')
    parser.add_argument('--en-md', help='Path to English FOR markdown')
    parser.add_argument('--trigger-json', help='Path to trigger_data JSON')
    parser.add_argument('--name', help='Project name')
    parser.add_argument('--symbol', help='Token symbol')
    parser.add_argument('--slug', help='Project slug')
    parser.add_argument('--output-dir', default=OUTPUT_DIR)

    args = parser.parse_args()

    trigger = {}
    if args.trigger_json and os.path.exists(args.trigger_json):
        with open(args.trigger_json) as f:
            trigger = json.load(f)

    result = generate_for_card(
        ko_md_path=args.ko_md,
        en_md_path=args.en_md,
        trigger_data=trigger,
        project_name=args.name,
        symbol=args.symbol,
        slug=args.slug,
        output_dir=args.output_dir,
    )

    print(f"\n✓ Card generated for {result['card_data']['slug']}")
    print(f"  Open QA preview: file://{result['qa_preview_path']}")
