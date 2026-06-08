const fs = require('fs');
const content = fs.readFileSync('index.html', 'utf8');

const scriptRegex = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;
let m;
let scripts = [];
while ((m = scriptRegex.exec(content)) !== null) {
  if (!m[0].includes('application/ld+json')) {
    scripts.push(m[1]);
  }
}
fs.writeFileSync('scratch/test_all.js', scripts.join('\n\n'));
console.log('Saved to scratch/test_all.js');
