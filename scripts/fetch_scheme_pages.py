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
                       r"media-?kit|handbook|active-?share|portfolio/|sitemap", re.I)
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


def url_tokens(u: str) -> tuple[set, set]:
    """(tokens of the whole path, tokens of the most specific part) — plan codes such as "nx-dg" are ignored."""
    path = unquote(urlparse(u).path).lower()
    segs = [s for s in path.split("/") if s]
    clean = lambda x: H.tokens(re.sub(r"\b(html?|aspx|php|direct|regular|growth|plan|option)\b", " ", re.sub(r"[-_+.()]+", " ", x)))
    allt = set().union(*[clean(s) for s in segs]) - GENERIC if segs else set()
    named = [s for s in segs if len([t for t in clean(s) - GENERIC if len(t) >= 3]) >= 2] or segs[-1:]
    return allt, (clean(named[-1]) - GENERIC) if named else set()


def match(funds: list[dict], urls: list[str], brand: set) -> dict[int, str]:
    out = {}
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
            ft = H.tokens(nm) - brand - GENERIC
            if not ft:
                continue
            for u, allt, spec in cands:
                if ft <= allt and ft & spec:
                    extra = len(spec - ft)
                    if extra <= 3:
                        low = u.lower()
                        plan = 0 if re.search(r"direct|dir-g|-dg\b", low) else (2 if re.search(r"regular|reg-g|-rg\b", low) else 1)
                        best.append((extra, plan, len(u), u))
        if not best:
            continue
        best.sort()
        top = [b for b in best if b[:2] == best[0][:2]]
        # several different scheme pages fit equally well → too ambiguous to link
        stems = {re.sub(r"/(direct|regular)[^/]*$|[-/](dir|reg)[-_]?g(rowth)?$", "", urlparse(b[3]).path.rstrip("/").lower()) for b in top}
        if len(stems) > 1:
            continue
        out[f["code"]] = best[0][3]
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

    def work(amc):
        site = WEBSITES.get(amc)
        if not site:
            return amc, {}, 0
        urls = sitemap_urls(site)
        brand = set(BRAND_WORDS.findall(amc.lower())) | {"mf", "mutual", "amc", "india", "asset", "management"}
        m = match(by_amc[amc], urls, brand)
        if len(m) < 0.6 * len(by_amc[amc]) and urls:
            fundish = [u for u in urls if re.search(r"fund|scheme|product", u, re.I) and not SKIP_PATH.search(urlparse(u).path)]
            log.info("  sample %s: %s", amc, " | ".join((fundish or urls)[:12]))
        return amc, m, len(urls)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for amc, m, n in ex.map(work, sorted(by_amc)):
            res.update(m)
            stats[amc] = (n, len(m), len(by_amc[amc]))
            log.info("%-24s sitemap URLs %6d · matched %3d of %3d", amc, n, len(m), len(by_amc[amc]))
    # keep last week's link for a fund whose fund house site was unreachable this time
    for k, v in prev.items():
        if not k.startswith("_") and k not in {str(c) for c in res} and stats.get(next((a for a, fs in by_amc.items()
                                                                                     if any(str(f["code"]) == k for f in fs)), ""), (1,))[0] == 0:
            res[int(k)] = v
    out = {str(k): v for k, v in sorted(res.items())}
    out["_asOf"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    log.info("Scheme pages for %d of %d funds", len(out) - 1, len(scr["rows"]))


if __name__ == "__main__":
    main()
