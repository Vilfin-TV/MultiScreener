"""Temporary v2: interact with disclosure pages (tabs, buttons, selects), capture downloads and data responses."""
import io, json, re, sys, time
sys.path.insert(0, "scripts")
import build_mf_holdings as H
from playwright.sync_api import sync_playwright

PAGES = {
    "Axis": ["https://www.axismf.com/statutory-disclosures"],
    "Bandhan": ["https://bandhanmutual.com/downloads/disclosures"],
    "UTI": ["https://www.utimf.com/downloads/consolidate-all-portfolio-disclosure"],
    "LIC": ["https://www.licmf.com/downloads/monthly-portfolio"],
    "WhiteOak Capital": ["https://mf.whiteoakamc.com/regulatory-disclosures/scheme-portfolios"],
    "Navi": ["https://navi.com/mutual-fund/downloads"],
    "NJ": ["https://www.njmutualfund.com/statutory-disclosures"],
    "Taurus": ["https://taurusmutualfund.com/monthly-portfolio"],
    "Angel One": ["https://www.angelonemf.com/statutory-disclosures"],
    "Zerodha": ["https://www.zerodhafundhouse.com/resources/disclosures"],
    "Jio BlackRock": ["https://www.jioblackrockamc.com/"],
    "Franklin Templeton": ["https://www.franklintempletonindia.com/downloads/fund-documents"],
    "Edelweiss": ["https://www.edelweissmf.com/statutory/portfolio-of-schemes"],
    "Kotak Mahindra": ["https://www.kotakmf.com/Information/portfolios"],
    "HSBC": ["https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library"],
    "Union": ["https://www.unionmf.com/downloads"],
    "Sundaram": ["https://www.sundarammutual.com/Downloads"],
    "Canara Robeco": ["https://www.canararobeco.com/statutory-disclosures"],
    "quant": ["https://www.quantmutual.com/statutory-disclosures"],
    "Mahindra Manulife": ["https://www.mahindramanulife.com/downloads"],
    "Bank of India": ["https://www.boimf.in/investor-corner"],
    "Bajaj Finserv": ["https://www.bajajamc.com/downloads"],
    "ITI": ["https://www.itiamc.com/downloads"],
}
amc, tag = sys.argv[1], sys.argv[2]
FILE = re.compile(r"""(?:https?://[^\s"'<>\\]+?|/[^\s"'<>\\]+?)\.(?:pdf|xlsx?|zip)(?:\?[^\s"'<>\\]*)?""", re.I)
CLICK = re.compile(r"monthly\s*portfolio|portfolio\s*disclosure|scheme\s*portfolio|month[- ]?end|^portfolio", re.I)
rec = {"pages": [], "files": [], "downloads": [], "xhr": [], "clicked": [], "text": ""}
t0 = time.time()
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False)
    ctx = br.new_context(user_agent=H.UA, accept_downloads=True, viewport={"width": 1366, "height": 900})
    ctx.set_default_timeout(15000)
    for url in PAGES.get(amc, []):
        p = ctx.new_page()

        def on_resp(r):
            try:
                u = r.url
                if FILE.search(u): rec["files"].append(u)
                ct = r.headers.get("content-type", "")
                if ("json" in ct or "javascript" not in ct and "text" in ct) and r.request.resource_type in ("xhr", "fetch"):
                    body = r.text().replace("\\/", "/")
                    fs = FILE.findall(body)
                    rec["xhr"].append([u[:200], len(body), fs[:5]])
                    rec["files"].extend(f for f in fs)
            except Exception:
                pass
        p.on("response", on_resp)
        p.on("download", lambda d: rec["downloads"].append([d.url, d.suggested_filename]))
        try:
            p.goto(url, wait_until="domcontentloaded", timeout=45000)
            try: p.wait_for_load_state("networkidle", timeout=12000)
            except Exception: pass
            rec["pages"].append(p.url)
            rec["text"] = (p.inner_text("body") or "")[:4000]
            rec["selects"] = p.eval_on_selector_all("select", "ss => ss.map(s => [s.name||s.id, [...s.options].slice(0,15).map(o => o.text.trim())])")
            # click tabs / buttons whose text mentions monthly portfolio
            els = p.query_selector_all("a, button, li, span, div[role=tab], [role=button]")
            n = 0
            for el in els:
                if time.time() - t0 > 200 or n >= 12: break
                try:
                    t = (el.inner_text() or "").strip()
                except Exception:
                    continue
                if not t or len(t) > 60 or not CLICK.search(t): continue
                try:
                    el.scroll_into_view_if_needed(timeout=3000); el.click(timeout=4000); n += 1
                    rec["clicked"].append(t); p.wait_for_timeout(2500)
                except Exception:
                    continue
            # links now present on the page
            hrefs = p.eval_on_selector_all("a", "as => as.map(a => a.href)")
            rec["files"].extend(h for h in hrefs if FILE.search(h))
            rec["files"].extend(m for m in FILE.findall(p.content()) if m.startswith("http"))
            # click the first few 'download' controls to catch click-triggered files
            dl = [e for e in p.query_selector_all("a, button") if re.search(r"download", (e.inner_text() or "") + (e.get_attribute("title") or ""), re.I)][:4]
            for e in dl:
                try:
                    with p.expect_download(timeout=8000) as d:
                        e.click(timeout=4000)
                    rec["downloads"].append([d.value.url, d.value.suggested_filename])
                except Exception:
                    pass
            rec["textAfter"] = (p.inner_text("body") or "")[:3000]
        except Exception as e:
            rec["pages"].append([url, "ERR " + str(e)[:120]])
        p.close()
    br.close()
rec["files"] = list(dict.fromkeys(rec["files"]))[:120]
rec["months"] = sorted({H.link_month(f) for f in rec["files"] if H.link_month(f)}, reverse=True)[:5]
rec["secs"] = round(time.time() - t0)
json.dump(rec, open(f".probe/v2_{tag}.json", "w"), indent=1, default=str)
print(amc, "files", len(rec["files"]), "months", rec["months"], "downloads", rec["downloads"][:3], "clicked", rec["clicked"][:6], flush=True)
