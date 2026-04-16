"""
Stage 2-S: Economy Design Analysis — Slide-Style Infographic PDF Generator
============================================================================
Converts enriched project JSON data into a visual-first, slide-style PDF
where each page acts as an infographic slide with minimal text and rich graphics.

Contrast with gen_pdf_econ.py (text-heavy report):
    gen_pdf_econ.py  → Document-style, 15-25 pages, 6000+ words
    gen_slide_econ.py → Slide-style, 8-12 pages, infographic-dense, <500 words

SLIDE STRUCTURE (8-12 slides):
    1. Cover — Project identity, rating badge, key metrics
    2. Executive Dashboard — KPI cards, overall gauge, verdict
    3. Market Overview — Price chart, macro indicators, sentiment
    4. Token Economy — Distribution pie, supply metrics, vesting
    5. Technical Architecture — Radar chart, pillar scores, stack info
    6. Risk Assessment — Risk matrix, heatmap, severity indicators
    7. Crypto Economy Design — Lifecycle timeline, 3-component framework
    8. Investment Thesis — Final scorecard, recommendation
    9. Data Sources — Methodology note, disclaimer (compact)

Each slide uses a 2-column or full-width layout with:
    - Dark header bar with slide title
    - 60-70% visual area (charts, infographics)
    - 30-40% minimal text (key insights, bullet points)

Usage:
    from gen_slide_econ import generate_slide_econ
    pdf_path, metadata = generate_slide_econ(project_data, output_dir='/tmp')
"""

import io
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import COLORS, ORG_NAME, ORG_FULL, DOMAIN, COPYRIGHT_YEAR, REPORT_TYPES
from chart_engine import ChartEngine, Palette, Quality

# ─── Constants ────────────────────────────────────────────
W, H = A4  # 210mm x 297mm
MARGIN = 15 * mm
USABLE_W = W - 2 * MARGIN
USABLE_H = H - 2 * MARGIN

# Slide layout zones
HEADER_H = 18 * mm
FOOTER_H = 12 * mm
CONTENT_TOP = H - MARGIN - HEADER_H
CONTENT_BOTTOM = MARGIN + FOOTER_H

# Colors
C_DARK = HexColor('#0F172A')
C_INDIGO = HexColor('#4F46E5')
C_INDIGO_LIGHT = HexColor('#818CF8')
C_WHITE = HexColor('#FFFFFF')
C_SLATE_50 = HexColor('#F8FAFC')
C_SLATE_100 = HexColor('#F1F5F9')
C_SLATE_200 = HexColor('#E2E8F0')
C_SLATE_400 = HexColor('#94A3B8')
C_SLATE_600 = HexColor('#475569')
C_SLATE_700 = HexColor('#334155')
C_SLATE_800 = HexColor('#1E293B')
C_GREEN = HexColor('#059669')
C_RED = HexColor('#DC2626')
C_AMBER = HexColor('#D97706')


def _hex(c):
    return HexColor(c) if isinstance(c, str) else c


# ═══════════════════════════════════════════════════════════
#  SLIDE PRIMITIVES — Reusable layout blocks
# ═══════════════════════════════════════════════════════════

def _draw_slide_header(c, title, subtitle='', slide_num=None, total=None):
    """Dark header bar at top of each slide."""
    y_top = H - MARGIN
    # Background bar
    c.setFillColor(C_DARK)
    c.roundRect(MARGIN, y_top - HEADER_H, USABLE_W, HEADER_H, 3*mm, fill=True, stroke=False)

    # Accent stripe
    c.setFillColor(C_INDIGO)
    c.rect(MARGIN, y_top - HEADER_H, 4*mm, HEADER_H, fill=True, stroke=False)

    # Title
    c.setFillColor(C_WHITE)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(MARGIN + 8*mm, y_top - 11*mm, title)

    # Subtitle
    if subtitle:
        c.setFillColor(C_INDIGO_LIGHT)
        c.setFont('Helvetica', 8.5)
        c.drawString(MARGIN + 8*mm, y_top - 16*mm, subtitle)

    # Slide number
    if slide_num:
        c.setFillColor(C_SLATE_400)
        c.setFont('Helvetica', 7)
        num_text = f'{slide_num}/{total}' if total else str(slide_num)
        c.drawRightString(MARGIN + USABLE_W - 5*mm, y_top - 11*mm, num_text)


def _draw_slide_footer(c, project_name):
    """Minimal footer with branding."""
    y = MARGIN
    c.setStrokeColor(C_SLATE_200)
    c.setLineWidth(0.5)
    c.line(MARGIN, y + FOOTER_H, MARGIN + USABLE_W, y + FOOTER_H)

    c.setFillColor(C_SLATE_400)
    c.setFont('Helvetica', 6.5)
    c.drawString(MARGIN + 2*mm, y + 4*mm, f'{ORG_NAME}  |  {project_name}')
    c.drawRightString(MARGIN + USABLE_W - 2*mm, y + 4*mm,
                      f'{DOMAIN}  |  {datetime.now().strftime("%Y-%m-%d")}')


def _draw_metric_box(c, x, y, w, h, value, label, color=None):
    """KPI metric box with colored top border."""
    color = color or C_INDIGO
    # Background
    c.setFillColor(C_SLATE_50)
    c.setStrokeColor(C_SLATE_200)
    c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, 2*mm, fill=True, stroke=True)
    # Colored top stripe
    c.setFillColor(_hex(color))
    c.rect(x, y + h - 2.5*mm, w, 2.5*mm, fill=True, stroke=False)
    # Value
    c.setFillColor(C_SLATE_800)
    c.setFont('Helvetica-Bold', 15)
    c.drawCentredString(x + w/2, y + h/2 - 1*mm, str(value))
    # Label
    c.setFillColor(C_SLATE_600)
    c.setFont('Helvetica', 7)
    c.drawCentredString(x + w/2, y + 4*mm, label)


def _draw_badge(c, x, y, text, bg_color, text_color=None):
    """Small rounded badge."""
    text_color = text_color or C_WHITE
    tw = c.stringWidth(text, 'Helvetica-Bold', 9) + 10*mm
    c.setFillColor(_hex(bg_color))
    c.roundRect(x, y, tw, 7*mm, 2*mm, fill=True, stroke=False)
    c.setFillColor(_hex(text_color))
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(x + tw/2, y + 2*mm, text)
    return tw


def _draw_chart_on_canvas(c, chart_buf, x, y, w, h):
    """Draw a chart image from BytesIO buffer onto canvas."""
    if chart_buf and chart_buf.getbuffer().nbytes > 100:
        from reportlab.lib.utils import ImageReader
        chart_buf.seek(0)
        img = ImageReader(chart_buf)
        c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, anchor='c')


def _draw_bullet_text(c, x, y, texts, line_height=12, font_size=8.5, max_width=None):
    """Draw bullet point texts with word-wrap. Returns final y position."""
    from reportlab.lib.utils import simpleSplit
    wrap_w = max_width or (USABLE_W / 2 - 10*mm)
    for text in texts:
        c.setFillColor(C_INDIGO)
        c.setFont('Helvetica-Bold', font_size + 1)
        c.drawString(x, y, '\u2022')
        c.setFillColor(C_SLATE_700)
        c.setFont('Helvetica', font_size)
        lines = simpleSplit(text, 'Helvetica', font_size, wrap_w)
        for line in lines[:3]:  # Max 3 wrapped lines per bullet
            c.drawString(x + 4*mm, y, line)
            y -= line_height
    return y


def _rating_color(rating):
    """Get color for rating letter."""
    if rating in ('S', 'A', 'A+', 'A-'):
        return Palette.SUCCESS
    elif rating in ('B', 'B+', 'B-'):
        return Palette.INDIGO_600
    elif rating in ('C', 'C+', 'C-'):
        return Palette.WARNING
    return Palette.DANGER


# ═══════════════════════════════════════════════════════════
#  SLIDE GENERATORS
# ═══════════════════════════════════════════════════════════

def _slide_cover(c, d):
    """Slide 1: Full-bleed cover with project identity."""
    project_name = d.get('project_name', 'Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    rating = d.get('overall_rating', 'B')
    version = d.get('version', 1)

    # Full dark background
    c.setFillColor(C_DARK)
    c.rect(0, 0, W, H, fill=True, stroke=False)

    # Top indigo accent
    c.setFillColor(C_INDIGO)
    c.rect(0, H - 10*mm, W, 10*mm, fill=True, stroke=False)

    # Logo area
    c.setFillColor(HexColor('#6366F1'))
    c.roundRect(30*mm, H - 42*mm, 12*mm, 12*mm, 2*mm, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(36*mm, H - 38*mm, 'B')
    c.setFont('Helvetica-Bold', 12)
    c.drawString(46*mm, H - 36*mm, ORG_NAME)
    c.setFillColor(C_SLATE_400)
    c.setFont('Helvetica', 8)
    c.drawString(46*mm, H - 42*mm, ORG_FULL)

    # Classification badge
    c.setStrokeColor(C_INDIGO_LIGHT)
    c.setLineWidth(1)
    c.setFillColor(Color(0.31, 0.27, 0.89, alpha=0.15))
    c.roundRect(W - 55*mm, H - 40*mm, 30*mm, 8*mm, 2*mm, fill=True, stroke=True)
    c.setFillColor(C_INDIGO_LIGHT)
    c.setFont('Helvetica-Bold', 7)
    c.drawCentredString(W - 40*mm, H - 37*mm, 'RPT-ECON SLIDE')

    # Project name (large)
    c.setFillColor(C_WHITE)
    c.setFont('Helvetica-Bold', 38)
    c.drawString(30*mm, H - 90*mm, project_name)

    # Token symbol
    c.setFillColor(C_INDIGO_LIGHT)
    c.setFont('Helvetica-Bold', 22)
    c.drawString(30*mm, H - 110*mm, f'${token_symbol}')

    # Report type
    c.setFont('Helvetica', 14)
    c.setFillColor(C_SLATE_400)
    c.drawString(30*mm, H - 128*mm, 'Economy Design Analysis  |  Infographic Edition')

    # Accent line
    c.setStrokeColor(C_INDIGO)
    c.setLineWidth(3)
    c.line(30*mm, H - 140*mm, 80*mm, H - 140*mm)

    # Rating circle (large)
    cx, cy = W - 50*mm, H - 110*mm
    r = 18*mm
    rc = _rating_color(rating)
    c.setFillColor(_hex(rc))
    c.circle(cx, cy, r, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont('Helvetica-Bold', 28)
    c.drawCentredString(cx, cy - 4*mm, rating)
    c.setFont('Helvetica', 8)
    c.drawCentredString(cx, cy - 14*mm, 'RATING')

    # Key metrics row
    market_data = d.get('market_data', {})
    metrics = []
    price = market_data.get('current_price')
    if price:
        metrics.append((f'${price:,.4f}' if price < 1 else f'${price:,.2f}', 'Price'))
    mcap = market_data.get('market_cap')
    if mcap:
        if mcap >= 1e9:
            metrics.append((f'${mcap/1e9:.1f}B', 'Market Cap'))
        else:
            metrics.append((f'${mcap/1e6:.0f}M', 'Market Cap'))
    vol = market_data.get('volume_24h')
    if vol:
        metrics.append((f'${vol/1e6:.1f}M', '24h Volume'))
    pct = market_data.get('price_change_24h_pct')
    if pct is not None:
        metrics.append((f'{pct:+.1f}%', '24h Change'))

    if metrics:
        box_w = 38*mm
        start_x = 30*mm
        y = H - 200*mm
        for i, (val, label) in enumerate(metrics[:4]):
            _draw_metric_box(c, start_x + i*(box_w + 4*mm), y, box_w, 22*mm, val, label)

    # Version & date
    c.setFillColor(C_SLATE_400)
    c.setFont('Helvetica', 9)
    c.drawString(30*mm, H - 240*mm, f'Version {version}  |  {datetime.now().strftime("%B %d, %Y")}')

    # Footer bar
    c.setFillColor(C_SLATE_700)
    c.rect(0, 0, W, 20*mm, fill=True, stroke=False)
    c.setFillColor(C_SLATE_400)
    c.setFont('Helvetica', 7)
    c.drawCentredString(W/2, 8*mm, f'\u00a9 {COPYRIGHT_YEAR} {ORG_NAME}  |  {DOMAIN}  |  Infographic Edition')


def _slide_executive_dashboard(c, d, engine, slide_num, total):
    """Slide 2: Executive dashboard with KPI cards + gauge."""
    _draw_slide_header(c, 'Executive Dashboard', 'Key Performance Indicators at a Glance', slide_num, total)
    _draw_slide_footer(c, d.get('project_name', ''))

    project_name = d.get('project_name', 'Project')
    rating = d.get('overall_rating', 'B')
    market_data = d.get('market_data', {})

    # KPI row (top section)
    kpi_metrics = []
    price = market_data.get('current_price')
    if price:
        kpi_metrics.append({
            'label': 'Price',
            'value': f'${price:,.4f}' if price < 1 else f'${price:,.2f}',
            'delta': f'{market_data.get("price_change_24h_pct", 0):+.1f}%',
            'color': Palette.INDIGO_600,
        })
    mcap = market_data.get('market_cap')
    if mcap:
        kpi_metrics.append({
            'label': 'Market Cap',
            'value': f'${mcap/1e9:.2f}B' if mcap >= 1e9 else f'${mcap/1e6:.0f}M',
            'color': Palette.INDIGO_600,
        })
    vol = market_data.get('volume_24h')
    if vol:
        kpi_metrics.append({
            'label': '24h Volume',
            'value': f'${vol/1e6:.1f}M',
            'color': Palette.INFO,
        })
    kpi_metrics.append({
        'label': 'Rating',
        'value': rating,
        'color': _rating_color(rating),
    })

    if kpi_metrics:
        kpi_buf = engine.render_kpi_card(metrics=kpi_metrics, width=800, height=180)
        _draw_chart_on_canvas(c, kpi_buf, MARGIN, CONTENT_TOP - 42*mm, USABLE_W, 35*mm)

    # Two columns: Gauge (left) + Summary (right)
    mid_y = CONTENT_TOP - 50*mm
    col_w = USABLE_W / 2 - 3*mm

    # Left: Rating gauge
    gauge_buf = engine.render_gauge_chart(
        value=_rating_to_score(rating), max_value=100,
        title=f'{project_name} Overall Score',
        suffix='', width=450, height=350,
    )
    _draw_chart_on_canvas(c, gauge_buf, MARGIN, mid_y - 80*mm, col_w, 75*mm)

    # Right: Key findings
    rx = MARGIN + col_w + 6*mm
    ry = mid_y - 5*mm
    c.setFillColor(C_SLATE_800)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(rx, ry, 'Key Findings')
    ry -= 5*mm
    c.setStrokeColor(C_INDIGO)
    c.setLineWidth(2)
    c.line(rx, ry, rx + 20*mm, ry)
    ry -= 8*mm

    summary = d.get('executive_summary', '')
    if summary:
        # Split into bullet points (max 4)
        sentences = [s.strip() + '.' for s in summary.split('.') if s.strip()][:4]
        ry = _draw_bullet_text(c, rx, ry, sentences, line_height=14, font_size=8)

    # Investment thesis snippet
    thesis = d.get('investment_thesis', '')
    if thesis:
        ry -= 8*mm
        c.setFillColor(C_SLATE_800)
        c.setFont('Helvetica-Bold', 10)
        c.drawString(rx, ry, 'Investment Thesis')
        ry -= 5*mm
        c.setStrokeColor(C_INDIGO)
        c.line(rx, ry, rx + 20*mm, ry)
        ry -= 8*mm
        sentences = [s.strip() + '.' for s in thesis.split('.') if s.strip()][:3]
        _draw_bullet_text(c, rx, ry, sentences, line_height=14, font_size=8)


def _slide_market_overview(c, d, engine, slide_num, total):
    """Slide 3: Market & macro context."""
    _draw_slide_header(c, 'Market Overview', 'Macro Environment & Sentiment Analysis', slide_num, total)
    _draw_slide_footer(c, d.get('project_name', ''))

    market_data = d.get('market_data', {})
    macro = d.get('macro_global', {})
    fg = d.get('fear_greed', {})

    # Top section: macro KPI cards
    macro_metrics = []
    total_mcap = macro.get('total_market_cap')
    if total_mcap:
        macro_metrics.append({'label': 'Total Crypto MCap', 'value': f'${total_mcap/1e12:.1f}T', 'color': Palette.INDIGO_600})
    btc_dom = macro.get('btc_dominance')
    if btc_dom:
        macro_metrics.append({'label': 'BTC Dominance', 'value': f'{btc_dom:.1f}%', 'color': Palette.WARNING})
    fgi = fg.get('fear_greed_index')
    if fgi is not None:
        macro_metrics.append({'label': 'Fear & Greed', 'value': str(fgi), 'delta': fg.get('classification', ''), 'color': Palette.INFO})
    ath = market_data.get('ath')
    price = market_data.get('current_price', 0)
    if ath and price:
        ath_pct = (price / ath) * 100
        macro_metrics.append({'label': 'ATH Distance', 'value': f'{ath_pct:.1f}%', 'color': Palette.DANGER if ath_pct < 30 else Palette.SUCCESS})

    if macro_metrics:
        kpi_buf = engine.render_kpi_card(metrics=macro_metrics, width=800, height=180)
        _draw_chart_on_canvas(c, kpi_buf, MARGIN, CONTENT_TOP - 42*mm, USABLE_W, 35*mm)

    # Fear & Greed gauge (left)
    mid_y = CONTENT_TOP - 52*mm
    col_w = USABLE_W / 2 - 3*mm

    if fgi is not None:
        fg_buf = engine.render_gauge_chart(
            value=fgi, max_value=100,
            title='Fear & Greed Index',
            suffix='', width=450, height=320,
            thresholds={'danger': 25, 'warning': 55},
        )
        _draw_chart_on_canvas(c, fg_buf, MARGIN, mid_y - 70*mm, col_w, 65*mm)

    # BTC dominance donut (right)
    if btc_dom:
        dom_buf = engine.render_donut_chart(
            labels=['BTC', 'Altcoins'],
            values=[btc_dom, 100 - btc_dom],
            title='Market Dominance',
            center_text=f'{btc_dom:.0f}%\nBTC',
            colors=[Palette.WARNING, Palette.INDIGO_400],
            width=500, height=400,
        )
        _draw_chart_on_canvas(c, dom_buf, MARGIN + col_w + 6*mm, mid_y - 72*mm, col_w, 68*mm)

    # Bottom insight bar
    y_bottom = CONTENT_BOTTOM + 5*mm
    c.setFillColor(C_SLATE_50)
    c.roundRect(MARGIN, y_bottom, USABLE_W, 20*mm, 2*mm, fill=True, stroke=False)
    c.setFillColor(C_INDIGO)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(MARGIN + 5*mm, y_bottom + 12*mm, 'INSIGHT')
    c.setFillColor(C_SLATE_700)
    c.setFont('Helvetica', 8)
    sentiment = fg.get('classification', 'Neutral')
    insight = f'Market sentiment is {sentiment}. BTC dominance at {btc_dom:.1f}% suggests {"altcoin rotation opportunity" if btc_dom and btc_dom < 50 else "risk-off environment favoring BTC"}.'
    c.drawString(MARGIN + 5*mm, y_bottom + 4*mm, insight[:120])


def _slide_token_economy(c, d, engine, slide_num, total):
    """Slide 4: Token distribution & economy."""
    _draw_slide_header(c, 'Token Economy', 'Distribution, Supply & Economic Design', slide_num, total)
    _draw_slide_footer(c, d.get('project_name', ''))

    token_econ = d.get('token_economy', {})
    dist = token_econ.get('distribution', [])
    token_symbol = d.get('token_symbol', 'TOKEN')

    col_w = USABLE_W / 2 - 3*mm
    mid_y = CONTENT_TOP - 5*mm

    # Left: Pie chart
    if dist:
        labels = [item.get('category', '?') for item in dist]
        values = [item.get('percentage', 0) for item in dist]
        pie_buf = engine.render_pie_chart(
            labels=labels, values=values,
            title=f'{token_symbol} Token Distribution',
            width=600, height=500,
        )
        _draw_chart_on_canvas(c, pie_buf, MARGIN, mid_y - 100*mm, col_w, 95*mm)

    # Right: Token metrics
    rx = MARGIN + col_w + 6*mm
    ry = mid_y - 5*mm

    # Token info cards
    info_items = []
    inflation = token_econ.get('inflation_deflation', '')
    if inflation:
        info_items.append(('Supply Model', inflation[:60]))
    utility = token_econ.get('utility', '')
    if utility:
        info_items.append(('Token Utility', utility[:60]))

    if dist:
        # Top allocation
        sorted_dist = sorted(dist, key=lambda x: x.get('percentage', 0), reverse=True)
        top = sorted_dist[0]
        info_items.append(('Largest Allocation', f"{top.get('category', '?')}: {top.get('percentage', 0):.0f}%"))
        # Community vs insider
        community = sum(item.get('percentage', 0) for item in dist if 'community' in item.get('category', '').lower() or 'ecosystem' in item.get('category', '').lower())
        insider = sum(item.get('percentage', 0) for item in dist if 'team' in item.get('category', '').lower() or 'investor' in item.get('category', '').lower())
        if community or insider:
            info_items.append(('Distribution Ratio', f'Community {community:.0f}% vs Insider {insider:.0f}%'))

    for label, value in info_items[:5]:
        c.setFillColor(C_SLATE_50)
        c.roundRect(rx, ry - 16*mm, col_w - 4*mm, 15*mm, 2*mm, fill=True, stroke=False)
        c.setFillColor(C_INDIGO)
        c.rect(rx, ry - 16*mm, 3*mm, 15*mm, fill=True, stroke=False)
        c.setFillColor(C_SLATE_800)
        c.setFont('Helvetica-Bold', 8)
        c.drawString(rx + 6*mm, ry - 6*mm, label)
        c.setFillColor(C_SLATE_600)
        c.setFont('Helvetica', 7.5)
        c.drawString(rx + 6*mm, ry - 13*mm, value)
        ry -= 20*mm

    # Vesting timeline bar chart
    if dist:
        vesting_labels = [item.get('category', '?')[:15] for item in dist[:6]]
        vesting_vals = [item.get('percentage', 0) for item in dist[:6]]
        bar_buf = engine.render_bar_chart(
            labels=vesting_labels, values=vesting_vals,
            title='Allocation Breakdown',
            horizontal=True, value_suffix='%',
            width=750, height=max(250, len(vesting_labels)*45+60),
        )
        chart_h = max(40, len(vesting_labels)*8 + 15) * mm
        _draw_chart_on_canvas(c, bar_buf, MARGIN, CONTENT_BOTTOM + 5*mm, USABLE_W, min(chart_h, 65*mm))


def _slide_technical_architecture(c, d, engine, slide_num, total):
    """Slide 5: Technical architecture radar + pillar scores."""
    _draw_slide_header(c, 'Technical Architecture', 'Core Pillars & Multi-Dimensional Assessment', slide_num, total)
    _draw_slide_footer(c, d.get('project_name', ''))

    pillars = d.get('tech_pillars', [])
    infra = d.get('onchain_infra', {})
    col_w = USABLE_W / 2 - 3*mm
    mid_y = CONTENT_TOP - 5*mm

    # Left: Radar chart
    if pillars and len(pillars) >= 3:
        cats = [p.get('name', f'P{i}')[:18] for i, p in enumerate(pillars[:8])]
        vals = [p.get('score', 0) for p in pillars[:8]]
        radar_buf = engine.render_radar_chart(
            categories=cats, values=vals,
            title='Technical Profile',
            max_value=100, width=550, height=480,
        )
        _draw_chart_on_canvas(c, radar_buf, MARGIN, mid_y - 95*mm, col_w, 90*mm)

    # Right: Pillar score bars
    if pillars:
        labels = [p.get('name', '?')[:22] for p in pillars[:6]]
        scores = [p.get('score', 0) for p in pillars[:6]]
        colors = [Palette.score_color(s) for s in scores]
        bar_buf = engine.render_bar_chart(
            labels=labels, values=scores,
            title='Pillar Scores',
            horizontal=True, color_map=colors,
            value_suffix='/100', max_value=100,
            width=650, height=max(300, len(labels)*50+60),
        )
        _draw_chart_on_canvas(c, bar_buf, MARGIN + col_w + 6*mm, mid_y - 95*mm, col_w, 90*mm)

    # Bottom: Infrastructure info strip
    y_strip = CONTENT_BOTTOM + 5*mm
    c.setFillColor(C_DARK)
    c.roundRect(MARGIN, y_strip, USABLE_W, 18*mm, 2*mm, fill=True, stroke=False)

    strip_items = []
    if infra.get('chain'):
        strip_items.append(('Chain', infra['chain'][:25]))
    if infra.get('consensus'):
        strip_items.append(('Consensus', infra['consensus'][:20]))
    if infra.get('tps'):
        strip_items.append(('TPS', str(infra['tps'])[:15]))
    if infra.get('gas'):
        strip_items.append(('Gas Cost', str(infra['gas'])[:15]))

    if strip_items:
        item_w = USABLE_W / len(strip_items)
        for i, (label, val) in enumerate(strip_items):
            x = MARGIN + i * item_w + item_w/2
            c.setFillColor(C_INDIGO_LIGHT)
            c.setFont('Helvetica', 6.5)
            c.drawCentredString(x, y_strip + 11*mm, label)
            c.setFillColor(C_WHITE)
            c.setFont('Helvetica-Bold', 8.5)
            c.drawCentredString(x, y_strip + 4*mm, val)


def _slide_risk_assessment(c, d, engine, slide_num, total):
    """Slide 6: Risk matrix + severity indicators."""
    _draw_slide_header(c, 'Risk Assessment', 'Threat Analysis & Severity Matrix', slide_num, total)
    _draw_slide_footer(c, d.get('project_name', ''))

    risks = d.get('risks', [])

    if risks:
        # Full-width risk matrix
        matrix_buf = engine.render_risk_matrix(
            risks=risks,
            title='Impact vs Probability',
            width=700, height=480,
        )
        _draw_chart_on_canvas(c, matrix_buf, MARGIN, CONTENT_TOP - 95*mm, USABLE_W, 88*mm)

        # Risk summary strip
        y_strip = CONTENT_TOP - 100*mm
        critical = sum(1 for r in risks if r.get('impact', 0) * r.get('probability', 0) >= 15)
        high = sum(1 for r in risks if 9 <= r.get('impact', 0) * r.get('probability', 0) < 15)
        medium = sum(1 for r in risks if r.get('impact', 0) * r.get('probability', 0) < 9)

        box_data = [
            (str(critical), 'Critical', Palette.DANGER),
            (str(high), 'High', Palette.WARNING),
            (str(medium), 'Moderate', Palette.SUCCESS),
            (str(len(risks)), 'Total Risks', Palette.INDIGO_600),
        ]
        box_w = USABLE_W / 4 - 3*mm
        for i, (val, label, color) in enumerate(box_data):
            _draw_metric_box(c, MARGIN + i*(box_w + 4*mm), y_strip - 25*mm, box_w, 20*mm, val, label, color)

        # Risk list
        y_list = y_strip - 55*mm
        c.setFillColor(C_SLATE_800)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(MARGIN + 2*mm, y_list, 'Identified Risks:')
        y_list -= 5*mm

        for r in risks[:5]:
            score = r.get('impact', 0) * r.get('probability', 0)
            color = _hex(Palette.risk_color(score))
            c.setFillColor(color)
            c.circle(MARGIN + 5*mm, y_list - 1*mm, 2*mm, fill=True, stroke=False)
            c.setFillColor(C_SLATE_700)
            c.setFont('Helvetica', 8)
            desc = r.get('description', r.get('name', ''))[:70]
            c.drawString(MARGIN + 10*mm, y_list - 2*mm, f"{r.get('name', '?')} — {desc}")
            y_list -= 12


def _slide_crypto_economy(c, d, engine, slide_num, total):
    """Slide 7: Crypto economy design — 3-component framework + lifecycle."""
    _draw_slide_header(c, 'Crypto Economy Design', 'Value System, Reward System & Lifecycle Assessment', slide_num, total)
    _draw_slide_footer(c, d.get('project_name', ''))

    ce = d.get('crypto_economy', {})

    # Lifecycle timeline (top)
    lifecycle = ce.get('lifecycle', ce.get('lifecycle_assessment', {}))
    current_stage = lifecycle.get('current_stage', 'bootstrap') if lifecycle else 'bootstrap'

    timeline_buf = engine.render_lifecycle_timeline(
        current_stage=current_stage,
        title='Protocol Lifecycle Position',
        width=800, height=200,
    )
    _draw_chart_on_canvas(c, timeline_buf, MARGIN, CONTENT_TOP - 38*mm, USABLE_W, 32*mm)

    # Three-component framework boxes
    mid_y = CONTENT_TOP - 48*mm
    col_w = USABLE_W / 3 - 4*mm

    components = [
        ('Value System', ce.get('value_system', {}), C_INDIGO),
        ('Reward System', ce.get('reward_system', {}), HexColor(Palette.INFO)),
        ('Reward Mechanism', ce.get('reward_mechanism', ce.get('reward_mechanisms', {})), HexColor(Palette.SUCCESS)),
    ]

    for i, (title, data, color) in enumerate(components):
        x = MARGIN + i * (col_w + 6*mm)
        y = mid_y

        # Card background
        card_h = 75*mm
        c.setFillColor(C_SLATE_50)
        c.setStrokeColor(C_SLATE_200)
        c.roundRect(x, y - card_h, col_w, card_h, 3*mm, fill=True, stroke=True)

        # Colored top bar
        c.setFillColor(color)
        c.roundRect(x, y - 4*mm, col_w, 4*mm, 0, fill=True, stroke=False)

        # Title
        c.setFillColor(C_SLATE_800)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(x + 4*mm, y - 12*mm, title)

        # Content
        c.setFillColor(C_SLATE_600)
        c.setFont('Helvetica', 7)
        ty = y - 20*mm

        if isinstance(data, dict):
            for key, val in list(data.items())[:5]:
                key_str = key.replace('_', ' ').title()[:22]
                c.setFont('Helvetica-Bold', 6.5)
                c.drawString(x + 4*mm, ty, key_str)
                c.setFont('Helvetica', 6.5)
                if isinstance(val, list):
                    # Show first 2 items from list
                    for item in val[:2]:
                        ty -= 8
                        item_str = str(item.get('type', item) if isinstance(item, dict) else item)[:35]
                        c.drawString(x + 6*mm, ty, f'- {item_str}')
                    if len(val) > 2:
                        ty -= 8
                        c.drawString(x + 6*mm, ty, f'  +{len(val)-2} more')
                elif isinstance(val, dict):
                    ty -= 8
                    c.drawString(x + 4*mm, ty, f'{len(val)} fields')
                else:
                    ty -= 8
                    c.drawString(x + 4*mm, ty, str(val)[:35])
                ty -= 12
        elif isinstance(data, str):
            c.drawString(x + 4*mm, ty, data[:50])

    # Maturity indicators (bottom) — 2-column grid layout
    maturity = lifecycle.get('maturity_indicators', lifecycle.get('maturity_transition_indicators', {})) if lifecycle else {}
    if maturity:
        y_mat = mid_y - 82*mm
        c.setFillColor(C_SLATE_800)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(MARGIN + 2*mm, y_mat, 'Maturity Transition Indicators')
        y_mat -= 14

        items = list(maturity.items())[:6]
        col_w_ind = USABLE_W / 2 - 4*mm
        for idx, (key, val) in enumerate(items):
            col = idx % 2
            row = idx // 2
            ix = MARGIN + 2*mm + col * (col_w_ind + 8*mm)
            iy = y_mat - row * 14

            label = key.replace('_', ' ').title()
            if isinstance(val, bool):
                status = 'Achieved' if val else 'Not Yet'
                dot_color = HexColor(Palette.SUCCESS) if val else C_SLATE_400
            else:
                status = str(val)
                dot_color = HexColor(Palette.INFO)

            c.setFillColor(dot_color)
            c.circle(ix + 3, iy + 2, 3, fill=True, stroke=False)
            c.setFillColor(C_SLATE_700)
            c.setFont('Helvetica', 7)
            c.drawString(ix + 10, iy, f'{label}: {status}')


def _slide_investment_thesis(c, d, engine, slide_num, total):
    """Slide 8: Final scorecard & recommendation."""
    _draw_slide_header(c, 'Investment Thesis', 'Final Assessment & Forward-Looking Analysis', slide_num, total)
    _draw_slide_footer(c, d.get('project_name', ''))

    project_name = d.get('project_name', 'Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    rating = d.get('overall_rating', 'B')
    pillars = d.get('tech_pillars', [])

    # Large rating display (centered top)
    cx = W / 2
    cy = CONTENT_TOP - 30*mm
    r = 22*mm
    rc = _rating_color(rating)
    c.setFillColor(_hex(rc))
    c.circle(cx, cy, r, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont('Helvetica-Bold', 36)
    c.drawCentredString(cx, cy - 6*mm, rating)
    c.setFont('Helvetica', 9)
    c.drawCentredString(cx, cy - 17*mm, 'OVERALL RATING')

    c.setFillColor(C_SLATE_800)
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(cx, cy - 30*mm, f'{project_name} ({token_symbol})')

    # Heatmap: Multi-dimensional score view
    if pillars and len(pillars) >= 2:
        names = [p.get('name', '?')[:15] for p in pillars[:6]]
        scores = [p.get('score', 50) for p in pillars[:6]]
        hm_buf = engine.render_heatmap(
            z_data=[scores],
            x_labels=names,
            y_labels=[project_name],
            title='Score Heatmap',
            width=750, height=250,
        )
        _draw_chart_on_canvas(c, hm_buf, MARGIN, CONTENT_TOP - 105*mm, USABLE_W, 35*mm)

    # Thesis text
    thesis = d.get('investment_thesis', '')
    if thesis:
        y_thesis = CONTENT_TOP - 115*mm
        c.setFillColor(C_SLATE_50)
        c.roundRect(MARGIN, y_thesis - 50*mm, USABLE_W, 48*mm, 3*mm, fill=True, stroke=False)
        c.setFillColor(C_INDIGO)
        c.rect(MARGIN, y_thesis - 50*mm, 4*mm, 48*mm, fill=True, stroke=False)

        c.setFillColor(C_SLATE_800)
        c.setFont('Helvetica-Bold', 10)
        c.drawString(MARGIN + 8*mm, y_thesis - 8*mm, 'Investment Thesis')

        c.setFont('Helvetica', 8)
        c.setFillColor(C_SLATE_700)
        sentences = [s.strip() + '.' for s in thesis.split('.') if s.strip()][:4]
        ty = y_thesis - 18*mm
        for s in sentences:
            c.drawString(MARGIN + 8*mm, ty, s[:100])
            ty -= 11

    # Disclaimer
    y_disc = CONTENT_BOTTOM + 8*mm
    c.setFillColor(C_SLATE_400)
    c.setFont('Helvetica', 6)
    c.drawString(MARGIN, y_disc, 'This report is for informational purposes only and does not constitute investment advice.')
    c.drawString(MARGIN, y_disc - 8, f'\u00a9 {COPYRIGHT_YEAR} {ORG_NAME}. All rights reserved. Reproduction prohibited.')


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _rating_to_score(rating):
    """Convert letter rating to numeric score."""
    mapping = {'S': 97, 'A+': 93, 'A': 88, 'A-': 83, 'B+': 78, 'B': 73, 'B-': 68,
               'C+': 63, 'C': 58, 'C-': 53, 'D': 40, 'F': 20}
    return mapping.get(rating, 70)


# ═══════════════════════════════════════════════════════════
#  MAIN GENERATOR
# ═══════════════════════════════════════════════════════════

def generate_slide_econ(project_data: dict, output_dir: str = '/tmp') -> Tuple[str, dict]:
    """
    Generate a slide-style infographic PDF for Economy Design Analysis.

    Args:
        project_data: Enriched project JSON data
        output_dir: Directory to write output files

    Returns:
        Tuple of (pdf_path, metadata_dict)
    """
    slug = project_data.get('slug', project_data.get('project_name', 'project').lower().replace(' ', '_'))
    version = project_data.get('version', 1)
    project_name = project_data.get('project_name', 'Project')

    # Output path
    filename = f"{slug}_econ_slide_v{version}_en.pdf"
    pdf_path = os.path.join(output_dir, filename)

    # Initialize chart engine
    engine = ChartEngine()

    # Determine which slides to generate
    has_crypto_economy = bool(project_data.get('crypto_economy'))

    slides = [
        ('cover', _slide_cover),
        ('executive', _slide_executive_dashboard),
        ('market', _slide_market_overview),
        ('token', _slide_token_economy),
        ('technical', _slide_technical_architecture),
        ('risk', _slide_risk_assessment),
    ]
    if has_crypto_economy:
        slides.append(('crypto_economy', _slide_crypto_economy))
    slides.append(('thesis', _slide_investment_thesis))

    total_slides = len(slides)

    # Create PDF
    pdf = canvas.Canvas(pdf_path, pagesize=A4)
    pdf.setTitle(f'{project_name} — Economy Design Analysis (Infographic)')
    pdf.setAuthor(ORG_NAME)
    pdf.setSubject(f'RPT-ECON Slide v{version}')

    for i, (name, draw_func) in enumerate(slides):
        try:
            if name == 'cover':
                draw_func(pdf, project_data)
            else:
                draw_func(pdf, project_data, engine, i + 1, total_slides)
        except Exception as e:
            # Fallback: draw error slide
            pdf.setFillColor(C_WHITE)
            pdf.rect(0, 0, W, H, fill=True, stroke=False)
            _draw_slide_header(pdf, f'Slide: {name}', f'Error: {str(e)[:60]}', i+1, total_slides)
            _draw_slide_footer(pdf, project_name)

        pdf.showPage()

    pdf.save()

    # Metadata
    metadata = {
        'project_name': project_name,
        'token_symbol': project_data.get('token_symbol', ''),
        'slug': slug,
        'version': version,
        'format': 'slide',
        'slide_count': total_slides,
        'overall_rating': project_data.get('overall_rating', ''),
        'published_date': datetime.now().strftime('%Y-%m-%d'),
        'generator': 'gen_slide_econ v1.0',
        'has_crypto_economy': has_crypto_economy,
    }

    # Save metadata
    meta_path = os.path.join(output_dir, f"{slug}_econ_slide_v{version}_meta.json")
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return pdf_path, metadata


# ─── Test ────────────────────────────────────────────────

if __name__ == '__main__':
    from datetime import datetime

    sample = {
        'project_name': 'ElsaAI',
        'token_symbol': 'ELSA',
        'slug': 'elsaai',
        'version': 1,
        'overall_rating': 'B+',
        'executive_summary': (
            'ElsaAI is a decentralized AI agent platform enabling autonomous on-chain economic agents. '
            'The protocol leverages tokenized AI models with on-chain execution guarantees. '
            'Strong technical foundations with growing ecosystem adoption. '
            'Bootstrap phase shows promising capital retention metrics.'
        ),
        'investment_thesis': (
            'ElsaAI pioneers the AI-agent economy with strong technical foundations. '
            'Early-stage bootstrap phase shows promising capital retention metrics. '
            'Multi-chain expansion increases addressable market. '
            'Key risk is regulatory uncertainty around autonomous agents.'
        ),
        'identity': {'overview': 'Decentralized AI agent marketplace.'},
        'token_type': 'AI Infrastructure',
        'tech_pillars': [
            {'name': 'AI Agent Runtime', 'score': 82},
            {'name': 'Agent Identity (ERC-8004)', 'score': 78},
            {'name': 'Compute Market', 'score': 75},
            {'name': 'Governance System', 'score': 70},
            {'name': 'Security Audit', 'score': 85},
        ],
        'onchain_infra': {'chain': 'Base L2', 'consensus': 'Optimistic Rollup', 'tps': '2000', 'gas': '$0.001'},
        'value_flow': {'description': 'Agent fees → compute providers + treasury.'},
        'token_economy': {
            'distribution': [
                {'category': 'Community', 'amount': 400e6, 'percentage': 40},
                {'category': 'Team', 'amount': 200e6, 'percentage': 20},
                {'category': 'Treasury', 'amount': 150e6, 'percentage': 15},
                {'category': 'Investors', 'amount': 150e6, 'percentage': 15},
                {'category': 'Compute Rewards', 'amount': 100e6, 'percentage': 10},
            ],
            'inflation_deflation': 'Fixed 1B supply with 2% burn rate',
            'utility': 'Governance, staking, agent deployment, fee discounts',
        },
        'risks': [
            {'name': 'Regulatory', 'impact': 4, 'probability': 3, 'description': 'AI regulation uncertainty'},
            {'name': 'Smart Contract', 'impact': 5, 'probability': 1, 'description': 'Novel agent mechanisms'},
            {'name': 'Competition', 'impact': 4, 'probability': 4, 'description': 'Growing AI-crypto space'},
            {'name': 'Compute Dependency', 'impact': 4, 'probability': 2, 'description': 'Off-chain GPU reliance'},
            {'name': 'Market Risk', 'impact': 3, 'probability': 3, 'description': 'Crypto market volatility'},
        ],
        'market_data': {
            'current_price': 0.045, 'market_cap': 45_000_000, 'volume_24h': 3_200_000,
            'ath': 0.12, 'atl': 0.008, 'price_change_24h_pct': -3.2,
        },
        'macro_global': {'total_market_cap': 1_800_000_000_000, 'btc_dominance': 52.3},
        'fear_greed': {'fear_greed_index': 55, 'classification': 'Neutral'},
        'crypto_economy': {
            'system_type': 'platform',
            'value_system': {
                'onchain_components': ['Smart contract execution', 'Agent identity registry', 'Token staking'],
                'offchain_components': ['AI model inference', 'Training data pipeline'],
                'onchain_verifiability': 'partial',
            },
            'reward_system': {
                'capital_contributions': [{'type': 'Staking', 'description': 'ELSA staking for compute priority'}],
                'cost_contributions': [{'type': 'Development', 'description': 'Agent dev and model training'}],
                'actor_types': ['Capital providers', 'AI developers', 'Node operators', 'End users'],
            },
            'reward_mechanism': {
                'fungible_token': 'ELSA (ERC-20)',
                'nft_token': 'ERC-8004 Agent Identity NFT',
                'utility_function': 'Priority execution, governance, fee discounts',
            },
            'lifecycle': {
                'current_stage': 'bootstrap',
                'genesis_complete': True,
                'bootstrap_indicators': {'value_system_operational': True, 'capital_outflow_control': '30-50%'},
                'maturity_indicators': {
                    'actor_replacement': False, 'reward_stabilization': False,
                    'security_token_transition': True, 'revenue_realization': True,
                    'decentralization_automation': False,
                },
            },
        },
    }

    pdf_path, meta = generate_slide_econ(sample)
    print(f"\u2713 Slide PDF: {pdf_path}")
    print(f"\u2713 Slides: {meta['slide_count']}")
    print(f"\u2713 Format: {meta['format']}")
