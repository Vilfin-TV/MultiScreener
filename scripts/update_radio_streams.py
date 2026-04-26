#!/usr/bin/env python3
"""
update_radio_streams.py
──────────────────────────────────────────────────────────────────
Queries the Radio Browser API (radio-browser.info) to fetch top
working streaming URLs for each region, verifies active streams,
and saves the result to public/data/radio_stations.json.

Run by GitHub Actions daily at 02:00 UTC.
"""

import json
import time
import socket
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
OUT_FILE = Path(__file__).parent.parent / "public" / "data" / "radio_stations.json"
RADIO_BROWSER_BASE = "https://de1.api.radio-browser.info/json"
TIMEOUT_CONNECT = 5   # seconds to verify stream is reachable
MAX_PER_CATEGORY = 6  # max stations per category to keep
HEADERS = {"User-Agent": "MultiScreenerRadioBot/1.0 (github.com/Vilfin-TV/MultiScreener)"}

# ─── SEARCH QUERIES ───────────────────────────────────────────────────────────
# Maps category_id → Radio Browser API search params
QUERIES = {
    "us": {"countrycode": "US", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true", "codec": "MP3,AAC"},
    "japan": {"countrycode": "JP", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-malayalam": {"countrycode": "IN", "language": "malayalam", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-tamil":     {"countrycode": "IN", "language": "tamil",     "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-kannada":   {"countrycode": "IN", "language": "kannada",   "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-telugu":    {"countrycode": "IN", "language": "telugu",    "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-hindi":     {"countrycode": "IN", "language": "hindi",     "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-marathi":   {"countrycode": "IN", "language": "marathi",   "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-punjabi":   {"countrycode": "IN", "language": "punjabi",   "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-bengali":   {"countrycode": "IN", "language": "bengali",   "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "india-bollywood": {"countrycode": "IN", "tags": "bollywood",     "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "africa":          {"continent": "Africa",  "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "middle-east":     {"tags": "arabic,middle east", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "china":           {"countrycode": "CN", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "korea":           {"countrycode": "KR", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "europe":          {"continent": "Europe",  "limit": 30, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "latin-america":   {"tags": "latin,spanish,portuguese", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "canada":          {"countrycode": "CA", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
    "mexico":          {"countrycode": "MX", "limit": 20, "order": "clickcount", "reverse": "true", "hidebroken": "true"},
}

# ─── CATEGORY LABELS ──────────────────────────────────────────────────────────
LABELS = {
    "us":              "🇺🇸 United States",
    "japan":           "🇯🇵 Japan",
    "india-malayalam": "🇮🇳 India — Malayalam",
    "india-tamil":     "🇮🇳 India — Tamil",
    "india-kannada":   "🇮🇳 India — Kannada",
    "india-telugu":    "🇮🇳 India — Telugu",
    "india-hindi":     "🇮🇳 India — Hindi",
    "india-marathi":   "🇮🇳 India — Marathi",
    "india-punjabi":   "🇮🇳 India — Punjabi",
    "india-bengali":   "🇮🇳 India — Bengali",
    "india-bollywood": "🇮🇳 India — Bollywood",
    "africa":          "🌍 Africa",
    "middle-east":     "🌙 Middle East",
    "china":           "🇨🇳 China",
    "korea":           "🇰🇷 Korea",
    "europe":          "🇪🇺 Europe",
    "latin-america":   "🌎 Latin America",
    "canada":          "🇨🇦 Canada",
    "mexico":          "🇲🇽 Mexico",
}


def rb_search(params: dict) -> list:
    """Query Radio Browser API /json/stations/search with given params."""
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{RADIO_BROWSER_BASE}/stations/search?{qs}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ⚠ Radio Browser query failed: {e}")
        return []


def is_stream_reachable(url: str) -> bool:
    """
    Quick TCP-level check: try to open a socket to the stream host:port.
    Returns True if connection succeeds within TIMEOUT_CONNECT seconds.
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme in ("https", "wss") else 80)
        with socket.create_connection((host, port), timeout=TIMEOUT_CONNECT):
            return True
    except Exception:
        return False


def fetch_category(cat_id: str, params: dict) -> list:
    """Fetch and verify stations for one category."""
    import urllib.parse  # ensure available
    print(f"  Querying: {cat_id}…", end=" ", flush=True)
    raw = rb_search(params)
    print(f"{len(raw)} results", flush=True)

    verified = []
    for s in raw:
        url = s.get("url_resolved") or s.get("url", "")
        if not url:
            continue
        # Skip non-audio formats
        codec = (s.get("codec") or "").upper()
        if codec in ("AAC+", "OGG", "FLAC"):
            codec = "AAC" if codec == "AAC+" else codec

        if is_stream_reachable(url):
            station = {
                "id":    f"{cat_id}-{s.get('stationuuid','')[:8]}",
                "name":  (s.get("name") or "Unknown").strip()[:50],
                "url":   url,
                "genre": (s.get("tags") or s.get("language") or "Radio").split(",")[0].strip().title()[:20],
                "codec": codec or "MP3",
            }
            verified.append(station)
            if len(verified) >= MAX_PER_CATEGORY:
                break
        time.sleep(0.05)  # be polite to the stream server

    print(f"    ✓ {len(verified)} verified")
    return verified


def load_existing() -> dict:
    """Load existing JSON so we can fall back per-category if API fails."""
    if OUT_FILE.exists():
        try:
            return json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"categories": []}


def build_fallback_map(existing: dict) -> dict:
    """Build a cat_id → stations map from existing JSON."""
    fm = {}
    for cat in existing.get("categories", []):
        fm[cat["id"]] = cat.get("stations", [])
    return fm


def main():
    import urllib.parse  # make available in fetch_category scope

    print("=" * 60)
    print("Radio Streams Auto-Fixer — MultiScreener")
    print(f"Run at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    existing = load_existing()
    fallback = build_fallback_map(existing)

    categories = []
    for cat_id, params in QUERIES.items():
        print(f"\n[{cat_id}]")
        stations = fetch_category(cat_id, params)

        # Fall back to existing stations if API returned nothing verified
        if not stations:
            stations = fallback.get(cat_id, [])
            if stations:
                print(f"    ↩ Using {len(stations)} existing (fallback)")

        categories.append({
            "id":       cat_id,
            "label":    LABELS.get(cat_id, cat_id),
            "stations": stations,
        })

    output = {
        "version":    "1.0",
        "updated":    datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "note":       "Auto-updated daily by scripts/update_radio_streams.py via GitHub Actions",
        "categories": categories,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Saved → {OUT_FILE}")
    total = sum(len(c["stations"]) for c in categories)
    print(f"   {len(categories)} categories | {total} stations total")


if __name__ == "__main__":
    import urllib.parse
    main()
