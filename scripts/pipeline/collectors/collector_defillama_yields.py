"""
DeFiLlama Yields Collector
Collects DeFi yield/APY pool data from DeFiLlama's Yields API (free, no auth).

Source: https://yields.llama.fi
Category: defi
CRO Quality Score: 87/100
Integrated: 2026-04-16
"""

import json
from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


class CollectorDefiLlamaYields(BaseCollector):
    """Collector for DeFiLlama yield pool data."""

    BASE_URL = "https://yields.llama.fi"

    # Chain filter — limit to major chains for relevance
    TARGET_CHAINS = {"Ethereum", "Arbitrum", "Optimism", "Polygon", "Base", "BNB Chain", "Solana"}

    def collect_top_pools(self, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """Collect top yield pools by TVL."""
        cache_key = f"defillama_yields_pools_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/pools")
        if not data or not data.get("data"):
            return None

        pools = data["data"]
        # Filter to target chains and sort by TVL
        filtered = [p for p in pools if p.get("chain") in self.TARGET_CHAINS]
        filtered.sort(key=lambda x: x.get("tvlUsd", 0), reverse=True)
        top = filtered[:limit]

        self._cache_set(cache_key, top, ttl=3600)
        return top

    def collect_project_yields(self, project: str) -> Optional[List[Dict[str, Any]]]:
        """Collect yield pools for a specific DeFi project."""
        cache_key = f"defillama_yields_project_{project}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = self._request(f"{self.BASE_URL}/pools")
        if not data or not data.get("data"):
            return None

        pools = [p for p in data["data"] if p.get("project", "").lower() == project.lower()]
        self._cache_set(cache_key, pools, ttl=3600)
        return pools

    def collect_market_summary(self) -> Dict[str, Any]:
        """Aggregate yield market overview."""
        pools = self.collect_top_pools(200)
        if not pools:
            return {}

        total_tvl = sum(p.get("tvlUsd", 0) for p in pools)
        avg_apy = (
            sum(p.get("apy", 0) for p in pools if p.get("apy")) / len([p for p in pools if p.get("apy")])
            if any(p.get("apy") for p in pools)
            else 0
        )
        stablecoin_pools = [p for p in pools if p.get("stablecoin")]
        chain_breakdown = {}
        for p in pools:
            chain = p.get("chain", "Unknown")
            chain_breakdown[chain] = chain_breakdown.get(chain, 0) + p.get("tvlUsd", 0)

        return {
            "total_tvl_usd": total_tvl,
            "avg_apy_pct": round(avg_apy, 2),
            "pool_count": len(pools),
            "stablecoin_pool_count": len(stablecoin_pools),
            "chain_tvl_breakdown": dict(sorted(chain_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]),
            "top_pools": pools[:10],
        }

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect yield data relevant to a token.

        Args:
            token_id: CoinGecko-style token identifier (used as project filter hint)

        Returns:
            Yield data dict
        """
        print(f"  [DeFiLlama Yields] Collecting yield data for {token_id}...")

        result = {
            "token_id": token_id,
            "source": "defillama_yields",
            "market_summary": None,
            "project_pools": None,
        }

        result["market_summary"] = self.collect_market_summary()
        result["project_pools"] = self.collect_project_yields(token_id)

        has_data = sum(1 for k in ["market_summary", "project_pools"] if result.get(k))
        print(f"    → Collected {has_data}/2 yield metrics")
        return result


if __name__ == "__main__":
    collector = CollectorDefiLlamaYields()
    data = collector.collect("aave")
    print(json.dumps(data, indent=2, default=str)[:2000])
