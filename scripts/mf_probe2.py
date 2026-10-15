import json, re, requests
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"})
B = "https://www.amfiindia.com"
home = S.get(B + "/", timeout=60).text
hrefs = sorted(set(re.findall(r'href="(/[^"#?]*)"', home)))
print("HOME hrefs", len(hrefs), hrefs)
chunks = sorted(set(re.findall(r'/_next/static/chunks/[^"\']+\.js', home)))
routes = set()
for j in chunks:
    try:
        c = S.get(B + j, timeout=60).text
    except Exception:
        continue
    for m in re.findall(r'["\'](/(?:otherdata|research-information|net-asset-value|investor|mutual-fund|portfolio|downloads|scheme)[a-zA-Z0-9/_\-]*)["\']', c):
        routes.add(m)
print("ROUTES", sorted(routes))
cands = sorted(routes | {"/otherdata/portfolio-disclosure", "/otherdata/monthly-portfolio", "/portfolio-disclosure",
                         "/otherdata/scheme-details", "/otherdata/scheme-information", "/research-information/other-data/scheme-details"})
for p in cands:
    if not re.search(r"portfolio|scheme|aum|exit|fund-perf|load|riskometer", p, re.I):
        continue
    try:
        r = S.get(B + p, timeout=60)
    except Exception as e:
        print("ERR", p, e); continue
    js = sorted(set(re.findall(r'/_next/static/chunks/app/[^"\']+\.js', r.text)))
    apis = set()
    for j in js:
        c = S.get(B + j, timeout=60).text
        apis |= set(re.findall(r'["`](/api/[a-zA-Z0-9\-/_]+)', c))
    print("PAGE", p, r.status_code, sorted(apis)[:30])
