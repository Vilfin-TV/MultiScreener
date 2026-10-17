#!/usr/bin/env python3
"""Portfolio-holdings audit for the India MF Screener → data/mf/p/_audit.json.

Run after every holdings build (and again after the repair pass). For every fund house with a configured source
(`build_mf_holdings.SOURCES`) it checks:

  · behind     — the latest portfolio month published by the fund house should be available (fund houses publish
                 within 10 days of month-end) but the stored month is older, or nothing is stored yet;
  · failed     — the fund house's files could not be found or downloaded on the last run;
  · dropped    — fewer of its funds have a portfolio than at the previous audit;
  · missing    — individual funds of the fund house that have no current portfolio (with the reason, when known).

Fund houses that are behind / failed / dropped are written to the `retry` list (and to $GITHUB_OUTPUT as `retry=`),
which the workflow re-processes once with `--force`. Funds of fund houses without a source are listed as
`uncovered`. The audit itself never edits portfolio data; it always exits 0 so a failed re-check never blocks the
verified data from publishing.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MF = ROOT / "data" / "mf"
P = MF / "p"
OUT = P / "_audit.json"
REPORT = ROOT / ".mfcache" / "holdings" / "report.json"
PUBLISH_DAY = 11          # by this day of the month the previous month's portfolio should be out
sys.path.insert(0, str(ROOT / "scripts"))


def expected_month(today: date) -> str:
    """Latest portfolio month every fund house should have published by `today`."""
    y, m = today.year, today.month - (1 if today.day >= PUBLISH_DAY else 2)
    while m < 1:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


def main() -> int:
    from build_mf_holdings import SOURCES, MAX_AGE_DAYS, pf_age_days
    today = date.today()
    scr = json.loads((MF / "screener.json").read_text())
    C = {c: i for i, c in enumerate(scr["cols"])}
    meta = json.loads((P / "_meta.json").read_text()) if (P / "_meta.json").exists() else {}
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    report = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    if not report:                                  # keep the last known table diagnostics when this run parsed nothing
        report = {a: {"unmatched": [{"ctx": [t]} for t in h.get("unmatchedSample", [])]} for a, h in prev.get("houses", {}).items()}
    have = {}
    for f in P.glob("*.json"):
        if not f.name.startswith("_"):
            for code, v in json.loads(f.read_text()).items():
                if pf_age_days(v["asOf"], today) <= MAX_AGE_DAYS:
                    have[code] = v["asOf"]
    funds_by_amc = defaultdict(list)
    for r in scr["rows"]:
        funds_by_amc[scr["amcs"][r[C["amc"]]]].append(r)
    want = expected_month(today)
    houses, retry, uncovered = {}, [], {}
    for amc, rows in sorted(funds_by_amc.items()):
        if amc not in SOURCES:
            uncovered[amc] = len(rows)
            continue
        m = meta.get(amc, {})
        got = [r for r in rows if str(r[C["code"]]) in have]
        miss = [r for r in rows if str(r[C["code"]]) not in have]
        issues = []
        if not m.get("month") or m["month"] < want:
            issues.append(f"behind: stored {m.get('month') or 'nothing'}, expected {want}")
        if m.get("discoveryFail") == today.isoformat():
            issues.append("failed: portfolio files not found on the fund-house site this run")
        if m.get("dlFail"):
            issues.append(f"failed: {m['dlFail']} file download(s) failed")
        before = (prev.get("houses", {}).get(amc) or {}).get("covered")
        if before is not None and len(got) < before:
            issues.append(f"dropped: {before} → {len(got)} funds with a portfolio")
        rep = report.get(amc) or {}
        unmatched = len(rep.get("unmatched") or [])
        houses[amc] = {
            "funds": len(rows), "covered": len(got), "month": m.get("month"), "issues": issues,
            "unmatchedTables": unmatched,
            "unmatchedSample": [(u.get("ctx") or [u.get("sheet", "")])[0][:90] for u in (rep.get("unmatched") or [])][:30],
            "missing": [{"code": r[C["code"]], "name": r[C["name"]], "sub": r[C["sub"]]} for r in miss][:60],
        }
        if issues:
            retry.append(amc)
    total = sum(len(r) for r in funds_by_amc.values())
    covered_src = sum(h["funds"] for h in houses.values())
    out = {
        "v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "expectedMonth": want,
        "funds": total, "withPortfolio": len(have),
        "covered": {"houses": len(houses), "funds": covered_src, "withPortfolio": sum(h["covered"] for h in houses.values())},
        "retry": retry, "houses": houses,
        "uncovered": dict(sorted(uncovered.items(), key=lambda kv: -kv[1])),
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"Portfolios: {len(have)} of {total} funds · configured fund houses: {out['covered']['withPortfolio']} of "
          f"{covered_src} funds · expected month {want}")
    for amc, h in houses.items():
        flag = "RETRY " if h["issues"] else "ok    "
        print(f"  {flag}{amc}: {h['covered']}/{h['funds']} funds, month {h['month']}"
              + (f", {h['unmatchedTables']} unmatched tables" if h["unmatchedTables"] else "")
              + ("" if not h["issues"] else " — " + "; ".join(h["issues"])))
    print("  Not configured: " + ", ".join(f"{a} ({n})" for a, n in out["uncovered"].items()))
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as fh:
            fh.write("retry=" + ",".join(retry) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
