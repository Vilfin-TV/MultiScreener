#!/usr/bin/env python3
"""
build_etf_smart.py
──────────────────
Smart Invest for ETFs → data/etf_smart.json (read by the "Smart Invest" section of etf_momentum.html). No network.

Strategy  : the same monthly strategic decisions as the mutual fund Smart Invest planner (data/mf/smartsip.json):
            asset mix per horizon × risk, valuation tilt and gates, large / mid / small rotation, rate-cycle debt
            choice, gold vs silver, value vs momentum style, sector satellite. Each fund slot is translated to the
            ETF that does the same job:
              core → Nifty 50 · lmcore → Nifty 50 + Midcap 150 · flexi → Nifty Next 50 (Nifty 50 for conservative)
              mid → Midcap 150 · small → Smallcap 250 · value → value or momentum factor ETF (style decision)
              pioneer → Nasdaq 100 / S&P 500 ETF (factor ETF when overseas ETFs trade at a premium)
              theme → sector ETF of the chosen sector (next attractive sector when no ETF qualifies)
              metal → gold or silver ETF · multi → 65% Nifty 50 + 20% liquid + 15% metal
              baf → 50% Nifty 50 + 50% short debt · eqsav → 35% Nifty 50 + 65% short debt · arb / dshort → liquid
              dcore / dmed → rising rates: liquid; neutral: target-maturity bond ETF maturing within the horizon;
                             easing: 10-year gilt ETF (7+ yrs) or target maturity
            Every plan from 3 years holds Indian equity, debt and gold/silver (≥5% each); balanced and riskier plans
            from 5 years also hold a global ETF (≥5%) when one trades near its NAV.
ETF checks: liquidity, regular trading, expense ratio vs peers, premium / discount to NAV, tracking error vs ETFs on
            the same index, fund size, track record, VilfinTV rating. The best ETF by liquidity 30 · cost 25 ·
            tracking 20 · size 15 · track record 10 is chosen; the previous month's ETF is kept unless it fails a
            check or a rival scores 10+ points higher (state in data/etf_smart_state.json, changes only at the
            monthly review).
Usage     : python scripts/build_etf_smart.py
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_etf_extras as X  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("etf_smart")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "etf_smart.json")
STATE = os.path.join(DATA, "etf_smart_state.json")

EQUITY_BASE = {"n50": 11.0, "next50": 12.0, "mid": 13.0, "small": 13.5, "value": 12.5, "momentum": 13.0,
               "sector": 12.5, "global": 12.5}
VAL_KEY = {"n50": "n50", "next50": "nn50", "mid": "mid150", "small": "sml250", "value": "n500", "momentum": "n500"}
# slot id → (label, asset class, tax class, index pattern on idx_norm() names, min traded value ₹ cr/day, min size ₹ cr)
SLOTS = {
    "n50": ("Large-cap core — Nifty 50", "Equity", "equity", r"^nifty 50$|^bse sensex$", 1.0, 500),
    "next50": ("Large-cap breadth — Nifty Next 50", "Equity", "equity", r"^nifty next 50$", 0.5, 200),
    "mid": ("Mid cap — Nifty Midcap 150", "Equity", "equity", r"^nifty midcap 150$", 0.5, 200),
    "small": ("Small cap — Nifty Smallcap 250", "Equity", "equity", r"^nifty smallcap 250$", 0.25, 100),
    "value": ("Value factor", "Equity", "equity", r"^nifty (50 value 20|200 value 30|500 value 50)$|^bse enhanced value$", 0.25, 100),
    "momentum": ("Momentum factor", "Equity", "equity", r"^nifty (200 momentum 30|500 momentum 50)$", 0.25, 100),
    "global": ("Global equity — US large caps", "Global", "other", r"^(nasdaq ?100|s&p 500|s&p 500 top 50|s&amp;p 500 top 50)$", 0.25, 100),
    "gold": ("Gold", "Commodity", "other", None, 1.0, 500),
    "silver": ("Silver", "Commodity", "other", None, 0.5, 200),
    "liquid": ("Liquid / overnight (parking)", "Debt", "debt", None, 1.0, 500),
    "gilt10": ("Government bonds — 10-year gilt", "Debt", "debt", r"10 yr|8 13 yr|10 year gilt", 0.1, 50),
    "gilt5": ("Government bonds — 5-year gilt", "Debt", "debt", r"5 yr benchmark g sec", 0.1, 50),
    "tmat": ("Target-maturity bonds (PSU / government)", "Debt", "debt", r"bharat bond", 0.1, 100),
}
SECTOR_IDX = {
    "bank": r"^nifty bank$|bankex|top 10 bank", "pvtbank": r"private bank", "psubank": r"psu bank",
    "finexbank": r"financial services ex", "fin": r"^nifty financial services$", "capmkt": r"capital market",
    "insurance": r"insurance", "it": r"^nifty it$|^bse it$|information technology", "digital": r"internet|digital",
    "health": r"healthcare|pharma", "hospitals": r"hospital", "fmcg": r"fmcg", "consumption": r"india consumption",
    "newcons": r"new age consumption", "auto": r"^nifty auto$|automobile", "ev": r"\bev\b", "defence": r"defence",
    "infra": r"infrastructure$|^nifty infra", "realty": r"realty", "metal": r"metal", "energy": r"energy",
    "oilgas": r"oil", "power": r"power", "psu": r"cpse|^nifty pse$|bharat 22", "mnc": r"\bmnc\b",
    "commodities": r"commodit", "chemicals": r"chemical", "cement": r"cement", "railpsu": r"railway",
    "tourism": r"tourism", "mfg": r"manufactur", "services": r"services sector", "infralog": r"infrastructure logistics",
}
TAX_NOTE = {"equity": "Equity tax: 20% if sold within 12 months, 12.5% after (₹1.25 lakh gains a year tax-free)",
            "other": "12.5% after 12 months (listed ETF); slab rate within 12 months",
            "debt": "Gains taxed at your income-tax slab, whatever the holding period"}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def round5(parts: dict) -> dict:
    """Round weights to multiples of 5 that still add up to 100 (largest remainders first)."""
    tot = sum(parts.values()) or 1
    raw = {k: v * 100 / tot for k, v in parts.items()}
    base = {k: int(v // 5) * 5 for k, v in raw.items()}
    rest = 100 - sum(base.values())
    for k in sorted(raw, key=lambda k: -(raw[k] - base[k])):
        if rest <= 0:
            break
        base[k] += 5
        rest -= 5
    return {k: v for k, v in base.items() if v > 0}


class ETFs:
    def __init__(self):
        d = json.load(open(os.path.join(DATA, "etf_momentum.json")))
        ex = json.load(open(os.path.join(DATA, "etf_extras.json")))
        self.asof = d["asOf"]
        self.etfs = [e for e in d["etfs"] if e.get("q") not in ("nodata",) and e.get("p")]
        self.ex = ex.get("etfs", {})
        self.names = {e["s"]: X.index_names(e) for e in self.etfs}
        ad = datetime.strptime(self.asof, "%Y-%m-%d")
        self.years = {e["s"]: ((ad - datetime.strptime(e["first"], "%Y-%m-%d")).days / 365.25 if e.get("first") else 0)
                      for e in self.etfs}

    def pool(self, slot: str, pattern: str | None = None) -> list[dict]:
        if slot == "gold":
            return [e for e in self.etfs if e.get("k") == "Gold"]
        if slot == "silver":
            return [e for e in self.etfs if e.get("k") == "Silver"]
        if slot == "liquid":
            return [e for e in self.etfs if X.role_of(e) == "debt" and X.is_liquid(e)]
        pat = pattern or SLOTS[slot][3]
        out = []
        for e in self.etfs:
            if slot in ("gilt5", "gilt10", "tmat") and X.role_of(e) != "debt":
                continue
            if slot not in ("gilt5", "gilt10", "tmat") and X.role_of(e) in ("debt", "com"):
                continue
            if any(re.search(pat, n) for n in self.names[e["s"]] or [""]):
                out.append(e)
        return out


def checks_for(u: ETFs, slot: str, e: dict, pool: list[dict], min_tv: float, min_aum: float) -> list:
    x, ex = e.get("x") or {}, u.ex.get(e["s"], {})
    ters = sorted(p["x"]["ter"] for p in pool if (p.get("x") or {}).get("ter", 0) > 0)
    med_ter = ters[(len(ters) - 1) // 2] if ters else None
    tes = sorted((u.ex.get(p["s"], {}).get("te") or {}).get("te") for p in pool if (u.ex.get(p["s"], {}).get("te") or {}).get("te") is not None)
    med_te = tes[(len(tes) - 1) // 2] if tes else None
    prem_lim = 2.0 if slot == "global" else 0.3 if slot in ("liquid",) else 0.75
    tv, ter, aum, prem, yrs = e.get("tv") or 0, x.get("ter"), x.get("aum"), e.get("prem"), u.years[e["s"]]
    te = (ex.get("te") or {}).get("te")
    rt = ex.get("rt")
    c = [
        ["Liquidity", tv >= min_tv, f"₹{tv:,.2f} cr traded a day (needs ₹{min_tv:g} cr+)"],
        ["Traded every day", e.get("q") == "ok", "regular daily trading" if e.get("q") == "ok" else "thin or irregular trading"],
        ["Expense ratio", not ter or med_ter is None or ter <= med_ter * 1.15 + 0.02,
         (f"{ter:.2f}% vs {med_ter:.2f}% median of {len(ters)} similar ETFs" if ter and med_ter else f"{ter:.2f}%" if ter else
          "not in the latest official expense-ratio file — check the fund house's site")],
        ["Price close to NAV", (prem is None and slot != "global") or (prem is not None and abs(prem) <= prem_lim),
         (("not available — overseas ETFs often trade far above NAV, so a known price is required" if slot == "global" else
           "not available — check the live iNAV") if prem is None else f"{prem:+.2f}% vs NAV at the last close (limit ±{prem_lim:g}%)")],
        ["Tracking", te is None or te <= max(1.0, (med_te or te) * 1.25),
         (f"tracking error {te:.2f}% a year vs {med_te:.2f}% median" if te is not None and med_te is not None else "no other ETF on the same index to compare")],
        ["Fund size", aum is not None and aum >= min_aum, (f"₹{aum:,.0f} cr (needs ₹{min_aum:g} cr+)" if aum is not None else "not disclosed")],
        ["Track record", yrs >= 1, f"{yrs:.1f} years of trading (needs 1+)"],
        ["VilfinTV rating", rt is None or rt["st"] >= 3, (f"{rt['st']}★ · {rt['s']}/100" if rt else "not rated yet")],
    ]
    return c


def pick(u: ETFs, slot: str, pattern: str | None, prev: str | None, min_tv=None, min_aum=None, hold=False) -> dict | None:
    pool = u.pool(slot, pattern)
    if not pool:
        return None
    min_tv = SLOTS[slot][4] if min_tv is None else min_tv
    min_aum = SLOTS[slot][5] if min_aum is None else min_aum
    rows = []
    for e in pool:
        ch = checks_for(u, slot, e, pool, min_tv, min_aum)
        rows.append((e, ch, all(c[1] for c in ch)))
    tv = X.pct_ranks([e.get("tv") for e, _, _ in rows])
    cost = X.pct_ranks([(e.get("x") or {}).get("ter") if ((e.get("x") or {}).get("ter") or 0) > 0 else None for e, _, _ in rows], False)
    trk = X.pct_ranks([(u.ex.get(e["s"], {}).get("te") or {}).get("te") for e, _, _ in rows], False)
    size = X.pct_ranks([(e.get("x") or {}).get("aum") for e, _, _ in rows])
    age = X.pct_ranks([u.years[e["s"]] for e, _, _ in rows])
    scored = []
    for i, (e, ch, ok) in enumerate(rows):
        parts = [(30, tv[i]), (25, cost[i]), (20, trk[i]), (15, size[i]), (10, age[i])]
        have = [(w, p) for w, p in parts if p is not None]
        sc = 100 * sum(w * p for w, p in have) / sum(w for w, _ in have) if have else 0
        scored.append({"e": e, "checks": ch, "ok": ok, "score": round(sc, 1)})
    scored.sort(key=lambda r: (-r["ok"], -r["score"], r["e"]["s"]))
    state = "ok"
    best = scored[0]
    if not best["ok"]:                      # nothing passes every check: best liquid, regularly traded, sizeable ETF
        soft = [r for r in scored if r["checks"][0][1] and r["checks"][1][1] and r["checks"][3][1]
                and ((r["e"].get("x") or {}).get("aum") or 0) >= 50]   # never buy far above NAV
        if not soft:
            return None
        best, state = soft[0], "relaxed"
    if prev and prev != best["e"]["s"]:     # keep last month's ETF unless it fails a check or is clearly beaten
        inc = next((r for r in scored if r["e"]["s"] == prev), None)
        if inc and (inc["ok"] or state == "relaxed") and (hold or best["score"] - inc["score"] < 10):
            best = inc
    alts = [r["e"]["s"] for r in scored if r is not best and r["ok"]][:2]
    return {"sym": best["e"]["s"], "score": best["score"], "checks": best["checks"], "state": state, "alts": alts,
            "pool": len(pool), "passed": sum(1 for r in scored if r["ok"])}


def global_note(u: ETFs) -> str:
    """Why the global sleeve is paused: the premiums of the US ETFs."""
    pool = u.pool("global")
    prem = [f"{e['s']} {e['prem']:+.1f}%" for e in pool if e.get("prem") is not None]
    return ("US-market ETFs are trading well above their NAV (" + ", ".join(prem) + ") because overseas investment limits stop "
            "new units being created — buying now means overpaying. The global share goes to the factor ETF until prices "
            "return close to NAV.") if prem else ("No US-market ETF shows a reliable price versus its NAV right now, so the "
            "global share goes to the factor ETF until one trades close to NAV.")


def main() -> int:
    ss = json.load(open(os.path.join(DATA, "mf", "smartsip.json")))
    macro = json.load(open(os.path.join(DATA, "mf", "macro.json")))
    u = ETFs()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    review = ss.get("reviewed")
    same_month = state.get("month") == review
    prev = state.get("picks", {})
    rates = macro.get("rates") or {}
    tb91 = ((rates.get("tb91") or {}).get("last")) or 6.0
    call = ((rates.get("call") or {}).get("last")) or tb91 - 0.3
    g10 = ((rates.get("g10") or {}).get("last")) or 7.0
    val = macro.get("valuation") or {}
    regime = (ss.get("rates") or {}).get("applied") or (ss.get("rates") or {}).get("regime") or "neutral"
    metal = (ss.get("metal") or {}).get("applied") or (ss.get("metal") or {}).get("choice") or "gold"
    style = (ss.get("style") or {}).get("value") or "value"
    metal_adj = 0.0

    def eq_er(slot, sector=None):
        base = EQUITY_BASE[slot]
        v = val.get(VAL_KEY.get(slot, "")) or {}
        if sector:
            v = {"pe": sector.get("pe"), "peMed": sector.get("peMed")}
        if v.get("pe") and v.get("peMed"):
            base += clamp(((v["peMed"] / v["pe"]) ** 0.1 - 1) * 100, -2.0, 2.0)
        return base

    slots_out, picks = {}, {}

    def resolve(sid: str, pattern=None, label=None, er=None, extra=None):
        if sid in slots_out:
            return sid
        kind = "tmat" if sid.startswith("tmat") else "n50" if sid.startswith("sector:") else sid
        lim = {"tmat": (0.1, 100), "n50": (0.25, 100)}.get(kind) if kind != sid else (None, None)
        p = pick(u, kind, pattern, prev.get(sid), lim[0], lim[1], hold=same_month)
        if not p:
            return None
        e = next(x for x in u.etfs if x["s"] == p["sym"])
        base = SLOTS[kind]
        ter = (e.get("x") or {}).get("ter") or 0
        ter_est = not ter
        if not ter:                         # not in the latest official file: assume the median of similar ETFs
            ts = sorted((x.get("x") or {}).get("ter") for x in u.pool(kind, pattern) if ((x.get("x") or {}).get("ter") or 0) > 0)
            ter = ts[(len(ts) - 1) // 2] if ts else 0.5
        p["ter"], p["terEst"] = round(ter, 3), ter_est
        slots_out[sid] = {"label": label or base[0], "asset": base[1], "tax": base[2], **p, "er": round((er or 0) - ter, 2),
                          "price": e.get("p"), "name": e["n"], **(extra or {})}
        picks[sid] = p["sym"]
        return sid

    # ── sector satellite: the planner's sector, else the next attractive sector with a qualifying ETF ──
    sec_rank = [ss.get("sector")] + [s["key"] for s in sorted(ss.get("sectors") or [], key=lambda s: -(s.get("score") or 0))]
    sector_id = None
    for k in dict.fromkeys(k for k in sec_rank if k):
        s = next((x for x in ss.get("sectors") or [] if x["key"] == k), None)
        if not s or k not in SECTOR_IDX:
            continue
        o = s.get("outlook") or {}
        if (s.get("valPct") or 0) >= 0.8 or o.get("mt") == "neg" or o.get("lt") == "neg":
            continue
        sid = f"sector:{k}"
        if True:
            resolve(sid, SECTOR_IDX[k], f"Sector satellite — {s['label']}", eq_er("sector", s),
                    {"asset": "Equity", "tax": "equity", "sector": s["label"], "signal": s.get("signal")})
            if sid in slots_out:
                slots_out[sid]["asset"], slots_out[sid]["tax"] = "Equity", "equity"
                sector_id = sid
                break
    # ── global: needs an ETF trading near its NAV (overseas ETFs often trade at a premium when the industry limit binds) ──
    global_id = resolve("global", er=eq_er("global"))
    style_id = resolve(style, er=eq_er(style)) or resolve("value" if style == "momentum" else "momentum", er=eq_er("value"))
    metal_id = resolve(metal, er=9.0 + metal_adj) or resolve("gold", er=9.0)
    liquid_id = resolve("liquid", er=call + 0.1)
    for sid, er in (("n50", eq_er("n50")), ("next50", eq_er("next50")), ("mid", eq_er("mid")), ("small", eq_er("small"))):
        resolve(sid, er=er)
    resolve("gilt10", er=g10)
    resolve("gilt5", er=g10 - 0.25)
    this_year = date.today().year

    def tmat_for(years: int) -> str | None:
        """Target-maturity bond ETF maturing within the horizon (latest maturity not after it)."""
        best = None
        for e in u.pool("tmat"):
            m = re.search(r"(20\d\d)", " ".join(u.names[e["s"]]) + " " + e["n"])
            if m and this_year + 1 <= int(m.group(1)) <= this_year + years:
                yr = int(m.group(1))
                if best is None or yr > best:
                    best = yr
        if best is None:
            return None
        sid = f"tmat{best}"
        return resolve(sid, pattern=rf"bharat bond.*{best}", label=f"Target-maturity bonds — matures {best}", er=g10 - 0.1,
                       extra={"asset": "Debt", "tax": "debt", "maturity": best}) if sid not in slots_out else sid

    def debt_for(years: int, short: bool) -> str:
        if short or regime == "rising" or years < 3:
            return liquid_id
        if regime == "easing" and years >= 7 and "gilt10" in slots_out:
            return "gilt10"
        return tmat_for(years) or ("gilt5" if "gilt5" in slots_out else liquid_id)

    plans = {}
    for pid, p in ss["plans"].items():
        hz, rk, yrs = pid[:-1], pid[-1], p.get("years") or 5
        mix: dict[str, float] = {}

        def add(sid, w):
            if sid and w > 0:
                mix[sid] = mix.get(sid, 0) + w

        for s in p["slots"]:
            k, w = s["key"], s.get("w") or 0
            if w <= 0:
                continue
            if k == "core":
                add("n50", w)
            elif k == "lmcore":
                add("n50", w / 2), add("mid", w / 2)
            elif k == "flexi":
                add("n50" if rk == "c" else "next50", w)
            elif k in ("mid", "small"):
                add(k, w)
            elif k in ("value", "momentum"):
                add(style_id or "n50", w)
            elif k == "pioneer":
                add(global_id or style_id or "n50", w)
            elif k == "theme":
                add(sector_id or "n50", w)
            elif k == "metal":
                add(metal_id, w)
            elif k == "multi":
                add("n50", w * 0.65), add(liquid_id, w * 0.2), add(metal_id, w * 0.15)
            elif k == "baf":
                add("n50", w * 0.5), add(debt_for(yrs, hz in ("h1",)), w * 0.5)
            elif k == "eqsav":
                add("n50", w * 0.35), add(liquid_id, w * 0.65)
            elif k in ("arb", "dshort"):
                add(liquid_id, w)
            elif k in ("dcore", "dmed"):
                add(debt_for(yrs, False), w)
            else:
                add("n50", w)
        mix = {k: v for k, v in mix.items() if k in slots_out}
        w = round5(mix)
        # diversification floors: from 3 years every plan holds Indian equity, debt and gold/silver; balanced+ from
        # 5 years also a global sleeve — funded from the largest Indian equity holding
        def asset_w(a):
            return sum(v for k, v in w.items() if slots_out[k]["asset"] == a)

        def take(n):
            donors = sorted([k for k in w if slots_out[k]["asset"] == "Equity"], key=lambda k: -w[k])
            if donors and w[donors[0]] - n >= 10:
                w[donors[0]] -= n
                return True
            return False
        if hz != "h1":
            if asset_w("Commodity") < 5 and metal_id and take(5):
                w[metal_id] = w.get(metal_id, 0) + 5
            if asset_w("Debt") < 5 and take(5):
                d = debt_for(yrs, False)
                w[d] = w.get(d, 0) + 5
        if hz in ("h5", "h7", "h10") and rk in ("b", "a", "v") and asset_w("Global") < 5 and global_id and take(5):
            w[global_id] = w.get(global_id, 0) + 5
        w = {k: v for k, v in sorted(w.items(), key=lambda kv: (-kv[1], kv[0])) if v > 0}
        assets = {}
        for k, v in w.items():
            assets[slots_out[k]["asset"]] = assets.get(slots_out[k]["asset"], 0) + v
        er = sum(v * slots_out[k]["er"] for k, v in w.items()) / 100
        ter = sum(v * slots_out[k]["ter"] for k, v in w.items()) / 100
        plans[pid] = {"horizon": p["horizon"], "risk": p["risk"], "years": yrs, "yearsMin": p.get("yearsMin"),
                      "yearsMax": p.get("yearsMax"), "slots": [{"id": k, "w": v} for k, v in w.items()],
                      "mix": assets, "er": round(er, 2), "ter": round(ter, 3)}
    used = {s["id"] for p in plans.values() for s in p["slots"]}
    slots_out = {k: v for k, v in slots_out.items() if k in used}
    for v in slots_out.values():
        v["taxNote"] = TAX_NOTE[v["tax"]]
    payload = {
        "v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "asOf": u.asof,
        "reviewed": review, "nextReview": ss.get("nextReview"),
        "decisions": {
            "tilt": (ss.get("market") or {}).get("tilt"), "market": (ss.get("market") or {}).get("components"),
            "rotation": (ss.get("market") or {}).get("rotation"), "gates": (ss.get("market") or {}).get("gates"),
            "rates": {"regime": regime, "signals": (ss.get("rates") or {}).get("signals")},
            "metal": {"choice": metal, "note": (ss.get("metal") or {}).get("note")},
            "style": ss.get("style"), "sector": slots_out.get(sector_id, {}).get("sector") if sector_id else None,
            "global": global_id is not None,
            "globalNote": None if global_id else global_note(u),
            "inflation": (ss.get("assumptions") or {}).get("inflation", 5.0),
        },
        "horizons": ss.get("horizons"), "risks": ss.get("risks"), "assumptions": ss.get("assumptions"),
        "slots": slots_out, "plans": plans,
    }
    with open(OUT + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)
    os.replace(OUT + ".tmp", OUT)
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump({"month": review, "picks": {**prev, **{k: v["sym"] for k, v in slots_out.items()}}}, fh, indent=1)
    log.info("ETF Smart Invest: %d plans · %d ETF slots (%s)", len(plans), len(slots_out),
             ", ".join(f"{k}={v['sym']}" for k, v in slots_out.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
