"""
ai_summary.py
--------------
Generates the "AI Decision" content: rating card, natural-language
summary paragraph, bull/bear/base case, and a bullish/neutral/bearish
probability read.

IMPORTANT HONESTY NOTE: this is template-driven natural language
generation from the real scores/reasons computed elsewhere - NOT a
call to an actual language model. It reads like AI-generated prose,
but every sentence is built directly from a specific number that was
actually computed, never invented. The UI should be upfront about this
distinction (see the "engine" field in the returned dict) so users
don't mistake it for something it isn't.

We deliberately do NOT pad "why buy" / "why avoid" lists with filler
reasons just to hit a round number like 10 - only genuine, data-backed
reasons are included. A shorter, honest list beats a padded fake one.
"""


def _signal_to_stars(overall_score: float) -> str:
    if overall_score >= 80:
        return "★★★★★"
    if overall_score >= 65:
        return "★★★★☆"
    if overall_score >= 50:
        return "★★★☆☆"
    if overall_score >= 35:
        return "★★☆☆☆"
    return "★☆☆☆☆"


def _expected_horizon(signal: str) -> str:
    bucket = {
        "Strong Buy": "6-12 Months",
        "Buy": "6-12 Months",
        "Accumulate": "3-6 Months",
        "Hold": "Monitor, no fixed horizon",
        "Reduce": "Review within 1-3 Months",
        "Sell": "Exit / Immediate Review",
        "Strong Sell": "Exit / Immediate Review",
    }
    return bucket.get(signal, "Not Determined")


def _rough_expected_return(overall_score: float, hist_vol: float = None) -> str:
    """
    A deliberately rough heuristic, not a forecast: maps score above/below
    neutral (50) to a plausible directional return band. This is NOT a
    statistical prediction - it's a translation of "how bullish/bearish
    is the score" into a return range a human can intuit. Labelled as
    such in the UI.
    """
    delta = overall_score - 50
    base = delta * 0.4  # e.g. score of 80 -> +12%, score of 20 -> -12%
    spread = 6 if hist_vol is None else min(15, max(4, hist_vol / 4))
    low, high = round(base - spread / 2, 1), round(base + spread / 2, 1)
    return f"{low:+.1f}% to {high:+.1f}%"


def build_stock_ai_summary(fundamentals: dict, technicals: dict, signal: dict, risk: dict) -> dict:
    overall = signal["overall_score"]
    sig_text = signal["signal"]
    company = fundamentals.get("company_name") or "This stock"

    # ---- Rating card ----
    rating_card = {
        "stars": _signal_to_stars(overall),
        "recommendation": sig_text,
        "confidence_pct": signal.get("confidence_pct"),
        "overall_risk": risk.get("overall_risk", "Unknown"),
        "expected_return_range": _rough_expected_return(overall, technicals.get("historical_volatility_20d")),
        "time_horizon": _expected_horizon(sig_text),
    }

    # ---- Why buy / why avoid, drawn only from real computed reasons ----
    all_reasons = list(signal.get("fundamental_reasons", [])) + list(signal.get("technical_reasons", []))
    why_buy = [r for r, p in all_reasons if p > 0]
    why_avoid = [r for r, p in all_reasons if p < 0]

    # ---- Natural-language paragraph ----
    trend = technicals.get("trend", "an unclear trend") if technicals and not technicals.get("error") else "an unclear trend"
    rsi14 = technicals.get("rsi14")
    rsi_note = ""
    if rsi14 is not None:
        if rsi14 > 70:
            rsi_note = " Momentum indicators suggest the stock is short-term overbought, raising pullback risk."
        elif rsi14 < 30:
            rsi_note = " Momentum indicators suggest the stock is short-term oversold, which can precede a bounce."

    fund_clause = ""
    rev_growth = fundamentals.get("revenue_growth")
    roe = fundamentals.get("roe")
    if rev_growth is not None and roe is not None:
        if rev_growth > 0.1 and roe > 0.15:
            fund_clause = " Fundamentally, the business shows solid revenue growth and healthy returns on equity."
        elif rev_growth < 0 or (roe is not None and roe < 0.05):
            fund_clause = " Fundamentally, growth or capital efficiency metrics look weaker than typical benchmarks."

    valuation_clause = ""
    pe = fundamentals.get("pe_trailing")
    if pe is not None:
        if pe > 40:
            valuation_clause = " Valuation is on the expensive side relative to typical market multiples."
        elif pe < 15:
            valuation_clause = " Valuation looks inexpensive relative to typical market multiples."

    action_clause = {
        "Strong Buy": "Long-term investors may find this an attractive entry, though position sizing should account for the risks below.",
        "Buy": "Accumulating gradually rather than all at once can help manage entry-price risk.",
        "Accumulate": "A phased entry (e.g. via SIP-style staggered buying) suits the current picture better than a lump-sum entry.",
        "Hold": "Existing holders may stay invested while watching for a change in the factors below; new buyers may wait for a clearer setup.",
        "Reduce": "Trimming exposure and reassessing thesis quality is worth considering.",
        "Sell": "The current picture argues for reducing or exiting existing positions.",
        "Strong Sell": "Multiple weak signals are aligned - this is not a favorable setup for new capital.",
    }.get(sig_text, "")

    summary = (
        f"{company} is currently in {trend.lower()}.{fund_clause}{valuation_clause}{rsi_note} "
        f"Combining fundamentals and technicals, the overall signal is {sig_text} "
        f"with {signal.get('confidence_pct')}% confidence. {action_clause}"
    ).strip()

    # ---- Bull / Bear / Base case ----
    bull_case = why_buy[:5] if why_buy else ["No strong bullish factors identified in current data."]
    bear_case = why_avoid[:5] if why_avoid else ["No strong bearish factors identified in current data."]
    base_case = [
        f"Overall score of {overall}/100 reflects a blend of {signal.get('technical_score')}/100 technical "
        f"and {signal.get('fundamental_score')}/100 fundamental scores.",
        f"Confidence in this read is {signal.get('confidence_pct')}%, based on how much the technical and "
        f"fundamental pictures agree with each other.",
    ]

    # ---- Probability matrix (derived from score distance from neutral, not a statistical model) ----
    probability = _probability_matrix(overall)

    # ---- Invalidation criteria (mechanical, derived from the actual trend/levels in play) ----
    invalidation = _invalidation_criteria(sig_text, technicals)

    return {
        "engine": "rule-based (not a live LLM call - generated from computed scores)",
        "rating_card": rating_card,
        "summary": summary,
        "why_buy": why_buy,
        "why_avoid": why_avoid,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "base_case": base_case,
        "probability": probability,
        "invalidation_criteria": invalidation,
    }


def _probability_matrix(overall_score: float) -> dict:
    """
    Converts the overall score into a bullish/neutral/bearish probability
    split. This is a deterministic transform of the score, not a
    backtested statistical estimate - framed as such in the UI.
    """
    delta = overall_score - 50
    bullish = max(5, min(85, 50 + delta * 0.9))
    bearish = max(5, min(85, 50 - delta * 0.9))
    neutral = max(5, 100 - bullish - bearish)
    total = bullish + neutral + bearish
    return {
        "bullish_pct": round(bullish / total * 100, 1),
        "neutral_pct": round(neutral / total * 100, 1),
        "bearish_pct": round(bearish / total * 100, 1),
    }


def _invalidation_criteria(signal_text: str, technicals: dict) -> list:
    if not technicals or technicals.get("error"):
        return ["Insufficient technical data to define precise invalidation levels."]

    ema50 = technicals.get("ema50")
    ema200 = technicals.get("ema200")
    support = technicals.get("support_resistance", {}).get("support_1")
    resistance = technicals.get("support_resistance", {}).get("resistance_1")

    bullish_signals = ("Strong Buy", "Buy", "Accumulate")
    criteria = []

    if signal_text in bullish_signals:
        if ema50 is not None:
            criteria.append(f"A sustained close below the 50-EMA ({ema50}) would weaken this bullish thesis.")
        if support is not None:
            criteria.append(f"A break below the nearest support ({support}) would invalidate the current setup.")
        if ema200 is not None:
            criteria.append(f"Price falling below the 200-EMA ({ema200}) would signal a structural trend change.")
    else:
        if ema50 is not None:
            criteria.append(f"A sustained close above the 50-EMA ({ema50}) would weaken this bearish/neutral thesis.")
        if resistance is not None:
            criteria.append(f"A break above the nearest resistance ({resistance}) would invalidate the current setup.")

    if not criteria:
        criteria.append("No specific technical invalidation levels could be computed from available data.")
    return criteria
