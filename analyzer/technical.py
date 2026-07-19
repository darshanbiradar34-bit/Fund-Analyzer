"""
technical.py
-------------
Computes technical indicators from OHLCV price history for stocks,
and simpler trend/volatility indicators for mutual fund NAV series.

Phase 1 expansion: added moving average stack (EMA9/20/50/100/200,
SMA20/50/200), ADX/+DI/-DI, ROC, CCI, Williams %R, Stochastic RSI,
OBV, rolling VWAP, MFI, CMF, Keltner Channel, historical volatility,
ATR%, Bollinger width, golden/death cross, market structure
(higher-highs/higher-lows swing read), and a bucketed trend-strength
label. All ORIGINAL keys are preserved unchanged so scoring.py keeps
working without modification.

LIMITATION: VWAP is normally an *intraday* session indicator. Since
this app works from daily bars (not tick/minute data), "vwap" here is
a rolling 20-day volume-weighted average price - a reasonable daily
proxy, but not the same thing a day-trader means by VWAP. Documented
here and flagged in the UI rather than silently mislabeled.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Core indicator building blocks
# ---------------------------------------------------------------------------

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


def stochastic_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    r = rsi(series, period)
    lowest = r.rolling(window=period, min_periods=period).min()
    highest = r.rolling(window=period, min_periods=period).max()
    return ((r - lowest) / (highest - lowest).replace(0, np.nan)) * 100


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


def true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    return pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)


def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def keltner_channel(df: pd.DataFrame, window: int = 20, atr_mult: float = 2.0):
    mid = ema(df["Close"], window)
    a = atr(df, window)
    upper = mid + atr_mult * a
    lower = mid - atr_mult * a
    return upper, mid, lower


def adx(df: pd.DataFrame, period: int = 14):
    """Average Directional Index, plus the +DI/-DI lines it's built from."""
    high, low, close = df["High"], df["Low"], df["Close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    tr = true_range(df)
    atr_smooth = tr.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_smooth.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_smooth.replace(0, np.nan))

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_line = dx.ewm(alpha=1 / period, adjust=False).mean()

    return adx_line, plus_di, minus_di


def roc(series: pd.Series, period: int = 12) -> pd.Series:
    """Rate of Change (%)."""
    return ((series - series.shift(period)) / series.shift(period)) * 100


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Commodity Channel Index."""
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    sma_tp = sma(typical_price, period)
    mean_dev = typical_price.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (typical_price - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    highest_high = df["High"].rolling(period).max()
    lowest_low = df["Low"].rolling(period).min()
    return -100 * (highest_high - df["Close"]) / (highest_high - lowest_low).replace(0, np.nan)


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume - cumulative volume, signed by price direction."""
    direction = np.sign(df["Close"].diff()).fillna(0)
    return (direction * df["Volume"]).cumsum()


def rolling_vwap(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Rolling volume-weighted average price over `window` days.
    See module docstring for why this is a daily proxy, not intraday VWAP.
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    pv = typical_price * df["Volume"]
    return pv.rolling(window).sum() / df["Volume"].rolling(window).sum().replace(0, np.nan)


def money_flow_index(df: pd.DataFrame, period: int = 14) -> pd.Series:
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    raw_money_flow = typical_price * df["Volume"]
    direction = np.sign(typical_price.diff()).fillna(0)

    positive_flow = (raw_money_flow.where(direction > 0, 0)).rolling(period).sum()
    negative_flow = (raw_money_flow.where(direction < 0, 0)).rolling(period).sum()

    money_ratio = positive_flow / negative_flow.replace(0, np.nan)
    return 100 - (100 / (1 + money_ratio))


def chaikin_money_flow(df: pd.DataFrame, period: int = 20) -> pd.Series:
    high, low, close, vol = df["High"], df["Low"], df["Close"], df["Volume"]
    mf_multiplier = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    mf_volume = mf_multiplier * vol
    return mf_volume.rolling(period).sum() / vol.rolling(period).sum().replace(0, np.nan)


def historical_volatility(series: pd.Series, window: int = 20) -> pd.Series:
    """Annualized historical volatility (%) from daily log returns."""
    log_returns = np.log(series / series.shift(1))
    return log_returns.rolling(window).std() * np.sqrt(252) * 100


# ---------------------------------------------------------------------------
# Market structure (swing highs/lows -> higher-highs/higher-lows read)
# ---------------------------------------------------------------------------

def _find_swings(series: pd.Series, order: int = 5):
    """
    Simple local-extrema swing detector: a point is a swing high if it's
    the max within +/- `order` bars, swing low if it's the min.
    Returns (swing_high_indices, swing_low_indices) as lists of integer
    positions into `series`.
    """
    values = series.values
    n = len(values)
    highs, lows = [], []
    for i in range(order, n - order):
        window = values[i - order: i + order + 1]
        if values[i] == window.max() and np.argmax(window) == order:
            highs.append(i)
        if values[i] == window.min() and np.argmin(window) == order:
            lows.append(i)
    return highs, lows


def read_market_structure(history: pd.DataFrame, order: int = 5) -> dict:
    high_idx, low_idx = _find_swings(history["Close"], order=order)

    structure = "Insufficient Data"
    detail = "Not enough price history to identify swing points."

    if len(high_idx) >= 2 and len(low_idx) >= 2:
        last_two_highs = history["Close"].iloc[high_idx[-2:]].values
        last_two_lows = history["Close"].iloc[low_idx[-2:]].values

        higher_highs = last_two_highs[1] > last_two_highs[0]
        higher_lows = last_two_lows[1] > last_two_lows[0]

        if higher_highs and higher_lows:
            structure = "Higher Highs & Higher Lows"
            detail = "Bullish market structure - each swing is making progress above the last."
        elif not higher_highs and not higher_lows:
            structure = "Lower Highs & Lower Lows"
            detail = "Bearish market structure - each swing is failing below the last."
        else:
            structure = "Mixed Structure"
            detail = "Swing highs and lows disagree - no clean directional structure yet."

    return {"structure": structure, "detail": detail}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_stock_technicals(history: pd.DataFrame) -> dict:
    """
    Given OHLCV history (from yfinance), compute the latest values
    of all key indicators plus a simple trend read.

    Returns a flat dict. Original (Phase-0) keys are unchanged so
    scoring.py's existing logic keeps working; new Phase-1 keys are
    additive.
    """
    if history is None or history.empty or len(history) < 60:
        return {"error": "Insufficient price history for technical analysis"}

    close = history["Close"]
    has_volume = bool("Volume" in history and history["Volume"].notna().any())

    # ---- Moving averages ----
    ema9 = ema(close, 9)
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema100 = ema(close, 100)
    ema200 = ema(close, 200) if len(close) >= 200 else pd.Series([np.nan] * len(close), index=close.index)
    sma20 = sma(close, 20)
    sma50 = sma(close, 50)
    sma200 = sma(close, 200) if len(close) >= 200 else pd.Series([np.nan] * len(close), index=close.index)

    # ---- Momentum ----
    rsi14 = rsi(close, 14)
    stoch_rsi14 = stochastic_rsi(close, 14)
    macd_line, signal_line, hist = macd(close)
    roc12 = roc(close, 12)
    cci20 = cci(history, 20)
    williams14 = williams_r(history, 14)
    adx14, plus_di14, minus_di14 = adx(history, 14)

    # ---- Volatility ----
    atr14 = atr(history, 14)
    bb_upper, bb_mid, bb_lower = bollinger_bands(close)
    kc_upper, kc_mid, kc_lower = keltner_channel(history, 20)
    hist_vol20 = historical_volatility(close, 20)

    # ---- Volume-based (only if volume data exists) ----
    obv_series = obv(history) if has_volume else None
    vwap20 = rolling_vwap(history, 20) if has_volume else None
    mfi14 = money_flow_index(history, 14) if has_volume else None
    cmf20 = chaikin_money_flow(history, 20) if has_volume else None

    last_close = float(close.iloc[-1])
    vol_avg_20 = history["Volume"].rolling(20).mean().iloc[-1] if has_volume else np.nan
    last_vol = history["Volume"].iloc[-1] if has_volume else np.nan

    lookback = min(len(close), 252)
    high_52w = close.iloc[-lookback:].max()
    low_52w = close.iloc[-lookback:].min()

    e200_last = ema200.iloc[-1]
    bb_width_pct = ((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1] * 100) if bb_mid.iloc[-1] else None

    trend = _read_trend(last_close, ema20.iloc[-1], ema50.iloc[-1],
                         e200_last if not np.isnan(e200_last) else None)
    structure = read_market_structure(history)
    adx_val = float(adx14.iloc[-1]) if not np.isnan(adx14.iloc[-1]) else None

    result = {
        # ---- Phase-0 keys (unchanged, scoring.py depends on these) ----
        "last_close": round(last_close, 2),
        "ema20": round(float(ema20.iloc[-1]), 2),
        "ema50": round(float(ema50.iloc[-1]), 2),
        "ema100": round(float(ema100.iloc[-1]), 2),
        "ema200": round(float(e200_last), 2) if not np.isnan(e200_last) else None,
        "rsi14": round(float(rsi14.iloc[-1]), 2) if not np.isnan(rsi14.iloc[-1]) else None,
        "macd_line": round(float(macd_line.iloc[-1]), 3),
        "macd_signal": round(float(signal_line.iloc[-1]), 3),
        "macd_histogram": round(float(hist.iloc[-1]), 3),
        "atr14": round(float(atr14.iloc[-1]), 2) if not np.isnan(atr14.iloc[-1]) else None,
        "bb_upper": round(float(bb_upper.iloc[-1]), 2),
        "bb_mid": round(float(bb_mid.iloc[-1]), 2),
        "bb_lower": round(float(bb_lower.iloc[-1]), 2),
        "volume_vs_20d_avg_pct": round(float((last_vol / vol_avg_20 - 1) * 100), 1) if has_volume and vol_avg_20 else None,
        "high_52w": round(float(high_52w), 2),
        "low_52w": round(float(low_52w), 2),
        "pct_from_52w_high": round(float((last_close / high_52w - 1) * 100), 2),
        "pct_from_52w_low": round(float((last_close / low_52w - 1) * 100), 2),
        "trend": trend,

        # ---- Phase-1 additions: moving averages ----
        "ema9": round(float(ema9.iloc[-1]), 2),
        "sma20": round(float(sma20.iloc[-1]), 2) if not np.isnan(sma20.iloc[-1]) else None,
        "sma50": round(float(sma50.iloc[-1]), 2) if not np.isnan(sma50.iloc[-1]) else None,
        "sma200": round(float(sma200.iloc[-1]), 2) if not np.isnan(sma200.iloc[-1]) else None,
        "golden_cross": bool(ema50.iloc[-1] > e200_last) if not np.isnan(e200_last) else None,
        "death_cross": bool(ema50.iloc[-1] < e200_last) if not np.isnan(e200_last) else None,
        "pct_from_ema200": round(float((last_close / e200_last - 1) * 100), 2) if not np.isnan(e200_last) else None,

        # ---- Phase-1: momentum ----
        "stoch_rsi14": round(float(stoch_rsi14.iloc[-1]), 2) if not np.isnan(stoch_rsi14.iloc[-1]) else None,
        "roc12": round(float(roc12.iloc[-1]), 2) if not np.isnan(roc12.iloc[-1]) else None,
        "cci20": round(float(cci20.iloc[-1]), 2) if not np.isnan(cci20.iloc[-1]) else None,
        "williams_r14": round(float(williams14.iloc[-1]), 2) if not np.isnan(williams14.iloc[-1]) else None,
        "adx14": round(adx_val, 2) if adx_val is not None else None,
        "plus_di14": round(float(plus_di14.iloc[-1]), 2) if not np.isnan(plus_di14.iloc[-1]) else None,
        "minus_di14": round(float(minus_di14.iloc[-1]), 2) if not np.isnan(minus_di14.iloc[-1]) else None,
        "trend_strength": _classify_adx(adx_val),

        # ---- Phase-1: volatility ----
        "bb_width_pct": round(float(bb_width_pct), 2) if bb_width_pct is not None else None,
        "atr_pct": round(float(atr14.iloc[-1] / last_close * 100), 2) if not np.isnan(atr14.iloc[-1]) else None,
        "historical_volatility_20d": round(float(hist_vol20.iloc[-1]), 2) if not np.isnan(hist_vol20.iloc[-1]) else None,
        "keltner_upper": round(float(kc_upper.iloc[-1]), 2) if not np.isnan(kc_upper.iloc[-1]) else None,
        "keltner_mid": round(float(kc_mid.iloc[-1]), 2) if not np.isnan(kc_mid.iloc[-1]) else None,
        "keltner_lower": round(float(kc_lower.iloc[-1]), 2) if not np.isnan(kc_lower.iloc[-1]) else None,

        # ---- Phase-1: volume ----
        "obv_trend": _obv_trend(obv_series) if obv_series is not None else None,
        "vwap20": round(float(vwap20.iloc[-1]), 2) if vwap20 is not None and not np.isnan(vwap20.iloc[-1]) else None,
        "mfi14": round(float(mfi14.iloc[-1]), 2) if mfi14 is not None and not np.isnan(mfi14.iloc[-1]) else None,
        "cmf20": round(float(cmf20.iloc[-1]), 3) if cmf20 is not None and not np.isnan(cmf20.iloc[-1]) else None,
        "has_volume_data": has_volume,

        # ---- Phase-1: market structure ----
        "market_structure": structure["structure"],
        "market_structure_detail": structure["detail"],
    }

    result["support_resistance"] = compute_support_resistance(history)
    result["candle_patterns"] = []  # populated by analyzer.patterns, kept here for a stable schema
    return result


def _classify_adx(adx_val) -> str:
    if adx_val is None:
        return "Unknown"
    if adx_val < 20:
        return "Weak / No Trend"
    if adx_val < 40:
        return "Moderate Trend"
    if adx_val < 60:
        return "Strong Trend"
    return "Very Strong Trend"


def _obv_trend(obv_series: pd.Series, window: int = 20) -> str:
    if obv_series is None or len(obv_series) < window + 1:
        return "Unknown"
    recent = obv_series.iloc[-window:]
    slope = recent.iloc[-1] - recent.iloc[0]
    return "Rising (Accumulation)" if slope > 0 else "Falling (Distribution)" if slope < 0 else "Flat"


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


# ---------------------------------------------------------------------------
# Support / Resistance / Pivot points / Fibonacci
# ---------------------------------------------------------------------------

def compute_support_resistance(history: pd.DataFrame, lookback: int = 60) -> dict:
    """
    Pivot points (classic formula, using the most recent completed bar),
    plus simple support/resistance from recent swing highs/lows, plus
    Fibonacci retracement levels over the lookback window.
    """
    recent = history.iloc[-lookback:] if len(history) >= lookback else history
    last = history.iloc[-1]

    pivot = (last["High"] + last["Low"] + last["Close"]) / 3
    r1 = 2 * pivot - last["Low"]
    s1 = 2 * pivot - last["High"]
    r2 = pivot + (last["High"] - last["Low"])
    s2 = pivot - (last["High"] - last["Low"])
    r3 = last["High"] + 2 * (pivot - last["Low"])
    s3 = last["Low"] - 2 * (last["High"] - pivot)

    swing_high = recent["High"].max()
    swing_low = recent["Low"].min()
    diff = swing_high - swing_low

    fib_levels = {
        "0.0%": round(float(swing_high), 2),
        "23.6%": round(float(swing_high - 0.236 * diff), 2),
        "38.2%": round(float(swing_high - 0.382 * diff), 2),
        "50.0%": round(float(swing_high - 0.5 * diff), 2),
        "61.8%": round(float(swing_high - 0.618 * diff), 2),
        "100.0%": round(float(swing_low), 2),
    }

    return {
        "pivot": round(float(pivot), 2),
        "resistance_1": round(float(r1), 2),
        "resistance_2": round(float(r2), 2),
        "resistance_3": round(float(r3), 2),
        "support_1": round(float(s1), 2),
        "support_2": round(float(s2), 2),
        "support_3": round(float(s3), 2),
        "swing_high": round(float(swing_high), 2),
        "swing_low": round(float(swing_low), 2),
        "fibonacci_levels": fib_levels,
    }


# ---------------------------------------------------------------------------
# Mutual fund technicals (unchanged from Phase 0)
# ---------------------------------------------------------------------------

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
