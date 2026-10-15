import json, re, requests
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"})
B = "https://www.amfiindia.com"
r = S.get(B + "/otherdata/scheme-details", timeout=60)
for j in sorted(set(re.findall(r'/_next/static/chunks/app/[^"\']+\.js', r.text))):
    c = S.get(B + j, timeout=60).text
    for m in re.finditer(r"/api/(populate-scheme|scheme-data|scheme-details|schemes/)", c):
        print("SNIP", j, c[max(0, m.start() - 500): m.end() + 700].replace("\n", " "))
        print("-----")
for u in ["/api/populate-scheme", "/api/populate-scheme?mfId=53", "/api/scheme-data", "/api/scheme-details", "/api/schemes/",
          "/api/scheme-details?SchemeCode=122639", "/api/scheme-details?schemeCode=122639", "/api/schemes/122639",
          "/api/scheme-data?mfId=53", "/api/scheme-details?mfId=53"]:
    try:
        x = S.get(B + u, timeout=60)
        print("API", u, x.status_code, x.text[:1500].replace("\n", " "))
    except Exception as e:
        print("API", u, "ERR", e)
    print("-----")
