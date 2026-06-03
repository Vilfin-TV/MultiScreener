import os

def fix_kana_game():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update HTML span
    old_span = "<span>KANA SOUND RECALL GAME</span>"
    new_span = "<span id=\"kana-game-title\">HIRAGANA SOUND RECALL GAME</span>"
    content = content.replace(old_span, new_span)

    # 2. Update toggleKanaType
    old_toggle = """// Toggle Hiragana vs Katakana
function toggleKanaType(type) {
  _activeKanaType = type;
  document.getElementById('btn-kana-hira').classList.remove('active');
  document.getElementById('btn-kana-kata').classList.remove('active');
  
  if (type === 'hiragana') {
    document.getElementById('btn-kana-hira').classList.add('active');
  } else {
    document.getElementById('btn-kana-kata').classList.add('active');
  }
  renderKanaChart();
}"""

    new_toggle = """// Toggle Hiragana vs Katakana
function toggleKanaType(type) {
  _activeKanaType = type;
  document.getElementById('btn-kana-hira').classList.remove('active');
  document.getElementById('btn-kana-kata').classList.remove('active');
  
  const titleEl = document.getElementById('kana-game-title');
  if (type === 'hiragana') {
    document.getElementById('btn-kana-hira').classList.add('active');
    if (titleEl) titleEl.innerText = 'HIRAGANA SOUND RECALL GAME';
  } else {
    document.getElementById('btn-kana-kata').classList.add('active');
    if (titleEl) titleEl.innerText = 'KATAKANA SOUND RECALL GAME';
  }
  renderKanaChart();
  
  // Refresh the game so it immediately shows the correct alphabet character
  if (typeof loadKanaRecallDrill === 'function') {
    loadKanaRecallDrill();
  }
}"""

    content = content.replace(old_toggle, new_toggle)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)

fix_kana_game()
