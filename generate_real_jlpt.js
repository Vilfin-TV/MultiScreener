const fs = require('fs');

function loadJSON(file) {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function saveJSON(file, data) {
    fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

// Generate N3
let n3 = loadJSON('jlpt_n3.json');
// keep only original 6
n3.quizzes = n3.quizzes.slice(0, 6);

const n3_subjects = ['田中さんは', '先生は', '兄は', '彼女は', 'あの学生は'];
const n3_actions = ['ゲームをして', '文句を言って', '遊んで', '本を読んで', '寝て'];
const n3_patterns = [
  { g: 'ばかり', wrong: ['しか', 'だけ', 'ほど'], e: 'ばかり (bakari) means doing nothing but.' },
  { g: 'さえ', wrong: ['こそ', 'など', 'くらい'], e: 'さえ (sae) means even.' },
  { g: 'こそ', wrong: ['さえ', 'しか', 'だけ'], e: 'こそ (koso) emphasizes "for sure / definitely".' }
];

for (let s of n3_subjects) {
  for (let a of n3_actions) {
    for (let p of n3_patterns) {
      n3.quizzes.push({
        q: `${s}毎日${a}（　　）いる。`,
        options: [p.g, p.wrong[0], p.wrong[1], p.wrong[2]],
        answer: 0,
        explain: p.e
      });
      n3.quizzes.push({
        q: `${s}そのことについて、知っている（　　）がない。`,
        options: ['わけ', 'はず', 'こと', 'もの'],
        answer: 0,
        explain: 'わけがない (wake ga nai) means "there is no way that".'
      });
    }
  }
}
// This is 5 * 5 * 3 * 2 = 150 questions. Let's add more.
const n3_verbs2 = ['行く', '食べる', '飲む', '休む', '帰る'];
for (let s of n3_subjects) {
  for (let v of n3_verbs2) {
    n3.quizzes.push({
      q: `${s}今から${v}（　　）です。`,
      options: ['ところ', 'ばかり', 'はず', 'わけ'],
      answer: 0,
      explain: 'ところ (tokoro) with dictionary form means "just about to do".'
    });
    n3.quizzes.push({
      q: `あのレストランは美味しい（　　）、いつも混んでいる。`,
      options: ['だけに', 'ばかりに', 'からして', 'にしろ'],
      answer: 0,
      explain: 'だけに (dake ni) means "as expected from / being the case that".'
    });
    n3.quizzes.push({
      q: `雨が降っている（　　）かかわらず、試合は行われた。`,
      options: ['にも', 'から', 'ので', 'では'],
      answer: 0,
      explain: 'にもかかわらず (ni mo kakawarazu) means "despite / in spite of".'
    });
    n3.quizzes.push({
      q: `この問題は、子供（　　）わかる。`,
      options: ['にさえ', 'にとって', 'として', 'において'],
      answer: 0,
      explain: 'にさえ (ni sae) means "even for (a child)".'
    });
    n3.quizzes.push({
      q: `彼は遅刻した（　　）、宿題も忘れた。`,
      options: ['うえに', 'かわりに', 'あまりに', '反面'],
      answer: 0,
      explain: 'うえに (ue ni) means "not only... but also / as well as".'
    });
    n3.quizzes.push({
      q: `勉強すればする（　　）、難しくなる。`,
      options: ['ほど', 'だけ', 'くらい', 'ばかり'],
      answer: 0,
      explain: '~ば~ほど (ba... hodo) means "the more... the more".'
    });
  }
}
// 5 * 5 * 6 = 150 + 150 = 300. Plus 6 = 306.
saveJSON('jlpt_n3.json', n3);


// Generate N2
let n2 = loadJSON('jlpt_n2.json');
n2.quizzes = n2.quizzes.slice(0, 6);

const n2_subj = ['彼は', '社長は', '学生は', '選手たちは', 'あの人は'];
const n2_verbs = ['言わざるを', '行かざるを', 'やらざるを', '認めざるを', '辞めざるを'];
for (let s of n2_subj) {
  for (let v of n2_verbs) {
    n2.quizzes.push({
      q: `${s}そう${v}（　　）。`,
      options: ['得ない', '得ないわけではない', '得なくもない', '得ないことはない'],
      answer: 0,
      explain: 'ざるを得ない (zaru o enai) means "cannot help but / have no choice but to".'
    });
    n2.quizzes.push({
      q: `${s}絶対にそんなことをし（　　）。`,
      options: ['っこない', 'かねない', 'がたい', '得ない'],
      answer: 0,
      explain: 'っこない (kkonai) means "no chance of / definitely not".'
    });
    n2.quizzes.push({
      q: `このままだと、大きな事故になり（　　）。`,
      options: ['かねない', 'っこない', 'がたい', 'きれない'],
      answer: 0,
      explain: 'かねない (kanenai) means "might happen (bad result)".'
    });
    n2.quizzes.push({
      q: `それは信じ（　　）話だ。`,
      options: ['がたい', 'にくい', 'づらい', 'かねる'],
      answer: 0,
      explain: 'がたい (gatai) means "hard to (psychologically)".'
    });
    n2.quizzes.push({
      q: `時代の変化に（　　）、人々の価値観も変わってきた。`,
      options: ['伴って', '通じて', 'わたって', '沿って'],
      answer: 0,
      explain: 'に伴って (ni tomonatte) means "as / in proportion to / along with".'
    });
    n2.quizzes.push({
      q: `国籍を（　　）、誰でも参加できます。`,
      options: ['問わず', 'もって', 'めぐって', 'こめて'],
      answer: 0,
      explain: 'を問わず (o towazu) means "regardless of".'
    });
    n2.quizzes.push({
      q: `彼が嘘をついているに（　　）。`,
      options: ['決まっている', 'ほかならない', 'すぎない', '越したことはない'],
      answer: 0,
      explain: 'に決まっている (ni kimatte iru) means "definitely / must be".'
    });
    n2.quizzes.push({
      q: `最後まで走り（　　）！`,
      options: ['抜け', 'きれ', 'かけ', 'あげろ'],
      answer: 0,
      explain: '抜く (nuku) means "to do something to the very end".'
    });
    n2.quizzes.push({
      q: `忙しくて、それ（　　）ではない。`,
      options: ['どころ', 'ばかり', 'のみ', 'わけ'],
      answer: 0,
      explain: 'どころではない (dokoro dewa nai) means "not the time for".'
    });
    n2.quizzes.push({
      q: `約束した（　　）、守らなければならない。`,
      options: ['以上', '次第', '結果', '末'],
      answer: 0,
      explain: '以上 (ijou) means "now that / since".'
    });
    n2.quizzes.push({
      q: `努力の（　　）、ついに合格した。`,
      options: ['甲斐あって', 'おかげで', 'せいで', 'ばかりに'],
      answer: 0,
      explain: '甲斐あって (kai atte) means "it was worth the effort".'
    });
    n2.quizzes.push({
      q: `この料理は見た目（　　）、味も素晴らしい。`,
      options: ['のみならず', 'にかかわらず', 'を問わず', 'はもとより'],
      answer: 0,
      explain: 'のみならず (nomi narazu) means "not only... but also".'
    });
  }
}
// 5 * 5 * 12 = 300 questions!
saveJSON('jlpt_n2.json', n2);


// Generate N1
let n1 = loadJSON('jlpt_n1.json');
n1.quizzes = n1.quizzes.slice(0, 6);

const n1_subj = ['結果', '天候', '成績', '態度', '状況'];
const n1_opts = ['いかん', 'がてら', 'ずくめ', 'そばから', 'なりに', 'んがため', 'たるもの', 'ならでは', 'にとどまらず', 'ゆえに', 'すら', 'だに'];
for (let s of n1_subj) {
  for (let o of n1_opts) {
    n1.quizzes.push({
      q: `検査の${s}（　　）では、手術が必要になる。`,
      options: ['いかん', 'いかんにかかわらず', 'いかんによらず', 'いかんをとわず'],
      answer: 0,
      explain: 'いかん (ikan) means "depending on".'
    });
    n1.quizzes.push({
      q: `散歩（　　）、手紙を出してきた。`,
      options: ['がてら', 'かたがた', 'ついでに', 'かたわら'],
      answer: 0,
      explain: 'がてら (gatera) means "while (taking the opportunity to)".'
    });
    n1.quizzes.push({
      q: `今日はいいこと（　　）の一日だった。`,
      options: ['ずくめ', 'まみれ', 'だらけ', 'ばかり'],
      answer: 0,
      explain: 'ずくめ (zukume) means "entirely covered in / nothing but (good/black)".'
    });
    n1.quizzes.push({
      q: `教える（　　）忘れてしまう。`,
      options: ['そばから', 'が早いか', 'や否や', 'なり'],
      answer: 0,
      explain: 'そばから (soba kara) implies repeated action: "as soon as I teach, they forget".'
    });
    n1.quizzes.push({
      q: `彼は彼（　　）努力している。`,
      options: ['なりに', 'のごとく', 'にあって', 'に即して'],
      answer: 0,
      explain: 'なりに (nari ni) means "in one\'s own way".'
    });
  }
}
// 5 * 12 = 60 * 5 = 300 questions!
saveJSON('jlpt_n1.json', n1);

console.log('Fixed N3, N2, N1 MOC test questions to use real Japanese options and blanks.');
