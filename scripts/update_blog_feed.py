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
# Each category gets up to MAX_PER_CAT items, drawn from the listed feeds.
FEEDS: dict[str, list[dict[str, str]]] = {
    "technology": [
        {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge"},
        {"url": "https://feeds.arstechnica.com/arstechnica/index", "source": "Ars Technica"},
        {"url": "https://feeds.feedburner.com/TechCrunch/", "source": "TechCrunch"},
    ],
    "finance": [
        {"url": "https://www.investing.com/rss/news_25.rss", "source": "Investing.com"},
        {"url": "https://feeds.marketwatch.com/marketwatch/topstories/", "source": "MarketWatch"},
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
    ],
    "politics": [
        {"url": "https://feeds.reuters.com/Reuters/PoliticsNews", "source": "Reuters"},
        {"url": "https://feeds.bbci.co.uk/news/politics/rss.xml", "source": "BBC"},
        {"url": "https://www.thehindu.com/news/national/feeder/default.rss", "source": "The Hindu"},
    ],
    "tax": [
        {"url": "https://www.livemint.com/rss/money", "source": "Mint Money"},
        {"url": "https://economictimes.indiatimes.com/rssfeeds/wealth/tax/articlelist/1466318837.cms", "source": "ET Wealth"},
    ],
    "mutual_funds": [
        {"url": "https://www.moneycontrol.com/rss/mfnews.xml", "source": "Moneycontrol MF"},
        {"url": "https://www.business-standard.com/rss/markets/mutual-funds-104.rss", "source": "Business Standard MF"},
        {"url": "https://www.morningstar.com/feeds/articles", "source": "Morningstar"},
    ],
    "etf": [
        {"url": "https://www.etf.com/rss/news.xml", "source": "ETF.com"},
        {"url": "https://www.etftrends.com/feed/", "source": "ETF Trends"},
    ],
    "stocks": [
        {"url": "https://feeds.marketwatch.com/marketwatch/marketpulse/", "source": "MarketWatch"},
        {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "source": "ET Markets"},
        {"url": "https://www.investing.com/rss/news_287.rss", "source": "Investing.com Stocks"},
    ],
    "brokers": [
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
        {"url": "https://economictimes.indiatimes.com/markets/stocks/news/articlelist/2146843.cms", "source": "ET Stocks"},
    ],
    "inventions": [
        {"url": "https://www.sciencedaily.com/rss/matter_energy/inventions.xml", "source": "ScienceDaily"},
        {"url": "https://www.newscientist.com/feed/home/", "source": "New Scientist"},
    ],
    "offers": [
        {"url": "https://www.livemint.com/rss/money", "source": "Mint Money"},
    ],
    "ipo": [
        {"url": "https://economictimes.indiatimes.com/markets/ipo/news/articlelist/74706482.cms", "source": "ET IPO"},
        {"url": "https://www.livemint.com/rss/markets", "source": "Mint Markets"},
    ],
    "nfo": [
        {"url": "https://www.moneycontrol.com/rss/mfnews.xml", "source": "Moneycontrol MF"},
        {"url": "https://www.business-standard.com/rss/markets/mutual-funds-104.rss", "source": "Business Standard MF"},
    ],
    "blockchain": [
        {"url": "https://cointelegraph.com/rss/tag/blockchain", "source": "CoinTelegraph"},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk"},
    ],
    "crypto": [
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk"},
        {"url": "https://cointelegraph.com/rss", "source": "CoinTelegraph"},
        {"url": "https://decrypt.co/feed", "source": "Decrypt"},
    ],
    "semiconductor": [
        {"url": "https://www.eetimes.com/feed/", "source": "EE Times"},
        {"url": "https://semiengineering.com/feed/", "source": "Semiconductor Engineering"},
    ],
    "ai": [
        {"url": "https://venturebeat.com/category/ai/feed/", "source": "VentureBeat AI"},
        {"url": "https://www.artificialintelligence-news.com/feed/", "source": "AI News"},
        {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "source": "The Verge AI"},
    ],
    "space": [
        {"url": "https://www.nasa.gov/feed/", "source": "NASA"},
        {"url": "https://www.space.com/feeds/all", "source": "Space.com"},
    ],
}

MAX_PER_CAT = 10
ITEM_TIMEOUT = 12


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


def normalise_pub(s: str) -> str:
    """Best-effort date string normaliser → 'Apr 29, 2026'."""
    if not s:
        return ""
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt.strftime("%b %d, %Y")
        except ValueError:
            continue
    return s[:24]


def trim_summary(text: str, words: int = 28) -> str:
    text = strip_html(text)
    parts = text.split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def main() -> int:
    out: dict[str, Any] = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
                seen.add(key)
                domain = urlparse(it["link"]).hostname or ""
                cat_items.append({
                    "title": strip_html(it["title"]),
                    "url": it["link"],
                    "summary": trim_summary(it.get("desc", ""), words=32),
                    "source": label,
                    "domain": domain,
                    "date": normalise_pub(it.get("pub", "")),
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
