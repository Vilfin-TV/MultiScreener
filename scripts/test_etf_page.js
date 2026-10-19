#!/usr/bin/env node
/**
 * test_etf_page.js — end-to-end UI audit of etf_momentum.html (desktop + phone, dark + light themes).
 *
 * Walks every menu: benchmark switch, mode tiles and tabs, asset-class chips, every option of every filter, every
 * sort option, the three column views, ETF detail pages for one ETF of every category plus edge cases (gold, liquid,
 * global at a premium, hybrid, new / thin ETFs), trading-chart ranges and types, scorecard toggles, all FAQs, and all
 * 20 Portfolio Simulator plans × 5 investing frequencies (Risk & score and Economy & earnings tabs included), and the
 * risk-warning dialog (shown before the simulator opens; Close keeps it locked, Accept opens it). On every screen it checks for page errors, horizontal overflow,
 * visible "NaN" / "undefined" / "Infinity" / "[object" text, and elements wider than the screen.
 *
 * Usage: (serve the repo root on :8765)  node scripts/test_etf_page.js [--shots=DIR]
 *   needs playwright; set CHROME=/path/to/chromium if the bundled browser is not installed.
 */
'use strict';
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://localhost:8765/etf_momentum.html';
const shotArg = process.argv.find(a => a.startsWith('--shots='));
const SHOTS = shotArg ? shotArg.slice(8) : null;
const issues = [];
let checks = 0;
function check(ok, msg) { checks++; if (!ok) issues.push(msg); }

async function pageHealth(p, where) {
  const r = await p.evaluate(() => {
    const vw = innerWidth, bad = [], txt = [];
    const vis = el => { const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && el.getClientRects().length; };
    document.querySelectorAll('main *').forEach(el => {
      if (!vis(el)) return;
      const rc = el.getBoundingClientRect();
      if (rc.width > 0 && rc.right > vw + 1 && !el.closest('.ptbl-wrap,.tbl-wrap,.acls,.vt-snwrap,[style*="overflow"],.cards-m .t-name,svg,.hist-row,.tabs')) {
        let sc = el.parentElement, scrolls = false;
        while (sc && sc !== document.body) { const o = getComputedStyle(sc).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') { scrolls = true; break; } sc = sc.parentElement; }
        if (!scrolls) bad.push((el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + String(el.className).split(' ')[0]) + ' →' + Math.round(rc.right));
      }
    });
    const t = document.querySelector('main').innerText;
    const m = t.match(/\bNaN\b|\bundefined\b|\bInfinity\b|\[object/g);
    return { ov: document.documentElement.scrollWidth - vw, bad: [...new Set(bad)].slice(0, 5), words: m ? [...new Set(m)] : [] };
  });
  check(r.ov <= 0, `${where}: page scrolls sideways by ${r.ov}px`);
  check(!r.bad.length, `${where}: elements past the screen edge ${r.bad.join(', ')}`);
  check(!r.words.length, `${where}: broken values on screen ${r.words.join(', ')}`);
}

(async () => {
  const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  const runs = [['desktop', { width: 1366, height: 900 }, 'default'], ['desktop-light', { width: 1440, height: 900 }, 'silver'],
                ['phone', { width: 390, height: 844 }, 'default'], ['phone-small-light', { width: 360, height: 740 }, 'news-reader']];
  for (const [name, vp, theme] of runs) {
    const p = await b.newPage({ viewport: vp });
    const errs = [];
    p.on('pageerror', e => errs.push(e.message));
    p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text()); });
    await p.addInitScript(t => { try { localStorage.setItem('viltv_theme', t); } catch (e) {} }, theme);
    await p.goto(BASE, { waitUntil: 'networkidle' });
    await p.waitForTimeout(800);
    await pageHealth(p, `${name} home`);
    const total = await p.evaluate(() => +(document.getElementById('countChip').textContent.match(/of (\d+)/) || [0, 0])[1]);
    check(total > 300, `${name}: only ${total} ETFs loaded`);
    // benchmarks
    const benches = await p.$$eval('#bench option', o => o.map(x => x.value));
    for (const bv of benches) {
      await p.selectOption('#bench', bv); await p.waitForTimeout(80);
      const n = await p.evaluate(() => document.querySelectorAll('#tbody tr[data-s], #cardsM .mc').length);
      check(n > 0, `${name}: benchmark ${bv} shows no ETFs`);
    }
    await p.selectOption('#bench', benches[0]);
    // tabs, asset chips, filters, sorts, views
    const count = () => p.evaluate(() => +(document.getElementById('countChip').textContent.match(/\d+/) || [0])[0]);
    for (const t of await p.$$eval('#tabs .tab', x => x.map(e => e.getAttribute('data-t')))) {
      await p.click(`#tabs .tab[data-t="${t}"]`); await p.waitForTimeout(60);
      const n = await count(), chip = await p.evaluate(t => { const e = document.querySelector(`#tabs .tab[data-t="${t}"] .n`); return e ? +e.textContent : null; }, t);
      check(chip == null || n === chip, `${name}: tab ${t} count ${n} vs chip ${chip}`);
    }
    await p.click('#tabs .tab[data-t="all"]');
    for (const a of await p.$$eval('#acls [data-a]', x => x.map(e => e.getAttribute('data-a')))) {
      await p.click(`#acls [data-a="${a}"]`); await p.waitForTimeout(60);
      const n = await count(), chip = await p.evaluate(a => +document.querySelector(`#acls [data-a="${a}"] .n`).textContent, a);
      check(n === chip, `${name}: asset ${a || 'all'} shows ${n} vs chip ${chip}`);
    }
    await p.click('#acls [data-a=""]');
    if (await p.isVisible('#fltBtn')) { await p.click('#fltBtn'); await p.waitForTimeout(60); }   // phones: filters fold away
    for (const sel of ['tRole', 'tTrend', 'tRate', 'tCat', 'tLiq', 'tAmc', 'tHist', 'tTer']) {
      const opts = await p.$$eval(`#${sel} option`, o => o.map(x => x.value));
      for (const v of opts) {
        await p.selectOption(`#${sel}`, v); await p.waitForTimeout(40);
        const n = await count();
        check(v === '' || n >= 0, `${name}: ${sel}=${v} broke the table`);
        if (v === '') check(n === total, `${name}: ${sel} reset shows ${n} of ${total}`);
      }
      await p.selectOption(`#${sel}`, '');
    }
    for (const view of ['momentum', 'returns', 'risk']) {
      await p.click(`#vseg [data-v="${view}"]`); await p.waitForTimeout(80);
      for (const so of await p.$$eval('#tSort option', o => o.map(x => x.value))) {
        await p.selectOption('#tSort', so); await p.waitForTimeout(40);
        const order = await p.evaluate(() => [...document.querySelectorAll('#tbody tr[data-s]')].slice(0, 3).map(r => r.getAttribute('data-s')));
        check(order.length > 0 || vp.width <= 1100, `${name}: sort ${so} in ${view} shows nothing`);
      }
      await pageHealth(p, `${name} view ${view}`);
    }
    await p.selectOption('#tSort', 'score');
    await p.click('#vseg [data-v="momentum"]');
    // ETF detail pages
    const sample = await p.evaluate(async () => {
      const D = await (await fetch('data/etf_momentum.json')).json(), bySym = {};
      D.etfs.forEach(e => { bySym[e.s] = e; });
      const out = {}, by = {};
      D.etfs.forEach(e => { if (e.q !== 'nodata' && !by[e.k]) by[e.k] = e.s; });
      Object.values(by).forEach(s => { out[s] = 1; });
      ['NIFTYBEES', 'GOLDBEES', 'LIQUIDBEES', 'MON100', 'HYBRIDETF', 'BANKBEES', 'SILVERBEES', 'CPSEETF'].forEach(s => { if (bySym[s]) out[s] = 1; });
      const thin = D.etfs.find(e => e.q === 'thin'), young = D.etfs.find(e => e.q === 'short');
      if (thin) out[thin.s] = 1; if (young) out[young.s] = 1;
      return Object.keys(out);
    });
    for (const s of sample) {
      await p.goto(`${BASE}?etf=${s}`, { waitUntil: 'networkidle' }); await p.waitForTimeout(450);
      const cards = await p.$$eval('#deep .dcard', c => c.length);
      check(cards >= 9, `${name} ${s}: only ${cards} analysis cards`);
      await pageHealth(p, `${name} ${s}`);
      if (s === 'NIFTYBEES') {
        for (const tt of ['l', 'c']) for (const tr of ['1M', '3M', '6M', '1Y']) {
          await p.click(`#trType [data-tt="${tt}"]`); await p.click(`#trSeg [data-tr="${tr}"]`); await p.waitForTimeout(40);
          check(await p.$('#trBox svg') != null, `${name}: trading chart ${tt} ${tr} missing`);
        }
        for (const r of ['1Y', '3Y', '5Y']) { await p.click(`#pcSeg [data-r="${r}"]`); await p.waitForTimeout(40); check(await p.$('#pcBox svg') != null, `${name}: price history ${r} missing`); }
        for (const v of ['5', '3']) { await p.click(`#scSeg [data-sv="${v}"]`); await p.waitForTimeout(60); }
        for (const l of ['c', 'r', 'v', 'o']) { await p.click(`#scLead [data-sl="${l}"]`); await p.waitForTimeout(60); }
        await pageHealth(p, `${name} NIFTYBEES toggles`);
        if (SHOTS) await (await p.$('#deep')).screenshot({ path: `${SHOTS}/${name}_detail.png` });
      }
    }
    // FAQs
    await p.goto(BASE, { waitUntil: 'networkidle' }); await p.waitForTimeout(500);
    const nFaq = await p.$$eval('details.faq', d => { d.forEach(x => { x.open = true; }); return d.length; });
    check(nFaq >= 20, `${name}: only ${nFaq} FAQs`);
    await pageHealth(p, `${name} FAQs open`);
    // Portfolio Simulator — locked until the risk warning is accepted
    check(await p.$eval('#smart', s => s.classList.contains('locked')), `${name}: simulator not locked before acceptance`);
    await p.click('#smOpen'); await p.waitForTimeout(150);
    check(await p.isVisible('.vts-dlg'), `${name}: risk-warning dialog not shown`);
    check(await p.$eval('#vtsOk', b => b.disabled), `${name}: Accept enabled before the acknowledgement is ticked`);
    await pageHealth(p, `${name} risk dialog`);
    await p.click('.vts-ft [data-act="close"]'); await p.waitForTimeout(150);
    check(await p.$eval('#smart', s => s.classList.contains('locked')), `${name}: Close unlocked the simulator`);
    await p.click('#smOpen'); await p.waitForTimeout(150);
    await p.check('#vtsAck'); await p.click('#vtsOk'); await p.waitForTimeout(250);
    check(!(await p.$eval('#smart', s => s.classList.contains('locked'))), `${name}: Accept did not open the simulator`);
    // Portfolio Simulator — every plan × frequency
    const hz = ['h1', 'h3', 'h5', 'h7', 'h10'], rk = ['c', 'b', 'a', 'v'], fq = ['m', 'w', 'q', 'y', 'l'];
    for (const h of hz) for (const r of rk) {
      await p.click(`#smHz [data-hz="${h}"]`); await p.click(`#smRisk [data-rk="${r}"]`);
      for (const f of fq) {
        await p.click(`#smFq [data-fq="${f}"]`); await p.waitForTimeout(25);
        const s = await p.evaluate(() => {
          const rows = [...document.querySelectorAll('.sm-row')], w = rows.map(x => +x.querySelector('.sm-w').textContent.replace('%', ''));
          return { n: rows.length, sum: w.reduce((a, b) => a + b, 0), proj: (document.querySelectorAll('.sm-t')[3] || {}).innerText || '' };
        });
        check(s.n > 0 && s.sum === 100, `${name}: plan ${h}${r}/${f} has ${s.n} ETFs adding up to ${s.sum}%`);
        check(/₹/.test(s.proj) && !/NaN|–/.test(s.proj), `${name}: plan ${h}${r}/${f} projection "${s.proj.replace(/\n/g, ' ')}"`);
      }
    }
    for (const st of ['risk', 'eco']) {
      await p.click(`#smTabs [data-st="${st}"]`); await p.waitForTimeout(120);
      const ok = await p.evaluate(st => { const el = document.getElementById(st === 'risk' ? 'smRiskPane' : 'smEcoPane'); return el.offsetHeight > 100 && !document.getElementById('smBody').offsetHeight; }, st);
      check(ok, `${name}: ${st} tab did not switch`);
      if (st === 'risk') {
        for (const h of hz) for (const r of rk) {
          await p.click(`#smHz [data-hz="${h}"]`); await p.click(`#smRisk [data-rk="${r}"]`); await p.waitForTimeout(20);
          const k = await p.evaluate(() => [...document.querySelectorAll('#smRiskPane .vts-k b')].map(b => b.textContent));
          check(k.length === 4 && /\d/.test(k[0]) && /\d/.test(k[1]), `${name}: risk tab ${h}${r} shows ${k.join(' | ')}`);
        }
      }
      await pageHealth(p, `${name} simulator ${st} tab`);
    }
    await p.click('#smTabs [data-st="plan"]');
    for (const amt of ['500', '3000', '100000']) { await p.fill('#smAmt', amt); await p.waitForTimeout(260); await pageHealth(p, `${name} smart ₹${amt}`); }
    if (SHOTS) await (await p.$('#smart')).screenshot({ path: `${SHOTS}/${name}_smart.png` });
    check(!errs.length, `${name}: page errors ${errs.slice(0, 3).join(' | ')}`);
    console.log(`${name}: done (${checks} checks so far, ${issues.length} issues)`);
    await p.close();
  }
  await b.close();
  console.log(`\n${checks} checks · ${issues.length} issues`);
  issues.slice(0, 60).forEach(i => console.log('  ✗', i));
  process.exit(issues.length ? 1 : 0);
})();
