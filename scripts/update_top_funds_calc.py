#!/usr/bin/env python3
"""
VilfinTV Blog Intelligence Hub — Daily Top Funds & ETFs Calculator + News Fetcher
===================================================================================
Fetches live prices/NAVs for a predefined universe of top Mutual Funds and ETFs
across the US, Japan, and India. Calculates their 1-year return, ranks them,
and strictly keeps the top 5 per country. Merges this with targeted RSS news.
Outputs: data/top_mutual_funds.json and data/top_etfs.json
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import requests
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_MF = REPO_ROOT / "data" / "top_mutual_funds.json"
OUT_ETF = REPO_ROOT / "data" / "top_etfs.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; VilfinTV-TopFundsBot/1.0)",
    "Accept": "application/rss+xml, application/json, text/xml",
})

# =====================================================================
# UNIVERSE OF FUNDS & ETFS
# =====================================================================
# We define a pool of 8-12 prominent funds per category/region. 
# The script fetches all, calculates 1Y return, and slices the Top 5.

MF_UNIVERSE = {
    "us": [
        {"name": "Fidelity 500 Index Fund", "symbol": "FXAIX", "source": "yf"},
        {"name": "Fidelity Contrafund", "symbol": "FCNTX", "source": "yf"},
        {"name": "Vanguard Total Stock Market", "symbol": "VTSAX", "source": "yf"},
        {"name": "Vanguard 500 Index Fund", "symbol": "VFIAX", "source": "yf"},
        {"name": "Vanguard US Growth", "symbol": "VWUSX", "source": "yf"},
        {"name": "T. Rowe Price Blue Chip Growth", "symbol": "TRBCX", "source": "yf"},
        {"name": "T. Rowe Price Growth Stock", "symbol": "PRGFX", "source": "yf"},
        {"name": "American Funds Growth Fund", "symbol": "AGTHX", "source": "yf"},
    ],
    "japan": [
        # Using MAXIS ETFs (2558, 2559) as proxy for eMAXIS Slim returns (identical tracking)
        {"name": "eMAXIS Slim All Country", "symbol": "2559.T", "source": "yf"},
        {"name": "eMAXIS Slim S&P 500", "symbol": "2558.T", "source": "yf"},
        {"name": "eMAXIS Slim Developed Markets", "symbol": "1614.T", "source": "yf"},
        {"name": "eMAXIS Slim TOPIX", "symbol": "1475.T", "source": "yf"},
        {"name": "eMAXIS Slim Nikkei 225", "symbol": "1329.T", "source": "yf"},
    ],
    "india": [
        {"name": "Parag Parikh Flexi Cap Fund", "symbol": "122639", "source": "mfapi"},
        {"name": "SBI Small Cap Fund", "symbol": "119847", "source": "mfapi"},
        {"name": "Axis Bluechip Fund", "symbol": "120465", "source": "mfapi"},
        {"name": "Mirae Asset Large Cap", "symbol": "118834", "source": "mfapi"},
        {"name": "Nippon India Small Cap", "symbol": "118778", "source": "mfapi"},
        {"name": "HDFC Mid-Cap Opportunities", "symbol": "118989", "source": "mfapi"},
        {"name": "ICICI Pru Bluechip Fund", "symbol": "120586", "source": "mfapi"},
        {"name": "Quant Small Cap Fund", "symbol": "120841", "source": "mfapi"},
    ]
}

ETF_UNIVERSE = {
    "us": [
        {"name": "SPDR S&P 500 ETF Trust", "symbol": "SPY", "source": "yf"},
        {"name": "Invesco QQQ Trust", "symbol": "QQQ", "source": "yf"},
        {"name": "Vanguard Total Stock Market", "symbol": "VTI", "source": "yf"},
        {"name": "Vanguard S&P 500 ETF", "symbol": "VOO", "source": "yf"},
        {"name": "iShares Core S&P 500 ETF", "symbol": "IVV", "source": "yf"},
        {"name": "VanEck Semiconductor ETF", "symbol": "SMH", "source": "yf"},
        {"name": "Technology Select Sector SPDR", "symbol": "XLK", "source": "yf"},
        {"name": "ARK Innovation ETF", "symbol": "ARKK", "source": "yf"},
    ],
    "japan": [
        {"name": "iShares Core TOPIX ETF", "symbol": "1475.T", "source": "yf"},
        {"name": "iShares Core Nikkei 225 ETF", "symbol": "1329.T", "source": "yf"},
        {"name": "NEXT FUNDS Nikkei 225 ETF", "symbol": "1321.T", "source": "yf"},
        {"name": "NEXT FUNDS Nikkei 225 Leveraged", "symbol": "1570.T", "source": "yf"},
        {"name": "MAXIS All Country Equity ETF", "symbol": "2559.T", "source": "yf"},
        {"name": "MAXIS S&P 500 Equity ETF", "symbol": "2558.T", "source": "yf"},
    ],
    "india": [
        {"name": "Nippon India ETF Nifty 50 BeES", "symbol": "NIFTYBEES.NS", "source": "yf"},
        {"name": "SBI Nifty 50 ETF", "symbol": "SETFNIF50.NS", "source": "yf"},
        {"name": "CPSE ETF", "symbol": "CPSEETF.NS", "source": "yf"},
        {"name": "Nippon India ETF Bank BeES", "symbol": "BANKBEES.NS", "source": "yf"},
        {"name": "Motilal Oswal Nasdaq 100 ETF", "symbol": "MON100.NS", "source": "yf"},
        {"name": "Bharat 22 ETF", "symbol": "ICICIB22.NS", "source": "yf"},
    ]
}

# =====================================================================
# FETCH CALCULATION LOGIC
# =====================================================================

def fetch_yfinance_1y_return(symbol: str) -> float | None:
    import math
    try:
        tkr = yf.Ticker(symbol)
        hist = tkr.history(period="1y")
        if hist.empty or len(hist) < 20:
            return None
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            return None
        start_price = hist["Close"].iloc[0]
        end_price = hist["Close"].iloc[-1]
        if not start_price or math.isnan(start_price) or start_price == 0:
            return None
        return round(((end_price - start_price) / start_price) * 100, 2)
    except Exception as e:
        log.warning(f"Failed YF fetch for {symbol}: {e}")
        return None

def fetch_mfapi_1y_return(scheme_code: str) -> float | None:
    try:
        url = f"https://api.mfapi.in/mf/{scheme_code}"
        r = SESSION.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        navs = data.get("data", [])
        if not navs or len(navs) < 200:
            return None
        end_price = float(navs[0]["nav"])
        
        # Approximate 1 year ago (assuming ~250 trading days per year)
        target_idx = min(250, len(navs) - 1)
        start_price = float(navs[target_idx]["nav"])
        
        return round(((end_price - start_price) / start_price) * 100, 2)
    except Exception as e:
        log.warning(f"Failed MFAPI fetch for {scheme_code}: {e}")
        return None

def calculate_top_5(universe: dict) -> dict:
    results = {}
    for country, funds in universe.items():
        calculated = []
        for f in funds:
            ret = None
            if f["source"] == "yf":
                ret = fetch_yfinance_1y_return(f["symbol"])
            elif f["source"] == "mfapi":
                ret = fetch_mfapi_1y_return(f["symbol"])
            
            if ret is not None:
                calculated.append({
                    "name": f["name"],
                    "symbol": f["symbol"].replace(".T", "").replace(".NS", ""),
                    "return_1y": ret,
                    "country": country
                })
                log.info(f"  {country}: {f['name']} -> {ret}%")
            time.sleep(0.5)
            
        calculated.sort(key=lambda x: x["return_1y"], reverse=True)
        top5 = calculated[:5]
        
        # Assign rank
        for i, fund in enumerate(top5):
            fund["rank"] = i + 1
            
        results[country] = top5
    return results

# =====================================================================
# NEWS FETCHING LOGIC
# =====================================================================

def _gn(query: str, loc: str) -> dict[str, str]:
    locales = {"us": "hl=en-US&gl=US&ceid=US:en", "jp": "hl=ja&gl=JP&ceid=JP:ja", "in": "hl=en-IN&gl=IN&ceid=IN:en"}
    return {"url": f"https://news.google.com/rss/search?q={quote(query)}+when:30d&{locales[loc]}", "source": "Google News"}

MF_FEEDS = {
    "us": [_gn("top performing mutual funds 2026", "us")],
    "japan": [_gn("おすすめ 投資信託 ランキング", "jp")],
    "india": [
        {"url": "https://www.moneycontrol.com/rss/mfnews.xml", "source": "Moneycontrol MF"},
        _gn("best mutual funds SIP returns India", "in"),
    ],
}

ETF_FEEDS = {
    "us": [_gn("top performing ETFs 2026", "us")],
    "japan": [_gn("おすすめ ETF ランキング", "jp")],
    "india": [
        _gn("Nifty ETF OR Sensex ETF OR CPSE ETF OR Bharat 22 ETF", "in"),
        _gn("Nippon India ETF OR SBI ETF OR ICICI Prudential ETF", "in"),
    ],
}

def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()

def fetch_rss(url: str) -> list:
    try:
        r = SESSION.get(url, timeout=12)
        r.raise_for_status()
        items = []
        root = ET.fromstring(r.content.lstrip(b"\xef\xbb\xbf"))
        for it in root.iter("item"):
            title, link, desc, pub = [ (it.findtext(tag) or "").strip() for tag in ["title", "link", "description", "pubDate"] ]
            if title and link: items.append({"title": title, "link": link, "desc": desc, "pub": pub})
        return items
    except Exception as e:
        log.warning(f"  Fetch failed: {url} \u2192 {e}")
        return []

def process_news(feeds: dict, max_age=30, max_items=18) -> dict:
    out = {}
    now = datetime.now(timezone.utc)
    for country, sources in feeds.items():
        items, seen = [], set()
        for src in sources:
            for it in fetch_rss(src["url"]):
                link, title = it["link"], strip_html(it["title"])
                if link in seen or not title: continue
                seen.add(link)
                items.append({
                    "title": title, "url": link, "source": src["source"],
                    "date": it.get("pub", "")[:24],
                })
                if len(items) >= max_items: break
            if len(items) >= max_items: break
        out[country] = items
    return out

# =====================================================================
# MAIN
# =====================================================================

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    log.info("Calculating Top 5 Mutual Funds...")
    mf_funds = calculate_top_5(MF_UNIVERSE)
    mf_news = process_news(MF_FEEDS)
    
    OUT_MF.write_text(json.dumps({
        "generated": now,
        "funds": mf_funds,
        "countries": mf_news
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    
    log.info("Calculating Top 5 ETFs...")
    etf_funds = calculate_top_5(ETF_UNIVERSE)
    etf_news = process_news(ETF_FEEDS)
    
    OUT_ETF.write_text(json.dumps({
        "generated": now,
        "funds": etf_funds,
        "countries": etf_news
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    
    log.info("✓ Generated top_mutual_funds.json and top_etfs.json")

if __name__ == "__main__":
    main()
