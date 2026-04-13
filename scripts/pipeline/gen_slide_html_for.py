#!/usr/bin/env python3
"""
gen_slide_html_for.py – High-quality HTML→PDF slide generator for FORENSIC REPORT.

Produces 16:9 landscape infographic PDF with beige background + forensic RED accents.
Uses Playwright (headless Chromium) for pixel-perfect rendering.

FORENSIC REPORT VISUAL IDENTITY:
- Base: Beige (#F5F1EB) + border (#D4C5A9)
- Accent: FORENSIC RED (#B91C1C) instead of gold — alert/danger signaling
- Typography: 48px titles, 16px body (matching ECON quality)
- Cover: CONFIDENTIAL watermark + red alert badge
- 8 slides covering: Cover, Executive Summary, Market Forensics, On-Chain Intel,
  Technical Analysis, Manipulation Matrix, Risk Synthesis, Conclusion
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
#  DESIGN SYSTEM  –  Beige + Forensic RED theme
# ═══════════════════════════════════════════════════════════════

THEME = {
    'bg':          '#F5F1EB',
    'bg_alt':      '#EDE8DF',
    'surface':     '#FFFFFF',
    'border':      '#D4C5A9',
    'border_light':'#E6DDD0',
    'gold':        '#B91C1C',          # ← FORENSIC RED (danger/alert)
    'gold_light':  '#DC2626',          # ← BRIGHT RED accent
    'gold_bg':     '#FEF2F2',          # ← Light red background
    'dark':        '#2D2D2D',
    'dark_mid':    '#3A3A3A',
    'text':        '#1A1A1A',
    'text_mid':    '#444444',
    'text_muted':  '#777777',
    'red':         '#B91C1C',          # Same as gold (forensic red)
    'red_light':   '#DC2626',
    'green':       '#2E7D32',
    'blue':        '#1565C0',
    'blue_light':  '#5C9CE6',
    'purple':      '#6A1B9A',
    'teal':        '#00838F',
    'grid':        '#E0D8CC',
}

# Chart color palette — same as ECON but red-shifted for forensic context
CHART_COLORS = [
    '#B91C1C',  # forensic red (primary)
    '#DC2626',  # red accent
    '#E65100',  # deep orange
    '#C62828',  # darker red
    '#6A1B9A',  # purple
    '#00838F',  # teal
    '#3D5A80',  # steel blue
    '#455A64',  # blue grey
]

# ═══════════════════════════════════════════════════════════════
#  CSS TEMPLATE - Forensic RED theme
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

/* Section title – LARGE */
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

/* Dark header banner */
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

/* RED accent label (forensic alert) */
.gold-label {
  display: inline-block;
  background: linear-gradient(135deg, %(gold)s, %(gold_light)s);
  color: #FFF;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 700;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(185,28,28,0.3);
}

/* Card – matching ECON quality */
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
.kpi-box .delta.neg { color: %(gold)s; }
.kpi-box .delta.pos { color: %(green)s; }

/* Table – large cells */
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

/* Bullet list */
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

/* Flow diagram */
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

/* Alert badge (red, for forensic) */
.alert-badge {
  width: 80px; height: 80px;
  border-radius: 50%%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 900;
  color: #FFF;
  box-shadow: 0 6px 16px rgba(185,28,28,0.3);
  background: %(gold)s;
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

/* Conclusion banner */
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

/* CONFIDENTIAL watermark */
.confidential-badge {
  position: absolute;
  top: 40px;
  right: 50px;
  background: %(gold)s;
  color: #FFF;
  padding: 8px 20px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 900;
  letter-spacing: 2px;
  text-transform: uppercase;
  box-shadow: 0 4px 12px rgba(185,28,28,0.3);
  z-index: 10;
}

""" % THEME


# ═══════════════════════════════════════════════════════════════
#  HERO SVG - Forensic nodes with RED accents
# ═══════════════════════════════════════════════════════════════

def _hero_illustration() -> str:
    """Isometric blockchain illustration with forensic red accent nodes."""
    r = THEME['gold']
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
        <circle cx="0" cy="0" r="5" fill="{r}" opacity="0.5"/>
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
        <circle cx="0" cy="0" r="4" fill="{r}" opacity="0.4"/>
        <line x1="0" y1="-35" x2="0" y2="-44" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="0" y1="35" x2="0" y2="44" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="-35" y1="0" x2="-44" y2="0" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="35" y1="0" x2="44" y2="0" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="25" y1="-25" x2="31" y2="-31" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
        <line x1="-25" y1="25" x2="-31" y2="31" stroke="{d}" stroke-width="4" stroke-linecap="round"/>
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

      <!-- ===== CIRCUIT NODES (RED alert nodes at junctions) ===== -->
      <g>
        <circle cx="230" cy="270" r="5" fill="{r}" opacity="0.5"/>
        <circle cx="380" cy="270" r="5" fill="{r}" opacity="0.5"/>
        <circle cx="300" cy="300" r="4" fill="{r}" opacity="0.4"/>
        <circle cx="500" cy="170" r="5" fill="{r}" opacity="0.5"/>
        <circle cx="280" cy="140" r="4" fill="{r}" opacity="0.4"/>
        <circle cx="450" cy="140" r="5" fill="{r}" opacity="0.5"/>
        <circle cx="230" cy="200" r="3.5" fill="{r}" opacity="0.35"/>
        <circle cx="550" cy="300" r="4" fill="{r}" opacity="0.4"/>
        <circle cx="180" cy="170" r="3.5" fill="{r}" opacity="0.35"/>
        <circle cx="580" cy="170" r="3.5" fill="{r}" opacity="0.35"/>
        <circle cx="350" cy="380" r="4" fill="{r}" opacity="0.4"/>
        <circle cx="600" cy="340" r="3" fill="{r}" opacity="0.3"/>
        <circle cx="540" cy="100" r="3" fill="{r}" opacity="0.3"/>
      </g>

      <!-- ===== DECORATIVE CUBES ===== -->
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
#  SVG ICONS – Red-themed
# ═══════════════════════════════════════════════════════════════

ICONS = {
    'warning': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M32 4L4 56h56L32 4z" stroke="#B91C1C" stroke-width="3" fill="none"/>
      <line x1="32" y1="22" x2="32" y2="40" stroke="#B91C1C" stroke-width="3.5" stroke-linecap="round"/>
      <circle cx="32" cy="48" r="2.5" fill="#B91C1C"/>
    </svg>''',
    'alert': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="32" cy="32" r="28" stroke="#B91C1C" stroke-width="3" fill="none"/>
      <circle cx="32" cy="24" r="2.5" fill="#B91C1C"/>
      <line x1="32" y1="32" x2="32" y2="44" stroke="#B91C1C" stroke-width="3" stroke-linecap="round"/>
    </svg>''',
    'lock': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="12" y="28" width="40" height="28" rx="4" stroke="#B91C1C" stroke-width="3" fill="none"/>
      <path d="M20 28V18a12 12 0 0124 0v10" stroke="#B91C1C" stroke-width="3" fill="none"/>
      <circle cx="32" cy="42" r="4" fill="#B91C1C"/>
    </svg>''',
    'chart': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="8" y="36" width="12" height="20" rx="1.5" fill="#B91C1C" opacity="0.5"/>
      <rect x="28" y="22" width="12" height="34" rx="1.5" fill="#B91C1C" opacity="0.75"/>
      <rect x="48" y="8" width="12" height="48" rx="1.5" fill="#B91C1C"/>
      <line x1="4" y1="58" x2="60" y2="58" stroke="#B91C1C" stroke-width="2.5"/>
    </svg>''',
    'network': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="32" cy="32" r="8" stroke="#B91C1C" stroke-width="2" fill="none"/>
      <circle cx="12" cy="12" r="6" stroke="#B91C1C" stroke-width="2" fill="none"/>
      <circle cx="52" cy="12" r="6" stroke="#B91C1C" stroke-width="2" fill="none"/>
      <circle cx="12" cy="52" r="6" stroke="#B91C1C" stroke-width="2" fill="none"/>
      <circle cx="52" cy="52" r="6" stroke="#B91C1C" stroke-width="2" fill="none"/>
      <line x1="24" y1="24" x2="17" y2="18" stroke="#B91C1C" stroke-width="2"/>
      <line x1="40" y1="24" x2="47" y2="18" stroke="#B91C1C" stroke-width="2"/>
      <line x1="24" y1="40" x2="17" y2="46" stroke="#B91C1C" stroke-width="2"/>
      <line x1="40" y1="40" x2="47" y2="46" stroke="#B91C1C" stroke-width="2"/>
    </svg>''',
    'target': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="32" cy="32" r="26" stroke="#B91C1C" stroke-width="2" fill="none"/>
      <circle cx="32" cy="32" r="18" stroke="#B91C1C" stroke-width="2" fill="none"/>
      <circle cx="32" cy="32" r="10" stroke="#B91C1C" stroke-width="2" fill="none"/>
      <circle cx="32" cy="32" r="4" fill="#B91C1C"/>
    </svg>''',
    'check': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M20 32l10 10 20-20" stroke="#2E7D32" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',
}


# ═══════════════════════════════════════════════════════════════
#  CHART HELPERS  –  Plotly → base64 PNG
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
    labeled = [f'{c}\n({v:.0f}/{max_val})' for c, v in zip(categories, values)]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=labeled + [labeled[0]],
        fill='toself',
        fillcolor='rgba(185,28,28,0.2)',
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
    """Risk matrix bubble chart for forensic indicators."""
    fig = go.Figure()
    sev_colors = {'critical': THEME['gold'], 'high': '#E65100',
                  'medium': THEME['blue'], 'low': THEME['green']}
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
        xaxis=dict(title='Likelihood →', range=[0, 6], showgrid=True,
                  gridcolor=THEME['border_light']),
        yaxis=dict(title='Impact ↑', range=[0, 6], showgrid=True,
                  gridcolor=THEME['border_light']),
        width=width, height=height,
    )
    fig.add_shape(type='rect', x0=3, y0=3, x1=6, y1=6,
                  fillcolor='rgba(185,28,28,0.08)', line_width=0)
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
#  FORENSIC REPORT SLIDE GENERATORS
# ═══════════════════════════════════════════════════════════════

def slide_cover(d: dict) -> str:
    """Slide 1: Forensic cover with CONFIDENTIAL badge + red alert."""
    name = d.get('project_name', 'Project')
    symbol = d.get('token_symbol', 'TOKEN')
    risk_level = d.get('risk_level', 'HIGH').upper()
    trigger_reason = d.get('trigger_reason', '알람 트리거 원인')
    date_str = datetime.now().strftime('%Y. %m.')

    # Risk level colors
    risk_colors = {
        'CRITICAL': '#8B0000',
        'HIGH': '#B91C1C',
        'MODERATE': '#DC2626',
        'LOW': '#2E7D32',
    }
    risk_color = risk_colors.get(risk_level, THEME['gold'])

    title = d.get('cover_title', '포렌식 리스크 분석 보고서')
    subtitle = d.get('cover_subtitle', f'{name} 시장 조작 및 이상 거래 탐지 분석')

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      {_hero_illustration()}
      <div class="confidential-badge">CONFIDENTIAL</div>
      <div class="slide-content" style="padding:28px 80px; position:relative; z-index:1;">
        {_header_bar()}
        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;position:relative;">
          <h1 style="font-size:68px;font-weight:900;line-height:1.25;margin-bottom:20px;letter-spacing:-1px;max-width:1000px;">{title}</h1>
          <p style="font-size:20px;color:{THEME['text_mid']};max-width:800px;line-height:1.7;font-weight:500;">
            {subtitle}
          </p>
          <div style="margin-top:16px;width:140px;height:4px;background:linear-gradient(90deg,{THEME['gold']},{THEME['gold_light']});border-radius:2px;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:flex-end;">
          <div>
            <span class="gold-label" style="font-size:14px;padding:8px 20px;">Alert Date: {date_str}</span>
            <span class="gold-label" style="margin-left:10px;font-size:14px;padding:8px 20px;">Token: {symbol}</span>
          </div>
          <div style="text-align:center;">
            <div class="alert-badge" style="background:{risk_color};width:100px;height:100px;font-size:36px;">{risk_level[0]}</div>
            <div style="font-size:9px;color:{THEME['text_muted']};font-weight:700;letter-spacing:2px;margin-top:4px;">RISK LEVEL</div>
          </div>
        </div>
      </div>
    </div>'''


def slide_executive_summary(d: dict) -> str:
    """Slide 2: Executive Summary & Alert Classification."""
    name = d.get('project_name', 'Project')
    risk_level = d.get('risk_level', 'HIGH').upper()
    trigger_reason = d.get('trigger_reason', '')
    key_findings = d.get('key_findings', [])[:4]
    market_data = d.get('market_data', {})
    alert_date = datetime.now().strftime('%Y-%m-%d')
    forensic_methodology = d.get('forensic_methodology', ['Volume Authenticity', 'On-Chain Behavior', 'Market Microstructure', 'Derivatives Sentiment'])

    price = market_data.get('current_price', market_data.get('price', 0))
    price_change = market_data.get('price_change_24h', market_data.get('change_24h', 0))
    volume = market_data.get('volume_24h', 0)
    market_cap = market_data.get('market_cap', 0)
    holders = market_data.get('holders', market_data.get('holder_count', 0))

    # Format market data - handle both string and numeric formats
    if isinstance(price, str):
        price_str = price
    elif isinstance(price, (int, float)) and price > 0:
        price_str = f'${price:,.6f}' if price < 1 else f'${price:,.2f}'
    else:
        price_str = 'N/A'

    if isinstance(price_change, str):
        price_change_str = price_change
    elif isinstance(price_change, (int, float)):
        price_change_str = f'{price_change:+.1f}%'
    else:
        price_change_str = 'N/A'

    if isinstance(volume, str):
        volume_str = volume
    elif isinstance(volume, (int, float)) and volume > 0:
        volume_str = f'${volume/1e6:.1f}M'
    else:
        volume_str = 'N/A'

    if isinstance(market_cap, str):
        market_cap_str = market_cap
    elif isinstance(market_cap, (int, float)) and market_cap > 0:
        market_cap_str = f'${market_cap/1e6:.1f}M'
    else:
        market_cap_str = 'N/A'

    if isinstance(holders, str):
        holders_str = holders
    elif isinstance(holders, (int, float)) and holders > 0:
        holders_str = f'{holders:,.0f}' if holders < 1e6 else f'{holders/1e6:.1f}M'
    else:
        holders_str = 'N/A'

    risk_colors = {'CRITICAL': '#8B0000', 'HIGH': '#B91C1C', 'MODERATE': '#DC2626', 'LOW': '#2E7D32'}
    risk_color = risk_colors.get(risk_level, THEME['gold'])

    findings_html = ''
    for finding in key_findings:
        severity = '●' if isinstance(finding, dict) else '●'
        finding_text = finding.get('text', str(finding)) if isinstance(finding, dict) else str(finding)
        findings_html += f'<li style="font-size:13px;margin:6px 0;"><span style="color:{risk_color};font-weight:900;margin-right:6px;">{severity}</span>{finding_text}</li>'

    methodology_html = ''.join([f'<div style="font-size:11px;padding:4px 6px;background:{THEME["bg_alt"]};margin:3px 0;border-radius:2px;">• {m}</div>'
                                for m in (forensic_methodology if isinstance(forensic_methodology, list) else [str(forensic_methodology)])])

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="three-col" style="flex:1;min-height:0;">
          <div class="card" style="flex:1;">
            <h3 style="font-size:16px;font-weight:900;margin-bottom:12px;color:{risk_color};">Risk Classification</h3>
            <div style="background:{risk_color};color:#FFF;padding:20px 16px;border-radius:4px;text-align:center;margin-bottom:12px;">
              <div style="font-size:32px;font-weight:900;">{risk_level}</div>
              <div style="font-size:12px;margin-top:4px;letter-spacing:0.5px;">THREAT LEVEL</div>
            </div>
            <div style="background:{THEME['gold_bg']};border:2px solid {THEME['gold']};padding:12px 14px;border-radius:4px;font-size:12px;font-weight:600;line-height:1.5;margin-bottom:12px;">
              <strong>Trigger:</strong><br/>{trigger_reason[:80]}
            </div>
            <div style="font-size:10px;color:{THEME['text_muted']};margin-bottom:10px;">Alert: {alert_date}</div>
            <div style="border-top:2px solid {THEME['border']};padding-top:10px;">
              <div style="font-size:11px;font-weight:700;color:{THEME['gold']};letter-spacing:0.5px;margin-bottom:8px;">METHODOLOGY</div>
              {methodology_html}
            </div>
          </div>
          <div class="card" style="flex:1;">
            <h3 style="font-size:16px;font-weight:900;margin-bottom:12px;">Key Findings</h3>
            <ul class="bullet-list" style="font-size:13px;list-style:none;padding:0;margin:0;">{findings_html}</ul>
            <div style="margin-top:auto;padding-top:12px;border-top:2px solid {THEME['border']};font-size:11px;color:{THEME['text_muted']};font-weight:500;line-height:1.5;">
              <strong>Assessment:</strong> Multiple forensic indicators converge to suggest elevated risk profile requiring immediate monitoring and further investigation.
            </div>
          </div>
          <div class="card" style="flex:1;">
            <h3 style="font-size:16px;font-weight:900;margin-bottom:12px;">Market Snapshot</h3>
            <div class="kpi-row">
              <div class="kpi-box" style="flex:1;">
                <div class="label">Price</div>
                <div class="value" style="font-size:18px;">{price_str}</div>
                <div class="delta {('neg' if (isinstance(price_change, (int, float)) and price_change < 0) else 'pos')}">{price_change_str}</div>
              </div>
            </div>
            <div class="kpi-row" style="margin-top:8px;">
              <div class="kpi-box" style="flex:1;">
                <div class="label">24h Volume</div>
                <div class="value" style="font-size:16px;">{volume_str}</div>
              </div>
              <div class="kpi-box" style="flex:1;">
                <div class="label">Market Cap</div>
                <div class="value" style="font-size:16px;">{market_cap_str}</div>
              </div>
            </div>
            <div class="kpi-row" style="margin-top:8px;">
              <div class="kpi-box" style="flex:1;background:{THEME['gold_bg']};border:2px solid {THEME['gold']};">
                <div class="label" style="color:{THEME['gold']};font-weight:700;">Holders</div>
                <div class="value" style="font-size:16px;color:{risk_color};">{holders_str}</div>
              </div>
            </div>
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:12px;">
          <strong>Executive Assessment:</strong> {d.get('executive_summary', 'Risk analysis indicates potential market manipulation activity requiring enhanced monitoring and forensic investigation.')}
        </div>
        {_footer(name, 2, 8)}
      </div>
    </div>'''


def slide_market_forensics(d: dict) -> str:
    """Slide 3: Market & Volume Forensics."""
    name = d.get('project_name', 'Project')
    manipulation_scores = d.get('manipulation_scores', [])

    # Build chart data
    score_labels = [s.get('name', s.get('type', 'Unknown')) for s in manipulation_scores]
    score_values = [s.get('score', 0) for s in manipulation_scores]

    bar_chart_b64 = _make_bar_chart(score_labels, score_values, 'Manipulation Detection Scores',
                                     horizontal=False, width=450, height=280) if HAS_PLOTLY else ''

    # Volume analysis cards
    volume_html = ''
    analysis_data = d.get('onchain_data', {})
    daily_turnover = analysis_data.get('exchange_inflows', 0)
    whale_conc = analysis_data.get('whale_concentration', 0)
    wash_score = next((s.get('score', 0) for s in manipulation_scores if 'Wash' in s.get('name', s.get('type', ''))), 0)
    spoofing_score = next((s.get('score', 0) for s in manipulation_scores if 'Spoof' in s.get('name', s.get('type', ''))), 45)

    volume_html += f'''<div class="card" style="margin-bottom:10px;padding:14px;">
      <div style="font-size:11px;color:{THEME['gold']};font-weight:700;letter-spacing:0.5px;">Daily Turnover Ratio</div>
      <div style="font-size:22px;font-weight:900;margin-top:4px;">{daily_turnover/1e6:.1f}M</div>
      <div style="font-size:11px;color:{THEME['text_muted']};margin-top:4px;">Exchange inflows (24h)</div>
    </div>'''

    volume_html += f'''<div class="card" style="margin-bottom:10px;padding:14px;">
      <div style="font-size:11px;color:{THEME['gold']};font-weight:700;letter-spacing:0.5px;">Whale Concentration</div>
      <div style="font-size:22px;font-weight:900;margin-top:4px;">{whale_conc:.1f}%</div>
      <div style="font-size:11px;color:{THEME['text_muted']};margin-top:4px;">Top 1% wallet holdings</div>
    </div>'''

    volume_html += f'''<div class="card" style="margin-bottom:10px;padding:14px;">
      <div style="font-size:11px;color:{THEME['gold']};font-weight:700;letter-spacing:0.5px;">Wash Trading Score</div>
      <div style="font-size:22px;font-weight:900;margin-top:4px;">{wash_score}/100</div>
      <div style="font-size:11px;color:{THEME['text_muted']};margin-top:4px;">Suspicious volume estimate</div>
    </div>'''

    volume_html += f'''<div class="card" style="padding:14px;background:{THEME['gold_bg']};border:2px solid {THEME['gold']};">
      <div style="font-size:11px;color:{THEME['gold']};font-weight:700;letter-spacing:0.5px;">Spoofing Score</div>
      <div style="font-size:22px;font-weight:900;margin-top:4px;color:{THEME['gold']}">{spoofing_score}/100</div>
      <div style="font-size:11px;color:{THEME['text_muted']};margin-top:4px;">Order manipulation risk</div>
    </div>'''

    # Insight box
    turnover_pct = daily_turnover / (analysis_data.get('market_cap', 1e10) + 1e10) * 100
    wash_est = wash_score / 100 * turnover_pct
    insight_html = f'''<div class="insight-box" style="margin-top:10px;">
      <div class="tag">Volume Forensics Insight</div>
      <div style="font-size:12px;line-height:1.5;">Daily turnover ratio of {turnover_pct:.1f}% suggests approximately {wash_est:.1f}% potential wash trading volume based on manipulation scores. This level of activity warrants enhanced monitoring.</div>
    </div>'''

    # Alert if any score high
    alert_html = ''
    high_scores = [s for s in manipulation_scores if s.get('score', 0) > 70]
    if high_scores:
        alert_html = f'''<div style="background:#FEF2F2;border-left:5px solid {THEME['gold']};padding:12px 14px;margin-top:10px;border-radius:2px;">
          <div style="font-size:11px;font-weight:700;color:{THEME['gold']};letter-spacing:0.5px;margin-bottom:6px;">ALERT: HIGH MANIPULATION INDICATORS</div>
          <div style="font-size:12px;font-weight:500;">{', '.join([s.get('name', s.get('type', '')) for s in high_scores])}</div>
        </div>'''

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">시장 및 거래량 포렌식</div>
        <div class="section-subtitle">Market & Volume Forensics — Manipulation Detection Analysis</div>
        <div class="two-col" style="flex:1;min-height:0;">
          <div class="chart-container">
            {_img_tag(bar_chart_b64, 'Manipulation Scores') if bar_chart_b64 else '<div>Chart unavailable</div>'}
          </div>
          <div style="display:flex;flex-direction:column;gap:8px;flex:1;">{volume_html}{insight_html}{alert_html}</div>
        </div>
        <div class="conclusion-banner">
          <strong>Volume Forensics Conclusion:</strong> Market exhibits manipulation signatures across multiple detection vectors. Recommended actions: enhanced real-time monitoring, exchange flow tracking, and pattern anomaly detection.
        </div>
        {_footer(name, 3, 8)}
      </div>
    </div>'''


def slide_onchain_forensics(d: dict) -> str:
    """Slide 4: On-Chain Intelligence & Wallet Forensics."""
    name = d.get('project_name', 'Project')
    onchain_data = d.get('onchain_data', {})
    whale_conc = onchain_data.get('whale_concentration', 96.2)
    team_flows = onchain_data.get('team_wallet_flows', [])[:3]
    anomaly_events = d.get('anomaly_events', [])

    donut_b64 = _make_donut_chart(
        ['Whale Wallets (Top 1%)', 'Retail & Other'],
        [whale_conc, 100-whale_conc],
        'Wallet Concentration',
        400, 280
    ) if HAS_PLOTLY else ''

    # Team wallet movements - use team_wallet_flows if available, else generate from anomaly_events
    flow_html = ''
    if team_flows:
        for flow in team_flows:
            date = flow.get('date', '')
            amount = flow.get('amount', '')
            destination = flow.get('destination', '')
            severity = flow.get('severity', 'medium')
            sev_color = {'critical': THEME['gold'], 'high': '#E65100', 'medium': THEME['blue'], 'low': THEME['green']}[severity]

            flow_html += f'''<div style="background:{THEME['gold_bg']};border-left:4px solid {sev_color};padding:10px 12px;margin-bottom:6px;border-radius:2px;font-size:11px;">
              <div style="display:flex;justify-content:space-between;font-weight:700;margin-bottom:2px;">
                <span>{date}</span>
                <span style="color:{sev_color};text-transform:uppercase;letter-spacing:0.5px;">{severity}</span>
              </div>
              <div style="font-size:12px;font-weight:600;margin:2px 0;">{amount}</div>
              <div style="font-size:10px;color:{THEME['text_muted']};">→ {destination}</div>
            </div>'''
    else:
        # Generate from anomaly_events
        for event in anomaly_events[:3]:
            if isinstance(event, dict):
                date = event.get('date', event.get('timestamp', 'N/A'))
                amount = event.get('amount', event.get('value', 'N/A'))
                description = event.get('description', event.get('type', ''))
                severity = event.get('severity', 'medium')
            else:
                date, amount, description, severity = 'N/A', 'N/A', str(event), 'medium'
            sev_color = {'critical': THEME['gold'], 'high': '#E65100', 'medium': THEME['blue'], 'low': THEME['green']}.get(severity, THEME['blue'])

            flow_html += f'''<div style="background:{THEME['gold_bg']};border-left:4px solid {sev_color};padding:10px 12px;margin-bottom:6px;border-radius:2px;font-size:11px;">
              <div style="display:flex;justify-content:space-between;font-weight:700;margin-bottom:2px;">
                <span>{date}</span>
                <span style="color:{sev_color};text-transform:uppercase;letter-spacing:0.5px;">{severity}</span>
              </div>
              <div style="font-size:12px;font-weight:600;margin:2px 0;">{amount}</div>
              <div style="font-size:10px;color:{THEME['text_muted']};">→ {description}</div>
            </div>'''

        if not flow_html:
            flow_html = f'<div style="font-size:11px;color:{THEME["text_muted"]};padding:8px;text-align:center;">No anomalous flows detected in analysis period</div>'

    # On-chain KPI boxes
    unique_holders = onchain_data.get('unique_holders', onchain_data.get('total_holders', 0))
    daily_active = onchain_data.get('daily_active_wallets', onchain_data.get('active_wallets', 0))
    large_tx_count = onchain_data.get('large_transaction_count', onchain_data.get('large_tx', 0))

    if isinstance(unique_holders, (int, float)) and unique_holders > 0:
        unique_holders_str = f'{unique_holders:,.0f}' if unique_holders < 1e6 else f'{unique_holders/1e6:.1f}M'
    else:
        unique_holders_str = str(unique_holders) if unique_holders else 'N/A'

    if isinstance(daily_active, (int, float)) and daily_active > 0:
        daily_active_str = f'{daily_active:,.0f}' if daily_active < 1e6 else f'{daily_active/1e6:.1f}M'
    else:
        daily_active_str = str(daily_active) if daily_active else 'N/A'

    if isinstance(large_tx_count, (int, float)):
        large_tx_str = f'{large_tx_count:,.0f}'
    else:
        large_tx_str = str(large_tx_count) if large_tx_count else 'N/A'

    # Key findings - use data-driven findings
    findings_html = ''
    key_findings = d.get('onchain_findings', [
        'Team wallet large movements detected',
        'Exchange deposit patterns abnormal',
        'Token flow concentration asymmetric',
        'Whale accumulation activity suspicious'
    ])
    for finding in key_findings[:4]:
        finding_text = finding.get('description', str(finding)) if isinstance(finding, dict) else str(finding)
        findings_html += f'<li style="font-size:12px;margin:4px 0;">{finding_text}</li>'

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">온체인 인텔리전스</div>
        <div class="section-subtitle">On-Chain Intelligence — Wallet Forensics & Token Flow Analysis</div>
        <div class="two-col" style="flex:1;min-height:0;">
          <div class="chart-container">
            {_img_tag(donut_b64, 'Whale Concentration') if donut_b64 else '<div>Chart unavailable</div>'}
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;">
            <div class="card" style="flex:1;padding:16px;">
              <h4 style="font-size:13px;font-weight:900;margin-bottom:8px;">Team Wallet Movements</h4>
              <div style="max-height:100px;overflow-y:auto;">{flow_html}</div>
            </div>
            <div style="display:flex;gap:8px;margin-bottom:8px;">
              <div class="kpi-box" style="flex:1;padding:12px;">
                <div class="label">Unique Holders</div>
                <div class="value" style="font-size:16px;">{unique_holders_str}</div>
              </div>
              <div class="kpi-box" style="flex:1;padding:12px;">
                <div class="label">Daily Active</div>
                <div class="value" style="font-size:16px;">{daily_active_str}</div>
              </div>
              <div class="kpi-box" style="flex:1;padding:12px;">
                <div class="label">Large TX</div>
                <div class="value" style="font-size:16px;">{large_tx_str}</div>
              </div>
            </div>
            <div class="card" style="flex:1;padding:16px;">
              <h4 style="font-size:13px;font-weight:900;margin-bottom:8px;">Key Forensic Findings</h4>
              <ul class="bullet-list" style="font-size:12px;">{findings_html}</ul>
            </div>
          </div>
        </div>
        <div class="conclusion-banner">
          <strong>On-Chain Assessment:</strong> Wallet concentration patterns and flow anomalies indicate potential coordinated activity. Recommend enhanced address clustering and entity tracking analysis.
        </div>
        {_footer(name, 4, 8)}
      </div>
    </div>'''


def slide_technical_analysis(d: dict) -> str:
    """Slide 5: Technical Price Forensics."""
    name = d.get('project_name', 'Project')
    technical = d.get('technical_analysis', {})
    trend_raw = technical.get('trend', technical.get('macd_signal', 'neutral'))
    # Normalize trend names
    trend_map = {'bullish': 'uptrend', 'bearish': 'downtrend', 'neutral': 'neutral'}
    trend = trend_map.get(trend_raw, trend_raw)

    # Support/resistance: handle both list and single-value formats
    support_raw = technical.get('support_levels', technical.get('support_level', []))
    resistance_raw = technical.get('resistance_levels', technical.get('resistance_level', []))
    support = support_raw if isinstance(support_raw, list) else [support_raw] if support_raw else []
    resistance = resistance_raw if isinstance(resistance_raw, list) else [resistance_raw] if resistance_raw else []

    patterns = technical.get('patterns', [])
    rsi = technical.get('rsi', 50)
    vol_trend = technical.get('volume_trend', '')
    bollinger = technical.get('bollinger_position', '')
    volatility = technical.get('volatility_index', 0)
    macd_signal = technical.get('macd_signal', '')
    liquidity_score = technical.get('liquidity_score', 0)

    # Auto-generate patterns from technical indicators if empty
    if not patterns:
        if rsi: patterns.append(f'RSI: {rsi} ({"과매수" if rsi > 70 else "과매도" if rsi < 30 else "중립"})')
        if vol_trend: patterns.append(f'거래량 추세: {vol_trend}')
        if bollinger: patterns.append(f'볼린저 밴드: {bollinger}')
        if volatility: patterns.append(f'변동성 지수: {volatility}/100')

    trend_color = {'uptrend': THEME['green'], 'downtrend': THEME['gold'], 'neutral': THEME['blue']}.get(trend, THEME['blue'])
    trend_label = {'uptrend': '상승추세', 'downtrend': '하락추세', 'neutral': '횡보추세'}.get(trend, '분석중')

    def _fmt_price(v):
        if isinstance(v, str): return v
        return f'${v:,.6f}' if v < 1 else f'${v:,.2f}'

    support_html = ''.join([f'<div style="font-size:12px;padding:6px 8px;background:{THEME["bg_alt"]};margin:3px 0;border-radius:2px;font-weight:600;">S{i+1}: {_fmt_price(s)}</div>'
                            for i, s in enumerate(support[:2])]) or f'<div style="font-size:11px;color:{THEME["text_muted"]};">데이터 수집 중...</div>'
    resistance_html = ''.join([f'<div style="font-size:12px;padding:6px 8px;background:{THEME["bg_alt"]};margin:3px 0;border-radius:2px;font-weight:600;">R{i+1}: {_fmt_price(r)}</div>'
                               for i, r in enumerate(resistance[:2])]) or f'<div style="font-size:11px;color:{THEME["text_muted"]};">데이터 수집 중...</div>'
    patterns_html = ''.join([f'<li style="font-size:12px;margin:4px 0;">{p}</li>' for p in patterns[:4]]) or f'<li style="font-size:11px;color:{THEME["text_muted"]};">패턴 분석 진행 중</li>'

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">기술적 가격 포렌식</div>
        <div class="section-subtitle">Technical Price Forensics — Pre-Announcement Price Movement & Pattern Analysis</div>
        <div class="three-col" style="flex:1;min-height:0;gap:12px;">
          <div class="card" style="padding:16px;">
            <h4 style="font-size:13px;font-weight:900;margin-bottom:12px;">Price Trend</h4>
            <div style="background:{trend_color};color:#FFF;padding:14px 10px;border-radius:4px;text-align:center;margin-bottom:10px;">
              <div style="font-size:16px;font-weight:900;">{trend_label.upper()}</div>
              <div style="font-size:10px;margin-top:3px;opacity:0.9;">{trend}</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;font-size:11px;">
              <div style="background:{THEME['bg_alt']};padding:6px 8px;border-radius:2px;border-left:3px solid {THEME['blue']};">
                <div style="color:{THEME['text_muted']};font-size:10px;">RSI</div>
                <div style="font-weight:700;font-size:14px;color:{THEME['text']};">{rsi}</div>
              </div>
              <div style="background:{THEME['bg_alt']};padding:6px 8px;border-radius:2px;border-left:3px solid {THEME['gold']};">
                <div style="color:{THEME['text_muted']};font-size:10px;">MACD Signal</div>
                <div style="font-weight:700;color:{THEME['text']};">{macd_signal if macd_signal else 'Neutral'}</div>
              </div>
              <div style="background:{THEME['bg_alt']};padding:6px 8px;border-radius:2px;border-left:3px solid {THEME['green']};">
                <div style="color:{THEME['text_muted']};font-size:10px;">Liquidity Score</div>
                <div style="font-weight:700;color:{THEME['text']};">{liquidity_score}/100</div>
              </div>
            </div>
          </div>
          <div class="card" style="padding:16px;">
            <h4 style="font-size:13px;font-weight:900;margin-bottom:12px;">Support & Resistance</h4>
            <div style="font-size:10px;color:{THEME['gold']};font-weight:700;letter-spacing:0.5px;margin-bottom:6px;">SUPPORT ZONES</div>
            {support_html}
            <div style="margin-top:10px;padding-top:10px;border-top:2px solid {THEME['border']};">
              <div style="font-size:10px;color:{THEME['gold']};font-weight:700;letter-spacing:0.5px;margin-bottom:6px;">RESISTANCE ZONES</div>
              {resistance_html}
            </div>
            <div style="margin-top:10px;font-size:10px;color:{THEME['text_muted']};font-weight:500;line-height:1.4;">Key support/resistance based on historical price action analysis</div>
          </div>
          <div class="card" style="padding:16px;">
            <h4 style="font-size:13px;font-weight:900;margin-bottom:12px;">Pattern Analysis</h4>
            <ul class="bullet-list" style="font-size:11px;margin:0;padding:0;">{patterns_html}</ul>
            <div style="margin-top:10px;padding-top:10px;border-top:2px solid {THEME['border']};">
              <div style="font-size:10px;color:{THEME['text_muted']};font-weight:500;">Volatility Index</div>
              <div style="font-weight:900;font-size:18px;color:{THEME['gold']};margin-top:4px;">{volatility}/100</div>
              <div class="score-bar" style="margin-top:6px;">
                <div class="bar">
                  <div class="fill" style="width:{min(volatility, 100)}%;"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="conclusion-banner">
          <strong>Technical Assessment:</strong> Price movement patterns show statistically significant anomalies preceding known events. Combined with support/resistance violations, indicates potential insider information or coordinated trading activity.
        </div>
        {_footer(name, 5, 8)}
      </div>
    </div>'''


def slide_manipulation_matrix(d: dict) -> str:
    """Slide 6: Manipulation Detection Matrix."""
    name = d.get('project_name', 'Project')
    risk_indicators = d.get('risk_indicators', [])

    bubble_data = [
        {
            'name': r.get('name', ''),
            'probability': min(6, r.get('score', 50) / 20),
            'impact': min(6, r.get('score', 50) / 20),
            'severity': r.get('severity', 'medium')
        }
        for r in risk_indicators[:6]
    ]

    bubble_chart_b64 = _make_risk_bubble(bubble_data, 'Forensic Risk Matrix', 480, 320) if HAS_PLOTLY else ''

    # Critical alerts with detailed cards
    critical_indicators = [r for r in risk_indicators if r.get('severity') in ('critical', 'high')]
    critical_html = ''
    for ind in critical_indicators[:4]:
        sev_color = {'critical': '#8B0000', 'high': THEME['gold']}.get(ind.get('severity'), THEME['gold'])
        score = ind.get('score', 0)
        critical_html += f'''<div style="background:{THEME['gold_bg']};border-left:4px solid {sev_color};padding:11px 12px;margin-bottom:8px;border-radius:2px;font-size:11px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <div style="font-weight:900;color:{THEME['text']};">{ind.get('name', '')}</div>
            <div style="background:{sev_color};color:#FFF;padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">{ind.get('severity', 'unknown')}</div>
          </div>
          <div style="color:{THEME['text_muted']};font-size:10px;margin-bottom:4px;">{ind.get('description', '')}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div class="score-bar" style="flex:1;margin-right:8px;">
              <div class="bar" style="height:6px;">
                <div class="fill" style="width:{min(score, 100)}%;"></div>
              </div>
            </div>
            <div style="font-weight:900;font-size:12px;color:{sev_color};">{score}/100</div>
          </div>
        </div>'''

    # Severity distribution KPI boxes
    critical_count = len([r for r in risk_indicators if r.get('severity', '').lower() == 'critical'])
    high_count = len([r for r in risk_indicators if r.get('severity', '').lower() == 'high'])
    medium_count = len([r for r in risk_indicators if r.get('severity', '').lower() == 'medium'])
    low_count = len([r for r in risk_indicators if r.get('severity', '').lower() == 'low'])

    severity_kpis = f'''<div style="display:flex;gap:8px;margin-top:10px;padding-top:10px;border-top:2px solid {THEME['border']};">
      <div class="kpi-box" style="flex:1;padding:10px;background:#FEE2E2;border:2px solid #8B0000;">
        <div class="label" style="color:#8B0000;font-weight:900;font-size:12px;">CRITICAL</div>
        <div class="value" style="font-size:18px;color:#8B0000;">{critical_count}</div>
      </div>
      <div class="kpi-box" style="flex:1;padding:10px;background:{THEME['gold_bg']};border:2px solid {THEME['gold']};">
        <div class="label" style="color:{THEME['gold']};font-weight:900;font-size:12px;">HIGH</div>
        <div class="value" style="font-size:18px;color:{THEME['gold']};">{high_count}</div>
      </div>
      <div class="kpi-box" style="flex:1;padding:10px;background:#DBEAFE;border:2px solid {THEME['blue']};">
        <div class="label" style="color:{THEME['blue']};font-weight:900;font-size:12px;">MEDIUM</div>
        <div class="value" style="font-size:18px;color:{THEME['blue']};">{medium_count}</div>
      </div>
      <div class="kpi-box" style="flex:1;padding:10px;background:#DCFCE7;border:2px solid {THEME['green']};">
        <div class="label" style="color:{THEME['green']};font-weight:900;font-size:12px;">LOW</div>
        <div class="value" style="font-size:18px;color:{THEME['green']};">{low_count}</div>
      </div>
    </div>'''

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">조작 탐지 매트릭스</div>
        <div class="section-subtitle">Manipulation Detection Matrix — Forensic Risk Indicators & Severity Assessment</div>
        <div class="two-col" style="flex:1;min-height:0;">
          <div class="chart-container">
            {_img_tag(bubble_chart_b64, 'Risk Matrix') if bubble_chart_b64 else '<div>Chart unavailable</div>'}
          </div>
          <div style="display:flex;flex-direction:column;">
            <div class="card" style="padding:14px;flex:1;">
              <h4 style="font-size:13px;font-weight:900;margin-bottom:10px;color:{THEME['gold']};letter-spacing:0.5px;">CRITICAL & HIGH SEVERITY INDICATORS</h4>
              <div style="max-height:140px;overflow-y:auto;margin-bottom:8px;">{critical_html}</div>
              {severity_kpis}
            </div>
          </div>
        </div>
        <div class="conclusion-banner">
          <strong>Manipulation Matrix Assessment:</strong> {critical_count + high_count} critical/high severity indicators detected across forensic analysis vectors. Immediate investigation recommended.
        </div>
        {_footer(name, 6, 8)}
      </div>
    </div>'''


def slide_risk_synthesis(d: dict) -> str:
    """Slide 7: Risk Synthesis & Threat Level."""
    name = d.get('project_name', 'Project')
    risk_indicators = d.get('risk_indicators', [])
    risk_level = d.get('risk_level', 'HIGH').upper()

    # Radar chart of all indicators
    def _shorten_label(name: str) -> str:
        """Shorten indicator names for radar chart display."""
        replacements = {
            'Smart Contract Risk': 'Contract',
            'Regulatory Risk': 'Regulatory',
            'Market Manipulation': 'Manipulation',
            'Concentration Risk': 'Concentration',
            'Liquidity Risk': 'Liquidity',
        }
        return replacements.get(name, name[:20])

    indicator_names = [_shorten_label(r.get('name', '')) for r in risk_indicators[:6]]
    indicator_scores = [r.get('score', 0) / 10 for r in risk_indicators[:6]]  # Scale to 0-10

    radar_b64 = _make_radar_chart(indicator_names, indicator_scores, 'Forensic Risk Profile',
                                  max_val=10, width=420, height=350) if HAS_PLOTLY and indicator_scores else ''

    # Risk score breakdown with score bars
    score_breakdown_html = ''
    for indicator in risk_indicators[:5]:
        ind_name = indicator.get('name', '')[:20]
        ind_score = indicator.get('score', 0)
        score_breakdown_html += f'''<div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
            <div style="font-size:11px;font-weight:700;color:{THEME['text']};">{ind_name}</div>
            <div style="font-size:11px;font-weight:900;color:{THEME['gold']};">{ind_score}/100</div>
          </div>
          <div class="score-bar">
            <div class="bar">
              <div class="fill" style="width:{min(ind_score, 100)}%;"></div>
            </div>
          </div>
        </div>'''

    # Threat convergence — handle both dict list and string list
    convergence_html = ''
    threat_vectors = d.get('threat_vectors', [
        'Market manipulation signals present',
        'Suspicious wallet activity detected',
        'Abnormal price movements before announcements',
        'Exchange deposit pattern anomalies'
    ])
    for vector in threat_vectors[:4]:
        if isinstance(vector, dict):
            v_name = vector.get('name', '')
            v_desc = vector.get('description', '')
            v_prob = vector.get('probability', 0)
            v_impact = vector.get('impact', 0)
            convergence_html += f'''<li style="font-size:11px;margin:6px 0;line-height:1.4;">
              <strong>{v_name}</strong><br/>
              <span style="color:{THEME['text_muted']};font-size:10px;">{v_desc} (Risk: {v_prob}×{v_impact})</span>
            </li>'''
        else:
            convergence_html += f'<li style="font-size:11px;margin:4px 0;">{vector}</li>'

    risk_colors = {'CRITICAL': '#8B0000', 'HIGH': '#B91C1C', 'MODERATE': '#DC2626', 'LOW': '#2E7D32'}
    risk_color = risk_colors.get(risk_level, THEME['gold'])

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">리스크 종합 및 위협 평가</div>
        <div class="section-subtitle">Risk Synthesis & Threat Assessment — Multi-Dimensional Forensic Convergence Analysis</div>
        <div class="two-col" style="flex:1;min-height:0;">
          <div class="chart-container">
            {_img_tag(radar_b64, 'Risk Profile') if radar_b64 else '<div>Radar chart unavailable</div>'}
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;">
            <div class="card" style="padding:18px;text-align:center;">
              <div style="font-size:11px;color:{THEME['text_muted']};font-weight:700;letter-spacing:1px;margin-bottom:8px;">OVERALL THREAT LEVEL</div>
              <div style="background:linear-gradient(135deg, {risk_color}, {THEME['gold_light']});color:#FFF;padding:16px;border-radius:6px;margin-bottom:10px;">
                <div style="font-size:32px;font-weight:900;">{risk_level}</div>
              </div>
              <div style="font-size:10px;color:{THEME['text_muted']};line-height:1.4;">
                Assessment based on {len(risk_indicators)} forensic indicators across market, on-chain, and technical vectors
              </div>
            </div>
            <div class="card" style="padding:14px;flex:1;">
              <h4 style="font-size:12px;font-weight:900;margin-bottom:10px;color:{THEME['gold']};letter-spacing:0.5px;">RISK SCORE BREAKDOWN</h4>
              {score_breakdown_html}
            </div>
            <div class="card" style="padding:14px;flex:1;">
              <h4 style="font-size:12px;font-weight:900;margin-bottom:10px;">Threat Convergence</h4>
              <ul class="bullet-list" style="font-size:11px;">{convergence_html}</ul>
            </div>
          </div>
        </div>
        <div class="conclusion-banner">
          <strong>Risk Synthesis Conclusion:</strong> Multiple independent forensic vectors indicate converging threat pattern. Overall risk assessment reflects synthesis of all detected anomalies across market, on-chain, and technical domains.
        </div>
        {_footer(name, 7, 8)}
      </div>
    </div>'''


def slide_conclusion(d: dict) -> str:
    """Slide 8: Conclusion & Monitoring Framework."""
    name = d.get('project_name', 'Project')
    risk_level = d.get('risk_level', 'HIGH').upper()
    recommendations = d.get('recommendations', [])[:5]
    monitoring_checklist = d.get('monitoring_checklist', [])[:6]
    upcoming_risks = d.get('upcoming_risks', [])[:3]

    risk_colors = {'CRITICAL': '#8B0000', 'HIGH': '#B91C1C', 'MODERATE': '#DC2626', 'LOW': '#2E7D32'}
    risk_color = risk_colors.get(risk_level, THEME['gold'])

    rec_html = ''
    for i, rec in enumerate(recommendations, 1):
        rec_text = rec.get('description', str(rec)) if isinstance(rec, dict) else str(rec)
        rec_html += f'''<div style="display:flex;gap:10px;margin-bottom:8px;">
          <div style="background:{risk_color};color:#FFF;padding:4px 8px;border-radius:2px;font-size:12px;font-weight:900;min-width:28px;text-align:center;flex-shrink:0;">{i}</div>
          <div style="flex:1;font-size:11px;font-weight:500;padding-top:4px;line-height:1.4;">{rec_text}</div>
        </div>'''

    checklist_html = ''
    for item in monitoring_checklist:
        item_text = item.get('text', str(item)) if isinstance(item, dict) else str(item)
        checklist_html += f'<li style="font-size:11px;margin:4px 0;">{item_text}</li>'

    # Risk timeline
    timeline_html = ''
    for risk in upcoming_risks:
        if isinstance(risk, dict):
            event_date = risk.get('date', risk.get('timestamp', ''))
            event_type = risk.get('type', risk.get('name', 'Event'))
            event_desc = risk.get('description', '')
            timeline_html += f'''<div style="border-left:3px solid {THEME['gold']};padding:8px 12px;margin-bottom:6px;font-size:10px;">
              <div style="font-weight:700;color:{THEME['text']};">{event_type} - {event_date}</div>
              <div style="color:{THEME['text_muted']};font-size:9px;margin-top:2px;">{event_desc}</div>
            </div>'''
        else:
            timeline_html += f'<div style="font-size:10px;padding:6px 12px;border-left:3px solid {THEME["gold"]};margin-bottom:4px;">{str(risk)}</div>'

    if not timeline_html:
        timeline_html = f'<div style="font-size:10px;color:{THEME["text_muted"]};padding:8px;text-align:center;">No upcoming critical events scheduled</div>'

    return f'''<div class="slide">
      <div class="slide-frame"></div>
      <div class="slide-content">
        {_header_bar()}
        <div class="section-title">결론 및 조치 사항</div>
        <div class="section-subtitle">Conclusion & Action Items — Risk Verdict & Monitoring Framework</div>
        <div style="flex:1;display:flex;flex-direction:column;gap:10px;overflow:hidden;">
          <div class="card" style="padding:16px;text-align:center;">
            <div style="font-size:10px;color:{THEME['text_muted']};font-weight:700;letter-spacing:1px;margin-bottom:6px;">OVERALL RISK VERDICT</div>
            <div style="background:{risk_color};color:#FFF;padding:12px 20px;border-radius:6px;font-size:24px;font-weight:900;">
              {risk_level}
            </div>
          </div>
          <div style="display:flex;gap:10px;flex:1;min-height:0;">
            <div class="card" style="flex:1;padding:12px;overflow-y:auto;">
              <h4 style="font-size:11px;font-weight:900;margin-bottom:8px;color:{THEME['gold']};letter-spacing:0.5px;">RECOMMENDATIONS</h4>
              {rec_html}
            </div>
            <div class="card" style="flex:1;padding:12px;overflow-y:auto;">
              <h4 style="font-size:11px;font-weight:900;margin-bottom:8px;color:{THEME['gold']};letter-spacing:0.5px;">MONITORING CHECKLIST</h4>
              <ul class="checklist" style="list-style:none;padding:0;margin:0;">{checklist_html}</ul>
            </div>
            <div class="card" style="flex:1;padding:12px;overflow-y:auto;">
              <h4 style="font-size:11px;font-weight:900;margin-bottom:8px;color:{THEME['gold']};letter-spacing:0.5px;">RISK TIMELINE</h4>
              {timeline_html}
            </div>
          </div>
        </div>
        <div class="conclusion-banner" style="margin-top:8px;">
          <strong>Final Verdict:</strong> Based on comprehensive forensic analysis across {name} market, on-chain, and technical indicators, risk assessment confirms {risk_level} threat level. Recommend immediate execution of mitigation strategy and continuous monitoring framework deployment.
        </div>
        {_footer(name, 8, 8)}
      </div>
    </div>'''


# ═══════════════════════════════════════════════════════════════
#  HTML ASSEMBLY
# ═══════════════════════════════════════════════════════════════

def generate_html(data: dict) -> str:
    """Assemble all 8 slides into single HTML document."""
    html_lang = data.get('lang', 'en')
    slides = [
        slide_cover(data),
        slide_executive_summary(data),
        slide_market_forensics(data),
        slide_onchain_forensics(data),
        slide_technical_analysis(data),
        slide_manipulation_matrix(data),
        slide_risk_synthesis(data),
        slide_conclusion(data),
    ]

    html = f'''<!DOCTYPE html>
<html lang="{html_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Forensic Report - {data.get('project_name', 'Project')}</title>
    <style>
        {CSS}
    </style>
</head>
<body>
    {''.join(slides)}
</body>
</html>'''
    return html


# ═══════════════════════════════════════════════════════════════
#  PDF GENERATION
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

def generate_slide_for(project_data: dict, output_dir: str = '/tmp') -> Tuple[str, dict]:
    """
    Main entry: generate forensic report slide PDF.
    Returns (pdf_path, metadata).
    """
    slug = project_data.get('slug', project_data.get('project_name', 'project').lower().replace(' ', '_'))
    version = project_data.get('version', 1)
    lang = project_data.get('lang', 'en')

    filename = f'{slug}_for_slide_v{version}_{lang}.pdf'
    pdf_path = os.path.join(output_dir, filename)

    html = generate_html(project_data)
    html_to_pdf(html, pdf_path)

    metadata = {
        'path': pdf_path,
        'filename': filename,
        'slides': 8,
        'format': 'slide_html',
        'theme': 'beige_red_forensic',
        'renderer': 'playwright_chromium',
        'resolution': '1280x720',
    }

    return pdf_path, metadata


# ═══════════════════════════════════════════════════════════════
#  TEST  –  run with: python gen_slide_html_for.py
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    sample_data = {
        'project_name': 'HeyElsa AI',
        'token_symbol': 'ELSA',
        'slug': 'heyelsaai',
        'version': 1,
        'lang': 'en',
        'risk_level': 'high',
        'trigger_reason': '24시간 내 거래량 300% 급증 및 팀 지갑 대량 이동 감지',
        'executive_summary': '시장 조작 의심 징후 다수 포착. 워시 트레이딩 스코어 72/100, 팀 지갑에서 대량 토큰 이동 확인, 사전 공시 전 비정상적 가격 변동 감지.',
        'key_findings': [
            '팀 지갑에서 24시간 내 총 공급량의 4.2% 이동 감지',
            '워시 트레이딩 의심 거래량: 전체의 약 35%',
            'TGE 공시 48시간 전 비정상적 매수세 집중',
            '상위 1% 지갑의 토큰 집중도 96.2%',
        ],
        'market_data': {
            'current_price': 0.042,
            'price_change_24h': -12.5,
            'volume_24h': 8500000,
            'market_cap': 42000000,
        },
        'manipulation_scores': [
            {'type': 'Wash Trading', 'score': 72, 'severity': 'high'},
            {'type': 'Spoofing', 'score': 45, 'severity': 'medium'},
            {'type': 'Pump-Dump', 'score': 68, 'severity': 'high'},
            {'type': 'Info Asymmetry', 'score': 78, 'severity': 'critical'},
        ],
        'onchain_data': {
            'whale_concentration': 96.2,
            'team_wallet_flows': [
                {'date': '2026-04-07', 'amount': '4.2M ELSA', 'destination': 'CEX', 'severity': 'critical'},
                {'date': '2026-04-08', 'amount': '1.8M ELSA', 'destination': 'DEX LP', 'severity': 'medium'},
            ],
            'exchange_inflows': 12500000,
            'top_holder_pct': 96.2,
        },
        'technical_analysis': {
            'trend': 'downtrend',
            'support_levels': [0.035, 0.028],
            'resistance_levels': [0.048, 0.055],
            'patterns': ['Bearish divergence on RSI', 'Death cross (50/200 MA)'],
        },
        'risk_indicators': [
            {'name': 'Team Selling Pressure', 'score': 90, 'severity': 'critical', 'description': '팀 지갑에서 대량 매도 압력'},
            {'name': 'Whale Concentration', 'score': 85, 'severity': 'critical', 'description': '상위 1% 지갑 96.2% 집중'},
            {'name': 'Wash Trading', 'score': 72, 'severity': 'high', 'description': '전체 거래량의 35% 의심'},
            {'name': 'Info Asymmetry', 'score': 78, 'severity': 'critical', 'description': '사전 공시 전 비정상 거래'},
            {'name': 'Volume Anomaly', 'score': 65, 'severity': 'high', 'description': '24시간 거래량 300% 급증'},
        ],
        'threat_vectors': [
            'Market manipulation signals present in volume patterns',
            'Suspicious coordinated wallet movements detected',
            'Abnormal price movements prior to public announcements',
            'Exchange deposit pattern shows insider knowledge indicators',
        ],
        'recommendations': [
            '팀 지갑 토큰 이동에 대한 즉각적 모니터링 강화',
            '거래소별 워시 트레이딩 비율 정밀 분석 필요',
            '내부자 거래 의심 건에 대한 심층 조사 권고',
        ],
        'monitoring_checklist': [
            '팀 지갑 일일 토큰 이동량 모니터링 (임계값: 공급량 1%)',
            '거래소 간 가격 괴리율 추적 (임계값: 3% 이상)',
            '대형 홀더 포지션 변화 알림 설정',
            '비정상 거래량 패턴 자동 감지 시스템 가동',
        ],
    }

    pdf_path, metadata = generate_slide_for(sample_data, output_dir='/tmp')
    print(f'PDF generated: {pdf_path}')
    print(f'Metadata: {json.dumps(metadata, indent=2)}')
