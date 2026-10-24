#!/usr/bin/env python3
"""
dip_rules.py — market-dip lump sums, shared by the Portfolio Simulator builds (build_smart_sip.py,
build_etf_smart.py) and the Simulator Buy engine. One source of truth: sim_config.json → "dipRule".

Signal (per segment: large / mid / small cap, gold, silver), from official closes of the segment's index tracker:
  fall     = how far the close is below the highest close of the last `lookback` sessions (≈ 3 months)
  tier     = 5% → ₹5,000 · 10% → ₹10,000 · 15% → ₹20,000 (sim_config dipRule tiers) (never below `min`, never above `max`)
  buy day  = the first close at a deeper tier in the current fall (at most one buy per tier); the fall ends when
             the index is back within `resetPct` of its high, and tiers start again
  confirm  = a second tracker of the same index shows the same fall (± `confirmPts`), the day's own move is not
             worse than `crashDayPct` (a crash day / bad print waits a session) and the fall is within `maxFallPct`
A buy day that is not confirmed does not use up its tier, so the next confirmed close at that tier can still buy.

37 checks before any dip lump sum: 8 market-trigger, 14 market/valuation and 15 fund checks.
The agents recompute the trigger checks from recorded prices themselves.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RULE = json.loads((ROOT / "scripts" / "sim_config.json").read_text())["dipRule"]
V = RULE["value"]
SIM_START = json.loads((ROOT / "scripts" / "sim_config.json").read_text())["start"]     # signals count only after it                      # valuation limits (checks 9, 10, 14; metals 9, 10)


def tier_of(fall: float) -> tuple[int, int]:
    """(tier %, amount ₹) for a fall in % — the deepest tier reached, (0, 0) below the first."""
    for t, amt in RULE["tiers"]:
        if fall + 1e-9 >= t:  # avoid 100→90 computing as 9.999999999999998%
            return t, max(RULE["min"], min(RULE["max"], amt))
    return 0, 0


def load_closes(sym: str) -> list[tuple[str, float]]:
    """Official daily closes of an exchange-traded fund from the published daily price file."""
    try:
        b = json.loads((DATA / "etf" / "d" / f"{sym}.json").read_text())
    except Exception:  # noqa: BLE001
        return []
    return [(f"{t // 10000:04d}-{t // 100 % 100:02d}-{t % 100:02d}", c) for t, c in zip(b["t"], b["c"]) if c]


def walk(closes: list[tuple[str, float]], second: dict) -> list[dict]:
    """Every session's dip state, in date order. `closes` = [(iso date, close)] of the tracker, `second` = {iso: close}
    of the confirming tracker. The state only depends on the series given, so the agents' engine, the audit and
    the page builds agree when they read the same closes.

    A level only counts once the fall has HELD for two closes: `tier` is the deepest level reached by both today's and
    the previous close (`raw` is today's alone), so a one-day dip that recovers the next session never buys."""
    lb, out, ep, ep_d, prev_raw = RULE["lookback"], [], 0, None, 0
    for i in range(len(closes)):
        if i + 1 < lb:
            continue
        d, c = closes[i]
        win = closes[i - lb + 1:i + 1]
        hi_d, hi = max(win, key=lambda x: (x[1], x[0]))
        fall = (1 - c / hi) * 100
        day = (c / closes[i - 1][1] - 1) * 100
        w2 = [v for v in (second.get(x) for x, _ in win) if v]
        # the second tracker needs its own close that day and ≥ 90% of the window's sessions
        fall2 = (1 - second[d] / max(w2)) * 100 if second.get(d) and len(w2) >= 0.9 * lb else None
        raw = tier_of(fall)[0]
        t = min(raw, prev_raw)                       # held for two closes
        amt = dict(RULE["tiers"]).get(t, 0) if t else 0
        amt = max(RULE["min"], min(RULE["max"], amt)) if t else 0
        prev_raw = raw
        if fall < RULE["resetPct"]:
            ep, ep_d = 0, None
        before = ep
        conf = fall2 is not None and abs(fall2 - fall) <= RULE["confirmPts"]
        sane = day >= RULE["crashDayPct"] and fall <= RULE["maxFallPct"]
        sig = t > ep and conf and sane
        if sig:
            ep, ep_d = t, d
        out.append({"d": d, "close": c, "high": hi, "highDate": hi_d, "fall": fall, "fall2": fall2, "day": day,
                    "raw": raw, "tier": t, "amount": amt, "epBefore": before, "ep": ep, "epDate": ep_d,
                    "conf": conf, "sane": sane, "signal": sig})
    return out


def trend(closes: list[tuple[str, float]]) -> dict:
    """5-session move and the fall from the 52-week (≈250-session) high — market checks 17–18."""
    if len(closes) < 6:
        return {}
    c = [x[1] for x in closes]
    hi = max(c[-250:])
    out = {"d5": round((c[-1] / c[-6] - 1) * 100, 2), "dd52": round((1 - c[-1] / hi) * 100, 2), "n52": min(250, len(c))}
    if len(c) >= 11:
        out["down10"] = sum(1 for i in range(len(c) - 10, len(c)) if c[i] < c[i - 1])
    if len(c) >= 220:
        sma = lambda k: sum(c[len(c) - k - 200:len(c) - k]) / 200        # noqa: E731
        out["sma200"], out["sma200Prev"] = round(sma(0), 4), round(sma(20), 4)
    return out


def segment_states(syms_from: str | None = None) -> dict:
    """Latest dip state of every segment plus its buy days since the Simulator Buy start (public pages)."""
    out, start = {}, SIM_START
    for key, s in RULE["segments"].items():
        cl = load_closes(s["trk"])
        if syms_from:
            cl = [x for x in cl if x[0] >= syms_from]
        st = walk(cl, dict(load_closes(s["trk2"])))
        if not st:
            continue
        last = st[-1]
        sigs = [{"d": x["d"], "tier": x["tier"], "fall": round(x["fall"], 2), "amount": x["amount"]}
                for x in st if x["signal"] and x["d"] >= start][-6:]
        out[key] = {"label": s["label"], "index": s["index"], "trk": s["trk"], "trk2": s["trk2"],
                    **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in last.items()},
                    "epBeforeStart": bool(last["ep"] and (last["epDate"] or "") < start), "recent": sigs, **trend(cl)}
    return out


def _chk(label, ok, detail):
    return [label, bool(ok), detail]


N_TRIG, N_MKT, N_FUND = 8, 14, 15       # checks 1–8 trigger · 9–22 market & valuation · 23–37 fund / ETF
N_ALL = N_TRIG + N_MKT + N_FUND


def _trend_checks(st: dict) -> list:
    """Market checks 20–21 for every segment: no falling streak, 200-day average still rising."""
    dn, a, b = st.get("down10"), st.get("sma200"), st.get("sma200Prev")
    return [_chk("No falling streak (last 10 closes)", dn is not None and dn <= V["down10Max"],
                 f"{dn} of the last 10 closes were lower than the day before (limit {V['down10Max']})" if dn is not None else "not enough closes"),
            _chk("200-day average still rising", a is not None and b is not None and a >= b,
                 f"200-day average {a:,.2f} vs {b:,.2f} twenty sessions ago ({(a / b - 1) * 100:+.2f}%)" if a and b else "not enough closes (needs 220)")]


def trigger_checks(st: dict, data_date: str) -> list:
    """Checks 1–8 (the market trigger) for one segment state — the agents recompute these from recorded closes."""
    t, amt = st["tier"], st["amount"]
    first = min(x for x, _ in RULE["tiers"])
    age = (date.fromisoformat(data_date) - date.fromisoformat(st["d"])).days
    reached = "first close at this level in the current fall" if st["signal"] else (
        f"the {st['ep']}% level was already used in this fall — next buy only at a deeper level" if st["ep"] and t and t <= st["ep"] else "no new level today")
    return [
        _chk(f"Fall from 3-month high ≥ {first}%", st["fall"] >= first, f"{st['fall']:.2f}% below the highest close {st['high']:.2f} ({st['highDate']})"),
        _chk("Official close up to date", age <= 5, f"close of {st['d']} ({age} days before the latest data)"),
        _chk("Fall held for two closes (not a one-day dip)", t > 0 and t >= min(st.get("raw", t), t),
             f"today {st['fall']:.2f}% · the previous close was also at the {t}% level or deeper" if t else
             (f"today {st['fall']:.2f}% — waits for a second close at {st.get('raw')}%+" if st.get("raw") else "no level reached")),
        _chk("Fall confirmed by a second tracker", st["conf"],
             f"second tracker {st['fall2']:.2f}% (within {RULE['confirmPts']} pt)" if st["fall2"] is not None else "second tracker has no close that day (or too few in the window)"),
        _chk("Not a crash-day print", st["day"] >= RULE["crashDayPct"], f"day's move {st['day']:+.2f}% (limit {RULE['crashDayPct']:.0f}%)"),
        _chk(f"Fall within {RULE['maxFallPct']:.0f}%", st["fall"] <= RULE["maxFallPct"], f"{st['fall']:.2f}%"),
        _chk("Dip level and amount", t > 0, f"{t}% level → ₹{amt:,}" if t else "below the first level — no dip amount"),
        _chk("New level in this fall", st["signal"], reached),
    ]


def valuation_checks(seg: str, macro: dict, gate: dict | None, metal_choice: str | None, extra: tuple, st: dict | None = None, config: dict | None = None) -> list:
    """Checks 9–18 (market & valuation). `extra` = (label, ok, detail) for check 15 (fund P/E for funds, index match
    for ETFs); `st` = the segment state (5-session move and fall from the 52-week high for checks 17–18)."""
    s = config if config is not None else RULE["segments"][seg]
    st = st or {}
    val, n50 = (macro.get("valuation") or {}), (macro.get("valuation") or {}).get("n50") or {}
    gr = macro.get("growth") or {}
    gs, gthr = gr.get("score"), gr.get("thr") or 4
    glob = macro.get("global") or {}
    vix = (glob.get("vix") or {}).get("last")
    g9 = _chk("Model not pausing this segment", (gate or {}).get("now") not in ("pause", "zero", "0"),
              f"valuation gate: {(gate or {}).get('now', 'not gated')}")
    n50pct = n50.get("pePct")
    c16 = _chk("Broad market not overheated", n50pct is not None and n50pct < V["n50PctMax"],
               f"Nifty 50 P/E at the {round((n50pct or 0) * 100)}th percentile of 10 years (limit {round(V['n50PctMax'] * 100)}th)" if n50pct is not None else "no valuation on file")
    c17 = _chk("No panic selling (5-session move)", st.get("d5") is not None and st["d5"] >= V["d5Min"],
               f"{st['d5']:+.2f}% over the last 5 sessions (limit {V['d5Min']:+.0f}% — a faster fall waits for calmer closes)" if st.get("d5") is not None else "not enough closes")
    c18 = _chk("Long-term trend intact (52-week high)", st.get("dd52") is not None and st["dd52"] <= V["dd52Max"],
               f"{st['dd52']:.2f}% below the highest close of the last {st.get('n52', 250)} sessions (limit {V['dd52Max']:.0f}%)" if st.get("dd52") is not None else "not enough closes")
    if s.get("val"):
        v = val.get(s["val"]) or {}
        pe, pct, med, pbp = v.get("pe"), v.get("pePct"), v.get("peMed"), v.get("pbPct")
        g10 = ((macro.get("rates") or {}).get("g10") or {}).get("last")
        ey = 100 / pe if pe else None
        eg = ((macro.get("growth") or {}).get("earnings") or {}).get(s["val"]) or {}
        return [g9,
                _chk(f"P/E below the {round(V['pePctMax'] * 100)}th percentile", pct is not None and pct < V["pePctMax"], f"{s['index']} P/E {pe} at the {round((pct or 0) * 100)}th percentile of 10 years" if pct is not None else "no valuation on file"),
                _chk(f"P/E within {V['peMedMax']:g}× its 10-year median", pe and med and pe <= V["peMedMax"] * med, f"P/E {pe} vs median {med}" if pe and med else "no valuation on file"),
                _chk(f"P/B below the {round(V['pbPctMax'] * 100)}th percentile", pbp is not None and pbp < V["pbPctMax"], f"P/B {v.get('pb')} at the {round((pbp or 0) * 100)}th percentile of 10 years" if pbp is not None else "no valuation on file"),
                _chk("Earnings yield vs 10-year G-Sec", ey is not None and g10 is not None and ey - g10 >= s["eyGapMin"],
                     f"{ey:.2f}% vs {g10:.2f}% (gap {ey - g10:+.2f} pt, limit {s['eyGapMin']:+.1f})" if ey and g10 else "not on file"),
                _chk("Earnings not collapsing", eg.get("g1") is not None and eg["g1"] >= -15, f"12-month earnings growth {eg['g1']:+.1f}% (limit −15%)" if eg.get("g1") is not None else "no earnings history"),
                _chk(*extra), c16, c17, c18,
                _chk("Economy & earnings checks not negative", gs is not None and gs > -gthr,
                     f"score {gs:+d} of {len(gr.get('checks') or [])} checks (headwind at −{gthr})" if gs is not None else "not on file"),
                *_trend_checks(st),
                _chk(f"Market fear not extreme (VIX ≤ {V['vixMax']:g})", vix is not None and vix <= V["vixMax"], f"global volatility index {vix:.1f}" if vix is not None else "not on file")]
    gl = ((macro.get("global") or {}).get(s["metal"]) or {})
    dx = ((macro.get("global") or {}).get("dxy") or {}).get("c3m")
    inr = (glob.get("usdinr") or {}).get("c3m")
    u10 = (glob.get("us10y") or {}).get("c3m")
    return [g9,
            _chk("Price not at a 2-year extreme", gl.get("pct2y") is not None and gl["pct2y"] < V["metalPctMax"], f"{round((gl.get('pct2y') or 0) * 100)}th percentile of 2 years (limit {round(V['metalPctMax'] * 100)}th)" if gl.get("pct2y") is not None else "not on file"),
            _chk("Not stretched above its 200-day average", gl.get("vs200") is not None and gl["vs200"] <= V["metalVs200Max"], f"{gl['vs200']:+.1f}% vs 200-day average (limit +{V['metalVs200Max']:g}%)" if gl.get("vs200") is not None else "not on file"),
            _chk("Model's metal choice", metal_choice == s["metal"], f"model holds {metal_choice or 'no metal'}"),
            _chk("12-month trend not broken", gl.get("c12m") is not None and gl["c12m"] > -25, f"12-month change {gl['c12m']:+.1f}% (limit −25%)" if gl.get("c12m") is not None else "not on file"),
            _chk("US dollar not surging", dx is not None and dx <= V["dxy3mMax"], f"dollar index {dx:+.1f}% over 3 months (limit +{V['dxy3mMax']:g}%)" if dx is not None else "not on file"),
            _chk(*extra), c16, c17, c18,
            _chk(f"Rupee not surging (USD/INR 3 months ≥ {V['inr3mMin']:+g}%)", inr is not None and inr >= V["inr3mMin"],
                 f"USD/INR {inr:+.1f}% over 3 months — a fast-rising rupee lowers the rupee price of {s['metal']}" if inr is not None else "not on file"),
            *_trend_checks(st),
            _chk(f"US 10-year yield not jumping (≤ +{V['us10y3mMax']:g} pt in 3 months)", u10 is not None and u10 <= V["us10y3mMax"],
                 f"US 10-year yield {u10:+.2f} pt over 3 months" if u10 is not None else "not on file")]


def _med(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    return xs[len(xs) // 2] if xs else None


def mf_purchase(f: dict) -> dict:
    """Fresh lump sums, not existing SIP instalments. A published NAV never proves availability."""
    if str(f.get("code")) == "118663":
        return {"state": "paused", "lump": False, "label": "Fresh lump-sum purchases paused",
                "detail": "From 16 Oct 2026: fresh/additional lump sums, switch-ins and new SIP/STP registrations suspended; existing registered SIP/STP instalments may continue.",
                "source": "https://mf.nipponindiaim.com/InvestorServices/Addenda/79-Restriction-on-subsscription-of-Gold-savings-fund.pdf",
                "effective": "2026-10-16"}
    buy = f.get("buy")
    if not isinstance(buy, str):
        return {"state": "unknown", "lump": False, "label": "Fresh purchase status unverified", "detail": "No positive lump-sum eligibility flag in the current screener."}
    if "L" not in buy:
        return {"state": "paused", "lump": False, "label": "Fresh lump-sum purchases paused", "detail": "The current screener does not permit fresh lump-sum orders; existing SIPs are a separate transaction type."}
    return {"state": "open", "lump": True, "label": "Lump sums accepted", "detail": "Current screener flag allows fresh lump sums; confirm the AMC terms before an order."}


def mf_fund_checks(slot: dict, f: dict, peers: list[dict], exit_rule, tier_amt: int, asof: str | None = None) -> list:
    """Checks 23–37 for a mutual fund (screener row `f`, same-category `peers`)."""
    ter_m, r3_m, mdd_m = _med([p.get("ter") for p in peers]), _med([p.get("r3y") for p in peers]), _med([p.get("mdd") for p in peers])
    r1_m, sh_m = _med([p.get("r1y") for p in peers]), _med([p.get("sharpe") for p in peers])
    nav_last = asof or max((p.get("navDate") or "" for p in peers), default="") or f.get("navDate") or ""
    nav_age = (date.fromisoformat(nav_last) - date.fromisoformat(f["navDate"])).days if f.get("navDate") and nav_last else None
    sc = slot.get("checks") or []
    er = exit_rule
    long_load = er.get("days", 0) > 365 or any(p > 1 for _, p in er.get("tiers", []))
    return [
        _chk("Model's choice for this segment", True, f"{slot.get('label')} — {f.get('name')}"),
        _chk("Passes every check of its model slot", sc and all(c[1] for c in sc), f"{sum(1 for c in sc if c[1])} of {len(sc)} slot checks"),
        _chk("Open for lump-sum purchases", mf_purchase(f)["lump"], mf_purchase(f)["label"] + ": " + mf_purchase(f)["detail"]),
        _chk("Lump-sum minimum ≤ ₹5,000", isinstance(f.get("lumpMin"), (int, float)) and 0 < f["lumpMin"] <= RULE["min"], f"₹{f['lumpMin']:,} minimum" if f.get("lumpMin") is not None else "minimum not disclosed"),
        _chk("Exit load ≤ 1% and within 12 months", er.get("known", False) and not long_load, "terms unverified" if not er.get("known") else "nil" if not er.get("tiers") else ", ".join(f"{p}% within {d} days" for d, p in er["tiers"])),
        _chk("Expense ratio ≤ category median", f.get("ter") is not None and ter_m is not None and f["ter"] <= ter_m + 1e-9, f"{f.get('ter')}% vs median {ter_m}%"),
        _chk("Fund size ≥ ₹500 cr", (f.get("aum") or 0) >= 500, f"₹{round(f.get('aum') or 0):,} cr"),
        _chk("Track record ≥ 3 years", f.get("r3y") is not None, "3-year return on file" if f.get("r3y") is not None else "under 3 years"),
        _chk("3-year return near or above category median", f.get("r3y") is not None and r3_m is not None and f["r3y"] >= r3_m - 1, f"{f.get('r3y')}% a year vs median {r3_m}%"),
        _chk("Worst fall no deeper than category median − 5 pt", f.get("mdd") is not None and mdd_m is not None and f["mdd"] >= mdd_m - 5, f"{f.get('mdd')}% vs median {mdd_m}%"),
        _chk("Status not lagging", bool(f.get("status")) and f.get("status") not in ("Underperforming", "Out of track"), f.get("status") or "not rated"),
        _chk("1-year return near or above category median", f.get("r1y") is not None and r1_m is not None and f["r1y"] >= r1_m - 2,
             f"{f.get('r1y')}% vs median {r1_m}% (within 2 pt)"),
        _chk("Risk-adjusted return (Sharpe) near category median", f.get("sharpe") is not None and sh_m is not None and f["sharpe"] >= sh_m - 0.1,
             f"Sharpe {f.get('sharpe')} vs median {sh_m} (within 0.1)"),
        _chk("NAV up to date", nav_age is not None and 0 <= nav_age <= 5, f"NAV of {f.get('navDate')}" + (f" ({nav_age} days behind published data)" if nav_age else "")),
        _chk("Dip amount within ₹5,000–₹20,000", tier_amt > 0 and RULE["min"] <= tier_amt <= RULE["max"], f"₹{tier_amt:,} at the current fall" if tier_amt else "no dip tier reached"),
    ]


def etf_fund_checks(slot: dict, e: dict, ex: dict, bars_v: list, cap: float, tier_amt: int, te_med: dict | None = None) -> list:
    """Checks 23–37 for an ETF (`e` = momentum row, `ex` = analytics row, `bars_v` = last daily volumes)."""
    sc = slot.get("checks") or []
    x = e.get("x") or {}
    te = (ex or {}).get("te") or {}
    tm = (te_med or {}).get(te.get("idx")) or te.get("te") or 0
    nav_age = (date.fromisoformat(e["d"]) - date.fromisoformat(x["navDate"])).days if x.get("navDate") and e.get("d") else None
    rt = (ex or {}).get("rt") or {}
    first = e.get("first")
    yrs = (date.fromisoformat(e["d"]) - date.fromisoformat(first)).days / 365.25 if first and e.get("d") else 0
    ter = x.get("ter")
    return [
        _chk("Model's choice for this segment", True, f"{slot.get('label')} — {e.get('n')}"),
        _chk("Passes every check of its model slot", sc and all(c[1] for c in sc), f"{sum(1 for c in sc if c[1])} of {len(sc)} slot checks"),
        _chk("Traded every session (last 20)", len(bars_v) >= 20 and all(v > 0 for v in bars_v[-20:]), f"{sum(1 for v in bars_v[-20:] if v > 0)} of 20 sessions"),
        _chk("Liquid: ≥ ₹1 cr traded a day", (e.get("tv") or 0) >= 1, f"₹{e.get('tv') or 0:,.1f} cr a day"),
        _chk("Price within ±0.75% of NAV", e.get("prem") is not None and abs(e["prem"]) <= 0.75, f"{e.get('prem'):+.2f}% vs NAV" if e.get("prem") is not None else "NAV not on file"),
        _chk(f"Expense ratio ≤ {cap:.2f}%", ter is not None and ter <= cap, f"{ter}%" if ter is not None else "not disclosed"),
        _chk("Tracking quality", (rt.get("p") or {}).get("trk", 0) >= 50, f"tracking & pricing score {(rt.get('p') or {}).get('trk', '–')} of 100"),
        _chk("Fund size ≥ ₹100 cr", (x.get("aum") or 0) >= 100, f"₹{round(x.get('aum') or 0):,} cr"),
        _chk("Track record ≥ 1 year", yrs >= 1, f"{yrs:.1f} years listed"),
        _chk("Rating ≥ 3★", (rt.get("st") or 0) >= 3, f"{rt.get('st') or '–'}★"),
        _chk("One unit costs ≤ ₹5,000", (e.get("p") or 0) <= RULE["min"], f"₹{e.get('p') or 0:,.2f} a unit"),
        _chk("Tracking error ≤ 1.25× same-index ETFs", te.get("te") is None or te["te"] <= 1.25 * max(tm, 0.5),
             f"{te['te']:.2f}% vs median {tm:.2f}% of {te.get('n', 0)} ETFs on the same index" if te.get("te") is not None
             else "not measured against peers — the model's own tracking check applies (check 24)"),
        _chk("1-year tracking difference within ±1%", te.get("td1") is None or abs(te["td1"]) <= 1,
             f"{te['td1']:+.2f}% a year vs same-index ETFs" if te.get("td1") is not None else "not measured against peers — the model's own tracking check applies (check 24)"),
        _chk("NAV up to date", nav_age is not None and nav_age <= 5, f"NAV of {x.get('navDate')} for the {e.get('d')} close" if x.get("navDate") else "NAV not on file"),
        _chk("Dip amount within ₹5,000–₹20,000", tier_amt > 0 and RULE["min"] <= tier_amt <= RULE["max"], f"₹{tier_amt:,} at the current fall" if tier_amt else "no dip tier reached"),
    ]


def verdict(checks: list) -> dict:
    """All 37 → buy today; checks 9–36 → the market and the fund are fit for a dip buy (what the agents read)."""
    return {"n": len(checks), "passed": sum(1 for c in checks if c[1]), "ok": all(c[1] for c in checks),
            "fundOk": all(c[1] for c in checks[8:-1]), "fail": [c[0] for c in checks if not c[1]]}


# ───────────────────────────── published blocks (page builds) ─────────────────────────────
# the index each ETF slot must track (check 13 for ETFs) — matched against the ETF's name / benchmark / underlying
INDEX_RX = {"large": r"nifty\s*50\b(?!.*(value|equal|quality|alpha|momentum|low\s*vol|next|shariah|dividend))",
            "mid": r"midcap\s*150", "small": r"smallcap\s*250", "gold": r"\bgold\b", "silver": r"\bsilver\b"}


def metal_of(name: str) -> str:
    return "silver" if "silver" in (name or "").lower() else "gold"


def _segments(asof: str, macro: dict | None = None, gates: dict | None = None, metal_choice: str | None = None,
              gate_of=None) -> dict:
    """Every segment's state with its trigger checks (1–8) and its market & valuation checks (9–18 without the fund-
    specific check 15), so a segment outside the selected plan still shows why it would or would not qualify."""
    segs = segment_states()
    out = {}
    for k, st in segs.items():
        mk = valuation_checks(k, macro or {}, (gates or {}).get(gate_of(k)) if gate_of else None, metal_choice,
                              ("—", True, ""), st)
        out[k] = {**st, "checks": trigger_checks(st, asof), "mkt": mk[:6] + mk[7:]}     # 13: check 15 is the fund's
    return out


def _alt_first(chk_fund: list, seg: str, metal_choice: str, what: str, n: int, why: str) -> list:
    """Fund / ETF checks 19–20 for a segment outside the plan: never the model's choice, so never bought."""
    return [_chk("Model's choice for this segment", False, f"the model holds {metal_choice} this month — {seg} is shown for information only"),
            _chk(f"Top-ranked {seg} {what}", True, f"{why} ({n} {seg} {what}s compared)")] + chk_fund[2:]


def _alt_rank(chk: list) -> int:
    return sum(1 for c in chk[N_MKT + 2:-1] if c[1])


def _info_alts(alts: dict, cands: list, pmap: dict) -> None:
    """Every segment a plan may lack gets the model's most-used fund / ETF for it, shown for information only:
    check 23 ("model's choice") fails and `fundOk` is false, so it can never be bought."""
    for seg in {s for m in pmap.values() for s in m}:
        if seg in alts:
            continue
        cnt = {}
        for m in pmap.values():
            if seg in m:
                cnt[m[seg]["c"]] = cnt.get(m[seg]["c"], 0) + 1
        ci = sorted(cnt, key=lambda i: (-cnt[i], i))[0]
        c = cands[ci]
        ch = [list(x) for x in c["checks"]]
        ch[N_MKT] = _chk("Model's choice for this segment", False,
                         f"not part of the selected model portfolio — the model's {c.get('name')} is shown for information only")
        alts[seg] = {**c, "checks": ch, "fundOk": False, "info": True}


def _add(cands: list, seen: dict, c: dict) -> int:
    k = json.dumps(c, sort_keys=True, ensure_ascii=False)
    if k not in seen:
        seen[k] = len(cands)
        cands.append(c)
    return seen[k]


def _plan_entry(segs: dict, seg: str, ci: int, cand: dict) -> dict:
    trig = segs[seg]["checks"]
    v = verdict(trig + cand["checks"])
    return {"c": ci, "passed": v["passed"], "n": v["n"], "ok": v["ok"]}


def rule_public() -> dict:
    keep = ("lookback", "resetPct", "tiers", "min", "max", "confirmPts", "crashDayPct", "maxFallPct", "reserve")
    return {k: RULE[k] for k in keep} | {"n": {"trig": N_TRIG, "mkt": N_MKT, "fund": N_FUND, "all": N_ALL}, "start": SIM_START, "persons": RULE["persons"], "segments": {k: {"label": s["label"], "index": s["index"]} for k, s in RULE["segments"].items()}}


def mf_reserve(rows: list[dict]) -> dict | None:
    """The liquid fund that holds an agent's dip reserve: open for lump sums, minimum ≤ the reserve, ≥ ₹10,000 cr,
    3-year record, lowest expense ratio (then largest)."""
    ok = [f for f in rows if f.get("sub") in ("liquid",) and "L" in (f.get("buy") or "") and (f.get("lumpMin") or 0) <= RULE["reserve"]
          and (f.get("aum") or 0) >= 10000 and f.get("r3y") is not None and f.get("ter") is not None]
    if not ok:
        return None
    f = sorted(ok, key=lambda f: (f["ter"], -f["aum"], f["code"]))[0]
    return {"code": f["code"], "name": f["name"], "ter": f["ter"], "aum": round(f["aum"]), "lumpMin": f.get("lumpMin"),
            "why": f"lowest expense ratio of {len(ok)} liquid funds open for lump sums with ≥ ₹10,000 cr and a 3-year record"}


def mf_block(plans: dict, fund, peers, exit_of, fpe_of, macro: dict, gates: dict, metal_choice: str, asof: str, rows: list[dict]) -> dict:
    """`fund(code)` → screener row dict, `peers(code)` → same-category rows, `exit_of(code)` → exit rule,
    `fpe_of(code)` → portfolio P/E vs category ({pe, peerPe, prem}) or None."""
    segs = _segments(asof, macro, gates, metal_choice, lambda k: {"large": "core", "mid": "mid", "small": "small"}.get(k))
    cands, seen, pmap = [], {}, {}
    for pid, p in plans.items():
        m = {}
        for seg, cfg in RULE["segments"].items():
            if seg not in segs:
                continue
            sl = next((s for s in p["slots"] if s["key"] in cfg["mf"]), None)
            f = fund(sl["code"]) if sl else None
            if not f or (cfg.get("metal") and metal_of(f.get("name")) != cfg["metal"]):
                continue
            gate = dict(gates.get(sl["key"]) or {})
            if (sl.get("w") or 0) <= 0:
                gate["now"] = "pause"
            if cfg.get("metal"):
                extra = ("Fund holds the metal", metal_of(f.get("name")) == cfg["metal"], f"{f.get('name')}")
            elif str(f.get("sub") or "").startswith("idx"):
                extra = ("Fund P/E vs category", True, "index fund — valued by its index (checks 9–10)")
            else:
                fi = fpe_of(sl["code"])
                # a fund whose monthly portfolio is not published is valued by its segment's index (checks 9–10)
                extra = ("Fund P/E below 1.25× category", fi is None or fi["prem"] < 1.25,
                         f"portfolio P/E {fi['pe']} vs {fi['peerPe']} category median ({fi['prem']:.2f}×)" if fi
                         else "portfolio P/E not published — the segment's index P/E applies (checks 9–10)")
            chk = valuation_checks(seg, macro, gate, metal_choice, extra, segs[seg]) + \
                mf_fund_checks(sl, f, peers(sl["code"]), exit_of(sl["code"]), segs[seg]["amount"], asof)
            cand = {"seg": seg, "slot": sl["key"], "code": sl["code"], "name": f.get("name"), "checks": chk,
                    "purchase": mf_purchase(f), "fundOk": all(c[1] for c in chk[:-1])}
            m[seg] = _plan_entry(segs, seg, _add(cands, seen, cand), cand)
        pmap[pid] = m
    alts = {}
    for seg, cfg in RULE["segments"].items():
        mt = cfg.get("metal")
        if not mt or seg not in segs or (mt == metal_choice and any(seg in m for m in pmap.values())):
            continue
        pool = [f for f in rows if f.get("sub") == mt and metal_of(f.get("name")) == mt]
        best = None
        for f in pool:
            slot = {"key": "metal", "label": f"Precious metals — {mt}", "checks": []}
            chk = valuation_checks(seg, macro, gates.get("metal"), metal_choice, ("Fund holds the metal", True, f.get("name")), segs[seg]) + \
                _alt_first(mf_fund_checks(slot, f, pool, exit_of(f["code"]), segs[seg]["amount"], asof), mt, metal_choice, "fund", len(pool),
                           "most fund checks passed, then lowest expense ratio and largest size")
            if mt == metal_choice:
                chk[N_MKT] = _chk("Model's choice for this segment", False, "No eligible fund in the regular plan; displayed for information only, never purchased.")
            key = (-_alt_rank(chk), f.get("ter") if f.get("ter") is not None else 9, -(f.get("aum") or 0), f["code"])
            if best is None or key < best[0]:
                best = (key, {"seg": seg, "slot": "metal", "code": f["code"], "name": f.get("name"), "purchase": mf_purchase(f), "checks": chk, "fundOk": False, "info": True})
        if best:
            alts[seg] = best[1]
    _info_alts(alts, cands, pmap)
    return {"asOf": asof, "rule": rule_public(), "segments": segs, "cands": cands, "plans": pmap, "alts": alts, "reserve": mf_reserve(rows)}


def etf_block(plans: dict, slots: dict, row, ex_of, vols_of, cap_of, names_of, macro: dict, gates: dict, metal_choice: str,
              asof: str, universe: list | None = None) -> dict:
    """`row(sym)` → momentum row, `ex_of(sym)` → analytics row, `vols_of(sym)` → daily volumes, `cap_of(slot id)` →
    expense-ratio cap, `names_of(sym)` → names / benchmark / underlying of the ETF."""
    import re
    gate_key = {"large": "core", "mid": "mid", "small": "small"}
    segs = _segments(asof, macro, gates, metal_choice, gate_key.get)
    cands, seen, pmap = [], {}, {}
    by_idx = {}
    for e in universe or []:
        t = (ex_of(e["s"]) or {}).get("te") or {}
        if t.get("te") is not None:
            by_idx.setdefault(t.get("idx"), []).append(t["te"])
    te_med = {k: _med(v) for k, v in by_idx.items()}
    for pid, p in plans.items():
        m = {}
        for seg, cfg in RULE["segments"].items():
            if seg not in segs:
                continue
            sid = next((x["id"] for x in p["slots"] if x["id"] in cfg["etf"]), None)
            sl = slots.get(sid) if sid else None
            e = row(sl["sym"]) if sl else None
            if not e:
                continue
            nm = " ".join(names_of(sl["sym"]) or [e.get("n") or ""]).lower()
            hit = re.search(INDEX_RX[seg], nm) is not None
            chk = valuation_checks(seg, macro, gates.get(gate_key.get(seg, "")), metal_choice,
                                   ("Tracks the segment's index", hit, (e.get("n") or sl["sym"]) + (" — " + segs[seg]["index"] if hit else " — index not matched")), segs[seg]) + \
                etf_fund_checks(sl, e, ex_of(sl["sym"]), vols_of(sl["sym"]), cap_of(sid), segs[seg]["amount"], te_med)
            cand = {"seg": seg, "slot": sid, "sym": sl["sym"], "name": e.get("n"), "checks": chk, "fundOk": all(c[1] for c in chk[:-1])}
            m[seg] = _plan_entry(segs, seg, _add(cands, seen, cand), cand)
        pmap[pid] = m
    alts = {}
    for seg, cfg in RULE["segments"].items():
        mt = cfg.get("metal")
        if not mt or mt == metal_choice or seg not in segs:
            continue
        pool = [e for e in (universe or []) if re.search(INDEX_RX[seg], " ".join(names_of(e["s"]) or [e.get("n") or ""]).lower())
                and not re.search(INDEX_RX["gold" if mt == "silver" else "silver"], (e.get("n") or "").lower())]
        best = None
        for e in pool:
            slot = {"label": f"{mt.capitalize()} ETF", "checks": []}
            chk = valuation_checks(seg, macro, gates.get("metal"), metal_choice, ("Tracks the segment's index", True, (e.get("n") or e["s"]) + " — " + segs[seg]["index"]), segs[seg]) + \
                _alt_first(etf_fund_checks(slot, e, ex_of(e["s"]), vols_of(e["s"]), cap_of(mt), segs[seg]["amount"], te_med), mt, metal_choice, "ETF", len(pool),
                           "most ETF checks passed, then most traded")
            key = (-_alt_rank(chk), -(e.get("tv") or 0), e["s"])
            if best is None or key < best[0]:
                best = (key, {"seg": seg, "slot": mt, "sym": e["s"], "name": e.get("n"), "checks": chk, "fundOk": False, "info": True})
        if best:
            alts[seg] = best[1]
    _info_alts(alts, cands, pmap)
    liq = next((slots[x["id"]]["sym"] for p in plans.values() for x in p["slots"] if x["id"] == "liquid" and slots.get("liquid")), None)
    return {"asOf": asof, "rule": rule_public(), "segments": segs, "cands": cands, "plans": pmap, "alts": alts,
            "reserve": {"sym": liq or "LIQUIDBEES", "why": "the model's liquid ETF" if liq else "default liquid ETF"}}

