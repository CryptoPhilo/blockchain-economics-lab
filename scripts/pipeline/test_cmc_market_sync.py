import importlib.util
from pathlib import Path


def load_sync():
    path = Path(__file__).resolve().parent / "cmc_market_sync.py"
    spec = importlib.util.spec_from_file_location("cmc_market_sync", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token(slug, symbol, cmc_id, cmc_rank, market_cap=100):
    return {
        "id": cmc_id,
        "slug": slug,
        "symbol": symbol,
        "cmc_rank": cmc_rank,
        "quote": {
            "USD": {
                "price": 1.25,
                "market_cap": market_cap,
                "volume_24h": 10,
                "percent_change_24h": 2.5,
                "percent_change_7d": 3.5,
                "percent_change_30d": 4.5,
                "fully_diluted_market_cap": market_cap + 10,
            }
        },
    }


class FakeCmc:
    credits_used = 1

    def __init__(self, tokens):
        self.tokens = tokens

    def get_listings(self, start=1, limit=200):
        return self.tokens

    def get_listings_paginated(self, total_limit=5000):
        return self.tokens


class FakeDb:
    def __init__(self, projects=None):
        self.projects = projects or []
        self.rows = []

    def get_tracked_projects(self):
        return self.projects

    def upsert_market_data(self, rows):
        self.rows.extend(rows)
        return len(rows)


def test_market_row_persists_canonical_cmc_rank_and_source():
    sync = load_sync()

    row = sync.cmc_to_market_row(token("bitcoin", "BTC", 1, "1"), slug_override="bitcoin")

    assert row["slug"] == "bitcoin"
    assert row["cmc_rank"] == 1
    assert row["source"] == "coinmarketcap"
    assert row["market_cap"] == 100


def test_slug_map_accepts_slug_and_numeric_cmc_identifiers_without_int_cast():
    sync = load_sync()
    tracked = [
        {"slug": "bitcoin", "symbol": "BTC", "coingecko_id": "bitcoin", "cmc_id": "bitcoin"},
        {"slug": "ethereum", "symbol": "ETH", "coingecko_id": "ethereum", "cmc_id": "1027"},
    ]
    tokens = [
        token("bitcoin", "BTC", 1, 1),
        token("ethereum", "ETH", 1027, 2),
    ]

    slug_map = sync.build_slug_map(tracked, tokens)

    assert slug_map["bitcoin"] == "bitcoin"
    assert slug_map["ethereum"] == "ethereum"


def test_slug_map_does_not_match_ambiguous_symbols():
    sync = load_sync()
    tracked = [
        {"slug": "legacy-a", "symbol": "ABC", "coingecko_id": "legacy-a", "cmc_id": None},
        {"slug": "legacy-b", "symbol": "ABC", "coingecko_id": "legacy-b", "cmc_id": None},
    ]

    slug_map = sync.build_slug_map(tracked, [token("new-abc", "ABC", 999, 99)])

    assert "new-abc" not in slug_map


def test_tracked_mode_matches_slug_cmc_id_and_writes_cmc_rank():
    sync = load_sync()
    db = FakeDb([
        {"slug": "bitcoin", "symbol": "BTC", "coingecko_id": "bitcoin", "cmc_id": "bitcoin"},
    ])
    cmc = FakeCmc([token("bitcoin", "BTC", 1, 1)])

    result = sync.mode_tracked(cmc, db, dry_run=False)

    assert result["matched"] == 1
    assert result["written"] == 1
    assert db.rows[0]["cmc_rank"] == 1


def test_top200_mode_filters_noncanonical_ranks_before_writing():
    sync = load_sync()
    db = FakeDb()
    cmc = FakeCmc([
        token("bitcoin", "BTC", 1, 1),
        token("rank-201", "R201", 201, 201),
        token("missing-rank", "MISS", 999, None),
    ])

    result = sync.mode_top200(cmc, db, dry_run=False)

    assert result["fetched"] == 3
    assert result["written"] == 1
    assert [row["slug"] for row in db.rows] == ["bitcoin"]
