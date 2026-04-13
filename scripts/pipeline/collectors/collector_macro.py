"""
Macro Market Data Collector
Collects global cryptocurrency market data and sentiment indicators:
- Global market cap and volume
- Bitcoin dominance
- Fear & Greed Index
- Bitcoin price
"""

import time
from datetime import datetime
from typing import Any, Dict, Optional

from .base_collector import BaseCollector


class CollectorMacro(BaseCollector):
    """Collector for macro-level cryptocurrency market data with CoinGecko (primary) + CoinCap/CoinPaprika (fallback)."""

    COINGECKO_BASE_URL = 'https://api.coingecko.com/api/v3'
    COINCAP_BASE_URL = 'https://api.coincap.io/v2'
    COINPAPRIKA_BASE_URL = 'https://api.coinpaprika.com/v1'
    FEAR_GREED_URL = 'https://api.alternative.me/fng/'
    RATE_LIMIT_SLEEP = 1

    def fetch_global_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch global cryptocurrency market data with automatic fallback.
        Primary: CoinGecko → Fallback: CoinPaprika
        """
        cache_key = 'global_market_data'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        result = self._try_with_fallback(
            primary_fn=self._fetch_global_coingecko,
            fallback_fn=self._fetch_global_coinpaprika,
            metric_name='global_data',
            primary_label='CoinGecko',
            fallback_label='CoinPaprika',
        )
        if result:
            self._cache_set(cache_key, result, ttl=3600)
        return result

    def _fetch_global_coingecko(self) -> Optional[Dict[str, Any]]:
        """Primary: CoinGecko /global"""
        time.sleep(self.RATE_LIMIT_SLEEP)
        url = f'{self.COINGECKO_BASE_URL}/global'
        data = self._request(url)
        if not data:
            return None
        data_field = data.get('data', {})
        return {
            'total_market_cap': data_field.get('total_market_cap', {}).get('usd'),
            'total_volume_24h': data_field.get('total_volume', {}).get('usd'),
            'btc_dominance': data_field.get('btc_dominance'),
            'active_cryptocurrencies': data_field.get('active_cryptocurrencies'),
            'market_cap_change_24h': data_field.get('market_cap_change_percentage_24h_usd'),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinGecko',
        }

    def _fetch_global_coinpaprika(self) -> Optional[Dict[str, Any]]:
        """Fallback: CoinPaprika /global"""
        time.sleep(0.5)
        url = f'{self.COINPAPRIKA_BASE_URL}/global'
        data = self._request(url)
        if not data:
            return None
        return {
            'total_market_cap': data.get('market_cap_usd'),
            'total_volume_24h': data.get('volume_24h_usd'),
            'btc_dominance': data.get('bitcoin_dominance_percentage'),
            'active_cryptocurrencies': data.get('cryptocurrencies_number'),
            'market_cap_change_24h': data.get('market_cap_ath_value'),  # approximate
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinPaprika (fallback)',
        }

    def fetch_fear_greed(self) -> Optional[Dict[str, Any]]:
        """
        Fetch Fear & Greed Index from Alternative.me.
        No direct fallback API — uses CoinCap BTC 24h change as proxy if primary fails.
        """
        cache_key = 'fear_greed_index'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        def _fallback_chain():
            result = self._estimate_fear_greed_from_coinpaprika()
            if result:
                return result
            return self._estimate_fear_greed_from_btc()

        result = self._try_with_fallback(
            primary_fn=self._fetch_fear_greed_alternative,
            fallback_fn=_fallback_chain,
            metric_name='fear_greed',
            primary_label='Alternative.me',
            fallback_label='CoinPaprika/CoinCap BTC proxy',
        )
        if result:
            self._cache_set(cache_key, result, ttl=3600)
        return result

    def _fetch_fear_greed_alternative(self) -> Optional[Dict[str, Any]]:
        """Primary: Alternative.me Fear & Greed Index"""
        time.sleep(self.RATE_LIMIT_SLEEP)
        data = self._request(self.FEAR_GREED_URL)
        if not data:
            return None
        fg_data = data.get('data', [{}])[0]
        index_value = float(fg_data.get('value', 50))
        classification = self._classify_fear_greed(index_value)
        return {
            'fear_greed_index': index_value,
            'classification': classification,
            'timestamp': fg_data.get('timestamp'),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'Alternative.me',
        }

    def _estimate_fear_greed_from_coinpaprika(self) -> Optional[Dict[str, Any]]:
        """Fallback: Estimate fear/greed from BTC 24h change via CoinPaprika."""
        time.sleep(0.5)
        url = f'{self.COINPAPRIKA_BASE_URL}/tickers/btc-bitcoin'
        data = self._request(url)
        if not data:
            return None
        quotes = data.get('quotes', {}).get('USD', {})
        chg = quotes.get('percent_change_24h', 0) or 0
        clamped = max(-10.0, min(10.0, chg))
        index_value = round((clamped + 10) * 5, 1)
        classification = self._classify_fear_greed(index_value)
        return {
            'fear_greed_index': index_value,
            'classification': classification,
            'timestamp': None,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinPaprika BTC proxy (fallback)',
        }

    def _estimate_fear_greed_from_btc(self) -> Optional[Dict[str, Any]]:
        """
        Fallback: Estimate fear/greed from BTC 24h change (CoinCap).
        Simple heuristic: map BTC change % to 0-100 scale.
        """
        time.sleep(0.5)
        url = f'{self.COINCAP_BASE_URL}/assets/bitcoin'
        data = self._request(url)
        if not data or 'data' not in data:
            return None
        chg = float(data['data'].get('changePercent24Hr', 0) or 0)
        # Heuristic: clamp to [-10, +10] range, map to [0, 100]
        clamped = max(-10.0, min(10.0, chg))
        index_value = round((clamped + 10) * 5, 1)  # -10→0, 0→50, +10→100
        classification = self._classify_fear_greed(index_value)
        return {
            'fear_greed_index': index_value,
            'classification': classification,
            'timestamp': None,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinCap BTC proxy (fallback)',
        }

    @staticmethod
    def _classify_fear_greed(value: float) -> str:
        """Classify fear/greed index value."""
        if value < 20:
            return 'Extreme Fear'
        elif value < 40:
            return 'Fear'
        elif value < 60:
            return 'Neutral'
        elif value < 80:
            return 'Greed'
        return 'Extreme Greed'

    def fetch_btc_price(self) -> Optional[Dict[str, Any]]:
        """
        Fetch current Bitcoin price with automatic fallback.
        Primary: CoinGecko → Fallback: CoinCap
        """
        cache_key = 'btc_price'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        def _fallback_chain():
            result = self._fetch_btc_coinpaprika()
            if result:
                return result
            return self._fetch_btc_coincap()

        result = self._try_with_fallback(
            primary_fn=self._fetch_btc_coingecko,
            fallback_fn=_fallback_chain,
            metric_name='btc_price',
            primary_label='CoinGecko',
            fallback_label='CoinPaprika/CoinCap',
        )
        if result:
            self._cache_set(cache_key, result, ttl=3600)
        return result

    def _fetch_btc_coingecko(self) -> Optional[Dict[str, Any]]:
        """Primary: CoinGecko /simple/price for BTC"""
        time.sleep(self.RATE_LIMIT_SLEEP)
        url = f'{self.COINGECKO_BASE_URL}/simple/price'
        params = {
            'ids': 'bitcoin',
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
        }
        data = self._request(url, params=params)
        if not data or 'bitcoin' not in data:
            return None
        btc_data = data['bitcoin']
        return {
            'btc_price': btc_data.get('usd'),
            'btc_24h_change': btc_data.get('usd_24h_change'),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinGecko',
        }

    def _fetch_btc_coinpaprika(self) -> Optional[Dict[str, Any]]:
        """Fallback: CoinPaprika /tickers/btc-bitcoin"""
        time.sleep(0.5)
        url = f'{self.COINPAPRIKA_BASE_URL}/tickers/btc-bitcoin'
        data = self._request(url)
        if not data:
            return None
        quotes = data.get('quotes', {}).get('USD', {})
        return {
            'btc_price': quotes.get('price', 0),
            'btc_24h_change': quotes.get('percent_change_24h', 0),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinPaprika (fallback)',
        }

    def _fetch_btc_coincap(self) -> Optional[Dict[str, Any]]:
        """Fallback: CoinCap /assets/bitcoin"""
        time.sleep(0.5)
        url = f'{self.COINCAP_BASE_URL}/assets/bitcoin'
        data = self._request(url)
        if not data or 'data' not in data:
            return None
        asset = data['data']
        return {
            'btc_price': float(asset.get('priceUsd', 0) or 0),
            'btc_24h_change': float(asset.get('changePercent24Hr', 0) or 0),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinCap (fallback)',
        }


if __name__ == '__main__':
    print("Testing CollectorMacro...")
    collector = CollectorMacro()

    # Test global data
    print("\n1. Fetching global market data...")
    global_data = collector.fetch_global_data()
    if global_data:
        print(f"   Total market cap: ${global_data.get('total_market_cap'):,.0f}")
        print(f"   Total 24h volume: ${global_data.get('total_volume_24h'):,.0f}")
        btc_dom = global_data.get('btc_dominance')
        if btc_dom is not None:
            print(f"   BTC dominance: {btc_dom:.2f}%")
        print(f"   Active cryptocurrencies: {global_data.get('active_cryptocurrencies')}")
        market_change = global_data.get('market_cap_change_24h')
        if market_change is not None:
            print(f"   24h change: {market_change:.2f}%")
        print(f"   Source: {global_data.get('source')}")
    else:
        print("   Failed to fetch global data")

    # Test fear & greed
    print("\n2. Fetching Fear & Greed Index...")
    fear_greed = collector.fetch_fear_greed()
    if fear_greed:
        print(f"   Index value: {fear_greed.get('fear_greed_index'):.1f}")
        print(f"   Classification: {fear_greed.get('classification')}")
        print(f"   Source: {fear_greed.get('source')}")
    else:
        print("   Failed to fetch Fear & Greed Index")

    # Test Bitcoin price
    print("\n3. Fetching Bitcoin price...")
    btc = collector.fetch_btc_price()
    if btc:
        print(f"   BTC price: ${btc.get('btc_price'):,.2f}")
        print(f"   24h change: {btc.get('btc_24h_change'):.2f}%")
        print(f"   Source: {btc.get('source')}")
    else:
        print("   Failed to fetch BTC price")

    print("\nCollectorMacro test complete!")
