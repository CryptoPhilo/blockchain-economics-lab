#!/usr/bin/env python3
"""
Inactive candidate for the FOR input node `급변동 종목 스캐닝`.

This module intentionally does not register database rows, send email, or call
the active FOR publishing pipeline. It only produces the proposed card-anchor
input contract from CoinMarketCap listings data.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import requests

try:
    from scripts.pipeline.config import get_forensic_scan_deviation_threshold
except ModuleNotFoundError:
    from config import get_forensic_scan_deviation_threshold


CMC_LISTINGS_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
NODE_ID = "candidate.for.sudden_movers_scanner"
NODE_NAME = "급변동 종목 스캐닝"
DEFAULT_LIMIT = 500
DEFAULT_MARKET_AVERAGE_WINDOW = 20
DEFAULT_STALE_AFTER_SECONDS = 2 * 60 * 60
LOGGER = logging.getLogger("sudden_movers_scanner")


class CandidateScanError(Exception):
    """Expected candidate-node failure with a stable error code."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_cmc_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if not isinstance(value, str):
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _quote_usd(token: Dict[str, Any]) -> Dict[str, Any]:
    quote = token.get("quote")
    if not isinstance(quote, dict):
        return {}
    usd = quote.get("USD")
    return usd if isinstance(usd, dict) else {}


def build_failure_envelope(
    code: str,
    message: str,
    *,
    observed_at: Optional[str] = None,
    retryable: bool = False,
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "node": {"id": NODE_ID, "name": NODE_NAME, "candidate": True},
        "status": "failed",
        "observed_at": observed_at or utc_now_iso(),
        "source": source or {"name": "coinmarketcap", "endpoint": CMC_LISTINGS_URL},
        "candidates": [],
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        },
    }


def resolve_cmc_api_key(env: Optional[Dict[str, str]] = None) -> str:
    """Resolve CMC credentials with intentional backwards-compatible precedence."""
    source = env or os.environ
    return source.get("CMC_API_KEY") or source.get("COINMARKETCAP_API_KEY") or ""


def _log_monitoring_signal(level: int, code: str, message: str, **extra: Any) -> None:
    payload = {"event": "sudden_movers_scanner", "code": code, "message": message, **extra}
    LOGGER.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def fetch_cmc_listings(
    *,
    api_key: str,
    limit: int = DEFAULT_LIMIT,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    if not api_key:
        raise CandidateScanError(
            "missing_cmc_api_key",
            "CMC_API_KEY is required to scan CoinMarketCap listings.",
            retryable=False,
        )

    http = session or requests.Session()
    response = http.get(
        CMC_LISTINGS_URL,
        headers={"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"},
        params={
            "start": 1,
            "limit": limit,
            "convert": "USD",
            "sort": "market_cap",
            "sort_dir": "desc",
            "aux": "num_market_pairs,date_added,platform,max_supply,circulating_supply,total_supply",
        },
        timeout=30,
    )

    if response.status_code == 429:
        raise CandidateScanError(
            "cmc_rate_limited",
            "CoinMarketCap returned HTTP 429 rate limit.",
            retryable=True,
        )
    if response.status_code < 200 or response.status_code >= 300:
        raise CandidateScanError(
            "cmc_non_200",
            f"CoinMarketCap returned HTTP {response.status_code}.",
            retryable=True,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise CandidateScanError("cmc_malformed_json", str(exc), retryable=True) from exc

    status = payload.get("status") if isinstance(payload, dict) else None
    if isinstance(status, dict) and status.get("error_code") not in (None, 0):
        raise CandidateScanError(
            "cmc_api_error",
            str(status.get("error_message") or "CoinMarketCap status.error_code was non-zero."),
            retryable=True,
        )

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise CandidateScanError(
            "cmc_malformed_data",
            "CoinMarketCap response did not include a data array.",
            retryable=True,
        )

    return payload


def compute_market_average_change_24h(
    listings: List[Dict[str, Any]],
    *,
    top_n: int = DEFAULT_MARKET_AVERAGE_WINDOW,
) -> float:
    weighted_tokens = []
    for token in listings:
        quote = _quote_usd(token)
        market_cap = _as_float(quote.get("market_cap"))
        change = _as_float(quote.get("percent_change_24h"))
        if market_cap is None or market_cap <= 0 or change is None:
            continue
        weighted_tokens.append((market_cap, change))

    weighted_tokens.sort(key=lambda item: item[0], reverse=True)
    window = weighted_tokens[:top_n]
    total_market_cap = sum(market_cap for market_cap, _ in window)
    if total_market_cap <= 0:
        raise CandidateScanError(
            "market_average_unavailable",
            "No listings had both positive market_cap and percent_change_24h.",
            retryable=True,
        )
    return sum(market_cap * change for market_cap, change in window) / total_market_cap


def find_sudden_mover_candidates(
    listings: List[Dict[str, Any]],
    *,
    market_average_change_24h: float,
    threshold_pct_points: float,
    observed_at: str,
    source_metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for token in listings:
        quote = _quote_usd(token)
        token_change = _as_float(quote.get("percent_change_24h"))
        if token_change is None:
            continue

        deviation = token_change - market_average_change_24h
        abs_deviation = abs(deviation)
        if abs_deviation < threshold_pct_points:
            continue

        candidate = {
            "symbol": token.get("symbol"),
            "name": token.get("name"),
            "slug": token.get("slug"),
            "rank": token.get("cmc_rank"),
            "price": _as_float(quote.get("price")),
            "market_average_change_24h": round(market_average_change_24h, 6),
            "token_change_24h": round(token_change, 6),
            "relative_deviation": round(abs_deviation, 6),
            "signed_relative_deviation": round(deviation, 6),
            "direction": "up" if deviation > 0 else "down",
            "observed_at": observed_at,
            "source": {
                **source_metadata,
                "cmc_id": token.get("id"),
                "last_updated": quote.get("last_updated") or token.get("last_updated"),
            },
        }

        if not candidate["symbol"] or not candidate["name"] or not candidate["slug"]:
            continue
        candidates.append(candidate)

    candidates.sort(key=lambda item: item["relative_deviation"], reverse=True)
    return candidates


def run_candidate_scan(
    *,
    api_key: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    threshold_pct_points: Optional[float] = None,
    payload_fetcher: Optional[Callable[..., Dict[str, Any]]] = None,
    now_fn: Callable[[], str] = utc_now_iso,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
) -> Dict[str, Any]:
    observed_at = now_fn()
    threshold = (
        float(threshold_pct_points)
        if threshold_pct_points is not None
        else get_forensic_scan_deviation_threshold()
    )
    fetcher = payload_fetcher or fetch_cmc_listings

    try:
        resolved_api_key = resolve_cmc_api_key() if api_key is None else api_key
        payload = fetcher(api_key=resolved_api_key, limit=limit)
        status = payload.get("status", {})
        listings = payload.get("data")
        if not isinstance(listings, list):
            raise CandidateScanError(
                "cmc_malformed_data",
                "CoinMarketCap response did not include a data array.",
                retryable=True,
            )

        source_timestamp = status.get("timestamp") if isinstance(status, dict) else None
        source_metadata = {
            "name": "coinmarketcap",
            "endpoint": CMC_LISTINGS_URL,
            "limit": limit,
            "credit_count": status.get("credit_count") if isinstance(status, dict) else None,
            "source_timestamp": source_timestamp,
        }

        warnings = []
        parsed_source_ts = _parse_cmc_timestamp(source_timestamp)
        parsed_observed_at = _parse_cmc_timestamp(observed_at)
        if parsed_source_ts and parsed_observed_at:
            source_age_seconds = (parsed_observed_at - parsed_source_ts).total_seconds()
            source_metadata["source_age_seconds"] = round(source_age_seconds, 3)
            if source_age_seconds > stale_after_seconds:
                warnings.append({
                    "code": "stale_source_data",
                    "message": (
                        f"CoinMarketCap source timestamp is older than "
                        f"{stale_after_seconds} seconds."
                    ),
                })

        market_average = compute_market_average_change_24h(listings)
        candidates = find_sudden_mover_candidates(
            listings,
            market_average_change_24h=market_average,
            threshold_pct_points=threshold,
            observed_at=observed_at,
            source_metadata=source_metadata,
        )

        if not candidates:
            warnings.append({
                "code": "empty_result_set",
                "message": "No listings exceeded the market-relative deviation threshold.",
            })

        for warning in warnings:
            _log_monitoring_signal(
                logging.WARNING,
                warning["code"],
                warning["message"],
                observed_at=observed_at,
            )

        return {
            "node": {"id": NODE_ID, "name": NODE_NAME, "candidate": True},
            "status": "ok",
            "observed_at": observed_at,
            "threshold_pct_points": threshold,
            "market_average_change_24h": round(market_average, 6),
            "source": source_metadata,
            "candidates": candidates,
            "error": None,
            "warnings": warnings,
        }
    except CandidateScanError as exc:
        _log_monitoring_signal(
            logging.ERROR,
            exc.code,
            exc.message,
            observed_at=observed_at,
            retryable=exc.retryable,
        )
        return build_failure_envelope(
            exc.code,
            exc.message,
            observed_at=observed_at,
            retryable=exc.retryable,
        )
    except requests.RequestException as exc:
        _log_monitoring_signal(
            logging.ERROR,
            "cmc_request_failed",
            str(exc),
            observed_at=observed_at,
            retryable=True,
        )
        return build_failure_envelope(
            "cmc_request_failed",
            str(exc),
            observed_at=observed_at,
            retryable=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inactive candidate: 급변동 종목 스캐닝")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--log-level", default=os.environ.get("SUDDEN_MOVERS_LOG_LEVEL", "WARNING"))
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.WARNING))
    result = run_candidate_scan(limit=args.limit, threshold_pct_points=args.threshold)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(encoded)
            fh.write("\n")
    else:
        print(encoded)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
