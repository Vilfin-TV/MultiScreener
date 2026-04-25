#!/usr/bin/env python3
"""
VilfinTV — Daily Symbol Updater
================================
Downloads equity / ETF / mutual-fund lists from official sources:
  • India  : NSE equity list, NSE ETF list, AMFI mutual-fund NAV file
  • US     : NASDAQ Trader FTP (covers NASDAQ, NYSE, AMEX, ARCA, …)
  • Japan  : JPX (Tokyo Stock Exchange) company list + ETF list

Normalises everything into:
  [{"symbol": "…", "name": "…", "exchange": "…", "type": "Stock|ETF|Fund"}]

Output : data/master_symbols.json  (relative to repo root)
"""

import io
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_FILE  = REPO_ROOT / "data" / "master_symbols.json"

# ── HTTP session ──────────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
})


def fetch(url: str, timeout: int = 45, retries: int = 3, **kw) -> requests.Response:
    """GET with retries and back-off."""
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=timeout, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            log.warning(f"  attempt {attempt}/{retries} failed for {url}: {exc}")
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"All {retries} attempts failed for {url}")


# ── Normaliser ────────────────────────────────────────────────────────────────
def make(symbol: str, name: str, exchange: str, type_: str) -> dict | None:
    s = str(symbol).strip().upper()
    n = str(name).strip()
    # Discard blanks, header echoes, and absurdly long tokens
    if not s or s in {"NAN", "SYMBOL", "CODE", "-", "N/A"} or len(s) > 20:
        return None
    if not n or n.upper() in {"NAN", "NAME", "COMPANY NAME", "-"}:
        n = s  # fall back to symbol as display name
    return {"symbol": s, "name": n, "exchange": exchange, "type": type_}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA SOURCES
# ═══════════════════════════════════════════════════════════════════════════════

# ── India: NSE Equity ─────────────────────────────────────────────────────────
def nse_equity() -> list[dict]:
    url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
    try:
        # NSE requires a prior visit to set cookies
        SESSION.get("https://www.nseindia.com", timeout=15)
        r = fetch(url)
        df = pd.read_csv(io.StringIO(r.text))
        # Columns: SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, …
        sym_col  = next((c for c in df.columns if "symbol" in c.lower()), None)
        name_col = next((c for c in df.columns if "name" in c.lower()), None)
        out = []
        for _, row in df.iterrows():
            rec = make(
                row.get(sym_col, "") if sym_col else "",
                row.get(name_col, "") if name_col else "",
                "NSE", "Stock",
            )
            if rec:
                out.append(rec)
        log.info(f"NSE equity   : {len(out):>6,} records")
        return out
    except Exception as e:
        log.warning(f"NSE equity skipped: {e}")
        return []


# ── India: NSE ETF ────────────────────────────────────────────────────────────
def nse_etf() -> list[dict]:
    url = "https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv"
    try:
        SESSION.get("https://www.nseindia.com", timeout=15)
        r = fetch(url)
        df = pd.read_csv(io.StringIO(r.text))
        sym_col  = next((c for c in df.columns if "symbol" in c.lower()), None)
        name_col = next((c for c in df.columns
                         if "security" in c.lower() or "name" in c.lower()), None)
        out = []
        for _, row in df.iterrows():
            rec = make(
                row.get(sym_col, "") if sym_col else "",
                row.get(name_col, "") if name_col else "",
                "NSE", "ETF",
            )
            if rec:
                out.append(rec)
        log.info(f"NSE ETF      : {len(out):>6,} records")
        return out
    except Exception as e:
        log.warning(f"NSE ETF skipped: {e}")
        return []


# ── India: AMFI Mutual Funds ──────────────────────────────────────────────────
def amfi_funds() -> list[dict]:
    """
    NAVAll.txt format (semicolon-separated):
      SchemeCode;ISINGrowth;ISINDivReinvest;SchemeName;NAV;RepurchasePrice;SalePrice;Date
    Category/AMC header lines have no semicolons (or fewer than 5 fields).
    """
    url = "https://www.amfiindia.com/spages/NAVAll.txt"
    try:
        r = fetch(url)
        out = []
        for line in r.text.splitlines():
            parts = line.strip().split(";")
            if len(parts) < 5:
                continue               # header / blank
            code = parts[0].strip()
            name = parts[3].strip()
            if not code.isdigit():
                continue               # still a header
            rec = make(code, name, "AMFI", "Fund")
            if rec:
                out.append(rec)
        log.info(f"AMFI funds   : {len(out):>6,} records")
        return out
    except Exception as e:
        log.warning(f"AMFI skipped: {e}")
        return []


# ── US: NASDAQ Trader FTP (covers all US exchanges) ──────────────────────────
def nasdaq_us() -> list[dict]:
    """
    nasdaqlisted.txt  — pipe-separated, NASDAQ-listed stocks
    otherlisted.txt   — pipe-separated, NYSE / AMEX / ARCA / BATS stocks
    Footer line starts with "File Creation Time".
    """
    sources = [
        ("https://ftp.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",  "NASDAQ"),
        ("https://ftp.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",   "NYSE"),
    ]
    out = []
    for url, default_exch in sources:
        try:
            r = fetch(url)
            lines = r.text.splitlines()
            for line in lines[1:]:                      # skip header row
                if line.startswith("File Creation"):    # skip footer
                    break
                parts = line.split("|")
                if len(parts) < 2:
                    continue
                symbol = parts[0].strip()
                name   = parts[1].strip()
                # otherlisted.txt has Exchange in col index 4
                exch = default_exch
                if default_exch == "NYSE" and len(parts) > 4:
                    exch_raw = parts[4].strip()
                    exch = {
                        "A": "AMEX", "N": "NYSE", "P": "ARCA",
                        "Z": "BATS", "V": "IEXG",
                    }.get(exch_raw, exch_raw or "NYSE")
                # Skip test symbols (contain $ or are purely numeric)
                if "$" in symbol or symbol.isdigit():
                    continue
                rec = make(symbol, name, exch, "Stock")
                if rec:
                    out.append(rec)
            log.info(f"US {default_exch:<8}: {len(out):>6,} records (cumulative)")
        except Exception as e:
            log.warning(f"US {default_exch} skipped: {e}")
    log.info(f"US total     : {len(out):>6,} records")
    return out


# ── Japan: JPX Listed Companies (English XLSX) ────────────────────────────────
def jpx_equity() -> list[dict]:
    """
    JPX publishes a daily-refreshed XLSX of all TSE-listed companies.
    Columns include: Code, Name (English), Market Division, Scale Category, …
    """
    url = ("https://www.jpx.co.jp/markets/statistics-equities/misc/"
           "tvdivq00000001vg-att/data_e.xlsx")
    try:
        r = fetch(url, timeout=60)
        df = pd.read_excel(io.BytesIO(r.content), header=0, engine="openpyxl")
        code_col = next((c for c in df.columns if "code" in str(c).lower()), None)
        name_col = next((c for c in df.columns if "name" in str(c).lower()), None)
        out = []
        for _, row in df.iterrows():
            code = str(row[code_col]).strip() if code_col else ""
            name = str(row[name_col]).strip() if name_col else ""
            rec = make(code, name, "JPX", "Stock")
            if rec:
                out.append(rec)
        log.info(f"JPX equity   : {len(out):>6,} records")
        return out
    except Exception as e:
        log.warning(f"JPX equity skipped: {e}")
        return []


# ── Japan: JPX ETF / ETN List ─────────────────────────────────────────────────
def jpx_etf() -> list[dict]:
    url = ("https://www.jpx.co.jp/markets/products/etfs-and-etns/search/"
           "b5b4pj000000amnk-att/etf_etn.xlsx")
    try:
        r = fetch(url, timeout=60)
        df = pd.read_excel(io.BytesIO(r.content), header=0, engine="openpyxl")
        # Flexible column detection (English/Japanese headers vary)
        code_col = next((c for c in df.columns
                         if "code" in str(c).lower() or "コード" in str(c)), None)
        name_col = next((c for c in df.columns
                         if "name" in str(c).lower() or "銘柄" in str(c)), None)
        out = []
        for _, row in df.iterrows():
            code = str(row[code_col]).strip() if code_col else ""
            name = str(row[name_col]).strip() if name_col else ""
            rec = make(code, name, "JPX", "ETF")
            if rec:
                out.append(rec)
        log.info(f"JPX ETF      : {len(out):>6,} records")
        return out
    except Exception as e:
        log.warning(f"JPX ETF skipped: {e}")
        return []


# ── Japan: PayPay Bank NISA-Eligible Fund List ────────────────────────────────
def paypay_nisa() -> list[dict]:
    """
    PayPay Bank publishes a CSV of NISA-eligible funds.
    URL format may change; we attempt a best-effort download.
    """
    url = ("https://www.paypay-bank.co.jp/service/fund/data/"
           "nisa_eligible_list.csv")
    try:
        r = fetch(url, timeout=30)
        df = pd.read_csv(io.StringIO(r.text), encoding="utf-8-sig")
        code_col = next((c for c in df.columns
                         if "code" in str(c).lower() or "コード" in str(c)), None)
        name_col = next((c for c in df.columns
                         if "name" in str(c).lower() or "ファンド" in str(c)
                         or "名称" in str(c)), None)
        out = []
        for _, row in df.iterrows():
            code = str(row[code_col]).strip() if code_col else ""
            name = str(row[name_col]).strip() if name_col else ""
            rec = make(code, name, "NISA-JP", "Fund")
            if rec:
                out.append(rec)
        log.info(f"PayPay NISA  : {len(out):>6,} records")
        return out
    except Exception as e:
        log.warning(f"PayPay NISA skipped (expected if URL changed): {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

FETCHERS = [
    ("NSE Equity",    nse_equity),
    ("NSE ETF",       nse_etf),
    ("AMFI Funds",    amfi_funds),
    ("US Stocks",     nasdaq_us),
    ("JPX Equity",    jpx_equity),
    ("JPX ETF",       jpx_etf),
    ("PayPay NISA",   paypay_nisa),
]


def main() -> None:
    log.info("═" * 52)
    log.info("  VilfinTV Symbol Updater — starting")
    log.info("═" * 52)

    all_records: list[dict] = []

    for label, fn in FETCHERS:
        log.info(f"── {label} ──")
        try:
            records = fn()
            all_records.extend(records)
        except Exception as exc:
            log.error(f"Unexpected error in {label}: {exc}")

    # ── Deduplicate on (symbol, exchange) ────────────────────────────────────
    seen: set[tuple] = set()
    unique: list[dict] = []
    for rec in all_records:
        key = (rec["symbol"], rec["exchange"])
        if key not in seen:
            seen.add(key)
            unique.append(rec)

    # ── Sort: exchange priority, then symbol alphabetically ─────────────────
    exch_order = {"NSE": 0, "BSE": 1, "AMFI": 2, "NASDAQ": 3, "NYSE": 4,
                  "AMEX": 5, "ARCA": 6, "JPX": 7, "NISA-JP": 8}
    unique.sort(key=lambda r: (exch_order.get(r["exchange"], 99), r["symbol"]))

    log.info("═" * 52)
    log.info(f"  Total unique symbols : {len(unique):,}")
    log.info("═" * 52)

    if not unique:
        log.error("No records collected — aborting to preserve existing file.")
        sys.exit(1)

    # ── Write output ──────────────────────────────────────────────────────────
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(unique, fh, ensure_ascii=False, separators=(",", ":"))

    size_kb = OUT_FILE.stat().st_size / 1024
    log.info(f"✅  Saved → {OUT_FILE}  ({size_kb:,.1f} KB)")


if __name__ == "__main__":
    main()
