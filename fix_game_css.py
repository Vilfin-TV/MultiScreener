import os

def fix_game_css():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to replace the bad CSS classes and inject proper ones.
    
    # 1. Fix .kana-game-box
    old_kgb = ".kana-game-box {\n  background: var(--card); border: 1px solid var(--border2);\n  border-radius: 12px; padding: 20px; margin-top: 20px;\n}"
    new_kgb = ".kana-game-box {\n  background: var(--card); border: 1px solid var(--border);\n  border-radius: 12px; padding: 20px; margin-top: 20px;\n}"
    content = content.replace(old_kgb, new_kgb)
    
    # 2. Fix .kana-game-char
    old_kgc = ".kana-game-char {\n  font-size: 48px; font-weight: 800; color: var(--text); text-align: center;\n  margin: 10px 0; background: var(--bg); border-radius: 8px; padding: 10px 0;\n}"
    new_kgc = ".kana-game-char {\n  font-size: 48px; font-weight: 800; color: var(--text); text-align: center;\n  margin: 10px 0; background: rgba(0,0,0,0.15); border-radius: 8px; padding: 10px 0;\n}"
    content = content.replace(old_kgc, new_kgc)
    
    # 3. Fix general .option-btn correctness for dark themes
    old_correct = ".option-btn.correct { background: #e0f6e6; border-color: var(--green); color: #21242c; }"
    new_correct = ".option-btn.correct { background: rgba(20,191,150,0.15) !important; border-color: var(--green) !important; color: var(--text) !important; }"
    content = content.replace(old_correct, new_correct)
    
    old_incorrect = ".option-btn.incorrect { background: #fce2e2; border-color: #d92916; color: #21242c; }"
    new_incorrect = ".option-btn.incorrect { background: rgba(217,41,22,0.15) !important; border-color: #d92916 !important; color: var(--text) !important; }"
    content = content.replace(old_incorrect, new_incorrect)
    
    # 4. Add specific overrides for .jlpt-options .option-btn
    missing_css = """
.jlpt-options .option-btn {
  margin-bottom: 0;
  border-radius: 8px;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  font-weight: 600;
  text-align: left;
}
.jlpt-options .option-btn:hover {
  background: var(--card-hover);
}
"""
    style_end_idx = content.find("</style>")
    if style_end_idx != -1:
        content = content[:style_end_idx] + missing_css + content[style_end_idx:]
        
    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print("Game CSS fixed!")

fix_game_css()
