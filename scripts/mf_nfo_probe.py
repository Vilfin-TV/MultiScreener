"""Temporary: NFO list + per-scheme details + SSD tags (looking for NFO open/close dates)."""
import json, re, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0", "Accept": "application/json, text/plain, */*", "Referer": "https://www.amfiindia.com/"}
S = requests.Session(); S.headers.update(UA)
out = {"nfo": None, "items": []}
j = S.get("https://www.amfiindia.com/api/new-fund-offer", timeout=60).json()
out["nfo"] = j
for g in j.get("NewFundOffer", []):
    for it in g.get("items", []):
        sid, mid = it["Scheme_Id"], it["MF_Id"]
        rec = {"sid": sid, "name": it["SchemeName"]}
        try:
            d = S.get(f"https://www.amfiindia.com/api/scheme-details?MF_ID={mid}&scheme_id={sid}", timeout=60).json()
            rec["details"] = (d.get("data") or [{}])[0]
        except Exception as e:
            rec["detErr"] = str(e)[:100]
        try:
            x = S.get(f"https://portal.amfiindia.com/spages/SSD_{sid}.xml", timeout=60)
            rec["ssdStatus"] = x.status_code
            t = x.text
            rec["ssdHead"] = t[:300]
            rec["ssdTags"] = sorted(set(re.findall(r"<([A-Za-z_][\w.]*)", t)))[:150]
            rec["ssdDates"] = re.findall(r"<([\w.]*(?:NFO|Open|Close|Allot|Date)[\w.]*)>([^<]{0,60})<", t, re.I)[:30]
        except Exception as e:
            rec["ssdErr"] = str(e)[:100]
        out["items"].append(rec)
# AMFI NFO web page (look for dates in rendered page data)
for path in ["/nfo", "/new-fund-offer", "/investor/new-fund-offer", "/research-information/nfo"]:
    try:
        r = S.get("https://www.amfiindia.com" + path, timeout=60, headers={"Accept": "text/html"})
        out.setdefault("pages", {})[path] = [r.status_code, re.findall(r"(?:Open|Close|NFO)[^\"<]{0,80}", r.text)[:20]]
    except Exception as e:
        out.setdefault("pages", {})[path] = str(e)[:100]
json.dump(out, open(".probe/nfo_probe3.json", "w"), indent=1, ensure_ascii=False)
print(len(out["items"]), "nfo items")
for r in out["items"][:6]:
    print(json.dumps({k: r.get(k) for k in ("sid", "name", "ssdStatus", "ssdDates")}, ensure_ascii=False)[:800])
print(json.dumps(out.get("pages"), indent=1)[:2000])
