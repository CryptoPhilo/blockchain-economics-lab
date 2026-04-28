import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen_pdf_econ import generate_pdf_econ
from gen_pdf_mat import generate_pdf_mat


class PdfProjectNameFallbackTests(unittest.TestCase):
    def test_generate_pdf_econ_falls_back_when_project_name_is_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = tmp_path / 'sample_econ_v1_en.md'
            pdf_path = tmp_path / 'sample_econ_v1_en.pdf'
            md_path.write_text(
                '# Intro\n\n'
                '## Executive Summary\n\n'
                'Body copy.\n\n',
                encoding='utf-8',
            )

            out_path = generate_pdf_econ(
                str(md_path),
                metadata={
                    'project_name': None,
                    'slug': 'sample-slug',
                    'version': 1,
                    'overall_rating': 'B',
                },
                lang='en',
                output_path=str(pdf_path),
            )

            self.assertEqual(out_path, str(pdf_path))
            self.assertTrue(pdf_path.exists())

    def test_generate_pdf_mat_falls_back_when_project_name_is_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = tmp_path / 'sample_mat_v1_en.md'
            pdf_path = tmp_path / 'sample_mat_v1_en.pdf'
            md_path.write_text(
                '# Intro\n\n'
                '## Final Assessment\n\n'
                'Body copy.\n\n',
                encoding='utf-8',
            )

            out_path = generate_pdf_mat(
                str(md_path),
                metadata={
                    'project_name': None,
                    'slug': 'sample-slug',
                    'version': 1,
                    'total_maturity_score': 75.0,
                    'maturity_stage': 'growing',
                    'charts_data': {},
                },
                lang='en',
                output_path=str(pdf_path),
            )

            self.assertEqual(out_path, str(pdf_path))
            self.assertTrue(pdf_path.exists())


if __name__ == '__main__':
    unittest.main()
