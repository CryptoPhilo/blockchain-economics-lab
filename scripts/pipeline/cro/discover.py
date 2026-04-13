"""
CRO Discovery Module — Searches for new blockchain data sources via web search.
Evaluates discovered APIs against criteria and registers candidates.
"""
import re
import json
import time
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

# Known API base URL patterns to extract from search results
API_URL_PATTERNS = [
    r'https?://api\.[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}/[a-zA-Z0-9/\-]*',
    r'https?://[a-zA-Z0-9\-]+\.(?:io|com|org|xyz)/api/[a-zA-Z0-9/\-]*',
    r'https?://[a-zA-Z0-9\-]+\.(?:io|com|org|xyz)/v[0-9]/[a-zA-Z0-9/\-]*',
]

# Categories mapped to search strategies
DISCOVERY_QUERIES = {
    "derivatives": [
        "free crypto derivatives API open interest funding rate 2025 2026",
        "bitcoin futures data API free tier",
        "crypto options analytics API",
    ],
    "social": [
        "crypto social sentiment API free 2025 2026",
        "blockchain community metrics API",
        "crypto twitter sentiment analysis API free",
    ],
    "governance": [
        "DAO governance data API snapshot tally 2025 2026",
        "on-chain voting analytics API",
        "crypto governance participation metrics API",
    ],
    "onchain": [
        "free blockchain analytics API 2025 2026",
        "crypto wallet labeling API free",
        "on-chain token flow analytics API",
        "blockchain explorer API multi-chain free",
    ],
    "defi": [
        "DeFi analytics API free TVL yields 2025 2026",
        "DEX aggregator volume API",
        "DeFi protocol revenue API",
    ],
    "news": [
        "crypto news API sentiment aggregator free 2025 2026",
        "blockchain news feed API real-time",
    ],
    "market_data": [
        "cryptocurrency market data API alternative CoinGecko 2025 2026",
        "crypto exchange aggregated volume API free",
    ],
}

# Keywords that indicate a good API data source
POSITIVE_SIGNALS = [
    "free tier", "free api", "no auth", "public api", "open api",
    "rest api", "json", "rate limit", "documentation", "endpoints",
    "real-time", "historical data", "websocket",
]

# Keywords that indicate the source is not suitable
NEGATIVE_SIGNALS = [
    "deprecated", "discontinued", "shutdown", "paid only",
    "enterprise only", "coming soon", "beta closed",
]


class DataSourceDiscoverer:
    """Discovers new blockchain data APIs through web search."""

    def __init__(self, web_search_fn=None, web_fetch_fn=None):
        """
        Initialize with optional web search/fetch functions.
        In production, these are provided by the Cowork environment.
        For standalone use, falls back to requests-based search.
        """
        self._web_search = web_search_fn
        self._web_fetch = web_fetch_fn
        self.discovered = []

    def search_category(self, category: str) -> List[Dict]:
        """Search for data sources in a specific category."""
        queries = DISCOVERY_QUERIES.get(category, [])
        candidates = []

        for query in queries:
            try:
                results = self._perform_search(query)
                for result in results:
                    candidate = self._evaluate_result(result, category)
                    if candidate:
                        candidates.append(candidate)
                time.sleep(1)  # Rate limit between searches
            except Exception as e:
                print(f"  Search error for '{query}': {e}")

        # Deduplicate by base_url
        seen = set()
        unique = []
        for c in candidates:
            url_key = c["base_url"].rstrip("/").lower()
            if url_key not in seen:
                seen.add(url_key)
                unique.append(c)

        self.discovered.extend(unique)
        return unique

    def search_all_categories(self) -> Dict[str, List[Dict]]:
        """Search all categories and return results grouped by category."""
        results = {}
        for category in DISCOVERY_QUERIES:
            print(f"🔍 Searching category: {category}")
            found = self.search_category(category)
            results[category] = found
            print(f"   Found {len(found)} candidates")
        return results

    def _perform_search(self, query: str) -> List[Dict]:
        """
        Execute a web search. Returns list of {title, url, snippet} dicts.
        Uses web_search_fn if available, otherwise returns empty.
        """
        if self._web_search:
            return self._web_search(query)

        # Fallback: try a simple Google search scrape (limited)
        try:
            headers = {"User-Agent": "BCE-CRO-Agent/1.0"}
            resp = requests.get(
                "https://www.google.com/search",
                params={"q": query, "num": 10},
                headers=headers,
                timeout=10,
            )
            # Parse results (simplified)
            results = []
            for match in re.finditer(r'<a href="/url\?q=(https?://[^&"]+)', resp.text):
                url = match.group(1)
                if not any(x in url for x in ["google.", "youtube.", "facebook."]):
                    results.append({"title": "", "url": url, "snippet": ""})
            return results[:10]
        except Exception:
            return []

    def _evaluate_result(self, result: Dict, category: str) -> Optional[Dict]:
        """Evaluate a search result to determine if it's a viable data source."""
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        combined_text = f"{title} {snippet}".lower()

        # Check for negative signals
        for neg in NEGATIVE_SIGNALS:
            if neg in combined_text:
                return None

        # Check for positive signals
        positive_count = sum(1 for pos in POSITIVE_SIGNALS if pos in combined_text)
        if positive_count < 1:
            return None  # Need at least one positive signal

        # Extract API base URL
        api_url = self._extract_api_url(url, combined_text)
        if not api_url:
            return None

        # Determine source name from URL
        source_name = self._extract_source_name(api_url)

        return {
            "source_name": source_name,
            "source_type": "api",
            "base_url": api_url,
            "category": category,
            "discovered_via": "web_search",
            "auth_type": "api_key" if "api key" in combined_text or "auth" in combined_text else "none",
            "free_tier": any(x in combined_text for x in ["free", "no auth", "public"]),
            "target_report_types": self._infer_report_types(category),
            "notes": f"Discovered via search. Signals: {positive_count} positive. {snippet[:200]}",
        }

    def _extract_api_url(self, page_url: str, text: str) -> Optional[str]:
        """Extract the API base URL from the page URL or text."""
        # Try extracting from text first
        for pattern in API_URL_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0).rstrip("/")

        # Fall back to constructing from page URL
        # e.g., https://docs.coinglass.com/api → https://api.coinglass.com
        domain_match = re.match(r'https?://(?:docs?\.|www\.)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})', page_url)
        if domain_match:
            domain = domain_match.group(1)
            if any(x in page_url.lower() for x in ["/api", "/docs", "/reference", "/endpoint"]):
                return f"https://api.{domain}"

        return None

    def _extract_source_name(self, api_url: str) -> str:
        """Extract a human-readable source name from an API URL."""
        match = re.match(r'https?://(?:api\.)?([a-zA-Z0-9\-]+)', api_url)
        if match:
            name = match.group(1).replace("-", " ").title()
            return name
        return api_url

    def _infer_report_types(self, category: str) -> List[str]:
        """Infer which report types benefit from a data source category."""
        mapping = {
            "market_data": ["econ", "mat", "for"],
            "onchain": ["econ", "for"],
            "defi": ["econ", "mat"],
            "social": ["econ"],
            "governance": ["econ", "mat"],
            "derivatives": ["for"],
            "regulatory": ["mat", "for"],
            "news": ["for", "econ"],
            "developer": ["econ", "mat"],
            "whale": ["for"],
        }
        return mapping.get(category, ["econ"])


def run_discovery(categories: Optional[List[str]] = None) -> Dict:
    """
    Run the discovery process for specified categories (or all).
    Returns summary of discovered candidates.
    """
    discoverer = DataSourceDiscoverer()
    if categories:
        results = {}
        for cat in categories:
            results[cat] = discoverer.search_category(cat)
    else:
        results = discoverer.search_all_categories()

    total = sum(len(v) for v in results.values())
    return {
        "total_discovered": total,
        "by_category": {k: len(v) for k, v in results.items()},
        "candidates": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
