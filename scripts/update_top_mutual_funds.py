#!/usr/bin/env python3
"""
VilfinTV Blog Intelligence Hub — Daily Top Mutual Funds Feed Updater
====================================================================
Builds data/top_mutual_funds.json
Fetches historical data for a pool of top mutual funds/ETFs for US, Japan, and India.
Calculates 1-year return to rank them and keeps only the Top 5 for each region.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Try importing yfinance; gracefully exit if missing to avoid breaking if not yet installed.
try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Please install with: pip install yfinance")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = REPO_ROOT / "data" / "top_mutual_funds.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# Pool of prominent Funds/ETFs per region to track
# We will rank these by 1-year return and select the Top 5
FUND_POOLS = {
    "us": [
        {"symbol": "FXAIX", "name": "Fidelity 500 Index Fund"},
        {"symbol": "VTSAX", "name": "Vanguard Total Stock Market"},
        {"symbol": "VFIAX", "name": "Vanguard 500 Index Fund"},
        {"symbol": "FCNTX", "name": "Fidelity Contrafund"},
        {"symbol": "VIGAX", "name": "Vanguard Growth Index"},
        {"symbol": "TRBCX", "name": "T. Rowe Price Blue Chip Growth"},
        {"symbol": "AGTHX", "name": "American Funds Growth"},
        {"symbol": "VWUSX", "name": "Vanguard U.S. Growth"},
        {"symbol": "QQQ",   "name": "Invesco QQQ Trust"},
        {"symbol": "SPY",   "name": "SPDR S&P 500 ETF Trust"},
    ],
    "japan": [
        {"symbol": "EWJ",  "name": "iShares MSCI Japan ETF"},
        {"symbol": "BBJP", "name": "JPMorgan BetaBuilders Japan"},
        {"symbol": "DXJ",  "name": "WisdomTree Japan Hedged"},
        {"symbol": "FLJP", "name": "Franklin FTSE Japan ETF"},
        {"symbol": "SCJ",  "name": "iShares MSCI Japan Small-Cap"},
        {"symbol": "DFJ",  "name": "WisdomTree Japan SmallCap Div"},
        {"symbol": "HEWJ", "name": "iShares Currency Hedged Japan"},
        {"symbol": "DBJP", "name": "Xtrackers Japan ESG ETF"},
    ],
    "india": [
        {"symbol": "INDA", "name": "iShares MSCI India ETF"},
        {"symbol": "EPI",  "name": "WisdomTree India Earnings"},
        {"symbol": "INDY", "name": "iShares India 50 ETF"},
        {"symbol": "SMIN", "name": "iShares MSCI India Small-Cap"},
        {"symbol": "PIN",  "name": "Invesco India ETF"},
        {"symbol": "FLIN", "name": "Franklin FTSE India ETF"},
        {"symbol": "INDA", "name": "iShares MSCI India ETF"},
        {"symbol": "NFTY", "name": "First Trust India NIFTY 50"},
    ]
}

def get_1y_return(symbol: str) -> float | None:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        if len(hist) < 2:
            return None
        start_price = hist['Close'].iloc[0]
        end_price = hist['Close'].iloc[-1]
        if start_price <= 0:
            return None
        return ((end_price - start_price) / start_price) * 100.0
    except Exception as e:
        log.warning(f"Failed to fetch data for {symbol}: {e}")
        return None

def main() -> int:
    now = datetime.now(timezone.utc)
    out = {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "regions": {}
    }

    for region, funds in FUND_POOLS.items():
        log.info(f"🌐 Fetching {region.upper()} funds...")
        results = []
        for f in funds:
            ret = get_1y_return(f["symbol"])
            if ret is not None:
                results.append({
                    "symbol": f["symbol"],
                    "name": f["name"],
                    "return_1y": round(ret, 2)
                })
        
        # Sort by return descending
        results.sort(key=lambda x: x["return_1y"], reverse=True)
        
        # Keep Top 5
        top_5 = results[:5]
        out["regions"][region] = top_5
        
        log.info(f"  → Top 5 selected out of {len(results)} valid funds for {region}.")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"✓ Wrote {OUT_FILE}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
