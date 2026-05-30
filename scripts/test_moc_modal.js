const fs = require('fs');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;

const html = fs.readFileSync('C:\\\\Users\\\\Vilfiin\\\\Downloads\\\\Multi Screener\\\\education.html', 'utf8');
const dom = new JSDOM(html, { runScripts: "dangerously" });

try {
  dom.window.eval(`
    _activeJlptLevel = 5;
    try {
      openMocTestModal();
      console.log('MOC Test opened successfully!');
      console.log('Questions rendered:', _mocQuestions.length);
    } catch (e) {
      console.error('Error opening MOC test:', e.message);
      console.error(e.stack);
    }
  `);
} catch (e) {
  console.error("JSDOM eval failed:", e);
}
