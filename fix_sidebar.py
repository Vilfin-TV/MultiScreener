import os

def fix_kana_sidebar():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add missing CSS
    missing_css = """
.kana-details-header {
  display: flex; justify-content: space-around; align-items: center;
  margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 12px;
}
.kana-details-big {
  font-size: 60px; font-weight: 800; color: var(--blue);
}
.kana-details-title {
  font-size: 13px; color: var(--text3); text-transform: uppercase; margin-bottom: 2px;
}
.kana-details-val {
  font-size: 16px; font-weight: 700; color: var(--text);
}
.kana-game-box {
  background: var(--card); border: 1px solid var(--border2);
  border-radius: 12px; padding: 20px; margin-top: 20px;
}
.kana-game-char {
  font-size: 48px; font-weight: 800; color: var(--text); text-align: center;
  margin: 10px 0; background: var(--bg); border-radius: 8px; padding: 10px 0;
}
.kana-score-row {
  display: flex; justify-content: space-between; font-size: 12px;
  font-weight: 700; color: var(--text3); margin-bottom: 10px;
}
"""
    # Find </style> and insert missing_css before it
    style_end_idx = content.find("</style>")
    if style_end_idx != -1:
        content = content[:style_end_idx] + missing_css + content[style_end_idx:]

    # 2. Replace kana-sidebar for jp-kana-section
    old_sidebar = """          <div class="kana-sidebar">
            <div class="kana-details-box" id="kana-details-box">Click a card</div>
            <div class="kana-game-box">
              <div class="kana-score-row"><span>RECALL GAME</span><span id="kana-score-display">SCORE: 0 / 0</span></div>
              <div class="kana-char" id="kana-game-question" style="text-align:center; margin:16px 0;">あ</div>
              <div id="kana-game-options"></div>
            </div>
          </div>"""

    new_sidebar = """          <div class="kana-sidebar">
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
          </div>"""
          
    content = content.replace(old_sidebar, new_sidebar)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Sidebar layout fixed successfully!")

fix_kana_sidebar()
