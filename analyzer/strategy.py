"""
strategy.py
------------
Builds the four horizon-specific "Strategy" views (Intraday, Short-Term,
Mid-Term, Long-Term). None of this pulls new data - it reorganizes and
re-weights the technicals/fundamentals/signal/risk already computed
elsewhere into horizon-appropriate entry/stop/target levels and framing,
as promised in the Phase 2 scope.

HONESTY NOTE ON INTRADAY: this app works from *daily* OHLCV bars, not
real-time tick or minute data. True intraday analysis (1min/5min/15min
charts, live opening-range breakout, real-time VWAP) needs a real-time
market data feed, which this project doesn't have. The "Intraday" view
below is honestly framed as a *daily-bar-derived approximation*
(expected range from ATR, pivot levels) rather than faking real
intraday granularity.
"""


def build_intraday_view(technicals: dict) -> dict:
    if not technicals or technicals.get("error"):
        return {"available": False, "note": "Insufficient price data."}

    last_close = technicals.get("last_close")
    atr14 = technicals.get("atr14")
    sr = technicals.get("support_resistance", {})
    rsi14 = technicals.get("rsi14")

    expected_range = None
    if last_close is not None and atr14 is not None:
        expected_range = {
            "low": round(last_close - atr14 * 0.5, 2),
            "high": round(last_close + atr14 * 0.5, 2),
        }

    bias = "Neutral"
    if rsi14 is not None:
        if rsi14 > 55 and technicals.get("trend") in ("Uptrend", "Strong Uptrend"):
            bias = "Bullish"
        elif rsi14 < 45 and technicals.get("trend") in ("Downtrend", "Strong Downtrend"):
            bias = "Bearish"

    return {
        "available": True,
        "data_limitation": (
            "Derived from the daily bar, not real-time intraday data. "
            "True 1/5/15-minute analysis needs a live market data feed this app doesn't have."
        ),
        "bias": bias,
        "expected_range_today": expected_range,
        "pivot": sr.get("pivot"),
        "resistance_1": sr.get("resistance_1"),
        "support_1": sr.get("support_1"),
    }


def build_short_term_view(technicals: dict, signal: dict) -> dict:
    """0-30 day swing-trade framing."""
    if not technicals or technicals.get("error"):
        return {"available": False, "note": "Insufficient price data."}

    last_close = technicals.get("last_close")
    atr14 = technicals.get("atr14")
    sr = technicals.get("support_resistance", {})
    overall = signal.get("overall_score", 50)
    bullish = overall >= 55

    if last_close is None or atr14 is None:
        return {"available": False, "note": "Insufficient volatility data to size a setup."}

    if bullish:
        ideal_entry = round(last_close, 2)
        aggressive_entry = round(last_close * 1.005, 2)
        confirmation_entry = sr.get("resistance_1")
        stop_loss = round(last_close - atr14 * 1.5, 2)
        target_1 = round(last_close + atr14 * 1.5, 2)
        target_2 = round(last_close + atr14 * 2.5, 2)
        atr_target_3 = round(last_close + atr14 * 3.5, 2)
        pivot_target_3 = sr.get("resistance_2")
        # Targets must increase (T1 < T2 < T3) - a near-in pivot level can't
        # stand in for T3 if it's tighter than T2, so take whichever is further out.
        target_3 = max(atr_target_3, pivot_target_3) if pivot_target_3 else atr_target_3
    else:
        ideal_entry = round(last_close, 2)
        aggressive_entry = round(last_close * 0.995, 2)
        confirmation_entry = sr.get("support_1")
        stop_loss = round(last_close + atr14 * 1.5, 2)
        target_1 = round(last_close - atr14 * 1.5, 2)
        target_2 = round(last_close - atr14 * 2.5, 2)
        atr_target_3 = round(last_close - atr14 * 3.5, 2)
        pivot_target_3 = sr.get("support_2")
        target_3 = min(atr_target_3, pivot_target_3) if pivot_target_3 else atr_target_3

    risk = abs(ideal_entry - stop_loss)
    reward = abs(target_2 - ideal_entry)
    rr_ratio = round(reward / risk, 2) if risk > 0 else None

    return {
        "available": True,
        "direction": "Long" if bullish else "Short / Avoid New Longs",
        "ideal_entry": ideal_entry,
        "aggressive_entry": aggressive_entry,
        "confirmation_entry": confirmation_entry,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "target_3": target_3,
        "risk_reward_ratio": rr_ratio,
        "holding_period": "Up to ~30 days, reassess if targets/stop not hit",
        "swing_probability_pct": round(min(85, max(15, overall)), 1),
    }


def build_mid_term_view(fundamentals: dict, technicals: dict, signal: dict, risk: dict) -> dict:
    """1-6 month framing - trend + fundamentals blend, portfolio-sizing guidance."""
    overall = signal.get("overall_score", 50)
    trend = technicals.get("trend") if technicals and not technicals.get("error") else "Unknown"
    pe = fundamentals.get("pe_trailing")

    valuation_view = "Unknown"
    if pe is not None:
        if pe < 20:
            valuation_view = "Reasonable to Inexpensive"
        elif pe < 40:
            valuation_view = "Moderately Rich"
        else:
            valuation_view = "Expensive"

    overall_risk = risk.get("overall_risk", "Unknown") if risk else "Unknown"
    allocation_guidance = _allocation_guidance(overall, overall_risk)

    expected_return = round((overall - 50) * 0.5, 1)  # rough directional heuristic, see ai_summary for full caveat

    return {
        "available": True,
        "trend_read": trend,
        "valuation_view": valuation_view,
        "overall_score": overall,
        "expected_return_pct_6m_heuristic": expected_return,
        "portfolio_allocation_guidance": allocation_guidance,
    }


def _allocation_guidance(overall_score: float, overall_risk: str) -> str:
    if overall_risk in ("Very High", "High"):
        return "Small position size (well under typical single-stock allocation) given elevated risk, regardless of score."
    if overall_score >= 70:
        return "Could warrant a standard-to-slightly-above-average position size for a single stock, subject to your own diversification rules."
    if overall_score >= 50:
        return "Standard or below-standard position size - the picture is mixed enough not to overweight."
    return "Avoid adding new capital; existing holders may size down."


def build_long_term_view(fundamentals: dict, technicals: dict, signal: dict) -> dict:
    """6+ month framing - business quality lens, simplified intrinsic value, growth extrapolation."""
    roe = fundamentals.get("roe")
    profit_margin = fundamentals.get("profit_margin")
    revenue_cagr = fundamentals.get("revenue_cagr")
    pe = fundamentals.get("pe_trailing")
    eps = None
    book_value = fundamentals.get("book_value_per_share")

    business_quality = "Unknown"
    if roe is not None and profit_margin is not None:
        if roe > 0.18 and profit_margin > 0.12:
            business_quality = "High Quality"
        elif roe > 0.10 and profit_margin > 0.05:
            business_quality = "Moderate Quality"
        else:
            business_quality = "Below Average Quality"

    intrinsic_value_note = (
        "Not computed: needs trailing EPS and a discount-rate assumption for a "
        "defensible DCF/Graham-style estimate, which current data sources don't "
        "reliably provide for Indian mid/small-caps. Showing PE-based context instead."
    )
    intrinsic_value_estimate = None
    if book_value is not None and roe is not None and roe > 0:
        # Simplified Graham-style sanity check, not a real DCF - explicitly caveated
        intrinsic_value_estimate = round(book_value * (1 + roe * 5), 2)
        intrinsic_value_note = (
            "Simplified heuristic (book value grown by 5 years of current ROE) - "
            "a sanity-check estimate, NOT a discounted cash flow valuation. "
            "Treat as a rough anchor, not a price target."
        )

    projections = {}
    if revenue_cagr is not None:
        for years in (3, 5, 10):
            projections[f"{years}y_revenue_projection_multiple"] = round((1 + revenue_cagr / 100) ** years, 2)
        projections["basis"] = f"Extrapolating the observed {revenue_cagr}% revenue CAGR forward - a mechanical extrapolation, not a forecast. Real growth rates rarely stay constant for a decade."
    else:
        projections["basis"] = "Insufficient multi-year financial history to extrapolate growth."

    overall = signal.get("overall_score", 50)
    wealth_creation_potential = (
        "High" if overall >= 70 and business_quality == "High Quality" else
        "Moderate" if overall >= 50 else
        "Low / Uncertain"
    )

    return {
        "available": True,
        "business_quality": business_quality,
        "intrinsic_value_estimate": intrinsic_value_estimate,
        "intrinsic_value_note": intrinsic_value_note,
        "growth_projection": projections,
        "wealth_creation_potential": wealth_creation_potential,
    }


def build_all_strategies(fundamentals: dict, technicals: dict, signal: dict, risk: dict) -> dict:
    return {
        "intraday": build_intraday_view(technicals),
        "short_term": build_short_term_view(technicals, signal),
        "mid_term": build_mid_term_view(fundamentals, technicals, signal, risk),
        "long_term": build_long_term_view(fundamentals, technicals, signal),
    }
