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
    make_header_footer, add_disclaimer, create_doc, USABLE_W, C,
    wrap_cjk_runs,
)
from config import report_filename, COLORS
from chart_engine import get_chart_engine, Palette


# ═══════════════════════════════════════════
# MARKDOWN PARSER
# ═══════════════════════════════════════════
class MarkdownStructureError(ValueError):
    pass


_H2_SECTION_RE = re.compile(r'^##\s+(?P<title>.+?)\s*$', re.MULTILINE)
_NUMBERED_SECTION_RE = re.compile(
    r'^(?P<title>(?:\d+(?:\.\d+){0,2}[.)]?|[IVXLCM]+[.)])\s+.{3,120})$'
)
_BOLD_SECTION_RE = re.compile(r'^\*\*(?P<title>[^*\n]{3,120})\*\*$')
_FOR_SECTION_TITLE_HINTS = (
    'executive summary', 'summary', '요약', '개요',
    'macro', '시장 구조', 'market structure',
    'chart analysis', '기술적 분석', '차트 포렌식',
    'derivatives', '파생상품', '수급 분석',
    'on-chain', '온체인',
    'manipulation', '시장 조작', 'integrity',
    'conclusion', '결론', '대응 전략',
    'data reliability', '신뢰도', '한계',
)


def _clean_section_title(title: str) -> str:
    title = title.strip().lstrip('\ufeff')
    title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)
    return title.replace('\\', '').strip()


def _is_for_heading_title(title: str) -> bool:
    normalized = _clean_section_title(title).lower()
    return any(hint in normalized for hint in _FOR_SECTION_TITLE_HINTS)


def _parse_sections_with_detector(md_text, detector, mode):
    lines = md_text.splitlines()
    preamble_lines = []
    sections = []
    current_title = None
    current_lines = []

    for idx, raw_line in enumerate(lines):
        detected = detector(lines, idx)
        if detected:
            if current_title is None:
                preamble_lines = current_lines
            else:
                sections.append((current_title, '\n'.join(current_lines).strip()))
            current_title = _clean_section_title(detected)
            current_lines = []
            continue
        current_lines.append(raw_line)

    if current_title is None:
        return md_text.strip(), [], mode

    sections.append((current_title, '\n'.join(current_lines).strip()))
    preamble = '\n'.join(preamble_lines).strip()
    sections = [(title, content) for title, content in sections if title and content]
    return preamble, sections, mode


def _detect_h2_section(lines, idx):
    line = lines[idx].lstrip('\ufeff')
    m = _H2_SECTION_RE.match(line)
    return m.group('title') if m else None


def _detect_numbered_section(lines, idx):
    line = lines[idx].lstrip('\ufeff').strip()
    if not line:
        return None
    prev_blank = idx == 0 or not lines[idx - 1].strip()
    next_nonblank = idx + 1 < len(lines) and bool(lines[idx + 1].strip())
    allow_inline_numbered = bool(re.match(r'^\d+\.\s+', line))
    if ((not prev_blank and not allow_inline_numbered) or not next_nonblank
            or '|' in line or ':' in line):
        return None
    m = _NUMBERED_SECTION_RE.match(line)
    if not m or len(line.split()) > 12:
        return None
    return m.group('title').strip()


def _detect_bold_section(lines, idx):
    line = lines[idx].lstrip('\ufeff').strip()
    if not line:
        return None
    prev_blank = idx == 0 or not lines[idx - 1].strip()
    next_nonblank = idx + 1 < len(lines) and bool(lines[idx + 1].strip())
    if not prev_blank or not next_nonblank:
        return None
    m = _BOLD_SECTION_RE.match(line)
    return m.group('title') if m and len(m.group('title').split()) <= 12 else None


def _parse_markdown_sections(md_text):
    """
    Parse markdown into sections and report which detector was used.
    """
    preamble, sections, mode = _parse_sections_with_detector(md_text, _detect_h2_section, 'markdown_h2')
    if sections:
        return preamble, sections, mode

    preamble, sections, mode = _parse_sections_with_detector(md_text, _detect_numbered_section, 'numbered_fallback')
    if len(sections) >= 2 and any(_is_for_heading_title(title) for title, _ in sections):
        return preamble, sections, mode

    preamble, sections, mode = _parse_sections_with_detector(md_text, _detect_bold_section, 'bold_fallback')
    if len(sections) >= 2:
        return preamble, sections, mode

    return md_text.strip(), [], 'unparsed'


def parse_markdown(md_text):
    """
    Parse markdown into sections.
    Returns list of tuples: (section_title, content_text)
    """
    preamble, sections, _ = _parse_markdown_sections(md_text)
    return preamble, sections


def _validate_parsed_sections(md_path: str, md_text: str, sections, parse_mode: str) -> None:
    content_chars = sum(len(content.strip()) for _, content in sections)
    numbered_candidates = len(re.findall(r'(?m)^(?:\d+(?:\.\d+){0,2}[.)]?|[IVXLCM]+[.)])\s+.{3,120}$', md_text))
    bold_candidates = len(re.findall(r'(?m)^\*\*[^*\n]{3,120}\*\*$', md_text))
    h2_count = len(re.findall(r'(?m)^##\s+', md_text))

    if sections and content_chars >= 300:
        return

    raise MarkdownStructureError(
        f'FOR markdown parse failure for {md_path}: '
        f'mode={parse_mode}, sections={len(sections)}, h2={h2_count}, '
        f'numbered_candidates={numbered_candidates}, bold_candidates={bold_candidates}'
    )


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


def _strip_markdown_bold(text):
    """
    Robustly strip all **bold** markdown markers from text, converting to
    ReportLab <b> tags. Handles edge cases: unbalanced markers, nested,
    escaped, and stray asterisks.
    OPS-005 fix: ensures no literal ** ever appears in final PDF output.
    """
    # Step 1: Normalize escaped bold from Google Docs export
    text = re.sub(r'\\\*\\\*(.+?)\\\*\\\*', r'**\1**', text, flags=re.DOTALL)

    # Step 2: Balance ** markers — if odd count, drop the last unpaired one
    parts = text.split('**')
    if len(parts) > 1 and (len(parts) - 1) % 2 == 1:
        parts[-2] = parts[-2] + parts[-1]
        parts.pop()
        text = '**'.join(parts)

    # Step 3: Convert **bold** → <b>bold</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)

    # Step 4: Safety net — remove any remaining literal ** that slipped through
    text = text.replace('**', '')

    return text


def _strip_markdown_italic(text):
    """Convert *italic* → <i>italic</i>, avoiding false matches inside tags."""
    return re.sub(r'(?<![<\w/])\*([^*\n]+?)\*(?![>\w])', r'<i>\1</i>', text)


def markdown_to_paragraphs(text, styles, max_width=None, lang='en'):
    """
    Convert markdown text to reportlab Paragraphs, respecting basic formatting.
    Handles: **bold**, *italic*, ### sub-headers, bullet points

    Uses ECON pipeline's improved markdown_to_paragraphs() as primary path.
    Falls back to a robust local implementation that guarantees no stray **
    markers remain in the output (OPS-005).
    """
    # Import improved converter from gen_pdf_econ
    try:
        from gen_pdf_econ import markdown_to_paragraphs as _econ_md_to_para
        return _econ_md_to_para(text, styles, lang=lang)
    except Exception:
        pass

    # ── Robust fallback (OPS-005: guaranteed no literal ** in output) ──
    flowables = []
    text = clean_text_remove_tables(text)

    # Strip triple/double-backtick code fences
    text = re.sub(r'```[a-zA-Z0-9_-]*\n?', '', text)
    text = re.sub(r'``([\s\S]*?)``', r'\1', text)

    # Force each bullet onto its own paragraph
    text = re.sub(r'(?<!\n)\n(\s*(?:[*\-\u2022]|\d+[.)])\s+)', r'\n\n\1', text)

    for paragraph_text in text.split('\n\n'):
        p = paragraph_text.strip()
        if not p:
            continue

        if p.startswith('### '):
            sub_title = p[4:].strip()
            sub_title = _strip_markdown_bold(sub_title)
            sub_title = wrap_cjk_runs(sub_title, lang=lang)
            flowables.append(Spacer(1, 10))
            flowables.append(Paragraph(f'<b>{sub_title}</b>', styles['h3']))
            flowables.append(Spacer(1, 4))
            continue

        # Escape XML special chars before markdown conversion
        p = p.replace('&', '&amp;')

        # Convert markdown formatting to ReportLab XML
        p = _strip_markdown_bold(p)
        p = _strip_markdown_italic(p)

        # Strip stray backticks
        p = p.replace('`', '')

        # Strip markdown links: [text](url) → text
        p = re.sub(r'\[([^\]]+?)\]\([^)]+?\)', r'\1', p)

        # Sanitize stray < > that aren't valid XML tags
        p = re.sub(r'<(?!/?(?:b|i|font|sub|super|br)\b)', '&lt;', p)

        p = wrap_cjk_runs(p, lang=lang)

        if p.startswith('- ') or p.startswith('• ') or p.startswith('\u2022 '):
            bullet_text = re.sub(r'^[-•\u2022]\s*', '', p)
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
    preamble, sections, parse_mode = _parse_markdown_sections(md_text)
    _validate_parsed_sections(md_path, md_text, sections, parse_mode)
    if parse_mode != 'markdown_h2':
        print(f"[WARN] FOR markdown fallback parser engaged ({parse_mode}) for {md_path}")

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

    # Process each section — every ## section starts on a new page for clean layout
    for idx, (section_title, section_content) in enumerate(sections):
        # Add page break before every section (skip first — already on new page after cover)
        if idx > 0:
            story.append(PageBreak())

        # Section header (returns list, must extend) - use forensic styling
        story.extend(section_header(section_title, styles, report_type='for'))

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
            story.extend(markdown_to_paragraphs(section_content, styles, lang=lang))

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
