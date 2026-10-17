#!/usr/bin/env python3
"""
build_etf_extras.py
───────────────────
Per-ETF analytics for etf_momentum.html, built from data already in the repo (no network):

  data/etf_extras.json    (loaded at page start)
    sc   VilfinTV scorecard, 3-year and 5-year views — consistency (share of month-ends in the top half of its
         peers on rolling 1-year returns), recency (3- and 6-month return rank), low volatility (rank of the
         standard deviation of weekly returns); overall = 40% consistency + 30% recency + 30% low volatility
    rt   VilfinTV rating — 0–100 score and 1–5 stars from cost, liquidity, tracking & pricing, returns, risk and
         size & track record, ranked against ETFs of the same peer group
    f    Factor DNA — returns-based style analysis of 3 years of weekly returns on factor ETFs
         (market, mid, small, momentum, value, quality, low volatility, US, cash)
    te   tracking error / difference vs other ETFs on the same index (when there are any)
  data/etf_holdings.json  (loaded when an ETF is opened)
         latest monthly portfolio: the ETF's own statutory portfolio (data/mf/etf_p.json) when the fund house
         publishes one, otherwise the portfolio of the largest index fund / ETF tracking the same index

Peers   : ETFs with the same portfolio role (core, satellite, global, hybrid); gold and silver separately;
          debt ETFs split into liquid-type and bond ETFs. A peer group needs at least 5 ETFs.
Usage   : python scripts/build_etf_extras.py
"""
from __future__ import annotations

import glob
import html
import json
import logging
import math
import os
import re
import sys
import warnings
from datetime import date, datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mf_common as C  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("etf_extras")

DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "etf_extras.json")
OUT_H = os.path.join(DATA, "etf_holdings.json")
MIN_PEERS = 5
PF_MAX_AGE_DAYS = 45
# factor key → ETFs tracking that factor index (first with a full 3-year weekly history wins)
FACTOR_ETFS = {
    "core": ["NIFTYBEES", "SETFNIF50", "NIFTYIETF"],
    "mid": ["MID150BEES", "MIDCAPIETF", "MIDCAPETF"],
    "small": ["HDFCSML250", "MOSMALL250"],
    "mom": ["HDFCMOMENT", "MOMENTUM", "MOM30IETF"],
    "val": ["NV20IETF", "NV20BEES", "NV20"],
    "qual": ["QUAL30IETF", "NIFTYQLITY", "SBIETFQLTY"],
    "lowvol": ["LOWVOLIETF", "LOWVOL1", "LOWVOL"],
    "us": ["MON100", "MASPTOP50"],
    "cash": ["LIQUIDBEES", "LIQUIDETF", "LIQUID"],
}
RATING_W = {"cost": 20, "liq": 20, "trk": 15, "ret": 20, "risk": 15, "size": 10}


def role_of(e: dict) -> str:
    """Same rule as roleOf() in etf_momentum.html."""
    k, n = e.get("k") or "", f"{e.get('n') or ''} {e.get('u') or ''}"
    if re.search(r"hybrid|balanced|multi.?asset", n, re.I):
        return "hyb"
    if k in ("Broad Market", "Next 50, Mid & Small Cap"):
        return "core"
    if k in ("Gold", "Silver"):
        return "com"
    if k == "Liquid & Debt":
        return "debt"
    if k == "International" or re.search(r"nasdaq|s&p 500|hang seng|nyse|ftse|msci|global|world", n, re.I):
        return "glob"
    return "sat"


def is_liquid(e: dict) -> bool:
    t = f"{e.get('n') or ''} {(e.get('x') or {}).get('benchmark') or ''} {e.get('u') or ''}"
    return bool(re.search(r"liquid|overnight|1 ?d rate|money market", t, re.I)) or (e.get("vol") is not None and e["vol"] < 1.5)


def peer_key(e: dict) -> str:
    r = role_of(e)
    if r == "com":
        return "silver" if e.get("k") == "Silver" else "gold"
    if r == "debt":
        return "liquid" if is_liquid(e) else "bond"
    return r


PEER_NAMES = {"core": "Core (broad market, mid & small cap) ETFs", "sat": "Satellite (sector, thematic & factor) ETFs",
              "glob": "Global ETFs", "hyb": "Hybrid ETFs", "gold": "Gold ETFs", "silver": "Silver ETFs",
              "liquid": "Liquid & overnight ETFs", "bond": "Bond & gilt ETFs"}


def idx_norm(k: str) -> str:
    """Comparable index name: 'Nifty 50 Index - TRI' / 'NIFTY50 TRI' → 'nifty 50'."""
    k = html.unescape(k or "").split("\n")[0].lower().replace("–", "-")
    k = re.sub(r"\(.*?\)?\)", " ", k)
    k = re.sub(r"\(.*", " ", k)
    k = re.sub(r"\b(total returns?|tri|price return|index|etf|bees|fund|benchmark)\b", " ", k)
    k = re.sub(r"\b(mirae asset|nippon india|icici prudential|icici pru|motilal oswal|kotak|hdfc|sbi|uti|axis|dsp|zerodha|"
               r"groww|aditya birla sun life|bajaj finserv|edelweiss|tata|invesco india|bandhan|angel one|lic mf)\b", " ", k)
    k = re.sub(r"\bs&p bse\b", "bse", k).replace("sensex 30", "sensex")
    k = re.sub(r"\b(nifty|midcap|smallcap)(\d)", r"\1 \2", k)
    k = re.sub(r"[^a-z0-9&:+ ]", " ", k)
    return re.sub(r"\s+", " ", k).strip()


def index_key(name: str) -> str:
    """The index a passive fund tracks, from its name — same rule as index_key() in build_mf_holdings.py."""
    n = re.sub(r"\(.*?\)", " ", (name or "").lower())
    n = re.sub(r"\b(nifty|midcap|smallcap)(\d)", r"\1 \2", n)
    m = re.search(r"\b((?:nifty|bse|s&p bse|sensex|crisil|msci|nasdaq|s&p)\b.*?)(?=\s+(?:index|etf|fund|fof|plan)\b|$)", n)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def index_names(e: dict) -> list[str]:
    x = e.get("x") or {}
    out = [idx_norm(x.get("benchmark") or ""), idx_norm(e.get("u") or ""), idx_norm(index_key(e.get("u") or "")),
           idx_norm(index_key(e.get("n") or ""))]
    return [k for k in dict.fromkeys(out) if k and k not in ("nifty", "bse", "domestic price of gold")]


def pct_ranks(vals: list, higher_better: bool = True) -> list:
    return C.percentile_ranks(vals, higher_better)


def wk_returns(arr: list) -> np.ndarray:
    a = np.array([np.nan if v is None else float(v) for v in arr])
    return a[1:] / a[:-1] - 1


def month_end_idx(weeks: list[str]) -> list[int]:
    """Index of the last weekly close of every calendar month."""
    out = []
    for i, w in enumerate(weeks):
        if i == len(weeks) - 1 or weeks[i + 1][:7] != w[:7]:
            out.append(i)
    return out


def scorecard(etfs: list[dict], hist: dict, groups: dict) -> dict:
    weeks = hist["weeks"]
    me = month_end_idx(weeks)
    W = len(weeks)
    closes = {s: np.array([np.nan if v is None else float(v) for v in hist["etfs"].get(s, [None] * W)]) for m in groups.values() for s in m}
    out: dict[str, dict] = {}
    for view, months, min_obs in (("3", 36, 24), ("5", 60, 36)):
        span = 52 * months // 12
        mes = [i for i in me if i >= W - 1 - span and i >= 52]
        for g, members in groups.items():
            # rolling 1-year return at every month-end → top-half share
            top = {s: [] for s in members}
            for i in mes:
                vals = []
                for s in members:
                    c = closes[s]
                    a, b = c[i - 52], c[i]
                    vals.append(b / a - 1 if np.isfinite(a) and np.isfinite(b) and a > 0 else None)
                ok = [v for v in vals if v is not None]
                if len(ok) < MIN_PEERS:
                    continue
                med = float(np.median(ok))
                for s, v in zip(members, vals):
                    if v is not None:
                        top[s].append(1 if v >= med else 0)
            cons = {s: (100.0 * sum(t) / len(t) if len(t) >= min_obs else None) for s, t in top.items()}
            # volatility of weekly returns over the window
            vol = {}
            for s in members:
                r = wk_returns(closes[s][W - 1 - span:])
                r = r[np.isfinite(r)]
                vol[s] = float(np.std(r, ddof=1) * math.sqrt(52) * 100) if len(r) >= 0.9 * span and cons[s] is not None else None
            # recency: 3- and 6-month returns (same in both views)
            rec_raw = {}
            for s in members:
                c = closes[s]
                r3 = c[-1] / c[-14] - 1 if np.isfinite(c[-1]) and np.isfinite(c[-14]) and c[-14] > 0 else None
                r6 = c[-1] / c[-27] - 1 if np.isfinite(c[-1]) and np.isfinite(c[-27]) and c[-27] > 0 else None
                rec_raw[s] = (r3, r6)
            elig = [s for s in members if cons[s] is not None and vol[s] is not None and None not in rec_raw[s]]
            if len(elig) < MIN_PEERS:
                continue
            p3 = pct_ranks([rec_raw[s][0] for s in elig])
            p6 = pct_ranks([rec_raw[s][1] for s in elig])
            pv = pct_ranks([vol[s] for s in elig], higher_better=False)
            rows = []
            for s, a, b, v in zip(elig, p3, p6, pv):
                rec = 100 * (a + b) / 2
                volsc = 100 * v
                o = 0.4 * cons[s] + 0.3 * rec + 0.3 * volsc
                rows.append((s, round(cons[s], 1), round(rec, 1), round(volsc, 1), round(o, 1), round(vol[s], 2)))
            rows.sort(key=lambda x: (-x[4], x[0]))
            n = len(rows)
            for i, (s, c_, r_, v_, o_, sd) in enumerate(rows):
                out.setdefault(s, {})[view] = {"c": c_, "r": r_, "v": v_, "o": o_, "sd": sd, "rk": i + 1, "n": n}
            # per-metric ranks
            for key, j in (("rkc", 1), ("rkr", 2), ("rkv", 3)):
                for i, row in enumerate(sorted(rows, key=lambda x: (-x[j], x[0]))):
                    out[row[0]][view][key] = i + 1
            med = {"c": float(np.median([r[1] for r in rows])), "r": float(np.median([r[2] for r in rows])),
                   "v": float(np.median([r[3] for r in rows])), "o": float(np.median([r[4] for r in rows]))}
            for s in elig:
                out[s][view]["med"] = {k: round(v, 1) for k, v in med.items()}
    return out


def tracking(etfs: list[dict], hist: dict) -> dict:
    """Annualised tracking error and 1-year tracking difference vs the median of other ETFs on the same index."""
    by_idx: dict[str, list[str]] = {}
    for e in etfs:
        if role_of(e) in ("debt",) or not hist["etfs"].get(e["s"]):
            continue
        names = index_names(e)
        if names:
            by_idx.setdefault(names[0], []).append(e["s"])
    out = {}
    W = len(hist["weeks"])
    for k, syms in by_idx.items():
        if len(syms) < 2:
            continue
        R = {s: wk_returns(hist["etfs"][s][W - 157:]) for s in syms}
        for s in syms:
            others = [R[o] for o in syms if o != s]
            with np.errstate(all="ignore"), warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                med = np.nanmedian(np.vstack(others), axis=0) if len(others) > 1 else others[0]
            gap = R[s] - med
            ok = np.isfinite(gap)
            if ok.sum() < 52:
                continue
            te = float(np.std(gap[ok], ddof=1) * math.sqrt(52) * 100)
            g1 = gap[-52:]
            td = float((np.prod(1 + R[s][-52:][np.isfinite(g1)]) - np.prod(1 + med[-52:][np.isfinite(g1)])) * 100) if np.isfinite(g1).sum() >= 45 else None
            out[s] = {"te": round(te, 2), "td1": None if td is None else round(td, 2), "n": len(syms), "idx": k}
    return out


def factor_dna(etfs: list[dict], hist: dict) -> tuple[dict, dict]:
    W = len(hist["weeks"])
    win = 157
    used, X = {}, []
    for k, cands in FACTOR_ETFS.items():
        for s in cands:
            arr = hist["etfs"].get(s) or []
            if len(arr) == W and sum(v is not None for v in arr[W - win:]) >= win - 2:
                used[k] = s
                X.append(wk_returns(arr[W - win:]))
                break
        else:
            log.warning("factor %s: no ETF with a full 3-year history", k)
    keys = list(used)
    if len(keys) < 6 or "core" not in used:
        log.warning("Factor DNA skipped: only %d factors", len(keys))
        return {}, used
    Xm = np.column_stack(X)
    out = {}
    for e in etfs:
        if role_of(e) in ("debt", "com") or e["s"] not in hist["etfs"]:
            continue
        y = wk_returns(hist["etfs"][e["s"]][W - win:])
        ok = np.isfinite(y) & np.all(np.isfinite(Xm), axis=1)
        if ok.sum() < 104:
            continue
        sa = C.style_analysis(y[ok], Xm[ok])
        if not sa:
            continue
        w, r2 = sa
        wd = {k: 0.0 for k in C.FACTOR_KEYS}
        wd.update({k: float(x) for k, x in zip(keys, w)})
        lab = C.factor_label(wd, r2)
        out[e["s"]] = {"w": {k: round(v * 100, 1) for k, v in wd.items() if k in used}, "r2": round(r2 * 100, 1),
                       "weeks": int(ok.sum()), **lab}
    return out, used


def rating(etfs: list[dict], groups: dict, trk: dict, as_of: str) -> dict:
    ad = datetime.strptime(as_of, "%Y-%m-%d")
    by = {e["s"]: e for e in etfs}

    def years(e):
        return (ad - datetime.strptime(e["first"], "%Y-%m-%d")).days / 365.25 if e.get("first") else 0

    out = {}
    for g, members in groups.items():
        es = [by[s] for s in members]
        elig = [e for e in es if years(e) >= 1 and (e.get("tv") or 0) >= 0.01 and (e.get("r") or {}).get("1y") is not None]
        if len(elig) < MIN_PEERS:
            continue
        x = lambda e: e.get("x") or {}  # noqa: E731
        parts = {
            "cost": pct_ranks([x(e).get("ter") if (x(e).get("ter") or 0) > 0 else None for e in elig], False),
            "liq": pct_ranks([e.get("tv") for e in elig]),
            "prem": pct_ranks([abs(e["prem"]) if e.get("prem") is not None else None for e in elig], False),
            "te": pct_ranks([(trk.get(e["s"]) or {}).get("te") for e in elig], False),
            "r1": pct_ranks([e["r"].get("1y") for e in elig]),
            "r3": pct_ranks([e["r"].get("3y") for e in elig]),
            "r5": pct_ranks([e["r"].get("5y") for e in elig]),
            "vol": pct_ranks([e.get("vol") for e in elig], False),
            "mdd": pct_ranks([e.get("mdd") for e in elig]),
            "rr3": pct_ranks([e.get("rr3") for e in elig]),
            "aum": pct_ranks([x(e).get("aum") for e in elig]),
            "age": pct_ranks([years(e) for e in elig]),
        }

        def avg(i, ks):
            v = [parts[k][i] for k in ks if parts[k][i] is not None]
            return 100 * sum(v) / len(v) if v else None

        scores = []
        for i, e in enumerate(elig):
            sc = {"cost": avg(i, ["cost"]), "liq": avg(i, ["liq"]), "trk": avg(i, ["prem", "te"]),
                  "ret": avg(i, ["r1", "r3", "r5"]), "risk": avg(i, ["vol", "mdd", "rr3"]), "size": avg(i, ["aum", "age"])}
            have = {k: v for k, v in sc.items() if v is not None}
            if "ret" not in have or len(have) < 4:
                scores.append(None)
                continue
            tot = sum(RATING_W[k] * v for k, v in have.items()) / sum(RATING_W[k] for k in have)
            scores.append((tot, {k: round(v) for k, v in have.items()}))
        stars = C.stars_from_scores([s[0] if s else None for s in scores])
        ok = [(e, s, st) for e, s, st in zip(elig, scores, stars) if s]
        ok.sort(key=lambda t: -t[1][0])
        for i, (e, s, st) in enumerate(ok):
            out[e["s"]] = {"s": round(s[0]), "st": st, "p": s[1], "rk": i + 1, "n": len(ok)}
    return out


def holdings(etfs: list[dict]) -> dict:
    """Own statutory portfolio first, then the portfolio of the largest fund (index fund or ETF) on the same index."""
    today = date.today()

    def fresh(v):
        try:
            y, m = map(int, v["asOf"][:7].split("-"))
            end = date(y + (m == 12), m % 12 + 1, 1)
            return (today - end).days + 1 <= PF_MAX_AGE_DAYS
        except Exception:  # noqa: BLE001
            return False

    own = {}
    p = os.path.join(DATA, "mf", "etf_p.json")
    if os.path.exists(p):
        own = {k: v for k, v in json.load(open(p)).items() if fresh(v)}
    scr = json.load(open(os.path.join(DATA, "mf", "screener.json")))
    ci = {c: i for i, c in enumerate(scr["cols"])}
    rows = {r[ci["code"]]: r for r in scr["rows"]}
    pf = {}
    for f in glob.glob(os.path.join(DATA, "mf", "p", "*.json")):
        if os.path.basename(f).startswith("_"):
            continue
        for c, v in json.load(open(f)).items():
            if not v.get("proxyOf") and fresh(v):
                pf[int(c)] = v
    peers: dict[str, list] = {}
    for code, v in pf.items():
        r = rows.get(code)
        if r and r[ci["sub"]].startswith("idx_"):
            k = idx_norm(index_key(r[ci["name"]]))
            if k:
                peers.setdefault(k, []).append((r[ci["aum"]] or 0, r[ci["name"]], v))
    by_isin = {e.get("i"): e for e in etfs if e.get("i")}
    for isin, v in own.items():                       # ETFs with their own portfolio also serve as same-index sources
        e = by_isin.get(isin)
        if e:
            for k in index_names(e)[:1]:
                peers.setdefault(k, []).append(((e.get("x") or {}).get("aum") or 0, e["n"], v))
    out = {}
    for e in etfs:
        if role_of(e) in ("debt", "com"):
            continue
        mine = own.get(e.get("i") or "")
        if mine:
            out[e["s"]] = {**mine, "src": "own"}
            continue
        for k in index_names(e):
            if k in peers:
                cand = [c for c in peers[k] if c[1] != e["n"]]
                if cand:
                    aum, name, v = max(cand, key=lambda c: c[0])
                    out[e["s"]] = {**v, "src": "index", "proxyName": name, "index": k}
                    break
    return out


def main() -> int:
    d = json.load(open(os.path.join(DATA, "etf_momentum.json")))
    hist = json.load(open(os.path.join(DATA, "etf_hist.json")))
    etfs = [e for e in d["etfs"] if e.get("q") != "nodata"]
    groups: dict[str, list[str]] = {}
    for e in etfs:
        if e["s"] in hist["etfs"]:
            groups.setdefault(peer_key(e), []).append(e["s"])
    sc = scorecard(etfs, hist, {g: m for g, m in groups.items() if g not in ("liquid", "bond")})
    trk = tracking(etfs, hist)
    fac, used = factor_dna(etfs, hist)
    rt = rating(etfs, groups, trk, d["asOf"])
    hold = holdings(etfs)
    rec = {}
    for e in etfs:
        o = {"g": peer_key(e)}
        if e["s"] in sc:
            o["sc"] = sc[e["s"]]
        if e["s"] in rt:
            o["rt"] = rt[e["s"]]
        if e["s"] in fac:
            o["f"] = fac[e["s"]]
        if e["s"] in trk:
            o["te"] = trk[e["s"]]
        if e["s"] in hold:
            o["h"] = hold[e["s"]]["src"]
        rec[e["s"]] = o
    payload = {"v": 1, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "asOf": d["asOf"],
               "groups": {g: {"name": PEER_NAMES[g], "n": len(m)} for g, m in groups.items()},
               "factors": {k: s for k, s in used.items()}, "ratingW": RATING_W, "etfs": rec}
    for path, obj in ((OUT, payload), (OUT_H, {"asOf": d["asOf"], "etfs": hold})):
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"), ensure_ascii=False)
        os.replace(path + ".tmp", path)
    log.info("scorecards %d · ratings %d · factor DNA %d · tracking %d · holdings %d (own %d)",
             len(sc), len(rt), len(fac), len(trk), len(hold), sum(1 for v in hold.values() if v["src"] == "own"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
