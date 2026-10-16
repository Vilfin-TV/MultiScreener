"""Temporary: find a source for SBI exit loads (fund-house site data feed) and a general fallback."""
import json, re, requests
from playwright.sync_api import sync_playwright
out = {"sbi": {}, "general": {}}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
# 1) general fund-facts feeds keyed by ISIN (SBI Small Cap Direct Growth INF200K01T28 / AMFI 125497)
S = requests.Session(); S.headers["User-Agent"] = UA
for name, url in [("kv_isin", "https://api.kuvera.in/mf/api/v5/fund_schemes/INF200K01T28.json"),
                  ("mirror", "https://mf.captnemo.in/kuvera/INF200K01T28")]:
    try:
        r = S.get(url, timeout=60)
        j = r.json(); j = j[0] if isinstance(j, list) and j else j
        out["general"][name] = {"status": r.status_code, "keys": sorted(j.keys()) if isinstance(j, dict) else str(type(j)),
                                "exit": {k: str(v)[:300] for k, v in (j.items() if isinstance(j, dict) else []) if re.search(r"load|exit|redempt", k, re.I)}}
    except Exception as e:
        out["general"][name] = str(e)[:200]
# 2) SBI website: find a scheme page, record data responses that mention exit load
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, locale="en-IN", viewport={"width": 1366, "height": 900})
    hits = []
    def on_resp(r):
        try:
            ct = r.headers.get("content-type", "")
            if ("json" in ct or "text/plain" in ct) and r.request.resource_type in ("xhr", "fetch"):
                t = r.text()
                hits.append({"url": r.url[:300], "method": r.request.method, "post": (r.request.post_data or "")[:300],
                             "exit": bool(re.search(r"exit\s*load|exitload", t, re.I)), "n": len(t),
                             "sample": t[:800] if re.search(r"exit\s*load|exitload", t, re.I) else ""})
        except Exception:
            pass
    p = ctx.new_page(); p.on("response", on_resp)
    p.goto("https://www.sbimf.com/", wait_until="domcontentloaded", timeout=90000); p.wait_for_timeout(8000)
    links = [l for l in p.eval_on_selector_all("a", "as=>as.map(a=>a.href)") if re.search(r"small-?cap", l, re.I)]
    out["sbi"]["links"] = list(dict.fromkeys(links))[:15]
    target = next((l for l in links if re.search(r"sbi-?small-?cap-?fund", l, re.I)), None) or "https://www.sbimf.com/sbimf-scheme-details/sbi-small-cap-fund-329"
    out["sbi"]["target"] = target
    p.goto(target, wait_until="domcontentloaded", timeout=90000); p.wait_for_timeout(12000)
    try:
        el = p.get_by_text(re.compile(r"view details", re.I)).first; el.hover(timeout=5000); el.click(timeout=5000); p.wait_for_timeout(3000)
    except Exception as e:
        out["sbi"]["clickErr"] = str(e)[:150]
    body = p.inner_text("body")
    i = body.lower().find("exit load")
    out["sbi"]["bodyExit"] = body[max(0, i - 100):i + 600] if i >= 0 else ""
    out["sbi"]["final"] = p.url
    html = p.content()
    out["sbi"]["htmlExit"] = [m[:400] for m in re.findall(r"[^<>]{0,200}[Ee]xit [Ll]oad[^<>]{0,300}", html)][:6]
    out["sbi"]["xhr"] = hits[:80]
    b.close()
json.dump(out, open(".probe/exit_probe.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out["general"], indent=1)[:3000]); print(out["sbi"].get("target"), out["sbi"].get("bodyExit", "")[:500])
