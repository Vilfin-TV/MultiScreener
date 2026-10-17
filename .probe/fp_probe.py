"""Temporary (v2): open fund pages, open Portfolio tab + expand lists, save holdings-like API bodies and DOM (name, %) rows."""
import json, re, sys, time, os
from playwright.sync_api import sync_playwright

pages = json.load(open("data/mf/scheme_pages.json"))
scr = json.load(open("data/mf/screener.json")); C = {c: i for i, c in enumerate(scr["cols"])}
amc_of = {str(r[C["code"]]): scr["amcs"][r[C["amc"]]] for r in scr["rows"]}
sub_of = {str(r[C["code"]]): r[C["sub"]] for r in scr["rows"]}
name_of = {str(r[C["code"]]): r[C["name"]] for r in scr["rows"]}
WANT = ["Axis", "Kotak Mahindra", "UTI", "Bandhan", "Motilal Oswal", "Franklin Templeton", "PGIM India", "Trust", "Sundaram",
        "Mahindra Manulife", "ITI", "Baroda BNP Paribas", "Zerodha", "Edelweiss", "quant", "HSBC", "Canara Robeco", "LIC",
        "Bank of India", "Jio BlackRock", "Quantum", "Unifi", "Choice", "Lakshya", "NJ", "The Wealth Company"]
KEY = re.compile(r'(?i)"(stockName|instrument|holding[s_a-z]*|securityName|security_name|companyName|company_name|issuer[a-z_]*|percentage[a-z_]*|weight[a-z_]*|netAsset[a-z]*|pct[a-z_]*)"')
os.makedirs(".probe/bodies", exist_ok=True)
ROWJS = r"""() => {
  const out = [];
  const pct = /^-?\d{1,3}(\.\d{1,4})?\s*%?$/;
  document.querySelectorAll('tr').forEach(tr => {
    const c = [...tr.querySelectorAll('td,th')].map(x => x.innerText.trim()).filter(Boolean);
    if (c.length >= 2 && pct.test(c[c.length-1]) && c[0].length > 2 && !pct.test(c[0])) out.push(c);
  });
  if (out.length < 5) {
    document.querySelectorAll('li,div').forEach(el => {
      if (el.children.length < 2 || el.children.length > 6) return;
      const c = [...el.children].map(x => (x.innerText||'').trim());
      if (c.length >= 2 && pct.test(c[c.length-1]) && c[0].length > 2 && c[0].length < 90 && !pct.test(c[0]) && !c[0].includes('\n')) out.push(c);
    });
  }
  return out.slice(0, 400);
}"""
out = {}
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False)
    ctx = br.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36", viewport={"width": 1366, "height": 900})
    ctx.set_default_timeout(25000)
    for amc in WANT:
        codes = [c for c, a in amc_of.items() if a == amc and isinstance(pages.get(c), str)]
        codes.sort(key=lambda c: (not re.search(r"flexi|multi|large|mid|small|elss|focus|value", sub_of[c]), c))
        rec = {"tried": []}
        for code in codes[:2]:
            url = pages[code]; reqs = []
            def on_resp(r, reqs=reqs, code=code):
                try:
                    if r.request.resource_type not in ("xhr", "fetch", "document"): return
                    b = r.text(); k = len(KEY.findall(b))
                    item = {"url": r.url[:400], "method": r.request.method, "post": (r.request.post_data or "")[:600], "len": len(b), "keys": k}
                    if k >= 8 and len(b) < 600000:
                        fn = f".probe/bodies/{re.sub(r'[^A-Za-z]', '', amc)}_{code}_{len(reqs)}.txt"
                        open(fn, "w").write(b); item["saved"] = fn
                    reqs.append(item)
                except Exception:
                    pass
            p = ctx.new_page(); p.on("response", on_resp); err = None; rows = []
            try:
                p.goto(url, wait_until="domcontentloaded", timeout=60000)
                try: p.wait_for_load_state("networkidle", timeout=15000)
                except Exception: pass
                for sel in ["text=/^\\s*Portfolio\\s*$/i", "text=/^\\s*Holdings\\s*$/i", "text=/Portfolio/i"]:
                    try:
                        el = p.locator(sel).first
                        if el.count(): el.click(timeout=4000); p.wait_for_timeout(3000); break
                    except Exception: pass
                for _ in range(4):
                    clicked = False
                    for sel in ["text=/^\\s*(Show|View|Load)\\s+(more|all)/i", "text=/^\\s*(more|view all holdings)\\s*$/i"]:
                        try:
                            loc = p.locator(sel)
                            for i in range(min(loc.count(), 4)):
                                try: loc.nth(i).click(timeout=2500); clicked = True; p.wait_for_timeout(1200)
                                except Exception: pass
                        except Exception: pass
                    if not clicked: break
                p.mouse.wheel(0, 4000); p.wait_for_timeout(2000)
                rows = p.evaluate(ROWJS)
            except Exception as e:
                err = str(e)[:150]
            p.close()
            tot = 0.0
            for r in rows:
                try: tot += float(r[-1].replace('%', '').strip())
                except Exception: pass
            rec["tried"].append({"code": code, "name": name_of[code], "url": url, "err": err, "rows": rows[:120], "nrows": len(rows), "sum": round(tot, 2),
                                 "reqs": [q for q in reqs if q["keys"] >= 3 or q["method"] == "POST"][:40]})
        out[amc] = rec
        print(amc, [(t["code"], t["nrows"], t["sum"], len([q for q in t["reqs"] if q.get("saved")]), t["err"]) for t in rec["tried"]], flush=True)
    br.close()
json.dump(out, open(".probe/fp_probe2.json", "w"), indent=1)
