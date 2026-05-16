/**
 * VilfinTV — Hybrid Symbol Autocomplete
 * =====================================
 * Cascade: local master_symbols.json → Yahoo Finance search → Alpha Vantage
 * Attaches to any input with data-ac="fund" or data-ac="stock"
 * Supports plan filtering via data-ac-plan="fundPlan" for fund radio groups
 */
(function() {
  'use strict';
  var DB = null, DB_CACHE = null, DB_LOADING = false, DB_LOAD_PROMISE = null, AC_TIMER = null, AC_IDX = -1;
  var AV_KEY = localStorage.getItem('av_key') || '';

  function loadLocal() {
    if (DB) return Promise.resolve(DB);
    if (DB_LOAD_PROMISE) return DB_LOAD_PROMISE;
    DB_LOAD_PROMISE = new Promise(function(resolve, reject) {
      DB_LOADING = true;
      fetch('data/master_symbols.json', { cache: 'force-cache' })
        .then(function(r) { return r.ok ? r.json() : Promise.reject('HTTP ' + r.status); })
        .then(function(data) {
          DB = data;
          DB_CACHE = data.map(function(it) {
            return {
              sym: it.symbol, name: it.name, exch: it.exchange, type: it.type,
              symL: (it.symbol||'').toLowerCase(), nameL: (it.name||'').toLowerCase()
            };
          });
          console.log('[AC] Loaded ' + data.length.toLocaleString() + ' symbols');
          resolve(DB);
        }).catch(function(e) {
          console.warn('[AC] Local failed:', e);
          DB = []; DB_CACHE = [];
          resolve([]);
        }).finally(function() { DB_LOADING = false; });
    });
    return DB_LOAD_PROMISE;
  }

  function getPlanFilter(input) {
    var planAttr = input.dataset.acPlan || '';
    if (!planAttr) return '';
    var radios = document.getElementsByName(planAttr);
    for (var i = 0; i < radios.length; i++) {
      if (radios[i].checked) return radios[i].value;
    }
    return '';
  }

  function acSearchEl(input) {
    var q = (input.value||'').trim();
    if (q.length < 2) { acClose(input); return; }
    clearTimeout(AC_TIMER);
    var filterType = input.dataset.ac || '';
    var planFilter = getPlanFilter(input);
    AC_TIMER = setTimeout(function() {
      // Show loading state immediately if DB hasn't loaded yet
      if (DB_LOADING || !DB_CACHE) {
        acRenderLoading(input);
      }
      loadLocal().then(function() {
        var results = localSearch(q, filterType, planFilter);
        if (results.length) {
          acRender(input, results);
        } else if (filterType !== 'fund') {
          // Only try Yahoo/AlphaVantage for non-fund types (Indian MF names aren't indexed there)
          acYahooSearch(input, q, filterType).then(function(r) { acRender(input, r); });
        } else {
          acRender(input, []);
        }
      });
    }, 200);
  }

  function planMatches(nameL, plan) {
    if (!plan) return true;
    if (plan === 'direct') {
      return nameL.indexOf('direct') >= 0 && nameL.indexOf('regular') < 0;
    }
    if (plan === 'regular') {
      return nameL.indexOf('regular') >= 0 && nameL.indexOf('direct') < 0;
    }
    if (plan === 'idcw') {
      return nameL.indexOf('idcw') >= 0;
    }
    return true;
  }

  function localSearch(q, filterType, planFilter) {
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
        var acType = filterType || '';
        if (acType === 'fund' && it.type !== 'Fund') continue;
        if (acType === 'etf' && it.type !== 'ETF') continue;
        if (acType === 'bond' && it.type !== 'Bond') continue;
        if (acType === 'commodity' && it.type !== 'Commodity') continue;
        if (acType === 'stock' && (it.type === 'Fund' || it.type === 'ETF')) continue;
        if (planFilter && !planMatches(it.nameL, planFilter)) continue;
        results.push({ sym: it.sym, name: it.name, exch: it.exch, type: it.type, score: score });
      }
    }
    results.sort(function(a,b) { return b.score - a.score; });
    return results.slice(0, 12);
  }

  function acYahooSearch(input, q) {
    return fetch('https://query1.finance.yahoo.com/v1/finance/search?q='+encodeURIComponent(q)+'&quotesCount=8&newsCount=0&lang=en-US')
      .then(function(r) { return r.json(); })
      .then(function(d) { return (d.quotes||[]).map(function(qt) { return { sym: qt.symbol, name: qt.longname||qt.shortname||qt.symbol, exch: qt.exchange||'', type: qt.quoteType||'' }; }); })
      .catch(function() { return acAlphaVantage(input, q); });
  }

  function acAlphaVantage(input, q) {
    if (!AV_KEY) return [];
    return fetch('https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords='+encodeURIComponent(q)+'&apikey='+AV_KEY)
      .then(function(r) { return r.json(); })
      .then(function(d) { return (d.bestMatches||[]).map(function(m) { return { sym: m['1. symbol'], name: m['2. name'], exch: m['4. region']||'', type: m['3. type']||'' }; }); })
      .catch(function() { return []; });
  }

  function getOrCreateDropdown(input) {
    var dd = input.parentNode.querySelector('.ac-dropdown');
    if (!dd) {
      dd = document.createElement('div');
      dd.className = 'ac-dropdown';
      dd.style.cssText = 'position:absolute;top:100%;left:0;right:0;background:#0d1d35;border:1px solid var(--border,#1e3a5c);border-top:2px solid var(--burn2,#3b82f6);border-radius:0 0 10px 10px;box-shadow:0 8px 28px rgba(0,0,0,.3);max-height:300px;overflow-y:auto;z-index:9999;display:none;scrollbar-width:thin;scrollbar-color:#1e3a5f transparent';
      input.parentNode.style.position = 'relative';
      input.parentNode.appendChild(dd);
    }
    return dd;
  }

  function acRenderLoading(input) {
    var dd = getOrCreateDropdown(input);
    dd.innerHTML = '<div style="display:flex;align-items:center;gap:10px;padding:14px 16px;color:var(--text3,#506480);font-size:13px">'
      + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:ac-spin 1s linear infinite;flex-shrink:0"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>'
      + '<span>Loading fund database&hellip;</span>'
      + '</div>';
    if (!document.getElementById('ac-spin-style')) {
      var style = document.createElement('style');
      style.id = 'ac-spin-style';
      style.textContent = '@keyframes ac-spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}';
      document.head.appendChild(style);
    }
    dd.style.display = 'block';
  }

  function acRender(input, results) {
    var dd = getOrCreateDropdown(input);
    if (!results.length) { dd.style.display='none'; return; }
    AC_IDX = -1;
    dd.innerHTML = results.map(function(r,i) {
      var badge = r.type==='ETF'?'ac-type-etf':(r.type==='Fund'?'ac-type-fund':'ac-type-stock');
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
    // Start loading DB immediately — don't wait for idle, fund pages need it right away
    loadLocal();

    document.addEventListener('input', function(e) {
      var el = e.target.closest('[data-ac]');
      if (!el) return;
      acSearchEl(el);
    });

    // Re-trigger search when plan radio changes
    document.addEventListener('change', function(e) {
      var radio = e.target.closest('input[type="radio"][name]');
      if (!radio) return;
      var planAttr = radio.getAttribute('name');
      var inputs = document.querySelectorAll('[data-ac-plan="' + planAttr + '"]');
      inputs.forEach(function(inp) {
        if (inp.value.trim().length >= 2) acSearchEl(inp);
      });
    });

    document.addEventListener('keydown', function(e) {
      var el = e.target.closest('[data-ac]');
      if (!el) return;
      var dd = el.parentNode.querySelector('.ac-dropdown');
      if (!dd || dd.style.display === 'none') return;
      var items = dd.querySelectorAll('.ac-item');
      if (e.key === 'ArrowDown') { e.preventDefault(); AC_IDX = Math.min(AC_IDX+1, items.length-1); if (items[AC_IDX]) items[AC_IDX].scrollIntoView({block:'nearest'}); acHover(dd); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); AC_IDX = Math.max(AC_IDX-1, 0); if (items[AC_IDX]) items[AC_IDX].scrollIntoView({block:'nearest'}); acHover(dd); }
      else if (e.key === 'Enter' && AC_IDX >= 0) { e.preventDefault(); if (items[AC_IDX]) items[AC_IDX].click(); }
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
