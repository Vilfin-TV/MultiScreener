function renderItems(listEl, items) {
  if (!listEl || !Array.isArray(items)) return;
  const channelGroup = listEl.dataset.group || '';
  const all = items.slice(0, 15); // UP TO 12 ITEMS
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
              .replace(/\uFFFD/g, ''); // Remove mojibake replacement characters
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
    return `role="button" tabindex="0" data-title="${d.safeTitle}" data-snippet="${d.encSnippet}" data-url="${d.safeUrl}" data-source="${d.safeSrc}" onclick="lnbCardOpen(this)" onkeydown="if(event.key==='Enter')lnbCardOpen(this)"`;
  }

  const layouts = ['hero-list', 'masonry', 'manorama', 'magazine'];
  let hash = 0;
  for(let i=0; i<listEl.id.length; i++) hash += listEl.id.charCodeAt(i);
  const layout = layouts[hash % layouts.length];
  
  const hasAnyImg = all.some(item => _d(item).imgSrc);
  if (!hasAnyImg && (layout === 'manorama' || layout === 'hero-list')) {
    layout = 'masonry';
  }
  listEl.className = 'layout-card-grid layout-' + layout;
  let html = '';

  if (layout === 'hero-list') {
    let heroIdx = all.findIndex(item => _d(item).imgSrc); if (heroIdx === -1) heroIdx = 0;
    const h = _d(all[heroIdx]); const subItems = all.filter((_, i) => i !== heroIdx);
    
    const rightCount = Math.min(10, Math.floor(subItems.length / 2) * 2);
    const rightItems = subItems.slice(0, rightCount);
    const leftItems = subItems.slice(rightCount);

    const heroHtml = `
      <div class="mano-hero" ${_ca(h)} style="${!h.imgSrc ? 'min-height:auto;' : 'aspect-ratio:4/3;margin-bottom:16px;'}">
        ${h.imgSrc ? `<img src="${escHtml(h.imgSrc)}" loading="lazy" style="object-position:center 25%;" alt="">
        <div class="mano-hero-grad">
          <div class="mano-hero-title" style="font-size:18px;">${h.safeTitle}</div>
          <div class="mano-hero-desc" style="font-size:12px;">${escHtml(h.snippet)}</div>
        </div>` : `<div style="padding:20px;background:var(--card3);height:100%;display:flex;flex-direction:column;justify-content:center;">
          <div class="mano-hero-title" style="color:var(--text);font-size:18px;margin-bottom:10px;">${h.safeTitle}</div>
          <div class="mano-hero-desc" style="color:var(--text3);font-size:12px;">${escHtml(h.snippet)}</div>
        </div>`}
      </div>`;
    
    const renderManoSub = item => {
      const d = _d(item);
      return `
        <div class="mano-sub" ${_ca(d)}>
          ${d.imgSrc ? `<img src="${escHtml(d.imgSrc)}" style="height:80px;object-position:center 25%;" loading="lazy" alt="">` : ''}
          <div class="mano-sub-body">
            <div class="mano-sub-title">${d.safeTitle}</div>
          </div>
        </div>`;
    };

    const rightHtml = rightItems.map(renderManoSub).join('');
    const leftSubHtml = leftItems.map(renderManoSub).join('');

    html = `<div class="mano-left" style="display:flex;flex-direction:column;">
      ${heroHtml}
      ${leftSubHtml ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">${leftSubHtml}</div>` : ''}
    </div>
    <div class="mano-right">${rightHtml}</div>`;

  } else {
    // magazine
    const magItems = all.slice(0, Math.floor(all.length/4)*4).map(item => {
      const d = _d(item);
      return `
        <div class="mag-card" ${_ca(d)}>
          ${d.imgSrc ? `<img class="mag-img" style="height:100px;object-position:center 25%;" src="${escHtml(d.imgSrc)}" loading="lazy" alt="">` : ''}
          <div class="mag-body">
            <div class="mag-title">${d.safeTitle}</div>
            <div class="mag-desc" style="font-size:11px;">${escHtml(d.snippet)}</div>
            ${d.timeStr ? `<div class="masonry-time">${d.timeStr}</div>` : ''}
          </div>
        </div>`;
    }).join('');
    html = magItems;
  }

  listEl.innerHTML = html;
}