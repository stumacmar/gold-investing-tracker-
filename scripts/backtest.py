#!/usr/bin/env python3
"""Honesty check: replay the scoring engine over ~5y of history (weekly steps) and
print band-by-band forward 3-month gold returns. The engine is only worth trusting
if high bands led to better forward returns than low bands.

Uses data/series_cache.json written by fetch_and_score.py (run that first).

Honesty measures baked in:
- Publication lags are applied so the replay only sees data when it was actually
  available: COT report dates shifted +3 calendar days (CFTC publishes Friday for
  Tuesday positions), GPR +32 days (monthly index published the following month),
  broad dollar +7 days (Fed publishes DTWEXBGS with ~1 week lag).
- Signals J (central banks) and K (ETF flows) are manual inputs with no history, so
  they are excluded and weights renormalise — the live engine does the same while
  manual_inputs.json carries placeholder values, so replay and live configurations
  match.
- Weekly samples of 63-day forward returns overlap ~92%; the effective number of
  independent observations is printed, and a non-overlapping subsample Spearman is
  reported alongside the full-sample one. Bands with N<20 are flagged.
- COT and GPR percentile windows are shorter at the start of the replay (less
  lookback exists in the cache); treat the earliest scores as softer.

Usage:
  python scripts/backtest.py                 # print the honesty table
  python scripts/backtest.py --write-history # also seed data/history.json with
                                             # replayed weekly scores (marked
                                             # "backfilled"; live rows always win)
"""

import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_and_score as eng  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

eng.warn = lambda msg: None  # replay would otherwise spam J/K-excluded warnings

# Days each series must be lagged so the replay only sees published data.
PUBLICATION_LAG_DAYS = {"cot": 3, "gpr": 32, "dollar": 7,
                        "icsa": 5, "unrate": 37, "effr": 1, "payems": 37}


def shift_dates(series, days):
    return eng.Series(
        [(dt.date.fromisoformat(d) + dt.timedelta(days=days)).isoformat() for d in series.dates],
        list(series.values))


def load_cache():
    path = os.path.join(DATA_DIR, "series_cache.json")
    if not os.path.exists(path):
        sys.exit("data/series_cache.json not found — run scripts/fetch_and_score.py first.")
    with open(path) as f:
        raw = json.load(f)
    cache = {k: eng.Series(v["dates"], v["values"]) for k, v in raw.items()}
    for k, lag in PUBLICATION_LAG_DAYS.items():
        if k in cache:
            cache[k] = shift_dates(cache[k], lag)
    return cache


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
        "dollar", "vix", "baa10y", "silver", "cot", "gpr",
        "effr", "icsa", "unrate", "payems"]
MIN_OBS = {"gpr": 30, "cot": 30, "icsa": 30, "unrate": 12, "payems": 15}


def score_asof(cache, date):
    d = {k: s.asof(date) for k, s in cache.items()}
    for k in CORE:
        if len(d.get(k, [])) < MIN_OBS.get(k, 300):
            return None
    signals = eng.compute_signals(d, fake_freshness(d), MANUAL_NEUTRAL)
    regime_key, regime_name, _ = eng.classify_regime(d)
    fv_mod = 0.0
    try:
        fv = eng.fair_value_gap(d["gold_usd"], d["dfii10"], d["dollar"])
        if fv:
            gap, beta1, _asof = fv
            if beta1 < 0:  # same sanity gate as the live engine
                fv_mod = eng.clamp(-gap / 4.0, -5, 5)
    except Exception:  # noqa: BLE001
        pass
    score, *_ = eng.compute_composite(signals, regime_key, fv_mod)
    return round(score, 1), regime_key


def ranks(xs):
    """Ranks with ties averaged (scores are rounded, so ties are common)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    return cov / (vx * vy) ** 0.5 if vx and vy else 0.0


def main():
    write_history = "--write-history" in sys.argv
    cache = load_cache()
    gold = cache["gold_usd"]

    n = len(gold)
    start_i = max(300, n - 1260)
    # Replay weekly to the present; rows with >=63 trading days of forward data feed
    # the honesty table, later rows exist only so the dashboard history is unbroken.
    replay_idx = list(range(start_i, n, 5))
    if (n - 1) not in replay_idx:
        replay_idx.append(n - 1)

    rows, prev_verdict = [], None
    for i in replay_idx:
        date = gold.dates[i]
        res = score_asof(cache, date)
        if res is None:
            continue
        score, regime = res
        verdict = eng.verdict_for(score, prev_verdict)
        prev_verdict = verdict
        fwd = gold.values[i + 63] / gold.values[i] - 1.0 if i + 63 < n else None
        rows.append({"date": date, "score": score, "verdict": verdict, "regime": regime,
                     "gold_usd": round(gold.values[i], 2), "fwd_3m": fwd})
    scored = [r for r in rows if r["fwd_3m"] is not None]
    if not scored:
        sys.exit("No replayable dates — cache too short.")

    eff_n = max(1, len(scored) // 13)  # 63-day windows sampled every 5 days overlap ~92%
    print(f"Replayed {len(rows)} weekly dates: {rows[0]['date']} → {rows[-1]['date']} "
          f"({len(scored)} with forward returns)")
    lags = ", ".join(f"{k} +{v}d" for k, v in PUBLICATION_LAG_DAYS.items())
    print(f"Publication lags applied: {lags}. J/K excluded "
          f"(matches live engine while manual inputs are placeholder).")
    print(f"CAUTION: overlapping windows — {len(scored)} samples ≈ {eff_n} independent "
          f"observations. Averages are descriptive, not proof.\n")

    order = ["ACCUMULATE", "ADD", "HOLD", "TRIM", "SELL/REDUCE"]
    print(f"{'BAND':<14} {'N':>4} {'AVG 3M FWD':>11} {'MEDIAN':>8} {'% POSITIVE':>11}")
    print("-" * 54)
    for band in order:
        sel = sorted(r["fwd_3m"] for r in scored if r["verdict"] == band)
        if not sel:
            print(f"{band:<14} {0:>4} {'—':>11} {'—':>8} {'—':>11}")
            continue
        flag = "*" if len(sel) < 20 else " "
        avg = sum(sel) / len(sel)
        med = sel[len(sel) // 2]
        pos = 100 * sum(1 for x in sel if x > 0) / len(sel)
        print(f"{band + flag:<14} {len(sel):>4} {avg:>+10.1%} {med:>+7.1%} {pos:>10.0f}%")
    all_fwd = sorted(r["fwd_3m"] for r in scored)
    print("-" * 54)
    print(f"{'ALL':<14} {len(all_fwd):>4} {sum(all_fwd)/len(all_fwd):>+10.1%} "
          f"{all_fwd[len(all_fwd)//2]:>+7.1%} "
          f"{100*sum(1 for x in all_fwd if x>0)/len(all_fwd):>10.0f}%")
    print("(* = N<20: too few observations to mean anything)")

    rho = spearman([r["score"] for r in scored], [r["fwd_3m"] for r in scored])
    sub = scored[::13]  # ~non-overlapping quarterly samples
    rho_nol = spearman([r["score"] for r in sub], [r["fwd_3m"] for r in sub]) if len(sub) > 3 else float("nan")
    changes = sum(1 for a, b in zip(rows, rows[1:]) if a["verdict"] != b["verdict"])
    print(f"\nSpearman rank corr (score vs fwd 3m): {rho:+.2f} full sample; "
          f"{rho_nol:+.2f} on {len(sub)} non-overlapping samples")
    print(f"Verdict changes across the replay (with hysteresis): {changes}")
    if rho < 0.10:
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
            gbp_t = gbp.asof(r["date"]) if gbp else None
            merged[r["date"]] = {"date": r["date"], "score": r["score"], "verdict": r["verdict"],
                                 "gold_usd": r["gold_usd"],
                                 "gold_gbp": round(gbp_t.last, 2) if gbp_t and len(gbp_t) else None,
                                 "regime": r["regime"], "backfilled": True}
        out = sorted(merged.values(), key=lambda h: h["date"])
        eng.write_json(hist_path, out, indent=0)
        eng.write_json(os.path.join(ROOT, "docs", "data", "history.json"), out, indent=0)
        print(f"\nWrote {len(out)} rows to data/history.json (+ docs/data mirror), "
              f"{sum(1 for h in out if h.get('backfilled'))} backfilled.")


if __name__ == "__main__":
    main()
