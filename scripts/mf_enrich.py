#!/usr/bin/env python3
"""
India Mutual Fund Screener — official scheme enrichment from AMFI.

For every fund in the universe this collects, from AMFI's public scheme-details service:
  * exit load (scheme master), investment objective, launch date, minimum investment text
  * quarterly average AUM per plan (summed across plans = fund size)
  * Scheme Summary Document (SEBI-mandated, machine-readable): riskometer, Tier-1 benchmark,
    fund managers with start dates, stated asset allocation, face value, allotment date,
    potential risk class, custodian / registrar, minimum application amounts, ISINs
  * links to the Scheme Information Document and the Scheme Summary Document

Everything is cached (.mfcache/enrich.json.gz) and refreshed weekly per scheme under a time
budget, so the daily build stays fast. Mapping to AMFI scheme codes is by ISIN (from the
summary document), falling back to exact scheme-name matching.
"""
from __future__ import annotations

import gzip
import json
import logging
import html
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

log = logging.getLogger("mf")

AMFI = "https://www.amfiindia.com"
PORTAL = "https://portal.amfiindia.com"
REFRESH_DAYS = 7
MAX_MF_ID = 110


def _load(path, default):
    try:
        with gzip.open(path, "rt") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _save(path, obj):
    tmp = Path(str(path) + ".tmp")
    with gzip.open(tmp, "wt") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    tmp.replace(path)


def norm(n: str) -> str:
    n = re.sub(r"\(.*?\)", " ", (n or "").lower())
    n = n.replace("&", " and ")
    n = re.sub(r"\b(fund|scheme|plan|the|direct|growth|option|an?|open ended|erstwhile)\b", " ", n)
    return re.sub(r"[^a-z0-9]+", "", n)


def _age(ts: str | None) -> int:
    try:
        return (date.today() - date.fromisoformat(ts or "")).days
    except ValueError:
        return 9999


def _clean(t: str | None) -> str:
    t = (t or "").replace("\r", "\n").replace(" ", " ").replace("â€™", "'").replace("â", "'")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def parse_exit_load(t: str | None) -> list[str]:
    """Scheme-master load text → list of readable lines (entry-load preamble removed)."""
    t = _clean(t)
    if not t:
        return []
    t = re.sub(r"(?i)entry\s*load\s*[:\-–]?\s*(not applicable|nil|n\.?a\.?)\s*[,;.]?", "", t)
    t = re.sub(r"(?i)^\s*exit\s*load\s*[:\-]?\s*", "", t.strip())
    t = re.sub(r"(?i)\bexit\s*load\s*(?:[:\-–]\s*|(?=\((?:i|a|1)\)))", "\n", t)     # "Exit load:" / "Exit Load (i)" headings only
    t = re.sub(r"(?<=[a-z)])\.(?=\s*(?:\d|No |Nil|If |For |In ))", ".\n", t)    # run-together sentences
    parts = re.split(r"\n|•|;\s+(?=[A-Z])|(?<=\.)\s+(?=[A-Z(])|\s(?=\((?:i{1,3}|iv|v|vi|[a-f])\)\s)", t)
    out = []
    for p in parts:
        p = p.strip(" -–;,")
        if re.fullmatch(r"(?i)(entry\s*(load)?\s*(&|and)?|exit\s*load|entry\s*load\s*[-–:]?\s*(nil|na|n\.a\.|not applicable)|load\s*structure)\W*", p):
            continue
        if re.search(r"(?i)entry\s*load", p) and not re.search(r"(?i)exit", p):
            continue                                   # entry loads were abolished in 2009; drop the boilerplate
        p = p.lstrip(". ")
        if len(p) > 1:
            out.append(re.sub(r"\s+", " ", p))
    # merge continuation fragments (lines that start lowercase)
    merged = []
    for p in out:
        if merged and (p[:1].islower() or p[:1] in ")%"):
            merged[-1] += " " + p
        else:
            merged.append(p)
    return merged[:12]


def is_nil_load(lines: list[str]) -> bool:
    j = " ".join(lines).lower()
    return bool(lines) and bool(re.fullmatch(r"\W*(nil|not applicable|na|n\.a\.|none|no load|0%?|0\.00%?|exit load\W*nil)\W*", j))


def parse_alloc(text: str | None) -> list[dict]:
    """'Equity ... - (65%-100%),Debt ... - (0%-35%)' → [{label, min, max, kind}]"""
    out = []
    for m in re.finditer(r"([^,;()]+?)\s*[-–:]?\s*\(?\s*(\d+(?:\.\d+)?)\s*%?\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*%\s*\)?", text or ""):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" -–,")
        label = re.split(r"(?<=[a-z])[:.]\s+(?=[A-Z])|:\s*", label)[-1].strip(" -–,")   # drop "The asset allocation … :" intros
        if len(label) < 3:
            continue
        lo, hi = float(m.group(2)), float(m.group(3))
        low = label.lower()
        if re.search(r"etcd|gold|silver|commodit", low):
            kind = "commodity"
        elif re.search(r"debt|money market|bond|g-?sec|government|treasury|tri-?party|repo|cash|fixed income|sdl|t-?bill|\bcps?\b|\bcds?\b", low):
            kind = "debt"
        elif re.search(r"equity|stock|share|arbitrage|derivative", low):
            kind = "equity"
        elif re.search(r"gold|silver|commodit", low):
            kind = "commodity"
        elif re.search(r"reit|invit", low):
            kind = "reit"
        elif re.search(r"overseas|foreign|international|global", low):
            kind = "global"
        elif re.search(r"units of|etf|mutual fund|fund", low):
            kind = "fund"
        else:
            kind = "other"
        out.append({"label": label[:120], "min": lo, "max": hi, "kind": kind})
    return out[:10]


# ───────── scheme summaries come in four layouts; convert all of them to the standard one ─────────
_LABELS = [  # (regex on a normalised row label, standard tag)
    (r"^fund_?name$", "Fund_Name"), (r"^fund_?type$", "Fund_Type"),
    (r"riskometer.*launch", "Riskometer_At_the_time_of_Launch"), (r"riskometer.*(as_?on|date)", "Riskometer_as_on_Date"),
    (r"category.*sebi", "Category_as_Per_SEBI_Categorization_Circular"), (r"potential_?risk", "Potential_Risk_Class_as_on_date"),
    (r"objective", "Description_Objective_of_the_scheme"), (r"stated_?asset_?allocation", "Stated_Asset_Allocation"),
    (r"^face_?value", "Face_Value"), (r"^allotment_?date", "Allotment_Date"),
    (r"benchmark.*(tier_?1|tier_?i)$", "Benchmark_Tier_1"), (r"benchmark.*(tier_?2|tier_?ii)$", "Benchmark_Tier_2"),
    (r"annual_?expense", "Annual_Expense_Stated_maximum"), (r"exit_?load", "Exit_Load_if_applicable"),
    (r"^custodian", "Custodian"), (r"^auditor", "Auditor"), (r"^registrar", "Registrar"), (r"^listing", "Listing_Details"),
    (r"^minimum_?application_?amount$", "Minimum_Application_Amount"), (r"^minimum_?additional_?amount$", "Minimum_Additional_Amount"),
    (r"side_?pocket|segr?egated_?portfolio", "Sidepocketing_if_applicable"),
]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _iso_to_dmy(v: str) -> str:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:T[\d:.]+)?$", v.strip())
    return f"{m.group(3)}-{_MONTHS[int(m.group(2)) - 1]}-{m.group(1)}" if m else v


def _local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def _rows(root) -> list[list[str]]:
    """Text of every table row in an Excel-2003 XML workbook or an OpenDocument flat file."""
    out = []
    for row in root.iter():
        if _local(row.tag) not in ("Row", "table-row"):
            continue
        cells = []
        for c in row:
            if _local(c.tag) not in ("Cell", "table-cell"):
                continue
            txt = "\n".join("".join(e.itertext()).strip() for e in c.iter() if _local(e.tag) in ("Data", "p")).strip()
            cells.append(txt)
        if any(cells):
            out.append(cells)
    return out


def _std_xml(fields: dict) -> str:
    body = "".join(f"<{k}>{html.escape(v)}</{k}>" for k, v in fields.items() if v)
    return f"<SchemeSummaryDocument><SchemeSummary>{body}</SchemeSummary></SchemeSummaryDocument>"


def normalise_ssd(text: str) -> str:
    """Return the scheme summary in the standard <SchemeSummary> layout (unchanged if it already is)."""
    if not text or "<SchemeSummary" in text:
        return text
    try:
        root = ET.fromstring(text.lstrip("﻿").replace("ï»¿", "").encode("utf-8"))
    except ET.ParseError:
        return text
    f = {}
    if _local(root.tag) == "root":                      # JSON-style XML (e.g. SBI)
        def first(tag):
            e = root.find(tag)
            return _clean(e.text) if e is not None and e.text else ""
        for tag in ("Fund_Name", "Riskometer_At_the_time_of_Launch", "Riskometer_as_on_Date",
                    "Category_as_Per_SEBI_Categorization_Circular", "Description_Objective_of_the_scheme", "Allotment_Date",
                    "Benchmark_Tier_1", "Benchmark_Tier_2", "Annual_Expense_Stated_maximum", "Custodian", "Auditor",
                    "Registrar", "Listing_Details", "Minimum_Application_Amount", "Minimum_Additional_Amount", "Face_Value",
                    "Exit_Load_if_applicable", "Fund_Type"):
            f[tag] = first(tag)
        f["Potential_Risk_Class_as_on_date"] = first("Potential_Risk_Class_as_on_Date") or first("Potential_Risk_Class_as_on_date")
        f["ISINs"] = ", ".join(_clean(e.text) for e in root.iter("ISIN") if e.text)
        alloc = []
        for arr in root:
            if arr.tag.startswith("Stated_Asset_Allocation"):
                for it in arr:
                    ins, ind = it.findtext("Instruments") or "", it.findtext("IndicativeAllocation") or ""
                    if ins.strip() and ind.strip():
                        alloc.append(f"{re.sub(r'[()^*#]', ' ', _clean(ins)).strip()} - ({_clean(ind)})")
        f["Stated_Asset_Allocation"] = ", ".join(alloc)
        names, dates = [], []
        for arr in root:
            if arr.tag.startswith("Fund_Manager"):
                for it in arr:
                    n = _clean(it.findtext("Name") or "")
                    if n:
                        names.append(n)
                        dates.append(f"{n} - {_iso_to_dmy(_clean(it.findtext('FundManagerFromDate') or ''))}")
        f["Fund_Manager_Name"], f["Fund_Manager_From_Date"] = ", ".join(names), ", ".join(dates)
        sip = [float(m) for t in root.iter("MinimumInstalments") if t.text and re.search(r"monthly.*\bsip\b", t.text, re.I)
               for m in re.findall(r"Rs\.?\s*([\d.]+)", t.text)]
        if sip:
            f["SIP_SWP__STP_Details_Minimum_amount"] = f"Monthly - Rs. {int(min(sip))}"
        f = {k: re.sub(r"\s\?\s", " – ", v) for k, v in f.items()}   # an en dash arrives as "?" in this layout
        return _std_xml(f)
    rows = _rows(root)                                  # Excel / OpenDocument workbooks
    if not rows:
        return text
    names, types, dates, isins, section, last = [], [], [], [], "", ""
    for cells in rows:
        cells = [c for c in cells]
        if len(cells) >= 3 and re.fullmatch(r"\d*\.?|\*", cells[0].strip()):
            label, value = cells[1], " ".join(c for c in cells[2:] if c).strip()
        elif len(cells) >= 2:
            label, value = cells[0], " ".join(c for c in cells[1:] if c).strip()
        else:
            if re.search(r"\b(sip|stp|swp)\b", cells[0], re.I):
                section = cells[0].lower()
            continue
        key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        if re.match(r"(sip|stp|swp)_?details", key):
            section = key
            continue
        if re.search(r"fund_?manager.*name", key):
            names.append(value); last = "fm"; continue
        if re.search(r"fund_?manager.*type", key):
            types.append(value); continue
        if re.search(r"fund_?manager.*(from|date)", key):
            dates.append(_iso_to_dmy(value)); continue
        if key == "isins":
            last = "isin"; continue
        if re.fullmatch(r"INF[A-Z0-9]{9}", value):
            isins.append(value); continue
        if key == "minimum_amount" and section.startswith("sip") and re.fullmatch(r"[\d.,]+", value):
            f["SIP_SWP__STP_Details_Minimum_amount"] = f"Monthly - Rs. {value}"
            continue
        if last == "expense" and key in ("regular", "direct"):
            try:
                v = float(value)
                f.setdefault("_exp", []).append(f"{label.title()} Plan - {round(v * 100 if v < 0.2 else v, 2)}")
            except ValueError:
                pass
            continue
        for rx, tag in _LABELS:
            if re.search(rx, key) and tag not in f:
                f[tag] = _iso_to_dmy(value) if tag == "Allotment_Date" else value
                last = "expense" if tag == "Annual_Expense_Stated_maximum" else tag
                break
    if f.get("_exp"):
        f["Annual_Expense_Stated_maximum"] = ", ".join(f.pop("_exp"))
    f.pop("_exp", None)
    f["ISINs"] = ", ".join(isins)
    f["Fund_Manager_Name"] = ", ".join(n for n in names if n)
    f["Fund_Manager_From_Date"] = ", ".join(f"{n} - {d}" for n, d in zip(names, dates) if n and d)
    f["Fund_Manager_Type_PrimaryComanageDescription"] = ", ".join(f"{n} - {t}" for n, t in zip(names, types) if n and t)
    return _std_xml({k: v for k, v in f.items() if isinstance(v, str)})


def parse_ssd(xml_text: str) -> dict:
    xml_text = normalise_ssd(xml_text)
    try:
        root = ET.fromstring(xml_text.lstrip("﻿").replace("ï»¿", "").encode("utf-8"))
    except ET.ParseError:
        return {}
    node = root.find("SchemeSummary")
    if node is None:
        node = root
    f = {c.tag: _clean(c.text) for c in node}

    def g(k):
        v = f.get(k, "")
        return "" if v in ("-", "N/A", "NA", "n/a") else v

    def clean_name(n):
        n = re.sub(r"\(.*?(\)|$)", " ", n)                                  # (Equity portion), (Fund manager ...
        n = re.sub(r"\bFM\s*-?\s*\d+\b\s*[-:]?", " ", n, flags=re.I)
        n = re.sub(r"(?i)^\s*for\s+[\w ]{2,30}?\s*[:\-]\s*", "", n)          # "For Equity : ..."
        n = n.strip(" -–—:.,")
        n = re.sub(r"^\s*(mr|ms|mrs|dr|shri|smt)\.?\s*(?=[A-Z])", "", n, flags=re.I)
        return re.sub(r"\s+", " ", n).strip(" -:.")

    raw_names = html.unescape(html.unescape(g("Fund_Manager_Name")))
    raw_names = re.sub(r"\([^)]*(\)|$)", " ", raw_names)                    # (Equity portion), (Fund manager & Analyst)
    raw_names = re.sub(r"(?:(?<=[a-z])|\b)FM\s*[-–]?\s*\d*\b", ",", raw_names, flags=re.I)
    raw_names = re.sub(r"(?<=[a-z])\s*(?=\b(?:Mr|Ms|Mrs|Dr)\.?\s*[A-Z])", ",", raw_names)   # "Prateek Jain Mr. Anoop V"
    names = [clean_name(n) for n in re.split(r",|;|\band\b|&|/|\n|\s[–—-]\s", raw_names)]
    names = [n for n in names if 2 < len(n) <= 40 and not re.search(r"\d|portion|manager|fund|scheme|equity|debt|income", n, re.I)]
    names = list(dict.fromkeys(names))
    since_txt = re.sub(r"\bFM\s*-?\s*\d+\b\s*[-:]?", " ", g("Fund_Manager_From_Date"), flags=re.I)
    role_txt = g("Fund_Manager_Type_PrimaryComanageDescription")
    date_rx = (r"(?:since\s+)?(?:\d{1,2}(?:st|nd|rd|th)?[-/ .](?:[A-Za-z]{3,9}|\d{1,2})[-/ .,]*\d{2,4}"
               r"|[A-Za-z]{3,9}\.?\s*[-,]?\s*\d{4})")
    dates_in_order = re.findall(date_rx, since_txt, re.I)
    managers = []
    for i, n in enumerate(names):
        since = ""
        m = re.search(re.escape(n) + r"\s*[-–:(]?\s*(" + date_rx + ")", since_txt, re.I)
        if m:
            since = m.group(1)
        elif len(dates_in_order) == len(names):
            since = dates_in_order[i]
        since = re.sub(r"(?i)^since\s+", "", since.strip())
        role = ""
        m = re.search(re.escape(n) + r"\s*[-–:]\s*([^,;]+)", role_txt, re.I)
        if m:
            role = m.group(1).strip()
        managers.append({"name": n, "since": since[:40], "role": role[:80]})
    isins = re.findall(r"INF[A-Z0-9]{9}", g("ISINs"))
    return {
        "riskometer": g("Riskometer_as_on_Date"), "riskLaunch": g("Riskometer_At_the_time_of_Launch"),
        "category": g("Category_as_Per_SEBI_Categorization_Circular"), "prc": g("Potential_Risk_Class_as_on_date"),
        "type": g("Fund_Type"), "objective": g("Description_Objective_of_the_scheme"),
        "alloc": parse_alloc(g("Stated_Asset_Allocation")), "allocText": g("Stated_Asset_Allocation")[:600],
        "faceValue": g("Face_Value"), "allotment": g("Allotment_Date"), "benchmark": g("Benchmark_Tier_1"),
        "benchmark2": g("Benchmark_Tier_2"), "managers": managers[:8], "maxTer": g("Annual_Expense_Stated_maximum"),
        "exitLoadSsd": g("Exit_Load_if_applicable"), "custodian": g("Custodian"), "auditor": g("Auditor"),
        "registrar": g("Registrar"), "minApp": g("Minimum_Application_Amount"),
        "minAdd": g("Minimum_Additional_Amount"), "sipMin": g("SIP_SWP__STP_Details_Minimum_amount")[:300],
        "listing": g("Listing_Details"), "sidePocket": g("Sidepocketing_if_applicable"), "isins": isins,
    }


class Enricher:
    def __init__(self, session, cache_path: Path, budget_s: int = 900, workers: int = 4):
        self.S = session
        self.path = cache_path
        self.budget = budget_s
        self.workers = workers
        c = _load(cache_path, {})
        if c.get("_v") != 3:
            c = {"_v": 3, "amcs": {}, "sd": {}}
        self.c = c
        self.stat = Counter()

    def _get(self, url, as_json=True, timeout=45):
        for k in range(3):
            try:
                r = self.S.get(url, timeout=timeout)
                if r.status_code == 200:
                    return r.json() if as_json else r.content.decode("utf-8-sig", errors="replace")
                if r.status_code == 404:
                    return None
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1.5 * (k + 1))
        self.stat["errors"] += 1
        return None

    # 1. scheme lists per fund house
    def refresh_amcs(self):
        if self.c.get("amcsTs") and _age(self.c["amcsTs"]) < REFRESH_DAYS and self.c["amcs"]:
            return

        def job(mid):
            j = self._get(f"{AMFI}/api/populate-scheme?MF_ID={mid}")
            lst = j.get("data", j) if isinstance(j, dict) else j
            return mid, [[str(x.get("scheme_id")), x.get("scheme_name", "")] for x in (lst or []) if x.get("scheme_id")]

        amcs = {}
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            for mid, lst in ex.map(job, range(1, MAX_MF_ID + 1)):
                if lst:
                    amcs[str(mid)] = lst
        if amcs:
            self.c["amcs"], self.c["amcsTs"] = amcs, date.today().isoformat()
        log.info("AMFI scheme lists: %d fund houses, %d schemes", len(amcs), sum(len(v) for v in amcs.values()))

    # 2. per-scheme detail
    def _fetch_sd(self, mid, sid):
        rec = {"ts": date.today().isoformat(), "mid": mid}
        d = self._get(f"{AMFI}/api/scheme-details?MF_ID={mid}&scheme_id={sid}")
        row = (d or {}).get("data", [None])[0] if isinstance(d, dict) else None
        if row:
            rec["details"] = {
                "name": row.get("Scheme_Name"), "objective": _clean(row.get("Scheme_Objective")),
                "load": _clean(row.get("Scheme_load"))[:1500], "category": row.get("SchemeCat_Desc"),
                "type": row.get("SchemeType_Desc"), "launch": (row.get("Launch_Date") or "")[:10],
                "minAmt": _clean(row.get("Scheme_min_amt"))[:200], "website": row.get("AMC_Website"),
                "amc": row.get("MF_Name"),
            }
        a = self._get(f"{AMFI}/api/scheme-data?strMFId={mid}&strSDId={sid}&strOption=AUM")
        rows = a if isinstance(a, list) else (a or {}).get("data", []) if isinstance(a, dict) else []
        if rows:
            tot, per = 0.0, {}
            q = ""
            for x in rows:
                try:
                    v = float(x.get("Average_AUM_For_The_Quarter") or 0)
                except (TypeError, ValueError):
                    v = 0.0
                tot += v
                per[f'{x.get("Plan", "")}|{x.get("Option", "")}'] = v
                q = x.get("As_At_The_End_Of") or q
            rec["aum"] = {"totalLakh": round(tot, 2), "quarter": q, "plans": per}
        x = self._get(f"{PORTAL}/spages/SSD_{sid}.xml", as_json=False)
        if x and re.search(r"<SchemeSummary|<root\b|<Workbook\b|<office:document\b", x[:4000]):
            rec["ssdXml"] = x          # kept raw so parsing improvements apply without refetching
        return sid, rec

    def run(self, universe: list[dict]) -> dict[int, dict]:
        t0 = time.time()
        self.refresh_amcs()
        by_name = defaultdict(list)
        for mid, lst in self.c["amcs"].items():
            for sid, name in lst:
                by_name[norm(name)].append((mid, sid))
        # which scheme ids do we need?
        want = {}
        for r in universe:
            for mid, sid in by_name.get(norm(r["name"]), []):
                want[sid] = mid
        # fuzzy fallback within the same fund house for names that differ slightly
        mid_of_amc = defaultdict(Counter)
        for r in universe:
            for mid, sid in by_name.get(norm(r["name"]), []):
                mid_of_amc[r["amc"]][mid] += 1
        unmatched = [r for r in universe if not by_name.get(norm(r["name"]))]
        for r in unmatched:
            mids = [m for m, _ in mid_of_amc[r["amc"]].most_common(2)]
            toks = set(re.findall(r"[a-z0-9]+", r["name"].lower())) - {"fund", "the", "plan", "scheme", "of"}
            best, best_s = None, 0.0
            for mid in mids:
                for sid, name in self.c["amcs"].get(mid, []):
                    t2 = set(re.findall(r"[a-z0-9]+", name.lower())) - {"fund", "the", "plan", "scheme", "of"}
                    if not t2:
                        continue
                    s = len(toks & t2) / len(toks | t2)
                    if s > best_s:
                        best, best_s = (mid, sid), s
            if best and best_s >= 0.75:
                want[best[1]] = best[0]
        sd = self.c["sd"]
        todo = [(mid, sid) for sid, mid in want.items() if sid not in sd or _age(sd[sid].get("ts")) >= REFRESH_DAYS]
        todo.sort(key=lambda x: (x[1] in sd, sd.get(x[1], {}).get("ts", "")))
        done = 0
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {}
            it = iter(todo)
            for _ in range(self.workers * 2):
                nxt = next(it, None)
                if nxt:
                    futs[ex.submit(self._fetch_sd, *nxt)] = nxt
            while futs:
                for fut in as_completed(list(futs)):
                    futs.pop(fut)
                    sid, rec = fut.result()
                    sd[sid] = rec          # stored even when empty, so missing schemes are retried weekly, not daily
                    done += 1
                    if time.time() - t0 < self.budget:
                        nxt = next(it, None)
                        if nxt:
                            futs[ex.submit(self._fetch_sd, *nxt)] = nxt
                    break
        _save(self.path, self.c)
        # map to scheme codes: ISIN from the summary document first, exact name second
        isin2sid, parsed = {}, {}
        for sid, rec in sd.items():
            if rec.get("ssdXml"):
                rec = dict(rec)
                rec["ssd"] = parse_ssd(rec["ssdXml"])
                parsed[sid] = rec
            for i in (rec.get("ssd") or {}).get("isins", []):
                isin2sid[i] = sid
        out, how = {}, Counter()
        for r in universe:
            sid = isin2sid.get(r["isin"])
            if sid:
                how["isin"] += 1
            else:
                cands = [s for m, s in by_name.get(norm(r["name"]), []) if s in sd]
                sid = cands[0] if len(cands) == 1 else None
                if sid:
                    how["name"] += 1
            if not sid:
                how["none"] += 1
                continue
            rec = parsed.get(sid) or sd[sid]
            out[r["code"]] = {"sid": sid, **{k: v for k, v in rec.items() if k != "ssdXml"}}
        log.info("Official scheme enrichment: %d fetched this run (%d pending), mapped %s, errors %d, %.0fs",
                 done, max(0, len(todo) - done), dict(how), self.stat["errors"], time.time() - t0)
        return out


# ═══════════════════════════════ TAXATION ═════════════════════════════════
# Indian capital-gains rules for mutual fund units bought on or after 1 Apr 2023
# (Finance (No. 2) Act 2024 rates, effective 23 Jul 2024; "specified mutual fund" definition as
# amended from 1 Apr 2025). Rates exclude surcharge and 4% health & education cess.
TAX_RULES_AS_OF = "Rules as amended by the Finance Acts 2024–2025 (rates from 23 Jul 2024)"
TAX = {
    "equity": {
        "label": "Equity-oriented fund",
        "stcg": "Held up to 12 months: 20% on gains",
        "ltcg": "Held over 12 months: 12.5% on gains above ₹1.25 lakh per financial year (across all equity-oriented funds & listed shares)",
        "note": "Securities Transaction Tax of 0.001% applies on redemption.",
    },
    "elss": {
        "label": "Equity-oriented fund (ELSS)",
        "stcg": "Not applicable — units are locked in for 3 years from each investment",
        "ltcg": "After the 3-year lock-in: 12.5% on gains above ₹1.25 lakh per financial year",
        "note": "Investments qualify for a deduction of up to ₹1.5 lakh a year under the old tax regime only.",
    },
    "debt": {
        "label": "Specified (debt-oriented) fund",
        "stcg": "Gains are added to your income and taxed at your slab rate, whatever the holding period",
        "ltcg": "No long-term rate or indexation benefit for units bought on or after 1 Apr 2023",
        "note": "Units bought before 1 Apr 2023 and held over 24 months: 12.5% without indexation.",
    },
    "other": {
        "label": "Other fund (non-equity, non-specified)",
        "stcg": "Held up to 24 months: taxed at your slab rate",
        "ltcg": "Held over 24 months: 12.5% without indexation",
        "note": "Applies to gold, silver and international fund-of-funds and hybrids that are neither equity-oriented nor debt-oriented.",
    },
}

EQUITY_SUBS = {"large", "largemid", "mid", "small", "multi", "flexi", "focused", "value", "contra", "divyield", "sector",
               "idx_large", "idx_midsmall", "idx_broad", "idx_factor", "idx_sector", "aggressive", "baf", "eqsavings",
               "arbitrage"}
DEBT_SUBS = {"overnight", "liquid", "ultrashort", "lowdur", "money", "shortdur", "meddur", "medlong", "longdur",
             "dynbond", "corpbond", "credit", "bankpsu", "gilt", "gilt10", "floater", "target", "debtfof", "conservative"}
OTHER_SUBS = {"gold", "silver", "multicomm", "us", "global", "asia", "globaldebt", "balanced"}


def tax_class(sub: str, alloc: list[dict] | None, name: str) -> str:
    if sub == "elss" or re.search(r"\belss\b|tax saver", name, re.I):
        return "elss"
    if sub in EQUITY_SUBS or sub.startswith(("sec_", "idx_")):
        return "equity"
    if sub in DEBT_SUBS:
        return "debt"
    if sub in OTHER_SUBS:
        return "other"
    # multi-asset, hybrid FoF, equity FoF, solution-oriented: decide from the stated asset allocation
    eq_min = max([a["min"] for a in alloc or [] if a["kind"] == "equity"] or [0])
    debt_min = max([a["min"] for a in alloc or [] if a["kind"] == "debt"] or [0])
    if sub == "eqfof":
        fund_min = max([a["min"] for a in alloc or [] if a["kind"] in ("fund", "equity")] or [0])
        return "equity" if fund_min >= 90 else "other"
    if eq_min >= 65:
        return "equity"
    if debt_min > 65:
        return "debt"
    if not alloc:
        return "equity" if sub in ("retire", "child") and not re.search(r"debt|hybrid|conservative", name, re.I) else "other"
    return "other"
