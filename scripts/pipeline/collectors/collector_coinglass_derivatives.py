"""
CoinGlass Derivatives Collector
Collects futures open interest, funding rates, and liquidation data
from CoinGlass public API (free tier, no auth required).

Source: https://open-api.coinglass.com/public/v2
Category: derivatives
CRO Quality Score: 76/100
Integrated: 2026-04-13
"""

from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


class CollectorCoinglassDerivatives(BaseCollector):
    """Collector for CoinGlass derivatives data (open interest, funding rates)."""

    BASE_URL = "https://open-api.coinglass.com/public/v2"

    # Token symbol mapping for CoinGlass API
    SYMBOL_MAP = {
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
    }

    def __init__(self):
        super().__init__()

    def _get_symbol(self, token_id: str) -> str:
        """Convert CoinGecko-style token ID to CoinGlass symbol."""
        return self.SYMBOL_MAP.get(token_id, token_id.upper())

    def collect_funding_rates(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Collect current funding rates for a token across exchanges.

        Args:
            token_id: CoinGecko-style token identifier (e.g., 'bitcoin')

        Returns:
            Dict with funding rate data or None on failure
        """
        symbol = self._get_symbol(token_id)
        cache_key = f"coinglass_funding_{symbol}"

        # Check cache first (15 min TTL for funding rates)
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        url = f"{self.BASE_URL}/funding"
        data = self._request(url, params={"symbol": symbol})

        if data and data.get("success") and data.get("data"):
            result = {
                "symbol": symbol,
                "funding_rates": data["data"],
                "source": "coinglass",
                "data_type": "funding_rates",
            }
            self._cache_set(cache_key, result, ttl=900)  # 15 min
            return result
        return None

    def collect_open_interest(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Collect aggregated open interest for a token.

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Dict with open interest data or None on failure
        """
        symbol = self._get_symbol(token_id)
        cache_key = f"coinglass_oi_{symbol}"

        cached = self._cache_get(cache_key)
        if cached:
            return cached

        url = f"{self.BASE_URL}/open_interest"
        data = self._request(url, params={"symbol": symbol})

        if data and data.get("success") and data.get("data"):
            result = {
                "symbol": symbol,
                "open_interest": data["data"],
                "source": "coinglass",
                "data_type": "open_interest",
            }
            self._cache_set(cache_key, result, ttl=900)
            return result
        return None

    def collect_liquidations(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Collect recent liquidation data for a token.

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Dict with liquidation data or None on failure
        """
        symbol = self._get_symbol(token_id)
        cache_key = f"coinglass_liq_{symbol}"

        cached = self._cache_get(cache_key)
        if cached:
            return cached

        url = f"{self.BASE_URL}/liquidation"
        data = self._request(url, params={"symbol": symbol})

        if data and data.get("success") and data.get("data"):
            result = {
                "symbol": symbol,
                "liquidations": data["data"],
                "source": "coinglass",
                "data_type": "liquidations",
            }
            self._cache_set(cache_key, result, ttl=900)
            return result
        return None

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect all derivatives data for a token.

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Combined derivatives data dict
        """
        symbol = self._get_symbol(token_id)
        print(f"  [CoinGlass] Collecting derivatives data for {symbol}...")

        result = {
            "symbol": symbol,
            "source": "coinglass",
            "funding_rates": None,
            "open_interest": None,
            "liquidations": None,
        }

        funding = self.collect_funding_rates(token_id)
        if funding:
            result["funding_rates"] = funding.get("funding_rates")

        oi = self.collect_open_interest(token_id)
        if oi:
            result["open_interest"] = oi.get("open_interest")

        liq = self.collect_liquidations(token_id)
        if liq:
            result["liquidations"] = liq.get("liquidations")

        collected = sum(1 for v in [result["funding_rates"], result["open_interest"], result["liquidations"]] if v)
        print(f"    → Collected {collected}/3 derivatives metrics for {symbol}")

        return result


if __name__ == "__main__":
    collector = CollectorCoinglassDerivatives()
    data = collector.collect("bitcoin")
    import json
    print(json.dumps(data, indent=2, default=str)[:2000])
