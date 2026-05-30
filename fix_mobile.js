const fs = require('fs');

// 1. Update education.html fonts and MOC test link
let eduHtml = fs.readFileSync('education.html', 'utf8');

// Increase small fonts
eduHtml = eduHtml.replace(/font-size:11px/g, 'font-size:13px');
eduHtml = eduHtml.replace(/font-size:12px/g, 'font-size:14px');
eduHtml = eduHtml.replace(/font-size:13px/g, 'font-size:15px');
eduHtml = eduHtml.replace(/font-size:13\.5px/g, 'font-size:16px');
eduHtml = eduHtml.replace(/font-size:14px/g, 'font-size:16px');

// Change window.open to window.location.assign
eduHtml = eduHtml.replace(
  "const popup = window.open('moc_test.html', 'JLPT_MOC_TEST', 'width=900,height=800,scrollbars=yes,resizable=yes');",
  "window.location.assign('moc_test.html');\n    const popup = true; // bypass old blocked popup logic"
);

// Bust cache again just in case
eduHtml = eduHtml.replace(/jlpt_textbook_data\.js\?v=\d+/, 'jlpt_textbook_data.js?v=' + Date.now());
fs.writeFileSync('education.html', eduHtml);

// 2. Update moc_test.html
let mocHtml = fs.readFileSync('moc_test.html', 'utf8');

// Add viewport
mocHtml = mocHtml.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">');

// Increase small fonts
mocHtml = mocHtml.replace(/font-size:12px/g, 'font-size:14px');
mocHtml = mocHtml.replace(/font-size:13px/g, 'font-size:15px');
mocHtml = mocHtml.replace(/font-size:14px/g, 'font-size:16px');

// Add a back button in the header
const headerTarget = '<h1 id="test-title">JLPT MOC Test</h1>';
const newHeader = '<h1 id="test-title" style="font-size:22px;">JLPT MOC Test</h1>\n    <button onclick="window.location.assign(\\'education.html\\')" style="background:var(--red); color:#fff; border:none; padding:8px 12px; border-radius:4px; font-weight:bold; cursor:pointer;">Exit</button>';
mocHtml = mocHtml.replace(headerTarget, newHeader);

// Fix the timer layout to fit the exit button
const timerTarget = '<div class="timer" id="timer">00:00</div>';
const newTimer = '<div class="timer" id="timer" style="font-size:18px;">00:00</div>';
mocHtml = mocHtml.replace(timerTarget, newTimer);

// Add back button after submission
const submitLogic = 'document.getElementById(\\'submit-btn\\').style.display = \\'none\\';';
const newSubmitLogic = 'document.getElementById(\\'submit-btn\\').style.display = \\'none\\';\n      document.getElementById(\\'quiz-container\\').insertAdjacentHTML(\\'afterend\\', \\'<div style="text-align:center;margin-top:20px;"><button onclick="window.location.assign(\\\\'education.html\\\\')" class="btn" style="background:var(--green);">Return to Study Guide</button></div>\\');';
mocHtml = mocHtml.replace(submitLogic, newSubmitLogic);

fs.writeFileSync('moc_test.html', mocHtml);

console.log('Successfully fixed mobile fonts and MOC test navigation.');
