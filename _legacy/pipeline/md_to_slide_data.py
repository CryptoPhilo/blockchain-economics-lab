"""
Bridge module: Extract slide data from .md file YAML frontmatter.

This module parses Markdown files with YAML frontmatter and extracts slide-ready
data compatible with gen_slide_html_*.py scripts (econ, mat, for variants).

Handles:
- YAML frontmatter parsing (content between --- markers)
- Extraction of slide_data section + top-level metadata
- Fallback data extraction from markdown body (tables, metrics)
- Graceful defaults for missing fields
- Type detection and auto-routing to correct builder function
"""

import yaml
import re
import json
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List


def parse_frontmatter(md_path: str) -> Tuple[dict, str]:
    """
    Parse YAML frontmatter and body from .md file.

    Frontmatter is the YAML content between --- markers at the top of the file.

    Args:
        md_path: Path to markdown file

    Returns:
        Tuple of (frontmatter_dict, body_text)
        Returns ({}, body) if no frontmatter found

    Raises:
        FileNotFoundError: If md_path does not exist
    """
    path = Path(md_path)
    if not path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    content = path.read_text(encoding='utf-8')

    # Check for frontmatter delimiter
    if not content.startswith('---'):
        return {}, content

    # Find the closing --- delimiter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content

    frontmatter_text, body = match.groups()

    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        print(f"Warning: Failed to parse YAML frontmatter: {e}")
        frontmatter = {}

    return frontmatter, body


def extract_tables_from_body(body: str) -> List[Dict[str, Any]]:
    """
    Extract markdown tables from body text as list of dicts.

    Parses pipe-delimited markdown tables and converts to list of row dicts.

    Args:
        body: Markdown body text

    Returns:
        List of table dicts, each with 'headers' and 'rows' keys
    """
    tables = []
    lines = body.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for table header (pipe delimited)
        if '|' in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # Check if next line is separator (pipes and dashes)
            if '|' in next_line and all(c in '|-: ' for c in next_line):
                headers = [h.strip() for h in line.split('|')[1:-1]]
                rows = []

                j = i + 2
                while j < len(lines) and '|' in lines[j]:
                    row_line = lines[j].strip()
                    if not all(c in '|-: ' for c in row_line):
                        cells = [c.strip() for c in row_line.split('|')[1:-1]]
                        if len(cells) == len(headers):
                            rows.append(dict(zip(headers, cells)))
                    j += 1

                if headers and rows:
                    tables.append({
                        'headers': headers,
                        'rows': rows
                    })

                i = j
                continue

        i += 1

    return tables


def extract_key_metrics(body: str) -> Dict[str, Any]:
    """
    Extract key numerical metrics from body text using regex patterns.

    Looks for patterns like:
    - "**Metric**: value" or "- Metric: value"
    - Percentage patterns: "##.##%"
    - Large numbers with units: "###,###B", "###M", etc.

    Args:
        body: Markdown body text

    Returns:
        Dict of extracted metrics {metric_name: value}
    """
    metrics = {}

    # Pattern 1: **Key**: value or - Key: value
    pattern1 = r'\*\*([^*]+)\*?\*?:\s*([^\n]+?)(?=\n|$)'
    for match in re.finditer(pattern1, body):
        key, value = match.groups()
        metrics[key.strip()] = value.strip()

    # Pattern 2: bullet points with metrics
    pattern2 = r'-\s+([^:]+):\s*([^\n]+)'
    for match in re.finditer(pattern2, body):
        key, value = match.groups()
        key = key.strip()
        value = value.strip()
        if key not in metrics:  # Don't override
            metrics[key] = value

    return metrics


def _build_econ_data(fm: dict, body: str) -> Dict[str, Any]:
    """
    Build gen_slide_html_econ.py compatible dict.

    Merges frontmatter slide_data with body-extracted data.

    Args:
        fm: Frontmatter dict
        body: Markdown body text

    Returns:
        Dict compatible with econ slide generator input schema
    """
    # Start with frontmatter slide_data
    slide_data = fm.get('slide_data', {}).copy() if isinstance(fm.get('slide_data'), dict) else {}

    # Top-level metadata
    data = {
        'title': fm.get('title', ''),
        'subtitle': fm.get('subtitle', ''),
        'author': fm.get('author', ''),
        'date': fm.get('date', ''),
        'language': fm.get('language', 'en'),
        'report_type': 'econ',
    }

    # Merge slide_data content
    data.update(slide_data)

    # Fallback: extract from body if not in frontmatter
    if not data.get('key_metrics'):
        data['key_metrics'] = extract_key_metrics(body)

    if not data.get('tables'):
        data['tables'] = extract_tables_from_body(body)

    # Ensure default empty structures
    data.setdefault('sections', [])
    data.setdefault('charts', [])
    data.setdefault('key_metrics', {})
    data.setdefault('tables', [])
    data.setdefault('footnotes', [])

    return data


def _build_mat_data(fm: dict, body: str) -> Dict[str, Any]:
    """
    Build gen_slide_html_mat.py compatible dict.

    For mathematical/technical content with equations and proofs.

    Args:
        fm: Frontmatter dict
        body: Markdown body text

    Returns:
        Dict compatible with mat slide generator input schema
    """
    slide_data = fm.get('slide_data', {}).copy() if isinstance(fm.get('slide_data'), dict) else {}

    data = {
        'title': fm.get('title', ''),
        'subtitle': fm.get('subtitle', ''),
        'author': fm.get('author', ''),
        'date': fm.get('date', ''),
        'language': fm.get('language', 'en'),
        'report_type': 'mat',
    }

    data.update(slide_data)

    # Extract equations/code blocks from body
    if not data.get('equations'):
        equations = re.findall(r'\$\$(.+?)\$\$', body, re.DOTALL)
        data['equations'] = equations

    if not data.get('tables'):
        data['tables'] = extract_tables_from_body(body)

    # Math-specific defaults
    data.setdefault('sections', [])
    data.setdefault('equations', [])
    data.setdefault('proofs', [])
    data.setdefault('theorems', [])
    data.setdefault('tables', [])
    data.setdefault('footnotes', [])

    return data


def _build_for_data(fm: dict, body: str) -> Dict[str, Any]:
    """
    Build gen_slide_html_for.py compatible dict.

    For forecast/scenario analysis content.

    Args:
        fm: Frontmatter dict
        body: Markdown body text

    Returns:
        Dict compatible with for slide generator input schema
    """
    slide_data = fm.get('slide_data', {}).copy() if isinstance(fm.get('slide_data'), dict) else {}

    data = {
        'title': fm.get('title', ''),
        'subtitle': fm.get('subtitle', ''),
        'author': fm.get('author', ''),
        'date': fm.get('date', ''),
        'language': fm.get('language', 'en'),
        'report_type': 'for',
    }

    data.update(slide_data)

    if not data.get('key_metrics'):
        data['key_metrics'] = extract_key_metrics(body)

    if not data.get('tables'):
        data['tables'] = extract_tables_from_body(body)

    # Forecast-specific defaults
    data.setdefault('scenarios', [])
    data.setdefault('key_metrics', {})
    data.setdefault('tables', [])
    data.setdefault('assumptions', [])
    data.setdefault('footnotes', [])

    return data


def extract_slide_data(md_path: str, report_type: str = None) -> Dict[str, Any]:
    """
    Extract slide-ready data dict from .md file.

    Auto-detects report_type from frontmatter if not provided.
    Routes to appropriate builder based on type.

    Args:
        md_path: Path to markdown file
        report_type: Optional override - 'econ', 'mat', or 'for'
                     Auto-detected from frontmatter if not provided

    Returns:
        Dict compatible with gen_slide_html_*.py input schema

    Raises:
        FileNotFoundError: If md_path does not exist
        ValueError: If report_type cannot be determined
    """
    fm, body = parse_frontmatter(md_path)

    # Determine report type
    detected_type = report_type or fm.get('report_type', '').lower()

    if not detected_type:
        raise ValueError(
            f"report_type not specified and not found in frontmatter of {md_path}. "
            "Specify report_type in frontmatter or as function argument."
        )

    # Route to appropriate builder
    if detected_type == 'econ':
        return _build_econ_data(fm, body)
    elif detected_type == 'mat':
        return _build_mat_data(fm, body)
    elif detected_type == 'for':
        return _build_for_data(fm, body)
    else:
        raise ValueError(
            f"Unknown report_type: {detected_type}. "
            "Must be one of: 'econ', 'mat', 'for'"
        )


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python md_to_slide_data.py <markdown_file> [report_type]")
        print("  markdown_file: Path to .md file with YAML frontmatter")
        print("  report_type: Optional - 'econ', 'mat', or 'for' (auto-detected if in frontmatter)")
        sys.exit(1)

    md_file = sys.argv[1]
    report_type = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        data = extract_slide_data(md_file, report_type)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
