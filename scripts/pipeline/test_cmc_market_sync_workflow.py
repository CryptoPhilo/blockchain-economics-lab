import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name('cmc_market_sync.py')
SPEC = importlib.util.spec_from_file_location('cmc_market_sync', MODULE_PATH)
cmc_market_sync = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(cmc_market_sync)

cmc_to_market_row = cmc_market_sync.cmc_to_market_row
CMCClient = cmc_market_sync.CMCClient
mode_top200 = cmc_market_sync.mode_top200


def make_token(rank, slug, symbol=None):
    return {
        'id': rank,
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

    def get_listings(self, start=1, limit=200):
        return self.tokens


class FakeDB:
    def __init__(self):
        self.rows = []

    def get_tracked_projects(self):
        return []

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

    client.get_listings(start=1, limit=200)

    assert 'cmc_rank' in fake_session.params['aux'].split(',')


def test_cmc_to_market_row_preserves_cmc_rank_and_source():
    row = cmc_to_market_row(make_token(28, 'rain'), slug_override='rain')

    assert row['slug'] == 'rain'
    assert row['cmc_rank'] == 28
    assert row['source'] == 'coinmarketcap'


def test_mode_top200_upserts_only_canonical_cmc_rank_1_to_200():
    tokens = [
        make_token(1, 'bitcoin', 'BTC'),
        make_token(200, 'rank-200', 'R200'),
        make_token(201, 'rain', 'RAIN'),
        make_token(203, 'htx-dao', 'HTX'),
        make_token(999, 'falcon-usd', 'USDf'),
        {**make_token(45, 'bad-rank'), 'cmc_rank': None},
    ]
    db = FakeDB()

    result = mode_top200(FakeCMC(tokens), db)

    assert result['fetched'] == len(tokens)
    assert result['written'] == 2
    assert [row['slug'] for row in db.rows] == ['bitcoin', 'rank-200']
    assert [row['cmc_rank'] for row in db.rows] == [1, 200]
    assert 'rain' not in {row['slug'] for row in db.rows}
    assert 'htx-dao' not in {row['slug'] for row in db.rows}
    assert 'falcon-usd' not in {row['slug'] for row in db.rows}
