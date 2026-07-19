"""
risk.py
--------
Assigns Low / Medium / High / Very High risk labels across several
categories, using the same fundamentals + technicals data already
gathered elsewhere - no new data source needed.

Each category returns a label plus the specific reasons behind it,
following the same "explainable, not a black box" principle as
scoring.py.

LIMITATION: several categories the original spec asked for
(Governance Risk, Regulatory Risk, Macro/Global Risk, Black Swan Risk)
genuinely need qualitative data we don't have a feed for yet (news,
litigation records, macro forecasts). Those are returned as
"Unknown / Not Assessed" rather than guessed, per the "never fabricate
values" rule - flagged clearly so the UI can show them honestly
instead of inventing a number.
"""


def _label_from_points(points: int) -> str:
    if points >= 3:
        return "Very High"
    if points >= 2:
        return "High"
    if points >= 1:
        return "Medium"
    return "Low"


def assess_stock_risk(fundamentals: dict, technicals: dict) -> dict:
    categories = {}

    # ---- Financial / Debt Risk ----
    pts, reasons = 0, []
    d2e = fundamentals.get("debt_to_equity")
    current_ratio = fundamentals.get("current_ratio")
    interest_related = fundamentals.get("profit_margin")
    if d2e is not None:
        if d2e > 150:
            pts += 2; reasons.append(f"Debt/Equity of {d2e:.0f}% is high leverage")
        elif d2e > 80:
            pts += 1; reasons.append(f"Debt/Equity of {d2e:.0f}% is moderately elevated")
    if current_ratio is not None and current_ratio < 1:
        pts += 1; reasons.append(f"Current ratio of {current_ratio:.2f} suggests short-term liquidity strain")
    if not reasons:
        reasons.append("No significant debt or liquidity red flags in available data")
    categories["financial_risk"] = {"label": _label_from_points(pts), "reasons": reasons}

    # ---- Valuation Risk ----
    pts, reasons = 0, []
    pe = fundamentals.get("pe_trailing")
    peg = fundamentals.get("peg_ratio")
    if pe is not None:
        if pe > 60:
            pts += 2; reasons.append(f"PE of {pe:.1f} is very rich - priced for flawless execution")
        elif pe > 35:
            pts += 1; reasons.append(f"PE of {pe:.1f} is elevated vs typical market average")
    if peg is not None and peg > 3:
        pts += 1; reasons.append(f"PEG of {peg:.1f} suggests growth doesn't justify the price paid")
    if not reasons:
        reasons.append("Valuation appears reasonable relative to available benchmarks")
    categories["valuation_risk"] = {"label": _label_from_points(pts), "reasons": reasons}

    # ---- Business / Profitability Risk ----
    pts, reasons = 0, []
    margin = fundamentals.get("profit_margin")
    rev_growth = fundamentals.get("revenue_growth")
    roe = fundamentals.get("roe")
    if margin is not None and margin < 0:
        pts += 2; reasons.append("Company is currently loss-making at the net level")
    if rev_growth is not None and rev_growth < -0.05:
        pts += 1; reasons.append(f"Revenue declining ({rev_growth*100:.1f}%) year-over-year")
    if roe is not None and roe < 0.05:
        pts += 1; reasons.append(f"ROE of {roe*100:.1f}% indicates weak capital efficiency")
    if not reasons:
        reasons.append("Core profitability metrics look healthy in available data")
    categories["business_risk"] = {"label": _label_from_points(pts), "reasons": reasons}

    # ---- Volatility / Technical Risk ----
    pts, reasons = 0, []
    if technicals and not technicals.get("error"):
        hist_vol = technicals.get("historical_volatility_20d")
        atr_pct = technicals.get("atr_pct")
        if hist_vol is not None:
            if hist_vol > 50:
                pts += 2; reasons.append(f"Annualized volatility of {hist_vol:.0f}% is very high")
            elif hist_vol > 30:
                pts += 1; reasons.append(f"Annualized volatility of {hist_vol:.0f}% is elevated")
        if atr_pct is not None and atr_pct > 4:
            pts += 1; reasons.append(f"Daily ATR of {atr_pct:.1f}% of price indicates large daily swings")
    if not reasons:
        reasons.append("Price volatility is within typical ranges")
    categories["volatility_risk"] = {"label": _label_from_points(pts), "reasons": reasons}

    # ---- Liquidity Risk (market cap as rough proxy - true liquidity needs traded-volume-in-currency data) ----
    pts, reasons = 0, []
    mcap = fundamentals.get("market_cap")
    if mcap is not None:
        if mcap < 5e9:  # < ~500 Cr
            pts += 2; reasons.append("Small market cap - wider bid-ask spreads and harder to exit in size are typical")
        elif mcap < 2e10:  # < ~2000 Cr
            pts += 1; reasons.append("Mid-sized market cap - moderate liquidity considerations apply")
    if not reasons:
        reasons.append("Market cap suggests reasonable trading liquidity")
    categories["liquidity_risk"] = {"label": _label_from_points(pts), "reasons": reasons}

    # ---- Categories we genuinely can't assess without additional data feeds ----
    for key, why in [
        ("governance_risk", "Requires litigation records, related-party transaction filings, and audit history not available from current data sources."),
        ("regulatory_risk", "Requires sector-specific regulatory tracking not available from current data sources."),
        ("macro_global_risk", "Requires macroeconomic forecasting and cross-market correlation data not available from current data sources."),
    ]:
        categories[key] = {"label": "Not Assessed", "reasons": [why]}

    overall = _overall_risk(categories)

    return {"categories": categories, "overall_risk": overall}


def _overall_risk(categories: dict) -> str:
    assessed = [c["label"] for c in categories.values() if c["label"] != "Not Assessed"]
    if not assessed:
        return "Unknown"
    order = {"Low": 0, "Medium": 1, "High": 2, "Very High": 3}
    worst = max(assessed, key=lambda x: order[x])
    avg_score = sum(order[l] for l in assessed) / len(assessed)
    # Blend: mostly driven by average, but a single "Very High" category pulls it up
    if worst == "Very High" and avg_score >= 1.5:
        return "Very High"
    if avg_score >= 2:
        return "Very High"
    if avg_score >= 1.2:
        return "High"
    if avg_score >= 0.5:
        return "Medium"
    return "Low"
