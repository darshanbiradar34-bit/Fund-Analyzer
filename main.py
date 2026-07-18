"""
main.py
--------
CLI entry point. Usage:

    python main.py stock TCS
    python main.py stock RELIANCE.NS
    python main.py fund "Parag Parikh Flexi Cap"

This is intentionally a thin CLI wrapper - all real logic lives in
the analyzer/ package so it can be reused by a future web backend
(FastAPI/Flask) or a scheduled batch job without rewriting anything.
"""

import sys
from analyzer.data_sources import fetch_stock_data, resolve_mutual_fund
from analyzer.technical import compute_stock_technicals, compute_fund_technicals
from analyzer.fundamental import extract_stock_fundamentals, extract_fund_fundamentals
from analyzer.scoring import (
    score_stock_technicals, score_stock_fundamentals, build_stock_signal, score_fund
)
from analyzer.report import format_stock_report, format_fund_report


def analyze_stock(name: str):
    print(f"Fetching data for {name}...")
    data = fetch_stock_data(name)

    fundamentals = extract_stock_fundamentals(data.info)
    technicals = compute_stock_technicals(data.history)

    tech_score = score_stock_technicals(technicals)
    fund_score = score_stock_fundamentals(fundamentals)
    signal = build_stock_signal(tech_score, fund_score)

    report = format_stock_report(data.ticker, fundamentals, technicals, signal)
    print(report)
    return report


def analyze_fund(name: str):
    print(f"Searching for fund matching '{name}'...")
    data = resolve_mutual_fund(name)

    technicals = compute_fund_technicals(data.nav_history)
    fundamentals = extract_fund_fundamentals({
        "fund_house": data.fund_house,
        "scheme_type": data.scheme_type,
        "scheme_category": data.scheme_category,
    })

    signal = score_fund(technicals, fundamentals)
    report = format_fund_report(data.scheme_name, fundamentals, technicals, signal)
    print(report)
    return report


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python main.py stock <ticker_or_name>")
        print("  python main.py fund <fund_name>")
        sys.exit(1)

    mode = sys.argv[1].lower()
    name = " ".join(sys.argv[2:])

    if mode == "stock":
        analyze_stock(name)
    elif mode == "fund":
        analyze_fund(name)
    else:
        print(f"Unknown mode '{mode}'. Use 'stock' or 'fund'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
