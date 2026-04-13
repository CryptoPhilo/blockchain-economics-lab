"""
BCE Lab Data Collector — CoinGlass Derivatives
Collects futures open interest, funding rates, liquidation data, long/short ratios.

Category: derivatives
Base URL: https://open-api.coinglass.com/public/v2
Auth: api_key (free tier: 30 req/min)
Target Reports: FOR
"""
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime, timezone

BASE_URL = "https://open-api.coinglass.com/public/v2"
# CoinGlass free tier — API key can be obtained at coinglass.com
API_KEY = ""  # Set via env or config
RATE_LIMIT_RPM = 30
MIN_INTERVAL = 60 / max(RATE_LIMIT_RPM, 1)
SOURCE_NAME = "CoinGlass"

_last_request_time = 0


def _rate_limited_get(endpoint: str, params: dict = None) -> Optional[Dict]:
    """Rate-limited GET request to CoinGlass API."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)

    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    headers = {
        "User-Agent": "BCE-Lab-Pipeline/1.0",
        "coinglassSecret": API_KEY,
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        _last_request_time = time.time()
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") or data.get("code") == "0":
                return data.get("data", data)
            return data
        else:
            print(f"[{SOURCE_NAME}] HTTP {resp.status_code}: {resp.text[:200]}")
            return None
    except requests.RequestException as e:
        print(f"[{SOURCE_NAME}] Request error: {e}")
        return None


def collect_open_interest(symbol: str = "BTC") -> Dict:
    """
    Collect aggregated futures open interest across exchanges.

    Returns:
        {
            "symbol": "BTC",
            "total_oi_usd": float,
            "exchanges": [{"exchange": str, "oi_usd": float, "oi_change_24h_pct": float}],
            "oi_change_24h_pct": float,
            "collected_at": str
        }
    """
    data = _rate_limited_get("open_interest", {"symbol": symbol, "interval": "0"})
    result = {
        "source": SOURCE_NAME,
        "symbol": symbol,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_oi_usd": 0,
        "exchanges": [],
        "oi_change_24h_pct": 0,
    }

    if data and isinstance(data, list):
        for item in data:
            exchange_data = {
                "exchange": item.get("exchangeName", "Unknown"),
                "oi_usd": item.get("openInterest", 0),
                "oi_change_1h_pct": item.get("h1OIChangePercent", 0),
                "oi_change_4h_pct": item.get("h4OIChangePercent", 0),
                "oi_change_24h_pct": item.get("h24OIChangePercent", 0),
            }
            result["exchanges"].append(exchange_data)
            result["total_oi_usd"] += exchange_data["oi_usd"]

        if result["exchanges"]:
            total_weighted = sum(
                e["oi_usd"] * e["oi_change_24h_pct"] / 100
                for e in result["exchanges"] if e["oi_usd"] > 0
            )
            if result["total_oi_usd"] > 0:
                result["oi_change_24h_pct"] = (total_weighted / result["total_oi_usd"]) * 100

    return result


def collect_funding_rate(symbol: str = "BTC") -> Dict:
    """
    Collect real-time funding rates across exchanges.

    Returns:
        {
            "symbol": "BTC",
            "weighted_avg_rate": float,
            "exchanges": [{"exchange": str, "rate": float, "predicted_rate": float}],
            "sentiment": "long_dominant" | "short_dominant" | "neutral"
        }
    """
    data = _rate_limited_get("funding", {"symbol": symbol})
    result = {
        "source": SOURCE_NAME,
        "symbol": symbol,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "weighted_avg_rate": 0,
        "exchanges": [],
        "sentiment": "neutral",
    }

    if data and isinstance(data, list):
        total_oi = 0
        weighted_sum = 0
        for item in data:
            rate = item.get("rate", 0) or 0
            oi = item.get("openInterest", 0) or 0
            exchange_data = {
                "exchange": item.get("exchangeName", "Unknown"),
                "rate": rate,
                "predicted_rate": item.get("predictedRate", 0) or 0,
                "open_interest": oi,
            }
            result["exchanges"].append(exchange_data)
            weighted_sum += rate * oi
            total_oi += oi

        if total_oi > 0:
            result["weighted_avg_rate"] = weighted_sum / total_oi

        # Sentiment classification
        avg = result["weighted_avg_rate"]
        if avg > 0.01:
            result["sentiment"] = "long_dominant"
        elif avg < -0.01:
            result["sentiment"] = "short_dominant"
        else:
            result["sentiment"] = "neutral"

    return result


def collect_liquidation(symbol: str = "BTC") -> Dict:
    """
    Collect recent liquidation data.

    Returns:
        {
            "symbol": "BTC",
            "liquidations_24h_usd": float,
            "long_liquidations_usd": float,
            "short_liquidations_usd": float,
            "long_short_ratio": float,
            "exchanges": [...]
        }
    """
    data = _rate_limited_get("liquidation", {"symbol": symbol, "interval": "2"})
    result = {
        "source": SOURCE_NAME,
        "symbol": symbol,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "liquidations_24h_usd": 0,
        "long_liquidations_usd": 0,
        "short_liquidations_usd": 0,
        "long_short_ratio": 0,
        "exchanges": [],
    }

    if data and isinstance(data, list):
        for item in data:
            long_liq = item.get("longLiquidationUsd", 0) or 0
            short_liq = item.get("shortLiquidationUsd", 0) or 0
            total = long_liq + short_liq
            result["exchanges"].append({
                "exchange": item.get("exchangeName", "Unknown"),
                "long_liquidation_usd": long_liq,
                "short_liquidation_usd": short_liq,
                "total_usd": total,
            })
            result["long_liquidations_usd"] += long_liq
            result["short_liquidations_usd"] += short_liq

        result["liquidations_24h_usd"] = (
            result["long_liquidations_usd"] + result["short_liquidations_usd"]
        )
        if result["short_liquidations_usd"] > 0:
            result["long_short_ratio"] = (
                result["long_liquidations_usd"] / result["short_liquidations_usd"]
            )

    return result


def collect_long_short_ratio(symbol: str = "BTC") -> Dict:
    """
    Collect global long/short account ratio.

    Returns:
        {
            "symbol": "BTC",
            "long_ratio": float (0-1),
            "short_ratio": float (0-1),
            "long_short_ratio": float,
            "exchanges": [...]
        }
    """
    data = _rate_limited_get("long_short", {"symbol": symbol, "interval": "2"})
    result = {
        "source": SOURCE_NAME,
        "symbol": symbol,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "long_ratio": 0.5,
        "short_ratio": 0.5,
        "long_short_ratio": 1.0,
        "exchanges": [],
    }

    if data and isinstance(data, list):
        long_sum = 0
        short_sum = 0
        count = 0
        for item in data:
            lr = item.get("longRate", 0.5) or 0.5
            sr = item.get("shortRate", 0.5) or 0.5
            result["exchanges"].append({
                "exchange": item.get("exchangeName", "Unknown"),
                "long_ratio": lr,
                "short_ratio": sr,
            })
            long_sum += lr
            short_sum += sr
            count += 1

        if count > 0:
            result["long_ratio"] = long_sum / count
            result["short_ratio"] = short_sum / count
            if result["short_ratio"] > 0:
                result["long_short_ratio"] = result["long_ratio"] / result["short_ratio"]

    return result


def collect_all(symbol: str = "BTC") -> Dict:
    """
    Collect all derivatives data for a token.
    Main entry point for the pipeline.
    """
    return {
        "source": SOURCE_NAME,
        "symbol": symbol,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "open_interest": collect_open_interest(symbol),
        "funding_rate": collect_funding_rate(symbol),
        "liquidation": collect_liquidation(symbol),
        "long_short_ratio": collect_long_short_ratio(symbol),
    }


def health_check() -> Dict:
    """Check if CoinGlass API is reachable."""
    try:
        resp = requests.get(f"{BASE_URL}/open_interest",
                           params={"symbol": "BTC"},
                           headers={"User-Agent": "BCE-CRO-Validator/1.0"},
                           timeout=10)
        return {
            "status": "healthy" if resp.status_code == 200 else "degraded",
            "latency_ms": int(resp.elapsed.total_seconds() * 1000),
            "http_status": resp.status_code,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
