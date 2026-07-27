#!/usr/bin/env python3
"""
VilfinTV Blog Intelligence Hub — Daily RSS Feed Updater
========================================================
Fetches up to MAX_PER_CAT new items per category from public RSS feeds and
ACCUMULATES them into data/blog_feed.json.  Articles are kept for MAX_AGE_DAYS
(7 days) so each tab shows a rolling week of coverage rather than only today's
snapshot.  Runs once per day via GitHub Actions.

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
        _gn("global+stock+market+finance+economy+news"),
        _gn("India+finance+economy+RBI+budget+market+news", india=True),
    ],
    "stocks": [
        {"url": "https://feeds.marketwatch.com/marketwatch/marketpulse/", "source": "MarketWatch"},
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        _gn("stock+market+BSE+NSE+Sensex+Nifty+equity+news", india=True),
        _gn("US+stock+market+S&P+Nasdaq+Dow+earnings+news"),
    ],
    "ipo": [
        {"url": "https://www.moneycontrol.com/rss/iponews.xml", "source": "Moneycontrol IPO"},
        _gn("IPO+India+listing+GMP+allotment+subscription+open", india=True, when="7d"),
        _gn("SME+IPO+BSE+NSE+India+listing+GMP+open+close", india=True, when="7d"),
        _gn("IPO+US+NASDAQ+NYSE+listing+debut+2026", when="7d"),
        _gn("mainboard+IPO+India+SEBI+DRHP+approval", india=True, when="7d"),
    ],
    "nfo": [
        {"url": "https://www.moneycontrol.com/rss/mfnews.xml", "source": "Moneycontrol MF"},
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        _gn("NFO+new+fund+offer+mutual+fund+India+open+close", india=True),
        _gn("new+fund+offer+NFO+launch+India+AMFI+SEBI+2026", india=True),
        _gn("mutual+fund+NFO+subscription+open+India+2026", india=True),
    ],
    "mutual_funds": [
        {"url": "https://www.moneycontrol.com/rss/mfnews.xml", "source": "Moneycontrol MF"},
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        _gn("mutual+fund+SIP+NAV+India+returns+AMFI+2026", india=True),
        _gn("mutual+fund+AUM+equity+debt+hybrid+performance+India", india=True),
    ],
    "etf": [
        {"url": "https://www.etftrends.com/feed/", "source": "ETF Trends"},
        _gn("ETF+exchange+traded+fund+flows+inflows+gold+index"),
        _gn("ETF+India+BSE+Nifty+Sensex+gold+silver+index+fund", india=True),
    ],
    "brokers": [
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        _gn("Zerodha+Groww+Angel+broker+India+trading+SEBI+update", india=True),
        _gn("stock+broker+trading+platform+regulation+India+news", india=True),
    ],
    "sebi": [
        {"url": "https://www.moneycontrol.com/rss/business.xml", "source": "Moneycontrol"},
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        _gn("SEBI+India+regulation+circular+order+market+regulator", india=True),
        _gn("SEBI+NSE+BSE+compliance+penalty+circular+India+2026", india=True),
        _gn("SEBI+India+IPO+FPI+insider+trading+regulation+2026", india=True),
    ],
    "tax": [
        {"url": "https://www.livemint.com/rss/money", "source": "Mint Money"},
        _gn("income+tax+India+ITR+filing+refund+deadline+2026", india=True),
        _gn("GST+India+tax+return+filing+update+deadline", india=True),
        _gn("India+income+tax+TDS+TCS+budget+rebate+slab+2026", india=True),
        _gn("ITR+filing+AY+2026+deadline+penalty+India", india=True),
    ],
    "insurance": [
        {"url": "https://www.livemint.com/rss/insurance", "source": "Mint Insurance"},
        _gn("insurance+India+LIC+health+term+IRDA+premium+policy", india=True),
        _gn("insurance+claim+settlement+premium+life+motor+India", india=True),
        _gn("insurance+global+health+life+industry+news+2026"),
    ],
    "payment": [
        {"url": "https://www.pymnts.com/feed/", "source": "PYMNTS"},
        {"url": "https://www.finextra.com/rss/headlines.aspx", "source": "Finextra"},
        _gn("UPI+payment+India+NPCI+fintech+digital+wallet", india=True),
        _gn("digital+payment+fintech+Visa+Mastercard+PayPal+news"),
    ],
    "currency": [
        {"url": "https://www.fxstreet.com/rss/news", "source": "FXStreet"},
        {"url": "https://www.dailyfx.com/feeds/all", "source": "DailyFX"},
        _gn("forex+currency+USD+INR+EUR+JPY+exchange+rate"),
        _gn("rupee+dollar+rate+RBI+forex+reserve+India", india=True),
    ],
    "blockchain": [
        {"url": "https://cointelegraph.com/rss/tag/blockchain", "source": "CoinTelegraph"},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk"},
        _gn("blockchain+Web3+DeFi+Ethereum+smart+contract+news"),
    ],
    "crypto": [
        {"url": "https://cointelegraph.com/rss", "source": "CoinTelegraph"},
        {"url": "https://decrypt.co/feed", "source": "Decrypt"},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk"},
        _gn("Bitcoin+Ethereum+crypto+price+market+news"),
    ],
    "offers": [
        {"url": "https://www.livemint.com/rss/money", "source": "Mint Money"},
        _gn("bank+offer+cashback+credit+card+deal+reward+India", india=True),
        _gn("discount+sale+offer+coupon+shopping+deal+India", india=True),
    ],
    # ── India Regional ───────────────────────────────────────────────────────
    # Google News when:7d keeps results within the same 7-day window as MAX_AGE_DAYS
    "bollywood": [
        {"url": "https://www.bollywoodhungama.com/feed/", "source": "Bollywood Hungama"},
        _gn("Bollywood+Hindi+movie+film+actor+actress+OTT+news", india=True, when="7d"),
        _gn("Hindi+cinema+box+office+release+trailer+streaming", india=True, when="7d"),
    ],
    "malayalam_cinema": [
        {"url": "https://www.onmanorama.com/entertainment/movies.rss", "source": "OnManorama Movies"},
        {"url": "https://english.mathrubhumi.com/movies/feed", "source": "Mathrubhumi Movies"},
        _gn("Malayalam+cinema+Mollywood+movie+actor+OTT+release+2026", india=True, when="7d"),
        _gn("Mollywood+box+office+Kerala+film+award+streaming+2026", india=True, when="7d"),
    ],
    "tamil_cinema": [
        {"url": "https://www.behindwoods.com/feed/", "source": "Behindwoods"},
        {"url": "https://www.cinemaexpress.com/feed/", "source": "Cinema Express"},
        _gn("Kollywood+Tamil+cinema+movie+actor+release+OTT+2026", india=True, when="7d"),
        _gn("Tamil+box+office+Chennai+Vijay+Ajith+Rajinikanth+film+2026", india=True, when="7d"),
    ],
    "telugu_cinema": [
        {"url": "https://www.123telugu.com/feed", "source": "123Telugu"},
        {"url": "https://www.gulte.com/feed/", "source": "Gulte"},
        _gn("Tollywood+Telugu+cinema+movie+actor+release+OTT+2026", india=True, when="7d"),
        _gn("Telugu+box+office+Hyderabad+Prabhas+Mahesh+Allu+film+2026", india=True, when="7d"),
    ],
    "kannada_cinema": [
        {"url": "https://www.deccanherald.com/rss/entertainment.rss", "source": "Deccan Herald Ent"},
        _gn("Sandalwood+Kannada+cinema+movie+actor+release+OTT+2026", india=True, when="7d"),
        _gn("Kannada+film+Yash+Rishab+Shetty+box+office+Karnataka+2026", india=True, when="7d"),
    ],
    "mumbai": [
        _gn("Mumbai+latest+news+Maharashtra+city+development", india=True, when="7d"),
        _gn("Mumbai+metro+infrastructure+BMC+real+estate+project", india=True, when="7d"),
        _gn("Mumbai+business+startup+economy+Dharavi+redevelopment", india=True, when="7d"),
    ],
    "tamil_nadu": [
        _gn("Tamil+Nadu+latest+news+Chennai+government+policy", india=True, when="7d"),
        _gn("Kollywood+Tamil+cinema+movie+actor+release+OTT+news", india=True, when="7d"),
        _gn("Tamil+Nadu+industry+technology+investment+development", india=True, when="7d"),
    ],
    "kerala": [
        _gn("Kerala+latest+news+government+Kochi+Thiruvananthapuram", india=True, when="7d"),
        _gn("Kerala+tourism+development+health+infrastructure+news", india=True, when="7d"),
        _gn("Malayalam+cinema+Mollywood+movie+OTT+release+news", india=True, when="7d"),
    ],
    "andhra": [
        _gn("Andhra+Pradesh+Telangana+latest+news+Hyderabad", india=True, when="7d"),
        _gn("Telugu+cinema+Tollywood+movie+actor+release+news", india=True, when="7d"),
        _gn("Andhra+Telangana+infrastructure+industry+investment", india=True, when="7d"),
    ],
    "bangalore": [
        _gn("Bangalore+Bengaluru+latest+news+tech+startup+Karnataka", india=True, when="7d"),
        _gn("Bengaluru+metro+real+estate+IT+industry+jobs+startup", india=True, when="7d"),
        _gn("Karnataka+government+Bengaluru+infrastructure+investment", india=True, when="7d"),
    ],
    "pune": [
        _gn("Pune+latest+news+Maharashtra+city+development", india=True, when="7d"),
        _gn("Pune+real+estate+IT+industry+startup+metro+PMC", india=True, when="7d"),
        _gn("Pune+education+business+investment+news+2026", india=True, when="7d"),
    ],
    "delhi": [
        _gn("Delhi+latest+news+NCR+government+city+development", india=True, when="7d"),
        _gn("Delhi+metro+infrastructure+air+quality+transport+news", india=True, when="7d"),
        _gn("Delhi+NCR+business+real+estate+investment+education", india=True, when="7d"),
    ],
    "gujarat": [
        _gn("Gujarat+latest+news+Ahmedabad+Surat+government", india=True, when="7d"),
        _gn("Gujarat+industry+GIFT+city+business+investment+news", india=True, when="7d"),
        _gn("Gujarat+infrastructure+development+Vibrant+summit", india=True, when="7d"),
    ],
    # ── Technology ───────────────────────────────────────────────────────────
    "technology": [
        {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge"},
        {"url": "https://feeds.arstechnica.com/arstechnica/index", "source": "Ars Technica"},
        {"url": "https://feeds.feedburner.com/TechCrunch/", "source": "TechCrunch"},
        _gn("technology+news+innovation+product+launch+2026"),
    ],
    "ai": [
        {"url": "https://venturebeat.com/category/ai/feed/", "source": "VentureBeat AI"},
        {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "source": "The Verge AI"},
        {"url": "https://www.artificialintelligence-news.com/feed/", "source": "AI News"},
        _gn("artificial+intelligence+LLM+ChatGPT+Gemini+Claude+agents"),
    ],
    "semiconductor": [
        {"url": "https://www.eetimes.com/feed/", "source": "EE Times"},
        {"url": "https://semiengineering.com/feed/", "source": "Semiconductor Engineering"},
        _gn("semiconductor+chip+TSMC+Nvidia+Intel+AMD+foundry+news"),
    ],
    "data_center": [
        {"url": "https://www.datacenterdynamics.com/rss/", "source": "DataCenter Dynamics"},
        {"url": "https://www.datacenterknowledge.com/rss.xml", "source": "DataCenter Knowledge"},
        _gn("data+center+cloud+AI+infrastructure+hyperscaler+GPU+news"),
    ],
    "internet": [
        {"url": "https://feeds.arstechnica.com/arstechnica/index", "source": "Ars Technica"},
        {"url": "https://www.wired.com/feed/rss", "source": "WIRED"},
        _gn("internet+broadband+5G+6G+connectivity+platform+news"),
    ],
    "mobile": [
        {"url": "https://www.gsmarena.com/rss-news-reviews.php3", "source": "GSMArena"},
        {"url": "https://www.androidauthority.com/feed/", "source": "Android Authority"},
        {"url": "https://9to5mac.com/feed/", "source": "9to5Mac"},
        _gn("smartphone+mobile+phone+launch+review+Android+iPhone+India"),
    ],
    "inventions": [
        {"url": "https://www.newscientist.com/feed/home/", "source": "New Scientist"},
        {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "source": "BBC Science"},
        _gn("invention+patent+breakthrough+technology+innovation+research+2026"),
        _gn("new+discovery+science+engineering+materials+robotics+2026"),
    ],
    "space": [
        {"url": "https://www.nasa.gov/feed/", "source": "NASA"},
        {"url": "https://www.space.com/feeds/all", "source": "Space.com"},
        _gn("space+rocket+satellite+NASA+SpaceX+ISRO+launch+moon+mars"),
    ],
    # ── Health & Energy ──────────────────────────────────────────────────────
    "health": [
        {"url": "https://feeds.bbci.co.uk/news/health/rss.xml", "source": "BBC Health"},
        {"url": "https://www.healthline.com/rss/news", "source": "Healthline"},
        {"url": "https://www.medicalnewstoday.com/newsfeeds/rss/medical_all.xml", "source": "Medical News Today"},
        _gn("health+wellness+fitness+diet+disease+prevention+news"),
    ],
    "medicine": [
        {"url": "https://www.statnews.com/feed/", "source": "STAT News"},
        {"url": "https://www.medscape.com/cx/rssfeeds/2900.xml", "source": "Medscape"},
        {"url": "https://feeds.bbci.co.uk/news/health/rss.xml", "source": "BBC Health"},
        _gn("medicine+drug+FDA+clinical+trial+research+treatment+news"),
    ],
    "hospital": [
        {"url": "https://www.healthcaredive.com/feeds/news/", "source": "Healthcare Dive"},
        _gn("hospital+healthcare+patient+care+India+Apollo+Fortis+Narayana", india=True),
        _gn("hospital+healthcare+system+investment+mergers+capacity+news"),
    ],
    "energy": [
        {"url": "https://oilprice.com/rss/main", "source": "OilPrice"},
        {"url": "https://www.utilitydive.com/feeds/news/", "source": "Utility Dive"},
        {"url": "https://www.rechargenews.com/rss", "source": "Recharge News"},
        _gn("oil+gas+renewable+energy+solar+wind+EV+battery+power"),
    ],
    # ── Lifestyle ────────────────────────────────────────────────────────────
    "lifestyle": [
        {"url": "https://www.thehindu.com/life-and-style/feeder/default.rss", "source": "The Hindu Lifestyle"},
        {"url": "https://lifehacker.com/feed/rss", "source": "Lifehacker"},
        _gn("lifestyle+wellness+productivity+personal+finance+travel+news"),
    ],
    "food": [
        {"url": "https://www.eater.com/rss/index.xml", "source": "Eater"},
        {"url": "https://www.bbcgoodfood.com/feed", "source": "BBC Good Food"},
        _gn("food+recipe+restaurant+nutrition+diet+trend+culinary+news"),
        _gn("India+food+restaurant+cuisine+chef+recipe+2026", india=True),
    ],
    "fashion": [
        {"url": "https://www.vogue.com/feed/rss", "source": "Vogue"},
        {"url": "https://www.gq.com/feed/rss", "source": "GQ"},
        {"url": "https://www.harpersbazaar.com/rss/all.xml/", "source": "Harper's Bazaar"},
        _gn("fashion+luxury+brand+design+trend+style+news+2026"),
    ],
    "entertainment": [
        {"url": "https://www.hollywoodreporter.com/feed", "source": "Hollywood Reporter"},
        {"url": "https://variety.com/feed/", "source": "Variety"},
        {"url": "https://www.rollingstone.com/feed/", "source": "Rolling Stone"},
        _gn("entertainment+celebrity+music+concert+OTT+streaming+news"),
    ],
    "movie": [
        {"url": "https://www.indiewire.com/feed/", "source": "IndieWire"},
        {"url": "https://variety.com/v/film/feed/", "source": "Variety Film"},
        {"url": "https://www.hollywoodreporter.com/t/movies/feed/", "source": "Hollywood Reporter Film"},
        _gn("movie+film+box+office+release+review+Netflix+OTT+2026"),
        _gn("Bollywood+Hollywood+Tamil+movie+release+review+2026", india=True),
    ],
    # ── Other ────────────────────────────────────────────────────────────────
    "politics": [
        {"url": "https://feeds.bbci.co.uk/news/politics/rss.xml", "source": "BBC Politics"},
        {"url": "https://www.thehindu.com/news/national/feeder/default.rss", "source": "The Hindu"},
        {"url": "https://feeds.reuters.com/Reuters/PoliticsNews", "source": "Reuters"},
        _gn("India+politics+parliament+election+government+policy", india=True),
        _gn("US+politics+White+House+Congress+Senate+global+policy"),
    ],
}

# ── Tuning constants ──────────────────────────────────────────────────────────
MAX_PER_CAT   = 12   # max NEW items fetched per category per daily run
MAX_PER_STORE = 50   # max articles kept per category across all days (rolling window)
ITEM_TIMEOUT  = 12   # per-feed HTTP timeout in seconds
MAX_AGE_DAYS  = 7    # articles older than this many days are pruned from the store


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
    "%b %d, %Y",   # stored display format  e.g. "May 20, 2026"
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

    # ── Load existing accumulated data (7-day rolling store) ──────────────────
    existing: dict[str, list[dict[str, Any]]] = {}
    if OUT_FILE.exists():
        try:
            old = json.loads(OUT_FILE.read_text(encoding="utf-8"))
            existing = old.get("categories", {})
            total_stored = sum(len(v) for v in existing.values())
            log.info(f"Loaded existing feed: {total_stored} stored items across {len(existing)} categories")
        except Exception as exc:
            log.warning(f"Could not load existing feed: {exc} — starting fresh")

    def is_fresh(item: dict[str, Any]) -> bool:
        """Return True if the article is still within the 7-day retention window."""
        # Primary: fetched_at (ISO, always UTC, most reliable)
        fa = item.get("fetched_at", "")
        if fa:
            try:
                dt = datetime.fromisoformat(fa.replace("Z", "+00:00"))
                return (now_utc - dt).days <= MAX_AGE_DAYS
            except Exception:
                pass
        # Fallback: parse the stored display date (e.g. "May 20, 2026")
        pub_dt = parse_pub_dt(item.get("date", ""))
        if pub_dt:
            return (now_utc - pub_dt).days <= MAX_AGE_DAYS
        return True  # keep if date is unparseable — better safe than pruning

    def sort_key(item: dict[str, Any]) -> datetime:
        """Sort by fetched_at first (reliable), then by publication date."""
        fa = item.get("fetched_at", "")
        if fa:
            try:
                return datetime.fromisoformat(fa.replace("Z", "+00:00"))
            except Exception:
                pass
        return parse_pub_dt(item.get("date", "")) or datetime(2000, 1, 1, tzinfo=timezone.utc)

    out: dict[str, Any] = {
        "generated": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "categories": {},
    }
    grand_total = 0

    for cat, feeds in FEEDS.items():
        log.info(f"📂 {cat}")

        # Step 1 — carry forward existing articles still within the 7-day window
        carried = [it for it in existing.get(cat, []) if is_fresh(it)]
        carried_urls: set[str] = {it["url"] for it in carried if it.get("url")}

        # Step 2 — fetch new articles from RSS feeds (deduplicated against carried)
        new_items: list[dict[str, Any]] = []
        new_urls: set[str] = set()
        for src in feeds:
            url  = src["url"]
            label = src["source"]
            log.info(f"  ↳ {label}")
            for it in fetch_rss(url):
                key = it["link"]
                if key in carried_urls or key in new_urls:
                    continue
                pub_raw = it.get("pub", "")
                pub_dt  = parse_pub_dt(pub_raw)
                if pub_dt and (now_utc - pub_dt).days > MAX_AGE_DAYS:
                    continue
                new_urls.add(key)
                domain = urlparse(it["link"]).hostname or ""
                new_items.append({
                    "title":      strip_html(it["title"]),
                    "url":        it["link"],
                    "summary":    trim_summary(it.get("desc", ""), words=32),
                    "source":     label,
                    "domain":     domain,
                    "date":       normalise_pub(pub_raw),
                    "fetched_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
                if len(new_items) >= MAX_PER_CAT:
                    break
            if len(new_items) >= MAX_PER_CAT:
                break

        # Step 3 — merge: new articles first (higher fetch priority), then carry-overs
        merged = new_items + carried

        # Step 4 — sort newest-first, deduplicate, cap at MAX_PER_STORE
        merged.sort(key=sort_key, reverse=True)
        seen_final: set[str] = set()
        cat_items: list[dict[str, Any]] = []
        for item in merged:
            u = item.get("url", "")
            if u and u not in seen_final:
                seen_final.add(u)
                cat_items.append(item)
            if len(cat_items) >= MAX_PER_STORE:
                break

        out["categories"][cat] = cat_items
        grand_total += len(cat_items)
        log.info(f"  → {len(cat_items)} items  ({len(new_items)} new · {len(carried)} carried over)")

    log.info(f"✓ Total {grand_total} items across {len(FEEDS)} categories")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"✓ Wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
