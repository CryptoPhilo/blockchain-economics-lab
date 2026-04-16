"""
Augmento Sentiment Collector
Collects AI-powered crypto sentiment scores from X (Twitter), Reddit,
and Bitcointalk via Augmento's public REST API.
Free endpoints available without authentication (limited to 30-day lag).

Source: https://api.augmento.ai/v0.1
Category: social
CRO Quality Score: 81/100
Integrated: 2026-04-16
"""

import json
from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


# Augmento coin identifiers (from /v0.1/coins endpoint)
TOKEN_COIN_MAP = {
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
    "maker": "MKR",
    "litecoin": "LTC",
    "dogecoin": "DOGE",
}


class CollectorAugmentoSentiment(BaseCollector):
    """Collector for Augmento AI-powered social sentiment data."""

    BASE_URL = "https://api.augmento.ai/v0.1"

    # Sentiment categories tracked by Augmento
    SENTIMENT_CATEGORIES = [
        "Bearish", "Bullish", "Fear", "Optimistic", "Pessimistic",
        "Price increase", "Price decrease", "Hype", "FUD",
        "Technical analysis", "Fundamental analysis"
    ]

    def collect_coins(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch list of supported coins."""
        cache_key = "augmento_coins"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/coins")
        if not data:
            return None

        self._cache_set(cache_key, data, ttl=86400)  # 24hr — rarely changes
        return data

    def collect_sentiment_aggregate(self, coin: str, bin_size: str = "day", limit: int = 30) -> Optional[List[Dict[str, Any]]]:
        """
        Collect sentiment time series for a coin.

        Args:
            coin: Augmento coin symbol (e.g. "BTC")
            bin_size: Aggregation window — "hour", "day", "week"
            limit: Number of periods to return

        Returns:
            List of sentiment data points
        """
        cache_key = f"augmento_sentiment_{coin}_{bin_size}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/events/aggregate/{coin}",
            params={"bin_size": bin_size, "limit": limit}
        )
        if not data:
            return None

        self._cache_set(cache_key, data, ttl=3600)
        return data

    def collect_bull_bear_index(self, coin: str) -> Optional[Dict[str, Any]]:
        """Collect Bull & Bear index for a coin (Augmento's headline metric)."""
        cache_key = f"augmento_bb_{coin}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/events/aggregate/{coin}", params={"bin_size": "day", "limit": 1})
        if not data or not isinstance(data, list) or not data:
            return None

        latest = data[-1] if data else None
        if not latest:
            return None

        result = {
            "coin": coin,
            "timestamp": latest.get("timestamp"),
            "bullish_score": latest.get("Bullish", 0),
            "bearish_score": latest.get("Bearish", 0),
            "bull_bear_ratio": (
                latest.get("Bullish", 0) / max(latest.get("Bearish", 1), 1)
            ),
            "total_mentions": latest.get("total", 0),
        }

        self._cache_set(cache_key, result, ttl=3600)
        return result

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect social sentiment data for a token.

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Sentiment data dict
        """
        coin = TOKEN_COIN_MAP.get(token_id)
        print(f"  [Augmento] Collecting sentiment for {token_id} (symbol={coin})...")

        result = {
            "token_id": token_id,
            "source": "augmento",
            "coin_symbol": coin,
            "supported": coin is not None,
            "bull_bear_index": None,
            "sentiment_30d": None,
        }

        if not coin:
            print(f"    → No Augmento mapping for {token_id}")
            # Still return market-level coins list as context
            result["supported_coins"] = self.collect_coins()
            return result

        result["bull_bear_index"] = self.collect_bull_bear_index(coin)
        result["sentiment_30d"] = self.collect_sentiment_aggregate(coin, "day", 30)

        has_data = sum(1 for k in ["bull_bear_index", "sentiment_30d"] if result.get(k))
        print(f"    → Collected {has_data}/2 sentiment metrics")
        return result


if __name__ == "__main__":
    collector = CollectorAugmentoSentiment()
    data = collector.collect("bitcoin")
    print(json.dumps(data, indent=2, default=str)[:2000])
