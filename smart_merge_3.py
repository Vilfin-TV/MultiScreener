import re

# 1. READ FILES
with open('education_backup.html', 'r', encoding='utf-8') as f:
    old_html = f.read()

with open('education_today_broken.html', 'r', encoding='utf-8') as f:
    new_html = f.read()

# 2. EXTRACT JLPT LEVELS AND DICT FROM BACKUP
# In old_html, find <div id="jp-levels-section" ...> to the end of it
jlpt_start = old_html.find('<div id="jp-levels-section"')
dict_start = old_html.find('<div id="jp-dict-section"')
footer_start = old_html.find('<!-- FOOTER -->')
if footer_start == -1: footer_start = old_html.find('<footer')

jlpt_html = old_html[jlpt_start:dict_start].strip()
dict_html = old_html[dict_start:footer_start].strip()

# We need to remove the closing </div> of jlpt-container from dict_html if it's there
# Actually, `old_html` structure was:
# <div class="jlpt-container" id="jlpt-container">
#   <div class="sub-hub-bar">...</div>
#   <div id="jp-kana-section">...</div>
#   <div id="jp-kanji-section">...</div>
#   <div id="jp-levels-section">...</div>
#   <div id="jp-dict-section">...</div>
# </div>
# So jlpt_html is just the <div id="jp-levels-section">...</div> block!
# dict_html might include the closing </div> of jlpt-container!
# Let's clean dict_html
dict_end = dict_html.rfind('</div>')
dict_end = dict_html.rfind('</div>', 0, dict_end) # step back a few divs to ensure we don't grab the container's closing div.
# Let's just find the end of `jp-dict-section` properly.
def get_block(html, start_idx):
    brace = 0
    in_block = False
    for i in range(start_idx, len(html)):
        if html[i:i+4] == '<div':
            brace += 1
            in_block = True
        elif html[i:i+6] == '</div>':
            brace -= 1
            if in_block and brace == 0:
                return html[start_idx:i+6]
    return ""

jlpt_html = get_block(old_html, jlpt_start)
dict_html = get_block(old_html, dict_start)

# 3. REPLACE IN NEW HTML
# The new_html has <div id="jp-levels-section" style="display:none;">...</div>
new_jlpt_start = new_html.find('<div id="jp-levels-section"')
new_jlpt_html = get_block(new_html, new_jlpt_start)
if new_jlpt_start != -1 and new_jlpt_html:
    # Change jlpt_html id to just have style="display:none;" instead of class="kana-layout" if needed, 
    # but the old one had class="kana-layout" style="display:none;".
    new_html = new_html.replace(new_jlpt_html, jlpt_html)

new_dict_start = new_html.find('<div id="jp-dict-section"')
new_dict_html = get_block(new_html, new_dict_start)
if new_dict_start != -1 and new_dict_html:
    new_html = new_html.replace(new_dict_html, dict_html)

# 4. EXTRACT MISSING CSS
style_start = old_html.find('<style>')
style_end = old_html.find('</style>')
old_css = old_html[style_start:style_end]

marker_idx = old_css.find("/* --- DICTIONARY, TRANSLATOR & WRITING PAD --- */")
if marker_idx == -1: marker_idx = old_css.find('.dict-layout')
if marker_idx == -1: marker_idx = old_css.find('.moc-modal')
missing_css = old_css[max(0, marker_idx-50):] if marker_idx != -1 else ""

new_style_end = new_html.find('</style>')
new_html = new_html[:new_style_end] + "\n/* --- INJECTED CSS FROM BACKUP --- */\n" + missing_css + "\n" + new_html[new_style_end:]

# 5. INJECT MODALS
modal_start = old_html.find('<!-- MODALS -->')
if modal_start == -1: modal_start = old_html.find('<div class="moc-modal-overlay"')
modal_end = old_html.find('<script src="kanji_data.js">')
modals_html = old_html[modal_start:modal_end].strip()

script_include_start = new_html.find('<script src="kanji_data.js"></script>')
new_html = new_html[:script_include_start] + f"\n<!-- INJECTED MODALS -->\n{modals_html}\n\n" + new_html[script_include_start:]

# 6. JAVASCRIPT FUNCTIONS FOR JLPT AND DICTIONARY
def extract_func(func_name, code):
    pattern = r'(async function ' + func_name + r'|function ' + func_name + r')\s*\([\w\s,]*\)\s*\{'
    match = re.search(pattern, code)
    if not match: return ""
    start = match.start()
    brace_count = 0
    in_string = False
    str_char = ''
    for i in range(start, len(code)):
        c = code[i]
        if not in_string:
            if c in ("'", '"', '`'):
                in_string = True; str_char = c
            elif c == '{': brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0: return code[start:i+1]
        else:
            if c == str_char and code[i-1] != '\\': in_string = False
    return ""

functions_to_copy = [
    "switchLessonTab", "renderLessonTabContent", "renderJlptContent",
    "changeLessonPage", "changeReadingSubPage", "playAudioDrill",
    "openMocTestModal", "closeMocTestModal", "submitMocTest", "resetJlptProgress",
    "loadJlptQuiz", "checkJlptAnswer",
    "doTranslation", "handleLangChange", "swapTranslationLangs",
    "startTranslationVoice", "clearTranslationInput", "copyTranslation",
    "playTranslationAudio", "openCameraModal", "closeCameraModal", "handleTransFileUpload",
    "searchJisho", "renderDictResults", "playDictAudio",
    "handleGrammarTranslation", "openGrammarTranslationModal", "closeGrammarTranslationModal",
    "stopConversation", "startVoiceRecognition", "copyGrammarTranslation", "playGrammarTranslationAudio"
]

missing_js = ""
for func in functions_to_copy:
    extracted = extract_func(func, old_html)
    if extracted: missing_js += extracted + "\n\n"

old_switch_jlpt = extract_func("switchJlptLevel", old_html)
if old_switch_jlpt:
    new_html = re.sub(r'async function switchJlptLevel.*?renderJlptContent\(\);\n\}', old_switch_jlpt.replace('\\', '\\\\'), new_html, flags=re.DOTALL)

vars_to_inject = """
// --- TRANSLATOR LOGIC ---
let _transDebounce = null; let _transAudio = null; let _transVoiceActive = false; let _transVoiceRecog = null;
let _dictResults = [];
let _grammarTransDebounce = null; let _grammarTransAudio = null; let _grammarVoiceActive = false; let _grammarVoiceRecog = null;
"""

last_script = new_html.rfind('</script>')
new_html = new_html[:last_script] + "\n" + vars_to_inject + "\n" + missing_js + "\n" + new_html[last_script:]

# 7. FIX ACADEMY VIDEO IFRAME (Original Layout)
academy_start = new_html.find('<div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border); margin-bottom:0;">')
if academy_start == -1: 
    # In broken it's an SVG layout
    academy_start = new_html.find('<div class="kana-card" style="padding:16px; margin-bottom:12px;">')
academy_iframe_idx = new_html.find('id="academy-video-iframe"', academy_start)
if academy_start != -1 and academy_iframe_idx != -1:
    list_idx = new_html.find('id="academy-video-controls"', academy_iframe_idx)
    list_close = new_html.find('</div>', list_idx) 
    list_close = new_html.find('</div>', list_close + 1)
    list_close = new_html.find('</div>', list_close + 1) + 6
    old_academy_block = new_html[academy_start:list_close]
    
    new_academy_block = '''<div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border); margin-bottom:0; background:var(--card);">
                <span id="academy-video-header" style="font-weight:bold; color:var(--text); text-transform:uppercase; font-size:12px;">LANGUAGE ACADEMY VIDEOS</span>
              </div>
              <iframe id="academy-video-iframe" src="https://www.youtube.com/embed/s8ZtdgZ7Pms?rel=0&controls=1"
                      style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;" 
                      allow="encrypted-media; picture-in-picture" 
                      allowfullscreen></iframe>
              <div id="academy-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:var(--card); border-bottom:1px solid var(--border);">
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg); cursor:pointer;" onclick="playPrevAcademyVideo()">&#9664; Back</button>
                <div style="font-size:12px; color:var(--text3);">Controls & Volume are inside video</div>
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg); cursor:pointer;" onclick="playNextAcademyVideo()">Next &#9654;</button>
              </div>
              <div id="academy-video-title" style="padding:12px 16px; background:var(--bg); color:var(--text2); font-size:14px; font-weight:500; border-bottom-left-radius:8px; border-bottom-right-radius:8px; text-align:center;">
                Katakana Lesson
              </div>'''
    
    if "s8ZtdgZ7Pms" not in old_academy_block:
        new_html = new_html.replace(old_academy_block, new_academy_block)

# 8. FIX KANJI VIDEO IFRAME
pattern = r'<div style="background:#0a192f; border-radius:12px; overflow:hidden; border:1px solid var\(--border2\); margin-bottom:12px; box-shadow:0 8px 24px rgba\(0,0,0,0\.3\);">.*?</div>\s*</div>\s*</div>\s*</div>\s*</div>'
new_kanji_video = '''<div style="border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px;">
              <div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border); margin-bottom:0; background:var(--card);">
                <span id="kanji-video-header" style="font-weight:bold; color:var(--text); text-transform:uppercase; font-size:12px;">KANJI ACADEMY VIDEOS</span>
              </div>
              <iframe id="kanji-video-iframe" src="https://www.youtube.com/embed/nO1N02B7HKE?rel=0&controls=1" style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;"></iframe>
              <div id="kanji-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:var(--card); border-bottom:1px solid var(--border);">
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg); cursor:pointer;" onclick="playPrevKanjiVideo()">&#9664; Back</button>
                <div style="font-size:12px; color:var(--text3);">Controls & Volume are inside video</div>
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg); cursor:pointer;" onclick="playNextKanjiVideo()">Next &#9654;</button>
              </div>
              <div id="kanji-video-title" style="padding:12px 16px; background:var(--bg); color:var(--text2); font-size:14px; font-weight:500; text-align:center;">
                Kanji Mastery Ep 1
              </div>
            </div>'''
new_html = re.sub(pattern, new_kanji_video, new_html, flags=re.DOTALL)

# Add playPrev/Next functions if not present
if "function playNextKanjiVideo()" not in new_html:
    new_html = new_html.replace('// --- TRANSLATOR LOGIC ---', '''let _currentKanjiVideoIdx = 0;
const kanjiVideos = [{id:'nO1N02B7HKE', title:'Kanji Mastery Ep 1'}, {id:'RkQ7pE9A13I', title:'Daily Casual Japanese'}, {id:'tE1cE3xO_o4', title:'Kanji Memory Tricks'}];
function playNextKanjiVideo() {
  _currentKanjiVideoIdx++;
  if (_currentKanjiVideoIdx >= kanjiVideos.length) _currentKanjiVideoIdx = 0;
  const iframe = document.getElementById('kanji-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + kanjiVideos[_currentKanjiVideoIdx].id + '?rel=0&controls=1';
  const title = document.getElementById('kanji-video-title');
  if (title) title.innerText = kanjiVideos[_currentKanjiVideoIdx].title;
}
function playPrevKanjiVideo() {
  _currentKanjiVideoIdx--;
  if (_currentKanjiVideoIdx < 0) _currentKanjiVideoIdx = kanjiVideos.length - 1;
  const iframe = document.getElementById('kanji-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + kanjiVideos[_currentKanjiVideoIdx].id + '?rel=0&controls=1';
  const title = document.getElementById('kanji-video-title');
  if (title) title.innerText = kanjiVideos[_currentKanjiVideoIdx].title;
}

let _currentAcademyVideoIdx = 0;
const academyVideos = [
  {id:'s8ZtdgZ7Pms', title:'Katakana Lesson'},
  {id:'yA8tEEDR-3M', title:'Hiragana Lesson'},
  {id:'nO1N02B7HKE', title:'Japanese Masterclass'}
];
function playNextAcademyVideo() {
  _currentAcademyVideoIdx++;
  if (_currentAcademyVideoIdx >= academyVideos.length) _currentAcademyVideoIdx = 0;
  const iframe = document.getElementById('academy-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + academyVideos[_currentAcademyVideoIdx].id + '?rel=0&controls=1';
  const title = document.getElementById('academy-video-title');
  if (title) title.innerText = academyVideos[_currentAcademyVideoIdx].title;
}
function playPrevAcademyVideo() {
  _currentAcademyVideoIdx--;
  if (_currentAcademyVideoIdx < 0) _currentAcademyVideoIdx = academyVideos.length - 1;
  const iframe = document.getElementById('academy-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + academyVideos[_currentAcademyVideoIdx].id + '?rel=0&controls=1';
  const title = document.getElementById('academy-video-title');
  if (title) title.innerText = academyVideos[_currentAcademyVideoIdx].title;
}
\n// --- TRANSLATOR LOGIC ---''')

with open('education.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print("Smart Merge 3 Complete!")
