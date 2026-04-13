"""
BCE Lab Risk Strategy Framework
Generates actionable trading strategies based on forensic findings.

Combines: technical indicators + liquidation analysis + exchange data
→ Scenario-based entry/exit/stop-loss recommendations
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone


class ForensicStrategyEngine:
    """Generate trading strategy recommendations from forensic analysis."""

    def __init__(self, technical: Dict, liquidation: Dict,
                 exchange: Dict = None, risk_level: str = "medium"):
        """
        Args:
            technical: Output from TechnicalIndicators.compute_all()
            liquidation: Output from LiquidationEngine.compute_all()
            exchange: Output from analyze_exchange_microstructure()
            risk_level: Forensic risk level (low/medium/high/critical)
        """
        self.tech = technical
        self.liq = liquidation
        self.exchange = exchange or {}
        self.risk_level = risk_level.lower()
        self.price = technical.get("current_price", 0) or 0

    def generate_strategy(self) -> Dict:
        """
        Generate comprehensive trading strategy.
        Main entry point.
        """
        if not self.price or self.price <= 0:
            return {
                "current_price": self.price,
                "risk_level": self.risk_level,
                "error": "Cannot generate strategy without valid current price",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        leverage = self._leverage_recommendation()
        scenarios = self._build_scenarios()
        position_sizing = self._position_sizing()
        monitoring = self._monitoring_framework()

        return {
            "current_price": self.price,
            "risk_level": self.risk_level,
            "leverage_recommendation": leverage,
            "scenarios": scenarios,
            "position_sizing": position_sizing,
            "monitoring": monitoring,
            "risk_warnings": self._risk_warnings(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _leverage_recommendation(self) -> Dict:
        """Compute maximum recommended leverage."""
        vol = self.tech.get("volatility", {}).get("annualized_90d_pct", 50)
        lev_data = self.tech.get("leverage_recommendation", {})
        max_lev = lev_data.get("max_leverage", 3)

        # Reduce for high forensic risk
        risk_multiplier = {
            "critical": 0.3,
            "high": 0.5,
            "medium": 0.8,
            "low": 1.0,
        }.get(self.risk_level, 0.5)

        adjusted_lev = max(1, round(max_lev * risk_multiplier, 1))

        return {
            "max_leverage": adjusted_lev,
            "volatility_based_max": max_lev,
            "risk_adjustment_factor": risk_multiplier,
            "volatility_90d_pct": vol,
            "rationale": (
                f"Base max {max_lev}x (from {vol:.1f}% 90-day volatility) "
                f"× {risk_multiplier} risk adjustment ({self.risk_level} forensic risk) "
                f"= {adjusted_lev}x recommended maximum"
            ),
            "danger_zone": f">{adjusted_lev * 2}x — risk of total loss in {vol/100*100/adjusted_lev:.0f}% move",
        }

    def _build_scenarios(self) -> List[Dict]:
        """Build 3 trading scenarios: bullish, bearish, neutral."""
        sr = self.tech.get("support_resistance", {})
        fib = self.tech.get("fibonacci", {})
        clusters = self.liq.get("liquidation_clusters", {})
        squeeze = self.liq.get("squeeze_probability", {})

        supports = sr.get("supports", [])
        resistances = sr.get("resistances", [])
        fib_levels = fib.get("levels", {})

        s1 = supports[0] if supports else self.price * 0.95
        s2 = supports[1] if len(supports) > 1 else self.price * 0.90
        r1 = resistances[0] if resistances else self.price * 1.05
        r2 = resistances[1] if len(resistances) > 1 else self.price * 1.15

        scenarios = []

        # ── BULLISH SCENARIO ──
        short_sq = squeeze.get("short_squeeze", {})
        scenarios.append({
            "name": "Bullish Breakout",
            "name_ko": "강세 돌파 시나리오",
            "probability": short_sq.get("label", "moderate"),
            "trigger": f"Price breaks above ${r1:.2f} with sustained volume",
            "entry": {
                "price_range": f"${r1:.2f} - ${r1 * 1.01:.2f}",
                "condition": "Close above resistance with volume > 2x average",
                "entry_type": "breakout_confirmation",
            },
            "targets": [
                {"level": f"T1: ${r2:.2f}", "gain_pct": f"+{(r2/self.price-1)*100:.1f}%"},
                {"level": f"T2: ${self.price * 1.20:.2f}", "gain_pct": f"+20.0%"},
            ],
            "stop_loss": {
                "price": f"${s1:.2f}",
                "loss_pct": f"-{(1-s1/self.price)*100:.1f}%",
                "rationale": "Below nearest support — invalidates bullish thesis",
            },
            "risk_reward_ratio": round((r2 - self.price) / (self.price - s1), 2) if self.price != s1 else 0,
            "time_frame": "1-4 weeks",
        })

        # ── BEARISH SCENARIO ──
        long_sq = squeeze.get("long_squeeze", {})
        scenarios.append({
            "name": "Bearish Breakdown",
            "name_ko": "약세 붕괴 시나리오",
            "probability": long_sq.get("label", "moderate"),
            "trigger": f"Price breaks below ${s1:.2f} on high volume",
            "entry": {
                "price_range": f"Short at ${s1:.2f} - ${s1 * 0.99:.2f}",
                "condition": "Close below support with increasing sell volume",
                "entry_type": "breakdown_confirmation",
            },
            "targets": [
                {"level": f"T1: ${s2:.2f}", "gain_pct": f"+{(1-s2/s1)*100:.1f}% (short)"},
                {"level": f"T2: ${self.price * 0.80:.2f}", "gain_pct": f"+{(1-0.80)*100:.1f}% (short)"},
            ],
            "stop_loss": {
                "price": f"${r1:.2f}",
                "loss_pct": f"-{(r1/s1-1)*100:.1f}%",
                "rationale": "Above nearest resistance — short thesis invalidated",
            },
            "risk_reward_ratio": round((s1 - s2) / (r1 - s1), 2) if r1 != s1 else 0,
            "time_frame": "1-2 weeks",
        })

        # ── RANGE/ACCUMULATION SCENARIO ──
        scenarios.append({
            "name": "Range Accumulation",
            "name_ko": "횡보 축적 시나리오",
            "probability": "moderate",
            "trigger": f"Price consolidates between ${s1:.2f} - ${r1:.2f}",
            "entry": {
                "price_range": f"${s1:.2f} - ${s1 * 1.02:.2f} (bounces off support)",
                "condition": "RSI below 40 + price at support + volume declining",
                "entry_type": "range_bottom_accumulation",
            },
            "targets": [
                {"level": f"T1: ${self.price:.2f} (midrange)", "gain_pct": f"+{(self.price/s1-1)*100:.1f}%"},
                {"level": f"T2: ${r1:.2f} (range top)", "gain_pct": f"+{(r1/s1-1)*100:.1f}%"},
            ],
            "stop_loss": {
                "price": f"${s1 * 0.97:.2f}",
                "loss_pct": "-3%",
                "rationale": "Tight stop below support — range strategy requires discipline",
            },
            "risk_reward_ratio": round((r1 - s1) / (s1 * 0.03), 2) if s1 > 0 else 0,
            "time_frame": "2-6 weeks",
        })

        return scenarios

    def _position_sizing(self) -> Dict:
        """Recommend position sizes based on risk."""
        lev = self._leverage_recommendation()
        max_leverage = lev["max_leverage"]

        # Kelly criterion simplified
        risk_per_trade = {
            "critical": 0.5,   # 0.5% of portfolio
            "high": 1.0,       # 1%
            "medium": 2.0,     # 2%
            "low": 3.0,        # 3%
        }.get(self.risk_level, 1.0)

        return {
            "max_risk_per_trade_pct": risk_per_trade,
            "max_leverage": max_leverage,
            "example": {
                "portfolio_size": "$100,000",
                "max_position": f"${100000 * risk_per_trade / 100 * max_leverage:,.0f}",
                "max_loss_if_stopped": f"${100000 * risk_per_trade / 100:,.0f}",
            },
            "rationale": f"At {self.risk_level} forensic risk, limit to {risk_per_trade}% "
                        f"portfolio risk per trade with {max_leverage}x max leverage",
        }

    def _monitoring_framework(self) -> Dict:
        """Generate monitoring checklist with trigger thresholds."""
        squeeze = self.liq.get("squeeze_probability", {})

        return {
            "real_time_alerts": [
                {
                    "metric": "Funding Rate",
                    "threshold": "< -0.03% or > 0.05%",
                    "action": "Review squeeze probability model",
                },
                {
                    "metric": "OI Change (1h)",
                    "threshold": "> ±5%",
                    "action": "Check for liquidation cascade initiation",
                },
                {
                    "metric": "Price vs Liquidation Cluster",
                    "threshold": "Within 3% of cluster boundary",
                    "action": "Prepare for volatility spike",
                },
                {
                    "metric": "Volume Spike",
                    "threshold": "> 300% of 7-day average",
                    "action": "Evaluate manipulation vs organic activity",
                },
            ],
            "weekly_review": [
                "Re-run forensic risk assessment",
                "Update support/resistance levels",
                "Check team wallet activity",
                "Review funding rate trend",
            ],
            "reassessment_triggers": [
                "Price breaks key support/resistance",
                "Major exchange listing/delisting",
                "Team token unlock event",
                "Regulatory action or investigation",
                "Whale wallet activity > 2% of supply",
            ],
        }

    def _risk_warnings(self) -> List[Dict]:
        """Generate risk warnings based on current conditions."""
        warnings = []
        squeeze = self.liq.get("squeeze_probability", {})

        if self.risk_level == "critical":
            warnings.append({
                "level": "CRITICAL",
                "message": "Forensic analysis indicates critical risk. New positions not recommended. "
                          "Existing holders should evaluate exit strategies.",
            })

        short_sq = squeeze.get("short_squeeze", {}).get("probability_pct", 0)
        long_sq = squeeze.get("long_squeeze", {}).get("probability_pct", 0)

        if short_sq >= 70:
            warnings.append({
                "level": "HIGH",
                "message": f"Short squeeze probability {short_sq}%. "
                          f"Short positions face extreme liquidation risk.",
            })

        if long_sq >= 70:
            warnings.append({
                "level": "HIGH",
                "message": f"Long squeeze probability {long_sq}%. "
                          f"Leveraged longs face extreme liquidation risk.",
            })

        vol = self.tech.get("volatility", {}).get("annualized_90d_pct", 0)
        if vol > 100:
            warnings.append({
                "level": "WARNING",
                "message": f"Extreme volatility ({vol:.0f}% annualized). "
                          f"Position sizes should be reduced accordingly.",
            })

        anomalies = self.exchange.get("multi_exchange_prices", {}).get("anomalies", [])
        for a in anomalies:
            warnings.append({"level": a.get("severity", "info").upper(), "message": a["description"]})

        return warnings
