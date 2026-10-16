"""Temporary: fetch full scheme-summary samples in each format."""
import requests, re
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"})
for sid in ["11589", "1473", "4371"]:
    x = S.get(f"https://portal.amfiindia.com/spages/SSD_{sid}.xml", timeout=60).text
    open(f".probe/ssd_{sid}.xml", "w").write(x)
# ICICI / Motilal: discover their scheme ids from the scheme list and fetch one summary each
import json
for mid in range(1, 111):
    try:
        j = S.get(f"https://www.amfiindia.com/api/populate-scheme?MF_ID={mid}", timeout=60).json()
    except Exception:
        continue
    rows = j.get("data", j) if isinstance(j, dict) else j
    txt = json.dumps(rows)[:400000]
    for brand in ("ICICI Prudential", "Motilal Oswal", "Navi", "Samco", "Shriram", "Trust"):
        if brand.lower() in txt.lower()[:3000]:
            ids = re.findall(r'"(?:SchemeID|Scheme_Id|scheme_Id|SchemeId|Value|id)"\s*:\s*"?(\d+)', txt)[:40]
            for sid in ids[-6:]:
                r = S.get(f"https://portal.amfiindia.com/spages/SSD_{sid}.xml", timeout=60)
                if r.status_code == 200:
                    open(f".probe/ssd_{brand.split()[0]}_{sid}.xml", "w").write(r.text)
                    break
            print(brand, mid, ids[-6:])
