const fs = require('fs');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;

const html = fs.readFileSync('education.html', 'utf8');

const dom = new JSDOM(html, { runScripts: "dangerously" });
const window = dom.window;

// Wait a bit for scripts to execute
setTimeout(() => {
  try {
    console.log("Active Hub: ", window._activeHub);
    console.log("Active JLPT Level: ", window._activeJlptLevel);
    
    // Switch to JLPT
    window.switchHub('jlpt');
    console.log("Switched to JLPT Hub.");
    
    // Call openMocTestModal
    window.openMocTestModal();
    console.log("MOC Modal Active Class:", window.document.getElementById('moc-modal-overlay').classList.contains('active'));
    console.log("MOC Title:", window.document.getElementById('moc-title').innerHTML);
    
    // Check questions rendered
    const bodyContent = window.document.getElementById('moc-body-content').innerHTML;
    console.log("MOC Questions Rendered Length:", bodyContent.length);
    
  } catch (err) {
    console.error("Error during MOC test logic:", err);
  }
}, 500);
