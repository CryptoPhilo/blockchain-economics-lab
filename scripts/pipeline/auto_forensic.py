"""
Auto-Forensic Anomaly Detection & FOR Report Trigger Generation
Part of BCE Universal Coverage Pipeline (OPS-002)

Automatically detects forensic anomalies based on market data thresholds
and generates FOR (Forensic Report) trigger data when risk criteria are met.
"""

import os
import sys
from typing import Optional, Dict, List, Any

# Import config thresholds
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FORENSIC_AUTO_TRIGGERS, get_forensic_auto_deviation_threshold


class AutoForensicDetector:
    """
    Detects forensic anomalies in market data and generates FOR report triggers.

    Risk levels follow the standard hierarchy:
    - CRITICAL: Multiple high-severity anomalies
    - HIGH: Single high-severity anomaly
    - ELEVATED: Medium-severity anomalies
    - MODERATE: Minor anomalies
    - LOW: No anomalies or below thresholds
    """

    def __init__(self):
        """Initialize detector with config thresholds."""
        # Auto-FOR is stricter than the scanner: it triggers full report generation
        # only after a larger market-relative move crosses the dedicated threshold.
        self.relative_deviation_threshold = get_forensic_auto_deviation_threshold()
        self.volume_spike_threshold = FORENSIC_AUTO_TRIGGERS['volume_spike_ratio']
        self.whale_supply_threshold = FORENSIC_AUTO_TRIGGERS['whale_supply_pct']
        self.exchange_netflow_threshold = FORENSIC_AUTO_TRIGGERS['exchange_netflow_pct']

    @staticmethod
    def _get_relative_deviation(market_token: Dict[str, Any]) -> Optional[float]:
        """
        Resolve the relative price deviation used by the auto-FOR gate.

        Preferred input is the explicit `relative_deviation` field produced by
        the scanner. Legacy data can still fall back to a raw 24h move.
        """
        if market_token.get('relative_deviation') is not None:
            return float(market_token['relative_deviation'])

        price_change = market_token.get('price_change_24h')
        market_avg = market_token.get('market_avg_change_24h')

        if price_change is None:
            return None
        if market_avg is None:
            return abs(float(price_change))
        return abs(float(price_change) - float(market_avg))

    def detect_anomalies(
        self,
        market_token: Dict[str, Any],
        prev_market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detect forensic anomalies from market token data.

        Checks against configured thresholds:
        - relative deviation vs market average > configured threshold → ELEVATED+
        - volume_spike > 5× 7-day avg → HIGH
        - Combined signals → CRITICAL

        Args:
            market_token: Market data dict with keys such as relative_deviation,
                         price_change_24h, market_avg_change_24h, total_volume,
                         market_cap, supply_info, exchange_flows, etc.
            prev_market_data: Optional previous market state for comparison

        Returns:
            {
                'anomaly_detected': bool,
                'risk_level': 'critical'|'high'|'elevated'|'moderate'|'low',
                'flags': {key: bool, ...},  # Individual anomaly flags
                'findings': [str, ...]       # Human-readable findings
            }
        """
        anomalies = {}
        findings = []
        risk_score = 0

        # 1. RELATIVE PRICE DEVIATION CHECK
        relative_deviation = self._get_relative_deviation(market_token)
        if relative_deviation is not None:
            if relative_deviation >= self.relative_deviation_threshold:
                price_change = market_token.get('price_change_24h')
                market_avg = market_token.get('market_avg_change_24h')
                if price_change is not None and market_avg is not None:
                    delta = float(price_change) - float(market_avg)
                    direction = "spike" if delta > 0 else "crash"
                    findings.append(
                        f"Extreme relative price {direction}: {delta:+.2f}% vs market average "
                        f"(threshold: ±{self.relative_deviation_threshold}%)"
                    )
                else:
                    findings.append(
                        f"Extreme relative price deviation: {relative_deviation:.2f}% "
                        f"(threshold: ±{self.relative_deviation_threshold}%)"
                    )
                anomalies['relative_price_deviation'] = True
                risk_score += 2
            else:
                anomalies['relative_price_deviation'] = False

        # 2. VOLUME SPIKE CHECK
        if 'total_volume' in market_token and 'volume_7d_avg' in market_token:
            volume_ratio = (
                market_token['total_volume'] / market_token['volume_7d_avg']
                if market_token['volume_7d_avg'] > 0
                else 0
            )
            if volume_ratio > self.volume_spike_threshold:
                anomalies['volume_spike'] = True
                findings.append(
                    f"Volume spike detected: {volume_ratio:.2f}× 7-day average "
                    f"(threshold: {self.volume_spike_threshold}×)"
                )
                risk_score += 2
            else:
                anomalies['volume_spike'] = False

        # 3. WHALE MOVEMENT CHECK
        if 'whale_movement_supply_pct' in market_token:
            whale_pct = market_token['whale_movement_supply_pct']
            if whale_pct > self.whale_supply_threshold:
                anomalies['whale_movement'] = True
                findings.append(
                    f"Whale movement detected: {whale_pct:.2f}% of supply "
                    f"(threshold: {self.whale_supply_threshold}%)"
                )
                risk_score += 1
            else:
                anomalies['whale_movement'] = False

        # 4. EXCHANGE NETFLOW CHECK
        if 'exchange_netflow_supply_pct' in market_token:
            netflow_pct = market_token['exchange_netflow_supply_pct']
            if abs(netflow_pct) > self.exchange_netflow_threshold:
                flow_type = "inflow to" if netflow_pct > 0 else "outflow from"
                anomalies['exchange_netflow'] = True
                findings.append(
                    f"Exchange {flow_type} exchanges: {abs(netflow_pct):.2f}% of supply "
                    f"(threshold: ±{self.exchange_netflow_threshold}%)"
                )
                risk_score += 1
            else:
                anomalies['exchange_netflow'] = False

        # DETERMINE RISK LEVEL
        anomaly_detected = bool(findings)

        if risk_score >= 4:
            risk_level = 'critical'
        elif risk_score >= 3:
            risk_level = 'high'
        elif risk_score >= 2:
            risk_level = 'elevated'
        elif risk_score >= 1:
            risk_level = 'moderate'
        else:
            risk_level = 'low'

        return {
            'anomaly_detected': anomaly_detected,
            'risk_level': risk_level,
            'flags': anomalies,
            'findings': findings
        }

    def generate_for_data(
        self,
        market_token: Dict[str, Any],
        transparency_scan: Dict[str, Any],
        anomaly_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate full project_data for FOR (Forensic Report) generation.

        Combines anomaly detection results with transparency context to produce
        the complete data structure expected by the FOR report generator.

        Args:
            market_token: Market data from phase B (CoinGecko API)
            transparency_scan: Transparency assessment result with transparency_score
            anomaly_result: Output from detect_anomalies()

        Returns:
            {
                'risk_level': str,
                'forensic_findings': [str, ...],
                'market_context': {
                    'price_24h_change': float,
                    'volume_24h': float,
                    'market_cap': float,
                    'timestamp': str
                },
                'trigger_source': 'auto_forensic',
                'transparency_score': int
            }
        """
        return {
            'risk_level': anomaly_result['risk_level'],
            'forensic_findings': anomaly_result['findings'],
            'market_context': {
                'price_24h_change': market_token.get('price_change_24h', 0),
                'relative_deviation': market_token.get('relative_deviation', 0),
                'volume_24h': market_token.get('total_volume', 0),
                'market_cap': market_token.get('market_cap', 0),
                'supply': market_token.get('total_supply', market_token.get('circulating_supply', 0)),
                'timestamp': market_token.get('timestamp', 'unknown')
            },
            'trigger_source': 'auto_forensic',
            'transparency_score': transparency_scan.get('transparency_score', 0),
            'flags': anomaly_result['flags']
        }

    def should_trigger_for(
        self,
        anomaly_result: Dict[str, Any],
        transparency_score: int
    ) -> bool:
        """
        Gate check: determine if FOR report should be triggered.

        FOR reports are only triggered when BOTH conditions are met:
        1. Anomaly detected (anomaly_detected == True)
        2. Transparency score >= 13 (PARTIAL or better)

        Args:
            anomaly_result: Output from detect_anomalies()
            transparency_score: Numerical transparency score (0-30)

        Returns:
            True if FOR should be triggered, False otherwise
        """
        return (
            anomaly_result['anomaly_detected'] and
            transparency_score >= 13
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST BLOCK
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    detector = AutoForensicDetector()

    print("=" * 80)
    print("AUTO-FORENSIC DETECTOR TEST SCENARIOS")
    print("=" * 80)

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 1: Extreme Price Volatility
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n[SCENARIO 1] Extreme Price Spike")
    print("-" * 80)

    market_token_1 = {
        'symbol': 'TEST1',
        'price_change_24h': 45.5,  # > 20%
        'total_volume': 150_000_000,
        'volume_7d_avg': 50_000_000,
        'market_cap': 500_000_000,
        'whale_movement_supply_pct': 0.5,
        'exchange_netflow_supply_pct': 0.2,
        'timestamp': '2026-04-12T14:30:00Z'
    }

    result_1 = detector.detect_anomalies(market_token_1)
    print(f"Token: {market_token_1['symbol']}")
    print(f"Anomaly Detected: {result_1['anomaly_detected']}")
    print(f"Risk Level: {result_1['risk_level'].upper()}")
    print(f"Findings:")
    for finding in result_1['findings']:
        print(f"  • {finding}")

    # Check FOR trigger at different transparency levels
    print(f"\nFOR Trigger Decision:")
    for ts in [8, 13, 19, 26]:
        should_trigger = detector.should_trigger_for(result_1, ts)
        print(f"  Transparency {ts}: {'✓ TRIGGER' if should_trigger else '✗ NO TRIGGER'}")

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 2: Volume Spike + Whale Movement (Multiple Signals)
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n\n[SCENARIO 2] Volume Spike + Whale Movement")
    print("-" * 80)

    market_token_2 = {
        'symbol': 'TEST2',
        'price_change_24h': 8.3,  # < 20% threshold
        'total_volume': 500_000_000,
        'volume_7d_avg': 80_000_000,  # 6.25× ratio > 5×
        'market_cap': 2_000_000_000,
        'whale_movement_supply_pct': 2.5,  # > 2%
        'exchange_netflow_supply_pct': 0.8,
        'timestamp': '2026-04-12T15:15:00Z'
    }

    result_2 = detector.detect_anomalies(market_token_2)
    print(f"Token: {market_token_2['symbol']}")
    print(f"Anomaly Detected: {result_2['anomaly_detected']}")
    print(f"Risk Level: {result_2['risk_level'].upper()}")
    print(f"Findings:")
    for finding in result_2['findings']:
        print(f"  • {finding}")

    # Generate FOR data
    transparency_scan_2 = {'transparency_score': 15}
    for_data_2 = detector.generate_for_data(market_token_2, transparency_scan_2, result_2)
    print(f"\nGenerated FOR Data:")
    print(f"  Risk Level: {for_data_2['risk_level']}")
    print(f"  Market Context:")
    print(f"    - Price 24h: {for_data_2['market_context']['price_24h_change']:+.2f}%")
    print(f"    - Volume: ${for_data_2['market_context']['volume_24h']:,.0f}")
    print(f"    - Market Cap: ${for_data_2['market_context']['market_cap']:,.0f}")

    should_trigger = detector.should_trigger_for(result_2, 15)
    print(f"  FOR Trigger (transparency=15): {'✓ TRIGGERED' if should_trigger else '✗ NOT TRIGGERED'}")

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 3: No Anomalies (Normal Market)
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n\n[SCENARIO 3] Normal Market Conditions")
    print("-" * 80)

    market_token_3 = {
        'symbol': 'TEST3',
        'price_change_24h': 1.2,  # < 20%
        'total_volume': 100_000_000,
        'volume_7d_avg': 95_000_000,  # 1.05× ratio < 5×
        'market_cap': 3_000_000_000,
        'whale_movement_supply_pct': 0.1,  # < 2%
        'exchange_netflow_supply_pct': 0.05,  # < ±1%
        'timestamp': '2026-04-12T16:00:00Z'
    }

    result_3 = detector.detect_anomalies(market_token_3)
    print(f"Token: {market_token_3['symbol']}")
    print(f"Anomaly Detected: {result_3['anomaly_detected']}")
    print(f"Risk Level: {result_3['risk_level'].upper()}")
    if result_3['findings']:
        print(f"Findings:")
        for finding in result_3['findings']:
            print(f"  • {finding}")
    else:
        print("Findings: None (all metrics normal)")

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 4: Price Crash + Exchange Inflow (Panic Sell)
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n\n[SCENARIO 4] Price Crash + Exchange Inflow")
    print("-" * 80)

    market_token_4 = {
        'symbol': 'TEST4',
        'price_change_24h': -28.7,  # < -20% threshold
        'total_volume': 250_000_000,
        'volume_7d_avg': 60_000_000,  # 4.17× ratio < 5×
        'market_cap': 800_000_000,
        'whale_movement_supply_pct': 1.8,  # < 2%
        'exchange_netflow_supply_pct': 1.3,  # > ±1% (inflow)
        'timestamp': '2026-04-12T17:45:00Z'
    }

    result_4 = detector.detect_anomalies(market_token_4)
    print(f"Token: {market_token_4['symbol']}")
    print(f"Anomaly Detected: {result_4['anomaly_detected']}")
    print(f"Risk Level: {result_4['risk_level'].upper()}")
    print(f"Findings:")
    for finding in result_4['findings']:
        print(f"  • {finding}")

    # Test edge case: High risk but low transparency
    print(f"\nFOR Trigger Decision:")
    for ts in [8, 12, 13, 25]:
        should_trigger = detector.should_trigger_for(result_4, ts)
        status = '✓ TRIGGER' if should_trigger else '✗ NO TRIGGER'
        print(f"  Transparency {ts}: {status}")

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 5: All Anomalies (CRITICAL Risk)
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n\n[SCENARIO 5] Multiple Anomalies (CRITICAL Risk)")
    print("-" * 80)

    market_token_5 = {
        'symbol': 'TEST5',
        'price_change_24h': -35.0,  # > ±20%
        'total_volume': 600_000_000,
        'volume_7d_avg': 100_000_000,  # 6× ratio > 5×
        'market_cap': 400_000_000,
        'whale_movement_supply_pct': 3.5,  # > 2%
        'exchange_netflow_supply_pct': -1.5,  # < -1%
        'timestamp': '2026-04-12T18:30:00Z'
    }

    result_5 = detector.detect_anomalies(market_token_5)
    print(f"Token: {market_token_5['symbol']}")
    print(f"Anomaly Detected: {result_5['anomaly_detected']}")
    print(f"Risk Level: {result_5['risk_level'].upper()}")
    print(f"Findings:")
    for finding in result_5['findings']:
        print(f"  • {finding}")

    transparency_scan_5 = {'transparency_score': 20}
    for_data_5 = detector.generate_for_data(market_token_5, transparency_scan_5, result_5)
    should_trigger = detector.should_trigger_for(result_5, 20)
    print(f"\nFOR Report Trigger: {'✓ TRIGGERED (CRITICAL)' if should_trigger else '✗ NOT TRIGGERED'}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
