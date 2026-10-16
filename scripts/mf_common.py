#!/usr/bin/env python3
"""
India Mutual Fund Screener — shared parsing, classification and analytics.

Used by scripts/build_mf_screener.py. Every formula here is re-implemented
independently in scripts/verify_mf_screener.js and CI requires both to agree.

Conventions (documented on india_mf_screener.html → Methodology):
  * Trailing returns: NAV on the latest date vs the NAV on or before the same
    calendar date N months/years earlier. Periods up to 1 year are absolute %,
    longer periods are CAGR with exponent 1/years. Since inception is CAGR over
    the actual day count (absolute when the fund is younger than 1 year).
  * SIP returns: ₹10,000 on the same calendar day each month (NAV of that day or
    the next business day), valued at the latest NAV, XIRR on an Actual/365 basis.
  * Rolling returns: CAGR for every trading day's window of N years.
  * Risk ratios: 36 monthly returns (month-end NAVs) ending at the last completed
    month-end. Risk-free = overnight money-market return for the same months.
  * Factor DNA: returns-based style analysis (non-negative weights summing to 1)
    of 156 weekly returns against NSE factor and size indices.
"""
from __future__ import annotations

import math
import re
from calendar import monthrange
from datetime import date, datetime

import numpy as np

# ═════════════════════════════════ PARSING ═════════════════════════════════
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_amfi_date(s: str) -> date | None:
    """'14-Oct-2026' → date."""
    try:
        d, m, y = s.strip().split("-")
        return date(int(y), MONTHS[m[:3].lower()], int(d))
    except Exception:
        return None


def parse_dmy(s: str) -> date | None:
    """'14-10-2026' → date (mfapi format)."""
    try:
        d, m, y = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def clean_text(s: str) -> str:
    s = s.replace("â\u0080\u0099", "'").replace("â\x80\x99", "'").replace("’", "'").replace("â", "'")
    return re.sub(r"\s+", " ", s).strip()


def parse_navall(text: str) -> list[dict]:
    """Parse AMFI NAVAll.txt (with Plan / Option columns)."""
    rows, cat, amc = [], None, None
    header = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ";" not in line:
            if re.search(r"Schemes\s*\(", line):
                cat = clean_text(line)
            else:
                amc = clean_text(line)
            continue
        p = [x.strip() for x in line.split(";")]
        if not p[0].isdigit():
            header = [h.lower() for h in p]
            continue
        if header and len(header) >= 8 and len(p) >= 8:
            code, isin1, isin2, name, plan, opt, nav, dt = p[:8]
        else:  # legacy 6-column layout
            code, isin1, isin2, name, nav, dt = p[:6]
            plan, opt = "", ""
        try:
            navf = float(nav)
        except ValueError:
            navf = None
        rows.append({
            "code": int(code), "isin": isin1 if isin1 not in ("-", "") else (isin2 if isin2 not in ("-", "") else ""),
            "isin2": isin2 if isin2 not in ("-", "") and isin1 not in ("-", "") else "",
            "name": clean_text(name), "plan": plan, "opt": opt, "nav": navf,
            "date": parse_amfi_date(dt), "cat": cat or "", "amc": amc or "",
        })
    return rows


_NOT_GROWTH = re.compile(r"idcw|dividend|bonus|payout|reinvest|income distribution|segregat", re.I)


def is_direct_growth(r: dict) -> bool:
    if not r["cat"].startswith("Open Ended"):
        return False
    if "ETF" in r["cat"].split("(", 1)[-1][:40] or re.search(r"Gold ETF|Other\s+ETFs", r["cat"]):
        return False
    if r["plan"].lower() != "direct plan":
        return False
    opt = r["opt"]
    if _NOT_GROWTH.search(r["name"]) or _NOT_GROWTH.search(opt):
        return False
    if re.search(r"growth|cumulative", opt, re.I):
        return True
    return opt == "" and bool(re.search(r"growth", r["name"], re.I))


# ═══════════════════════════════ CLASSIFICATION ════════════════════════════
ASSETS = ["Equity", "Debt", "Hybrid", "Commodity", "Global", "Index", "Solution"]

SUBS = {  # key: (asset, label)
    "large": ("Equity", "Large Cap"), "largemid": ("Equity", "Large & Mid Cap"), "mid": ("Equity", "Mid Cap"),
    "small": ("Equity", "Small Cap"), "multi": ("Equity", "Multi Cap"), "flexi": ("Equity", "Flexi Cap"),
    "focused": ("Equity", "Focused"), "value": ("Equity", "Value"), "contra": ("Equity", "Contra"),
    "divyield": ("Equity", "Dividend Yield"), "elss": ("Equity", "ELSS (Tax Saver)"),
    # sectoral / thematic funds, split by theme (ratings and scorecards still rank across all of them, see GROUP)
    "sec_bank": ("Equity", "Banking & Financial"), "sec_pharma": ("Equity", "Pharma & Healthcare"),
    "sec_tech": ("Equity", "Technology & Digital"), "sec_consumption": ("Equity", "Consumption"),
    "sec_infra": ("Equity", "Infrastructure & Housing"), "sec_mfg": ("Equity", "Manufacturing & Exports"),
    "sec_energy": ("Equity", "Energy & Commodities"), "sec_psu": ("Equity", "PSU"),
    "sec_mnc": ("Equity", "MNC & Conglomerates"), "sec_cycle": ("Equity", "Business Cycle & Rotation"),
    "sec_quant": ("Equity", "Quant, Momentum & Factor"), "sec_esg": ("Equity", "ESG & Ethical"),
    "sec_innov": ("Equity", "Innovation & Opportunities"), "sec_other": ("Equity", "Other Thematic"),
    "eqfof": ("Equity", "Equity FoF"),
    "overnight": ("Debt", "Overnight"), "liquid": ("Debt", "Liquid"), "ultrashort": ("Debt", "Ultra Short Duration"),
    "lowdur": ("Debt", "Low Duration"), "money": ("Debt", "Money Market"), "shortdur": ("Debt", "Short Duration"),
    "meddur": ("Debt", "Medium Duration"), "medlong": ("Debt", "Medium to Long Duration"),
    "longdur": ("Debt", "Long Duration"), "dynbond": ("Debt", "Dynamic Bond"), "corpbond": ("Debt", "Corporate Bond"),
    "credit": ("Debt", "Credit Risk"), "bankpsu": ("Debt", "Banking & PSU"), "gilt": ("Debt", "Gilt"),
    "gilt10": ("Debt", "Gilt 10Y Constant Maturity"), "floater": ("Debt", "Floater"),
    "target": ("Debt", "Target Maturity / Debt Index"), "debtfof": ("Debt", "Debt FoF"),
    "aggressive": ("Hybrid", "Aggressive Hybrid"), "balanced": ("Hybrid", "Balanced Hybrid"),
    "conservative": ("Hybrid", "Conservative Hybrid"), "baf": ("Hybrid", "Balanced Advantage / Dynamic"),
    "eqsavings": ("Hybrid", "Equity Savings"), "multiasset": ("Hybrid", "Multi Asset Allocation"),
    "arbitrage": ("Hybrid", "Arbitrage"), "hybridfof": ("Hybrid", "Hybrid FoF / Index"),
    "gold": ("Commodity", "Gold"), "silver": ("Commodity", "Silver"), "multicomm": ("Commodity", "Gold & Silver"),
    "us": ("Global", "US Equity"), "global": ("Global", "Global / Developed"), "asia": ("Global", "Asia & Emerging"),
    "globaldebt": ("Global", "International Bonds"),
    "idx_large": ("Index", "Large Cap Index"), "idx_midsmall": ("Index", "Mid & Small Cap Index"),
    "idx_broad": ("Index", "Broad Market Index"), "idx_factor": ("Index", "Smart Beta / Factor"),
    "idx_bank": ("Index", "Bank & Financial Index"), "idx_tech": ("Index", "IT & Digital Index"),
    "idx_infra": ("Index", "Infra, Defence, Auto & Realty Index"), "idx_theme": ("Index", "Other Sectoral / Thematic Index"),
    "retire": ("Solution", "Retirement"), "child": ("Solution", "Children's"), "lifecycle": ("Solution", "Life Cycle"),
}

# ratings and scorecards rank a fund against this wider group (themes alone are too small for percentiles)
GROUP = {k: ("sector" if k.startswith("sec_") else "idx_sector" if k in ("idx_bank", "idx_tech", "idx_infra", "idx_theme") else k)
         for k in SUBS}


def group(sub: str) -> str:
    return GROUP.get(sub, sub)


SEC_THEMES = [  # first match wins
    ("sec_bank", r"bank|financ|bfsi"),
    ("sec_pharma", r"pharma|health"),
    ("sec_tech", r"technolog|digital|\bteck\b|\bit\b|internet"),
    ("sec_consumption", r"consum|fmcg|rural"),
    ("sec_infra", r"infra|power|build india|t\.?i\.?g\.?e\.?r|reform|housing|transport|logistic|defence"),
    ("sec_mfg", r"manufactur|automotive|export"),
    ("sec_energy", r"energy|resource|commodit|\bcomma\b"),
    ("sec_psu", r"\bpsu\b|cpse"),
    ("sec_mnc", r"\bmnc\b|conglomerate|business group"),
    ("sec_quant", r"quant|momentum|quality|multi.?factor|minimum variance|low vol"),
    ("sec_esg", r"\besg\b|ethical|shariah"),
    ("sec_cycle", r"business cycle|rotation|multi sector"),
    ("sec_innov", r"innovat|pioneer|\bipo\b|opportunit|special|services"),
]
IDX_THEMES = [
    ("idx_bank", r"bank|financ|capital market"),
    ("idx_tech", r"\bit\b|niftyit|information technology|digital|internet"),
    ("idx_infra", r"infra|defence|housing|realty|reit|railway|manufactur|\bauto\b|clean environment"),
]


def _theme(name: str, themes, default: str) -> str:
    for key, rx in themes:
        if re.search(rx, name, re.I):
            return key
    return default


# fund-house names that contain a country word ("Nippon India", "Franklin India" …) must not hide a global fund
RX_BRAND = re.compile(r"^(nippon india|invesco india|franklin india|bank of india|franklin|union|edelweiss)\s+", re.I)


_EQ = [
    (r"large\s*&\s*mid", "largemid"), (r"large cap", "large"), (r"mid cap", "mid"), (r"small cap", "small"),
    (r"multi cap", "multi"), (r"flexi cap", "flexi"), (r"focused", "focused"), (r"value", "value"),
    (r"contra", "contra"), (r"dividend yield", "divyield"), (r"elss", "elss"), (r"sectoral|thematic", "sector"),
]
_DEBT = [
    (r"overnight", "overnight"), (r"ultra short to short", "lowdur"), (r"ultra short", "ultrashort"),
    (r"low duration", "lowdur"), (r"money market", "money"), (r"medium to long", "medlong"),
    (r"short duration|short term", "shortdur"), (r"medium duration|medium term", "meddur"),
    (r"long duration|long term", "longdur"), (r"dynamic bond|dynamic term", "dynbond"),
    (r"corporate bond", "corpbond"), (r"credit risk", "credit"), (r"banking and psu|banking & psu", "bankpsu"),
    (r"10.year constant|constant maturity", "gilt10"), (r"gilt", "gilt"), (r"floater|floating", "floater"),
    (r"liquid", "liquid"), (r"sectoral", "bankpsu"),
]
_HYB = [
    (r"aggressive", "aggressive"), (r"balanced hybrid", "balanced"), (r"conservative", "conservative"),
    (r"balanced advantage|dynamic asset", "baf"), (r"equity savings", "eqsavings"),
    (r"multi asset", "multiasset"), (r"arbitrage", "arbitrage"),
]

RX_GLOBAL = re.compile(
    r"\b(us|u\.s\.|usa|nasdaq|s&p ?500|nyse|fang|america|american|global|international|world|overseas|"
    r"developed|europe|european|japan|china|chinese|taiwan|hang ?seng|asia|asian|asean|emerging|brazil|korea|"
    r"greater china|feeder|offshore|msci)\b", re.I)
RX_US = re.compile(r"\b(us|u\.s\.|usa|nasdaq|s&p ?500|nyse|fang|america|american)\b", re.I)
RX_ASIA = re.compile(r"\b(japan|china|chinese|taiwan|hang ?seng|asia|asian|asean|emerging|brazil|korea|greater china)\b", re.I)
RX_GOLD = re.compile(r"\bgold\b", re.I)
RX_SILVER = re.compile(r"\bsilver\b", re.I)
RX_PRECIOUS = re.compile(r"precious metal", re.I)
RX_DEBTNAME = re.compile(
    r"\b(sdl|g-?sec|gilt|crisil|ibx|bond|t-?bill|liquid|money market|corporate|aaa|debt|psu|bharat bond|"
    r"target maturity|income|treasury|state development|g sec|government securities|nifty .*index .*20\d\d|apr 20\d\d|"
    r"20[2-4]\d index)\b", re.I)
# debt words that never appear in equity index names ("PSU" alone does: PSU Bank, Railways PSU)
RX_DEBT_STRICT = re.compile(
    r"\b(sdl|g-?sec|gilt|crisil|ibx|bond|t-?bill|liquid|money market|corporate|aaa|debt|bharat bond|target maturity|"
    r"treasury|state development|g sec|government securities|20[2-4]\d)\b", re.I)
RX_HYBNAME = re.compile(r"multi.?asset|asset allocat|hybrid|balanced|dynamic|allocator|equity savings|aggressive|"
                        r"conservative|arbitrage|life ?cycle|retirement", re.I)
RX_FACTOR = re.compile(r"momentum|low vol|quality|value|alpha|equal weight|dividend|high beta|enhanced esg|"
                       r"size|smart beta|multi factor|factor", re.I)
RX_MIDSMALL = re.compile(r"mid ?cap|small ?cap|midsmall|micro ?cap|mid ?small", re.I)
RX_BROAD = re.compile(r"nifty ?500\b|total market|bse 500|nifty ?200\b|large ?mid ?cap|largemidcap|multi ?cap|"
                      r"flexi ?cap|bse allcap|all ?cap|nifty india 500|bse 250|bse ?1000|nifty ?1000|nifty total", re.I)
RX_LARGE = re.compile(r"nifty ?50\b|sensex|nifty ?100\b|bse ?100\b|top 100|large ?cap|next ?50\b|bse ?50\b|"
                      r"nifty next|bse ?sensex next|\bnifty index fund", re.I)


def _match(rules, s):
    for rx, key in rules:
        if re.search(rx, s, re.I):
            return key
    return None


def _commodity_sub(name):
    g, s = bool(RX_GOLD.search(name)), bool(RX_SILVER.search(name))
    if RX_PRECIOUS.search(name) or (g and s):
        return "multicomm"
    return "silver" if s else "gold"


RX_GDEBT = re.compile(r"treasury|\bbond|\bdebt\b|fixed income", re.I)
RX_DOMESTIC = re.compile(r"\bdomestic\b|india (consumption|opportunit)", re.I)


def _global_sub(name):
    if RX_GDEBT.search(name):
        return "globaldebt"
    if RX_US.search(name):
        return "us"
    if RX_ASIA.search(name):
        return "asia"
    return "global"


def _index_sub(name):
    if RX_FACTOR.search(name):
        return "idx_factor"
    if RX_MIDSMALL.search(name) and not re.search(r"large ?mid|largemid", name, re.I):
        return "idx_midsmall"
    if RX_BROAD.search(name):
        return "idx_broad"
    if RX_LARGE.search(name):
        return "idx_large"
    return _theme(name, IDX_THEMES, "idx_theme")


def classify(name: str, cat: str) -> str | None:
    """AMFI category + scheme name → sub-category key (see SUBS)."""
    inner = cat.split("(", 1)[1].rsplit(")", 1)[0] if "(" in cat else cat
    low = inner.lower()
    n = name

    if low.startswith(("children", "solution")):
        if "retire" in low:
            return "retire"
        return "child"
    if low.startswith("life cycle"):
        return "lifecycle"
    if re.search(r"overseas|investing overseas|fof overseas", low):
        return _global_sub(n)
    if re.search(r"fund of funds scheme \(domestic\)|fof domestic", low):
        if RX_GLOBAL.search(n) and not RX_DOMESTIC.search(n):
            return _global_sub(n)
        if RX_GOLD.search(n) or RX_SILVER.search(n) or RX_PRECIOUS.search(n):
            return _commodity_sub(n)
        if RX_HYBNAME.search(n):
            return "hybridfof"
        if RX_DEBT_STRICT.search(n):
            return "target" if re.search(r"ibx|sdl|g-?sec|gilt|bharat bond|target|20[2-4]\d|crisil", n, re.I) else "debtfof"
        return "eqfof"
    if "index fund" in low:
        if RX_GLOBAL.search(n) and not RX_DOMESTIC.search(n):
            return _global_sub(n)
        if RX_GOLD.search(n) or RX_SILVER.search(n):
            return _commodity_sub(n)
        if "debt" in low or RX_DEBT_STRICT.search(n):
            if not re.search(r"nifty ?50\b|sensex|midcap|smallcap|momentum|quality", n, re.I) or "debt" in low:
                return "target"
        if "hybrid" in low or RX_HYBNAME.search(n):
            return "hybridfof"
        return _index_sub(n)
    if low.startswith("equity"):
        key = _match(_EQ, low)
        if key == "sector":
            core = RX_BRAND.sub("", n)
            if RX_GLOBAL.search(core) and not re.search(r"india|bharat", core, re.I):
                return _global_sub(core)
            return _theme(core, SEC_THEMES, "sec_other")
        return key
    if low.startswith(("debt", "income/debt")):
        return _match(_DEBT, low)
    if low.startswith("hybrid"):
        return _match(_HYB, low)
    # legacy open-ended buckets ("Growth", "Income", "Gilt")
    if low in ("gilt",):
        return "gilt"
    if low in ("growth",):
        if RX_GLOBAL.search(n):
            return _global_sub(n)
        return "flexi" if not RX_MIDSMALL.search(n) else ("small" if re.search("small", n, re.I) else "mid")
    if low in ("income",):
        return "liquid" if re.search("liquid", n, re.I) else ("shortdur" if re.search("short", n, re.I) else "dynbond")
    return None


# ═════════════════════════════════ NAMES ═══════════════════════════════════
_ACRO = {"sbi", "hdfc", "icici", "uti", "dsp", "lic", "iti", "psu", "elss", "etf", "bse", "s&p", "us", "idfc", "pgim",
         "hsbc", "jm", "nj", "mf", "fof", "sdl", "crisil", "ibx", "aaa", "nasdaq", "esg", "it", "mnc", "cpse", "g-sec",
         "tri", "bnp", "absl", "sip", "ii", "iii", "iv", "nyse", "fang", "msci", "pse", "gsec", "bfsi", "ev", "ai", "nfo"}
_LOWER = {"of", "and", "the", "to", "in", "for", "with", "&"}


def nice_name(name: str) -> str:
    """Normalise ALL-CAPS AMFI names; strip plan/option noise."""
    n = re.sub(r"\s*[-–]\s*(direct( plan)?|growth( option| plan)?|regular( plan)?)\b.*$", "", name, flags=re.I)
    n = re.sub(r"\(\s*erstwhile[^)]*\)", "", n, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip(" -")
    letters = [c for c in n if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        out = []
        for i, w in enumerate(n.split(" ")):
            lw = w.lower()
            if lw in _ACRO or re.fullmatch(r"[a-z]{1,2}\d+|\d+[a-z]*", lw):
                out.append("FoF" if lw == "fof" else ("S&P" if lw == "s&p" else w.upper()))
            elif lw == "nifty":
                out.append("Nifty")
            elif i and lw in _LOWER:
                out.append(lw)
            else:
                out.append(lw[:1].upper() + lw[1:])
        n = " ".join(out)
    n = re.sub(r"\bNIFTY\b", "Nifty", n)
    n = re.sub(r"\bFOF\b|\bFund of Fund\b(?!s)", "FoF", n)
    return n


def amc_short(amc: str) -> str:
    s = re.sub(r"\s*Mutual Fund\s*$", "", amc, flags=re.I).strip()
    return s


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ═════════════════════════════════ DATES ═══════════════════════════════════
def shift_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def month_end(y: int, m: int) -> date:
    return date(y, m, monthrange(y, m)[1])


def shift_months_np(ords: np.ndarray, months: int) -> np.ndarray:
    """Vectorised shift_months on an array of date ordinals."""
    base = np.datetime64("0001-01-01")
    dt = base + (ords - 1).astype("timedelta64[D]")
    mon = dt.astype("datetime64[M]")
    day = (dt - mon.astype("datetime64[D]")).astype(int)  # 0-based day of month
    tgt_mon = mon + np.timedelta64(months, "M")
    nxt = tgt_mon + np.timedelta64(1, "M")
    mlen = (nxt.astype("datetime64[D]") - tgt_mon.astype("datetime64[D]")).astype(int)
    tgt = tgt_mon.astype("datetime64[D]") + np.minimum(day, mlen - 1).astype("timedelta64[D]")
    return (tgt - base).astype(int) + 1


# ═══════════════════════════════ ANALYTICS ═════════════════════════════════
BASE_TOL_DAYS = 10   # a base NAV must lie within this many days of the target date

TRAILING = [("1w", "d", 7), ("1m", "m", 1), ("3m", "m", 3), ("6m", "m", 6), ("1y", "m", 12),
            ("2y", "m", 24), ("3y", "m", 36), ("5y", "m", 60), ("7y", "m", 84), ("10y", "m", 120)]


class Series:
    """Daily NAV series: sorted ordinals d, values v."""

    def __init__(self, pts):
        pts = sorted(pts)
        self.d = np.array([p[0] for p in pts], dtype=np.int64)
        self.v = np.array([p[1] for p in pts], dtype=float)

    def __len__(self):
        return len(self.d)

    def upto(self, ordinal):
        i = int(np.searchsorted(self.d, ordinal, side="right"))
        s = Series([])
        s.d, s.v = self.d[:i], self.v[:i]
        return s

    def idx_on_or_before(self, t):
        return int(np.searchsorted(self.d, t, side="right")) - 1

    def idx_on_or_after(self, t):
        return int(np.searchsorted(self.d, t, side="left"))

    def base_idx(self, t):
        """Index of the NAV on/before target t, or -1 when unavailable (before launch / data hole)."""
        if not len(self.d) or t < self.d[0]:
            return -1
        i = self.idx_on_or_before(t)
        if i < 0 or t - self.d[i] > BASE_TOL_DAYS:
            return -1
        return i


def pct(x):
    return None if x is None or not math.isfinite(x) else round(x * 100, 4)


def trailing_returns(s: Series) -> dict:
    out = {}
    if len(s) < 2:
        return out
    end_d, end_v = int(s.d[-1]), float(s.v[-1])
    end_date = date.fromordinal(end_d)
    out["1d"] = pct(end_v / s.v[-2] - 1)
    for key, kind, n in TRAILING:
        t = end_d - n if kind == "d" else shift_months(end_date, -n).toordinal()
        i = s.base_idx(t)
        if i < 0:
            out[key] = None
            continue
        r = end_v / s.v[i]
        out[key] = pct(r - 1 if (kind == "d" or n <= 12) else r ** (12.0 / n) - 1)
    # YTD
    t = date(end_date.year - 1, 12, 31).toordinal()
    i = s.base_idx(t)
    out["ytd"] = pct(end_v / s.v[i] - 1) if i >= 0 else None
    # since inception (first available NAV of the Direct plan)
    days = end_d - int(s.d[0])
    r = end_v / s.v[0]
    out["si"] = pct((r ** (365.0 / days) - 1) if days >= 365 else r - 1) if days > 0 else None
    return out


def calendar_returns(s: Series, years: list[int]) -> dict:
    out = {}
    end_date = date.fromordinal(int(s.d[-1]))
    for y in years:
        b = s.base_idx(date(y - 1, 12, 31).toordinal())
        if b < 0:
            continue
        if y == end_date.year:
            continue
        e = s.base_idx(date(y, 12, 31).toordinal())
        if e < 0:
            continue
        out[str(y)] = pct(s.v[e] / s.v[b] - 1)
    return out


def xirr(flows: list[tuple[int, float]]) -> float | None:
    """flows: [(ordinal, amount)] (negative = invested). Actual/365."""
    if not flows:
        return None
    t0 = flows[0][0]
    ts = np.array([(f[0] - t0) / 365.0 for f in flows])
    cf = np.array([f[1] for f in flows])

    def npv(r):
        return float(np.sum(cf / (1 + r) ** ts))

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7:
            break
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


SIP_AMT = 10000.0


def sip_returns(s: Series, months: int) -> dict | None:
    end_d = int(s.d[-1])
    end_date = date.fromordinal(end_d)
    flows, units = [], 0.0
    for k in range(months, 0, -1):
        t = shift_months(end_date, -k).toordinal()
        if t < s.d[0]:
            return None
        i = s.idx_on_or_after(t)
        if i >= len(s.d) or s.d[i] - t > BASE_TOL_DAYS or s.d[i] >= end_d:
            return None
        units += SIP_AMT / s.v[i]
        flows.append((int(s.d[i]), -SIP_AMT))
    value = units * float(s.v[-1])
    flows.append((end_d, value))
    r = xirr(flows)
    return {"inv": round(SIP_AMT * months, 2), "val": round(value, 2), "xirr": pct(r)}


ROLL_BUCKETS = {
    "growth": [0, 8, 12, 15, 20],     # equity-like: <0, 0-8, 8-12, 12-15, 15-20, >20
    "income": [4, 6, 7, 8, 9],        # debt-like:   <4, 4-6, 6-7, 7-8, 8-9, >9
}


def rolling_series(s: Series, years: int):
    """Return (end ordinals, CAGR array) for every trading day with a full window."""
    tgt = shift_months_np(s.d, -12 * years)
    idx = np.searchsorted(s.d, tgt, side="right") - 1
    ok = (tgt >= s.d[0]) & (idx >= 0)
    idx = np.where(ok, idx, 0)
    ok &= (tgt - s.d[idx]) <= BASE_TOL_DAYS
    r = (s.v / s.v[idx]) ** (1.0 / years) - 1
    return s.d[ok], r[ok]


def rolling_stats(s: Series, years: int, bench: Series | None, buckets: list[float]) -> dict | None:
    ends, r = rolling_series(s, years)
    if len(r) < 20:
        return None
    o = {
        "n": int(len(r)), "avg": pct(float(np.mean(r))), "med": pct(float(np.median(r))),
        "min": pct(float(np.min(r))), "max": pct(float(np.max(r))),
        "minD": date.fromordinal(int(ends[int(np.argmin(r))])).isoformat(),
        "maxD": date.fromordinal(int(ends[int(np.argmax(r))])).isoformat(),
        "pos": round(float(np.mean(r > 0)) * 100, 2),
    }
    edges = [-np.inf] + [b / 100 for b in buckets] + [np.inf]
    hist, _ = np.histogram(r, bins=edges)
    o["dist"] = [round(float(h) / len(r) * 100, 2) for h in hist]
    if bench is not None and len(bench) > 20:
        bends, br = rolling_series(bench, years)
        common, ia, ib = np.intersect1d(ends, bends, return_indices=True)
        if len(common) >= 20:
            o["beat"] = round(float(np.mean(r[ia] > br[ib])) * 100, 2)
            o["beatN"] = int(len(common))
    return o


def month_end_values(s: Series, ends: list[date]) -> np.ndarray:
    out = np.full(len(ends), np.nan)
    for k, me in enumerate(ends):
        i = s.base_idx(me.toordinal())
        if i >= 0:
            out[k] = s.v[i]
    return out


def max_drawdown(s: Series, start_ord: int, end_ord: int) -> dict | None:
    a = int(np.searchsorted(s.d, start_ord, side="left"))
    b = int(np.searchsorted(s.d, end_ord, side="right"))
    if b - a < 5:
        return None
    v = s.v[a:b]
    peak = np.maximum.accumulate(v)
    dd = v / peak - 1
    t = int(np.argmin(dd))
    p = int(np.argmax(v[: t + 1]))
    o = {"mdd": pct(float(dd[t])), "peak": date.fromordinal(int(s.d[a + p])).isoformat(),
         "trough": date.fromordinal(int(s.d[a + t])).isoformat(), "rec": None, "recDays": None}
    if dd[t] < 0:
        later = np.nonzero(s.v[a + t:] >= v[p])[0]
        if len(later):
            rd = int(s.d[a + t + int(later[0])])
            o["rec"] = date.fromordinal(rd).isoformat()
            o["recDays"] = rd - int(s.d[a + t])
    return o


def _geo_mean(x):
    return float(np.prod(1 + x) ** (1.0 / len(x)) - 1)


def risk_metrics(s: Series, ends: list[date], rf_vals: np.ndarray, bench_vals: np.ndarray | None,
                 with_alpha: bool) -> dict | None:
    """ends: month-ends oldest→newest (len 37 for 36 returns). rf_vals/bench_vals: values at those ends."""
    fv = month_end_values(s, ends)
    # use the longest run of trailing months that are all available (≥ 12 returns)
    k = len(fv) - 1
    while k > 0 and np.isfinite(fv[k - 1]) and np.isfinite(rf_vals[k - 1]):
        k -= 1
    fv, rv = fv[k:], rf_vals[k:]
    n = len(fv) - 1
    if n < 12 or not np.isfinite(fv[-1]):
        return None
    f = fv[1:] / fv[:-1] - 1
    rf = rv[1:] / rv[:-1] - 1
    ex = f - rf
    sd = float(np.std(f, ddof=1))
    sde = float(np.std(ex, ddof=1))
    o = {"months": n, "from": ends[k].isoformat(), "to": ends[-1].isoformat(),
         "ret": pct(float(np.prod(1 + f)) ** (12.0 / n) - 1),
         "std": pct(sd * math.sqrt(12)),
         "sharpe": round(float(np.mean(ex)) / sde * math.sqrt(12), 4) if sde > 0 else None}
    dd = math.sqrt(float(np.mean(np.minimum(ex, 0) ** 2)))
    o["sortino"] = round(float(np.mean(ex)) * 12 / (dd * math.sqrt(12)), 4) if dd > 0 else None
    o["rf"] = pct(float(np.prod(1 + rf)) ** (12.0 / n) - 1)
    if bench_vals is not None:
        bv_all = bench_vals[k:]
        kb = len(bv_all) - 1
        while kb > 0 and np.isfinite(bv_all[kb - 1]):
            kb -= 1
        if np.isfinite(bv_all[-1]) and len(bv_all) - 1 - kb >= 12:
            bv = bv_all[kb:]
            fb, rfb = f[kb:], rf[kb:]
            exf = fb - rfb
            b = bv[1:] / bv[:-1] - 1
            exb = b - rfb
            vb = float(np.var(exb, ddof=1))
            if vb > 0:
                nb = len(b)
                beta = float(np.cov(exf, exb, ddof=1)[0, 1]) / vb
                o["bMonths"] = nb
                o["beta"] = round(beta, 4)
                c = float(np.corrcoef(exf, exb)[0, 1])
                o["r2"] = round(c * c * 100, 2)
                o["bret"] = pct(float(np.prod(1 + b)) ** (12.0 / nb) - 1)
                if with_alpha:
                    o["alpha"] = pct((float(np.mean(exf)) - beta * float(np.mean(exb))) * 12)
                    d = fb - b
                    te = float(np.std(d, ddof=1)) * math.sqrt(12)
                    o["te"] = pct(te)
                    o["ir"] = round(float(np.mean(d)) * 12 / te, 4) if te > 0 else None
                    up, dn = b > 0, b < 0
                    if up.sum() >= 3:
                        o["upCap"] = round(_geo_mean(fb[up]) / _geo_mean(b[up]) * 100, 2)
                    if dn.sum() >= 3:
                        o["downCap"] = round(_geo_mean(fb[dn]) / _geo_mean(b[dn]) * 100, 2)
    return o


# ═══════════════════════════════ FACTOR DNA ════════════════════════════════
FACTOR_KEYS = ["core", "mid", "small", "mom", "val", "qual", "lowvol", "us", "cash"]
STYLE_KEYS = ["mom", "val", "qual", "lowvol"]
STYLE_LABEL = {"mom": "Momentum", "val": "Value", "qual": "Quality", "lowvol": "Low Volatility"}


def weekly_points(asof: date, weeks: int) -> list[int]:
    """Fridays (ordinals) oldest→newest, the last one on/before asof."""
    d = asof.toordinal()
    while date.fromordinal(d).weekday() != 4:
        d -= 1
    return [d - 7 * k for k in range(weeks, -1, -1)]


def weekly_returns(s: Series, fridays: list[int]) -> np.ndarray:
    v = np.full(len(fridays), np.nan)
    for k, t in enumerate(fridays):
        i = s.base_idx(t)
        if i >= 0 and t - s.d[i] <= 6:
            v[k] = s.v[i]
    return v[1:] / v[:-1] - 1


def style_analysis(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, float] | None:
    """min ||y - Xw||²  s.t. w ≥ 0, Σw = 1  (Sharpe returns-based style analysis)."""
    from scipy.optimize import minimize
    k = X.shape[1]
    XtX, Xty = X.T @ X, X.T @ y

    def fun(w):
        r = y - X @ w
        return float(r @ r)

    def jac(w):
        return 2 * (XtX @ w - Xty)

    res = minimize(fun, np.full(k, 1.0 / k), jac=jac, method="SLSQP", bounds=[(0, 1)] * k,
                   constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1, "jac": lambda w: np.ones(k)}],
                   options={"maxiter": 500, "ftol": 1e-12})
    if not res.success and res.status not in (8, 9):
        return None
    w = np.clip(res.x, 0, None)
    w = w / w.sum()
    e = y - X @ w
    r2 = 1 - float(np.var(e)) / float(np.var(y)) if np.var(y) > 0 else 0.0
    return w, r2


def factor_label(w: dict, r2: float) -> dict:
    eq = sum(w[k] for k in FACTOR_KEYS if k not in ("us", "cash"))
    style = {k: w[k] for k in STYLE_KEYS}
    top = max(style, key=style.get)
    if r2 < 0.6:
        primary = "Blend"
    elif style[top] >= 0.30:
        primary = STYLE_LABEL[top]
    elif w["core"] >= 0.70:
        primary = "Market"
    else:
        primary = "Blend"
    secondary = [STYLE_LABEL[k] for k in sorted(style, key=style.get, reverse=True)
                 if k != top and style[k] >= 0.20 and r2 >= 0.6]
    ms = w["mid"] + w["small"]
    if eq <= 0:
        size = None
    elif ms / eq < 0.30:
        size = "Large"
    elif ms / eq >= 0.60:
        size = "Small" if w["small"] >= w["mid"] else "Mid"
    else:
        size = "Multi"
    return {"primary": primary, "secondary": secondary[:2], "size": size}


# ═════════════════════════════════ RATING ══════════════════════════════════
def percentile_ranks(vals: list[float | None], higher_better=True) -> list[float | None]:
    idx = [i for i, v in enumerate(vals) if v is not None]
    out = [None] * len(vals)
    if len(idx) < 2:
        for i in idx:
            out[i] = 0.5
        return out
    xs = sorted(vals[i] for i in idx)
    for i in idx:
        v = vals[i]
        lt = sum(1 for x in xs if x < v)
        eq = sum(1 for x in xs if x == v)
        p = (lt + (eq - 1) / 2) / (len(xs) - 1)
        out[i] = p if higher_better else 1 - p
    return out


def stars_from_scores(scores: list[float | None]) -> list[int | None]:
    """Morningstar-style bell distribution: 10% / 22.5% / 35% / 22.5% / 10%."""
    pr = percentile_ranks(scores)
    out = []
    for p in pr:
        if p is None:
            out.append(None)
        elif p >= 0.90:
            out.append(5)
        elif p >= 0.675:
            out.append(4)
        elif p >= 0.325:
            out.append(3)
        elif p >= 0.10:
            out.append(2)
        else:
            out.append(1)
    return out


def iso(o: int) -> str:
    return date.fromordinal(int(o)).isoformat()


def today_ist() -> datetime:
    from datetime import timedelta, timezone
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


# ═════════════════════════════ SCORECARD ═══════════════════════════════════
STATUS = ["In form", "On track", "Underperforming", "Out of track"]


def status_of(rec: float | None, ltp: float | None) -> str | None:
    """Recency score (0-100) and long-term percentile (0-100) → status label.
    In form: recent performance in the top 30% of the category.
    On track: recent performance mid-pack (40th–70th percentile).
    Underperforming: recent performance in the bottom 40% but long-term record in the top half.
    Out of track: both recent and long-term performance in the bottom half / bottom 40%."""
    if rec is None:
        return None
    if rec >= 70:
        return "In form"
    if rec >= 40:
        return "On track"
    if ltp is not None and ltp >= 50:
        return "Underperforming"
    return "Out of track"


def scorecard(group: list[dict]) -> dict:
    """group: funds of one sub-category, each {code, tr:{3m,6m,1y,3y}, roll12: [1Y return at each of the last
    36 month-ends or None], std}. Returns code → {rec, cons, consTop, consN, vol, ltp, status}."""
    out = {c["code"]: {} for c in group}
    if len(group) < 5:
        return out
    # recency: weighted percentile of 3M / 6M / 1Y returns
    p3 = percentile_ranks([g["tr"].get("3m") if g["tr"].get("1y") is not None else None for g in group])
    p6 = percentile_ranks([g["tr"].get("6m") if g["tr"].get("1y") is not None else None for g in group])
    p12 = percentile_ranks([g["tr"].get("1y") for g in group])
    for i, g in enumerate(group):
        if p12[i] is not None and p3[i] is not None and p6[i] is not None:
            out[g["code"]]["rec"] = round((0.2 * p3[i] + 0.3 * p6[i] + 0.5 * p12[i]) * 100, 1)
    # long-term percentile: 3Y return where available, else 1Y
    l3 = percentile_ranks([g["tr"].get("3y") for g in group])
    for i, g in enumerate(group):
        v = l3[i] if l3[i] is not None else p12[i]
        if v is not None:
            out[g["code"]]["ltp"] = round(v * 100, 1)
    # consistency: share of month-ends in the top half of the category on rolling 1-year return
    months = max((len(g["roll12"]) for g in group), default=0)
    top = {g["code"]: 0 for g in group}
    seen = {g["code"]: 0 for g in group}
    for k in range(months):
        vals = [(g["code"], g["roll12"][k]) for g in group if k < len(g["roll12"]) and g["roll12"][k] is not None]
        if len(vals) < 4:
            continue
        vals.sort(key=lambda x: -x[1])
        half = (len(vals) + 1) // 2
        for rank, (code, _) in enumerate(vals):
            seen[code] += 1
            if rank < half:
                top[code] += 1
    for g in group:
        if seen[g["code"]] >= 12:
            o = out[g["code"]]
            o["cons"] = round(top[g["code"]] / seen[g["code"]] * 100, 1)
            o["consTop"], o["consN"] = top[g["code"]], seen[g["code"]]
    # volatility score: 100 = calmest in category (3Y std dev, lower is better)
    pv = percentile_ranks([g.get("std") for g in group], higher_better=False)
    for i, g in enumerate(group):
        if pv[i] is not None:
            out[g["code"]]["vol"] = round(pv[i] * 100, 1)
    for g in group:
        o = out[g["code"]]
        o["status"] = status_of(o.get("rec"), o.get("ltp"))
    return out
