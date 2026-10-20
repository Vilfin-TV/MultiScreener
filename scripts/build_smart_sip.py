#!/usr/bin/env python3
"""Smart SIP planner v2 for the India MF Screener → data/mf/smartsip.json (+ data/mf/smartsip_state.json).

Twenty model plans — 5 investment horizons × 4 risk levels (conservative, balanced, aggressive, very aggressive: equity + debt + metals, Nifty Next 50 core) — each with a fixed set of up to 8 fund slots.
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
  - Sector satellite (7+ year aggressive plans, 5–10%): 54 sectors (every published Nifty sector index) — e.g. banking, IT, healthcare, consumption,
    infrastructure, real estate & housing, manufacturing & defence, auto, energy, PSU, MNC — are scored on cheapness
    (60%) and relative momentum (40%); expensive sectors (above the 85th valuation percentile) and falling knives
    are excluded; the best fund in the most attractive sector is chosen.
  - Precious metals: gold, or silver when silver is historically cheap against gold (gold/silver ratio in the top
    30% of its range) for 7+ year aggressive plans.
* Global macro — the US dollar, US yields and curve, inflation expectations, emerging-market vs US equities, the
  rupee, crude oil, copper vs gold, volatility and metal trends score equities, bonds, gold and silver; the totals
  feed the equity tilt, the rate cycle, the precious-metal weight (±5 points) and the gold-vs-silver choice.
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

import dip_rules
from sim_engine import exit_rule

ROOT = Path(__file__).resolve().parent.parent
MF = ROOT / "data" / "mf"
OUT = MF / "smartsip.json"
STATE = MF / "smartsip_state.json"
VERSION = 4
log = logging.getLogger("smartsip")

HORIZONS = [("h1", "Under 3 years", 2, 1, 3), ("h3", "3–5 years", 4, 3, 5), ("h5", "5–7 years", 6, 5, 7),
            ("h7", "7–10 years", 8, 7, 10), ("h10", "10+ years", 15, 10, 30)]
RISKS = [("c", "Conservative"), ("b", "Balanced"), ("a", "Aggressive"), ("v", "Very aggressive")]

# slot → label, asset, candidate subs (None = decided at run time), kind, min years, min AUM (₹ cr), volatility %
SLOTS = {
    "core":   ("Large-cap core (Nifty 50 index)", "Equity", ["idx_large"], "index", 3, 500, 15),
    "next50": ("Large-cap growth (Nifty Next 50 index)", "Equity", ["idx_large"], "index", 3, 500, 20),
    "lmcore": ("Large & mid cap core", "Equity", ["largemid"], "active", 5, 1000, 17),
    "flexi":  ("Diversified equity (flexi / multi / large & mid / focused)", "Equity", ["flexi", "multi", "largemid", "focused"], "active", 5, 1000, 16),
    "mid":    ("Mid cap", "Equity", ["mid"], "active", 5, 1000, 19),
    "small":  ("Small cap", "Equity", ["small"], "active", 5, 1000, 23),
    "baf":    ("Balanced advantage (dynamic)", "Hybrid", ["baf"], "active", 5, 1000, 9),
    "eqsav":  ("Equity savings", "Hybrid", ["eqsavings"], "hybrid", 5, 300, 5),
    "arb":    ("Arbitrage", "Hybrid", ["arbitrage"], "arb", 3, 1000, 0.7),
    "dshort": ("Short-term debt", "Debt", None, "debt", 3, 1000, 0.8),
    "dcore":  ("Core debt", "Debt", None, "debt", 3, 1000, 2.5),
    "dmed":   ("Medium-term debt", "Debt", None, "debt", 3, 1000, 3.5),
    "metal":  ("Precious metals", "Commodity", None, "passive", 3, 200, 15),
    "value":  ("Value / contrarian", "Equity", ["value", "contra"], "active", 5, 1000, 17),
    "momentum": ("Momentum factor (index)", "Equity", ["idx_factor"], "factor", 3, 300, 21),
    "theme":  ("Sector satellite", "Equity", None, "sector", 5, 300, 22),
    "intl":   ("International satellite", "International", ["us", "global"], "intl", 3, 300, 17),
    "multi":  ("Multi-asset allocation (equity + debt + gold/silver)", "Hybrid", ["multiasset"], "active", 3, 1000, 11),
    "pioneer": ("Innovation & global tech (Nasdaq 100 sleeve)", "Equity", ["sec_innov"], "active", 5, 1000, 18),
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
    "h5a":  {"core": 20, "flexi": 25, "mid": 15, "small": 5, "pioneer": 10, "dcore": 15, "metal": 10},
    "h7c":  {"core": 30, "flexi": 15, "baf": 15, "dcore": 30, "metal": 10},
    "h7b":  {"core": 30, "flexi": 20, "mid": 15, "small": 5, "dcore": 20, "metal": 10},
    "h7a":  {"core": 25, "flexi": 20, "mid": 15, "small": 10, "pioneer": 10, "theme": 5, "dcore": 10, "metal": 5},
    "h10c": {"core": 30, "flexi": 20, "mid": 5, "baf": 10, "dcore": 25, "metal": 10},
    "h10b": {"core": 30, "flexi": 20, "mid": 15, "small": 10, "dcore": 15, "metal": 10},
    "h10a": {"core": 25, "flexi": 20, "mid": 15, "small": 15, "pioneer": 10, "theme": 5, "dcore": 5, "metal": 5},
    # very aggressive: growth-heavy, diversified across market caps, styles (value, momentum), a sector and overseas
    # every very aggressive plan holds equity + debt + precious metals; the core is an active large & mid cap fund (3+ yrs)
    "h1v":  {"core": 15, "baf": 30, "arb": 15, "dshort": 30, "metal": 10},
    "h3v":  {"lmcore": 30, "flexi": 20, "mid": 15, "baf": 10, "dmed": 15, "metal": 10},
    "h5v":  {"lmcore": 15, "flexi": 15, "mid": 20, "small": 10, "value": 10, "pioneer": 10, "dmed": 10, "metal": 10},
    "h7v":  {"lmcore": 10, "flexi": 10, "mid": 20, "small": 15, "value": 10, "pioneer": 10, "theme": 10, "dmed": 5, "metal": 10},
    "h10v": {"lmcore": 20, "flexi": 10, "mid": 25, "small": 20, "pioneer": 10, "theme": 5, "dmed": 5, "metal": 5},
}
ORDER = ["core", "next50", "lmcore", "flexi", "mid", "small", "value", "momentum", "pioneer", "theme", "baf", "multi", "eqsav", "arb", "dcore", "dmed", "dshort", "metal", "intl"]
FALLBACK = {"lmcore": ["flexi", "core"], "next50": ["flexi", "core"], "dmed": ["dcore", "dshort", "metal"], "value": ["flexi", "core"], "momentum": ["mid", "flexi", "core"], "intl": ["flexi", "core"], "theme": ["flexi", "core"], "small": ["mid", "flexi"], "mid": ["flexi", "core"],
            "flexi": ["core"], "core": ["flexi"], "metal": ["dcore", "dshort"], "eqsav": ["arb", "baf"], "baf": ["core", "dcore"],
            "dcore": ["dshort", "baf"], "dshort": ["dcore", "arb"], "arb": ["dshort"], "multi": ["baf", "flexi"], "pioneer": ["value", "momentum", "flexi"]}

# debt pools by rate regime
DEBT_POOLS = {
    "dshort": {"rising": ["money", "floater", "ultrashort"], "neutral": ["money", "lowdur", "ultrashort"],
               "easing": ["money", "lowdur", "ultrashort"]},
    "dcore": {"rising": ["shortdur", "bankpsu", "floater"], "neutral": ["corpbond", "bankpsu", "shortdur"],
              "easing": ["corpbond", "bankpsu", "shortdur"], "easing_long": ["gilt", "dynbond", "gilt10", "corpbond"]},
    "dmed": {"rising": ["corpbond"], "neutral": ["corpbond", "meddur"], "easing": ["meddur", "corpbond", "dynbond"]},
}
DEBT_LABEL = {
    ("dshort", "rising"): "Short-term debt (money market / floating rate)", ("dshort", "neutral"): "Short-term debt (money market / low duration)",
    ("dshort", "easing"): "Short-term debt (money market / low duration)", ("dcore", "rising"): "Core debt (short duration / floating rate)",
    ("dcore", "neutral"): "Core debt (corporate bond / banking & PSU)", ("dcore", "easing"): "Core debt (corporate bond / banking & PSU)",
    ("dcore", "easing_long"): "Core debt (gilt / dynamic bond — duration)",
    ("dmed", "rising"): "Medium-term debt (corporate bond)", ("dmed", "neutral"): "Medium-term debt (corporate bond / medium duration)",
    ("dmed", "easing"): "Medium-term debt (medium duration / corporate bond)",
}
# worst acceptable 3-year drawdown per debt category (a deeper fall means a credit or liquidity event)
DEBT_TER_CAP = {"dshort": 0.45, "dcore": 0.50, "dmed": 0.60}   # direct-plan expense-ratio ceilings for debt slots
DURATION_SUBS = {"gilt", "gilt10", "dynbond", "meddur", "medlong", "longdur"}   # rate-sensitive debt: more red 1-year periods are normal
DEBT_MDD = {"overnight": -0.3, "liquid": -0.5, "money": -0.5, "ultrashort": -0.75, "lowdur": -1.0, "floater": -1.5,
            "shortdur": -2.0, "bankpsu": -2.0, "corpbond": -2.5, "meddur": -3.0, "gilt": -6.0, "gilt10": -7.0, "dynbond": -6.0}

# sector satellite: key → label, index keys (valuation), fund subs, name filter (include / exclude)
THEME_SUBS = ["sec_bank", "sec_pharma", "sec_tech", "sec_consumption", "sec_infra", "sec_mfg", "sec_energy", "sec_psu", "sec_mnc",
              "sec_cycle", "sec_innov", "sec_other", "idx_bank", "idx_finsvc", "idx_capmkt", "idx_tech", "idx_digital",
              "idx_health", "idx_consumption", "idx_tourism", "idx_mfg", "idx_auto", "idx_defence", "idx_infra", "idx_housing",
              "idx_realty", "idx_energy", "idx_commod", "idx_psu", "idx_leaders", "idx_theme"]
# sector satellite: key → label, index keys (valuation, first available wins), fund subs, name filter (include / exclude)
SECTORS = [
    # banking & finance
    ("bank", "Banking & financial services", ["fin", "bank"], ["sec_bank", "idx_bank", "idx_finsvc"], None,
     r"capital market|ex[- ]?bank|non[- ]?bank|private bank|psu bank|mid ?small|nbfc|insurance|housing finance|small finance|microfinance"),
    ("pvtbank", "Private banks", ["pvtbank"], THEME_SUBS, r"private bank", None),
    ("psubank", "PSU banks", ["psubank"], THEME_SUBS, r"psu bank", None),
    ("finexbank", "Financial services ex-bank", ["finexbank"], THEME_SUBS, r"ex[- ]?bank|non[- ]?bank", None),
    ("msfin", "MidSmall financial services", ["msfin"], THEME_SUBS, r"mid ?small.*financ", None),
    ("capmkt", "Capital markets", ["capmkt"], THEME_SUBS, r"capital market", None),
    ("nbfc", "NBFCs", ["nbfc"], THEME_SUBS, r"\bnbfc", None),
    ("hfc", "Housing finance", ["hfc"], THEME_SUBS, r"housing finance", None),
    ("insurance", "Insurance", ["insurance"], THEME_SUBS, r"insurance", None),
    ("sfb", "Small finance banks & MFIs", ["sfb"], THEME_SUBS, r"small finance|microfinance", None),
    # IT, telecom & digital
    ("it", "IT & technology", ["it"], ["sec_tech", "idx_tech"], None, r"mid ?small|telecom|digital|internet"),
    ("msit", "MidSmall IT & telecom", ["msit"], THEME_SUBS, r"mid ?small.*(it|tele)|it ?(&|and) ?telecom", None),
    ("telecom", "Telecommunications", ["telecom"], THEME_SUBS, r"telecom", r"it ?(&|and) ?telecom|mid ?small"),
    ("digital", "Digital & internet", ["digital", "internet"], THEME_SUBS, r"digital|internet", None),
    # healthcare
    ("health", "Healthcare & pharma", ["health", "pharma"], ["sec_pharma", "idx_health"], None, r"mid ?small|hospital"),
    ("mshealth", "MidSmall healthcare", ["mshealth"], THEME_SUBS, r"mid ?small.*health", None),
    ("hospitals", "Hospitals", ["hospitals"], THEME_SUBS, r"hospital", None),
    # consumption & retail
    ("fmcg", "FMCG", ["fmcg"], THEME_SUBS, r"\bfmcg\b", None),
    ("consumption", "Consumption", ["consumption"], ["sec_consumption", "idx_consumption"], None,
     r"\bfmcg\b|mid ?small|new age|non[- ]?cyclical|durable|rural|tourism|retail|consumer services"),
    ("mscons", "MidSmall consumption", ["mscons"], THEME_SUBS, r"mid ?small.*consumption", None),
    ("newcons", "New-age consumption", ["newcons"], THEME_SUBS, r"new age consumption", None),
    ("noncyc", "Non-cyclical consumer", ["noncyc"], THEME_SUBS, r"non[- ]?cyclical", None),
    ("durables", "Consumer durables", ["durables"], THEME_SUBS, r"durable", None),
    ("conssvc", "Consumer services", ["conssvc"], THEME_SUBS, r"consumer services", None),
    ("retail", "Retail", ["retail"], THEME_SUBS, r"\bretail", None),
    ("tourism", "Tourism & hospitality", ["tourism"], THEME_SUBS, r"tourism|hospitality|travel", None),
    ("rural", "Rural", ["rural"], THEME_SUBS, r"\brural", None),
    ("media", "Media & entertainment", ["media"], THEME_SUBS, r"\bmedia\b|entertainment", None),
    # industrials, infrastructure & real estate
    ("infra", "Infrastructure", ["infra"], ["sec_infra", "idx_infra"], None,
     r"housing|realty|real estate|reit|invit|transport|logistic|construction|cement|power|railway"),
    ("infralog", "Infrastructure & logistics", ["infralog"], THEME_SUBS, r"infrastructure ?(&|and) ?logistic", None),
    ("construction", "Construction", ["construction"], THEME_SUBS, r"\bconstruction", None),
    ("capgoods", "Capital goods", ["capgoods"], THEME_SUBS, r"capital goods", None),
    ("realty", "Real estate & housing", ["realty", "reitrealty", "housing"], THEME_SUBS, r"housing|realty|real estate", r"housing finance|\breits?\b|invit"),
    ("reits", "REITs & InvITs", ["reits"], THEME_SUBS, r"\breits?\b|invit", r"realty"),
    ("transport", "Transport & logistics", ["transport"], THEME_SUBS, r"transport|logistic", r"infrastructure ?(&|and) ?logistic"),
    ("commsvc", "Commercial & transport services", ["commsvc"], THEME_SUBS, r"commercial ?(&|and) ?transport", None),
    ("services", "Services sector", ["services"], THEME_SUBS, r"services sector", None),
    ("railpsu", "Railways PSU", ["railpsu"], THEME_SUBS, r"railway", None),
    ("mfg", "Manufacturing", ["mfg"], ["sec_mfg", "idx_mfg"], None, r"\bauto|mobility|transport|defen[cs]e|\bev\b|capital goods"),
    ("defence", "Defence", ["defence"], THEME_SUBS, r"defen[cs]e", None),
    ("auto", "Auto", ["auto"], THEME_SUBS, r"\bauto|automotive", r"transport|logistic|\bev\b|new age automotive"),
    ("ev", "EV & new-age mobility", ["ev", "mobility"], THEME_SUBS, r"\bev\b|electric vehicle|new age automotive|mobility", None),
    # energy, utilities & materials
    ("energy", "Energy", ["energy"], ["sec_energy"], None, r"oil|gas\b|commodit|power"),
    ("oilgas", "Oil & gas", ["oilgas"], THEME_SUBS, r"\boil\b|\bgas\b", None),
    ("power", "Power", ["power"], THEME_SUBS, r"\bpower\b", None),
    ("commodities", "Commodities", ["commodities"], THEME_SUBS, r"commodit", None),
    ("metal", "Metal & mining", ["metal"], THEME_SUBS, r"\bmetal|mining", None),
    ("chemicals", "Chemicals", ["chemicals"], THEME_SUBS, r"chemical", None),
    ("cement", "Cement", ["cement"], THEME_SUBS, r"cement", None),
    ("sugar", "Sugar & ethanol", ["sugar"], THEME_SUBS, r"sugar|ethanol", None),
    ("textile", "Textiles", ["textile"], THEME_SUBS, r"textile", None),
    # ownership & diversified
    ("psu", "PSU", ["cpse", "pse"], ["sec_psu"], None, r"railway|psu bank"),
    ("mnc", "MNC", ["mnc"], ["sec_mnc"], None, r"conglomerate"),
    ("conglo", "Conglomerates", ["conglo"], THEME_SUBS, r"conglomerate", None),
]
# international-slot backup: Indian funds with an overseas sleeve, used only while no pure international fund is
# open and passes every check (overseas funds pause purchases whenever the industry overseas limit is reached).
# Evidence = a published portfolio with ≥10 % overseas, or a known overseas (Nasdaq 100) sleeve listed here.
RX_INTL_BACKUP = re.compile(r"(?!x)x")        # names only by published portfolio (≥10 % overseas); none listed by name
# innovation & global-tech sleeve (aggressive / very aggressive 5+ yrs): Kotak Pioneer holds a Nasdaq 100 sleeve
RX_PIONEER = re.compile(r"\bkotak pioneer\b", re.I)
INTL_BACKUP_MIN_OVERSEAS = 10.0
RX_MOMENTUM = re.compile(r"momentum", re.I)
RX_NEXT50 = re.compile(r"\bnext 50\b", re.I)
RX_NIFTY50 = re.compile(r"\bnifty 50\b(?!\s*(equal|value|quality|low|momentum|alpha|shariah|arbitrage))", re.I)
RX_NOT_CORE = re.compile(r"elss|tax saver|next 50|equal weight|value|quality|momentum|low vol|alpha", re.I)
RX_INTL_THEME = re.compile(r"mining|clean energy|energy|innovation|technology|tech\b|agri|real estate|reit|ev\b|electric|"
                           r"healthcare|consumer|commodit|fang|nasdaq|china|brazil|japan|taiwan|asean|emerging|india", re.I)
SAFE_CREDIT = ("AAA", "Sovereign", "A1+", "Cash")
EQUITY_BASE = {"core": 11.0, "next50": 12.0, "lmcore": 12.0, "flexi": 12.0, "mid": 13.0, "small": 13.5, "value": 12.5, "momentum": 13.0, "theme": 12.5, "intl": 10.0, "pioneer": 12.5}
EQUITY_VAL_KEY = {"pioneer": "n500", "core": "n50", "next50": "nn50", "flexi": "n500", "mid": "mid150", "small": "sml250", "value": "n500", "momentum": "n500"}
ASSUMPTIONS = {"inflation": 5.0, "cess": 4.0, "stcgEquity": 20.0, "ltcgEquity": 12.5, "ltcgExempt": 125000, "ltcgOther": 12.5,
               "equityLtMonths": 12, "otherLtMonths": 24, "metalReturn": 9.0}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


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

    def detail(self, code):
        sub = self.g(code, "sub")
        if sub and sub not in self.det:
            self.det[sub] = load(MF / "d" / f"{sub}.json", {}) or {}
        return (self.det.get(sub) or {}).get(str(code)) or {}

    def deep(self, code):
        """Flat dict of the deeper analytics used by the equity / hybrid checklist."""
        d = self.detail(code)
        rk, ro = d.get("risk") or {}, d.get("roll") or {}
        r3, r5 = ro.get("3") or {}, ro.get("5") or {}
        return {"roll3avg": r3.get("avg"), "downCap": rk.get("downCap"), "upCap": rk.get("upCap"), "alpha": rk.get("alpha"), "ir": rk.get("ir"),
                "r2": rk.get("r2"), "sharpe": rk.get("sharpe"), "sortino": rk.get("sortino"), "std": rk.get("std"),
                "min3": r3.get("min"), "beat5": r5.get("beat"), "n5": r5.get("n"), "cal": d.get("cal") or {},
                "turnover": _num((d.get("info") or {}).get("turnover"))}

    def deep_rank(self, subs, key, code, higher=True):
        """Percentile (0 = worst, 1 = best) of a deep metric within the category."""
        cache = self.cat_med.setdefault(("deep", tuple(sorted(subs)), key), {})
        if not cache:
            for c in self.by_subs(subs):
                v = self.deep(c).get(key)
                if v is not None:
                    cache[c] = v
        v = cache.get(code)
        if v is None or len(cache) < 4:
            return None
        vals = sorted(cache.values())
        below = sum(1 for x in vals if x < v)
        p = below / (len(vals) - 1) if len(vals) > 1 else 0.5
        return p if higher else 1 - p

    def cal_vs_category(self, subs, code):
        """(years beating the category average, years compared) over the last five calendar years."""
        key = ("calavg", tuple(sorted(subs)))
        if key not in self.cat_med:
            acc = {}
            for c in self.by_subs(subs):
                for y, v in (self.deep(c)["cal"] or {}).items():
                    if v is not None:
                        acc.setdefault(y, []).append(v)
            self.cat_med[key] = {y: sum(v) / len(v) for y, v in acc.items() if len(v) >= 4}
        avg = self.cat_med[key]
        cal = self.deep(code)["cal"]
        yrs = sorted(y for y in cal if y in avg and cal[y] is not None)[-5:]
        return sum(1 for y in yrs if cal[y] >= avg[y]), len(yrs)

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
            self.cat_med[key] = {c: median([self.g(x, c) for x in codes]) for c in ("ter", "roll3", "mdd", "std", "r3y", "r1y", "cons", "sharpe")}
        return self.cat_med[key]


# ───────────────────────────── market conditions ─────────────────────────────
def global_signals(macro):
    """Global cross-asset checks → points for equities (E), debt duration (D), gold (G) and silver (S).
    Each check is +1 / −1 / 0 for the assets it affects; the totals steer the equity tilt, the rate cycle,
    the precious-metal weight and the gold-vs-silver choice."""
    g = (macro or {}).get("global") or {}
    sig, tot = [], {"E": 0, "D": 0, "G": 0, "S": 0}

    def x(k, f):
        return (g.get(k) or {}).get(f)

    def add(key, label, reading, fav, note=""):
        for a, p in fav.items():
            tot[a] += p
        sig.append({"key": key, "k": label, "v": reading, "fav": fav, "note": note})

    v200, c6 = x("dxy", "vs200"), x("dxy", "c6m")
    if v200 is not None and c6 is not None:
        strong, weak = v200 > 1 and c6 > 2, v200 < -1 and c6 < -2
        add("dxy", "US dollar trend", f"{x('dxy', 'last'):.1f} · {c6:+.1f}% in 6M · {v200:+.1f}% vs 200-day",
            {"E": -1, "G": -1} if strong else ({"E": 1, "G": 1} if weak else {}),
            "Strong dollar pulls money out of emerging markets and weighs on gold" if strong else
            ("Weak dollar supports emerging-market equities and gold" if weak else "Dollar range-bound"))
    c3 = x("us10y", "c3m")
    if c3 is not None:
        up, dn = c3 >= 0.4, c3 <= -0.4
        add("us10y", "US 10-year yield", f"{x('us10y', 'last'):.2f}% · {c3:+.2f} pt in 3M",
            {"E": -1, "D": -1, "G": -1} if up else ({"E": 1, "D": 1, "G": 1} if dn else {}),
            "Rising global yields hurt bonds, gold and equity valuations" if up else
            ("Falling global yields support bonds, gold and equities" if dn else "Global yields steady"))
    if x("us10y", "last") is not None and x("us3m", "last") is not None:
        cv = x("us10y", "last") - x("us3m", "last")
        add("curve", "US yield curve (10Y − 3M)", f"{cv:+.2f} pt", {"G": 1} if cv < -0.25 else {},
            "Inverted curve — recession risk favours gold as a hedge" if cv < -0.25 else "Curve not inverted")
    if x("tip", "c6m") is not None and x("ief", "c6m") is not None:
        be = x("tip", "c6m") - x("ief", "c6m")
        up, dn = be > 1.0, be < -1.0
        add("infl", "US inflation expectations", f"inflation-linked vs regular Treasuries {be:+.2f} pt in 6M",
            {"G": 1, "S": 1, "D": -1} if up else ({"D": 1} if dn else {}),
            "Inflation expectations rising — favours real assets over bonds" if up else
            ("Inflation expectations easing — supports bonds" if dn else "Inflation expectations stable"))
    if x("em", "c6m") is not None and x("spx", "c6m") is not None:
        rel = x("em", "c6m") - x("spx", "c6m")
        add("em", "Emerging markets vs US", f"{rel:+.1f} pt in 6M", {"E": 1} if rel > 5 else ({"E": -1} if rel < -5 else {}),
            "Money rotating into emerging markets" if rel > 5 else ("Emerging markets lagging the US" if rel < -5 else "No clear rotation"))
    if x("nifty", "c6m") is not None and x("em", "c6m") is not None:
        rel = x("nifty", "c6m") - x("em", "c6m")
        add("india", "India vs emerging markets", f"{rel:+.1f} pt in 6M", {},
            "India ahead of its peers" if rel > 5 else ("India behind its peers — catch-up potential if flows return" if rel < -5 else "In line with peers"))
    c6 = x("usdinr", "c6m")
    if c6 is not None:
        weak, strong = c6 > 3, c6 < -2
        add("inr", "Rupee vs US dollar", f"₹{x('usdinr', 'last'):.2f} · {c6:+.1f}% in 6M",
            {"E": -1, "G": 1} if weak else ({"E": 1} if strong else {}),
            "Weak rupee lifts gold in rupee terms and can drive foreign selling" if weak else
            ("Firm rupee attracts foreign inflows" if strong else "Rupee stable"))
    c6, p2 = x("brent", "c6m"), x("brent", "pct2y")
    if c6 is not None:
        hot, cool = c6 > 20 or (p2 or 0) > 0.85, c6 < -20
        rupee_oil = c6 + (x("usdinr", "c6m") or 0)
        add("oil", "Crude oil (imported inflation)", f"Brent ${x('brent', 'last'):.0f} · {c6:+.1f}% in 6M · {rupee_oil:+.1f}% in rupees",
            {"E": -1, "D": -1} if hot else ({"E": 1, "D": 1} if cool else {}),
            "Costly oil raises India's inflation and import bill" if hot else ("Cheaper oil eases inflation and helps margins" if cool else "Oil not a pressure point"))
    if x("copper", "c6m") is not None and x("gold", "c6m") is not None:
        r = x("copper", "c6m") - x("gold", "c6m")
        add("cu", "Copper vs gold (growth vs fear)", f"{r:+.1f} pt in 6M",
            {"E": 1, "S": 1} if r > 10 else ({"G": 1, "S": -1} if r < -10 else {}),
            "Industrial demand strong — growth assets and silver favoured" if r > 10 else
            ("Defensive demand dominates — gold favoured over silver" if r < -10 else "Balanced"))
    vx = x("vix", "last")
    if vx is not None:
        add("vix", "Global volatility (VIX)", f"{vx:.1f}", {"G": 1} if vx > 28 else {},
            "Stress in global markets — gold as a hedge" if vx > 28 else ("Calm, possibly complacent" if vx < 13 else "Normal"))
    gv, gc = x("gold", "vs200"), x("gold", "c6m")
    if gv is not None:
        stretched, down = gv > 20, (gc or 0) < -10
        add("goldtrend", "Gold trend", f"${x('gold', 'last'):,.0f} · {gv:+.1f}% vs 200-day · {gc:+.1f}% in 6M",
            {"G": -1} if stretched or down else {},
            "Gold stretched far above its trend — buy less this month" if stretched else ("Gold in a downtrend" if down else "Healthy trend"))
    sv = x("silver", "vs200")
    if sv is not None:
        add("silvertrend", "Silver trend", f"${x('silver', 'last'):,.2f} · {sv:+.1f}% vs 200-day", {"S": -1} if sv > 25 else {},
            "Silver stretched above its trend" if sv > 25 else "Normal")
    asof = max((v.get("d") for v in g.values() if v.get("d")), default=None)
    return {"signals": sig, "score": tot, "asOf": asof}


def apply_metal_tilt(weights, gscore, hz):
    """Gold/silver weight ±5 from the global score (≥+2 adds, ≤−2 trims; metals stay 5–15%)."""
    w = dict(weights)
    if "metal" not in w or hz == "h1" or abs(gscore) < 2:
        return w, 0
    if gscore >= 2 and w["metal"] + 5 <= 15:
        src = next((k for k in ("dcore", "dmed", "dshort", "baf", "arb", "eqsav", "flexi", "core", "lmcore") if w.get(k, 0) > 5), None)
        if src:
            w[src] -= 5
            w["metal"] += 5
            return w, 5
    if gscore <= -2 and w["metal"] > 5:
        dst = next((k for k in ("dcore", "dmed", "dshort", "baf", "flexi", "core", "lmcore") if k in w), None)
        if dst:
            w["metal"] -= 5
            w[dst] += 5
            return w, -5
    return w, 0


EARLY_BEAT3, EARLY_CONS = 80, 80     # very aggressive: 3-year exception for an exceptional early record
TURNOVER_MAX, TURNOVER_MAX_GROWTH = 150, 300
MULTI_MIN = 10        # a multi-asset fund holds ≥10 % each in equity, debt and gold/silver (SEBI) — keep it meaningful


def apply_multi_asset(weights, rk, hz, regime, dscore, gscore):
    """Very aggressive plans (3+ yrs): when bonds are unattractive (rising rate cycle or bond score ≤ −2) the separate
    debt slot is dropped, and when gold is unattractive (gold score ≤ −2) the separate precious-metal slot is dropped;
    their weight goes to a multi-asset allocation fund (≥10 %, topped up from the diversified-equity slot), which still
    holds debt and gold/silver and lets its manager shift between them. Returns (weights, dropped slots)."""
    w = dict(weights)
    if rk != "v" or hz == "h1":
        return w, []
    drop = []
    debt = next((k for k in ("dmed", "dcore", "dshort") if w.get(k)), None)
    if debt and (regime == "rising" or dscore <= -2):
        drop.append(debt)
    if w.get("metal") and gscore <= -2:
        drop.append("metal")
    if not drop:
        return w, []
    moved = sum(w.pop(k) for k in drop)
    if moved < MULTI_MIN:
        for src in ("flexi", "lmcore", "mid"):
            take = min(MULTI_MIN - moved, max(0, w.get(src, 0) - 5))
            if take > 0:
                w[src] -= take
                moved += take
            if moved >= MULTI_MIN:
                break
    w["multi"] = w.get("multi", 0) + moved
    return w, drop


def rate_regime(macro, u, glob=None):
    """Rising / neutral / easing from the policy rate, the 10-year yield, the curve and gilt vs liquid performance."""
    r = (macro or {}).get("rates") or {}
    sig, score = [], 0.0

    def add(label, reading, pts):
        nonlocal score
        score += pts
        sig.append({"k": label, "v": reading, "p": pts})
    repo, g10 = r.get("repo") or {}, r.get("g10") or {}
    if repo.get("last") is not None:
        prev = repo.get("summaryLast")                 # value before the latest policy decision, if it changed since
        if prev is not None and abs(repo["last"] - prev) > 1e-9:
            d = repo["last"] - prev
            add("Policy repo rate, latest decision", f"{'raised' if d > 0 else 'cut'} to {repo['last']:.2f}% from {prev:.2f}%",
                -1 if d > 0 else 1)
        if repo.get("yearAgo") is not None:
            d = repo["last"] - repo["yearAgo"]
            add("Policy repo rate vs a year ago", f"{repo['yearAgo']:.2f}% → {repo['last']:.2f}%" + ("" if d else " (unchanged)"),
                1 if d < -1e-9 else (-1 if d > 1e-9 else 0))
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
    if glob and glob.get("signals"):
        d = glob["score"]["D"]
        add("Global bonds, oil & inflation expectations", f"{d:+d} from global checks", 0.5 if d >= 2 else (-0.5 if d <= -2 else 0))
    regime = "easing" if score >= 1.5 else ("rising" if score <= -1.5 else "neutral")
    return {"regime": regime, "score": round(score, 2), "signals": sig,
            "repo": repo.get("last"), "g10": g10.get("last"), "g10YearAgo": g10.get("yearAgo"),
            "tb91": (r.get("tb91") or {}).get("last"), "tb364": (r.get("tb364") or {}).get("last"),
            "call": (r.get("call") or {}).get("last")}


def market_tilt(u, macro, sentiment, glob=None):
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
    if glob and glob.get("signals"):
        e = glob["score"]["E"]
        add("Global macro (dollar, yields, EM flows, rupee, oil)", f"{e:+d} from global checks", 5 if e >= 2 else (-5 if e <= -2 else 0))
    gr = (macro or {}).get("growth") or {}
    if gr.get("checks"):
        sc, n = gr.get("score", 0), len(gr["checks"])
        thr = max(3, round(n * 0.4))               # 40% of the checks agree (3 of 7, 4 of 10): adding checks keeps the sensitivity
        add("India growth & earnings (GDP, inflation, earnings, profitability)", f"{sc:+d} from {n} checks (±{thr} moves equity)",
            5 if sc >= thr else (-5 if sc <= -thr else 0))
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
                     "r6mRel": v.get("r6mRel"), "r12mRel": v.get("r12mRel"), "r6m": v.get("r6m"), "years": v.get("years")})
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


# how each sector reacts to the macro backdrop (used for the medium-term outlook)
SENS_RATES = {"bank", "pvtbank", "psubank", "finexbank", "msfin", "nbfc", "hfc", "sfb", "realty", "reits", "auto", "ev",
              "durables", "construction", "capgoods", "infra"}
SENS_OIL_USER = {"auto", "ev", "chemicals", "transport", "commsvc", "cement", "tourism", "durables", "fmcg", "conssvc"}
SENS_OIL_PROD = {"oilgas"}
SENS_EXPORT = {"it", "msit", "health", "mshealth", "textile", "chemicals", "digital"}
SENS_COMMOD = {"metal", "commodities", "cement", "power", "energy"}
SENS_FLOWS = {"bank", "pvtbank", "capmkt", "finexbank", "msfin"}


def sector_outlook(rows, macro, regime, glob):
    """Short (1–3 months), medium (6–12 months) and long term (3+ years) outlook per sector: positive / neutral /
    negative, with the reasons."""
    val = (macro or {}).get("valuation") or {}
    g = (glob or {}).get("signals") or []
    gs = {x["key"]: x for x in g}
    eflows = ((glob or {}).get("score") or {}).get("E", 0)
    oil_hot = bool(gs.get("oil", {}).get("fav", {}).get("E", 0) < 0)
    oil_cool = bool(gs.get("oil", {}).get("fav", {}).get("E", 0) > 0)
    inr = ((macro or {}).get("global") or {}).get("usdinr", {}).get("c6m")
    cu = gs.get("cu", {}).get("fav", {})

    def lab(x, up, dn):
        return "pos" if x >= up else ("neg" if x <= dn else "neu")
    for r in rows:
        v = val.get(r["index"]) or {}
        # short term — relative momentum and trend
        r3, r1, tr = v.get("r3mRel"), v.get("r1mRel"), v.get("vs6m")
        st_s, st_w = 0.0, []
        if r3 is not None:
            st_s += 1 if r3 > 3 else (-1 if r3 < -3 else 0)
            st_w.append(f"3M vs Nifty {r3:+.1f}%")
        if r1 is not None:
            st_s += 0.5 if r1 > 2 else (-0.5 if r1 < -2 else 0)
            st_w.append(f"1M vs Nifty {r1:+.1f}%")
        if tr is not None:
            st_s += 0.5 if tr > 2 else (-0.5 if tr < -2 else 0)
            st_w.append(f"{tr:+.1f}% vs 6-month average")
        if (r3 or 0) > 15 and (r.get("valPct") or 0) > 0.85:
            st_s = min(st_s, 0.5)
            st_w.append("stretched after a sharp run")
        # medium term — 6/12-month relative momentum, valuation and macro sensitivity
        k, mt_s, mt_w = r["key"], 0.0, []
        r6, r12, vp = r.get("r6mRel"), r.get("r12mRel"), r.get("valPct")
        if r6 is not None:
            mt_s += 1 if r6 > 3 else (-1 if r6 < -3 else 0)
            mt_w.append(f"6M vs Nifty {r6:+.1f}%")
        if r12 is not None:
            mt_s += 0.5 if r12 > 5 else (-0.5 if r12 < -5 else 0)
        if vp is not None:
            mt_s += 0.5 if vp < 0.3 else (-0.5 if vp > 0.8 else 0)
        if k in SENS_RATES and regime in ("rising", "easing"):
            mt_s += 0.5 if regime == "easing" else -0.5
            mt_w.append("easing rates help" if regime == "easing" else "rising rates weigh")
        if k in SENS_OIL_USER and (oil_hot or oil_cool):
            mt_s += -0.5 if oil_hot else 0.5
            mt_w.append("costly oil weighs" if oil_hot else "cheaper oil helps")
        if k in SENS_OIL_PROD and (oil_hot or oil_cool):
            mt_s += 0.5 if oil_hot else -0.5
            mt_w.append("high oil prices help" if oil_hot else "lower oil prices weigh")
        if k in SENS_EXPORT and inr is not None and abs(inr) > 2:
            mt_s += 0.5 if inr > 2 else -0.5
            mt_w.append("weak rupee helps exporters" if inr > 2 else "strong rupee weighs on exporters")
        if k in SENS_COMMOD and cu.get("E"):
            mt_s += 0.5 if cu["E"] > 0 else -0.5
            mt_w.append("strong industrial demand" if cu["E"] > 0 else "weak industrial demand")
        if k in SENS_FLOWS and abs(eflows) >= 2:
            mt_s += 0.5 if eflows > 0 else -0.5
            mt_w.append("global flows supportive" if eflows > 0 else "global flows a headwind")
        # long term — valuation vs its own 10-year history
        if vp is None:
            lt, lt_w = "neu", f"only {r.get('years') or 0:.1f} yrs of history — valuation not yet rankable"
        else:
            lt = "pos" if vp <= 0.35 else ("neg" if vp >= 0.75 else "neu")
            pe, med = r.get("pe"), r.get("peMed")
            lt_w = f"{ordinal(round(vp * 100))} percentile of 10-yr valuation" + (f" · P/E {pe:.1f} vs median {med:.1f}" if pe and med else "")
        r["outlook"] = {"st": lab(st_s, 1, -1), "mt": lab(mt_s, 1, -1), "lt": lt,
                        "why": {"st": " · ".join(st_w) or "no recent data", "mt": " · ".join(mt_w) or "no clear driver", "lt": lt_w}}
    return rows


def sector_funds(u, key):
    s = next(x for x in SECTORS if x[0] == key)
    codes = u.by_subs(s[3])
    if s[4]:
        codes = [c for c in codes if re.search(s[4], u.g(c, "name") or "", re.I)]
    if s[5]:
        codes = [c for c in codes if not re.search(s[5], u.g(c, "name") or "", re.I)]
    return codes


def metal_signal(u, sscore=0):
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
    choice = "silver" if ((pct >= 0.7 and sscore >= -1) or (pct >= 0.55 and sscore >= 2)) and (smom is None or smom > -10) else "gold"
    return {"choice": choice, "ratioPct": round(pct, 3), "silver3m": smom, "gold3m": u.g(g, "r3m"),
            "years": round(len(common) / 52, 1),
            "silverScore": sscore,
            "note": ("Silver is cheap relative to gold" + (" and global growth signals support it" if sscore >= 2 else "")) if choice == "silver" else
                    ("Gold preferred — silver not cheap enough relative to gold" if pct < 0.7 else
                     ("Gold preferred — global signals favour gold over silver" if sscore < -1 else "Gold preferred — silver momentum weak"))}


# ───────────────────────────── per-fund checks ─────────────────────────────
LUMP_MAX = 1000                              # every fund must accept a monthly lump sum of ₹1,000 or less


def buy_ok(u, code):
    """Open for both lump-sum purchases and SIPs (the plan can be invested either way each month)."""
    b = u.g(code, "buy")
    return True if b is None else ("S" in b and "L" in b)


def fund_checks(u, slot, code, ctx):
    """[(label, passed, detail)] — every item must pass for a fund to enter a plan."""
    label, asset, _subs, kind, min_y, min_aum, _vol = SLOTS[slot]
    subs = ctx["subs"]
    growth = ctx.get("profile") == "growth"      # very aggressive plans accept more volatility for more return
    cs = u.category_stats(subs)
    g = lambda c: u.g(code, c)  # noqa: E731
    name, sub = g("name") or "", g("sub") or ""
    is_idx = sub.startswith("idx_")
    out = []

    def chk(lab, ok, det=""):
        out.append([lab, bool(ok), det])
    y = years_since(g("inc"), u.today)
    my = 3 if (kind == "sector" and is_idx) else min_y
    # very aggressive plans accept a younger active fund (3+ years) whose early record is exceptional
    early = (growth and kind in ("active", "sector") and not is_idx and my > 3 and y >= 3
             and (g("beat3") or 0) >= EARLY_BEAT3 and (g("cons") or 0) >= EARLY_CONS)
    chk("Track record", y >= my or early,
        f"{y:.1f} years — strong early record (beat its benchmark in {g('beat3'):.0f}% of rolling 3-year periods, consistency {g('cons'):.0f}/100)"
        if early and y < my else f"{y:.1f} years (needs {my}+)")
    ma = 100 if (kind == "sector" and is_idx) else (500 if sub in ("gilt", "dynbond", "gilt10", "floater") else min_aum)
    chk("Fund size", (g("aum") or 0) >= ma, f"₹{(g('aum') or 0):,.0f} cr (needs ₹{ma:,} cr+)")
    ter, med = g("ter"), cs.get("ter")
    if slot == "momentum":                   # factor funds cost more than plain index funds — compare like with like
        med = median([u.g(c, "ter") for c in u.by_subs(subs) if RX_MOMENTUM.search(u.g(c, "name") or "") and u.g(c, "ter") is not None])
    tol = 0.05 if asset == "Debt" or kind in ("index", "passive", "arb") or is_idx else 0.10
    chk("Expense ratio", ter is not None and (med is None or ter <= med + tol),
        (f"{ter:.2f}% vs category median {med:.2f}%" if ter is not None else "not disclosed") if med is not None else f"{ter}%")
    chk("Open for investment", buy_ok(u, code), "accepts lump-sum purchases and SIPs" if buy_ok(u, code) else "fresh lump sums or SIPs paused")
    lm = g("lumpMin")
    chk("Lump-sum minimum", lm is None or lm <= LUMP_MAX, f"₹{lm:,.0f} per purchase (limit ₹{LUMP_MAX:,})" if lm is not None else "not disclosed")
    chk("No lock-in", not ((g("lock") or 0) > 0 or re.search(r"elss|tax saver", name, re.I)), "redeemable any time")
    chk("Status", g("status") != "Out of track" and not (kind in ("active", "sector", "hybrid") and g("status") == "Underperforming"),
        g("status") or "not rated yet")
    if kind in ("active", "sector") and not is_idx:
        if slot not in ("baf", "eqsav"):
            b3 = g("beat3")
            chk("Beats benchmark (rolling 3Y)", b3 is not None and b3 >= 50, f"{b3:.0f}% of periods" if b3 is not None else "no 3-year record")
        r3 = g("roll3")
        pr = u.deep_rank(subs, "roll3avg", code)
        chk("Rolling 3Y return vs category", r3 is not None and (pr is None or pr >= 0.4),
            f"{r3:.1f}% a year · better than {round(pr * 100)}% of peers" if r3 is not None and pr is not None else (f"{r3:.1f}%" if r3 is not None else "no 3-year record"))
        c = g("cons")
        chk("Consistency", c is None or c >= 40, f"{c:.0f}/100" if c is not None else "not scored")
        md, mm = g("mdd"), cs.get("mdd")
        chk("Drawdown vs category", md is None or mm is None or md >= mm - (10 if growth else 5),
            f"{md:.1f}% vs median {mm:.1f}%" if md is not None and mm is not None else "–")
        newest, longest = u.manager_since(code)
        if longest:
            chk("Fund-manager tenure", (u.today - longest).days >= 365, f"longest-serving manager since {longest:%b %Y}")
        top10 = (u.pf.get(code) or {}).get("top10")
        if top10 and slot in ("flexi", "lmcore", "mid", "small", "value"):
            chk("Portfolio concentration", top10 <= 60, f"top 10 holdings {top10:.0f}%")
    if (kind in ("active", "sector") and not is_idx) or kind == "hybrid":
        deep_checks(u, slot, code, subs, chk, growth)
    if slot == "flexi":
        chk("Market-cap fit", g("size") not in ("Mid", "Small"), f"{g('size') or 'blend'} tilt (mid / small caps have their own slots)")
    if slot == "lmcore":
        chk("Market-cap fit", g("size") not in ("Small",), f"{g('size') or 'blend'} tilt (needs large and mid caps)")
    if slot == "mid":
        chk("Market-cap fit", g("size") not in ("Large",), f"{g('size') or 'blend'} tilt")
    if slot == "small":
        chk("Market-cap fit", g("size") not in ("Large", "Multi"), f"{g('size') or 'blend'} tilt")
        chk("Size manageable for small caps", (g("aum") or 0) <= 40000, f"₹{(g('aum') or 0):,.0f} cr")
    if slot == "value":
        chk("Value style", sub in ("value", "contra") and g("size") not in ("Small",), f"{'contra' if sub == 'contra' else 'value'} fund · {g('size') or 'blend'} tilt")
    if slot == "momentum":
        chk("Momentum factor", bool(RX_MOMENTUM.search(name)), "rules-based momentum index" if RX_MOMENTUM.search(name) else "not a momentum index")
        r3, m3 = g("r3y"), median([u.g(c, "r3y") for c in u.by_subs(["idx_large"]) if RX_NIFTY50.search(u.g(c, "name") or "") and u.g(c, "r3y") is not None])
        chk("3Y return above the Nifty 50", r3 is not None and (m3 is None or r3 > m3), f"{r3:.1f}% vs {m3:.1f}% a year" if r3 is not None and m3 is not None else "no 3-year record")
    if slot == "next50":
        chk("Tracks the Nifty Next 50", bool(RX_NEXT50.search(name)) and not RX_NOT_CORE.search(name.lower().replace("next 50", "")), "plain Nifty Next 50 index fund")
    if slot == "core":
        chk("Tracks the Nifty 50", bool(RX_NIFTY50.search(name)) and not RX_NOT_CORE.search(name), "plain Nifty 50 index fund")
    if kind in ("index", "passive") or is_idx:
        rmed = median([u.g(c, "r3y") for c in index_peers(u, code, sub)] or [u.g(c, "r3y") for c in u.by_subs([sub])]) if sub else None
        td = None if g("r3y") is None or rmed is None else abs(g("r3y") - rmed)
        chk("Tracking vs peers", td is None or td <= (0.6 if kind not in ("sector", "factor") else 1.5), f"3Y return within {td:.2f} pt of peers" if td is not None else "new")
        index_checks(u, slot, code, sub, chk)
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
        own = u.category_stats([sub])                # returns are compared within the fund's own debt category
        r1, m1 = g("r1y"), own.get("r1y")
        chk("1Y return vs category", r1 is None or m1 is None or r1 >= m1 - 0.5,
            f"{r1:.2f}% vs median {m1:.2f}%" if r1 is not None and m1 is not None else "–")
        sh, shm = g("sharpe"), own.get("sharpe")
        chk("Risk-adjusted return vs category", sh is None or shm is None or sh >= shm - max(0.3, abs(shm) * 0.4),
            f"Sharpe {sh:.2f} vs median {shm:.2f}" if sh is not None and shm is not None else "–")
        p1, plim = g("pos1"), (85 if sub in DURATION_SUBS else 95)
        chk("Positive 1-year periods", p1 is None or p1 >= plim,
            f"{p1:.0f}% of rolling 1-year periods positive (needs {plim}%+)" if p1 is not None else "–")
        pf = u.pf.get(code) or {}
        sov = sum(w for k, w in (pf.get("credit") or []) if "sovereign" in k.lower())
        t10 = pf.get("top10All")
        chk("Issuer concentration", t10 is None or sov >= 50 or t10 <= 75,
            (f"top 10 holdings {t10:.0f}%" + (" (mostly government securities)" if sov >= 50 else " (limit 75%)")) if t10 is not None else "portfolio not yet published")
        r3, m3 = g("r3y"), own.get("r3y")
        chk("3Y return vs category", r3 is None or m3 is None or r3 >= m3 - 0.4,
            f"{r3:.2f}% vs median {m3:.2f}% a year (within 0.4 pt)" if r3 is not None and m3 is not None else "–")
        rl, ml = g("roll3"), own.get("roll3")
        chk("Rolling 3Y return vs category", rl is None or ml is None or rl >= ml - 0.4,
            f"{rl:.2f}% vs median {ml:.2f}% a year" if rl is not None and ml is not None else "not enough history")
        cap = DEBT_TER_CAP.get(slot, 0.5)
        chk("Cost cap", ter is None or ter <= cap, f"{ter:.2f}% (limit {cap:.2f}% for this kind of debt fund)" if ter is not None else "not disclosed")
        if slot == "dshort":
            nil = g("exitNil")
            chk("No exit load", sub == "liquid" or nil is not False,
                "liquid fund — only the statutory 7-day exit charge" if sub == "liquid" else ("no exit load — money can be taken out any time" if nil else "exit load not confirmed — check the scheme documents"))
    if kind == "arb":
        r1, m1 = g("r1y"), cs.get("r1y")
        chk("1Y return vs category", r1 is None or m1 is None or r1 >= m1 - 0.3, f"{r1:.2f}% vs median {m1:.2f}%" if r1 is not None and m1 is not None else "–")
    if slot == "intl" and ctx.get("intl_backup"):
        ov = ((u.pf.get(code) or {}).get("mix") or {}).get("overseas")
        chk("International exposure", ov is not None and ov >= INTL_BACKUP_MIN_OVERSEAS or bool(RX_INTL_BACKUP.search(name)),
            (f"{ov:.0f}% held overseas" if ov is not None else "Indian innovation fund with an overseas (Nasdaq 100) sleeve")
            + " — used while international funds are closed to new money")
    if slot == "intl":
        core = re.sub(r"\b(invesco|nippon|franklin|bank of) india\b", "", name, flags=re.I)   # fund-house brands are not mandates
        chk("Diversified mandate", not RX_INTL_THEME.search(core), "broad overseas market" if not RX_INTL_THEME.search(core) else "narrow theme or single region")
    if slot == "metal":
        chk("Metal", re.search(ctx["metal"], name, re.I) is not None, f"{ctx['metal']} fund")
        r1, m1 = g("r1y"), cs.get("r1y")
        chk("1Y return vs same-metal funds", r1 is None or m1 is None or r1 >= m1 - 1.5,
            f"{r1:.1f}% vs median {m1:.1f}%" if r1 is not None and m1 is not None else "–")
        sd, sm = g("std"), cs.get("std")
        chk("Volatility vs same-metal funds", sd is None or sm is None or sd <= sm * 1.15,
            f"{sd:.1f} vs median {sm:.1f}" if sd is not None and sm is not None else "–")
        md, mm = g("mdd"), cs.get("mdd")
        chk("Drawdown vs same-metal funds", md is None or mm is None or md >= mm - 3,
            f"worst fall {md:.1f}% vs median {mm:.1f}%" if md is not None and mm is not None else "–")
        mix = (u.pf.get(code) or {}).get("mix") or {}
        held = (mix.get("fund") or 0) + (mix.get("commodity") or 0) + (mix.get("gold") or 0) + (mix.get("silver") or 0)
        chk("Backed by the metal", not mix or held >= 90,
            f"{held:.0f}% in {ctx['metal']} ETF units / bullion" if mix else "portfolio not yet published (fund of the house's own ETF)")
        r3, m3 = g("r3y"), cs.get("r3y")
        chk("3Y return vs same-metal funds", r3 is None or m3 is None or r3 >= m3 - 0.75,
            f"{r3:.1f}% vs median {m3:.1f}% a year (within 0.75 pt)" if r3 is not None and m3 is not None else "–")
        chk("Cost cap", ter is None or ter <= 0.5, f"{ter:.2f}% (limit 0.50% — a metal fund only needs to track the price)" if ter is not None else "not disclosed")
        sh, shm = g("sharpe"), cs.get("sharpe")
        chk("Risk-adjusted return vs same-metal funds", sh is None or shm is None or sh >= shm - 0.15,
            f"Sharpe {sh:.2f} vs median {shm:.2f}" if sh is not None and shm is not None else "–")
    if slot == "multi":
        mix = (u.pf.get(code) or {}).get("mix") or {}
        if mix:
            eqs = (mix.get("equity") or 0) + (mix.get("overseas") or 0)
            dbt = (mix.get("debt") or 0) + (mix.get("cashOther") or 0)
            com = (mix.get("fund") or 0) + (mix.get("commodity") or 0) + (mix.get("gold") or 0) + (mix.get("silver") or 0)
            chk("Holds all three asset classes", eqs >= 10 and dbt >= 10 and com >= 5,
                f"equity {eqs:.0f}% · debt & cash {dbt:.0f}% · gold / silver & other funds {com:.0f}%")
            chk("Equity share in range", 35 <= eqs <= 80, f"{eqs:.0f}% in shares (range 35–80% — the model assumes about 65%)")
            chk("Gold / silver share", com >= 8, f"{com:.0f}% in gold / silver and other fund units (needs 8%+)")
            cash = mix.get("cashOther") or 0
            chk("Cash not idle", cash <= 15, f"{cash:.0f}% in cash & other (limit 15%)")
        else:
            chk("Holds all three asset classes", True, "portfolio not yet published — multi-asset funds must hold at least 10% in each of three asset classes")
        chk("Cost cap", ter is None or ter <= 1.0, f"{ter:.2f}% (limit 1.00%)" if ter is not None else "not disclosed")
        r3, m3 = g("r3y"), cs.get("r3y")
        chk("3Y return vs category", r3 is None or m3 is None or r3 >= m3 - 1.0,
            f"{r3:.1f}% vs median {m3:.1f}% a year (within 1 pt)" if r3 is not None and m3 is not None else "–")
        md, mm = g("mdd"), cs.get("mdd")
        chk("Smaller falls than equity funds", md is None or md >= -25, f"worst fall {md:.1f}% (limit −25%)" if md is not None else "–")
    if slot == "theme":
        theme_checks(u, code, ctx, chk)
    return out


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def theme_checks(u, code, ctx, chk):
    """Sector satellite: the sector must still be worth owning, and the fund must be a sound way to own it —
    compared with the other funds of the same sector, not with the whole sectoral category."""
    g = lambda c: u.g(code, c)  # noqa: E731
    row = ctx.get("sector_row") or {}
    lab = ctx.get("sector_label") or row.get("label") or "sector"
    vp = row.get("valPct")
    chk("Sector valuation", vp is None or vp < 0.80,
        f"{lab} at the {ordinal(round(vp * 100))} percentile of its 10-year valuation (limit 80th)" if vp is not None else f"{lab} — valuation history too short")
    ol = row.get("outlook") or {}
    why = ol.get("why") or {}
    chk("Medium-term sector outlook", ol.get("mt") != "neg", f"{ {'pos': 'positive', 'neu': 'neutral'}.get(ol.get('mt'), 'negative' if ol.get('mt') else 'not rated')} · {why.get('mt') or '6–12 months'}")
    chk("Long-term sector outlook", ol.get("lt") != "neg", f"{ {'pos': 'positive', 'neu': 'neutral'}.get(ol.get('lt'), 'negative' if ol.get('lt') else 'not rated')} · {why.get('lt') or '3+ years'}")
    rel = row.get("r6mRel")
    chk("Sector momentum (6M vs Nifty 50)", rel is None or rel >= -10, f"{rel:+.1f}% vs the Nifty 50 over 6 months (limit −10%)" if rel is not None else "not enough history")
    # like with like: index funds against the sector's index funds, active funds against its active funds
    idx = (g("sub") or "").startswith("idx_")
    peers = [c for c in sector_funds(u, ctx["sector"]) if c != code and (u.g(c, "sub") or "").startswith("idx_") == idx] if ctx.get("sector") else []

    kind = "sector index-fund" if idx else "sector active-fund"

    def peer_med(col):
        return median([u.g(c, col) for c in peers if u.g(c, col) is not None])
    for col, lab2, tol, fmt in (("r1y", "1Y return vs sector peers", 3.0, "{:.1f}%"), ("r3y", "3Y return vs sector peers", 2.0, "{:.1f}% a year")):
        v, m = g(col), peer_med(col)
        if v is not None and m is not None and len(peers) >= 2:
            chk(lab2, v >= m - tol, f"{fmt.format(v)} vs {kind} median {fmt.format(m)} (within {tol:.0f} pt)")
    v, m = g("mdd"), peer_med("mdd")
    if v is not None and m is not None and len(peers) >= 2:
        chk("Drawdown vs sector peers", v >= m - 5, f"{v:.1f}% vs {kind} median {m:.1f}%")
    v, m = g("std"), peer_med("std")
    if v is not None and m is not None and len(peers) >= 2:
        chk("Volatility vs sector peers", v <= m * 1.2, f"{v:.1f}% vs {kind} median {m:.1f}% a year")
    v, m = g("sharpe"), peer_med("sharpe")
    if v is not None and m is not None and len(peers) >= 2:
        chk("Risk-adjusted return vs sector peers", v >= m - 0.15, f"Sharpe {v:.2f} vs {kind} median {m:.2f}")
    pf = u.pf.get(code) or {}
    eq = (pf.get("mix") or {}).get("equity")
    if eq is not None:
        chk("Fully invested in equity", eq >= 90, f"{eq:.0f}% in equities (needs 90%+)")
    top = pf.get("top") or []
    if top:
        chk("Single-stock concentration", top[0][2] <= 35, f"largest holding {top[0][0]} {top[0][2]:.1f}% (limit 35%)")
    if pf.get("n") is not None:
        chk("Enough holdings", pf["n"] >= 10, f"{pf['n']} stocks (needs 10+)")


def index_key(name: str) -> str:
    """The index a passive fund tracks, from its name ("HDFC Nifty 50 Index Fund" → "nifty 50")."""
    n = re.sub(r"\(.*?\)", " ", (name or "").lower())
    n = re.sub(r"\b(nifty|midcap|smallcap)(\d)", r"\1 \2", n)          # "Nifty200" / "Midcap150" spellings
    m = re.search(r"\b((?:nifty|bse|s&p bse|sensex|crisil|msci|nasdaq|s&p)\b.*?)(?=\s+(?:index|etf|fund|fof|plan)\b|$)", n)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else n.strip()


def index_peers(u, code, sub):
    key = index_key(u.g(code, "name"))
    return [c for c in u.by_subs([sub]) if c != code and index_key(u.g(c, "name")) == key]


def index_checks(u, slot, code, sub, chk):
    """Passive funds: how closely, cheaply and consistently the fund delivers its index."""
    d, peers = u.deep(code), index_peers(u, code, sub)
    rk = (u.detail(code).get("risk") or {})
    if slot == "core":                                   # measured against the Nifty 50 itself
        if rk.get("te") is not None:
            chk("Tracking error (3Y)", rk["te"] <= 0.30, f"{rk['te']:.2f}% a year (limit 0.30%)")
        if rk.get("r2") is not None:
            chk("R² vs the index", rk["r2"] >= 99, f"{rk['r2']:.2f}%")
        if rk.get("beta") is not None:
            chk("Beta vs the index", 0.97 <= rk["beta"] <= 1.03, f"{rk['beta']:.3f}")
        if rk.get("ret") is not None and rk.get("bret") is not None:
            tdiff = rk["ret"] - rk["bret"]
            chk("Tracking difference (3Y)", tdiff >= -0.30, f"{tdiff:+.2f}% a year vs the index")
        if rk.get("upCap") is not None and rk.get("downCap") is not None:
            gap = abs(rk["upCap"] - rk["downCap"])
            chk("Symmetric capture", gap <= 1.0, f"up {rk['upCap']:.1f}% / down {rk['downCap']:.1f}%")
    # year-by-year tracking against the median of funds tracking the same index
    cal = d["cal"] or {}
    if cal and peers:
        yrs = sorted(cal)[-5:]
        devs = []
        for y in yrs:
            pv = [u.deep(c)["cal"].get(y) for c in peers]
            pv = [v for v in pv if v is not None]
            if len(pv) >= 3 and cal[y] is not None:
                devs.append(abs(cal[y] - median(pv)))
        if devs:
            lim = 0.6 if slot == "core" else 1.5
            chk("Consistent tracking every year", max(devs) <= lim, f"largest yearly gap to peers {max(devs):.2f} pt over {len(devs)} years")
    if peers:
        ters = sorted(t for t in [u.g(c, "ter") for c in peers] + [u.g(code, "ter")] if t is not None)
        if len(ters) >= 4 and u.g(code, "ter") is not None:
            rank = sum(1 for t in ters if t < u.g(code, "ter")) / (len(ters) - 1)
            chk("Cost rank among peers", rank <= 0.4, f"cheaper than {round((1 - rank) * 100)}% of funds tracking this index")
        aums = sorted(a for a in [u.g(c, "aum") for c in peers] + [u.g(code, "aum")] if a is not None)
        if len(aums) >= 4 and u.g(code, "aum") is not None:
            rank = sum(1 for a in aums if a < u.g(code, "aum")) / (len(aums) - 1)
            chk("Size rank among peers", rank >= 0.5, f"larger than {round(rank * 100)}% of funds tracking this index")
    load = " ".join(u.info(code).get("exitLoad") or []).lower()
    if load:
        m = re.search(r"(\d+|seven|fifteen|thirty)\s*(day|month|year)", load)
        words = {"seven": 7, "fifteen": 15, "thirty": 30}
        days = None
        if m:
            n = int(m.group(1)) if m.group(1).isdigit() else words[m.group(1)]
            days = n * {"day": 1, "month": 30, "year": 365}[m.group(2)]
        nil = bool(re.search(r"\bnil\b|no load|not applicable", load))
        chk("Exit load", nil or (days is not None and days <= 30), "nil" if nil else (f"only within {days} days" if days else "see scheme documents"))


def deep_checks(u, slot, code, subs, chk, growth=False):
    """Extra quality checks for actively managed equity and hybrid funds (3-year monthly risk, rolling and calendar data)."""
    d = u.deep(code)
    hybrid = slot in ("baf", "eqsav")
    dc, uc = d["downCap"], d["upCap"]
    if dc is not None:
        lim = (80 if slot == "baf" else 60) if hybrid else (115 if growth else 100)
        chk("Downside protection", dc <= lim, f"captured {dc:.0f}% of the benchmark's falls (limit {lim}%)")
    if not hybrid:
        if dc and uc is not None:
            chk("Upside vs downside capture", uc / dc >= 1.0, f"up {uc:.0f}% / down {dc:.0f}%")
        if d["alpha"] is not None:
            chk("Alpha vs benchmark (3Y)", d["alpha"] > 0, f"{d['alpha']:+.2f}% a year")
        if d["ir"] is not None:
            chk("Information ratio (3Y)", d["ir"] > 0, f"{d['ir']:.2f}")
    for key, lab in (("sharpe", "Sharpe ratio"), ("sortino", "Sortino ratio")):
        p = u.deep_rank(subs, key, code)
        if p is not None:
            chk(f"{lab} vs category", p >= 0.35, f"{d[key]:.2f} · better than {round(p * 100)}% of peers")
    p = u.deep_rank(subs, "std", code, higher=False)
    if p is not None and not growth:
        chk("Volatility vs category", p >= 0.2, f"{d['std']:.1f}% a year · calmer than {round(p * 100)}% of peers")
    p = u.deep_rank(subs, "min3", code)
    if p is not None:
        chk("Worst rolling 3Y return", p >= (0.15 if growth else 0.3), f"{d['min3']:.1f}% a year · better than {round(p * 100)}% of peers")
    if d["beat5"] is not None and (d["n5"] or 0) >= 120 and not hybrid:
        chk("Beats benchmark (rolling 5Y)", d["beat5"] >= 50, f"{d['beat5']:.0f}% of periods")
    won, n = u.cal_vs_category(subs, code)
    if n >= 3:
        need = math.ceil(n * 0.5)
        chk("Calendar-year record", won >= need, f"beat the category average in {won} of the last {n} years (needs {need})")
    if d["r2"] is not None and slot in ("flexi", "lmcore", "mid", "small"):
        chk("True to mandate (R²)", d["r2"] >= 70, f"{d['r2']:.0f}% of moves explained by its benchmark")
    if d["turnover"] is not None and not hybrid:
        t = d["turnover"] * (100 if d["turnover"] <= 5 else 1)
        lim = TURNOVER_MAX_GROWTH if growth else TURNOVER_MAX
        chk("Portfolio turnover", t <= lim, f"{t:.0f}% a year (limit {lim}%)")
    rec = u.g(code, "rec")
    if rec is not None:
        chk("Recent form", rec >= 25, f"{rec:.0f}/100 recency score")
    rating = u.g(code, "rating")
    if rating:
        chk("VilfinTV rating", rating >= 3, f"{rating} star{'s' if rating > 1 else ''}")
    if hybrid:
        md = u.g(code, "mdd")
        lim = -20 if slot == "baf" else -10
        chk("Smaller falls than equity", md is None or md >= lim, f"worst fall {md:.1f}% (limit {lim}%)" if md is not None else "–")


def scores(u, slot, codes, kind, growth=False):
    m = lambda col: {c: u.g(c, col) for c in codes}  # noqa: E731
    logaum = {c: math.log10(max(u.g(c, "aum") or 1, 1)) for c in codes}
    if kind == "factor":
        parts = [(pct_rank(m("r3y")), .25), (pct_rank(m("sortino")), .15), (pct_rank(m("mdd")), .10),
                 (pct_rank(m("ter"), False), .25), (pct_rank(logaum), .25)]
    elif kind in ("index", "passive"):
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
    elif growth and kind == "active":           # very aggressive: rank on return and skill first
        alpha = {c: u.deep(c).get("alpha") for c in codes}
        parts = [(pct_rank(m("roll3")), .22), (pct_rank(m("r5y")), .15), (pct_rank(alpha), .13), (pct_rank(m("beat3")), .12),
                 (pct_rank(m("sortino")), .10), (pct_rank(m("cons")), .08), (pct_rank(m("rec")), .07), (pct_rank(m("mdd")), .05),
                 (pct_rank(m("ter"), False), .05), (pct_rank(logaum), .03)]
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
    if slot == "pioneer":
        return subs, [c for c in u.by_subs(subs) if RX_PIONEER.search(u.g(c, "name") or "")], kind
    if slot == "metal":
        subs = [ctx["metal"]]
        return subs, u.by_subs(subs), kind
    if slot == "momentum":
        codes = [c for c in u.by_subs(subs) if RX_MOMENTUM.search(u.g(c, "name") or "")]
        return subs, codes, kind
    if slot == "theme":
        codes = sector_funds(u, ctx["sector"])
        return sorted({u.g(c, "sub") for c in codes}), codes, kind
    return subs, u.by_subs(subs), kind


def rank_pool(u, slot, ctx, cache):
    key = (slot, ctx.get("pool_key"), ctx.get("metal"), ctx.get("sector"), ctx.get("profile"), ctx.get("style") if slot == "pioneer" else None)
    if key in cache:
        return cache[key]
    subs, codes, kind = pool_for(u, slot, ctx)
    cctx = {**ctx, "subs": subs}
    checks = {c: fund_checks(u, slot, c, cctx) for c in codes}
    ok = [c for c in codes if all(x[1] for x in checks[c])]
    if kind == "sector":
        act = [c for c in ok if not (u.g(c, "sub") or "").startswith("idx_")]
        idx = [c for c in ok if (u.g(c, "sub") or "").startswith("idx_")]
        sc = {**(scores(u, slot, act, "active", ctx.get("profile") == "growth") if act else {}), **(scores(u, slot, idx, "index") if idx else {})}
    else:
        sc = scores(u, slot, ok, kind, ctx.get("profile") == "growth") if ok else {}
    if slot == "intl" and not ok:                       # every international fund closed or failing → backup pool
        bsubs = list(subs) + ["sec_innov"]
        backup = [c for c in u.by_subs(["sec_innov"])
                  if ((u.pf.get(c) or {}).get("mix") or {}).get("overseas", 0) >= INTL_BACKUP_MIN_OVERSEAS
                  or RX_INTL_BACKUP.search(u.g(c, "name") or "")]
        bctx = {**ctx, "subs": bsubs, "intl_backup": True}
        checks.update({c: fund_checks(u, slot, c, bctx) for c in backup})
        ok = [c for c in backup if all(x[1] for x in checks[c])]
        sc = scores(u, slot, ok, "active", ctx.get("profile") == "growth") if ok else {}
        subs = bsubs
    ranked = sorted(ok, key=lambda c: -sc[c])
    if slot == "pioneer":            # alternates: value or momentum funds, whichever style the market favours this month
        sr, ssc, schecks, ssubs = rank_pool(u, ctx.get("style") or "value", {**ctx, "pool_key": None}, cache)
        ranked = ranked + [c for c in sr if c not in ranked]
        sc, checks, subs = {**ssc, **sc}, {**schecks, **checks}, list(subs) + [x for x in ssubs if x not in subs]
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
    if slot == "lmcore":
        gross = (eq("core") + eq("mid")) / 2      # the category holds at least 35% each in large and mid caps
    elif slot == "pioneer" and ctx.get("style_fund"):           # slot filled by its value / momentum alternate
        gross = eq(ctx["style_fund"])
    elif slot in ("core", "next50", "flexi", "mid", "small", "value", "momentum", "theme", "intl", "pioneer"):
        gross = eq(slot)
    elif slot == "baf":
        gross = 0.6 * eq("core") + 0.4 * (tb364 + 0.6)
    elif slot == "multi":                         # typical mix: two-thirds equity, a fifth debt, the rest gold/silver
        gross = 0.65 * eq("core") + 0.2 * (tb364 + 0.6) + 0.15 * (ASSUMPTIONS["metalReturn"] + (ctx.get("metalAdj") or 0))
    elif slot == "eqsav":
        gross = 0.35 * eq("core") + 0.65 * (tb364 + 0.3)
    elif slot == "arb":
        gross = tb91 - 0.1
    elif slot == "dshort":
        gross = tb91 + (0.5 if sub == "floater" else 0.3)
    elif slot == "dmed":
        gross = g10 + 0.4 if sub == "meddur" else (g10 if sub == "dynbond" else tb364 + 0.7)
    elif slot == "dcore":
        gross = g10 if sub in ("gilt", "gilt10", "dynbond") else tb364 + (0.5 if sub == "floater" else 0.6)
    elif slot == "metal":
        gross = ASSUMPTIONS["metalReturn"] + (ctx.get("metalAdj") or 0)
    else:
        gross = 8.0
    if slot in ALPHA_SLOTS and not (sub or "").startswith("idx_"):
        gross += alpha_credit(u, code)
    return round(gross - (u.g(code, "ter") or 0), 2)


ALPHA_SLOTS = ("lmcore", "flexi", "mid", "small", "value", "theme", "multi", "pioneer")


def alpha_credit(u, code):
    """Expected-return credit for an active fund's proven skill: a third of its 3-year alpha over its benchmark
    (only part of past out-performance tends to persist), between −1 and +2 points a year."""
    a = u.deep(code).get("alpha")
    return 0.0 if a is None else round(clamp(a / 3, -1.0, 2.0), 2)


def past_return(u, slots, col):
    """Weighted past annual return of the plan's funds (weights re-scaled over funds with that much history)."""
    have = [(s["w"], u.g(s["code"], col)) for s in slots if u.g(s["code"], col) is not None]
    tw = sum(w for w, _ in have)
    if tw < 70:
        return None
    return {"v": round(sum(w * r for w, r in have) / tw, 2), "cover": tw}


def risk10(vol, mdd):
    """Risk score out of 10 (0 = no price swings): 60% annual volatility (25% or more = full) + 40% worst fall (40% or more = full)."""
    if vol is None and mdd is None:
        return None
    v = min((vol or 0) / 25, 1) if vol is not None else min(abs(mdd) / 40, 1)
    d = min(abs(mdd or 0) / 40, 1) if mdd is not None else v
    return round(10 * (0.6 * v + 0.4 * d), 1)


_WEEKLY = {}


def weekly_nav(code):
    """{friday: nav} from data/mf/h/<code>.json (last NAV on or before each Friday); cached."""
    if code not in _WEEKLY:
        out = {}
        try:
            h = json.loads((MF / "h" / f"{code}.json").read_text())
            s0 = date.fromisoformat(h["s"])
            for off, nav in h["p"]:
                d = s0 + timedelta(days=off)
                out[d + timedelta(days=(4 - d.weekday()) % 7)] = nav
        except Exception:  # noqa: BLE001
            pass
        _WEEKLY[code] = out
    return _WEEKLY[code]


def mix_drawdown(u, slots, years=10):
    """Worst peak-to-trough fall of the plan's funds held together (weekly, rebalanced to the plan weights every week)
    over the last `years` years. Before a fund existed, the longest-running fund of the same category stands in for it
    (`proxy`); funds still without history on a date are left out and the rest re-weighted, and the series starts once
    funds worth >= 80% of the plan have history."""
    held = [(s["code"], s["w"]) for s in slots if s.get("w")]
    navs, proxied = {}, False
    for c, _ in held:
        own = weekly_nav(c)
        peers = [x for x in u.by_subs([u.g(c, "sub")]) if x != c]
        old = min(peers, key=lambda x: min(weekly_nav(x) or [date.max]), default=None)
        px = weekly_nav(old) if old else {}
        if own and px and min(px) < min(own):
            first = min(own)
            navs[c] = {d: v for d, v in px.items() if d <= first}
            k = own[first] / navs[c][first] if first in navs[c] else None
            if k:                                              # splice: scale the stand-in onto the fund's own NAV
                navs[c] = {d: v * k for d, v in navs[c].items()}
                navs[c].update(own)
                proxied = True
                continue
        navs[c] = own
    days = sorted({d for n in navs.values() for d in n})
    if not days:
        return None
    start = days[-1] - timedelta(days=round(365.25 * years))
    days = [d for d in days if d >= start]
    tot = sum(w for _, w in held)
    val, peak, worst, wpk, wtr, first, rets = 1.0, 1.0, 0.0, None, None, None, []
    for a, b in zip(days, days[1:]):
        rs = [(w, navs[c][b] / navs[c][a] - 1) for c, w in held if a in navs[c] and b in navs[c] and navs[c][a] > 0]
        cw = sum(w for w, _ in rs)
        if not rs or (first is None and cw < 0.8 * tot):
            continue
        if first is None:
            first = pk_day = a
        pr = sum(w * r for w, r in rs) / cw
        rets.append(pr)
        val *= 1 + pr
        if val > peak:
            peak, pk_day = val, b
        dd = val / peak - 1
        if dd < worst:
            worst, wpk, wtr = dd, pk_day, b
    if first is None:
        return None
    vol = st.pstdev(rets) * 52 ** 0.5 * 100 if len(rets) > 10 else None
    return {"v": round(worst * 100, 1) + 0.0, "vol": round(vol, 1) if vol is not None else None, "peak": wpk.isoformat() if wpk else None, "trough": wtr.isoformat() if wtr else None,
            "from": first.isoformat(), "years": round((days[-1] - first).days / 365.25, 1), "proxy": proxied}


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
            lim = 30 if {"core", "next50", "lmcore"} & {slot, oslot} else 20
            if ov is not None and ov > lim:
                return False
        return True

    def fits(c):
        return amc_count.get(u.g(c, "amc"), 0) < 2 and overlap_ok(c) and c not in chosen
    cand = [c for c in ranked if fits(c)] or [c for c in ranked if c not in chosen]
    if incumbent:
        code = incumbent["code"]
        hard = (u.g(code, "sub") is not None and buy_ok(u, code) and u.g(code, "status") != "Out of track"
                and code in checks)                      # a fund that no longer belongs to this slot's pool is replaced
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
            if code in ranked:
                return code, [c for c in cand if c != code][:2], "kept", ""
            fails = [x[0] for x in fund_checks(u, slot, code, {**ctx, "subs": subs}) if not x[1]]
            return code, [c for c in cand if c != code][:2], "watch", (
                "On watch (" + (", ".join(fails[:2]) if fails else "slipped in its category ranking") + ") — reviewed at the next monthly review")
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


UPGRADE_MAX_MIN = 25000      # an "upgrade" fund may need up to ₹25,000 per purchase
UPGRADE_MARGIN = 3.0          # and must score clearly above the plan's fund


def upgrade_for(u, slot, ctx, cache, chosen, amc_count, code, macro):
    """Best fund for the slot when the investor's amount per purchase is larger: it passes every check except the
    ₹1,000 lump-sum limit (minimum ≤ ₹25,000) and scores clearly above the plan's fund. The page swaps it in when
    the slot's amount per purchase covers its minimum. None when no such fund exists."""
    kind = SLOTS[slot][3]
    if kind == "sector" or slot in ("metal", "intl"):
        return None
    ranked, sc, checks, subs = rank_pool(u, slot, ctx, cache)
    cands = [c for c, ck in checks.items() if c != code and c not in chosen
             and all(x[1] or x[0] == "Lump-sum minimum" for x in ck) and not all(x[1] for x in ck)
             and (u.g(c, "lumpMin") or 0) <= UPGRADE_MAX_MIN
             and amc_count.get(u.g(c, "amc"), 0) < 2]
    if not cands:
        return None
    sc2 = scores(u, slot, cands + [code], kind, ctx.get("profile") == "growth")
    best = max(cands, key=lambda c: sc2[c])
    if sc2[best] < sc2[code] + UPGRADE_MARGIN:
        return None
    mn = u.g(best, "lumpMin")
    ck = [([x[0], True, f"₹{mn:,.0f} per purchase — used when your amount for this fund covers it"] if x[0] == "Lump-sum minimum" else x)
          for x in checks[best]]
    return {"code": best, "min": mn, "score": round(sc2[best], 1), "vsScore": round(sc2[code], 1), "checks": ck,
            "why": why(u, slot, best), "er": expected_return(u, slot, best, ctx, macro),
            "tax": u.g(best, "tax") or ("equity" if SLOTS[slot][1] == "Equity" else "other")}


SEGMENTS = [("large", "Large caps", "n50", ["core", "next50", "lmcore", "flexi"]), ("mid", "Mid caps", "mid150", ["mid"]), ("small", "Small caps", "sml250", ["small"])]


def segment_rotation(macro):
    """Rank large / mid / small caps by valuation vs their own 10-year history; points move from the dearest
    segment to the cheapest (5 pts for a 30-pt percentile gap, 10 pts for 50+)."""
    val = (macro or {}).get("valuation") or {}
    segs = []
    for key, label, vk, slots in SEGMENTS:
        v = val.get(vk) or {}
        ps = [x for x in (v.get("pePct"), v.get("pbPct")) if x is not None]
        if ps:
            segs.append({"key": key, "label": label, "pe": v.get("pe"), "peMed": v.get("peMed"), "pct": round(sum(ps) / len(ps), 3)})
    if len(segs) < 2:
        return {"segments": segs, "from": None, "to": None, "pts": 0}
    cheap, dear = min(segs, key=lambda x: x["pct"]), max(segs, key=lambda x: x["pct"])
    gap = dear["pct"] - cheap["pct"]
    pts = 10 if gap >= 0.5 else (5 if gap >= 0.3 else 0)
    return {"segments": segs, "from": dear["key"] if pts else None, "to": cheap["key"] if pts else None, "pts": pts, "gap": round(gap, 3)}


def apply_rotation(weights, rot, hz):
    """Within the equity sleeve: move points from the dearest segment's slot to the cheapest one present (≥5% kept)."""
    w = dict(weights)
    if hz in ("h1", "h3") or not rot or not rot.get("pts"):
        return w, 0
    src = next((s for k, _, _, sl in SEGMENTS if k == rot["from"] for s in reversed(sl) if s in w), None)
    dst = next((s for k, _, _, sl in SEGMENTS if k == rot["to"] for s in sl if s in w), None)
    if not src or not dst or src == dst:
        return w, 0
    moved = 0
    while moved < rot["pts"] and w[src] > 5:
        w[src] -= 5
        w[dst] += 5
        moved += 5
    return w, moved


# valuation gate: an equity slot whose market segment is very expensive vs its own 10-year history gets a smaller
# (or no) allocation that month; the money goes to the cheapest fairly valued equity slot in the plan, else to debt.
GATE_KEYS = {"core": ["n50"], "next50": ["nn50"], "lmcore": ["n50", "mid150"], "flexi": ["n500"], "mid": ["mid150"], "small": ["sml250"]}
GATE_PAUSE, GATE_HALF = 0.90, 0.80
GATE_CAP = 40                                 # no single fund receives more than 40% after a move


def gate_cap(key):
    """Most a slot may hold after receiving moved money (style sleeves ≤15%, satellites never receive)."""
    return 0 if key in ("theme", "intl") else (15 if key in ("value", "momentum") else GATE_CAP)
GATE_LABEL = {"n50": "Nifty 50", "nn50": "Nifty Next 50", "n500": "Nifty 500", "mid150": "Nifty Midcap 150", "sml250": "Nifty Smallcap 250"}


def valuation_gates(macro, dec, review):
    val = (macro or {}).get("valuation") or {}
    out = {}
    for slot, keys in GATE_KEYS.items():
        pcts = []
        for k in keys:
            ps = [x for x in ((val.get(k) or {}).get("pePct"), (val.get(k) or {}).get("pbPct")) if x is not None]
            if ps:
                pcts.append(sum(ps) / len(ps))
        pct = round(sum(pcts) / len(pcts), 3) if pcts else None
        now = "full" if pct is None else ("pause" if pct >= GATE_PAUSE else ("half" if pct >= GATE_HALF else "full"))
        out[slot] = {"pct": pct, "now": now, "level": stable(dec, f"gate:{slot}", now, review, strong=True),
                     "index": " / ".join(GATE_LABEL.get(k, k) for k in keys),
                     "pe": [(val.get(k) or {}).get("pe") for k in keys], "peMed": [(val.get(k) or {}).get("peMed") for k in keys]}
    return out


def apply_gate(weights, gates):
    """Cut the weight of very expensive segments this month (pause = 0%, half = half) and move it on."""
    w, cuts = dict(weights), {}
    for slot in [k for k in sorted(w, key=ORDER.index) if k in gates]:
        lv = gates[slot]["level"]
        cut = w[slot] if lv == "pause" else ((w[slot] // 10) * 5 if lv == "half" else 0)
        if cut <= 0:
            continue
        fair = [k for k in w if k in gates and gates[k]["level"] == "full"] or [k for k in ("value", "momentum") if k in w]
        rank = lambda k: (gates[k]["pct"] if k in gates and gates[k]["pct"] is not None else 0.5)  # noqa: E731
        moved, first = 0, None
        while moved < cut:                       # 5-point steps to the cheapest fair segment below the cap
            cand = sorted([k for k in fair if w[k] + 5 <= gate_cap(k)], key=rank)
            dst = cand[0] if cand else next((k for k in ("dmed", "dcore", "baf", "dshort", "arb") if k in w), None)
            if not dst:
                break
            w[slot] -= 5
            w[dst] += 5
            moved += 5
            first = first or dst
        if moved:
            cuts[slot] = {"level": lv, "cut": moved, "to": first, "pct": gates[slot]["pct"], "index": gates[slot]["index"]}
    return w, cuts


# fund-level valuation: portfolio P/E (data/mf/fund_pe.json) against the median of funds in the same category
FPE_SLOTS = ("lmcore", "flexi", "mid", "small", "value")
FPE_HALF, FPE_PAUSE = 1.25, 1.5


def fund_pe_info(u, code, fpe):
    x = fpe.get(code)
    if not x:
        return None
    peers = [fpe[c][0] for c in u.by_subs([u.g(code, "sub")]) if c in fpe]
    if len(peers) < 5:
        return None
    med = median(peers)
    return {"pe": x[0], "peerPe": round(med, 1), "prem": round(x[0] / med, 2), "cover": x[1]}


def apply_fund_pe(u, slots, fpe, dec, pid, review):
    """Halve (P/E ≥1.25× peers) or pause (≥1.5×) a fund's allocation this month; the money goes to the plan's
    most reasonably valued equity fund, else to debt."""
    for s in slots:
        if s["key"] not in FPE_SLOTS or s["w"] <= 0:
            continue
        info = fund_pe_info(u, s["code"], fpe)
        if not info:
            continue
        s["pe"] = info
        s["why"] = s["why"] + [f"Portfolio P/E {info['pe']:.1f} vs category median {info['peerPe']:.1f}"]
        now = "pause" if info["prem"] >= FPE_PAUSE else ("half" if info["prem"] >= FPE_HALF else "full")
        lv = stable(dec, f"fpe:{pid}:{s['key']}:{s['code']}", now, review, strong=True)
        cut = s["w"] if lv == "pause" else ((s["w"] // 10) * 5 if lv == "half" else 0)
        if cut <= 0:
            continue
        moved, first = 0, None
        while moved < cut:
            eq = [z for z in slots if z is not s and z["w"] > 0 and z["w"] + 5 <= gate_cap(z["key"]) and z["asset"] == "Equity" and not z.get("gate")]
            eq.sort(key=lambda z: ((z.get("pe") or {}).get("prem") or 1.0, z["w"]))
            dst = eq[0] if eq else next((z for z in slots if z["key"] in ("dmed", "dcore", "baf", "dshort", "arb")), None)
            if dst is None:
                break
            s["w"] -= 5
            dst["w"] += 5
            moved += 5
            first = first or dst
        if not moved:
            continue
        s["gate"] = {"level": lv, "cut": moved, "to": first["key"], "toLabel": first["label"], "reason": "fund",
                     "pe": info["pe"], "peerPe": info["peerPe"], "index": f"portfolio P/E {info['pe']:.1f} vs category median {info['peerPe']:.1f}"}


def apply_tilt(weights, tilt, hz):
    w = dict(weights)
    if hz in ("h1", "h3") or not tilt:
        return w, 0
    eq_take = ["core", "next50", "lmcore", "flexi"] if tilt > 0 else ["small", "mid", "flexi", "lmcore", "next50", "core"]
    dt_take = ["dcore", "dmed", "dshort", "metal", "baf", "eqsav", "arb"]
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


def data_since(macro: dict) -> dict:
    """First month on record for every index in the earnings table (val_hist.json; global indices from VilfinTV's own
    monthly record), so the page can say when a 1 / 3 / 5-year figure will first be available instead of a blank."""
    out = {}
    for path, pre in ((MF / "val_hist.json", ""), (MF / "global_val_hist.json", "")):
        try:
            months = json.loads(path.read_text()).get("months") or {}
        except Exception:  # noqa: BLE001
            continue
        for m in sorted(months):
            row = months[m]
            for k in (row.get("v") if isinstance(row, dict) and "v" in row else row) or {}:
                out.setdefault(pre + k, m)
    return out


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

    glob = global_signals(macro)
    gold_lvl = stable(dec, "goldtilt", "up" if glob["score"]["G"] >= 2 else ("down" if glob["score"]["G"] <= -2 else "flat"), review, strong=True)
    gscore = {"up": 2, "down": -2}.get(gold_lvl, 0)
    rr = rate_regime(macro, u, glob)
    regime = stable(dec, "regime", rr["regime"], review, strong=abs(rr["score"]) >= 2.5)
    # style for the innovation sleeve's alternates: momentum while the Nifty 50 trends up (above its 6-month average with a
    # positive 6-month return), value otherwise — a monthly-stable decision like the others
    n50v = ((macro or {}).get("valuation") or {}).get("n50") or {}
    trending = (n50v.get("vs6m") or 0) > 0 and (n50v.get("r6m") or 0) > 0
    style = stable(dec, "style", "momentum" if trending else "value", review)
    style_why = (f"Nifty 50 {n50v.get('vs6m', 0):+.1f}% vs its 6-month average, {n50v.get('r6m', 0):+.1f}% over 6 months — "
                 + ("trend-following (momentum) funds favoured" if style == "momentum" else "valuation-led (value) funds favoured"))
    tilt_now, tilt_comps = market_tilt(u, macro, sentiment, glob)
    tilt = stable(dec, "tilt", tilt_now, review, strong=True)
    rot_now = segment_rotation(macro)
    rot_key = stable(dec, "rotation", f"{rot_now['from']}>{rot_now['to']}:{rot_now['pts']}", review)
    rot_from, rest = rot_key.split(">")
    rot_to, rot_pts = rest.split(":")
    rotation = {**rot_now, "from": None if rot_from == "None" else rot_from, "to": None if rot_to == "None" else rot_to, "pts": int(rot_pts)}
    gates = valuation_gates(macro, dec, review)
    fpe = (load(MF / "fund_pe.json", {}) or {}).get("funds") or {}
    sectors = sector_outlook(sector_table(u, macro), macro, regime, glob)
    metal = metal_signal(u, glob["score"]["S"])
    metal_choice = stable(dec, "metal", metal.get("choice", "gold"), review)

    cache = {}
    sector_pick = None                       # most attractive sector with at least one fund passing every check
    for row in sectors:
        ranked, *_ = rank_pool(u, "theme", {"sector": row["key"], "pool_key": None, "metal": None, "regime": regime,
                                            "sector_label": row["label"], "sector_row": row}, cache)
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
            weights, rotated = apply_rotation(weights, rotation, hz)
            weights, cuts = apply_gate(weights, gates)
            weights, metal_tilt = apply_metal_tilt(weights, gscore, hz)
            weights, multi_drop = apply_multi_asset(weights, rk, hz, regime, 0, gscore)   # both decisions are monthly-stable
            pst = state["plans"].setdefault(pid, {"slots": {}})
            chosen, amc_count, slots, changes, skipped = {}, {}, [], [], []
            for slot in sorted(weights, key=ORDER.index):
                pool_key = None
                if slot in DEBT_POOLS:
                    pool_key = "easing_long" if (slot == "dcore" and regime == "easing" and hz in ("h5", "h7", "h10")) else regime
                m = metal_choice if (rk in ("a", "v") and hz in ("h7", "h10")) else "gold"
                ctx = {"pool_key": pool_key, "metal": m if slot == "metal" else None, "sector": sector if slot == "theme" else None,
                       "style": style if slot == "pioneer" else None,
                       "regime": regime, "sector_index": sector_row.get("index"), "sector_label": sector_row.get("label"), "sector_row": sector_row,
                       "metalAdj": 1.0 if gscore >= 2 else (-1.0 if gscore <= -2 else 0.0),
                       "profile": "growth" if rk == "v" else "std"}
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
                if slot == "pioneer" and not RX_PIONEER.search(u.g(code, "name") or ""):
                    lab = f"{SLOTS[style][0]} — in place of the innovation & global tech sleeve"
                slots.append({
                    "key": slot, "label": lab, "asset": SLOTS[slot][1], "w": weights[slot], "base": base.get(slot, 0),
                    "code": code, "score": sc.get(code), "alts": alts, "since": pst["slots"][slot]["since"],
                    "state": "watch" if action == "watch" else "ok", "note": note, "why": why(u, slot, code),
                    "checks": ck, "pool": len(ranked),
                    "er": expected_return(u, slot, code, {**ctx, "style_fund": (None if slot != "pioneer" or RX_PIONEER.search(u.g(code, "name") or "")
                                                                            else ("value" if u.g(code, "sub") in ("value", "contra") else "momentum"))}, macro),
                    "vol": SLOTS[slot][6] if slot != "metal" else (25 if ctx["metal"] == "silver" else 14),
                    "tax": u.g(code, "tax") or ("equity" if SLOTS[slot][1] == "Equity" else "other"),
                })
                up = upgrade_for(u, slot, ctx, cache, chosen, amc_count, code, macro)
                if up:
                    slots[-1]["upgrade"] = up
                if slot in cuts:
                    c = cuts[slot]
                    slots[-1]["gate"] = {**c, "toLabel": SLOTS[c["to"]][0]}
            for sk in skipped:
                tgt = next((x for x in FALLBACK.get(sk, []) if any(z["key"] == x for z in slots)), None)
                tgt = next(z for z in slots if z["key"] == tgt) if tgt else max(slots, key=lambda z: z["w"])
                tgt["w"] += weights[sk]
                tgt["note"] = (tgt["note"] + " " if tgt["note"] else "") + f"Includes the {SLOTS[sk][0].lower()} allocation (no fund currently passes every check)."
            apply_fund_pe(u, slots, fpe, dec, pid, review)
            for k in list(pst["slots"]):
                if k not in weights or k in skipped:
                    pst["slots"].pop(k)
            pst["changes"] = (changes + pst.get("changes", []))[:6]
            for z in slots:                          # each fund over the same window as the mix (stand-in before launch)
                own = mix_drawdown(u, [{"code": z["code"], "w": 100}]) or {}
                z["hist10"] = {"v": own.get("v"), "vol": own.get("vol")} if own else None
                z["risk10"] = risk10(own.get("vol"), own.get("v")) if own else risk10(u.g(z["code"], "std"), u.g(z["code"], "mdd"))
                z["pts10"] = round(z["score"] / 10, 1) if z.get("score") is not None else None
            codes = [s["code"] for s in slots]
            eq = [c for c in codes if chosen.get(c) in ("core", "next50", "lmcore", "flexi", "mid", "small", "value", "momentum", "theme")]
            ovs = [o for o in (u.overlap(a, b) for i, a in enumerate(eq) for b in eq[i + 1:]) if o is not None]
            mix = {}
            for s in slots:
                mix[s["asset"]] = mix.get(s["asset"], 0) + s["w"]
            plans[pid] = {
                "horizon": hz_label, "risk": rk_label, "years": yrs, "yearsMin": ymin, "yearsMax": ymax, "tilt": applied, "rotated": rotated, "metalTilt": metal_tilt, "multiFor": multi_drop,
                "slots": slots, "mix": mix, "ter": round(sum((u.g(s["code"], "ter") or 0) * s["w"] for s in slots) / 100, 2),
                "er": round(sum(s["er"] * s["w"] for s in slots) / 100, 2),
                "hist": {k: past_return(u, slots, k) for k in ("r3y", "r5y")},
                "mdd": (mdd := mix_drawdown(u, slots)),
                "risk10": risk10((mdd or {}).get("vol"), (mdd or {}).get("v")),
                "points10": round(sum((z.get("score") or 0) * z["w"] for z in slots) / max(1, sum(z["w"] for z in slots if z.get("score") is not None)) / 10, 1),
                "mddFunds": past_return(u, slots, "mdd"),
                "gated": sum(z["gate"]["cut"] for z in slots if z.get("gate")),
                "maxOverlap": max(ovs) if ovs else None, "amcs": len({u.g(c, "amc") for c in codes}),
                "checks": sum(len(s["checks"]) for s in slots), "changes": pst["changes"],
            }
    if review:
        state["reviewed"] = month
    state["updated"] = today.isoformat()
    val = macro.get("valuation") or {}
    row = lambda c: {k: u.g(c, k) for k in u.cols} if c in u.rows else None   # noqa: E731
    by_sub = {}
    for c in u.rows:
        by_sub.setdefault(u.g(c, "sub"), []).append(row(c))
    dip = dip_rules.mf_block(plans, row, lambda c: by_sub.get(u.g(c, "sub"), []),
                     lambda c: exit_rule(u.info(c).get("exitLoad"), u.g(c, "exitNil")),
                     lambda c: fund_pe_info(u, c, fpe), macro, gates, metal_choice, scr["asOf"], [row(c) for c in u.rows])
    out = {"v": VERSION, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "asOf": scr["asOf"],
           "reviewed": state["reviewed"], "nextReview": date(today.year + (today.month == 12), today.month % 12 + 1, 1).isoformat(),
           "market": {"tilt": tilt, "tiltNow": tilt_now, "components": tilt_comps, "rotation": rotation, "gates": gates,
                      "growth": {**{k: v for k, v in ((macro or {}).get("growth") or {}).items() if k != "gdpRaw"}, "since": data_since(macro)},
                      "n50": {k: (val.get("n50") or {}).get(k) for k in ("pe", "pb", "dy", "pePct", "pbPct", "peMed", "pbMed", "r12m")},
                      "valuationAsOf": macro.get("valuationAsOf")},
           "rates": {**rr, "applied": regime},
           "global": {**glob, "goldTilt": gold_lvl},
           "sectors": [{k: r.get(k) for k in ("key", "label", "pe", "peMed", "valPct", "r6mRel", "r12mRel", "score", "signal", "excluded", "eligible", "years", "outlook")}
                       for r in sectors],
           "sector": sector, "metal": {**metal, "applied": metal_choice}, "style": {"value": style, "why": style_why},
           "assumptions": ASSUMPTIONS,
           "horizons": [{"id": h, "label": l, "years": y, "min": a, "max": b} for h, l, y, a, b in HORIZONS],
           "risks": [{"id": r, "label": l} for r, l in RISKS],
           "plans": plans, "dip": dip}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    STATE.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")))
    log.info("Smart SIP v2: regime %s (score %s) · tilt %+d · sector %s · metal %s · review=%s",
             regime, rr["score"], tilt, sector, metal_choice, review)
    for pid, p in plans.items():
        log.info("  %-4s er %.2f%% | %s", pid, p["er"], " | ".join(f"{s['key']}:{s['w']}% {u.g(s['code'], 'name')[:26]}" for s in p["slots"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
