"""
fundamental.py
---------------
Extracts and organizes fundamental metrics for a stock from yfinance's
`info` dict and financial statements. Also computes mutual-fund-level
"fundamentals" (expense ratio, AUM, category consistency) which are
conceptually different from stock fundamentals but serve the same
decision-making role.

IMPORTANT LIMITATION: yfinance's fundamental data for Indian (NSE/BSE)
stocks is often incomplete or delayed compared to US stocks. For a
serious product, plan to supplement this with a paid data provider
(e.g. Screener.in has no public API but can be scraped with permission,
Tickertape, or Refinitiv/Bloomberg if budget allows).
"""

import numpy as np


def extract_stock_fundamentals(info: dict) -> dict:
    """
    Pulls the key ratios out of yfinance's info dict into a clean,
    consistently-named structure. Missing values are returned as None
    rather than guessed.
    """
    def g(key):
        val = info.get(key)
        return val if val not in (None, "None") else None

    return {
        "company_name": g("longName") or g("shortName"),
        "sector": g("sector"),
        "industry": g("industry"),
        "market_cap": g("marketCap"),
        "pe_trailing": g("trailingPE"),
        "pe_forward": g("forwardPE"),
        "peg_ratio": g("pegRatio"),
        "price_to_book": g("priceToBook"),
        "ev_to_ebitda": g("enterpriseToEbitda"),
        "ev_to_revenue": g("enterpriseToRevenue"),
        "profit_margin": g("profitMargins"),
        "operating_margin": g("operatingMargins"),
        "roe": g("returnOnEquity"),
        "roa": g("returnOnAssets"),
        "debt_to_equity": g("debtToEquity"),
        "current_ratio": g("currentRatio"),
        "quick_ratio": g("quickRatio"),
        "revenue_growth": g("revenueGrowth"),
        "earnings_growth": g("earningsGrowth"),
        "dividend_yield": g("dividendYield"),
        "payout_ratio": g("payoutRatio"),
        "beta": g("beta"),
        "free_cashflow": g("freeCashflow"),
        "total_cash": g("totalCash"),
        "total_debt": g("totalDebt"),
        "shares_outstanding": g("sharesOutstanding"),
        "held_by_institutions_pct": g("heldPercentInstitutions"),
        "held_by_insiders_pct": g("heldPercentInsiders"),
        "52w_change_pct": g("52WeekChange"),
        "target_mean_price": g("targetMeanPrice"),
        "recommendation_key": g("recommendationKey"),  # yfinance's own analyst-consensus tag
        "number_of_analyst_opinions": g("numberOfAnalystOpinions"),
    }


def extract_fund_fundamentals(mf_meta: dict, expense_ratio: float = None,
                               aum_crore: float = None) -> dict:
    """
    mfapi.in does not provide expense ratio or AUM directly - those
    typically require AMFI's separate factsheet data or a paid data
    vendor (Value Research, Morningstar API). This function is
    structured to accept them once you wire up that source.
    """
    return {
        "fund_house": mf_meta.get("fund_house"),
        "scheme_type": mf_meta.get("scheme_type"),
        "scheme_category": mf_meta.get("scheme_category"),
        "expense_ratio": expense_ratio,   # plug in from AMFI/Value Research when available
        "aum_crore": aum_crore,           # plug in from AMFI/Value Research when available
    }
