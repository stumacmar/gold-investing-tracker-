# Gold Signal Engine

A regime-aware scoring model for gold. Twice a day it fetches the macro data that
actually drives the gold price, scores 12 signals, and publishes a **0–100 Gold
Signal Score** with a one-word verdict on a [GitHub Pages dashboard](docs/).
Every score is traceable to its inputs — no black boxes.

Gold has no earnings. It trades on **real yields, the dollar, policy
expectations, positioning, and fear**. The model is built around that fact: the
single largest weight is real yields, and a regime overlay decides which other
signals matter most right now.

## The verdict bands

| Score | Verdict | Meaning |
|---|---|---|
| ≥ 72 | **ACCUMULATE** | Add meaningfully. Macro tailwind + trend + room to run. |
| 58–71 | **ADD** | Scale in. The balance of evidence is bullish. |
| 43–57 | **HOLD** | Sit tight. Signals conflict or the edge is small. |
| 28–42 | **TRIM** | Reduce into strength. Headwinds outweigh tailwinds. |
| < 28 | **SELL/REDUCE** | The macro is against you and the tape agrees. |

Alongside the verdict the engine always reports:

- **Confidence** (High/Med/Low) — driven by data freshness (what fraction of
  signal weight is live) and signal agreement (weighted dispersion of the
  −2…+2 scores). A high score built on stale data or violently disagreeing
  signals is flagged, not hidden.
- **What would change my mind** — the two live signals closest to flipping,
  each with the exact threshold from today's numbers (e.g. "DFII10 above
  1.94% turns the 3-month real-yield trend positive and flips A bearish").
- **GBP lens** — the same verdict sanity-checked against the XAUGBP trend,
  because a sterling investor can be right on gold and still lose the move to
  the currency.

## The 12 signals

Each signal scores **−2 to +2** (positive = bullish for gold) with a
plain-English rationale generated from the actual numbers.

| # | Signal | Weight | What it measures |
|---|---|---|---|
| A | Real yields | 20 | Level and 3-month change of 10Y TIPS yield (`DFII10`). Falling/negative real yields are the single most important driver of gold. −0.5pp over 3m ⇒ +2; +0.5pp ⇒ −2; small bonus below 0%, penalty above 2%. |
| B | Dollar | 15 | Broad dollar (`DTWEXBGS`) vs its 200DMA plus 3-month momentum. A weakening dollar is bullish. |
| C | Policy trajectory | 10 | 3-month change in the 2Y yield (`DGS2`) as a proxy for rate expectations. Falling 2Y = easing being priced = bullish. |
| D | Inflation expectations | 8 | 3-month change in 10Y breakevens (`T10YIE`), with 5y5y (`T5YIFR`) as context. Breakevens rising **while real yields fall** earns a bonus — that combination is the strongest macro mix gold gets. |
| E | Trend & momentum | 12 | Price vs 50DMA and 200DMA, golden/death cross, and the 12-month return's percentile within 5 years of rolling 12-month returns. |
| F | Positioning (COT) | 8 | CFTC managed-money net longs in COMEX gold as a percentile of the 5y range. **Contrarian at extremes**: >90th percentile = crowded = bearish even in an uptrend; <10th = washed out = fuel for rallies. Mid-range ≈ neutral. |
| G | Valuation stretch | 8 | % deviation from the 200DMA and RSI(14). >15% above the 200DMA or RSI>75 draws an overbought penalty; deep oversold earns a bonus. |
| H | Fear & credit | 6 | VIX regime (`VIXCLS`) and 3-month widening of the BAA-Treasury spread (`BAA10Y`). Stress = safe-haven bid. |
| I | Geopolitics | 5 | Iacoviello GPR index vs its 5-year average. |
| J | Central bank demand | 4 | **Manual, quarterly** (from WGC): last 4 quarters of official-sector net purchases vs the 5y average annual pace. |
| K | ETF flows | 2 | **Manual, quarterly**: 3-month global gold-ETF net flows — Western participation confirming or diverging from price. |
| L | Gold/silver ratio | 2 | Extreme ratio percentiles as a risk-appetite tell. Silver confirming (low/falling ratio) is healthy; silver absent at the highs is a tired-rally warning. |

**Fair-value anchor.** A rolling 5-year regression of ln(gold) on the 10Y real
yield and ln(broad dollar). The residual — "gold is trading X% above/below its
macro fair value" — is a headline stat and modifies the composite by up to ±5
points (rich to the model subtracts, cheap adds).

## Regime overlay

Before final weighting the engine classifies the macro regime and re-weights:

1. **Disinflationary easing** — real yields falling, dollar soft. The best
   regime gold gets: A, B and trend (E) are upweighted.
2. **Reflation** — breakevens rising faster than nominal yields. Bullish;
   inflation signal (D) weight ×1.5.
3. **Rising real yields / strong dollar** — hostile. A and B upweighted, so
   momentum must be exceptional to overcome the macro drag.
4. **Crisis / risk-off** — VIX > 30 or credit spreads spiking. Fear (H) and
   geopolitics (I) dominate; positioning and trend downweighted. Remember 2008
   and March 2020: gold can dip first on forced liquidation before the
   safe-haven bid takes over.

## Composite

Weighted average of live signal scores (−2…+2), rescaled to 0–100, plus the
fair-value modifier. If a series is stale or a fetch fails, that signal is
**excluded and the remaining weights renormalise** — the dashboard shows it
greyed out with "data stale". The engine never silently scores on dead data.

## Honesty check (backtest)

`scripts/backtest.py` replays the scoring weekly over ~5 years of history
(J and K excluded — manual inputs have no history) and prints forward 3-month
gold returns by verdict band, plus the Spearman rank correlation between score
and forward return.

Current result (2021-08 → 2026-05, 240 weekly observations): the top of the
scale orders correctly — ACCUMULATE +14.0% avg forward 3m, ADD +7.1%, HOLD
+4.3% — but TRIM (+3.3%) and SELL/REDUCE (+5.8%) were **not** followed by
negative returns, and the overall rank correlation is only +0.10. Plainly: in
the 2024–26 central-bank-driven bull, gold kept rising through macro-hostile
readings that this model scores bearishly. Treat low-band verdicts as "the
usual macro tailwinds are absent", not as a short signal, and treat the engine
as a risk framework, not a crystal ball.

Re-run it any time: `python scripts/fetch_and_score.py && python scripts/backtest.py`.
Score history on the dashboard chart before the first live run is backfilled
from this replay (`--write-history`), so you can see where the engine would
have called past turns.

## Architecture

```
.github/workflows/update-data.yml   cron 07:00 & 21:00 UTC weekdays + manual dispatch
scripts/fetch_and_score.py          fetch -> score -> data/latest.json + history.json
scripts/backtest.py                 weekly replay + band-by-band honesty table
data/                               latest.json, history.json, series_cache.json,
                                    manual_inputs.json, gpr_cache.json
docs/                               static dashboard (GitHub Pages), reads docs/data/
```

- Static site, no server. The Action commits refreshed JSON back to the repo;
  the dashboard is pure HTML/CSS/JS (Chart.js from CDN) and works offline once
  loaded (service worker).
- JSON is mirrored into `docs/data/` because Pages serves only `/docs`.

### Data sources (all free)

| Series | Source | Fallback |
|---|---|---|
| Gold, silver, XAUGBP | Stooq CSV | Yahoo Finance (`GC=F`, `SI=F`, derived GBP via `GBPUSD=X`) |
| DFII10, DGS10, DGS2, T10YIE, T5YIFR, DTWEXBGS, VIXCLS, BAA10Y | FRED API (`FRED_API_KEY` secret) | FRED keyless CSV endpoint |
| COT managed money (gold) | CFTC Socrata API (disaggregated futures-only) | — |
| Geopolitical Risk index | matteoiacoviello.com xls | last good copy cached in `data/gpr_cache.json` |
| Central bank buying, ETF flows | `data/manual_inputs.json`, updated quarterly by hand from WGC | staleness-dated |

Every fetch has retry with backoff and a per-series freshness stamp, shown in
the dashboard footer.

## Setup

1. **FRED API key** (optional but recommended): create a free key at
   fred.stlouisfed.org and add it as a repo secret named `FRED_API_KEY`.
   Without it the engine falls back to FRED's keyless CSV endpoint.
2. **GitHub Pages**: Settings → Pages → deploy from branch, folder `/docs`.
3. **Manual inputs**: update `data/manual_inputs.json` quarterly from the World
   Gold Council's Gold Demand Trends (fields documented in the file). If you
   let it go stale the J/K signals grey out and the rest of the model carries on.
4. Run the workflow once by hand (Actions → "Update gold signal data" → Run
   workflow) to generate the first live data point.

Nothing here is investment advice — it's a disciplined way of looking at the
same dashboard of drivers before acting.
