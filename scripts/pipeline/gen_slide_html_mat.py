#!/usr/bin/env python3
"""
gen_slide_html_mat.py – High-quality HTML→PDF slide generator for MATURITY REPORT.

Produces 8-slide 16:9 landscape infographic PDF evaluating project execution maturity.
Uses Playwright (headless Chromium) for pixel-perfect rendering.
Follows the exact same architecture as gen_slide_html_econ.py with identical CSS, themes, and chart helpers.

Maturity Report Theme: Beige + Gold (matching ECON generator)
Focus: Strategic objective achievement, on-chain/off-chain architecture split, risk & mitigation.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Chart rendering ──────────────────────────────────────────
try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# ═══════════════════════════════════════════════════════════════
#  DESIGN SYSTEM  –  Beige + Gold theme matching BCE Lab samples
# ═══════════════════════════════════════════════════════════════

THEME = {
    'bg':          '#F5F1EB',
    'bg_alt':      '#EDE8DF',
    'surface':     '#FFFFFF',
    'border':      '#D4C5A9',
    'border_light':'#E6DDD0',
    'gold':        '#B8860B',
    'gold_light':  '#C9A84C',
    'gold_bg':     '#F0E6D0',
    'dark':        '#2D2D2D',
    'dark_mid':    '#3A3A3A',
    'text':        '#1A1A1A',
    'text_mid':    '#444444',
    'text_muted':  '#777777',
    'red':         '#C62828',
    'red_light':   '#EF5350',
    'green':       '#2E7D32',
    'blue':        '#1565C0',
    'blue_light':  '#5C9CE6',
    'purple':      '#6A1B9A',
    'teal':        '#00838F',
    'grid':        '#E0D8CC',
}

# Chart color palette matching the beige-gold theme
CHART_COLORS = [
    '#3D5A80',  # steel blue
    '#B8860B',  # dark goldenrod
    '#2E7D32',  # green
    '#C62828',  # red
    '#6A1B9A',  # purple
    '#00838F',  # teal
    '#E65100',  # deep orange
    '#455A64',  # blue grey
    '#8D6E63',  # brown
    '#546E7A',  # slate
]

# ═══════════════════════════════════════════════════════════════
#  CSS TEMPLATE - IDENTICAL TO ECON GENERATOR
# ═══════════════════════════════════════════════════════════════

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

@page {
  size: 1280px 720px;
  margin: 0;
}

body {
  font-family: 'Noto Sans KR', 'Helvetica Neue', Arial, sans-serif;
  color: %(text)s;
  background: %(bg)s;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

.slide {
  width: 1280px;
  height: 720px;
  position: relative;
  overflow: hidden;
  background: %(bg)s;
  page-break-after: always;
  page-break-inside: avoid;
}

/* Blueprint grid pattern overlay */
.slide::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(%(grid)s 1px, transparent 1px),
    linear-gradient(90deg, %(grid)s 1px, transparent 1px);
  background-size: 80px 80px;
  opacity: 0.25;
  pointer-events: none;
  z-index: 0;
}

/* Decorative border frame */
.slide-frame {
  position: absolute;
  top: 12px; left: 12px; right: 12px; bottom: 12px;
  border: 1.5px solid %(border)s;
  border-radius: 2px;
  z-index: 0;
  pointer-events: none;
}
.slide-frame::before {
  content: '';
  position: absolute;
  top: 4px; left: 4px; right: 4px; bottom: 4px;
  border: 0.5px solid %(border_light)s;
}

.slide-content {
  position: relative;
  z-index: 1;
  padding: 28px 44px;
  width: 100%%;
  height: 100%%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

/* Header bar */
.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: %(text_muted)s;
  margin-bottom: 16px;
}
.header-bar .credit {
  border: 1px solid %(border)s;
  padding: 4px 12px;
  background: %(surface)s;
  font-size: 10px;
}

/* Section title – MUCH LARGER */
.section-title {
  font-size: 48px;
  font-weight: 900;
  color: %(text)s;
  margin-bottom: 8px;
  letter-spacing: -0.5px;
  line-height: 1.2;
}
.section-subtitle {
  font-size: 18px;
  color: %(gold)s;
  font-weight: 500;
  margin-bottom: 20px;
}

/* Dark header banner – TALLER, MORE PROMINENT */
.dark-header {
  background: %(dark)s;
  color: #FFF;
  padding: 16px 28px;
  margin: -28px -44px 20px -44px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 50px;
}
.dark-header h2 {
  font-size: 28px;
  font-weight: 700;
}
.dark-header .badge {
  background: %(gold)s;
  color: #FFF;
  padding: 6px 16px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 700;
}

/* Gold accent label */
.gold-label {
  display: inline-block;
  background: linear-gradient(135deg, %(gold)s, %(gold_light)s);
  color: #FFF;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 700;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(184,134,11,0.3);
}

/* Card – HEAVIER STYLING */
.card {
  background: %(surface)s;
  border: 2.5px solid %(border)s;
  border-radius: 6px;
  padding: 24px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
}
.card-dark {
  background: %(dark)s;
  color: #FFF;
  border: 2.5px solid %(dark_mid)s;
  border-radius: 6px;
  padding: 24px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.15);
}

/* KPI metric box */
.kpi-row {
  display: flex;
  gap: 12px;
}
.kpi-box {
  flex: 1;
  background: %(surface)s;
  border: 2px solid %(border)s;
  padding: 16px 18px;
  text-align: center;
  border-radius: 4px;
  box-shadow: 0 3px 10px rgba(0,0,0,0.08);
}
.kpi-box .label { font-size: 11px; color: %(text_muted)s; margin-bottom: 6px; font-weight: 500; }
.kpi-box .value { font-size: 26px; font-weight: 900; color: %(text)s; }
.kpi-box .delta { font-size: 11px; font-weight: 700; }
.kpi-box .delta.neg { color: %(red)s; }
.kpi-box .delta.pos { color: %(green)s; }

/* Table – MUCH LARGER CELLS & TEXT */
.styled-table {
  width: 100%%;
  border-collapse: collapse;
  font-size: 16px;
}
.styled-table th {
  background: %(dark)s;
  color: #FFF;
  padding: 18px 20px;
  font-weight: 700;
  text-align: center;
  border: 2px solid %(dark_mid)s;
  font-size: 16px;
}
.styled-table td {
  padding: 18px 20px;
  border: 2px solid %(border)s;
  vertical-align: top;
  font-size: 16px;
}
.styled-table tr:nth-child(even) td { background: %(bg_alt)s; }
.styled-table .row-header {
  background: %(gold_bg)s;
  font-weight: 700;
  color: %(text)s;
  text-align: center;
  min-width: 120px;
  border: 2px solid %(gold)s;
}

/* Pillar card – 3D PEDESTAL STYLE */
.pillar-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.pillar-card {
  background: %(surface)s;
  border: 2.5px solid %(border)s;
  border-top: 4px solid %(dark)s;
  padding: 24px;
  text-align: center;
  border-radius: 6px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  min-height: 200px;
  position: relative;
}
.pillar-card .icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
}
.pillar-card h4 {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 8px;
  color: %(text)s;
}
.pillar-card .sub {
  font-size: 14px;
  color: %(gold)s;
  font-weight: 700;
  margin-bottom: 12px;
}
.pillar-card p {
  font-size: 14px;
  color: %(text_mid)s;
  line-height: 1.5;
  flex: 1;
}
.pillar-card .pedestal {
  background: %(dark)s;
  color: #FFF;
  margin: -24px -24px -24px -24px;
  margin-top: auto;
  padding: 12px 16px;
  border-radius: 0 0 4px 4px;
  font-size: 12px;
  text-align: center;
  border-top: 1px solid %(dark_mid)s;
}

/* Two-column layout */
.two-col { display: flex; gap: 24px; flex: 1; }
.two-col > * { flex: 1; }
.three-col { display: flex; gap: 16px; flex: 1; }
.three-col > * { flex: 1; }

/* Chart container */
.chart-container {
  display: flex;
  align-items: center;
  justify-content: center;
}
.chart-container img {
  max-width: 100%%;
  max-height: 100%%;
}

/* Bullet list – LARGER TEXT */
.bullet-list {
  list-style: none;
  padding: 0;
}
.bullet-list li {
  position: relative;
  padding-left: 24px;
  margin-bottom: 12px;
  font-size: 16px;
  line-height: 1.6;
}
.bullet-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: %(gold)s;
  font-weight: 900;
  font-size: 20px;
}

/* Checklist */
.checklist li::before {
  content: '☑';
  color: %(gold)s;
  font-size: 18px;
}

/* Flow diagram – THICKER ARROWS */
.flow-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.flow-box {
  background: %(surface)s;
  border: 2px solid %(border)s;
  padding: 20px 24px;
  text-align: center;
  border-radius: 6px;
  flex: 1;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.flow-box h4 {
  background: %(dark_mid)s;
  color: #FFF;
  padding: 6px 10px;
  font-size: 14px;
  margin: -20px -24px 10px -24px;
  border-radius: 4px 4px 0 0;
  font-weight: 700;
}
.flow-box p { font-size: 14px; color: %(text_mid)s; line-height: 1.5; font-weight: 500; }
.flow-arrow {
  font-size: 32px;
  color: %(gold)s;
  font-weight: 900;
  flex-shrink: 0;
  text-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* Comparison layout */
.compare-panel {
  display: flex;
  gap: 20px;
  align-items: stretch;
}
.compare-side {
  flex: 1;
  padding: 20px;
}

/* Footer */
.slide-footer {
  position: absolute;
  bottom: 16px;
  left: 44px;
  right: 44px;
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: %(text_muted)s;
  z-index: 2;
}

/* Rating badge */
.rating-circle {
  width: 80px; height: 80px;
  border-radius: 50%%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 900;
  color: #FFF;
  box-shadow: 0 6px 16px rgba(0,0,0,0.2);
}

/* Score progress bar */
.score-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.score-bar .label { font-size: 11px; color: %(text_muted)s; min-width: 40px; font-weight: 600; }
.score-bar .bar {
  flex: 1;
  height: 8px;
  background: %(border_light)s;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
}
.score-bar .fill {
  height: 100%%;
  background: linear-gradient(90deg, %(gold)s, %(gold_light)s);
  border-radius: 4px;
}

/* Conclusion banner – LARGER, FULL-WIDTH */
.conclusion-banner {
  background: linear-gradient(135deg, %(dark)s 0%%, %(dark_mid)s 100%%);
  color: #FFF;
  padding: 18px 28px;
  border-radius: 6px;
  border-left: 5px solid %(gold)s;
  font-size: 15px;
  line-height: 1.6;
  box-shadow: 0 6px 20px rgba(0,0,0,0.15);
}
.conclusion-banner strong { color: %(gold_light)s; font-weight: 700; }

/* Insight box */
.insight-box {
  background: %(gold_bg)s;
  border: 2px solid %(gold)s;
  border-radius: 6px;
  padding: 16px 20px;
  font-size: 14px;
  line-height: 1.6;
}
.insight-box .tag {
  color: %(gold)s;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  margin-bottom: 6px;
  letter-spacing: 0.5px;
}
""" % THEME


# ═══════════════════════════════════════════════════════════════
#  HERO SVG ILLUSTRATION - Isometric Blockchain (IDENTICAL TO ECON)
# ═══════════════════════════════════════════════════════════════

def _hero_illustration() -> str:
    """Large isometric 3D blockchain/gear illustration for cover slide."""
    g = THEME['gold']
    d = THEME['dark']
    return f'''<svg style="position:absolute;top:42%;left:52%;transform:translate(-50%,-50%);width:750px;height:580px;" viewBox="0 0 750 580" xmlns="http://www.w3.org/2000/svg">
      <!-- ===== LARGE ISOMETRIC CUBE (center) ===== -->
      <g transform="translate(320,220)" opacity="0.14">
        <polygon points="0,0 120,-70 120,80 0,150" fill="none" stroke="{d}" stroke-width="2.5"/>
        <polygon points="0,0 120,-70 240,0 120,70" fill="none" stroke="{d}" stroke-width="2.5"/>
        <polygon points="120,70 240,0 240,150 120,220" fill="none" stroke="{d}" stroke-width="1.5" stroke-dasharray="4,3"/>
        <line x1="60" y1="-35" x2="60" y2="115" stroke="{d}" stroke-width="1"/>
        <line x1="180" y1="-35" x2="180" y2="115" stroke="{d}" stroke-width="1"/>
        <line x1="0" y1="75" x2="240" y2="75" stroke="{d}" stroke-width="1"/>
      </g>
      <!-- ===== LARGE GEAR (top-right) ===== -->
      <g transform="translate(500,140)" opacity="0.16">
        <circle cx="0" cy="0" r="55" fill="none" stroke="{d}" stroke-width="2.5"/>
        <circle cx="0" cy="0" r="35" fill="none" stroke="{d}" stroke-width="2"/>
        <circle cx="0" cy="0" r="12" fill="none" stroke="{d}" stroke-width="2"/>
        <circle cx="0" cy="0" r="5" fill="{g}" opacity="0.5"/>
        <line x1="0" y1="-55" x2="0" y2="-68" stroke="{d}" stroke-width="5" stroke-linecap="round"/>
        <line x1="0" y1="55" x2="0" y2="68" stroke="{d}" stroke-width="5" stroke-linecap="round"/>
        <line x1="-55" y1="0" x2="-68" y2="0" stroke="{d}" stroke-width="5" stroke-linecap="round"/>
        <line x1="55" y1="0" x2="68" y2="0" stroke="{d}" stroke-width="5" stroke-linecap="round"/>
        <line x1="39" y1="-39" x2="48" y2="-48" stroke="{d}" stroke-width="5" stroke-linecap="round"/>
        <line x1="-39" y1="39" x2="-48" y2="48" stroke="{d}" stroke-width="5" stroke-linecap="round"/>
        <line x1="39" y1="39" x2="48" y2="48" stroke="{d}" stroke-width="5" stroke-linecap="round"/>
        <line x1="-39" y1="-39" x2="-48" y2="-48" stroke="{d}" stroke-width="5" stroke-linecap="round"/>
      </g>
      <!-- ===== SMALL GEAR (left) ===== -->
      <g transform="translate(180,160)" opacity="0.12">
        <circle cx="0" cy="0" r="35" fill="none" stroke="{d}" stroke-width="2"/>
        <circle cx="0" cy="0" r="20" fill="none" stroke="{d}" stroke-width="1.5"/>
        <circle cx="0" cy="0" r="4" fill="{g}" opacity="0.4"/>
        <line x1="0" y1="-35" x2="0" y2="-44" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="0" y1="35" x2="0" y2="44" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="-35" y1="0" x2="-44" y2="0" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="35" y1="0" x2="44" y2="0" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="25" y1="-25" x2="31" y2="-31" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="-25" y1="25" x2="-31" y2="31" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
      </g>
      <!-- ===== MICRO GEAR (bottom) ===== -->
      <g transform="translate(400,380)" opacity="0.10">
        <circle cx="0" cy="0" r="25" fill="none" stroke="{d}" stroke-width="2"/>
        <circle cx="0" cy="0" r="14" fill="none" stroke="{d}" stroke-width="1.5"/>
        <line x1="0" y1="-25" x2="0" y2="-32" stroke="{d}" stroke-width="3.5" stroke-linecap="round"/>
        <line x1="0" y1="25" x2="0" y2="32" stroke="{d}" stroke-width="3.5" stroke-linecap="round"/>
        <line x1="-25" y1="0" x2="-32" y2="0" stroke="{d}" stroke-width="3.5" stroke-linecap="round"/>
        <line x1="25" y1="0" x2="32" y2="0" stroke="{d}" stroke-width="3.5" stroke-linecap="round"/>
      </g>
      <!-- ===== SECOND ISOMETRIC CUBE (upper-left) ===== -->
      <g transform="translate(120,60)" opacity="0.10">
        <polygon points="0,0 80,-46 80,54 0,100" fill="none" stroke="{d}" stroke-width="2"/>
        <polygon points="0,0 80,-46 160,0 80,46" fill="none" stroke="{d}" stroke-width="2"/>
        <polygon points="80,46 160,0 160,100 80,146" fill="none" stroke="{d}" stroke-width="1.5"/>
      </g>
      <!-- ===== CIRCUIT BOARD TRACES ===== -->
      <g opacity="0.18">
        <path d="M80,300 L200,300 L230,270 L380,270 L410,300 L550,300" stroke="{d}" stroke-width="2" fill="none"/>
        <path d="M230,270 L230,200" stroke="{d}" stroke-width="1.5" fill="none"/>
        <path d="M380,270 L380,200 L420,180" stroke="{d}" stroke-width="1.5" fill="none"/>
        <path d="M300,300 L300,350 L350,380" stroke="{d}" stroke-width="1.5" fill="none"/>
        <path d="M180,170 L250,170 L280,140 L450,140 L500,170 L580,170" stroke="{d}" stroke-width="1.5" fill="none"/>
        <path d="M500,140 L540,100" stroke="{d}" stroke-width="1.5" fill="none" stroke-dasharray="5,3"/>
        <path d="M550,300 L600,340" stroke="{d}" stroke-width="1.5" fill="none" stroke-dasharray="5,3"/>
      </g>
      <!-- ===== CIRCUIT NODES (gold dots at junctions) ===== -->
      <g>
        <circle cx="230" cy="270" r="5" fill="{g}" opacity="0.35"/>
        <circle cx="380" cy="270" r="5" fill="{g}" opacity="0.35"/>
        <circle cx="300" cy="300" r="4" fill="{g}" opacity="0.30"/>
        <circle cx="500" cy="170" r="5" fill="{g}" opacity="0.35"/>
        <circle cx="280" cy="140" r="4" fill="{g}" opacity="0.30"/>
        <circle cx="450" cy="140" r="5" fill="{g}" opacity="0.35"/>
        <circle cx="230" cy="200" r="3.5" fill="{g}" opacity="0.25"/>
        <circle cx="550" cy="300" r="4" fill="{g}" opacity="0.30"/>
        <circle cx="180" cy="170" r="3.5" fill="{g}" opacity="0.25"/>
        <circle cx="580" cy="170" r="3.5" fill="{g}" opacity="0.25"/>
        <circle cx="350" cy="380" r="4" fill="{g}" opacity="0.30"/>
        <circle cx="600" cy="340" r="3" fill="{g}" opacity="0.20"/>
        <circle cx="540" cy="100" r="3" fill="{g}" opacity="0.20"/>
      </g>
      <!-- ===== SMALL DECORATIVE CUBES ===== -->
      <g transform="translate(580,250)" opacity="0.08">
        <polygon points="0,0 40,-23 40,27 0,50" fill="none" stroke="{d}" stroke-width="2"/>
        <polygon points="0,0 40,-23 80,0 40,23" fill="none" stroke="{d}" stroke-width="2"/>
        <polygon points="40,23 80,0 80,50 40,73" fill="none" stroke="{d}" stroke-width="1.5"/>
      </g>
      <g transform="translate(60,340)" opacity="0.08">
        <polygon points="0,0 30,-17 30,23 0,40" fill="none" stroke="{d}" stroke-width="1.5"/>
        <polygon points="0,0 30,-17 60,0 30,17" fill="none" stroke="{d}" stroke-width="1.5"/>
        <polygon points="30,17 60,0 60,40 30,57" fill="none" stroke="{d}" stroke-width="1.5"/>
      </g>
    </svg>'''


# ═══════════════════════════════════════════════════════════════
#  CHART HELPERS  –  Plotly → base64 PNG (IDENTICAL TO ECON)
# ═══════════════════════════════════════════════════════════════

def _chart_to_b64(fig: go.Figure, width=500, height=350) -> str:
    """Render Plotly figure to base64 PNG string."""
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Helvetica, Arial, sans-serif', size=12, color=THEME['text']),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    buf = io.BytesIO()
    try:
        fig.write_image(buf, format='png', width=width, height=height, scale=3)
    except Exception:
        fig.write_image(buf, format='png', width=width, height=height)
    return base64.b64encode(buf.getvalue()).decode()


def _make_donut_chart(labels, values, title='', width=420, height=350) -> str:
    colors = CHART_COLORS[:len(labels)]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=colors, line=dict(color=THEME['bg'], width=2)),
        textinfo='label+percent', textfont=dict(size=12),
        insidetextorientation='auto',
    ))
    fig.update_layout(title=dict(text=title, font=dict(size=15, color=THEME['text'])),
                      showlegend=False, width=width, height=height)
    return _chart_to_b64(fig, width, height)


def _make_radar_chart(categories, values, title='', max_val=10, width=420, height=380) -> str:
    """Radar chart with score labels."""
    labeled = [f'{c}' for c in categories]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=labeled + [labeled[0]],
        fill='toself',
        fillcolor='rgba(184,134,11,0.2)',
        line=dict(color=THEME['gold'], width=3),
        marker=dict(size=9, color=THEME['gold']),
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, max_val], showticklabels=True,
                           tickfont=dict(size=10), gridcolor=THEME['border_light']),
            angularaxis=dict(tickfont=dict(size=12, color=THEME['text'])),
            bgcolor='rgba(0,0,0,0)',
        ),
        title=dict(text=title, font=dict(size=15, color=THEME['text'])),
        showlegend=False, width=width, height=height,
        margin=dict(l=80, r=80, t=50, b=80),
    )
    return _chart_to_b64(fig, width, height)


def _make_bar_chart(labels, values, title='', horizontal=False, width=500, height=300) -> str:
    colors = CHART_COLORS[:len(labels)]
    if horizontal:
        fig = go.Figure(go.Bar(y=labels, x=values, orientation='h',
                               marker_color=colors, text=values,
                               textposition='outside', textfont=dict(size=12)))
    else:
        fig = go.Figure(go.Bar(x=labels, y=values,
                               marker_color=colors, text=values,
                               textposition='outside', textfont=dict(size=12)))
    fig.update_layout(title=dict(text=title, font=dict(size=15, color=THEME['text'])),
                      showlegend=False, width=width, height=height,
                      yaxis=dict(showgrid=True, gridcolor=THEME['border_light']))
    return _chart_to_b64(fig, width, height)


def _make_risk_bubble(risks: list, title='', width=500, height=350) -> str:
    """Risk matrix bubble chart."""
    fig = go.Figure()
    sev_colors = {'critical': THEME['red'], 'high': '#E65100',
                  'medium': THEME['gold'], 'low': THEME['green']}
    text_positions = ['top center', 'bottom center', 'top right', 'bottom left', 'top left', 'bottom right']
    for i, r in enumerate(risks):
        fig.add_trace(go.Scatter(
            x=[r.get('probability', 3)], y=[r.get('impact', 3)],
            mode='markers+text', text=[r.get('name', '')[:16]],
            textposition=text_positions[i % len(text_positions)],
            textfont=dict(size=11),
            marker=dict(size=r.get('impact', 3)*12,
                       color=sev_colors.get(r.get('severity', 'medium'), THEME['gold']),
                       opacity=0.75, line=dict(width=2, color='#FFF')),
            showlegend=False,
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=THEME['text'])),
        xaxis=dict(title='Probability', range=[0, 6], showgrid=True,
                  gridcolor=THEME['border_light']),
        yaxis=dict(title='Impact', range=[0, 6], showgrid=True,
                  gridcolor=THEME['border_light']),
        width=width, height=height,
    )
    fig.add_shape(type='rect', x0=3, y0=3, x1=6, y1=6,
                  fillcolor='rgba(198,40,40,0.08)', line_width=0)
    return _chart_to_b64(fig, width, height)


def _make_gauge(value, max_val=100, title='', width=320, height=250) -> str:
    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=value,
        title=dict(text=title, font=dict(size=14)),
        gauge=dict(
            axis=dict(range=[0, max_val], tickwidth=1, tickcolor=THEME['text_muted']),
            bar=dict(color=THEME['gold']),
            bgcolor=THEME['bg_alt'],
            bordercolor=THEME['border'],
            steps=[
                dict(range=[0, max_val*0.3], color='rgba(198,40,40,0.15)'),
                dict(range=[max_val*0.3, max_val*0.7], color='rgba(184,134,11,0.12)'),
                dict(range=[max_val*0.7, max_val], color='rgba(46,125,50,0.12)'),
            ],
        ),
    ))
    fig.update_layout(width=width, height=height)
    return _chart_to_b64(fig, width, height)


# ═══════════════════════════════════════════════════════════════
#  HTML ASSEMBLY HELPERS
# ═══════════════════════════════════════════════════════════════

def _header_bar(credit_text: str = '') -> str:
    if not credit_text:
        credit_text = '저작권 : 블록체인경제연구소(Crypto Economy Lab) │ 연락처 : zhang@coinlab.co.kr'
    return f'''<div class="header-bar">
      <div class="credit">{credit_text}</div>
    </div>'''


def _footer(project_name: str = '', page: int = 0, total: int = 0) -> str:
    date = datetime.now().strftime('%Y. %m.')
    right = f'{page}/{total}' if page else ''
    return f'''<div class="slide-footer">
      <span>© {datetime.now().year} BCE Lab │ {project_name}</span>
      <span>{date} │ bcelab.xyz {right}</span>
    </div>'''


def _img_tag(b64: str, alt: str = '', style: str = '') -> str:
    return f'<img src="data:image/png;base64,{b64}" alt="{alt}" style="{style}"/>'


# ═══════════════════════════════════════════════════════════════
#  SLIDE GENERATORS - MAT REPORT (8 SLIDES)
# ═══════════════════════════════════════════════════════════════

def slide_cover_mat(d: dict) -> str:
    """Slide 1: Cover with maturity score badge and strategic overview."""
    name = d.get('project_name', 'Project')
    stage = d.get('maturity_stage', 'growing').capitalize()
    score = d.get('total_maturity_score', 0)
    summary = d.get('executive_summary', '')[:120]
    date_str = datetime.now().strftime('%Y. %m.')

    score_color = THEME['green'] if score >= 80 else THEME['gold'] if score >= 60 else THEME['red']

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      {_hero_illustration()}
      <div class="slide-content" style="padding:28px 80px; position:relative; z-index:1;">
        {_header_bar()}
        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;position:relative;">
          <h1 style="font-size:68px;font-weight:900;line-height:1.25;margin-bottom:20px;letter-spacing:-1px;">크립토 이코노미 진행률 평가 보고서</h1>
          <p style="font-size:20px;color:{THEME['text_mid']};max-width:800px;line-height:1.7;font-weight:500;">
            {name} 프로젝트 종합 성숙도 분석
          </p>
          <div style="margin-top:16px;width:140px;height:4px;background:linear-gradient(90deg,{THEME['gold']},{THEME['gold_light']});border-radius:2px;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:flex-end;">
          <div>
            <span class="gold-label" style="font-size:14px;padding:8px 20px;">Published: {date_str}</span>
            <span class="gold-label" style="margin-left:10px;font-size:14px;padding:8px 20px;">Maturity: {stage}</span>
          </div>
          <div style="text-align:center;">
            <div class="rating-circle" style="background:{score_color};width:100px;height:100px;font-size:36px;">{score:.1f}%</div>
            <div style="font-size:9px;color:{THEME['text_muted']};font-weight:700;letter-spacing:2px;margin-top:4px;">MATURITY SCORE</div>
          </div>
        </div>
      </div>
    </div>'''


def slide_executive_summary_mat(d: dict) -> str:
    """Slide 2: 3-column layout with identity, maturity gauge, architecture split."""
    name = d.get('project_name', 'Project')
    identity = d.get('project_identity', [])
    score = d.get('total_maturity_score', 0)
    summary = d.get('executive_summary', '')
    objectives = d.get('strategic_objectives', [])
    arch = d.get('architecture', {})
    arch_summary = d.get('architecture_summary', '')

    # Left: Identity (4 items) + Target Network info + score
    id_items = ''
    id_list = identity if isinstance(identity, list) else [identity]
    for item in id_list[:4]:
        id_items += f'<li>{item}</li>'

    # Center: Objectives with bars + Insight box
    obj_bars = ''
    avg_achievement = 0
    best_performer = ''
    best_score = 0
    for obj in objectives[:5]:
        obj_name = obj.get('short_name', obj.get('name', ''))[:14]
        obj_score = obj.get('achievement_rate', 0)
        avg_achievement += obj_score
        if obj_score > best_score:
            best_score = obj_score
            best_performer = obj_name
        bar_color = THEME['green'] if obj_score >= 80 else THEME['gold'] if obj_score >= 60 else THEME['red']
        obj_bars += f'''<div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px;font-weight:600;">
            <span>{obj_name}</span><span style="color:{bar_color};font-weight:700;">{obj_score:.0f}%</span>
          </div>
          <div style="height:8px;background:{THEME['border_light']};border-radius:4px;overflow:hidden;">
            <div style="height:100%;width:{obj_score}%;background:{bar_color};border-radius:4px;"></div>
          </div>
        </div>'''

    if objectives:
        avg_achievement = avg_achievement / len(objectives)

    # Right: On-chain/Off-chain split
    onchain_pct = arch.get('onchain_pct', arch.get('onchain_percentage', 50))
    offchain_pct = arch.get('offchain_pct', arch.get('offchain_percentage', 50))
    gauge_b64 = _make_donut_chart(['On-Chain', 'Off-Chain'], [onchain_pct, offchain_pct], 'Architecture Split', 300, 250) if HAS_PLOTLY else ''

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">경영 요약 및 전략 개요</div>
        <div class="section-subtitle">Executive Summary & Strategic Overview</div>
        <div class="three-col" style="flex:1;min-height:0;">
          <div class="card">
            <h3 style="font-size:16px;font-weight:900;margin-bottom:12px;">Project Identity</h3>
            <ul class="bullet-list" style="margin-bottom:16px;font-size:13px;">{id_items}</ul>
            <div style="margin-bottom:12px;padding:12px;background:{THEME['gold_bg']};border:1px solid {THEME['gold']};border-radius:4px;font-size:12px;">
              <div style="font-weight:700;color:{THEME['gold']};margin-bottom:4px;">Target Network</div>
              <div style="color:{THEME['text_mid']};line-height:1.5;">{arch.get('target_network', 'Multi-chain ecosystem')}</div>
            </div>
            <div style="margin-top:auto;background:{THEME['dark']};color:#FFF;padding:12px 16px;border-radius:4px;font-size:13px;font-weight:600;">
              <div style="font-size:10px;opacity:0.7;letter-spacing:0.5px;margin-bottom:4px;">MATURITY SCORE</div>
              <div style="font-size:24px;font-weight:900;color:{THEME['gold_light']};text-align:center;">{score:.1f}%</div>
            </div>
          </div>
          <div class="card">
            <h3 style="font-size:16px;font-weight:900;text-align:center;margin-bottom:12px;">Strategic Objectives</h3>
            {obj_bars}
            <div style="margin-top:12px;padding:12px;background:{THEME['bg_alt']};border-radius:4px;border:1px solid {THEME['border']};font-size:12px;">
              <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="color:{THEME['text_muted']};">Avg Achievement:</span>
                <span style="font-weight:700;color:{THEME['gold']}">{avg_achievement:.1f}%</span>
              </div>
              <div style="display:flex;justify-content:space-between;">
                <span style="color:{THEME['text_muted']};">Best Performer:</span>
                <span style="font-weight:700;color:{THEME['green']}">{best_performer}</span>
              </div>
            </div>
          </div>
          <div class="card">
            <h3 style="font-size:16px;font-weight:900;text-align:center;margin-bottom:12px;">Architecture</h3>
            <div class="chart-container" style="height:180px;">
              {_img_tag(gauge_b64, 'Architecture Split') if gauge_b64 else '<div>Chart unavailable</div>'}
            </div>
            <div style="margin-top:12px;font-size:12px;text-align:center;font-weight:600;margin-bottom:12px;">
              <div style="display:flex;justify-content:space-around;padding:8px 0;border-top:1px solid {THEME['border_light']};">
                <div><div style="color:{THEME['text_muted']};font-weight:400;font-size:11px;">On-Chain</div><div style="color:{THEME['gold']};">{onchain_pct:.0f}%</div></div>
                <div><div style="color:{THEME['text_muted']};font-weight:400;font-size:11px;">Off-Chain</div><div style="color:{THEME['gold']};">{offchain_pct:.0f}%</div></div>
              </div>
            </div>
            <div style="font-size:11px;color:{THEME['text_mid']};line-height:1.4;padding:10px;background:{THEME['bg_alt']};border-radius:3px;">
              {arch_summary or 'Hybrid architecture ensures both flexibility and trustworthiness'}
            </div>
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:12px;">
          <strong>핵심 가치 제안:</strong> {summary[:100]}
        </div>
        {_footer(name, 2, 8)}
      </div>
    </div>'''


def slide_objectives_assessment(d: dict) -> str:
    """Slide 3: Full-width horizontal bar chart for each objective with KPI boxes."""
    name = d.get('project_name', 'Project')
    objectives = d.get('strategic_objectives', [])

    bars_html = ''
    total_weight = 0
    total_achievement = 0
    best_obj_name = ''
    best_obj_score = 0

    for obj in objectives:
        obj_name = obj.get('name', '')
        weight = obj.get('weight', 0)
        achievement = obj.get('achievement_rate', 0)
        score = obj.get('weighted_score', 0)
        total_weight += weight
        total_achievement += achievement
        if achievement > best_obj_score:
            best_obj_score = achievement
            best_obj_name = obj.get('short_name', obj_name)

        bar_color = THEME['green'] if achievement >= 80 else THEME['gold'] if achievement >= 60 else THEME['red']

        bars_html += f'''<div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <div style="flex:1;">
              <div style="font-size:13px;font-weight:700;color:{THEME['text']}">{obj_name}</div>
              <div style="font-size:11px;color:{THEME['text_muted']};margin-top:1px;">Weight: {weight}% | Achievement: {achievement:.0f}% | Weighted Score: {score:.1f}</div>
            </div>
            <div style="width:60px;text-align:right;">
              <div style="font-size:16px;font-weight:900;color:{bar_color};">{achievement:.0f}%</div>
            </div>
          </div>
          <div style="height:14px;background:{THEME['border_light']};border-radius:4px;overflow:hidden;border:1px solid {THEME['border']};">
            <div style="height:100%;width:{achievement}%;background:linear-gradient(90deg,{bar_color},{THEME['gold_light']});border-radius:4px;"></div>
          </div>
        </div>'''

    # Weight distribution summary
    weight_summary = ' + '.join([f"{obj.get('short_name', obj.get('name', ''))[:12]} ({obj.get('weight', 0):.0f}%)" for obj in objectives[:5]])

    avg_achievement = total_achievement / len(objectives) if objectives else 0

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">전략 목표 달성도 평가</div>
        <div class="section-subtitle">Achievement Rate by Pillar (Weighted Distribution)</div>
        <div style="flex:1;display:flex;flex-direction:column;justify-content:space-between;gap:10px;">
          <div class="card" style="padding:14px 20px;flex:1;">
            {bars_html}
          </div>
          <div style="display:flex;gap:12px;height:90px;">
            <div class="card" style="flex:1;padding:12px;text-align:center;background:{THEME['gold_bg']};border-color:{THEME['gold']};">
              <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:4px;">TOTAL WEIGHT COVERED</div>
              <div style="font-size:28px;font-weight:900;color:{THEME['gold']};margin-bottom:3px;">{total_weight:.0f}%</div>
              <div style="font-size:10px;color:{THEME['text_mid']};">All objectives accounted</div>
            </div>
            <div class="card" style="flex:1;padding:12px;text-align:center;background:#E8F5E9;border-color:{THEME['green']};">
              <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:4px;">AVERAGE ACHIEVEMENT</div>
              <div style="font-size:28px;font-weight:900;color:{THEME['green']};margin-bottom:3px;">{avg_achievement:.1f}%</div>
              <div style="font-size:10px;color:{THEME['text_mid']};">Across all objectives</div>
            </div>
            <div class="card" style="flex:1;padding:12px;text-align:center;background:{THEME['bg_alt']};border-color:{THEME['border']};">
              <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:4px;">BEST PERFORMER</div>
              <div style="font-size:24px;font-weight:900;color:{THEME['gold']};margin-bottom:3px;">{best_obj_score:.0f}%</div>
              <div style="font-size:10px;color:{THEME['text_mid']};word-break:break-word;">{best_obj_name}</div>
            </div>
          </div>
          <div class="insight-box">
            <div class="tag">Weight Distribution</div>
            {weight_summary}
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:6px;padding:14px 20px;font-size:13px;line-height:1.4;">
          <strong>전체 가중치 분포:</strong> {weight_summary}로 균형잡힌 평가 체계 구성
        </div>
        {_footer(name, 3, 8)}
      </div>
    </div>'''


def slide_architecture_panel(d: dict) -> str:
    """Slide 4: Two-panel On-Chain vs Off-Chain architecture comparison with KPI boxes."""
    name = d.get('project_name', 'Project')
    arch = d.get('architecture', {})

    onchain_pct = arch.get('onchain_pct', arch.get('onchain_percentage', 55))
    offchain_pct = arch.get('offchain_pct', arch.get('offchain_percentage', 45))
    onchain_comps = arch.get('onchain_components', [])
    offchain_comps = arch.get('offchain_components', [])

    def _render_comp(c):
        if isinstance(c, dict):
            return f"<strong>{c.get('name', '')}</strong> — {c.get('description', '')}"
        return str(c)

    onchain_html = ''.join([f'<li style="margin-bottom:10px;font-size:14px;line-height:1.5;">{_render_comp(c)}</li>' for c in onchain_comps[:4]])
    offchain_html = ''.join([f'<li style="margin-bottom:10px;font-size:14px;line-height:1.5;">{_render_comp(c)}</li>' for c in offchain_comps[:4]])

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">온체인/오프체인 아키텍처</div>
        <div class="section-subtitle">On-Chain & Off-Chain Architecture Panel</div>
        <div style="display:flex;gap:20px;flex:1;min-height:0;margin-bottom:12px;">
          <div class="card" style="flex:1;background:{THEME['gold_bg']};border-color:{THEME['gold']};">
            <h3 style="font-size:18px;font-weight:900;margin-bottom:12px;color:{THEME['gold']};">오프체인 지능형 추론</h3>
            <div style="font-size:14px;font-weight:700;color:{THEME['dark']};margin-bottom:12px;">{offchain_pct:.0f}% - Smart Reasoning</div>
            <ul class="bullet-list" style="font-size:13px;">
              {offchain_html}
            </ul>
          </div>
          <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;min-width:40px;">
            <div style="font-size:32px;font-weight:900;color:{THEME['gold']};text-shadow:0 2px 4px rgba(0,0,0,0.1);">⇄</div>
            <div style="width:2px;height:60px;background:{THEME['gold']};"></div>
          </div>
          <div class="card" style="flex:1;background:#E8F5E9;border-color:{THEME['green']};">
            <h3 style="font-size:18px;font-weight:900;margin-bottom:12px;color:{THEME['green']};">온체인 신뢰 및 실행</h3>
            <div style="font-size:14px;font-weight:700;color:{THEME['dark']};margin-bottom:12px;">{onchain_pct:.0f}% - Verifiable Execution</div>
            <ul class="bullet-list" style="font-size:13px;">
              {onchain_html}
            </ul>
          </div>
        </div>
        <div style="display:flex;gap:12px;height:100px;">
          <div class="card" style="flex:1;padding:14px;text-align:center;background:{THEME['gold_bg']};border-color:{THEME['gold']};">
            <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:6px;">ON-CHAIN RATIO</div>
            <div style="font-size:36px;font-weight:900;color:{THEME['gold']};margin-bottom:2px;">{onchain_pct:.0f}%</div>
            <div style="font-size:11px;color:{THEME['text_mid']};font-weight:500;">Verifiable Settlement</div>
          </div>
          <div class="card" style="flex:1;padding:14px;text-align:center;background:#E8F5E9;border-color:{THEME['green']};">
            <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:6px;">OFF-CHAIN RATIO</div>
            <div style="font-size:36px;font-weight:900;color:{THEME['green']};margin-bottom:2px;">{offchain_pct:.0f}%</div>
            <div style="font-size:11px;color:{THEME['text_mid']};font-weight:500;">Intelligent Reasoning</div>
          </div>
          <div class="card" style="flex:1;padding:14px;text-align:center;background:{THEME['bg_alt']};border-color:{THEME['border']};">
            <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:6px;">TRUST BOUNDARY</div>
            <div style="font-size:36px;font-weight:900;color:{THEME['dark']};margin-bottom:2px;">⇄</div>
            <div style="font-size:11px;color:{THEME['text_mid']};font-weight:500;">Hybrid Model</div>
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:12px;">
          <strong>하이브리드 아키텍처:</strong> 오프체인 지능형 추론은 유연한 의사결정을 가능하게 하며, 온체인 정산이 암호학적 신뢰와 검증가능성을 보장합니다.
        </div>
        {_footer(name, 4, 8)}
      </div>
    </div>'''


def slide_timeline_milestones(d: dict) -> str:
    """Slide 5: Progress timeline with milestones (inc. descriptions) and maturity progression."""
    name = d.get('project_name', 'Project')
    milestones = d.get('timeline_milestones', [])
    score = d.get('total_maturity_score', 0)
    maturity_progression = d.get('maturity_progression', [])

    milestone_html = ''
    for m in milestones[:6]:
        m_name = m.get('name', '')
        m_date = m.get('date', '')
        m_status = m.get('status', 'planned')
        m_desc = m.get('description', '')
        status_color = THEME['green'] if m_status == 'completed' else THEME['gold']
        status_icon = '✓' if m_status == 'completed' else '→'

        milestone_html += f'''<div style="margin-bottom:14px;display:flex;align-items:flex-start;gap:12px;">
          <div style="font-size:20px;font-weight:900;color:{status_color};flex-shrink:0;width:30px;text-align:center;">{status_icon}</div>
          <div style="flex:1;">
            <div style="font-size:14px;font-weight:700;">{m_name}</div>
            <div style="font-size:11px;color:{THEME['text_muted']};margin-top:2px;margin-bottom:4px;">{m_date}</div>
            {f'<div style="font-size:12px;color:{THEME["text_mid"]};line-height:1.4;">{m_desc}</div>' if m_desc else ''}
          </div>
        </div>'''

    # Determine current stage based on score
    if score >= 86:
        current_stage = 'Established'
        stage_idx = 3
    elif score >= 61:
        current_stage = 'Mature'
        stage_idx = 2
    elif score >= 26:
        current_stage = 'Growing'
        stage_idx = 1
    else:
        current_stage = 'Nascent'
        stage_idx = 0

    # Default maturity progression if not provided
    default_stages = [
        ('Nascent', '0-25%', 'Initial development with proof of concept', 0),
        ('Growing', '26-60%', 'MVP deployed; early users engaging', 1),
        ('Mature', '61-85%', 'Stable operations; significant user base', 2),
        ('Established', '86-100%', 'Full autonomy; market leadership', 3),
    ]

    stages = maturity_progression if maturity_progression else default_stages

    stages_html = ''
    for idx, stage in enumerate(stages[:4]):
        if isinstance(stage, dict):
            stage_name = stage.get('name', 'Stage')
            stage_range = stage.get('range', '')
            stage_desc = stage.get('description', '')
        else:
            stage_name, stage_range, stage_desc, _ = stage

        is_current = idx == stage_idx
        bg_color = THEME['gold_bg'] if is_current else THEME['bg_alt']
        border_color = THEME['gold'] if is_current else THEME['border']
        accent_color = THEME['gold'] if is_current else THEME['text_muted']

        stages_html += f'''<div style="margin-bottom:12px;padding:10px;background:{bg_color};border:2px solid {border_color};border-radius:4px;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <div style="font-size:20px;font-weight:900;color:{accent_color};">{idx + 1}</div>
            <div>
              <div style="font-size:13px;font-weight:700;color:{THEME['text']};">{stage_name} {is_current and '●' or ''}</div>
              <div style="font-size:11px;color:{THEME['text_muted']};">{stage_range}</div>
            </div>
          </div>
          <div style="font-size:11px;color:{THEME['text_mid']};line-height:1.4;margin-left:28px;">{stage_desc}</div>
        </div>'''

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">진행 타임라인 및 마일스톤</div>
        <div class="section-subtitle">Progress Timeline & Milestones</div>
        <div style="flex:1;display:flex;gap:20px;min-height:0;">
          <div class="card" style="flex:1;">
            <h3 style="font-size:16px;font-weight:900;margin-bottom:4px;">Project Roadmap</h3>
            <div style="font-size:12px;color:{THEME['text_muted']};margin-bottom:16px;">Key milestones and progress checkpoints</div>
            <div style="flex:1;overflow-y:auto;max-height:280px;">
              {milestone_html}
            </div>
            <div style="margin-top:12px;padding-top:12px;border-top:1px solid {THEME['border']};text-align:center;">
              <div style="font-size:12px;color:{THEME['text_muted']};margin-bottom:4px;">Current Maturity Score</div>
              <div style="font-size:28px;font-weight:900;color:{THEME['gold']};">{score:.1f}%</div>
            </div>
          </div>
          <div class="card" style="flex:1;background:{THEME['dark']};color:#FFF;">
            <h3 style="font-size:16px;font-weight:900;margin-bottom:12px;color:{THEME['gold_light']};text-align:center;">Maturity Progression</h3>
            {stages_html}
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:12px;">
          <strong>현재 단계:</strong> <span style="color:{THEME['gold']};">{current_stage}</span> – {score:.1f}% 성숙도 달성, 지속적 발전 경로 진행 중
        </div>
        {_footer(name, 5, 8)}
      </div>
    </div>'''


def slide_goal_achievement(d: dict) -> str:
    """Slide 6: Radar chart + full weighted score table + conclusion banner."""
    name = d.get('project_name', 'Project')
    objectives = d.get('strategic_objectives', [])
    score = d.get('total_maturity_score', 0)
    stage = d.get('maturity_stage', 'growing')

    # Radar data
    obj_names = [obj.get('short_name', obj.get('name', ''))[:16] for obj in objectives]
    obj_scores = [obj.get('achievement_rate', 0) for obj in objectives]
    radar_b64 = _make_radar_chart(obj_names, obj_scores, 'Objective Achievement Radar', 100, 380, 320) if HAS_PLOTLY else ''

    # Weighted score breakdown table - ALL COLUMNS
    score_rows = ''
    total_weighted = 0
    for obj in objectives[:5]:
        obj_name = obj.get('name', '')
        weight = obj.get('weight', 0)
        achievement = obj.get('achievement_rate', 0)
        weighted = obj.get('weighted_score', 0)
        total_weighted += weighted
        score_rows += f'''<tr>
          <td style="text-align:left;padding:6px 4px;border-bottom:1px solid {THEME['border_light']};">{obj_name[:25]}</td>
          <td style="text-align:center;padding:6px 4px;border-bottom:1px solid {THEME['border_light']};">{weight:.0f}%</td>
          <td style="text-align:center;padding:6px 4px;border-bottom:1px solid {THEME['border_light']};">{achievement:.0f}%</td>
          <td style="text-align:center;padding:6px 4px;border-bottom:1px solid {THEME['border_light']};font-weight:700;color:{THEME['gold']};">{weighted:.1f}</td>
        </tr>'''

    stage_badge_color = THEME['green'] if score >= 80 else THEME['gold'] if score >= 60 else THEME['red']

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">목표 달성도 스코어링</div>
        <div class="section-subtitle">Goal Achievement Scoring</div>
        <div class="two-col" style="flex:1;min-height:0;gap:16px;">
          <div class="chart-container" style="height:320px;">
            {_img_tag(radar_b64, 'Achievement Radar') if radar_b64 else '<div>Chart unavailable</div>'}
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;flex:1;">
            <div class="card" style="padding:12px;flex:1;overflow-y:auto;">
              <h4 style="font-size:12px;font-weight:700;color:{THEME['gold']};letter-spacing:0.5px;margin-bottom:8px;">WEIGHTED SCORE BREAKDOWN (모든 지표)</h4>
              <table class="styled-table" style="font-size:10px;width:100%;">
                <thead>
                  <tr style="border-bottom:2px solid {THEME['gold']};">
                    <th style="text-align:left;padding:6px 4px;font-weight:700;font-size:10px;">Objective</th>
                    <th style="text-align:center;padding:6px 4px;font-weight:700;font-size:10px;">Weight</th>
                    <th style="text-align:center;padding:6px 4px;font-weight:700;font-size:10px;">Achievement</th>
                    <th style="text-align:center;padding:6px 4px;font-weight:700;font-size:10px;">Weighted</th>
                  </tr>
                </thead>
                <tbody>
                  {score_rows}
                </tbody>
              </table>
            </div>
            <div class="card" style="padding:14px;text-align:center;background:{THEME['dark']};color:#FFF;border-color:{THEME['dark_mid']};min-height:100px;display:flex;flex-direction:column;justify-content:center;">
              <div style="font-size:9px;opacity:0.7;letter-spacing:0.5px;margin-bottom:6px;font-weight:700;">TOTAL MATURITY SCORE</div>
              <div style="font-size:36px;font-weight:900;color:{THEME['gold_light']};margin-bottom:8px;">{score:.1f}</div>
              <div style="background:{stage_badge_color};color:#FFF;padding:6px 12px;border-radius:4px;font-size:11px;font-weight:700;display:inline-block;align-self:center;margin-bottom:6px;">
                {stage.upper()}
              </div>
              <div style="font-size:10px;opacity:0.9;margin-top:4px;">Total Weighted: {total_weighted:.1f}</div>
            </div>
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:10px;padding:12px 18px;font-size:13px;line-height:1.4;">
          <strong>최종 성숙도 점수:</strong> <span style="color:{stage_badge_color};font-weight:900;">{score:.1f}%</span> – <span style="color:{THEME['text_mid']};">{stage.title()} stage</span> 분류. 지속적 개선을 통해 다음 단계로의 진화 기대.
        </div>
        {_footer(name, 6, 8)}
      </div>
    </div>'''


def slide_risk_limitations(d: dict) -> str:
    """Slide 7: Risk bubble chart + full risk details + severity distribution KPI + mitigation banner."""
    name = d.get('project_name', 'Project')
    risks = d.get('risks', [])
    risk_mitigation = d.get('risk_mitigation', '')

    # Risk bubble chart
    risk_b64 = _make_risk_bubble(risks, 'Risk Matrix: Probability vs Impact', 480, 300) if HAS_PLOTLY else ''

    # Risk list with full descriptions and severity
    risk_html = ''
    sev_colors = {'high': '#E65100', 'medium': THEME['gold'], 'low': THEME['green']}
    critical_count = 0
    high_count = 0
    medium_count = 0

    for r in risks[:5]:
        r_name = r.get('name', '')
        r_desc = r.get('description', '')
        r_severity = r.get('severity', 'medium')
        r_probability = r.get('probability', 0)
        r_impact = r.get('impact', 0)
        r_color = sev_colors.get(r_severity, THEME['gold'])

        # Count severity levels
        if r_severity == 'high':
            high_count += 1
        elif r_severity == 'medium':
            medium_count += 1

        risk_score = r_probability * r_impact if r_probability and r_impact else 0

        risk_html += f'''<div style="margin-bottom:12px;padding:12px;background:{THEME['bg_alt']};border-left:4px solid {r_color};border-radius:2px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
            <div style="font-weight:700;color:{THEME['text']};flex:1;">{r_name}</div>
            <span style="background:{r_color};color:#FFF;padding:3px 10px;border-radius:3px;font-size:10px;font-weight:700;white-space:nowrap;margin-left:8px;">{r_severity.upper()}</span>
          </div>
          <div style="font-size:11px;color:{THEME['text_mid']};line-height:1.4;margin-bottom:4px;">{r_desc}</div>
          {f'<div style="font-size:10px;color:{THEME["text_muted"]};margin-top:4px;">P×I Score: {risk_score:.1f}</div>' if risk_score else ''}
        </div>'''

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">리스크 및 한계 평가</div>
        <div class="section-subtitle">Risk & Limitations Assessment</div>
        <div class="two-col" style="flex:1;min-height:0;gap:16px;margin-bottom:12px;">
          <div class="chart-container" style="height:300px;">
            {_img_tag(risk_b64, 'Risk Matrix') if risk_b64 else '<div>Chart unavailable</div>'}
          </div>
          <div class="card" style="padding:16px;overflow-y:auto;flex:1;">
            <h4 style="font-size:13px;font-weight:700;color:{THEME['gold']};letter-spacing:0.5px;margin-bottom:12px;">IDENTIFIED RISKS (상세 분석)</h4>
            {risk_html}
          </div>
        </div>
        <div style="display:flex;gap:12px;height:90px;margin-bottom:12px;">
          <div class="card" style="flex:1;padding:14px;text-align:center;background:#FFEBEE;border-color:#E65100;">
            <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:6px;">CRITICAL RISKS</div>
            <div style="font-size:36px;font-weight:900;color:#E65100;">{critical_count}</div>
            <div style="font-size:11px;color:{THEME['text_mid']};">Highest priority</div>
          </div>
          <div class="card" style="flex:1;padding:14px;text-align:center;background:{THEME['gold_bg']};border-color:{THEME['gold']};">
            <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:6px;">HIGH RISKS</div>
            <div style="font-size:36px;font-weight:900;color:{THEME['gold']};">{high_count}</div>
            <div style="font-size:11px;color:{THEME['text_mid']};">Immediate action</div>
          </div>
          <div class="card" style="flex:1;padding:14px;text-align:center;background:#FFF3E0;border-color:#FF6F00;">
            <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:0.5px;margin-bottom:6px;">MEDIUM RISKS</div>
            <div style="font-size:36px;font-weight:900;color:#FF6F00;">{medium_count}</div>
            <div style="font-size:11px;color:{THEME['text_mid']};">Monitor & plan</div>
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:12px;">
          <strong>완화 전략:</strong> {risk_mitigation or '지속적인 거버넌스 탈중앙화, 보안 감시 강화, 생태계 파트너십 다양화를 통해 주요 리스크 관리.'}
        </div>
        {_footer(name, 7, 8)}
      </div>
    </div>'''


def slide_final_assessment(d: dict) -> str:
    """Slide 8: Maturity gauge + colored objective scores + monitoring checklist + investment thesis."""
    name = d.get('project_name', 'Project')
    score = d.get('total_maturity_score', 0)
    stage = d.get('maturity_stage', 'growing')
    objectives = d.get('strategic_objectives', [])
    checklist = d.get('monitoring_checklist', [])
    investment_thesis = d.get('investment_thesis', '')

    # Gauge chart
    gauge_b64 = _make_gauge(score, 100, 'Maturity Score', 340, 280) if HAS_PLOTLY else ''

    # Objective scores with colored bars
    score_items = ''
    for obj in objectives[:5]:
        obj_name = obj.get('short_name', obj.get('name', ''))[:16]
        weighted = obj.get('weighted_score', 0)
        achievement = obj.get('achievement_rate', 0)
        bar_color = THEME['green'] if achievement >= 80 else THEME['gold'] if achievement >= 60 else THEME['red']

        score_items += f'''<div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;font-weight:600;">
            <span>{obj_name}</span><span style="color:{bar_color};font-weight:700;">{weighted:.1f}</span>
          </div>
          <div style="height:6px;background:{THEME['border_light']};border-radius:3px;overflow:hidden;">
            <div style="height:100%;width:{min(weighted / 10 * 100, 100):.0f}%;background:{bar_color};border-radius:3px;"></div>
          </div>
        </div>'''

    # Enhanced Checklist with more items (4-5)
    checklist_html = ''
    checklist_items = checklist if isinstance(checklist, list) else [checklist] if checklist else []

    # Provide default checklist if none provided
    if not checklist_items:
        checklist_items = [
            'Regular security audits and smart contract reviews',
            'Governance token distribution monitoring',
            'Cross-chain interoperability validation',
            'Community engagement and developer ecosystem growth',
            'Regulatory compliance and market readiness assessment'
        ]

    for idx, item in enumerate(checklist_items[:5], 1):
        checklist_html += f'''<li style="margin-bottom:10px;font-size:12px;line-height:1.5;padding-left:8px;">
          <strong style="color:{THEME['gold']};">{idx}.</strong> {item}
        </li>'''

    stage_color = THEME['green'] if score >= 80 else THEME['gold'] if score >= 60 else THEME['red']
    stage_badge_color = THEME['green'] if score >= 80 else THEME['gold'] if score >= 60 else THEME['red']

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">최종 평가 및 전망</div>
        <div class="section-subtitle">Final Assessment & Outlook</div>
        <div style="flex:1;display:flex;gap:16px;min-height:0;margin-bottom:12px;">
          <div class="chart-container" style="flex:0.45;height:300px;">
            {_img_tag(gauge_b64, 'Maturity Gauge') if gauge_b64 else '<div>Chart unavailable</div>'}
          </div>
          <div style="flex:1;display:flex;flex-direction:column;gap:12px;">
            <div class="card" style="padding:14px;flex:1;">
              <h4 style="font-size:12px;font-weight:700;color:{THEME['gold']};letter-spacing:0.5px;margin-bottom:10px;">OBJECTIVE SCORES (색상 표시)</h4>
              {score_items}
            </div>
            <div class="card" style="padding:14px;flex:1;overflow-y:auto;">
              <h4 style="font-size:12px;font-weight:700;color:{THEME['gold']};letter-spacing:0.5px;margin-bottom:10px;">MONITORING CHECKLIST (5항목)</h4>
              <ul class="bullet-list" style="margin:0;padding-left:12px;">
                {checklist_html}
              </ul>
            </div>
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:12px;background:linear-gradient(90deg,{stage_badge_color}12,{stage_badge_color}08);border-left:4px solid {stage_badge_color};">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="background:{stage_badge_color};color:#FFF;padding:10px 16px;border-radius:4px;font-size:14px;font-weight:900;white-space:nowrap;">
              {stage.upper()} STAGE
            </div>
            <div style="font-size:13px;line-height:1.5;">
              <strong>성숙도 점수: {score:.1f}%</strong> — {investment_thesis[:140]}
            </div>
          </div>
        </div>
        {_footer(name, 8, 8)}
      </div>
    </div>'''


# ═══════════════════════════════════════════════════════════════
#  HTML GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_html_mat(project_data: dict) -> str:
    """Generate complete HTML document with all MAT slides."""
    html_lang = project_data.get('lang', 'en')
    slides = [
        slide_cover_mat(project_data),
        slide_executive_summary_mat(project_data),
        slide_objectives_assessment(project_data),
        slide_architecture_panel(project_data),
        slide_timeline_milestones(project_data),
        slide_goal_achievement(project_data),
        slide_risk_limitations(project_data),
        slide_final_assessment(project_data),
    ]

    html = f'''<!DOCTYPE html>
<html lang="{html_lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1280">
  <title>{project_data.get('project_name', 'Report')} - Maturity Report</title>
  <style>{CSS}</style>
</head>
<body>
{''.join(slides)}
</body>
</html>'''
    return html


# ═══════════════════════════════════════════════════════════════
#  PDF CONVERSION (IDENTICAL TO ECON)
# ═══════════════════════════════════════════════════════════════

def html_to_pdf(html: str, output_path: str) -> str:
    """Convert HTML string to PDF using Playwright headless Chromium."""
    from playwright.sync_api import sync_playwright

    with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
        f.write(html)
        tmp_html = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1280, 'height': 720})
            page.goto(f'file://{tmp_html}', wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            page.pdf(
                path=output_path,
                width='1280px',
                height='720px',
                print_background=True,
                margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
            )
            browser.close()
    finally:
        os.unlink(tmp_html)

    return output_path


# ═══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def generate_slide_mat(project_data: dict, output_dir: str = '/tmp') -> Tuple[str, dict]:
    """
    Main entry: generate high-quality MAT slide PDF.
    Returns (pdf_path, metadata).
    """
    slug = project_data.get('slug', project_data.get('project_name', 'project').lower().replace(' ', '_'))
    version = project_data.get('version', 1)
    lang = project_data.get('lang', 'en')

    filename = f'{slug}_mat_slide_v{version}_{lang}.pdf'
    pdf_path = os.path.join(output_dir, filename)

    html = generate_html_mat(project_data)
    html_to_pdf(html, pdf_path)

    metadata = {
        'path': pdf_path,
        'filename': filename,
        'slides': 8,
        'format': 'slide_html',
        'theme': 'beige_gold',
        'renderer': 'playwright_chromium',
        'resolution': '1280x720',
        'report_type': 'maturity',
    }

    return pdf_path, metadata


# ═══════════════════════════════════════════════════════════════
#  TEST  –  run with: python gen_slide_html_mat.py
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    sample_data = {
        'project_name': 'HeyElsa AI',
        'token_symbol': 'ELSA',
        'slug': 'heyelsaai',
        'version': 1,
        'lang': 'en',
        'total_maturity_score': 80.25,
        'maturity_stage': 'mature',
        'executive_summary': 'AI 에이전트 경제 인프라 프로젝트로서 높은 성숙도(80.25%)를 달성. 기술적 실행력과 생태계 확장에서 강점을 보이나, 거버넌스 탈중앙화가 향후 과제.',
        'project_identity': ['AI 에이전트 플랫폼', 'DeFi 실행 계층', '인텐트 기반 UX'],
        'strategic_objectives': [
            {'name': 'AI 엔진 및 인텐트 실행', 'short_name': 'AI Engine', 'weight': 35.0, 'achievement_rate': 85.0, 'weighted_score': 29.75, 'description': '자연어 기반 실질적 트랜잭션 실행 기능은 안정적'},
            {'name': '멀티체인 & MPC 인프라', 'short_name': 'Multi-Chain', 'weight': 20.0, 'achievement_rate': 90.0, 'weighted_score': 18.0, 'description': 'Base, Solana, Ethereum 등 8개 이상 네트워크 통합'},
            {'name': '$ELSA 토큰 이코노미', 'short_name': 'Token Econ', 'weight': 20.0, 'achievement_rate': 75.0, 'weighted_score': 15.0, 'description': '디플레이션 메커니즘을 통한 프로젝트 경제적 자립도'},
            {'name': '에이전트 생태계(AgentOS)', 'short_name': 'AgentOS', 'weight': 15.0, 'achievement_rate': 70.0, 'weighted_score': 10.5, 'description': 'B2B 확장성 및 개발자 지원을 통한 Web3 실행 레이어화'},
            {'name': '글로벌 시장 & 규제 준수', 'short_name': 'Compliance', 'weight': 10.0, 'achievement_rate': 70.0, 'weighted_score': 7.0, 'description': '대중적 채택을 위한 제도적 신뢰 확보'},
        ],
        'architecture': {
            'onchain_percentage': 55.0,
            'offchain_percentage': 45.0,
            'onchain_components': ['가치 이전 엔진: 스마트 컨트랙트 기반 트랜잭션', '보안 인프라: MPC 지갑 암호학적 서명', 'M2M 경제 레이어: x402 마이크로페이먼트'],
            'offchain_components': ['LLM & NLP 엔진: DeepSeek, LLaMA 기반', 'AI 플래너: STRIPS형 알고리즘', '외부 데이터 연동: Zerion API'],
        },
        'timeline_milestones': [
            {'name': '시드 투자 유치 ($3M)', 'date': '2024 Q2', 'status': 'completed'},
            {'name': 'Intro Quest 런칭', 'date': '2024 Q4', 'status': 'completed'},
            {'name': 'TGE 실행', 'date': '2026 Q1', 'status': 'completed'},
            {'name': 'AgentOS 정식 출시', 'date': '2026 Q3', 'status': 'planned'},
            {'name': 'B2B 전환', 'date': '2027 Q1', 'status': 'planned'},
        ],
        'risks': [
            {'name': 'Governance Centralization', 'description': '96% 홀더 집중도의 분산화 지연', 'probability': 3, 'impact': 4, 'severity': 'high'},
            {'name': 'AI Bias Risk', 'description': 'ERC-8004 검증 시스템의 실효성 미검증', 'probability': 2, 'impact': 4, 'severity': 'high'},
            {'name': 'Multi-Chain Complexity', 'description': '타 L2 확장 시 가치 포착 역량 미증명', 'probability': 3, 'impact': 3, 'severity': 'medium'},
        ],
        'monitoring_checklist': [
            '공급 집중도 해소: 96% 홀더 집중도의 분산화 이행 스케줄 확인',
            'AI 편향성 방어 시스템: ERC-8004 검증 실효성',
            '네트워크 효과 이식 여부: 타 L2 확장 시 가치 포착 역량 증명',
        ],
        'investment_thesis': '기술 실행력(85%)과 인프라 성숙도(90%)에서 업계 상위 수준을 달성했으나, 거버넌스 탈중앙화(70%)가 최대 과제로 남아 있음.',
    }

    print("Generating Maturity Report HTML slides...")
    pdf_path, meta = generate_slide_mat(sample_data, '/tmp')
    print(f"✓ Slide PDF: {pdf_path}")
    print(f"✓ Slides: {meta['slides']}")
    print(f"✓ Theme: {meta['theme']}")
    print(f"✓ Renderer: {meta['renderer']}")
    print(f"✓ Size: {os.path.getsize(pdf_path):,} bytes")
