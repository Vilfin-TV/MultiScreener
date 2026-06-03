import re

def apply_cloudflare_images():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Replace the getKanaSvgVisual function entirely
    pattern = r'function getKanaSvgVisual\(romaji, wordStr\)\s*\{.*?return `<svg.*?<\/svg>`;\n\}'
    
    new_func = """// Set this to your Cloudflare R2 Bucket / Images URL
const CF_KANA_IMG_BASE = 'https://your-cloudflare-bucket.com/kana/';

function getKanaSvgVisual(romaji, wordStr) {
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

  // Create the dynamic typographic SVG to use as a fallback if the Cloudflare image fails to load
  const fallbackSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="110" height="110" viewBox="0 0 120 120" style="background:#060f1c; border-radius:8px; border:1px solid #1a2b4c; display:block; margin:0 auto 12px;">
    <circle cx="60" cy="50" r="38" fill="#112240" stroke="#1a2b4c" stroke-width="1"/>
    <text x="60" y="64" font-size="34" fill="#ffffff" font-weight="bold" text-anchor="middle">${mainVisual}</text>
    <text x="60" y="106" font-size="9" fill="#8892b0" font-weight="700" text-anchor="middle" letter-spacing="0.5">${subText}</text>
  </svg>`;
  
  const encodedFallback = encodeURIComponent(fallbackSvg);
  const imgUrl = `${CF_KANA_IMG_BASE}${romaji.toLowerCase()}.svg`;
  
  return `<img 
    src="${imgUrl}" 
    alt="${subText}"
    style="width:110px; height:110px; border-radius:8px; border:1px solid var(--border2); display:block; margin:0 auto 12px; object-fit:cover; background:#060f1c;"
    onerror="this.onerror=null; this.outerHTML=decodeURIComponent('${encodedFallback}');"
  />`;
}"""
    
    content = re.sub(pattern, new_func, content, flags=re.DOTALL)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)

apply_cloudflare_images()
