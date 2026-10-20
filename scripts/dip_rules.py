#!/usr/bin/env python3
"""
dip_rules.py — market-dip lump sums, shared by the Portfolio Simulator builds (build_smart_sip.py,
build_etf_smart.py) and the Simulator Buy engine. One source of truth: sim_config.json → "dipRule".

Signal (per segment: large / mid / small cap, gold, silver), from official closes of the segment's index tracker:
  fall     = how far the close is below the highest close of the last `lookback` sessions (≈ 3 months)
  tier     = 3% → ₹5,000 · 5% → ₹10,000 · 10% → ₹20,000 (never below `min`, never above `max`)
  buy day  = the first close at a deeper tier in the current fall (at most one buy per tier); the fall ends when
             the index is back within `resetPct` of its high, and tiers start again
  confirm  = a second tracker of the same index shows the same fall (± `confirmPts`), the day's own move is not
             worse than `crashDayPct` (a crash day / bad print waits a session) and the fall is within `maxFallPct`
A buy day that is not confirmed does not use up its tier, so the next confirmed close at that tier can still buy.

26 checks before any dip lump sum: 7 trigger checks, 7 valuation checks and 12 fund (or ETF) checks. The agents
recompute the trigger checks from recorded prices themselves; checks 8–25 come from the published plan snapshot.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RULE = json.loads((ROOT / "scripts" / "sim_config.json").read_text())["dipRule"]


def tier_of(fall: float) -> tuple[int, int]:
    """(tier %, amount ₹) for a fall in % — the deepest tier reached, (0, 0) below the first."""
    for t, amt in RULE["tiers"]:
        if fall >= t:
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
    the page builds agree when they read the same closes."""
    lb, out, ep = RULE["lookback"], [], 0
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
        t, amt = tier_of(fall)
        if fall < RULE["resetPct"]:
            ep = 0
        before = ep
        conf = fall2 is not None and abs(fall2 - fall) <= RULE["confirmPts"]
        sane = day >= RULE["crashDayPct"] and fall <= RULE["maxFallPct"]
        sig = t > ep and conf and sane
        if sig:
            ep = t
        out.append({"d": d, "close": c, "high": hi, "highDate": hi_d, "fall": fall, "fall2": fall2, "day": day,
                    "tier": t, "amount": amt, "epBefore": before, "ep": ep, "conf": conf, "sane": sane, "signal": sig})
    return out


def segment_states(syms_from: str | None = None) -> dict:
    """Latest dip state of every segment plus its recent buy days (public pages)."""
    out = {}
    for key, s in RULE["segments"].items():
        cl = load_closes(s["trk"])
        if syms_from:
            cl = [x for x in cl if x[0] >= syms_from]
        st = walk(cl, dict(load_closes(s["trk2"])))
        if not st:
            continue
        last = st[-1]
        sigs = [{"d": x["d"], "tier": x["tier"], "fall": round(x["fall"], 2), "amount": x["amount"]} for x in st if x["signal"]][-6:]
        out[key] = {"label": s["label"], "index": s["index"], "trk": s["trk"], "trk2": s["trk2"],
                    **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in last.items()}, "recent": sigs}
    return out


def _chk(label, ok, detail):
    return [label, bool(ok), detail]


def trigger_checks(st: dict, data_date: str) -> list:
    """Checks 1–7 (the market trigger) for one segment state."""
    t, amt = st["tier"], st["amount"]
    age = (date.fromisoformat(data_date) - date.fromisoformat(st["d"])).days
    reached = "first close at this tier in the current fall" if st["signal"] else (
        f"tier {st['ep']}% already used in this fall — next buy at a deeper tier" if st["ep"] and t and t <= st["ep"] else "no new tier today")
    return [
        _chk("Fall from 3-month high ≥ 3%", st["fall"] >= RULE["tiers"][-1][0],
             f"{st['fall']:.2f}% below the highest close {st['high']:.2f} ({st['highDate']})"),
        _chk("Official close up to date", age <= 5, f"close of {st['d']} ({age} days before the latest data)"),
        _chk("Fall confirmed by a second tracker", st["conf"],
             f"second tracker {st['fall2']:.2f}% (within {RULE['confirmPts']} pt)" if st["fall2"] is not None else "second tracker has no close that day (or too few in the window)"),
        _chk("Not a crash-day print", st["day"] >= RULE["crashDayPct"], f"day's move {st['day']:+.2f}% (limit {RULE['crashDayPct']:.0f}%)"),
        _chk(f"Fall within {RULE['maxFallPct']:.0f}%", st["fall"] <= RULE["maxFallPct"], f"{st['fall']:.2f}%"),
        _chk("Dip tier and amount", t > 0, f"{t}% tier → ₹{amt:,}" if t else "below the 3% tier — no dip amount"),
        _chk("New tier in this fall", st["signal"], reached),
    ]


def valuation_checks(seg: str, macro: dict, gate: dict | None, metal_choice: str | None, extra: tuple) -> list:
    """Checks 8–14. `extra` = (label, ok, detail) for check 13 (fund P/E for funds, index match for ETFs)."""
    s = RULE["segments"][seg]
    val, n50 = (macro.get("valuation") or {}), (macro.get("valuation") or {}).get("n50") or {}
    g8 = _chk("Model not pausing this segment", (gate or {}).get("now") not in ("pause", "zero", "0"),
              f"valuation gate: {(gate or {}).get('now', 'not gated')}")
    n50pct = n50.get("pePct")
    c14 = _chk("Broad market not overheated", n50pct is not None and n50pct < 0.9,
               f"Nifty 50 P/E at the {round((n50pct or 0) * 100)}th percentile of 10 years (limit 90th)" if n50pct is not None else "no valuation on file")
    if s.get("val"):
        v = val.get(s["val"]) or {}
        pe, pct, med = v.get("pe"), v.get("pePct"), v.get("peMed")
        g10 = ((macro.get("rates") or {}).get("g10") or {}).get("last")
        ey = 100 / pe if pe else None
        eg = ((macro.get("growth") or {}).get("earnings") or {}).get(s["val"]) or {}
        return [g8,
                _chk("P/E below the 90th percentile", pct is not None and pct < 0.9, f"{s['index']} P/E {pe} at the {round((pct or 0) * 100)}th percentile of 10 years" if pct is not None else "no valuation on file"),
                _chk("P/E within 1.25× its 10-year median", pe and med and pe <= 1.25 * med, f"P/E {pe} vs median {med}" if pe and med else "no valuation on file"),
                _chk("Earnings yield vs 10-year G-Sec", ey is not None and g10 is not None and ey - g10 >= s["eyGapMin"],
                     f"{ey:.2f}% vs {g10:.2f}% (gap {ey - g10:+.2f} pt, limit {s['eyGapMin']:+.1f})" if ey and g10 else "not on file"),
                _chk("Earnings not collapsing", eg.get("g1") is not None and eg["g1"] >= -15, f"12-month earnings growth {eg['g1']:+.1f}% (limit −15%)" if eg.get("g1") is not None else "no earnings history"),
                _chk(*extra), c14]
    gl = ((macro.get("global") or {}).get(s["metal"]) or {})
    return [g8,
            _chk("Price not at a 2-year extreme", gl.get("pct2y") is not None and gl["pct2y"] < 0.95, f"{round((gl.get('pct2y') or 0) * 100)}th percentile of 2 years (limit 95th)" if gl.get("pct2y") is not None else "not on file"),
            _chk("Not stretched above its 200-day average", gl.get("vs200") is not None and gl["vs200"] <= 20, f"{gl['vs200']:+.1f}% vs 200-day average (limit +20%)" if gl.get("vs200") is not None else "not on file"),
            _chk("Model's metal choice", metal_choice == s["metal"], f"model holds {metal_choice or 'no metal'}"),
            _chk("12-month trend not broken", gl.get("c12m") is not None and gl["c12m"] > -25, f"12-month change {gl['c12m']:+.1f}% (limit −25%)" if gl.get("c12m") is not None else "not on file"),
            _chk(*extra), c14]


def _med(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    return xs[len(xs) // 2] if xs else None


def mf_fund_checks(slot: dict, f: dict, peers: list[dict], exit_rule, tier_amt: int) -> list:
    """Checks 15–26 for a mutual fund (screener row `f`, same-category `peers`)."""
    ter_m, r3_m, mdd_m = _med([p.get("ter") for p in peers]), _med([p.get("r3y") for p in peers]), _med([p.get("mdd") for p in peers])
    sc = slot.get("checks") or []
    er = exit_rule
    long_load = er.get("days", 0) > 365 or any(p > 1 for _, p in er.get("tiers", []))
    return [
        _chk("Model's choice for this segment", True, f"{slot.get('label')} — {f.get('name')}"),
        _chk("Passes every check of its model slot", sc and all(c[1] for c in sc), f"{sum(1 for c in sc if c[1])} of {len(sc)} slot checks"),
        _chk("Open for lump-sum purchases", "L" in (f.get("buy") or ""), "accepts one-time purchases" if "L" in (f.get("buy") or "") else "lump sums paused"),
        _chk("Lump-sum minimum ≤ ₹5,000", (f.get("lumpMin") or 0) <= RULE["min"], f"₹{f.get('lumpMin') or 0:,} minimum"),
        _chk("Exit load ≤ 1% and within 12 months", not long_load, "nil" if not er.get("tiers") else ", ".join(f"{p}% within {d} days" for d, p in er["tiers"])),
        _chk("Expense ratio ≤ category median", f.get("ter") is not None and ter_m is not None and f["ter"] <= ter_m + 1e-9, f"{f.get('ter')}% vs median {ter_m}%"),
        _chk("Fund size ≥ ₹500 cr", (f.get("aum") or 0) >= 500, f"₹{round(f.get('aum') or 0):,} cr"),
        _chk("Track record ≥ 3 years", f.get("r3y") is not None, "3-year return on file" if f.get("r3y") is not None else "under 3 years"),
        _chk("3-year return near or above category median", f.get("r3y") is not None and r3_m is not None and f["r3y"] >= r3_m - 1, f"{f.get('r3y')}% a year vs median {r3_m}%"),
        _chk("Worst fall no deeper than category median − 5 pt", f.get("mdd") is not None and mdd_m is not None and f["mdd"] >= mdd_m - 5, f"{f.get('mdd')}% vs median {mdd_m}%"),
        _chk("Status not lagging", f.get("status") not in ("Underperforming", "Out of track"), f.get("status") or "not rated"),
        _chk("Dip amount within ₹5,000–₹20,000", tier_amt > 0 and RULE["min"] <= tier_amt <= RULE["max"], f"₹{tier_amt:,} at the current fall" if tier_amt else "no dip tier reached"),
    ]


def etf_fund_checks(slot: dict, e: dict, ex: dict, bars_v: list, cap: float, tier_amt: int) -> list:
    """Checks 15–26 for an ETF (`e` = momentum row, `ex` = analytics row, `bars_v` = last daily volumes)."""
    sc = slot.get("checks") or []
    x = e.get("x") or {}
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
        _chk("Dip amount within ₹5,000–₹20,000", tier_amt > 0 and RULE["min"] <= tier_amt <= RULE["max"], f"₹{tier_amt:,} at the current fall" if tier_amt else "no dip tier reached"),
    ]


def verdict(checks: list) -> dict:
    """All 26 → buy today; checks 8–25 → the fund itself is fit for a dip buy (what the agents read)."""
    return {"n": len(checks), "passed": sum(1 for c in checks if c[1]), "ok": all(c[1] for c in checks),
            "fundOk": all(c[1] for c in checks[7:25]), "fail": [c[0] for c in checks if not c[1]]}


# ───────────────────────────── published blocks (page builds) ─────────────────────────────
# the index each ETF slot must track (check 13 for ETFs) — matched against the ETF's name / benchmark / underlying
INDEX_RX = {"large": r"nifty\s*50\b(?!.*(value|equal|quality|alpha|momentum|low\s*vol|next|shariah|dividend))",
            "mid": r"midcap\s*150", "small": r"smallcap\s*250", "gold": r"\bgold\b", "silver": r"\bsilver\b"}


def metal_of(name: str) -> str:
    return "silver" if "silver" in (name or "").lower() else "gold"


def _segments(asof: str) -> dict:
    segs = segment_states()
    return {k: {**st, "checks": trigger_checks(st, asof)} for k, st in segs.items()}


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
    return {k: RULE[k] for k in keep} | {"persons": RULE["persons"], "segments": {k: {"label": s["label"], "index": s["index"]} for k, s in RULE["segments"].items()}}


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
    segs = _segments(asof)
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
            chk = valuation_checks(seg, macro, gate, metal_choice, extra) + \
                mf_fund_checks(sl, f, peers(sl["code"]), exit_of(sl["code"]), segs[seg]["amount"])
            cand = {"seg": seg, "slot": sl["key"], "code": sl["code"], "name": f.get("name"), "checks": chk,
                    "fundOk": all(c[1] for c in chk[:18])}
            m[seg] = _plan_entry(segs, seg, _add(cands, seen, cand), cand)
        pmap[pid] = m
    return {"asOf": asof, "rule": rule_public(), "segments": segs, "cands": cands, "plans": pmap, "reserve": mf_reserve(rows)}


def etf_block(plans: dict, slots: dict, row, ex_of, vols_of, cap_of, names_of, macro: dict, gates: dict, metal_choice: str,
              asof: str) -> dict:
    """`row(sym)` → momentum row, `ex_of(sym)` → analytics row, `vols_of(sym)` → daily volumes, `cap_of(slot id)` →
    expense-ratio cap, `names_of(sym)` → names / benchmark / underlying of the ETF."""
    import re
    segs = _segments(asof)
    gate_key = {"large": "core", "mid": "mid", "small": "small"}
    cands, seen, pmap = [], {}, {}
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
                                   ("Tracks the segment's index", hit, (e.get("n") or sl["sym"]) + (" — " + segs[seg]["index"] if hit else " — index not matched"))) + \
                etf_fund_checks(sl, e, ex_of(sl["sym"]), vols_of(sl["sym"]), cap_of(sid), segs[seg]["amount"])
            cand = {"seg": seg, "slot": sid, "sym": sl["sym"], "name": e.get("n"), "checks": chk, "fundOk": all(c[1] for c in chk[:18])}
            m[seg] = _plan_entry(segs, seg, _add(cands, seen, cand), cand)
        pmap[pid] = m
    liq = next((slots[x["id"]]["sym"] for p in plans.values() for x in p["slots"] if x["id"] == "liquid" and slots.get("liquid")), None)
    return {"asOf": asof, "rule": rule_public(), "segments": segs, "cands": cands, "plans": pmap,
            "reserve": {"sym": liq or "LIQUIDBEES", "why": "the model's liquid ETF" if liq else "default liquid ETF"}}
