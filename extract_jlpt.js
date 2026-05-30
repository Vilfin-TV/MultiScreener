const fs = require('fs');
const html = fs.readFileSync('education.html', 'utf8');

const startIndex = html.indexOf('const JLPT_DATA = {');
const endIndex = html.indexOf('// RENDER CBSE CONTENT');

if (startIndex === -1 || endIndex === -1) {
    console.error('Could not find boundaries');
    process.exit(1);
}

// Get the substring
let rawStr = html.substring(startIndex, endIndex).trim();
// Strip trailing semicolons or anything after the main object
rawStr = rawStr.replace(/^const JLPT_DATA = /, 'module.exports = ');

const vm = require('vm');
const sandbox = { module: {} };
vm.createContext(sandbox);

try {
    vm.runInContext(rawStr, sandbox);
    const jlptData = sandbox.module.exports;
    if (!jlptData) {
        console.error('module.exports is undefined after eval!');
        process.exit(1);
    }
    
    [1, 2, 3, 4, 5].forEach(level => {
        if (jlptData[level]) {
            fs.writeFileSync(`jlpt_n${level}.json`, JSON.stringify(jlptData[level], null, 2));
            console.log(`Saved jlpt_n${level}.json`);
        } else {
            console.warn(`No data for N${level}`);
        }
    });
} catch(e) {
    console.error('Eval error:', e);
}
