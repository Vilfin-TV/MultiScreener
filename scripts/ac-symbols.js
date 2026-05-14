/**
 * VilfinTV — Hybrid Symbol Autocomplete
 * =====================================
 * Cascade: local master_symbols.json → Yahoo Finance search → Alpha Vantage
 * Attaches to any input with data-ac="fund" or data-ac="stock"
 */
(function() {
  'use strict';
  var DB = null, DB_CACHE = null, DB_LOADING = false, AC_TIMER = null, AC_IDX = -1;
  var AV_KEY = localStorage.getItem('av_key') || '';

  function loadLocal() {
    if (DB || DB_LOADING) return Promise.resolve(DB);
    DB_LOADING = true;
    return fetch('../data/master_symbols.json', { cache: 'force-cache' })
      .then(r => r.ok ? r.json() : Promise.reject('HTTP '+r.status))
      .then(data => {
        DB = data;
        DB_CACHE = data.map(it => ({
          sym: it.symbol, name: it.name, exch: it.exchange, type: it.type,
          symL: (it.symbol||'').toLowerCase(), nameL: (it.name||'').toLowerCase()
        }));
        console.log('[AC] Loaded '+data.length.toLocaleString()+' symbols');
        return DB;
      }).catch(e => { console.warn('[AC] Local failed:',e); DB=[]; DB_CACHE=[]; return []; })
      .finally(() => { DB_LOADING = false; });
  }

  function acSearchEl(input) {
    var q = (input.value||'').trim();
    if (q.length < 2) { acClose(input); return; }
    clearTimeout(AC_TIMER);
    var filterType = input.dataset.ac || ''; // 'fund' or 'stock'
    var resolved = false;
    AC_TIMER = setTimeout(function() {
      if (resolved) return;
      var results = localSearch(q, filterType);
      if (results.length) { acRender(input, results); resolved = true; }
      else acYahooSearch(input, q, filterType).then(r => { if (!resolved) { acRender(input, r); resolved = true; } });
    }, 150);
  }

  function localSearch(q, filterType) {
    if (!DB_CACHE || !DB_CACHE.length) return [];
    var ql = q.toLowerCase(), results = [];
    for (var i = 0; i < DB_CACHE.length && results.length < 24; i++) {
      var it = DB_CACHE[i];
      var score = 0;
      if (it.symL.startsWith(ql)) score = 4;
      else if (it.symL.includes(ql)) score = 3;
      else if (it.nameL.startsWith(ql)) score = 2;
      else if (it.nameL.includes(ql)) score = 1;
      if (score > 0) {
        // Filter by type if specified (fund = only mutual funds, stock = exclude mutual funds)
        if (filterType === 'fund' && it.type !== 'Mutual Fund') continue;
        if (filterType === 'stock' && it.type === 'Mutual Fund') continue;
        results.push({ sym: it.sym, name: it.name, exch: it.exch, type: it.type, score: score });
      }
    }
    results.sort(function(a,b) { return b.score - a.score; });
    return results.slice(0, 12);
  }

  function acYahooSearch(input, q) {
    return fetch('https://query1.finance.yahoo.com/v1/finance/search?q='+encodeURIComponent(q)+'&quotesCount=8&newsCount=0&lang=en-US')
      .then(r => r.json())
      .then(d => (d.quotes||[]).map(qt => ({
        sym: qt.symbol, name: qt.longname||qt.shortname||qt.symbol, exch: qt.exchange||'', type: qt.quoteType||''
      })))
      .catch(function() { return acAlphaVantage(input, q); });
  }

  function acAlphaVantage(input, q) {
    if (!AV_KEY) return [];
    return fetch('https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords='+encodeURIComponent(q)+'&apikey='+AV_KEY)
      .then(r => r.json())
      .then(d => (d.bestMatches||[]).map(m => ({
        sym: m['1. symbol'], name: m['2. name'], exch: m['4. region']||'', type: m['3. type']||''
      })))
      .catch(function() { return []; });
  }

  function acRender(input, results) {
    var dd = input.parentNode.querySelector('.ac-dropdown');
    if (!dd) {
      dd = document.createElement('div');
      dd.className = 'ac-dropdown';
      dd.style.cssText = 'position:absolute;top:100%;left:0;right:0;background:#0d1d35;border:1px solid var(--border,#1e3a5c);border-top:2px solid var(--burn2,#3b82f6);border-radius:0 0 10px 10px;box-shadow:0 8px 28px rgba(0,0,0,.3);max-height:300px;overflow-y:auto;z-index:9999;display:none;scrollbar-width:thin;scrollbar-color:#1e3a5f transparent';
      input.parentNode.style.position = 'relative';
      input.parentNode.appendChild(dd);
    }
    if (!results.length) { dd.style.display='none'; return; }
    AC_IDX = -1;
    dd.innerHTML = results.map(function(r,i) {
      var badge = r.type==='ETF'?'ac-type-etf':(r.type==='Mutual Fund'?'ac-type-fund':'ac-type-stock');
      return '<div class="ac-item" data-idx="'+i+'" style="display:flex;align-items:center;gap:8px;padding:9px 12px;cursor:pointer;border-bottom:1px solid rgba(255,255,255,.05);transition:background .1s" onmousedown="event.preventDefault()">'
        +'<span style="font-family:monospace;font-size:11px;font-weight:700;color:var(--burn3,#93c5fd);background:rgba(37,99,235,.15);padding:2px 7px;border-radius:5px;white-space:nowrap">'+esc(r.sym)+'</span>'
        +'<span style="flex:1;font-size:12px;color:var(--text,#e2eeff);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(r.name)+'</span>'
        +'<span style="font-size:10px;color:var(--text3,#506480);white-space:nowrap">'+esc(r.exch)+'</span>'
        +(r.type?'<span class="'+badge+'" style="font-size:9px;font-weight:700;padding:1px 6px;border-radius:4px;background:rgba(22,163,74,.1);color:#16a34a">'+esc(r.type)+'</span>':'')
        +'</div>';
    }).join('');
    dd.querySelectorAll('.ac-item').forEach(function(item) {
      item.addEventListener('click', function() {
        var r = results[parseInt(this.dataset.idx)];
        input.value = r.name || r.sym;
        input.dataset.acSym = r.sym;
        dd.style.display = 'none';
      });
      item.addEventListener('mouseenter', function() { AC_IDX = parseInt(this.dataset.idx); acHover(dd); });
    });
    dd.style.display = 'block';
  }

  function acHover(dd) {
    dd.querySelectorAll('.ac-item').forEach(function(el,i) {
      el.style.background = i === AC_IDX ? 'rgba(37,99,235,.15)' : '';
    });
  }

  function acClose(input) {
    var dd = input && input.parentNode ? input.parentNode.querySelector('.ac-dropdown') : null;
    if (dd) dd.style.display = 'none';
  }

  function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function acInit() {
    // Preload local DB on idle
    if ('requestIdleCallback' in window) { requestIdleCallback(loadLocal, { timeout: 2000 }); }
    else { setTimeout(loadLocal, 1000); }

    document.addEventListener('input', function(e) {
      var el = e.target.closest('[data-ac]');
      if (!el) return;
      acSearchEl(el);
    });
    document.addEventListener('keydown', function(e) {
      var el = e.target.closest('[data-ac]');
      if (!el) return;
      var dd = el.parentNode.querySelector('.ac-dropdown');
      if (!dd || dd.style.display === 'none') return;
      var items = dd.querySelectorAll('.ac-item');
      if (e.key === 'ArrowDown') { e.preventDefault(); AC_IDX = Math.min(AC_IDX+1, items.length-1); items[AC_IDX]?.scrollIntoView({block:'nearest'}); acHover(dd); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); AC_IDX = Math.max(AC_IDX-1, 0); items[AC_IDX]?.scrollIntoView({block:'nearest'}); acHover(dd); }
      else if (e.key === 'Enter' && AC_IDX >= 0) { e.preventDefault(); items[AC_IDX]?.click(); }
      else if (e.key === 'Escape') { acClose(el); }
    });
    document.addEventListener('click', function(e) {
      if (!e.target.closest('[data-ac]') && !e.target.closest('.ac-dropdown')) {
        document.querySelectorAll('[data-ac]').forEach(function(el) { acClose(el); });
      }
    });
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', acInit); }
  else { acInit(); }
})();
