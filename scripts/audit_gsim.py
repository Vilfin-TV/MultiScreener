#!/usr/bin/env python3
"""Independent audit of the Global Simulator Buy ledger (does not import gsim_engine.py).

Recomputes from the event log, the recorded official closes and gsim_config.json / sim_config.json:
  chain     hash chain, sequence, unique ids, one completion per order, completions only for recorded orders
  schedule  every account has exactly the instalments its schedule requires up to the valuation date, right amounts
  plan      each instalment uses the latest plan recorded before its date; orders = plan rows, share = amount × weight
  cash      each order's cash = its share + the slot's cash left by earlier executions and dividends (ledger order)
  trades    trade date = first recorded session on/after the order day with a close; price = recorded close (and the
            published daily file, warning); units = most whole shares the cash buys after commission; commission
            formula; credit date = next US business day; nothing executed after the valuation date
  dividends entitlement = shares traded before the ex-date; gross, withholding by residency, net
  value     every daily record of the view: credited units × close + uncredited at cost + uninvested cash; invested;
            day change; the benchmark's value (same cash into SPY)
Any error → exit 1 and nothing is published. Output: --out audit.json.
"""
import argparse, hashlib, json, sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "gsim_config.json").read_text())
import os
if os.environ.get("GSIM_START"):
    CFG["start"] = os.environ["GSIM_START"]
PERSONS = json.loads((HERE / "sim_config.json").read_text())["persons"]


def iso(s):
    return date.fromisoformat(str(s)[:10])


def holidays(y):
    """NYSE full-day holidays (independent formulation: weekday arithmetic over the month's dates)."""
    def nth(m, wd, n):
        days = [date(y, m, d) for d in range(1, 29) if date(y, m, d).weekday() == wd]
        return days[n - 1]

    def last_mon_may():
        return max(date(y, 5, d) for d in range(25, 32) if date(y, 5, d).weekday() == 0)

    def observed(d):
        return {5: d - timedelta(days=1), 6: d + timedelta(days=1)}.get(d.weekday(), d)
    # Easter (Meeus/Jones/Butcher)
    a = y % 19; b, c = divmod(y, 100); d_, e = divmod(b, 4); f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d_ - g + 15) % 30; i, k = divmod(c, 4); l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451; month = (h + l_ - 7 * m + 114) // 31; day = ((h + l_ - 7 * m + 114) % 31) + 1
    out = {nth(1, 0, 3), nth(2, 0, 3), date(y, month, day) - timedelta(days=2), last_mon_may(), observed(date(y, 6, 19)),
           observed(date(y, 7, 4)), nth(9, 0, 1), nth(11, 3, 4), observed(date(y, 12, 25))}
    ny = date(y, 1, 1)
    if ny.weekday() == 6:
        out.add(ny + timedelta(days=1))
    elif ny.weekday() < 5:
        out.add(ny)
    return out


def next_bday(d):
    d += timedelta(days=1)
    while d.weekday() >= 5 or d in holidays(d.year):
        d += timedelta(days=1)
    return d


def commission(n, px):
    f = CFG["fees"]
    return 0.0 if n <= 0 else round(min(max(f["min"], f["perShare"] * n), f["maxPct"] / 100 * n * px), 2)


def expected_schedule(freq, start, upto):
    s = CFG["schedule"]
    out = []
    d = start
    while d <= upto:
        if d == start:
            out.append(d)
        elif freq == "m" and d.day == s["monthDay"]:
            out.append(d)
        elif freq == "w" and d.weekday() == s["weekday"]:
            out.append(d)
        elif freq == "q" and d.month in s["quarterMonths"] and d.day == s["anchorDay"]:
            out.append(d)
        elif freq == "y" and d.month == s["anchorMonth"] and d.day == s["anchorDay"]:
            out.append(d)
        d += timedelta(days=1)
        if freq == "l":
            break
    return out


class A:
    def __init__(self):
        self.err, self.warn, self.n = [], [], {}

    def ok(self, area, cond, msg, warn=False):
        self.n[area] = self.n.get(area, 0) + 1
        if not cond:
            (self.warn if warn else self.err).append(f"[{area}] {msg}")
        return cond


def audit(store, view, daily):
    au = A()
    evs = store.get("events", [])
    px = store.get("px", {})
    start = iso(CFG["start"])
    # ---- chain
    prev = None
    ids, done, orders = set(), set(), {}
    for i, e in enumerate(evs):
        body = {k: v for k, v in e.items() if k not in ("h", "prev")}
        h = hashlib.sha256((prev or "").encode() + json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        au.ok("chain", e.get("seq") == i and e.get("prev") == prev and e.get("h") == h, f"entry {i} breaks the hash chain")
        prev = e.get("h")
        if e["k"] in ("fill", "carry"):
            au.ok("chain", e["id"] in orders, f"completion {e['id']} for an order not recorded before it")
            au.ok("chain", e["id"] not in done, f"second completion of {e['id']}")
            done.add(e["id"])
        else:
            au.ok("chain", e["id"] not in ids, f"duplicate id {e['id']}")
            ids.add(e["id"])
            if e["k"] == "order":
                orders[e["id"]] = e
    if au.err:
        return au
    # ---- accounts & schedule
    today = iso(view["today"])
    accts = {}
    for p in PERSONS:
        r = CFG["riskMap"][p["risk"]]
        m = CFG["monthlyUsd"][p["risk"]]
        amt = {"m": m, "w": round(m * 12 / 52), "q": 3 * m, "y": 12 * m, "l": 12 * m}[p["freq"]]
        accts[p["name"] + "-GL"] = {"freq": p["freq"], "amt": amt, "pid": CFG["horizon"] + r, "res": p["res"]}
    insts = [e for e in evs if e["k"] == "inst"]
    for aid, a in accts.items():
        got = sorted(iso(e["d"]) for e in insts if e["a"] == aid)
        want = expected_schedule(a["freq"], start, today)
        au.ok("schedule", got == want[:len(got)], f"{aid}: instalment dates {got[:3]}… do not follow the schedule")
        missing = want[len(got):]
        if missing:
            au.ok("schedule", True, "")
            au.warn.append(f"[schedule] {aid}: {len(missing)} instalment(s) from {missing[0]} not yet placed (waiting for closes)")
        for e in insts:
            if e["a"] == aid:
                au.ok("schedule", e["amt"] == a["amt"], f"{e['id']}: amount {e['amt']} ≠ {a['amt']}")
    for e in insts:
        au.ok("schedule", e["a"] in accts, f"{e['id']}: unknown account")
    # ---- plan, orders, cash, trades, dividends (ledger order)
    plans = [e for e in evs if e["k"] == "plan"]
    carry = {}
    res = {aid: a["res"] for aid, a in accts.items()}
    lots = {}
    seen_inst_orders = {}
    for e in evs:
        k = e["k"]
        if k == "plan":
            au.ok("plan", hashlib.sha256(json.dumps(e["plans"], sort_keys=True).encode()).hexdigest() == e["hash"], f"{e['id']}: plan hash")
            for pid, rows in e["plans"].items():
                au.ok("plan", abs(sum(r[2] for r in rows) - 100) < 0.01, f"{e['id']} {pid}: weights add to {sum(r[2] for r in rows)}")
        elif k == "inst":
            d = iso(e["d"])
            before = [p for p in plans if p["seq"] < e["seq"] and iso(p["asOf"]) < d]
            known = [p for p in plans if p["seq"] < e["seq"]]
            want = (before[-1] if before else known[0])["id"] if known else None
            au.ok("plan", e["plan"] == want, f"{e['id']}: plan {e['plan']} ≠ {want}")
            pe = next((p for p in plans if p["id"] == e["plan"]), None)
            seen_inst_orders[e["id"]] = (pe["plans"][accts[e["a"]]["pid"]] if pe and e["a"] in accts else [], e)
        elif k == "order":
            iid = e["id"].rsplit("|", 1)[0]
            rows, ie = seen_inst_orders.get(iid, ([], None))
            row = next((r for r in rows if r[0] == e["slot"]), None)
            au.ok("plan", row is not None and row[1] == e["t"], f"{e['id']}: slot / ETF not in the plan")
            if row and ie:
                au.ok("plan", abs(e["share"] - round(ie["amt"] * row[2] / 100, 2)) < 0.006, f"{e['id']}: share {e['share']}")
            key = (e["a"], e["slot"])
            au.ok("cash", abs(e["cash"] - round(e["share"] + carry.get(key, 0), 2)) < 0.006,
                  f"{e['id']}: cash {e['cash']} ≠ share {e['share']} + left {carry.get(key, 0):.2f}")
            carry[key] = 0.0
        elif k in ("fill", "carry"):
            o = orders[e["id"]]
            ses = sorted(x for x in px.get(o["t"], {}) if x >= o["d"])
            au.ok("trades", bool(ses) and e["T"] == ses[0], f"{e['id']}: trade date {e['T']} is not the first session on/after {o['d']}")
            au.ok("trades", iso(e["T"]) <= today, f"{e['id']}: executed after the valuation date")
            cl = px.get(o["t"], {}).get(e["T"])
            au.ok("trades", cl is not None and abs(e["px"] - cl) < 1e-9, f"{e['id']}: price {e['px']} ≠ recorded close {cl}")
            dc = daily_close(daily, o["t"], e["T"])
            if dc is not None:
                au.ok("trades", abs(dc - e["px"]) < 1e-6, f"{e['id']}: price {e['px']} ≠ published close {dc}", warn=True)
            n = e["n"]
            au.ok("trades", n * e["px"] + commission(n, e["px"]) <= o["cash"] + 1e-9, f"{e['id']}: {n} shares cost more than the cash")
            step, mino = CFG["fractional"]["step"], CFG["fractional"]["minOrder"]
            au.ok("trades", abs(n / step - round(n / step)) < 1e-6, f"{e['id']}: {n} shares not in steps of {step}")
            m1 = round(n + step, 4)
            au.ok("trades", o["cash"] < mino or m1 * e["px"] + commission(m1, e["px"]) > o["cash"] + 1e-9,
                  f"{e['id']}: {step} more share was affordable")
            au.ok("trades", n == 0 or o["cash"] >= mino, f"{e['id']}: bought below the minimum order value")
            if k == "fill":
                au.ok("trades", abs(e["fee"] - commission(n, e["px"])) < 0.006, f"{e['id']}: commission {e['fee']}")
                au.ok("trades", abs(e["cost"] - round(n * e["px"] + e["fee"], 2)) < 0.006, f"{e['id']}: cost")
                au.ok("trades", e["cr"] == str(next_bday(iso(e["T"]))), f"{e['id']}: credit date {e['cr']}")
                au.ok("trades", e["rule"] == CFG["trade"]["rule"], f"{e['id']}: trade rule")
                lots.setdefault((e["a"], e["t"]), []).append([e["T"], n])
            else:
                au.ok("trades", n == 0 and (o["cash"] < mino or e["px"] * step + commission(step, e["px"]) > o["cash"]), f"{e['id']}: carried although a buy was possible")
            au.ok("cash", abs(e["left"] - round(o["cash"] - (e.get("cost") or 0), 2)) < 0.006, f"{e['id']}: cash left {e['left']}")
            carry[(e["a"], e["slot"])] = round(carry.get((e["a"], e["slot"]), 0) + e["left"], 2)
        elif k == "div":
            units = sum(n for T, n in lots.get((e["a"], e["t"]), []) if T < e["ex"])
            au.ok("dividends", abs(units - e["units"]) < 1e-6, f"{e['id']}: entitled units {e['units']} ≠ {units}")
            dps = store.get("div", {}).get(e["t"], {}).get(e["ex"])
            au.ok("dividends", dps is not None and abs(dps - e["dps"]) < 1e-9, f"{e['id']}: dividend per share")
            rate = CFG["withholding"]["nri" if res.get(e["a"]) == "nri" else "resident"]
            au.ok("dividends", e["rate"] == rate and abs(e["gross"] - round(units * e["dps"], 2)) < 0.006
                  and abs(e["wht"] - round(e["gross"] * rate / 100, 2)) < 0.006 and abs(e["net"] - round(e["gross"] - e["wht"], 2)) < 0.006,
                  f"{e['id']}: gross / withholding / net")
            carry[(e["a"], e["slot"])] = round(carry.get((e["a"], e["slot"]), 0) + e["net"], 2)
        elif k == "split":
            for l_ in lots.get((e["a"], e["t"]), []):
                if l_[0] < e["d"]:
                    l_[1] = round(l_[1] * e["ratio"], 6)
    # ---- valuation of every daily record
    for va in view.get("accounts", []):
        aid = va["id"]
        aev = [e for e in evs if e.get("a") == aid]
        for rec in va["days"]:
            d = rec["d"]
            inv = sum(e["amt"] for e in aev if e["k"] == "inst" and e["d"] <= d)
            val = 0.0
            held = {}
            for e in aev:
                if e["k"] == "order" and e["d"] <= d:
                    val += e["share"]
                elif e["k"] == "fill" and e["T"] <= d:
                    val -= e["cost"]
                    held.setdefault(e["t"], []).append([e["T"], e["n"], e["cost"], e["cr"]])
                elif e["k"] == "div" and e["ex"] <= d:
                    val += e["net"]
                elif e["k"] == "split" and e["d"] <= d:
                    for l_ in held.get(e["t"], []):
                        if l_[0] < e["d"]:
                            l_[1] = round(l_[1] * e["ratio"], 6)
            for t, ls in held.items():
                m = px.get(t, {})
                pk = max((x for x in m if x <= d), default=None)
                for T, n, cost, cr in ls:
                    val += n * m[pk] if cr <= d and pk else cost
            au.ok("value", abs(inv - rec["inv"]) < 0.006, f"{aid} {d}: invested {rec['inv']} ≠ {inv}")
            au.ok("value", abs(val - rec["val"]) < 0.02, f"{aid} {d}: value {rec['val']} ≠ {val:.2f}")
        for i in range(1, len(va["days"])):
            p, q = va["days"][i - 1], va["days"][i]
            au.ok("value", abs(q["chg"] - round(q["val"] - p["val"] - (q["inv"] - p["inv"]), 2)) < 0.02, f"{aid} {q['d']}: day change")
    # ---- benchmark (same cash into SPY, fractional)
    b = CFG["bench"]
    bpx, bdiv = px.get(b, {}), store.get("div", {}).get(b, {})
    for va in view.get("accounts", []):
        ins = [e for e in evs if e["k"] == "inst" and e["a"] == va["id"]]
        rate = CFG["withholding"]["nri" if va["res"] == "nri" else "resident"]
        for rec in va["days"][-3:]:
            d = rec["d"]
            lots_b = []
            for e in ins:
                T = min((x for x in bpx if x >= e["d"]), default=None)
                if T:
                    lots_b.append([T, e["amt"] / bpx[T], e["amt"], str(next_bday(iso(T)))])
            for ex in sorted(bdiv):
                h = sum(l_[1] for l_ in lots_b if l_[0] < ex)
                if h > 0 and ex in bpx:
                    lots_b.append([ex, h * bdiv[ex] * (1 - rate / 100) / bpx[ex], 0.0, ex])
            pk = max((x for x in bpx if x <= d), default=None)
            bv = sum((n * bpx[pk] if cr <= d else c) for T, n, c, cr in lots_b if T <= d)
            au.ok("bench", abs(bv - rec["bval"]) < 0.02, f"{va['id']} {d}: benchmark value {rec['bval']} ≠ {bv:.2f}")
    return au


def daily_close(daily, t, d):
    if not daily:
        return None
    try:
        i = daily["dates"].index(d)
    except ValueError:
        return None
    c = daily.get("c", {}).get(t)
    return c[i] if c else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--view", required=True)
    ap.add_argument("--daily", default=str(HERE.parent / "data" / "global_etf_daily.json"))
    ap.add_argument("--out")
    a = ap.parse_args()
    store = json.loads(Path(a.store).read_text())
    view = json.loads(Path(a.view).read_text())
    daily = json.loads(Path(a.daily).read_text()) if Path(a.daily).exists() else None
    au = audit(store, view, daily)
    out = {"checks": sum(au.n.values()), "areas": au.n, "nErrors": len(au.err), "errors": au.err[:200], "warnings": au.warn[:200]}
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"global simulator audit: {out['checks']} checks · {len(au.err)} errors · {len(au.warn)} warnings")
    for m in au.err[:30]:
        print("  ERROR", m)
    for m in au.warn[:10]:
        print("  warn ", m)
    return 1 if au.err else 0


if __name__ == "__main__":
    sys.exit(main())
