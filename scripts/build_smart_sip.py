#!/usr/bin/env python3
"""Smart SIP planner v2 for the India MF Screener → data/mf/smartsip.json (+ data/mf/smartsip_state.json).

Fifteen model plans — 5 investment horizons × 3 risk levels — each with a fixed set of up to 8 fund slots.
Every slot is filled by the best fund that passes a full checklist, chosen dynamically from market conditions:

* Rate cycle (debt) — policy repo rate (now vs a year ago), the 10-year government bond yield (latest weeks and a
  year ago), T-bill yields, the term spread and how long-duration gilts have done against liquid funds. The
  regime (rising yields / neutral / falling yields) decides which debt categories are eligible: short duration and
  floating rate when yields rise, high-quality corporate / PSU in between, gilt and dynamic bond (for horizons of
  5+ years) when yields fall.
* Valuations — P/E and P/B of the Nifty 50 and of each sector index ranked against their own 10-year history
  (data/mf/val_hist.json via build_macro.py), plus the earnings yield vs the 10-year bond yield.
  - Equity tilt: cheap markets add up to 10 points of equity, expensive markets remove up to 10 (5-point steps,
    combined with drawdown from the 52-week high; horizons under 5 years are not tilted).
  - Sector satellite (7+ year aggressive plans, 5%): sectors — banking, IT, healthcare, consumption,
    infrastructure, real estate & housing, manufacturing & defence, auto, energy, PSU, MNC — are scored on cheapness
    (60%) and relative momentum (40%); expensive sectors (above the 85th valuation percentile) and falling knives
    are excluded; the best fund in the most attractive sector is chosen.
  - Precious metals: gold, or silver when silver is historically cheap against gold (gold/silver ratio in the top
    30% of its range) for 7+ year aggressive plans.
* Checks on every fund (all must pass to enter a plan; shown on the page): track record, fund size, expense ratio
  vs category median, accepting SIPs, no lock-in, status, benchmark beaten in rolling 3-year periods, rolling return
  vs category, consistency, drawdown vs category, style / market-cap fit, portfolio concentration, fund-manager
  tenure; debt adds credit quality (from the monthly portfolio where available), no credit events (drawdown limit
  per category), volatility vs category and rate-cycle fit; index / passive funds add tracking.
* Diversification — top-holding overlap kept low, at most two funds per fund house.
* Stability — the number of funds is fixed per plan; reviewed monthly; a fund that slips is put on watch and
  replaced only after two failed reviews (at once if it stops accepting SIPs or goes "Out of track"); regime,
  sector and metal choices also change only at a monthly review. Existing units are never sold.
* Expected returns — per slot, from current yields (debt), valuation-adjusted long-run equity returns, net of the
  fund's expense ratio, with volatility for a likely range. The page projects the SIP over the chosen years and
  applies Indian capital-gains tax per fund (equity-oriented, debt at slab, other) for a post-tax outcome.
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
VERSION = 2
log = logging.getLogger("smartsip")

HORIZONS = [("h1", "Under 3 years", 2, 1, 3), ("h3", "3–5 years", 4, 3, 5), ("h5", "5–7 years", 6, 5, 7),
            ("h7", "7–10 years", 8, 7, 10), ("h10", "10+ years", 15, 10, 30)]
RISKS = [("c", "Conservative"), ("b", "Balanced"), ("a", "Aggressive")]

# slot → label, asset, candidate subs (None = decided at run time), kind, min years, min AUM (₹ cr), volatility %
SLOTS = {
    "core":   ("Large-cap core (Nifty 50 index)", "Equity", ["idx_large"], "index", 3, 500, 15),
    "flexi":  ("Diversified equity (flexi / multi / large & mid)", "Equity", ["flexi", "multi", "largemid"], "active", 5, 1000, 16),
    "mid":    ("Mid cap", "Equity", ["mid"], "active", 5, 1000, 19),
    "small":  ("Small cap", "Equity", ["small"], "active", 5, 1000, 23),
    "baf":    ("Balanced advantage (dynamic)", "Hybrid", ["baf"], "active", 5, 1000, 9),
    "eqsav":  ("Equity savings", "Hybrid", ["eqsavings"], "hybrid", 5, 300, 5),
    "arb":    ("Arbitrage", "Hybrid", ["arbitrage"], "arb", 3, 1000, 0.7),
    "dshort": ("Short-term debt", "Debt", None, "debt", 3, 1000, 0.8),
    "dcore":  ("Core debt", "Debt", None, "debt", 3, 1000, 2.5),
    "metal":  ("Precious metals", "Commodity", None, "passive", 3, 200, 15),
    "theme":  ("Sector satellite", "Equity", None, "sector", 5, 300, 22),
    "intl":   ("International satellite", "International", ["us", "global"], "intl", 3, 300, 17),
}
TEMPLATES = {
    "h1c":  {"arb": 40, "dshort": 60},
    "h1b":  {"arb": 35, "eqsav": 20, "dshort": 45},
    "h1a":  {"arb": 30, "baf": 25, "dshort": 45},
    "h3c":  {"core": 15, "baf": 25, "dcore": 50, "metal": 10},
    "h3b":  {"core": 25, "flexi": 15, "baf": 20, "dcore": 30, "metal": 10},
    "h3a":  {"core": 30, "flexi": 25, "baf": 15, "dcore": 20, "metal": 10},
    "h5c":  {"core": 25, "flexi": 10, "baf": 20, "dcore": 35, "metal": 10},
    "h5b":  {"core": 30, "flexi": 20, "mid": 10, "baf": 10, "dcore": 20, "metal": 10},
    "h5a":  {"core": 30, "flexi": 25, "mid": 15, "small": 5, "dcore": 15, "metal": 10},
    "h7c":  {"core": 30, "flexi": 15, "baf": 15, "dcore": 30, "metal": 10},
    "h7b":  {"core": 30, "flexi": 20, "mid": 15, "small": 5, "dcore": 20, "metal": 10},
    "h7a":  {"core": 25, "flexi": 20, "mid": 15, "small": 10, "theme": 5, "intl": 10, "dcore": 10, "metal": 5},
    "h10c": {"core": 30, "flexi": 20, "mid": 5, "baf": 10, "dcore": 25, "metal": 10},
    "h10b": {"core": 30, "flexi": 20, "mid": 15, "small": 10, "dcore": 15, "metal": 10},
    "h10a": {"core": 25, "flexi": 20, "mid": 15, "small": 15, "theme": 5, "intl": 10, "dcore": 5, "metal": 5},
}
ORDER = ["core", "flexi", "mid", "small", "theme", "baf", "eqsav", "arb", "dcore", "dshort", "metal", "intl"]
FALLBACK = {"intl": ["flexi", "core"], "theme": ["flexi", "core"], "small": ["mid", "flexi"], "mid": ["flexi", "core"],
            "flexi": ["core"], "core": ["flexi"], "metal": ["dcore", "dshort"], "eqsav": ["arb", "baf"], "baf": ["core", "dcore"],
            "dcore": ["dshort", "baf"], "dshort": ["dcore", "arb"], "arb": ["dshort"]}

# debt pools by rate regime
DEBT_POOLS = {
    "dshort": {"rising": ["money", "floater", "ultrashort"], "neutral": ["money", "lowdur", "ultrashort"],
               "easing": ["money", "lowdur", "ultrashort"]},
    "dcore": {"rising": ["shortdur", "bankpsu", "floater"], "neutral": ["corpbond", "bankpsu", "shortdur"],
              "easing": ["corpbond", "bankpsu", "shortdur"], "easing_long": ["gilt", "dynbond", "gilt10", "corpbond"]},
}
DEBT_LABEL = {
    ("dshort", "rising"): "Short-term debt (money market / floating rate)", ("dshort", "neutral"): "Short-term debt (money market / low duration)",
    ("dshort", "easing"): "Short-term debt (money market / low duration)", ("dcore", "rising"): "Core debt (short duration / floating rate)",
    ("dcore", "neutral"): "Core debt (corporate bond / banking & PSU)", ("dcore", "easing"): "Core debt (corporate bond / banking & PSU)",
    ("dcore", "easing_long"): "Core debt (gilt / dynamic bond — duration)",
}
# worst acceptable 3-year drawdown per debt category (a deeper fall means a credit or liquidity event)
DEBT_MDD = {"overnight": -0.3, "liquid": -0.5, "money": -0.5, "ultrashort": -0.75, "lowdur": -1.0, "floater": -1.5,
            "shortdur": -2.0, "bankpsu": -2.0, "corpbond": -2.5, "gilt": -6.0, "gilt10": -7.0, "dynbond": -6.0}

# sector satellite: key → label, index keys (valuation), fund subs, name filter (include / exclude)
SECTORS = [
    ("bank", "Banking & financial", ["fin", "bank"], ["sec_bank", "idx_bank"], None, None),
    ("it", "IT & technology", ["it"], ["sec_tech", "idx_tech"], None, None),
    ("health", "Healthcare & pharma", ["health", "pharma"], ["sec_pharma", "idx_health"], None, None),
    ("consumption", "Consumption", ["consumption", "fmcg"], ["sec_consumption", "idx_consumption"], None, None),
    ("infra", "Infrastructure", ["infra"], ["sec_infra", "idx_infra"], None, r"housing|realty|real estate|reit"),
    ("realty", "Real estate & housing", ["realty", "housing"], ["sec_infra", "idx_infra"], r"housing|realty|real estate|reit", None),
    ("mfg", "Manufacturing & defence", ["mfg", "defence"], ["sec_mfg", "idx_mfg"], None, r"\bauto|mobility|transport"),
    ("auto", "Auto & mobility", ["auto"], ["sec_mfg", "idx_mfg", "sec_infra", "idx_theme", "sec_innov", "sec_other"], r"\bauto|mobility|\bev\b|transport", None),
    ("energy", "Energy & commodities", ["energy", "commodities"], ["sec_energy"], None, None),
    ("psu", "PSU", ["cpse", "pse"], ["sec_psu"], None, None),
    ("mnc", "MNC", ["mnc"], ["sec_mnc"], None, None),
]
RX_NIFTY50 = re.compile(r"\bnifty 50\b(?!\s*(equal|value|quality|low|momentum|alpha|shariah|arbitrage))", re.I)
RX_NOT_CORE = re.compile(r"elss|tax saver|next 50|equal weight|value|quality|momentum|low vol|alpha", re.I)
RX_INTL_THEME = re.compile(r"mining|clean energy|energy|innovation|technology|tech\b|agri|real estate|reit|ev\b|electric|"
                           r"healthcare|consumer|commodit|fang|nasdaq|china|brazil|japan|taiwan|asean|emerging|india", re.I)
SAFE_CREDIT = ("AAA", "Sovereign", "A1+", "Cash")
EQUITY_BASE = {"core": 11.0, "flexi": 12.0, "mid": 13.0, "small": 13.5, "theme": 12.5, "intl": 10.0}
EQUITY_VAL_KEY = {"core": "n50", "flexi": "n500", "mid": "mid150", "small": "sml250"}
ASSUMPTIONS = {"inflation": 5.0, "cess": 4.0, "stcgEquity": 20.0, "ltcgEquity": 12.5, "ltcgExempt": 125000, "ltcgOther": 12.5,
               "equityLtMonths": 12, "otherLtMonths": 24, "metalReturn": 9.0}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


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


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def pct_rank(vals: dict, higher=True):
    """code → percentile 0..1 among known values; unknown → 0.35."""
    known = sorted((v, k) for k, v in vals.items() if v is not None and not (isinstance(v, float) and math.isnan(v)))
    out = {k: 0.35 for k in vals}
    n = len(known)
    if n == 1:
        out[known[0][1]] = 0.6
    for i, (v, k) in enumerate(known):
        if n > 1:
            lo = next(j for j in range(n) if known[j][0] == v)
            hi = max(j for j in range(n) if known[j][0] == v)
            p = ((lo + hi) / 2) / (n - 1)
            out[k] = p if higher else 1 - p
    return out


def median(vals):
    v = [x for x in vals if x is not None]
    return st.median(v) if v else None


def parse_since(s: str):
    s = (s or "").strip().lower()
    m = re.search(r"(\d{1,2})[-/ .]([a-z]{3,9}|\d{1,2})[-/ .,]*(\d{4})", s)
    if m:
        mon = MONTHS.get(m.group(2)[:3]) if m.group(2).isalpha() else int(m.group(2))
        try:
            return date(int(m.group(3)), mon or 1, min(int(m.group(1)), 28))
        except (TypeError, ValueError):
            return None
    m = re.search(r"([a-z]{3,9})\.?\s*[-,]?\s*(\d{4})", s)
    if m and m.group(1)[:3] in MONTHS:
        return date(int(m.group(2)), MONTHS[m.group(1)[:3]], 1)
    m = re.search(r"\b(19|20)(\d{2})\b", s)
    return date(int(m.group(0)), 7, 1) if m else None


class Universe:
    def __init__(self, scr, today):
        self.cols = {c: i for i, c in enumerate(scr["cols"])}
        self.rows = {r[0]: r for r in scr["rows"]}
        self.amcs = scr["amcs"]
        self.today = today
        self.pf, self.det = {}, {}
        for sub in {r[self.cols["sub"]] for r in scr["rows"]}:
            for code, v in (load(MF / "p" / f"{sub}.json", {}) or {}).items():
                self.pf[int(code)] = v
        self.ter_med, self.cat_med = {}, {}

    def g(self, code, col):
        r = self.rows.get(code)
        return r[self.cols[col]] if r is not None and col in self.cols else None

    def by_subs(self, subs):
        return [c for c, r in self.rows.items() if r[self.cols["sub"]] in subs]

    def info(self, code):
        sub = self.g(code, "sub")
        if sub and sub not in self.det:
            self.det[sub] = load(MF / "d" / f"{sub}.json", {}) or {}
        return ((self.det.get(sub) or {}).get(str(code)) or {}).get("info") or {}

    def holdings(self, code):
        p = self.pf.get(code) or {}
        return {h[3]: h[2] for h in (p.get("top") or []) if len(h) > 4 and h[3] and h[4] in ("equity", "overseas")}

    def overlap(self, a, b):
        ha, hb = self.holdings(a), self.holdings(b)
        if not ha or not hb:
            return None
        return round(sum(min(w, hb[i]) for i, w in ha.items() if i in hb), 1)

    def credit_share(self, code):
        cr = (self.pf.get(code) or {}).get("credit")
        if not cr:
            return None
        safe = sum(w for k, w in cr if any(s.lower() in k.lower() for s in SAFE_CREDIT))
        tot = sum(w for _, w in cr) or 100
        return round(safe / tot * 100, 1)

    def manager_since(self, code):
        ds = [parse_since(m.get("since", "")) for m in (self.info(code).get("managers") or [])]
        ds = [d for d in ds if d and d <= self.today]
        return max(ds) if ds else None, min(ds) if ds else None     # newest, longest-serving

    def category_stats(self, subs):
        key = tuple(sorted(subs))
        if key not in self.cat_med:
            codes = self.by_subs(subs)
            self.cat_med[key] = {c: median([self.g(x, c) for x in codes]) for c in ("ter", "roll3", "mdd", "std", "r3y", "r1y", "cons")}
        return self.cat_med[key]


# ───────────────────────────── market conditions ─────────────────────────────
def rate_regime(macro, u):
    """Rising / neutral / easing from the policy rate, the 10-year yield, the curve and gilt vs liquid performance."""
    r = (macro or {}).get("rates") or {}
    sig, score = [], 0.0

    def add(label, reading, pts):
        nonlocal score
        score += pts
        sig.append({"k": label, "v": reading, "p": pts})
    repo, g10 = r.get("repo") or {}, r.get("g10") or {}
    if repo.get("last") is not None and repo.get("yearAgo") is not None:
        d = repo["last"] - repo["yearAgo"]
        add("Policy repo rate", f"{repo['last']:.2f}% ({'cut' if d < 0 else 'raised' if d > 0 else 'unchanged'} {abs(d):.2f} pt in a year)",
            1 if d < 0 else (-1 if d > 0 else 0))
    if g10.get("last") is not None:
        wk = g10.get("weeks") or []
        if len(wk) >= 2:
            d = wk[-1] - wk[0]
            add("10-year bond yield, recent weeks", f"{wk[0]:.2f}% → {wk[-1]:.2f}%", 1 if d < -0.15 else (-1 if d > 0.15 else 0))
        if g10.get("yearAgo") is not None:
            d = g10["last"] - g10["yearAgo"]
            add("10-year bond yield vs a year ago", f"{g10['yearAgo']:.2f}% → {g10['last']:.2f}%", 1 if d < -0.3 else (-1 if d > 0.3 else 0))
        if repo.get("last") is not None:
            sp = g10["last"] - repo["last"]
            add("Term spread (10-year minus repo)", f"{sp:.2f} pt", 0.5 if sp > 1.5 else (-0.5 if sp < 0.75 else 0))
    gilt = median([u.g(c, "r6m") for c in u.by_subs(["gilt10", "gilt"])])
    liq = median([u.g(c, "r6m") for c in u.by_subs(["liquid"])])
    if gilt is not None and liq is not None:
        d = gilt - liq
        add("Gilt funds vs liquid funds, 6 months", f"{d:+.2f} pt", 1 if d > 1.0 else (-1 if d < -0.5 else 0))
    regime = "easing" if score >= 1.5 else ("rising" if score <= -1.5 else "neutral")
    return {"regime": regime, "score": round(score, 2), "signals": sig,
            "repo": repo.get("last"), "g10": g10.get("last"), "g10YearAgo": g10.get("yearAgo"),
            "tb91": (r.get("tb91") or {}).get("last"), "tb364": (r.get("tb364") or {}).get("last"),
            "call": (r.get("call") or {}).get("last")}


def market_tilt(u, macro, sentiment):
    """Equity tilt in points (−10…+10, 5-pt steps) from valuation, the bond-yield gap and drawdown."""
    val = (macro or {}).get("valuation") or {}
    n50 = val.get("n50") or {}
    comps, t = [], 0

    def add(label, reading, pts):
        nonlocal t
        t += pts
        comps.append({"k": label, "v": reading, "p": pts})
    vp = [x for x in (n50.get("pePct"), n50.get("pbPct")) if x is not None]
    if vp:
        p = sum(vp) / len(vp)
        pts = 10 if p <= 0.2 else 5 if p <= 0.35 else -10 if p >= 0.85 else -5 if p >= 0.7 else 0
        add("Nifty 50 valuation vs 10 years", f"P/E {n50.get('pe')} · P/B {n50.get('pb')} · {ordinal(round(p * 100))} percentile", pts)
    g10 = (((macro or {}).get("rates") or {}).get("g10") or {}).get("last")
    if n50.get("pe") and g10:
        gap = 100 / n50["pe"] - g10
        add("Earnings yield vs 10-year bond yield", f"{100 / n50['pe']:.2f}% vs {g10:.2f}% ({gap:+.2f} pt)",
            5 if gap > -1.0 else (-5 if gap < -3.5 else 0))
    for code in (147625, 118581):           # drawdown of the broad market from its 52-week high
        h = load(MF / "h" / f"{code}.json") or {}
        if not h.get("p"):
            continue
        s0 = date.fromisoformat(h["s"])
        pts = [(s0 + timedelta(days=d), v) for d, v in h["p"]]
        nav = u.g(code, "nav")
        if nav:
            pts.append((date.fromisoformat(u.g(code, "navDate")), nav))
        last_d, last = pts[-1]
        hi = max(v for d, v in pts if d >= last_d - timedelta(days=365))
        dd = (last / hi - 1) * 100
        add("Broad market vs 52-week high", f"{dd:.1f}%", 5 if dd <= -12 else (-5 if dd > -2 else 0))
        break
    zone = next((m.get("zone") for m in (sentiment or {}).get("markets", []) if m.get("country") == "India"), None)
    if zone in ("Extreme Fear", "Extreme Greed"):
        add("Market sentiment", zone, 5 if zone == "Extreme Fear" else -5)
    tilt = int(clamp(round(t / 5) * 5, -10, 10))
    return tilt, comps


def sector_table(u, macro):
    val = (macro or {}).get("valuation") or {}
    rows = []
    for key, label, idx, subs, inc, exc in SECTORS:
        v = next((val[k] for k in idx if k in val and val[k].get("pe")), None)
        if not v:
            continue
        vp = [x for x in (v.get("pePct"), v.get("pbPct")) if x is not None]
        rows.append({"key": key, "label": label, "index": next(k for k in idx if k in val), "pe": v.get("pe"), "pb": v.get("pb"),
                     "peMed": v.get("peMed"), "valPct": round(sum(vp) / len(vp), 3) if vp else None,
                     "r6mRel": v.get("r6mRel"), "r12mRel": v.get("r12mRel"), "r6m": v.get("r6m")})
    mom = pct_rank({r["key"]: r.get("r6mRel") for r in rows})
    for r in rows:
        cheap = 1 - r["valPct"] if r["valPct"] is not None else 0.5
        r["score"] = round(0.6 * cheap + 0.4 * mom[r["key"]], 3)
        reasons = []
        if r["valPct"] is not None and r["valPct"] > 0.85:
            reasons.append("expensive vs its own history")
        if (r.get("r12mRel") or 0) < -25 and (r["valPct"] or 1) > 0.2:
            reasons.append("sharp relative decline without valuation support")
        r["excluded"] = reasons
        r["signal"] = "Avoid" if reasons else ("Attractive" if r["score"] >= 0.6 else ("Neutral" if r["score"] >= 0.4 else "Unattractive"))
    rows.sort(key=lambda r: (bool(r["excluded"]), -r["score"]))
    return rows


def sector_funds(u, key):
    s = next(x for x in SECTORS if x[0] == key)
    codes = u.by_subs(s[3])
    if s[4]:
        codes = [c for c in codes if re.search(s[4], u.g(c, "name") or "", re.I)]
    if s[5]:
        codes = [c for c in codes if not re.search(s[5], u.g(c, "name") or "", re.I)]
    return codes


def metal_signal(u):
    """Gold/silver ratio from the longest-running gold and silver funds; high ratio = silver cheap vs gold."""
    def longest(sub, rx):
        cands = [c for c in u.by_subs([sub]) if re.search(rx, u.g(c, "name") or "", re.I)]
        return min(cands, key=lambda c: u.g(c, "inc") or "9999") if cands else None
    g, s = longest("gold", r"gold"), longest("silver", r"silver")
    if not g or not s:
        return {"choice": "gold", "note": "silver data unavailable"}

    def series(code):
        h = load(MF / "h" / f"{code}.json") or {}
        if not h.get("p"):
            return {}
        s0 = date.fromisoformat(h["s"])
        return {(s0 + timedelta(days=d)).isocalendar()[:2]: v for d, v in h["p"]}
    gs, ss = series(g), series(s)
    common = sorted(set(gs) & set(ss))
    if len(common) < 120:
        return {"choice": "gold", "note": "not enough silver history"}
    ratios = [gs[k] / ss[k] for k in common]
    cur = (u.g(g, "nav") or gs[common[-1]]) / (u.g(s, "nav") or ss[common[-1]])
    pct = sum(1 for r in ratios if r < cur) / len(ratios)
    smom = u.g(s, "r3m")
    choice = "silver" if pct >= 0.7 and (smom is None or smom > -10) else "gold"
    return {"choice": choice, "ratioPct": round(pct, 3), "silver3m": smom, "gold3m": u.g(g, "r3m"),
            "years": round(len(common) / 52, 1),
            "note": "Silver is cheap relative to gold" if choice == "silver" else
                    ("Gold preferred — silver not cheap enough relative to gold" if pct < 0.7 else "Gold preferred — silver momentum weak")}


# ───────────────────────────── per-fund checks ─────────────────────────────
def buy_ok(u, code):
    b = u.g(code, "buy")
    return True if b is None else ("S" in b)


def fund_checks(u, slot, code, ctx):
    """[(label, passed, detail)] — every item must pass for a fund to enter a plan."""
    label, asset, _subs, kind, min_y, min_aum, _vol = SLOTS[slot]
    subs = ctx["subs"]
    cs = u.category_stats(subs)
    g = lambda c: u.g(code, c)  # noqa: E731
    name, sub = g("name") or "", g("sub") or ""
    is_idx = sub.startswith("idx_")
    out = []

    def chk(lab, ok, det=""):
        out.append([lab, bool(ok), det])
    y = years_since(g("inc"), u.today)
    my = 3 if (kind == "sector" and is_idx) else min_y
    chk("Track record", y >= my, f"{y:.1f} years (needs {my}+)")
    ma = 100 if (kind == "sector" and is_idx) else (500 if sub in ("gilt", "dynbond", "gilt10", "floater") else min_aum)
    chk("Fund size", (g("aum") or 0) >= ma, f"₹{(g('aum') or 0):,.0f} cr (needs ₹{ma:,} cr+)")
    ter, med = g("ter"), cs.get("ter")
    tol = 0.05 if asset == "Debt" or kind in ("index", "passive", "arb") or is_idx else 0.10
    chk("Expense ratio", ter is not None and (med is None or ter <= med + tol),
        (f"{ter:.2f}% vs category median {med:.2f}%" if ter is not None else "not disclosed") if med is not None else f"{ter}%")
    chk("Accepting SIPs", buy_ok(u, code), "open for new SIPs" if buy_ok(u, code) else "fresh SIPs paused")
    chk("No lock-in", not ((g("lock") or 0) > 0 or re.search(r"elss|tax saver", name, re.I)), "redeemable any time")
    chk("Status", g("status") != "Out of track" and not (kind in ("active", "sector", "hybrid") and g("status") == "Underperforming"),
        g("status") or "not rated yet")
    if kind in ("active", "sector") and not is_idx:
        b3 = g("beat3")
        chk("Beats benchmark (rolling 3Y)", b3 is not None and b3 >= 50, f"{b3:.0f}% of periods" if b3 is not None else "no 3-year record")
        r3, rm = g("roll3"), cs.get("roll3")
        chk("Rolling 3Y return vs category", r3 is not None and (rm is None or r3 >= rm),
            f"{r3:.1f}% vs median {rm:.1f}%" if r3 is not None and rm is not None else "–")
        c = g("cons")
        chk("Consistency", c is None or c >= 40, f"{c:.0f}/100" if c is not None else "not scored")
        md, mm = g("mdd"), cs.get("mdd")
        chk("Drawdown vs category", md is None or mm is None or md >= mm - 5,
            f"{md:.1f}% vs median {mm:.1f}%" if md is not None and mm is not None else "–")
        newest, longest = u.manager_since(code)
        if longest:
            chk("Fund-manager tenure", (u.today - longest).days >= 365, f"longest-serving manager since {longest:%b %Y}")
        top10 = (u.pf.get(code) or {}).get("top10")
        if top10 and slot in ("flexi", "mid", "small"):
            chk("Portfolio concentration", top10 <= 60, f"top 10 holdings {top10:.0f}%")
    if slot == "flexi":
        chk("Market-cap fit", g("size") not in ("Mid", "Small"), f"{g('size') or 'blend'} tilt (mid / small caps have their own slots)")
    if slot == "mid":
        chk("Market-cap fit", g("size") not in ("Large",), f"{g('size') or 'blend'} tilt")
    if slot == "small":
        chk("Market-cap fit", g("size") not in ("Large", "Multi"), f"{g('size') or 'blend'} tilt")
        chk("Size manageable for small caps", (g("aum") or 0) <= 40000, f"₹{(g('aum') or 0):,.0f} cr")
    if slot == "core":
        chk("Tracks the Nifty 50", bool(RX_NIFTY50.search(name)) and not RX_NOT_CORE.search(name), "plain Nifty 50 index fund")
    if kind in ("index", "passive") or is_idx:
        rmed = median([u.g(c, "r3y") for c in u.by_subs([sub])]) if sub else None
        td = None if g("r3y") is None or rmed is None else abs(g("r3y") - rmed)
        chk("Tracking vs peers", td is None or td <= (0.6 if kind != "sector" else 1.5), f"3Y return within {td:.2f} pt of peers" if td is not None else "new")
    if asset == "Debt" or kind == "arb":
        sd, sm = g("std"), cs.get("std")
        chk("Volatility vs category", sd is None or sm is None or sd <= sm * 1.5, f"{sd:.2f} vs median {sm:.2f}" if sd is not None and sm is not None else "–")
        r3 = g("r3y")
        chk("3-year record", r3 is not None, f"{r3:.2f}% a year" if r3 is not None else "")
    if asset == "Debt":
        lim = DEBT_MDD.get(sub, -2.5)
        md = g("mdd")
        chk("No credit events", md is None or md >= lim, f"worst fall {md:.2f}% (limit {lim}%)" if md is not None else "no drawdown record")
        cq = u.credit_share(code)
        chk("Credit quality", cq is None or cq >= 85, f"{cq:.0f}% AAA / sovereign / A1+" if cq is not None else "high-quality category (portfolio not yet published)")
        chk("Rate-cycle fit", sub in subs, f"suits a {ctx['regime']} rate cycle")
    if kind == "arb":
        r1, m1 = g("r1y"), cs.get("r1y")
        chk("1Y return vs category", r1 is None or m1 is None or r1 >= m1 - 0.3, f"{r1:.2f}% vs median {m1:.2f}%" if r1 is not None and m1 is not None else "–")
    if slot == "intl":
        chk("Diversified mandate", not RX_INTL_THEME.search(name), "broad overseas market")
        b = g("buy")
        chk("Accepting lump sum", b is None or "L" in b, "open for fresh money")
    if slot == "metal":
        chk("Metal", re.search(ctx["metal"], name, re.I) is not None, f"{ctx['metal']} fund")
    if slot == "theme":
        chk("Sector valuation", True, f"{ctx.get('sector_label', '')} chosen on valuation and momentum")
    return out


def scores(u, slot, codes, kind):
    m = lambda col: {c: u.g(c, col) for c in codes}  # noqa: E731
    logaum = {c: math.log10(max(u.g(c, "aum") or 1, 1)) for c in codes}
    if kind in ("index", "passive"):
        r3 = [u.g(c, "r3y") for c in codes if u.g(c, "r3y") is not None]
        med = st.median(r3) if r3 else None
        track = {c: (None if u.g(c, "r3y") is None or med is None else -abs(u.g(c, "r3y") - med)) for c in codes}
        parts = [(pct_rank(m("ter"), False), .40), (pct_rank(logaum), .35), (pct_rank(track), .25)]
    elif kind in ("debt", "arb"):
        exitnil = {c: (1 if u.g(c, "exitNil") else 0) for c in codes}
        parts = [(pct_rank(m("r3y")), .20), (pct_rank(m("r1y")), .10), (pct_rank(m("cons")), .15), (pct_rank(m("sharpe")), .15),
                 (pct_rank(m("std"), False), .10), (pct_rank(m("mdd")), .10), (pct_rank(m("ter"), False), .10),
                 (pct_rank(logaum), .05), (pct_rank(exitnil), .05)]
    elif kind == "intl":
        parts = [(pct_rank(m("r5y")), .20), (pct_rank(m("r3y")), .15), (pct_rank(m("sortino")), .20),
                 (pct_rank(m("mdd")), .10), (pct_rank(m("ter"), False), .20), (pct_rank(logaum), .15)]
    else:
        rec_w = .12 if kind == "sector" else .07
        parts = [(pct_rank(m("roll3")), .20), (pct_rank(m("beat3")), .17), (pct_rank(m("cons")), .14),
                 (pct_rank(m("sortino")), .14), (pct_rank(m("mdd")), .10), (pct_rank(m("r5y")), .08),
                 (pct_rank(m("rec")), rec_w), (pct_rank(m("ter"), False), .06), (pct_rank(logaum), .04)]
    tw = sum(w for _, w in parts)
    return {c: round(100 * sum(p[c] * w for p, w in parts) / tw, 1) for c in codes}


def pool_for(u, slot, ctx):
    """(subs, candidate codes, kind) for a slot given the plan context."""
    label, asset, subs, kind, *_ = SLOTS[slot]
    if slot in DEBT_POOLS:
        subs = DEBT_POOLS[slot][ctx["pool_key"]]
        return subs, u.by_subs(subs), kind
    if slot == "metal":
        subs = [ctx["metal"]]
        return subs, u.by_subs(subs), kind
    if slot == "theme":
        codes = sector_funds(u, ctx["sector"])
        return sorted({u.g(c, "sub") for c in codes}), codes, kind
    return subs, u.by_subs(subs), kind


def rank_pool(u, slot, ctx, cache):
    key = (slot, ctx.get("pool_key"), ctx.get("metal"), ctx.get("sector"))
    if key in cache:
        return cache[key]
    subs, codes, kind = pool_for(u, slot, ctx)
    cctx = {**ctx, "subs": subs}
    checks = {c: fund_checks(u, slot, c, cctx) for c in codes}
    ok = [c for c in codes if all(x[1] for x in checks[c])]
    if kind == "sector":
        act = [c for c in ok if not (u.g(c, "sub") or "").startswith("idx_")]
        idx = [c for c in ok if (u.g(c, "sub") or "").startswith("idx_")]
        sc = {**(scores(u, slot, act, "active") if act else {}), **(scores(u, slot, idx, "index") if idx else {})}
    else:
        sc = scores(u, slot, ok, kind) if ok else {}
    ranked = sorted(ok, key=lambda c: -sc[c])
    cache[key] = (ranked, sc, checks, subs)
    return cache[key]


def expected_return(u, slot, code, ctx, macro):
    rates = (macro or {}).get("rates") or {}
    val = (macro or {}).get("valuation") or {}
    tb91 = ((rates.get("tb91") or {}).get("last")) or 6.0
    tb364 = ((rates.get("tb364") or {}).get("last")) or tb91 + 0.3
    g10 = ((rates.get("g10") or {}).get("last")) or tb364 + 0.7

    def eq(s):
        base = EQUITY_BASE.get(s, 12.0)
        vk = EQUITY_VAL_KEY.get(s) or (ctx.get("sector_index") if s == "theme" else None)
        v = val.get(vk) or {}
        if v.get("pe") and v.get("peMed"):
            base += clamp(((v["peMed"] / v["pe"]) ** 0.1 - 1) * 100, -2.0, 2.0)
        return base
    sub = u.g(code, "sub")
    if slot in ("core", "flexi", "mid", "small", "theme", "intl"):
        gross = eq(slot)
    elif slot == "baf":
        gross = 0.6 * eq("core") + 0.4 * (tb364 + 0.6)
    elif slot == "eqsav":
        gross = 0.35 * eq("core") + 0.65 * (tb364 + 0.3)
    elif slot == "arb":
        gross = tb91 - 0.1
    elif slot == "dshort":
        gross = tb91 + (0.5 if sub == "floater" else 0.3)
    elif slot == "dcore":
        gross = g10 if sub in ("gilt", "gilt10", "dynbond") else tb364 + (0.5 if sub == "floater" else 0.6)
    elif slot == "metal":
        gross = ASSUMPTIONS["metalReturn"]
    else:
        gross = 8.0
    return round(gross - (u.g(code, "ter") or 0), 2)


def why(u, slot, code):
    g = lambda c: u.g(code, c)  # noqa: E731
    out = []
    y = years_since(g("inc"), u.today)
    if y >= 1:
        out.append(f"{int(y)}-year track record")
    if g("beat3") is not None and SLOTS[slot][3] in ("active", "sector"):
        out.append(f"Beat its benchmark in {g('beat3'):.0f}% of rolling 3-year periods")
    if g("roll3") is not None and SLOTS[slot][3] in ("active", "intl", "sector"):
        out.append(f"Average rolling 3-year return {g('roll3'):.1f}%")
    if g("ter") is not None:
        out.append(f"Expense ratio {g('ter'):.2f}%")
    if g("mdd") is not None:
        out.append(f"Max drawdown (3 yrs) {g('mdd'):.1f}%")
    if g("aum") is not None:
        out.append(f"Fund size ₹{g('aum'):,.0f} cr")
    return out[:5]


def choose(u, slot, ctx, chosen, amc_count, incumbent, review, cache):
    """(code, alternates, action, note)."""
    ranked, sc, checks, subs = rank_pool(u, slot, ctx, cache)

    def overlap_ok(c):
        for o, oslot in chosen.items():
            ov = u.overlap(c, o)
            lim = 30 if "core" in (slot, oslot) else 20
            if ov is not None and ov > lim:
                return False
        return True

    def fits(c):
        return amc_count.get(u.g(c, "amc"), 0) < 2 and overlap_ok(c) and c not in chosen
    cand = [c for c in ranked if fits(c)] or [c for c in ranked if c not in chosen]
    if incumbent:
        code = incumbent["code"]
        hard = u.g(code, "sub") is not None and buy_ok(u, code) and u.g(code, "status") != "Out of track"
        strategic = incumbent.get("ctx") == ctx.get("ctx_tag")
        if not hard:
            new = cand[0] if cand else None
            return new, cand[1:3], "replaced", "Previous fund replaced: closed to SIPs, out of track or no longer listed"
        if not strategic:
            if code in ranked:
                return code, [c for c in cand if c != code][:2], "kept", ""
            new = cand[0] if cand else None
            if new is not None:
                return new, [c for c in cand if c != new][:2], "replaced", "Moved at the monthly review to match current market conditions"
        if not review:
            return code, [c for c in cand if c != code][:2], "kept", ""
        passes = code in ranked and (ranked.index(code) / max(len(ranked) - 1, 1)) <= 0.6
        strikes = 0 if passes else incumbent.get("strikes", 0) + 1
        incumbent["strikes"] = strikes
        if strikes < 2:
            fails = [x[0] for x in fund_checks(u, slot, code, {**ctx, "subs": subs}) if not x[1]]
            note = "" if passes else ("On watch (" + (", ".join(fails[:2]) if fails else "slipped in its category ranking") +
                                      ") — replaced only if it fails next month's review too")
            return code, [c for c in cand if c != code][:2], "kept" if passes else "watch", note
        new = next((c for c in cand if c != code), None)
        return new, [c for c in cand if c not in (code, new)][:2], "replaced", "Previous fund replaced after two monthly reviews"
    new = cand[0] if cand else None
    return new, cand[1:3], "new", ""


def apply_tilt(weights, tilt, hz):
    w = dict(weights)
    if hz in ("h1", "h3") or not tilt:
        return w, 0
    eq_take = ["core", "flexi"] if tilt > 0 else ["small", "mid", "flexi", "core"]
    dt_take = ["dcore", "dshort", "metal", "baf", "eqsav", "arb"]
    moved, need = 0, abs(tilt)
    for k in (dt_take if tilt > 0 else eq_take):
        while need > 0 and w.get(k, 0) > 5:
            w[k] -= 5
            need -= 5
            moved += 5
    if moved:
        dst = next((k for k in (eq_take if tilt > 0 else dt_take) if k in w), None)
        if dst:
            w[dst] += moved
        else:
            return dict(weights), 0
    return w, moved if tilt > 0 else -moved


def stable(state, key, new_value, review, strong=False):
    """Change a strategic decision only at a monthly review, and only after it is seen twice in a row (or strongly)."""
    rec = state.setdefault(key, {"value": new_value, "pending": None})
    if review and new_value != rec["value"]:
        if strong or rec.get("pending") == new_value:
            rec["value"], rec["pending"] = new_value, None
        else:
            rec["pending"] = new_value
    elif review:
        rec["pending"] = None
    return rec["value"]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    scr = load(MF / "screener.json")
    if not scr:
        log.error("screener.json missing")
        return 1
    today = date.fromisoformat(scr["asOf"])
    u = Universe(scr, today)
    macro = load(MF / "macro.json", {}) or {}
    sentiment = load(ROOT / "data" / "market_sentiment.json", {})
    state = load(STATE, {}) or {}
    if state.get("v") != VERSION:
        state = {"v": VERSION, "plans": {}, "decisions": {}}
    month = scr["asOf"][:7]
    review = state.get("reviewed") != month
    dec = state.setdefault("decisions", {})

    rr = rate_regime(macro, u)
    regime = stable(dec, "regime", rr["regime"], review, strong=abs(rr["score"]) >= 2.5)
    tilt_now, tilt_comps = market_tilt(u, macro, sentiment)
    tilt = stable(dec, "tilt", tilt_now, review, strong=True)
    sectors = sector_table(u, macro)
    metal = metal_signal(u)
    metal_choice = stable(dec, "metal", metal.get("choice", "gold"), review)

    cache = {}
    sector_pick = None                       # most attractive sector with at least one fund passing every check
    for row in sectors:
        ranked, *_ = rank_pool(u, "theme", {"sector": row["key"], "pool_key": None, "metal": None, "regime": regime,
                                            "sector_label": row["label"]}, cache)
        row["eligible"] = len(ranked)
        if ranked and sector_pick is None and not row["excluded"]:
            sector_pick = row["key"]
    if sector_pick is None and sectors:
        sector_pick = sectors[0]["key"]
    sector = stable(dec, "sector", sector_pick, review)
    if sector and not any(r["key"] == sector and not r["excluded"] and r.get("eligible") for r in sectors):
        sector = sector_pick                 # held sector turned expensive or lost its funds → follow today's pick
        dec["sector"] = {"value": sector, "pending": None}
    sector_row = next((r for r in sectors if r["key"] == sector), {})

    plans = {}
    for hz, hz_label, yrs, ymin, ymax in HORIZONS:
        for rk, rk_label in RISKS:
            pid = hz + rk
            base = TEMPLATES[pid]
            weights, applied = apply_tilt(base, tilt, hz)
            pst = state["plans"].setdefault(pid, {"slots": {}})
            chosen, amc_count, slots, changes, skipped = {}, {}, [], [], []
            for slot in sorted(weights, key=ORDER.index):
                pool_key = None
                if slot in DEBT_POOLS:
                    pool_key = "easing_long" if (slot == "dcore" and regime == "easing" and hz in ("h5", "h7", "h10")) else regime
                m = metal_choice if (rk == "a" and hz in ("h7", "h10")) else "gold"
                ctx = {"pool_key": pool_key, "metal": m if slot == "metal" else None, "sector": sector if slot == "theme" else None,
                       "regime": regime, "sector_index": sector_row.get("index"), "sector_label": sector_row.get("label")}
                ctx["ctx_tag"] = f"{pool_key}|{ctx['metal']}|{ctx['sector']}"
                inc = pst["slots"].get(slot)
                code, alts, action, note = choose(u, slot, ctx, chosen, amc_count, inc, review, cache)
                if code is None:
                    log.warning("%s/%s: no eligible fund — weight moves to a related slot", pid, slot)
                    skipped.append(slot)
                    continue
                if action in ("new", "replaced") or not inc or inc.get("code") != code:
                    prev_code = inc.get("code") if inc else None
                    pst["slots"][slot] = {"code": code, "since": today.isoformat(), "strikes": 0, "ctx": ctx["ctx_tag"]}
                    if prev_code and prev_code != code:
                        changes.append({"slot": slot, "from": prev_code, "to": code, "date": today.isoformat(), "note": note})
                else:
                    pst["slots"][slot]["ctx"] = ctx["ctx_tag"]
                chosen[code] = slot
                amc_count[u.g(code, "amc")] = amc_count.get(u.g(code, "amc"), 0) + 1
                ranked, sc, checks, subs = rank_pool(u, slot, ctx, cache)
                lab = DEBT_LABEL.get((slot, pool_key)) or (f"Sector satellite — {sector_row.get('label', '')}" if slot == "theme" else
                                                             (f"Precious metals — {ctx['metal']}" if slot == "metal" else SLOTS[slot][0]))
                ck = checks.get(code) or fund_checks(u, slot, code, {**ctx, "subs": subs})
                slots.append({
                    "key": slot, "label": lab, "asset": SLOTS[slot][1], "w": weights[slot], "base": base[slot],
                    "code": code, "score": sc.get(code), "alts": alts, "since": pst["slots"][slot]["since"],
                    "state": "watch" if action == "watch" else "ok", "note": note, "why": why(u, slot, code),
                    "checks": ck, "pool": len(ranked), "er": expected_return(u, slot, code, ctx, macro),
                    "vol": SLOTS[slot][6] if slot != "metal" else (25 if ctx["metal"] == "silver" else 14),
                    "tax": u.g(code, "tax") or ("equity" if SLOTS[slot][1] == "Equity" else "other"),
                })
            for sk in skipped:
                tgt = next((x for x in FALLBACK.get(sk, []) if any(z["key"] == x for z in slots)), None)
                tgt = next(z for z in slots if z["key"] == tgt) if tgt else max(slots, key=lambda z: z["w"])
                tgt["w"] += weights[sk]
                tgt["note"] = (tgt["note"] + " " if tgt["note"] else "") + f"Includes the {SLOTS[sk][0].lower()} allocation (no fund currently passes every check)."
            for k in list(pst["slots"]):
                if k not in weights or k in skipped:
                    pst["slots"].pop(k)
            pst["changes"] = (changes + pst.get("changes", []))[:6]
            codes = [s["code"] for s in slots]
            eq = [c for c in codes if chosen.get(c) in ("core", "flexi", "mid", "small", "theme")]
            ovs = [o for o in (u.overlap(a, b) for i, a in enumerate(eq) for b in eq[i + 1:]) if o is not None]
            mix = {}
            for s in slots:
                mix[s["asset"]] = mix.get(s["asset"], 0) + s["w"]
            plans[pid] = {
                "horizon": hz_label, "risk": rk_label, "years": yrs, "yearsMin": ymin, "yearsMax": ymax, "tilt": applied,
                "slots": slots, "mix": mix, "ter": round(sum((u.g(s["code"], "ter") or 0) * s["w"] for s in slots) / 100, 2),
                "er": round(sum(s["er"] * s["w"] for s in slots) / 100, 2),
                "maxOverlap": max(ovs) if ovs else None, "amcs": len({u.g(c, "amc") for c in codes}),
                "checks": sum(len(s["checks"]) for s in slots), "changes": pst["changes"],
            }
    if review:
        state["reviewed"] = month
    state["updated"] = today.isoformat()
    val = macro.get("valuation") or {}
    out = {"v": VERSION, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "asOf": scr["asOf"],
           "reviewed": state["reviewed"], "nextReview": date(today.year + (today.month == 12), today.month % 12 + 1, 1).isoformat(),
           "market": {"tilt": tilt, "tiltNow": tilt_now, "components": tilt_comps,
                      "n50": {k: (val.get("n50") or {}).get(k) for k in ("pe", "pb", "dy", "pePct", "pbPct", "peMed", "pbMed", "r12m")},
                      "valuationAsOf": macro.get("valuationAsOf")},
           "rates": {**rr, "applied": regime},
           "sectors": [{k: r.get(k) for k in ("key", "label", "pe", "peMed", "valPct", "r6mRel", "r12mRel", "score", "signal", "excluded", "eligible")}
                       for r in sectors],
           "sector": sector, "metal": {**metal, "applied": metal_choice},
           "assumptions": ASSUMPTIONS,
           "horizons": [{"id": h, "label": l, "years": y, "min": a, "max": b} for h, l, y, a, b in HORIZONS],
           "risks": [{"id": r, "label": l} for r, l in RISKS],
           "plans": plans}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    STATE.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")))
    log.info("Smart SIP v2: regime %s (score %s) · tilt %+d · sector %s · metal %s · review=%s",
             regime, rr["score"], tilt, sector, metal_choice, review)
    for pid, p in plans.items():
        log.info("  %-4s er %.2f%% | %s", pid, p["er"], " | ".join(f"{s['key']}:{s['w']}% {u.g(s['code'], 'name')[:26]}" for s in p["slots"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
