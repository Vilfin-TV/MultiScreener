const fs = require('fs');

const txt = fs.readFileSync('jlpt_textbook_data.js', 'utf8');
const JLPT_TEXTBOOK = eval(txt + '\nJLPT_TEXTBOOK;');

const newReading = {
  "5": [
    {
      "title": "読解問題 1 (Reading 1)",
      "passage": "わたしは 毎朝 ７時に 起きます。朝ごはんを 食べて、８時に うちを 出ます。電車で 会社へ 行きます。会社は ９時から ５時まで です。うちへ 帰ってから、テレビを 見ます。それから、１１時ごろ 寝ます。",
      "translation": "I wake up at 7 every morning. I eat breakfast and leave the house at 8. I go to the company by train. The company is from 9 to 5. After I go home, I watch TV. Then, I go to bed around 11.",
      "vocabulary": [ { "ja": "毎朝 (まいあさ)", "en": "Every morning" }, { "ja": "帰ってから (かえってから)", "en": "After returning" } ],
      "questions": [
        { "q": "この人は 何時ごろ 寝ますか。", "a": "１１時ごろ 寝ます。" },
        { "q": "会社は 何時に 終わりますか。", "a": "５時に 終わります。" }
      ]
    },
    {
      "title": "読解問題 2 (Reading 2)",
      "passage": "きのうは 日曜日でしたから、友達と 東京へ 行きました。東京で くつを 買いました。とても 高かったです。それから、レストランで 昼ごはんを 食べました。レストランは 混んでいました。",
      "translation": "Yesterday was Sunday, so I went to Tokyo with a friend. I bought shoes in Tokyo. They were very expensive. Then, we ate lunch at a restaurant. The restaurant was crowded.",
      "vocabulary": [ { "ja": "日曜日 (にちようび)", "en": "Sunday" }, { "ja": "混んでいました (こんでいました)", "en": "Was crowded" } ],
      "questions": [
        { "q": "どこで くつを 買いましたか。", "a": "東京で 買いました。" },
        { "q": "くつは 安かったですか。", "a": "いいえ、とても 高かったです。" }
      ]
    },
    {
      "title": "読解問題 3 (Reading 3)",
      "passage": "田中さんの うちは 新しいです。部屋が ３つ あります。テレビや 冷蔵庫などの 電化製品は まだ ありません。明日、買いに 行きます。",
      "translation": "Tanaka-san's house is new. There are 3 rooms. There are no appliances like a TV or refrigerator yet. He will go buy them tomorrow.",
      "vocabulary": [ { "ja": "新しい (あたらしい)", "en": "New" }, { "ja": "電化製品 (でんかせいひん)", "en": "Home appliances" } ],
      "questions": [
        { "q": "田中さんの うちに 部屋は いくつ ありますか。", "a": "３つ あります。" },
        { "q": "田中さんは 明日 何を しますか。", "a": "テレビなどを 買いに 行きます。" }
      ]
    },
    {
      "title": "読解問題 4 (Reading 4)",
      "passage": "先週の 土曜日に パーティーを しました。山田さんは ギターを 弾きました。佐藤さんは 歌を 歌いました。料理は 母が 作りました。おいしかったです。",
      "translation": "We had a party last Saturday. Yamada-san played the guitar. Sato-san sang a song. My mother cooked the food. It was delicious.",
      "vocabulary": [ { "ja": "弾きました (ひきました)", "en": "Played (instrument)" }, { "ja": "料理 (りょうり)", "en": "Cooking/Food" } ],
      "questions": [
        { "q": "誰が 料理を 作りましたか。", "a": "母が 作りました。" },
        { "q": "佐藤さんは 何を しましたか。", "a": "歌を 歌いました。" }
      ]
    }
  ],
  "4": [
    {
      "title": "読解問題 1 (Reading 1)",
      "passage": "私は日本の文化に興味があります。特に、着物や茶道が好きです。来年、日本へ行って、お茶の作り方を習いたいです。そのために、今日本語を一生懸命勉強しています。",
      "translation": "I am interested in Japanese culture. In particular, I like kimono and tea ceremony. Next year, I want to go to Japan and learn how to make tea. For that reason, I am studying Japanese very hard right now.",
      "vocabulary": [ { "ja": "文化 (ぶんか)", "en": "Culture" }, { "ja": "茶道 (さどう)", "en": "Tea ceremony" } ],
      "questions": [
        { "q": "筆者はなぜ日本語を勉強していますか。", "a": "日本で茶道を習いたいからです。" },
        { "q": "筆者は日本の何が好きですか。", "a": "着物や茶道です。" }
      ]
    },
    {
      "title": "読解問題 2 (Reading 2)",
      "passage": "最近、パソコンで仕事をする人が増えています。便利ですが、一日中座っているので、体に悪いです。時々休んで、運動をしたほうがいいです。",
      "translation": "Recently, the number of people working on computers is increasing. It's convenient, but because they sit all day, it's bad for the body. It is better to take a break sometimes and exercise.",
      "vocabulary": [ { "ja": "増えている (ふえている)", "en": "Is increasing" }, { "ja": "運動 (うんどう)", "en": "Exercise" } ],
      "questions": [
        { "q": "パソコンで仕事をするのはなぜ体に悪いですか。", "a": "一日中座っているからです。" },
        { "q": "どうしたほうがいいと言っていますか。", "a": "時々休んで、運動をしたほうがいいと言っています。" }
      ]
    },
    {
      "title": "読解問題 3 (Reading 3)",
      "passage": "私の趣味は写真を撮ることです。週末はよく山や海へ行って、きれいな景色の写真を撮ります。将来、自分の写真の展覧会を開くのが夢です。",
      "translation": "My hobby is taking pictures. On weekends, I often go to the mountains or the sea and take pictures of beautiful scenery. In the future, my dream is to hold my own photography exhibition.",
      "vocabulary": [ { "ja": "趣味 (しゅみ)", "en": "Hobby" }, { "ja": "展覧会 (てんらんかい)", "en": "Exhibition" } ],
      "questions": [
        { "q": "筆者は週末どこへ行きますか。", "a": "山や海へ行きます。" },
        { "q": "筆者の夢は何ですか。", "a": "写真の展覧会を開くことです。" }
      ]
    },
    {
      "title": "読解問題 4 (Reading 4)",
      "passage": "地球温暖化が進んでいます。私たちにできることは、電気を大切に使ったり、ゴミを減らしたりすることです。小さなことでも、みんなでやれば大きな力になります。",
      "translation": "Global warming is advancing. What we can do is use electricity carefully and reduce garbage. Even small things can become a great power if everyone does them.",
      "vocabulary": [ { "ja": "地球温暖化 (ちきゅうおんだんか)", "en": "Global warming" }, { "ja": "減らす (へらす)", "en": "To reduce" } ],
      "questions": [
        { "q": "私たちにできることは何ですか。", "a": "電気を大切に使ったり、ゴミを減らしたりすることです。" },
        { "q": "小さなことでも、みんなでやればどうなりますか。", "a": "大きな力になります。" }
      ]
    }
  ],
  "3": [
    {
      "title": "読解問題 1 (Reading 1)",
      "passage": "現代の社会において、スマートフォンは必要不可欠なものとなっている。連絡手段としてだけでなく、情報の検索や娯楽としても広く利用されている。しかし、それに依存しすぎるあまり、人との直接の会話が減っているという問題も指摘されている。",
      "translation": "In modern society, smartphones have become essential. They are widely used not only as a means of communication, but also for searching for information and for entertainment. However, the problem has been pointed out that direct conversation with people is decreasing because of too much dependence on them.",
      "vocabulary": [ { "ja": "必要不可欠 (ひつようふかけつ)", "en": "Absolutely necessary" }, { "ja": "依存 (いぞん)", "en": "Dependence" } ],
      "questions": [
        { "q": "スマートフォンの問題点として何が挙げられていますか。", "a": "依存しすぎて人との直接の会話が減っていること。" },
        { "q": "スマートフォンは何のために利用されていますか。", "a": "連絡手段、情報検索、娯楽のため。" }
      ]
    },
    {
      "title": "読解問題 2 (Reading 2)",
      "passage": "健康を維持するためには、バランスの取れた食事と適度な運動が欠かせない。特に朝食をしっかり取ることは、一日のエネルギー源となるため重要である。忙しい現代人は朝食を抜きがちだが、少し早起きしてでも食べる習慣をつけるべきだ。",
      "translation": "In order to maintain health, a balanced diet and moderate exercise are essential. Especially, eating a solid breakfast is important because it becomes the energy source for the day. Busy modern people tend to skip breakfast, but they should make a habit of eating it even if they wake up a little early.",
      "vocabulary": [ { "ja": "維持 (いじ)", "en": "Maintenance" }, { "ja": "抜きがち (ぬきがち)", "en": "Tend to skip" } ],
      "questions": [
        { "q": "筆者は朝食についてどう考えていますか。", "a": "一日のエネルギー源になるため、しっかり食べるべきだと考えている。" },
        { "q": "忙しい現代人に何を勧めていますか。", "a": "少し早起きしてでも朝食を食べる習慣をつけること。" }
      ]
    },
    {
      "title": "読解問題 3 (Reading 3)",
      "passage": "最近、リモートワークが普及し、自宅で仕事をする人が増えた。通勤時間がなくなり、家族と過ごす時間が増えるというメリットがある一方で、仕事とプライベートの境界線が曖昧になり、ストレスを感じる人も少なくない。",
      "translation": "Recently, remote work has become widespread, and the number of people working at home has increased. While there is the merit of eliminating commuting time and increasing time spent with family, not a few people feel stress because the boundary between work and private life becomes ambiguous.",
      "vocabulary": [ { "ja": "普及 (ふきゅう)", "en": "Spread/diffusion" }, { "ja": "境界線 (きょうかいせん)", "en": "Boundary line" } ],
      "questions": [
        { "q": "リモートワークのメリットは何ですか。", "a": "通勤時間がなくなり、家族と過ごす時間が増えること。" },
        { "q": "なぜストレスを感じる人がいますか。", "a": "仕事とプライベートの境界線が曖昧になるから。" }
      ]
    },
    {
      "title": "読解問題 4 (Reading 4)",
      "passage": "読書は知識を得るだけでなく、想像力を豊かにする効果がある。文字だけで書かれた物語を読むことで、脳は情景を思い浮かべるために活発に働く。動画を見るのとは違った脳の使い方ができるため、子供の教育にも良いとされている。",
      "translation": "Reading books has the effect of not only gaining knowledge but also enriching imagination. By reading a story written only in letters, the brain works actively to imagine the scene. Since it uses the brain differently than watching videos, it is said to be good for children's education as well.",
      "vocabulary": [ { "ja": "想像力 (そうぞうりょく)", "en": "Imagination" }, { "ja": "情景 (じょうけい)", "en": "Scene/spectacle" } ],
      "questions": [
        { "q": "読書の効果は何ですか。", "a": "知識を得ることと、想像力を豊かにすること。" },
        { "q": "なぜ読書は子供の教育に良いとされていますか。", "a": "動画を見るのとは違い、文字から情景を思い浮かべることで脳が活発に働くから。" }
      ]
    }
  ],
  "2": [
    {
      "title": "読解問題 1 (Reading 1)",
      "passage": "近年、人工知能（AI）の技術が急速に進化しており、私たちの生活の様々な場面で活用されるようになっている。しかし、AIが人間の仕事を奪うのではないかという懸念の声も上がっている。技術の進歩を恐れるのではなく、どのように共存し、活用していくかを模索することが今後の課題と言えるだろう。",
      "translation": "In recent years, artificial intelligence (AI) technology has rapidly evolved and is being utilized in various scenes of our lives. However, there are growing concerns that AI might take away human jobs. Rather than fearing the progress of technology, exploring how to coexist and utilize it can be said to be the challenge for the future.",
      "vocabulary": [ { "ja": "懸念 (けねん)", "en": "Concern" }, { "ja": "模索 (もさく)", "en": "Groping for / exploring" } ],
      "questions": [
        { "q": "AIに対する人々の懸念は何ですか。", "a": "人間の仕事を奪うのではないかということ。" },
        { "q": "筆者は今後の課題は何だと述べていますか。", "a": "AIを恐れるのではなく、どのように共存し活用していくかを模索すること。" }
      ]
    },
    {
      "title": "読解問題 2 (Reading 2)",
      "passage": "環境保護の観点から、プラスチック製品の削減が世界的な課題となっている。レジ袋の有料化や紙製ストローの導入など、身近なところから変化が始まっているが、企業だけでなく消費者一人一人の意識改革が求められている。利便性ばかりを追求するライフスタイルを見直す時期に来ているのではないか。",
      "translation": "From the perspective of environmental protection, the reduction of plastic products has become a global issue. Changes are starting from familiar places, such as charging for plastic bags and introducing paper straws, but a change in consciousness is required not only from companies but from each individual consumer. It may be time to reconsider lifestyles that pursue only convenience.",
      "vocabulary": [ { "ja": "削減 (さくげん)", "en": "Reduction" }, { "ja": "利便性 (りべんせい)", "en": "Convenience" } ],
      "questions": [
        { "q": "プラスチック製品削減のために、誰の意識改革が求められていますか。", "a": "企業だけでなく、消費者一人一人の意識改革。" },
        { "q": "筆者はどのようなライフスタイルを見直すべきだと主張していますか。", "a": "利便性ばかりを追求するライフスタイル。" }
      ]
    },
    {
      "title": "読解問題 3 (Reading 3)",
      "passage": "多様性（ダイバーシティ）を尊重する社会の実現が叫ばれて久しい。性別や国籍、年齢にとらわれず、誰もが能力を発揮できる環境づくりが求められている。しかし、制度を整えるだけでは不十分であり、無意識の偏見（アンコンシャス・バイアス）に気づき、それを乗り越える個人の努力が不可欠である。",
      "translation": "It has been a long time since the realization of a society that respects diversity has been called for. Creating an environment where everyone can demonstrate their abilities, regardless of gender, nationality, or age, is required. However, simply adjusting systems is insufficient; the personal effort to realize and overcome unconscious bias is indispensable.",
      "vocabulary": [ { "ja": "多様性 (たようせい)", "en": "Diversity" }, { "ja": "偏見 (へんけん)", "en": "Bias / prejudice" } ],
      "questions": [
        { "q": "多様性を尊重する社会を実現するために不可欠なことは何ですか。", "a": "制度を整えるだけでなく、無意識の偏見に気づき乗り越える個人の努力。" },
        { "q": "どのような環境づくりが求められていますか。", "a": "性別や国籍、年齢にとらわれず、誰もが能力を発揮できる環境。" }
      ]
    },
    {
      "title": "読解問題 4 (Reading 4)",
      "passage": "少子高齢化が進む日本において、地域コミュニティの役割が再び見直されている。かつてのような密接な近所付き合いは減少しつつあるが、災害時の助け合いや高齢者の見守りなど、地域住民同士のネットワークが果たす役割は依然として大きい。新たな形でのコミュニティ形成が急務となっている。",
      "translation": "In Japan, where the birthrate is declining and the population is aging, the role of local communities is being reconsidered. Close neighborhood relationships like in the past are decreasing, but the role played by networks of local residents, such as mutual help during disasters and watching over the elderly, remains significant. Forming communities in a new shape has become an urgent task.",
      "vocabulary": [ { "ja": "少子高齢化 (しょうしこうれいか)", "en": "Declining birthrate and aging population" }, { "ja": "急務 (きゅうむ)", "en": "Urgent business/task" } ],
      "questions": [
        { "q": "地域住民同士のネットワークはどのような時に役立ちますか。", "a": "災害時の助け合いや高齢者の見守りなど。" },
        { "q": "筆者は現在の日本において何が急務だと述べていますか。", "a": "新たな形での地域コミュニティを形成すること。" }
      ]
    }
  ],
  "1": [
    {
      "title": "読解問題 1 (Reading 1)",
      "passage": "情報化社会の進展に伴い、情報リテラシーの重要性が飛躍的に高まっている。膨大な情報の中から真偽を見極め、必要な情報を適切に取捨選択する能力は、もはや現代を生き抜くための必須スキルと言えよう。偏った情報に翻弄されることなく、多角的な視点から物事を捉える姿勢が不可欠である。",
      "translation": "With the advancement of the information society, the importance of information literacy has risen dramatically. The ability to discern truth from falsehood among vast amounts of information and appropriately select necessary information can now be said to be an essential skill for surviving in the modern age. An attitude of grasping things from multiple perspectives, without being swayed by biased information, is indispensable.",
      "vocabulary": [ { "ja": "飛躍的 (ひやくてき)", "en": "Dramatic / leaps and bounds" }, { "ja": "翻弄される (ほんろうされる)", "en": "To be at the mercy of / toyed with" } ],
      "questions": [
        { "q": "現代において必須とされるスキルは何ですか。", "a": "膨大な情報の中から真偽を見極め、必要な情報を適切に取捨選択する情報リテラシー。" },
        { "q": "情報に接する際、どのような姿勢が求められますか。", "a": "偏った情報に翻弄されず、多角的な視点から物事を捉える姿勢。" }
      ]
    },
    {
      "title": "読解問題 2 (Reading 2)",
      "passage": "グローバル化が加速する中、異文化コミュニケーションの障壁をいかに乗り越えるかが問われている。単に言語を習得するだけでなく、その背後にある歴史や価値観を深く理解し、他者を尊重する態度が前提となる。自らの枠組みにとらわれず、柔軟に異質なものを受け入れる寛容さが求められる。",
      "translation": "As globalization accelerates, how to overcome the barriers of cross-cultural communication is being questioned. It is premised not only on merely acquiring language, but on deeply understanding the history and values behind it and maintaining an attitude of respecting others. Tolerance to flexibly accept heterogeneous things without being caught in one's own framework is required.",
      "vocabulary": [ { "ja": "障壁 (しょうへき)", "en": "Barrier" }, { "ja": "寛容さ (かんようさ)", "en": "Tolerance" } ],
      "questions": [
        { "q": "異文化コミュニケーションにおいて、言語習得以外に何が必要だと述べていますか。", "a": "その背後にある歴史や価値観を深く理解し、他者を尊重する態度。" },
        { "q": "他者と接する際、どのような心構えが求められますか。", "a": "自らの枠組みにとらわれず、柔軟に異質なものを受け入れる寛容さ。" }
      ]
    },
    {
      "title": "読解問題 3 (Reading 3)",
      "passage": "科学技術の発展は人類に多大な恩恵をもたらしてきた一方で、倫理的な課題も突きつけている。生命倫理やAIの自律性に関する議論は、技術の進歩に追いついていないのが現状である。技術がもたらす光と影を直視し、社会全体でどのように制御していくべきか、根本的な議論を深める必要がある。",
      "translation": "While the development of science and technology has brought enormous benefits to humanity, it also poses ethical challenges. The current situation is that discussions on bioethics and AI autonomy have not caught up with the progress of technology. It is necessary to face squarely the light and shadow brought about by technology and deepen fundamental discussions on how society as a whole should control it.",
      "vocabulary": [ { "ja": "恩恵 (おんけい)", "en": "Benefit / blessing" }, { "ja": "直視する (ちょくしする)", "en": "To look straight at / face squarely" } ],
      "questions": [
        { "q": "科学技術の発展がもたらした現状の課題は何ですか。", "a": "生命倫理やAIの自律性に関する倫理的な議論が技術の進歩に追いついていないこと。" },
        { "q": "筆者は今後どのようにすべきだと主張していますか。", "a": "技術のもたらす光と影を直視し、社会全体でどう制御すべきか根本的な議論を深めるべきだ。" }
      ]
    },
    {
      "title": "読解問題 4 (Reading 4)",
      "passage": "都市への人口集中が引き起こす地方の過疎化は、深刻な社会問題として立ちはだかっている。地方創生を掲げ、若者の移住を促す様々な施策が打たれているものの、根本的な解決には至っていない。その地域の独自の魅力を再発掘し、持続可能な産業を育成することが、真の地方再生の鍵となる。",
      "translation": "The depopulation of rural areas caused by the concentration of population in cities stands as a serious social problem. Although various measures have been taken under the banner of regional revitalization to encourage young people to migrate, a fundamental solution has not been reached. Rediscovering the unique charm of the region and nurturing sustainable industries holds the key to true regional revitalization.",
      "vocabulary": [ { "ja": "過疎化 (かそか)", "en": "Depopulation" }, { "ja": "立ちはだかる (たちはだかる)", "en": "To stand in the way" } ],
      "questions": [
        { "q": "地方の過疎化はなぜ起きていますか。", "a": "都市へ人口が集中しているため。" },
        { "q": "真の地方再生の鍵は何だと述べていますか。", "a": "地域の独自の魅力を再発掘し、持続可能な産業を育成すること。" }
      ]
    }
  ]
};

const newListening = {
  "5": [
    {
      "title": "聴解問題 1 (Listening 1)",
      "context": "男の人と女の人が話しています。男の人は明日、何時に起きますか。",
      "transcript": "男：明日は日曜日ですね。ゆっくり休みますか。\n女：いいえ、明日は６時に起きて、出かけます。\n男：早いですね。私はいつも８時に起きますが、明日は９時に起きます。",
      "key_phrases": [ { "ja": "何時に起きますか", "en": "What time will you wake up?" }, { "ja": "ゆっくり休みます", "en": "Rest slowly/relax" } ],
      "questions": [ { "q": "男の人は明日、何時に起きますか。", "a": "９時に起きます。" } ]
    },
    {
      "title": "聴解問題 2 (Listening 2)",
      "context": "女の人と男の人が電話で話しています。男の人は今、どこにいますか。",
      "transcript": "女：もしもし、今どこですか。もう駅に着きましたか。\n男：すみません。今、バスの中です。道がとても混んでいますから、少し遅れます。\n女：わかりました。駅の前の喫茶店で待っています。",
      "key_phrases": [ { "ja": "駅に着きましたか", "en": "Did you arrive at the station?" }, { "ja": "バスの中", "en": "Inside the bus" } ],
      "questions": [ { "q": "男の人は今、どこにいますか。", "a": "バスの中にいます。" } ]
    },
    {
      "title": "聴解問題 3 (Listening 3)",
      "context": "レストランで男の人と女の人が話しています。二人は何を食べますか。",
      "transcript": "男：お腹が空きましたね。何を食べますか。\n女：私はカレーがいいです。山田さんは？\n男：私はうどんにします。あ、でも、カレーも美味しそうですね。\n女：じゃあ、カレーを二つにしましょう。\n男：そうですね。",
      "key_phrases": [ { "ja": "お腹が空きました", "en": "I'm hungry" }, { "ja": "美味しそうですね", "en": "Looks delicious doesn't it" } ],
      "questions": [ { "q": "二人は何を食べますか。", "a": "カレーを食べます。" } ]
    },
    {
      "title": "聴解問題 4 (Listening 4)",
      "context": "先生が学生に話しています。学生は明日、何を持ってきますか。",
      "transcript": "先生：明日はテストをしますから、鉛筆と消しゴムを持ってきてください。辞書は使えませんから、持ってこないでください。ボールペンもだめです。",
      "key_phrases": [ { "ja": "持ってきてください", "en": "Please bring it" }, { "ja": "持ってこないでください", "en": "Please do not bring it" } ],
      "questions": [ { "q": "学生は明日、何を持ってきますか。", "a": "鉛筆と消しゴムを持ってきます。" } ]
    }
  ],
  "4": [
    {
      "title": "聴解問題 1 (Listening 1)",
      "context": "男の人と女の人が話しています。女の人はこれからどうしますか。",
      "transcript": "男：雨が降ってきましたよ。傘を持っていますか。\n女：いいえ、持っていません。困ったなあ。\n男：私の傘に入りますか。駅まで一緒に帰りましょう。\n女：ありがとうございます。助かります。",
      "key_phrases": [ { "ja": "困ったなあ", "en": "I'm in trouble / Oh dear" }, { "ja": "助かります", "en": "That helps (Thank you)" } ],
      "questions": [ { "q": "女の人はこれからどうしますか。", "a": "男の人の傘に入って、駅まで一緒に帰ります。" } ]
    },
    {
      "title": "聴解問題 2 (Listening 2)",
      "context": "店で男の人と店員が話しています。男の人はどの鞄を買いますか。",
      "transcript": "男：すみません、パソコンが入る鞄を探しているんですが。\n店員：こちらはいかがですか。黒くて、ポケットがたくさんありますよ。\n男：うーん、少し重いですね。もう少し軽くて、茶色の鞄はありませんか。\n店員：それなら、こちらが人気です。\n男：あ、いいですね。これにします。",
      "key_phrases": [ { "ja": "探しているんですが", "en": "I'm looking for..." }, { "ja": "人気です", "en": "Is popular" } ],
      "questions": [ { "q": "男の人はどの鞄を買いますか。", "a": "軽くて、茶色の鞄を買います。" } ]
    },
    {
      "title": "聴解問題 3 (Listening 3)",
      "context": "電話で女の人と男の人が話しています。男の人は、この後まず何をしますか。",
      "transcript": "女：はい、さくら商事です。\n男：鈴木です。今から会社に戻りますが、頼まれていた資料、印刷しておきましょうか。\n女：あ、それはもう終わりました。それより、帰る前に郵便局へ寄って、この手紙を出してくれませんか。\n男：わかりました。すぐ行きます。",
      "key_phrases": [ { "ja": "会社に戻ります", "en": "Returning to the company" }, { "ja": "寄って", "en": "Drop by" } ],
      "questions": [ { "q": "男の人は、この後まず何をしますか。", "a": "郵便局へ行って、手紙を出します。" } ]
    },
    {
      "title": "聴解問題 4 (Listening 4)",
      "context": "テレビのニュースでアナウンサーが話しています。明日の天気はどうなりますか。",
      "transcript": "アナウンサー：明日の天気をお伝えします。午前中はよく晴れて、暖かくなるでしょう。しかし、午後からは急に雲が多くなり、夕方には強い雨が降る見込みです。お帰りが遅くなる方は、傘をお持ちください。",
      "key_phrases": [ { "ja": "晴れて", "en": "Sunny" }, { "ja": "見込みです", "en": "Is expected to" } ],
      "questions": [ { "q": "明日の天気はどうなりますか。", "a": "午前中は晴れますが、夕方には強い雨が降ります。" } ]
    }
  ],
  "3": [
    {
      "title": "聴解問題 1 (Listening 1)",
      "context": "会社で男の人と女の人が新商品の企画について話しています。二人はどの案を採用しますか。",
      "transcript": "男：新商品のデザインだけど、A案とB案、どっちがいいと思う？\n女：A案はスタイリッシュで若者向けだけど、少しコストが高いですよね。B案はシンプルで幅広い年代に受けそうだし、予算内におさまります。\n男：うーん、今回は幅広いターゲットを狙いたいから、B案で進めようか。\n女：賛成です。",
      "key_phrases": [ { "ja": "企画 (きかく)", "en": "Planning / project" }, { "ja": "幅広い年代 (はばひろいねんだい)", "en": "Wide age range" } ],
      "questions": [ { "q": "二人はどの案を採用しますか。", "a": "B案を採用します。" } ]
    },
    {
      "title": "聴解問題 2 (Listening 2)",
      "context": "ラジオで専門家が健康について話しています。専門家が一番言いたいことは何ですか。",
      "transcript": "専門家：最近、ダイエットのために炭水化物を全く食べない人が増えています。確かに体重は一時的に減るかもしれませんが、脳のエネルギーが不足して集中力が低下したり、疲れやすくなったりします。極端な食事制限ではなく、バランスよく食べることが何より大切なのです。",
      "key_phrases": [ { "ja": "炭水化物 (たんすいかぶつ)", "en": "Carbohydrates" }, { "ja": "極端な (きょくたんな)", "en": "Extreme" } ],
      "questions": [ { "q": "専門家が一番言いたいことは何ですか。", "a": "極端な食事制限をせず、バランスよく食べることが大切だということ。" } ]
    },
    {
      "title": "聴解問題 3 (Listening 3)",
      "context": "大学で先生がレポートについて説明しています。学生はレポートをどのように提出しなければなりませんか。",
      "transcript": "先生：この授業の最終レポートについて説明します。締め切りは来週の金曜日の午後５時です。ワードで作成し、PDFに変換した上で、大学のシステムから提出してください。印刷して直接持ってくるのは受け付けませんから注意してください。",
      "key_phrases": [ { "ja": "締め切り (しめきり)", "en": "Deadline" }, { "ja": "提出 (ていしゅつ)", "en": "Submission" } ],
      "questions": [ { "q": "学生はレポートをどのように提出しなければなりませんか。", "a": "PDFに変換して、大学のシステムから提出しなければならない。" } ]
    },
    {
      "title": "聴解問題 4 (Listening 4)",
      "context": "友達同士が旅行の計画を立てています。どこに泊まることにしましたか。",
      "transcript": "男：来月の温泉旅行、宿はどうする？海が見える旅館がいいな。\n女：海が見えるところは景色はいいけど、駅から遠くて不便じゃない？私は料理が美味しいと評判のホテルがいいな。\n男：それもいいけど、せっかく温泉に行くんだから、やっぱり和室でゆっくりしたいな。\n女：じゃあ、駅に近くて、食事が美味しい和風の旅館を探してみようか。\n男：そうだね、それにしよう。",
      "key_phrases": [ { "ja": "評判 (ひょうばん)", "en": "Reputation" }, { "ja": "和室 (わしつ)", "en": "Japanese-style room" } ],
      "questions": [ { "q": "二人はどんな宿を探すことにしましたか。", "a": "駅に近くて、食事が美味しい和風の旅館。" } ]
    }
  ],
  "2": [
    {
      "title": "聴解問題 1 (Listening 1)",
      "context": "会議でプロジェクトマネージャーがスケジュールの遅れについて話しています。マネージャーはどのように対処すると言っていますか。",
      "transcript": "マネージャー：現在、システムの開発が予定より１週間遅れています。原因は一部の仕様変更に対応するためです。このままでは納期に間に合わない恐れがありますので、来週から外注のエンジニアを２名追加して、遅れを取り戻す方針です。皆さんもサポートをお願いします。",
      "key_phrases": [ { "ja": "仕様変更 (しようへんこう)", "en": "Specification change" }, { "ja": "外注 (がいちゅう)", "en": "Outsourcing" } ],
      "questions": [ { "q": "マネージャーは遅れを取り戻すためにどうすると言っていますか。", "a": "外注のエンジニアを２名追加する。" } ]
    },
    {
      "title": "聴解問題 2 (Listening 2)",
      "context": "テレビの討論番組で、評論家が都市開発について意見を述べています。評論家は何を問題視していますか。",
      "transcript": "評論家：最近の都市開発は、高層ビルや大型商業施設ばかりが建設され、経済的な利益が最優先されています。もちろん経済成長は重要ですが、古くからある歴史的な景観や、地域住民の憩いの場である公園などが次々と失われている現状は、到底見過ごすわけにはいきません。",
      "key_phrases": [ { "ja": "最優先 (さいゆうせん)", "en": "Top priority" }, { "ja": "見過ごす (みすごす)", "en": "To overlook / ignore" } ],
      "questions": [ { "q": "評論家は何を問題視していますか。", "a": "経済利益優先で、歴史的景観や地域の憩いの場が失われていること。" } ]
    },
    {
      "title": "聴解問題 3 (Listening 3)",
      "context": "夫婦が週末の過ごし方について相談しています。二人は日曜日、何をすることにしましたか。",
      "transcript": "妻：ねえ、今週末はどうする？久しぶりに映画でも見に行かない？\n夫：映画もいいけど、最近運動不足だから、少し山登りでもしないか。\n妻：えー、山登りは疲れるから嫌よ。それなら、少し遠くのアウトレットモールまでドライブがてら買い物に行かない？歩くから運動にもなるし。\n夫：なるほど、それはいい妥協案だね。じゃあ、日曜日はそうしよう。",
      "key_phrases": [ { "ja": "運動不足 (うんどうぶそく)", "en": "Lack of exercise" }, { "ja": "妥協案 (だきょうあん)", "en": "Compromise plan" } ],
      "questions": [ { "q": "二人は日曜日、何をすることにしましたか。", "a": "アウトレットモールまでドライブがてら買い物に行くこと。" } ]
    },
    {
      "title": "聴解問題 4 (Listening 4)",
      "context": "社内研修で講師がコミュニケーションの重要性について語っています。講師が強調していることは何ですか。",
      "transcript": "講師：職場で円滑な人間関係を築く上で、自分の意見を相手に分かりやすく伝える論理的な説明力は確かに重要です。しかし、それ以上に不可欠なのは、相手の言葉に耳を傾け、相手の立場や感情を理解しようとする「共感する力」なのです。これなしでは、真の信頼関係は生まれません。",
      "key_phrases": [ { "ja": "円滑な (えんかつな)", "en": "Smooth" }, { "ja": "共感 (きょうかん)", "en": "Empathy / sympathy" } ],
      "questions": [ { "q": "講師がコミュニケーションにおいて最も重要だと強調していることは何ですか。", "a": "相手の立場や感情を理解しようとする「共感する力」。" } ]
    }
  ],
  "1": [
    {
      "title": "聴解問題 1 (Listening 1)",
      "context": "講演会で経営者が企業の社会的責任（CSR）について論じています。経営者が最も重視している姿勢は何ですか。",
      "transcript": "経営者：企業が利潤を追求することは大前提ですが、現代においてそれだけでは市場からの支持を得ることは困難です。環境問題や人権問題など、社会が直面する複雑な課題に対し、自社の事業活動を通じてどのように解決に寄与できるか。単なるボランティアではなく、本業と結びつけた持続可能な価値創造こそが、我々が目指すべき真の姿なのです。",
      "key_phrases": [ { "ja": "利潤を追求する (りじゅんをついきゅうする)", "en": "Pursue profit" }, { "ja": "価値創造 (かちそうぞう)", "en": "Value creation" } ],
      "questions": [ { "q": "経営者が最も重視している企業の姿勢は何ですか。", "a": "本業と結びつけて社会課題の解決に寄与する、持続可能な価値創造。" } ]
    },
    {
      "title": "聴解問題 2 (Listening 2)",
      "context": "ニュース解説番組で、有識者がAIの規制について見解を述べています。有識者の主張の要点は何ですか。",
      "transcript": "有識者：AIの急速な発展に伴い、各国で法規制の議論が活発化しています。確かに、プライバシーの侵害やフェイクニュースの拡散など、負の側面を抑制するためのルール作りは急務です。しかし、過度な規制は技術革新の芽を摘むことにもなりかねません。イノベーションの促進とリスク管理の絶妙なバランスをいかに取るかが、今後の最大の焦点となるでしょう。",
      "key_phrases": [ { "ja": "活発化 (かっぱつか)", "en": "Becoming active" }, { "ja": "芽を摘む (めをつむ)", "en": "To nip in the bud" } ],
      "questions": [ { "q": "有識者の主張の要点は何ですか。", "a": "AIの過度な規制は避け、イノベーション促進とリスク管理のバランスを取ることが重要だということ。" } ]
    },
    {
      "title": "聴解問題 3 (Listening 3)",
      "context": "ラジオの対談番組で、作家が自身の執筆スタイルについて語っています。作家が作品を完成させる過程で最も苦労するのはどの段階ですか。",
      "transcript": "作家：作品の構想を練り、おおまかなプロットを作る段階は、インスピレーションが湧いてきて比較的楽しいものです。また、一度書き上がった原稿を推敲し、表現を磨き上げる作業も、職人的なやりがいを感じます。しかし、いざ真っ白な原稿用紙に向かい、頭の中の抽象的なイメージを具体的な最初の言語へと変換して書き連ねていく、その産みの苦しみたるや、毎回逃げ出したくなるほどです。",
      "key_phrases": [ { "ja": "構想を練る (こうそうをねる)", "en": "To work out a plot/concept" }, { "ja": "推敲 (すいこう)", "en": "Polishing / revising (text)" } ],
      "questions": [ { "q": "作家が最も苦労するのはどの段階ですか。", "a": "頭の中の抽象的なイメージを具体的な言葉に変換して書き始める段階。" } ]
    },
    {
      "title": "聴解問題 4 (Listening 4)",
      "context": "社内の役員会議で、新規事業の撤退に関する議論が行われています。社長はどのような理由で撤退を決断しましたか。",
      "transcript": "社長：この新規事業には莫大な時間と資金を投資してきました。担当チームの並々ならぬ努力は深く評価していますし、ここで手を引くのは断腸の思いです。しかし、市場環境の劇的な変化により、当初見込んでいた需要の拡大がもはや絶望的である以上、これ以上のサンクコストの増大を防ぎ、限られた経営資源を成長分野へ迅速に振り向けることこそが、会社全体を守る唯一の道だと判断しました。",
      "key_phrases": [ { "ja": "撤退 (てったい)", "en": "Withdrawal" }, { "ja": "断腸の思い (だんちょうのおもい)", "en": "Heartbreaking / agonizing" } ],
      "questions": [ { "q": "社長が新規事業から撤退を決断した一番の理由は何ですか。", "a": "市場環境の変化で需要拡大が見込めず、経営資源を成長分野へ集中させるため。" } ]
    }
  ]
};

// Inject the new data
['1', '2', '3', '4', '5'].forEach(lvl => {
  JLPT_TEXTBOOK[lvl].reading = newReading[lvl];
  JLPT_TEXTBOOK[lvl].listening = newListening[lvl];
});

const output = '// AUTO-GENERATED JLPT TEXTBOOK DATABASE\n'
  + '// This file contains comprehensive Minna no Nihongo style textbook lessons.\n\n'
  + 'const JLPT_TEXTBOOK = ' + JSON.stringify(JLPT_TEXTBOOK, null, 2) + ';\n';

fs.writeFileSync('jlpt_textbook_data.js', output, 'utf8');
console.log('Successfully injected huge sets of reading and listening questions for N1-N5.');
