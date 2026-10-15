import json, re, requests
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"})
PAGES = {
 "ppfas": "https://amc.ppfas.com/downloads/portfolio-disclosure/",
 "sbi": "https://www.sbimf.com/portfolios",
 "hdfc": "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio",
 "icici": "https://www.icicipruamc.com/downloads/others/monthly-portfolio-disclosures",
 "nippon": "https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures",
 "kotak": "https://www.kotakmf.com/Information/portfolios",
 "axis": "https://www.axismf.com/statutory-disclosures",
 "absl": "https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio",
 "uti": "https://www.utimf.com/downloads/consolidate-all-portfolio-disclosure",
 "mirae": "https://www.miraeassetmf.co.in/downloads/portfolios",
 "dsp": "https://www.dspim.com/mandatory-disclosures/portfolio-disclosures",
 "tata": "https://www.tatamutualfund.com/schemes-related/portfolio",
 "motilal": "https://www.motilaloswalmf.com/download/month-end-portfolio",
 "bandhan": "https://bandhanmutual.com/downloads/disclosures",
 "edelweiss": "https://www.edelweissmf.com/statutory-disclosures/portfolio-disclosure",
 "canara": "https://www.canararobeco.com/documents/statutory-disclosures/scheme-monthly-portfolio",
 "franklin": "https://www.franklintempletonindia.com/downloads/fund-documents/monthly-portfolio",
 "hsbc": "https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library",
 "invesco": "https://invescomutualfund.com/literature-and-form?tab=Complete",
 "quant": "https://quantmutual.com/statutory-disclosures",
}
res = {}
for k, u in PAGES.items():
    try:
        r = S.get(u, timeout=40)
        t = r.text
        links = sorted(set(re.findall(r'(?:href|src|url)=["\']([^"\']+\.(?:xlsx|xls|zip|xlsm)[^"\']*)', t, re.I)))
        jsonish = sorted(set(re.findall(r'https?://[^"\'\s]+\.(?:xlsx|xls|zip)', t, re.I)))
        res[k] = {"status": r.status_code, "len": len(t), "links": len(links), "sample": links[:6], "abs": jsonish[:6],
                  "final": r.url}
    except Exception as e:
        res[k] = {"err": repr(e)[:200]}
    print(k, json.dumps(res[k])[:900])
# AMFI sitemap
try:
    sm = S.get("https://www.amfiindia.com/sitemap.xml", timeout=40).text
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    print("AMFI sitemap", len(locs), [l for l in locs if re.search(r"scheme|portfolio|exit|aum|load|fact", l, re.I)][:60])
except Exception as e:
    print("sitemap err", e)
json.dump(res, open(".probe/probe3.json", "w"), indent=1)
