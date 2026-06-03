import os

def update_html():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update CSS to include Footer styles
    css_to_add = """
/* Footer Styles */
.story-footer { margin-top: 60px; background: #21242c; padding: 48px 20px 20px; color: #fff; }
.footer-main { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 2fr 1fr 1.5fr 1.5fr; gap: 40px; }
@media(max-width: 900px) { .footer-main { grid-template-columns: 1fr 1fr; } }
@media(max-width: 500px) { .footer-main { grid-template-columns: 1fr; } }
.footer-col-title { font-family: 'Bebas Neue', sans-serif; font-size: 20px; letter-spacing: 1.5px; margin-bottom: 16px; color: #fff; }
.footer-brand-desc { color: #a4a7b0; font-size: 15px; max-width: 280px; }
.footer-links { list-style: none; padding: 0; }
.footer-links li { margin-bottom: 10px; }
.footer-links a { color: #a4a7b0; font-size: 15px; transition: color 0.2s; }
.footer-links a:hover { color: #fff; }
.footer-bottom { max-width: 1200px; margin: 32px auto 0; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 14px; color: #a4a7b0; flex-wrap: wrap; gap: 12px; }
</style>"""
    content = content.replace("</style>", css_to_add)

    # 2. Replace Navigation
    old_nav = """<!-- Top Navigation -->
<nav class="top-menubar">
  <div class="nav-inner">
    <div class="nav-brand-group">
      <div class="nav-brand">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>
        VilfinTV Academy
      </div>
      <div class="nav-links">
        <a href="index.html">Dashboard</a>
        <a href="news.html">News</a>
        <a href="story.html">Stories</a>
      </div>
    </div>
  </div>
</nav>"""
    
    new_nav = """<!-- Top Navigation -->
<nav class="top-menubar">
  <div class="nav-inner">
    <div class="nav-brand-group">
      <div class="nav-brand">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>
        VilfinTV Academy
      </div>
      <div class="nav-links">
        <a href="index.html">Home</a>
        <a href="news.html">News</a>
        <a href="story.html">Stories</a>
        <a href="blog_intelligence_hub.html">Blog</a>
      </div>
    </div>
    <div style="font-size: 14px; color: #3b3e46; font-weight: 500;">
      Already have a VilfinTV account? <a href="#" style="color:#1865f2; font-weight: 600; margin-left: 4px;">Log in</a>
    </div>
  </div>
</nav>"""
    content = content.replace(old_nav, new_nav)

    # 3. Replace Hero Section
    old_hero = """<!-- Hero Section -->
<div class="hero-section" id="hero-section">
  <div>
    <h1 class="hero-title">VilfinTV Academy boosts scores!</h1>
    <p class="hero-subtitle">Learn with structured courses, tackling practice problems, and exploring robust educational content.</p>
    <!-- Placeholder for Hero Image -->
    <div style="width:100%; height:250px; background: #e2e2e2; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #888;">
      [ Hero Image Placeholder ]
    </div>
  </div>
  <div>
    <h2 class="hero-card-title">Start learning today!</h2>
    <div class="hero-cards-container">
      <a href="#" class="user-card" onclick="return false;">
        I'm a learner <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
      </a>
      <a href="#" class="user-card" onclick="return false;">
        I'm a teacher <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
      </a>
      <a href="#" class="user-card" onclick="return false;">
        I'm a parent <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
      </a>
    </div>
    <div style="margin-top: 16px; font-size: 14px;">
      Already have a VilfinTV account? <a href="#" style="color:#1865f2; font-weight: 600;">Log in</a>
    </div>
  </div>
</div>"""

    new_hero = """<!-- Hero Section -->
<div class="hero-section" id="hero-section" style="grid-template-columns: 1fr 1fr; align-items: center;">
  <div>
    <h1 class="hero-title">VilfinTV Academy boosts scores!</h1>
    <p class="hero-subtitle" style="font-size: 18px; margin-bottom: 24px; color: #3b3e46; max-width: 480px;">Learn with structured courses, tackling practice problems, and exploring robust educational content.</p>
  </div>
  <div style="display: flex; justify-content: center;">
    <img src="academy_hero.png" alt="Students learning joyfully" style="max-width: 100%; height: auto; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.1);" />
  </div>
</div>"""
    content = content.replace(old_hero, new_hero)

    # 4. Add Footer
    footer_html = """
<!-- Footer -->
<footer class="story-footer">
  <div class="footer-main">
    <div>
      <div class="footer-col-title">VilfinTV Academy</div>
      <p class="footer-brand-desc">Interactive curriculum study, practical STEM tools, and robust Asian languages training.</p>
    </div>
    <div>
      <div class="footer-col-title">CBSE Hub</div>
      <ul class="footer-links">
        <li><a href="#" onclick="openCbseLesson('math', 10); return false;">Class 10 CBSE Notes</a></li>
        <li><a href="#" onclick="openCbseLesson('math', 9); return false;">Class 9 CBSE Notes</a></li>
        <li><a href="#" onclick="openCbseLesson('math', 8); return false;">Class 8 CBSE Notes</a></li>
        <li><a href="#" onclick="openCbseLesson('math', 7); return false;">Class 7 CBSE Notes</a></li>
      </ul>
    </div>
    <div>
      <div class="footer-col-title">Japanese Hub</div>
      <ul class="footer-links">
        <li><a href="#" onclick="openJlpt(5); return false;">JLPT N5 vocabulary</a></li>
        <li><a href="#" onclick="openJlpt(4); return false;">JLPT N4 Kanji Drills</a></li>
        <li><a href="#" onclick="openJlpt(3); return false;">JLPT N3 Formal Polite</a></li>
        <li><a href="#" onclick="openJlpt(1); return false;">JLPT N1 Classical particles</a></li>
      </ul>
    </div>
    <div>
      <div class="footer-col-title">VilfinTV Platform</div>
      <ul class="footer-links">
        <li><a href="index.html">&#x1F4CA; MultiScreener Dashboard</a></li>
        <li><a href="news.html">&#x1F4FA; VilfinTV News</a></li>
        <li><a href="story.html">&#x1F4D6; VilfinTV Stories</a></li>
        <li><a href="blog_intelligence_hub.html" target="_blank">&#x1F4F0; Blog Intelligence Hub</a></li>
      </ul>
    </div>
  </div>

  <div class="footer-bottom">
    <p>&copy; 2026 VilfinTV Academy. NCERT &amp; JLPT curriculum resources updated in real time.</p>
    <p>Institutional-Grade Education Hub</p>
  </div>
</footer>
"""
    
    # Insert footer right before Navigation Logic script
    script_pos = content.find('<!-- Navigation Logic -->')
    if script_pos != -1:
        content = content[:script_pos] + footer_html + content[script_pos:]
    else:
        print("Could not find Navigation Logic marker!")

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("education.html successfully updated with requested adjustments.")

update_html()
