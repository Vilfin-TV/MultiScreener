const fs = require('fs');

let html = fs.readFileSync('education.html', 'utf8');

// 1. Add Grammar button
const oldTabs = `'<div class="class-selector-bar" style="margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid var(--border);">'
    + '  <button class="class-btn ' + (_activeLessonTab === 'overview' ? 'active' : '') + '" onclick="switchLessonTab(\\'overview\\')">Overview</button>'
    + '  <button class="class-btn ' + (_activeLessonTab === 'writing' ? 'active' : '') + '" onclick="switchLessonTab(\\'writing\\')">Writing</button>'
    + '  <button class="class-btn ' + (_activeLessonTab === 'listening' ? 'active' : '') + '" onclick="switchLessonTab(\\'listening\\')">Listening</button>'
    + '  <button class="class-btn ' + (_activeLessonTab === 'reading' ? 'active' : '') + '" onclick="switchLessonTab(\\'reading\\')">Reading</button>'
    + '</div>'`;

const newTabs = `'<div class="class-selector-bar" style="margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid var(--border);">'
    + '  <button class="class-btn ' + (_activeLessonTab === 'overview' ? 'active' : '') + '" onclick="switchLessonTab(\\'overview\\')">Overview</button>'
    + '  <button class="class-btn ' + (_activeLessonTab === 'writing' ? 'active' : '') + '" onclick="switchLessonTab(\\'writing\\')">Writing</button>'
    + '  <button class="class-btn ' + (_activeLessonTab === 'grammar' ? 'active' : '') + '" onclick="switchLessonTab(\\'grammar\\')">Grammar</button>'
    + '  <button class="class-btn ' + (_activeLessonTab === 'listening' ? 'active' : '') + '" onclick="switchLessonTab(\\'listening\\')">Listening</button>'
    + '  <button class="class-btn ' + (_activeLessonTab === 'reading' ? 'active' : '') + '" onclick="switchLessonTab(\\'reading\\')">Reading</button>'
    + '</div>'`;

html = html.replace(oldTabs, newTabs);

const oldTabsCrLf = oldTabs.replace(/\n/g, '\r\n');
if (html.indexOf(oldTabsCrLf) !== -1) {
    html = html.replace(oldTabsCrLf, newTabs.replace(/\n/g, '\r\n'));
}

// 2. Add Grammar rendering logic and change Writing title
const oldWritingTitle = `'<h3 class="study-lead">Writing & Grammar Practice (N' + _activeJlptLevel + ')</h3>'`;
const newWritingTitle = `'<h3 class="study-lead">Writing & Kanji Practice (N' + _activeJlptLevel + ')</h3>'`;
html = html.replace(oldWritingTitle, newWritingTitle);

const oldWritingBlock = `} else if (_activeLessonTab === 'listening') {`;
const newGrammarBlock = `} else if (_activeLessonTab === 'grammar') {
    if (!textbook || !textbook.grammar) { container.innerHTML = '<p>No data</p>'; return; }
    let html = '<h3 class="study-lead">Grammar Structures (N' + _activeJlptLevel + ')</h3>';
    textbook.grammar.forEach(item => {
      html += '<div style="background:var(--card2); border:1px solid var(--border2); padding:16px; border-radius:8px; margin-bottom:16px;">'
        + '  <div style="font-weight:700; color:var(--gold2); font-size:16px; margin-bottom:8px;">' + esc(item.title) + '</div>'
        + '  <p style="color:var(--text2); font-size:13.5px; margin-bottom:12px; line-height:1.6;">' + esc(item.explanation) + '</p>'
        + '  <div style="background:rgba(255,255,255,0.03); border-radius:6px; padding:10px; margin-bottom:12px;">'
        + (item.table || []).map(r => '<div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:13px;"><span style="color:var(--text);">' + esc(r.ja) + '</span><span style="color:var(--text3);">' + esc(r.en) + '</span></div>').join('')
        + '  </div>'
        + '  <div style="font-weight:700; margin-bottom:6px; color:var(--text);">Example Sentences:</div>';
      (item.examples || []).forEach(ex => {
        html += '<div style="background:var(--bg); border-left:3px solid var(--blue); padding:10px; margin-bottom:8px; border-radius:4px;">'
          + '  <div style="font-size:14px; margin-bottom:4px;">' + esc(ex.ja) + '</div>'
          + '  <div style="font-size:12px; color:var(--text3); margin-bottom:2px;">' + esc(ex.romaji) + '</div>'
          + '  <div style="font-size:12px; color:var(--text2);">' + esc(ex.en) + '</div>'
          + '</div>';
      });
      html += '</div>';
    });
    container.innerHTML = html;
  } else if (_activeLessonTab === 'listening') {`;

html = html.replace(oldWritingBlock, newGrammarBlock);

fs.writeFileSync('education.html', html);
console.log('UI updated successfully!');
