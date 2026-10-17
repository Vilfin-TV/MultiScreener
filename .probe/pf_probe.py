"""Temporary: find monthly portfolio files for fund houses without a source and test-parse the newest one."""
import json, re, sys, time
from urllib.parse import urljoin, urlparse
sys.path.insert(0, "scripts")
import build_mf_holdings as H
from playwright.sync_api import sync_playwright

sites = json.load(open("data/mf/scheme_pages.json"))["_sites"]
GUESS = {
    "Kotak Mahindra": ["https://www.kotakmf.com/Information/portfolios"],
    "Axis": ["https://www.axismf.com/statutory-disclosures", "https://www.axismf.com/downloads"],
    "Bandhan": ["https://bandhanmutual.com/downloads/disclosures", "https://bandhanmutual.com/downloads"],
    "UTI": ["https://www.utimf.com/downloads/consolidate-all-portfolio-disclosure", "https://www.utimf.com/downloads"],
    "Edelweiss": ["https://www.edelweissmf.com/statutory/portfolio-of-schemes", "https://www.edelweissmf.com/downloads"],
    "Motilal Oswal": ["https://www.motilaloswalmf.com/download/month-end-portfolio", "https://www.motilaloswalmf.com/downloads"],
    "Franklin Templeton": ["https://www.franklintempletonindia.com/downloads/fund-documents", "https://www.franklintempletonindia.com/investor/reports"],
    "LIC": ["https://www.licmf.com/downloads", "https://www.licmf.com/statutory-disclosure"],
    "Sundaram": ["https://www.sundarammutual.com/Monthly-Portfolio", "https://www.sundarammutual.com/Downloads"],
    "Union": ["https://www.unionmf.com/downloads/disclosures", "https://www.unionmf.com/downloads"],
    "quant": ["https://www.quantmutual.com/statutory-disclosures", "https://www.quantmutual.com/downloads"],
    "Canara Robeco": ["https://www.canararobeco.com/statutory-disclosures/scheme-monthly-portfolio", "https://www.canararobeco.com/downloads"],
    "Mahindra Manulife": ["https://www.mahindramanulife.com/downloads"],
    "Bank of India": ["https://www.boimf.in/investor-corner", "https://www.boimf.in/downloads"],
    "Bajaj Finserv": ["https://www.bajajamc.com/downloads", "https://www.bajajamc.com/statutory-disclosures"],
    "ITI": ["https://www.itiamc.com/downloads", "https://www.itiamc.com/statutory-disclosures"],
    "WhiteOak Capital": ["https://mf.whiteoakamc.com/regulatory-disclosures/scheme-portfolios", "https://mf.whiteoakamc.com/downloads"],
    "Jio BlackRock": ["https://www.jioblackrockamc.com/statutory-disclosures", "https://www.jioblackrockamc.com/downloads"],
    "Zerodha": ["https://www.zerodhafundhouse.com/resources/disclosures/"],
    "Navi": ["https://navi.com/mutual-fund/downloads", "https://navi.com/mutual-fund/statutory-disclosures"],
    "Quantum": ["https://www.quantumamc.com/downloads", "https://www.quantumamc.com/statutory-disclosures"],
    "The Wealth Company": ["https://www.wealthcompanyamc.in/statutory-disclosures", "https://www.wealthcompanyamc.in/downloads"],
    "Taurus": ["https://www.taurusmutualfund.com/Download/portfolio.php", "https://www.taurusmutualfund.com/downloads"],
    "NJ": ["https://www.njmutualfund.com/statutory-disclosures"],
    "Angel One": ["https://www.angelonemf.com/statutory-disclosures"],
    "AlphaGrep": [], "Choice": [], "Unifi": ["https://unifimf.com/statutory-disclosures"], "ASK": [], "Lakshya": [], "Monarch": [],
}
todo = [a for a in sys.argv[1].split(",")] if len(sys.argv) > 1 else list(GUESS)
KEY = re.compile(r"portfolio|disclosure|statutory|download|holding", re.I)
BAD = re.compile(r"\.(pdf|jpg|png|svg|mp4)(\?|$)|facebook|twitter|linkedin|youtube|instagram|whatsapp|mailto:|tel:|javascript:", re.I)
out = {}
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False)
    ctx = br.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36", accept_downloads=True)
    ctx.set_default_timeout(30000)
    for amc in todo:
        t0 = time.time()
        site = sites.get(amc, "")
        host = urlparse(site).netloc.replace("www.", "") if site else ""
        rec = {"site": site, "visited": [], "files": [], "pdfs": 0, "parse": []}
        queue = list(dict.fromkeys(GUESS.get(amc, []) + ([site] if site else [])))
        seen = set()
        while queue and len(rec["visited"]) < 12 and time.time() - t0 < 200:
            url = queue.pop(0)
            if url in seen: continue
            seen.add(url)
            try:
                p = ctx.new_page(); p.goto(url, wait_until="domcontentloaded", timeout=45000)
                try: p.wait_for_load_state("networkidle", timeout=12000)
                except Exception: pass
                p.wait_for_timeout(1500)
                links = p.eval_on_selector_all("a", "as => as.map(a => [a.href, (a.innerText||a.title||'').trim().slice(0,80)])")
                final = p.url; p.close()
            except Exception as e:
                rec["visited"].append([url, "ERR " + str(e)[:80]]); continue
            try:
                fs = [f for f in dict.fromkeys(H.harvest(ctx, url)) if H.FILE_RX.search(f)]
            except Exception:
                fs = []
            rec["pdfs"] += sum(1 for h, t in links if re.search(r"\.pdf(\?|$)", h, re.I) and re.search(r"portfolio", h + t, re.I))
            rec["visited"].append([final, len(fs)])
            for f in fs:
                rec["files"].append([f, H.link_month(f), final])
            cands = []
            for href, txt in links:
                if not href.startswith("http") or BAD.search(href) or (host and host not in href): continue
                s = (3 if re.search(r"portfolio", href + txt, re.I) else 0) + (2 if re.search(r"month", href + txt, re.I) else 0) + (1 if KEY.search(href + txt) else 0)
                if s >= 2: cands.append((s, href))
            for _, h in sorted(set(cands), key=lambda x: -x[0])[:8]:
                if h not in seen and h not in queue: queue.append(h)
        # newest portfolio-looking files → download & parse
        files = list({f[0]: f for f in rec["files"]}.values())
        port = [f for f in files if re.search(r"portfolio|holding|port", f[0], re.I) and not re.search(H.SKIP_DEFAULT, f[0], re.I)] or files
        dated = sorted([f for f in port if f[1]], key=lambda f: tuple(f[1]), reverse=True)
        for f in (dated or port)[:2]:
            try:
                r = ctx.request.get(f[0], headers={"Referer": f[2]}, timeout=90000)
                blob = r.body() if r.ok else b""
                res = {"url": f[0], "status": r.status, "bytes": len(blob)}
                if blob[:2] == b"PK" and f[0].lower().split("?")[0].endswith(".zip"):
                    import zipfile, io
                    z = zipfile.ZipFile(io.BytesIO(blob)); res["zip"] = z.namelist()[:20]
                elif blob:
                    blocks = []
                    for sh, rows in H.read_book(blob, f[0].split("?")[0]):
                        blocks += H.parse_sheet(sh, rows)
                    res["blocks"] = len(blocks); res["holdings"] = sum(len(b["holdings"]) for b in blocks)
                    res["titles"] = [b["title"][:70] for b in blocks[:8]]
            except Exception as e:
                res = {"url": f[0], "err": str(e)[:160]}
            rec["parse"].append(res)
        rec["files"] = files[:50]
        rec["secs"] = round(time.time() - t0)
        out[amc] = rec
        print(amc, "files", len(files), "dated", len(dated), "parse", json.dumps(rec["parse"])[:300], flush=True)
    br.close()
tag = sys.argv[2] if len(sys.argv) > 2 else "all"
json.dump(out, open(f".probe/pf_probe_{tag}.json", "w"), indent=1)
