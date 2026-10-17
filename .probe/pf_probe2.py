"""Temporary: look for monthly portfolio files on known disclosure pages of the larger fund houses."""
import json, re, sys, time
sys.path.insert(0, "scripts")
import build_mf_holdings as H
from playwright.sync_api import sync_playwright

PAGES = {
 "Axis": ["https://www.axismf.com/statutory-disclosures", "https://www.axismf.com/downloads/monthly-portfolio", "https://www.axismf.com/downloads/portfolio"],
 "Kotak Mahindra": ["https://www.kotakmf.com/Information/portfolios", "https://www.kotakmf.com/Information/corporate-disclosure"],
 "UTI": ["https://www.utimf.com/downloads/consolidate-all-portfolio-disclosure", "https://www.utimf.com/downloads/portfolio-disclosure"],
 "Motilal Oswal": ["https://www.motilaloswalmf.com/download/month-end-portfolio", "https://www.motilaloswalmf.com/download/scheme-portfolio-details"],
 "Franklin Templeton": ["https://www.franklintempletonindia.com/downloads/fund-documents#portfolio-disclosures", "https://www.franklintempletonindia.com/reports"],
 "quant": ["https://quantmutual.com/statutory-disclosures", "https://quantmutual.com/downloads"],
 "Bandhan": ["https://bandhanmutual.com/downloads/disclosures", "https://bandhanmutual.com/statutory-disclosures"],
 "HSBC": ["https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library"],
 "Edelweiss": ["https://www.edelweissmf.com/statutory/portfolio-of-schemes", "https://www.edelweissmf.com/downloads"],
 "Sundaram": ["https://www.sundarammutual.com/Statutory-Disclosures", "https://www.sundarammutual.com/Portfolio-Disclosure"],
 "Mahindra Manulife": ["https://www.mahindramanulife.com/downloads", "https://www.mahindramanulife.com/statutory-disclosures"],
 "PGIM India": ["https://www.pgimindia.com/mutual-funds/statutory-disclosures/portfolio-disclosure", "https://www.pgimindiamf.com/statutory-disclosure"],
 "Union": ["https://unionmf.com/about-us/downloads/portfolio-disclosure", "https://unionmf.com/downloads"],
 "Bank of India": ["https://www.boimf.in/investor-corner", "https://www.boimf.in/investor-corner/statutory-disclosures"],
 "ITI": ["https://www.itiamc.com/statutory-disclosure", "https://www.itiamc.com/downloads"],
 "Navi": ["https://navi.com/mutual-fund/downloads", "https://navi.com/mutual-fund/statutory-disclosures"],
 "Taurus": ["https://www.taurusmutualfund.com/statutory-disclosure", "https://www.taurusmutualfund.com/downloads"],
 "WhiteOak Capital": ["https://mf.whiteoakamc.com/regulatory-disclosures/scheme-portfolios", "https://mf.whiteoakamc.com/downloads"],
 "Bajaj Finserv": ["https://www.bajajamc.com/downloads", "https://www.bajajamc.com/statutory-disclosures"],
 "NJ": ["https://www.njmutualfund.com/statutory-disclosures", "https://www.njmutualfund.com/downloads"],
 "Canara Robeco": ["https://www.canararobeco.com/documents/statutory-disclosures/scheme-dashboard/scheme-monthly-portfolio/"],
 "Quantum": ["https://www.quantumamc.com/portfolio/combined/-1/1/0/0", "https://www.quantumamc.com/statutory-disclosures"],
 "Jio BlackRock": ["https://www.jioblackrockamc.com/statutory-disclosures", "https://www.jioblackrockamc.com/downloads"],
 "Choice": ["https://choicemf.com/disclosures/portfolio", "https://choicemf.com/information/notice-fortnightly-monthly-portfolios"],
 "The Wealth Company": ["https://www.wealthcompanyamc.in/statutory-disclosures"],
 "Angel One": ["https://www.angelonemf.com/statutory-disclosures"],
 "AlphaGrep": ["https://www.alphagrepmf.com/statutory-disclosures"],
 "Monarch": ["https://www.monarchmf.com/statutory-disclosures"],
 "Lakshya": ["https://www.lakshyamf.com/statutory-disclosures"],
}
only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
out = {}
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False)
    ctx = br.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36", accept_downloads=True)
    ctx.set_default_timeout(30000)
    for amc, pages in PAGES.items():
        if only and amc not in only: continue
        t0 = time.time(); rec = {"pages": [], "files": [], "links": []}
        for url in pages:
            if time.time() - t0 > 150: break
            try:
                p = ctx.new_page(); p.goto(url, wait_until="domcontentloaded", timeout=45000); p.wait_for_timeout(2500)
                title = p.title()[:80]; final = p.url
                links = p.eval_on_selector_all("a", "as => as.map(a => [a.href, (a.innerText||a.title||'').trim().slice(0,80)])")
                p.close()
                rec["links"] += [l for l in links if l[0].startswith("http") and re.search(r"portfolio", l[0] + l[1], re.I)][:25]
                fs = [f for f in dict.fromkeys(H.harvest(ctx, url)) if H.FILE_RX.search(f)]
                rec["pages"].append([url, final, title, len(fs)])
                rec["files"] += [[f, H.link_month(f)] for f in fs if re.search(r"portfol|holding", f, re.I) and not re.search(r"fortnight|overlap|half", f, re.I)]
            except Exception as e:
                rec["pages"].append([url, "ERR " + str(e)[:100]])
        rec["files"] = list({f[0]: f for f in rec["files"]}.values())[:80]
        out[amc] = rec
        print(amc, len(rec["files"]), len(rec["links"]), round(time.time() - t0), flush=True)
    br.close()
json.dump(out, open(".probe/pf_probe2.json", "w"), indent=1)
