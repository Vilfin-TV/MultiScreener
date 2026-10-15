import json, re, requests
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"})
for u in ["https://portal.amfiindia.com/spages/SSD_10950.xml", "https://portal.amfiindia.com/spages/SSD_10950.xls"]:
    r = S.get(u, timeout=60)
    print("SSD", u, r.status_code, r.headers.get("content-type"), len(r.content))
    if u.endswith("xml"): print(r.text[:6000])
ids = []
for m in range(1, 90):
    try:
        r = S.get(f"https://www.amfiindia.com/api/populate-scheme?MF_ID={m}", timeout=30)
        j = r.json()
        if j: ids.append((m, len(j), j[0]["scheme_name"]))
    except Exception:
        pass
print("AMC IDS", ids)
