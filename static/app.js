// app.js — The Desk frontend logic

const form = document.getElementById("search-form");
const input = document.getElementById("search-input");
const demoCheckbox = document.getElementById("demo-checkbox");
const modeButtons = document.querySelectorAll(".mode-btn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const emptyState = document.getElementById("empty-state");

let currentMode = "stock";

const MODE_PLACEHOLDERS = {
  stock: "TCS · RELIANCE · INFY",
  fund: "Parag Parikh Flexi Cap · HDFC Flexi Cap",
};

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

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = input.value.trim();
  if (!name) return;

  const demo = demoCheckbox.checked;
  const submitBtn = form.querySelector(".search-btn");

  setStatus(`Pulling ${demo ? "demo" : "live"} data for "${name}"…`);
  resultEl.hidden = true;
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

    render(data);
    clearStatus();
  } catch (err) {
    setStatus(`Couldn't complete analysis: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
});

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.hidden = false;
  statusEl.classList.toggle("error", isError);
}

function clearStatus() {
  statusEl.hidden = true;
  statusEl.textContent = "";
}

function render(data) {
  resultEl.hidden = false;

  const isStock = data.type === "stock";
  const signal = data.signal;
  const name = isStock ? data.ticker : data.scheme_name;

  document.getElementById("result-eyebrow").textContent = isStock ? "Stock" : "Mutual Fund";
  document.getElementById("result-name").textContent = name;

  // Signal chip
  const chip = document.getElementById("signal-chip");
  const signalText = signal.signal;
  document.getElementById("signal-text").textContent = signalText;
  chip.className = "signal-chip " + classifySignal(signalText);

  // Gauge
  const score = signal.overall_score;
  drawGauge(score);
  document.getElementById("gauge-score-value").textContent = Math.round(score);

  const subScores = document.getElementById("gauge-sub-scores");
  subScores.innerHTML = "";
  if (isStock) {
    subScores.appendChild(subScoreRow("Technical", signal.technical_score));
    subScores.appendChild(subScoreRow("Fundamental", signal.fundamental_score));
    subScores.appendChild(subScoreRow("Confidence", signal.confidence_pct + "%", false));
  } else {
    if (signal.cagr_1y != null) subScores.appendChild(subScoreRow("1Y CAGR", signal.cagr_1y + "%", false));
    if (signal.cagr_3y != null) subScores.appendChild(subScoreRow("3Y CAGR", signal.cagr_3y + "%", false));
    if (signal.cagr_5y != null) subScores.appendChild(subScoreRow("5Y CAGR", signal.cagr_5y + "%", false));
  }

  // Metrics strip
  const metricsStrip = document.getElementById("metrics-strip");
  metricsStrip.innerHTML = "";
  const metrics = isStock ? buildStockMetrics(data) : buildFundMetrics(data);
  metrics.forEach(([label, value]) => metricsStrip.appendChild(metricEl(label, value)));

  // Ledgers
  const ledgerGrid = document.getElementById("ledger-grid");
  ledgerGrid.innerHTML = "";
  if (isStock) {
    ledgerGrid.appendChild(buildLedger("Fundamental Ledger", signal.fundamental_reasons));
    ledgerGrid.appendChild(buildLedger("Technical Ledger", signal.technical_reasons));
  } else {
    ledgerGrid.appendChild(buildLedger("Signal Ledger", signal.reasons));
  }

  document.getElementById("disclaimer").textContent =
    "Rule-based, educational analysis" + (data.demo ? " using SYNTHETIC DEMO DATA (not real market data)" : "") +
    ". Not investment advice, and not reviewed by a SEBI Registered Investment Advisor. " +
    "Past performance and technical patterns do not guarantee future results.";
}

function classifySignal(text) {
  const t = text.toLowerCase();
  if (t.includes("strong sell") || t.includes("sell") || t.includes("switching")) return "bearish";
  if (t.includes("buy")) return "bullish";
  return "neutral";
}

function subScoreRow(label, value, isScore = true) {
  const div = document.createElement("div");
  div.className = "sub-row";
  div.innerHTML = `<span>${label}</span><span>${isScore ? Math.round(value) + "/100" : value}</span>`;
  return div;
}

function metricEl(label, value) {
  const div = document.createElement("div");
  div.className = "metric";
  div.innerHTML = `<span class="metric-label">${label}</span><span class="metric-value">${value}</span>`;
  return div;
}

function buildStockMetrics(data) {
  const t = data.technicals;
  const f = data.fundamentals;
  const pct = (x) => (x == null ? "N/A" : (x * 100).toFixed(1) + "%");
  return [
    ["Last Close", t.last_close ?? "N/A"],
    ["Trend", t.trend ?? "N/A"],
    ["RSI (14)", t.rsi14 ?? "N/A"],
    ["52W High/Low", `${t.low_52w ?? "?"} – ${t.high_52w ?? "?"}`],
    ["PE (Trailing)", f.pe_trailing != null ? f.pe_trailing.toFixed(1) : "N/A"],
    ["ROE", pct(f.roe)],
    ["Net Margin", pct(f.profit_margin)],
    ["Debt/Equity", f.debt_to_equity != null ? f.debt_to_equity.toFixed(0) : "N/A"],
    ["Revenue Growth", pct(f.revenue_growth)],
    ["Sector", f.sector ?? "N/A"],
  ];
}

function buildFundMetrics(data) {
  const f = data.fundamentals;
  return [
    ["Category", f.scheme_category ?? "N/A"],
    ["Fund House", f.fund_house ?? "N/A"],
    ["Expense Ratio", f.expense_ratio != null ? f.expense_ratio + "%" : "N/A"],
    ["AUM", f.aum_crore != null ? `₹${Math.round(f.aum_crore).toLocaleString("en-IN")} Cr` : "N/A"],
    ["Type", f.scheme_type ?? "N/A"],
  ];
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

// ---------------------------------------------------------------------------
// Gauge drawing
// ---------------------------------------------------------------------------

function drawGauge(score) {
  const track = document.getElementById("gauge-track");
  const needle = document.getElementById("gauge-needle");

  // Semicircle track from (10,130) to (230,130), radius 110, centered at (120,130)
  track.setAttribute("d", "M10,130 A110,110 0 0 1 230,130");

  // Needle: default line points straight up from hub (120,130) to (120,40).
  // score=0 -> pointing left (-90deg), score=100 -> pointing right (+90deg)
  const clamped = Math.max(0, Math.min(100, score));
  const angle = (clamped / 100) * 180 - 90;
  needle.setAttribute("transform", `rotate(${angle})`);
}
