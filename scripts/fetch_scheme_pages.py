#!/usr/bin/env python3
"""
India Mutual Fund Screener — each fund's own page on its fund house's website.

Fund-house sites publish sitemaps that list every scheme page. This script reads them (robots.txt
"Sitemap:" entries, /sitemap.xml and nested sitemap indexes), then matches each fund to the page
whose address carries the fund's name. Runs weekly in the holdings workflow.

Output: data/mf/scheme_pages.json  {"_asOf": "...", "<AMFI code>": "https://…", …}
"""
from __future__ import annotations

import gzip
import json
import logging
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_mf_holdings as H  # noqa: E402  (scheme-name tokeniser)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mf" / "scheme_pages.json"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("pages")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
      "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"}

# official fund-house websites (also used by the page for the "website" link)
WEBSITES = {
    "360 ONE": "https://www.360.one/asset/mutual-funds/", "ASK": "https://www.askmutualfund.com",
    "Abakkus": "https://www.abakkusmf.com", "Aditya Birla Sun Life": "https://mutualfund.adityabirlacapital.com",
    "AlphaGrep": "https://www.alphagrepmf.ai", "Angel One": "https://www.angelonemf.com", "Axis": "https://www.axismf.com",
    "Bajaj Finserv": "https://www.bajajamc.com", "Bandhan": "https://bandhanmutual.com", "Bank of India": "https://www.boimf.in",
    "Baroda BNP Paribas": "https://www.barodabnpparibasmf.in", "Canara Robeco": "https://www.canararobeco.com",
    "Capitalmind": "https://capitalmindmf.com", "Choice": "https://choicemf.com", "DSP": "https://www.dspim.com",
    "Edelweiss": "https://www.edelweissmf.com", "Franklin Templeton": "https://www.franklintempletonindia.com",
    "Groww": "https://www.growwmf.in", "HDFC": "https://www.hdfcfund.com", "HSBC": "https://www.assetmanagement.hsbc.co.in",
    "Helios": "https://www.heliosmf.in", "ICICI Prudential": "https://www.icicipruamc.com", "ITI": "https://www.itiamc.com",
    "Invesco": "https://www.invescomutualfund.com", "JM Financial": "https://www.jmfinancialmf.com",
    "Jio BlackRock": "https://www.jioblackrockamc.com", "Kotak Mahindra": "https://www.kotakmf.com", "LIC": "https://www.licmf.com",
    "Lakshya": "https://www.lakshyafunds.com", "Mahindra Manulife": "https://www.mahindramanulife.com",
    "Mirae Asset": "https://www.miraeassetmf.co.in", "Monarch": "https://monarchamc.in", "Motilal Oswal": "https://www.motilaloswalmf.com",
    "NJ": "https://www.njmutualfund.com", "Navi": "https://navi.com/mutual-fund", "Nippon India": "https://mf.nipponindiaim.com",
    "Old Bridge": "https://www.oldbridgemf.com", "PGIM India": "https://www.pgimindia.com/mutual-funds", "PPFAS": "https://amc.ppfas.com",
    "Quantum": "https://www.quantumamc.com", "SBI": "https://www.sbimf.com", "Samco": "https://www.samcomf.com",
    "Shriram": "https://www.shriramamc.in", "Sundaram": "https://www.sundarammutual.com", "Tata": "https://www.tatamutualfund.com",
    "Taurus": "https://www.taurusmutualfund.com", "The Wealth Company": "https://www.wealthcompanyamc.in", "Trust": "https://www.trustmf.com",
    "UTI": "https://www.utimf.com", "Unifi": "https://unifimf.com", "Union": "https://www.unionmf.com",
    "WhiteOak Capital": "https://mf.whiteoakamc.com", "Zerodha": "https://www.zerodhafundhouse.com", "quant": "https://www.quantmutual.com",
}
SKIP_PATH = re.compile(r"\.(pdf|xlsx?|zip|jpe?g|png|svg|docx?)$|blog|news|article|press|media-?cent|insight|learn|faq|calculator|"
                       r"factsheet|disclosure|download|career|investor-?education|campaign|webinar|video|podcast|glossary|"
                       r"compare|nfo-?update|addendum|notice|/tag/|/category/|/author/|/amp/|idcw|dividend-?option|archive|timeline|"
                       r"media-?kit|handbook|active-?share|portfolio/|sitemap|knowledge|guide|infographic|personal-finance|what-is|-vs-|"
                       r"benefits-of|nfo-details|/nfo/|explained|how-to", re.I)
GENERIC = {"mutual", "funds", "fund", "schemes", "scheme", "equity", "debt", "hybrid", "products", "product", "our", "details",
           "detail", "solution", "oriented", "invest", "empower", "explorer", "overview", "mf", "en", "in", "fund-details"}
BRAND_WORDS = re.compile(r"[a-z0-9]+")


def get(url: str, timeout=40) -> bytes | None:
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception:  # noqa: BLE001
        pass
    return None


def sitemap_urls(site: str, budget_s: float = 90) -> list[str]:
    t0 = time.time()
    root = f"{urlparse(site).scheme}://{urlparse(site).netloc}"
    seeds = []
    rb = get(root + "/robots.txt")
    if rb:
        seeds += re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rb.decode("utf-8", "replace"))
    seeds += [root + p for p in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/sitemaps.xml")]
    seen, pages, queue = set(), [], list(dict.fromkeys(seeds))
    while queue and len(seen) < 40 and time.time() - t0 < budget_s:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        body = get(sm)
        if not body:
            continue
        if body[:2] == b"\x1f\x8b":
            try:
                body = gzip.decompress(body)
            except OSError:
                continue
        text = body.decode("utf-8", "replace")
        locs = [unquote(x.strip()) for x in re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.S)]
        if "<sitemapindex" in text[:3000]:
            # fund pages live in "scheme/fund/product" sitemaps — fetch those first
            locs.sort(key=lambda u: 0 if re.search(r"fund|scheme|product|mutual", u, re.I) else 1)
            queue.extend(locs)
        else:
            pages.extend(locs)
    return list(dict.fromkeys(pages))


def _prep(text: str) -> str:
    """Keep phrases whose small words matter ("ultra short TO short term" is a different fund)."""
    t = re.sub(r"short[\s\-_]+to[\s\-_]+short", "shorttoshort", text, flags=re.I)
    return re.sub(r"fund[\s\-_]+of[\s\-_]+funds?", "fof", t, flags=re.I)


KIND_WORDS = ("etf", "fof", "index")


def url_tokens(u: str) -> tuple[set, set]:
    """(tokens of the whole path, tokens of the most specific part) — plan codes such as "nx-dg" are ignored."""
    path = _prep(unquote(urlparse(u).path).lower())
    segs = [s for s in path.split("/") if s]
    clean = lambda x: H.tokens(re.sub(r"\b(html?|aspx|php|direct|regular|growth|plan|option)\b", " ", re.sub(r"[-_+.()]+", " ", x)))
    allt = set().union(*[clean(s) for s in segs]) - GENERIC if segs else set()
    named = [s for s in segs if len([t for t in clean(s) - GENERIC if len(t) >= 3]) >= 2] or segs[-1:]
    return allt, (clean(named[-1]) - GENERIC) if named else set()


def match(funds: list[dict], urls: list[str], brand: set) -> dict[int, str]:
    out, fit = {}, {}
    # 1) an address carrying the fund's own scheme code is an exact match
    for f in funds:
        rx = re.compile(r"[=/]" + str(f["code"]) + r"(?:\b|$)")
        hit = [u for u in urls if rx.search(u)]
        if hit:
            out[f["code"]] = min(hit, key=len)
    cands = []
    for u in urls:
        if SKIP_PATH.search(urlparse(u).path):
            continue
        allt, spec = url_tokens(u)
        allt, spec = allt - brand, spec - brand
        if spec:
            cands.append((u, allt, spec))
    for f in funds:
        if f["code"] in out:
            continue
        best = []
        for nm in f["names"]:
            ft = H.tokens(_prep(nm)) - brand - GENERIC
            if not ft:
                continue
            for u, allt, spec in cands:
                # an ETF / index / FoF page only fits a fund of the same kind (and vice versa)
                if any((k in spec) != (k in ft) for k in KIND_WORDS if k != "index") or ("index" in spec and "index" not in ft):
                    continue
                if ft <= allt and ft & spec:
                    extra = len(spec - ft)
                    if extra <= 3:
                        low = u.lower()
                        plan = 0 if re.search(r"direct|dir-g|-dg\b", low) else (2 if re.search(r"regular|reg-g|-rg\b", low) else 1)
                        best.append((extra, plan, len(u), u))
        if not best:
            continue
        best.sort()                              # fewest extra words, direct plan, shortest address
        out[f["code"]] = best[0][3]
        fit[f["code"]] = best[0][0]
    # one scheme page claimed by several funds (e.g. plans of one scheme): keep it for the closest name only
    by_url = defaultdict(list)
    for code, u in out.items():
        by_url[u].append(code)
    for u, codes in by_url.items():
        if len(codes) > 1:
            ranked = sorted(codes, key=lambda c: fit.get(c, 0))
            if len(ranked) > 1 and fit.get(ranked[0], 0) == fit.get(ranked[1], 0):
                keep = None
            else:
                keep = ranked[0]
            for c in codes:
                if c != keep:
                    out.pop(c, None)
    return {c: re.sub(r"[?&]utm_[^#]*$", "", u) for c, u in out.items()}


LIST_RX = re.compile(r"^/?(mutual-?funds?|our-?(schemes|funds|products)|products?|schemes?|funds?|mutual-fund-schemes|"
                     r"fund-?finder|explore[^/]*|ourfunds/our-funds|invest/mutual-fund-schemes|funds-and-solutions/funds-explorer/all-mutual-funds|"
                     r"mf-scheme-list\.html|our-funds)/?$", re.I)


def list_page(site: str, urls: list[str]) -> str:
    """The fund house's page listing all its funds (falls back to the home page)."""
    host = urlparse(site).netloc
    cands = [u for u in urls if urlparse(u).netloc.endswith(host.replace("www.", "")) and LIST_RX.match(urlparse(u).path)]
    return min(cands, key=len) if cands else site


def browser_links(sites: dict[str, str], budget_s: float = 900, per_site_s: float = 70) -> dict[str, list[str]]:
    """Render each fund-house site, follow its fund-listing pages and collect every link (sites without sitemaps)."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as pw:
        b, ctx = H.browser(pw)
        t_all = time.time()
        for amc, site in sites.items():
            if time.time() - t_all > budget_s:
                log.info("  browser budget used up; %s skipped this week", amc)
                continue
            links, visited, t_site = set(), set(), time.time()
            queue = [site]
            while queue and len(visited) < 5 and time.time() - t_site < per_site_s:
                url = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                try:
                    p = ctx.new_page()
                    p.goto(url, wait_until="domcontentloaded", timeout=35000)
                    try:
                        p.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:  # noqa: BLE001
                        pass
                    for _ in range(3):
                        p.mouse.wheel(0, 3000)
                        p.wait_for_timeout(400)
                    got = p.eval_on_selector_all("a", "as => as.map(a => [a.href, (a.innerText || '').trim()])")
                    p.close()
                except Exception as e:  # noqa: BLE001
                    log.info("  %s: %s not reachable (%s)", amc, url[:80], str(e)[:80])
                    continue
                host = urlparse(site).netloc.replace("www.", "")
                for href, txt in got:
                    if not href.startswith("http") or host not in urlparse(href).netloc:
                        continue
                    links.add(href.split("#")[0])
                    path = urlparse(href).path
                    if LIST_RX.match(path) or (re.search(r"\b(all|our|explore|view)\b.*\bfunds?\b|\bfunds?\b$", txt, re.I) and len(path) < 60):
                        queue.append(href.split("#")[0])
            out[amc] = sorted(links)
            log.info("  %s: %d links from %d pages", amc, len(links), len(visited))
        b.close()
    return out


def main():
    scr = json.load(open(ROOT / "data" / "mf" / "screener.json"))
    C = {c: i for i, c in enumerate(scr["cols"])}
    det = {}
    for f in (ROOT / "data" / "mf" / "d").glob("*.json"):
        det.update(json.load(open(f)))
    by_amc = defaultdict(list)
    for r in scr["rows"]:
        code = r[C["code"]]
        amfi = (det.get(str(code)) or {}).get("info", {}).get("amfiName") or ""
        by_amc[scr["amcs"][r[C["amc"]]]].append({"code": code, "names": [n for n in {r[C["name"]], amfi} if n]})
    prev = json.load(open(OUT)) if OUT.exists() else {}
    res, stats = {}, {}

    all_urls = {}

    def work2(amc):
        site = WEBSITES.get(amc)
        urls = sitemap_urls(site) if site else []
        brand = set(BRAND_WORDS.findall(amc.lower())) | {"mf", "mutual", "amc", "india", "asset", "management"}
        return amc, urls, match(by_amc[amc], urls, brand)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for amc, urls, m in ex.map(work2, sorted(by_amc)):
            all_urls[amc] = urls
            res.update(m)
            stats[amc] = (len(urls), len(m), len(by_amc[amc]))
            log.info("%-24s sitemap URLs %6d · matched %3d of %3d", amc, len(urls), len(m), len(by_amc[amc]))
    # second pass in a browser for fund houses without a usable sitemap
    weak = {a: WEBSITES[a] for a in by_amc if a in WEBSITES and stats[a][1] < 0.8 * stats[a][2]}
    try:
        crawled = browser_links(weak)
    except Exception as e:  # noqa: BLE001
        log.warning("browser pass unavailable (%s)", str(e)[:120])
        crawled = {}
    for amc, links in crawled.items():
        all_urls[amc] = list(dict.fromkeys(all_urls.get(amc, []) + links))
        brand = set(BRAND_WORDS.findall(amc.lower())) | {"mf", "mutual", "amc", "india", "asset", "management"}
        todo = [f for f in by_amc[amc] if f["code"] not in res]
        m = match(todo, all_urls[amc], brand)
        res.update(m)
        log.info("%-24s browser links %5d · +%3d → %3d of %3d", amc, len(links), len(m), stats[amc][1] + len(m), stats[amc][2])
    lists = {amc: list_page(WEBSITES[amc], all_urls.get(amc, [])) for amc in by_amc if amc in WEBSITES}
    # a fund house whose site was unreachable this time keeps last week's links
    down = {f["code"] for a, fs in by_amc.items() if not all_urls.get(a) for f in fs}
    for k, v in prev.items():
        if not k.startswith("_") and int(k) in down and int(k) not in res:
            res[int(k)] = v
    out = {str(k): v for k, v in sorted(res.items())}
    out["_asOf"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out["_sites"] = {a: WEBSITES[a] for a in sorted(by_amc) if a in WEBSITES}
    out["_lists"] = lists
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    log.info("Scheme pages for %d of %d funds", len(out) - 1, len(scr["rows"]))


if __name__ == "__main__":
    main()
