#!/usr/bin/env python3
"""Market & rates inputs for the Smart SIP planner → data/mf/macro.json (+ data/mf/val_hist.json).

* Interest rates — the central bank's national summary data: policy repo rate, call money, 91/182/364-day
  T-bill yields and the 10-year government bond par yield, each with the year-ago value and the last few weeks
  (so the direction of rates is known, not just the level). The central bank's home page is the fallback for
  the policy rate and T-bills. Every reading is appended to a small history kept in macro.json.
* Valuations — the exchange's daily index-close file carries P/E, P/B and dividend yield for every index.
  val_hist.json keeps one reading per month-end for ~30 indices going back to 2016 (bootstrapped once, then the
  latest month is refreshed each run), so each index's valuation can be ranked against its own 10-year history.

* Global markets — two years of daily closes for the US dollar index, US 10-year / 5-year / 3-month yields,
  emerging-market and US equities, the Nifty 50, USD/INR, gold, silver, copper, Brent and WTI crude, the US
  volatility index and US inflation-linked vs regular Treasury bond funds (a market measure of inflation
  expectations). Each series is summarised as level, 3/6/12-month change, distance from its 200-day average and
  its 2-year percentile; the planner turns these into signals for equities, debt and precious metals.

Run daily before build_smart_sip.py. Missing sources never fail the build — the previous file is kept.
"""
from __future__ import annotations

import json
import logging
import re
import statistics as st
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MF = ROOT / "data" / "mf"
OUT = MF / "macro.json"
HIST = MF / "val_hist.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
log = logging.getLogger("macro")

# index name in the daily close file → short key used by the planner
INDICES = {
    "Nifty 50": "n50", "Nifty Next 50": "nn50", "Nifty 500": "n500", "Nifty Midcap 150": "mid150", "Nifty Smallcap 250": "sml250",
    "Nifty Bank": "bank", "Nifty Financial Services": "fin", "Nifty Private Bank": "pvtbank", "Nifty PSU Bank": "psubank",
    "Nifty IT": "it", "Nifty Pharma": "pharma", "Nifty Healthcare Index": "health", "Nifty FMCG": "fmcg",
    "Nifty India Consumption": "consumption", "Nifty Auto": "auto", "Nifty Infrastructure": "infra",
    "Nifty Realty": "realty", "Nifty Energy": "energy", "Nifty Oil & Gas": "oilgas", "Nifty PSE": "pse",
    "Nifty CPSE": "cpse", "Nifty MNC": "mnc", "Nifty Commodities": "commodities", "Nifty Metal": "metal",
    "Nifty India Manufacturing": "mfg", "Nifty India Defence": "defence", "Nifty Media": "media",
    "Nifty Services Sector": "services", "Nifty Housing": "housing", "Nifty Transportation & Logistics": "transport",
    "Nifty India Digital": "digital", "Nifty Capital Markets": "capmkt", "Nifty Financial Services Ex-Bank": "finexbank",
    "Nifty MidSmall IT & Telecom": "msit", "Nifty Chemicals": "chemicals", "Nifty Textile": "textile",
    # further sector and sub-sector indices (published today)
    "Nifty MidSmall Financial Services": "msfin", "Nifty MidSmall Healthcare": "mshealth",
    "Nifty MidSmall India Consumption": "mscons", "Nifty Consumer Durables": "durables", "Nifty Cement": "cement",
    "Nifty REITs & Realty": "reitrealty", "Nifty REITs & InvITs": "reits", "Nifty EV & New Age Automotive": "ev",
    "Nifty Mobility": "mobility", "Nifty India Tourism": "tourism", "Nifty India Internet": "internet",
    "Nifty India Railways PSU": "railpsu", "Nifty Rural": "rural", "Nifty India New Age Consumption": "newcons",
    "Nifty Non-Cyclical Consumer": "noncyc", "Nifty India Infrastructure & Logistics": "infralog",
    "Nifty Conglomerate 50": "conglo", "Nifty Core Housing": "corehousing",
    # sector indices not in the daily file yet — picked up automatically once published
    "Nifty Telecommunications": "telecom", "Nifty Capital Goods": "capgoods", "Nifty Construction": "construction",
    "Nifty Consumer Services": "conssvc", "Nifty Retail": "retail", "Nifty Hospitals": "hospitals",
    "Nifty Power": "power", "Nifty Sugar & Ethanol": "sugar", "Nifty NBFC": "nbfc", "Nifty Housing Finance": "hfc",
    "Nifty Insurance": "insurance", "Nifty Small Finance Banks & MFIs": "sfb",
    "Nifty Commercial & Transport Services": "commsvc",
}
# alternative spellings used by the exchange over the years (matched after normalising case and punctuation)
ALIASES = {
    "capmkt": ["Nifty Capital Market", "Nifty Capital Markets Index"],
    "finexbank": ["Nifty Financial Services Ex Bank", "Nifty Financial Services ex-Bank Index", "Nifty Fin Services Ex-Bank"],
    "msit": ["Nifty MidSmall IT and Telecom", "Nifty Midsmall IT & Telecom Index"],
    "chemicals": ["Nifty Chemical", "Nifty Chemicals Index", "Nifty India Chemicals"],
    "textile": ["Nifty Textiles", "Nifty India Textile", "Nifty India Textiles", "Nifty Textile Index"],
    "defence": ["Nifty Defence", "Nifty India Defence Index"],
    "transport": ["Nifty Transportation and Logistics", "Nifty India Transportation & Logistics"],
    "oilgas": ["Nifty Oil and Gas", "Nifty Oil & Gas Index"],
    "commodities": ["Nifty Commodity"], "health": ["Nifty Healthcare"], "mfg": ["Nifty Manufacturing"],
    "telecom": ["Nifty Telecom", "Nifty India Telecom", "Nifty Telecommunication"], "capgoods": ["Nifty India Capital Goods"],
    "durables": ["Nifty Consumer Durable"], "reits": ["Nifty REITs and InvITs Index"], "ev": ["Nifty EV and New Age Automotive"],
    "tourism": ["Nifty Tourism"], "internet": ["Nifty Internet"], "railpsu": ["Nifty India Railway PSU", "Nifty Railways PSU"],
    "sugar": ["Nifty Sugar and Ethanol"], "sfb": ["Nifty Small Finance Banks and MFIs", "Nifty SFB & MFI"],
    "nbfc": ["Nifty India NBFC"], "insurance": ["Nifty India Insurance"], "power": ["Nifty India Power", "Nifty Power Index"],
    "commsvc": ["Nifty Commercial and Transport Services"], "conssvc": ["Nifty India Consumer Services"],
}


def norm_name(n: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", n.lower().replace("&", "and"))


NAME_KEY = {norm_name(k): v for k, v in INDICES.items()}
for _k, _names in ALIASES.items():
    for _n in _names:
        NAME_KEY.setdefault(norm_name(_n), _k)
SEEN_NAMES: set = set()
START_MONTH = (2016, 1)


def num(x):
    try:
        v = float(str(x).replace(",", "").strip())
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:  # noqa: BLE001
        return default


# ─────────────────────────────── rates ───────────────────────────────
RATE_ROWS = {
    "repo": r"^Policy Repo Rate", "call": r"^Call Money Rate", "tb91": r"^91-Day Treasury Bill",
    "tb182": r"^182-Day Treasury Bill", "tb364": r"^364-Day Treasury Bill", "g10": r"^10-Year G-Sec Par Yield",
}


def fetch_rates(S) -> dict:
    out = {}
    try:
        t = S.get("https://www.rbi.org.in/Scripts/BS_NSDPDisplay.aspx?param=4", timeout=60).text
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S | re.I):
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
            if not cells:
                continue
            for k, rx in RATE_ROWS.items():
                if k not in out and re.search(rx, cells[0], re.I):
                    vals = [num(c) for c in cells[1:]]
                    vals = [v for v in vals if v is not None and 0 < v < 25]
                    if len(vals) >= 2:
                        out[k] = {"yearAgo": vals[0], "weeks": vals[1:], "last": vals[-1]}
        log.info("Rates (national summary): %s", {k: v["last"] for k, v in out.items()})
    except Exception as e:  # noqa: BLE001
        log.warning("national summary unavailable: %s", e)
    # The central bank's home page carries the rates in force today; the weekly summary lags policy decisions,
    # so the home page sets the current value and the summary supplies the history (year ago, recent weeks).
    try:
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", S.get("https://www.rbi.org.in/", timeout=60).text))
        for k, rx in (("repo", r"Policy Repo Rate\s*:\s*([\d.]+)"), ("tb91", r"91 day T-bills\s*:\s*([\d.]+)"),
                      ("tb182", r"182 day T-bills\s*:\s*([\d.]+)"), ("tb364", r"364 day T-bills\s*:\s*([\d.]+)")):
            m = re.search(rx, txt, re.I)
            if not m:
                continue
            cur = float(m.group(1))
            rec = out.setdefault(k, {"weeks": []})
            if rec.get("last") is not None and abs(rec["last"] - cur) > 1e-9:
                rec["summaryLast"] = rec["last"]
            rec["last"], rec["current"] = cur, True
        log.info("Rates in force (home page): %s", {k: v["last"] for k, v in out.items() if v.get("current")})
    except Exception as e:  # noqa: BLE001
        log.warning("central bank home page unavailable: %s", e)
    return out


# ─────────────────────────────── valuations ───────────────────────────────
def nse_session():
    s = requests.Session()
    s.headers.update({**UA, "Accept": "*/*", "Referer": "https://www.nseindia.com/"})
    try:
        s.get("https://www.nseindia.com", timeout=20)
    except Exception:  # noqa: BLE001
        pass
    return s


def close_file(s, d: date):
    try:
        r = s.get(f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv", timeout=40)
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200 or "Index Name" not in r.text[:200]:
        return None
    rows = {}
    lines = r.text.splitlines()
    hdr = [h.strip().lower() for h in lines[0].split(",")]
    try:
        i_n, i_c, i_pe, i_pb, i_dy = (hdr.index("index name"), next(i for i, h in enumerate(hdr) if h.startswith("closing")),
                                      hdr.index("p/e"), hdr.index("p/b"), hdr.index("div yield"))
    except (ValueError, StopIteration):
        return None
    for ln in lines[1:]:
        c = ln.split(",")
        if len(c) <= max(i_n, i_c, i_pe, i_pb, i_dy):
            continue
        SEEN_NAMES.add(c[i_n].strip())
        key = NAME_KEY.get(norm_name(c[i_n].strip()))
        if key:
            rows[key] = [num(c[i_pe]), num(c[i_pb]), num(c[i_dy]), num(c[i_c])]
    return rows or None


def month_last_file(s, y: int, m: int, not_after: date):
    """Close file for the last trading day of a month (walks back up to 8 days)."""
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    d = min(d, not_after)
    for _ in range(9):
        if d.weekday() < 5:
            rows = close_file(s, d)
            if rows:
                return d, rows
            time.sleep(0.4)
        d -= timedelta(days=1)
    return None, None


def update_history(s) -> dict:
    h = load(HIST, {"months": {}, "latest": None})
    months = h.setdefault("months", {})
    today = date.today()
    y, m = START_MONTH
    todo = []
    while (y, m) <= (today.year, today.month):
        key = f"{y}-{m:02d}"
        if key not in months:
            todo.append((y, m))
        y, m = (y + (m == 12), m % 12 + 1)
    s_ = time.time()
    got = 0
    keyset = sorted(set(INDICES.values()))
    if h.get("keys") != keyset:                 # new indices tracked → re-read each stored month-end file once
        refreshed = 0
        for mk, rec in list(months.items()):
            if time.time() - s_ > 420:
                break
            try:
                rows = close_file(s, date.fromisoformat(rec["d"]))
            except Exception:  # noqa: BLE001
                rows = None
            if rows:
                months[mk] = {"d": rec["d"], "v": rows}
                refreshed += 1
            time.sleep(0.2)
        if refreshed >= len(months) - 2:
            h["keys"] = keyset
        log.info("Valuation history: re-read %d/%d month-end files for newly tracked indices", refreshed, len(months))
    for y, m in todo:
        if (y, m) == (today.year, today.month) or time.time() - s_ > 600:
            continue
        d, rows = month_last_file(s, y, m, today - timedelta(days=1))
        if rows:
            months[f"{y}-{m:02d}"] = {"d": d.isoformat(), "v": rows}
            got += 1
        time.sleep(0.3)
    # latest session (refreshed every run)
    d = today
    for _ in range(8):
        d -= timedelta(days=1)
        if d.weekday() < 5:
            rows = close_file(s, d)
            if rows:
                h["latest"] = {"d": d.isoformat(), "v": rows}
                break
    h["months"] = dict(sorted(months.items()))
    latest_keys = set(((h.get("latest") or {}).get("v") or {}).keys())
    missing = sorted(set(INDICES.values()) - latest_keys)
    if missing:
        log.warning("Indices not found in the latest close file: %s · candidates: %s", missing,
                    sorted(n for n in SEEN_NAMES if re.search(r"textile|chemical|capital|ex.?bank|telecom|defen", n, re.I)))
    log.info("Valuation history: %d months (+%d this run), latest %s", len(h["months"]), got, (h.get("latest") or {}).get("d"))
    HIST.write_text(json.dumps(h, separators=(",", ":")))
    return h


def clean_hist(values: list) -> list:
    """Drop readings that are not comparable (e.g. a P/E of several hundred while a new index held loss-making
    companies): for indices with under 7 years of data, anything beyond 2.5× either side of the median of the
    latest 24 readings becomes None."""
    have = [v for v in values if v]
    recent = have[-24:]
    if len(recent) < 12 or len(have) >= 84:      # long-running indices keep their full history
        return values
    m = st.median(recent)
    return [v if v and m / 2.5 <= v <= m * 2.5 else None for v in values]


def pct_of(values: list[float], x: float) -> float | None:
    vals = sorted(v for v in values if v is not None and v > 0)
    if len(vals) < 24 or x is None:
        return None
    below = sum(1 for v in vals if v < x)
    equal = sum(1 for v in vals if v == x)
    return round((below + equal / 2) / len(vals), 3)


def valuation_table(h: dict) -> dict:
    latest = (h.get("latest") or {}).get("v") or {}
    months = h.get("months") or {}
    keys = list(months)
    out = {}
    for key in INDICES.values():
        cur = latest.get(key) or (months[keys[-1]]["v"].get(key) if keys else None)
        if not cur:
            continue
        pe_hist = clean_hist([months[k]["v"].get(key, [None])[0] for k in keys[-120:]])
        pb_hist = clean_hist([months[k]["v"].get(key, [None, None])[1] for k in keys[-120:]])
        closes = [(k, months[k]["v"].get(key, [None, None, None, None])[3]) for k in keys]
        closes = [(k, c) for k, c in closes if c]
        last_close = cur[3]

        def back(n):
            return closes[-1 - n][1] if len(closes) > n else None
        rec = {"pe": cur[0], "pb": cur[1], "dy": cur[2],
               "pePct": pct_of(pe_hist, cur[0]), "pbPct": pct_of(pb_hist, cur[1]),
               "peMed": round(st.median([v for v in pe_hist if v]), 2) if sum(1 for v in pe_hist if v) >= 24 else None,
               "pbMed": round(st.median([v for v in pb_hist if v]), 2) if sum(1 for v in pb_hist if v) >= 24 else None,
               "years": round(sum(1 for v in pe_hist if v) / 12, 1)}
        for n, lab in ((1, "r1m"), (3, "r3m"), (6, "r6m"), (12, "r12m")):
            b = back(n)
            rec[lab] = round((last_close / b - 1) * 100, 2) if b and last_close else None
        six = [c for _, c in closes[-6:]]
        rec["vs6m"] = round((last_close / (sum(six) / len(six)) - 1) * 100, 2) if len(six) == 6 and last_close else None
        out[key] = rec
    n50 = out.get("n50") or {}
    for k, r in out.items():                      # momentum relative to the Nifty 50
        for lab in ("r1m", "r3m", "r6m", "r12m"):
            if r.get(lab) is not None and n50.get(lab) is not None:
                r[lab + "Rel"] = round(r[lab] - n50[lab], 2)
    return out


# global market series: key → (chart symbol, label, kind) — kind "yield" = change in points, else in %
GLOBAL = {
    "dxy": ("DX-Y.NYB", "US dollar index", "level"), "us10y": ("^TNX", "US 10-year yield", "yield"),
    "us5y": ("^FVX", "US 5-year yield", "yield"), "us3m": ("^IRX", "US 3-month T-bill yield", "yield"),
    "em": ("EEM", "Emerging-market equities", "level"), "spx": ("^GSPC", "US equities (S&P 500)", "level"),
    "nifty": ("^NSEI", "Nifty 50", "level"), "usdinr": ("INR=X", "USD/INR", "level"),
    "gold": ("GC=F", "Gold (USD)", "level"), "silver": ("SI=F", "Silver (USD)", "level"),
    "copper": ("HG=F", "Copper", "level"), "brent": ("BZ=F", "Brent crude", "level"), "wti": ("CL=F", "WTI crude", "level"),
    "vix": ("^VIX", "US volatility index", "level"), "tip": ("TIP", "US inflation-linked Treasuries", "level"),
    "ief": ("IEF", "US 7-10 year Treasuries", "level"),
}


def fetch_global(S) -> dict:
    out = {}
    for key, (sym, label, kind) in GLOBAL.items():
        try:
            r = S.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(sym)}?interval=1d&range=2y", timeout=30)
            res = r.json()["chart"]["result"][0]
            ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
            pts = [(datetime.fromtimestamp(t, timezone.utc).date(), c) for t, c in zip(ts, cl) if c is not None]
        except Exception as e:  # noqa: BLE001
            log.warning("global series %s unavailable: %s", key, e)
            continue
        if len(pts) < 220:
            continue
        last_d, last = pts[-1]

        def ago(days):
            tgt = last_d - timedelta(days=days)
            return next((v for d, v in reversed(pts) if d <= tgt), None)

        def chg(days):
            v = ago(days)
            if v is None:
                return None
            return round(last - v, 3) if kind == "yield" else round((last / v - 1) * 100, 2)
        ma200 = sum(v for _, v in pts[-200:]) / 200
        vals = [v for _, v in pts]
        out[key] = {"label": label, "kind": kind, "d": last_d.isoformat(), "last": round(last, 4),
                    "c1m": chg(30), "c3m": chg(91), "c6m": chg(182), "c12m": chg(365),
                    "vs200": round(last - ma200, 3) if kind == "yield" else round((last / ma200 - 1) * 100, 2),
                    "pct2y": round(sum(1 for v in vals if v < last) / len(vals), 3),
                    "w": [round(v, 4) for _, v in pts[-260::5]]}            # weekly sample for sparklines
        time.sleep(0.3)
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    S = requests.Session()
    S.headers.update(UA)
    prev = load(OUT, {})
    rates = fetch_rates(S) or prev.get("rates", {})
    try:
        h = update_history(nse_session())
        val = valuation_table(h)
        val_asof = (h.get("latest") or {}).get("d")
    except Exception as e:  # noqa: BLE001
        log.warning("valuations unavailable: %s", e)
        val, val_asof = prev.get("valuation", {}), prev.get("valuationAsOf")
    hist = prev.get("rateHist", [])
    today = date.today().isoformat()
    snap = {k: v.get("last") for k, v in rates.items()}
    if snap and (not hist or hist[-1].get("d") != today):
        hist.append({"d": today, **snap})
    hist = hist[-800:]
    glob = fetch_global(S)
    if len(glob) < len(GLOBAL) // 2:
        glob = prev.get("global", {}) or glob
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rates": rates, "rateHist": hist,
           "valuation": val, "valuationAsOf": val_asof, "global": glob}
    if not rates and not val:
        log.error("no market inputs available — keeping the previous file")
        return 0
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    log.info("macro.json: rates %s · valuations %d indices (as of %s) · global series %d", snap, len(val), val_asof, len(glob))
    for k, g in glob.items():
        log.info("  %-7s %-10s 3M %s · 6M %s · vs200 %s · 2y pct %s", k, g["last"], g["c3m"], g["c6m"], g["vs200"], g["pct2y"])
    for k in ("n50", "mid150", "sml250", "realty", "auto", "health", "it", "bank"):
        if k in val:
            log.info("  %-8s P/E %s (pct %s, median %s) · 6M rel %s", k, val[k]["pe"], val[k]["pePct"], val[k]["peMed"], val[k].get("r6mRel"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
