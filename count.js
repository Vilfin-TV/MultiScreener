const fs = require('fs');
const html = fs.readFileSync('education.html', 'utf8');
const dataStr = html.substring(html.indexOf('const JLPT_DATA'), html.indexOf('const CBSE_DATA'));
[1, 2, 3, 4, 5].forEach(lvl => {
  const lvlIdx = dataStr.indexOf(lvl + ': {');
  if (lvlIdx !== -1) {
    const quizzesIdx = dataStr.indexOf('quizzes: [', lvlIdx);
    if (quizzesIdx !== -1) {
      let nextLvlIdx = dataStr.indexOf((lvl-1) + ': {', lvlIdx);
      if(nextLvlIdx === -1) nextLvlIdx = dataStr.length;
      const chunk = dataStr.substring(quizzesIdx, nextLvlIdx);
      const count = (chunk.match(/\"q\":/g) || []).length;
      console.log('N' + lvl + ' quizzes count:', count);
    }
  }
});
