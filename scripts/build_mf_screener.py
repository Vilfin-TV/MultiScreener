#!/usr/bin/env python3
"""
India Mutual Fund Screener — data builder (runs in GitHub Actions only).

Universe: every open-ended Indian mutual fund scheme, Direct plan, Growth option
(ETFs, closed-ended, interval and segregated portfolios excluded).

Inputs (fetched here, never from the browser):
  * AMFI NAVAll.txt            — official daily NAV, scheme code, ISIN, SEBI category, AMC
  * Scheme NAV history         — per-scheme full daily history (community mirror of AMFI data)
  * Scheme facts               — expense ratio, AUM, fund managers, riskometer, minimums
  * NSE index history          — factor / size indices for Factor DNA

Outputs (same-origin static JSON for india_mf_screener.html):
  data/mf/screener.json        — every fund + headline metrics (loaded at page start; daily)
  data/mf/t/<sub>.json         — daily tail: NAVs since the last month-end + extra returns (daily)
  data/mf/d/<sub>.json         — deep analytics as of the last month-end (changes monthly)
  data/mf/h/<code>.json        — NAV history up to the last month-end (changes monthly)

Caches (GitHub Actions cache, not committed): .mfcache/
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mf_common as C  # noqa: E402
import mf_enrich as E  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mf"
CACHE = ROOT / ".mfcache"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("mf")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
NAVALL_URLS = ["https://www.amfiindia.com/spages/NAVAll.txt", "https://portal.amfiindia.com/spages/NAVAll.txt"]
HIST_URL = "https://api.mfapi.in/mf/{code}"
FACTS_URL = "https://mf.captnemo.in/kuvera/{isin}"
AMFI_TER = ("https://www.amfiindia.com/api/populate-te-rdata-revised?MF_ID=All&Month={month}"
            "&strCat=-1&strType=-1&page={page}&pageSize=1000")
AMFI_TER_MONTHS = "https://www.amfiindia.com/api/populate-ter-month?year={year}"
AMFI_HIST = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?tp=1&frmdt={f}&todt={t}"
NSE_HOME = "https://www.nseindia.com/reports-indices-historical-index-data"
NSE_HIST = "https://www.nseindia.com/api/historicalOR/indicesHistory?indexType={name}&from={f}&to={t}"

NSE_FACTORS = {  # factor key → NSE index name
    "core": "NIFTY 50", "mid": "NIFTY MIDCAP 150", "small": "NIFTY SMALLCAP 250",
    "mom": "NIFTY200 MOMENTUM 30", "val": "NIFTY500 VALUE 50", "qual": "NIFTY200 QUALITY 30",
    "lowvol": "NIFTY100 LOW VOLATILITY 30",
}

# Benchmarks are tracked through the longest-running Direct-Growth index fund on each index
# (a total-return series net of a small expense ratio).
BENCH_DEF = {
    "n50": ("Nifty 50", r"^(?!.*(next|equal|value|alpha|low vol|quality|momentum|shariah|arbitrage|dividend|"
                        r"etf|fof|top|bharat|esg)).*\bnifty ?50 index fund"),
    "n100": ("Nifty 100", r"^(?!.*(low vol|quality|equal|alpha|esg|etf|fof)).*\bnifty ?100 index fund"),
    "n500": ("Nifty 500", r"^(?!.*(value|momentum|quality|low vol|equal|multicap|shariah|etf|fof)).*\bnifty ?500 index fund"),
    "lm250": ("Nifty LargeMidcap 250", r"^(?!.*(elss|tax|etf|fof)).*(large ?mid ?cap|largemidcap) ?250 index fund"),
    "mid150": ("Nifty Midcap 150", r"^(?!.*(quality|momentum|etf|fof|value)).*\bnifty ?mid ?cap ?150 index fund"),
    "sml250": ("Nifty Smallcap 250", r"^(?!.*(quality|momentum|etf|fof|value)).*\bnifty ?small ?cap ?250 index fund"),
    "mom": ("Nifty200 Momentum 30", r"^(?!.*(etf|fof)).*nifty ?200 momentum 30 index fund"),
    "lowvol": ("Nifty100 Low Volatility 30", r"nifty ?100 low vol(atility)? 30"),
    "val": ("Nifty500 Value 50", r"nifty ?500 value 50 index fund"),
    "qual": ("Nifty200 Quality 30", r"nifty ?200 quality 30 index fund"),
    "us": ("S&P 500", r"s&p 500 index fund"),
}

SUB_BENCH = {
    "large": "n100", "largemid": "lm250", "mid": "mid150", "small": "sml250", "multi": "n500", "flexi": "n500",
    "focused": "n500", "value": "n500", "contra": "n500", "divyield": "n500", "elss": "n500", "sector": "n500",
    "eqfof": "n500", "idx_large": "n50", "idx_broad": "n500", "idx_factor": "n500", "idx_sector": "n500",
    "aggressive": "n50", "baf": "n50", "multiasset": "n50", "eqsavings": "n50", "balanced": "n50",
    "retire": "n50", "child": "n50", "lifecycle": "n50", "us": "us",
}
ALPHA_ASSETS = {"Equity", "Index"}          # alpha / TE / IR / capture only where the benchmark is like-for-like
FACTOR_ASSETS = {"Equity", "Index"}
GROWTH_ASSETS = {"Equity", "Index", "Global", "Commodity", "Hybrid", "Solution"}

RECON = {}
SNAPS = {}
TER = {}
ENRICH = {}
SCORES = {}
# exit loads read directly from fund houses missing from the scheme master (see fetch_fundhouse_loads.py)
try:
    LOADS_EXTRA = json.loads((Path(__file__).resolve().parent.parent / "data" / "mf" / "exitload_extra.json").read_text())
except (OSError, ValueError):
    LOADS_EXTRA = {}
# each fund's page on its fund house's site + the fund house's website (see fetch_scheme_pages.py)
try:
    PAGES = json.loads((Path(__file__).resolve().parent.parent / "data" / "mf" / "scheme_pages.json").read_text())
except (OSError, ValueError):
    PAGES = {}
RISKOMETER = ["Low", "Low to Moderate", "Moderate", "Moderately High", "High", "Very High"]


# ════════════════════════════════ HTTP ═════════════════════════════════════
def session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"})
    a = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32)
    s.mount("https://", a)
    return s


S = session()


def get(url, tries=4, timeout=40, **kw):
    last = None
    for k in range(tries):
        try:
            r = S.get(url, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
            if r.status_code == 404:
                break
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(1.5 * (k + 1))
    raise RuntimeError(f"{url}: {last}")


# ═══════════════════════════════ CACHE IO ══════════════════════════════════
def load_gz(path, default):
    try:
        with gzip.open(path, "rt") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_gz(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    tmp.replace(path)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=False)
    if path.exists() and path.read_text() == txt:
        return False
    path.write_text(txt)
    return True


# ════════════════════════════════ STEPS ════════════════════════════════════
def fetch_navall():
    for u in NAVALL_URLS:
        try:
            r = get(u)
            if len(r.text) > 200000 and "Scheme Code" in r.text[:500]:
                log.info("NAVAll from %s (%d bytes)", u, len(r.text))
                return r.text
        except Exception as e:  # noqa: BLE001
            log.warning("NAVAll %s failed: %s", u, e)
    raise SystemExit("AMFI NAVAll unavailable")


def build_universe(rows):
    dg = [r for r in rows if C.is_direct_growth(r) and r["date"] and r["nav"]]
    latest = Counter(r["date"] for r in dg).most_common(1)[0][0]
    keep, unclassified, stale = [], [], []
    for r in dg:
        if (latest - r["date"]).days > 10:
            stale.append(r)
            continue
        sub = C.classify(r["name"], r["cat"])
        if sub is None:
            unclassified.append(r)
            continue
        r["sub"] = sub
        keep.append(r)
    log.info("Direct-Growth rows %d → universe %d (stale %d, unclassified %d); NAV date %s",
             len(dg), len(keep), len(stale), len(unclassified), latest)
    return keep, latest, unclassified, stale


def fetch_history(code):
    r = get(HIST_URL.format(code=code), tries=3, timeout=60)
    j = r.json()
    pts = []
    for x in j.get("data", []):
        d = C.parse_dmy(x.get("date", ""))
        try:
            v = float(x.get("nav"))
        except (TypeError, ValueError):
            continue
        if d and v > 0:
            pts.append([d.toordinal(), v])
    pts.sort()
    return pts, j.get("meta", {})


def fix_face_value(pts):
    """Undo unit face-value changes (NAV jumps ×10 / ×100 / ÷10 overnight and stays there).
    Earlier NAVs are restated in today's units so returns stay continuous."""
    pts = [list(p) for p in pts]
    fixes = []
    for i in range(len(pts) - 1, 0, -1):
        r = pts[i][1] / pts[i - 1][1]
        k = round(math.log10(r)) if r > 0 else 0
        if k != 0 and abs(math.log10(r) - k) < 0.03:
            f = 10 ** k
            for j in range(i):
                pts[j][1] *= f
            fixes.append(C.iso(pts[i][0]))
    return pts, fixes


def clean_points(pts):
    """Drop isolated spikes (a one-day jump that fully reverses), duplicates and face-value breaks."""
    out, dropped = [], 0
    pts = sorted({p[0]: p for p in pts}.values())
    pts, fv = fix_face_value(pts)
    if fv:
        log.info("  unit face-value change restated on %s", ", ".join(fv[:4]))
    for i, p in enumerate(pts):
        if 0 < i < len(pts) - 1:
            a, b, c = pts[i - 1][1], p[1], pts[i + 1][1]
            if abs(b / a - 1) > 0.20 and abs(c / a - 1) < 0.03:
                dropped += 1
                continue
        out.append(p)
    return out, dropped


def load_histories(universe, navdate, args):
    cache = load_gz(CACHE / "hist.json.gz", {})
    hist, fail, meta = {}, [], {}
    codes = [r["code"] for r in universe]

    def job(code):
        try:
            return code, fetch_history(code), None
        except Exception as e:  # noqa: BLE001
            return code, None, str(e)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(job, c) for c in codes]):
            code, res, err = fut.result()
            if res and res[0]:
                hist[code], meta[code] = res
            else:
                fail.append(code)
                if str(code) in cache:
                    hist[code] = cache[str(code)]
    log.info("History: %d fetched, %d failed (%d served from cache) in %.0fs",
             len(meta), len(fail), sum(1 for c in fail if c in hist), time.time() - t0)
    # append today's official NAV when the history mirror lags
    appended = 0
    for r in universe:
        h = hist.get(r["code"])
        if h is None:
            continue
        o = r["date"].toordinal()
        if not h or h[-1][0] < o:
            h.append([o, r["nav"]])
            appended += 1
        elif h[-1][0] == o and abs(h[-1][1] / r["nav"] - 1) > 1e-6:
            h[-1][1] = r["nav"]
    log.info("Appended latest official NAV to %d histories", appended)
    # raw (as published) — reconciled with AMFI before face-value / spike cleaning
    raw = {code: sorted({p[0]: [p[0], p[1]] for p in h}.values()) for code, h in hist.items()}
    save_gz(CACHE / "hist.json.gz", {str(k): v for k, v in raw.items()})
    return raw, meta, fail


def dedupe(universe, facts, series):
    """AMFI occasionally lists several 'Direct / Growth' codes under one scheme name (legacy plans,
    IDCW plans mis-tagged as growth). Keep the genuine one."""
    groups = defaultdict(list)
    for r in universe:
        groups[(r["amc"], r["name"].lower())].append(r)
    drop = set()
    for key, lst in groups.items():
        if len(lst) < 2:
            continue
        def bad(r):
            f = facts.get(r["isin"]) or {}
            nm = f.get("name") or ""
            return bool(r.get("isin2")) or bool(re.search(r"idcw|dividend|bonus|unclaimed|payout|segregat", nm, re.I))
        good = [r for r in lst if not bad(r)]
        if not good:
            good = lst
        with_facts = [r for r in good if facts.get(r["isin"])]
        if with_facts:
            good = with_facts
        distinct = {((facts.get(r["isin"]) or {}).get("name") or "").lower() for r in good}
        if len(good) > 1 and len(distinct) < len(good):
            # same scheme listed twice: keep the longest-running series
            good = [min(good, key=lambda r: (series[r["code"]].d[0] if r["code"] in series else 10 ** 9, r["code"]))]
        keep = {r["code"] for r in good}
        for r in lst:
            if r["code"] not in keep:
                drop.add(r["code"])
                log.info("Dropped duplicate listing %s %s (kept %s)", r["code"], r["name"], sorted(keep))
    return [r for r in universe if r["code"] not in drop]


def amfi_snapshots(days_needed, codes, budget):
    """Official AMFI NAVs for the given 4-day windows (ending on each target day). Cached per day."""
    cache = load_gz(CACHE / "amfi_days.json.gz", {})
    fetched = 0
    for end in days_needed:
        win = [end - timedelta(days=k) for k in range(3, -1, -1)]
        if all(d.isoformat() in cache for d in win):
            continue
        if fetched >= budget:
            continue
        url = AMFI_HIST.format(f=win[0].strftime("%d-%b-%Y"), t=win[-1].strftime("%d-%b-%Y"))
        try:
            r = get(url, tries=3, timeout=180)
        except Exception as e:  # noqa: BLE001
            log.warning("AMFI history %s: %s", url, e)
            continue
        fetched += 1
        got = {d.isoformat(): {} for d in win}
        for line in r.text.splitlines():
            p = line.strip().split(";")
            if len(p) < 8 or not p[0].isdigit():
                continue
            c = int(p[0])
            if c not in codes:
                continue
            d = C.parse_amfi_date(p[7])
            try:
                v = float(p[6])
            except ValueError:
                continue
            if d and d.isoformat() in got and v > 0:
                got[d.isoformat()][str(c)] = v
        if sum(len(v) for v in got.values()) == 0:
            log.warning("AMFI history window %s–%s returned no rows (%d bytes)", win[0], win[-1], len(r.text))
            continue
        cache.update(got)
    keep_from = (min(days_needed) - timedelta(days=10)).isoformat() if days_needed else "0"
    cache = {k: v for k, v in cache.items() if k >= keep_from}
    save_gz(CACHE / "amfi_days.json.gz", cache)
    log.info("AMFI official snapshots: %d day(s) cached, %d window(s) fetched this run", len(cache), fetched)
    return cache


def reconcile_with_amfi(hist_pts, snaps):
    """Make the history agree with AMFI's official NAV on every snapshot day."""
    stats = {"checked": 0, "fixed": 0, "inserted": 0, "funds": 0}
    examples = []
    for code, pts in hist_pts.items():
        idx = {p[0]: i for i, p in enumerate(pts)}
        changed = False
        for day, vals in snaps.items():
            v = vals.get(str(code))
            if v is None:
                continue
            o = date.fromisoformat(day).toordinal()
            if pts and o < pts[0][0]:
                continue
            stats["checked"] += 1
            i = idx.get(o)
            if i is None:
                pts.append([o, v])
                stats["inserted"] += 1
                changed = True
            elif abs(pts[i][1] / v - 1) > 1e-6:
                if len(examples) < 40:
                    examples.append({"code": code, "day": day, "mirror": pts[i][1], "official": v})
                pts[i][1] = v
                stats["fixed"] += 1
                changed = True
        if changed:
            pts.sort()
            stats["funds"] += 1
    log.info("AMFI reconciliation: %s", stats)
    return stats, examples


def _norm_name(n):
    n = re.sub(r"\(.*?\)", " ", n.lower())
    n = re.sub(r"\b(fund|scheme|plan|the|direct|growth|option|an?|open ended)\b", " ", n)
    return re.sub(r"[^a-z0-9]+", "", n)


def load_official_ter(universe, args):
    """Official Direct-plan TER disclosed daily to AMFI (latest date per scheme).
    The disclosure is paged (100 rows per call), so it is collected under a time budget and resumed on the
    next run; a complete month is refreshed weekly."""
    cache = load_gz(CACHE / "ter.json.gz", {})
    if cache.get("_v") != 5:
        cache = {"_v": 5}
    rows = cache.get("rows", {})
    st = cache.get("state", {})
    today_ = date.today()
    stale = True
    try:
        stale = (today_ - date.fromisoformat(st.get("done", ""))).days >= 7
    except ValueError:
        pass
    if not cache.get("_etf"):              # one fresh pass that also keeps the regular-plan TER (ETFs have no Direct plan)
        stale, st = True, {}
    stat = Counter()
    if stale:
        if not st.get("month") or st.get("done"):
            fy = f"{today_.year}-{today_.year + 1}" if today_.month >= 4 else f"{today_.year - 1}-{today_.year}"
            try:
                j = S.get(AMFI_TER_MONTHS.format(year=fy), timeout=60).json()
                lst = j.get("data", j) if isinstance(j, dict) else j
                mon = next((m.get("MonthNumber") for m in lst if isinstance(m, dict) and m.get("MonthNumber")), None)
            except Exception as e:  # noqa: BLE001
                mon = None
                stat[type(e).__name__] += 1
            if mon:
                st = {"month": mon, "page": 1, "done": ""}
        t0 = time.time()
        while st.get("month") and not st.get("done") and time.time() - t0 < args.ter_seconds:
            data = None
            for k in range(3):
                try:
                    r = S.get(AMFI_TER.format(month=st["month"], page=st["page"]), timeout=60)
                    j = r.json()
                    d = j.get("data") if isinstance(j, dict) else None
                    data = (d.get("data") if isinstance(d, dict) else (d if isinstance(d, list) else [])) or []
                    break
                except Exception as e:  # noqa: BLE001
                    stat[type(e).__name__] += 1
                    time.sleep(3 * (k + 1))
            if data is None:
                break
            for x in data:
                dd = str(x.get("TER_Date") or "")[:10]
                ter, rter = _num(x.get("D_TER")), _num(x.get("R_TER"))
                if not dd or (ter is None and rter is None):
                    continue
                k = _norm_name(x.get("Scheme_Name", ""))
                if k and (k not in rows or dd >= rows[k][0]):
                    rows[k] = [dd, ter, x.get("Scheme_Name"), rter]
            stat["rows"] += len(data)
            if len(data) < 100:
                st["done"] = today_.isoformat()
                break
            st["page"] += 1
        stat["seconds"] = round(time.time() - t0)
        save_gz(CACHE / "ter.json.gz", {"_v": 5, "_etf": 1, "rows": rows, "state": st})
    out = {}
    for r in universe:
        hit = rows.get(_norm_name(r["name"]))
        if hit and r.get("etf"):              # ETFs: single plan — use whichever TER is disclosed
            hit = [hit[0], hit[1] if hit[1] is not None else (hit[3] if len(hit) > 3 else None), hit[2]]
        if hit and hit[1] is None:
            hit = None
        if hit and 0 <= hit[1] <= 2.6:          # SEBI caps Direct-plan TER well below this; anything above is a typo
            out[r["code"]] = {"ter": hit[1], "date": hit[0]}
        elif hit:
            log.warning("Ignoring implausible official TER %.2f%% for %s", hit[1], r["name"])
    log.info("Official TER: %s · state %s · %d schemes known, matched %d/%d funds",
             dict(stat), st, len(rows), len(out), len(universe))
    return out


def load_facts(universe, args):
    """Scheme facts (TER, AUM, managers, riskometer, minimums). Refreshed weekly per scheme, gently paced;
    schemes the source does not list yet are re-tried after a few days."""
    cache = load_gz(CACHE / "facts.json.gz", {})
    neg = cache.pop("_missing", {})
    today = date.today()
    isins = sorted({r["isin"] for r in universe if r["isin"]})

    def age(ts):
        try:
            return (today - date.fromisoformat(ts)).days
        except Exception:  # noqa: BLE001
            return 999

    todo = [i for i in isins if (i in cache and (age(cache[i].get("_ts", "")) >= 6 or "lump_available" not in cache[i]))
            or (i not in cache and age(neg.get(i, "")) >= 3)]
    todo.sort(key=lambda i: (i in cache, cache.get(i, {}).get("_ts", "")))
    todo = todo[:args.facts_budget]
    ok, errs = 0, Counter()

    def job(isin):
        time.sleep(0.25)
        try:
            r = S.get(FACTS_URL.format(isin=isin), timeout=30)
            if r.status_code != 200:
                return isin, None, f"HTTP {r.status_code}"
            j = r.json()
            return isin, (j[0] if isinstance(j, list) and j else None), ("empty" if not j else None)
        except Exception as e:  # noqa: BLE001
            return isin, None, type(e).__name__

    for workers, pause in ((3, 0), (1, 30), (1, 60)):
        if not todo:
            break
        time.sleep(pause)
        retry = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for fut in as_completed([ex.submit(job, i) for i in todo]):
                isin, rec, err = fut.result()
                if rec:
                    keep = {k: rec.get(k) for k in (
                        "name", "short_name", "lump_min", "sip_min", "lock_in_period", "detail_info", "start_date",
                        "expense_ratio", "expense_ratio_date", "fund_manager", "crisil_rating", "investment_objective",
                        "portfolio_turnover", "aum", "fund_category", "fund_type", "returns", "nav",
                        "lump_available", "sip_available", "sips")}
                    keep["_ts"] = today.isoformat()
                    cache[isin] = keep
                    neg.pop(isin, None)
                    ok += 1
                elif err in ("empty", "HTTP 404"):
                    errs[err] += 1
                    neg[isin] = today.isoformat()
                else:
                    errs[err] += 1
                    retry.append(isin)
        todo = retry
    log.info("Facts: %d refreshed this run, %d/%d schemes covered; misses %s", ok,
             sum(1 for i in isins if i in cache), len(isins), dict(errs))
    save_gz(CACHE / "facts.json.gz", {**cache, "_missing": neg})
    return cache


def fetch_nse_indices(start: date, end: date):
    cache = load_gz(CACHE / "nse.json.gz", {})
    s = session()
    s.headers.update({"Accept": "application/json, text/plain, */*", "Referer": NSE_HOME})
    try:
        s.get("https://www.nseindia.com/", timeout=30)
    except Exception:  # noqa: BLE001
        pass
    for key, name in NSE_FACTORS.items():
        have = {int(k): v for k, v in cache.get(key, {}).items()}
        last = max(have) if have else None
        span = [d for d in have if start.toordinal() <= d <= end.toordinal()]
        dense = len(span) >= 0.85 * (end - start).days * 5 / 7 * 0.95
        f0 = start if not have or min(have) > start.toordinal() + 7 or not dense else date.fromordinal(last) - timedelta(days=10)
        cur, got = f0, 0
        while cur <= end:
            to = min(cur + timedelta(days=90), end)   # the endpoint returns at most ~70 rows per call
            url = NSE_HIST.format(name=requests.utils.quote(name), f=cur.strftime("%d-%m-%Y"), t=to.strftime("%d-%m-%Y"))
            for k in range(3):
                try:
                    r = s.get(url, timeout=40)
                    data = r.json().get("data", []) if r.status_code == 200 and r.text.lstrip().startswith("{") else None
                    if data is None:
                        log.info("  NSE %s %s→%s: HTTP %s %s", key, cur, to, r.status_code, r.text[:80].replace("\n", " "))
                    if data is not None:
                        if data:
                            ds = [x.get("EOD_TIMESTAMP") for x in data]
                            log.info("  NSE %s %s→%s: %d rows (%s … %s)", key, cur, to, len(data), ds[-1], ds[0])
                        for x in data:
                            d = C.parse_amfi_date(x.get("EOD_TIMESTAMP", "").title())
                            v = x.get("EOD_CLOSE_INDEX_VAL")
                            if d and v:
                                have[d.toordinal()] = float(v)
                                got += 1
                        break
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(2 * (k + 1))
            cur = to + timedelta(days=1)
            time.sleep(0.4)
        cache[key] = {str(k): v for k, v in have.items()}
        log.info("NSE %-28s %5d pts (+%d)", name, len(have), got)
    save_gz(CACHE / "nse.json.gz", cache)
    return {k: C.Series([(int(d), v) for d, v in cache.get(k, {}).items()]) for k in NSE_FACTORS}


def pick_benchmarks(universe, series):
    out = {}
    for key, (label, rx) in BENCH_DEF.items():
        cands = [r for r in universe if re.search(rx, r["name"], re.I) and r["code"] in series and len(series[r["code"]]) > 60]
        if not cands:
            log.warning("No proxy for benchmark %s", key)
            continue
        best = min(cands, key=lambda r: (series[r["code"]].d[0], r["code"]))
        out[key] = {"name": label, "code": best["code"], "fund": best["name"],
                    "since": C.iso(series[best["code"]].d[0])}
        log.info("Benchmark %-7s %-28s ← %s (%s, since %s)", key, label, best["name"], best["code"], out[key]["since"])
    rf = [r for r in universe if r["sub"] == "overnight" and r["code"] in series and len(series[r["code"]]) > 60]
    best = min(rf, key=lambda r: (series[r["code"]].d[0], r["code"]))
    out["rf"] = {"name": "Overnight money-market rate", "code": best["code"], "fund": best["name"],
                 "since": C.iso(series[best["code"]].d[0])}
    log.info("Risk-free proxy ← %s (%s)", best["name"], best["code"])
    return out


def inception(series_pts: C.Series, fact: dict | None):
    """(ordinal, nav) to measure since-inception returns from."""
    d0, v0 = int(series_pts.d[0]), float(series_pts.v[0])
    sd = C.parse_dmy("-".join(reversed((fact or {}).get("start_date", "").split("-")))) if fact and fact.get("start_date") else None
    if sd and sd.toordinal() < d0 and d0 - sd.toordinal() <= 45 and sd >= date(2013, 1, 1):
        fv = 10 ** round(math.log10(v0))
        if abs(v0 / fv - 1) < 0.08:
            return sd.toordinal(), float(fv)
    return d0, v0


def si_return(end_d, end_v, d0, v0):
    days = end_d - d0
    if days <= 0:
        return None
    r = end_v / v0
    return C.pct((r ** (365.0 / days) - 1) if days >= 365 else r - 1)


def chart_points(s: C.Series, upto_ord: int):
    """Weekly points until 400 days before upto, then daily; offsets from the first date."""
    i_end = int(np.searchsorted(s.d, upto_ord, side="right"))
    d, v = s.d[:i_end], s.v[:i_end]
    if not len(d):
        return {"s": C.iso(s.d[0]), "p": []}
    cut = upto_ord - 400
    pts, last_week = [], None
    for k in range(len(d)):
        o = int(d[k])
        if o < cut:
            wk = (o - 1) // 7  # weeks bucket (Sunday-based); keep the last NAV of each week
            if last_week == wk and pts:
                pts[-1] = [o - int(d[0]), round(float(v[k]), 4)]
                continue
            last_week = wk
        pts.append([o - int(d[0]), round(float(v[k]), 4)])
    return {"s": C.iso(d[0]), "p": pts}


# ════════════════════════════════ MAIN ═════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--only", help="comma-separated scheme codes (validation runs)")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--facts-budget", type=int, default=1200, help="max scheme-fact refreshes per run")
    ap.add_argument("--enrich-seconds", type=int, default=900, help="time budget for official scheme details")
    ap.add_argument("--ter-seconds", type=int, default=420, help="time budget for the official TER disclosure")
    ap.add_argument("--etf-enrich-seconds", type=int, default=240, help="time budget for official ETF scheme details")
    ap.add_argument("--amfi-budget", type=int, default=60, help="max official history windows fetched per run")
    args = ap.parse_args()
    CACHE.mkdir(exist_ok=True)

    rows = C.parse_navall(fetch_navall())
    universe, navdate, unclassified, stale = build_universe(rows)
    if unclassified:
        for r in unclassified:
            log.error("UNCLASSIFIED %s | %s | %s", r["code"], r["name"], r["cat"])
        raise SystemExit(f"{len(unclassified)} fund(s) could not be classified — update mf_common.classify()")

    # display names (+ disambiguation of identical names within the universe)
    for r in universe:
        r["disp"] = C.nice_name(r["name"])
        r["amcName"] = C.amc_short(r["amc"])

    hist_pts, meta, failed = load_histories(universe, navdate, args)
    series = {c: C.Series(p) for c, p in hist_pts.items() if len(p) >= 2}
    universe = [r for r in universe if r["code"] in series]
    facts = load_facts(universe, args)
    universe = dedupe(universe, facts, series)
    global TER, ENRICH
    TER = load_official_ter(universe, args)
    try:
        ENRICH = E.Enricher(S, CACHE / "enrich.json.gz", budget_s=args.enrich_seconds).run(universe)
    except Exception as e:  # noqa: BLE001 — enrichment must never block the NAV refresh
        log.warning("Official scheme enrichment failed: %s", e)
        ENRICH = {}
    try:
        write_etf_facts(rows, args)
    except Exception as e:  # noqa: BLE001 — ETF facts must never block the fund refresh
        log.warning("ETF facts failed: %s", e)

    # official AMFI NAVs on every date the analytics depend on (return base dates first, then month-ends)
    asof0 = navdate
    targets = [asof0 - timedelta(days=7), date(asof0.year - 1, 12, 31)]
    targets += [C.shift_months(asof0, -m) for m in (1, 3, 6, 12, 24, 36, 60, 84, 120)]
    me = C.month_end(asof0.year, asof0.month)
    if me > asof0:
        pm = C.shift_months(date(asof0.year, asof0.month, 1), -1)
        me = C.month_end(pm.year, pm.month)
    targets += [C.month_end(C.shift_months(me, -k).year, C.shift_months(me, -k).month) for k in range(0, 37)]
    snaps = amfi_snapshots(targets, {r["code"] for r in universe}, budget=args.amfi_budget)
    recon, recon_ex = reconcile_with_amfi({r["code"]: hist_pts[r["code"]] for r in universe}, snaps)
    save_gz(CACHE / "hist.json.gz", {str(k): v for k, v in hist_pts.items()})
    for r in universe:
        cleaned, dropped = clean_points(hist_pts[r["code"]])
        if dropped:
            log.info("  %s: dropped %d isolated spike point(s)", r["code"], dropped)
        series[r["code"]] = C.Series(cleaned)
    global RECON, SNAPS
    RECON = {"stats": recon, "examples": recon_ex}
    SNAPS = snaps
    dup = Counter((r["disp"].lower()) for r in universe)
    for r in universe:
        if dup[r["disp"].lower()] > 1:
            f = facts.get(r["isin"]) or {}
            alt = (f.get("name") or "").replace("Growth Direct Plan", "").strip()
            r["disp"] = (C.nice_name(alt) if alt and alt.lower() != r["disp"].lower() else f'{r["disp"]} ({r["code"]})')

    asof = navdate
    risk_asof = C.month_end(asof.year, asof.month)
    if risk_asof > asof:
        prev = C.shift_months(date(asof.year, asof.month, 1), -1)
        risk_asof = C.month_end(prev.year, prev.month)
    month_ends = [C.shift_months(risk_asof, -k) for k in range(36, -1, -1)]
    month_ends = [C.month_end(m.year, m.month) for m in month_ends]
    log.info("NAV as of %s · risk/rolling as of %s", asof, risk_asof)

    bench = pick_benchmarks(universe, series)
    rf_s = series[bench["rf"]["code"]].upto(risk_asof.toordinal())
    rf_vals = C.month_end_values(rf_s, month_ends)
    bench_me = {k: C.month_end_values(series[b["code"]].upto(risk_asof.toordinal()), month_ends)
                for k, b in bench.items() if k != "rf"}

    # factor matrix (weekly)
    fridays = C.weekly_points(risk_asof, 156)
    nse = {}
    try:
        nse = fetch_nse_indices(date.fromordinal(fridays[0]) - timedelta(days=14), asof)
    except Exception as e:  # noqa: BLE001
        log.warning("NSE indices unavailable: %s", e)
    fac_ret = {}
    for k in C.FACTOR_KEYS:
        s = None
        if k in nse and len(nse[k]) > 600:
            s = nse[k]
        elif k == "cash":
            s = series[bench["rf"]["code"]]
        elif k == "us" and "us" in bench:
            s = series[bench["us"]["code"]]
        elif k in ("core", "mid", "small", "mom", "val", "qual", "lowvol"):
            alt = {"core": "n50", "mid": "mid150", "small": "sml250"}.get(k, k)
            if alt in bench:
                s = series[bench[alt]["code"]]
        if s is not None:
            fr = C.weekly_returns(s, fridays)
            if int(np.isfinite(fr).sum()) < 130:
                log.warning("Factor %s skipped: only %d weekly returns", k, int(np.isfinite(fr).sum()))
                continue
            fac_ret[k] = fr
            log.info("Factor %-6s %3d/%d weeks", k, int(np.isfinite(fr).sum()), len(fr))
    fac_keys = [k for k in C.FACTOR_KEYS if k in fac_ret]
    Xfull = np.column_stack([fac_ret[k] for k in fac_keys])

    only = {int(x) for x in args.only.split(",")} if args.only else None
    work = [r for r in universe if (only is None or r["code"] in only)]
    years = list(range(asof.year - 7, asof.year))

    results = {}
    t0 = time.time()
    for n_done, r in enumerate(work, 1):
        code, sub = r["code"], r["sub"]
        asset = C.SUBS[sub][0]
        s = series[code]
        sm = s.upto(risk_asof.toordinal())
        f = facts.get(r["isin"]) or {}
        res = {"tr": C.trailing_returns(s)}
        inc_d, inc_v = inception(s, f)
        res["tr"]["si"] = si_return(int(s.d[-1]), float(s.v[-1]), inc_d, inc_v)
        res["inc"], res["incV"] = C.iso(inc_d), inc_v
        res["sip"] = {str(n // 12): C.sip_returns(s, n) for n in (12, 36, 60, 120)}
        res["cal"] = C.calendar_returns(s, years)
        bkey = SUB_BENCH.get(sub) or SUB_BENCH.get(C.group(sub))
        if sub.startswith("idx_") and bkey:
            nm = r["name"]
            if re.search(r"small ?cap", nm, re.I) and "sml250" in bench:
                bkey = "sml250"
            elif re.search(r"mid ?cap", nm, re.I) and "mid150" in bench:
                bkey = "mid150"
        if bkey and bkey not in bench:
            bkey = None
        if bkey and bench[bkey]["code"] == code:
            bkey = "n500" if bkey == "n50" else "n50"
            if bkey not in bench:
                bkey = None
        res["bench"] = bkey
        bser = series[bench[bkey]["code"]].upto(risk_asof.toordinal()) if bkey else None
        res["risk"] = None
        if len(sm) > 30:
            res["risk"] = C.risk_metrics(sm, month_ends, rf_vals, bench_me.get(bkey) if bkey else None,
                                         with_alpha=asset in ALPHA_ASSETS)
            buckets = C.ROLL_BUCKETS["growth" if asset in GROWTH_ASSETS and sub not in ("arbitrage", "conservative") else "income"]
            res["roll"] = {str(y): C.rolling_stats(sm, y, bser, buckets) for y in (1, 3, 5)}
            res["rollEdges"] = buckets
            res["mdd3"] = C.max_drawdown(s, C.shift_months(risk_asof, -36).toordinal(), risk_asof.toordinal())
            res["mddAll"] = C.max_drawdown(s, int(s.d[0]), risk_asof.toordinal())
            res["trM"] = C.trailing_returns(sm) if len(sm) > 2 else {}
        if asset in FACTOR_ASSETS and len(sm) > 30:
            y = C.weekly_returns(sm, fridays)
            ok = np.isfinite(y) & np.all(np.isfinite(Xfull), axis=1)
            if ok.sum() >= 104:
                sa = C.style_analysis(y[ok], Xfull[ok])
                if sa:
                    w, r2 = sa
                    wd = {k: 0.0 for k in C.FACTOR_KEYS}
                    wd.update({k: float(x) for k, x in zip(fac_keys, w)})
                    lab = C.factor_label(wd, r2)
                    res["factor"] = {"w": {k: round(v * 100, 2) for k, v in wd.items()}, "r2": round(r2 * 100, 2),
                                     "weeks": int(ok.sum()), **lab}
        results[code] = res
        if n_done % 200 == 0:
            log.info("  analysed %d/%d (%.0fs)", n_done, len(work), time.time() - t0)
    log.info("Analytics for %d funds in %.0fs", len(results), time.time() - t0)

    # ── ratings (month-end data, within each sub-category, ≥3Y history, ≥5 peers)
    rating = {}
    by_sub = defaultdict(list)
    for r in work:
        res = results[r["code"]]
        rk = res.get("risk") or {}
        if C.SUBS[r["sub"]][0] != "Index" and rk.get("months", 0) >= 36 and res.get("trM", {}).get("3y") is not None:
            by_sub[C.group(r["sub"])].append(r)
    for sub, lst in by_sub.items():
        if len(lst) < 5:
            continue
        g = lambda r, k: (results[r["code"]].get("risk") or {}).get(k)  # noqa: E731
        sh = C.percentile_ranks([g(r, "sharpe") for r in lst])
        so = C.percentile_ranks([g(r, "sortino") for r in lst])
        r3 = C.percentile_ranks([results[r["code"]]["trM"].get("3y") for r in lst])
        r5 = C.percentile_ranks([results[r["code"]]["trM"].get("5y") if results[r["code"]]["trM"].get("5y") is not None
                                 else results[r["code"]]["trM"].get("3y") for r in lst])
        md = C.percentile_ranks([(results[r["code"]].get("mdd3") or {}).get("mdd") for r in lst])
        ter = []
        for r in lst:
            try:
                ter.append(ter_of(r, facts.get(r["isin"]) or {})[0])
            except (TypeError, ValueError):
                ter.append(None)
        te = C.percentile_ranks(ter, higher_better=False)
        scores = []
        for i in range(len(lst)):
            parts = [(sh[i], .25), (so[i], .15), (r3[i], .20), (r5[i], .10), (md[i], .15), (te[i], .15)]
            parts = [(p, w) for p, w in parts if p is not None]
            scores.append(sum(p * w for p, w in parts) / sum(w for _, w in parts) if parts else None)
        for r, st in zip(lst, C.stars_from_scores(scores)):
            rating[r["code"]] = st

    # ── scorecard: recency, consistency, volatility, status (within each sub-category)
    me48 = [C.month_end(C.shift_months(risk_asof, -k).year, C.shift_months(risk_asof, -k).month) for k in range(47, -1, -1)]
    me72 = [C.month_end(C.shift_months(risk_asof, -k).year, C.shift_months(risk_asof, -k).month) for k in range(71, -1, -1)]
    groups = defaultdict(list)
    for r in work:
        if C.SUBS[r["sub"]][0] == "Index":
            continue
        res = results[r["code"]]
        vals = C.month_end_values(series[r["code"]].upto(risk_asof.toordinal()), me48)
        roll12 = []
        for k in range(12, len(me48)):
            a, b = vals[k - 12], vals[k]
            roll12.append(float(b / a - 1) if np.isfinite(a) and np.isfinite(b) and a > 0 else None)
        v72 = C.month_end_values(series[r["code"]].upto(risk_asof.toordinal()), me72)
        roll12_5 = []
        for k in range(12, len(me72)):
            a, b = v72[k - 12], v72[k]
            roll12_5.append(float(b / a - 1) if np.isfinite(a) and np.isfinite(b) and a > 0 else None)
        m_ret = [float(v72[k] / v72[k - 1] - 1) for k in range(len(me72) - 60, len(me72))
                 if np.isfinite(v72[k]) and np.isfinite(v72[k - 1]) and v72[k - 1] > 0]
        std5 = float(np.std(m_ret, ddof=1) * np.sqrt(12) * 100) if len(m_ret) >= 58 else None
        groups[C.group(r["sub"])].append({"code": r["code"], "tr": res["tr"], "roll12": roll12, "roll12_5": roll12_5,
                                 "std": (res.get("risk") or {}).get("std"), "std5": std5})
    global SCORES
    SCORES = {}
    for sub, grp in groups.items():
        SCORES.update(C.scorecard(grp))
        for code, v in C.scorecard_5y(grp).items():
            SCORES.setdefault(code, {}).update(v)
        for g in grp:
            if g.get("std5") is not None:
                SCORES.setdefault(g["code"], {})["std5"] = round(g["std5"], 2)
    log.info("Scorecard: %s", dict(Counter(v.get("status") for v in SCORES.values())))

    if args.no_write:
        dump_validation(universe, work, results, facts, bench, asof, risk_asof, series, month_ends, rf_vals, bench_me)
        return
    write_outputs(universe, work, results, facts, bench, asof, risk_asof, series, rating, stale, fac_keys)
    dump_validation(universe, work, results, facts, bench, asof, risk_asof, series, month_ends, rf_vals, bench_me)


def _site(u):
    """Normalise a fund-house address from the scheme master ("www.x.com", "https:\\\\x.com")."""
    if not u:
        return None
    u = u.strip().replace("\\", "/").replace("https:////", "https://").replace("http:////", "http://")
    return u if re.match(r"https?://", u, re.I) else "https://" + u.lstrip("/")


def etf_rows(rows):
    """Open-ended exchange-traded schemes in the official NAV file (one row per ISIN, growth units)."""
    out = {}
    for r in rows:
        if not r["cat"].startswith("Open Ended") or not r["isin"] or not r["nav"] or not r["date"]:
            continue
        if not ("ETF" in r["cat"].split("(", 1)[-1][:40] or re.search(r"Gold ETF|Other\s+ETFs", r["cat"])):
            continue
        if re.search(r"idcw|dividend|payout|segregat", r["name"], re.I):
            continue
        out[r["isin"]] = {**r, "etf": True, "disp": C.nice_name(r["name"]), "amcName": C.amc_short(r["amc"])}
    return list(out.values())


def write_etf_facts(rows, args):
    """data/mf/etf_facts.json — official facts for every listed ETF, keyed by ISIN (read by the ETF page build):
    NAV, expense ratio, fund size, benchmark, riskometer, launch date, managers and document links."""
    etfs = etf_rows(rows)
    if len(etfs) < 50:
        log.warning("ETF facts: only %d ETFs in the NAV file — skipped", len(etfs))
        return
    ter = load_official_ter(etfs, argparse.Namespace(**{**vars(args), "ter_seconds": 0}))
    try:
        enr = E.Enricher(S, CACHE / "enrich.json.gz", budget_s=args.etf_enrich_seconds).run(etfs)
    except Exception as e:  # noqa: BLE001
        log.warning("ETF enrichment failed: %s", e)
        enr = {}
    # official NAV history → long-horizon returns (split / face-value changes restated like every fund)
    navr = {}

    def job(code):
        try:
            return code, fetch_history(code)[0]
        except Exception:  # noqa: BLE001
            return code, None
    yrs = list(range(date.today().year - 6, date.today().year))
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for code, pts in ex.map(job, [r["code"] for r in etfs]):
            if not pts or len(pts) < 30:
                continue
            row = next(r for r in etfs if r["code"] == code)
            o = row["date"].toordinal()
            if pts[-1][0] < o:
                pts.append([o, row["nav"]])
            cleaned, _ = clean_points(pts)
            sr = C.Series(cleaned)
            if len(sr) < 30 or date.fromordinal(int(sr.d[-1])) < row["date"] - timedelta(days=10):
                continue
            tr = C.trailing_returns(sr)
            navr[code] = {"r": {k: (None if tr.get(k) is None else round(tr[k], 2)) for k in ("1y", "3y", "5y", "10y", "si")},
                          "cy": {k: round(v, 2) for k, v in C.calendar_returns(sr, yrs).items() if v is not None},
                          "first": C.iso(int(sr.d[0]))}
    log.info("ETF NAV histories: %d/%d", len(navr), len(etfs))
    out = {}
    for r in etfs:
        e = enr.get(r["code"]) or {}
        det, ssd, aum = e.get("details") or {}, e.get("ssd") or {}, e.get("aum") or {}
        t = ter.get(r["code"]) or {}
        sid = e.get("sid")
        rec = {"code": r["code"], "name": r["disp"], "amc": r["amcName"], "nav": r["nav"], "navDate": C.iso(r["date"].toordinal()),
               "ter": t.get("ter"), "terDate": t.get("date"),
               "aum": round(aum["totalLakh"] / 100, 1) if aum.get("totalLakh") else None, "aumAsOf": aum.get("quarter"),
               "benchmark": ssd.get("benchmark") or "", "risk": re.sub(r"\s+risk$", "", (ssd.get("riskometer") or ""), flags=re.I).strip(),
               "launch": det.get("launch") or "", "managers": [m["name"] for m in (ssd.get("managers") or [])][:4],
               "objective": re.sub(r"\s+", " ", ssd.get("objective") or det.get("objective") or "")[:500],
               "sid": f"{E.PORTAL}/spages/{sid}.pdf" if sid else None, "ssd": f"{E.PORTAL}/spages/SSD_{sid}.pdf" if sid else None,
               "website": (PAGES.get("_sites") or {}).get(r["amcName"]) or _site(det.get("website"))}
        if r["code"] in navr:
            rec["navR"], rec["navCy"], rec["navFirst"] = navr[r["code"]]["r"], navr[r["code"]]["cy"], navr[r["code"]]["first"]
        out[r["isin"]] = {k: v for k, v in rec.items() if v not in (None, "", [])}
    write_json(OUT / "etf_facts.json", {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        "count": len(out), "etfs": out})
    log.info("ETF facts: %d ETFs · TER %d · AUM %d · benchmark %d", len(out), sum("ter" in v for v in out.values()),
             sum("aum" in v for v in out.values()), sum("benchmark" in v for v in out.values()))


def ter_of(r, f):
    """(TER %, as-of date): AMFI's official daily disclosure first, scheme facts otherwise."""
    o = TER.get(r["code"])
    if o:
        return o["ter"], o["date"]
    try:
        return float(f.get("expense_ratio")), f.get("expense_ratio_date")
    except (TypeError, ValueError):
        return None, None


def _f(x, nd=2):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(x) else round(x, nd)


def _num(x):
    try:
        v = float(str(x).replace(",", "").strip())
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def buy_flags(f):
    """Purchase status: "L" lump sum accepted, "S" SIP accepted, "W" weekly SIP offered; "" = closed to fresh
    money (e.g. overseas schemes paused at the industry overseas-investment limit); None = not known yet."""
    la, sa = f.get("lump_available"), f.get("sip_available")
    if la is None and sa is None:
        return None
    freqs = {str(x.get("sip_frequency", "")).upper() for x in (f.get("sips") or []) if isinstance(x, dict)}
    return ("L" if la == "Y" else "") + ("S" if sa == "Y" else "") + ("W" if sa == "Y" and "WEEKLY" in freqs else "")


def merged_facts(r, f):
    """Combine AMFI official scheme data (preferred) with scheme facts (fallback)."""
    e = ENRICH.get(r["code"]) or {}
    det, ssd, aum = e.get("details") or {}, e.get("ssd") or {}, e.get("aum") or {}
    m = {}
    # fund size: AMFI quarterly average AUM summed over all plans (₹ lakh → ₹ crore)
    if aum.get("totalLakh"):
        m["aum"], m["aumAsOf"], m["aumSrc"] = round(aum["totalLakh"] / 100, 1), aum.get("quarter"), "Quarterly average AUM (all plans)"
    elif _num(f.get("aum")) is not None:
        m["aum"], m["aumAsOf"], m["aumSrc"] = round(_num(f.get("aum")) / 10, 1), None, "Fund size"
    else:
        m["aum"] = None
    rk = (ssd.get("riskometer") or (f.get("crisil_rating") or "").replace(" Risk", "")).strip()
    rk = re.sub(r"\s+risk$", "", rk, flags=re.I).strip().title().replace(" To ", " to ")
    m["risk"] = RISKOMETER.index(rk) if rk in RISKOMETER else None
    m["sipMin"] = _num(f.get("sip_min"))
    if m["sipMin"] is None:
        mm = re.search(r"monthly\s*[-:]?\s*(?:rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)", ssd.get("sipMin") or "", re.I)
        m["sipMin"] = _num(mm.group(1)) if mm else None
    m["lumpMin"] = _num(f.get("lump_min"))
    if m["lumpMin"] is None:
        m["lumpMin"] = _num(ssd.get("minApp"))
    lock = f.get("lock_in_period")
    if not lock:
        lock = 3 if r["sub"] == "elss" else (5 if r["sub"] in ("retire", "child") else 0)
    m["lock"] = lock
    lines = (E.parse_exit_load(det.get("load")) or E.parse_exit_load(ssd.get("exitLoadSsd"))
             or LOADS_EXTRA.get(str(r["code"])) or [])
    m["exitLoad"] = lines
    m["exitNil"] = E.is_nil_load(lines) if lines else None
    m["managers"] = ssd.get("managers") or [{"name": x.strip(), "since": "", "role": ""}
                                            for x in re.split(r";|,(?![^()]*\))", f.get("fund_manager") or "") if x.strip()]
    m["objective"] = ssd.get("objective") or det.get("objective") or (f.get("investment_objective") or "").strip()
    m["benchmark"] = ssd.get("benchmark") or ""
    m["alloc"] = ssd.get("alloc") or []
    m["tax"] = E.tax_class(r["sub"], m["alloc"], r["name"])
    sid = e.get("sid")
    m["docs"] = {"sid": f"{E.PORTAL}/spages/{sid}.pdf" if sid else (f.get("detail_info") or None),
                 "ssd": f"{E.PORTAL}/spages/SSD_{sid}.pdf" if sid else None,
                 "website": (PAGES.get("_sites") or {}).get(r["amcName"]) or _site(det.get("website")),
                 "scheme": PAGES.get(str(r["code"])) or None,
                 "list": (PAGES.get("_lists") or {}).get(r["amcName"]) or None}
    m["extra"] = {k: ssd.get(k) for k in ("faceValue", "allotment", "prc", "custodian", "registrar", "maxTer", "listing",
                                          "category", "type") if ssd.get(k)}
    if det.get("launch"):
        m["extra"]["launch"] = det["launch"]
    if det.get("minAmt"):
        m["extra"]["minText"] = det["minAmt"]
    return m


def rebucket_portfolios(sub_of: dict) -> None:
    """Portfolio files (data/mf/p/<sub>.json, built monthly) follow each fund's current category."""
    pdir = OUT / "p"
    if not pdir.exists():
        return
    by_sub, files = defaultdict(dict), [f for f in pdir.glob("*.json") if not f.name.startswith("_")]
    for f in files:
        for code, v in json.loads(f.read_text()).items():
            if int(code) in sub_of:
                by_sub[sub_of[int(code)]][code] = v
    for f in files:
        if f.stem not in by_sub:
            f.unlink()
    for sub, d in by_sub.items():
        new = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
        path = pdir / f"{sub}.json"
        if not path.exists() or path.read_text() != new:
            path.write_text(new)


def write_outputs(universe, work, results, facts, bench, asof, risk_asof, series, rating, stale, fac_keys):
    OUT.mkdir(parents=True, exist_ok=True)
    rebucket_portfolios({r["code"]: r["sub"] for r in work})
    amcs = sorted({r["amcName"] for r in work})
    amc_i = {a: i for i, a in enumerate(amcs)}
    subs_used = sorted({r["sub"] for r in work}, key=lambda k: list(C.SUBS).index(k))
    cols = ["code", "name", "amc", "sub", "nav", "navDate", "r1d", "r1w", "r1m", "r3m", "r6m", "ytd", "r1y", "r3y",
            "r5y", "r10y", "si", "inc", "sip1", "sip3", "sip5", "ter", "aum", "risk", "rating", "std", "sharpe",
            "sortino", "beta", "alpha", "mdd", "style", "size", "roll3", "beat3", "pos1", "sipMin", "lumpMin",
            "lock", "bench", "isin", "cons", "rec", "vols", "ltp", "status", "tax", "exitNil", "buy"]
    rows = []
    MF = {}
    for r in sorted(work, key=lambda r: (r["sub"], r["disp"].lower())):
        res, f = results[r["code"]], facts.get(r["isin"]) or {}
        tr, rk, ro = res["tr"], res.get("risk") or {}, res.get("roll") or {}
        s = series[r["code"]]
        fac = res.get("factor") or {}
        m = MF[r["code"]] = merged_facts(r, f)
        sc = SCORES.get(r["code"]) or {}
        rows.append([
            r["code"], r["disp"], amc_i[r["amcName"]], r["sub"], round(float(s.v[-1]), 4), C.iso(s.d[-1]),
            tr.get("1d"), tr.get("1w"), tr.get("1m"), tr.get("3m"), tr.get("6m"), tr.get("ytd"), tr.get("1y"),
            tr.get("3y"), tr.get("5y"), tr.get("10y"), tr.get("si"), res["inc"],
            (res["sip"].get("1") or {}).get("xirr"), (res["sip"].get("3") or {}).get("xirr"),
            (res["sip"].get("5") or {}).get("xirr"),
            _f(ter_of(r, f)[0]), m["aum"], m["risk"], rating.get(r["code"]),
            rk.get("std"), rk.get("sharpe"), rk.get("sortino"), rk.get("beta"), rk.get("alpha"),
            (res.get("mdd3") or {}).get("mdd"), fac.get("primary"), fac.get("size"),
            (ro.get("3") or {}).get("avg"), (ro.get("3") or {}).get("beat"), (ro.get("1") or {}).get("pos"),
            m["sipMin"], m["lumpMin"], m["lock"], res["bench"], r["isin"],
            sc.get("cons"), sc.get("rec"), sc.get("vol"), sc.get("ltp"), sc.get("status"), m["tax"], m["exitNil"],
            buy_flags(f),
        ])
    # round all floats to 2 dp in the screener (returns in %, ratios) — 4 dp for NAV / ratios
    for row in rows:
        for i, c in enumerate(cols):
            v = row[i]
            if isinstance(v, float):
                row[i] = round(v, 4 if c in ("nav", "sharpe", "sortino", "beta") else 2)
    bench_out = {}
    for k, b in bench.items():
        s = series[b["code"]]
        tr = C.trailing_returns(s)
        bench_out[k] = {"name": b["name"], "code": b["code"], "since": b["since"],
                        "r": {p: (round(tr[p], 2) if tr.get(p) is not None else None) for p in ("1m", "3m", "6m", "1y", "3y", "5y", "10y")}}
    screener = {
        "v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asOf": asof.isoformat(), "riskAsOf": risk_asof.isoformat(),
        "assets": C.ASSETS, "subs": {k: list(C.SUBS[k]) for k in subs_used}, "amcs": amcs,
        "riskometer": RISKOMETER, "bench": bench_out, "factors": fac_keys, "statuses": C.STATUS, "rules": C.RULES_VERSION,
        "tax": {"asOf": E.TAX_RULES_AS_OF, "rules": E.TAX},
        "count": len(rows), "cols": cols, "rows": rows,
    }
    write_json(OUT / "screener.json", screener)

    by_sub = defaultdict(list)
    for r in work:
        by_sub[r["sub"]].append(r)
    keep_files = {"screener.json"}
    for sub, lst in by_sub.items():
        det, tail = {}, {}
        for r in lst:
            res, f = results[r["code"]], facts.get(r["isin"]) or {}
            det[str(r["code"])] = {
                "cal": res["cal"], "roll": res.get("roll"), "edges": res.get("rollEdges"), "risk": res.get("risk"),
                "mdd3": res.get("mdd3"), "mddAll": res.get("mddAll"), "factor": res.get("factor"),
                "trM": {k: v for k, v in (res.get("trM") or {}).items() if k in ("1y", "3y", "5y", "10y", "si")},
                "info": {
                    "amfiName": r["name"], "cat": r["cat"], "objective": MF[r["code"]]["objective"],
                    "managers": MF[r["code"]]["managers"], "benchmark": MF[r["code"]]["benchmark"],
                    "exitLoad": MF[r["code"]]["exitLoad"], "alloc": MF[r["code"]]["alloc"],
                    "docs": MF[r["code"]]["docs"], "extra": MF[r["code"]]["extra"],
                    "aumAsOf": MF[r["code"]].get("aumAsOf"), "aumSrc": MF[r["code"]].get("aumSrc"),
                    "sid": MF[r["code"]]["docs"]["sid"], "turnover": _f(f.get("portfolio_turnover")),
                    "terDate": ter_of(r, f)[1], "start": f.get("start_date"),
                },
                "score": {k: v for k, v in (SCORES.get(r["code"]) or {}).items()
                          if k in ("consTop", "consN", "cons5", "cons5Top", "cons5N", "vol5", "std5")},
            }
            s = series[r["code"]]
            i0 = int(np.searchsorted(s.d, risk_asof.toordinal(), side="right"))
            tr = res["tr"]
            tail[str(r["code"])] = {
                "p": [[C.iso(s.d[i]), round(float(s.v[i]), 4)] for i in range(i0, len(s.d))],
                "r": {k: tr.get(k) for k in ("2y", "7y")},
                "sip": res["sip"],
            }
            h = chart_points(s, risk_asof.toordinal())
            if h:
                write_json(OUT / "h" / f"{r['code']}.json", h)
        write_json(OUT / "d" / f"{sub}.json", det)
        write_json(OUT / "t" / f"{sub}.json", tail)
    # prune files of funds / sub-categories that left the universe
    live = {str(r["code"]) for r in work}
    for p in (OUT / "h").glob("*.json"):
        if p.stem not in live:
            p.unlink()
    for folder in ("d", "t"):
        for p in (OUT / folder).glob("*.json"):
            if p.stem not in by_sub:
                p.unlink()
    log.info("Wrote screener.json (%d funds), %d sub-category files", len(rows), len(by_sub))


def dump_validation(universe, work, results, facts, bench, asof, risk_asof, series, month_ends, rf_vals, bench_me):
    """Compare trailing returns with an independent published source + write the cross-language verify sample."""
    cmp_rows, diffs = [], {"1y": [], "3y": [], "5y": [], "1w": []}
    kmap = {"1w": "week_1", "1y": "year_1", "3y": "year_3", "5y": "year_5"}
    for r in work:
        f = facts.get(r["isin"]) or {}
        ret = f.get("returns") or {}
        if not ret or ret.get("date") != C.iso(series[r["code"]].d[-1]):
            continue
        tr = results[r["code"]]["tr"]
        row = {"code": r["code"], "name": r["disp"]}
        for k, kk in kmap.items():
            a, b = tr.get(k), ret.get(kk)
            if a is None or b in (None, 0, 0.0):
                continue
            diffs[k].append(abs(a - b))
            row[k] = [round(a, 3), round(b, 3)]
        cmp_rows.append(row)
    summ = {}
    for k, d in diffs.items():
        if d:
            d = np.array(d)
            summ[k] = {"n": int(len(d)), "within_0.05pp": round(float(np.mean(d <= 0.05)) * 100, 2),
                       "within_0.25pp": round(float(np.mean(d <= 0.25)) * 100, 2),
                       "median": round(float(np.median(d)), 4), "max": round(float(np.max(d)), 4)}
    worst = sorted(cmp_rows, key=lambda x: -max((abs(v[0] - v[1]) for kk, v in x.items() if kk in kmap), default=0))[:25]
    # returns recomputed purely from AMFI's official NAVs (latest NAV file + official history on the base date)
    off = {"1w": [], "1m": [], "3m": [], "6m": [], "1y": [], "3y": [], "5y": [], "10y": []}
    off_bad = []
    per = {"1w": ("d", 7), "1m": ("m", 1), "3m": ("m", 3), "6m": ("m", 6), "1y": ("m", 12), "3y": ("m", 36), "5y": ("m", 60), "10y": ("m", 120)}
    for r in work:
        s = series[r["code"]]
        if C.iso(s.d[-1]) != r["date"].isoformat():
            continue
        for k, (kind, n) in per.items():
            t = r["date"] - timedelta(days=n) if kind == "d" else C.shift_months(r["date"], -n)
            base = None
            for back in range(0, 4):
                v = SNAPS.get((t - timedelta(days=back)).isoformat(), {}).get(str(r["code"]))
                if v:
                    base = v
                    break
            ours = results[r["code"]]["tr"].get(k)
            if base is None or ours is None:
                continue
            x = r["nav"] / base
            o = (x - 1 if (kind == "d" or n <= 12) else x ** (12.0 / n) - 1) * 100
            d = abs(o - ours)
            off[k].append(d)
            if d > 0.01 and len(off_bad) < 30:
                off_bad.append({"code": r["code"], "name": r["disp"], "period": k, "ours": ours, "official": round(o, 4)})
    vs_official = {k: {"n": len(v), "exact_0.01pp": round(float(np.mean(np.array(v) <= 0.01)) * 100, 2)}
                   for k, v in off.items() if v}
    log.info("Validation vs AMFI official NAVs: %s", json.dumps(vs_official))
    both = []
    for r in work:
        o, f = TER.get(r["code"]), facts.get(r["isin"]) or {}
        try:
            both.append(abs(o["ter"] - float(f["expense_ratio"])))
        except (TypeError, ValueError, KeyError):
            pass
    ter_cmp = {"official": len(TER), "both": len(both),
               "within_0.05": round(float(np.mean(np.array(both) <= 0.05)) * 100, 2) if both else None}
    log.info("TER official vs scheme facts: %s", ter_cmp)
    REF = [r"Parag Parikh Flexi Cap", r"ICICI Prudential Large Cap", r"Nippon India Small Cap Fund$",
           r"Mirae Asset ELSS", r"SBI Liquid", r"ICICI Prudential Gilt Fund$", r"HDFC Balanced Advantage",
           r"Nippon India Gold Savings", r"Motilal Oswal Nasdaq 100 Fund of Fund", r"UTI Nifty 50 Index Fund$"]
    ref = []
    for rx in REF:
        m = [r for r in work if re.search(rx, r["name"], re.I)]
        if not m:
            continue
        r = m[0]
        res, f = results[r["code"]], facts.get(r["isin"]) or {}
        ref.append({"code": r["code"], "name": r["disp"], "sub": C.SUBS[r["sub"]][1], "asset": C.SUBS[r["sub"]][0],
                    "nav": round(float(series[r["code"]].v[-1]), 4), "navDate": C.iso(series[r["code"]].d[-1]),
                    "ours": {k: res["tr"].get(k) for k in ("1d", "1w", "1m", "3m", "6m", "1y", "3y", "5y", "si")},
                    "independent": f.get("returns"), "sip3": (res["sip"].get("3") or {}).get("xirr"),
                    "risk": res.get("risk"), "factor": res.get("factor"), "bench": res.get("bench"),
                    "ter": ter_of(r, f)[0], "terFacts": f.get("expense_ratio"), "aum_cr": round(float(f["aum"]) / 10, 1) if f.get("aum") else None,
                    "managers": f.get("fund_manager"), "riskometer": f.get("crisil_rating")})
    sub_counts = Counter(C.SUBS[r["sub"]][1] + " | " + C.SUBS[r["sub"]][0] for r in work)
    report = {"asOf": asof.isoformat(), "riskAsOf": risk_asof.isoformat(), "universe": len(universe), "amfiReconciliation": RECON,
              "analysed": len(work), "terCheck": ter_cmp, "vsOfficial": vs_official, "officialMismatches": off_bad, "vsIndependent": summ, "worst": worst, "reference": ref,
              "benchmarks": bench, "subCounts": dict(sorted(sub_counts.items())),
              "global": sorted(r["disp"] for r in work if C.SUBS[r["sub"]][0] == "Global"),
              "commodity": sorted(r["disp"] for r in work if C.SUBS[r["sub"]][0] == "Commodity"),
              "factorIdx": [{"name": r["disp"], "f": (results[r["code"]].get("factor") or {}).get("primary"),
                             "w": (results[r["code"]].get("factor") or {}).get("w"),
                             "r2": (results[r["code"]].get("factor") or {}).get("r2")}
                            for r in work if r["sub"] == "idx_factor"][:60]}
    CACHE.mkdir(exist_ok=True)
    (CACHE / "validation.json").write_text(json.dumps(report, indent=1, default=str))
    log.info("Validation vs independent source: %s", json.dumps(summ))

    # cross-language verification sample: raw inputs + Python outputs
    pick = [x["code"] for x in ref]
    by_sub = defaultdict(list)
    for r in work:
        by_sub[r["sub"]].append(r["code"])
    for sub in sorted(by_sub):
        pick.extend(by_sub[sub][:1])
    import random
    rnd = random.Random(asof.toordinal())          # a different random sample every day
    pool = [r["code"] for r in work]
    pick += rnd.sample(pool, min(120, len(pool)))
    pick = list(dict.fromkeys(pick))[:200]
    sample = {"monthEnds": [m.isoformat() for m in month_ends], "rf": [None if not np.isfinite(x) else x for x in rf_vals],
              "riskAsOf": risk_asof.isoformat(), "bench": {k: [None if not np.isfinite(x) else x for x in v] for k, v in bench_me.items()},
              "benchCodes": {k: b["code"] for k, b in bench.items()}, "funds": []}
    for code in pick:
        r = next(x for x in work if x["code"] == code)
        s = series[code]
        res = results[code]
        sample["funds"].append({"code": code, "asset": C.SUBS[r["sub"]][0], "sub": r["sub"],
                                "d": [C.iso(x) for x in s.d], "v": [float(x) for x in s.v],
                                "out": {"tr": res["tr"], "sip": res["sip"], "risk": res.get("risk"), "roll": res.get("roll"),
                                        "mdd3": res.get("mdd3"), "inc": res["inc"], "incV": res["incV"],
                                        "bench": res.get("bench"), "edges": res.get("rollEdges")}})
    bench_series = {}
    for k, b in bench.items():
        s = series[b["code"]]
        bench_series[k] = {"d": [C.iso(x) for x in s.d], "v": [float(x) for x in s.v]}
    sample["benchSeries"] = bench_series
    save_gz(CACHE / "verify_sample.json.gz", sample)


if __name__ == "__main__":
    main()
