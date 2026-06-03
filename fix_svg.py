import os
import re

def apply_dynamic_svg():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Replace the getKanaSvgVisual function entirely
    # The function goes from "function getKanaSvgVisual(romaji) {" to the next function declaration
    # I will just use regex to find it
    pattern = r'function getKanaSvgVisual\(romaji\)\s*\{.*?(?=var _activeKanaType)'
    
    new_func = """function getKanaSvgVisual(romaji, wordStr) {
  let mainVisual = "✿";
  let subText = "EXAMPLE";
  
  if (wordStr) {
    const match = wordStr.match(/^([^\\(]+)\\s*\\((.+?)\\)$/);
    if (match) {
      mainVisual = match[1].trim(); 
      subText = match[2].trim().toUpperCase(); 
    } else {
      mainVisual = wordStr.slice(0, 2);
      subText = wordStr.toUpperCase();
    }
  }

  return `<svg width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px;">
    <circle cx="60" cy="50" r="38" fill="var(--card4)" stroke="var(--border2)" stroke-width="1"/>
    <text x="60" y="64" font-size="34" fill="#ffffff" font-weight="bold" text-anchor="middle">${mainVisual}</text>
    <text x="60" y="106" font-size="9" fill="var(--text2)" font-weight="700" text-anchor="middle" letter-spacing="0.5">${subText}</text>
  </svg>`;
}

"""
    content = re.sub(pattern, new_func, content, flags=re.DOTALL)

    # 2. Update the function call
    old_call = "const svgVisual = getKanaSvgVisual(item.r);"
    new_call = "const svgVisual = getKanaSvgVisual(item.r, item.word);"
    content = content.replace(old_call, new_call)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)

apply_dynamic_svg()
