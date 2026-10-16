#!/usr/bin/env python3
"""
India Mutual Fund Screener — exit loads straight from fund houses whose loads are missing from the
industry scheme master (currently SBI). Runs weekly inside the holdings workflow (needs a browser).

Output: data/mf/exitload_extra.json  {"_asOf": "...", "<AMFI code>": ["line", ...], ...}
The daily screener build uses these lines only when the official scheme master has no exit load.
"""
from __future__ import annotations

import html
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_mf_holdings as H  # noqa: E402  (scheme-name tokeniser + browser helper)
import mf_enrich as E  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mf" / "exitload_extra.json"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("loads")

SBI_PAGE = "https://www.sbimf.com/sbimf-scheme-details/sbi-small-cap-fund-329"

# runs inside the fund-house page: reuses the page's own session token to read each fund's details
SBI_JS = """async ([hdr, post, ids]) => {
  const out = {};
  const h = {};
  for (const k of Object.keys(hdr)) if (!/^(host|content-length|cookie|accept-encoding|origin|referer|user-agent|sec-)/i.test(k)) h[k] = hdr[k];
  for (const id of ids) {
    const body = JSON.parse(post); const d = JSON.parse(body.Data); d.FundId = String(id); body.Data = JSON.stringify(d);
    body.Requestid = crypto.randomUUID();
    try {
      const r = await fetch('/api/SchemeDetailsAPI/SingleFundDetails/', {method: 'POST', headers: h, body: JSON.stringify(body)});
      const j = await r.json();
      if (j && j.FundExitLoadDescription !== undefined) out[id] = j.FundExitLoadDescription || '';
    } catch (e) { /* skip this fund */ }
    await new Promise(res => setTimeout(res, 250));
  }
  return out;
}"""


def html_to_lines(h: str) -> list[str]:
    t = re.sub(r"(?i)<\s*(br|/p|/div|/li)\s*/?>|&bull;|•", "\n", h or "")
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = "\n".join(re.sub(r"\s+", " ", x).strip() for x in t.splitlines())
    return E.parse_exit_load(t)


def sbi_loads(funds: list[dict]) -> dict[int, list[str]]:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b, ctx = H.browser(pw)
        p = ctx.new_page()
        req, names = {}, {}

        def on_req(r):
            if "SingleFundDetails" in r.url and "post" not in req:
                req.update(headers=r.headers, post=r.post_data)

        def on_resp(r):
            if "AllFundNames" in r.url and not names:
                try:
                    data = json.loads(json.loads(r.text())["Data"])["Data"]
                    names.update({x["FundID"]: x for x in data})
                except Exception:  # noqa: BLE001
                    pass
        p.on("request", on_req)
        p.on("response", on_resp)
        p.goto(SBI_PAGE, wait_until="domcontentloaded", timeout=90000)
        p.wait_for_timeout(12000)
        if not req or not names:
            log.warning("SBI: fund list or detail request not captured (list %d, request %s)", len(names), bool(req))
            b.close()
            return {}
        # match our funds to the fund house's fund ids by scheme name (current or former)
        cands = []
        for fid, x in names.items():
            for nm in {x.get("FundUrlTitle") or "", x.get("FundName") or ""} | set(
                    re.findall(r"\((?:formerly|erstwhile)\s+known\s+as\s+([^)]+)\)", x.get("FundName") or "", re.I)):
                t = H.tokens(nm)
                if t and not (re.search(r"\betf\b", nm, re.I) and not re.search(r"\bfof\b|fund of funds?", nm, re.I)):
                    cands.append((fid, t))
        want = {}
        for f in funds:
            ft = H.tokens(f["amfi"])
            if not ft:
                continue
            scored = sorted(((len(ft & t) / len(ft | t), fid) for fid, t in cands), reverse=True)
            if scored and scored[0][0] >= 0.75 and (len(scored) == 1 or scored[0][0] - next(
                    (s for s, i in scored[1:] if i != scored[0][1]), 0) >= 0.1):
                want[f["code"]] = scored[0][1]
        log.info("SBI: %d fund ids listed, %d of %d funds matched", len(names), len(want), len(funds))
        raw = p.evaluate(SBI_JS, [req["headers"], req["post"], sorted(set(want.values()))])
        b.close()
    out = {}
    for code, fid in want.items():
        lines = html_to_lines(raw.get(str(fid)) or raw.get(fid) or "")
        if lines:
            out[code] = lines
    return out


def main():
    scr = json.load(open(ROOT / "data" / "mf" / "screener.json"))
    C = {c: i for i, c in enumerate(scr["cols"])}
    det = {}
    for f in (ROOT / "data" / "mf" / "d").glob("*.json"):
        det.update(json.load(open(f)))
    by_amc = defaultdict(list)
    for r in scr["rows"]:
        code = r[C["code"]]
        by_amc[scr["amcs"][r[C["amc"]]]].append(
            {"code": code, "amfi": (det.get(str(code)) or {}).get("info", {}).get("amfiName") or r[C["name"]]})
    prev = json.load(open(OUT)) if OUT.exists() else {}
    res = {}
    try:
        res.update(sbi_loads(by_amc.get("SBI", [])))
    except Exception as e:  # noqa: BLE001
        log.warning("SBI exit loads unavailable this run (%s) — keeping the previous file", str(e)[:160])
    if not res:
        log.info("No exit loads fetched; previous file kept (%d funds)", len(prev) - 1 if prev else 0)
        return
    res = {str(k): v for k, v in sorted(res.items())}
    res["_asOf"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=0))
    log.info("Exit loads written for %d funds", len(res) - 1)


if __name__ == "__main__":
    main()
