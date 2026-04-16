"""
DeFiLlama Stablecoins Collector
Collects stablecoin supply, peg stability, and chain distribution data
from DeFiLlama's Stablecoins API (free, no auth required).

Source: https://stablecoins.llama.fi
Category: defi
CRO Quality Score: 94/100
Integrated: 2026-04-16
"""

import json
from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


class CollectorDefiLlamaStablecoins(BaseCollector):
    """Collector for DeFiLlama stablecoin market data."""

    BASE_URL = "https://stablecoins.llama.fi"

    # Stablecoin pegged assets to highlight
    MAJOR_STABLECOINS = {"USDT", "USDC", "DAI", "FRAX", "BUSD", "TUSD", "USDP", "USDD", "GUSD", "LUSD"}

    def collect_stablecoins(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch all stablecoin data with supply and chain breakdown."""
        cache_key = "defillama_stablecoins_all"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/stablecoins", params={"includePrices": "true"})
        if not data or not data.get("peggedAssets"):
            return None

        stables = data["peggedAssets"]
        self._cache_set(cache_key, stables, ttl=1800)
        return stables

    def collect_stablecoin_charts(self) -> Optional[Dict[str, Any]]:
        """Fetch stablecoin aggregate chart data (total market cap over time)."""
        cache_key = "defillama_stablecoins_charts"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/stablecoincharts/all")
        if not data:
            return None

        # Return most recent 30 data points
        recent = data[-30:] if isinstance(data, list) else data
        self._cache_set(cache_key, recent, ttl=3600)
        return recent

    def collect_market_summary(self) -> Dict[str, Any]:
        """Aggregate stablecoin market overview."""
        stables = self.collect_stablecoins()
        if not stables:
            return {}

        total_mcap = sum(
            float(s.get("circulating", {}).get("peggedUSD", 0) or 0)
            for s in stables
        )
        major = [s for s in stables if s.get("symbol") in self.MAJOR_STABLECOINS]
        major_mcap = sum(
            float(s.get("circulating", {}).get("peggedUSD", 0) or 0)
            for s in major
        )

        peg_types = {}
        for s in stables:
            pt = s.get("pegType", "unknown")
            peg_types[pt] = peg_types.get(pt, 0) + 1

        # Top 10 by circulating supply
        top10 = sorted(
            stables,
            key=lambda x: float(x.get("circulating", {}).get("peggedUSD", 0) or 0),
            reverse=True
        )[:10]

        return {
            "total_stablecoin_mcap_usd": total_mcap,
            "major_stablecoin_mcap_usd": major_mcap,
            "stablecoin_count": len(stables),
            "peg_type_breakdown": peg_types,
            "top_stablecoins": [
                {
                    "name": s.get("name"),
                    "symbol": s.get("symbol"),
                    "mcap_usd": float(s.get("circulating", {}).get("peggedUSD", 0) or 0),
                    "peg_type": s.get("pegType"),
                    "chains": len(s.get("chainCirculating", {})),
                }
                for s in top10
            ],
        }

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect stablecoin market data (context for any token analysis).

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Stablecoin data dict
        """
        print(f"  [DeFiLlama Stablecoins] Collecting stablecoin data (context for {token_id})...")

        result = {
            "token_id": token_id,
            "source": "defillama_stablecoins",
            "market_summary": None,
            "recent_charts": None,
        }

        result["market_summary"] = self.collect_market_summary()
        result["recent_charts"] = self.collect_stablecoin_charts()

        has_data = sum(1 for k in ["market_summary", "recent_charts"] if result.get(k))
        print(f"    → Collected {has_data}/2 stablecoin metrics")
        return result


if __name__ == "__main__":
    collector = CollectorDefiLlamaStablecoins()
    data = collector.collect("usd-coin")
    print(json.dumps(data, indent=2, default=str)[:2000])
