#!/usr/bin/env python3
"""Global Simulator Buy — simulated US-listed ETF accounts of the 20 VilfinTV agents.

Each agent (persons in sim_config.json, rules in gsim_config.json) buys the Portfolio Simulator — Global ETF 10+ year
model portfolio (plan h15<risk> published in data/global_etf.json → "plans") on a fixed schedule from the start date:

  * order day D: the instalment is split by the plan's weights (the latest plan published before D); each slot's
    share is added to that slot's cash left over from earlier buys;
  * market-on-close: executes at the official closing price (4:00 pm ET) of the first session on or after D on which
    the ETF has a close (data/global_etf_daily.json); fractional shares in steps of 0.0001, as many as the cash buys
    after commission ($0.0035 a share, min $0.35, max 1% of the trade); cents left over (or an order under $1) wait in
    the slot for its next buy;
  * shares are credited the next US business day (T+1) and count at cost until then;
  * cash dividends: shares bought before the ex-date earn the dividend on the ex-date, less US withholding (India
    residents 25%, US-based agents 0%); the net cash joins the slot's cash for its next buy. Splits multiply units;
  * never sells: when the model changes a slot's ETF, new money goes to the new choice and earlier shares are kept.

Benchmark: the same cash on the same days into the S&P 500 (SPY) as fractional shares, no costs, dividends net of the
same withholding reinvested on the ex-date.

Append-only event log with a SHA-256 hash chain; every closing price used is kept in the store. The store is private
(R2) — only the scoreboard and per-account summaries are published. Audited independently by audit_gsim.py.
"""
from __future__ import annotations

import argparse, calendar, hashlib, json, math, re, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from global_plans import SLOTS, RISK_NAMES, all_plans  # noqa: E402

CFG = json.loads((Path(__file__).resolve().parent / "gsim_config.json").read_text())
if __import__("os").environ.get("GSIM_START"):           # rehearsals / tests only
    CFG["start"] = __import__("os").environ["GSIM_START"]
PERSONS = json.loads((Path(__file__).resolve().parent / "sim_config.json").read_text())["persons"]
FREQ = {"m": "Monthly", "w": "Weekly", "q": "Quarterly", "y": "Yearly", "l": "One-time"}
SLOT_OF = {t: k for k, s in SLOTS.items() for t in s["cands"]}
MARKET_LABELS = [["SPY", "S&P 500"], ["QQQ", "Nasdaq-100"], ["IWM", "Russell 2000"], ["EFA", "Developed ex-US"],
                 ["EEM", "Emerging markets"], ["AGG", "US bonds"], ["GLD", "Gold"]]
ALLOC_OF = {"eq": "Equity", "bond": "Debt", "gold": "Gold", "cash": "Debt"}


class ChainError(Exception):
    pass


class DuplicateEvent(Exception):
    pass


def D(s):
    return date.fromisoformat(str(s)[:10])


def r2(x):
    return None if x is None else round(x + 0.0, 2)


def r6(x):
    return round(x + 0.0, 6)


# ---------------------------------------------------------------- US market calendar (NYSE full-day holidays)
def _nth(y, m, wd, n):
    d = date(y, m, 1)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last(y, m, wd):
    d = date(y, m, calendar.monthrange(y, m)[1])
    return d - timedelta(days=(d.weekday() - wd) % 7)


def _easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mo = (h + l_ - 7 * m + 114) // 31
    return date(y, mo, (h + l_ - 7 * m + 114) % 31 + 1)


def _obs(d):
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def us_holidays(y):
    nyd = date(y, 1, 1)
    h = {nyd + timedelta(days=1)} if nyd.weekday() == 6 else ({nyd} if nyd.weekday() < 5 else set())
    h |= {_nth(y, 1, 0, 3), _nth(y, 2, 0, 3), _easter(y) - timedelta(days=2), _last(y, 5, 0),
          _obs(date(y, 6, 19)), _obs(date(y, 7, 4)), _nth(y, 9, 0, 1), _nth(y, 11, 3, 4), _obs(date(y, 12, 25))}
    return h


def is_us_session(d):
    return d.weekday() < 5 and d not in us_holidays(d.year)


def add_business(d, n):
    while n > 0:
        d += timedelta(days=1)
        if is_us_session(d):
            n -= 1
    return d


# ---------------------------------------------------------------- schedule
def accounts():
    out = []
    for p in PERSONS:
        risk = CFG["riskMap"][p["risk"]]
        m = CFG["monthlyUsd"][p["risk"]]
        f = p["freq"]
        amt = {"m": m, "w": round(m * 12 / 52), "q": m * 3, "y": m * 12, "l": m * 12}[f]
        out.append({"id": p["name"] + "-GL", "name": p["name"], "risk": risk, "personRisk": p["risk"], "freq": f, "amt": amt,
                    "res": p["res"], "role": p.get("role"), "desk": p.get("desk"), "team": p.get("team"),
                    "pid": CFG["horizon"] + risk, "step": step_kind(p["name"] + "-GL")})
    return out


def step_kind(aid):
    su = CFG.get("stepUps") or {}
    return next((k for k in ("bonus", "hike") if aid in (su.get(k) or {}).get("accounts", [])), None)


def contribution(a, d, start):
    """Regular buy on order date d with the yearly step-up rules (gsim_config stepUps): bonus = the year-end bonus
    added in full to the first buy dated in each new year; hike = + pct % of the original buy every January (fixed step, not compounding), rounded."""
    su, base, k = CFG.get("stepUps") or {}, a["amt"], d.year - start.year
    if a.get("step") == "hike" and k >= 1:
        h = su["hike"]
        amt = round(base * (1 + h["pct"] / 100 * k) / h["round"]) * h["round"]
        return amt, {"base": base, "hike": amt - base}
    if a.get("step") == "bonus" and k >= 1:
        first = next(x for x in due_dates(a["freq"], start, d) if x.year == d.year)
        if first == d:
            return base + su["bonus"]["amount"], {"base": base, "bonus": su["bonus"]["amount"]}
    return base, {}


def due_dates(freq, start, upto):
    """Order dates of an account from start to upto (inclusive): first buy on the start date for everyone."""
    s = CFG["schedule"]
    out = [start] if start <= upto else []
    if freq == "l":
        return out
    d = start + timedelta(days=1)
    while d <= upto:
        if (freq == "m" and d.day == s["monthDay"]) or (freq == "w" and d.weekday() == s["weekday"]) \
           or (freq == "q" and d.month in s["quarterMonths"] and d.day == s["anchorDay"]) \
           or (freq == "y" and d.month == s["anchorMonth"] and d.day == s["anchorDay"]):
            out.append(d)
        d += timedelta(days=1)
    return out


def next_due(freq, after):
    if freq == "l":
        return None
    nx = due_dates(freq, after, after + timedelta(days=400))
    return nx[1] if len(nx) > 1 else None


def fee_for(n, px):
    f = CFG["fees"]
    if n <= 0:
        return 0.0
    return round(min(max(f["min"], f["perShare"] * n), f["maxPct"] / 100 * n * px), 2)


def max_units(cash, px):
    """Most shares, in steps of 0.0001 (fractional shares), whose cost plus commission fits the cash; orders under the
    minimum order value wait for the slot's next buy."""
    step = CFG["fractional"]["step"]
    if not px or px <= 0 or cash < CFG["fractional"]["minOrder"]:
        return 0
    k = int(cash / px / step)
    while k > 0 and k * step * px + fee_for(round(k * step, 4), px) > cash + 1e-9:
        k = int(min(k - 1, (cash - fee_for(round(k * step, 4), px)) / px / step))
    while (k + 1) * step * px + fee_for(round((k + 1) * step, 4), px) <= cash + 1e-9:
        k += 1
    return round(k * step, 4) if k > 0 else 0


# ---------------------------------------------------------------- store
def ev_hash(e, prev):
    body = {k: v for k, v in e.items() if k not in ("h", "prev")}
    return hashlib.sha256((prev or "").encode() + json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_chain(events):
    prev = None
    for i, e in enumerate(events):
        if e.get("seq") != i or e.get("prev") != prev or ev_hash(e, prev) != e.get("h"):
            raise ChainError(f"hash chain broken at entry {i}")
        prev = e["h"]


class Engine:
    def __init__(self, store, today):
        self.s = store
        self.today = today
        self.events = store.setdefault("events", [])
        self.px = store.setdefault("px", {})          # ticker → {date: official close} (first seen wins)
        self.div = store.setdefault("div", {})        # ticker → {ex-date: cash dividend per share}
        self.split = store.setdefault("split", {})    # ticker → {date: ratio}
        self.dates = set(store.setdefault("dates", []))
        self.ids = {e["id"] for e in self.events}
        self.done = {e["id"] for e in self.events if e["k"] in ("fill", "carry")}
        verify_chain(self.events)

    # single write path: ids are unique, completions happen once
    def append(self, e):
        if e["id"] in self.ids and e["k"] not in ("fill", "carry"):
            raise DuplicateEvent(e["id"])
        if e["k"] in ("fill", "carry"):
            if e["id"] in self.done:
                raise DuplicateEvent("second completion of " + e["id"])
            if e["id"] not in self.ids:
                raise DuplicateEvent("completion for unknown order " + e["id"])
            self.done.add(e["id"])
        prev = self.events[-1]["h"] if self.events else None
        e = {"seq": len(self.events), **e, "prev": prev}
        e["h"] = ev_hash(e, prev)
        self.events.append(e)
        self.ids.add(e["id"])
        return e

    def ingest(self, daily):
        """Record official closes, dividends and splits from the published daily file (append-only)."""
        dates = daily.get("dates", [])
        for t, cl in daily.get("c", {}).items():
            m = self.px.setdefault(t, {})
            for d, v in zip(dates, cl):
                if v is not None and d not in m and D(d) <= self.today:
                    m[d] = v
        for t, lst in daily.get("div", {}).items():
            m = self.div.setdefault(t, {})
            for d, v in lst:
                if d not in m and D(d) <= self.today:
                    m[d] = v
        for t, lst in daily.get("split", {}).items():
            m = self.split.setdefault(t, {})
            for d, v in lst:
                if d not in m and D(d) <= self.today:
                    m[d] = v
        self.dates |= {d for d in dates if D(d) <= self.today}
        self.s["dates"] = sorted(self.dates)

    def record_plan(self, doc):
        plans = doc.get("plans") or all_plans(doc.get("etfs", []))
        want = {CFG["horizon"] + r: [[x["k"], x["t"], x["w"]] for x in plans[CFG["horizon"] + r]["rows"]]
                for r in ("c", "b", "a", "v") if CFG["horizon"] + r in plans}
        last = next((e for e in reversed(self.events) if e["k"] == "plan"), None)
        if last and (last["plans"] == want or last["asOf"] >= doc["asOf"]):
            return
        self.append({"k": "plan", "id": "plan|" + doc["asOf"], "asOf": doc["asOf"], "plans": want,
                     "hash": hashlib.sha256(json.dumps(want, sort_keys=True).encode()).hexdigest()})

    def plan_for(self, d):
        ps = [e for e in self.events if e["k"] == "plan"]
        before = [e for e in ps if D(e["asOf"]) < d]
        return (before[-1] if before else ps[0]) if ps else None

    def session_on_or_after(self, t, d):
        ds = str(d)
        c = [x for x in self.px.get(t, {}) if x >= ds]
        return min(c) if c else None

    # ------------------------------------------------------------ the run
    def safe_to_place(self, d):
        """An order on day d takes the cash left by every earlier execution, so it is placed only once the official
        closes of every US session before d are in (a catch-up run then writes exactly the same orders)."""
        last = self._last
        s = d - timedelta(days=1)
        while s >= D(CFG["start"]):
            if last and s <= D(last):
                return True
            if is_us_session(s):
                return False
            s -= timedelta(days=1)
        return True

    def run(self, accts):
        """Day by day from the start: (1) dividends and splits with that ex-date, (2) that day's instalments and
        orders, (3) executions at that day's official close. Already-recorded steps are skipped, so any run — daily or
        after an outage — continues the same ledger."""
        start = D(CFG["start"])
        carry = self.carry_state()
        res = {a["id"]: a["res"] for a in accts}
        due = {}
        for a in accts:
            for d in due_dates(a["freq"], start, self.today):
                due.setdefault(d, []).append(a)
        act_days = {x for book in (self.div, self.split) for m in book.values() for x in m}
        pending = {}
        for e in self.events:
            if e["k"] == "order" and e["id"] not in self.done:
                T = self.session_on_or_after(e["t"], D(e["d"]))
                if T:
                    pending.setdefault(T, []).append(e)
        self._last = max(self.dates) if self.dates else None
        d = start
        while d <= self.today:
            ds = str(d)
            if ds in act_days:
                self.actions(ds, carry, res)
            if due.get(d):
                if not self.safe_to_place(d):
                    break
                p = self.plan_for(d)
                if not p:
                    break
                for a in due[d]:
                    iid = f"{a['id']}|{ds}"
                    if iid in self.ids:
                        continue
                    amt, step = contribution(a, d, start)
                    self.append({"k": "inst", "id": iid, "a": a["id"], "d": ds, "amt": amt, "plan": p["id"], **step})
                    for k, t, w in p["plans"][a["pid"]]:
                        share = round(amt * w / 100, 2)
                        cash = round(share + carry.get((a["id"], k), 0), 2)
                        carry[(a["id"], k)] = 0.0
                        o = self.append({"k": "order", "id": f"{iid}|{k}", "a": a["id"], "d": ds, "slot": k, "t": t,
                                         "share": share, "cash": cash})
                        T = self.session_on_or_after(t, d)
                        if T:
                            pending.setdefault(T, []).append(o)
            for o in sorted(pending.pop(ds, []), key=lambda e: e["seq"]):
                self.fill(o, ds, carry)
            d += timedelta(days=1)

    def carry_state(self):
        carry = {}
        for e in self.events:
            key = (e.get("a"), e.get("slot"))
            if e["k"] == "order":
                carry[key] = 0.0
            elif e["k"] in ("fill", "carry"):
                carry[key] = round(carry.get(key, 0) + e["left"], 2)
            elif e["k"] == "div":
                carry[key] = round(carry.get(key, 0) + e["net"], 2)
        return carry

    def lots(self, upto=None):
        """Lots per account & ticker from fills (and splits), optionally only trades before a date."""
        out = {}
        for e in self.events:
            if e["k"] == "fill" and e["n"] > 0 and (upto is None or D(e["T"]) < upto):
                out.setdefault((e["a"], e["t"]), []).append({"T": e["T"], "n": e["n"], "cost": e["cost"], "cr": e["cr"]})
            elif e["k"] == "split" and (upto is None or D(e["d"]) < upto):
                for l_ in out.get((e["a"], e["t"]), []):
                    if D(l_["T"]) < D(e["d"]):
                        l_["n"] = r6(l_["n"] * e["ratio"])
        return out

    def actions(self, ds, carry, res):
        wht = CFG["withholding"]
        for kind, book in (("split", self.split), ("div", self.div)):
            for t in sorted(book):
                if ds not in book[t]:
                    continue
                for (aid, tk), ls in sorted(self.lots(upto=D(ds)).items()):
                    units = r6(sum(l_["n"] for l_ in ls))
                    eid = f"{aid}|{kind}|{t}|{ds}"
                    if tk != t or units <= 0 or eid in self.ids:
                        continue
                    if kind == "split":
                        self.append({"k": "split", "id": eid, "a": aid, "t": t, "d": ds, "ratio": book[t][ds],
                                     "before": units, "after": r6(units * book[t][ds])})
                        continue
                    dps = book[t][ds]
                    gross = round(units * dps, 2)
                    rate = wht["nri"] if res.get(aid) == "nri" else wht["resident"]
                    tax = round(gross * rate / 100, 2)
                    slot = SLOT_OF.get(t, "us_core")
                    self.append({"k": "div", "id": eid, "a": aid, "t": t, "ex": ds, "slot": slot, "units": units, "dps": dps,
                                 "gross": gross, "wht": tax, "rate": rate, "net": round(gross - tax, 2)})
                    carry[(aid, slot)] = round(carry.get((aid, slot), 0) + gross - tax, 2)

    def fill(self, o, T, carry):
        px = self.px[o["t"]][T]
        n = max_units(o["cash"], px)
        fee = fee_for(n, px)
        cost = round(n * px + fee, 2)
        rest = round(o["cash"] - cost, 2)
        base = {"id": o["id"], "a": o["a"], "t": o["t"], "slot": o["slot"], "T": T, "px": px,
                "rule": CFG["trade"]["rule"], "priceTime": CFG["trade"]["priceTime"], "left": rest}
        if n > 0:
            self.append({"k": "fill", **base, "n": n, "fee": fee, "cost": cost,
                         "cr": str(add_business(D(T), CFG["trade"]["settleDays"]))})
        else:
            self.append({"k": "carry", **base, "n": 0, "why": "below the minimum order value"})
        carry[(o["a"], o["slot"])] = round(carry.get((o["a"], o["slot"]), 0) + rest, 2)


# ---------------------------------------------------------------- valuation, journal, public files
def close_on(px, t, d):
    m = px.get(t, {})
    ks = [x for x in m if x <= d]
    if not ks:
        return None, None
    k = max(ks)
    return m[k], k


def bench_series(store, accts):
    """Same cash on the same days into SPY (fractional, no costs), dividends net of the account's withholding
    reinvested at the ex-date close; units count at cost until T+1. Returns {acct: [(date, units, pend_lots)]}."""
    b = CFG["bench"]
    px, div = store["px"].get(b, {}), store["div"].get(b, {})
    wht = CFG["withholding"]
    out = {}
    insts = [e for e in store["events"] if e["k"] == "inst"]
    for a in accts:
        lots = []
        for e in insts:
            if e["a"] != a["id"]:
                continue
            T = min([x for x in px if D(x) >= D(e["d"])], default=None)
            if T:
                lots.append({"T": T, "n": e["amt"] / px[T], "cost": e["amt"], "cr": str(add_business(D(T), 1))})
        rate = wht["nri"] if a["res"] == "nri" else wht["resident"]
        for ex in sorted(div):
            held = sum(l_["n"] for l_ in lots if D(l_["T"]) < D(ex))
            if held > 0 and ex in px:
                net = held * div[ex] * (1 - rate / 100)
                lots.append({"T": ex, "n": net / px[ex], "cost": 0.0, "cr": ex, "div": True})
        out[a["id"]] = lots
    return out


def bench_value(lots, px, d, inv_cash=None):
    p, _ = close_on(px, CFG["bench"], d)
    v = 0.0
    for l_ in lots:
        if D(l_["T"]) > D(d):
            continue
        v += l_["n"] * p if D(l_["cr"]) <= D(d) else l_["cost"]
    return v


def xirr(flows):
    if not flows or all(f[1] >= 0 for f in flows) or all(f[1] <= 0 for f in flows):
        return None
    t0 = flows[0][0]

    def npv(r):
        return sum(c / (1 + r) ** ((d - t0).days / 365.0) for d, c in flows)
    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def snapshot(store, a, d, names, evs=None):
    """Account state on session d: holdings (credited / at cost), cash, invested."""
    evs = evs if evs is not None else [e for e in store["events"] if e.get("a") == a["id"]]
    px = store["px"]
    inv = sum(e["amt"] for e in evs if e["k"] == "inst" and e["a"] == a["id"] and D(e["d"]) <= D(d))
    hold = {}
    cash = 0.0
    for e in evs:
        if e.get("a") != a["id"]:
            continue
        if e["k"] == "order" and D(e["d"]) <= D(d):
            cash += e["share"]               # money of the instalment, until spent
        elif e["k"] in ("fill", "carry") and D(e["T"]) <= D(d):
            if e["k"] == "fill":
                h = hold.setdefault(e["t"], {"lots": []})
                h["lots"].append({"T": e["T"], "n": e["n"], "cost": e["cost"], "cr": e["cr"]})
                cash -= e["cost"]
        elif e["k"] == "div" and D(e["ex"]) <= D(d):
            cash += e["net"]
        elif e["k"] == "split" and D(e["d"]) <= D(d):
            for l_ in hold.get(e["t"], {}).get("lots", []):
                if D(l_["T"]) < D(e["d"]):
                    l_["n"] = r6(l_["n"] * e["ratio"])
    rows = []
    for t, h in hold.items():
        p, pd_ = close_on(px, t, d)
        cu = sum(l_["n"] for l_ in h["lots"] if D(l_["cr"]) <= D(d))
        pu = sum(l_["n"] for l_ in h["lots"] if D(l_["cr"]) > D(d))
        pc = sum(l_["cost"] for l_ in h["lots"] if D(l_["cr"]) > D(d))
        cost = sum(l_["cost"] for l_ in h["lots"])
        rows.append({"t": t, "n": names.get(t, t), "cu": cu, "pu": pu, "pc": round(pc, 2), "cost": round(cost, 2), "px": p, "pd": pd_,
                     "val": round(cu * (p or 0), 2), "cr": max((l_["cr"] for l_ in h["lots"] if D(l_["cr"]) > D(d)), default=None)})
    val = sum(r["cu"] * (r["px"] or 0) + r["pc"] for r in rows) + cash
    return {"inv": inv, "cash": round(cash, 2), "rows": rows, "val": round(val, 2)}


def build_view(store, today):
    accts = accounts()
    names, cats, grp = {}, {}, {}
    try:
        g = json.loads((DATA / "global_etf.json").read_text())
        for e in g["etfs"]:
            names[e["t"]] = e["n"]; cats[e["t"]] = e.get("cat", "")
    except Exception:  # noqa: BLE001
        pass
    for t, k in SLOT_OF.items():
        grp[t] = SLOTS[k]["grp"]
    sessions = sorted(d for d in store.get("dates", []) if D(d) >= D(CFG["start"]) and D(d) <= today)
    bench = bench_series(store, accts)
    bpx = store["px"]
    view = {"start": CFG["start"], "today": str(today), "asOf": sessions[-1] if sessions else None, "accounts": []}
    mkt = {}
    for i, d in enumerate(sessions):
        prev = sessions[i - 1] if i else None
        row = []
        for t, lab in MARKET_LABELS:
            p, pd_ = close_on(bpx, t, d)
            q, qd = close_on(bpx, t, prev) if prev else (None, None)
            if p and q and pd_ == d:
                row.append([lab, t, round((p / q - 1) * 100, 2)])
        mkt[d] = sorted(row, key=lambda x: -abs(x[2]))
    by_acct = {}
    for e in store["events"]:
        if e.get("a"):
            by_acct.setdefault(e["a"], []).append(e)
    for a in accts:
        aev = by_acct.get(a["id"], [])
        days, prev = [], None
        first_fill = min((e["T"] for e in store["events"] if e["k"] == "fill" and e["a"] == a["id"]), default=None)
        for d in sessions:
            if not first_fill or D(d) < D(first_fill):
                continue
            s = snapshot(store, a, d, names, aev)
            if not any(r["cu"] > 0 for r in s["rows"]):
                continue                       # first record once shares are credited
            bv = round(bench_value(bench[a["id"]], bpx, d), 2)
            hold = []
            for r in s["rows"]:
                pp, ppd = (close_on(bpx, r["t"], prev["d"]) if prev else (None, None))
                pr = next((x for x in prev["rows"] if x["t"] == r["t"]), None) if prev else None
                chg = round(r["val"] - (pr["cu"] * (pp or 0) if pr else 0) - (r["cu"] - (pr["cu"] if pr else 0)) * (r["px"] or 0), 2) if prev else round(r["val"] + r["pc"] - r["cost"], 2)
                hold.append([r["n"], r["t"], cats.get(r["t"], ""), r["cu"], r["px"], r["pd"], pp, ppd, r["val"], r["pc"], chg])
            if prev:
                new = s["inv"] - prev["inv"]
                chg = round(s["val"] - prev["val"] - new, 2)
                pct = round(chg / prev["val"] * 100, 2) if prev["val"] else 0.0
                bchg = round(bv - prev["bval"] - new, 2)
                bpct = round(bchg / prev["bval"] * 100, 2) if prev["bval"] else 0.0
            else:
                chg = round(s["val"] - s["inv"], 2); pct = round(chg / s["inv"] * 100, 2) if s["inv"] else 0.0
                bchg = round(bv - s["inv"], 2); bpct = round(bchg / s["inv"] * 100, 2) if s["inv"] else 0.0
            rec = {"d": d, "val": s["val"], "inv": s["inv"], "chg": chg, "pct": pct, "bval": bv, "bchg": bchg, "bpct": bpct,
                   "first": prev is None, "cash": s["cash"], "pend": round(sum(r["pc"] for r in s["rows"]), 2), "hold": hold,
                   "rows": s["rows"], "mkt": mkt.get(d, [])}
            days.append(rec)
            prev = rec
        last = snapshot(store, a, sessions[-1], names, aev) if sessions else {"inv": 0, "cash": 0, "rows": [], "val": 0}
        evs = aev
        open_orders = [e for e in evs if e["k"] == "order" and not any(x["k"] in ("fill", "carry") and x["id"] == e["id"] for x in evs)]
        view["accounts"].append({**a, "days": days, "last": last, "events": evs, "open": open_orders,
                                 "divNet": round(sum(e["net"] for e in evs if e["k"] == "div"), 2),
                                 "divWht": round(sum(e["wht"] for e in evs if e["k"] == "div"), 2),
                                 "fees": round(sum(e["fee"] for e in evs if e["k"] == "fill"), 2)})
    view["names"], view["cats"], view["grp"] = names, cats, grp
    return view


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


_GCAT = None


def vs_category(t):
    """The ETF's own 1-year and 3-year return (3Y per year) against the simple average of the ETFs in its category on
    the Global ETF page (its asset class when the category has fewer than three); see sim_engine.vs_category."""
    global _GCAT
    if _GCAT is None:
        try:
            etfs = json.loads((DATA / "global_etf.json").read_text())["etfs"]
        except Exception:  # noqa: BLE001
            etfs = []
        _GCAT = {e["t"]: e for e in etfs}
    e = _GCAT.get(t)
    if not e:
        return None
    peers = [x for x in _GCAT.values() if x.get("cat") == e.get("cat")]
    if len(peers) < 3:
        peers = [x for x in _GCAT.values() if x.get("ac") == e.get("ac")]
    avg = []
    for k in ("1y", "3y"):
        v = [(x.get("r") or {}).get(k) for x in peers]
        v = [y for y in v if y is not None]
        avg.append(round(sum(v) / len(v), 2) if len(v) >= 3 else None)
    own = [(e.get("r") or {}).get("1y"), (e.get("r") or {}).get("3y")]
    cmp = [o >= a for o, a in zip(own, avg) if o is not None and a is not None]
    return {"n": len(peers), "own": own, "avg": avg, "v": ("beat" if all(cmp) else "lag" if not any(cmp) else "mixed") if cmp else None}


def public(view, audit_ok):
    """Scoreboard (data/gsim_scoreboard.json) + per-account files (data/gsim/<slug>.json, only while the audit passes)."""
    today = D(view["today"])
    rows, files = [], {}
    keep = CFG["keepPublicDays"]
    for a in view["accounts"]:
        ds = a["days"]
        last = ds[-1] if ds else None
        pend_cr = max((r["cr"] for r in a["last"]["rows"] if r["cr"]), default=None)
        if not pend_cr and a["open"]:
            pend_cr = None
        valued = bool(last) and audit_ok
        days_ = (D(last["d"]) - D(CFG["start"])).days if last else 0
        ret = None
        metric = "abs"
        if valued:
            if days_ >= 365:
                flows = [(D(e["d"]), -e["amt"]) for e in a["events"] if e["k"] == "inst"] + [(D(last["d"]), last["val"])]
                x = xirr(sorted(flows))
                ret = round(x * 100, 2) if x is not None else None
                metric = "xirr"
            else:
                ret = round((last["val"] / last["inv"] - 1) * 100, 2) if last["inv"] else None
        row = {"name": a["name"], "product": "gl", "risk": RISK_NAMES[a["risk"]], "freq": FREQ[a["freq"]], "amt": a["amt"],
               "nri": a["res"] == "nri", "role": a["role"], "desk": a["desk"], "team": a["team"], "dip": False,
               "since": CFG["start"], "days": days_ if valued else 0, "metric": metric, "ret": ret, "f": slug(a["name"]) + "-gl"}
        if a.get("step"):
            row["step"] = {"k": a["step"], **{k: v for k, v in CFG["stepUps"][a["step"]].items() if k != "accounts"}}
        if pend_cr:
            row["credit"] = pend_cr
        elif a["open"]:
            row["credit"] = None
        if last:
            row["day"] = {"d": last["d"], "chg": last["chg"], "pct": last["pct"], "first": last["first"]}
        rows.append(row)
        if not audit_ok:
            continue
        L = a["last"]
        tot = sum(r["val"] + r["pc"] for r in L["rows"]) or 1
        hold = [{"n": r["n"], "k": r["t"], "cat": view["cats"].get(r["t"], ""), "u": r["cu"] + r["pu"],
                 "avg": round(r["cost"] / (r["cu"] + r["pu"]), 4) if r["cu"] + r["pu"] else None, "px": r["px"], "pd": r["pd"],
                 "val": round(r["val"] + r["pc"], 2), "g": round(((r["val"] + r["pc"]) / r["cost"] - 1) * 100, 2) if r["cu"] and r["cost"] and not r["pu"] else None,
                 "w": round((r["val"] + r["pc"]) / tot * 100, 1), "pu": r["pu"] or None, "cr": r["cr"], "vc": vs_category(r["t"])} for r in sorted(L["rows"], key=lambda r: -(r["val"] + r["pc"]))]
        pend = [{"n": view["names"].get(o["t"], o["t"]), "k": o["t"], "amt": o["cash"], "T": o["d"],
                 "st": "executes at the official close of the first session on or after the order day"} for o in a["open"]]
        paid = sum(e["amt"] for e in a["events"] if e["k"] == "inst" and D(e["d"]) <= today)
        detail = {"inv": max(L["inv"], paid), "val": last["val"] if last else None, "gain": round(last["val"] - last["inv"], 2) if last else None,
                  "bench": round((last["bval"] / last["inv"] - 1) * 100, 2) if last and last["inv"] else None,
                  "asOf": view["asOf"], "next": str(next_due(a["freq"], max(today, D(CFG["start"])) - timedelta(days=0))) if a["freq"] != "l" else None,
                  "hold": hold, "pend": pend, "cash": L["cash"], "div": a["divNet"], "wht": a["divWht"], "fees": a["fees"]}
        if a["freq"] != "l":
            nd = next_due(a["freq"], today)
            if not nd or D(CFG["start"]) > today:
                nd = D(CFG["start"])
            detail["next"] = str(nd)
        alloc = {}
        for r in L["rows"]:
            lab = ALLOC_OF.get(view["grp"].get(r["t"], "eq"), "Equity")
            if lab == "Equity" and SLOT_OF.get(r["t"]) in ("intl", "em"):
                lab = "International"
            alloc[lab] = alloc.get(lab, 0) + r["val"] + r["pc"]
        if L["cash"] > 0:
            alloc["Cash & others"] = alloc.get("Cash & others", 0) + L["cash"]
        at = sum(alloc.values()) or 1
        files[row["f"]] = {"v": 1, "id": a["id"], "updated": view["asOf"] or CFG["start"], "auditOk": True,
                           **{k: row[k] for k in ("name", "product", "risk", "freq", "amt", "nri", "since", "metric", "ret")},
                           "credit": row.get("credit"), "detail": detail,
                           "orders": [
                               {"id": str(o.get("id", "")), "placedAt": o.get("d"),
                                "completedAt": fill.get("T") if fill and fill.get("k") == "fill" else None,
                                "settledAt": fill.get("cr") if fill and fill.get("k") == "fill" else None,
                                "name": o.get("t"), "symbol": o.get("t"), "side": "buy",
                                "quantity": fill.get("n") if fill and fill.get("k") == "fill" else None,
                                "price": fill.get("px") if fill and fill.get("k") == "fill" else None,
                                "amount": fill.get("cost") if fill and fill.get("k") == "fill" else o.get("cash"),
                                "status": ("Completed" if fill and fill.get("k") == "fill" and
                                           fill.get("cr", "9999") <= view["today"] else "In progress")}
                               for o in a["events"] if o.get("k") == "order"
                               for fill in [next((e for e in a["events"] if e.get("id") == o.get("id")
                                                 and e.get("k") in ("fill", "carry")), None)]
                           ],

                           "series": [[e["d"], e["val"], e["inv"], e["pct"], e["bpct"], e["bval"]] for e in ds],
                           "recent": [{k: e[k] for k in ("d", "val", "inv", "chg", "pct", "bval", "bchg", "bpct", "first", "cash", "pend", "hold", "mkt")} for e in ds[-keep:]],
                           "breakdown": {"alloc": sorted([[k, round(v / at * 100, 2)] for k, v in alloc.items()], key=lambda x: -x[1]),
                                         "d": last["d"] if last else view["asOf"], "val": round(at, 2), "pfCover": 100, "global": True} if L["rows"] else None}
    sb = {"v": 4, "cur": "USD", "dir": "gsim", "bench": "S&P 500", "benchKey": "SPY", "updated": view["asOf"] or CFG["start"],
          "start": CFG["start"], "auditOk": audit_ok, "rows": rows}
    return sb, files


def restate(old, meta_out=None):
    """Ledger epoch change (gsim_config "ledgerEpoch" / "restatement"): start a new hash chain from the start date with
    the old ledger's plan snapshots — every existing plan row copied exactly, plus the seeded rows of plans added since
    (e.g. h15v) — so the replay re-buys every account at the same official closes. Returns the new store; the old one
    is archived by the caller. Refuses when a plan date has no seed."""
    R = CFG["restatement"]
    old_ev = old.get("events", [])
    new = {"meta": {"v": 1, "start": CFG["start"], "created": old.get("meta", {}).get("created"), "epoch": CFG["ledgerEpoch"],
                    "restated": {"date": R["date"], "fromEpoch": old.get("meta", {}).get("epoch", 1), "fromEvents": len(old_ev),
                                 "fromHead": old_ev[-1]["h"] if old_ev else None, "plans": []}},
           "events": []}
    eng = Engine(new, D(R["date"]))
    for e in old_ev:
        if e["k"] != "plan":
            continue
        seed = R["seedPlans"].get(e["asOf"]) or {}
        need = {CFG["horizon"] + r for r in set(CFG["riskMap"].values())}
        missing = need - set(e["plans"]) - set(seed)
        if missing:
            raise SystemExit(f"restatement: no seed for {sorted(missing)} in the snapshot of {e['asOf']} — refusing")
        plans = {**e["plans"], **{k: v for k, v in seed.items() if k not in e["plans"]}}
        new["meta"]["restated"]["plans"].append({"asOf": e["asOf"], "oldHash": e["hash"], "kept": sorted(e["plans"])})
        eng.append({"k": "plan", "id": e["id"], "asOf": e["asOf"], "plans": plans,
                    "hash": hashlib.sha256(json.dumps(plans, sort_keys=True).encode()).hexdigest()})
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--view")
    ap.add_argument("--today")
    ap.add_argument("--meta", default=str(DATA / "gsim_meta.json"))
    ap.add_argument("--daily", default=str(DATA / "global_etf_daily.json"))
    ap.add_argument("--data", default=str(DATA / "global_etf.json"))
    args = ap.parse_args()
    if args.today:
        today = D(args.today)
    else:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/New_York")).date()
    p = Path(args.store)
    store = json.loads(p.read_text()) if p.exists() and p.stat().st_size > 2 else {}
    store.setdefault("meta", {"v": 1, "start": CFG["start"], "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "epoch": CFG.get("ledgerEpoch", 1)})
    meta = json.loads(Path(args.meta).read_text()) if Path(args.meta).exists() else {}
    evs = store.get("events", [])
    epoch = CFG.get("ledgerEpoch", 1)
    if evs and store["meta"].get("epoch", 1) < epoch:
        # the downloaded ledger must still be the published one before it is restated
        if meta.get("events") and (len(evs) < meta["events"] or evs[meta["events"] - 1]["h"] != meta["head"]):
            print("ledger does not continue the published head — refusing to restate"); return 1
        arch = p.with_name(p.stem + f".epoch{store['meta'].get('epoch', 1)}.json")
        arch.write_text(json.dumps(store, separators=(",", ":")))
        store = restate(store)
        evs = store["events"]
        meta = {}
        print(f"ledger restated to epoch {epoch}: {len(evs)} plan snapshots carried over, old ledger archived as {arch.name}")
    elif meta.get("epoch", 1) > store["meta"].get("epoch", 1):
        print("the published ledger is a newer epoch than the downloaded copy — refusing to run"); return 1
    if meta.get("events") and meta.get("epoch", 1) == store["meta"].get("epoch", 1):
        n = meta["events"]
        if len(evs) < n or evs[n - 1]["h"] != meta["head"]:
            print(f"ledger ({len(evs)} entries) does not continue the published head at entry {n} — refusing to run")
            return 1
    eng = Engine(store, today)
    if Path(args.daily).exists():
        eng.ingest(json.loads(Path(args.daily).read_text()))
    doc = json.loads(Path(args.data).read_text())
    eng.record_plan(doc)
    before = len(eng.events)
    eng.run(accounts())
    p.write_text(json.dumps(store, separators=(",", ":")))
    print(f"ledger: {len(eng.events)} entries (+{len(eng.events) - before}) · closes up to {max(store['dates']) if store.get('dates') else '–'}")
    if args.view:
        Path(args.view).write_text(json.dumps(build_view(store, today), separators=(",", ":"), default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
