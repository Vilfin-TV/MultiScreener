"""Temporary: how to link SBI / ABSL / ICICI / Motilal schemes to their official records."""
import gzip, json, re, sys, requests
sys.path.insert(0, "scripts")
import mf_enrich as E
enr = json.load(gzip.open(".mfcache/enrich.json.gz", "rt"))
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0", "Accept": "application/json, text/plain, */*", "Referer": "https://www.amfiindia.com/"})
out = {}
for brand, want in [("SBI", "aggressive hybrid|equity hybrid|large cap|bluechip"), ("Aditya Birla", "arbitrage|aggressive hybrid|equity hybrid"),
                    ("ICICI", "arbitrage|balanced"), ("Motilal", "midcap|flexi")]:
    mids = [m for m, lst in enr["amcs"].items() if any(brand.lower() in n.lower() for _, n in lst[:30])]
    rec = {"mids": mids}
    for mid in mids[:1]:
        lst = enr["amcs"][mid]
        rec["count"] = len(lst)
        rec["names"] = [n for _, n in lst if re.search(want, n, re.I)][:12]
        sids = [s for s, n in lst if re.search(want, n, re.I)][:3]
        rec["probe"] = []
        for sid in sids:
            r = {"sid": sid, "cached": list((enr["sd"].get(str(sid)) or enr["sd"].get(sid) or {}).keys())}
            try:
                d = S.get(f"{E.AMFI}/api/scheme-details?MF_ID={mid}&scheme_id={sid}", timeout=60).json()
                row = (d.get("data") or [{}])[0]
                r["detailKeys"] = {k: str(v)[:140] for k, v in row.items()}
            except Exception as e: r["detailErr"] = str(e)[:120]
            for ext in ("xml", "xls", "xlsx"):
                try:
                    x = S.get(f"{E.PORTAL}/spages/SSD_{sid}.{ext}", timeout=60)
                    r["ssd_" + ext] = [x.status_code, x.headers.get("content-type"), len(x.content), x.content[:60].hex() if ext != "xml" else x.text[:150]]
                except Exception as e: r["ssd_" + ext] = str(e)[:80]
            try:
                dd = S.get(f"{E.AMFI}/api/schemes/{sid}/documents", timeout=60)
                r["docs"] = dd.text[:600]
            except Exception as e: r["docs"] = str(e)[:80]
            rec["probe"].append(r)
    out[brand] = rec
json.dump(out, open(".probe/info_probe2.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])
