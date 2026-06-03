import os

def fix_open_functions():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix openJlpt
    old_jlpt = """function openJlpt(level) {
  document.getElementById('hero-section').style.display = 'none';
  document.getElementById('subjects-section').style.display = 'none';
  document.getElementById('lesson-view-container').style.display = 'block';
  
  document.getElementById('cbse-content-area').style.display = 'none';
  document.getElementById('jlpt-content-area').style.display = 'block';
  
  _activeHub = 'jlpt';"""

    new_jlpt = """function openJlpt(level) {
  document.getElementById('hero-section').style.display = 'none';
  document.getElementById('subjects-section').style.display = 'none';
  document.getElementById('lesson-view-container').style.display = 'block';
  
  document.getElementById('cbse-content-area').style.display = 'none';
  document.getElementById('jlpt-content-area').style.display = 'block';
  
  const jCont = document.getElementById('jlpt-container');
  if (jCont) jCont.style.display = 'block';
  
  _activeHub = 'jlpt';"""

    content = content.replace(old_jlpt, new_jlpt)

    # Fix openCbseLesson
    old_cbse = """function openCbseLesson(subject, classNum) {
  document.getElementById('hero-section').style.display = 'none';
  document.getElementById('subjects-section').style.display = 'none';
  document.getElementById('lesson-view-container').style.display = 'block';
  
  document.getElementById('jlpt-content-area').style.display = 'none';
  document.getElementById('cbse-content-area').style.display = 'block';
  
  _activeHub = 'cbse';"""

    new_cbse = """function openCbseLesson(subject, classNum) {
  document.getElementById('hero-section').style.display = 'none';
  document.getElementById('subjects-section').style.display = 'none';
  document.getElementById('lesson-view-container').style.display = 'block';
  
  document.getElementById('jlpt-content-area').style.display = 'none';
  document.getElementById('cbse-content-area').style.display = 'block';
  
  const cCont = document.getElementById('cbse-container');
  if (cCont) cCont.style.display = 'block';
  
  _activeHub = 'cbse';"""

    content = content.replace(old_cbse, new_cbse)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)

fix_open_functions()
