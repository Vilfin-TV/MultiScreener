"""Temporary: find NFO listings and 'open for investment' flags for international funds."""
import json, re, requests
from playwright.sync_api import sync_playwright
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
out = {"facts": {}, "pages": {}}
S = requests.Session(); S.headers["User-Agent"] = UA
# fund facts for two international FoFs + one domestic fund (purchase flags?)
for isin in ["INF247L01AL5", "INF109K01Z14", "INF200K01T28"]:
    for name, url in [("kv", f"https://api.kuvera.in/mf/api/v5/fund_schemes/{isin}.json"), ("mirror", f"https://mf.captnemo.in/kuvera/{isin}")]:
        try:
            r = S.get(url, timeout=60); j = r.json(); j = j[0] if isinstance(j, list) and j else j
            out["facts"][f"{name}:{isin}"] = {"status": r.status_code, "keys": sorted(j.keys()) if isinstance(j, dict) else str(j)[:200],
                                              "flags": {k: v for k, v in (j.items() if isinstance(j, dict) else []) if re.search(r"avail|allow|open|purchase|sip|lump|status|active|suspend", k, re.I)}}
        except Exception as e:
            out["facts"][f"{name}:{isin}"] = str(e)[:150]
pages = {"amfi_nfo": "https://www.amfiindia.com/nfo", "amfi_nfo2": "https://www.amfiindia.com/research-information/other-data/nfo-details",
         "amfi_home": "https://www.amfiindia.com/", "sebi_nfo": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doMutualFund=yes&mftype=3"}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, locale="en-IN")
    for k, u in pages.items():
        rec = {"xhr": [], "bodies": []}
        p = ctx.new_page()
        def on_resp(r, rec=rec):
            try:
                if r.request.resource_type in ("xhr", "fetch"):
                    rec["xhr"].append(f"{r.status} {r.url[:200]}")
                    t = r.text()
                    if re.search(r"nfo|new fund offer|open date|close date", t, re.I) and len(rec["bodies"]) < 4:
                        rec["bodies"].append({"url": r.url[:200], "body": t[:1500]})
            except Exception:
                pass
        p.on("response", on_resp)
        try:
            resp = p.goto(u, wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(9000)
            rec["status"] = resp.status if resp else None; rec["final"] = p.url
            txt = p.inner_text("body"); i = txt.lower().find("nfo")
            rec["text"] = txt[max(0, i - 200): i + 1500] if i >= 0 else txt[:600]
            rec["links"] = [a for a in p.eval_on_selector_all("a", "as=>as.map(a=>a.href+' | '+(a.innerText||'').trim().slice(0,50))") if re.search(r"nfo|new fund", a, re.I)][:20]
        except Exception as e:
            rec["err"] = str(e)[:150]
        p.close(); rec["xhr"] = rec["xhr"][:40]
        out["pages"][k] = rec
    b.close()
json.dump(out, open(".probe/nfo_probe.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out["facts"], indent=1)[:4000])
