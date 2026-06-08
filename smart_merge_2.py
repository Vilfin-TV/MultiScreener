import re

with open('education_backup.html', 'r', encoding='utf-8') as f:
    old_html = f.read()

with open('education.html', 'r', encoding='utf-8') as f:
    new_html = f.read()

# ================== 1. EXTRACT CSS ==================
style_start = old_html.find('<style>')
style_end = old_html.find('</style>')
old_css = old_html[style_start:style_end]

marker_idx = old_css.find("/* --- DICTIONARY, TRANSLATOR & WRITING PAD --- */")
if marker_idx == -1: marker_idx = old_css.find('.dict-layout')
if marker_idx == -1: marker_idx = old_css.find('.moc-modal')

missing_css = old_css[max(0, marker_idx-50):] if marker_idx != -1 else ""
new_style_end = new_html.find('</style>')
new_html = new_html[:new_style_end] + "\n/* --- INJECTED CSS FROM BACKUP --- */\n" + missing_css + "\n" + new_html[new_style_end:]

# ================== 2. EXTRACT HTML ==================
jlpt_start = old_html.find('<div class="jlpt-container" id="jlpt-container"')
dict_start = old_html.find('<!-- Dictionary -->')
dict_end = old_html.find('<!-- FOOTER -->')
if dict_end == -1: dict_end = old_html.find('<footer')

jlpt_html = old_html[jlpt_start:dict_start].strip()
dict_html = old_html[dict_start:dict_end].strip()

# ================== 3. INJECT HTML ==================
# We will find the exact bounds of <div id="jp-levels-section" style="display:none;"> ... </div> in new_html
new_jlpt_start = new_html.find('<div id="jp-levels-section" style="display:none;">')
new_dict_start = new_html.find('<div id="jp-dict-section" style="display:none;">')

if new_jlpt_start != -1 and new_dict_start != -1:
    # Replace everything from inside jp-levels-section to the start of jp-dict-section
    prefix = new_html[:new_jlpt_start]
    # We want to replace the content of jp-levels-section with jlpt_html
    suffix = new_html[new_dict_start:]
    
    new_html = prefix + '<div id="jp-levels-section" style="display:none;">\n' + jlpt_html + '\n</div>\n' + suffix

# Now find where the footer starts
footer_start = new_html.find('<!-- ══════════════════════════════════════════\n     FOOTER')
if footer_start == -1: footer_start = new_html.find('<footer')

new_dict_start = new_html.find('<div id="jp-dict-section" style="display:none;">')
if new_dict_start != -1 and footer_start != -1:
    prefix = new_html[:new_dict_start]
    suffix = new_html[footer_start:]
    
    new_html = prefix + '<div id="jp-dict-section" style="display:none;">\n' + dict_html + '\n</div>\n</div>\n' + suffix

# ================== 4. EXTRACT MODALS ==================
modal_start = old_html.find('<!-- MODALS -->')
if modal_start == -1: modal_start = old_html.find('<div class="moc-modal-overlay"')
modal_end = old_html.find('<script src="kanji_data.js">')
modals_html = old_html[modal_start:modal_end].strip()

# Inject Modals right before the Javascript includes
script_include_start = new_html.find('<script src="kanji_data.js"></script>')
new_html = new_html[:script_include_start] + f"\n<!-- INJECTED MODALS -->\n{modals_html}\n\n" + new_html[script_include_start:]

# ================== 5. EXTRACT & INJECT JAVASCRIPT ==================
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

# Fix switchJlptLevel (replace simplified version with original)
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

with open('education.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print("Smart Merge 2 Complete!")
