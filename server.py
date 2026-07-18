"""
server.py
----------
A small, dependency-light web server exposing the analyzer engine
over HTTP, and serving the static frontend (static/index.html etc).

Built on Python's standard library `http.server` rather than
FastAPI/Flask deliberately — zero extra install burden for you or
your friends beyond what analysis itself needs (requests + yfinance
for live mode). If this grows beyond a friend group, migrating this
to FastAPI later is straightforward since all the actual logic lives
in analyzer/ and main.py, not in this file.

Run:
    python server.py
Then open:
    http://localhost:8000

Query params on the API:
    /api/analyze/stock?name=TCS
    /api/analyze/stock?name=TCS&demo=1        <- synthetic data, no internet needed
    /api/analyze/fund?name=Parag+Parikh+Flexi+Cap
    /api/analyze/fund?name=...&demo=1
"""

import json
import os
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path

from analyzer.technical import compute_stock_technicals, compute_fund_technicals
from analyzer.fundamental import extract_stock_fundamentals, extract_fund_fundamentals
from analyzer.scoring import (
    score_stock_technicals, score_stock_fundamentals, build_stock_signal, score_fund
)
from analyzer import demo_data

STATIC_DIR = Path(__file__).parent / "static"
# Most hosting platforms (Render, Railway, Heroku, Fly.io) assign a port via
# the PORT environment variable at runtime — you don't pick it yourself.
# Locally this just falls back to 8000.
PORT = int(os.environ.get("PORT", 8000))


# ---------------------------------------------------------------------------
# Core analysis functions - return plain dicts (JSON-serializable)
# ---------------------------------------------------------------------------

def run_stock_analysis(name: str, demo: bool) -> dict:
    if demo:
        info = demo_data.demo_stock_info(name)
        history = demo_data.demo_stock_history(name)
        ticker = f"{name.strip().upper()}.DEMO"
    else:
        # Live mode - requires `pip install yfinance requests` and internet access
        from analyzer.data_sources import fetch_stock_data
        data = fetch_stock_data(name)
        info = data.info
        history = data.history
        ticker = data.ticker

    fundamentals = extract_stock_fundamentals(info)
    technicals = compute_stock_technicals(history)

    tech_score = score_stock_technicals(technicals)
    fund_score = score_stock_fundamentals(fundamentals)
    signal = build_stock_signal(tech_score, fund_score)

    return {
        "type": "stock",
        "ticker": ticker,
        "demo": demo,
        "fundamentals": fundamentals,
        "technicals": technicals,
        "signal": signal,
    }


def run_fund_analysis(name: str, demo: bool) -> dict:
    if demo:
        meta = demo_data.demo_fund_meta(name)
        nav_history = demo_data.demo_fund_nav_history(name)
        scheme_name = meta["scheme_name"]
    else:
        # Live mode - requires `pip install requests` and internet access
        from analyzer.data_sources import resolve_mutual_fund
        data = resolve_mutual_fund(name)
        nav_history = data.nav_history
        scheme_name = data.scheme_name
        meta = {
            "fund_house": data.fund_house,
            "scheme_type": data.scheme_type,
            "scheme_category": data.scheme_category,
        }

    technicals = compute_fund_technicals(nav_history)
    fundamentals = extract_fund_fundamentals(
        meta,
        expense_ratio=meta.get("expense_ratio"),
        aum_crore=meta.get("aum_crore"),
    )
    signal = score_fund(technicals, fundamentals)

    return {
        "type": "fund",
        "scheme_name": scheme_name,
        "demo": demo,
        "fundamentals": fundamentals,
        "technicals": technicals,
        "signal": signal,
    }


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, rel_path: str):
        if rel_path == "" or rel_path == "/":
            rel_path = "index.html"
        file_path = (STATIC_DIR / rel_path.lstrip("/")).resolve()

        # Prevent path traversal outside static/
        if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
            self.send_error(403, "Forbidden")
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not found")
            return

        content_type = CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        try:
            if path == "/api/analyze/stock":
                name = unquote(params.get("name", "")).strip()
                demo = params.get("demo", "0") in ("1", "true", "True")
                if not name:
                    return self._send_json({"error": "Missing 'name' parameter"}, 400)
                result = run_stock_analysis(name, demo)
                return self._send_json(result)

            if path == "/api/analyze/fund":
                name = unquote(params.get("name", "")).strip()
                demo = params.get("demo", "0") in ("1", "true", "True")
                if not name:
                    return self._send_json({"error": "Missing 'name' parameter"}, 400)
                result = run_fund_analysis(name, demo)
                return self._send_json(result)

            if path.startswith("/api/"):
                return self._send_json({"error": "Unknown API route"}, 404)

            # Everything else -> static frontend.
            # "/" serves index.html; "/static/x" serves static/x (strip the prefix
            # since STATIC_DIR already points at the static/ folder).
            if path == "/":
                return self._send_static("index.html")
            if path.startswith("/static/"):
                return self._send_static(path[len("/static/"):])
            return self.send_error(404, "Not found")

        except ValueError as e:
            # Expected errors (e.g. "no fund found matching X")
            return self._send_json({"error": str(e)}, 404)
        except Exception as e:
            traceback.print_exc()
            return self._send_json({"error": f"Analysis failed: {e}"}, 500)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}")
    print(f"  Try:  http://localhost:{PORT}/api/analyze/stock?name=TCS&demo=1")
    print(f"  Try:  http://localhost:{PORT}/api/analyze/fund?name=Flexi+Cap&demo=1")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
