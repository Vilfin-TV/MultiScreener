#!/usr/bin/env node
/**
 * sim_xirr.js — independent XIRR re-computation for the Simulator Buy audit (scripts/audit_sim.py).
 * stdin: [{id, flows: [[date, amount], …], xirr}] → stdout: [{id, mine, js, ok}]
 * Newton's method with a bisection fallback, actual/365 day count.
 */
'use strict';
let raw = '';
process.stdin.on('data', d => { raw += d; });
process.stdin.on('end', () => {
  const rows = JSON.parse(raw);
  const out = rows.map(r => {
    const fl = r.flows.map(([d, v]) => [Date.parse(d) / 86400000, v]);
    const js = xirr(fl);
    const ok = (js == null && r.xirr == null) || (js != null && r.xirr != null && Math.abs(js - r.xirr) < 1e-4);
    return { id: r.id, mine: r.xirr, js, ok };
  });
  process.stdout.write(JSON.stringify(out));
});

function xirr(fl) {
  if (!fl.length || !fl.some(f => f[1] > 0) || !fl.some(f => f[1] < 0)) return null;
  const t0 = Math.min(...fl.map(f => f[0]));
  const npv = r => fl.reduce((s, [t, v]) => s + v / Math.pow(1 + r, (t - t0) / 365), 0);
  const d = r => fl.reduce((s, [t, v]) => s - ((t - t0) / 365) * v / Math.pow(1 + r, (t - t0) / 365 + 1), 0);
  let r = 0.1;
  for (let i = 0; i < 100; i++) {
    const f = npv(r), df = d(r);
    if (!isFinite(f) || !isFinite(df) || df === 0) break;
    const n = r - f / df;
    if (n <= -0.9999 || !isFinite(n)) break;
    if (Math.abs(n - r) < 1e-10) return n;
    r = n;
  }
  let lo = -0.9999, hi = 10, flo = npv(lo);
  if (flo * npv(hi) > 0) return null;
  for (let i = 0; i < 300; i++) {
    const m = (lo + hi) / 2, fm = npv(m);
    if (Math.abs(fm) < 1e-9) return m;
    if (flo * fm < 0) hi = m; else { lo = m; flo = fm; }
  }
  return (lo + hi) / 2;
}
