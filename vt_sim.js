/*
 * vt_sim.js — shared by india_mf_screener.html and etf_momentum.html
 *
 *  VTSim.gate(onAccept, homeFn)  Shows the Portfolio Simulator risk-acknowledgement dialog before the simulator is
 *                                opened. Accept (after ticking the acknowledgement) runs onAccept; Close / Escape /
 *                                "Read the FAQs" run homeFn (back to the page's home view). "Don't show this again"
 *                                remembers the acceptance in this browser (localStorage) until site data is cleared.
 *  VTSim.accepted()              true when the visitor has already accepted in this browser (remembered) or this visit.
 *  VTSim.faqCols(card)           On wide screens splits the <details class="faq"> items of a card into two
 *                                independent columns (opening one never shifts the other column).
 */
(function () {
  'use strict';
  var KEY = 'vt_sim_ack_v1', session = false, open = false;

  function remembered() { try { return localStorage.getItem(KEY) === '1'; } catch (e) { return false; } }
  function accepted() { return session || remembered(); }

  var CSS =
    '.vts-ov{position:fixed;inset:0;z-index:9999;background:rgba(2,8,20,.72);display:flex;align-items:center;justify-content:center;padding:16px;backdrop-filter:blur(3px)}' +
    '.vts-dlg{background:var(--surface);color:var(--text);border:1px solid var(--border2);border-radius:var(--radius,14px);box-shadow:0 24px 60px rgba(0,0,0,.45);width:100%;max-width:620px;max-height:calc(100vh - 32px);display:flex;flex-direction:column;overflow:hidden}' +
    '.vts-hd{display:flex;align-items:flex-start;gap:12px;padding:18px 20px 12px;border-bottom:1px solid var(--border)}' +
    '.vts-ic{flex:none;width:38px;height:38px;border-radius:10px;display:grid;place-items:center;background:rgba(232,163,23,.14);font-size:20px}' +
    '.vts-hd h2{font-size:18px;line-height:1.3;margin:0}' +
    '.vts-hd p{margin:3px 0 0;color:var(--text2);font-size:13px}' +
    '.vts-x{margin-left:auto;flex:none;background:none;border:1px solid var(--border);color:var(--text2);border-radius:8px;width:32px;height:32px;cursor:pointer;font-size:16px;line-height:1}' +
    '.vts-x:hover{color:var(--text);border-color:var(--border2)}' +
    '.vts-bd{padding:14px 20px;overflow-y:auto;font-size:13.5px;line-height:1.6}' +
    '.vts-warn{background:rgba(232,163,23,.10);border-left:4px solid #e8a317;border-radius:8px;padding:10px 12px;margin-bottom:12px}' +
    '.vts-bd ul{margin:0 0 12px;padding-left:0;list-style:none}' +
    '.vts-bd li{position:relative;padding:6px 0 6px 26px;border-top:1px solid var(--border)}' +
    '.vts-bd li:first-child{border-top:none}' +
    '.vts-bd li::before{content:"!";position:absolute;left:0;top:8px;width:17px;height:17px;border-radius:50%;background:var(--accent-soft);color:var(--accent2);font-size:11px;font-weight:800;display:grid;place-items:center}' +
    '.vts-bd a{color:var(--accent2);font-weight:600}' +
    '.vts-chk{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border:1px solid var(--border);border-radius:10px;margin-top:8px;cursor:pointer;background:var(--surface2)}' +
    '.vts-chk input{margin-top:3px;width:17px;height:17px;flex:none;accent-color:var(--accent)}' +
    '.vts-chk.req{border-color:var(--accent)}' +
    '.vts-ft{display:flex;gap:10px;justify-content:flex-end;padding:12px 20px 16px;border-top:1px solid var(--border);flex-wrap:wrap}' +
    '.vts-b{height:40px;padding:0 18px;white-space:nowrap;border-radius:10px;font-weight:700;font-size:14px;cursor:pointer;border:1px solid var(--border2);background:var(--surface2);color:var(--text)}' +
    '.vts-b.pri{background:var(--accent);border-color:var(--accent);color:var(--accent-ink,#fff)}' +
    '.vts-b.pri:disabled{opacity:.45;cursor:not-allowed}' +
    '.vts-dlg:focus{outline:none}.vts-b:focus-visible,.vts-x:focus-visible{outline:none;box-shadow:var(--focus)}' +
    '@media (max-width:560px){.vts-ov{padding:10px;align-items:flex-end}.vts-dlg{max-height:calc(100vh - 20px)}.vts-hd,.vts-bd,.vts-ft{padding-left:14px;padding-right:14px}.vts-hd h2{font-size:16px}.vts-ft .vts-b{flex:1;padding:0 10px}.vts-ft .vts-b.pri{flex:1.6}}' +
    /* two-column FAQ */
    '.vts-fcols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 28px;align-items:start}' +
    '.vts-fcols>div>details.faq:first-child{border-top:none}' +
    '@media (max-width:999px){.vts-fcols{display:block}.vts-fcols>div+div>details.faq:first-child{border-top:1px solid var(--border)}}' +
    /* simulator tabs + Risk & score + Economy & earnings panels */
    '.vts-tabs{display:flex;gap:6px;margin:0 0 14px;padding:4px;border:1px solid var(--border);border-radius:12px;background:var(--surface);overflow-x:auto;scrollbar-width:none}' +
    '.vts-tabs::-webkit-scrollbar{display:none}' +
    '.vts-tabs button{flex:1 0 auto;height:40px;padding:0 14px;border:0;border-radius:9px;background:none;color:var(--text2);font-weight:700;font-size:13.5px;cursor:pointer;white-space:nowrap}' +
    '.vts-tabs button.on{background:var(--accent);color:var(--accent-ink,#fff)}' +
    '.vts-tabs button:not(.on):hover{background:var(--surface2);color:var(--text)}' +
    '.vts-tabs button:focus-visible{outline:none;box-shadow:var(--focus)}' +
    '.vts-pane{display:grid;gap:14px;min-width:0}.vts-pane>*,.vts-grid2>*{min-width:0}.vts-t td:first-child{white-space:nowrap}' +
    '.vts-box{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius,14px);padding:18px}' +
    '.vts-box h3{font-size:15px;margin:0 0 4px}' +
    '.vts-sub{color:var(--text2);font-size:12.5px;margin:0 0 12px;line-height:1.5}' +
    '.vts-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}' +
    '.vts-k{border:1px solid var(--border);border-radius:12px;padding:12px 14px;background:var(--surface2);min-width:0}' +
    '.vts-k small{display:block;color:var(--text2);font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}' +
    '.vts-k b{display:block;font-size:24px;line-height:1.2;margin-top:4px;font-variant-numeric:tabular-nums}' +
    '.vts-k b i{font-style:normal;font-size:13px;color:var(--text2);font-weight:600}' +
    '.vts-k em{display:block;font-style:normal;color:var(--text2);font-size:12px;margin-top:2px}' +
    '.vts-meter{position:relative;height:8px;border-radius:5px;margin-top:8px;background:var(--surface3)}' +
    '.vts-meter>span{position:absolute;left:0;top:0;bottom:0;border-radius:5px}' +
    '.vts-band{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:700;margin-top:6px}' +
    '.vts-tw{overflow-x:auto;margin:0 -4px;padding:0 4px}' +
    '.vts-t{width:100%!important;max-width:none!important;border-collapse:collapse;font-size:13px;min-width:640px}' +
    '.vts-t th{text-align:left;color:var(--text2);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;padding:8px 8px;border-bottom:1px solid var(--border2);white-space:nowrap}' +
    '.vts-t td{padding:9px 8px;border-bottom:1px solid var(--border);vertical-align:middle}' +
    '.vts-t td.n,.vts-t th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}' +
    '.vts-t tr.tot td{font-weight:800;border-top:2px solid var(--border2);border-bottom:none}' +
    '.vts-t .nm b{display:block;font-weight:700}.vts-t .nm small{color:var(--text3);font-size:11.5px}' +
    '.vts-mini{display:flex;align-items:center;gap:8px;justify-content:flex-end}' +
    '.vts-mini .vts-meter{width:64px;margin:0}' +
    '.vts-cards{display:none}' +
    '.vts-scale{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--text2);margin-top:10px}' +
    '.vts-scale span::before{content:"";display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;background:var(--c)}' +
    '.vts-cl{list-style:none;margin:0;padding:0}' +
    '.vts-cl li{display:grid;grid-template-columns:auto 1fr auto;gap:4px 12px;align-items:start;padding:10px 0;border-top:1px solid var(--border)}' +
    '.vts-cl li:first-child{border-top:none}' +
    '.vts-cl .sg{width:76px;text-align:center;padding:3px 0;border-radius:999px;font-size:11.5px;font-weight:800}' +
    '.vts-cl .k{font-weight:700;font-size:13.5px}.vts-cl .w{grid-column:2/4;color:var(--text2);font-size:12.5px}' +
    '.vts-cl .v{font-variant-numeric:tabular-nums;font-size:13px;text-align:right;color:var(--text)}' +
    '.sg.pos{background:rgba(34,197,94,.15);color:#22c55e}.sg.neu{background:rgba(148,163,184,.16);color:var(--text2)}.sg.neg{background:rgba(248,113,113,.15);color:#f87171}' +
    '.vts-grid2{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:14px}' +
    '@media (max-width:520px){.vts-earn th,.vts-earn td{padding:8px 4px;font-size:12px}.vts-earn th{font-size:10.5px;letter-spacing:0}.vts-earn td:first-child{white-space:normal}}' +
    '.vts-t td.fc{color:var(--text2)}.vts-t td.fc::after{content:" F";font-size:10px;font-weight:800;color:var(--accent2)}' +
    '.vts-note{font-size:12px;color:var(--text2);line-height:1.55;margin-top:10px}' +
    '@media (max-width:900px){.vts-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.vts-grid2{grid-template-columns:1fr}}' +
    '@media (max-width:640px){.vts-box{padding:14px}.vts-k b{font-size:20px}.vts-tw.vts-rkw{display:none}.vts-cards{display:grid;gap:8px}' +
    '.vts-card{border:1px solid var(--border);border-radius:10px;padding:10px 12px;background:var(--surface2)}' +
    '.vts-card .h{display:flex;justify-content:space-between;gap:8px;font-weight:700;font-size:13px}.vts-card .h span{flex:none;color:var(--text2)}' +
    '.vts-card .g{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 12px;margin-top:8px;font-size:12px;color:var(--text2)}.vts-card .g b{color:var(--text);font-variant-numeric:tabular-nums}' +
    '.vts-cl li{grid-template-columns:auto 1fr}.vts-cl .v{grid-column:2;text-align:left}.vts-cl .w{grid-column:1/3}}';

  function style() {
    if (document.getElementById('vtsCss')) return;
    var s = document.createElement('style'); s.id = 'vtsCss'; s.textContent = CSS; document.head.appendChild(s);
  }

  function gate(onAccept, homeFn) {
    if (accepted()) { onAccept(); return; }
    if (open) return;
    style(); open = true;
    var last = document.activeElement;
    var ov = document.createElement('div');
    ov.className = 'vts-ov';
    ov.innerHTML =
      '<div class="vts-dlg" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="vtsT" aria-describedby="vtsD">' +
        '<div class="vts-hd"><span class="vts-ic" aria-hidden="true">⚠️</span><div><h2 id="vtsT">Before you open the Portfolio Simulator</h2>' +
        '<p>Please read this risk warning and disclaimer.</p></div><button type="button" class="vts-x" data-act="close" aria-label="Close">✕</button></div>' +
        '<div class="vts-bd" id="vtsD">' +
          '<div class="vts-warn"><b>Risk warning:</b> mutual fund, ETF and stock market investments are subject to market risks. ' +
          'Read all scheme-related documents carefully before investing. Values go up and down, and you can lose money.</div>' +
          '<p style="margin:0 0 8px">By continuing you confirm that you understand:</p>' +
          '<ul>' +
            '<li><b>VilfinTV is a free educational website.</b> The Portfolio Simulator shows illustrative model portfolios built from published data and fixed rules, for learning only.</li>' +
            '<li><b>VilfinTV is not a SEBI-registered investment adviser or research analyst.</b> Nothing here is investment advice, a recommendation or an offer to buy or sell any fund.</li>' +
            '<li><b>Data may be delayed, incomplete or wrong.</b> Always confirm every figure on the fund house\'s official website and scheme documents.</li>' +
            '<li><b>Markets can fall sharply.</b> Historical model estimates and past returns do not predict future returns; red years are normal and losses are possible.</li>' +
            '<li><b>Any investment decision is your own, at your own risk.</b> VilfinTV is not responsible for gains or losses. Consider consulting a SEBI-registered investment adviser.</li>' +
          '</ul>' +
          '<p style="margin:0">Please also read the <a href="#faq" data-act="faq">FAQs</a>, including "Is the Portfolio Simulator investment advice?".</p>' +
          '<label class="vts-chk req"><input type="checkbox" id="vtsAck"><span>I have read and accept the risk warning and disclaimer above.</span></label>' +
          '<label class="vts-chk"><input type="checkbox" id="vtsMem"><span>Don\'t show this again in this browser</span></label>' +
        '</div>' +
        '<div class="vts-ft"><button type="button" class="vts-b" data-act="close">Close</button>' +
        '<button type="button" class="vts-b pri" data-act="accept" id="vtsOk" disabled>Accept &amp; continue</button></div>' +
      '</div>';
    document.body.appendChild(ov);
    var prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    var ack = ov.querySelector('#vtsAck'), ok = ov.querySelector('#vtsOk');
    ack.addEventListener('change', function () { ok.disabled = !ack.checked; });
    function done(acceptIt, faq) {
      if (!open) return;
      open = false;
      document.removeEventListener('keydown', onKey, true);
      document.body.style.overflow = prevOverflow;
      ov.remove();
      if (acceptIt) {
        session = true;
        if (ov.querySelector('#vtsMem').checked) { try { localStorage.setItem(KEY, '1'); } catch (e) {} }
        onAccept();
      } else {
        homeFn(!!faq);
        if (last && last.focus && !faq) try { last.focus({preventScroll: true}); } catch (e) {}
      }
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); done(false); return; }
      if (e.key === 'Tab') {                                     // keep focus inside the dialog
        var f = [].slice.call(ov.querySelectorAll('button:not([disabled]),input,a[href]'));
        var i = f.indexOf(document.activeElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
      }
    }
    document.addEventListener('keydown', onKey, true);
    ov.addEventListener('click', function (e) {
      var a = e.target.closest('[data-act]');
      if (!a) return;
      e.preventDefault();
      var act = a.getAttribute('data-act');
      if (act === 'accept') { if (ack.checked) done(true); }
      else done(false, act === 'faq');
    });
    setTimeout(function () { var d = ov.querySelector('.vts-dlg'); d.focus({preventScroll: true}); ov.querySelector('.vts-bd').scrollTop = 0; }, 30);
  }

  function faqCols(card) {
    if (!card || card.querySelector('.vts-fcols')) return;
    style();
    var items = [].slice.call(card.querySelectorAll(':scope > details.faq'));
    if (items.length < 6) return;
    // balance the columns by text length so both end at about the same height
    var len = items.map(function (d) { return (d.querySelector('summary') || d).textContent.length + 60; });
    var total = len.reduce(function (a, b) { return a + b; }, 0), acc = 0, cut = items.length;
    for (var i = 0; i < items.length; i++) { acc += len[i]; if (acc >= total / 2) { cut = i + 1; break; } }
    var wrap = document.createElement('div'), c1 = document.createElement('div'), c2 = document.createElement('div');
    wrap.className = 'vts-fcols';
    items[0].parentNode.insertBefore(wrap, items[0]);
    items.forEach(function (d, k) { (k < cut ? c1 : c2).appendChild(d); });
    wrap.appendChild(c1); wrap.appendChild(c2);
  }


  /* ── Risk & score / Economy & earnings panels (shared by the MF and ETF simulators) ── */
  function esc(x) { return String(x == null ? '' : x).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function num(x, d) { if (x == null || isNaN(x)) return '–'; var t = (+x).toFixed(d == null ? 1 : d); return /^-0(\.0+)?$/.test(t) ? t.slice(1) : t; }
  var BANDS = [[2, 'Low', '#22c55e'], [4, 'Low to moderate', '#84cc16'], [6, 'Moderate', '#eab308'], [8, 'High', '#f97316'], [99, 'Very high', '#ef4444']];
  function band(r) { for (var i = 0; i < BANDS.length; i++) if (r < BANDS[i][0]) return BANDS[i]; return BANDS[4]; }
  function risk10(vol, mdd) {
    if (vol == null && mdd == null) return null;
    var v = vol != null ? Math.min(vol / 25, 1) : Math.min(Math.abs(mdd) / 40, 1);
    var d = mdd != null ? Math.min(Math.abs(mdd) / 40, 1) : v;
    return Math.round(100 * (0.6 * v + 0.4 * d)) / 10;
  }
  function meter(v, col) { return '<div class="vts-meter"><span style="width:' + Math.max(2, Math.min(100, (v || 0) * 10)) + '%;background:' + col + '"></span></div>'; }
  function riskCell(r) { if (r == null) return '–'; var b = band(r); return '<div class="vts-mini"><b>' + num(r) + '</b>' + meter(r, b[2]) + '</div>'; }
  function ptsCell(p) { return p == null ? '–' : '<div class="vts-mini"><b>' + num(p) + '</b>' + meter(p, 'var(--accent)') + '</div>'; }
  function fmtMonth(d) { if (!d) return ''; var m = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(' '); return m[+d.slice(5, 7) - 1] + ' ' + d.slice(0, 4); }

  // o: {kind:'fund'|'ETF', risk10, points10, mdd:{v,vol,peak,trough,from,years,proxy}, rows:[{name, sub, w, risk, pts, vol, mdd, ok, n}]}
  function riskPanel(o) {
    var b = band(o.risk10 == null ? 0 : o.risk10), m = o.mdd || {}, k = o.kind;
    var rows = o.rows.slice().sort(function (a, c) { return c.w - a.w; });
    var wsum = rows.reduce(function (a, r) { return a + r.w; }, 0) || 1;
    var avgRisk = rows.reduce(function (a, r) { return a + (r.risk || 0) * r.w; }, 0) / wsum;
    var nOk = rows.reduce(function (a, r) { return a + (r.ok || 0); }, 0), nAll = rows.reduce(function (a, r) { return a + (r.n || 0); }, 0);
    var h = '<div class="vts-box"><h3>Total risk and points of this model portfolio</h3>' +
      '<p class="vts-sub">Risk out of 10 combines how much prices swing (volatility, 60%) and the worst fall from a peak (40%); 0 means a steady value, 10 means equity-like swings of 25%+ a year and falls of 40%+. ' +
      'Points out of 10 show how well each ' + k + ' ranked among the ' + k + 's that passed every check for its role. Totals are for the whole mix, weighted by allocation.</p>' +
      '<div class="vts-kpis">' +
        '<div class="vts-k"><small>Total risk</small><b>' + num(o.risk10) + ' <i>/ 10</i></b>' + meter(o.risk10, b[2]) + '<span class="vts-band" style="background:' + b[2] + '22;color:' + b[2] + '">' + b[1] + '</span></div>' +
        '<div class="vts-k"><small>Total points</small><b>' + num(o.points10) + ' <i>/ 10</i></b>' + meter(o.points10, 'var(--accent)') + '<em>' + nOk + ' of ' + nAll + ' checks passed</em></div>' +
        '<div class="vts-k"><small>Worst fall of the mix</small><b>' + (m.v != null ? num(m.v) + '%' : '–') + '</b><em>' + (m.peak ? fmtMonth(m.peak) + ' → ' + fmtMonth(m.trough) : 'no fall in the period') + '</em></div>' +
        '<div class="vts-k"><small>Volatility of the mix</small><b>' + (m.vol != null ? num(m.vol) + '%' : '–') + '</b><em>a year · ' + (m.years ? 'last ' + num(m.years, 0) + ' years' : '') + '</em></div>' +
      '</div>' +
      '<div class="vts-scale">' + BANDS.map(function (x, i) { return '<span style="--c:' + x[2] + '">' + (i ? BANDS[i - 1][0] : 0) + '–' + (x[0] > 10 ? 10 : x[0]) + ' ' + x[1] + '</span>'; }).join('') + '</div>' +
      '<p class="vts-note">The worst fall and volatility are measured on the ' + k + 's held together, rebalanced every week, since ' + fmtMonth(m.from) + (m.proxy ? ' — before ' + (k === 'ETF' ? 'an' : 'a') + ' ' + k + ' existed, the longest-running ' + k + ' of the same category stands in for it' : '') +
      '. Average ' + k + ' risk is ' + num(avgRisk) + '/10; the mix usually scores lower because different assets rarely fall at the same time. Past falls do not limit future falls.</p></div>';
    h += '<div class="vts-box"><h3>Risk and points of each ' + k + '</h3><p class="vts-sub">Volatility and worst fall are each ' + k + '\'s own figures over the same period as the mix (a similar ' + k + ' stands in before it was launched), so they compare directly with the whole-mix row.</p>' +
      '<div class="vts-tw vts-rkw"><table class="vts-t"><thead><tr><th>' + (k === 'ETF' ? 'ETF' : 'Fund') + '</th><th class="n">Weight</th><th class="n">Risk / 10</th><th class="n">Points / 10</th><th class="n">Volatility</th><th class="n">Worst fall</th><th class="n">Checks</th></tr></thead><tbody>' +
      rows.map(function (r) {
        return '<tr><td class="nm"><b>' + esc(r.name) + '</b><small>' + esc(r.sub) + '</small></td><td class="n">' + r.w + '%</td><td class="n">' + riskCell(r.risk) + '</td><td class="n">' + ptsCell(r.pts) +
          '</td><td class="n">' + (r.vol != null ? num(r.vol) + '%' : '–') + '</td><td class="n">' + (r.mdd != null ? num(r.mdd) + '%' : '–') + '</td><td class="n">' + (r.n ? r.ok + '/' + r.n : '–') + '</td></tr>';
      }).join('') +
      '<tr class="tot"><td>Whole mix</td><td class="n">' + Math.round(wsum) + '%</td><td class="n">' + riskCell(o.risk10) + '</td><td class="n">' + ptsCell(o.points10) + '</td><td class="n">' + (m.vol != null ? num(m.vol) + '%' : '–') +
      '</td><td class="n">' + (m.v != null ? num(m.v) + '%' : '–') + '</td><td class="n">' + nOk + '/' + nAll + '</td></tr></tbody></table></div>' +
      '<div class="vts-cards">' + rows.map(function (r) {
        return '<div class="vts-card"><div class="h">' + esc(r.name) + '<span>' + r.w + '%</span></div><div class="g"><div>Risk <b>' + num(r.risk) + '/10</b></div><div>Points <b>' + num(r.pts) + '/10</b></div>' +
          '<div>Volatility <b>' + (r.vol != null ? num(r.vol) + '%' : '–') + '</b></div><div>Worst fall <b>' + (r.mdd != null ? num(r.mdd) + '%' : '–') + '</b></div><div>Checks <b>' + (r.n ? r.ok + '/' + r.n : '–') + '</b></div><div>' + esc(r.sub) + '</div></div></div>';
      }).join('') + '</div></div>';
    return '<div class="vts-pane">' + h + '</div>';
  }

  // g: market.growth {fy, checks:[{k,v,s,why}], score, gdp:[{fy, real, infl, usd, world, f}], nominal, nominalNext, earnings:{n50, n500}}
  function ecoPanel(g, comps) {
    g = g || {};
    var sig = function (s) { return s > 0 ? '<span class="sg pos">Supportive</span>' : s < 0 ? '<span class="sg neg">Headwind</span>' : '<span class="sg neu">Neutral</span>'; };
    var comp = (comps || []).filter(function (c) { return /growth/i.test(c.k); })[0];
    var checks = g.checks || [];
    var h = '<div class="vts-box"><h3>India economy &amp; earnings checks</h3><p class="vts-sub">Seven checks on growth, inflation and company earnings, each scored +1 (supportive for shares), 0 or −1 (a headwind). ' +
      'A total of +3 or more adds 5 points of equity to the model portfolios of 5+ years, −3 or less removes 5 points — one input alongside valuation, interest rates, market falls, sentiment and global markets.</p>';
    if (!checks.length) {
      h += '<p class="vts-note">These checks will appear after the next daily data refresh.</p></div>';
      return '<div class="vts-pane">' + h + '</div>';
    }
    var now = (g.gdp || []).filter(function (x) { return x.y === g.fy; })[0], e50 = (g.earnings || {}).n50 || {}, e500 = (g.earnings || {}).n500 || {};
    var pct = function (v) { return v == null ? '–' : (v > 0 ? '+' : '') + num(v) + '%'; };
    var cards = now && now.real != null ? [
        ['Real GDP growth ' + esc(now.fy || ''), num(now.real) + '%', g.src === 'wb' ? 'latest published year' : 'forecast for this fiscal year'],
        ['Nominal GDP growth', num(g.nominal) + '%', 'real growth + inflation']]
      : [['Nifty 500 earnings', pct(e500.g1), 'last 12 months'], ['Nifty 50 earnings', e50.g3 != null ? num(e50.g3) + '%' : '–', 'a year over 3 years']];
    h += '<div class="vts-kpis" style="margin-bottom:12px">' +
      '<div class="vts-k"><small>Total score</small><b>' + (g.score > 0 ? '+' : '') + g.score + ' <i>/ ' + checks.length + '</i></b><em>' + (comp ? (comp.p > 0 ? '+5 equity points this month' : comp.p < 0 ? '−5 equity points this month' : 'no change to equity this month') : '') + '</em></div>' +
      cards.map(function (c) { return '<div class="vts-k"><small>' + c[0] + '</small><b>' + c[1] + '</b><em>' + c[2] + '</em></div>'; }).join('') +
      '<div class="vts-k"><small>Nifty 50 earnings</small><b>' + pct(e50.g1) + '</b><em>last 12 months</em></div>' +
      '</div>' + (now && now.real != null ? '' : '<p class="vts-note" style="margin:0 0 8px">GDP, inflation and growth checks are being refreshed and will appear after the next data update; the earnings checks below are current.</p>') + '<ul class="vts-cl">' + checks.map(function (c) { return '<li>' + sig(c.s) + '<span class="k">' + esc(c.k) + '</span><span class="v">' + esc(c.v) + '</span><span class="w">' + esc(c.why) + '</span></li>'; }).join('') + '</ul></div>';
    var gd = g.gdp || [];
    h += '<div class="' + (gd.length ? 'vts-grid2' : 'vts-pane') + '">';
    if (gd.length) {
      h += '<div class="vts-box"><h3>India GDP by fiscal year</h3><p class="vts-sub">April–March fiscal years.' + (g.src === 'wb' ? ' Published figures (forecasts are added when available).' : ' <b>F</b> = forecast.') + ' Nominal growth is approximated as real growth plus consumer-price inflation.</p><div class="vts-tw"><table class="vts-t" style="min-width:0"><thead><tr><th>Year</th><th class="n">Real GDP</th><th class="n">Inflation</th><th class="n">Nominal</th><th class="n">GDP size</th><th class="n">World</th></tr></thead><tbody>' +
        gd.map(function (x) {
          var nom = x.real != null && x.infl != null ? ((1 + x.real / 100) * (1 + x.infl / 100) - 1) * 100 : null, fc = x.f ? ' class="n fc"' : ' class="n"';
          return '<tr><td>' + esc(x.fy) + (x.y === g.fy ? ' <small style="color:var(--accent2);font-weight:700">now</small>' : '') + '</td><td' + fc + '>' + num(x.real) + '%</td><td' + fc + '>' + num(x.infl) + '%</td><td' + fc + '>' + num(nom) + '%</td><td' + fc + '>' + (x.usd ? '$' + num(x.usd / 1000, 2) + ' tn' : '–') + '</td><td' + fc + '>' + num(x.world) + '%</td></tr>';
        }).join('') + '</tbody></table></div></div>';
    }
    var e = g.earnings || {}, er = function (lbl, x) { x = x || {}; return '<tr><td>' + lbl + '</td><td class="n">' + num(x.pe) + '</td><td class="n">' + (x.g1 != null ? num(x.g1) + '%' : '–') + '</td><td class="n">' + (x.g3 != null ? num(x.g3) + '%' : '–') + '</td><td class="n">' + (x.g5 != null ? num(x.g5) + '%' : '–') + '</td></tr>'; };
    h += '<div class="vts-box"><h3>Company earnings</h3><p class="vts-sub">Earnings per index unit = index level ÷ P/E, compared with the same month in earlier years (3- and 5-year figures are per year).</p><div class="vts-tw"><table class="vts-t vts-earn" style="min-width:0"><thead><tr><th>Index</th><th class="n">P/E</th><th class="n">1 year</th><th class="n">3 years</th><th class="n">5 years</th></tr></thead><tbody>' +
      er('Nifty 50', e.n50) + er('Nifty Next 50', e.nn50) + er('Nifty Midcap 150', e.mid150) + er('Nifty Smallcap 250', e.sml250) +
      er('Nifty Microcap 250', e.micro250) + er('Nifty 500', e.n500) + '</tbody></table></div>' +
      (e.micro250 && e.micro250.pe != null ? '' : '<p class="vts-note" style="margin-top:6px">Nifty Microcap 250 figures appear after its history is added in the next data update.</p>') +
      '<p class="vts-note">Earnings outlook (model): over long periods company earnings tend to grow roughly in line with nominal GDP' + (g.nominalNext != null ? ', so the model uses next year\'s nominal GDP forecast of <b>' + num(g.nominalNext) + '%</b> as the expected earnings growth' : '') +
      '. This is a simple model, not a forecast of actual company results.</p></div></div>';
    h += '<p class="vts-note">GDP and inflation figures are ' + (g.src === 'wb' ? 'the latest published official international figures for India' : 'the latest official international forecasts for India, updated a few times a year') + '; earnings are updated every trading day. Economic data is often revised. For education only.</p>';
    return '<div class="vts-pane">' + h + '</div>';
  }

  /* FAQ accordion: opening one question closes the one that was open (the 'toggle' event does not bubble, so listen
     in the capture phase); the newly opened question stays in view even when a longer one above it closes */
  document.addEventListener('toggle', function (e) {
    var d = e.target;
    if (!d || d.tagName !== 'DETAILS' || !d.classList.contains('faq') || !d.open) return;
    var top = d.getBoundingClientRect().top, moved = false;
    document.querySelectorAll('details.faq[open]').forEach(function (o) { if (o !== d) { o.open = false; moved = true; } });
    if (moved) { var shift = d.getBoundingClientRect().top - top; if (Math.abs(shift) > 1) window.scrollBy(0, shift); }
  }, true);

  /* Simulator Buy card: SIMULATED agent accounts that follow the 10+ year model portfolios with real-life order rules
     from the start date. Public data = data/sim_scoreboard.json (name, model, schedule, return % only — absolute under
     one year, XIRR after; null until an account has been valued). Fills every element with data-vts-buy="mf" | "etf".
     No real money is invested and nothing is bought on anyone's behalf — the card says so prominently. */
  function simBuy() {
    var els = document.querySelectorAll('[data-vts-buy]');
    if (!els.length || !window.fetch) return;
    fetch('data/sim_scoreboard.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (sb) {
      if (!sb) return;
      style();
      var d = function (x) { return new Date(String(x).slice(0, 10) + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); };
      var inr = function (v) { return '₹' + Number(v).toLocaleString('en-IN'); };
      var started = new Date() >= new Date(sb.start + 'T00:00:00');
      els.forEach(function (el) {
        var prod = el.getAttribute('data-vts-buy'), what = prod === 'etf' ? 'ETF' : 'mutual fund';
        var rows = (sb.rows || []).filter(function (r) { return r.product === prod; });
        if (!rows.length) { el.innerHTML = ''; return; }
        rows.sort(function (a, b) { return (b.ret == null ? -1e9 : b.ret) - (a.ret == null ? -1e9 : a.ret); });
        var anyRet = rows.some(function (r) { return r.ret != null; });
        var metric = rows.some(function (r) { return r.metric === 'xirr'; }) ? 'XIRR (annualised)' : 'absolute return so far';
        var retTxt = function (r) {
          if (r.ret != null) return (r.ret > 0 ? '+' : '') + r.ret.toFixed(2) + '%';
          return started ? (sb.auditOk === false ? 'Under review' : 'Buy in progress') : 'Starts ' + d(sb.start).replace(/ \d{4}$/, '');
        };
        var cls = function (r) { return r.ret == null ? ' na' : r.ret >= 0 ? ' up' : ' dn'; };
        var card = function (r) {
          return '<div class="vts-buy-c" role="listitem"><div class="vts-buy-who"><div><b>' + esc(r.name) + '</b>' + (r.nri ? '<i class="vts-buy-nri">NRI</i>' : '') + '</div>' +
            '<span>10+ yr ' + esc(r.risk) + ' · ' + esc(r.freq) + (r.amt ? ' ' + inr(r.amt) : '') + '</span></div><strong class="' + cls(r).trim() + '">' + retTxt(r) +
            (r.ret != null ? '<small>' + (r.metric === 'xirr' ? 'XIRR' : 'abs') + '</small>' : '') + '</strong></div>';
        };
        el.innerHTML = '<section class="vts-buy" aria-label="Simulator Buy — simulated accounts">' +
          '<div class="vts-buy-h"><div class="vts-buy-t1"><b>🧾 Simulator Buy</b><span class="vts-buy-badge">Simulation · not real money</span></div>' +
          '<span class="vts-buy-sub">' + rows.length + ' simulated ' + what + ' accounts of VilfinTV agents following this simulator\'s 10+ year model portfolios' +
          (anyRet ? ' since ' + esc(d(sb.start)) + ' · ' + metric : ' · simulated buying from ' + esc(d(sb.start))) + '</span></div>' +
          '<p class="vts-buy-warn"><b>Disclaimer:</b> This is a <b>simulation for education only — not a real purchase</b>. No real money is invested, no units are bought or held for anyone, and the agents are internal test accounts, not real investors. Figures are calculated from official end-of-day prices with stamp duty' + (prod === 'etf' ? ', brokerage and exchange charges' : '') + ', exit loads, taxes and settlement days, to show how the model portfolios would have behaved. Not investment advice; not a recommendation to buy any fund. Past or simulated results do not predict future returns.</p>' +
          '<div class="vts-buy-g" role="list" aria-label="Simulated accounts">' + rows.map(card).join('') + '</div>' +
          '<p class="vts-buy-n">' + (anyRet ? 'Return: absolute for accounts under one year old, XIRR after. ' : '') + 'Updated ' + esc(d(sb.updated)) + (sb.auditOk === false ? ' · figures withheld while a data check is resolved' : '') + '.</p></section>';
      });
    }).catch(function () {});
  }
  CSS += '.vts-buy{border:1px solid var(--border2,var(--border));border-left:4px solid #f5a524;border-radius:var(--radius,12px);background:var(--surface);padding:14px 16px;margin:0 0 16px;min-width:0;overflow:hidden}' +
    '.vts-buy-h{display:flex;flex-direction:column;gap:4px}.vts-buy-t1{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:15px}' +
    '.vts-buy-badge{display:inline-block;background:rgba(245,165,36,.16);color:#c77800;border:1px solid rgba(245,165,36,.55);border-radius:999px;padding:2px 10px;font-size:11px;font-weight:800;letter-spacing:.5px;text-transform:uppercase}' +
    '[data-theme="dark"] .vts-buy-badge,.dark .vts-buy-badge{color:#f5b54a}' +
    '@media (prefers-color-scheme:dark){.vts-buy-badge{color:#f5b54a}}' +
    '.vts-buy-sub{color:var(--text2);font-size:12.5px}' +
    '.vts-buy-warn{margin:10px 0 0;background:rgba(245,165,36,.09);border:1px solid rgba(245,165,36,.35);border-radius:8px;padding:9px 12px;font-size:12px;line-height:1.55;color:var(--text2)}.vts-buy-warn b{color:var(--text)}' +
    '.vts-buy-g{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px;margin-top:12px}' +
    '.vts-buy-c{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid var(--border);border-radius:10px;padding:8px 12px;background:var(--surface2,transparent);min-width:0}' +
    '.vts-buy-who{display:flex;flex-direction:column;min-width:0}.vts-buy-who b{font-size:13px}.vts-buy-who span{color:var(--text2);font-size:11.5px;line-height:1.35}' +
    '.vts-buy-nri{font-style:normal;font-size:10px;font-weight:800;color:var(--text2);border:1px solid var(--border2,var(--border));border-radius:4px;padding:0 4px;margin-left:6px;vertical-align:1px}' +
    '.vts-buy-c strong{font-variant-numeric:tabular-nums;font-size:13px;text-align:right;white-space:nowrap}.vts-buy-c strong small{display:block;font-size:10px;color:var(--text2);font-weight:600}' +
    '.vts-buy .up{color:#16a34a}.vts-buy .dn{color:#dc2626}.vts-buy .na{color:var(--text2);font-weight:600;font-size:12px}' +
    '.vts-buy-n{margin:8px 0 0;font-size:11px;color:var(--text3,var(--text2))}' +
    '@media (max-width:520px){.vts-buy{padding:12px}.vts-buy-g{grid-template-columns:1fr}}' +
    '';
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', simBuy); else simBuy();

  window.VTSim = { gate: gate, accepted: accepted, faqCols: faqCols, riskPanel: riskPanel, ecoPanel: ecoPanel, risk10: risk10, css: style, simBuy: simBuy };
})();
