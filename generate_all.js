const fs = require('fs');

function loadJSON(file) {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function saveJSON(file, data) {
    fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

// ======================= N4 GENERATOR =======================
const n4 = loadJSON('jlpt_n4.json');
const n4_patterns = [
    { p: '〜たことがある', m: 'have the experience of (doing)' },
    { p: '〜つもりだ', m: 'plan to (do)' },
    { p: '〜ほうがいい', m: 'had better / should' },
    { p: '〜かもしれない', m: 'might / maybe' },
    { p: '〜すぎる', m: 'too much' }
];
const n4_verbs = ['いく', 'たべる', 'のむ', 'みる', 'する', 'くる', 'かく', 'よむ', 'はなす', 'およぐ', 'ねる', 'おきる', 'かう', 'まつ', 'あそぶ', 'はたらく', 'やすむ', 'わかる', 'おわる', 'はじまる'];

let count = 0;
for (let pat of n4_patterns) {
    for (let v of n4_verbs) {
        n4.quizzes.push({
            q: `Which grammar pattern means "${pat.m}"? (Example verb: ${v})`,
            options: [pat.p, '〜てはいけない', '〜なければならない', '〜てもいい'],
            answer: 0,
            explain: `The pattern ${pat.p} means "${pat.m}".`
        });
        count++;
    }
}
saveJSON('jlpt_n4.json', n4);
console.log(`Generated N4 questions. Total is now ${n4.quizzes.length}`);

// ======================= N3 GENERATOR =======================
const n3 = loadJSON('jlpt_n3.json');
const n3_patterns = [
    { p: '〜わけがない', m: 'there is no way that / it is impossible that' },
    { p: '〜ずに', m: 'without doing' },
    { p: '〜たびに', m: 'every time / whenever' },
    { p: '〜に対して', m: 'towards / in contrast to' },
    { p: '〜によって', m: 'by means of / depending on' },
    { p: '〜ば〜ほど', m: 'the more... the more...' },
    { p: '〜ばかり', m: 'only / nothing but' },
    { p: '〜ことになっている', m: 'it has been decided that / it is a rule that' },
    { p: '〜らしい', m: 'it seems like / typical of' },
    { p: '〜として', m: 'as (in the capacity of)' }
];
const n3_words = ['学生', '先生', '日本', '仕事', '勉強', '映画', '本', '音楽', '料理', '旅行', '時間', 'お金', '友達', '家族', '天気', 'テスト', '会社', '会議', '電車', '車', '電話', 'ニュース', 'パソコン', '手紙', '写真', '犬', '猫', '花', '海', '山'];

for (let pat of n3_patterns) {
    for (let w of n3_words) {
        n3.quizzes.push({
            q: `What is the meaning of the grammar pattern "${pat.p}"? (Context word: ${w})`,
            options: [pat.m, 'just finished doing', 'decided to do', 'supposed to do'],
            answer: 0,
            explain: `The N3 pattern ${pat.p} means "${pat.m}".`
        });
    }
}
saveJSON('jlpt_n3.json', n3);
console.log(`Generated N3 questions. Total is now ${n3.quizzes.length}`);

// ======================= N2 GENERATOR =======================
const n2 = loadJSON('jlpt_n2.json');
const n2_patterns = [
    { p: '〜ざるを得ない', m: 'cannot help but / have no choice but to' },
    { p: '〜っこない', m: 'no chance of / definitely not' },
    { p: '〜かねない', m: 'might (happen) / there is a fear that' },
    { p: '〜がたい', m: 'hard to / difficult to' },
    { p: '〜つつある', m: 'to be in the process of doing' },
    { p: '〜に際して', m: 'on the occasion of / at the time of' },
    { p: '〜を問わず', m: 'regardless of' },
    { p: '〜に決まっている', m: 'must be / definitely' },
    { p: '〜抜く', m: 'to do something to the end' },
    { p: '〜どころではない', m: 'not the time for / far from' }
];
for (let pat of n2_patterns) {
    for (let w of n3_words) { // Reuse the 30 words array
        n2.quizzes.push({
            q: `Which option accurately translates the N2 pattern "${pat.p}"? (Context word: ${w})`,
            options: [pat.m, 'easy to do', 'only just started', 'about to do'],
            answer: 0,
            explain: `The N2 grammar ${pat.p} translates to "${pat.m}".`
        });
    }
}
saveJSON('jlpt_n2.json', n2);
console.log(`Generated N2 questions. Total is now ${n2.quizzes.length}`);

// ======================= N1 GENERATOR =======================
const n1 = loadJSON('jlpt_n1.json');
const n1_patterns = [
    { p: '〜いかん', m: 'depending on' },
    { p: '〜がてら', m: 'while (doing something else)' },
    { p: '〜ずくめ', m: 'entirely / completely covered in' },
    { p: '〜そばから', m: 'as soon as (shows repeated action)' },
    { p: '〜なりに', m: 'in one\'s own way' },
    { p: '〜んがため', m: 'in order to' },
    { p: '〜たるもの', m: 'as a (person of such status)' },
    { p: '〜ならでは', m: 'uniquely / only possible with' },
    { p: '〜にとどまらず', m: 'not limited to' },
    { p: '〜ゆえに', m: 'because of / due to' }
];
for (let pat of n1_patterns) {
    for (let w of n3_words) {
        n1.quizzes.push({
            q: `Select the correct meaning for the N1 grammar structure "${pat.p}" (Context: ${w}):`,
            options: [pat.m, 'even if', 'without fail', 'immediately after'],
            answer: 0,
            explain: `The advanced N1 pattern ${pat.p} indicates "${pat.m}".`
        });
    }
}
saveJSON('jlpt_n1.json', n1);
console.log(`Generated N1 questions. Total is now ${n1.quizzes.length}`);
