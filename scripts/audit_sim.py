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
  etf         close price on the trade date; whole units; every charge recomputed; budget = amount + carry of the same role (switch-ins and dip buys keep their own);
              cost within budget; credit T+1
  cash        ETF cash = instalments − purchases (+ switch proceeds) and never negative
  holdings    units held = units bought − units sold, per fund / ETF
  value       latest valuation recomputed from holdings × latest price (+ pending orders, + ETF cash)
  xirr        recomputed by scripts/sim_xirr.js (JavaScript) and compared
  verified    share of MF NAVs confirmed against the official AMFI file (warning below 100%)
  dip         market-dip lump sums (sim_config dipRule): one reserve per dip agent's account on the reserve date in
              the published liquid fund / ETF; the frozen tracker closes (append-only, hashed at every scan); every
              signal recomputed independently (3-month high, fall, tier, second-tracker confirmation, crash-day and
              maximum-fall guards, one buy per new tier) and matched by exactly one decision per agent account;
              each decision (buy / skip, amount, reserve left) re-derived from the plan snapshot; the reserve
              redemption (units, NAV date, payout) and the switch-in funded with exactly its proceeds
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
DIP = CFG["dipRule"]


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


def expected_amounts(aid, risk, freq, start, today):
    """{trade date: amount} with the yearly step-up rules (stepUps) — re-derived here, independently of the engine:
    bonus = the year-end bonus added to the first instalment dated in each new year; hike = + pct % of the original
    amount every January (a fixed yearly step, not compounding), rounded."""
    su = CFG.get("stepUps") or {}
    base = amount_for(risk, freq)
    kind = next((k for k in ("bonus", "hike") if aid in (su.get(k) or {}).get("accounts", [])), None)
    sc, noms = CFG["schedule"], {start}
    if freq == "m":
        for k in range(1, 600):
            y, m = divmod(start.month - 1 + k, 12)
            noms.add(date(start.year + y, m + 1, sc["monthDay"]))
    elif freq == "w":
        noms |= {start + timedelta(days=7 * k) for k in range(1, 3000)}
    out, first = {}, {}
    for n in sorted(noms):
        first.setdefault(n.year, n)
    for n in sorted(noms):
        T = roll(n)
        if T > today or T in out:
            continue
        yrs, amt = n.year - start.year, base
        if kind == "hike" and yrs >= 1:
            amt = int(round(base * (1 + su["hike"]["pct"] / 100 * yrs) / su["hike"]["round"]) * su["hike"]["round"])
        elif kind == "bonus" and yrs >= 1 and first[n.year] == n:
            amt = base + su["bonus"]["amount"]
        out[T] = amt
    return out, kind


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

def dip_walk(cl, second):
    """Independent re-implementation of the dip signal (sim_config dipRule): returns {day: state} for signal days."""
    lb, ep, out, prev = DIP["lookback"], 0, {}, 0
    tiers = sorted(DIP["tiers"], key=lambda t: -t[0])
    amt_of = {t: max(DIP["min"], min(DIP["max"], a)) for t, a in tiers}
    for i in range(lb - 1, len(cl)):
        d, c = cl[i]
        win = cl[i - lb + 1:i + 1]
        hi = max(x[1] for x in win)
        hd = max(x[0] for x in win if x[1] == hi)
        fall = (1 - c / hi) * 100
        mv = (c / cl[i - 1][1] - 1) * 100
        w2 = [second[x] for x, _ in win if second.get(x)]
        f2 = (1 - second[d] / max(w2)) * 100 if second.get(d) and len(w2) >= 0.9 * lb else None
        raw = next((t for t, _ in tiers if fall >= t), 0)
        t = min(raw, prev)                                   # the level must hold for two closes
        prev = raw
        amt = amt_of.get(t, 0)
        if fall < DIP["resetPct"]:
            ep = 0
        if t > ep and f2 is not None and abs(f2 - fall) <= DIP["confirmPts"] and mv >= DIP["crashDayPct"] and fall <= DIP["maxFallPct"]:
            ep = t
            out[d] = {"close": c, "high": hi, "highDate": hd, "fall": fall, "fall2": f2, "day": mv, "tier": t, "amount": amt}
    return out


def audit_dips(A, store, evs, orders, done, funded, prices, today, start):
    accts = [f"{n}-{p}" for n in DIP["persons"] for p in ("MF", "ETF")]
    plans = store.get("plans", {})
    rsv = {e["acct"]: e for e in evs if e["k"] == "reserve" and not e.get("n")}
    refills = {}
    for e in evs:
        if e["k"] == "reserve" and e.get("n"):
            refills.setdefault(e["acct"], []).append(e)
    dips = [e for e in evs if e["k"] == "dip"]
    scans = [e for e in evs if e["k"] == "dipscan"]
    since = lambda p: p.get("since", p["ref"][:10])      # noqa: E731

    def dip_plan(d):
        ps = [p for p in plans.values() if p.get("dip")]
        if not ps:
            return {}
        ok = [p for p in ps if since(p) <= iso(d)]
        return max(ok, key=lambda p: (since(p), p["ref"])) if ok else min(ps, key=lambda p: (since(p), p["ref"]))
    backtest = bool(store.get("meta", {}).get("backtest"))
    rd = roll(start if backtest else max(start, day(DIP["reserveFrom"])))
    persons = {p["name"]: p for p in CFG["persons"]}
    A.check("dip", all(n in persons for n in DIP["persons"]), "a dip agent is not in the persons list")

    # reserves
    for aid, e in rsv.items():
        A.check("dip", aid in accts, f"{aid}: dip reserve for an account outside the dip rule")
    for aid in accts:
        e = rsv.get(aid)
        rv = (dip_plan(rd).get("dip") or {}).get(("mf" if aid.endswith("-MF") else "etf") + "Reserve") or {}
        A.check("dip", (e is not None) == (rd <= today and bool(rv)), f"{aid}: dip reserve missing / unexpected")
        if not e:
            continue
        A.check("dip", e["T"] == iso(rd) and abs(e["amount"] - DIP["reserve"]) < 1e-9, f"{aid}: reserve {e['amount']} on {e['T']} vs {DIP['reserve']} on {iso(rd)}")
        legs = [o for o in orders.values() if o.get("iid") == e["iid"]]
        A.check("dip", len(legs) == 1 and legs[0]["oid"] == f"{e['iid']}|liquid" and legs[0]["slot"] == "reserve" and legs[0]["side"] == "buy"
                and abs(legs[0]["amount"] - DIP["reserve"]) < 1e-9 and legs[0]["T"] == e["T"], f"{aid}: reserve purchase order")
        key = "code" if aid.endswith("-MF") else "sym"
        A.check("dip", legs and str(legs[0].get(key)) == str(rv.get(key)) == str(e.get(key)), f"{aid}: reserve parked in {legs and legs[0].get(key)} — the published reserve fund is {rv.get(key)}")

    # refills: once dip buys leave less than the minimum, the same amount (DIP reserve) is added on the first
    # trading day of the following month, into the same fund / ETF — never otherwise
    buys_of = {}
    for e in dips:
        if e["action"] == "buy":
            buys_of.setdefault(e["acct"], []).append(e)
    for aid in accts:
        if aid not in rsv:
            A.check("dip", not refills.get(aid), f"{aid}: refill without a first reserve")
            continue
        chain = [rsv[aid]] + sorted(refills.get(aid, []), key=lambda e: e["n"])
        A.check("dip", [e.get("n", 0) for e in chain] == list(range(len(chain))), f"{aid}: refills not numbered in order")
        bs = sorted(buys_of.get(aid, []), key=lambda e: (e["T"], e["seq"]))
        for k in range(len(chain) + 1):
            nxt = chain[k] if k < len(chain) else None
            prev = chain[k - 1] if k else None
            if prev is None:
                continue
            before = [b for b in bs if nxt is None or b["T"] < nxt["T"]]
            left = sum(e["amount"] for e in chain[:k]) - sum(b["amt"] for b in before)
            last = max((b for b in before if b["T"] >= prev["T"]), key=lambda b: (b["T"], b["seq"]), default=None)
            due = None
            if left < DIP["min"] and last is not None:
                t = day(last["T"])
                due = roll(date(t.year + (t.month == 12), t.month % 12 + 1, 1))
            if nxt is None:
                A.check("dip", due is None or due > today, f"{aid}: reserve used up — refill due {due} is missing")
                continue
            A.check("dip", due is not None and nxt["T"] == iso(due) and abs(nxt["amount"] - DIP["reserve"]) < 0.011
                    and str(nxt.get("code") or nxt.get("sym")) == str(rsv[aid].get("code") or rsv[aid].get("sym")),
                    f"{aid}: refill #{nxt['n']} ₹{nxt['amount']} on {nxt['T']} — the rule gives {due} ₹{DIP['reserve']}")
            o = orders.get(nxt["iid"] + "|liquid")
            A.check("dip", o is not None and o["slot"] == "reserve" and o["side"] == "buy" and abs(o["amount"] - nxt["amount"]) < 1e-9 and o["T"] == nxt["T"],
                    f"{aid}: refill #{nxt['n']} purchase order")

    # the frozen tracker closes
    ser = store.get("dipSeries", {})
    for sym, rows in ser.items():
        A.check("dip", all(rows[i][0] < rows[i + 1][0] for i in range(len(rows) - 1)) and all(r[1] > 0 for r in rows), f"dip series {sym}: dates not increasing / bad close")
        book = prices.get("etf", {}).get(sym) or {}
        bad = [r for r in rows if r[0] in book and abs(book[r[0]] - r[1]) > 1e-9]
        A.check("dip", not bad, f"dip series {sym}: closes differ from the recorded closes {bad[:2]}")
    prev = ""
    for e in scans:
        A.check("dip", e["through"] > prev, f"dip scan {e['through']} does not move forward")
        prev = e["through"]
        body = json.dumps({k: [r for r in v if r[0] <= e["through"]] for k, v in sorted(ser.items())}, sort_keys=True, separators=(",", ":"))
        A.check("dip", hashlib.sha256(body.encode()).hexdigest() == e["sha"], f"dip series changed after the scan through {e['through']}")
    through = prev
    A.check("dip", not dips or through, "dip decisions without a recorded scan")

    # every signal → exactly one decision per agent account; nothing else
    first = iso(biz_add(rd, CFG["mfRules"]["creditBusinessDays"]))
    expect = {}
    for seg, sg in DIP["segments"].items():
        for d, x in dip_walk([tuple(r) for r in ser.get(sg["trk"], [])], {r[0]: r[1] for r in ser.get(sg["trk2"], [])}).items():
            if first <= d <= through:
                expect[(d, seg)] = x
    got = {}
    for e in dips:
        got.setdefault(e["acct"], {})[(e["D"], e["seg"])] = e
        A.check("dip", e["acct"] in accts, f"{e['did']}: dip decision for an account outside the dip rule")
        A.check("dip", e["D"] > iso(start) and e["T"] > iso(start), f"{e['did']}: dip decision on or before the start date {iso(start)}")
    for aid in accts:
        if aid not in rsv:
            continue
        mine = got.get(aid, {})
        miss = [k for k in expect if k not in mine]
        extra = [k for k in mine if k not in expect]
        A.check("dip", not miss, f"{aid}: dip signals without a decision {miss[:3]}")
        A.check("dip", not extra, f"{aid}: dip decisions without a signal {extra[:3]}")
        # decisions in order (day, deepest fall first), the reserve drawn down exactly
        seq = sorted(mine.values(), key=lambda e: e["seq"])
        A.check("dip", [(e["D"], -e["fall"], e["seg"]) for e in seq] == sorted((e["D"], -e["fall"], e["seg"]) for e in seq), f"{aid}: dip decisions out of order")
        units, prod = None, "mf" if aid.endswith("-MF") else "etf"
        used = 0.0
        ro = orders.get(f"{aid}|reserve|liquid")
        rdone = done.get(f"{aid}|reserve|liquid")
        rlist = [rsv[aid]] + refills.get(aid, [])
        units_of = lambda T: sum(done[r["iid"] + "|liquid"]["units"] for r in rlist if r["iid"] + "|liquid" in done and r["T"] <= T)   # noqa: E731
        sold = 0.0
        pid = CFG["horizon"] + persons[aid.rsplit("-", 1)[0]]["risk"]
        for e in seq:
            x = expect.get((e["D"], e["seg"]))
            if not x:
                continue
            T = roll(day(e["D"]) + timedelta(days=1))
            A.check("dip", e["T"] == iso(T) and e["trk"] == DIP["segments"][e["seg"]]["trk"], f"{e['did']}: action day {e['T']} vs {iso(T)}")
            A.check("dip", abs(e["close"] - x["close"]) < 1e-9 and abs(e["high"] - x["high"]) < 1e-9 and e["highDate"] == x["highDate"]
                    and abs(e["fall"] - x["fall"]) < 1e-3 and e["tier"] == x["tier"] and e["amount"] == x["amount"], f"{e['did']}: signal figures differ from the recomputed ones")
            A.check("dip", rdone is not None and day(rdone["credit"]) <= T, f"{e['did']}: decided before the reserve was credited")
            plan = dip_plan(T)
            A.check("dip", e.get("ref") == plan.get("ref"), f"{e['did']}: decided on plan {e.get('ref')}, the plan in force was {plan.get('ref')}")
            ent = ((plan.get("dip") or {}).get(prod) or {}).get(pid, {}).get(e["seg"])
            paid = sum(r["amount"] for r in rlist if (done.get(r["iid"] + "|liquid") or {}).get("credit", "9999") <= iso(T))
            left = paid - used
            amt = min(x["amount"], left)
            act = "skip" if not ent or not ent["fundOk"] or amt < DIP["min"] else "buy"
            A.check("dip", e["action"] == act and abs(e["amt"] - (amt if act == "buy" else 0)) < 1e-9, f"{e['did']}: {e['action']} ₹{e['amt']} — the rule gives {act} ₹{amt if act == 'buy' else 0}")
            if act == "buy":
                left -= amt
                used += amt
            A.check("dip", abs(e["left"] - left) < 1e-9, f"{e['did']}: reserve left {e['left']} vs {left}")
            legs = {o["oid"]: o for o in orders.values() if o.get("iid") == e["did"]}
            if e["action"] != "buy":
                A.check("dip", not legs, f"{e['did']}: orders placed on a skipped signal")
                continue
            fld = "code" if prod == "mf" else "sym"
            out, inn = legs.get(e["did"] + "|out"), legs.get(e["did"] + "|in")
            A.check("dip", len(legs) == 2 and out and inn, f"{e['did']}: needs one reserve sale and one buy")
            if not (out and inn):
                continue
            A.check("dip", out["side"] == "sell" and out.get("level") == "dip" and abs(out["amountOut"] - e["amt"]) < 1e-9 and out["T"] == e["T"]
                    and ro and str(out.get(fld)) == str(ro.get(fld)), f"{e['did']}: reserve sale order")
            A.check("dip", inn["side"] == "buy" and inn.get("fromOid") == out["oid"] and inn.get("amount") is None and ent is not None
                    and str(inn.get(fld)) == str(ent[fld]) and inn["slot"] == ent["slot"] and inn["T"] == iso(biz_add(T, 1)), f"{e['did']}: dip buy order")
            d = done.get(out["oid"])
            if not d:
                continue
            px = d["price"]
            if prod == "mf":
                nd = biz_add(T, 1) - timedelta(days=1)
                A.check("dip", day(d["navDate"]) <= nd and (nd - day(d["navDate"])).days <= 5, f"{out['oid']}: liquid redemption NAV of {d['navDate']} (rule: {iso(nd)})")
                rec = (prices.get("mf", {}).get(str(out["code"])) or {}).get(d["navDate"])
                A.check("dip", rec is not None and abs(rec - px) < 1e-9, f"{out['oid']}: NAV {px} not the recorded NAV of {d['navDate']}")
                units = round(units_of(out["T"]) - sold, 6)
                want = min(units, math.ceil(out["amountOut"] / px * 1000 - 1e-6) / 1000)
                A.check("dip", d["payout"] == iso(biz_add(T, 1)), f"{out['oid']}: liquid payout {d['payout']} (T+1)")
            else:
                units = round(units_of(out["T"]) - sold, 6)
                want = min(units, float(math.ceil(out["amountOut"] / px - 1e-9)))
            A.check("dip", abs(d["units"] - round(want, 6)) < 1e-6, f"{out['oid']}: redeemed {d['units']} units vs {want}")
            sold = round(sold + d["units"], 6)
            f = funded.get(inn["oid"])
            A.check("dip", f is None or abs(f - d["net"]) < 0.01, f"{out['oid']}: dip buy funded {f} vs the sale proceeds {d['net']}")
        # the reserve's units are never sold by reviews / harvesting
        if ro:
            k = str(ro.get("code") or ro.get("sym"))
            held = sum(x["units"] for x in evs if x["k"] in ("allot", "fill") and orders.get(x["oid"], {}).get("acct") == aid
                       and str(orders[x["oid"]].get("code") or orders[x["oid"]].get("sym")) == k) - \
                sum(x["units"] for x in evs if x["k"] == "redeem" and orders.get(x["oid"], {}).get("acct") == aid
                    and str(orders[x["oid"]].get("code") or orders[x["oid"]].get("sym")) == k)
            rest = round(units_of("9999") - sold, 6)
            A.check("dip", held >= rest - 1e-6, f"{aid}: holds {round(held, 6)} units of the reserve fund but {rest} still belong to the reserve")


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
        elif e["k"] == "reserve":
            n = e.get("n", 0)
            A.check("chain", ("R", e["acct"], n) not in seen_i and e["iid"] == f"{e['acct']}|reserve" + (str(n) if n else ""), f"duplicate or mislabelled dip reserve {e['acct']} #{n}")
            seen_i.add(("R", e["acct"], n))
        elif e["k"] == "dip":
            A.check("chain", ("D", e["did"]) not in seen_i and e["did"] == f"{e['acct']}|dip|{e['D']}|{e['seg']}", f"duplicate or mislabelled dip decision {e['did']}")
            seen_i.add(("D", e["did"]))
    # completions of unknown orders are already reported above; keep them out of the remaining checks so the audit
    # still finishes and records every problem
    evs = [e for e in evs if not (e["k"] in ("allot", "fill", "redeem", "fund") and e["oid"] not in oset)]
    A.check("chain", view.get("head") == (evs[-1]["h"] if evs else None), "view built from a different ledger")

    orders = {e["oid"]: e for e in evs if e["k"] == "order"}
    done = {e["oid"]: e for e in evs if e["k"] in ("allot", "fill", "redeem")}
    funded = {e["oid"]: e["amount"] for e in evs if e["k"] == "fund"}
    inst = [e for e in evs if e["k"] == "instalment"]
    money = [e for e in evs if e["k"] in ("instalment", "reserve")]      # every rupee paid into an account
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
            want, kind = expected_amounts(aid, p["risk"], p["freq"], start, today)
            if kind:
                A.check("schedule", p["name"] not in DIP["persons"], f"{aid}: a step-up account must not hold a dip reserve")
            for e in inst:
                if e["acct"] == aid:
                    exp_amt = want.get(day(e["T"]), amount_for(p["risk"], p["freq"]))
                    A.check("schedule", e["amount"] == exp_amt, f"{aid} {e['T']}: amount {e['amount']} vs {exp_amt} by the schedule rules")
                    A.check("schedule", (e.get("bonus") or 0) + (e.get("hike") or 0) == e["amount"] - amount_for(p["risk"], p["freq"]),
                            f"{aid} {e['T']}: bonus / step-up parts do not add up")
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
                rec_days = sorted(x for x in (prices.get("mf", {}).get(str(o["code"])) or {}) if x > iso(T))
                A.check("mf", nd == T or (nd > T and (nd - T).days <= 7 and (prices.get("mf", {}).get(str(o["code"])) or {}).get(iso(T)) is None
                                          and len(rec_days) >= 2 and rec_days[0] == iso(nd)),
                        f"{oid}: NAV date {nd} for trade date {T} (the next NAV day is used only once two later NAVs are published)")
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
        seq = sorted([e for e in evs if (e["k"] in ("instalment", "reserve") and e["acct"] == aid) or
                      (e["k"] in ("fill", "redeem") and orders[e["oid"]]["acct"] == aid)], key=lambda e: e["seq"])
        for e in seq:
            if e["k"] in ("instalment", "reserve"):
                cash += e["amount"]
                continue
            o = orders[e["oid"]]
            if e["k"] == "redeem":
                if not o.get("withdraw"):
                    cash += e["net"]
                continue
            amt = o["amount"] if o.get("amount") is not None else funded.get(o["oid"])
            ck = ("dip:" if "|dip|" in o.get("iid", "") else "rv:" if "|review|" in o.get("iid", "") else "hv:" if "|harvest|" in o.get("iid", "") else "") + str(o["slot"])
            budget = r2(amt + carry.get(ck, 0.0))
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
            carry[ck] = e["carry"]
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
    # tax at source: residents pay capital-gains tax through their return (no TDS); NRIs have TDS deducted on every
    # sale — gains and losses of the sale netted within each rate bucket, plus cess, no exemption at source
    T_ = CFG["tax"]
    for oid, d in redeems.items():
        o = orders.get(oid) or {}
        nri = res.get(o.get("acct", "").rsplit("-", 1)[0]) == "nri"
        exp = 0.0
        if nri:
            bk = {}
            for g in d["gains"]:
                rate = T_["ltcgEquity"] if g["term"] == "LT" else T_["stcgEquity"] if g["term"] == "ST" else T_["debtSlab"]
                bk[rate] = bk.get(rate, 0.0) + g["gain"]
            exp = sum(max(0.0, v) * rate * (1 + T_["cess"]) for rate, v in bk.items())
        A.check("rules", abs(d["tds"] - exp) < 0.02, f"{oid}: TDS {d['tds']} vs {r2(exp)} ({'NRI' if nri else 'resident'})")
        A.check("rules", abs(d["net"] - r2(d["gross"] - d["charges"]["total"] - d["tds"])) < 0.02, f"{oid}: net proceeds")
        if nri and o.get("level") == "harvest":
            A.check("rules", not any(g["gain"] > 0 for g in d["gains"]) or CFG["taxHarvest"].get("nriGainHarvest"),
                    f"{oid}: gain harvesting in an NRI account (TDS at source)")
    for (person, fy), g in harvested.items():
        A.check("rules", g <= CFG["tax"]["ltcgExempt"] + 1, f"{person} FY{fy}: harvested equity gains {g:.0f} exceed the yearly exemption")

    audit_dips(A, store, evs, orders, done, funded, prices, today, start)

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
            inv = sum(e["amount"] for e in money if e["acct"] == aid)
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
    for x in money:
        acc_inst.setdefault(x["acct"], []).append(x)
    in_from = {o["fromOid"]: o["T"] for o in orders.values() if o.get("fromOid")}
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
                for l in sorted(lots.get(key, []), key=lambda l: (l[3], l[4])):     # FIFO by purchase date
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
            lots.setdefault(key, []).append([x["credit"], x["units"], cost, o["T"], o["oid"]])
            if not mf:
                cash -= x["gross"] + x["charges"]["total"]
        if mf:
            for o in acc_orders.get(aid, []):
                if o["side"] == "buy" and o["T"] <= ds and o["oid"] not in done:
                    pend += o["amount"] if o.get("amount") is not None else funded.get(o["oid"], 0.0)
                # sale proceeds on their way to a switch-in order dated after this day
                if o["side"] == "sell" and o["T"] <= ds and o["oid"] in done and not o.get("withdraw") and in_from.get(o["oid"], "") > ds:
                    pend += done[o["oid"]]["net"]
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
        payload = [{"id": a["id"], "flows": [[e["T"], -e["amount"]] for e in money if e["acct"] == a["id"]] +
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
