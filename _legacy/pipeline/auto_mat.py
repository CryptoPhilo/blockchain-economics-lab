"""
Stage 0.5: Auto MAT (Maturity) Report Generator

Auto-generates MAT report data from market + transparency data, enabling
MAT reports to be produced without manual data entry.

Requires fields from triage_result, market_data, transparency_scan, collected_data
and outputs data compatible with gen_text_mat.py MAT report generator.
"""

import os
import sys
import json
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Import maturity levels configuration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config import MATURITY_LEVELS
except ImportError:
    MATURITY_LEVELS = {
        'nascent': {'min': 0, 'max': 25},
        'growing': {'min': 25, 'max': 50},
        'mature': {'min': 50, 'max': 75},
        'established': {'min': 75, 'max': 100}
    }

# Import category-specific objective templates and community scoring
try:
    from maturity_objectives_templates import (
        get_objectives_for_project,
        compute_community_score,
        resolve_template_key,
    )
    TEMPLATES_AVAILABLE = True
except ImportError:
    TEMPLATES_AVAILABLE = False

# Import community data collector
try:
    from collectors.collector_community import collect_community_data
    COMMUNITY_COLLECTOR_AVAILABLE = True
except ImportError:
    COMMUNITY_COLLECTOR_AVAILABLE = False


@dataclass
class StrategicObjective:
    """Represents a strategic objective with achievement metrics."""
    name: str
    weight: float
    achievement_rate: float
    milestones: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TechPillar:
    """Represents a technical capability pillar."""
    name: str
    score: float
    prev_score: float
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PeerComparison:
    """Represents a peer project for comparison."""
    name: str
    market_cap: float
    tvl: float
    maturity_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskMatrix:
    """Represents risk assessment across dimensions."""
    tech_risk: float
    market_risk: float
    regulatory_risk: float
    operational_risk: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GrowthTrajectory:
    """Represents projected growth trajectory."""
    outlook_3m: str
    milestones: List[str]
    watch_points: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutoMatGenerator:
    """
    Automatically generates MAT (Maturity) report data from market and transparency data.

    Uses data from:
    - triage_result: Initial triage analysis
    - market_data: Market metrics (price, volume, holders, etc.)
    - transparency_scan: Transparency assessment scores
    - collected_data: Additional collected metrics
    """

    # Universal strategic objectives for all projects
    STRATEGIC_OBJECTIVES = [
        'Market Adoption',
        'Technical Development',
        'Ecosystem Growth',
        'Security & Transparency',
        'Market Position & Liquidity'
    ]

    # Tech pillars to infer from available data
    TECH_PILLARS = [
        'Smart Contract Quality',
        'Code Activity',
        'Security Audits',
        'Documentation',
        'Community Engagement'
    ]

    def __init__(self):
        """Initialize the Auto MAT Generator."""
        self.maturity_levels = MATURITY_LEVELS

    def generate(
        self,
        triage_result: Dict[str, Any],
        market_data: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate MAT report data from available sources.

        v2: Now supports category-specific objective templates and community maturity scoring.

        Args:
            triage_result: Initial triage analysis results
            market_data: Market metrics (price, volume, holders, exchange listings, etc.)
            transparency_scan: Transparency assessment scores
            collected_data: Additional collected metrics and metadata

        Returns:
            Dictionary with fields required by gen_text_mat.py
        """

        # ── Collect community data if collector available ──────────
        community_raw = collected_data.get('community_data', {})
        coingecko_id = collected_data.get('coingecko_id', '') or triage_result.get('coingecko_id', '')
        categories = collected_data.get('categories', []) or triage_result.get('categories', [])

        if not community_raw and COMMUNITY_COLLECTOR_AVAILABLE and coingecko_id:
            try:
                community_raw = collect_community_data(coingecko_id)
                if community_raw.get('categories'):
                    categories = community_raw['categories']
            except Exception as e:
                print(f"[auto_mat] Community collection failed: {e}")
                community_raw = {}

        # ── Resolve category template ─────────────────────────────
        template_key = None
        template_objectives = None
        if TEMPLATES_AVAILABLE and categories:
            template_key = resolve_template_key(categories)
            template = get_objectives_for_project(categories=categories)
            template_objectives = template.get('objectives', [])

        # ── Compute community maturity score ──────────────────────
        community_score_data = {}
        if TEMPLATES_AVAILABLE and community_raw:
            community_score_data = compute_community_score(community_raw)

        # ── Generate strategic objectives (v2: category-aware) ────
        if template_objectives:
            objectives = self._generate_template_objectives(
                template_objectives, market_data, transparency_scan,
                collected_data, community_raw
            )
        else:
            objectives = self._generate_strategic_objectives(
                market_data, transparency_scan, collected_data
            )

        # ── Calculate overall maturity score ──────────────────────
        total_score = self._calculate_maturity_score_v2(
            objectives, community_score_data, market_data,
            transparency_scan, collected_data
        )

        maturity_stage = self._determine_stage(total_score)

        # Generate tech pillars from available data
        pillars = self._generate_tech_pillars(
            collected_data, transparency_scan
        )

        # Extract peer comparison data
        peers = self._extract_peer_comparison(collected_data, market_data)

        # Calculate risk matrix
        risk_matrix = self._calculate_risk_matrix(
            market_data, transparency_scan, collected_data
        )

        # Generate growth trajectory
        trajectory = self._generate_growth_trajectory(
            triage_result, market_data, collected_data
        )

        result = {
            'total_maturity_score': round(total_score, 1),
            'maturity_stage': maturity_stage,
            'strategic_objectives': [obj.to_dict() for obj in objectives],
            'tech_pillars': [pillar.to_dict() for pillar in pillars],
            'peer_comparison': [peer.to_dict() for peer in peers],
            'risk_matrix': risk_matrix.to_dict(),
            'growth_trajectory': trajectory.to_dict(),
            'auto_generated': True,
            'generated_at': datetime.now().isoformat(),
        }

        # v2 additions
        if template_key:
            result['template_key'] = template_key
            result['template_description'] = (
                get_objectives_for_project(template_key=template_key).get('description', '')
                if TEMPLATES_AVAILABLE else ''
            )
        if community_score_data:
            result['community_maturity'] = community_score_data
        if community_raw and 'coingecko_error' not in community_raw:
            result['community_data_raw'] = {
                k: v for k, v in community_raw.items()
                if k not in ('categories', 'github_repos', 'source')
            }
        if categories:
            result['categories'] = categories

        return result

    # ─────────────────────────────────────────────────────────────
    # v2: Category-aware objective generation
    # ─────────────────────────────────────────────────────────────

    def _generate_template_objectives(
        self,
        template_objectives: List[Dict],
        market_data: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        collected_data: Dict[str, Any],
        community_data: Dict[str, Any],
    ) -> List[StrategicObjective]:
        """
        Generate objectives from category-specific template with data-driven achievement rates.
        """
        objectives = []

        for tmpl in template_objectives:
            name = tmpl['name']
            weight = tmpl['weight'] / 100.0  # Convert to decimal
            kpis = tmpl.get('kpis', [])

            # Calculate achievement rate from available KPI data
            achievement = self._estimate_achievement_from_kpis(
                kpis, market_data, transparency_scan, collected_data, community_data
            )

            # Build milestones from available data
            milestones = self._build_milestones_from_kpis(
                kpis, market_data, collected_data, community_data
            )

            objectives.append(StrategicObjective(
                name=name,
                weight=weight,
                achievement_rate=achievement,
                milestones=milestones,
            ))

        return objectives

    def _estimate_achievement_from_kpis(
        self,
        kpis: List[str],
        market_data: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        collected_data: Dict[str, Any],
        community_data: Dict[str, Any],
    ) -> float:
        """
        Estimate achievement rate (0-100) from KPI availability and values.

        Uses a composite scoring approach: each available KPI contributes to the score.
        """
        scores = []

        for kpi in kpis:
            score = self._score_single_kpi(kpi, market_data, transparency_scan,
                                           collected_data, community_data)
            if score is not None:
                scores.append(score)

        if not scores:
            return 40.0  # Default when no KPI data available

        return min(100, sum(scores) / len(scores))

    def _score_single_kpi(
        self,
        kpi: str,
        market_data: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        collected_data: Dict[str, Any],
        community_data: Dict[str, Any],
    ) -> Optional[float]:
        """Score a single KPI on 0-100 scale. Returns None if data unavailable."""

        # ── Market / Exchange metrics ────────────────────────────
        if kpi == 'holder_count':
            val = market_data.get('holder_count', 0)
            if val > 0:
                return min(100, (math.log(val) / math.log(10)) * 20)
        elif kpi == 'daily_volume_usd':
            val = market_data.get('daily_volume_usd', 0)
            if val > 0:
                return min(100, (math.log(val) / math.log(1_000_000)) * 30)
        elif kpi == 'exchange_count':
            val = len(market_data.get('exchanges', []))
            return min(100, val * 10)
        elif kpi == 'market_share_pct':
            return None  # Requires category-level data

        # ── Transparency metrics ─────────────────────────────────
        elif kpi == 'transparency_score':
            return transparency_scan.get('overall_score', None)
        elif kpi in ('audit_count', 'security_audits'):
            val = len(collected_data.get('security_audits', []))
            return min(100, val * 35)
        elif kpi == 'contract_verified':
            return 80.0 if collected_data.get('contract_audited', False) else 20.0

        # ── Development metrics ──────────────────────────────────
        elif kpi in ('github_commits_30d', 'github_commits_4w'):
            val = community_data.get('github_commits_30d', 0) or collected_data.get('github_commits_last_month', 0)
            if val > 0:
                return min(100, (val / 150) * 100)
        elif kpi == 'github_contributors':
            val = community_data.get('github_contributors', 0)
            if val > 0:
                return min(100, (val / 100) * 100)

        # ── Community / Social metrics ───────────────────────────
        elif kpi == 'community_score':
            if TEMPLATES_AVAILABLE and community_data:
                cs = compute_community_score(community_data)
                return cs.get('overall_score', None)
        elif kpi == 'twitter_followers':
            val = community_data.get('twitter_followers', 0)
            if val > 0:
                return min(100, (math.log(val) / math.log(1_000_000)) * 80)
        elif kpi == 'telegram_members':
            val = community_data.get('telegram_members', 0)
            if val > 0:
                return min(100, (math.log(max(1, val)) / math.log(500_000)) * 80)
        elif kpi == 'reddit_active_48h':
            val = community_data.get('reddit_active_48h', 0)
            if val > 0:
                return min(100, (val / 5000) * 100)
        elif kpi == 'social_engagement_rate':
            val = community_data.get('social_engagement_rate', 0)
            if val > 0:
                return min(100, (val / 3.0) * 100)
        elif kpi == 'multi_platform_presence':
            val = community_data.get('multi_platform_presence', 0)
            return min(100, val * 17)

        # ── Tokenomics metrics ───────────────────────────────────
        elif kpi == 'staking_ratio':
            val = collected_data.get('staking_ratio', None)
            if val is not None:
                return min(100, val * 150)  # 67% staking → 100 score
        elif kpi in ('protocol_revenue_30d', 'protocol_fees_30d'):
            return None  # Requires DefiLlama integration (future)
        elif kpi == 'tvl_usd':
            val = collected_data.get('tvl_usd', 0)
            if val > 0:
                return min(100, (math.log(val) / math.log(1_000_000_000)) * 80)

        # ── Infrastructure metrics ───────────────────────────────
        elif kpi == 'uptime_pct':
            val = collected_data.get('uptime_pct', None)
            if val is not None:
                return val  # Already 0-100
        elif kpi == 'tps':
            return None  # Requires chain-specific data

        return None

    def _build_milestones_from_kpis(
        self,
        kpis: List[str],
        market_data: Dict[str, Any],
        collected_data: Dict[str, Any],
        community_data: Dict[str, Any],
    ) -> List[str]:
        """Build human-readable milestone descriptions from KPI values."""
        milestones = []

        for kpi in kpis:
            if kpi == 'holder_count' and market_data.get('holder_count', 0) > 0:
                milestones.append(f"{market_data['holder_count']:,} active holders")
            elif kpi == 'daily_volume_usd' and market_data.get('daily_volume_usd', 0) > 0:
                milestones.append(f"${market_data['daily_volume_usd']:,.0f} daily trading volume")
            elif kpi == 'twitter_followers' and community_data.get('twitter_followers', 0) > 0:
                milestones.append(f"{community_data['twitter_followers']:,} Twitter/X followers")
            elif kpi == 'telegram_members' and community_data.get('telegram_members', 0) > 0:
                milestones.append(f"{community_data['telegram_members']:,} Telegram members")
            elif kpi == 'reddit_subscribers' and community_data.get('reddit_subscribers', 0) > 0:
                milestones.append(f"{community_data.get('reddit_subscribers', 0):,} Reddit subscribers")
            elif kpi == 'github_contributors' and community_data.get('github_contributors', 0) > 0:
                milestones.append(f"{community_data['github_contributors']} GitHub contributors")
            elif kpi == 'github_commits_30d' and community_data.get('github_commits_30d', 0) > 0:
                milestones.append(f"{community_data['github_commits_30d']} commits (last 4 weeks)")
            elif kpi == 'audit_count' and len(collected_data.get('security_audits', [])) > 0:
                milestones.append(f"{len(collected_data['security_audits'])} security audit(s)")

        if not milestones:
            milestones.append('Data collection in progress')

        return milestones[:5]  # Limit to 5

    def _calculate_maturity_score_v2(
        self,
        objectives: List[StrategicObjective],
        community_score: Dict[str, Any],
        market_data: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        collected_data: Dict[str, Any],
    ) -> float:
        """
        v2: Calculate maturity score from weighted objectives.

        If template objectives are available, score = sum(weight × achievement).
        Falls back to v1 scoring if no objectives data.
        """
        if objectives:
            total = 0.0
            for obj in objectives:
                total += obj.weight * obj.achievement_rate
            return min(100, max(0, total))

        # Fallback to v1
        return self._calculate_maturity_score(market_data, transparency_scan, collected_data)

    def _calculate_maturity_score(
        self,
        market_data: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> float:
        """
        Calculate overall maturity score (0-100) from available metrics.

        Factors considered:
        - Holder concentration (distribution quality)
        - Volume stability (market depth)
        - Transparency score
        - GitHub activity (development velocity)
        - Exchange listings (market presence)
        """
        scores = []

        # Market distribution score (holder count, concentration)
        holder_count = market_data.get('holder_count', 0)
        holder_concentration = market_data.get('holder_concentration', 1.0)

        if holder_count > 0:
            # More holders = better distribution (max 25 points)
            distribution_score = min(25, (math.log(holder_count) / math.log(10)) * 10)
            # Lower concentration = better (penalty)
            concentration_penalty = holder_concentration * 10 if holder_concentration > 0.5 else 0
            holder_score = max(0, distribution_score - concentration_penalty)
            scores.append(holder_score)

        # Volume and liquidity score (max 25 points)
        daily_volume = market_data.get('daily_volume_usd', 0)
        if daily_volume > 0:
            volume_score = min(25, (math.log(daily_volume) / math.log(1000000)) * 15)
            scores.append(max(0, volume_score))

        # Transparency score (max 25 points)
        transparency_score = transparency_scan.get('overall_score', 0)
        if transparency_score is not None:
            scores.append(transparency_score * 0.25)

        # Development activity score (max 25 points)
        github_commits = collected_data.get('github_commits_last_month', 0)
        github_score = min(25, (github_commits / 100) * 25)
        scores.append(max(0, github_score))

        # Exchange listings score (max 10 points)
        exchange_count = len(market_data.get('exchanges', []))
        listing_score = min(10, exchange_count * 2)
        scores.append(listing_score)

        # Average all scores
        if scores:
            return sum(scores) / len(scores)
        return 25.0  # Default nascent score

    def _determine_stage(self, score: float) -> str:
        """Determine maturity stage based on score."""
        for stage, bounds in self.maturity_levels.items():
            if bounds['min'] <= score <= bounds['max']:
                return stage
        return 'nascent' if score < 25 else 'established'

    def _generate_strategic_objectives(
        self,
        market_data: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> List[StrategicObjective]:
        """
        Generate 5 universal strategic objectives with achievement rates.

        Achievement rates estimated from:
        - Market Adoption: holder count, volume growth
        - Technical Development: GitHub activity, code quality
        - Ecosystem Growth: partnerships, integrations
        - Security & Transparency: audit status, transparency score
        - Market Position & Liquidity: exchange listings, market cap
        """
        objectives = []

        # 1. Market Adoption
        holder_count = market_data.get('holder_count', 0)
        adoption_rate = min(100, (math.log(max(1, holder_count)) / math.log(10)) * 20)
        objectives.append(StrategicObjective(
            name='Market Adoption',
            weight=0.20,
            achievement_rate=adoption_rate,
            milestones=[
                f'{holder_count:,} active holders',
                'Established trading pairs on major exchanges',
                'Consistent daily volume'
            ]
        ))

        # 2. Technical Development
        github_commits = collected_data.get('github_commits_last_month', 0)
        is_audited = collected_data.get('contract_audited', False)
        tech_rate = (github_commits / 200 * 60) + (40 if is_audited else 0)
        objectives.append(StrategicObjective(
            name='Technical Development',
            weight=0.20,
            achievement_rate=min(100, tech_rate),
            milestones=[
                f'{github_commits} commits this month',
                'Smart contracts deployed and verified' if is_audited else 'Smart contracts in development',
                'Continuous integration/deployment pipeline'
            ]
        ))

        # 3. Ecosystem Growth
        integrations = len(collected_data.get('integrations', []))
        partnerships = len(collected_data.get('partnerships', []))
        ecosystem_rate = ((integrations + partnerships) / 5) * 100
        objectives.append(StrategicObjective(
            name='Ecosystem Growth',
            weight=0.20,
            achievement_rate=min(100, ecosystem_rate),
            milestones=[
                f'{integrations} active integrations',
                f'{partnerships} strategic partnerships',
                'Active developer community'
            ]
        ))

        # 4. Security & Transparency
        transparency_score = transparency_scan.get('overall_score', 0)
        security_audits = len(collected_data.get('security_audits', []))
        security_rate = (transparency_score * 0.7) + min(30, security_audits * 10)
        objectives.append(StrategicObjective(
            name='Security & Transparency',
            weight=0.20,
            achievement_rate=min(100, security_rate),
            milestones=[
                f'Transparency score: {transparency_score:.0f}%',
                f'{security_audits} security audit(s) completed',
                'Clear risk disclosures and documentation'
            ]
        ))

        # 5. Market Position & Liquidity
        exchange_count = len(market_data.get('exchanges', []))
        daily_volume = market_data.get('daily_volume_usd', 0)
        market_cap = market_data.get('market_cap_usd', 0)

        liquidity_rate = min(
            100,
            (exchange_count * 8) +
            (math.log(max(1, daily_volume)) / math.log(1000000) * 30) +
            (math.log(max(1, market_cap)) / math.log(1000000) * 30)
        )
        objectives.append(StrategicObjective(
            name='Market Position & Liquidity',
            weight=0.20,
            achievement_rate=liquidity_rate,
            milestones=[
                f'Listed on {exchange_count} major exchanges',
                f'${daily_volume:,.0f} daily volume',
                f'${market_cap:,.0f} market cap'
            ]
        ))

        return objectives

    def _generate_tech_pillars(
        self,
        collected_data: Dict[str, Any],
        transparency_scan: Dict[str, Any]
    ) -> List[TechPillar]:
        """
        Generate tech pillars inferred from GitHub data, contract verification, audits.
        """
        pillars = []

        # Smart Contract Quality
        is_audited = collected_data.get('contract_audited', False)
        contract_quality = 80 if is_audited else 50
        pillars.append(TechPillar(
            name='Smart Contract Quality',
            score=contract_quality,
            prev_score=collected_data.get('prev_contract_quality_score', contract_quality - 5),
            details='Audited' if is_audited else 'Pending security audit'
        ))

        # Code Activity
        github_commits = collected_data.get('github_commits_last_month', 0)
        code_activity = min(100, (github_commits / 150) * 100)
        pillars.append(TechPillar(
            name='Code Activity',
            score=code_activity,
            prev_score=collected_data.get('prev_code_activity_score', max(0, code_activity - 10)),
            details=f'{github_commits} commits this month'
        ))

        # Security Audits
        audit_count = len(collected_data.get('security_audits', []))
        audit_score = min(100, audit_count * 40)
        pillars.append(TechPillar(
            name='Security Audits',
            score=audit_score,
            prev_score=collected_data.get('prev_audit_score', max(0, audit_score - 20)),
            details=f'{audit_count} audit(s) completed'
        ))

        # Documentation
        has_whitepaper = collected_data.get('has_whitepaper', False)
        has_docs = collected_data.get('has_documentation', False)
        doc_score = (50 if has_whitepaper else 0) + (50 if has_docs else 0)
        pillars.append(TechPillar(
            name='Documentation',
            score=doc_score,
            prev_score=collected_data.get('prev_documentation_score', max(0, doc_score - 10)),
            details='Whitepaper and technical documentation present' if doc_score == 100 else 'Partial documentation'
        ))

        # Community Engagement
        github_stars = collected_data.get('github_stars', 0)
        discord_members = collected_data.get('discord_members', 0)
        engagement_score = min(100, (github_stars / 500) * 50 + (discord_members / 5000) * 50)
        pillars.append(TechPillar(
            name='Community Engagement',
            score=engagement_score,
            prev_score=collected_data.get('prev_engagement_score', max(0, engagement_score - 5)),
            details=f'{github_stars} GitHub stars, {discord_members} Discord members'
        ))

        return pillars

    def _extract_peer_comparison(
        self,
        collected_data: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> List[PeerComparison]:
        """
        Extract peer comparison data from collected data.
        """
        peers = []

        peer_data = collected_data.get('peer_projects', [])
        for peer in peer_data:
            if isinstance(peer, dict):
                peers.append(PeerComparison(
                    name=peer.get('name', 'Unknown'),
                    market_cap=peer.get('market_cap', 0),
                    tvl=peer.get('tvl', 0),
                    maturity_score=peer.get('maturity_score', 50)
                ))

        return peers

    def _calculate_risk_matrix(
        self,
        market_data: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> RiskMatrix:
        """
        Calculate risk matrix across tech, market, regulatory, operational dimensions.

        Risks are scored 0-100 where higher = more risk.
        """

        # Tech Risk: inverse of audit score and code quality
        audit_count = len(collected_data.get('security_audits', []))
        github_commits = collected_data.get('github_commits_last_month', 0)
        tech_risk = max(
            0,
            100 - (audit_count * 30) - ((github_commits / 150) * 40) - 20
        )

        # Market Risk: based on price volatility and holder concentration
        price_volatility = market_data.get('price_volatility_30d', 0.5)
        holder_concentration = market_data.get('holder_concentration', 0.5)
        market_risk = (price_volatility * 100 * 0.5) + (holder_concentration * 100 * 0.5)

        # Regulatory Risk: based on transparency and jurisdiction clarity
        transparency_score = transparency_scan.get('overall_score', 50)
        has_legal_analysis = collected_data.get('has_legal_analysis', False)
        regulatory_risk = max(
            0,
            100 - (transparency_score * 0.5) - (50 if has_legal_analysis else 0)
        )

        # Operational Risk: based on team structure and business continuity
        team_size = len(collected_data.get('team_members', []))
        has_continuity_plan = collected_data.get('has_contingency_plan', False)
        operational_risk = max(
            0,
            100 - (min(team_size, 20) * 3) - (30 if has_continuity_plan else 0)
        )

        return RiskMatrix(
            tech_risk=round(max(0, min(100, tech_risk)), 1),
            market_risk=round(max(0, min(100, market_risk)), 1),
            regulatory_risk=round(max(0, min(100, regulatory_risk)), 1),
            operational_risk=round(max(0, min(100, operational_risk)), 1)
        )

    def _generate_growth_trajectory(
        self,
        triage_result: Dict[str, Any],
        market_data: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> GrowthTrajectory:
        """
        Generate 3-month growth trajectory, milestones, and watch points.
        """

        # Determine outlook based on current metrics
        github_commits = collected_data.get('github_commits_last_month', 0)
        daily_volume = market_data.get('daily_volume_usd', 0)
        price_trend = market_data.get('price_trend_30d', 0)

        if github_commits > 100 and price_trend > 0:
            outlook = 'Positive - strong development activity and positive price momentum'
        elif github_commits > 50:
            outlook = 'Moderate - consistent development activity, stable market conditions'
        elif price_trend < -0.15:
            outlook = 'Cautious - declining activity or negative market sentiment'
        else:
            outlook = 'Neutral - awaiting further catalyst development'

        milestones = [
            'Planned feature releases from roadmap',
            'Exchange listing expansion',
            'Community growth initiatives',
            'Technical upgrades or improvements'
        ]

        watch_points = [
            'Monitor GitHub activity for sustained development',
            'Track holder distribution for concentration changes',
            'Watch for regulatory announcements',
            'Observe trading volume trends and price stability'
        ]

        return GrowthTrajectory(
            outlook_3m=outlook,
            milestones=milestones,
            watch_points=watch_points
        )


def main():
    """Test the AutoMatGenerator with mock data."""

    # Mock data structures
    mock_triage = {
        'project_id': 'test-project',
        'category': 'DeFi',
        'risk_level': 'medium'
    }

    mock_market = {
        'holder_count': 5000,
        'holder_concentration': 0.25,
        'daily_volume_usd': 500000,
        'market_cap_usd': 50000000,
        'price_volatility_30d': 0.35,
        'price_trend_30d': 0.08,
        'exchanges': ['Uniswap', 'Sushiswap', 'Curve', 'Balancer']
    }

    mock_transparency = {
        'overall_score': 72,
        'contract_verification': 90,
        'team_disclosure': 65,
        'financial_transparency': 60
    }

    mock_collected = {
        'github_commits_last_month': 85,
        'github_stars': 2300,
        'discord_members': 12000,
        'contract_audited': True,
        'security_audits': [
            {'firm': 'CertiK', 'date': '2025-11-15'},
            {'firm': 'OpenZeppelin', 'date': '2025-08-20'}
        ],
        'has_whitepaper': True,
        'has_documentation': True,
        'has_legal_analysis': True,
        'has_contingency_plan': True,
        'team_members': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
        'integrations': ['Curve', 'Uniswap', 'Aave'],
        'partnerships': ['Lido', 'Compound'],
        'prev_contract_quality_score': 75,
        'prev_code_activity_score': 75,
        'prev_audit_score': 60,
        'prev_documentation_score': 85,
        'prev_engagement_score': 65,
        'peer_projects': [
            {
                'name': 'Project A',
                'market_cap': 100000000,
                'tvl': 50000000,
                'maturity_score': 78
            },
            {
                'name': 'Project B',
                'market_cap': 75000000,
                'tvl': 30000000,
                'maturity_score': 72
            }
        ]
    }

    # Generate MAT report data
    generator = AutoMatGenerator()
    result = generator.generate(
        triage_result=mock_triage,
        market_data=mock_market,
        transparency_scan=mock_transparency,
        collected_data=mock_collected
    )

    # Display results
    print("=" * 80)
    print("AUTO MAT REPORT GENERATOR - TEST OUTPUT")
    print("=" * 80)
    print(json.dumps(result, indent=2))
    print("\n" + "=" * 80)
    print(f"Maturity Score: {result['total_maturity_score']}")
    print(f"Maturity Stage: {result['maturity_stage']}")
    print(f"Auto Generated: {result['auto_generated']}")
    print(f"Generated At: {result['generated_at']}")
    print("=" * 80)


if __name__ == '__main__':
    main()
