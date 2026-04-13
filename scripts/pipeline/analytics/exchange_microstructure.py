"""
BCE Lab Exchange Microstructure Analysis
Multi-exchange price/volume comparison, spread analysis, anomaly detection.

Data Source: CryptoCompare (validated, score 87)
"""
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime, timezone

CRYPTOCOMPARE_BASE = "https://min-api.cryptocompare.com/data"
RATE_LIMIT_RPM = 50
MIN_INTERVAL = 60 / max(RATE_LIMIT_RPM, 1)
_last_request_time = 0


def _cc_get(endpoint: str, params: dict = None) -> Optional[Dict]:
    """Rate-limited GET to CryptoCompare."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)

    url = f"{CRYPTOCOMPARE_BASE}/{endpoint}"
    headers = {"User-Agent": "BCE-Lab-Pipeline/1.0"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        _last_request_time = time.time()
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"[CryptoCompare] Error: {e}")
        return None


def collect_multi_exchange_prices(symbol: str = "BTC", currency: str = "USD") -> Dict:
    """
    Collect price data from multiple exchanges for a single token.

    Returns:
        {
            "symbol": "BTC",
            "exchanges": [
                {"exchange": "Binance", "price": 84000.5, "volume_24h": ..., "change_24h_pct": ...},
                ...
            ],
            "price_spread": {"min": ..., "max": ..., "spread_pct": ...},
            "anomalies": [...]
        }
    """
    data = _cc_get("pricemultifull", {"fsyms": symbol, "tsyms": currency})
    result = {
        "symbol": symbol,
        "currency": currency,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "exchanges": [],
        "price_spread": {},
        "anomalies": [],
    }

    if not data or "RAW" not in data:
        return result

    raw = data["RAW"].get(symbol, {}).get(currency, {})
    if not raw:
        return result

    # Get top exchanges for this pair
    top_exchanges = _cc_get("top/exchanges/full", {"fsym": symbol, "tsym": currency, "limit": 10})
    if top_exchanges and "Data" in top_exchanges:
        exchanges_data = top_exchanges["Data"].get("Exchanges", [])
    else:
        exchanges_data = []

    prices = []
    for ex in exchanges_data:
        ex_name = ex.get("MARKET", "Unknown")
        ex_price = ex.get("PRICE", 0)
        ex_vol = ex.get("VOLUME24HOURTO", 0)
        ex_open = ex.get("OPEN24HOUR", 0)

        change_pct = ((ex_price - ex_open) / ex_open * 100) if ex_open > 0 else 0

        if ex_price > 0:
            prices.append(ex_price)
            result["exchanges"].append({
                "exchange": ex_name,
                "price": round(ex_price, 4),
                "volume_24h_usd": round(ex_vol, 2),
                "change_24h_pct": round(change_pct, 2),
            })

    # Calculate price spread
    if len(prices) >= 2:
        min_p = min(prices)
        max_p = max(prices)
        avg_p = sum(prices) / len(prices)
        spread_pct = (max_p - min_p) / avg_p * 100

        result["price_spread"] = {
            "min_price": round(min_p, 4),
            "max_price": round(max_p, 4),
            "avg_price": round(avg_p, 4),
            "spread_usd": round(max_p - min_p, 4),
            "spread_pct": round(spread_pct, 4),
        }

        # Anomaly detection
        if spread_pct > 3.0:
            result["anomalies"].append({
                "type": "extreme_spread",
                "severity": "critical",
                "description": f"Price spread {spread_pct:.2f}% across exchanges exceeds 3% threshold",
            })
        elif spread_pct > 1.0:
            result["anomalies"].append({
                "type": "high_spread",
                "severity": "warning",
                "description": f"Price spread {spread_pct:.2f}% across exchanges exceeds 1% threshold",
            })

    # Volume concentration check
    if result["exchanges"]:
        total_vol = sum(e["volume_24h_usd"] for e in result["exchanges"])
        if total_vol > 0:
            for ex in result["exchanges"]:
                ex["volume_share_pct"] = round(ex["volume_24h_usd"] / total_vol * 100, 2)

            top_share = result["exchanges"][0]["volume_share_pct"] if result["exchanges"] else 0
            if top_share > 60:
                result["anomalies"].append({
                    "type": "volume_concentration",
                    "severity": "warning",
                    "description": f"{result['exchanges'][0]['exchange']} holds "
                                  f"{top_share:.1f}% of total volume — single-exchange dependency risk",
                })

    return result


def collect_exchange_volume_history(symbol: str = "BTC", currency: str = "USD",
                                     days: int = 30) -> Dict:
    """
    Collect historical daily volume per exchange.

    Returns volume trends for identifying unusual volume patterns.
    """
    data = _cc_get("exchange/histoday", {
        "fsym": symbol, "tsym": currency, "limit": days, "aggregate": 1
    })
    result = {
        "symbol": symbol,
        "days": days,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "daily_volumes": [],
        "volume_stats": {},
    }

    if data and "Data" in data:
        volumes = []
        for day in data["Data"]:
            vol = day.get("volumeto", 0)
            volumes.append(vol)
            result["daily_volumes"].append({
                "timestamp": day.get("time", 0),
                "volume_usd": round(vol, 2),
            })

        if volumes:
            avg_vol = sum(volumes) / len(volumes)
            max_vol = max(volumes)
            min_vol = min(volumes)
            recent_vol = volumes[-1] if volumes else 0

            result["volume_stats"] = {
                "avg_daily_usd": round(avg_vol, 2),
                "max_daily_usd": round(max_vol, 2),
                "min_daily_usd": round(min_vol, 2),
                "recent_vs_avg_ratio": round(recent_vol / avg_vol, 2) if avg_vol > 0 else 0,
                "volume_spike": recent_vol > avg_vol * 3,
            }

    return result


def analyze_exchange_microstructure(symbol: str = "BTC") -> Dict:
    """
    Full exchange microstructure analysis.
    Main entry point for the pipeline.
    """
    prices = collect_multi_exchange_prices(symbol)
    volume_history = collect_exchange_volume_history(symbol)

    # Combine analyses
    return {
        "symbol": symbol,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "multi_exchange_prices": prices,
        "volume_history": volume_history,
        "exchange_count": len(prices.get("exchanges", [])),
        "anomaly_count": len(prices.get("anomalies", [])),
        "has_volume_spike": volume_history.get("volume_stats", {}).get("volume_spike", False),
    }
