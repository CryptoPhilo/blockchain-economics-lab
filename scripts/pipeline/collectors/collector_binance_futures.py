"""
Binance Futures Collector
Collects open interest, funding rates, liquidation data, and long/short
ratios from Binance's public FAPI endpoints (free, no auth required for
market data).

Source: https://fapi.binance.com
Category: derivatives
CRO Quality Score: 79/100
Integrated: 2026-04-16
"""

import json
from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


# CoinGecko token_id → Binance USDT-M perpetual symbol mapping
TOKEN_SYMBOL_MAP = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "solana": "SOLUSDT",
    "binancecoin": "BNBUSDT",
    "ripple": "XRPUSDT",
    "cardano": "ADAUSDT",
    "avalanche-2": "AVAXUSDT",
    "polkadot": "DOTUSDT",
    "chainlink": "LINKUSDT",
    "polygon": "MATICUSDT",
    "uniswap": "UNIUSDT",
    "aave": "AAVEUSDT",
    "doge": "DOGEUSDT",
    "litecoin": "LTCUSDT",
    "arbitrum": "ARBUSDT",
    "optimism": "OPUSDT",
    "aptos": "APTUSDT",
    "sui": "SUIUSDT",
}


class CollectorBinanceFutures(BaseCollector):
    """Collector for Binance USDT-M perpetual futures market data."""

    BASE_URL = "https://fapi.binance.com"

    def collect_open_interest(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Collect current open interest for a perpetual futures contract."""
        symbol = TOKEN_SYMBOL_MAP.get(token_id)
        if not symbol:
            return None

        cache_key = f"binance_oi_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/fapi/v1/openInterest",
            params={"symbol": symbol}
        )
        if not data:
            return None

        self._cache_set(cache_key, data, ttl=300)  # 5 min — frequently changing
        return data

    def collect_open_interest_hist(self, token_id: str, period: str = "4h", limit: int = 42) -> Optional[List[Dict[str, Any]]]:
        """Collect historical open interest (7 day = 42 × 4h periods)."""
        symbol = TOKEN_SYMBOL_MAP.get(token_id)
        if not symbol:
            return None

        cache_key = f"binance_oi_hist_{symbol}_{period}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/futures/data/openInterestHist",
            params={"symbol": symbol, "period": period, "limit": limit}
        )
        if not data:
            return None

        self._cache_set(cache_key, data, ttl=3600)
        return data

    def collect_funding_rate(self, token_id: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Collect recent funding rate history for a contract."""
        symbol = TOKEN_SYMBOL_MAP.get(token_id)
        if not symbol:
            return None

        cache_key = f"binance_funding_{symbol}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/fapi/v1/fundingRate",
            params={"symbol": symbol, "limit": limit}
        )
        if not data:
            return None

        self._cache_set(cache_key, data, ttl=1800)
        return data

    def collect_long_short_ratio(self, token_id: str, period: str = "4h", limit: int = 30) -> Optional[List[Dict[str, Any]]]:
        """Collect global long/short position ratio."""
        symbol = TOKEN_SYMBOL_MAP.get(token_id)
        if not symbol:
            return None

        cache_key = f"binance_lsr_{symbol}_{period}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/futures/data/globalLongShortAccountRatio",
            params={"symbol": symbol, "period": period, "limit": limit}
        )
        if not data:
            return None

        self._cache_set(cache_key, data, ttl=3600)
        return data

    def collect_market_overview(self) -> Optional[List[Dict[str, Any]]]:
        """Collect top perpetual futures by open interest (market-wide view)."""
        cache_key = "binance_futures_ticker_all"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/fapi/v1/ticker/24hr")
        if not data:
            return None

        # Filter USDT pairs and sort by quote volume
        usdt = [t for t in data if str(t.get("symbol", "")).endswith("USDT")]
        usdt.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        top20 = usdt[:20]

        self._cache_set(cache_key, top20, ttl=300)
        return top20

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect Binance futures derivatives data for a token.

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Derivatives data dict with OI, funding rates, long/short ratio
        """
        symbol = TOKEN_SYMBOL_MAP.get(token_id)
        print(f"  [Binance Futures] Collecting derivatives data for {token_id} (symbol={symbol})...")

        result = {
            "token_id": token_id,
            "source": "binance_futures",
            "symbol": symbol,
            "open_interest": None,
            "oi_history_7d": None,
            "funding_rates": None,
            "long_short_ratio": None,
            "market_overview": None,
        }

        if symbol:
            result["open_interest"] = self.collect_open_interest(token_id)
            result["oi_history_7d"] = self.collect_open_interest_hist(token_id)
            result["funding_rates"] = self.collect_funding_rate(token_id)
            result["long_short_ratio"] = self.collect_long_short_ratio(token_id)

        result["market_overview"] = self.collect_market_overview()

        has_data = sum(1 for k in ["open_interest", "oi_history_7d", "funding_rates", "long_short_ratio", "market_overview"] if result.get(k))
        print(f"    → Collected {has_data}/5 derivatives metrics")
        return result


if __name__ == "__main__":
    collector = CollectorBinanceFutures()
    data = collector.collect("bitcoin")
    print(json.dumps(data, indent=2, default=str)[:2000])
