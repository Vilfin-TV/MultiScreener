import os

def fix_js_errors():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix switchHub
    old_sh = """function switchHub(hub) {
  _activeHub = hub;
  document.getElementById('toggle-cbse').classList.remove('active');
  document.getElementById('toggle-jlpt').classList.remove('active');
  
  if (hub === 'cbse') {
    document.getElementById('toggle-cbse').classList.add('active');
    document.getElementById('cbse-container').style.display = 'block';
    document.getElementById('jlpt-container').style.display = 'none';
    renderCbseContent();
  } else {
    document.getElementById('toggle-jlpt').classList.add('active');
    document.getElementById('cbse-container').style.display = 'none';
    document.getElementById('jlpt-container').style.display = 'block';
    switchJlptLevel(_activeJlptLevel);
  }
}"""

    new_sh = """function switchHub(hub) {
  _activeHub = hub;
  const tCbse = document.getElementById('toggle-cbse');
  const tJlpt = document.getElementById('toggle-jlpt');
  
  if (tCbse) tCbse.classList.remove('active');
  if (tJlpt) tJlpt.classList.remove('active');
  
  if (hub === 'cbse') {
    if (tCbse) tCbse.classList.add('active');
    const cCont = document.getElementById('cbse-container');
    if (cCont) cCont.style.display = 'block';
    const jCont = document.getElementById('jlpt-container');
    if (jCont) jCont.style.display = 'none';
    if (typeof renderCbseContent === 'function') renderCbseContent();
  } else {
    if (tJlpt) tJlpt.classList.add('active');
    const cCont = document.getElementById('cbse-container');
    if (cCont) cCont.style.display = 'none';
    const jCont = document.getElementById('jlpt-container');
    if (jCont) jCont.style.display = 'block';
    if (typeof switchJlptLevel === 'function') switchJlptLevel(_activeJlptLevel);
  }
}"""

    content = content.replace(old_sh, new_sh)
    
    # Also fix DOMContentLoaded to ensure loadKanaRecallDrill runs even if switchHub fails
    old_dom = """// Initialize Hub
document.addEventListener('DOMContentLoaded', function() {
  setTheme(localStorage.getItem('viltv_theme') || 'midnight');
  switchHub('cbse');
  // Initialize recall game
  loadKanaRecallDrill();
  loadKanjiGame();
  // Load admin notices
  _loadAcademyNotices();
});"""

    new_dom = """// Initialize Hub
document.addEventListener('DOMContentLoaded', function() {
  try { setTheme(localStorage.getItem('viltv_theme') || 'midnight'); } catch(e){}
  try { switchHub('cbse'); } catch(e){}
  // Initialize recall game
  try { loadKanaRecallDrill(); } catch(e){ console.error(e); }
  try { loadKanjiGame(); } catch(e){ console.error(e); }
  // Load admin notices
  try { _loadAcademyNotices(); } catch(e){}
});"""

    content = content.replace(old_dom, new_dom)
    
    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Fixed JS errors!")

fix_js_errors()
