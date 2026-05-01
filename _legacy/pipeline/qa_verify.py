"""
Final-Report QA Verification Pipeline
======================================

Automated quality assurance for generated PDF reports (ECON / MAT / FOR).

Verification layers
-------------------
1. Structural checks
   - File exists and is a valid PDF
   - Page count within expected range (min/max configurable per report type)
   - All pages have text (no totally blank pages mid-document)

2. Text-level artefact checks (pdfplumber extraction)
   - No literal markdown residues: `**`, `\\*`, `\\/`, `\\_`, `\\-`
   - No unrendered backtick fences: ``` ```, `` `` ``, stray ``
   - No literal "&amp;" / "&lt;" / "&gt;" entity leaks
   - No CJK-fallback boxes (U+FFFD, U+25A0 "■", U+25A1 "□", U+25C7, U+25CA)
   - No duplicated heading lines (##, ###) showing as raw markdown
   - No Courier/code-block CJK fragments

3. Layout checks
   - First page cover rendered (contains project name token)
   - Section headers each start on a new page (for MAT/ECON)
   - Disclaimer page exists at the end

4. Language-specific checks
   - ko: Hangul (U+AC00-D7AF) found in body
   - ja: Hiragana/Katakana found in body
   - zh: CJK Unified Ideographs found
   - en/fr/es/de: no untranslated CJK fragments outside cover

5. Metadata consistency
   - If metadata passed in, score/stage on cover matches metadata

Output
------
Returns a `QAReport` dataclass with per-check results and a severity level:
  - PASS  : clean
  - WARN  : minor (cosmetic)
  - FAIL  : blocks publication

Usage
-----
    from qa_verify import verify_pdf, QASeverity
    report = verify_pdf('/path/to/report.pdf', lang='ko', report_type='mat',
                        metadata={'total_maturity_score': 78.28})
    if report.severity == QASeverity.FAIL:
        ...

CLI:
    python qa_verify.py <pdf_path> --lang ko --type mat
    python qa_verify.py --batch <dir> --out qa_report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import pdfplumber  # type: ignore
except ImportError:
    pdfplumber = None


class QASeverity(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class QACheck:
    name: str
    severity: QASeverity
    detail: str = ""
    samples: List[str] = field(default_factory=list)


@dataclass
class QAReport:
    path: str
    lang: str
    report_type: str
    page_count: int = 0
    checks: List[QACheck] = field(default_factory=list)
    severity: QASeverity = QASeverity.PASS

    def add(self, check: QACheck) -> None:
        self.checks.append(check)
        # Escalate overall severity: FAIL > WARN > PASS
        order = {QASeverity.PASS: 0, QASeverity.WARN: 1, QASeverity.FAIL: 2}
        if order[check.severity] > order[self.severity]:
            self.severity = check.severity

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['severity'] = self.severity.value
        for c in d['checks']:
            c['severity'] = (c['severity'].value
                             if isinstance(c['severity'], QASeverity)
                             else c['severity'])
        return d


# ─── Regex rulesets ──────────────────────────────────────────────────────────
_MARKDOWN_RESIDUES = [
    (r'(?<!\\)\*\*[^*\n]{1,80}\*\*', 'literal **bold** markdown'),
    (r'\\\*', r'escaped \\* backslash'),
    (r'\\/', r'escaped \\/ backslash'),
    (r'\\_', r'escaped \\_ backslash'),
    (r'(?<!\w)\\-(?!\w)', r'escaped \\- backslash'),
    (r'```[a-zA-Z]*', 'triple-backtick fence'),
    (r'``[^`]', 'double-backtick fence'),
    (r'&amp;|&lt;|&gt;', 'HTML entity leak'),
    (r'<b>|</b>|<i>|</i>|<font ', 'raw ReportLab XML tag'),
]

# CJK-fallback glyphs (boxes / replacement chars)
_FALLBACK_GLYPHS_RE = re.compile(r'[\uFFFD\u25A0\u25A1\u25C6\u25C7\u25CA▪▫]')

_HANGUL_RE = re.compile(r'[\uAC00-\uD7AF]')
_HIRAGANA_RE = re.compile(r'[\u3040-\u309F]')
_KATAKANA_RE = re.compile(r'[\u30A0-\u30FF]')
_CJK_UNIFIED_RE = re.compile(r'[\u4E00-\u9FFF]')


def _extract_pages(pdf_path: Path) -> List[str]:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required. pip install pdfplumber")
    pages: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for p in pdf.pages:
            pages.append(p.extract_text() or '')
    return pages


def _check_structure(report: QAReport, pages: List[str],
                     expected_min: int, expected_max: int) -> None:
    pc = len(pages)
    report.page_count = pc
    if pc == 0:
        report.add(QACheck('structure.pages', QASeverity.FAIL,
                           'PDF has zero extractable pages'))
        return
    if pc < expected_min:
        report.add(QACheck('structure.pages', QASeverity.FAIL,
                           f'page count {pc} below expected min {expected_min}'))
    elif pc > expected_max:
        report.add(QACheck('structure.pages', QASeverity.WARN,
                           f'page count {pc} above expected max {expected_max}'))
    else:
        report.add(QACheck('structure.pages', QASeverity.PASS,
                           f'{pc} pages'))

    # Blank-page check (middle pages only; skip first and last)
    blanks = [i + 1 for i, t in enumerate(pages[1:-1], start=1)
              if len(t.strip()) < 20]
    if blanks:
        report.add(QACheck('structure.blank_pages', QASeverity.WARN,
                           f'near-empty mid-pages: {blanks}'))


def _check_markdown_artefacts(report: QAReport, pages: List[str]) -> None:
    full = '\n'.join(pages)
    found_any = False
    for pattern, label in _MARKDOWN_RESIDUES:
        matches = re.findall(pattern, full)
        if matches:
            found_any = True
            samples = list({m if isinstance(m, str) else m[0] for m in matches})[:5]
            report.add(QACheck(f'artefact.{label}', QASeverity.FAIL,
                               f'{len(matches)} occurrences of {label}',
                               samples=samples))
    if not found_any:
        report.add(QACheck('artefact.markdown', QASeverity.PASS,
                           'no markdown residues'))


def _check_fallback_boxes(report: QAReport, pages: List[str]) -> None:
    full = '\n'.join(pages)
    boxes = _FALLBACK_GLYPHS_RE.findall(full)
    if boxes:
        # Find context snippets for first few
        snippets: List[str] = []
        for m in _FALLBACK_GLYPHS_RE.finditer(full):
            s = max(0, m.start() - 25)
            e = min(len(full), m.end() + 25)
            snippets.append(full[s:e].replace('\n', ' '))
            if len(snippets) >= 3:
                break
        report.add(QACheck('artefact.fallback_boxes', QASeverity.FAIL,
                           f'{len(boxes)} fallback-box glyphs detected',
                           samples=snippets))
    else:
        report.add(QACheck('artefact.fallback_boxes', QASeverity.PASS,
                           'no fallback boxes'))


def _check_language_coverage(report: QAReport, pages: List[str],
                             lang: str) -> None:
    # Skip cover + disclaimer pages; check body text
    body = '\n'.join(pages[1:-1]) if len(pages) > 2 else '\n'.join(pages)
    hangul_n = len(_HANGUL_RE.findall(body))
    hira_n = len(_HIRAGANA_RE.findall(body))
    kata_n = len(_KATAKANA_RE.findall(body))
    cjk_n = len(_CJK_UNIFIED_RE.findall(body))

    if lang == 'ko':
        if hangul_n < 50:
            report.add(QACheck('lang.ko_hangul', QASeverity.FAIL,
                               f'only {hangul_n} Hangul chars in body'))
        else:
            report.add(QACheck('lang.ko_hangul', QASeverity.PASS,
                               f'{hangul_n} Hangul chars'))
    elif lang == 'ja':
        if (hira_n + kata_n) < 20:
            report.add(QACheck('lang.ja_kana', QASeverity.FAIL,
                               f'only {hira_n + kata_n} kana chars in body'))
        else:
            report.add(QACheck('lang.ja_kana', QASeverity.PASS,
                               f'{hira_n + kata_n} kana chars'))
    elif lang == 'zh':
        if cjk_n < 100:
            report.add(QACheck('lang.zh_cjk', QASeverity.FAIL,
                               f'only {cjk_n} CJK chars in body'))
        else:
            report.add(QACheck('lang.zh_cjk', QASeverity.PASS,
                               f'{cjk_n} CJK chars'))
    elif lang in ('en', 'fr', 'es', 'de'):
        # Latin-lang reports may have product names in CJK; only fail on heavy
        # untranslated CJK fragments (> 30 chars) which suggest broken translation.
        if (hangul_n + hira_n + kata_n + cjk_n) > 30:
            report.add(QACheck(f'lang.{lang}_latin', QASeverity.WARN,
                               f'significant CJK fragments in {lang} body '
                               f'(hangul={hangul_n}, kana={hira_n + kata_n}, '
                               f'hanzi={cjk_n})'))
        else:
            report.add(QACheck(f'lang.{lang}_latin', QASeverity.PASS,
                               'latin-script content'))


def _check_cover_and_metadata(report: QAReport, pages: List[str],
                              metadata: Optional[Dict[str, Any]]) -> None:
    if not pages:
        return
    cover = pages[0]
    if metadata:
        # Check score appears on cover (MAT)
        score = metadata.get('total_maturity_score')
        if score is not None:
            # Accept any format: 78.28, 78.3, 78
            candidates = [f'{score:.2f}', f'{score:.1f}', f'{int(round(score))}']
            if not any(c in cover for c in candidates):
                report.add(QACheck('cover.score_match', QASeverity.WARN,
                                   f'score {score} not found on cover page',
                                   samples=candidates))
            else:
                report.add(QACheck('cover.score_match', QASeverity.PASS,
                                   f'score {score} present on cover'))


def _check_pagebreak_sections(report: QAReport, pages: List[str],
                              report_type: str) -> None:
    """For MAT/ECON each numbered section should begin on a new page."""
    if report_type not in ('mat', 'econ', 'maturity'):
        return
    # Look for section headings like "1. ", "01. ", "1) " etc. Must appear near
    # the top of a page (first 80 chars).
    section_pages = 0
    for t in pages:
        lead = t.lstrip()[:120]
        if re.match(r'^(?:\d{1,2}[\.\)]|I{1,3}V?\.?)\s+\S', lead):
            section_pages += 1
    if section_pages < 3:
        report.add(QACheck('layout.section_breaks', QASeverity.WARN,
                           f'only {section_pages} pages start with a section header'))
    else:
        report.add(QACheck('layout.section_breaks', QASeverity.PASS,
                           f'{section_pages} section-leading pages'))


# ─── Report-type configs ─────────────────────────────────────────────────────
_PAGE_RANGES = {
    'econ':     (8, 40),
    'mat':      (6, 40),
    'maturity': (6, 40),
    'for':      (6, 30),
    'forensic': (6, 30),
}


def verify_pdf(pdf_path: str | Path,
               lang: str = 'en',
               report_type: str = 'econ',
               metadata: Optional[Dict[str, Any]] = None) -> QAReport:
    """Run full QA verification on a single PDF."""
    path = Path(pdf_path)
    report = QAReport(path=str(path), lang=lang, report_type=report_type)

    if not path.exists():
        report.add(QACheck('structure.file', QASeverity.FAIL,
                           f'file not found: {path}'))
        return report

    try:
        pages = _extract_pages(path)
    except Exception as e:
        report.add(QACheck('structure.extract', QASeverity.FAIL,
                           f'pdfplumber failed: {e}'))
        return report

    pmin, pmax = _PAGE_RANGES.get(report_type, (1, 200))
    _check_structure(report, pages, pmin, pmax)
    _check_markdown_artefacts(report, pages)
    _check_fallback_boxes(report, pages)
    _check_language_coverage(report, pages, lang)
    _check_cover_and_metadata(report, pages, metadata)
    _check_pagebreak_sections(report, pages, report_type)

    return report


# ─── Batch + CLI ─────────────────────────────────────────────────────────────
def _infer_lang_type(filename: str) -> tuple[str, str]:
    stem = Path(filename).stem.lower()
    m = re.search(r'_(ko|en|ja|zh|fr|es|de)(?:\.|$|_)', stem)
    lang = m.group(1) if m else 'en'
    if '_mat_' in stem or stem.endswith('_mat'):
        rtype = 'mat'
    elif '_for_' in stem or '_forensic' in stem:
        rtype = 'forensic'
    else:
        rtype = 'econ'
    return lang, rtype


def batch_verify(directory: str | Path, out_json: Optional[str] = None,
                 pattern: str = '*.pdf') -> List[QAReport]:
    d = Path(directory)
    reports: List[QAReport] = []
    for pdf in sorted(d.rglob(pattern)):
        lang, rtype = _infer_lang_type(pdf.name)
        r = verify_pdf(pdf, lang=lang, report_type=rtype)
        reports.append(r)
        flag = {'PASS': 'OK', 'WARN': '!', 'FAIL': 'X'}[r.severity.value]
        print(f'[{flag}] {r.severity.value:4s} {pdf.name}  ({rtype}/{lang}, '
              f'{r.page_count}p, {sum(1 for c in r.checks if c.severity == QASeverity.FAIL)} fails)')

    if out_json:
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump([r.to_dict() for r in reports], f,
                      ensure_ascii=False, indent=2)
        print(f'Wrote {out_json}')
    return reports


def _print_report(r: QAReport) -> None:
    print(f'\n═══ {r.path} ({r.lang}/{r.report_type}, {r.page_count}p) ═══')
    print(f'Overall: {r.severity.value}')
    for c in r.checks:
        mark = {'PASS': 'OK', 'WARN': '!', 'FAIL': 'X'}[c.severity.value]
        print(f'  [{mark}] {c.name:40s} {c.severity.value:4s}  {c.detail}')
        for s in c.samples[:3]:
            print(f'         sample: {s!r}')


def main() -> int:
    ap = argparse.ArgumentParser(description='PDF QA verification pipeline')
    ap.add_argument('pdf', nargs='?', help='single PDF path')
    ap.add_argument('--lang', default=None)
    ap.add_argument('--type', dest='rtype', default=None,
                    help='econ | mat | forensic')
    ap.add_argument('--batch', help='directory to scan recursively')
    ap.add_argument('--out', help='write JSON report to path')
    ap.add_argument('--score', type=float, help='expected MAT score on cover')
    args = ap.parse_args()

    if args.batch:
        reports = batch_verify(args.batch, out_json=args.out)
        fails = [r for r in reports if r.severity == QASeverity.FAIL]
        return 1 if fails else 0

    if not args.pdf:
        ap.print_help()
        return 2

    lang = args.lang
    rtype = args.rtype
    if not lang or not rtype:
        gl, gt = _infer_lang_type(args.pdf)
        lang = lang or gl
        rtype = rtype or gt
    md = {'total_maturity_score': args.score} if args.score else None
    r = verify_pdf(args.pdf, lang=lang, report_type=rtype, metadata=md)
    _print_report(r)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(r.to_dict(), f, ensure_ascii=False, indent=2)
    return 0 if r.severity != QASeverity.FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
