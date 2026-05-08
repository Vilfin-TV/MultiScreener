# -*- coding: utf-8 -*-
"""
monitor_fix.py — VilfinTV Multi-Asset Screener Auto-Monitor & Fix
==================================================================
Checks live-TV YouTube stream IDs, music playlist IDs, ticker symbols,
and radio stream URLs. Auto-repairs broken entries in the Google Sheet
and exports updated JSON data files consumed by the frontend.

Schedule: Daily at 00:00 UTC via GitHub Actions (.github/workflows/monitor_fix.yml)

Dependencies (add to requirements.txt or install in workflow):
  gspread google-auth requests tradingview_ta
"""

from __future__ import annotations

import os
import sys
import json
import logging
import time
import socket
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── Logger — set up BEFORE optional imports so their logging.warning() uses it ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Optional imports (graceful degradation) ───────────────────────────────────
try:
    import gspread
    from google.oauth2.service_account import Credentials as SACredentials
    GSPREAD_OK = True
except ImportError:
    GSPREAD_OK = False
    log.warning("gspread / google-auth not installed — Google Sheet sync disabled.")

try:
    from tradingview_ta import TA_Handler, Interval
    TVTA_OK = True
except ImportError:
    TVTA_OK = False
    log.warning("tradingview_ta not installed — ticker checks disabled.")

# ─────────────────────────────────────────────────────────────────────────────
#  Config — read from environment / GitHub Secrets
# ─────────────────────────────────────────────────────────────────────────────
YOUTUBE_API_KEY   = os.getenv("YOUTUBE_API_KEY", "")
GSHEET_CREDS_JSON = os.getenv("GSHEET_CREDS_JSON", "")   # full JSON string of service-account key
GSHEET_DOC_TITLE  = os.getenv("GSHEET_DOC_TITLE", "VilfinTV Screener Config")

STREAMS_JSON      = Path("streams.json")
RADIO_JSON        = Path("public/data/radio_stations.json")

YT_VIDEO_API      = "https://www.googleapis.com/youtube/v3/videos"
YT_SEARCH_API     = "https://www.googleapis.com/youtube/v3/search"
YT_CHANNELS_API   = "https://www.googleapis.com/youtube/v3/channels"
HTTP_TIMEOUT      = 8   # seconds
RADIO_TCP_TIMEOUT = 5

# ─────────────────────────────────────────────────────────────────────────────
#  Google Sheets helper
# ─────────────────────────────────────────────────────────────────────────────
def _get_gspread_client():
    if not GSPREAD_OK or not GSHEET_CREDS_JSON:
        return None
    try:
        creds_dict = json.loads(GSHEET_CREDS_JSON)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = SACredentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as exc:
        log.error("Google Sheets auth failed: %s", exc)
        return None


def get_sheet(client, sheet_name: str):
    if client is None:
        return None
    try:
        doc = client.open(GSHEET_DOC_TITLE)
        return doc.worksheet(sheet_name)
    except Exception as exc:
        log.warning("Could not open sheet '%s': %s", sheet_name, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  YouTube helpers
# ─────────────────────────────────────────────────────────────────────────────
def yt_is_live(video_id: str) -> bool:
    """Return True if the YouTube videoId (or channelId) is currently live."""
    if not YOUTUBE_API_KEY or not video_id:
        return True   # assume OK if we can't check
    try:
        # If this looks like a channel ID (starts with UC), search for a live stream on that channel
        if video_id.startswith("UC"):
            r = requests.get(
                YT_SEARCH_API,
                params={"part": "id", "channelId": video_id, "eventType": "live",
                        "type": "video", "key": YOUTUBE_API_KEY, "maxResults": 1},
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            return len(items) > 0
        # Otherwise check if the specific video ID is live
        r = requests.get(
            YT_VIDEO_API,
            params={"part": "snippet,liveStreamingDetails", "id": video_id, "key": YOUTUBE_API_KEY},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return False
        status = items[0].get("snippet", {}).get("liveBroadcastContent", "")
        return status == "live"
    except Exception as exc:
        log.warning("yt_is_live(%s) error: %s", video_id, exc)
        return True   # network failure → don't mark broken


def yt_find_live_id(channel_id: str, search_query: str) -> str | None:
    """Search for the current live-stream videoId on a channel or by keyword.
    Falls back to recent uploads if no live stream is active."""
    if not YOUTUBE_API_KEY:
        return None
    # 1. Try channel-based live search
    if channel_id:
        try:
            r = requests.get(
                YT_SEARCH_API,
                params={
                    "part": "id",
                    "channelId": channel_id,
                    "eventType": "live",
                    "type": "video",
                    "key": YOUTUBE_API_KEY,
                    "maxResults": 1,
                },
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            if items:
                return items[0]["id"]["videoId"]
        except Exception as exc:
            log.warning("yt_find_live_id channel search error: %s", exc)
        # 2. Fallback: search recent uploads on the channel (no eventType filter)
        try:
            r = requests.get(
                YT_SEARCH_API,
                params={
                    "part": "id",
                    "channelId": channel_id,
                    "type": "video",
                    "order": "date",
                    "key": YOUTUBE_API_KEY,
                    "maxResults": 1,
                },
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            if items:
                return items[0]["id"]["videoId"]
        except Exception as exc:
            log.warning("yt_find_live_id recent uploads error: %s", exc)

    # 3. Fall back to keyword search (with 'live' suffix)
    if search_query:
        try:
            r = requests.get(
                YT_SEARCH_API,
                params={
                    "part": "id",
                    "q": search_query + " live",
                    "eventType": "live",
                    "type": "video",
                    "key": YOUTUBE_API_KEY,
                    "maxResults": 1,
                },
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            if items:
                return items[0]["id"]["videoId"]
        except Exception as exc:
            log.warning("yt_find_live_id keyword search error: %s", exc)
        # 4. Final fallback: keyword search without live filter
        try:
            r = requests.get(
                YT_SEARCH_API,
                params={
                    "part": "id",
                    "q": search_query,
                    "type": "video",
                    "order": "date",
                    "key": YOUTUBE_API_KEY,
                    "maxResults": 1,
                },
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            if items:
                return items[0]["id"]["videoId"]
        except Exception as exc:
            log.warning("yt_find_live_id fallback search error: %s", exc)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Task 1 — Auto-Fix YouTube Live TV stream IDs (streams.json)
# ─────────────────────────────────────────────────────────────────────────────
def check_and_fix_streams() -> bool:
    """Returns True if streams.json was modified."""
    if not STREAMS_JSON.exists():
        log.warning("streams.json not found — skipping Live TV check.")
        return False

    with open(STREAMS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    channels = data.get("channels", [])
    modified = False

    for ch in channels:
        vid_id    = ch.get("videoId", "")
        ch_id     = ch.get("channelId", "")
        label     = ch.get("label", "")

        if not vid_id:
            continue

        # If videoId is actually a channel ID (UC...), skip live check
        # and directly search for a live video from that channel
        if vid_id.startswith("UC") and not ch_id:
            ch_id = vid_id  # use videoId as channelId
            new_id = yt_find_live_id(ch_id, label.replace("🇮🇳", "").replace("📺", "").replace("📡", "").strip())
            if new_id:
                log.info("  → %s — channel search found live video: %s", label, new_id)
                ch["videoId"] = new_id
                ch["status"]  = "auto-fixed"
                modified = True
            else:
                log.warning("  → %s — no live video found for channel %s", label, ch_id)
                ch["status"] = "offline"
            time.sleep(0.3)
            continue

        if yt_is_live(vid_id):
            log.info("  ✓ %s — live", label)
            ch["status"] = "live"
            continue

        log.warning("  ✗ %s (videoId=%s) offline — searching for replacement…", label, vid_id)

        new_id = yt_find_live_id(ch_id, label.replace("🇮🇳", "").replace("📺", "").replace("📡", "").strip())
        if new_id and new_id != vid_id:
            log.info("    → replaced with %s", new_id)
            ch["videoId"] = new_id
            ch["status"]  = "auto-fixed"
            modified = True
        else:
            log.warning("    → no replacement found — marking offline")
            ch["status"] = "offline"

        time.sleep(0.3)   # be gentle with quota

    if modified or any(c.get("status") for c in channels):
        data["updated"] = datetime.now(timezone.utc).isoformat()
        with open(STREAMS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info("streams.json updated.")

    return modified


# ─────────────────────────────────────────────────────────────────────────────
#  Task 2 — Auto-Fix ticker symbols (via tradingview_ta)
# ─────────────────────────────────────────────────────────────────────────────
FALLBACK_TICKERS = {
    "NSE":    "NIFTY",
    "NASDAQ": "IXIC",
    "NYSE":   "DJI",
}

def check_ticker(symbol: str, exchange: str) -> tuple[bool, str]:
    """Returns (ok, message)."""
    if not TVTA_OK:
        return True, "tradingview_ta not available"
    try:
        h = TA_Handler(symbol=symbol, screener="india" if exchange in ("NSE","BSE") else "america",
                       exchange=exchange, interval=Interval.INTERVAL_1_DAY)
        h.get_analysis()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def fix_tickers_in_sheet(client):
    """Checks tickers listed in the Google Sheet's 'Tickers' worksheet."""
    ws = get_sheet(client, "Tickers")
    if ws is None:
        log.info("No 'Tickers' sheet found — skipping ticker check.")
        return

    rows = ws.get_all_records()
    for i, row in enumerate(rows, start=2):   # row 1 = header
        symbol   = str(row.get("Symbol", "")).strip()
        exchange = str(row.get("Exchange", "NSE")).strip()
        status   = str(row.get("Status", "")).strip()

        if not symbol or status.lower() in ("broken", "skip"):
            continue

        ok, msg = check_ticker(symbol, exchange)
        if ok:
            ws.update_cell(i, list(row.keys()).index("Status") + 1, "OK")
        else:
            fallback = FALLBACK_TICKERS.get(exchange, "")
            if fallback:
                ok2, _ = check_ticker(fallback, exchange)
                if ok2:
                    ws.update_cell(i, list(row.keys()).index("Symbol") + 1, fallback)
                    ws.update_cell(i, list(row.keys()).index("Status") + 1, f"Auto-fixed → {fallback}")
                    log.info("  Ticker %s/%s → replaced with %s", symbol, exchange, fallback)
                else:
                    ws.update_cell(i, list(row.keys()).index("Status") + 1, "Broken")
                    log.warning("  Ticker %s/%s → Broken (no fallback)", symbol, exchange)
            else:
                ws.update_cell(i, list(row.keys()).index("Status") + 1, "Broken")
                log.warning("  Ticker %s/%s → Broken", symbol, exchange)
        time.sleep(0.5)


# ─────────────────────────────────────────────────────────────────────────────
#  Task 3 — Radio stream health check (HTTP HEAD + TCP)
# ─────────────────────────────────────────────────────────────────────────────
def is_stream_reachable(url: str) -> bool:
    """Quick TCP-connect or HTTP HEAD check."""
    try:
        # Try HTTP HEAD first
        r = requests.head(url, timeout=RADIO_TCP_TIMEOUT, allow_redirects=True,
                          headers={"User-Agent": "VilfinTV-Monitor/1.0"})
        return r.status_code < 400
    except requests.exceptions.RequestException:
        pass
    # Fall back to TCP socket
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host   = parsed.hostname
        port   = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=RADIO_TCP_TIMEOUT):
            return True
    except Exception:
        return False


def check_radio_streams() -> bool:
    """Mark unreachable streams in radio_stations.json. Returns True if file changed."""
    if not RADIO_JSON.exists():
        log.warning("radio_stations.json not found — skipping radio check.")
        return False

    with open(RADIO_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    modified = False
    if isinstance(data, list):
        stations = data
    elif "categories" in data:
        stations = [s for cat in data["categories"] for s in cat.get("stations", [])]
    else:
        stations = data.get("stations", [])

    for st in stations:
        url  = st.get("url_resolved") or st.get("url") or ""
        name = st.get("name", "?")
        if not url:
            continue

        reachable = is_stream_reachable(url)
        prev_status = st.get("viltv_status", "ok")

        if reachable:
            if prev_status != "ok":
                st["viltv_status"] = "ok"
                modified = True
            log.info("  ✓ %s", name)
        else:
            if prev_status != "broken":
                st["viltv_status"] = "broken"
                modified = True
            log.warning("  ✗ %s — stream not reachable", name)

        time.sleep(0.1)

    if modified:
        with open(RADIO_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info("radio_stations.json updated.")

    return modified


# ─────────────────────────────────────────────────────────────────────────────
#  Task 4 — Sync streams.json to Google Sheet (optional)
# ─────────────────────────────────────────────────────────────────────────────
def sync_streams_to_sheet(client):
    """Write current stream statuses to 'LiveTV' worksheet in the Google Sheet."""
    ws = get_sheet(client, "LiveTV")
    if ws is None:
        log.info("No 'LiveTV' sheet — skipping sync.")
        return
    if not STREAMS_JSON.exists():
        return

    with open(STREAMS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    channels = data.get("channels", [])
    rows = [["Label", "VideoId", "ChannelId", "Status", "LastChecked"]]
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for ch in channels:
        rows.append([
            ch.get("label", ""),
            ch.get("videoId", ""),
            ch.get("channelId", ""),
            ch.get("status", ""),
            now,
        ])
    ws.clear()
    ws.update("A1", rows)
    log.info("LiveTV sheet synced — %d rows.", len(rows) - 1)


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    log.info("═══ VilfinTV Monitor & Auto-Fix ═══")
    log.info("Started at %s UTC", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    log.info("YouTube API key present: %s", "Yes" if YOUTUBE_API_KEY else "No")
    log.info("Google Sheets creds present: %s", "Yes" if GSHEET_CREDS_JSON else "No")
    log.info("tradingview_ta available: %s", "Yes" if TVTA_OK else "No")
    log.info("gspread available: %s", "Yes" if GSPREAD_OK else "No")

    results = {"streams": False, "tickers": False, "radio": False, "sync": False}
    gs_client = _get_gspread_client()

    log.info("── [1/4] Checking YouTube Live TV streams …")
    results["streams"] = check_and_fix_streams()

    log.info("── [2/4] Checking ticker symbols …")
    fix_tickers_in_sheet(gs_client)

    log.info("── [3/4] Checking radio stream health …")
    results["radio"] = check_radio_streams()

    log.info("── [4/4] Syncing streams to Google Sheet …")
    sync_streams_to_sheet(gs_client)

    modified = [k for k, v in results.items() if v]
    log.info("═══ Done — modified: %s ═══", ", ".join(modified) if modified else "none")


if __name__ == "__main__":
    main()
