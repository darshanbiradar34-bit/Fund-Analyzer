"""
data_sources.py
----------------
Handles all external data fetching for stocks and mutual funds.

Stock data:  yfinance (free, unofficial Yahoo Finance wrapper)
             Works for Indian stocks by appending .NS (NSE) or .BO (BSE)
             e.g. "RELIANCE.NS", "TCS.NS", "INFY.NS"

Mutual fund data: mfapi.in (free, public, unofficial AMFI wrapper)
             No API key needed. Search by scheme name/code.

NOTE: This module makes real network calls. It will only work in an
environment with internet access (your local machine / server), not
in this sandbox.
"""

import requests
import yfinance as yf
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# STOCK DATA
# ---------------------------------------------------------------------------

@dataclass
class StockData:
    ticker: str
    info: dict = field(default_factory=dict)          # company/fundamental info
    history: Optional[pd.DataFrame] = None             # OHLCV price history
    financials: Optional[pd.DataFrame] = None           # income statement
    balance_sheet: Optional[pd.DataFrame] = None
    cashflow: Optional[pd.DataFrame] = None


def resolve_indian_ticker(name_or_ticker: str) -> str:
    """
    Best-effort resolution of a plain name/ticker into a Yahoo Finance
    compatible symbol for NSE listed stocks. If the user already passed
    something like 'TCS.NS' or 'AAPL', it's returned unchanged.

    For a production app, replace this with a proper symbol search
    (e.g. NSE's own symbol master CSV, or a search endpoint) rather than
    guessing suffixes.
    """
    name_or_ticker = name_or_ticker.strip().upper()
    if "." in name_or_ticker:
        return name_or_ticker
    # crude heuristic: assume NSE unless told otherwise
    return f"{name_or_ticker}.NS"


def fetch_stock_data(ticker: str, period: str = "2y") -> StockData:
    """
    Pulls price history + fundamental info + financial statements
    for a given ticker using yfinance.
    """
    resolved = resolve_indian_ticker(ticker)
    yf_ticker = yf.Ticker(resolved)

    info = {}
    try:
        info = yf_ticker.info
    except Exception as e:
        info = {"error": str(e)}

    history = yf_ticker.history(period=period)

    financials = None
    balance_sheet = None
    cashflow = None
    try:
        financials = yf_ticker.financials
        balance_sheet = yf_ticker.balance_sheet
        cashflow = yf_ticker.cashflow
    except Exception:
        pass

    return StockData(
        ticker=resolved,
        info=info,
        history=history,
        financials=financials,
        balance_sheet=balance_sheet,
        cashflow=cashflow,
    )


# ---------------------------------------------------------------------------
# MUTUAL FUND DATA (mfapi.in - free, no key required)
# ---------------------------------------------------------------------------

MFAPI_SEARCH_URL = "https://api.mfapi.in/mf/search"
MFAPI_SCHEME_URL = "https://api.mfapi.in/mf/{scheme_code}"


@dataclass
class MutualFundData:
    scheme_code: str
    scheme_name: str
    nav_history: pd.DataFrame  # columns: date, nav
    fund_house: str = ""
    scheme_type: str = ""
    scheme_category: str = ""


def search_mutual_fund(name: str) -> list:
    """
    Searches mfapi.in for scheme names matching the query.
    Returns a list of {schemeCode, schemeName} dicts.
    """
    resp = requests.get(MFAPI_SEARCH_URL, params={"q": name}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_mutual_fund_data(scheme_code: str) -> MutualFundData:
    """
    Fetches full NAV history + meta info for a given AMFI scheme code.
    """
    resp = requests.get(MFAPI_SCHEME_URL.format(scheme_code=scheme_code), timeout=10)
    resp.raise_for_status()
    payload = resp.json()

    meta = payload.get("meta", {})
    nav_records = payload.get("data", [])

    df = pd.DataFrame(nav_records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
        df["nav"] = df["nav"].astype(float)
        df = df.sort_values("date").reset_index(drop=True)

    return MutualFundData(
        scheme_code=str(scheme_code),
        scheme_name=meta.get("scheme_name", ""),
        nav_history=df,
        fund_house=meta.get("fund_house", ""),
        scheme_type=meta.get("scheme_type", ""),
        scheme_category=meta.get("scheme_category", ""),
    )


def resolve_mutual_fund(name: str) -> MutualFundData:
    """
    Convenience wrapper: search by name, take the best match, fetch full data.
    In a real app you'd show the user the list and let them pick, since
    fund names are often ambiguous (e.g. many "Direct Growth" variants).
    """
    results = search_mutual_fund(name)
    if not results:
        raise ValueError(f"No mutual fund found matching '{name}'")
    best_match = results[0]
    return fetch_mutual_fund_data(best_match["schemeCode"])


# ---------------------------------------------------------------------------
# NEWS (via yfinance - no separate news API key needed)
# ---------------------------------------------------------------------------

def fetch_stock_news(ticker: str, limit: int = 10) -> list:
    """
    Pulls recent headlines from yfinance's built-in news feed. This
    piggybacks on the Yahoo Finance data we already fetch prices from,
    so it needs no separate API key or paid news service - the
    tradeoff is coverage can be thin for smaller Indian names.

    Returns a list of {title, publisher, link, published_ts} dicts.
    """
    resolved = resolve_indian_ticker(ticker)
    yf_ticker = yf.Ticker(resolved)

    try:
        raw = yf_ticker.news or []
    except Exception:
        raw = []

    items = []
    for entry in raw[:limit]:
        # yfinance's news schema has shifted over versions; read defensively
        content = entry.get("content", entry)
        title = content.get("title") or entry.get("title")
        provider = content.get("provider")
        publisher = provider.get("displayName") if isinstance(provider, dict) else entry.get("publisher")
        canonical = content.get("canonicalUrl")
        link = canonical.get("url") if isinstance(canonical, dict) else entry.get("link")
        published = content.get("pubDate") or entry.get("providerPublishTime")
        if title:
            items.append({"title": title, "publisher": publisher, "link": link, "published": published})

    return items


# ---------------------------------------------------------------------------
# CHART DATA (Phase 5) - flexible period/interval series for candlestick charts
# ---------------------------------------------------------------------------

def fetch_price_series(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Lighter-weight than fetch_stock_data() - just OHLCV for a chosen
    period/interval, without also pulling info/financials. Used by the
    candlestick chart endpoint so switching date ranges doesn't re-fetch
    everything.
    """
    resolved = resolve_indian_ticker(ticker)
    yf_ticker = yf.Ticker(resolved)
    return yf_ticker.history(period=period, interval=interval)


def fetch_intraday_series(ticker: str, interval: str = "5m") -> pd.DataFrame:
    """
    Today's intraday candles for "live" chart mode.

    HONESTY NOTE: Yahoo Finance's free intraday data is typically
    delayed ~15-20 minutes, not true real-time tick data. yfinance also
    restricts how far back fine intervals go (1m is last-7-days only,
    for example). This is fine for a "roughly live" view during market
    hours, but should never be sold to users as real-time.
    """
    resolved = resolve_indian_ticker(ticker)
    yf_ticker = yf.Ticker(resolved)
    return yf_ticker.history(period="1d", interval=interval)
