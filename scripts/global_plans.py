"""Portfolio Simulator — Global ETF: model portfolios from the published data (data/global_etf.json).

Python twin of buildPlan() / evalSlot() in global_etf_momentum.html — the two MUST stay identical. The builder
publishes every plan (goal × risk) in global_etf.json → "plans"; the page recomputes them in the browser and checks
they match ("checks passed" in the status card), and the Simulator Buy engine (gsim_engine.py) buys the 10+ year
plans. Inputs are the rounded, published ETF records, so all three see exactly the same numbers.
"""
import math

NOISE = 1
HORIZONS = ["h1", "h3", "h5", "h10", "h15"]
RISKS = ["c", "b", "a"]
RISK_NAMES = {"c": "Conservative", "b": "Balanced", "a": "Aggressive"}
LONG_GOALS = ("h5", "h10", "h15")

ALLOC = {  # equity, bond (aggregate), short (short Treasuries), gold, cash (T-bills)
    "h1": {"c": {"cash": 100}, "b": {"cash": 100}, "a": {"cash": 100}},
    "h3": {"c": {"cash": 60, "short": 40}, "b": {"cash": 40, "short": 40, "eq": 20}, "a": {"cash": 30, "short": 30, "eq": 40}},
    "h5": {"c": {"eq": 35, "bond": 45, "gold": 10, "cash": 10}, "b": {"eq": 55, "bond": 30, "gold": 10, "cash": 5}, "a": {"eq": 70, "bond": 20, "gold": 10}},
    "h10": {"c": {"eq": 50, "bond": 35, "gold": 10, "cash": 5}, "b": {"eq": 70, "bond": 20, "gold": 10}, "a": {"eq": 85, "bond": 5, "gold": 10}},
    "h15": {"c": {"eq": 60, "bond": 30, "gold": 10}, "b": {"eq": 80, "bond": 10, "gold": 10}, "a": {"eq": 90, "gold": 10}},
}
EQSPLIT = {
    "c": {"us_core": 65, "us_small": 5, "intl": 22, "em": 8},
    "b": {"us_core": 55, "us_small": 10, "intl": 20, "em": 10, "factor": 5},
    "a": {"us_core": 50, "us_small": 12, "intl": 18, "em": 12, "factor": 8},
}
SLOTS = {
    "us_core": {"label": "US large & total market", "grp": "eq", "cands": ["VOO", "IVV", "VTI", "ITOT", "SCHB", "SPY"], "cap": 0.10, "tol": 2.5},
    "us_small": {"label": "US small & mid caps", "grp": "eq", "cands": ["IJR", "VB", "IJH", "VO", "IWM", "MDY"], "cap": 0.25, "tol": None},
    "intl": {"label": "Developed markets ex-US", "grp": "eq", "cands": ["IEFA", "VEA", "EFA"], "cap": 0.35, "tol": 3},
    "em": {"label": "Emerging markets", "grp": "eq", "cands": ["IEMG", "VWO", "EEM"], "cap": 0.75, "tol": 4},
    "factor": {"label": "Factor satellite", "grp": "eq", "cands": ["MTUM", "QUAL", "USMV", "VTV", "VUG", "SCHG", "SCHD", "DGRO", "COWZ"], "cap": 0.60, "tol": None, "momentum": True},
    "bond": {"label": "US investment-grade bonds", "grp": "bond", "cands": ["AGG", "BND"], "cap": 0.10, "tol": 1},
    "short": {"label": "Short Treasuries", "grp": "bond", "cands": ["SHY"], "cap": 0.20, "tol": None},
    "gold": {"label": "Gold", "grp": "gold", "cands": ["GLDM", "IAU", "GLD"], "cap": 0.45, "tol": 1.5},
    "cash": {"label": "Treasury bills", "grp": "cash", "cands": ["SGOV", "BIL"], "cap": 0.20, "tol": 0.5},
}
SLOT_ORDER = list(SLOTS)
ALL_CANDS = sorted({t for s in SLOTS.values() for t in s["cands"]})


def _ema(a, n):
    k = 2.0 / (n + 1); out = []; prev = None
    for v in a:
        prev = v if prev is None else prev + k * (v - prev)
        out.append(prev)
    return out


def engine(etf_w, bench_w, min_weeks=20):
    """Same as the page's engine(): RS-Ratio = 100·EMA3(rs)/SMA10(rs), RS-Mom = 100 + (ratio_t − ratio_t−3)."""
    idx = [i for i in range(len(etf_w)) if etf_w[i] is not None and bench_w[i] is not None and etf_w[i] > 0 and bench_w[i] > 0]
    if len(idx) < min_weeks:
        return None
    rs = [100.0 * etf_w[i] / bench_w[i] for i in idx]
    em = _ema(rs, 3)
    ratio = [None] * len(rs); mom = [None] * len(rs)
    for i in range(9, len(rs)):
        ratio[i] = 100.0 * em[i] / (sum(rs[i - 9:i + 1]) / 10.0)
    for i in range(3, len(rs)):
        if ratio[i] is not None and ratio[i - 3] is not None:
            mom[i] = 100.0 + (ratio[i] - ratio[i - 3])
    n = len(rs) - 1
    r, m = ratio[n], mom[n]
    if r is None or m is None:
        return None
    mode = ("ACC" if m >= 100 else "DEC") if r >= 100 else ("REC" if m >= 100 else "UND")

    def rel(a, b):
        return (rs[n - a] / rs[n - b] - 1) * 100 if n - a >= 0 and n - b >= 0 else None
    rel13, rel4, prev4 = rel(0, 13), rel(0, 4), rel(4, 8)
    return {"ratio": r, "mom": m, "mode": mode, "rel13": rel13,
            "relImp": rel4 - prev4 if rel4 is not None and prev4 is not None else None}


def median(a):
    v = sorted(x for x in a if x is not None)
    if not v:
        return None
    m = len(v) >> 1
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def pct_rank(arr, v, higher_better):
    xs = [x for x in arr if x is not None]
    if len(xs) < 2 or v is None:
        return 0.5
    below = sum(1 for x in xs if (x < v if higher_better else x > v))
    return below / (len(xs) - 1)


def conf_of(e, g):
    if not g:
        return 0
    c = 0
    if g["rel13"] is not None and (g["rel13"] >= 0) == (g["ratio"] >= 100): c += 1
    if g["relImp"] is not None and (g["relImp"] >= 0) == (g["mom"] >= 100): c += 1
    if (e.get("adv") or 0) >= 10e6: c += 1
    if abs(g["ratio"] - 100) >= NOISE or abs(g["mom"] - 100) >= NOISE: c += 1
    return c


def js_round(x):
    return int(math.floor(x + 0.5))


def _r(e, k):
    return (e.get("r") or {}).get(k)


def eval_slot(key, by):
    sl, spy = SLOTS[key], by["SPY"]
    lst = [by[t] for t in sl["cands"] if t in by]
    r1y_med = median([_r(e, "1y") for e in lst])
    vol_med = median([e.get("vol") for e in lst])
    rows = []
    for e in lst:
        g = engine(e["w"], spy["w"]) if sl.get("momentum") else None
        conf = conf_of(e, g) if sl.get("momentum") else None
        weeks = sum(1 for v in (e.get("w") or []) if v is not None)
        ck = [
            ["fresh", not e.get("stale")],
            ["3y", _r(e, "3y") is not None],
            ["adv", (e.get("adv") or 0) >= 20e6],
            ["aum", (e.get("aum") or 0) >= 1e9],
            ["er", e.get("er") is not None and e["er"] <= sl["cap"] + 1e-9],
        ]
        if sl["tol"] is not None and len(lst) > 1:
            d = _r(e, "1y") - r1y_med if _r(e, "1y") is not None and r1y_med is not None else None
            ck.append(["r1y", d is not None and abs(d) <= sl["tol"]])
        if not sl.get("momentum") and len(lst) > 1:
            ck.append(["vol", e.get("vol") is not None and vol_med is not None and e["vol"] <= 1.3 * vol_med + 1e-9])
        ck.append(["weeks", weeks >= 52])
        if sl.get("momentum"):
            ck.append(["acc", bool(g) and g["mode"] == "ACC" and conf >= 3])
        rows.append({"e": e, "g": g, "ck": ck, "pass": all(c[1] for c in ck), "passed": sum(1 for c in ck if c[1])})
    surv = [r for r in rows if r["pass"]]

    def yrs(r):
        return 5 if _r(r["e"], "5y") is not None else 3 if _r(r["e"], "3y") is not None else 1
    for r in surv:
        e = r["e"]
        cost = pct_rank([x["e"].get("er") for x in surv], e.get("er"), False)
        liq = pct_rank([x["e"].get("adv") for x in surv], e.get("adv"), True)
        size = pct_rank([x["e"].get("aum") for x in surv], e.get("aum"), True)
        age = pct_rank([yrs(x) for x in surv], yrs(r), True)
        if sl.get("momentum"):
            cons = pct_rank([x["g"]["ratio"] + 0.5 * x["g"]["mom"] for x in surv], r["g"]["ratio"] + 0.5 * r["g"]["mom"], True)
        else:
            dev = lambda x: abs((_r(x["e"], "1y") if _r(x["e"], "1y") is not None else 0) - (r1y_med if r1y_med is not None else 0))
            cons = pct_rank([dev(x) for x in surv], dev(r), False)
        r["score"] = js_round(100 * (0.35 * cost + 0.25 * liq + 0.20 * size + 0.10 * age + 0.10 * cons))
    surv.sort(key=lambda r: (-r["score"], r["e"].get("er") if r["e"].get("er") is not None else 9))
    return {"key": key, "rows": rows, "pick": surv[0] if surv else None}


def build_plan(by, h, risk):
    base = dict(ALLOC[h][risk]); notes = []; long_goal = h in LONG_GOALS
    spy = by["SPY"]
    if long_goal and base.get("eq") and spy.get("trend") and spy["trend"][2] == -1:
        s = min(10, base["eq"]); base["eq"] -= s; base["bond"] = base.get("bond", 0) + s
        notes.append(["overlay", s])
    w = {}
    if base.get("eq"):
        split = {"us_core": 100} if h == "h3" else EQSPLIT[risk]
        for k, v in split.items():
            w[k] = base["eq"] * v / 100
        if not long_goal:
            w.pop("factor", None)
    for k in ("bond", "short", "gold", "cash"):
        if base.get(k):
            w[k] = base[k]
    res = {k: eval_slot(k, by) for k in w}
    for k in list(w):
        if res[k]["pick"] or not w[k]:
            continue
        to = "us_core" if SLOTS[k]["grp"] == "eq" else "cash"
        if k == to:
            continue
        if to not in res:
            res[to] = eval_slot(to, by)
        w[to] = w.get(to, 0) + w[k]
        notes.append(["moved", k, to, w[k]])
        w[k] = 0
    rows = []
    for k in [k for k in w if w[k] > 0]:
        r = res[k]
        pick = r["pick"] or (sorted(r["rows"], key=lambda x: -x["passed"])[0] if r["rows"] else None)
        if not r["pick"] and pick:
            notes.append(["best", k, pick["e"]["t"]])
        if pick:
            rows.append({"k": k, "w": w[k], "t": pick["e"]["t"], "ok": bool(r["pick"])})
    rows.sort(key=lambda x: SLOT_ORDER.index(x["k"]))
    tot = sum(x["w"] for x in rows)
    for x in rows:
        x["w"] = x["w"] / tot * 100
    return {"rows": rows, "notes": notes}


def all_plans(etfs):
    """{pid: {"rows": [{k, w, t, ok}], "notes": [...]}} for every goal × risk, pid = h10b etc. Weights rounded to 4 dp."""
    by = {e["t"]: e for e in etfs}
    if "SPY" not in by:
        return {}
    out = {}
    for h in HORIZONS:
        for r in RISKS:
            p = build_plan(by, h, r)
            for x in p["rows"]:
                x["w"] = round(x["w"], 4)
            out[h + r] = p
    return out
