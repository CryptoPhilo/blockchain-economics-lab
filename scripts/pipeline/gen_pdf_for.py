"""
BCE Lab Report Pipeline — Stage 2: FOR Markdown + Metadata → PDF
Converts Forensic Analysis markdown text and JSON metadata into a red-themed alert PDF.

Stage 2 receives output from Stage 1 (gen_text_for.py):
  INPUT:
    - {slug}_for_v{version}_analysis.md (markdown forensic analysis)
    - {slug}_for_v{version}_meta.json (JSON with risk metrics and trigger info)
  OUTPUT:
    - {slug}_for_v{version}_{lang}.pdf (branded forensic alert PDF)

Key features:
  - Parses markdown into sections with intelligent table/chart detection
  - Generates charts: risk indicator bar chart, manipulation detection chart
  - Uses BCE Lab forensic red theme
  - Cover page with risk level and trigger reason, headers/footers on content pages
  - Professional tables from markdown source
  - Includes confidentiality disclaimer section
"""
import json
import re
import os
from io import BytesIO
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
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
    make_styles, section_header, build_table, draw_cover_forensic,
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


def markdown_to_paragraphs(text, styles, max_width=None, lang='en'):
    """
    Convert markdown text to reportlab Paragraphs, respecting basic formatting.
    Handles: **bold**, *italic*, ### sub-headers, bullet points

    Uses ECON pipeline's improved _md_to_rl() for robust XML conversion
    (OPS-005: ** balancing + bullet paragraph splitting).
    """
    # Import improved converter from gen_pdf_econ
    from gen_pdf_econ import _md_to_rl as _md_to_rl_econ
    from gen_pdf_econ import markdown_to_paragraphs as _econ_md_to_para

    # Delegate to ECON's improved implementation
    try:
        return _econ_md_to_para(text, styles, lang=lang)
    except Exception:
        # Fallback to simple implementation
        flowables = []
        text = clean_text_remove_tables(text)

        # OPS-005: Force each bullet onto its own paragraph
        text = re.sub(r'(?<!\n)\n(\s*(?:[*\-\u2022]|\d+[.)])\s+)', r'\n\n\1', text)

        for paragraph_text in text.split('\n\n'):
            p = paragraph_text.strip()
            if not p:
                continue

            if p.startswith('### '):
                sub_title = p[4:].strip()
                flowables.append(Spacer(1, 10))
                flowables.append(Paragraph(f'<b>{sub_title}</b>', styles['h3']))
                flowables.append(Spacer(1, 4))
                continue

            # OPS-005: Balance ** markers
            parts = p.split('**')
            if len(parts) > 1 and (len(parts) - 1) % 2 == 1:
                parts[-2] = parts[-2] + parts[-1]
                parts.pop()
                p = '**'.join(parts)

            p = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', p)
            p = re.sub(r'\*(.*?)\*', r'<i>\1</i>', p)

            if p.startswith('- ') or p.startswith('• '):
                bullet_text = p[2:] if p[0] in '-•' else p
                flowables.append(Paragraph(f'\u2022 {bullet_text}', styles['bullet']))
            elif p.startswith('<b>') and ':' in p[:60]:
                style_name = 'callout_forensic' if 'callout_forensic' in styles else 'callout'
                flowables.append(Paragraph(p, styles[style_name]))
            else:
                flowables.append(Paragraph(p, styles['body']))

            flowables.append(Spacer(1, 4))

        return flowables


# ═══════════════════════════════════════════
# CHART GENERATORS (matplotlib → reportlab Image)
# ═══════════════════════════════════════════
def generate_risk_indicator_chart(indicators):
    engine = get_chart_engine()
    labels = [ind.get('name', f'Indicator {i}') for i, ind in enumerate(indicators)]
    scores = [ind.get('score', 0) for ind in indicators]
    severity_colors = []
    for ind in indicators:
        sev = ind.get('severity', 'medium').lower()
        severity_colors.append(Palette.RISK_SEVERITY.get(sev, Palette.WARNING))
    return engine.render_bar_chart(
        labels=labels, values=scores,
        title='Risk Indicator Assessment',
        horizontal=True, color_map=severity_colors,
        value_suffix='', max_value=100,
        width=750, height=max(350, len(labels)*50+80),
    )


def generate_manipulation_detection_chart(manipulations):
    engine = get_chart_engine()
    labels = [m.get('type', f'Type {i}') for i, m in enumerate(manipulations)]
    scores = [m.get('score', 0) for m in manipulations]
    return engine.render_bar_chart(
        labels=labels, values=scores,
        title='Manipulation Detection Scores',
        horizontal=False, color=Palette.DANGER,
        value_suffix='', max_value=100,
        width=700, height=420,
    )


# ═══════════════════════════════════════════
# PDF GENERATOR
# ═══════════════════════════════════════════
def generate_pdf_for(md_path: str, metadata: dict, lang: str = 'en', output_path: str = None) -> str:
    """
    Generate branded FOR (Forensic Report) PDF from markdown analysis + JSON metadata.

    Args:
        md_path: Path to markdown forensic analysis file
        metadata: Dict with project_name, token_symbol, risk_level, version, charts_data, etc.
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
    token_symbol = metadata.get('token_symbol', 'TOKEN')
    slug = metadata.get('slug', 'project')
    version = metadata.get('version', 1)
    risk_level = metadata.get('risk_level', 'warning')
    trigger_reason = metadata.get('trigger_reason', 'Market Analysis Alert')
    charts_data = metadata.get('charts_data', {})

    # Output path
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(md_path),
            report_filename(slug, 'for', version, lang)
        )

    # Create document
    doc = create_doc(output_path)
    story = []
    styles = make_styles(lang=lang)

    # ═══════════════════════════════════════════
    # PAGE 1: COVER (using callback)
    # ═══════════════════════════════════════════
    def cover_callback(c, doc):
        draw_cover_forensic(
            c, doc,
            project_name=project_name,
            token_symbol=token_symbol,
            risk_level=risk_level,
            trigger_reason=trigger_reason,
            version=version,
            lang=lang
        )

    # ═══════════════════════════════════════════
    # PAGE 2+: CONTENT
    # ═══════════════════════════════════════════
    # Add first content page break
    story.append(PageBreak())

    # Process each section
    for section_title, section_content in sections:
        # Section header (returns list, must extend) - use forensic styling
        story.extend(section_header(section_title, styles, report_type='for'))

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
                # Use forensic red for table headers in forensic reports
                table = build_table(headers, rows, col_widths=col_widths, styles=styles, header_color='forensic_red')
                story.append(table)
                story.append(Spacer(1, 8))

                # Add chart if this is a known chart section
                title_lower = section_title.lower()
                header_str = ' '.join(headers).lower()
                is_risk = ('risk' in title_lower or 'severity' in header_str) and 'score' in header_str
                is_manipulation = ('manipulation' in title_lower or 'trading' in header_str) and ('wash' in header_str or 'spoofing' in header_str)

                if is_risk and charts_data.get('risk_indicators'):
                    try:
                        chart_buf = generate_risk_indicator_chart(charts_data['risk_indicators'])
                        img = Image(chart_buf, width=115*mm, height=70*mm)
                        story.append(img)
                        story.append(Spacer(1, 8))
                    except Exception as e:
                        print(f"Warning: Could not generate risk indicator chart: {e}")

                elif is_manipulation and charts_data.get('manipulation_scores'):
                    try:
                        chart_buf = generate_manipulation_detection_chart(charts_data['manipulation_scores'])
                        img = Image(chart_buf, width=110*mm, height=70*mm)
                        story.append(img)
                        story.append(Spacer(1, 8))
                    except Exception as e:
                        print(f"Warning: Could not generate manipulation detection chart: {e}")

        else:
            # No tables - just prose
            story.extend(markdown_to_paragraphs(section_content, styles))

    # Forensic multi-factor radar (if risk_indicators available)
    if charts_data.get('risk_indicators') and len(charts_data['risk_indicators']) >= 3:
        try:
            engine = get_chart_engine()
            cats = [r['name'][:20] for r in charts_data['risk_indicators'][:8]]
            vals = [r['score'] for r in charts_data['risk_indicators'][:8]]
            radar_buf = engine.render_radar_chart(
                categories=cats, values=vals,
                title='Forensic Risk Profile',
                color=Palette.DANGER,
                width=600, height=480,
            )
            story.append(Image(radar_buf, width=100*mm, height=80*mm))
            story.append(Spacer(1, 6*mm))
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # DISCLAIMER (Forensic-specific confidentiality notice)
    # ═══════════════════════════════════════════
    story.append(PageBreak())
    add_disclaimer(story, styles, report_type='for')

    # ═══════════════════════════════════════════
    # BUILD PDF
    # ═══════════════════════════════════════════
    header_footer_func = make_header_footer(project_name, 'for')
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

    md_path = os.path.join(output_dir, 'heyelsaai_for_v1_analysis.md')
    meta_path = os.path.join(output_dir, 'heyelsaai_for_v1_meta.json')

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

    # Extract trigger reason from markdown if not in metadata
    if 'trigger_reason' not in metadata:
        with open(md_path, 'r', encoding='utf-8') as f:
            md_first_lines = f.read()[:500]
        # Try to extract trigger reason from markdown
        if 'Trigger:' in md_first_lines:
            metadata['trigger_reason'] = 'Market Analysis Alert'
        else:
            metadata['trigger_reason'] = 'Forensic Analysis Triggered'

    # Generate PDF
    pdf_path = generate_pdf_for(md_path, metadata, lang='en')
    print(f"Success! Generated: {pdf_path}")
