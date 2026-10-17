// Run: python3 -m http.server 8765 (repo root) && node scripts/test_smart_invest.js   [env: URL, CHROME, OUT]
// End-to-end test of the Smart Invest planner: many inputs, desktop + phone, independent reference maths.
const { chromium } = require('playwright');
const OUT = process.env.OUT || require('os').tmpdir();
const URL = process.env.URL || 'http://localhost:8765/india_mf_screener.html';
const SC = [ // [hz, rk, fq, amt, stay, years, slab, forcePct]
  ['h10','v','m',100000,15,15,30], ['h10','v','m',100000,15,1,30], ['h10','v','m',100000,20,10,30], ['h10','b','m',10000,25,25,20],
  ['h10','a','w',2500,12,5,30], ['h10','c','q',30000,10,10,0], ['h10','a','y',120000,30,20,30], ['h10','v','l',1000000,15,0,30],
  ['h10','v','l',5000000,20,0,30,0.70], ['h10','a','l',2000000,12,0,30,0.92], ['h10','c','l',25000,10,0,5,0.95],
  ['h7','b','m',5000,8,8,10], ['h7','a','q',15000,9,4,20], ['h7','v','l',300000,8,0,30,0.65], ['h7','c','y',60000,7,7,30],
  ['h5','b','m',2000,6,6,30], ['h5','a','w',500,5,2,30], ['h5','v','l',100000,6,0,20], ['h5','c','q',9000,7,3,0],
  ['h3','c','m',1000,4,4,30], ['h3','b','y',50000,5,5,30], ['h3','a','l',200000,3,0,30,0.85], ['h3','v','w',1000,4,1,10],
  ['h1','c','m',5000,2,2,30], ['h1','b','l',500000,1,0,30], ['h1','a','q',10000,3,3,20], ['h1','c','y',20000,2,1,0],
  ['h10','v','m',100,15,15,30], ['h10','b','l',100,15,0,30], ['h10','a','m',9999999,40,40,30],
  ['h5','v','m',40000,6,6,30], ['h5','v','m',20000,6,6,30], ['h3','v','l',30000,4,0,30], ['h1','c','m',10000,2,2,30],
];
(async () => {
  const b = await chromium.launch({executablePath: process.env.CHROME || undefined});
  let pass = 0, fail = 0; const rows = [];
  for (const [vw, vh, dev] of [[1366, 900, 'desktop'], [390, 844, 'phone']]) {
    const ctx = await b.newContext({viewport:{width:vw, height:vh}, isMobile: vw < 500, hasTouch: vw < 500});
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
    for (const sc of SC) {
      const [hz, rk, fq, amt, stay, years, slab, pct] = sc;
      const q = `?view=sip&h=${hz}&r=${rk}&amt=${amt}&st=${stay}${years ? '&y=' + years : ''}${fq !== 'm' ? '&fq=' + fq : ''}${slab !== 30 ? '&tx=' + slab : ''}`;
      await p.goto(URL + q); await p.waitForFunction(() => window.SIP && document.querySelector('.card.proj'), null, {timeout: 20000});
      if (pct != null) { await p.evaluate(v => { SIP.market.n50.pePct = v; renderSip(); }, pct); }
      const r = await p.evaluate(() => {
        const P = S.plan, plan = SIP.plans[P.hz + P.rk], A = SIP.assumptions;
        const sized = sizePlan(plan, P.amt, P.fq), lump = P.fq === 'l';
        const entry = lump ? entryPlan(sized, P.amt) : null;
        const stay = +document.getElementById('sipStay').value, years = lump ? stay : +document.getElementById('sipYrs').value;
        const pr = projectPlan(sized, P, years, stay, entry);
        // ── independent reference (does not call the page's maths) ──
        const ppy = {w:52, m:12, q:4, y:1, l:12}[P.fq], n = lump ? 1 : Math.max(1, Math.round(years * ppy)), T = lump ? Math.round(stay * 12) : Math.max(n, Math.round(stay * ppy));
        const G = {eqS:0, eqL:0, debt:0, oS:0, oL:0}; let inv = 0, val = 0;
        const add = (tax, gain, mo) => { if (tax === 'equity' || tax === 'elss') G[mo > 12 ? 'eqL' : 'eqS'] += gain; else if (tax === 'debt') G.debt += gain; else G[mo > 24 ? 'oL' : 'oS'] += gain; };
        const stp = {}; (entry && entry.months ? entry.stp : []).forEach(x => stp[x.slot.key] = x);
        sized.slots.forEach(s => {
          const mr = Math.pow(1 + s.er / 100, 1 / ppy);
          if (lump && stp[s.key]) { const x = stp[s.key], K = entry.months, ml = Math.pow(1 + (x.liquid.r1y ?? 6.5) / 100, 1 / 12);
            inv += s.amt; for (let j = 1; j <= K; j++) { const c = s.amt / K * Math.pow(ml, j); G.debt += c - s.amt / K; const v = c * Math.pow(mr, T - j); val += v; add(s.tax, v - c, T - j); } return; }
          for (let k = 0; k < n; k++) { const v = s.amt * Math.pow(mr, T - k); inv += s.amt; val += v; add(s.tax, v - s.amt, (T - k) / ppy * 12); }
        });
        const cess = 1 + A.cess / 100, sl = P.slab / 100;
        const tax = ((Math.max(0, G.eqS) * A.stcgEquity + Math.max(0, G.eqL - A.ltcgExempt) * A.ltcgEquity) / 100 + Math.max(0, G.debt) * sl + Math.max(0, G.oL) * A.ltcgOther / 100 + Math.max(0, G.oS) * sl) * cess;
        const post = val - tax;
        const fv = rr => lump ? P.amt * Math.pow(1 + rr / 100, stay) : (() => { const g = Math.pow(1 + rr / 100, 1 / ppy); let v = 0; for (let k = 0; k < n; k++) v += P.amt * Math.pow(g, T - k); return v; })();
        const card = document.querySelector('.card.proj'), kp = [...card.querySelectorAll('.kpi')].map(k => k.innerText.replace(/\s+/g, ' '));
        const entryCard = [...document.querySelectorAll('.card.pcard .sec-title')].some(t => t.innerText === 'Entry plan');
        const entryAmts = lump ? [...document.querySelectorAll('.entry-step')][0].querySelectorAll('li b') : [];
        let entryToday = 0; entryAmts.forEach(e => entryToday += +e.innerText.replace(/[^\d]/g, ''));
        return {
          name: P.hz + P.rk + '/' + P.fq, amt: P.amt, stay, years, hzOn: document.querySelector('#sipHz .on').dataset.hz, fqOn: document.querySelector('#sipFq .on').dataset.fq,
          yrsHidden: document.getElementById('sipYrsFld').hidden, lump, months: entry ? entry.months : null,
          sumSlots: sized.slots.reduce((a, s) => a + s.amt, 0), wSum: sized.slots.reduce((a, s) => a + s.w, 0),
          inv: pr.invested, invRef: inv, val: pr.value, valRef: val, tax: pr.tax, taxRef: tax, post: pr.post, postRef: post,
          low: pr.low, high: pr.high, fvX: fv(pr.xirr), title: card.querySelector('.sec-title').innerText, sub: card.querySelector('.sec-sub').innerText,
          kInv: kp[0], kVal: kp[1], fmtInv: fmtCr(pr.invested), fmtVal: fmtCr(pr.value), entryCard, entryToday,
          stpParts: entry && entry.months ? entry.stp.map(x => [x.slot.amt, x.per * entry.months, x.same]) : [],
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, merged: sized.merged,
          upOk: sized.slots.every(s => { const up = (plan.slots.find(z => z.key === s.key) || {}).upgrade, uf = up && BY[up.code];
            const eligible = !!(uf && !s.swapped && !(P.fq === 'w' && (uf.buy || '').indexOf('W') < 0) && s.amt >= sipMinOf(up.code));
            return s.upFrom ? (eligible && s.code === up.code && s.amt >= sipMinOf(s.code)) : !eligible; }),
          upN: sized.slots.filter(s => s.upFrom).length, upTags: [...document.querySelectorAll('.sip-tbl .tag')].filter(t => t.innerText === 'Upgraded for your amount').length,
        };
      });
      const checks = [];
      const near = (a, b, rel) => Math.abs(a - b) <= Math.max(1, Math.abs(b) * rel);
      checks.push(['amounts add up', r.sumSlots === r.amt]);
      checks.push(['weights add up to 100', r.wSum === 100]);
      checks.push(['invested', near(r.inv, r.invRef, 1e-9) && near(r.inv, r.lump ? r.amt : r.amt * Math.round(r.years * {w:52,m:12,q:4,y:1}[fq]), 1e-9)]);
      checks.push(['value vs reference', near(r.val, r.valRef, 1e-9)]);
      checks.push(['tax vs reference', near(r.tax, r.taxRef, 1e-9)]);
      checks.push(['post-tax vs reference', near(r.post, r.postRef, 1e-9)]);
      checks.push(['post-tax return reproduces post-tax value', near(r.fvX, r.post, 1e-4)]);
      checks.push(['range brackets value', r.low <= r.val && r.val <= r.high && r.post <= r.val && r.tax >= 0]);
      checks.push(['heading uses holding period', r.title === `Expected outcome after ${r.stay} year${r.stay > 1 ? 's' : ''}`]);
      checks.push(['KPI text = computed', r.kInv.includes(r.fmtInv) && r.kVal.includes(r.fmtVal)]);
      checks.push(['horizon + option highlighted', r.hzOn === hz && r.fqOn === fq]);
      checks.push(['invest-for hidden only for one-time', r.yrsHidden === r.lump]);
      checks.push(['entry plan only for one-time', r.entryCard === r.lump]);
      if (r.lump) {
        checks.push(['entry today = amount (or amount incl. parking)', Math.abs(r.entryToday - r.amt) <= 5]);
        checks.push(['transfers cover each equity fund', r.stpParts.every(([a, t]) => Math.abs(a - t) <= Math.max(5, a * 0.002))]);
        if (pct != null) checks.push(['stagger matches valuation', pct >= 0.8 ? r.months === 12 || (r.months >= 3 && r.months < 12) || r.months === 0 : pct >= 0.6 ? r.months === 6 || (r.months >= 0 && r.months < 6) : r.months === 0]);
        else checks.push(['invest at once when cheap', r.months === 0]);
      }
      if (!r.lump && r.years < r.stay) checks.push(['sub-heading mentions holding after instalments', /then left invested for/.test(r.sub)]);
      checks.push(['upgrade used exactly when the amount covers its minimum', r.upOk]);
      checks.push(['upgrade labelled on the page', r.upTags === r.upN]);
      checks.push(['no horizontal overflow', r.overflow <= 0]);
      const bad = checks.filter(c => !c[1]).map(c => c[0]);
      bad.length ? fail++ : pass++;
      rows.push(`${dev.padEnd(7)} ${r.name.padEnd(9)} ₹${String(r.amt).padStart(8)} stay ${String(r.stay).padStart(2)} inv ${String(r.years).padStart(2)} slab ${String(slab).padStart(2)}${pct != null ? ' val ' + pct : '         '} | invested ${r.fmtInv.padStart(9)} value ${r.fmtVal.padStart(10)} tax ${fmt(r.tax)} | ${r.lump ? (r.months ? 'stagger ' + r.months + 'm' : 'at once  ') : '         '}${r.merged ? ' merged ' + r.merged : ''}${r.upN ? ' upgraded ' + r.upN : ''} | ${bad.length ? 'FAIL: ' + bad.join(', ') : 'ok (' + checks.length + ' checks)'}`);
      if (['h10v/l', 'h10v/q'].includes(r.name) && !rows.some(x => x.startsWith('shot ' + dev + r.name))) { rows.push('shot ' + dev + r.name); await p.screenshot({path: `${OUT}/${dev}_${r.name.replace('/', '_')}.png`, fullPage: true}); }
    }
    if (errs.length) { fail++; rows.push(dev + ' PAGE ERRORS: ' + errs.join(' | ')); }
    await ctx.close();
  }
  function fmt(v){ return v >= 1e7 ? (v / 1e7).toFixed(2) + ' Cr' : v >= 1e5 ? (v / 1e5).toFixed(2) + ' L' : Math.round(v).toString(); }
  console.log(rows.filter(r => !r.startsWith('shot')).join('\n'));
  console.log(`\n${pass} scenario runs passed, ${fail} failed`); process.exitCode = fail ? 1 : 0;
  await b.close();
})();
