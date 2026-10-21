"""Optional market-dip buys — Portfolio Simulator, Global ETF (the global twin of the India market-dip lump sums).

For each segment, the official daily close of a tracker ETF is measured against its highest close of the last 63
sessions. A fall of 5% / 10% / 15% that has held for two closes, is confirmed by a second ETF on the same market and
passes the market checks below is a dip signal; the page sizes the optional extra buy as ½× / 1× / 2× the reader's
regular purchase and requires the plan's model ETF for that segment to pass all of its own checks.

Used by build_global_etf.py (published as global_etf.json → "dip"); runs on the published daily file too:
    python3 scripts/global_dip.py   → prints the block for data/global_etf_daily.json
Descriptive, forward-looking signals only — not a forecast and not advice.
"""
import json, math, os, sys

TIERS = [5, 10, 15]
MULT = [0.5, 1, 2]
WINDOW = 63
SEGMENTS = [
    # key, name, plan slot, trackers (primary, confirmation), macro valuation key
    ("large", "US large caps (S&P 500)", "us_core", ("SPY", "IVV"), "g_spx"),
    ("small", "US mid caps (S&P 400)", "us_small", ("IJH", "MDY"), "g_spx"),
    ("intl", "Developed markets ex-US", "intl", ("EFA", "IEFA"), "g_eur"),
    ("em", "Emerging markets", "em", ("EEM", "IEMG"), "g_em"),
    ("gold", "Gold", "gold", ("GLD", "IAU"), None),
    # satellites — not in the model mixes; optional dip buys for Aggressive / Very aggressive goals of 5+ years only,
    # at half the core model amount (the page applies both rules)
    ("latam", "Latin America", "latam", ("ILF", "FLLA"), None),
    ("europe", "Europe", "europe", ("VGK", "IEUR"), "g_eur"),
    ("japan", "Japan", "japan", ("EWJ", "BBJP"), "g_n225"),
    ("india", "India", "india", ("INDA", "EPI"), None),
    ("reit", "US real estate (REITs)", "reit", ("VNQ", "SCHH"), None),
    ("longbond", "Long-term Treasuries", "longbond", ("TLT", "VGLT"), None),
    ("energy", "Energy", "energy", ("XLE", "VDE"), None),
]
SATELLITES = ("latam", "europe", "japan", "india", "reit", "longbond", "energy")
LIM = {"confirmPts": 1.5, "crash": -8, "maxFall": 40, "d5Min": -12, "dd52Max": 30, "down10Max": 7, "vixMax": 35,
       "eyGapMin": -2.5, "goldPctMax": 0.9, "goldVs200Max": 15, "vs200Max": 15}


def _series(dates, c):
    return [(d, v) for d, v in zip(dates, c) if v]


def walk(pts, upto=None):
    """Fall % from the highest close of the last WINDOW sessions for each session (by index)."""
    out = []
    for i in range(len(pts)):
        lo = max(0, i - WINDOW + 1)
        hi_i = max(range(lo, i + 1), key=lambda k: pts[k][1])
        out.append(((1 - pts[i][1] / pts[hi_i][1]) * 100, pts[hi_i][0], pts[hi_i][1]))
    return out


def held_tier(f_today, f_prev):
    t = 0
    for x in TIERS:
        if f_today >= x and f_prev >= x:
            t = x
    return t


def segment(dates, closes, key, name, slot, trackers, vkey, macro):
    p = _series(dates, closes.get(trackers[0]) or [])
    q = dict(_series(dates, closes.get(trackers[1]) or []))
    if len(p) < 220:
        return None
    w = walk(p)
    n = len(p) - 1
    fall, hd, hv = w[n]
    prev = w[n - 1][0]
    held = held_tier(fall, prev)
    raw = max([x for x in TIERS if fall >= x], default=0)
    # current fall episode: from its high; the deepest level held before today
    start = max(i for i in range(n + 1) if p[i][0] == hd)
    before = 0
    last_sig = None
    for i in range(max(start + 1, 1), n):
        h = held_tier(w[i][0], w[i - 1][0])
        if h > before:
            before = h
            last_sig = {"d": p[i][0], "tier": h}
    signal = held > before
    # confirmation by the second tracker
    qp = [(d, q[d]) for d, _ in p if d in q]
    qf = None
    if len(qp) >= WINDOW * 0.9 and qp[-1][0] == p[n][0]:
        qf = walk(qp)[-1][0]
    confirmed = qf is not None and qf >= (held or raw) - LIM["confirmPts"] if (held or raw) else qf is not None
    day = (p[n][1] / p[n - 1][1] - 1) * 100
    d5 = (p[n][1] / p[n - 5][1] - 1) * 100
    hi52 = max(v for _, v in p[-252:])
    dd52 = (1 - p[n][1] / hi52) * 100
    down10 = sum(1 for i in range(n - 9, n + 1) if p[i][1] < p[i - 1][1])
    ma = lambda k: sum(v for _, v in p[k - 199:k + 1]) / 200
    ma_up = ma(n) >= ma(n - 20)
    g = (macro or {}).get("global") or {}
    E = ((macro or {}).get("growth") or {}).get("gidx", {}).get("earnings", {})
    vix = (g.get("vix") or {}).get("last")
    us10 = (g.get("us10y") or {}).get("last")
    checks = [
        [f"Fall from the 3-month high reaches {TIERS[0]}% or more", raw >= TIERS[0], f"{fall:.2f}% below {hv:.2f} ({hd})"],
        ["The level has held for two closes", held >= TIERS[0], f"today {fall:.2f}% · previous close {prev:.2f}%"],
        ["First close at this level in the current fall", signal or held == 0, (f"new level {held}%" if signal else f"already reached on {last_sig['d']}" if last_sig else "–")],
        [f"Confirmed by {trackers[1]} (within {LIM['confirmPts']} pts)", bool(confirmed), f"{trackers[1]} {qf:.2f}% below its high" if qf is not None else "no close"],
        [f"Not a crash day (day's move ≥ {LIM['crash']}%)", day >= LIM["crash"], f"{day:+.2f}%"],
        [f"Fall not deeper than {LIM['maxFall']}%", fall <= LIM["maxFall"], f"{fall:.2f}%"],
        [f"5-session move ≥ {LIM['d5Min']}% (no panic selling)", d5 >= LIM["d5Min"], f"{d5:+.2f}%"],
        [f"No more than {LIM['dd52Max']}% below the 52-week high", dd52 <= LIM["dd52Max"], f"{dd52:.2f}%"],
        [f"Not a falling streak (≤ {LIM['down10Max']} lower closes in 10)", down10 <= LIM["down10Max"], f"{down10} of 10"],
        ["200-day average rising vs 20 sessions ago", ma_up, f"{ma(n):.2f} vs {ma(n - 20):.2f}"],
        [f"Market fear contained (VIX ≤ {LIM['vixMax']})", vix is not None and vix <= LIM["vixMax"], f"VIX {vix:.1f}" if vix is not None else "–"],
    ]
    if vkey:
        ey = (E.get(vkey) or {}).get("ey")
        gap = ey - us10 if ey is not None and us10 is not None else None
        checks.append([f"Valuation: earnings yield ≥ US 10Y {LIM['eyGapMin']} pts", gap is not None and gap >= LIM["eyGapMin"],
                       f"{ey:.2f}% vs {us10:.2f}% ({gap:+.2f} pts)" if gap is not None else "–"])
    elif key != "gold":
        v200 = (p[n][1] / ma(n) - 1) * 100
        checks.append([f"Not stretched: no more than +{LIM['vs200Max']}% above its 200-day average", v200 <= LIM["vs200Max"], f"{v200:+.1f}% vs 200-day"])
    else:
        gd = g.get("gold") or {}
        checks.append([f"Gold not stretched (2-year percentile < {int(LIM['goldPctMax'] * 100)}, ≤ +{LIM['goldVs200Max']}% vs 200-day)",
                       gd.get("pct2y") is not None and gd["pct2y"] < LIM["goldPctMax"] and (gd.get("vs200") or 0) <= LIM["goldVs200Max"],
                       f"{round((gd.get('pct2y') or 0) * 100)}th · {gd.get('vs200', 0):+.1f}% vs 200-day" if gd else "–"])
    mkt_ok = all(c[1] for c in checks)
    return {"name": name, "slot": slot, "kind": "sat" if key in SATELLITES else "core", "trackers": list(trackers), "d": p[n][0], "close": round(p[n][1], 4),
            "high": round(hv, 4), "highDate": hd, "fall": round(fall, 2), "prevFall": round(prev, 2), "raw": raw, "held": held,
            "signal": bool(signal and mkt_ok), "lastSignal": last_sig, "checks": checks, "mktOk": mkt_ok}


def dip_block(daily, macro):
    dates, closes = daily["dates"], daily["c"]
    segs = {}
    for key, name, slot, tr, vk in SEGMENTS:
        s = segment(dates, closes, key, name, slot, tr, vk, macro)
        if s:
            segs[key] = s
    return {"v": 1, "asOf": daily.get("asOf"), "tiers": TIERS, "mult": MULT, "window": WINDOW, "lim": LIM, "segments": segs}


if __name__ == "__main__":
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    daily = json.load(open(os.path.join(root, "global_etf_daily.json")))
    macro = json.load(open(os.path.join(root, "mf", "macro.json"))) if os.path.exists(os.path.join(root, "mf", "macro.json")) else {}
    b = dip_block(daily, macro)
    for k, s in b["segments"].items():
        print(k, s["fall"], s["held"], s["signal"], s["mktOk"], [c[0][:30] for c in s["checks"] if not c[1]])
    if "--write" in sys.argv:
        p = os.path.join(root, "global_etf.json")
        d = json.load(open(p)); d["dip"] = b
        json.dump(d, open(p, "w"), separators=(",", ":"), allow_nan=False)
        print("written")
