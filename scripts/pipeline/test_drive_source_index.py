import importlib.util
import sys
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parent / "drive_source_index.py"
    spec = importlib.util.spec_from_file_location("drive_source_index", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.filters = []
        self.action = None
        self.payload = None

    def select(self, payload):
        self.action = "select"
        self.payload = payload
        return self

    def upsert(self, payload, **kwargs):
        self.action = "upsert"
        self.payload = payload
        self.db.operations.append((self.name, "upsert", payload, kwargs))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, _value):
        return self

    def execute(self):
        rows = list(self.db.tables.get(self.name, []))
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        return FakeExecuteResult(rows)


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or {}
        self.operations = []

    def table(self, name):
        return FakeTable(self, name)


class FakeFilesResource:
    def __init__(self, service):
        self.service = service

    def list(self, **kwargs):
        self.service.queries.append(kwargs.get("q"))
        return FakeDriveListRequest({"files": list(self.service.files_payload), "nextPageToken": None})


class FakeDriveService:
    def __init__(self, files_payload=None):
        self.files_payload = files_payload or []
        self.queries = []

    def files(self):
        return FakeFilesResource(self)


class FakeDriveListRequest:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self.data


def test_map_source_file_marks_mat_natural_language_ambiguous():
    module = load_module()
    indexed = module.DriveIndexedFile(
        file_id="file-1",
        folder_scope="active",
        source_root="analysis2",
        report_type="mat",
        folder_id="folder",
        path="analysis2/MAT/Falcon USD maturity report.md",
        name="Falcon USD maturity report.md",
        mime_type="text/markdown",
        modified_time="2026-06-21T00:00:00Z",
        revision_id="rev-1",
        size=10,
        trashed=False,
        web_view_link=None,
    )

    mapping = module.map_source_file(indexed, [
        {"slug": "falcon-usd", "name": "Falcon USD", "symbol": "USDF"},
        {"slug": "falcon-finance", "name": "Falcon Finance", "symbol": "FALCON"},
    ])

    assert mapping.mapping_status == "ambiguous"
    assert mapping.report_type == "mat"
    assert mapping.mapping_evidence["candidates"]


def test_select_index_candidates_reads_safe_extracted_rows_ordered_by_modified_time():
    module = load_module()
    sb = FakeSupabase({
        "analysis_source_map": [
            {"file_id": "old", "revision_id": "rev-old", "report_type": "econ", "project_slug": "solana", "mapping_status": "safe"},
            {"file_id": "new", "revision_id": "rev-new", "report_type": "econ", "project_slug": "solana", "mapping_status": "safe"},
            {"file_id": "amb", "revision_id": "rev-amb", "report_type": "econ", "project_slug": "solana", "mapping_status": "ambiguous"},
        ],
        "drive_file_index": [
            {"file_id": "old", "name": "old.md", "modified_time": "2026-06-20T00:00:00Z"},
            {"file_id": "new", "name": "new.md", "modified_time": "2026-06-21T00:00:00Z"},
        ],
        "drive_file_content_index": [
            {"file_id": "old", "revision_id": "rev-old", "extraction_status": "extracted", "extracted_text_path": "/tmp/old.txt"},
            {"file_id": "new", "revision_id": "rev-new", "extraction_status": "extracted", "extracted_text_path": "/tmp/new.txt"},
        ],
    })

    rows = module.select_index_candidates(sb, report_type="econ", slug="solana", limit=1)

    assert len(rows) == 1
    assert rows[0]["file"]["file_id"] == "new"


def test_select_index_candidates_skips_sources_with_existing_summary_jobs():
    module = load_module()
    sb = FakeSupabase({
        "analysis_source_map": [
            {"file_id": "done", "revision_id": "rev-done", "report_type": "econ", "project_slug": "solana", "mapping_status": "safe"},
            {"file_id": "next", "revision_id": "rev-next", "report_type": "econ", "project_slug": "solana", "mapping_status": "safe"},
        ],
        "drive_file_index": [
            {"file_id": "done", "name": "done.md", "modified_time": "2026-06-22T00:00:00Z"},
            {"file_id": "next", "name": "next.md", "modified_time": "2026-06-21T00:00:00Z"},
        ],
        "drive_file_content_index": [
            {"file_id": "done", "revision_id": "rev-done", "extraction_status": "extracted", "extracted_text_path": "/tmp/done.txt"},
            {"file_id": "next", "revision_id": "rev-next", "extraction_status": "extracted", "extracted_text_path": "/tmp/next.txt"},
        ],
        "report_summary_jobs": [
            {"id": "job-1", "source_identity": "drive:done:rev-done"},
        ],
    })

    rows = module.select_index_candidates(sb, report_type="econ", slug="solana", limit=5)

    assert [row["file"]["file_id"] for row in rows] == ["next"]


def test_sync_index_dry_run_reports_no_upserts(monkeypatch, tmp_path):
    module = load_module()
    indexed = module.DriveIndexedFile(
        file_id="file-1",
        folder_scope="active",
        source_root="analysis2",
        report_type="econ",
        folder_id="folder",
        path="analysis2/ECON/solana_econ_v1_ko.md",
        name="solana_econ_v1_ko.md",
        mime_type="text/markdown",
        modified_time="2026-06-21T00:00:00Z",
        revision_id="rev-1",
        size=10,
        trashed=False,
        web_view_link=None,
    )
    monkeypatch.setattr(module, "list_drive_source_files", lambda *args, **kwargs: [indexed])
    monkeypatch.setattr(module, "extract_content", lambda *args, **kwargs: module.ContentIndex("file-1", "rev-1", "hash", "extracted", None, str(tmp_path / "x.txt")))
    monkeypatch.setattr(module, "_folder_keys_for_scope", lambda *args, **kwargs: [("active", "analysis2", "folder")])
    sb = FakeSupabase({"tracked_projects": [{"slug": "solana", "name": "Solana", "symbol": "SOL"}]})

    metrics = module.sync_index(sb, object(), report_type="econ", drive_root_scope="active", slug="solana", dry_run=True)

    assert metrics["seen"] == 1
    assert metrics["metadata_upserts"] == 0
    assert metrics["safe"] == 1
    assert sb.operations == []


def test_sync_index_reuses_unchanged_revision_without_extracting(monkeypatch, tmp_path):
    module = load_module()
    indexed = module.DriveIndexedFile(
        file_id="file-1",
        folder_scope="active",
        source_root="analysis2",
        report_type="econ",
        folder_id="folder",
        path="analysis2/ECON/solana_econ_v1_ko.md",
        name="solana_econ_v1_ko.md",
        mime_type="text/markdown",
        modified_time="2026-06-21T00:00:00Z",
        revision_id="rev-1",
        size=10,
        trashed=False,
        web_view_link=None,
    )
    text_path = tmp_path / "source.txt"
    text_path.write_text("# cached\n", encoding="utf-8")
    monkeypatch.setattr(module, "list_drive_source_files", lambda *args, **kwargs: [indexed])
    monkeypatch.setattr(module, "_folder_keys_for_scope", lambda *args, **kwargs: [("active", "analysis2", "folder")])

    def fail_extract(*args, **kwargs):
        raise AssertionError("unchanged revision should not be re-extracted")

    monkeypatch.setattr(module, "extract_content", fail_extract)
    sb = FakeSupabase({
        "tracked_projects": [{"slug": "solana", "name": "Solana", "symbol": "SOL"}],
        "drive_file_index": [{"file_id": "file-1", "revision_id": "rev-1"}],
        "drive_file_content_index": [
            {
                "file_id": "file-1",
                "revision_id": "rev-1",
                "extraction_status": "extracted",
                "text_sha256": "hash",
                "extracted_text_path": str(text_path),
            }
        ],
        "analysis_source_map": [
            {
                "file_id": "file-1",
                "revision_id": "rev-1",
                "report_type": "econ",
                "project_slug": "solana",
                "mapping_status": "safe",
            }
        ],
    })

    metrics = module.sync_index(sb, object(), report_type="econ", drive_root_scope="active", slug="solana", dry_run=False)

    assert metrics["seen"] == 1
    assert metrics["changed"] == 0
    assert metrics["unchanged"] == 1
    assert metrics["content_cached"] == 1
    assert metrics["metadata_upserts"] == 0
    assert metrics["no_op"] is True
    assert [op[0] for op in sb.operations] == ["drive_source_sync_state"]


def test_sync_index_persists_sync_state_after_successful_write(monkeypatch, tmp_path):
    module = load_module()
    indexed = module.DriveIndexedFile(
        file_id="file-1",
        folder_scope="active",
        source_root="analysis2",
        report_type="econ",
        folder_id="folder",
        path="analysis2/ECON/solana_econ_v1_ko.md",
        name="solana_econ_v1_ko.md",
        mime_type="text/markdown",
        modified_time="2026-06-21T00:00:00Z",
        revision_id="rev-1",
        size=10,
        trashed=False,
        web_view_link=None,
    )
    monkeypatch.setattr(module, "list_drive_source_files", lambda *args, **kwargs: [indexed])
    monkeypatch.setattr(module, "_folder_keys_for_scope", lambda *args, **kwargs: [("active", "analysis2", "folder")])
    monkeypatch.setattr(module, "extract_content", lambda *args, **kwargs: module.ContentIndex("file-1", "rev-1", "hash", "extracted", None, str(tmp_path / "x.txt")))
    sb = FakeSupabase({"tracked_projects": [{"slug": "solana", "name": "Solana", "symbol": "SOL"}]})

    metrics = module.sync_index(sb, object(), report_type="econ", drive_root_scope="active", slug="solana", dry_run=False)

    sync_ops = [op for op in sb.operations if op[0] == "drive_source_sync_state"]
    assert metrics["sync_state_upserts"] == 1
    assert len(sync_ops) == 1
    payload = sync_ops[0][2]
    assert payload["source_root"] == "analysis2"
    assert payload["folder_scope"] == "active"
    assert payload["report_type"] == "econ"
    assert payload["folder_id"] == "folder"
    assert payload["last_seen_count"] == 1
    assert payload["last_changed_count"] == 1
    assert payload["last_sync_at"]
    assert payload["last_success_at"]


def test_second_default_run_uses_sync_state_checkpoint_without_folder_wide_query(monkeypatch):
    module = load_module()
    service = FakeDriveService([
        {
            "id": "file-2",
            "name": "solana_econ_v2_ko.md",
            "mimeType": "text/markdown",
            "modifiedTime": "2026-06-21T01:00:00Z",
            "headRevisionId": "rev-2",
            "size": "10",
            "trashed": False,
        }
    ])
    monkeypatch.setattr(module, "_folder_keys_for_scope", lambda *args, **kwargs: [("active", "analysis2", "folder")])
    sb = FakeSupabase({
        "tracked_projects": [{"slug": "solana", "name": "Solana", "symbol": "SOL"}],
        "drive_source_sync_state": [
            {
                "source_root": "analysis2",
                "folder_scope": "active",
                "report_type": "econ",
                "folder_id": "folder",
                "last_success_at": "2026-06-21T00:00:00Z",
            }
        ],
    })

    metrics = module.sync_index(sb, service, report_type="econ", drive_root_scope="active", slug="solana", dry_run=True)

    assert metrics["sync_state_used"] is True
    assert len(service.queries) == 1
    assert "modifiedTime > '2026-06-21T00:00:00Z'" in service.queries[0]
    assert service.queries[0] != "'folder' in parents and trashed = false and (name contains '.md' or name contains '.pdf')"


def test_full_rescan_bypasses_sync_state_checkpoint(monkeypatch):
    module = load_module()
    service = FakeDriveService([])
    monkeypatch.setattr(module, "_folder_keys_for_scope", lambda *args, **kwargs: [("active", "analysis2", "folder")])
    sb = FakeSupabase({
        "drive_source_sync_state": [
            {
                "source_root": "analysis2",
                "folder_scope": "active",
                "report_type": "econ",
                "folder_id": "folder",
                "last_success_at": "2026-06-21T00:00:00Z",
            }
        ],
    })

    metrics = module.sync_index(sb, service, report_type="econ", drive_root_scope="active", slug=None, dry_run=True, full_rescan=True)

    assert metrics["sync_state_used"] is False
    assert len(service.queries) == 1
    assert "modifiedTime >" not in service.queries[0]
