"""
BCE Lab Report Pipeline — Base PDF rendering utilities
Shared styles, cover pages, headers/footers, table builders for all 3 report types.
Tiger Research-inspired design with Noto Sans KR typography.
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
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

from config import COLORS, ORG_NAME, ORG_FULL, DOMAIN, COPYRIGHT_YEAR, REPORT_TYPES

W, H = A4

# ═══════════════════════════════════════════
# FONT REGISTRATION (Noto Sans KR TTF support)
# ═══════════════════════════════════════════

# Resolve fonts directory relative to this script
# Try multiple paths: relative to project root, or at session root
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))  # Project blockchain-economics-lab/

# Check for fonts in: project/fonts, scripts/fonts, or session/fonts
_FONTS_CANDIDATES = [
    os.path.join(_PROJECT_ROOT, 'fonts'),  # /blockchain-economics-lab/fonts
    os.path.join(_SCRIPT_DIR, 'fonts'),    # /pipeline/fonts
    os.path.abspath(os.path.join(_SCRIPT_DIR, '../../../fonts')),  # /sessions/amazing-cool-davinci/fonts
]

_FONTS_DIR = None
for candidate in _FONTS_CANDIDATES:
    if os.path.exists(candidate):
        _FONTS_DIR = candidate
        break

if _FONTS_DIR is None:
    # Fallback to the most common location
    _FONTS_DIR = os.path.join(_PROJECT_ROOT, 'fonts')

# Per-script font files. KR subset lacks JP kana + SC chars, so each CJK
# language gets its own Noto Sans variant. OTF files are loaded via TTFont.
_NOTO_CJK_FONTS = {
    'KR': {
        'regular': 'NotoSansKR-Regular.ttf',
        'bold':    'NotoSansKR-Bold.ttf',
        'medium':  'NotoSansKR-Medium.ttf',
    },
    # Use static-weight TTFs (from Google Fonts gstatic). Variable TTFs
    # embed but lose the Unicode cmap round-trip that downstream tools
    # (pdfplumber, copy-paste, search) rely on.
    'JP': {
        'regular': 'NotoSansJP-Regular-Static.ttf',
        'bold':    'NotoSansJP-Bold-Static.ttf',
    },
    'SC': {
        'regular': 'NotoSansSC-Regular-Static.ttf',
        'bold':    'NotoSansSC-Bold-Static.ttf',
    },
}

_FONT_REGISTRY = {}


_CID_FALLBACKS = {
    'JP': 'HeiseiMin-W3',   # Adobe built-in, ToUnicode-clean
    'SC': 'STSong-Light',
    # KR has a full Hangul TTF — no CID fallback needed
}


def _register_cid_fallback(variant: str) -> str | None:
    """Register built-in Adobe CID font for JP/SC so text extracts cleanly
    from embedded subsets. Returns registered font name or None."""
    cid_name = _CID_FALLBACKS.get(variant)
    if not cid_name:
        return None
    key = f'CID-{cid_name}'
    if key in _FONT_REGISTRY:
        return cid_name
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(cid_name))
        _FONT_REGISTRY[key] = cid_name
        return cid_name
    except Exception as e:
        print(f"Warning: Failed to register CID {cid_name}: {e}")
        return None


def _register_noto_variant(variant: str):
    """Register one Noto Sans script variant (KR/JP/SC). Idempotent.

    For all variants: prefers bundled Static TTF files. TTFs handle both
    CJK and Latin glyphs correctly in mixed-script text and support
    pdfplumber text extraction.

    OPS-006 lesson: Adobe CID fonts (HeiseiMin-W3, STSong-Light) misrender
    Latin bytes in mixed Korean/English table cells as UTF-16 high-surrogate
    codepoints, causing fallback_boxes QA failures. TTF avoids this entirely.
    CID fonts are only used as last resort if TTF files are missing.
    """
    family = f'NotoSans{variant}'
    if f'{family}-Regular' in _FONT_REGISTRY:
        return True

    # TTF path (preferred — handles Latin + CJK correctly)
    files = _NOTO_CJK_FONTS.get(variant, {})
    for weight, filename in files.items():
        font_path = os.path.join(_FONTS_DIR, filename)
        if not os.path.exists(font_path):
            continue
        try:
            font_name = f'{family}-{weight.capitalize()}'
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            _FONT_REGISTRY[font_name] = font_path
        except Exception as e:
            print(f"Warning: Failed to register {filename}: {e}")
    reg = f'{family}-Regular'
    bold = f'{family}-Bold'
    if reg in _FONT_REGISTRY and bold in _FONT_REGISTRY:
        registerFontFamily(
            family,
            normal=reg, bold=bold,
            italic=reg, boldItalic=bold,
        )
        return True

    # CID fallback (last resort if TTF files missing)
    if variant in _CID_FALLBACKS:
        cid = _register_cid_fallback(variant)
        if cid:
            _FONT_REGISTRY[f'{family}-Regular'] = cid
            _FONT_REGISTRY[f'{family}-Bold'] = cid
            registerFontFamily(family, normal=cid, bold=cid,
                               italic=cid, boldItalic=cid)
            return True

    return False


# Back-compat alias
def _register_noto_sans_kr():
    _register_noto_variant('KR')


def get_fonts_for_lang(lang: str = 'en'):
    """
    Return (regular, bold, medium) font names appropriate for language.
    - ko  → NotoSansKR
    - ja  → NotoSansJP
    - zh  → NotoSansSC
    - en/fr/es/de → NotoSansSC (Latin + CJK + arrows all in one file, so
      CJK fragments left over from source render correctly instead of as tofu)
    """
    variant = None
    if lang == 'ko':
        variant = 'KR'
    elif lang == 'ja':
        variant = 'JP'
    else:
        # zh + Latin langs all use SC (good Latin + full CJK + symbols)
        variant = 'SC'
    ok = _register_noto_variant(variant)
    if ok:
        family = f'NotoSans{variant}'
        # Always register the other two variants as additional fallback fonts
        for v in ('KR', 'JP', 'SC'):
            if v != variant:
                _register_noto_variant(v)

        def _resolve(key: str) -> str:
            val = _FONT_REGISTRY.get(key, key)
            # CID aliases store the CID font name; TTFs store a file path
            if isinstance(val, str) and not val.endswith('.ttf') \
                    and not val.endswith('.otf'):
                return val
            return key

        reg = _resolve(f'{family}-Regular')
        bold = _resolve(f'{family}-Bold')
        medium_key = f'{family}-Medium'
        medium = _resolve(medium_key) if medium_key in _FONT_REGISTRY else reg
        return reg, bold, medium
    if _register_noto_variant('KR'):
        return 'NotoSansKR-Regular', 'NotoSansKR-Bold', 'NotoSansKR-Medium'
    return 'Helvetica', 'Helvetica-Bold', 'Helvetica'


# Regex to detect CJK + halfwidth arrows + box-drawing characters
_CJK_RUN_RE = None


def wrap_cjk_runs(text: str, lang: str = 'en') -> str:
    """Wrap CJK / symbol runs in a <font name='...'> tag so that glyphs missing
    from the default font (e.g. Latin Helvetica or NotoSansSC for Hangul)
    render correctly. Called AFTER XML escaping.
    """
    global _CJK_RUN_RE
    if _CJK_RUN_RE is None:
        import re as _re
        # Hangul + CJK ideographs + kana + arrows + box-drawing + CJK punct
        _CJK_RUN_RE = _re.compile(
            r'([\u3000-\u303F\u3040-\u30FF\u31F0-\u31FF\u3200-\u32FF'
            r'\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF'
            r'\u2190-\u21FF\u2500-\u257F\uFF00-\uFFEF]+)'
        )
    # Which font to use for a given run depends on the dominant block.
    # _FONT_REGISTRY values are the actual registered reportlab font names;
    # for CID-aliased variants they map to e.g. 'HeiseiMin-W3'.
    def _choose(run: str) -> str:
        has_hangul = any('\uAC00' <= ch <= '\uD7AF' for ch in run)
        has_kana = any('\u3040' <= ch <= '\u30FF' for ch in run)
        if has_hangul and 'NotoSansKR-Regular' in _FONT_REGISTRY:
            return 'NotoSansKR-Regular'  # real TTF
        if has_kana and 'NotoSansJP-Regular' in _FONT_REGISTRY:
            val = _FONT_REGISTRY['NotoSansJP-Regular']
            # CID aliases map to the CID font name (string not path)
            return val if isinstance(val, str) and not val.endswith('.ttf') else 'NotoSansJP-Regular'
        if 'NotoSansSC-Regular' in _FONT_REGISTRY:
            val = _FONT_REGISTRY['NotoSansSC-Regular']
            return val if isinstance(val, str) and not val.endswith('.ttf') else 'NotoSansSC-Regular'
        return None
    def _sub(m):
        run = m.group(1)
        font = _choose(run)
        return f'<font name="{font}">{run}</font>' if font else run
    return _CJK_RUN_RE.sub(_sub, text)


# ═══════════════════════════════════════════
# COLOR HELPERS
# ═══════════════════════════════════════════
def C(hex_key):
    """Get HexColor from COLORS dict, raw hex string, or pass through Color objects."""
    if not isinstance(hex_key, str):
        return hex_key  # Already a Color object
    if hex_key.startswith('#'):
        return HexColor(hex_key)
    return HexColor(COLORS.get(hex_key, '#1A1A1A'))


# ═══════════════════════════════════════════
# STYLES FACTORY
# ═══════════════════════════════════════════
def make_styles(lang: str = 'en'):
    """
    Build paragraph styles for PDF generation.
    Tiger Research-inspired: clean typography, proper font weights, professional spacing.
    """
    regular, bold, medium = get_fonts_for_lang(lang)

    # For titles, try Helvetica-Bold for ASCII-only content, fall back to NotoSansKR-Bold for CJK
    title_font = bold

    s = {}

    # Body text — 10.5pt, justified, line height 1.6x (17pt leading)
    s['body'] = ParagraphStyle(
        'body', fontName=regular, fontSize=10.5, leading=17,
        alignment=TA_JUSTIFY, spaceAfter=8, textColor=C('body_text'))

    s['body_small'] = ParagraphStyle(
        'body_small', parent=s['body'], fontSize=9, leading=14, spaceAfter=4)

    # Title — 22-26pt, Bold, black
    s['h1'] = ParagraphStyle(
        'h1', fontName=bold, fontSize=24, leading=32,
        textColor=C('primary_text'), spaceAfter=12, spaceBefore=20)

    # H2 sub-section — 14-16pt, Bold, dark gray
    s['h2'] = ParagraphStyle(
        'h2', fontName=bold, fontSize=15, leading=20,
        textColor=C('primary_text'), spaceAfter=10, spaceBefore=14)

    # H3 minor heading — 12pt, Bold, dark gray
    s['h3'] = ParagraphStyle(
        'h3', fontName=bold, fontSize=12, leading=16,
        textColor=C('primary_text'), spaceAfter=6, spaceBefore=10)

    # Caption/label — 9pt, coral accent
    s['caption'] = ParagraphStyle(
        'caption', fontName=regular, fontSize=9, leading=12,
        alignment=TA_LEFT, textColor=C('accent_coral'), spaceAfter=8, spaceBefore=2)

    # Bullet text — body style with indent
    s['bullet'] = ParagraphStyle(
        'bullet', parent=s['body'], leftIndent=18, bulletIndent=10,
        spaceAfter=6, fontSize=10.5, leading=17)

    # Table of contents
    s['toc'] = ParagraphStyle(
        'toc', fontName=regular, fontSize=10, leading=20, textColor=C('body_text'), leftIndent=16)

    s['toc_section'] = ParagraphStyle(
        'toc_section', fontName=bold, fontSize=10, leading=20, textColor=C('primary_text'), leftIndent=8)

    # Disclaimer — 7.5pt, justified, light gray
    s['disclaimer'] = ParagraphStyle(
        'disclaimer', fontName=regular, fontSize=7.5, leading=11,
        textColor=C('mid_gray'), alignment=TA_JUSTIFY, spaceAfter=4)

    # Table header — 9pt bold, white on dark
    s['th'] = ParagraphStyle(
        'th', fontName=bold, fontSize=9, leading=12,
        textColor=C('white'), alignment=TA_CENTER)

    # Table cell — center aligned
    s['tc'] = ParagraphStyle(
        'tc', fontName=regular, fontSize=9, leading=12,
        textColor=C('body_text'), alignment=TA_CENTER)

    # Table cell — left aligned
    s['tc_left'] = ParagraphStyle(
        'tc_left', fontName=regular, fontSize=9, leading=12,
        textColor=C('body_text'), alignment=TA_LEFT)

    # Table cell — bold, left aligned (first column)
    s['tc_bold'] = ParagraphStyle(
        'tc_bold', fontName=bold, fontSize=9, leading=12,
        textColor=C('primary_text'), alignment=TA_LEFT)

    # Forensic-specific: red accent for h1
    s['h1_forensic'] = ParagraphStyle(
        'h1_forensic', fontName=bold, fontSize=24, leading=32,
        textColor=C('forensic_red'), spaceAfter=12, spaceBefore=20)

    # Callout — normal weight, accent color
    s['callout'] = ParagraphStyle(
        'callout', fontName=medium, fontSize=11, leading=16,
        textColor=C('primary_text'), alignment=TA_LEFT, spaceAfter=8, leftIndent=0)

    # Callout forensic
    s['callout_forensic'] = ParagraphStyle(
        'callout_forensic', fontName=medium, fontSize=11, leading=16,
        textColor=C('forensic_red'), alignment=TA_LEFT, spaceAfter=8, leftIndent=0)

    # Key takeaway
    s['takeaway_title'] = ParagraphStyle(
        'takeaway_title', fontName=bold, fontSize=26, leading=34,
        textColor=C('primary_text'), spaceAfter=12, spaceBefore=8)

    s['takeaway_label'] = ParagraphStyle(
        'takeaway_label', fontName=bold, fontSize=12, leading=16,
        textColor=C('primary_text'), spaceAfter=8, spaceBefore=8)

    return s


# ═══════════════════════════════════════════
# FLOWABLE HELPERS
# ═══════════════════════════════════════════
def accent_line(color='section_divider_bg'):
    """Create an accent line (default: BCE Lab green)."""
    return HRFlowable(width="100%", thickness=2, color=C(color), spaceAfter=8, spaceBefore=2)


def thin_line():
    """Create a thin gray divider line."""
    return HRFlowable(width="100%", thickness=0.5, color=C('table_border'), spaceAfter=6, spaceBefore=6)


def section_header(text, styles, report_type='econ'):
    """Create a styled section header with accent line."""
    style_key = 'h1_forensic' if report_type == 'for' else 'h1'
    color = 'forensic_red' if report_type == 'for' else 'section_divider_bg'
    return [Spacer(1, 4), Paragraph(text, styles[style_key]), accent_line(color)]


import re as _re

def _clean_cell_md(text):
    """Convert markdown bold/italic in table cell text to ReportLab XML.
    Handles **bold**, \*\*bold\*\*, *italic*, and cleans backslash escapes.
    """
    text = str(text)
    # Escaped bold from Google Docs: \*\*text\*\* → **text**
    text = _re.sub(r'\\\*\\\*(.+?)\\\*\\\*', r'**\1**', text, flags=_re.DOTALL)
    # Escaped italic: \*text\* → *text*
    text = _re.sub(r'(?<!\\\*)\\\*([^*]+?)\\\*(?!\\\*)', r'*\1*', text)
    # Clean remaining backslash escapes
    text = _re.sub(r'\\(.)', r'\1', text)
    # Escape XML &
    text = text.replace('&', '&amp;')
    # Bold: **text** → <b>text</b>
    text = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=_re.DOTALL)
    # Italic: *text* → <i>text</i>
    text = _re.sub(r'(?<![<\w/])\*([^*\n]+?)\*(?![>\w])', r'<i>\1</i>', text)
    # Sanitize stray < >
    text = _re.sub(r'<(?!/?(?:b|i|font|sub|super|br)\b)', '&lt;', text)
    # Remove empty tags
    text = _re.sub(r'<[bi]>\s*</[bi]>', '', text)
    return text


# ═══════════════════════════════════════════
# TABLE BUILDER
# ═══════════════════════════════════════════
def build_table(headers, rows=None, col_widths=None, styles=None, first_col_bold=True, header_color='table_header_bg'):
    """
    Build a professional table with Tiger Research styling.

    Dark gray header, light alternating rows, subtle horizontal lines only.
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

    # Build table data — apply markdown→XML conversion to all cell text
    data = [[Paragraph(_clean_cell_md(h), s['th']) for h in headers]]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            cleaned = _clean_cell_md(cell)
            if i == 0 and first_col_bold:
                cells.append(Paragraph(cleaned, s['tc_bold']))
            else:
                cells.append(Paragraph(cleaned, s['tc'] if i > 0 else s['tc_left']))
        data.append(cells)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    hc = C(header_color)

    # Build style commands
    style_cmds = [
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), hc),
        ('TEXTCOLOR', (0, 0), (-1, 0), C('white')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Data row padding
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),

        # Subtle horizontal lines only (no grid)
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, hc),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, C('table_border')),
    ]

    # Alternating row colors: white and light gray
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), C('table_alt_row')))

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
    """
    Tiger Research-inspired cover page for ECON and MAT reports.
    White background, clean typography, green accents (BCE Lab branding).
    """
    c.saveState()
    rt = REPORT_TYPES[report_type]
    _regular, _bold, _medium = get_fonts_for_lang(lang)
    accent = C('section_divider_bg')  # BCE Lab green

    # ── White background (clean like Tiger Research) ──
    c.setFillColor(C('white'))
    c.rect(0, 0, W, H, fill=True, stroke=False)

    # ── Top decorative accent line ──
    c.setStrokeColor(accent)
    c.setLineWidth(2)
    c.line(0, H - 6*mm, W, H - 6*mm)

    # ── Top-left: BCE Lab branding ──
    c.setFillColor(accent)
    c.roundRect(25*mm, H - 35*mm, 10*mm, 10*mm, 2*mm, fill=True, stroke=False)
    c.setFillColor(C('white'))
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(30*mm, H - 32*mm, 'B')

    # ── Organization name ──
    c.setFillColor(C('primary_text'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(38*mm, H - 30*mm, ORG_NAME)
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 8)
    c.drawString(38*mm, H - 36*mm, ORG_FULL)

    # ── Report type label ──
    label_y = H * 0.60
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 10)
    report_label = 'CRYPTO ECONOMY REPORT:' if report_type == 'econ' else 'PROJECT MATURITY REPORT:'
    c.drawString(25*mm, label_y, report_label)

    # ── Project name (large, bold) ──
    is_ascii_name = all(ord(ch) < 128 for ch in project_name)
    name_font = 'Helvetica-Bold' if is_ascii_name else _bold
    c.setFillColor(C('primary_text'))
    name_size = 42
    if len(project_name) > 16:
        name_size = 34
    if len(project_name) > 24:
        name_size = 26
    c.setFont(name_font, name_size)
    c.drawString(25*mm, label_y - 22*mm, project_name)

    # ── Subtitle (report type title in local language) ──
    title_line2 = _get_report_title(rt, lang)
    c.setFillColor(C('body_text'))
    c.setFont(_medium, 13)
    c.drawString(25*mm, label_y - 42*mm, title_line2)

    # ── Green accent underline ──
    c.setStrokeColor(accent)
    c.setLineWidth(3)
    c.line(25*mm, label_y - 50*mm, 65*mm, label_y - 50*mm)

    # ── "By BCE Lab" — positioned above key metrics area ──
    metrics_area_top = H * 0.28
    c.setFillColor(C('primary_text'))
    c.setFont('Helvetica', 10)
    c.drawString(25*mm, metrics_area_top + 12*mm, 'By ')
    c.setFont('Helvetica-Bold', 10)
    c.drawString(33*mm, metrics_area_top + 12*mm, ORG_NAME)

    # ── Key metrics strip (if provided) ──
    if key_metrics and len(key_metrics) >= 2:
        n_items = min(len(key_metrics), 4)
        usable = W - 50*mm
        col_w = usable / n_items
        label_y_strip = metrics_area_top + 6*mm
        value_y_strip = metrics_area_top - 2*mm

        for i, (label, value) in enumerate(key_metrics[:4]):
            x = 25*mm + i * col_w
            # Label (gray, small)
            c.setFillColor(C('mid_gray'))
            c.setFont('Helvetica', 7.5)
            c.drawString(x, label_y_strip, label.upper())
            # Value (black, bold)
            c.setFillColor(C('primary_text'))
            c.setFont('Helvetica-Bold', 11)
            c.drawString(x, value_y_strip, str(value))

    # ── Footer info ──
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 8)
    today = datetime.now().strftime('%B %d, %Y')
    c.drawString(25*mm, 15*mm, f'Published: {today}  |  Version {version}')
    c.drawRightString(W - 25*mm, 15*mm, DOMAIN)

    # ── Copyright ──
    c.setFillColor(C('mid_gray'))
    c.setFont('Helvetica', 7)
    c.drawCentredString(W/2, 6*mm, f'© {COPYRIGHT_YEAR} {ORG_NAME}. All rights reserved.')

    c.restoreState()


def draw_cover_forensic(c, doc, project_name, token_symbol, risk_level, trigger_reason, version, lang):
    """Red-themed cover for Forensic reports."""
    c.saveState()
    _regular, _bold, _medium = get_fonts_for_lang(lang)

    # Dark background
    c.setFillColor(HexColor('#1A1A1A'))
    c.rect(0, 0, W, H, fill=True, stroke=False)

    # Top red confidential bar
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
    c.drawCentredString(W/2, 5*mm, f'© {COPYRIGHT_YEAR} {ORG_NAME}. CONFIDENTIAL — Authorized subscribers only.')

    c.restoreState()


# ═══════════════════════════════════════════
# HEADER / FOOTER TEMPLATES
# ═══════════════════════════════════════════
def make_header_footer(project_name, report_type):
    """
    Returns a function for later-page headers/footers.
    Tiger Research style: thin top line, clean footer with page number.
    """
    rt = REPORT_TYPES[report_type]
    is_forensic = (report_type == 'for')
    report_label = {
        'econ': 'Crypto Economy Report',
        'mat':  'Project Maturity Report',
        'for':  'Forensic Alert Report',
    }.get(report_type, rt['code'])

    def _header_footer(c, doc):
        c.saveState()

        if is_forensic:
            # Forensic: red confidential bar at top
            c.setFillColor(C('forensic_red'))
            c.rect(0, H - 8*mm, W, 8*mm, fill=True, stroke=False)
            c.setFillColor(C('white'))
            c.setFont('Helvetica-Bold', 7)
            c.drawCentredString(W/2, H - 6*mm, 'CONFIDENTIAL: MARKET RISK ALERT')
        else:
            # ECON/MAT: thin green accent line at top
            c.setStrokeColor(C('section_divider_bg'))
            c.setLineWidth(1)
            c.line(25*mm, H - 10*mm, W - 25*mm, H - 10*mm)

        # Header text (below top element)
        header_y = H - 16*mm if is_forensic else H - 17*mm
        c.setFillColor(C('body_text'))
        c.setFont('Helvetica', 8)
        c.drawString(25*mm, header_y, f'{report_label}: {project_name}')
        c.setFillColor(C('mid_gray'))
        c.setFont('Helvetica', 7.5)
        c.drawRightString(W - 25*mm, header_y, ORG_NAME)

        # Footer: thin line + copyright + page number
        c.setStrokeColor(C('table_border'))
        c.setLineWidth(0.5)
        c.line(25*mm, 15*mm, W - 25*mm, 15*mm)

        c.setFillColor(C('mid_gray'))
        c.setFont('Helvetica', 7)
        c.drawString(25*mm, 10*mm, f'© {COPYRIGHT_YEAR} {ORG_NAME}  |  {DOMAIN}')
        c.drawRightString(W - 25*mm, 10*mm, f'Page {doc.page}')

        c.restoreState()

    return _header_footer


# ═══════════════════════════════════════════
# DISCLAIMER SECTION
# ═══════════════════════════════════════════
def add_disclaimer(story, styles, report_type='econ'):
    """Add legal disclaimer section at end of report."""
    color = 'forensic_red' if report_type == 'for' else 'section_divider_bg'
    disc_h1 = ParagraphStyle(
        'disc_h1', fontName='Helvetica-Bold', fontSize=22, leading=28,
        textColor=C('primary_text') if report_type != 'for' else C('forensic_red'),
        spaceAfter=10, spaceBefore=20)

    story.extend([Spacer(1, 4), Paragraph('Disclaimer & Legal', disc_h1), accent_line(color)])

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
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 12))
    story.append(thin_line())
    story.append(Paragraph(
        f'© {COPYRIGHT_YEAR} {ORG_NAME} ({DOMAIN}). All rights reserved.',
        ParagraphStyle('final', fontName='Helvetica', fontSize=8,
                       textColor=C('mid_gray'), alignment=TA_CENTER)))


# ═══════════════════════════════════════════
# DOC BUILDER
# ═══════════════════════════════════════════
def create_doc(output_path):
    """Create a SimpleDocTemplate with standard margins (25mm left/right, 22mm top/bottom)."""
    return SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=25*mm, rightMargin=25*mm,
        topMargin=22*mm, bottomMargin=22*mm)

USABLE_W = W - 50*mm  # 25mm margins each side
