"""Temporary: record data API calls on fund-house portfolio pages (headed browser under xvfb)."""
import json, re
from playwright.sync_api import sync_playwright

PAGES = {
  "hdfc": ("https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio", [r"monthly portfolio", r"2026"]),
  "kotak": ("https://www.kotakmf.com/Information/portfolios", [r"monthly", r"sep"]),
  "axis": ("https://www.axismf.com/statutory-disclosures", [r"^\s*8\.\s*portfolios", r"monthly portfolio(?!\s*overlap)"]),
  "bandhan": ("https://bandhanmutual.com/downloads/disclosures", [r"portfolio", r"monthly"]),
  "uti": ("https://www.utimf.com/downloads/consolidate-all-portfolio-disclosure", [r"get portfolio"]),
  "edelweiss": ("https://www.edelweissmf.com/statutory-disclosures/portfolio-disclosure", [r"monthly"]),
  "mirae": ("https://www.miraeassetmf.co.in/downloads/portfolio", [r"show more", r"show more", r"show more"]),
  "barodabnp": ("https://www.barodabnpparibasmf.in/downloads/monthly-portfolio", [r"hosted on", r"click here"]),
  "hsbc": ("https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library", [r"portfolio"]),
  "motilal": ("https://www.motilaloswalmf.com/download/scheme-portfolio", [r"monthly", r"portfolio"]),
  "franklin": ("https://www.franklintempletonindia.com/downloads/fund-documents/monthly-portfolio", [r"september\s*2026|sep\w*\s*2026"]),
}
FILE = re.compile(r"""https?://[^\s"'<>\\]+?\.(?:xlsx|xls|zip|xlsm)(?:\?[^\s"'<>\\]*)?""", re.I)
out = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
                        locale="en-IN", viewport={"width": 1366, "height": 900}, accept_downloads=True)
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    for k, (u, clicks) in PAGES.items():
        rec = {"xhr": [], "files": set(), "downloads": [], "texts": [], "bodies": []}
        p = ctx.new_page()
        def on_resp(r, rec=rec):
            try:
                rt = r.request.resource_type
                if FILE.search(r.url): rec["files"].add(r.url)
                if rt in ("xhr", "fetch"):
                    ct = r.headers.get("content-type", "")
                    rec["xhr"].append(f"{r.request.method} {r.status} {ct[:30]} {r.url[:220]}")
                    if "json" in ct or "text" in ct:
                        t = r.text()
                        rec["files"].update(FILE.findall(t)[:300])
                        if re.search(r"portfolio|\.xlsx?|\.zip", t, re.I) and len(rec["bodies"]) < 6:
                            rec["bodies"].append({"url": r.url[:250], "post": (r.request.post_data or "")[:400], "body": t[:1500]})
            except Exception:
                pass
        p.on("response", on_resp)
        p.on("download", lambda d, rec=rec: rec["downloads"].append({"url": d.url, "name": d.suggested_filename}))
        try:
            resp = p.goto(u, wait_until="domcontentloaded", timeout=90000)
            rec["status"] = resp.status if resp else None
            p.wait_for_timeout(10000)
            for _ in range(3):
                p.mouse.wheel(0, 2000); p.wait_for_timeout(600)
            for rx in clicks:
                try:
                    el = p.get_by_text(re.compile(rx, re.I)).first
                    el.click(force=True, timeout=5000)
                    p.wait_for_timeout(5000)
                    rec.setdefault("clicked", []).append(rx)
                except Exception as e:
                    rec.setdefault("clickErr", []).append(rx + ": " + str(e)[:80])
            body = p.inner_text("body")
            rec["texts"] = [l.strip()[:120] for l in body.splitlines() if re.search(r"portfolio|sep\w*\s*,?\s*2026|30.?09.?2026", l, re.I)][:50]
            rec["files"].update(FILE.findall(p.content()))
            rec["anchors"] = [a for a in p.eval_on_selector_all("a", "as=>as.map(a=>a.href+' | '+(a.innerText||'').trim().slice(0,60))") if re.search(r"\.xls|\.zip|portfolio", a, re.I)][:40]
            rec["final"] = p.url; rec["title"] = p.title()[:80]
        except Exception as e:
            rec["err"] = str(e)[:200]
        p.close()
        for pg in ctx.pages:
            try: pg.close()
            except Exception: pass
        rec["files"] = sorted(rec["files"])[:80]
        rec["xhr"] = rec["xhr"][:60]
        out[k] = rec
        print(k, rec.get("status"), rec.get("err", ""), "xhr", len(rec["xhr"]), "files", len(rec["files"]), "dl", len(rec["downloads"]), flush=True)
    b.close()
json.dump(out, open(".probe/holdings_probe2.json", "w"), indent=1)
