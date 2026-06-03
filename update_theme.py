import re

def add_themes():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Define the new CSS with CSS variables
    new_css = """
:root {
  --bg: #ffffff;
  --text: #21242c;
  --text2: #3b3e46;
  --border: #e2e2e2;
  --card: #f7f7f8;
  --card-hover: #ebf2ff;
  --blue: #1865f2;
  --green: #14bf96;
  --footer-bg: #21242c;
  --footer-text: #a4a7b0;
}

[data-theme="midnight"] {
  --bg: #0a192f;
  --text: #e6f1ff;
  --text2: #8892b0;
  --border: #233554;
  --card: #112240;
  --card-hover: #1e3a6a;
  --blue: #3b82f6;
  --green: #14bf96;
  --footer-bg: #020c1b;
  --footer-text: #8892b0;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', 'DM Sans', sans-serif;
  background-color: var(--bg);
  color: var(--text);
  line-height: 1.5;
  padding-bottom: 60px;
  transition: background-color 0.3s, color 0.3s;
}
a { color: inherit; text-decoration: none; transition: color 0.2s ease; }
button { font-family: inherit; cursor: pointer; transition: all 0.2s ease; }

/* Top Navbar */
.top-menubar {
  position: sticky; top: 0; z-index: 1000;
  height: 60px; background-color: var(--bg);
  border-bottom: 1px solid var(--border);
  transition: background-color 0.3s, border-color 0.3s;
}
.nav-inner {
  max-width: 1200px; margin: 0 auto; height: 100%;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px;
}
.nav-brand-group { display: flex; align-items: center; gap: 24px; }
.nav-brand {
  display: flex; align-items: center; gap: 8px;
  font-size: 20px; font-weight: 700; color: var(--green);
}
.nav-links {
  display: flex; align-items: center; gap: 16px; font-weight: 600; color: var(--text2); font-size: 15px;
}
.nav-links a:hover { color: var(--green); }
.story-theme-btn {
  background: transparent; border: none; font-size: 22px; cursor: pointer;
  padding: 4px; border-radius: 4px; transition: background 0.2s;
}
.story-theme-btn:hover { background: var(--card); }

/* Hero Section */
.hero-section {
  max-width: 1200px; margin: 48px auto; padding: 0 20px;
  display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: center;
}
@media(max-width: 900px) {
  .hero-section { grid-template-columns: 1fr; text-align: center; }
}
.hero-title {
  font-size: 42px; font-weight: 700; color: var(--text); margin-bottom: 16px; line-height: 1.1;
  font-family: 'Playfair Display', serif;
}
.hero-subtitle {
  font-size: 18px; color: var(--text2); margin-bottom: 32px;
}

/* Subjects Grid Section */
.subjects-section {
  background-color: var(--card);
  padding: 48px 20px; border-top: 1px solid var(--border);
  transition: background-color 0.3s, border-color 0.3s;
}
.subjects-inner {
  max-width: 1200px; margin: 0 auto;
}
.subjects-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 32px;
}
.subject-card {
  display: flex; flex-direction: column;
}
.subject-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
  padding-bottom: 8px; border-bottom: 2px solid var(--border);
}
.subject-icon {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; color: white; flex-shrink: 0;
}
.subject-title {
  font-size: 18px; font-weight: 700; color: var(--text);
}
.subject-links {
  display: flex; flex-direction: column; gap: 12px;
}
.subject-links a {
  font-size: 15px; color: var(--blue); font-weight: 600;
  display: flex; justify-content: space-between; align-items: center;
}
.subject-links a:hover {
  text-decoration: underline;
}

/* Colors for Subject Icons */
.icon-social { background: #d92916; }
.icon-econ { background: #e07d10; }
.icon-math-hs { background: #db4d8b; }
.icon-math-pk { background: #ff9200; }
.icon-language { background: #9059ff; }
.icon-life { background: #00a699; }
.icon-science { background: var(--green); }
.icon-cs { background: var(--blue); }

/* Lesson View Container */
.lesson-view-container {
  display: none; max-width: 1200px; margin: 40px auto; padding: 0 20px;
}
.back-btn {
  background: transparent; border: 1px solid var(--blue); color: var(--blue);
  font-weight: 600; padding: 8px 16px; border-radius: 4px; margin-bottom: 24px;
}
.back-btn:hover { background: var(--blue); color: white; }
.lesson-content-wrapper {
  background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 32px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

/* Reused Classes */
.subject-tab-bar { display: none; }
.class-selector-bar {
  display: flex; overflow-x: auto; gap: 8px; padding-bottom: 12px;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent; margin-bottom: 16px;
}
.class-btn {
  flex-shrink: 0; background: var(--card); border: 1px solid var(--border);
  color: var(--text2); font-size: 14px; font-weight: 600;
  padding: 8px 16px; border-radius: 20px; cursor: pointer;
  transition: all 0.2s ease;
}
.class-btn.active {
  background: var(--blue); border-color: var(--blue); color: #fff;
}
.study-lead { font-size: 18px; font-weight: 700; color: var(--blue); margin-bottom: 12px; }
.study-bullets { margin-left: 20px; margin-bottom: 16px; }
.study-bullets li { margin-bottom: 8px; }
.qa-item { border-bottom: 1px solid var(--border); padding: 12px 0; }
.qa-question { font-weight: 600; cursor: pointer; color: var(--text); }
.qa-answer { display: none; margin-top: 8px; color: var(--text2); border-left: 3px solid var(--green); padding-left: 12px; }
.qa-item.active .qa-answer { display: block; }
.section-headline { font-size: 24px; font-weight: 700; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.option-btn { border: 1px solid var(--border); padding: 10px; border-radius: 4px; background: var(--bg); margin-bottom: 8px; display: block; width: 100%; text-align: left; color: var(--text); }
.option-btn:hover { background: var(--card); }
.option-btn.correct { background: #e0f6e6; border-color: var(--green); color: #21242c; }
.option-btn.incorrect { background: #fce2e2; border-color: #d92916; color: #21242c; }

/* JLPT specifics */
.sub-hub-bar { display: flex; gap: 12px; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 12px; overflow-x: auto; }
.sub-hub-btn { background: var(--card); border: 1px solid var(--border); padding: 8px 16px; border-radius: 16px; font-weight: 600; font-size: 14px; color: var(--text2); }
.sub-hub-btn.active { background: var(--blue); color: white; border-color: var(--blue); }
.kana-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.kana-card { border: 1px solid var(--border); border-radius: 8px; text-align: center; padding: 12px; cursor: pointer; background: var(--bg); }
.kana-card:hover { border-color: var(--blue); }
.kana-card.active { background: var(--card-hover); border-color: var(--blue); }
.kana-char { font-size: 24px; font-weight: 700; }
.kana-layout { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }
@media(max-width:800px){ .kana-layout { grid-template-columns: 1fr; } }
.kana-details-box { border: 1px solid var(--border); padding: 20px; border-radius: 8px; background: var(--bg); }

/* Footer Styles */
.story-footer { margin-top: 60px; background: var(--footer-bg); padding: 48px 20px 20px; color: #fff; }
.footer-main { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 2fr 1fr 1.5fr 1.5fr; gap: 40px; }
@media(max-width: 900px) { .footer-main { grid-template-columns: 1fr 1fr; } }
@media(max-width: 500px) { .footer-main { grid-template-columns: 1fr; } }
.footer-col-title { font-family: 'Bebas Neue', sans-serif; font-size: 20px; letter-spacing: 1.5px; margin-bottom: 16px; color: #fff; }
.footer-brand-desc { color: var(--footer-text); font-size: 15px; max-width: 280px; }
.footer-links { list-style: none; padding: 0; }
.footer-links li { margin-bottom: 10px; }
.footer-links a { color: var(--footer-text); font-size: 15px; transition: color 0.2s; }
.footer-links a:hover { color: #fff; }
.footer-bottom { max-width: 1200px; margin: 32px auto 0; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 14px; color: var(--footer-text); flex-wrap: wrap; gap: 12px; }
"""

    # Replace everything between /* ==========================================================================
    # KHAN ACADEMY STYLE RESET & BASE
    # ========================================================================== */
    # and </style>
    start_str = "/* ==========================================================================\n   KHAN ACADEMY STYLE RESET & BASE\n   ========================================================================== */"
    
    start_idx = content.find(start_str)
    end_idx = content.find("</style>")
    
    if start_idx != -1 and end_idx != -1:
        content = content[:start_idx] + new_css + content[end_idx:]
    else:
        print("Could not find CSS boundaries!")
        
    # Update HTML header to add theme button
    old_nav_right = """<div style="font-size: 14px; color: #3b3e46; font-weight: 500;">
      Already have a VilfinTV account? <a href="#" style="color:#1865f2; font-weight: 600; margin-left: 4px;">Log in</a>
    </div>"""
    new_nav_right = """<div style="display: flex; align-items: center; gap: 16px;">
      <button class="story-theme-btn" onclick="cycleTheme()" title="Change theme">&#x1F3A8;</button>
      <div style="font-size: 14px; color: var(--text2); font-weight: 500;">
        Already have a VilfinTV account? <a href="#" style="color:var(--blue); font-weight: 600; margin-left: 4px;">Log in</a>
      </div>
    </div>"""
    content = content.replace(old_nav_right, new_nav_right)
    
    # Update JS for cycleTheme
    old_js = """function cycleTheme() {
  var cur = localStorage.getItem('viltv_theme') || 'midnight';
  var idx = THEMES.indexOf(cur);
  var next = THEMES[(idx + 1) % THEMES.length];
  setTheme(next);
}"""
    new_js = """function cycleTheme() {
  var cur = document.documentElement.getAttribute('data-theme') || 'khan';
  var next = (cur === 'khan') ? 'midnight' : 'khan';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('viltv_theme', next);
}

// Set initial theme
var savedTheme = localStorage.getItem('viltv_theme') || 'khan';
document.documentElement.setAttribute('data-theme', savedTheme);
"""
    content = content.replace(old_js, new_js)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print("Theme styling added successfully!")

add_themes()
