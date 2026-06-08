const fs = require('fs');
let content = fs.readFileSync('scratch/render_current.js', 'utf8');

// 1. Increase limit to 15 (max items fetched)
content = content.replace('const all = items.slice(0, 12); // UP TO 12 ITEMS', 'const all = items.slice(0, 15);');

// 2. Add fallback layout to masonry if NO items have an image
const fallbackLogic = `
  const hasAnyImg = all.some(item => _d(item).imgSrc);
  if (!hasAnyImg && (layout === 'manorama' || layout === 'hero-list')) {
    layout = 'masonry';
  }
  listEl.className = 'layout-card-grid layout-' + layout;
`;
content = content.replace("listEl.className = 'layout-card-grid layout-' + layout;", fallbackLogic.trim());

// 3. Fix hero-list balancing (let it use all available items)
content = content.replace('subItems.slice(3, 11)', 'subItems.slice(3, 15)');

// 4. Fix masonry balancing (must be multiple of 3)
content = content.replace('all.slice(0, 12).forEach', 'all.slice(0, Math.floor(all.length/3)*3).forEach');

// 5. Fix magazine balancing (must be multiple of 4)
content = content.replace('all.slice(0, 12).map', 'all.slice(0, Math.floor(all.length/4)*4).map');

// 6. Fix manorama balancing
const manoramaSearch = /let heroIdx = all\.findIndex[\s\S]*?html = `<div class="mano-left" style="align-self:start;position:sticky;top:20px;">\$\{heroHtml\}<\/div><div class="mano-right">\$\{subHtml\}<\/div>`;/;

const manoramaReplace = `
    let heroIdx = all.findIndex(item => _d(item).imgSrc); if (heroIdx === -1) heroIdx = 0;
    const h = _d(all[heroIdx]); const subItems = all.filter((_, i) => i !== heroIdx);
    
    const rightCount = Math.min(10, Math.floor(subItems.length / 2) * 2);
    const rightItems = subItems.slice(0, rightCount);
    const leftItems = subItems.slice(rightCount);

    const heroHtml = \`
      <div class="mano-hero" \${_ca(h)} style="\${!h.imgSrc ? 'min-height:auto;' : 'aspect-ratio:4/3;margin-bottom:16px;'}">
        \${h.imgSrc ? \`<img src="\${escHtml(h.imgSrc)}" loading="lazy" style="object-position:center 25%;" alt="">
        <div class="mano-hero-grad">
          <div class="mano-hero-title" style="font-size:18px;">\${h.safeTitle}</div>
          <div class="mano-hero-desc" style="font-size:12px;">\${escHtml(h.snippet)}</div>
        </div>\` : \`<div style="padding:20px;background:var(--card3);height:100%;display:flex;flex-direction:column;justify-content:center;">
          <div class="mano-hero-title" style="color:var(--text);font-size:18px;margin-bottom:10px;">\${h.safeTitle}</div>
          <div class="mano-hero-desc" style="color:var(--text3);font-size:12px;">\${escHtml(h.snippet)}</div>
        </div>\`}
      </div>\`;
    
    const renderManoSub = item => {
      const d = _d(item);
      return \`
        <div class="mano-sub" \${_ca(d)}>
          \${d.imgSrc ? \`<img src="\${escHtml(d.imgSrc)}" style="height:80px;object-position:center 25%;" loading="lazy" alt="">\` : ''}
          <div class="mano-sub-body">
            <div class="mano-sub-title">\${d.safeTitle}</div>
          </div>
        </div>\`;
    };

    const rightHtml = rightItems.map(renderManoSub).join('');
    const leftSubHtml = leftItems.map(renderManoSub).join('');

    html = \`<div class="mano-left" style="display:flex;flex-direction:column;">
      \${heroHtml}
      \${leftSubHtml ? \`<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">\${leftSubHtml}</div>\` : ''}
    </div>
    <div class="mano-right">\${rightHtml}</div>\`;
`;

content = content.replace(manoramaSearch, manoramaReplace.trim());

fs.writeFileSync('scratch/render_current2.js', content);
