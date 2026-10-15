"""Temporary: deep discovery of monthly-portfolio files on fund-house sites (network capture + tab clicks)."""
import json, re, sys
from playwright.sync_api import sync_playwright

PAGES = {
  "icici": "https://www.icicipruamc.com/media-center/downloads?currentTabFilter=OtherSchemeDisclosures&&subCatTabFilter=Monthly%20Portfolio%20Disclosures",
  "hdfc": "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio",
  "kotak": "https://www.kotakmf.com/Information/portfolios",
  "axis": "https://www.axismf.com/statutory-disclosures",
  "uti": "https://www.utimf.com/downloads/consolidate-all-portfolio-disclosure",
  "bandhan": "https://bandhanmutual.com/downloads/disclosures",
  "edelweiss": "https://www.edelweissmf.com/statutory-disclosures/portfolio-disclosure",
  "mirae": "https://www.miraeassetmf.co.in/downloads/portfolio",
  "invesco": "https://www.invescomutualfund.com/literature-forms/monthly-holdings/equity",
  "barodabnp": "https://www.barodabnpparibasmf.in/downloads/monthly-portfolio",
  "hsbc": "https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library",
  "motilal": "https://www.motilaloswalmf.com/download/scheme-portfolio",
  "franklin": "https://www.franklintempletonindia.com/downloads/fund-documents/monthly-portfolio",
  "groww": "https://www.growwmf.in/statutory-disclosure/portfolio",
  "lic": "https://www.licmf.com/downloads/monthly-portfolio",
  "sundaram": "https://www.sundarammutual.com/Monthly-Portfolio",
  "union": "https://www.unionmf.com/about-us/downloads/portfolio",
  "quant": "https://quantmutual.com/statutory-disclosures",
  "canara": "https://www.canararobeco.com/documents/statutory-disclosures/scheme-monthly-portfolio/",
  "mahindra": "https://www.mahindramanulife.com/downloads#monthly-portfolio",
  "pgim": "https://www.pgimindiamf.com/statutory-disclosure/portfolio-disclosure",
}
FILE = re.compile(r"""https?://[^\s"'<>\\]+?\.(?:xlsx|xls|zip|xlsm)(?:\?[^\s"'<>\\]*)?""", re.I)
REL = re.compile(r"""["']([^"'<>\s]+?\.(?:xlsx|xls|zip))["']""", re.I)
out = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                        locale="en-IN", viewport={"width": 1366, "height": 900})
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    for k, u in PAGES.items():
        if len(sys.argv) > 1 and k not in sys.argv[1:]:
            continue
        rec = {"files": set(), "api": [], "clicks": []}
        p = ctx.new_page()
        def on_resp(r, rec=rec):
            try:
                url = r.url
                if FILE.search(url):
                    rec["files"].add(url)
                ct = r.headers.get("content-type", "")
                if "json" in ct or "text/plain" in ct:
                    t = r.text()
                    hits = FILE.findall(t) + [m for m in REL.findall(t) if re.search(r"portfolio|monthly", m, re.I)]
                    if hits:
                        rec["api"].append(url[:200])
                        rec["files"].update(hits[:400])
            except Exception:
                pass
        p.on("response", on_resp)
        try:
            resp = p.goto(u, wait_until="domcontentloaded", timeout=90000)
            rec["status"] = resp.status if resp else None
            p.wait_for_timeout(9000)
            for _ in range(4):
                p.mouse.wheel(0, 2500); p.wait_for_timeout(700)
            for pat in [r"monthly\s*portfolio", r"^portfolio", r"portfolio\s*disclosure", r"load\s*more|view\s*more|show\s*more"]:
                try:
                    els = p.get_by_text(re.compile(pat, re.I)).all()[:3]
                    for el in els:
                        try:
                            txt = el.inner_text(timeout=1500)[:60]
                            el.click(timeout=3000); p.wait_for_timeout(3000)
                            rec["clicks"].append(txt)
                        except Exception:
                            pass
                except Exception:
                    pass
            html = p.content()
            rec["files"].update(FILE.findall(html))
            rec["files"].update(m for m in REL.findall(html) if re.search(r"portfolio|monthly", m, re.I))
            rec["anchors"] = [a for a in p.eval_on_selector_all("a", "as=>as.map(a=>a.href)") if FILE.search(a)][:50]
            rec["final"] = p.url
            rec["html"] = len(html)
            rec["title"] = p.title()[:80]
        except Exception as e:
            rec["err"] = str(e)[:200]
        p.close()
        rec["files"] = sorted(rec["files"])
        rec["recent"] = [f for f in rec["files"] if re.search(r"2026", f) and re.search(r"sep|0926|092026|30-?09|aug", f, re.I)][:40]
        rec["files"] = rec["files"][:80]
        out[k] = rec
        print(k, rec.get("status"), rec.get("err", ""), len(rec["files"]), "files", len(rec["recent"]), "recent", rec["clicks"], flush=True)
    b.close()
json.dump(out, open(".probe/holdings_probe2.json", "w"), indent=1)
