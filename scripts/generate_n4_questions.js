const fs = require('fs');
const path = require('path');

// ============================================================================
// 200 JLPT N4 QUESTIONS DATABASE
// Divided into:
// - Questions 1-50: Grammar & Sentence Structure
// - Questions 51-100: Particles
// - Questions 101-150: Vocabulary & Expressions
// - Questions 151-200: Kanji & Readings
// ============================================================================

const quizzes = [
  // --------------------------------------------------------------------------
  // GRAMMAR & SENTENCE STRUCTURE (1-50)
  // --------------------------------------------------------------------------
  {
    q: 'Choose the correct form to express the potential: "I can speak Japanese." (日本語が___。)',
    options: ['話せます', '話します', '話そう', '話せて'],
    answer: 0,
    explain: 'Potential verbs in Group 1 are formed by changing the final -u sound to -eru. 話す (to speak) becomes 話せる, and in polite form, 話せます (can speak).'
  },
  {
    q: 'Choose the correct conditional form for: "If it rains tomorrow, let\'s stay home." (明日、雨が___たら、家にいましょう。)',
    options: ['降っ', '降る', '降り', '降ら'],
    answer: 0,
    explain: 'The conditional form "~たら" (~tara) is created by adding "ra" to the past casual (Ta-form) of a verb. The past casual of 降る (to fall/rain) is 降った, so it is 降ったら.'
  },
  {
    q: 'Complete the sentence to mean "Please try to study every day": "毎日、勉強する___にしてください。"',
    options: ['よう', 'そう', 'こと', 'つもり'],
    answer: 0,
    explain: 'The pattern "~ようにする" (~youni suru) is used to express making a continuous effort or establishing a habit ("try/make an effort to do X").'
  },
  {
    q: 'Choose the correct form to express natural consequence: "When spring comes, flowers bloom." (春に___と、花が咲きます。)',
    options: ['なる', 'なって', 'なり', 'なら'],
    answer: 0,
    explain: 'The conditional particle "と" (to) expresses a natural, automatic, or inevitable consequence. It follows the dictionary form (なる + と).'
  },
  {
    q: 'Complete the sentence: "I heard that Mr. Tanaka will not go." (田中さんは行かない___です。)',
    options: ['そうだ', 'そう', 'らしい', 'こと'],
    answer: 1,
    explain: 'To express hearsay ("I heard that..."), use plain form + "そうです" (sou desu). "行かない" is the plain negative form, so "行かないそうです" means "I heard he is not going."'
  },
  {
    q: 'How do you say "This book seems difficult" (based on appearance)? (この本は___そうです。)',
    options: ['難しい', '難し', '難しくて', '難しく'],
    answer: 1,
    explain: 'To express conjecture or impression ("looks like / seems..."), drop the final "-i" from an I-adjective and add "そうです". 難しい becomes 難しそうです.'
  },
  {
    q: 'Choose the correct form to express passive: "I was bitten by a dog." (わたしは犬に___ました。)',
    options: ['かまれ', 'かみ', 'かませ', 'かむ'],
    answer: 0,
    explain: 'Passive verbs for Group 1 are formed by changing the final -u sound to -areru. 噛む (kamu - to bite) becomes 噛まれる. Polite past is 噛まれました.'
  },
  {
    q: 'Choose the correct form to express causative: "My father made me eat vegetables." (父はわたしに野菜を___ました。)',
    options: ['食べさせ', '食べられ', '食べ', '食べさせられ'],
    answer: 0,
    explain: 'Causative verbs (making/letting someone do X) for Group 2 are formed by replacing -ru with -saseru. 食べる becomes 食べさせる, and polite past is 食べさせました.'
  },
  {
    q: 'Complete the sentence to mean "I have the experience of climbing Mt. Fuji": "富士山に登った___があります。"',
    options: ['こと', 'とき', 'もの', 'ところ'],
    answer: 0,
    explain: 'The pattern "Verb (Ta-form) + ことがあります" (~koto ga arimasu) is used to express past experience ("have done X before"). 登った is past casual of 登る.'
  },
  {
    q: 'Choose the correct form to express: "The window is open (state of being)." (窓が___います。)',
    options: ['開けて', '開いて', '開く', '開けられて'],
    answer: 1,
    explain: 'For an intransitive verb representing a continuous state resulting from an action, use "Te-form + います". 開く (aku - to open intransitive) Te-form is 開いて.'
  },
  {
    q: 'Choose the correct form to express: "The window has been opened (intentional state)." (窓が___あります。)',
    options: ['開けて', '開いて', '開く', '開け'],
    answer: 0,
    explain: 'The pattern "Transitive Verb (Te-form) + あります" (~te arimasu) represents a state that was intentionally completed by someone. 開ける (akeru - transitive) Te-form is 開けて.'
  },
  {
    q: 'Complete the sentence: "I will finish doing my homework before 8:00." (８時までに宿題をやって___ます。)',
    options: ['しまいます', 'おきます', 'みます', 'いきます'],
    answer: 0,
    explain: 'The pattern "Te-form + しまう" (~te shimau) expresses completing an action fully or doing something completely.'
  },
  {
    q: 'Complete the sentence to mean "I will buy drinks in advance": "飲み物を買って___ます。"',
    options: ['おき', 'しまい', 'み', 'き'],
    answer: 0,
    explain: 'The pattern "Te-form + おく" (~te oku) expresses performing an action in advance or preparing for the future.'
  },
  {
    q: 'Choose the correct conjugation for: "It is decided that I will go to Tokyo next month." (来月、東京へ行くことになりました。)',
    options: ['ことになりました', 'ことにしました', 'はずになりました', 'つもりになりました'],
    answer: 0,
    explain: 'The grammar pattern "~ことになる" (~koto ni naru) indicates that an arrangement or decision has been made by someone else or a external factor ("it has been decided that").'
  },
  {
    q: 'Choose the correct conjugation to mean "I started writing a letter": "手紙を書き___ました。"',
    options: ['始め', '終わり', 'すぎ', '出し'],
    answer: 0,
    explain: 'To express starting an action, attach "~始める" (~hajimeru) to the verb Masu-stem. 書きます stem is 書き.'
  },
  {
    q: 'Choose the correct form to mean "I finished eating dinner": "晩ご飯を食べ___ました。"',
    options: ['終わり', '始め', 'すぎ', '出し'],
    answer: 0,
    explain: 'To express finishing an action, attach "~終わる" (~owaru) to the verb Masu-stem. 食べます stem is 食べ.'
  },
  {
    q: 'Choose the correct form to mean "Please don\'t worry": "心配___でください。"',
    options: ['しなく', 'しないで', 'しな', 'し'],
    answer: 1,
    explain: 'The pattern "~ないでください" (~nai de kudasai) is used for polite negative requests. 心配する becomes 心配しないでください.'
  },
  {
    q: 'Complete the sentence to mean "According to the weather report, it will be clear tomorrow": "天気予報___、明日は晴れるそうです。"',
    options: ['によれば', 'について', 'にとって', 'にともなって'],
    answer: 0,
    explain: 'The phrase "~によれば" (~ni yoreba) means "according to [source]" and is commonly paired with "~そうです" (hearsay).'
  },
  {
    q: 'Complete the sentence to mean "Compared to last year, this year is hotter": "去年に___、今年は暑いです。"',
    options: ['比べて', '対して', '伴って', 'ついて'],
    answer: 0,
    explain: 'The compound particle "~に比べて" (~ni kurabete) is used to express "compared to".'
  },
  {
    q: 'Complete the sentence to mean "I think it is going to rain shortly": "今にも雨が___そうです。"',
    options: ['降り出し', '降る', '降って', '降ら'],
    answer: 0,
    explain: 'Conjecture based on visual evidence ("about to start raining") uses the verb Masu-stem (降り出す stem is 降り出し) + そうです.'
  },
  {
    q: 'How do you politely say "Please look at this"? (これをご覧ください。)',
    options: ['ご覧ください', '見せてください', '見られてください', '拝見してください'],
    answer: 0,
    explain: '"ご覧ください" (goran kudasai) is the respectful (Sonkeigo) way to say "please look". 拝見する (haiken suru) is humble (Kenjougo).'
  },
  {
    q: 'Choose the humble (Kenjougo) form for "I will do it": "わたしが___ます。"',
    options: ['いたします', 'なさいます', 'あそばします', 'おっしゃいます'],
    answer: 0,
    explain: '"いたします" (itashimasu) is the humble form of する (to do) and is used to lower your own action in deference.'
  },
  {
    q: 'Choose the respectful (Sonkeigo) form of "to eat / drink" to say to a guest: "どうぞ、___ください。"',
    options: ['召し上がって', 'いただいて', '食べられて', 'おっしゃって'],
    answer: 0,
    explain: '"召し上がる" (meshiagaru) is the respectful verb for eat/drink. いただく (itadaku) is the humble form.'
  },
  {
    q: 'Complete the sentence: "Because I have a cold, I cannot go to school." (風邪をひいた___、学校へ行けません。)',
    options: ['ため', 'のに', 'ほど', 'ばかり'],
    answer: 0,
    explain: 'The particle "ため" (tame) indicates a formal reason or cause ("because / due to").'
  },
  {
    q: 'Choose the correct form to express hearsay: "I heard she is a teacher." (彼女は先生だ___です。)',
    options: ['そう', 'らしい', 'よう', 'みたい'],
    answer: 0,
    explain: 'For nouns, hearsay "~そうです" is preceded by "だ" (da) in plain form (先生だそうです). "らしい" means "seems/like".'
  },
  {
    q: 'Choose the correct form: "He speaks Japanese as if he were a Japanese person." (彼は日本人の___日本語を話します。)',
    options: ['ように', 'ような', 'そうで', 'らしく'],
    answer: 0,
    explain: 'The pattern "Noun + のように" indicates a simile or doing an action "like/as if" another noun (日本人のように - like a Japanese).'
  },
  {
    q: 'Choose the correct word: "This bag looks like a real one." (このバッグは本物の___です。)',
    options: ['よう', 'そう', 'らしい', 'こと'],
    answer: 0,
    explain: '"〜のようです" (no you desu) indicates similarity to a noun ("looks/appears like").'
  },
  {
    q: 'Choose the correct ending to mean "It is supposed to be cold tomorrow (strong expectation)": "明日は寒いはず___。"',
    options: ['です', 'ね', 'よ', 'でしょう'],
    answer: 0,
    explain: 'The pattern "~はずです" (~hazu desu) represents a logical, objective expectation based on evidence ("is supposed to / should be").'
  },
  {
    q: 'Complete the sentence to mean "I decided to buy a new computer": "新しいパソコンを買うことに___。"',
    options: ['しました', 'なりました', 'できました', 'ありました'],
    answer: 0,
    explain: 'The pattern "Verb (plain form) + ことにする" indicates a personal decision to perform an action.'
  },
  {
    q: 'Choose the correct form: "While studying, don\'t listen to music." (勉強して___、音楽を聞いてはいけません。)',
    options: ['いるあいだに', 'いるあいだ', 'おわるまえに', 'おわったあと'],
    answer: 1,
    explain: '"〜あいだ" (aida - during/while) is used when two continuous actions happen in parallel. "あいだに" is used when a single event occurs in the middle.'
  },
  {
    q: 'Complete: "While my mother was sleeping, a friend arrived." (母が寝ている___、友達が来ました。)',
    options: ['あいだに', 'あいだ', 'あとで', 'まえに'],
    answer: 0,
    explain: '"〜あいだに" (aida ni) indicates that a short, punctual event (friend arriving) happened in the middle of a continuous state (mother sleeping).'
  },
  {
    q: 'Complete the sentence: "I will read a book instead of watching TV." (テレビを見る___に、本を読みます。)',
    options: ['かわり', 'ために', 'ように', 'はず'],
    answer: 0,
    explain: 'The phrase "〜かわりに" (kawari ni) means "instead of / in place of".'
  },
  {
    q: 'Complete: "Please eat this cake before it gets cold." (ケーキが冷たくならない___、食べてください。)',
    options: ['うちに', 'あいだに', 'まえに', 'ため'],
    answer: 0,
    explain: 'The pattern "Verb (negative plain form) + うちに" (uchi ni) means "while a certain state holds / before it changes" ("while it is not cold").'
  },
  {
    q: 'Choose the correct conditional form: "If you want to buy a camera, that shop is good." (カメラを買う___、あの店がいいですよ。)',
    options: ['なら', 'たら', 'と', 'ば'],
    answer: 0,
    explain: 'The conditional "なら" (nara) is used when the speaker is responding or giving advice based on a topic brought up by the listener ("if that is the case").'
  },
  {
    q: 'Choose the correct form for "easy to use": "この道具は使い___です。"',
    options: ['やすい', 'にくい', 'かた', 'すぎる'],
    answer: 0,
    explain: '"Masu-stem + やすい" means easy to do. 使う (tsukau - to use) stem is 使い.'
  },
  {
    q: 'Choose the correct form for "difficult to read": "この本は読み___です。"',
    options: ['にくい', 'やすい', 'かた', 'すぎる'],
    answer: 0,
    explain: '"Masu-stem + にくい" means difficult to do. 読む (yomu - to read) stem is 読み.'
  },
  {
    q: 'Choose the correct form: "He ate too much." (彼は食べ___ました。)',
    options: ['すぎ', 'おわり', 'はじめ', 'やすい'],
    answer: 0,
    explain: '"Masu-stem + すぎる" (sugiru) means to do excessively. 食べる stem is 食べ.'
  },
  {
    q: 'Complete the sentence: "Please write how to read this Kanji." (この漢字の読み___を書いてください。)',
    options: ['かた', 'やすい', 'にくい', 'すぎ'],
    answer: 0,
    explain: '"Masu-stem + 方 (kata)" indicates the method or manner of doing an action ("how to read").'
  },
  {
    q: 'How do you say "It began to rain" suddenly? (雨が降り___ました。)',
    options: ['出し', '始め', '終わり', 'すぎ'],
    answer: 0,
    explain: '"Masu-stem + 出す" (dasu) indicates a sudden, unexpected start of an action. 降り出しました means "burst out raining".'
  },
  {
    q: 'Complete the sentence: "I went to buy food, but the shop was closed." (食べ物を買いに行きましたが、店は閉まって___。)',
    options: ['いました', 'ありました', 'おきました', 'みました'],
    answer: 0,
    explain: 'The state resulting from an intransitive verb (閉まる - to close) is represented by "Te-form + いる" (閉まっていました - was closed).'
  },
  {
    q: 'Complete the sentence to mean "Please leave it as it is": "そのままにして___ください。"',
    options: ['おいて', 'しまって', 'みせて', 'いって'],
    answer: 0,
    explain: '"〜ておく" (te oku) means to perform an action in preparation or to leave a state as it is.'
  },
  {
    q: 'Choose the correct form: "I tried wearing the Japanese kimono." (日本の着物を着て___ました。)',
    options: ['み', 'おき', 'しまい', 'き'],
    answer: 0,
    explain: 'The pattern "Te-form + みる" (~te miru) means "to try doing something / attempt to see how it goes".'
  },
  {
    q: 'Choose the correct respectful (Sonkeigo) verb for "to go" or "to come": "先生がこちらへ___ました。"',
    options: ['いらっしゃい', 'まいり', 'おっしゃい', 'いたし'],
    answer: 0,
    explain: '"いらっしゃる" (irassharu) is the respectful form of 行く, 来る, and いる. まいる (mairu) is humble.'
  },
  {
    q: 'Choose the humble (Kenjougo) verb for "to go" or "to come": "明日、そちらへ___ます。"',
    options: ['まいり', 'いらっしゃい', 'おっしゃい', 'いたし'],
    answer: 0,
    explain: '"まいる" (mairu) is the humble form of 行く and 来る, used to lower your own action in politeness.'
  },
  {
    q: 'Choose the respectful (Sonkeigo) verb for "to say": "社長がそう___ました。"',
    options: ['おっしゃい', '申し上げ', 'いたし', 'いらっしゃい'],
    answer: 0,
    explain: '"おっしゃる" (ossharu) is the respectful verb for "to say". 申し上げる is humble.'
  },
  {
    q: 'Choose the humble (Kenjougo) verb for "to say": "わたしが___ます。"',
    options: ['申し上げ', 'おっしゃい', 'いたし', 'なさり'],
    answer: 0,
    explain: '"申し上げる" (moushiageru) is the humble verb for "to say".'
  },
  {
    q: 'Choose the respectful (Sonkeigo) verb for "to do": "何をお仕事に___ますか。"',
    options: ['なさし', 'なさっ', 'なさり', 'なされ'],
    answer: 1,
    explain: '"なさる" (nasaru) is the respectful form of する (to do). Its polite non-past is なさいます. Its past casual is なさった.'
  },
  {
    q: 'Complete: "The food was delicious, so I ate it all up." (美味しかったので、全部食べて___ました。)',
    options: ['しまい', 'おき', 'み', 'いき'],
    answer: 0,
    explain: '"〜てしまう" (~te shimau) indicates that an action is fully completed or done with regret/satisfaction.'
  },
  {
    q: 'Choose the potential form of the Group 2 verb "食べる" (can eat):',
    options: ['食べられます', '食べせます', '食べれます', '食べます'],
    answer: 0,
    explain: 'Potential forms for Group 2 verbs are formed by replacing -ru with -rareru (食べられる). Note: while "tabereru" is colloquial slang, "taberareru" is the correct standard.'
  },
  {
    q: 'Choose the potential form of the irregular verb "する" (can do):',
    options: ['できます', 'しられます', 'せます', 'します'],
    answer: 0,
    explain: 'The irregular verb する (to do) has the potential form できる (dekiru), which in polite form is できます (can do).'
  },

  // --------------------------------------------------------------------------
  // PARTICLES (51-100)
  // --------------------------------------------------------------------------
  {
    q: 'Complete: "I only have 1,000 yen (expressing limitation negatively)." (千円___ありません。)',
    options: ['しか', 'だけ', 'ばかり', 'ほど'],
    answer: 0,
    explain: 'The particle "しか" (shika) represents limitation and must always be paired with a negative verb ("nothing but / only").'
  },
  {
    q: 'Complete: "I have only 1,000 yen (expressing limitation positively)." (千円___あります。)',
    options: ['だけ', 'しか', 'ばかり', 'ほど'],
    answer: 0,
    explain: 'The particle "だけ" (dake) represents limitation and is paired with positive verbs ("only").'
  },
  {
    q: 'Complete the sentence: "Although I studied hard, the exam was difficult." (一生懸命勉強した___、試験は難しかったです。)',
    options: ['のに', 'から', 'ので', 'ため'],
    answer: 0,
    explain: 'The conjunctive particle "のに" (noni) indicates contrast, surprise, or regret ("although / in spite of the fact that").'
  },
  {
    q: 'Complete the sentence: "This book is not as heavy as that one." (この本はその本___重くないです。)',
    options: ['ほど', 'だけ', 'しか', 'ばかり'],
    answer: 0,
    explain: 'In negative comparison sentences, "~ほど [negative]" is used to mean "not as... as..." (not as heavy as that book).'
  },
  {
    q: 'Complete the sentence: "I bought a camera for the sake of traveling." (旅行の___カメラを買いました。)',
    options: ['ために', 'ように', 'までに', 'あいだに'],
    answer: 0,
    explain: 'The compound particle "〜ために" (tame ni) means "for the sake of / in order to" when following a noun + の.'
  },
  {
    q: 'Complete: "Please speak loudly so that everyone can hear." (みんなに聞こえる___、大きな声で話してください。)',
    options: ['ように', 'ために', 'までに', 'あいだに'],
    answer: 0,
    explain: '"〜ように" (you ni) is used to express "so that / in order that" when preceding a potential or non-volitional verb.'
  },
  {
    q: 'Complete the sentence: "This temple was built by a famous monk." (この寺は有名な僧___建てられました。)',
    options: ['によって', 'について', 'に対して', 'によっても'],
    answer: 0,
    explain: 'In passive sentences, the agent or creator of a historic/monumental object is marked with "~によって" (ni yotte - "by").'
  },
  {
    q: 'Complete the sentence: "Even if it is cold tomorrow, I will go out." (明日、寒く___出かけます。)',
    options: ['ても', 'でも', 'のに', 'ので'],
    answer: 0,
    explain: 'For I-adjectives, the conjunctive form for "even if / although" is "~ても" (~te mo). 寒い becomes 寒くても.'
  },
  {
    q: 'Complete the sentence: "Even if it rains tomorrow, I will go." (明日、雨___行きます。)',
    options: ['でも', 'ても', 'のに', 'ので'],
    answer: 0,
    explain: 'For nouns and Na-adjectives, the conjunctive form for "even if" is "~でも" (~de mo). 雨 becomes 雨でも.'
  },
  {
    q: 'Complete the sentence: "He just arrived (very recently)." (彼は今、着いた___です。)',
    options: ['ばかり', 'だけ', 'しか', 'ほど'],
    answer: 0,
    explain: 'The pattern "Verb (Ta-form) + ばかり" (~bakari) indicates that an action was completed very recently ("just did X").'
  },
  {
    q: 'Complete: "While I was studying, my brother was playing games." (わたしが勉強している___、弟はゲームをしていました。)',
    options: ['あいだ', 'あいだに', 'までに', 'うちに'],
    answer: 0,
    explain: '"〜あいだ" (aida) is used because both actions (studying and playing games) occurred continuously and concurrently.'
  },
  {
    q: 'Complete the sentence: "Please submit your homework by 3:00." (３時___宿題を出してください。)',
    options: ['までに', 'まで', 'から', 'に'],
    answer: 0,
    explain: '"〜までに" (made ni) indicates a deadline ("by / no later than"). "まで" means "until" continuously.'
  },
  {
    q: 'Complete the sentence: "I will study until 5:00." (５時___勉強します。)',
    options: ['まで', 'までに', 'から', 'に'],
    answer: 0,
    explain: '"〜まで" (made) indicates continuous action up to a certain point in time ("until").'
  },
  {
    q: 'Complete the sentence: "I gave some chocolate to my younger sister." (妹___チョコレートをあげました。)',
    options: ['に', 'を', 'で', 'が'],
    answer: 0,
    explain: 'The recipient of an action (giving chocolate) is marked with "に" (ni).'
  },
  {
    q: 'Complete the sentence: "I got a letter from my teacher." (先生___手紙をいただきました。)',
    options: ['から', 'を', 'に', 'の'],
    answer: 0,
    explain: '"から" (kara) marks the source or sender. "いただく" is the humble form of receive.'
  },
  {
    q: 'Complete: "This is a book that my father wrote." (これは父___書いた本です。)',
    options: ['が', 'は', 'を', 'に'],
    answer: 0,
    explain: 'In relative modifying clauses, the subject of the modifying clause is marked with "が" (ga) or "の" (no), never "は".'
  },
  {
    q: 'Complete the sentence: "I read newspapers as much as possible." (できる___新聞を読むようにしています。)',
    options: ['だけ', 'しか', 'ばかり', 'ほど'],
    answer: 0,
    explain: 'The expression "できるだけ" (dekiru dake) is a fixed phrase meaning "as much as possible".'
  },
  {
    q: 'Complete the sentence: "I have to write it in either Japanese or English." (日本語___英語で書かなければなりません。)',
    options: ['か', 'と', 'や', 'も'],
    answer: 0,
    explain: 'The particle "か" (ka) is used between nouns to indicate alternative options ("either X or Y / or").'
  },
  {
    q: 'Complete the sentence: "Please choose whichever one you like." (どれ___好きなものを選んでください。)',
    options: ['でも', 'か', 'も', 'が'],
    answer: 0,
    explain: '"どれでも" (doredemo) means "whichever / any of them".'
  },
  {
    q: 'Complete the sentence: "Nobody knows about that." (それについては、だれ___知りません。)',
    options: ['も', 'か', 'が', 'は'],
    answer: 0,
    explain: '"だれも" (daremo) paired with a negative verb (知りません) means "nobody".'
  },
  {
    q: 'Complete: "I want to go somewhere (unspecified place) on vacation." (休みにどこ___行きたいです。)',
    options: ['か', 'も', 'が', 'でも'],
    answer: 0,
    explain: '"どこか" (dokoka) means "somewhere".'
  },
  {
    q: 'Complete: "I can go anywhere (any place at all)!" (どこ___行けますよ！)',
    options: ['でも', 'か', 'も', 'が'],
    answer: 0,
    explain: '"どこでも" (dokodemo) means "anywhere / any place at all".'
  },
  {
    q: 'Complete the sentence: "Is there anything in the bag?" (カバンの中に何か___ありますか。)',
    options: ['か', 'も', 'が', '（無記入）'],
    answer: 3,
    explain: '"何か" (nanika) means "something/anything" and does not require an additional particle like "が" or "を".'
  },
  {
    q: 'Complete the sentence: "No, there is nothing." (いいえ、何___ありません。)',
    options: ['も', 'か', 'が', 'でも'],
    answer: 0,
    explain: '"何も" (nanimo) paired with a negative verb means "nothing".'
  },
  {
    q: 'Complete the sentence: "I decided to make a decision." (決めること___しました。)',
    options: ['に', 'を', 'で', 'が'],
    answer: 0,
    explain: 'The noun-connector "ことに" is used with "する" to form "~ことにする" (to decide to do).'
  },
  {
    q: 'Complete the sentence: "The meeting starts at 10:00." (会議は１０時___始まります。)',
    options: ['に', 'で', 'へ', 'を'],
    answer: 0,
    explain: 'The particle "に" (ni) marks a specific numerical time point.'
  },
  {
    q: 'Complete: "I will call you when I arrive at the station." (駅に着いた___、電話します。)',
    options: ['とき', 'まえに', 'ために', 'ように'],
    answer: 0,
    explain: '"〜とき" (toki) means "when / at the time of".'
  },
  {
    q: 'Complete: "I will do my best for the family." (家族の___に頑張ります。)',
    options: ['ため', 'よう', 'こと', 'はず'],
    answer: 0,
    explain: '"家族のために" means "for the sake of / for the benefit of the family".'
  },
  {
    q: 'Complete the sentence: "I saw a bird flying in the sky." (鳥が空を飛んでいる___を見ました。)',
    options: ['の', 'こと', 'もの', 'ところ'],
    answer: 0,
    explain: 'The nominalizer "の" (no) is used when directly perceiving/seeing/hearing a concrete action (飛んでいるのを見ました).'
  },
  {
    q: 'Complete: "Please turn off the light before sleeping." (寝る___に電気を消してください。)',
    options: ['まえ', 'あと', 'あいだ', 'うち'],
    answer: 0,
    explain: 'The pattern "Verb (plain dictionary form) + まえに" means "before doing X".'
  },
  {
    q: 'Complete the sentence: "After eating, wash the dishes." (食べた___に皿を洗ってください。)',
    options: ['あと', 'まえ', 'あいだ', 'うち'],
    answer: 0,
    explain: 'The pattern "Verb (Ta-form) + あとに/あとで" means "after doing X".'
  },
  {
    q: 'Complete: "Since I have no money, I will not buy it." (お金がない___、買いません。)',
    options: ['から', 'のに', 'ほど', 'ばかり'],
    answer: 0,
    explain: 'The causal particle "から" (kara) states the subjective reason or cause ("since / because").'
  },
  {
    q: 'Complete the sentence: "Mr. Yamada seems busy." (山田さんは忙しい___です。)',
    options: ['よう', 'そう', 'はず', 'つもり'],
    answer: 0,
    explain: 'The pattern "~ようです" (you desu) indicates conjecture based on observation ("seems/looks like").'
  },
  {
    q: 'Complete the sentence: "Please give me whichever one is cheap." (安い___をください。)',
    options: ['ほう', 'だけ', 'ばかり', 'ほど'],
    answer: 0,
    explain: '"〜のほう" (no hou) indicates a specific direction, alternative, or side in a comparison ("the cheap one").'
  },
  {
    q: 'Complete the sentence: "I will go even if it is far." (遠く___行きますよ。)',
    options: ['ても', 'でも', 'のに', 'ので'],
    answer: 0,
    explain: 'For I-adjectives, drop the -i and add -temo to mean "even if". 遠い becomes 遠くても.'
  },
  {
    q: 'Complete the sentence: "I bought books, pens, and so on." (本やペン___を買いました。)',
    options: ['など', 'だけ', 'しか', 'ばかり'],
    answer: 0,
    explain: 'The particle "など" (nado) represents non-exhaustive listing ("and so on / etc.") and is paired with "や".'
  },
  {
    q: 'Complete the sentence: "I spent all day watching TV." (一日中テレビ___見ていました。)',
    options: ['ばかり', 'しか', 'だけ', 'ほど'],
    answer: 0,
    explain: 'The particle "ばかり" (bakari) following a noun here denotes "nothing but / constantly doing X".'
  },
  {
    q: 'Complete the sentence: "This is my brother\'s car." (これは弟___車です。)',
    options: ['の', 'は', 'が', 'を'],
    answer: 0,
    explain: 'The possessive particle "の" (no) connects two nouns.'
  },
  {
    q: 'Complete the sentence: "I came to Japan to study Japanese." (日本語を勉強する___に日本へ来ました。)',
    options: ['ため', 'よう', 'こと', 'はず'],
    answer: 0,
    explain: 'The construction "Verb (plain form) + ために" indicates purpose ("in order to").'
  },
  {
    q: 'Complete the sentence: "I am trying not to drink sweet drinks." (甘い飲み物を飲まない___にしています。)',
    options: ['よう', 'ため', 'こと', 'はず'],
    answer: 0,
    explain: '"〜ないようにする" means "to try/make an effort not to do X".'
  },
  {
    q: 'Complete: "Which of these two is larger?" (この二つの中で、どちら___大きいですか。)',
    options: ['が', 'は', 'を', 'に'],
    answer: 0,
    explain: 'Comparison interrogatives like どちら take the subject marker particle "が" (ga).'
  },
  {
    q: 'Complete: "I think he will pass the exam." (彼は試験に合格する___と思います。)',
    options: ['と', 'が', 'を', 'は'],
    answer: 0,
    explain: 'The particle "と" (to) acts as a quote/thought nominalizer before 思います.'
  },
  {
    q: 'Complete: "She said she was going." (彼女は行く___言っていました。)',
    options: ['と', 'が', 'を', 'は'],
    answer: 0,
    explain: 'The quote connector "と" (to) is used before reporting verbs like 言う.'
  },
  {
    q: 'Complete the sentence: "Please tell me what you did." (何をした___教えてください。)',
    options: ['か', 'も', 'が', 'を'],
    answer: 0,
    explain: 'The indirect question marker "か" (ka) is attached to the end of the embedded clause.'
  },
  {
    q: 'Complete: "I don\'t know whether he is coming or not." (彼が来る___どうか分かりません。)',
    options: ['か', 'と', 'が', 'を'],
    answer: 0,
    explain: 'The construction "Verb (plain form) + かどうか" means "whether or not".'
  },
  {
    q: 'Complete the sentence: "He passed the exam by studying hard." (よく勉強した___、合格しました。)',
    options: ['ので', 'のに', 'ほど', 'ばかり'],
    answer: 0,
    explain: '"ので" (node) indicates a soft, objective cause/reason for his success.'
  },
  {
    q: 'Complete the sentence: "I will do my homework." (宿題___します。)',
    options: ['を', 'が', 'に', 'は'],
    answer: 0,
    explain: 'The direct object "宿題" of "します" takes "を".'
  },
  {
    q: 'Complete the sentence: "My hobby is taking photos." (私の趣味は写真を撮る___です。)',
    options: ['こと', 'の', 'もの', 'ところ'],
    answer: 0,
    explain: 'To define a hobby, nominalize the verb using "こと" (撮ることです - is taking photos).'
  },
  {
    q: 'Complete: "My older sister is taller than my mother." (姉は母___背が高いです。)',
    options: ['より', 'ほど', 'だけ', 'ばかり'],
    answer: 0,
    explain: 'The particle "より" (yori) marks the baseline of comparison ("than mother").'
  },
  {
    q: 'Complete the sentence: "Let\'s read a book at home." (家___本を読みましょう。)',
    options: ['で', 'に', 'へ', 'を'],
    answer: 0,
    explain: 'The location where the active event (reading) occurs is marked with "で".'
  },

  // --------------------------------------------------------------------------
  // VOCABULARY & EXPRESSIONS (101-150)
  // --------------------------------------------------------------------------
  {
    q: 'Which word means "Reason / Circumstance" in Japanese?',
    options: ['都合 (つごう)', '理由 (りゆう)', '予定 (よてい)', '約束 (やくそく)'],
    answer: 1,
    explain: '"理由" (riyuu) means reason. 都合 (tsugou) refers to convenience/schedule.'
  },
  {
    q: 'Which word means "Schedule / Plan" in Japanese?',
    options: ['予定 (よてい)', '理由 (りゆう)', '都合 (つごう)', '約束 (やくそく)'],
    answer: 0,
    explain: '"予定" (yotei) means plan, schedule, or arrangement.'
  },
  {
    q: 'Which transitive/intransitive pair means "to open" in Japanese?',
    options: ['開ける / 開く', '閉める / 閉まる', '付ける / 付く', '消す / 消える'],
    answer: 0,
    explain: '"開ける" (akeru) is transitive (to open something). "開く" (aku) is intransitive (something opens).'
  },
  {
    q: 'Which transitive/intransitive pair means "to close" in Japanese?',
    options: ['閉める / 閉まる', '開ける / 開く', '消す / 消える', '掛ける / 掛かる'],
    answer: 0,
    explain: '"閉める" (shimeru) is transitive (to close something). "閉まる" (shimaru) is intransitive (something closes).'
  },
  {
    q: 'What is the opposite of "増える" (fueru - to increase)?',
    options: ['減る (へる)', '下がる (さがる)', '消える (きえる)', '落ちる (おちる)'],
    answer: 0,
    explain: 'The opposite of increase (増える) is decrease (減る - heru).'
  },
  {
    q: 'What is the Japanese word for "Newspaper"?',
    options: ['新聞 (しんぶん)', '雑誌 (ざっし)', '本 (ほん)', '辞書 (じしょ)'],
    answer: 0,
    explain: '"新聞" (shinbun) means newspaper.'
  },
  {
    q: 'What is the Japanese word for "Dictionary"?',
    options: ['辞書 (じしょ)', '新聞 (しんぶん)', '雑誌 (ざっし)', '小説 (しょうせつ)'],
    answer: 0,
    explain: '"辞書" (jisho) means dictionary.'
  },
  {
    q: 'What does the adverb "ずいぶん" (zuibun) mean?',
    options: ['Extremely / Considerably', 'Slightly', 'A little', 'Never'],
    answer: 0,
    explain: '"ずいぶん" (zuibun) means considerably, extremely, or very.'
  },
  {
    q: 'What does "はっきり" (hakkiri) mean?',
    options: ['Clearly', 'Vaguely', 'Slowly', 'Quickly'],
    answer: 0,
    explain: '"はっきり" (hakkiri) means clearly, distinctly, or plainly.'
  },
  {
    q: 'What does the verb "遅れる" (okureru) mean?',
    options: ['To be late', 'To advance', 'To repeat', 'To explain'],
    answer: 0,
    explain: '"遅れる" (okureru) means to be late or delayed.'
  },
  {
    q: 'What is the Japanese word for "Preparation"?',
    options: ['準備 (じゅんび)', '練習 (れんしゅう)', '宿題 (しゅくだい)', '経験 (けいけん)'],
    answer: 0,
    explain: '"準備" (junbi) means preparation.'
  },
  {
    q: 'What is the Japanese word for "Experience"?',
    options: ['経験 (けいけん)', '準備 (じゅんび)', '相談 (そうだん)', '紹介 (しょうかい)'],
    answer: 0,
    explain: '"経験" (keiken) means experience.'
  },
  {
    q: 'What does "ちっとも" (chittomo) mean when used with a negative verb?',
    options: ['Not at all', 'Slightly', 'Always', 'Quickly'],
    answer: 0,
    explain: '"ちっとも" (chittomo) paired with negative verbs means "not in the least / not at all".'
  },
  {
    q: 'What is the Japanese word for "Introduction"?',
    options: ['紹介 (しょうかい)', '相談 (そうだん)', '説明 (せつめい)', '注意 (ちゅうい)'],
    answer: 0,
    explain: '"紹介" (shoukai) means introduction.'
  },
  {
    q: 'What is the Japanese word for "Consultation / Discussion"?',
    options: ['相談 (そうだん)', '紹介 (しょうかい)', '連絡 (れんらく)', '説明 (せつめい)'],
    answer: 0,
    explain: '"相談" (soudan) means consultation, discussion, or counsel.'
  },
  {
    q: 'What does the verb "片付ける" (katadukeru) mean?',
    options: ['To tidy up / clean', 'To break', 'To throw away', 'To lose'],
    answer: 0,
    explain: '"片付ける" (katadukeru) means to tidy up, put in order, or clean.'
  },
  {
    q: 'What is the Japanese word for "Garbage / Trash"?',
    options: ['ごみ', '道具 (どうぐ)', '家具 (かぐ)', '品物 (しなもの)'],
    answer: 0,
    explain: '"ごみ" (gomi) means garbage or trash.'
  },
  {
    q: 'What does "うらやましい" (urayamashii) mean?',
    options: ['Envious / Jealous', 'Sad', 'Scared', 'Happy'],
    answer: 0,
    explain: '"うらやましい" (urayamashii) means envious or jealous.'
  },
  {
    q: 'What does "おかしい" (okashii) mean?',
    options: ['Strange / Funny', 'Ordinary', 'Serious', 'Expensive'],
    answer: 0,
    explain: '"おかしい" (okashii) means strange, odd, funny, or peculiar.'
  },
  {
    q: 'What is the Japanese word for "Adult"?',
    options: ['大人 (おとな)', '子供 (こども)', '若者 (わかもの)', '老人 (ろうじん)'],
    answer: 0,
    explain: '"大人" (otona) means adult.'
  },
  {
    q: 'Which word means "Information / Guidance" in Japanese?',
    options: ['案内 (あんない)', '説明 (せつめい)', '相談 (そうだん)', '計画 (けいかく)'],
    answer: 0,
    explain: '"案内" (annai) means guidance, information, or leading the way.'
  },
  {
    q: 'What is the Japanese word for "Meeting"?',
    options: ['会議 (かいぎ)', '授業 (じゅぎょう)', '運動 (うんどう)', '計画 (けいかく)'],
    answer: 0,
    explain: '"会議" (kaigi) means meeting or conference.'
  },
  {
    q: 'What does "しっかり" (shikkari) mean?',
    options: ['Firmly / Reliably', 'Weakly', 'Vaguely', 'Slowly'],
    answer: 0,
    explain: '"しっかり" (shikkari) means firmly, steadily, or reliably.'
  },
  {
    q: 'What does the verb "調べる" (shiraberu) mean?',
    options: ['To investigate / search', 'To lose', 'To break', 'To decide'],
    answer: 0,
    explain: '"調べる" (shiraberu) means to investigate, search, check, or look up.'
  },
  {
    q: 'What is the Japanese word for "Airport"?',
    options: ['空港 (くうこう)', '港 (みなと)', '駅 (えき)', 'バス停 (ばすてい)'],
    answer: 0,
    explain: '"空港" (kuukou) means airport.'
  },
  {
    q: 'What is the Japanese word for "Port / Harbor"?',
    options: ['港 (みなと)', '空港 (くうこう)', '駅 (えき)', '道 (みち)'],
    answer: 0,
    explain: '"港" (minato) means port or harbor.'
  },
  {
    q: 'What is the Japanese word for "Station"?',
    options: ['駅 (えき)', '港 (みなと)', '道 (みち)', '交番 (こうばん)'],
    answer: 0,
    explain: '"駅" (eki) means station.'
  },
  {
    q: 'What is the Japanese word for "Police Box"?',
    options: ['交番 (こうばん)', '銀行 (ぎんこう)', '病院 (びょういん)', '郵便局 (ゆうびんきょく)'],
    answer: 0,
    explain: '"交番" (kouban) means police box/substation.'
  },
  {
    q: 'What is the Japanese word for "Neighborhood"?',
    options: ['近所 (きんじょ)', '遠く (とおく)', '場所 (ばしょ)', '住所 (じゅうしょ)'],
    answer: 0,
    explain: '"近所" (kinjo) means neighborhood.'
  },
  {
    q: 'What is the Japanese word for "Address"?',
    options: ['住所 (じゅうしょ)', '近所 (きんじょ)', '場所 (ばしょ)', '氏名 (しめい)'],
    answer: 0,
    explain: '"住所" (juusho) means address.'
  },
  {
    q: 'What does "かなしい" (kanashii) mean?',
    options: ['Sad', 'Happy', 'Angry', 'Envious'],
    answer: 0,
    explain: '"かなしい" (kanashii) means sad.'
  },
  {
    q: 'What is the opposite of "ぬれる" (nureru - to get wet)?',
    options: ['乾く (かわく)', '閉まる (しまる)', '壊れる (こわれる)', '落ちる (おちる)'],
    answer: 0,
    explain: 'The opposite of getting wet (ぬれる) is to get dry (乾く - kawaku).'
  },
  {
    q: 'What does the verb "さしあげる" (sashiageru) mean?',
    options: ['To give (polite/honorific)', 'To receive (polite)', 'To say (humble)', 'To ask'],
    answer: 0,
    explain: '"さしあげる" is the humble/polite form of あげる (to give to a superior).'
  },
  {
    q: 'What is the Japanese word for "Mirror"?',
    options: ['鏡 (かがみ)', '眼鏡 (めがね)', '時計 (とけい)', '窓 (まど)'],
    answer: 0,
    explain: '"鏡" (kagami) means mirror.'
  },
  {
    q: 'What is the Japanese word for "Glasses"?',
    options: ['眼鏡 (めがね)', '鏡 (かがみ)', '時計 (とけい)', '帽子 (ぼうし)'],
    answer: 0,
    explain: '"眼鏡" (megane) means glasses.'
  },
  {
    q: 'What is the Japanese word for "Calendar"?',
    options: ['カレンダー', '鏡 (かがみ)', '時計 (とけい)', '日記 (にっき)'],
    answer: 0,
    explain: '"カレンダー" (karenda-) is the loanword for calendar.'
  },
  {
    q: 'What does the word "熱心" (nesshin) mean?',
    options: ['Enthusiastic / Eager', 'Cold / Indifferent', 'Kind', 'Quiet'],
    answer: 0,
    explain: '"熱心" (nesshin) means enthusiastic, eager, or passionate.'
  },
  {
    q: 'What does "親切" (shinsetsu) mean?',
    options: ['Kind', 'Mean', 'Polite', 'Beautiful'],
    answer: 0,
    explain: '"親切" (shinsetsu) means kind or friendly.'
  },
  {
    q: 'What does "ていねい" (teinei) mean?',
    options: ['Polite', 'Rude', 'Quick', 'Slow'],
    answer: 0,
    explain: '"ていねい" (teinei) means polite or courteous.'
  },
  {
    q: 'What is the Japanese word for "Kitchen utensil / Tool"?',
    options: ['道具 (どうぐ)', '家具 (かぐ)', '品物 (しなもの)', 'おもちゃ'],
    answer: 0,
    explain: '"道具" (dougu) means tool or implement.'
  },
  {
    q: 'What does the verb "おこなう" (okonau) mean?',
    options: ['To perform / conduct', 'To rest', 'To read', 'To buy'],
    answer: 0,
    explain: '"おこなう" (okonau) means to perform, conduct, execute, or hold (an event).'
  },
  {
    q: 'What does the verb "かける" (kakeru) mean in the context of glasses?',
    options: ['To wear glasses', 'To take off glasses', 'To clean glasses', 'To buy glasses'],
    answer: 0,
    explain: 'To wear glasses in Japanese is expressed as "眼鏡をかける" (megane o kakeru).'
  },
  {
    q: 'What is the Japanese word for "Grandfather"?',
    options: ['祖父 (そふ) / おじいさん', '祖母 (そぼ) / おばあさん', '叔父 (おじ)', '叔母 (おば)'],
    answer: 0,
    explain: '"祖父" (sofu) is your own grandfather; "おじいさん" (ojiisan) is grandfather in general.'
  },
  {
    q: 'What is the Japanese word for "Grandmother"?',
    options: ['祖母 (そぼ) / おばあさん', '祖父 (そふ) / おじいさん', '叔父 (おじ)', '叔母 (おば)'],
    answer: 0,
    explain: '"祖母" (sobo) is your own grandmother; "おばあさん" (obaasan) is grandmother.'
  },
  {
    q: 'What is the Japanese word for "Uncle"?',
    options: ['おじ', 'おば', 'いとこ', 'かぞく'],
    answer: 0,
    explain: '"おじ" (oji) means uncle.'
  },
  {
    q: 'What is the Japanese word for "Cousin"?',
    options: ['いとこ', 'おじ', 'おば', 'きょうだい'],
    answer: 0,
    explain: '"いとこ" (itoko) means cousin.'
  },
  {
    q: 'What does the verb "あやまる" (ayamaru) mean?',
    options: ['To apologize', 'To thank', 'To ask', 'To say'],
    answer: 0,
    explain: '"あやまる" (ayamaru) means to apologize.'
  },
  {
    q: 'What is the Japanese word for "Self-introduction"?',
    options: ['自己紹介 (じこしょうかい)', '相談 (そうだん)', '案内 (あんない)', '連絡 (れんらく)'],
    answer: 0,
    explain: '"自己紹介" (jiko shoukai) means self-introduction.'
  },
  {
    q: 'What is the Japanese word for "Contact / Liaison"?',
    options: ['連絡 (れんらく)', '自己紹介 (じこしょうかい)', '相談 (そうだん)', '案内 (あんない)'],
    answer: 0,
    explain: '"連絡" (renraku) means contact, connection, or messaging.'
  },
  {
    q: 'What does the expression "お邪魔します" (ojama shimasu) mean?',
    options: ['Excuse me for disturbing (said when entering someone\'s house)', 'Thank you for the meal', 'Good morning', 'Goodbye'],
    answer: 0,
    explain: '"お邪魔します" (ojama shimasu, literally "I am going to get in the way") is the standard polite greeting when entering someone\'s house.'
  },

  // --------------------------------------------------------------------------
  // KANJI & READINGS (151-200)
  // --------------------------------------------------------------------------
  {
    q: 'What is the correct Hiragana reading for the Kanji "社会"?',
    options: ['しゃかい', 'じゃかい', 'しゃがい', 'じゃがい'],
    answer: 0,
    explain: '"社会" (society) is read as "しゃかい" (shakai).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "神社"?',
    options: ['じんじゃ', 'しんじゃ', 'じんしゃ', 'しんしゃ'],
    answer: 0,
    explain: '"神社" (Shinto shrine) is read as "じんじゃ" (jinja).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "病院"?',
    options: ['びょういん', 'びよういん', 'ひょういん', 'へいいん'],
    answer: 0,
    explain: '"病院" (hospital) is read as "びょういん" (byouin). "美容院" (beauty salon) is read as びよういん.'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "美容院"?',
    options: ['びよういん', 'びょういん', 'ひょういん', 'びやいん'],
    answer: 0,
    explain: '"美容院" (beauty salon) is read as "びよういん" (biyouin).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "作文"?',
    options: ['さくぶん', 'さっぶん', 'さくもん', 'さっこん'],
    answer: 0,
    explain: '"作文" (essay / composition) is read as "さくぶん" (sakubun).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "運動"?',
    options: ['うんどう', 'うんど', 'こうどう', 'こんど'],
    answer: 0,
    explain: '"運動" (exercise / sports) is read as "うんどう" (undou).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "授業"?',
    options: ['じゅぎょう', 'じゅごう', 'しゅぎょう', 'じょうぎょう'],
    answer: 0,
    explain: '"授業" (class / lesson) is read as "じゅぎょう" (jugyou).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "試験"?',
    options: ['しけん', 'しっけん', 'じけん', 'しけんう'],
    answer: 0,
    explain: '"試験" (examination) is read as "しけん" (shiken).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "計画"?',
    options: ['けいかく', 'けいご', 'けいかつ', 'けいが'],
    answer: 0,
    explain: '"計画" (plan / project) is read as "けいかく" (keikaku).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "地理"?',
    options: ['ちり', 'じり', 'ちりょう', 'ちがく'],
    answer: 0,
    explain: '"地理" (geography) is read as "ちり" (chiri).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "歴史"?',
    options: ['れきし', 'れきしん', 'れくし', 'りきし'],
    answer: 0,
    explain: '"歴史" (history) is read as "れきし" (rekishi).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "科学"?',
    options: ['かがく', 'けがく', 'こうがく', 'きがく'],
    answer: 0,
    explain: '"科学" (science) is read as "かがく" (kagaku).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "文学"?',
    options: ['ぶんがく', 'もんがく', 'ふんがく', 'びがく'],
    answer: 0,
    explain: '"文学" (literature) is read as "ぶんがく" (bungaku).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "小説"?',
    options: ['しょうせつ', 'しょうせっ', 'そうせつ', 'しょせつ'],
    answer: 0,
    explain: '"小説" (novel) is read as "しょうせつ" (shousetsu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "注意"?',
    options: ['ちゅうい', 'しゅうい', 'ちゅい', 'ちゅうき'],
    answer: 0,
    explain: '"注意" (attention / warning) is read as "ちゅうい" (chuui).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "意見"?',
    options: ['いけん', 'いげん', 'いけんう', 'おけん'],
    answer: 0,
    explain: '"意見" (opinion) is read as "いけん" (iken).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "安全"?',
    options: ['あんぜん', 'かんぜん', 'しんぜん', 'おんぜん'],
    answer: 0,
    explain: '"安全" (safety) is read as "あんぜん" (anzen). "完全" (complete) is read as かんぜん.'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "目的"?',
    options: ['もくてき', 'めくてき', 'もくひょう', 'もくてっ'],
    answer: 0,
    explain: '"目的" (purpose / goal) is read as "もくてき" (mokuteki).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "貿易"?',
    options: ['ぼうえき', 'ぼうぎ', 'ほうえき', 'ほうえきっ'],
    answer: 0,
    explain: '"貿易" (foreign trade) is read as "ぼうえき" (boueki).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "輸出"?',
    options: ['ゆしゅつ', 'ゆしゅっ', 'ようしゅつ', 'ゆすつ'],
    answer: 0,
    explain: '"輸出" (export) is read as "ゆしゅつ" (yushutsu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "輸入"?',
    options: ['ゆにゅう', 'ゆにゅっ', 'ゆうにゅう', 'ゆにう'],
    answer: 0,
    explain: '"輸入" (import) is read as "ゆにゅう" (yunyuu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "結果"?',
    options: ['けっか', 'けつか', 'けつが', 'けっが'],
    answer: 0,
    explain: '"結果" (result) is read as "けっか" (kekka).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "連絡"?',
    options: ['れんらく', 'てんらく', 'せんらく', 'けんらく'],
    answer: 0,
    explain: '"連絡" (contact) is read as "れんらく" (renraku).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "相手"?',
    options: ['あいて', 'そうしゅ', 'あいで', 'あいてが'],
    answer: 0,
    explain: '"相手" (partner/opponent) is read as "あいて" (aite).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "都合"?',
    options: ['つごう', 'とごう', 'つあい', 'づごう'],
    answer: 0,
    explain: '"都合" (convenience) is read as "つごう" (tsugou).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "特別"?',
    options: ['とくべつ', 'とくべっ', 'どくべつ', 'とくべつに'],
    answer: 0,
    explain: '"特別" (special) is read as "とくべつ" (tokubetsu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "普通"?',
    options: ['ふつう', 'ふづう', 'ほうつう', 'ふっつう'],
    answer: 0,
    explain: '"普通" (ordinary/standard) is read as "ふつう" (futsuu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "説明"?',
    options: ['せつめい', 'ぜつめい', 'せつみょう', 'せっめい'],
    answer: 0,
    explain: '"説明" (explanation) is read as "せつめい" (setsumei).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "道具"?',
    options: ['どうぐ', 'とうぐ', 'どうく', 'とうく'],
    answer: 0,
    explain: '"道具" (tool) is read as "どうぐ" (dougu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "家具"?',
    options: ['かぐ', 'いえぐ', 'かき', 'やぐ'],
    answer: 0,
    explain: '"家具" (furniture) is read as "かぐ" (kagu).'
  },
  {
    q: 'What is the correct Kanji for the reading "keiken" (experience)?',
    options: ['経験', '準備', '相談', '説明'],
    answer: 0,
    explain: '"経験" is read as "けいけん" (keiken).'
  },
  {
    q: 'What is the correct Kanji for the reading "shoukai" (introduction)?',
    options: ['紹介', '相談', '案内', '説明'],
    answer: 0,
    explain: '"紹介" is read as "しょうかい" (shoukai).'
  },
  {
    q: 'What is the correct Kanji for the reading "annai" (guidance)?',
    options: ['案内', '紹介', '説明', '注意'],
    answer: 0,
    explain: '"案内" is read as "あんない" (annai).'
  },
  {
    q: 'What is the correct Kanji for the reading "shiraberu" (to look up/check)?',
    options: ['調べる', '比べる', '壊れる', '落ちる'],
    answer: 0,
    explain: '"調べる" is read as "しらべる" (shiraberu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "交通"?',
    options: ['こうつう', 'こうずう', 'ごうつう', 'こつう'],
    answer: 0,
    explain: '"交通" (traffic / transport) is read as "こうつう" (koutsuu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "法律"?',
    options: ['ほうりつ', 'ほうりっ', 'ほうちつ', 'ほうせい'],
    answer: 0,
    explain: '"法律" (law) is read as "ほうりつ" (houritsu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "政治"?',
    options: ['せいじ', 'しょうじ', 'せいし', 'ぜいじ'],
    answer: 0,
    explain: '"政治" (politics / government) is read as "せいじ" (seiji).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "経済"?',
    options: ['けいざい', 'けいさい', 'けいじ', 'げいざい'],
    answer: 0,
    explain: '"経済" (economics / economy) is read as "けいざい" (keizai).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "世界"?',
    options: ['せかい', 'せがい', 'せいかい', 'せいがい'],
    answer: 0,
    explain: '"世界" (world) is read as "せかい" (sekai).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "理由"?',
    options: ['りゆう', 'じゆう', 'りよう', 'ゆうり'],
    answer: 0,
    explain: '"理由" (reason) is read as "りゆう" (riyuu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "心配"?',
    options: ['しんぱい', 'じんばい', 'しんばい', 'じんぱい'],
    answer: 0,
    explain: '"心配" (worry / anxiety) is read as "しんぱい" (shinpai).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "予定"?',
    options: ['よてい', 'よでい', 'よどう', 'よてっ'],
    answer: 0,
    explain: '"予定" (plan / schedule) is read as "よてい" (yotei).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "約束"?',
    options: ['やくそく', 'やくそっ', 'よくそく', 'がいそく'],
    answer: 0,
    explain: '"約束" (promise / appointment) is read as "やくそく" (yakusoku).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "相談"?',
    options: ['そうだん', 'しょうだん', 'しょうさん', 'ぞうだん'],
    answer: 0,
    explain: '"相談" (consultation) is read as "そうだん" (soudan).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "技術"?',
    options: ['ぎじゅつ', 'わざじゅつ', 'きじゅつ', 'ぎしゅつ'],
    answer: 0,
    explain: '"技術" (technology / technique) is read as "ぎじゅつ" (gijutsu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "製品"?',
    options: ['せいひん', 'せいびん', 'せいもん', 'せいぴん'],
    answer: 0,
    explain: '"製品" (manufactured product) is read as "せいひん" (seihin).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "機械"?',
    options: ['きかい', 'きがい', 'きかいっ', 'こうかい'],
    answer: 0,
    explain: '"機械" (machine / mechanism) is read as "きかい" (kikai).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "台風"?',
    options: ['たいふう', 'たいふ', 'だいふう', 'こかぜ'],
    answer: 0,
    explain: '"台風" (typhoon/hurricane) is read as "たいふう" (taifu).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "報告"?',
    options: ['ほうこく', 'ほうこっ', 'ぼうこく', 'ほうごく'],
    answer: 0,
    explain: '"報告" (report) is read as "ほうこく" (houkokou).'
  },
  {
    q: 'What is the correct Hiragana reading for the Kanji "準備"?',
    options: ['じゅんび', 'じゅんぴ', 'しゅんび', 'しゅんぴ'],
    answer: 0,
    explain: '"準備" (preparation / arrangements) is read as "じゅんび" (junbi).'
  }
];

// ============================================================================
// INTEGRITY, SCHEMA & DUPLICATE VALIDATION
// ============================================================================

console.log('🚀 Running JLPT N4 Question Bank verification...');

if (quizzes.length !== 200) {
  console.error(`❌ Validation failed: Got ${quizzes.length} questions, expected exactly 200!`);
  process.exit(1);
}

const questionTexts = new Set();

quizzes.forEach((item, index) => {
  const qNum = index + 1;
  
  if (!item.q || typeof item.q !== 'string' || item.q.trim() === '') {
    console.error(`❌ Question ${qNum} has an invalid or empty 'q' property.`);
    process.exit(1);
  }
  
  const normalizedQ = item.q.trim().toLowerCase();
  if (questionTexts.has(normalizedQ)) {
    console.error(`❌ Duplicate question detected at Question ${qNum}: "${item.q}"`);
    process.exit(1);
  }
  questionTexts.add(normalizedQ);
  
  if (!item.options || !Array.isArray(item.options) || item.options.length !== 4) {
    console.error(`❌ Question ${qNum} must have exactly 4 choices.`);
    process.exit(1);
  }
  
  const optionTexts = new Set();
  item.options.forEach((opt, oIdx) => {
    if (!opt || typeof opt !== 'string' || opt.trim() === '') {
      console.error(`❌ Question ${qNum} choice ${oIdx} is invalid or empty.`);
      process.exit(1);
    }
    const normalizedOpt = opt.trim().toLowerCase();
    if (optionTexts.has(normalizedOpt)) {
      console.error(`❌ Duplicate choice option detected in Question ${qNum}: "${opt}"`);
      process.exit(1);
    }
    optionTexts.add(normalizedOpt);
  });
  
  if (typeof item.answer !== 'number' || item.answer < 0 || item.answer > 3) {
    console.error(`❌ Question ${qNum} answer index '${item.answer}' is out of bounds (must be 0, 1, 2, or 3).`);
    process.exit(1);
  }
  
  if (!item.explain || typeof item.explain !== 'string' || item.explain.trim() === '') {
    console.error(`❌ Question ${qNum} explanation is invalid or empty.`);
    process.exit(1);
  }
});

console.log('✅ All 200 N4 questions successfully passed schema validation & duplicate checking!');

// ============================================================================
// INJECT INTO EDUCATION.HTML
// ============================================================================

const eduPath = path.join(__dirname, '..', 'education.html');
console.log(`📖 Reading education.html from ${eduPath}...`);
let htmlContent = fs.readFileSync(eduPath, 'utf8').replace(/\r\n/g, '\n');

// Find start and end of quizzes block under JLPT_DATA[4]
// The structure is:
//   4: {
//     lesson: {
//       ...
//     },
//     quizzes: [
//       ...
//     ]
//   },
const quizzesStartMarker = '4: {\n    lesson: {\n      headline: \'JLPT N4 (Elementary) — Verb Conjugations & Adjectives\',\n      lead: \'Progressing from polite styles to basic plain/casual formats. Developing competency in fluid spoken expressions and complex conditional phrases.\',\n      bullets: [\n        \'<strong>Verb Forms:</strong> Plain/Dictionary Form (to eat - たべる), Negative Form (tabenai - たべない), Past Form (tabeta - たべた), and Te-form (tabete - たべた).\',\n        \'<strong>The Vital Te-form (~て):</strong> Used to link actions, make polite requests (~て ください), and represent ongoing states (~て いる).\',\n        \'<strong>Conditional Structures:</strong> ~たら (tara - if/when general condition), ~と (to - natural/inevitable consequence, e.g. "when spring comes, flowers bloom").\',\n        \'<strong>Adjective Conjugations:</strong> I-adjectives (e.g. さむい) vs Na-adjectives (e.g. しずかな). Past negative of さむい is 寒くなかった (samukunakatta).\'\n      ]\n    },\n    quizzes: [';

const quizzesEndMarker = ']\n  },\n  3: {';

const startIndex = htmlContent.indexOf(quizzesStartMarker);
if (startIndex === -1) {
  console.error('❌ Could not locate the JLPT N4 quizzes start marker in education.html.');
  process.exit(1);
}

const endIndex = htmlContent.indexOf(quizzesEndMarker, startIndex);
if (endIndex === -1) {
  console.error('❌ Could not locate the JLPT N4 quizzes end marker in education.html.');
  process.exit(1);
}

console.log('🔄 Formulating JSON structure for quizzes...');
const formattedQuizzes = JSON.stringify(quizzes, null, 8);

// Adjust formatting: replace outer bracket brackets with clean alignment
const startPart = htmlContent.substring(0, startIndex + quizzesStartMarker.length);
const endPart = htmlContent.substring(endIndex);

const updatedHtml = startPart + '\n' + formattedQuizzes.substring(8, formattedQuizzes.length - 1) + '    ' + endPart;

console.log('✍️ Writing updated education.html back...');
// Restore CRLF line endings when writing on Windows
fs.writeFileSync(eduPath, updatedHtml.replace(/\n/g, '\r\n'), 'utf8');

console.log('🎉 Successfully added and verified 200 N4 JLPT questions inside education.html!');
