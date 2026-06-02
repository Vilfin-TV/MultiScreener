const fs = require('fs');
const html = fs.readFileSync('education.html', 'utf8');
const scriptMatch = html.match(/<script>(.*?)<\/script>/s);
if (scriptMatch) {
  fs.writeFileSync('check.js', scriptMatch[1]);
  console.log('check.js written');
} else {
  // Try finding the last script tag
  const scripts = html.match(/<script>([\s\S]*?)<\/script>/g);
  if (scripts) {
    const last = scripts[scripts.length - 1];
    fs.writeFileSync('check.js', last.replace(/<\/?script>/g, ''));
    console.log('check.js written');
  } else {
    console.log('No script found');
  }
}
