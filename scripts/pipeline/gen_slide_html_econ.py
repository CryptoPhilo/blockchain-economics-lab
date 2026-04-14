#!/usr/bin/env python3
"""
gen_slide_html_econ.py – High-quality HTML→PDF slide generator for ECON reports.

Produces 16:9 landscape infographic PDF matching BCE Lab's beige+gold design.
Uses Playwright (headless Chromium) for pixel-perfect rendering.

MAJOR QUALITY UPGRADES:
- Typography: 42-48px titles, 16-18px body text (was 32px and 11-13px)
- Card styling: 2-3px borders, deep shadows, 24-32px padding, 6-8px radius
- Cover slide: Large isometric SVG hero illustration with blockchain nodes
- Pillar cards: 3D pedestal-style with colored icons, 200px height, 64px icons
- Table styling: 2px borders, 18-24px padding, colored column headers
- Dark header bars: Full-width, 40-50px height, gold badges
- Conclusion banners: Full-width, 14-16px text, prominent styling
- Flow arrows: 3D-style, thick strokes, gradient fills
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

# ── Matplotlib (reliable Korean font rendering) ─────────────
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    import numpy as np
    _FONTS_DIR = Path(__file__).parent / 'fonts'
    _KR_FONT_PATH = _FONTS_DIR / 'NotoSansKR-Regular.ttf'
    _KR_FONT_BOLD_PATH = _FONTS_DIR / 'NotoSansKR-Bold.ttf'
    if _KR_FONT_PATH.exists():
        _KR_FONT = FontProperties(fname=str(_KR_FONT_PATH))
        _KR_FONT_BOLD = FontProperties(fname=str(_KR_FONT_BOLD_PATH)) if _KR_FONT_BOLD_PATH.exists() else _KR_FONT
    else:
        _KR_FONT = FontProperties()
        _KR_FONT_BOLD = FontProperties()
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

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
#  CSS TEMPLATE - SIGNIFICANTLY UPGRADED
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
#  HERO SVG ILLUSTRATION - Isometric Blockchain
# ═══════════════════════════════════════════════════════════════

def _hero_illustration() -> str:
    """Large isometric 3D blockchain/gear illustration for cover slide – matching NotebookLM sample style."""
    g = THEME['gold']
    d = THEME['dark']
    return f'''<svg style="position:absolute;top:42%;left:52%;transform:translate(-50%,-50%);width:750px;height:580px;" viewBox="0 0 750 580" xmlns="http://www.w3.org/2000/svg">

      <!-- ===== LARGE ISOMETRIC CUBE (center) ===== -->
      <g transform="translate(320,220)" opacity="0.14">
        <!-- Front face -->
        <polygon points="0,0 120,-70 120,80 0,150" fill="none" stroke="{d}" stroke-width="2.5"/>
        <!-- Top face -->
        <polygon points="0,0 120,-70 240,0 120,70" fill="none" stroke="{d}" stroke-width="2.5"/>
        <!-- Right face -->
        <polygon points="120,70 240,0 240,150 120,220" fill="none" stroke="{d}" stroke-width="1.5" stroke-dasharray="4,3"/>
        <!-- Internal structure lines -->
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
        <!-- 8 gear teeth -->
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
        <!-- Main horizontal trace -->
        <path d="M80,300 L200,300 L230,270 L380,270 L410,300 L550,300" stroke="{d}" stroke-width="2" fill="none"/>
        <!-- Vertical branches -->
        <path d="M230,270 L230,200" stroke="{d}" stroke-width="1.5" fill="none"/>
        <path d="M380,270 L380,200 L420,180" stroke="{d}" stroke-width="1.5" fill="none"/>
        <path d="M300,300 L300,350 L350,380" stroke="{d}" stroke-width="1.5" fill="none"/>
        <!-- Horizontal upper trace -->
        <path d="M180,170 L250,170 L280,140 L450,140 L500,170 L580,170" stroke="{d}" stroke-width="1.5" fill="none"/>
        <!-- Diagonal connections -->
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
#  SVG ICONS  (inline, no external deps) – UPGRADED
# ═══════════════════════════════════════════════════════════════

ICONS = {
    'gear': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="32" cy="32" r="14" stroke="#B8860B" stroke-width="3" fill="none"/>
      <path d="M32 2v10M32 52v10M2 32h10M52 32h10M10 10l7 7M47 47l7 7M10 54l7-7M47 17l7-7" stroke="#B8860B" stroke-width="2.5" stroke-linecap="round"/>
      <circle cx="32" cy="32" r="6" fill="#B8860B"/>
    </svg>''',
    'money': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="4" y="14" width="56" height="36" rx="4" stroke="#B8860B" stroke-width="3" fill="none"/>
      <circle cx="32" cy="32" r="11" stroke="#B8860B" stroke-width="2.5" fill="none"/>
      <path d="M28 32h8M32 28v8" stroke="#B8860B" stroke-width="2.5" stroke-linecap="round"/>
    </svg>''',
    'shield': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M32 4L6 16v16c0 15 10 24 26 28 16-4 26-13 26-28V16L32 4z" stroke="#B8860B" stroke-width="3" fill="none"/>
      <path d="M24 32l6 6 10-10" stroke="#B8860B" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',
    'id_card': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="4" y="8" width="56" height="48" rx="4" stroke="#B8860B" stroke-width="3" fill="none"/>
      <circle cx="22" cy="28" r="7" stroke="#B8860B" stroke-width="2.5" fill="none"/>
      <path d="M10 48c0-6 5-10 12-10s12 4 12 10" stroke="#B8860B" stroke-width="2.5" fill="none"/>
      <line x1="42" y1="20" x2="56" y2="20" stroke="#B8860B" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="42" y1="28" x2="56" y2="28" stroke="#B8860B" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="42" y1="36" x2="54" y2="36" stroke="#B8860B" stroke-width="2.5" stroke-linecap="round"/>
    </svg>''',
    'lock': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="12" y="28" width="40" height="28" rx="4" stroke="#B8860B" stroke-width="3" fill="none"/>
      <path d="M20 28V18a12 12 0 0124 0v10" stroke="#B8860B" stroke-width="3" fill="none"/>
      <circle cx="32" cy="42" r="4" fill="#B8860B"/>
    </svg>''',
    'chart': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="8" y="36" width="12" height="20" rx="1.5" fill="#B8860B" opacity="0.5"/>
      <rect x="28" y="22" width="12" height="34" rx="1.5" fill="#B8860B" opacity="0.75"/>
      <rect x="48" y="8" width="12" height="48" rx="1.5" fill="#B8860B"/>
      <line x1="4" y1="58" x2="60" y2="58" stroke="#B8860B" stroke-width="2.5"/>
    </svg>''',
    'network': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="32" cy="32" r="8" stroke="#B8860B" stroke-width="2" fill="none"/>
      <circle cx="12" cy="12" r="6" stroke="#B8860B" stroke-width="2" fill="none"/>
      <circle cx="52" cy="12" r="6" stroke="#B8860B" stroke-width="2" fill="none"/>
      <circle cx="12" cy="52" r="6" stroke="#B8860B" stroke-width="2" fill="none"/>
      <circle cx="52" cy="52" r="6" stroke="#B8860B" stroke-width="2" fill="none"/>
      <line x1="24" y1="24" x2="17" y2="18" stroke="#B8860B" stroke-width="2"/>
      <line x1="40" y1="24" x2="47" y2="18" stroke="#B8860B" stroke-width="2"/>
      <line x1="24" y1="40" x2="17" y2="46" stroke="#B8860B" stroke-width="2"/>
      <line x1="40" y1="40" x2="47" y2="46" stroke="#B8860B" stroke-width="2"/>
    </svg>''',
    'warning': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M32 4L4 56h56L32 4z" stroke="#C62828" stroke-width="3" fill="none"/>
      <line x1="32" y1="22" x2="32" y2="40" stroke="#C62828" stroke-width="3.5" stroke-linecap="round"/>
      <circle cx="32" cy="48" r="2.5" fill="#C62828"/>
    </svg>''',
}


# ═══════════════════════════════════════════════════════════════
#  CHART HELPERS  –  matplotlib → base64 PNG (Korean font safe)
# ═══════════════════════════════════════════════════════════════

def _mpl_font(size=12, bold=False):
    """Return FontProperties copy with given size (Korean-safe)."""
    if not HAS_MPL:
        return {}
    base = _KR_FONT_BOLD if bold else _KR_FONT
    fp = base.copy()
    fp.set_size(size)
    return fp


def _mpl_to_b64(fig, dpi=200) -> str:
    """Render matplotlib figure to base64 PNG string with transparent bg."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                transparent=True, facecolor='none', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode()


def _chart_to_b64(fig_or_go, width=500, height=350) -> str:
    """Render Plotly figure to base64 PNG (fallback, non-Korean charts only)."""
    fig = fig_or_go
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Noto Sans KR, Helvetica, Arial, sans-serif', size=12, color=THEME['text']),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    buf = io.BytesIO()
    try:
        fig.write_image(buf, format='png', width=width, height=height, scale=3)
    except Exception:
        fig.write_image(buf, format='png', width=width, height=height)
    return base64.b64encode(buf.getvalue()).decode()


def _make_donut_chart(labels, values, title='', width=420, height=350) -> str:
    """Donut chart with Korean labels using matplotlib."""
    if HAS_MPL:
        colors = CHART_COLORS[:len(labels)]
        fig, ax = plt.subplots(figsize=(width/100, height/100))
        fig.patch.set_alpha(0)
        wedges, texts, autotexts = ax.pie(
            values, labels=None, colors=colors, autopct='%1.1f%%',
            startangle=90, pctdistance=0.78,
            wedgeprops=dict(width=0.45, edgecolor=THEME['bg'], linewidth=2),
        )
        for t in autotexts:
            t.set_fontproperties(_mpl_font(10))
            t.set_color('#FFFFFF')
            t.set_fontweight('bold')
        # Add labels outside
        for i, (wedge, label) in enumerate(zip(wedges, labels)):
            ang = (wedge.theta2 + wedge.theta1) / 2
            x = np.cos(np.radians(ang))
            y = np.sin(np.radians(ang))
            ha = 'left' if x > 0 else 'right'
            ax.annotate(label, xy=(0.78*x, 0.78*y), xytext=(1.25*x, 1.15*y),
                       fontproperties=_mpl_font(11),
                       ha=ha, va='center', color=THEME['text'],
                       arrowprops=dict(arrowstyle='-', color=THEME['text_muted'], lw=0.8))
        if title:
            ax.set_title(title, fontproperties=_mpl_font(14, bold=True),
                        color=THEME['text'], pad=12)
        ax.set_aspect('equal')
        return _mpl_to_b64(fig)
    else:
        # Plotly fallback
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
    """Radar/spider chart with Korean labels using matplotlib."""
    if HAS_MPL:
        N = len(categories)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]
        vals = list(values) + [values[0]]

        fig, ax = plt.subplots(figsize=(width/100, height/100), subplot_kw=dict(polar=True))
        fig.patch.set_alpha(0)
        ax.set_facecolor('none')

        # Draw the polygon
        ax.fill(angles, vals, color=THEME['gold'], alpha=0.2)
        ax.plot(angles, vals, color=THEME['gold'], linewidth=2.5)
        ax.scatter(angles[:-1], values, color=THEME['gold'], s=60, zorder=5)

        # Set radial axis
        ax.set_ylim(0, max_val)
        ax.set_yticks([max_val*0.25, max_val*0.5, max_val*0.75, max_val])
        for label in ax.get_yticklabels():
            label.set_fontproperties(_mpl_font(9))
            label.set_color(THEME['text_muted'])
        ax.yaxis.grid(True, color=THEME['border_light'], linewidth=0.8)
        ax.xaxis.grid(True, color=THEME['border_light'], linewidth=0.8)

        # Set angular labels with scores
        ax.set_xticks(angles[:-1])
        labeled = [f'{c}\n({v:.0f}/{max_val})' for c, v in zip(categories, values)]
        ax.set_xticklabels(labeled)
        for label in ax.get_xticklabels():
            label.set_fontproperties(_mpl_font(11))
            label.set_color(THEME['text'])

        if title:
            ax.set_title(title, fontproperties=_mpl_font(14, bold=True),
                        color=THEME['text'], pad=20)
        return _mpl_to_b64(fig)
    else:
        # Plotly fallback
        labeled = [f'{c}\n({v:.0f}/{max_val})' for c, v in zip(categories, values)]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]], theta=labeled + [labeled[0]],
            fill='toself', fillcolor='rgba(184,134,11,0.2)',
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
    """Bar chart with Korean labels using matplotlib."""
    if HAS_MPL:
        colors = CHART_COLORS[:len(labels)]
        fig, ax = plt.subplots(figsize=(width/100, height/100))
        fig.patch.set_alpha(0)
        ax.set_facecolor('none')

        if horizontal:
            y_pos = range(len(labels))
            bars = ax.barh(y_pos, values, color=colors, edgecolor='none', height=0.6)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels)
            for label in ax.get_yticklabels():
                label.set_fontproperties(_mpl_font(11))
                label.set_color(THEME['text'])
            for bar, val in zip(bars, values):
                ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                       f'{val}', va='center', fontproperties=_mpl_font(11),
                       color=THEME['text'])
        else:
            x_pos = range(len(labels))
            bars = ax.bar(x_pos, values, color=colors, edgecolor='none', width=0.6)
            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels)
            for label in ax.get_xticklabels():
                label.set_fontproperties(_mpl_font(11))
                label.set_color(THEME['text'])
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                       f'{val}', ha='center', fontproperties=_mpl_font(11),
                       color=THEME['text'])

        ax.yaxis.grid(True, color=THEME['border_light'], linewidth=0.8, alpha=0.5)
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(THEME['border_light'])
        ax.spines['bottom'].set_color(THEME['border_light'])
        for label in ax.get_yticklabels():
            label.set_fontproperties(_mpl_font(10))
            label.set_color(THEME['text_muted'])

        if title:
            ax.set_title(title, fontproperties=_mpl_font(14, bold=True),
                        color=THEME['text'], pad=12)
        return _mpl_to_b64(fig)
    else:
        # Plotly fallback
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
    """Risk matrix bubble chart with Korean labels using matplotlib."""
    if HAS_MPL:
        sev_colors = {'critical': THEME['red'], 'high': '#E65100',
                      'medium': THEME['gold'], 'low': THEME['green']}
        fig, ax = plt.subplots(figsize=(width/100, height/100))
        fig.patch.set_alpha(0)
        ax.set_facecolor('none')

        # Quadrant shading (high-risk zone)
        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((3, 3), 3, 3, facecolor=(198/255, 40/255, 40/255, 0.08),
                               edgecolor='none', zorder=0))

        text_offsets = [(0, 12), (0, -14), (8, 10), (-8, -14), (-8, 10), (8, -14)]
        for i, r in enumerate(risks):
            x = r.get('probability', 3)
            y = r.get('impact', 3)
            sev = r.get('severity', 'medium')
            color = sev_colors.get(sev, THEME['gold'])
            size = r.get('impact', 3) * 120

            ax.scatter(x, y, s=size, c=color, alpha=0.75,
                      edgecolors='#FFFFFF', linewidths=2, zorder=3)

            ox, oy = text_offsets[i % len(text_offsets)]
            name = r.get('name', '')[:16]
            ax.annotate(name, (x, y), textcoords='offset points', xytext=(ox, oy),
                       fontproperties=_mpl_font(10), color=THEME['text'],
                       ha='center', va='center', zorder=4)

        ax.set_xlim(0, 6)
        ax.set_ylim(0, 6)
        ax.set_xlabel('Probability', fontproperties=_mpl_font(11),
                     color=THEME['text_muted'])
        ax.set_ylabel('Impact', fontproperties=_mpl_font(11),
                     color=THEME['text_muted'])
        ax.xaxis.grid(True, color=THEME['border_light'], linewidth=0.8, alpha=0.5)
        ax.yaxis.grid(True, color=THEME['border_light'], linewidth=0.8, alpha=0.5)
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(THEME['border_light'])
        ax.spines['bottom'].set_color(THEME['border_light'])
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontproperties(_mpl_font(10))
            label.set_color(THEME['text_muted'])

        if title:
            ax.set_title(title, fontproperties=_mpl_font(14, bold=True),
                        color=THEME['text'], pad=12)
        return _mpl_to_b64(fig)
    else:
        # Plotly fallback
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
            xaxis=dict(title='Probability →', range=[0, 6], showgrid=True,
                      gridcolor=THEME['border_light']),
            yaxis=dict(title='Impact ↑', range=[0, 6], showgrid=True,
                      gridcolor=THEME['border_light']),
            width=width, height=height,
        )
        fig.add_shape(type='rect', x0=3, y0=3, x1=6, y1=6,
                      fillcolor='rgba(198,40,40,0.08)', line_width=0)
        return _chart_to_b64(fig, width, height)


def _make_gauge(value, max_val=100, title='', width=320, height=250) -> str:
    """Gauge chart – uses matplotlib arc for Korean text support."""
    if HAS_MPL:
        from matplotlib.patches import Arc, FancyArrowPatch
        fig, ax = plt.subplots(figsize=(width/100, height/100))
        fig.patch.set_alpha(0)
        ax.set_facecolor('none')

        # Draw gauge arc segments
        import matplotlib.colors as mcolors
        segments = [
            (0, 60, 'rgba(198,40,40,0.25)'),
            (60, 126, 'rgba(184,134,11,0.20)'),
            (126, 180, 'rgba(46,125,50,0.20)'),
        ]
        for start, end, color in segments:
            arc = Arc((0.5, 0), 0.8, 0.8, angle=0, theta1=start, theta2=end,
                     color=THEME['border_light'], linewidth=20, zorder=1)
            ax.add_patch(arc)

        # Needle
        frac = value / max_val
        angle = np.pi * (1 - frac)
        nx = 0.5 + 0.35 * np.cos(angle)
        ny = 0.35 * np.sin(angle)
        ax.annotate('', xy=(nx, ny), xytext=(0.5, 0),
                    arrowprops=dict(arrowstyle='->', color=THEME['gold'], lw=2.5))

        # Value text
        ax.text(0.5, -0.08, f'{value}', ha='center', va='center',
               fontproperties=_mpl_font(22, bold=True), color=THEME['text'])
        if title:
            ax.text(0.5, -0.22, title, ha='center', va='center',
                   fontproperties=_mpl_font(11), color=THEME['text_muted'])

        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.35, 0.55)
        ax.set_aspect('equal')
        ax.axis('off')
        return _mpl_to_b64(fig)
    else:
        # Plotly fallback
        fig = go.Figure(go.Indicator(
            mode='gauge+number', value=value,
            title=dict(text=title, font=dict(size=14)),
            gauge=dict(
                axis=dict(range=[0, max_val], tickwidth=1, tickcolor=THEME['text_muted']),
                bar=dict(color=THEME['gold']),
                bgcolor=THEME['bg_alt'], bordercolor=THEME['border'],
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


def _icon_html(name: str, size: int = 48) -> str:
    svg = ICONS.get(name, '')
    return f'<div class="icon" style="width:{size}px;height:{size}px;">{svg}</div>'


def _img_tag(b64: str, alt: str = '', style: str = '') -> str:
    return f'<img src="data:image/png;base64,{b64}" alt="{alt}" style="{style}"/>'


# ═══════════════════════════════════════════════════════════════
#  SLIDE GENERATORS - COMPLETELY REWRITTEN WITH QUALITY IMPROVEMENTS
# ═══════════════════════════════════════════════════════════════

def slide_cover(d: dict) -> str:
    """Slide 1: Full cover with hero SVG + large typography + KPI metrics."""
    name = d.get('project_name', 'Project')
    symbol = d.get('token_symbol', 'TOKEN')
    rating = d.get('overall_rating', 'B+')
    subtitle = d.get('report_subtitle', f'{name} (${{symbol}}) 크립토 경제 설계 분석')
    date_str = datetime.now().strftime('%Y. %m.')

    # Get market data for KPI metrics
    market_data = d.get('market_data', {})
    price = market_data.get('price', '$0.00')
    market_cap = market_data.get('market_cap', 'N/A')
    volume = market_data.get('volume_24h', 'N/A')
    chain = d.get('chain', 'EVM')

    # Rating color
    rc = THEME['green'] if rating in ('S','A','A+','A-') else THEME['gold'] if rating.startswith('B') else THEME['red']

    # Executive summary for cover
    summary = d.get('executive_summary', '')
    summary_text = summary[:150] if summary else f'{name} 크립토 경제 설계 분석 보고서'

    # Build Korean cover title (sample-matching: large centered title)
    cover_title = d.get('cover_title', f'AI 에이전트 경제 인프라의\n설계와 지속 가능성 분석')
    cover_subtitle = d.get('cover_subtitle', f'{name} ({symbol}) 프로젝트 심층 해부: 인텐트(Intent) 기반 매칭부터 중앙화 리스크까지')

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      {_hero_illustration()}
      <div class="slide-content" style="padding:28px 80px; position:relative; z-index:1;">
        {_header_bar()}
        <!-- Large centered Korean title (matching sample) -->
        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;position:relative;">
          <h1 style="font-size:68px;font-weight:900;line-height:1.25;margin-bottom:20px;letter-spacing:-1px;max-width:1000px;">{cover_title.replace(chr(10), '<br/>')}</h1>
          <p style="font-size:20px;color:{THEME['text_mid']};max-width:800px;line-height:1.7;font-weight:500;">
            {cover_subtitle}
          </p>
          <div style="margin-top:16px;width:140px;height:4px;background:linear-gradient(90deg,{THEME['gold']},{THEME['gold_light']});border-radius:2px;"></div>
        </div>
        <!-- Bottom row: badges + rating -->
        <div style="display:flex;justify-content:space-between;align-items:flex-end;">
          <div>
            <span class="gold-label" style="font-size:14px;padding:8px 20px;">Report Published: {date_str}</span>
            <span class="gold-label" style="margin-left:10px;font-size:14px;padding:8px 20px;">Target Network: {chain}</span>
          </div>
          <div style="text-align:center;">
            <div class="rating-circle" style="background:{rc};width:80px;height:80px;font-size:28px;">{rating}</div>
            <div style="font-size:9px;color:{THEME['text_muted']};font-weight:700;letter-spacing:2px;margin-top:4px;">RATING</div>
          </div>
        </div>
      </div>
    </div>'''


def slide_executive_summary(d: dict) -> str:
    """Slide 2: Executive overview with 3-column key facts + expanded tech details."""
    name = d.get('project_name', 'Project')
    summary = d.get('executive_summary', '')
    identity = d.get('project_identity', [])
    tech_stack = d.get('core_tech_stack', [])
    chain_info = d.get('chain_info', {})
    pillars = d.get('tech_pillars', [])
    rating = d.get('overall_rating', 'N/A')

    # Left column items
    id_items = ''
    for item in (identity if isinstance(identity, list) else [identity])[:4]:
        id_items += f'<li>{item}</li>'

    # Pillar score bars for left column (fill vertical space)
    pillar_bars = ''
    for p in pillars[:4]:
        p_name = p.get('short_name', p.get('name', ''))[:12]
        p_score = p.get('score', 0)
        bar_color = THEME['gold'] if p_score >= 75 else THEME['blue'] if p_score >= 60 else THEME['red']
        pillar_bars += f'''<div style="margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px;font-weight:600;">
            <span>{p_name}</span><span style="color:{bar_color};font-weight:700;">{p_score}/100</span>
          </div>
          <div style="height:10px;background:{THEME['border_light']};border-radius:4px;overflow:hidden;box-shadow:inset 0 1px 2px rgba(0,0,0,0.05);">
            <div style="height:100%;width:{p_score}%;background:linear-gradient(90deg,{bar_color},{THEME['gold_light']});border-radius:4px;"></div>
          </div>
        </div>'''

    # Middle column items with descriptions
    tech_items = ''
    for i, item in enumerate(tech_stack[:4], 1):
        if isinstance(item, dict):
            name_t = item.get('name', '')
            desc_t = item.get('description', '')
        else:
            name_t = str(item)
            desc_t = ''
        desc_html = f'<div style="font-size:12px;color:{THEME["text_muted"]};margin-top:3px;">{desc_t[:60]}</div>' if desc_t else ''
        tech_items += f'''<div style="background:{THEME['surface']};border:2px solid {THEME['border']};padding:12px 16px;margin-bottom:8px;border-radius:4px;font-size:14px;font-weight:600;"><strong>{i}. {name_t}</strong>{desc_html}</div>'''

    # Right column
    chain = d.get('chain', 'Base L2')
    consensus = chain_info.get('consensus', 'Optimistic Rollup')
    contract = d.get('contract_address', '')[:20] + '...' if d.get('contract_address', '') else 'N/A'
    tps = chain_info.get('tps', 'N/A')
    gas_cost = chain_info.get('gas_cost', 'N/A')

    # Rating badge color
    rating_color = THEME['green'] if rating.startswith('A') else THEME['gold'] if rating.startswith('B') else THEME['red']

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="conclusion-banner" style="margin-bottom:12px;text-align:center;font-size:16px;padding:20px 28px;">
          <strong>핵심 가치 제안:</strong> {summary[:100] if summary else name + ' Economy Design Analysis'}
        </div>
        <div class="three-col" style="flex:1;min-height:0;">
          <div class="card" style="flex:1;justify-content:flex-start;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
              <h3 style="font-size:18px;font-weight:900;">프로젝트 정체성</h3>
              <div style="background:{rating_color};color:#FFF;padding:5px 14px;border-radius:4px;font-size:14px;font-weight:900;">{rating}</div>
            </div>
            <ul class="bullet-list" style="margin-bottom:8px;">{id_items}</ul>
            <div style="background:{THEME['gold_bg']};padding:10px 14px;border-radius:4px;margin:8px 0;font-size:13px;font-weight:600;">
              <strong>Target:</strong> <span>{chain}</span>
            </div>
            <div style="margin-top:8px;">
              <div style="font-size:12px;font-weight:700;color:{THEME['gold']};margin-bottom:8px;letter-spacing:0.5px;">기술 필러 점수</div>
              {pillar_bars}
            </div>
          </div>
          <div class="card" style="flex:1;justify-content:flex-start;">
            <h3 style="font-size:18px;font-weight:900;text-align:center;margin-bottom:12px;">핵심 기술 스택</h3>
            <div>{tech_items}</div>
            <div style="margin-top:auto;background:{THEME['dark']};color:#FFF;padding:14px 16px;border-radius:4px;font-weight:600;">
              <div style="font-size:11px;opacity:0.7;margin-bottom:4px;letter-spacing:0.5px;">ARCHITECTURE PATTERN</div>
              <div style="font-size:14px;font-weight:700;margin-bottom:8px;">Intent → Parse → Execute → Verify</div>
              <div style="display:flex;margin-top:8px;gap:4px;">
                <div style="flex:1;height:3px;background:{THEME['gold']};border-radius:2px;"></div>
                <div style="flex:1;height:3px;background:{THEME['gold_light']};border-radius:2px;"></div>
                <div style="flex:1;height:3px;background:{THEME['blue_light']};border-radius:2px;"></div>
                <div style="flex:1;height:3px;background:{THEME['teal']};border-radius:2px;"></div>
              </div>
            </div>
          </div>
          <div class="card" style="flex:1;justify-content:flex-start;">
            <h3 style="font-size:18px;font-weight:900;text-align:center;margin-bottom:12px;">온체인 인프라 스펙</h3>
            <div>
              <div style="margin-bottom:10px;">
                <div style="color:{THEME['gold']};font-weight:700;font-size:12px;letter-spacing:0.5px;">● 컨트랙트 주소</div>
                <div style="font-size:12px;background:{THEME['dark']};color:#FFF;padding:8px 10px;border-radius:3px;margin-top:4px;word-break:break-all;font-family:monospace;">{contract}</div>
              </div>
              <div style="margin-bottom:8px;">
                <div style="color:{THEME['gold']};font-weight:700;font-size:12px;letter-spacing:0.5px;">● 컨센서스</div>
                <div style="font-size:14px;margin-top:4px;font-weight:500;">{consensus}</div>
              </div>
              <div style="margin-bottom:8px;">
                <div style="color:{THEME['gold']};font-weight:700;font-size:12px;letter-spacing:0.5px;">● 체인</div>
                <div style="font-size:14px;margin-top:4px;font-weight:500;">{chain}</div>
              </div>
            </div>
            <div style="display:flex;gap:10px;margin-top:auto;">
              <div style="flex:1;background:{THEME['dark']};color:#FFF;padding:12px 10px;border-radius:4px;text-align:center;font-weight:600;">
                <div style="font-size:10px;opacity:0.7;letter-spacing:0.5px;">TPS</div>
                <div style="font-size:20px;font-weight:900;color:{THEME['gold_light']};margin-top:4px;">{tps}</div>
              </div>
              <div style="flex:1;background:{THEME['dark']};color:#FFF;padding:12px 10px;border-radius:4px;text-align:center;font-weight:600;">
                <div style="font-size:10px;opacity:0.7;letter-spacing:0.5px;">GAS COST</div>
                <div style="font-size:20px;font-weight:900;color:{THEME['gold_light']};margin-top:4px;">{gas_cost}</div>
              </div>
            </div>
            <div style="margin-top:10px;background:{THEME['gold_bg']};padding:10px 14px;border-radius:4px;font-size:12px;font-weight:600;">
              <strong>요약:</strong> {chain}의 {consensus} 기반 인프라
            </div>
          </div>
        </div>
        {_footer(name, 2, 8)}
      </div>
    </div>'''


def slide_tech_architecture(d: dict) -> str:
    """Slide 3: 4-pillar tech architecture with 3D pedestal style cards."""
    pillars = d.get('tech_pillars', [])
    name = d.get('project_name', 'Project')

    icon_map = ['gear', 'money', 'id_card', 'lock']
    pillar_html = ''
    total_score = 0

    for i, p in enumerate(pillars[:4]):
        p_name = p.get('name', f'Pillar {i+1}') if isinstance(p, dict) else str(p)
        p_score = p.get('score', 0) if isinstance(p, dict) else 0
        p_desc = p.get('description', '') if isinstance(p, dict) else ''
        sub_items = p.get('sub_items', []) if isinstance(p, dict) else []
        icon_name = icon_map[i] if i < len(icon_map) else 'gear'
        score_pct = min(100, max(0, (p_score / 100 * 100))) if p_score else 0
        total_score += p_score

        # Build sub-items display
        sub_html = ''
        for sub in (sub_items if isinstance(sub_items, list) else [])[:2]:
            sub_text = sub if isinstance(sub, str) else sub.get('name', '')
            sub_html += f'<div style="font-size:12px;color:{THEME["text_muted"]};margin-top:3px;">→ {sub_text[:40]}</div>'

        pillar_html += f'''<div class="pillar-card">
          {_icon_html(icon_name, 64)}
          <h4>{p_name}</h4>
          <div class="sub">{p_score}/100</div>
          <div class="score-bar">
            <div class="bar"><div class="fill" style="width:{score_pct}%;"></div></div>
          </div>
          <p>{p_desc[:180]}</p>
          {sub_html}
          <div class="pedestal">Score: {p_score}/100</div>
        </div>'''

    # Score comparison bars
    chain = d.get('chain', 'Base L2')
    avg_score = total_score / len(pillars[:4]) if pillars else 0

    score_bars_html = ''
    for p in pillars[:4]:
        p_name = p.get('name', '') if isinstance(p, dict) else str(p)
        p_score = p.get('score', 0) if isinstance(p, dict) else 0
        bar_color = THEME['green'] if p_score >= 80 else THEME['gold'] if p_score >= 60 else THEME['red']
        score_bars_html += f'''<div style="display:flex;align-items:center;margin-bottom:10px;">
          <div style="width:160px;font-size:14px;font-weight:600;text-align:right;padding-right:12px;">{p_name[:20]}</div>
          <div style="flex:1;height:20px;background:{THEME['bg_alt']};border-radius:3px;overflow:hidden;border:1.5px solid {THEME['border_light']};box-shadow:inset 0 1px 2px rgba(0,0,0,0.05);">
            <div style="height:100%;width:{p_score}%;background:linear-gradient(90deg,{bar_color},{THEME['gold_light']});border-radius:3px;"></div>
          </div>
          <div style="width:60px;font-size:14px;font-weight:700;text-align:center;color:{bar_color};">{p_score}/100</div>
        </div>'''

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">핵심 기술 아키텍처</div>
        <div class="section-subtitle">Core Pillars & Multi-Dimensional Assessment</div>
        <div class="pillar-grid" style="margin-bottom:16px;">
          {pillar_html}
        </div>
        <!-- Score comparison chart -->
        <div class="card" style="padding:18px 24px;">
          <div style="display:flex;align-items:center;margin-bottom:12px;">
            <div style="font-size:16px;font-weight:700;margin-right:20px;">Pillar Score Comparison</div>
            <div style="font-size:14px;color:{THEME['gold']};font-weight:700;letter-spacing:0.5px;">평균: {avg_score:.1f}/100</div>
            <div style="flex:1;"></div>
            <div style="font-size:13px;color:{THEME['text_muted']};font-weight:600;">Target: {chain}</div>
          </div>
          {score_bars_html}
        </div>
        {_footer(name, 3, 8)}
      </div>
    </div>'''


def slide_token_economy(d: dict) -> str:
    """Slide 4: Token distribution donut + allocation breakdown + vesting info."""
    name = d.get('project_name', 'Project')
    symbol = d.get('token_symbol', 'TOKEN')
    token = d.get('token_data', {})
    distribution = token.get('distribution', {})
    supply_model = token.get('supply_model', 'N/A')
    utility = token.get('utility', [])
    vesting = token.get('vesting', {})
    unlock_schedule = token.get('unlock_schedule', '')

    # Normalize distribution to dict format (handle list[dict] or dict)
    if isinstance(distribution, list):
        dist_dict = {}
        for item in distribution:
            if isinstance(item, dict):
                name = item.get('name', item.get('label', f'Alloc {len(dist_dict)+1}'))
                pct = item.get('pct', item.get('percentage', item.get('value', 0)))
                dist_dict[name] = pct
        distribution = dist_dict
    elif not isinstance(distribution, dict):
        distribution = {}

    # Chart data
    labels = list(distribution.keys()) if distribution else ['Community', 'Team', 'Treasury', 'Investors']
    values = list(distribution.values()) if distribution else [40, 20, 15, 25]
    donut_b64 = _make_donut_chart(labels, values, f'{symbol} Token Distribution', 400, 280) if (HAS_MPL or HAS_PLOTLY) else ''

    # Allocation details with horizontal bars
    alloc_html = ''
    max_val = max(values) if values else 1
    for i, (k, v) in enumerate(distribution.items()):
        color = CHART_COLORS[i % len(CHART_COLORS)]
        bar_w = int((v / max_val) * 100)
        alloc_html += f'''<div style="margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px;font-weight:600;">
            <span>{k}</span><span style="font-weight:700;">{v}%</span>
          </div>
          <div style="height:10px;background:{THEME['border_light']};border-radius:4px;overflow:hidden;">
            <div style="height:100%;width:{bar_w}%;background:{color};border-radius:4px;"></div>
          </div>
        </div>'''

    util_items = ''
    for u in (utility if isinstance(utility, list) else [utility])[:4]:
        util_items += f'<li>{u}</li>'

    # Distribution ratio summary
    sorted_dist = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
    dist_summary = ' > '.join([f'{k} {v}%' for k, v in sorted_dist[:3]]) if sorted_dist else 'N/A'

    # Vesting info
    vesting_html = ''
    if vesting:
        for k, v in list(vesting.items())[:3]:
            vesting_html += f'<div style="font-size:13px;margin:3px 0;font-weight:500;">• {k}: {v}</div>'
    if unlock_schedule:
        vesting_html += f'<div style="font-size:13px;margin:3px 0;font-weight:500;"><strong>Schedule:</strong> {unlock_schedule[:50]}</div>'

    # Token flow diagram (SVG-based)
    flow_svg = f'''<div style="background:{THEME['dark']};padding:16px 20px;border-radius:6px;margin-top:auto;box-shadow:0 4px 12px rgba(0,0,0,0.1);">
      <div style="font-size:12px;color:{THEME['gold_light']};font-weight:700;margin-bottom:12px;letter-spacing:0.5px;">TOKEN FLOW CYCLE</div>
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div style="text-align:center;flex:1;">
          <div style="background:{THEME['gold']};color:#FFF;padding:8px 6px;border-radius:4px;font-size:12px;font-weight:700;">MINT</div>
          <div style="font-size:11px;color:#AAA;margin-top:4px;font-weight:500;">Fixed Supply</div>
        </div>
        <div style="color:{THEME['gold_light']};font-size:28px;font-weight:900;">→</div>
        <div style="text-align:center;flex:1;">
          <div style="background:{CHART_COLORS[0]};color:#FFF;padding:8px 6px;border-radius:4px;font-size:12px;font-weight:700;">STAKE</div>
          <div style="font-size:11px;color:#AAA;margin-top:4px;font-weight:500;">Lock & Earn</div>
        </div>
        <div style="color:{THEME['gold_light']};font-size:28px;font-weight:900;">→</div>
        <div style="text-align:center;flex:1;">
          <div style="background:{CHART_COLORS[2]};color:#FFF;padding:8px 6px;border-radius:4px;font-size:12px;font-weight:700;">USE</div>
          <div style="font-size:11px;color:#AAA;margin-top:4px;font-weight:500;">Fee & Govern</div>
        </div>
        <div style="color:{THEME['gold_light']};font-size:28px;font-weight:900;">→</div>
        <div style="text-align:center;flex:1;">
          <div style="background:{CHART_COLORS[3]};color:#FFF;padding:8px 6px;border-radius:4px;font-size:12px;font-weight:700;">BURN</div>
          <div style="font-size:11px;color:#AAA;margin-top:4px;font-weight:500;">2% Annual</div>
        </div>
      </div>
    </div>'''

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">토큰 할당 및 경제 설계</div>
        <div class="section-subtitle">Token Economy & Distribution Structure</div>
        <div class="two-col" style="flex:1;min-height:0;">
          <div style="display:flex;flex-direction:column;">
            <div class="chart-container" style="height:240px;">
              {_img_tag(donut_b64, 'Token Distribution') if donut_b64 else '<div>Chart unavailable</div>'}
            </div>
            <div style="margin-top:10px;">{alloc_html}</div>
            <div style="margin-top:10px;padding:10px 14px;background:{THEME['gold_bg']};border-radius:4px;font-size:12px;font-weight:600;">
              <strong>Rank:</strong> {dist_summary}
            </div>
          </div>
          <div style="display:flex;flex-direction:column;">
            <div class="card" style="margin-bottom:12px;padding:18px;flex:1;">
              <h4 style="font-weight:700;margin-bottom:8px;font-size:16px;color:{THEME['gold']};">Supply Model</h4>
              <p style="font-size:14px;line-height:1.6;font-weight:500;">{supply_model}</p>
            </div>
            <div class="card" style="margin-bottom:12px;padding:18px;flex:1;">
              <h4 style="font-weight:700;margin-bottom:8px;font-size:16px;color:{THEME['gold']};">Token Utility</h4>
              <ul class="bullet-list">{util_items}</ul>
            </div>
            {'<div class="card" style="margin-bottom:12px;padding:18px;flex:0;"><h4 style="font-weight:700;margin-bottom:8px;font-size:16px;color:' + THEME['gold'] + ';">Vesting & Unlock</h4><div style="font-size:13px;font-weight:500;">' + (vesting_html if vesting_html else 'No vesting data') + '</div></div>' if vesting or unlock_schedule else ''}
            {flow_svg}
          </div>
        </div>
        {_footer(name, 4, 8)}
      </div>
    </div>'''


def slide_crypto_economy_framework(d: dict) -> str:
    """Slide 5: Three-component framework table with much larger text."""
    name = d.get('project_name', 'Project')
    ce = d.get('crypto_economy', {})
    vs = ce.get('value_system', {})
    rs = ce.get('reward_system', {})
    if isinstance(rs, str):
        rs = {'description': rs}
    rm = ce.get('reward_mechanism', ce.get('reward_mechanisms', {}))
    if isinstance(rm, str):
        rm = {'description': rm}

    actors = ce.get('actor_types', rs.get('actor_types', []) if isinstance(rs, dict) else [])

    # Build table rows with colored backgrounds (matching sample style)
    row_bg_colors = ['#FFFDE7', '#FFF8E1', '#F3E5F5']  # Alternating warm tints
    rows_html = ''
    for idx, actor in enumerate((actors if isinstance(actors, list) else [])[:4]):
        if isinstance(actor, dict):
            a_name = actor.get('type', actor.get('name', 'Actor'))
            contribution = actor.get('contribution', '')
            verification = actor.get('verification', '')
            reward = actor.get('reward', '')
        else:
            a_name = str(actor)
            contribution = verification = reward = ''
        bg = row_bg_colors[idx % len(row_bg_colors)]
        rows_html += f'''<tr>
          <td class="row-header" style="font-size:16px;padding:20px 16px;border-left:4px solid {THEME['gold']};">{a_name}</td>
          <td style="text-align:center;font-size:15px;padding:20px 16px;background:{bg};">{contribution}</td>
          <td style="text-align:center;font-size:15px;padding:20px 16px;">{verification}</td>
          <td style="text-align:center;font-size:15px;padding:20px 16px;background:rgba(184,134,11,0.06);">{reward}</td>
        </tr>'''

    # If no actor data, generate a summary view
    if not rows_html:
        vs_items = []
        for k, v in list(vs.items())[:3]:
            vs_items.append(f'{k.replace("_"," ").title()}: {len(v) if isinstance(v,list) else v}')
        rs_items = []
        for k, v in list(rs.items())[:3]:
            rs_items.append(f'{k.replace("_"," ").title()}: {len(v) if isinstance(v,list) else v}')
        rm_items = []
        for k, v in list(rm.items())[:3]:
            rm_items.append(f'{k.replace("_"," ").title()}: {len(v) if isinstance(v,list) else v}')

        rows_html = f'''<tr>
          <td class="row-header">Value System</td>
          <td>{'<br>'.join(vs_items)}</td>
          <td class="row-header">Reward System</td>
          <td>{'<br>'.join(rs_items)}</td>
        </tr><tr>
          <td class="row-header" colspan="2">Reward Mechanism</td>
          <td colspan="2">{'<br>'.join(rm_items)}</td>
        </tr>'''

    # Process flow visualization
    process_flow = f'''<div class="flow-row" style="margin-bottom:16px;">
      <div class="flow-box">
        <h4>기여(Contribution)</h4>
        <p>생태계 참여자의 기여도 측정 및 기록</p>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">
        <h4>검증(Verification)</h4>
        <p>온체인 스마트계약을 통한 자동 검증</p>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">
        <h4>보상(Reward)</h4>
        <p>경제적 인센티브 배분 및 지급</p>
      </div>
    </div>'''

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">크립토 경제 프레임워크</div>
        <div class="section-subtitle">생태계 기여(Contribution) → 온체인 검증(Verification) → 경제적 보상(Reward)</div>
        {process_flow}
        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-bottom:12px;">
          <table class="styled-table" style="border:2px solid {THEME['border']};">
            <thead>
              <tr>
                <th style="width:140px;background:{THEME['dark']};font-size:16px;padding:16px;"></th>
                <th style="background:{THEME['dark']};font-size:16px;padding:16px;"><span style="color:{THEME['gold_light']};text-decoration:underline;">생태계 기여(Contribution)</span></th>
                <th style="background:{THEME['dark']};font-size:16px;padding:16px;"><span style="text-decoration:underline;">온체인 검증(Verification)</span></th>
                <th style="background:linear-gradient(135deg,{THEME['dark']},#3D2E1E);font-size:16px;padding:16px;"><span style="color:{THEME['gold_light']};text-decoration:underline;">경제적 보상(Reward)</span></th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
        <div class="conclusion-banner" style="margin-top:12px;font-size:15px;padding:18px 28px;">
          <strong>프레임워크 강점:</strong> 투명한 기여 측정, 자동화된 검증 프로세스, 공정한 보상 배분을 통한 지속가능한 생태계 구축
        </div>
        {_footer(name, 5, 8)}
      </div>
    </div>'''


def slide_risk_assessment(d: dict) -> str:
    """Slide 6: Risk matrix + critical risk highlight."""
    name = d.get('project_name', 'Project')
    risks = d.get('risk_factors', [])

    # Prepare risk data
    risk_items = []
    for r in risks[:6]:
        if isinstance(r, dict):
            risk_items.append(r)
        else:
            risk_items.append({'name': str(r), 'probability': 3, 'impact': 3, 'severity': 'medium'})

    # Top risk
    top_risk = risk_items[0] if risk_items else {'name': 'No data', 'description': ''}
    top_name = top_risk.get('name', '')
    top_desc = top_risk.get('description', '')

    # Bubble chart (matplotlib preferred, Plotly fallback)
    bubble_b64 = _make_risk_bubble(risk_items, 'Impact vs Probability', 540, 340) if (HAS_MPL or HAS_PLOTLY) and risk_items else ''

    # Risk list with expanded descriptions
    risk_list_html = ''
    sev_colors = {'critical': THEME['red'], 'high': '#E65100', 'medium': THEME['gold'], 'low': THEME['green']}
    for r in risk_items:
        sc = sev_colors.get(r.get('severity', 'medium'), THEME['gold'])
        desc = r.get('description', '')[:90]
        risk_list_html += f'''<div style="display:flex;gap:8px;margin-bottom:10px;">
          <span style="width:10px;height:10px;border-radius:50%;background:{sc};margin-right:4px;flex-shrink:0;margin-top:3px;box-shadow:0 2px 4px rgba(0,0,0,0.2);"></span>
          <div style="font-size:14px;flex:1;font-weight:500;">
            <strong style="color:{THEME['text']};font-size:15px;">{r.get('name','')}</strong>
            {f'<div style="color:{THEME["text_muted"]};font-size:12px;margin-top:2px;">{desc}</div>' if desc else ''}
          </div>
        </div>'''

    # Count by severity
    crit = sum(1 for r in risk_items if r.get('severity') == 'critical')
    high = sum(1 for r in risk_items if r.get('severity') == 'high')
    medium = sum(1 for r in risk_items if r.get('severity') == 'medium')

    # Summary sentence above chart
    summary_text = f"총 {len(risk_items)}개 위험요소 식별: 심각 {crit}건, 높음 {high}건, 중간 {medium}건"

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">리스크 평가</div>
        <div class="section-subtitle">Threat Analysis & Severity Matrix</div>
        <div style="font-size:14px;margin-bottom:12px;color:{THEME['text_mid']};font-weight:600;"><strong>분석 결과:</strong> {summary_text}</div>
        <div class="two-col" style="flex:1;">
          <div class="chart-container" style="max-height:340px;overflow:hidden;display:flex;align-items:center;justify-content:center;">
            {f'<img src="data:image/png;base64,{bubble_b64}" alt="Risk Matrix" style="max-width:100%;max-height:320px;object-fit:contain;" />' if bubble_b64 else ''}
          </div>
          <div style="display:flex;flex-direction:column;">
            <div class="card" style="border-left:5px solid {THEME['red']};margin-bottom:14px;flex:1;">
              <div style="font-size:22px;font-weight:900;color:{THEME['red']};margin-bottom:8px;">
                CRITICAL RISK: {top_name}
              </div>
              <p style="font-size:14px;line-height:1.6;flex:1;font-weight:500;">{top_desc[:180]}</p>
            </div>
            <div style="display:flex;gap:10px;margin-bottom:14px;">
              <div class="kpi-box" style="border-top:4px solid {THEME['red']};flex:1;">
                <div class="value">{crit}</div><div class="label">Critical</div>
              </div>
              <div class="kpi-box" style="border-top:4px solid #E65100;flex:1;">
                <div class="value">{high}</div><div class="label">High</div>
              </div>
              <div class="kpi-box" style="border-top:4px solid {THEME['gold']};flex:1;">
                <div class="value">{len(risk_items)}</div><div class="label">Total</div>
              </div>
            </div>
            <div style="font-weight:700;font-size:14px;margin-bottom:8px;">Identified Risks:</div>
            <div style="flex:1;overflow-y:auto;">{risk_list_html}</div>
          </div>
        </div>
        {_footer(name, 6, 8)}
      </div>
    </div>'''


def slide_lifecycle_roadmap(d: dict) -> str:
    """Slide 7: S-curve lifecycle roadmap."""
    name = d.get('project_name', 'Project')
    ce = d.get('crypto_economy', {})
    lifecycle = ce.get('lifecycle', ce.get('lifecycle_assessment', {}))
    if isinstance(lifecycle, str):
        current = lifecycle.split('(')[0].strip().lower().replace(' ', '_') if lifecycle else 'bootstrap'
    elif isinstance(lifecycle, dict):
        current = lifecycle.get('current_stage', 'bootstrap')
    else:
        current = 'bootstrap'
    phases = d.get('roadmap_phases', [])

    # Build phases HTML
    stages = ['genesis', 'bootstrap', 'mature', 'stability', 'evolution']
    current_idx = stages.index(current) if current in stages else 1

    # S-curve SVG
    curve_svg = f'''<svg viewBox="0 0 900 300" style="width:100%;height:auto;">
      <!-- Grid -->
      <line x1="60" y1="260" x2="860" y2="260" stroke="{THEME['border']}" stroke-width="2"/>
      <line x1="60" y1="20" x2="60" y2="260" stroke="{THEME['border']}" stroke-width="2"/>
      <!-- S-curve path -->
      <path d="M80,250 C200,248 250,240 350,180 S500,50 600,45 S750,40 840,35"
            stroke="{THEME['dark']}" stroke-width="4" fill="none" stroke-linecap="round"/>
    '''

    # Phase markers on curve
    positions = [(130, 248), (320, 190), (480, 70), (640, 42), (800, 36)]
    for i, (px, py) in enumerate(positions[:len(stages)]):
        is_current = i == current_idx
        fill = THEME['gold'] if is_current else THEME['dark']
        r = 20 if is_current else 16
        curve_svg += f'''
          <circle cx="{px}" cy="{py}" r="{r}" fill="{fill}" stroke="#FFF" stroke-width="2.5"/>
          <text x="{px}" y="{py+6}" text-anchor="middle" fill="#FFF" font-size="14" font-weight="bold">{i+1}</text>
          <text x="{px}" y="{py+38}" text-anchor="middle" fill="{THEME['text']}" font-size="12" font-weight="{'bold' if is_current else 'normal'}">{stages[i].title()}</text>
        '''
    curve_svg += '</svg>'

    # Phase descriptions
    phase_html = ''
    default_phases = [
        {'name': 'Phase 1: 초기 부트스트래핑', 'description': '프로젝트 런칭 및 초기 사용자 확보 • 핵심 팀 구성 • 초기 개발 완료 • 커뮤니티 형성'},
        {'name': 'Phase 2: 유동성 확보 및 시장 진입', 'description': '토큰 상장 및 생태계 확장 • DEX/CEX 상장 • 유동성 풀 운영 • 파트너십 체결'},
        {'name': 'Phase 3: 장기 성장 및 자생적 생태계', 'description': '지속가능한 경제 모델 실현 • 자생적 거래량 증가 • 거버넌스 탈중앙화 • 규모의 확장'},
    ]
    for ph in (phases or default_phases)[:3]:
        ph_name = ph.get('name', '') if isinstance(ph, dict) else str(ph)
        ph_desc = ph.get('description', '') if isinstance(ph, dict) else ''
        phase_html += f'<div class="card" style="flex:1;display:flex;flex-direction:column;"><h4 style="font-size:16px;font-weight:700;color:{THEME["gold"]};margin-bottom:10px;">{ph_name}</h4><p style="font-size:14px;line-height:1.6;flex:1;font-weight:500;">{ph_desc[:170]}</p></div>'

    # Maturity indicators
    maturity = lifecycle.get('maturity_indicators', lifecycle.get('maturity_transition_indicators', {})) if isinstance(lifecycle, dict) else {}
    mat_html = ''
    for k, v in list(maturity.items())[:4]:
        label = k.replace('_', ' ').title()
        if isinstance(v, bool):
            icon = '☑' if v else '☐'
            color = THEME['gold'] if v else THEME['text_muted']
        else:
            icon = '●'
            color = THEME['gold']
        mat_html += f'<span style="margin-right:20px;color:{color};font-size:13px;font-weight:600;">{icon} {label}</span>'

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">라이프사이클 로드맵</div>
        <div class="section-subtitle">Growth Trajectory & Phase Transition</div>
        <div style="margin-bottom:12px;">{curve_svg}</div>
        <div style="display:flex;gap:12px;margin-bottom:12px;">{phase_html}</div>
        <div class="conclusion-banner" style="font-size:14px;padding:14px 24px;margin-bottom:20px;font-weight:600;">
          성숙 단계 전환 조건: {mat_html if mat_html else '데이터 없음'}
        </div>
        {_footer(name, 7, 8)}
      </div>
    </div>'''


def slide_final_assessment(d: dict) -> str:
    """Slide 8: Final radar chart + score + monitoring checklist."""
    name = d.get('project_name', 'Project')
    symbol = d.get('token_symbol', 'TOKEN')
    rating = d.get('overall_rating', 'B+')
    pillars = d.get('tech_pillars', [])
    thesis = d.get('investment_thesis', '')
    monitoring = d.get('monitoring_checklist', [])

    # Radar chart from pillar scores
    categories = []
    values = []
    for p in pillars[:6]:
        if isinstance(p, dict):
            short = p.get('short_name', p.get('name', 'Pillar'))
            # Abbreviate long names
            if len(short) > 14:
                words = short.split()
                short = ' '.join(w[:4] + '.' if len(w) > 5 else w for w in words)[:14]
            categories.append(short)
            values.append(p.get('score', 70) / 10)
        else:
            categories.append(str(p)[:14])
            values.append(7)

    radar_b64 = _make_radar_chart(categories, values, '',
                                   max_val=10, width=480, height=360) if (HAS_MPL or HAS_PLOTLY) and categories else ''

    # Checklist
    check_html = ''
    default_checks = [
        '공급 집중도 해소: 홀더 분산화 이행 확인',
        '거버넌스 탈중앙화: 온체인 거버넌스 전환 추적',
        '네트워크 효과 이식 여부: 멀티체인 확장 시 가치 포착 증명',
    ]
    for item in (monitoring or default_checks)[:4]:
        check_html += f'''<div style="display:flex;align-items:flex-start;margin-bottom:12px;">
          <span style="color:{THEME['gold']};font-size:20px;margin-right:10px;flex-shrink:0;font-weight:bold;">☑</span>
          <span style="font-size:14px;line-height:1.6;font-weight:500;">{item}</span>
        </div>'''

    # Pillar score bars breakdown
    pillar_bars = ''
    for p in pillars[:6]:
        if isinstance(p, dict):
            p_name = p.get('short_name', p.get('name', 'Pillar'))[:14]
            p_score = p.get('score', 0)
            score_pct = min(100, max(0, (p_score / 100 * 100)))
            pillar_bars += f'''<div style="margin-bottom:8px;">
              <div style="font-size:13px;display:flex;justify-content:space-between;margin-bottom:3px;font-weight:600;">
                <span>{p_name}</span>
                <span style="color:{THEME['gold']};font-weight:700;">{p_score}</span>
              </div>
              <div style="height:6px;background:{THEME['border_light']};border-radius:3px;overflow:hidden;">
                <div style="height:100%;width:{score_pct}%;background:linear-gradient(90deg,{THEME['gold']},{THEME['gold_light']});"></div>
              </div>
            </div>'''

    # Final verdict
    verdict = thesis[:140] if thesis else f'{name}의 크립토 경제 설계에 대한 종합 분석 완료.'

    rc = THEME['green'] if rating in ('S','A','A+','A-') else THEME['gold'] if rating.startswith('B') else THEME['red']

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="two-col" style="flex:1;">
          <div style="display:flex;flex-direction:column;align-items:center;justify-content:space-between;">
            <div style="text-align:center;margin-bottom:6px;width:100%;">
              <div style="font-size:20px;font-weight:900;">종합 평점: {_score_from_rating(rating)} / 40</div>
            </div>
            <div class="chart-container" style="flex:1;max-height:360px;width:100%;display:flex;align-items:center;justify-content:center;">
              {_img_tag(radar_b64, 'Radar', 'max-height:340px;') if radar_b64 else ''}
            </div>
            <div style="width:100%;background:{THEME['gold_bg']};padding:12px 16px;border-radius:4px;font-size:12px;font-weight:600;border:1.5px solid {THEME['gold']};">
              <strong>핵심 평가 영역:</strong> 기술·경제·위험 다차원 분석
            </div>
          </div>
          <div style="display:flex;flex-direction:column;">
            <div style="font-size:16px;font-weight:900;margin-bottom:12px;">Security & Pillar Assessment</div>
            <div style="background:{THEME['surface']};border:2px solid {THEME['border']};padding:14px 16px;border-radius:4px;margin-bottom:12px;flex:1;box-shadow:0 3px 10px rgba(0,0,0,0.08);">
              <div style="font-size:12px;font-weight:700;margin-bottom:8px;color:{THEME['gold']};text-transform:uppercase;letter-spacing:0.5px;">Score Breakdown</div>
              {pillar_bars if pillar_bars else '<div style="font-size:12px;color:' + THEME['text_muted'] + ';font-weight:500;">데이터 없음</div>'}
            </div>
            <div style="font-size:16px;font-weight:900;margin-bottom:12px;">핵심 모니터링 체크리스트</div>
            <div style="flex:1;overflow-y:auto;margin-bottom:12px;">{check_html}</div>
            <div class="conclusion-banner">
              <div style="display:flex;align-items:center;gap:16px;">
                <div class="rating-circle" style="background:{rc};width:56px;height:56px;font-size:24px;flex-shrink:0;font-weight:900;">{rating}</div>
                <div style="font-size:14px;font-weight:500;line-height:1.6;">
                  <strong style="font-size:15px;">최종 진단:</strong><br/>{verdict}
                </div>
              </div>
            </div>
          </div>
        </div>
        {_footer(name, 8, 8)}
      </div>
    </div>'''


def _score_from_rating(rating: str) -> int:
    scores = {'S': 40, 'A+': 38, 'A': 36, 'A-': 34, 'B+': 31, 'B': 28, 'B-': 25,
              'C+': 22, 'C': 20, 'C-': 18, 'D': 15, 'F': 10}
    return scores.get(rating, 28)


def _rating_to_score(rating: str) -> int:
    m = {'S': 98, 'A+': 95, 'A': 90, 'A-': 85, 'B+': 78, 'B': 72, 'B-': 65,
         'C+': 58, 'C': 50, 'C-': 42, 'D': 30, 'F': 15}
    return m.get(rating, 72)


# ═══════════════════════════════════════════════════════════════
#  MAIN ASSEMBLY  &  PDF CONVERSION
# ═══════════════════════════════════════════════════════════════

def generate_html(project_data: dict) -> str:
    """Generate complete HTML document with all slides."""
    html_lang = project_data.get('lang', 'en')
    slides = [
        slide_cover(project_data),
        slide_executive_summary(project_data),
        slide_tech_architecture(project_data),
        slide_token_economy(project_data),
        slide_crypto_economy_framework(project_data),
        slide_risk_assessment(project_data),
        slide_lifecycle_roadmap(project_data),
        slide_final_assessment(project_data),
    ]

    html = f'''<!DOCTYPE html>
<html lang="{html_lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1280">
  <title>{project_data.get('project_name', 'Report')} - Economy Design Analysis</title>
  <style>{CSS}</style>
</head>
<body>
{''.join(slides)}
</body>
</html>'''
    return html


def html_to_pdf(html: str, output_path: str) -> str:
    """Convert HTML string to PDF. Tries Playwright first, falls back to WeasyPrint."""

    # ── Attempt 1: Playwright (best quality) ──
    try:
        from playwright.sync_api import sync_playwright

        with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
            f.write(html)
            tmp_html = f.name

        try:
            with sync_playwright() as p:
                launch_args = {'args': ['--no-sandbox', '--disable-gpu']}
                import glob as _glob
                _pw_dir = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', os.path.expanduser('~/.cache/ms-playwright'))
                _hs_candidates = _glob.glob(os.path.join(_pw_dir, 'chromium_headless_shell-*/chrome-linux/headless_shell'))
                _ch_candidates = _glob.glob(os.path.join(_pw_dir, 'chromium-*/chrome-linux/chrome'))
                if _hs_candidates:
                    launch_args['executable_path'] = sorted(_hs_candidates)[-1]
                elif _ch_candidates:
                    launch_args['executable_path'] = sorted(_ch_candidates)[-1]
                browser = p.chromium.launch(**launch_args)
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
                return output_path
        except Exception as e:
            print(f"⚠ Playwright PDF failed ({e}), trying WeasyPrint fallback...")
        finally:
            if os.path.exists(tmp_html):
                os.unlink(tmp_html)
    except ImportError:
        print("⚠ Playwright not available, trying WeasyPrint...")

    # ── Attempt 2: WeasyPrint fallback ──
    try:
        import weasyprint
        # Inject @page CSS for landscape 16:9
        page_css = '@page { size: 1280px 720px; margin: 0; }'
        styled_html = html.replace('</head>', f'<style>{page_css}</style></head>')
        doc = weasyprint.HTML(string=styled_html)
        doc.write_pdf(output_path)
        print("✓ PDF generated via WeasyPrint fallback")
        return output_path
    except ImportError:
        raise RuntimeError("Neither Playwright nor WeasyPrint available for PDF generation")
    except Exception as e:
        raise RuntimeError(f"WeasyPrint PDF generation failed: {e}")


def generate_slide_econ(project_data: dict, output_dir: str = '/tmp') -> Tuple[str, dict]:
    """
    Main entry: generate high-quality slide PDF for ECON report.
    Returns (pdf_path, metadata).
    """
    slug = project_data.get('slug', project_data.get('project_name', 'project').lower().replace(' ', '_'))
    version = project_data.get('version', 1)
    lang = project_data.get('lang', 'en')

    filename = f'{slug}_econ_slide_v{version}_{lang}.pdf'
    pdf_path = os.path.join(output_dir, filename)

    html = generate_html(project_data)
    html_to_pdf(html, pdf_path)

    metadata = {
        'path': pdf_path,
        'filename': filename,
        'slides': 8,
        'format': 'slide_html',
        'theme': 'beige_gold',
        'renderer': 'playwright_chromium',
        'resolution': '1280x720',
    }

    return pdf_path, metadata


# ═══════════════════════════════════════════════════════════════
#  TEST  –  run with: python gen_slide_html_econ.py
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    sample_data = {
        'project_name': 'ElsaAI',
        'token_symbol': 'ELSA',
        'slug': 'elsaai',
        'chain': 'Base (Ethereum L2)',
        'overall_rating': 'B+',
        'version': 1,
        'lang': 'en',
        'contract_address': '0x29cc30f9d113b356ce408667aa6433589cecbdca',
        'executive_summary': 'AI 에이전트 경제 인프라의 설계와 지속 가능성 분석. 단순한 대행을 넘어선 지능형 대리 모델.',
        'project_identity': [
            'AI 에이전트 레이어',
            'DeFi 실행 계층',
            '인텐트(Intent) 기반 dApp',
        ],
        'core_tech_stack': [
            {'name': 'ElsaAI Automata', 'description': 'The Brain — 인텐트 및 데이터 엔진'},
            {'name': 'x402 Protocol', 'description': 'The Economy — M2M 초소액 결제'},
            {'name': 'ERC-8004', 'description': 'The Identity — AI 에이전트 온체인 여권'},
            {'name': 'MPC Wallets', 'description': 'The Security — 비수탁형 지갑'},
        ],
        'chain_info': {'consensus': 'Optimistic Rollup', 'tps': 2000, 'gas_cost': '$0.001'},
        'tech_pillars': [
            {'name': 'AI Agent Runtime', 'short_name': 'AI Runtime', 'score': 82, 'description': '인텐트 파싱 및 실행 계획 수립 엔진'},
            {'name': 'Agent Identity (ERC-8004)', 'short_name': 'Identity', 'score': 78, 'description': '온체인 에이전트 신원 검증 표준'},
            {'name': 'Compute Market', 'short_name': 'Compute', 'score': 75, 'description': '분산 컴퓨팅 자원 마켓플레이스'},
            {'name': 'Governance System', 'short_name': 'Governance', 'score': 70, 'description': '탈중앙 거버넌스 프레임워크'},
        ],
        'token_data': {
            'distribution': {
                'Community': 40, 'Team': 20, 'Treasury': 15,
                'Investors': 15, 'Compute Rewards': 10,
            },
            'supply_model': 'Fixed 1B supply with 2% annual burn rate',
            'utility': [
                'Governance voting',
                'Agent deployment staking',
                'Fee discounts (50% max)',
                'Compute marketplace payments',
            ],
        },
        'crypto_economy': {
            'value_system': {
                'onchain_components': ['Smart contract execution', 'Agent identity registry', 'Reputation scoring'],
                'offchain_components': ['AI model inference', 'Training data pipeline'],
                'onchain_verifiability': 'partial',
            },
            'reward_system': {
                'capital_contributions': [{'type': 'Staking', 'description': 'ELSA token staking'}],
                'cost_contributions': [{'type': 'Development'}, {'type': 'Compute'}, {'type': 'Marketing'}],
                'actor_types': [
                    {'type': '에이전트 개발자', 'contribution': '비용적 기여: AI 에이전트 노드 운영',
                     'verification': 'x402 결제 증명 및 ERC-8004 평판', 'reward': '호출당 서비스 수수료'},
                    {'type': '자본 공급자(스테이커)', 'contribution': '자본적 기여: ELSA 락업',
                     'verification': '스마트 컨트랙트 상태 증명', 'reward': '플랫폼 수수료 수익 공유'},
                    {'type': '일반 사용자', 'contribution': '생태계 활성화: 인텐트 플랫폼 이용',
                     'verification': '온체인 트랜잭션 로그', 'reward': '엘사 포인트 적립'},
                ],
            },
            'reward_mechanism': {
                'fungible_token': 'ELSA (ERC-20)',
                'nft_token': 'ERC-8004 Agent Identity NFT',
                'utility_function': 'Priority execution, governance, fee discounts',
            },
            'lifecycle': {
                'current_stage': 'bootstrap',
                'maturity_indicators': {
                    'actor_replacement': False,
                    'reward_stabilization': False,
                    'security_token_transition': True,
                    'revenue_realization': True,
                    'decentralization_automation': False,
                },
            },
        },
        'risk_factors': [
            {'name': 'Regulatory', 'description': 'AI regulation uncertainty in major markets',
             'probability': 3, 'impact': 4, 'severity': 'high'},
            {'name': 'Smart Contract', 'description': 'Novel agent mechanisms with limited audit history',
             'probability': 2, 'impact': 5, 'severity': 'critical'},
            {'name': 'Competition', 'description': 'Growing AI-crypto space with well-funded competitors',
             'probability': 4, 'impact': 3, 'severity': 'high'},
            {'name': 'Compute Dependency', 'description': 'Off-chain GPU reliance creates centralization risk',
             'probability': 3, 'impact': 4, 'severity': 'high'},
            {'name': 'Market Risk', 'description': 'Crypto market volatility affecting token value',
             'probability': 3, 'impact': 3, 'severity': 'medium'},
        ],
        'roadmap_phases': [
            {'name': 'Phase 1: 초기 부트스트래핑 (2024-2025)',
             'description': '$300만 시드 투자 유치. 엘사 포인트 및 Intro Quest 중심 활동. PMF 검증 집중.'},
            {'name': 'Phase 2: 유동성 확보 (2026년 1월)',
             'description': 'TGE 실행. 주요 글로벌 거래소 상장을 통한 유동성 확보 및 인지도 구축.'},
            {'name': 'Phase 3: 장기 성장 (2026년 이후)',
             'description': 'AgentOS 정식 출시. B2C→B2B 전환. 에이전트 간 자율적 거래(A2A) 경제 실현.'},
        ],
        'investment_thesis': '투명한 자산 분배 거버넌스만 확보된다면, 에이전트 머신 경제(Machine Economy) 시대의 최상위 핵심 레이어로 자리매김할 압도적 잠재력을 지님.',
        'monitoring_checklist': [
            '공급 집중도 해소: 96% 홀더 집중도의 분산화 이행 스케줄 확인',
            'AI 편향성 방어 시스템: ERC-8004 검증 실효성',
            '네트워크 효과 이식 여부: 타 L2 확장 시 가치 포착 역량 증명',
        ],
    }

    print("Generating HTML slides...")
    pdf_path, meta = generate_slide_econ(sample_data, '/tmp')
    print(f"✓ Slide PDF: {pdf_path}")
    print(f"✓ Slides: {meta['slides']}")
    print(f"✓ Theme: {meta['theme']}")
    print(f"✓ Renderer: {meta['renderer']}")
    print(f"✓ Size: {os.path.getsize(pdf_path):,} bytes")
