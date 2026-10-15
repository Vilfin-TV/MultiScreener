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
  }
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
    for (const bad of [/workers\.dev/i, /mfapi/i, /captnemo/i, /kuvera/i, /amfiindia\.com\/spages/i, /nseindia\.com\/api/i,
                       /free ai/i, /no api key/i, /powered by/i, /serverless/i, /live web search/i])
      ok(!bad.test(src), `page contains forbidden reference ${bad}`);
  }
  console.log(`Files: ${J.rows.length} funds · ${Object.entries(perAsset).map(([a, n]) => `${a} ${n}`).join(' · ')}`);
}

verifySample();
verifyFiles();
console.log(`${checks} checks, ${failures} failure(s).`);
process.exit(failures ? 1 : 0);
