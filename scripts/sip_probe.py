"""Temporary probe 3: RBI WSS table layout."""
import re, requests, json
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"}
r = requests.get("https://www.rbi.org.in/Scripts/BS_NSDPDisplay.aspx?param=4", headers=UA, timeout=60)
t = r.text
i = t.find("10-Year G-Sec")
seg = t[max(0, i - 6000): i + 1500]
rows = []
for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S | re.I):
    cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
    if any(re.search(r"repo|t-bill|treasury|g-sec|yield|call|cblo|triparty|week|item|policy|cd\b|cp\b|91|364", c, re.I) for c in cells[:2]):
        rows.append(cells)
json.dump({"rows": rows[:120], "title": re.findall(r"<title>(.*?)</title>", t, re.S)[:1]}, open(".probe/sip_probe3.json", "w"), indent=1)
print(json.dumps(rows[:120], indent=0)[:8000])
