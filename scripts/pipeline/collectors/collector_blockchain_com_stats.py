"""
Blockchain.com Stats Collector
Collects Bitcoin network health metrics from Blockchain.com's public Stats API
(free, no auth required).

Source: https://api.blockchain.info
Category: onchain
CRO Quality Score: 93/100
Integrated: 2026-04-16
"""

import json
from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


class CollectorBlockchainComStats(BaseCollector):
    """Collector for Bitcoin network statistics from Blockchain.com."""

    BASE_URL = "https://api.blockchain.info"

    # Available chart names from Blockchain.com charts API
    KEY_CHARTS = [
        "hash-rate",
        "difficulty",
        "n-transactions",
        "mempool-size",
        "transaction-fees-usd",
        "market-price",
        "trade-volume",
        "miners-revenue",
    ]

    def collect_network_stats(self) -> Optional[Dict[str, Any]]:
        """Collect Bitcoin network summary stats."""
        cache_key = "blockchain_com_stats"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/stats")
        if not data:
            return None

        self._cache_set(cache_key, data, ttl=1800)
        return data

    def collect_chart(self, chart_name: str, timespan: str = "30days") -> Optional[List[Dict[str, Any]]]:
        """Collect a specific Bitcoin chart's time series data."""
        cache_key = f"blockchain_com_chart_{chart_name}_{timespan}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(
            f"{self.BASE_URL}/charts/{chart_name}",
            params={"timespan": timespan, "format": "json", "sampled": "true"}
        )
        if not data or not data.get("values"):
            return None

        values = data["values"]
        self._cache_set(cache_key, values, ttl=3600)
        return values

    def collect_mempool_stats(self) -> Optional[Dict[str, Any]]:
        """Collect Bitcoin mempool statistics."""
        cache_key = "blockchain_com_mempool"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/mempool/fees")
        if not data:
            return None

        self._cache_set(cache_key, data, ttl=600)  # 10 min TTL — mempool changes fast
        return data

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect Bitcoin network health data (most relevant for BTC reports,
        provides macro network context for other tokens).

        Args:
            token_id: CoinGecko-style token identifier (used for context; BTC data always collected)

        Returns:
            Network stats dict
        """
        print(f"  [Blockchain.com] Collecting Bitcoin network stats (context for {token_id})...")

        result = {
            "token_id": token_id,
            "source": "blockchain_com",
            "network_stats": None,
            "mempool": None,
            "charts": {},
        }

        # Core stats
        result["network_stats"] = self.collect_network_stats()
        result["mempool"] = self.collect_mempool_stats()

        # Key charts (hash rate, difficulty, fees)
        priority_charts = ["hash-rate", "difficulty", "transaction-fees-usd", "mempool-size"]
        for chart in priority_charts:
            chart_data = self.collect_chart(chart, "30days")
            if chart_data:
                result["charts"][chart] = chart_data[-7:]  # Last 7 data points

        has_data = sum(1 for k in ["network_stats", "mempool"] if result.get(k))
        has_data += len(result["charts"])
        print(f"    → Collected {has_data} Blockchain.com metrics")
        return result


if __name__ == "__main__":
    collector = CollectorBlockchainComStats()
    data = collector.collect("bitcoin")
    print(json.dumps(data, indent=2, default=str)[:2000])
