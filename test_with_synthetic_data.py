"""
test_with_synthetic_data.py
-----------------------------
Validates the analyzer package end-to-end using fabricated data,
since this dev sandbox has no internet access to hit real APIs.

Run this to confirm the scoring/report pipeline works correctly.
When you run main.py on your own machine (with internet), the same
code path will be fed real data from yfinance / mfapi.in instead.
"""

import sys
import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from analyzer.technical import compute_stock_technicals, compute_fund_technicals
from analyzer.fundamental import extract_stock_fundamentals, extract_fund_fundamentals
from analyzer.scoring import (
    score_stock_technicals, score_stock_fundamentals, build_stock_signal, score_fund
)
from analyzer.report import format_stock_report, format_fund_report


def make_synthetic_price_history(days=400, start_price=1000, trend=0.0006, vol=0.015, seed=42):
    """Generates a random-walk-with-drift OHLCV series to mimic real price data."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(trend, vol, days)
    close = start_price * np.cumprod(1 + returns)
    high = close * (1 + rng.uniform(0, 0.01, days))
    low = close * (1 - rng.uniform(0, 0.01, days))
    open_ = close * (1 + rng.normal(0, 0.005, days))
    volume = rng.integers(500_000, 2_000_000, days)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=days, freq="D")
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=dates)


def test_stock_pipeline():
    print("### TEST 1: Stock analysis pipeline (bullish synthetic stock) ###\n")

    history = make_synthetic_price_history(trend=0.0012, vol=0.013)  # upward-biased

    fake_info = {
        "longName": "Synthetic Test Industries Ltd",
        "sector": "Technology",
        "industry": "IT Services",
        "marketCap": 850_000_000_000,
        "trailingPE": 22.5,
        "forwardPE": 19.8,
        "priceToBook": 6.2,
        "returnOnEquity": 0.24,
        "returnOnAssets": 0.15,
        "debtToEquity": 18.0,
        "currentRatio": 2.1,
        "profitMargins": 0.19,
        "operatingMargins": 0.24,
        "revenueGrowth": 0.16,
        "earningsGrowth": 0.18,
        "dividendYield": 0.012,
        "heldPercentInstitutions": 0.42,
    }

    fundamentals = extract_stock_fundamentals(fake_info)
    technicals = compute_stock_technicals(history)

    assert "error" not in technicals, "Technical calc failed unexpectedly"
    assert fundamentals["company_name"] == "Synthetic Test Industries Ltd"

    tech_score = score_stock_technicals(technicals)
    fund_score = score_stock_fundamentals(fundamentals)
    signal = build_stock_signal(tech_score, fund_score)

    assert 0 <= signal["overall_score"] <= 100
    assert signal["signal"] in ("Strong Buy", "Buy", "Accumulate", "Hold", "Reduce", "Sell", "Strong Sell")

    report = format_stock_report("TEST.NS", fundamentals, technicals, signal)
    print(report)
    print(f"\n[PASS] Stock pipeline produced signal: {signal['signal']} (score {signal['overall_score']})\n")


def test_stock_pipeline_bearish():
    print("\n### TEST 2: Stock analysis pipeline (bearish synthetic stock) ###\n")

    history = make_synthetic_price_history(trend=-0.0015, vol=0.02, seed=7)  # downward-biased

    fake_info = {
        "longName": "Synthetic Decline Corp",
        "sector": "Industrials",
        "trailingPE": 55.0,
        "returnOnEquity": 0.04,
        "debtToEquity": 210.0,
        "profitMargins": -0.03,
        "revenueGrowth": -0.08,
        "currentRatio": 0.8,
    }

    fundamentals = extract_stock_fundamentals(fake_info)
    technicals = compute_stock_technicals(history)

    tech_score = score_stock_technicals(technicals)
    fund_score = score_stock_fundamentals(fundamentals)
    signal = build_stock_signal(tech_score, fund_score)

    print(f"Signal: {signal['signal']}  |  Score: {signal['overall_score']}")
    print("Fundamental reasons:")
    for r, p in signal["fundamental_reasons"]:
        print(f"  [{p:+.0f}] {r}")
    print("Technical reasons:")
    for r, p in signal["technical_reasons"]:
        print(f"  [{p:+.0f}] {r}")

    assert signal["overall_score"] < 50, "Bearish synthetic stock should score below neutral"
    print(f"\n[PASS] Bearish stock correctly scored below neutral: {signal['overall_score']}\n")


def test_fund_pipeline():
    print("\n### TEST 3: Mutual fund analysis pipeline ###\n")

    days = 1800  # ~5 years of daily NAV
    rng = np.random.default_rng(1)
    returns = rng.normal(0.0005, 0.009, days)  # decent long-term compounding
    nav = 50 * np.cumprod(1 + returns)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=days, freq="D")
    nav_history = pd.DataFrame({"date": dates, "nav": nav})

    technicals = compute_fund_technicals(nav_history)
    fundamentals = extract_fund_fundamentals(
        {"fund_house": "Test AMC", "scheme_type": "Open Ended", "scheme_category": "Equity - Flexi Cap"},
        expense_ratio=0.55,
        aum_crore=32000,
    )

    signal = score_fund(technicals, fundamentals)
    report = format_fund_report("Test Flexi Cap Fund - Direct Growth", fundamentals, technicals, signal)
    print(report)

    assert 0 <= signal["overall_score"] <= 100
    print(f"\n[PASS] Fund pipeline produced signal: {signal['signal']} (score {signal['overall_score']})\n")


if __name__ == "__main__":
    test_stock_pipeline()
    test_stock_pipeline_bearish()
    test_fund_pipeline()
    print("\n" + "="*70)
    print("ALL TESTS PASSED - scoring engine logic verified with synthetic data")
    print("="*70)
