"""Temporary: why are benchmark / allocation / exit load / managers missing for some funds?"""
import gzip, json, re, sys, collections
import xml.etree.ElementTree as ET
sys.path.insert(0, "scripts")
import mf_enrich as E

def load(p):
    try: return json.load(gzip.open(p, "rt"))
    except Exception as e: print("cannot load", p, e); return {}
enr = load(".mfcache/enrich.json.gz"); facts = load(".mfcache/facts.json.gz")
scr = json.load(open("data/mf/screener.json")); C = {c: i for i, c in enumerate(scr["cols"])}
D = {}
import glob
for f in glob.glob("data/mf/d/*.json"): D.update(json.load(open(f)))
isin2sid = {}
for sid, rec in enr.get("sd", {}).items():
    if rec.get("ssdXml"):
        for i in re.findall(r"INF[A-Z0-9]{9}", rec["ssdXml"]): isin2sid.setdefault(i, sid)
out = {"tags_when_missing": {}, "samples": []}
miss = collections.defaultdict(list)
for r in scr["rows"]:
    code = str(r[C["code"]]); info = D[code]["info"]
    for f in ("benchmark", "alloc", "exitLoad", "managers"):
        if not info.get(f): miss[f].append(r)
for f, lst in miss.items():
    tagc = collections.Counter(); nossd = 0
    for r in lst:
        sid = isin2sid.get(r[C["isin"]])
        if not sid: nossd += 1; continue
        root = ET.fromstring(enr["sd"][sid]["ssdXml"].lstrip("﻿").encode())
        node = root.find("SchemeSummary") or root
        for c in node:
            if (c.text or "").strip() and re.search(r"bench|alloc|load|manager|index", c.tag, re.I): tagc[c.tag] += 1
    out["tags_when_missing"][f] = {"n": len(lst), "noSsd": nossd, "tags": tagc.most_common(15)}
seen = set()
for f, lst in miss.items():
    for r in lst[:5] + [x for x in lst if x[C["amc"]] not in seen][:6]:
        seen.add(r[C["amc"]])
        sid = isin2sid.get(r[C["isin"]]); rec = enr["sd"].get(sid, {}) if sid else {}
        tags = {}
        if rec.get("ssdXml"):
            root = ET.fromstring(rec["ssdXml"].lstrip("﻿").encode()); node = root.find("SchemeSummary") or root
            tags = {c.tag: (c.text or "").strip()[:220] for c in node if re.search(r"bench|alloc|load|manager|index|objective", c.tag, re.I)}
        fk = facts.get(r[C["isin"]]) or {}
        out["samples"].append({"missing": f, "name": r[C["name"]], "amc": scr["amcs"][r[C["amc"]]], "isin": r[C["isin"]], "sid": sid,
            "detailsLoad": (rec.get("details") or {}).get("load", "")[:300], "ssdTags": tags,
            "factKeys": {k: (str(v)[:160]) for k, v in fk.items() if re.search(r"load|bench|manager|objective|alloc|sip|lump|min", k, re.I)}})
json.dump(out, open(".probe/info_probe.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out["tags_when_missing"], indent=1))
