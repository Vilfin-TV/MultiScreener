#!/usr/bin/env python3
"""Portfolio P/E of every equity-oriented fund → data/mf/fund_pe.json.

Uses each fund's latest monthly portfolio (top holdings with ISINs, data/mf/p/<sub>.json) and the exchange's daily
stock P/E file. A fund's P/E is the weighted harmonic mean over the holdings that have a positive P/E
(Σw / Σ(w / P/E) — i.e. the price paid for each rupee of the portfolio's earnings); loss-making or unlisted
holdings are left out and the share of the equity holdings covered is published with the figure.

Run daily from the MF screener workflow, before the Smart SIP planner. On any download failure the previously
published file is kept.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MF = ROOT / "data" / "mf"
OUT = MF / "fund_pe.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36",
      "Accept": "*/*", "Referer": "https://www.nseindia.com/"}
BASE = "https://nsearchives.nseindia.com/content/equities"
MIN_EQUITY = 60          # % of the portfolio in equity for a fund to get a P/E
log = logging.getLogger("fund_pe")


def fetch(s, url):
    for _ in range(3):
        try:
            r = s.get(url, timeout=45)
            if r.status_code == 200 and r.content:
                return r.content.decode("utf-8-sig", errors="replace")
            if r.status_code == 404:
                return None
        except Exception:  # noqa: BLE001
            pass
    return None


def stock_pe(s):
    """(as-of date, {ISIN: P/E}) from the latest daily P/E file and the listed-equity master."""
    pe_txt, as_of = None, None
    for i in range(10):
        d = date.today() - timedelta(days=i)
        pe_txt = fetch(s, f"{BASE}/peDetail/PE_{d:%d%m%y}.csv")
        if pe_txt and "SYMBOL" in pe_txt[:200]:
            as_of = d
            break
    master = fetch(s, f"{BASE}/EQUITY_L.csv")
    if not pe_txt or not master:
        return None, {}
    sym_isin = {}
    for row in csv.DictReader(io.StringIO(master)):
        row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        if row.get("SYMBOL") and row.get("ISIN NUMBER"):
            sym_isin[row["SYMBOL"]] = row["ISIN NUMBER"]
    out = {}
    for row in csv.DictReader(io.StringIO(pe_txt)):
        row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        try:
            pe = float(row.get("SYMBOL P/E") or "nan")
        except ValueError:
            continue
        isin = sym_isin.get(row.get("SYMBOL", ""))
        if isin and 0 < pe < 1000:
            out[isin] = pe
    return as_of, out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = requests.Session()
    s.headers.update(UA)
    as_of, pe = stock_pe(s)
    if len(pe) < 500:
        log.error("Stock P/E data unavailable (%d stocks) — keeping the published file", len(pe))
        return 0
    funds = {}
    for f in sorted((MF / "p").glob("*.json")):
        if f.name.startswith("_"):
            continue
        for code, p in (json.loads(f.read_text()) or {}).items():
            if ((p.get("mix") or {}).get("equity") or 0) < MIN_EQUITY:
                continue
            eq = [(h[2], h[3]) for h in p.get("top") or [] if len(h) >= 5 and h[4] == "equity" and h[2] and h[3]]
            tot = sum(w for w, _ in eq)
            have = [(w, pe[i]) for w, i in eq if i in pe]
            cw = sum(w for w, _ in have)
            if not have or tot <= 0 or cw / tot < 0.4:
                continue
            funds[code] = [round(cw / sum(w / x for w, x in have), 1), round(100 * cw / tot), p.get("asOf")]
    if len(funds) < 100:
        log.error("Only %d fund P/Es computed — keeping the published file", len(funds))
        return 0
    OUT.write_text(json.dumps({"v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "asOf": as_of.isoformat(), "stocks": len(pe), "cols": ["pe", "coverPct", "portfolioAsOf"],
                               "funds": funds}, separators=(",", ":")))
    log.info("Wrote %s: %d funds (stock P/E as of %s, %d stocks)", OUT, len(funds), as_of, len(pe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
