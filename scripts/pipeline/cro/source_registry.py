"""
CRO Data Source Registry — Supabase-backed registry for tracking data sources.
Manages lifecycle: candidate → testing → validated → integrated
"""
import os
import json
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional

SUPABASE_URL = "https://wbqponoiyoeqlepxogcb.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
PROJECT_ID = "wbqponoiyoeqlepxogcb"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


class SourceRegistry:
    """Manages data source registry in Supabase."""

    # ── Known high-value candidate sources for blockchain data ──
    PRIORITY_SEARCH_TARGETS = [
        # Derivatives & Options
        {"category": "derivatives", "keywords": ["crypto futures open interest API",
                                                   "crypto options data API free",
                                                   "bitcoin derivatives market data"]},
        # Social Sentiment
        {"category": "social", "keywords": ["crypto social sentiment API",
                                             "twitter crypto sentiment analysis API",
                                             "crypto community metrics API"]},
        # Governance
        {"category": "governance", "keywords": ["DAO governance API",
                                                  "snapshot.org API voting data",
                                                  "crypto governance participation API"]},
        # Regulatory
        {"category": "regulatory", "keywords": ["crypto regulatory filings API",
                                                  "blockchain compliance data API"]},
        # News & Events
        {"category": "news", "keywords": ["crypto news aggregator API",
                                            "blockchain news feed API free"]},
        # On-chain Advanced
        {"category": "onchain", "keywords": ["blockchain analytics API free",
                                               "crypto wallet labeling API",
                                               "token holder analytics API"]},
        # DeFi
        {"category": "defi", "keywords": ["DeFi protocol analytics API",
                                            "DEX volume aggregator API",
                                            "yield farming data API"]},
    ]

    # ── Well-known blockchain data APIs to seed discovery ──
    KNOWN_CANDIDATES = [
        {
            "source_name": "CoinCap",
            "source_type": "api",
            "base_url": "https://api.coincap.io/v2",
            "category": "market_data",
            "auth_type": "none",
            "rate_limit_rpm": 200,
            "free_tier": True,
            "target_report_types": ["econ", "mat"],
            "notes": "Real-time market data, alternative to CoinGecko",
        },
        {
            "source_name": "CryptoCompare",
            "source_type": "api",
            "base_url": "https://min-api.cryptocompare.com/data",
            "category": "market_data",
            "auth_type": "api_key",
            "rate_limit_rpm": 50,
            "free_tier": True,
            "target_report_types": ["econ", "for"],
            "notes": "Historical + social data, exchange-level volume",
        },
        {
            "source_name": "Messari",
            "source_type": "api",
            "base_url": "https://data.messari.io/api/v1",
            "category": "market_data",
            "auth_type": "api_key",
            "rate_limit_rpm": 20,
            "free_tier": True,
            "target_report_types": ["econ", "mat"],
            "notes": "Curated metrics, quantitative analysis",
        },
        {
            "source_name": "Glassnode Free",
            "source_type": "api",
            "base_url": "https://api.glassnode.com/v1/metrics",
            "category": "onchain",
            "auth_type": "api_key",
            "rate_limit_rpm": 10,
            "free_tier": True,
            "target_report_types": ["econ", "for"],
            "notes": "On-chain metrics (limited free tier)",
        },
        {
            "source_name": "DefiLlama Yields",
            "source_type": "api",
            "base_url": "https://yields.llama.fi",
            "category": "defi",
            "auth_type": "none",
            "rate_limit_rpm": 60,
            "free_tier": True,
            "target_report_types": ["econ"],
            "notes": "DeFi yield data across protocols",
        },
        {
            "source_name": "DeFiLlama Stablecoins",
            "source_type": "api",
            "base_url": "https://stablecoins.llama.fi",
            "category": "defi",
            "auth_type": "none",
            "rate_limit_rpm": 60,
            "free_tier": True,
            "target_report_types": ["econ", "mat"],
            "notes": "Stablecoin market cap and flows",
        },
        {
            "source_name": "CoinGlass",
            "source_type": "api",
            "base_url": "https://open-api.coinglass.com/public/v2",
            "category": "derivatives",
            "auth_type": "api_key",
            "rate_limit_rpm": 30,
            "free_tier": True,
            "target_report_types": ["for"],
            "notes": "Futures OI, funding rates, liquidations",
        },
        {
            "source_name": "Snapshot.org GraphQL",
            "source_type": "api",
            "base_url": "https://hub.snapshot.org/graphql",
            "category": "governance",
            "auth_type": "none",
            "rate_limit_rpm": 60,
            "free_tier": True,
            "target_report_types": ["econ", "mat"],
            "notes": "DAO governance votes, proposals, participation",
        },
        {
            "source_name": "CryptoPanic",
            "source_type": "api",
            "base_url": "https://cryptopanic.com/api/v1",
            "category": "news",
            "auth_type": "api_key",
            "rate_limit_rpm": 10,
            "free_tier": True,
            "target_report_types": ["for", "econ"],
            "notes": "Aggregated crypto news with sentiment labels",
        },
        {
            "source_name": "Blockchain.com Stats",
            "source_type": "api",
            "base_url": "https://api.blockchain.info",
            "category": "onchain",
            "auth_type": "none",
            "rate_limit_rpm": 30,
            "free_tier": True,
            "target_report_types": ["econ", "for"],
            "notes": "Bitcoin network stats (hashrate, difficulty, mempool)",
        },
    ]

    @classmethod
    def get_all_sources(cls, status: Optional[str] = None) -> List[Dict]:
        """Fetch all sources from registry, optionally filtered by status."""
        url = f"{SUPABASE_URL}/rest/v1/data_source_registry?select=*&order=overall_score.desc"
        if status:
            url += f"&status=eq.{status}"
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def register_source(cls, source: Dict) -> Dict:
        """Register a new data source candidate."""
        url = f"{SUPABASE_URL}/rest/v1/data_source_registry"
        headers = {**HEADERS, "Prefer": "return=representation,resolution=merge-duplicates"}
        payload = {
            "source_name": source["source_name"],
            "source_type": source.get("source_type", "api"),
            "base_url": source["base_url"],
            "category": source["category"],
            "discovered_via": source.get("discovered_via", "manual"),
            "auth_type": source.get("auth_type", "none"),
            "rate_limit_rpm": source.get("rate_limit_rpm"),
            "free_tier": source.get("free_tier", True),
            "target_report_types": source.get("target_report_types", []),
            "notes": source.get("notes", ""),
            "status": "candidate",
        }
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def update_source(cls, source_id: int, updates: Dict) -> Dict:
        """Update a data source record."""
        url = f"{SUPABASE_URL}/rest/v1/data_source_registry?id=eq.{source_id}"
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        resp = requests.patch(url, headers=HEADERS, json=updates)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def log_test_result(cls, source_id: int, test_type: str, passed: bool,
                        latency_ms: int = 0, sample_tokens: int = 0,
                        tokens_with_data: int = 0, error: str = "",
                        details: Dict = None) -> Dict:
        """Log a test result for a data source."""
        url = f"{SUPABASE_URL}/rest/v1/source_test_results"
        payload = {
            "source_id": source_id,
            "test_type": test_type,
            "passed": passed,
            "latency_ms": latency_ms,
            "sample_tokens_tested": sample_tokens,
            "tokens_with_data": tokens_with_data,
            "error_message": error or None,
            "details": json.dumps(details or {}),
        }
        resp = requests.post(url, headers=HEADERS, json=payload)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def log_improvement(cls, action_type: str, source_id: int = None,
                        description: str = "", impact: str = "") -> Dict:
        """Log a CRO improvement action."""
        url = f"{SUPABASE_URL}/rest/v1/cro_improvement_log"
        payload = {
            "action_type": action_type,
            "source_id": source_id,
            "description": description,
            "impact_assessment": impact or None,
        }
        resp = requests.post(url, headers=HEADERS, json=payload)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def seed_known_candidates(cls) -> int:
        """Seed registry with well-known blockchain data source candidates."""
        count = 0
        for source in cls.KNOWN_CANDIDATES:
            try:
                source["discovered_via"] = "seed"
                cls.register_source(source)
                count += 1
            except Exception as e:
                print(f"  Skip {source['source_name']}: {e}")
        return count

    @classmethod
    def get_sources_needing_test(cls) -> List[Dict]:
        """Get candidate sources that haven't been tested recently."""
        url = (f"{SUPABASE_URL}/rest/v1/data_source_registry"
               f"?select=*&status=in.(candidate,testing)"
               f"&order=overall_score.asc")
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def get_validated_sources(cls) -> List[Dict]:
        """Get sources that passed validation and are ready for integration."""
        url = (f"{SUPABASE_URL}/rest/v1/data_source_registry"
               f"?select=*&status=eq.validated&order=overall_score.desc")
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()
