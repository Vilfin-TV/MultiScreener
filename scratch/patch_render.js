const fs = require('fs');
let content = fs.readFileSync('scratch/renderItems.js', 'utf8');

// 1. Find hero image
content = content.replace(
  'const h = _d(all[0]);',
  'let heroIdx = all.findIndex(item => _d(item).imgSrc); if (heroIdx === -1) heroIdx = 0; const h = _d(all[heroIdx]); const subItems = all.filter((_, i) => i !== heroIdx);'
);
// Replace all.slice(1, ...) with subItems.slice(0, ...)
content = content.replace('all.slice(1, 4).map', 'subItems.slice(0, 3).map');
content = content.replace('all.slice(4, 12).map', 'subItems.slice(3, 11).map');
content = content.replace('all.slice(1, 12).map', 'subItems.slice(0, 11).map');

// 2. Fix manorama sticky and aspect ratio
content = content.replace(
  "class=\"mano-hero\" ${_ca(h)} style=\"${!h.imgSrc ? 'min-height:auto;' : ''}\"",
  "class=\"mano-hero\" ${_ca(h)} style=\"${!h.imgSrc ? 'min-height:auto;' : 'aspect-ratio:4/3;'}\""
);
content = content.replace(
  '<div class="mano-left">',
  '<div class="mano-left" style="align-self:start;position:sticky;top:20px;">'
);

// 3. Fix object-position top being too extreme
content = content.replace(/object-position:top;/g, 'object-position:center 25%;');

fs.writeFileSync('scratch/renderItems2.js', content);
