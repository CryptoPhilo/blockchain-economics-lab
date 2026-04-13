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
    make_header_footer, add_disclaimer, create_doc, USABLE_W, C
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


def markdown_to_paragraphs(text, styles, max_width=None):
    """
    Convert markdown text to reportlab Paragraphs, respecting basic formatting.
    Handles: **bold**, *italic*, etc.
    """
    flowables = []
    text = clean_text_remove_tables(text)

    for paragraph_text in text.split('\n\n'):
        p = paragraph_text.strip()
        if not p:
            continue

        # Handle ### sub-headers
        if p.startswith('### '):
            sub_title = p[4:].strip()
            flowables.append(Spacer(1, 10))
            flowables.append(Paragraph(f'<b>{sub_title}</b>', styles['h3']))
            flowables.append(Spacer(1, 4))
            continue

        # Convert **bold** to <b>...</b>
        p = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', p)
        # Convert *italic* to <i>...</i>
        p = re.sub(r'\*(.*?)\*', r'<i>\1</i>', p)

        # Detect if it starts with - (bullet)
        if p.startswith('- '):
            flowables.append(Paragraph(p[2:], styles['bullet']))
        elif p.startswith('<b>') and ':' in p:
            # Bold key-value pair (e.g., "<b>Key</b>: value")
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
    # Build key metrics for cover
    key_metrics = [
        (str(version), 'Version'),
        (rating, 'Rating'),
        (lang.upper(), 'Lang'),
    ]

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

    # Process each section
    for section_title, section_content in sections:
        # Skip data sources section (goes at end)
        if section_title.lower() == 'data sources':
            continue

        # Section header (returns list, must extend)
        story.extend(section_header(section_title, styles, report_type='econ'))

        # Extract tables from this section
        tables_in_section = extract_tables_from_markdown(section_content)

        if tables_in_section:
            # Has tables - process with tables
            clean_prose = clean_text_remove_tables(section_content)

            # Add prose before first table
            if clean_prose:
                story.extend(markdown_to_paragraphs(clean_prose, styles))

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
            story.extend(markdown_to_paragraphs(section_content, styles))

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
    # NEW CHARTS: Radar chart and KPI card
    # ═══════════════════════════════════════════

    # Radar chart for multi-dimensional assessment
    if charts_data.get('tech_pillars') and len(charts_data['tech_pillars']) >= 3:
        try:
            engine = get_chart_engine()
            categories = [p['name'] for p in charts_data['tech_pillars'][:8]]
            values = [p['score'] for p in charts_data['tech_pillars'][:8]]
            radar_buf = engine.render_radar_chart(
                categories=categories, values=values,
                title='Multi-Dimensional Technical Assessment',
                width=600, height=480,
            )
            story.append(Image(radar_buf, width=100*mm, height=80*mm))
            story.append(Spacer(1, 6*mm))
        except Exception:
            pass

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
