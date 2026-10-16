#!/usr/bin/env python3
"""Market & rates inputs for the Smart SIP planner → data/mf/macro.json (+ data/mf/val_hist.json).

* Interest rates — the central bank's national summary data: policy repo rate, call money, 91/182/364-day
  T-bill yields and the 10-year government bond par yield, each with the year-ago value and the last few weeks
  (so the direction of rates is known, not just the level). The central bank's home page is the fallback for
  the policy rate and T-bills. Every reading is appended to a small history kept in macro.json.
* Valuations — the exchange's daily index-close file carries P/E, P/B and dividend yield for every index.
  val_hist.json keeps one reading per month-end for ~30 indices going back to 2016 (bootstrapped once, then the
  latest month is refreshed each run), so each index's valuation can be ranked against its own 10-year history.

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
    "Nifty 50": "n50", "Nifty 500": "n500", "Nifty Midcap 150": "mid150", "Nifty Smallcap 250": "sml250",
    "Nifty Bank": "bank", "Nifty Financial Services": "fin", "Nifty Private Bank": "pvtbank", "Nifty PSU Bank": "psubank",
    "Nifty IT": "it", "Nifty Pharma": "pharma", "Nifty Healthcare Index": "health", "Nifty FMCG": "fmcg",
    "Nifty India Consumption": "consumption", "Nifty Auto": "auto", "Nifty Infrastructure": "infra",
    "Nifty Realty": "realty", "Nifty Energy": "energy", "Nifty Oil & Gas": "oilgas", "Nifty PSE": "pse",
    "Nifty CPSE": "cpse", "Nifty MNC": "mnc", "Nifty Commodities": "commodities", "Nifty Metal": "metal",
    "Nifty India Manufacturing": "mfg", "Nifty India Defence": "defence", "Nifty Media": "media",
    "Nifty Services Sector": "services", "Nifty Housing": "housing", "Nifty Transportation & Logistics": "transport",
    "Nifty India Digital": "digital",
}
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
    if "repo" not in out or "tb91" not in out:
        try:
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", S.get("https://www.rbi.org.in/", timeout=60).text))
            for k, rx in (("repo", r"Policy Repo Rate\s*:\s*([\d.]+)"), ("tb91", r"91 day T-bills\s*:\s*([\d.]+)"),
                          ("tb182", r"182 day T-bills\s*:\s*([\d.]+)"), ("tb364", r"364 day T-bills\s*:\s*([\d.]+)")):
                m = re.search(rx, txt, re.I)
                if m and k not in out:
                    out[k] = {"last": float(m.group(1))}
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
    lower = {k.lower(): v for k, v in INDICES.items()}
    for ln in lines[1:]:
        c = ln.split(",")
        if len(c) <= max(i_n, i_c, i_pe, i_pb, i_dy):
            continue
        key = lower.get(c[i_n].strip().lower())
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
    log.info("Valuation history: %d months (+%d this run), latest %s", len(h["months"]), got, (h.get("latest") or {}).get("d"))
    HIST.write_text(json.dumps(h, separators=(",", ":")))
    return h


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
        pe_hist = [months[k]["v"].get(key, [None])[0] for k in keys[-120:]]
        pb_hist = [months[k]["v"].get(key, [None, None])[1] for k in keys[-120:]]
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
        for n, lab in ((3, "r3m"), (6, "r6m"), (12, "r12m")):
            b = back(n)
            rec[lab] = round((last_close / b - 1) * 100, 2) if b and last_close else None
        out[key] = rec
    n50 = out.get("n50") or {}
    for k, r in out.items():                      # momentum relative to the Nifty 50
        for lab in ("r6m", "r12m"):
            if r.get(lab) is not None and n50.get(lab) is not None:
                r[lab + "Rel"] = round(r[lab] - n50[lab], 2)
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
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rates": rates, "rateHist": hist,
           "valuation": val, "valuationAsOf": val_asof}
    if not rates and not val:
        log.error("no market inputs available — keeping the previous file")
        return 0
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    log.info("macro.json: rates %s · valuations %d indices (as of %s)", snap, len(val), val_asof)
    for k in ("n50", "mid150", "sml250", "realty", "auto", "health", "it", "bank"):
        if k in val:
            log.info("  %-8s P/E %s (pct %s, median %s) · 6M rel %s", k, val[k]["pe"], val[k]["pePct"], val[k]["peMed"], val[k].get("r6mRel"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
