# Gold Signal Engine — 24.1/100 SELL/REDUCE

As of 2026-08-07 (generated 2026-08-09T08:30:01.217049Z).

- Gold: $4,399.70 USD / £3,152.65 GBP
- Regime: Rising real yields / strong dollar — The macro is leaning on gold from both sides. Momentum must be exceptional to overcome this drag.
- Data confidence: Med (94% of signal weight live). This measures input quality, not model validity.
- Fair value: Reference only: the 5y fair-value regression fails its sanity check (real-yield beta +0.28 is positive — the window co-trended), so the +16% gap does not adjust the score.
- Band meaning: Macro tailwinds absent — risk posture, not a sell-timing call.
- GBP lens: XAUGBP £3,153, -10.9% over 3m, downtrend vs 200DMA — sterling gold is trending down: if the USD verdict says add, the currency is eating the move — size down; if it says trim, GBP agrees.

## Signals (score -2 bearish to +2 bullish for gold)

- **A. Real yields** (weight 23.0): -1.59 — 10Y real yield 2.43%, +0.49pp over 3m — rising real yields are gold’s biggest headwind.
- **B. Dollar** (weight 17.25): -0.40 — Broad dollar 0.1% below its 200DMA, +0.9% over 3m — a firm dollar caps gold.
- **E. Trend & momentum** (weight 12.0): +0.38 — Price above the 50DMA, below the 200DMA (death cross in force), +7.2% over 20 sessions — the trend is doing the heavy lifting.
- **C. Policy trajectory** (weight 10.0): -1.45 — 2Y yield 4.25%, +0.38pp over 3m; 2Y 0.62pp above the funds rate (no cuts priced) — rate expectations are firming against gold.
- **D. Inflation expectations** (weight 8.0): -1.20 — 10Y breakevens 2.25% (-0.20pp 3m), 5y5y 2.28% (-0.01pp) — inflation expectations contained.
- **F. Positioning (COT)** (weight 8.0): -0.17 — Managed money net long 130,766 contracts, 71st percentile of 5y — mid-range — positioning is not the story right now.
- **G. Valuation stretch** (weight 8.0): +0.00 — -1.8% vs 200DMA, RSI(14) 74 — no stretch either way.
- **H. Fear & credit** (weight 6.0): +0.00 — VIX 15, BAA-10Y spread 1.61% (-0.05pp 3m) — no stress signal either way.
- **I. Geopolitics (GPR)** (weight 5.0): +0.18 — GPR index 153 vs 5y average 143 — geopolitical risk elevated.
- **M. Labour market** (weight 5.0): -0.81 — Initial claims 4-wk avg 198,750 (-2.1% vs 3m ago), unemployment 4.1% (-0.20pp 3m) — labour market strong — no pressure on the Fed to ease.
- **L. Gold/silver ratio** (weight 2.0): +0.00 — Gold/silver ratio 69 (12th pct of 5y) — ratio mid-range; no tell either way.
- **J. Central bank demand** (weight 0.0): excluded — Input unavailable (central_banks: stale, failed or placeholder) — excluded; weights renormalised.
- **K. ETF flows** (weight 0.0): excluded — Input unavailable (etf_flows: stale, failed or placeholder) — excluded; weights renormalised.

## What would change my mind

- **F**: Managed-money net longs crossing the 90th percentile of the 5y range flips positioning hard bearish (crowded).
- **I**: GPR crossing its 5y average (143) flips geopolitics bearish.

## Data freshness

- gold_usd: 2026-08-07 (2d old) via yahoo:GC=F
- gold_gbp: 2026-08-06 (3d old) via derived:GC=F/GBPUSD
- silver: 2026-08-07 (2d old) via yahoo:SI=F
- dfii10: 2026-08-06 (3d old) via fred-csv
- dgs10: 2026-08-06 (3d old) via fred-csv
- dgs2: 2026-08-06 (3d old) via fred-csv
- t10yie: 2026-08-07 (2d old) via fred-csv
- t5yifr: 2026-08-07 (2d old) via fred-csv
- dollar: 2026-07-31 (9d old) via fred-csv
- vix: 2026-08-06 (3d old) via fred-csv
- baa10y: 2026-08-06 (3d old) via fred-csv
- effr: 2026-08-06 (3d old) via fred-csv
- icsa: 2026-08-01 (8d old) via fred-csv
- unrate: 2026-07-01 (39d old) via fred-csv
- cot: 2026-08-04 (5d old) via cftc-socrata
- gpr: 2026-07-01 (39d old) via iacoviello-xls
- central_banks: 2026-07-30 (10d old) via manual (PLACEHOLDER — not scored) [EXCLUDED]
- etf_flows: 2026-07-30 (10d old) via manual (PLACEHOLDER — not scored) [EXCLUDED]

Machine-readable: data/latest.json · history: data/history.json · methodology: README.md
