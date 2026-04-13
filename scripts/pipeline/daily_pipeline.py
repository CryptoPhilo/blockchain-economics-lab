"""
BCE Universal Coverage — Daily Pipeline Orchestrator
=====================================================
Executes the full Phase A-F daily pipeline:

    Phase A (06:00 UTC): Token list collection
    Phase B (07:00 UTC): Market data collection
    Phase C (08:00 UTC): Transparency scan (rotated)
    Phase D (09:00 UTC): Triage — grade + report decision
    Phase E (09:30 UTC): Report queue building
    Phase F (10:00 UTC): Publishing + notifications

Usage:
    # Full pipeline
    python daily_pipeline.py

    # Specific phases only
    python daily_pipeline.py --phases A,B,D

    # Limit token count (for testing)
    python daily_pipeline.py --limit 50

    # Dry run (no DB writes)
    python daily_pipeline.py --dry-run
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure pipeline directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    COINGECKO_BATCH_SIZE,
    TRANSPARENCY_SCAN_ROTATION_DAYS,
    MAX_DAILY_REPORTS,
    FORENSIC_AUTO_TRIGGERS,
    OUTPUT_DIR,
)
from collectors.collector_tokenlist import CollectorTokenList
from collectors.collector_transparency import CollectorTransparency
from collectors.collector_transparency_enhanced import EnhancedTransparencyScanner
from triage import TriageEngine, TriageResult
from report_queue import ReportQueue


# Supabase client (optional, for persistence)
try:
    from supabase import create_client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False


class DailyPipeline:
    """
    Orchestrates the daily Universal Coverage pipeline.
    Each phase is independent and can be run individually or as a full sequence.
    """

    def __init__(
        self,
        supabase_url: str = None,
        supabase_key: str = None,
        dry_run: bool = False,
        limit: int = None,
    ):
        self.dry_run = dry_run
        self.limit = limit
        self.db = None

        # Initialize Supabase
        url = supabase_url or os.environ.get('SUPABASE_URL', '')
        key = supabase_key or os.environ.get('SUPABASE_SERVICE_KEY', '')
        if HAS_SUPABASE and url and key and not dry_run:
            try:
                self.db = create_client(url, key)
                print("  [Pipeline] Supabase connected")
            except Exception as e:
                print(f"  [Pipeline] Supabase failed: {e}")

        # Pipeline state (passed between phases)
        self.tokens: List[Dict] = []
        self.new_listings: List[Dict] = []
        self.delistings: List[str] = []
        self.market_data: Dict[str, Dict] = {}  # slug -> market data
        self.transparency_scans: Dict[str, Dict] = {}  # slug -> scan result
        self.triage_results: List[TriageResult] = []
        self.grade_changes: List[Dict] = []
        self.report_queue: List[Dict] = []

        # Stats
        self.stats = {
            'started_at': datetime.utcnow().isoformat() + 'Z',
            'phases_run': [],
        }

    def run(self, phases: str = 'ABCDEF'):
        """
        Execute specified phases of the daily pipeline.

        Args:
            phases: String of phase letters to run (e.g., 'ABCDEF' for all)
        """
        print("\n" + "=" * 70)
        print("  BCE Universal Coverage — Daily Pipeline")
        print(f"  Date: {date.today().isoformat()}")
        print(f"  Phases: {phases}")
        print(f"  Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        if self.limit:
            print(f"  Token limit: {self.limit}")
        print("=" * 70)

        phase_map = {
            'A': ('Token List Collection', self.phase_a_token_list),
            'B': ('Market Data Collection', self.phase_b_market_data),
            'C': ('Transparency Scan', self.phase_c_transparency),
            'D': ('Triage', self.phase_d_triage),
            'E': ('Report Queue', self.phase_e_report_queue),
            'F': ('Publishing', self.phase_f_publish),
        }

        for letter in phases.upper():
            if letter in phase_map:
                name, func = phase_map[letter]
                print(f"\n{'─' * 70}")
                print(f"  Phase {letter}: {name}")
                print(f"{'─' * 70}")
                start = time.time()
                try:
                    func()
                    elapsed = time.time() - start
                    print(f"  Phase {letter} completed in {elapsed:.1f}s")
                    self.stats['phases_run'].append({
                        'phase': letter,
                        'name': name,
                        'duration_seconds': round(elapsed, 1),
                        'status': 'success',
                    })
                except Exception as e:
                    elapsed = time.time() - start
                    print(f"  Phase {letter} FAILED after {elapsed:.1f}s: {e}")
                    self.stats['phases_run'].append({
                        'phase': letter,
                        'name': name,
                        'duration_seconds': round(elapsed, 1),
                        'status': 'failed',
                        'error': str(e),
                    })

        self.stats['finished_at'] = datetime.utcnow().isoformat() + 'Z'
        self._print_summary()
        return self.stats

    # ═══════════════════════════════════════════════════════════
    # PHASE A: Token List Collection
    # ═══════════════════════════════════════════════════════════

    def phase_a_token_list(self):
        """
        Collect full list of CEX-traded tokens from CoinGecko.
        Detect new listings and delistings.
        """
        ctl = CollectorTokenList()
        result = ctl.collect()

        self.tokens = result.get('tokens', [])
        self.new_listings = result.get('new_listings', [])
        self.delistings = result.get('delistings', [])

        # Apply limit for testing
        if self.limit and len(self.tokens) > self.limit:
            self.tokens = self.tokens[:self.limit]
            print(f"  [Phase A] Limited to top {self.limit} tokens")

        print(f"  [Phase A] {len(self.tokens)} tokens, "
              f"{len(self.new_listings)} new, "
              f"{len(self.delistings)} delisted")

    # ═══════════════════════════════════════════════════════════
    # PHASE B: Market Data Collection
    # ═══════════════════════════════════════════════════════════

    def phase_b_market_data(self):
        """
        Collect market data for all tokens and store in market_data_daily.
        Tokens already come with market data from Phase A (CoinGecko /coins/markets).
        """
        if not self.tokens:
            print("  [Phase B] No tokens — run Phase A first")
            return

        count = 0
        batch_rows = []

        for token in self.tokens:
            slug = token.get('id', '')
            self.market_data[slug] = token

            if not self.dry_run and self.db:
                batch_rows.append({
                    'slug': slug,
                    'coingecko_id': slug,
                    'price_usd': token.get('current_price'),
                    'market_cap': token.get('market_cap'),
                    'volume_24h': token.get('total_volume'),
                    'change_24h': token.get('price_change_percentage_24h'),
                    'change_7d': token.get('price_change_percentage_7d_in_currency'),
                    'change_30d': token.get('price_change_percentage_30d_in_currency'),
                    'circulating_supply': token.get('circulating_supply'),
                    'total_supply': token.get('total_supply'),
                    'fdv': token.get('fully_diluted_valuation'),
                    'ath': token.get('ath'),
                    'atl': token.get('atl'),
                    'recorded_at': date.today().isoformat(),
                })
            count += 1

        # Batch upsert to market_data_daily
        if batch_rows and self.db:
            try:
                # Upsert in batches of 500
                for i in range(0, len(batch_rows), 500):
                    batch = batch_rows[i:i+500]
                    self.db.table('market_data_daily').upsert(
                        batch,
                        on_conflict='slug,recorded_at'
                    ).execute()
                print(f"  [Phase B] Persisted {len(batch_rows)} market snapshots to DB")
            except Exception as e:
                print(f"  [Phase B] DB persist failed: {e}")

        print(f"  [Phase B] {count} tokens with market data indexed")

        # Detect anomalies
        anomaly_count = 0
        for slug, token in self.market_data.items():
            change = abs(token.get('price_change_percentage_24h', 0) or 0)
            if change > FORENSIC_AUTO_TRIGGERS['price_change_24h_pct']:
                anomaly_count += 1

        if anomaly_count:
            print(f"  [Phase B] {anomaly_count} price anomalies detected (>±{FORENSIC_AUTO_TRIGGERS['price_change_24h_pct']}%)")

    # ═══════════════════════════════════════════════════════════
    # PHASE C: Transparency Scan
    # ═══════════════════════════════════════════════════════════

    def phase_c_transparency(self):
        """
        Run transparency scans on a rotation subset of tokens.
        Full scan of all ~2500 tokens takes ~5 days (500/day).
        """
        if not self.tokens:
            print("  [Phase C] No tokens — run Phase A first")
            return

        # Load existing scans from DB
        existing_scans = self._load_existing_transparency()

        # Determine today's rotation subset
        today_index = date.today().toordinal() % TRANSPARENCY_SCAN_ROTATION_DAYS
        rotation_tokens = [
            t for i, t in enumerate(self.tokens)
            if i % TRANSPARENCY_SCAN_ROTATION_DAYS == today_index
        ]

        # Always scan new listings (priority)
        new_slugs = {t['id'] for t in self.new_listings}
        priority_tokens = [t for t in self.tokens if t['id'] in new_slugs]
        rotation_tokens = priority_tokens + [
            t for t in rotation_tokens if t['id'] not in new_slugs
        ]

        print(f"  [Phase C] Rotation day {today_index + 1}/{TRANSPARENCY_SCAN_ROTATION_DAYS}")
        print(f"  [Phase C] Scanning {len(rotation_tokens)} tokens "
              f"({len(priority_tokens)} new listings + {len(rotation_tokens) - len(priority_tokens)} rotation)")

        # Use existing scans for tokens not in today's rotation
        self.transparency_scans = dict(existing_scans)

        # Scan rotation subset
        # Use Enhanced scanner for top tokens (market_cap_rank <= 200)
        # Use base scanner for the rest (faster, less API calls)
        ct = CollectorTransparency()
        enhanced = EnhancedTransparencyScanner()
        scanned = 0

        for token in rotation_tokens:
            slug = token['id']
            rank = token.get('market_cap_rank', 9999) or 9999
            try:
                if rank <= 200:
                    # Enhanced scan: website crawling + existing collectors
                    scan = enhanced.quick_scan(slug, market_token=token)
                    scan_type = 'enhanced'
                else:
                    # Base scan: website crawling only
                    scan = ct.scan(slug, market_token=token)
                    scan_type = 'base'

                self.transparency_scans[slug] = scan

                # Persist to DB
                if not self.dry_run and self.db:
                    self._persist_transparency(scan)

                scanned += 1
                if scanned % 10 == 0:
                    score = scan.get('transparency_score', 0)
                    label = scan.get('transparency_label', '?')
                    print(f"    [{scanned}/{len(rotation_tokens)}] {slug}: "
                          f"{score}/30 ({label}) [{scan_type}]")

                time.sleep(2)  # Rate limit

            except Exception as e:
                print(f"    Failed to scan {slug}: {e}")

        print(f"  [Phase C] Scanned {scanned} tokens today")
        print(f"  [Phase C] Total transparency data: {len(self.transparency_scans)} tokens")

        # Phase C.5: Execute pending re-scans
        from rescan_manager import RescanManager
        rescan_mgr = RescanManager()
        pending = rescan_mgr.get_pending_rescans()
        if pending:
            print(f"\n  [Phase C.5] Executing {len(pending)} pending re-scans...")
            rescan_results = rescan_mgr.execute_rescans(
                market_data=self.market_data,
                max_rescans=min(len(pending), 10),
            )
            # Merge re-scan results into transparency_scans
            for rr in rescan_results:
                if rr.get('status') == 'completed' and rr.get('upgraded'):
                    slug = rr['slug']
                    # Re-scan result will be picked up in Phase D
                    print(f"    → {slug} UPGRADED to {rr['new_report_decision']}")
        else:
            print(f"  [Phase C.5] No pending re-scans")

    # ═══════════════════════════════════════════════════════════
    # PHASE D: Triage
    # ═══════════════════════════════════════════════════════════

    def phase_d_triage(self):
        """
        Run triage engine on all tokens: assign grades + report decisions.
        Detect grade changes from previous day.
        """
        if not self.market_data:
            print("  [Phase D] No market data — run Phase B first")
            return

        engine = TriageEngine()

        # Load previous ratings for change detection
        old_ratings = self._load_previous_ratings()

        # Evaluate all tokens
        market_tokens = list(self.market_data.values())
        self.triage_results = engine.evaluate_batch(market_tokens, self.transparency_scans)

        # Detect grade changes
        self.grade_changes = engine.detect_grade_changes(self.triage_results, old_ratings)

        # Print summary
        summary = engine.summarize(self.triage_results)
        print(f"\n  [Phase D] Triage Summary:")
        print(f"    Total tokens: {summary['total']}")
        print(f"    Average score: {summary.get('avg_total_score', 0)}")
        print(f"    Grade distribution: {summary.get('grade_distribution', {})}")
        print(f"    Decision distribution: {summary.get('decision_distribution', {})}")
        print(f"    Forensic alerts: {summary.get('forensic_alerts', 0)}")
        print(f"    Grade changes: {len(self.grade_changes)}")

        # Persist to DB
        if not self.dry_run and self.db:
            self._persist_triage_results()
            self._persist_grade_changes()

    # ═══════════════════════════════════════════════════════════
    # PHASE E: Report Queue
    # ═══════════════════════════════════════════════════════════

    def phase_e_report_queue(self):
        """
        Build the daily report generation queue based on triage results.
        """
        if not self.triage_results:
            print("  [Phase E] No triage results — run Phase D first")
            return

        rq = ReportQueue()

        # Get existing reports info for staleness check
        existing_reports = self._load_existing_reports()

        self.report_queue = rq.build_queue(
            triage_results=self.triage_results,
            existing_reports=existing_reports,
            max_daily=MAX_DAILY_REPORTS,
        )

        summary = rq.summarize_queue(self.report_queue)
        print(f"\n  [Phase E] Report Queue:")
        print(f"    Total queued: {summary.get('total', 0)}")
        print(f"    By priority: {summary.get('by_priority', {})}")
        print(f"    Report types: {summary.get('report_types', {})}")

        # Save queue to file for report generators
        queue_path = os.path.join(OUTPUT_DIR, 'daily_report_queue.json')
        try:
            serializable_queue = []
            for item in self.report_queue:
                q = dict(item)
                # Convert TriageResult to dict
                if 'triage_result' in q and hasattr(q['triage_result'], 'to_dict'):
                    q['triage_result'] = q['triage_result'].to_dict()
                serializable_queue.append(q)

            with open(queue_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_queue, f, indent=2, ensure_ascii=False, default=str)
            print(f"    Queue saved: {queue_path}")
        except Exception as e:
            print(f"    Queue save failed: {e}")

    # ═══════════════════════════════════════════════════════════
    # PHASE F: Publishing
    # ═══════════════════════════════════════════════════════════

    def phase_f_publish(self):
        """
        Publish updated ratings, generate content for marketing channels.
        """
        if not self.triage_results:
            print("  [Phase F] No triage results — run Phase D first")
            return

        # 1. Save full ratings snapshot
        ratings_path = os.path.join(OUTPUT_DIR, f'ratings_{date.today().isoformat()}.json')
        try:
            ratings_data = [r.to_dict() for r in self.triage_results]
            with open(ratings_path, 'w', encoding='utf-8') as f:
                json.dump(ratings_data, f, indent=2, ensure_ascii=False, default=str)
            print(f"  [Phase F] Ratings snapshot: {ratings_path}")
        except Exception as e:
            print(f"  [Phase F] Ratings save failed: {e}")

        # 2. Grade Movers report
        if self.grade_changes:
            movers_path = os.path.join(OUTPUT_DIR, f'grade_movers_{date.today().isoformat()}.json')
            with open(movers_path, 'w', encoding='utf-8') as f:
                json.dump(self.grade_changes, f, indent=2, ensure_ascii=False, default=str)
            print(f"  [Phase F] Grade movers: {len(self.grade_changes)} changes")
            for change in self.grade_changes[:5]:
                print(f"    {change['slug']}: {change['old_grade']} → {change['new_grade']}")

        # 3. New listings report
        if self.new_listings:
            new_path = os.path.join(OUTPUT_DIR, f'new_listings_{date.today().isoformat()}.json')
            new_data = [{
                'slug': t['id'],
                'symbol': t.get('symbol', '').upper(),
                'name': t.get('name', ''),
                'price': t.get('current_price'),
                'market_cap': t.get('market_cap'),
            } for t in self.new_listings[:20]]
            with open(new_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)
            print(f"  [Phase F] New listings: {len(self.new_listings)}")

        # 4. Forensic alerts
        forensic_alerts = [
            r for r in self.triage_results
            if any(r.forensic_flags.values())
        ]
        if forensic_alerts:
            alerts_path = os.path.join(OUTPUT_DIR, f'forensic_alerts_{date.today().isoformat()}.json')
            alerts_data = [{
                'slug': r.slug,
                'symbol': r.token_symbol,
                'grade': r.bce_grade,
                'flags': r.forensic_flags,
                'change_24h': r.change_24h,
            } for r in forensic_alerts]
            with open(alerts_path, 'w', encoding='utf-8') as f:
                json.dump(alerts_data, f, indent=2, ensure_ascii=False, default=str)
            print(f"  [Phase F] Forensic alerts: {len(forensic_alerts)} tokens flagged")

        print(f"  [Phase F] Publishing complete")

    # ═══════════════════════════════════════════════════════════
    # DB HELPERS
    # ═══════════════════════════════════════════════════════════

    def _load_existing_transparency(self) -> Dict[str, Dict]:
        """Load existing transparency scans from DB."""
        if not self.db:
            return {}
        try:
            resp = self.db.table('transparency_scan').select('*').execute()
            return {row['slug']: row for row in (resp.data or [])}
        except Exception:
            return {}

    def _load_previous_ratings(self) -> Dict[str, Dict]:
        """Load previous day's ratings from DB."""
        if not self.db:
            return {}
        try:
            resp = self.db.table('universal_ratings').select(
                'slug, bce_grade, transparency_label, total_score'
            ).execute()
            return {row['slug']: row for row in (resp.data or [])}
        except Exception:
            return {}

    def _load_existing_reports(self) -> Dict[str, Dict]:
        """Load existing report metadata for staleness check."""
        if not self.db:
            return {}
        try:
            resp = self.db.table('project_reports').select(
                'slug, report_type, version, updated_at'
            ).execute()
            reports = {}
            for row in (resp.data or []):
                slug = row.get('slug', '')
                if slug not in reports:
                    reports[slug] = {}
                reports[slug][row.get('report_type', '')] = {
                    'version': row.get('version'),
                    'updated_at': row.get('updated_at'),
                }
            return reports
        except Exception:
            return {}

    def _persist_transparency(self, scan: Dict):
        """Upsert a single transparency scan to DB."""
        if not self.db:
            return
        try:
            row = {
                'slug': scan['slug'],
                'team_public': scan.get('team_public', False),
                'team_info_source': scan.get('team_info_source'),
                'code_opensource': scan.get('code_opensource', False),
                'github_org': scan.get('github_org'),
                'github_repo_count': scan.get('github_repo_count', 0),
                'github_last_commit': scan.get('github_last_commit'),
                'github_stars': scan.get('github_stars', 0),
                'github_contributors': scan.get('github_contributors', 0),
                'token_distribution_public': scan.get('token_distribution_public', False),
                'top10_holder_pct': scan.get('top10_holder_pct'),
                'total_holders': scan.get('total_holders'),
                'audit_completed': scan.get('audit_completed', False),
                'audit_provider': scan.get('audit_provider'),
                'contract_verified': scan.get('contract_verified', False),
                'contract_address': scan.get('contract_address'),
                'website_url': scan.get('website_url'),
                'transparency_score': scan.get('transparency_score', 0),
                'scanned_at': scan.get('scanned_at', datetime.utcnow().isoformat()),
            }
            self.db.table('transparency_scan').upsert(
                row, on_conflict='slug'
            ).execute()
        except Exception as e:
            print(f"    DB persist transparency failed for {scan.get('slug')}: {e}")

    def _persist_triage_results(self):
        """Batch upsert triage results to universal_ratings."""
        if not self.db or not self.triage_results:
            return
        try:
            rows = []
            for r in self.triage_results:
                rows.append({
                    'slug': r.slug,
                    'coingecko_id': r.coingecko_id,
                    'token_symbol': r.token_symbol,
                    'token_name': r.token_name,
                    'chain': r.chain,
                    'contract_address': r.contract_address,
                    'transparency_score': r.transparency_score,
                    'transparency_label': r.transparency_label,
                    'maturity_score': r.maturity_score,
                    'total_score': r.total_score,
                    'bce_grade': r.bce_grade,
                    'report_decision': r.report_decision,
                    'data_availability': json.dumps(r.data_availability),
                    'forensic_flags': json.dumps(r.forensic_flags),
                    'price_usd': r.price_usd,
                    'market_cap': r.market_cap,
                    'volume_24h': r.volume_24h,
                    'change_24h': r.change_24h,
                    'triaged_at': r.triaged_at,
                    'updated_at': datetime.utcnow().isoformat(),
                })

            # Batch upsert (500 at a time)
            for i in range(0, len(rows), 500):
                batch = rows[i:i+500]
                self.db.table('universal_ratings').upsert(
                    batch, on_conflict='slug'
                ).execute()

            print(f"  [Phase D] Persisted {len(rows)} ratings to DB")
        except Exception as e:
            print(f"  [Phase D] DB persist ratings failed: {e}")

    def _persist_grade_changes(self):
        """Insert grade changes into grade_history."""
        if not self.db or not self.grade_changes:
            return
        try:
            self.db.table('grade_history').insert(self.grade_changes).execute()
            print(f"  [Phase D] Persisted {len(self.grade_changes)} grade changes")
        except Exception as e:
            print(f"  [Phase D] DB persist grade changes failed: {e}")

    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════

    def _print_summary(self):
        """Print final pipeline summary."""
        print(f"\n{'=' * 70}")
        print(f"  Daily Pipeline Complete")
        print(f"{'=' * 70}")
        print(f"  Tokens:       {len(self.tokens)}")
        print(f"  New listings: {len(self.new_listings)}")
        print(f"  Triage:       {len(self.triage_results)} rated")
        print(f"  Changes:      {len(self.grade_changes)} grade changes")
        print(f"  Queue:        {len(self.report_queue)} reports to generate")
        print(f"  Mode:         {'DRY RUN' if self.dry_run else 'LIVE'}")

        for phase in self.stats['phases_run']:
            status = '✓' if phase['status'] == 'success' else '✗'
            print(f"  {status} Phase {phase['phase']}: {phase['name']} ({phase['duration_seconds']}s)")

        print(f"{'=' * 70}\n")


def main():
    parser = argparse.ArgumentParser(description='BCE Universal Coverage Daily Pipeline')
    parser.add_argument('--phases', default='ABCDEF', help='Phases to run (default: ABCDEF)')
    parser.add_argument('--limit', type=int, default=None, help='Limit token count (for testing)')
    parser.add_argument('--dry-run', action='store_true', help='No DB writes')
    parser.add_argument('--supabase-url', default=None, help='Supabase URL')
    parser.add_argument('--supabase-key', default=None, help='Supabase service key')
    args = parser.parse_args()

    pipeline = DailyPipeline(
        supabase_url=args.supabase_url,
        supabase_key=args.supabase_key,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    stats = pipeline.run(phases=args.phases)

    # Save stats
    stats_path = os.path.join(OUTPUT_DIR, f'pipeline_stats_{date.today().isoformat()}.json')
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2, default=str)


if __name__ == '__main__':
    main()
