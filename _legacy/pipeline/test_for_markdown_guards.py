import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gen_pdf_for
import qa_verify_md


TESTDATA_DIR = Path(__file__).resolve().parent / 'testdata' / 'for_header_loss'
OUTPUT_DIR = Path(__file__).resolve().parent / 'output'
SOURCE_KO = TESTDATA_DIR / 'source_ko.md'
COLLAPSED_JA = TESTDATA_DIR / 'collapsed_ja.md'
ORDINARY_NUMBERED_LIST_KO = TESTDATA_DIR / 'ordinary_numbered_list_ko.md'
REAL_FAIL_CASES = [
    OUTPUT_DIR / 'req-포렌식-분석-보고서_for_v1_ko.md',
    OUTPUT_DIR / 'zro-포렌식-분석-보고서_for_v1_ko.md',
    OUTPUT_DIR / 'aave-포렌식-분석-보고서_for_v1_ko.md',
]
REAL_STABLE_CASE = OUTPUT_DIR / 'stable-포렌식-분석-보고서_for_v1_ko.md'


def _check(report, name):
    for item in report.checks:
        if item.name == name:
            return item
    raise AssertionError(f'missing check: {name}')


class ForMarkdownGuardTests(unittest.TestCase):
    def test_detect_true_collapse_with_real_operational_samples(self):
        for path in REAL_FAIL_CASES:
            with self.subTest(path=path.name):
                self.assertTrue(path.exists(), path)
                report = qa_verify_md.verify_markdown(path, lang='ko', report_type='for')
                self.assertEqual(
                    _check(report, 'md.structure.section_markers').severity,
                    qa_verify_md.QASeverity.WARN,
                )

    def test_real_stable_output_keeps_passing_structure_guard(self):
        self.assertTrue(REAL_STABLE_CASE.exists(), REAL_STABLE_CASE)
        report = qa_verify_md.verify_markdown(REAL_STABLE_CASE, lang='ko', report_type='for')

        self.assertEqual(
            _check(report, 'md.structure.section_markers').severity,
            qa_verify_md.QASeverity.PASS,
        )

    def test_detect_true_collapse_warns_without_reference(self):
        report = qa_verify_md.verify_markdown(
            COLLAPSED_JA,
            lang='ja',
            report_type='for',
        )

        self.assertEqual(
            _check(report, 'md.structure.section_markers').severity,
            qa_verify_md.QASeverity.WARN,
        )

    def test_detect_true_collapse_fails_with_reference(self):
        report = qa_verify_md.verify_markdown(
            COLLAPSED_JA,
            lang='ja',
            ko_reference=SOURCE_KO,
            report_type='for',
        )

        self.assertEqual(
            _check(report, 'md.parity.section_structure').severity,
            qa_verify_md.QASeverity.FAIL,
        )

    def test_detect_true_collapse_parser_uses_numbered_heading_fallback(self):
        preamble, sections = gen_pdf_for.parse_markdown(COLLAPSED_JA.read_text(encoding='utf-8'))

        self.assertEqual(preamble, '')
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0][0], '1. Executive Summary')

    def test_parse_markdown_recovers_sections_from_real_failed_output(self):
        text = REAL_FAIL_CASES[0].read_text(encoding='utf-8')
        preamble, sections = gen_pdf_for.parse_markdown(text)

        self.assertTrue(preamble)
        self.assertGreaterEqual(len(sections), 6)
        self.assertEqual(sections[0][0], '1. Executive Summary')

    def test_ignore_ordinary_numbered_list_in_parser(self):
        preamble, sections = gen_pdf_for.parse_markdown(
            ORDINARY_NUMBERED_LIST_KO.read_text(encoding='utf-8')
        )

        self.assertTrue(preamble)
        self.assertEqual(sections, [])

    def test_ignore_ordinary_numbered_list_in_structure_qa(self):
        report = qa_verify_md.verify_markdown(
            ORDINARY_NUMBERED_LIST_KO,
            lang='ko',
            report_type='for',
        )

        self.assertEqual(
            _check(report, 'md.structure.section_markers').severity,
            qa_verify_md.QASeverity.PASS,
        )

    def test_generate_pdf_for_raises_on_unparseable_structure(self):
        bad_md = """포렌식 보고서 초안

본문은 충분히 길지만 섹션 헤더가 전혀 없습니다.
""" * 12
        metadata = {
            'project_name': 'Test Project',
            'token_symbol': 'TEST',
            'slug': 'test-project',
            'version': 1,
            'risk_level': 'warning',
            'trigger_reason': 'Test Trigger',
            'charts_data': {},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / 'test_for_v1_ko.md'
            meta_path = Path(tmpdir) / 'test_for_v1_meta.json'
            md_path.write_text(bad_md, encoding='utf-8')
            meta_path.write_text(json.dumps(metadata), encoding='utf-8')

            with self.assertRaises(gen_pdf_for.MarkdownStructureError):
                gen_pdf_for.generate_pdf_for(str(md_path), metadata, lang='ko')


if __name__ == '__main__':
    unittest.main()
