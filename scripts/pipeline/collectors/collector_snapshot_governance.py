"""
Snapshot.org Governance Collector
Collects DAO governance data: proposals, voting results, space activity
from Snapshot.org GraphQL API (free, no auth required).

Source: https://hub.snapshot.org/graphql
Category: governance
CRO Quality Score: 78/100
Integrated: 2026-04-13
"""

import json
from typing import Any, Dict, List, Optional
from .base_collector import BaseCollector


class CollectorSnapshotGovernance(BaseCollector):
    """Collector for Snapshot.org DAO governance data."""

    BASE_URL = "https://hub.snapshot.org/graphql"

    # Mapping from CoinGecko token IDs to Snapshot space IDs
    SPACE_MAP = {
        "ethereum": "ens.eth",
        "aave": "aave.eth",
        "uniswap": "uniswapgovernance.eth",
        "compound-governance-token": "comp-vote.eth",
        "arbitrum": "arbitrumfoundation.eth",
        "optimism": "opcollective.eth",
        "lido-dao": "lido-snapshot.eth",
        "maker": "makerdao.eth",
        "curve-dao-token": "curve.eth",
        "balancer": "balancer.eth",
    }

    def __init__(self):
        super().__init__()

    def _graphql_request(self, query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
        """Execute a GraphQL query against Snapshot.org."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = self.session.post(
                self.BASE_URL,
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
            if "errors" in result:
                return None
            return result.get("data")
        except Exception:
            return None

    def collect_top_spaces(self, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """Collect top governance spaces by follower count."""
        cache_key = f"snapshot_top_spaces_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        query = """
        query TopSpaces($limit: Int!) {
            spaces(first: $limit, orderBy: "followers", orderDirection: desc) {
                id
                name
                members
                proposals_count: proposalsCount
                followers
                voting {
                    delay
                    period
                    quorum
                }
            }
        }
        """
        data = self._graphql_request(query, {"limit": limit})
        if data and data.get("spaces"):
            self._cache_set(cache_key, data["spaces"], ttl=3600)
            return data["spaces"]
        return None

    def collect_recent_proposals(self, space_id: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Collect recent proposals for a specific DAO space."""
        cache_key = f"snapshot_proposals_{space_id}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        query = """
        query Proposals($space: String!, $limit: Int!) {
            proposals(
                first: $limit,
                where: { space: $space },
                orderBy: "created",
                orderDirection: desc
            ) {
                id
                title
                state
                author
                created
                start
                end
                choices
                scores
                scores_total
                votes
                quorum
                type
            }
        }
        """
        data = self._graphql_request(query, {"space": space_id, "limit": limit})
        if data and data.get("proposals"):
            self._cache_set(cache_key, data["proposals"], ttl=1800)  # 30 min
            return data["proposals"]
        return None

    def collect_governance_summary(self, space_id: str) -> Optional[Dict[str, Any]]:
        """Collect governance summary for a DAO space."""
        cache_key = f"snapshot_summary_{space_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        query = """
        query SpaceSummary($space: String!) {
            space(id: $space) {
                id
                name
                members
                proposalsCount
                followers
                strategies {
                    name
                }
                voting {
                    delay
                    period
                    quorum
                }
                categories
            }
        }
        """
        data = self._graphql_request(query, {"space": space_id})
        if data and data.get("space"):
            self._cache_set(cache_key, data["space"], ttl=3600)
            return data["space"]
        return None

    def collect(self, token_id: str) -> Dict[str, Any]:
        """
        Collect governance data for a token's associated DAO.

        Args:
            token_id: CoinGecko-style token identifier

        Returns:
            Governance data dict
        """
        space_id = self.SPACE_MAP.get(token_id)
        print(f"  [Snapshot] Collecting governance data for {token_id}...")

        result = {
            "token_id": token_id,
            "source": "snapshot.org",
            "space_id": space_id,
            "space_info": None,
            "recent_proposals": None,
            "top_spaces": None,
        }

        if space_id:
            summary = self.collect_governance_summary(space_id)
            if summary:
                result["space_info"] = summary

            proposals = self.collect_recent_proposals(space_id)
            if proposals:
                result["recent_proposals"] = proposals
                result["active_proposals"] = [p for p in proposals if p.get("state") == "active"]
                result["total_votes_recent"] = sum(p.get("votes", 0) for p in proposals)
        else:
            print(f"    → No Snapshot space mapped for {token_id}")

        # Always collect top spaces for market overview
        top = self.collect_top_spaces(10)
        if top:
            result["top_spaces"] = top

        has_data = sum(1 for k in ["space_info", "recent_proposals", "top_spaces"] if result.get(k))
        print(f"    → Collected {has_data}/3 governance metrics")

        return result


if __name__ == "__main__":
    collector = CollectorSnapshotGovernance()
    data = collector.collect("aave")
    print(json.dumps(data, indent=2, default=str)[:2000])
