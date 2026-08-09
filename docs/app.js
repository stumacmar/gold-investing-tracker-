/* Gold Signal Engine dashboard. Reads data/latest.json + data/history.json. */

const $ = (id) => document.getElementById(id);

const fmtUSD = (v) => "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });
const fmtGBP = (v) => v == null ? "—" : "£" + v.toLocaleString("en-GB", { maximumFractionDigits: 0 });

// All strings from the JSON pass through here before hitting innerHTML.
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

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
  $("band-note").textContent = d.band_note || "";
  const vn = $("vol-note");
  if (vn) vn.textContent = d.volatility ? d.volatility.note : "";
  $("confidence").textContent =
    `Data confidence ${d.confidence.level} · ${d.confidence.freshness_pct}% of weight live`;
  const live = d.signals.filter((s) => !s.stale && s.score !== null);
  const top = live.slice().sort((a, b) =>
    Math.abs(b.score * b.eff_weight) - Math.abs(a.score * a.eff_weight)).slice(0, 2);
  $("drivers").innerHTML = top.length
    ? "Driven by " + top.map((s) =>
        `<b>${esc(s.name)}</b> (${s.score > 0 ? "+" : ""}${s.score.toFixed(1)} × w${s.eff_weight})`).join(" and ")
    : "";
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
    statCell("Gold GBP", fmtGBP(g.gbp), g.gbp_chg_1d_pct == null ? "n/a" :
             (g.gbp_chg_1d_pct >= 0 ? "+" : "") + g.gbp_chg_1d_pct + "% 1d",
             (g.gbp_chg_1d_pct ?? 0) >= 0 ? "up" : "down") +
    statCell("Fair value gap", fvTxt, fv.applied ? "vs macro model" : "reference only — not applied",
             fv.applied ? (fv.gap_pct > 5 ? "down" : fv.gap_pct < -5 ? "up" : "") : "") +
    statCell("Regime", esc(d.regime.name.split("/")[0].trim()),
             d.regime.name.includes("/") ? esc(d.regime.name.split("/")[1].trim()) : "") +
    statCell("Data confidence", esc(d.confidence.level), d.confidence.freshness_pct + "% weight live") +
    (d.volatility ? statCell(esc(d.volatility.label),
        "$" + Math.round(d.volatility.atr_abs).toLocaleString("en-US") + "/day",
        esc(d.volatility.percentile_5y + "th pct · " + d.volatility.regime),
        d.volatility.percentile_5y >= 90 ? "down" : "") : "");
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
    const weightTxt = stale ? "excluded" : "weight " + (s.eff_weight ?? s.weight);
    return `<div class="signal ${stale ? "stale" : ""}" id="sig-${esc(s.id)}">
      <button class="signal-head" aria-expanded="false" data-id="${esc(s.id)}">
        <div class="sig-id">${esc(s.id)}</div>
        <div><div class="sig-name">${esc(s.name)}</div><div class="sig-value">${esc(s.value)} · ${weightTxt}</div></div>
        <div class="scorebar">${fill}</div>
        <div class="sig-score ${score === null ? "" : score >= 0 ? "pos" : "neg"}">${scoreTxt}</div>
      </button>
      <div class="signal-body">
        <div class="sig-rationale">${esc(s.rationale)}</div>
        ${s.spark && s.spark.length ? `<div class="sig-spark">${sparkSVG(s.spark)}
          <div class="spark-caption">${esc(s.name)} — ${esc(first)} → ${esc(s.spark[s.spark.length - 1][0])}</div></div>` : ""}
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
    `<div class="flip-item"><div class="flip-id">${esc(f.signal)}</div><div>${esc(f.text)}</div></div>`
  ).join("") || `<div class="flip-item">No live signals near a flip.</div>`;
}

function renderGBP(d) {
  $("gbp-price").textContent = d.gbp_lens.price == null ? "—" : fmtGBP(d.gbp_lens.price) +
    "  ·  " + (d.gbp_lens.chg_3m_pct >= 0 ? "+" : "") + d.gbp_lens.chg_3m_pct + "% 3m";
  $("gbp-note").textContent = d.gbp_lens.note;
}

const SOURCE_LABELS = {
  gold_usd: "Gold spot (USD)", gold_gbp: "Gold spot (GBP)", silver: "Silver spot",
  dfii10: "10Y real yield (DFII10)", dgs10: "10Y nominal (DGS10)", dgs2: "2Y yield (DGS2)",
  t10yie: "10Y breakeven (T10YIE)", t5yifr: "5y5y inflation (T5YIFR)",
  dollar: "Broad dollar (DTWEXBGS)", vix: "VIX (VIXCLS)", baa10y: "Credit (BAA10Y)",
  effr: "Fed funds rate (EFFR)", icsa: "Initial claims (ICSA)", unrate: "Unemployment (UNRATE)", payems: "Nonfarm payrolls (PAYEMS)", usdjpy: "USDJPY (FX stress)",
  cot: "COT managed money", gpr: "Geopolitical risk (GPR)",
  central_banks: "Central bank buying (manual)", etf_flows: "ETF flows (manual)",
};

function renderFreshness(d) {
  const bad = Object.entries(d.freshness).filter(([, f]) => !f.ok || f.stale);
  $("fresh-banner").innerHTML = bad.length
    ? `⚠ ${bad.length} source${bad.length > 1 ? "s" : ""} excluded this run: ` +
      bad.map(([k]) => esc(SOURCE_LABELS[k] || k)).join(", ") +
      " — score computed without them, weights renormalised."
    : "";
  const rows = Object.entries(d.freshness).map(([k, f]) => {
    const label = SOURCE_LABELS[k] || k;
    const badge = !f.ok ? ` <span class="badge-stale">FAILED</span>`
                : f.stale ? ` <span class="badge-stale">STALE</span>` : "";
    return `<tr><td class="src">${esc(label)}${badge}</td><td>${esc(f.provider)}</td>
      <td class="age">${esc(f.last_date) || "—"} (${f.age_days}d)</td></tr>`;
  }).join("");
  $("freshness").innerHTML = `<table>${rows}</table>`;
  $("generated").textContent = (d.generated_at || "").replace("T", " ").slice(0, 16) + " UTC";
}


// ---- Price structure: support/resistance lines + consolidation band drawn on canvas.
// Chart.js has no annotation support without a plugin, so this draws them directly.
const structurePlugin = {
  id: "structure",
  beforeDatasetsDraw(chart, args, opts) {
    const s = opts && opts.structure;
    if (!s) return;
    const { ctx, chartArea: area, scales: { y } } = chart;
    const css = getComputedStyle(document.documentElement);
    const gold = css.getPropertyValue("--gold").trim();
    const neg = css.getPropertyValue("--neg").trim();
    const pos = css.getPropertyValue("--pos").trim();
    ctx.save();
    if (s.range) {
      const yTop = y.getPixelForValue(s.range.high);
      const yBot = y.getPixelForValue(s.range.low);
      ctx.fillStyle = "rgba(201,162,39,0.10)";
      ctx.fillRect(area.left, yTop, area.right - area.left, yBot - yTop);
      ctx.strokeStyle = "rgba(201,162,39,0.45)";
      ctx.setLineDash([4, 3]); ctx.lineWidth = 1;
      ctx.strokeRect(area.left, yTop, area.right - area.left, yBot - yTop);
      ctx.setLineDash([]);
      ctx.fillStyle = gold; ctx.font = "10px system-ui"; ctx.textAlign = "right";
      ctx.fillText(`${s.range.pct_of_time}% of the year`, area.right - 4, yTop - 3);
      ctx.textAlign = "left";
    }
    let lastLabelY = null;
    (s.levels || []).forEach((l) => {
      const py = y.getPixelForValue(l.price);
      if (py < area.top || py > area.bottom) return;
      ctx.strokeStyle = l.type === "resistance" ? neg : pos;
      ctx.globalAlpha = Math.min(0.85, 0.4 + 0.15 * l.touches);
      ctx.lineWidth = 1.2; ctx.setLineDash([6, 4]);
      ctx.beginPath(); ctx.moveTo(area.left, py); ctx.lineTo(area.right, py); ctx.stroke();
      ctx.setLineDash([]); ctx.globalAlpha = 1;
      ctx.fillStyle = l.type === "resistance" ? neg : pos;
      ctx.font = "10px system-ui";
      // Left-aligned inside the plot so labels never clip on narrow phones; nudge down
      // when two levels sit close enough for their labels to collide.
      let ly = py - 3;
      if (lastLabelY !== null && Math.abs(ly - lastLabelY) < 11) ly = lastLabelY + 11;
      lastLabelY = ly;
      ctx.fillText(`$${Math.round(l.price).toLocaleString("en-US")} · ${l.touches}x`, area.left + 5, ly);
    });
    ctx.restore();
  },
};

function renderStructure(latest, prices) {
  const s = latest.price_structure;
  if (!s) return;
  $("struct-note").textContent = s.note;
  $("struct-levels").innerHTML = (s.levels || []).map((l) =>
    `<div class="lvl ${l.type === "resistance" ? "res" : "sup"}">
       <div class="p">$${Math.round(l.price).toLocaleString("en-US")}</div>
       <div class="t">${esc(l.type)} · tested ${l.touches}x · last ${esc(l.last_touch)}</div>
       <div class="d">${l.distance_pct > 0 ? "+" : ""}${l.distance_pct}%</div>
     </div>`).join("");
  if (typeof Chart === "undefined" || !prices || !prices.dates) return;
  const css = getComputedStyle(document.documentElement);
  const goldC = css.getPropertyValue("--gold").trim();
  const faint = css.getPropertyValue("--faint").trim();
  new Chart($("structure-chart"), {
    type: "line",
    data: {
      labels: prices.dates,
      datasets: [{ label: "Gold USD", data: prices.close, borderColor: goldC,
                   borderWidth: 1.6, pointRadius: 0, tension: 0.15 }],
    },
    options: {
      maintainAspectRatio: false,
      animation: matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 500 },
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false }, structure: { structure: s } },
      scales: {
        x: { ticks: { color: faint, maxTicksLimit: 6, font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: faint, font: { size: 10 } }, grid: { color: "#1c231d" } },
      },
    },
    plugins: [structurePlugin],
  });
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
  // Backfilled (replayed) score history draws dashed so it can't be mistaken for live calls.
  const dashSeg = { borderDash: (ctx) =>
    (h[ctx.p0DataIndex]?.backfilled || h[ctx.p1DataIndex]?.backfilled) ? [4, 4] : undefined };
  new Chart($("chart"), {
    type: "line",
    data: {
      labels: h.map((r) => r.date),
      datasets: [
        { label: "Signal score", data: h.map((r) => r.score), yAxisID: "y",
          borderColor: gold, borderWidth: 2, pointRadius: 0, tension: 0.25, segment: dashSeg },
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
    (backfilled ? "Dashed score = backfilled from the replay in scripts/backtest.py, NOT live calls. " : "") +
    "Gold line: right axis. Score: left axis, bands at 28/43/58/72.";
}

(async function init() {
  try {
    const [latest, history, prices] = await Promise.all([
      loadJSON("data/latest.json"),
      loadJSON("data/history.json").catch(() => []),
      loadJSON("data/prices.json").catch(() => null),
    ]);
    $("asof").textContent = "as of " + latest.as_of;
    renderGauge(latest);
    renderStats(latest);
    renderSignals(latest);
    renderFlips(latest);
    renderGBP(latest);
    renderFreshness(latest);
    const drawChart = () => { renderChart(history, latest); renderStructure(latest, prices); };
    // Render immediately; renderChart/renderStructure degrade gracefully when Chart.js
    // is missing. (A "load" listener added after load has already fired never runs.)
    drawChart();
    if (typeof Chart === "undefined") window.addEventListener("load", drawChart, { once: true });
  } catch (e) {
    document.querySelector("main").insertAdjacentHTML("afterbegin",
      `<div class="panel" style="color:var(--neg)">Failed to load data: ${e.message}</div>`);
  }
})();
