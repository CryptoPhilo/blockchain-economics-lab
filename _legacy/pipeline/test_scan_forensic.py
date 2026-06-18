import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scan_forensic


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

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def eq(self, field, value):
        self.filters.append((field, "eq", value))
        return self

    def in_(self, field, values):
        self.filters.append((field, "in", tuple(values)))
        return self

    def gte(self, field, value):
        self.filters.append((field, "gte", value))
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def execute(self):
        return self.client.execute(self.table_name, self.operation, self.filters, self.payload)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = {name: [dict(row) for row in rows] for name, rows in tables.items()}

    def table(self, name):
        self.tables.setdefault(name, [])
        return FakeQuery(name, self)

    def execute(self, table_name, operation, filters, payload):
        rows = self.tables.setdefault(table_name, [])
        if operation == "select":
            return FakeResult([dict(row) for row in rows if self._matches(row, filters)])
        if operation == "insert":
            row = dict(payload)
            row.setdefault("id", f"{table_name}-{len(rows) + 1}")
            rows.append(row)
            return FakeResult([dict(row)])
        if operation == "update":
            updated = []
            for row in rows:
                if self._matches(row, filters):
                    row.update(payload)
                    updated.append(dict(row))
            return FakeResult(updated)
        raise AssertionError(f"Unsupported operation: {operation}")

    @staticmethod
    def _matches(row, filters):
        for field, op, value in filters:
            current = row.get(field)
            if op == "eq" and current != value:
                return False
            if op == "in" and current not in value:
                return False
            if op == "gte":
                if current is None or str(current) < str(value):
                    return False
        return True


def trigger(slug="shiba-inu", symbol="SHIB"):
    return {
        "cmc_id": 5994,
        "name": "Shiba Inu",
        "symbol": symbol,
        "slug": slug,
        "price_usd": 0.00001,
        "price_change_24h": -18.2,
        "market_avg_change_24h": -1.1,
        "relative_deviation": 17.1,
        "volume_24h": 1000000,
        "market_cap": 900000000,
        "cmc_rank": 29,
        "direction": "down",
    }


def test_next_forensic_report_version_uses_existing_max_version():
    sb = FakeSupabase(
        {
            "project_reports": [
                {"project_id": "project-1", "report_type": "forensic", "version": 1},
                {"project_id": "project-1", "report_type": "forensic", "version": "2"},
                {"project_id": "project-1", "report_type": "econ", "version": 9},
                {"project_id": "project-2", "report_type": "forensic", "version": 5},
                {"project_id": "project-1", "report_type": "forensic", "version": "bad"},
            ]
        }
    )

    assert scan_forensic._next_forensic_report_version(sb, "project-1") == 3


def test_register_coming_soon_skips_active_latest_for_report():
    sb = FakeSupabase(
        {
            "tracked_projects": [{"id": "project-1", "slug": "shiba-inu"}],
            "project_reports": [
                {
                    "id": "report-active",
                    "project_id": "project-1",
                    "report_type": "forensic",
                    "status": "in_progress",
                    "is_latest": True,
                }
            ],
            "forensic_triggers": [],
        }
    )

    with patch.object(scan_forensic, "_get_supabase", return_value=sb):
        registered = scan_forensic.register_coming_soon([trigger()])

    assert registered == []
    assert sb.tables["forensic_triggers"] == []


def test_register_coming_soon_creates_next_version_and_links_trigger():
    sb = FakeSupabase(
        {
            "tracked_projects": [{"id": "project-1", "slug": "shiba-inu"}],
            "project_reports": [
                {
                    "id": "report-v1",
                    "project_id": "project-1",
                    "report_type": "forensic",
                    "status": "published",
                    "published_at": "2000-01-01T00:00:00+00:00",
                    "version": 1,
                    "is_latest": False,
                },
                {
                    "id": "report-v2",
                    "project_id": "project-1",
                    "report_type": "forensic",
                    "status": "published",
                    "published_at": "2001-01-01T00:00:00+00:00",
                    "version": 2,
                    "is_latest": False,
                },
            ],
            "forensic_triggers": [],
        }
    )

    with patch.object(scan_forensic, "_get_supabase", return_value=sb):
        registered = scan_forensic.register_coming_soon([trigger()])

    assert len(registered) == 1
    inserted_report = sb.tables["project_reports"][-1]
    inserted_trigger = sb.tables["forensic_triggers"][-1]
    assert inserted_report["version"] == 3
    assert inserted_report["status"] == "coming_soon"
    assert inserted_report["trigger_data"]["trigger_id"] == inserted_trigger["id"]
    assert inserted_report["trigger_data"]["risk_level"] == "elevated"
    assert inserted_report["trigger_data"]["trigger_reasons"]
    assert inserted_trigger["status"] == "notified"
    assert inserted_trigger["report_id"] == inserted_report["id"]
