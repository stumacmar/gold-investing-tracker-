#!/usr/bin/env python3
"""Gold Signal Engine — fetch market data, score 12 signals (A-L), write dashboard JSON.

Data flow:
  fetch everything (with retries + fallbacks + per-series freshness stamps)
  -> compute signals A-L, regime overlay, fair-value anchor, composite 0-100
  -> write data/latest.json, append data/history.json, write data/series_cache.json
  -> mirror latest.json/history.json into docs/data/ for GitHub Pages

No pandas/numpy: plain Python so the Action stays fast. xlrd is used only for the GPR xls.
"""

import json
import math
import os
import sys
import time
import io
import csv
import datetime as dt
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DATA_DIR = os.path.join(ROOT, "docs", "data")

# Per-source user agents: FRED's WAF silently hangs on browser-ish UAs but serves curl-style
# ones; Yahoo rejects curl/Chrome UAs but accepts a bare Mozilla token.
UA = "gold-signal-engine/1.0 (python-urllib)"
UA_FRED = "curl/8.5.0"
UA_BROWSER = "Mozilla/5.0"
TODAY = dt.date.today()

WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    print(f"WARN: {msg}", file=sys.stderr)


# ---------------------------------------------------------------- HTTP helper

def http_get(url, retries=3, timeout=30, ua=UA):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 - any network error retries
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"GET failed after {retries} tries: {url} ({last_err})")


# ---------------------------------------------------------------- Series

class Series:
    """Sorted (date, value) series. Dates are ISO strings, values floats."""

    def __init__(self, dates, values):
        pairs = sorted(zip(dates, values))
        self.dates = [d for d, _ in pairs]
        self.values = [v for _, v in pairs]

    def __len__(self):
        return len(self.values)

    @property
    def last(self):
        return self.values[-1]

    @property
    def last_date(self):
        return self.dates[-1]

    def asof(self, date):
        """Truncated copy containing only observations dated <= date (ISO string)."""
        import bisect
        i = bisect.bisect_right(self.dates, date)
        s = Series.__new__(Series)
        s.dates = self.dates[:i]
        s.values = self.values[:i]
        return s

    def ago(self, n):
        """Value n observations before the last one (n=0 -> last)."""
        return self.values[-1 - n]

    def change(self, n):
        return self.values[-1] - self.values[-1 - n]

    def pct_change(self, n):
        base = self.values[-1 - n]
        return (self.values[-1] / base - 1.0) * 100.0

    def ma(self, n):
        window = self.values[-n:]
        return sum(window) / len(window)

    def pct_dev_from_ma(self, n):
        m = self.ma(n)
        return (self.values[-1] / m - 1.0) * 100.0

    def rsi(self, n=14):
        vals = self.values[-(n + 1):]
        gains = losses = 0.0
        for a, b in zip(vals, vals[1:]):
            d = b - a
            if d >= 0:
                gains += d
            else:
                losses -= d
        if losses == 0:
            return 100.0
        rs = (gains / n) / (losses / n)
        return 100.0 - 100.0 / (1.0 + rs)

    def percentile_of_last(self, window):
        """Percentile rank (0-100) of the latest value within the trailing window."""
        vals = self.values[-window:]
        below = sum(1 for v in vals if v < vals[-1])
        return 100.0 * below / max(1, len(vals) - 1)

    def spark(self, points=40, span=None):
        """Downsampled [[date, value], ...] over the trailing span observations."""
        vals = self.values[-(span or points * 5):]
        dates = self.dates[-(span or points * 5):]
        if len(vals) <= points:
            idx = range(len(vals))
        else:
            step = (len(vals) - 1) / (points - 1)
            idx = sorted({round(i * step) for i in range(points)})
        return [[dates[i], round(vals[i], 4)] for i in idx]


def align(sa, sb):
    """Intersect two series on date; returns (dates, a_vals, b_vals)."""
    bmap = dict(zip(sb.dates, sb.values))
    dates, av, bv = [], [], []
    for d, v in zip(sa.dates, sa.values):
        if d in bmap:
            dates.append(d)
            av.append(v)
            bv.append(bmap[d])
    return dates, av, bv


# ---------------------------------------------------------------- Fetchers

def fetch_fred(series_id):
    """FRED series. Uses the API when FRED_API_KEY is set, else the keyless CSV endpoint."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    start = (TODAY - dt.timedelta(days=365 * 11)).isoformat()
    if key:
        url = ("https://api.stlouisfed.org/fred/series/observations"
               f"?series_id={series_id}&api_key={key}&file_type=json&observation_start={start}")
        obs = json.loads(http_get(url, ua=UA_FRED))["observations"]
        pairs = [(o["date"], o["value"]) for o in obs]
    else:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        text = http_get(url, ua=UA_FRED).decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(text)))
        pairs = [(r[0], r[1]) for r in rows[1:] if len(r) >= 2 and r[0] >= start]
    dates, values = [], []
    for d, v in pairs:
        try:
            values.append(float(v))
            dates.append(d)
        except ValueError:
            continue  # "." = missing observation
    if not dates:
        raise RuntimeError(f"FRED {series_id}: no observations parsed")
    return Series(dates, values)


def fetch_stooq(symbol):
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    text = http_get(url, retries=2, timeout=20, ua=UA_BROWSER).decode("utf-8", "replace")
    if text.lstrip()[:1] == "<" or "Date" not in text.splitlines()[0]:
        raise RuntimeError(f"Stooq {symbol}: non-CSV response (bot-blocked?)")
    start = (TODAY - dt.timedelta(days=365 * 11)).isoformat()
    dates, values = [], []
    for row in csv.DictReader(io.StringIO(text)):
        d, c = row.get("Date", ""), row.get("Close", "")
        if d >= start:
            try:
                values.append(float(c))
                dates.append(d)
            except ValueError:
                continue
    if len(dates) < 200:
        raise RuntimeError(f"Stooq {symbol}: only {len(dates)} rows")
    return Series(dates, values)


def fetch_yahoo(symbol, rng="10y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={rng}&interval=1d")
    data = json.loads(http_get(url, ua=UA_BROWSER))
    result = data["chart"]["result"][0]
    ts = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    dates, values = [], []
    for t, c in zip(ts, closes):
        if c is not None:
            dates.append(dt.datetime.utcfromtimestamp(t).date().isoformat())
            values.append(float(c))
    if len(dates) < 200:
        raise RuntimeError(f"Yahoo {symbol}: only {len(dates)} rows")
    return Series(dates, values)


def fetch_with_fallback(name, primary, fallback):
    """Try primary fetcher, fall back; returns (Series, provider_label)."""
    p_label, p_fn = primary
    f_label, f_fn = fallback
    try:
        return p_fn(), p_label
    except Exception as e:  # noqa: BLE001
        warn(f"{name}: primary source {p_label} failed ({e}); trying {f_label}")
        return f_fn(), f_label


def fetch_cot_gold():
    """CFTC disaggregated futures-only, managed money net position in COMEX gold (weekly)."""
    start = (TODAY - dt.timedelta(days=365 * 7)).isoformat()
    url = ("https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
           "?$select=report_date_as_yyyy_mm_dd,m_money_positions_long_all,m_money_positions_short_all"
           "&$where=contract_market_name='GOLD'%20AND%20report_date_as_yyyy_mm_dd>='"
           + start + "T00:00:00.000'&$order=report_date_as_yyyy_mm_dd&$limit=5000")
    rows = json.loads(http_get(url.replace(" ", "%20")))
    dates, values = [], []
    for r in rows:
        try:
            net = float(r["m_money_positions_long_all"]) - float(r["m_money_positions_short_all"])
            dates.append(r["report_date_as_yyyy_mm_dd"][:10])
            values.append(net)
        except (KeyError, ValueError):
            continue
    if len(dates) < 100:
        raise RuntimeError(f"CFTC COT: only {len(dates)} weekly rows")
    return Series(dates, values)


def fetch_gpr():
    """Iacoviello monthly GPR index; caches last good copy in data/gpr_cache.json."""
    cache_path = os.path.join(DATA_DIR, "gpr_cache.json")
    try:
        import xlrd
        raw = http_get("https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls")
        wb = xlrd.open_workbook(file_contents=raw)
        sh = wb.sheet_by_index(0)
        header = [str(sh.cell_value(0, c)).strip() for c in range(sh.ncols)]
        m_col, g_col = header.index("month"), header.index("GPR")
        dates, values = [], []
        for r in range(1, sh.nrows):
            mv, gv = sh.cell_value(r, m_col), sh.cell_value(r, g_col)
            if not isinstance(gv, (int, float)) or gv == "":
                continue
            d = xlrd.xldate_as_datetime(mv, wb.datemode).date().isoformat()
            dates.append(d)
            values.append(float(gv))
        if len(dates) < 60:
            raise RuntimeError("GPR: too few rows")
        with open(cache_path, "w") as f:
            json.dump({"dates": dates[-200:], "values": values[-200:],
                       "cached_at": dt.datetime.utcnow().isoformat() + "Z"}, f)
        return Series(dates, values), "iacoviello-xls"
    except Exception as e:  # noqa: BLE001
        warn(f"GPR: live fetch failed ({e}); using cache")
        with open(cache_path) as f:
            c = json.load(f)
        return Series(c["dates"], c["values"]), "cache"


def load_manual_inputs():
    with open(os.path.join(DATA_DIR, "manual_inputs.json")) as f:
        return json.load(f)


# ---------------------------------------------------------------- Freshness

# Max acceptable age in days before a series is declared stale and dropped from scoring.
STALE_DAYS = {"daily": 8, "weekly": 21, "monthly": 100, "manual": 130}
# DTWEXBGS is daily data but the Fed publishes it with ~1 week lag.
MAX_AGE_OVERRIDE = {"dollar": 16}


def stamp(series_last_date, cadence, provider, ok=True, key=None):
    age = (TODAY - dt.date.fromisoformat(series_last_date)).days if series_last_date else 9999
    max_age = MAX_AGE_OVERRIDE.get(key, STALE_DAYS[cadence])
    return {
        "last_date": series_last_date,
        "age_days": age,
        "cadence": cadence,
        "provider": provider,
        "ok": ok,
        "stale": age > max_age,
        "fetched_at": dt.datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------- Helpers

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def fmt_pp(x):
    return f"{x:+.2f}pp"


def ordinal(n):
    n = int(round(n))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ---------------------------------------------------------------- Signals A-L
# Each returns a dict:
#   id, name, weight (base), score in [-2, 2] (None if stale), value (display string),
#   rationale (plain English from actual numbers), stale, spark, flip {text, distance}
# 3 months ~ 63 trading days.

M3 = 63


def sig_A_real_yields(d):
    s = d["dfii10"]
    lvl, chg = s.last, s.change(M3)
    score = clamp(-chg / 0.5 * 2.0, -2, 2)  # -0.5pp over 3m -> +2
    if lvl < 0:
        score = clamp(score + 0.5, -2, 2)
    elif lvl > 2.0:
        score = clamp(score - 0.5, -2, 2)
    direction = "falling" if chg < 0 else "rising"
    rationale = (f"10Y real yield {lvl:.2f}%, {fmt_pp(chg)} over 3m — {direction} real yields are "
                 f"{'the tailwind that matters most' if chg < 0 else 'gold’s biggest headwind'}.")
    flip_level = s.ago(M3)
    flip = {"text": f"DFII10 {'above' if chg < 0 else 'below'} {flip_level:.2f}% turns the 3-month real-yield trend "
                    f"{'positive and flips A bearish' if chg < 0 else 'negative and flips A bullish'}.",
            "distance": abs(score)}
    return dict(id="A", name="Real yields", weight=20, score=round(score, 2),
                value=f"{lvl:.2f}% ({fmt_pp(chg)} 3m)", rationale=rationale,
                spark=s.spark(span=260), flip=flip)


def sig_B_dollar(d):
    s = d["dollar"]
    dev, mom = s.pct_dev_from_ma(200), s.pct_change(M3)
    score = clamp(-dev / 1.5 - mom / 2.0, -2, 2)
    rationale = (f"Broad dollar {abs(dev):.1f}% {'above' if dev > 0 else 'below'} its 200DMA, "
                 f"{mom:+.1f}% over 3m — {'a firm dollar caps gold' if score < 0 else 'a soft dollar clears the runway'}.")
    flip = {"text": f"Broad dollar index crossing its 200DMA at {s.ma(200):.1f} "
                    f"({'below' if dev > 0 else 'above'} it now flips B {'bullish' if dev > 0 else 'bearish'}).",
            "distance": abs(score)}
    return dict(id="B", name="Dollar", weight=15, score=round(score, 2),
                value=f"{s.last:.1f} ({dev:+.1f}% vs 200DMA)", rationale=rationale,
                spark=s.spark(span=260), flip=flip)


def sig_C_policy(d):
    s = d["dgs2"]
    chg = s.change(M3)
    score = clamp(-chg / 0.4 * 2.0, -2, 2)
    rationale = (f"2Y yield {s.last:.2f}%, {fmt_pp(chg)} over 3m — "
                 f"{'the market is pricing easing; that pays gold’s rent' if chg < 0 else 'rate expectations are firming against gold'}.")
    flip = {"text": f"2Y yield {'above' if chg < 0 else 'below'} {s.ago(M3):.2f}% flips the policy trajectory "
                    f"{'bearish' if chg < 0 else 'bullish'}.",
            "distance": abs(score)}
    return dict(id="C", name="Policy trajectory", weight=10, score=round(score, 2),
                value=f"{s.last:.2f}% ({fmt_pp(chg)} 3m)", rationale=rationale,
                spark=s.spark(span=260), flip=flip)


def sig_D_inflation(d):
    bk, fwd, ry = d["t10yie"], d["t5yifr"], d["dfii10"]
    chg = bk.change(M3)
    score = clamp(chg / 0.25 * 1.5, -1.5, 1.5)
    combo = chg > 0.05 and ry.change(M3) < -0.05
    if combo:
        score = clamp(score + 0.5, -2, 2)
    fwd_chg = fwd.change(M3)
    rationale = (f"10Y breakevens {bk.last:.2f}% ({fmt_pp(chg)} 3m), 5y5y {fwd.last:.2f}% ({fmt_pp(fwd_chg)})"
                 + (" — breakevens rising while real yields fall is the strongest macro mix gold gets."
                    if combo else
                    (" — inflation expectations drifting higher." if chg > 0 else " — inflation expectations contained.")))
    flip = {"text": f"10Y breakeven {'below' if chg > 0 else 'above'} {bk.ago(M3):.2f}% flips inflation expectations "
                    f"{'bearish' if chg > 0 else 'bullish'}.",
            "distance": abs(score)}
    return dict(id="D", name="Inflation expectations", weight=8, score=round(score, 2),
                value=f"{bk.last:.2f}% ({fmt_pp(chg)} 3m)", rationale=rationale,
                spark=bk.spark(span=260), flip=flip)


def sig_E_trend(d):
    s = d["gold_usd"]
    ma50, ma200 = s.ma(50), s.ma(200)
    px = s.last
    score = (0.5 if px > ma50 else -0.5) + (0.7 if px > ma200 else -0.7) \
        + (0.3 if ma50 > ma200 else -0.3)
    # 12m return percentile vs 5y of rolling 12m returns
    rets = [s.values[i] / s.values[i - 252] - 1 for i in range(len(s) - 1260, len(s)) if i >= 252]
    if rets:
        below = sum(1 for r in rets if r < rets[-1])
        pct = 100.0 * below / max(1, len(rets) - 1)
        score += (pct - 50) / 50 * 0.5
    score = clamp(score, -2, 2)
    cross = "golden cross intact" if ma50 > ma200 else "death cross in force"
    rationale = (f"Price {'above' if px > ma50 else 'below'} the 50DMA and "
                 f"{'above' if px > ma200 else 'below'} the 200DMA, {cross} — "
                 f"{'the trend is doing the heavy lifting' if score > 0 else 'the tape is against you'}.")
    flip = {"text": f"A close {'below' if px > ma50 else 'above'} the 50DMA at ${ma50:,.0f} starts flipping trend "
                    f"{'bearish' if px > ma50 else 'bullish'}.",
            "distance": abs(score)}
    return dict(id="E", name="Trend & momentum", weight=12, score=round(score, 2),
                value=f"${px:,.0f} (50DMA ${ma50:,.0f})", rationale=rationale,
                spark=s.spark(span=260), flip=flip)


def sig_F_positioning(d):
    s = d["cot"]
    pct = s.percentile_of_last(260)  # ~5y of weekly reports
    if pct > 90:
        score, tone = -1.5, "crowded long — everyone who wants gold owns it; contrarian bearish"
    elif pct > 80:
        score, tone = -0.75, "getting crowded — late-comers are the seller of tomorrow"
    elif pct < 10:
        score, tone = 1.5, "washed out — stale longs are gone, dry powder for rallies"
    elif pct < 20:
        score, tone = 0.75, "light positioning — plenty of fuel if the tape turns up"
    else:
        score, tone = round((50 - pct) / 50 * 0.4, 2), "mid-range — positioning is not the story right now"
    rationale = f"Managed money net long {s.last:,.0f} contracts, {ordinal(pct)} percentile of 5y — {tone}."
    nearest = 90 if pct >= 50 else 10
    flip = {"text": f"Managed-money net longs crossing the {nearest}th percentile of the 5y range flips positioning "
                    f"{'hard bearish (crowded)' if nearest == 90 else 'hard bullish (washed out)'}.",
            "distance": abs(score) if abs(score) > 0 else abs(pct - nearest) / 40}
    return dict(id="F", name="Positioning (COT)", weight=8, score=round(score, 2),
                value=f"{s.last:,.0f} net ({ordinal(pct)} pct)", rationale=rationale,
                spark=s.spark(span=260), flip=flip)


def sig_G_valuation(d):
    s = d["gold_usd"]
    dev, rsi = s.pct_dev_from_ma(200), s.rsi(14)
    score = 0.0
    if dev > 15:
        score -= min(2.0, 1.0 + (dev - 15) / 10)
    elif dev < -10:
        score += min(2.0, 1.0 + (-dev - 10) / 10)
    if rsi > 85:
        score -= 1.25
    elif rsi > 75:
        score -= 0.75
    elif rsi < 20:
        score += 1.25
    elif rsi < 30:
        score += 0.75
    score = clamp(score, -2, 2)
    if score < 0:
        tone = "stretched — chasing here is paying up for someone else's exit"
    elif score > 0:
        tone = "washed out — the spring is compressed"
    else:
        tone = "no stretch either way"
    rationale = f"{dev:+.1f}% vs 200DMA, RSI(14) {rsi:.0f} — {tone}."
    flip = {"text": f"Gold {'below' if dev > 15 else 'above'} ${s.ma(200) * 1.15:,.0f} (15% over the 200DMA) "
                    f"{'removes' if dev > 15 else 'triggers'} the overbought penalty.",
            "distance": abs(score) if score != 0 else abs(dev - 15) / 10}
    return dict(id="G", name="Valuation stretch", weight=8, score=round(score, 2),
                value=f"{dev:+.1f}% / RSI {rsi:.0f}", rationale=rationale,
                spark=s.spark(span=130), flip=flip)


def sig_H_fear(d):
    vix, credit = d["vix"], d["baa10y"]
    v = vix.last
    cchg = credit.change(M3)
    score = 0.0
    if v > 30:
        score += 1.0
    elif v > 20:
        score += 0.5
    elif v < 15:
        score -= 0.25
    if cchg > 0.15:
        score += 1.0
    elif cchg > 0.05:
        score += 0.5
    elif cchg < -0.15:
        score -= 0.5
    score = clamp(score, -2, 2)
    rationale = (f"VIX {v:.0f}, BAA-10Y spread {credit.last:.2f}% ({fmt_pp(cchg)} 3m) — "
                 f"{'fear is bidding for havens' if score > 0 else ('markets are calm; no safe-haven bid' if score < 0 else 'no stress signal either way')}.")
    flip = {"text": f"VIX above 30 or credit spreads widening >0.15pp in 3m puts a safe-haven bid under gold.",
            "distance": abs(score) if score != 0 else 0.5}
    return dict(id="H", name="Fear & credit", weight=6, score=round(score, 2),
                value=f"VIX {v:.0f} / {credit.last:.2f}%", rationale=rationale,
                spark=vix.spark(span=260), flip=flip)


def sig_I_geopolitics(d):
    s = d["gpr"]
    avg5 = s.ma(60)  # 60 monthly obs = 5y
    ratio = s.last / avg5
    score = clamp((ratio - 1) * 2.5, -2, 2)
    rationale = (f"GPR index {s.last:.0f} vs 5y average {avg5:.0f} — geopolitical risk "
                 f"{'running hot; keeps a floor under gold' if ratio > 1.1 else ('elevated' if ratio > 1 else 'below trend; no war premium')}.")
    flip = {"text": f"GPR crossing its 5y average ({avg5:.0f}) flips geopolitics "
                    f"{'bearish' if ratio > 1 else 'bullish'}.",
            "distance": abs(score)}
    return dict(id="I", name="Geopolitics (GPR)", weight=5, score=round(score, 2),
                value=f"{s.last:.0f} (5y avg {avg5:.0f})", rationale=rationale,
                spark=s.spark(points=30, span=60), flip=flip)


def sig_J_central_banks(manual):
    cb = manual["central_banks"]
    r = cb["recent_4q_tonnes"] / max(1e-9, cb["five_year_avg_annual_tonnes"])
    score = clamp((r - 1) * 4.0, -2, 2)
    rationale = (f"Central banks bought {cb['recent_4q_tonnes']:,}t over the last 4 quarters vs "
                 f"{cb['five_year_avg_annual_tonnes']:,}t/yr 5y average — "
                 f"{'official-sector bid is above trend; that is structural demand' if r > 1 else ('buying at trend' if r > 0.9 else 'official-sector bid is fading')}.")
    flip = {"text": f"Central-bank pace dropping below {cb['five_year_avg_annual_tonnes']:,}t/yr (5y avg) flips J bearish.",
            "distance": abs(score)}
    return dict(id="J", name="Central bank demand", weight=4, score=round(score, 2),
                value=f"{cb['recent_4q_tonnes']:,}t / 4q", rationale=rationale,
                spark=[], flip=flip, manual_date=cb["last_updated"])


def sig_K_etf_flows(manual):
    etf = manual["etf_flows"]
    t = etf["last_3m_net_tonnes"]
    if t > 50:
        score, tone = 1.5, "Western money is confirming the move"
    elif t > 0:
        score, tone = 0.5, "mild inflows — quiet confirmation"
    elif t > -50:
        score, tone = -0.5, "mild outflows — Western investors not participating"
    else:
        score, tone = -1.5, "heavy outflows — Western money is leaving"
    rationale = f"ETF net flows {t:+,}t over 3m — {tone}."
    flip = {"text": "ETF 3-month net flows crossing zero flips K.",
            "distance": abs(score)}
    return dict(id="K", name="ETF flows", weight=2, score=round(score, 2),
                value=f"{t:+,}t / 3m", rationale=rationale,
                spark=[], flip=flip, manual_date=etf["last_updated"])


def sig_L_gold_silver(d):
    g, s = d["gold_usd"], d["silver"]
    dates, gv, sv = align(g, s)
    ratio = Series(dates, [a / b for a, b in zip(gv, sv)])
    pct = ratio.percentile_of_last(1260)
    if pct > 90:
        score, tone = -1.0, "silver is not confirming — historically a tired-rally tell"
    elif pct < 10:
        score, tone = 1.0, "silver outperforming — broad metals risk appetite, healthy bull"
    else:
        score, tone = 0.0, "ratio mid-range; no tell either way"
    rationale = f"Gold/silver ratio {ratio.last:.0f} ({ordinal(pct)} pct of 5y) — {tone}."
    flip = {"text": f"Gold/silver ratio moving beyond the 90th/below the 10th percentile of 5y turns L into a signal.",
            "distance": abs(score) if score != 0 else 0.6}
    return dict(id="L", name="Gold/silver ratio", weight=2, score=round(score, 2),
                value=f"{ratio.last:.1f}", rationale=rationale,
                spark=ratio.spark(span=260), flip=flip)


# ---------------------------------------------------------------- Fair value

def fair_value_gap(gold, dfii10, dollar, window=1260):
    """OLS of ln(gold) on DFII10 + ln(dollar) over the trailing window; returns residual gap %."""
    dts, gv, rv = align(gold, dfii10)
    gs, ds2 = Series(dts, gv), Series(dts, rv)
    dts2, gv2, dv2 = align(gs, dollar)
    rmap = dict(zip(dts, rv))
    rows = [(math.log(g), rmap[d], math.log(x)) for d, g, x in zip(dts2, gv2, dv2)][-window:]
    n = len(rows)
    if n < 400:
        return None
    # Normal equations for y = b0 + b1*x1 + b2*x2
    sx1 = sum(r[1] for r in rows); sx2 = sum(r[2] for r in rows); sy = sum(r[0] for r in rows)
    sx1x1 = sum(r[1] * r[1] for r in rows); sx2x2 = sum(r[2] * r[2] for r in rows)
    sx1x2 = sum(r[1] * r[2] for r in rows)
    sx1y = sum(r[1] * r[0] for r in rows); sx2y = sum(r[2] * r[0] for r in rows)
    A = [[n, sx1, sx2], [sx1, sx1x1, sx1x2], [sx2, sx1x2, sx2x2]]
    b = [sy, sx1y, sx2y]
    # Gaussian elimination
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(A[r][i]))
        A[i], A[piv] = A[piv], A[i]
        b[i], b[piv] = b[piv], b[i]
        if abs(A[i][i]) < 1e-12:
            return None
        for r in range(i + 1, 3):
            f = A[r][i] / A[i][i]
            for c in range(i, 3):
                A[r][c] -= f * A[i][c]
            b[r] -= f * b[i]
    beta = [0.0, 0.0, 0.0]
    for i in (2, 1, 0):
        beta[i] = (b[i] - sum(A[i][c] * beta[c] for c in range(i + 1, 3))) / A[i][i]
    y, x1, x2 = rows[-1]
    resid = y - (beta[0] + beta[1] * x1 + beta[2] * x2)
    return (math.exp(resid) - 1.0) * 100.0


# ---------------------------------------------------------------- Regime

def classify_regime(d):
    vix = d["vix"].last
    credit_1m = d["baa10y"].change(21)
    ry_chg = d["dfii10"].change(M3)
    usd_mom = d["dollar"].pct_change(M3)
    bk_chg = d["t10yie"].change(M3)
    nom_chg = d["dgs10"].change(M3)
    if vix > 30 or credit_1m > 0.30:
        return ("crisis", "Crisis / risk-off",
                "VIX or credit spreads are spiking. Fear signals dominate — but remember 2008 and March 2020: "
                "gold can dip first on forced liquidation before the safe-haven bid takes over.")
    if ry_chg < -0.05 and usd_mom < 0:
        return ("disinflationary_easing", "Disinflationary easing",
                "Real yields falling with a soft dollar — the best regime gold gets. Macro and trend signals carry extra weight.")
    if bk_chg > 0.05 and bk_chg > nom_chg:
        return ("reflation", "Reflation",
                "Breakevens rising faster than nominal yields — real yields compressing via the inflation side. Bullish; inflation signals upweighted.")
    if ry_chg > 0.05 and usd_mom > 0:
        return ("hostile", "Rising real yields / strong dollar",
                "The macro is leaning on gold from both sides. Momentum must be exceptional to overcome this drag.")
    return ("neutral", "Mixed / transitional",
            "No dominant macro regime — base weights apply.")


REGIME_WEIGHT_MULT = {
    "disinflationary_easing": {"A": 1.2, "B": 1.2, "E": 1.15},
    "reflation": {"D": 1.5, "A": 1.1},
    "hostile": {"A": 1.25, "B": 1.25},
    "crisis": {"H": 2.0, "I": 1.4, "F": 0.8, "E": 0.8},
    "neutral": {},
}

BANDS = [(72, "ACCUMULATE"), (58, "ADD"), (43, "HOLD"), (28, "TRIM"), (-1, "SELL/REDUCE")]


def verdict_for(score):
    for lo, name in BANDS:
        if score >= lo:
            return name
    return "SELL/REDUCE"


# ---------------------------------------------------------------- Composite

def compute_composite(signals, regime_key, fv_gap):
    mult = REGIME_WEIGHT_MULT.get(regime_key, {})
    total_base = sum(s["weight"] for s in signals)
    live = [s for s in signals if not s.get("stale") and s["score"] is not None]
    for s in signals:
        s["eff_weight"] = round(s["weight"] * mult.get(s["id"], 1.0), 2) if s in live else 0.0
    wsum = sum(s["eff_weight"] for s in live)
    raw = sum(s["eff_weight"] * s["score"] for s in live) / wsum if wsum else 0.0
    base_score = 50 + 25 * raw  # raw in [-2,2] -> [0,100]
    fv_mod = clamp(-fv_gap / 4.0, -5, 5) if fv_gap is not None else 0.0
    score = clamp(base_score + fv_mod, 0, 100)

    live_base_weight = sum(s["weight"] for s in live)
    freshness_frac = live_base_weight / total_base
    mean = sum(s["eff_weight"] * s["score"] for s in live) / wsum if wsum else 0.0
    var = sum(s["eff_weight"] * (s["score"] - mean) ** 2 for s in live) / wsum if wsum else 0.0
    dispersion = math.sqrt(var)
    if freshness_frac >= 0.95 and dispersion <= 1.0:
        conf = "High"
    elif freshness_frac < 0.80 or dispersion > 1.4:
        conf = "Low"
    else:
        conf = "Med"
    return score, raw, fv_mod, conf, freshness_frac, dispersion


# ---------------------------------------------------------------- Main

def build_data_bundle():
    """Fetch everything; returns (series dict, freshness dict, provider notes)."""
    d, fresh = {}, {}

    gold_usd, prov = fetch_with_fallback(
        "gold_usd",
        ("stooq:xauusd", lambda: fetch_stooq("xauusd")),
        ("yahoo:GC=F", lambda: fetch_yahoo("GC=F")))
    d["gold_usd"] = gold_usd
    fresh["gold_usd"] = stamp(gold_usd.last_date, "daily", prov)

    def gbp_derived():
        fx = fetch_yahoo("GBPUSD=X")
        dts, gv, fv = align(d["gold_usd"], fx)
        return Series(dts, [g / f for g, f in zip(gv, fv)])

    gold_gbp, prov = fetch_with_fallback(
        "gold_gbp",
        ("stooq:xaugbp", lambda: fetch_stooq("xaugbp")),
        ("derived:GC=F/GBPUSD", gbp_derived))
    d["gold_gbp"] = gold_gbp
    fresh["gold_gbp"] = stamp(gold_gbp.last_date, "daily", prov)

    silver, prov = fetch_with_fallback(
        "silver",
        ("stooq:xagusd", lambda: fetch_stooq("xagusd")),
        ("yahoo:SI=F", lambda: fetch_yahoo("SI=F")))
    d["silver"] = silver
    fresh["silver"] = stamp(silver.last_date, "daily", prov)

    fred_ids = {"dfii10": "DFII10", "dgs10": "DGS10", "dgs2": "DGS2",
                "t10yie": "T10YIE", "t5yifr": "T5YIFR", "dollar": "DTWEXBGS",
                "vix": "VIXCLS", "baa10y": "BAA10Y"}
    provider = "fred-api" if os.environ.get("FRED_API_KEY") else "fred-csv"
    for key, sid in fred_ids.items():
        try:
            d[key] = fetch_fred(sid)
            fresh[key] = stamp(d[key].last_date, "daily", provider, key=key)
        except Exception as e:  # noqa: BLE001
            warn(f"FRED {sid} failed: {e}")
            fresh[key] = stamp(None, "daily", provider, ok=False)

    try:
        d["cot"] = fetch_cot_gold()
        fresh["cot"] = stamp(d["cot"].last_date, "weekly", "cftc-socrata")
    except Exception as e:  # noqa: BLE001
        warn(f"COT failed: {e}")
        fresh["cot"] = stamp(None, "weekly", "cftc-socrata", ok=False)

    try:
        gpr, prov = fetch_gpr()
        d["gpr"] = gpr
        fresh["gpr"] = stamp(gpr.last_date, "monthly", prov)
    except Exception as e:  # noqa: BLE001
        warn(f"GPR failed entirely (no cache?): {e}")
        fresh["gpr"] = stamp(None, "monthly", "none", ok=False)

    manual = load_manual_inputs()
    fresh["central_banks"] = stamp(manual["central_banks"]["last_updated"], "manual", "manual_inputs.json")
    fresh["etf_flows"] = stamp(manual["etf_flows"]["last_updated"], "manual", "manual_inputs.json")
    return d, fresh, manual


SIGNAL_DEPS = {
    "A": ["dfii10"], "B": ["dollar"], "C": ["dgs2"], "D": ["t10yie", "t5yifr", "dfii10"],
    "E": ["gold_usd"], "F": ["cot"], "G": ["gold_usd"], "H": ["vix", "baa10y"],
    "I": ["gpr"], "J": ["central_banks"], "K": ["etf_flows"], "L": ["gold_usd", "silver"],
}


def compute_signals(d, fresh, manual):
    builders = {
        "A": lambda: sig_A_real_yields(d), "B": lambda: sig_B_dollar(d),
        "C": lambda: sig_C_policy(d), "D": lambda: sig_D_inflation(d),
        "E": lambda: sig_E_trend(d), "F": lambda: sig_F_positioning(d),
        "G": lambda: sig_G_valuation(d), "H": lambda: sig_H_fear(d),
        "I": lambda: sig_I_geopolitics(d), "J": lambda: sig_J_central_banks(manual),
        "K": lambda: sig_K_etf_flows(manual), "L": lambda: sig_L_gold_silver(d),
    }
    names = {"A": "Real yields", "B": "Dollar", "C": "Policy trajectory",
             "D": "Inflation expectations", "E": "Trend & momentum", "F": "Positioning (COT)",
             "G": "Valuation stretch", "H": "Fear & credit", "I": "Geopolitics (GPR)",
             "J": "Central bank demand", "K": "ETF flows", "L": "Gold/silver ratio"}
    weights = {"A": 20, "B": 15, "C": 10, "D": 8, "E": 12, "F": 8,
               "G": 8, "H": 6, "I": 5, "J": 4, "K": 2, "L": 2}
    signals = []
    for sid, build in builders.items():
        deps = SIGNAL_DEPS[sid]
        dead = [k for k in deps if not fresh.get(k, {}).get("ok") or fresh[k]["stale"]]
        if dead:
            warn(f"Signal {sid} excluded: stale/missing inputs {dead}")
            signals.append(dict(id=sid, name=names[sid], weight=weights[sid], score=None,
                                value="—", rationale=f"Data stale ({', '.join(dead)}) — "
                                "score computed without this signal; weights renormalised.",
                                stale=True, spark=[], flip=None))
            continue
        try:
            sig = build()
            sig["stale"] = False
            signals.append(sig)
        except Exception as e:  # noqa: BLE001
            warn(f"Signal {sid} computation failed: {e}")
            signals.append(dict(id=sid, name=names[sid], weight=weights[sid], score=None,
                                value="—", rationale="Computation failed — excluded, weights renormalised.",
                                stale=True, spark=[], flip=None))
    return signals


def gbp_lens(d):
    g = d["gold_gbp"]
    ma200, ma50 = g.ma(200), g.ma(50)
    px = g.last
    trend = ("uptrend" if px > ma200 and ma50 > ma200
             else "downtrend" if px < ma200 and ma50 < ma200 else "mixed")
    chg3m = g.pct_change(M3)
    note = (f"XAUGBP £{px:,.0f}, {chg3m:+.1f}% over 3m, {trend} vs 200DMA — "
            + ("sterling gold is trending up: a bullish USD verdict carries into GBP." if trend == "uptrend"
               else "sterling gold is trending down: if the USD verdict says add, the currency is eating the move — "
               "size down; if it says trim, GBP agrees."
               if trend == "downtrend" else "sterling picture is mixed; let the USD signal lead but scale sizes down."))
    return {"price": round(px, 2), "chg_3m_pct": round(chg3m, 1), "trend": trend, "note": note}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DOCS_DATA_DIR, exist_ok=True)

    print("Fetching data...")
    d, fresh, manual = build_data_bundle()
    for k, f in fresh.items():
        status = "STALE" if f["stale"] else "ok"
        print(f"  {k:14s} {f['provider']:22s} last={f['last_date']} age={f['age_days']}d [{status}]")

    print("Scoring signals...")
    signals = compute_signals(d, fresh, manual)
    regime_key, regime_name, regime_desc = classify_regime(d)

    fv_gap = None
    try:
        fv_gap = fair_value_gap(d["gold_usd"], d["dfii10"], d["dollar"])
    except Exception as e:  # noqa: BLE001
        warn(f"Fair-value regression failed: {e}")

    score, raw, fv_mod, conf, freshness_frac, dispersion = compute_composite(signals, regime_key, fv_gap)
    verdict = verdict_for(score)

    live = [s for s in signals if not s["stale"]]
    flips = sorted((s for s in live if s.get("flip")), key=lambda s: s["flip"]["distance"])[:2]
    change_my_mind = [{"signal": s["id"], "name": s["name"], "text": s["flip"]["text"]} for s in flips]

    # Rank: biggest effective weight first (stale signals sink to the bottom)
    signals_ranked = sorted(signals, key=lambda s: (s["stale"], -s.get("eff_weight", 0), s["id"]))

    gold = d["gold_usd"]
    ggbp = d["gold_gbp"]
    latest = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "as_of": gold.last_date,
        "score": round(score, 1),
        "verdict": verdict,
        "bands": {"ACCUMULATE": "≥72", "ADD": "58–71", "HOLD": "43–57", "TRIM": "28–42", "SELL/REDUCE": "<28"},
        "confidence": {"level": conf, "freshness_pct": round(freshness_frac * 100),
                       "dispersion": round(dispersion, 2)},
        "regime": {"key": regime_key, "name": regime_name, "description": regime_desc},
        "fair_value": {
            "gap_pct": round(fv_gap, 1) if fv_gap is not None else None,
            "modifier": round(fv_mod, 1),
            "text": (f"Gold is trading {abs(fv_gap):.0f}% {'above' if fv_gap > 0 else 'below'} its macro fair value "
                     f"(5y regression on real yields + dollar)." if fv_gap is not None
                     else "Fair-value model unavailable this run."),
        },
        "gold": {
            "usd": round(gold.last, 2), "usd_chg_1d_pct": round(gold.pct_change(1), 2),
            "usd_chg_3m_pct": round(gold.pct_change(M3), 1),
            "usd_200dma": round(gold.ma(200), 2),
            "gbp": round(ggbp.last, 2), "gbp_chg_1d_pct": round(ggbp.pct_change(1), 2),
        },
        "gbp_lens": gbp_lens(d),
        "change_my_mind": change_my_mind,
        "signals": signals_ranked,
        "freshness": fresh,
        "warnings": WARNINGS,
    }

    with open(os.path.join(DATA_DIR, "latest.json"), "w") as f:
        json.dump(latest, f, indent=1)

    # History: one row per as-of date; live runs overwrite backfilled rows for the same date.
    hist_path = os.path.join(DATA_DIR, "history.json")
    history = []
    if os.path.exists(hist_path):
        with open(hist_path) as f:
            history = json.load(f)
    row = {"date": gold.last_date, "score": round(score, 1), "verdict": verdict,
           "gold_usd": round(gold.last, 2), "gold_gbp": round(ggbp.last, 2), "regime": regime_key}
    history = [h for h in history if h["date"] != row["date"]] + [row]
    history.sort(key=lambda h: h["date"])
    with open(hist_path, "w") as f:
        json.dump(history, f, indent=0)

    # Series cache for backtest.py and offline replay
    cache = {k: {"dates": s.dates, "values": [round(v, 6) for v in s.values]}
             for k, s in d.items()}
    with open(os.path.join(DATA_DIR, "series_cache.json"), "w") as f:
        json.dump(cache, f)

    # Mirror to docs/data for GitHub Pages (Pages serves /docs only)
    for name in ("latest.json", "history.json"):
        with open(os.path.join(DATA_DIR, name)) as src, \
             open(os.path.join(DOCS_DATA_DIR, name), "w") as dst:
            dst.write(src.read())

    print(f"\n=== GOLD SIGNAL: {latest['score']} / 100 -> {verdict} "
          f"(regime: {regime_name}, confidence: {conf}) ===")
    print(f"Gold ${gold.last:,.2f} / £{ggbp.last:,.2f} | {latest['fair_value']['text']}")
    for s in signals_ranked:
        sc = "  --" if s["score"] is None else f"{s['score']:+.2f}"
        print(f"  [{s['id']}] {s['name']:24s} w={s.get('eff_weight', 0):5.1f} score={sc}  {s['rationale']}")
    if WARNINGS:
        print(f"\n{len(WARNINGS)} warning(s) — see above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
