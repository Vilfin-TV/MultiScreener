#!/usr/bin/env python3
"""Monthly portfolios read from fund-house *fund pages* (for fund houses that publish no machine-readable monthly
portfolio file). Used by build_mf_holdings.py.

Readers
  · "trust"  — TRUSTMF: the site's portfolio data service, one call per fund (slug from the fund's page address).
  · "pgim"   — PGIM India: scheme list (name → scheme code) + one portfolio call per scheme.
  · "dom"    — any other site: open the fund page in a browser, open its holdings view ("Portfolio" / "Holdings" tab,
               "See all / Show more"), and read the table whose weights add up like a full portfolio. The portfolio
               date must be stated on the page ("as on 30 Sep 2026"); pages without one are skipped.

Page holdings carry names, not ISINs. `Resolver` maps names to ISINs with the exchange's listed-equity master and the
ISINs already known from statutory portfolio files; cash, repo, government securities and fund units are classified
by name. A fund is used only when ≥85 % of its equity weight maps to an ISIN; unmapped holdings stay in the asset mix
but never appear in the top-15 list.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import time
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger("holdings.pages")
ROOT = Path(__file__).resolve().parent.parent
MF = ROOT / "data" / "mf"
MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MIN_EQ_MAPPED = 0.85

# ───────────────────────────── names → ISIN ─────────────────────────────
DROP = re.compile(r"\b(the|limited|ltd|ltd\.|co|company|corp|corporation|inc|plc|pvt|private)\b")
CASH_RX = re.compile(r"treps|tri-?party|reverse\s*repo|\brepo\b|cblo|net\s*(current\s*)?(receivable|payable|asset)|cash|margin|"
                     r"current\s*assets|receivables|payables", re.I)
DEBT_RX = re.compile(r"\bgoi\b|government|g-?sec|t-?bill|treasury|\bsdl\b|state\s*development|\bbond|ncd|debenture|"
                     r"commercial\s*paper|\bcp\b|certificate\s*of\s*deposit|\bcd\b|\d{1,2}\.\d+\s*%|\bdays\s*tbill|sovereign", re.I)
FUND_RX = re.compile(r"\b(fund|etf|bees|units?\s+of)\b", re.I)
REIT_RX = re.compile(r"\breit\b|\binvit\b|infrastructure\s+investment\s+trust|real\s+estate\s+investment", re.I)
HEADER_RX = re.compile(r"^(equity|debt|money\s*market|others?|total|grand\s*total|sub\s*total|equity\s*&\s*equity\s*related|"
                       r"listed|unlisted|awaiting\s*listing|holdings?|stocks?|instrument|name)\b.*$", re.I)


def norm(name: str) -> str:
    n = (name or "").lower().replace("&", " and ").replace("'", "")
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    n = DROP.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


class Resolver:
    def __init__(self, session):
        self.idx: dict[str, str] = {}          # normalised name → ISIN
        self.ind: dict[str, str] = {}          # ISIN → industry
        try:
            r = session.get("https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv", timeout=60)
            if r.status_code == 200:
                for row in csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", errors="replace"))):
                    row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                    if row.get("NAME OF COMPANY") and re.match(r"^INE[A-Z0-9]{9}$", row.get("ISIN NUMBER", "")):
                        self.idx.setdefault(norm(row["NAME OF COMPANY"]), row["ISIN NUMBER"])
        except Exception as e:  # noqa: BLE001
            log.warning("listed-equity master unavailable (%s)", str(e)[:80])
        n_master = len(self.idx)
        for f in (MF / "p").glob("*.json"):                       # names and industries seen in statutory files
            if f.name.startswith("_"):
                continue
            for v in json.loads(f.read_text()).values():
                for t in v.get("top") or []:
                    if len(t) >= 5 and t[3] and t[4] == "equity":
                        self.idx.setdefault(norm(t[0]), t[3])
                        if t[1]:
                            self.ind.setdefault(t[3], t[1])
        self.keys = sorted(self.idx)
        log.info("Name resolver: %d listed companies, %d names in total", n_master, len(self.idx))

    def isin(self, name: str) -> str | None:
        k = norm(name)
        if not k:
            return None
        if k in self.idx:
            return self.idx[k]
        # abbreviated or truncated names ("HDFC BANK", "Larsen and Toubro") — accept a unique prefix match only
        cands = {self.idx[x] for x in self.keys if x.startswith(k + " ") or k.startswith(x + " ")}
        return cands.pop() if len(cands) == 1 else None


def kind_of(name: str, group: str = "") -> str:
    t = f"{group} {name}"
    if CASH_RX.search(t):
        return "cash"
    if REIT_RX.search(name):
        return "reit"
    if re.search(r"debt|money\s*market|government|sovereign|bond", group, re.I) or DEBT_RX.search(name):
        return "debt"
    if FUND_RX.search(name) and not re.search(r"\b(bank|finance|financial|insurance)\b", name, re.I):
        return "fund"
    return "equity"


def build_block(rows: list[tuple[str, str, float, str]], res: Resolver) -> dict | None:
    """rows: (name, industry, pct, group). Returns a summarise()-ready block or None when too little maps."""
    hs, eq_w, eq_mapped = [], 0.0, 0.0
    for name, ind, pct, group in rows:
        name = re.sub(r"\s+", " ", name or "").strip()
        if not name or HEADER_RX.match(name) or pct is None:
            continue
        k = kind_of(name, group)
        if k == "cash":
            continue                                   # cash / repo / net receivables → cashOther
        isin = res.isin(name) if k == "equity" else None
        if k == "equity":
            eq_w += pct
            if isin:
                eq_mapped += pct
        hs.append({"name": name, "isin": isin or "", "ind": ind or (res.ind.get(isin, "") if isin else ""), "pct": pct, "kind": k})
    if not hs:
        return None
    if eq_w > 5 and eq_mapped / eq_w < MIN_EQ_MAPPED:
        log.info("    only %.0f%% of equity weight mapped to ISINs — skipped", 100 * eq_mapped / eq_w)
        return None
    return {"title": "", "ctx": [], "holdings": hs}


def pct_num(x) -> float | None:
    try:
        return float(str(x).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def month_of(text: str) -> str | None:
    """Latest plausible portfolio month-end mentioned as 'as on/of <date>' (or a bare dd-Mon-yyyy / dd/mm/yyyy)."""
    t = (text or "").lower()
    found = []
    for m in re.finditer(r"(\d{1,2})(?:st|nd|rd|th)?[\s\-/.]*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-/.,]*(\d{4}|\d{2})\b", t):
        y = int(m.group(3)); y += 2000 if y < 100 else 0
        found.append((y, MON[m.group(2)], int(m.group(1))))
    for m in re.finditer(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](20\d{2})\b", t):
        d1, m1, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if m1 > 12 and d1 <= 12:                       # month-first (9/30/2026)
            d1, m1 = m1, d1
        if 1 <= m1 <= 12:
            found.append((y, m1, d1))
    today = date.today()
    ok = [(y, m, d) for y, m, d in found if 2015 <= y <= today.year and (y, m) < (today.year, today.month) and d >= 25]
    if not ok:
        return None
    y, m, _ = max(ok)
    return f"{y:04d}-{m:02d}"


# ───────────────────────────── readers ─────────────────────────────
def read_trust(session, funds: list[dict], pages: dict, res: Resolver) -> dict:
    out = {}
    for f in funds:
        url = pages.get(str(f["code"])) or ""
        m = re.search(r"/our-products/([a-z0-9\-]+)", url)
        if not m:
            continue
        body = {"systemQueryFileName": "productsweb.xml", "tagName": "GetPortfolioWeb", "searchField": "p.slug",
                "searchValue": m.group(1), "sortField": "pf.srno", "sortDirection": "asc"}
        try:
            r = session.post("https://www.trustmf.com/api/api/Trust/GetData", json=body, timeout=45,
                             headers={"Referer": url, "Origin": "https://www.trustmf.com"})
            rows = (r.json() or {}).get("resultSetArray") or []
        except Exception as e:  # noqa: BLE001
            log.info("  Trust %s: %s", m.group(1), str(e)[:80])
            continue
        if not rows:
            continue
        tot = sum(pct_num(x.get("percentageofassets")) or 0 for x in rows)
        scale = 100 if tot <= 1.6 else 1
        mo = month_of(rows[0].get("uploaddate", "").replace("12:00:00 AM", ""))
        blk = build_block([(x.get("instrument", ""), x.get("rating", "") if not re.search(r"\b(AAA|AA|A1|SOV)", x.get("rating", "")) else "",
                            (pct_num(x.get("percentageofassets")) or 0) * scale, x.get("portfoliogroup", "")) for x in rows], res)
        if blk and mo:
            out[f["code"]] = (mo, blk)
        time.sleep(0.4)
    return out


def read_pgim(session, funds: list[dict], pages: dict, res: Resolver) -> dict:
    out = {}
    try:
        cats = session.get("https://www.pgimindia.com/api/v1/brochure/product/schemes", timeout=60).json()["data"]["categories"]
    except Exception as e:  # noqa: BLE001
        log.warning("  PGIM scheme list unavailable (%s)", str(e)[:80])
        return out
    codes = {}
    for c in cats:
        for p in c.get("products") or []:
            if re.search(r"direct", p.get("planDesc", ""), re.I) and re.search(r"growth", p.get("planDesc", "") + p.get("optDesc", ""), re.I):
                codes[norm(p.get("schemeDesc", ""))] = p.get("schemeCode")
    for f in funds:
        sc = codes.get(norm(re.sub(r"\s*-\s*direct.*$", "", f["amfi"], flags=re.I)))
        if not sc:
            continue
        try:
            d = session.post("https://www.pgimindia.com/api/v1/brochure/product/list/portfolio",
                             json={"schemeCode": sc, "planType": "DIRECT", "source": "W", "branchCode": None}, timeout=45).json()["data"]
        except Exception as e:  # noqa: BLE001
            log.info("  PGIM %s: %s", sc, str(e)[:80])
            continue
        rows = []
        for grp, v in (d.get("categories") or {}).items():
            for h in v.get("topHoldings") or []:
                rows.append((h.get("stockName", ""), "", pct_num(h.get("percentage")), grp))
        mo, blk = month_of(d.get("asOnDate", "")), build_block(rows, res)
        if blk and mo:
            out[f["code"]] = (mo, blk)
        time.sleep(0.4)
    return out


ROWS_JS = r"""() => {
  const pct = /^-?\d{1,3}(\.\d{1,4})?\s*%?$/;
  const groups = [];
  const take = (container, rowEls, cellsOf) => {
    const rows = [];
    rowEls.forEach(r => { const c = cellsOf(r).map(x => (x.innerText || '').trim()).filter(Boolean);
      if (c.length >= 2 && pct.test(c[c.length - 1]) && c[0].length > 2 && c[0].length < 120 && !pct.test(c[0])) rows.push(c); });
    if (rows.length >= 5) groups.push(rows);
  };
  document.querySelectorAll('table').forEach(t => take(t, t.querySelectorAll('tr'), r => [...r.querySelectorAll('td,th')]));
  const seen = new Set();
  document.querySelectorAll('li, div').forEach(el => {
    const kids = [...el.children]; if (kids.length < 2 || kids.length > 6) return;
    const p = el.parentElement; if (!p || seen.has(p)) return; seen.add(p);
    take(p, [...p.children], r => [...r.children]);
  });
  return groups;
}"""
OPEN_TABS = ["text=/^\\s*(Portfolio|Holdings)\\s*$/i", "#tab-holdings", "text=/^\\s*Portfolio\\s+Holdings\\s*$/i"]
EXPAND = ["text=/^\\s*(See|View|Show|Load)\\s+(all|more)(\\s+holdings)?\\s*$/i", "text=/^\\s*View\\s+all\\s+holdings\\s*$/i"]


def read_dom(ctx, funds: list[dict], pages: dict, res: Resolver, budget_s: int = 1500) -> dict:
    out, t0 = {}, time.time()
    for f in funds:
        if time.time() - t0 > budget_s:
            log.info("  page budget reached after %d funds", len(out))
            break
        url = pages.get(str(f["code"]))
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        p = ctx.new_page()
        try:
            p.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                p.wait_for_load_state("networkidle", timeout=12000)
            except Exception:  # noqa: BLE001
                pass
            for sel in OPEN_TABS:
                try:
                    el = p.locator(sel).first
                    if el.count():
                        el.click(timeout=3000)
                        p.wait_for_timeout(2500)
                        break
                except Exception:  # noqa: BLE001
                    pass
            for _ in range(3):
                clicked = False
                for sel in EXPAND:
                    loc = p.locator(sel)
                    for i in range(min(loc.count(), 3)):
                        try:
                            loc.nth(i).click(timeout=2000)
                            clicked = True
                            p.wait_for_timeout(1200)
                        except Exception:  # noqa: BLE001
                            pass
                if not clicked:
                    break
            groups = p.evaluate(ROWS_JS)
            text = p.inner_text("body")
        except Exception as e:  # noqa: BLE001
            log.info("  %s: page error %s", f["code"], str(e)[:80])
            p.close()
            continue
        p.close()
        best = None
        for g in groups:
            vals = [pct_num(r[-1]) for r in g]
            tot = sum(v for v in vals if v is not None)
            names = [r[0] for r in g]
            if not (60 <= tot <= 105) or len(set(names)) < 0.8 * len(names):
                continue
            if sum(1 for n in names if re.search(r"return|cagr|nav|benchmark|year|month|plan|idcw", n, re.I)) > 1:
                continue
            if best is None or len(g) > len(best):
                best = g
        mo = month_of(" ".join(re.findall(r"(?:as\s+(?:on|of|at)|portfolio\s+(?:as\s+)?(?:on|of))\s*[:\-]?\s*([^\n]{6,24})", text, re.I)))
        if not best or not mo:
            log.info("  %s: %s", f["amfi"][:50], "no full holdings table" if not best else "no portfolio date on the page")
            continue
        rows = [(r[0], r[1] if len(r) >= 3 and not pct_num(r[1]) else "", pct_num(r[-1]), "") for r in best]
        blk = build_block(rows, res)
        if blk:
            out[f["code"]] = (mo, blk)
    return out


# ─────────────────────────── monthly factsheet PDFs ───────────────────────────
LINE_RX = re.compile(r"^(.*?[A-Za-z&).].*?)\s+(-?\d{1,3}(?:\.\d+)?)\s*%$")
STOP_RX = re.compile(r"^(top\s*10|scheme\s*performance|value\s*of|note|\*|for\s+detailed|sector\s*allocation|asset\s*allocation|"
                     r"maturity\s*profile|rating\s*profile|returns?\s+are)", re.I)


def _factsheet_index(pdf) -> dict[int, str]:
    """{printed page number: scheme name} from the factsheet's INDEX page(s)."""
    out = {}
    for pg in pdf.pages[:6]:
        txt = pg.extract_text() or ""
        if not re.search(r"\bINDEX\b|contents", txt, re.I):
            continue
        for line in txt.splitlines():
            m = re.match(r"^\s*\d+\.\s*(.+?)\s*\.{3,}\s*(\d{1,3})\s*$", line)
            if m and re.search(r"fund|plan|etf|fof", m.group(1), re.I):
                out[int(m.group(2))] = m.group(1).strip()
    return out


def _printed_page(pg) -> int | None:
    """The page number printed in the footer (a lone number at the bottom of the page)."""
    words = [w for w in pg.extract_words() if w["top"] > pg.height - 70 and re.fullmatch(r"\d{1,3}", w["text"])]
    return int(max(words, key=lambda w: w["top"])["text"]) if words else None


def _split_sectors(lines: list[tuple[str, float]]) -> list[tuple[str, str, float]]:
    """[(name, pct)] in reading order → [(name, industry, pct)]: a line whose weight equals the sum of the lines right
    after it is a sector heading for them (factsheets list 'Banks 24.67%' then each bank)."""
    out, i = [], 0
    while i < len(lines):
        name, pct = lines[i]
        acc, k, end = 0.0, i + 1, None
        while k < len(lines) and acc <= pct + 0.05:
            acc += lines[k][1]
            k += 1
            if abs(acc - pct) <= 0.006 * (k - i - 1) + 0.011:      # each figure is rounded to 2 decimals
                end = k
                break
        if end:
            out += [(n, name, p) for n, p in lines[i + 1:end]]
            i = end
        else:
            out.append((name, "", pct))
            i += 1
    return out


def equity_total(pg) -> float | None:
    """The page's own 'Equity Holdings Total' figure, used to check the parsed holdings."""
    m = re.search(r"equity\s*(?:&\s*equity\s*related\s*)?holdings?\s*total\s*(\d{1,3}(?:\.\d+)?)\s*%", pg.extract_text() or "", re.I)
    return float(m.group(1)) if m else None


def parse_portfolio_page(pg) -> tuple[str | None, list[tuple[str, str, float]]]:
    """One factsheet page with a 'PORTFOLIO as on dd/mm/yyyy' box laid out in 'Company · % of NAV' columns."""
    words = pg.extract_words()
    head = next((w for w in words if w["text"] == "PORTFOLIO"), None)
    if not head:
        return None, []
    text = pg.crop((head["x0"] - 2, head["top"] - 2, pg.width, head["bottom"] + 2)).extract_text() or ""
    month = month_of(text)
    cols = sorted({round(w["x0"]) for w in words if w["text"] == "Company" and 0 <= w["top"] - head["top"] < 40})
    if not cols:
        return month, []
    top = min(w["top"] for w in words if w["text"] == "Company" and 0 <= w["top"] - head["top"] < 40)
    lines, done = [], False
    for j, x in enumerate(cols):
        x1 = cols[j + 1] - 6 if j + 1 < len(cols) else pg.width
        for raw in (pg.crop((x - 6, top - 1, x1, pg.height)).extract_text() or "").splitlines():
            raw = raw.strip()
            if not raw or re.match(r"^company\b", raw, re.I):
                continue
            if STOP_RX.match(raw) or re.match(r"^grand\s*total", raw, re.I):
                done = bool(re.match(r"^grand\s*total", raw, re.I)) or done
                break
            m = LINE_RX.match(raw)
            if not m:
                continue
            name, pct = m.group(1).strip(), float(m.group(2))
            if re.search(r"\btotal\b", name, re.I):
                if CASH_RX.search(name):
                    lines.append(("Cash & other receivables", pct))   # residual cash, net of payables
                continue
            lines.append((name, pct))
        if done:
            break
    return month, _split_sectors(lines)


def match_scheme(name: str, funds: list[dict]) -> int | None:
    """Fund code whose official name best matches a factsheet scheme name (unique best only)."""
    stop = {"lic", "mf", "fund", "the", "direct", "plan", "growth", "option", "regular", "scheme", "of", "s"}

    def tok(s):
        s = (s or "").lower().replace("&", " and ").replace("'", "")
        s = re.sub(r"\b(multi|large|mid|small|flexi)\s+cap\b", r"\1cap", s)       # "Multi Cap" = "MultiCap"
        return {t for t in re.sub(r"[^a-z0-9 ]+", " ", s).split() if t not in stop}
    want = tok(name)
    if not want:
        return None
    scored = []
    for f in funds:
        have = tok(f.get("amfi"))
        if want <= have:
            scored.append((len(want) / len(have | want), f["code"]))
    scored.sort(reverse=True)
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return None
    return scored[0][1]


def read_factsheet_pdf(blob: bytes, funds: list[dict], res: Resolver) -> dict:
    """{fund code: (month, block)} from a fund house's monthly factsheet PDF."""
    import pdfplumber
    out = {}
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        idx = _factsheet_index(pdf)
        for i, pg in enumerate(pdf.pages):
            if "PORTFOLIO" not in (pg.extract_text() or ""):
                continue
            month, rows = parse_portfolio_page(pg)
            name = idx.get(_printed_page(pg) or -1) or idx.get(i + 1)
            if not (month and rows and name):
                continue
            code = match_scheme(name, funds)
            if code is None:
                log.info("    factsheet page %d (%s): no unique fund match", i + 1, name)
                continue
            # equity-oriented portfolios only, and the parsed stocks must add up to the page's own equity total
            eq_tot = equity_total(pg)
            eq_sum = sum(p for n, _, p in rows if kind_of(n) == "equity")
            if eq_tot is None or eq_tot < 60 or abs(eq_sum - eq_tot) > 0.15:
                log.info("    factsheet page %d (%s): parsed equity %.2f%% vs stated %s — skipped", i + 1, name, eq_sum, eq_tot)
                continue
            blk = build_block([(n, ind, p, "") for n, ind, p in rows], res)
            if blk:
                blk["title"] = name
                out[code] = (month, blk)
    return out


FACTSHEETS = {"lic": {"page": "https://www.licmf.com/downloads/factsheet", "pick": r"monthly_fact_sheet/.+factsheet.+\.pdf"}}


def read_factsheet(ctx, kind: str, funds: list[dict], res: Resolver) -> dict:
    """Find the latest monthly factsheet on the fund house's download page (browser) and read it."""
    cfg = FACTSHEETS[kind]
    p = ctx.new_page()
    try:
        p.goto(cfg["page"], wait_until="domcontentloaded", timeout=90000)
        try:
            p.wait_for_load_state("networkidle", timeout=20000)
        except Exception:  # noqa: BLE001
            pass
        links = p.eval_on_selector_all("a", "as => as.map(a => a.href)")
    finally:
        p.close()
    dated = []
    for l in dict.fromkeys(links):
        if re.search(cfg["pick"], l, re.I):
            mo = month_of(re.sub(r"[-_]", " ", l.rsplit("/", 1)[-1]))
            if mo:
                dated.append((mo, l))
    if not dated:
        log.warning("factsheet (%s): no dated factsheet links found", kind)
        return {}
    mo, url = max(dated)
    r = ctx.request.get(url, headers={"Referer": cfg["page"]}, timeout=180000)
    if not r.ok or not r.body().startswith(b"%PDF"):
        log.warning("factsheet (%s): download failed (%s)", kind, r.status)
        return {}
    log.info("factsheet (%s): %s · %s", kind, mo, url.rsplit("/", 1)[-1])
    return read_factsheet_pdf(r.body(), funds, res)


READERS = {"trust": read_trust, "pgim": read_pgim}
