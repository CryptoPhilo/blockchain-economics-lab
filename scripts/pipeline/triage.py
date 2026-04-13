"""
Phase D: Triage Engine — BCE Universal Ratings
===============================================
Evaluates each project's transparency + maturity to assign:
  - BCE Grade (A/B/C/D/F/UR)
  - Transparency Label (OPEN/MOSTLY/PARTIAL/LIMITED/OPAQUE)
  - Report Decision (FULL/STANDARD/MINIMAL/SCAN_ONLY/UNRATABLE)

The Triage Engine is the gatekeeper: it determines which projects get
which level of analysis, ensuring we don't waste resources generating
reports for projects with insufficient data.

Usage:
    from triage import TriageEngine
    engine = TriageEngine()
    result = engine.evaluate(market_token, transparency_scan)
"""

import math
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    BCE_GRADE_THRESHOLDS,
    TRANSPARENCY_LABELS,
    REPORT_DECISIONS,
    UNRATABLE_TRANSPARENCY_THRESHOLD,
    MATURITY_WEIGHTS,
    FORENSIC_AUTO_TRIGGERS,
)


@dataclass
class TriageResult:
    """Output of the Triage Engine for a single project."""
    slug: str
    coingecko_id: str
    token_symbol: str
    token_name: str
    chain: Optional[str]
    contract_address: Optional[str]

    # Scores
    transparency_score: int          # 0-30
    transparency_label: str          # OPEN/MOSTLY/PARTIAL/LIMITED/OPAQUE
    maturity_score: int              # 0-70
    total_score: int                 # 0-100
    bce_grade: str                   # A/B/C/D/F/UR
    report_decision: str             # FULL/STANDARD/MINIMAL/SCAN_ONLY/UNRATABLE

    # Market snapshot
    price_usd: Optional[float]
    market_cap: Optional[float]
    volume_24h: Optional[float]
    change_24h: Optional[float]

    # Data availability flags
    data_availability: Dict[str, bool]

    # Forensic anomaly flags
    forensic_flags: Dict[str, bool]

    # Metadata
    triage_reason: str
    triaged_at: str

    def to_dict(self) -> Dict:
        return asdict(self)


class TriageEngine:
    """
    Evaluates projects and assigns BCE Grades + Report Decisions.

    The engine combines two independent assessments:
    1. Transparency Score (0-30): How much verifiable data exists?
    2. Maturity Score (0-70): How established is the project?

    Total Score = Transparency + Maturity (0-100)
    """

    def evaluate(
        self,
        market_token: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        market_avg_24h: float = 0.0,
    ) -> TriageResult:
        """
        Run triage evaluation for a single project.

        Args:
            market_token: CoinGecko market data dict (from /coins/markets)
                Must have: id, symbol, name, current_price, market_cap,
                total_volume, price_change_percentage_24h, etc.
            transparency_scan: Output from CollectorTransparency.scan()
                Must have: transparency_score, transparency_label, etc.

        Returns:
            TriageResult with grade, label, and report decision
        """
        slug = market_token.get('id', '')
        symbol = market_token.get('symbol', '').upper()
        name = market_token.get('name', '')

        # ── Transparency Score (from Phase C) ──
        t_score = transparency_scan.get('transparency_score', 0)
        t_label = transparency_scan.get('transparency_label', 'OPAQUE')

        # ── Maturity Score (calculated here from market data) ──
        m_score = self._calc_maturity_score(market_token, transparency_scan)

        # ── Total Score ──
        total = t_score + m_score

        # ── BCE Grade ──
        grade = self._assign_grade(total, t_score, m_score)

        # ── Report Decision ──
        decision, reason = self._decide_reports(total, t_score, m_score, grade)

        # ── Forensic Flags ──
        forensic_flags = self._check_forensic_flags(market_token, market_avg_24h)

        # ── Data Availability ──
        data_avail = {
            'coingecko': True,  # We have market data
            'etherscan': transparency_scan.get('contract_verified', False) or
                        transparency_scan.get('token_distribution_public', False),
            'github': transparency_scan.get('code_opensource', False),
            'defillama': False,  # Would need separate check
            'audit': transparency_scan.get('audit_completed', False),
        }

        # Extract chain/contract from transparency scan
        chain = None
        contract = transparency_scan.get('contract_address')
        platforms = market_token.get('platforms', {})
        if platforms:
            for c in ['ethereum', 'binance-smart-chain', 'polygon-pos', 'arbitrum-one']:
                if platforms.get(c):
                    chain = c
                    contract = contract or platforms[c]
                    break

        return TriageResult(
            slug=slug,
            coingecko_id=slug,
            token_symbol=symbol,
            token_name=name,
            chain=chain,
            contract_address=contract,
            transparency_score=t_score,
            transparency_label=t_label,
            maturity_score=m_score,
            total_score=total,
            bce_grade=grade,
            report_decision=decision,
            price_usd=market_token.get('current_price'),
            market_cap=market_token.get('market_cap'),
            volume_24h=market_token.get('total_volume'),
            change_24h=market_token.get('price_change_percentage_24h'),
            data_availability=data_avail,
            forensic_flags=forensic_flags,
            triage_reason=reason,
            triaged_at=datetime.utcnow().isoformat() + 'Z',
        )

    def evaluate_batch(
        self,
        market_tokens: List[Dict],
        transparency_scans: Dict[str, Dict],
        market_avg_24h: float = 0.0,
    ) -> List[TriageResult]:
        """
        Evaluate a batch of projects.

        Args:
            market_tokens: List of CoinGecko market data dicts
            transparency_scans: Dict of slug -> transparency scan result
            market_avg_24h: Market benchmark 24h change for forensic flags

        Returns:
            List of TriageResult, sorted by total_score descending
        """
        results = []
        for token in market_tokens:
            slug = token.get('id', '')
            t_scan = transparency_scans.get(slug, {
                'transparency_score': 0,
                'transparency_label': 'OPAQUE',
            })
            result = self.evaluate(token, t_scan, market_avg_24h)
            results.append(result)

        # Sort: highest score first
        results.sort(key=lambda r: r.total_score, reverse=True)
        return results

    # ═══════════════════════════════════════════════════════════
    # MATURITY SCORING
    # ═══════════════════════════════════════════════════════════

    def _calc_maturity_score(
        self,
        market_token: Dict,
        transparency_scan: Dict,
    ) -> int:
        """
        Calculate maturity score (0-70) from market data.

        Components (from config MATURITY_WEIGHTS):
          - exchange_listings: 0-15
          - volume_ratio: 0-15
          - derivatives: 0-10
          - market_cap: 0-10
          - holder_count: 0-10
          - project_age: 0-10
        """
        score = 0

        # 1. Exchange Listings (0-15)
        # We approximate from CoinGecko tickers_count or market presence
        # CoinGecko market data doesn't directly give exchange count,
        # but we can infer from trust_score or use tickers_count from detail
        tickers = market_token.get('tickers_count', 0)
        if tickers >= 11:
            score += 15
        elif tickers >= 6:
            score += 12
        elif tickers >= 4:
            score += 9
        elif tickers >= 2:
            score += 6
        elif tickers >= 1:
            score += 3
        # If tickers_count not available, estimate from market_cap rank
        elif market_token.get('market_cap_rank'):
            rank = market_token['market_cap_rank']
            if rank <= 100:
                score += 12
            elif rank <= 300:
                score += 9
            elif rank <= 500:
                score += 6
            elif rank <= 1000:
                score += 3

        # 2. Volume/MCap Ratio (0-15)
        mcap = market_token.get('market_cap', 0) or 0
        vol = market_token.get('total_volume', 0) or 0
        if mcap > 0:
            ratio = (vol / mcap) * 100  # as percentage
            if 5 <= ratio <= 30:
                score += 15  # Healthy range
            elif 2 <= ratio < 5 or 30 < ratio <= 50:
                score += 10
            elif 1 <= ratio < 2 or 50 < ratio <= 100:
                score += 5
            elif ratio > 0:
                score += 2

        # 3. Derivatives Market (0-10)
        # No direct way to check from /coins/markets.
        # Proxy: high market cap rank often correlates with derivative availability
        rank = market_token.get('market_cap_rank', 9999) or 9999
        if rank <= 50:
            score += 10
        elif rank <= 100:
            score += 7
        elif rank <= 200:
            score += 4
        elif rank <= 500:
            score += 2

        # 4. Market Cap Scale (0-10)
        if mcap >= 1_000_000_000:      # > $1B
            score += 10
        elif mcap >= 100_000_000:      # > $100M
            score += 8
        elif mcap >= 10_000_000:       # > $10M
            score += 6
        elif mcap >= 1_000_000:        # > $1M
            score += 4
        elif mcap > 0:
            score += 2

        # 5. Holder Count (0-10)
        # Use enhanced_data if available, otherwise fallback to transparency_scan
        enhanced = transparency_scan.get('enhanced_data', {})
        holders = enhanced.get('holder_count') or transparency_scan.get('total_holders', 0) or 0
        if holders >= 10_000:
            score += 10
        elif holders >= 1_000:
            score += 7
        elif holders >= 100:
            score += 4
        elif holders > 0:
            score += 2

        # 5b. TVL Bonus (0-5, from enhanced_data)
        tvl = enhanced.get('tvl', 0) or 0
        if tvl >= 1_000_000_000:       # > $1B TVL
            score += 5
        elif tvl >= 100_000_000:       # > $100M TVL
            score += 3
        elif tvl >= 10_000_000:        # > $10M TVL
            score += 1

        # 6. Project Age (0-10)
        genesis = market_token.get('genesis_date')
        if genesis:
            try:
                genesis_date = datetime.fromisoformat(genesis).date()
                age_days = (date.today() - genesis_date).days
                if age_days >= 1095:      # > 3 years
                    score += 10
                elif age_days >= 365:     # > 1 year
                    score += 7
                elif age_days >= 180:     # > 6 months
                    score += 4
                elif age_days > 0:
                    score += 2
            except (ValueError, TypeError):
                pass
        elif rank <= 200:
            # Projects in top 200 are usually > 1 year old
            score += 5

        return min(score, 70)

    # ═══════════════════════════════════════════════════════════
    # GRADE ASSIGNMENT
    # ═══════════════════════════════════════════════════════════

    def _assign_grade(self, total_score: int, transparency_score: int,
                       maturity_score: int = 0) -> str:
        """
        Assign BCE Grade based on total score.
        Exception: UR if transparency is below threshold (can't meaningfully rate).

        Maturity Override: 고성숙도 프로젝트(M≥50)는 T≥7이면 등급 부여 가능.
        이는 BTC/ETH 같은 대형 프로젝트가 웹사이트 크롤링에서 낮은 점수를
        받더라도 분석 대상에서 제외되지 않도록 하기 위함.
        """
        # Maturity override: 고성숙도 프로젝트는 더 낮은 투명성으로도 등급 부여
        effective_threshold = UNRATABLE_TRANSPARENCY_THRESHOLD  # default 10
        if maturity_score >= 50:
            effective_threshold = 7  # LIMITED 라벨 최소값
        elif maturity_score >= 40:
            effective_threshold = 9

        if transparency_score < effective_threshold:
            return 'UR'

        for grade, (low, high) in BCE_GRADE_THRESHOLDS.items():
            if grade == 'UR':
                continue
            if low <= total_score <= high:
                return grade

        return 'F'

    # ═══════════════════════════════════════════════════════════
    # REPORT DECISION
    # ═══════════════════════════════════════════════════════════

    def _decide_reports(
        self,
        total_score: int,
        transparency_score: int,
        maturity_score: int,
        grade: str = '',
    ) -> tuple:
        """
        Determine which reports can be produced for this project.
        Uses grade as additional input to handle maturity-override cases
        where total_score may not match the grade threshold exactly.

        Returns:
            (decision: str, reason: str)
        """
        # Maturity override for report decisions (고성숙도 프로젝트 배려)
        effective_t_threshold = UNRATABLE_TRANSPARENCY_THRESHOLD  # default 10
        if maturity_score >= 50:
            effective_t_threshold = 7
        elif maturity_score >= 40:
            effective_t_threshold = 9

        if transparency_score < effective_t_threshold:
            return 'UNRATABLE', (
                f"Transparency too low ({transparency_score}/30, threshold={effective_t_threshold}). "
                f"Cannot verify enough data to assign a meaningful rating."
            )

        if total_score >= 80 and transparency_score >= 19:
            return 'FULL', (
                f"High transparency ({transparency_score}/30) + high maturity ({maturity_score}/70). "
                f"All data sources available for ECON + MAT + FOR reports."
            )

        # STANDARD: C등급 이상 → 3종 리포트 (ECON + MAT + FOR)
        # grade 기반 판정으로 maturity override 케이스도 포함
        if total_score >= 50 or grade in ('A', 'B', 'C'):
            return 'STANDARD', (
                f"Transparency ({transparency_score}/30) + maturity ({maturity_score}/70). "
                f"Sufficient data for ECON + MAT + FOR reports."
            )

        # MINIMAL: D등급 → ECON + MAT 보고서
        if total_score >= 35 or grade == 'D':
            return 'MINIMAL', (
                f"Limited transparency ({transparency_score}/30) but market presence ({maturity_score}/70). "
                f"Market data sufficient for ECON + MAT reports."
            )

        if total_score >= 20:
            return 'SCAN_ONLY', (
                f"Low total score ({total_score}/100). "
                f"Only automated scan grade can be assigned. No reports producible."
            )

        return 'SCAN_ONLY', (
            f"Very low total score ({total_score}/100). "
            f"Minimal data available."
        )

    # ═══════════════════════════════════════════════════════════
    # FORENSIC FLAG DETECTION
    # ═══════════════════════════════════════════════════════════

    def _check_forensic_flags(
        self,
        market_token: Dict,
        market_avg_24h: float = 0.0,
    ) -> Dict[str, bool]:
        """
        Check if any forensic anomaly thresholds are breached.
        CRO-002 개정: 가격 이상은 시장 평균 대비 상대 변동률로 판정.

        Args:
            market_token: CoinGecko market data
            market_avg_24h: Market benchmark 24h change (default 0 for backward compat)
        """
        flags = {
            'price_anomaly': False,
            'volume_spike': False,
            'whale_alert': False,
            'exchange_flow_alert': False,
        }

        # Price anomaly: 상대 변동률 (시장 평균 대비) ≥ 15%
        change_24h = market_token.get('price_change_percentage_24h', 0) or 0
        relative_deviation = abs(change_24h - market_avg_24h)
        threshold = FORENSIC_AUTO_TRIGGERS.get('relative_deviation_24h_pct',
                    FORENSIC_AUTO_TRIGGERS.get('price_change_24h_pct', 15.0))
        if relative_deviation >= threshold:
            flags['price_anomaly'] = True

        # Volume spike: would need 7-day average comparison
        # For now, use volume/mcap ratio as proxy
        mcap = market_token.get('market_cap', 0) or 0
        vol = market_token.get('total_volume', 0) or 0
        if mcap > 0:
            vol_ratio = vol / mcap
            if vol_ratio > 1.0:  # Volume > 100% of market cap
                flags['volume_spike'] = True

        # Whale and exchange flow alerts need on-chain data (Phase C)
        # These are set during transparency scan or separate whale collector

        return flags

    # ═══════════════════════════════════════════════════════════
    # GRADE CHANGE DETECTION
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def detect_grade_changes(
        new_results: List[TriageResult],
        old_ratings: Dict[str, Dict],
    ) -> List[Dict]:
        """
        Compare new triage results against previous ratings to detect changes.

        Args:
            new_results: Current triage results
            old_ratings: Dict of slug -> {bce_grade, transparency_label, total_score}

        Returns:
            List of change records for grade_history table
        """
        changes = []
        for result in new_results:
            old = old_ratings.get(result.slug)
            if not old:
                # New entry — not a "change"
                continue

            if result.bce_grade != old.get('bce_grade') or \
               result.transparency_label != old.get('transparency_label'):
                changes.append({
                    'slug': result.slug,
                    'old_grade': old.get('bce_grade'),
                    'new_grade': result.bce_grade,
                    'old_label': old.get('transparency_label'),
                    'new_label': result.transparency_label,
                    'old_score': old.get('total_score', 0),
                    'new_score': result.total_score,
                    'reason': result.triage_reason,
                })

        return changes

    # ═══════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def summarize(results: List[TriageResult]) -> Dict:
        """Generate summary statistics for a batch of triage results."""
        total = len(results)
        if total == 0:
            return {'total': 0}

        grade_dist = {}
        decision_dist = {}
        label_dist = {}
        forensic_count = 0

        for r in results:
            grade_dist[r.bce_grade] = grade_dist.get(r.bce_grade, 0) + 1
            decision_dist[r.report_decision] = decision_dist.get(r.report_decision, 0) + 1
            label_dist[r.transparency_label] = label_dist.get(r.transparency_label, 0) + 1
            if any(r.forensic_flags.values()):
                forensic_count += 1

        return {
            'total': total,
            'grade_distribution': grade_dist,
            'decision_distribution': decision_dist,
            'label_distribution': label_dist,
            'forensic_alerts': forensic_count,
            'avg_total_score': round(sum(r.total_score for r in results) / total, 1),
            'avg_transparency': round(sum(r.transparency_score for r in results) / total, 1),
            'avg_maturity': round(sum(r.maturity_score for r in results) / total, 1),
        }


if __name__ == '__main__':
    engine = TriageEngine()

    # Test with mock data
    mock_market = {
        'id': 'uniswap',
        'symbol': 'uni',
        'name': 'Uniswap',
        'current_price': 7.5,
        'market_cap': 5_600_000_000,
        'total_volume': 280_000_000,
        'market_cap_rank': 20,
        'price_change_percentage_24h': 2.3,
        'genesis_date': '2020-09-17',
    }

    mock_transparency = {
        'transparency_score': 28,
        'transparency_label': 'OPEN',
        'team_public': True,
        'code_opensource': True,
        'token_distribution_public': True,
        'audit_completed': True,
        'contract_verified': True,
        'total_holders': 350_000,
    }

    result = engine.evaluate(mock_market, mock_transparency)

    print("═" * 50)
    print(f"  {result.token_name} ({result.token_symbol})")
    print("═" * 50)
    print(f"  Transparency: {result.transparency_score}/30 → {result.transparency_label}")
    print(f"  Maturity:     {result.maturity_score}/70")
    print(f"  Total:        {result.total_score}/100")
    print(f"  BCE Grade:    {result.bce_grade}")
    print(f"  Decision:     {result.report_decision}")
    print(f"  Reason:       {result.triage_reason}")
    print(f"  Forensic:     {result.forensic_flags}")
