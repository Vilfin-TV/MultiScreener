#!/usr/bin/env python3
"""New Fund Offers (NFOs) for the India MF Screener → data/mf/nfo.json.

Source: the industry body's official list of schemes currently in their new-fund-offer period, plus each
scheme's official details (category, type, launch date, minimum amount, objective, load) and, where already
published, its scheme summary (offer close date, allotment and re-open dates, benchmark, riskometer, managers).

An offer that drops off the official list is kept for 45 days as "Closed" (with the date it was last listed),
so investors can still find a fund they saw recently. Run daily from the MF screener workflow.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mf_enrich as E  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mf" / "nfo.json"
KEEP_CLOSED_DAYS = 45
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*", "Referer": "https://www.amfiindia.com/"}
log = logging.getLogger("nfo")


def get(S, url, as_json=True):
    for _ in range(3):
        try:
            r = S.get(url, timeout=45)
            if r.status_code == 200:
                return r.json() if as_json else r.content.decode("utf-8-sig", errors="replace")
            if r.status_code == 404:
                return None
        except Exception:  # noqa: BLE001
            pass
    return None


def to_iso(v: str | None) -> str | None:
    v = (v or "").strip()
    if not v or v in ("-", "NA", "N/A"):
        return None
    v = v[:10] if re.match(r"\d{4}-\d{2}-\d{2}", v) else v
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%B %d, %Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def ssd_dates(xml_text: str) -> dict:
    """NFO open/close, allotment and re-open dates from a standard-layout scheme summary."""
    try:
        root = ET.fromstring(E.normalise_ssd(xml_text).lstrip("﻿").replace("ï»¿", "").encode("utf-8"))
    except ET.ParseError:
        return {}
    node = root.find("SchemeSummary")
    node = root if node is None else node
    f = {c.tag.lower(): E._clean(c.text) for c in node}
    return {k: to_iso(f.get(t)) for k, t in (("open", "nfo_open_date"), ("close", "nfo_close_date"),
                                             ("allot", "allotment_date"), ("reopen", "reopen_date"))}


def nice_cat(raw: str) -> str:
    left, _, right = (raw or "").partition(" - ")
    left, right = left.strip(), right.strip()
    if left.lower().startswith("index fund"):
        return "Index Fund · " + re.sub(r"\s+funds?$", "", right, flags=re.I)
    return right or left


def min_amount(text: str | None) -> float | None:
    m = re.search(r"([\d,]+(?:\.\d+)?)", (text or "").replace("Rs.", " ").replace("₹", " "))
    try:
        v = float(m.group(1).replace(",", "")) if m else None
    except ValueError:
        return None
    return v if v and v < 1e7 else None


def kind_of(cat: str, typ: str, name: str) -> str:
    c = f"{cat} {name}".lower()
    if "close" in (typ or "").lower() or "interval" in (typ or "").lower():
        return "closed"
    if "etf" in c and "fund of fund" not in c and "fof" not in c:
        return "etf"
    if "index" in c:
        return "index"
    if "fund of fund" in c or "fof" in c:
        return "fof"
    return "active"


def asset_of(cat: str, name: str) -> str:
    c = f"{cat} {name}".lower()
    if re.search(r"gold|silver|commodit", c):
        return "Commodities"
    if re.search(r"overseas|international|global|nasdaq|s&p 500|us equity", c):
        return "International"
    if re.search(r"hybrid|arbitrage|balanced|asset allocation|multi asset|equity savings|70:30|g-sec.*index|retirement|children", c):
        return "Hybrid"
    if re.search(r"debt|income|liquid|overnight|money market|gilt|bond|duration|credit|target maturity|sdl|crisil-ibx|crisil ibx|fixed maturity|psu", c):
        return "Debt"
    if re.search(r"equity|cap|index|etf|elss|focused|value|contra|dividend yield|sector|thematic|nifty|bse|sensex", c):
        return "Equity"
    return "Other"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    S = requests.Session()
    S.headers.update(UA)
    today = date.today().isoformat()
    prev = {}
    try:
        prev = {str(x["sid"]): x for x in json.loads(OUT.read_text()).get("nfos", [])}
    except Exception:  # noqa: BLE001
        pass
    j = get(S, f"{E.AMFI}/api/new-fund-offer")
    if not isinstance(j, dict) or not isinstance(j.get("NewFundOffer"), list):
        log.error("NFO list unavailable — keeping the published file")
        return 0
    live = [(it, g.get("MutualFund")) for g in j["NewFundOffer"] for it in (g.get("items") or []) if it.get("Scheme_Id")]
    log.info("Official NFO list: %d schemes", len(live))
    out = {}
    for it, amc in live:
        sid, mid = str(it["Scheme_Id"]), it.get("MF_Id")
        p = prev.get(sid) or {}
        d = get(S, f"{E.AMFI}/api/scheme-details?MF_ID={mid}&scheme_id={sid}")
        row = ((d or {}).get("data") or [{}])[0] if isinstance(d, dict) else {}
        x = get(S, f"{E.PORTAL}/spages/SSD_{sid}.xml", as_json=False)
        ss = E.parse_ssd(x) if x and re.search(r"<SchemeSummary|<root\b|<Workbook\b|<office:document\b", x[:4000]) else {}
        dt = ssd_dates(x) if ss else {}
        cat_raw = row.get("SchemeCat_Desc") or p.get("catRaw") or ""
        cat = nice_cat(cat_raw)
        typ = row.get("SchemeType_Desc") or p.get("type") or ""
        name = (row.get("Scheme_Name") or it.get("SchemeName") or "").strip()
        sid_pdf = p.get("sidDoc")
        if not sid_pdf:
            try:
                h = S.head(f"{E.PORTAL}/spages/{sid}.pdf", timeout=30, allow_redirects=True)
                sid_pdf = f"{E.PORTAL}/spages/{sid}.pdf" if h.status_code == 200 else None
            except Exception:  # noqa: BLE001
                sid_pdf = None
        out[sid] = {
            "sid": int(sid), "name": name, "amc": (row.get("MF_Name") or amc or "").strip(),
            "cat": cat, "catRaw": cat_raw, "type": typ, "kind": kind_of(cat_raw, typ, name), "asset": asset_of(cat_raw, name),
            "open": dt.get("open") or to_iso(row.get("Launch_Date")) or p.get("open"),
            "close": dt.get("close") or p.get("close"), "allot": dt.get("allot") or p.get("allot"),
            "reopen": dt.get("reopen") or p.get("reopen"),
            "minAmt": min_amount(row.get("Scheme_min_amt")) or min_amount(ss.get("minApp")) or p.get("minAmt"),
            "minTxt": E._clean(row.get("Scheme_min_amt"))[:160] or p.get("minTxt") or "",
            "objective": re.sub(r"\s+", " ", ss.get("objective") or E._clean(row.get("Scheme_Objective")) or p.get("objective") or "")[:900],
            "benchmark": ss.get("benchmark") or p.get("benchmark") or "",
            "risk": ss.get("riskometer") or ss.get("riskLaunch") or p.get("risk") or "",
            "managers": [m["name"] for m in (ss.get("managers") or [])][:4] or p.get("managers") or [],
            "load": (E.parse_exit_load(row.get("Scheme_load")) or E.parse_exit_load(ss.get("exitLoadSsd")) or p.get("load") or [])[:4],
            "maxTer": ss.get("maxTer") or p.get("maxTer") or "",
            "website": E._clean(row.get("AMC_Website")) or p.get("website") or "",
            "sidDoc": sid_pdf, "ssdDoc": f"{E.PORTAL}/spages/SSD_{sid}.pdf" if ss else p.get("ssdDoc"),
            "firstSeen": p.get("firstSeen") or today, "lastSeen": today, "status": "Open",
        }
        if out[sid]["close"] and out[sid]["close"] < today:
            out[sid]["status"] = "Closing"            # still listed, offer period ended (allotment pending)
    cutoff = (date.today() - timedelta(days=KEEP_CLOSED_DAYS)).isoformat()
    for sid, p in prev.items():
        if sid not in out and (p.get("lastSeen") or "") >= cutoff:
            out[sid] = {**p, "status": "Closed"}
    rows = sorted(out.values(), key=lambda r: (r["status"] != "Open", r["status"] == "Closed",
                                              r.get("close") or "9999", -(int(r["sid"]))))
    for r in rows:
        r["website"] = r["website"] if r["website"].startswith("http") else (f"https://{r['website']}" if r["website"] else "")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"v": 1, "generated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "asOf": today, "count": len(rows), "nfos": rows}, ensure_ascii=False, separators=(",", ":")))
    log.info("Wrote %s: %d offers (%d open)", OUT, len(rows), sum(r["status"] != "Closed" for r in rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
