import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name('cmc_market_sync.py')
SPEC = importlib.util.spec_from_file_location('cmc_market_sync', MODULE_PATH)
cmc_market_sync = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(cmc_market_sync)

cmc_to_market_row = cmc_market_sync.cmc_to_market_row
build_slug_map = cmc_market_sync.build_slug_map
CMCClient = cmc_market_sync.CMCClient
mode_top500 = cmc_market_sync.mode_top500
mode_tracked = cmc_market_sync.mode_tracked


def make_token(rank, slug, symbol=None, token_id=None):
    return {
        'id': token_id or rank,
        'name': slug.title(),
        'symbol': symbol or slug[:4].upper(),
        'slug': slug,
        'cmc_rank': rank,
        'circulating_supply': 1000,
        'total_supply': 2000,
        'quote': {
            'USD': {
                'price': rank,
                'market_cap': 1_000_000 - rank,
                'volume_24h': 10_000,
                'percent_change_24h': 1.2,
                'percent_change_7d': 2.3,
                'percent_change_30d': 3.4,
                'fully_diluted_market_cap': 2_000_000 - rank,
            },
        },
    }


class FakeCMC:
    credits_used = 1

    def __init__(self, tokens):
        self.tokens = tokens

    def get_listings(self, start=1, limit=500):
        return self.tokens

    def get_listings_paginated(self, total_limit=5000):
        return self.tokens


class FakeDB:
    def __init__(self, tracked_projects=None):
        self.rows = []
        self.tracked_projects = tracked_projects or []

    def get_tracked_projects(self):
        return self.tracked_projects

    def upsert_market_data(self, rows):
        self.rows.extend(rows)
        return len(rows)


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            'status': {
                'credit_count': 1,
                'error_code': 0,
            },
            'data': [],
        }


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.params = None

    def get(self, _url, params, timeout):
        self.params = params
        return FakeResponse()


def test_cmc_get_listings_requests_canonical_rank_aux():
    client = CMCClient('test-key')
    fake_session = FakeSession()
    client.session = fake_session

    client.get_listings(start=1, limit=500)

    assert 'cmc_rank' in fake_session.params['aux'].split(',')


def test_cmc_to_market_row_preserves_cmc_rank_and_source():
    row = cmc_to_market_row(make_token(28, 'synthetix', 'SNX'), slug_override='synthetix')

    assert row['slug'] == 'synthetix'
    assert row['cmc_rank'] == 28
    assert row['cmc_symbol'] == 'SNX'
    assert row['cmc_name'] == 'Synthetix'
    assert row['source'] == 'coinmarketcap'


def test_mode_top500_upserts_response_order_as_canonical_rank_1_to_500():
    tokens = [make_token(rank, f'rank-{rank}', f'R{rank}') for rank in range(1, 501)]
    tokens[168] = make_token(169, 'duplicate-rank-a', 'DRA')
    tokens[169] = make_token(169, 'duplicate-rank-b', 'DRB')
    tokens.extend([
        make_token(501, 'rain', 'RAIN'),
        make_token(503, 'htx-dao', 'HTX'),
        make_token(999, 'falcon-usd', 'USDf'),
    ])
    db = FakeDB()

    result = mode_top500(FakeCMC(tokens), db)

    assert result['fetched'] == len(tokens)
    assert result['written'] == 500
    assert [row['cmc_rank'] for row in db.rows] == list(range(1, 501))
    assert db.rows[168]['slug'] == 'duplicate-rank-a'
    assert db.rows[168]['cmc_rank'] == 169
    assert db.rows[169]['slug'] == 'duplicate-rank-b'
    assert db.rows[169]['cmc_rank'] == 170
    assert 'rain' not in {row['slug'] for row in db.rows}
    assert 'htx-dao' not in {row['slug'] for row in db.rows}
    assert 'falcon-usd' not in {row['slug'] for row in db.rows}


def test_build_slug_map_does_not_match_by_symbol_only():
    tracked_projects = [
        {
            'slug': 'irys',
            'name': 'Irys',
            'symbol': 'MEGA',
            'coingecko_id': 'irys',
            'cmc_id': None,
        },
    ]
    tokens = [make_token(120, 'unrelated-top-token', 'MEGA')]

    assert build_slug_map(tracked_projects, tokens) == {}


def test_build_slug_map_matches_numeric_cmc_id_without_symbol_guessing():
    tracked_projects = [
        {
            'slug': 'myx-finance',
            'name': 'MYX Finance',
            'symbol': 'MYX',
            'coingecko_id': None,
            'cmc_id': '36410',
        },
    ]
    tokens = [make_token(530, 'myx-finance', 'MYX', token_id=36410)]

    assert build_slug_map(tracked_projects, tokens) == {'myx-finance': 'myx-finance'}


def test_mode_tracked_writes_project_slug_for_numeric_cmc_id_match():
    tracked_projects = [
        {
            'slug': 'opengradient',
            'name': 'OpenGradient',
            'symbol': 'OPG',
            'coingecko_id': None,
            'cmc_id': '39800',
        },
    ]
    db = FakeDB(tracked_projects)

    result = mode_tracked(FakeCMC([
        make_token(564, 'open-gradient', 'OPG', token_id=39800),
    ]), db)

    assert result['matched'] == 1
    assert result['unmatched'] == 0
    assert db.rows[0]['slug'] == 'opengradient'
    assert db.rows[0]['cmc_rank'] == 564


def test_mode_top500_preserves_cmc_slug_when_tracked_symbol_collides():
    tokens = [make_token(rank, f'rank-{rank}', f'R{rank}') for rank in range(1, 501)]
    tokens[149] = make_token(150, 'unrelated-top-token', 'MEGA')
    db = FakeDB([
        {
            'slug': 'megaeth',
            'name': 'MegaETH',
            'symbol': 'MEGA',
            'coingecko_id': 'megaeth',
            'cmc_id': None,
        },
    ])

    mode_top500(FakeCMC(tokens), db)

    assert db.rows[149]['slug'] == 'unrelated-top-token'
    assert db.rows[149]['cmc_rank'] == 150
    assert 'megaeth' not in {row['slug'] for row in db.rows}
