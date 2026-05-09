# -*- coding: utf-8 -*-
"""
monitor_fix.py — VilfinTV Multi-Asset Screener Auto-Monitor & Fix
==================================================================
Checks live-TV YouTube stream IDs using a 3-Step Hybrid Fallback system,
validates radio stream URLs, and syncs results to Google Sheets.

Schedule: Daily at 00:00 UTC via GitHub Actions (.github/workflows/monitor_fix.yml)

Dependencies (install in workflow):
  pandas google-api-python-client gspread google-auth requests tradingview_ta
"""

from __future__ import annotations

import os
import re
import sys
import json
import logging
import time
import socket
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import requests

# ── Logger ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Optional imports (graceful degradation) ────────────────────────────────
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

# ────────────────────────────────────────────────────────────────────────────
#  Config — read from environment / GitHub Secrets
# ────────────────────────────────────────────────────────────────────────────
YOUTUBE_API_KEY   = os.getenv("YOUTUBE_API_KEY", "")
GSHEET_CREDS_JSON = os.getenv("GSHEET_CREDS_JSON", "")
GSHEET_DOC_TITLE  = os.getenv("GSHEET_DOC_TITLE", "VilfinTV Screener Config")

CSV_PATH          = Path("youtube_live_audit.csv")
STREAMS_JSON      = Path("streams.json")
RADIO_JSON        = Path("public/data/radio_stations.json")

RADIO_TCP_TIMEOUT = 5

# ────────────────────────────────────────────────────────────────────────────
#  Google Sheets helpers
# ────────────────────────────────────────────────────────────────────────────
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


# ────────────────────────────────────────────────────────────────────────────
#  YouTube API helpers (googleapiclient.discovery)
# ────────────────────────────────────────────────────────────────────────────
def _build_youtube():
    """Build a YouTube Data API v3 service object."""
    if not YOUTUBE_API_KEY:
        log.warning("No YOUTUBE_API_KEY set — cannot query YouTube.")
        return None
    try:
        return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    except Exception as exc:
        log.error("Failed to build YouTube API client: %s", exc)
        return None


def _extract_video_id(url: str) -> str | None:
    """Extract a YouTube video ID from a watch URL. Returns None if invalid."""
    if not url or pd.isna(url):
        return None
    m = re.search(r'(?:v=|/embed/|youtu\.be/)([A-Za-z0-9_-]{11})', str(url))
    return m.group(1) if m else None


# ────────────────────────────────────────────────────────────────────────────
#  3-Step Hybrid Fallback — channels 1-20 only
# ────────────────────────────────────────────────────────────────────────────
def check_and_fix_csv(youtube) -> bool:
    """
    Process only rows 1-20 in youtube_live_audit.csv.
    Returns True if the CSV was modified.
    """
    if not CSV_PATH.exists():
        log.warning("youtube_live_audit.csv not found — skipping Live TV check.")
        return False

    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8")

        # 1. Strip whitespace from ALL column names
        df.columns = df.columns.str.strip()

        # 2. Dynamically get the first column (ID column) regardless of its name
        id_col = df.columns[0]

        # 3. Force the ID column to numeric
        df[id_col] = pd.to_numeric(df[id_col], errors="coerce")

        # 4. Filter for channels 1 through 20
        target_mask = (df[id_col] >= 1) & (df[id_col] <= 20)

        # Map other columns with stripped names
        channel_id_col = "Channel ID" if "Channel ID" in df.columns else df.columns[2]
        url1_col       = "full url 1 with Video ID" if "full url 1 with Video ID" in df.columns else df.columns[5]
        url2_col       = "full url 2 with Video ID" if "full url 2 with Video ID" in df.columns else df.columns[6]
    except Exception as exc:
        log.error("Failed to read CSV: %s", exc)
        return False

    # Add Status column if not present
    status_col = "Status"
    if status_col not in df.columns:
        df[status_col] = ""

    modified = False

    for idx, row in df[target_mask].iterrows():
        ch_num = row[id_col]
        if pd.isna(ch_num):
            continue

        ch_name    = str(row.iloc[1]) if len(row) > 1 else ""
        channel_id = str(row.get(channel_id_col, "")).strip() if not pd.isna(row.get(channel_id_col)) else ""
        url1       = str(row.get(url1_col, "")).strip()   if not pd.isna(row.get(url1_col))   else ""
        url2       = str(row.get(url2_col, "")).strip()   if not pd.isna(row.get(url2_col))   else ""

        log.info("  🔍 Ch %d — %s", ch_num, ch_name)

        try:
            # ── Step 1: Search for current live stream on the channel ──
            if channel_id:
                try:
                    search_resp = youtube.search().list(
                        part="snippet",
                        channelId=channel_id,
                        type="video",
                        eventType="live",
                        maxResults=1,
                    ).execute()
                    items = search_resp.get("items", [])
                    if items:
                        new_video_id = items[0]["id"]["videoId"]
                        new_url = f"https://www.youtube.com/watch?v={new_video_id}"
                        df.at[idx, url1_col] = new_url
                        df.at[idx, status_col] = "Active"
                        log.info("    [OK] Step 1 (channel search) — live: %s -> %s", ch_name, new_video_id)
                        modified = True
                        continue
                except HttpError as e:
                    if e.resp.status == 403:
                        log.error("    ⛔ API quota exceeded (HTTP 403). Saving CSV and stopping.")
                        break
                    log.warning("    Step 1 search error: %s", e)
                except Exception as e:
                    log.warning("    Step 1 search error: %s", e)

            # ── Step 2: Check existing URL 1 video ID ──
            vid1 = _extract_video_id(url1)
            if vid1:
                try:
                    vid_resp = youtube.videos().list(
                        part="snippet",
                        id=vid1,
                        maxResults=1,
                    ).execute()
                    v_items = vid_resp.get("items", [])
                    if v_items:
                        status = v_items[0]["snippet"].get("liveBroadcastContent", "")
                        if status == "live":
                            df.at[idx, status_col] = "Active"
                            log.info("    ✓ Step 2 (URL 1) — still live: %s → %s", ch_name, vid1)
                            modified = True
                            continue
                except HttpError as e:
                    if e.resp.status == 403:
                        log.error("    ⛔ API quota exceeded (HTTP 403). Saving CSV and stopping.")
                        break
                    log.warning("    Step 2 error: %s", e)
                except Exception as e:
                    log.warning("    Step 2 error: %s", e)

            # ── Step 3: Check existing URL 2 video ID ──
            vid2 = _extract_video_id(url2)
            if vid2:
                try:
                    vid_resp = youtube.videos().list(
                        part="snippet",
                        id=vid2,
                        maxResults=1,
                    ).execute()
                    v_items = vid_resp.get("items", [])
                    if v_items:
                        status = v_items[0]["snippet"].get("liveBroadcastContent", "")
                        if status == "live":
                            new_url = f"https://www.youtube.com/watch?v={vid2}"
                            df.at[idx, url1_col] = new_url
                            df.at[idx, status_col] = "Active"
                            log.info("    ✓ Step 3 (URL 2) — live, updated URL 1: %s → %s", ch_name, vid2)
                            modified = True
                            continue
                except HttpError as e:
                    if e.resp.status == 403:
                        log.error("    ⛔ API quota exceeded (HTTP 403). Saving CSV and stopping.")
                        break
                    log.warning("    Step 3 error: %s", e)
                except Exception as e:
                    log.warning("    Step 3 error: %s", e)

            # ── Step 4: All steps failed — mark as Broken / Offline ──
            df.at[idx, url1_col]  = "Broken"
            df.at[idx, status_col] = "Offline"
            log.warning("    ✗ %s — no live stream found, marked Offline", ch_name)
            modified = True

        except Exception as e:
            log.error("    Unexpected error on Ch %d: %s", ch_num, e)
            df.at[idx, status_col] = "Error"
            modified = True

        time.sleep(0.25)  # gentle with quota

    # Save the updated CSV
    if modified:
        try:
            df.to_csv(CSV_PATH, index=False, encoding="utf-8")
            log.info("youtube_live_audit.csv updated.")
        except Exception as exc:
            log.error("Failed to save CSV: %s", exc)

    return modified


# ────────────────────────────────────────────────────────────────────────────
#  Sync CSV results to streams.json
# ────────────────────────────────────────────────────────────────────────────
def sync_csv_to_streams():
    """Write updated video IDs from the CSV back into streams.json."""
    if not CSV_PATH.exists() or not STREAMS_JSON.exists():
        return

    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8")
        df.columns = df.columns.str.strip()
        id_col = df.columns[0]
        df[id_col] = pd.to_numeric(df[id_col], errors="coerce")
    except Exception:
        return

    with open(STREAMS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    channels = data.get("channels", [])
    for idx, row in df.iterrows():
        ch_num = row[id_col]
        if pd.isna(ch_num):
            continue
        ch_num = int(ch_num)
        if ch_num < 1 or ch_num > len(channels):
            continue

        url1   = str(row.get("full url 1 with Video ID", "")) if not pd.isna(row.get("full url 1 with Video ID")) else ""
        status = str(row.get("Status", ""))  if not pd.isna(row.get("Status")) else ""

        vid_id = _extract_video_id(url1)
        if vid_id and url1 != "Broken":
            channels[ch_num - 1]["videoId"] = vid_id
        channels[ch_num - 1]["status"] = status if status else channels[ch_num - 1].get("status", "")

    data["updated"] = datetime.now(timezone.utc).isoformat()
    with open(STREAMS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("streams.json synced from CSV.")


# ────────────────────────────────────────────────────────────────────────────
#  Ticker check (via tradingview_ta)
# ────────────────────────────────────────────────────────────────────────────
FALLBACK_TICKERS = {
    "NSE":    "NIFTY",
    "NASDAQ": "IXIC",
    "NYSE":   "DJI",
}

def check_ticker(symbol: str, exchange: str) -> tuple[bool, str]:
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
    ws = get_sheet(client, "Tickers")
    if ws is None:
        log.info("No 'Tickers' sheet found — skipping ticker check.")
        return
    rows = ws.get_all_records()
    for i, row in enumerate(rows, start=2):
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


# ────────────────────────────────────────────────────────────────────────────
#  Radio stream health check (HTTP HEAD + TCP)
# ────────────────────────────────────────────────────────────────────────────
def is_stream_reachable(url: str) -> bool:
    try:
        r = requests.head(url, timeout=RADIO_TCP_TIMEOUT, allow_redirects=True,
                          headers={"User-Agent": "VilfinTV-Monitor/1.0"})
        return r.status_code < 400
    except requests.exceptions.RequestException:
        pass
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


# ────────────────────────────────────────────────────────────────────────────
#  Sync streams.json to Google Sheet (optional)
# ────────────────────────────────────────────────────────────────────────────
def sync_streams_to_sheet(client):
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


# ────────────────────────────────────────────────────────────────────────────
#  Main
# ────────────────────────────────────────────────────────────────────────────
def main():
    log.info("═══ VilfinTV Monitor & Auto-Fix ═══")
    log.info("Started at %s UTC", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    log.info("YouTube API key present: %s", "Yes" if YOUTUBE_API_KEY else "No")
    log.info("Google Sheets creds present: %s", "Yes" if GSHEET_CREDS_JSON else "No")

    sorted_events = {"csv": False, "radio": False, "sync": False}
    gs_client = _get_gspread_client()

    # ── [1/4] 3-Step Hybrid Fallback for channels 1-20 ──────────────
    log.info("── [1/4] YouTube Live TV check (3-Step Hybrid Fallback) …")
    youtube = _build_youtube()
    if youtube:
        sorted_events["csv"] = check_and_fix_csv(youtube)
        sync_csv_to_streams()
    else:
        log.warning("Skipping YouTube check — no API key or client build failed.")

    # ── [2/4] Ticker symbols ─────────────────────────────────────────
    log.info("── [2/4] Checking ticker symbols …")
    fix_tickers_in_sheet(gs_client)

    # ── [3/4] Radio stream health ────────────────────────────────────
    log.info("── [3/4] Checking radio stream health …")
    sorted_events["radio"] = check_radio_streams()

    # ── [4/4] Sync to Google Sheet ───────────────────────────────────
    log.info("── [4/4] Syncing streams to Google Sheet …")
    sync_streams_to_sheet(gs_client)

    sorted_events = [k for k, v in sorted_events.items() if v]
    log.info("═══ Done — sorted: %s ═══", ", ".join(sorted_events) if sorted_events else "none")


if __name__ == "__main__":
    main()
