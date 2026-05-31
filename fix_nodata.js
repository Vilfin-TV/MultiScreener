const fs = require('fs');

// 1. Add dummy data to jlpt_textbook_data.js
let js = fs.readFileSync('jlpt_textbook_data.js', 'utf8');

// Use regex to inject writing_practice array into each level
js = js.replace(/"1": \{/g, '"1": { "writing_practice": [{ "title": "Translation Writing Pad" }],');
js = js.replace(/"2": \{/g, '"2": { "writing_practice": [{ "title": "Translation Writing Pad" }],');
js = js.replace(/"3": \{/g, '"3": { "writing_practice": [{ "title": "Translation Writing Pad" }],');
js = js.replace(/"4": \{/g, '"4": { "writing_practice": [{ "title": "Translation Writing Pad" }],');
js = js.replace(/"5": \{/g, '"5": { "writing_practice": [{ "title": "Translation Writing Pad" }],');

fs.writeFileSync('jlpt_textbook_data.js', js);

// 2. Modify education.html to stack the JLPT section vertically and bypass pagination UI for writing_practice
let html = fs.readFileSync('education.html', 'utf8');

// Stack vertically instead of side-by-side
html = html.replace('.edu-content-layout {\\r\\n  display:grid;grid-template-columns:1fr 1fr;gap:20px;\\r\\n}', '.edu-content-layout {\\r\\n  display:flex; flex-direction:column; gap:20px;\\r\\n}');
html = html.replace('.edu-content-layout {\\n  display:grid;grid-template-columns:1fr 1fr;gap:20px;\\n}', '.edu-content-layout {\\n  display:flex; flex-direction:column; gap:20px;\\n}');
html = html.replace('.edu-content-layout { display:grid;grid-template-columns:1fr 1fr;gap:20px; }', '.edu-content-layout { display:flex; flex-direction:column; gap:20px; }');
html = html.replace('.edu-content-layout{grid-template-columns:1fr}', '.edu-content-layout{flex-direction:column}');

// Update cache buster
html = html.replace(/jlpt_textbook_data\.js\?v=\d+/, 'jlpt_textbook_data.js?v=' + Date.now());

// Hide pagination controls for writing_practice
const paginationLogic = `if (_activeLessonTab !== 'writing_practice') {
      html += '<div style="display:flex; justify-content:space-between; margin-bottom:16px;">'
        + '<button class="widget-btn" style="background:var(--card3);" onclick="prevLessonPage(\\'' + _activeLessonTab + '\\')" ' + (pageIdx === 0 ? 'disabled style="opacity:0.5;background:var(--card3);"' : '') + '>⬅ Prev Page</button>'
        + '<button class="widget-btn" style="background:var(--blue);" onclick="nextLessonPage(\\'' + _activeLessonTab + '\\')" ' + (pageIdx >= arr.length - 1 ? 'disabled style="opacity:0.5;background:var(--blue);"' : '') + '>Next Page ➡</button>'
        + '</div>';
    }`;
    
html = html.replace(/html \+= '<div style="display:flex; justify-content:space-between; margin-bottom:16px;">'[^\;]+\;/, paginationLogic);

fs.writeFileSync('education.html', html);
console.log('Fixed No Data issue and Layout');
