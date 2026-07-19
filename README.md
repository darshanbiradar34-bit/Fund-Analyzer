# Fund/Stock Analysis Engine — now with a web UI

A rule-based research engine that pulls stock or mutual fund data and
produces a scored Buy/Hold/Sell signal with full reasoning, wrapped in
a small web app ("The Desk") so you and your friends can use it from
a browser.

## Run the web app

```bash
cd fund_analyzer
pip install -r requirements.txt
python server.py
```

Then open **http://localhost:8000** in a browser. Type a ticker
(e.g. `TCS`, `RELIANCE`) or a fund name (e.g. `Parag Parikh Flexi Cap`),
pick Stock or Mutual Fund, and hit Analyze.

**"Demo mode" is checked by default** — it generates realistic-looking
but entirely synthetic data, so you and your friends can try the UI
immediately without needing internet access from the server or worrying
about hitting real API rate limits. Uncheck it to pull real data via
yfinance / mfapi.in (needs internet access on whatever machine runs
`server.py`).

### Sharing it with your friend group

`server.py` binds to `0.0.0.0:8000`, so anyone on the same network can
reach it at `http://<your-machine's-IP>:8000`. To make it reachable from
outside your home network (so friends can use it remotely), the simplest
options are:
- Run it on a small cloud VM (DigitalOcean/AWS Lightsail/Render/Railway
  all work fine for something this lightweight) and open port 8000.
- Or use a tunneling tool like `ngrok` or `cloudflared` for a quick
  temporary public URL without deploying anywhere.

This app has **no login/auth** — anyone with the URL can use it. Fine
for a small trusted friend group; add basic auth before sharing further.

## Phase 1 — what's new (July 2026 update)

The stock view is now a **tabbed dossier** instead of one long page:

- **Overview** — AI Rating Card (stars, recommendation, confidence, risk, expected return range, time horizon), a rule-based AI summary paragraph, and key snapshot data
- **Technical** — the score gauge plus trend/market structure, moving averages (EMA 9/20/50/100/200, SMA 20/50/200, golden/death cross), momentum (RSI, Stochastic RSI, MACD, ROC, CCI, Williams %R, ADX/+DI/-DI), volatility (ATR, ATR%, Bollinger width, Keltner Channel, historical volatility), volume (OBV trend, rolling VWAP, MFI, CMF), support/resistance + pivot points + Fibonacci levels, and detected candlestick patterns (Doji, Hammer, Engulfing, Morning/Evening Star, etc.)
- **Fundamental** — expanded ratio grid + the existing ledger
- **Risk** — Low/Medium/High/Very High labels across Financial, Valuation, Business, Volatility, and Liquidity risk, each with real reasons. Governance/Regulatory/Macro risk are honestly marked **"Not Assessed"** rather than guessed — we don't have data feeds for those yet
- **AI Decision** — bull/bear/base case, why-buy/why-avoid (only real reasons, never padded to hit a round number), a bullish/neutral/bearish probability bar, and invalidation criteria

Plus a **dark/light mode toggle** (top right, persisted across visits).

**Important honesty note:** the "AI Summary" and "AI Decision" content is **not a live LLM call** — it's natural-language generation templated directly from the real computed scores (see `analyzer/ai_summary.py`). It reads like AI-generated prose because the sentence structure is templated, but every number in it was actually computed, never invented. A real LLM-backed version is a Phase 4 item (needs an Anthropic API key wired into the server).

New files: `analyzer/patterns.py` (candlestick detection), `analyzer/risk.py` (risk scoring), `analyzer/ai_summary.py` (rating card + narrative generation). `analyzer/technical.py` was significantly expanded but all original fields are unchanged, so nothing downstream broke.

---



Right now `python server.py` only serves `http://localhost:8000` — reachable
from your own machine only. To turn it into a normal website with a URL you
can text to friends, you need to run it somewhere with a public address.
Three options, roughly easiest-to-most-durable:

### Option A — Quick temporary link (minutes, free, resets when you close it)

Good for showing friends right now without deploying anywhere.

```bash
# Terminal 1
python server.py

# Terminal 2 — install ngrok first: https://ngrok.com/download
ngrok http 8000
```

ngrok prints a URL like `https://a1b2c3d4.ngrok-free.app` — share that.
It only works while both commands keep running on your machine, and free
ngrok URLs change every time you restart it.

### Option B — Free/cheap permanent hosting on Render.com (recommended)

This keeps running even when your laptop is off — a real always-on URL.

1. Push this `fund_analyzer` folder to a GitHub repo.
2. Go to [render.com](https://render.com) → sign up (free) → **New +** → **Web Service**.
3. Connect your GitHub repo. Render will detect `render.yaml` automatically
   and pre-fill the build/start commands (`pip install -r requirements.txt`
   and `python server.py`).
4. Click **Create Web Service**. First deploy takes 2-3 minutes.
5. You'll get a URL like `https://the-desk-analyzer.onrender.com` — that's
   your real website. Share it with friends directly.

Render's free tier spins the app down after inactivity and takes ~30-60
seconds to wake up on the next visit — fine for casual friend-group use.
Paid tiers ($7/mo+) keep it always warm if that matters to you.

*(Railway.app and Fly.io work almost identically if you'd rather use those —
same repo, same `Procfile`/start command.)*

### Option C — A VPS you fully control (DigitalOcean, AWS Lightsail, etc.)

More setup, but full control — useful if this grows beyond a hobby tool.

```bash
# On the VPS, after cloning your repo:
pip install -r requirements.txt
nohup python server.py > server.log 2>&1 &
```

Then point a domain's A record at the VPS's IP, and put a reverse proxy
(nginx or Caddy) in front for HTTPS — Caddy is the easiest, it handles
free HTTPS certificates automatically with about 3 lines of config.

### Adding a custom domain

Once deployed on Render/Railway (Option B), you can attach a domain you
own (e.g. `analysis.yourdomain.com`) in the platform's dashboard under
"Custom Domains" — they'll give you a CNAME record to add at your domain
registrar. Both platforms handle HTTPS automatically once that's set up.

### Before sharing it wider than a few close friends

- **There's no login.** Anyone with the URL can use it. Fine for a small
  trusted group; if it spreads further, add basic auth (a single shared
  password check in `server.py`'s `do_GET` is a quick way to start).
- **Live mode calls yfinance/mfapi.in on every request** with no caching —
  if usage grows, you'll want to cache recent results (even a simple
  in-memory dict with a 15-minute expiry) to avoid rate limits.

---

```
fund_analyzer/
├── server.py                   # Stdlib HTTP server: serves the UI + JSON API
├── static/
│   ├── index.html              # Search UI + result dossier layout
│   ├── styles.css              # "Ledger/dossier" visual design
│   └── app.js                  # Fetches from the API, renders gauge + ledgers
├── main.py                     # CLI entry point (still works standalone)
├── analyzer/
│   ├── data_sources.py         # Live data: yfinance + mfapi.in
│   ├── demo_data.py            # Synthetic data generator for demo mode
│   ├── technical.py            # RSI, MACD, EMA, Bollinger, ATR, trend logic
│   ├── fundamental.py          # Extracts PE, ROE, margins, debt ratios etc.
│   ├── scoring.py               # Converts data → 0-100 scores → Buy/Hold/Sell
│   └── report.py               # CLI text report formatter (used by main.py)
└── test_with_synthetic_data.py # Validates the pipeline with fake data
```

**Why a stdlib server instead of FastAPI/Flask?** Zero extra install
burden — `server.py` only needs what's already in `requirements.txt`
for demo mode (numpy/pandas). Live mode additionally needs `requests`
and `yfinance`. If this grows past a friend-group tool, migrating
`server.py`'s two route handlers into FastAPI is a quick, low-risk
change since none of the actual analysis logic lives in that file.

## Phase 2, 3 & 4 — what's new (this update)

### Phase 2 — Deeper Fundamentals + Strategy tabs
- **Fundamental tab** now shows a business overview, multi-year Revenue/Profit CAGR (computed from yfinance's financial statements in live mode), employee count, and next earnings date.
- New **Strategy tab** with four sub-tabs, all built by reorganizing data you already have — no new data source:
  - **Intraday** — honestly framed as a *daily-bar-derived approximation* (expected range from ATR, pivot levels), not real tick data. A clear note in the UI explains this limitation rather than pretending to have real-time granularity.
  - **Short-Term (0-30d)** — entry zones, stop loss, three targets, risk/reward ratio, swing probability.
  - **Mid-Term (1-6mo)** — trend/valuation read, rough expected return, portfolio allocation guidance.
  - **Long-Term (6mo+)** — business quality label, a simplified (explicitly-labeled-as-not-a-real-DCF) intrinsic value sanity check, and mechanical growth extrapolation with a caveat that real growth rates don't stay constant for a decade.

### Phase 3 — Watchlist + Accounts
- Full account system: register/login/logout with hashed passwords (PBKDF2-SHA256, stdlib only) and session cookies.
- Watchlist: star any stock/fund result to save it; manage your list from the new **Watchlist** page (top nav).
- Alerts: set price/RSI thresholds; check them on demand from the Watchlist page. **This is an in-app check, not a push notification or email** — there's no background job or notification service wired up, by design, since that needs infrastructure (a task scheduler + email/push credentials) this build doesn't have.
- **Read this before relying on it:** all of this is stored in a local SQLite file (`data.db`). On Render's free tier, the filesystem resets on every redeploy and periodically on restarts — so watchlists/accounts *will* disappear unexpectedly on the free tier. Fine for trying it out; for anything you want to keep, either upgrade to a Render paid plan with a persistent disk, or migrate to a hosted database (Render/Railway/Supabase all have free Postgres tiers — would need swapping `analyzer/db.py`'s queries, which is the only file that would need to change).

### Phase 4a — News (no new API key needed)
- Reuses yfinance's built-in news feed (the same connection already used for prices), so no separate news API signup required.
- Headlines get a simple keyword-based sentiment tag (Positive/Negative/Neutral) — transparent and inspectable, not a trained model or paid sentiment API. Treat it as a rough at-a-glance signal.

### Phase 4b — AI Chat Assistant
- A floating chat widget on every page, wired to a real Claude API call (`POST /api/chat` in `server.py`).
- **Requires you to set an `ANTHROPIC_API_KEY` environment variable** on your server (Render → your service → Environment tab) — get one at console.anthropic.com. Without it, the chat clearly says it isn't configured rather than failing silently.
- **Important honesty note:** this endpoint was written correctly against Anthropic's documented API shape, but the environment this was built in has no internet access and no API key, so **it has not been tested end-to-end**. Test it yourself after deploying with a real key before relying on it — if something's off, the fix is almost certainly in `call_claude_chat()` in `server.py`.

### Bug fixes found during this update
- Fixed a logic bug in the Short-Term strategy view where Target 3 could come out lower than Target 2 on a Long trade (backwards) — it now always extends further than Target 2 in the trade's direction.
- Fixed a CSS bug where the login modal and chat panel had `display: flex` unconditionally, overriding the browser's default hidden-attribute behavior — this was silently blocking clicks on the search button underneath. Both are now properly hidden until opened.

---

## API reference

```
GET /api/analyze/stock?name=TCS&demo=1
GET /api/analyze/fund?name=Parag+Parikh+Flexi+Cap&demo=1
```

Set `demo=0` (or omit it) for live data. Returns JSON with `fundamentals`,
`technicals`, and `signal` (the score + reasons the frontend renders).
Errors come back as `{"error": "..."}` with a 400/404/500 status.

---

## ⚠️ Important disclaimer

This is an educational tool using rule-based heuristics (moving averages,
RSI, PE ratios, ROE thresholds, etc.) — **not** a licensed investment
advisory product. Since it will only be shared with friends and not sold
or offered publicly, it likely doesn't require SEBI RIA registration —
but if you ever open it up to the public or charge for it, revisit that.
Always keep the disclaimer visible in the UI.

## Setup

```bash
cd fund_analyzer
pip install -r requirements.txt
```

## Usage

```bash
# Analyze a stock (Indian stocks auto-append .NS for NSE)
python main.py stock TCS
python main.py stock "RELIANCE"
python main.py stock AAPL          # US stocks work too, pass ticker directly

# Analyze a mutual fund (searches by name via mfapi.in)
python main.py fund "Parag Parikh Flexi Cap"
python main.py fund "HDFC Flexi Cap"
```

## How it's structured

```
fund_analyzer/
├── main.py                    # CLI entry point
├── analyzer/
│   ├── data_sources.py        # Fetches raw data (yfinance + mfapi.in)
│   ├── technical.py           # RSI, MACD, EMA, Bollinger, ATR, trend logic
│   ├── fundamental.py         # Extracts PE, ROE, margins, debt ratios etc.
│   ├── scoring.py             # Converts data → 0-100 scores → Buy/Hold/Sell
│   └── report.py              # Formats everything into a readable report
└── test_with_synthetic_data.py  # Validates the pipeline with fake data
```

This layering matters: **scoring.py never talks to the internet**, and
**data_sources.py never makes scoring decisions**. That means you can
swap in a web UI, a Telegram bot, or a scheduled daily-email version
later without touching the analysis logic at all.

## Known limitations (be upfront about these with your friends)

1. **yfinance data for Indian stocks is often incomplete** — some ratios
   (ROE, margins, debt) may come back as `None` for smaller/less-covered
   NSE stocks. The report will say "N/A" and explain the score defaulted
   to neutral for that factor rather than silently guessing.
2. **Mutual fund expense ratio and AUM aren't available** from the free
   mfapi.in source — `fundamental.py` has placeholders ready for when you
   wire up a source like AMFI's factsheet data or a paid provider
   (Value Research / Morningstar API).
3. **This is rule-based, not backtested.** The point thresholds (e.g.
   "PE < 15 = +12 points") are sensible textbook defaults, not
   optimized values. Before trusting this with real SIP decisions,
   backtest the scoring against 3-5 years of historical signals vs.
   actual returns and adjust the weights in `scoring.py`.
4. **No caching yet.** Every run hits the APIs fresh. Fine for a
   small friend group checking occasionally; add a simple cache
   (even just saving JSON files with a timestamp) if usage grows.

## Suggested next steps

1. **Run it locally** on 5-10 stocks/funds you know well and sanity-check
   whether the signals match your own intuition. Adjust weights in
   `scoring.py` if something feels off.
2. **Wrap it in a simple API** (FastAPI is the easiest — a single
   `/analyze?type=stock&name=TCS` endpoint calling `main.analyze_stock()`).
3. **Build a minimal web front end** (even a single HTML page with a
   search box) that calls that API and displays the report.
4. **Add caching + rate limiting** once more than 1-2 people are using it,
   so you don't hit API limits.
5. Optionally layer an LLM call (e.g. Claude API) on top of the structured
   scores to generate the narrative "Why Buy / Why Not Buy" prose in
   natural language, using the `reasons` list as grounding so it doesn't
   hallucinate numbers.

## Extending the scoring

All scoring weights and thresholds live in `analyzer/scoring.py` as plain
Python if/else blocks — deliberately not hidden in a config file, so you
can read exactly what drives every score. To change how much technical vs.
fundamental data matters, adjust `tech_weight` / `fund_weight` in
`build_stock_signal()`.
