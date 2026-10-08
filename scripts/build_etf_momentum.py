#!/usr/bin/env python3
"""
build_etf_momentum.py
─────────────────────
Builds data/etf_momentum.json for etf_momentum.html (ETF Momentum Mode).

Universe   : every NSE-listed ETF in data/master_symbols.json (refreshed daily
             by update_symbols.py) merged with NSE's live ETF list, so newly
             listed ETFs are picked up automatically on the next run.
Prices     : 2 years of daily adjusted closes via yfinance, cleaned (bad-tick
             and unadjusted-split repair), then resampled to weekly closes on
             one shared trading calendar.
Benchmarks : several Indian indices (with ETF proxies as a fallback). The page
             lets users switch benchmark, so raw aligned weekly closes are
             stored and the classification is recomputed client-side.
Modes      : relative-rotation quadrants, computed identically here and in
             the page (see rrg() below and RRG() in etf_momentum.html):
               RS            = 100 * ETF / Benchmark
               RS-Ratio      = 100 + zscore(RS, 10 weeks)        (sd floored at 1% of RS)
               RS-Momentum   = 100 + zscore(RS-Ratio, 10 weeks)  (sd floored at 1.0)
             Accelerating   : RS-Ratio >= 100 and RS-Momentum >= 100
             Decelerating   : RS-Ratio >= 100 and RS-Momentum <  100
             Recovering     : RS-Ratio <  100 and RS-Momentum >= 100
             Underperforming: RS-Ratio <  100 and RS-Momentum <  100

Safety     : the output file is only replaced when quality gates pass, so a
             bad fetch never wipes the published data.

Usage      : python scripts/build_etf_momentum.py [--out data/etf_momentum.json]
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import math
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "data", "master_symbols.json")
DEFAULT_OUT = os.path.join(ROOT, "data", "etf_momentum.json")

WEEKS = 104            # weekly bars kept per series
N_RATIO = 10           # RS-Ratio z-score window (weeks)
N_MOM = 10             # RS-Momentum z-score window (weeks)
TRAIL = 8              # trail points used by the page
MIN_WEEKS = N_RATIO + N_MOM          # minimum valid weeks to classify (first RS-Momentum point)
FFILL_LIMIT = 2        # max consecutive missing weeks bridged
FLOOR_RATIO = 0.01     # RS moves under 1% of its level are noise (stops index trackers looking "strong")
FLOOR_MOM = 1.0        # matching floor for RS-Ratio swings

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("etf_momentum")

# id, label, group, yahoo candidates (first that validates wins)
BENCHMARKS = [
    ("NIFTY50",    "Nifty 50",             "Broad Market", ["^NSEI", "NIFTYBEES.NS"]),
    ("NIFTY100",   "Nifty 100",            "Broad Market", ["^CNX100"]),
    ("NIFTYNEXT50","Nifty Next 50",        "Broad Market", ["^NSMIDCP", "JUNIORBEES.NS"]),
    ("NIFTY500",   "Nifty 500",            "Broad Market", ["^CRSLDX"]),
    ("SENSEX",     "BSE Sensex",           "Broad Market", ["^BSESN"]),
    ("MIDCAP100",  "Nifty Midcap 100",     "Size",         ["NIFTY_MIDCAP_100.NS", "^CNXMIDCAP"]),
    ("MIDCAP150",  "Nifty Midcap 150",     "Size",         ["MID150BEES.NS"]),
    ("SMALLCAP100","Nifty Smallcap 100",   "Size",         ["^CNXSC"]),
    ("BANKNIFTY",  "Nifty Bank",           "Sectoral",     ["^NSEBANK", "BANKBEES.NS"]),
    ("NIFTYIT",    "Nifty IT",             "Sectoral",     ["^CNXIT", "ITBEES.NS"]),
    ("GOLD",       "Gold (Domestic)",      "Commodity",    ["GOLDBEES.NS"]),
]
DEFAULT_BENCH = "NIFTY50"

AMC_NAMES = {
    "ABSL": "Aditya Birla SL", "BIRLASLAMC": "Aditya Birla SL", "AXISAMC": "Axis",
    "BAJAJAMC": "Bajaj Finserv", "BANDHANAMC": "Bandhan", "BARODAAMC": "Baroda BNP",
    "DSPAMC": "DSP", "EDELAMC": "Edelweiss", "GROWWAMC": "Groww", "HDFCAMC": "HDFC",
    "HSBCAMC": "HSBC", "ICICIPRAMC": "ICICI Pru", "INVESCOAMC": "Invesco",
    "KOTAKMAMC": "Kotak", "LICNAMC": "LIC MF", "MIRAEAMC": "Mirae Asset",
    "MOTILALAMC": "Motilal Oswal", "NAVIAMC": "Navi", "NIPPONAMC": "Nippon India",
    "QUANTUMAMC": "Quantum", "SBIAMC": "SBI", "TATAAMC": "Tata", "UTIAMC": "UTI",
    "ZERODHAAMC": "Zerodha", "AONEAMC": "Angel One", "UNIONAMC": "Union",
    "SHRIRAMAMC": "Shriram", "CAPITALMIND": "Capitalmind", "PPFASAMC": "PPFAS",
    "WHITEOAKAMC": "WhiteOak", "360ONEAMC": "360 ONE", "SAMCOAMC": "Samco",
}


_AMC_PREFIX = [
    ("NIPINDETF", "Nippon India"), ("NIP IND", "Nippon India"), ("NIPPON", "Nippon India"), ("RELCAP", "Nippon India"),
    ("ICICIPRU", "ICICI Pru"), ("ICICIPR", "ICICI Pru"), ("MOTILAL", "Motilal Oswal"), ("BIRLASL", "Aditya Birla SL"),
    ("ABSL", "Aditya Birla SL"), ("HDFC", "HDFC"), ("KOTAK", "Kotak"), ("INVESCO", "Invesco"), ("RELIGARE", "Invesco"),
    ("LICMF", "LIC MF"), ("LICN", "LIC MF"), ("TATAAM", "Tata"), ("BFAM", "Bajaj Finserv"), ("BAJAJ", "Bajaj Finserv"),
    ("BARODA", "Baroda BNP"), ("CHOICE", "Choice"), ("JIOBLACKROCK", "Jio BlackRock"), ("SHRIRAM", "Shriram"),
    ("SBI", "SBI"), ("HSBC", "HSBC"), ("MIRAE", "Mirae Asset"), ("DSP", "DSP"), ("GROWW", "Groww"), ("EDEL", "Edelweiss"),
    ("UTI", "UTI"), ("AXIS", "Axis"), ("ZERODHA", "Zerodha"), ("AONE", "Angel One"), ("ANGEL", "Angel One"),
    ("360ONE", "360 ONE"), ("BANDHAN", "Bandhan"), ("QUANTUM", "Quantum"), ("NAVI", "Navi"), ("UNION", "Union"),
    ("CAPITALMIND", "Capitalmind"), ("PPFAS", "PPFAS"), ("WHITEOAK", "WhiteOak"), ("SAMCO", "Samco"), ("TATA", "Tata"),
]


def amc_of(raw: str) -> str:
    if not raw:
        return ""
    code = re.split(r"\s*-\s*", raw)[0].strip().upper().replace(" ", "")
    if code in AMC_NAMES:
        return AMC_NAMES[code]
    for pre, name in _AMC_PREFIX:
        if code.startswith(pre):
            return name
    return ""


# ── Category tagging ──────────────────────────────────────────────────────────
_CAT_RULES = [
    ("Liquid & Debt", r"LIQUID|LIQ\b|LIQID|LIQETF|CASH|G-?SEC|GILT|BOND|SDL|T-?BILL|OVERNIGHT|MONEY ?MARKET|DEBT|IBX|BBETF|1D RATE|GSC\b|CRISIL"),
    ("Silver", r"SILVER|SILV|SLVR"),
    ("Gold", r"GOLD"),
    ("International", r"NASDAQ|MON100|MONQ|MAFANG|FANG|HANG ?SENG|HNGSNG|S&P ?500|SP500|MASPTOP|NYSE|MSCI ?(US|EAFE|WORLD|CHINA|EM\b)|HK ?TECH|GLOBAL|JAPAN|TAIWAN|CHINA|US ?TECH"),
    ("Banking & Financial", r"BANK|BNK|BAN\b|NIFBAN|PVTBAN|BANETF|PVTBK|FINANCIAL|FIN ?SERV|FINNIFTY|NIFTY ?FIN|BFSI|INSUR|CAPITAL ?MARKET|CAPM|MOCAPITAL|\bPB\b|ETFPB|SBIBPB|NPBET|FINIETF|\bFS\b|MAFSETF"),
    ("IT & Technology", r"\bIT\b|ITBEES|ITETF|ITADD|ITAXIS|ITBETA|ITIETF|ETFIT\b|NIFTYIT|NIFIT|TECH|INTERNET|DIGITAL|GROWWNET\b"),
    ("Sectoral & Thematic", r"PHARMA|HEALTH|HOSPI|AUTO|\bEV\b|EVINDIA|EVIETF|GROWWEV|FMCG|CONSUM|\bCONS\b|ETFCON\b|INFRA|ENERGY|POWER|METAL|REALTY|RLTY|CEMNT|CEMENT|CHEM|DEFENCE|DEFENSE|DEFNC|RAIL|TOURISM|MOTOUR|COMMODIT|COMMO|MANUFACT|MAKEINDIA|MFG|SERVICE|\bIPO\b|MOIPO|SELECTIPO|ESG|MNC|CPSE|PSE\b|BHARAT ?22|ICICIB22|PSU|SHARIAH|OIL|MEDIA|HOUSING|MOBILITY"),
    ("Factor & Smart Beta", r"ALPHA|ALPL|LOW ?VOL|LOVOL|QUALITY|QLTY|QUAL|MOMENT|MOM30|MOMGF|VALUE|VAL\d|VALETF|EQUAL|EQW|EQL|DIV|MULTI ?FACT|MULTIMQ|TMMQ|\bMQ|GROWTH|SMART|NV20|SECLED|ENHANCED"),
    ("Next 50, Mid & Small Cap", r"MID|MC150|SMALL|SML|SC250|MICRO|JUNIOR|NEXT ?50|NXT50|NN50|NEXT ?30|M100\b"),
    ("Broad Market", r"NIFTY|SENSEX|\bSEN|SENETF|BSE|TOTAL|N200|MULTICAP|FLEXI|MSCI|LARGE|TOP ?\d|BEES|N50|M50|NETF|TNIDETF|ELM250|NIF|SETF|NFNHGP|NETFSEN|BHARAT|NIFTY ?50|\bSENSEX"),
]


def categorise(symbol: str, name: str, underlying: str) -> str:
    """Asset class (debt/gold/silver/international) from symbol or underlying first,
    then the underlying index text, then symbol/name as the fallback."""
    both = f"{symbol} {underlying}".upper()
    for cat, pat in _CAT_RULES[:4]:
        if re.search(pat, both):
            return cat
    for hay in (underlying.upper(), f"{symbol} {name} {underlying}".upper()):
        if not hay.strip():
            continue
        for cat, pat in _CAT_RULES:
            if re.search(pat, hay):
                return cat
    return "Other"


# ── Universe ──────────────────────────────────────────────────────────────────
def load_master() -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        with open(MASTER, encoding="utf-8") as fh:
            rows = json.load(fh)
        for r in rows:
            if r.get("type") == "ETF" and r.get("exchange") == "NSE":
                sym = str(r.get("symbol", "")).strip().upper()
                if sym:
                    out[sym] = {"raw": str(r.get("name", "")).strip()}
    except Exception as exc:  # noqa: BLE001
        log.warning(f"master_symbols.json unreadable: {exc}")
    log.info(f"master_symbols ETFs : {len(out)}")
    return out


def load_nse_list() -> dict[str, dict]:
    """Best-effort fetch of NSE's ETF list (adds underlying + full names)."""
    out: dict[str, dict] = {}
    try:
        import pandas as pd
        import requests
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/csv,application/octet-stream,*/*",
            "Referer": "https://www.nseindia.com/",
        })
        try:
            s.get("https://www.nseindia.com", timeout=15)
        except Exception:  # noqa: BLE001
            pass
        r = s.get("https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv", timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip() for c in df.columns]
        sym_c = next((c for c in df.columns if "symbol" in c.lower()), None)
        und_c = next((c for c in df.columns if "underlying" in c.lower()), None)
        nam_c = next((c for c in df.columns if "security" in c.lower() or "name" in c.lower()), None)
        for _, row in df.iterrows():
            sym = str(row.get(sym_c, "")).strip().upper() if sym_c else ""
            if not sym or sym == "NAN":
                continue
            out[sym] = {
                "full": str(row.get(nam_c, "")).strip() if nam_c else "",
                "underlying": str(row.get(und_c, "")).strip() if und_c else "",
            }
        log.info(f"NSE ETF list        : {len(out)}")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"NSE ETF list skipped: {exc}")
    return out


def load_previous(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def nice_name(sym: str, master: dict, nse: dict, prev_names: dict) -> tuple[str, str, str]:
    """Return (display name, AMC, underlying)."""
    n = nse.get(sym, {})
    full = (n.get("full") or "").strip()
    und = (n.get("underlying") or "").strip()
    if full.lower() in ("nan", ""):
        full = ""
    if und.lower() == "nan":
        und = ""
    raw = master.get(sym, {}).get("raw", "")
    amc = amc_of(raw)
    prev = prev_names.get(sym, {})
    if not und and prev.get("u"):          # NSE list unavailable this run → reuse last good metadata
        und = prev.get("u", "")
        full = full or prev.get("n", "")
    if not amc:
        amc = amc_of(full) or prev.get("a", "")
    cu = clean_underlying(und)
    if cu:
        full = cu if (_has_amc(cu) or not amc) else f"{amc} {cu}"
        if not re.search(r"\bETF\b", full, re.I):
            full += " ETF"
    elif not full or " " not in full:   # NSE security names are often run-together codes
        full = f"{amc} ETF · {sym}" if amc else sym
    return full, amc, und


_AMC_WORDS = ("ADITYA", "BIRLA", "ICICI", "MIRAE", "HDFC", "AXIS", "NIPPON", "SBI", "KOTAK", "MOTILAL", "UTI",
              "DSP", "GROWW", "EDELWEISS", "INVESCO", "TATA", "BANDHAN", "LIC ", "ZERODHA", "ANGEL", "BAJAJ",
              "BARODA", "HSBC", "360 ONE", "SHRIRAM", "UNION", "QUANTUM", "NAVI", "JIO", "CHOICE", "WHITEOAK")


def _has_amc(text: str) -> bool:
    t = f"{text.upper()} "
    return any(w in t for w in _AMC_WORDS)


def clean_underlying(u: str) -> str:
    u = (u or "").strip()
    if not u or u.lower() == "nan":
        return ""
    u = re.split(r"\s*-\s*based|\s+based on", u, flags=re.I)[0]
    u = re.sub(r"^domestic price of\s+", "", u, flags=re.I)
    u = re.sub(r"^commodity\s*-\s*", "", u, flags=re.I)
    u = re.sub(r"\s*\((?:TRI|PRI)\)\s*$", "", u, flags=re.I)
    u = re.sub(r"\s+(Total Returns? Index|TRI|Index)\s*$", "", u, flags=re.I)
    u = re.sub(r"\bIndex\b", "", u, flags=re.I)
    u = re.sub(r"\s{2,}", " ", u).strip(" -")
    if u.isupper():
        keep = {"CPSE", "PSU", "ETF", "BSE", "NSE", "MSCI", "IT", "FMCG", "ESG", "PSE", "MNC", "TRI", "US", "EV",
                "HDFC", "ICICI", "UTI", "DSP", "SBI", "LIC", "HSBC", "CRISIL", "BHARAT", "S&P"}
        u = " ".join(w if (w in keep or len(w) < 4) else w.title() for w in u.split())
    return u[:60]


# ── Price download ────────────────────────────────────────────────────────────
def download(tickers: list[str], period: str = "2y", chunk: int = 60) -> dict:
    """Return {ticker: pandas.DataFrame(Close, Volume)} for tickers that returned data."""
    import pandas as pd
    import yfinance as yf

    result: dict[str, "pd.DataFrame"] = {}

    def _one_batch(batch: list[str]) -> None:
        try:
            df = yf.download(batch, period=period, interval="1d", auto_adjust=True,
                             group_by="ticker", threads=True, progress=False)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"batch failed ({len(batch)}): {exc}")
            return
        if df is None or df.empty:
            return
        for t in batch:
            try:
                sub = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                sub = sub[["Close", "Volume"]].copy()
                sub = sub[pd.to_numeric(sub["Close"], errors="coerce") > 0].dropna(subset=["Close"])
                if len(sub) >= 5:
                    result[t] = sub
            except Exception:  # noqa: BLE001
                continue

    todo = list(dict.fromkeys(tickers))
    for attempt in range(3):
        pending = [t for t in todo if t not in result]
        if not pending:
            break
        if attempt:
            log.info(f"retry {attempt}: {len(pending)} tickers")
            time.sleep(4 * attempt)
        size = chunk if attempt == 0 else max(10, chunk // (2 * attempt))
        for i in range(0, len(pending), size):
            _one_batch(pending[i:i + size])
            time.sleep(1.0)
    # Batch downloads occasionally truncate a ticker's history; refetch short ones singly.
    short = [t for t in todo if t in result and len(result[t]) < 300]
    fixed = 0
    for t in short:
        try:
            h = yf.Ticker(t).history(period=period, interval="1d", auto_adjust=True)
            if h is not None and len(h) > len(result[t]) + 5:
                h = h[["Close", "Volume"]].copy()
                h = h[pd.to_numeric(h["Close"], errors="coerce") > 0].dropna(subset=["Close"])
                if len(h) > len(result[t]):
                    result[t] = h
                    fixed += 1
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    log.info(f"downloaded {len(result)}/{len(todo)} tickers; short re-fetched {len(short)}, extended {fixed}")
    return result


def refresh_latest(raw: dict, tk: str) -> None:
    """Re-query one ticker's last month and append sessions missing from the batch result."""
    try:
        import pandas as pd
        import yfinance as yf
        h = yf.Ticker(tk).history(period="1mo", interval="1d", auto_adjust=True)
        if h is None or h.empty:
            return
        h = h[["Close", "Volume"]]
        h = h[pd.to_numeric(h["Close"], errors="coerce") > 0].dropna(subset=["Close"])
        cur = raw[tk]
        last = cur.index[-1].date()
        newer = h[[ts.date() > last for ts in h.index]]
        if len(newer):
            newer.index = newer.index.tz_convert(cur.index.tz) if cur.index.tz is not None and newer.index.tz is not None else newer.index
            raw[tk] = pd.concat([cur, newer])
            log.info(f"refreshed {tk}: +{len(newer)} session(s) to {raw[tk].index[-1].date()}")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"refresh {tk} failed: {exc}")


# ── Cleaning ──────────────────────────────────────────────────────────────────
SPLIT_FACTORS = (2, 3, 4, 5, 10, 20, 25, 50, 100)


def clean_series(dates: list, closes: list[float]) -> tuple[list, list[float], list[str]]:
    """Remove one-day bad ticks and repair un-adjusted splits. Returns flags."""
    flags: list[str] = []
    d, c = list(dates), [float(x) for x in closes]
    # 1. one-bar spikes that fully reverse (bad prints)
    i = 1
    while i < len(c) - 1:
        r1 = c[i] / c[i - 1] - 1
        r2 = c[i + 1] / c[i] - 1
        if abs(r1) > 0.25 and abs(r2) > 0.2 and (r1 > 0) != (r2 > 0) and abs(c[i + 1] / c[i - 1] - 1) < 0.1:
            del d[i]; del c[i]
            if "bad-tick" not in flags:
                flags.append("bad-tick")
            continue
        i += 1
    # 2. persistent drops matching a split ratio → scale older history
    cut = 0
    for i in range(1, len(c)):
        if c[i] <= 0:
            continue
        ratio = c[i - 1] / c[i]
        if ratio > 1.8:
            for k in SPLIT_FACTORS:
                if abs(ratio / k - 1) < (0.06 if k < 5 else 0.12):
                    for j in range(i):
                        c[j] /= k
                    flags.append(f"split-1:{k}")
                    break
            else:
                cut = i                      # unexplained break → keep only the consistent recent segment
    if cut:
        d, c = d[cut:], c[cut:]
        flags.append("reset")
    # 3. a wild final print (no next bar to confirm it) is dropped
    while len(c) >= 6:
        ref = sorted(c[-6:-1])[2]
        if c[-1] / ref > 1.8 or c[-1] / ref < 1 / 1.8:
            d.pop(); c.pop()
            if "bad-last" not in flags:
                flags.append("bad-last")
            continue
        break
    return d, c, flags


# ── Weekly calendar ───────────────────────────────────────────────────────────
def weekly_last(dates: list, closes: list[float]) -> dict[str, tuple[str, float]]:
    """Map ISO week key → (last trading date in that week, close)."""
    out: dict[str, tuple[str, float]] = {}
    for dt, px in zip(dates, closes):
        iso = dt.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        out[key] = (dt.strftime("%Y-%m-%d"), px)   # later dates overwrite → week close
    return out


def to_rounded(x: float | None) -> float | None:
    if x is None or not math.isfinite(x):
        return None
    if x >= 100:
        return round(x, 2)
    if x >= 1:
        return round(x, 3)
    return round(x, 5)


# ── RRG maths (mirrored 1:1 in the page's JavaScript) ─────────────────────────
def _z(win: list[float], rel_floor: float = 0.0, abs_floor: float = 0.0) -> float | None:
    n = len(win)
    m = sum(win) / n
    var = sum((v - m) ** 2 for v in win) / n
    if var <= 1e-18:
        return None
    sd = max(math.sqrt(var), abs(m) * rel_floor, abs_floor)
    return (win[-1] - m) / sd


def rrg(etf: list, bench: list, n_ratio: int = N_RATIO, n_mom: int = N_MOM,
        f_ratio: float = FLOOR_RATIO, f_mom: float = FLOOR_MOM) -> tuple[list, list]:
    L = len(etf)
    rs = [None] * L
    for i in range(L):
        e, b = etf[i], bench[i]
        if e is not None and b is not None and b > 0 and e > 0:
            rs[i] = 100.0 * e / b
    rsr = [None] * L
    for i in range(n_ratio - 1, L):
        win = rs[i - n_ratio + 1:i + 1]
        if all(v is not None for v in win):
            z = _z(win, rel_floor=f_ratio)
            rsr[i] = None if z is None else 100.0 + z
    rsm = [None] * L
    for i in range(n_mom - 1, L):
        win = rsr[i - n_mom + 1:i + 1]
        if all(v is not None for v in win):
            z = _z(win, abs_floor=f_mom)
            rsm[i] = None if z is None else 100.0 + z
    return rsr, rsm


def mode_of(r: float | None, m: float | None) -> str | None:
    if r is None or m is None:
        return None
    if r >= 100:
        return "A" if m >= 100 else "D"
    return "R" if m >= 100 else "U"


# ── Build ─────────────────────────────────────────────────────────────────────
def pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b <= 0:
        return None
    return round((a / b - 1) * 100, 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    prev = load_previous(args.out)
    prev_names = {e["s"]: e for e in prev.get("etfs", []) if isinstance(e, dict) and e.get("s")}

    master = load_master()
    nse = load_nse_list()
    universe = sorted(set(master) | set(nse) | set(prev_names))
    universe = [s for s in universe if re.fullmatch(r"[A-Z0-9&\-]{2,20}", s)]
    if not universe:
        log.error("empty ETF universe — aborting")
        return 1
    log.info(f"universe            : {len(universe)} ETFs")

    bench_syms = [c for _, _, _, cands in BENCHMARKS for c in cands]
    etf_syms = [f"{s}.NS" for s in universe]
    raw = download(bench_syms + etf_syms)

    # ── as-of date: the latest session most ETFs have traded; indices must reach it ──
    def last_day(tk: str):
        df = raw.get(tk)
        return df.index[-1].date() if df is not None and len(df) else None

    etf_last = Counter(d for d in (last_day(t) for t in etf_syms) if d)
    if not etf_last:
        log.error("no ETF prices downloaded — keeping previous file")
        return 1
    market_last = max(d for d, n in etf_last.items() if n >= 0.2 * sum(etf_last.values()))
    for tk in bench_syms:
        if tk in raw and last_day(tk) and last_day(tk) < market_last:
            refresh_latest(raw, tk)              # batch feeds sometimes omit the latest index print
    bench_last = last_day(BENCHMARKS[0][3][0]) or last_day(BENCHMARKS[0][3][-1])
    as_of = min(market_last, bench_last) if bench_last else market_last
    if bench_last and bench_last < market_last:
        log.warning(f"Nifty 50 last print {bench_last} behind ETFs {market_last}; aligning all series to {as_of}")
    log.info(f"as-of session       : {as_of}")
    prev_asof = prev.get("asOf")
    if prev_asof and str(as_of) < prev_asof:
        log.warning(f"source data ({as_of}) is older than published data ({prev_asof}) — keeping previous file")
        return 0

    # ── benchmarks (Nifty 50 defines the trading calendar) ──
    series: dict[str, tuple[list, list, list]] = {}

    def prep(tk: str):
        if tk in series:
            return series[tk]
        df = raw.get(tk)
        if df is None:
            return None
        df = df[[ts.date() <= as_of for ts in df.index]]   # one common session for every series
        if not len(df):
            return None
        dates = [ts.to_pydatetime().replace(tzinfo=None) for ts in df.index]
        closes = [float(x) for x in df["Close"].tolist()]
        vols = [float(x) if x == x else 0.0 for x in df["Volume"].tolist()]
        d, c, flags = clean_series(dates, closes)
        vol_map = dict(zip(dates, vols))
        v = [vol_map.get(x, 0.0) for x in d]
        series[tk] = (d, c, v, flags)
        return series[tk]

    bench_out = []
    bench_week_maps = {}
    for bid, label, group, cands in BENCHMARKS:
        for tk in cands:
            s = prep(tk)
            if s and len(s[0]) >= 200:
                wk = weekly_last(s[0], s[1])
                if len(wk) >= 60:
                    bench_week_maps[bid] = wk
                    bench_out.append({"id": bid, "name": label, "group": group,
                                      "proxy": not tk.startswith("^") and tk != "NIFTY_MIDCAP_100.NS",
                                      "last": to_rounded(s[1][-1]), "lastDate": s[0][-1].strftime("%Y-%m-%d"),
                                      "_tk": tk})
                    log.info(f"benchmark {bid:<12} ← {tk}")
                    break
        else:
            log.warning(f"benchmark {bid} unavailable")

    if DEFAULT_BENCH not in bench_week_maps:
        log.error("Nifty 50 benchmark unavailable — keeping previous file")
        return 1

    cal_map = bench_week_maps[DEFAULT_BENCH]
    week_keys = sorted(cal_map)[-WEEKS:]
    week_dates = [cal_map[k][0] for k in week_keys]
    last_trade = week_dates[-1]

    def align(wk: dict) -> list:
        vals, gap = [], 0
        last = None
        for k in week_keys:
            if k in wk:
                last, gap = wk[k][1], 0
                vals.append(wk[k][1])
            else:
                gap += 1
                vals.append(last if (last is not None and gap <= FFILL_LIMIT) else None)
        return vals

    bench_closes = {}
    for b in bench_out:
        b["c"] = [to_rounded(v) for v in align(bench_week_maps[b["id"]])]
        bench_closes[b["id"]] = b["c"]
        del b["_tk"]

    # ── ETFs ──
    etfs, failed, insufficient = [], [], 0
    stale_cut = datetime.strptime(last_trade, "%Y-%m-%d")
    for sym in universe:
        name, amc, und = nice_name(sym, master, nse, prev_names)
        cat = categorise(sym, name, und)
        s = prep(f"{sym}.NS")
        rec = {"s": sym, "n": name, "a": amc, "u": und, "k": cat}
        if not s or len(s[0]) < 5:
            failed.append(sym)
            rec.update({"q": "nodata", "c": []})
            etfs.append(rec)
            continue
        d, c, v, flags = s
        weekly = align(weekly_last(d, c))
        rec["c"] = [to_rounded(x) for x in weekly]
        last_px, last_dt = c[-1], d[-1]
        rec["p"] = to_rounded(last_px)
        rec["d"] = last_dt.strftime("%Y-%m-%d")

        def back(n: int):
            return c[-1 - n] if len(c) > n else None
        rec["r"] = {"1w": pct(last_px, back(5)), "1m": pct(last_px, back(21)),
                    "3m": pct(last_px, back(63)), "6m": pct(last_px, back(126)),
                    "1y": pct(last_px, back(250))}
        yr = c[-250:]
        rec["h52"] = to_rounded(max(yr)); rec["l52"] = to_rounded(min(yr))
        tv = [px * vv for px, vv in zip(c[-20:], v[-20:])]
        rec["tv"] = round(sum(tv) / len(tv) / 1e7, 3) if tv else 0.0   # ₹ crore / day
        zero_days = sum(1 for vv in v[-20:] if vv <= 0)
        valid_weeks = 0                       # contiguous recent history (RRG needs unbroken windows)
        for x in reversed(weekly):
            if x is None:
                break
            valid_weeks += 1
        q = "ok"
        if (stale_cut - last_dt).days > 7:
            q = "stale"
        elif valid_weeks < MIN_WEEKS:
            q = "short"
        elif rec["tv"] < 0.01 or zero_days >= 10:
            q = "thin"
        rec["q"] = q
        if flags:
            rec["f"] = flags
        if q in ("stale", "short"):
            insufficient += 1
        etfs.append(rec)

    # ── reference classification on the default benchmark (page + CI cross-check) ──
    ref: dict[str, dict] = {}
    counts = {"A": 0, "D": 0, "R": 0, "U": 0}
    for b in [x for x in bench_out if x["id"] == DEFAULT_BENCH]:
        bc = bench_closes[b["id"]]
        out = {}
        for e in etfs:
            if e["q"] in ("nodata", "stale", "short") or not e["c"]:
                continue
            r, m = rrg(e["c"], bc)
            mo = mode_of(r[-1], m[-1])
            if mo:
                out[e["s"]] = [round(r[-1], 4), round(m[-1], 4), mo]
                if b["id"] == DEFAULT_BENCH:
                    counts[mo] += 1
        ref[b["id"]] = out

    classified = len(ref.get(DEFAULT_BENCH, {}))
    # ── quality gates ──
    with_data = sum(1 for e in etfs if e["q"] != "nodata")
    if with_data < max(50, int(0.5 * len(universe))):
        log.error(f"only {with_data}/{len(universe)} ETFs returned prices — keeping previous file")
        return 1
    if classified < 40:
        log.error(f"only {classified} ETFs classified — keeping previous file")
        return 1
    prev_cls = prev.get("stats", {}).get("classified", 0)
    if prev_cls and classified < 0.6 * prev_cls:
        log.error(f"classified dropped {prev_cls} → {classified} — keeping previous file")
        return 1

    payload = {
        "v": 1,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asOf": last_trade,
        "params": {"interval": "1wk", "nRatio": N_RATIO, "nMom": N_MOM, "trail": TRAIL,
                   "floorRatio": FLOOR_RATIO, "floorMom": FLOOR_MOM,
                   "minWeeks": MIN_WEEKS, "defaultBench": DEFAULT_BENCH},
        "weeks": week_dates,
        "benchmarks": bench_out,
        "etfs": etfs,
        "ref": ref,
        "stats": {"universe": len(universe), "withData": with_data, "classified": classified,
                  "insufficient": insufficient, "noData": len(failed), "counts": counts},
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)
    os.replace(tmp, args.out)
    log.info(f"wrote {args.out}  ({os.path.getsize(args.out)/1024:.0f} KB)  "
             f"classified={classified} counts={counts} noData={len(failed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
