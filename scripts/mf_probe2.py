import json, re, requests
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0"
out = {}
def g(name, url, n=2500):
    try:
        r = S.get(url, timeout=40)
        out[name] = [r.status_code, r.headers.get("content-type", ""), r.text[:n]]
    except Exception as e:
        out[name] = ["ERR", repr(e)]
    print("=====", name, url); print(json.dumps(out[name])[:n + 200])
for u in ["https://mfdata.in/api/v1/schemes/122639", "https://mfdata.in/api/v1/schemes/122639/holdings",
          "https://mfdata.in/api/v1/funds/122639", "https://mfdata.in/api/v1/schemes?q=parag",
          "https://mfdata.in/docs", "https://mfdata.in/api/v1", "https://mfdata.in/"]:
    g(u, u, 3000)
for u in ["https://api.kuvera.in/mf/api/v5/fund_schemes/PP001ZG-GR.json",
          "https://api.kuvera.in/mf/api/v4/fund_schemes/PP001ZG-GR.json"]:
    g(u, u, 6000)
# AMFI site: find aum / portfolio links
home = S.get("https://www.amfiindia.com/", timeout=40).text
links = sorted(set(re.findall(r'href="(/[^"]*(?:aum|portfolio|scheme)[^"]*)"', home, re.I)))
print("AMFI links", links[:80])
for l in links[:12]:
    t = S.get("https://www.amfiindia.com" + l, timeout=40).text
    js = sorted(set(re.findall(r'/_next/static/chunks/app/[^"\']+\.js', t)))
    for j in js:
        c = S.get("https://www.amfiindia.com" + j, timeout=40).text
        apis = sorted(set(re.findall(r'"(/api/[^"]{3,120})"', c))) + sorted(set(re.findall(r"\"(/api/[a-zA-Z0-9\-/]+)\"\.concat", c)))
        if apis: print("PAGE", l, j, apis[:20])
json.dump(out, open(".probe/probe2.json", "w"), indent=1)
