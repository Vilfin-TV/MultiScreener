const fs = require('fs');
const path = require('path');

const target = path.join(__dirname, '../index.html');
let content = fs.readFileSync(target, 'utf8');

// 1. Replace CSS for lns-grid
content = content.replace(
  /\.lns-grid\{display:grid;grid-template-columns:repeat\(2,1fr\);gap:16px;align-items:start\}/g,
  '.lns-grid{display:grid;grid-template-columns:1fr;gap:24px;align-items:start}'
);

// 2. Add layout CSS
const layoutCSS = `
/* Layout Base */
.layout-card-grid { padding:0; overflow:hidden; min-height: 400px; border-bottom-left-radius:10px; border-bottom-right-radius:10px; }

/* ── Layout 1: Hero List (classic) ── */
.layout-hero-list { display:grid; grid-template-columns:1.5fr 1fr; height: 500px; }
@media(max-width:900px){ .layout-hero-list { grid-template-columns:1fr; height:auto; } }

/* ── Layout 2: Masonry / 3 Columns ── */
.layout-masonry { padding:16px; display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; background:var(--card); }
.masonry-col { display:flex; flex-direction:column; gap:16px; }
.masonry-card { background:var(--card2); border-radius:8px; overflow:hidden; display:flex; flex-direction:column; cursor:pointer; transition:transform 0.2s; border:1px solid var(--border); }
.masonry-card:hover { transform:translateY(-2px); border-color:var(--gold2); }
.masonry-img { width:100%; height:160px; object-fit:cover; }
.masonry-body { padding:12px; }
.masonry-title { font-size:14px; font-weight:700; color:var(--text); line-height:1.4; margin-bottom:6px; }
.masonry-desc { font-size:12px; color:var(--text3); line-height:1.5; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.masonry-time { font-size:10px; color:var(--text3); font-family:'JetBrains Mono',monospace; margin-top:8px; }
@media(max-width:900px){ .layout-masonry { grid-template-columns:1fr 1fr; } }
@media(max-width:600px){ .layout-masonry { grid-template-columns:1fr; } }

/* ── Layout 3: Manorama (1 large, 4 small grid) ── */
.layout-manorama { padding:16px; display:grid; grid-template-columns:1.5fr 1fr; gap:16px; background:var(--card); }
.mano-left { display:flex; flex-direction:column; gap:12px; }
.mano-hero { flex:1; position:relative; border-radius:8px; overflow:hidden; cursor:pointer; min-height: 300px; border:1px solid var(--border); }
.mano-hero img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; transition:transform 0.3s; }
.mano-hero:hover img { transform:scale(1.05); }
.mano-hero-grad { position:absolute; inset:0; background:linear-gradient(0deg, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.2) 60%, transparent 100%); display:flex; flex-direction:column; justify-content:flex-end; padding:20px; }
.mano-hero-title { font-size:22px; font-weight:700; color:#fff; line-height:1.3; text-shadow:0 2px 4px rgba(0,0,0,0.8); margin-bottom:8px; }
.mano-hero-desc { font-size:14px; color:#ddd; line-height:1.4; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; text-shadow:0 1px 2px rgba(0,0,0,0.8); }
.mano-right { display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:12px; }
.mano-sub { background:var(--card2); border-radius:8px; overflow:hidden; display:flex; flex-direction:column; cursor:pointer; border:1px solid var(--border); }
.mano-sub:hover { border-color:var(--gold2); }
.mano-sub img { width:100%; height:100px; object-fit:cover; }
.mano-sub-body { padding:10px; display:flex; flex-direction:column; flex:1; }
.mano-sub-title { font-size:13px; font-weight:600; color:var(--text); line-height:1.4; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
@media(max-width:900px){ .layout-manorama { grid-template-columns:1fr; } .mano-right { grid-template-columns:1fr 1fr; } }
@media(max-width:600px){ .mano-right { grid-template-columns:1fr; } }

/* ── Layout 4: Magazine Row ── */
.layout-magazine { padding:16px; display:grid; grid-template-columns:repeat(4, 1fr); gap:16px; background:var(--card); }
.mag-card { background:var(--card2); border-radius:8px; overflow:hidden; display:flex; flex-direction:column; cursor:pointer; border:1px solid var(--border); }
.mag-card:hover { border-color:var(--gold2); }
.mag-img { width:100%; height:140px; object-fit:cover; }
.mag-body { padding:12px; display:flex; flex-direction:column; flex:1; }
.mag-title { font-size:14px; font-weight:700; color:var(--text); line-height:1.4; margin-bottom:6px; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.mag-desc { font-size:12px; color:var(--text3); line-height:1.4; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; margin-bottom:8px; flex:1; }
@media(max-width:1000px){ .layout-magazine { grid-template-columns:repeat(2, 1fr); } }
@media(max-width:600px){ .layout-magazine { grid-template-columns:1fr; } }
`;

content = content.replace(/\.lnb-card-grid\{[^}]+\}/, match => match + '\n' + layoutCSS);

// 3. Replace fetchAllNews
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
content = content.replace(/function fetchAllNews\(\) \{[\s\S]*?\}\n/, newFetchAllNews + '\n');


// 4. Replace fetchFeed (shorter version that uses JSON cache)
const newFetchFeed = `
async function fetchFeed(src, _unused, usedFallback) {
  const listEl = document.getElementById('lnbl-' + src.id);
  if (!listEl) return;
  
  if (liveNewsCache && liveNewsCache[src.id] && liveNewsCache[src.id].length) {
    renderItems(listEl, liveNewsCache[src.id]);
    return;
  }
  
  // Fallback: If not in cache, show error
  listEl.innerHTML = \`<div class="lnb-error">Waiting for backend sync... <br><br> <a href="\${escHtml(src.url)}" target="_blank" style="color:var(--gold2)">Open Feed Directly</a></div>\`;
}
`;
content = content.replace(/async function fetchFeed\(src, _unused, usedFallback\) \{[\s\S]*?(?=\n\/\/ ═══════════════════════════════════════════════════════════════════════════)/, newFetchFeed + '\n');


// 5. Replace renderItems with dynamic layout generation
const newRenderItems = `
function renderItems(listEl, items) {
  const channelGroup = listEl.dataset.group || '';
  const fallbackImg  = _LNB_FALLBACKS[channelGroup] || _LNB_FALLBACK_DEFAULT;
  const all = items.slice(0, 16);
  if (!all.length) return;

  function _d(item) {
    const title   = _cleanNewsTitle(typeof item === 'string' ? item : (item.title || ''));
    const link    = item.link || item.url || '#';
    const rawDesc = item.description || item.summary || item.content || '';
    const snippet = _sanitizeRssContent(rawDesc, 200);
    const source  = item.source || item.feed || '';
    const pub     = item.pubDate || item.published || '';
    return {
      title, snippet, source,
      imgSrc:   item.image || '',
      category: item.category || '',
      timeStr:  pub ? new Date(pub).toLocaleTimeString('en-IN', {hour:'2-digit', minute:'2-digit'}) : '',
      safeTitle:  escHtml(title),
      safeUrl:    escHtml(link),
      safeSrc:    escHtml(source),
      encSnippet: encodeURIComponent(snippet),
    };
  }
  function _ca(d) {
    return \`role="button" tabindex="0" data-title="\${d.safeTitle}" data-snippet="\${d.encSnippet}" data-url="\${d.safeUrl}" data-source="\${d.safeSrc}" onclick="lnbCardOpen(this)" onkeydown="if(event.key==='Enter')lnbCardOpen(this)"\`;
  }
  function _thumbFallback(title) {
    let h = 0;
    for (let i = 0; i < title.length; i++) { h = Math.imul(31, h) + title.charCodeAt(i) | 0; }
    return \`https://picsum.photos/seed/lnbt\${Math.abs(h) % 8999 + 1000}/500/280\`;
  }

  // Determine dynamic layout based on channel ID
  const layouts = ['hero-list', 'masonry', 'manorama', 'magazine'];
  let hash = 0;
  for(let i=0; i<listEl.id.length; i++) hash += listEl.id.charCodeAt(i);
  // Force specific layouts for demonstration or use hash
  const layout = layouts[hash % layouts.length];
  
  listEl.className = 'layout-card-grid layout-' + layout;
  let html = '';

  if (layout === 'hero-list') {
    // ── Layout 1: Hero List (classic) ──
    const h = _d(all[0]);
    const heroSrc = h.imgSrc || fallbackImg;
    const wrapBg  = \`background-image:url('\${escHtml(fallbackImg)}');background-size:cover;background-position:center\`;

    const subHtml = all.slice(1, 5).map(item => {
      const d = _d(item);
      return \`<div class="lnb-hero-sub" \${_ca(d)}>
        <div class="lnb-hero-sub-title">\${d.safeTitle}</div>
        \${d.snippet ? \`<div class="lnb-hero-sub-desc">\${escHtml(d.snippet)}</div>\` : ''}
        \${d.timeStr ? \`<div class="lnb-hero-sub-time">\${d.timeStr}</div>\` : ''}
      </div>\`;
    }).join('');

    const heroHtml = \`<div class="lnb-hero-card">
      <div class="lnb-hero-img-wrap" style="\${wrapBg}">
        <img class="lnb-hero-img" src="\${escHtml(heroSrc)}" alt="" loading="lazy" onerror="this.onerror=null;this.style.display='none'">
      </div>
      <div class="lnb-hero-body" \${_ca(h)}>
        <div class="lnb-hero-title">\${h.safeTitle}</div>
        \${h.snippet ? \`<div class="lnb-hero-snippet">\${escHtml(h.snippet)}</div>\` : ''}
        \${h.timeStr ? \`<div class="lnb-hero-time">\${h.timeStr}</div>\` : ''}
      </div>
      \${subHtml ? \`<div class="lnb-hero-subs">\${subHtml}</div>\` : ''}
    </div>\`;

    const listHtml = all.slice(5, 13).map(item => {
      const d = _d(item);
      const catLabel = d.category || d.source || '';
      const thumbSrc = d.imgSrc || _thumbFallback(d.title);
      return \`<div class="lnb-list-item" \${_ca(d)}>
        <div class="lnb-list-body">
          \${catLabel ? \`<div class="lnb-list-category">\${escHtml(catLabel.slice(0, 30))}</div>\` : ''}
          <div class="lnb-list-title">\${d.safeTitle}</div>
          \${d.timeStr ? \`<div class="lnb-list-time">\${d.timeStr}</div>\` : ''}
        </div>
        <img class="lnb-list-thumb" src="\${escHtml(thumbSrc)}" alt="" loading="lazy" onerror="this.style.opacity=0">
      </div>\`;
    }).join('');

    html = heroHtml + \`<div class="lnb-right-col">\${listHtml}</div>\`;

  } else if (layout === 'masonry') {
    // ── Layout 2: Masonry ──
    const cols = [[], [], []];
    all.slice(0, 12).forEach((item, i) => {
      cols[i % 3].push(_d(item));
    });
    html = cols.map(col => \`<div class="masonry-col">\${col.map(d => \`
      <div class="masonry-card" \${_ca(d)}>
        <img class="masonry-img" src="\${escHtml(d.imgSrc || _thumbFallback(d.title))}" loading="lazy" alt="">
        <div class="masonry-body">
          <div class="masonry-title">\${d.safeTitle}</div>
          <div class="masonry-desc">\${escHtml(d.snippet)}</div>
          \${d.timeStr ? \`<div class="masonry-time">\${d.timeStr}</div>\` : ''}
        </div>
      </div>
    \`).join('')}</div>\`).join('');

  } else if (layout === 'manorama') {
    // ── Layout 3: Manorama ──
    const h = _d(all[0]);
    const heroHtml = \`
      <div class="mano-hero" \${_ca(h)}>
        <img src="\${escHtml(h.imgSrc || fallbackImg)}" loading="lazy" alt="">
        <div class="mano-hero-grad">
          <div class="mano-hero-title">\${h.safeTitle}</div>
          <div class="mano-hero-desc">\${escHtml(h.snippet)}</div>
        </div>
      </div>\`;
    
    const subHtml = all.slice(1, 5).map(item => {
      const d = _d(item);
      return \`
        <div class="mano-sub" \${_ca(d)}>
          <img src="\${escHtml(d.imgSrc || _thumbFallback(d.title))}" loading="lazy" alt="">
          <div class="mano-sub-body">
            <div class="mano-sub-title">\${d.safeTitle}</div>
          </div>
        </div>\`;
    }).join('');

    html = \`<div class="mano-left">\${heroHtml}</div><div class="mano-right">\${subHtml}</div>\`;

  } else {
    // ── Layout 4: Magazine Row ──
    const magItems = all.slice(0, 4).map(item => {
      const d = _d(item);
      return \`
        <div class="mag-card" \${_ca(d)}>
          <img class="mag-img" src="\${escHtml(d.imgSrc || _thumbFallback(d.title))}" loading="lazy" alt="">
          <div class="mag-body">
            <div class="mag-title">\${d.safeTitle}</div>
            <div class="mag-desc">\${escHtml(d.snippet)}</div>
            \${d.timeStr ? \`<div class="masonry-time">\${d.timeStr}</div>\` : ''}
          </div>
        </div>\`;
    }).join('');
    html = magItems;
  }

  listEl.innerHTML = html;
}
`;
content = content.replace(/function renderItems\(listEl, items\) \{[\s\S]*?(?=\nfunction _parseXmlItems)/, newRenderItems + '\n');


fs.writeFileSync(target, content);
console.log('Successfully patched index.html');
