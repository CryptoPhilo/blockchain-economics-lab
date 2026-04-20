"""
Markdown-level QA Verification
==============================

Pre-PDF QA pass on translated / source .md files. Catches problems the
PDF-level QA can't cleanly flag back to the source (broken ASCII diagrams,
translation parity mismatches, fence mismatches, orphan placeholders).

Layers
------
1. Structural
   - File exists, non-empty
   - Fenced code blocks (``` / ~~~) open/close balanced
   - No trailing backslash-newline noise

2. Markdown residues that survive translation
   - Literal `\*`, `\_`, `\-`, `\/`, `\<`, `\>` (post-translation artefacts)
   - Stray HTML entities `&amp;/&lt;/&gt;` outside code fences

3. Broken ASCII flowchart / box-drawing diagrams
   - Clusters of `|` characters across >=3 lines with column drift > 2
     AND zero proper box-drawing (┌┐└┘─│) or arrow (→↓▼←) glyphs
   - Flagged as WARN; real fix = rewrite as mermaid.

4. Translation parity (only when paired with ko source)
   - Heading count (lines starting with `#`) must match ±1
   - Fenced code block count must match
   - Image link count (`![...](...)`) must match
   - Mermaid block count must match
   - Markdown table count (rows starting `|`) must match ±1

5. Language coverage (same rules as pdf QA)
   - ko: >= 200 Hangul chars
   - ja: >= 50 kana chars
   - zh: >= 200 CJK chars
   - en/fr/es/de: no big CJK fragments (> 30 chars → WARN)

Returns a QAReport compatible with qa_verify.py's schema so callers can
aggregate both layers.

Usage
-----
    from qa_verify_md import verify_markdown
    r = verify_markdown('path/ko.md', lang='ko')
    r_ja = verify_markdown('path/ja.md', lang='ja', ko_reference='path/ko.md')

CLI:
    python qa_verify_md.py path/to/file_ko.md
    python qa_verify_md.py --batch output/ --out md_qa.json
    python qa_verify_md.py --batch output/ --parity   # enable ko<->lang parity
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Reuse the dataclasses / severity enum from the PDF QA module
from qa_verify import QAReport, QACheck, QASeverity  # type: ignore


# ─── Regexes ────────────────────────────────────────────────────────────────
_HANGUL_RE = re.compile(r'[\uAC00-\uD7AF]')
_HIRAGANA_RE = re.compile(r'[\u3040-\u309F]')
_KATAKANA_RE = re.compile(r'[\u30A0-\u30FF]')
_CJK_RE = re.compile(r'[\u4E00-\u9FFF]')
_ATX_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
_NUMBERED_SECTION_RE = re.compile(
    r'^(?:\d+(?:\.\d+){0,2}[.)]?|[IVXLCM]+[.)])\s+(.{3,120})$'
)
_BOLD_HEADING_RE = re.compile(r'^\*\*([^*\n]{3,120})\*\*$')
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

_MD_RESIDUE_PATTERNS = [
    (r'\\\*', r'escaped \\* backslash'),
    (r'\\_', r'escaped \\_ backslash'),
    (r'(?<!\w)\\-(?!\w)', r'escaped \\- backslash'),
    (r'\\/', r'escaped \\/ backslash'),
    (r'\\<', r'escaped \\< backslash'),
    (r'\\>', r'escaped \\> backslash'),
]

_BOX_DRAW_RE = re.compile(r'[┌┐└┘─│├┤┬┴┼╔╗╚╝═║╠╣╦╩╬▲▼◀▶→←↑↓]')
_ASCII_DIAGRAM_HINT_RE = re.compile(r'^[\s|+\-=<>^vV]*$')


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')


def _strip_code_fences(text: str) -> str:
    """Return text with contents of fenced code blocks removed (keep markers)."""
    out_lines: List[str] = []
    in_fence = False
    for line in text.splitlines():
        if re.match(r'^\s*(```|~~~)', line):
            in_fence = not in_fence
            out_lines.append(line)
        elif not in_fence:
            out_lines.append(line)
    return '\n'.join(out_lines)


def _collect_code_blocks(text: str) -> List[Tuple[str, List[str]]]:
    """Return list of (fence_lang, lines) for each fenced block."""
    blocks: List[Tuple[str, List[str]]] = []
    lang = ''
    buf: List[str] = []
    in_fence = False
    for line in text.splitlines():
        m = re.match(r'^\s*(?:```|~~~)\s*([a-zA-Z0-9_+-]*)\s*$', line)
        if m and not in_fence:
            in_fence = True
            lang = m.group(1)
            buf = []
        elif re.match(r'^\s*(?:```|~~~)\s*$', line) and in_fence:
            blocks.append((lang, buf))
            in_fence = False
        elif in_fence:
            buf.append(line)
    if in_fence:
        # unterminated
        blocks.append((lang + ':UNCLOSED', buf))
    return blocks


def _collect_headings_by_level(text: str) -> Dict[int, List[str]]:
    headings: Dict[int, List[str]] = {i: [] for i in range(1, 7)}
    for raw_line in text.splitlines():
        line = raw_line.lstrip('\ufeff').strip()
        if not line:
            continue
        m = _ATX_HEADING_RE.match(line)
        if not m:
            continue
        headings[len(m.group(1))].append(m.group(2).strip())
    return headings


def _collect_heading_like_lines(text: str) -> Dict[str, List[str]]:
    numbered: List[str] = []
    bold: List[str] = []
    lines = text.splitlines()
    for idx, raw_line in enumerate(lines):
        line = raw_line.lstrip('\ufeff').strip()
        if not line:
            continue
        prev_blank = idx == 0 or not lines[idx - 1].strip()
        next_nonblank = idx + 1 < len(lines) and bool(lines[idx + 1].strip())
        allow_inline_numbered = bool(re.match(r'^\d+\.\s+', line))
        if (not prev_blank and not allow_inline_numbered) or not next_nonblank:
            continue
        if '|' in line or ':' in line:
            continue

        m = _NUMBERED_SECTION_RE.match(line)
        if m and len(line.split()) <= 12:
            numbered.append(line)
            continue

        m = _BOLD_HEADING_RE.match(line)
        if m and len(m.group(1).split()) <= 12:
            bold.append(m.group(1).strip())
    return {'numbered': numbered, 'bold': bold}


def _is_for_heading_title(title: str) -> bool:
    normalized = title.lstrip('\ufeff').strip().lower()
    return any(hint in normalized for hint in _FOR_SECTION_TITLE_HINTS)


# ─── Individual checks ───────────────────────────────────────────────────────
def _check_structure(report: QAReport, text: str) -> None:
    if len(text.strip()) < 100:
        report.add(QACheck('md.structure.size', QASeverity.FAIL,
                           f'file too short ({len(text)} chars)'))
        return
    report.add(QACheck('md.structure.size', QASeverity.PASS,
                       f'{len(text)} chars'))

    # Fence balance
    opens = len(re.findall(r'(?m)^\s*(```|~~~)[a-zA-Z0-9_+-]*\s*$', text))
    closes = len(re.findall(r'(?m)^\s*(```|~~~)\s*$', text))
    total = opens + closes
    if total % 2 != 0:
        report.add(QACheck('md.structure.fences', QASeverity.FAIL,
                           f'unbalanced fences (total markers: {total})'))
    else:
        report.add(QACheck('md.structure.fences', QASeverity.PASS,
                           f'{total // 2} fenced blocks'))


def _check_heading_structure(report: QAReport, text: str, report_type: str = 'econ') -> None:
    headings = _collect_headings_by_level(text)
    heading_like = _collect_heading_like_lines(text)
    h2_count = len(headings[2])
    numbered = heading_like['numbered']
    bold = heading_like['bold']
    suspicious = numbered + bold

    # FOR reports can still be recoverable when translators collapse `##` markers
    # into clean numbered section titles. Treat that as a warning here and rely on
    # ko-reference parity to hard-fail real translation-structure regressions.
    if (
        report_type == 'for'
        and h2_count == 0
        and len(numbered) >= 3
        and not bold
    ):
        if not any(_is_for_heading_title(title) for title in numbered):
            report.add(QACheck(
                'md.structure.section_markers',
                QASeverity.PASS,
                f'numbered list detected without FOR section-heading signals ({len(numbered)} items)',
                samples=numbered[:5],
            ))
            return
        report.add(QACheck(
            'md.structure.section_markers',
            QASeverity.WARN,
            f'no markdown H2 sections found; detected {len(numbered)} recoverable numbered '
            f'section lines outside markdown structure',
            samples=numbered[:5],
        ))
        return

    if h2_count == 0 and len(suspicious) >= 3:
        report.add(QACheck(
            'md.structure.section_markers',
            QASeverity.FAIL,
            f'no markdown H2 sections found; detected {len(suspicious)} heading-like lines '
            f'outside markdown structure',
            samples=suspicious[:5],
        ))
    elif h2_count < 2 and len(suspicious) >= 3:
        report.add(QACheck(
            'md.structure.section_markers',
            QASeverity.WARN,
            f'only {h2_count} markdown H2 sections found; detected {len(suspicious)} additional '
            f'heading-like lines outside markdown structure',
            samples=suspicious[:5],
        ))
    else:
        report.add(QACheck(
            'md.structure.section_markers',
            QASeverity.PASS,
            f'markdown H2 sections={h2_count}',
        ))


def _check_residues(report: QAReport, text: str) -> None:
    stripped = _strip_code_fences(text)
    found = False
    for pat, label in _MD_RESIDUE_PATTERNS:
        ms = re.findall(pat, stripped)
        if ms:
            found = True
            report.add(QACheck(f'md.residue.{label}', QASeverity.WARN,
                               f'{len(ms)} occurrences'))
    # HTML entity leaks outside code
    for ent in ('&amp;', '&lt;', '&gt;'):
        if ent in stripped:
            found = True
            report.add(QACheck(f'md.residue.entity_{ent}', QASeverity.WARN,
                               f'html entity leak: {ent}'))
    if not found:
        report.add(QACheck('md.residue', QASeverity.PASS, 'no residues'))


def _check_broken_ascii_diagram(report: QAReport, text: str) -> None:
    """
    Heuristic: find runs of >=3 consecutive lines where each line is dense
    with `|`, `-`, `+` and whitespace but has no proper box-drawing or arrow
    glyphs. Likely a flowchart that lost its box chars during translation.
    """
    lines = text.splitlines()
    i = 0
    broken_runs: List[Tuple[int, int]] = []
    while i < len(lines):
        # must contain at least 2 '|' and look like ASCII art
        if lines[i].count('|') >= 2 and _ASCII_DIAGRAM_HINT_RE.match(lines[i]):
            j = i
            while (j < len(lines)
                   and lines[j].count('|') >= 2
                   and _ASCII_DIAGRAM_HINT_RE.match(lines[j])):
                j += 1
            if j - i >= 3:
                block = '\n'.join(lines[i:j])
                # if has proper box chars or arrows, skip — it's fine
                if not _BOX_DRAW_RE.search(block):
                    broken_runs.append((i + 1, j))
            i = j
        else:
            i += 1
    if broken_runs:
        samples = [f'lines {s}-{e}' for s, e in broken_runs[:3]]
        report.add(QACheck('md.diagram.broken_ascii', QASeverity.WARN,
                           f'{len(broken_runs)} suspected broken ASCII diagram(s)',
                           samples=samples))
    else:
        report.add(QACheck('md.diagram.broken_ascii', QASeverity.PASS,
                           'no broken ASCII diagrams'))


def _check_broken_tables(report: QAReport, text: str) -> None:
    """
    Detect broken markdown tables. A well-formed table requires:
      - header line: `| a | b | c |`
      - separator line directly below: `|---|---|---|`  (colons allowed)
      - >= 1 data row with same column count
    Flags:
      FAIL — header + separator present but column counts disagree across rows
      FAIL — header has >=3 cells but no separator directly below it
      WARN — orphan table-like lines (single `|` row with no neighbors)
      WARN — separator row with wrong dash/colon chars (post-translation damage)
    """
    lines = text.splitlines()
    # Strip fenced code blocks from consideration
    in_fence = False
    masked: List[str] = []
    for ln in lines:
        if re.match(r'^\s*(```|~~~)', ln):
            in_fence = not in_fence
            masked.append('')
        else:
            masked.append('' if in_fence else ln)

    def count_cells(s: str) -> int:
        s = s.strip()
        if not s.startswith('|') or not s.endswith('|'):
            # Allow tables without leading/trailing pipes too
            parts = s.split('|')
        else:
            parts = s.strip('|').split('|')
        return len([p for p in parts if True])  # include empty cells

    sep_re = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$')
    bad_sep_re = re.compile(r'^\s*\|[\s\|\-–—−=:]{4,}\|\s*$')  # looks like sep but uses em/en-dash, =, etc.
    row_re = re.compile(r'^\s*\|.*\|\s*$')

    fails: List[str] = []
    warns: List[str] = []

    i = 0
    n = len(masked)
    while i < n:
        line = masked[i]
        prev_blank = i == 0 or masked[i-1].strip() == ''
        # Only treat as header candidate when the preceding line is blank /
        # start of file. Otherwise it is likely a data row inside an already-
        # parsed table.
        if prev_blank and row_re.match(line) and line.count('|') >= 3:
            header_cells = count_cells(line)
            # Next non-blank line
            j = i + 1
            while j < n and masked[j].strip() == '':
                j += 1
            if j >= n:
                i += 1
                continue
            nxt = masked[j]
            if sep_re.match(nxt):
                # Valid table — verify data rows
                sep_cells = count_cells(nxt)
                if header_cells != sep_cells:
                    fails.append(f'line {i+1}: header {header_cells} cols vs sep {sep_cells} cols')
                # Check subsequent data rows
                k = j + 1
                bad_rows = 0
                total_rows = 0
                while k < n and row_re.match(masked[k]):
                    total_rows += 1
                    if count_cells(masked[k]) != header_cells:
                        bad_rows += 1
                    k += 1
                if bad_rows > 0 and total_rows > 0:
                    fails.append(f'line {i+1}: {bad_rows}/{total_rows} rows with mismatched column count')
                i = k
                continue
            elif bad_sep_re.match(nxt) and not sep_re.match(nxt):
                warns.append(f'line {j+1}: separator row uses damaged chars (em/en-dash or =)')
                i = j + 1
                continue
            elif row_re.match(nxt) and header_cells >= 3:
                # 2+ rows of pipes but no separator
                # Only flag if cluster is >= 3 rows (else too noisy)
                cluster = 2
                k = j + 1
                while k < n and row_re.match(masked[k]):
                    cluster += 1
                    k += 1
                if cluster >= 3:
                    fails.append(f'line {i+1}: {cluster} pipe-rows with no header separator')
                i = k
                continue
        i += 1

    # Orphan single-row pipes (heuristic, low priority)
    for idx, ln in enumerate(masked):
        if row_re.match(ln) and ln.count('|') >= 3:
            prev_blank = idx == 0 or masked[idx-1].strip() == ''
            next_blank = idx == n-1 or masked[idx+1].strip() == ''
            if prev_blank and next_blank:
                warns.append(f'line {idx+1}: orphan table row (isolated)')

    if fails:
        report.add(QACheck('md.table.broken', QASeverity.FAIL,
                           f'{len(fails)} broken table issue(s)',
                           samples=fails[:5]))
    elif warns:
        report.add(QACheck('md.table.broken', QASeverity.WARN,
                           f'{len(warns)} suspicious table pattern(s)',
                           samples=warns[:5]))
    else:
        report.add(QACheck('md.table.broken', QASeverity.PASS,
                           'no broken tables'))


def _check_language(report: QAReport, text: str, lang: str) -> None:
    body = _strip_code_fences(text)
    h = len(_HANGUL_RE.findall(body))
    ki = len(_HIRAGANA_RE.findall(body))
    ka = len(_KATAKANA_RE.findall(body))
    cj = len(_CJK_RE.findall(body))

    if lang == 'ko':
        if h < 200:
            report.add(QACheck('md.lang.ko_hangul', QASeverity.FAIL,
                               f'only {h} Hangul chars'))
        else:
            report.add(QACheck('md.lang.ko_hangul', QASeverity.PASS,
                               f'{h} Hangul chars'))
    elif lang == 'ja':
        if (ki + ka) < 50:
            report.add(QACheck('md.lang.ja_kana', QASeverity.FAIL,
                               f'only {ki + ka} kana chars — likely untranslated'))
        else:
            report.add(QACheck('md.lang.ja_kana', QASeverity.PASS,
                               f'{ki + ka} kana chars'))
    elif lang == 'zh':
        if cj < 200:
            report.add(QACheck('md.lang.zh_cjk', QASeverity.FAIL,
                               f'only {cj} CJK chars'))
        else:
            report.add(QACheck('md.lang.zh_cjk', QASeverity.PASS,
                               f'{cj} CJK chars'))
    elif lang in ('en', 'fr', 'es', 'de'):
        total_cjk = h + ki + ka + cj
        # Allow a little CJK for product names; > 80 chars suggests bad translation
        if total_cjk > 80:
            report.add(QACheck(f'md.lang.{lang}_latin', QASeverity.WARN,
                               f'significant CJK in body (hangul={h}, kana={ki + ka}, '
                               f'hanzi={cj}) — translation incomplete?'))
        else:
            report.add(QACheck(f'md.lang.{lang}_latin', QASeverity.PASS,
                               f'latin-script ({total_cjk} stray CJK)'))


def _count_features(text: str) -> Dict[str, int]:
    stripped = _strip_code_fences(text)
    blocks = _collect_code_blocks(text)
    mermaid_n = sum(1 for lang, _ in blocks if lang.startswith('mermaid'))
    # heading counts (atx)
    headings = len(re.findall(r'(?m)^#{1,6}\s+\S', stripped))
    # image links (markdown, not HTML)
    images = len(re.findall(r'!\[[^\]]*\]\([^)]+\)', stripped))
    # table rows (consecutive lines starting with `|`)
    table_rows = len(re.findall(r'(?m)^\s*\|[^\n]*\|\s*$', stripped))
    return dict(headings=headings, fenced=len(blocks), mermaid=mermaid_n,
                images=images, table_rows=table_rows)


def _check_parity(report: QAReport, text: str, ko_text: str) -> None:
    a = _count_features(ko_text)
    b = _count_features(text)

    def cmp(key: str, tol: int, severity: QASeverity) -> None:
        if abs(a[key] - b[key]) > tol:
            report.add(QACheck(f'md.parity.{key}', severity,
                               f'ko={a[key]} vs lang={b[key]} (tol ±{tol})'))
        else:
            report.add(QACheck(f'md.parity.{key}', QASeverity.PASS,
                               f'ko={a[key]} lang={b[key]}'))

    cmp('headings', 1, QASeverity.WARN)
    cmp('fenced', 0, QASeverity.WARN)
    cmp('mermaid', 0, QASeverity.WARN)
    cmp('images', 0, QASeverity.WARN)
    cmp('table_rows', 2, QASeverity.WARN)

    ko_headings = _collect_headings_by_level(ko_text)
    lang_headings = _collect_headings_by_level(text)
    heading_like = _collect_heading_like_lines(text)
    ko_h2 = len(ko_headings[2])
    lang_h2 = len(lang_headings[2])
    suspicious = heading_like['numbered'] + heading_like['bold']

    if ko_h2 >= 3:
        missing_h2 = ko_h2 - lang_h2
        if lang_h2 == 0 and suspicious:
            report.add(QACheck(
                'md.parity.section_structure',
                QASeverity.FAIL,
                f'ko has {ko_h2} H2 sections but translation has none; '
                f'found {len(suspicious)} heading-like lines that may have collapsed '
                f'out of markdown structure',
                samples=suspicious[:5],
            ))
        elif missing_h2 > max(1, ko_h2 // 3):
            severity = QASeverity.FAIL if missing_h2 >= max(2, ko_h2 // 2) else QASeverity.WARN
            detail = f'ko H2 sections={ko_h2} vs lang H2 sections={lang_h2}'
            if suspicious:
                detail += f'; heading-like lines outside markdown={len(suspicious)}'
            report.add(QACheck(
                'md.parity.section_structure',
                severity,
                detail,
                samples=suspicious[:5],
            ))
        else:
            report.add(QACheck(
                'md.parity.section_structure',
                QASeverity.PASS,
                f'ko H2 sections={ko_h2} lang H2 sections={lang_h2}',
            ))


# ─── Entry points ───────────────────────────────────────────────────────────
def verify_markdown(md_path: str | Path, lang: Optional[str] = None,
                    ko_reference: Optional[str | Path] = None,
                    report_type: str = 'econ') -> QAReport:
    path = Path(md_path)
    if lang is None:
        m = re.search(r'_(ko|en|ja|zh|fr|es|de)\.md$', path.name)
        lang = m.group(1) if m else 'en'

    report = QAReport(path=str(path), lang=lang, report_type=report_type)

    if not path.exists():
        report.add(QACheck('md.structure.file', QASeverity.FAIL,
                           f'file not found: {path}'))
        return report

    text = _read(path)
    _check_structure(report, text)
    _check_heading_structure(report, text, report_type=report_type)
    _check_residues(report, text)
    _check_broken_ascii_diagram(report, text)
    _check_broken_tables(report, text)
    _check_language(report, text, lang)

    if ko_reference:
        ko_path = Path(ko_reference)
        if ko_path.exists():
            _check_parity(report, text, _read(ko_path))
        else:
            report.add(QACheck('md.parity.ref', QASeverity.WARN,
                               f'ko reference not found: {ko_path}'))

    return report


def _infer_ko_reference(md_path: Path) -> Optional[Path]:
    """For path foo_ja.md return foo_ko.md if it exists."""
    m = re.match(r'(.+)_(ko|en|ja|zh|fr|es|de)\.md$', md_path.name)
    if not m:
        return None
    base, lang = m.group(1), m.group(2)
    if lang == 'ko':
        return None
    ko = md_path.with_name(f'{base}_ko.md')
    return ko if ko.exists() else None


def batch_verify(directory: str | Path, out_json: Optional[str] = None,
                 parity: bool = True) -> List[QAReport]:
    d = Path(directory)
    reports: List[QAReport] = []
    md_files = sorted(p for p in d.rglob('*.md')
                      if re.search(r'_(ko|en|ja|zh|fr|es|de)\.md$', p.name))
    for md in md_files:
        ko_ref = _infer_ko_reference(md) if parity else None
        r = verify_markdown(md, ko_reference=str(ko_ref) if ko_ref else None)
        reports.append(r)
        flag = {'PASS': 'OK', 'WARN': '!', 'FAIL': 'X'}[r.severity.value]
        fails = sum(1 for c in r.checks if c.severity == QASeverity.FAIL)
        warns = sum(1 for c in r.checks if c.severity == QASeverity.WARN)
        print(f'[{flag}] {r.severity.value:4s} {md.name:55s} '
              f'fail={fails} warn={warns}')

    if out_json:
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump([r.to_dict() for r in reports], f,
                      ensure_ascii=False, indent=2)
        print(f'Wrote {out_json}')
    return reports


def main() -> int:
    ap = argparse.ArgumentParser(description='Markdown QA verification')
    ap.add_argument('md', nargs='?', help='single .md path')
    ap.add_argument('--lang', default=None)
    ap.add_argument('--ko-ref', default=None,
                    help='ko reference for parity check (auto-inferred in batch)')
    ap.add_argument('--batch', help='directory to scan')
    ap.add_argument('--out', help='write json report to path')
    ap.add_argument('--no-parity', action='store_true',
                    help='skip ko<->lang parity check in batch mode')
    args = ap.parse_args()

    if args.batch:
        reports = batch_verify(args.batch, out_json=args.out,
                               parity=not args.no_parity)
        fails = [r for r in reports if r.severity == QASeverity.FAIL]
        print(f'\nSummary: {len(reports)} files, '
              f'{len(fails)} FAIL, '
              f'{sum(1 for r in reports if r.severity == QASeverity.WARN)} WARN')
        return 1 if fails else 0

    if not args.md:
        ap.print_help()
        return 2

    r = verify_markdown(args.md, lang=args.lang, ko_reference=args.ko_ref)
    print(f'\n═══ {r.path} ({r.lang}) ═══')
    print(f'Overall: {r.severity.value}')
    for c in r.checks:
        mark = {'PASS': 'OK', 'WARN': '!', 'FAIL': 'X'}[c.severity.value]
        print(f'  [{mark}] {c.name:40s} {c.severity.value:4s}  {c.detail}')
        for s in c.samples[:3]:
            print(f'         sample: {s!r}')
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(r.to_dict(), f, ensure_ascii=False, indent=2)
    return 0 if r.severity != QASeverity.FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
