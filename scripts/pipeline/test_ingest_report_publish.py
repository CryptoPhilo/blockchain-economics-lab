import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ingest_report


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table_name, client):
        self.table_name = table_name
        self.client = client
        self.filters = []
        self.operation = "select"
        self.payload = None
        self.limit_count = None

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def ilike(self, field, pattern):
        self.filters.append((field, "__ilike__", pattern))
        return self

    def in_(self, field, values):
        self.filters.append((field, "__in__", tuple(values)))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def upsert(self, payload, **_kwargs):
        self.operation = "upsert"
        self.payload = payload
        return self

    def execute(self):
        result = self.client.execute(self.table_name, self.operation, self.filters, self.payload)
        if self.limit_count is not None and result.data is not None:
            result.data = result.data[:self.limit_count]
        return result


class FakeSupabase:
    def __init__(self, tables):
        self.tables = {name: [dict(row) for row in rows] for name, rows in tables.items()}

    def table(self, name):
        self.tables.setdefault(name, [])
        return FakeQuery(name, self)

    def execute(self, table_name, operation, filters, payload):
        rows = self.tables.setdefault(table_name, [])

        if operation == "select":
            matched = [dict(row) for row in rows if self._matches(row, filters)]
            return FakeResult(matched)

        if operation == "update":
            updated = []
            for row in rows:
                if self._matches(row, filters):
                    row.update(payload)
                    updated.append(dict(row))
            return FakeResult(updated)

        if operation == "insert":
            row = dict(payload)
            row.setdefault("id", f"{table_name}-{len(rows) + 1}")
            rows.append(row)
            return FakeResult([dict(row)])

        if operation == "upsert":
            if table_name == "project_reports":
                for row in rows:
                    if (
                        row.get("project_id") == payload.get("project_id")
                        and row.get("report_type") == payload.get("report_type")
                        and row.get("version") == payload.get("version")
                        and row.get("language") == payload.get("language")
                    ):
                        row.update(payload)
                        return FakeResult([dict(row)])
            row = dict(payload)
            row.setdefault("id", f"{table_name}-{len(rows) + 1}")
            rows.append(row)
            return FakeResult([dict(row)])

        raise AssertionError(f"Unsupported operation: {operation}")

    @staticmethod
    def _matches(row, filters):
        for filter_item in filters:
            if len(filter_item) == 2:
                field, value = filter_item
                if row.get(field) != value:
                    return False
                continue
            field, op, value = filter_item
            if op == "__in__":
                if row.get(field) not in value:
                    return False
                continue
            if op == "__ilike__":
                cell = row.get(field)
                if cell is None:
                    return False
                pattern = value.strip("%").lower()
                if pattern not in str(cell).lower():
                    return False
                continue
            raise AssertionError(f"Unsupported filter op: {op}")
        return True


class PublishSupabaseContractTests(unittest.TestCase):
    def test_publish_restores_forensic_language_rows_and_trigger_updates(self):
        sb = FakeSupabase(
            {
                "project_reports": [
                    {
                        "id": "report-ko",
                        "project_id": "project-1",
                        "report_type": "forensic",
                        "version": 1,
                        "language": "ko",
                        "status": "published",
                        "published_at": "2026-04-20T00:00:00+00:00",
                    }
                ],
                "forensic_triggers": [
                    {
                        "id": "trigger-1",
                        "project_id": "project-1",
                        "report_id": None,
                        "status": "processing",
                    }
                ],
                "tracked_projects": [{"id": "project-1", "slug": "layerzero"}],
            }
        )

        with patch.object(ingest_report, "_get_supabase_client", return_value=sb):
            with patch.object(
                ingest_report,
                "_resolve_project_slug",
                return_value=("project-1", "layerzero", "LayerZero", "ZRO"),
            ):
                ingest_report._publish_supabase(
                    slug="zro",
                    report_type="for",
                    version=1,
                    gdrive_urls={"ko": "https://drive/ko.pdf", "en": "https://drive/en.pdf"},
                    card_db={"title_ko": "새 제목"},
                    db_report_type="forensic",
                )

        self.assertEqual(len(sb.tables["project_reports"]), 2)
        ko_report = next(row for row in sb.tables["project_reports"] if row["language"] == "ko")
        en_report = next(row for row in sb.tables["project_reports"] if row["language"] == "en")
        self.assertEqual(ko_report["published_at"], "2026-04-20T00:00:00+00:00")
        self.assertEqual(ko_report["title_ko"], "새 제목")
        self.assertEqual(ko_report["gdrive_url"], "https://drive/ko.pdf")
        self.assertEqual(en_report["gdrive_url"], "https://drive/en.pdf")
        self.assertEqual(en_report["translation_status"]["en"], "published")
        self.assertEqual(sb.tables["forensic_triggers"][0]["status"], "published")
        self.assertIsNotNone(sb.tables["tracked_projects"][0]["last_forensic_report_at"])

    def test_publish_updates_tracked_project_timestamp_via_canonical_slug(self):
        sb = FakeSupabase(
            {
                "project_reports": [],
                "forensic_triggers": [],
                "tracked_projects": [{"id": "project-1", "slug": "layerzero"}],
            }
        )

        with patch.object(ingest_report, "_get_supabase_client", return_value=sb):
            with patch.object(
                ingest_report,
                "_resolve_project_slug",
                return_value=("project-1", "layerzero", "LayerZero", "ZRO"),
            ):
                ingest_report._publish_supabase(
                    slug="zro",
                    report_type="for",
                    version=1,
                    gdrive_urls={"en": "https://drive/en.pdf"},
                    db_report_type="forensic",
                )

        self.assertIsNotNone(sb.tables["tracked_projects"][0]["last_forensic_report_at"])


class ProcessReportIntegrationTests(unittest.TestCase):
    def test_process_report_for_promotes_trigger_and_publishes_per_language_rows(self):
        sb = FakeSupabase(
            {
                "project_reports": [
                    {
                        "id": "report-ko",
                        "project_id": "project-1",
                        "report_type": "forensic",
                        "version": 1,
                        "language": "ko",
                        "status": "coming_soon",
                    }
                ],
                "forensic_triggers": [
                    {
                        "id": "trigger-1",
                        "project_id": "project-1",
                        "report_id": "report-ko",
                        "status": "processing",
                    }
                ],
                "tracked_projects": [{"id": "project-1", "slug": "layerzero"}],
            }
        )
        file_info = {
            "file_id": "file-1",
            "name": "zro_for_v1.md",
            "slug": "layerzero",
            "project_name": "LayerZero",
            "symbol": "ZRO",
        }

        def fake_translate(md_path, target_lang, output_dir, backend, strict=False):
            self.assertTrue(strict)
            out_path = Path(output_dir) / f"layerzero_for_v1_{target_lang}.md"
            out_path.write_text(f"# {target_lang}", encoding="utf-8")
            return str(out_path), {"word_count_target": 10, "google_request_count": 2}

        def fake_generate_pdf(md_path, meta, lang, output_path):
            Path(output_path).write_text(f"pdf:{lang}", encoding="utf-8")

        class FakeGDriveStorage:
            def ensure_folder_path(self, slug, report_type):
                return f"{slug}/{report_type}"

            def upload_file(self, pdf_path, folder_id=None):
                pdf_name = Path(pdf_path).name
                return {
                    "id": pdf_name,
                    "webViewLink": f"https://drive.example/{pdf_name}",
                }

        qa_result = SimpleNamespace(
            checks=[],
            page_count=1,
            severity=SimpleNamespace(value="pass"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(ingest_report, "OUTPUT_DIR", tmpdir):
                with patch.object(ingest_report, "_get_drive_service", return_value=object()):
                    with patch.object(
                        ingest_report,
                        "download_markdown_text",
                        return_value="# LayerZero report",
                    ):
                        with patch.object(ingest_report, "translate_md_file", side_effect=fake_translate):
                            with patch.object(ingest_report, "_load_pdf_generator", return_value=fake_generate_pdf):
                                with patch.object(ingest_report, "verify_markdown", return_value=qa_result):
                                    with patch.object(ingest_report, "verify_pdf", return_value=qa_result):
                                        with patch.object(ingest_report, "_load_card_generator", return_value=None):
                                            with patch.object(ingest_report, "GDriveStorage", return_value=FakeGDriveStorage()):
                                                with patch.object(ingest_report, "_get_supabase_client", return_value=sb):
                                                    with patch.object(
                                                        ingest_report,
                                                        "_resolve_project_slug",
                                                        return_value=("project-1", "layerzero", "LayerZero", "ZRO"),
                                                    ):
                                                        result = ingest_report.process_report("for", file_info)

            self.assertEqual(result["status"], "published")
            self.assertEqual(result["google_request_count_total"], 2)
        self.assertEqual(len(sb.tables["project_reports"]), 2)
        published_rows = [
            row for row in sb.tables["project_reports"]
            if row["project_id"] == "project-1" and row["report_type"] == "forensic"
        ]
        self.assertEqual(len(published_rows), 2)
        self.assertTrue(all(row["status"] == "published" for row in published_rows))
        self.assertEqual(sb.tables["forensic_triggers"][0]["status"], "published")

    def test_process_report_blocks_publish_when_a_language_fails_translation(self):
        sb = FakeSupabase(
            {
                "project_reports": [
                    {
                        "id": "report-ko",
                        "project_id": "project-1",
                        "report_type": "forensic",
                        "version": 1,
                        "language": "ko",
                        "status": "coming_soon",
                    }
                ],
                "forensic_triggers": [
                    {
                        "id": "trigger-1",
                        "project_id": "project-1",
                        "report_id": "report-ko",
                        "status": "processing",
                    }
                ],
                "tracked_projects": [{"id": "project-1", "slug": "layerzero"}],
            }
        )
        file_info = {
            "file_id": "file-1",
            "name": "zro_for_v1.md",
            "slug": "layerzero",
            "project_name": "LayerZero",
            "symbol": "ZRO",
        }

        def fake_translate(md_path, target_lang, output_dir, backend, strict=False):
            self.assertTrue(strict)
            if target_lang == "en":
                raise RuntimeError("google throttled")
            out_path = Path(output_dir) / f"layerzero_for_v1_{target_lang}.md"
            out_path.write_text(f"# {target_lang}", encoding="utf-8")
            return str(out_path), {"word_count_target": 10}

        def fake_generate_pdf(md_path, meta, lang, output_path):
            Path(output_path).write_text(f"pdf:{lang}", encoding="utf-8")

        class FakeGDriveStorage:
            def __init__(self):
                self.uploaded = []

            def ensure_folder_path(self, slug, report_type):
                return f"{slug}/{report_type}"

            def upload_file(self, pdf_path, folder_id=None):
                self.uploaded.append((pdf_path, folder_id))
                return {
                    "id": Path(pdf_path).name,
                    "webViewLink": f"https://drive.example/{Path(pdf_path).name}",
                }

        qa_result = SimpleNamespace(
            checks=[],
            page_count=1,
            severity=SimpleNamespace(value="pass"),
        )
        fake_gdrive = FakeGDriveStorage()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(ingest_report, "OUTPUT_DIR", tmpdir):
                with patch.object(ingest_report, "_get_drive_service", return_value=object()):
                    with patch.object(
                        ingest_report,
                        "download_markdown_text",
                        return_value="# LayerZero report",
                    ):
                        with patch.object(ingest_report, "translate_md_file", side_effect=fake_translate):
                            with patch.object(ingest_report, "_load_pdf_generator", return_value=fake_generate_pdf):
                                with patch.object(ingest_report, "verify_markdown", return_value=qa_result):
                                    with patch.object(ingest_report, "verify_pdf", return_value=qa_result):
                                        with patch.object(ingest_report, "_load_card_generator", return_value=None):
                                            with patch.object(ingest_report, "GDriveStorage", return_value=fake_gdrive):
                                                with patch.object(ingest_report, "_get_supabase_client", return_value=sb):
                                                    with patch.object(
                                                        ingest_report,
                                                        "_resolve_project_slug",
                                                        return_value=("project-1", "layerzero", "LayerZero", "ZRO"),
                                                    ):
                                                        result = ingest_report.process_report("for", file_info)

        self.assertEqual(result["status"], ingest_report.RETRIABLE_PROCESSING_STATUS)
        self.assertIn("en", result["missing_publish_langs"])
        self.assertIn("en", result["translation_failed_langs"])
        self.assertEqual(result["uploaded_count"], 0)
        self.assertEqual(fake_gdrive.uploaded, [])
        report_rows = [
            row for row in sb.tables["project_reports"]
            if row["project_id"] == "project-1" and row["report_type"] == "forensic"
        ]
        self.assertEqual(len(report_rows), 1)
        self.assertEqual(report_rows[0]["status"], "coming_soon")
        self.assertEqual(sb.tables["forensic_triggers"][0]["status"], "processing")


class MainExitCodeTests(unittest.TestCase):
    def test_main_returns_nonzero_when_processing_fails(self):
        with patch.object(ingest_report, "scan_drafts", return_value=[{
            "file_id": "file-1",
            "name": "broken_for_v1.md",
            "slug": "broken",
            "size": 1,
        }]):
            with patch.object(ingest_report, "PipelineState", side_effect=RuntimeError("no state")):
                with patch.object(
                    ingest_report,
                    "process_report",
                    return_value={"status": ingest_report.RETRIABLE_PROCESSING_STATUS},
                ):
                    with patch.object(sys, "argv", ["ingest_report.py", "--type", "for"]):
                        rc = ingest_report.main()

        self.assertEqual(rc, 1)

    def test_scan_drafts_increments_retry_count_for_retriable_runs(self):
        files = [
            {
                "id": "file-zro",
                "name": "zro_for_v1.md",
                "size": "123",
                "modifiedTime": "2026-04-23T07:20:34Z",
            }
        ]
        existing_run = {
            "status": ingest_report.RETRIABLE_PROCESSING_STATUS,
            "retry_count": 2,
        }

        with patch.dict(ingest_report.os.environ, {"GDRIVE_ROOT_FOLDER_ID": "root"}, clear=False):
            with patch.object(ingest_report, "_get_drive_service", return_value=object()):
                with patch.object(ingest_report, "ensure_drafts_type_folder", return_value="for-folder"):
                    with patch.object(ingest_report, "scan_markdown_drafts", return_value=files):
                        with patch.object(ingest_report, "_get_supabase_client", return_value=object()):
                            with patch.object(
                                ingest_report,
                                "_resolve_project_slug",
                                return_value=("project-1", "layerzero", "LayerZero", "ZRO"),
                            ):
                                state = unittest.mock.Mock()
                                state.should_process.return_value = (True, existing_run)
                                result = ingest_report.scan_drafts("for", pipeline_state=state)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["_retry_count"], 3)

    def test_qa_strict_accepts_true_string(self):
        with patch.dict(ingest_report.os.environ, {"QA_STRICT": "true"}, clear=False):
            self.assertTrue(ingest_report._is_qa_strict_enabled())

    def test_required_publish_languages_defaults_to_ko_and_en(self):
        with patch.dict(ingest_report.os.environ, {}, clear=False):
            self.assertEqual(ingest_report._required_publish_languages(), ["ko", "en"])

    def test_main_writes_unique_summary_path_with_seconds_precision(self):
        summary_dir = Path(ingest_report.__file__).resolve().parent / "output"
        before = {p.name for p in summary_dir.glob("ingest_for_*.json")}

        with tempfile.TemporaryDirectory() as tmpdir:
            file_info = {
                "file_id": "file-1",
                "name": "ok_for_v1.md",
                "slug": "layerzero",
                "size": 1,
                "_retry_count": 0,
            }
            state = unittest.mock.Mock()
            state.start_run.return_value = {"id": "run-1"}

            with patch.object(ingest_report, "OUTPUT_DIR", tmpdir):
                with patch.object(ingest_report, "scan_drafts", return_value=[file_info]):
                    with patch.object(ingest_report, "PipelineState", return_value=state):
                        with patch.object(ingest_report, "process_report", return_value={"status": "published"}):
                            with patch.object(sys, "argv", ["ingest_report.py", "--type", "for"]):
                                rc = ingest_report.main()

        self.assertEqual(rc, 0)
        after = {p.name for p in summary_dir.glob("ingest_for_*.json")}
        new_files = sorted(after - before)
        self.assertEqual(len(new_files), 1)
        self.assertRegex(new_files[0], r"^ingest_for_\d{8}_\d{6}_\d{6}\.json$")
        (summary_dir / new_files[0]).unlink()


class KoreanSlugResolutionTests(unittest.TestCase):
    """Regression tests for BCE-1048: Korean slug → canonical English slug."""

    def test_resolve_korean_prefix_slug_matches_canonical_project(self):
        sb = FakeSupabase(
            {
                "tracked_projects": [
                    {"id": "project-cardano", "slug": "cardano",
                     "name": "Cardano", "symbol": "ADA"},
                ],
            }
        )

        result = ingest_report._resolve_project_slug(
            sb, "카르다노-프로젝트-진행률-평가-보고서"
        )

        self.assertEqual(
            result,
            ("project-cardano", "cardano", "Cardano", "ADA"),
        )

    def test_resolve_bare_korean_name_matches_canonical_project(self):
        sb = FakeSupabase(
            {
                "tracked_projects": [
                    {"id": "project-bitcoin", "slug": "bitcoin",
                     "name": "Bitcoin", "symbol": "BTC"},
                ],
            }
        )

        result = ingest_report._resolve_project_slug(sb, "비트코인")

        self.assertEqual(
            result,
            ("project-bitcoin", "bitcoin", "Bitcoin", "BTC"),
        )

    def test_resolve_multiword_korean_prefix_prefers_longer_match(self):
        sb = FakeSupabase(
            {
                "tracked_projects": [
                    {"id": "project-bch", "slug": "bitcoin-cash",
                     "name": "Bitcoin Cash", "symbol": "BCH"},
                    {"id": "project-btc", "slug": "bitcoin",
                     "name": "Bitcoin", "symbol": "BTC"},
                ],
            }
        )

        result = ingest_report._resolve_project_slug(sb, "비트코인-캐시-보고서")

        # Longer "비트코인-캐시" must beat "비트코인" prefix.
        self.assertEqual(result[1], "bitcoin-cash")

    def test_resolve_english_slug_unchanged(self):
        sb = FakeSupabase(
            {
                "tracked_projects": [
                    {"id": "project-cardano", "slug": "cardano",
                     "name": "Cardano", "symbol": "ADA"},
                ],
            }
        )

        result = ingest_report._resolve_project_slug(sb, "cardano")

        self.assertEqual(
            result,
            ("project-cardano", "cardano", "Cardano", "ADA"),
        )

    def test_resolve_unknown_korean_slug_returns_none(self):
        sb = FakeSupabase({"tracked_projects": []})

        result = ingest_report._resolve_project_slug(sb, "알수없는-한국어-슬러그")

        self.assertEqual(result, (None, None, None, None))

    def test_korean_slug_to_canonical_helper(self):
        self.assertEqual(
            ingest_report._korean_slug_to_canonical(
                "카르다노-프로젝트-진행률-평가-보고서"
            ),
            "cardano",
        )
        self.assertEqual(
            ingest_report._korean_slug_to_canonical("비트코인-캐시"),
            "bitcoin-cash",
        )
        self.assertIsNone(
            ingest_report._korean_slug_to_canonical("cardano")
        )
        self.assertIsNone(
            ingest_report._korean_slug_to_canonical("")
        )

    def test_publish_supabase_succeeds_with_korean_slug(self):
        """End-to-end: publish step accepts a Korean slug and writes to DB."""
        sb = FakeSupabase(
            {
                "project_reports": [],
                "tracked_projects": [
                    {"id": "project-cardano", "slug": "cardano",
                     "name": "Cardano", "symbol": "ADA"},
                ],
                "forensic_triggers": [],
            }
        )

        with patch.object(ingest_report, "_get_supabase_client", return_value=sb):
            ingest_report._publish_supabase(
                slug="카르다노-프로젝트-진행률-평가-보고서",
                report_type="mat",
                version=1,
                gdrive_urls={"ko": "https://drive/ko.pdf",
                             "en": "https://drive/en.pdf"},
                db_report_type="maturity",
            )

        self.assertEqual(len(sb.tables["project_reports"]), 2)
        for row in sb.tables["project_reports"]:
            self.assertEqual(row["project_id"], "project-cardano")
            self.assertEqual(row["status"], "published")
        self.assertIsNotNone(
            sb.tables["tracked_projects"][0].get("last_maturity_report_at")
        )


if __name__ == "__main__":
    unittest.main()
