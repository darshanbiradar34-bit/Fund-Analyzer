// app.js — The Desk frontend logic (Phase 1: tabs, theme toggle, expanded sections)

const form = document.getElementById("search-form");
const input = document.getElementById("search-input");
const demoCheckbox = document.getElementById("demo-checkbox");
const modeButtons = document.querySelectorAll(".mode-btn");
const statusEl = document.getElementById("status");
const stockResultEl = document.getElementById("stock-result");
const fundResultEl = document.getElementById("fund-result");
const emptyState = document.getElementById("empty-state");

let currentMode = "stock";

const MODE_PLACEHOLDERS = {
  stock: "TCS · RELIANCE · INFY",
  fund: "Parag Parikh Flexi Cap · HDFC Flexi Cap",
};

// ---------------------------------------------------------------------------
// Theme toggle (persisted so it survives a reload)
// ---------------------------------------------------------------------------

const THEME_KEY = "the-desk-theme";
const themeToggleBtn = document.getElementById("theme-toggle");
const themeToggleIcon = document.getElementById("theme-toggle-icon");

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeToggleIcon.textContent = theme === "dark" ? "☾" : "☀";
  try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* ignore storage errors */ }
}

(function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch (e) { /* ignore */ }
  applyTheme(saved || "dark");
})();

themeToggleBtn.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme");
  applyTheme(current === "dark" ? "light" : "dark");
});

// ---------------------------------------------------------------------------
// Mode toggle (Stock vs Fund)
// ---------------------------------------------------------------------------

modeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    modeButtons.forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-selected", "false");
    });
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    currentMode = btn.dataset.mode;
    input.placeholder = MODE_PLACEHOLDERS[currentMode];
  });
});

// ---------------------------------------------------------------------------
// Tab navigation (within stock result)
// ---------------------------------------------------------------------------

document.getElementById("tab-nav").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-btn");
  if (!btn) return;
  const tab = btn.dataset.tab;

  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b === btn);
    b.setAttribute("aria-selected", b === btn ? "true" : "false");
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `panel-${tab}`);
  });
});

// ---------------------------------------------------------------------------
// Search + fetch
// ---------------------------------------------------------------------------

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = input.value.trim();
  if (!name) return;

  const demo = demoCheckbox.checked;
  const submitBtn = form.querySelector(".search-btn");

  setStatus(`Pulling ${demo ? "demo" : "live"} data for "${name}"…`);
  stockResultEl.hidden = true;
  fundResultEl.hidden = true;
  emptyState.hidden = true;
  submitBtn.disabled = true;

  try {
    const endpoint = currentMode === "stock" ? "/api/analyze/stock" : "/api/analyze/fund";
    const url = `${endpoint}?name=${encodeURIComponent(name)}&demo=${demo ? "1" : "0"}`;
    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    if (data.type === "stock") {
      renderStock(data);
    } else {
      renderFund(data);
    }
    clearStatus();
  } catch (err) {
    setStatus(`Couldn't complete analysis: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
});

function setStatus(msg, isError = false) {
  statusEl.classList.toggle("error", isError);
  const spinnerHtml = isError ? "" : `<span class="spinner"></span>`;
  statusEl.innerHTML = `${spinnerHtml}<span>${msg}</span>`;
  statusEl.hidden = false;
}

function clearStatus() {
  statusEl.hidden = true;
  statusEl.innerHTML = "";
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function classifySignal(text) {
  const t = text.toLowerCase();
  if (t.includes("strong sell") || t.includes("sell") || t.includes("switching")) return "bearish";
  if (t.includes("buy")) return "bullish";
  return "neutral";
}

function pct(x, digits = 1) {
  return x == null ? "N/A" : (x * 100).toFixed(digits) + "%";
}

function num(x, digits = 2) {
  return x == null ? "N/A" : Number(x).toFixed(digits);
}

function metricEl(label, value) {
  const div = document.createElement("div");
  div.className = "metric";
  div.innerHTML = `<span class="metric-label">${label}</span><span class="metric-value">${value}</span>`;
  return div;
}

function fillMetrics(containerId, pairs) {
  const el = document.getElementById(containerId);
  el.innerHTML = "";
  pairs.forEach(([label, value]) => el.appendChild(metricEl(label, value ?? "N/A")));
}

function buildLedger(title, reasons) {
  const wrap = document.createElement("div");
  wrap.className = "ledger";
  const h = document.createElement("h3");
  h.className = "ledger-title";
  h.textContent = title;
  wrap.appendChild(h);

  if (!reasons || reasons.length === 0) {
    const line = document.createElement("div");
    line.className = "ledger-line";
    line.innerHTML = `<span class="ledger-reason">No contributing factors recorded.</span>`;
    wrap.appendChild(line);
    return wrap;
  }

  reasons.forEach(([reason, points]) => {
    const line = document.createElement("div");
    line.className = "ledger-line";
    const cls = points > 0 ? "pos" : points < 0 ? "neg" : "zero";
    const sign = points > 0 ? "+" : "";
    line.innerHTML = `<span class="ledger-reason">${reason}</span><span class="ledger-points ${cls}">${sign}${Math.round(points)}</span>`;
    wrap.appendChild(line);
  });

  return wrap;
}

function fillList(id, items) {
  const ul = document.getElementById(id);
  ul.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = "None identified from current data.";
    ul.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    ul.appendChild(li);
  });
}

function drawGaugeOn(trackId, needleId, score) {
  const track = document.getElementById(trackId);
  const needle = document.getElementById(needleId);
  track.setAttribute("d", "M10,130 A110,110 0 0 1 230,130");
  const clamped = Math.max(0, Math.min(100, score));
  const angle = (clamped / 100) * 180 - 90;
  needle.setAttribute("transform", `rotate(${angle})`);
}

function subScoreRow(label, value, isScore = true) {
  const div = document.createElement("div");
  div.className = "sub-row";
  div.innerHTML = `<span>${label}</span><span>${isScore ? Math.round(value) + "/100" : value}</span>`;
  return div;
}

// ---------------------------------------------------------------------------
// STOCK rendering
// ---------------------------------------------------------------------------

function renderStock(data) {
  fundResultEl.hidden = true;
  stockResultEl.hidden = false;

  const f = data.fundamentals;
  const t = data.technicals;
  const s = data.signal;
  const risk = data.risk;
  const ai = data.ai_summary;

  document.getElementById("stock-eyebrow").textContent = "Stock";
  document.getElementById("stock-name").textContent = data.ticker;

  const chip = document.getElementById("stock-signal-chip");
  document.getElementById("stock-signal-text").textContent = s.signal;
  chip.className = "signal-chip " + classifySignal(s.signal);

  renderOverviewTab(f, t, ai);
  renderTechnicalTab(t, s);
  renderFundamentalTab(f, s);
  renderRiskTab(risk);
  renderAiDecisionTab(ai);
  renderStrategyTab(data.strategy);
  renderNewsTab(data.news);

  currentStockContext = { ticker: data.ticker, signal: s.signal, overall_score: s.overall_score, ai_summary: ai.summary };
  currentStockSymbolForWatchlist = data.ticker.replace(/\.(NS|BO|DEMO)$/i, "");
  updateWatchStarButton("stock-watch-btn", currentStockSymbolForWatchlist, "stock");

  stopLivePolling();
  liveToggleCheckbox.checked = false;
  document.querySelector(".live-toggle").classList.remove("live-active");
  currentChartSymbol = currentStockSymbolForWatchlist;
  currentChartRange = "6mo";
  document.querySelectorAll(".chart-range-btn").forEach((b) => b.classList.toggle("active", b.dataset.range === "6mo"));
  // Only actually fetch chart data if the Chart tab is the active one on render;
  // otherwise it loads lazily when the user clicks into that tab (see tab-nav listener).
  if (document.getElementById("panel-chart").classList.contains("active")) {
    loadDailyChart(currentChartSymbol, currentChartRange);
  }

  document.getElementById("stock-disclaimer").textContent =
    "Rule-based, educational analysis" + (data.demo ? " using SYNTHETIC DEMO DATA (not real market data)" : "") +
    ". Not investment advice, and not reviewed by a SEBI Registered Investment Advisor. " +
    "Past performance and technical patterns do not guarantee future results.";

  // Always return to the Overview tab on a fresh search
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === "overview");
    b.setAttribute("aria-selected", b.dataset.tab === "overview" ? "true" : "false");
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === "panel-overview");
  });
}

function renderOverviewTab(f, t, ai) {
  const rc = ai.rating_card;
  const recClass = classifySignal(rc.recommendation);

  const card = document.getElementById("rating-card");
  card.innerHTML = `
    <div class="rating-item"><span class="rating-label">Rating</span><span class="rating-stars">${rc.stars}</span></div>
    <div class="rating-item"><span class="rating-label">Recommendation</span><span class="rating-value rec-${recClass}">${rc.recommendation}</span></div>
    <div class="rating-item"><span class="rating-label">Confidence</span><span class="rating-value">${rc.confidence_pct}%</span></div>
    <div class="rating-item"><span class="rating-label">Risk</span><span class="rating-value">${rc.overall_risk}</span></div>
    <div class="rating-item"><span class="rating-label">Expected Range</span><span class="rating-value">${rc.expected_return_range}</span></div>
    <div class="rating-item"><span class="rating-label">Horizon</span><span class="rating-value">${rc.time_horizon}</span></div>
  `;

  const box = document.getElementById("ai-summary-box");
  box.innerHTML = `<span class="ai-tag">AI Summary — rule-based, not a live model call</span><p style="margin:0">${ai.summary}</p>`;

  fillMetrics("overview-metrics", [
    ["Last Close", t.last_close],
    ["52W High", t.high_52w],
    ["52W Low", t.low_52w],
    ["Market Cap", f.market_cap != null ? formatMarketCap(f.market_cap) : "N/A"],
    ["Sector", f.sector],
    ["Industry", f.industry],
    ["Beta", f.beta != null ? num(f.beta) : "N/A"],
    ["Volatility (20d)", t.historical_volatility_20d != null ? t.historical_volatility_20d + "%" : "N/A"],
    ["Dividend Yield", pct(f.dividend_yield)],
    ["Institutional Holding", pct(f.held_by_institutions_pct)],
  ]);
}

function formatMarketCap(mcap) {
  const crore = mcap / 1e7;
  if (crore >= 100000) return `₹${(crore / 100000).toFixed(2)} Lakh Cr`;
  return `₹${Math.round(crore).toLocaleString("en-IN")} Cr`;
}

function renderTechnicalTab(t, s) {
  drawGaugeOn("gauge-track", "gauge-needle", s.overall_score);
  document.getElementById("gauge-score-value").textContent = Math.round(s.overall_score);
  const subScores = document.getElementById("gauge-sub-scores");
  subScores.innerHTML = "";
  subScores.appendChild(subScoreRow("Technical", s.technical_score));
  subScores.appendChild(subScoreRow("Fundamental", s.fundamental_score));
  subScores.appendChild(subScoreRow("Confidence", s.confidence_pct + "%", false));

  if (t.error) {
    fillMetrics("technical-headline-metrics", [["Status", t.error]]);
    return;
  }

  fillMetrics("technical-headline-metrics", [
    ["Last Close", t.last_close],
    ["Trend", t.trend],
    ["Trend Strength", t.trend_strength],
    ["52W Range", `${t.low_52w} – ${t.high_52w}`],
  ]);

  fillMetrics("trend-metrics", [
    ["Primary Trend", t.trend],
    ["Market Structure", t.market_structure],
    ["ADX (14)", t.adx14],
    ["+DI / -DI", `${t.plus_di14} / ${t.minus_di14}`],
    ["% from 52W High", t.pct_from_52w_high + "%"],
    ["% from 52W Low", t.pct_from_52w_low + "%"],
  ]);

  fillMetrics("ma-metrics", [
    ["EMA 9", t.ema9],
    ["EMA 20", t.ema20],
    ["EMA 50", t.ema50],
    ["EMA 100", t.ema100],
    ["EMA 200", t.ema200],
    ["SMA 20", t.sma20],
    ["SMA 50", t.sma50],
    ["SMA 200", t.sma200],
    ["Golden Cross", t.golden_cross == null ? "N/A" : (t.golden_cross ? "Yes" : "No")],
    ["Death Cross", t.death_cross == null ? "N/A" : (t.death_cross ? "Yes" : "No")],
    ["% from EMA200", t.pct_from_ema200 != null ? t.pct_from_ema200 + "%" : "N/A"],
  ]);

  fillMetrics("momentum-metrics", [
    ["RSI (14)", t.rsi14],
    ["Stochastic RSI", t.stoch_rsi14],
    ["MACD Line", t.macd_line],
    ["MACD Signal", t.macd_signal],
    ["MACD Histogram", t.macd_histogram],
    ["ROC (12)", t.roc12 != null ? t.roc12 + "%" : "N/A"],
    ["CCI (20)", t.cci20],
    ["Williams %R", t.williams_r14],
  ]);

  fillMetrics("volatility-metrics", [
    ["ATR (14)", t.atr14],
    ["ATR %", t.atr_pct != null ? t.atr_pct + "%" : "N/A"],
    ["Historical Vol (20d)", t.historical_volatility_20d != null ? t.historical_volatility_20d + "%" : "N/A"],
    ["Bollinger Width", t.bb_width_pct != null ? t.bb_width_pct + "%" : "N/A"],
    ["BB Upper / Lower", `${t.bb_upper} / ${t.bb_lower}`],
    ["Keltner Upper / Lower", `${t.keltner_upper} / ${t.keltner_lower}`],
  ]);

  fillMetrics("volume-metrics", [
    ["OBV Trend", t.obv_trend ?? "N/A"],
    ["Rolling VWAP (20d)", t.vwap20 ?? "N/A"],
    ["Money Flow Index", t.mfi14 ?? "N/A"],
    ["Chaikin Money Flow", t.cmf20 ?? "N/A"],
    ["Volume vs 20d Avg", t.volume_vs_20d_avg_pct != null ? t.volume_vs_20d_avg_pct + "%" : "N/A"],
    ["Has Volume Data", t.has_volume_data ? "Yes" : "No"],
  ]);

  const sr = t.support_resistance || {};
  fillMetrics("sr-metrics", [
    ["Pivot", sr.pivot],
    ["Resistance 1 / 2 / 3", `${sr.resistance_1} / ${sr.resistance_2} / ${sr.resistance_3}`],
    ["Support 1 / 2 / 3", `${sr.support_1} / ${sr.support_2} / ${sr.support_3}`],
    ["Swing High / Low", `${sr.swing_high} / ${sr.swing_low}`],
  ]);

  const fibRow = document.getElementById("fib-row");
  fibRow.innerHTML = "";
  if (sr.fibonacci_levels) {
    Object.entries(sr.fibonacci_levels).forEach(([levelPct, val]) => {
      const div = document.createElement("div");
      div.className = "fib-item";
      div.innerHTML = `<span class="fib-pct">${levelPct}</span><span class="fib-val">${val}</span>`;
      fibRow.appendChild(div);
    });
  }

  const chipsWrap = document.getElementById("pattern-chips");
  chipsWrap.innerHTML = "";
  const patterns = t.candle_patterns || [];
  if (patterns.length === 0) {
    chipsWrap.innerHTML = `<span class="pattern-chips-empty">No candlestick patterns detected in the most recent bars.</span>`;
  } else {
    patterns.forEach((p) => {
      const chip = document.createElement("span");
      chip.className = `pattern-chip ${p.signal}`;
      chip.title = p.description;
      chip.textContent = p.name;
      chipsWrap.appendChild(chip);
    });
  }

  const ledgerGrid = document.getElementById("technical-ledger-grid");
  ledgerGrid.innerHTML = "";
  ledgerGrid.appendChild(buildLedger("Technical Ledger", s.technical_reasons));
}

function renderFundamentalTab(f, s) {
  document.getElementById("business-summary-text").textContent =
    f.business_summary || "No business summary available from current data sources.";

  fillMetrics("growth-metrics", [
    ["Revenue CAGR", f.revenue_cagr != null ? f.revenue_cagr + "%" : "N/A"],
    ["Profit CAGR", f.profit_cagr != null ? f.profit_cagr + "%" : "N/A"],
    ["Years of Data", f.growth_years_of_data ?? "N/A"],
    ["Next Earnings", f.next_earnings_date || "N/A"],
    ["Employees", f.full_time_employees != null ? Number(f.full_time_employees).toLocaleString("en-IN") : "N/A"],
  ]);

  fillMetrics("fundamental-metrics", [
    ["PE (Trailing)", f.pe_trailing != null ? num(f.pe_trailing, 1) : "N/A"],
    ["PE (Forward)", f.pe_forward != null ? num(f.pe_forward, 1) : "N/A"],
    ["PEG Ratio", f.peg_ratio != null ? num(f.peg_ratio) : "N/A"],
    ["Price/Book", f.price_to_book != null ? num(f.price_to_book) : "N/A"],
    ["EV/EBITDA", f.ev_to_ebitda != null ? num(f.ev_to_ebitda) : "N/A"],
    ["ROE", pct(f.roe)],
    ["ROA", pct(f.roa)],
    ["Operating Margin", pct(f.operating_margin)],
    ["Net Margin", pct(f.profit_margin)],
    ["Debt/Equity", f.debt_to_equity != null ? num(f.debt_to_equity, 0) : "N/A"],
    ["Current Ratio", f.current_ratio != null ? num(f.current_ratio) : "N/A"],
    ["Quick Ratio", f.quick_ratio != null ? num(f.quick_ratio) : "N/A"],
    ["Revenue Growth", pct(f.revenue_growth)],
    ["Earnings Growth", pct(f.earnings_growth)],
    ["Dividend Yield", pct(f.dividend_yield)],
    ["Payout Ratio", pct(f.payout_ratio)],
  ]);

  const ledgerGrid = document.getElementById("fundamental-ledger-grid");
  ledgerGrid.innerHTML = "";
  ledgerGrid.appendChild(buildLedger("Fundamental Ledger", s.fundamental_reasons));
}

function renderRiskTab(risk) {
  const overallEl = document.getElementById("risk-overall");
  const overallCls = riskClass(risk.overall_risk);
  overallEl.innerHTML = `
    <span class="risk-overall-label">Overall Risk</span>
    <span class="risk-chip ${overallCls}">${risk.overall_risk}</span>
  `;

  const grid = document.getElementById("risk-grid");
  grid.innerHTML = "";
  const labels = {
    financial_risk: "Financial / Debt Risk",
    valuation_risk: "Valuation Risk",
    business_risk: "Business Risk",
    volatility_risk: "Volatility Risk",
    liquidity_risk: "Liquidity Risk",
    governance_risk: "Governance Risk",
    regulatory_risk: "Regulatory Risk",
    macro_global_risk: "Macro / Global Risk",
  };

  Object.entries(risk.categories).forEach(([key, cat]) => {
    const card = document.createElement("div");
    card.className = "risk-card";
    const cls = riskClass(cat.label);
    const reasonItems = cat.reasons.map((r) => `<li>${r}</li>`).join("");
    card.innerHTML = `
      <div class="risk-card-header">
        <span class="risk-card-title">${labels[key] || key}</span>
        <span class="risk-chip ${cls}">${cat.label}</span>
      </div>
      <ul>${reasonItems}</ul>
    `;
    grid.appendChild(card);
  });
}

function riskClass(label) {
  const map = {
    "Low": "low",
    "Medium": "medium",
    "High": "high",
    "Very High": "very-high",
    "Not Assessed": "not-assessed",
    "Unknown": "not-assessed",
  };
  return map[label] || "not-assessed";
}

function renderAiDecisionTab(ai) {
  document.getElementById("engine-note").textContent =
    `Engine: ${ai.engine}`;

  const prob = ai.probability;
  const bar = document.getElementById("probability-bar");
  bar.innerHTML = `
    <div class="probability-segment bullish" style="width:${prob.bullish_pct}%">${prob.bullish_pct}%</div>
    <div class="probability-segment neutral" style="width:${prob.neutral_pct}%">${prob.neutral_pct > 8 ? prob.neutral_pct + "%" : ""}</div>
    <div class="probability-segment bearish" style="width:${prob.bearish_pct}%">${prob.bearish_pct}%</div>
  `;
  document.getElementById("probability-legend").innerHTML = `
    <span>▮ Bullish</span><span>▮ Neutral</span><span>▮ Bearish</span>
  `;

  fillList("bull-case-list", ai.bull_case);
  fillList("bear-case-list", ai.bear_case);
  fillList("base-case-list", ai.base_case);
  fillList("why-buy-list", ai.why_buy);
  fillList("why-avoid-list", ai.why_avoid);
  fillList("invalidation-list", ai.invalidation_criteria);
}

// ---------------------------------------------------------------------------
// FUND rendering (Phase 0 layout, unchanged in substance)
// ---------------------------------------------------------------------------

function renderFund(data) {
  stockResultEl.hidden = true;
  fundResultEl.hidden = false;

  const signal = data.signal;
  const f = data.fundamentals;

  document.getElementById("fund-name").textContent = data.scheme_name;

  currentFundSymbolForWatchlist = input.value.trim();
  updateWatchStarButton("fund-watch-btn", currentFundSymbolForWatchlist, "fund");

  const chip = document.getElementById("fund-signal-chip");
  document.getElementById("fund-signal-text").textContent = signal.signal;
  chip.className = "signal-chip " + classifySignal(signal.signal);

  const score = signal.overall_score;
  drawGaugeOn("fund-gauge-track", "fund-gauge-needle", score);
  document.getElementById("fund-gauge-score-value").textContent = Math.round(score);

  const subScores = document.getElementById("fund-gauge-sub-scores");
  subScores.innerHTML = "";
  if (signal.cagr_1y != null) subScores.appendChild(subScoreRow("1Y CAGR", signal.cagr_1y + "%", false));
  if (signal.cagr_3y != null) subScores.appendChild(subScoreRow("3Y CAGR", signal.cagr_3y + "%", false));
  if (signal.cagr_5y != null) subScores.appendChild(subScoreRow("5Y CAGR", signal.cagr_5y + "%", false));

  fillMetrics("fund-metrics", [
    ["Category", f.scheme_category],
    ["Fund House", f.fund_house],
    ["Expense Ratio", f.expense_ratio != null ? f.expense_ratio + "%" : "N/A"],
    ["AUM", f.aum_crore != null ? `₹${Math.round(f.aum_crore).toLocaleString("en-IN")} Cr` : "N/A"],
    ["Type", f.scheme_type],
  ]);

  const ledgerGrid = document.getElementById("fund-ledger-grid");
  ledgerGrid.innerHTML = "";
  ledgerGrid.appendChild(buildLedger("Signal Ledger", signal.reasons));

  document.getElementById("fund-disclaimer").textContent =
    "Rule-based, educational analysis" + (data.demo ? " using SYNTHETIC DEMO DATA (not real market data)" : "") +
    ". Not investment advice, and not reviewed by a SEBI Registered Investment Advisor. " +
    "Past performance and technical patterns do not guarantee future results.";
}

// ---------------------------------------------------------------------------
// PHASE 2: Strategy tab (with sub-tabs) and News tab
// ---------------------------------------------------------------------------

document.getElementById("strategy-subtab-nav").addEventListener("click", (e) => {
  const btn = e.target.closest(".subtab-btn");
  if (!btn) return;
  const sub = btn.dataset.subtab;
  document.querySelectorAll(".subtab-btn").forEach((b) => b.classList.toggle("active", b === btn));
  document.querySelectorAll(".subtab-panel").forEach((p) => p.classList.toggle("active", p.id === `subpanel-${sub}`));
});

function renderStrategyTab(strategy) {
  if (!strategy) return;

  const intraday = strategy.intraday;
  document.getElementById("intraday-limitation").textContent = intraday.data_limitation || "";
  if (intraday.available) {
    fillMetrics("intraday-metrics", [
      ["Bias", intraday.bias],
      ["Expected Range (Today)", intraday.expected_range_today ? `${intraday.expected_range_today.low} – ${intraday.expected_range_today.high}` : "N/A"],
      ["Pivot", intraday.pivot],
      ["Resistance 1", intraday.resistance_1],
      ["Support 1", intraday.support_1],
    ]);
  } else {
    fillMetrics("intraday-metrics", [["Status", intraday.note || "Not available"]]);
  }

  const st = strategy.short_term;
  if (st.available) {
    fillMetrics("short-term-metrics", [
      ["Direction", st.direction],
      ["Ideal Entry", st.ideal_entry],
      ["Aggressive Entry", st.aggressive_entry],
      ["Confirmation Entry", st.confirmation_entry],
      ["Stop Loss", st.stop_loss],
      ["Target 1", st.target_1],
      ["Target 2", st.target_2],
      ["Target 3", st.target_3],
      ["Risk/Reward Ratio", st.risk_reward_ratio],
      ["Swing Probability", st.swing_probability_pct + "%"],
      ["Holding Period", st.holding_period],
    ]);
  } else {
    fillMetrics("short-term-metrics", [["Status", st.note || "Not available"]]);
  }

  const mt = strategy.mid_term;
  fillMetrics("mid-term-metrics", [
    ["Trend Read", mt.trend_read],
    ["Valuation View", mt.valuation_view],
    ["Overall Score", mt.overall_score + "/100"],
    ["Expected Return (6mo, rough)", mt.expected_return_pct_6m_heuristic + "%"],
    ["Portfolio Allocation Guidance", mt.portfolio_allocation_guidance],
  ]);

  const lt = strategy.long_term;
  const growth = lt.growth_projection || {};
  fillMetrics("long-term-metrics", [
    ["Business Quality", lt.business_quality],
    ["Intrinsic Value Estimate", lt.intrinsic_value_estimate ?? "Not computed"],
    ["3Y Revenue Multiple", growth["3y_revenue_projection_multiple"] ?? "N/A"],
    ["5Y Revenue Multiple", growth["5y_revenue_projection_multiple"] ?? "N/A"],
    ["10Y Revenue Multiple", growth["10y_revenue_projection_multiple"] ?? "N/A"],
    ["Wealth Creation Potential", lt.wealth_creation_potential],
  ]);
  document.getElementById("long-term-intrinsic-note").textContent =
    (lt.intrinsic_value_note || "") + (growth.basis ? " " + growth.basis : "");
}

function renderNewsTab(news) {
  const list = document.getElementById("news-list");
  list.innerHTML = "";

  if (!news || news.length === 0) {
    list.innerHTML = `<p class="news-empty">No recent headlines found for this ticker.</p>`;
    return;
  }

  news.forEach((item) => {
    const sentimentClass = (item.sentiment || "Neutral").toLowerCase();
    const div = document.createElement("div");
    div.className = `news-item ${sentimentClass}`;
    const dateStr = item.published ? new Date(item.published * 1000).toLocaleDateString("en-IN") : "";
    const titleHtml = item.link
      ? `<a href="${item.link}" target="_blank" rel="noopener noreferrer" class="news-item-title">${item.title}</a>`
      : `<span class="news-item-title">${item.title}</span>`;
    div.innerHTML = `
      <div class="news-item-main">
        ${titleHtml}
        <div class="news-item-meta">${item.publisher || "Unknown source"}${dateStr ? " · " + dateStr : ""}</div>
      </div>
      <span class="news-sentiment-chip ${sentimentClass}">${item.sentiment || "Neutral"}</span>
    `;
    list.appendChild(div);
  });
}

// ---------------------------------------------------------------------------
// PHASE 3: Accounts, Watchlist, Alerts
// ---------------------------------------------------------------------------

let currentUser = null;
let currentStockContext = null;
let currentStockSymbolForWatchlist = null;
let currentFundSymbolForWatchlist = null;

const authOverlay = document.getElementById("auth-overlay");
const accountBtn = document.getElementById("account-btn");
const authForm = document.getElementById("auth-form");
const authError = document.getElementById("auth-error");
const authSubmitBtn = document.getElementById("auth-submit-btn");
let authMode = "login";

async function apiFetch(url, options = {}) {
  const res = await fetch(url, { ...options, credentials: "include" });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

async function refreshAuthState() {
  const { data } = await apiFetch("/api/auth/me");
  if (data.logged_in) {
    currentUser = data.username;
    accountBtn.textContent = `${data.username} (Sign Out)`;
  } else {
    currentUser = null;
    accountBtn.textContent = "Sign in";
  }
  document.querySelectorAll(".watch-star-btn").forEach((btn) => {
    if (!currentUser) btn.classList.remove("saved");
  });
}

accountBtn.addEventListener("click", async () => {
  if (currentUser) {
    await apiFetch("/api/auth/logout", { method: "POST" });
    await refreshAuthState();
  } else {
    authOverlay.hidden = false;
  }
});

document.getElementById("auth-close").addEventListener("click", () => { authOverlay.hidden = true; });
authOverlay.addEventListener("click", (e) => { if (e.target === authOverlay) authOverlay.hidden = true; });

document.querySelectorAll(".auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".auth-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    authMode = tab.dataset.authtab;
    authSubmitBtn.textContent = authMode === "login" ? "Sign In" : "Create Account";
    authError.hidden = true;
  });
});

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("auth-username").value.trim();
  const password = document.getElementById("auth-password").value;
  const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register";

  const { ok, data } = await apiFetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!ok) {
    authError.textContent = data.error || "Something went wrong.";
    authError.hidden = false;
    return;
  }

  authError.hidden = true;
  authOverlay.hidden = true;
  authForm.reset();
  await refreshAuthState();
  if (!watchlistViewEl.hidden) loadWatchlistView();
});

async function updateWatchStarButton(btnId, symbol, itemType) {
  const btn = document.getElementById(btnId);
  btn.classList.remove("saved");
  btn.onclick = async () => {
    if (!currentUser) {
      authOverlay.hidden = false;
      return;
    }
    const { ok, data } = await apiFetch("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, item_type: itemType }),
    });
    if (ok) {
      btn.classList.add("saved");
      btn.textContent = "★";
    } else {
      alert(data.error || "Could not add to watchlist.");
    }
  };
}

// ---- Watchlist view toggling ----

const searchViewEl = document.getElementById("search-view");
const watchlistViewEl = document.getElementById("watchlist-view");

document.getElementById("watchlist-nav-btn").addEventListener("click", () => {
  searchViewEl.hidden = true;
  watchlistViewEl.hidden = false;
  loadWatchlistView();
});

document.getElementById("watchlist-back-btn").addEventListener("click", () => {
  watchlistViewEl.hidden = true;
  searchViewEl.hidden = false;
});

document.getElementById("watchlist-signin-btn").addEventListener("click", () => {
  authOverlay.hidden = false;
});

async function loadWatchlistView() {
  await refreshAuthState();
  const signedOut = document.getElementById("watchlist-signed-out");
  const signedIn = document.getElementById("watchlist-signed-in");

  if (!currentUser) {
    signedOut.hidden = false;
    signedIn.hidden = true;
    return;
  }
  signedOut.hidden = true;
  signedIn.hidden = false;

  const { data: wl } = await apiFetch("/api/watchlist");
  renderWatchlistTable(wl.items || []);

  const { data: al } = await apiFetch("/api/alerts");
  renderAlertsTable(al.items || []);
}

function renderWatchlistTable(items) {
  const el = document.getElementById("watchlist-table");
  if (items.length === 0) {
    el.innerHTML = `<p class="news-empty">Nothing on your watchlist yet. Search a stock or fund, then tap the ☆ next to its name.</p>`;
    return;
  }
  const rows = items.map((item) => `
    <tr>
      <td>${item.symbol}</td>
      <td>${item.item_type}</td>
      <td>${item.notes || "—"}</td>
      <td>${new Date(item.added_at * 1000).toLocaleDateString("en-IN")}</td>
      <td><button class="remove-btn" data-id="${item.id}">Remove</button></td>
    </tr>
  `).join("");
  el.innerHTML = `
    <table class="watch-table">
      <thead><tr><th>Symbol</th><th>Type</th><th>Notes</th><th>Added</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  el.querySelectorAll(".remove-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await apiFetch(`/api/watchlist/${btn.dataset.id}`, { method: "DELETE" });
      loadWatchlistView();
    });
  });
}

function renderAlertsTable(items) {
  const el = document.getElementById("alerts-table");
  if (items.length === 0) {
    el.innerHTML = `<p class="news-empty">No alerts set yet.</p>`;
    return;
  }
  const rows = items.map((item) => `
    <tr>
      <td>${item.symbol}</td>
      <td>${item.condition_type.replace("_", " ")}</td>
      <td>${item.threshold}</td>
      <td>${item.triggered_at ? "Triggered" : "Active"}</td>
      <td><button class="remove-btn" data-id="${item.id}">Remove</button></td>
    </tr>
  `).join("");
  el.innerHTML = `
    <table class="watch-table">
      <thead><tr><th>Symbol</th><th>Condition</th><th>Threshold</th><th>Status</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  el.querySelectorAll(".remove-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await apiFetch(`/api/alerts/${btn.dataset.id}`, { method: "DELETE" });
      loadWatchlistView();
    });
  });
}

document.getElementById("alert-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const symbol = document.getElementById("alert-symbol").value.trim();
  const item_type = document.getElementById("alert-item-type").value;
  const condition_type = document.getElementById("alert-condition").value;
  const threshold = parseFloat(document.getElementById("alert-threshold").value);

  const { ok, data } = await apiFetch("/api/alerts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, item_type, condition_type, threshold }),
  });
  if (!ok) {
    alert(data.error || "Could not add alert.");
    return;
  }
  e.target.reset();
  loadWatchlistView();
});

document.getElementById("check-alerts-btn").addEventListener("click", async () => {
  const resultEl = document.getElementById("alerts-triggered-result");
  resultEl.innerHTML = `<p class="news-empty">Checking…</p>`;
  const { data } = await apiFetch("/api/alerts/check?demo=1", { method: "POST" });
  const triggered = data.triggered || [];
  if (triggered.length === 0) {
    resultEl.innerHTML = `<p class="news-empty">No alerts triggered.</p>`;
  } else {
    resultEl.innerHTML = triggered.map((t) =>
      `<div class="triggered-alert">🔔 ${t.symbol}: ${t.condition_type.replace("_", " ")} ${t.threshold} — current value ${t.current_value}</div>`
    ).join("");
  }
  loadWatchlistView();
});

// Check login state on page load
refreshAuthState();

// ---------------------------------------------------------------------------
// PHASE 4b: AI Chat widget
// (Backend requires ANTHROPIC_API_KEY - see server.py. Untested live here.)
// ---------------------------------------------------------------------------

const chatFab = document.createElement("button");
chatFab.className = "chat-fab";
chatFab.textContent = "💬";
chatFab.title = "Ask the AI assistant";
document.body.appendChild(chatFab);

const chatPanel = document.createElement("div");
chatPanel.className = "chat-panel";
chatPanel.hidden = true;
chatPanel.innerHTML = `
  <div class="chat-panel-header">
    <span>Ask about this analysis</span>
    <button type="button" id="chat-close" style="background:none;border:none;color:inherit;cursor:pointer;font-size:16px;">×</button>
  </div>
  <div class="chat-messages" id="chat-messages">
    <div class="chat-msg assistant">Ask me about the stock or fund you're currently viewing — e.g. "why is the risk high?" or "explain the RSI value".</div>
  </div>
  <form class="chat-input-row" id="chat-form">
    <input type="text" id="chat-input" placeholder="Ask a question…" autocomplete="off">
    <button type="submit" class="search-btn">Send</button>
  </form>
`;
document.body.appendChild(chatPanel);

chatFab.addEventListener("click", () => { chatPanel.hidden = !chatPanel.hidden; });
chatPanel.querySelector("#chat-close").addEventListener("click", () => { chatPanel.hidden = true; });

chatPanel.querySelector("#chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = chatPanel.querySelector("#chat-input");
  const message = input.value.trim();
  if (!message) return;

  const messagesEl = chatPanel.querySelector("#chat-messages");
  const userMsg = document.createElement("div");
  userMsg.className = "chat-msg user";
  userMsg.textContent = message;
  messagesEl.appendChild(userMsg);
  input.value = "";
  messagesEl.scrollTop = messagesEl.scrollHeight;

  const thinkingMsg = document.createElement("div");
  thinkingMsg.className = "chat-msg assistant";
  thinkingMsg.textContent = "Thinking…";
  messagesEl.appendChild(thinkingMsg);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context: currentStockContext || {} }),
    });
    const data = await res.json();
    thinkingMsg.textContent = data.reply || data.error || "No response.";
    thinkingMsg.className = "chat-msg " + (data.error ? "error" : "assistant");
  } catch (err) {
    thinkingMsg.textContent = "Couldn't reach the chat service: " + err.message;
    thinkingMsg.className = "chat-msg error";
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
});

// ---------------------------------------------------------------------------
// PHASE 5: Candlestick chart with EMA overlays, range selector, live mode
// ---------------------------------------------------------------------------

let priceChart = null;
let candleSeries = null;
let volumeSeries = null;
let emaSeriesMap = {};
let currentChartSymbol = null;
let currentChartRange = "6mo";
let liveIntervalHandle = null;

const EMA_COLORS = { ema9: "#7C9070", ema20: "#C89B3C", ema50: "#B5432F", ema200: "#7C8B94" };

function initChartIfNeeded() {
  if (priceChart) return;
  const container = document.getElementById("candlestick-chart");
  if (!container || typeof LightweightCharts === "undefined") return;

  const isDark = document.documentElement.getAttribute("data-theme") !== "light";

  priceChart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight,
    layout: {
      background: { color: "transparent" },
      textColor: isDark ? "#9AA7AE" : "#5B6167",
    },
    grid: {
      vertLines: { color: isDark ? "rgba(237,230,216,0.06)" : "rgba(16,24,32,0.06)" },
      horzLines: { color: isDark ? "rgba(237,230,216,0.06)" : "rgba(16,24,32,0.06)" },
    },
    timeScale: { timeVisible: true, secondsVisible: false, borderColor: "rgba(124,139,148,0.3)" },
    rightPriceScale: { borderColor: "rgba(124,139,148,0.3)" },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });

  candleSeries = priceChart.addCandlestickSeries({
    upColor: "#7C9070", downColor: "#B5432F",
    borderUpColor: "#7C9070", borderDownColor: "#B5432F",
    wickUpColor: "#7C9070", wickDownColor: "#B5432F",
  });

  volumeSeries = priceChart.addHistogramSeries({
    priceFormat: { type: "volume" },
    priceScaleId: "",
    color: "#7C8B94",
  });
  volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

  window.addEventListener("resize", () => {
    if (priceChart && container) {
      priceChart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    }
  });
}

function renderChartData(payload) {
  updateMarketStatusBadge(payload.market_status);

  initChartIfNeeded();
  if (!priceChart) {
    document.getElementById("chart-data-note").textContent =
      "Chart library failed to load (check your internet connection to unpkg.com).";
    return;
  }

  candleSeries.setData(payload.candles);
  volumeSeries.setData(payload.volume.map((v) => ({
    time: v.time, value: v.value, color: v.color === "up" ? "rgba(124,144,112,0.5)" : "rgba(181,67,47,0.5)",
  })));

  // Clear old EMA series and redraw
  Object.values(emaSeriesMap).forEach((s) => priceChart.removeSeries(s));
  emaSeriesMap = {};
  const legendParts = [];
  Object.entries(payload.emas || {}).forEach(([key, points]) => {
    const color = EMA_COLORS[key] || "#C89B3C";
    const series = priceChart.addLineSeries({ color, lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false });
    series.setData(points);
    emaSeriesMap[key] = series;
    legendParts.push(`<span><span class="legend-swatch" style="background:${color}"></span>${key.toUpperCase()}</span>`);
  });
  document.getElementById("chart-legend").innerHTML = legendParts.join("");

  priceChart.timeScale().fitContent();

  let note = payload.demo ? "Showing SYNTHETIC DEMO DATA, not real prices. " : "";
  if (payload.interval) {
    note += payload.data_delay_note || "";
  } else {
    note += "Daily candles.";
  }
  document.getElementById("chart-data-note").textContent = note;
}

function updateMarketStatusBadge(status) {
  const badge = document.getElementById("market-status-badge");
  if (!status) { badge.textContent = ""; return; }
  badge.textContent = status.is_open ? "● Market Open (IST)" : "○ Market Closed (IST)";
  badge.className = "market-status-badge " + (status.is_open ? "open" : "closed");
}

async function loadDailyChart(symbol, range) {
  const demo = demoCheckbox.checked;
  const { data } = await apiFetch(`/api/chart/stock?name=${encodeURIComponent(symbol)}&demo=${demo ? "1" : "0"}&period=${range}`);
  if (data.candles) renderChartData(data);
}

async function loadIntradayChart(symbol) {
  const demo = demoCheckbox.checked;
  const { data } = await apiFetch(`/api/chart/stock/intraday?name=${encodeURIComponent(symbol)}&demo=${demo ? "1" : "0"}&interval=5m`);
  if (data.candles) renderChartData(data);
}

document.querySelectorAll(".chart-range-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".chart-range-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentChartRange = btn.dataset.range;
    document.getElementById("live-toggle-checkbox").checked = false;
    stopLivePolling();
    if (currentChartSymbol) loadDailyChart(currentChartSymbol, currentChartRange);
  });
});

const liveToggleCheckbox = document.getElementById("live-toggle-checkbox");
liveToggleCheckbox.addEventListener("change", async () => {
  const label = liveToggleCheckbox.closest(".live-toggle");
  if (liveToggleCheckbox.checked) {
    const { data: status } = await apiFetch("/api/market-status");
    updateMarketStatusBadge(status);
    if (!status.is_open) {
      alert("Market is currently closed (NSE hours: 9:15 AM - 3:30 PM IST, Mon-Fri). Live mode only polls during market hours.");
      liveToggleCheckbox.checked = false;
      return;
    }
    label.classList.add("live-active");
    startLivePolling();
  } else {
    label.classList.remove("live-active");
    stopLivePolling();
    if (currentChartSymbol) loadDailyChart(currentChartSymbol, currentChartRange);
  }
});

function startLivePolling() {
  stopLivePolling();
  if (!currentChartSymbol) return;
  loadIntradayChart(currentChartSymbol);
  // Poll every 60s - reasonable balance between "roughly live" and not hammering
  // the free Yahoo Finance endpoint or your own server with requests.
  liveIntervalHandle = setInterval(() => {
    if (currentChartSymbol) loadIntradayChart(currentChartSymbol);
  }, 60000);
}

function stopLivePolling() {
  if (liveIntervalHandle) {
    clearInterval(liveIntervalHandle);
    liveIntervalHandle = null;
  }
}

// Hook chart loading into the tab switcher - loads lazily the first time
// the Chart tab is opened, rather than on every search, to avoid an
// extra request when someone never looks at the chart.
document.getElementById("tab-nav").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-btn");
  if (btn && btn.dataset.tab === "chart" && currentChartSymbol) {
    setTimeout(() => {
      initChartIfNeeded();
      if (priceChart) priceChart.applyOptions({ width: document.getElementById("candlestick-chart").clientWidth });
      if (!liveToggleCheckbox.checked) loadDailyChart(currentChartSymbol, currentChartRange);
    }, 50);
  }
});
