import os

def fix_recall_game():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add missing .jlpt-options CSS
    missing_css = """
.jlpt-options { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
@media(max-width:500px){ .jlpt-options{grid-template-columns:1fr} }
"""
    style_end_idx = content.find("</style>")
    if style_end_idx != -1:
        content = content[:style_end_idx] + missing_css + content[style_end_idx:]

    # 2. Re-arrange HTML: Move kana-game-box from left column to right sidebar
    # We will just replace the whole section structure since we know it exactly.
    old_layout = """        <div id="jp-kana-section" class="kana-layout">
          <div>
            <div class="sub-hub-bar" style="border-bottom:none; margin-bottom:12px; padding-bottom:0;">
              <button class="sub-hub-btn active" id="btn-kana-hira" onclick="toggleKanaType('hiragana')">Hiragana</button>
              <button class="sub-hub-btn" id="btn-kana-kata" onclick="toggleKanaType('katakana')">Katakana</button>
            </div>
            <div class="kana-grid" id="kana-grid-area"></div>
            
            <!-- Recall Game Moved Under Grid -->
            <div class="kana-game-box" style="margin-top: 24px;">
              <div class="kana-score-row">
                <span>KANA SOUND RECALL GAME</span>
                <span id="kana-score-display">SCORE: 0 / 0</span>
              </div>
              <div class="kana-game-char" id="kana-game-question">あ</div>
              <p class="study-lead" style="font-size:16px; margin-bottom:8px; text-align:center;">Identify the correct romaji syllable sound:</p>
              <div class="jlpt-options" id="kana-game-options" style="margin-bottom:0;">
              </div>
            </div>
          </div>
          <div class="kana-sidebar">
            <div class="kana-details-box" id="kana-details-box">
              <div style="text-align:center; color:var(--text3);">Click any Character card on the left to inspect its stroke notes, pronunciation, example vocabulary, and custom visual cues!</div>
            </div>
            
            <!-- Academy YouTube Panel -->
            <div class="kana-game-box" style="margin-top:20px; padding:0; overflow:hidden; border:1px solid var(--border2);">
              <div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border2); margin-bottom:0;">
                <span id="academy-video-header">LANGUAGE ACADEMY VIDEOS</span>
              </div>
              <iframe id="academy-video-iframe" 
                      style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;" 
                      allow="autoplay; encrypted-media; picture-in-picture" 
                      allowfullscreen></iframe>
              <div id="academy-video-list" style="max-height:240px; overflow-y:auto; background:var(--card); scrollbar-width:thin;">
                <!-- Dynamically populated by JS -->
              </div>
            </div>
          </div>
        </div>"""

    new_layout = """        <div id="jp-kana-section" class="kana-layout">
          <div>
            <div class="sub-hub-bar" style="border-bottom:none; margin-bottom:12px; padding-bottom:0;">
              <button class="sub-hub-btn active" id="btn-kana-hira" onclick="toggleKanaType('hiragana')">Hiragana</button>
              <button class="sub-hub-btn" id="btn-kana-kata" onclick="toggleKanaType('katakana')">Katakana</button>
            </div>
            <div class="kana-grid" id="kana-grid-area"></div>
          </div>
          <div class="kana-sidebar">
            <div class="kana-details-box" id="kana-details-box">
              <div style="text-align:center; color:var(--text3);">Click any Character card on the left to inspect its stroke notes, pronunciation, example vocabulary, and custom visual cues!</div>
            </div>
            
            <!-- Recall Game Moved Under Letter -->
            <div class="kana-game-box" style="margin-top: 20px;">
              <div class="kana-score-row">
                <span>KANA SOUND RECALL GAME</span>
                <span id="kana-score-display">SCORE: 0 / 0</span>
              </div>
              <div class="kana-game-char" id="kana-game-question">あ</div>
              <p class="study-lead" style="font-size:16px; margin-bottom:8px; text-align:center;">Identify the correct romaji syllable sound:</p>
              <div class="jlpt-options" id="kana-game-options" style="margin-bottom:0;">
              </div>
            </div>
            
            <!-- Academy YouTube Panel -->
            <div class="kana-game-box" style="margin-top:20px; padding:0; overflow:hidden; border:1px solid var(--border2);">
              <div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border2); margin-bottom:0;">
                <span id="academy-video-header">LANGUAGE ACADEMY VIDEOS</span>
              </div>
              <iframe id="academy-video-iframe" 
                      style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;" 
                      allow="autoplay; encrypted-media; picture-in-picture" 
                      allowfullscreen></iframe>
              <div id="academy-video-list" style="max-height:240px; overflow-y:auto; background:var(--card); scrollbar-width:thin;">
                <!-- Dynamically populated by JS -->
              </div>
            </div>
          </div>
        </div>"""

    content = content.replace(old_layout, new_layout)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Fixed layout and CSS!")

fix_recall_game()
