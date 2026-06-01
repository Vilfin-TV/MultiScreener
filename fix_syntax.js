const fs = require('fs');
let html = fs.readFileSync('education.html', 'utf8');
const searchString = "onclick=\\"nextLessonPage(\\\\'\\\\' + _activeLessonTab + \\\\'\\\\')\\"";
const replaceString = "onclick=\\"nextLessonPage('\\'' + _activeLessonTab + '\\'')\\"";
html = html.replace(searchString, replaceString);
fs.writeFileSync('education.html', html);
console.log('Fixed');
