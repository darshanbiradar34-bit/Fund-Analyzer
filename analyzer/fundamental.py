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

        # ---- Phase 2 additions ----
        "business_summary": g("longBusinessSummary"),
        "full_time_employees": g("fullTimeEmployees"),
        "website": g("website"),
        "city": g("city"),
        "country": g("country"),
        "ev_to_revenue_alt": g("enterpriseToRevenue"),
        "price_to_sales": g("priceToSalesTrailing12Months"),
        "book_value_per_share": g("bookValue"),
        "next_earnings_date": _extract_earnings_date(info),
    }


def _extract_earnings_date(info: dict):
    """yfinance sometimes returns earnings date as a list of timestamps."""
    val = info.get("earningsTimestampStart") or info.get("earningsTimestamp")
    if val is None:
        return None
    try:
        import datetime
        return datetime.datetime.utcfromtimestamp(val).strftime("%Y-%m-%d")
    except Exception:
        return None


def compute_growth_metrics(financials) -> dict:
    """
    Computes multi-year revenue/profit CAGR from yfinance's `financials`
    DataFrame (columns = period-end dates, most recent first; rows =
    line items like 'Total Revenue', 'Net Income').

    LIMITATION: yfinance typically only returns ~4 years of annual
    financials, and coverage for Indian (NSE/BSE) stocks is often
    thinner than for US stocks - some rows may simply be missing.
    Returns None for any metric it can't compute rather than guessing.
    """
    result = {"revenue_cagr": None, "profit_cagr": None, "years_of_data": 0}

    if financials is None or financials.empty:
        return result

    try:
        cols = sorted(financials.columns)  # oldest -> newest
        years = len(cols)
        result["years_of_data"] = years
        if years < 2:
            return result

        oldest_col, newest_col = cols[0], cols[-1]
        n_years = (newest_col - oldest_col).days / 365.25
        if n_years <= 0:
            return result

        for row_name, out_key in [("Total Revenue", "revenue_cagr"), ("Net Income", "profit_cagr")]:
            if row_name in financials.index:
                old_val = financials.loc[row_name, oldest_col]
                new_val = financials.loc[row_name, newest_col]
                if old_val and new_val and old_val > 0 and new_val > 0:
                    cagr = ((new_val / old_val) ** (1 / n_years) - 1) * 100
                    result[out_key] = round(float(cagr), 2)
    except Exception:
        pass  # leave as None rather than guessing on unexpected data shapes

    return result


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
