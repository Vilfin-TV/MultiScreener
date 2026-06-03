import re

def update_all_themes():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Themes to insert
    themes_css = """
[data-theme="default"] {
  --bg: #030810;
  --text: #e2eeff;
  --text2: #8ea8c8;
  --border: #162d4a;
  --card: #0a1830;
  --card-hover: #162d4a;
  --blue: #2563eb;
  --green: #10b981;
  --footer-bg: #060f1c;
  --footer-text: #8ea8c8;
}
[data-theme="standard"] {
  --bg: #f0f4f9;
  --text: #0f172a;
  --text2: #374151;
  --border: #dde3ed;
  --card: #ffffff;
  --card-hover: #edf2f9;
  --blue: #1d4ed8;
  --green: #10b981;
  --footer-bg: #e8edf5;
  --footer-text: #6b7280;
}
[data-theme="maroon"] {
  --bg: #0a0202;
  --text: #ffe2e2;
  --text2: #c89494;
  --border: #3a1414;
  --card: #250a0a;
  --card-hover: #3a1414;
  --blue: #ff7f7f;
  --green: #10b981;
  --footer-bg: #150505;
  --footer-text: #c89494;
}
[data-theme="silver"] {
  --bg: #f3f4f6;
  --text: #111827;
  --text2: #4b5563;
  --border: #e5e7eb;
  --card: #ffffff;
  --card-hover: #f3f4f6;
  --blue: #374151;
  --green: #10b981;
  --footer-bg: #e5e7eb;
  --footer-text: #4b5563;
}
[data-theme="gold"] {
  --bg: #0a0804;
  --text: #fffae8;
  --text2: #c8b387;
  --border: #352d19;
  --card: #201b0e;
  --card-hover: #352d19;
  --blue: #ffd700;
  --green: #10b981;
  --footer-bg: #141108;
  --footer-text: #c8b387;
}
[data-theme="gemini"] {
  --bg: #050310;
  --text: #f5e2ff;
  --text2: #bca8c8;
  --border: #1e144a;
  --card: #130b30;
  --card-hover: #1e144a;
  --blue: #f48fb1;
  --green: #10b981;
  --footer-bg: #09061c;
  --footer-text: #bca8c8;
}
* { box-sizing: border-box; margin: 0; padding: 0; }"""

    # Replace "* { box-sizing: border-box; margin: 0; padding: 0; }" with the themes CSS
    content = content.replace("* { box-sizing: border-box; margin: 0; padding: 0; }", themes_css)

    # JS logic update
    old_js = """function cycleTheme() {
  var cur = document.documentElement.getAttribute('data-theme') || 'khan';
  var next = (cur === 'khan') ? 'midnight' : 'khan';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('viltv_theme', next);
}"""

    new_js = """var THEMES = ['khan', 'default', 'standard', 'midnight', 'maroon', 'silver', 'gold', 'gemini'];
function cycleTheme() {
  var cur = document.documentElement.getAttribute('data-theme') || 'khan';
  var idx = THEMES.indexOf(cur);
  if (idx === -1) idx = 0;
  var next = THEMES[(idx + 1) % THEMES.length];
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('viltv_theme', next);
}"""

    content = content.replace(old_js, new_js)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("All 8 themes added successfully!")

update_all_themes()
