"""Temporary probe: index valuations, policy rates, government bond yields."""
import json, re, requests, time
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"}
out = {}
def tryit(k, fn):
    try:
        out[k] = fn()
    except Exception as e:
        out[k] = "ERR " + str(e)[:200]
S = requests.Session(); S.headers.update(UA)
# 1. niftyindices P/E P/B history
def ni():
    S.get("https://www.niftyindices.com/reports/historical-data", timeout=30)
    res = {}
    for name in ["NIFTY 50", "NIFTY 500", "NIFTY AUTO", "NIFTY PHARMA", "NIFTY REALTY", "NIFTY INDIA MANUFACTURING", "NIFTY HEALTHCARE INDEX"]:
        body = {"cinfo": json.dumps({"name": name, "startDate": "01-Jan-2016", "endDate": "15-Oct-2026", "indexName": name}).replace('"', "'")}
        r = S.post("https://www.niftyindices.com/Backpage.aspx/getpepbHistoricaldataDBtoString", json=body,
                   headers={"Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest",
                            "Referer": "https://www.niftyindices.com/reports/historical-data", "Origin": "https://www.niftyindices.com"}, timeout=60)
        t = r.text
        try:
            arr = json.loads(json.loads(t)["d"])
            res[name] = {"n": len(arr), "first": arr[-1] if arr else None, "last": arr[0] if arr else None}
        except Exception:
            res[name] = [r.status_code, t[:300]]
        time.sleep(1)
    return res
tryit("niftyindices", ni)
# 2. NSE all indices (current pe/pb/dy)
def nse():
    s = requests.Session(); s.headers.update({**UA, "Accept": "application/json", "Referer": "https://www.nseindia.com/"})
    s.get("https://www.nseindia.com", timeout=20)
    j = s.get("https://www.nseindia.com/api/allIndices", timeout=30).json()
    d = j.get("data", [])
    return {"n": len(d), "sample": [{k: x.get(k) for k in ("index", "last", "pe", "pb", "dy", "perChange365d")} for x in d if x.get("index") in ("NIFTY 50", "NIFTY AUTO", "NIFTY REALTY", "NIFTY PHARMA", "NIFTY 500")]}
tryit("nse_allIndices", nse)
# 3. RBI home page rates
def rbi():
    res = {}
    for u in ["https://www.rbi.org.in/", "https://website.rbi.org.in/web/rbi"]:
        try:
            t = S.get(u, timeout=40).text
            txt = re.sub(r"<[^>]+>", " ", t); txt = re.sub(r"\s+", " ", txt)
            res[u] = [m for m in re.findall(r"(?:Policy Repo Rate|Repo Rate|Standing Deposit|Marginal Standing|Bank Rate|91 day|182 day|364 day|T-Bill|10 Year|G-Sec|CRR|SLR)[^0-9%]{0,40}[0-9.]+\s*%?", txt)][:30]
        except Exception as e:
            res[u] = str(e)[:150]
    return res
tryit("rbi", rbi)
# 4. FRED series
def fred():
    res = {}
    for sid in ["INDIRLTLT01STM", "IR3TIB01INM156N", "INTDSRINM193N", "INDCPIALLMINMEI"]:
        r = S.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=40)
        lines = r.text.strip().splitlines()
        res[sid] = [r.status_code, len(lines), lines[:2], lines[-3:]]
    return res
tryit("fred", fred)
# 5. other yield pages
def others():
    res = {}
    for u in ["https://www.ccilindia.com/web/ccil/home", "https://www.fbil.org.in/", "https://www.worldgovernmentbonds.com/bond-historical-data/india/10-years/",
              "https://in.investing.com/rates-bonds/india-10-year-bond-yield-historical-data"]:
        try:
            r = S.get(u, timeout=40)
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
            res[u] = [r.status_code, re.findall(r"(?:10[- ]?(?:Yr|Year)[^0-9]{0,60}[0-9]\.[0-9]{2,4})", txt)[:5]]
        except Exception as e:
            res[u] = str(e)[:150]
    return res
tryit("others", others)
json.dump(out, open(".probe/sip_probe.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str)[:6000])
