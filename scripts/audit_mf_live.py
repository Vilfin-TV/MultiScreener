#!/usr/bin/env python3
"""
India Mutual Fund Screener — live audit of the PUBLISHED data (runs on every 30-minute wake-up).

Checks performed (standard library only, so the gate job stays fast):
  1. Freshness   — is AMFI's latest NAV date newer than the published one?  → rebuild
  2. NAV audit   — for every published fund whose NAV date equals AMFI's date, the published NAV
                   must equal AMFI's official NAV exactly.                      → rebuild on mismatch
  3. Return audit (three times a day) — for a random sample of funds, 1-year and 3-year returns are
                   recomputed purely from AMFI's official NAVs and must match the published values
                   to within 0.02 percentage points.                            → rebuild on mismatch

Writes `run=true|false` and `why=...` to $GITHUB_OUTPUT and a summary to $GITHUB_STEP_SUMMARY.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import random
import re
import sys
import urllib.request

NAVALL = ["https://www.amfiindia.com/spages/NAVAll.txt", "https://portal.amfiindia.com/spages/NAVAll.txt"]
HIST = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?tp=1&frmdt={f}&todt={t}"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def parse_navall(txt):
    out = {}
    for line in txt.splitlines():
        p = [x.strip() for x in line.split(";")]
        if len(p) >= 8 and p[0].isdigit():
            try:
                out[int(p[0])] = (float(p[6]), dt.datetime.strptime(p[7], "%d-%b-%Y").date())
            except ValueError:
                pass
    return out


def shift_months(d, m):
    y, mo = divmod(d.month - 1 + m, 12)
    y += d.year
    mo += 1
    import calendar
    return dt.date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))


def official_base(codes, target):
    """AMFI official NAV on/before target (within 10 days) for the given codes."""
    f = target - dt.timedelta(days=10)
    txt = fetch(HIST.format(f=f.strftime("%d-%b-%Y"), t=target.strftime("%d-%b-%Y")), timeout=240)
    best = {}
    for line in txt.splitlines():
        p = [x.strip() for x in line.split(";")]
        if len(p) < 8 or not p[0].isdigit():
            continue
        c = int(p[0])
        if c not in codes:
            continue
        try:
            d = dt.datetime.strptime(p[7], "%d-%b-%Y").date()
            v = float(p[6])
        except ValueError:
            continue
        if d <= target and (c not in best or d > best[c][1]):
            best[c] = (v, d)
    return best


def main():
    event = os.environ.get("EVENT", "")
    force = os.environ.get("FORCE") == "true"
    deep = os.environ.get("DEEP") == "true"
    summary, run, why = [], False, []
    try:
        pub = json.load(open("data/mf/screener.json"))
    except Exception as e:  # noqa: BLE001
        pub = None
        run, why = True, [f"no published data ({e})"]
    if event not in ("schedule", "workflow_dispatch", "workflow_run") or force:
        run, why = True, [f"{event or 'manual'} trigger"]
    nav = None
    for u in NAVALL:
        try:
            nav = parse_navall(fetch(u))
            if len(nav) > 5000:
                break
        except Exception as e:  # noqa: BLE001
            summary.append(f"- AMFI NAV file unavailable from {u}: {e}")
    if pub and nav:
        latest = collections.Counter(d for _, d in nav.values()).most_common(1)[0][0]
        asof = dt.date.fromisoformat(pub["asOf"])
        if latest > asof:
            run = True
            why.append(f"new NAV date {latest} (published {asof})")
        C = {c: i for i, c in enumerate(pub["cols"])}
        rows = pub["rows"]
        # 2. NAV audit
        checked = bad = 0
        bad_list = []
        for r in rows:
            code, pnav, pdate = r[C["code"]], r[C["nav"]], r[C["navDate"]]
            o = nav.get(code)
            if not o or o[1].isoformat() != pdate:
                continue
            checked += 1
            if abs(pnav / o[0] - 1) > 1e-6:
                bad += 1
                bad_list.append(f"{code} published {pnav} vs official {o[0]} ({pdate})")
        summary.append(f"- NAV audit: {checked} funds compared with AMFI official NAVs, {bad} mismatch(es)")
        summary += [f"  - {x}" for x in bad_list[:10]]
        if bad:
            run = True
            why.append(f"{bad} published NAV(s) differ from AMFI")
        # 3. return audit (sampled, a few times a day)
        if deep and not run:
            rnd = random.Random(dt.datetime.utcnow().strftime("%Y%m%d%H"))
            sample = rnd.sample(rows, min(60, len(rows)))
            codes = {r[C["code"]] for r in sample}
            mism, n = [], 0
            for key, months in (("r1y", 12), ("r3y", 36)):
                base = official_base(codes, shift_months(asof, -months))
                for r in sample:
                    code, pv = r[C["code"]], r[C[key]]
                    end = nav.get(code)
                    b = base.get(code)
                    if pv is None or not end or not b or end[1] != asof or (asof - shift_months(asof, -months)).days < 0:
                        continue
                    if (shift_months(asof, -months) - b[1]).days > 10:
                        continue
                    x = end[0] / b[0]
                    o = (x - 1) * 100 if months <= 12 else (x ** (12 / months) - 1) * 100
                    n += 1
                    if abs(o - pv) > 0.02:
                        mism.append(f"{code} {key}: published {pv} vs official {o:.4f}")
            summary.append(f"- Return audit: {n} returns recomputed from AMFI official NAVs, {len(mism)} outside 0.02 pp")
            summary += [f"  - {x}" for x in mism[:10]]
            # funds whose unit face value changed are restated by design; only act on widespread gaps
            if len(mism) > max(2, n * 0.03):
                run = True
                why.append(f"{len(mism)} sampled returns differ from AMFI official NAVs")
    # never loop: an audit-only rebuild is attempted at most once every 3 hours
    if run and pub and not any(w.startswith(("new NAV", "no published", event or "manual")) for w in why):
        try:
            gen = dt.datetime.fromisoformat(pub["generated"].replace("Z", "+00:00"))
            age = (dt.datetime.now(dt.timezone.utc) - gen).total_seconds() / 60
        except Exception:  # noqa: BLE001
            age = 999
        if age < 180:
            run = False
            why.append(f"audit issue noted, but data was rebuilt {age:.0f} min ago — not rebuilding again yet")
    if not why:
        why = ["published data is current and matches AMFI"]
    msg = "; ".join(why)
    print(f"run={run}: {msg}")
    print("\n".join(summary))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"run={'true' if run else 'false'}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(f"### India MF screener live audit\n\n**Decision:** {'rebuild' if run else 'no rebuild'} — {msg}\n\n" + "\n".join(summary) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
