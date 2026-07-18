"""
demo_data.py
-------------
Generates synthetic stock price / mutual fund NAV data for demo mode -
lets the web app be tried out instantly without hitting real APIs
(useful for showing friends the UI, or developing without burning
API calls). Real analysis in production mode uses data_sources.py instead.

The synthetic series is seeded deterministically from the name typed in,
so the same query always produces the same demo result (rather than
random noise every refresh).
"""

import hashlib
import numpy as np
import pandas as pd


def _seed_from_name(name: str) -> int:
    return int(hashlib.sha256(name.lower().strip().encode()).hexdigest(), 16) % (2**31)


def demo_stock_history(name: str, days: int = 400) -> pd.DataFrame:
    seed = _seed_from_name(name)
    rng = np.random.default_rng(seed)

    # Deterministic but varied "personality" per name: drift and vol
    # derived from the hash so different tickers look genuinely different.
    trend = rng.uniform(-0.0018, 0.0018)
    vol = rng.uniform(0.010, 0.022)
    start_price = rng.uniform(150, 3500)

    returns = rng.normal(trend, vol, days)
    close = start_price * np.cumprod(1 + returns)
    high = close * (1 + rng.uniform(0, 0.01, days))
    low = close * (1 - rng.uniform(0, 0.01, days))
    open_ = close * (1 + rng.normal(0, 0.005, days))
    volume = rng.integers(200_000, 3_000_000, days)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=days, freq="D")

    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


def demo_stock_info(name: str) -> dict:
    seed = _seed_from_name(name)
    rng = np.random.default_rng(seed + 1)

    sectors = ["Technology", "Financial Services", "Healthcare", "Energy",
               "Consumer Goods", "Industrials", "Materials"]
    sector = sectors[seed % len(sectors)]

    return {
        "longName": f"{name.strip().title()} Ltd (Demo Data)",
        "sector": sector,
        "industry": f"{sector} - General",
        "marketCap": float(rng.uniform(5e9, 2e12)),
        "trailingPE": float(rng.uniform(8, 60)),
        "forwardPE": float(rng.uniform(7, 55)),
        "priceToBook": float(rng.uniform(0.8, 12)),
        "returnOnEquity": float(rng.uniform(-0.05, 0.35)),
        "returnOnAssets": float(rng.uniform(-0.02, 0.20)),
        "debtToEquity": float(rng.uniform(5, 220)),
        "currentRatio": float(rng.uniform(0.6, 3.2)),
        "profitMargins": float(rng.uniform(-0.05, 0.28)),
        "operatingMargins": float(rng.uniform(0.02, 0.32)),
        "revenueGrowth": float(rng.uniform(-0.12, 0.30)),
        "earningsGrowth": float(rng.uniform(-0.15, 0.35)),
        "dividendYield": float(rng.uniform(0, 0.035)),
        "heldPercentInstitutions": float(rng.uniform(0.10, 0.65)),
    }


def demo_fund_nav_history(name: str, days: int = 1900) -> pd.DataFrame:
    seed = _seed_from_name(name)
    rng = np.random.default_rng(seed + 2)

    trend = rng.uniform(-0.0002, 0.0009)
    vol = rng.uniform(0.006, 0.013)
    start_nav = rng.uniform(15, 120)

    returns = rng.normal(trend, vol, days)
    nav = start_nav * np.cumprod(1 + returns)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=days, freq="D")

    return pd.DataFrame({"date": dates, "nav": nav})


def demo_fund_meta(name: str) -> dict:
    seed = _seed_from_name(name)
    rng = np.random.default_rng(seed + 3)

    categories = ["Equity - Flexi Cap", "Equity - Large Cap", "Equity - Mid Cap",
                  "Equity - Small Cap", "Equity - ELSS", "Hybrid - Aggressive"]
    amcs = ["Demo Mutual Fund AMC", "Sample Asset Management", "Test Fund House"]

    return {
        "scheme_name": f"{name.strip().title()} Fund - Direct Growth (Demo Data)",
        "fund_house": amcs[seed % len(amcs)],
        "scheme_type": "Open Ended",
        "scheme_category": categories[seed % len(categories)],
        "expense_ratio": round(float(rng.uniform(0.3, 1.8)), 2),
        "aum_crore": round(float(rng.uniform(200, 90000)), 0),
    }
