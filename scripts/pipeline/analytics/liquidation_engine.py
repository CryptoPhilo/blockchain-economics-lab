"""
BCE Lab Liquidation Cluster Engine
Models liquidation price clusters, squeeze probability, and leverage risk.

Uses OI data + price levels + funding rates to estimate:
- 3-tier liquidation clusters (upper/mid/lower)
- Short squeeze probability
- Long squeeze risk
- Cascade scenario modeling
"""
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone


# Common leverage levels used by retail/institutional traders
LEVERAGE_TIERS = [2, 3, 5, 10, 20, 25, 50, 100]

# Maintenance margin rates by leverage (approximate, Binance-style)
MAINTENANCE_MARGIN = {
    2: 0.004, 3: 0.006, 5: 0.01, 10: 0.02,
    20: 0.04, 25: 0.05, 50: 0.10, 100: 0.20,
}


class LiquidationEngine:
    """Models liquidation clusters and squeeze scenarios."""

    def __init__(self, current_price: float, oi_data: Dict = None,
                 funding_data: Dict = None, long_short_ratio: Dict = None,
                 volatility_pct: float = 0, price_change_24h_pct: float = 0):
        """
        Args:
            current_price: Current spot/futures price
            oi_data: Open interest data from CoinGlass collector
            funding_data: Funding rate data from CoinGlass collector
            long_short_ratio: Long/short account ratio data
            volatility_pct: 90-day annualized volatility (%)
            price_change_24h_pct: 24h price change (%)
        """
        self.price = current_price
        self.oi = oi_data or {}
        self.funding = funding_data or {}
        self.ls_ratio = long_short_ratio or {}
        self.volatility = volatility_pct
        self.price_change_24h = price_change_24h_pct

    # ══════════════════════════════════════════
    # LIQUIDATION CLUSTER MAPPING
    # ══════════════════════════════════════════

    def compute_liquidation_clusters(self) -> Dict:
        """
        Compute 3-tier liquidation price clusters.

        For each leverage level, calculate where longs/shorts get liquidated:
        - Long liquidation: entry_price × (1 - 1/leverage + maintenance_margin)
        - Short liquidation: entry_price × (1 + 1/leverage - maintenance_margin)

        Returns:
            {
                "upper_cluster": {"range": [low, high], "type": "short_liquidation", ...},
                "mid_cluster": {"range": [low, high], "type": "long_liquidation", ...},
                "lower_cluster": {"range": [low, high], "type": "capitulation", ...},
            }
        """
        # Estimate entry prices based on recent price action
        entry_high = self.price * 1.05   # Recent buyers in last rally
        entry_mid = self.price           # Current level entries
        entry_low = self.price * 0.95    # Bottom fishers

        # SHORT liquidation levels (price goes UP)
        short_liq_levels = []
        for lev in LEVERAGE_TIERS:
            mm = MAINTENANCE_MARGIN.get(lev, 0.02)
            # Short liquidation = entry × (1 + 1/leverage - mm)
            for entry in [entry_mid, entry_low]:
                liq_price = entry * (1 + 1 / lev - mm)
                if liq_price > self.price:
                    short_liq_levels.append({
                        "price": round(liq_price, 4),
                        "leverage": lev,
                        "entry_est": round(entry, 4),
                    })

        # LONG liquidation levels (price goes DOWN)
        long_liq_levels = []
        for lev in LEVERAGE_TIERS:
            mm = MAINTENANCE_MARGIN.get(lev, 0.02)
            # Long liquidation = entry × (1 - 1/leverage + mm)
            for entry in [entry_mid, entry_high]:
                liq_price = entry * (1 - 1 / lev + mm)
                if liq_price < self.price:
                    long_liq_levels.append({
                        "price": round(liq_price, 4),
                        "leverage": lev,
                        "entry_est": round(entry, 4),
                    })

        # Cluster short liquidations into upper band
        short_prices = sorted(set(l["price"] for l in short_liq_levels))
        long_prices = sorted(set(l["price"] for l in long_liq_levels), reverse=True)

        # 3-tier classification
        clusters = {
            "upper_cluster": {
                "type": "short_liquidation_zone",
                "label": "숏 청산 집중 구간 (Short Liquidation Zone)",
                "range": [
                    round(self.price * 1.05, 4),
                    round(self.price * 1.20, 4),
                ],
                "leverage_range": "3x-10x shorts",
                "description": f"Short positions at 3x-10x leverage face liquidation if price rises "
                              f"5-20% from current ${self.price:.2f}",
                "key_levels": short_prices[:5] if short_prices else [],
            },
            "mid_cluster": {
                "type": "long_liquidation_zone",
                "label": "롱 청산 집중 구간 (Long Liquidation Zone)",
                "range": [
                    round(self.price * 0.85, 4),
                    round(self.price * 0.95, 4),
                ],
                "leverage_range": "5x-20x longs",
                "description": f"Long positions at 5x-20x leverage face liquidation if price drops "
                              f"5-15% from current ${self.price:.2f}",
                "key_levels": long_prices[:5] if long_prices else [],
            },
            "lower_cluster": {
                "type": "capitulation_zone",
                "label": "항복 구간 (Capitulation Zone)",
                "range": [
                    round(self.price * 0.70, 4),
                    round(self.price * 0.80, 4),
                ],
                "leverage_range": "2x-3x longs + spot panic",
                "description": f"Conservative leveraged longs and spot panic selling zone. "
                              f"Price drop of 20-30% from ${self.price:.2f} triggers cascade.",
                "key_levels": [l["price"] for l in long_liq_levels
                              if l["leverage"] <= 3][:3],
            },
        }

        return clusters

    # ══════════════════════════════════════════
    # SQUEEZE PROBABILITY MODEL
    # ══════════════════════════════════════════

    def compute_squeeze_probability(self) -> Dict:
        """
        Estimate short squeeze and long squeeze probabilities.

        Factors considered:
        - Funding rate (negative = short-heavy → squeeze potential)
        - Long/short ratio
        - OI concentration
        - Recent price momentum
        - Volatility
        """
        funding_rate = self.funding.get("weighted_avg_rate", 0)
        sentiment = self.funding.get("sentiment", "neutral")
        long_ratio = self.ls_ratio.get("long_ratio", 0.5)
        short_ratio = self.ls_ratio.get("short_ratio", 0.5)
        oi_change = self.oi.get("oi_change_24h_pct", 0)

        # ── SHORT SQUEEZE PROBABILITY ──
        short_squeeze_score = 0

        # Factor 1: Negative funding rate (max 30 points)
        if funding_rate < -0.03:
            short_squeeze_score += 30
        elif funding_rate < -0.01:
            short_squeeze_score += 20
        elif funding_rate < 0:
            short_squeeze_score += 10

        # Factor 2: Short dominance in L/S ratio (max 25 points)
        if short_ratio > 0.65:
            short_squeeze_score += 25
        elif short_ratio > 0.55:
            short_squeeze_score += 15
        elif short_ratio > 0.50:
            short_squeeze_score += 5

        # Factor 3: Rising OI with falling price = shorts accumulating (max 20 points)
        if oi_change > 5 and self.price_change_24h < -3:
            short_squeeze_score += 20
        elif oi_change > 0 and self.price_change_24h < 0:
            short_squeeze_score += 10

        # Factor 4: High volatility amplifies squeeze potential (max 15 points)
        if self.volatility > 100:
            short_squeeze_score += 15
        elif self.volatility > 60:
            short_squeeze_score += 10
        elif self.volatility > 30:
            short_squeeze_score += 5

        # Factor 5: Oversold conditions (max 10 points)
        if self.price_change_24h < -10:
            short_squeeze_score += 10
        elif self.price_change_24h < -5:
            short_squeeze_score += 5

        short_squeeze_pct = min(short_squeeze_score, 100)

        # ── LONG SQUEEZE PROBABILITY ──
        long_squeeze_score = 0

        # Factor 1: Positive funding rate (max 30 points)
        if funding_rate > 0.03:
            long_squeeze_score += 30
        elif funding_rate > 0.01:
            long_squeeze_score += 20
        elif funding_rate > 0:
            long_squeeze_score += 10

        # Factor 2: Long dominance (max 25 points)
        if long_ratio > 0.65:
            long_squeeze_score += 25
        elif long_ratio > 0.55:
            long_squeeze_score += 15
        elif long_ratio > 0.50:
            long_squeeze_score += 5

        # Factor 3: Rising OI with rising price = longs overleveraged (max 20 points)
        if oi_change > 5 and self.price_change_24h > 3:
            long_squeeze_score += 20
        elif oi_change > 0 and self.price_change_24h > 0:
            long_squeeze_score += 10

        # Factor 4: Volatility (max 15 points)
        if self.volatility > 100:
            long_squeeze_score += 15
        elif self.volatility > 60:
            long_squeeze_score += 10

        # Factor 5: Overbought (max 10 points)
        if self.price_change_24h > 15:
            long_squeeze_score += 10
        elif self.price_change_24h > 8:
            long_squeeze_score += 5

        long_squeeze_pct = min(long_squeeze_score, 100)

        return {
            "short_squeeze": {
                "probability_pct": short_squeeze_pct,
                "label": self._prob_label(short_squeeze_pct),
                "trigger_condition": f"Price breaks above upper liquidation cluster "
                                    f"(${self.price * 1.05:.2f}+) with volume",
                "expected_move_pct": f"{min(15 + self.volatility * 0.1, 40):.0f}%",
                "factors": {
                    "funding_rate": funding_rate,
                    "short_ratio": short_ratio,
                    "oi_rising_price_falling": oi_change > 0 and self.price_change_24h < 0,
                },
            },
            "long_squeeze": {
                "probability_pct": long_squeeze_pct,
                "label": self._prob_label(long_squeeze_pct),
                "trigger_condition": f"Price breaks below mid liquidation cluster "
                                    f"(${self.price * 0.95:.2f}-) on high volume",
                "expected_move_pct": f"{min(15 + self.volatility * 0.1, 40):.0f}%",
                "factors": {
                    "funding_rate": funding_rate,
                    "long_ratio": long_ratio,
                    "oi_rising_price_rising": oi_change > 0 and self.price_change_24h > 0,
                },
            },
            "dominant_risk": "short_squeeze" if short_squeeze_pct > long_squeeze_pct
                           else "long_squeeze" if long_squeeze_pct > short_squeeze_pct
                           else "balanced",
        }

    def _prob_label(self, pct: int) -> str:
        if pct >= 80:
            return "very_high"
        elif pct >= 60:
            return "high"
        elif pct >= 40:
            return "moderate"
        elif pct >= 20:
            return "low"
        return "very_low"

    # ══════════════════════════════════════════
    # CASCADE SCENARIO MODELING
    # ══════════════════════════════════════════

    def model_cascade_scenarios(self) -> List[Dict]:
        """
        Model potential liquidation cascade scenarios.
        Each scenario: trigger → chain reaction → estimated impact.
        """
        clusters = self.compute_liquidation_clusters()
        squeeze = self.compute_squeeze_probability()

        scenarios = []

        # Scenario 1: Short Squeeze Cascade
        if squeeze["short_squeeze"]["probability_pct"] >= 30:
            upper = clusters["upper_cluster"]
            scenarios.append({
                "name": "Short Squeeze Cascade",
                "name_ko": "숏 스퀴즈 연쇄 청산",
                "probability": squeeze["short_squeeze"]["label"],
                "trigger": f"Price breaks ${upper['range'][0]:.2f} with strong volume",
                "chain": [
                    f"1. High-leverage shorts (10x+) liquidated at ${upper['range'][0]:.2f}",
                    f"2. Forced buy-backs push price toward ${upper['range'][1]:.2f}",
                    f"3. Medium-leverage shorts (5x) liquidated, accelerating rally",
                    f"4. FOMO buying amplifies move to ${self.price * 1.25:.2f}+",
                ],
                "estimated_price_target": round(self.price * 1.20, 2),
                "estimated_duration": "4-12 hours",
                "risk_to": "short_holders",
            })

        # Scenario 2: Long Liquidation Cascade
        if squeeze["long_squeeze"]["probability_pct"] >= 30:
            mid = clusters["mid_cluster"]
            scenarios.append({
                "name": "Long Liquidation Cascade",
                "name_ko": "롱 포지션 연쇄 청산",
                "probability": squeeze["long_squeeze"]["label"],
                "trigger": f"Price breaks ${mid['range'][1]:.2f} support on sell volume",
                "chain": [
                    f"1. High-leverage longs (20x+) liquidated at ${mid['range'][1]:.2f}",
                    f"2. Forced sell-offs push price toward ${mid['range'][0]:.2f}",
                    f"3. Stop-loss orders triggered, accelerating decline",
                    f"4. Panic selling pushes toward capitulation zone ${clusters['lower_cluster']['range'][0]:.2f}",
                ],
                "estimated_price_target": round(self.price * 0.80, 2),
                "estimated_duration": "2-8 hours",
                "risk_to": "long_holders",
            })

        # Scenario 3: Whale-Induced Flash Crash
        scenarios.append({
            "name": "Whale-Induced Flash Crash",
            "name_ko": "고래 유발 급락",
            "probability": "moderate" if self.volatility > 50 else "low",
            "trigger": "Large market sell order (>5% of daily volume) during low liquidity",
            "chain": [
                "1. Order book depth insufficient to absorb sell pressure",
                "2. Price slips through multiple liquidation levels simultaneously",
                f"3. Cascading liquidations from ${self.price * 0.95:.2f} to ${self.price * 0.75:.2f}",
                "4. Recovery bounce as liquidation selling exhausts",
            ],
            "estimated_price_target": round(self.price * 0.80, 2),
            "estimated_duration": "30 minutes - 2 hours",
            "risk_to": "all_leveraged_positions",
        })

        return scenarios

    # ══════════════════════════════════════════
    # COMPREHENSIVE ANALYSIS
    # ══════════════════════════════════════════

    def compute_all(self) -> Dict:
        """
        Run full liquidation and squeeze analysis.
        Main entry point for the pipeline.
        """
        return {
            "current_price": self.price,
            "liquidation_clusters": self.compute_liquidation_clusters(),
            "squeeze_probability": self.compute_squeeze_probability(),
            "cascade_scenarios": self.model_cascade_scenarios(),
            "derivatives_summary": {
                "total_oi_usd": self.oi.get("total_oi_usd", 0),
                "oi_change_24h_pct": self.oi.get("oi_change_24h_pct", 0),
                "funding_rate": self.funding.get("weighted_avg_rate", 0),
                "funding_sentiment": self.funding.get("sentiment", "unknown"),
                "long_ratio": self.ls_ratio.get("long_ratio", 0.5),
                "short_ratio": self.ls_ratio.get("short_ratio", 0.5),
            },
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
