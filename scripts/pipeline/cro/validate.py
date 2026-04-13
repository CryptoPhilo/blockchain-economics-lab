"""
CRO Validation Framework — Tests data sources for reliability, quality, and coverage.
Runs 6 types of tests and updates quality scores in the registry.
"""
import time
import json
import requests
import statistics
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from .source_registry import SourceRegistry

# Sample tokens to test against (high-traffic, well-known)
SAMPLE_TOKENS = [
    {"symbol": "BTC", "coingecko_id": "bitcoin", "name": "Bitcoin"},
    {"symbol": "ETH", "coingecko_id": "ethereum", "name": "Ethereum"},
    {"symbol": "SOL", "coingecko_id": "solana", "name": "Solana"},
    {"symbol": "BNB", "coingecko_id": "binancecoin", "name": "BNB"},
    {"symbol": "XRP", "coingecko_id": "ripple", "name": "XRP"},
    {"symbol": "ADA", "coingecko_id": "cardano", "name": "Cardano"},
    {"symbol": "DOGE", "coingecko_id": "dogecoin", "name": "Dogecoin"},
    {"symbol": "LINK", "coingecko_id": "chainlink", "name": "Chainlink"},
    {"symbol": "UNI", "coingecko_id": "uniswap", "name": "Uniswap"},
    {"symbol": "AAVE", "coingecko_id": "aave", "name": "Aave"},
]

# Test endpoint patterns for known APIs
API_TEST_ENDPOINTS = {
    "coincap.io": {"path": "/assets", "token_param": None, "list_key": "data"},
    "cryptocompare.com": {"path": "/price", "token_param": "fsym={symbol}&tsyms=USD", "list_key": None},
    "messari.io": {"path": "/assets/{coingecko_id}/metrics", "token_param": None, "list_key": "data"},
    "llama.fi": {"path": "/protocols", "token_param": None, "list_key": None},
    "coinglass.com": {"path": "/futures/openInterest", "token_param": "symbol={symbol}", "list_key": "data"},
    "blockchain.info": {"path": "/stats", "token_param": None, "list_key": None},
    "cryptopanic.com": {"path": "/posts/", "token_param": "currencies={symbol}", "list_key": "results"},
    "snapshot.org": {"path": "", "token_param": None, "list_key": "data"},
}

# Minimum thresholds for validation
VALIDATION_THRESHOLDS = {
    "availability_min_pct": 80,      # 80% of calls must succeed
    "response_time_max_ms": 5000,    # Under 5 seconds
    "coverage_min_pct": 50,          # At least 50% of sample tokens
    "stability_variance_max": 0.3,   # Response time variance < 30%
    "freshness_max_age_hours": 24,   # Data less than 24h old
}

PASS_THRESHOLD = 60  # Minimum overall score to pass validation


class DataSourceValidator:
    """Runs comprehensive tests on data source candidates."""

    def __init__(self):
        self.results = []

    def validate_source(self, source: Dict) -> Dict:
        """
        Run all validation tests on a single data source.
        Returns test summary with scores.
        """
        source_id = source.get("id")
        source_name = source.get("source_name", "Unknown")
        base_url = source.get("base_url", "")

        print(f"\n{'='*60}")
        print(f"🧪 Validating: {source_name} ({base_url})")
        print(f"{'='*60}")

        # Update status to testing
        if source_id:
            SourceRegistry.update_source(source_id, {"status": "testing"})

        results = {}

        # Test 1: Availability
        results["availability"] = self._test_availability(source)
        print(f"  ✓ Availability: {'PASS' if results['availability']['passed'] else 'FAIL'} "
              f"({results['availability']['success_rate']:.0%})")

        # Test 2: Response Time
        results["response_time"] = self._test_response_time(source)
        print(f"  ✓ Response Time: {'PASS' if results['response_time']['passed'] else 'FAIL'} "
              f"(avg {results['response_time']['avg_ms']:.0f}ms)")

        # Test 3: Data Quality
        results["data_quality"] = self._test_data_quality(source)
        print(f"  ✓ Data Quality: {'PASS' if results['data_quality']['passed'] else 'FAIL'} "
              f"(score {results['data_quality']['score']})")

        # Test 4: Freshness
        results["freshness"] = self._test_freshness(source)
        print(f"  ✓ Freshness: {'PASS' if results['freshness']['passed'] else 'FAIL'}")

        # Test 5: Coverage
        results["coverage"] = self._test_coverage(source)
        print(f"  ✓ Coverage: {'PASS' if results['coverage']['passed'] else 'FAIL'} "
              f"({results['coverage']['tokens_found']}/{results['coverage']['tokens_tested']})")

        # Test 6: Stability
        results["stability"] = self._test_stability(source)
        print(f"  ✓ Stability: {'PASS' if results['stability']['passed'] else 'FAIL'}")

        # Calculate scores
        scores = self._calculate_scores(results)
        overall_passed = scores["overall"] >= PASS_THRESHOLD

        print(f"\n  📊 Scores: R={scores['reliability']} F={scores['freshness']} "
              f"C={scores['coverage']} Q={scores['quality']} → Overall={scores['overall']}")
        print(f"  {'✅ VALIDATED' if overall_passed else '❌ REJECTED'}")

        # Update registry
        if source_id:
            SourceRegistry.update_source(source_id, {
                "reliability_score": scores["reliability"],
                "freshness_score": scores["freshness"],
                "coverage_score": scores["coverage"],
                "quality_score": scores["quality"],
                "status": "validated" if overall_passed else "rejected",
                "last_test_at": datetime.now(timezone.utc).isoformat(),
                "test_pass_count": sum(1 for r in results.values() if r.get("passed")),
                "test_fail_count": sum(1 for r in results.values() if not r.get("passed")),
            })

            # Log test results
            for test_type, result in results.items():
                SourceRegistry.log_test_result(
                    source_id=source_id,
                    test_type=test_type,
                    passed=result.get("passed", False),
                    latency_ms=result.get("avg_ms", 0),
                    sample_tokens=result.get("tokens_tested", 0),
                    tokens_with_data=result.get("tokens_found", 0),
                    error=result.get("error", ""),
                    details=result,
                )

            # Log improvement action
            action = "source_validated" if overall_passed else "source_rejected"
            SourceRegistry.log_improvement(
                action_type=action,
                source_id=source_id,
                description=f"{source_name}: overall={scores['overall']}, "
                           f"tests passed={sum(1 for r in results.values() if r.get('passed'))}/6",
                impact=f"Report types: {source.get('target_report_types', [])}",
            )

        return {
            "source_name": source_name,
            "scores": scores,
            "passed": overall_passed,
            "results": results,
        }

    def validate_all_candidates(self) -> List[Dict]:
        """Validate all candidate sources in the registry."""
        candidates = SourceRegistry.get_sources_needing_test()
        print(f"Found {len(candidates)} sources to validate\n")

        summaries = []
        for source in candidates:
            try:
                summary = self.validate_source(source)
                summaries.append(summary)
                time.sleep(2)  # Rate limit between source tests
            except Exception as e:
                print(f"  ❌ Error validating {source.get('source_name')}: {e}")
                summaries.append({
                    "source_name": source.get("source_name"),
                    "passed": False,
                    "error": str(e),
                })

        validated = [s for s in summaries if s.get("passed")]
        print(f"\n{'='*60}")
        print(f"📋 Validation Summary: {len(validated)}/{len(summaries)} passed")
        return summaries

    # ══════════════════════════════════════════════════
    # INDIVIDUAL TESTS
    # ══════════════════════════════════════════════════

    def _test_availability(self, source: Dict) -> Dict:
        """Test: Can we reach the endpoint? (3 attempts)"""
        base_url = source["base_url"].rstrip("/")
        attempts = 3
        successes = 0

        for _ in range(attempts):
            try:
                resp = requests.get(base_url, timeout=10,
                                     headers={"User-Agent": "BCE-CRO-Validator/1.0"})
                if resp.status_code < 500:
                    successes += 1
            except Exception:
                pass
            time.sleep(0.5)

        rate = successes / attempts
        return {
            "passed": rate >= (VALIDATION_THRESHOLDS["availability_min_pct"] / 100),
            "success_rate": rate,
            "attempts": attempts,
            "successes": successes,
        }

    def _test_response_time(self, source: Dict) -> Dict:
        """Test: How fast does it respond? (3 measurements)"""
        base_url = source["base_url"].rstrip("/")
        latencies = []

        for _ in range(3):
            try:
                start = time.time()
                resp = requests.get(base_url, timeout=10,
                                     headers={"User-Agent": "BCE-CRO-Validator/1.0"})
                latency = (time.time() - start) * 1000
                if resp.status_code < 500:
                    latencies.append(latency)
            except Exception:
                latencies.append(10000)  # Timeout penalty
            time.sleep(0.5)

        avg_ms = statistics.mean(latencies) if latencies else 10000
        return {
            "passed": avg_ms <= VALIDATION_THRESHOLDS["response_time_max_ms"],
            "avg_ms": avg_ms,
            "min_ms": min(latencies) if latencies else 0,
            "max_ms": max(latencies) if latencies else 0,
            "measurements": len(latencies),
        }

    def _test_data_quality(self, source: Dict) -> Dict:
        """Test: Is the returned data valid JSON with expected fields?"""
        base_url = source["base_url"].rstrip("/")

        try:
            resp = requests.get(base_url, timeout=10,
                                 headers={"User-Agent": "BCE-CRO-Validator/1.0"})
            if resp.status_code >= 400:
                return {"passed": False, "score": 0, "error": f"HTTP {resp.status_code}"}

            # Check if JSON
            try:
                data = resp.json()
            except ValueError:
                return {"passed": False, "score": 20, "error": "Not valid JSON"}

            # Score based on data structure
            score = 40  # Base: valid JSON
            if isinstance(data, dict):
                if len(data) >= 3:
                    score += 20  # Has multiple fields
                if any(k in str(data.keys()).lower() for k in ["price", "market", "volume", "data", "result"]):
                    score += 20  # Has expected crypto fields
                if any(isinstance(v, (list, dict)) for v in data.values()):
                    score += 20  # Has nested structures (richer data)
            elif isinstance(data, list) and len(data) > 0:
                score += 40  # Array with data

            return {"passed": score >= 60, "score": min(score, 100)}

        except Exception as e:
            return {"passed": False, "score": 0, "error": str(e)}

    def _test_freshness(self, source: Dict) -> Dict:
        """Test: Is the data recently updated?"""
        base_url = source["base_url"].rstrip("/")

        try:
            resp = requests.get(base_url, timeout=10,
                                 headers={"User-Agent": "BCE-CRO-Validator/1.0"})
            data = resp.json() if resp.status_code < 400 else {}

            # Look for timestamp fields
            text = json.dumps(data).lower()
            has_timestamps = any(k in text for k in [
                "timestamp", "updated_at", "last_updated", "time",
                "date", "created_at",
            ])

            # Check response headers for cache age
            cache_control = resp.headers.get("Cache-Control", "")
            age = int(resp.headers.get("Age", "0"))

            return {
                "passed": has_timestamps or age < 3600,
                "has_timestamps": has_timestamps,
                "cache_age_seconds": age,
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _test_coverage(self, source: Dict) -> Dict:
        """Test: How many of our sample tokens does this source cover?"""
        base_url = source["base_url"].rstrip("/")
        tokens_found = 0
        tokens_tested = min(5, len(SAMPLE_TOKENS))  # Test 5 tokens

        for token in SAMPLE_TOKENS[:tokens_tested]:
            try:
                # Try common endpoint patterns
                urls_to_try = [
                    f"{base_url}/{token['coingecko_id']}",
                    f"{base_url}/assets/{token['coingecko_id']}",
                    f"{base_url}?symbol={token['symbol']}",
                    f"{base_url}?ids={token['coingecko_id']}",
                ]
                for url in urls_to_try:
                    resp = requests.get(url, timeout=8,
                                         headers={"User-Agent": "BCE-CRO-Validator/1.0"})
                    if resp.status_code == 200:
                        data = resp.json()
                        if data and str(data) != "[]" and str(data) != "{}":
                            tokens_found += 1
                            break
                    time.sleep(0.3)
            except Exception:
                pass

        coverage_pct = (tokens_found / tokens_tested * 100) if tokens_tested > 0 else 0
        return {
            "passed": coverage_pct >= VALIDATION_THRESHOLDS["coverage_min_pct"],
            "tokens_tested": tokens_tested,
            "tokens_found": tokens_found,
            "coverage_pct": coverage_pct,
        }

    def _test_stability(self, source: Dict) -> Dict:
        """Test: Are responses consistent over multiple calls?"""
        base_url = source["base_url"].rstrip("/")
        response_sizes = []

        for _ in range(3):
            try:
                resp = requests.get(base_url, timeout=10,
                                     headers={"User-Agent": "BCE-CRO-Validator/1.0"})
                if resp.status_code == 200:
                    response_sizes.append(len(resp.content))
            except Exception:
                pass
            time.sleep(1)

        if len(response_sizes) < 2:
            return {"passed": False, "error": "Too few successful responses"}

        avg_size = statistics.mean(response_sizes)
        if avg_size == 0:
            return {"passed": False, "error": "Empty responses"}

        variance = statistics.stdev(response_sizes) / avg_size if avg_size > 0 else 1
        return {
            "passed": variance <= VALIDATION_THRESHOLDS["stability_variance_max"],
            "response_count": len(response_sizes),
            "avg_size_bytes": avg_size,
            "variance": variance,
        }

    # ══════════════════════════════════════════════════
    # SCORING
    # ══════════════════════════════════════════════════

    def _calculate_scores(self, results: Dict) -> Dict:
        """Calculate quality scores (0-100) from test results."""
        # Reliability: availability + stability
        avail = results.get("availability", {})
        stab = results.get("stability", {})
        reliability = int(
            (avail.get("success_rate", 0) * 50) +
            (50 if stab.get("passed") else 20 if stab.get("response_count", 0) > 0 else 0)
        )

        # Freshness: based on timestamps and response time
        fresh = results.get("freshness", {})
        resp_time = results.get("response_time", {})
        freshness = int(
            (50 if fresh.get("has_timestamps") else 20) +
            (50 if resp_time.get("avg_ms", 9999) < 2000 else
             30 if resp_time.get("avg_ms", 9999) < 5000 else 10)
        )

        # Coverage: token coverage percentage
        cov = results.get("coverage", {})
        coverage = int(cov.get("coverage_pct", 0))

        # Quality: data structure quality
        qual = results.get("data_quality", {})
        quality = qual.get("score", 0)

        overall = (reliability + freshness + coverage + quality) // 4

        return {
            "reliability": min(reliability, 100),
            "freshness": min(freshness, 100),
            "coverage": min(coverage, 100),
            "quality": min(quality, 100),
            "overall": min(overall, 100),
        }


def run_validation(source_ids: Optional[List[int]] = None) -> List[Dict]:
    """
    Run validation on specific sources or all candidates.
    Returns list of validation summaries.
    """
    validator = DataSourceValidator()
    if source_ids:
        sources = SourceRegistry.get_all_sources()
        sources = [s for s in sources if s["id"] in source_ids]
        return [validator.validate_source(s) for s in sources]
    else:
        return validator.validate_all_candidates()
