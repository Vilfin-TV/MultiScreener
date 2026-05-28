const fs = require('fs');
const path = require('path');
const vm = require('vm');

const eduPath = path.join(__dirname, '..', 'education.html');
console.log(`🔍 Checking syntax of inline JavaScript in ${eduPath}...`);
const html = fs.readFileSync(eduPath, 'utf8');

// Regex to extract all content inside <script> tags
const scriptRegex = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;
let match;
let scriptIndex = 1;
let syntaxErrors = 0;

while ((match = scriptRegex.exec(html)) !== null) {
  const code = match[1].trim();
  if (code.length === 0) continue;
  
  try {
    // Compile the script (does not execute, just checks syntax)
    new vm.Script(code, { filename: `education.html [Script ${scriptIndex}]` });
    console.log(`  ✅ Script tag ${scriptIndex} syntax is completely clean.`);
  } catch (e) {
    console.error(`  ❌ Syntax error in Script tag ${scriptIndex}:`, e.message);
    syntaxErrors++;
  }
  scriptIndex++;
}

if (syntaxErrors > 0) {
  console.error(`❌ Validation failed: Found ${syntaxErrors} syntax error(s) in education.html script tags.`);
  process.exit(1);
} else {
  console.log('🎉 Syntax check passed perfectly! No syntax errors in education.html inline scripts.');
  process.exit(0);
}
