import re

def merge_svgs():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # The current getKanaSvgVisual looks like this:
    # // Set this to your Cloudflare R2 Bucket / Images URL
    # const CF_KANA_IMG_BASE = 'https://your-cloudflare-bucket.com/kana/';
    # function getKanaSvgVisual(romaji, wordStr) { ... }
    
    pattern = r'// Set this to your Cloudflare R2 Bucket / Images URL\s*const CF_KANA_IMG_BASE = [^\n]+\s*function getKanaSvgVisual\(romaji, wordStr\) \{.*?return `<img.*?<\/img>`;\n\}'
    
    new_func = """function getKanaSvgVisual(romaji, wordStr) {
  const r = romaji.toLowerCase();
  
  if (r === 'a') {
    return `<svg width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px;">
      <circle cx="60" cy="70" r="28" fill="var(--amber)" opacity="0.8"/>
      <line x1="15" y1="75" x2="105" y2="75" stroke="#fff" stroke-width="3"/>
      <path d="M 25 85 Q 45 75 65 85 T 105 85" stroke="var(--gold2)" stroke-width="2" fill="none"/>
      <path d="M 15 95 Q 35 85 55 95 T 105 95" stroke="var(--burn2)" stroke-width="2" fill="none"/>
      <text x="60" y="32" font-size="10" fill="var(--text2)" font-weight="700" text-anchor="middle" letter-spacing="1">ASA (SUNRISE)</text>
    </svg>`;
  } else if (r === 'i') {
    return `<svg width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px;">
      <polygon points="35,45 20,70 45,60" fill="var(--text3)"/>
      <polygon points="85,45 100,70 75,60" fill="var(--text3)"/>
      <circle cx="60" cy="70" r="25" fill="var(--card4)" stroke="var(--border2)" stroke-width="2"/>
      <circle cx="50" cy="65" r="3" fill="#fff"/>
      <circle cx="70" cy="65" r="3" fill="#fff"/>
      <polygon points="57,72 63,72 60,76" fill="var(--red)"/>
      <path d="M 57 80 Q 60 83 63 80" stroke="var(--text)" stroke-width="1.5" fill="none"/>
      <text x="60" y="32" font-size="10" fill="var(--text2)" font-weight="700" text-anchor="middle" letter-spacing="1">INU (DOG)</text>
    </svg>`;
  } else if (r === 'u') {
    return `<svg width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px;">
      <path d="M15,50 C45,30 75,70 105,50" stroke="var(--gold2)" stroke-width="3" stroke-linecap="round" fill="none"/>
      <path d="M10,75 C40,55 70,95 110,75" stroke="var(--burn2)" stroke-width="3" stroke-linecap="round" fill="none"/>
      <path d="M40,75 L80,75 L90,65 L30,65 Z" fill="var(--text2)"/>
      <line x1="60" y1="65" x2="60" y2="45" stroke="#fff" stroke-width="2"/>
      <polygon points="60,45 75,52 60,60" fill="var(--red)"/>
      <text x="60" y="32" font-size="10" fill="var(--text2)" font-weight="700" text-anchor="middle" letter-spacing="1">UMI (SEA)</text>
    </svg>`;
  } else if (r === 'e') {
    return `<svg width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px;">
      <line x1="20" y1="80" x2="100" y2="80" stroke="var(--border2)" stroke-width="4"/>
      <line x1="20" y1="90" x2="100" y2="90" stroke="var(--border2)" stroke-width="4"/>
      <line x1="30" y1="75" x2="30" y2="95" stroke="var(--text3)" stroke-width="2"/>
      <line x1="50" y1="75" x2="50" y2="95" stroke="var(--text3)" stroke-width="2"/>
      <line x1="70" y1="75" x2="70" y2="95" stroke="var(--text3)" stroke-width="2"/>
      <rect x="40" y="45" width="40" height="20" rx="3" fill="var(--card3)" stroke="var(--green)" stroke-width="1.5"/>
      <text x="60" y="58" font-size="8" fill="#fff" font-weight="700" text-anchor="middle">EKI</text>
      <line x1="60" y1="65" x2="60" y2="75" stroke="#fff" stroke-width="2"/>
      <text x="60" y="32" font-size="10" fill="var(--text2)" font-weight="700" text-anchor="middle" letter-spacing="1">EKI (STATION)</text>
    </svg>`;
  } else if (r === 'o') {
    return `<svg width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px;">
      <path d="M 50 45 Q 45 35 50 25" stroke="var(--text3)" stroke-width="2" fill="none"/>
      <path d="M 60 45 Q 55 35 60 25" stroke="var(--text3)" stroke-width="2" fill="none"/>
      <rect x="40" y="48" width="40" height="40" rx="6" fill="var(--card4)" stroke="var(--border2)" stroke-width="2"/>
      <rect x="43" y="52" width="34" height="10" rx="2" fill="var(--green)" opacity="0.7"/>
      <text x="60" y="72" font-size="9" fill="var(--text2)" font-weight="700" text-anchor="middle">TEA</text>
      <text x="60" y="106" font-size="10" fill="var(--text2)" font-weight="700" text-anchor="middle" letter-spacing="1">OCHA (TEA)</text>
    </svg>`;
  } else if (r === 'ka') {
    return `<svg width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px;">
      <path d="M30,65 C30,40 90,40 90,65 Z" fill="var(--red)" opacity="0.8" stroke="#fff" stroke-width="1.5"/>
      <line x1="60" y1="65" x2="60" y2="85" stroke="#fff" stroke-width="2"/>
      <path d="M60,85 Q65,90 70,85" stroke="#fff" stroke-width="2" fill="none"/>
      <text x="60" y="32" font-size="10" fill="var(--text2)" font-weight="700" text-anchor="middle" letter-spacing="1">KASA (UMBRELLA)</text>
    </svg>`;
  } else if (r === 'neko' || r === 'ne') {
    return `<svg width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px;">
      <polygon points="40,50 30,30 55,45" fill="var(--amber)"/>
      <polygon points="80,50 90,30 65,45" fill="var(--amber)"/>
      <circle cx="60" cy="65" r="25" fill="var(--card4)" stroke="var(--border2)" stroke-width="2"/>
      <circle cx="50" cy="60" r="3" fill="#fff"/>
      <circle cx="70" cy="60" r="3" fill="#fff"/>
      <line x1="30" y1="65" x2="45" y2="65" stroke="var(--text3)" stroke-width="1.5"/>
      <line x1="90" y1="65" x2="75" y2="65" stroke="var(--text3)" stroke-width="1.5"/>
      <polygon points="58,66 62,66 60,69" fill="var(--red)"/>
      <text x="60" y="105" font-size="10" fill="var(--text2)" font-weight="700" text-anchor="middle" letter-spacing="1">NEKO (CAT)</text>
    </svg>`;
  } else {
    // Dynamic Typography Badge for all other characters!
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
}"""
    
    content = re.sub(pattern, new_func, content, flags=re.DOTALL)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)

merge_svgs()
