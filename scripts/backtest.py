#!/usr/bin/env python3
"""Honesty check: replay the scoring engine over ~5y of history (weekly steps) and
print band-by-band forward 3-month gold returns. The engine is only worth trusting
if high bands led to better forward returns than low bands.

Uses data/series_cache.json written by fetch_and_score.py (run that first).
Signals J (central banks) and K (ETF flows) are manual inputs with no history, so
they are excluded and weights renormalise — exactly what the live engine does when
a series is stale. COT and GPR percentile windows are shorter at the start of the
replay (less lookback exists in the cache); treat the earliest scores as softer.
Note: GPR is monthly and published with a lag, so the replay sees each month's
value ~immediately — a mild lookahead on a 5-weight signal.

Usage:
  python scripts/backtest.py                 # print the honesty table
  python scripts/backtest.py --write-history # also seed data/history.json with
                                             # replayed weekly scores (marked
                                             # "backfilled"; live rows always win)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_and_score as eng  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

eng.warn = lambda msg: None  # replay would otherwise spam J/K-excluded warnings


def load_cache():
    path = os.path.join(DATA_DIR, "series_cache.json")
    if not os.path.exists(path):
        sys.exit("data/series_cache.json not found — run scripts/fetch_and_score.py first.")
    with open(path) as f:
        raw = json.load(f)
    return {k: eng.Series(v["dates"], v["values"]) for k, v in raw.items()}


def fake_freshness(bundle):
    """Every cached series is 'live' at replay time; manual inputs are excluded."""
    fresh = {k: {"ok": True, "stale": False} for k in bundle}
    fresh["central_banks"] = {"ok": False, "stale": True}
    fresh["etf_flows"] = {"ok": False, "stale": True}
    return fresh


MANUAL_NEUTRAL = {
    "central_banks": {"last_updated": "1970-01-01", "recent_4q_tonnes": 0, "five_year_avg_annual_tonnes": 1},
    "etf_flows": {"last_updated": "1970-01-01", "last_3m_net_tonnes": 0},
}

CORE = ["gold_usd", "dfii10", "dgs10", "dgs2", "t10yie", "t5yifr",
        "dollar", "vix", "baa10y", "silver", "cot", "gpr"]


def score_asof(cache, date):
    d = {k: s.asof(date) for k, s in cache.items()}
    for k in CORE:
        if len(d.get(k, [])) < (30 if k in ("gpr", "cot") else 300):
            return None
    signals = eng.compute_signals(d, fake_freshness(d), MANUAL_NEUTRAL)
    regime_key, regime_name, _ = eng.classify_regime(d)
    try:
        fv_gap = eng.fair_value_gap(d["gold_usd"], d["dfii10"], d["dollar"])
    except Exception:  # noqa: BLE001
        fv_gap = None
    score, *_ = eng.compute_composite(signals, regime_key, fv_gap)
    return round(score, 1), eng.verdict_for(score), regime_key


def main():
    write_history = "--write-history" in sys.argv
    cache = load_cache()
    gold = cache["gold_usd"]

    # Weekly replay dates over the last ~5 years, leaving 63 trading days of forward data
    n = len(gold)
    start_i = max(300, n - 1260)
    replay_idx = list(range(start_i, n - 63, 5))

    rows = []
    for i in replay_idx:
        date = gold.dates[i]
        res = score_asof(cache, date)
        if res is None:
            continue
        score, verdict, regime = res
        fwd = gold.values[i + 63] / gold.values[i] - 1.0
        rows.append({"date": date, "score": score, "verdict": verdict,
                     "regime": regime, "gold_usd": round(gold.values[i], 2), "fwd_3m": fwd})
    if not rows:
        sys.exit("No replayable dates — cache too short.")

    print(f"Replayed {len(rows)} weekly dates: {rows[0]['date']} → {rows[-1]['date']}")
    print(f"(J/K excluded — no manual history. Early COT/GPR percentiles use shorter lookback.)\n")

    order = ["ACCUMULATE", "ADD", "HOLD", "TRIM", "SELL/REDUCE"]
    print(f"{'BAND':<12} {'N':>4} {'AVG 3M FWD':>11} {'MEDIAN':>8} {'% POSITIVE':>11}")
    print("-" * 50)
    for band in order:
        sel = [r["fwd_3m"] for r in rows if r["verdict"] == band]
        if not sel:
            print(f"{band:<12} {0:>4} {'—':>11} {'—':>8} {'—':>11}")
            continue
        sel.sort()
        avg = sum(sel) / len(sel)
        med = sel[len(sel) // 2]
        pos = 100 * sum(1 for x in sel if x > 0) / len(sel)
        print(f"{band:<12} {len(sel):>4} {avg:>+10.1%} {med:>+7.1%} {pos:>10.0f}%")

    all_fwd = sorted(r["fwd_3m"] for r in rows)
    print("-" * 50)
    print(f"{'ALL':<12} {len(all_fwd):>4} {sum(all_fwd)/len(all_fwd):>+10.1%} "
          f"{all_fwd[len(all_fwd)//2]:>+7.1%} "
          f"{100*sum(1 for x in all_fwd if x>0)/len(all_fwd):>10.0f}%")

    # Rank correlation between score and forward return (Spearman via rank differences)
    def ranks(xs):
        order_i = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0] * len(xs)
        for rank, i in enumerate(order_i):
            r[i] = rank
        return r
    rs, rf = ranks([r["score"] for r in rows]), ranks([r["fwd_3m"] for r in rows])
    m = len(rows)
    rho = 1 - 6 * sum((a - b) ** 2 for a, b in zip(rs, rf)) / (m * (m * m - 1))
    print(f"\nSpearman rank correlation (score vs fwd 3m return): {rho:+.2f}")
    if rho < 0.05:
        print("Read that honestly: over this window the score had little-to-no predictive "
              "edge on 3-month horizons. Treat the engine as a risk framework, not a crystal ball.")

    if write_history:
        hist_path = os.path.join(DATA_DIR, "history.json")
        existing = []
        if os.path.exists(hist_path):
            with open(hist_path) as f:
                existing = json.load(f)
        live_dates = {h["date"] for h in existing if not h.get("backfilled")}
        merged = {h["date"]: h for h in existing}
        for r in rows:
            if r["date"] in live_dates:
                continue
            gbp = cache.get("gold_gbp")
            gbp_v = gbp.asof(r["date"]).last if gbp and len(gbp.asof(r["date"])) else None
            merged[r["date"]] = {"date": r["date"], "score": r["score"], "verdict": r["verdict"],
                                 "gold_usd": r["gold_usd"],
                                 "gold_gbp": round(gbp_v, 2) if gbp_v else None,
                                 "regime": r["regime"], "backfilled": True}
        out = sorted(merged.values(), key=lambda h: h["date"])
        with open(hist_path, "w") as f:
            json.dump(out, f, indent=0)
        docs_copy = os.path.join(ROOT, "docs", "data", "history.json")
        with open(docs_copy, "w") as f:
            json.dump(out, f, indent=0)
        print(f"\nWrote {len(out)} rows to data/history.json (+ docs/data mirror), "
              f"{sum(1 for h in out if h.get('backfilled'))} backfilled.")


if __name__ == "__main__":
    main()
