#!/usr/bin/env node
/*
 * India Mutual Fund Screener — independent verification.
 *
 * 1. Re-computes every published analytic for a sample of funds (one per
 *    sub-category + the reference funds) from the raw NAV history, using a
 *    from-scratch JavaScript implementation, and requires agreement with the
 *    Python build (scripts/mf_common.py) to within rounding.
 * 2. Structural checks on data/mf/: schema, value ranges, classification
 *    coverage, every fund has its detail / tail / history files.
 *
 * Exit code 1 on any failure (the workflow then refuses to publish).
 */
'use strict';
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'data', 'mf');
const SAMPLE = path.join(ROOT, '.mfcache', 'verify_sample.json.gz');

let failures = 0, checks = 0;
const AUDIT = {};
const fail = (msg) => { failures++; if (failures <= 80) console.error('✗ ' + msg); };
const ok = (cond, msg) => { checks++; if (!cond) fail(msg); };

// ───────────────────────── date helpers (UTC day numbers) ─────────────────────────
const DAY = 86400000;
const dn = (iso) => Math.round(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / DAY);
const isoOf = (n) => new Date(n * DAY).toISOString().slice(0, 10);
const daysInMonth = (y, m0) => new Date(Date.UTC(y, m0 + 1, 0)).getUTCDate();
function addMonths(n, k) {
  const d = new Date(n * DAY);
  let y = d.getUTCFullYear(), m = d.getUTCMonth() + k;
  y += Math.floor(m / 12); m = ((m % 12) + 12) % 12;
  const day = Math.min(d.getUTCDate(), daysInMonth(y, m));
  return Math.round(Date.UTC(y, m, day) / DAY);
}
const TOL = 10;

// ───────────────────────── series helpers ─────────────────────────
function lastLE(d, t) {           // index of last d[i] <= t, -1 if none
  let lo = 0, hi = d.length - 1, ans = -1;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (d[mid] <= t) { ans = mid; lo = mid + 1; } else hi = mid - 1; }
  return ans;
}
function firstGE(d, t) {
  let lo = 0, hi = d.length - 1, ans = d.length;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (d[mid] >= t) { ans = mid; hi = mid - 1; } else lo = mid + 1; }
  return ans;
}
function baseIdx(d, t) {
  if (!d.length || t < d[0]) return -1;
  const i = lastLE(d, t);
  if (i < 0 || t - d[i] > TOL) return -1;
  return i;
}
function cut(s, t) { const i = lastLE(s.d, t) + 1; return { d: s.d.slice(0, i), v: s.v.slice(0, i) }; }

// ───────────────────────── analytics (independent implementation) ─────────────────────────
function trailing(s) {
  const o = {}, n = s.d.length, E = s.d[n - 1], V = s.v[n - 1];
  o['1d'] = (V / s.v[n - 2] - 1) * 100;
  const P = [['1w', 'd', 7], ['1m', 'm', 1], ['3m', 'm', 3], ['6m', 'm', 6], ['1y', 'm', 12], ['2y', 'm', 24],
             ['3y', 'm', 36], ['5y', 'm', 60], ['7y', 'm', 84], ['10y', 'm', 120]];
  for (const [k, kind, m] of P) {
    const t = kind === 'd' ? E - m : addMonths(E, -m);
    const i = baseIdx(s.d, t);
    if (i < 0) { o[k] = null; continue; }
    const r = V / s.v[i];
    o[k] = (kind === 'd' || m <= 12 ? r - 1 : Math.pow(r, 12 / m) - 1) * 100;
  }
  const y = new Date(E * DAY).getUTCFullYear();
  const iy = baseIdx(s.d, dn(`${y - 1}-12-31`));
  o.ytd = iy >= 0 ? (V / s.v[iy] - 1) * 100 : null;
  return o;
}
function siReturn(s, incIso, incV) {
  const E = s.d[s.d.length - 1], V = s.v[s.v.length - 1], d0 = dn(incIso), days = E - d0;
  const r = V / incV;
  return (days >= 365 ? Math.pow(r, 365 / days) - 1 : r - 1) * 100;
}
function xirr(flows) {
  const t0 = flows[0][0];
  const npv = (r) => flows.reduce((a, [t, c]) => a + c / Math.pow(1 + r, (t - t0) / 365), 0);
  let lo = -0.9999, hi = 10, flo = npv(lo);
  if (flo * npv(hi) > 0) return null;
  for (let i = 0; i < 200; i++) {
    const mid = (lo + hi) / 2, fm = npv(mid);
    if (Math.abs(fm) < 1e-7) { lo = hi = mid; break; }
    if (flo * fm < 0) hi = mid; else { lo = mid; flo = fm; }
  }
  return (lo + hi) / 2;
}
function sip(s, months) {
  const n = s.d.length, E = s.d[n - 1];
  let units = 0; const flows = [];
  for (let k = months; k >= 1; k--) {
    const t = addMonths(E, -k);
    if (t < s.d[0]) return null;
    const i = firstGE(s.d, t);
    if (i >= n || s.d[i] - t > TOL || s.d[i] >= E) return null;
    units += 10000 / s.v[i]; flows.push([s.d[i], -10000]);
  }
  const val = units * s.v[n - 1];
  flows.push([E, val]);
  const r = xirr(flows);
  return { inv: 10000 * months, val, xirr: r == null ? null : r * 100 };
}
function rollingSeries(s, years) {
  const ends = [], r = [];
  for (let i = 0; i < s.d.length; i++) {
    const t = addMonths(s.d[i], -12 * years);
    if (t < s.d[0]) continue;
    const j = lastLE(s.d, t);
    if (j < 0 || t - s.d[j] > TOL) continue;
    ends.push(s.d[i]); r.push(Math.pow(s.v[i] / s.v[j], 1 / years) - 1);
  }
  return { ends, r };
}
function rolling(s, years, bench) {
  const { ends, r } = rollingSeries(s, years);
  if (r.length < 20) return null;
  const sorted = [...r].sort((a, b) => a - b);
  const mean = r.reduce((a, b) => a + b, 0) / r.length;
  const o = { n: r.length, avg: mean * 100, min: sorted[0] * 100, max: sorted[sorted.length - 1] * 100,
              pos: r.filter(x => x > 0).length / r.length * 100 };
  const m = sorted.length;
  o.med = (m % 2 ? sorted[(m - 1) / 2] : (sorted[m / 2 - 1] + sorted[m / 2]) / 2) * 100;
  if (bench && bench.d.length > 20) {
    const b = rollingSeries(bench, years), map = new Map(b.ends.map((e, i) => [e, b.r[i]]));
    let n = 0, beat = 0;
    ends.forEach((e, i) => { if (map.has(e)) { n++; if (r[i] > map.get(e)) beat++; } });
    if (n >= 20) o.beat = beat / n * 100;
  }
  return o;
}
function monthEndVals(s, ends) { return ends.map(me => { const i = baseIdx(s.d, dn(me)); return i >= 0 ? s.v[i] : NaN; }); }
const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
const sd = (a) => { const m = mean(a); return Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1)); };
const cov = (a, b) => { const ma = mean(a), mb = mean(b); return a.reduce((x, _, i) => x + (a[i] - ma) * (b[i] - mb), 0) / (a.length - 1); };
const geo = (a) => Math.pow(a.reduce((x, y) => x * (1 + y), 1), 1 / a.length) - 1;
function risk(s, ends, rfV, benchV, withAlpha) {
  let fv = monthEndVals(s, ends);
  let k = fv.length - 1;
  while (k > 0 && isFinite(fv[k - 1]) && isFinite(rfV[k - 1])) k--;
  fv = fv.slice(k); const rv = rfV.slice(k);
  const n = fv.length - 1;
  if (n < 12 || !isFinite(fv[fv.length - 1])) return null;
  const f = [], rf = [];
  for (let i = 1; i <= n; i++) { f.push(fv[i] / fv[i - 1] - 1); rf.push(rv[i] / rv[i - 1] - 1); }
  const ex = f.map((x, i) => x - rf[i]);
  const o = { months: n, std: sd(f) * Math.sqrt(12) * 100, sharpe: sd(ex) > 0 ? mean(ex) / sd(ex) * Math.sqrt(12) : null,
              ret: (Math.pow(f.reduce((a, x) => a * (1 + x), 1), 12 / n) - 1) * 100 };
  const dd = Math.sqrt(mean(ex.map(x => Math.min(x, 0) ** 2)));
  o.sortino = dd > 0 ? mean(ex) * 12 / (dd * Math.sqrt(12)) : null;
  if (benchV) {
    const bAll = benchV.slice(k);
    let kb = bAll.length - 1;
    while (kb > 0 && isFinite(bAll[kb - 1])) kb--;
    if (isFinite(bAll[bAll.length - 1]) && bAll.length - 1 - kb >= 12) {
      const bv = bAll.slice(kb), fb = f.slice(kb), rfb = rf.slice(kb);
      const b = []; for (let i = 1; i < bv.length; i++) b.push(bv[i] / bv[i - 1] - 1);
      const exf = fb.map((x, i) => x - rfb[i]), exb = b.map((x, i) => x - rfb[i]);
      const beta = cov(exf, exb) / cov(exb, exb);
      o.beta = beta;
      const c = cov(exf, exb) / (sd(exf) * sd(exb)); o.r2 = c * c * 100;
      if (withAlpha) {
        o.alpha = (mean(exf) - beta * mean(exb)) * 12 * 100;
        const d = fb.map((x, i) => x - b[i]), te = sd(d) * Math.sqrt(12);
        o.te = te * 100; o.ir = mean(d) * 12 / te;
        const up = b.map((x, i) => x > 0 ? i : -1).filter(i => i >= 0), dnI = b.map((x, i) => x < 0 ? i : -1).filter(i => i >= 0);
        if (up.length >= 3) o.upCap = geo(up.map(i => fb[i])) / geo(up.map(i => b[i])) * 100;
        if (dnI.length >= 3) o.downCap = geo(dnI.map(i => fb[i])) / geo(dnI.map(i => b[i])) * 100;
      }
    }
  }
  return o;
}
function mdd(s, a0, b0) {
  const a = firstGE(s.d, a0), b = lastLE(s.d, b0) + 1;
  if (b - a < 5) return null;
  let peak = -Infinity, best = 0, tI = a;
  for (let i = a; i < b; i++) { peak = Math.max(peak, s.v[i]); const dd = s.v[i] / peak - 1; if (dd < best) { best = dd; tI = i; } }
  return { mdd: best * 100, trough: isoOf(s.d[tI]) };
}

// ───────────────────────── comparison ─────────────────────────
function close(a, b, tol, label) {
  checks++;
  if (a == null && b == null) return;
  if (a == null || b == null || !isFinite(a) || !isFinite(b) || Math.abs(a - b) > tol) {
    fail(`${label}: python=${b} js=${a}`);
  }
}

function verifySample() {
  if (!fs.existsSync(SAMPLE)) { fail('verify sample missing (.mfcache/verify_sample.json.gz)'); return; }
  const S = JSON.parse(zlib.gunzipSync(fs.readFileSync(SAMPLE)).toString());
  const riskAsOf = dn(S.riskAsOf);
  const benchSeries = {};
  for (const [k, b] of Object.entries(S.benchSeries)) benchSeries[k] = { d: b.d.map(dn), v: b.v };
  // month-end values of the risk-free proxy and benchmarks must match too
  const rfJs = monthEndVals(cut(benchSeries.rf, riskAsOf), S.monthEnds);
  rfJs.forEach((x, i) => close(x, S.rf[i], 1e-9, `rf month-end ${S.monthEnds[i]}`));
  const benchMe = {};
  for (const k of Object.keys(S.bench)) {
    benchMe[k] = monthEndVals(cut(benchSeries[k], riskAsOf), S.monthEnds);
    benchMe[k].forEach((x, i) => { if (isFinite(x) || S.bench[k][i] != null) close(isFinite(x) ? x : null, S.bench[k][i], 1e-9, `bench ${k} ${S.monthEnds[i]}`); });
  }
  for (const F of S.funds) {
    const s = { d: F.d.map(dn), v: F.v }, o = F.out, L = `${F.code}`;
    const tr = trailing(s);
    for (const k of Object.keys(tr)) close(tr[k], o.tr[k], 2e-4, `${L} trailing ${k}`);
    close(siReturn(s, o.inc, o.incV), o.tr.si, 2e-4, `${L} since inception`);
    for (const [yrs, m] of [['1', 12], ['3', 36], ['5', 60], ['10', 120]]) {
      const j = sip(s, m), p = o.sip[yrs];
      if (!j || !p) { ok(!j === !p, `${L} SIP ${yrs}Y availability`); continue; }
      close(j.xirr, p.xirr, 2e-3, `${L} SIP ${yrs}Y XIRR`);
      close(j.val, p.val, 0.02, `${L} SIP ${yrs}Y value`);
    }
    const sm = cut(s, riskAsOf);
    const bser = o.bench ? cut(benchSeries[o.bench], riskAsOf) : null;
    if (o.roll) {
      for (const y of ['1', '3', '5']) {
        const j = rolling(sm, +y, bser), p = o.roll[y];
        if (!j || !p) { ok(!j === !p, `${L} rolling ${y}Y availability`); continue; }
        ok(j.n === p.n, `${L} rolling ${y}Y count ${j.n} vs ${p.n}`);
        for (const k of ['avg', 'med', 'min', 'max', 'pos']) close(j[k], p[k], 2e-2, `${L} rolling ${y}Y ${k}`);
        if (p.beat != null || j.beat != null) close(j.beat, p.beat, 2e-2, `${L} rolling ${y}Y beat`);
      }
    }
    if (o.risk) {
      const withAlpha = F.asset === 'Equity' || F.asset === 'Index';
      const j = risk(sm, S.monthEnds, S.rf.map(x => x == null ? NaN : x), o.bench ? S.bench[o.bench].map(x => x == null ? NaN : x) : null, withAlpha);
      ok(!!j, `${L} risk availability`);
      if (j) {
        ok(j.months === o.risk.months, `${L} risk months ${j.months} vs ${o.risk.months}`);
        for (const k of ['std', 'ret', 'alpha', 'te']) if (o.risk[k] != null || j[k] != null) close(j[k], o.risk[k], 2e-3, `${L} ${k}`);
        for (const k of ['sharpe', 'sortino', 'beta', 'ir']) if (o.risk[k] != null || j[k] != null) close(j[k], o.risk[k], 2e-4, `${L} ${k}`);
        for (const k of ['upCap', 'downCap', 'r2']) if (o.risk[k] != null || j[k] != null) close(j[k], o.risk[k], 1e-2, `${L} ${k}`);
      }
    }
    if (o.mdd3) {
      const j = mdd(s, addMonths(riskAsOf, -36), riskAsOf);
      close(j && j.mdd, o.mdd3.mdd, 2e-4, `${L} max drawdown 3Y`);
      ok(j && j.trough === o.mdd3.trough, `${L} drawdown trough date`);
    }
  }
  AUDIT.recomputedFunds = S.funds.length;
  console.log(`Cross-language check: ${S.funds.length} funds re-computed.`);
}

function verifyFiles() {
  const p = path.join(OUT, 'screener.json');
  if (!fs.existsSync(p)) { fail('data/mf/screener.json missing'); return; }
  const J = JSON.parse(fs.readFileSync(p, 'utf8'));
  const C = Object.fromEntries(J.cols.map((c, i) => [c, i]));
  ok(J.rows.length >= 1000, `universe too small: ${J.rows.length}`);
  ok(J.rows.length === J.count, 'count mismatch');
  ok(/^\d{4}-\d{2}-\d{2}$/.test(J.asOf), 'asOf format');
  const age = (Date.now() / DAY) - dn(J.asOf);
  ok(age < 10, `NAV date ${J.asOf} is ${age.toFixed(1)} days old`);
  const codes = new Set();
  const perAsset = {};
  for (const r of J.rows) {
    ok(r.length === J.cols.length, `row width ${r[0]}`);
    const code = r[C.code];
    ok(!codes.has(code), `duplicate code ${code}`); codes.add(code);
    ok(typeof r[C.name] === 'string' && r[C.name].length > 3, `name ${code}`);
    ok(J.subs[r[C.sub]], `unknown sub ${r[C.sub]} for ${code}`);
    const asset = J.subs[r[C.sub]] && J.subs[r[C.sub]][0];
    ok(J.assets.includes(asset), `asset ${asset}`);
    perAsset[asset] = (perAsset[asset] || 0) + 1;
    ok(r[C.nav] > 0, `nav ${code}`);
    for (const k of ['r1d', 'r1w', 'r1m', 'r3m', 'r6m', 'r1y', 'r3y', 'r5y', 'r10y', 'si'])
      ok(r[C[k]] == null || (isFinite(r[C[k]]) && r[C[k]] > -95 && r[C[k]] < 1000), `${code} ${k}=${r[C[k]]}`);
    ok(r[C.r1d] == null || Math.abs(r[C.r1d]) < 25, `${code} 1D move ${r[C.r1d]}% looks wrong`);
    ok(r[C.ter] == null || (r[C.ter] >= 0 && r[C.ter] < 3.5), `${code} TER ${r[C.ter]}`);
    ok(r[C.rating] == null || [1, 2, 3, 4, 5].includes(r[C.rating]), `${code} rating`);
    ok(r[C.sharpe] == null || Math.abs(r[C.sharpe]) < 50, `${code} sharpe ${r[C.sharpe]}`);
    for (const f of [`d/${r[C.sub]}.json`, `t/${r[C.sub]}.json`, `h/${code}.json`])
      ok(fs.existsSync(path.join(OUT, f)), `${code} missing ${f}`);
    // scorecard + taxation
    if ('status' in C) {
      for (const k of ['cons', 'rec', 'vols', 'ltp']) ok(r[C[k]] == null || (r[C[k]] >= 0 && r[C[k]] <= 100), `${code} ${k}=${r[C[k]]}`);
      const st = r[C.status];
      ok(st == null || (J.statuses || []).includes(st), `${code} status ${st}`);
      ok(st === statusOf(r[C.rec], r[C.ltp]), `${code} status ${st} does not follow its scores (rec ${r[C.rec]}, long-term ${r[C.ltp]})`);
      ok(asset !== 'Index' || st == null, `${code} index fund should not carry a status`);
      ok(J.tax && J.tax.rules && J.tax.rules[r[C.tax]], `${code} tax class ${r[C.tax]}`);
      if (r[C.sub] === 'elss') ok(r[C.tax] === 'elss' && r[C.lock] >= 3, `${code} ELSS tax / lock-in`);
      if (asset === 'Debt') ok(r[C.tax] === 'debt' || r[C.sub] === 'globaldebt', `${code} debt fund tax class ${r[C.tax]}`);
      ok(r[C.aum] == null || (r[C.aum] >= 0 && r[C.aum] < 500000), `${code} AUM ${r[C.aum]} Cr looks wrong`);
      ok(r[C.sipMin] == null || (r[C.sipMin] >= 0 && r[C.sipMin] <= 1e6), `${code} SIP minimum ${r[C.sipMin]}`);
    }
  }
  verifyAgainstPrevious(J, C);
  for (const a of ['Equity', 'Debt', 'Hybrid', 'Commodity', 'Global', 'Index'])
    ok((perAsset[a] || 0) >= 5, `asset class ${a} has only ${perAsset[a] || 0} funds`);
  // detail + tail files contain every fund of their sub-category
  const bySub = {};
  for (const r of J.rows) (bySub[r[C.sub]] = bySub[r[C.sub]] || []).push(String(r[C.code]));
  for (const [sub, list] of Object.entries(bySub)) {
    const d = JSON.parse(fs.readFileSync(path.join(OUT, 'd', sub + '.json'), 'utf8'));
    const t = JSON.parse(fs.readFileSync(path.join(OUT, 't', sub + '.json'), 'utf8'));
    for (const c of list) { ok(d[c], `detail ${sub}/${c}`); ok(t[c], `tail ${sub}/${c}`); }
  }
  // the published page must never reference backend endpoints
  const html = path.join(ROOT, 'india_mf_screener.html');
  if (fs.existsSync(html)) {
    const src = fs.readFileSync(html, 'utf8');
    // every inline script must parse — a syntax error would blank the whole page
    for (const m of src.matchAll(/<script>([\s\S]*?)<\/script>/g)) {
      try { new Function(m[1]); checks++; } catch (e) { fail(`page script does not parse: ${e.message}`); }
    }
    for (const bad of [/workers\.dev/i, /mfapi/i, /captnemo/i, /kuvera/i, /amfiindia\.com\/spages/i, /nseindia\.com\/api/i,
                       /free ai/i, /no api key/i, /powered by/i, /serverless/i, /live web search/i])
      ok(!bad.test(src), `page contains forbidden reference ${bad}`);
  }
  console.log(`Files: ${J.rows.length} funds · ${Object.entries(perAsset).map(([a, n]) => `${a} ${n}`).join(' · ')}`);
}

// mirrors mf_common.status_of
function statusOf(rec, ltp) {
  if (rec == null) return null;
  if (rec >= 70) return 'In form';
  if (rec >= 40) return 'On track';
  if (ltp != null && ltp >= 50) return 'Underperforming';
  return 'Out of track';
}

// Day-over-day audit against the previously published file (MF_PREV=<path>)
function verifyAgainstPrevious(J, C) {
  const prevPath = process.env.MF_PREV;
  if (!prevPath || !fs.existsSync(prevPath)) { console.log('Day-over-day audit: no previous file.'); return; }
  let P;
  try { P = JSON.parse(fs.readFileSync(prevPath, 'utf8')); } catch (e) { console.log('Day-over-day audit: previous file unreadable.'); return; }
  const PC = Object.fromEntries(P.cols.map((c, i) => [c, i]));
  ok(J.asOf >= P.asOf, `NAV date went backwards: ${P.asOf} → ${J.asOf}`);
  ok(Math.abs(J.rows.length - P.rows.length) <= Math.max(25, P.rows.length * 0.03), `fund count jumped ${P.rows.length} → ${J.rows.length}`);
  const prev = new Map(P.rows.map(r => [r[PC.code], r]));
  let navJumps = 0, terJumps = 0, aumJumps = 0, subMoves = 0, n = 0;
  for (const r of J.rows) {
    const q = prev.get(r[C.code]); if (!q) continue; n++;
    const asset = J.subs[r[C.sub]][0];
    if (q[PC.nav] > 0 && r[C.navDate] > q[PC.navDate]) {
      const mv = Math.abs(r[C.nav] / q[PC.nav] - 1) * 100;
      const lim = asset === 'Debt' ? 3 : 15;
      if (mv > lim) { navJumps++; if (navJumps <= 10) console.error(`! ${r[C.code]} ${r[C.name]} NAV moved ${mv.toFixed(2)}% since last publish`); }
    }
    if (q[PC.ter] != null && r[C.ter] != null && Math.abs(r[C.ter] - q[PC.ter]) > 0.75) terJumps++;
    if ('aum' in PC && q[PC.aum] > 50 && r[C.aum] != null && (r[C.aum] / q[PC.aum] > 3 || r[C.aum] / q[PC.aum] < 0.33)) aumJumps++;
    // a renamed or newly split category is not a move; only funds whose old category still exists count
    if (q[PC.sub] !== r[C.sub] && J.subs[q[PC.sub]]) subMoves++;
  }
  ok(navJumps <= Math.max(3, n * 0.005), `${navJumps} funds with implausible NAV moves since the last publish`);
  ok(terJumps <= Math.max(10, n * 0.02), `${terJumps} expense ratios changed by more than 0.75 points`);
  ok(aumJumps <= Math.max(15, n * 0.03), `${aumJumps} fund sizes changed more than 3x`);
  if ((P.rules || 0) !== (J.rules || 0)) console.log(`Category rules updated (v${P.rules || 0} → v${J.rules}): ${subMoves} intentional category moves accepted`);
  else ok(subMoves <= Math.max(5, n * 0.01), `${subMoves} funds changed category`);
  AUDIT.dayOverDay = {vs: P.asOf, compared: n, navJumps, terJumps, aumJumps, categoryMoves: subMoves};
  console.log(`Day-over-day audit vs ${P.asOf}: ${n} funds compared · NAV jumps ${navJumps} · TER jumps ${terJumps} · AUM jumps ${aumJumps} · category moves ${subMoves}`);
}

// portfolio holdings (data/mf/p/<sub>.json) — built monthly from fund-house disclosures
const EQUITY_DIRECT = new Set(['large', 'largemid', 'mid', 'small', 'multi', 'flexi', 'focused', 'value', 'contra', 'elss', 'dividend',
  'idx_large', 'idx_midsmall', 'idx_broad', 'idx_factor', 'idx_sector']);
const DEBT_DIRECT = new Set(['overnight', 'liquid', 'money', 'ultrashort', 'lowdur', 'shortdur', 'meddur', 'medlong', 'longdur', 'dynbond',
  'corpbond', 'credit', 'bankpsu', 'gilt', 'gilt10', 'floater', 'target', 'debtidx']);
function verifyHoldings() {
  const dir = path.join(OUT, 'p');
  if (!fs.existsSync(dir)) return;
  const J = JSON.parse(fs.readFileSync(path.join(OUT, 'screener.json'), 'utf8'));
  const C = Object.fromEntries(J.cols.map((c, i) => [c, i]));
  const subOf = Object.fromEntries(J.rows.map(r => [String(r[C.code]), r[C.sub]]));
  const now = new Date(J.asOf + 'T00:00:00Z');
  let funds = 0;
  for (const f of fs.readdirSync(dir).filter(n => n.endsWith('.json') && !n.startsWith('_'))) {
    const sub = f.slice(0, -5), P = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
    for (const [code, h] of Object.entries(P)) {
      funds++;
      const id = `holdings ${sub}/${code}`;
      ok(subOf[code] === sub, `${id}: fund not in this category file`);
      ok(/^\d{4}-\d{2}$/.test(h.asOf || ''), `${id}: bad month ${h.asOf}`);
      const age = (now.getUTCFullYear() - +h.asOf.slice(0, 4)) * 12 + now.getUTCMonth() + 1 - +h.asOf.slice(5, 7);
      ok(age >= 0 && age <= 4, `${id}: portfolio month ${h.asOf} is ${age} months old`);
      const listed = Object.entries(h.mix || {}).filter(([k]) => k !== 'cashOther').reduce((a, [, v]) => a + v, 0);
      ok(listed >= 40 && listed <= 130, `${id}: holdings add up to ${listed.toFixed(1)}%`);
      ok(Array.isArray(h.top) && h.top.length >= 1, `${id}: no holdings`);
      for (let i = 1; i < h.top.length; i++) ok(h.top[i][2] <= h.top[i - 1][2] + 1e-9, `${id}: holdings not sorted`);
      for (const t of h.top) ok(/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(t[3]) && t[2] > -50 && t[2] <= 105, `${id}: bad holding ${t[0]} ${t[2]}`);
      const sec = (h.sectors || []).reduce((a, x) => a + x[1], 0);
      ok(sec <= (h.mix.equity || 0) + 0.05, `${id}: sectors ${sec.toFixed(2)}% exceed equity ${h.mix.equity}%`);
      if (h.cap) {
        const capT = h.cap.large + h.cap.mid + h.cap.small;
        ok(Math.abs(capT - (h.mix.equity || 0)) < 0.1, `${id}: market-cap split ${capT.toFixed(2)}% vs equity ${h.mix.equity}%`);
      }
      ok(h.top10 <= (h.mix.equity || 0) + 0.05, `${id}: top-10 weight exceeds equity`);
      if (h.credit) ok(h.credit.reduce((a, x) => a + x[1], 0) <= (h.mix.debt || 0) + 0.1, `${id}: credit split exceeds debt share`);
      // the portfolio must fit the fund's category (guards against a sheet being matched to the wrong fund)
      const eq = (h.mix.equity || 0) + (h.mix.overseas || 0) + (h.mix.reit || 0);
      if (EQUITY_DIRECT.has(sub) || /^(sec_|idx_)/.test(sub)) ok(eq >= 60, `${id}: equity fund holds only ${eq.toFixed(1)}% equity`);
      if (DEBT_DIRECT.has(sub)) ok((h.mix.equity || 0) <= 5, `${id}: debt fund holds ${h.mix.equity}% equity`);
    }
  }
  AUDIT.holdingsFunds = funds;
  console.log(`Holdings: ${funds} fund portfolios checked`);
}

// Smart SIP model plans (data/mf/smartsip.json) — structure, diversification and satellite rules
function verifySmartSip() {
  const f = path.join(OUT, 'smartsip.json');
  if (!fs.existsSync(f)) { fail('smartsip.json missing'); return; }
  const P = JSON.parse(fs.readFileSync(f, 'utf8'));
  const J = JSON.parse(fs.readFileSync(path.join(OUT, 'screener.json'), 'utf8'));
  const C = Object.fromEntries(J.cols.map((c, i) => [c, i]));
  const rows = Object.fromEntries(J.rows.map(r => [r[C.code], r]));
  ok(Object.keys(P.plans).length === 15, `smart SIP has ${Object.keys(P.plans).length} plans`);
  ok(Math.abs(P.market.tilt) <= 10 && P.market.tilt % 5 === 0, `market tilt ${P.market.tilt}`);
  for (const [id, p] of Object.entries(P.plans)) {
    const w = p.slots.reduce((a, s) => a + s.w, 0);
    ok(w === 100, `${id}: weights add to ${w}`);
    ok(p.slots.length >= 2 && p.slots.length <= 8, `${id}: ${p.slots.length} funds`);
    const codes = p.slots.map(s => s.code);
    ok(new Set(codes).size === codes.length, `${id}: duplicate fund`);
    const amc = {};
    for (const s of p.slots) {
      const r = rows[s.code];
      ok(!!r, `${id}/${s.key}: fund ${s.code} not in screener`);
      if (!r) continue;
      amc[r[C.amc]] = (amc[r[C.amc]] || 0) + 1;
      ok(s.w >= 5, `${id}/${s.key}: weight ${s.w}`);
      ok(!(r[C.lock] > 0), `${id}/${s.key}: fund has a lock-in`);
      if (C.buy != null && r[C.buy] != null) ok(r[C.buy].includes('S'), `${id}/${s.key}: fund not accepting SIPs`);
      ok(r[C.status] !== 'Out of track', `${id}/${s.key}: fund is Out of track`);
      if (s.key === 'theme' || s.key === 'intl') {
        ok(s.w <= 10, `${id}/${s.key}: satellite weight ${s.w}`);
        ok(/^h(7|10)a$/.test(id), `${id}: satellite ${s.key} outside 7+ year aggressive plans`);
      }
      (s.alts || []).forEach(a => ok(!!rows[a], `${id}/${s.key}: alternate ${a} not in screener`));
    }
    for (const [a, n] of Object.entries(amc)) ok(n <= 2 || p.slots.length <= 3, `${id}: ${n} funds from fund house ${J.amcs[a]}`);
  }
  console.log(`Smart SIP: ${Object.keys(P.plans).length} plans checked (tilt ${P.market.tilt})`);
}
// new fund offers (data/mf/nfo.json)
function verifyNfo() {
  const f = path.join(OUT, 'nfo.json');
  if (!fs.existsSync(f)) return;                      // optional: the page shows an empty state
  const N = JSON.parse(fs.readFileSync(f, 'utf8'));
  ok(Array.isArray(N.nfos) && N.count === N.nfos.length, 'nfo.json count');
  const seen = new Set();
  for (const n of N.nfos) {
    ok(n.sid && n.name && n.amc, `NFO ${n.sid}: missing name / fund house`);
    ok(!seen.has(n.sid), `NFO ${n.sid}: duplicate`); seen.add(n.sid);
    ok(['Open', 'Closing', 'Closed'].includes(n.status), `NFO ${n.sid}: status ${n.status}`);
    ok(!n.open || /^\d{4}-\d\d-\d\d$/.test(n.open), `NFO ${n.sid}: open date ${n.open}`);
    ok(!n.close || !n.open || n.close >= n.open, `NFO ${n.sid}: closes before it opens`);
    for (const u of [n.sidDoc, n.ssdDoc, n.website]) ok(!u || /^https:\/\//.test(u) || /^http:\/\//.test(u), `NFO ${n.sid}: bad link ${u}`);
  }
  console.log(`NFO: ${N.nfos.length} offers checked`);
}

if (process.argv.includes('--holdings')) { verifyHoldings(); console.log(`${checks} checks, ${failures} failure(s).`); process.exit(failures ? 1 : 0); }
verifySample();
verifyFiles();
verifySmartSip();
verifyNfo();
// publish a compact audit record next to the data (shown on the page as a verification note)
try {
  const J = JSON.parse(fs.readFileSync(path.join(OUT, 'screener.json'), 'utf8'));
  let official = null;
  try { official = JSON.parse(fs.readFileSync(path.join(ROOT, '.mfcache', 'validation.json'), 'utf8')).vsOfficial || null; } catch (e) { /* optional */ }
  fs.writeFileSync(path.join(OUT, 'audit.json'), JSON.stringify({
    asOf: J.asOf, generated: J.generated, funds: J.rows.length, checks, failures,
    recomputedFunds: AUDIT.recomputedFunds || 0, holdingsFunds: AUDIT.holdingsFunds || 0, dayOverDay: AUDIT.dayOverDay || null, officialNav: official,
  }));
} catch (e) { console.error('could not write audit.json', e.message); }
console.log(`${checks} checks, ${failures} failure(s).`);
process.exit(failures ? 1 : 0);
