import re

def main():
    with open('education_backup.html', 'r', encoding='utf-8') as f:
        old_html = f.read()
    with open('education_today_broken.html', 'r', encoding='utf-8') as f:
        new_html = f.read()

    # 1. Extract JLPT Container from old_html
    # Look for `<div class="jlpt-container" id="jlpt-container"` until its matching closing div.
    jlpt_match = re.search(r'(<div class="jlpt-container" id="jlpt-container".*?<!-- END OF JLPT CONTAINER -->\s*</div>)', old_html, re.DOTALL)
    if jlpt_match:
        jlpt_container = jlpt_match.group(1)
        # We need to remove the top level selector from the old JLPT container because it's already in the sub-hub bar in the new UI?
        # Actually, let's keep the JLPT container as is, but we will inject it into `jp-levels-section`.
    else:
        # Fallback if no comment
        jlpt_match = re.search(r'(<div class="jlpt-container" id="jlpt-container".*?<div class="qa-card" id="jlpt-quiz-card" style="display:none;"></div>\s*</div>\s*</div>)', old_html, re.DOTALL)
        jlpt_container = jlpt_match.group(1) if jlpt_match else ""

    # Let's extract exactly using string split or regex
    jlpt_start = old_html.find('<div class="jlpt-container" id="jlpt-container"')
    # We find the end of JLPT container. It is right before <!-- Dictionary -->
    dict_start = old_html.find('<!-- Dictionary -->')
    jlpt_container = old_html[jlpt_start:dict_start].strip()

    # 2. Extract Dictionary from old_html
    dict_end = old_html.find('<!-- FOOTER -->')
    if dict_end == -1:
        dict_end = old_html.find('<script src="kanji_data.js"></script>')
    dict_container = old_html[dict_start:dict_end].strip()

    # 3. Inject into new_html
    # Replace `<div id="jp-levels-section" style="display:none;"> ... </div>`
    new_jlpt_section = f'<div id="jp-levels-section" style="display:none;">\n{jlpt_container}\n</div>'
    new_html = re.sub(r'<div id="jp-levels-section" style="display:none;">.*?</div>\s*</div>\s*<div id="jp-dict-section"', new_jlpt_section + '\n        <div id="jp-dict-section"', new_html, flags=re.DOTALL)

    # Replace `<div id="jp-dict-section" style="display:none;"> ... </div>`
    new_html = re.sub(r'<div id="jp-dict-section" style="display:none;">.*?</div>', f'<div id="jp-dict-section" style="display:none;">\n{dict_container}\n</div>', new_html, flags=re.DOTALL)

    # 4. Extract Javascript functions from old_html
    # We need: switchJlptLevel, switchLessonTab, renderLessonTabContent, renderJlptContent, changeLessonPage, openMocTestModal, closeMocTestModal, submitMocTest, and all Translator/Dictionary logic.
    # It's safest to extract the ENTIRE script block that contains JLPT/Translator/Dict logic and overwrite the JS in the new HTML.
    
    # Old script block starts at `// Active States`
    js_start = old_html.find('// Active States')
    js_end = old_html.find('</script>', js_start)
    old_js = old_html[js_start:js_end]

    # New script block starts at `// Active States`
    new_js_start = new_html.find('// Active States')
    new_js_end = new_html.find('</script>', new_js_start)
    
    # Wait, new_js has some new UI specific logic for Kana, Kanji Hubs:
    # switchJpSubHub, toggleKanaType, etc.
    # We must KEEP those!
    # Let's extract the Kana/Kanji Hub logic from new_html
    kana_kanji_logic = ""
    subhub_match = re.search(r'(function switchJpSubHub.*?\}).*?(function toggleJpCasualArea.*?\}).*?(function renderKanjiGrid.*?\}).*?(function toggleKanaType.*?\}).*?(function renderKanaGrid.*?\}).*?(function showKanaDetails.*?\}).*?(function playKanaAudio.*?\}).*?(function renderAcademyVideos.*?\}).*?(function playAcademyVideo.*?\}).*?(function renderKanaGame.*?\}).*?(function checkKanaAnswer.*?\}).*?(window\.addEventListener\(\'load\', function\(\) \{.*?\}\);)', new_html[new_js_start:new_js_end], re.DOTALL)
    if subhub_match:
        # Actually it's better to just inject the old JS and APPEND the new UI specific functions, OR inject the missing functions into the new JS.
        pass

    # The missing functions in new_html:
    # renderLessonTabContent
    # renderJlptContent
    # switchLessonTab
    # loadJlptQuiz
    # changeLessonPage
    # changeReadingSubPage
    # playAudioDrill
    # openMocTestModal, closeMocTestModal, submitMocTest, resetJlptProgress
    # TRANSLATOR LOGIC
    # DICTIONARY LOGIC
    # Jisho fetch, etc.

    # Let's just find the missing chunks in old_html
    def extract_func(func_name, code):
        pattern = r'(async function ' + func_name + r'|function ' + func_name + r')\s*\([\w\s,]*\)\s*\{'
        match = re.search(pattern, code)
        if not match:
            return ""
        start = match.start()
        # Find closing brace by counting
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
            
    # Also we need the TRANSLATOR variables and Dictionary state
    translator_vars = """
// --- TRANSLATOR LOGIC ---
let _transDebounce = null;
let _transAudio = null;
let _transVoiceActive = false;
let _transVoiceRecog = null;

"""
    dict_vars = """
// Dictionary State
let _dictResults = [];
"""

    grammar_vars = """
// Grammar Translation State
let _grammarTransDebounce = null;
let _grammarTransAudio = null;
let _grammarVoiceActive = false;
let _grammarVoiceRecog = null;
"""
    
    # We must REPLACE switchJlptLevel in new_html with the one from old_html, because new_html simplified it.
    old_switch_jlpt = extract_func("switchJlptLevel", old_html)
    new_html = re.sub(r'async function switchJlptLevel.*?renderJlptContent\(\);\n\}', old_switch_jlpt, new_html, flags=re.DOTALL)

    # Append all missing JS at the end of the script block
    injection = translator_vars + dict_vars + grammar_vars + missing_js
    
    # We also need to add modals to the HTML body
    modals = ""
    moc_modal_start = old_html.find('<div id="moc-test-modal"')
    if moc_modal_start != -1:
        moc_modal_end = old_html.find('</div>', old_html.find('</div>', old_html.find('</div>', moc_modal_start)+1)+1)+6
        # Just grab from moc_modal_start to end of body
        modals_chunk = old_html[moc_modal_start:old_html.find('</body>')]
        modals = modals_chunk.replace('<script src="kanji_data.js"></script>', '').replace('<script src="jlpt_textbook_data.js?v=1780213198118"></script>', '')

    # Insert modals before </body>
    new_html = new_html.replace('</body>', modals + '\n</body>')

    # Insert missing JS before </script> at the end
    last_script_end = new_html.rfind('</script>')
    new_html = new_html[:last_script_end] + '\n' + injection + '\n' + new_html[last_script_end:]

    # Remove the `var KANA_DATA = [];` etc if they conflict, but let's just write to file
    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(new_html)

if __name__ == "__main__":
    main()
