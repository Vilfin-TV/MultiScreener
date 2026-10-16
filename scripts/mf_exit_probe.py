"""Temporary: replay SBI's scheme-details request for several funds from inside the page."""
import json, re
from playwright.sync_api import sync_playwright
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
out = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, locale="en-IN")
    p = ctx.new_page()
    reqs = {}
    def on_req(r):
        if "SingleFundDetails" in r.url or "AllFundNames" in r.url or "GenerateToken" in r.url:
            reqs.setdefault(r.url.split("/api/")[-1], {"headers": r.headers, "post": r.post_data})
    allnames = {}
    def on_resp(r):
        if "AllFundNames" in r.url:
            try: allnames["t"] = r.text()
            except Exception: pass
    p.on("request", on_req); p.on("response", on_resp)
    p.goto("https://www.sbimf.com/sbimf-scheme-details/sbi-small-cap-fund-329", wait_until="domcontentloaded", timeout=90000)
    p.wait_for_timeout(12000)
    out["reqs"] = reqs
    out["allNames"] = allnames.get("t", "")[:3000]
    req = reqs.get("SchemeDetailsAPI/SingleFundDetails/")
    if req:
        res = p.evaluate("""async ([hdr, post, ids]) => {
            const out = {};
            for (const id of ids) {
              const body = JSON.parse(post); const d = JSON.parse(body.Data); d.FundId = String(id); body.Data = JSON.stringify(d);
              body.Requestid = crypto.randomUUID();
              const h = {}; for (const k of Object.keys(hdr)) if (!/^(host|content-length|cookie|accept-encoding|origin|referer|user-agent|sec-)/i.test(k)) h[k] = hdr[k];
              try { const r = await fetch('/api/SchemeDetailsAPI/SingleFundDetails/', {method: 'POST', headers: h, body: JSON.stringify(body)});
                    const t = await r.text(); out[id] = [r.status, t.slice(0, 900)]; } catch (e) { out[id] = String(e); }
            }
            return out; }""", [req["headers"], req["post"], [329, 2, 43, 70]])
        out["replay"] = res
    b.close()
json.dump(out, open(".probe/exit_probe2.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])
