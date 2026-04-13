"""
BCE Lab Report Pipeline — Base PDF rendering utilities
Shared styles, cover pages, headers/footers, table builders for all 3 report types.
"""
import os
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from config import COLORS, ORG_NAME, ORG_FULL, DOMAIN, COPYRIGHT_YEAR, REPORT_TYPES

W, H = A4

# ═══════════════════════════════════════════
# CJK FONT SUPPORT
# ═══════════════════════════════════════════
# Language → (regular_font, bold_font)
# CJK CID fonts don't have true bold variants; we use the best available.
_CJK_FONTS = {
    'ko': ('HYGothic-Medium', 'HYGothic-Medium'),
    'ja': ('HeiseiKakuGo-W5', 'HeiseiKakuGo-W5'),
    'zh': ('STSong-Light', 'STSong-Light'),
}

_CJK_REGISTERED = set()


def _register_cjk_font(lang: str):
    """Register CID font for a CJK language (idempotent)."""
    if lang not in _CJK_FONTS or lang in _CJK_REGISTERED:
        return
    regular, bold = _CJK_FONTS[lang]
    for name in {regular, bold}:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(name))
        except Exception:
            pass  # Already registered or unavailable
    _CJK_REGISTERED.add(lang)


def get_fonts_for_lang(lang: str = 'en'):
    """
    Return (regular, bold, italic) font names appropriate for language.
    For CJK languages, returns CID fonts that can render native characters.
    For Latin languages, returns Helvetica family.
    """
    if lang in _CJK_FONTS:
        _register_cjk_font(lang)
        regular, bold = _CJK_FONTS[lang]
        return regular, bold, regular  # CID fonts don't have italic
    return 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'


# ═══════════════════════════════════════════
# COLOR HELPERS
# ═══════════════════════════════════════════
def C(hex_key):
    """Get HexColor from COLORS dict, raw hex string, or pass through Color objects."""
    if not isinstance(hex_key, str):
        return hex_key  # Already a Color object
    if hex_key.startswith('#'):
        return HexColor(hex_key)
    return HexColor(COLORS.get(hex_key, '#4F46E5'))


# ═══════════════════════════════════════════
# STYLES FACTORY
# ═══════════════════════════════════════════
def make_styles(lang: str = 'en'):
    """
    Build paragraph styles for PDF generation.
    Automatically selects CJK-compatible fonts for ko, ja, zh.
    """
    regular, bold, italic = get_fonts_for_lang(lang)

    s = {}
    s['body'] = ParagraphStyle(
        'body', fontName=regular, fontSize=9.5, leading=14,
        alignment=TA_JUSTIFY, spaceAfter=6, textColor=C('slate_800'))
    s['body_small'] = ParagraphStyle(
        'body_small', parent=s['body'], fontSize=8.5, leading=12, spaceAfter=4)
    s['h1'] = ParagraphStyle(
        'h1', fontName=bold, fontSize=18, leading=22,
        textColor=C('indigo'), spaceAfter=4, spaceBefore=16)
    s['h2'] = ParagraphStyle(
        'h2', fontName=bold, fontSize=13, leading=16,
        textColor=C('slate_800'), spaceAfter=4, spaceBefore=12)
    s['h3'] = ParagraphStyle(
        'h3', fontName=bold, fontSize=10.5, leading=14,
        textColor=C('slate_700'), spaceAfter=3, spaceBefore=8)
    s['caption'] = ParagraphStyle(
        'caption', fontName=italic, fontSize=8, leading=10,
        alignment=TA_CENTER, textColor=C('mid_gray'), spaceAfter=8, spaceBefore=2)
    s['callout'] = ParagraphStyle(
        'callout', fontName=bold, fontSize=9.5, leading=13,
        textColor=C('indigo'), alignment=TA_LEFT, spaceAfter=6,
        leftIndent=12)
    s['bullet'] = ParagraphStyle(
        'bullet', parent=s['body'], leftIndent=18, bulletIndent=6, spaceAfter=4)
    s['toc'] = ParagraphStyle(
        'toc', fontName=regular, fontSize=10, leading=18, textColor=C('slate_700'), leftIndent=16)
    s['toc_section'] = ParagraphStyle(
        'toc_section', fontName=bold, fontSize=10, leading=18, textColor=C('slate_800'), leftIndent=8)
    s['disclaimer'] = ParagraphStyle(
        'disclaimer', fontName=regular, fontSize=7.5, leading=10,
        textColor=C('mid_gray'), alignment=TA_JUSTIFY, spaceAfter=4)
    s['th'] = ParagraphStyle(
        'th', fontName=bold, fontSize=8.5, leading=11,
        textColor=C('white'), alignment=TA_CENTER)
    s['tc'] = ParagraphStyle(
        'tc', fontName=regular, fontSize=8.5, leading=11,
        textColor=C('slate_800'), alignment=TA_CENTER)
    s['tc_left'] = ParagraphStyle(
        'tc_left', fontName=regular, fontSize=8.5, leading=11,
        textColor=C('slate_800'), alignment=TA_LEFT)
    s['tc_bold'] = ParagraphStyle(
        'tc_bold', fontName=bold, fontSize=8.5, leading=11,
        textColor=C('slate_800'), alignment=TA_LEFT)
    # Forensic-specific: red accent
    s['h1_forensic'] = ParagraphStyle(
        'h1_for', fontName=bold, fontSize=18, leading=22,
        textColor=C('forensic_red'), spaceAfter=4, spaceBefore=16)
    s['callout_forensic'] = ParagraphStyle(
        'callout_for', fontName=bold, fontSize=9.5, leading=13,
        textColor=C('forensic_red'), alignment=TA_LEFT, spaceAfter=6, leftIndent=12)
    return s


# ═══════════════════════════════════════════
# FLOWABLE HELPERS
# ═══════════════════════════════════════════
def accent_line(color='indigo'):
    return HRFlowable(width="100%", thickness=1.5, color=C(color), spaceAfter=8, spaceBefore=2)

def thin_line():
    return HRFlowable(width="100%", thickness=0.5, color=C('light_gray'), spaceAfter=6, spaceBefore=6)

def section_header(text, styles, report_type='econ'):
    style_key = 'h1_forensic' if report_type == 'for' else 'h1'
    color = 'forensic_red' if report_type == 'for' else 'indigo'
    return [Spacer(1, 4), Paragraph(text, styles[style_key]), accent_line(color)]


# ═══════════════════════════════════════════
# TABLE BUILDER
# ═══════════════════════════════════════════
def build_table(headers, rows=None, col_widths=None, styles=None, first_col_bold=True, header_color='indigo'):
    """Build a professional table.
    Can be called as:
      build_table(headers_list, rows_list, col_widths, styles)
    Or with combined data (first row = headers):
      build_table(all_data, col_widths=..., styles=...)
    """
    s = styles
    # Handle case where rows is actually col_widths (combined data passed as single list)
    if rows is not None and not isinstance(rows[0] if rows else [], list):
        # rows looks like col_widths — shift args
        col_widths = rows
        rows = headers[1:]
        headers = headers[0]
    elif rows is None:
        # All data in headers, first row is header
        rows = headers[1:]
        headers = headers[0]

    data = [[Paragraph(h, s['th']) for h in headers]]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i == 0 and first_col_bold:
                cells.append(Paragraph(str(cell), s['tc_bold']))
            else:
                cells.append(Paragraph(str(cell), s['tc'] if i > 0 else s['tc_left']))
        data.append(cells)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    hc = C(header_color)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), hc),
        ('TEXTCOLOR', (0, 0), (-1, 0), C('white')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, C('light_gray')),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, hc),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), C('slate_50')))
    t.setStyle(TableStyle(style_cmds))
    return t


# ═══════════════════════════════════════════
# COVER PAGE TEMPLATE
# ═══════════════════════════════════════════
def _get_report_title(rt: dict, lang: str) -> str:
    """Get localized report title. Falls back through: lang → en."""
    key = f'name_{lang}'
    if key in rt:
        return rt[key]
    return rt.get('name_en', rt.get('name_ko', ''))


def draw_cover_econ_mat(c, doc, project_name, report_type, version, lang,
                         subtitle='', key_metrics=None, rating=None):
    """Standard cover for ECON and MAT reports."""
    c.saveState()
    rt = REPORT_TYPES[report_type]
    _regular, _bold, _ = get_fonts_for_lang(lang)

    # Dark background
    c.setFillColor(C('dark_bg'))
    c.rect(0, 0, W, H, fill=True, stroke=False)

    # Top accent bar
    c.setFillColor(C('indigo'))
    c.rect(0, H - 12*mm, W, 12*mm, fill=True, stroke=False)

    # Logo
    c.setFillColor(HexColor('#6366F1'))
    c.roundRect(30*mm, H - 50*mm, 14*mm, 14*mm, 3*mm, fill=True, stroke=False)
    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(37*mm, H - 46*mm, 'B')

    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 14)
    c.drawString(48*mm, H - 42*mm, ORG_NAME)
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 9)
    c.drawString(48*mm, H - 49*mm, ORG_FULL)

    # Classification badge
    badge_text = rt['code']
    c.setStrokeColor(HexColor('#6366F1'))
    c.setLineWidth(1)
    c.setFillColor(Color(0.31, 0.27, 0.89, alpha=0.15))
    c.roundRect(W - 65*mm, H - 45*mm, 35*mm, 9*mm, 2*mm, fill=True, stroke=True)
    c.setFillColor(HexColor('#A5B4FC'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(W - 47.5*mm, H - 42*mm, badge_text)

    # Title — project name (always Latin-safe)
    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 32)
    c.drawString(30*mm, H - 100*mm, project_name)

    # Report type title — uses CJK font for CJK languages
    c.setFillColor(HexColor('#818CF8'))
    c.setFont(_bold, 20)
    title_line2 = _get_report_title(rt, lang)
    c.drawString(30*mm, H - 120*mm, title_line2)

    c.setFont('Helvetica-Bold', 16)
    c.drawString(30*mm, H - 138*mm, f"Version {version}")

    if subtitle:
        c.setFillColor(C('mid_gray'))
        c.setFont('Helvetica', 11)
        c.drawString(30*mm, H - 158*mm, subtitle)

    # Accent line
    c.setStrokeColor(C('indigo'))
    c.setLineWidth(2)
    c.line(30*mm, H - 168*mm, 90*mm, H - 168*mm)

    # Key metrics (if provided)
    if key_metrics:
        box_w = 35*mm
        start_x = 30*mm
        start_y = H - 210*mm
        for i, (val, label) in enumerate(key_metrics[:4]):
            x = start_x + i * (box_w + 5*mm)
            c.setFillColor(Color(0.31, 0.27, 0.89, alpha=0.1))
            c.setStrokeColor(HexColor('#334155'))
            c.setLineWidth(0.5)
            c.roundRect(x, start_y, box_w, 25*mm, 2*mm, fill=True, stroke=True)
            c.setFillColor(C('white'))
            c.setFont('Helvetica-Bold', 16)
            c.drawCentredString(x + box_w/2, start_y + 13*mm, str(val))
            c.setFillColor(C('mid_gray'))
            c.setFont('Helvetica', 7)
            c.drawCentredString(x + box_w/2, start_y + 5*mm, label)

    # Footer
    c.setFillColor(C('slate_700'))
    c.rect(0, 0, W, 30*mm, fill=True, stroke=False)
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 8)
    today = datetime.now().strftime('%B %d, %Y')
    c.drawString(30*mm, 18*mm, f'Published: {today}')
    c.drawString(30*mm, 12*mm, f'Report ID: {rt["code"]}-{project_name.upper()[:8]}-v{version}')
    c.drawRightString(W - 30*mm, 18*mm, f'Version {version}.0')
    c.drawRightString(W - 30*mm, 12*mm, DOMAIN)
    c.setFillColor(HexColor('#64748B'))
    c.setFont('Helvetica', 7)
    c.drawCentredString(W/2, 5*mm, f'\u00a9 {COPYRIGHT_YEAR} {ORG_NAME}. All rights reserved. For authorized subscribers only.')

    c.restoreState()


def draw_cover_forensic(c, doc, project_name, token_symbol, risk_level, trigger_reason, version, lang):
    """Red-themed cover for Forensic reports."""
    c.saveState()
    _regular, _bold, _ = get_fonts_for_lang(lang)

    # Dark red background
    c.setFillColor(HexColor('#1C1917'))
    c.rect(0, 0, W, H, fill=True, stroke=False)

    # Top red accent bar
    c.setFillColor(C('forensic_red'))
    c.rect(0, H - 14*mm, W, 14*mm, fill=True, stroke=False)
    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(W/2, H - 10*mm, 'CONFIDENTIAL: MARKET RISK ALERT')

    # Logo
    c.setFillColor(C('forensic_red'))
    c.roundRect(30*mm, H - 50*mm, 14*mm, 14*mm, 3*mm, fill=True, stroke=False)
    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(37*mm, H - 46*mm, 'B')

    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 14)
    c.drawString(48*mm, H - 42*mm, ORG_NAME)
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 9)
    c.drawString(48*mm, H - 49*mm, 'Forensic Analysis Division')

    # Risk level badge
    risk_colors = {
        'critical': '#DC2626', 'warning': '#D97706', 'watch': '#16A34A'
    }
    badge_color = risk_colors.get(risk_level, '#DC2626')
    c.setFillColor(HexColor(badge_color))
    c.roundRect(W - 55*mm, H - 45*mm, 25*mm, 9*mm, 2*mm, fill=True, stroke=False)
    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(W - 42.5*mm, H - 42*mm, risk_level.upper())

    # Title
    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 32)
    c.drawString(30*mm, H - 100*mm, project_name)
    c.setFont('Helvetica-Bold', 20)
    c.drawString(30*mm, H - 120*mm, f'${token_symbol}')

    c.setFillColor(C('forensic_red'))
    c.setFont('Helvetica-Bold', 16)
    c.drawString(30*mm, H - 145*mm, 'Forensic Alert Report')

    # Trigger reason
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 10)
    c.drawString(30*mm, H - 165*mm, f'Trigger: {trigger_reason}')

    # Footer
    c.setFillColor(HexColor('#292524'))
    c.rect(0, 0, W, 30*mm, fill=True, stroke=False)
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 8)
    today = datetime.now().strftime('%B %d, %Y')
    c.drawString(30*mm, 18*mm, f'Published: {today}')
    c.drawRightString(W - 30*mm, 18*mm, f'Version {version}.0')
    c.setFillColor(HexColor('#64748B'))
    c.setFont('Helvetica', 7)
    c.drawCentredString(W/2, 5*mm, f'\u00a9 {COPYRIGHT_YEAR} {ORG_NAME}. CONFIDENTIAL — Authorized subscribers only.')

    c.restoreState()


# ═══════════════════════════════════════════
# HEADER / FOOTER TEMPLATES
# ═══════════════════════════════════════════
def make_header_footer(project_name, report_type):
    """Returns a function for later-page headers/footers."""
    rt = REPORT_TYPES[report_type]
    bar_color = C('forensic_red') if report_type == 'for' else C('indigo')
    classification = 'CONFIDENTIAL: MARKET RISK ALERT' if report_type == 'for' else rt['code']

    def _header_footer(c, doc):
        c.saveState()
        # Top bar
        c.setFillColor(bar_color)
        c.rect(0, H - 8*mm, W, 8*mm, fill=True, stroke=False)
        # Header text
        c.setFillColor(C('slate_600'))
        c.setFont('Helvetica', 7)
        c.drawString(20*mm, H - 15*mm, f'{ORG_NAME}  |  {project_name}')
        c.drawRightString(W - 20*mm, H - 15*mm, classification)
        # Footer line
        c.setStrokeColor(C('light_gray'))
        c.setLineWidth(0.5)
        c.line(20*mm, 15*mm, W - 20*mm, 15*mm)
        # Footer text
        c.setFillColor(C('mid_gray'))
        c.setFont('Helvetica', 6.5)
        c.drawString(20*mm, 10*mm, f'\u00a9 {COPYRIGHT_YEAR} {ORG_NAME}  |  {DOMAIN}')
        c.drawRightString(W - 20*mm, 10*mm, f'Page {doc.page}')
        c.restoreState()

    return _header_footer


# ═══════════════════════════════════════════
# DISCLAIMER SECTION
# ═══════════════════════════════════════════
def add_disclaimer(story, styles, report_type='econ'):
    story.extend(section_header('Disclaimer & Legal', styles, report_type))

    disclaimers = [
        '<b>General Disclaimer:</b> This report is published by BCE Lab for informational purposes only and does not constitute investment advice, a solicitation, or an offer to buy or sell any securities or financial instruments.',
        '<b>Risk Warning:</b> Cryptocurrency investments are subject to high market risk and volatility. The value of digital assets can fluctuate significantly, and investors may lose their entire investment.',
        '<b>Forward-Looking Statements:</b> This report may contain forward-looking statements based on current assumptions that may prove incorrect. Actual results may differ materially.',
        f'<b>Distribution:</b> This report is intended for authorized subscribers of {ORG_NAME} only. Reproduction or redistribution without prior written consent is strictly prohibited.',
    ]

    if report_type == 'for':
        disclaimers.insert(1,
            '<b>Confidentiality:</b> This Forensic Alert Report contains sensitive market intelligence. '
            'Unauthorized disclosure may violate applicable securities regulations and BCE Lab terms of service.')

    for d in disclaimers:
        story.append(Paragraph(d, styles['disclaimer']))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 12))
    story.append(thin_line())
    story.append(Paragraph(
        f'\u00a9 {COPYRIGHT_YEAR} {ORG_NAME} ({DOMAIN}). All rights reserved.',
        ParagraphStyle('final', fontName='Helvetica', fontSize=8,
                       textColor=C('mid_gray'), alignment=TA_CENTER)))


# ═══════════════════════════════════════════
# DOC BUILDER
# ═══════════════════════════════════════════
def create_doc(output_path):
    """Create a SimpleDocTemplate with standard margins."""
    return SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=22*mm, bottomMargin=22*mm)

USABLE_W = W - 40*mm  # 20mm margins each side
