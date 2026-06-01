const fs = require('fs');

let html = fs.readFileSync('education.html', 'utf8');

// 1. Inject CSS for the widget
const cssToInject = `
/* Translation Widget Styles */
.trans-widget {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 24px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
}
.trans-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.trans-select {
  flex: 1;
  min-width: 120px;
  background: var(--card);
  color: var(--text);
  border: 1px solid var(--border);
  padding: 10px;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
}
.trans-swap-btn {
  background: var(--blue);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  font-weight: bold;
  cursor: pointer;
  transition: opacity 0.2s;
}
.trans-swap-btn:hover { opacity: 0.8; }
.trans-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media(max-width: 768px) {
  .trans-body { grid-template-columns: 1fr; }
}
.trans-box {
  background: var(--card2);
  border: 1px solid var(--border2);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.trans-input {
  width: 100%;
  height: 120px;
  background: transparent;
  color: var(--text);
  border: none;
  padding: 16px;
  font-size: 16px;
  resize: none;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}
.trans-output {
  width: 100%;
  height: 120px;
  padding: 16px;
  font-size: 16px;
  color: var(--text2);
  overflow-y: auto;
  box-sizing: border-box;
}
.trans-actions {
  display: flex;
  justify-content: flex-end;
  padding: 8px 12px;
  background: rgba(0,0,0,0.2);
  border-top: 1px solid var(--border2);
}
.trans-action-btn {
  background: transparent;
  color: var(--gold2);
  border: 1px solid var(--gold2);
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}
.trans-action-btn:hover {
  background: var(--gold2);
  color: var(--bg);
}
`;

// Insert CSS right before </style>
html = html.replace('</style>', cssToInject + '\n</style>');

// 2. JS Logic for Translation
const jsToInject = `
// Translation Logic
let _transTimeout;
function doTranslation() {
  const text = document.getElementById('trans-input').value;
  if (!text.trim()) { document.getElementById('trans-output').innerText = 'Translation will appear here...'; return; }
  const inLang = document.getElementById('trans-in-lang').value;
  const outLang = document.getElementById('trans-out-lang').value;
  
  clearTimeout(_transTimeout);
  document.getElementById('trans-output').innerText = 'Translating...';
  _transTimeout = setTimeout(() => {
    const url = \`https://translate.googleapis.com/translate_a/single?client=gtx&sl=\${inLang}&tl=\${outLang}&dt=t&q=\${encodeURIComponent(text)}\`;
    fetch(url)
      .then(r => r.json())
      .then(d => {
        let result = '';
        if(d && d[0]) d[0].forEach(p => { if(p[0]) result += p[0]; });
        document.getElementById('trans-output').innerText = result || 'Translation failed.';
      })
      .catch(e => { document.getElementById('trans-output').innerText = 'Error: ' + e.message; });
  }, 500);
}

function swapTranslationLangs() {
  const i = document.getElementById('trans-in-lang');
  const o = document.getElementById('trans-out-lang');
  const tmp = i.value;
  i.value = o.value;
  o.value = tmp;
  doTranslation();
}

function startTranslationVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { alert('Voice recording is not supported in this browser.'); return; }
  
  const rec = new SR();
  rec.lang = document.getElementById('trans-in-lang').value;
  rec.interimResults = true;
  
  const input = document.getElementById('trans-input');
  const btn = document.getElementById('trans-voice-btn');
  const originalText = btn.innerHTML;
  
  rec.onresult = (e) => {
    let final = '';
    for(let i=0; i < e.results.length; i++) final += e.results[i][0].transcript;
    input.value = final;
    doTranslation();
  };
  
  rec.onstart = () => {
    btn.innerHTML = '🔴 Listening...';
    btn.style.color = 'var(--red)';
    btn.style.borderColor = 'var(--red)';
  };
  
  rec.onend = () => {
    btn.innerHTML = originalText;
    btn.style.color = '';
    btn.style.borderColor = '';
  };
  
  rec.start();
}

function playTranslationAudio() {
  const text = document.getElementById('trans-output').innerText;
  if (!text || text.includes('Translating')) return;
  if (!('speechSynthesis' in window)) { alert('Audio not supported.'); return; }
  
  const u = new SpeechSynthesisUtterance(text);
  u.lang = document.getElementById('trans-out-lang').value;
  window.speechSynthesis.speak(u);
}
`;

// Insert JS right before </script> at bottom of file
html = html.replace('</script>\n\n</body>', jsToInject + '\n</script>\n\n</body>');


// 3. Inject the HTML into the Writing Tab renderer
const htmlWidget = `
    if (_activeLessonTab === 'writing') {
      const langs = {
        'ja': 'Japanese', 'en': 'English', 'hi': 'Hindi', 'ml': 'Malayalam', 
        'ta': 'Tamil', 'te': 'Telugu', 'kn': 'Kannada', 'bn': 'Bengali', 
        'zh-CN': 'Chinese', 'fr': 'French', 'es': 'Spanish', 'ar': 'Arabic', 
        'mr': 'Marathi', 'gu': 'Gujarati', 'la': 'Latin'
      };
      let optionsHtml = '';
      for(let k in langs) optionsHtml += \`<option value="\${k}">\${langs[k]}</option>\`;
      
      html += \`<div class="trans-widget">
        <div style="font-weight:700; color:var(--gold2); font-size:18px; margin-bottom:12px;">🌟 Intelligent Translator Writing Pad</div>
        <div class="trans-controls">
          <select id="trans-in-lang" class="trans-select" onchange="doTranslation()">\${optionsHtml.replace('value="en"', 'value="en" selected')}</select>
          <button class="trans-swap-btn" onclick="swapTranslationLangs()">⇄ Swap</button>
          <select id="trans-out-lang" class="trans-select" onchange="doTranslation()">\${optionsHtml.replace('value="ja"', 'value="ja" selected')}</select>
        </div>
        <div class="trans-body">
          <div class="trans-box">
            <textarea id="trans-input" class="trans-input" placeholder="Type or dictate text here..." oninput="doTranslation()"></textarea>
            <div class="trans-actions">
              <button id="trans-voice-btn" class="trans-action-btn" onclick="startTranslationVoice()">🎤 Voice Record</button>
            </div>
          </div>
          <div class="trans-box">
            <div id="trans-output" class="trans-output">Translation will appear here...</div>
            <div class="trans-actions">
              <button class="trans-action-btn" onclick="playTranslationAudio()">🔊 Play Audio</button>
            </div>
          </div>
        </div>
      </div>\`;
    }
`;

const targetHtml = `if (_activeLessonTab === 'writing') {
      html += '<div style="font-weight:700; color:var(--gold2); font-size:16px; margin-bottom:8px;">' + esc(item.title) + '</div>'`;

html = html.replace(targetHtml, htmlWidget + "\n      " + targetHtml.replace("if (_activeLessonTab === 'writing') {", "if (item) { // wrap existing writing logic\n"));

// Wait, the block was:
/*
    if (_activeLessonTab === 'writing') {
      html += '<div style="font-weight:700; color:var(--gold2); font-size:16px; margin-bottom:8px;">' + esc(item.title) + '</div>'
...
*/
// The above replacement creates a bug because `if (_activeLessonTab === 'writing')` is now replaced, but we still need the old logic for the textbook lesson!
// Let me refine the replacement:
`;

fs.writeFileSync('inject_translation.js', `const fs = require('fs');

let html = fs.readFileSync('education.html', 'utf8');

// Inject CSS
const cssToInject = \`${cssToInject.replace(/`/g, '\\`')}\`;
if (!html.includes('trans-widget')) {
  html = html.replace('</style>', cssToInject + '\\n</style>');
}

// Inject JS
const jsToInject = \`${jsToInject.replace(/`/g, '\\`')}\`;
if (!html.includes('doTranslation')) {
  html = html.replace('</script>\\n\\n</body>', jsToInject + '\\n</script>\\n\\n</body>');
}

// Inject Widget UI
const targetHtml = \`if (_activeLessonTab === 'writing') {\`;
const replacementHtml = \`${htmlWidget.replace(/`/g, '\\`')}\\n    if (_activeLessonTab === 'writing' && item) {\`;

if (!html.includes('Intelligent Translator Writing Pad')) {
  html = html.replace(targetHtml, replacementHtml);
}

fs.writeFileSync('education.html', html);
console.log('Successfully injected Translation Widget!');`);
