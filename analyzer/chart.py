"""
chart.py
---------
Converts an OHLCV DataFrame into the plain-JSON series shape the
frontend candlestick chart (TradingView's lightweight-charts library)
expects, plus EMA overlay lines computed over the same window.

Kept separate from technical.py because that module returns only the
*latest* value of each indicator (for scoring); charts need the full
time series instead.
"""

import numpy as np
import pandas as pd
from analyzer.technical import ema


def build_chart_payload(history, include_emas=(20, 50, 200)) -> dict:
    """
    history: OHLCV DataFrame with a DatetimeIndex (as returned by
    yfinance or the demo generators).

    Returns:
        {
          "candles": [{"time": unix_ts, "open":.., "high":.., "low":.., "close":..}, ...],
          "volume": [{"time": unix_ts, "value":.., "color": "up"|"down"}, ...],
          "emas": {"ema20": [{"time":.., "value":..}, ...], ...}
        }
    lightweight-charts wants Unix seconds (or 'YYYY-MM-DD' strings for
    daily-only series) for the `time` field - we use Unix seconds
    throughout so both daily and intraday series work the same way.
    """
    if history is None or history.empty:
        return {"candles": [], "volume": [], "emas": {}}

    df = history.dropna(subset=["Open", "High", "Low", "Close"])
    # Resolution-independent conversion to Unix seconds. Don't use
    # `.astype('int64') // 10**9` here - pandas 2.x/3.x can store the
    # index at second/microsecond/nanosecond resolution depending on
    # how it was constructed, and that shortcut silently assumes
    # nanoseconds, producing wildly wrong timestamps when it isn't.
    epoch = pd.Timestamp("1970-01-01", tz=df.index.tz)
    times = ((df.index - epoch) // pd.Timedelta(seconds=1)).tolist()

    candles = [
        {
            "time": int(t),
            "open": round(float(o), 2),
            "high": round(float(h), 2),
            "low": round(float(l), 2),
            "close": round(float(c), 2),
        }
        for t, o, h, l, c in zip(times, df["Open"], df["High"], df["Low"], df["Close"])
    ]

    volume = []
    if "Volume" in df.columns:
        for t, v, o, c in zip(times, df["Volume"], df["Open"], df["Close"]):
            volume.append({
                "time": int(t),
                "value": float(v) if not np.isnan(v) else 0,
                "color": "up" if c >= o else "down",
            })

    emas = {}
    for span in include_emas:
        if len(df) < span:
            continue  # not enough bars for this EMA to mean anything yet
        series = ema(df["Close"], span)
        emas[f"ema{span}"] = [
            {"time": int(t), "value": round(float(v), 2)}
            for t, v in zip(times, series) if not np.isnan(v)
        ]

    return {"candles": candles, "volume": volume, "emas": emas}
