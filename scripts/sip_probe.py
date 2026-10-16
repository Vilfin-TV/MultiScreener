"""Temporary probe 2: valuation history + 10Y yield."""
import json, re, requests, time, io
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"}
out = {}
def tryit(k, fn):
    try: out[k] = fn()
    except Exception as e: out[k] = "ERR " + str(e)[:200]
def nse_session():
    s = requests.Session(); s.headers.update({**UA, "Accept": "*/*", "Referer": "https://www.nseindia.com/"})
    s.get("https://www.nseindia.com", timeout=20); return s
def closeall():
    s = nse_session(); res = {}
    for d in ["15102026", "30092026", "29092021", "31012017", "30062016"]:
        r = s.get(f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{d}.csv", timeout=40)
        lines = r.text.splitlines()
        res[d] = [r.status_code, len(lines), lines[:1], [l for l in lines if re.match(r'"?(Nifty 50|Nifty Auto|NIFTY 10 yr|Nifty 10 yr|Nifty Realty)', l, re.I)][:6]]
        time.sleep(1)
    return res
tryit("ind_close_all", closeall)
def bondidx():
    s = nse_session(); j = s.get("https://www.nseindia.com/api/allIndices", timeout=30).json()
    return [ {k: x.get(k) for k in ("index", "last", "pe", "pb", "dy", "key")} for x in j.get("data", []) if re.search(r"g-?sec|bond|gilt|yield|sdl|t-?bill", x.get("index",""), re.I)] + [sorted({x.get("key") for x in j.get("data", [])})]
tryit("nse_bond_indices", bondidx)
def fred():
    res = {}
    for sid in ["INDIRLTLT01STM", "IR3TIB01INM156N"]:
        r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", headers=UA, timeout=90)
        lines = r.text.strip().splitlines(); res[sid] = [r.status_code, len(lines), lines[-3:]]
    return res
tryit("fred", fred)
def wgb():
    res = {}
    for u in ["https://www.ccilindia.com/web/ccil/tenor-wise-yields", "https://www.ccilindia.com/web/ccil/zcyc", "https://www.rbi.org.in/Scripts/BS_NSDPDisplay.aspx?param=4",
              "https://tradingeconomics.com/india/government-bond-yield", "https://www.cnbc.com/quotes/IN10Y-IN", "https://www.marketwatch.com/investing/bond/tmbmkin-10y?countrycode=bx",
              "https://query1.finance.yahoo.com/v8/finance/chart/IN10Y.BOND?range=5d&interval=1d"]:
        try:
            r = requests.get(u, headers=UA, timeout=40)
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
            res[u] = [r.status_code, len(r.text), re.findall(r"(?:10[- ]?(?:Yr|Year|Y)\b[^0-9]{0,80}[0-9]\.[0-9]{2,4})", txt)[:4], txt[:200] if r.status_code != 200 else re.findall(r"[0-9]\.[0-9]{3,4}\s*%", txt)[:8]]
        except Exception as e:
            res[u] = str(e)[:150]
    return res
tryit("yield_pages", wgb)
def niftyxhr():
    from playwright.sync_api import sync_playwright
    caps = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.on("request", lambda rq: caps.append([rq.method, rq.url[:160], (rq.post_data or "")[:200]]) if rq.resource_type in ("xhr", "fetch") else None)
        pg.goto("https://www.niftyindices.com/reports/historical-data", timeout=60000); pg.wait_for_timeout(5000)
        html = pg.content()
        btns = re.findall(r'id="([^"]*(?:pe|PE|Pe|pepb|PEPB)[^"]*)"', html)[:20]
        b.close()
    return {"xhr": caps[:30], "ids": btns}
tryit("niftyindices_xhr", niftyxhr)
json.dump(out, open(".probe/sip_probe2.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str)[:9000])
