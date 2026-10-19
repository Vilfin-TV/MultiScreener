#!/usr/bin/env python3
"""
sim_engine.py — Simulator Buy: real-life tracking accounts for the Portfolio Simulator's model portfolios.

Each person in scripts/sim_config.json holds a mutual fund account and an ETF demat account that buy the
Portfolio Simulator's 10+ year model portfolio for their risk level on their schedule, starting 19 Oct 2026,
with real-life order rules:

  Mutual funds  order placed before the 3 pm cut-off on the trade date T (a holiday or weekend rolls to the next
                trading day) · official NAV of T (liquid / overnight funds: NAV of the previous calendar day) ·
                stamp duty 0.005% · units truncated to 3 decimals · "Buy in progress" until credited T+2 business
                days · amounts split with the simulator's own sizing rules (minimums, merged slots, upgrade funds)
  ETFs          delivery buy at the closing price of T · whole units · leftover cash carried per holding ·
                stamp duty, exchange / SEBI / investor-protection charges, GST, brokerage (NRI desks) ·
                STT and DP charge on sells · credited T+1
  Review        on each start anniversary a very weak holding is switched to the current model choice
  Sells         redemptions (review switches or entries in sim_config "sells") with exit load, STT, FIFO lots,
                capital gains and NRI TDS estimates

State is an append-only event log; every event carries the hash of the previous one, so any later edit breaks the
chain (scripts/audit_sim.py checks it). The ledger, prices used, plan snapshots and daily valuations live in the
private R2 store (downloaded / uploaded by .github/workflows/sim_ledger.yml); only per-person return percentages are
published (data/sim_scoreboard.json).

Usage: python scripts/sim_engine.py --store sim_store.json [--today YYYY-MM-DD] [--view out.json]
       [--scoreboard data/sim_scoreboard.json] [--backtest-start YYYY-MM-DD] [--no-network]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CFG = json.loads((ROOT / "scripts" / "sim_config.json").read_text())
log = logging.getLogger("sim")
AMFI_HIST = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?tp=1&frmdt={f}&todt={t}"
IST = timezone(timedelta(hours=5, minutes=30))


def D(s) -> date:
    return s if isinstance(s, date) else date.fromisoformat(str(s)[:10])


def r2(x: float) -> float:
    return round(x + 0.0, 2)


def trunc(x: float, n: int) -> float:
    f = 10 ** n
    return math.floor(x * f + 1e-9) / f


# ───────────────────────────── calendar ─────────────────────────────
def load_holidays() -> set[str]:
    try:
        h = json.loads((DATA / "nse_holidays.json").read_text())
    except Exception:  # noqa: BLE001
        return set()
    items = h if isinstance(h, list) else h.get("holidays", h)
    return {x for x in items if isinstance(x, str) and len(x) == 10 and x[4] == "-"}


HOL = load_holidays()


def is_trading(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in HOL


def next_trading(d: date) -> date:
    while not is_trading(d):
        d += timedelta(days=1)
    return d


def add_business(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if is_trading(d):
            n -= 1
    return d


# ───────────────────────────── accounts & schedules ─────────────────────────────
def instalment_amount(risk: str, freq: str) -> int:
    m = CFG["monthly"][risk]
    if freq == "m":
        return m
    if freq == "w":
        return int(round(m * 12 / 52 / 10) * 10)
    if freq == "q":
        return m * 3
    return m * 12                                   # yearly and one-time: one year of investing


def accounts() -> list[dict]:
    out = []
    for p in CFG["persons"]:
        for prod in ("mf", "etf"):
            out.append({"id": f"{p['name']}-{prod.upper()}", "name": p["name"], "product": prod, "risk": p["risk"],
                        "freq": p["freq"], "res": p["res"], "plan": CFG["horizon"] + p["risk"],
                        "amount": instalment_amount(p["risk"], p["freq"])})
    return out


def schedule(freq: str, until: date) -> list[tuple[date, date]]:
    """[(nominal date, trade date)] from the start up to `until` (trade date ≤ until)."""
    sc, start = CFG["schedule"], D(CFG["start"])
    nominal = [start]
    if freq == "m":
        y, m = start.year, start.month
        while True:
            m += 1
            if m > 12:
                y, m = y + 1, 1
            d = date(y, m, sc["monthDay"])
            if d > until + timedelta(days=10):
                break
            nominal.append(d)
    elif freq == "w":
        d = start
        while d <= until + timedelta(days=10):
            d += timedelta(days=7)
            nominal.append(d)
    elif freq == "q":
        y = start.year
        while True:
            for mo in sc["quarterMonths"]:
                d = date(y, mo, sc["anchorDay"])
                if d > start:
                    nominal.append(d)
            if date(y, 1, 1) > until:
                break
            y += 1
    elif freq == "y":
        y = start.year
        while date(y + 1, sc["anchorMonth"], sc["anchorDay"]) <= until + timedelta(days=10):
            y += 1
            nominal.append(date(y, sc["anchorMonth"], sc["anchorDay"]))
    seen, out = set(), []
    for n in sorted(set(nominal)):
        t = next_trading(n)
        if t <= until and t not in seen:
            seen.add(t)
            out.append((n, t))
    return out


# ───────────────────────────── market data ─────────────────────────────
class Market:
    """Official NAVs and exchange closes, cached in the store so every value used stays on record."""

    def __init__(self, store: dict, network: bool, backtest: bool = False):
        self.c = store.setdefault("prices", {"mf": {}, "etf": {}, "amfi": {}})
        self.c.setdefault("amfi", {})
        self.network, self.backtest = network, backtest
        s = json.loads((DATA / "mf" / "screener.json").read_text())
        cols = s["cols"]
        self.funds = {r[cols.index("code")]: dict(zip(cols, r)) for r in s["rows"]}
        self.mf_asof = s["asOf"]
        m = json.loads((DATA / "etf_momentum.json").read_text())
        self.etfs = {e["s"]: e for e in m["etfs"]}
        self.etf_asof = max((e.get("d") or "") for e in m["etfs"])
        self._tail_loaded = set()
        self._bars = {}
        self._hist = {}

    # mutual funds
    def _merge_tail(self, code: int):
        if code in self._tail_loaded:
            return
        self._tail_loaded.add(code)
        f = self.funds.get(code)
        if not f:
            return
        mc = self.c["mf"].setdefault(str(code), {})
        try:
            t = json.loads((DATA / "mf" / "t" / f"{f['sub']}.json").read_text()).get(str(code)) or {}
            for d, v in t.get("p") or []:
                mc.setdefault(d, v)
        except Exception:  # noqa: BLE001
            pass
        if f.get("nav") and f.get("navDate"):
            mc.setdefault(f["navDate"], f["nav"])

    def _hist_nav(self, code: int, d: date):
        """Backtests only: NAV from the weekly history file (nearest point on or before the date)."""
        if code not in self._hist:
            try:
                h = json.loads((DATA / "mf" / "h" / f"{code}.json").read_text())
                s0 = D(h["s"])
                self._hist[code] = [(s0 + timedelta(days=o), v) for o, v in h["p"]]
            except Exception:  # noqa: BLE001
                self._hist[code] = []
        pts = [p for p in self._hist[code] if p[0] <= d]
        return pts[-1][1] if pts and (d - pts[-1][0]).days <= 10 else None

    def fetch_amfi(self, days: list[date], codes: set[int]):
        """Official AMFI NAVs for the given days (4-day windows), stored in the cache and marked verified."""
        if not self.network or not days or not codes:
            return
        import requests
        want = sorted({d for d in days if d.isoformat() not in self.c["amfi"]})
        for end in want:
            win = [end - timedelta(days=k) for k in range(3, -1, -1)]
            url = AMFI_HIST.format(f=win[0].strftime("%d-%b-%Y"), t=win[-1].strftime("%d-%b-%Y"))
            try:
                r = requests.get(url, timeout=180, headers={"User-Agent": "Mozilla/5.0 (compatible; VilfinTV-data/1.0)"})
                r.raise_for_status()
            except Exception as e:  # noqa: BLE001
                log.warning("AMFI history %s: %s", url, e)
                continue
            got = 0
            for line in r.text.splitlines():
                p = line.strip().split(";")
                if len(p) < 8 or not p[0].isdigit() or int(p[0]) not in codes:
                    continue
                try:
                    v, dd = float(p[6]), datetime.strptime(p[7].strip(), "%d-%b-%Y").date()
                except ValueError:
                    continue
                if v > 0:
                    self.c["mf"].setdefault(p[0], {})[dd.isoformat()] = v
                    self.c["amfi"].setdefault(dd.isoformat(), {})[p[0]] = v
                    got += 1
            log.info("AMFI official NAVs %s–%s: %d values", win[0], win[-1], got)

    def mf_nav(self, code: int, d: date):
        self._merge_tail(code)
        v = self.c["mf"].get(str(code), {}).get(d.isoformat())
        if v is None and self.backtest:
            v = self._hist_nav(code, d)
            if v is not None:                              # keep every price used on record (the audit reads it)
                self.c["mf"].setdefault(str(code), {})[d.isoformat()] = v
        return v

    def mf_dates(self, code: int) -> list[str]:
        self._merge_tail(code)
        return sorted(self.c["mf"].get(str(code), {}))

    def mf_latest(self, code: int, upto: date):
        if self.backtest:
            for k in range(0, 12):
                v = self.mf_nav(code, upto - timedelta(days=k))
                if v:
                    return upto - timedelta(days=k), v
            return None, None
        ds = [d for d in self.mf_dates(code) if d <= upto.isoformat()]
        return (D(ds[-1]), self.c["mf"][str(code)][ds[-1]]) if ds else (None, None)

    # ETFs
    def bars(self, sym: str):
        if sym not in self._bars:
            try:
                b = json.loads((DATA / "etf" / "d" / f"{sym}.json").read_text())
                self._bars[sym] = {f"{t // 10000:04d}-{t // 100 % 100:02d}-{t % 100:02d}": c for t, c in zip(b["t"], b["c"])}
            except Exception:  # noqa: BLE001
                self._bars[sym] = {}
            ec = self.c["etf"].setdefault(sym, {})
            for k in list(self._bars[sym])[-30:]:      # keep the recent closes on record
                ec.setdefault(k, self._bars[sym][k])
        return self._bars[sym]

    def etf_close(self, sym: str, d: date):
        v = self.c["etf"].get(sym, {}).get(d.isoformat())
        if v is None:
            v = self.bars(sym).get(d.isoformat())
            if v is not None:
                self.c["etf"].setdefault(sym, {})[d.isoformat()] = v
        return v

    def etf_session_on_or_after(self, sym: str, d: date, upto: date):
        ks = sorted(k for k in set(self.bars(sym)) | set(self.c["etf"].get(sym, {})) if d.isoformat() <= k <= upto.isoformat())
        return (D(ks[0]), self.etf_close(sym, D(ks[0]))) if ks else (None, None)

    def etf_latest(self, sym: str, upto: date):
        ks = sorted(k for k in set(self.bars(sym)) | set(self.c["etf"].get(sym, {})) if k <= upto.isoformat())
        return (D(ks[-1]), self.etf_close(sym, D(ks[-1]))) if ks else (None, None)

    def etf_equity(self, sym: str) -> bool:
        k = (self.etfs.get(sym) or {}).get("k") or ""
        return not any(x in k for x in ("Gold", "Silver", "Liquid", "Debt", "International", "Global"))


# ───────────────────────────── charges ─────────────────────────────
def etf_charges(value: float, side: str, res: str, equity: bool) -> dict:
    f = CFG["etfFees"]
    brok = 0.0 if res == "resident" else min(max(value * f["brokerageNriRate"], f["brokerageNriMin"]), f["brokerageNriMax"])
    exch, sebi, ipft = value * f["exchange"], value * f["sebi"], value * f["ipft"]
    c = {"brokerage": r2(brok), "exchange": r2(exch), "sebi": r2(sebi), "ipft": r2(ipft),
         "gst": r2(f["gst"] * (brok + exch + sebi)),
         "stamp": r2(value * f["stampBuy"]) if side == "buy" else 0.0,
         "stt": r2(value * f["sttSellEquity"]) if side == "sell" and equity else 0.0,
         "dp": r2(f["dpSell"] * (1 + f["gst"])) if side == "sell" else 0.0}
    c["total"] = r2(sum(c.values()))
    return c


def etf_units_for(budget: float, price: float, res: str, equity: bool) -> tuple[int, dict]:
    n = int(budget // price) if price > 0 else 0
    while n > 0:
        ch = etf_charges(n * price, "buy", res, equity)
        if n * price + ch["total"] <= budget + 1e-9:
            return n, ch
        n -= 1
    return 0, etf_charges(0, "buy", res, equity)


# ───────────────────────────── plan snapshots & sizing ─────────────────────────────
def plan_snapshot() -> tuple[str, dict]:
    ss = json.loads((DATA / "mf" / "smartsip.json").read_text())
    es = json.loads((DATA / "etf_smart.json").read_text())
    mf = {}
    for pid, p in ss["plans"].items():
        if not pid.startswith(CFG["horizon"]):
            continue
        mf[pid] = [{k: s.get(k) for k in ("key", "label", "asset", "w", "code", "alts", "er", "tax")} |
                   {"upgrade": ({k: s["upgrade"].get(k) for k in ("code", "min", "tax", "er")} if s.get("upgrade") else None)}
                   for s in p["slots"]]
    etf = {}
    for pid, p in es["plans"].items():
        if not pid.startswith(CFG["horizon"]):
            continue
        etf[pid] = [{"id": x["id"], "w": x["w"], "sym": es["slots"][x["id"]]["sym"], "name": es["slots"][x["id"]].get("name"),
                     "label": es["slots"][x["id"]].get("label")} for x in p["slots"]]
    ref = f"{ss.get('generated', '')[:10]}|{es.get('generated', '')[:10]}"
    return ref, {"ref": ref, "mfAsOf": ss.get("asOf"), "etfAsOf": es.get("asOf"), "mf": mf, "etf": etf}


MERGE_TO = {"theme": "flexi", "intl": "flexi", "small": "mid", "mid": "flexi", "flexi": "core", "core": "flexi",
            "metal": "dcore", "gold": "dcore", "eqsav": "arb", "baf": "core", "dcore": "baf", "dshort": "arb", "arb": "dshort"}


def size_mf(slots: list[dict], amt: float, fq: str, funds: dict) -> list[dict]:
    """Port of sizePlan() in india_mf_screener.html — the simulator's own rules for splitting an amount."""
    def isnum(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    def min_of(code):
        f = funds.get(code) or {}
        m = max(f["sipMin"] if isnum(f.get("sipMin")) else 0, f["lumpMin"] if isnum(f.get("lumpMin")) else 0)
        return m if m > 0 else 500
    out = []
    for s in slots:
        if not (s.get("w") or 0) > 0:
            continue
        code, swapped = s["code"], None
        if fq == "w":
            f = funds.get(code)
            if f and f.get("buy") is not None and "W" not in f["buy"]:
                alt = next((c for c in (s.get("alts") or []) if funds.get(c) and funds[c].get("buy") is not None and "W" in funds[c]["buy"]), None)
                if alt:
                    swapped, code = code, alt
        out.append({"key": s["key"], "label": s["label"], "asset": s["asset"], "w": s["w"], "code": code,
                    "swapped": swapped, "src": s, "merged": []})
    guard = 0
    while len(out) > 1 and guard < 10:
        guard += 1
        bad = [s for s in out if amt * s["w"] / 100 < min_of(s["code"])]
        if not bad:
            break
        bad.sort(key=lambda s: s["w"])
        x = bad[0]
        tgt = next((s for s in out if s["key"] == MERGE_TO.get(x["key"])), None)
        if not tgt:
            same = sorted([s for s in out if s is not x and s["asset"] == x["asset"]], key=lambda s: -s["w"])
            tgt = same[0] if same else None
        if not tgt:
            tgt = sorted([s for s in out if s is not x], key=lambda s: -s["w"])[0]
        tgt["w"] += x["w"]
        tgt["merged"].append(x["label"])
        out.remove(x)
    left = amt
    for i, s in enumerate(out):
        s["amt"] = left if i == len(out) - 1 else round(amt * s["w"] / 100 / 10) * 10
        left -= s["amt"]
    for s in out:
        up = s["src"].get("upgrade")
        uf = up and funds.get(up["code"])
        if not uf or s["swapped"] or (fq == "w" and "W" not in (uf.get("buy") or "")) or s["amt"] < min_of(up["code"]):
            continue
        s["upFrom"], s["code"] = s["code"], up["code"]
    return out


# ───────────────────────────── event log ─────────────────────────────
def ev_hash(ev: dict) -> str:
    body = {k: v for k, v in ev.items() if k != "h"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def append(store: dict, kind: str, **data) -> dict:
    evs = store.setdefault("events", [])
    ev = {"seq": len(evs) + 1, "k": kind, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "prev": evs[-1]["h"] if evs else "genesis", **data}
    ev["h"] = ev_hash(ev)
    evs.append(ev)
    return ev


def replay(events: list[dict]) -> dict:
    """Current state of every account from the event log (the only source of truth)."""
    st = {}
    orders = {}
    for ev in events:
        k = ev["k"]
        if k == "instalment":
            a = st.setdefault(ev["acct"], {"inst": [], "orders": [], "lots": {}, "cash": 0.0, "carry": {}, "sells": []})
            a["inst"].append(ev)
            if ev["acct"].endswith("-ETF"):
                a["cash"] += ev["amount"]
        elif k == "order":
            a = st.setdefault(ev["acct"], {"inst": [], "orders": [], "lots": {}, "cash": 0.0, "carry": {}, "sells": []})
            o = dict(ev)
            orders[ev["oid"]] = o
            a["orders"].append(o)
        elif k in ("allot", "fill"):
            o = orders[ev["oid"]]
            o["done"] = ev
            a = st[o["acct"]]
            key = str(o.get("code") or o.get("sym"))
            a["lots"].setdefault(key, []).append({"date": o["T"], "units": ev["units"], "cost": ev["amount"] if k == "allot" else ev["gross"] + ev["charges"]["total"],
                                                  "price": ev.get("nav", ev.get("price")), "oid": o["oid"], "credit": ev["credit"]})
            if k == "fill":
                a["cash"] = r2(a["cash"] - ev["gross"] - ev["charges"]["total"])
                a["carry"][o["slot"]] = ev["carry"]
        elif k == "redeem":
            o = orders[ev["oid"]]
            o["done"] = ev
            a = st[o["acct"]]
            key = str(o.get("code") or o.get("sym"))
            left = ev["units"]
            lots = a["lots"].get(key, [])
            while left > 1e-9 and lots:
                take = min(left, lots[0]["units"])
                frac = take / lots[0]["units"]
                lots[0]["cost"] = lots[0]["cost"] * (1 - frac)
                lots[0]["units"] = round(lots[0]["units"] - take, 6)
                left = round(left - take, 6)
                if lots[0]["units"] <= 1e-9:
                    lots.pop(0)
            if o["acct"].endswith("-ETF") and not o.get("withdraw"):
                a["cash"] = r2(a["cash"] + ev["net"])
            a["sells"].append(dict(ev, withdraw=bool(o.get("withdraw"))))
    return st


# ───────────────────────────── engine ─────────────────────────────
class Engine:
    def __init__(self, store: dict, today: date, network: bool, backtest: bool = False):
        self.store, self.today, self.backtest = store, today, backtest
        self.mkt = Market(store, network, backtest)
        self.accts = accounts()
        store.setdefault("plans", {})
        store.setdefault("series", {})
        store.setdefault("meta", {"start": CFG["start"], "created": datetime.now(timezone.utc).isoformat()})

    # plan in force on a date
    def plan_on(self, d: date) -> dict:
        refs = sorted(self.store["plans"])
        best = None
        for r in refs:
            if self.store["plans"][r].get("since", r[:10]) <= d.isoformat():
                best = r
        return self.store["plans"][best or refs[0]]

    def snapshot(self):
        ref, snap = plan_snapshot()
        if ref not in self.store["plans"]:
            snap["since"] = self.today.isoformat() if self.store["plans"] else CFG["start"]
            if self.backtest:
                snap["since"] = "1900-01-01"
            self.store["plans"][ref] = snap
            append(self.store, "plan", ref=ref, sha=hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest())
            log.info("plan snapshot %s recorded", ref)

    def place_orders(self):
        st = replay(self.store["events"])
        start = D(CFG["start"])
        for a in self.accts:
            have = {e["T"] for e in st.get(a["id"], {}).get("inst", [])}
            for nominal, T in schedule(a["freq"], self.today):
                if T < start or T.isoformat() in have:
                    continue
                iid = f"{a['id']}|{T.isoformat()}"
                plan = self.plan_on(T)
                extra = {}
                if a["freq"] == "l":
                    pct = ((json.loads((DATA / "mf" / "smartsip.json").read_text()).get("market") or {}).get("n50") or {}).get("pePct")
                    extra["entry"] = ("invested at once (Nifty 50 valuation at the %dth percentile of 10 years — below the 60th)" % round((pct or 0) * 100)
                                      if pct is None or pct < 0.6 else "valuation above the 60th percentile — staged entry")
                append(self.store, "instalment", acct=a["id"], iid=iid, T=T.isoformat(), nominal=nominal.isoformat(),
                       amount=a["amount"], ref=plan["ref"], **extra)
                if a["product"] == "mf":
                    self.place_mf(a, T, iid, plan)
                else:
                    self.place_etf(a, T, iid, plan)

    def place_mf(self, a, T, iid, plan):
        funds = self.mkt.funds
        legs = size_mf(plan["mf"][a["plan"]], a["amount"], "l" if a["freq"] == "l" else a["freq"], funds)
        for s in legs:
            code, note = s["code"], []
            f = funds.get(code) or {}
            if f.get("buy") is not None and "L" not in f["buy"]:          # fresh lump sums paused → next open alternate
                alt = next((c for c in (s["src"].get("alts") or []) if funds.get(c) and "L" in (funds[c].get("buy") or "L")), None)
                if alt:
                    note.append(f"{f.get('name', code)} paused fresh purchases — bought the model's alternate")
                    code = alt
            if s.get("upFrom"):
                note.append("upgrade fund for this amount (the simulator's rule)")
            if s.get("swapped"):
                note.append("weekly-SIP alternate (the simulator's rule)")
            if s["merged"]:
                note.append("includes " + ", ".join(s["merged"]) + " (amount below the fund minimum)")
            append(self.store, "order", oid=f"{iid}|{s['key']}", iid=iid, acct=a["id"], T=T.isoformat(), side="buy",
                   code=code, name=(funds.get(code) or {}).get("name"), slot=s["key"], label=s["label"], asset=s["asset"],
                   weight=s["w"], amount=float(s["amt"]), note="; ".join(note), ref=plan["ref"])

    def place_etf(self, a, T, iid, plan):
        for x in plan["etf"][a["plan"]]:
            append(self.store, "order", oid=f"{iid}|{x['id']}", iid=iid, acct=a["id"], T=T.isoformat(), side="buy",
                   sym=x["sym"], name=x.get("name"), slot=x["id"], label=x.get("label"), weight=x["w"],
                   amount=r2(a["amount"] * x["w"] / 100), ref=plan["ref"])

    # settlement
    def settle(self):
        st = replay(self.store["events"])
        mf_upto = D(self.mkt.mf_asof) if not self.backtest else self.today
        etf_upto = D(self.mkt.etf_asof) if not self.backtest else self.today
        need_days, need_codes = [], set()
        for a in st.values():
            for o in a["orders"]:
                if "done" not in o and o.get("code"):
                    need_days.append(D(o["T"]))
                    need_codes.add(int(o["code"]))
        need_codes.add(int(CFG["benchmark"]["mf"]))
        self.mkt.fetch_amfi([d for d in need_days if d <= mf_upto], need_codes)
        accts = {x["id"]: x for x in self.accts}
        funded = {e["oid"]: e["amount"] for e in self.store["events"] if e["k"] == "fund"}
        for aid in sorted(st):
            a = st[aid]
            acc = accts.get(aid)
            pend = sorted([o for o in a["orders"] if "done" not in o], key=lambda o: (o["T"], o["oid"]))
            carry = dict(a["carry"])
            for o in pend:
                T = D(o["T"])
                if o["side"] == "buy" and o.get("amount") is None:
                    if o["oid"] not in funded:
                        continue                                    # switch-in waits for its sell proceeds
                    o = dict(o, amount=funded[o["oid"]])
                if o["side"] == "buy" and o.get("code"):
                    self.allot_mf(o, T, mf_upto)
                elif o["side"] == "buy":
                    done = self.fill_etf(o, T, etf_upto, acc["res"], carry)
                    if done:
                        carry[o["slot"]] = done["carry"]
                elif o["side"] == "sell":
                    self.redeem(o, T, mf_upto if o.get("code") else etf_upto, acc)

    def nav_date_for(self, code: int, T: date, upto: date):
        f = self.mkt.funds.get(code) or {}
        if f.get("sub") in CFG["mfRules"]["liquidSubs"]:
            d = T - timedelta(days=1)                       # liquid / overnight: NAV of the previous calendar day
            for k in range(0, 6):
                v = self.mkt.mf_nav(code, d - timedelta(days=k))
                if v:
                    return d - timedelta(days=k), v
            return None, None
        v = self.mkt.mf_nav(code, T)
        if v:
            return T, v
        later = [x for x in self.mkt.mf_dates(code) if T.isoformat() < x <= upto.isoformat()]
        if later and not self.backtest:                     # no NAV on T (a fund-house holiday) → next NAV day
            return D(later[0]), self.mkt.c["mf"][str(code)][later[0]]
        if self.backtest:
            for k in range(1, 8):
                v = self.mkt.mf_nav(code, T + timedelta(days=k))
                if v:
                    return T + timedelta(days=k), v
        return None, None

    def allot_mf(self, o, T, upto):
        if T > upto:
            return
        nd, nav = self.nav_date_for(int(o["code"]), T, upto)
        if not nav:
            return
        stamp = r2(o["amount"] * CFG["mfRules"]["stampDuty"])
        net = r2(o["amount"] - stamp)
        units = trunc(net / nav, CFG["mfRules"]["unitDecimals"])
        verified = str(o["code"]) in self.mkt.c["amfi"].get(nd.isoformat(), {})
        append(self.store, "allot", oid=o["oid"], amount=o["amount"], navDate=nd.isoformat(), nav=nav, stamp=stamp, net=net, units=units,
               credit=add_business(T, CFG["mfRules"]["creditBusinessDays"]).isoformat(), verified=verified)

    def fill_etf(self, o, T, upto, res, carry):
        if T > upto:
            return None
        d, px = self.mkt.etf_session_on_or_after(o["sym"], T, upto)
        if not px:
            return None
        budget = r2(o["amount"] + carry.get(o["slot"], 0.0))
        eq = self.mkt.etf_equity(o["sym"])
        n, ch = etf_units_for(budget, px, res, eq)
        gross = r2(n * px)
        ev = append(self.store, "fill", oid=o["oid"], tradeDate=d.isoformat(), price=px, units=n, gross=gross, charges=ch,
                    budget=budget, carry=r2(budget - gross - ch["total"]),
                    credit=add_business(d, CFG["etfFees"]["creditBusinessDays"]).isoformat())
        return ev

    def redeem(self, o, T, upto, acc):
        if T > upto:
            return
        st = replay(self.store["events"])
        a = st[o["acct"]]
        key = str(o.get("code") or o.get("sym"))
        lots = [l for l in a["lots"].get(key, []) if l["units"] > 0]
        have = round(sum(l["units"] for l in lots), 6)
        units = have if o.get("units") in (None, "all") else min(float(o["units"]), have)
        if units <= 0:
            append(self.store, "note", oid=o["oid"], text="nothing to sell")
            return
        if o.get("code"):
            nd, px = self.nav_date_for(int(o["code"]), T, upto)
        else:
            nd, px = self.mkt.etf_session_on_or_after(o["sym"], T, upto)
        if not px:
            return
        gross = r2(units * px)
        f = self.mkt.funds.get(int(o["code"])) if o.get("code") else None
        equity = (f or {}).get("tax") in ("equity", "elss") if f else self.mkt.etf_equity(o["sym"])
        tclass = tax_class(f, o.get("sym"), self.mkt)
        left, gains, exit_load = units, [], 0.0
        for l in lots:
            if left <= 1e-9:
                break
            take = min(left, l["units"])
            cost = l["cost"] * take / l["units"]
            days = (T - D(l["date"])).days
            val = take * px
            if f is not None and days < 365 and not f.get("exitNil"):
                exit_load += val * CFG["mfRules"]["exitLoadIfUnknown"]
            gains.append({"buyDate": l["date"], "units": round(take, 6), "cost": r2(cost), "value": r2(val), "gain": r2(val - cost),
                          "days": days, "term": term_for(tclass, days), "class": tclass})
            left -= take
        if f is not None:
            charges = {"exitLoad": r2(exit_load), "stt": r2(gross * CFG["mfRules"]["sttRedeemEquity"]) if equity else 0.0}
            charges["total"] = r2(sum(charges.values()))
            payout = add_business(nd, 3)
        else:
            charges = etf_charges(gross, "sell", acc["res"], equity)
            payout = add_business(nd, 1)
        tds = 0.0
        if acc["res"] == "nri":
            t = CFG["tax"]
            for g in gains:
                if g["gain"] > 0:
                    rate = t["ltcgEquity"] if g["term"] == "LT" else t["stcgEquity"] if g["term"] == "ST" else t["debtSlab"]
                    tds += g["gain"] * rate * (1 + t["cess"])
        net = r2(gross - charges["total"] - tds)
        append(self.store, "redeem", oid=o["oid"], navDate=nd.isoformat(), price=px, units=round(units, 6), gross=gross,
               charges=charges, tds=r2(tds), net=net, gains=gains, payout=payout.isoformat())

    # annual review — switch only very weak holdings
    def review(self):
        start = D(CFG["start"])
        st = replay(self.store["events"])
        for a in self.accts:
            k = 1
            while True:
                ann = date(start.year + k, start.month, start.day)
                if ann > self.today:
                    break
                T = next_trading(ann)
                rid = f"{a['id']}|review|{T.isoformat()}"
                if any(e.get("rid") == rid for e in self.store["events"] if e["k"] == "review"):
                    k += 1
                    continue
                switches = []
                acct = st.get(a["id"], {"lots": {}})
                plan = self.plan_on(T)
                for key, lots in acct["lots"].items():
                    if sum(l["units"] for l in lots) <= 0:
                        continue
                    bad, why = self.very_weak(a["product"], key)
                    if bad:
                        target = self.model_choice(a, plan, key, st)
                        if target and str(target) != key:
                            switches.append({"from": key, "to": target, "why": why})
                append(self.store, "review", rid=rid, acct=a["id"], T=T.isoformat(), switches=switches)
                for s in switches:
                    oid = f"{rid}|{s['from']}"
                    fld = "code" if a["product"] == "mf" else "sym"
                    frm = int(s["from"]) if a["product"] == "mf" else s["from"]
                    append(self.store, "order", oid=oid + "|out", iid=rid, acct=a["id"], T=T.isoformat(), side="sell",
                           units="all", reason="Annual review: " + s["why"], **{fld: frm})
                    append(self.store, "order", oid=oid + "|in", iid=rid, acct=a["id"], T=add_business(T, 3 if a["product"] == "mf" else 1).isoformat(),
                           side="buy", amount=None, fromOid=oid + "|out", slot="review", label="Review switch",
                           **{fld: (int(s["to"]) if a["product"] == "mf" else s["to"])})
                k += 1

    def very_weak(self, product, key):
        if product == "mf":
            f = self.mkt.funds.get(int(key))
            if not f:
                return True, "fund no longer listed"
            if f.get("status") == "Out of track":
                return True, "VilfinTV status 'Out of track'"
            return False, ""
        e = self.mkt.etfs.get(key)
        if not e:
            return True, "ETF no longer listed"
        if e.get("q") not in ("ok", None):
            return True, "not traded regularly"
        try:
            rt = json.loads((DATA / "etf_extras.json").read_text())["etfs"].get(key, {}).get("rt")
        except Exception:  # noqa: BLE001
            rt = None
        if rt and rt.get("st", 3) <= 1:
            return True, "VilfinTV rating 1 star"
        return False, ""

    def model_choice(self, a, plan, key, st):
        orders = [o for o in st[a["id"]]["orders"] if str(o.get("code") or o.get("sym")) == key and o["side"] == "buy"]
        slot = orders[-1]["slot"] if orders else None
        if a["product"] == "mf":
            return next((s["code"] for s in plan["mf"][a["plan"]] if s["key"] == slot and (s.get("w") or 0) > 0), None)
        return next((x["sym"] for x in plan["etf"][a["plan"]] if x["id"] == slot), None)

    def manual_sells(self):
        for s in CFG.get("sells", []):
            oid = f"{s['acct']}|sell|{s['date']}|{s.get('code') or s.get('sym')}"
            if any(e.get("oid") == oid for e in self.store["events"] if e["k"] == "order") or D(s["date"]) > self.today:
                continue
            append(self.store, "order", oid=oid, iid=oid, acct=s["acct"], T=next_trading(D(s["date"])).isoformat(), side="sell",
                   units=s.get("units", "all"), reason=s.get("reason", "Withdrawal"), withdraw=True,
                   **({"code": int(s["code"])} if s.get("code") else {"sym": s["sym"]}))

    def fund_review_buys(self):
        """Switch-in orders take the proceeds of their sell once it is paid out."""
        st = replay(self.store["events"])
        orders = {o["oid"]: o for a in st.values() for o in a["orders"]}
        for o in orders.values():
            if o.get("fromOid") and o.get("amount") is None and "done" in orders.get(o["fromOid"], {}):
                if not any(e["k"] == "fund" and e["oid"] == o["oid"] for e in self.store["events"]):
                    append(self.store, "fund", oid=o["oid"], amount=orders[o["fromOid"]]["done"]["net"])

    def run(self):
        self.snapshot()
        self.place_orders()
        self.manual_sells()
        self.settle()
        self.review()
        self.settle()                    # review sells
        self.fund_review_buys()
        self.settle()                    # switch-in buys with the sell proceeds
        self.value()

    # valuation, XIRR, benchmark
    def value(self):
        st = replay(self.store["events"])
        funded = {e["oid"]: e["amount"] for e in self.store["events"] if e["k"] == "fund"}
        for a in self.accts:
            s = st.get(a["id"])
            if not s:
                continue
            V, val, pend = self.valuation_date(a), 0.0, 0.0
            for key, lots in s["lots"].items():
                u = sum(l["units"] for l in lots)
                if u <= 0:
                    continue
                px = self.price(a["product"], key, V)
                val += u * (px or 0)
            for o in s["orders"]:
                if "done" not in o and o["side"] == "buy":
                    pend += o["amount"] if o.get("amount") is not None else funded.get(o["oid"], 0.0)
            if a["product"] == "etf":
                val += s["cash"]
            ser = self.store["series"].setdefault(a["id"], [])
            if V < D(CFG["start"]):                  # latest prices predate the first order — nothing to value yet
                ser[:] = [r for r in ser if r[0] >= CFG["start"]]
                continue
            invested = sum(i["amount"] for i in s["inst"])
            bench = self.benchmark(a, s["inst"], V)
            row = [V.isoformat(), r2(invested), r2(val + pend), r2(bench)]
            if ser and ser[-1][0] == row[0]:
                ser[-1] = row
            elif not ser or ser[-1][0] < row[0]:
                ser.append(row)

    def valuation_date(self, a) -> date:
        if self.backtest:
            return self.today
        return min(self.today, D(self.mkt.mf_asof if a["product"] == "mf" else self.mkt.etf_asof))

    def price(self, product, key, V):
        if product == "mf":
            return self.mkt.mf_latest(int(key), V)[1]
        return self.mkt.etf_latest(key, V)[1]

    def benchmark(self, a, inst, V) -> float:
        """Same cash on the same dates into a plain Nifty 50 index fund / ETF, with the same costs."""
        units, cash = 0.0, 0.0
        if a["product"] == "mf":
            code = int(CFG["benchmark"]["mf"])
            for i in inst:
                T = D(i["T"])
                if T > V:
                    cash += i["amount"]
                    continue
                nd, nav = self.nav_date_for(code, T, V)
                if not nav:
                    cash += i["amount"]
                    continue
                units += trunc(r2(i["amount"] - r2(i["amount"] * CFG["mfRules"]["stampDuty"])) / nav, 3)
            return units * (self.mkt.mf_latest(code, V)[1] or 0) + cash
        sym = CFG["benchmark"]["etf"]
        for i in inst:
            T = D(i["T"])
            d, px = self.mkt.etf_session_on_or_after(sym, T, V)
            cash += i["amount"]
            if not px:
                continue
            n, ch = etf_units_for(cash, px, a["res"], True)
            units += n
            cash = r2(cash - n * px - ch["total"])
        return units * (self.mkt.etf_latest(sym, V)[1] or 0) + cash


def tax_class(fund, sym, mkt) -> str:
    """equity · debt (taxed at the slab) · other (12.5% after 24 months: gold / international fund-of-funds and
    non-equity hybrids) · listed (non-equity listed ETFs such as gold / silver / international: 12.5% after 12 months)."""
    if fund is not None:
        t = fund.get("tax")
        return "equity" if t in ("equity", "elss") else "debt" if t == "debt" else "other"
    k = ((mkt.etfs.get(sym) or {}).get("k") or "")
    if mkt.etf_equity(sym):
        return "equity"
    return "debt" if ("Liquid" in k or "Debt" in k) else "listed"


def term_for(tclass: str, days: int) -> str:
    if tclass == "equity":
        return "LT" if days > 365 else "ST"
    if tclass == "listed":
        return "LT" if days > 365 else "slab"
    if tclass == "other":
        return "LT" if days > 730 else "slab"
    return "slab"


def xirr(flows: list[tuple[date, float]]) -> float | None:
    if not flows or not any(v > 0 for _, v in flows) or not any(v < 0 for _, v in flows):
        return None
    t0 = min(d for d, _ in flows)

    def f(r):
        return sum(v / (1 + r) ** ((d - t0).days / 365.0) for d, v in flows)
    lo, hi = -0.9999, 10.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < 1e-7:
            break
        if flo * fm < 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


# ───────────────────────────── views ─────────────────────────────
def build_view(store: dict, eng: Engine) -> dict:
    st = replay(store["events"])
    funded = {e["oid"]: e["amount"] for e in store["events"] if e["k"] == "fund"}
    reviews = [e for e in store["events"] if e["k"] == "review"]
    out = {"v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "start": CFG["start"],
           "config": {k: CFG[k] for k in ("riskNames", "freqNames", "benchmark", "etfFees", "mfRules", "tax", "schedule", "monthly")},
           "mfAsOf": eng.mkt.mf_asof, "etfAsOf": eng.mkt.etf_asof, "accounts": [], "plans": store["plans"],
           "events": len(store["events"]), "head": store["events"][-1]["h"] if store["events"] else None}
    for a in eng.accts:
        s = st.get(a["id"], {"inst": [], "orders": [], "lots": {}, "cash": 0.0, "sells": []})
        V = eng.valuation_date(a)
        today = eng.today
        txns, holdings = [], []
        for o in sorted(s["orders"], key=lambda o: (o["T"], o["oid"])):
            done = o.get("done")
            amount = o["amount"] if o.get("amount") is not None else funded.get(o["oid"])
            row = {"oid": o["oid"], "T": o["T"], "side": o["side"], "code": o.get("code"), "sym": o.get("sym"),
                   "name": o.get("name") or (eng.mkt.funds.get(int(o["code"])) or {}).get("name") if o.get("code") else o.get("name") or o.get("sym"),
                   "slot": o.get("slot"), "label": o.get("label"), "amount": amount, "note": o.get("note") or o.get("reason"), "ref": o.get("ref"),
                   "src": "withdraw" if o.get("withdraw") else "review" if o.get("iid", "").count("|review|") else "plan"}
            if done and done["k"] == "allot":
                row |= {"navDate": done["navDate"], "price": done["nav"], "units": done["units"], "stamp": done["stamp"], "net": done["net"],
                        "credit": done["credit"], "verified": done.get("verified"),
                        "status": "Allotted" if D(done["credit"]) <= today else "Buy in progress"}
            elif done and done["k"] == "fill":
                row |= {"navDate": done["tradeDate"], "price": done["price"], "units": done["units"], "gross": done["gross"],
                        "charges": done["charges"], "budget": done["budget"], "carry": done["carry"], "credit": done["credit"],
                        "status": "Settled" if D(done["credit"]) <= today else "Buy in progress"}
            elif done and done["k"] == "redeem":
                row |= {"navDate": done["navDate"], "price": done["price"], "units": done["units"], "gross": done["gross"],
                        "charges": done["charges"], "tds": done["tds"], "net": done["net"], "gains": done["gains"], "credit": done["payout"],
                        "status": "Paid out" if D(done["payout"]) <= today else "Sell in progress"}
            else:
                row["status"] = ("Order placed — awaiting NAV" if o.get("code") else "Order placed — awaiting close") if D(o["T"]) <= today else "Scheduled"
            txns.append(row)
        for key, lots in s["lots"].items():
            u = round(sum(l["units"] for l in lots), 6)
            if u <= 0:
                continue
            px_d, px = (eng.mkt.mf_latest(int(key), V) if a["product"] == "mf" else eng.mkt.etf_latest(key, V))
            cost = sum(l["cost"] for l in lots)
            credited = round(sum(l["units"] for l in lots if D(l["credit"]) <= today), 6)
            meta = eng.mkt.funds.get(int(key)) if a["product"] == "mf" else eng.mkt.etfs.get(key)
            holdings.append({"key": key, "name": (meta or {}).get("name") or (meta or {}).get("n") or key, "units": u, "credited": credited,
                             "cost": r2(cost), "avg": round(cost / u, 4) if u else None, "price": px, "priceDate": px_d.isoformat() if px_d else None,
                             "value": r2(u * (px or 0)), "gain": r2(u * (px or 0) - cost),
                             "category": (meta or {}).get("sub") if a["product"] == "mf" else (meta or {}).get("k"),
                             "lots": [{"date": l["date"], "units": l["units"], "cost": r2(l["cost"]), "credit": l["credit"]} for l in lots]})
        ser = store["series"].get(a["id"], [])
        last = ser[-1] if ser else None
        flows = [(D(i["T"]), -i["amount"]) for i in s["inst"]]
        flows += [(D(e["payout"]), e["net"]) for e in s["sells"] if e.get("withdraw")]   # switches stay invested
        x = xirr(flows + [(D(last[0]), last[2])]) if last and last[2] > 0 else None
        xb = xirr(flows + [(D(last[0]), last[3])]) if last and last[3] > 0 else None
        days = (D(last[0]) - D(CFG["start"])).days if last else 0
        out["accounts"].append({**a, "riskName": CFG["riskNames"][a["risk"]], "freqName": CFG["freqNames"][a["freq"]],
                                "valuationDate": last[0] if last else None, "invested": last[1] if last else 0, "value": last[2] if last else 0,
                                "benchValue": last[3] if last else 0, "xirr": x, "benchXirr": xb, "days": days,
                                "cash": r2(s["cash"]) if a["product"] == "etf" else None, "carry": s.get("carry", {}),
                                "txns": txns, "holdings": holdings, "series": ser,
                                "reviews": [r for r in reviews if r["acct"] == a["id"]]})
    # price history of everything held or bought (statements for any past date are valued from it)
    keys = {"mf": {str(CFG["benchmark"]["mf"])}, "etf": {CFG["benchmark"]["etf"]}}
    for a in out["accounts"]:
        for t in a["txns"]:
            keys["mf" if t.get("code") else "etf"].add(str(t.get("code") or t.get("sym")))
    out["px"] = {p: {k: dict(sorted((store["prices"].get(p, {}).get(k) or {}).items())) for k in sorted(ks)} for p, ks in keys.items()}
    return out


def scoreboard(view: dict, audit_ok: bool) -> dict:
    """Public strip data: every account with its model, buying schedule and return % only (absolute under one year,
    XIRR after). Accounts not yet valued (before the start date / first allotment) carry ret = None."""
    rows = []
    for a in view["accounts"]:
        valued = bool(a["valuationDate"] and a["invested"] and a["holdings"] and a["valuationDate"] >= view["start"])
        absr = (a["value"] / a["invested"] - 1) * 100 if valued else None
        rows.append({"name": a["name"], "product": a["product"], "risk": a["riskName"], "freq": a["freqName"],
                     "amt": a["amount"], "nri": a["res"] == "nri", "since": view["start"], "days": a["days"] if valued else 0,
                     "metric": "xirr" if valued and a["days"] >= 365 else "abs",
                     "ret": (round((a["xirr"] or 0) * 100, 2) if a["days"] >= 365 else round(absr, 2)) if valued and audit_ok else None})
    # dated by the market data, not the run time — an unchanged scoreboard must not create a new commit every run
    asof = max([a["valuationDate"] for a in view["accounts"] if a.get("valuationDate")] or [min(view.get("mfAsOf") or "", view.get("etfAsOf") or "") or view["start"]])
    return {"v": 2, "updated": asof, "start": view["start"], "auditOk": audit_ok, "rows": rows}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--today")
    ap.add_argument("--view")
    ap.add_argument("--backtest-start")
    ap.add_argument("--no-network", action="store_true")
    args = ap.parse_args()
    if args.backtest_start:
        CFG["start"] = args.backtest_start
    today = D(args.today) if args.today else datetime.now(IST).date()
    p = Path(args.store)
    store = json.loads(p.read_text()) if p.exists() and p.stat().st_size > 2 else {}
    meta = store.setdefault("meta", {"start": CFG["start"], "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    if meta["start"] != CFG["start"]:
        if any(e["k"] != "plan" for e in store.get("events", [])):
            log.error("store starts %s but the config says %s — refusing to mix ledgers", meta["start"], CFG["start"])
            return 2
        log.info("start date moved %s → %s (no orders on record yet)", meta["start"], CFG["start"])
        meta["start"] = CFG["start"]
    eng = Engine(store, today, network=not args.no_network, backtest=bool(args.backtest_start))
    if today < D(CFG["start"]):
        eng.snapshot()
        log.info("before the start date (%s) — plan snapshot only", CFG["start"])
    else:
        eng.run()
    p.write_text(json.dumps(store, separators=(",", ":"), ensure_ascii=False))
    if args.view:
        Path(args.view).write_text(json.dumps(build_view(store, eng), separators=(",", ":"), ensure_ascii=False))
    n = len(store.get("events", []))
    log.info("store: %d events · %d plan snapshots · head %s", n, len(store.get("plans", {})), store["events"][-1]["h"][:12] if n else "-")
    return 0


if __name__ == "__main__":
    sys.exit(main())
