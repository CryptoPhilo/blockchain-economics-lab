"""
Phase A-2: CoinMarketCap Token List Collector
Fetches the full list of cryptocurrencies from CoinMarketCap,
normalizes the data format to match CoinGecko output for merging.

CoinMarketCap API (Free Basic tier):
  - 10,000 credits/month
  - 30 requests/minute
  - /v1/cryptocurrency/listings/latest: 1 credit per 200 tokens

Usage:
    from collectors.collector_tokenlist_cmc import CollectorTokenListCMC
    ctl = CollectorTokenListCMC(api_key='YOUR_CMC_API_KEY')
    result = ctl.collect()
    # result = {
    #   'tokens': [...],         # All CMC-listed tokens (normalized format)
    #   'total': 9500,
    #   'cmc_exclusive': [...],  # Tokens NOT on CoinGecko
    #   'source': 'coinmarketcap',
    # }
"""

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base_collector import BaseCollector


class CollectorTokenListCMC(BaseCollector):
    """
    Collects the full list of cryptocurrencies from CoinMarketCap.
    Normalizes output format to be compatible with CoinGecko-based pipeline.
    """

    CMC_BASE = 'https://pro-api.coinmarketcap.com/v1'
    SNAPSHOT_DIR = Path(__file__).parent / '.cache' / 'cmc_snapshots'
    BATCH_SIZE = 5000  # CMC max per request

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key or os.environ.get('CMC_API_KEY', '')
        self.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Set CMC-specific headers
        if self.api_key:
            self.session.headers.update({
                'X-CMC_PRO_API_KEY': self.api_key,
                'Accept': 'application/json',
            })

    def collect(self, known_coingecko_symbols: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        Main entry: fetch all CMC-listed tokens, normalize, detect CMC-exclusive tokens.

        Args:
            known_coingecko_symbols: Set of lowercase symbols already known from CoinGecko.
                Used to identify CMC-exclusive projects for discovery.

        Returns:
            Dict with normalized token list and CMC-exclusive tokens.
        """
        print("  [Phase A-2] Collecting token list from CoinMarketCap...")

        if not self.api_key:
            print("  [Phase A-2] WARNING: No CMC_API_KEY set. Skipping CMC collection.")
            return {
                'tokens': [], 'total': 0, 'cmc_exclusive': [],
                'source': 'coinmarketcap', 'error': 'no_api_key',
            }

        # 1. Fetch all CMC listings (paginated)
        all_listings = self._fetch_all_listings()
        if not all_listings:
            print("  [Phase A-2] Failed to fetch CMC listings")
            return {
                'tokens': [], 'total': 0, 'cmc_exclusive': [],
                'source': 'coinmarketcap', 'error': 'fetch_failed',
            }

        # 2. Filter active tokens with volume > 0
        active_tokens = [
            t for t in all_listings
            if t.get('quote', {}).get('USD', {}).get('volume_24h', 0)
            and t.get('quote', {}).get('USD', {}).get('volume_24h', 0) > 0
        ]

        print(f"  [Phase A-2] Total CMC listings: {len(all_listings)}")
        print(f"  [Phase A-2] Active tokens (vol > 0): {len(active_tokens)}")

        # 3. Normalize to CoinGecko-compatible format
        normalized = [self._normalize_token(t) for t in active_tokens]

        # 4. Identify CMC-exclusive candidates (preliminary symbol filter)
        # NOTE: This is a quick pre-filter only. The authoritative multi-key
        # deduplication happens in CollectorTokenList._merge_token_lists(),
        # which uses contract address, slug, name+mcap, AND symbol matching.
        # We pass all normalized tokens so the parent can run full dedup.
        cmc_exclusive_preliminary = []
        if known_coingecko_symbols:
            cmc_exclusive_preliminary = [
                t for t in normalized
                if t['symbol'].lower() not in known_coingecko_symbols
            ]
            print(f"  [Phase A-2] CMC candidates (symbol pre-filter): {len(cmc_exclusive_preliminary)}")
            print(f"  [Phase A-2] (Final dedup by multi-key merge in parent collector)")
            if cmc_exclusive_preliminary:
                for t in cmc_exclusive_preliminary[:10]:
                    print(f"    + {t['symbol'].upper()} — {t['name']} (MCap: ${t.get('market_cap', 0):,.0f})")
                if len(cmc_exclusive_preliminary) > 10:
                    print(f"    ... and {len(cmc_exclusive_preliminary) - 10} more")
        else:
            # No CoinGecko symbols provided — all CMC tokens are candidates
            cmc_exclusive_preliminary = list(normalized)

        # 5. Save snapshot
        self._save_snapshot(normalized)

        return {
            'tokens': normalized,
            'total': len(normalized),
            'cmc_exclusive': cmc_exclusive_preliminary,
            'cmc_exclusive_count': len(cmc_exclusive_preliminary),
            'source': 'coinmarketcap',
            'collected_at': date.today().isoformat(),
        }

    def _fetch_all_listings(self) -> List[Dict]:
        """
        Paginate through CMC /listings/latest to get all tokens.
        CMC free tier: max 5000 per request. Total listings ~10,000+.
        Cost: 1 credit per 200 tokens (5000 tokens = 25 credits).
        """
        cached = self._cache_get('cmc_listings_all')
        if cached:
            print("  [Phase A-2] Using cached CMC listings")
            return cached

        all_tokens = []
        start = 1
        max_iterations = 5  # Safety limit: 5 × 5000 = 25,000 tokens

        for i in range(max_iterations):
            data = self._request_cmc(
                f'{self.CMC_BASE}/cryptocurrency/listings/latest',
                params={
                    'start': start,
                    'limit': self.BATCH_SIZE,
                    'convert': 'USD',
                    'sort': 'market_cap',
                    'sort_dir': 'desc',
                    'cryptocurrency_type': 'all',
                    'aux': 'num_market_pairs,date_added,tags,platform,max_supply,circulating_supply,total_supply',
                },
            )

            if not data or 'data' not in data:
                break

            batch = data['data']
            if not batch:
                break

            all_tokens.extend(batch)
            print(f"    CMC Page {i + 1}: +{len(batch)} tokens (total: {len(all_tokens)})")

            # If we got less than BATCH_SIZE, we've reached the end
            if len(batch) < self.BATCH_SIZE:
                break

            start += self.BATCH_SIZE
            time.sleep(2.0)  # Rate limit: 30 req/min

        # Cache for 1 hour
        if all_tokens:
            self._cache_set('cmc_listings_all', all_tokens, ttl=3600)

        return all_tokens

    def _request_cmc(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict]:
        """
        CMC-specific request wrapper.
        CMC returns {status: {...}, data: [...]} format.
        """
        result = self._request(url, params=params, timeout=30, max_retries=3)

        if result and 'status' in result:
            status = result['status']
            if status.get('error_code', 0) != 0:
                print(f"  [Phase A-2] CMC API error: {status.get('error_message', 'Unknown')}")
                return None
            # Log credit usage
            credit_count = status.get('credit_count', 0)
            if credit_count:
                print(f"    CMC credits used: {credit_count}")

        return result

    def _normalize_token(self, cmc_token: Dict) -> Dict[str, Any]:
        """
        Normalize CMC token data to CoinGecko-compatible format.
        This allows seamless merging in the unified token list.
        """
        quote = cmc_token.get('quote', {}).get('USD', {})
        platform = cmc_token.get('platform') or {}

        return {
            # Core identification
            'id': f"cmc-{cmc_token.get('slug', cmc_token.get('id', ''))}",
            'symbol': cmc_token.get('symbol', '').lower(),
            'name': cmc_token.get('name', ''),

            # Market data (CoinGecko-compatible field names)
            'current_price': quote.get('price', 0),
            'market_cap': quote.get('market_cap', 0),
            'market_cap_rank': cmc_token.get('cmc_rank'),
            'total_volume': quote.get('volume_24h', 0),
            'fully_diluted_valuation': quote.get('fully_diluted_market_cap', 0),
            'circulating_supply': cmc_token.get('circulating_supply', 0),
            'total_supply': cmc_token.get('total_supply', 0),
            'max_supply': cmc_token.get('max_supply'),

            # Price changes
            'price_change_percentage_24h': quote.get('percent_change_24h', 0),
            'price_change_percentage_7d_in_currency': quote.get('percent_change_7d', 0),
            'price_change_percentage_30d_in_currency': quote.get('percent_change_30d', 0),

            # Metadata
            'num_market_pairs': cmc_token.get('num_market_pairs', 0),
            'date_added': cmc_token.get('date_added'),
            'tags': cmc_token.get('tags', []),
            'last_updated': quote.get('last_updated'),

            # Platform/contract info
            'platform_name': platform.get('name'),
            'platform_token_address': platform.get('token_address'),

            # Source tracking
            '_source': 'coinmarketcap',
            '_cmc_id': cmc_token.get('id'),
            '_cmc_slug': cmc_token.get('slug'),
        }

    def _save_snapshot(self, tokens: List[Dict]):
        """Save today's CMC snapshot for diffing."""
        today = date.today().isoformat()
        snapshot = {
            'date': today,
            'total': len(tokens),
            'slugs': [t['id'] for t in tokens],
            'symbols': [t['symbol'] for t in tokens],
        }
        snap_path = self.SNAPSHOT_DIR / f'{today}.json'
        try:
            with open(snap_path, 'w') as f:
                json.dump(snapshot, f)

            # Cleanup: keep only last 7 days
            snapshots = sorted(self.SNAPSHOT_DIR.glob('*.json'))
            if len(snapshots) > 7:
                for old in snapshots[:-7]:
                    old.unlink()

        except Exception as e:
            print(f"  [Phase A-2] CMC snapshot save failed: {e}")

    def fetch_token_metadata(self, cmc_id: int) -> Optional[Dict]:
        """
        Fetch detailed metadata for a single CMC token.
        Includes: description, logo, urls, tags, platform info.
        Cost: 1 credit per token.
        """
        if not self.api_key:
            return None

        cached = self._cache_get(f'cmc_meta_{cmc_id}')
        if cached:
            return cached

        data = self._request_cmc(
            f'{self.CMC_BASE}/cryptocurrency/info',
            params={'id': str(cmc_id)},
        )

        if data and 'data' in data:
            meta = data['data'].get(str(cmc_id), {})
            if meta:
                result = {
                    'id': meta.get('id'),
                    'name': meta.get('name'),
                    'symbol': meta.get('symbol'),
                    'slug': meta.get('slug'),
                    'description': (meta.get('description', '') or '')[:500],
                    'date_launched': meta.get('date_launched'),
                    'tags': meta.get('tags', []),
                    'urls': meta.get('urls', {}),
                    'logo': meta.get('logo'),
                    'platform': meta.get('platform'),
                    'contract_address': meta.get('contract_address', []),
                }
                self._cache_set(f'cmc_meta_{cmc_id}', result, ttl=86400)  # 24h
                return result

        return None


if __name__ == '__main__':
    import sys

    api_key = os.environ.get('CMC_API_KEY', '')
    if not api_key:
        print("Set CMC_API_KEY environment variable to test.")
        print("Example: CMC_API_KEY=your_key python -m collectors.collector_tokenlist_cmc")
        sys.exit(1)

    ctl = CollectorTokenListCMC(api_key=api_key)
    result = ctl.collect()
    print(f"\nTotal CMC tokens: {result['total']}")
    print(f"CMC-exclusive: {result.get('cmc_exclusive_count', 0)}")
    if result['tokens']:
        top5 = result['tokens'][:5]
        print("\nTop 5 by market cap:")
        for t in top5:
            print(f"  {t.get('symbol','?').upper():>8} | ${t.get('current_price',0):>12,.2f} | MCap: ${t.get('market_cap',0):>16,.0f}")
