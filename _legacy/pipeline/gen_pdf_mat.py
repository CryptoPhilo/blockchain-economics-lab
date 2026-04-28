"""
BCE Lab Report Pipeline — Stage 2: MAT Markdown + Metadata → PDF
Converts Project Maturity Assessment markdown text and JSON metadata into a branded PDF.

Stage 2 receives output from Stage 1 (gen_text_mat.py):
  INPUT:
    - {slug}_mat_v{version}_assessment.md (markdown text analysis)
    - {slug}_mat_v{version}_meta.json (JSON with chart data & metadata)
  OUTPUT:
    - {slug}_mat_v{version}_{lang}.pdf (branded graphic PDF report)

Key features:
  - Parses markdown into sections with intelligent table/chart detection
  - Generates charts: goal achievement bar chart, on-chain/off-chain donut, maturity gauge
  - Uses BCE Lab brand styling (indigo theme)
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
from matplotlib.patches import Circle, Wedge, Rectangle
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
    wrap_cjk_runs
)
from config import report_filename, COLORS
from chart_engine import get_chart_engine, Palette


# ═══════════════════════════════════════════
# MARKDOWN PARSER
# ═══════════════════════════════════════════
def parse_markdown(md_text):
    """
    Parse markdown into sections.
    Returns list of tuples: (section_title, content_text)
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
        # Clean markdown formatting from title: **bold**, \escapes, brackets
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


def _md_to_rl(text, lang='en'):
    """Convert markdown inline formatting to ReportLab XML tags.
    Mirrors gen_pdf_econ._md_to_rl: handles Google-Docs escaped patterns,
    strips stray backslash escapes, drops triple-backtick code fences
    (keeping content as plain text), wraps CJK runs in font tags for
    universal glyph coverage.
    """
    # 0a. Extract $$...$$ and $...$ math blocks before backslash processing
    from gen_pdf_econ import _latex_to_text
    math_placeholders = {}
    def _replace_math(m):
        key = f'\x00MATH{len(math_placeholders)}\x00'
        math_placeholders[key] = f'<i>{_latex_to_text(m.group(0))}</i>'
        return key
    text = re.sub(r'\$\$[\s\S]*?\$\$', _replace_math, text)
    text = re.sub(r'\$[^\n$]+?\$', _replace_math, text)

    # 0b. Strip triple-backtick code fences (keep content)
    text = re.sub(r'```[a-zA-Z0-9_-]*\n?', '', text)
    # Also handle double-backtick spans: keep content without font swap
    text = re.sub(r'``\s*([\s\S]*?)\s*``', r'\1', text)

    # 1. Normalise within-paragraph line breaks
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)

    # 2. Escaped markdown → real markdown
    text = re.sub(r'\\\*\\\*(.+?)\\\*\\\*', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'(?<!\\\*)\\\*([^*]+?)\\\*(?!\\\*)', r'*\1*', text)

    # 3. Strip backslash escapes that don't need XML treatment
    text = text.replace('\\-', '-').replace('\\.', '.')
    text = text.replace('\\/', '/').replace('\\_', '_')
    text = text.replace('\\`', '`')
    text = text.replace('\\"', '"').replace("\\'", "'")

    # 4. XML escape & (must precede &lt;/&gt; conversion)
    text = text.replace('&', '&amp;')

    # 4b. Escaped angle brackets → XML entities (AFTER & escape)
    text = text.replace('\\<', '&lt;').replace('\\>', '&gt;')
    text = re.sub(r'\\(.)', r'\1', text)

    # 4c. Balance ** markers — strip the last unpaired one if odd count,
    # so non-greedy bold regex can't mispair across bullet items.
    parts = text.split('**')
    if len(parts) > 1 and (len(parts) - 1) % 2 == 1:
        parts[-2] = parts[-2] + parts[-1]
        parts.pop()
        text = '**'.join(parts)

    # 5. Markdown → RL XML
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    text = text.replace('**', '')
    text = re.sub(r'(?<![<\w/])\*([^*\n]+?)\*(?![>\w])', r'<i>\1</i>', text)
    # Inline single-backtick code → italic (no Courier, no CJK-breaking font swap)
    text = re.sub(r'`([^`]+?)`', r'<i>\1</i>', text)
    text = re.sub(r'\[([^\]]+?)\]\([^)]+?\)', r'\1', text)

    # 6. Sanitise stray < not part of allowed tags
    text = re.sub(r'<(?!/?(?:b|i|font|sub|super|br)\b)', '&lt;', text)

    # 6b. Wrap CJK / arrow / box-drawing runs in per-script font tags
    text = wrap_cjk_runs(text, lang=lang)

    # 7. Balance unpaired tags
    ob = len(re.findall(r'<b>', text)); cb = len(re.findall(r'</b>', text))
    if ob > cb:   text += '</b>' * (ob - cb)
    elif cb > ob: text = '<b>' * (cb - ob) + text
    oi = len(re.findall(r'<i>', text)); ci = len(re.findall(r'</i>', text))
    if oi > ci:   text += '</i>' * (oi - ci)
    elif ci > oi: text = '<i>' * (ci - oi) + text

    # 8. Remove empty tags
    text = re.sub(r'<i>\s*</i>', '', text)
    text = re.sub(r'<b>\s*</b>', '', text)

    # 9. Restore math placeholders
    for key, rendered in math_placeholders.items():
        text = text.replace(key, rendered)

    return text


def markdown_to_paragraphs(text, styles, max_width=None, lang='en'):
    """
    Convert markdown text to reportlab Paragraphs, respecting basic formatting.
    Handles: **bold**, *italic*, \\-escaped artefacts, ### sub-headers, bullets.
    """
    flowables = []
    text = clean_text_remove_tables(text)

    def _safe_para(t, style):
        try:
            return Paragraph(t, style)
        except Exception:
            return Paragraph(re.sub(r'<[^>]+>', '', t), style)

    # Force each bullet / numbered list item to its own paragraph so inline
    # bold/italic substitutions never cross item boundaries.
    text = re.sub(r'(?<!\n)\n(\s*(?:[*\-\u2022]|\d+[.)])\s+)', r'\n\n\1', text)

    for paragraph_text in text.split('\n\n'):
        p = paragraph_text.strip()
        if not p:
            continue

        # ### sub-headers
        if p.startswith('### '):
            sub_title = _md_to_rl(p[4:].strip(), lang=lang)
            flowables.append(Spacer(1, 10))
            flowables.append(_safe_para(f'<b>{sub_title}</b>', styles['h3']))
            flowables.append(Spacer(1, 4))
            continue

        p = _md_to_rl(p, lang=lang)

        if p.startswith('- ') or p.startswith('* '):
            flowables.append(_safe_para(f'\u2022 {p[2:]}', styles['bullet']))
        elif p.startswith('<b>') and ':' in p:
            flowables.append(_safe_para(p, styles['callout']))
        else:
            flowables.append(_safe_para(p, styles['body']))

        flowables.append(Spacer(1, 4))

    return flowables


# ═══════════════════════════════════════════
# CHART GENERATORS (matplotlib → reportlab Image)
# ═══════════════════════════════════════════
def generate_goal_achievement_chart(objectives):
    engine = get_chart_engine()
    labels = [o.get('name', f'Objective {i}') for i, o in enumerate(objectives)]
    scores = [o.get('weighted_score', 0) for o in objectives]
    colors = [Palette.score_color(s) for s in scores]
    return engine.render_bar_chart(
        labels=labels, values=scores,
        title='Strategic Goal Achievement',
        horizontal=True, color_map=colors,
        value_suffix='%', max_value=100,
        width=750, height=max(350, len(labels)*50+80),
    )


def generate_onchain_offchain_donut(onchain_pct, offchain_pct):
    engine = get_chart_engine()
    return engine.render_donut_chart(
        labels=['On-Chain', 'Off-Chain'],
        values=[onchain_pct, offchain_pct],
        title='On-Chain vs Off-Chain Architecture',
        center_text=f'{onchain_pct:.0f}%\nOn-Chain',
        colors=[Palette.INDIGO_600, Palette.INDIGO_300],
        width=550, height=450,
    )


def generate_maturity_gauge(score, label='Maturity Score'):
    engine = get_chart_engine()
    return engine.render_gauge_chart(
        value=score, max_value=100,
        title=label,
        suffix='%',
        thresholds={'danger': 30, 'warning': 60},
        width=500, height=350,
    )


# ═══════════════════════════════════════════
# PDF GENERATOR
# ═══════════════════════════════════════════
def generate_pdf_mat(md_path: str, metadata: dict, lang: str = 'en', output_path: str = None) -> str:
    """
    Generate branded MAT (Maturity Assessment) PDF from markdown analysis + JSON metadata.

    Args:
        md_path: Path to markdown assessment file
        metadata: Dict with project_name, version, maturity_score, charts_data, etc.
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
    project_name = metadata.get('project_name') or metadata.get('slug') or 'Project'
    if lang == 'en':
        project_name = metadata.get('name_en') or project_name
    slug = metadata.get('slug', 'project')
    version = metadata.get('version', 1)
    maturity_score = metadata.get('total_maturity_score', 0.0)
    maturity_stage = metadata.get('maturity_stage', 'growing')
    charts_data = metadata.get('charts_data', {})

    # Output path
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(md_path),
            report_filename(slug, 'mat', version, lang)
        )

    # Create document
    doc = create_doc(output_path)
    story = []
    styles = make_styles(lang=lang)

    # ═══════════════════════════════════════════
    # PAGE 1: COVER (using callback)
    # ═══════════════════════════════════════════
    # Build key metrics for cover
    key_metrics = [
        (f'{maturity_score:.1f}%', 'Maturity'),
        (maturity_stage.capitalize(), 'Stage'),
        (str(version), 'Version'),
        (lang.upper(), 'Lang'),
    ]

    def cover_callback(c, doc):
        draw_cover_econ_mat(
            c, doc,
            project_name=project_name,
            report_type='mat',
            version=version,
            lang=lang,
            subtitle='Project Maturity Assessment',
            key_metrics=key_metrics,
            rating=None
        )

    # ═══════════════════════════════════════════
    # PAGE 2+: CONTENT
    # ═══════════════════════════════════════════
    # Add first content page break
    story.append(PageBreak())

    # Process each section
    for idx, (section_title, section_content) in enumerate(sections):
        # PageBreak before each chapter (except the first, which follows cover break)
        if idx > 0:
            story.append(PageBreak())
        # Section header (returns list, must extend)
        story.extend(section_header(section_title, styles, report_type='mat'))

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
                is_goal = ('objective' in header_str or 'achievement' in header_str) and 'weighted' in header_str
                is_onchain = ('on-chain' in section_content.lower() or 'distribution' in header_str) and 'ratio' in section_content.lower()

                if is_goal and charts_data.get('goal_achievements'):
                    try:
                        chart_buf = generate_goal_achievement_chart(charts_data['goal_achievements'])
                        img = Image(chart_buf, width=115*mm, height=70*mm)
                        story.append(img)
                        story.append(Spacer(1, 8))
                    except Exception as e:
                        print(f"Warning: Could not generate goal achievement chart: {e}")

        else:
            # No tables - just prose
            story.extend(markdown_to_paragraphs(section_content, styles, lang=lang))

        # On-Chain/Off-Chain special handling: add donut chart
        if 'on-chain' in section_title.lower() and charts_data.get('onchain_offchain'):
            try:
                oc = charts_data['onchain_offchain']
                chart_buf = generate_onchain_offchain_donut(oc.get('onchain', 50), oc.get('offchain', 50))
                img = Image(chart_buf, width=90*mm, height=75*mm)
                story.append(Spacer(1, 6))
                story.append(img)
                story.append(Spacer(1, 8))
            except Exception as e:
                print(f"Warning: Could not generate on-chain/off-chain chart: {e}")

        # Final Assessment section: add maturity gauge
        if 'final assessment' in section_title.lower() or 'aggregate' in section_title.lower():
            try:
                gauge_buf = generate_maturity_gauge(maturity_score)
                img = Image(gauge_buf, width=85*mm, height=60*mm)
                story.append(Spacer(1, 6))
                story.append(img)
                story.append(Spacer(1, 8))
            except Exception as e:
                print(f"Warning: Could not generate maturity gauge: {e}")

    # Lifecycle timeline (if crypto_economy data available)
    if charts_data.get('lifecycle_stage'):
        try:
            engine = get_chart_engine()
            timeline_buf = engine.render_lifecycle_timeline(
                current_stage=charts_data['lifecycle_stage'],
                title='Protocol Lifecycle Position',
                width=750, height=200,
            )
            story.append(Image(timeline_buf, width=120*mm, height=35*mm))
            story.append(Spacer(1, 6*mm))
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # DISCLAIMER
    # ═══════════════════════════════════════════
    story.append(PageBreak())
    add_disclaimer(story, styles, report_type='mat')

    # ═══════════════════════════════════════════
    # BUILD PDF
    # ═══════════════════════════════════════════
    header_footer_func = make_header_footer(project_name, 'mat')
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

    md_path = os.path.join(output_dir, 'heyelsaai_mat_v1_assessment.md')
    meta_path = os.path.join(output_dir, 'heyelsaai_mat_v1_meta.json')

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
    pdf_path = generate_pdf_mat(md_path, metadata, lang='en')
    print(f"Success! Generated: {pdf_path}")
