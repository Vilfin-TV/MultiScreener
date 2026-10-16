#!/usr/bin/env python3
"""Smart SIP planner for the India MF Screener → data/mf/smartsip.json (+ data/mf/smartsip_state.json).

Fifteen model plans — 5 investment horizons × 3 risk levels — each with a fixed set of up to 8 fund slots
(equity core, flexi, mid, small, hybrid, debt, gold and, for 7+ year aggressive plans only, a ≤10% thematic and
a ≤10% international satellite). The page scales a plan to the investor's amount and weekly / monthly SIP.

How funds are chosen (per slot):
  1. Hard filters — track record (5y equity / hybrid, 3y others), fund size, expense ratio no higher than the
     slot's category median (+0.10 pt), no lock-in, still accepting SIPs, not "Out of track", benchmark beaten
     in at least half of rolling 3-year periods (active funds), high-quality debt portfolios only.
  2. Weighted score (percentiles within the slot) — rolling 3-year return, % of rolling periods beating the
     benchmark, consistency, Sortino, max drawdown, 5-year return, recent form, low expense ratio and size.
     Index funds: low cost, size and tracking (closeness to peers' return).
  3. Diversification — top-holding overlap with funds already chosen kept low (≤30% vs the large-cap core,
     ≤20% otherwise), and at most two funds from one fund house.

Stability (so the plan does not keep adding or swapping funds):
  * The number of funds per plan is fixed by the plan template.
  * Picks are reviewed once a month. An incumbent fund is kept while it still passes the (looser) keep test;
    it is replaced only after failing two monthly reviews in a row, or immediately on a hard red flag
    (scheme gone, closed to SIPs, or "Out of track"). Existing units are never sold — only future instalments move.
  * The market-condition tilt (±10 points between equity and debt, in 5-point steps) also changes at most monthly.

Market conditions: drawdown of the broad Indian market (Nifty 500 index fund NAV) from its 52-week high, its
position against the 40-week average, and the India fear/greed zone from data/market_sentiment.json. Lower
prices / fear → slightly more equity; stretched prices with extreme greed → slightly less. Horizons under 5
years are not tilted.
"""
from __future__ import annotations

import json
import logging
import math
import re
import statistics as st
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MF = ROOT / "data" / "mf"
OUT = MF / "smartsip.json"
STATE = MF / "smartsip_state.json"
VERSION = 1
log = logging.getLogger("smartsip")

HORIZONS = [("h1", "Under 3 years"), ("h3", "3–5 years"), ("h5", "5–7 years"), ("h7", "7–10 years"), ("h10", "10+ years")]
RISKS = [("c", "Conservative"), ("b", "Balanced"), ("a", "Aggressive")]

# slot → (label, asset class, candidate subs, kind, min years, min AUM ₹ cr)
SLOTS = {
    "core":   ("Large-cap core (Nifty 50 index)", "Equity", ["idx_large"], "index", 3, 500),
    "flexi":  ("Diversified equity (flexi / multi / large & mid)", "Equity", ["flexi", "multi", "largemid"], "active", 5, 1000),
    "mid":    ("Mid cap", "Equity", ["mid"], "active", 5, 1000),
    "small":  ("Small cap", "Equity", ["small"], "active", 5, 1000),
    "baf":    ("Balanced advantage (dynamic)", "Hybrid", ["baf"], "active", 5, 1000),
    "eqsav":  ("Equity savings", "Hybrid", ["eqsavings"], "active", 5, 300),
    "arb":    ("Arbitrage", "Hybrid", ["arbitrage"], "debt", 3, 1000),
    "dshort": ("Money market / low duration", "Debt", ["money", "lowdur", "ultrashort"], "debt", 3, 1000),
    "dcore":  ("High-quality debt (corporate bond / PSU / short)", "Debt", ["corpbond", "bankpsu", "shortdur"], "debt", 3, 1000),
    "gold":   ("Gold", "Gold", ["gold"], "passive", 3, 200),
    "theme":  ("Thematic satellite", "Equity", "sec_*", "active", 5, 500),
    "intl":   ("International satellite", "International", ["us", "global"], "intl", 3, 300),
}
# weights in % per plan (sum 100). Satellites only for 7+ year aggressive plans; never more than 8 funds.
TEMPLATES = {
    "h1c":  {"arb": 40, "dshort": 60},
    "h1b":  {"arb": 35, "eqsav": 20, "dshort": 45},
    "h1a":  {"arb": 30, "baf": 25, "dshort": 45},
    "h3c":  {"core": 15, "baf": 25, "dcore": 50, "gold": 10},
    "h3b":  {"core": 25, "flexi": 15, "baf": 20, "dcore": 30, "gold": 10},
    "h3a":  {"core": 30, "flexi": 25, "baf": 15, "dcore": 20, "gold": 10},
    "h5c":  {"core": 25, "flexi": 10, "baf": 20, "dcore": 35, "gold": 10},
    "h5b":  {"core": 30, "flexi": 20, "mid": 10, "baf": 10, "dcore": 20, "gold": 10},
    "h5a":  {"core": 30, "flexi": 25, "mid": 15, "small": 5, "dcore": 15, "gold": 10},
    "h7c":  {"core": 30, "flexi": 15, "baf": 15, "dcore": 30, "gold": 10},
    "h7b":  {"core": 30, "flexi": 20, "mid": 15, "small": 5, "dcore": 20, "gold": 10},
    "h7a":  {"core": 25, "flexi": 20, "mid": 15, "small": 10, "theme": 5, "intl": 10, "dcore": 10, "gold": 5},
    "h10c": {"core": 30, "flexi": 20, "mid": 5, "baf": 10, "dcore": 25, "gold": 10},
    "h10b": {"core": 30, "flexi": 20, "mid": 15, "small": 10, "dcore": 15, "gold": 10},
    "h10a": {"core": 25, "flexi": 20, "mid": 15, "small": 15, "theme": 5, "intl": 10, "dcore": 5, "gold": 5},
}
ORDER = ["core", "flexi", "mid", "small", "theme", "baf", "eqsav", "arb", "dcore", "dshort", "gold", "intl"]
EQUITY_SLOTS = {"core", "flexi", "mid", "small", "theme", "baf", "eqsav"}
RX_NIFTY50 = re.compile(r"\bnifty 50\b(?!\s*(equal|value|quality|low|momentum|alpha|shariah|arbitrage))", re.I)
RX_NOT_CORE = re.compile(r"elss|tax saver|next 50|equal weight|value|quality|momentum|low vol|alpha", re.I)
RX_INTL_THEME = re.compile(r"mining|clean energy|energy|innovation|technology|tech\b|agri|real estate|reit|ev\b|electric|"
                           r"healthcare|consumer|commodit|fang|nasdaq|china|brazil|japan|taiwan|asean|emerging|india", re.I)
SAFE_CREDIT = ("AAA", "Sovereign", "A1+", "Cash")


def load(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except Exception:  # noqa: BLE001
        return default


def years_since(iso, today):
    try:
        return (today - date.fromisoformat(iso)).days / 365.25
    except Exception:  # noqa: BLE001
        return 0.0


def pct_rank(vals: dict, higher=True):
    """code → percentile 0..1 among known values; unknown → 0.35."""
    known = sorted((v, k) for k, v in vals.items() if v is not None and not (isinstance(v, float) and math.isnan(v)))
    out = {k: 0.35 for k in vals}
    n = len(known)
    if n == 1:
        out[known[0][1]] = 0.6
    for i, (v, k) in enumerate(known):
        if n > 1:
            # average rank for ties
            lo = next(j for j in range(n) if known[j][0] == v)
            hi = max(j for j in range(n) if known[j][0] == v)
            p = ((lo + hi) / 2) / (n - 1)
            out[k] = p if higher else 1 - p
    return out


class Universe:
    def __init__(self, scr, today):
        self.cols = {c: i for i, c in enumerate(scr["cols"])}
        self.rows = {r[0]: r for r in scr["rows"]}
        self.amcs = scr["amcs"]
        self.today = today
        self.pf = {}
        for sub in {r[self.cols["sub"]] for r in scr["rows"]}:
            for code, v in (load(MF / "p" / f"{sub}.json", {}) or {}).items():
                self.pf[int(code)] = v
        self.ter_med = {}

    def g(self, code, col):
        r = self.rows.get(code)
        return r[self.cols[col]] if r is not None and col in self.cols else None

    def pool(self, slot):
        subs = SLOTS[slot][2]
        if subs == "sec_*":
            return [c for c, r in self.rows.items() if str(r[self.cols["sub"]]).startswith("sec_")]
        return [c for c, r in self.rows.items() if r[self.cols["sub"]] in subs]

    def holdings(self, code):
        p = self.pf.get(code) or {}
        return {h[3]: h[2] for h in (p.get("top") or []) if len(h) > 3 and h[3] and h[4] in ("equity", "overseas")}

    def overlap(self, a, b):
        ha, hb = self.holdings(a), self.holdings(b)
        if not ha or not hb:
            return None
        return round(sum(min(w, hb[i]) for i, w in ha.items() if i in hb), 1)

    def credit_ok(self, code):
        p = self.pf.get(code) or {}
        cr = p.get("credit")
        if not cr:
            return True                    # no portfolio published yet → rely on category
        safe = sum(w for k, w in cr if any(s.lower() in k.lower() for s in SAFE_CREDIT))
        tot = sum(w for _, w in cr) or 100
        return safe / tot >= 0.85


def buy_ok(u, code, need_sip=True):
    b = u.g(code, "buy")
    if b is None:
        return True                        # status not known yet → do not exclude
    return ("S" in b) if need_sip else bool(b)


def hard_filter(u, slot, code, loose=False):
    """Entry test (loose=False) or keep test for an incumbent (loose=True). Returns (ok, reason)."""
    label, asset, subs, kind, min_y, min_aum = SLOTS[slot]
    g = lambda c: u.g(code, c)  # noqa: E731
    if g("sub") is None:
        return False, "no longer listed"
    if not buy_ok(u, code):
        return False, "not accepting SIPs"
    if g("status") == "Out of track":
        return False, "Out of track"
    if loose:
        return True, ""
    name = g("name") or ""
    if (g("lock") or 0) > 0 or re.search(r"elss|tax saver", name, re.I):
        return False, "lock-in"
    if years_since(g("inc"), u.today) < min_y:
        return False, "short track record"
    if (g("aum") or 0) < min_aum:
        return False, "small fund size"
    med = u.ter_med.get(slot)
    ter = g("ter")
    if ter is None or (med is not None and ter > med + 0.10):
        return False, "expense ratio above category median"
    if slot == "core" and (not RX_NIFTY50.search(name) or RX_NOT_CORE.search(name)):
        return False, "not a Nifty 50 index fund"
    if slot == "flexi" and g("size") in ("Mid", "Small"):
        return False, "tilted to mid / small caps (covered by dedicated slots)"
    if slot == "intl" and RX_INTL_THEME.search(name):
        return False, "narrow theme / region"
    if kind == "active" and slot not in ("eqsav",):
        b3 = g("beat3")
        if b3 is None or b3 < 50:
            return False, "benchmark beaten in under half of rolling 3-year periods"
        if g("status") == "Underperforming":
            return False, "Underperforming"
    if asset == "Debt" or slot == "arb":
        if asset == "Debt" and not u.credit_ok(code):
            return False, "credit quality below 85% AAA / sovereign"
        if g("r3y") is None:
            return False, "no 3-year record"
    return True, ""


def scores(u, slot, codes):
    kind = SLOTS[slot][3]
    m = lambda col: {c: u.g(c, col) for c in codes}  # noqa: E731
    logaum = {c: math.log10(max(u.g(c, "aum") or 1, 1)) for c in codes}
    if kind in ("index", "passive"):
        r3 = [u.g(c, "r3y") for c in codes if u.g(c, "r3y") is not None]
        med = st.median(r3) if r3 else None
        track = {c: (None if u.g(c, "r3y") is None or med is None else -abs(u.g(c, "r3y") - med)) for c in codes}
        parts = [(pct_rank(m("ter"), False), .40), (pct_rank(logaum), .35), (pct_rank(track), .25)]
    elif kind == "debt":
        parts = [(pct_rank(m("r3y")), .25), (pct_rank(m("cons")), .20), (pct_rank(m("std"), False), .15),
                 (pct_rank(m("sharpe")), .15), (pct_rank(m("ter"), False), .15), (pct_rank(logaum), .10)]
    elif kind == "intl":
        parts = [(pct_rank(m("r5y")), .20), (pct_rank(m("r3y")), .15), (pct_rank(m("sortino")), .20),
                 (pct_rank(m("mdd")), .10), (pct_rank(m("ter"), False), .20), (pct_rank(logaum), .15)]
    else:
        rec_w = .15 if slot == "theme" else .07
        parts = [(pct_rank(m("roll3")), .20), (pct_rank(m("beat3")), .17), (pct_rank(m("cons")), .14),
                 (pct_rank(m("sortino")), .14), (pct_rank(m("mdd")), .10), (pct_rank(m("r5y")), .08),
                 (pct_rank(m("rec")), rec_w), (pct_rank(m("ter"), False), .06), (pct_rank(logaum), .04)]
    tw = sum(w for _, w in parts)
    return {c: round(100 * sum(p[c] * w for p, w in parts) / tw, 1) for c in codes}


def market_tilt(u, sentiment, prev):
    """Equity tilt in points (−10…+10, 5-pt steps) and the readings behind it."""
    hist = load(MF / "h" / "147625.json") or load(MF / "h" / "118581.json") or {}
    code = 147625 if (MF / "h" / "147625.json").exists() else 118581
    pts = []
    try:
        s0 = date.fromisoformat(hist["s"])
        pts = [(s0 + timedelta(days=d), v) for d, v in hist["p"]]
    except Exception:  # noqa: BLE001
        pass
    sub = u.g(code, "sub")
    tail = (load(MF / "t" / f"{sub}.json", {}) or {}).get(str(code), {}) if sub else {}
    for d, v in (tail.get("p") or []):
        dd = date.fromisoformat(d)
        if not pts or dd > pts[-1][0]:
            pts.append((dd, v))
    zone = next((m.get("zone") for m in (sentiment or {}).get("markets", []) if m.get("country") == "India"), None)
    info = {"index": "Nifty 500", "zone": zone}
    if len(pts) < 60:
        return 0, {**info, "note": "insufficient history"}
    last_d, last = pts[-1]
    yr = [v for d, v in pts if d >= last_d - timedelta(days=365)]
    hi = max(yr)
    dd = (last / hi - 1) * 100
    avg40 = st.mean([v for d, v in pts if d >= last_d - timedelta(days=280)])
    vs_avg = (last / avg40 - 1) * 100
    y_ago = next((v for d, v in reversed(pts) if d <= last_d - timedelta(days=365)), None)
    r1y = (last / y_ago - 1) * 100 if y_ago else None
    t = 0
    if dd <= -20:
        t += 10
    elif dd <= -12:
        t += 5
    elif dd <= -7 and vs_avg < 0:
        t += 5
    if zone == "Extreme Fear":
        t += 5
    elif zone == "Fear" and dd <= -7:
        t += 5
    stretched = dd > -3 and vs_avg > 8 and (r1y or 0) > 25
    if stretched and zone == "Extreme Greed":
        t -= 10
    elif stretched or (dd > -2 and zone == "Extreme Greed" and vs_avg > 4):
        t -= 5
    t = max(-10, min(10, t))
    info.update({"asOf": last_d.isoformat(), "drawdown": round(dd, 1), "vsAvg40w": round(vs_avg, 1),
                 "r1y": None if r1y is None else round(r1y, 1)})
    return t, info


def apply_tilt(weights, tilt, hz):
    """Move `tilt` points between equity sleeves and debt / hybrid sleeves, keeping every slot ≥5%."""
    w = dict(weights)
    if hz in ("h1", "h3") or not tilt:
        return w, 0
    eq_take = ["core", "flexi"] if tilt > 0 else ["small", "mid", "flexi", "core"]
    dt_take = ["dcore", "dshort", "gold", "baf", "eqsav", "arb"]
    moved = 0
    need = abs(tilt)
    src = dt_take if tilt > 0 else eq_take
    for k in src:
        while need > 0 and w.get(k, 0) > 5:
            w[k] -= 5
            need -= 5
            moved += 5
    if moved:
        dst = next((k for k in (eq_take if tilt > 0 else dt_take) if k in w), None)
        if dst:
            w[dst] += moved
        else:
            moved = 0
            w = dict(weights)
    return w, moved if tilt > 0 else -moved


def why(u, slot, code, med_ter):
    g = lambda c: u.g(code, c)  # noqa: E731
    out = []
    y = years_since(g("inc"), u.today)
    if y >= 1:
        out.append(f"{int(y)}-year track record")
    if g("beat3") is not None and SLOTS[slot][3] == "active":
        out.append(f"Beat its benchmark in {g('beat3'):.0f}% of rolling 3-year periods")
    if g("roll3") is not None and SLOTS[slot][3] in ("active", "intl"):
        out.append(f"Average rolling 3-year return {g('roll3'):.1f}%")
    if g("ter") is not None:
        out.append(f"Expense ratio {g('ter'):.2f}%" + (f" (category median {med_ter:.2f}%)" if med_ter is not None else ""))
    if g("mdd") is not None and SLOTS[slot][1] in ("Equity", "Hybrid", "International"):
        out.append(f"Max drawdown (3 yrs) {g('mdd'):.1f}%")
    if g("aum") is not None:
        out.append(f"Fund size ₹{g('aum'):,.0f} cr")
    return out[:5]


def choose(u, slot, chosen, amc_count, incumbent, review, rank_cache):
    """Return (code, alternates, action, note)."""
    pool = rank_cache.get(slot)
    if pool is None:
        allc = u.pool(slot)
        ters = [u.g(c, "ter") for c in allc if u.g(c, "ter") is not None]
        u.ter_med[slot] = round(st.median(ters), 2) if ters else None
        ok = [c for c in allc if hard_filter(u, slot, c)[0]]
        sc = scores(u, slot, ok) if ok else {}
        pool = rank_cache[slot] = sorted(ok, key=lambda c: -sc[c]), sc
    ranked, sc = pool

    def overlap_ok(c):
        for o in chosen:
            ov = u.overlap(c, o)
            lim = 30 if "core" in (slot, chosen[o]) else 20
            if ov is not None and ov > lim:
                return False
        return True

    def fits(c):
        amc = u.g(c, "amc")
        return amc_count.get(amc, 0) < 2 and overlap_ok(c) and c not in chosen

    cand = [c for c in ranked if fits(c)] or [c for c in ranked if c not in chosen]
    if incumbent:
        code = incumbent["code"]
        hard, reason = hard_filter(u, slot, code, loose=True)
        if not hard:
            new = cand[0] if cand else None
            return new, [c for c in cand[1:3]], "replaced", f"Previous fund replaced: {reason}"
        if not review:
            return code, [c for c in cand if c != code][:2], "kept", ""
        # monthly review: keep test = entry filters still met, or score in the top 60% of the slot
        entry_ok, reason = hard_filter(u, slot, code)
        rank_pct = None
        if code in sc:
            rank_pct = 1 - ranked.index(code) / max(len(ranked) - 1, 1)
        passes = entry_ok and (rank_pct is None or rank_pct >= 0.4)
        strikes = 0 if passes else incumbent.get("strikes", 0) + 1
        incumbent["strikes"] = strikes
        if strikes < 2:
            note = "" if passes else f"On watch ({reason or 'slipped in its category ranking'}) — replaced only if it fails next month's review too"
            return code, [c for c in cand if c != code][:2], "kept" if passes else "watch", note
        new = next((c for c in cand if c != code), None)
        return new, [c for c in cand if c not in (code, new)][:2], "replaced", \
            f"Previous fund replaced after two monthly reviews: {reason or 'slipped in its category ranking'}"
    new = cand[0] if cand else None
    return new, [c for c in cand[1:3]], "new", ""


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    scr = load(MF / "screener.json")
    if not scr:
        log.error("screener.json missing")
        return 1
    today = date.fromisoformat(scr["asOf"])
    u = Universe(scr, today)
    state = load(STATE, {}) or {}
    if state.get("v") != VERSION:
        state = {"v": VERSION, "plans": {}, "tilt": 0, "tiltMonth": None, "market": {}}
    month = scr["asOf"][:7]
    review = state.get("reviewed") != month
    sentiment = load(ROOT / "data" / "market_sentiment.json", {})
    if review or state.get("tiltMonth") is None:
        tilt, minfo = market_tilt(u, sentiment, state)
        state["tilt"], state["tiltMonth"], state["market"] = tilt, month, minfo
    tilt = state["tilt"]
    rank_cache = {}
    plans = {}
    for hz, hz_label in HORIZONS:
        for rk, rk_label in RISKS:
            pid = hz + rk
            base = TEMPLATES[pid]
            weights, applied = apply_tilt(base, tilt, hz)
            pst = state["plans"].setdefault(pid, {"slots": {}})
            chosen, amc_count, slots, changes = {}, {}, [], []
            for slot in sorted(weights, key=ORDER.index):
                inc = pst["slots"].get(slot)
                code, alts, action, note = choose(u, slot, chosen, amc_count, inc, review, rank_cache)
                if code is None:
                    log.warning("%s/%s: no eligible fund", pid, slot)
                    continue
                if action in ("new", "replaced") or not inc or inc.get("code") != code:
                    prev_code = inc.get("code") if inc else None
                    pst["slots"][slot] = {"code": code, "since": today.isoformat(), "strikes": 0}
                    if prev_code and prev_code != code:
                        changes.append({"slot": slot, "from": prev_code, "to": code, "date": today.isoformat(), "note": note})
                chosen[code] = slot
                amc = u.g(code, "amc")
                amc_count[amc] = amc_count.get(amc, 0) + 1
                ranked, sc = rank_cache[slot]
                slots.append({
                    "key": slot, "label": SLOTS[slot][0], "asset": SLOTS[slot][1], "w": weights[slot], "base": base[slot],
                    "code": code, "score": sc.get(code), "alts": alts, "since": pst["slots"][slot]["since"],
                    "state": "watch" if action == "watch" else "ok", "note": note,
                    "why": why(u, slot, code, u.ter_med.get(slot)), "pool": len(ranked),
                })
            for k in list(pst["slots"]):
                if k not in weights:
                    pst["slots"].pop(k)
            pst["changes"] = (changes + pst.get("changes", []))[:6]
            codes = [s["code"] for s in slots]
            eq = [c for c in codes if chosen.get(c) in ("core", "flexi", "mid", "small", "theme")]
            ovs = [u.overlap(a, b) for i, a in enumerate(eq) for b in eq[i + 1:]]
            ovs = [o for o in ovs if o is not None]
            mix = {}
            for s in slots:
                mix[s["asset"]] = mix.get(s["asset"], 0) + s["w"]
            plans[pid] = {
                "horizon": hz_label, "risk": rk_label, "tilt": applied, "slots": slots, "mix": mix,
                "ter": round(sum((u.g(s["code"], "ter") or 0) * s["w"] for s in slots) / 100, 2),
                "maxOverlap": max(ovs) if ovs else None, "amcs": len({u.g(c, "amc") for c in codes}),
                "changes": pst["changes"],
            }
    if review:
        state["reviewed"] = month
    state["updated"] = today.isoformat()
    out = {"v": VERSION, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "asOf": scr["asOf"],
           "reviewed": state["reviewed"], "nextReview": (date(today.year + (today.month == 12), today.month % 12 + 1, 1)).isoformat(),
           "market": {**state["market"], "tilt": tilt},
           "horizons": [{"id": h, "label": l} for h, l in HORIZONS], "risks": [{"id": r, "label": l} for r, l in RISKS],
           "slots": {k: {"label": v[0], "asset": v[1]} for k, v in SLOTS.items()},
           "plans": plans}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=0, separators=(",", ":")))
    log.info("Smart SIP: %d plans, tilt %+d (%s), review=%s", len(plans), tilt, state["market"], review)
    for pid, p in plans.items():
        log.info("  %-4s %s", pid, " | ".join(f"{s['key']}:{s['w']}% {u.g(s['code'], 'name')[:28]}" for s in p["slots"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
