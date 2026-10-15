#!/usr/bin/env python3
"""
India Mutual Fund Screener — Phase 2: portfolio holdings, sector allocation and market-cap split.

Source: each fund house's SEBI-mandated monthly portfolio disclosure (published within 10 days of
month-end). A headless browser renders each disclosure page, the latest month's files are
downloaded, and a layout-agnostic parser reads every sheet that has ISIN and "% to net assets"
columns. Sheets are matched to funds in data/mf/screener.json by scheme name within the fund house.

Outputs:
  data/mf/p/<sub>.json   — per fund: holdings (top 15), sector split, market-cap split, asset mix
  data/mf/p/_meta.json   — per fund house: portfolio month processed, files, funds matched

Market-cap buckets: Nifty 100 constituents = large cap, Nifty Midcap 150 = mid cap, other listed
Indian equities = small cap (the same 1–100 / 101–250 / 251+ ranking SEBI uses).
"""
from __future__ import annotations

import io
import json
import logging
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mf_enrich as E  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mf" / "p"
CACHE = ROOT / ".mfcache" / "holdings"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("hold")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# fund house (as named in screener.json "amcs") → disclosure page + link filter
SOURCES = {
    "SBI": {"page": "https://www.sbimf.com/portfolios",
            "pick": r"all-schemes-monthly-portfolio"},
    "Nippon India": {"page": "https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures",
                     "pick": r"NIMF-MONTHLY-PORTFOLIO"},
    "Aditya Birla Sun Life": {"page": "https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio",
                              "pick": r"monthly-portfolio/|monthlydisclosure|monthly_portfolio"},
    "Mirae Asset": {"page": "https://www.miraeassetmf.co.in/downloads/portfolio",
                    "pick": r"/portfolios/[a-z0-9]+_[a-z]{3,9}\d{4}\.xlsx", "multi": True},
    "DSP": {"page": "https://www.dspim.com/mandatory-disclosures/portfolio-disclosures",
            "pick": r"month[-_]?end[-_]portfolio|monthly[-_]portfolio", "skip": r"isin-debt|fortnight|half-yearly"},
    "Tata": {"page": "https://www.tatamutualfund.com/schemes-related/portfolio",
             "pick": r"Monthly%20Portfolio|monthly-portfolio"},
    "PPFAS": {"page": "https://amc.ppfas.com/downloads/portfolio-disclosure/",
              "pick": r"PPFAS_Monthly_Portfolio_Report_[A-Za-z]+_\d+_\d{4}\.xls|_PPFAS_Monthly_Portfolio_Report_", "multi": True},
}
SKIP_DEFAULT = r"fortnight|debt-portfolio|risk-param|half|annual|commission|aaum|votes|riskometer|weblink"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def link_month(url: str) -> tuple[int, int] | None:
    """Best-effort (year, month) of a portfolio file from its URL."""
    u = requests.utils.unquote(url).lower()
    m = re.search(r"(\d{1,2})[-_ ]?(?:st|nd|rd|th)?[-_ ]*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_ ,]*(\d{2,4})", u)
    if m:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        return y, MONTHS[m.group(2)]
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_ ]*(?:\d{1,2}[-_ ]*)?(\d{4})", u)
    if m:
        return int(m.group(2)), MONTHS[m.group(1)]
    m = re.search(r"(\d{2})(\d{2})(20\d{2})", u)            # 30092026
    if m and 1 <= int(m.group(2)) <= 12:
        return int(m.group(3)), int(m.group(2))
    m = re.search(r"(20\d{2})-(\d{2})/", u)                 # /2026-10/ upload folder → previous month
    if m:
        y, mo = int(m.group(1)), int(m.group(2)) - 1
        return (y, mo) if mo else (y - 1, 12)
    return None


def discover(sources: dict) -> dict[str, list[str]]:
    from playwright.sync_api import sync_playwright
    found = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(user_agent=UA, locale="en-IN", accept_downloads=True)
        for amc, cfg in sources.items():
            links = []
            try:
                p = ctx.new_page()
                p.goto(cfg["page"], wait_until="networkidle", timeout=90000)
                p.wait_for_timeout(2500)
                links = p.eval_on_selector_all("a", "as => as.map(a => a.href)")
                p.close()
            except Exception as e:  # noqa: BLE001
                log.warning("%s: page not reachable (%s)", amc, str(e)[:120])
                continue
            allx = [l for l in dict.fromkeys(links) if re.search(r"\.(xlsx?|zip|xlsm)(\?|#|$)", l, re.I)]
            links = [l for l in allx if re.search(cfg["pick"], l, re.I)
                     and not re.search(cfg.get("skip", SKIP_DEFAULT), l, re.I)]
            dated = [(link_month(l), l) for l in dict.fromkeys(links)]
            dated = [(d, l) for d, l in dated if d]
            if not dated:
                log.warning("%s: no dated portfolio files found (%d candidate links)", amc, len(links))
                for l in allx[:15]:
                    log.warning("    %s", l[:160])
                continue
            latest = max(d for d, _ in dated)
            pick = [l for d, l in dated if d == latest]
            if not cfg.get("multi"):
                pick = pick[:1]
            found[amc] = {"month": f"{latest[0]}-{latest[1]:02d}", "files": pick}
            log.info("%s: %s · %d file(s)", amc, found[amc]["month"], len(pick))
        b.close()
    return found


# ═════════════════════════════ PARSING ═════════════════════════════════════
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
PCT_HDR = re.compile(r"%\s*(to|of)\s*(the\s*)?(net\s*assets?|nav|aum|net\s*asset\s*value)|%\s*to\s*net|percentage\s*(to|of)|% of nav|\bnav\s*%|% to aum", re.I)
NAME_HDR = re.compile(r"name\s*of\s*(the\s*)?(instrument|security|issuer|company)|instrument|security\s*name|company|issuer|particulars|^name$", re.I)
IND_HDR = re.compile(r"industry|sector|rating", re.I)


def read_book(blob: bytes, fname: str):
    """Yield (sheet_name, rows) for xls / xlsx content."""
    if fname.lower().endswith((".xlsx", ".xlsm")) or blob[:2] == b"PK":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = []
            for i, r in enumerate(ws.iter_rows(values_only=True)):
                rows.append(list(r))
                if i > 1500:
                    break
            yield ws.title, rows
    else:
        import xlrd
        wb = xlrd.open_workbook(file_contents=blob)
        for sh in wb.sheets():
            yield sh.name, [sh.row_values(i) for i in range(min(sh.nrows, 1500))]


def _s(v):
    return str(v).strip() if v is not None else ""


def parse_sheet(name: str, rows: list[list]) -> list[dict]:
    """A sheet may hold one or several schemes. Returns [{title, holdings:[{name,isin,ind,pct}]}]."""
    out, cur, hdr = [], None, None
    titles = []
    for i, row in enumerate(rows):
        cells = [_s(c) for c in row]
        line = " ".join(c for c in cells if c)
        if not line:
            continue
        # header row?
        if any(re.search(r"\bisin\b", c, re.I) for c in cells) and any(PCT_HDR.search(c) for c in cells):
            isin_c = next(j for j, c in enumerate(cells) if re.search(r"\bisin\b", c, re.I))
            pct_c = next(j for j, c in enumerate(cells) if PCT_HDR.search(c))
            name_c = next((j for j, c in enumerate(cells) if NAME_HDR.search(c) and j != isin_c), max(0, isin_c - 1))
            ind_c = next((j for j, c in enumerate(cells) if IND_HDR.search(c)), None)
            hdr = (name_c, isin_c, ind_c, pct_c)
            title = next((t for t in reversed(titles[-6:]) if re.search(r"fund|scheme|plan|etf|fof", t, re.I)), name)
            cur = {"title": title, "holdings": []}
            out.append(cur)
            titles = []
            continue
        # title-like line (scheme name banners appear above each header)
        if len(line) < 220 and re.search(r"fund|scheme|plan|portfolio|etf", line, re.I) and not any(ISIN.match(c) for c in cells):
            titles.append(re.sub(r"(?i)^(scheme\s*name|name of the scheme)\s*[:\-]\s*", "", next(c for c in cells if c)))
        if not hdr or not cur:
            continue
        name_c, isin_c, ind_c, pct_c = hdr
        isin = cells[isin_c] if isin_c < len(cells) else ""
        if not ISIN.match(isin.upper()):
            continue
        try:
            pct = float(str(row[pct_c]).replace("%", "").replace(",", "").strip())
        except (ValueError, TypeError, IndexError):
            continue
        cur["holdings"].append({"name": cells[name_c] if name_c < len(cells) else "", "isin": isin.upper(),
                                "ind": cells[ind_c] if ind_c is not None and ind_c < len(cells) else "", "pct": pct})
    # scale: some files report 0.0512 for 5.12 %
    for blk in out:
        tot = sum(h["pct"] for h in blk["holdings"])
        if 0 < tot <= 1.6:
            for h in blk["holdings"]:
                h["pct"] *= 100
    return [b for b in out if len(b["holdings"]) >= 1]


def classify_holding(h: dict) -> str:
    i = h["isin"]
    if i.startswith("INE") and i[7:9] == "01":
        return "equity"
    if i.startswith("INF"):
        return "fund"
    if not i.startswith("IN"):
        return "overseas"
    if re.search(r"reit|invit|trust", h["name"], re.I) and not re.search(r"bank|finance", h["name"], re.I):
        return "reit"
    return "debt"


def cap_sets(session) -> tuple[set, set]:
    """ISINs of Nifty 100 (large) and Nifty Midcap 150 (mid) constituents."""
    large, mid = set(), set()
    for url, bucket in (("https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv", large),
                        ("https://www.niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv", mid),
                        ("https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv", large),
                        ("https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv", mid)):
        if bucket:
            continue
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 200 and "ISIN" in r.text[:400]:
                bucket.update(re.findall(r"INE[A-Z0-9]{9}", r.text))
        except Exception:  # noqa: BLE001
            pass
    log.info("Market-cap lists: %d large, %d mid", len(large), len(mid))
    return large, mid


def summarise(blk: dict, large: set, mid: set) -> dict:
    hs = [h for h in blk["holdings"] if h["pct"] > -50]
    kinds = defaultdict(float)
    for h in hs:
        h["kind"] = classify_holding(h)
        kinds[h["kind"]] += h["pct"]
    listed = sum(kinds.values())
    eq = [h for h in hs if h["kind"] == "equity"]
    sectors = defaultdict(float)
    for h in eq:
        sec = re.sub(r"\s+", " ", h["ind"] or "Others").strip().title() or "Others"
        sectors[sec] += h["pct"]
    cap = {"large": 0.0, "mid": 0.0, "small": 0.0}
    if large or mid:
        for h in eq:
            cap["large" if h["isin"] in large else "mid" if h["isin"] in mid else "small"] += h["pct"]
    top = sorted(hs, key=lambda h: -h["pct"])[:15]
    return {
        "n": len(eq), "nAll": len(hs),
        "mix": {k: round(v, 2) for k, v in kinds.items()} | {"cashOther": round(max(0.0, 100 - listed), 2)},
        "top": [[h["name"][:80], h["ind"][:50], round(h["pct"], 2), h["isin"], h["kind"]] for h in top],
        "top10": round(sum(h["pct"] for h in sorted(eq, key=lambda h: -h["pct"])[:10]), 2),
        "sectors": sorted([[k, round(v, 2)] for k, v in sectors.items()], key=lambda x: -x[1])[:14],
        "cap": {k: round(v, 2) for k, v in cap.items()} if (large or mid) and eq else None,
    }


def tokens(n: str) -> set:
    n = re.sub(r"\(.*?\)", " ", n.lower()).replace("&", " and ")
    stop = {"fund", "the", "plan", "scheme", "of", "an", "open", "ended", "direct", "growth", "regular", "option",
            "portfolio", "monthly", "statement", "as", "on", "mutual", "india", "formerly", "known", "erstwhile"}
    return {t for t in re.findall(r"[a-z0-9]+", n) if t not in stop and not re.fullmatch(r"\d{1,2}|20\d\d|19\d\d", t)}


def match_blocks(blocks: list[dict], funds: list[dict]) -> dict[int, dict]:
    """Map parsed blocks to fund codes by token overlap with the AMFI scheme name."""
    out = {}
    ft = [(f, tokens(f["amfi"])) for f in funds]
    for blk in blocks:
        bt = tokens(blk["title"])
        if not bt:
            continue
        best, best_s, second = None, 0.0, 0.0
        for f, t in ft:
            if not t:
                continue
            s = len(bt & t) / len(bt | t)
            if s > best_s:
                best, best_s, second = f, s, best_s
            elif s > second:
                second = s
        if best and best_s >= 0.6 and best_s - second >= 0.08:
            # the first (largest) block wins if a scheme appears twice
            out.setdefault(best["code"], blk)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    scr = json.load(open(ROOT / "data" / "mf" / "screener.json"))
    C = {c: i for i, c in enumerate(scr["cols"])}
    det = {}
    for f in (ROOT / "data" / "mf" / "d").glob("*.json"):
        det.update(json.load(open(f)))
    funds_by_amc = defaultdict(list)
    sub_of = {}
    for r in scr["rows"]:
        amc = scr["amcs"][r[C["amc"]]]
        code = r[C["code"]]
        sub_of[code] = r[C["sub"]]
        funds_by_amc[amc].append({"code": code, "amfi": (det.get(str(code)) or {}).get("info", {}).get("amfiName") or r[C["name"]]})
    meta_path = OUT / "_meta.json"
    meta = json.load(open(meta_path)) if meta_path.exists() else {}
    S = requests.Session()
    S.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})
    found = discover({k: v for k, v in SOURCES.items() if k in funds_by_amc})
    large, mid = cap_sets(S)
    results, report = {}, {}
    for amc, info in found.items():
        if meta.get(amc, {}).get("month") == info["month"] and meta[amc].get("funds", 0) > 0 and "--force" not in sys.argv:
            log.info("%s: %s already processed", amc, info["month"])
            continue
        blocks = []
        for url in info["files"]:
            try:
                r = S.get(url, timeout=120, headers={"Referer": SOURCES[amc]["page"]})
                r.raise_for_status()
            except Exception as e:  # noqa: BLE001
                log.warning("%s: download failed %s (%s)", amc, url[:100], e)
                continue
            payloads = []
            if r.content[:2] == b"PK" and url.lower().split("?")[0].endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    for n in z.namelist():
                        if re.search(r"\.(xlsx?|xlsm)$", n, re.I) and not re.search(SKIP_DEFAULT, n, re.I):
                            payloads.append((n, z.read(n)))
            else:
                payloads.append((url.split("?")[0].rsplit("/", 1)[-1], r.content))
            for fname, blob in payloads:
                try:
                    for sname, rows in read_book(blob, fname):
                        for blk in parse_sheet(sname, rows):
                            blk["file"] = fname
                            blocks.append(blk)
                except Exception as e:  # noqa: BLE001
                    log.warning("%s: could not read %s (%s)", amc, fname, str(e)[:120])
            time.sleep(0.5)
        matched = match_blocks(blocks, funds_by_amc[amc])
        hit = {id(b) for b in matched.values()}
        report[amc] = {"files": [u.split("?")[0].rsplit("/", 1)[-1] for u in info["files"]],
                       "unmatched": sorted({b["title"][:90] for b in blocks if id(b) not in hit})[:60],
                       "matched": {str(c): b["title"][:90] for c, b in matched.items()}}
        bad = 0
        for code, blk in matched.items():
            sm = summarise(blk, large, mid)
            listed = 100 - sm["mix"]["cashOther"]
            if listed < 40 or listed > 130:          # sanity: a portfolio should add up to ~100 %
                bad += 1
                continue
            sm["asOf"] = info["month"]
            results[code] = sm
        meta[amc] = {"month": info["month"], "files": len(info["files"]), "blocks": len(blocks),
                     "funds": len(matched) - bad, "rejected": bad, "updated": date.today().isoformat()}
        log.info("%s: %d sheet blocks parsed, %d funds matched, %d rejected by sanity checks",
                 amc, len(blocks), len(matched) - bad, bad)
    # merge into per-sub files (keep other fund houses' last good data)
    by_sub = defaultdict(dict)
    for p in OUT.glob("*.json"):
        if p.name.startswith("_"):
            continue
        for code, v in json.load(open(p)).items():
            if int(code) in sub_of:
                by_sub[sub_of[int(code)]][code] = v
    for code, v in results.items():
        by_sub[sub_of[code]][str(code)] = v
    for sub, d in by_sub.items():
        (OUT / f"{sub}.json").write_text(json.dumps(d, separators=(",", ":"), ensure_ascii=False))
    meta["_generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["_funds"] = sum(len(d) for d in by_sub.values())
    meta_path.write_text(json.dumps(meta, indent=1))
    (CACHE / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    log.info("Holdings available for %d funds", meta["_funds"])


if __name__ == "__main__":
    main()
