import os

def update_language_card():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update CSS
    old_css = ".class-selector-bar, .subject-tab-bar { display: none; } /* Hide the old tabs in new view */"
    new_css = """
.subject-tab-bar { display: none; } /* We keep subject tabs hidden since subjects are on home grid */
.class-selector-bar {
  display: flex; overflow-x: auto; gap: 8px; padding-bottom: 12px;
  scrollbar-width: thin; scrollbar-color: #e2e2e2 transparent; margin-bottom: 16px;
}
.class-btn {
  flex-shrink: 0; background: #f7f7f8; border: 1px solid #e2e2e2;
  color: #3b3e46; font-size: 14px; font-weight: 600;
  padding: 8px 16px; border-radius: 20px; cursor: pointer;
  transition: all 0.2s ease;
}
.class-btn.active {
  background: #1865f2; border-color: #1865f2; color: #fff;
}
"""
    content = content.replace(old_css, new_css)

    # 2. Update Language Card
    old_lang = """<a href="#" onclick="openCbseLesson('english', 5); return false;">Class 5 English</a>
          <a href="#" onclick="openCbseLesson('english', 10); return false;">Class 10 English</a>
          <a href="#" onclick="openCbseLesson('hindi', 5); return false;">Class 5 Hindi</a>
          <a href="#" onclick="openCbseLesson('hindi', 10); return false;">Class 10 Hindi</a>
          <a href="#" onclick="openJlpt(5); return false;">Japanese JLPT N5</a>
          <a href="#" onclick="openJlpt(4); return false;">Japanese JLPT N4</a>
          <a href="#" onclick="openJlpt(3); return false;">Japanese JLPT N3</a>
          <a href="#" onclick="openJlpt(2); return false;">Japanese JLPT N2</a>
          <a href="#" onclick="openJlpt(1); return false;">Japanese JLPT N1</a>"""

    new_lang = """<a href="#" onclick="openJlpt(5); return false;">Japanese</a>
          <a href="#" onclick="openCbseLesson('english', 10); return false;">English</a>
          <a href="#" onclick="openCbseLesson('hindi', 10); return false;">Hindi</a>
          <a href="#" onclick="alert('Coming Soon'); return false;">Malayalam</a>
          <a href="#" onclick="alert('Coming Soon'); return false;">French</a>
          <a href="#" onclick="alert('Coming Soon'); return false;">Chinese</a>
          <a href="#" onclick="alert('Coming Soon'); return false;">Spanish</a>"""
    
    content = content.replace(old_lang, new_lang)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Language card and CSS successfully updated.")

update_language_card()
