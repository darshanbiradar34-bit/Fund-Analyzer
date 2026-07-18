"""
report.py
----------
Takes the raw scoring output and formats it into a human-readable
report (console/markdown). This is deliberately separated from the
scoring logic so you can later swap this out for a JSON API response,
HTML template, or PDF generator without touching the analysis code.
"""

from datetime import datetime


DISCLAIMER = (
    "This is an automated, rule-based analysis for educational purposes only. "
    "It is NOT investment advice. It has not been reviewed by a SEBI Registered "
    "Investment Advisor. Past performance and technical patterns do not guarantee "
    "future results. Do your own research and consider consulting a qualified "
    "advisor before making investment decisions."
)


def format_stock_report(ticker: str, fundamentals: dict, technicals: dict, signal: dict) -> str:
    lines = []
    lines.append(f"{'='*70}")
    lines.append(f"STOCK ANALYSIS REPORT: {fundamentals.get('company_name') or ticker}")
    lines.append(f"Ticker: {ticker}   |   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"{'='*70}\n")

    lines.append(f"FINAL SIGNAL: {signal['signal']}")
    lines.append(f"Overall Score: {signal['overall_score']}/100   "
                 f"(Technical: {signal['technical_score']}/100, Fundamental: {signal['fundamental_score']}/100)")
    lines.append(f"Confidence: {signal['confidence_pct']}%\n")

    lines.append("-- KEY FUNDAMENTAL DATA --")
    lines.append(f"Sector: {fundamentals.get('sector')}  |  Industry: {fundamentals.get('industry')}")
    lines.append(f"Market Cap: {_fmt_num(fundamentals.get('market_cap'))}")
    lines.append(f"PE (Trailing/Forward): {fundamentals.get('pe_trailing')} / {fundamentals.get('pe_forward')}")
    lines.append(f"ROE: {_fmt_pct(fundamentals.get('roe'))}   ROA: {_fmt_pct(fundamentals.get('roa'))}")
    lines.append(f"Net Margin: {_fmt_pct(fundamentals.get('profit_margin'))}   "
                 f"Debt/Equity: {fundamentals.get('debt_to_equity')}")
    lines.append(f"Revenue Growth: {_fmt_pct(fundamentals.get('revenue_growth'))}")
    lines.append(f"Institutional Holding: {_fmt_pct(fundamentals.get('held_by_institutions_pct'))}\n")

    lines.append("-- KEY TECHNICAL DATA --")
    lines.append(f"Last Close: {technicals.get('last_close')}   Trend: {technicals.get('trend')}")
    lines.append(f"EMA20/50/200: {technicals.get('ema20')} / {technicals.get('ema50')} / {technicals.get('ema200')}")
    lines.append(f"RSI(14): {technicals.get('rsi14')}   MACD Histogram: {technicals.get('macd_histogram')}")
    lines.append(f"52W Range: {technicals.get('low_52w')} - {technicals.get('high_52w')}  "
                 f"(currently {technicals.get('pct_from_52w_high')}% from high)\n")

    lines.append("-- WHY THIS SIGNAL: FUNDAMENTAL REASONS --")
    for reason, pts in signal["fundamental_reasons"]:
        sign = "+" if pts >= 0 else ""
        lines.append(f"  [{sign}{pts:.0f}] {reason}")

    lines.append("\n-- WHY THIS SIGNAL: TECHNICAL REASONS --")
    for reason, pts in signal["technical_reasons"]:
        sign = "+" if pts >= 0 else ""
        lines.append(f"  [{sign}{pts:.0f}] {reason}")

    lines.append(f"\n{'-'*70}")
    lines.append("DISCLAIMER: " + DISCLAIMER)
    lines.append(f"{'='*70}")

    return "\n".join(lines)


def format_fund_report(scheme_name: str, fundamentals: dict, technicals: dict, signal: dict) -> str:
    lines = []
    lines.append(f"{'='*70}")
    lines.append(f"MUTUAL FUND ANALYSIS REPORT: {scheme_name}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"{'='*70}\n")

    lines.append(f"FINAL SIGNAL: {signal['signal']}")
    lines.append(f"Overall Score: {signal['overall_score']}/100\n")

    lines.append("-- FUND DETAILS --")
    lines.append(f"Fund House: {fundamentals.get('fund_house')}")
    lines.append(f"Category: {fundamentals.get('scheme_category')}")
    lines.append(f"Type: {fundamentals.get('scheme_type')}")
    if fundamentals.get("expense_ratio") is not None:
        lines.append(f"Expense Ratio: {fundamentals.get('expense_ratio')}%")
    if fundamentals.get("aum_crore") is not None:
        lines.append(f"AUM: ₹{fundamentals.get('aum_crore')} Cr")
    lines.append("")

    lines.append("-- RETURNS --")
    lines.append(f"1-Year CAGR: {signal.get('cagr_1y')}%")
    lines.append(f"3-Year CAGR: {signal.get('cagr_3y')}%")
    lines.append(f"5-Year CAGR: {signal.get('cagr_5y')}%\n")

    lines.append("-- WHY THIS SIGNAL --")
    for reason, pts in signal["reasons"]:
        sign = "+" if pts >= 0 else ""
        lines.append(f"  [{sign}{pts:.0f}] {reason}")

    lines.append(f"\n{'-'*70}")
    lines.append("DISCLAIMER: " + DISCLAIMER)
    lines.append(f"{'='*70}")

    return "\n".join(lines)


def _fmt_num(n):
    if n is None:
        return "N/A"
    if n >= 1e7:
        return f"₹{n/1e7:.1f} Cr" if n < 1e12 else f"{n:,.0f}"
    return f"{n:,.0f}"


def _fmt_pct(x):
    if x is None:
        return "N/A"
    return f"{x*100:.1f}%"
