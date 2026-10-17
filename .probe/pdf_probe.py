"""Temporary: find monthly portfolio PDFs on fund-house sites and test-read the newest with a PDF table reader."""
import io, json, re, sys, time
from urllib.parse import urlparse
sys.path.insert(0, "scripts")
import build_mf_holdings as H
import pdfplumber
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
amc, tag = sys.argv[1], sys.argv[2]
PDF_RX = re.compile(r"""(?:https?://[^\s"'<>\\]+?|/[^\s"'<>\\]+?)\.pdf(?:\?[^\s"'<>\\]*)?""", re.I)
KEY = re.compile(r"portfolio|disclosure|statutory|download|holding", re.I)
BAD = re.compile(r"\.(jpg|png|svg|mp4)(\?|$)|facebook|twitter|linkedin|youtube|instagram|whatsapp|mailto:|tel:|javascript:", re.I)


def pdf_rows(blob, max_pages=400):
    rows = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for i, pg in enumerate(pdf.pages[:max_pages]):
            got = False
            for t in pg.extract_tables() or []:
                for r in t:
                    if r and any(c for c in r):
                        rows.append([(c or "").replace("\n", " ").strip() for c in r]); got = True
            if not got:
                for line in (pg.extract_text(layout=True) or "").splitlines():
                    cells = [c.strip() for c in re.split(r"\s{2,}", line.strip()) if c.strip()]
                    if cells: rows.append(cells)
    return rows


site = sites.get(amc, "")
host = urlparse(site).netloc.replace("www.", "") if site else ""
rec = {"site": site, "visited": [], "pdfs": [], "parse": []}
t0 = time.time()
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False)
    ctx = br.new_context(user_agent=H.UA, accept_downloads=True)
    ctx.set_default_timeout(30000)
    queue = list(dict.fromkeys(GUESS.get(amc, []) + ([site] if site else [])))
    seen = set()
    while queue and len(rec["visited"]) < 10 and time.time() - t0 < 170:
        url = queue.pop(0)
        if url in seen: continue
        seen.add(url)
        try:
            p = ctx.new_page(); p.goto(url, wait_until="domcontentloaded", timeout=40000)
            try: p.wait_for_load_state("networkidle", timeout=10000)
            except Exception: pass
            for _ in range(3):
                p.mouse.wheel(0, 2500); p.wait_for_timeout(400)
            links = p.eval_on_selector_all("a", "as => as.map(a => [a.href, (a.innerText||a.title||'').trim().slice(0,100)])")
            html = p.content(); final = p.url; p.close()
        except Exception as e:
            rec["visited"].append([url, "ERR " + str(e)[:80]]); continue
        pdfs = [(h, t) for h, t in links if PDF_RX.search(h)] + [(m, "") for m in PDF_RX.findall(html) if m.startswith("http")]
        n = 0
        for h, t in pdfs:
            if re.search(r"portfolio|holding", h + " " + t, re.I) and not re.search(r"fortnight|half|annual|overlap|riskometer|factsheet", h + " " + t, re.I):
                rec["pdfs"].append([h, t, H.link_month(h + " " + t), final]); n += 1
        rec["visited"].append([final, n])
        for href, txt in links:
            if not href.startswith("http") or BAD.search(href) or PDF_RX.search(href) or (host and host not in href): continue
            s = (3 if re.search(r"portfolio", href + txt, re.I) else 0) + (2 if re.search(r"month", href + txt, re.I) else 0) + (1 if KEY.search(href + txt) else 0)
            if s >= 2 and href not in seen and href not in queue: queue.append(href)
    uniq = list({x[0]: x for x in rec["pdfs"]}.values())
    rec["pdfs"] = uniq[:80]
    dated = sorted([x for x in uniq if x[2]], key=lambda x: tuple(x[2]), reverse=True)
    latest = tuple(dated[0][2]) if dated else None
    rec["latest"] = latest; rec["latestCount"] = sum(1 for x in dated if tuple(x[2]) == latest)
    for x in (dated or uniq)[:2]:
        res = {"url": x[0]}
        try:
            r = ctx.request.get(x[0], headers={"Referer": x[3]}, timeout=90000)
            blob = r.body() if r.ok else b""
            res.update(status=r.status, bytes=len(blob), pdf=blob[:4] == b"%PDF")
            if blob[:4] == b"%PDF":
                rows = pdf_rows(blob)
                blocks = H.parse_sheet("pdf", rows)
                res.update(rows=len(rows), blocks=len(blocks), holdings=sum(len(b["holdings"]) for b in blocks),
                           titles=[b["title"][:70] for b in blocks[:6]], sums=[round(sum(h["pct"] for h in b["holdings"]), 1) for b in blocks[:6]],
                           isinRows=sum(1 for rw in rows if any(H.ISIN.match(c.upper()) for c in rw)), sample=[rw for rw in rows if any(H.ISIN.match(c.upper()) for c in rw)][:3])
        except Exception as e:
            res["err"] = str(e)[:160]
        rec["parse"].append(res)
    br.close()
rec["secs"] = round(time.time() - t0)
json.dump(rec, open(f".probe/pdf_{tag}.json", "w"), indent=1)
print(amc, "pdfs", len(uniq), "latest", latest, json.dumps(rec["parse"])[:400], flush=True)
