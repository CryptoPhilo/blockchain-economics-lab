"""
CryptoCompare Collector
Collects market OHLCV, social stats, and volume-by-exchange data from
CryptoCompare's free API tier (no API key required for most endpoints).

Source: https://min-api.cryptocompare.com/data
Category: market_data
CRO Quality Score: 93/100
Integrated: 2026-04-16
"""

import json
from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


# CoinGecko token_id → CryptoCompare symbol mapping
TOKEN_SYMBOL_MAP = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
    "ripple": "XRP",
    "cardano": "ADA",
    "avalanche-2": "AVAX",
    "polkadot": "DOT",
    "chainlink": "LINK",
    "polygon": "MATIC",
    "uniswap": "UNI",
    "aave": "AAVE",
    "compound-governance-token": "COMP",
    "curve-dao-token": "CRV",
    "maker": "MKR",
    "lido-dao": "LDO",
    "arbitrum": "ARB",
    "optimism": "OP",
}


class CollectorCryptoCompare(BaseCollector):
    """Collector for CryptoCompare market and social data."""

    BASE_URL = "https://min-api.cryptocompare.com/data"

    def _symbol(self, token_id: str) -> str:
        return TOKEN_SYMBOL_MAP.get(token_id, token_id.upper())

    def collect_ohlcv_daily(self, token_id: str, limit: int = 30) -> Optional[List[Dict[str, Any]]]:
        """Collect daily OHLCV candles for a token (last N days)."""
        symbol = self._symbol(token_id)
        cache_key = f"cc_ohlcv_{symbol}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/v2/histoday",
            params={"fsym": symbol, "tsym": "USD", "limit": limit}
        )
        if not data or data.get("Response") != "Success":
            return None

        candles = data.get("Data", {}).get("Data", [])
        self._cache_set(cache_key, candles, ttl=3600)
        return candles

    def collect_social_stats(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Collect social stats (Reddit, Twitter, GitHub activity) for a token."""
        symbol = self._symbol(token_id)
        cache_key = f"cc_social_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/social/coin/latest",
            params={"coinId": symbol}
        )
        if not data or data.get("Response") != "Success":
            return None

        result = data.get("Data", {})
        self._cache_set(cache_key, result, ttl=3600)
        return result

    def collect_top_volume_exchanges(self, token_id: str) -> Optional[List[Dict[str, Any]]]:
        """Collect top exchanges by volume for a token."""
        symbol = self._symbol(token_id)
        cache_key = f"cc_exchanges_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/top/exchanges",
            params={"fsym": symbol, "tsym": "USD", "limit": 10}
        )
        if not data or data.get("Response") != "Success":
            return None

        exchanges = data.get("Data", [])
        self._cache_set(cache_key, exchanges, ttl=3600)
        return exchanges

    def collect_global_top_volume(self) -> Optional[List[Dict[str, Any]]]:
        """Collect top coins by total volume (market overview)."""
        cache_key = "cc_global_top_volume"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/top/totaltoptiervolfull",
            params={"limit": 20, "tsym": "USD"}
        )
        if not data or data.get("Response") != "Success":
            return None

        coins = data.get("Data", [])
        self._cache_set(cache_key, coins, ttl=1800)
        return coins

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect CryptoCompare market and social data for a token.

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Market data dict with OHLCV, social, exchange breakdown
        """
        print(f"  [CryptoCompare] Collecting market data for {token_id}...")

        result = {
            "token_id": token_id,
            "source": "cryptocompare",
            "symbol": self._symbol(token_id),
            "ohlcv_30d": None,
            "social_stats": None,
            "top_exchanges": None,
            "global_top_volume": None,
        }

        result["ohlcv_30d"] = self.collect_ohlcv_daily(token_id, 30)
        result["social_stats"] = self.collect_social_stats(token_id)
        result["top_exchanges"] = self.collect_top_volume_exchanges(token_id)
        result["global_top_volume"] = self.collect_global_top_volume()

        has_data = sum(1 for k in ["ohlcv_30d", "social_stats", "top_exchanges", "global_top_volume"] if result.get(k))
        print(f"    → Collected {has_data}/4 CryptoCompare metrics")
        return result


if __name__ == "__main__":
    collector = CollectorCryptoCompare()
    data = collector.collect("bitcoin")
    print(json.dumps(data, indent=2, default=str)[:2000])
