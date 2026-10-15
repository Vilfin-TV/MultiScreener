#!/usr/bin/env python3
"""One-off probe of public MF data sources (run in GitHub Actions). Saves samples to .probe/."""
import json, re, sys, time, traceback
from pathlib import Path
import requests

OUT = Path(".probe"); OUT.mkdir(exist_ok=True)
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                  "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"})
report = {}

def probe(name, fn):
    t = time.time()
    try:
        r = fn()
        report[name] = {"ok": True, "info": r, "sec": round(time.time() - t, 1)}
    except Exception as e:
        report[name] = {"ok": False, "err": repr(e)[:400], "sec": round(time.time() - t, 1)}
        traceback.print_exc()
    print(name, json.dumps(report[name])[:600], flush=True)

def get(url, **kw):
    r = S.get(url, timeout=60, **kw); return r

# 1. AMFI NAVAll
navall = {}
def p_navall():
    for u in ["https://www.amfiindia.com/spages/NAVAll.txt", "https://portal.amfiindia.com/spages/NAVAll.txt"]:
        r = get(u)
        navall[u] = r
    r = navall["https://www.amfiindia.com/spages/NAVAll.txt"]
    if r.status_code != 200 or len(r.text) < 10000:
        r = navall["https://portal.amfiindia.com/spages/NAVAll.txt"]
    (OUT / "NAVAll.txt").write_text(r.text)
    return {u: [x.status_code, len(x.text)] for u, x in navall.items()}
probe("navall", p_navall)

# find reference funds
REF = {
 "flexi":   r"Parag Parikh Flexi Cap Fund.*Direct.*Growth",
 "large":   r"ICICI Prudential (Bluechip|Large Cap) Fund.*Direct.*Growth",
 "small":   r"Nippon India Small Cap Fund.*Direct.*Growth",
 "elss":    r"Mirae Asset (Tax Saver|ELSS Tax Saver) Fund.*Direct.*Growth",
 "liquid":  r"SBI Liquid Fund.*Direct.*Growth",
 "gilt":    r"ICICI Prudential Gilt Fund.*Direct.*Growth",
 "baf":     r"HDFC Balanced Advantage Fund.*Direct.*Growth",
 "gold":    r"Nippon India Gold Savings Fund.*Direct.*Growth",
 "nasdaq":  r"Motilal Oswal Nasdaq 100 Fund of Fund.*Direct.*Growth",
 "nifty50": r"UTI Nifty 50 Index Fund.*Direct.*Growth",
 "mom30":   r"UTI Nifty200 Momentum 30 Index Fund.*Direct.*Growth",
 "lowvol":  r"(ICICI Prudential|UTI) Nifty ?100 Low Vol(atility)? 30 .*Index Fund.*Direct.*Growth",
 "value":   r"Nifty ?500 Value 50 Index Fund.*Direct.*Growth",
 "quality": r"Nifty ?200 Quality 30 Index Fund.*Direct.*Growth",
}
refs = {}
def p_refs():
    txt = (OUT / "NAVAll.txt").read_text()
    cat = amc = None
    rows = []
    for line in txt.splitlines():
        line = line.strip()
        if not line: continue
        if ";" not in line:
            if re.search(r"Schemes\s*\(", line): cat = line
            else: amc = line
            continue
        p = line.split(";")
        if not p[0].isdigit(): continue
        rows.append((p, cat, amc))
    for k, rx in REF.items():
        m = [r for r in rows if re.search(rx, r[0][3] + " Direct Growth" if r[0][4] == "Direct Plan" and re.search("growth", r[0][5], re.I) else r[0][3], re.I) and not re.search(r"IDCW|Dividend|Bonus", r[0][3] + r[0][5], re.I)]
        if m:
            p, c, a = m[0]
            refs[k] = {"code": p[0], "isin": p[1], "name": p[3], "plan": p[4], "opt": p[5], "nav": p[6], "date": p[7], "cat": c, "amc": a, "n": len(m), "all": [x[0][0] for x in m]}
    cats = sorted(set(r[1] for r in rows if r[1]))
    (OUT / "categories.txt").write_text("\n".join(cats))
    dg = [r for r in rows if r[0][4] == "Direct Plan" and re.search(r"growth", r[0][5], re.I) and r[1] and r[1].startswith("Open")]
    (OUT / "refs.json").write_text(json.dumps(refs, indent=1))
    return {"rows": len(rows), "cats": len(cats), "direct_growth_open": len(dg), "refs": {k: v["name"] for k, v in refs.items()}}
probe("refs", p_refs)

# 2. mfapi history
def p_mfapi():
    out = {}
    for k, v in refs.items():
        r = get(f"https://api.mfapi.in/mf/{v['code']}")
        out[k] = [r.status_code, len(r.text)]
        if r.status_code == 200:
            (OUT / f"hist_{k}.json").write_text(r.text)
    return out
probe("mfapi", p_mfapi)

# 3. AMFI NAV history report (portal)
def p_amfi_hist():
    u = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?mf=53&tp=1&frmdt=01-Sep-2026&todt=10-Sep-2026"
    r = get(u); (OUT / "amfi_hist_sample.txt").write_text(r.text[:20000])
    return [r.status_code, len(r.text), r.text[:300]]


# 4. Kuvera via captnemo (ISIN)
def p_kuvera():
    out = {}
    for k in list(refs):
        if k not in refs: continue
        r = get(f"https://mf.captnemo.in/kuvera/{refs[k]['isin']}")
        out[k] = [r.status_code, len(r.text)]
        if r.status_code == 200: (OUT / f"kuvera_{k}.json").write_text(r.text)
    return out
probe("kuvera", p_kuvera)

# 5. niftyindices TRI
def p_nifty():
    out = {}
    hdr = {"Content-Type": "application/json; charset=UTF-8", "Accept": "application/json, text/javascript, */*; q=0.01", "Origin": "https://www.niftyindices.com",
           "Referer": "https://www.niftyindices.com/reports/historical-data", "X-Requested-With": "XMLHttpRequest"}
    get("https://www.niftyindices.com/reports/historical-data")
    for name in ["NIFTY 50"]:
        cinfo = "{'name':'%s','startDate':'01-Sep-2026','endDate':'14-Oct-2026','indexName':'%s'}" % (name, name)
        r = S.post("https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString", json={"cinfo": cinfo}, headers=hdr, timeout=60)
        out[name] = [r.status_code, r.text[:300]]
        if r.status_code == 200 and r.text.lstrip().startswith("{"): (OUT / f"tri_{name.replace(' ', '_')}.json").write_text(r.text)
    return out
probe("niftyindices", p_nifty)

# 6. yfinance indices
def p_yf():
    import yfinance as yf
    out = {}
    for s in ["^NSEI", "^CRSLDX", "^NSEMDCP50", "NIFTY_MIDCAP_100.NS", "^CNXSC"]:
        h = yf.Ticker(s).history(period="1mo")
        out[s] = len(h)
    return out


# 7. AMFI pages (TER / performance / AUM) – save HTML to discover APIs
def p_pages():
    out = {}
    for n, u in {"ter": "https://www.amfiindia.com/ter-of-mf-schemes",
                 "perf": "https://www.amfiindia.com/research-information/other-data/mf-scheme-performance-details",
                 "aum": "https://www.amfiindia.com/research-information/aum-data/average-aum",
                 "otherdata": "https://www.amfiindia.com/otherdata/fund-performance",
                 "mfapi_all": "https://api.mfapi.in/mf"}.items():
        r = get(u); out[n] = [r.status_code, len(r.text), r.url]
        (OUT / f"page_{n}.html").write_text(r.text[:400000])
    return out

def p_chunks():
    out = {}
    base = "https://www.amfiindia.com"
    for n, u in {"ter": base + "/ter-of-mf-schemes", "perf": base + "/otherdata/fund-performance",
                 "aum": base + "/otherdata/aum", "navhist": base + "/net-asset-value/nav-history"}.items():
        r = get(u); out[n] = [r.status_code]
        js = sorted(set(re.findall(r'/_next/static/chunks/[^"\']+\.js', r.text)))
        hits = set()
        for j in js:
            if not re.search(r"app/|page", j): continue
            t = get(base + j).text
            for m in re.findall(r'["\'`]((?:https?://[^"\'`\s]*)?/?api[^"\'`\s]{2,200})["\'`]', t):
                hits.add(m)
            for m in re.findall(r'["\'`](https?://[^"\'`\s]{5,200})["\'`]', t):
                hits.add(m)
        out[n].append(sorted(hits)[:80])
    (OUT / "amfi_api_hits.json").write_text(json.dumps(out, indent=1))
    return {k: len(v[1]) if len(v) > 1 else v for k, v in out.items()}
probe("chunks", p_chunks)

def p_nse():
    out = {}
    s2 = requests.Session(); s2.headers.update(S.headers)
    s2.headers.update({"Accept": "application/json, text/plain, */*", "Referer": "https://www.nseindia.com/reports-indices-historical-index-data"})
    r = s2.get("https://www.nseindia.com/", timeout=30); out["home"] = r.status_code
    for name in ["NIFTY 50", "NIFTY200 MOMENTUM 30"]:
        u = "https://www.nseindia.com/api/historicalOR/indicesHistory?indexType=%s&from=01-09-2026&to=14-10-2026" % requests.utils.quote(name)
        r = s2.get(u, timeout=30); out[name] = [r.status_code, r.text[:400]]
        u2 = "https://www.nseindia.com/api/historical/indicesHistory?indexType=%s&from=01-09-2026&to=14-10-2026" % requests.utils.quote(name)
        r = s2.get(u2, timeout=30); out[name + "_v1"] = [r.status_code, r.text[:400]]
    return out
probe("nse", p_nse)


(OUT / "report.json").write_text(json.dumps(report, indent=1))
