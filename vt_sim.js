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
  var lastEco = null;          // ecoPanel returns a string; the earnings box re-renders itself from this on tab / sort clicks
  function ecoPanel(g, comps) {
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
    var gd = g.gdp || [];
    h += '<div class="vts-pane">';
    if (gd.length) {
      h += '<div class="vts-box"><h3>India GDP by fiscal year</h3><p class="vts-sub">April–March fiscal years.' + (g.src === 'wb' ? ' Published figures (forecasts are added when available).' : ' <b>F</b> = forecast.') + ' Nominal growth is approximated as real growth plus consumer-price inflation.</p><div class="vts-tw"><table class="vts-t" style="min-width:0"><thead><tr><th>Year</th><th class="n">Real GDP</th><th class="n">Inflation</th><th class="n">Nominal</th><th class="n">GDP size</th><th class="n">World</th></tr></thead><tbody>' +
        gd.map(function (x) {
          var nom = x.real != null && x.infl != null ? ((1 + x.real / 100) * (1 + x.infl / 100) - 1) * 100 : null, fc = x.f ? ' class="n fc"' : ' class="n"';
          return '<tr><td>' + esc(x.fy) + (x.y === g.fy ? ' <small style="color:var(--accent2);font-weight:700">now</small>' : '') + '</td><td' + fc + '>' + num(x.real) + '%</td><td' + fc + '>' + num(x.infl) + '%</td><td' + fc + '>' + num(nom) + '%</td><td' + fc + '>' + (x.usd ? '$' + num(x.usd / 1000, 2) + ' tn' : '–') + '</td><td' + fc + '>' + num(x.world) + '%</td></tr>';
        }).join('') + '</tbody></table></div></div>';
    }
    h += '</div>' + earnBox(g);
    h += '<p class="vts-note">GDP and inflation figures are ' + (g.src === 'wb' ? 'the latest published official international figures for India' : 'the latest official international forecasts for India, updated a few times a year') + '; earnings are updated every trading day. Economic data is often revised. For education only.</p>';
    return '<div class="vts-pane">' + h + '</div>';
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
    var e = g.earnings || {}, names = g.names || {}, broad = g.broad || ['n50', 'nn50', 'mid150', 'sml250', 'micro250', 'n500'];
    var keys = Object.keys(e).filter(function (k) { return earnState.view === 'broad' ? broad.indexOf(k) >= 0 : broad.indexOf(k) < 0; });
    if (earnState.view === 'broad') keys.sort(function (a, b) { return broad.indexOf(a) - broad.indexOf(b); });
    else keys.sort(function (a, b) {
      var x = e[a][earnState.sort], y = e[b][earnState.sort];
      if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      return (x - y) * earnState.dir;
    });
    var f = function (k, v) {
      if (v == null) return '–';
      if (k === 'pe' || k === 'pb' || k === 'peg') return num(v, k === 'pe' ? 1 : 2);
      var t = num(v, 1) + '%';
      return /^g/.test(k) ? '<span class="' + (v >= 0 ? 'up' : 'dn') + '">' + (v > 0 ? '+' : '') + t + '</span>' : t;
    };
    var nm = function (k) { return esc(String(names[k] || k).replace(/^Nifty /, earnState.view === 'broad' ? 'Nifty ' : '')); };
    return keys.map(function (k) {
      return '<tr><td>' + nm(k) + '</td>' + EARN_COLS.map(function (c) { return '<td class="n">' + f(c[0], e[k][c[0]]) + '</td>'; }).join('') + '</tr>';
    }).join('') || '<tr><td colspan="10" class="vts-note">Figures appear after the next data update.</td></tr>';
  }
  function earnBox(g) {
    var e = g.earnings || {}, broad = g.broad || ['n50', 'nn50', 'mid150', 'sml250', 'micro250', 'n500'], nSec = Object.keys(e).filter(function (k) { return broad.indexOf(k) < 0; }).length;
    var head = EARN_COLS.map(function (c) {
      var on = earnState.view !== 'broad' && earnState.sort === c[0];
      return '<th class="n" title="' + esc(c[2]) + '">' + (earnState.view === 'broad' ? c[1] : '<button type="button" class="vts-es' + (on ? ' on' : '') + '" data-es="' + c[0] + '" aria-label="Sort by ' + esc(c[1]) + '">' + c[1] + (on ? (earnState.dir < 0 ? ' ▾' : ' ▴') : '') + '</button>') + '</th>';
    }).join('');
    return '<div class="vts-box vts-earnbox"><h3>Company earnings &amp; valuation — every Nifty index</h3>' +
      '<p class="vts-sub">Earnings per index unit = index level ÷ P/E, compared with the same month in earlier years (3- and 5-year growth is per year). ROE = P/B ÷ P/E. Tap a column name in Sectors &amp; themes to sort.</p>' +
      '<div class="vts-seg" role="tablist" aria-label="Index group"><button type="button" role="tab" data-ev="broad" aria-selected="' + (earnState.view === 'broad') + '" class="' + (earnState.view === 'broad' ? 'on' : '') + '">Broad market</button>' +
      (nSec ? '<button type="button" role="tab" data-ev="sector" aria-selected="' + (earnState.view !== 'broad') + '" class="' + (earnState.view !== 'broad' ? 'on' : '') + '">Sectors &amp; themes (' + nSec + ')</button>' : '') + '</div>' +
      '<div class="vts-tw vts-earnw"><table class="vts-t vts-earn"><thead><tr><th>Index</th>' + head + '</tr></thead><tbody>' + earnRows(g) + '</tbody></table></div>' +
      '<p class="vts-note">Earnings outlook (model): over long periods company earnings tend to grow roughly in line with nominal GDP' + (g.nominalNext != null ? ', so the model uses next year\'s nominal GDP forecast of <b>' + num(g.nominalNext) + '%</b> as the expected earnings growth' : '') +
      '. Young indices have shorter histories, so some 3- and 5-year figures are blank. Very large growth figures usually come from a low base — companies moving from losses or thin profits to solid profits — and rarely repeat. This is a simple model, not a forecast of actual company results.</p></div>';
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
    var els = document.querySelectorAll('[data-vts-buy]');
    if (!els.length || !window.fetch) return;
    fetch('data/sim_scoreboard.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (sb) {
      if (!sb) return;
      style();
      els.forEach(function (el) { simBuyCard(el, sb); });
    }).catch(function () {});
  }

  function simBuyCard(el, sb) {
    var prod = el.getAttribute('data-vts-buy'), mf = prod !== 'etf', what = mf ? 'mutual fund' : 'ETF';
    var rows = (sb.rows || []).filter(function (r) { return r.product === prod; });
    if (!rows.length) { el.innerHTML = ''; return; }
    var dt = function (x, yr) { var s = new Date(String(x).slice(0, 10) + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); return yr === false ? s.replace(/ \d{4}$/, '') : s; };
    var dtw = function (x) { return new Date(String(x).slice(0, 10) + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }); };
    var num = function (v, dp) { return v == null ? '–' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: dp, maximumFractionDigits: dp }); };
    var inr = function (v, dp) { return v == null ? '–' : (v < 0 ? '−' : '') + '₹' + num(Math.abs(v), dp == null ? 2 : dp); };
    var sinr = function (v, dp) { return v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + '₹' + num(Math.abs(v), dp == null ? 2 : dp); };
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
      '<p class="vts-buy-warn"><b>Disclaimer:</b> This is a <b>simulation for education only — not a real purchase</b>. No real money is invested, no units are bought or held for anyone, and the agents are internal test accounts, not real investors. Figures are calculated from official end-of-day prices with stamp duty' + (mf ? '' : ', brokerage and exchange charges') + ', exit loads, taxes and settlement days, to show how the model portfolios would have behaved. Not investment advice; not a recommendation to buy any fund. Past or simulated results do not predict future returns.</p>' +
      (mf
        ? '<details class="vts-buy-rule"><summary>⏱ How each fund purchase is priced</summary><ul>' +
          '<li><b>When:</b> every purchase is placed on its plan date before the 3 pm IST cut-off.</li>' +
          '<li><b>Unit price:</b> the fund\'s <b>official NAV of that business day</b> (liquid and overnight funds: the NAV of the previous calendar day); if the fund house has no NAV that day, the next NAV day. Stamp duty of 0.005% is taken first; units are rounded down to 3 decimals and credited two business days later (market holidays skipped). Until then the purchase shows as "buy in progress" — no return, gain or stamp duty is shown before the units are credited.</li>' +
          '<li><b>Record:</b> each purchase in the ledger stores its NAV date and NAV, and the daily audit checks it against the official NAV file.</li></ul></details>'
        : '<details class="vts-buy-rule"><summary>⏱ How each ETF trade is priced</summary><ul>' +
          '<li><b>When:</b> every buy (and any sale) is placed on its plan date and treated as a market-on-close order — it executes at the end of that day\'s trading session, <b>3:30 pm IST</b>.</li>' +
          '<li><b>Unit price:</b> the exchange\'s <b>official closing price</b> of that session (the weighted average price of the last 30 minutes of trading, 3:00–3:30 pm IST). If the market is closed (weekend or exchange holiday) or the ETF did not trade that day, it executes at the close of the next session it trades.</li>' +
          '<li><b>Units:</b> whole units only, as many as the amount buys after charges; cash left over is added to the next buy of the same ETF. Units are credited the next trading day (T+1).</li>' +
          '<li><b>Record:</b> each trade in the ledger stores this rule, its trade date and the closing price used, and the daily audit checks every trade against the exchange\'s published closing price for that session.</li></ul></details>') +
      '<div class="vts-pf"><button type="button" class="vts-pf-sw" aria-haspopup="listbox" aria-expanded="false"></button>' +
      '<div class="vts-pf-list" role="listbox" aria-label="Switch account" hidden></div></div>' +
      '<div class="vts-pv" aria-live="polite"></div>' +
      '<p class="vts-buy-n">Total return: absolute for accounts under one year old, XIRR after. Day change excludes new money. Updated ' + esc(dt(sb.updated)) + (sb.auditOk === false ? ' · figures withheld while a data check is resolved' : '') + '.</p></div></details>';
    var sw = el.querySelector('.vts-pf-sw'), list = el.querySelector('.vts-pf-list'), pv = el.querySelector('.vts-pv');
    var cache = {}, tab = 'today', per = '1M';

    function drawSwitch() {
      sw.innerHTML = av(cur, true) + '<span class="vts-pf-who"><b>' + esc(cur.name) + (cur.nri ? '<i class="vts-buy-nri">NRI</i>' : '') + '</b><span>' + plan(cur) + '</span></span>' +
        '<span class="vts-pf-st">' + status(cur) + '</span><span class="vts-pf-chg">Switch <i>▾</i></span>';
      list.innerHTML = rows.map(function (r, i) {
        return '<button type="button" role="option" class="vts-pf-o" aria-selected="' + (r === cur) + '" data-i="' + i + '">' + av(r) +
          '<span class="vts-pf-who"><b>' + esc(r.name) + (r.nri ? '<i class="vts-buy-nri">NRI</i>' : '') + '</b><span>' + plan(r) + '</span></span>' +
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
      cur = rows[+b.getAttribute('data-i')];
      try { localStorage.setItem(key, cur.name); } catch (er) {}
      openList(false); drawSwitch(); load(); sw.focus();
    });
    list.addEventListener('keydown', function (e) {
      var os = [].slice.call(list.querySelectorAll('.vts-pf-o')), i = os.indexOf(document.activeElement);
      if (e.key === 'Escape') { openList(false); sw.focus(); }
      else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); var n = os[Math.max(0, Math.min(os.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))]; if (n) n.focus(); }
    });
    document.addEventListener('click', function (e) { if (!list.hidden && !el.querySelector('.vts-pf').contains(e.target)) openList(false); });

    function load() {
      var r = cur;
      if (!r.f || sb.auditOk === false) { render(r, r.detail ? { detail: r.detail } : null); return; }
      if (cache[r.f]) { render(r, cache[r.f]); return; }
      pv.innerHTML = '<div class="vts-pv-load">Loading ' + esc(r.name) + '\'s account…</div>';
      fetch('data/sim/' + encodeURIComponent(r.f) + '.json', { cache: 'no-cache' }).then(function (x) { return x.ok ? x.json() : null; })
        .then(function (a) { cache[r.f] = a || {}; if (cur === r) render(r, a); })
        .catch(function () { if (cur === r) render(r, null); });
    }

    function render(r, a) {
      var x = a && a.detail, rc = (a && a.recent) || [], last = rc[rc.length - 1];
      var h = '<div class="vts-pv-top"><div class="vts-pv-v"><span>Current value</span><b>' + (x && x.val != null ? inr(x.val) : (x ? inr(x.inv) : '–')) + '</b>' +
        (x && x.val == null && r.credit ? '<small>At cost until units are credited on ' + esc(dt(r.credit)) + '</small>' : '') + '</div>' +
        '<div class="vts-pv-k"><div><span>Invested</span><b>' + (x ? inr(x.inv) : '–') + '</b></div>' +
        '<div><span>Total gain</span><b class="' + cl(x && x.gain) + '">' + (x && x.gain != null ? sinr(x.gain) + ' <small>' + spct(r.ret) + '</small>' : '–') + '</b></div>' +
        '<div><span>' + (last ? (last.first ? 'Since purchase' : 'Day change · ' + esc(dt(last.d, false))) : 'Day change') + '</span><b class="' + cl(last && last.chg) + '">' + (last ? sinr(last.chg) + ' <small>' + spct(last.pct) + '</small>' : '–') + '</b></div>' +
        '<div><span>Same money in Nifty 50</span>' + (function () { var bv = last && last.inv ? (last.bval / last.inv - 1) * 100 : (x && x.bench); return '<b class="' + cl(bv) + '">' + (bv != null ? spct(bv) : '–') + '</b>'; })() + '</div></div></div>';
      var tabs = [['today', 'Summary'], ['bench', 'vs Nifty 50'], ['hold', 'Holdings'], ['hist', 'History']];
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
    }

    function pane(r, a) {
      var rc = (a && a.recent) || [], last = rc[rc.length - 1];
      if (tab === 'today') return today(r, last);
      if (tab === 'bench') return bench(a);
      if (tab === 'hold') return holdings(r, a && a.detail);
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
        ' The same money in the Nifty 50 ' + (e.first ? 'is ' : 'moved ') + '<b class="' + cl(e.bpct) + '">' + spct(e.bpct) + '</b>' +
        (Math.abs(gap) >= 0.01 ? ' — ' + Math.abs(gap).toFixed(2) + ' pts ' + (gap > 0 ? 'ahead' : 'behind') + '.' : '.') + '</p>';
      var m = e.mkt || [], nifty = m.filter(function (q) { return q[1] === 'NIFTYBEES'; })[0];
      var others = m.filter(function (q) { return q[1] !== 'NIFTYBEES'; }).slice(0, 4);
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
      h += '<div class="vts-ch-k"><div class="p"><span><i></i>Portfolio</span><b class="' + cl(lastP[1]) + '">' + spct(lastP[1]) + '</b><small>' + inr(q[1]) + '</small></div>' +
        '<div class="b"><span><i></i>Same money in Nifty 50</span><b class="' + cl(lastP[2]) + '">' + spct(lastP[2]) + '</b><small>' + inr(q[5]) + '</small></div></div>';
      h += chart(pts);
      h += '<p class="vts-pv-e">Time-weighted return over the period (daily changes chained, new money excluded). Both start from the same cash on the same dates; units count at cost until credited.</p>';
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
        '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Portfolio versus Nifty 50, cumulative return over the period">' + g +
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
        tip.innerHTML = '<b>' + esc(dt(p[0])) + '</b><span><i class="p"></i>Portfolio ' + spct(p[1]) + '</span><span><i class="b"></i>Nifty 50 ' + spct(p[2]) + '</span>';
        var left = p[3] / 640 * r.width; tip.style.left = Math.min(Math.max(left - tip.offsetWidth / 2, 0), r.width - tip.offsetWidth) + 'px';
      };
      var out = function () { cx.setAttribute('visibility', 'hidden'); tip.hidden = true; };
      svg.addEventListener('mousemove', move); svg.addEventListener('touchmove', move, { passive: true }); svg.addEventListener('touchstart', move, { passive: true });
      svg.addEventListener('mouseleave', out); svg.addEventListener('touchend', out);
    }

    function holdings(r, x) {
      if (!x) return '<p class="vts-pv-e">' + (sb.auditOk === false ? 'Figures are withheld while a data check is resolved.' : 'No purchases yet — the first buy is on ' + esc(dt(sb.start)) + '.') + '</p>';
      var h = '<div class="vts-acc-k">' + [['Next buy', x.next ? dt(x.next) : (r.freq === 'One-time' ? 'One-time (done)' : '–')]].concat(mf ? [] : [['Cash left (next buy)', inr(x.cash)]]).map(function (q) { return '<div><span>' + q[0] + '</span><b>' + q[1] + '</b></div>'; }).join('') + '</div>';
      if (x.hold && x.hold.length) {
        h += '<div class="vts-acc-t" role="table" aria-label="Holdings"><div class="vts-acc-r vts-acc-hd" role="row"><span>' + (mf ? 'Fund' : 'ETF') + '</span><span>Units</span><span>Avg cost</span><span>' + (mf ? 'NAV' : 'Close') + '</span><span>Value</span><span>Gain</span><span>Share</span></div>' +
          x.hold.map(function (o) {
            return '<div class="vts-acc-r" role="row"><span class="vts-acc-n"><b>' + esc(o.n) + '</b><small>' + esc(mf ? (o.cat || '') : o.k + (o.cat ? ' · ' + o.cat : '')) + (o.pu ? ' · <em>' + num(o.pu, mf ? 3 : 0) + ' units being credited' + (o.cr ? ' by ' + esc(dt(o.cr, false)) : '') + '</em>' : '') + '</small></span>' +
              '<span data-l="Units">' + num(o.u, mf ? 3 : 0) + '</span><span data-l="Avg cost">₹' + num(o.avg, mf ? 4 : 2) + '</span>' +
              '<span data-l="' + (mf ? 'NAV' : 'Close') + '">₹' + num(o.px, mf ? 4 : 2) + (o.pd ? '<small>' + dt(o.pd, false) + '</small>' : '') + '</span>' +
              '<span data-l="Value">₹' + num(o.val, 0) + '</span><span data-l="Gain" class="' + cl(o.g) + '">' + spct(o.g) + '</span><span data-l="Share">' + (o.w == null ? '–' : o.w.toFixed(1) + '%') + '</span></div>';
          }).join('') + '</div>';
      }
      if (x.pend && x.pend.length)
        h += '<div class="vts-acc-p"><b>Waiting for price</b>' + x.pend.map(function (o) { return '<div>' + esc(o.n) + ' · ' + inr(Math.round(o.amt), 0) + ' · ordered ' + dt(o.T, false) + ' — ' + esc(o.st) + '</div>'; }).join('') + '</div>';
      h += '<p class="vts-acc-e">Values as of ' + (x.asOf ? esc(dt(x.asOf)) : '–') + ' at official ' + (mf ? 'NAVs' : 'closing prices') + ' · simulation, not real money.</p>';
      return h;
    }

    function history(rc) {
      if (!rc.length) return '<p class="vts-pv-e">Daily summaries start once the units are credited.</p>';
      return '<div class="vts-hist" role="table" aria-label="Recent days"><div class="vts-hist-r hd" role="row"><span>Day</span><span>Value</span><span>Day change</span><span>Portfolio</span><span>Nifty 50</span></div>' +
        rc.slice().reverse().map(function (e) {
          return '<div class="vts-hist-r" role="row"><span>' + esc(dtw(e.d)) + (e.first ? '<small>since purchase</small>' : '') + '</span><span data-l="Value">' + inr(e.val, 0) + '</span>' +
            '<span data-l="Day change" class="' + cl(e.chg) + '">' + sinr(e.chg) + '</span><span data-l="Portfolio" class="' + cl(e.pct) + '">' + spct(e.pct) + '</span><span data-l="Nifty 50" class="' + cl(e.bpct) + '">' + spct(e.bpct) + '</span></div>';
        }).join('') + '</div><p class="vts-pv-e">The full daily history is kept in the ledger journal; the latest ' + rc.length + ' days are shown here.</p>';
    }

    drawSwitch();
    load();
  }
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
    '.vts-acc{min-width:0}.vts-acc[open]{grid-column:1/-1}.vts-acc>summary{list-style:none;cursor:pointer}.vts-acc>summary::-webkit-details-marker{display:none}' +
    '.vts-acc>summary:hover{border-color:var(--accent,#4a90e2)}.vts-acc>summary:focus-visible{outline:2px solid var(--accent,#4a90e2);outline-offset:1px}' +
    '.vts-acc-x{font-style:normal;color:var(--text2);font-size:12px;transition:transform .15s;margin-left:-2px}.vts-acc[open] .vts-acc-x{transform:rotate(180deg)}' +
    '.vts-acc[open]>summary{border-bottom-left-radius:0;border-bottom-right-radius:0;border-color:var(--accent,#4a90e2)}' +
    '.vts-acc-b{border:1px solid var(--accent,#4a90e2);border-top:none;border-radius:0 0 10px 10px;padding:10px 12px 8px;background:var(--surface,transparent)}' +
    '.vts-acc-k{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-bottom:10px}.vts-acc-k div{border:1px solid var(--border);border-radius:8px;padding:6px 9px;min-width:0}' +
    '.vts-acc-k span{display:block;font-size:10.5px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em}.vts-acc-k b{font-size:13px;font-variant-numeric:tabular-nums}' +
    '.vts-acc-r{display:grid;grid-template-columns:minmax(0,2.6fr) repeat(6,minmax(0,1fr));gap:8px;align-items:center;padding:7px 0;border-top:1px solid var(--border);font-size:12.5px;font-variant-numeric:tabular-nums}' +
    '.vts-acc-r>span:not(.vts-acc-n){text-align:right}.vts-acc-r small{display:block;font-size:10.5px;color:var(--text2);font-weight:500}.vts-acc-r em{font-style:normal;color:#d97706}' +
    '.vts-acc-hd>span:first-child{text-align:left!important}.vts-acc-hd{border-top:none;font-size:10.5px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em;font-weight:700}' +
    '.vts-acc-n{min-width:0}.vts-acc-n b{display:block;font-size:12.5px;line-height:1.3;overflow-wrap:anywhere}' +
    '.vts-acc-p{margin-top:8px;font-size:12px;color:var(--text2);line-height:1.6}.vts-acc-p b{display:block;color:var(--text);font-size:12px}' +
    '.vts-acc-e{margin:8px 0 0;font-size:11px;color:var(--text3,var(--text2))}' +
    '@media (max-width:700px){.vts-acc-hd{display:none}.vts-acc-r{grid-template-columns:repeat(3,minmax(0,1fr));row-gap:6px;padding:9px 0}.vts-acc-n{grid-column:1/-1}' +
    '.vts-acc-r>span:not(.vts-acc-n){text-align:left}.vts-acc-r>span[data-l]::before{content:attr(data-l);display:block;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em}' +
    '.vts-acc-k{grid-template-columns:repeat(2,minmax(0,1fr))}}' +
    '@media (max-width:520px){.vts-buy{padding:12px}.vts-buy-h{margin:-12px;padding:12px}.vts-buy-g{grid-template-columns:1fr}' +
    '.vts-buy-t1>b{order:0}.vts-buy-tg{order:1}.vts-buy-badge{order:2}.vts-buy-peek{order:3;flex-basis:100%}.vts-buy:not([open]) .vts-buy-sub{display:none}}' +
    '';
  CSS += '.vts-pf{position:relative;margin:2px 0 12px}' +
    '.vts-pf-sw{display:flex;align-items:center;gap:12px;width:100%;text-align:left;border:1px solid var(--border2,var(--border));border-radius:12px;background:var(--surface2,var(--surface));color:var(--text);padding:10px 12px;cursor:pointer;font:inherit}' +
    '.vts-pf-sw:hover{border-color:var(--accent,#4a90e2)}.vts-pf-sw:focus-visible,.vts-pf-o:focus-visible{outline:2px solid var(--accent,#4a90e2);outline-offset:1px}' +
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
    '.vts-pv-tabs{margin-bottom:12px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}.vts-pv-tabs button{height:36px;font-size:13px;padding:0 6px;min-width:0}' +
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
    '@media (max-width:760px){.vts-pv-top{grid-template-columns:1fr}.vts-pv-k{grid-template-columns:repeat(2,minmax(0,1fr))}.vts-pf-chg{display:none}.vts-pf-sw .vts-pf-av.lg{width:36px;height:36px}' +
    '.vts-hist-r.hd{display:none}.vts-hist-r{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:4px}.vts-hist-r>span:first-child{grid-column:1/-1;font-weight:700}.vts-hist-r>span:not(:first-child){text-align:left}' +
    '.vts-hist-r>span[data-l]::before{content:attr(data-l);display:block;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.03em}.vts-ch-k b{font-size:15px}}';
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
  window.VTSim = { tabSettle: tabSettle, gate: gate, accepted: accepted, faqCols: faqCols, riskPanel: riskPanel, ecoPanel: ecoPanel, risk10: risk10, css: style, simBuy: simBuy, col: col, colOpen: colOpen };
})();
