#!/usr/bin/env python3
"""
CMC Market Data Sync — Lightweight Periodic Collector
=====================================================
CMC 무료 티어(10,000크레딧/월)를 활용하여 market_data_daily 테이블을
주기적으로 업데이트하는 경량 스크립트.

크레딧 소비:
  /v1/cryptocurrency/listings/latest (limit=200) = 1 credit
  /v1/cryptocurrency/listings/latest (limit=5000) = 25 credits
  하루 1회(5000개) = 25크레딧 × 30일 = 750크레딧/월 (예산의 7.5%)

실행 모드:
  --mode full     : 상위 5,000개 전체 수집 (25 credits, 기본)
  --mode tracked  : tracked_projects만 수집 (~74개, 1 credit)
  --mode top200   : 상위 200개만 수집 (1 credit)
  --dry-run       : DB 저장 없이 테스트

예산 관리:
  일일 예산 ~300크레딧 중 full 1회(25) + tracked 3회(3) = 28크레딧/일
  월간 예산 840크레딧/월 → 무료 10,000크레딧의 8.4%

Usage:
    python cmc_market_sync.py --mode full
    python cmc_market_sync.py --mode tracked
    python cmc_market_sync.py --mode top200 --dry-run
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import requests

# ─── Configuration ───────────────────────────────────────────
CMC_BASE = 'https://pro-api.coinmarketcap.com'
CMC_API_KEY = os.environ.get('CMC_API_KEY', '')

# Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

# Rate limiting
REQUEST_INTERVAL = 2.0  # seconds between CMC API calls
MAX_RETRIES = 3
RETRY_BACKOFF = [3, 6, 12]  # seconds


# ─── CMC API Client ──────────────────────────────────────────

class CMCClient:
    """Minimal CoinMarketCap API client for market data."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-CMC_PRO_API_KEY': api_key,
            'Accept': 'application/json',
        })
        self.credits_used = 0

    def get_listings(self, start: int = 1, limit: int = 200) -> List[Dict]:
        """
        Fetch cryptocurrency listings sorted by market cap.
        Cost: 1 credit per 200 tokens.
        """
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(
                    f'{CMC_BASE}/v1/cryptocurrency/listings/latest',
                    params={
                        'start': start,
                        'limit': limit,
                        'convert': 'USD',
                        'sort': 'market_cap',
                        'sort_dir': 'desc',
                        'aux': 'num_market_pairs,date_added,platform,max_supply,'
                               'circulating_supply,total_supply',
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                # Track credits
                credit_count = data.get('status', {}).get('credit_count', 0)
                self.credits_used += credit_count

                if data.get('status', {}).get('error_code', 0) != 0:
                    msg = data['status'].get('error_message', 'Unknown error')
                    print(f"  [CMC] API error: {msg}")
                    return []

                return data.get('data', [])

            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    print(f"  [CMC] Request failed (attempt {attempt+1}): {e}")
                    print(f"  [CMC] Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  [CMC] Request failed after {MAX_RETRIES} attempts: {e}")
                    return []

        return []

    def get_listings_paginated(self, total_limit: int = 5000) -> List[Dict]:
        """
        Fetch multiple pages of listings up to total_limit.
        Uses batch size of 5000 (max per CMC request).
        """
        all_tokens = []
        batch_size = min(total_limit, 5000)
        start = 1

        while len(all_tokens) < total_limit:
            remaining = total_limit - len(all_tokens)
            fetch_limit = min(batch_size, remaining)

            print(f"  [CMC] Fetching {fetch_limit} tokens (start={start})...")
            batch = self.get_listings(start=start, limit=fetch_limit)

            if not batch:
                break

            all_tokens.extend(batch)
            print(f"  [CMC] Got {len(batch)} tokens (total: {len(all_tokens)})")

            if len(batch) < fetch_limit:
                break  # No more data

            start += len(batch)
            time.sleep(REQUEST_INTERVAL)

        return all_tokens


# ─── Supabase Client ─────────────────────────────────────────

class SupabaseClient:
    """Minimal Supabase REST client for market_data_daily upserts."""

    def __init__(self, url: str, service_key: str):
        self.base_url = url
        self.session = requests.Session()
        self.session.headers.update({
            'apikey': service_key,
            'Authorization': f'Bearer {service_key}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates,return=minimal',
        })

    def upsert_market_data(self, rows: List[Dict], batch_size: int = 500) -> int:
        """Upsert rows into market_data_daily. Returns count of rows written."""
        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            try:
                # on_conflict=slug,recorded_at for proper upsert
                resp = self.session.post(
                    f'{self.base_url}/rest/v1/market_data_daily'
                    '?on_conflict=slug,recorded_at',
                    json=batch,
                )
                if resp.status_code in (200, 201, 204):
                    total += len(batch)
                else:
                    print(f"  [DB] Upsert error (batch {i//batch_size + 1}): "
                          f"{resp.status_code} {resp.text[:200]}")
            except Exception as e:
                print(f"  [DB] Upsert exception: {e}")
        return total

    def get_tracked_projects(self) -> List[Dict]:
        """Fetch all tracked_projects with their CMC/CoinGecko IDs."""
        try:
            resp = self.session.get(
                f'{self.base_url}/rest/v1/tracked_projects',
                params={'select': 'id,slug,symbol,name,coingecko_id,cmc_id'},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"  [DB] Failed to fetch tracked_projects: {e}")
            return []


# ─── Data Transform ──────────────────────────────────────────

def cmc_to_market_row(token: Dict, slug_override: str = None) -> Dict:
    """
    Convert a CMC token listing to market_data_daily row format.

    CMC slug → market_data_daily.slug 매핑:
    기존 데이터와 호환을 위해 CMC slug을 그대로 사용.
    tracked_projects와의 JOIN은 coingecko_id 또는 slug 기반.
    """
    quote = token.get('quote', {}).get('USD', {})
    cmc_slug = token.get('slug', '')

    return {
        'slug': slug_override or cmc_slug,
        'coingecko_id': slug_override or cmc_slug,  # 호환성: 기존 JOIN 조건 유지
        'price_usd': quote.get('price'),
        'market_cap': quote.get('market_cap'),
        'volume_24h': quote.get('volume_24h'),
        'change_24h': quote.get('percent_change_24h'),
        'change_7d': quote.get('percent_change_7d'),
        'change_30d': quote.get('percent_change_30d'),
        'circulating_supply': token.get('circulating_supply'),
        'total_supply': token.get('total_supply'),
        'fdv': quote.get('fully_diluted_market_cap'),
        'ath': None,  # CMC free tier doesn't include ATH
        'atl': None,
        'recorded_at': date.today().isoformat(),
    }


def build_slug_map(tracked_projects: List[Dict], cmc_tokens: List[Dict]) -> Dict[str, str]:
    """
    Build CMC slug → preferred slug mapping.

    tracked_projects와 market_data_daily의 기존 JOIN 조건
    (md.slug = tp.coingecko_id OR md.slug = tp.slug)을 유지하기 위해,
    CMC slug을 tracked_projects의 coingecko_id 또는 slug으로 변환.

    4단계 매칭:
      1. CMC ID 직접 매칭 (가장 정확)
      2. CMC slug == coingecko_id (동일한 경우)
      3. CMC slug == tracked_projects.slug (동일한 경우)
      4. Symbol 매칭 (CMC symbol == tracked_projects.symbol, 대소문자 무시)
    """
    cmc_slug_to_preferred: Dict[str, str] = {}

    # ── Index 구축 ──
    # CMC ID → tracked_project preferred slug
    cmc_id_to_slug: Dict[int, str] = {}
    for tp in tracked_projects:
        cmc_id = tp.get('cmc_id')
        if cmc_id:
            preferred = tp.get('coingecko_id') or tp.get('slug')
            cmc_id_to_slug[int(cmc_id)] = preferred

    # CoinGecko ID index
    tp_by_cg_id = {tp['coingecko_id']: tp for tp in tracked_projects if tp.get('coingecko_id')}

    # tracked_projects slug index
    tp_by_slug = {tp['slug']: tp for tp in tracked_projects}

    # Symbol index (lowercase → preferred slug)
    # 주의: 동일 심볼 중복 가능 → 첫 번째만 사용
    tp_by_symbol: Dict[str, str] = {}
    for tp in tracked_projects:
        sym = (tp.get('symbol') or '').upper()
        if sym and sym not in tp_by_symbol:
            tp_by_symbol[sym] = tp.get('coingecko_id') or tp.get('slug')

    # ── 매칭 실행 ──
    for token in cmc_tokens:
        cmc_slug = token.get('slug', '')
        cmc_id = token.get('id')
        cmc_symbol = (token.get('symbol') or '').upper()

        if not cmc_slug:
            continue

        # 1차: CMC ID 직접 매칭
        if cmc_id and cmc_id in cmc_id_to_slug:
            cmc_slug_to_preferred[cmc_slug] = cmc_id_to_slug[cmc_id]
            continue

        # 2차: CMC slug == coingecko_id
        if cmc_slug in tp_by_cg_id:
            cmc_slug_to_preferred[cmc_slug] = cmc_slug
            continue

        # 3차: CMC slug == tracked_projects.slug
        if cmc_slug in tp_by_slug:
            preferred = tp_by_slug[cmc_slug].get('coingecko_id') or cmc_slug
            cmc_slug_to_preferred[cmc_slug] = preferred
            continue

        # 4차: Symbol 매칭 (BNB→binancecoin, XRP→ripple 등)
        if cmc_symbol and cmc_symbol in tp_by_symbol:
            cmc_slug_to_preferred[cmc_slug] = tp_by_symbol[cmc_symbol]

    return cmc_slug_to_preferred


# ─── Execution Modes ─────────────────────────────────────────

def mode_full(cmc: CMCClient, db: SupabaseClient, dry_run: bool = False) -> Dict:
    """
    Full sync: 상위 5,000개 토큰 수집.
    크레딧: ~25 (5000 / 200)
    """
    print("\n=== CMC Market Sync: FULL MODE (top 5,000) ===")

    tokens = cmc.get_listings_paginated(total_limit=5000)
    if not tokens:
        print("  [FAIL] No tokens fetched")
        return {'mode': 'full', 'fetched': 0, 'written': 0}

    # Build slug mapping from tracked_projects
    tracked = db.get_tracked_projects() if not dry_run else []
    slug_map = build_slug_map(tracked, tokens) if tracked else {}

    rows = []
    seen_slugs = set()
    duplicates = 0
    for token in tokens:
        cmc_slug = token.get('slug', '')
        preferred_slug = slug_map.get(cmc_slug, cmc_slug)
        # Deduplicate: 같은 slug이 여러 번 나올 수 있음 (symbol 매핑 충돌)
        # 시총이 높은 것(먼저 등장)을 우선
        if preferred_slug in seen_slugs:
            duplicates += 1
            continue
        seen_slugs.add(preferred_slug)
        rows.append(cmc_to_market_row(token, slug_override=preferred_slug))

    print(f"  [CMC] {len(tokens)} tokens fetched, {len(slug_map)} mapped to tracked_projects")
    if duplicates:
        print(f"  [CMC] {duplicates} duplicate slugs removed (kept highest market cap)")
    print(f"  [CMC] {len(rows)} unique rows prepared")
    print(f"  [CMC] Credits used: {cmc.credits_used}")

    written = 0
    if not dry_run:
        written = db.upsert_market_data(rows)
        print(f"  [DB] {written} rows upserted to market_data_daily")
    else:
        print(f"  [DRY] Would upsert {len(rows)} rows")
        # Show sample
        for r in rows[:5]:
            print(f"    {r['slug']:>20} | ${r['price_usd'] or 0:>12,.4f} | "
                  f"MCap: ${r['market_cap'] or 0:>16,.0f} | "
                  f"24h: {r['change_24h'] or 0:>+7.2f}%")

    return {'mode': 'full', 'fetched': len(tokens), 'written': written,
            'credits': cmc.credits_used, 'mapped': len(slug_map)}


def mode_tracked(cmc: CMCClient, db: SupabaseClient, dry_run: bool = False) -> Dict:
    """
    Tracked-only sync: tracked_projects에 등록된 프로젝트만 수집.
    상위 200개를 가져와서 tracked_projects와 매칭.
    추가로 매칭 안 된 프로젝트는 개별 처리 불필요 (대부분 top 200 안에 있음).
    크레딧: 1 (200 / 200)
    """
    print("\n=== CMC Market Sync: TRACKED MODE ===")

    tracked = db.get_tracked_projects()
    if not tracked:
        print("  [FAIL] No tracked projects found")
        return {'mode': 'tracked', 'fetched': 0, 'written': 0}

    print(f"  [DB] {len(tracked)} tracked projects loaded")

    # Fetch top 5000 to cover all tracked projects (most are within top 5000)
    tokens = cmc.get_listings_paginated(total_limit=5000)
    if not tokens:
        print("  [FAIL] No tokens fetched")
        return {'mode': 'tracked', 'fetched': 0, 'written': 0}

    slug_map = build_slug_map(tracked, tokens)

    # Build reverse lookup: find which CMC tokens match tracked projects
    # Match by: CMC ID, CMC slug == coingecko_id, CMC slug == tp.slug, symbol match
    tp_cmc_ids = {int(tp['cmc_id']) for tp in tracked if tp.get('cmc_id')}
    tp_cg_ids = {tp['coingecko_id'] for tp in tracked if tp.get('coingecko_id')}
    tp_slugs = {tp['slug'] for tp in tracked}
    tp_symbols = {tp['symbol'].lower() for tp in tracked if tp.get('symbol')}

    matched_rows = []
    matched_slugs = set()

    for token in tokens:
        cmc_id = token.get('id')
        cmc_slug = token.get('slug', '')
        cmc_symbol = token.get('symbol', '').lower()

        is_tracked = (
            cmc_id in tp_cmc_ids or
            cmc_slug in tp_cg_ids or
            cmc_slug in tp_slugs or
            cmc_symbol in tp_symbols
        )

        if is_tracked:
            preferred_slug = slug_map.get(cmc_slug, cmc_slug)
            matched_rows.append(cmc_to_market_row(token, slug_override=preferred_slug))
            matched_slugs.add(preferred_slug)

    # Report unmatched tracked projects
    all_tp_slugs = {tp.get('coingecko_id') or tp['slug'] for tp in tracked}
    unmatched = all_tp_slugs - matched_slugs

    print(f"  [CMC] {len(matched_rows)} tracked projects matched from {len(tokens)} CMC tokens")
    if unmatched:
        print(f"  [WARN] {len(unmatched)} tracked projects not found in CMC top 5000:")
        for s in sorted(unmatched)[:10]:
            print(f"    - {s}")
    print(f"  [CMC] Credits used: {cmc.credits_used}")

    written = 0
    if not dry_run:
        written = db.upsert_market_data(matched_rows)
        print(f"  [DB] {written} rows upserted")
    else:
        print(f"  [DRY] Would upsert {len(matched_rows)} rows")

    return {'mode': 'tracked', 'fetched': len(tokens), 'matched': len(matched_rows),
            'unmatched': len(unmatched), 'written': written, 'credits': cmc.credits_used}


def mode_top200(cmc: CMCClient, db: SupabaseClient, dry_run: bool = False) -> Dict:
    """
    Quick sync: 상위 200개만 수집.
    크레딧: 1
    """
    print("\n=== CMC Market Sync: TOP 200 MODE ===")

    tokens = cmc.get_listings(start=1, limit=200)
    if not tokens:
        print("  [FAIL] No tokens fetched")
        return {'mode': 'top200', 'fetched': 0, 'written': 0}

    tracked = db.get_tracked_projects() if not dry_run else []
    slug_map = build_slug_map(tracked, tokens) if tracked else {}

    rows = []
    for token in tokens:
        cmc_slug = token.get('slug', '')
        preferred_slug = slug_map.get(cmc_slug, cmc_slug)
        rows.append(cmc_to_market_row(token, slug_override=preferred_slug))

    print(f"  [CMC] {len(tokens)} tokens fetched")
    print(f"  [CMC] Credits used: {cmc.credits_used}")

    written = 0
    if not dry_run:
        written = db.upsert_market_data(rows)
        print(f"  [DB] {written} rows upserted")
    else:
        print(f"  [DRY] Would upsert {len(rows)} rows")
        for r in rows[:5]:
            print(f"    {r['slug']:>20} | ${r['price_usd'] or 0:>12,.4f} | "
                  f"MCap: ${r['market_cap'] or 0:>16,.0f}")

    return {'mode': 'top200', 'fetched': len(tokens), 'written': written,
            'credits': cmc.credits_used}


# ─── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='CMC Market Data Sync')
    parser.add_argument('--mode', choices=['full', 'tracked', 'top200'],
                        default='full', help='Collection mode')
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch but do not write to DB')
    args = parser.parse_args()

    # Validate credentials
    if not CMC_API_KEY:
        print("[ERROR] CMC_API_KEY not set. Export it or add to .env")
        sys.exit(1)

    if not args.dry_run and (not SUPABASE_URL or not SUPABASE_SERVICE_KEY):
        print("[ERROR] SUPABASE_URL and SUPABASE_SERVICE_KEY required for DB writes")
        sys.exit(1)

    # Initialize clients
    cmc = CMCClient(api_key=CMC_API_KEY)
    db = SupabaseClient(url=SUPABASE_URL, service_key=SUPABASE_SERVICE_KEY)

    # Execute
    start_time = time.time()

    modes = {
        'full': mode_full,
        'tracked': mode_tracked,
        'top200': mode_top200,
    }

    result = modes[args.mode](cmc, db, dry_run=args.dry_run)
    elapsed = time.time() - start_time

    # Summary
    print(f"\n{'='*50}")
    print(f"  CMC Market Sync Complete")
    print(f"{'='*50}")
    print(f"  Mode:     {result['mode']}")
    print(f"  Fetched:  {result.get('fetched', 0)} tokens")
    print(f"  Written:  {result.get('written', 0)} rows")
    print(f"  Credits:  {result.get('credits', 0)}")
    print(f"  Time:     {elapsed:.1f}s")
    if result.get('mapped'):
        print(f"  Mapped:   {result['mapped']} to tracked_projects")
    if result.get('unmatched'):
        print(f"  Unmatched: {result['unmatched']} tracked projects")
    print(f"{'='*50}\n")


if __name__ == '__main__':
    main()
