/* Gold Signal Engine dashboard. Reads data/latest.json + data/history.json. */

const $ = (id) => document.getElementById(id);

const fmtUSD = (v) => "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });
const fmtGBP = (v) => "£" + v.toLocaleString("en-GB", { maximumFractionDigits: 0 });

async function loadJSON(path) {
  const r = await fetch(path, { cache: "no-cache" });
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}

function verdictColor(v) {
  return v === "ACCUMULATE" || v === "ADD" ? "var(--gold)"
       : v === "HOLD" ? "var(--text)" : "var(--neg)";
}

function renderGauge(d) {
  $("score").textContent = d.score.toFixed(1).replace(/\.0$/, "");
  $("verdict").textContent = d.verdict;
  $("verdict").style.color = verdictColor(d.verdict);
  $("confidence").textContent =
    `Confidence ${d.confidence.level} · ${d.confidence.freshness_pct}% of weight live · dispersion ${d.confidence.dispersion}`;
  requestAnimationFrame(() =>
    requestAnimationFrame(() => { $("needle").style.left = d.score + "%"; }));
}

function statCell(k, v, sub, cls = "") {
  return `<div class="stat"><div class="k">${k}</div><div class="v ${cls}">${v}</div><div class="s">${sub}</div></div>`;
}

function renderStats(d) {
  const g = d.gold;
  const fv = d.fair_value;
  const fvTxt = fv.gap_pct === null ? "n/a" : (fv.gap_pct > 0 ? "+" : "") + fv.gap_pct + "%";
  $("stats").innerHTML =
    statCell("Gold USD", fmtUSD(g.usd), (g.usd_chg_1d_pct >= 0 ? "+" : "") + g.usd_chg_1d_pct + "% 1d",
             g.usd_chg_1d_pct >= 0 ? "up" : "down") +
    statCell("Gold GBP", fmtGBP(g.gbp), (g.gbp_chg_1d_pct >= 0 ? "+" : "") + g.gbp_chg_1d_pct + "% 1d",
             g.gbp_chg_1d_pct >= 0 ? "up" : "down") +
    statCell("Fair value gap", fvTxt, "vs macro model", fv.gap_pct > 5 ? "down" : fv.gap_pct < -5 ? "up" : "") +
    statCell("Regime", d.regime.name.split("/")[0].trim(), d.regime.name.includes("/") ? d.regime.name.split("/")[1].trim() : "") +
    statCell("Confidence", d.confidence.level, d.confidence.freshness_pct + "% weight live");
  $("regime-name").textContent = d.regime.name;
  $("regime-desc").textContent = d.regime.description;
}

function sparkSVG(points) {
  if (!points || points.length < 2) return "";
  const vs = points.map((p) => p[1]);
  const min = Math.min(...vs), max = Math.max(...vs), span = max - min || 1;
  const W = 300, H = 56, pad = 3;
  const xy = points.map((p, i) => {
    const x = pad + (i / (points.length - 1)) * (W - 2 * pad);
    const y = H - pad - ((p[1] - min) / span) * (H - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const last = xy[xy.length - 1].split(",");
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img">
    <polyline points="${xy.join(" ")}" fill="none" stroke="#8d968b" stroke-width="1.5"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="2.5" fill="#c9a227"/>
  </svg>`;
}

function renderSignals(d) {
  const el = $("signals");
  el.innerHTML = d.signals.map((s) => {
    const stale = s.stale;
    const score = s.score;
    const half = score === null ? 0 : Math.min(50, Math.abs(score) / 2 * 50);
    const fill = score === null ? "" :
      `<div class="fill ${score >= 0 ? "pos" : "neg"}" style="width:${half}%"></div>`;
    const scoreTxt = score === null ? "—" : (score > 0 ? "+" : "") + score.toFixed(1);
    const first = (s.spark && s.spark.length) ? s.spark[0][0] : null;
    return `<div class="signal ${stale ? "stale" : ""}" id="sig-${s.id}">
      <button class="signal-head" aria-expanded="false" data-id="${s.id}">
        <div class="sig-id">${s.id}</div>
        <div><div class="sig-name">${s.name}</div><div class="sig-value">${s.value} · weight ${s.eff_weight || s.weight}</div></div>
        <div class="scorebar">${fill}</div>
        <div class="sig-score ${score === null ? "" : score >= 0 ? "pos" : "neg"}">${scoreTxt}</div>
      </button>
      <div class="signal-body">
        <div class="sig-rationale">${s.rationale}</div>
        ${s.spark && s.spark.length ? `<div class="sig-spark">${sparkSVG(s.spark)}
          <div class="spark-caption">${s.name} — ${first} → ${s.spark[s.spark.length - 1][0]}</div></div>` : ""}
      </div>
    </div>`;
  }).join("");
  el.querySelectorAll(".signal-head").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = btn.parentElement;
      const open = row.classList.toggle("open");
      btn.setAttribute("aria-expanded", open);
    });
  });
}

function renderFlips(d) {
  $("flips").innerHTML = (d.change_my_mind || []).map((f) =>
    `<div class="flip-item"><div class="flip-id">${f.signal}</div><div>${f.text}</div></div>`
  ).join("") || `<div class="flip-item">No live signals near a flip.</div>`;
}

function renderGBP(d) {
  $("gbp-price").textContent = fmtGBP(d.gbp_lens.price) +
    "  ·  " + (d.gbp_lens.chg_3m_pct >= 0 ? "+" : "") + d.gbp_lens.chg_3m_pct + "% 3m";
  $("gbp-note").textContent = d.gbp_lens.note;
}

const SOURCE_LABELS = {
  gold_usd: "Gold spot (USD)", gold_gbp: "Gold spot (GBP)", silver: "Silver spot",
  dfii10: "10Y real yield (DFII10)", dgs10: "10Y nominal (DGS10)", dgs2: "2Y yield (DGS2)",
  t10yie: "10Y breakeven (T10YIE)", t5yifr: "5y5y inflation (T5YIFR)",
  dollar: "Broad dollar (DTWEXBGS)", vix: "VIX (VIXCLS)", baa10y: "Credit (BAA10Y)",
  cot: "COT managed money", gpr: "Geopolitical risk (GPR)",
  central_banks: "Central bank buying (manual)", etf_flows: "ETF flows (manual)",
};

function renderFreshness(d) {
  const rows = Object.entries(d.freshness).map(([k, f]) => {
    const label = SOURCE_LABELS[k] || k;
    const badge = f.stale ? ` <span class="badge-stale">STALE</span>` : "";
    return `<tr><td class="src">${label}${badge}</td><td>${f.provider}</td>
      <td class="age">${f.last_date || "—"} (${f.age_days}d)</td></tr>`;
  }).join("");
  $("freshness").innerHTML = `<table>${rows}</table>`;
  $("generated").textContent = (d.generated_at || "").replace("T", " ").slice(0, 16) + " UTC";
}

function renderChart(history, latest) {
  if (typeof Chart === "undefined") { $("chart-note").textContent = "Chart library offline — score history unavailable."; return; }
  const cutoff = new Date(Date.now() - 730 * 864e5).toISOString().slice(0, 10);
  const h = history.filter((r) => r.date >= cutoff);
  if (h.length < 2) { $("chart-note").textContent = "Score history builds up as the engine runs — check back after a few sessions."; }
  const css = getComputedStyle(document.documentElement);
  const gold = css.getPropertyValue("--gold").trim();
  const sage = css.getPropertyValue("--muted").trim();
  const faint = css.getPropertyValue("--faint").trim();
  new Chart($("chart"), {
    type: "line",
    data: {
      labels: h.map((r) => r.date),
      datasets: [
        { label: "Signal score", data: h.map((r) => r.score), yAxisID: "y",
          borderColor: gold, borderWidth: 2, pointRadius: 0, tension: 0.25 },
        { label: "Gold USD", data: h.map((r) => r.gold_usd), yAxisID: "y1",
          borderColor: sage, borderWidth: 1.2, pointRadius: 0, tension: 0.25 },
      ],
    },
    options: {
      maintainAspectRatio: false,
      animation: matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 500 },
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: sage, boxWidth: 14, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: faint, maxTicksLimit: 6, font: { size: 10 } }, grid: { display: false } },
        y: { min: 0, max: 100, ticks: { color: gold, font: { size: 10 } }, grid: { color: "#1c231d" } },
        y1: { position: "right", ticks: { color: sage, font: { size: 10 } }, grid: { display: false } },
      },
    },
  });
  const backfilled = h.some((r) => r.backfilled);
  if (h.length >= 2) $("chart-note").textContent =
    (backfilled ? "History before first live run is backfilled from the replay in scripts/backtest.py. " : "") +
    "Gold line: right axis. Score: left axis, bands at 28/43/58/72.";
}

(async function init() {
  try {
    const [latest, history] = await Promise.all([
      loadJSON("data/latest.json"),
      loadJSON("data/history.json").catch(() => []),
    ]);
    $("asof").textContent = "as of " + latest.as_of;
    renderGauge(latest);
    renderStats(latest);
    renderSignals(latest);
    renderFlips(latest);
    renderGBP(latest);
    renderFreshness(latest);
    const drawChart = () => renderChart(history, latest);
    if (typeof Chart === "undefined") window.addEventListener("load", drawChart); else drawChart();
  } catch (e) {
    document.querySelector("main").insertAdjacentHTML("afterbegin",
      `<div class="panel" style="color:var(--neg)">Failed to load data: ${e.message}</div>`);
  }
})();
