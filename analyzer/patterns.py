"""
patterns.py
------------
Rule-based candlestick pattern detection over the most recent bars.

Each detector looks only at the last 1-3 candles (the standard
definition for these patterns) and returns True/False plus a short
explanation. This is intentionally simple, threshold-based logic -
not a trained classifier - so every detection is explainable.

LIMITATION: candlestick patterns are a probabilistic signal, not a
guarantee. They work best combined with trend/volume context (which
scoring.py already accounts for separately), not read in isolation.
"""

import pandas as pd
import numpy as np


def _body(row) -> float:
    return abs(row["Close"] - row["Open"])


def _range(row) -> float:
    return row["High"] - row["Low"]


def _upper_wick(row) -> float:
    return row["High"] - max(row["Close"], row["Open"])


def _lower_wick(row) -> float:
    return min(row["Close"], row["Open"]) - row["Low"]


def _is_bullish(row) -> bool:
    return row["Close"] > row["Open"]


def _is_bearish(row) -> bool:
    return row["Close"] < row["Open"]


def detect_candlestick_patterns(history: pd.DataFrame, lookback: int = 5) -> list:
    """
    Checks the last few candles against a set of classic pattern
    definitions. Returns a list of {name, signal, description} dicts
    for every pattern found (usually 0-2 on any given day).
    """
    if history is None or len(history) < 3:
        return []

    found = []
    recent = history.iloc[-lookback:] if len(history) >= lookback else history
    c0 = recent.iloc[-1]                              # today
    c1 = recent.iloc[-2] if len(recent) >= 2 else None  # yesterday
    c2 = recent.iloc[-3] if len(recent) >= 3 else None  # day before

    avg_range = recent["High"].sub(recent["Low"]).mean()
    if avg_range == 0 or np.isnan(avg_range):
        return []

    # ---- Single-candle patterns ----

    body0 = _body(c0)
    range0 = _range(c0)

    if range0 > 0 and body0 <= 0.1 * range0:
        found.append({
            "name": "Doji",
            "signal": "neutral",
            "description": "Open and close nearly equal - indecision between buyers and sellers.",
        })

    if range0 > 0:
        lower_wick = _lower_wick(c0)
        upper_wick = _upper_wick(c0)
        if lower_wick >= 2 * body0 and upper_wick <= 0.3 * body0 and body0 > 0:
            label = "Hammer" if _is_bullish(c0) or True else "Hammer"
            # Direction context: hammer after a decline is bullish reversal read
            prior_trend_down = c1 is not None and c1["Close"] < recent["Close"].iloc[0]
            found.append({
                "name": "Hammer",
                "signal": "bullish" if prior_trend_down else "neutral",
                "description": "Long lower wick, small body near the top - buyers rejected lower prices.",
            })
        if upper_wick >= 2 * body0 and lower_wick <= 0.3 * body0 and body0 > 0:
            prior_trend_up = c1 is not None and c1["Close"] > recent["Close"].iloc[0]
            found.append({
                "name": "Shooting Star",
                "signal": "bearish" if prior_trend_up else "neutral",
                "description": "Long upper wick, small body near the bottom - sellers rejected higher prices.",
            })

    if body0 >= 0.9 * range0 and range0 > 0:
        found.append({
            "name": "Marubozu",
            "signal": "bullish" if _is_bullish(c0) else "bearish",
            "description": "Almost no wicks - one side was in full control all session.",
        })

    # ---- Two-candle patterns ----
    if c1 is not None:
        body1 = _body(c1)

        # Bullish engulfing
        if _is_bearish(c1) and _is_bullish(c0) and c0["Close"] >= c1["Open"] and c0["Open"] <= c1["Close"]:
            found.append({
                "name": "Bullish Engulfing",
                "signal": "bullish",
                "description": "Today's green candle fully engulfs yesterday's red candle - buyers took control.",
            })

        # Bearish engulfing
        if _is_bullish(c1) and _is_bearish(c0) and c0["Open"] >= c1["Close"] and c0["Close"] <= c1["Open"]:
            found.append({
                "name": "Bearish Engulfing",
                "signal": "bearish",
                "description": "Today's red candle fully engulfs yesterday's green candle - sellers took control.",
            })

        # Harami (today's body inside yesterday's body)
        if body1 > 0 and body0 < body1 * 0.6:
            hi = max(c1["Open"], c1["Close"])
            lo = min(c1["Open"], c1["Close"])
            if lo <= c0["Open"] <= hi and lo <= c0["Close"] <= hi:
                found.append({
                    "name": "Harami",
                    "signal": "bullish" if _is_bearish(c1) else "bearish",
                    "description": "Small candle contained within the prior candle's range - momentum stalling.",
                })

        # Inside bar / Outside bar (range-based, not body-based)
        if c0["High"] <= c1["High"] and c0["Low"] >= c1["Low"]:
            found.append({
                "name": "Inside Bar",
                "signal": "neutral",
                "description": "Today's full range sits inside yesterday's - contraction, often precedes a breakout.",
            })
        if c0["High"] > c1["High"] and c0["Low"] < c1["Low"]:
            found.append({
                "name": "Outside Bar",
                "signal": "bullish" if _is_bullish(c0) else "bearish",
                "description": "Today's range fully exceeds yesterday's on both sides - a volatility expansion.",
            })

    # ---- Three-candle patterns ----
    if c1 is not None and c2 is not None:
        body2 = _body(c2)

        # Morning Star: big red, small body (gap down), big green closing well into candle 1
        if (_is_bearish(c2) and body2 > avg_range * 0.5
                and _body(c1) < avg_range * 0.3
                and _is_bullish(c0) and c0["Close"] > (c2["Open"] + c2["Close"]) / 2):
            found.append({
                "name": "Morning Star",
                "signal": "bullish",
                "description": "Big decline, a pause, then a strong rally - classic bottoming reversal pattern.",
            })

        # Evening Star: big green, small body, big red closing well into candle 1
        if (_is_bullish(c2) and body2 > avg_range * 0.5
                and _body(c1) < avg_range * 0.3
                and _is_bearish(c0) and c0["Close"] < (c2["Open"] + c2["Close"]) / 2):
            found.append({
                "name": "Evening Star",
                "signal": "bearish",
                "description": "Big rally, a pause, then a strong decline - classic topping reversal pattern.",
            })

    return found
