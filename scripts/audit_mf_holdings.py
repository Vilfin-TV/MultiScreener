#!/usr/bin/env python3
"""Data audit for the India MF Screener: portfolio holdings (default) and Smart SIP accuracy (--smartsip).

Holdings → data/mf/p/_audit.json.

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

Smart SIP (--smartsip) → data/mf/smartsip_audit.json. Recomputes every plan from the published screener data and
compares it with data/mf/smartsip.json:
  errors (exit 1 — the workflow rebuilds the planner once, re-audits, and blocks publishing if any remain):
    · plan built from an older screener date than the screener; weights not summing to 100; asset mix, expense
      ratio, expected return or past return of the mix not matching the slot figures / screener data;
    · a recommended fund missing from the screener, closed to lump sums or SIPs, above the ₹1,000 lump-sum limit,
      or in the wrong category for its slot; figures quoted in a fund's checklist (expense ratio, 3-year return,
      fund size, lump-sum minimum) not matching the screener; a paused slot without gate details;
  warnings (reported, never blocking): stale market inputs (yields, index valuations, global series, stock P/E),
    implausible one-day moves in yields, recommended funds without a current portfolio (credit-quality and fund
    P/E checks then fall back to category rules), alternates no longer in the screener.
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
    from build_mf_holdings import SOURCES as FILE_SOURCES, PAGE_SOURCES, MAX_AGE_DAYS, pf_age_days
    SOURCES = {**FILE_SOURCES, **PAGE_SOURCES}
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


# ═════════════════════════════ SMART SIP ═════════════════════════════
SIP_OUT = MF / "smartsip_audit.json"


def _num(txt: str) -> float | None:
    import re
    m = re.search(r"-?[\d,]+(?:\.\d+)?", txt or "")
    return float(m.group(0).replace(",", "")) if m else None


def allowed_pools(SS, key: str) -> set:
    """Every category a slot may draw from: its own pools, the rate-regime debt pools and its fallback slots' pools."""
    out = set()
    for k in [key] + list(SS.FALLBACK.get(key, [])):
        out |= set((SS.SLOTS.get(k) or (None, None, []))[2] or [])
        for pools in (SS.DEBT_POOLS.get(k) or {}).values():
            out |= set(pools)
    return out


def audit_smartsip() -> int:
    import re
    import build_smart_sip as SS
    from build_mf_holdings import MAX_AGE_DAYS, pf_age_days
    scr = json.loads((MF / "screener.json").read_text())
    C = {c: i for i, c in enumerate(scr["cols"])}
    F = {r[C["code"]]: r for r in scr["rows"]}
    g = lambda code, col: (F.get(code) or [None] * len(C))[C[col]]  # noqa: E731
    sip = json.loads((MF / "smartsip.json").read_text())
    macro = json.loads((MF / "macro.json").read_text()) if (MF / "macro.json").exists() else {}
    fpe = json.loads((MF / "fund_pe.json").read_text()) if (MF / "fund_pe.json").exists() else {}
    have_pf = set()
    for f in P.glob("*.json"):
        if not f.name.startswith("_"):
            have_pf |= {int(c) for c, v in json.loads(f.read_text()).items() if pf_age_days(v["asOf"]) <= MAX_AGE_DAYS}
    asof = date.fromisoformat(scr["asOf"])
    errors, warns = [], []
    E = lambda m: errors.append(m)  # noqa: E731
    W = lambda m: warns.append(m)   # noqa: E731
    near = lambda a, b, tol: a is not None and b is not None and abs(a - b) <= tol  # noqa: E731

    # ── freshness of the plan and its inputs
    if sip.get("asOf") != scr["asOf"]:
        E(f"planner built for {sip.get('asOf')} but screener is {scr['asOf']}")
    def days(d):
        try:
            return (asof - date.fromisoformat(str(d)[:10])).days
        except Exception:  # noqa: BLE001
            return 999
    if days(macro.get("valuationAsOf")) > 5:
        W(f"index valuations are from {macro.get('valuationAsOf')} ({days(macro.get('valuationAsOf'))} days old)")
    hist = macro.get("rateHist") or []
    if hist and days(hist[-1].get("d")) > 10:
        W(f"interest-rate data last updated {hist[-1].get('d')}")
    if len(hist) >= 2:
        a, b = hist[-2], hist[-1]
        for k, lim in (("g10", 0.30), ("tb91", 0.50), ("tb182", 0.50), ("tb364", 0.50), ("repo", 0.50)):
            if a.get(k) is not None and b.get(k) is not None and abs(b[k] - a[k]) > lim:
                W(f"{k} moved {a[k]} → {b[k]} between {a['d']} and {b['d']} — check the source")
    for key, ser in (macro.get("global") or {}).items():
        if days(ser.get("d")) > 7:
            W(f"global series {ser.get('label', key)} last value {ser.get('d')}")
    if days(fpe.get("asOf")) > 5:
        W(f"stock P/E data is from {fpe.get('asOf')}")

    # ── every plan
    pf_missing = set()
    for pid, pl in sip["plans"].items():
        slots = pl["slots"]
        tw = sum(s["w"] for s in slots)
        if tw != 100:
            E(f"{pid}: weights add up to {tw}")
        mix = defaultdict(int)
        for s in slots:
            mix[s["asset"]] += s["w"]
        if {k: v for k, v in mix.items() if v} != {k: v for k, v in (pl.get("mix") or {}).items() if v}:
            E(f"{pid}: asset mix {dict(pl.get('mix') or {})} does not match the slots {dict(mix)}")
        ter = round(sum((g(s["code"], "ter") or 0) * s["w"] for s in slots) / 100, 2)
        if not near(ter, pl.get("ter"), 0.011):
            E(f"{pid}: plan expense ratio {pl.get('ter')} vs {ter} from the screener")
        er = round(sum(s["er"] * s["w"] for s in slots) / 100, 2)
        if not near(er, pl.get("er"), 0.011):
            E(f"{pid}: plan expected return {pl.get('er')} vs {er} from its slots")
        for col in ("r3y", "r5y"):
            have = [(s["w"], g(s["code"], col)) for s in slots if g(s["code"], col) is not None]
            w = sum(x for x, _ in have)
            calc = round(sum(x * r for x, r in have) / w, 2) if w >= 70 else None
            pub = ((pl.get("hist") or {}).get(col) or {}).get("v")
            if (calc is None) != (pub is None) or (calc is not None and not near(calc, pub, 0.011)):
                E(f"{pid}: past {col} of the mix {pub} vs {calc} recomputed")
        for s in slots:
            code, sid = s["code"], f"{pid}/{s['key']}"
            if code not in F:
                E(f"{sid}: fund {code} is not in the screener")
                continue
            if s["w"] == 0 and not s.get("gate"):
                E(f"{sid}: weight 0 without gate details")
            if s["w"] > 0:
                buy = g(code, "buy") or ""
                if "L" not in buy or "S" not in buy:
                    E(f"{sid}: {g(code, 'name')} is not open for both lump sums and SIPs (status '{buy}')")
                if (g(code, "lumpMin") or 0) > SS.LUMP_MAX:
                    E(f"{sid}: lump-sum minimum ₹{g(code, 'lumpMin')} above ₹{SS.LUMP_MAX}")
            name = g(code, "name") or ""
            fallback_ok = g(code, "sub") in allowed_pools(SS, s["key"])     # filled from a fallback slot's pool
            if s["key"] in ("metal", "theme") and fallback_ok:
                pass
            elif s["key"] == "metal":
                ok = g(code, "sub") in ("gold", "silver") and g(code, "sub") == (sip.get("metal") or {}).get("applied", g(code, "sub"))
                if not ok:
                    E(f"{sid}: {name} ({g(code, 'sub')}) does not match the chosen metal {(sip.get('metal') or {}).get('applied')}")
            elif s["key"] == "theme":
                sec = next((x for x in SS.SECTORS if x[0] == sip.get("sector")), None)
                if sec is None or g(code, "sub") not in sec[3] or (sec[4] and not re.search(sec[4], name, re.I)) \
                        or (sec[5] and re.search(sec[5], name, re.I)):
                    E(f"{sid}: {name} is not a fund of the chosen sector {sip.get('sector')}")
            elif s["key"] == "intl" and any(c[0] == "International exposure" and c[1] for c in s.get("checks") or []):
                if g(code, "sub") != "sec_innov":                 # backup pool: Indian funds with an overseas sleeve
                    E(f"{sid}: international backup {name} is not an innovation / opportunities fund")
            else:
                pools = allowed_pools(SS, s["key"])
                if pools and g(code, "sub") not in pools:
                    E(f"{sid}: {name} is in category {g(code, 'sub')}, not one of {sorted(pools)}")
                if s["key"] == "momentum" and g(code, "sub") in (SS.SLOTS["momentum"][2] or []) and not SS.RX_MOMENTUM.search(name):
                    E(f"{sid}: {name} is not a momentum index fund")
            for name, ok, txt in s.get("checks") or []:
                v = _num(txt)
                if name == "Expense ratio" and g(code, "ter") is not None and not near(v, g(code, "ter"), 0.006):
                    E(f"{sid}: checklist expense ratio {v} vs screener {g(code, 'ter')}")
                elif name == "3-year record" and g(code, "r3y") is not None and not near(v, g(code, "r3y"), 0.006):
                    E(f"{sid}: checklist 3-year return {v} vs screener {g(code, 'r3y')}")
                elif name == "Fund size" and g(code, "aum") is not None and not near(v, g(code, "aum"), 1.0):
                    E(f"{sid}: checklist fund size {v} vs screener {g(code, 'aum')}")
                elif name == "Lump-sum minimum" and g(code, "lumpMin") is not None and not near(v, g(code, "lumpMin"), 0.5):
                    E(f"{sid}: checklist lump-sum minimum {v} vs screener {g(code, 'lumpMin')}")
            up = s.get("upgrade")
            if up:                                   # fund used when the investor's amount covers a higher minimum
                uc = up.get("code")
                if uc not in F:
                    E(f"{sid}: upgrade fund {uc} is not in the screener")
                else:
                    if not all(c[1] for c in up.get("checks") or [[0, False]]):
                        E(f"{sid}: upgrade fund {g(uc, 'name')} does not pass every check")
                    if g(uc, "lumpMin") != up.get("min") or not (SS.LUMP_MAX < (up.get("min") or 0) <= SS.UPGRADE_MAX_MIN):
                        E(f"{sid}: upgrade minimum {up.get('min')} vs screener {g(uc, 'lumpMin')}")
                    if g(uc, "sub") != g(code, "sub") and g(uc, "sub") not in allowed_pools(SS, s["key"]):
                        E(f"{sid}: upgrade fund {g(uc, 'name')} outside the slot's categories")
                    if "L" not in (g(uc, "buy") or "") or "S" not in (g(uc, "buy") or ""):
                        E(f"{sid}: upgrade fund {g(uc, 'name')} not open for lump sums and SIPs")
            for alt in s.get("alts") or []:
                if alt not in F:
                    W(f"{sid}: alternate {alt} is no longer in the screener")
            if s["w"] > 0 and code not in have_pf:
                pf_missing.add((code, g(code, "name"), g(code, "amc")))
    # ── market-dip lump sums (dip block): 7 trigger checks per segment, 19 fund checks per candidate, 26 per plan entry,
    # tier amounts within the rule, the candidate is the plan's own fund for that segment, fund verdicts consistent
    dp = sip.get("dip") or {}
    rule = dp.get("rule") or {}
    tiers = sorted(rule.get("tiers") or [], key=lambda t: -t[0])
    if not dp.get("segments") or not tiers:
        E("dip: block missing")
    for k, sg in (dp.get("segments") or {}).items():
        want = next(((t, max(rule["min"], min(rule["max"], a))) for t, a in tiers if sg["fall"] >= t), (0, 0))
        if (sg["tier"], sg["amount"]) != want:
            E(f"dip {k}: tier / amount {sg['tier']} / {sg['amount']} vs {want} for a {sg['fall']}% fall")
        if len(sg.get("checks") or []) != 7 or (sg["signal"] and not all(c[1] for c in sg["checks"])):
            E(f"dip {k}: trigger checks")
    cands = dp.get("cands") or []
    for i, c in enumerate(cands):
        if len(c["checks"]) != 19 or c["fundOk"] != all(x[1] for x in c["checks"][:18]) or c["code"] not in F:
            E(f"dip candidate {i} ({c.get('name')}): checks / verdict / fund")
    rv = dp.get("reserve") or {}
    if rv.get("code") not in F or g(rv.get("code"), "sub") != "liquid" or "L" not in (g(rv.get("code"), "buy") or ""):
        E(f"dip: reserve fund {rv.get('code')} not an open liquid fund")
    for pid, ents in (dp.get("plans") or {}).items():
        codes = {sl["key"]: sl["code"] for sl in sip["plans"][pid]["slots"]}
        for seg, x in ents.items():
            c = cands[x["c"]] if 0 <= x["c"] < len(cands) else None
            allc = (dp["segments"][seg]["checks"] if seg in dp.get("segments", {}) else []) + (c["checks"] if c else [])
            if not c or c["seg"] != seg or codes.get(c["slot"]) != c["code"] or x["n"] != 26 or x["passed"] != sum(1 for y in allc if y[1]) \
                    or x["ok"] != all(y[1] for y in allc) or len(allc) != 26:
                E(f"dip {pid} {seg}: entry does not match the plan's fund / its 26 checks")
    if pf_missing:
        amcs = scr["amcs"]
        W(f"{len(pf_missing)} recommended funds have no current portfolio (credit-quality / fund P/E checks use "
          f"category rules): " + "; ".join(f"{n} ({amcs[a]})" for _, n, a in sorted(pf_missing, key=lambda x: x[1])))
    out = {"v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "asOf": scr["asOf"],
           "plans": len(sip["plans"]), "errors": errors, "warnings": warns}
    SIP_OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"Smart SIP audit: {len(sip['plans'])} plans · {len(errors)} error(s) · {len(warns)} warning(s)")
    for m in errors:
        print("  ✗ " + m)
    for m in warns:
        print("  ! " + m)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(audit_smartsip() if "--smartsip" in sys.argv else main())
