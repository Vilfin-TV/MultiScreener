import json, re, requests
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"})
B = "https://www.amfiindia.com"
h = S.get(B + "/otherdata/scheme-details", timeout=60).text
i = h.find("mfName")
print("HTML mfName ctx:", h[max(0, i - 600): i + 1200].replace("\n", " ") if i >= 0 else "none")
ids = re.findall(r'\\?"mfId\\?":\\?"?(\d+)\\?"?,\\?"mfName\\?":\\?"([^"\\]+)', h) or re.findall(r'"mfId":"?(\d+)"?,"mfName":"([^"]+)"', h)
print("AMC IDS", len(ids), ids[:60])
mid = ids[0][0] if ids else "53"
for m in [mid, "53"]:
    r = S.get(f"{B}/api/populate-scheme?MF_ID={m}", timeout=60)
    print("POPULATE", m, r.status_code, r.text[:1200].replace("\n", " "))
r = S.get(f"{B}/api/populate-scheme?MF_ID=53", timeout=60)
try:
    lst = r.json()
    lst = lst.get("data", lst) if isinstance(lst, dict) else lst
except Exception:
    lst = []
print("N schemes axis", len(lst))
if lst:
    e = lst[0]; print("FIRST", e)
    sid = next((v for k, v in e.items() if re.search(r"id", k, re.I)), None)
    for k, v in e.items(): print("  ", k, v)
    for u in [f"/api/scheme-details?MF_ID=53&scheme_id={sid}", f"/api/scheme-data?strMFId=53&strSDId={sid}&strOption=AUM",
              f"/api/scheme-data?strMFId=53&strSDId={sid}&strOption=NAV", f"/api/schemes/{sid}/documents"]:
        x = S.get(B + u, timeout=60); print("API", u, x.status_code, x.text[:2500].replace("\n", " ")); print("-----")
    # find a flexi / large fund for richer load text
    for e in lst:
        if re.search(r"flexi|large|small", json.dumps(e), re.I):
            sid = next((v for k, v in e.items() if re.search(r"id", k, re.I)), None)
            x = S.get(f"{B}/api/scheme-details?MF_ID=53&scheme_id={sid}", timeout=60); print("EQ", e, x.text[:1500]); break
