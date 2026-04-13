"""
Santiment Social & On-Chain Collector
Collects social sentiment, development activity, and on-chain metrics
from Santiment Free GraphQL API.

Source: https://api.santiment.net/graphql
Category: social
CRO Quality Score: 86/100
Integrated: 2026-04-13
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


class CollectorSantimentSocial(BaseCollector):
    """Collector for Santiment social sentiment and dev activity data."""

    BASE_URL = "https://api.santiment.net/graphql"

    # CoinGecko ID -> Santiment slug mapping
    SLUG_MAP = {
        "bitcoin": "bitcoin",
        "ethereum": "ethereum",
        "solana": "solana",
        "binancecoin": "binance-coin",
        "ripple": "ripple",
        "cardano": "cardano",
        "avalanche-2": "avalanche",
        "polkadot": "polkadot",
        "chainlink": "chainlink",
        "polygon": "polygon",
        "uniswap": "uniswap",
        "aave": "aave",
        "lido-dao": "lido-dao",
        "maker": "maker",
    }

    def __init__(self):
        super().__init__()

    def _get_slug(self, token_id: str) -> str:
        """Convert CoinGecko token ID to Santiment slug."""
        return self.SLUG_MAP.get(token_id, token_id)

    def _graphql_request(self, query: str) -> Optional[Dict]:
        """Execute GraphQL query against Santiment API."""
        try:
            response = self.session.post(
                self.BASE_URL,
                json={"query": query},
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
            if "errors" in result:
                return None
            return result.get("data")
        except Exception:
            return None

    def _date_range(self, days_back: int = 30):
        """Generate ISO date range strings."""
        now = datetime.utcnow()
        from_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00Z")
        to_date = now.strftime("%Y-%m-%dT00:00:00Z")
        return from_date, to_date

    def collect_dev_activity(self, token_id: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Collect development activity metrics."""
        slug = self._get_slug(token_id)
        cache_key = f"santiment_dev_{slug}_{days}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        from_date, to_date = self._date_range(days)
        query = f'''
        {{
            getMetric(metric: "dev_activity") {{
                timeseriesData(
                    slug: "{slug}"
                    from: "{from_date}"
                    to: "{to_date}"
                    interval: "1d"
                ) {{
                    datetime
                    value
                }}
            }}
        }}
        '''
        data = self._graphql_request(query)
        if data and data.get("getMetric", {}).get("timeseriesData"):
            ts = data["getMetric"]["timeseriesData"]
            values = [p["value"] for p in ts if p.get("value") is not None]
            result = {
                "slug": slug,
                "metric": "dev_activity",
                "timeseries": ts,
                "avg_30d": sum(values) / len(values) if values else 0,
                "latest": values[-1] if values else 0,
                "data_points": len(ts),
            }
            self._cache_set(cache_key, result, ttl=3600)
            return result
        return None

    def collect_social_volume(self, token_id: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Collect social media volume (mentions across platforms)."""
        slug = self._get_slug(token_id)
        cache_key = f"santiment_social_vol_{slug}_{days}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        from_date, to_date = self._date_range(days)
        query = f'''
        {{
            getMetric(metric: "social_volume_total") {{
                timeseriesData(
                    slug: "{slug}"
                    from: "{from_date}"
                    to: "{to_date}"
                    interval: "1d"
                ) {{
                    datetime
                    value
                }}
            }}
        }}
        '''
        data = self._graphql_request(query)
        if data and data.get("getMetric", {}).get("timeseriesData"):
            ts = data["getMetric"]["timeseriesData"]
            values = [p["value"] for p in ts if p.get("value") is not None]
            result = {
                "slug": slug,
                "metric": "social_volume_total",
                "timeseries": ts,
                "avg_30d": sum(values) / len(values) if values else 0,
                "latest": values[-1] if values else 0,
                "peak": max(values) if values else 0,
                "data_points": len(ts),
            }
            self._cache_set(cache_key, result, ttl=1800)
            return result
        return None

    def collect_social_dominance(self, token_id: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Collect social dominance (share of total crypto social volume)."""
        slug = self._get_slug(token_id)
        cache_key = f"santiment_social_dom_{slug}_{days}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        from_date, to_date = self._date_range(days)
        query = f'''
        {{
            getMetric(metric: "social_dominance_total") {{
                timeseriesData(
                    slug: "{slug}"
                    from: "{from_date}"
                    to: "{to_date}"
                    interval: "1d"
                ) {{
                    datetime
                    value
                }}
            }}
        }}
        '''
        data = self._graphql_request(query)
        if data and data.get("getMetric", {}).get("timeseriesData"):
            ts = data["getMetric"]["timeseriesData"]
            values = [p["value"] for p in ts if p.get("value") is not None]
            result = {
                "slug": slug,
                "metric": "social_dominance_total",
                "timeseries": ts,
                "avg_30d": sum(values) / len(values) if values else 0,
                "latest": values[-1] if values else 0,
                "data_points": len(ts),
            }
            self._cache_set(cache_key, result, ttl=1800)
            return result
        return None

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect all social and development metrics for a token.

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Combined social metrics dict
        """
        slug = self._get_slug(token_id)
        print(f"  [Santiment] Collecting social/dev metrics for {slug}...")

        result = {
            "token_id": token_id,
            "slug": slug,
            "source": "santiment",
            "dev_activity": None,
            "social_volume": None,
            "social_dominance": None,
        }

        dev = self.collect_dev_activity(token_id)
        if dev:
            result["dev_activity"] = dev

        vol = self.collect_social_volume(token_id)
        if vol:
            result["social_volume"] = vol

        dom = self.collect_social_dominance(token_id)
        if dom:
            result["social_dominance"] = dom

        collected = sum(1 for k in ["dev_activity", "social_volume", "social_dominance"] if result.get(k))
        print(f"    → Collected {collected}/3 social metrics for {slug}")

        return result


if __name__ == "__main__":
    collector = CollectorSantimentSocial()
    data = collector.collect("bitcoin")
    print(json.dumps(data, indent=2, default=str)[:2000])
