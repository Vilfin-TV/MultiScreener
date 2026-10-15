"""Temporary: discover monthly-portfolio files that are served on click (downloads / popups)."""
import json, re
from playwright.sync_api import sync_playwright

PAGES = {
  "icici": ("https://www.icicipruamc.com/media-center/downloads?currentTabFilter=OtherSchemeDisclosures&&subCatTabFilter=Monthly%20Portfolio%20Disclosures", r"monthly portfolio disclosure\s+september\s+2026"),
  "groww": ("https://www.growwmf.in/statutory-disclosure/portfolio", r"monthly portfolio.{0,4}sep\w*\s*30,?\s*2026"),
  "quant": ("https://quantmutual.com/statutory-disclosures", r"monthly portfolio\s*-\s*fund\s*-\s*wise"),
  "canara": ("https://www.canararobeco.com/documents/statutory-disclosures/scheme-monthly-portfolio/", r"sep\w*\s*-?\s*2026|30\.?0?9\.?2026"),
  "barodabnp": ("https://www.barodabnpparibasmf.in/downloads/monthly-portfolio", r"sep\w*\s*-?\s*2026|30\.?0?9\.?2026"),
  "kotak": ("https://www.kotakmf.com/Information/portfolios", r"sep\w*\s*-?\s*2026|portfolios?"),
  "bandhan": ("https://bandhanmutual.com/downloads/disclosures", r"monthly portfolio|portfolio summary"),
  "uti": ("https://www.utimf.com/downloads/consolidate-all-portfolio-disclosure", r"sep\w*\s*-?\s*2026|monthly"),
  "mirae": ("https://www.miraeassetmf.co.in/downloads/portfolio", r"show more"),
  "invesco_debt": ("https://www.invescomutualfund.com/literature-forms/monthly-holdings/debt", r"$^"),
  "invesco_hybrid": ("https://www.invescomutualfund.com/literature-forms/monthly-holdings/hybrid", r"$^"),
  "axis": ("https://www.axismf.com/statutory-disclosures", r"monthly portfolio(?! overlap)"),
  "motilal": ("https://www.motilaloswalmf.com/downloads/mutual-fund/portfolio", r"sep\w*\s*-?\s*2026"),
  "sundaram": ("https://www.sundarammutual.com/downloads/portfolio", r"sep\w*\s*-?\s*2026"),
}
FILE = re.compile(r"""https?://[^\s"'<>\\]+?\.(?:xlsx|xls|zip|xlsm)(?:\?[^\s"'<>\\]*)?""", re.I)
out = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                        locale="en-IN", viewport={"width": 1366, "height": 900}, accept_downloads=True)
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    for k, (u, rx) in PAGES.items():
        rec = {"downloads": [], "popups": [], "files": set(), "texts": [], "api": []}
        p = ctx.new_page()
        def on_resp(r, rec=rec):
            try:
                if FILE.search(r.url): rec["files"].add(r.url)
                ct = r.headers.get("content-type", "")
                if "json" in ct:
                    t = r.text()
                    h = FILE.findall(t)
                    if h or re.search(r"portfolio", t, re.I):
                        rec["api"].append({"url": r.url[:250], "n": len(t), "sample": t[:600]})
                        rec["files"].update(h[:300])
            except Exception:
                pass
        p.on("response", on_resp)
        p.on("download", lambda d, rec=rec: rec["downloads"].append({"url": d.url, "name": d.suggested_filename}))
        ctx.on("page", lambda np, rec=rec: rec["popups"].append(np.url))
        try:
            resp = p.goto(u, wait_until="domcontentloaded", timeout=90000)
            rec["status"] = resp.status if resp else None
            p.wait_for_timeout(9000)
            for _ in range(3):
                p.mouse.wheel(0, 2000); p.wait_for_timeout(600)
            # visible texts that look like portfolio entries
            txt = p.inner_text("body")
            rec["texts"] = [l.strip()[:120] for l in txt.splitlines() if re.search(r"portfolio", l, re.I)][:60]
            els = p.get_by_text(re.compile(rx, re.I)).all()[:4]
            for el in els:
                try:
                    el.scroll_into_view_if_needed(timeout=2000)
                    el.click(timeout=4000)
                    p.wait_for_timeout(5000)
                except Exception as e:
                    rec.setdefault("clickErr", []).append(str(e)[:100])
            rec["files"].update(FILE.findall(p.content()))
            rec["anchors"] = [a for a in p.eval_on_selector_all("a", "as=>as.map(a=>a.href+' | '+(a.innerText||'').trim().slice(0,60))") if re.search(r"portfolio|\.xls|\.zip", a, re.I)][:60]
            rec["final"] = p.url
        except Exception as e:
            rec["err"] = str(e)[:200]
        for pg in ctx.pages:
            if pg != p:
                try: pg.close()
                except Exception: pass
        p.close()
        rec["files"] = sorted(rec["files"])[:80]
        rec["api"] = rec["api"][:6]
        out[k] = rec
        print(k, rec.get("status"), rec.get("err", ""), "dl", len(rec["downloads"]), "pop", len(rec["popups"]), "files", len(rec["files"]), flush=True)
    b.close()
json.dump(out, open(".probe/holdings_probe2.json", "w"), indent=1)
