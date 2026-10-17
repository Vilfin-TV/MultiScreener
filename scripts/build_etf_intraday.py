#!/usr/bin/env python3
"""
build_etf_intraday.py
─────────────────────
Near-live prices for the ETF page's trading chart: during NSE market hours, today's forming daily bar
(open, high, low, latest price, volume so far) for every ETF → data/etf_live.json.

The page appends this bar to the end-of-day history in data/etf/d/<SYMBOL>.json only while its session is newer
than the last end-of-day bar, so once the evening build publishes the official close the live file is ignored.
Run by .github/workflows/etf_intraday.yml roughly every 30 minutes on trading days.

Safety : a bar is used only when it is dated today (IST), its price is within ±20% of the previous close and
         high ≥ max(open, price) ≥ min(open, price) ≥ low; the file is written only when ≥50 ETFs pass.
Usage  : python scripts/build_etf_intraday.py [--force]   (--force skips the market-hours check)
"""
from __future__ import annotations

import json
import logging
import math
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_etf_momentum import download, to_rounded  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("etf_intraday")
OUT = os.path.join(ROOT, "data", "etf_live.json")
DAILY_DIR = os.path.join(ROOT, "data", "etf", "d")
OPEN_IST, CLOSE_IST = (9, 15), (15, 30)


def ist_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


def trading_day(d) -> bool:
    if d.weekday() > 4:
        return False
    try:
        return d.isoformat() not in json.load(open(os.path.join(ROOT, "data", "nse_holidays.json")))
    except Exception:  # noqa: BLE001
        return True


def main() -> int:
    now = ist_now()
    today = now.date()
    if "--force" not in sys.argv:
        if not trading_day(today):
            log.info("%s is not a trading day — nothing to do", today)
            return 0
        if (now.hour, now.minute) < (OPEN_IST[0], OPEN_IST[1] + 5) or (now.hour, now.minute) > (CLOSE_IST[0], CLOSE_IST[1] + 20):
            log.info("outside market hours (%s IST) — nothing to do", now.strftime("%H:%M"))
            return 0
    syms = sorted(f[:-5] for f in os.listdir(DAILY_DIR) if f.endswith(".json"))
    prev = {}
    for s in syms:
        try:
            b = json.load(open(os.path.join(DAILY_DIR, f"{s}.json")))
            if b["t"] and b["t"][-1] < int(today.strftime("%Y%m%d")):
                prev[s] = b["c"][-1]
        except Exception:  # noqa: BLE001
            continue
    raw = download([f"{s}.NS" for s in prev], period="5d")
    bars, rejected = {}, 0
    for s, pc in prev.items():
        df = raw.get(f"{s}.NS")
        if df is None or not len(df) or df.index[-1].date() != today:
            continue
        row = df.iloc[-1]
        try:
            o, h, lo, c = (float(row[k]) for k in ("Open", "High", "Low", "Close"))
            v = float(row["Volume"]) if row["Volume"] == row["Volume"] else 0.0
        except Exception:  # noqa: BLE001
            continue
        if not all(math.isfinite(x) and x > 0 for x in (o, h, lo, c)) or not pc or abs(c / pc - 1) > 0.2:
            rejected += 1
            continue
        h, lo = max(h, o, c), min(lo, o, c)
        if h > 1.2 * pc or lo < 0.8 * pc:
            h, lo = max(o, c), min(o, c)
        bars[s] = [to_rounded(o), to_rounded(h), to_rounded(lo), to_rounded(c), int(v)]
    if len(bars) < 50:
        log.warning("only %d ETFs have a bar for %s (%d rejected) — keeping the previous file", len(bars), today, rejected)
        return 0
    closed = (now.hour, now.minute) >= CLOSE_IST
    payload = {"v": 1, "session": today.isoformat(), "updated": now.strftime("%Y-%m-%dT%H:%M") + "+05:30",
               "closed": closed, "bars": bars}
    with open(OUT + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    os.replace(OUT + ".tmp", OUT)
    log.info("live bars: %d ETFs for %s at %s IST (%d rejected)", len(bars), today, now.strftime("%H:%M"), rejected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
