const fs = require('fs');
let html = fs.readFileSync('education.html', 'utf8');

const startIndex = html.indexOf('const JLPT_DATA = {');
const endIndex = html.indexOf('// RENDER CBSE CONTENT');

if (startIndex === -1 || endIndex === -1) {
    console.error('Could not find boundaries');
    process.exit(1);
}

// 1. Replace the hardcoded data with let JLPT_DATA = {};
const before = html.substring(0, startIndex);
const after = html.substring(endIndex);

html = before + 'let JLPT_DATA = {};\n\n' + after;

// 2. Refactor switchJlptLevel
const oldSwitch = `function switchJlptLevel(lvl) {
  _activeJlptLevel = lvl;
  document.querySelectorAll('.jlpt-container .class-btn').forEach(btn => {
    btn.classList.remove('active');
    if (parseInt(btn.getAttribute('data-jlpt')) === lvl) btn.classList.add('active');
  });
  renderJlptContent();
}`;

const newSwitch = `async function switchJlptLevel(lvl) {
  _activeJlptLevel = lvl;
  document.querySelectorAll('.jlpt-container .class-btn').forEach(btn => {
    btn.classList.remove('active');
    if (parseInt(btn.getAttribute('data-jlpt')) === lvl) btn.classList.add('active');
  });
  
  if (!JLPT_DATA[lvl]) {
    document.getElementById('jlpt-lesson-card').innerHTML = '<p>Loading N' + lvl + ' data...</p>';
    try {
      const res = await fetch('jlpt_n' + lvl + '.json');
      if (!res.ok) throw new Error('Network response was not ok');
      JLPT_DATA[lvl] = await res.json();
    } catch (e) {
      console.error('Error fetching JLPT data:', e);
      document.getElementById('jlpt-lesson-card').innerHTML = '<p>Error loading N' + lvl + ' data.</p>';
      return;
    }
  }
  
  renderJlptContent();
}`;

html = html.replace(oldSwitch, newSwitch);

fs.writeFileSync('education.html', html);
console.log('education.html successfully refactored.');
