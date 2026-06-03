import os

def move_recall_game():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Old structure
    old_layout = """        <div id="jp-kana-section" class="kana-layout">
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
            
            <!-- Recall Game -->
            <div class="kana-game-box">
              <div class="kana-score-row">
                <span>KANA SOUND RECALL GAME</span>
                <span id="kana-score-display">SCORE: 0 / 0</span>
              </div>
              <div class="kana-game-char" id="kana-game-question">あ</div>
              <p class="study-lead" style="font-size:16px; margin-bottom:8px; text-align:center;">Identify the correct romaji syllable sound:</p>
              <div class="jlpt-options" id="kana-game-options" style="margin-bottom:0;">
              </div>
            </div>
            
            <!-- Academy YouTube Panel -->"""

    new_layout = """        <div id="jp-kana-section" class="kana-layout">
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
            
            <!-- Academy YouTube Panel -->"""

    content = content.replace(old_layout, new_layout)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Moved recall game!")

move_recall_game()
