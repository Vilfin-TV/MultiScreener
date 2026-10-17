"""Temporary: discover monthly portfolio spreadsheet links on fund-house websites."""
import json, re, sys, time
from urllib.parse import urljoin
sys.path.insert(0, "scripts")
import build_mf_holdings as H
from playwright.sync_api import sync_playwright

sites = json.load(open("data/mf/scheme_pages.json"))["_sites"]
have = set(H.SOURCES)
todo = [a for a in sites if a not in have]
if len(sys.argv) > 1:
    todo = [a for a in todo if a in sys.argv[1].split(",")]
KEY = re.compile(r"portfolio|disclosure|statutory|downloads?", re.I)
out = {}
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False)
    ctx = br.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36", accept_downloads=True)
    ctx.set_default_timeout(30000)
    for amc in todo:
        t0 = time.time(); rec = {"site": sites[amc], "pages": [], "files": []}
        try:
            p = ctx.new_page(); p.goto(sites[amc], wait_until="domcontentloaded", timeout=45000); p.wait_for_timeout(3000)
            links = p.eval_on_selector_all("a", "as => as.map(a => [a.href, (a.innerText||a.title||'').trim().slice(0,80)])")
            p.close()
            cands = []
            for href, txt in links:
                if not href.startswith("http"): continue
                s = (3 if re.search(r"portfolio", href + txt, re.I) else 0) + (2 if re.search(r"month", href + txt, re.I) else 0) + (1 if KEY.search(href + txt) else 0)
                if s: cands.append((s, href, txt))
            cands = sorted(set(cands), key=lambda x: -x[0])[:6]
            rec["cands"] = [(h, t) for _, h, t in cands]
            for _, href, txt in cands:
                if time.time() - t0 > 100: break
                try:
                    fs = H.harvest(ctx, href)
                except Exception as e:
                    rec["pages"].append([href, "ERR " + str(e)[:80]]); continue
                fs = [f for f in dict.fromkeys(fs) if H.FILE_RX.search(f)]
                rec["pages"].append([href, len(fs)])
                for f in fs:
                    rec["files"].append([f, H.link_month(f)])
        except Exception as e:
            rec["err"] = str(e)[:200]
        rec["files"] = rec["files"][:60]
        out[amc] = rec
        print(amc, len(rec["files"]), round(time.time() - t0), flush=True)
    br.close()
json.dump(out, open(".probe/pf_probe.json", "w"), indent=1)
