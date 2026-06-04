#!/usr/bin/env python3
"""
VilfinTV Blog Intelligence Hub — Daily Top ETFs News Feed Updater
========================================================================
Builds data/top_etfs.json — the auto-live half of the Top ETFs board on
blog_intelligence_hub.html. Pulls "top ETFs" news
per country (US, Japan, India) from public RSS feeds (Google News + Moneycontrol),
keeps a rolling MAX_AGE_DAYS window so stale news falls off
automatically, and groups items by country.

The accurate, structured Top 5 ETFs list is managed
separately from the VilfinTV Console and stored in config.json (top_etfs);
the frontend merges both and removes any fund if its rank falls below top 5.

Output: data/top_etfs.json
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
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = REPO_ROOT / "data" / "top_etfs.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; VilfinTV-TopETFBot/1.0; +https://vilfin-tv.github.io/MultiScreener)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
})


def _gn(query: str, loc: str) -> dict[str, str]:
    """Google News RSS search URL. loc = 'us' | 'jp' | 'in'."""
    locales = {
        "us": "hl=en-US&gl=US&ceid=US:en",
        "jp": "hl=ja&gl=JP&ceid=JP:ja",
        "in": "hl=en-IN&gl=IN&ceid=IN:en",
    }
    return {
        "url": f"https://news.google.com/rss/search?q={quote(query)}+when:30d&{locales[loc]}",
        "source": "Google News",
    }


# Per-country feed lists — "top ETF" focus.
COUNTRY_FEEDS: dict[str, list[dict[str, str]]] = {
    "us": [
        _gn("top performing ETFs 2026", "us"),
        _gn("best ETFs to invest", "us"),
        _gn("ETF performance market", "us"),
    ],
    "japan": [
        _gn("おすすめ ETF ランキング", "jp"),
        _gn("好成績 ETF ファンド 2026", "jp"),
        _gn("人気 ETF 利回り", "jp"),
    ],
    "india": [
        {"url": "https://www.moneycontrol.com/rss/mfnews.xml", "source": "Moneycontrol MF"},
        _gn("Nifty ETF OR Sensex ETF OR CPSE ETF OR Bharat 22 ETF", "in"),
        _gn("Nippon India ETF OR SBI ETF OR ICICI Prudential ETF", "in"),
        _gn("NSE BSE domestic ETF returns performance", "in"),
    ],
}

COUNTRY_LABELS = {"us": "United States", "japan": "Japan", "india": "India"}

MAX_PER_COUNTRY = 18    # cap items kept per country
ITEM_TIMEOUT = 12       # per-feed HTTP timeout (s)
MAX_AGE_DAYS = 30       # drop news older than this (stale news falls off)

# Only keep items that look like ETF news (avoids generic market noise)
KEYWORDS = re.compile(
    r"\b(etf|etfs|上場投資信託|ランキング|好成績|おすすめ|returns|performance|best etfs|top etfs)\b",
    re.IGNORECASE,
)


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_rss(url: str) -> list[dict[str, Any]]:
    try:
        r = SESSION.get(url, timeout=ITEM_TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"  fetch failed: {url} → {e}")
        return []
    items: list[dict[str, Any]] = []
    try:
        body = r.content.lstrip(b"\xef\xbb\xbf")
        root = ET.fromstring(body)
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            desc = (it.findtext("description") or "").strip()
            pub = (it.findtext("pubDate") or "").strip()
            if title and link:
                items.append({"title": title, "link": link, "desc": desc, "pub": pub})
        if not items:
            ns = "{http://www.w3.org/2005/Atom}"
            for entry in root.iter(f"{ns}entry"):
                t = entry.find(f"{ns}title")
                l = entry.find(f"{ns}link")
                s = entry.find(f"{ns}summary")
                p = entry.find(f"{ns}updated")
                title = strip_html(t.text) if t is not None else ""
                link = (l.get("href") or "").strip() if l is not None else ""
                if title and link:
                    items.append({
                        "title": title, "link": link,
                        "desc": strip_html(s.text) if s is not None else "",
                        "pub": (p.text or "").strip() if p is not None else "",
                    })
    except ET.ParseError as e:
        log.warning(f"  XML parse error: {url} → {e}")
    return items


_PUB_FMTS = (
    "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%b %d, %Y",
)


def parse_pub_dt(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in _PUB_FMTS:
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


def normalise_pub(s: str) -> str:
    dt = parse_pub_dt(s)
    return dt.strftime("%b %d, %Y") if dt else s[:24]


def trim_summary(text: str, words: int = 28) -> str:
    parts = strip_html(text).split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def main() -> int:
    now = datetime.now(timezone.utc)
    out: dict[str, Any] = {"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "countries": {}}

    for country, feeds in COUNTRY_FEEDS.items():
        log.info(f"🌐 {COUNTRY_LABELS[country]}")
        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        for src in feeds:
            for it in fetch_rss(src["url"]):
                link = it["link"]
                title = strip_html(it["title"])
                if link in seen or not title:
                    continue
                if not KEYWORDS.search(title + " " + it.get("desc", "")):
                    continue
                pub_dt = parse_pub_dt(it.get("pub", ""))
                if pub_dt and (now - pub_dt).days > MAX_AGE_DAYS:
                    continue
                seen.add(link)
                items.append({
                    "title": title,
                    "url": link,
                    "summary": trim_summary(it.get("desc", ""), 30),
                    "source": src["source"],
                    "domain": urlparse(link).hostname or "",
                    "date": normalise_pub(it.get("pub", "")),
                    "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
                if len(items) >= MAX_PER_COUNTRY:
                    break
            if len(items) >= MAX_PER_COUNTRY:
                break
        items.sort(key=lambda x: parse_pub_dt(x.get("date", "")) or datetime(2000, 1, 1, tzinfo=timezone.utc), reverse=True)
        out["countries"][country] = items
        log.info(f"  → {len(items)} news items")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"✓ Wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
