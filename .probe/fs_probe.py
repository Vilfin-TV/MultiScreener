"""Temporary: find each fund house's latest monthly factsheet PDF, download it and save text samples."""
import io, json, re, sys, time
sys.path.insert(0, "scripts")
import build_mf_holdings as H
import pdfplumber
from playwright.sync_api import sync_playwright

PAGES = {
    "Kotak Mahindra": ["https://www.kotakmf.com/Information/factsheets", "https://www.kotakmf.com/Information/forms-and-downloads"],
    "Axis": ["https://www.axismf.com/factsheets", "https://www.axismf.com/downloads"],
    "Bandhan": ["https://bandhanmutual.com/downloads/factsheets", "https://bandhanmutual.com/downloads"],
    "UTI": ["https://www.utimf.com/downloads/factsheets", "https://www.utimf.com/downloads"],
    "Edelweiss": ["https://www.edelweissmf.com/downloads/factsheets", "https://www.edelweissmf.com/downloads"],
    "Franklin Templeton": ["https://www.franklintempletonindia.com/downloads/fund-documents/factsheets", "https://www.franklintempletonindia.com/downloads/fund-documents"],
    "LIC": ["https://www.licmf.com/downloads/factsheet", "https://www.licmf.com/downloads"],
    "Sundaram": ["https://www.sundarammutual.com/Factsheet", "https://www.sundarammutual.com/Downloads"],
    "Union": ["https://www.unionmf.com/downloads/factsheets", "https://www.unionmf.com/downloads"],
    "quant": ["https://www.quantmutual.com/factsheet", "https://www.quantmutual.com/downloads"],
    "Canara Robeco": ["https://www.canararobeco.com/forms-downloads/factsheets", "https://www.canararobeco.com/downloads"],
    "Mahindra Manulife": ["https://www.mahindramanulife.com/downloads/factsheet", "https://www.mahindramanulife.com/downloads"],
    "Bajaj Finserv": ["https://www.bajajamc.com/downloads/factsheet", "https://www.bajajamc.com/downloads"],
    "ITI": ["https://www.itiamc.com/downloads/factsheet", "https://www.itiamc.com/downloads"],
    "WhiteOak Capital": ["https://mf.whiteoakamc.com/downloads/factsheet", "https://mf.whiteoakamc.com/downloads"],
    "Navi": ["https://navi.com/mutual-fund/downloads/factsheet", "https://navi.com/mutual-fund/downloads"],
    "Zerodha": ["https://www.zerodhafundhouse.com/resources/factsheets/", "https://www.zerodhafundhouse.com/resources/"],
    "Jio BlackRock": ["https://www.jioblackrockamc.com/downloads", "https://www.jioblackrockamc.com/"],
    "NJ": ["https://www.njmutualfund.com/factsheet", "https://www.njmutualfund.com/downloads"],
    "HSBC": ["https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library#factsheets"],
}
amc, tag = sys.argv[1], sys.argv[2]
PDF = re.compile(r"""(?:https?://[^\s"'<>\\]+?|/[^\s"'<>\\]+?)\.pdf(?:\?[^\s"'<>\\]*)?""", re.I)
rec = {"pages": [], "cands": [], "pick": None}
t0 = time.time()
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False)
    ctx = br.new_context(user_agent=H.UA, accept_downloads=True, viewport={"width": 1366, "height": 900})
    ctx.set_default_timeout(15000)
    found = []
    for url in PAGES.get(amc, []):
        p = ctx.new_page()
        p.on("response", lambda r: found.append([r.url, "", url]) if PDF.search(r.url) else None)
        try:
            p.goto(url, wait_until="domcontentloaded", timeout=45000)
            try: p.wait_for_load_state("networkidle", timeout=12000)
            except Exception: pass
            for el in p.query_selector_all("a, button, li, [role=tab]")[:400]:
                try: t = (el.inner_text() or "").strip()
                except Exception: continue
                if t and len(t) < 40 and re.search(r"fact\s*sheet", t, re.I):
                    try: el.click(timeout=3000); p.wait_for_timeout(2000)
                    except Exception: pass
                    break
            links = p.eval_on_selector_all("a", "as => as.map(a => [a.href, (a.innerText||a.title||'').trim().slice(0,100)])")
            found += [[h, t, p.url] for h, t in links if PDF.search(h)]
            found += [[m, "", p.url] for m in PDF.findall(p.content()) if m.startswith("http")]
            rec["pages"].append([p.url, len(links)])
        except Exception as e:
            rec["pages"].append([url, "ERR " + str(e)[:100]])
        p.close()
    cands = [x for x in {f[0]: f for f in found}.values() if re.search(r"fact.?sheet", x[0] + " " + x[1], re.I)
             and not re.search(r"debt|passive|etf|index|addend|kim|sid|key", x[0], re.I)]
    for x in cands: x.append(H.link_month(x[0] + " " + x[1]))
    rec["cands"] = [[c[0][-160:], c[1][:60], c[3]] for c in cands][:40]
    dated = sorted([c for c in cands if c[3]], key=lambda c: tuple(c[3]), reverse=True)
    pick = (dated or cands or [None])[0]
    if pick:
        rec["pick"] = pick[0]
        try:
            r = ctx.request.get(pick[0], headers={"Referer": pick[2]}, timeout=120000)
            blob = r.body() if r.ok else b""
            rec["status"], rec["bytes"] = r.status, len(blob)
            if blob[:4] == b"%PDF":
                with pdfplumber.open(io.BytesIO(blob)) as pdf:
                    rec["nPages"] = len(pdf.pages)
                    samples = []
                    for i, pg in enumerate(pdf.pages[:80]):
                        txt = pg.extract_text() or ""
                        if re.search(r"portfolio|holdings", txt, re.I) and re.search(r"\d+\.\d{2}\s*%?", txt):
                            samples.append([i, txt[:2500]])
                        if len(samples) >= 3: break
                    rec["samples"] = samples
        except Exception as e:
            rec["err"] = str(e)[:160]
    br.close()
rec["secs"] = round(time.time() - t0)
json.dump(rec, open(f".probe/fs_{tag}.json", "w"), indent=1)
print(amc, "cands", len(rec["cands"]), "pick", (rec["pick"] or "")[-100:], "pages", rec.get("nPages"), "samples", len(rec.get("samples") or []), flush=True)
