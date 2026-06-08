const fs = require('fs');

let content = fs.readFileSync('index.html', 'utf8');

// 1. CSS adjustments: object-position: top center to prevent head cropping
// Reduce sizes of massive hero images
content = content.replace('.masonry-img { width:100%; height:160px; object-fit:cover; }', '.masonry-img { width:100%; height:160px; object-fit:cover; object-position:top; }');
content = content.replace('.mano-hero img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; transition:transform 0.3s; }', '.mano-hero img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:top; transition:transform 0.3s; }');
content = content.replace('.mano-sub img { width:100%; height:100px; object-fit:cover; }', '.mano-sub img { width:100%; height:100px; object-fit:cover; object-position:top; }');
content = content.replace('.mag-img { width:100%; height:140px; object-fit:cover; }', '.mag-img { width:100%; height:140px; object-fit:cover; object-position:top; }');
content = content.replace('.lnb-hero-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform .3s ease}', '.lnb-hero-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:top;transition:transform .3s ease}');
content = content.replace('.lnb-list-thumb{width:48px;height:48px;border-radius:50%;object-fit:cover;flex-shrink:0;background:var(--card3);border:2px solid var(--border2)}', '.lnb-list-thumb{width:48px;height:48px;border-radius:50%;object-fit:cover;object-position:top;flex-shrink:0;background:var(--card3);border:2px solid var(--border2)}');

content = content.replace('.mano-hero { flex:1; position:relative; border-radius:8px; overflow:hidden; cursor:pointer; min-height: 300px; border:1px solid var(--border); }', '.mano-hero { flex:1; position:relative; border-radius:8px; overflow:hidden; cursor:pointer; min-height: 200px; border:1px solid var(--border); }');
content = content.replace('.lnb-hero-img-wrap{position:relative;width:100%;padding-top:38%;overflow:hidden;flex-shrink:0;background:var(--card3)}', '.lnb-hero-img-wrap{position:relative;width:100%;padding-top:30%;overflow:hidden;flex-shrink:0;background:var(--card3)}');

// Update renderItems to 12 items, decode entities
const newRenderFn = `function renderItems(listEl, items) {
  const channelGroup = listEl.dataset.group || '';
  const all = items.slice(0, 12); // UP TO 12 ITEMS
  if (!all.length) return;

  function _decode(str) {
    if (!str) return '';
    return str.replace(/&amp;/g, '&')
              .replace(/&lt;/g, '<')
              .replace(/&gt;/g, '>')
              .replace(/&quot;/g, '"')
              .replace(/&#39;/g, "'")
              .replace(/&#039;/g, "'")
              .replace(/&nbsp;/g, ' ')
              .replace(//g, ''); // Remove mojibake replacement characters
  }

  function _d(item) {
    const title   = _decode(_cleanNewsTitle(typeof item === 'string' ? item : (item.title || '')));
    const link    = item.link || item.url || '#';
    const rawDesc = _decode(item.description || item.summary || item.content || '');
    const snippet = _sanitizeRssContent(rawDesc, 200);
    const source  = item.source || item.feed || '';
    const pub     = item.pubDate || item.published || '';
    return {
      title, snippet, source,
      imgSrc:   item.image || item.imageUrl || '',
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

  const layouts = ['hero-list', 'masonry', 'manorama', 'magazine'];
  let hash = 0;
  for(let i=0; i<listEl.id.length; i++) hash += listEl.id.charCodeAt(i);
  const layout = layouts[hash % layouts.length];
  
  listEl.className = 'layout-card-grid layout-' + layout;
  let html = '';

  if (layout === 'hero-list') {
    const h = _d(all[0]);
    const wrapBg = h.imgSrc ? \`background-image:url('\${escHtml(h.imgSrc)}');background-size:cover;background-position:top center\` : 'background:var(--card3)';

    const subHtml = all.slice(1, 4).map(item => {
      const d = _d(item);
      return \`<div class="lnb-hero-sub" \${_ca(d)}>
        <div class="lnb-hero-sub-title">\${d.safeTitle}</div>
        \${d.snippet ? \`<div class="lnb-hero-sub-desc">\${escHtml(d.snippet)}</div>\` : ''}
        \${d.timeStr ? \`<div class="lnb-hero-sub-time">\${d.timeStr}</div>\` : ''}
      </div>\`;
    }).join('');

    const heroHtml = \`<div class="lnb-hero-card">
      \${h.imgSrc ? \`<div class="lnb-hero-img-wrap" style="\${wrapBg}">
        <img class="lnb-hero-img" src="\${escHtml(h.imgSrc)}" alt="" loading="lazy" onerror="this.onerror=null;this.style.display='none'">
      </div>\` : ''}
      <div class="lnb-hero-body" \${_ca(h)}>
        <div class="lnb-hero-title">\${h.safeTitle}</div>
        \${h.snippet ? \`<div class="lnb-hero-snippet">\${escHtml(h.snippet)}</div>\` : ''}
        \${h.timeStr ? \`<div class="lnb-hero-time">\${h.timeStr}</div>\` : ''}
      </div>
      \${subHtml ? \`<div class="lnb-hero-subs">\${subHtml}</div>\` : ''}
    </div>\`;

    const listHtml = all.slice(4, 12).map(item => {
      const d = _d(item);
      const catLabel = d.category || d.source || '';
      return \`<div class="lnb-list-item" \${_ca(d)}>
        <div class="lnb-list-body">
          \${catLabel ? \`<div class="lnb-list-category">\${escHtml(catLabel.slice(0, 30))}</div>\` : ''}
          <div class="lnb-list-title">\${d.safeTitle}</div>
          \${d.timeStr ? \`<div class="lnb-list-time">\${d.timeStr}</div>\` : ''}
        </div>
        \${d.imgSrc ? \`<img class="lnb-list-thumb" style="width:40px;height:40px;border-radius:6px;object-position:top;" src="\${escHtml(d.imgSrc)}" alt="" loading="lazy" onerror="this.style.opacity=0">\` : ''}
      </div>\`;
    }).join('');

    html = heroHtml + \`<div class="lnb-right-col">\${listHtml}</div>\`;

  } else if (layout === 'masonry') {
    const cols = [[], [], []];
    all.slice(0, 12).forEach((item, i) => {
      cols[i % 3].push(_d(item));
    });
    html = cols.map(col => \`<div class="masonry-col">\${col.map(d => \`
      <div class="masonry-card" \${_ca(d)}>
        \${d.imgSrc ? \`<img class="masonry-img" style="height:120px;object-position:top;" src="\${escHtml(d.imgSrc)}" loading="lazy" alt="">\` : ''}
        <div class="masonry-body">
          <div class="masonry-title">\${d.safeTitle}</div>
          <div class="masonry-desc">\${escHtml(d.snippet)}</div>
          \${d.timeStr ? \`<div class="masonry-time">\${d.timeStr}</div>\` : ''}
        </div>
      </div>
    \`).join('')}</div>\`).join('');

  } else if (layout === 'manorama') {
    const h = _d(all[0]);
    const heroHtml = \`
      <div class="mano-hero" \${_ca(h)} style="\${!h.imgSrc ? 'min-height:auto;' : ''}">
        \${h.imgSrc ? \`<img src="\${escHtml(h.imgSrc)}" loading="lazy" style="object-position:top;" alt="">
        <div class="mano-hero-grad">
          <div class="mano-hero-title" style="font-size:18px;">\${h.safeTitle}</div>
          <div class="mano-hero-desc" style="font-size:12px;">\${escHtml(h.snippet)}</div>
        </div>\` : \`<div style="padding:20px;background:var(--card3);height:100%;display:flex;flex-direction:column;justify-content:center;">
          <div class="mano-hero-title" style="color:var(--text);font-size:18px;margin-bottom:10px;">\${h.safeTitle}</div>
          <div class="mano-hero-desc" style="color:var(--text3);font-size:12px;">\${escHtml(h.snippet)}</div>
        </div>\`}
      </div>\`;
    
    const subHtml = all.slice(1, 12).map(item => {
      const d = _d(item);
      return \`
        <div class="mano-sub" \${_ca(d)}>
          \${d.imgSrc ? \`<img src="\${escHtml(d.imgSrc)}" style="height:80px;object-position:top;" loading="lazy" alt="">\` : ''}
          <div class="mano-sub-body">
            <div class="mano-sub-title">\${d.safeTitle}</div>
          </div>
        </div>\`;
    }).join('');

    html = \`<div class="mano-left">\${heroHtml}</div><div class="mano-right">\${subHtml}</div>\`;

  } else {
    // magazine
    const magItems = all.slice(0, 12).map(item => {
      const d = _d(item);
      return \`
        <div class="mag-card" \${_ca(d)}>
          \${d.imgSrc ? \`<img class="mag-img" style="height:100px;object-position:top;" src="\${escHtml(d.imgSrc)}" loading="lazy" alt="">\` : ''}
          <div class="mag-body">
            <div class="mag-title">\${d.safeTitle}</div>
            <div class="mag-desc" style="font-size:11px;">\${escHtml(d.snippet)}</div>
            \${d.timeStr ? \`<div class="masonry-time">\${d.timeStr}</div>\` : ''}
          </div>
        </div>\`;
    }).join('');
    html = magItems;
  }

  listEl.innerHTML = html;
}`;

content = content.replace(/function renderItems\(listEl, items\) \{[\s\S]*?(?=function _parseXmlItems)/, newRenderFn + '\n\n');

fs.writeFileSync('index.html', content);
console.log('Fixed UI issues in index.html');
