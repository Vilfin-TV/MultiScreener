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
private R2 store (downloaded / uploaded by .github/workflows/sim_ledger.yml). A daily portfolio summary journal
(store["days"], its own hash chain) records every account's value, day change, holdings' moves, look-through exposure
and the day's market moves. Published: data/sim_scoreboard.json and, while the audit passes, data/sim/<person>.json.

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
import re
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
        self.known = store.setdefault("funds", {})         # facts of every fund bought (kept if it is later delisted)
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
        self._info = {}

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

    def fund(self, code: int):
        """Fund facts; for a fund no longer listed, the facts recorded when it was bought (store["funds"])."""
        f = self.funds.get(code)
        if f:
            return f
        k = self.known.get(str(code))
        return dict(k, delisted=True) if k else None

    def remember(self, code: int):
        f = self.funds.get(code)
        if f:
            self.known[str(code)] = {k: f.get(k) for k in ("code", "name", "sub", "tax", "exitNil", "lock", "amc")}

    def exit_rule(self, code: int) -> dict:
        f = self.fund(code) or {}
        if f.get("exitNil"):
            return exit_rule([], True)
        sub = f.get("sub")
        if sub not in self._info:
            try:
                self._info[sub] = {int(k): (v.get("info") or {}).get("exitLoad") for k, v in
                                   json.loads((DATA / "mf" / "d" / f"{sub}.json").read_text()).items()}
            except Exception:  # noqa: BLE001
                self._info[sub] = {}
        return exit_rule(self._info[sub].get(code))

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


class DuplicateEvent(RuntimeError):
    """A second instalment for the same account and date, a repeated order id, or a second completion / funding of
    the same order. Raised before anything is written, so the run stops and nothing is uploaded or published."""


def ev_key(kind: str, data: dict):
    if kind == "instalment":
        return ("instalment", data["acct"], data["T"])
    if kind == "order":
        return ("order", data["oid"])
    if kind in ("allot", "fill", "redeem"):
        return ("done", data["oid"])            # every order completes exactly once
    if kind == "fund":
        return ("fund", data["oid"])
    return None


_KEYS: dict = {}                                # id(store) → (events seen, keys) — rebuilt if the log was replaced


def append(store: dict, kind: str, **data) -> dict:
    evs = store.setdefault("events", [])
    seen = _KEYS.get(id(store))
    if seen is None or seen[0] != len(evs) or seen[2] is not evs:
        keys = {ev_key(e["k"], e) for e in evs} - {None}
        seen = [len(evs), keys, evs]
        _KEYS[id(store)] = seen
    key = ev_key(kind, data)
    if key is not None and key in seen[1]:
        raise DuplicateEvent(f"refusing a duplicate {kind}: {key}")
    ev = {"seq": len(evs) + 1, "k": kind, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "prev": evs[-1]["h"] if evs else "genesis", **data}
    ev["h"] = ev_hash(ev)
    evs.append(ev)
    if key is not None:
        seen[1].add(key)
    seen[0] = len(evs)
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



# ───────────────────────────── exit loads & sale estimates ─────────────────────────────
UNIT = {"day": 1, "month": 365 / 12, "year": 365, "week": 7}
def exit_rule(lines, nil=None):
    """Exit-load lines → {"tiers": [[days, pct], …] (a sale held fewer than `days` days pays `pct` %, first match),
    "days": load-free after, "known": parsed?}. Unreadable terms → a cautious 1% within 365 days."""
    if nil:
        return {"tiers": [], "days": 0, "known": True}
    tiers, seen = {}, False
    for ln in lines or []:
        l = ln.lower().replace("–", "-")
        ps = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", l) if float(x) <= 5]
        if re.search(r"\bnil\b|no exit load|not applicable|0\.0+\s*%|\b0\s*%", l) and not any(p > 0 for p in ps):
            seen = True
            continue
        if not ps or max(ps) <= 0:
            continue
        per = [int(round(float(n) * UNIT[u])) for n, u in re.findall(r"(\d+(?:\.\d+)?)\s*(day|week|month|year)s?\b", l)]
        per += [int(n) for n in re.findall(r"\bday\s*(\d+)\b", l)]
        if not per:
            continue
        seen = True
        if re.search(r"\b(after|beyond|more than|exceeding|onwards|greater than)\b", l) and not re.search(r"within|up ?to|less than|before|on or before|prior|<", l):
            continue
        d = max(per)
        d = 365 if d in (360, 366) else d
        tiers[d] = max(tiers.get(d, 0.0), max(ps))
    if not seen:
        return {"tiers": [[365, 1.0]], "days": 365, "known": False}
    t = sorted([d, p] for d, p in tiers.items())
    return {"tiers": t, "days": t[-1][0] if t else 0, "known": True}

def load_pct(rule, held_days):
    for d, p in rule["tiers"]:
        if held_days < d:
            return p
    return 0.0


LT_DAYS = {"equity": 365, "listed": 365, "other": 730, "debt": 0}


def sale_estimate(lots: list[dict], units: float, px: float, T: date, tclass: str, rule: dict, exempt_left: float) -> dict:
    """FIFO sale of `units` at `px` on T: exit load, gains by term and an estimated resident tax (slab 30% where it
    applies, 4% cess; equity long-term gains above the remaining yearly exemption at 12.5%)."""
    t = CFG["tax"]
    left, load, st, lt, slab, value = units, 0.0, 0.0, 0.0, 0.0, 0.0
    for l in lots:
        if left <= 1e-9:
            break
        take = min(left, l["units"])
        days = (T - D(l["date"])).days
        val, cost = take * px, l["cost"] * take / l["units"]
        load += val * load_pct(rule, days) / 100
        g = val - cost
        term = term_for(tclass, days)
        if term == "LT":
            lt += g
        elif term == "ST":
            st += g
        else:
            slab += g
        value += val
        left -= take
    rate_lt = t["ltcgEquity"]
    lt_taxable = max(0.0, lt - exempt_left) if tclass == "equity" else max(0.0, lt)
    tax = (max(0.0, st) * t["stcgEquity"] + lt_taxable * rate_lt + max(0.0, slab) * t["debtSlab"]) * (1 + t["cess"])
    return {"value": r2(value), "exitLoad": r2(load), "gainST": r2(st), "gainLT": r2(lt), "gainSlab": r2(slab),
            "tax": r2(tax), "cost": r2(load + tax)}


def lot_free(l: dict, T: date, tclass: str, rule: dict, lock_years: int) -> bool:
    """A lot may be sold without exit load, at the long-term rate and outside any lock-in."""
    days = (T - D(l["date"])).days
    long_term = days > LT_DAYS[tclass] if tclass in ("equity", "listed", "other") else True    # long term = MORE than 365 / 730 days
    return long_term and load_pct(rule, days) == 0 and days >= 365 * (lock_years or 0)


def free_from(l: dict, tclass: str, rule: dict, lock_years: int) -> date:
    d0 = D(l["date"])
    return d0 + timedelta(days=max(LT_DAYS.get(tclass, 365) + (1 if tclass in ("equity", "listed", "other") else 0),
                                   rule.get("days") or 0, 365 * (lock_years or 0)))


def person_gains(st: dict, name: str, T: date, skip_iid_tag: str = "") -> dict:
    """Realised equity gains of a person (MF + ETF accounts together) in the financial year of T, by term — the
    yearly LTCG exemption is per person, not per account."""
    fy0 = date(T.year if T.month >= 4 else T.year - 1, 4, 1)
    out = {"lt": 0.0, "st": 0.0, "other": 0.0}
    for aid in (f"{name}-MF", f"{name}-ETF"):
        orders = {o["oid"]: o for o in (st.get(aid) or {}).get("orders", [])}
        for s_ in (st.get(aid) or {}).get("sells", []):
            o = orders.get(s_["oid"]) or {}
            if not (fy0 <= D(o.get("T", s_["payout"])) <= T):
                continue
            if skip_iid_tag and skip_iid_tag in (orders.get(s_["oid"]) or {}).get("iid", ""):
                continue                                   # counted from the harvest plan instead
            for g in s_["gains"]:
                k = "lt" if g["term"] == "LT" and g["class"] == "equity" else "st" if g["term"] == "ST" else "other"
                out[k] += g["gain"]
    return out


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
        plans = self.store["plans"]
        ok = [r for r in plans if plans[r].get("since", r[:10]) <= d.isoformat()]
        best = max(ok, key=lambda r: (plans[r].get("since", r[:10]), r)) if ok else min(plans, key=lambda r: (plans[r].get("since", r[:10]), r))
        return plans[best]

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
            if code not in funds:                                          # no longer listed → the model's next listed alternate
                alt = next((c for c in (s["src"].get("alts") or []) if funds.get(c)), None)
                if alt:
                    note.append("fund no longer listed — bought the model's alternate")
                    code, f = alt, funds[alt]
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
            self.mkt.remember(code)
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
        f = self.mkt.fund(code) or {}
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
        ev = append(self.store, "fill", oid=o["oid"], tradeDate=d.isoformat(), price=px, rule=CFG["etfRules"]["id"],
                    priceTime=CFG["etfRules"]["priceTime"], units=n, gross=gross, charges=ch,
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
            if not px and int(o["code"]) not in self.mkt.funds and (upto - T).days >= 3:
                nd, px = self.mkt.mf_latest(int(o["code"]), T)       # wound up / merged: last official NAV
        else:
            nd, px = self.mkt.etf_session_on_or_after(o["sym"], T, upto)
        if not px:
            return
        gross = r2(units * px)
        f = self.mkt.fund(int(o["code"])) if o.get("code") else None
        equity = (f or {}).get("tax") in ("equity", "elss") if f else self.mkt.etf_equity(o["sym"])
        tclass = tax_class(f, o.get("sym"), self.mkt)
        rule = self.mkt.exit_rule(int(o["code"])) if f is not None else {"tiers": [], "days": 0, "known": True}
        left, gains, exit_load = units, [], 0.0
        for l in lots:
            if left <= 1e-9:
                break
            take = min(left, l["units"])
            cost = l["cost"] * take / l["units"]
            days = (T - D(l["date"])).days
            val = take * px
            if f is not None:
                exit_load += val * load_pct(rule, days) / 100
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
               charges=charges, tds=r2(tds), net=net, gains=gains, payout=payout.isoformat(),
               exitRule=rule["tiers"] if f is not None else None,
               **({} if o.get("code") else {"rule": CFG["etfRules"]["id"], "priceTime": CFG["etfRules"]["priceTime"]}))

    # monthly sell review — tax- and exit-load-aware (CFG["sellRules"]); the agents follow it exactly
    def review_dates(self) -> list[date]:
        start, sc = D(CFG["start"]), CFG["schedule"]
        out, y, m = [], start.year, start.month
        while True:
            m += 1
            if m > 12:
                y, m = y + 1, 1
            T = next_trading(date(y, m, min(sc["anchorDay"], 28)))
            if T > self.today:
                return out
            out.append(T)

    def slot_of(self, acct_state: dict, key: str):
        buys = [o for o in acct_state["orders"] if str(o.get("code") or o.get("sym")) == key and o["side"] == "buy"]
        return buys[-1].get("slot") if buys else None

    def in_model(self, a, plan, key, slot) -> bool:
        """Still the model's choice for the holding's own role (its slot: the fund, an alternate or the amount upgrade);
        a holding whose slot no longer exists counts only if it is some slot's main choice."""
        if a["product"] == "mf":
            slots = plan["mf"][a["plan"]]
            own = [sl for sl in slots if sl["key"] == slot]
            if own:
                sl = own[0]
                ids = {str(sl["code"])} | {str(c) for c in (sl.get("alts") or [])} | ({str(sl["upgrade"]["code"])} if sl.get("upgrade") else set())
                return key in ids
            return any(str(sl["code"]) == key for sl in slots)
        own = [x for x in plan["etf"][a["plan"]] if x["id"] == slot]
        return own[0]["sym"] == key if own else any(x["sym"] == key for x in plan["etf"][a["plan"]])

    def target_for(self, a, plan, slot, key):
        """Where the proceeds go: the model's current choice for the holding's role — or, when that is the holding
        itself (no longer listed), the role's first listed alternate; else the largest other role. Never None for
        mutual funds (an MF account holds no cash)."""
        if a["product"] == "mf":
            slots = plan["mf"][a["plan"]]
            own = [x for x in slots if x["key"] == slot]
            rest = sorted([x for x in slots if x["key"] != slot], key=lambda x: -(x.get("w") or 0))
            for sl in own + rest:
                for c in [sl["code"]] + list(sl.get("alts") or []):
                    if str(c) != key and int(c) in self.mkt.funds:
                        return c
            return None
        slots = plan["etf"][a["plan"]]
        own = [x for x in slots if x["id"] == slot]
        rest = sorted([x for x in slots if x["id"] != slot], key=lambda x: -x["w"])
        return next((x["sym"] for x in own + rest if x["sym"] != key and x["sym"] in self.mkt.etfs), None)

    def assess(self, a, key, plan, slot):
        """'severe' (no longer listed) · 'weak' (no longer the model's choice) · 'ok'."""
        if a["product"] == "mf":
            if int(key) not in self.mkt.funds:
                return "severe", "fund no longer listed (merged or wound up)"
        elif key not in self.mkt.etfs:
            return "severe", "ETF no longer listed"
        if not self.in_model(a, plan, key, slot):
            return "weak", "no longer the model portfolio's choice for this role"
        return "ok", ""

    def review(self):
        R = CFG["sellRules"]
        start = D(CFG["start"])
        m = start.month - 1 + R["minHoldMonths"]
        first_year_end = date(start.year + m // 12, m % 12 + 1, min(start.day, 28))
        done = {e["rid"] for e in self.store["events"] if e["k"] == "review"}
        for a in self.accts:
            prev = []                                            # this account's earlier reviews (for streaks)
            for T in self.review_dates():
                rid = f"{a['id']}|review|{T.isoformat()}"
                if rid in done:
                    prev.append(next(e for e in self.store["events"] if e["k"] == "review" and e["rid"] == rid))
                    continue
                st = replay(self.store["events"])
                acct = st.get(a["id"])
                if not acct:
                    continue
                plan = self.plan_on(T)
                exempt_left = max(0.0, CFG["tax"]["ltcgExempt"] - person_gains(st, a["name"], T)["lt"])
                items, sells = [], []
                for key, lots in acct["lots"].items():
                    lots = [l for l in lots if l["units"] > 1e-9 and D(l["date"]) <= T]
                    units = round(sum(l["units"] for l in lots), 6)
                    if units <= 0 or any(o.get("side") == "sell" and str(o.get("code") or o.get("sym")) == key and "done" not in o
                                         for o in acct["orders"]):
                        continue
                    slot = self.slot_of(acct, key)
                    level, why = self.assess(a, key, plan, slot)
                    streak, flagged = 0, [T]
                    for e in reversed(prev):
                        it = next((x for x in e.get("items", []) if x["key"] == key), None)
                        if it and it["level"] in ("weak", "severe"):
                            streak += 1
                            flagged.append(D(e["T"]))
                        else:
                            break
                    streak = streak + 1 if level != "ok" else 0
                    flagged = sorted(flagged)
                    f = self.mkt.fund(int(key)) if a["product"] == "mf" else None
                    tclass = tax_class(f, None if f else key, self.mkt) if (f or a["product"] == "etf") else "equity"
                    rule = self.mkt.exit_rule(int(key)) if a["product"] == "mf" else {"tiers": [], "days": 0, "known": True}
                    lock = int((f or {}).get("lock") or 0)
                    px = self.price(a["product"], key, min(T, self.valuation_date(a))) or lots[-1]["price"]
                    item = {"key": key, "slot": slot, "level": level, "why": why, "streak": streak, "units": units,
                            "tclass": tclass, "exitDays": rule.get("days"), "lock": lock}
                    if level == "ok":
                        item["action"] = "hold"
                    elif level == "weak" and streak < R["droppedStreak"]:
                        item["action"] = "watch"
                        item["note"] = f"flagged {streak} of {R['droppedStreak']} reviews needed before selling"
                    else:
                        free = [l for l in lots if (T - D(l["date"])).days >= 365 * lock] if level == "severe" else []
                        if level == "severe":
                            sell_lots = []
                            for l in lots:                                      # FIFO; stop at the first locked lot
                                if (T - D(l["date"])).days < 365 * lock:
                                    break
                                sell_lots.append(l)
                            why_now = "severe: sold whatever the tax / exit load"
                        elif T < first_year_end:
                            sell_lots, why_now = [], "no non-urgent sales in the account's first year"
                        else:
                            # the deferral clock starts when a sale first became allowed (confirmed flag, after year one)
                            allowed = max(flagged[min(R["droppedStreak"] - 1, len(flagged) - 1)], first_year_end)
                            deferred = (T - allowed).days >= R["deferMaxMonths"] * 365 / 12 - 3
                            sell_lots = []
                            for l in lots:
                                if deferred or lot_free(l, T, tclass, rule, lock):
                                    sell_lots.append(l)
                                else:
                                    break
                            why_now = "deferral limit reached — sold now" if deferred else "lots free of exit load and short-term tax"
                            if sell_lots and not deferred and tclass == "equity" and T.month in R["harvestMonths"]:
                                keep, gain = [], 0.0
                                for l in sell_lots:                             # stay within the yearly LTCG exemption
                                    g = l["units"] * px - l["cost"]
                                    if gain + max(g, 0) > exempt_left and keep:
                                        break
                                    keep.append(l)
                                    gain += max(g, 0)
                                if len(keep) < len(sell_lots):
                                    why_now = "Jan–Mar: long-term gains kept within this year's exemption; the rest after 1 April"
                                sell_lots = keep
                        sell_units = round(sum(l["units"] for l in sell_lots), 6)
                        if a["product"] == "etf":
                            sell_units = int(sell_units)
                        rest = [l for l in lots[len(sell_lots):]]
                        item["estNow"] = sale_estimate(lots, units, px, T, tclass, rule, exempt_left)
                        if rest and level == "weak":
                            nxt = max(free_from(rest[0], tclass, rule, lock), first_year_end)
                            item["waitUntil"] = nxt.isoformat()
                            item["estAtWait"] = sale_estimate(lots, units, px, nxt, tclass, rule, CFG["tax"]["ltcgExempt"])
                        if sell_units > 0:
                            target = self.target_for(a, plan, slot, key)
                            item.update(action="sell", sellUnits=sell_units, to=target, note=why_now)
                            sells.append((key, sell_units, target, why, level, slot))
                        else:
                            item.update(action="wait", note=why_now)
                    items.append(item)
                ev = append(self.store, "review", rid=rid, acct=a["id"], T=T.isoformat(), items=items,
                            switches=[{"from": k, "to": t, "units": u, "why": w, "level": lv} for k, u, t, w, lv, _ in sells])
                prev.append(ev)
                for key, u, target, why, level, slot in sells:
                    oid = f"{rid}|{key}"
                    fld = "code" if a["product"] == "mf" else "sym"
                    frm = int(key) if a["product"] == "mf" else key
                    append(self.store, "order", oid=oid + "|out", iid=rid, acct=a["id"], T=T.isoformat(), side="sell",
                           units=u, level=level, reason=f"Sell review ({level}): {why}", **{fld: frm})
                    if target:
                        append(self.store, "order", oid=oid + "|in", iid=rid, acct=a["id"],
                               T=add_business(T, 3 if a["product"] == "mf" else 1).isoformat(), side="buy", amount=None,
                               fromOid=oid + "|out", slot=slot or "review", label="Review switch",
                               **{fld: (int(target) if a["product"] == "mf" else target)})
                if sells:                                # carry out what the prices on file allow before the next review
                    self.settle()
                    self.fund_review_buys()
                    self.settle()

    # yearly tax harvesting (CFG["taxHarvest"]) — per person, MF account first
    def harvest(self):
        H, t = CFG["taxHarvest"], CFG["tax"]
        start = D(CFG["start"])
        done = {e["rid"] for e in self.store["events"] if e["k"] == "harvest"}
        for y in range(start.year, self.today.year + 1):
            T = next_trading(date(y, H["month"], H["day"]))
            if T < start or T > self.today:
                continue
            for name in dict.fromkeys(a["name"] for a in self.accts):
                for a in [x for x in self.accts if x["name"] == name]:
                    rid = f"{a['id']}|harvest|{T.isoformat()}"
                    if rid in done:
                        continue
                    st = replay(self.store["events"])
                    acct = st.get(a["id"])
                    if not acct:
                        continue
                    pg = person_gains(st, name, T, skip_iid_tag=f"|harvest|{T.isoformat()}")
                    planned = sum(it["gain"] for e in self.store["events"] if e["k"] == "harvest" and e["T"] == T.isoformat()
                                  and e["acct"].rsplit("-", 1)[0] == name for it in e["items"]
                                  if it["action"] == "harvest" and it["mode"] == "gain")
                    room = max(0.0, t["ltcgExempt"] - pg["lt"] - planned)  # unused exemption this year (both accounts)
                    taxable = max(0.0, pg["lt"] - t["ltcgExempt"]) + max(0.0, pg["st"])
                    items, sells = [], []
                    for key, lots in acct["lots"].items():
                        lots = [l for l in lots if l["units"] > 1e-9 and D(l["date"]) <= T]
                        if not lots or any(o.get("side") == "sell" and str(o.get("code") or o.get("sym")) == key and "done" not in o
                                           for o in acct["orders"]):
                            continue
                        f = self.mkt.fund(int(key)) if a["product"] == "mf" else None
                        if a["product"] == "mf" and not f:
                            continue
                        tclass = tax_class(f, None if f else key, self.mkt)
                        if tclass != "equity":
                            continue
                        rule = self.mkt.exit_rule(int(key)) if f else {"tiers": [], "days": 0, "known": True}
                        lock = int((f or {}).get("lock") or 0)
                        px = self.price(a["product"], key, min(T, self.valuation_date(a)))
                        if not px:
                            continue
                        units, gain, mode = 0.0, 0.0, None
                        # gain harvesting: long-term lots (FIFO) into the unused exemption
                        for l in lots:
                            if not lot_free(l, T, tclass, rule, lock) or room - gain <= 0:
                                break
                            gpu = px - l["cost"] / l["units"]
                            take = l["units"] if gpu <= 0 else min(l["units"], (room - gain) / gpu)
                            take = int(take) if a["product"] == "etf" else math.floor(take * 1000) / 1000
                            if take <= 0:
                                break
                            units += take
                            gain += take * gpu
                            mode = "gain"
                            if take < l["units"]:
                                break
                        # loss harvesting: only against taxable gains already realised this year
                        if mode == "gain" and gain < H["minGain"]:
                            units, gain, mode = 0.0, 0.0, None            # FIFO reached loss lots first — nothing worth booking
                        if mode is None and taxable > 0:
                            loss, units = 0.0, 0.0
                            for l in lots:
                                gpu = px - l["cost"] / l["units"]
                                if gpu >= 0 or (T - D(l["date"])).days < 365 * lock or load_pct(rule, (T - D(l["date"])).days) > 0:
                                    break
                                take = l["units"] if a["product"] == "mf" else int(l["units"])
                                units += take
                                loss += take * gpu
                                if -loss >= taxable:
                                    break
                            if units > 0:
                                gain, mode = loss, "loss"
                        if not mode or units <= 0:
                            continue
                        value = units * px
                        if a["product"] == "mf":
                            cost = value * (CFG["mfRules"]["sttRedeemEquity"] + CFG["mfRules"]["stampDuty"])
                        else:
                            cost = etf_charges(value, "sell", a["res"], True)["total"] + etf_charges(value, "buy", a["res"], True)["total"]
                        # gain mode: 12.5% (+cess) saved later on gains moved into this year's exemption; loss mode: tax on the
                        # realised gains the booked loss offsets (at the long-term rate — the lower one, to stay conservative)
                        saving = max(gain, 0) * t["ltcgEquity"] * (1 + t["cess"]) if mode == "gain" else min(-gain, taxable) * t["ltcgEquity"] * (1 + t["cess"])
                        ok = abs(gain) >= H["minGain"] and saving > cost
                        items.append({"key": key, "mode": mode, "units": round(units, 6), "gain": r2(gain), "saving": r2(saving),
                                      "cost": r2(cost), "action": "harvest" if ok else "skip",
                                      "note": ("long-term gains booked within the unused exemption and bought back" if mode == "gain"
                                               else "losses booked against this year's taxable gains and bought back") if ok
                                      else "saving does not beat the round-trip costs / too small"})
                        if ok:
                            sells.append((key, units, mode, gain))
                            if mode == "gain":
                                room -= max(gain, 0)
                            else:
                                taxable = max(0.0, taxable + gain)
                    append(self.store, "harvest", rid=rid, acct=a["id"], T=T.isoformat(), items=items,
                           exemptLeft=r2(max(0.0, t["ltcgExempt"] - pg["lt"] - planned)))
                    for key, u, mode, gain in sells:
                        oid = f"{rid}|{key}"
                        fld = "code" if a["product"] == "mf" else "sym"
                        k = int(key) if a["product"] == "mf" else key
                        slot = self.slot_of(acct, key)
                        append(self.store, "order", oid=oid + "|out", iid=rid, acct=a["id"], T=T.isoformat(), side="sell",
                               units=round(u, 6), level="harvest", reason=f"Tax harvesting ({mode}s)", **{fld: k})
                        append(self.store, "order", oid=oid + "|in", iid=rid, acct=a["id"],
                               T=add_business(T, 3 if a["product"] == "mf" else 1).isoformat(), side="buy", amount=None,
                               fromOid=oid + "|out", slot=slot or "harvest", label="Tax harvesting buy-back", **{fld: k})
                    if sells:
                        self.settle()
                        self.fund_review_buys()
                        self.settle()

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
        self.harvest()
        self.settle()                    # review / harvest sells
        self.fund_review_buys()
        self.settle()                    # switch-in buys with the sell proceeds
        self.value()
        self.journal()

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
            for o in s["orders"]:                    # ETF money waiting for a fill is still in the account's cash
                if "done" not in o and o["side"] == "buy" and a["product"] == "mf":
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

    # ───────────── daily portfolio summary journal ─────────────
    def prev_price(self, product, key, pd: date):
        """The official price before pd (previous NAV / previous session close) — the base of the day's move."""
        if product == "mf":
            if self.backtest:
                return self.mkt.mf_latest(int(key), pd - timedelta(days=1))
            ds = [d for d in self.mkt.mf_dates(int(key)) if d < pd.isoformat()]
            return (D(ds[-1]), self.mkt.c["mf"][str(key)][ds[-1]]) if ds else (None, None)
        return self.mkt.etf_latest(key, pd - timedelta(days=1))

    def bench_at(self, a, inst, d: date) -> float:
        """Same cash on the same dates into the Nifty 50 index fund / ETF, with the same costs and the same credit
        rule as the account (units count at what was paid until they are credited)."""
        units, cash = 0.0, 0.0
        if a["product"] == "mf":
            code = int(CFG["benchmark"]["mf"])
            for i in inst:
                T = D(i["T"])
                nd, nav = self.nav_date_for(code, T, d)
                if not nav:
                    cash += i["amount"]
                    continue
                u = trunc(r2(i["amount"] - r2(i["amount"] * CFG["mfRules"]["stampDuty"])) / nav, 3)
                if add_business(T, CFG["mfRules"]["creditBusinessDays"]) <= d:
                    units += u
                else:
                    cash += i["amount"]
            return units * (self.mkt.mf_latest(code, d)[1] or 0) + cash
        sym, pend = CFG["benchmark"]["etf"], 0.0
        for i in inst:
            sd, px = self.mkt.etf_session_on_or_after(sym, D(i["T"]), d)
            cash += i["amount"]
            if not px:
                continue
            n, ch = etf_units_for(cash, px, a["res"], True)
            cash = r2(cash - n * px - ch["total"])
            if add_business(sd, CFG["etfFees"]["creditBusinessDays"]) <= d:
                units += n
            else:
                pend += n * px + ch["total"]
        return units * (self.mkt.etf_latest(sym, d)[1] or 0) + pend + cash

    def lookthrough(self, a, key: str) -> str:
        """The fund's / ETF's composition from its latest monthly portfolio (all sectors, top stocks) and its asset
        label, recorded once per portfolio month in store["lookthrough"]; returns that month (the daily record keeps
        only this reference, so any day's exposure can be recomputed exactly)."""
        cache = self.__dict__.setdefault("_pfc", {})
        if a["product"] == "mf":
            f = self.mkt.fund(int(key)) or {}
            kind = f.get("sub") or ""
            if kind not in cache:
                try:
                    cache[kind] = json.loads((DATA / "mf" / "p" / f"{kind}.json").read_text()) if kind else {}
                except Exception:  # noqa: BLE001
                    cache[kind] = {}
            pf = cache[kind].get(str(key))
        else:
            kind = ((self.mkt.etfs.get(key) or {}).get("k") or "")
            if "_etf" not in cache:
                try:
                    cache["_etf"] = json.loads((DATA / "etf_holdings.json").read_text()).get("etfs", {})
                except Exception:  # noqa: BLE001
                    cache["_etf"] = {}
            pf = cache["_etf"].get(key)
        lk = kind.lower()
        label = ("Gold" if "gold" in lk else "Silver" if "silver" in lk
                 else "International" if any(x in lk for x in ("international", "global", "us", "asia", "nasdaq"))
                 else "Debt & cash" if any(x in lk for x in ("liquid", "debt", "gilt", "bond", "floater", "money", "overnight", "duration", "credit", "arbitrage")) else None)
        month = (pf or {}).get("asOf") or "none"
        book = self.store.setdefault("lookthrough", {}).setdefault(f"{a['product']}:{key}", {})
        if month not in book:
            book[month] = {"asset": label,
                           "sec": [[n.strip(), p] for n, p in (pf or {}).get("sectors") or [] if isinstance(n, str) and any(c.isalpha() for c in n) and n not in ("N.A.", "Others")],
                           "stk": [[t[0], t[2]] for t in (pf or {}).get("top") or [] if len(t) > 4 and t[4] == "equity"]}
        return month

    def journal(self):
        """One summary per account per market day (from the first day it holds credited units) and one record of the
        day's market moves, appended to store["days"] — a hash chain of its own, never rewritten. Each account
        summary is computed from the ledger as of that day and the official prices kept in the store, so the audit
        can recompute it; missed days are filled in order on the next run."""
        days = self.store.setdefault("days", [])
        last = {}
        self._lastlt = {}                    # look-through month references are stored only when they change
        for e in days:
            last[e.get("a") or "mkt"] = e
            if "lt" in e:
                self._lastlt[e["a"]] = e["lt"]
        evs = self.store["events"]
        odate = {e["oid"]: e["T"] for e in evs if e["k"] == "order"}

        def eff(e):
            return e.get("T") if e["k"] in ("instalment", "order") else odate.get(e.get("oid")) if e["k"] in ("allot", "fill", "redeem") else None
        Vmax = max(self.valuation_date(a) for a in self.accts)
        d0 = D(CFG["start"])
        d = min(D(last[k]["d"]) + timedelta(days=1) if k in last else d0 for k in ["mkt"] + [a["id"] for a in self.accts])
        while d <= Vmax:
            if not is_trading(d):
                d += timedelta(days=1)
                continue
            ds = d.isoformat()
            if d <= D(self.mkt.etf_asof) or self.backtest:
                lm = last.get("mkt")
                if not lm or lm["d"] < ds:
                    m = []
                    for sym, _ in CFG["daily"]["market"]:
                        pd, px = self.mkt.etf_latest(sym, d)
                        if pd != d or not px:
                            continue
                        qd, qx = self.prev_price("etf", sym, d)
                        if qx:
                            m.append([sym, px, ds, qx, qd.isoformat()])
                    if m:
                        last["mkt"] = self._day(days, {"t": "mkt", "d": ds, "m": m})
            st = None
            for a in self.accts:
                le = last.get(a["id"])
                if (le and le["d"] >= ds) or d > self.valuation_date(a):
                    continue
                if st is None:
                    st = replay([e for e in evs if (eff(e) or "9999") <= ds])
                e = self.day_entry(a, st.get(a["id"]), d, le, evs, odate)
                if e:
                    last[a["id"]] = self._day(days, e)
            d += timedelta(days=1)

    @staticmethod
    def _day(days: list, e: dict) -> dict:
        e = {"seq": len(days) + 1, **e, "prev": days[-1]["h"] if days else "genesis"}
        e["h"] = ev_hash(e)
        days.append(e)
        return e

    def day_entry(self, a, s, d: date, prev, evs, odate):
        if not s:
            return None
        ds, mf = d.isoformat(), a["product"] == "mf"
        hold, cred_any, val = [], False, 0.0
        for key, lots in sorted(s["lots"].items()):
            lots = [l for l in lots if l["units"] > 1e-9]
            if not lots:
                continue
            cu = round(sum(l["units"] for l in lots if D(l["credit"]) <= d), 6)
            uc = r2(sum(l["cost"] for l in lots if D(l["credit"]) > d))
            pd, px = (self.mkt.mf_latest(int(key), d) if mf else self.mkt.etf_latest(key, d))
            qd, qx = self.prev_price(a["product"], key, pd) if pd else (None, None)
            hv = r2(cu * (px or 0) + uc)
            if cu > 0 and not px:
                return None                  # no official price on record for a credited holding — no summary that day
            cred_any = cred_any or cu > 0
            hold.append([key, cu, px, pd.isoformat() if pd else None, qx, qd.isoformat() if qd else None, hv, uc])
            val += hv
        if not cred_any:
            return None
        pend = 0.0
        if mf:
            funded = {e["oid"]: e["amount"] for e in evs if e["k"] == "fund"}
            for o in s["orders"]:
                if "done" not in o and o["side"] == "buy":
                    pend += o["amount"] if o.get("amount") is not None else funded.get(o["oid"], 0.0)
        cash = r2(s["cash"]) if not mf else 0.0
        val = r2(val + pend + cash)
        inv = r2(sum(i["amount"] for i in s["inst"]))
        out = r2(sum(x["net"] for x in s["sells"] if x.get("withdraw")))
        bval = r2(self.bench_at(a, s["inst"], d))
        # per-holding change: value now − value at the last summary − money added + sale proceeds
        ph = {h[0]: h for h in (prev or {}).get("hold", [])}
        pdate = prev["d"] if prev else "0000"
        added, sold = {}, {}
        for o in s["orders"]:
            if not (pdate < o["T"] <= ds) or "done" not in o:
                continue
            k = str(o.get("code") or o.get("sym"))
            dn = o["done"]
            if o["side"] == "buy":
                added[k] = added.get(k, 0) + (dn["amount"] if dn["k"] == "allot" else dn["gross"] + dn["charges"]["total"])
            else:
                sold[k] = sold.get(k, 0) + dn["gross"]
        for h in hold:
            base = ph[h[0]][6] if h[0] in ph else 0.0
            if prev:
                h.append(r2(h[6] - base - added.get(h[0], 0) + sold.get(h[0], 0)))
            else:
                h.append(r2(h[6] - sum(l["cost"] for l in s["lots"][h[0]] if l["units"] > 1e-9)))
        if prev:
            flow = (inv - prev["inv"]) - (out - prev["out"])
            chg, bchg = r2(val - prev["val"] - flow), r2(bval - prev["bval"] - flow)
            pct = round(chg / prev["val"] * 100, 4) if prev["val"] else 0.0
            bpct = round(bchg / prev["bval"] * 100, 4) if prev["bval"] else 0.0
        else:
            net = inv - out
            chg, bchg = r2(val - net), r2(bval - net)
            pct = round(chg / net * 100, 4) if net else 0.0
            bpct = round(bchg / net * 100, 4) if net else 0.0
        e = {"t": "acct", "d": ds, "a": a["id"], "inv": inv, "out": out, "val": val, "cash": cash, "pend": r2(pend),
             "chg": chg, "pct": pct, "bval": bval, "bchg": bchg, "bpct": bpct, "first": not prev,
             "hold": hold}
        lt = {h[0]: self.lookthrough(a, h[0]) for h in hold if h[1] > 0}
        if lt != self._lastlt.get(a["id"]):
            e["lt"] = self._lastlt[a["id"]] = lt
        return e


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
    harvests = [e for e in store["events"] if e["k"] == "harvest"]
    out = {"v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "start": CFG["start"],
           "today": eng.today.isoformat(),
           "config": {k: CFG[k] for k in ("riskNames", "freqNames", "benchmark", "etfFees", "mfRules", "tax", "schedule", "monthly", "sellRules", "taxHarvest")},
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
                row |= {"navDate": done["tradeDate"], "price": done["price"], "rule": done.get("rule") or CFG["etfRules"]["id"],
                        "priceTime": done.get("priceTime") or CFG["etfRules"]["priceTime"], "units": done["units"], "gross": done["gross"],
                        "charges": done["charges"], "budget": done["budget"], "carry": done["carry"], "credit": done["credit"],
                        "status": "Settled" if D(done["credit"]) <= today else "Buy in progress"}
            elif done and done["k"] == "redeem":
                row |= {"navDate": done["navDate"], "price": done["price"], "units": done["units"], "gross": done["gross"],
                        **({} if o.get("code") else {"rule": done.get("rule") or CFG["etfRules"]["id"],
                                                     "priceTime": done.get("priceTime") or CFG["etfRules"]["priceTime"]}),
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
                                "reviews": [r for r in reviews if r["acct"] == a["id"]],
                                "harvests": [h for h in harvests if h["acct"] == a["id"]]})
    # price history of everything held or bought (statements for any past date are valued from it)
    keys = {"mf": {str(CFG["benchmark"]["mf"])}, "etf": {CFG["benchmark"]["etf"]}}
    for a in out["accounts"]:
        for t in a["txns"]:
            keys["mf" if t.get("code") else "etf"].add(str(t.get("code") or t.get("sym")))
    out["px"] = {p: {k: dict(sorted((store["prices"].get(p, {}).get(k) or {}).items())) for k in sorted(ks)} for p, ks in keys.items()}
    return out


def account_detail(a: dict, valued: bool, sub_names: dict, today: date) -> dict:
    """Per-account summary for the public card (only when the audit passed): what is held, units, average cost, latest
    official price, value and gain, orders still waiting for their price, and the next scheduled buy. Full transaction
    history, cash ledger and statements stay on the private page."""
    mf = a["product"] == "mf"
    tot = sum(h["value"] for h in a["holdings"]) or 0
    hold = []
    for h in sorted(a["holdings"], key=lambda h: -h["value"]):
        hold.append({"n": h["name"], "k": h["key"], "cat": (sub_names.get(h["category"]) or h["category"]) if mf else h["category"],
                     "u": h["units"], "avg": h["avg"], "px": h["price"], "pd": h["priceDate"], "val": h["value"],
                     "g": round((h["value"] / h["cost"] - 1) * 100, 2) if h["cost"] and h["credited"] > 0 else None,
                     "w": round(h["value"] / tot * 100, 1) if tot else None,
                     "pu": round(h["units"] - h["credited"], 6) if h["credited"] < h["units"] - 1e-9 else 0,
                     "cr": max((l["credit"] for l in h.get("lots", []) if D(l["credit"]) > today), default=None)})
    pend = [{"n": t["name"], "amt": t["amount"], "T": t["T"], "st": t["status"]} for t in a["txns"]
            if t["side"] == "buy" and t.get("units") is None and t.get("amount")]
    nxt = None
    try:
        nxt = next((d2.isoformat() for _, d2 in schedule(a["freq"], today + timedelta(days=400)) if d2 > today), None)
    except Exception:  # noqa: BLE001
        pass
    out = {"inv": r2(a["invested"]), "val": r2(a["value"]) if valued else None, "gain": r2(a["value"] - a["invested"]) if valued else None,
           "bench": round((a["benchValue"] / a["invested"] - 1) * 100, 2) if valued and a.get("benchValue") else None,
           "asOf": a["valuationDate"], "next": nxt, "hold": hold, "pend": pend[:12]}
    if not mf:
        out["cash"] = a.get("cash")
    return out


def scoreboard(view: dict, audit_ok: bool) -> dict:
    """Public strip data: every account with its model, buying schedule and return % only (absolute under one year,
    XIRR after). Accounts not yet valued (before the start date / first allotment) carry ret = None."""
    rows = []
    try:
        sub_names = {k: v[1] for k, v in json.loads((DATA / "mf" / "screener.json").read_text())["subs"].items()}
    except Exception:  # noqa: BLE001
        sub_names = {}
    for a in view["accounts"]:
        # units are only owned once credited (MF T+2, ETF T+1, exchange holidays skipped): until then a lot counts at
        # what was paid for it (no gain or loss), and an account with nothing credited yet shows no return at all
        today = D(view["today"]) if view.get("today") else datetime.now(IST).date()
        pend_lots = [(h, l) for h in a["holdings"] for l in h.get("lots", []) if D(l["credit"]) > today]
        pend_val = sum(l["units"] * (h["price"] or 0) for h, l in pend_lots)
        pend_cost = sum(l["cost"] for _, l in pend_lots)
        credit_by = max((l["credit"] for _, l in pend_lots), default=None)
        any_credited = any(h["credited"] > 0 for h in a["holdings"])
        valued = bool(a["valuationDate"] and a["invested"] and any_credited and a["valuationDate"] >= view["start"])
        value = a["value"] - pend_val + pend_cost
        absr = (value / a["invested"] - 1) * 100 if valued else None
        row = {"name": a["name"], "product": a["product"], "risk": a["riskName"], "freq": a["freqName"],
               "amt": a["amount"], "nri": a["res"] == "nri", "since": view["start"], "days": a["days"] if valued else 0,
               "metric": "xirr" if valued and a["days"] >= 365 else "abs",
               "ret": (round((a["xirr"] or 0) * 100, 2) if a["days"] >= 365 else round(absr, 2)) if valued and audit_ok else None}
        if credit_by:
            row["credit"] = credit_by
        if audit_ok:
            row["detail"] = account_detail({**a, "value": value}, valued, sub_names, today)
        rows.append(row)
    # dated by the market data, not the run time — an unchanged scoreboard must not create a new commit every run
    asof = max([a["valuationDate"] for a in view["accounts"] if a.get("valuationDate")] or [min(view.get("mfAsOf") or "", view.get("etfAsOf") or "") or view["start"]])
    return {"v": 4, "updated": asof, "start": view["start"], "auditOk": audit_ok, "rows": rows}


def exposure_from(product: str, hold: list, lt: dict, book: dict) -> dict:
    """Look-through exposure (% of the portfolio) of a daily record: credited holdings' values × each one's recorded
    composition (store["lookthrough"]) — top sectors with their market tracker, top stocks and non-equity shares."""
    vals = {h[0]: h[1] * (h[2] or 0) for h in hold if h[1] > 0}
    tot = sum(vals.values())
    if tot <= 0:
        return {}
    sec, stk, asset, months = {}, {}, {}, set()
    for key, v in vals.items():
        m = lt.get(key)
        comp = (book.get(f"{product}:{key}") or {}).get(m) or {}
        w = v / tot * 100
        if m and m != "none":
            months.add(m)
        if comp.get("asset"):
            asset[comp["asset"]] = asset.get(comp["asset"], 0) + w
        for n, pct in comp.get("sec", []):
            k = n.lower()
            sec[k] = (sec.get(k, (n, 0))[0], sec.get(k, (n, 0))[1] + w * pct / 100)
        for n, pct in comp.get("stk", []):
            stk[n] = stk.get(n, 0) + w * pct / 100
    tr = CFG["daily"]["sectorTracker"]
    return {"pm": max(months) if months else None,
            "sec": [[n, round(v, 2), tr.get(k)] for k, (n, v) in sorted(sec.items(), key=lambda x: -x[1][1])[:6]],
            "stk": [[n, round(v, 2)] for n, v in sorted(stk.items(), key=lambda x: -x[1])[:5]],
            "asset": [[n, round(v, 2)] for n, v in sorted(asset.items(), key=lambda x: -x[1])]}

def acct_slug(aid: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in aid.lower()).strip("-")


def account_files(store: dict, view: dict, sb: dict) -> dict:
    """Per-person public files (data/sim/<slug>.json), written only while the audit passes: profile, holdings
    summary (moved here from the scoreboard), the daily summary series for the Portfolio-vs-Nifty-50 chart and the
    last few full daily summaries (holdings' moves and contributions, look-through exposure, market moves)."""
    days = store.get("days", [])
    labels = {sym: lab for sym, lab in CFG["daily"]["market"]}
    mkt = {e["d"]: e for e in days if e["t"] == "mkt"}
    by = {}
    for e in days:
        if e["t"] == "acct":
            by.setdefault(e["a"], []).append(e)
    names, cats = {}, {}
    try:
        sc = json.loads((DATA / "mf" / "screener.json").read_text())
        c = sc["cols"]
        subn = {k: v[1] for k, v in sc["subs"].items()}
        for r in sc["rows"]:
            cats[str(r[c.index("code")])] = subn.get(r[c.index("sub")], r[c.index("sub")])
    except Exception:  # noqa: BLE001
        pass
    try:
        for x in json.loads((DATA / "etf_momentum.json").read_text())["etfs"]:
            cats[x["s"]] = x.get("k") or ""
    except Exception:  # noqa: BLE001
        pass
    for a in view["accounts"]:
        for t in a["txns"]:
            names[str(t.get("code") or t.get("sym"))] = t["name"]

    def moves(ds):
        m = mkt.get(ds)
        if not m:
            return []
        return sorted([[labels.get(sym, sym), sym, round((px / qx - 1) * 100, 2)] for sym, px, _, qx, _ in m["m"] if qx],
                      key=lambda x: -abs(x[2]))
    keep = CFG["daily"]["keepPublicDays"]
    book = store.get("lookthrough", {})
    for es in by.values():                   # look-through references are recorded only when they change
        lt = {}
        for e in es:
            lt = e.get("lt", lt)
            e["_lt"] = lt
    out = {}
    for row, a in zip(sb["rows"], view["accounts"]):
        es = by.get(a["id"], [])
        f = acct_slug(a["id"])
        row["f"] = f
        if es:
            row["day"] = {"d": es[-1]["d"], "chg": es[-1]["chg"], "pct": es[-1]["pct"], "first": es[-1]["first"]}
        out[f] = {"v": 1, "id": a["id"], "updated": sb["updated"], "auditOk": sb["auditOk"],
                  **{k: row[k] for k in ("name", "product", "risk", "freq", "amt", "nri", "since", "metric", "ret") if k in row},
                  "credit": row.get("credit"), "detail": row.pop("detail", None),
                  "series": [[e["d"], e["val"], e["inv"], e["pct"], e["bpct"], e["bval"]] for e in es],
                  "recent": [{"d": e["d"], "val": e["val"], "inv": e["inv"], "chg": e["chg"], "pct": e["pct"], "bval": e["bval"],
                              "bchg": e["bchg"], "bpct": e["bpct"], "first": e["first"], "cash": e["cash"], "pend": e["pend"],
                              "hold": [[names.get(h[0], h[0]), h[0], cats.get(h[0], "")] + h[1:] for h in e["hold"]],
                              "x": exposure_from(a["product"], e["hold"], e["_lt"], book), "mkt": moves(e["d"])} for e in es[-keep:]]}
    return out

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
