#!/usr/bin/env python3
"""
audit_sim.py — independent audit of the Simulator Buy ledger (written separately from sim_engine.py; it does not
import it). Recomputes every figure from the raw records and blocks publishing on any error.

Checks
  chain       every event's hash, the link to the previous event, sequence numbers, no duplicate order ids
  schedule    the trade dates are exactly the expected ones (start date, monthly day / weekday / quarter / year
              anniversaries rolled forward over weekends and exchange holidays) and the amounts are right
  plan        each order refers to a recorded plan snapshot; MF legs add up to the instalment; funds belong to the
              plan (or carry a note); ETF budgets = weight × instalment
  mf          NAV = recorded official NAV for the NAV date; NAV date rule (trade date, previous day for liquid
              funds, next NAV day after a fund holiday); stamp duty; units truncated to 3 decimals; credit T+2
  etf         close price on the trade date; whole units; every charge recomputed; budget = amount + slot carry;
              cost within budget; credit T+1
  cash        ETF cash = instalments − purchases (+ switch proceeds) and never negative
  holdings    units held = units bought − units sold, per fund / ETF
  value       latest valuation recomputed from holdings × latest price (+ pending orders, + ETF cash)
  xirr        recomputed by scripts/sim_xirr.js (JavaScript) and compared
  verified    share of MF NAVs confirmed against the official AMFI file (warning below 100%)
  daily       the daily portfolio summary journal: its own hash chain, one record per account / market per day, market
              closes = recorded closes, and every account summary recomputed (credited units, pending cost, prices,
              cash, value, invested, day change) from the ledger as of that day

Usage: python scripts/audit_sim.py --store sim_store.json --view sim_view.json --out sim_audit.json [--today D]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "scripts" / "sim_config.json").read_text())


class Audit:
    def __init__(self):
        self.n, self.errors, self.warnings, self.by = 0, [], [], {}

    def check(self, area, ok, msg, warn=False):
        self.n += 1
        b = self.by.setdefault(area, [0, 0])
        b[0] += 1
        if not ok:
            b[1] += 1
            (self.warnings if warn else self.errors).append(f"[{area}] {msg}")


def iso(d):
    return d.isoformat()


def day(s):
    return date.fromisoformat(s[:10])


def holidays():
    try:
        h = json.loads((ROOT / "data" / "nse_holidays.json").read_text())
    except Exception:  # noqa: BLE001
        return set()
    items = h if isinstance(h, list) else h.get("holidays", h)
    return {x for x in items if isinstance(x, str) and len(x) == 10}


H = holidays()


def open_day(d):
    return d.weekday() < 5 and iso(d) not in H


def roll(d):
    while not open_day(d):
        d += timedelta(days=1)
    return d


def biz_add(d, n):
    k = 0
    while k < n:
        d += timedelta(days=1)
        if open_day(d):
            k += 1
    return d


def expected_dates(freq, start, today):
    sc = CFG["schedule"]
    noms = {start}
    if freq == "m":
        y, m = start.year, start.month
        for _ in range(600):
            m = m % 12 + 1
            y += 1 if m == 1 else 0
            noms.add(date(y, m, sc["monthDay"]))
    elif freq == "w":
        for k in range(1, 3000):
            noms.add(start + timedelta(days=7 * k))
    elif freq == "q":
        for y in range(start.year, start.year + 60):
            for mo in sc["quarterMonths"]:
                if date(y, mo, sc["anchorDay"]) > start:
                    noms.add(date(y, mo, sc["anchorDay"]))
    elif freq == "y":
        for y in range(start.year + 1, start.year + 60):
            noms.add(date(y, sc["anchorMonth"], sc["anchorDay"]))
    return sorted({roll(n) for n in noms if roll(n) <= today})


def amount_for(risk, freq):
    m = CFG["monthly"][risk]
    return {"m": m, "w": int(round(m * 12 / 52 / 10) * 10), "q": m * 3}.get(freq, m * 12)


def r2(x):
    return round(x + 0.0, 2)


def charges(value, side, res, equity):
    f = CFG["etfFees"]
    brok = 0.0 if res == "resident" else min(max(value * f["brokerageNriRate"], f["brokerageNriMin"]), f["brokerageNriMax"])
    parts = [r2(brok), r2(value * f["exchange"]), r2(value * f["sebi"]), r2(value * f["ipft"]),
             r2(f["gst"] * (brok + value * f["exchange"] + value * f["sebi"])),
             r2(value * f["stampBuy"]) if side == "buy" else 0.0,
             r2(value * f["sttSellEquity"]) if side == "sell" and equity else 0.0,
             r2(f["dpSell"] * (1 + f["gst"])) if side == "sell" else 0.0]
    return r2(sum(parts))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--view", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--today")
    args = ap.parse_args()
    store = json.loads(Path(args.store).read_text())
    view = json.loads(Path(args.view).read_text())
    today = day(args.today) if args.today else datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    A = Audit()
    evs = store.get("events", [])
    start = day(store.get("meta", {}).get("start") or view.get("start") or CFG["start"])

    # chain
    prev = "genesis"
    for i, e in enumerate(evs):
        body = {k: v for k, v in e.items() if k != "h"}
        h = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        A.check("chain", h == e["h"], f"event {e.get('seq')} hash mismatch")
        A.check("chain", e["prev"] == prev, f"event {e.get('seq')} does not link to the previous event")
        A.check("chain", e["seq"] == i + 1, f"event {i + 1} has sequence {e.get('seq')}")
        prev = e["h"]
    for e in evs:
        if e["k"] == "plan":
            snap = store.get("plans", {}).get(e["ref"])
            A.check("chain", snap is not None and hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest() == e["sha"],
                    f"plan snapshot {e['ref']} changed after it was recorded")
    oids = [e["oid"] for e in evs if e["k"] == "order"]
    A.check("chain", len(oids) == len(set(oids)), "duplicate order ids")
    # no double buying: one instalment per account and date, one completion (allotment / fill / redemption) and at
    # most one funding per order, and every completion belongs to a recorded order
    seen_i, seen_d, seen_f, oset = set(), set(), set(), set(oids)
    for e in evs:
        if e["k"] == "instalment":
            k = (e["acct"], e["T"])
            A.check("chain", k not in seen_i and e["iid"] == f"{e['acct']}|{e['T']}", f"duplicate or mislabelled instalment {k}")
            seen_i.add(k)
        elif e["k"] in ("allot", "fill", "redeem"):
            A.check("chain", e["oid"] not in seen_d, f"order {e['oid']} completed more than once (double credit)")
            A.check("chain", e["oid"] in oset, f"{e['k']} for an unknown order {e['oid']}")
            seen_d.add(e["oid"])
        elif e["k"] == "fund":
            A.check("chain", e["oid"] not in seen_f, f"order {e['oid']} funded more than once")
            seen_f.add(e["oid"])
    # completions of unknown orders are already reported above; keep them out of the remaining checks so the audit
    # still finishes and records every problem
    evs = [e for e in evs if not (e["k"] in ("allot", "fill", "redeem", "fund") and e["oid"] not in oset)]
    A.check("chain", view.get("head") == (evs[-1]["h"] if evs else None), "view built from a different ledger")

    orders = {e["oid"]: e for e in evs if e["k"] == "order"}
    done = {e["oid"]: e for e in evs if e["k"] in ("allot", "fill", "redeem")}
    funded = {e["oid"]: e["amount"] for e in evs if e["k"] == "fund"}
    inst = [e for e in evs if e["k"] == "instalment"]
    prices = store.get("prices", {})
    amfi = prices.get("amfi", {})
    persons = {p["name"]: p for p in CFG["persons"]}

    # schedule & amounts
    for p in CFG["persons"]:
        exp = [iso(d) for d in expected_dates(p["freq"], start, today)]
        for prod in ("MF", "ETF"):
            aid = f"{p['name']}-{prod}"
            got = sorted(e["T"] for e in inst if e["acct"] == aid)
            A.check("schedule", got == exp, f"{aid}: trade dates {got[:3]}… differ from the expected {exp[:3]}…")
            for e in inst:
                if e["acct"] == aid:
                    A.check("schedule", e["amount"] == amount_for(p["risk"], p["freq"]), f"{aid} {e['T']}: amount {e['amount']}")
                    A.check("schedule", open_day(day(e["T"])), f"{aid}: instalment on a closed day {e['T']}")

    # plan & legs
    for e in inst:
        legs = [o for o in orders.values() if o.get("iid") == e["iid"]]
        A.check("plan", e["ref"] in store.get("plans", {}), f"{e['iid']}: plan {e['ref']} not recorded")
        tot = r2(sum(o["amount"] for o in legs))
        A.check("plan", abs(tot - e["amount"]) < 0.02, f"{e['iid']}: orders add up to {tot} vs instalment {e['amount']}")
        plan = store.get("plans", {}).get(e["ref"], {})
        risk = persons[e["acct"].rsplit("-", 1)[0]]["risk"]
        pid = CFG["horizon"] + risk
        if e["acct"].endswith("-MF"):
            allowed = set()
            for s in plan.get("mf", {}).get(pid, []):
                allowed |= {s["code"], *(s.get("alts") or [])} | ({s["upgrade"]["code"]} if s.get("upgrade") else set())
            for o in legs:
                A.check("plan", o["code"] in allowed or bool(o.get("note")), f"{o['oid']}: fund {o['code']} not in the plan")
        else:
            ws = {x["id"]: x for x in plan.get("etf", {}).get(pid, [])}
            for o in legs:
                x = ws.get(o["slot"])
                A.check("plan", x is not None and x["sym"] == o["sym"] and abs(o["amount"] - r2(e["amount"] * x["w"] / 100)) < 0.02,
                        f"{o['oid']}: ETF / budget does not match the plan")

    # MF allotments
    liquid = set(CFG["mfRules"]["liquidSubs"])
    subs = {}
    try:
        s = json.loads((ROOT / "data" / "mf" / "screener.json").read_text())
        c = s["cols"]
        subs = {r[c.index("code")]: r[c.index("sub")] for r in s["rows"]}
    except Exception:  # noqa: BLE001
        pass
    verified = total_mf = 0
    for oid, d in done.items():
        o = orders[oid]
        T = day(o["T"])
        if d["k"] == "allot":
            total_mf += 1
            amt = o["amount"] if o.get("amount") is not None else funded.get(oid)
            rec = (prices.get("mf", {}).get(str(o["code"])) or {}).get(d["navDate"])
            A.check("mf", rec is not None and abs(rec - d["nav"]) < 1e-9, f"{oid}: NAV {d['nav']} not the recorded NAV for {d['navDate']}")
            nd = day(d["navDate"])
            if subs.get(o["code"]) in liquid:
                A.check("mf", nd < T and (T - nd).days <= 6, f"{oid}: liquid-fund NAV date {nd} should precede {T}")
            else:
                A.check("mf", nd == T or (nd > T and (nd - T).days <= 7 and (prices.get("mf", {}).get(str(o["code"])) or {}).get(iso(T)) is None),
                        f"{oid}: NAV date {nd} for trade date {T}")
            stamp = r2(amt * CFG["mfRules"]["stampDuty"])
            A.check("mf", abs(d["stamp"] - stamp) < 0.005 and abs(d["net"] - r2(amt - stamp)) < 0.005, f"{oid}: stamp duty / net amount")
            units = math.floor(r2(amt - stamp) / d["nav"] * 1000 + 1e-9) / 1000
            A.check("mf", abs(d["units"] - units) < 1e-9, f"{oid}: units {d['units']} vs {units}")
            A.check("mf", d["credit"] == iso(biz_add(T, CFG["mfRules"]["creditBusinessDays"])), f"{oid}: credit date {d['credit']}")
            if str(o["code"]) in amfi.get(d["navDate"], {}):
                verified += 1
                A.check("mf", abs(amfi[d["navDate"]][str(o["code"])] - d["nav"]) < 1e-9, f"{oid}: NAV differs from the official AMFI file")
    if total_mf:
        A.check("verified", verified == total_mf, f"{total_mf - verified} of {total_mf} MF NAVs not yet confirmed against the official AMFI file", warn=True)

    # ETF fills, cash, carry
    res = {p["name"]: p["res"] for p in CFG["persons"]}
    try:
        cats = {e["s"]: e.get("k") or "" for e in json.loads((ROOT / "data" / "etf_momentum.json").read_text())["etfs"]}
    except Exception:  # noqa: BLE001
        cats = {}

    def is_eq(sym):
        k = cats.get(sym, "")
        return not any(x in k for x in ("Gold", "Silver", "Liquid", "Debt", "International", "Global"))
    # the ETF trade rule (sim_config etfRules): market-on-close at the official closing price of the first session the
    # ETF traded on or after the order date. Sessions come from the published daily price files, read here directly.
    ER, bars_of = CFG["etfRules"], {}

    def sessions(sym):
        if sym not in bars_of:
            try:
                b = json.loads((ROOT / "data" / "etf" / "d" / f"{sym}.json").read_text())
                bars_of[sym] = {f"{t // 10000:04d}-{t // 100 % 100:02d}-{t % 100:02d}": c for t, c in zip(b["t"], b["c"])}
            except Exception:  # noqa: BLE001
                bars_of[sym] = {}
        return bars_of[sym]

    def trade_rule(o, e, when, what):
        A.check("etf", e.get("rule", ER["id"]) == ER["id"] and e.get("priceTime", ER["priceTime"]) == ER["priceTime"],
                f"{o['oid']}: {what} recorded under rule {e.get('rule')} / {e.get('priceTime')}, not {ER['id']} / {ER['priceTime']}")
        bs = sessions(o["sym"])
        if bs and min(bs) <= o["T"]:                      # the published file covers the order date
            first = min((k for k in bs if k >= o["T"]), default=None)
            A.check("etf", first is None or when == first, f"{o['oid']}: {what} on {when}, but the first session on or after the order date {o['T']} was {first}")
            if when in bs:
                A.check("etf", abs(bs[when] - e["price"]) < 1e-6, f"{o['oid']}: {what} price {e['price']} differs from the published close {bs[when]} of {when}", warn=True)
    for o in orders.values():
        d = done.get(o["oid"])
        if o.get("sym") and d and d["k"] == "redeem":
            trade_rule(o, d, d["navDate"], "sale")
            px = (prices.get("etf", {}).get(o["sym"]) or {}).get(d["navDate"])
            A.check("etf", px is not None and abs(px - d["price"]) < 1e-9, f"{o['oid']}: sale price {d['price']} not the recorded close of {d['navDate']}")

    for aid in sorted({o["acct"] for o in orders.values() if o["acct"].endswith("-ETF")}):
        carry, cash = {}, 0.0
        r = res[aid.rsplit("-", 1)[0]]
        seq = sorted([e for e in evs if (e["k"] == "instalment" and e["acct"] == aid) or
                      (e["k"] in ("fill", "redeem") and orders[e["oid"]]["acct"] == aid)], key=lambda e: e["seq"])
        for e in seq:
            if e["k"] == "instalment":
                cash += e["amount"]
                continue
            o = orders[e["oid"]]
            if e["k"] == "redeem":
                if not o.get("withdraw"):
                    cash += e["net"]
                continue
            amt = o["amount"] if o.get("amount") is not None else funded.get(o["oid"])
            budget = r2(amt + carry.get(o["slot"], 0.0))
            px = (prices.get("etf", {}).get(o["sym"]) or {}).get(e["tradeDate"])
            A.check("etf", px is not None and abs(px - e["price"]) < 1e-9, f"{o['oid']}: price {e['price']} not the recorded close of {e['tradeDate']}")
            A.check("etf", day(e["tradeDate"]) >= day(o["T"]) and open_day(day(e["tradeDate"])), f"{o['oid']}: trade date {e['tradeDate']}")
            trade_rule(o, e, e["tradeDate"], "buy")
            A.check("etf", isinstance(e["units"], int) and e["units"] >= 0, f"{o['oid']}: units not whole")
            A.check("etf", abs(e["budget"] - budget) < 0.011, f"{o['oid']}: budget {e['budget']} vs {budget}")
            ch = charges(e["units"] * e["price"], "buy", r, is_eq(o["sym"]))
            A.check("etf", abs(e["charges"]["total"] - ch) < 0.011 and abs(e["gross"] - r2(e["units"] * e["price"])) < 0.011, f"{o['oid']}: charges / gross")
            A.check("etf", e["gross"] + e["charges"]["total"] <= budget + 0.011, f"{o['oid']}: spent more than the budget")
            nxt = e["units"] + 1
            A.check("etf", nxt * e["price"] + charges(nxt * e["price"], "buy", r, is_eq(o["sym"])) > budget - 0.011,
                    f"{o['oid']}: one more unit was affordable")
            A.check("etf", abs(e["carry"] - r2(budget - e["gross"] - e["charges"]["total"])) < 0.011, f"{o['oid']}: carry")
            A.check("etf", e["credit"] == iso(biz_add(day(e["tradeDate"]), CFG["etfFees"]["creditBusinessDays"])), f"{o['oid']}: credit date")
            carry[o["slot"]] = e["carry"]
            cash = r2(cash - e["gross"] - e["charges"]["total"])
            A.check("cash", cash >= -0.01, f"{aid}: cash negative ({cash}) after {o['oid']}")
        acc = next((a for a in view["accounts"] if a["id"] == aid), None)
        if acc is not None:
            A.check("cash", abs((acc.get("cash") or 0) - cash) < 0.02, f"{aid}: cash {acc.get('cash')} vs recomputed {cash}")

    # sell review & tax harvesting rules (sim_config sellRules / taxHarvest)
    R, TH = CFG["sellRules"], CFG["taxHarvest"]
    m = start.month - 1 + R["minHoldMonths"]
    year1 = date(start.year + m // 12, m % 12 + 1, min(start.day, 28))
    reviews = {e["rid"]: e for e in evs if e["k"] in ("review", "harvest")}
    redeems = {e["oid"]: e for e in evs if e["k"] == "redeem"}
    harvested = {}
    for oid, o in orders.items():
        if o["side"] != "sell" or o.get("level") not in ("weak", "severe", "harvest"):
            continue
        rv = reviews.get(o["iid"])
        A.check("rules", rv is not None, f"{oid}: sale without its review / harvest record")
        d = redeems.get(oid)
        if not d:
            continue
        key = str(o.get("code") or o.get("sym"))
        if o["level"] in ("weak", "harvest"):
            bad = [g for g in d["gains"] if g["class"] != "debt" and g["term"] != "LT"]
            A.check("rules", not bad, f"{oid}: {o['level']} sale includes short-term / slab-rate lots {[(g['buyDate'], g['days']) for g in bad][:3]}")
            A.check("rules", not (d["charges"].get("exitLoad") or 0), f"{oid}: {o['level']} sale paid exit load {d['charges'].get('exitLoad')}")
        if o["level"] == "weak":
            it = next((i for i in (rv or {}).get("items", []) if i["key"] == key), {})
            A.check("rules", day(o["T"]) >= year1, f"{oid}: non-urgent sale inside the account's first year")
            A.check("rules", it.get("streak", 0) >= R["droppedStreak"], f"{oid}: sold after {it.get('streak')} flagged reviews (needs {R['droppedStreak']})")
        if o["level"] == "harvest":
            T = day(o["T"])
            fy = T.year if T.month >= 4 else T.year - 1
            person = o["acct"].rsplit("-", 1)[0]
            harvested[(person, fy)] = harvested.get((person, fy), 0.0) + sum(g["gain"] for g in d["gains"] if g["class"] == "equity")
        inn = orders.get(oid.replace("|out", "|in"))
        if inn and d:
            f = next((e for e in evs if e["k"] == "fund" and e["oid"] == inn["oid"]), None)
            A.check("rules", f is None or abs(f["amount"] - d["net"]) < 0.01, f"{oid}: switch-in funded {f and f['amount']} vs sale proceeds {d['net']}")
            if o["level"] == "harvest":
                A.check("rules", str(inn.get("code") or inn.get("sym")) == key, f"{oid}: harvest buy-back is a different fund")
    for (person, fy), g in harvested.items():
        A.check("rules", g <= CFG["tax"]["ltcgExempt"] + 1, f"{person} FY{fy}: harvested equity gains {g:.0f} exceed the yearly exemption")

    # holdings & value
    for acc in view["accounts"]:
        aid = acc["id"]
        units = {}
        for e in evs:
            if e["k"] in ("allot", "fill") and orders[e["oid"]]["acct"] == aid:
                k = str(orders[e["oid"]].get("code") or orders[e["oid"]].get("sym"))
                units[k] = units.get(k, 0) + e["units"]
            if e["k"] == "redeem" and orders[e["oid"]]["acct"] == aid:
                k = str(orders[e["oid"]].get("code") or orders[e["oid"]].get("sym"))
                units[k] = units.get(k, 0) - e["units"]
        held = {h["key"]: h["units"] for h in acc["holdings"]}
        for k, u in units.items():
            if abs(u) > 1e-6:
                A.check("holdings", abs(held.get(k, 0) - u) < 1e-6, f"{aid}: {k} holds {held.get(k)} vs recomputed {round(u, 6)}")
        if acc["series"]:
            book = prices.get("mf" if aid.endswith("-MF") else "etf", {})
            for h in acc["holdings"]:
                A.check("value", h["price"] is not None and (book.get(h["key"]) or {}).get(h["priceDate"]) == h["price"],
                        f"{aid}: {h['key']} valued at {h['price']} — not the recorded price for {h['priceDate']}")
                A.check("value", h["priceDate"] is not None and (day(acc["series"][-1][0]) - day(h["priceDate"])).days <= 12,
                        f"{aid}: {h['key']} price from {h['priceDate']} is stale", warn=True)
            val = sum(h["units"] * (h["price"] or 0) for h in acc["holdings"])
            pend = sum((t["amount"] or 0) for t in acc["txns"] if t["side"] == "buy" and t.get("units") is None) if aid.endswith("-MF") else 0.0
            val += pend + (acc.get("cash") or 0)
            A.check("value", abs(val - acc["value"]) < 1.0, f"{aid}: value {acc['value']} vs recomputed {r2(val)}")
            inv = sum(e["amount"] for e in inst if e["acct"] == aid)
            A.check("value", abs(inv - acc["invested"]) < 0.01, f"{aid}: invested {acc['invested']} vs {inv}")

    # daily portfolio summaries (store["days"]): own hash chain, one record per account / market per day, and every
    # figure recomputed from the ledger as of that day and the recorded official prices
    days = store.get("days", [])
    prev, seen = "genesis", set()
    for i, e in enumerate(days):
        body = {k: v for k, v in e.items() if k != "h"}
        h = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        A.check("daily", h == e["h"] and e["prev"] == prev and e["seq"] == i + 1, f"daily record {e.get('seq')} hash / link / sequence")
        prev = e["h"]
        k = (e.get("a") or "mkt", e["d"])
        A.check("daily", k not in seen, f"daily record {k} recorded twice")
        seen.add(k)
        A.check("daily", open_day(day(e["d"])) and day(e["d"]) <= today, f"daily record {k} on a closed or future day")
    book = prices
    for e in days:
        if e["t"] != "mkt":
            continue
        for sym, px, pd, qx, qd in e["m"]:
            b = book.get("etf", {}).get(sym) or {}
            A.check("daily", b.get(pd) == px and b.get(qd) == qx and qd < pd, f"market {e['d']} {sym}: closes {qx}→{px} not the recorded closes of {qd}/{pd}")
    lastd, acc_evs, acc_inst = {}, {}, {}
    for x in evs:                                   # per-account indexes keep this linear in the ledger size
        if x["k"] in ("allot", "fill", "redeem"):
            acc_evs.setdefault(orders[x["oid"]]["acct"], []).append(x)
    for x in inst:
        acc_inst.setdefault(x["acct"], []).append(x)
    acc_orders = {}
    for o in orders.values():
        acc_orders.setdefault(o["acct"], []).append(o)
    for e in days:
        if e["t"] != "acct":
            continue
        aid, ds = e["a"], e["d"]
        mf = aid.endswith("-MF")
        lots, cash, pend, inv, out = {}, 0.0, 0.0, 0.0, 0.0
        for x in acc_inst.get(aid, []):
            if x["T"] <= ds:
                inv += x["amount"]
                cash += 0 if mf else x["amount"]
        for x in acc_evs.get(aid, []):
            o = orders[x["oid"]]
            if o["T"] > ds:
                continue
            key = str(o.get("code") or o.get("sym"))
            if x["k"] == "redeem":
                left = x["units"]
                for l in lots.get(key, []):
                    take = min(left, l[1])
                    if take <= 0:
                        continue
                    l[2] *= 1 - take / l[1]
                    l[1] = round(l[1] - take, 6)
                    left = round(left - take, 6)
                if o.get("withdraw"):
                    out += x["net"]
                elif not mf:
                    cash += x["net"]
                continue
            cost = x["amount"] if x["k"] == "allot" else x["gross"] + x["charges"]["total"]
            lots.setdefault(key, []).append([x["credit"], x["units"], cost])
            if not mf:
                cash -= x["gross"] + x["charges"]["total"]
        if mf:
            for o in acc_orders.get(aid, []):
                if o["side"] == "buy" and o["T"] <= ds and o["oid"] not in done:
                    pend += o["amount"] if o.get("amount") is not None else funded.get(o["oid"], 0.0)
        hold = {h[0]: h for h in e["hold"]}
        val = 0.0
        for key, ls in lots.items():
            cu = round(sum(l[1] for l in ls if l[0] <= ds), 6)
            uc = sum(l[2] for l in ls if l[0] > ds and l[1] > 1e-9)
            h = hold.get(key)
            if cu <= 1e-9 and uc <= 0.005:
                continue
            A.check("daily", h is not None and abs(h[1] - cu) < 1e-6 and abs(h[7] - uc) < 0.02, f"{aid} {ds}: {key} credited {h and h[1]} / pending cost {h and h[7]} vs {cu} / {r2(uc)}")
            if h is None:
                continue
            if cu <= 1e-9:
                val += uc                               # nothing credited: counted at cost, no price used
                continue
            b = book.get("mf" if mf else "etf", {}).get(key) or {}
            A.check("daily", h[3] is not None and h[3] <= ds and b.get(h[3]) == h[2], f"{aid} {ds}: {key} price {h[2]} not the recorded price of {h[3]}")
            later = [x for x in b if h[3] and h[3] < x <= ds]
            A.check("daily", not later, f"{aid} {ds}: {key} valued at {h[3]} although a later price ({later[:1]}) is on record", warn=True)
            val += cu * (h[2] or 0) + uc
        A.check("daily", abs(e["pend"] - pend) < 0.02 and abs(e["cash"] - (0.0 if mf else cash)) < 0.02, f"{aid} {ds}: pending {e['pend']} / cash {e['cash']} vs {r2(pend)} / {r2(cash)}")
        val += pend + (0.0 if mf else cash)
        A.check("daily", abs(e["val"] - val) < 0.1 and abs(e["inv"] - inv) < 0.01 and abs(e["out"] - out) < 0.02,
                f"{aid} {ds}: value / invested {e['val']} / {e['inv']} vs recomputed {r2(val)} / {r2(inv)}")
        lt = e.get("lt", lastd.get(aid, {}).get("_lt", {}))
        e["_lt"] = lt
        lb = store.get("lookthrough", {})
        A.check("daily", all((lb.get(f"{'mf' if mf else 'etf'}:{k}") or {}).get(m) is not None for k, m in lt.items()),
                f"{aid} {ds}: a look-through reference has no recorded composition")
        p = lastd.get(aid)
        if p:
            flow = (e["inv"] - p["inv"]) - (e["out"] - p["out"])
            ok = abs(e["chg"] - (e["val"] - p["val"] - flow)) < 0.02 and (not p["val"] or abs(e["pct"] - e["chg"] / p["val"] * 100) < 0.001) \
                and abs(e["bchg"] - (e["bval"] - p["bval"] - flow)) < 0.02 and not e["first"]
        else:
            net = e["inv"] - e["out"]
            ok = e["first"] and abs(e["chg"] - (e["val"] - net)) < 0.02 and abs(e["bchg"] - (e["bval"] - net)) < 0.02
        A.check("daily", ok, f"{aid} {ds}: day change {e['chg']} ({e['pct']}%) does not follow from the previous summary")
        lastd[aid] = e

    # XIRR in JavaScript
    try:
        wd = {e["oid"]: e for e in evs if e["k"] == "redeem" and orders[e["oid"]].get("withdraw")}
        payload = [{"id": a["id"], "flows": [[e["T"], -e["amount"]] for e in inst if e["acct"] == a["id"]] +
                    [[d["payout"], d["net"]] for oid, d in wd.items() if orders[oid]["acct"] == a["id"]] +
                    ([[a["series"][-1][0], a["series"][-1][2]]] if a["series"] and a["series"][-1][2] > 0 else []),
                    "xirr": a.get("xirr")} for a in view["accounts"]]
        out = subprocess.run(["node", str(ROOT / "scripts" / "sim_xirr.js")], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
        js = json.loads(out.stdout)
        for r in js:
            A.check("xirr", r["ok"], f"{r['id']}: XIRR {r['mine']} vs recomputed {r['js']}")
    except Exception as e:  # noqa: BLE001
        A.check("xirr", False, f"XIRR cross-check could not run: {e}")

    res_out = {"v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "events": len(evs),
               "checks": A.n, "errors": A.errors[:200], "warnings": A.warnings[:200], "nErrors": len(A.errors),
               "nWarnings": len(A.warnings), "areas": {k: {"checks": v[0], "issues": v[1]} for k, v in sorted(A.by.items())}}
    Path(args.out).write_text(json.dumps(res_out, indent=1))
    print(f"Simulator Buy audit: {A.n} checks · {len(A.errors)} errors · {len(A.warnings)} warnings")
    for k, v in sorted(A.by.items()):
        print(f"  {k:10} {v[0]:6} checks {v[1]:4} issues")
    for m in A.errors[:25]:
        print("  ERROR", m)
    for m in A.warnings[:5]:
        print("  warn ", m)
    return 1 if A.errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — a ledger the audit cannot even read is a failed audit
        print(f"Simulator Buy audit: FAILED — the ledger could not be checked ({type(e).__name__}: {e})")
        sys.exit(1)
