const fs = require('fs');
let content = fs.readFileSync('index.html', 'utf8');

// 1. Rewrite fetchAllNews and add liveNewsCache
const newFetchAllNews = `
let liveNewsCache = null;

async function fetchAllNews() {
  const activeFeeds = getActiveFeeds();
  activeFeeds.forEach(s => {
    const listEl = document.getElementById('lnbl-' + s.id);
    if (listEl) listEl.innerHTML = '<div class="lnb-loading">Loading LIVE data...</div>';
  });

  try {
    const res = await fetch('data/live_news.json?_t=' + Date.now(), { cache: 'no-store' });
    if (res.ok) {
      liveNewsCache = await res.json();
    }
  } catch(e) {
    console.error("Failed to load backend live news cache", e);
  }

  activeFeeds.forEach(s => fetchFeed(s, 0));
}
`;

content = content.replace(/function fetchAllNews\(\) \{[\s\S]*?\}\n/, newFetchAllNews);

// 2. Rewrite fetchFeed to be Hybrid
const newFetchFeed = `async function fetchFeed(src, _unused, usedFallback) {
  const listEl = document.getElementById('lnbl-' + src.id);
  if (!listEl) return;
  
  // ── HYBRID: 1. Try pre-built JSON cache ──────────────────────
  if (liveNewsCache && liveNewsCache[src.id] && liveNewsCache[src.id].length) {
    renderItems(listEl, liveNewsCache[src.id]);
    return;
  }

  // ── HYBRID: 2. Fallback to proxy fetch if backend cache failed or empty ──
  const targetUrl = src.url || src.originalUrl;
  if (!targetUrl) {
    listEl.innerHTML = '<div class="lnb-error">Feed unavailable.</div>';
    return;
  }

  const bust = (targetUrl.includes('?') ? '&' : '?') + '_t=' + Date.now();
  const fetchUrl = targetUrl + bust;

  for (const proxy of _PROXY_CHAIN) {
    if (proxy.name === 'worker' && Date.now() < _workerProxyDownUntil) continue;
    try {
      const proxyUrl = proxy.build(fetchUrl);
      const res = await fetch(proxyUrl, { cache: 'no-store', signal: AbortSignal.timeout(proxy.timeout || 10000) });
      if (proxy.name === 'worker' && res.status >= 500) {
        _workerProxyDownUntil = Date.now() + 5 * 60 * 1000;
      }
      if (!res.ok) continue;
      const items = await proxy.extract(res);
      if (items && items.length) {
        try { sessionStorage.setItem(_FEED_CACHE_KEY(src.id), JSON.stringify({ items, ts: Date.now() })); } catch(_) {}
        renderItems(listEl, items);
        return;
      }
    } catch(_) { }
  }

  try {
    const r = await fetch(targetUrl, { signal: AbortSignal.timeout(8000) });
    if (r.ok) {
      const xml = await r.text();
      const items = _parseXmlItems(xml);
      if (items.length) {
        try { sessionStorage.setItem(_FEED_CACHE_KEY(src.id), JSON.stringify({ items, ts: Date.now() })); } catch(_) {}
        renderItems(listEl, items);
        return;
      }
    }
  } catch(_) {}

  if (!usedFallback) {
    const fallbackUrl = getNewsFallbackUrl(src);
    if (fallbackUrl && fallbackUrl !== targetUrl) {
      fetchFeed({ ...src, originalUrl: src.originalUrl || src.url, url: fallbackUrl }, 0, true);
      return;
    }
  }

  try {
    const cached = JSON.parse(sessionStorage.getItem(_FEED_CACHE_KEY(src.id)));
    if (cached && cached.items && cached.items.length) {
      renderItems(listEl, cached.items);
      const ageMin = Math.round((Date.now() - (cached.ts || 0)) / 60000);
      const staleEl = document.createElement('div');
      staleEl.className = 'lnb-stale';
      staleEl.innerHTML = \`⚠️ Cached\${ageMin > 0 ? ' &middot; ' + ageMin + 'm ago' : ''} <button class="lnb-retry" onclick="window._feedRetry('\${src.id}')">↺ Refresh</button>\`;
      listEl.appendChild(staleEl);
      return;
    }
  } catch(_) {}

  const directUrl = src.originalUrl || src.url || '#';
  listEl.innerHTML = \`<div class="lnb-error">Feed unavailable &mdash; <a href="\${escHtml(directUrl)}" target="_blank" style="color:var(--gold2)">Open directly</a> &nbsp;<button class="lnb-retry" onclick="window._feedRetry('\${escHtml(src.id)}')">↺ Retry</button></div>\`;
}
`;

content = content.replace(/async function fetchFeed\(src, _unused, usedFallback\) \{[\s\S]*?(?=\n\/\/ ═══════════════════════════════════════════════════════════════════════════\n\/\/ NEWS SETTINGS MODAL)/, newFetchFeed);

fs.writeFileSync('index.html', content);
console.log('Successfully applied hybrid fetch logic to index.html');
