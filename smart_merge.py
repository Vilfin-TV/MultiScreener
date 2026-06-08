import re

with open('education_backup.html', 'r', encoding='utf-8') as f:
    old_html = f.read()

with open('education.html', 'r', encoding='utf-8') as f:
    new_html = f.read()

# 1. EXTRACT CSS
# Find where CSS starts in old_html
style_start = old_html.find('<style>')
style_end = old_html.find('</style>')
old_css = old_html[style_start:style_end]

# Extract specific CSS chunks that were lost
# Let's extract everything from "/* --- DICTIONARY, TRANSLATOR & WRITING PAD --- */" up to the end of old_css
css_marker = "/* --- DICTIONARY, TRANSLATOR & WRITING PAD --- */"
marker_idx = old_css.find(css_marker)
if marker_idx == -1:
    marker_idx = old_css.find('.dict-layout')
if marker_idx == -1:
    marker_idx = old_css.find('.moc-modal')

missing_css = old_css[max(0, marker_idx-50):] if marker_idx != -1 else ""
if not missing_css:
    # fallback: grab from moc-modal down
    moc_idx = old_css.find('.moc-modal')
    missing_css = old_css[max(0, moc_idx-100):] if moc_idx != -1 else ""

# Append missing_css to new_html's style block
new_style_end = new_html.find('</style>')
new_html = new_html[:new_style_end] + "\n/* --- INJECTED FROM BACKUP --- */\n" + missing_css + "\n" + new_html[new_style_end:]

# 2. EXTRACT HTML
jlpt_start = old_html.find('<div class="jlpt-container" id="jlpt-container"')
dict_start = old_html.find('<!-- Dictionary -->')
dict_end = old_html.find('<!-- FOOTER -->')
if dict_end == -1: dict_end = old_html.find('<footer')

jlpt_html = old_html[jlpt_start:dict_start].strip()
dict_html = old_html[dict_start:dict_end].strip()

# Inject HTML into new_html
# In new_html, find <div id="jp-levels-section" style="display:none;"> and replace its contents.
# new_html has exactly one of these because we just reset it.
new_jlpt_marker = '<div id="jp-levels-section" style="display:none;">'
new_dict_marker = '<div id="jp-dict-section" style="display:none;">'

# Find the end of jp-levels-section in new_html
jlpt_pos = new_html.find(new_jlpt_marker)
# Find the next </div></div></div> etc. Actually we can just regex replace the contents between new_jlpt_marker and new_dict_marker
new_html = re.sub(
    r'(<div id="jp-levels-section" style="display:none;">).*?(<div id="jp-dict-section" style="display:none;">)',
    rf'\g<1>\n{jlpt_html}\n</div>\n\g<2>',
    new_html,
    flags=re.DOTALL
)

# Find the end of jp-dict-section in new_html (it goes up to the footer)
new_html = re.sub(
    r'(<div id="jp-dict-section" style="display:none;">).*?(<!-- ══════════════════════════════════════════)',
    rf'\g<1>\n{dict_html}\n</div>\n</div>\n\g<2>',
    new_html,
    flags=re.DOTALL
)

# 3. EXTRACT MODALS
modal_start = old_html.find('<!-- MODALS -->')
if modal_start == -1:
    modal_start = old_html.find('<div class="moc-modal-overlay"')
modal_end = old_html.find('<script src="kanji_data.js">')
modals_html = old_html[modal_start:modal_end].strip()

# Inject Modals before </footer> in new_html? No, before scripts at the bottom.
script_start = new_html.find('<!-- ══════════════════════════════════════════\n     DATABASE & INTERACTIVE LOGIC')
new_html = new_html[:script_start] + f"\n<!-- INJECTED MODALS -->\n{modals_html}\n\n" + new_html[script_start:]

# 4. EXTRACT JAVASCRIPT
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
                in_string = True
                str_char = c
            elif c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    return code[start:i+1]
        else:
            if c == str_char and code[i-1] != '\\':
                in_string = False
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
    if extracted:
        missing_js += extracted + "\n\n"
        
# Fix switchJlptLevel (replace simplified version with original)
old_switch_jlpt = extract_func("switchJlptLevel", old_html)
if old_switch_jlpt:
    new_html = re.sub(r'async function switchJlptLevel.*?renderJlptContent\(\);\n\}', old_switch_jlpt.replace('\\', '\\\\'), new_html, flags=re.DOTALL)

vars_to_inject = """
// --- TRANSLATOR LOGIC ---
let _transDebounce = null;
let _transAudio = null;
let _transVoiceActive = false;
let _transVoiceRecog = null;

// Dictionary State
let _dictResults = [];

// Grammar Translation State
let _grammarTransDebounce = null;
let _grammarTransAudio = null;
let _grammarVoiceActive = false;
let _grammarVoiceRecog = null;
"""

last_script = new_html.rfind('</script>')
new_html = new_html[:last_script] + "\n" + vars_to_inject + "\n" + missing_js + "\n" + new_html[last_script:]

with open('education.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print("Smart Merge Complete!")
