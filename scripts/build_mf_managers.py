#!/usr/bin/env python3
"""Fund-manager directory for the India MF Screener → data/mf/managers.json.

Built from the published screener data (data/mf/screener.json + data/mf/d/<sub>.json, which carry each scheme's
official fund-manager names, roles and start dates). For every manager (keyed by name + fund house) it records:
the funds managed today with the start date on each, the earliest start date found (a lower bound on their
fund-management experience at that fund house), total assets managed, and how their funds rank within their
categories on 3-year return. Run after build_mf_screener.py; it needs no network access.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MF = ROOT / "data" / "mf"
OUT = MF / "managers.json"
log = logging.getLogger("managers")
MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_since(txt: str, today: date) -> str | None:
    """Best-effort start date ("01-Jan-2020", "Jan 2020", "1st April 2021", "01/04/2021", "Apr-21") → ISO."""
    t = (txt or "").strip().lower().replace(",", " ").replace(".", " ")
    if not t:
        return None
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t)
    y = mo = None
    m = re.search(r"\b(\d{1,2})[-/ ]+([a-z]{3,9})[-/ ]+(\d{2,4})\b", t)
    if m and m.group(2)[:3] in MON:
        mo, y = MON[m.group(2)[:3]], int(m.group(3))
    if y is None:
        m = re.search(r"\b([a-z]{3,9})[-/ ]+(?:\d{1,2}[-/ ]+)?(\d{2,4})\b", t)
        if m and m.group(1)[:3] in MON:
            mo, y = MON[m.group(1)[:3]], int(m.group(2))
    if y is None:                                               # 01/04/2021 · 01 04 2021 · 11/22/2022 · 31/10/24
        m = re.search(r"\b(\d{1,2})[-/ ]+(\d{1,2})[-/ ]+(\d{4}|\d{2})\b", t)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            mo = b if 1 <= b <= 12 else (a if 1 <= a <= 12 else None)
            y = int(m.group(3)) if mo else None
    if y is None:
        m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
        if m:
            y, mo = int(m.group(1)), int(m.group(2))
    if y is None:
        m = re.fullmatch(r"\s*(?:since\s+)?((?:19|20)\d{2})\s*", t)
        if m:
            y, mo = int(m.group(1)), 1
    if y is None:
        return None
    if y < 100:
        y += 2000 if y <= today.year % 100 else 1900
    if not (1990 <= y <= today.year) or not mo or (y == today.year and mo > today.month):
        return None
    return f"{y:04d}-{mo:02d}"


def norm(name: str) -> str:
    n = re.sub(r"^\s*(mr|ms|mrs|dr|shri|smt|ca)\.?\s+", "", name.strip(), flags=re.I)
    return re.sub(r"\s+", " ", n).strip(" .,-")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    scr = json.loads((MF / "screener.json").read_text())
    C = {c: i for i, c in enumerate(scr["cols"])}
    today = date.fromisoformat(scr["asOf"])
    rows = {str(r[C["code"]]): r for r in scr["rows"]}
    # 3-year return percentile within each category (1 = best)
    by_sub = defaultdict(list)
    for code, r in rows.items():
        if r[C["r3y"]] is not None:
            by_sub[r[C["sub"]]].append((r[C["r3y"]], code))
    pct = {}
    for sub, lst in by_sub.items():
        lst.sort()
        n = len(lst)
        for i, (_, code) in enumerate(lst):
            pct[code] = round(i / (n - 1), 3) if n > 1 else None
    mgr = {}
    for f in sorted((MF / "d").glob("*.json")):
        for code, d in json.loads(f.read_text()).items():
            r = rows.get(str(code))
            if not r:
                continue
            for m in (d.get("info") or {}).get("managers") or []:
                if not isinstance(m, dict) or not m.get("name"):
                    continue
                name = norm(m["name"])
                if len(name) < 3 or re.search(r"not applicable|^n\s*/?\s*a$|^na$|^nil$|^-+$", name, re.I):
                    continue
                key = re.sub(r"[^a-z]", "", name.lower()) + "|" + str(r[C["amc"]])
                rec = mgr.setdefault(key, {"n": name, "amc": r[C["amc"]], "f": []})
                if any(x[0] == int(code) for x in rec["f"]):
                    continue
                rec["f"].append([int(code), parse_since(m.get("since"), today), (m.get("role") or "")[:40]])
    out = {}
    for key, rec in mgr.items():
        codes = [str(x[0]) for x in rec["f"]]
        starts = [x[1] for x in rec["f"] if x[1]]
        aum = sum((rows[c][C["aum"]] or 0) for c in codes)
        ps = [pct[c] for c in codes if pct.get(c) is not None]
        out[key] = {"n": rec["n"], "amc": rec["amc"], "f": sorted(rec["f"], key=lambda x: -(rows[str(x[0])][C["aum"]] or 0)),
                    "e": min(starts) if starts else None, "aum": round(aum, 1),
                    "p3": round(sum(ps) / len(ps), 3) if ps else None, "n3": len(ps)}
    OUT.write_text(json.dumps({"v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "asOf": scr["asOf"], "m": out}, ensure_ascii=False, separators=(",", ":")))
    dated = sum(1 for v in out.values() if v["e"])
    log.info("Wrote %s: %d managers (%d with a start date), %d fund links", OUT, len(out), dated, sum(len(v["f"]) for v in out.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
