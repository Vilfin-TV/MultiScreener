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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mf_enrich as E  # noqa: E402
import mf_fundpages as FP  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mf" / "p"
CACHE = ROOT / ".mfcache" / "holdings"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("hold")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# fund house (as named in screener.json "amcs") → disclosure page + link filter
# fund houses whose monthly portfolio is read from each fund's own page (no machine-readable monthly file)
PAGE_SOURCES = {"Trust": "trust", "PGIM India": "pgim", "Baroda BNP Paribas": "dom"}
# fund-page tables can be truncated: an equity fund must show ≥90 % invested (index funds ≥95 %) to be used
PAGE_MIN_LISTED = {"index": 95.0, "equity": 90.0}
EQUITY_SUBS = {"large", "largemid", "mid", "small", "multi", "flexi", "focused", "value", "contra", "elss", "dividend"}
SKIP_DEFAULT = r"fortnight|debt-portfolio|risk-param|half|annual|commission|aaum|votes|riskometer|weblink"
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
    "Invesco": {"page": "https://www.invescomutualfund.com/literature-forms/monthly-holdings/equity", "mode": "invesco", "multi": True},
    "Groww": {"page": "https://www.growwmf.in/statutory-disclosure/portfolio",
              "pick": r"Statutory(?:%20| )Disclosure/Portfolio/.*Monthly(?:%20| )?Portfolio", "multi": True},
    "ICICI Prudential": {"page": "https://www.icicipruamc.com/media-center/downloads?currentTabFilter=OtherSchemeDisclosures&&subCatTabFilter=Monthly%20Portfolio%20Disclosures",
                         "mode": "click", "click": r"monthly\s+portfolio\s+disclosure\s+{month}\s+{year}"},
    "HDFC": {"page": "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio",
             "pick": r"hdfcfund\.com/.*Monthly", "skip": r"fortnight|overlap|half", "multi": True},
    "PPFAS": {"page": "https://amc.ppfas.com/downloads/portfolio-disclosure/",
              "pick": r"PPFAS_Monthly_Portfolio_Report_[A-Za-z]+_\d+_\d{4}\.xls|_PPFAS_Monthly_Portfolio_Report_", "multi": True},
    "Abakkus": {"page": "https://www.abakkusmf.com/statutory-disclosures.html",
                "pick": r"monthly[_-]?port(?:f)?olio", "skip": SKIP_DEFAULT + r"|overlap", "multi": True},
    "Capitalmind": {"page": "https://capitalmindmf.com/statutory-disclosures.html",
                    "pick": r"Monthly_Portfolio_Disclosure", "multi": True},
    "Old Bridge": {"page": "https://www.oldbridgemf.com/statutory-disclosures.html",
                   "pick": r"OBMF_.+_Portfolio_", "skip": SKIP_DEFAULT + r"|overlap", "multi": True},
    "JM Financial": {"page": "https://www.jmfinancialmf.com/downloads/Portfolio-Disclosure",
                     "pick": r"Monthly(?:%20| )Portfolio", "multi": True},
    "Shriram": {"page": "https://www.shriramamc.in/investor-statutory-disclosures",
                "pick": r"/Monthly-Portfolio-Shriram[^/]*$", "skip": r"half|annual|aaum", "multi": True},
    "Samco": {"page": "https://www.samcomf.com/StatutoryDisclosure",
              "pick": r"Portfolio[_-]Monthly|Monthly[_-]Portfolio", "multi": True},
    "Helios": {"page": "https://www.heliosmf.in/portfolio-disclosure/",
               "pick": r"monthly[-_]portfolio|portfolio[-_]as[-_]on", "skip": SKIP_DEFAULT + r"|overlap", "multi": True},
    "HSBC": {"page": "https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library",
             "pick": r"/mutual-funds/portfolios/document-\d{8}/", "multi": True},
    "360 ONE": {"page": "https://www.360.one/asset/mutual-funds/downloads/",
                "pick": r"monthly[-_ ]?portfolio|portfolio[-_ ]?monthly", "multi": True},
    "Motilal Oswal": {"page": "https://www.motilaloswalmf.com/downloads/scheme-portfolio-details",
                      "pick": r"month-end-portfolio/.*scheme(?:%20| |-|_)portfolio(?:%20| |-|_)details", "skip": SKIP_DEFAULT + r"|copy"},
    "Bank of India": {"page": "https://www.boimf.in/investor-corner#t2",
                      "pick": r"/investorcorner/monthly-portfolio/monthly-portfolio"},
    # file names carry no date: the portfolio month is read from inside each file (date: content)
    "Quantum": {"page": "https://www.quantumamc.com/portfolio/combined/-1/1/0/0", "pick": r"/FileCDN/FactSheet/", "date": "content", "scan": 4},
    "The Wealth Company": {"page": "https://www.wealthcompanyamc.in/literature-forms/portfolio-documents/monthly/",
                           "pick": r"/uploads/Monthly_Portfolio_", "date": "content", "scan": 30, "multi": True},
}
# a matched portfolio must fit the fund's category (same rule as verify) — otherwise it is skipped, not published
FIT_EQUITY = {"large", "largemid", "mid", "small", "multi", "flexi", "focused", "value", "contra", "elss", "dividend",
              "idx_large", "idx_midsmall", "idx_broad", "idx_factor", "idx_sector"}
FIT_DEBT = {"overnight", "liquid", "money", "ultrashort", "lowdur", "shortdur", "meddur", "medlong", "longdur", "dynbond",
            "corpbond", "credit", "bankpsu", "gilt", "gilt10", "floater", "target", "debtidx"}


def fits_category(sub: str, mix: dict) -> bool:
    eq = (mix.get("equity") or 0) + (mix.get("overseas") or 0) + (mix.get("reit") or 0)
    if sub in FIT_EQUITY or re.match(r"(sec_|idx_)", sub or ""):
        return eq >= 60
    if sub in FIT_DEBT:
        return (mix.get("equity") or 0) <= 5
    return True


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


MAX_AGE_DAYS = 45      # a portfolio is shown for at most 45 days after its month-end (~1.5 months)


def pf_age_days(month: str, today: date | None = None) -> int:
    """Days from the end of a portfolio month ("YYYY-MM") to today."""
    y, m = map(int, month.split("-"))
    end = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return ((today or date.today()) - end).days


def expected_month(today: date | None = None) -> str:
    """Latest portfolio month every fund house should have published (fund houses publish within 10 days)."""
    t = today or date.today()
    y, m = t.year, t.month - (1 if t.day >= 11 else 2)
    while m < 1:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


def link_month(url: str) -> tuple[int, int] | None:
    """Best-effort (year, month) of a portfolio file from its URL (implausible years are ignored)."""
    u = requests.utils.unquote(url).lower()
    ok = lambda y, mo: 2015 <= y <= date.today().year and 1 <= mo <= 12 and (y, mo) <= (date.today().year, date.today().month)
    M = "(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
    for m in re.finditer(r"(\d{1,2})[-_ ]?(?:st|nd|rd|th)?[-_ ]*" + M + r"[-_ ,.]*(\d{4}|\d{2})(?!\d)", u):
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        if ok(y, MONTHS[m.group(2)]):
            return y, MONTHS[m.group(2)]
    for m in re.finditer(M + r"[-_ ,.]*(?:\d{1,2}(?:st|nd|rd|th)?[-_ ,.]+)?(\d{4})(?!\d)", u):
        if ok(int(m.group(2)), MONTHS[m.group(1)]):
            return int(m.group(2)), MONTHS[m.group(1)]
    for m in re.finditer(M + r"[-_ ,.']*(\d{2})(?![\d])", u):          # Sept_26 · Jun'26
        y = 2000 + int(m.group(2))
        if ok(y, MONTHS[m.group(1)]):
            return y, MONTHS[m.group(1)]
    for m in re.finditer(r"(\d{2})[.\-_]?(\d{2})[.\-_]?(20\d{2})", u):       # 30092026 · 31.01.2026
        if ok(int(m.group(3)), int(m.group(2))):
            return int(m.group(3)), int(m.group(2))
    m = re.search(r"(20\d{2})-(\d{2})/", u)                 # /2026-10/ upload folder → previous month
    if m:
        y, mo = int(m.group(1)), int(m.group(2)) - 1
        return (y, mo) if mo else (y - 1, 12)
    return None


FILE_RX = re.compile(r"""(?:https?://[^\s"'<>\\]+?|/[^\s"'<>\\]+?)\.(?:xlsx|xls|zip|xlsm)(?:\?[^\s"'<>\\]*)?""", re.I)


def harvest(ctx, url: str) -> list[str]:
    """Render a page and collect every spreadsheet/zip URL from links, page source and data responses."""
    from urllib.parse import urljoin
    found = []
    p = ctx.new_page()

    def on_resp(r):
        try:
            if FILE_RX.search(r.url):
                found.append(r.url)
            if "json" in r.headers.get("content-type", ""):
                body = r.text().replace("\\/", "/")
                found.extend(m for m in FILE_RX.findall(body) if m.startswith("http"))
        except Exception:  # noqa: BLE001
            pass
    p.on("response", on_resp)
    try:
        p.goto(url, wait_until="domcontentloaded", timeout=90000)
        try:
            p.wait_for_load_state("networkidle", timeout=20000)
        except Exception:  # noqa: BLE001
            pass
        p.wait_for_timeout(3000)
        for _ in range(3):
            p.mouse.wheel(0, 2500)
            p.wait_for_timeout(500)
        found.extend(p.eval_on_selector_all("a", "as => as.map(a => a.href)"))
        found.extend(urljoin(p.url, m) for m in FILE_RX.findall(p.content()))
    finally:
        p.close()
    return [f.replace("&amp;", "&") for f in found]


MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
               "november", "december"]


def recent_months(n: int = 3) -> list[tuple[int, int]]:
    t = date.today()
    y, m = t.year, t.month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append((y, m))
    return out


def invesco_files(ctx, cfg) -> dict | None:
    """Invesco lists each scheme's complete monthly holdings per calendar month in a JSON feed."""
    p = ctx.new_page()
    try:
        p.goto(cfg["page"], wait_until="domcontentloaded", timeout=90000)
        p.wait_for_timeout(4000)
        for y, m in recent_months(3):
            key = MONTH_NAMES[m - 1][:3].title() + "Url"
            files = []
            for cls in ("equity", "hybrid", "debt", "fixed-income", "others", "fof", "index"):
                r = ctx.request.get(f"https://www.invescomutualfund.com/api/CompleteMonthlyHoldings?year={y}&classification={cls}",
                                    headers={"Referer": cfg["page"]}, timeout=60000)
                if not r.ok:
                    continue
                try:
                    rows = r.json()
                except Exception:  # noqa: BLE001
                    continue
                for row in rows if isinstance(rows, list) else []:
                    u = (row.get(key) or "").strip()
                    if u:
                        # the scheme name travels with the URL so the parser can match opaque file names
                        files.append(u + ("&" if "?" in u else "?") + "_scheme=" + requests.utils.quote(str(row.get("Name", "")).strip()))
            if files:
                return {"month": f"{y}-{m:02d}", "files": list(dict.fromkeys(files))}
    finally:
        p.close()
    return None


def click_download(ctx, cfg) -> dict | None:
    """Some fund houses serve the monthly file only through a click-triggered download."""
    p = ctx.new_page()
    try:
        p.goto(cfg["page"], wait_until="domcontentloaded", timeout=90000)
        try:
            p.wait_for_load_state("networkidle", timeout=20000)
        except Exception:  # noqa: BLE001
            pass
        p.wait_for_timeout(4000)
        for y, m in recent_months(3):
            rx = re.compile(cfg["click"].format(month=MONTH_NAMES[m - 1], year=y), re.I)
            loc = p.get_by_text(rx)
            if not loc.count():
                continue
            for el in loc.all()[:3]:
                try:
                    with p.expect_download(timeout=90000) as dl:
                        el.click(force=True, timeout=8000)
                    d = dl.value
                    path = CACHE / f"dl_{y}{m:02d}_{re.sub(r'[^A-Za-z0-9._-]', '_', d.suggested_filename)}"
                    d.save_as(str(path))
                    return {"month": f"{y}-{m:02d}", "files": [path.as_uri()]}
                except Exception as e:  # noqa: BLE001
                    log.info("click download attempt failed: %s", str(e)[:120])
    finally:
        p.close()
    return None


def browser(pw):
    """A real (headed) browser when a display is available — some fund-house sites refuse headless clients."""
    import os
    b = pw.chromium.launch(headless=not os.environ.get("DISPLAY"), args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, locale="en-IN", viewport={"width": 1366, "height": 900}, accept_downloads=True)
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return b, ctx


def browser_fetch(items: list[tuple[str, str]]) -> dict[str, bytes]:
    """Download files through the browser (after visiting the referring page) when plain requests are refused."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as pw:
        b, ctx = browser(pw)
        seen = set()
        for url, ref in items:
            try:
                if ref not in seen:
                    seen.add(ref)
                    pg = ctx.new_page()
                    pg.goto(ref, wait_until="domcontentloaded", timeout=90000)
                    pg.wait_for_timeout(4000)
                    pg.close()
                r = ctx.request.get(url, headers={"Referer": ref}, timeout=120000)
                if r.ok and r.body().startswith((b"PK", b"\xd0\xcf\x11\xe0")):
                    out[url] = r.body()
            except Exception as e:  # noqa: BLE001
                log.warning("browser download failed %s (%s)", url[:100], str(e)[:100])
        b.close()
    return out


DATE_TXT = re.compile(r"(?:(\d{1,2})(?:st|nd|rd|th)?[\s\-/,.]*)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-/,.']*(?:(\d{1,2})(?:st|nd|rd|th)?,?\s+)?(20\d{2})", re.I)
DATE_NUM = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b")


def content_month(blob: bytes, fname: str) -> tuple[int, int] | None:
    """Portfolio month written inside a file ("as on 30 September 2026", "period ended 30/09/2026") —
    the most frequent plausible month in the first lines of each sheet."""
    seen = Counter()
    today = date.today()
    try:
        for _, rows in read_book(blob, fname):
            for row in rows[:12]:
                line = " ".join(_s(c) for c in row if c is not None)
                for m in DATE_TXT.finditer(line):
                    y, mo = int(m.group(4)), MONTHS[m.group(2).lower()[:3]]
                    if (y, mo) <= (today.year, today.month) and y >= today.year - 2:
                        seen[(y, mo)] += 1
                for m in DATE_NUM.finditer(line):
                    y, mo = int(m.group(3)), int(m.group(2))
                    if 1 <= mo <= 12 and (y, mo) <= (today.year, today.month) and y >= today.year - 2:
                        seen[(y, mo)] += 1
                for c in row:                                    # real date cells
                    if isinstance(c, datetime) and today.year - 2 <= c.year and (c.year, c.month) <= (today.year, today.month):
                        seen[(c.year, c.month)] += 1
    except Exception:  # noqa: BLE001
        return None
    return max(seen, key=lambda k: (seen[k], k)) if seen else None


def content_dated(ctx, cfg, links: list[str]) -> dict | None:
    """Download the first few candidate files (pages list newest first) and date each from its contents."""
    dated = []
    for l in links[: cfg.get("scan", 6)]:
        try:
            r = ctx.request.get(l, headers={"Referer": cfg["page"]}, timeout=120000)
            if not r.ok:
                continue
            ym = content_month(r.body(), l.split("?")[0])
        except Exception as e:  # noqa: BLE001
            log.warning("content date failed %s (%s)", l[:100], str(e)[:100])
            continue
        if ym:
            dated.append((ym, l))
    if not dated:
        return None
    latest = max(d for d, _ in dated)
    pick = [l for d, l in dated if d == latest]
    return {"month": f"{latest[0]}-{latest[1]:02d}", "files": pick if cfg.get("multi") else pick[:1]}


def discover(sources: dict) -> dict[str, list[str]]:
    from playwright.sync_api import sync_playwright
    found = {}
    with sync_playwright() as pw:
        b, ctx = browser(pw)
        for amc, cfg in sources.items():
            if cfg.get("mode") in ("invesco", "click"):
                try:
                    got = (invesco_files if cfg["mode"] == "invesco" else click_download)(ctx, cfg)
                except Exception as e:  # noqa: BLE001
                    got = None
                    log.warning("%s: discovery failed (%s)", amc, str(e)[:160])
                if got:
                    found[amc] = got
                    log.info("%s: %s · %d file(s)", amc, got["month"], len(got["files"]))
                else:
                    log.warning("%s: no portfolio files found", amc)
                continue
            links = []
            for page in cfg.get("pages") or [cfg["page"]]:
                try:
                    links += harvest(ctx, page)
                except Exception as e:  # noqa: BLE001
                    log.warning("%s: page not reachable (%s)", amc, str(e)[:120])
            allx = [l for l in dict.fromkeys(links) if re.search(r"\.(xlsx?|zip|xlsm)(\?|#|$)", l, re.I)]
            links = [l for l in allx if re.search(cfg["pick"], l, re.I)
                     and not re.search(cfg.get("skip", SKIP_DEFAULT), l, re.I)]
            if cfg.get("date") == "content":
                got = content_dated(ctx, cfg, links) if links else None
                if got:
                    found[amc] = got
                    log.info("%s: %s · %d file(s) (dated from contents)", amc, got["month"], len(got["files"]))
                else:
                    log.warning("%s: no dated portfolio files found (%d candidate links)", amc, len(links))
                continue
            dated = [(link_month(l), l) for l in links]
            dated = [(d, l) for d, l in dated if d]
            if not dated:
                log.warning("%s: no dated portfolio files found (%d spreadsheet links)", amc, len(allx))
                for l in allx[:15]:
                    log.warning("    %s", l[:160])
                continue
            latest = max(d for d, _ in dated)
            pick = list({l.split("?")[0].lower(): l for d, l in dated if d == latest}.values())
            if not cfg.get("multi"):
                host = re.sub(r"^https?://([^/]+).*", r"\1", (cfg.get("pages") or [cfg["page"]])[0])
                pick = sorted(pick, key=lambda l: host not in l)[:1]      # prefer the fund house's own domain
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
    """A sheet may hold one or several schemes. Returns [{title, ctx, holdings:[{name,isin,ind,pct}]}].
    `ctx` keeps the lines just above each table header (scheme name banners), plus the sheet name."""
    out, cur, hdr = [], None, None
    recent: list[str] = []
    for row in rows:
        cells = [_s(c) for c in row]
        line = " ".join(c for c in cells if c)
        if not line:
            continue
        if any(re.search(r"\bisin\b", c, re.I) for c in cells) and any(PCT_HDR.search(c) for c in cells):
            isin_c = next(j for j, c in enumerate(cells) if re.search(r"\bisin\b", c, re.I))
            pct_c = next(j for j, c in enumerate(cells) if PCT_HDR.search(c))
            name_c = next((j for j, c in enumerate(cells) if NAME_HDR.search(c) and j != isin_c), max(0, isin_c - 1))
            ind_c = next((j for j, c in enumerate(cells) if IND_HDR.search(c)), None)
            hdr = (name_c, isin_c, ind_c, pct_c)
            ctx = [l for l in reversed(recent[-10:])] + [name]
            if cur is not None and not any(re.search(r"fund|scheme|etf|fof|plan", l, re.I) for l in recent):
                # a second table (e.g. unlisted / debt section) of the same scheme: keep adding to it
                recent = []
                continue
            title = next((t for t in ctx if re.search(r"fund|scheme|plan|etf|fof", t, re.I)
                          and not re.match(r"\W*an\s+open", t, re.I)), name)
            cur = {"title": title, "ctx": ctx, "holdings": []}
            out.append(cur)
            recent = []
            continue
        if not any(ISIN.match(c.upper()) for c in cells):
            if len(line) < 400:
                recent.append(line)
            continue
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
    if (re.search(r"reit\b|invit\b|real\s*estate|infrastructure\s*investment|infra(structure)?\s*trust|\btrust\b", h["name"], re.I)
            and not re.search(r"securiti[sz]ation|\bptc\b|pass\s*through|series|bank|financ|\d{1,2}\.\d+\s*%", h["name"], re.I)):
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


NOTE_MARKS = re.compile(r"[\s\^£$#*@~†‡]+$")


def credit_bucket(rating: str) -> str:
    r = rating.upper()
    if re.search(r"SOV|GOVERNMENT|G-?SEC|T-?BILL|SDL|GOI", r):
        return "Sovereign"
    if re.search(r"A1\+|A1 ?\+", r):
        return "A1+ (money market)"
    if re.search(r"\bAAA", r):
        return "AAA & equivalent"
    if re.search(r"\bAA[+-]?\b|\bAA[+-]?\(", r):
        return "AA"
    if re.search(r"\bA[+-]?\b|\bBBB|\bBB|\bD\b|\bA2|\bA3", r):
        return "A & below"
    return "Unrated / others"


def summarise(blk: dict, large: set, mid: set) -> dict:
    hs = [h for h in blk["holdings"] if h["pct"] > -50]
    for h in hs:
        h["name"] = NOTE_MARKS.sub("", h["name"])
        h["ind"] = NOTE_MARKS.sub("", h["ind"])
    kinds = defaultdict(float)
    for h in hs:
        h["kind"] = h.get("kind") or classify_holding(h)        # fund-page holdings arrive already classified
        kinds[h["kind"]] += h["pct"]
    listed = sum(kinds.values())
    eq = [h for h in hs if h["kind"] == "equity"]
    sectors = defaultdict(float)
    for h in eq:
        sec = re.sub(r"\s+", " ", h["ind"] or "").strip() or "Others"
        if sec.isupper() and len(sec) > 4:
            sec = sec.title().replace("It ", "IT ").replace("Fmcg", "FMCG")
        sectors[sec] += h["pct"]
    cap = {"large": 0.0, "mid": 0.0, "small": 0.0}
    if large or mid:
        for h in eq:
            if h["isin"]:
                cap["large" if h["isin"] in large else "mid" if h["isin"] in mid else "small"] += h["pct"]
        mapped, eq_w = sum(cap.values()), sum(h["pct"] for h in eq)
        if 0 < mapped < eq_w:                                    # holdings without an ISIN: spread pro rata
            cap = {k: v * eq_w / mapped for k, v in cap.items()}
    credit = defaultdict(float)
    for h in hs:
        if h["kind"] == "debt":
            credit[credit_bucket(h["ind"] + " " + h["name"])] += h["pct"]
    top = sorted([h for h in hs if h["isin"]], key=lambda h: -h["pct"])[:15]
    return {
        "n": len(eq), "nAll": len(hs),
        "mix": {k: round(v, 2) for k, v in kinds.items()} | {"cashOther": round(max(0.0, 100 - listed), 2)},
        "top": [[h["name"][:80], h["ind"][:50], round(h["pct"], 2), h["isin"], h["kind"]] for h in top],
        "top10": round(sum(h["pct"] for h in sorted(eq, key=lambda h: -h["pct"])[:10]), 2),
        "sectors": sorted([[k, round(v, 2)] for k, v in sectors.items()], key=lambda x: -x[1])[:14],
        "cap": {k: round(v, 2) for k, v in cap.items()} if (large or mid) and eq else None,
        "top10All": round(sum(h["pct"] for h in sorted(hs, key=lambda h: -h["pct"])[:10]), 2),
        "credit": sorted([[k, round(v, 2)] for k, v in credit.items() if v >= 0.05], key=lambda x: -x[1]) or None,
    }


STOP = {"fund", "the", "plan", "scheme", "of", "an", "open", "ended", "direct", "growth", "regular", "option",
        "portfolio", "monthly", "statement", "as", "on", "mutual", "formerly", "known", "erstwhile", "name",
        "and", "for", "in", "at", "to", "mf", "ltd", "limited", "sep", "september", "month", "end"}
SYN = [(r"\bmid\s*cap\b", " midcap "), (r"\bsmall\s*cap\b", " smallcap "), (r"\blarge\s*cap\b", " largecap "),
       (r"\bmulti\s*cap\b", " multicap "), (r"\bflexi\s*cap\b", " flexicap "), (r"\bfocus(ed)?\b", " focused "),
       (r"\btax\s*saver\b|\belss\b|\btax\s*saving\b", " elss "), (r"\bfund\s*of\s*funds?\b|\bfof\b", " fof "),
       (r"\bpsu\b", " psu "), (r"\bs\s*&\s*p\b", " sp "), (r"\bbse\b|\bnifty\b|\bnse\b", " "), (r"&", " and ")]


def tokens(n: str) -> set:
    n = n.lower()
    n = re.sub(r"\((?:formerly|erstwhile|earlier).*?(\)|$)", " ", n)
    n = re.sub(r"\(\s*an?\s+open.*", " ", n)          # "(An open ended … scheme …)" descriptions
    n = re.sub(r"\(.*?\)", " ", n)
    for a, b in SYN:
        n = re.sub(a, b, n)
    return {t for t in re.findall(r"[a-z0-9]+", n) if t not in STOP and not re.fullmatch(r"20\d\d|19\d\d", t)}


def match_blocks(blocks: list[dict], funds: list[dict]) -> dict[int, dict]:
    """Map parsed blocks to fund codes: the fund whose name tokens are best covered by one of the
    banner lines above the table (fewest extra words breaks ties). Ambiguous matches are dropped."""
    ft = [(f, tokens(f["amfi"])) for f in funds]
    ft = [(f, t) for f, t in ft if t]
    out, score_of = {}, {}
    for blk in blocks:
        best = None
        lines = []
        for dist, line in enumerate(blk.get("ctx") or [blk["title"]]):
            lines.append((dist, line))
            # a renamed scheme may still carry its former name in AMFI's records
            for old in re.findall(r"\(\s*(?:formerly|erstwhile|earlier|ex)\b(?:\s+known)?(?:\s+as)?\s*:?\s*([^)]+)\)", line, re.I):
                lines.append((dist, old))
        for dist, line in lines:
            if re.match(r"\W*an?\s+open", line, re.I):
                continue
            lt = tokens(line)
            if not lt:
                continue
            cands = []
            for f, t in ft:
                cov = len(lt & t) / len(t)
                if cov >= 0.99 or (cov >= 0.8 and len(t) >= 5):
                    cands.append((cov, -len(lt - t), f))
            if not cands:
                continue
            cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
            top = cands[0]
            if len(cands) > 1 and cands[1][:2] == top[:2]:
                continue                                  # two funds fit equally well → ambiguous
            sc = (top[0], top[1], -dist)
            if best is None or sc > best[0]:
                best = (sc, top[2])
        if best:
            code = best[1]["code"]
            # the same fund can appear twice (e.g. a combined file and a per-scheme file): keep the better fit,
            # or the larger table on a tie
            prev = score_of.get(code)
            if prev is None or best[0][:2] > prev[0][:2] or (best[0][:2] == prev[0][:2] and len(blk["holdings"]) > len(out[code]["holdings"])):
                out[code], score_of[code] = blk, best
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
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    found = discover({k: v for k, v in SOURCES.items() if k in funds_by_amc and (not only or k in only)})
    for amc in SOURCES:                       # remember fund houses whose files could not be found this run (for the audit)
        if amc in funds_by_amc and (not only or amc in only):
            if amc in found:
                meta.setdefault(amc, {}).pop("discoveryFail", None)
            else:
                meta.setdefault(amc, {})["discoveryFail"] = date.today().isoformat()
    large, mid = cap_sets(S)
    results, report = {}, {}
    for amc, info in found.items():
        if pf_age_days(info["month"]) > MAX_AGE_DAYS:
            log.warning("%s: latest portfolio file is for %s — too old, skipped", amc, info["month"])
            continue
        if (meta.get(amc, {}).get("month") == info["month"] and meta[amc].get("funds", 0) > 0
                and not meta[amc].get("dlFail") and "--force" not in sys.argv):
            log.info("%s: %s already processed", amc, info["month"])
            continue
        blocks, dl_fail = [], 0
        contents, retry = {}, []
        for url in info["files"]:
            clean = re.sub(r"[?&]_scheme=[^&]*$", "", url)
            try:
                if clean.startswith("file://"):
                    contents[url] = Path(requests.utils.unquote(clean[7:])).read_bytes()
                else:
                    r = S.get(clean, timeout=120, headers={"Referer": SOURCES[amc]["page"]})
                    r.raise_for_status()
                    if not r.content.startswith((b"PK", b"\xd0\xcf\x11\xe0")):
                        raise ValueError("not a spreadsheet (likely a bot-check page)")
                    contents[url] = r.content
            except Exception as e:  # noqa: BLE001
                log.info("%s: plain download refused for %s (%s) — retrying in browser", amc, clean[:90], str(e)[:60])
                retry.append((url, clean))
            time.sleep(0.3)
        if retry:
            got = browser_fetch([(c, SOURCES[amc]["page"]) for _, c in retry])
            for url, c in retry:
                if c in got:
                    contents[url] = got[c]
                else:
                    log.warning("%s: download failed %s", amc, c[:100])
                    dl_fail += 1
        for url in info["files"]:
            if url not in contents:
                continue
            content = contents[url]
            scheme_hint = ""
            m_h = re.search(r"[?&]_scheme=([^&]*)", url)
            if m_h:
                scheme_hint = requests.utils.unquote(m_h.group(1))
                url = re.sub(r"[?&]_scheme=[^&]*$", "", url)
            payloads = []
            if content[:2] == b"PK" and re.search(r"\.zip$", url.lower().split("?")[0]):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    for n in z.namelist():
                        if re.search(r"\.(xlsx?|xlsm)$", n, re.I) and not re.search(SKIP_DEFAULT, n, re.I):
                            payloads.append((n, z.read(n)))
            else:
                payloads.append((url.split("?")[0].rsplit("/", 1)[-1], content))
            for fname, blob in payloads:
                try:
                    for sname, rows in read_book(blob, fname):
                        for blk in parse_sheet(sname, rows):
                            blk["file"] = fname
                            # the file name often carries the scheme name (per-scheme files)
                            stem = re.sub(r"[_-]+", " ", requests.utils.unquote(fname).rsplit(".", 1)[0])
                            blk["ctx"] = blk["ctx"] + [stem] + ([scheme_hint] if scheme_hint else [])
                            blocks.append(blk)
                except Exception as e:  # noqa: BLE001
                    log.warning("%s: could not read %s (%s)", amc, fname, str(e)[:120])
            time.sleep(0.5)
        matched = match_blocks(blocks, funds_by_amc[amc])
        hit = {id(b) for b in matched.values()}
        report[amc] = {"files": [u.split("?")[0].rsplit("/", 1)[-1] for u in info["files"]],
                       "unmatched": [{"sheet": b["ctx"][-1], "ctx": [c[:110] for c in b["ctx"][:6]]} for b in blocks if id(b) not in hit][:40],
                       "matched": {str(c): b["title"][:90] for c, b in matched.items()}}
        bad = 0
        for code, blk in matched.items():
            sm = summarise(blk, large, mid)
            listed = 100 - sm["mix"]["cashOther"]
            if listed < 40 or listed > 130:          # sanity: a portfolio should add up to ~100 %
                bad += 1
                continue
            if not fits_category(sub_of.get(code, ""), sm["mix"]):
                log.warning("%s: %s portfolio does not fit its category (%s) — skipped", amc, code, sub_of.get(code))
                bad += 1
                continue
            sm["asOf"] = info["month"]
            results[code] = sm
        meta[amc] = {"month": info["month"], "files": len(info["files"]), "blocks": len(blocks),
                     "funds": len(matched) - bad, "rejected": bad, "dlFail": dl_fail, "updated": date.today().isoformat()}
        log.info("%s: %d sheet blocks parsed, %d funds matched, %d rejected by sanity checks",
                 amc, len(blocks), len(matched) - bad, bad)
    # fund houses read from their fund pages (one portfolio per fund page)
    want_page = [a for a in PAGE_SOURCES if a in funds_by_amc and (not only or a in only)
                 and ("--force" in sys.argv or (meta.get(a, {}).get("month") or "") < expected_month())]
    if want_page:
        pages = json.load(open(ROOT / "data" / "mf" / "scheme_pages.json"))
        res = FP.Resolver(S)
        pw_ctx = None
        for amc in want_page:
            kind, funds = PAGE_SOURCES[amc], funds_by_amc[amc]
            log.info("%s: reading %d fund pages (%s)", amc, len(funds), kind)
            try:
                if kind == "dom":
                    if pw_ctx is None:
                        from playwright.sync_api import sync_playwright
                        pw_ctx = sync_playwright().start()
                        b, bctx = browser(pw_ctx)
                    got = FP.read_dom(bctx, funds, pages, res)
                else:
                    got = FP.READERS[kind](S, funds, pages, res)
            except Exception as e:  # noqa: BLE001
                log.warning("%s: fund-page reader failed (%s)", amc, str(e)[:160])
                got = {}
            ok_n, months = 0, []
            for code, (month, blk) in got.items():
                if pf_age_days(month) > MAX_AGE_DAYS:
                    continue
                sm = summarise(blk, large, mid)
                listed = 100 - sm["mix"]["cashOther"]
                if listed < 40 or listed > 130 or not sm["top"]:
                    continue
                sub = sub_of.get(code, "")
                need = PAGE_MIN_LISTED["index"] if sub.startswith("idx_") else PAGE_MIN_LISTED["equity"] if (sub in EQUITY_SUBS or sub.startswith("sec_")) else 0
                if listed < need:
                    log.info("    %s: page lists only %.0f%% of the portfolio — incomplete, skipped", code, listed)
                    continue
                sm["asOf"] = month
                results[code] = sm
                ok_n += 1
                months.append(month)
            entry = {"month": max(months) if months else (meta.get(amc, {}).get("month")), "files": 0, "blocks": len(got),
                     "funds": ok_n, "rejected": len(got) - ok_n, "dlFail": 0, "source": "fund pages", "updated": date.today().isoformat()}
            if not ok_n:
                entry = {**meta.get(amc, {}), "discoveryFail": date.today().isoformat()}
            meta[amc] = entry
            log.info("%s: %d fund portfolios from fund pages (%d read, %d rejected)", amc, ok_n, len(got), len(got) - ok_n)
        if pw_ctx is not None:
            b.close()
            pw_ctx.stop()

    # merge into per-sub files (keep other fund houses' last good data)
    by_sub = defaultdict(dict)
    for p in OUT.glob("*.json"):
        if p.name.startswith("_"):
            continue
        for code, v in json.load(open(p)).items():
            y, m = map(int, v["asOf"].split("-"))
            if int(code) in sub_of and pf_age_days(v["asOf"]) <= MAX_AGE_DAYS:
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
