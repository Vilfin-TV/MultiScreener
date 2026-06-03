import re

def apply_merge():
    with open('education.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    with open('education_today_broken.html', 'r', encoding='utf-8') as f:
        broken = f.read()

    # Helper function to replace exactly the match
    def safe_replace(pattern_to_find_in_html, html_str, replacement_str):
        m = re.search(pattern_to_find_in_html, html_str, re.DOTALL)
        if m:
            return html_str.replace(m.group(0), replacement_str)
        return html_str

    # 1. PEXELS IMAGE UPDATE (getKanaSvgVisual)
    kana_match = re.search(r'// Setup local images directory mapping.*?var _activeKanaType', broken, re.DOTALL)
    if kana_match:
        html = safe_replace(r'// Get dynamic SVG visuals for character memory cues.*?var _activeKanaType', html, kana_match.group(0))
        print("Pexels Kana logic merged.")

    # 2. PEXELS IMAGE UPDATE (renderKanjiDetails)
    kanji_match = re.search(r'const imgUrl = `\$\{CF_R2_URL\}/kanji.*?document\.getElementById\(\'kanji-details-box\'\)\.innerHTML = detailsHtml;', broken, re.DOTALL)
    if kanji_match:
        html = safe_replace(r'const detailsHtml = \'\<div class="kana-details-header"\>.*?document\.getElementById\(\'kanji-details-box\'\)\.innerHTML = detailsHtml;', html, kanji_match.group(0))
        print("Pexels Kanji logic merged.")
        
    # 3. VIDEO CONTROLS
    video_logic = re.search(r'// ACADEMY VIDEO INTEGRATION.*?// ---', broken, re.DOTALL)
    if video_logic:
        html = safe_replace(r'// ACADEMY VIDEO INTEGRATION.*?// ---', html, video_logic.group(0))
        print("Video logic merged.")
        
    video_html = re.search(r'\<div class="video-playlist-container"\>.*?\</div\>\s*\</div\>\s*\</div\>', broken, re.DOTALL)
    if video_html:
        html = safe_replace(r'\<div class="video-playlist-container"\>.*?\</div\>\s*\</div\>\s*\</div\>', html, video_html.group(0))
        print("Video HTML merged.")

    # 4. KANA GAMES HTML
    kana_area_match = re.search(r'\<div id="jp-kana-area-container"\>.*?\<!-- END KANA AREA --\>', broken, re.DOTALL)
    if kana_area_match:
        m = re.search(r'\<div id="jp-kana-area-container"\>.*?\</div\>\s*\</div\>\s*\</div\>\s*\<!-- End Kana Section --\>', html, re.DOTALL)
        if m:
            html = html.replace(m.group(0), kana_area_match.group(0) + '\n              </div>\n            </div>\n          </div>\n          <!-- End Kana Section -->')
            print("Kana Games HTML merged.")

    # 5. KANA GAMES JAVASCRIPT LOGIC
    # In the broken file, the functions extend down. Let's find from "// Hiragana Game State" until just before "function renderKanjiHub()"
    game_js_match = re.search(r'// Hiragana Game State.*?function renderKanjiHub', broken, re.DOTALL)
    if game_js_match:
        m = re.search(r'// Kana Game State.*?function renderKanjiHub', html, re.DOTALL)
        if m:
            # We don't want to swallow "function renderKanjiHub", so replace correctly
            replacement = game_js_match.group(0)
            html = html.replace(m.group(0), replacement)
            print("Kana Games JS merged.")

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(html)
        
apply_merge()
