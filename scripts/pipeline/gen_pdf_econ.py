"""
BCE Lab Report Pipeline — Stage 2: Markdown + Metadata → PDF
Converts analyzed markdown text and JSON metadata into a branded graphical PDF.

Stage 2 receives output from Stage 1 (gen_text_econ.py):
  INPUT:
    - {slug}_econ_v{version}_analysis.md (markdown text analysis)
    - {slug}_econ_v{version}_meta.json (JSON with chart data & metadata)
  OUTPUT:
    - {slug}_econ_v{version}_{lang}.pdf (branded graphic PDF report)

Key features:
  - Parses markdown into sections with intelligent table/chart detection
  - Generates charts: tech pillar bar chart, token distribution pie, risk matrix
  - Uses BCE Lab brand styling (dark indigo theme)
  - Cover page with key metrics, headers/footers on content pages
  - Professional tables from markdown source
  - Includes disclaimer section
"""
import json
import re
import os
from io import BytesIO
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)

from pdf_base import (
    make_styles, section_header, build_table, draw_cover_econ_mat,
    make_header_footer, add_disclaimer, create_doc, USABLE_W, C,
    wrap_cjk_runs,
)
from config import report_filename, COLORS
from chart_engine import get_chart_engine, Palette


# ═══════════════════════════════════════════
# MARKDOWN PARSER
# ═══════════════════════════════════════════
def parse_markdown(md_text):
    """
    Parse markdown into sections.
    Returns list of tuples: (section_title, content_text, tables_found)
    """
    sections = []
    # Split on ## headers
    parts = re.split(r'^## ', md_text, flags=re.MULTILINE)

    # First part (before any ##) is preamble
    preamble = parts[0].strip()

    # Process remaining sections
    for part in parts[1:]:
        lines = part.split('\n')
        title = lines[0].strip()
        # Clean markdown formatting from title: **bold**, \escapes
        title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)
        title = title.replace('\\', '')
        content = '\n'.join(lines[1:]).strip()
        sections.append((title, content))

    return preamble, sections


def extract_tables_from_markdown(text):
    """
    Extract markdown tables from text.
    Returns list of (table_data, remaining_text) where table_data is (headers, rows).
    """
    tables = []
    remaining = text

    # Match markdown tables: |...|...|...|
    table_pattern = r'\|[\s\S]*?\|[\s\S]*?\|[\s\S]*?\n(?:\|[-\s|:]+\|)\n(?:\|[\s\S]*?\|(?:\n|$))*'

    for match in re.finditer(table_pattern, text):
        table_text = match.group(0)
        lines = [l.strip() for l in table_text.split('\n') if l.strip()]

        if len(lines) >= 3:
            # First line: headers
            headers = [h.strip() for h in lines[0].split('|')[1:-1]]
            # Skip separator line (lines[1])
            # Remaining: rows
            rows = []
            for line in lines[2:]:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if cells:
                    rows.append(cells)

            if headers and rows:
                tables.append(((headers, rows), table_text))

    return tables


def clean_text_remove_tables(text):
    """Remove markdown tables from text, keeping only prose."""
    table_pattern = r'\|[\s\S]*?\|[\s\S]*?\|[\s\S]*?\n(?:\|[-\s|:]+\|)\n(?:\|[\s\S]*?\|(?:\n|$))*'
    return re.sub(table_pattern, '', text).strip()


# ── Semantic color keywords (multilingual) ──
# Green labels: scores, positive evaluations, strengths
_GREEN_LABEL_RE = re.compile(
    r'<b>(평가|점수|Score|Rating|장점|Strength|Advantage'
    r'|결론|Conclusion|結論|结论|Fazit|Conclusión'
    r'|종합\s*평가|Overall|총평'
    r'|강점|Merit|Stärke|Ventaja|Avantage'
    r')\s*([:\uff1a]?)\s*</b>',
    re.IGNORECASE
)

# Red labels: risks, weaknesses, warnings, limitations
_RED_LABEL_RE = re.compile(
    r'<b>(한계|리스크|위험|Risk|Warning|Limitation|Weakness'
    r'|잠재적\s*리스크|Potential\s*Risk'
    r'|약점|취약|Vulnerability|Risiko|Riesgo|Risque'
    r'|주의|Caution|注意|注意事项'
    r')\s*([:\uff1a]?)\s*</b>',
    re.IGNORECASE
)


def _apply_semantic_colors(text):
    """Apply green/red colors to specific bold labels for visual hierarchy.
    - Green (#2D8F5E): 평가, 장점, 결론, Score, Rating, etc.
    - Red (#C0392B): 한계, 리스크, Risk, Warning, etc.
    """
    green = COLORS['score_green']
    red = COLORS['risk_red']

    # Green labels
    text = _GREEN_LABEL_RE.sub(
        rf'<b><font color="{green}">\1\2</font></b>', text
    )
    # Red labels
    text = _RED_LABEL_RE.sub(
        rf'<b><font color="{red}">\1\2</font></b>', text
    )
    return text


def _latex_to_text(latex: str) -> str:
    """Convert LaTeX math expression to readable plain text for PDF."""
    s = latex.strip().strip('$').strip()
    replacements = [
        ('\\Delta', '\u0394'), ('\\Sigma', '\u03A3'), ('\\Pi', '\u03A0'),
        ('\\alpha', '\u03B1'), ('\\beta', '\u03B2'), ('\\gamma', '\u03B3'),
        ('\\delta', '\u03B4'), ('\\epsilon', '\u03B5'), ('\\lambda', '\u03BB'),
        ('\\mu', '\u03BC'), ('\\sigma', '\u03C3'), ('\\pi', '\u03C0'),
        ('\\theta', '\u03B8'), ('\\omega', '\u03C9'), ('\\phi', '\u03C6'),
        ('\\times', '\u00D7'), ('\\cdot', '\u00B7'), ('\\pm', '\u00B1'),
        ('\\leq', '\u2264'), ('\\geq', '\u2265'), ('\\neq', '\u2260'),
        ('\\approx', '\u2248'), ('\\infty', '\u221E'),
        ('\\sum', '\u03A3'), ('\\prod', '\u03A0'),
        ('\\rightarrow', '\u2192'), ('\\leftarrow', '\u2190'),
        ('\\sqrt', '\u221A'),
    ]
    for pat, repl in replacements:
        s = s.replace(pat, repl)
    s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\(?:mathrm|mathit|mathbf)\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1 / \2)', s)
    s = re.sub(r'\\(?:left|right|Big|big)[{}()|]?', '', s)
    s = re.sub(r'\\sqrt\{([^}]*)\}', '\u221A(\\1)', s)
    s = re.sub(r'\\[a-zA-Z]+', '', s)
    s = re.sub(r'[{}]', '', s)
    s = re.sub(r'\\', '', s)
    return s.strip()


def _md_to_rl(text, lang='en'):
    """Convert markdown inline formatting to ReportLab XML tags.
    Handles Google Docs export patterns like \\*\\*bold\\*\\* and regular **bold**.
    """
    # Step 0a: Extract $$...$$ math blocks before any backslash processing
    math_placeholders = {}
    def _replace_math(m):
        key = f'\x00MATH{len(math_placeholders)}\x00'
        math_placeholders[key] = f'<i>{_latex_to_text(m.group(0))}</i>'
        return key
    text = re.sub(r'\$\$[\s\S]*?\$\$', _replace_math, text)
    text = re.sub(r'\$[^\n$]+?\$', _replace_math, text)

    # Step 0b: Strip triple-backtick code fences (keep content as plain text)
    text = re.sub(r'```[a-zA-Z0-9_-]*\n?', '', text)
    text = re.sub(r'``\s*([\s\S]*?)\s*``', r'\1', text)

    # Step 1: Normalize single newlines to spaces (within-paragraph line breaks)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)

    # Step 2: Convert escaped markdown from Google Docs export
    # \*\*text\*\* → **text** (escaped bold)
    text = re.sub(r'\\\*\\\*(.+?)\\\*\\\*', r'**\1**', text, flags=re.DOTALL)
    # \*text\* → *text* (escaped italic)
    text = re.sub(r'(?<!\\\*)\\\*([^*]+?)\\\*(?!\\\*)', r'*\1*', text)

    # Step 3a: Clean backslash escapes that don't need XML treatment
    text = text.replace('\\-', '-').replace('\\.', '.')
    text = text.replace('\\_', '_').replace('\\`', '`')
    text = text.replace('\\"', '"').replace("\\'", "'")

    # Step 4: Escape XML special chars (& first, then < > as literals)
    text = text.replace('&', '&amp;')

    # Step 4b: Now safely convert escaped angle brackets to XML entities
    # (must come AFTER & escaping to avoid &gt; becoming &amp;gt;)
    text = text.replace('\\<', '&lt;').replace('\\>', '&gt;')

    # Step 4c: Remove any remaining single-backslash escapes
    text = re.sub(r'\\(.)', r'\1', text)

    # Step 4d: Balance ** markers — if odd count, strip the last unpaired one
    # (prevents mispairing across bullet items when stray \*\* leaks through)
    parts = text.split('**')
    if len(parts) > 1 and (len(parts) - 1) % 2 == 1:
        # Odd marker count → drop the last `**` by merging last two segments
        parts[-2] = parts[-2] + parts[-1]
        parts.pop()
        text = '**'.join(parts)

    # Step 5: Markdown → ReportLab XML
    # Bold: **text** → <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    # Italic: *text* → <i>text</i> (only standalone *, avoid matching inside tags)
    text = re.sub(r'(?<![<\w/])\*([^*\n]+?)\*(?![>\w])', r'<i>\1</i>', text)
    # Inline code: `text` → <i>text</i> (avoid Courier which lacks CJK)
    text = re.sub(r'`([^`]+?)`', r'<i>\1</i>', text)
    # Strip any stray leftover backticks (e.g. unmatched `` from split paragraphs)
    text = text.replace('``', '').replace('`', '')
    # Links: [text](url) → text
    text = re.sub(r'\[([^\]]+?)\]\([^)]+?\)', r'\1', text)

    # Step 6: Sanitize stray < > that aren't valid XML tags
    text = re.sub(r'<(?!/?(?:b|i|font|sub|super|br)\b)', '&lt;', text)

    # Step 6.5: Wrap CJK/symbol runs in proper script-specific font to avoid ■
    text = wrap_cjk_runs(text, lang=lang)

    # Step 7: Remove empty tags only
    text = re.sub(r'<i>\s*</i>', '', text)
    text = re.sub(r'<b>\s*</b>', '', text)

    # Step 8: Apply semantic colors to specific bold labels
    text = _apply_semantic_colors(text)

    # Step 9: Restore math placeholders
    for key, rendered in math_placeholders.items():
        text = text.replace(key, rendered)

    return text


_CONCLUSION_RE = re.compile(
    r'^<b>(결론|Conclusion|結論|结论|Fazit|Conclusión)\s*[:\uff1a]?\s*</b>',
    re.IGNORECASE
)


def _is_conclusion_paragraph(text):
    """Detect if a paragraph starts with a conclusion label like '<b>결론:</b>'."""
    return bool(_CONCLUSION_RE.match(text))


def _build_conclusion_box(text, styles):
    """
    Render a conclusion paragraph as a bordered highlight box.
    Uses a 1-cell Table with left accent border and light background.
    The '결론:' label is colored green for visual emphasis.
    """
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Table, TableStyle

    conclusion_style = ParagraphStyle(
        'conclusion_box', parent=styles['body'],
        fontSize=10.5, leading=17,
        textColor=HexColor(COLORS['primary_text']),
    )
    para = Paragraph(text, conclusion_style)

    # Single-cell table to create the box effect
    t = Table([[para]], colWidths=[USABLE_W - 16])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#F5F7F5')),  # light green-gray bg
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        # Left accent border (BCE Lab green)
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, HexColor(COLORS['table_border'])),
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, HexColor(COLORS['table_border'])),
        ('LINEBEFORE', (0, 0), (0, -1), 3, HexColor(COLORS['accent'])),
        ('LINEAFTER', (-1, 0), (-1, -1), 0.5, HexColor(COLORS['table_border'])),
    ]))
    return t


def _auto_bold_label(text):
    """Auto-bold leading label patterns like '항목명:' or '항목명 (English):' in bullet text.
    Skips if already wrapped in <b> tags.
    Handles patterns:
      - "한글라벨:" → "<b>한글라벨:</b>"
      - "한글라벨 (English):" → "<b>한글라벨 (English):</b>"
      - "<b>라벨:</b> 설명" → unchanged (already bold)
    """
    # Skip if already starts with a bold tag
    if text.startswith('<b>'):
        return text
    # Match: leading label text followed by colon, optionally with parenthetical
    # e.g. "자원희소성:", "초기 공급량:", "보상 수단:", "온체인 State 매핑:"
    m = re.match(
        r'^([^\s<][^<:]{0,40}(?:\([^)]*\))?)\s*:\s*',
        text
    )
    if m:
        label = m.group(0).rstrip()  # "라벨:"
        rest = text[m.end():]
        return f'<b>{label}</b> {rest}'
    return text


def markdown_to_paragraphs(text, styles, max_width=None, lang='en'):
    """
    Convert markdown text to reportlab Paragraphs.
    Handles: **bold**, *italic*, `code`, [links](url), bullets, headers.
    """
    flowables = []
    text = clean_text_remove_tables(text)
    # Pre-strip triple/double-backtick fences at whole-text level so they don't
    # survive the paragraph split (markdown_to_paragraphs splits on \n\n).
    text = re.sub(r'```[a-zA-Z0-9_-]*\n?', '', text)
    text = re.sub(r'``([\s\S]*?)``', r'\1', text)

    # Force each bullet / numbered list item onto its own paragraph so
    # inline-markdown (bold/italic) substitutions never cross item boundaries.
    text = re.sub(r'(?<!\n)\n(\s*(?:[*\-\u2022]|\d+[.)])\s+)', r'\n\n\1', text)

    for paragraph_text in text.split('\n\n'):
        # Detect indentation level BEFORE stripping (for hierarchy)
        raw = paragraph_text.rstrip()
        indent_level = 0
        if raw and raw[0] == ' ':
            leading_spaces = len(raw) - len(raw.lstrip(' '))
            indent_level = leading_spaces // 2  # 2 spaces = 1 indent level

        p = raw.strip()
        if not p:
            continue

        # Handle ### sub-headers (skip if empty or just "###")
        if p.startswith('###'):
            sub_title = _md_to_rl(p.lstrip('#').strip(), lang=lang)
            if not sub_title:
                continue
            flowables.append(Spacer(1, 10))
            flowables.append(Paragraph(sub_title, styles['h3']))
            flowables.append(Spacer(1, 4))
            continue

        # Handle ## section headers (in case not caught by parser)
        if p.startswith('## '):
            sub_title = _md_to_rl(p[3:].strip(), lang=lang)
            flowables.append(Spacer(1, 12))
            flowables.append(Paragraph(sub_title, styles['h2']))
            flowables.append(Spacer(1, 4))
            continue

        # Convert markdown to RL tags
        p = _md_to_rl(p, lang=lang)

        # ── Hierarchy-aware bullet rendering ──
        # Different bullet glyphs per indent level for visual distinction:
        #   Level 0 (top):   • (BULLET U+2022)
        #   Level 1:         – (EN DASH U+2013)
        #   Level 2+:        · (MIDDLE DOT U+00B7)
        BULLET_GLYPHS = ['\u2022', '\u2013', '\u00B7', '\u00B7']

        # Choose style based on indentation: sub-items get extra leftIndent
        if indent_level >= 1:
            glyph = BULLET_GLYPHS[min(indent_level, len(BULLET_GLYPHS) - 1)]
            sub_indent = 18 + indent_level * 14  # increasing indent per level
            is_bullet = p.startswith('* ') or p.startswith('- ') or p.startswith('\u2022 ')
            if is_bullet:
                bullet_text = re.sub(r'^[*\-\u2022]\s+', '', p)
                # Auto-bold label patterns like "항목명:" at start of bullet
                bullet_text = _auto_bold_label(bullet_text)
                sub_style = ParagraphStyle(
                    f'sub_bullet_{indent_level}', parent=styles['bullet'],
                    leftIndent=sub_indent, bulletIndent=sub_indent - 12,
                    fontSize=10, leading=16)
                flowables.append(Paragraph(f'{glyph} {bullet_text}', sub_style))
            else:
                p = _auto_bold_label(p)
                sub_style = ParagraphStyle(
                    f'sub_body_{indent_level}', parent=styles['body'],
                    leftIndent=sub_indent, fontSize=10, leading=16)
                flowables.append(Paragraph(p, sub_style))
            flowables.append(Spacer(1, 2))
            continue

        # Handle numbered list items: "1. text" or "1) text"
        numbered_match = re.match(r'^(\d+)[.)]\s+(.+)', p)

        # Detect bullet points (top-level): use • (BULLET)
        if p.startswith('* ') or p.startswith('- ') or p.startswith('\u2022 '):
            bullet_text = re.sub(r'^[*\-\u2022]\s+', '', p)
            bullet_text = _auto_bold_label(bullet_text)
            flowables.append(Paragraph(f'\u2022 {bullet_text}', styles['bullet']))
        elif numbered_match:
            num, content = numbered_match.groups()
            flowables.append(Paragraph(f'{num}. {content}', styles['bullet']))
        elif _is_conclusion_paragraph(p):
            # Render conclusion as a bordered highlight box
            flowables.append(Spacer(1, 6))
            flowables.append(_build_conclusion_box(p, styles))
            flowables.append(Spacer(1, 6))
            continue  # skip default spacer
        elif p.startswith('<b>') and ':' in p[:60]:
            flowables.append(Paragraph(p, styles['callout']))
        else:
            flowables.append(Paragraph(p, styles['body']))

        flowables.append(Spacer(1, 4))

    return flowables


# ═══════════════════════════════════════════
# CHART GENERATORS (matplotlib → reportlab Image)
# ═══════════════════════════════════════════
def generate_tech_pillar_chart(pillars):
    engine = get_chart_engine()
    labels = [p.get('name', f'Pillar {i}') for i, p in enumerate(pillars)]
    scores = [p.get('score', 0) for p in pillars]
    colors = [Palette.score_color(s) for s in scores]
    return engine.render_bar_chart(
        labels=labels, values=scores,
        title='Technical Pillar Assessment',
        horizontal=True, color_map=colors,
        value_suffix='/100', max_value=100,
        width=750, height=max(350, len(labels)*50+80),
    )


def generate_token_distribution_pie(distribution):
    engine = get_chart_engine()
    labels = [d.get('category', '?') for d in distribution]
    values = [d.get('percentage', 0) for d in distribution]
    return engine.render_pie_chart(
        labels=labels, values=values,
        title='Token Distribution',
        width=600, height=480,
    )


def generate_risk_matrix(risks):
    engine = get_chart_engine()
    return engine.render_risk_matrix(
        risks=risks,
        title='Risk Assessment Matrix',
        width=700, height=520,
    )


# ═══════════════════════════════════════════
# SCORING SECTION DETECTION
# ═══════════════════════════════════════════

# Multilingual keywords for "comprehensive analysis / evaluation" section titles.
# These are the sections where the radar chart should be placed.
_SCORING_TITLE_KEYWORDS = {
    # Korean
    '종합', '점검', '평가', '점수',
    # English
    'comprehensive', 'inspection', 'checkpoint', 'evaluation',
    'scorecard', 'assessment', 'overall',
    # Japanese
    '総合', 'チェックポイント', '評価',
    # Chinese
    '综合', '检查', '评级', '检查点',
    # German
    'umfassende', 'inspektion', 'bewertung',
    # French
    'complète', 'complets', 'contrôle', 'inspection',
    # Spanish
    'integral', 'inspección', 'completos',
}

# Content patterns that indicate scoring (X/10, X / 10, etc.)
_SCORING_CONTENT_RE = re.compile(
    r'(\d+\s*/\s*10'           # "9 / 10" or "9/10"
    r'|\d+\s*/\s*100'          # "85 / 100"
    r'|점검\s*포인트'            # 점검 포인트
    r'|Check\s*[Pp]oint'       # Checkpoint
    r'|チェックポイント'          # Japanese checkpoint
    r'|检查点|检查要点'           # Chinese checkpoint
    r'|Inspektionspunkt'       # German
    r'|punto.*control'         # Spanish
    r')',
    re.IGNORECASE
)


def _is_scoring_section(title: str, content: str) -> bool:
    """
    Detect whether a section is the scoring/evaluation section
    where the radar chart should be placed.

    Strategy (both must match):
      1. Title contains at least one multilingual scoring keyword
      2. Content contains scoring patterns (X/10, 점검 포인트, etc.)

    This ensures the chart isn't placed in unrelated sections that
    happen to share a keyword (e.g. '분석' appears in many titles).
    """
    # Normalize title: strip markdown, numbers, punctuation
    t = re.sub(r'\*\*|\\|\d+[.。)]', '', title).strip().lower()

    # Check title keywords
    title_match = any(kw in t for kw in _SCORING_TITLE_KEYWORDS)
    if not title_match:
        return False

    # Check content for scoring patterns
    content_match = bool(_SCORING_CONTENT_RE.search(content))
    return content_match


# ═══════════════════════════════════════════
# PDF GENERATOR
# ═══════════════════════════════════════════
def generate_pdf_econ(md_path: str, metadata: dict, lang: str = 'en', output_path: str = None) -> str:
    """
    Generate branded ECON PDF from markdown analysis + JSON metadata.

    Args:
        md_path: Path to markdown analysis file
        metadata: Dict with project_name, version, overall_rating, charts_data, etc.
        lang: Language code (default: 'en')
        output_path: Path for output PDF (default: auto-generated from config)

    Returns:
        Path to generated PDF
    """
    # Read markdown
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Parse markdown
    preamble, sections = parse_markdown(md_text)

    # Setup
    project_name = metadata.get('project_name', 'Project')
    slug = metadata.get('slug', 'project')
    version = metadata.get('version', 1)
    rating = metadata.get('overall_rating', 'B')
    charts_data = metadata.get('charts_data', {})

    # Output path
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(md_path),
            report_filename(slug, 'econ', version, lang)
        )

    # Create document
    doc = create_doc(output_path)
    story = []
    styles = make_styles(lang=lang)

    # ═══════════════════════════════════════════
    # PAGE 1: COVER (using callback)
    # ═══════════════════════════════════════════
    # Build key metrics for cover (FDA-style: label, value pairs)
    asset_type = metadata.get('asset_type', 'Digital Asset')
    consensus = metadata.get('consensus', 'N/A')
    key_metrics = [
        ('Asset Type', asset_type),
        ('Rating', rating),
        ('Version', str(version)),
        ('Language', lang.upper()),
    ]
    if consensus and consensus != 'N/A':
        key_metrics[1:1] = [('Consensus', consensus)]
        key_metrics = key_metrics[:4]  # max 4 items

    def cover_callback(c, doc):
        draw_cover_econ_mat(
            c, doc,
            project_name=project_name,
            report_type='econ',
            version=version,
            lang=lang,
            subtitle=f'AI Agent Economy Design Analysis',
            key_metrics=key_metrics,
            rating=rating
        )

    # ═══════════════════════════════════════════
    # PAGE 2+: CONTENT
    # ═══════════════════════════════════════════
    # Add first content page break
    story.append(PageBreak())

    # Process each section — each chapter starts on a new page
    is_first_section = True
    for section_title, section_content in sections:
        # Skip data sources section (goes at end)
        if section_title.lower() == 'data sources':
            continue

        # Skip empty sections (e.g. stray "## " with no title/content)
        if not section_title.strip() and not section_content.strip():
            continue

        # PageBreak before each chapter (except the first, which follows cover break)
        if not is_first_section:
            story.append(PageBreak())
        is_first_section = False

        # Section header (returns list, must extend)
        story.extend(section_header(section_title, styles, report_type='econ'))

        # Insert radar chart at the top of the scoring/evaluation section.
        # Detection uses both title keywords (multilingual) and content scoring patterns.
        if _is_scoring_section(section_title, section_content) \
                and charts_data.get('tech_pillars') and len(charts_data['tech_pillars']) >= 3:
            try:
                engine = get_chart_engine()
                categories = [p['name'] for p in charts_data['tech_pillars'][:8]]
                values = [p['score'] for p in charts_data['tech_pillars'][:8]]
                radar_buf = engine.render_radar_chart(
                    categories=categories, values=values,
                    title='Multi-Dimensional Technical Assessment',
                    width=600, height=480,
                )
                story.append(Spacer(1, 4))
                story.append(Image(radar_buf, width=105*mm, height=84*mm))
                story.append(Spacer(1, 8))
            except Exception:
                pass

        # Extract tables from this section
        tables_in_section = extract_tables_from_markdown(section_content)

        if tables_in_section:
            # Has tables - process with tables
            clean_prose = clean_text_remove_tables(section_content)

            # Add prose before first table
            if clean_prose:
                story.extend(markdown_to_paragraphs(clean_prose, styles, lang=lang))

            # Add tables and associated charts
            for (headers, rows), _ in tables_in_section:
                # Build and add table
                col_widths = [USABLE_W / len(headers)] * len(headers)
                table = build_table(headers, rows, col_widths=col_widths, styles=styles)
                story.append(table)
                story.append(Spacer(1, 8))

                # Add chart if this is a known chart section
                title_lower = section_title.lower()
                header_str = ' '.join(headers).lower()
                is_tech = ('technical' in title_lower or 'pillar' in header_str or 'score' in header_str) and 'score' in header_str
                is_token = ('token' in title_lower or 'distribution' in header_str) and ('percentage' in header_str or 'amount' in header_str)

                if is_tech and charts_data.get('tech_pillars'):
                    try:
                        chart_buf = generate_tech_pillar_chart(charts_data['tech_pillars'])
                        img = Image(chart_buf, width=115*mm, height=70*mm)
                        story.append(img)
                        story.append(Spacer(1, 8))
                    except Exception as e:
                        print(f"Warning: Could not generate tech pillar chart: {e}")

                elif is_token and charts_data.get('token_distribution'):
                    try:
                        chart_buf = generate_token_distribution_pie(charts_data['token_distribution'])
                        img = Image(chart_buf, width=100*mm, height=80*mm)
                        story.append(img)
                        story.append(Spacer(1, 8))
                    except Exception as e:
                        print(f"Warning: Could not generate token distribution chart: {e}")

        else:
            # No tables - just prose
            story.extend(markdown_to_paragraphs(section_content, styles, lang=lang))

        # Risk Assessment special handling: add scatter plot
        if section_title.lower() == 'risk assessment' and charts_data.get('risks'):
            try:
                risk_buf = generate_risk_matrix(charts_data['risks'])
                img = Image(risk_buf, width=110*mm, height=85*mm)
                story.append(Spacer(1, 6))
                story.append(img)
                story.append(Spacer(1, 8))
            except Exception as e:
                print(f"Warning: Could not generate risk matrix: {e}")

    # ═══════════════════════════════════════════
    # KPI CARD (appended after all sections)
    # ═══════════════════════════════════════════

    # KPI card for key financial metrics
    if charts_data.get('market_snapshot'):
        try:
            engine = get_chart_engine()
            ms = charts_data['market_snapshot']
            kpi_metrics = []
            if ms.get('price'):
                kpi_metrics.append({'label': 'Price', 'value': ms['price'], 'delta': ms.get('change_24h', ''), 'color': Palette.INDIGO_600})
            if ms.get('market_cap'):
                kpi_metrics.append({'label': 'Market Cap', 'value': ms['market_cap'], 'color': Palette.INDIGO_600})
            if ms.get('volume'):
                kpi_metrics.append({'label': '24h Volume', 'value': ms['volume'], 'color': Palette.INFO})
            if kpi_metrics:
                kpi_buf = engine.render_kpi_card(metrics=kpi_metrics, width=750, height=180)
                story.append(Image(kpi_buf, width=120*mm, height=35*mm))
                story.append(Spacer(1, 6*mm))
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # DISCLAIMER
    # ═══════════════════════════════════════════
    story.append(PageBreak())
    add_disclaimer(story, styles, report_type='econ')

    # ═══════════════════════════════════════════
    # BUILD PDF
    # ═══════════════════════════════════════════
    header_footer_func = make_header_footer(project_name, 'econ')
    doc.build(story, onFirstPage=cover_callback, onLaterPages=header_footer_func)

    print(f"✓ PDF generated: {output_path}")
    return output_path


# ═══════════════════════════════════════════
# MAIN / TEST
# ═══════════════════════════════════════════
if __name__ == '__main__':
    import sys

    pipeline_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(pipeline_dir, 'output')

    md_path = os.path.join(output_dir, 'heyelsaai_econ_v1_analysis.md')
    meta_path = os.path.join(output_dir, 'heyelsaai_econ_v1_meta.json')

    # Verify input files exist
    if not os.path.exists(md_path):
        print(f"Error: Markdown file not found: {md_path}")
        sys.exit(1)

    if not os.path.exists(meta_path):
        print(f"Error: Metadata file not found: {meta_path}")
        sys.exit(1)

    # Load metadata
    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Generate PDF
    pdf_path = generate_pdf_econ(md_path, metadata, lang='en')
    print(f"Success! Generated: {pdf_path}")
