#!/usr/bin/env python3
"""
Daily forensic monitoring script for BCE Lab projects.

Implements STR-002 §3.2 and process doc §4 forensic monitoring requirements.
Checks 5 forensic triggers and routes to appropriate escalation level.

Usage:
    python monitor_forensic.py [--projects project1,project2,...]
    python monitor_forensic.py --projects btc,eth,sol
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('forensic_monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# FORENSIC TRIGGER CHECKERS
# ============================================================================

def get_market_benchmark_24h() -> float:
    """
    Get the overall crypto market 24h change as benchmark.
    Uses CoinGecko /global endpoint for total market cap change.
    Falls back to BTC 70% + ETH 30% weighted average if unavailable.

    Returns:
        Market average 24h change percentage
    """
    try:
        import requests

        # Primary: CoinGecko global market data
        url = 'https://api.coingecko.com/api/v3/global'
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {})
            market_change = data.get('market_cap_change_percentage_24h_usd', None)
            if market_change is not None:
                logger.info(f"[Benchmark] Market 24h change: {market_change:.2f}% (source: CoinGecko global)")
                return float(market_change)

        # Fallback: BTC 70% + ETH 30% weighted
        url = 'https://api.coingecko.com/api/v3/simple/price'
        params = {'ids': 'bitcoin,ethereum', 'vs_currencies': 'usd', 'include_24hr_change': 'true'}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            btc_change = data.get('bitcoin', {}).get('usd_24h_change', 0.0)
            eth_change = data.get('ethereum', {}).get('usd_24h_change', 0.0)
            weighted = btc_change * 0.7 + eth_change * 0.3
            logger.info(f"[Benchmark] Market 24h change: {weighted:.2f}% (fallback: BTC {btc_change:.2f}% * 0.7 + ETH {eth_change:.2f}% * 0.3)")
            return weighted

    except Exception as e:
        logger.warning(f"[Benchmark] Failed to fetch market benchmark: {e}")

    # Last resort: assume 0% (no market-wide movement)
    logger.warning("[Benchmark] Using 0% as market benchmark (all API calls failed)")
    return 0.0


# Cache market benchmark per monitoring run (avoid repeated API calls)
_market_benchmark_cache: Optional[float] = None


def _get_cached_benchmark() -> float:
    """Get market benchmark, caching for the duration of a monitoring run."""
    global _market_benchmark_cache
    if _market_benchmark_cache is None:
        _market_benchmark_cache = get_market_benchmark_24h()
    return _market_benchmark_cache


def reset_benchmark_cache() -> None:
    """Reset benchmark cache (call at start of each monitoring run)."""
    global _market_benchmark_cache
    _market_benchmark_cache = None


def check_price_volatility(project_slug: str, token_id: str) -> Tuple[bool, float]:
    """
    Check if 24h price change deviates from market average by >= ±10%.

    CRO-002 개정: 절대 변동률 대신 시장 평균 대비 상대 변동률 사용.
    - 시장 평균: CoinGecko /global total_market_cap_change_24h
    - 초과 변동률 = |토큰 변동률 - 시장 평균|
    - 임계값: ±10% (수동 트리거), ±15% (자동 FOR 리포트)

    Args:
        project_slug: Project identifier (e.g., 'btc')
        token_id: CoinGecko token ID

    Returns:
        Tuple of (flag_triggered, relative_deviation_pct)
    """
    try:
        import requests

        # Get token's 24h change
        url = 'https://api.coingecko.com/api/v3/simple/price'
        params = {'ids': token_id, 'vs_currencies': 'usd', 'include_24hr_change': 'true'}
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200 and token_id in response.json():
            token_change = response.json()[token_id].get('usd_24h_change', 0.0) or 0.0
        else:
            logger.warning(f"[{project_slug}] Could not fetch price data for {token_id}")
            return False, 0.0

        # Get market benchmark
        market_avg = _get_cached_benchmark()

        # Calculate relative deviation
        relative_deviation = token_change - market_avg

        # Trigger threshold from config (default 10%)
        threshold = 10.0
        try:
            from config import FORENSIC_TRIGGERS
            threshold = FORENSIC_TRIGGERS.get('relative_deviation_24h_pct', 10.0)
        except ImportError:
            pass

        triggered = abs(relative_deviation) >= threshold

        logger.debug(
            f"[{project_slug}] Price: token={token_change:+.2f}%, market={market_avg:+.2f}%, "
            f"deviation={relative_deviation:+.2f}% (threshold: ±{threshold}%, trigger: {triggered})"
        )
        return triggered, relative_deviation

    except Exception as e:
        logger.error(f"Error checking price volatility for {project_slug}: {e}")
        return False, 0.0


def check_volume_anomaly(project_slug: str, token_id: str) -> Tuple[bool, float]:
    """
    Check if volume ratio vs 7d average >= 300%.

    Args:
        project_slug: Project identifier
        token_id: CoinGecko token ID

    Returns:
        Tuple of (flag_triggered, volume_ratio)
    """
    try:
        # TODO: Integrate real CoinGecko API call for 7d volume data
        # url = f'https://api.coingecko.com/api/v3/coins/{token_id}'
        # params = {'localization': False}
        # response = requests.get(url, params=params)
        # current_volume = response.json()['market_data']['total_volume']['usd']
        # Calculate 7d average from market_cap_chart data

        # Mock data for now
        import random
        volume_ratio = random.uniform(100, 400)

        triggered = volume_ratio >= 300.0
        logger.debug(f"[{project_slug}] Volume ratio: {volume_ratio:.1f}% of 7d avg (trigger: {triggered})")
        return triggered, volume_ratio

    except Exception as e:
        logger.error(f"Error checking volume anomaly for {project_slug}: {e}")
        return False, 0.0


def check_whale_movement(project_slug: str, token_id: str) -> Tuple[bool, float]:
    """
    Check if whale movement >= 1% of supply.

    Args:
        project_slug: Project identifier
        token_id: CoinGecko token ID

    Returns:
        Tuple of (flag_triggered, whale_pct_of_supply)

    Note:
        Requires blockchain data from Whale Alert API or on-chain indexer.
    """
    try:
        # TODO: Integrate Whale Alert API or on-chain data provider
        # Example: Whale Alert API
        # url = f'https://api.whale-alert.io/v1/transactions'
        # params = {'apiKey': WHALE_ALERT_KEY, 'min_value': 1000000}
        # response = requests.get(url, params=params)
        # Calculate total whale movement vs circulating supply

        # Mock data for now
        import random
        whale_pct = random.uniform(0, 2)

        triggered = whale_pct >= 1.0
        logger.debug(f"[{project_slug}] Whale movement: {whale_pct:.2f}% of supply (trigger: {triggered})")
        return triggered, whale_pct

    except Exception as e:
        logger.error(f"Error checking whale movement for {project_slug}: {e}")
        return False, 0.0


def check_exchange_inflow(project_slug: str, token_id: str) -> Tuple[bool, float]:
    """
    Check if exchange net inflow >= 0.5% of supply.

    Args:
        project_slug: Project identifier
        token_id: CoinGecko token ID

    Returns:
        Tuple of (flag_triggered, inflow_pct_of_supply)

    Note:
        Requires blockchain data from Glassnode, Nansen, or on-chain indexer.
    """
    try:
        # TODO: Integrate Glassnode API or similar exchange flow data
        # url = f'https://api.glassnode.com/v1/metrics/exchange/inflow_sum'
        # params = {'a': token_id, 'i': '24h', 'api_key': GLASSNODE_KEY}
        # response = requests.get(url, params=params)
        # Calculate net inflow vs circulating supply

        # Mock data for now
        import random
        inflow_pct = random.uniform(0, 1)

        triggered = inflow_pct >= 0.5
        logger.debug(f"[{project_slug}] Exchange inflow: {inflow_pct:.2f}% of supply (trigger: {triggered})")
        return triggered, inflow_pct

    except Exception as e:
        logger.error(f"Error checking exchange inflow for {project_slug}: {e}")
        return False, 0.0


def check_insider_activity(project_slug: str, token_id: str) -> Tuple[bool, Dict]:
    """
    Check for insider wallet abnormal activity.

    Args:
        project_slug: Project identifier
        token_id: CoinGecko token ID

    Returns:
        Tuple of (flag_triggered, activity_summary_dict)

    Note:
        Requires access to project-specific insider wallet tracking.
        May include team wallets, founder wallets, treasury movements.
    """
    try:
        # TODO: Implement insider wallet tracking
        # This could involve:
        # 1. Maintaining a database of known insider addresses
        # 2. Monitoring on-chain movements from these addresses
        # 3. Cross-referencing with public transaction data
        # 4. Detecting anomalous activity patterns

        # Mock data for now
        activity = {
            'wallet_count': 0,
            'total_movement': 0,
            'anomalies_detected': 0
        }

        triggered = False
        logger.debug(f"[{project_slug}] Insider activity: {triggered}")
        return triggered, activity

    except Exception as e:
        logger.error(f"Error checking insider activity for {project_slug}: {e}")
        return False, {}


# ============================================================================
# MAIN MONITORING FUNCTION
# ============================================================================

def check_project(project_slug: str, token_id: str) -> Dict:
    """
    Check all 5 forensic triggers for a project.

    Args:
        project_slug: Project identifier (e.g., 'btc')
        token_id: CoinGecko token ID (e.g., 'bitcoin')

    Returns:
        Dictionary containing check results and flag count
    """
    logger.info(f"Checking forensic triggers for {project_slug}...")

    # Run all checks
    price_flag, price_change = check_price_volatility(project_slug, token_id)
    volume_flag, volume_ratio = check_volume_anomaly(project_slug, token_id)
    whale_flag, whale_pct = check_whale_movement(project_slug, token_id)
    exchange_flag, exchange_pct = check_exchange_inflow(project_slug, token_id)
    insider_flag, insider_activity = check_insider_activity(project_slug, token_id)

    # Count flags
    flag_count = sum([price_flag, volume_flag, whale_flag, exchange_flag, insider_flag])

    result = {
        'project_slug': project_slug,
        'token_id': token_id,
        'timestamp': datetime.utcnow().isoformat(),
        'flags': {
            'price_volatility': {
                'triggered': price_flag,
                'value': price_change,     # relative deviation from market avg
                'market_avg_24h': _get_cached_benchmark(),
                'threshold': 10.0,         # CRO-002: ±10% relative deviation
                'method': 'relative_deviation',
            },
            'volume_anomaly': {
                'triggered': volume_flag,
                'value': volume_ratio,
                'threshold': 300.0
            },
            'whale_movement': {
                'triggered': whale_flag,
                'value': whale_pct,
                'threshold': 1.0
            },
            'exchange_inflow': {
                'triggered': exchange_flag,
                'value': exchange_pct,
                'threshold': 0.5
            },
            'insider_activity': {
                'triggered': insider_flag,
                'details': insider_activity
            }
        },
        'flag_count': flag_count
    }

    return result


def log_only(result: Dict) -> None:
    """Log check result with no escalation (0 flags)."""
    logger.info(f"[{result['project_slug']}] No flags triggered - logging only")


def alert_cro(result: Dict) -> None:
    """Alert CRO team (1 flag)."""
    logger.warning(f"[{result['project_slug']}] ALERT: 1 flag triggered - notifying CRO team")
    logger.warning(f"  Triggered flags:")
    for flag_name, flag_data in result['flags'].items():
        if flag_data.get('triggered') or (flag_name == 'insider_activity' and flag_data.get('details')):
            logger.warning(f"    - {flag_name}")


def request_forensic(result: Dict) -> None:
    """Request forensic report (2+ flags)."""
    logger.critical(f"[{result['project_slug']}] CRITICAL: {result['flag_count']} flags triggered - requesting forensic report")
    logger.critical(f"  Triggered flags:")
    for flag_name, flag_data in result['flags'].items():
        if flag_data.get('triggered') or (flag_name == 'insider_activity' and flag_data.get('details')):
            logger.critical(f"    - {flag_name}")


def route_escalation(result: Dict) -> None:
    """Route result to appropriate escalation level."""
    flag_count = result['flag_count']

    if flag_count == 0:
        log_only(result)
    elif flag_count == 1:
        alert_cro(result)
    else:  # flag_count >= 2
        request_forensic(result)


def save_monitoring_log(results: List[Dict], output_path: Optional[str] = None) -> str:
    """
    Save monitoring results to JSON log (per process doc §4.2).

    Args:
        results: List of check results
        output_path: Path to save log file (optional)

    Returns:
        Path to saved log file
    """
    if output_path is None:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        output_path = f'forensic_monitoring_{timestamp}.json'

    log_data = {
        'run_timestamp': datetime.utcnow().isoformat(),
        'results': results,
        'summary': {
            'total_projects': len(results),
            'critical_alerts': sum(1 for r in results if r['flag_count'] >= 2),
            'warnings': sum(1 for r in results if r['flag_count'] == 1),
            'clean': sum(1 for r in results if r['flag_count'] == 0)
        }
    }

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Monitoring log saved: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to save monitoring log: {e}")
        raise


def run_daily_monitoring(projects: List[Tuple[str, str]]) -> None:
    """
    Run daily forensic monitoring for all projects.

    Args:
        projects: List of (project_slug, token_id) tuples
    """
    logger.info("="*70)
    logger.info("STARTING DAILY FORENSIC MONITORING")
    logger.info("="*70)

    # Reset market benchmark cache for this run
    reset_benchmark_cache()
    market_avg = _get_cached_benchmark()
    logger.info(f"Market benchmark 24h: {market_avg:+.2f}%")

    results = []

    for project_slug, token_id in projects:
        try:
            result = check_project(project_slug, token_id)
            results.append(result)
            route_escalation(result)
        except Exception as e:
            logger.error(f"Failed to check project {project_slug}: {e}")

    # Save monitoring log
    try:
        log_path = save_monitoring_log(results)
        logger.info(f"Monitoring log saved: {log_path}")
    except Exception as e:
        logger.error(f"Failed to save monitoring log: {e}")

    # Print summary
    logger.info("="*70)
    logger.info("DAILY MONITORING COMPLETE")
    logger.info(f"Projects checked: {len(results)}")
    critical = sum(1 for r in results if r['flag_count'] >= 2)
    warnings = sum(1 for r in results if r['flag_count'] == 1)
    clean = sum(1 for r in results if r['flag_count'] == 0)
    logger.info(f"  Critical (2+ flags): {critical}")
    logger.info(f"  Warnings (1 flag): {warnings}")
    logger.info(f"  Clean (0 flags): {clean}")
    logger.info("="*70)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for forensic monitoring."""
    parser = argparse.ArgumentParser(
        description='Daily forensic monitoring for BCE Lab projects',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python monitor_forensic.py
  python monitor_forensic.py --projects btc,eth,sol
        """
    )

    parser.add_argument(
        '--projects',
        default='btc,eth,sol,bnb,ada',
        help='Comma-separated list of projects to monitor (default: btc,eth,sol,bnb,ada)'
    )

    args = parser.parse_args()

    # Parse project list and map to token IDs
    # This is a simple mapping; in production, load from config
    token_id_map = {
        'btc': 'bitcoin',
        'eth': 'ethereum',
        'sol': 'solana',
        'bnb': 'binancecoin',
        'ada': 'cardano',
        'xrp': 'ripple',
        'doge': 'dogecoin',
        'ltc': 'litecoin',
    }

    projects = []
    for slug in args.projects.split(','):
        slug = slug.strip()
        token_id = token_id_map.get(slug, slug)
        projects.append((slug, token_id))

    # Run monitoring
    run_daily_monitoring(projects)


if __name__ == '__main__':
    main()
