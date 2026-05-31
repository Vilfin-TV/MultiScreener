const fs = require('fs');

let html = fs.readFileSync('education.html', 'utf8');

// 1. Update cache buster
html = html.replace(/jlpt_textbook_data\.js\?v=\d+/, 'jlpt_textbook_data.js?v=' + Date.now());

// 2. Increase text area size
html = html.replace('.trans-input, .trans-output { width: 100%; height: 120px;', '.trans-input, .trans-output { width: 100%; height: 280px;');

// 3. Move widget from 'writing' to 'writing_practice'
// The exact string was: if (_activeLessonTab === 'writing') { \n      const langs = {
// Wait, I used a regex to safely replace it just in case line endings are weird.
html = html.replace(/if \(_activeLessonTab === 'writing'\) \{\s*const langs = \{/, "if (_activeLessonTab === 'writing_practice') {\n      const langs = {");

// 4. Inject the missing JS block at the very end of the script before </body>
const jsCode = `
// --- TRANSLATOR LOGIC ---
let _transTimeout;

function handleLangChange(type) {
  const inLang = document.getElementById('trans-in-lang');
  const outLang = document.getElementById('trans-out-lang');
  
  if (inLang.value === outLang.value) {
    if (type === 'in') {
      outLang.value = (inLang.value === 'en') ? 'ja' : 'en';
    } else {
      inLang.value = (outLang.value === 'en') ? 'ja' : 'en';
    }
  }
  doTranslation();
}

function doTranslation() {
  const text = document.getElementById('trans-input').value;
  if (!text.trim()) { document.getElementById('trans-output').innerText = 'Translation will appear here...'; return; }
  const inLang = document.getElementById('trans-in-lang').value;
  const outLang = document.getElementById('trans-out-lang').value;
  clearTimeout(_transTimeout);
  document.getElementById('trans-output').innerText = 'Translating...';
  _transTimeout = setTimeout(() => {
    fetch('https://translate.googleapis.com/translate_a/single?client=gtx&sl=' + inLang + '&tl=' + outLang + '&dt=t&q=' + encodeURIComponent(text))
      .then(r => r.json()).then(d => {
        let result = '';
        if(d && d[0]) d[0].forEach(p => { if(p[0]) result += p[0]; });
        document.getElementById('trans-output').innerText = result || 'Translation failed.';
      }).catch(e => { document.getElementById('trans-output').innerText = 'Error: ' + e.message; });
  }, 500);
}
function swapTranslationLangs() {
  const i = document.getElementById('trans-in-lang');
  const o = document.getElementById('trans-out-lang');
  const tmp = i.value; i.value = o.value; o.value = tmp;
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
  rec.onstart = () => { btn.innerHTML = '🔴 Listening...'; btn.style.color = 'var(--red)'; btn.style.borderColor = 'var(--red)'; };
  rec.onend = () => { btn.innerHTML = originalText; btn.style.color = ''; btn.style.borderColor = ''; };
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
// --- END TRANSLATOR LOGIC ---
`;

// Make sure it doesn't get injected twice
if (!html.includes('function doTranslation()')) {
  // Use lastIndexOf to find the final </script> tag
  const lastScriptIdx = html.lastIndexOf('</script>');
  if (lastScriptIdx !== -1) {
    html = html.substring(0, lastScriptIdx) + jsCode + '\\n</script>' + html.substring(lastScriptIdx + 9);
  }
}

// 5. Also, need to update the HTML to use handleLangChange(type) instead of doTranslation() for the onchange
html = html.replace('id="trans-in-lang" class="trans-select" onchange="doTranslation()"', 'id="trans-in-lang" class="trans-select" onchange="handleLangChange(\\\'in\\\')"');
html = html.replace('id="trans-out-lang" class="trans-select" onchange="doTranslation()"', 'id="trans-out-lang" class="trans-select" onchange="handleLangChange(\\\'out\\\')"');

fs.writeFileSync('education.html', html);
console.log('Fixed Translator Bugs and Moved to Writing Practice!');
