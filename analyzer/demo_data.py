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


# ---------------------------------------------------------------------------
# Phase 2/4 additions: demo growth metrics, business summary, and news
# ---------------------------------------------------------------------------

def demo_growth_metrics(name: str) -> dict:
    seed = _seed_from_name(name)
    rng = np.random.default_rng(seed + 4)
    return {
        "revenue_cagr": round(float(rng.uniform(-5, 25)), 2),
        "profit_cagr": round(float(rng.uniform(-10, 30)), 2),
        "years_of_data": 4,
    }


def demo_business_summary(name: str) -> str:
    seed = _seed_from_name(name)
    rng = np.random.default_rng(seed + 5)
    templates = [
        "{n} designs, manufactures, and sells products across its core markets, "
        "serving both domestic and export customers through a network of "
        "distributors and direct sales channels.",
        "{n} operates primarily in services, offering solutions to enterprise "
        "and retail customers, with a growing focus on digital delivery channels.",
        "{n} is engaged in the production and distribution of goods for "
        "industrial and consumer markets, with operations spanning several "
        "manufacturing facilities.",
    ]
    template = templates[seed % len(templates)]
    return "[DEMO DATA] " + template.format(n=name.strip().title())


_HEADLINE_TEMPLATES_POSITIVE = [
    "{n} reports strong quarterly profit growth, beats estimates",
    "{n} shares rally after upgrade from brokerage firm",
    "{n} announces buyback, board approves dividend increase",
    "{n} expands into new markets, wins large export order",
]
_HEADLINE_TEMPLATES_NEGATIVE = [
    "{n} shares fall after quarterly results miss expectations",
    "{n} faces regulatory probe over compliance concerns",
    "Brokerage downgrades {n} citing valuation risk",
    "{n} warns of margin pressure amid rising input costs",
]
_HEADLINE_TEMPLATES_NEUTRAL = [
    "{n} to announce quarterly results next week",
    "{n} appoints new independent director to the board",
    "{n} completes previously announced facility expansion",
    "Analysts maintain hold rating on {n} ahead of earnings",
]


def demo_stock_news(name: str, limit: int = 6) -> list:
    seed = _seed_from_name(name)
    rng = np.random.default_rng(seed + 6)
    display_name = name.strip().title()

    pool = (
        [(t, "positive") for t in _HEADLINE_TEMPLATES_POSITIVE]
        + [(t, "negative") for t in _HEADLINE_TEMPLATES_NEGATIVE]
        + [(t, "neutral") for t in _HEADLINE_TEMPLATES_NEUTRAL]
    )
    rng.shuffle(pool)

    now = pd.Timestamp.today()
    items = []
    for i, (template, _bias) in enumerate(pool[:limit]):
        days_ago = int(rng.integers(0, 14))
        items.append({
            "title": "[DEMO] " + template.format(n=display_name),
            "publisher": "Demo Financial Wire",
            "link": None,
            "published": int((now - pd.Timedelta(days=days_ago)).timestamp()),
        })
    return items


# ---------------------------------------------------------------------------
# Phase 5 additions: chart series (period/interval aware) + intraday demo
# ---------------------------------------------------------------------------

_PERIOD_TO_DAYS = {
    "1mo": 30, "3mo": 90, "6mo": 182, "1y": 365, "2y": 730, "5y": 1825,
}


def demo_price_series(name: str, period: str = "6mo") -> pd.DataFrame:
    """Same generator as demo_stock_history, just parameterized by period string."""
    days = _PERIOD_TO_DAYS.get(period, 182)
    return demo_stock_history(name, days=days)


def demo_intraday_series(name: str, interval: str = "5m") -> pd.DataFrame:
    """
    Synthetic "today's session" candles, 9:15 AM - 3:30 PM IST, for
    exercising the Live chart mode without needing real market hours
    or a network connection.
    """
    seed = _seed_from_name(name)
    rng = np.random.default_rng(seed + 7)

    minutes_map = {"1m": 1, "5m": 5, "15m": 15}
    step = minutes_map.get(interval, 5)
    session_minutes = (15 * 60 + 30) - (9 * 60 + 15)  # 9:15 to 15:30
    bars = session_minutes // step

    today = pd.Timestamp.today().normalize()
    start = today + pd.Timedelta(hours=9, minutes=15)
    times = [start + pd.Timedelta(minutes=step * i) for i in range(bars)]

    start_price = rng.uniform(200, 3500)
    trend = rng.uniform(-0.0004, 0.0004)
    vol = rng.uniform(0.002, 0.006)
    returns = rng.normal(trend, vol, bars)
    close = start_price * np.cumprod(1 + returns)
    high = close * (1 + rng.uniform(0, 0.003, bars))
    low = close * (1 - rng.uniform(0, 0.003, bars))
    open_ = close * (1 + rng.normal(0, 0.001, bars))
    volume = rng.integers(5_000, 80_000, bars)

    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=pd.DatetimeIndex(times),
    )
