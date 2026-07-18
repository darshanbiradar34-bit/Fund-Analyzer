"""
technical.py
-------------
Computes technical indicators from OHLCV price history for stocks,
and simpler trend/volatility indicators for mutual fund NAV series.

All functions take a pandas DataFrame and return either a Series
(indicator over time) or a dict of the latest computed values.
"""

import pandas as pd
import numpy as np


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range - needs High/Low/Close columns."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def compute_stock_technicals(history: pd.DataFrame) -> dict:
    """
    Given OHLCV history (from yfinance), compute the latest values
    of all key indicators plus a simple trend read.
    """
    if history is None or history.empty or len(history) < 60:
        return {"error": "Insufficient price history for technical analysis"}

    close = history["Close"]

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema100 = ema(close, 100)
    ema200 = ema(close, 200) if len(close) >= 200 else pd.Series([np.nan] * len(close))

    rsi14 = rsi(close, 14)
    macd_line, signal_line, hist = macd(close)
    atr14 = atr(history, 14)
    bb_upper, bb_mid, bb_lower = bollinger_bands(close)

    last_close = close.iloc[-1]
    vol_avg_20 = history["Volume"].rolling(20).mean().iloc[-1] if "Volume" in history else np.nan
    last_vol = history["Volume"].iloc[-1] if "Volume" in history else np.nan

    # 52-week high/low
    lookback = min(len(close), 252)
    high_52w = close.iloc[-lookback:].max()
    low_52w = close.iloc[-lookback:].min()

    return {
        "last_close": round(float(last_close), 2),
        "ema20": round(float(ema20.iloc[-1]), 2),
        "ema50": round(float(ema50.iloc[-1]), 2),
        "ema100": round(float(ema100.iloc[-1]), 2),
        "ema200": round(float(ema200.iloc[-1]), 2) if not np.isnan(ema200.iloc[-1]) else None,
        "rsi14": round(float(rsi14.iloc[-1]), 2) if not np.isnan(rsi14.iloc[-1]) else None,
        "macd_line": round(float(macd_line.iloc[-1]), 3),
        "macd_signal": round(float(signal_line.iloc[-1]), 3),
        "macd_histogram": round(float(hist.iloc[-1]), 3),
        "atr14": round(float(atr14.iloc[-1]), 2) if not np.isnan(atr14.iloc[-1]) else None,
        "bb_upper": round(float(bb_upper.iloc[-1]), 2),
        "bb_mid": round(float(bb_mid.iloc[-1]), 2),
        "bb_lower": round(float(bb_lower.iloc[-1]), 2),
        "volume_vs_20d_avg_pct": round(float((last_vol / vol_avg_20 - 1) * 100), 1) if vol_avg_20 else None,
        "high_52w": round(float(high_52w), 2),
        "low_52w": round(float(low_52w), 2),
        "pct_from_52w_high": round(float((last_close / high_52w - 1) * 100), 2),
        "pct_from_52w_low": round(float((last_close / low_52w - 1) * 100), 2),
        "trend": _read_trend(last_close, ema20.iloc[-1], ema50.iloc[-1],
                              ema200.iloc[-1] if not np.isnan(ema200.iloc[-1]) else None),
    }


def _read_trend(price, e20, e50, e200) -> str:
    """Simple moving-average-stack based trend classification."""
    if e200 is not None:
        if price > e20 > e50 > e200:
            return "Strong Uptrend"
        if price < e20 < e50 < e200:
            return "Strong Downtrend"
    if price > e20 and price > e50:
        return "Uptrend"
    if price < e20 and price < e50:
        return "Downtrend"
    return "Sideways / Mixed"


def compute_fund_technicals(nav_history: pd.DataFrame) -> dict:
    """
    Simplified trend/momentum read for a mutual fund NAV series
    (no volume/OHLC available for MFs, so this is lighter weight
    than the stock version).
    """
    if nav_history is None or nav_history.empty or len(nav_history) < 60:
        return {"error": "Insufficient NAV history for technical analysis"}

    nav = nav_history.set_index("date")["nav"]

    sma50 = sma(nav, 50)
    sma200 = sma(nav, 200) if len(nav) >= 200 else pd.Series([np.nan] * len(nav))
    rsi14 = rsi(nav, 14)

    last_nav = nav.iloc[-1]

    # Rolling returns - the standard way to judge a fund's consistency
    def rolling_return(days):
        if len(nav) <= days:
            return None
        past = nav.iloc[-days - 1]
        years = days / 365
        return round(((last_nav / past) ** (1 / years) - 1) * 100, 2)

    return {
        "last_nav": round(float(last_nav), 4),
        "sma50": round(float(sma50.iloc[-1]), 4) if not np.isnan(sma50.iloc[-1]) else None,
        "sma200": round(float(sma200.iloc[-1]), 4) if not np.isnan(sma200.iloc[-1]) else None,
        "rsi14": round(float(rsi14.iloc[-1]), 2) if not np.isnan(rsi14.iloc[-1]) else None,
        "cagr_1y": rolling_return(365),
        "cagr_3y": rolling_return(365 * 3),
        "cagr_5y": rolling_return(365 * 5),
        "trend": "Uptrend" if not np.isnan(sma50.iloc[-1]) and last_nav > sma50.iloc[-1] else "Downtrend/Sideways",
    }
