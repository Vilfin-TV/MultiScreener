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
    '@media (max-width:560px){.vts-tabs{overflow:visible;gap:4px}.vts-tabs button{flex:1 1 0;min-width:0;height:auto;min-height:46px;padding:6px 6px;white-space:normal;line-height:1.25;font-size:12.5px}}' +
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
    '.vts-seg{display:inline-flex;flex-wrap:wrap;gap:4px;background:var(--surface2,transparent);border:1px solid var(--border);border-radius:10px;padding:3px;margin:4px 0 10px}' +
    '.vts-seg button{border:0;background:none;color:var(--text2);font:inherit;font-size:12.5px;font-weight:700;padding:6px 12px;border-radius:7px;cursor:pointer}' +
    '.vts-seg button.on{background:var(--accent,#2563eb);color:#fff}' +
    '.vts-earnw{max-height:520px;overflow:auto;border:1px solid var(--border);border-radius:10px;margin:0}' +
    '.vts-earn{min-width:820px!important}.vts-earn thead th{position:sticky;top:0;background:var(--surface);z-index:2}' +
    '.vts-earn td:first-child,.vts-earn th:first-child{position:sticky;left:0;background:var(--surface);z-index:1;white-space:nowrap}.vts-earn thead th:first-child{z-index:3}' +
    '.vts-earn .up{color:#16a34a;font-weight:700}.vts-earn .dn{color:#dc2626;font-weight:700}' +
    '.vts-es{border:0;background:none;color:inherit;font:inherit;text-transform:inherit;letter-spacing:inherit;cursor:pointer;padding:0;white-space:nowrap}.vts-es.on{color:var(--accent2,var(--accent,#2563eb))}' +
    '@media (max-width:520px){.vts-earn th,.vts-earn td{padding:8px 6px;font-size:12px}.vts-earn th{font-size:10.5px;letter-spacing:0}.vts-earnw{max-height:440px}}' +
    '.vts-t td.fc{color:var(--text2)}.vts-t td.fc::after{content:" F";font-size:10px;font-weight:800;color:var(--accent2)}' +
    '.vts-note{font-size:12px;color:var(--text2);line-height:1.55;margin-top:10px}' +
    '@media (max-width:900px){.vts-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.vts-grid2{grid-template-columns:1fr}}' +
    '@media (max-width:640px){.vts-box{padding:14px}.vts-k b{font-size:20px}.vts-tw.vts-rkw{display:none}.vts-cards{display:grid;gap:8px}' +
    '.vts-card{border:1px solid var(--border);border-radius:10px;padding:10px 12px;background:var(--surface2)}' +
    '.vts-card .h{display:flex;justify-content:space-between;gap:8px;font-weight:700;font-size:13px}.vts-card .h span{flex:none;color:var(--text2)}' +
    '.vts-card .g{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 12px;margin-top:8px;font-size:12px;color:var(--text2)}.vts-card .g b{color:var(--text);font-variant-numeric:tabular-nums}' +
    '.vts-cl li{grid-template-columns:auto 1fr}.vts-cl .v{grid-column:2;text-align:left}.vts-cl .w{grid-column:1/3}}';

  function style() {
    var cur = document.getElementById('vtsCss');
    if (cur) { if (cur.textContent.length !== CSS.length) cur.textContent = CSS; return; }
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
    style();
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
    var hTot = h; h = '';
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
    return '<div class="vts-pane">' +
      ecoSec('risk', 'Total risk and points of this model portfolio', 'Risk ' + num(o.risk10) + ' / 10 (' + b[1] + ') · points ' + num(o.points10) + ' / 10 · worst fall and volatility of the mix', hTot, true) +
      ecoSec('riskf', 'Risk and points of each ' + k, rows.length + ' ' + k + 's — risk / 10, points / 10, volatility, worst fall and checks passed', h, false) + '</div>';
  }

  // g: market.growth {fy, checks:[{k,v,s,why}], score, gdp:[{fy, real, infl, usd, world, f}], nominal, nominalNext, earnings:{n50, n500}}
  var lastEco = null;          // ecoPanel returns a string; the earnings box re-renders itself from this on tab / sort clicks
  function ecoPanel(g, comps) {
    style();
    g = g || {};
    lastEco = g;
    var sig = function (s) { return s > 0 ? '<span class="sg pos">Supportive</span>' : s < 0 ? '<span class="sg neg">Headwind</span>' : '<span class="sg neu">Neutral</span>'; };
    var comp = (comps || []).filter(function (c) { return /growth/i.test(c.k); })[0];
    var checks = g.checks || [];
    var nck = (g.checks || []).length, thr = g.thr || Math.max(3, Math.round(nck * 0.4));
    var h = '<div class="vts-box"><h3>India economy &amp; earnings checks</h3><p class="vts-sub">' + (nck || 'These') + ' checks on growth, inflation, company earnings and profitability — the figures fund-house analysts track — each scored +1 (supportive for shares), 0 or −1 (a headwind). ' +
      'A total of +' + thr + ' or more adds 5 points of equity to the model portfolios of 5+ years, −' + thr + ' or less removes 5 points — one input alongside valuation, interest rates, market falls, sentiment and global markets.</p>';
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
    var p1 = h; h = '';
    var gd = g.gdp || [];
    h += '<div class="vts-pane">';
    if (gd.length) {
      h += '<div class="vts-box"><h3>India GDP by fiscal year</h3><p class="vts-sub">April–March fiscal years.' + (g.src === 'wb' ? ' Published figures (forecasts are added when available).' : ' <b>F</b> = forecast.') + ' Nominal growth is approximated as real growth plus consumer-price inflation.</p><div class="vts-tw"><table class="vts-t" style="min-width:0"><thead><tr><th>Year</th><th class="n">Real GDP</th><th class="n">Inflation</th><th class="n">Nominal</th><th class="n">GDP size</th><th class="n">World</th></tr></thead><tbody>' +
        gd.map(function (x) {
          var nom = x.real != null && x.infl != null ? ((1 + x.real / 100) * (1 + x.infl / 100) - 1) * 100 : null, fc = x.f ? ' class="n fc"' : ' class="n"';
          return '<tr><td>' + esc(x.fy) + (x.y === g.fy ? ' <small style="color:var(--accent2);font-weight:700">now</small>' : '') + '</td><td' + fc + '>' + num(x.real) + '%</td><td' + fc + '>' + num(x.infl) + '%</td><td' + fc + '>' + num(nom) + '%</td><td' + fc + '>' + (x.usd ? '$' + num(x.usd / 1000, 2) + ' tn' : '–') + '</td><td' + fc + '>' + num(x.world) + '%</td></tr>';
        }).join('') + '</tbody></table></div></div>';
    }
    h += '</div>';
    var p2 = gd.length ? h : '';
    h = earnBox(g);
    h += '<p class="vts-note">GDP and inflation figures are ' + (g.src === 'wb' ? 'the latest published official international figures for India' : 'the latest official international forecasts for India, updated a few times a year') + '; earnings are updated every trading day. Economic data is often revised. For education only.</p>';
    return '<div class="vts-pane">' +
      ecoSec('checks', 'India economy & earnings checks', 'Total score ' + (g.score > 0 ? '+' : '') + g.score + ' of ' + checks.length + ' — growth, inflation, earnings and profitability', p1, true) +
      (p2 ? ecoSec('gdp', 'India GDP by fiscal year', 'Real growth, inflation, nominal growth and GDP size, with forecasts', p2, false) : '') +
      ecoSec('earn', 'Company earnings & valuation', 'P/E, P/B, ROE, earnings growth and PEG for every Nifty index' + (g.gidx ? ' and key global indices' : ''), h, false) +
      ecoSec('faq', 'Economy & earnings — FAQs', 'How these figures are calculated and how the model uses them', ecoFaq(thr, nck), false) + '</div>';
  }
  /* Economy & earnings sections: each one has an Expand / Minimise bar; the viewer's choice is remembered on this device */
  function ecoSec(key, title, hint, body, def) {
    var st = null;
    try { st = localStorage.getItem('vt_eco_' + key); } catch (e) {}
    var open = st == null ? def : st === '1';
    return '<details class="vts-eco" data-eco="' + key + '"' + (open ? ' open' : '') + '><summary><span class="vts-eco-t"><b>' + esc(title) + '</b><small>' + esc(hint) + '</small></span>' +
      '<span class="vts-eco-b"><span class="o">Expand</span><span class="c">Minimise</span><i aria-hidden="true">▾</i></span></summary><div class="vts-eco-in">' + body + '</div></details>';
  }
  document.addEventListener('toggle', function (e) {
    var d = e.target;
    if (d && d.classList && d.classList.contains('vts-eco')) { try { localStorage.setItem('vt_eco_' + d.getAttribute('data-eco'), d.open ? '1' : '0'); } catch (er) {} }
  }, true);
  function ecoFaq(thr, nck) {
    var q = [
      ['Why does the Portfolio Simulator look at the economy and company earnings?',
       'Over long periods share prices follow company earnings, and earnings follow the economy. Growth, inflation and profitability tell the model whether the backdrop for shares is supportive or a headwind. They are one input alongside valuation, interest rates, market falls, sentiment and global markets — never the only reason for a change.'],
      ['How does the total score change the model portfolios?',
       'Each of the ' + (nck || 10) + ' checks scores +1 (supportive), 0 (neutral) or −1 (headwind). A total of +' + thr + ' or more adds 5 percentage points of equity to the model portfolios of 5 years and longer; −' + thr + ' or less removes 5 points. Anything in between leaves the mix unchanged. Strategic changes are applied only at the monthly review.'],
      ['What is the difference between real and nominal GDP growth?',
       'Real growth measures how much more the economy produces, after removing price rises. Nominal growth is real growth plus inflation — growth in rupee terms. Company sales and profits are earned in rupees, so over long periods earnings tend to grow roughly in line with nominal GDP.'],
      ['How is the earnings growth of an index calculated?',
       'Earnings per index unit = index level ÷ its P/E, compared with the same month one, three and five years earlier (three- and five-year growth is per year, compounded). These are trailing earnings — what companies have already reported — not forecasts.'],
      ['Why do some growth figures look very large, negative or blank?',
       'Very large growth usually comes from a low base — companies moving from losses or thin profits back to normal profits — and rarely repeats. Negative figures mean reported profits fell. A dash means the index, or VilfinTV\'s own monthly record for a global index, does not yet have enough history for that period; the figures fill in automatically as months pass.'],
      ['What do P/E, P/B, ROE, earnings yield and PEG mean?',
       '<b>P/E</b> = price ÷ earnings (what investors pay for ₹1 of profit). <b>P/B</b> = price ÷ book value. <b>ROE</b> = P/B ÷ P/E — the profit companies earn on shareholders\' money (15%+ is strong, below 12% weak). <b>Earnings yield</b> = 1 ÷ P/E, comparable with bond yields. <b>PEG</b> = P/E ÷ 3-year earnings growth — below about 1.5 suggests growth is reasonably priced.'],
      ['How are the global indices valued?',
       'Each global index is valued from the published P/E, P/B and dividend yield of the holdings of a large exchange-traded fund that tracks it (shown under its name), in that market\'s currency. Its earnings growth is measured from VilfinTV\'s own monthly records, so it fills in over time.'],
      ['How often are these figures updated?',
       'Index valuations and earnings are refreshed every trading day from the exchange\'s official index files. GDP and inflation come from official international figures for India, which are revised a few times a year.'],
      ['Do strong economic numbers mean markets will rise?',
       'No. Markets often price good news in advance, and shares can fall in a strong economy or rise in a weak one. These checks only nudge the model\'s equity share by a small amount; they are not a forecast. The Portfolio Simulator is an educational model — not investment advice.']
    ];
    return '<div class="vts-box vts-efaq">' + q.map(function (x) {
      return '<details class="vts-efq"><summary>' + esc(x[0]) + '</summary><p>' + x[1] + '</p></details>';
    }).join('') + '</div>';
  }

  /* Company earnings for every Nifty index: broad market and sector / theme views, sortable columns.
     e: {key: {pe, pb, roe, dy, ey, g1, g3, g5, peg}} · names: {key: index name} · broad: [keys] */
  var EARN_COLS = [['pe', 'P/E', 'Price ÷ trailing earnings — lower is cheaper'], ['pb', 'P/B', 'Price ÷ book value'],
    ['roe', 'ROE', 'Return on equity = P/B ÷ P/E — how much profit companies earn on shareholders\' money'],
    ['dy', 'Div. yield', 'Dividends paid in the last year ÷ price'], ['ey', 'Earn. yield', 'Earnings ÷ price (1 ÷ P/E) — compare with the 10-year government bond yield'],
    ['g1', 'EPS 1Y', 'Earnings growth over the last 12 months'], ['g3', 'EPS 3Y', 'Earnings growth a year over 3 years'],
    ['g5', 'EPS 5Y', 'Earnings growth a year over 5 years'], ['peg', 'PEG', 'P/E ÷ 3-year earnings growth — below 1.5 is attractive, above 2.5 expensive']];
  var earnState = { view: 'broad', sort: 'g1', dir: -1 };
  function earnRows(g) {
    var e = g.earnings || {}, names = g.names || {}, broad = g.broad || ['n50', 'nn50', 'mid150', 'sml250', 'micro250', 'n500', 'totalmkt'];
    var keys = Object.keys(e).filter(function (k) { return earnState.view === 'broad' ? broad.indexOf(k) >= 0 : broad.indexOf(k) < 0; });
    if (earnState.view === 'broad') keys.sort(function (a, b) { return broad.indexOf(a) - broad.indexOf(b); });
    else keys.sort(function (a, b) {
      var x = e[a][earnState.sort], y = e[b][earnState.sort];
      if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      return (x - y) * earnState.dir;
    });
    var since = g.since || {};
    var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var avail = function (key, yrs) {                        // when a figure first becomes available
      var s0 = since[key]; if (!s0) return null;
      var y = +s0.slice(0, 4) + yrs, m = +s0.slice(5, 7);
      return MON[m - 1] + ' ' + y;
    };
    var f = function (k, v, key, x) {
      if (v == null) {
        var yrs = { g1: 1, g3: 3, g5: 5, peg: 3 }[k];
        if (k === 'peg' && x && x.g3 != null) return '<span class="vts-na" title="PEG needs positive 3-year earnings growth">n/a</span>';
        var a = yrs && avail(key, yrs);
        return a ? '<span class="vts-na" title="This index has data from ' + esc(avail(key, 0)) + '; this figure first appears in ' + esc(a) + '">from ' + esc(a.replace(/ 20(\d\d)$/, " '$1")) + '</span>' : '–';
      }
      if (k === 'pe' || k === 'pb' || k === 'peg') return num(v, k === 'pe' ? 1 : 2);
      var t = num(v, 1) + '%';
      return /^g/.test(k) ? '<span class="' + (v >= 0 ? 'up' : 'dn') + '">' + (v > 0 ? '+' : '') + t + '</span>' : t;
    };
    var nm = function (k) { return esc(String(names[k] || k).replace(/^Nifty /, earnState.view === 'broad' ? 'Nifty ' : '')); };
    var rows = keys.map(function (k) {
      return '<tr><td>' + nm(k) + '</td>' + EARN_COLS.map(function (c) { return '<td class="n">' + f(c[0], e[k][c[0]], k, e[k]) + '</td>'; }).join('') + '</tr>';
    }).join('');
    var gi = g.gidx;
    if (earnState.view === 'broad' && gi && (gi.order || []).length) {      // global indices, after the Indian broad market
      rows += '<tr class="vts-earn-sec"><td colspan="' + (EARN_COLS.length + 1) + '">Global indices</td></tr>' + gi.order.map(function (k) {
        var x = gi.earnings[k] || {};
        return '<tr><td>' + esc(gi.names[k] || k) + '<small class="vts-earn-via">via ' + esc((gi.via || {})[k] || '') + ' holdings</small></td>' + EARN_COLS.map(function (c) { return '<td class="n">' + f(c[0], x[c[0]], k, x) + '</td>'; }).join('') + '</tr>';
      }).join('');
    }
    return rows || '<tr><td colspan="10" class="vts-note">Figures appear after the next data update.</td></tr>';
  }
  function earnBox(g) {
    var e = g.earnings || {}, broad = g.broad || ['n50', 'nn50', 'mid150', 'sml250', 'micro250', 'n500', 'totalmkt'], nSec = Object.keys(e).filter(function (k) { return broad.indexOf(k) < 0; }).length;
    var head = EARN_COLS.map(function (c) {
      var on = earnState.view !== 'broad' && earnState.sort === c[0];
      return '<th class="n" title="' + esc(c[2]) + '">' + (earnState.view === 'broad' ? c[1] : '<button type="button" class="vts-es' + (on ? ' on' : '') + '" data-es="' + c[0] + '" aria-label="Sort by ' + esc(c[1]) + '">' + c[1] + (on ? (earnState.dir < 0 ? ' ▾' : ' ▴') : '') + '</button>') + '</th>';
    }).join('');
    return '<div class="vts-box vts-earnbox"><h3>Company earnings &amp; valuation — every Nifty index' + (g.gidx ? ' and key global indices' : '') + '</h3>' +
      '<p class="vts-sub">Earnings per index unit = index level ÷ P/E, compared with the same month in earlier years (3- and 5-year growth is per year). ROE = P/B ÷ P/E. Tap a column name in Sectors &amp; themes to sort.</p>' +
      '<div class="vts-seg" role="tablist" aria-label="Index group"><button type="button" role="tab" data-ev="broad" aria-selected="' + (earnState.view === 'broad') + '" class="' + (earnState.view === 'broad' ? 'on' : '') + '">Broad market</button>' +
      (nSec ? '<button type="button" role="tab" data-ev="sector" aria-selected="' + (earnState.view !== 'broad') + '" class="' + (earnState.view !== 'broad' ? 'on' : '') + '">Sectors &amp; themes (' + nSec + ')</button>' : '') + '</div>' +
      '<div class="vts-tw vts-earnw"><table class="vts-t vts-earn"><thead><tr><th>Index</th>' + head + '</tr></thead><tbody>' + earnRows(g) + '</tbody></table></div>' +
      '<p class="vts-note">Earnings outlook (model): over long periods company earnings tend to grow roughly in line with nominal GDP' + (g.nominalNext != null ? ', so the model uses next year\'s nominal GDP forecast of <b>' + num(g.nominalNext) + '%</b> as the expected earnings growth' : '') +
      '. Young indices have shorter histories: where a 1-, 3- or 5-year figure cannot exist yet, the table shows the month it first becomes available ("from Jun \'27"). Very large growth figures usually come from a low base — companies moving from losses or thin profits to solid profits — and rarely repeat. This is a simple model, not a forecast of actual company results.</p>' +
      (g.gidx ? '<p class="vts-note">Global indices: P/E, P/B and dividend yield of the holdings of a large exchange-traded fund that tracks each index (shown under its name), in that market\'s currency. Their earnings growth is measured from VilfinTV\'s own monthly records' + (g.gidx.since ? ' kept since ' + esc(g.gidx.since) : '') + ', so 1-, 3- and 5-year figures fill in as those records age.</p>' : '') + '</div>';
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.vts-earnbox [data-ev], .vts-earnbox [data-es]');
    if (!b) return;
    var box = b.closest('.vts-earnbox'), g = box && (box._g || lastEco);
    if (!g) return;
    if (b.hasAttribute('data-ev')) earnState.view = b.getAttribute('data-ev');
    else { var k = b.getAttribute('data-es'); earnState.dir = earnState.sort === k ? -earnState.dir : -1; earnState.sort = k; }
    var tmp = document.createElement('div'); tmp.innerHTML = earnBox(g);
    var nb = tmp.firstChild; nb._g = g; box.parentNode.replaceChild(nb, box);
  });

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
  /* ── Simulator Buy: simulated accounts of VilfinTV agents that follow the 10+ year model portfolios. One person at a
     time (profile switcher), with the daily portfolio summary recorded in the ledger journal, a Portfolio-vs-Nifty-50
     chart, holdings and recent days. Data: data/sim_scoreboard.json + data/sim/<person>.json (audited). ── */
  function simBuy() {
    var els = document.querySelectorAll('[data-vts-buy]'), bySrc = {};
    if (!els.length || !window.fetch) return;
    els.forEach(function (el) { var u = el.getAttribute('data-vts-src') || 'data/sim_scoreboard.json'; (bySrc[u] = bySrc[u] || []).push(el); });
    Object.keys(bySrc).forEach(function (u) {
      fetch(u, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (sb) {
        if (!sb) return;
        style();
        bySrc[u].forEach(function (el) { simBuyCard(el, sb); });
      }).catch(function () {});
    });
  }

  function simBuyCard(el, sb) {
    var prod = el.getAttribute('data-vts-buy'), mf = prod === 'mf', gl = prod === 'gl', what = mf ? 'mutual fund' : gl ? 'US-listed ETF' : 'ETF';
    var CUR = sb.cur === 'USD' ? '$' : '₹', LOC = sb.cur === 'USD' ? 'en-US' : 'en-IN', BN = sb.bench || 'Nifty 50', BK = sb.benchKey || 'NIFTYBEES';
    var UD = mf ? 3 : gl ? 4 : 0;
    var rows = (sb.rows || []).filter(function (r) { return r.product === prod; });
    if (!rows.length) { el.innerHTML = ''; return; }
    var dt = function (x, yr) { var s = new Date(String(x).slice(0, 10) + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); return yr === false ? s.replace(/ \d{4}$/, '') : s; };
    var dtw = function (x) { return new Date(String(x).slice(0, 10) + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }); };
    var num = function (v, dp) { return v == null ? '–' : Number(v).toLocaleString(LOC, { minimumFractionDigits: dp, maximumFractionDigits: dp }); };
    var inr = function (v, dp) { return v == null ? '–' : (v < 0 ? '−' : '') + CUR + num(Math.abs(v), dp == null ? 2 : dp); };
    var sinr = function (v, dp) { return v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + CUR + num(Math.abs(v), dp == null ? 2 : dp); };
    var spct = function (v, dp) { return v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dp == null ? 2 : dp) + '%'; };
    var cl = function (v) { return v == null ? 'na' : v > 0 ? 'up' : v < 0 ? 'dn' : ''; };
    var started = new Date() >= new Date(sb.start + 'T00:00:00');
    var initials = function (n) { return String(n).split(/\s+/).map(function (w) { return w.charAt(0); }).join('').slice(0, 2).toUpperCase(); };
    var hue = function (n) { var h = 0; for (var i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i)) % 360; return h; };
    var av = function (r, big) { return '<span class="vts-pf-av' + (big ? ' lg' : '') + '" style="background:hsl(' + hue(r.name) + ' 55% 42%)" aria-hidden="true">' + esc(initials(r.name)) + '</span>'; };
    var plan = function (r) { return '10+ yr ' + esc(r.risk) + ' · ' + esc(r.freq) + (r.amt ? ' ' + inr(r.amt, 0) : ''); };
    var status = function (r) {
      if (r.ret != null) return '<b class="' + cl(r.ret) + '">' + spct(r.ret) + '</b><small>' + (r.metric === 'xirr' ? 'XIRR' : 'total') + '</small>';
      if (!started) return '<b class="na">Starts ' + esc(dt(sb.start, false)) + '</b>';
      if (sb.auditOk === false) return '<b class="na">Under review</b>';
      return '<b class="na">' + (r.credit ? 'Units credited ' + esc(dt(r.credit, false)) : 'Buy in progress') + '</b>';
    };
    rows.sort(function (a, b) { return (b.ret == null ? -1e9 : b.ret) - (a.ret == null ? -1e9 : a.ret) || (a.name < b.name ? -1 : 1); });
    var key = 'vt_simbuy_' + prod, sel = null;
    try { sel = localStorage.getItem(key); } catch (e) {}
    var cur = rows.filter(function (r) { return r.name === sel; })[0] || rows[0];
    var best = rows.filter(function (r) { return r.ret != null; })[0];
    var crBy = rows.reduce(function (m, r) { return r.credit && r.credit > m ? r.credit : m; }, '');
    var peek = best ? 'Top: ' + esc(best.name) + ' ' + spct(best.ret) + ' · ' + rows.length + ' accounts'
      : rows.length + ' accounts · ' + (started ? (sb.auditOk === false ? 'under review' : 'buy in progress' + (crBy ? ' · units credited by ' + esc(dt(crBy, false)) : '')) : 'starts ' + esc(dt(sb.start)));
    el.innerHTML = '<details class="vts-buy">' +
      '<summary class="vts-buy-h" aria-label="Simulator Buy — simulated accounts. Show or hide details">' +
      '<div class="vts-buy-t1"><b>🧾 Simulator Buy</b><span class="vts-buy-badge">Simulation · not real money</span><span class="vts-buy-peek">' + peek + '</span>' +
      '<span class="vts-buy-tg" aria-hidden="true"><span class="o">Show</span><span class="c">Hide</span><i>▾</i></span></div>' +
      '<span class="vts-buy-sub">Follow each of ' + rows.length + ' simulated ' + what + ' accounts of VilfinTV agents day by day as they buy this simulator\'s 10+ year model portfolios — value, daily change and why it moved.</span></summary>' +
      '<div class="vts-buy-b">' +
      '<p class="vts-buy-warn"><b>Disclaimer:</b> This is a <b>simulation for education only — not a real purchase</b>. No real money is invested, no units are bought or held for anyone, and the agents are internal test accounts, not real investors. Figures are calculated from official end-of-day prices with ' + (gl ? 'commission, US tax withheld on dividends and settlement days; currency conversion and remittance costs are not modelled' : 'stamp duty' + (mf ? '' : ', brokerage and exchange charges') + ', exit loads, taxes and settlement days') + ', to show how the model portfolios would have behaved. Not investment advice; not a recommendation to buy any fund. Past or simulated results do not predict future returns.</p>' +
      (gl
        ? '<details class="vts-buy-rule"><summary>⏱ How each ETF trade is priced</summary><ul>' +
          '<li><b>When:</b> every buy is placed on its plan date as a market-on-close order — it executes at the end of that day\'s US session, <b>4:00 pm New York time</b> (1:30 am IST in the northern summer, 2:30 am in winter).</li>' +
          '<li><b>Share price:</b> the exchange\'s <b>official closing price</b> of that session. On a US market holiday or a day the ETF did not trade, it executes at the close of the next session it trades.</li>' +
          '<li><b>Shares:</b> fractional shares in steps of 0.0001 — as many as the amount buys after commission ($0.0035 a share, at least $0.35, at most 1% of the trade). Cents left over, or an order under $1, wait for that slot\'s next buy. Shares are credited the next US business day (T+1).</li>' +
          '<li><b>Dividends:</b> shares bought before the ex-date earn the dividend, less US tax withheld (25% for India residents under the tax treaty; nothing at source for the US-based team members). The cash joins that slot\'s next buy.</li>' +
          '<li><b>Record:</b> each trade in the ledger stores this rule, its trade date and the closing price used, and the daily audit checks every trade, dividend and value again.</li></ul></details>'
        : mf
        ? '<details class="vts-buy-rule"><summary>⏱ How each fund purchase is priced</summary><ul>' +
          '<li><b>When:</b> every purchase is placed on its plan date before the 3 pm IST cut-off.</li>' +
          '<li><b>Unit price:</b> the fund\'s <b>official NAV of that business day</b> (liquid and overnight funds: the NAV of the previous calendar day); if the fund house has no NAV that day, the next NAV day. Stamp duty of 0.005% is taken first; units are rounded down to 3 decimals and credited two business days later (market holidays skipped). Until then the purchase shows as "buy in progress" — no return, gain or stamp duty is shown before the units are credited.</li>' +
          '<li><b>Record:</b> each purchase in the ledger stores its NAV date and NAV, and the daily audit checks it against the official NAV file.</li>' +
          '<li><b>Market-dip buys</b> (Govind, Nithin and Aishwarya only): a ₹20,000 reserve sits in a liquid fund (topped up with the same ₹20,000 on the first trading day of the month after it is used up). After a confirmed dip close, the dip amount is redeemed the next trading day at the liquid fund\'s applicable NAV, paid out the following business day and invested in the segment\'s model fund at that day\'s NAV — the same cut-off, stamp duty and T+2 credit rules apply.</li></ul></details>'
        : '<details class="vts-buy-rule"><summary>⏱ How each ETF trade is priced</summary><ul>' +
          '<li><b>When:</b> every buy (and any sale) is placed on its plan date and treated as a market-on-close order — it executes at the end of that day\'s trading session, <b>3:30 pm IST</b>.</li>' +
          '<li><b>Unit price:</b> the exchange\'s <b>official closing price</b> of that session (the weighted average price of the last 30 minutes of trading, 3:00–3:30 pm IST). If the market is closed (weekend or exchange holiday) or the ETF did not trade that day, it executes at the close of the next session it trades.</li>' +
          '<li><b>Units:</b> whole units only, as many as the amount buys after charges; cash left over is added to the next buy of the same ETF. Units are credited the next trading day (T+1).</li>' +
          '<li><b>Record:</b> each trade in the ledger stores this rule, its trade date and the closing price used, and the daily audit checks every trade against the exchange\'s published closing price for that session.</li>' +
          '<li><b>Market-dip buys</b> (Govind, Nithin and Aishwarya only): a ₹20,000 reserve sits in a liquid ETF (topped up with the same ₹20,000 on the first trading day of the month after it is used up). After a confirmed dip close, whole liquid-ETF units worth the dip amount are sold at the next session\'s close and the segment\'s model ETF is bought at the following session\'s close, once the sale proceeds settle.</li></ul></details>') +
      '<div class="vts-pf"><div class="vts-pf-bar"><button type="button" class="vts-pf-me" aria-haspopup="dialog"></button><span class="vts-pf-st vts-pf-cur"></span>' +
      '<button type="button" class="vts-pf-sw" aria-haspopup="listbox" aria-expanded="false">Switch <i>▾</i></button></div>' +
      '<div class="vts-pf-list" role="listbox" aria-label="Switch account" hidden></div></div>' +
      '<div class="vts-pv" aria-live="polite"></div>' +
      '<p class="vts-buy-n">Total return: absolute for accounts under one year old, XIRR after. Day change excludes new money. Updated ' + esc(dt(sb.updated)) + (sb.auditOk === false ? ' · figures withheld while a data check is resolved' : '') + '.</p></div></details>';
    var sw = el.querySelector('.vts-pf-sw'), me = el.querySelector('.vts-pf-me'), stEl = el.querySelector('.vts-pf-cur'), list = el.querySelector('.vts-pf-list'), pv = el.querySelector('.vts-pv');
    var cache = {}, tab = 'today', per = '1M';

    function drawSwitch() {
      me.setAttribute('aria-label', cur.name + ' — view profile');
      me.innerHTML = av(cur, true) + '<span class="vts-pf-who"><b>' + esc(cur.name) + (cur.nri ? '<i class="vts-buy-nri">NRI</i>' : '') + stepTag(cur) + '<em class="vts-pf-vp">Profile ›</em></b>' +
        (cur.role ? '<span class="vts-pf-role">' + esc(cur.role) + ' · VilfinTV</span>' : '') + '<span>' + plan(cur) + '</span></span>';
      stEl.innerHTML = status(cur);
      list.innerHTML = rows.map(function (r, i) {
        return '<button type="button" role="option" class="vts-pf-o" aria-selected="' + (r === cur) + '" data-i="' + i + '">' + av(r) +
          '<span class="vts-pf-who"><b>' + esc(r.name) + (r.nri ? '<i class="vts-buy-nri">NRI</i>' : '') + stepTag(r) + '</b>' + (r.role ? '<span class="vts-pf-role">' + esc(r.role) + '</span>' : '') + '<span>' + plan(r) + '</span></span>' +
          '<span class="vts-pf-st">' + status(r) + (r.day && r.ret != null && !r.day.first ? '<small class="' + cl(r.day.chg) + '">' + spct(r.day.pct) + ' on ' + esc(dt(r.day.d, false)) + '</small>' : '') + '</span></button>';
      }).join('');
    }
    function openList(on) {
      list.hidden = !on; sw.setAttribute('aria-expanded', on ? 'true' : 'false');
      if (on) { var s = list.querySelector('[aria-selected="true"]'); if (s) { s.focus(); s.scrollIntoView({ block: 'nearest' }); } }
    }
    sw.addEventListener('click', function () { openList(list.hidden); });
    list.addEventListener('click', function (e) {
      var b = e.target.closest('.vts-pf-o'); if (!b) return;
      cur = rows[+b.getAttribute('data-i')]; ovSel = null;
      try { localStorage.setItem(key, cur.name); } catch (er) {}
      openList(false); drawSwitch(); load(); sw.focus();
    });
    list.addEventListener('keydown', function (e) {
      var os = [].slice.call(list.querySelectorAll('.vts-pf-o')), i = os.indexOf(document.activeElement);
      if (e.key === 'Escape') { openList(false); sw.focus(); }
      else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); var n = os[Math.max(0, Math.min(os.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))]; if (n) n.focus(); }
    });
    document.addEventListener('click', function (e) { if (!list.hidden && !el.querySelector('.vts-pf').contains(e.target)) openList(false); });
    me.addEventListener('click', function () { profile(cur, cache[cur.f]); });

    /* Profile of a VilfinTV staff member: role, desk, base, investor profile, the account type and the charges and
       tax rules that apply to it (resident vs NRI), and the account's figures. */
    var TEAM = { core: ['Core team', 'VilfinTV HQ, India'], recruit: ['Joined in 2026', 'VilfinTV HQ, India'],
                 us: ['US AI training programme 2026–27', 'United States (NRI)'] };
    var ad = new Date(sb.start + 'T00:00:00').getDate();
    var WHEN = { 'Monthly': 'on the 3rd of every month', 'Weekly': 'every Monday', 'Quarterly': 'on ' + ad + ' Jan, Apr, Jul and Oct',
                 'Yearly': 'every year on ' + ad + ' Oct', 'One-time': 'once, on ' + dt(sb.start) };
    /* Yearly step-up rules (sim_config / gsim_config stepUps): one agent per page gets a year-end bonus added to the
       first buy of January, another raises the regular buy by a fixed % every January after a salary hike. */
    function stepTag(r) {
      if (!r.step) return '';
      return r.step.k === 'bonus' ? '<i class="vts-buy-nri vts-step" title="Year-end bonus added to the first buy of January">🎁 Bonus</i>'
                                  : '<i class="vts-buy-nri vts-step" title="Regular buy rises by ' + r.step.pct + '% of the original amount every January after a salary hike">📈 +' + r.step.pct + '%/yr</i>';
    }
    function stepAmt(r, yrs) {
      var h = r.step, f = 1 + h.pct / 100 * yrs;   /* + pct % of the original amount each year (not compounding) */
      return Math.round(r.amt * f / h.round) * h.round;
    }
    function stepNote(r) {
      if (!r.step || !r.amt) return null;
      var y0 = new Date(sb.start + 'T00:00:00').getFullYear(), per = r.freq === 'Weekly' ? 'weekly' : 'monthly';
      if (r.step.k === 'bonus') {
        return ['Bonus', 'Receives a year-end bonus of ' + inr(r.step.amount, 0) + ' every 31 December and adds all of it to the first ' + per + ' buy dated in January (first: January ' + (y0 + 1) +
          ' — ' + inr(r.amt, 0) + ' + ' + inr(r.step.amount, 0) + ' = ' + inr(r.amt + r.step.amount, 0) + '). The bonus is split by the model like any buy; the other buys of the year stay at ' + inr(r.amt, 0) + '. No dip reserve'];
      }
      return ['Salary hike', 'Gets a salary hike at the end of every year and raises the ' + per + ' buy by ' + r.step.pct + '% of the original amount (' + inr(Math.round(r.amt * r.step.pct / 100), 0) + ') from the first buy of January, every year (rounded to ' + inr(r.step.round, 0) + '): ' +
        inr(r.amt, 0) + ' in ' + y0 + ' → ' + inr(stepAmt(r, 1), 0) + ' in ' + (y0 + 1) + ' → ' + inr(stepAmt(r, 2), 0) + ' in ' + (y0 + 2) + ' → ' + inr(stepAmt(r, 3), 0) + ' in ' + (y0 + 3) + '. No bonus and no dip reserve'];
    }
    /* The buying strategy each agent follows — exactly the engine's rules (sim_config.json), in plain words. */
    function strategy(r, x, nri) {
      var st = stepNote(r);
      return strategy_(r, x, nri).concat(st ? [st] : []);
    }
    function strategy_(r, x, nri) {
      if (gl) {
        var ga = r.amt ? inr(r.amt, 0) : 'the plan amount', gn = x && x.hold ? x.hold.length : null;
        return [
          ['Model', '10+ year ' + esc(r.risk) + ' model portfolio of the Portfolio Simulator — Global ETF: the same ETFs and weights shown on this page (the latest model published before each buy)'],
          ['When', r.freq === 'One-time' ? 'Once — the full ' + ga + ' on ' + esc(dt(sb.start)) + ', then held for the long term'
            : esc(r.freq) + ' — ' + ga + ' ' + esc(WHEN[r.freq] || '') + '. On a US market holiday, at the next session'],
          ['Split', ga + ' is split across the model\'s ETFs' + (gn ? ' (' + gn + ' now)' : '') + ' by their weights; each share is added to the cash that slot has left over'],
          ['Price', 'A market-on-close order at the official closing price (4:00 pm New York time), fractional shares after commission; shares are credited the next US business day'],
          ['Dividends', nri ? 'Paid in full (US tax resident — taxed through the US return) and added to that slot\'s next buy' : '25% US tax withheld under the India–US treaty (claimable as a foreign tax credit in the Indian return); the rest is added to that slot\'s next buy'],
          ['Model changes', 'Never sells: when the model replaces an ETF, new money goes to the new choice and the earlier shares are kept'],
          ['Discipline', 'Never times the market, never sells because prices fell, never adds or withdraws money outside the plan']
        ];
      }
      var amt = r.amt ? inr(r.amt, 0) : 'the plan amount', once = r.freq === 'One-time';
      var n = x && x.hold ? x.hold.length : null;
      var when = once ? 'Once — the full ' + amt + ' on ' + esc(dt(sb.start)) + ', then the units are held for the long term'
        : esc(r.freq) + ' — ' + amt + ' ' + esc(WHEN[r.freq] || '') + '. If the market is closed that day, on the next trading day';
      var split = mf
        ? amt + ' is split across the model\'s funds' + (n ? ' (' + n + ' now)' : '') + ' by their weights, each as a one-time purchase. A share below a fund\'s minimum is merged into the next fund, and a larger amount can move a slot to its upgrade fund'
        : amt + ' is split across the model\'s ETFs' + (n ? ' (' + n + ' now)' : '') + ' by their weights. Only whole units are bought; cash left over waits for that ETF\'s next buy';
      var price = mf
        ? 'Placed before the 3 pm cut-off at that day\'s official NAV (liquid funds: the previous day\'s NAV). Stamp duty 0.005% is taken first; units are credited two business days later'
        : 'A market-on-close order at the exchange\'s official closing price (3:30 pm IST)' + (nri ? ', with NRI brokerage' : ', zero brokerage') + ' and statutory charges; units are credited the next trading day';
      return [
        ['Model', '10+ year ' + esc(r.risk) + ' model portfolio of the Portfolio Simulator — the same ' + (mf ? 'funds' : 'ETFs') + ' and weights shown on this page, changed only at the monthly review'],
        ['When', when],
        ['Split', split],
        ['Price', price],
        ['Review', 'On the 19th of every month. A holding is switched only when the model has dropped it at two reviews in a row — never in the first 12 months, and only once exit load and short-term tax no longer apply (at most a 6-month wait). A ' + (mf ? 'fund' : 'ETF') + ' that is wound up or delisted is sold at once'],
        ['Tax', nri ? 'TDS is deducted on every sale; no March gain harvesting. Losses can still be booked against gains already taxed that year'
                    : 'Every March, long-term equity gains up to the ₹1.25 lakh yearly exemption are booked and bought back the same day to raise the cost base (tax harvesting)'],
        ['Discipline', r.dip ? 'Never sells because prices fell and never adds or withdraws money outside the plan — the only extra buys are the market-dip lump sums from the reserve'
                             : 'Never times the market, never sells because prices fell, never adds or withdraws money outside the plan']
      ].concat(r.dip ? [['Dips', 'Keeps a ₹20,000 reserve in a ' + (mf ? 'liquid fund' : 'liquid ETF') + ', topped up with the same ₹20,000 on the first trading day of the month after it is used up. When the Nifty 50, Midcap 150, Smallcap 250, gold or silver closes 5% / 10% / 15% below its 3-month high, the next trading day ₹5,000 / ₹10,000 / ₹20,000 of the reserve is ' +
        (mf ? 'redeemed and invested in that segment\'s model fund when the money arrives the next business day' : 'sold and invested in that segment\'s model ETF at the next session\'s close') +
        ' — once per new tier in a fall, only when the fall holds for two closes and all 37 checks pass (strict value checks: P/E and P/B below the 80th percentile, P/E within 1.15× its 10-year median); signals count only from the 19 Oct 2026 start and only while reserve money is left']] : []);
    }
    function profile(r, a) {
      var x = (a && a.detail) || r.detail, nri = !!r.nri, tm = TEAM[r.team] || ['VilfinTV team', nri ? 'Outside India (NRI)' : 'India'];
      var acct = gl ? (nri ? 'US brokerage account (US tax resident, Form W-9), funded in US dollars' : 'International brokerage account for US-listed ETFs (resident Indian, Form W-8BEN), funded in US dollars under the Liberalised Remittance Scheme')
                    : mf ? (nri ? 'Direct-plan mutual fund account with NRI KYC, funded from an NRE bank account (repatriable)' : 'Direct-plan mutual fund account (resident Indian, Indian savings account)')
                    : (nri ? 'NRI demat & trading account with PIS, funded from an NRE bank account; delivery trades only' : 'Demat & trading account (resident Indian); delivery trades');
      var costs = gl ? ['Commission $0.0035 a share per order, at least $0.35 and at most 1% of the trade value', 'Exchange and clearing fees on buys (fractions of a cent) and currency conversion / remittance costs are not modelled']
                     : mf ? ['Stamp duty 0.005% on every purchase; exit load as per each fund when sold']
                     : [nri ? 'Brokerage 0.1% of each trade (min ₹20, max ₹100) — NRI desks charge more than resident accounts' : 'Zero brokerage on delivery trades',
                        'Stamp duty 0.015% on buys; exchange, SEBI and investor-protection charges + 18% GST; STT and depository charge on sales'];
      var tax = gl ? (nri ? ['US tax resident: dividends paid in full and taxed through the US return; no US tax is withheld at source',
                              'No sales in this simulation, so no capital-gains tax is due yet']
                           : ['25% US tax withheld on dividends under the India–US treaty (Form W-8BEN), claimable as a foreign tax credit (Form 67)',
                              'Gains on sale are taxed in India: held over 24 months 12.5%, otherwise at the income slab; no sales in this simulation so far',
                              'Remittances under the Liberalised Remittance Scheme above ₹10 lakh a financial year attract 20% TCS, adjustable against tax — this plan stays well below it',
                              'US-listed ETFs above US$60,000 in total can face US estate tax for non-US persons'])
              : nri ? ['Tax deducted at source (TDS) on every sale: equity held over a year 12.5%, under a year 20%; debt and other funds 30%; plus 4% cess (surcharge not modelled)',
                       'No ₹1.25 lakh yearly exemption at source — any excess is reclaimed through the Indian tax return; tax paid in India can be credited in the country of residence under its tax treaty',
                       'No yearly gain harvesting: TDS is deducted on the sale itself, so the saving would only return months later as a refund',
                       'The simulation assumes the model\'s funds accept US-based investors; in practice several fund houses do not']
                    : ['No TDS: capital-gains tax is paid through the yearly return — equity held over a year 12.5% on gains above ₹1.25 lakh a year, under a year 20%; debt at the income slab',
                       'Yearly tax harvesting in March: long-term equity gains booked within the ₹1.25 lakh exemption and bought back'];
      var row = function (k, v) { return '<div class="vts-pm-r"><span>' + k + '</span><b>' + v + '</b></div>'; };
      var h = '<div class="vts-pm-h">' + av(r, true).replace('vts-pf-av lg', 'vts-pf-av xl') + '<div><h3 id="vtsPmT">' + esc(r.name) + (nri ? ' <i class="vts-buy-nri">NRI</i>' : '') + stepTag(r) + '</h3>' +
        '<p>' + esc(r.role || 'VilfinTV team') + ' · VilfinTV</p></div><button type="button" class="vts-pm-x" aria-label="Close profile">✕</button></div>' +
        '<div class="vts-pm-b"><div class="vts-pm-c"><h4>At VilfinTV</h4>' + row('Role', esc(r.role || '–')) + row('Works on', esc(r.desk || '–')) + row('Team', esc(tm[0])) + row('Based in', esc(tm[1])) +
        '<h4>Investor profile</h4>' + row('Residency', nri ? 'Non-resident Indian (NRI)' : 'Resident Indian') + row('Model portfolio', '10+ years · ' + esc(r.risk)) +
        row('Buys', esc(r.freq) + (r.amt ? ' · ' + inr(r.amt, 0) : '') + ' — ' + esc(WHEN[r.freq] || '')) + row('Started', esc(dt(sb.start))) +
        (r.step ? row(r.step.k === 'bonus' ? 'Year-end bonus' : 'Salary hike', r.step.k === 'bonus' ? inr(r.step.amount, 0) + ' every 31 Dec → added to the first buy of January'
          : '+' + r.step.pct + '% of ' + inr(r.amt, 0) + ' every January (' + (new Date(sb.start + 'T00:00:00').getFullYear() + 1) + ': ' + inr(stepAmt(r, 1), 0) + ')') : '') +
        row('Account', esc(acct)) +
        (x ? row('Invested', inr(x.inv)) + row('Value', x.val != null ? inr(x.val) : 'After units are credited') : '') +
        row('Total return', r.ret != null ? '<span class="' + cl(r.ret) + '">' + spct(r.ret) + '</span>' + (r.metric === 'xirr' ? ' XIRR' : '') : (r.credit ? 'Units credited ' + esc(dt(r.credit)) : '–')) +
        (x && x.dip ? '<h4>Market-dip reserve</h4>' + row('Reserve', inr(x.dip.reserve, 0) + (x.dip.fund ? ' in ' + esc(x.dip.fund) : '') + (x.dip.date ? ' · since ' + esc(dt(x.dip.date)) : '')) +
          (x.dip.refills && x.dip.refills.length ? row('Topped up', x.dip.refills.length + '× · ' + inr(x.dip.paid - x.dip.reserve, 0) + ' added (latest ' + esc(dt(x.dip.refills[x.dip.refills.length - 1].T)) + ')') : '') +
          row('Used for dip buys', inr(x.dip.used, 0)) + row('Left', inr(x.dip.left, 0)) +
          ((x.dip.ev || []).length ? '<ul class="vts-pm-dip">' + x.dip.ev.slice().reverse().map(function (e) {
            return '<li><b>' + esc(dt(e.D)) + ' · ' + esc(e.seg === 'large' ? 'Large cap' : e.seg === 'mid' ? 'Mid cap' : e.seg === 'small' ? 'Small cap' : e.seg === 'gold' ? 'Gold' : 'Silver') + ' −' + Number(e.fall).toFixed(2) + '%</b> ' +
              (e.action === 'buy' ? 'bought ' + inr(e.amt, 0) + (e.name ? ' of ' + esc(e.name) : '') : 'no buy — ' + esc(e.why)) + '</li>';
          }).join('') + '</ul>' : '<p class="vts-pv-e">No dip buys yet — the reserve waits for the first confirmed fall.</p>') +
          (x.dip.empty ? '<p class="vts-pv-e">' + x.dip.empty + ' dip signal' + (x.dip.empty > 1 ? 's' : '') + ' passed without a buy while the reserve was used up (it is topped up with ₹20,000 on the first trading day of the next month).</p>' : '') : '') +
        '<h4>Charges</h4><ul>' + costs.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>' +
        '<h4>Tax rules for this account</h4><ul>' + tax.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>' +
        '</div><div class="vts-pm-c"><h4>How ' + esc(r.name) + ' buys</h4><ol class="vts-pm-steps">' + strategy(r, x, nri).map(function (t) { return '<li><b>' + t[0] + '</b><span>' + t[1] + '</span></li>'; }).join('') + '</ol>' +
        '</div><p class="vts-pv-e vts-pm-foot">Simulated account of a VilfinTV team member for education — not real money and not advice. Every figure comes from the audited ledger.</p></div>';
      var back = document.createElement('div');
      back.className = 'vts-pm-back';
      back.innerHTML = '<div class="vts-pm" role="dialog" aria-modal="true" aria-labelledby="vtsPmT" tabindex="-1">' + h + '</div>';
      document.body.appendChild(back);
      var dlg = back.querySelector('.vts-pm'), prevOv = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      var close = function () { document.removeEventListener('keydown', key_); back.remove(); document.body.style.overflow = prevOv; me.focus(); };
      var key_ = function (e) { if (e.key === 'Escape') close(); else if (e.key === 'Tab') { e.preventDefault(); dlg.querySelector('.vts-pm-x').focus(); } };
      back.addEventListener('click', function (e) { if (e.target === back || e.target.closest('.vts-pm-x')) close(); });
      document.addEventListener('keydown', key_);
      dlg.querySelector('.vts-pm-x').focus();
    }

    function load() {
      var r = cur;
      if (!r.f || sb.auditOk === false) { render(r, r.detail ? { detail: r.detail } : null); return; }
      if (cache[r.f]) { render(r, cache[r.f]); return; }
      pv.innerHTML = '<div class="vts-pv-load">Loading ' + esc(r.name) + '\'s account…</div>';
      fetch('data/' + (sb.dir || 'sim') + '/' + encodeURIComponent(r.f) + '.json', { cache: 'no-cache' }).then(function (x) { return x.ok ? x.json() : null; })
        .then(function (a) { cache[r.f] = a || {}; if (cur === r) render(r, a); })
        .catch(function () { if (cur === r) render(r, null); });
    }

    function render(r, a) {
      var x = a && a.detail, rc = (a && a.recent) || [], last = rc[rc.length - 1];
      /* Never stamp today's date on a previous market-close valuation.
         Validate the ledger against its own last history row and the audited scoreboard. */
      var valDate = x && x.asOf, lastDate = last && last.d;
      var synced = !!(x && valDate && lastDate && sb.updated &&
        /^\\d{4}-\\d{2}-\\d{2}$/.test(valDate) &&
        valDate === lastDate && valDate === sb.updated &&
        a.updated === sb.updated && sb.auditOk !== false && a.auditOk !== false &&
        x.val != null && isFinite(x.val));
      var valueText = synced ? inr(x.val) : '–';
      var valueNote = synced ? 'Valued as of ' + esc(dt(valDate, false)) + ' · latest audited close' :
        'Valuation unavailable — ledger date or audit is not in sync';
      var h = '<div class="vts-pv-top"><div class="vts-pv-v"><span>Current value</span><b>' + valueText + '</b>' +
        '<small>' + valueNote + '</small>' + '</div>' +
        '<div class="vts-pv-k"><div><span>Invested</span><b>' + (x ? inr(x.inv) : '–') + '</b></div>' +
        '<div><span>Total gain</span><b class="' + cl(x && x.gain) + '">' + (x && x.gain != null ? sinr(x.gain) + ' <small>' + spct(r.ret) + '</small>' : '–') + '</b></div>' +
        '<div><span>' + (last ? (last.first ? 'Since purchase' : 'Day change · ' + esc(dt(last.d, false))) : 'Day change') + '</span><b class="' + cl(last && last.chg) + '">' + (last ? sinr(last.chg) + ' <small>' + spct(last.pct) + '</small>' : '–') + '</b></div>' +
        '<div><span>Same money in ' + esc(BN) + '</span>' + (function () { var bv = last && last.inv ? (last.bval / last.inv - 1) * 100 : (x && x.bench); return '<b class="' + cl(bv) + '">' + (bv != null ? spct(bv) : '–') + '</b>'; })() + '</div></div></div>';
      var tabs = [['today', 'Summary'], ['bench', 'vs ' + BN], ['brk', 'Breakdown'], ['hold', 'Holdings'], ['hist', 'History']];
      h += '<div class="vts-tabs vts-pv-tabs" role="tablist">' + tabs.map(function (t) { return '<button type="button" role="tab" data-t="' + t[0] + '" class="' + (tab === t[0] ? 'on' : '') + '" aria-selected="' + (tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>';
      h += '<div class="vts-pv-pane">' + pane(r, a) + '</div>';
      pv.innerHTML = h;
      pv.querySelector('.vts-pv-tabs').addEventListener('click', function (e) {
        var b = e.target.closest('button[data-t]'); if (!b) return;
        tab = b.getAttribute('data-t'); render(r, a);
      });
      var pb = pv.querySelector('.vts-ch-per');
      if (pb) pb.addEventListener('click', function (e) { var b = e.target.closest('button[data-p]'); if (!b) return; per = b.getAttribute('data-p'); render(r, a); });
      chartHover(pv.querySelector('.vts-ch'));
      var ov = pv.querySelector('.vts-olap');
      if (ov) ov.addEventListener('change', function () { ovSel = [+ov.querySelector('[data-o="0"]').value, +ov.querySelector('[data-o="1"]').value]; ov.querySelector('.vts-olap-r').innerHTML = overlapOut(a.breakdown); });
      var dtb = pv.querySelector('.vts-dist-t');
      if (dtb) dtb.addEventListener('click', function (e) { var bt = e.target.closest('button[data-dt]'); if (!bt) return; distTab = bt.getAttribute('data-dt'); render(r, a); });
      pv.querySelectorAll('.vts-pbk').forEach(function (d) { d.addEventListener('toggle', function () { bdOpen[d.getAttribute('data-k')] = d.open; }); });
    }

    function pane(r, a) {
      var rc = (a && a.recent) || [], last = rc[rc.length - 1];
      if (tab === 'today') return today(r, last);
      if (tab === 'bench') return bench(a);
      if (tab === 'hold') return holdings(r, a && a.detail);
      if (tab === 'brk') return breakdown(r, a && a.breakdown);
      return history(rc);
    }

    function today(r, e) {
      if (!e) {
        if (!started) return '<p class="vts-pv-e">Simulated buying starts on ' + esc(dt(sb.start)) + '.</p>';
        return '<p class="vts-pv-e">' + (r.credit ? 'Units are credited on <b>' + esc(dt(r.credit)) + '</b>. The first daily summary appears that evening, once the day\'s official ' + (mf ? 'NAVs' : 'closing prices') + ' are out.' : 'The first daily summary appears once the units are credited.') + '</p>';
      }
      var moved = Math.abs(e.chg) < 0.5 ? 'was flat' : (e.chg > 0 ? 'rose ' : 'fell ') + '<b class="' + cl(e.chg) + '">' + inr(Math.abs(e.chg)) + ' (' + spct(e.pct) + ')</b>';
      var gap = e.pct - e.bpct;
      var h = '<div class="vts-sum"><p class="vts-sum-l">' + (e.first
        ? 'Since purchase, ' + esc(r.name) + '\'s portfolio is ' + (e.chg >= 0 ? 'up' : 'down') + ' <b class="' + cl(e.chg) + '">' + inr(Math.abs(e.chg)) + ' (' + spct(e.pct) + ')</b> as of ' + esc(dtw(e.d)) + '.'
        : esc(r.name) + '\'s portfolio ' + moved + ' on ' + esc(dtw(e.d)) + '.') +
        ' The same money in the ' + esc(BN) + ' ' + (e.first ? 'is ' : 'moved ') + '<b class="' + cl(e.bpct) + '">' + spct(e.bpct) + '</b>' +
        (Math.abs(gap) >= 0.01 ? ' — ' + Math.abs(gap).toFixed(2) + ' pts ' + (gap > 0 ? 'ahead' : 'behind') + '.' : '.') + '</p>';
      var m = e.mkt || [], nifty = m.filter(function (q) { return q[1] === BK; })[0];
      var others = m.filter(function (q) { return q[1] !== BK; }).slice(0, 4);
      if (m.length) {
        h += '<h4>Market moves that day</h4><ul class="vts-sum-m">' + (nifty ? [nifty] : []).concat(others).map(function (q) {
          return '<li><span>' + esc(q[0]) + '</span><b class="' + cl(q[2]) + '">' + spct(q[2]) + '</b></li>'; }).join('') + '</ul>';
      }
      var hs = (e.hold || []).filter(function (q) { return q[3] > 0; });
      var mv = function (q) { return q[6] && q[5] !== q[7] ? (q[4] / q[6] - 1) * 100 : null; };
      var drags = hs.filter(function (q) { return q[10] < 0; }).sort(function (p, q) { return p[10] - q[10]; }).slice(0, 2);
      var lifts = hs.filter(function (q) { return q[10] > 0; }).sort(function (p, q) { return q[10] - p[10]; }).slice(0, 2);
      var li = [];
      var line = function (q) { var p = mv(q); return '<b>' + esc(q[0]) + '</b> ' + (p == null ? 'unchanged price' : (p >= 0 ? 'up ' : 'down ') + Math.abs(p).toFixed(2) + '%') + ' · <span class="' + cl(q[10]) + '">' + sinr(q[10]) + '</span>'; };
      if (e.first) li.push('Gain or loss of each holding since it was bought: ' + hs.slice().sort(function (p, q) { return p[10] - q[10]; }).map(function (q) { return esc(q[0]) + ' <span class="' + cl(q[10]) + '">' + sinr(q[10]) + '</span>'; }).join(' · ') + '.');
      else {
        if (drags.length) li.push('Biggest drag' + (drags.length > 1 ? 's' : '') + ': ' + drags.map(line).join('; ') + '.');
        if (lifts.length) li.push('Biggest lift' + (lifts.length > 1 ? 's' : '') + ': ' + lifts.map(line).join('; ') + '.');
      }
      var x = e.x || {}, mk = {};
      m.forEach(function (q) { mk[q[1]] = q; });
      var links = (x.sec || []).filter(function (s) { return s[2] && mk[s[2]]; }).sort(function (p, q) { return Math.abs(q[1] * mk[q[2]][2]) - Math.abs(p[1] * mk[p[2]][2]); }).slice(0, 2);
      links.forEach(function (s) { var q = mk[s[2]]; li.push('About <b>' + s[1].toFixed(1) + '%</b> of the portfolio was in <b>' + esc(s[0]) + '</b> (look-through); ' + esc(q[0]) + ' ' + (q[2] >= 0 ? 'rose' : 'fell') + ' <span class="' + cl(q[2]) + '">' + spct(q[2]) + '</span> that day.'); });
      if (x.stk && x.stk.length) li.push('Largest look-through stock exposure: ' + x.stk.map(function (s) { return esc(s[0].replace(/ (Ltd\.?|Limited)$/i, '')) + ' ' + s[1].toFixed(1) + '%'; }).join(' · ') + '.');
      if (x.asset && x.asset.length) li.push('Beyond Indian equity: ' + x.asset.map(function (s) { return esc(s[0]) + ' ' + s[1].toFixed(1) + '%'; }).join(' · ') + '.');
      var pend = (e.hold || []).filter(function (q) { return q[9] > 0; });
      if (pend.length) li.push('Still being credited (counted at cost): ' + pend.map(function (q) { return esc(q[0]) + ' ' + inr(q[9]); }).join(' · ') + '.');
      if (li.length) h += '<h4>What this meant for the portfolio</h4><ul class="vts-sum-b">' + li.map(function (t) { return '<li>' + t + '</li>'; }).join('') + '</ul>';
      if (gl) return h + '<p class="vts-pv-e">Calculated from official US closing prices and recorded in the audited ledger. Market moves use the official closes of index-tracking ETFs.</p></div>';
      h += '<p class="vts-pv-e">Calculated from official ' + (mf ? 'NAVs' : 'closing prices') + ' and recorded in the audited ledger journal. Market moves use the official closes of index-tracking ETFs; look-through exposure comes from the funds\' ' + (x.pm ? esc(dt(x.pm + '-01').replace(/^\d+ /, '')) + ' ' : '') + 'monthly portfolios (top holdings only).</p></div>';
      return h;
    }

    function window_(series) {
      if (!series || !series.length) return [];
      var lastD = new Date(series[series.length - 1][0] + 'T00:00:00'), days = { '1W': 7, '1M': 30, '6M': 182, '1Y': 365 }[per];
      var from = days ? new Date(lastD - days * 864e5) : null;
      var s = from ? series.filter(function (q) { return new Date(q[0] + 'T00:00:00') >= from; }) : series;
      var pts = [], cp = 0, cb = 0;
      if (!from) pts.push([sb.start, 0, 0, null]);
      s.forEach(function (q, i) {
        if (i === 0 && from) { pts.push([q[0], 0, 0, q]); return; }
        cp = ((1 + cp / 100) * (1 + q[3] / 100) - 1) * 100; cb = ((1 + cb / 100) * (1 + q[4] / 100) - 1) * 100;
        pts.push([q[0], cp, cb, q]);
      });
      return pts;
    }

    function bench(a) {
      var series = (a && a.series) || [];
      if (series.length < 1) return '<p class="vts-pv-e">The comparison starts with the first daily summary, once units are credited.</p>';
      var pts = window_(series), lastP = pts[pts.length - 1], q = lastP[3] || series[series.length - 1];
      var h = '<div class="vts-ch-per" role="group" aria-label="Period">' + ['1W', '1M', '6M', '1Y', 'ALL'].map(function (p) { return '<button type="button" data-p="' + p + '" class="' + (per === p ? 'on' : '') + '" aria-pressed="' + (per === p) + '">' + p + '</button>'; }).join('') + '</div>';
      h += '<div class="vts-ch-k"><div class="p"><span><i></i>Portfolio · time-weighted</span><b class="' + cl(lastP[1]) + '">' + spct(lastP[1]) + '</b><small>' + inr(q[1]) + '</small></div>' +
        '<div class="b"><span><i></i>' + esc(BN) + ' · time-weighted</span><b class="' + cl(lastP[2]) + '">' + spct(lastP[2]) + '</b><small>' + inr(q[5]) + '</small></div></div>';
      h += chart(pts);
      h += '<p class="vts-pv-e">Time-weighted return over the period: daily changes chained, so new money and its timing do not count — the way fund returns are quoted. The total gain above is measured on the money actually invested, so the two differ for accounts that keep buying. Both lines start from the same cash on the same dates; units count at cost until credited.</p>';
      return h;
    }

    function chart(pts) {
      if (pts.length < 2) return '<p class="vts-pv-e">The chart appears after the second daily summary.</p>';
      var W = 640, H = 220, L = 46, R = 10, T = 12, B = 26;
      var ys = []; pts.forEach(function (p) { ys.push(p[1], p[2]); });
      var lo = Math.min.apply(null, ys.concat([0])), hi = Math.max.apply(null, ys.concat([0]));
      if (hi - lo < 0.2) { hi += 0.1; lo -= 0.1; }
      var pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
      var X = function (i) { return L + (W - L - R) * (pts.length === 1 ? 0 : i / (pts.length - 1)); };
      var Y = function (v) { return T + (H - T - B) * (1 - (v - lo) / (hi - lo)); };
      var path = function (k) { return pts.map(function (p, i) { return (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p[k]).toFixed(1); }).join(''); };
      var g = '', step = (hi - lo) / 3;
      for (var j = 0; j <= 3; j++) { var v = lo + step * j; g += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(v).toFixed(1) + '" y2="' + Y(v).toFixed(1) + '" class="gl"/><text x="' + (L - 6) + '" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end">' + v.toFixed(2) + '%</text>'; }
      var xl = [0, Math.floor((pts.length - 1) / 2), pts.length - 1].filter(function (v, i, s) { return s.indexOf(v) === i; });
      xl.forEach(function (i) { g += '<text x="' + X(i).toFixed(1) + '" y="' + (H - 6) + '" text-anchor="' + (i === 0 ? 'start' : i === pts.length - 1 ? 'end' : 'middle') + '">' + esc(dt(pts[i][0], false)) + '</text>'; });
      return '<div class="vts-ch" data-pts="' + esc(JSON.stringify(pts.map(function (p) { return [p[0], +p[1].toFixed(3), +p[2].toFixed(3), X(pts.indexOf(p))]; }))) + '">' +
        '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Portfolio versus ' + esc(BN) + ', cumulative return over the period">' + g +
        '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(0).toFixed(1) + '" y2="' + Y(0).toFixed(1) + '" class="zl"/>' +
        '<path d="' + path(2) + '" class="lb"/><path d="' + path(1) + '" class="lp"/>' +
        '<line class="cx" x1="0" x2="0" y1="' + T + '" y2="' + (H - B) + '" visibility="hidden"/></svg><div class="vts-ch-tip" hidden></div></div>';
    }

    function chartHover(box) {
      if (!box) return;
      var pts = JSON.parse(box.getAttribute('data-pts')), svg = box.querySelector('svg'), cx = svg.querySelector('.cx'), tip = box.querySelector('.vts-ch-tip');
      var move = function (ev) {
        var r = svg.getBoundingClientRect(), px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * 640 / r.width, k = 0;
        pts.forEach(function (p, i) { if (Math.abs(p[3] - px) < Math.abs(pts[k][3] - px)) k = i; });
        var p = pts[k]; cx.setAttribute('x1', p[3]); cx.setAttribute('x2', p[3]); cx.setAttribute('visibility', 'visible');
        tip.hidden = false;
        tip.innerHTML = '<b>' + esc(dt(p[0])) + '</b><span><i class="p"></i>Portfolio ' + spct(p[1]) + '</span><span><i class="b"></i>' + esc(BN) + ' ' + spct(p[2]) + '</span>';
        var left = p[3] / 640 * r.width; tip.style.left = Math.min(Math.max(left - tip.offsetWidth / 2, 0), r.width - tip.offsetWidth) + 'px';
      };
      var out = function () { cx.setAttribute('visibility', 'hidden'); tip.hidden = true; };
      svg.addEventListener('mousemove', move); svg.addEventListener('touchmove', move, { passive: true }); svg.addEventListener('touchstart', move, { passive: true });
      svg.addEventListener('mouseleave', out); svg.addEventListener('touchend', out);
    }

    /* The holding's own 1Y / 3Y return vs the simple average of its category (published with the account file). */
    function vcCell(v) {
      if (!v || !v.v) return '<span data-l="vs category avg" class="vts-vc"><small>–</small></span>';
      var f = function (q) { return q == null ? '–' : (q > 0 ? '+' : '') + q.toFixed(1) + '%'; };
      var lab = v.v === 'beat' ? '✓ Beats avg' : v.v === 'lag' ? '✕ Below avg' : '≈ Mixed';
      return '<span data-l="vs category avg" class="vts-vc ' + v.v + '" title="Average of ' + v.n + ' in its category"><b>' + lab + '</b>' +
        '<small>1Y ' + f(v.own[0]) + ' vs ' + f(v.avg[0]) + (v.own[1] != null || v.avg[1] != null ? ' · 3Y ' + f(v.own[1]) + ' vs ' + f(v.avg[1]) : '') + '</small></span>';
    }
    function holdings(r, x) {
      if (!x) return '<p class="vts-pv-e">' + (sb.auditOk === false ? 'Figures are withheld while a data check is resolved.' : 'No purchases yet — the first buy is on ' + esc(dt(sb.start)) + '.') + '</p>';
      var h = '<div class="vts-acc-k">' + [['Next buy', x.next ? dt(x.next) : (r.freq === 'One-time' ? 'One-time (done)' : '–')]].concat(mf ? [] : [['Cash left (next buy)', inr(x.cash)]]).map(function (q) { return '<div><span>' + q[0] + '</span><b>' + q[1] + '</b></div>'; }).join('') + '</div>';
      if (x.hold && x.hold.length) {
        h += '<div class="vts-acc-t" role="table" aria-label="Holdings"><div class="vts-acc-r vts-acc-hd" role="row"><span>' + (mf ? 'Fund' : 'ETF') + '</span><span>Units</span><span>Avg cost</span><span>' + (mf ? 'NAV' : 'Close') + '</span><span>Value</span><span>Gain</span><span>Share</span><span>vs category avg</span></div>' +
          x.hold.map(function (o) {
            return '<div class="vts-acc-r" role="row"><span class="vts-acc-n"><b>' + esc(o.n) + '</b><small>' + esc(mf ? (o.cat || '') : o.k + (o.cat ? ' · ' + o.cat : '')) + (o.pu ? ' · <em>' + num(o.pu, UD) + ' units being credited' + (o.cr ? ' by ' + esc(dt(o.cr, false)) : '') + '</em>' : '') + '</small></span>' +
              '<span data-l="Units">' + num(o.u, UD) + '</span><span data-l="Avg cost">' + CUR + num(o.avg, mf ? 4 : 2) + '</span>' +
              '<span data-l="' + (mf ? 'NAV' : 'Close') + '">' + CUR + num(o.px, mf ? 4 : 2) + (o.pd ? '<small>' + dt(o.pd, false) + '</small>' : '') + '</span>' +
              '<span data-l="Value">' + CUR + num(o.val, gl ? 2 : 0) + '</span><span data-l="Gain" class="' + cl(o.g) + '">' + spct(o.g) + '</span><span data-l="Share">' + (o.w == null ? '–' : o.w.toFixed(1) + '%') + '</span>' + vcCell(o.vc) + '</div>';
          }).join('') + '</div>';
      }
      if (x.pend && x.pend.length)
        h += '<div class="vts-acc-p"><b>Waiting for price</b>' + x.pend.map(function (o) { return '<div>' + esc(o.n) + ' · ' + inr(Math.round(o.amt), 0) + ' · ordered ' + dt(o.T, false) + ' — ' + esc(o.st) + '</div>'; }).join('') + '</div>';
      h += '<p class="vts-acc-e">Values as of ' + (x.asOf ? esc(dt(x.asOf)) : '–') + ' at official ' + (mf ? 'NAVs' : 'closing prices') + ' · simulation, not real money.' +
        (x.hold && x.hold.some(function (o) { return o.vc; }) ? ' “vs category avg” compares each ' + (mf ? 'fund' : 'ETF') + '’s own 1-year and 3-year (per year) return with the simple average of its category; the monthly review, not this label, decides any sale.' : '') + '</p>';
      return h;
    }

    var ACOL = { 'Equity': '#3b82f6', 'Debt': '#14b8a6', 'Gold': '#eab308', 'Silver': '#94a3b8', 'International': '#8b5cf6', 'REITs & InvITs': '#f97316', 'Cash & others': '#64748b' };
    var bdOpen = { alloc: true }, ovSel = null, distTab = 'eq';
    function ovPct(A, B) { var wb = {}; B[3].forEach(function (q) { wb[q[0]] = q[1]; }); return A[3].reduce(function (t, q) { return t + (wb[q[0]] != null ? Math.min(q[1], wb[q[0]]) : 0); }, 0); }
    var svg = function (d) { return '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>'; };
    var IC = { alloc: svg('<rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="8" height="6" rx="1.5"/><rect x="13" y="14" width="8" height="6" rx="1.5"/>'),
               dist: svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5V12l6 6"/>'),
               ovl: svg('<circle cx="9" cy="12" r="5.5"/><circle cx="15" cy="12" r="5.5"/>') };
    function bd(k, icon, title, sub, body) {
      return '<details class="vts-pbk" data-k="' + k + '"' + (bdOpen[k] ? ' open' : '') + '><summary><span class="vts-pbk-i" aria-hidden="true">' + icon + '</span><span class="vts-pbk-t"><b>' + title + '</b><small>' + sub + '</small></span><i class="vts-pbk-x" aria-hidden="true">▾</i></summary><div class="vts-pbk-b">' + body + '</div></details>';
    }
    function pfx(v) { return (v > 0 && v < 0.05 ? '<0.05' : v < 1 ? v.toFixed(2) : v.toFixed(1)) + '%'; }
    function bars(list, max, fmtR) {
      return '<div class="vts-bl">' + list.map(function (q) {
        return '<div class="vts-bl-r"><span class="vts-bl-n">' + esc(q[0]) + '</span><span class="vts-bl-t"><i style="width:' + Math.max(1, Math.min(100, q[1] / max * 100)).toFixed(1) + '%' + (q[2] ? ';background:' + q[2] : '') + '"></i></span><b>' + pfx(q[1]) + '</b>' + (fmtR ? '<small>' + fmtR(q[1]) + '</small>' : '') + '</div>';
      }).join('') + '</div>';
    }
    function overlapOut(b) {
      var f = b.funds, A = f[ovSel[0]], B = f[ovSel[1]];
      if (!A || !B || ovSel[0] === ovSel[1]) return '<p class="vts-pv-e">Choose two different funds.</p>';
      var wb = {}; B[3].forEach(function (q) { wb[q[0]] = q[1]; });
      var com = A[3].filter(function (q) { return wb[q[0]] != null; }).map(function (q) { return [q[0], q[1], wb[q[0]]]; }).sort(function (p, q) { return Math.min(q[1], q[2]) - Math.min(p[1], p[2]); });
      var ovp = com.reduce(function (t, q) { return t + Math.min(q[1], q[2]); }, 0);
      return '<div class="vts-olap-s"><b>' + ovp.toFixed(1) + '%</b><span>overlap in their top holdings · ' + com.length + ' common stock' + (com.length === 1 ? '' : 's') + '</span></div>' +
        (com.length ? '<div class="vts-olap-t"><div class="hd"><span>Stock</span><span>' + esc(A[1]).slice(0, 18) + '…</span><span>' + esc(B[1]).slice(0, 18) + '…</span></div>' + com.map(function (q) {
          return '<div><span>' + esc(q[0].replace(/ (Ltd\.?|Limited)$/i, '')) + '</span><span>' + q[1].toFixed(2) + '%</span><span>' + q[2].toFixed(2) + '%</span></div>'; }).join('') + '</div>' : '<p class="vts-pv-e">No common stocks among their top holdings.</p>') +
        '<p class="vts-pv-e">Overlap = sum of the smaller weight of each common stock, from the top 15 holdings of each fund\'s latest monthly portfolio.</p>';
    }
    function breakdown(r, b) {
      if (!b) return '<p class="vts-pv-e">' + (r.credit ? 'The breakdown appears once the units are credited on <b>' + esc(dt(r.credit)) + '</b>.' : 'The breakdown appears once the units are credited.') + '</p>';
      var al = b.alloc || [], tot = al.reduce(function (t, q) { return t + q[1]; }, 0) || 1;
      var h1 = '<div class="vts-al-bar" role="img" aria-label="Asset allocation">' + al.map(function (q) { return '<i style="width:' + (q[1] / tot * 100).toFixed(2) + '%;background:' + (ACOL[q[0]] || '#64748b') + '" title="' + esc(q[0]) + ' ' + q[1].toFixed(1) + '%"></i>'; }).join('') + '</div>' +
        '<div class="vts-al-l">' + al.map(function (q) { return '<div><span><i style="background:' + (ACOL[q[0]] || '#64748b') + '"></i>' + esc(q[0]) + '</span><b>' + pfx(q[1]) + '</b><small>' + inr(b.val * q[1] / 100, 0) + '</small></div>'; }).join('') + '</div>' +
        '<p class="vts-pv-e">Look-through allocation of the credited holdings on ' + esc(dt(b.d)) + ' (value ' + inr(b.val, 0) + '), from each fund\'s ' + (b.pm ? esc(dt(b.pm + '-01').replace(/^\d+ /, '')) + ' ' : '') + 'monthly portfolio' + (b.pfCover < 99.5 ? '; ' + (100 - b.pfCover).toFixed(0) + '% of the value is in funds without a published portfolio, counted by their asset class' : '') + '.</p>';
      if (b.global) return '<div class="vts-pbks">' + bd('alloc', IC.alloc, 'Allocation', 'US equity, international, bonds, gold and cash', h1.replace(/from each fund\'s [^.]*monthly portfolio[^.]*\./, 'by each ETF\'s asset class.')) + '</div>';
      var cap = b.cap || {}, eq = (al.filter(function (q) { return q[0] === 'Equity'; })[0] || [0, 0])[1];
      var capL = [['Large cap', cap.large || 0, '#3b82f6'], ['Mid cap', cap.mid || 0, '#60a5fa'], ['Small cap', cap.small || 0, '#93c5fd']];
      if (eq - (b.eqCapCover || 0) > 0.5) capL.push(['Not classified', eq - (b.eqCapCover || 0), '#64748b']);
      var hEq = '<h4>Sectors <small>(% of portfolio)</small></h4>' + ((b.sec || []).length ? bars(b.sec.map(function (q) { return [q[0], q[1]]; }), b.sec[0][1]) : '<p class="vts-pv-e">No sector data.</p>') +
        '<h4>Market cap <small>(equity, % of portfolio)</small></h4>' + bars(capL.filter(function (q) { return q[1] > 0.05; }), Math.max.apply(null, capL.map(function (q) { return q[1]; }).concat([1]))) +
        '<h4>Top stocks <small>(look-through)</small></h4>' + ((b.stk || []).length ? bars(b.stk.map(function (q) { return [q[0].replace(/ (Ltd\.?|Limited)$/i, ''), q[1]]; }), b.stk[0][1]) : '<p class="vts-pv-e">No stock data.</p>');
      var alv = function (c) { return (al.filter(function (q) { return q[0] === c; })[0] || [0, 0])[1]; };
      var fundsBars = function (list) { return bars(list.map(function (q) { return [q[1], q[2]]; }), Math.max.apply(null, list.map(function (q) { return q[2]; }).concat([0.01]))); };
      var dbt = b.debt || {}, gl = b.glob || {}, dsh = alv('Debt'), gsh = alv('International');
      var CCOL = { 'Sovereign': '#14b8a6', 'AAA & equivalent': '#0ea5e9', 'A1+ (money market)': '#22c55e', 'AA': '#eab308', 'A': '#f97316', 'Below A': '#ef4444', 'Not disclosed': '#64748b' };
      var hDebt = !dsh ? '<p class="vts-pv-e">No debt in this portfolio.</p>' :
        '<div class="vts-dist-k"><b>' + pfx(dsh) + '</b><span>of the portfolio is in debt · ' + inr(b.val * dsh / 100, 0) + '</span></div>' +
        ((dbt.credit || []).length ? '<h4>Credit quality <small>(% of portfolio)</small></h4>' + bars(dbt.credit.map(function (q) { return [q[0], q[1], CCOL[q[0]] || '#64748b']; }), dbt.credit[0][1]) : '') +
        ((dbt.type || []).length ? '<h4>Instrument type <small>(top debt holdings)</small></h4>' + bars(dbt.type, dbt.type[0][1]) : '') +
        ((dbt.issuers || []).length ? '<h4>Top issuers <small>(look-through)</small></h4>' + bars(dbt.issuers.map(function (q) { return [q[0].replace(/ (Ltd\.?|Limited)$/i, ''), q[1]]; }), dbt.issuers[0][1]) : '') +
        ((dbt.funds || []).length ? '<h4>Where the debt comes from</h4>' + fundsBars(dbt.funds) : '') +
        '<p class="vts-pv-e">Credit quality from each fund\'s rating split; instrument type and issuers from the top holdings of each monthly portfolio.</p>';
      var hGlob = !gsh ? '<p class="vts-pv-e">No international holdings in this portfolio.</p>' :
        '<div class="vts-dist-k"><b>' + pfx(gsh) + '</b><span>of the portfolio is invested abroad · ' + inr(b.val * gsh / 100, 0) + '</span></div>' +
        ((gl.top || []).length ? '<h4>Top overseas holdings <small>(look-through)</small></h4>' + bars(gl.top, gl.top[0][1]) : '') +
        ((gl.funds || []).length ? '<h4>Where the global exposure comes from</h4>' + fundsBars(gl.funds) : '') +
        '<p class="vts-pv-e">Overseas shares, ETFs and funds held by each fund, from its monthly portfolio.</p>';
      var dt3 = [['eq', 'Equity', alv('Equity')], ['debt', 'Debt', dsh], ['glob', 'Global', gsh]];
      var h2 = '<div class="vts-dist-t" role="tablist">' + dt3.map(function (t) { return '<button type="button" role="tab" data-dt="' + t[0] + '" class="' + (distTab === t[0] ? 'on' : '') + '" aria-selected="' + (distTab === t[0]) + '">' + t[1] + ' <small>' + (t[2] > 0 && t[2] < 1 ? '<1' : t[2].toFixed(0)) + '%</small></button>'; }).join('') + '</div>' +
        (distTab === 'debt' ? hDebt : distTab === 'glob' ? hGlob : hEq);
      var f = b.funds || [], h3;
      if (f.length < 2) h3 = '<p class="vts-pv-e">Needs at least two equity funds with a published monthly portfolio.</p>';
      else {
        if (!ovSel || ovSel[0] >= f.length || ovSel[1] >= f.length) {   // start with the most overlapping pair
          ovSel = [0, 1];
          for (var i = 0; i < f.length; i++) for (var j = i + 1; j < f.length; j++) if (ovPct(f[i], f[j]) > ovPct(f[ovSel[0]], f[ovSel[1]])) ovSel = [i, j];
        }
        var opt = function (i) { return f.map(function (q, j) { return '<option value="' + j + '"' + (j === ovSel[i] ? ' selected' : '') + '>' + esc(q[1]) + '</option>'; }).join(''); };
        h3 = '<div class="vts-olap"><div class="vts-olap-p"><label>Fund 1<select data-o="0">' + opt(0) + '</select></label><label>Fund 2<select data-o="1">' + opt(1) + '</select></label></div><div class="vts-olap-r">' + overlapOut(b) + '</div></div>';
      }
      return '<div class="vts-pbks">' + bd('alloc', IC.alloc, 'Allocation', 'Equity, debt, gold and others', h1) + bd('dist', IC.dist, 'Distribution', 'Equity, debt and global holdings', h2) +
        bd('ovl', IC.ovl, 'Overlap calculator', 'Common holdings in two funds', h3) + '</div>';
    }

    function history(rc) {
      if (!rc.length) return '<p class="vts-pv-e">Daily summaries start once the units are credited.</p>';
      return '<div class="vts-hist" role="table" aria-label="Recent days"><div class="vts-hist-r hd" role="row"><span>Day</span><span>Value</span><span>Day change</span><span>Portfolio</span><span>' + esc(BN) + '</span></div>' +
        rc.slice().reverse().map(function (e) {
          return '<div class="vts-hist-r" role="row"><span>' + esc(dtw(e.d)) + (e.first ? '<small>since purchase</small>' : '') + '</span><span data-l="Value">' + inr(e.val, gl ? 2 : 0) + '</span>' +
            '<span data-l="Day change" class="' + cl(e.chg) + '">' + sinr(e.chg) + '</span><span data-l="Portfolio" class="' + cl(e.pct) + '">' + spct(e.pct) + '</span><span data-l="' + esc(BN) + '" class="' + cl(e.bpct) + '">' + spct(e.bpct) + '</span></div>';
        }).join('') + '</div><p class="vts-pv-e">The full daily history is kept in the ledger journal; the latest ' + rc.length + ' days are shown here.</p>';
    }

    drawSwitch();
    load();
  }
  CSS += '.vts-earn .vts-earn-sec td{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--text2);background:var(--surface2,rgba(127,127,127,.06));padding-top:9px;padding-bottom:7px}' +
    '.vts-earn-via{display:block;font-size:10.5px;color:var(--text2);font-weight:500}';
  CSS += '.vts-buy-rule{border:1px solid var(--border2,var(--border));border-radius:10px;background:rgba(74,144,226,.06);padding:10px 14px;margin:0 0 12px;font-size:12.5px;line-height:1.55;color:var(--text2,var(--text))}' +
    '.vts-buy-rule>summary{cursor:pointer;font-weight:700;color:var(--text);font-size:13px}.vts-buy-rule[open]>summary{margin-bottom:4px}.vts-buy-rule ul{margin:0;padding-left:18px}.vts-buy-rule li{margin:2px 0}.vts-buy-rule li b{color:var(--text)}';
  CSS += '.vts-buy{border:1px solid var(--border2,var(--border));border-left:4px solid #f5a524;border-radius:var(--radius,12px);background:var(--surface);padding:14px 16px;margin:0 0 16px;min-width:0;overflow:hidden}' +
    '.vts-buy-h{display:flex;flex-direction:column;gap:4px;cursor:pointer;list-style:none;margin:-14px -16px;padding:14px 16px;border-radius:inherit}.vts-buy-h::-webkit-details-marker{display:none}' +
    '.vts-buy-h:hover{background:rgba(245,165,36,.05)}.vts-buy-h:focus-visible{outline:2px solid #f5a524;outline-offset:-2px}' +
    '.vts-buy-t1{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:15px}' +
    '.vts-buy-peek{color:var(--text2);font-size:12.5px;font-weight:600}' +
    '.vts-buy-tg{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:800;color:var(--text);border:1px solid var(--border2,var(--border));border-radius:999px;padding:4px 10px;white-space:nowrap}' +
    '.vts-buy-tg i{font-style:normal;transition:transform .2s}.vts-buy[open] .vts-buy-tg i{transform:rotate(180deg)}.vts-buy-tg .c,.vts-buy[open] .vts-buy-tg .o{display:none}.vts-buy[open] .vts-buy-tg .c{display:inline}' +
    '.vts-buy[open] .vts-buy-h{margin-bottom:0}.vts-buy-b{padding-top:14px}' +
    '.vts-buy-badge{display:inline-block;background:rgba(245,165,36,.16);color:#c77800;border:1px solid rgba(245,165,36,.55);border-radius:999px;padding:2px 10px;font-size:11px;font-weight:800;letter-spacing:.5px;text-transform:uppercase}' +
    '[data-theme="dark"] .vts-buy-badge,.dark .vts-buy-badge{color:#f5b54a}' +
    '[data-theme="app"] .vts-dip-c.ok>i,[data-theme="app"] .vts-buy .up,[data-theme="app"] .vts-pm .up,[data-theme="app"] .vts-earn .up{color:#137333}' +
    '[data-theme="app"] .vts-dip-c.no>i,[data-theme="app"] .vts-buy .dn,[data-theme="app"] .vts-pm .dn,[data-theme="app"] .vts-earn .dn{color:#b91c1c}' +
    '[data-theme="app"] .vts-buy-badge,[data-theme="silver"] .vts-buy-badge,[data-theme="news-reader"] .vts-buy-badge{color:#8a4b00}' +
    '@media (prefers-color-scheme:dark){.vts-buy-badge{color:#f5b54a}}' +
    '.vts-buy-sub{color:var(--text2);font-size:12.5px}' +
    '.vts-buy-warn{margin:10px 0 0;background:rgba(245,165,36,.09);border:1px solid rgba(245,165,36,.35);border-radius:8px;padding:9px 12px;font-size:12px;line-height:1.55;color:var(--text2)}.vts-buy-warn b{color:var(--text)}' +
    '.vts-buy-g{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px;margin-top:12px}' +
    '.vts-buy-c{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid var(--border);border-radius:10px;padding:8px 12px;background:var(--surface2,transparent);min-width:0}' +
    '.vts-buy-who{display:flex;flex-direction:column;min-width:0}.vts-buy-who b{font-size:13px}.vts-buy-who span{color:var(--text2);font-size:11.5px;line-height:1.35}' +
    '.vts-step{white-space:nowrap}' +
    '.vts-st{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:12px 14px;box-shadow:var(--shadow-s,0 2px 10px rgba(0,0,0,.12));min-width:280px;align-self:start}' +
    '.vts-st-r{display:flex;justify-content:space-between;gap:16px;font-size:13px;padding:3px 0}.vts-st-r>span{color:var(--text3)}.vts-st-r>b{font-weight:600;text-align:right}' +
    '.vts-st .ok{color:var(--pos)}.vts-st .warn{color:var(--warn,#b45309)}.vts-st-n{margin:6px 0 0;font-size:11.5px;color:var(--text3);line-height:1.4}' +
    '@media (max-width:760px){.vts-st{min-width:0;width:100%;padding:10px 12px}.vts-st-r{font-size:12.5px}}' +
    '.vts-buy-nri{font-style:normal;font-size:10px;font-weight:800;color:var(--text2);border:1px solid var(--border2,var(--border));border-radius:4px;padding:0 4px;margin-left:6px;vertical-align:1px}' +
    '.vts-buy-c strong{font-variant-numeric:tabular-nums;font-size:13px;text-align:right;white-space:nowrap}.vts-buy-c strong small{display:block;font-size:10px;color:var(--text2);font-weight:600}' +
    '.vts-buy .up{color:#16a34a}.vts-buy .dn{color:#dc2626}.vts-buy .na{color:var(--text2);font-weight:600;font-size:12px}' +
    '.vts-buy-n{margin:8px 0 0;font-size:11px;color:var(--text3,var(--text2))}' +
    '.vts-acc{min-width:0}.vts-acc[open]{grid-column:1/-1}.vts-acc>summary{list-style:none;cursor:pointer}.vts-acc>summary::-webkit-details-marker{display:none}' +
    '.vts-acc>summary:hover{border-color:var(--accent,#4a90e2)}.vts-acc>summary:focus-visible{outline:2px solid var(--accent,#4a90e2);outline-offset:1px}' +
    '.vts-acc-x{font-style:normal;color:var(--text2);font-size:12px;transition:transform .15s;margin-left:-2px}.vts-acc[open] .vts-acc-x{transform:rotate(180deg)}' +
    '.vts-acc[open]>summary{border-bottom-left-radius:0;border-bottom-right-radius:0;border-color:var(--accent,#4a90e2)}' +
    '.vts-acc-b{border:1px solid var(--accent,#4a90e2);border-top:none;border-radius:0 0 10px 10px;padding:10px 12px 8px;background:var(--surface,transparent)}' +
    '.vts-acc-k{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-bottom:10px}.vts-acc-k div{border:1px solid var(--border);border-radius:8px;padding:6px 9px;min-width:0}' +
    '.vts-acc-k span{display:block;font-size:10.5px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em}.vts-acc-k b{font-size:13px;font-variant-numeric:tabular-nums}' +
    '.vts-acc-r{display:grid;grid-template-columns:minmax(0,2.2fr) repeat(6,minmax(0,.95fr)) minmax(0,2.1fr);gap:8px;align-items:center;padding:7px 0;border-top:1px solid var(--border);font-size:12.5px;font-variant-numeric:tabular-nums}' +
    '.vts-acc-r>span:not(.vts-acc-n){text-align:right}.vts-acc-r small{display:block;font-size:10.5px;color:var(--text2);font-weight:500}.vts-acc-r em{font-style:normal;color:#d97706}' +
    '.vts-acc-hd>span:first-child{text-align:left!important}.vts-acc-hd{border-top:none;font-size:10.5px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em;font-weight:700}' +
    '.vts-acc-n{min-width:0}.vts-acc-n b{display:block;font-size:12.5px;line-height:1.3;overflow-wrap:anywhere}' +
    '.vts-acc-p{margin-top:8px;font-size:12px;color:var(--text2);line-height:1.6}.vts-acc-p b{display:block;color:var(--text);font-size:12px}' +
    '.vts-acc-e{margin:8px 0 0;font-size:11px;color:var(--text3,var(--text2))}' +
    '.vts-vc b{display:block;font-size:12px}.vts-vc small{display:block;font-size:10.5px;color:var(--text3);line-height:1.35}.vts-vc.beat b{color:var(--pos,#16a34a)}.vts-vc.lag b{color:var(--neg,#dc2626)}.vts-vc.mixed b{color:var(--warn,#b45309)}' +
    '@media (max-width:700px){.vts-acc-hd{display:none}.vts-vc{grid-column:1/-1}.vts-acc-r{grid-template-columns:repeat(3,minmax(0,1fr));row-gap:6px;padding:9px 0}.vts-acc-n{grid-column:1/-1}' +
    '.vts-acc-r>span:not(.vts-acc-n){text-align:left}.vts-acc-r>span[data-l]::before{content:attr(data-l);display:block;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em}' +
    '.vts-acc-k{grid-template-columns:repeat(2,minmax(0,1fr))}}' +
    '@media (max-width:520px){.vts-buy{padding:12px}.vts-buy-h{margin:-12px;padding:12px}.vts-buy-g{grid-template-columns:1fr}' +
    '.vts-buy-t1>b{order:0}.vts-buy-tg{order:1}.vts-buy-badge{order:2}.vts-buy-peek{order:3;flex-basis:100%}.vts-buy:not([open]) .vts-buy-sub{display:none}}' +
    '';
  CSS += '.vts-pf{position:relative;margin:2px 0 12px}' +
    '.vts-pf-bar{display:flex;align-items:center;gap:12px;border:1px solid var(--border2,var(--border));border-radius:12px;background:var(--surface2,var(--surface));padding:8px 10px}' +
    '.vts-pf-me{display:flex;align-items:center;gap:12px;flex:1;min-width:0;text-align:left;border:0;background:none;color:var(--text);padding:2px;cursor:pointer;font:inherit;border-radius:9px}' +
    '.vts-pf-me:hover .vts-pf-vp{text-decoration:underline}.vts-pf-vp{font-style:normal;font-size:11.5px;font-weight:700;color:var(--accent,#4a90e2);margin-left:8px}' +
    '.vts-pf-role{color:var(--text)!important;font-weight:600;font-size:12px!important}' +
    '.vts-pf-sw{flex:none;font:inherit;font-size:12px;font-weight:800;border:1px solid var(--border2,var(--border));border-radius:999px;padding:6px 12px;color:var(--text);background:var(--surface);cursor:pointer}.vts-pf-sw i{font-style:normal}' +
    '.vts-pf-sw:hover{border-color:var(--accent,#4a90e2)}.vts-pf-me:focus-visible,.vts-pf-sw:focus-visible,.vts-pf-o:focus-visible{outline:2px solid var(--accent,#4a90e2);outline-offset:1px}' +
    '.vts-pm-back{position:fixed;inset:0;z-index:10000;background:rgba(2,8,20,.62);display:flex;align-items:center;justify-content:center;padding:16px}' +
    '.vts-pm{width:min(980px,100%);max-height:calc(100vh - 32px);overflow:auto;background:var(--surface,#0f1b33);color:var(--text);border:1px solid var(--border2,var(--border));border-radius:16px;box-shadow:0 24px 60px rgba(0,0,0,.45);outline:none}' +
    '.vts-pm-h{position:sticky;top:0;display:flex;align-items:center;gap:14px;padding:16px 18px;border-bottom:1px solid var(--border);background:var(--surface,#0f1b33)}' +
    '.vts-pm-h h3{margin:0;font-size:18px}.vts-pm-h p{margin:2px 0 0;color:var(--text2);font-size:13px}.vts-pm-h>div{flex:1;min-width:0}' +
    '.vts-pf-av.xl{width:52px;height:52px;font-size:17px}' +
    '.vts-pm-x{flex:none;width:34px;height:34px;border-radius:50%;border:1px solid var(--border2,var(--border));background:none;color:var(--text);font-size:14px;cursor:pointer}.vts-pm-x:focus-visible{outline:2px solid var(--accent,#4a90e2)}' +
    '.vts-pm-b{padding:4px 18px 18px;font-size:13px;line-height:1.55}.vts-pm-b h4{margin:16px 0 6px;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--text2)}' +
    '.vts-pm-r{display:grid;grid-template-columns:130px 1fr;gap:10px;padding:6px 0;border-top:1px solid var(--border)}.vts-pm-r span{color:var(--text2)}.vts-pm-r b{font-weight:600}' +
    '.vts-pm-b ul{margin:0;padding-left:18px}.vts-pm-b ul li{margin:4px 0;color:var(--text2)}' +
    '.vts-pm-steps{list-style:none;margin:0;padding:0;counter-reset:st;border:1px solid var(--border);border-radius:12px;overflow:hidden}' +
    '.vts-pm-steps li{counter-increment:st;display:grid;grid-template-columns:26px 92px 1fr;gap:10px;align-items:start;padding:9px 12px;margin:0;border-top:1px solid var(--border)}' +
    '.vts-pm-steps li:first-child{border-top:none}.vts-pm-steps li::before{content:counter(st);width:22px;height:22px;border-radius:50%;background:var(--accent,#4a90e2);color:var(--accent-ink,#fff);font-size:11.5px;font-weight:800;display:grid;place-items:center}' +
    '.vts-pm-steps b{font-size:12.5px;padding-top:2px}.vts-pm-steps span{color:var(--text2);font-size:12.5px;line-height:1.55}' +
    '.vts-pm .up{color:#16a34a}.vts-pm .dn{color:#dc2626}' +
    '.vts-pm-dip{margin:6px 0 0;padding-left:18px;font-size:12.5px;line-height:1.5;color:var(--text2)}.vts-pm-dip b{color:var(--text)}' +
    '@media (max-width:560px){.vts-pm-steps li{grid-template-columns:24px 1fr;row-gap:2px}.vts-pm-steps span{grid-column:2}.vts-pf-bar{flex-wrap:wrap;row-gap:8px}.vts-pf-me{flex-basis:100%}.vts-pf-cur{flex:1;flex-direction:row!important;align-items:baseline!important;gap:6px;justify-content:flex-start}' +
    '.vts-pm-back{padding:0;align-items:flex-end}.vts-pm{max-height:88vh;border-radius:16px 16px 0 0}.vts-pm-r{grid-template-columns:1fr;gap:2px}.vts-pf-vp{display:none}}' +
    '.vts-pf-av{flex:none;display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;color:#fff;font-weight:800;font-size:12.5px;letter-spacing:.02em}.vts-pf-av.lg{width:42px;height:42px;font-size:14px}' +
    '.vts-pf-who{display:flex;flex-direction:column;min-width:0;flex:1}.vts-pf-who b{font-size:14px;line-height:1.3}.vts-pf-who>span{color:var(--text2);font-size:12px;line-height:1.35}' +
    '.vts-pf-st{display:flex;flex-direction:column;align-items:flex-end;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.vts-pf-st b{font-size:14px}.vts-pf-st small{font-size:10.5px;color:var(--text2);font-weight:600}' +
    '.vts-pf-chg{flex:none;font-size:12px;font-weight:800;border:1px solid var(--border2,var(--border));border-radius:999px;padding:4px 10px;color:var(--text)}.vts-pf-chg i{font-style:normal}' +
    '.vts-pf-list{position:absolute;z-index:30;left:0;right:0;top:calc(100% + 6px);max-height:min(420px,62vh);overflow:auto;border:1px solid var(--border2,var(--border));border-radius:12px;background:var(--surface);box-shadow:0 12px 32px rgba(0,0,0,.28);padding:6px}' +
    '.vts-pf-o{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:0;border-radius:9px;background:none;color:var(--text);padding:8px 10px;cursor:pointer;font:inherit}' +
    '.vts-pf-o:hover{background:var(--surface2,rgba(127,127,127,.08))}.vts-pf-o[aria-selected="true"]{background:rgba(74,144,226,.12);box-shadow:inset 3px 0 0 var(--accent,#4a90e2)}' +
    '.vts-pv-load{padding:24px 4px;color:var(--text2);font-size:13px}' +
    '.vts-pv-top{display:grid;grid-template-columns:minmax(180px,1fr) 3fr;gap:10px;align-items:stretch;margin-bottom:12px}' +
    '.vts-pv-v{border:1px solid var(--border);border-radius:10px;padding:10px 12px;background:rgba(74,144,226,.06)}.vts-pv-v span{display:block;font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:.04em}' +
    '.vts-pv-v b{display:block;font-size:22px;font-variant-numeric:tabular-nums;margin-top:2px}.vts-pv-v small{display:block;font-size:11.5px;color:var(--text2);margin-top:2px}' +
    '.vts-pv-k{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.vts-pv-k div{border:1px solid var(--border);border-radius:10px;padding:8px 10px;min-width:0}' +
    '.vts-pv-k span{display:block;font-size:10.5px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em}.vts-pv-k b{display:block;font-size:14px;font-variant-numeric:tabular-nums;margin-top:2px}.vts-pv-k b small{font-size:11.5px;font-weight:700}' +
    '.vts-pv-tabs{margin-bottom:12px;display:grid;grid-template-columns:repeat(5,minmax(0,1fr))}.vts-pv-tabs button{height:auto;min-height:36px;font-size:13px;padding:4px 4px;min-width:0;white-space:normal;line-height:1.15;overflow-wrap:anywhere}' +
    '.vts-pv-e{margin:8px 0 0;font-size:11.5px;color:var(--text3,var(--text2));line-height:1.55}' +
    '.vts-sum{font-size:13.5px;line-height:1.6}.vts-sum-l{margin:0 0 10px;font-size:14.5px}.vts-sum h4{margin:12px 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--text2)}' +
    '.vts-sum-m{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:6px}.vts-sum-m li{display:flex;justify-content:space-between;gap:8px;border:1px solid var(--border);border-radius:8px;padding:6px 10px;font-size:12.5px}.vts-sum-m b{font-variant-numeric:tabular-nums}' +
    '.vts-sum-b{margin:0;padding-left:18px}.vts-sum-b li{margin:4px 0}' +
    '.vts-ch-per{display:inline-flex;gap:4px;padding:3px;border:1px solid var(--border);border-radius:10px;margin-bottom:10px}.vts-ch-per button{border:0;background:none;color:var(--text2);font-weight:700;font-size:12.5px;padding:6px 12px;border-radius:7px;cursor:pointer}' +
    '.vts-ch-per button.on{background:var(--accent,#4a90e2);color:var(--accent-ink,#fff)}.vts-ch-per button:focus-visible{outline:2px solid var(--accent,#4a90e2)}' +
    '.vts-ch-k{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}.vts-ch-k div{border:1px solid var(--border);border-radius:10px;padding:8px 12px}.vts-ch-k .p{background:rgba(74,144,226,.08)}.vts-ch-k .b{background:rgba(217,119,6,.08)}' +
    '.vts-ch-k span{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text2);font-weight:700}.vts-ch-k i{width:12px;height:3px;border-radius:2px;display:inline-block}.vts-ch-k .p i,.vts-ch-tip .p{background:#3b82f6}.vts-ch-k .b i,.vts-ch-tip .b{background:#d97706}' +
    '.vts-ch-k b{display:block;font-size:17px;font-variant-numeric:tabular-nums}.vts-ch-k small{font-size:11.5px;color:var(--text2)}' +
    '.vts-ch{position:relative}.vts-ch svg{display:block;width:100%;height:auto;touch-action:pan-y}.vts-ch text{font-size:10.5px;fill:var(--text2)}.vts-ch .gl{stroke:var(--border);stroke-width:1}.vts-ch .zl{stroke:var(--text3,var(--text2));stroke-width:1;stroke-dasharray:3 3;opacity:.6}' +
    '.vts-ch .lp{fill:none;stroke:#3b82f6;stroke-width:2;stroke-linejoin:round}.vts-ch .lb{fill:none;stroke:#d97706;stroke-width:2;stroke-linejoin:round}.vts-ch .cx{stroke:var(--text2);stroke-width:1}' +
    '.vts-ch-tip{position:absolute;top:0;pointer-events:none;background:var(--surface);border:1px solid var(--border2,var(--border));border-radius:8px;padding:6px 9px;font-size:11.5px;box-shadow:0 6px 18px rgba(0,0,0,.2);white-space:nowrap}' +
    '.vts-ch-tip b{display:block;margin-bottom:2px}.vts-ch-tip span{display:flex;align-items:center;gap:6px;font-variant-numeric:tabular-nums}.vts-ch-tip i{width:10px;height:3px;border-radius:2px;display:inline-block}' +
    '.vts-hist-r{display:grid;grid-template-columns:1.4fr repeat(4,minmax(0,1fr));gap:8px;padding:7px 0;border-top:1px solid var(--border);font-size:12.5px;font-variant-numeric:tabular-nums}.vts-hist-r>span:not(:first-child){text-align:right}' +
    '.vts-hist-r small{display:block;font-size:10.5px;color:var(--text2)}.vts-hist-r.hd{border-top:none;font-size:10.5px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em;font-weight:700}' +
    '.vts-pbks{border:1px solid var(--border);border-radius:12px;overflow:hidden}.vts-pbk+.vts-pbk{border-top:1px solid var(--border)}' +
    '.vts-pbk>summary{display:flex;align-items:center;gap:12px;padding:12px 14px;cursor:pointer;list-style:none}.vts-pbk>summary::-webkit-details-marker{display:none}.vts-pbk>summary:hover{background:var(--surface2,rgba(127,127,127,.06))}' +
    '.vts-pbk>summary:focus-visible{outline:2px solid var(--accent,#4a90e2);outline-offset:-2px}.vts-pbk-i{flex:none;width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--border);border-radius:9px;font-size:17px;color:var(--text2)}' +
    '.vts-pbk-t{flex:1;display:flex;flex-direction:column;min-width:0}.vts-pbk-t b{font-size:14px}.vts-pbk-t small{font-size:12px;color:var(--text2)}.vts-pbk-x{font-style:normal;color:var(--text2);transition:transform .15s}.vts-pbk[open] .vts-pbk-x{transform:rotate(180deg)}' +
    '.vts-pbk-b{padding:4px 14px 14px}.vts-pbk-b h4{margin:12px 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--text2)}.vts-pbk-b h4 small{text-transform:none;letter-spacing:0;font-weight:500}' +
    '.vts-dist-t{display:inline-flex;gap:4px;padding:3px;border:1px solid var(--border);border-radius:10px;margin:4px 0 8px}.vts-dist-t button{border:0;background:none;color:var(--text2);font-weight:700;font-size:12.5px;padding:6px 14px;border-radius:7px;cursor:pointer}' +
    '.vts-dist-t button small{font-weight:600;opacity:.8}.vts-dist-t button.on{background:var(--accent,#4a90e2);color:var(--accent-ink,#fff)}.vts-dist-t button:focus-visible{outline:2px solid var(--accent,#4a90e2)}' +
    '.vts-dist-k{display:flex;align-items:baseline;gap:10px;margin:4px 0 2px}.vts-dist-k b{font-size:20px;font-variant-numeric:tabular-nums}.vts-dist-k span{font-size:12.5px;color:var(--text2)}' +
    '.vts-al-bar{display:flex;height:14px;border-radius:7px;overflow:hidden;gap:2px;margin:6px 0 10px}.vts-al-bar i{display:block;min-width:2px}' +
    '.vts-al-l{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px}.vts-al-l div{display:flex;align-items:baseline;gap:8px;border:1px solid var(--border);border-radius:8px;padding:6px 10px;font-size:12.5px}' +
    '.vts-al-l span{flex:1;display:flex;align-items:center;gap:7px;min-width:0}.vts-al-l span i{width:10px;height:10px;border-radius:3px;flex:none}.vts-al-l b{font-variant-numeric:tabular-nums}.vts-al-l small{color:var(--text2);font-variant-numeric:tabular-nums}' +
    '.vts-bl{display:flex;flex-direction:column;gap:5px}.vts-bl-r{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(60px,2fr) 52px;gap:10px;align-items:center;font-size:12.5px}' +
    '.vts-bl-n{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.vts-bl-t{height:8px;border-radius:4px;background:var(--surface2,rgba(127,127,127,.12));overflow:hidden}.vts-bl-t i{display:block;height:100%;border-radius:4px;background:#3b82f6}' +
    '.vts-bl-r b{text-align:right;font-variant-numeric:tabular-nums}' +
    '.vts-olap-p{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:6px 0 10px}.vts-olap-p label{display:flex;flex-direction:column;gap:4px;font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:.04em;font-weight:700;min-width:0}' +
    '.vts-olap-p select{font:inherit;font-size:13px;text-transform:none;letter-spacing:0;font-weight:600;color:var(--text);background:var(--surface2,var(--surface));border:1px solid var(--border2,var(--border));border-radius:8px;padding:8px;min-width:0;width:100%}' +
    '.vts-olap-s{display:flex;align-items:baseline;gap:10px;margin-bottom:8px}.vts-olap-s b{font-size:22px;font-variant-numeric:tabular-nums}.vts-olap-s span{font-size:12.5px;color:var(--text2)}' +
    '.vts-olap-t>div{display:grid;grid-template-columns:minmax(0,2fr) 1fr 1fr;gap:8px;padding:6px 0;border-top:1px solid var(--border);font-size:12.5px;font-variant-numeric:tabular-nums}.vts-olap-t>div>span:not(:first-child){text-align:right}' +
    '.vts-olap-t .hd{border-top:none;font-size:10.5px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em;font-weight:700}' +
    '@media (max-width:760px){.vts-bl-r{grid-template-columns:minmax(0,1.9fr) minmax(36px,1fr) 46px;gap:8px}.vts-pv-tabs{grid-template-columns:repeat(3,minmax(0,1fr))}.vts-olap-p{grid-template-columns:1fr}.vts-pv-top{grid-template-columns:1fr}.vts-pv-k{grid-template-columns:repeat(2,minmax(0,1fr))}.vts-pf-me .vts-pf-av.lg{width:36px;height:36px}' +
    '.vts-hist-r.hd{display:none}.vts-hist-r{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:4px}.vts-hist-r>span:first-child{grid-column:1/-1;font-weight:700}.vts-hist-r>span:not(:first-child){text-align:left}' +
    '.vts-hist-r>span[data-l]::before{content:attr(data-l);display:block;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em}.vts-ch-k b{font-size:15px}}';
  /* ── Market-dip lump sums (data: smartsip.json / etf_smart.json → dip). When a segment's index tracker closes 3% or
     more below its 3-month high, the model adds a one-time amount (₹5,000 · ₹10,000 at 5% · ₹20,000 at 10%), once per
     new tier in a fall, only when all 37 checks pass. Shown for the selected plan, just above Simulator Buy. ── */
  function dipPanel(o) {
    var b = o && o.blk;
    if (!b || !b.segments) return '';
    style();
    var R = b.rule || {}, segs = b.segments, plan = (b.plans || {})[o.pid] || {}, etf = o.kind === 'etf', what = etf ? 'ETF' : 'fund';
    var tiers = (R.tiers || []).slice().sort(function (x, y) { return x[0] - y[0]; }), first = tiers.length ? tiers[0][0] : 5;
    var start = R.start || '2026-10-19', NM = (R.n || {}).mkt || 14, NA = (R.n || {}).all || 37;
    var inr = function (v) { return '₹' + Number(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 }); };
    var dt = function (x, y) { return x ? new Date(String(x).slice(0, 10) + 'T00:00:00').toLocaleDateString('en-GB', y ? { day: 'numeric', month: 'short', year: 'numeric' } : { day: 'numeric', month: 'short' }) : ''; };
    var last = Object.keys(segs).reduce(function (m, k) { return segs[k].d > m ? segs[k].d : m; }, '');
    var order = ['large', 'mid', 'small', 'gold', 'silver'];
    var buys = [];
    var rows = order.filter(function (k) { return segs[k]; }).map(function (k) {
      var s = segs[k], e = plan[k], c = e ? (b.cands || [])[e.c] : null, alt = !c && b.alts ? b.alts[k] : null;
      var mc = alt ? alt : c;
      var fall = s.fall || 0, w = Math.max(0, Math.min(100, fall / 18 * 100));
      var lvl = function (t) { return tiers.filter(function (x) { return x[0] === t; })[0]; };
      var next = tiers.filter(function (t) { return t[0] > Math.max(s.ep || 0, s.tier || 0); })[0];
      var today = s.d === last;
      var all = mc ? (s.checks || []).concat(mc.checks || []) : null;
      var ok = all ? all.filter(function (x) { return x[1]; }).length : null;
      var firstFail = all ? (all.filter(function (x) { return !x[1]; })[0] || [])[0] : null;
      var dip = s.signal && today;                                     // a new, held, confirmed level on the latest close
      var tone = dip && c && e && e.ok ? 'go' : dip && c ? 'no' : 'q';
      // plain-language status
      var st;
      if (fall < first) st = 'No dip — ' + fall.toFixed(1) + '% below its 3-month high. The model acts only from ' + first + '%; keep your regular plan.';
      else if (dip && !(c && e && e.ok)) st = 'Dip on ' + dt(s.d) + ': ' + fall.toFixed(1) + '% down for two closes (' + s.tier + '% level), but not bought' + (c ? ' — a check failed (see the red tag).' : ' — not part of this model portfolio.');
      else if (dip) st = 'Dip confirmed on ' + dt(s.d) + ': ' + fall.toFixed(1) + '% down and held for two closes → ' + s.tier + '% level, model amount ' + inr(s.amount) + '.';
      else if (s.raw > (s.ep || 0) && s.tier < s.raw) st = 'Down ' + fall.toFixed(1) + '% today — waits for a second close at ' + s.raw + '%+ to rule out a one-day dip.';
      else if (s.tier > (s.ep || 0) && !s.conf) st = 'Down ' + fall.toFixed(1) + '% — not yet confirmed by the second ' + (etf ? 'ETF' : 'tracker') + ' on the same index; waits.';
      else if (s.tier > (s.ep || 0) && !s.sane) st = 'Down ' + fall.toFixed(1) + '% — a crash-day or unusual close; the model waits a session.';
      else if (s.ep) st = (s.epBeforeStart ? 'Down ' + fall.toFixed(1) + '% — this fall began before the ' + dt(start, true) + ' start, so its ' + s.ep + '% level is not bought.'
                                          : 'Down ' + fall.toFixed(1) + '% — the ' + s.ep + '% level was already bought on ' + dt(s.epDate) + '.') +
                         (next ? ' Next model amount only if it reaches ' + next[0] + '% (' + inr(next[1]) + ').' : ' No deeper level is left in this fall.');
      else st = 'Down ' + fall.toFixed(1) + '% — no new level today.';
      if (tone === 'go') buys.push({ seg: s.label, amt: s.amount, name: etf ? c.sym : c.name });
      var tag = !c ? '<span class="vts-dip-tag q">' + (alt ? /model holds/.test((alt.checks[NM] || [])[2] || '') ? 'Info only · model holds ' + (k === 'silver' ? 'gold' : 'silver') + ' now' : 'Info only · not in this plan' : 'Not in this plan') + '</span>'
        : tone === 'go' ? '<span class="vts-dip-tag go">✓ Can buy today · ' + inr(s.amount) + ' (optional)</span>'
        : tone === 'no' ? '<span class="vts-dip-tag no">✕ Not today — ' + esc(firstFail || 'a check failed') + '</span>'
        : '<span class="vts-dip-tag q">No dip buy today</span>';
      var grp = function (t, from, xs) {
        return '<div class="vts-dip-g"><h5>' + t + '</h5>' + xs.map(function (x, i) {
          return '<div class="vts-dip-c ' + (x[1] ? 'ok' : 'no') + '"><i>' + (x[1] ? '✓' : '✕') + '</i><span><b>' + (from + i) + '. ' + esc(x[0]) + '</b>' + esc(x[2]) + '</span></div>';
        }).join('') + '</div>';
      };
      var det = grp('Market trigger', 1, s.checks || []) +
        (mc ? grp('Market & valuation', 9, mc.checks.slice(0, NM)) + grp(etf ? 'ETF checks' : 'Fund checks', 9 + NM, mc.checks.slice(NM)) +
             (alt ? '<p class="vts-dip-na">' + esc(s.label) + ' is not part of this model portfolio, so no dip amount applies. ' + (/model holds/.test((alt.checks[NM] || [])[2] || '') ? 'The top-ranked ' + what : 'The model\'s ' + what + ' for this segment (from the other plans)') + ' is shown for information, with every check.</p>' : '')
           : grp('Market & valuation', 9, s.mkt || []) + '<p class="vts-dip-na">' + esc(s.label) + ' is not part of this model portfolio, so the ' + what + ' checks (' + (9 + NM) + '–' + NA + ') do not apply and no dip amount is shown.</p>');
      var n = mc ? all.length : (s.checks || []).length + (s.mkt || []).length;
      var nOk = mc ? ok : (s.checks || []).concat(s.mkt || []).filter(function (x) { return x[1]; }).length;
      return '<details class="vts-dip-r ' + tone + '"><summary>' +
        '<span class="vts-dip-s"><b>' + esc(s.label) + '</b><small>' + esc(s.index) + '</small></span>' +
        '<span class="vts-dip-f"><b>' + (fall > 0.005 ? '−' + fall.toFixed(2) + '%' : '0.00%') + '</b><span class="vts-dip-m" aria-hidden="true">' +
          tiers.map(function (t) { return '<i style="left:' + (t[0] / 18 * 100) + '%"></i>'; }).join('') + '<em style="width:' + w + '%"></em></span><small>below the 3-month high · ' + esc(dt(s.d)) + '</small></span>' +
        '<span class="vts-dip-st">' + esc(st) + '</span>' +
        '<span class="vts-dip-fd">' + (mc ? '<b>' + esc(etf ? mc.sym + ' · ' + (mc.name || '') : mc.name || '') + '</b>' : '') + tag + '</span>' +
        '<span class="vts-dip-k ' + (c && e && e.ok ? 'ok' : '') + '">' + nOk + '/' + n + '<small>checks</small></span><span class="vts-dip-ch" aria-hidden="true">›</span></summary>' +
        '<div class="vts-dip-d">' + det + '</div></details>';
    }).join('');
    var rv = b.reserve || {}, who = (R.persons || []).join(', ').replace(/, ([^,]*)$/, ' and $1');
    var banner = buys.length
      ? '<div class="vts-dip-ban go"><b>Optional dip lump sum today</b><span>' + buys.map(function (x) { return esc(x.seg) + ': ' + inr(x.amt) + ' in ' + esc(x.name); }).join(' · ') +
        '. This is an extra, one-time amount on top of your regular plan above — every one of the ' + NA + ' checks passed on the ' + esc(dt(last)) + ' close.</span></div>'
      : '<div class="vts-dip-ban q"><b>No dip lump sum today — continue your regular plan above</b><span>The model adds an optional one-time amount only when an index has stayed ' + first + '%+ below its 3-month high for two closes and all ' + NA + ' checks pass. A one-day dip that recovers the next session is never bought. Latest close: ' + esc(dt(last, true)) + '.</span></div>';
    return '<section class="vts-dip" aria-labelledby="vtsDipT">' +
      '<div class="vts-dip-h"><div><h3 id="vtsDipT">📉 Market-dip lump sums</h3><span class="vts-dip-b">Optional · model rule</span></div>' +
      '<p>When an index falls <b>' + tiers.map(function (t) { return t[0] + '%'; }).join(' / ') + '</b> below its highest close of the last 3 months — and stays there for <b>two closes</b> — the model adds a one-time ' +
      tiers.map(function (t) { return '<b>' + inr(t[1]) + '</b>'; }).join(' / ') + ' to that segment\'s ' + what + ', once per new level in a fall. Signals count only from ' + esc(dt(start, true)) + ' onwards.</p></div>' +
      banner +
      '<div class="vts-dip-lg" aria-hidden="true"><span><i class="go"></i>Can buy today (optional)</span><span><i class="no"></i>Dip today, but a check failed</span><span><i class="q"></i>No dip buy today</span></div>' +
      '<div class="vts-dip-l"><div class="vts-dip-hd" aria-hidden="true"><span>Segment</span><span>Fall</span><span>What the model does</span><span>Model ' + what + '</span><span>Checks</span><span></span></div>' + rows + '</div>' +
      '<p class="vts-dip-n">Checks: 1–8 market trigger (fall, two-close hold, confirmation by a second ' + (etf ? 'ETF' : 'tracker') + ', crash-day and data guards), 9–' + (8 + NM) + ' market & valuation (P/E, P/B, earnings, bond yields, economy, volatility, 5-session, 10-close, 200-day and 52-week trend), ' + (9 + NM) + '–' + NA + ' the ' + what + ' itself (cost, size, returns, risk, tracking, NAV). Tap a segment for every check and its figure. ' +
      (who ? 'In Simulator Buy, ' + esc(who) + ' follow this rule with a ' + inr(R.reserve) + ' reserve in ' + (etf ? 'a liquid ETF (' + esc(rv.sym || 'liquid ETF') + ')' : 'a liquid fund (' + esc(rv.name || 'liquid fund') + ')') +
        ', topped up with the same ' + inr(R.reserve) + ' on the first trading day of the month after it is used up. ' : '') +
      'Educational model — not investment advice.</p></section>';
  }
  CSS += '.vts-na{color:var(--text2);font-size:11px;font-weight:600;white-space:nowrap}';
  CSS += '.vts-eco{border:1px solid var(--border);border-radius:var(--radius,14px);background:var(--surface);margin:0 0 12px;overflow:hidden}' +
    '.vts-eco>summary{display:flex;align-items:center;gap:12px;padding:14px 16px;cursor:pointer;list-style:none}.vts-eco>summary::-webkit-details-marker{display:none}' +
    '.vts-eco>summary:hover{background:rgba(74,144,226,.05)}.vts-eco>summary:focus-visible{outline:2px solid var(--accent,#4a90e2);outline-offset:-2px}' +
    '.vts-eco-t{flex:1;min-width:0}.vts-eco-t b{display:block;font-size:15px;color:var(--text)}.vts-eco-t small{display:block;color:var(--text2);font-size:12.5px;margin-top:2px}' +
    '.vts-eco-b{flex:none;display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:800;color:var(--text);border:1px solid var(--border2,var(--border));border-radius:999px;padding:5px 12px;white-space:nowrap}' +
    '.vts-eco-b i{font-style:normal;transition:transform .2s}.vts-eco[open] .vts-eco-b i{transform:rotate(180deg)}.vts-eco-b .c,.vts-eco[open] .vts-eco-b .o{display:none}.vts-eco[open] .vts-eco-b .c{display:inline}' +
    '.vts-eco-in{padding:0 16px 16px;min-width:0}.vts-eco-in>.vts-box,.vts-eco-in>.vts-pane>.vts-box{border:none;padding:0;background:none}.vts-eco-in>.vts-box>h3:first-child,.vts-eco-in>.vts-pane>.vts-box>h3:first-child{display:none}' +
    '.vts-eco-in>.vts-pane{display:block;margin:0}' +
    '.vts-efq{border-top:1px solid var(--border)}.vts-efq:first-child{border-top:none}.vts-efq>summary{cursor:pointer;padding:12px 26px 12px 0;font-weight:700;font-size:14px;color:var(--text);position:relative;list-style:none}' +
    '.vts-efq>summary::-webkit-details-marker{display:none}.vts-efq>summary::after{content:"+";position:absolute;right:4px;top:10px;font-size:18px;color:var(--text2)}.vts-efq[open]>summary::after{content:"−"}' +
    '.vts-efq p{margin:0 0 12px;color:var(--text2);font-size:13px;line-height:1.6}.vts-efq p b{color:var(--text)}' +
    '@media (max-width:560px){.vts-eco>summary{padding:12px;align-items:flex-start}.vts-eco-in{padding:0 12px 12px}.vts-eco-t b{font-size:14px}}';
  CSS += '.vts-pm-b{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:4px 28px;padding:6px 24px 22px;align-items:start}' +
    '.vts-pm-c{min-width:0}.vts-pm-foot{grid-column:1/-1}.vts-pm-h{padding-left:24px!important;padding-right:24px!important}' +
    '@media (max-width:860px){.vts-pm-b{grid-template-columns:1fr;padding:4px 18px 18px}.vts-pm-h{padding-left:18px!important;padding-right:18px!important}}';
  CSS += '.vts-dip{border:1px solid var(--border2,var(--border));border-left:4px solid #4a90e2;border-radius:var(--radius,12px);background:var(--surface);padding:14px 16px;margin:0 0 16px;min-width:0}' +
    '.vts-dip-h>div{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px}.vts-dip-h h3{margin:0;font-size:15px}' +
    '.vts-dip-b{display:inline-block;background:rgba(74,144,226,.13);color:var(--accent2,#2f6fbf);border:1px solid rgba(74,144,226,.45);border-radius:999px;padding:2px 10px;font-size:11px;font-weight:800;letter-spacing:.5px;text-transform:uppercase}' +
    '.vts-dip-h p{margin:6px 0 10px;color:var(--text2);font-size:12.5px;line-height:1.55}.vts-dip-h p b{color:var(--text)}' +
    '.vts-dip-l{border:1px solid var(--border);border-radius:10px;overflow:hidden}' +
    '.vts-dip-hd,.vts-dip-r>summary{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.05fr) minmax(0,2fr) minmax(0,1.6fr) 64px 16px;gap:12px;align-items:center;padding:10px 12px}' +
    '.vts-dip-hd{font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--text2);background:var(--surface2,rgba(127,127,127,.06))}' +
    '.vts-dip-r{border-top:1px solid var(--border)}.vts-dip-r>summary{cursor:pointer;list-style:none;font-size:13px}.vts-dip-r>summary::-webkit-details-marker{display:none}' +
    '.vts-dip-r>summary:hover{background:rgba(74,144,226,.05)}.vts-dip-r>summary:focus-visible{outline:2px solid #4a90e2;outline-offset:-2px}' +
    '.vts-dip-r small{display:block;color:var(--text2);font-size:11px;font-weight:500;margin-top:1px}' +
    '.vts-dip-s b,.vts-dip-f b{font-size:13.5px}.vts-dip-f b{color:var(--text)}' +
    '.vts-dip-m{position:relative;display:block;height:6px;border-radius:3px;background:var(--surface2,rgba(127,127,127,.14));margin:5px 0 2px;overflow:hidden}' +
    '.vts-dip-m em{position:absolute;left:0;top:0;bottom:0;background:#4a90e2;border-radius:3px}.vts-dip-m i{position:absolute;top:0;bottom:0;width:2px;background:var(--surface);z-index:1}' +
    '.vts-dip-st{font-weight:700;font-size:12.5px;line-height:1.4}.vts-dip-r.go .vts-dip-st{color:#16a34a}.vts-dip-r.used .vts-dip-st{color:var(--text)}.vts-dip-r.q .vts-dip-st,.vts-dip-r.wait .vts-dip-st{color:var(--text2)}' +
    '.vts-dip-fd{font-weight:600;font-size:12.5px;line-height:1.35;min-width:0;overflow-wrap:anywhere}.vts-dip-na{color:var(--text2);font-weight:500}' +
    '.vts-dip-k{text-align:center;font-weight:800;font-size:13px;border:1px solid rgba(245,165,36,.5);border-radius:8px;padding:3px 0;color:var(--text)}.vts-dip-k.ok{border-color:rgba(22,163,74,.55);color:#16a34a}.vts-dip-k small{font-size:9.5px;text-transform:uppercase;letter-spacing:.04em;margin:0}' +
    '.vts-dip-ch{color:var(--text2);transition:transform .2s;font-size:16px}.vts-dip-r[open] .vts-dip-ch{transform:rotate(90deg)}' +
    '.vts-dip-d{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;padding:4px 12px 14px}' +
    '.vts-dip-g h5{margin:6px 0 6px;font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--text2)}' +
    '.vts-dip-c{display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-top:1px solid var(--border);font-size:12px;line-height:1.45;color:var(--text2)}.vts-dip-c:first-of-type{border-top:none}' +
    '.vts-dip-c b{display:block;color:var(--text);font-weight:700}.vts-dip-c i{font-style:normal;flex:none;width:18px;height:18px;border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:800;margin-top:1px}' +
    '.vts-dip-c.ok i{background:rgba(22,163,74,.14);color:#16a34a}.vts-dip-c.no i{background:rgba(220,38,38,.12);color:#dc2626}' +
    '.vts-dip-d>.vts-dip-na{grid-column:1/-1;margin:8px 0 0;font-size:12.5px}' +
    '.vts-dip-n{margin:10px 0 0;color:var(--text2);font-size:12px;line-height:1.55}.vts-dip-n b{color:var(--text)}' +
    '@media (max-width:900px){.vts-dip-d{grid-template-columns:1fr}}' +
    '@media (max-width:760px){.vts-dip{padding:12px}.vts-dip-hd{display:none}.vts-dip-r>summary{grid-template-columns:minmax(0,1fr) minmax(0,1fr) 56px 14px;row-gap:6px;gap:8px 10px}' +
    '.vts-dip-s{grid-column:1}.vts-dip-f{grid-column:2}.vts-dip-k{grid-column:3;grid-row:1}.vts-dip-ch{grid-column:4;grid-row:1}.vts-dip-st{grid-column:1/-1;grid-row:2}.vts-dip-fd{grid-column:1/-1;grid-row:3}}';
  CSS += '.vts-dip-ban{display:flex;flex-direction:column;gap:3px;border-radius:10px;padding:10px 14px;margin:0 0 10px;font-size:12.5px;line-height:1.5;border:1px solid var(--border)}' +
    '.vts-dip-ban b{font-size:13.5px;color:var(--text)}.vts-dip-ban span{color:var(--text2)}' +
    '.vts-dip-ban.go{background:rgba(22,163,74,.10);border-color:rgba(22,163,74,.45)}.vts-dip-ban.q{background:rgba(127,127,127,.07)}' +
    '.vts-dip-lg{display:flex;flex-wrap:wrap;gap:6px 16px;margin:0 0 8px;font-size:11.5px;color:var(--text2)}.vts-dip-lg span{display:inline-flex;align-items:center;gap:6px}' +
    '.vts-dip-lg i{width:10px;height:10px;border-radius:3px;display:inline-block}.vts-dip-lg i.go,.vts-dip-tag.go{background:#16a34a}.vts-dip-lg i.no{background:#dc2626}.vts-dip-lg i.q{background:#94a3b8}' +
    '.vts-dip-tag{display:inline-block;margin-top:4px;border-radius:6px;padding:3px 8px;font-size:11px;font-weight:800;line-height:1.35}' +
    '.vts-dip-tag.go{color:#fff}.vts-dip-tag.no{background:rgba(220,38,38,.12);color:#dc2626;border:1px solid rgba(220,38,38,.45)}.vts-dip-tag.q{background:rgba(127,127,127,.12);color:var(--text2);border:1px solid var(--border)}' +
    '.vts-dip-r.go{background:rgba(22,163,74,.06);box-shadow:inset 3px 0 0 #16a34a}.vts-dip-r.no{background:rgba(220,38,38,.05);box-shadow:inset 3px 0 0 #dc2626}' +
    '.vts-dip-fd b{display:block}.vts-dip-st{font-weight:600!important;color:var(--text)!important}';
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', simBuy); else simBuy();

  /* ── Collapsible sections: any element with data-col="key" gets a header bar (its own .sec-title / .mi-head moved
     into it, a one-line summary from data-col-hint) and a Minimise / Expand pill. Closed by default unless
     data-col-open="1"; each viewer's choice is remembered on this device. Sections re-rendered by script (innerHTML)
     get their header back automatically; children marked by data-col-keep (a selector, e.g. the disclaimer) stay
     visible when minimised. ── */
  var colMem = {};
  function colStored(key) { try { return localStorage.getItem('vt_col_' + key); } catch (e) { return null; } }
  function colSave(key, open) { colMem[key] = open; try { localStorage.setItem('vt_col_' + key, open ? '1' : '0'); } catch (e) {} }
  function colSet(el, open) {
    el.classList.toggle('is-closed', !open);
    var b = el.querySelector(':scope > .vts-col-h .vts-col-b');
    if (b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function col(el) {
    if (!el || !el.getAttribute) return;
    style();
    var key = el.getAttribute('data-col');
    var first = el.firstElementChild;
    if (first && first.classList.contains('vts-col-h')) return;          // already has its header
    el.classList.add('vts-col');
    if (!el.classList.contains('card') && !el.classList.contains('vts-col-card')) el.classList.add('vts-col-bare');
    var t = el.querySelector(':scope > .sec-title, :scope > .mi-head');
    if (!t && el.getAttribute('data-col-title')) { t = document.createElement('div'); t.className = 'sec-title'; t.textContent = el.getAttribute('data-col-title'); }
    var h = document.createElement('div');
    h.className = 'vts-col-h';
    var tw = document.createElement('div');
    tw.className = 'vts-col-t';
    if (t) tw.appendChild(t);
    var hint = el.getAttribute('data-col-hint');
    if (hint) { var p = document.createElement('p'); p.className = 'vts-col-s'; p.textContent = hint; tw.appendChild(p); }
    h.appendChild(tw);
    var id = 'vtcb-' + key;
    h.insertAdjacentHTML('beforeend', '<button type="button" class="vts-col-b" id="' + id + '" aria-expanded="true"><span class="o">Expand</span><span class="c">Minimise</span><i aria-hidden="true">▾</i></button>');
    el.insertBefore(h, el.firstChild);
    var keep = el.getAttribute('data-col-keep');
    if (keep) el.querySelectorAll(':scope > ' + keep).forEach(function (k) { k.classList.add('vts-col-keep'); });
    var open = key in colMem ? colMem[key] : (colStored(key) != null ? colStored(key) === '1' : el.getAttribute('data-col-open') === '1');
    colMem[key] = open;
    colSet(el, open);
    if (!el._colObs && window.MutationObserver) {          // innerHTML re-renders drop the header: put it back
      el._colObs = new MutationObserver(function () { col(el); });
      el._colObs.observe(el, { childList: true });
    }
  }
  function colOpen(el) {
    var c = el && el.closest ? el.closest('.vts-col') : null;
    while (c) { colSave(c.getAttribute('data-col'), true); colSet(c, true); c = c.parentElement && c.parentElement.closest('.vts-col'); }
  }
  function colInit() { document.querySelectorAll('[data-col]').forEach(col); colHash(); }
  function colHash() { if (location.hash && location.hash.length > 1) { try { colOpen(document.querySelector(location.hash)); } catch (e) {} } }
  document.addEventListener('click', function (e) {
    var h = e.target.closest && e.target.closest('.vts-col-h');
    if (!h || (e.target.closest('a') && !e.target.closest('.vts-col-b'))) return;
    var el = h.parentElement, open = el.classList.contains('is-closed');
    colSave(el.getAttribute('data-col'), open);
    colSet(el, open);
    if (open) { var top = h.getBoundingClientRect().top; if (top < 0) h.scrollIntoView({ block: 'start' }); }
  });
  CSS += '.vts-col-h{display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;margin:-4px -6px 0;padding:4px 6px;border-radius:10px;transition:background .15s}' +
    '.vts-col-h:hover{background:rgba(127,127,127,.06)}' +
    '.vts-col-t{min-width:0;flex:1}.vts-col-t .sec-title{margin:0;line-height:1.2;align-items:flex-start}.vts-col-t .sec-title::before{flex-shrink:0;margin-top:.1em}.vts-col-t .mi-head{margin:0;padding:0;border:0}.vts-col-t .mi-head .sec-sub{margin:3px 0 0 14px;font-size:12.5px;color:var(--text3,var(--text2))}' +
    '.vts-col-s{margin:3px 0 0 14px;color:var(--text3,var(--text2));font-size:12.5px;line-height:1.45}' +
    '.vts-col-b{flex-shrink:0;display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border2,var(--border));background:var(--surface2,transparent);color:var(--text);font:inherit;font-size:12px;font-weight:700;border-radius:999px;padding:6px 12px;cursor:pointer;white-space:nowrap;transition:border-color .15s,background .15s}' +
    '.vts-col-b:hover{border-color:var(--accent,#3d8bff)}.vts-col-b:focus-visible{outline:2px solid var(--accent,#3d8bff);outline-offset:2px}' +
    '.vts-col-b i{font-style:normal;font-size:11px;transform:rotate(180deg);transition:transform .2s}.vts-col.is-closed .vts-col-b i{transform:none}' +
    '.vts-col-b .o,.vts-col.is-closed .vts-col-b .c{display:none}.vts-col.is-closed .vts-col-b .o{display:inline}' +
    '.vts-col:not(.is-closed)>.vts-col-h{margin-bottom:12px}' +
    '.vts-col.is-closed>:not(.vts-col-h):not(.vts-col-keep){display:none!important}' +
    '.vts-col:not(.is-closed)>:not(.vts-col-h){animation:vtsColIn .22s ease-out}' +
    '@keyframes vtsColIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}' +
    '.vts-col-bare{margin-top:14px}.vts-col-bare>.vts-col-h{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius,14px);padding:16px 18px;margin:0}' +
    '.vts-col-bare:not(.is-closed)>.vts-col-h{margin-bottom:14px}.vts-col-bare>.vts-col-h:hover{border-color:var(--border2,var(--border))}' +
    '@media (prefers-reduced-motion:reduce){.vts-col:not(.is-closed)>:not(.vts-col-h){animation:none}}' +
    '@media (max-width:520px){.vts-col-h{align-items:flex-start}.vts-col-b{padding:6px 10px}.vts-col-s,.vts-col-t .mi-head .sec-sub{margin-left:14px}}';
  window.addEventListener('hashchange', colHash);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', colInit); else colInit();

  /* Tabs: keep the reader at the start of the new tab. After a switch, when the reader had scrolled past the tab bar
     (or, for a sticky bar, past the start of its content), the content start is brought just under the header /
     sticky bar; otherwise the view is left where it is. Shorter content never makes the page jump down. */
  var tabUser = 0;
  ['wheel', 'touchstart', 'keydown'].forEach(function (ev) { window.addEventListener(ev, function () { tabUser++; }, { passive: true }); });
  function tabSettleNow(bar, content) {
    var h = document.querySelector('.vt-header'), hdr = h ? h.offsetHeight : 0;
    var cs = getComputedStyle(bar), sticky = cs.position === 'sticky' && content;
    var off = sticky ? (parseFloat(cs.top) || hdr) + bar.offsetHeight + 8 : hdr + 8;
    var top = (sticky ? content : bar).getBoundingClientRect().top;
    if (top < off - 1) window.scrollTo({ top: Math.max(0, top + window.pageYOffset - off), behavior: 'instant' });
  }
  function tabSettle(bar, content) {
    if (!bar) return;
    var mark = tabUser;
    tabSettleNow(bar, content);
    setTimeout(function () { if (tabUser === mark) tabSettleNow(bar, content); }, 400);   // late content (charts, files) may shift it
  }

  /* ── Fund-house strip (same look as the India MF page's "Fund houses" card): monogram icon, name, ETF count and
     size, largest first; the first 12 with "Show all", the chosen one always visible, tap = filter, tap again or
     "Clear ✕" = clear. o = {title, sub, items:[{k, name, n, size}], cur, noun, onPick(k|'')}. ── */
  function houseMono(n) {
    n = String(n || '').replace(/\b(mutual fund|asset management|investment management|investments?|amc|ltd|limited|etfs?|funds?|trust)\b/ig, '').trim();
    var w = n.split(/[\s\-.]+/).filter(Boolean);
    if (!w.length) return '?';
    if (/^\d/.test(w[0])) return w[0].slice(0, 3);
    if (w[0].length <= 4 && w[0] === w[0].toUpperCase() && /[A-Z]/.test(w[0])) return w[0];
    if (w.length >= 2) return (w[0][0] + w[1][0]).toUpperCase();
    return w[0].slice(0, 2);
  }
  function houseHue(n) { var h = 0; String(n).split('').forEach(function (c) { h = (h * 31 + c.charCodeAt(0)) % 3600; }); return Math.round(h / 10); }
  function houseAv(n) { var m = houseMono(n); return '<span class="vts-hav' + (m.length > 2 ? ' l3' : '') + '" style="--h:' + houseHue(n) + '" aria-hidden="true">' + esc(m) + '</span>'; }
  function houseStrip(el, o) {
    if (!el) return;
    style();
    var all = el.getAttribute('data-all') === '1', SHOW = 12, items = o.items.slice(), cur = o.cur || '';
    var shown = all ? items : items.slice(0, SHOW);
    if (cur && !shown.some(function (x) { return x.k === cur; })) shown = shown.concat(items.filter(function (x) { return x.k === cur; }));
    el.innerHTML = '<div class="vts-hs-h"><div><div class="vts-hs-t">' + esc(o.title || 'Fund houses') + '</div><div class="vts-hs-s">' + esc(o.sub || '') + '</div></div>' +
      (cur ? '<button type="button" class="vts-hs-clr" data-hs="">Clear ✕</button>' : '') + '</div>' +
      '<div class="vts-hs-g" role="list">' + shown.map(function (x) {
        var on = x.k === cur;
        return '<button type="button" role="listitem" class="vts-hs-i' + (on ? ' on' : '') + '" data-hs="' + esc(x.k) + '" aria-pressed="' + on + '">' + houseAv(x.name) +
          '<span class="vts-hs-n"><b>' + esc(x.name) + '</b><small>' + x.n + ' ' + esc(o.noun || 'ETF') + (x.n === 1 ? '' : 's') + (x.size ? ' · ' + esc(x.size) : '') + '</small></span>' +
          '<i aria-hidden="true">' + (on ? '✓' : '›') + '</i></button>';
      }).join('') + '</div>' +
      (items.length > SHOW ? '<button type="button" class="vts-hs-more" data-hsmore aria-expanded="' + all + '">' + (all ? 'Show fewer' : 'Show all ' + items.length + ' ' + (o.plural || 'fund houses')) + '</button>' : '');
    if (!el._hsBound) {
      el._hsBound = true;
      el.addEventListener('click', function (e) {
        if (e.target.closest('[data-hsmore]')) { el.setAttribute('data-all', el.getAttribute('data-all') === '1' ? '0' : '1'); houseStrip(el, el._hsOpts); return; }
        var b = e.target.closest('[data-hs]'); if (!b) return;
        var k = b.getAttribute('data-hs'); el._hsOpts.onPick(k && k === el._hsOpts.cur ? '' : k);
      });
    }
    el._hsOpts = o;
  }
  CSS += '.vts-hs{margin:0 0 14px;padding:16px 18px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius,14px);box-shadow:var(--shadow-s,none)}' +
    '.vts-hs-h{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.vts-hs-t{font-size:15px;font-weight:700;color:var(--text)}.vts-hs-s{font-size:12.5px;color:var(--text2);margin-top:2px}' +
    '.vts-hs-clr{border:1px solid var(--border2,var(--border));background:var(--surface2,transparent);color:var(--text);font:inherit;font-size:12px;font-weight:700;border-radius:999px;padding:6px 12px;cursor:pointer;white-space:nowrap}' +
    '.vts-hs-g{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px;margin-top:12px}' +
    '.vts-hs-i{display:flex;align-items:center;gap:12px;min-width:0;padding:9px 12px;border:1px solid var(--border);border-radius:12px;background:var(--surface);color:var(--text);font:inherit;text-align:left;cursor:pointer;transition:background .15s,border-color .15s}' +
    '.vts-hs-i:hover{background:var(--surface2,transparent);border-color:var(--border2,var(--border))}.vts-hs-i:focus-visible{outline:2px solid var(--accent);outline-offset:1px}' +
    '.vts-hs-i.on{border-color:var(--accent);background:var(--accent-soft,rgba(59,130,246,.12))}' +
    '.vts-hs-i>i{font-style:normal;color:var(--text3,var(--text2));font-size:16px;flex:none}.vts-hs-i.on>i{color:var(--accent);font-weight:800}' +
    '.vts-hs-n{display:flex;flex-direction:column;min-width:0;flex:1}.vts-hs-n b{font-size:13.5px;font-weight:700;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.vts-hs-n small{font-size:11.5px;color:var(--text2);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.vts-hav{--h:210;flex:0 0 auto;width:38px;height:38px;border-radius:30%;display:inline-grid;place-items:center;font-weight:800;letter-spacing:-.3px;font-size:13px;color:#fff;' +
    'background:linear-gradient(140deg,hsl(var(--h) 62% 52%),hsl(calc(var(--h) + 28) 58% 38%));box-shadow:inset 0 0 0 1px rgba(255,255,255,.14),0 2px 6px rgba(0,0,0,.18);text-transform:uppercase;line-height:1}' +
    '.vts-hav.l3{font-size:10.5px}' +
    '.vts-hs-more{display:block;margin:10px auto 0;border:1px solid var(--border2,var(--border));background:var(--surface2,transparent);color:var(--text);font:inherit;font-size:12.5px;font-weight:700;border-radius:999px;padding:7px 16px;cursor:pointer}.vts-hs-more:hover{border-color:var(--accent)}' +
    '@media (max-width:760px){.vts-hs{padding:14px}.vts-hs-g{grid-template-columns:1fr 1fr;gap:6px}.vts-hs-i{padding:8px 9px;gap:9px}.vts-hav{width:32px;height:32px;font-size:11.5px}.vts-hs-n b{font-size:12.5px}.vts-hs-n small{font-size:11px}.vts-hs-i>i{display:none}}';
  /* ── "Liquid glass" tab bars on phones (all three screener pages): the bottom navigation floats as a frosted pill
        and every in-page tab row becomes a frosted segmented control with a soft glowing active pill. Pure CSS,
        theme-aware through each page's own tokens (--surface / --accent work on every page). ── */
  (function liquid() {
    if (document.getElementById('vts-liquid')) return;
    var st = document.createElement('style');
    st.id = 'vts-liquid';
    st.textContent =
      '@media (max-width:760px){' +
      '.views.bnav,.ebnav,body>#views.views,#views.views{left:10px!important;right:10px!important;bottom:calc(10px + env(safe-area-inset-bottom,0px))!important;width:auto!important;' +
        'border-radius:24px!important;border:1px solid color-mix(in srgb,#fff 22%,transparent)!important;' +
        'background:color-mix(in srgb,var(--surface) 90%,transparent)!important;-webkit-backdrop-filter:blur(26px) saturate(180%);backdrop-filter:blur(26px) saturate(180%);' +
        'box-shadow:0 14px 34px rgba(2,6,23,.30),inset 0 1px 0 color-mix(in srgb,#fff 30%,transparent)!important;padding:6px!important}' +
      '.views.bnav .vbtn,.ebnav a,#views.views button{border-radius:18px!important;transition:background .25s,box-shadow .25s,color .2s,transform .15s}' +
      '.views.bnav .vbtn:active,.ebnav a:active,#views.views button:active{transform:scale(.96)}' +
      '.views.bnav .vbtn.on,.ebnav a.on,#views.views button[aria-selected="true"]{color:var(--accent)!important;' +
        'background:linear-gradient(180deg,color-mix(in srgb,var(--accent) 24%,transparent),color-mix(in srgb,var(--accent) 9%,transparent))!important;' +
        'box-shadow:inset 0 1px 0 color-mix(in srgb,#fff 45%,transparent),0 6px 16px color-mix(in srgb,var(--accent) 26%,transparent)!important}' +
      '.views.bnav .vbtn.on::before{display:none}' +
      '.views.bnav .vbtn,.ebnav a,#views.views button{min-width:0;padding-left:2px!important;padding-right:2px!important;overflow:hidden}' +
      'body::after{content:"";display:block;height:16px}' +
      '.vts-tabs,.tabs[role=tablist],.dxtabs{border-radius:18px!important;border:1px solid color-mix(in srgb,var(--accent) 14%,var(--border,var(--line)))!important;' +
        'background:color-mix(in srgb,var(--surface) 60%,transparent)!important;-webkit-backdrop-filter:blur(16px) saturate(170%);backdrop-filter:blur(16px) saturate(170%);' +
        'box-shadow:inset 0 1px 0 color-mix(in srgb,#fff 25%,transparent),0 4px 16px rgba(2,6,23,.10)}' +
      '.vts-tabs button,.tabs[role=tablist] .tab,.dxtabs button{border-radius:14px!important;transition:background .25s,box-shadow .25s,color .2s}' +
      '.vts-pv-tabs button{font-size:12px!important;letter-spacing:-.1px}' +
      '.vts-tabs button.on,.tabs[role=tablist] .tab[aria-selected="true"],.dxtabs button[aria-selected="true"]{color:var(--accent)!important;' +
        'background:linear-gradient(180deg,color-mix(in srgb,var(--surface) 92%,#fff),color-mix(in srgb,var(--accent) 12%,var(--surface)))!important;' +
        'box-shadow:inset 0 1px 0 color-mix(in srgb,#fff 60%,transparent),0 4px 14px color-mix(in srgb,var(--accent) 22%,transparent)!important}' +
      '}' +
      '@media (max-width:370px){.views.bnav .vbtn .lbl::after{font-size:10px!important;letter-spacing:-.2px}.ebnav a,#views.views button{font-size:10.5px!important}}';
    (document.head || document.documentElement).appendChild(st);
  })();

  /* ── Data status card (same as the Global ETF page): data date, last update and next update in the reader's own
        time zone, coverage and the accuracy audit. o = { asOf, updated (ISO), covered: [label, value],
        audit: { passed, errors, title }, times: [[hh, mm] IST …], note } — the next update is the next listed IST
        time on an Indian trading day (weekends and data/nse_holidays.json skipped). ── */
  var HOL = null;
  function holidays() { return HOL || (HOL = fetch('data/nse_holidays.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; })); }
  function nextIST(times, hol, now) {
    now = now || new Date();
    for (var k = 0; k < 14; k++) {
      var ist = new Date(now.getTime() + 330 * 60000 + k * 864e5), y = ist.getUTCFullYear(), m = ist.getUTCMonth(), d = ist.getUTCDate(), wd = ist.getUTCDay();
      var key = y + '-' + String(m + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      if (wd === 0 || wd === 6 || (hol && hol[key])) continue;
      for (var i = 0; i < times.length; i++) {
        var t = Date.UTC(y, m, d, times[i][0], times[i][1]) - 330 * 60000;
        if (t > now.getTime()) return new Date(t);
      }
    }
    return null;
  }
  function statusCard(el, o) {
    if (!el) return;
    style();
    var f = function (dt) { try { return dt.toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }); } catch (e) { return dt.toISOString(); } };
    var draw = function (hol) {
      var n = o.times ? nextIST(o.times, hol) : null, a = o.audit;
      var rows = [['Data as of', esc(o.asOf || '–')], ['Updated (your time)', o.updated ? esc(f(new Date(o.updated))) : '–'],
                  ['Next update', n ? 'about ' + esc(f(n)) : '–'], [esc(o.covered[0]), esc(o.covered[1])],
                  ['Accuracy audit', a ? (a.errors ? '<span class="warn">' + esc(String(a.errors)) + ' issue' + (a.errors > 1 ? 's' : '') + ' under review</span>' : '<span class="ok">' + Number(a.passed).toLocaleString('en-IN') + ' checks passed</span>') : '–']];
      el.innerHTML = rows.map(function (r, i) { return '<div class="vts-st-r"' + (i === 4 && a && a.title ? ' title="' + esc(a.title) + '"' : i === 2 && o.note ? ' title="' + esc(o.note) + '"' : '') + '><span>' + r[0] + '</span><b>' + r[1] + '</b></div>'; }).join('') +
        (o.note ? '<p class="vts-st-n">' + esc(o.note) + '</p>' : '');
      el.hidden = false;
    };
    draw(null);
    holidays().then(draw);
  }

  window.VTSim = { tabSettle: tabSettle, gate: gate, accepted: accepted, faqCols: faqCols, riskPanel: riskPanel, ecoPanel: ecoPanel, risk10: risk10, css: style, simBuy: simBuy, dipPanel: dipPanel, col: col, colOpen: colOpen, houseStrip: houseStrip, houseAv: houseAv, statusCard: statusCard, nextIST: nextIST };
})();
