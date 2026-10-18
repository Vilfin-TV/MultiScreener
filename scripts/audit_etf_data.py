#!/usr/bin/env python3
"""
audit_etf_data.py
─────────────────
Independent accuracy audit of the ETF page data after every refresh → data/etf_audit.json (shown on the page).
Exit code 1 on any error, so the workflow never publishes data that fails it.

Recomputed from the raw daily bars (data/etf/d/<SYMBOL>.json), not from the build's own intermediate values:
  prices     last close and date, 52-week high / low, weekly closes in etf_hist.json = last daily close of each week
  returns    1W / 1M / 3M / 6M / YTD / 1Y price returns (same calendar rules as the page: absolute up to 1 year)
  risk       1-year volatility of daily log returns, 3-year max drawdown cannot be shallower than the 1-year one
  liquidity  20-day average volume and traded value
  premium    closing price on the NAV date vs the official NAV
Cross-file consistency:
  etf_extras.json   scorecard overall = 40/30/30, ranks within peers, recency recomputed from weekly closes, rating =
                    weighted parts, stars 1–5, Factor DNA weights sum to 100
  etf_holdings.json weights sorted, equity ≥ 60%, top-10 share = sum of the 10 largest listed weights (when complete)
  etf_smart.json    every chosen ETF re-checked against the published source fields (liquidity, trading, price vs
                    NAV), plan weights = 100 in 5% steps
  etf_live.json     (market hours) bars dated after the last close, within ±20% of it, OHLC consistent
Day over day (vs the previous audit): ETFs that disappeared, coverage drops, price jumps over 20% without a split
flag, a published date going backwards.

Usage: python scripts/audit_etf_data.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "etf_audit.json")


class Audit:
    def __init__(self):
        self.n = 0
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.by: dict[str, list[int]] = {}

    def check(self, area: str, ok: bool, msg: str, warn: bool = False):
        self.n += 1
        b = self.by.setdefault(area, [0, 0])
        b[0] += 1
        if not ok:
            b[1] += 1
            (self.warnings if warn else self.errors).append(f"[{area}] {msg}")


def load(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def shift_months(d: date, m: int) -> date:
    y, mo = divmod(d.month - 1 + m, 12)
    y += d.year
    mo += 1
    import calendar
    return date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))


def close(a, b, tol_abs, tol_rel=0.0):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= max(tol_abs, tol_rel * abs(b))


def main() -> int:
    A = Audit()
    M = load("etf_momentum.json")
    H = load("etf_hist.json")
    X = load("etf_extras.json", {})
    HO = load("etf_holdings.json", {})
    SM = load("etf_smart.json", {})
    LV = load("etf_live.json")
    prev = load("etf_audit.json", {}) or {}
    if not M or not H:
        print("ETF data missing")
        return 1
    asof = M["asOf"]
    ad = date.fromisoformat(asof)
    today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()
    A.check("freshness", (today - ad).days <= 6, f"published session {asof} is {(today - ad).days} days old")
    A.check("freshness", H.get("asOf") == asof, f"etf_hist asOf {H.get('asOf')} != {asof}")
    weeks = H["weeks"]
    ddir = os.path.join(DATA, "etf", "d")
    have_daily = os.path.isdir(ddir)
    A.check("coverage", have_daily, "daily bars folder missing", warn=True)
    priced = [e for e in M["etfs"] if e.get("p")]
    by_k = {e["s"]: e.get("k") for e in M["etfs"]}
    n_daily = 0
    jumps_by: dict[tuple, list[str]] = {}         # (category, date) → ETFs with a >20% daily move
    jump_rows = []
    for e in priced:
        s = e["s"]
        p = os.path.join(ddir, f"{s}.json")
        if not os.path.exists(p):
            continue
        B = json.load(open(p))
        n_daily += 1
        d = [date(t // 10000, t // 100 % 100, t % 100) for t in B["t"]]
        c, v = B["c"], B["v"]
        last = d[-1]
        # prices
        A.check("prices", close(c[-1], e["p"], 0.011, 0.0005), f"{s}: last close {c[-1]} vs published {e['p']}")
        A.check("prices", last.isoformat() == e.get("d"), f"{s}: last bar {last} vs published date {e.get('d')}")
        if len(c) >= 250:
            A.check("prices", close(max(c[-250:]), e.get("h52"), 0.011, 0.0005), f"{s}: 52-week high {max(c[-250:])} vs {e.get('h52')}")
            A.check("prices", close(min(c[-250:]), e.get("l52"), 0.011, 0.0005), f"{s}: 52-week low {min(c[-250:])} vs {e.get('l52')}")
        # weekly close in the 5-year history = last daily close of that week
        hs = (H.get("etfs") or {}).get(s)
        if hs:
            wk = weeks[-1]
            j = bisect_right(d, date.fromisoformat(wk)) - 1
            if j >= 0 and d[j].isocalendar()[:2] == date.fromisoformat(wk).isocalendar()[:2] and hs[-1] is not None:
                A.check("history", close(c[j], hs[-1], 0.011, 0.0005), f"{s}: weekly close {hs[-1]} vs daily {c[j]} ({wk})")
        # returns (absolute up to 1 year, 10-day tolerance for the base date — same rule as the build)

        def at(t: date):
            i = bisect_right(d, t) - 1
            if i < 0 or (t - d[i]).days > 10:
                return None
            return c[i]
        r = e.get("r") or {}
        bases = {"1w": last - timedelta(days=7), "1m": shift_months(last, -1), "3m": shift_months(last, -3),
                 "6m": shift_months(last, -6), "ytd": date(last.year - 1, 12, 31), "1y": shift_months(last, -12)}
        for k, t in bases.items():
            b = at(t)
            if b and r.get(k) is not None and d[0] <= t:
                mine = round((c[-1] / b - 1) * 100, 2)
                A.check("returns", close(mine, r[k], 0.06), f"{s}: {k} return {r[k]} vs recomputed {mine}")
        if len(c) >= 2 and r.get("1d") is not None:
            A.check("returns", close(round((c[-1] / c[-2] - 1) * 100, 2), r["1d"], 0.06), f"{s}: 1-day return {r['1d']}")
        # risk
        if len(c) >= 251 and e.get("vol") is not None:
            lr = [math.log(c[i] / c[i - 1]) for i in range(len(c) - 250, len(c)) if c[i] > 0 and c[i - 1] > 0]
            m = sum(lr) / len(lr)
            vol = math.sqrt(sum((x - m) ** 2 for x in lr) / (len(lr) - 1)) * math.sqrt(250) * 100
            A.check("risk", close(vol, e["vol"], 0.15, 0.02), f"{s}: volatility {e['vol']} vs recomputed {vol:.2f}")
        if e.get("mdd") is not None and len(c) >= 250:
            peak, dd = 0, 0
            for x in c[-250:]:
                peak = max(peak, x)
                dd = min(dd, x / peak - 1)
            A.check("risk", e["mdd"] <= dd * 100 + 0.05, f"{s}: 3-year drawdown {e['mdd']} shallower than the 1-year {dd * 100:.2f}")
        # liquidity
        if e.get("tv") is not None:
            tv = sum(px * vv for px, vv in zip(c[-20:], v[-20:])) / min(20, len(c)) / 1e7
            A.check("liquidity", close(tv, e["tv"], 0.002, 0.02), f"{s}: traded value {e['tv']} vs recomputed {tv:.3f}")
        if e.get("av") is not None:
            av = int(sum(v[-20:]) / min(20, len(v)))
            A.check("liquidity", close(av, e["av"], 2, 0.01), f"{s}: average volume {e['av']} vs recomputed {av}")
        # bars themselves
        bad = [B["t"][i] for i in range(len(c)) if not (B["h"][i] >= max(B["o"][i], c[i]) - 1e-6 and B["l"][i] <= min(B["o"][i], c[i]) + 1e-6 and B["l"][i] > 0)]
        A.check("bars", not bad, f"{s}: inconsistent OHLC on {bad[:3]}")
        jumps = [B["t"][i] for i in range(1, len(c)) if abs(c[i] / c[i - 1] - 1) > 0.2]
        for t in jumps:
            jumps_by.setdefault((e.get("k"), t), []).append(s)
        jump_rows.append((s, jumps, bool(e.get("f"))))
        # premium / discount on the NAV date
        x = e.get("x") or {}
        if e.get("prem") is not None and x.get("nav") and e.get("premD"):
            j = bisect_right(d, date.fromisoformat(e["premD"])) - 1
            if j >= 0 and d[j].isoformat() == e["premD"]:
                pm = round((c[j] / x["nav"] - 1) * 100, 2)
                A.check("premium", close(pm, e["prem"], 0.02), f"{s}: premium {e['prem']} vs recomputed {pm}")
    # a >20% day shared by 3+ ETFs of the same category is a market move (e.g. a metal crash), not a data error
    for s, jumps, flagged in jump_rows:
        cat = by_k.get(s)
        own = [t for t in jumps if len(jumps_by.get((cat, t), [])) < 3]
        A.check("bars", not own or flagged, f"{s}: daily moves over 20% on {own[:3]} without a split / repair flag", warn=True)
    A.check("coverage", n_daily >= 0.9 * len(priced), f"daily bars for {n_daily} of {len(priced)} priced ETFs")

    # ── analytics ──
    XE = X.get("etfs", {})
    syms = {e["s"] for e in M["etfs"]}
    W = len(weeks)
    for s, o in XE.items():
        A.check("analytics", s in syms, f"etf_extras: unknown ETF {s}")
        for view, c in (o.get("sc") or {}).items():
            A.check("scorecard", abs(0.4 * c["c"] + 0.3 * c["r"] + 0.3 * c["v"] - c["o"]) <= 0.15, f"{s}: {view}Y overall {c['o']}")
            A.check("scorecard", 1 <= c["rk"] <= c["n"], f"{s}: {view}Y rank {c['rk']}/{c['n']}")
        if o.get("rt"):
            rt, w8 = o["rt"], X.get("ratingW", {})
            mix = sum(w8[k] * v for k, v in rt["p"].items()) / sum(w8[k] for k in rt["p"])
            A.check("rating", abs(mix - rt["s"]) <= 1.01 and 1 <= rt["st"] <= 5, f"{s}: rating {rt['s']}★{rt['st']} vs parts {mix:.1f}")
        if o.get("f"):
            A.check("factor", abs(sum(o["f"]["w"].values()) - 100) <= 1, f"{s}: factor weights sum {sum(o['f']['w'].values())}")
    # recency ranks recomputed from weekly closes for one peer group (independent of the build's code path)
    groups: dict[str, list[str]] = {}
    for s, o in XE.items():
        if (o.get("sc") or {}).get("3"):
            groups.setdefault(o["g"], []).append(s)
    for g, members in groups.items():
        def r(s, w):
            a = H["etfs"][s]
            return a[-1] / a[-1 - w] - 1 if a[-1] and a[-1 - w] else None
        vals = {s: (r(s, 13), r(s, 26)) for s in members}
        for s in members:
            mine = []
            for k in (0, 1):
                xs = sorted(v[k] for v in vals.values() if v[k] is not None)
                me = vals[s][k]
                lt = sum(1 for x in xs if x < me)
                eq = sum(1 for x in xs if x == me)
                mine.append((lt + (eq - 1) / 2) / (len(xs) - 1))
            rec = 100 * sum(mine) / 2
            pub = XE[s]["sc"]["3"]["r"]
            A.check("scorecard", abs(rec - pub) <= 0.2, f"{s}: recency {pub} vs recomputed {rec:.1f} (group {g})")
    # holdings
    for s, h in (HO.get("etfs") or {}).items():
        top = [t[2] for t in h.get("top", [])]
        A.check("holdings", all(top[i] <= top[i - 1] + 1e-9 for i in range(1, len(top))), f"{s}: holdings not sorted")
        eq = (h["mix"].get("equity") or 0) + (h["mix"].get("overseas") or 0)
        A.check("holdings", eq >= 60, f"{s}: equity {eq}%")
        if h.get("n", 0) <= 15 and len(top) == h.get("n"):
            A.check("holdings", abs(sum(sorted(top, reverse=True)[:10]) - h["top10"]) <= 0.2, f"{s}: top-10 share {h['top10']}")
        y, m = map(int, h["asOf"].split("-"))
        age = (ad - date(y + (m == 12), m % 12 + 1, 1)).days + 1
        A.check("holdings", age <= 46, f"{s}: portfolio {h['asOf']} is {age} days past month-end")
    # smart invest
    by = {e["s"]: e for e in M["etfs"]}
    for k, sl in (SM.get("slots") or {}).items():
        e = by.get(sl["sym"])
        A.check("smart", e is not None, f"smart {k}: unknown ETF {sl['sym']}")
        if not e:
            continue
        A.check("smart", (e.get("tv") or 0) > 0 and e.get("q") == "ok", f"smart {k}: {sl['sym']} not regularly traded")
        lim = 2.0 if k == "global" else 0.3 if k == "liquid" else 0.75
        A.check("smart", e.get("prem") is None and k != "global" or (e.get("prem") is not None and abs(e["prem"]) <= lim),
                f"smart {k}: {sl['sym']} trades {e.get('prem')}% vs NAV")
    for pid, p in (SM.get("plans") or {}).items():
        A.check("smart", sum(x["w"] for x in p["slots"]) == 100 and all(x["w"] % 5 == 0 for x in p["slots"]), f"smart {pid}: weights")
    # live bars
    if LV and LV.get("bars"):
        ses = LV["session"]
        for s, b in LV["bars"].items():
            e = by.get(s)
            if not e:
                A.check("live", False, f"live: unknown ETF {s}")
                continue
            o, h, l, c, v = b
            A.check("live", h >= max(o, c) - 1e-6 and l <= min(o, c) + 1e-6, f"live {s}: inconsistent bar")
            if ses > (e.get("d") or ""):
                A.check("live", abs(c / e["p"] - 1) <= 0.2, f"live {s}: {c} vs last close {e['p']}")
    # day over day
    pv = prev.get("snapshot") or {}
    if pv:
        A.check("day-over-day", asof >= pv.get("asOf", ""), f"published date went back {pv.get('asOf')} → {asof}")
        gone = [s for s in pv.get("syms", []) if s not in syms]
        A.check("day-over-day", len(gone) <= 5, f"{len(gone)} ETFs disappeared: {gone[:8]}")
        A.check("day-over-day", len(priced) >= 0.9 * pv.get("priced", 0), f"priced ETFs dropped {pv.get('priced')} → {len(priced)}")
        pp = pv.get("px", {})
        for e in priced:
            if e["s"] in pp and pp[e["s"]] and pv.get("asOf") != asof:
                A.check("day-over-day", abs(e["p"] / pp[e["s"]] - 1) <= 0.25 or bool(e.get("f")),
                        f"{e['s']}: price {pp[e['s']]} → {e['p']} since the last audit", warn=True)
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "asOf": asof, "checks": A.n,
           "errors": len(A.errors), "warnings": len(A.warnings), "areas": {k: {"checks": v[0], "issues": v[1]} for k, v in A.by.items()},
           "errorList": A.errors[:50], "warningList": A.warnings[:50],
           "snapshot": {"asOf": asof, "priced": len(priced), "syms": sorted(syms), "px": {e["s"]: e["p"] for e in priced}}}
    with open(OUT + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(OUT + ".tmp", OUT)
    print(f"ETF audit {asof}: {A.n} checks · {len(A.errors)} errors · {len(A.warnings)} warnings")
    for k, v in sorted(A.by.items()):
        print(f"  {k:<13} {v[0]:>6} checks  {v[1]:>4} issues")
    for m in A.errors[:30]:
        print("  ERROR", m)
    for m in A.warnings[:15]:
        print("  warn ", m)
    return 1 if A.errors else 0


if __name__ == "__main__":
    sys.exit(main())
