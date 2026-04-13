"""
Stage 0: Master Data Collector
Orchestrates all individual collectors, persists to warehouse, and returns enriched project data.

Usage:
    from collectors.collect_all import collect_all_data
    enriched = collect_all_data(project_config)
"""

import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional

from collectors.collector_exchange import CollectorExchange
from collectors.collector_onchain import CollectorOnchain
from collectors.collector_macro import CollectorMacro
from collectors.collector_whale import CollectorWhale
from collectors.collector_fundamentals import CollectorFundamentals
from collectors.warehouse import Warehouse, get_warehouse


def _monday_of_week(d: date = None) -> date:
    """Return the Monday of the week containing date d."""
    d = d or date.today()
    return d - timedelta(days=d.weekday())


def collect_all_data(
    project_config: Dict[str, Any],
    skip_whale: bool = False,
    persist: bool = True,
) -> Dict[str, Any]:
    """
    Collect all available data for a project from multiple API sources.
    Optionally persist long-term data to Supabase warehouse.

    Args:
        project_config: Dict with at minimum:
            - coingecko_id (str): CoinGecko identifier (e.g., 'uniswap')
            - contract_address (str, optional): Token contract address
            - chain (str, optional): Blockchain name (default: 'ethereum')
            - defi_slug (str, optional): DeFiLlama slug
            - github_org (str, optional): GitHub organization/repo
            - slug (str, optional): Project slug for tracked_projects
            - name (str, optional): Project display name
            - symbol (str, optional): Token symbol
        skip_whale: Skip whale tracking (slow, requires API key)
        persist: Whether to persist data to Supabase warehouse

    Returns:
        Enriched dict with all collected data merged in.
    """
    cg_id = project_config.get('coingecko_id', '')
    contract = project_config.get('contract_address', '')
    chain = project_config.get('chain', 'ethereum')
    defi_slug = project_config.get('defi_slug', '')
    github_org = project_config.get('github_org', '')
    slug = project_config.get('slug', cg_id or 'unknown')
    name = project_config.get('name', slug.title())
    symbol = project_config.get('symbol', '')

    collected = {
        'collection_timestamp': datetime.utcnow().isoformat() + 'Z',
        'data_sources_available': [],
    }

    # ── Warehouse Setup ──────────────────────────────────────
    wh: Optional[Warehouse] = None
    project_id: Optional[str] = None
    run_id: Optional[int] = None
    records_count = 0

    if persist:
        wh = get_warehouse()
        if wh.connected:
            project_id = wh.ensure_tracked_project(
                slug=slug,
                name=name,
                symbol=symbol,
                chain=chain,
                coingecko_id=cg_id,
                website_url=project_config.get('website_url', ''),
                category=project_config.get('category', ''),
            )
            run_id = wh.start_collection_run(
                project_id=project_id,
                run_type='full',
                triggered_by='collect_all',
            )
            print(f"  [Stage 0] Warehouse connected. Project: {project_id}")
        else:
            print("  [Stage 0] Warehouse offline — collecting without persistence.")

    today = date.today()

    # ── 1. Exchange / Market Data ─────────────────────────────
    print("  [Stage 0] Collecting exchange/market data...")
    ex = CollectorExchange()
    if cg_id:
        market = ex.fetch_market_data(cg_id)
        if market:
            collected['market_data'] = market
            collected['data_sources_available'].append('exchange')

            # Persist: market snapshot (temporary, 90d)
            if wh and project_id:
                wh.insert_market_snapshot(project_id, market)
                # Also persist today's close price (long-term)
                wh.upsert_price_daily(project_id, cg_id, today, {
                    'close': market.get('current_price', 0),
                    'volume_usd': market.get('total_volume'),
                    'market_cap_usd': market.get('market_cap'),
                })
                records_count += 2

        time.sleep(1.5)  # Rate limit

        price_history = ex.fetch_price_history(cg_id, days=90)
        if price_history:
            collected['price_history_90d'] = price_history

            # Persist: historical daily prices (long-term)
            if wh and project_id and isinstance(price_history, list):
                n = wh.bulk_upsert_price_daily(project_id, cg_id, price_history)
                records_count += n
                print(f"    → Persisted {n} daily price records")

        time.sleep(1.5)

        ohlc = ex.fetch_ohlc(cg_id, days=30)
        if ohlc:
            collected['ohlc_30d'] = ohlc

        time.sleep(1.5)

    # ── 2. Macro Context ──────────────────────────────────────
    print("  [Stage 0] Collecting macro context...")
    macro = CollectorMacro()
    global_data = macro.fetch_global_data()
    if global_data:
        collected['macro_global'] = global_data
        collected['data_sources_available'].append('macro')

        # Persist: macro indicators (long-term)
        if wh:
            wh.upsert_macro_daily(today, {
                'total_market_cap_usd': global_data.get('total_market_cap_usd'),
                'total_volume_24h_usd': global_data.get('total_volume_24h_usd'),
                'btc_dominance_pct': global_data.get('btc_dominance_pct'),
                'eth_dominance_pct': global_data.get('eth_dominance_pct'),
                'active_cryptos': global_data.get('active_cryptocurrencies'),
            })
            records_count += 1

    time.sleep(1.5)

    btc = macro.fetch_btc_price()
    if btc:
        collected['btc_data'] = btc
        # Update macro with BTC price
        if wh:
            wh.upsert_macro_daily(today, {
                'btc_price_usd': btc.get('current_price'),
            })

    time.sleep(1.5)

    fg = macro.fetch_fear_greed()
    if fg:
        collected['fear_greed'] = fg
        # Update macro with fear/greed
        if wh:
            wh.upsert_macro_daily(today, {
                'fear_greed_value': fg.get('value'),
                'fear_greed_label': fg.get('classification'),
            })

    # ── 3. On-Chain Data ──────────────────────────────────────
    print("  [Stage 0] Collecting on-chain data...")
    oc = CollectorOnchain()
    onchain_metrics = {}

    if contract:
        token_info = oc.fetch_token_info(contract, chain)
        if token_info:
            collected['onchain_token_info'] = token_info
            collected['data_sources_available'].append('onchain')
            onchain_metrics['holder_count'] = token_info.get('holder_count')

        time.sleep(1)

        holders = oc.fetch_top_holders(contract, chain)
        if holders:
            collected['onchain_top_holders'] = holders

    if defi_slug:
        time.sleep(1)
        tvl = oc.fetch_protocol_tvl(defi_slug)
        if tvl:
            collected['defi_tvl'] = tvl
            onchain_metrics['tvl_usd'] = tvl.get('tvl')
            if 'onchain' not in collected['data_sources_available']:
                collected['data_sources_available'].append('onchain')

    # Persist: on-chain daily (long-term)
    if wh and project_id and onchain_metrics:
        wh.upsert_onchain_daily(project_id, today, onchain_metrics)
        records_count += 1

    # ── 4. Whale Tracking ─────────────────────────────────────
    if not skip_whale and contract:
        print("  [Stage 0] Collecting whale data...")
        wh_collector = CollectorWhale()
        transfers = wh_collector.fetch_large_transfers(contract, chain=chain)
        if transfers:
            collected['whale_transfers'] = transfers
            flow = wh_collector.estimate_exchange_flow(transfers.get('transfers', []))
            if flow:
                collected['whale_exchange_flow'] = flow
            collected['data_sources_available'].append('whale')

            # Persist: whale transfers (long-term)
            if wh and project_id:
                transfer_list = transfers.get('transfers', [])
                n = wh.insert_whale_transfers(project_id, transfer_list)
                records_count += n
                print(f"    → Persisted {n} whale transfer records")

                if flow:
                    wh.upsert_exchange_flow_daily(project_id, today, flow)
                    records_count += 1

    # ── 5. Fundamentals ───────────────────────────────────────
    print("  [Stage 0] Collecting project fundamentals...")
    fund = CollectorFundamentals()
    fundamentals = {}

    if cg_id:
        links = fund.fetch_project_links(cg_id)
        if links:
            collected['project_links'] = links
            collected['data_sources_available'].append('fundamentals')

        time.sleep(1.5)

    if github_org:
        gh = fund.fetch_github_info(github_org)
        if gh:
            collected['github_data'] = gh
            fundamentals['github_stars'] = gh.get('stars')
            fundamentals['github_forks'] = gh.get('forks')
            fundamentals['github_open_issues'] = gh.get('open_issues')
            fundamentals['github_contributors'] = gh.get('contributors')

    # Persist: fundamentals weekly (long-term)
    if wh and project_id and fundamentals:
        week_monday = _monday_of_week(today)
        wh.upsert_fundamentals_weekly(project_id, week_monday, fundamentals)
        records_count += 1

    # ── Source Tracking (redundancy audit) ─────────────────────
    source_log = []
    for collector_instance in [ex, macro, oc, fund]:
        if hasattr(collector_instance, 'get_source_log'):
            source_log.extend(collector_instance.get_source_log())
    if not skip_whale and contract:
        if hasattr(wh_collector, 'get_source_log'):
            source_log.extend(wh_collector.get_source_log())

    collected['_source_log'] = source_log

    # Count primary vs fallback usage
    primary_count = sum(1 for s in source_log if s.get('status') == 'ok')
    fallback_count = sum(1 for s in source_log if s.get('status') == 'fallback')
    failed_count = sum(1 for s in source_log if s.get('status') == 'failed')
    collected['_source_summary'] = {
        'primary_used': primary_count,
        'fallback_used': fallback_count,
        'both_failed': failed_count,
        'total_metrics': len(source_log),
    }

    # ── Summary & Audit ───────────────────────────────────────
    n_sources = len(collected['data_sources_available'])
    print(f"  [Stage 0] Collection complete: {n_sources} data sources available")
    print(f"             Sources: {', '.join(collected['data_sources_available'])}")
    if source_log:
        print(f"             Redundancy: {primary_count} primary, {fallback_count} fallback, {failed_count} failed")
        for entry in source_log:
            status_icon = '✓' if entry['status'] == 'ok' else ('⚠' if entry['status'] == 'fallback' else '✗')
            print(f"               {status_icon} {entry['metric']}: {entry['source']} ({entry['status']})")

    if wh and run_id:
        wh.finish_collection_run(
            run_id=run_id,
            status='success',
            sources=collected['data_sources_available'],
            records_inserted=records_count,
        )
        print(f"             Records persisted: {records_count}")

    return collected


if __name__ == '__main__':
    # Test with Uniswap
    config = {
        'coingecko_id': 'uniswap',
        'contract_address': '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984',
        'chain': 'ethereum',
        'defi_slug': 'uniswap',
        'github_org': 'Uniswap',
        'slug': 'uniswap',
        'name': 'Uniswap',
        'symbol': 'UNI',
    }
    data = collect_all_data(config, skip_whale=True, persist=True)
    print(f"\nCollected keys: {list(data.keys())}")
    if 'market_data' in data:
        md = data['market_data']
        print(f"UNI Price: ${md.get('current_price', 'N/A')}")
        print(f"Market Cap: ${md.get('market_cap', 'N/A'):,.0f}")
    if 'macro_global' in data:
        mg = data['macro_global']
        print(f"Total Crypto Market: ${mg.get('total_market_cap_usd', 'N/A'):,.0f}")
    if 'fear_greed' in data:
        fg_data = data['fear_greed']
        print(f"Fear & Greed: {fg_data.get('value', 'N/A')} ({fg_data.get('classification', 'N/A')})")
