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
    const s = RRG.series(e.c, bench.c, P.nRatio, P.nMom);
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
if (jumps > (D.etfs || []).length * 0.05) fail(`too many suspicious weekly jumps: ${jumps}`);

console.log(`ETFs: ${(D.etfs || []).length} · weeks: ${W} · benchmarks: ${[...benchIds].join(', ')}`);
console.log(`classified (default bench): ${checked} · mismatches: ${mismatch} · counts: ${JSON.stringify(counts)}`);
if (warn.length) console.log(`warnings (${warn.length}):\n  ` + warn.slice(0, 15).join('\n  '));
if (errors.length) { console.error(`FAILED (${errors.length}):\n  ` + errors.slice(0, 25).join('\n  ')); process.exit(1); }
console.log('OK — page engine and reference data agree.');
