"""
scoring.py
-----------
The decision-making core. Converts raw technical + fundamental data
into 0-100 sub-scores, then a weighted overall score, then a final
Strong Buy / Buy / Accumulate / Hold / Reduce / Sell / Strong Sell
signal - along with the specific reasons behind it.

DESIGN PRINCIPLE: every score must be explainable. Each scoring function
returns not just a number but a list of (reason, points) tuples so the
report layer can show exactly why a stock/fund scored the way it did.
This avoids the "black box" trap - the whole point of this tool is
to teach reasoning, not just spit out a verdict.

These are RULE-BASED heuristics, not a trained ML model. They encode
sensible textbook thresholds (e.g. RSI > 70 = overbought) but you
should tune the weights/thresholds based on backtesting before trusting
this with real money decisions.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class ScoreResult:
    score: float                          # 0-100
    reasons: List[Tuple[str, float]] = field(default_factory=list)  # (reason, points contributed)

    def add(self, reason: str, points: float):
        self.reasons.append((reason, points))


def _clip(x, lo=0, hi=100):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# STOCK SCORING
# ---------------------------------------------------------------------------

def score_stock_technicals(tech: dict) -> ScoreResult:
    result = ScoreResult(score=50)  # start neutral
    if tech.get("error"):
        result.add("Insufficient data - defaulting to neutral", 0)
        return result

    pts = 0

    # Trend (moving average stack) - biggest weight, trend is king
    trend = tech.get("trend")
    if trend == "Strong Uptrend":
        pts += 25; result.add("Price above all key EMAs in bullish stack (Strong Uptrend)", 25)
    elif trend == "Uptrend":
        pts += 12; result.add("Price above short/medium-term EMAs (Uptrend)", 12)
    elif trend == "Strong Downtrend":
        pts -= 25; result.add("Price below all key EMAs in bearish stack (Strong Downtrend)", -25)
    elif trend == "Downtrend":
        pts -= 12; result.add("Price below short/medium-term EMAs (Downtrend)", -12)
    else:
        result.add("Sideways/mixed trend - no clear directional edge", 0)

    # RSI - momentum + overbought/oversold
    rsi14 = tech.get("rsi14")
    if rsi14 is not None:
        if rsi14 > 70:
            pts -= 8; result.add(f"RSI at {rsi14} - overbought, pullback risk", -8)
        elif rsi14 < 30:
            pts += 8; result.add(f"RSI at {rsi14} - oversold, potential bounce zone", 8)
        elif 45 <= rsi14 <= 60:
            pts += 5; result.add(f"RSI at {rsi14} - healthy momentum zone", 5)

    # MACD
    if tech.get("macd_histogram") is not None:
        if tech["macd_histogram"] > 0 and tech.get("macd_line", 0) > tech.get("macd_signal", 0):
            pts += 8; result.add("MACD line above signal line - bullish momentum", 8)
        elif tech["macd_histogram"] < 0 and tech.get("macd_line", 0) < tech.get("macd_signal", 0):
            pts -= 8; result.add("MACD line below signal line - bearish momentum", -8)

    # Distance from 52w high/low
    pct_from_high = tech.get("pct_from_52w_high")
    pct_from_low = tech.get("pct_from_52w_low")
    if pct_from_high is not None and pct_from_high > -5:
        pts += 6; result.add("Trading near 52-week high - strength/breakout zone", 6)
    if pct_from_low is not None and pct_from_low < 10:
        pts -= 6; result.add("Trading near 52-week low - weakness, caution warranted", -6)

    # Volume confirmation
    vol_diff = tech.get("volume_vs_20d_avg_pct")
    if vol_diff is not None and vol_diff > 50 and trend in ("Uptrend", "Strong Uptrend"):
        pts += 6; result.add("Volume surge confirming uptrend - institutional interest likely", 6)

    result.score = _clip(50 + pts)
    return result


def score_stock_fundamentals(fund: dict) -> ScoreResult:
    result = ScoreResult(score=50)
    pts = 0
    have_data = False

    pe = fund.get("pe_trailing")
    if pe is not None:
        have_data = True
        if 0 < pe < 15:
            pts += 12; result.add(f"PE of {pe:.1f} - inexpensive vs typical market average", 12)
        elif 15 <= pe <= 30:
            pts += 4; result.add(f"PE of {pe:.1f} - reasonable valuation range", 4)
        elif pe > 40:
            pts -= 10; result.add(f"PE of {pe:.1f} - richly valued, priced for high growth", -10)

    roe = fund.get("roe")
    if roe is not None:
        have_data = True
        if roe > 0.20:
            pts += 12; result.add(f"ROE of {roe*100:.1f}% - excellent capital efficiency", 12)
        elif roe > 0.12:
            pts += 6; result.add(f"ROE of {roe*100:.1f}% - decent capital efficiency", 6)
        elif roe < 0.05:
            pts -= 8; result.add(f"ROE of {roe*100:.1f}% - weak returns on shareholder capital", -8)

    d2e = fund.get("debt_to_equity")
    if d2e is not None:
        have_data = True
        if d2e < 30:
            pts += 8; result.add(f"Debt/Equity of {d2e:.0f}% - low leverage, financially conservative", 8)
        elif d2e > 150:
            pts -= 10; result.add(f"Debt/Equity of {d2e:.0f}% - high leverage, elevated financial risk", -10)

    profit_margin = fund.get("profit_margin")
    if profit_margin is not None:
        have_data = True
        if profit_margin > 0.15:
            pts += 8; result.add(f"Net margin of {profit_margin*100:.1f}% - strong profitability", 8)
        elif profit_margin < 0:
            pts -= 15; result.add("Company is currently loss-making at the net level", -15)

    rev_growth = fund.get("revenue_growth")
    if rev_growth is not None:
        have_data = True
        if rev_growth > 0.15:
            pts += 8; result.add(f"Revenue growth of {rev_growth*100:.1f}% - strong topline momentum", 8)
        elif rev_growth < 0:
            pts -= 8; result.add(f"Revenue declining ({rev_growth*100:.1f}%) - shrinking business", -8)

    current_ratio = fund.get("current_ratio")
    if current_ratio is not None:
        have_data = True
        if current_ratio < 1:
            pts -= 6; result.add(f"Current ratio of {current_ratio:.2f} - potential short-term liquidity strain", -6)

    if not have_data:
        result.add("Fundamental data unavailable from data source - score defaulted to neutral", 0)

    result.score = _clip(50 + pts)
    return result


def build_stock_signal(tech_score: ScoreResult, fund_score: ScoreResult,
                        tech_weight: float = 0.45, fund_weight: float = 0.55) -> dict:
    overall = tech_score.score * tech_weight + fund_score.score * fund_weight
    return {
        "technical_score": round(tech_score.score, 1),
        "fundamental_score": round(fund_score.score, 1),
        "overall_score": round(overall, 1),
        "signal": _signal_from_score(overall),
        "confidence_pct": _confidence_from_agreement(tech_score.score, fund_score.score),
        "technical_reasons": tech_score.reasons,
        "fundamental_reasons": fund_score.reasons,
    }


def _signal_from_score(score: float) -> str:
    if score >= 80:
        return "Strong Buy"
    if score >= 68:
        return "Buy"
    if score >= 58:
        return "Accumulate"
    if score >= 45:
        return "Hold"
    if score >= 32:
        return "Reduce"
    if score >= 20:
        return "Sell"
    return "Strong Sell"


def _confidence_from_agreement(score_a: float, score_b: float) -> float:
    """
    When technical and fundamental scores agree (both bullish or both
    bearish), confidence is higher. When they conflict (e.g. great
    fundamentals but breaking down technically), confidence drops -
    that's a genuinely harder call and the report should say so.
    """
    diff = abs(score_a - score_b)
    base_confidence = 90 - diff  # bigger disagreement -> lower confidence
    return round(_clip(base_confidence, 40, 90), 1)


# ---------------------------------------------------------------------------
# MUTUAL FUND SCORING
# ---------------------------------------------------------------------------

def score_fund(tech: dict, fundamentals: dict) -> dict:
    result = ScoreResult(score=50)
    pts = 0

    cagr3 = tech.get("cagr_3y")
    cagr5 = tech.get("cagr_5y")
    cagr1 = tech.get("cagr_1y")

    if cagr5 is not None:
        if cagr5 > 15:
            pts += 15; result.add(f"5-year CAGR of {cagr5}% - strong long-term compounding", 15)
        elif cagr5 < 8:
            pts -= 10; result.add(f"5-year CAGR of {cagr5}% - lagging long-term performance", -10)

    if cagr3 is not None:
        if cagr3 > 15:
            pts += 10; result.add(f"3-year CAGR of {cagr3}% - strong medium-term performance", 10)
        elif cagr3 < 8:
            pts -= 8; result.add(f"3-year CAGR of {cagr3}% - weak medium-term performance", -8)

    # Consistency check: is recent performance falling off vs longer-term?
    if cagr1 is not None and cagr5 is not None:
        if cagr1 < cagr5 - 8:
            pts -= 6; result.add("Recent 1-year return notably weaker than 5-year track record - momentum fading", -6)
        elif cagr1 > cagr5 + 8:
            pts += 4; result.add("Recent 1-year return outpacing long-term average - positive momentum", 4)

    expense_ratio = fundamentals.get("expense_ratio")
    if expense_ratio is not None:
        if expense_ratio < 0.7:
            pts += 6; result.add(f"Low expense ratio of {expense_ratio}% - cost efficient", 6)
        elif expense_ratio > 1.5:
            pts -= 6; result.add(f"High expense ratio of {expense_ratio}% - costs eating into returns", -6)

    aum = fundamentals.get("aum_crore")
    if aum is not None:
        if aum < 500:
            pts -= 4; result.add(f"Small AUM (₹{aum} Cr) - liquidity/stability risk in stress scenarios", -4)
        elif aum > 75000:
            pts -= 2; result.add(f"Very large AUM (₹{aum} Cr) - may face agility constraints, especially for mid/small cap mandates", -2)

    score = _clip(50 + pts)
    return {
        "overall_score": round(score, 1),
        "signal": _fund_signal_from_score(score),
        "reasons": result.reasons,
        "cagr_1y": cagr1,
        "cagr_3y": cagr3,
        "cagr_5y": cagr5,
    }


def _fund_signal_from_score(score: float) -> str:
    """
    Mutual fund signals are framed differently from stocks -
    'Sell' rarely applies the same way (you don't short a fund),
    the real decision is continue-SIP / switch / stop.
    """
    if score >= 75:
        return "Strong Buy / Continue & Consider Increasing SIP"
    if score >= 62:
        return "Buy / Continue SIP"
    if score >= 48:
        return "Hold / Continue SIP, Monitor"
    if score >= 35:
        return "Reduce / Review vs Category Peers"
    return "Consider Switching to a Better Performing Fund in Category"
