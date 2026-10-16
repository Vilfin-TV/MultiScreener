"""Temporary: discover AMFI's data endpoints (new site) that mention NFOs, and test the scheme-master route."""
import json, re, requests, gzip
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0", "Accept": "application/json, text/plain, */*", "Referer": "https://www.amfiindia.com/"}
S = requests.Session(); S.headers.update(UA)
out = {"apis": [], "tries": {}, "recent": []}
home = S.get("https://www.amfiindia.com/", timeout=60).text
chunks = sorted(set(re.findall(r'/_next/static/chunks/[^"\']+\.js', home)))
found = set()
for c in chunks[:120]:
    try:
        js = S.get("https://www.amfiindia.com" + c, timeout=60).text
    except Exception:
        continue
    for m in re.findall(r'["\'`](/api/[A-Za-z0-9_\-/]+)', js):
        found.add(m)
out["apis"] = sorted(found)
for path in [p for p in sorted(found) if re.search(r"nfo|new-?fund|launch|offer", p, re.I)][:20] + ["/api/nfo", "/api/nfo-details", "/api/populate-nfo", "/api/new-fund-offer"]:
    try:
        r = S.get("https://www.amfiindia.com" + path, timeout=60)
        out["tries"][path] = [r.status_code, r.text[:600]]
    except Exception as e:
        out["tries"][path] = str(e)[:100]
# scheme-master route: newest scheme ids of a few fund houses + their details
for mid in (22, 3, 20, 55):
    try:
        j = S.get(f"https://www.amfiindia.com/api/populate-scheme?MF_ID={mid}", timeout=60).json()
        rows = j.get("data", j) if isinstance(j, dict) else j
        rows = rows if isinstance(rows, list) else []
        out["recent"].append({"mid": mid, "n": len(rows), "sample": rows[:2]})
        ids = sorted({int(v) for r in rows for k, v in (r.items() if isinstance(r, dict) else []) if re.search(r"id", k, re.I) and str(v).isdigit()})[-5:]
        for sid in ids:
            d = S.get(f"https://www.amfiindia.com/api/scheme-details?MF_ID={mid}&scheme_id={sid}", timeout=60).json()
            row = (d.get("data") or [{}])[0] if isinstance(d, dict) else {}
            out["recent"].append({"sid": sid, "name": row.get("Scheme_Name"), "launch": row.get("Launch_Date"), "type": row.get("SchemeType_Desc"), "cat": row.get("SchemeCat_Desc"), "keys": list(row.keys())})
    except Exception as e:
        out["recent"].append({"mid": mid, "err": str(e)[:150]})
json.dump(out, open(".probe/nfo_probe2.json", "w"), indent=1, ensure_ascii=False)
print(len(out["apis"]), "api paths"); print(json.dumps(out["tries"], indent=1)[:3000]); print(json.dumps(out["recent"], indent=1)[:3000])
