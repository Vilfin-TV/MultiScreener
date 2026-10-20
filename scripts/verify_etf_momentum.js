#!/usr/bin/env node
/**
 * verify_etf_momentum.js
 * Independent cross-check for data/etf_momentum.json.
 *
 *  1. Structural checks (calendar, array lengths, benchmark presence, value sanity).
 *  2. Re-computes every mode with the exact RRG engine shipped in etf_momentum.html
 *     (extracted between the RRG-ENGINE markers) and compares it with the
 *     reference values produced by scripts/build_etf_momentum.py.
 *
 * Exit code 1 on any failure so the workflow never publishes inconsistent data.
 * Usage: node scripts/verify_etf_momentum.js [data/etf_momentum.json] [etf_momentum.html]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const dataPath = process.argv[2] || path.join(ROOT, 'data', 'etf_momentum.json');
const htmlPath = process.argv[3] || path.join(ROOT, 'etf_momentum.html');

const errors = [];
const warn = [];
function fail(msg) { errors.push(msg); }

const html = fs.readFileSync(htmlPath, 'utf8');
const m = html.match(/\/\*RRG-ENGINE-START\*\/([\s\S]*?)\/\*RRG-ENGINE-END\*\//);
if (!m) { console.error('RRG engine markers not found in page'); process.exit(1); }
const ctx = {};
vm.createContext(ctx);
vm.runInContext(m[1] + '\nthis.RRG = RRG;', ctx);
const RRG = ctx.RRG;

const D = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
const P = D.params || {};
const W = (D.weeks || []).length;

// ── 1. structure ──
if (!W || W < 60) fail(`weeks too short: ${W}`);
for (let i = 1; i < W; i++) if (!(D.weeks[i] > D.weeks[i - 1])) { fail(`week calendar not increasing at ${i}`); break; }
if (D.asOf !== D.weeks[W - 1]) fail(`asOf ${D.asOf} != last week ${D.weeks[W - 1]}`);
const benchIds = new Set();
for (const b of D.benchmarks || []) {
  if (benchIds.has(b.id)) fail(`duplicate benchmark ${b.id}`);
  benchIds.add(b.id);
  if (!Array.isArray(b.c) || b.c.length !== W) fail(`benchmark ${b.id} length ${b.c && b.c.length} != ${W}`);
  else {
    const valid = b.c.filter(v => v != null && v > 0).length;
    if (valid < W * 0.9) fail(`benchmark ${b.id} has only ${valid}/${W} valid weeks`);
  }
}
if (!benchIds.has(P.defaultBench)) fail(`default benchmark ${P.defaultBench} missing`);

const syms = new Set();
let jumps = 0;
for (const e of D.etfs || []) {
  if (!e.s || syms.has(e.s)) fail(`missing/duplicate symbol ${e.s}`);
  syms.add(e.s);
  if (e.q === 'nodata') continue;
  if (!Array.isArray(e.c) || e.c.length !== W) { fail(`${e.s} length ${e.c && e.c.length} != ${W}`); continue; }
  if (!(e.p > 0)) fail(`${e.s} invalid last price ${e.p}`);
  for (let i = 1; i < W; i++) {
    const a = e.c[i - 1], b = e.c[i];
    if (a != null && b != null && (b / a > 3 || a / b > 3)) { jumps++; warn.push(`${e.s} weekly jump ${a}→${b} at ${D.weeks[i]}`); break; }
  }
}

// ── 2. engine parity ──
const bench = (D.benchmarks || []).find(b => b.id === P.defaultBench);
const ref = (D.ref || {})[P.defaultBench] || {};
let checked = 0, mismatch = 0;
const counts = { A: 0, D: 0, R: 0, U: 0 };
if (bench) {
  for (const e of D.etfs) {
    if (['nodata', 'stale', 'short'].includes(e.q) || !e.c || !e.c.length) {
      if (ref[e.s]) { mismatch++; fail(`${e.s} unclassifiable but present in reference`); }
      continue;
    }
    const s = RRG.series(e.c, bench.c, P.nRatio, P.nMom, P.floorRatio, P.floorMom);
    const L = e.c.length, r = s.rsr[L - 1], mo = s.rsm[L - 1], md = RRG.mode(r, mo);
    const x = ref[e.s];
    if (!md && !x) continue;
    checked++;
    if (md) counts[md]++;
    if (!md || !x || md !== x[2] || Math.abs(r - x[0]) > 1e-3 || Math.abs(mo - x[1]) > 1e-3) {
      mismatch++;
      if (mismatch <= 10) fail(`${e.s}: page=${md} ${r && r.toFixed(4)}/${mo && mo.toFixed(4)} ref=${x && x.join('/')}`);
    }
  }
}
const st = D.stats || {};
for (const k of ['A', 'D', 'R', 'U']) if (st.counts && st.counts[k] !== counts[k]) fail(`count ${k}: stats=${st.counts[k]} recomputed=${counts[k]}`);
if (checked < 40) fail(`only ${checked} ETFs classified`);
// long-horizon returns, risk and official facts: plausibility
let withLong = 0;
for (const e of D.etfs || []) {
  const r = e.r || {};
  for (const [k, lim] of [['1d', 25], ['1y', 300], ['3y', 120], ['5y', 100], ['10y', 80]])
    if (r[k] != null && !(Math.abs(r[k]) <= lim)) fail(`${e.s}: implausible ${k} return ${r[k]}`);
  if (r['3y'] != null) withLong++;
  if (e.vol != null && !(e.vol >= 0 && e.vol < 150)) fail(`${e.s}: volatility ${e.vol}`);
  if (e.mdd != null && !(e.mdd <= 0 && e.mdd >= -100)) fail(`${e.s}: drawdown ${e.mdd}`);
  if (e.prem != null && !(Math.abs(e.prem) < 25)) fail(`${e.s}: premium ${e.prem}`);
  if (e.x && e.x.ter != null && !(e.x.ter >= 0 && e.x.ter <= 2.6)) fail(`${e.s}: expense ratio ${e.x.ter}`);
}
if (withLong < 50) fail(`only ${withLong} ETFs have a 3-year return`);
const histFile = path.join(path.dirname(dataPath), 'etf_hist.json');
if (fs.existsSync(histFile)) {
  const H = JSON.parse(fs.readFileSync(histFile, 'utf8'));
  if (!H.weeks || H.weeks.length < 200) fail(`etf_hist weeks ${H.weeks && H.weeks.length}`);
  for (const [s, a] of Object.entries(H.etfs || {})) if (a.length !== H.weeks.length) { fail(`etf_hist ${s} length`); break; }
  if (H.asOf !== D.asOf) fail(`etf_hist asOf ${H.asOf} != ${D.asOf}`);
} else fail('etf_hist.json missing');
// ── 3. ETF analytics (scorecard, rating, Factor DNA, holdings) and daily bars ──
const root = path.dirname(dataPath);
const exFile = path.join(root, 'etf_extras.json'), hoFile = path.join(root, 'etf_holdings.json');
if (fs.existsSync(exFile)) {
  const X = JSON.parse(fs.readFileSync(exFile, 'utf8')), XE = X.etfs || {};
  if (X.asOf !== D.asOf) warn.push(`etf_extras asOf ${X.asOf} != ${D.asOf}`);
  let nSc = 0, nRt = 0, nF = 0;
  for (const [s, o] of Object.entries(XE)) {
    if (!syms.has(s)) fail(`etf_extras: unknown ETF ${s}`);
    for (const v of ['3', '5']) {
      const c = o.sc && o.sc[v]; if (!c) continue; nSc++;
      for (const k of ['c', 'r', 'v', 'o']) if (!(c[k] >= 0 && c[k] <= 100)) fail(`${s}: scorecard ${v}Y ${k} = ${c[k]}`);
      if (Math.abs(0.4 * c.c + 0.3 * c.r + 0.3 * c.v - c.o) > 0.15) fail(`${s}: scorecard ${v}Y overall ${c.o} != 40/30/30 mix`);
      if (!(c.rk >= 1 && c.rk <= c.n && c.n >= 5)) fail(`${s}: scorecard rank ${c.rk}/${c.n}`);
    }
    if (o.rt) { nRt++;
      if (!(o.rt.st >= 1 && o.rt.st <= 5)) fail(`${s}: stars ${o.rt.st}`);
      if (!(o.rt.s >= 0 && o.rt.s <= 100) || !(o.rt.rk >= 1 && o.rt.rk <= o.rt.n)) fail(`${s}: rating ${o.rt.s} rank ${o.rt.rk}/${o.rt.n}`);
      const W8 = X.ratingW || {}, have = Object.keys(o.rt.p || {});
      if (have.length < 4 || have.indexOf('ret') < 0) fail(`${s}: rating built from ${have.join(',')}`);
      const mix = have.reduce((t, k) => t + W8[k] * o.rt.p[k], 0) / have.reduce((t, k) => t + W8[k], 0);
      if (Math.abs(mix - o.rt.s) > 1.01) fail(`${s}: rating ${o.rt.s} != weighted parts ${mix.toFixed(1)}`);
    }
    if (o.f) { nF++;
      const sum = Object.values(o.f.w).reduce((a, b) => a + b, 0);
      if (Math.abs(sum - 100) > 1) fail(`${s}: factor weights sum ${sum}`);
      if (!(o.f.r2 >= -50 && o.f.r2 <= 100)) fail(`${s}: factor R² ${o.f.r2}`);
    }
  }
  const byStar = {}; Object.values(XE).forEach(o => { if (o.rt) byStar[o.rt.st] = (byStar[o.rt.st] || 0) + 1; });
  if (nRt < 100) fail(`only ${nRt} ETFs rated`);
  if (nSc < 60) fail(`only ${nSc} scorecards`);
  if (nF < 60) fail(`only ${nF} ETFs with Factor DNA`);
  console.log(`analytics: scorecards ${nSc} · ratings ${nRt} ${JSON.stringify(byStar)} · Factor DNA ${nF}`);
  if (fs.existsSync(hoFile)) {
    const HO = JSON.parse(fs.readFileSync(hoFile, 'utf8')).etfs || {};
    const now = Date.parse(D.asOf);
    for (const [s, h] of Object.entries(HO)) {
      if (!syms.has(s)) fail(`etf_holdings: unknown ETF ${s}`);
      for (let i = 1; i < (h.top || []).length; i++) if (h.top[i][2] > h.top[i - 1][2] + 1e-9) { fail(`${s}: holdings not sorted`); break; }
      const eq = (h.mix.equity || 0) + (h.mix.overseas || 0);
      if (eq < 60) fail(`${s}: holdings only ${eq}% equity`);
      const [y, m] = h.asOf.split('-').map(Number), end = Date.UTC(y, m, 1);
      if ((now - end) / 864e5 + 1 > 46) fail(`${s}: portfolio ${h.asOf} older than 45 days`);
      if (h.src !== 'own' && h.src !== 'index') fail(`${s}: holdings source ${h.src}`);
      if (h.src === 'index' && !h.proxyName) fail(`${s}: index holdings without a source fund`);
    }
    console.log(`holdings: ${Object.keys(HO).length} ETFs (own ${Object.values(HO).filter(h => h.src === 'own').length})`);
  } else fail('etf_holdings.json missing');
} else fail('etf_extras.json missing');
// ── 4. Smart Invest for ETFs ──
const smFile = path.join(root, 'etf_smart.json');
if (fs.existsSync(smFile)) {
  const SMJ = JSON.parse(fs.readFileSync(smFile, 'utf8'));
  const etfBy = {}; (D.etfs || []).forEach(e => { etfBy[e.s] = e; });
  for (const [k, sl] of Object.entries(SMJ.slots || {})) {
    const e = etfBy[sl.sym];
    if (!e) { fail(`smart: slot ${k} uses unknown ETF ${sl.sym}`); continue; }
    if (!(e.tv > 0)) fail(`smart: ${k} ${sl.sym} has no trading`);
    const ck = Object.fromEntries((sl.checks || []).map(c => [c[0], c[1]]));
    if (sl.state === 'ok' && (sl.checks || []).some(c => !c[1])) fail(`smart: ${k} ${sl.sym} marked ok but fails a check`);
    if (!ck['Liquidity'] || !ck['Traded every day'] || !ck['Price close to NAV']) fail(`smart: ${k} ${sl.sym} fails liquidity / trading / price-vs-NAV`);
    if (!(sl.er > 0 && sl.er < 20)) fail(`smart: ${k} expected return ${sl.er}`);
    if (!['equity', 'other', 'debt'].includes(sl.tax)) fail(`smart: ${k} tax class ${sl.tax}`);
  }
  const plans = Object.entries(SMJ.plans || {});
  if (plans.length !== 20) fail(`smart: ${plans.length} plans (expected 20)`);
  for (const [pid, p] of plans) {
    const tot = p.slots.reduce((t, s) => t + s.w, 0);
    if (tot !== 100) fail(`smart: ${pid} weights add up to ${tot}`);
    for (const s of p.slots) {
      if (!SMJ.slots[s.id]) fail(`smart: ${pid} slot ${s.id} missing`);
      if (s.w % 5 || s.w <= 0) fail(`smart: ${pid} ${s.id} weight ${s.w}`);
    }
    const mix = p.mix || {};
    if (pid.slice(0, 2) !== 'h1' && (!(mix.Equity >= 5) || !(mix.Debt >= 5) || !(mix.Commodity >= 5))) fail(`smart: ${pid} not diversified ${JSON.stringify(mix)}`);
    const er = p.slots.reduce((t, s) => t + s.w * SMJ.slots[s.id].er, 0) / 100;
    if (Math.abs(er - p.er) > 0.02) fail(`smart: ${pid} expected return ${p.er} != weighted ${er.toFixed(2)}`);
  }
  const eqOf = pid => (SMJ.plans[pid] || {}).mix ? (SMJ.plans[pid].mix.Equity || 0) + (SMJ.plans[pid].mix.Global || 0) : 0;
  for (const hz of ['h3', 'h5', 'h7', 'h10']) if (!(eqOf(hz + 'c') <= eqOf(hz + 'b') && eqOf(hz + 'b') <= eqOf(hz + 'a') + 5)) fail(`smart: ${hz} equity not rising with risk`);
  // market-dip lump sums: 7 trigger checks per segment, 19 ETF checks per candidate, 26 per plan entry, tier amounts
  const dp = SMJ.dip || {}, rule = dp.rule || {}, tiers = (rule.tiers || []).slice().sort((a, b) => b[0] - a[0]);
  if (!dp.segments || !tiers.length) fail('smart: dip block missing');
  for (const [k, sg] of Object.entries(dp.segments || {})) {
    const t = tiers.find(x => sg.fall >= x[0]), want = t ? [t[0], Math.max(rule.min, Math.min(rule.max, t[1]))] : [0, 0];
    if (sg.tier !== want[0] || sg.amount !== want[1]) fail(`smart: dip ${k} tier/amount ${sg.tier}/${sg.amount} vs ${want}`);
    if ((sg.checks || []).length !== 7 || (sg.signal && sg.checks.some(c => !c[1]))) fail(`smart: dip ${k} trigger checks`);
  }
  const dc = dp.cands || [];
  dc.forEach((c, i) => { if (c.checks.length !== 19 || c.fundOk !== c.checks.slice(0, 18).every(x => x[1]) || !etfBy[c.sym]) fail(`smart: dip candidate ${i} ${c.sym}`); });
  if (!dp.reserve || !etfBy[dp.reserve.sym]) fail('smart: dip reserve ETF unknown');
  for (const [pid, ents] of Object.entries(dp.plans || {})) {
    const ids = new Set(((SMJ.plans[pid] || {}).slots || []).map(s => s.id));
    for (const [seg, x] of Object.entries(ents)) {
      const c = dc[x.c], all = ((dp.segments[seg] || {}).checks || []).concat(c ? c.checks : []);
      if (!c || c.seg !== seg || !ids.has(c.slot) || (SMJ.slots[c.slot] || {}).sym !== c.sym || x.n !== 26 || all.length !== 26 ||
          x.passed !== all.filter(y => y[1]).length || x.ok !== all.every(y => y[1])) fail(`smart: dip ${pid} ${seg} entry`);
    }
  }
  console.log(`smart invest: ${plans.length} plans · ${Object.keys(SMJ.slots || {}).length} ETF slots · dip ${Object.keys(dp.segments || {}).length} segments / ${dc.length} candidates`);
} else fail('etf_smart.json missing');
const dDir = path.join(root, 'etf', 'd');
if (fs.existsSync(dDir)) {
  let nD = 0, cur = 0;
  const last = {}; (D.etfs || []).forEach(e => { last[e.s] = e.d; });
  for (const fn of fs.readdirSync(dDir)) {
    if (!fn.endsWith('.json')) continue;
    const B = JSON.parse(fs.readFileSync(path.join(dDir, fn), 'utf8')), n = B.t.length; nD++;
    if (!syms.has(B.s)) fail(`daily bars for unknown ETF ${B.s}`);
    if ([B.o, B.h, B.l, B.c, B.v].some(a => a.length !== n)) { fail(`${B.s}: daily bar arrays differ in length`); continue; }
    for (let i = 0; i < n; i++) {
      if (i && !(B.t[i] > B.t[i - 1])) { fail(`${B.s}: daily dates not increasing`); break; }
      if (!(B.h[i] >= Math.max(B.o[i], B.c[i]) - 1e-6 && B.l[i] <= Math.min(B.o[i], B.c[i]) + 1e-6 && B.l[i] > 0)) { fail(`${B.s}: bad bar on ${B.t[i]}`); break; }
    }
    const ld = String(B.t[n - 1]); if (last[B.s] === ld.slice(0, 4) + '-' + ld.slice(4, 6) + '-' + ld.slice(6)) cur++;
  }
  if (nD < 100) fail(`daily bars for only ${nD} ETFs`);
  else if (cur < nD * 0.9) fail(`daily bars current for only ${cur}/${nD} ETFs`);
  console.log(`daily bars: ${nD} ETFs (${cur} current)`);
} else warn.push('data/etf/d not built yet — trading chart unavailable until the next ETF build');
if (jumps > (D.etfs || []).length * 0.05) fail(`too many suspicious weekly jumps: ${jumps}`);

console.log(`ETFs: ${(D.etfs || []).length} · weeks: ${W} · benchmarks: ${[...benchIds].join(', ')}`);
console.log(`classified (default bench): ${checked} · mismatches: ${mismatch} · counts: ${JSON.stringify(counts)}`);
if (warn.length) console.log(`warnings (${warn.length}):\n  ` + warn.slice(0, 15).join('\n  '));
if (errors.length) { console.error(`FAILED (${errors.length}):\n  ` + errors.slice(0, 25).join('\n  ')); process.exit(1); }
console.log('OK — page engine and reference data agree.');
