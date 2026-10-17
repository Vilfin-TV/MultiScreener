"""Temporary: open fund pages of fund houses without monthly files, capture the data behind their Portfolio tab."""
import json, re, sys, time
from playwright.sync_api import sync_playwright

pages = json.load(open("data/mf/scheme_pages.json"))
scr = json.load(open("data/mf/screener.json")); C = {c: i for i, c in enumerate(scr["cols"])}
amc_of = {str(r[C["code"]]): scr["amcs"][r[C["amc"]]] for r in scr["rows"]}
sub_of = {str(r[C["code"]]): r[C["sub"]] for r in scr["rows"]}
WANT = ["Axis", "Kotak Mahindra", "UTI", "Bandhan", "Motilal Oswal", "Edelweiss", "Franklin Templeton", "quant", "HSBC",
        "Baroda BNP Paribas", "Canara Robeco", "Sundaram", "Mahindra Manulife", "Bank of India", "LIC", "PGIM India",
        "ITI", "Jio BlackRock", "Quantum", "Zerodha", "Union", "WhiteOak Capital", "Bajaj Finserv", "Navi", "NJ", "Taurus",
        "Trust", "Unifi", "Choice", "The Wealth Company", "Angel One", "Lakshya"]
if len(sys.argv) > 1: WANT = sys.argv[1].split(",")
ISIN = re.compile(r"IN[EF][A-Z0-9]{9}")
out = {}
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False)
    ctx = br.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36", viewport={"width": 1366, "height": 900})
    ctx.set_default_timeout(30000)
    for amc in WANT:
        codes = [c for c, a in amc_of.items() if a == amc and isinstance(pages.get(c), str)]
        # prefer equity funds
        codes.sort(key=lambda c: (not re.search(r"flexi|multi|large|mid|small|elss|focus|value", sub_of[c]), c))
        rec = {"tried": [], "hits": []}
        for code in codes[:2]:
            url = pages[code]; got = []
            def on_resp(r, got=got):
                try:
                    ct = r.headers.get("content-type", "")
                    if r.request.resource_type in ("image", "stylesheet", "font", "media"): return
                    if not ("json" in ct or "javascript" not in ct and "html" not in ct): return
                    b = r.text()
                    n = len(ISIN.findall(b)); w = len(re.findall(r"(?i)holding|weight|percent|netasset|net_asset|allocation|corpus", b))
                    if n >= 5 or (w >= 10 and "json" in ct):
                        got.append({"url": r.url[:300], "method": r.request.method, "post": (r.request.post_data or "")[:400], "ct": ct[:40], "isins": n, "len": len(b), "sample": b[:1500]})
                except Exception:
                    pass
            p = ctx.new_page(); p.on("response", on_resp)
            t0 = time.time(); err = None
            try:
                p.goto(url, wait_until="domcontentloaded", timeout=60000)
                try: p.wait_for_load_state("networkidle", timeout=15000)
                except Exception: pass
                for sel in ["text=/^\\s*Portfolio\\s*$/i", "text=/Portfolio/i", "text=/Holdings/i"]:
                    try:
                        el = p.locator(sel).first
                        if el.count(): el.click(timeout=4000); p.wait_for_timeout(3000); break
                    except Exception: pass
                p.mouse.wheel(0, 3000); p.wait_for_timeout(2500)
                html = p.content(); hn = len(ISIN.findall(html))
                txt = p.inner_text("body")[:200000]
                pct_rows = len(re.findall(r"\n[^\n]{3,80}\n\s*\d{1,2}\.\d{1,2}\s*%", txt))
            except Exception as e:
                err = str(e)[:150]; hn = pct_rows = None
            p.close()
            rec["tried"].append({"code": code, "url": url, "err": err, "htmlIsins": hn, "pctRows": pct_rows, "secs": round(time.time() - t0), "nresp": len(got)})
            rec["hits"] += got[:6]
        out[amc] = rec
        print(amc, [(t["code"], t["htmlIsins"], t["pctRows"], t["nresp"], t["err"]) for t in rec["tried"]], flush=True)
    br.close()
json.dump(out, open(".probe/fp_probe.json", "w"), indent=1)
