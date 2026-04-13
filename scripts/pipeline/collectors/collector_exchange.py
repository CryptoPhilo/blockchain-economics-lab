"""
Exchange Data Collector - CoinGecko API
Rate limit: 10-30 requests/minute (free tier, no API key needed)

Collects:
- Market data (price, market cap, volume, changes)
- Price history
- OHLC (Open, High, Low, Close) candles
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_collector import BaseCollector


class CollectorExchange(BaseCollector):
    """Collector for exchange/market data with CoinGecko (primary) + CoinCap/CoinPaprika (fallback)."""

    BASE_URL = 'https://api.coingecko.com/api/v3'
    COINCAP_BASE_URL = 'https://api.coincap.io/v2'
    COINPAPRIKA_BASE_URL = 'https://api.coinpaprika.com/v1'
    RATE_LIMIT_SLEEP = 1  # Sleep between requests to respect rate limits

    def fetch_market_data(self, coingecko_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current market data with automatic fallback chain.
        Primary: CoinGecko → Fallback 1: CoinPaprika → Fallback 2: CoinCap
        """
        cache_key = f'market_data_{coingecko_id}'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        def _fallback_chain():
            """Try CoinPaprika first, then CoinCap."""
            result = self._fetch_market_coinpaprika(coingecko_id)
            if result:
                return result
            return self._fetch_market_coincap(coingecko_id)

        result = self._try_with_fallback(
            primary_fn=lambda: self._fetch_market_coingecko(coingecko_id),
            fallback_fn=_fallback_chain,
            metric_name='market_data',
            primary_label='CoinGecko',
            fallback_label='CoinPaprika/CoinCap',
        )
        if result:
            self._cache_set(cache_key, result, ttl=3600)
        return result

    def _fetch_market_coinpaprika(self, coingecko_id: str) -> Optional[Dict[str, Any]]:
        """Fallback: CoinPaprika /search + /tickers/{id}"""
        time.sleep(0.5)
        # Search for coin
        search_url = f'{self.COINPAPRIKA_BASE_URL}/search'
        search_data = self._request(search_url, params={'q': coingecko_id, 'limit': 1})
        paprika_id = None
        if search_data and search_data.get('currencies'):
            paprika_id = search_data['currencies'][0].get('id')
        if not paprika_id:
            return None

        url = f'{self.COINPAPRIKA_BASE_URL}/tickers/{paprika_id}'
        data = self._request(url)
        if not data:
            return None

        quotes = data.get('quotes', {}).get('USD', {})
        return {
            'current_price': quotes.get('price'),
            'market_cap': quotes.get('market_cap'),
            'volume_24h': quotes.get('volume_24h'),
            'price_change_24h_pct': quotes.get('percent_change_24h'),
            'price_change_7d_pct': quotes.get('percent_change_7d'),
            'price_change_30d_pct': quotes.get('percent_change_30d'),
            'ath': quotes.get('ath_price'),
            'atl': None,
            'circulating_supply': data.get('circulating_supply'),
            'total_supply': data.get('total_supply'),
            'fdv': None,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinPaprika (fallback)',
        }

    def _fetch_market_coingecko(self, coingecko_id: str) -> Optional[Dict[str, Any]]:
        """Primary: CoinGecko /coins/{id}"""
        url = f'{self.BASE_URL}/coins/{coingecko_id}'
        params = {
            'localization': 'false',
            'tickers': 'false',
            'community_data': 'false',
            'developer_data': 'false',
        }
        data = self._request(url, params=params)
        if not data:
            return None

        market_data = data.get('market_data', {})
        return {
            'current_price': market_data.get('current_price', {}).get('usd'),
            'market_cap': market_data.get('market_cap', {}).get('usd'),
            'volume_24h': market_data.get('total_volume', {}).get('usd'),
            'price_change_24h_pct': market_data.get('price_change_percentage_24h'),
            'price_change_7d_pct': market_data.get('price_change_percentage_7d'),
            'price_change_30d_pct': market_data.get('price_change_percentage_30d'),
            'ath': market_data.get('ath', {}).get('usd'),
            'atl': market_data.get('atl', {}).get('usd'),
            'circulating_supply': market_data.get('circulating_supply'),
            'total_supply': market_data.get('total_supply'),
            'fdv': market_data.get('fully_diluted_valuation', {}).get('usd'),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinGecko',
        }

    def _fetch_market_coincap(self, coingecko_id: str) -> Optional[Dict[str, Any]]:
        """Fallback: CoinCap /assets/{id}"""
        time.sleep(0.5)
        url = f'{self.COINCAP_BASE_URL}/assets/{coingecko_id}'
        data = self._request(url)
        if not data or 'data' not in data:
            # CoinCap IDs may differ — try search by symbol
            return self._fetch_market_coincap_search(coingecko_id)

        asset = data['data']
        price = float(asset.get('priceUsd', 0) or 0)
        mcap = float(asset.get('marketCapUsd', 0) or 0)
        vol = float(asset.get('volumeUsd24Hr', 0) or 0)
        chg24 = float(asset.get('changePercent24Hr', 0) or 0)
        supply = float(asset.get('supply', 0) or 0)
        max_supply = asset.get('maxSupply')
        if max_supply:
            max_supply = float(max_supply)

        return {
            'current_price': price,
            'market_cap': mcap,
            'volume_24h': vol,
            'price_change_24h_pct': chg24,
            'price_change_7d_pct': None,
            'price_change_30d_pct': None,
            'ath': None,
            'atl': None,
            'circulating_supply': supply,
            'total_supply': max_supply,
            'fdv': None,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinCap (fallback)',
        }

    def _fetch_market_coincap_search(self, query: str) -> Optional[Dict[str, Any]]:
        """Search CoinCap by name when direct ID fails."""
        url = f'{self.COINCAP_BASE_URL}/assets'
        params = {'search': query, 'limit': 1}
        data = self._request(url, params=params)
        if not data or not data.get('data'):
            return None
        asset = data['data'][0]
        price = float(asset.get('priceUsd', 0) or 0)
        mcap = float(asset.get('marketCapUsd', 0) or 0)
        vol = float(asset.get('volumeUsd24Hr', 0) or 0)
        chg24 = float(asset.get('changePercent24Hr', 0) or 0)
        return {
            'current_price': price,
            'market_cap': mcap,
            'volume_24h': vol,
            'price_change_24h_pct': chg24,
            'price_change_7d_pct': None,
            'price_change_30d_pct': None,
            'ath': None, 'atl': None,
            'circulating_supply': float(asset.get('supply', 0) or 0),
            'total_supply': None, 'fdv': None,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinCap (fallback)',
        }

    def fetch_price_history(
        self,
        coingecko_id: str,
        days: int = 90,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch historical price data with automatic fallback.
        Primary: CoinGecko → Fallback: CoinCap

        Args:
            coingecko_id: CoinGecko cryptocurrency ID
            days: Number of days of history to fetch (default: 90)

        Returns:
            Dict with 'data' list of {timestamp, price} dicts, or None on failure
        """
        cache_key = f'price_history_{coingecko_id}_{days}d'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        def _fallback_chain():
            result = self._fetch_price_history_coinpaprika(coingecko_id, days)
            if result:
                return result
            return self._fetch_price_history_coincap(coingecko_id, days)

        result = self._try_with_fallback(
            primary_fn=lambda: self._fetch_price_history_coingecko(coingecko_id, days),
            fallback_fn=_fallback_chain,
            metric_name='price_history',
            primary_label='CoinGecko',
            fallback_label='CoinPaprika/CoinCap',
        )
        if result:
            self._cache_set(cache_key, result, ttl=3600)
        return result

    def _fetch_price_history_coingecko(self, coingecko_id: str, days: int) -> Optional[Dict[str, Any]]:
        """Primary: CoinGecko /coins/{id}/market_chart"""
        time.sleep(self.RATE_LIMIT_SLEEP)
        url = f'{self.BASE_URL}/coins/{coingecko_id}/market_chart'
        params = {
            'vs_currency': 'usd',
            'days': days,
            'interval': 'daily',
        }
        data = self._request(url, params=params)
        if not data or 'prices' not in data:
            return None

        result = []
        for timestamp_ms, price in data['prices']:
            result.append({
                'timestamp': datetime.fromtimestamp(timestamp_ms / 1000).isoformat(),
                'price': price,
            })
        return {
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinGecko',
            'data': result,
        }

    def _fetch_price_history_coinpaprika(self, coingecko_id: str, days: int) -> Optional[Dict[str, Any]]:
        """Fallback: CoinPaprika /tickers/{id}/historical"""
        time.sleep(0.5)
        # Find CoinPaprika ID
        search_url = f'{self.COINPAPRIKA_BASE_URL}/search'
        search_data = self._request(search_url, params={'q': coingecko_id, 'limit': 1})
        paprika_id = None
        if search_data and search_data.get('currencies'):
            paprika_id = search_data['currencies'][0].get('id')
        if not paprika_id:
            return None

        # Get historical tickers
        from datetime import timedelta
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        url = f'{self.COINPAPRIKA_BASE_URL}/tickers/{paprika_id}/historical'
        params = {
            'start': start.strftime('%Y-%m-%dT00:00:00Z'),
            'interval': '1d',
            'limit': days + 1,
        }
        data = self._request(url, params=params)
        if not data or not isinstance(data, list) or not data:
            return None

        result = []
        for point in data:
            price = point.get('price', 0) or 0
            ts = point.get('timestamp', '')
            result.append({'timestamp': ts, 'price': price})

        if not result:
            return None
        return {
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinPaprika (fallback)',
            'data': result,
        }

    def _fetch_price_history_coincap(self, coingecko_id: str, days: int) -> Optional[Dict[str, Any]]:
        """Fallback: CoinCap /assets/{id}/history?interval=d1"""
        time.sleep(0.5)
        # Calculate start/end timestamps in milliseconds
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - (days * 86400 * 1000)

        url = f'{self.COINCAP_BASE_URL}/assets/{coingecko_id}/history'
        params = {
            'interval': 'd1',
            'start': start_ms,
            'end': end_ms,
        }
        data = self._request(url, params=params)
        if not data or 'data' not in data or not data['data']:
            # Try search if direct ID fails
            return self._fetch_price_history_coincap_search(coingecko_id, days)

        result = []
        for point in data['data']:
            price = float(point.get('priceUsd', 0) or 0)
            ts = point.get('time') or point.get('date')
            if ts and isinstance(ts, (int, float)):
                ts_iso = datetime.fromtimestamp(ts / 1000).isoformat()
            elif ts:
                ts_iso = ts
            else:
                continue
            result.append({'timestamp': ts_iso, 'price': price})

        if not result:
            return None
        return {
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinCap (fallback)',
            'data': result,
        }

    def _fetch_price_history_coincap_search(self, query: str, days: int) -> Optional[Dict[str, Any]]:
        """Search CoinCap for asset ID then fetch history."""
        url = f'{self.COINCAP_BASE_URL}/assets'
        params = {'search': query, 'limit': 1}
        data = self._request(url, params=params)
        if not data or not data.get('data'):
            return None
        asset_id = data['data'][0].get('id')
        if not asset_id:
            return None

        end_ms = int(time.time() * 1000)
        start_ms = end_ms - (days * 86400 * 1000)
        hist_url = f'{self.COINCAP_BASE_URL}/assets/{asset_id}/history'
        hist_params = {'interval': 'd1', 'start': start_ms, 'end': end_ms}
        hist_data = self._request(hist_url, params=hist_params)
        if not hist_data or 'data' not in hist_data or not hist_data['data']:
            return None

        result = []
        for point in hist_data['data']:
            price = float(point.get('priceUsd', 0) or 0)
            ts = point.get('time') or point.get('date')
            if ts and isinstance(ts, (int, float)):
                ts_iso = datetime.fromtimestamp(ts / 1000).isoformat()
            elif ts:
                ts_iso = ts
            else:
                continue
            result.append({'timestamp': ts_iso, 'price': price})

        if not result:
            return None
        return {
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinCap (fallback)',
            'data': result,
        }

    def fetch_ohlc(
        self,
        coingecko_id: str,
        days: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch OHLC candlestick data with automatic fallback.
        Primary: CoinGecko → Fallback: CoinCap (synthesized from daily history)

        Args:
            coingecko_id: CoinGecko cryptocurrency ID
            days: Number of days (default: 30, max: 90)

        Returns:
            Dict with 'data' list of {timestamp, open, high, low, close} dicts, or None
        """
        days = min(days, 90)
        cache_key = f'ohlc_{coingecko_id}_{days}d'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        result = self._try_with_fallback(
            primary_fn=lambda: self._fetch_ohlc_coingecko(coingecko_id, days),
            fallback_fn=lambda: self._fetch_ohlc_from_history(coingecko_id, days),
            metric_name='ohlc',
            primary_label='CoinGecko',
            fallback_label='CoinCap (synthesized)',
        )
        if result:
            self._cache_set(cache_key, result, ttl=3600)
        return result

    def _fetch_ohlc_coingecko(self, coingecko_id: str, days: int) -> Optional[Dict[str, Any]]:
        """Primary: CoinGecko /coins/{id}/ohlc"""
        time.sleep(self.RATE_LIMIT_SLEEP)
        url = f'{self.BASE_URL}/coins/{coingecko_id}/ohlc'
        params = {'vs_currency': 'usd', 'days': days}
        data = self._request(url, params=params)
        if not data or not isinstance(data, list):
            return None

        result = []
        for candle in data:
            if len(candle) >= 5:
                result.append({
                    'timestamp': datetime.fromtimestamp(candle[0] / 1000).isoformat(),
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                })
        if not result:
            return None
        return {
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinGecko',
            'data': result,
        }

    def _fetch_ohlc_from_history(self, coingecko_id: str, days: int) -> Optional[Dict[str, Any]]:
        """
        Fallback: Synthesize OHLC from CoinCap daily price history.
        CoinCap doesn't have native OHLC, so we use daily prices as open=close=price, high=low=price.
        This gives approximate daily candles.
        """
        history = self._fetch_price_history_coincap(coingecko_id, days)
        if not history or not history.get('data'):
            return None

        result = []
        for point in history['data']:
            price = point.get('price', 0)
            result.append({
                'timestamp': point['timestamp'],
                'open': price,
                'high': price,
                'low': price,
                'close': price,
            })
        if not result:
            return None
        return {
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinCap (synthesized fallback)',
            'data': result,
        }


if __name__ == '__main__':
    print("Testing CollectorExchange with Uniswap (UNI)...")
    collector = CollectorExchange()

    # Test market data
    print("\n1. Fetching market data for Uniswap...")
    market = collector.fetch_market_data('uniswap')
    if market:
        print(f"   Current price: ${market.get('current_price')}")
        print(f"   Market cap: ${market.get('market_cap')}")
        print(f"   24h change: {market.get('price_change_24h_pct')}%")
        print(f"   Source: {market.get('source')}")
    else:
        print("   Failed to fetch market data")

    # Test price history
    print("\n2. Fetching 30-day price history...")
    history = collector.fetch_price_history('uniswap', days=30)
    if history:
        print(f"   Total data points: {len(history.get('data', []))}")
        if history.get('data'):
            print(f"   First: {history['data'][0]}")
            print(f"   Last: {history['data'][-1]}")
    else:
        print("   Failed to fetch price history")

    # Test OHLC
    print("\n3. Fetching 7-day OHLC data...")
    ohlc = collector.fetch_ohlc('uniswap', days=7)
    if ohlc:
        print(f"   Total candles: {len(ohlc.get('data', []))}")
        if ohlc.get('data'):
            print(f"   Latest candle: {ohlc['data'][-1]}")
    else:
        print("   Failed to fetch OHLC data")

    print("\nCollectorExchange test complete!")
