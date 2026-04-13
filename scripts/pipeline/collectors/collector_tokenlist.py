"""
Phase A: Token List Collector (v2 — CoinGecko + CoinMarketCap)
Fetches the full list of CEX-traded tokens from CoinGecko (primary) and
CoinMarketCap (secondary), merges into a unified list with deduplication.
Detects new listings and delistings by comparing against yesterday's list.

v2 Changes (CRO-001):
  - Added CoinMarketCap as secondary data source
  - Unified merge logic with symbol-based deduplication
  - CMC-exclusive token discovery for expanded coverage
  - Source tracking (_source field) for provenance

Usage:
    from collectors.collector_tokenlist import CollectorTokenList
    ctl = CollectorTokenList(cmc_api_key='YOUR_CMC_KEY')
    result = ctl.collect()
    # result = {
    #   'tokens': [...],              # Merged CoinGecko + CMC tokens
    #   'total': 4200,
    #   'new_listings': [...],        # Added since last run
    #   'delistings': [...],          # Removed since last run
    #   'sources': {'coingecko': 2534, 'coinmarketcap': 3800, 'cmc_exclusive': 1666},
    # }
"""

import json
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .base_collector import BaseCollector
from .collector_tokenlist_cmc import CollectorTokenListCMC


class CollectorTokenList(BaseCollector):
    """
    Collects the full list of tokens traded on centralized exchanges.
    Primary source: CoinGecko. Secondary source: CoinMarketCap.
    Merges both into a unified list with symbol-based deduplication.
    Maintains a daily snapshot for diffing (new listings / delistings).
    """

    COINGECKO_BASE = 'https://api.coingecko.com/api/v3'
    SNAPSHOT_DIR = Path(__file__).parent / '.cache' / 'token_snapshots'
    BATCH_SIZE = 250  # CoinGecko /coins/markets max per_page

    def __init__(self, cmc_api_key: Optional[str] = None):
        super().__init__()
        self.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.cmc_api_key = cmc_api_key or os.environ.get('CMC_API_KEY', '')
        self._cmc_collector = CollectorTokenListCMC(api_key=self.cmc_api_key) if self.cmc_api_key else None

    def collect(self) -> Dict[str, Any]:
        """
        Main entry: fetch tokens from CoinGecko + CoinMarketCap, merge, detect changes.
        Returns enriched dict with unified token list, new_listings, delistings, source stats.
        """
        print("  [Phase A] Collecting token list (CoinGecko + CoinMarketCap)...")

        # ── Step 1: CoinGecko (primary) ──
        print("  [Phase A] Step 1/4: CoinGecko fetch...")
        all_tokens_cg = self._fetch_all_market_tokens()
        cex_tokens_cg = []
        if all_tokens_cg:
            cex_tokens_cg = [
                t for t in all_tokens_cg
                if t.get('total_volume', 0) and t.get('total_volume', 0) > 0
            ]
            # Tag source
            for t in cex_tokens_cg:
                t['_source'] = 'coingecko'

        print(f"  [Phase A] CoinGecko: {len(cex_tokens_cg)} active CEX tokens")

        # ── Step 2: CoinMarketCap (secondary) ──
        cmc_result = {'tokens': [], 'cmc_exclusive': [], 'total': 0}
        if self._cmc_collector:
            print("  [Phase A] Step 2/4: CoinMarketCap fetch...")
            known_cg_symbols = {t.get('symbol', '').lower() for t in cex_tokens_cg}
            cmc_result = self._cmc_collector.collect(known_coingecko_symbols=known_cg_symbols)
            print(f"  [Phase A] CoinMarketCap: {cmc_result['total']} tokens, "
                  f"{len(cmc_result.get('cmc_exclusive', []))} exclusive")
        else:
            print("  [Phase A] Step 2/4: CoinMarketCap skipped (no API key)")

        # ── Step 3: Merge with deduplication ──
        print("  [Phase A] Step 3/4: Merging token lists...")
        merged_tokens = self._merge_token_lists(cex_tokens_cg, cmc_result.get('cmc_exclusive', []))
        print(f"  [Phase A] Merged total: {len(merged_tokens)} tokens "
              f"(CG: {len(cex_tokens_cg)}, CMC-exclusive: {len(cmc_result.get('cmc_exclusive', []))})")

        # ── Step 4: Diff against yesterday ──
        print("  [Phase A] Step 4/4: Detecting changes...")
        yesterday_slugs = self._load_snapshot_slugs()
        today_slugs = {t['id'] for t in merged_tokens}

        new_listings = [
            t for t in merged_tokens
            if t['id'] not in yesterday_slugs
        ] if yesterday_slugs else []

        delistings = [
            slug for slug in yesterday_slugs
            if slug not in today_slugs
        ] if yesterday_slugs else []

        if new_listings:
            print(f"  [Phase A] New listings detected: {len(new_listings)}")
            for t in new_listings[:5]:
                src = t.get('_source', '?')
                print(f"    + {t.get('symbol','?').upper()} ({t['id']}) [{src}]")
            if len(new_listings) > 5:
                print(f"    ... and {len(new_listings) - 5} more")

        if delistings:
            print(f"  [Phase A] Delistings detected: {len(delistings)}")
            for slug in delistings[:5]:
                print(f"    - {slug}")

        # Save snapshot
        self._save_snapshot(merged_tokens)

        return {
            'tokens': merged_tokens,
            'total': len(merged_tokens),
            'new_listings': new_listings,
            'delistings': delistings,
            'collected_at': date.today().isoformat(),
            'sources': {
                'coingecko': len(cex_tokens_cg),
                'coinmarketcap': cmc_result.get('total', 0),
                'cmc_exclusive': len(cmc_result.get('cmc_exclusive', [])),
                'merged_total': len(merged_tokens),
            },
        }

    # ── Multi-Key Deduplication (CRO-001 v2) ──────────────────────────

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize token name for comparison: lowercase, strip suffixes, remove punctuation."""
        n = name.lower().strip()
        # Remove common suffixes that differ between sources
        for suffix in [' token', ' coin', ' network', ' protocol', ' finance', ' swap', ' chain']:
            if n.endswith(suffix):
                n = n[:-len(suffix)].strip()
        # Remove punctuation and extra whitespace
        n = re.sub(r'[^a-z0-9\s]', '', n)
        n = re.sub(r'\s+', ' ', n).strip()
        return n

    @staticmethod
    def _normalize_contract(addr: str) -> str:
        """Normalize contract address: lowercase, strip whitespace."""
        if not addr:
            return ''
        return addr.lower().strip()

    @staticmethod
    def _market_cap_similar(mc1: float, mc2: float, tolerance: float = 0.25) -> bool:
        """Check if two market caps are within tolerance ratio of each other."""
        if not mc1 or not mc2 or mc1 <= 0 or mc2 <= 0:
            return False
        ratio = max(mc1, mc2) / min(mc1, mc2)
        return ratio <= (1.0 + tolerance)

    def _build_cg_indexes(self, cg_tokens: List[Dict]) -> dict:
        """
        Build multi-key lookup indexes from CoinGecko tokens for O(1) matching.

        Returns dict with:
          - 'symbols': set of lowercase symbols
          - 'names': set of normalized names
          - 'slugs': set of CoinGecko IDs (slugs)
          - 'contracts': dict mapping normalized_address → token
          - 'name_to_token': dict mapping normalized_name → token (for mcap check)
        """
        symbols: Set[str] = set()
        names: Set[str] = set()
        slugs: Set[str] = set()
        contracts: Dict[str, Dict] = {}
        name_to_token: Dict[str, Dict] = {}

        for t in cg_tokens:
            sym = t.get('symbol', '').lower()
            if sym:
                symbols.add(sym)

            slug = t.get('id', '').lower()
            if slug:
                slugs.add(slug)

            norm_name = self._normalize_name(t.get('name', ''))
            if norm_name:
                names.add(norm_name)
                name_to_token[norm_name] = t

            # CoinGecko /coins/markets doesn't include contract addresses directly,
            # but if we've enriched the token with platform data, use it
            platforms = t.get('platforms', {})
            if platforms:
                for chain, addr in platforms.items():
                    if addr:
                        norm_addr = self._normalize_contract(addr)
                        if norm_addr:
                            contracts[norm_addr] = t

        return {
            'symbols': symbols,
            'names': names,
            'slugs': slugs,
            'contracts': contracts,
            'name_to_token': name_to_token,
        }

    def _is_duplicate(self, cmc_token: Dict, cg_index: dict) -> Tuple[bool, str]:
        """
        Multi-key duplicate check for a CMC token against CoinGecko index.

        Matching priority (most reliable first):
          1. Contract address — unique per chain, near-perfect match
          2. Slug match — CoinGecko id vs CMC slug (e.g. both "bitcoin-cash")
          3. Normalized name + market cap proximity — catches renamed/rebranded tokens
          4. Symbol match — least reliable (kept as final layer)

        Returns:
            (is_duplicate: bool, match_reason: str)
        """
        # ── Layer 1: Contract Address ──
        cmc_contract = self._normalize_contract(
            cmc_token.get('platform_token_address', '')
        )
        if cmc_contract and cmc_contract in cg_index['contracts']:
            return True, 'contract_address'

        # ── Layer 2: Slug Match ──
        cmc_slug = cmc_token.get('_cmc_slug', '').lower()
        if cmc_slug and cmc_slug in cg_index['slugs']:
            return True, 'slug'

        # ── Layer 3: Name + Market Cap Proximity ──
        cmc_name = self._normalize_name(cmc_token.get('name', ''))
        if cmc_name and cmc_name in cg_index['names']:
            cg_match = cg_index['name_to_token'].get(cmc_name)
            if cg_match:
                cmc_mc = cmc_token.get('market_cap', 0)
                cg_mc = cg_match.get('market_cap', 0)
                # Name match + market cap within 25% → almost certainly same project
                if self._market_cap_similar(cmc_mc, cg_mc, tolerance=0.25):
                    return True, 'name+mcap'
                # Name exact match alone is strong but not conclusive
                # (e.g., "Baby Doge" vs "Baby Doge Coin" after normalization)
                # Still flag as duplicate if market cap data is missing
                if not cmc_mc or not cg_mc:
                    return True, 'name_only'

        # ── Layer 4: Symbol Match (legacy, least reliable) ──
        sym = cmc_token.get('symbol', '').lower()
        if sym and sym in cg_index['symbols']:
            return True, 'symbol'

        return False, ''

    def _merge_token_lists(
        self,
        coingecko_tokens: List[Dict],
        cmc_exclusive_tokens: List[Dict],
    ) -> List[Dict]:
        """
        Merge CoinGecko tokens with CMC-exclusive tokens using multi-key dedup.

        CoinGecko is primary (takes precedence on all duplicates).
        CMC tokens are checked against CoinGecko using 4 layers:
          1. Contract address (most reliable)
          2. Slug/ID match
          3. Normalized name + market cap proximity
          4. Symbol (fallback, least reliable)

        Only tokens that pass ALL layers without a match are added as CMC-exclusive.
        """
        merged = list(coingecko_tokens)  # CoinGecko first (primary)

        # Build multi-key index from CoinGecko data
        cg_index = self._build_cg_indexes(coingecko_tokens)

        # Also track already-added CMC tokens to prevent intra-CMC duplicates
        added_symbols: Set[str] = set()
        added_names: Set[str] = set()

        added = 0
        skipped_reasons: Dict[str, int] = {}

        for cmc_token in cmc_exclusive_tokens:
            is_dup, reason = self._is_duplicate(cmc_token, cg_index)

            if is_dup:
                skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
                continue

            # Intra-CMC dedup: prevent same symbol/name from CMC list itself
            sym = cmc_token.get('symbol', '').lower()
            norm_name = self._normalize_name(cmc_token.get('name', ''))

            if sym and sym in added_symbols:
                skipped_reasons['intra_cmc_symbol'] = skipped_reasons.get('intra_cmc_symbol', 0) + 1
                continue
            if norm_name and norm_name in added_names:
                skipped_reasons['intra_cmc_name'] = skipped_reasons.get('intra_cmc_name', 0) + 1
                continue

            merged.append(cmc_token)
            if sym:
                added_symbols.add(sym)
                cg_index['symbols'].add(sym)  # Update index for subsequent checks
            if norm_name:
                added_names.add(norm_name)
                cg_index['names'].add(norm_name)
            added += 1

        # Log dedup stats
        if added:
            print(f"  [Merge] Added {added} CMC-exclusive tokens to unified list")
        if skipped_reasons:
            total_skipped = sum(skipped_reasons.values())
            print(f"  [Merge] Deduplicated {total_skipped} CMC tokens:")
            for reason, count in sorted(skipped_reasons.items(), key=lambda x: -x[1]):
                print(f"    - {reason}: {count}")

        return merged

    def _fetch_all_market_tokens(self) -> List[Dict]:
        """
        Paginate through CoinGecko /coins/markets to get all tokens.
        CoinGecko free tier: max 250 per page, up to ~60 pages.
        """
        # Check cache first (1 hour TTL)
        cached = self._cache_get('tokenlist_all_markets')
        if cached:
            print("  [Phase A] Using cached token list")
            return cached

        all_tokens = []
        page = 1
        max_pages = 60  # Safety limit (~15,000 tokens)

        while page <= max_pages:
            data = self._request(
                f'{self.COINGECKO_BASE}/coins/markets',
                params={
                    'vs_currency': 'usd',
                    'order': 'market_cap_desc',
                    'per_page': self.BATCH_SIZE,
                    'page': page,
                    'sparkline': 'false',
                    'price_change_percentage': '24h,7d,30d',
                },
                timeout=15,
            )

            if not data or len(data) == 0:
                break

            all_tokens.extend(data)
            print(f"    Page {page}: +{len(data)} tokens (total: {len(all_tokens)})")
            page += 1

            # Rate limit: CoinGecko free tier ~10-30 req/min
            # Use 6s interval to stay safely under limit
            time.sleep(6)

        # Cache for 1 hour
        if all_tokens:
            self._cache_set('tokenlist_all_markets', all_tokens, ttl=3600)

        return all_tokens

    def _load_snapshot_slugs(self) -> set:
        """Load yesterday's token slugs for comparison."""
        yesterday = date.today().isoformat()
        # Look for most recent snapshot that isn't today
        snapshots = sorted(self.SNAPSHOT_DIR.glob('*.json'), reverse=True)

        for snap_path in snapshots:
            snap_date = snap_path.stem
            if snap_date != yesterday:
                try:
                    with open(snap_path, 'r') as f:
                        data = json.load(f)
                    return set(data.get('slugs', []))
                except Exception:
                    continue

        return set()

    def _save_snapshot(self, tokens: List[Dict]):
        """Save today's snapshot for tomorrow's diff."""
        today = date.today().isoformat()
        snapshot = {
            'date': today,
            'total': len(tokens),
            'slugs': [t['id'] for t in tokens],
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
            print(f"  [Phase A] Snapshot save failed: {e}")

    def fetch_token_detail(self, coingecko_id: str) -> Optional[Dict]:
        """
        Fetch detailed info for a single token (for transparency checks).
        Includes: description, links, team info, tickers.
        """
        cached = self._cache_get(f'token_detail_{coingecko_id}')
        if cached:
            return cached

        data = self._request(
            f'{self.COINGECKO_BASE}/coins/{coingecko_id}',
            params={
                'localization': 'false',
                'tickers': 'true',
                'market_data': 'false',
                'community_data': 'true',
                'developer_data': 'true',
            },
            timeout=15,
        )

        if data:
            detail = {
                'id': data.get('id'),
                'symbol': data.get('symbol'),
                'name': data.get('name'),
                'description': (data.get('description', {}).get('en', '') or '')[:500],
                'genesis_date': data.get('genesis_date'),
                'categories': data.get('categories', []),
                'links': {
                    'homepage': (data.get('links', {}).get('homepage', []) or [None])[0],
                    'github': data.get('links', {}).get('repos_url', {}).get('github', []),
                    'twitter': data.get('links', {}).get('twitter_screen_name'),
                    'telegram': data.get('links', {}).get('telegram_channel_identifier'),
                    'subreddit': data.get('links', {}).get('subreddit_url'),
                },
                'platforms': data.get('platforms', {}),
                'tickers_count': len(data.get('tickers', [])),
                'community_data': data.get('community_data', {}),
                'developer_data': data.get('developer_data', {}),
            }
            self._cache_set(f'token_detail_{coingecko_id}', detail, ttl=86400)  # 24h
            return detail

        return None


if __name__ == '__main__':
    ctl = CollectorTokenList()
    result = ctl.collect()
    print(f"\nTotal merged tokens: {result['total']}")
    print(f"New listings: {len(result['new_listings'])}")
    print(f"Delistings: {len(result['delistings'])}")
    if 'sources' in result:
        src = result['sources']
        print(f"\nSource breakdown:")
        print(f"  CoinGecko:      {src.get('coingecko', 0)}")
        print(f"  CoinMarketCap:  {src.get('coinmarketcap', 0)}")
        print(f"  CMC-exclusive:  {src.get('cmc_exclusive', 0)}")
        print(f"  Merged total:   {src.get('merged_total', 0)}")
    if result['tokens']:
        top5 = result['tokens'][:5]
        print("\nTop 5 by market cap:")
        for t in top5:
            src = t.get('_source', '?')
            print(f"  {t.get('symbol','?').upper():>8} | ${t.get('current_price',0):>12,.2f} | MCap: ${t.get('market_cap',0):>16,.0f} [{src}]")
