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

=== Phase 2/3/4 additions ===
- Stock analysis now also returns growth metrics, business summary,
  horizon-based strategy views, and recent news+sentiment.
- New accounts/watchlist/alerts API, backed by a local SQLite file
  (see analyzer/db.py for the important caveat about free-tier hosting
  wiping this file on redeploy).
- New /api/chat endpoint for a real LLM-backed assistant. Requires an
  ANTHROPIC_API_KEY environment variable - without it, this endpoint
  returns a clear "not configured" error instead of failing silently.
  *** This endpoint was written correctly against the documented API
  shape but has NOT been tested end-to-end (no internet/API key were
  available in the environment this was built in). Test it yourself
  once deployed with a real key before relying on it. ***

Query params on the analysis API (unchanged):
    /api/analyze/stock?name=TCS
    /api/analyze/stock?name=TCS&demo=1        <- synthetic data, no internet needed
    /api/analyze/fund?name=Parag+Parikh+Flexi+Cap
    /api/analyze/fund?name=...&demo=1
"""

import json
import os
import re
import traceback
import numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import cookies as http_cookies
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path

from analyzer.technical import compute_stock_technicals, compute_fund_technicals
from analyzer.fundamental import (
    extract_stock_fundamentals, extract_fund_fundamentals, compute_growth_metrics,
)
from analyzer.scoring import (
    score_stock_technicals, score_stock_fundamentals, build_stock_signal, score_fund
)
from analyzer.patterns import detect_candlestick_patterns
from analyzer.risk import assess_stock_risk
from analyzer.ai_summary import build_stock_ai_summary
from analyzer.strategy import build_all_strategies
from analyzer.sentiment import score_headline
from analyzer import demo_data
from analyzer import db

STATIC_DIR = Path(__file__).parent / "static"
# Most hosting platforms (Render, Railway, Heroku, Fly.io) assign a port via
# the PORT environment variable at runtime — you don't pick it yourself.
# Locally this just falls back to 8000.
PORT = int(os.environ.get("PORT", 8000))

SESSION_COOKIE_NAME = "desk_session"


# ---------------------------------------------------------------------------
# Core analysis functions - return plain dicts (JSON-serializable)
# ---------------------------------------------------------------------------

def run_stock_analysis(name: str, demo: bool) -> dict:
    if demo:
        info = demo_data.demo_stock_info(name)
        history = demo_data.demo_stock_history(name)
        ticker = f"{name.strip().upper()}.DEMO"
        growth = demo_data.demo_growth_metrics(name)
        business_summary = demo_data.demo_business_summary(name)
        news_raw = demo_data.demo_stock_news(name)
    else:
        # Live mode - requires `pip install yfinance requests` and internet access
        from analyzer.data_sources import fetch_stock_data, fetch_stock_news
        data = fetch_stock_data(name)
        info = data.info
        history = data.history
        ticker = data.ticker
        growth = compute_growth_metrics(data.financials)
        business_summary = info.get("longBusinessSummary")
        news_raw = fetch_stock_news(name)

    fundamentals = extract_stock_fundamentals(info)
    fundamentals["revenue_cagr"] = growth.get("revenue_cagr")
    fundamentals["profit_cagr"] = growth.get("profit_cagr")
    fundamentals["growth_years_of_data"] = growth.get("years_of_data")
    if not fundamentals.get("business_summary"):
        fundamentals["business_summary"] = business_summary

    technicals = compute_stock_technicals(history)

    if technicals and not technicals.get("error"):
        technicals["candle_patterns"] = detect_candlestick_patterns(history)

    tech_score = score_stock_technicals(technicals)
    fund_score = score_stock_fundamentals(fundamentals)
    signal = build_stock_signal(tech_score, fund_score)

    risk = assess_stock_risk(fundamentals, technicals)
    ai_summary = build_stock_ai_summary(fundamentals, technicals, signal, risk)
    strategy = build_all_strategies(fundamentals, technicals, signal, risk)

    news = []
    for item in news_raw:
        sentiment = score_headline(item.get("title", ""))
        news.append({**item, "sentiment": sentiment["label"]})

    return {
        "type": "stock",
        "ticker": ticker,
        "demo": demo,
        "fundamentals": fundamentals,
        "technicals": technicals,
        "signal": signal,
        "risk": risk,
        "ai_summary": ai_summary,
        "strategy": strategy,
        "news": news,
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
# Alert evaluation (Phase 3) - checked on demand, not push/email notified.
# See db.py + README for what "alerting" does and doesn't do here.
# ---------------------------------------------------------------------------

def check_alerts_for_user(user_id: int, demo: bool) -> list:
    alerts = db.list_alerts(user_id)
    triggered = []

    # Group by symbol+type so we only run analysis once per instrument
    by_symbol = {}
    for a in alerts:
        if a["triggered_at"] is not None:
            continue
        key = (a["symbol"], a["item_type"])
        by_symbol.setdefault(key, []).append(a)

    for (symbol, item_type), symbol_alerts in by_symbol.items():
        try:
            if item_type == "stock":
                result = run_stock_analysis(symbol, demo)
                last_price = result["technicals"].get("last_close")
                rsi = result["technicals"].get("rsi14")
            else:
                result = run_fund_analysis(symbol, demo)
                last_price = result["technicals"].get("last_nav")
                rsi = result["technicals"].get("rsi14")
        except Exception:
            continue  # skip symbols that fail to fetch rather than crashing the whole check

        for a in symbol_alerts:
            hit = False
            if a["condition_type"] == "price_above" and last_price is not None and last_price > a["threshold"]:
                hit = True
            elif a["condition_type"] == "price_below" and last_price is not None and last_price < a["threshold"]:
                hit = True
            elif a["condition_type"] == "rsi_above" and rsi is not None and rsi > a["threshold"]:
                hit = True
            elif a["condition_type"] == "rsi_below" and rsi is not None and rsi < a["threshold"]:
                hit = True

            if hit:
                db.mark_alert_triggered(a["id"])
                triggered.append({**a, "current_value": last_price if "price" in a["condition_type"] else rsi})

    return triggered


# ---------------------------------------------------------------------------
# AI Chat (Phase 4b) - real LLM call, requires ANTHROPIC_API_KEY.
# *** UNTESTED: written to the documented API shape, but this sandbox has
# no internet access and no API key to verify against. Test after deploy. ***
# ---------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

CHAT_SYSTEM_PROMPT = (
    "You are a financial research assistant embedded in a stock/fund analysis "
    "tool called 'The Desk'. You'll be given the current analysis context "
    "(scores, key metrics) for whatever the user is looking at. Answer their "
    "question using that context where relevant. Be concise, use plain "
    "English, explain financial terms on first use, and never give a bare "
    "'buy' or 'sell' instruction without reasoning. Always note you are not "
    "a licensed financial advisor and this isn't personalized advice."
)


def call_claude_chat(message: str, context: dict) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "error": (
                "AI chat isn't configured yet - set an ANTHROPIC_API_KEY environment "
                "variable on your server (e.g. in Render's dashboard under Environment) "
                "and redeploy. Get a key from console.anthropic.com."
            )
        }

    try:
        import requests
    except ImportError:
        return {"error": "The 'requests' package is required for chat but isn't installed."}

    context_str = json.dumps(context, default=str)[:4000]  # keep the prompt bounded
    user_content = f"Current analysis context:\n{context_str}\n\nUser question: {message}"

    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 1024,
                "system": CHAT_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_content}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
        return {"reply": "\n".join(text_parts) or "(empty response)"}
    except Exception as e:
        return {"error": f"Chat request failed: {e}"}


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


def _json_default(obj):
    """
    Safety net for numpy scalar types slipping into API responses
    (e.g. np.bool_, np.int64, np.float64) - converts them to plain
    Python types instead of crashing the response.
    """
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


WATCHLIST_ID_RE = re.compile(r"^/api/watchlist/(\d+)$")
ALERT_ID_RE = re.compile(r"^/api/alerts/(\d+)$")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    # ---- response helpers ----

    def _send_json(self, payload: dict, status: int = 200, set_cookie: str = None):
        body = json.dumps(payload, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Credentials", "true")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, rel_path: str):
        if rel_path == "" or rel_path == "/":
            rel_path = "index.html"
        file_path = (STATIC_DIR / rel_path.lstrip("/")).resolve()

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

    # ---- request helpers ----

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _session_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = http_cookies.SimpleCookie()
        jar.load(raw)
        morsel = jar.get(SESSION_COOKIE_NAME)
        return morsel.value if morsel else None

    def _current_user_id(self):
        return db.get_user_id_from_session(self._session_token())

    def _require_user(self):
        """Returns user_id, or sends a 401 and returns None."""
        user_id = self._current_user_id()
        if user_id is None:
            self._send_json({"error": "Not logged in."}, 401)
            return None
        return user_id

    @staticmethod
    def _make_cookie(token: str) -> str:
        return f"{SESSION_COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={30*24*60*60}"

    @staticmethod
    def _clear_cookie() -> str:
        return f"{SESSION_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    # ---- CORS preflight ----

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ---- GET ----

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
                return self._send_json(run_stock_analysis(name, demo))

            if path == "/api/analyze/fund":
                name = unquote(params.get("name", "")).strip()
                demo = params.get("demo", "0") in ("1", "true", "True")
                if not name:
                    return self._send_json({"error": "Missing 'name' parameter"}, 400)
                return self._send_json(run_fund_analysis(name, demo))

            if path == "/api/auth/me":
                user_id = self._current_user_id()
                if user_id is None:
                    return self._send_json({"logged_in": False})
                return self._send_json({"logged_in": True, "username": db.get_username(user_id)})

            if path == "/api/watchlist":
                user_id = self._require_user()
                if user_id is None:
                    return
                return self._send_json({"items": db.list_watchlist(user_id)})

            if path == "/api/alerts":
                user_id = self._require_user()
                if user_id is None:
                    return
                return self._send_json({"items": db.list_alerts(user_id)})

            if path.startswith("/api/"):
                return self._send_json({"error": "Unknown API route"}, 404)

            if path == "/":
                return self._send_static("index.html")
            if path.startswith("/static/"):
                return self._send_static(path[len("/static/"):])
            return self.send_error(404, "Not found")

        except ValueError as e:
            return self._send_json({"error": str(e)}, 404)
        except Exception as e:
            traceback.print_exc()
            return self._send_json({"error": f"Analysis failed: {e}"}, 500)

    # ---- POST ----

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/auth/register":
                body = self._read_json_body()
                result = db.create_user(body.get("username", ""), body.get("password", ""))
                if not result["ok"]:
                    return self._send_json({"error": result["error"]}, 400)
                token = db.create_session(result["user_id"])
                return self._send_json(
                    {"ok": True, "username": body.get("username", "").strip()},
                    set_cookie=self._make_cookie(token),
                )

            if path == "/api/auth/login":
                body = self._read_json_body()
                user_id = db.verify_user(body.get("username", ""), body.get("password", ""))
                if user_id is None:
                    return self._send_json({"error": "Invalid username or password."}, 401)
                token = db.create_session(user_id)
                return self._send_json(
                    {"ok": True, "username": db.get_username(user_id)},
                    set_cookie=self._make_cookie(token),
                )

            if path == "/api/auth/logout":
                token = self._session_token()
                if token:
                    db.delete_session(token)
                return self._send_json({"ok": True}, set_cookie=self._clear_cookie())

            if path == "/api/watchlist":
                user_id = self._require_user()
                if user_id is None:
                    return
                body = self._read_json_body()
                symbol = body.get("symbol", "")
                item_type = body.get("item_type", "stock")
                notes = body.get("notes", "")
                if not symbol:
                    return self._send_json({"error": "Missing 'symbol'."}, 400)
                result = db.add_watchlist_item(user_id, symbol, item_type, notes)
                if not result["ok"]:
                    return self._send_json({"error": result["error"]}, 400)
                return self._send_json({"ok": True, "id": result["id"]})

            if path == "/api/alerts":
                user_id = self._require_user()
                if user_id is None:
                    return
                body = self._read_json_body()
                symbol = body.get("symbol", "")
                item_type = body.get("item_type", "stock")
                condition_type = body.get("condition_type", "")
                threshold = body.get("threshold")
                if not symbol or threshold is None:
                    return self._send_json({"error": "Missing 'symbol' or 'threshold'."}, 400)
                try:
                    threshold = float(threshold)
                except (TypeError, ValueError):
                    return self._send_json({"error": "'threshold' must be a number."}, 400)
                result = db.add_alert(user_id, symbol, item_type, condition_type, threshold)
                if not result["ok"]:
                    return self._send_json({"error": result["error"]}, 400)
                return self._send_json({"ok": True, "id": result["id"]})

            if path == "/api/alerts/check":
                user_id = self._require_user()
                if user_id is None:
                    return
                params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                demo = params.get("demo", "1") in ("1", "true", "True")
                triggered = check_alerts_for_user(user_id, demo)
                return self._send_json({"triggered": triggered})

            if path == "/api/chat":
                body = self._read_json_body()
                message = body.get("message", "")
                context = body.get("context", {})
                if not message:
                    return self._send_json({"error": "Missing 'message'."}, 400)
                result = call_claude_chat(message, context)
                if "error" in result:
                    return self._send_json(result, 503)
                return self._send_json(result)

            return self._send_json({"error": "Unknown API route"}, 404)

        except Exception as e:
            traceback.print_exc()
            return self._send_json({"error": f"Request failed: {e}"}, 500)

    # ---- DELETE ----

    def do_DELETE(self):
        path = urlparse(self.path).path

        try:
            m = WATCHLIST_ID_RE.match(path)
            if m:
                user_id = self._require_user()
                if user_id is None:
                    return
                ok = db.remove_watchlist_item(user_id, int(m.group(1)))
                return self._send_json({"ok": ok})

            m = ALERT_ID_RE.match(path)
            if m:
                user_id = self._require_user()
                if user_id is None:
                    return
                ok = db.remove_alert(user_id, int(m.group(1)))
                return self._send_json({"ok": ok})

            return self._send_json({"error": "Unknown API route"}, 404)

        except Exception as e:
            traceback.print_exc()
            return self._send_json({"error": f"Request failed: {e}"}, 500)


def main():
    db.init_db()
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
