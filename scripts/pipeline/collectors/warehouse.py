"""
Data Warehouse Client — Supabase Integration (RPC-based)
Provides persistent storage for all collector data via the BCE Lab data warehouse.

All data operations go through PostgreSQL RPC functions (wh_*) to avoid
PostgREST schema exposure issues. The `data` schema tables are accessed
exclusively through SECURITY DEFINER functions in the public schema.

Architecture:
    TEMPORARY data (auto-expire):
        - api_cache: API response cache with TTL (replaces file-based cache)
        - market_snapshots: High-frequency market data (90-day retention)

    LONG-TERM data (permanent):
        - price_daily: Daily OHLCV price data
        - onchain_daily: Daily on-chain metrics (TVL, holders, tx counts)
        - macro_daily: Daily macro market indicators
        - whale_transfers: Individual large transfer records
        - exchange_flow_daily: Daily exchange inflow/outflow summary
        - fundamentals_weekly: Weekly project fundamental metrics
        - collection_runs: Audit log for pipeline executions

Usage:
    from collectors.warehouse import Warehouse, get_warehouse

    wh = get_warehouse()
    wh.upsert_price_daily(project_id, 'uniswap', date.today(), {...})
    wh.cache_set('coingecko:uniswap:market', data, ttl_seconds=3600)
    cached = wh.cache_get('coingecko:uniswap:market')
"""

import json
import os
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

# ─── Configuration ───────────────────────────────────────────

SUPABASE_URL = os.environ.get(
    'SUPABASE_URL',
    'https://wbqponoiyoeqlepxogcb.supabase.co'
)
SUPABASE_KEY = os.environ.get(
    'SUPABASE_SERVICE_KEY',
    os.environ.get('SUPABASE_KEY', '')
)


def _clean_for_json(val):
    """Convert Python types to JSON-serializable values."""
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, (int, float, str, bool)):
        return val
    return str(val)


class Warehouse:
    """
    Supabase data warehouse client for BCE Lab collectors.
    Uses RPC functions (wh_*) for all data schema operations.
    Falls back gracefully if Supabase is unavailable.
    """

    def __init__(self, url: str = None, key: str = None):
        self.url = url or SUPABASE_URL
        self.key = key or SUPABASE_KEY
        self.client: Optional[Client] = None
        self._connected = False

        if HAS_SUPABASE and self.key:
            try:
                self.client = create_client(self.url, self.key)
                self._connected = True
            except Exception as e:
                print(f"  [Warehouse] Connection failed: {e}")
        elif not HAS_SUPABASE:
            print("  [Warehouse] supabase-py not installed. pip install supabase")
        elif not self.key:
            print("  [Warehouse] No SUPABASE_SERVICE_KEY set. Running in offline mode.")

    @property
    def connected(self) -> bool:
        return self._connected

    def _rpc(self, fn_name: str, params: dict) -> Any:
        """Call a Supabase RPC function. Returns result data or None."""
        if not self._connected:
            return None
        try:
            result = self.client.rpc(fn_name, params).execute()
            return result.data
        except Exception as e:
            print(f"  [Warehouse] RPC {fn_name} error: {e}")
            return None

    # ═══════════════════════════════════════════════════════════
    #  API CACHE (Temporary)
    # ═══════════════════════════════════════════════════════════

    def cache_get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached API response if not expired.

        Args:
            cache_key: Unique cache key, e.g. 'coingecko:uniswap:market'

        Returns:
            Cached response body as dict, or None if miss/expired
        """
        result = self._rpc('wh_cache_get', {'p_key': cache_key})
        return result if result else None

    def cache_set(
        self,
        cache_key: str,
        data: Dict[str, Any],
        source: str = 'unknown',
        ttl_seconds: int = 3600,
    ) -> bool:
        """
        Store API response in cache with TTL.

        Args:
            cache_key: Unique key
            data: Response body to cache
            source: API source name ('coingecko', 'etherscan', etc.)
            ttl_seconds: Time-to-live in seconds (default 1 hour)
        """
        result = self._rpc('wh_cache_set', {
            'p_key': cache_key,
            'p_body': data,
            'p_source': source,
            'p_ttl_seconds': ttl_seconds,
        })
        return result is not None

    # ═══════════════════════════════════════════════════════════
    #  PRICE DATA (Long-term)
    # ═══════════════════════════════════════════════════════════

    def upsert_price_daily(
        self,
        project_id: str,
        coingecko_id: str,
        date_val: date,
        ohlcv: Dict[str, Any],
    ) -> bool:
        """Insert or update daily price OHLCV record."""
        if not self._connected:
            return False
        result = self._rpc('wh_upsert_price_daily', {
            'p_data': {
                'project_id': project_id,
                'coingecko_id': coingecko_id,
                'date': date_val.isoformat(),
                'open': _clean_for_json(ohlcv.get('open')),
                'high': _clean_for_json(ohlcv.get('high')),
                'low': _clean_for_json(ohlcv.get('low')),
                'close': _clean_for_json(ohlcv.get('close', ohlcv.get('price'))),
                'volume_usd': _clean_for_json(ohlcv.get('volume_usd', ohlcv.get('volume'))),
                'market_cap_usd': _clean_for_json(ohlcv.get('market_cap_usd', ohlcv.get('market_cap'))),
            }
        })
        return result is not None

    def bulk_upsert_price_daily(
        self,
        project_id: str,
        coingecko_id: str,
        records: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk insert/update daily price records via RPC.

        Returns:
            Number of records upserted
        """
        if not self._connected or not records:
            return 0

        rows = []
        for r in records:
            d = r.get('date')
            if isinstance(d, datetime):
                d = d.date()
            if isinstance(d, date):
                d = d.isoformat()
            rows.append({
                'project_id': project_id,
                'coingecko_id': coingecko_id,
                'date': d,
                'open': _clean_for_json(r.get('open')),
                'high': _clean_for_json(r.get('high')),
                'low': _clean_for_json(r.get('low')),
                'close': _clean_for_json(r.get('close', r.get('price'))),
                'volume_usd': _clean_for_json(r.get('volume_usd', r.get('volume'))),
                'market_cap_usd': _clean_for_json(r.get('market_cap_usd', r.get('market_cap'))),
            })

        # Batch in chunks of 500
        total = 0
        for i in range(0, len(rows), 500):
            chunk = rows[i:i+500]
            result = self._rpc('wh_bulk_upsert_prices', {'p_rows': chunk})
            if result is not None:
                total += result if isinstance(result, int) else len(chunk)
        return total

    def get_price_history(
        self,
        project_id: str,
        days: int = 90,
    ) -> List[Dict[str, Any]]:
        """Fetch recent price history from warehouse."""
        result = self._rpc('wh_get_price_history', {
            'p_project_id': project_id,
            'p_days': days,
        })
        return result if isinstance(result, list) else []

    # ═══════════════════════════════════════════════════════════
    #  MARKET SNAPSHOTS (Temporary — 90-day retention)
    # ═══════════════════════════════════════════════════════════

    def insert_market_snapshot(
        self,
        project_id: str,
        snapshot: Dict[str, Any],
    ) -> bool:
        """Insert a high-frequency market snapshot."""
        if not self._connected:
            return False
        result = self._rpc('wh_insert_market_snapshot', {
            'p_data': {
                'project_id': project_id,
                'price_usd': _clean_for_json(snapshot.get('current_price')),
                'volume_24h_usd': _clean_for_json(snapshot.get('total_volume')),
                'market_cap_usd': _clean_for_json(snapshot.get('market_cap')),
                'price_change_1h_pct': _clean_for_json(snapshot.get('price_change_percentage_1h_in_currency')),
                'price_change_24h_pct': _clean_for_json(snapshot.get('price_change_percentage_24h')),
                'price_change_7d_pct': _clean_for_json(snapshot.get('price_change_percentage_7d')),
                'circulating_supply': _clean_for_json(snapshot.get('circulating_supply')),
                'total_supply': _clean_for_json(snapshot.get('total_supply')),
                'ath_usd': _clean_for_json(snapshot.get('ath')),
                'atl_usd': _clean_for_json(snapshot.get('atl')),
                'extra': {},
            }
        })
        return result is not None

    # ═══════════════════════════════════════════════════════════
    #  ON-CHAIN METRICS (Long-term)
    # ═══════════════════════════════════════════════════════════

    def upsert_onchain_daily(
        self,
        project_id: str,
        date_val: date,
        metrics: Dict[str, Any],
    ) -> bool:
        """Insert or update daily on-chain metrics."""
        if not self._connected:
            return False

        known = {'tvl_usd', 'holder_count', 'active_addresses_24h',
                 'tx_count_24h', 'transfer_volume_usd', 'gas_used', 'unique_contracts'}
        extra = {k: _clean_for_json(v) for k, v in metrics.items() if k not in known}

        result = self._rpc('wh_upsert_onchain_daily', {
            'p_data': {
                'project_id': project_id,
                'date': date_val.isoformat(),
                'tvl_usd': _clean_for_json(metrics.get('tvl_usd')),
                'holder_count': _clean_for_json(metrics.get('holder_count')),
                'active_addresses_24h': _clean_for_json(metrics.get('active_addresses_24h')),
                'tx_count_24h': _clean_for_json(metrics.get('tx_count_24h')),
                'transfer_volume_usd': _clean_for_json(metrics.get('transfer_volume_usd')),
                'gas_used': _clean_for_json(metrics.get('gas_used')),
                'unique_contracts': _clean_for_json(metrics.get('unique_contracts')),
                'extra': extra if extra else {},
            }
        })
        return result is not None

    # ═══════════════════════════════════════════════════════════
    #  MACRO INDICATORS (Long-term)
    # ═══════════════════════════════════════════════════════════

    def upsert_macro_daily(
        self,
        date_val: date,
        macro: Dict[str, Any],
    ) -> bool:
        """Insert or update daily macro market indicators."""
        if not self._connected:
            return False

        known = {'total_market_cap_usd', 'total_volume_24h_usd', 'btc_price_usd',
                 'btc_dominance_pct', 'eth_price_usd', 'eth_dominance_pct',
                 'defi_tvl_usd', 'fear_greed_value', 'fear_greed_label',
                 'active_cryptos', 'stablecoin_mcap_usd', 'dxy_index', 'fed_rate', 'sp500_close'}
        extra = {k: _clean_for_json(v) for k, v in macro.items() if k not in known}

        result = self._rpc('wh_upsert_macro_daily', {
            'p_data': {
                'date': date_val.isoformat(),
                'total_market_cap_usd': _clean_for_json(macro.get('total_market_cap_usd')),
                'total_volume_24h_usd': _clean_for_json(macro.get('total_volume_24h_usd')),
                'btc_price_usd': _clean_for_json(macro.get('btc_price_usd')),
                'btc_dominance_pct': _clean_for_json(macro.get('btc_dominance_pct')),
                'eth_price_usd': _clean_for_json(macro.get('eth_price_usd')),
                'eth_dominance_pct': _clean_for_json(macro.get('eth_dominance_pct')),
                'defi_tvl_usd': _clean_for_json(macro.get('defi_tvl_usd')),
                'fear_greed_value': _clean_for_json(macro.get('fear_greed_value')),
                'fear_greed_label': macro.get('fear_greed_label'),
                'active_cryptos': _clean_for_json(macro.get('active_cryptos')),
                'stablecoin_mcap_usd': _clean_for_json(macro.get('stablecoin_mcap_usd')),
                'dxy_index': _clean_for_json(macro.get('dxy_index')),
                'fed_rate': _clean_for_json(macro.get('fed_rate')),
                'sp500_close': _clean_for_json(macro.get('sp500_close')),
                'extra': extra if extra else {},
            }
        })
        return result is not None

    def get_macro_history(self, days: int = 90) -> List[Dict[str, Any]]:
        """Fetch recent macro history from warehouse."""
        if not self._connected:
            return []
        try:
            since = (date.today() - timedelta(days=days)).isoformat()
            result = self.client.from_("macro_daily").select("*").gte("date", since).order("date").execute()
            return result.data or []
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════
    #  WHALE TRANSFERS (Long-term)
    # ═══════════════════════════════════════════════════════════

    def insert_whale_transfers(
        self,
        project_id: str,
        transfers: List[Dict[str, Any]],
    ) -> int:
        """Bulk insert whale transfer records. Skips duplicates."""
        if not self._connected or not transfers:
            return 0
        count = 0
        for t in transfers:
            result = self._rpc('wh_insert_whale_transfer', {
                'p_data': {
                    'project_id': project_id,
                    'tx_hash': t.get('tx_hash', t.get('hash', '')),
                    'block_number': _clean_for_json(t.get('block_number')),
                    'timestamp': t.get('timestamp', datetime.utcnow().isoformat()),
                    'from_address': t.get('from_address', t.get('from', '')),
                    'to_address': t.get('to_address', t.get('to', '')),
                    'amount': str(t.get('amount', 0)),
                    'amount_usd': _clean_for_json(t.get('amount_usd')),
                    'from_label': t.get('from_label'),
                    'to_label': t.get('to_label'),
                    'direction': t.get('direction'),
                    'chain': t.get('chain', 'ethereum'),
                }
            })
            if result is not None:
                count += 1
        return count

    def upsert_exchange_flow_daily(
        self,
        project_id: str,
        date_val: date,
        flow: Dict[str, Any],
    ) -> bool:
        """Insert or update daily exchange flow summary."""
        if not self._connected:
            return False
        result = self._rpc('wh_upsert_exchange_flow', {
            'p_data': {
                'project_id': project_id,
                'date': date_val.isoformat(),
                'inflow_count': _clean_for_json(flow.get('inflow_count', 0)),
                'inflow_amount': str(flow.get('inflow_amount', 0)),
                'inflow_usd': _clean_for_json(flow.get('inflow_usd', 0)),
                'outflow_count': _clean_for_json(flow.get('outflow_count', 0)),
                'outflow_amount': str(flow.get('outflow_amount', 0)),
                'outflow_usd': _clean_for_json(flow.get('outflow_usd', 0)),
                'netflow_amount': str(flow.get('netflow_amount', 0)),
                'netflow_usd': _clean_for_json(flow.get('netflow_usd', 0)),
            }
        })
        return result is not None

    # ═══════════════════════════════════════════════════════════
    #  FUNDAMENTALS (Long-term, weekly)
    # ═══════════════════════════════════════════════════════════

    def upsert_fundamentals_weekly(
        self,
        project_id: str,
        week_start: date,
        data: Dict[str, Any],
    ) -> bool:
        """Insert or update weekly fundamentals snapshot."""
        if not self._connected:
            return False

        known = {'github_stars', 'github_forks', 'github_commits_7d',
                 'github_contributors', 'github_open_issues', 'twitter_followers',
                 'telegram_members', 'discord_members', 'governance_proposals', 'governance_voters'}
        extra = {k: _clean_for_json(v) for k, v in data.items() if k not in known}

        result = self._rpc('wh_upsert_fundamentals', {
            'p_data': {
                'project_id': project_id,
                'week_start': week_start.isoformat(),
                'github_stars': _clean_for_json(data.get('github_stars')),
                'github_forks': _clean_for_json(data.get('github_forks')),
                'github_commits_7d': _clean_for_json(data.get('github_commits_7d')),
                'github_contributors': _clean_for_json(data.get('github_contributors')),
                'github_open_issues': _clean_for_json(data.get('github_open_issues')),
                'twitter_followers': _clean_for_json(data.get('twitter_followers')),
                'telegram_members': _clean_for_json(data.get('telegram_members')),
                'discord_members': _clean_for_json(data.get('discord_members')),
                'governance_proposals': _clean_for_json(data.get('governance_proposals')),
                'governance_voters': _clean_for_json(data.get('governance_voters')),
                'extra': extra if extra else {},
            }
        })
        return result is not None

    # ═══════════════════════════════════════════════════════════
    #  COLLECTION RUNS (Audit)
    # ═══════════════════════════════════════════════════════════

    def start_collection_run(
        self,
        project_id: str,
        run_type: str = 'full',
        triggered_by: str = 'manual',
    ) -> Optional[int]:
        """Start a new collection run audit record. Returns run ID."""
        result = self._rpc('wh_start_run', {
            'p_project_id': project_id,
            'p_run_type': run_type,
            'p_triggered_by': triggered_by,
        })
        return result if isinstance(result, int) else None

    def finish_collection_run(
        self,
        run_id: int,
        status: str = 'success',
        sources: List[str] = None,
        records_inserted: int = 0,
        error_log: str = None,
    ) -> bool:
        """Complete a collection run audit record."""
        if run_id is None:
            return False
        result = self._rpc('wh_finish_run', {
            'p_run_id': run_id,
            'p_status': status,
            'p_sources': sources or [],
            'p_records': records_inserted,
            'p_error': error_log,
        })
        return result is not None

    # ═══════════════════════════════════════════════════════════
    #  TRACKED PROJECTS (Helper — uses public schema directly)
    # ═══════════════════════════════════════════════════════════

    def get_project_id(self, slug: str) -> Optional[str]:
        """Look up tracked_projects UUID by slug."""
        result = self._rpc('wh_get_project_id', {'p_slug': slug})
        return result if result else None

    def ensure_tracked_project(
        self,
        slug: str,
        name: str,
        symbol: str = '',
        chain: str = 'ethereum',
        coingecko_id: str = '',
        **kwargs,
    ) -> Optional[str]:
        """Get or create a tracked project entry. Returns project UUID."""
        result = self._rpc('wh_ensure_project', {
            'p_slug': slug,
            'p_name': name,
            'p_symbol': symbol,
            'p_chain': chain,
            'p_coingecko_id': coingecko_id,
            'p_website_url': kwargs.get('website_url', ''),
            'p_category': kwargs.get('category', ''),
        })
        return result if result else None

    # ═══════════════════════════════════════════════════════════
    #  CLEANUP
    # ═══════════════════════════════════════════════════════════

    def cleanup_expired(self) -> Dict[str, int]:
        """Run the cleanup function to remove expired temporary data."""
        result = self._rpc('wh_cleanup', {})
        return result if isinstance(result, dict) else {}


# ─── Convenience singleton ───────────────────────────────────

_warehouse_instance: Optional[Warehouse] = None


def get_warehouse() -> Warehouse:
    """Get or create the global warehouse singleton."""
    global _warehouse_instance
    if _warehouse_instance is None:
        _warehouse_instance = Warehouse()
    return _warehouse_instance


if __name__ == '__main__':
    print("Testing Warehouse client...")
    wh = Warehouse()
    print(f"  Connected: {wh.connected}")
    if wh.connected:
        # Test cache
        print("\n  Testing API cache...")
        ok = wh.cache_set('test:hello', {'msg': 'world', 'ts': 123}, source='test', ttl_seconds=60)
        print(f"    cache_set: {ok}")
        val = wh.cache_get('test:hello')
        print(f"    cache_get: {val}")

        # Test project
        print("\n  Testing tracked project...")
        pid = wh.ensure_tracked_project(
            slug='uniswap',
            name='Uniswap',
            symbol='UNI',
            coingecko_id='uniswap',
        )
        print(f"    Project ID: {pid}")

        if pid:
            # Test price
            from datetime import date as dt_date
            print("\n  Testing price upsert...")
            ok = wh.upsert_price_daily(pid, 'uniswap', dt_date.today(), {
                'close': 5.23, 'volume_usd': 100000000, 'market_cap_usd': 3000000000,
            })
            print(f"    upsert_price_daily: {ok}")

            # Test macro
            print("\n  Testing macro upsert...")
            ok = wh.upsert_macro_daily(dt_date.today(), {
                'btc_price_usd': 70000, 'btc_dominance_pct': 54.2,
                'fear_greed_value': 25, 'fear_greed_label': 'Extreme Fear',
            })
            print(f"    upsert_macro_daily: {ok}")
    else:
        print("  Set SUPABASE_SERVICE_KEY to enable warehouse.")
    print("\nDone.")
