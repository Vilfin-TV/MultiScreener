#!/usr/bin/env python3
"""
VilfinTV — US & Global ETF Momentum data builder.

Builds data/global_etf.json for global_etf_momentum.html.

  pip install yfinance pandas numpy
  python scripts/build_global_etf.py            # build + audit + publish
  python scripts/build_global_etf.py --dry-run  # build + audit, do not write

Publishing rule: the JSON is written ONLY if every critical audit check passes.
On any critical failure the previous file is left untouched and the script exits 1.
Volatile fund facts (expense ratio, AUM, inception, yield, official name) are
fetched every run — never hard-coded — and range-checked.
"""
from __future__ import annotations

import argparse, json, math, os, sys, time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from global_plans import all_plans, ALL_CANDS  # noqa: E402  (shared with the page's simulator and gsim_engine.py)
from global_dip import dip_block  # noqa: E402  (optional market-dip buys)

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "global_etf.json")
DAILY_OUT = os.path.join(os.path.dirname(__file__), "..", "data", "global_etf_daily.json")
DAILY_SESSIONS = 320    # raw daily closes kept for the Simulator Buy (official closes, dividends, splits)
MARKET = ["SPY", "QQQ", "IWM", "EFA", "EEM", "AGG", "GLD"]   # day's market moves in the Simulator Buy journal
WEEKS_OUT = 60          # weekly closes exported per ETF
MIN_WEEKS = 20          # minimum clean weeks to classify
TAIL = 8                # tail length on the rotation map

# --------------------------------------------------------------------------
# Universe: ticker, fallback name, asset class, region, role, category
# Classification is editorial and stable; names are replaced by official
# long names when available.
# --------------------------------------------------------------------------
U = [
 # US core & size
 ("SPY","SPDR S&P 500 ETF Trust","Equity","US","Core","US Large Cap"),
 ("IVV","iShares Core S&P 500 ETF","Equity","US","Core","US Large Cap"),
 ("VOO","Vanguard S&P 500 ETF","Equity","US","Core","US Large Cap"),
 ("VTI","Vanguard Total Stock Market ETF","Equity","US","Core","US Total Market"),
 ("ITOT","iShares Core S&P Total U.S. Stock Market ETF","Equity","US","Core","US Total Market"),
 ("SCHB","Schwab U.S. Broad Market ETF","Equity","US","Core","US Total Market"),
 ("RSP","Invesco S&P 500 Equal Weight ETF","Equity","US","Core","US Large Cap"),
 ("DIA","SPDR Dow Jones Industrial Average ETF Trust","Equity","US","Core","US Large Cap"),
 ("QQQ","Invesco QQQ Trust","Equity","US","Core","US Large Growth"),
 ("QQQM","Invesco NASDAQ 100 ETF","Equity","US","Core","US Large Growth"),
 ("IWB","iShares Russell 1000 ETF","Equity","US","Core","US Large Cap"),
 ("VO","Vanguard Mid-Cap ETF","Equity","US","Core","US Mid Cap"),
 ("IJH","iShares Core S&P Mid-Cap ETF","Equity","US","Core","US Mid Cap"),
 ("MDY","SPDR S&P MidCap 400 ETF Trust","Equity","US","Core","US Mid Cap"),
 ("IWM","iShares Russell 2000 ETF","Equity","US","Core","US Small Cap"),
 ("IJR","iShares Core S&P Small-Cap ETF","Equity","US","Core","US Small Cap"),
 ("VB","Vanguard Small-Cap ETF","Equity","US","Core","US Small Cap"),
 # US style & factor
 ("VUG","Vanguard Growth ETF","Equity","US","Factor","US Growth"),
 ("VTV","Vanguard Value ETF","Equity","US","Factor","US Value"),
 ("IWF","iShares Russell 1000 Growth ETF","Equity","US","Factor","US Growth"),
 ("IWD","iShares Russell 1000 Value ETF","Equity","US","Factor","US Value"),
 ("SCHG","Schwab U.S. Large-Cap Growth ETF","Equity","US","Factor","US Growth"),
 ("SCHD","Schwab U.S. Dividend Equity ETF","Equity","US","Factor","US Dividend"),
 ("VIG","Vanguard Dividend Appreciation ETF","Equity","US","Factor","US Dividend"),
 ("VYM","Vanguard High Dividend Yield ETF","Equity","US","Factor","US Dividend"),
 ("DGRO","iShares Core Dividend Growth ETF","Equity","US","Factor","US Dividend"),
 ("MTUM","iShares MSCI USA Momentum Factor ETF","Equity","US","Factor","US Momentum"),
 ("QUAL","iShares MSCI USA Quality Factor ETF","Equity","US","Factor","US Quality"),
 ("USMV","iShares MSCI USA Min Vol Factor ETF","Equity","US","Factor","US Low Volatility"),
 ("SPLV","Invesco S&P 500 Low Volatility ETF","Equity","US","Factor","US Low Volatility"),
 ("COWZ","Pacer US Cash Cows 100 ETF","Equity","US","Factor","US Value"),
 # US sectors (SPDR)
 ("XLK","Technology Select Sector SPDR Fund","Equity","US","Sector","Technology"),
 ("XLF","Financial Select Sector SPDR Fund","Equity","US","Sector","Financials"),
 ("XLV","Health Care Select Sector SPDR Fund","Equity","US","Sector","Health Care"),
 ("XLE","Energy Select Sector SPDR Fund","Equity","US","Sector","Energy"),
 ("VDE","Vanguard Energy ETF","Equity","US","Sector","Energy"),
 ("XLI","Industrial Select Sector SPDR Fund","Equity","US","Sector","Industrials"),
 ("XLY","Consumer Discretionary Select Sector SPDR Fund","Equity","US","Sector","Consumer Discretionary"),
 ("XLP","Consumer Staples Select Sector SPDR Fund","Equity","US","Sector","Consumer Staples"),
 ("XLU","Utilities Select Sector SPDR Fund","Equity","US","Sector","Utilities"),
 ("XLB","Materials Select Sector SPDR Fund","Equity","US","Sector","Materials"),
 ("XLRE","Real Estate Select Sector SPDR Fund","Equity","US","Sector","Real Estate"),
 ("XLC","Communication Services Select Sector SPDR Fund","Equity","US","Sector","Communication Services"),
 ("VGT","Vanguard Information Technology ETF","Equity","US","Sector","Technology"),
 # Industries & themes
 ("SMH","VanEck Semiconductor ETF","Equity","US","Thematic","Semiconductors"),
 ("SOXX","iShares Semiconductor ETF","Equity","US","Thematic","Semiconductors"),
 ("IGV","iShares Expanded Tech-Software Sector ETF","Equity","US","Thematic","Software"),
 ("CIBR","First Trust NASDAQ Cybersecurity ETF","Equity","Global","Thematic","Cybersecurity"),
 ("XBI","SPDR S&P Biotech ETF","Equity","US","Thematic","Biotechnology"),
 ("IBB","iShares Biotechnology ETF","Equity","US","Thematic","Biotechnology"),
 ("KRE","SPDR S&P Regional Banking ETF","Equity","US","Thematic","Regional Banks"),
 ("ITA","iShares U.S. Aerospace & Defense ETF","Equity","US","Thematic","Aerospace & Defense"),
 ("ITB","iShares U.S. Home Construction ETF","Equity","US","Thematic","Homebuilders"),
 ("XOP","SPDR S&P Oil & Gas Exploration & Production ETF","Equity","US","Thematic","Oil & Gas"),
 ("GDX","VanEck Gold Miners ETF","Equity","Global","Thematic","Gold Miners"),
 ("XME","SPDR S&P Metals & Mining ETF","Equity","US","Thematic","Metals & Mining"),
 ("ICLN","iShares Global Clean Energy ETF","Equity","Global","Thematic","Clean Energy"),
 ("TAN","Invesco Solar ETF","Equity","Global","Thematic","Clean Energy"),
 ("URA","Global X Uranium ETF","Equity","Global","Thematic","Uranium"),
 ("BOTZ","Global X Robotics & Artificial Intelligence ETF","Equity","Global","Thematic","Robotics & AI"),
 ("ARKK","ARK Innovation ETF","Equity","Global","Thematic","Innovation"),
 ("JETS","U.S. Global Jets ETF","Equity","Global","Thematic","Airlines"),
 # Global & developed
 ("ACWI","iShares MSCI ACWI ETF","Equity","Global","Core","Global All Cap"),
 ("VT","Vanguard Total World Stock ETF","Equity","Global","Core","Global All Cap"),
 ("VXUS","Vanguard Total International Stock ETF","Equity","Developed ex-US","Core","International All Cap"),
 ("VEA","Vanguard FTSE Developed Markets ETF","Equity","Developed ex-US","Core","Developed Markets"),
 ("IEFA","iShares Core MSCI EAFE ETF","Equity","Developed ex-US","Core","Developed Markets"),
 ("EFA","iShares MSCI EAFE ETF","Equity","Developed ex-US","Core","Developed Markets"),
 ("VGK","Vanguard FTSE Europe ETF","Equity","Europe","Country","Europe"),
 ("IEUR","iShares Core MSCI Europe ETF","Equity","Europe","Country","Europe"),
 ("EZU","iShares MSCI Eurozone ETF","Equity","Europe","Country","Eurozone"),
 ("EWU","iShares MSCI United Kingdom ETF","Equity","Europe","Country","United Kingdom"),
 ("EWG","iShares MSCI Germany ETF","Equity","Europe","Country","Germany"),
 ("EWQ","iShares MSCI France ETF","Equity","Europe","Country","France"),
 ("EWL","iShares MSCI Switzerland ETF","Equity","Europe","Country","Switzerland"),
 ("EWJ","iShares MSCI Japan ETF","Equity","Asia-Pacific","Country","Japan"),
 ("BBJP","JPMorgan BetaBuilders Japan ETF","Equity","Asia-Pacific","Country","Japan"),
 ("DXJ","WisdomTree Japan Hedged Equity Fund","Equity","Asia-Pacific","Country","Japan (Hedged)"),
 ("EWA","iShares MSCI Australia ETF","Equity","Asia-Pacific","Country","Australia"),
 ("EWS","iShares MSCI Singapore ETF","Equity","Asia-Pacific","Country","Singapore"),
 ("EWH","iShares MSCI Hong Kong ETF","Equity","Asia-Pacific","Country","Hong Kong"),
 ("EWC","iShares MSCI Canada ETF","Equity","Americas","Country","Canada"),
 # Emerging
 ("VWO","Vanguard FTSE Emerging Markets ETF","Equity","Emerging","Core","Emerging Markets"),
 ("IEMG","iShares Core MSCI Emerging Markets ETF","Equity","Emerging","Core","Emerging Markets"),
 ("EEM","iShares MSCI Emerging Markets ETF","Equity","Emerging","Core","Emerging Markets"),
 ("INDA","iShares MSCI India ETF","Equity","Emerging","Country","India"),
 ("EPI","WisdomTree India Earnings Fund","Equity","Emerging","Country","India"),
 ("SMIN","iShares MSCI India Small-Cap ETF","Equity","Emerging","Country","India Small Cap"),
 ("FXI","iShares China Large-Cap ETF","Equity","Emerging","Country","China"),
 ("MCHI","iShares MSCI China ETF","Equity","Emerging","Country","China"),
 ("KWEB","KraneShares CSI China Internet ETF","Equity","Emerging","Thematic","China Internet"),
 ("EWT","iShares MSCI Taiwan ETF","Equity","Emerging","Country","Taiwan"),
 ("EWY","iShares MSCI South Korea ETF","Equity","Emerging","Country","South Korea"),
 ("EWZ","iShares MSCI Brazil ETF","Equity","Emerging","Country","Brazil"),
 ("ILF","iShares Latin America 40 ETF","Equity","Emerging","Country","Latin America"),
 ("FLLA","Franklin FTSE Latin America ETF","Equity","Emerging","Country","Latin America"),
 ("EWW","iShares MSCI Mexico ETF","Equity","Emerging","Country","Mexico"),
 ("EIDO","iShares MSCI Indonesia ETF","Equity","Emerging","Country","Indonesia"),
 ("EZA","iShares MSCI South Africa ETF","Equity","Emerging","Country","South Africa"),
 ("VNM","VanEck Vietnam ETF","Equity","Emerging","Country","Vietnam"),
 ("ARGT","Global X MSCI Argentina ETF","Equity","Emerging","Country","Argentina"),
 # Bonds
 ("AGG","iShares Core U.S. Aggregate Bond ETF","Bond","US","Bond","US Aggregate"),
 ("BND","Vanguard Total Bond Market ETF","Bond","US","Bond","US Aggregate"),
 ("BNDX","Vanguard Total International Bond ETF","Bond","Developed ex-US","Bond","International Bonds (Hedged)"),
 ("TLT","iShares 20+ Year Treasury Bond ETF","Bond","US","Bond","Long Treasury"),
 ("IEF","iShares 7-10 Year Treasury Bond ETF","Bond","US","Bond","Intermediate Treasury"),
 ("SHY","iShares 1-3 Year Treasury Bond ETF","Bond","US","Bond","Short Treasury"),
 ("SGOV","iShares 0-3 Month Treasury Bond ETF","Bond","US","Bond","Treasury Bills"),
 ("BIL","SPDR Bloomberg 1-3 Month T-Bill ETF","Bond","US","Bond","Treasury Bills"),
 ("TIP","iShares TIPS Bond ETF","Bond","US","Bond","Inflation-Protected"),
 ("LQD","iShares iBoxx $ Investment Grade Corporate Bond ETF","Bond","US","Bond","Investment Grade Corporate"),
 ("HYG","iShares iBoxx $ High Yield Corporate Bond ETF","Bond","US","Bond","High Yield"),
 ("EMB","iShares J.P. Morgan USD Emerging Markets Bond ETF","Bond","Emerging","Bond","EM Sovereign (USD)"),
 ("MUB","iShares National Muni Bond ETF","Bond","US","Bond","Municipal"),
 ("GOVT","iShares U.S. Treasury Bond ETF","Bond","US","Bond","US Treasury (all maturities)"),
 ("VGSH","Vanguard Short-Term Treasury ETF","Bond","US","Bond","Short Treasury"),
 ("SHV","iShares Short Treasury Bond ETF","Bond","US","Bond","Treasury Bills"),
 ("VGIT","Vanguard Intermediate-Term Treasury ETF","Bond","US","Bond","Intermediate Treasury"),
 ("VGLT","Vanguard Long-Term Treasury ETF","Bond","US","Bond","Long Treasury"),
 ("SCHZ","Schwab U.S. Aggregate Bond ETF","Bond","US","Bond","US Aggregate"),
 ("BSV","Vanguard Short-Term Bond ETF","Bond","US","Bond","Short-Term Bond"),
 ("BIV","Vanguard Intermediate-Term Bond ETF","Bond","US","Bond","Intermediate-Term Bond"),
 ("VCSH","Vanguard Short-Term Corporate Bond ETF","Bond","US","Bond","Short-Term Corporate"),
 ("VCIT","Vanguard Intermediate-Term Corporate Bond ETF","Bond","US","Bond","Investment Grade Corporate"),
 ("IGSB","iShares 1-5 Year Investment Grade Corporate Bond ETF","Bond","US","Bond","Short-Term Corporate"),
 ("MBB","iShares MBS ETF","Bond","US","Bond","Mortgage-Backed"),
 ("VMBS","Vanguard Mortgage-Backed Securities ETF","Bond","US","Bond","Mortgage-Backed"),
 ("SCHP","Schwab U.S. TIPS ETF","Bond","US","Bond","Inflation-Protected"),
 ("VTIP","Vanguard Short-Term Inflation-Protected Securities ETF","Bond","US","Bond","Short TIPS"),
 ("JPST","JPMorgan Ultra-Short Income ETF","Bond","US","Bond","Ultra-Short"),
 ("FLOT","iShares Floating Rate Bond ETF","Bond","US","Bond","Floating Rate"),
 ("USHY","iShares Broad USD High Yield Corporate Bond ETF","Bond","US","Bond","High Yield"),
 ("JNK","SPDR Bloomberg High Yield Bond ETF","Bond","US","Bond","High Yield"),
 ("BKLN","Invesco Senior Loan ETF","Bond","US","Bond","Senior Loans"),
 ("IAGG","iShares Core International Aggregate Bond ETF","Bond","Developed ex-US","Bond","International Bonds (Hedged)"),
 ("BWX","SPDR Bloomberg International Treasury Bond ETF","Bond","Developed ex-US","Bond","International Treasury"),
 ("EMLC","VanEck J.P. Morgan EM Local Currency Bond ETF","Bond","Emerging","Bond","EM Local Currency"),
 ("VWOB","Vanguard Emerging Markets Government Bond ETF","Bond","Emerging","Bond","EM Sovereign (USD)"),
 # Commodities
 ("GLD","SPDR Gold Shares","Commodity","Global","Commodity","Gold"),
 ("IAU","iShares Gold Trust","Commodity","Global","Commodity","Gold"),
 ("GLDM","SPDR Gold MiniShares Trust","Commodity","Global","Commodity","Gold"),
 ("SLV","iShares Silver Trust","Commodity","Global","Commodity","Silver"),
 ("PPLT","abrdn Platinum ETF Trust","Commodity","Global","Commodity","Platinum"),
 ("CPER","United States Copper Index Fund","Commodity","Global","Commodity","Copper"),
 ("DBC","Invesco DB Commodity Index Tracking Fund","Commodity","Global","Commodity","Broad Commodities"),
 ("PDBC","Invesco Optimum Yield Diversified Commodity Strategy No K-1 ETF","Commodity","Global","Commodity","Broad Commodities"),
 ("USO","United States Oil Fund","Commodity","Global","Commodity","Crude Oil"),
 ("UNG","United States Natural Gas Fund","Commodity","Global","Commodity","Natural Gas"),
 ("SGOL","abrdn Physical Gold Shares ETF","Commodity","Global","Commodity","Gold"),
 ("BAR","GraniteShares Gold Trust","Commodity","Global","Commodity","Gold"),
 ("AAAU","Goldman Sachs Physical Gold ETF","Commodity","Global","Commodity","Gold"),
 ("SIVR","abrdn Physical Silver Shares ETF","Commodity","Global","Commodity","Silver"),
 ("PALL","abrdn Physical Palladium Shares ETF","Commodity","Global","Commodity","Palladium"),
 ("GSG","iShares S&P GSCI Commodity-Indexed Trust","Commodity","Global","Commodity","Broad Commodities"),
 ("BCI","abrdn Bloomberg All Commodity Strategy K-1 Free ETF","Commodity","Global","Commodity","Broad Commodities"),
 ("COMT","iShares GSCI Commodity Dynamic Roll Strategy ETF","Commodity","Global","Commodity","Broad Commodities"),
 ("DBA","Invesco DB Agriculture Fund","Commodity","Global","Commodity","Agriculture"),
 ("DBB","Invesco DB Base Metals Fund","Commodity","Global","Commodity","Industrial Metals"),
 ("BNO","United States Brent Oil Fund","Commodity","Global","Commodity","Crude Oil"),
 ("CORN","Teucrium Corn Fund","Commodity","Global","Commodity","Agriculture"),
 ("WEAT","Teucrium Wheat Fund","Commodity","Global","Commodity","Agriculture"),
 # Real estate
 ("VNQ","Vanguard Real Estate ETF","Real Estate","US","Sector","US REITs"),
 ("VNQI","Vanguard Global ex-U.S. Real Estate ETF","Real Estate","Developed ex-US","Sector","International REITs"),
 ("SCHH","Schwab U.S. REIT ETF","Real Estate","US","Sector","US REITs"),
 ("IYR","iShares U.S. Real Estate ETF","Real Estate","US","Sector","US REITs"),
 ("USRT","iShares Core U.S. REIT ETF","Real Estate","US","Sector","US REITs"),
 ("RWR","SPDR Dow Jones REIT ETF","Real Estate","US","Sector","US REITs"),
 ("REET","iShares Global REIT ETF","Real Estate","Global","Sector","Global REITs"),
 ("RWX","SPDR Dow Jones International Real Estate ETF","Real Estate","Developed ex-US","Sector","International REITs"),
 ("REM","iShares Mortgage Real Estate ETF","Real Estate","US","Sector","Mortgage REITs"),
 ("INDS","Pacer Industrial Real Estate ETF","Real Estate","US","Sector","Industrial REITs"),
 ("SRVR","Pacer Data & Infrastructure Real Estate ETF","Real Estate","US","Sector","Data & Infrastructure REITs"),
 # Digital assets
 ("IBIT","iShares Bitcoin Trust ETF","Digital Assets","Global","Digital","Bitcoin"),
 ("FBTC","Fidelity Wise Origin Bitcoin Fund","Digital Assets","Global","Digital","Bitcoin"),
 ("ETHA","iShares Ethereum Trust ETF","Digital Assets","Global","Digital","Ether"),
]
BENCHMARKS = ["SPY","QQQ","IWM","ACWI","EFA","EEM","AGG","GLD"]

# --------------------------------------------------------------------------
# Momentum engine — MUST stay identical to the JS engine in the page.
#   rs        = 100 * ETF / benchmark            (weekly closes)
#   RS-Ratio  = 100 * EMA3(rs) / SMA10(rs)
#   RS-Mom    = 100 + (RS-Ratio_t - RS-Ratio_{t-3})
# --------------------------------------------------------------------------
def _ema(a, n):
    k = 2.0 / (n + 1); out = []; prev = None
    for v in a:
        prev = v if prev is None else prev + k * (v - prev)
        out.append(prev)
    return out

def rrg(etf, bench):
    pts = [(e, b) for e, b in zip(etf, bench) if e is not None and b is not None and b > 0 and e > 0]
    if len(pts) < MIN_WEEKS:
        return None
    rs = [100.0 * e / b for e, b in pts]
    ema = _ema(rs, 3)
    ratio = [None] * len(rs)
    for i in range(9, len(rs)):
        sma = sum(rs[i - 9:i + 1]) / 10.0
        ratio[i] = 100.0 * ema[i] / sma
    mom = [None] * len(rs)
    for i in range(len(rs)):
        if i >= 3 and ratio[i] is not None and ratio[i - 3] is not None:
            mom[i] = 100.0 + (ratio[i] - ratio[i - 3])
    r, m = ratio[-1], mom[-1]
    if r is None or m is None:
        return None
    mode = ("ACC" if m >= 100 else "DEC") if r >= 100 else ("REC" if m >= 100 else "UND")
    return {"ratio": r, "mom": m, "mode": mode}

# --------------------------------------------------------------------------
def fetch_prices(tickers):
    import yfinance as yf
    df = yf.download(tickers, period="6y", interval="1d", auto_adjust=False, actions=True,
                     group_by="ticker", progress=False, threads=True)
    return drop_open_session(df)

def drop_open_session(df):
    """During US trading hours the download ends with today's unfinished bar — never publish it as a close."""
    if df is None or getattr(df, "empty", True):
        return df
    from zoneinfo import ZoneInfo
    ny = datetime.now(ZoneInfo("America/New_York"))
    df = df[[d.date() <= ny.date() for d in df.index]]          # never a bar dated after today in New York
    if len(df) and df.index[-1].date() == ny.date() and (ny.hour, ny.minute) < (16, 30):
        df = df.iloc[:-1]
    return df

def daily_export(raw, as_of):
    """Official daily closes (not dividend-adjusted), cash dividends by ex-date and splits of every ETF the Portfolio
    Simulator can choose plus the market trackers — read by scripts/gsim_engine.py to price every simulated trade."""
    tick = sorted(set(ALL_CANDS) | set(MARKET))
    dates = [d for d in raw.index if d <= as_of][-DAILY_SESSIONS:]
    out = {"v": 1, "asOf": str(as_of.date()), "dates": [str(d.date()) for d in dates], "c": {}, "div": {}, "split": {}}
    for t in tick:
        if t not in raw.columns.get_level_values(0):
            continue
        d = raw[t].reindex(dates)
        out["c"][t] = [r4(v, 4) if pd.notna(v) and v > 0 else None for v in d["Close"].values]
        if "Dividends" in d:
            out["div"][t] = [[str(i.date()), r4(v, 6)] for i, v in d["Dividends"].items() if pd.notna(v) and v > 0]
        if "Stock Splits" in d:
            out["split"][t] = [[str(i.date()), float(v)] for i, v in d["Stock Splits"].items() if pd.notna(v) and v > 0 and v != 1]
    return out

def fetch_facts(t):
    import yfinance as yf
    for attempt in range(3):
        try:
            info = yf.Ticker(t).info or {}
            er = info.get("netExpenseRatio")
            if er is None and info.get("annualReportExpenseRatio") is not None:
                er = info["annualReportExpenseRatio"] * 100.0
            inc = info.get("fundInceptionDate")
            return {
                "name": info.get("longName") or info.get("shortName"),
                "issuer": info.get("fundFamily"),
                "er": float(er) if er is not None else None,                 # percent
                "aum": float(info["totalAssets"]) if info.get("totalAssets") else None,
                "yld": float(info["yield"]) * 100.0 if info.get("yield") is not None else None,
                "inc": datetime.fromtimestamp(inc, tz=timezone.utc).strftime("%Y-%m-%d") if inc else None,
                "exch": info.get("exchange"),
            }
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return {}

def fund_holdings(t):
    """Top holdings, sector weights and asset-class split as the fund publishes them (best effort; {} when absent)."""
    import yfinance as yf
    out = {}
    try:
        fd = yf.Ticker(t).funds_data
    except Exception:
        return out
    try:
        th = fd.top_holdings
        if th is not None and len(th):
            rows = []
            for sym, row in th.head(10).iterrows():
                pct = row.get("Holding Percent")
                if pct is None or not math.isfinite(float(pct)):
                    continue
                rows.append([str(sym), str(row.get("Name") or sym)[:60], round(float(pct) * 100, 2)])
            if rows:
                out["hold"] = rows
    except Exception:
        pass
    try:
        sw = fd.sector_weightings or {}
        sec = {k.replace("_", " ").title(): round(float(v) * 100, 1) for k, v in sw.items() if v and float(v) > 0.0005}
        if sec:
            out["sec"] = dict(sorted(sec.items(), key=lambda x: -x[1]))
    except Exception:
        pass
    try:
        acl = fd.asset_classes or {}
        a = {k.replace("Position", "").replace("_", " ").strip().title(): round(float(v) * 100, 1) for k, v in acl.items() if v and abs(float(v)) > 0.0005}
        if a:
            out["acl"] = a
    except Exception:
        pass
    return out


def xirr(flows):
    """Annual internal rate of return of dated cash flows [(Timestamp, amount)] (bisection; None if undefined)."""
    if not flows or all(a >= 0 for _, a in flows) or all(a <= 0 for _, a in flows):
        return None
    t0 = flows[0][0]
    f = lambda r: sum(a / (1 + r) ** ((d - t0).days / 365.25) for d, a in flows)
    lo, hi = -0.99, 10.0
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0: hi = mid
        else: lo = mid
    return (lo + hi) / 2 * 100


def deep_stats(adj, spy_adj, rf_adj):
    """Long-history figures for the ETF detail card, all from the dividend-adjusted daily closes:
    monthly closes (6 years), monthly-SIP XIRR over 1/3/5 years, rolling 1Y/3Y returns (min · median · max · share
    positive, sampled every week over up to 5 years), calendar-year returns, Sharpe / Sortino (1Y over T-bills),
    up / down capture vs the S&P 500 (3 years of monthly returns)."""
    last = adj.index[-1]
    mo = adj.resample("ME").last().dropna()
    if len(mo) and mo.index[-1] > last:
        mo.index = mo.index[:-1].append(pd.DatetimeIndex([last]))
    res = {"mo": [r4(v, 4) for v in mo.tail(72).values], "moEnd": str(mo.index[-1].date()) if len(mo) else None}
    sip = {}
    for y in (1, 3, 5):
        start = last - pd.DateOffset(years=y)
        if adj.index[0] > start + pd.Timedelta(days=7):
            continue
        days = adj[adj.index > start]
        firsts = days.groupby([days.index.year, days.index.month]).head(1)
        if len(firsts) < 6 * y:
            continue
        units = sum(100.0 / v for v in firsts.values)
        flows = [(d, -100.0) for d in firsts.index] + [(last, units * float(adj.iloc[-1]))]
        v = xirr(flows)
        if v is not None:
            sip[f"{y}y"] = [r4(v, 2), int(len(firsts) * 100), r4(units * float(adj.iloc[-1]), 0)]
    res["sip"] = sip
    wk = adj.resample("W-FRI").last().dropna()
    wk = wk[wk.index > last - pd.DateOffset(years=8)]
    for y, key in ((1, "roll1"), (3, "roll3")):
        n = 52 * y
        if len(wk) <= n + 26:
            continue
        rr = ((wk / wk.shift(n)) ** (1.0 / y) - 1).dropna() * 100
        rr = rr[rr.index > last - pd.DateOffset(years=5)]
        if len(rr) < 26:
            continue
        res[key] = [r4(float(rr.min()), 2), r4(float(rr.median()), 2), r4(float(rr.max()), 2), r4(float((rr > 0).mean() * 100), 1), int(len(rr))]
    cal = {}
    ye = adj.resample("YE").last()
    for i in range(1, len(ye)):
        yr = ye.index[i].year
        if yr == last.year:
            continue
        cal[str(yr)] = r4((ye.iloc[i] / ye.iloc[i - 1] - 1) * 100, 2)
    if len(ye) and ye.index[0].year < last.year:
        prev = ye[ye.index.year == last.year - 1]
        if len(prev):
            cal[str(last.year) + " YTD"] = r4((adj.iloc[-1] / prev.iloc[-1] - 1) * 100, 2)
    res["cal"] = dict(list(cal.items())[-6:])
    d1 = adj[adj.index > last - pd.DateOffset(years=1)].pct_change().dropna()
    if len(d1) > 150:
        rf = 0.0
        if rf_adj is not None and len(rf_adj) > 200:
            rb = rf_adj[rf_adj.index <= last - pd.DateOffset(years=1)]
            if len(rb):
                rf = float(rf_adj.iloc[-1] / rb.iloc[-1] - 1)
        ann = float(adj.iloc[-1] / adj[adj.index <= last - pd.DateOffset(years=1)].iloc[-1] - 1)
        sd = float(d1.std() * math.sqrt(252)); dn = d1[d1 < 0]
        dsd = float(np.sqrt((dn ** 2).mean()) * math.sqrt(252)) if len(dn) > 10 else None
        res["shp"] = r4((ann - rf) / sd, 2) if sd > 0 else None
        res["sor"] = r4((ann - rf) / dsd, 2) if dsd else None
    m = adj.resample("ME").last().pct_change().dropna().tail(36)
    sm = spy_adj.resample("ME").last().pct_change().reindex(m.index).dropna()
    m = m.reindex(sm.index)
    if len(m) >= 24:
        up, dn = sm > 0, sm < 0
        cap = lambda a, b: (float((1 + a).prod() ** (12 / len(a)) - 1) / float((1 + b).prod() ** (12 / len(b)) - 1) * 100) if len(b) >= 4 and float((1 + b).prod()) != 1 else None
        res["cap"] = [r4(cap(m[up], sm[up]), 0), r4(cap(m[dn], sm[dn]), 0)]
    return res


def ret_since(s: pd.Series, start_date):
    base = s[s.index <= start_date]
    if base.empty:
        return None
    return (s.iloc[-1] / base.iloc[-1] - 1.0) * 100.0

def cagr_since(s, years):
    d = s.index[-1] - pd.DateOffset(years=years)
    if s.index[0] > d + pd.Timedelta(days=7):
        return None
    base = s[s.index <= d]
    if base.empty:
        return None
    return ((s.iloc[-1] / base.iloc[-1]) ** (1.0 / years) - 1.0) * 100.0

def r4(x, n=4):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), n)

# --------------------------------------------------------------------------
class Audit:
    def __init__(self):
        self.passed = 0; self.critical = []; self.warnings = []
    def check(self, ok, msg, critical=True):
        if ok:
            self.passed += 1
        elif critical:
            self.critical.append(msg)
        else:
            self.warnings.append(msg)
        return ok

def build(dry=False):
    tickers = [u[0] for u in U]
    A = Audit()
    A.check(len(tickers) == len(set(tickers)), "duplicate tickers in universe")

    raw = fetch_prices(tickers)
    # Common as-of date = latest date present for SPY
    if raw is None or getattr(raw, "empty", True) or "SPY" not in raw.columns.get_level_values(0):
        print("No price data downloaded — previous data left online."); return 1
    spy = raw["SPY"].dropna(subset=["Close"])
    if spy.empty:
        print("No SPY prices downloaded — previous data left online."); return 1
    as_of = spy.index[-1]
    A.check((pd.Timestamp.now("UTC").tz_localize(None) - as_of).days <= 5, f"SPY last close {as_of.date()} is stale")

    weeks = pd.date_range(end=as_of, periods=WEEKS_OUT + 2, freq="W-FRI")
    weeks = [w for w in weeks if w <= as_of]
    if weeks[-1] < as_of:
        weeks.append(as_of)          # current partial week ends at as-of
    weeks = weeks[-WEEKS_OUT:]

    prev = None
    if os.path.exists(OUT):
        try:
            with open(OUT) as f:
                prev = {e["t"]: e for e in json.load(f).get("etfs", [])}
        except Exception:
            prev = None

    spy_adj = raw["SPY"]["Adj Close"].dropna()
    adj_last = {}
    rf_adj = raw["BIL"]["Adj Close"].dropna() if "BIL" in raw.columns.get_level_values(0) else None
    out = []
    for (t, nm, ac, reg, role, cat) in U:
        if t not in raw.columns.get_level_values(0):
            A.check(False, f"{t}: no price data", critical=False); continue
        d = raw[t].dropna(subset=["Close", "Adj Close"])
        if len(d) < 30:
            A.check(False, f"{t}: fewer than 30 sessions", critical=False); continue
        close, adj, vol = d["Close"], d["Adj Close"], d["Volume"].fillna(0)
        last = d.index[-1]
        stale = (as_of - last).days > 4
        A.check(not stale, f"{t}: last close {last.date()} older than as-of", critical=False)

        # integrity: positive, finite, no unexplained jumps in total-return series
        A.check(bool((adj > 0).all() and np.isfinite(adj).all()), f"{t}: non-positive/NaN adjusted price")
        jumps = adj.pct_change().abs()
        big = jumps[jumps > 0.40]
        A.check(big.empty or ac in ("Digital Assets", "Commodity"), f"{t}: unexplained daily move >40% on {list(big.index.date)[:3]}", critical=False)

        px = float(close.iloc[-1])
        y1 = close[close.index > last - pd.DateOffset(years=1)]
        hi, lo = float(y1.max()), float(y1.min())
        A.check(lo - 1e-9 <= px <= hi + 1e-9, f"{t}: price outside 52w range")

        r = {
            "1d": (adj.iloc[-1] / adj.iloc[-2] - 1) * 100 if len(adj) > 1 else None,
            "1w": ret_since(adj, last - pd.DateOffset(weeks=1)),
            "1m": ret_since(adj, last - pd.DateOffset(months=1)),
            "3m": ret_since(adj, last - pd.DateOffset(months=3)),
            "6m": ret_since(adj, last - pd.DateOffset(months=6)),
            "ytd": ret_since(adj, pd.Timestamp(year=last.year - 1, month=12, day=31)),
            "1y": ret_since(adj, last - pd.DateOffset(years=1)) if adj.index[0] <= last - pd.DateOffset(years=1) else None,
            "3y": cagr_since(adj, 3), "5y": cagr_since(adj, 5),
        }
        # independent recompute of 1M via positional search must agree
        base_1m = adj[adj.index <= last - pd.DateOffset(months=1)]
        if not base_1m.empty and r["1m"] is not None:
            alt = (adj.values[-1] / adj.values[len(base_1m) - 1] - 1) * 100
            A.check(abs(alt - r["1m"]) < 1e-6, f"{t}: 1M return recompute mismatch")

        dr = np.log(adj).diff().dropna()
        dr1 = dr[dr.index > last - pd.DateOffset(years=1)]
        volat = float(dr1.std() * math.sqrt(252) * 100) if len(dr1) > 60 else None
        a3 = adj[adj.index > last - pd.DateOffset(years=3)]
        mdd = float(((a3 / a3.cummax()) - 1).min() * 100) if len(a3) > 60 else None
        if volat is not None:
            A.check(0 < volat < 250, f"{t}: volatility {volat:.1f}% out of range")
        if mdd is not None:
            A.check(-100 <= mdd <= 0, f"{t}: drawdown out of range")

        beta = None
        j = pd.concat([dr1, np.log(spy_adj).diff().reindex(dr1.index)], axis=1).dropna()
        if len(j) > 120:
            c = np.cov(j.iloc[:, 0], j.iloc[:, 1]); beta = float(c[0, 1] / c[1, 1])

        dv = (close * vol)
        adv = float(dv.tail(20).mean()); adv_med = float(dv.tail(60).median())

        wk = adj.reindex(adj.index.union(pd.DatetimeIndex(weeks))).ffill().reindex(weeks)
        first = adj.index[0]
        w = [r4(v) if (dt >= first and pd.notna(v)) else None for dt, v in zip(weeks, wk.values)]
        A.check(w[-1] is not None and abs(w[-1] - round(float(adj.iloc[-1]), 4)) < 1e-6 or stale,
                f"{t}: weekly series does not end at last adjusted close")
        A.check(sum(v is not None for v in w) >= MIN_WEEKS or (adj.index[0] > as_of - pd.Timedelta(weeks=MIN_WEEKS)),
                f"{t}: gaps in weekly series", critical=False)

        # trend chips (weekly)
        ws = adj.resample("W-FRI").last().dropna()
        def chip(sma_n, ret_w, rising=False):
            if len(ws) < sma_n + 1: return None
            sma = ws.rolling(sma_n).mean()
            above = ws.iloc[-1] > sma.iloc[-1]
            rr = ws.iloc[-1] / ws.iloc[-1 - min(ret_w, len(ws) - 1)] - 1
            up = rr > 0 and (not rising or sma.iloc[-1] > sma.iloc[-5])
            if above and up: return 1
            if (not above) and rr < 0: return -1
            return 0
        trend = [chip(10, 13), chip(26, 26), chip(52, 52, rising=True)]

        f = fetch_facts(t)
        adj_last[t] = float(adj.iloc[-1])
        deep = deep_stats(adj, spy_adj, rf_adj)
        for k in ("mo",):
            A.check(all(v is None or v > 0 for v in deep[k]), f"{t}: non-positive monthly close")
        for y, v in deep.get("sip", {}).items():
            A.check(-99 < v[0] < 500, f"{t}: SIP {y} XIRR {v[0]} out of range", critical=False)
        for k in ("roll1", "roll3"):
            if deep.get(k):
                lo_, md_, hi_ = deep[k][:3]
                A.check(lo_ <= md_ <= hi_, f"{t}: rolling {k} min/median/max out of order")
        deep.update(fund_holdings(t))
        if deep.get("hold"):
            A.check(all(0 < h[2] <= 100 for h in deep["hold"]) and sum(h[2] for h in deep["hold"]) <= 100.5, f"{t}: holding weights out of range", critical=False)
        er = f.get("er")
        if er is not None:
            A.check(0 <= er <= 3.0, f"{t}: expense ratio {er} outside 0–3%")
            if not (0 <= er <= 3.0): er = None
        else:
            A.check(False, f"{t}: expense ratio unavailable", critical=False)
        aum = f.get("aum")
        if aum is not None and aum <= 0: aum = None

        # day-over-day continuity vs previous publish
        if prev and t in prev and prev[t].get("asOf") and prev[t]["asOf"] < str(last.date()):
            p_px = prev[t].get("px")
            if p_px:
                implied = (px / p_px - 1) * 100
                A.check(abs(implied) < 30 or ac in ("Digital Assets", "Commodity"),
                        f"{t}: {implied:.1f}% move vs previous publish", critical=False)

        out.append({
            "t": t, "n": f.get("name") or nm, "iss": f.get("issuer") or nm.split()[0],
            "ac": ac, "reg": reg, "role": role, "cat": cat,
            "px": r4(px, 2), "asOf": str(last.date()), "stale": stale,
            "r": {k: r4(v, 2) for k, v in r.items()},
            "vol": r4(volat, 2), "mdd": r4(mdd, 2), "beta": r4(beta, 2),
            "hi": r4(hi, 2), "lo": r4(lo, 2), "adv": r4(adv, 0), "advMed": r4(adv_med, 0),
            "er": r4(er, 3), "aum": r4(aum, 0), "yld": r4(f.get("yld"), 2), "inc": f.get("inc"),
            "trend": trend, "w": w, **deep,
        })

    # missing vs previous publish
    if prev:
        missing = set(prev) - {e["t"] for e in out}
        A.check(not missing, f"ETFs missing vs previous publish: {sorted(missing)}", critical=False)
    A.check(len(out) >= 0.9 * len(U), f"only {len(out)} of {len(U)} ETFs built")
    present = {e["t"] for e in out}
    for b in BENCHMARKS:
        A.check(b in present, f"benchmark {b} missing")

    # engine reference modes vs SPY, computed from the exported (rounded) series
    spyw = next(e["w"] for e in out if e["t"] == "SPY")
    for e in out:
        g = rrg(e["w"], spyw)
        e["m"] = g["mode"] if g else None
        if g:
            A.check(math.isfinite(g["ratio"]) and math.isfinite(g["mom"]), f"{e['t']}: engine non-finite")

    plans = all_plans(out, str(as_of.date()))
    for pid, p in plans.items():
        A.check(bool(p["rows"]) and abs(sum(x["w"] for x in p["rows"]) - 100) < 0.01, f"plan {pid}: weights do not add to 100")
    daily = daily_export(raw, as_of)
    for t in {x["t"] for p in plans.values() for x in p["rows"]} | set(MARKET):
        cl = daily["c"].get(t) or []
        A.check(bool(cl) and cl[-1] is not None, f"{t}: no official close on {as_of.date()} for the simulator", critical=False)

    try:
        with open(os.path.join(os.path.dirname(OUT), "mf", "macro.json")) as f:
            macro = json.load(f)
    except Exception:
        macro = {}
    dip = dip_block(daily, macro)
    A.check(len(dip["segments"]) >= 4, f"market-dip block: only {len(dip['segments'])} segments", critical=False)
    # ---- extended accuracy checks: plans, dip readings and the long-history figures of every ETF
    by_t = {e["t"]: e for e in out}
    for pid, p in plans.items():
        for x in p["rows"]:
            A.check(x["t"] in by_t, f"plan {pid}: {x['t']} is not in the published list")
            A.check(0 < x["w"] <= 100, f"plan {pid}: weight {x['w']} out of range")
        A.check(len({x["k"] for x in p["rows"]}) == len(p["rows"]), f"plan {pid}: a slot appears twice")
    for k, sg in dip["segments"].items():
        A.check(len(sg["checks"]) == 12, f"dip {k}: {len(sg['checks'])} market checks instead of 12")
        A.check(sg["held"] <= max(sg["raw"], sg["held"]) and sg["held"] in [0] + dip["tiers"], f"dip {k}: held level {sg['held']} invalid")
        A.check(0 <= sg["fall"] <= 100 and sg["close"] > 0 and sg["high"] >= sg["close"] - 1e-9, f"dip {k}: fall / close / high inconsistent")
        A.check(not sg["signal"] or sg["mktOk"], f"dip {k}: signal without every market check")
    for e in out:
        t = e["t"]
        mo = [v for v in (e.get("mo") or []) if v]
        if mo:
            A.check(abs(mo[-1] / adj_last[t] - 1) < 1e-4, f"{t}: last month-end close differs from the latest adjusted close")
        for y, v in (e.get("sip") or {}).items():
            months = int(v[1] / 100)
            A.check(v[1] % 100 == 0 and 12 * int(y[0]) - 1 <= months <= 12 * int(y[0]) + 1, f"{t}: SIP {y} has {months} instalments")
            A.check(v[2] > 0 and (abs(v[0]) < 0.5 or (v[0] >= 0) == (v[2] >= v[1])), f"{t}: SIP {y} XIRR sign does not match its value", critical=False)
        for k in ("roll1", "roll3"):
            v = e.get(k)
            if v:
                A.check(0 <= v[3] <= 100 and v[4] >= 26, f"{t}: {k} share positive / periods out of range")
        cal = e.get("cal") or {}
        ytd = next((v for kk, v in cal.items() if kk.endswith("YTD")), None)
        if ytd is not None and e["r"].get("ytd") is not None:
            A.check(abs(ytd - e["r"]["ytd"]) < 0.6, f"{t}: calendar YTD {ytd} vs YTD return {e['r']['ytd']}", critical=False)
        if e.get("hold"):
            A.check(e["hold"] == sorted(e["hold"], key=lambda h: -h[2]), f"{t}: holdings not sorted by weight", critical=False)
        if e.get("shp") is not None and e.get("vol"):
            A.check(-10 < e["shp"] < 10, f"{t}: Sharpe {e['shp']} out of range", critical=False)

    doc = {
        "version": 1,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asOf": str(as_of.date()),
        "weeks": [str(w.date()) for w in weeks],
        "benchmarks": BENCHMARKS,
        "engineRef": "SPY",
        "audit": {"passed": A.passed, "critical": len(A.critical), "warnings": len(A.warnings)},
        "etfs": out,
        "plans": plans,
        "dip": dip,
    }
    print(f"as-of {doc['asOf']}  ETFs {len(out)}  checks passed {A.passed}  "
          f"critical {len(A.critical)}  warnings {len(A.warnings)}")
    for m in A.critical: print("  CRITICAL:", m)
    for m in A.warnings[:40]: print("  warn:", m)

    if A.critical:
        print("Audit failed — previous data left online."); return 1
    # never go backwards: a later retry whose download lacks the newest session must not replace newer data
    try:
        with open(OUT) as f:
            prev = json.load(f).get("asOf")
        if prev and prev > doc["asOf"]:
            print(f"Downloaded data ends {doc['asOf']}, older than the published {prev} — previous data left online."); return 0
    except (OSError, ValueError):
        pass
    if dry:
        print("Dry run — not written."); return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, separators=(",", ":"), allow_nan=False)
    os.replace(tmp, OUT)
    with open(DAILY_OUT + ".tmp", "w") as f:
        json.dump(daily, f, separators=(",", ":"), allow_nan=False)
    os.replace(DAILY_OUT + ".tmp", DAILY_OUT)
    print("Published", os.path.relpath(OUT), "and", os.path.relpath(DAILY_OUT)); return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true")
    sys.exit(build(ap.parse_args().dry_run))
