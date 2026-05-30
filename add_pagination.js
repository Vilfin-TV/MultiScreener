const fs = require('fs');

let html = fs.readFileSync('education.html', 'utf8');

// 1. Cache bust
html = html.replace('<script src="jlpt_textbook_data.js"></script>', '<script src="jlpt_textbook_data.js?v=' + Date.now() + '"></script>');

// 2. Add global page state
const stateInject = `var _activeLessonTab = 'overview';
var _lessonPageIndexes = { writing: 0, grammar: 0, listening: 0, reading: 0 };

function nextLessonPage(tab) {
  const data = (typeof JLPT_TEXTBOOK !== 'undefined' && JLPT_TEXTBOOK[_activeJlptLevel]) ? JLPT_TEXTBOOK[_activeJlptLevel] : null;
  if (!data || !data[tab]) return;
  if (_lessonPageIndexes[tab] < data[tab].length - 1) {
    _lessonPageIndexes[tab]++;
    renderLessonTabContent();
  }
}

function prevLessonPage(tab) {
  if (_lessonPageIndexes[tab] > 0) {
    _lessonPageIndexes[tab]--;
    renderLessonTabContent();
  }
}
`;
html = html.replace(`var _activeLessonTab = 'overview';`, stateInject);

// 3. Rewrite renderLessonTabContent
// I will just replace the entire function using a robust regex or indexOf.

const startStr = 'function renderLessonTabContent() {';
const endStr = '// Global text-to-speech audio player';

const startIndex = html.indexOf(startStr);
const endIndex = html.indexOf(endStr);

if (startIndex === -1 || endIndex === -1) {
    console.error("Could not find bounds for renderLessonTabContent");
    process.exit(1);
}

const newFunction = `function renderLessonTabContent() {
  const data = JLPT_DATA[_activeJlptLevel] || { lesson: { headline: 'JLPT N' + _activeJlptLevel, lead: 'Study Guide' } };
  const textbook = (typeof JLPT_TEXTBOOK !== 'undefined' && JLPT_TEXTBOOK[_activeJlptLevel]) ? JLPT_TEXTBOOK[_activeJlptLevel] : null;
  const container = document.getElementById('jlpt-lesson-tab-content');
  
  if (_activeLessonTab === 'overview') {
    container.innerHTML = '<p class="study-lead">' + esc(data.lesson.headline) + '</p>'
      + '<p style="margin-bottom:12px; color:var(--text2); font-size:13.5px;">' + esc(data.lesson.lead) + '</p>'
      + '<ul class="study-bullets">'
      + (data.lesson.bullets || []).map(b => '<li>' + b + '</li>').join('')
      + '</ul>';
  } else {
    // Shared pagination logic for writing, grammar, listening, reading
    if (!textbook || !textbook[_activeLessonTab] || textbook[_activeLessonTab].length === 0) { 
      container.innerHTML = '<p>No data</p>'; 
      return; 
    }
    
    const arr = textbook[_activeLessonTab];
    let pageIdx = _lessonPageIndexes[_activeLessonTab] || 0;
    if (pageIdx >= arr.length) { pageIdx = 0; _lessonPageIndexes[_activeLessonTab] = 0; }
    
    const item = arr[pageIdx];
    
    let html = '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">';
    
    if (_activeLessonTab === 'writing') html += '<h3 class="study-lead" style="margin:0;">Writing & Kanji (N' + _activeJlptLevel + ')</h3>';
    else if (_activeLessonTab === 'grammar') html += '<h3 class="study-lead" style="margin:0;">Grammar Structures (N' + _activeJlptLevel + ')</h3>';
    else if (_activeLessonTab === 'listening') html += '<h3 class="study-lead" style="margin:0;">Listening Comprehension (N' + _activeJlptLevel + ')</h3>';
    else if (_activeLessonTab === 'reading') html += '<h3 class="study-lead" style="margin:0;">Reading Comprehension (N' + _activeJlptLevel + ')</h3>';
    
    html += '<div style="font-size:13px; color:var(--text3); background:var(--card3); padding:4px 10px; border-radius:12px;">Page ' + (pageIdx+1) + ' of ' + arr.length + '</div>'
         + '</div>';
         
    html += '<div style="background:var(--card2); border:1px solid var(--border2); padding:16px; border-radius:8px; margin-bottom:16px;">';
    
    if (_activeLessonTab === 'writing') {
      html += '<div style="font-weight:700; color:var(--gold2); font-size:16px; margin-bottom:8px;">' + esc(item.title) + '</div>'
        + '<p style="color:var(--text2); font-size:13.5px; margin-bottom:12px; line-height:1.6;">' + esc(item.explanation) + '</p>'
        + '<div style="background:rgba(255,255,255,0.03); border-radius:6px; padding:10px; margin-bottom:12px;">'
        + (item.table||[]).map(r => '<div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:13px;"><span style="color:var(--text);">' + esc(r.ja) + '</span><span style="color:var(--text3);">' + esc(r.en) + '</span></div>').join('')
        + '</div>';
        if (item.examples && item.examples.length > 0) {
          html += '<div style="font-weight:700; margin-bottom:6px; color:var(--text);">Example Sentences:</div>';
          item.examples.forEach(ex => {
            html += '<div style="margin-bottom:8px; font-size:14px; border-left:3px solid var(--gold2); padding-left:10px;">'
              + '<div style="color:var(--green);">' + esc(ex.ja) + '</div>'
              + '<div style="color:var(--text2); font-size:12px;">' + esc(ex.romaji) + '</div>'
              + '<div style="color:var(--text3); font-size:12px; font-style:italic;">"' + esc(ex.en) + '"</div>'
              + '</div>';
          });
        }
    } else if (_activeLessonTab === 'grammar') {
      html += '<div style="font-weight:700; color:var(--gold2); font-size:16px; margin-bottom:8px;">' + esc(item.title) + '</div>'
        + '<p style="color:var(--text2); font-size:13.5px; margin-bottom:12px; line-height:1.6;">' + esc(item.explanation) + '</p>'
        + '<div style="background:rgba(255,255,255,0.03); border-radius:6px; padding:10px; margin-bottom:12px;">'
        + (item.table || []).map(r => '<div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:13px;"><span style="color:var(--text);">' + esc(r.ja) + '</span><span style="color:var(--text3);">' + esc(r.en) + '</span></div>').join('')
        + '</div>'
        + '<div style="font-weight:700; margin-bottom:6px; color:var(--text);">Example Sentences:</div>';
      (item.examples || []).forEach(ex => {
        html += '<div style="background:var(--bg); border-left:3px solid var(--blue); padding:10px; margin-bottom:8px; border-radius:4px;">'
          + '<div style="font-size:14px; margin-bottom:4px;">' + esc(ex.ja) + '</div>'
          + '<div style="font-size:12px; color:var(--text3); margin-bottom:2px;">' + esc(ex.romaji) + '</div>'
          + '<div style="font-size:12px; color:var(--text2);">' + esc(ex.en) + '</div>'
          + '</div>';
      });
    } else if (_activeLessonTab === 'listening') {
      html += '<div style="font-size:32px; text-align:center; margin-bottom:12px;">🎧</div>'
        + '<div style="text-align:center; margin-bottom:16px;"><button class="widget-btn" onclick="playAudioTranscript(this, \\'' + btoa(unescape(encodeURIComponent(item.transcript))) + '\\')">Play Audio Track</button></div>'
        + '<div style="font-weight:700; color:var(--gold2); font-size:16px; margin-bottom:8px;">' + esc(item.title) + '</div>'
        + '<div style="background:rgba(0,0,0,0.3); border-radius:6px; padding:12px; font-family:monospace; margin-bottom:12px; line-height:1.6;">' + esc(item.transcript).replace(/\\n/g, '<br/>') + '</div>'
        + (item.translation ? ('<div style="font-weight:700; margin-bottom:6px; color:var(--text);">English Translation:</div>'
        + '<div style="color:var(--text2); font-size:13px; margin-bottom:12px; line-height:1.6;">' + esc(item.translation).replace(/\\n/g, '<br/>') + '</div>') : '')
        + (item.notes ? ('<div style="color:var(--amber); font-size:12px; border-top:1px dashed var(--border2); padding-top:8px;">💡 ' + esc(item.notes) + '</div>') : '');
    } else if (_activeLessonTab === 'reading') {
      html += '<div style="font-weight:700; color:var(--gold2); font-size:16px; margin-bottom:8px;">' + esc(item.title) + '</div>'
        + '<p style="font-family:serif; font-size:16px; line-height:1.8; margin-bottom:16px; color:var(--text);">' + esc(item.passage) + '</p>'
        + '<div style="font-weight:700; margin-bottom:6px; color:var(--text);">English Translation:</div>'
        + '<p style="color:var(--text3); font-size:13.5px; margin-bottom:12px; line-height:1.6; font-style:italic;">' + esc(item.translation) + '</p>'
        + '<div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px;">';
      (item.vocabulary || item.vocab || []).forEach(v => {
        let word = v.word || v.ja;
        let meaning = v.meaning || v.en;
        html += '<span style="background:var(--card3); padding:4px 8px; border-radius:4px; font-size:12px;"><strong>' + esc(word) + '</strong>: ' + esc(meaning) + '</span>';
      });
      html += '</div>';
      
      let questions = item.questions || item.comprehension || [];
      if (questions.length > 0) {
        html += '<div style="border-top:1px dashed var(--border2); padding-top:12px;">'
          + '<div style="font-weight:700; margin-bottom:6px;">Comprehension Check:</div>';
        questions.forEach(q => {
          let qText = q.q || q.question;
          let aText = q.a || q.answer;
          html += '<div style="margin-bottom:8px; font-size:13px;"><span style="color:var(--amber);">Q: ' + esc(qText) + '</span><br/><span style="color:var(--green);">A: ' + esc(aText) + '</span></div>';
        });
        html += '</div>';
      }
    }
    
    html += '</div>'; // close card
    
    // Pagination Controls
    html += '<div style="display:flex; justify-content:space-between; margin-bottom:16px;">'
      + '<button class="widget-btn" style="background:var(--card3);" onclick="prevLessonPage(\\'' + _activeLessonTab + '\\')" ' + (pageIdx === 0 ? 'disabled style="opacity:0.5;background:var(--card3);"' : '') + '>⬅ Prev Page</button>'
      + '<button class="widget-btn" style="background:var(--blue);" onclick="nextLessonPage(\\'' + _activeLessonTab + '\\')" ' + (pageIdx >= arr.length - 1 ? 'disabled style="opacity:0.5;background:var(--blue);"' : '') + '>Next Page ➡</button>'
      + '</div>';
      
    // MOC Test Button
    html += '<div style="margin-top:24px; text-align:center; padding-top:16px; border-top:1px solid var(--border);">'
      + '<button class="hub-toggle-btn active" style="background:var(--gold2); border:none; box-shadow:0 0 12px var(--glow);" onclick="openMocTestModal()">🎯 Take N' + _activeJlptLevel + ' MOC Test</button>'
      + '</div>';
      
    container.innerHTML = html;
  }
}

`;

html = html.substring(0, startIndex) + newFunction + html.substring(endIndex);

fs.writeFileSync('education.html', html);
console.log('Successfully added pagination and cache busting!');
