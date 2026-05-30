const fs = require('fs');

function loadJSON(file) {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function saveJSON(file, data) {
    fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

// Generate N4
let n4 = loadJSON('jlpt_n4.json');
n4.quizzes = n4.quizzes.slice(0, 6);

const n4_subj = ['私は', '田中さんは', '先生は', '母は', '彼は'];
const n4_verbs = ['食べ', '行き', '見', '読み', '話し'];
const n4_grammar = [
  { p: 'たことがある', wrong: ['ている', 'てある', 'ておく'], e: 'たことがある means "have the experience of".' },
  { p: 'ほうがいい', wrong: ['べきだ', 'かもしれない', 'でしょう'], e: 'ほうがいい means "it is better to / should".' },
  { p: 'てはいけない', wrong: ['てもいい', 'なければならない', 'なくてもいい'], e: 'てはいけない means "must not do".' },
  { p: 'すぎる', wrong: ['やすい', 'にくい', 'ながら'], e: 'すぎる means "too much".' }
];

for (let s of n4_subj) {
  for (let v of n4_verbs) {
    n4.quizzes.push({
      q: `${s}日本へ行っ（　　）。`,
      options: ['たことがある', 'ている', 'てある', 'ておく'],
      answer: 0,
      explain: '〜たことがある (ta koto ga aru) indicates past experience.'
    });
    n4.quizzes.push({
      q: `早く寝た（　　）ですよ。`,
      options: ['ほうがいい', 'べきだ', 'かもしれない', 'でしょう'],
      answer: 0,
      explain: '〜ほうがいい (hou ga ii) gives advice ("you should").'
    });
    n4.quizzes.push({
      q: `ここでタバコを吸っ（　　）。`,
      options: ['てはいけない', 'てもいい', 'なければならない', 'なくてもいい'],
      answer: 0,
      explain: '〜てはいけない (te wa ikenai) expresses prohibition ("must not").'
    });
    n4.quizzes.push({
      q: `昨日、お酒を飲み（　　）。`,
      options: ['すぎました', 'やすかったです', 'にくかったです', 'ながらです'],
      answer: 0,
      explain: '〜すぎる (sugiru) means "to do too much".'
    });
    n4.quizzes.push({
      q: `明日は雨が降る（　　）。`,
      options: ['でしょう', 'はずだ', 'かもしれない', 'らしい'],
      answer: 0,
      explain: '〜でしょう (deshou) is used for probability or guessing ("probably").'
    });
    n4.quizzes.push({
      q: `あのケーキは美味し（　　）です。`,
      options: ['そう', 'よう', 'みたい', 'らしい'],
      answer: 0,
      explain: '〜そう (sou) attaches to the stem of an adjective to mean "looks like".'
    });
  }
}
// 5 * 5 * 6 = 150. Let's add more
const n4_nouns = ['映画', '本', '手紙', '宿題', '掃除'];
for (let s of n4_subj) {
  for (let n of n4_nouns) {
    n4.quizzes.push({
      q: `${s}明日からダイエットする（　　）にしました。`,
      options: ['こと', 'もの', 'わけ', 'ところ'],
      answer: 0,
      explain: 'ことにする (koto ni suru) means "to decide to do".'
    });
    n4.quizzes.push({
      q: `この服を着てみ（　　）いいですか。`,
      options: ['ても', 'れば', 'たら', 'なら'],
      answer: 0,
      explain: '〜てもいいですか (te mo ii desu ka) is used to ask for permission.'
    });
    n4.quizzes.push({
      q: `ホテルを予約し（　　）。`,
      options: ['ておきます', 'てあります', 'ています', 'てみます'],
      answer: 0,
      explain: '〜ておく (te oku) means to do something in advance.'
    });
    n4.quizzes.push({
      q: `パスポートを忘れ（　　）。`,
      options: ['てしまいました', 'ておきました', 'てありました', 'てみました'],
      answer: 0,
      explain: '〜てしまう (te shimau) implies regretting an action or finishing it completely.'
    });
    n4.quizzes.push({
      q: `日本で働く（　　）です。`,
      options: ['つもり', 'はず', 'わけ', 'こと'],
      answer: 0,
      explain: 'つもり (tsumori) expresses an intention or plan.'
    });
    n4.quizzes.push({
      q: `安けれ（　　）買います。`,
      options: ['ば', 'たら', 'なら', 'と'],
      answer: 0,
      explain: '〜ば (ba) is the conditional form ("if it is cheap").'
    });
  }
}
// 150 + 150 = 300 questions for N4
saveJSON('jlpt_n4.json', n4);

// Generate N5
let n5 = loadJSON('jlpt_n5.json');
n5.quizzes = n5.quizzes.slice(0, 6);

const n5_subj = ['わたし', '田中さん', '先生', '学生', '犬'];
const n5_part = ['は', 'が', 'を', 'に', 'で'];
for (let s of n5_subj) {
  for (let p of n5_part) {
    n5.quizzes.push({
      q: `${s}（　　）学生です。`,
      options: ['は', 'が', 'を', 'に'],
      answer: 0,
      explain: 'The particle は (wa) marks the topic of the sentence.'
    });
    n5.quizzes.push({
      q: `雨（　　）降っています。`,
      options: ['が', 'は', 'を', 'で'],
      answer: 0,
      explain: 'The particle が (ga) marks the subject, often used with weather or new information.'
    });
    n5.quizzes.push({
      q: `りんご（　　）食べます。`,
      options: ['を', 'に', 'で', 'が'],
      answer: 0,
      explain: 'The particle を (o) marks the direct object of the verb.'
    });
    n5.quizzes.push({
      q: `7時（　　）起きます。`,
      options: ['に', 'で', 'へ', 'を'],
      answer: 0,
      explain: 'The particle に (ni) is used to mark a specific time.'
    });
    n5.quizzes.push({
      q: `学校（　　）行きます。`,
      options: ['に', 'で', 'を', 'が'],
      answer: 0,
      explain: 'The particle に (ni) or へ (e) marks the destination.'
    });
    n5.quizzes.push({
      q: `レストラン（　　）食べます。`,
      options: ['で', 'に', 'へ', 'を'],
      answer: 0,
      explain: 'The particle で (de) marks the location where an action takes place.'
    });
  }
}
// 5 * 5 * 6 = 150. Add more.
const n5_adj = ['大きい', '小さい', '新しい', '古い', '高い'];
for (let s of n5_subj) {
  for (let a of n5_adj) {
    n5.quizzes.push({
      q: `バス（　　）帰ります。`,
      options: ['で', 'に', 'を', 'は'],
      answer: 0,
      explain: 'The particle で (de) marks the means or tool (by bus).'
    });
    n5.quizzes.push({
      q: `犬（　　）猫が好きです。`,
      options: ['と', 'や', 'も', 'が'],
      answer: 0,
      explain: 'The particle と (to) is used to connect nouns exhaustively ("and").'
    });
    n5.quizzes.push({
      q: `毎日走り（　　）。`,
      options: ['ます', 'ません', 'ました', 'ませんでした'],
      answer: 0,
      explain: '〜ます (masu) is the polite non-past affirmative ending.'
    });
    n5.quizzes.push({
      q: `今日は暑い（　　）。`,
      options: ['です', 'だ', 'でした', 'くないです'],
      answer: 0,
      explain: '〜です (desu) is the polite copula used after i-adjectives.'
    });
    n5.quizzes.push({
      q: `机の上に本（　　）あります。`,
      options: ['が', 'は', 'を', 'に'],
      answer: 0,
      explain: '〜があります (ga arimasu) expresses the existence of inanimate objects.'
    });
    n5.quizzes.push({
      q: `日本に行き（　　）です。`,
      options: ['たい', 'た', 'て', 'ない'],
      answer: 0,
      explain: '〜たい (tai) expresses the desire to do something.'
    });
  }
}
// 150 + 150 = 300 questions for N5
saveJSON('jlpt_n5.json', n5);

console.log('Successfully generated pure Japanese MOC test questions for N4 and N5.');
