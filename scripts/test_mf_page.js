// UI + data test of india_mf_screener.html: every asset class and category, every filter option (count and every
// listed fund checked against an independent re-computation from data/mf/screener.json), status cards, fund-house
// strip, every sortable column, presets, return periods, "Show more", combined filters, a fund of every category on
// every detail tab, Compare, NFO filters, Portfolio Simulator tabs and FAQs — at desktop and phone sizes in dark and
// light themes, checking page errors, sideways overflow and "NaN / undefined" text.
// Needs the repo served on :8765 (python3 -m http.server 8765). CHROME=<path> for a custom browser.
const { chromium } = require('playwright');
const fs = require('fs');
const B = 'http://localhost:8765/india_mf_screener.html';
const D = JSON.parse(fs.readFileSync('data/mf/screener.json'));
const NFO = JSON.parse(fs.readFileSync('data/mf/nfo.json'));
const C = Object.fromEntries(D.cols.map((c, i) => [c, i]));
const dnum = s => Math.round(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / 86400000);
const isNum = v => typeof v === 'number' && isFinite(v);
// independent model of the fund list
const F = D.rows.map(r => {
  const f = Object.fromEntries(D.cols.map((c, i) => [c, r[i]]));
  f.asset = D.subs[f.sub][0]; f.amcName = D.amcs[f.amc];
  f.search = (f.name + ' ' + f.amcName + ' ' + D.subs[f.sub][1] + ' ' + f.asset).toLowerCase();
  f.ageY = (dnum(D.asOf) - dnum(f.inc)) / 365.25;
  return f;
});
const BYC = Object.fromEntries(F.map(f => [f.code, f]));
const buy = f => f.buy == null ? null : f.buy === '' ? 'paused' : /L/.test(f.buy) && /S/.test(f.buy) ? 'open' : /S/.test(f.buy) ? 'sip' : 'lump';
const FILT = {
  amc: (f, v) => f.amc === +v,
  rating: (f, v) => f.rating >= +v,
  hist: (f, v) => f.ageY >= +v,
  ter: (f, v) => isNum(f.ter) && f.ter <= +v,
  risk: (f, v) => f.risk === +v,
  status: (f, v) => f.status === v,
  buy: (f, v) => { const b = buy(f); return v === 'open' ? b === 'open' : v === 'sip' ? (b === 'open' || b === 'sip') : b === 'paused'; },
  text: (f, v) => v.toLowerCase().split(/\s+/).filter(Boolean).every(t => f.search.includes(t)),
};
const SEL = { amc: 'fAmc', rating: 'fRating', hist: 'fHist', ter: 'fTer', risk: 'fRisk', status: 'fStatus', buy: 'fBuy' };
const EMPTY = { amc: '', rating: '0', hist: '0', ter: '0', risk: '', status: '', buy: '' };
const expect = (scope, flt) => F.filter(f => (scope.sub ? f.sub === scope.sub : f.asset === scope.asset) &&
  Object.entries(flt).every(([k, v]) => v === '' || v === '0' || v == null || FILT[k](f, v)));
const bad = t => (t.match(/.{0,40}\b(NaN|undefined|Infinity|\[object Object\])\b.{0,30}/) || [null])[0];
const ASSETS = [...new Set(F.map(f => f.asset))];
const subsOf = a => [...new Set(F.filter(f => f.asset === a).map(f => f.sub))];

(async () => {
  const br = await chromium.launch({ executablePath: process.env.CHROME || undefined });
  const issues = []; let checks = 0;
  const VP = [[1366, 900, 'dark', 'desktop'], [1440, 900, 'light', 'desktop-light'], [820, 1180, 'dark', 'ipad'], [1180, 820, 'light', 'ipad-landscape'], [390, 844, 'light', 'phone'], [360, 780, 'dark', 'phone-small']];
  for (const [w, h, sc, name] of VP) {
    const full = name === 'desktop';            // the exhaustive filter × scope matrix runs once; other sizes take a sample
    const ctx = await br.newContext({ viewport: { width: w, height: h }, colorScheme: sc });
    await ctx.addInitScript(() => { try { localStorage.setItem('vt_sim_ack_v1', '1'); } catch (e) {} });
    const p = await ctx.newPage();
    let errs = []; p.on('pageerror', e => errs.push(e.message));
    const note = (where, msg) => issues.push(`${name} | ${where} | ${msg}`);
    const ok = (cond, where, msg) => { checks++; if (!cond) note(where, msg); return cond; };
    const look = async where => {
      checks++;
      const r = await p.evaluate(() => {
        const vw = innerWidth, out = [];
        if (document.documentElement.scrollWidth > vw + 1) out.push('page scrolls sideways (' + document.documentElement.scrollWidth + 'px)');
        document.querySelectorAll('.card,.pcard,section,.dtabs,.vts-buy,.tools,.stc,.amc-card').forEach(el => {
          const b = el.getBoundingClientRect(); if (b.width && b.right > vw + 2 && getComputedStyle(el).position !== 'fixed') out.push((el.id || el.className).toString().slice(0, 40) + ' overflows right by ' + Math.round(b.right - vw) + 'px');
        });
        return { out: out.slice(0, 3), text: document.body.innerText };
      });
      r.out.forEach(m => note(where, m));
      const t = bad(r.text); if (t) note(where, 'text: ' + t.replace(/\s+/g, ' '));
      if (errs.length) { errs.forEach(e => note(where, 'JS error: ' + e)); errs = []; }
    };
    const shown = () => p.evaluate(() => {
      const box = getComputedStyle(document.getElementById('fcards')).display !== 'none' ? '#fcards' : '#ftbody';
      return { n: +document.getElementById('tblCount').textContent.replace(/[^\d]/g, ''),
               codes: [...document.querySelectorAll(box + ' [data-code]')].map(e => +e.getAttribute('data-code')) };
    });
    const openTools = async () => { if (await p.isVisible('#fTog') && (await p.getAttribute('#fTog', 'aria-expanded')) !== 'true') { await p.click('#fTog'); await p.waitForTimeout(150); } };
    const setSel = async (k, v) => { await openTools(); await p.selectOption('#' + SEL[k], String(v)); await p.waitForTimeout(60); };
    const resetAll = async () => { await p.evaluate(E => { Object.keys(E).forEach(k => { const el = document.getElementById(E[k][0]); el.value = E[k][1]; el.dispatchEvent(new Event('change', { bubbles: true })); }); const t = document.getElementById('fText'); t.value = ''; t.dispatchEvent(new Event('input', { bubbles: true })); },
      Object.fromEntries(Object.keys(SEL).map(k => [k, [SEL[k], EMPTY[k]]]))); await p.waitForTimeout(200); };
    const verify = async (scope, flt, where) => {
      const exp = expect(scope, flt), s = await shown(), set = new Set(exp.map(f => f.code));
      ok(s.n === exp.length, where, `count ${s.n}, expected ${exp.length}`);
      const wrong = s.codes.filter(c => !set.has(c));
      ok(!wrong.length, where, `${wrong.length} listed fund(s) outside the filter, e.g. ${wrong.slice(0, 2).map(c => BYC[c] ? BYC[c].name : c).join('; ')}`);
      ok(exp.length === 0 ? s.codes.length === 0 : s.codes.length > 0, where, `rows shown ${s.codes.length} with ${exp.length} expected`);
      return exp;
    };
    const goAsset = async a => { await p.click(`#assets [data-asset="${a}"]`); await p.waitForTimeout(250); };
    const goSub = async s => { await p.click(`#subs [data-sub="${s}"]`); await p.waitForTimeout(200); };
    try {

    await p.goto(B, { waitUntil: 'networkidle' }); await p.waitForTimeout(900); await look('explore');

    // 1. asset classes and every category
    for (const a of ASSETS) {
      await goAsset(a); await verify({ asset: a }, {}, `asset ${a}`); await look(`asset ${a}`);
      const subs = subsOf(a);
      const tabN = await p.$$eval('#subs [data-sub]', x => x.map(e => [e.getAttribute('data-sub'), +(e.querySelector('.n') || {}).textContent || 0]));
      for (const s of subs) {
        const t = tabN.find(x => x[0] === s);
        ok(t && t[1] === F.filter(f => f.sub === s).length, `asset ${a} / tab ${s}`, `category tab count ${t && t[1]} vs ${F.filter(f => f.sub === s).length}`);
        if (full || subs.indexOf(s) % 4 === 0) { await goSub(s); await verify({ sub: s }, {}, `category ${s}`); await look(`category ${s}`); }
      }
      await goSub('');
    }

    // 2. every filter option on every asset class (desktop) / two asset classes (other sizes)
    const opts = await p.evaluate(S => Object.fromEntries(Object.entries(S).map(([k, id]) => [k, [...document.getElementById(id).options].map(o => o.value).filter(v => v !== '' && v !== '0')])), SEL);
    for (const a of (full ? ASSETS : ASSETS.slice(0, 2))) {
      await goAsset(a);
      for (const k of Object.keys(SEL)) {
        let vals = opts[k];
        if (k === 'amc') { const inA = new Set(F.filter(f => f.asset === a).map(f => String(f.amc))); vals = vals.filter(v => inA.has(v)); if (!full) vals = vals.slice(0, 6); }
        for (const v of vals) { await setSel(k, v); await verify({ asset: a }, { [k]: v }, `${a} · ${k}=${v}`); }
        await setSel(k, EMPTY[k]);
      }
      for (const t of ['index', 'hdfc', 'small cap', 'sbi bluechip', 'zzzz']) {
        await openTools(); await p.fill('#fText', t); await p.waitForTimeout(260);
        await verify({ asset: a }, { text: t }, `${a} · text "${t}"`);
      }
      await p.fill('#fText', ''); await p.waitForTimeout(260);
      await look(`filters ${a}`);
    }

    // 3. combined filters, status cards and fund-house strip (Equity)
    await goAsset('Equity');
    const combos = [{ rating: '3', hist: '5' }, { ter: '1', status: 'On track' }, { buy: 'open', rating: '4', hist: '3' }, { risk: '5', ter: '0.75', buy: 'sip' }];
    for (const c of combos) { for (const [k, v] of Object.entries(c)) await setSel(k, v); await verify({ asset: 'Equity' }, c, 'combo ' + JSON.stringify(c));
      const fc = await p.$eval('#fTogN', e => e.hidden ? 0 : +e.textContent); ok(fc === Object.keys(c).length, 'combo ' + JSON.stringify(c), `filter badge ${fc}`); await resetAll(); }
    for (const st of ['In form', 'On track', 'Underperforming', 'Out of track']) {
      const cnt = await p.$eval(`#stCards [data-stf="${st}"] em`, e => +e.textContent);
      ok(cnt === expect({ asset: 'Equity' }, { status: st }).length, `status card ${st}`, `card shows ${cnt}`);
      await p.click(`#stCards [data-stf="${st}"]`); await p.waitForTimeout(200);
      await verify({ asset: 'Equity' }, { status: st }, `status card ${st} (tapped)`);
      ok((await p.$eval('#fStatus', e => e.value)) === st, `status card ${st}`, 'filter menu not in sync');
      await p.click(`#stCards [data-stf="${st}"]`); await p.waitForTimeout(200);
      await verify({ asset: 'Equity' }, {}, `status card ${st} (tapped again = cleared)`);
    }
    const strip = await p.$$eval('#amcStrip [data-amcf]', x => x.map(e => [e.getAttribute('data-amcf'), +e.querySelector('small').textContent]));
    const inEq = {}; F.filter(f => f.asset === 'Equity').forEach(f => { inEq[f.amc] = (inEq[f.amc] || 0) + 1; });
    ok(strip.length === Object.keys(inEq).length, 'fund-house strip', `${strip.length} fund houses shown, ${Object.keys(inEq).length} expected`);
    strip.forEach(([i, n]) => ok(n === inEq[i], 'fund-house strip', `${D.amcs[i]} shows ${n}, expected ${inEq[i]}`));
    for (const [i] of strip.slice(0, full ? 8 : 3)) {
      await p.$eval(`#amcStrip [data-amcf="${i}"]`, e => e.click()); await p.waitForTimeout(220);
      await verify({ asset: 'Equity' }, { amc: i }, `fund-house tap ${D.amcs[i]}`);
      ok((await p.$eval('#fAmc', e => e.value)) === i, `fund-house tap ${D.amcs[i]}`, 'filter menu not in sync');
      // category switch keeps the fund house only when it has funds there
      const sub = subsOf('Equity').find(s => !F.some(f => f.sub === s && f.amc === +i));
      if (sub) { await goSub(sub); ok((await p.$eval('#fAmc', e => e.value)) === '', `fund-house ${D.amcs[i]} → ${sub}`, 'fund-house filter not cleared in a category without its funds'); await goSub(''); }
      await resetAll();
    }

    // 4. sorting by every column (desktop table only) — listed values must be in order, blanks last
    if (w > 760) {
      await goAsset('Equity');
      const keys = await p.$$eval('#fthead th[data-k]', x => x.map(e => e.getAttribute('data-k')));
      for (const k of keys) {
        for (const pass of [1, 2]) {
          await p.click(`#fthead th[data-k="${k}"]`); await p.waitForTimeout(150);
          const dir = await p.$eval(`#fthead th[data-k="${k}"]`, e => e.getAttribute('aria-sort'));
          const s = await shown(), vals = s.codes.map(c => k === 'rec' ? BYC[c].rec : BYC[c][k]);
          if (k === 'name') { const nm = s.codes.map(c => BYC[c].name); ok(nm.every((x, i) => !i || (dir === 'ascending' ? nm[i - 1].localeCompare(x) <= 0 : nm[i - 1].localeCompare(x) >= 0)), `sort ${k} ${dir}`, 'names out of order'); continue; }
          if (!(k in C)) continue;
          const num = vals.filter(isNum), firstBlank = vals.findIndex(v => !isNum(v));
          ok(firstBlank < 0 || vals.slice(firstBlank).every(v => !isNum(v)), `sort ${k} ${dir}`, 'blank values not last');
          ok(num.every((x, i) => !i || (dir === 'ascending' ? num[i - 1] <= x : num[i - 1] >= x)), `sort ${k} ${dir} (pass ${pass})`, 'values out of order: ' + num.slice(0, 6).join(', '));
        }
      }
      // show more
      const before = (await shown()).codes.length;
      if (await p.isVisible('#moreBtn')) { await p.click('#moreBtn'); await p.waitForTimeout(250); ok((await shown()).codes.length > before, 'show more', 'no extra rows'); }
    }

    // 5. presets and return periods
    await p.goto(B, { waitUntil: 'networkidle' }); await p.waitForTimeout(700);
    const PRE = { sip: 'sip3', riskadj: 'sharpe', cost: 'ter', large: 'aum', inform: 'rec', mom3: 'r3m' };
    const pres = await p.$$eval('#presets [data-pre]', x => x.map(e => e.getAttribute('data-pre')));
    for (const pr of pres) {
      await p.click(`#presets [data-pre="${pr}"]`); await p.waitForTimeout(pr === 'value' ? 1500 : 250);
      const s = await shown(); ok(s.codes.length > 0, `preset ${pr}`, 'no funds listed');
      if (PRE[pr]) { const v = s.codes.map(c => BYC[c][PRE[pr]]).filter(isNum), asc = pr === 'cost'; ok(v.every((x, i) => !i || (asc ? v[i - 1] <= x : v[i - 1] >= x)), `preset ${pr}`, 'not ordered by ' + PRE[pr]); }
      await look(`preset ${pr}`);
    }
    for (const per of ['r1y', 'r5y', 'r3y']) { await p.click(`#presets [data-pre="${pres[0]}"]`); await p.click(`#perSeg [data-p="${per}"]`); await p.waitForTimeout(200);
      const v = (await shown()).codes.map(c => BYC[c][per]).filter(isNum); ok(v.every((x, i) => !i || v[i - 1] >= x), `period ${per}`, 'not ordered by ' + per); }

    // 6. fund detail: a fund of every category (desktop) / every 4th (others), every tab
    const bySub = {}; F.forEach(f => { if (!bySub[f.sub] || (f.aum || 0) > (bySub[f.sub].aum || 0)) bySub[f.sub] = f; });
    const subs = Object.keys(bySub).filter((_, i) => full || i % 4 === 0);
    for (const s of subs) {
      const f = bySub[s];
      await p.goto(B + '?fund=' + f.code, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(900);
      const tabs = await p.$$eval('#dtabs .dtab', x => x.map(e => e.dataset.tab));
      if (!ok(tabs.length > 0, `fund ${f.name}`, 'detail did not open')) continue;
      const title = await p.evaluate(() => document.body.innerText);
      ok(title.includes(f.name), `fund ${f.name}`, 'fund name not on the page');
      for (const t of tabs) { await p.click(`#dtabs .dtab[data-tab="${t}"]`); await p.waitForTimeout(t === 'overview' ? 900 : 400); await look(`fund ${f.code} (${s}) / ${t}`); }
    }

    // 7. compare: add three funds from fund pages, then remove one
    const cmp = [bySub.large_cap, bySub.flexi_cap, bySub.mid_cap].filter(Boolean);
    await p.goto(B + '?view=compare', { waitUntil: 'networkidle' }); await p.waitForTimeout(500); await look('compare (empty)');
    await p.goto(B + '?view=compare&cmp=' + cmp.map(f => f.code).join(','), { waitUntil: 'networkidle' }); await p.waitForTimeout(1200);
    const ct = await p.evaluate(() => document.getElementById('cmpBody').innerText);
    cmp.forEach(f => ok(ct.includes(f.name), 'compare', `${f.name} missing`));
    ok((await p.$eval('#cmpN', e => +e.textContent)) === cmp.length, 'compare', 'badge count wrong');
    for (const r of ['1Y', '3Y', '5Y', 'Max']) { const b = await p.$(`#cmpRange [data-r="${r}"]`); if (b) { await b.click(); await p.waitForTimeout(400); } }
    await look('compare (3 funds)');

    // 8. NFO filters vs nfo.json
    await p.goto(B + '?view=nfo', { waitUntil: 'networkidle' }); await p.waitForTimeout(700);
    const all = NFO.nfos || [];
    const nexp = (st, as, kind, q) => all.filter(n => (st === 'live' ? n.status !== 'Closed' : st === 'Closed' ? n.status === 'Closed' : true) && (!as || n.asset === as) && (!kind || n.kind === kind) &&
      q.toLowerCase().split(/\s+/).filter(Boolean).every(t => (n.name + ' ' + n.amc + ' ' + n.cat).toLowerCase().includes(t))).length;
    const ncount = () => p.$$eval('#nfoGrid > .card', x => x.filter(e => !e.querySelector('.empty,.err')).length);
    for (const st of ['live', '', 'Closed']) for (const kind of ['', 'active', 'index', 'etf', 'fof', 'closed']) {
      await p.selectOption('#nfoStatus', st); await p.selectOption('#nfoKind', kind); await p.waitForTimeout(80);
      const got = await ncount(); ok(got === nexp(st, '', kind, ''), `nfo status=${st || 'all'} kind=${kind || 'all'}`, `${got} offers shown, ${nexp(st, '', kind, '')} expected`);
    }
    await p.selectOption('#nfoKind', ''); await p.selectOption('#nfoStatus', '');
    for (const as of [...new Set(all.map(n => n.asset))]) { await p.selectOption('#nfoAsset', as); await p.waitForTimeout(80); const got = await ncount(); ok(got === nexp('', as, '', ''), `nfo asset=${as}`, `${got} vs ${nexp('', as, '', '')}`); }
    await p.selectOption('#nfoAsset', '');
    for (const q of ['fund', 'zzzz']) { await p.fill('#nfoText', q); await p.waitForTimeout(300); const got = await ncount(); ok(got === nexp('', '', '', q), `nfo text "${q}"`, `${got} vs ${nexp('', '', '', q)}`); }
    await p.fill('#nfoText', ''); await look('nfo');

    // 9. Portfolio Simulator tabs and every horizon × risk (the full maths is in test_smart_invest.js)
    await p.goto(B + '?view=sip', { waitUntil: 'networkidle' }); await p.waitForTimeout(1200);
    for (const t of await p.$$eval('#sipTabs [data-t], #sipTabs button', x => x.map((e, i) => i))) { await p.$$eval('#sipTabs button', (x, i) => x[i].click(), t); await p.waitForTimeout(500); await look(`simulator tab ${t}`); }
    for (const hz of (full ? ['h1', 'h3', 'h5', 'h7', 'h10'] : ['h1', 'h10'])) for (const rk of ['c', 'b', 'a', 'v']) {
      await p.goto(B + `?view=sip&h=${hz}&r=${rk}`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(700);
      ok(await p.$eval('#sipBody', e => e.innerText.length > 200), `simulator ${hz}${rk}`, 'plan did not render'); await look(`simulator ${hz}${rk}`);
    }

    // 10. bottom tab bar (phones) / view switcher and FAQs
    await p.goto(B, { waitUntil: 'networkidle' }); await p.waitForTimeout(600);
    for (const v of ['compare', 'nfo', 'explore']) { await p.click(`.vbtn[data-view="${v}"]`); await p.waitForTimeout(400); ok(await p.isVisible('#v-' + v), `view ${v}`, 'view did not open'); }
    const nf = await p.$$eval('details.faq', x => x.length);
    for (let i = 0; i < nf; i++) await p.evaluate(i => { document.querySelectorAll('details.faq')[i].open = true; }, i);
    ok(nf > 40, 'faq', `only ${nf} questions`); await look(`faq (${nf})`);
    } catch (e) { note('run', 'test stopped: ' + e.message.split('\n')[0]); }
    await ctx.close();
    console.log(`${name}: done (${checks} checks so far, ${issues.length} issues)`);
  }
  await br.close();
  console.log(`\n${checks} checks · ${issues.length} issues`);
  [...new Set(issues)].slice(0, 150).forEach(x => console.log('  ' + x));
  process.exit(issues.length ? 1 : 0);
})();
