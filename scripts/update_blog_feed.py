#!/usr/bin/env python3
"""
VilfinTV Blog Intelligence Hub — Daily RSS Feed Updater
========================================================
Fetches 5–10 recent items per category from public RSS feeds and writes a
unified JSON file the static blog page reads at load. Runs once per day.

Output: data/blog_feed.json
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = REPO_ROOT / "data" / "blog_feed.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; VilfinTV-BlogBot/1.0; +https://vilfin-tv.github.io/MultiScreener)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
})

# ─── Per-category RSS feed list ────────────────────────────────────────────────
# Rule: primary feeds first, then Google News RSS as a guaranteed fallback.
# Google News RSS always returns ~10 fresh items and never requires auth.
# GN_IN = India locale, GN_US = US/global locale.
def _gn(q: str, india: bool = False, when: str = "") -> dict[str, str]:
    loc = "en-IN&gl=IN&ceid=IN:en" if india else "en&gl=US&ceid=US:en"
    when_part = f"+when:{when}" if when else ""
    return {"url": f"https://news.google.com/rss/search?q={q}{when_part}&hl={loc}", "source": "Google News"}

FEEDS: dict[str, list[dict[str, str]]] = {
    # ── Markets & Money ──────────────────────────────────────────────────────
    "finance": [
        {"url": "https://feeds.marketwatch.com/marketwatch/topstories/", "source": "MarketWatch"},
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "source": "ET Markets"},
        _gn("global+stock+market+finance+news"),
    ],
    "stocks": [
        {"url": "https://feeds.marketwatch.com/marketwatch/marketpulse/", "source": "MarketWatch"},
        {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "source": "ET Markets"},
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        _gn("stock+market+BSE+NSE+equity+news", india=True),
    ],
    "ipo": [
        {"url": "https://www.moneycontrol.com/rss/iponews.xml", "source": "Moneycontrol IPO"},
        {"url": "https://www.business-standard.com/rss/markets/ipos-130.rss", "source": "Business Standard IPO"},
        {"url": "https://economictimes.indiatimes.com/markets/ipo/news/articlelist/74706482.cms", "source": "ET IPO"},
        {"url": "https://www.cnbc.com/id/100782720/device/rss/rss.html", "source": "CNBC IPOs"},
        _gn("IPO+India+listing+GMP+allotment", india=True),
        _gn("IPO+US+NASDAQ+NYSE+listing"),
    ],
    "nfo": [
        {"url": "https://economictimes.indiatimes.com/rssfeeds/mutual-funds/articlelist/360199.cms", "source": "ET Mutual Funds"},
        {"url": "https://www.moneycontrol.com/rss/mfnews.xml", "source": "Moneycontrol MF"},
        _gn("NFO+new+fund+offer+mutual+fund+India+SEBI", india=True),
        _gn("new+fund+offer+open+close+India+2026", india=True),
    ],
    "mutual_funds": [
        {"url": "https://economictimes.indiatimes.com/rssfeeds/mutual-funds/articlelist/360199.cms", "source": "ET Mutual Funds"},
        {"url": "https://www.moneycontrol.com/rss/mfnews.xml", "source": "Moneycontrol MF"},
        {"url": "https://www.business-standard.com/rss/markets/mutual-funds-104.rss", "source": "Business Standard MF"},
        _gn("mutual+fund+SIP+NAV+India+returns", india=True),
        _gn("mutual+fund+investing+top+performing+2026"),
    ],
    "etf": [
        {"url": "https://www.etftrends.com/feed/", "source": "ETF Trends"},
        {"url": "https://etfdb.com/category/etf-education/feed/", "source": "ETFdb"},
        _gn("ETF+exchange+traded+fund+gold+index+2026"),
        _gn("ETF+India+BSE+Nifty+Sensex+index+fund", india=True),
    ],
    "brokers": [
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        {"url": "https://economictimes.indiatimes.com/markets/stocks/news/articlelist/2146843.cms", "source": "ET Stocks"},
        _gn("Zerodha+Groww+Angel+broker+India+trading+platform", india=True),
        _gn("stock+broker+trading+platform+SEBI+regulation", india=True),
    ],
    "sebi": [
        _gn("SEBI+India+regulation+circular+market+regulator", india=True),
        _gn("SEBI+order+penalty+NSE+BSE+compliance", india=True),
        {"url": "https://www.moneycontrol.com/rss/business.xml", "source": "Moneycontrol"},
        {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "source": "ET Markets"},
    ],
    "tax": [
        {"url": "https://economictimes.indiatimes.com/rssfeeds/wealth/tax/articlelist/1466318837.cms", "source": "ET Wealth Tax"},
        _gn("income+tax+India+ITR+filing+refund+2026", india=True),
        _gn("GST+India+tax+return+filing+deadline+update", india=True),
    ],
    "insurance": [
        {"url": "https://www.insurancejournal.com/rss.xml", "source": "Insurance Journal"},
        {"url": "https://www.livemint.com/rss/insurance", "source": "Mint Insurance"},
        _gn("insurance+India+LIC+health+term+policy", india=True),
        _gn("insurance+claim+premium+IRDA+regulation+2026"),
    ],
    "payment": [
        {"url": "https://www.pymnts.com/feed/", "source": "PYMNTS"},
        {"url": "https://www.finextra.com/rss/headlines.aspx", "source": "Finextra"},
        _gn("UPI+payment+India+fintech+digital+wallet", india=True),
        _gn("digital+payment+fintech+Visa+Mastercard+news"),
    ],
    "currency": [
        {"url": "https://www.fxstreet.com/rss/news", "source": "FXStreet"},
        {"url": "https://www.dailyfx.com/feeds/all", "source": "DailyFX"},
        _gn("forex+currency+USD+INR+EUR+exchange+rate"),
        _gn("rupee+dollar+rate+RBI+forex+reserve", india=True),
    ],
    "blockchain": [
        {"url": "https://cointelegraph.com/rss/tag/blockchain", "source": "CoinTelegraph"},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk"},
        _gn("blockchain+Web3+DeFi+technology+news+2026"),
    ],
    "crypto": [
        {"url": "https://cointelegraph.com/rss", "source": "CoinTelegraph"},
        {"url": "https://decrypt.co/feed", "source": "Decrypt"},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk"},
        _gn("Bitcoin+Ethereum+crypto+price+news+2026"),
    ],
    "offers": [
        {"url": "https://www.livemint.com/rss/money", "source": "Mint Money"},
        _gn("bank+offer+cashback+credit+card+deal+India", india=True),
        _gn("discount+offer+sale+shopping+deal+India+2026", india=True),
    ],
    # ── India Regional ───────────────────────────────────────────────────────
    "bollywood": [
        {"url": "https://www.bollywoodhungama.com/feed/", "source": "Bollywood Hungama"},
        {"url": "https://www.filmfare.com/rss/rss.xml", "source": "Filmfare"},
        _gn("Bollywood+movie+film+actor+actress+OTT+2026", india=True),
        _gn("Hindi+cinema+box+office+release+streaming+India", india=True),
    ],
    "mumbai": [
        _gn("Mumbai+latest+news+Maharashtra+development", india=True, when="30d"),
        _gn("Mumbai+metro+infrastructure+BMC+project+update", india=True, when="30d"),
        _gn("Mumbai+real+estate+business+startup+city+2026", india=True, when="14d"),
    ],
    "tamil_nadu": [
        _gn("Tamil+Nadu+latest+news+Chennai+state+government", india=True, when="30d"),
        _gn("Kollywood+Tamil+cinema+movie+release+actor+news", india=True, when="14d"),
        _gn("Tamil+Nadu+development+business+technology+2026", india=True, when="30d"),
    ],
    "kerala": [
        _gn("Kerala+latest+news+state+government+Kochi+Trivandrum", india=True, when="30d"),
        _gn("Kerala+tourism+flood+development+health+news", india=True, when="30d"),
        _gn("Malayalam+cinema+Mollywood+movie+OTT+release+2026", india=True, when="14d"),
    ],
    "andhra": [
        _gn("Andhra+Pradesh+Telangana+latest+news+Hyderabad", india=True, when="30d"),
        _gn("Telugu+cinema+Tollywood+movie+release+actor+news", india=True, when="14d"),
        _gn("Andhra+Telangana+government+infrastructure+development", india=True, when="30d"),
    ],
    "bangalore": [
        _gn("Bangalore+Bengaluru+latest+news+tech+startup+Karnataka", india=True, when="30d"),
        _gn("Bengaluru+metro+real+estate+IT+industry+jobs", india=True, when="30d"),
        _gn("Karnataka+government+Bengaluru+infrastructure+news", india=True, when="30d"),
    ],
    "pune": [
        _gn("Pune+latest+news+Maharashtra+development+city", india=True, when="30d"),
        _gn("Pune+real+estate+IT+industry+startup+infrastructure", india=True, when="30d"),
        _gn("Pune+metro+PMC+education+business+news+2026", india=True, when="30d"),
    ],
    "delhi": [
        _gn("Delhi+latest+news+NCR+government+development", india=True, when="30d"),
        _gn("Delhi+metro+infrastructure+air+quality+city+update", india=True, when="30d"),
        _gn("Delhi+business+real+estate+education+news+2026", india=True, when="14d"),
    ],
    "gujarat": [
        _gn("Gujarat+latest+news+Ahmedabad+Surat+state+government", india=True, when="30d"),
        _gn("Gujarat+industry+business+GIFT+city+development", india=True, when="30d"),
        _gn("Gujarat+infrastructure+investment+BJP+news+2026", india=True, when="30d"),
    ],
    # ── Technology ───────────────────────────────────────────────────────────
    "technology": [
        {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge"},
        {"url": "https://feeds.arstechnica.com/arstechnica/index", "source": "Ars Technica"},
        {"url": "https://feeds.feedburner.com/TechCrunch/", "source": "TechCrunch"},
        _gn("technology+news+innovation+2026"),
    ],
    "ai": [
        {"url": "https://venturebeat.com/category/ai/feed/", "source": "VentureBeat AI"},
        {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "source": "The Verge AI"},
        {"url": "https://www.artificialintelligence-news.com/feed/", "source": "AI News"},
        _gn("artificial+intelligence+ChatGPT+Gemini+LLM+2026"),
    ],
    "semiconductor": [
        {"url": "https://www.eetimes.com/feed/", "source": "EE Times"},
        {"url": "https://semiengineering.com/feed/", "source": "Semiconductor Engineering"},
        _gn("semiconductor+chip+TSMC+Intel+Nvidia+foundry+2026"),
    ],
    "data_center": [
        {"url": "https://www.datacenterdynamics.com/rss/", "source": "DataCenter Dynamics"},
        {"url": "https://www.datacenterknowledge.com/rss.xml", "source": "DataCenter Knowledge"},
        _gn("data+center+cloud+AI+infrastructure+hyperscaler+2026"),
    ],
    "internet": [
        {"url": "https://feeds.arstechnica.com/arstechnica/index", "source": "Ars Technica"},
        {"url": "https://www.wired.com/feed/rss", "source": "WIRED"},
        _gn("internet+broadband+5G+connectivity+online+platform+2026"),
    ],
    "mobile": [
        {"url": "https://www.gsmarena.com/rss-news-reviews.php3", "source": "GSMArena"},
        {"url": "https://www.androidauthority.com/feed/", "source": "Android Authority"},
        {"url": "https://9to5mac.com/feed/", "source": "9to5Mac"},
        {"url": "https://feeds.feedburner.com/91mobiles", "source": "91Mobiles"},
        _gn("smartphone+mobile+launch+review+Android+iPhone+India+2026"),
    ],
    "inventions": [
        {"url": "https://www.sciencedaily.com/rss/matter_energy/inventions.xml", "source": "ScienceDaily"},
        {"url": "https://www.newscientist.com/feed/home/", "source": "New Scientist"},
        _gn("invention+patent+breakthrough+technology+innovation+2026"),
    ],
    "space": [
        {"url": "https://www.nasa.gov/feed/", "source": "NASA"},
        {"url": "https://www.space.com/feeds/all", "source": "Space.com"},
        _gn("space+rocket+satellite+NASA+SpaceX+ISRO+launch+2026"),
    ],
    # ── Health & Energy ──────────────────────────────────────────────────────
    "health": [
        {"url": "https://feeds.bbci.co.uk/news/health/rss.xml", "source": "BBC Health"},
        {"url": "https://www.healthline.com/rss/news", "source": "Healthline"},
        {"url": "https://www.medicalnewstoday.com/newsfeeds/rss/medical_all.xml", "source": "Medical News Today"},
        _gn("health+wellness+fitness+diet+disease+prevention+2026"),
    ],
    "medicine": [
        {"url": "https://www.nih.gov/news-events/news-releases/feed.xml", "source": "NIH"},
        {"url": "https://www.statnews.com/feed/", "source": "STAT News"},
        {"url": "https://www.medscape.com/cx/rssfeeds/2900.xml", "source": "Medscape"},
        _gn("medical+research+drug+approval+FDA+clinical+trial+2026"),
    ],
    "hospital": [
        {"url": "https://www.healthcaredive.com/feeds/news/", "source": "Healthcare Dive"},
        {"url": "https://www.beckershospitalreview.com/rss/all-articles.xml", "source": "Becker's Hospital Review"},
        _gn("hospital+healthcare+patient+care+India+Apollo+Fortis", india=True),
        _gn("hospital+healthcare+system+investment+mergers+2026"),
    ],
    "energy": [
        {"url": "https://oilprice.com/rss/main", "source": "OilPrice"},
        {"url": "https://www.utilitydive.com/feeds/news/", "source": "Utility Dive"},
        {"url": "https://www.rechargenews.com/rss", "source": "Recharge News"},
        _gn("oil+gas+renewable+energy+solar+wind+EV+battery+2026"),
    ],
    # ── Lifestyle ────────────────────────────────────────────────────────────
    "lifestyle": [
        {"url": "https://www.thehindu.com/life-and-style/feeder/default.rss", "source": "The Hindu Lifestyle"},
        {"url": "https://lifehacker.com/feed/rss", "source": "Lifehacker"},
        _gn("lifestyle+wellness+personal+finance+productivity+2026"),
    ],
    "food": [
        {"url": "https://www.foodandwine.com/syndication/rss", "source": "Food & Wine"},
        {"url": "https://www.eater.com/rss/index.xml", "source": "Eater"},
        {"url": "https://www.bbcgoodfood.com/feed", "source": "BBC Good Food"},
        _gn("food+recipe+restaurant+nutrition+trend+2026"),
    ],
    "fashion": [
        {"url": "https://www.vogue.com/feed/rss", "source": "Vogue"},
        {"url": "https://www.gq.com/feed/rss", "source": "GQ"},
        {"url": "https://www.harpersbazaar.com/rss/all.xml/", "source": "Harper's Bazaar"},
        _gn("fashion+luxury+brand+design+trend+2026"),
    ],
    "entertainment": [
        {"url": "https://www.hollywoodreporter.com/feed", "source": "Hollywood Reporter"},
        {"url": "https://variety.com/feed/", "source": "Variety"},
        {"url": "https://www.rollingstone.com/feed/", "source": "Rolling Stone"},
        _gn("entertainment+celebrity+music+show+OTT+streaming+2026"),
    ],
    "movie": [
        {"url": "https://www.indiewire.com/feed/", "source": "IndieWire"},
        {"url": "https://variety.com/v/film/feed/", "source": "Variety Film"},
        {"url": "https://www.hollywoodreporter.com/t/movies/feed/", "source": "Hollywood Reporter Film"},
        _gn("movie+film+box+office+release+Netflix+OTT+2026"),
        _gn("Bollywood+Hollywood+movie+review+release+2026", india=True),
    ],
    # ── Other ────────────────────────────────────────────────────────────────
    "politics": [
        {"url": "https://feeds.bbci.co.uk/news/politics/rss.xml", "source": "BBC"},
        {"url": "https://www.thehindu.com/news/national/feeder/default.rss", "source": "The Hindu"},
        {"url": "https://feeds.reuters.com/Reuters/PoliticsNews", "source": "Reuters"},
        _gn("India+politics+parliament+election+government+2026", india=True),
        _gn("US+politics+White+House+Congress+policy+2026"),
    ],
}

MAX_PER_CAT = 12   # fetch up to 12; output is capped at 10 after dedup
ITEM_TIMEOUT = 12
MAX_AGE_DAYS = 30  # drop articles published more than 30 days ago


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_rss(url: str) -> list[dict[str, Any]]:
    try:
        r = SESSION.get(url, timeout=ITEM_TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"  fetch failed: {url} → {e}")
        return []
    items: list[dict[str, Any]] = []
    try:
        # Strip BOM and namespaces for friendlier parsing
        body = r.content.lstrip(b"\xef\xbb\xbf")
        root = ET.fromstring(body)
        # RSS 2.0
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            desc = (
                it.findtext("description")
                or it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
                or ""
            ).strip()
            pub = (it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
            if title and link:
                items.append({"title": title, "link": link, "desc": desc, "pub": pub})
        # Atom fallback
        if not items:
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                t_el = entry.find("{http://www.w3.org/2005/Atom}title")
                l_el = entry.find("{http://www.w3.org/2005/Atom}link")
                s_el = entry.find("{http://www.w3.org/2005/Atom}summary")
                p_el = entry.find("{http://www.w3.org/2005/Atom}updated")
                title = strip_html(t_el.text) if t_el is not None else ""
                link = (l_el.get("href") or "").strip() if l_el is not None else ""
                desc = strip_html(s_el.text) if s_el is not None else ""
                pub = (p_el.text or "").strip() if p_el is not None else ""
                if title and link:
                    items.append({"title": title, "link": link, "desc": desc, "pub": pub})
    except ET.ParseError as e:
        log.warning(f"  XML parse error: {url} → {e}")
    return items


_PUB_FMTS = (
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d",
)


def normalise_pub(s: str) -> str:
    """Best-effort date string normaliser → 'Apr 29, 2026'."""
    if not s:
        return ""
    for fmt in _PUB_FMTS:
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt.strftime("%b %d, %Y")
        except ValueError:
            continue
    return s[:24]


def parse_pub_dt(s: str) -> datetime | None:
    """Return a timezone-aware datetime for age filtering, or None if unparseable."""
    if not s:
        return None
    for fmt in _PUB_FMTS:
        try:
            dt = datetime.strptime(s.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def trim_summary(text: str, words: int = 28) -> str:
    text = strip_html(text)
    parts = text.split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def main() -> int:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc.replace(tzinfo=timezone.utc)

    out: dict[str, Any] = {
        "generated": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "categories": {},
    }
    grand_total = 0
    for cat, feeds in FEEDS.items():
        log.info(f"📂 {cat}")
        seen: set[str] = set()
        cat_items: list[dict[str, Any]] = []
        for src in feeds:
            url = src["url"]
            label = src["source"]
            log.info(f"  ↳ {label}")
            for it in fetch_rss(url):
                key = it["link"]
                if key in seen:
                    continue
                # Age filter: skip items older than MAX_AGE_DAYS
                pub_raw = it.get("pub", "")
                pub_dt = parse_pub_dt(pub_raw)
                if pub_dt and (cutoff - pub_dt).days > MAX_AGE_DAYS:
                    continue
                seen.add(key)
                domain = urlparse(it["link"]).hostname or ""
                cat_items.append({
                    "title": strip_html(it["title"]),
                    "url": it["link"],
                    "summary": trim_summary(it.get("desc", ""), words=32),
                    "source": label,
                    "domain": domain,
                    "date": normalise_pub(pub_raw),
                })
                if len(cat_items) >= MAX_PER_CAT:
                    break
            if len(cat_items) >= MAX_PER_CAT:
                break
        # Trim to 5–10 items: prefer more if available, but always at least the first 5
        cat_items = cat_items[:MAX_PER_CAT]
        out["categories"][cat] = cat_items
        grand_total += len(cat_items)
        log.info(f"  → {len(cat_items)} items")
    log.info(f"✓ Total {grand_total} items across {len(FEEDS)} categories")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"✓ Wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
