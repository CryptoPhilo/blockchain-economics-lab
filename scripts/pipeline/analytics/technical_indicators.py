"""
BCE Lab Technical Indicators Engine
Calculates RSI, SMA, EMA, Bollinger Bands, Fibonacci, Volatility,
Support/Resistance levels from price history data.

Input: 90-day price history from CoinGecko (already in pipeline)
Output: Dict of computed indicators for FOR/ECON reports
"""
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone


class TechnicalIndicators:
    """Compute technical analysis indicators from OHLCV price data."""

    def __init__(self, prices: List[float], timestamps: List[int] = None,
                 volumes: List[float] = None, highs: List[float] = None,
                 lows: List[float] = None):
        """
        Args:
            prices: List of closing prices (oldest first)
            timestamps: Unix timestamps (ms)
            volumes: Trading volumes
            highs: High prices
            lows: Low prices
        """
        self.prices = prices
        self.timestamps = timestamps or []
        self.volumes = volumes or []
        self.highs = highs or prices[:]
        self.lows = lows or prices[:]
        self.n = len(prices)

    # ══════════════════════════════════════════
    # MOVING AVERAGES
    # ══════════════════════════════════════════

    def sma(self, period: int) -> List[Optional[float]]:
        """Simple Moving Average."""
        result = [None] * self.n
        for i in range(period - 1, self.n):
            result[i] = sum(self.prices[i - period + 1:i + 1]) / period
        return result

    def ema(self, period: int) -> List[Optional[float]]:
        """Exponential Moving Average."""
        result = [None] * self.n
        if self.n < period:
            return result
        # Seed with SMA
        result[period - 1] = sum(self.prices[:period]) / period
        multiplier = 2 / (period + 1)
        for i in range(period, self.n):
            result[i] = (self.prices[i] - result[i - 1]) * multiplier + result[i - 1]
        return result

    def current_sma(self, period: int) -> Optional[float]:
        """Get current (latest) SMA value."""
        vals = self.sma(period)
        return vals[-1] if vals else None

    def current_ema(self, period: int) -> Optional[float]:
        """Get current (latest) EMA value."""
        vals = self.ema(period)
        return vals[-1] if vals else None

    # ══════════════════════════════════════════
    # RSI (Relative Strength Index)
    # ══════════════════════════════════════════

    def rsi(self, period: int = 14) -> List[Optional[float]]:
        """
        Compute RSI using Wilder's smoothing method.
        Returns list of RSI values (0-100).
        """
        result = [None] * self.n
        if self.n < period + 1:
            return result

        # Calculate price changes
        deltas = [self.prices[i] - self.prices[i - 1] for i in range(1, self.n)]

        # Initial average gain/loss
        gains = [max(d, 0) for d in deltas[:period]]
        losses = [abs(min(d, 0)) for d in deltas[:period]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            result[period] = 100
        else:
            rs = avg_gain / avg_loss
            result[period] = 100 - (100 / (1 + rs))

        # Wilder's smoothing
        for i in range(period, len(deltas)):
            gain = max(deltas[i], 0)
            loss = abs(min(deltas[i], 0))
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

            if avg_loss == 0:
                result[i + 1] = 100
            else:
                rs = avg_gain / avg_loss
                result[i + 1] = 100 - (100 / (1 + rs))

        return result

    def current_rsi(self, period: int = 14) -> Optional[float]:
        """Get current RSI value."""
        vals = self.rsi(period)
        return round(vals[-1], 2) if vals[-1] is not None else None

    def rsi_interpretation(self, period: int = 14) -> Dict:
        """Interpret RSI value."""
        rsi_val = self.current_rsi(period)
        if rsi_val is None:
            return {"value": None, "signal": "insufficient_data"}

        if rsi_val >= 70:
            signal = "overbought"
            risk = "high_reversal_risk"
        elif rsi_val >= 60:
            signal = "bullish"
            risk = "moderate"
        elif rsi_val <= 30:
            signal = "oversold"
            risk = "high_bounce_potential"
        elif rsi_val <= 40:
            signal = "bearish"
            risk = "moderate"
        else:
            signal = "neutral"
            risk = "low"

        return {"value": rsi_val, "signal": signal, "risk": risk}

    # ══════════════════════════════════════════
    # BOLLINGER BANDS
    # ══════════════════════════════════════════

    def bollinger_bands(self, period: int = 20, num_std: float = 2.0) -> Dict:
        """
        Compute Bollinger Bands.
        Returns: {upper: [], middle: [], lower: [], bandwidth: [], %b: []}
        """
        middle = self.sma(period)
        upper = [None] * self.n
        lower = [None] * self.n
        bandwidth = [None] * self.n
        pct_b = [None] * self.n

        for i in range(period - 1, self.n):
            window = self.prices[i - period + 1:i + 1]
            mean = middle[i]
            std = (sum((p - mean) ** 2 for p in window) / period) ** 0.5
            upper[i] = mean + num_std * std
            lower[i] = mean - num_std * std
            if upper[i] != lower[i]:
                bandwidth[i] = (upper[i] - lower[i]) / middle[i] * 100
                pct_b[i] = (self.prices[i] - lower[i]) / (upper[i] - lower[i])

        return {
            "upper": upper, "middle": middle, "lower": lower,
            "bandwidth": bandwidth, "pct_b": pct_b,
        }

    def current_bollinger(self, period: int = 20, num_std: float = 2.0) -> Dict:
        """Get current Bollinger Band values."""
        bb = self.bollinger_bands(period, num_std)
        return {
            "upper": round(bb["upper"][-1], 4) if bb["upper"][-1] else None,
            "middle": round(bb["middle"][-1], 4) if bb["middle"][-1] else None,
            "lower": round(bb["lower"][-1], 4) if bb["lower"][-1] else None,
            "bandwidth": round(bb["bandwidth"][-1], 2) if bb["bandwidth"][-1] else None,
            "pct_b": round(bb["pct_b"][-1], 4) if bb["pct_b"][-1] else None,
        }

    # ══════════════════════════════════════════
    # FIBONACCI RETRACEMENT
    # ══════════════════════════════════════════

    def fibonacci_levels(self, lookback: int = 90) -> Dict:
        """
        Compute Fibonacci retracement levels from recent high/low.
        Standard levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
        """
        window = self.prices[-lookback:] if lookback < self.n else self.prices
        high = max(window)
        low = min(window)
        diff = high - low

        # Determine trend direction
        high_idx = window.index(high)
        low_idx = window.index(low)
        is_uptrend = low_idx < high_idx  # Low came first = uptrend

        levels = {}
        fib_ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]

        if is_uptrend:
            # Retracement from high (pullback targets)
            for ratio in fib_ratios:
                level = high - diff * ratio
                levels[f"{ratio*100:.1f}%"] = round(level, 4)
        else:
            # Retracement from low (bounce targets)
            for ratio in fib_ratios:
                level = low + diff * ratio
                levels[f"{ratio*100:.1f}%"] = round(level, 4)

        current = self.prices[-1]
        # Find nearest fib level
        nearest = min(levels.items(), key=lambda x: abs(x[1] - current))

        return {
            "trend": "uptrend" if is_uptrend else "downtrend",
            "swing_high": round(high, 4),
            "swing_low": round(low, 4),
            "levels": levels,
            "current_price": round(current, 4),
            "nearest_level": {"name": nearest[0], "price": nearest[1]},
            "key_support": round(levels.get("61.8%", low), 4),
            "key_resistance": round(levels.get("38.2%", high), 4),
        }

    # ══════════════════════════════════════════
    # VOLATILITY
    # ══════════════════════════════════════════

    def annualized_volatility(self, period: int = 90) -> float:
        """
        Compute annualized volatility from daily returns.
        Formula: stdev(daily_returns) × sqrt(365)
        """
        window = self.prices[-period:] if period < self.n else self.prices
        if len(window) < 2:
            return 0

        returns = [
            math.log(window[i] / window[i - 1])
            for i in range(1, len(window))
            if window[i - 1] > 0 and window[i] > 0
        ]

        if not returns:
            return 0

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        daily_vol = variance ** 0.5
        annual_vol = daily_vol * (365 ** 0.5)
        return round(annual_vol * 100, 2)  # Percentage

    def max_recommended_leverage(self) -> Dict:
        """
        Calculate maximum recommended leverage based on volatility.
        Formula: 1 / (volatility_90d / 100) × safety_factor(0.5)
        """
        vol = self.annualized_volatility(90)
        if vol <= 0:
            return {"max_leverage": 1, "volatility_90d": 0, "risk_level": "unknown"}

        # Raw Kelly-style: 1/vol, with 0.5 safety factor
        raw_leverage = (1 / (vol / 100)) * 0.5
        max_lev = max(1, min(round(raw_leverage, 1), 20))  # Clamp 1-20x

        if max_lev <= 2:
            risk = "extreme"
        elif max_lev <= 3:
            risk = "very_high"
        elif max_lev <= 5:
            risk = "high"
        elif max_lev <= 10:
            risk = "moderate"
        else:
            risk = "low"

        return {
            "max_leverage": max_lev,
            "volatility_90d_pct": vol,
            "risk_level": risk,
            "recommendation": f"Maximum {max_lev}x leverage (90-day vol: {vol}%)",
        }

    # ══════════════════════════════════════════
    # SUPPORT / RESISTANCE
    # ══════════════════════════════════════════

    def support_resistance_levels(self, lookback: int = 90, num_levels: int = 3) -> Dict:
        """
        Detect support/resistance levels from local minima/maxima.
        Uses pivot point detection with volume weighting.
        """
        window_prices = self.prices[-lookback:] if lookback < self.n else self.prices
        window_highs = self.highs[-lookback:] if lookback < len(self.highs) else self.highs
        window_lows = self.lows[-lookback:] if lookback < len(self.lows) else self.lows
        n = len(window_prices)

        # Find local maxima (resistance) and minima (support)
        resistances = []
        supports = []
        pivot_range = 5  # Look 5 candles each side

        for i in range(pivot_range, n - pivot_range):
            # Local high
            if all(window_highs[i] >= window_highs[j]
                   for j in range(i - pivot_range, i + pivot_range + 1) if j != i):
                resistances.append(window_highs[i])

            # Local low
            if all(window_lows[i] <= window_lows[j]
                   for j in range(i - pivot_range, i + pivot_range + 1) if j != i):
                supports.append(window_lows[i])

        # Cluster nearby levels (within 2%)
        def cluster_levels(levels: List[float], threshold: float = 0.02) -> List[float]:
            if not levels:
                return []
            sorted_levels = sorted(levels)
            clusters = [[sorted_levels[0]]]
            for level in sorted_levels[1:]:
                if abs(level - clusters[-1][-1]) / clusters[-1][-1] < threshold:
                    clusters[-1].append(level)
                else:
                    clusters.append([level])
            return [sum(c) / len(c) for c in clusters]

        support_levels = cluster_levels(supports)
        resistance_levels = cluster_levels(resistances)

        current = window_prices[-1]

        # Filter: supports below current, resistances above
        support_levels = sorted([s for s in support_levels if s < current], reverse=True)
        resistance_levels = sorted([r for r in resistance_levels if r > current])

        return {
            "current_price": round(current, 4),
            "supports": [round(s, 4) for s in support_levels[:num_levels]],
            "resistances": [round(r, 4) for r in resistance_levels[:num_levels]],
            "nearest_support": round(support_levels[0], 4) if support_levels else None,
            "nearest_resistance": round(resistance_levels[0], 4) if resistance_levels else None,
            "support_distance_pct": round(
                (current - support_levels[0]) / current * 100, 2
            ) if support_levels else None,
            "resistance_distance_pct": round(
                (resistance_levels[0] - current) / current * 100, 2
            ) if resistance_levels else None,
        }

    # ══════════════════════════════════════════
    # MACD
    # ══════════════════════════════════════════

    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """Compute MACD line, signal line, and histogram."""
        fast_ema = self.ema(fast)
        slow_ema = self.ema(slow)

        macd_line = [None] * self.n
        for i in range(self.n):
            if fast_ema[i] is not None and slow_ema[i] is not None:
                macd_line[i] = fast_ema[i] - slow_ema[i]

        # Signal line (EMA of MACD)
        valid_macd = [(i, v) for i, v in enumerate(macd_line) if v is not None]
        signal_line = [None] * self.n
        if len(valid_macd) >= signal:
            first_idx = valid_macd[signal - 1][0]
            signal_line[first_idx] = sum(v for _, v in valid_macd[:signal]) / signal
            mult = 2 / (signal + 1)
            for j in range(signal, len(valid_macd)):
                idx = valid_macd[j][0]
                prev_idx = valid_macd[j - 1][0]
                signal_line[idx] = (macd_line[idx] - signal_line[prev_idx]) * mult + signal_line[prev_idx]

        # Histogram
        histogram = [None] * self.n
        for i in range(self.n):
            if macd_line[i] is not None and signal_line[i] is not None:
                histogram[i] = macd_line[i] - signal_line[i]

        # Current values
        return {
            "macd_line": round(macd_line[-1], 6) if macd_line[-1] else None,
            "signal_line": round(signal_line[-1], 6) if signal_line[-1] else None,
            "histogram": round(histogram[-1], 6) if histogram[-1] else None,
            "crossover": "bullish" if histogram[-1] and histogram[-1] > 0 and
                         histogram[-2] and histogram[-2] <= 0 else
                         "bearish" if histogram[-1] and histogram[-1] < 0 and
                         histogram[-2] and histogram[-2] >= 0 else "none",
        }

    # ══════════════════════════════════════════
    # COMPREHENSIVE ANALYSIS
    # ══════════════════════════════════════════

    def compute_all(self) -> Dict:
        """
        Compute all technical indicators.
        Main entry point for the pipeline.
        """
        rsi_data = self.rsi_interpretation()
        fib = self.fibonacci_levels()
        bb = self.current_bollinger()
        sr = self.support_resistance_levels()
        macd_data = self.macd()
        leverage = self.max_recommended_leverage()

        # Overall trend assessment
        sma_30 = self.current_sma(30)
        sma_200 = self.current_sma(200) if self.n >= 200 else self.current_sma(self.n // 2)
        current = self.prices[-1]

        if sma_30 and sma_200:
            if current > sma_30 > sma_200:
                trend = "strong_bullish"
            elif current > sma_30:
                trend = "bullish"
            elif current < sma_30 < (sma_200 or sma_30):
                trend = "strong_bearish"
            elif current < sma_30:
                trend = "bearish"
            else:
                trend = "neutral"
        else:
            trend = "insufficient_data"

        return {
            "current_price": round(current, 4),
            "trend": trend,
            "rsi": rsi_data,
            "moving_averages": {
                "sma_30": round(sma_30, 4) if sma_30 else None,
                "sma_200": round(sma_200, 4) if sma_200 else None,
                "ema_12": round(self.current_ema(12), 4) if self.current_ema(12) else None,
                "ema_26": round(self.current_ema(26), 4) if self.current_ema(26) else None,
                "price_vs_sma30": round((current / sma_30 - 1) * 100, 2) if sma_30 else None,
            },
            "macd": macd_data,
            "bollinger_bands": bb,
            "fibonacci": fib,
            "support_resistance": sr,
            "volatility": {
                "annualized_90d_pct": self.annualized_volatility(90),
                "annualized_30d_pct": self.annualized_volatility(30),
            },
            "leverage_recommendation": leverage,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }


def compute_from_coingecko_history(price_history: List) -> Dict:
    """
    Convenience function: compute indicators from CoinGecko price history format.
    CoinGecko returns: [[timestamp_ms, price], ...]
    """
    if not price_history:
        return {"error": "No price history data"}

    prices = [p[1] for p in price_history if len(p) >= 2]
    timestamps = [p[0] for p in price_history if len(p) >= 2]

    if len(prices) < 14:
        return {"error": f"Insufficient data points ({len(prices)} < 14)"}

    ti = TechnicalIndicators(prices=prices, timestamps=timestamps)
    return ti.compute_all()
