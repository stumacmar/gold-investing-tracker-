# Gold Signal Engine — 30.1/100 TRIM

As of 2026-08-14 (generated 2026-08-14T21:04:44.944778Z).

- Gold: $4,430.90 USD / £3,273.46 GBP
- Regime: Rising real yields / strong dollar — The macro is leaning on gold from both sides. Momentum must be exceptional to overcome this drag.
- Data confidence: Med (95% of signal weight live). This measures input quality, not model validity.
- Fair value: Reference only: the 5y fair-value regression fails its sanity check (real-yield beta +0.28 is positive — the window co-trended), so the +22% gap does not adjust the score.
- Band meaning: Macro tailwinds absent — risk posture, not a sell-timing call.
- GBP lens: XAUGBP £3,273, -6.3% over 3m, downtrend vs 200DMA — sterling gold is trending down: if the USD verdict says add, the currency is eating the move — size down; if it says trim, GBP agrees.
- Volatility (true ATR(14) from Yahoo GC=F OHLC): Gold is moving about $76 a day (1.7% of price) — the 84th percentile of the last five years. Moves are running 1.5× normal; trim position sizes accordingly.
- Price structure: Gold $4,431: next resistance $5,306 (+19.8%, tested 2x); nearest support $3,967 (-10.5%, tested 2x). It has spent 24% of the past year between $3,945 and $4,145 — price is above it.

## Signals (score -2 bearish to +2 bullish for gold)

- **A. Real yields** (weight 23.0): -1.39 — 10Y real yield 2.39%, +0.40pp over 3m — rising real yields are gold’s biggest headwind.
- **B. Dollar** (weight 17.25): -0.07 — Broad dollar 0.6% below its 200DMA, +0.9% over 3m — a firm dollar caps gold.
- **E. Trend & momentum** (weight 12.0): +0.43 — Price above the 50DMA, below the 200DMA (death cross in force), +10.4% over 20 sessions — the trend is doing the heavy lifting.
- **C. Policy trajectory** (weight 10.0): -0.98 — 2Y yield 4.15%, +0.17pp over 3m; 2Y 0.52pp above the funds rate (no cuts priced) — rate expectations are firming against gold.
- **D. Inflation expectations** (weight 8.0): -1.38 — 10Y breakevens 2.24% (-0.23pp 3m), 5y5y 2.30% (+0.03pp) — inflation expectations contained.
- **F. Positioning (COT)** (weight 8.0): -0.20 — Managed money net long 137,662 contracts, 75th percentile of 5y — mid-range — positioning is not the story right now.
- **G. Valuation stretch** (weight 8.0): -0.75 — -1.2% vs 200DMA, RSI(14) 77 — stretched — chasing here is paying up for someone else's exit.
- **H. Fear & credit** (weight 6.0): -0.25 — VIX 15, BAA-10Y spread 1.67% (+0.01pp 3m) — markets are calm; no safe-haven bid.
- **M. Labour market** (weight 6.0): +0.39 — Payrolls -23k last month, +20k 3m average vs the ~100k breakeven; claims 4-wk avg 199,000 (-2.5% vs 3m ago); unemployment 4.1% (-0.20pp 3m) — labour softening at the edges.
- **I. Geopolitics (GPR)** (weight 5.0): +0.18 — GPR index 153 vs 5y average 143 — geopolitical risk elevated.
- **N. FX stress (yen)** (weight 4.0): +0.12 — USDJPY 159.3, +0.7% vs 200DMA; no intervention footprint — no FX stress signal.
- **L. Gold/silver ratio** (weight 2.0): +0.00 — Gold/silver ratio 68 (11th pct of 5y) — ratio mid-range; no tell either way.
- **J. Central bank demand** (weight 0.0): excluded — Input unavailable (central_banks: stale, failed or placeholder) — excluded; weights renormalised.
- **K. ETF flows** (weight 0.0): excluded — Input unavailable (etf_flows: stale, failed or placeholder) — excluded; weights renormalised.

## What would change my mind

- **B**: Broad dollar index crossing its 200DMA at 119.7 (above it now flips B bearish).
- **N**: USDJPY back below its 200DMA (158.2) removes the FX-stress support; a fresh >1.5% one-day yen surge re-fires it.

## Data freshness

- gold_usd: 2026-08-14 (0d old) via yahoo:GC=F
- gold_gbp: 2026-08-14 (0d old) via derived:GC=F/GBPUSD
- silver: 2026-08-14 (0d old) via yahoo:SI=F
- usdjpy: 2026-08-14 (0d old) via yahoo:JPY=X
- dfii10: 2026-08-13 (1d old) via fred-csv
- dgs10: 2026-08-13 (1d old) via fred-csv
- dgs2: 2026-08-13 (1d old) via fred-csv
- t10yie: 2026-08-13 (1d old) via fred-csv
- t5yifr: 2026-08-14 (0d old) via fred-csv
- dollar: 2026-08-07 (7d old) via fred-csv
- vix: 2026-08-13 (1d old) via fred-csv
- baa10y: 2026-08-13 (1d old) via fred-csv
- effr: 2026-08-13 (1d old) via fred-csv
- icsa: 2026-08-08 (6d old) via fred-csv
- unrate: 2026-07-01 (44d old) via fred-csv
- payems: 2026-07-01 (44d old) via fred-csv
- cot: 2026-08-11 (3d old) via cftc-socrata
- gpr: 2026-07-01 (44d old) via iacoviello-xls
- central_banks: 2026-07-30 (15d old) via manual (PLACEHOLDER — not scored) [EXCLUDED]
- etf_flows: 2026-07-30 (15d old) via manual (PLACEHOLDER — not scored) [EXCLUDED]

## Jargon, in plain English

- **The score** — All 14 signals squashed into one number from 0 to 100. Higher means more of the things that usually push gold up are happening right now. It's a summary, not a prediction. 30 doesn't mean gold will fall — it means the usual reasons to buy aren't there.
- **Real yield** — The interest a safe US government bond pays you after you take inflation off. If a bond pays 4% and prices rise 2%, your real yield is 2%. Gold pays you nothing at all. When bonds pay a good real return, people would rather own bonds. When real yields fall, gold gets more attractive. This is the single biggest driver.
- **The dollar index** — A measure of how strong the US dollar is compared with a basket of other currencies. Gold is priced in dollars. A stronger dollar usually means a lower gold price, because it takes fewer dollars to buy the same ounce.
- **2-year yield & Fed funds** — The 2-year yield shows what traders think US interest rates will average over the next couple of years. The Fed funds rate is what the US central bank charges today. If the 2-year sits below Fed funds, the market is betting on rate cuts — which is good for gold. Above it means no cuts expected.
- **Inflation expectations** — What the bond market thinks inflation will average in future. Worked out by comparing normal bonds with inflation-protected ones. Gold is bought as protection against money losing value. Rising inflation expectations usually help it.
- **Moving averages** — The average closing price over the last 50 days, or the last 200 days. It smooths out the daily noise so you can see the direction. Price above both averages means an uptrend. A 'golden cross' is when the 50-day rises above the 200-day (good sign); a 'death cross' is the opposite.
- **Positioning (COT)** — A weekly US government report showing how much big speculative funds are betting on gold going up. If almost everyone is already betting gold rises, there's nobody left to buy — and any bad news makes them all sell at once. Very low bets mean lots of buying power in reserve.
- **Stretch & RSI** — How far price has run above its 200-day average, plus RSI — a 0-to-100 speedometer of how fast it has moved recently. Above 70 on RSI means gold has risen very quickly and may need a rest. Below 30 means it has fallen very quickly and may bounce.
- **VIX & credit spreads** — VIX is the stock market's 'fear gauge' — how much turbulence investors expect. Credit spreads are the extra interest riskier companies must pay compared with the government. When both rise, investors are scared and look for somewhere safe. Gold is the classic hiding place.
- **Geopolitical risk** — An index that counts how often the world's newspapers mention war, terrorism and international conflict. A scarier world usually puts a floor under the gold price.
- **Central bank demand** — How much gold the world's central banks — the institutions that run each country's money — are buying. They have been the biggest buyers in recent years. Unlike traders, they buy for decades and rarely sell.
- **ETF flows** — Money moving in or out of funds that hold gold on investors' behalf, so people can own gold without storing it. Shows whether ordinary Western investors are joining in or heading for the exit.
- **Gold/silver ratio** — How many ounces of silver you could buy with one ounce of gold. Silver is the more excitable metal. When it keeps up with gold, the rally is broad and healthy. When gold rises alone, the move can be running out of steam.
- **Jobs data** — Nonfarm payrolls is the monthly count of how many jobs the US added or lost. Jobless claims count how many people asked for unemployment help last week. A weakening job market is what usually forces the central bank to cut interest rates — and rate cuts are gold's best friend.
- **FX stress & intervention** — When a country's currency falls too far, its government can step in and buy it back to prop it up. That's an intervention. Japan doing this means selling US government bonds to raise the money, which strains the whole financial system — and money moves toward gold.
- **Fair value gap** — Our estimate of what gold 'should' cost based only on interest rates and the dollar, compared with what it actually costs. A big gap means something else is driving the price. Right now the estimate fails its own reliability check, so we show it but don't use it.
- **Regime** — What kind of market we're in right now — calm, panicking, inflation-driven, and so on. The same signal matters more in some conditions than others, so the engine changes how much weight it gives each one depending on the regime.
- **Data confidence** — Whether today's numbers all arrived fresh and on time, and whether the signals agree with each other. Important: this is about the quality of the DATA, not whether the model is right. A high score built on stale data would be flagged here.
- **ATR (daily range)** — How many dollars gold moves in a typical day. It doesn't tell you to buy or sell. It tells you how big a position should be — in a jumpy market the same position risks a lot more money.
- **Support** — A price where gold has stopped falling before, more than once. Buyers showed up there. It's a rough guide to where the next floor might be, not a guarantee.
- **Resistance** — A price where gold has stopped rising before, more than once. Sellers showed up there. It's a rough guide to where the next ceiling might be, not a guarantee.
- **Consolidation range** — The price zone where gold has spent most of its time over the past year. Think of it as the room gold keeps coming back to. Being above or below it tells you whether something has changed.
- **Backfilled (dashed line)** — Scores worked out afterwards by replaying old data through today's model. These are NOT calls the engine made at the time — nobody was watching. They're a rough check of whether the model would have been sensible.

Machine-readable: data/latest.json · history: data/history.json · methodology: README.md
