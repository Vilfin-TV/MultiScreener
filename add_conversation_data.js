const fs = require('fs');

let js = fs.readFileSync('jlpt_textbook_data.js', 'utf8');

const conversationPages = [
  {
    title: "Trip to Odaiba: Characters & Scene 1 (The Weekend Plan)",
    image: "https://images.unsplash.com/photo-1517502884422-41eaead166d4?auto=format&fit=crop&w=800&q=80",
    passage: `
<div style="margin-bottom:16px;">
  <strong>登場人物 (Characters)</strong><br>
  👤 <strong>ラヴィ (Ravi):</strong> From India. Lives in Nishi-Kasai. Works as a Desktop Support Team leader. Has a young daughter.<br>
  👤 <strong>林 / リン (Lin):</strong> From China. Works in IT.<br>
  👤 <strong>エマ (Emma):</strong> From America. Works as an English teacher.
</div>
<div style="background:var(--bg); padding:16px; border-radius:8px; border-left:4px solid var(--blue);">
  <strong>Setting:</strong> A group chat on Friday evening.<br><br>
  <strong style="color:var(--gold2);">ラヴィ:</strong> みんな、今週の土曜日、どこか遊びに行かない？<br>
  <span style="color:var(--text3); font-size:14px;">(Hey guys, do you want to go hang out somewhere this Saturday?)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> いいね！最近ずっと忙しかったから、どこかに出かけたいな。お台場はどう？<br>
  <span style="color:var(--text3); font-size:14px;">(Sounds good! I've been really busy lately, so I want to go out somewhere. How about Odaiba?)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> お台場、大賛成！買い物もできるし、海も見えるしね。リラックスできそう。<br>
  <span style="color:var(--text3); font-size:14px;">(Odaiba, I totally agree! We can shop and see the ocean. It sounds relaxing.)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> じゃあ、明日はお台場に行こう。何時に集まる？私の家の近くの、西葛西駅で待ち合わせするのはどう？<br>
  <span style="color:var(--text3); font-size:14px;">(Let's go to Odaiba tomorrow then. What time should we meet? How about meeting at Nishi-Kasai station, near my house?)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> うん、いいよ。朝10時に西葛西駅の改札でどう？<br>
  <span style="color:var(--text3); font-size:14px;">(Yeah, that works. How about 10 AM at the Nishi-Kasai station ticket gate?)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> わかった。西葛西からなら、東西線と大江戸線とゆりかもめを乗り換えて行くのが便利だね。<br>
  <span style="color:var(--text3); font-size:14px;">(Got it. From Nishi-Kasai, it's convenient to transfer between the Tozai Line, Oedo Line, and Yurikamome.)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> そうだね。じゃあ、明日10時に西葛西で！<br>
  <span style="color:var(--text3); font-size:14px;">(Right. See you tomorrow at 10 in Nishi-Kasai then!)</span>
</div>
    `
  },
  {
    title: "Trip to Odaiba: Scene 2 (Conversation on the Train)",
    image: "https://images.unsplash.com/photo-1542051841857-5f90071e7989?auto=format&fit=crop&w=800&q=80",
    passage: `
<div style="background:var(--bg); padding:16px; border-radius:8px; border-left:4px solid var(--blue);">
  <strong>Setting:</strong> Saturday morning. The three friends are on the train heading to Odaiba.<br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> ラヴィ、最近仕事はどう？相変わらず忙しい？<br>
  <span style="color:var(--text3); font-size:14px;">(Ravi, how's work lately? Busy as usual?)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> うん、すごく忙しいよ。最近、会社のデスクトップサポートのチームリーダーになったんだ。だから、責任が重くなって、やることがたくさんあるんだよね。<br>
  <span style="color:var(--text3); font-size:14px;">(Yeah, really busy. I recently became the desktop support team leader at my company. So I have more responsibility and a lot to do.)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> え、チームリーダー？すごい！おめでとう！でも、無理しないでね。<br>
  <span style="color:var(--text3); font-size:14px;">(Eh, Team Leader? That's amazing! Congratulations! But don't push yourself too hard.)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> ありがとう。大変だけど、やりがいはあるよ。リンは仕事どう？<br>
  <span style="color:var(--text3); font-size:14px;">(Thanks. It's tough, but it's rewarding. How about your work, Lin?)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> 私もITの仕事だけど、毎日ずっとパソコンの画面を見ているから、最近目がすごく疲れるんだ。中国にいる両親も私の健康を心配しているよ。<br>
  <span style="color:var(--text3); font-size:14px;">(I'm in IT too, but I stare at a computer screen all day every day, so my eyes are really tired lately. My parents in China are worried about my health too.)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> わかる！私も毎日アメリカの家族と電話するけど、いつも「ちゃんと寝ている？」って聞かれるよ。<br>
  <span style="color:var(--text3); font-size:14px;">(I get it! I call my family in America every day too, and they always ask, "Are you sleeping properly?")</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> 家族といえば、私の娘も最近大きくなってきて、来年はもう小学生なんだ。インターナショナルスクールに入れる予定だから、その準備も少し大変なんだよね。<br>
  <span style="color:var(--text3); font-size:14px;">(Speaking of family, my daughter has gotten bigger recently, and she'll be an elementary school student next year. We plan to put her in an international school, so preparing for that is a bit tough too.)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> わあ、もうそんなに大きくなったんだね！子供の成長は本当に早いなぁ。<br>
  <span style="color:var(--text3); font-size:14px;">(Wow, she's already gotten that big! Children grow up so fast.)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> あ、おしゃべりしていたら、もう新橋駅に着くよ。ゆりかもめに乗り換えよう！<br>
  <span style="color:var(--text3); font-size:14px;">(Ah, while we were chatting, we're already arriving at Shimbashi station. Let's transfer to the Yurikamome!)</span>
</div>
    `
  },
  {
    title: "Trip to Odaiba: Scene 3 (Arriving in Odaiba)",
    image: "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?auto=format&fit=crop&w=800&q=80",
    passage: `
<div style="background:var(--bg); padding:16px; border-radius:8px; border-left:4px solid var(--blue);">
  <strong>Setting:</strong> Getting off the train at Odaiba. The weather is sunny and clear.<br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> 着いた！見て、海がすごくきれい！レインボーブリッジもよく見えるね。<br>
  <span style="color:var(--text3); font-size:14px;">(We're here! Look, the ocean is so beautiful! We can see the Rainbow Bridge clearly too.)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> 本当だね。風も気持ちいい。アメリカの海と比べてどう？<br>
  <span style="color:var(--text3); font-size:14px;">(It really is. The wind feels nice too. How does it compare to the ocean in America?)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> カリフォルニアのビーチはもっと広くて波が高いけど、お台場は静かで平和な感じがして好きだよ。<br>
  <span style="color:var(--text3); font-size:14px;">(The beaches in California are wider and the waves are higher, but I like Odaiba because it feels quiet and peaceful.)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> インドの海もきれいで活気があるけど、東京の海も素晴らしいね。よし、まずはあの大きなガンダムを見に行かない？<br>
  <span style="color:var(--text3); font-size:14px;">(The beaches in India are beautiful and lively too, but Tokyo's ocean is wonderful. Alright, shouldn't we go see that giant Gundam first?)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> 賛成！写真をたくさん撮ろう。その後は、ダイバーシティで少し買い物がしたいな。秋のコートを探しているんだ。<br>
  <span style="color:var(--text3); font-size:14px;">(Agreed! Let's take lots of photos. After that, I want to do a little shopping at DiverCity. I'm looking for an autumn coat.)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> いいね。買い物の後はランチにしよう。何が食べたい？<br>
  <span style="color:var(--text3); font-size:14px;">(Sounds good. Let's have lunch after shopping. What do you want to eat?)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> 私は和食が食べたいな。最近、家ではバスマティライスやアタ粉を使ってインド料理ばかり作っているから、外では日本の味が楽しみたいんだ。<br>
  <span style="color:var(--text3); font-size:14px;">(I want to eat Japanese food. Lately, I've only been making Indian food at home using basmati rice and atta flour, so I want to enjoy Japanese flavors when I'm out.)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> じゃあ、美味しいお寿司か天ぷらを食べに行こう！<br>
  <span style="color:var(--text3); font-size:14px;">(Then let's go eat some delicious sushi or tempura!)</span>
</div>
    `
  },
  {
    title: "Trip to Odaiba: Scene 4 (The Journey Home)",
    image: "https://images.unsplash.com/photo-1494548162494-384bba4ab999?auto=format&fit=crop&w=800&q=80",
    passage: `
<div style="background:var(--bg); padding:16px; border-radius:8px; border-left:4px solid var(--blue);">
  <strong>Setting:</strong> Late afternoon, watching the sunset by the water before heading back.<br><br>
  
  <strong style="color:var(--green);">リン:</strong> ああ、お寿司、美味しかったね。買い物もできたし、大満足！<br>
  <span style="color:var(--text3); font-size:14px;">(Ah, the sushi was delicious. We got to shop too, I'm super satisfied!)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> 見て、夕日が沈んでいくよ。空の色がオレンジ色になって、すごくロマンチックだね。<br>
  <span style="color:var(--text3); font-size:14px;">(Look, the sun is setting. The sky is turning orange, it's so romantic.)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> 本当だ。今日は一日たくさん歩いて疲れたけど、すごく楽しかった。娘にお土産も買えたし。<br>
  <span style="color:var(--text3); font-size:14px;">(It's true. I'm tired from walking a lot all day today, but it was really fun. I even got to buy a souvenir for my daughter.)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> 私もいいリフレッシュになったよ。また来月、どこか遊びに行こうね。<br>
  <span style="color:var(--text3); font-size:14px;">(It was a good refresh for me too. Let's go hang out somewhere again next month.)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> うん、絶対に！次は少し足を伸ばして、箱根や富士山の近くに行くのもいいかもしれないね。<br>
  <span style="color:var(--text3); font-size:14px;">(Yeah, definitely! Next time it might be nice to go a little further, maybe near Hakone or Mt. Fuji.)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> いいアイデアだね。じゃあ、そろそろ西葛西に帰ろうか。<br>
  <span style="color:var(--text3); font-size:14px;">(That's a good idea. Well, should we head back to Nishi-Kasai soon?)</span>
</div>
    `
  },
  {
    title: "N4/N3 Key Grammar & Vocabulary Study Guide",
    passage: `
<div style="margin-bottom:20px;">
  <h4 style="color:var(--gold2); margin-bottom:8px;">📚 Vocabulary (語彙)</h4>
  <ul style="line-height:1.8;">
    <li><strong>大賛成 (だいさんせい):</strong> Complete agreement</li>
    <li><strong>改札 (かいさつ):</strong> Ticket gate</li>
    <li><strong>乗り換える (のりかえる):</strong> To transfer (trains)</li>
    <li><strong>責任 (せきにん):</strong> Responsibility</li>
    <li><strong>やりがいがある:</strong> Rewarding / worth doing</li>
    <li><strong>相変わらず (あいかわらず):</strong> As usual</li>
    <li><strong>平和 (へいわ):</strong> Peaceful</li>
    <li><strong>活気がある (かっきがある):</strong> Lively / energetic</li>
    <li><strong>足を伸ばす (あしをのばす):</strong> To go a little further (idiom)</li>
  </ul>
</div>

<div style="margin-bottom:20px;">
  <h4 style="color:var(--gold2); margin-bottom:8px;">📝 General Grammar Points (文法)</h4>
  <ul style="line-height:1.8;">
    <li><strong>〜し、〜し (Reason/Listing):</strong> 買い物もできるし、海も見えるしね。(We can shop, and we can see the ocean...) - Used to list multiple reasons or attractive points.</li>
    <li><strong>〜かもしれない (Might / Possibility):</strong> 富士山の近くに行くのもいいかもしれないね。(It might be nice to go near Mt. Fuji.)</li>
    <li><strong>〜てしまう / 〜ちゃう (Completed action / minor regret):</strong> 声が疲れちゃう。(My voice gets tired / ends up tired.) - Chau is the casual, spoken form of te-shimau.</li>
    <li><strong>〜予定です (Plan to):</strong> インターナショナルスクールに入れる予定だから... (Because we plan to enroll her in an international school...)</li>
  </ul>
</div>

<div>
  <h4 style="color:var(--gold2); margin-bottom:8px;">🔥 3 Key N3 Conversational Grammar Structures</h4>
  
  <div style="background:var(--card3); padding:12px; border-radius:6px; margin-bottom:12px;">
    <strong>1. 〜と比べて (〜とくらべて) - Compared to...</strong><br>
    Used to contrast two things. Natural conversational comparison.<br>
    <em>Structure:</em> [Noun] + と比べて<br>
    <em>Example:</em> 「アメリカの海と比べてどう？」 (How is it compared to the ocean in America?)
  </div>
  
  <div style="background:var(--card3); padding:12px; border-radius:6px; margin-bottom:12px;">
    <strong>2. 〜感じがする (〜かんじがする) - Gives a feeling of / Feels like...</strong><br>
    Used when sensing a vibe, atmosphere, or physical sensation without stating an objective fact.<br>
    <em>Structure:</em> [Noun]の / [な-Adj]な / [い-Adj] / [Verb casual] + 感じがする<br>
    <em>Example:</em> 「お台場は静かで平和な感じがして好きだよ。」 (I like Odaiba because it feels quiet and peaceful.)
  </div>
  
  <div style="background:var(--card3); padding:12px; border-radius:6px; margin-bottom:12px;">
    <strong>3. 〜ばかり / 〜てばかりいる - Only / Nothing but / Always doing...</strong><br>
    Emphasizes an exclusive habit or current situation.<br>
    <em>Structure:</em> [Noun] + ばかり | [Verb て-form] + ばかりいる<br>
    <em>Example:</em> 「家ではインド料理ばかり作っているから...」 (Because I've been making nothing but Indian food at home...)
  </div>
</div>
    `
  },
  {
    title: "Scene 2 (Conversation on the Train - Polite Form)",
    passage: `
<div style="background:var(--bg); padding:16px; border-radius:8px; border-left:4px solid var(--blue);">
  <strong>Setting:</strong> Scene 2 rewritten using Desu/Masu form. Notice how the characters now use 〜さん when addressing each other, add お before certain nouns (like お仕事), and change their sentence endings. This is the level of politeness you would use with colleagues, acquaintances, or people you are not extremely close with yet.<br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> ラヴィさん、最近お仕事はどうですか？相変わらず忙しいですか？<br>
  <span style="color:var(--text3); font-size:14px;">(Ravi, how is your work lately? Are you busy as usual?)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> はい、すごく忙しいです。最近、会社のデスクトップサポートのチームリーダーになったんです。ですから、責任が重くなって、やることがたくさんあります。<br>
  <span style="color:var(--text3); font-size:14px;">(Yes, I am really busy. I recently became the desktop support team leader at my company. So I have more responsibility and a lot to do.)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> え、チームリーダーですか？すごいですね！おめでとうございます！でも、無理をしないでくださいね。<br>
  <span style="color:var(--text3); font-size:14px;">(Eh, Team Leader? That's amazing! Congratulations! But please don't push yourself too hard.)</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> ありがとうございます。大変ですが、やりがいはありますよ。リンさんのお仕事はどうですか？<br>
  <span style="color:var(--text3); font-size:14px;">(Thank you. It's tough, but it's rewarding. How is your work, Lin?)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> 私もITの仕事ですが、毎日ずっとパソコンの画面を見ていますから、最近目がすごく疲れるんです。中国にいる両親も私の健康を心配していますよ。<br>
  <span style="color:var(--text3); font-size:14px;">(I'm in IT too, but I stare at a computer screen all day every day, so my eyes are really tired lately. My parents in China are worried about my health too.)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> わかります！私も毎日アメリカの家族と電話しますが、いつも「ちゃんと寝ていますか？」と聞かれますよ。<br>
  <span style="color:var(--text3); font-size:14px;">(I understand! I call my family in America every day too, but I am always asked, "Are you sleeping properly?")</span><br><br>
  
  <strong style="color:var(--gold2);">ラヴィ:</strong> 家族といえば、私の娘も最近大きくなってきて、来年はもう小学生になります。インターナショナルスクールに入れる予定なので、その準備も少し大変なんですよ。<br>
  <span style="color:var(--text3); font-size:14px;">(Speaking of family, my daughter has gotten bigger recently, and she will be an elementary school student next year. We plan to put her in an international school, so preparing for that is a bit tough too.)</span><br><br>
  
  <strong style="color:var(--pink);">エマ:</strong> わあ、もうそんなに大きくなったんですね！子供の成長は本当に早いですね。<br>
  <span style="color:var(--text3); font-size:14px;">(Wow, she has already gotten that big! Children grow up so fast, don't they?)</span><br><br>
  
  <strong style="color:var(--green);">リン:</strong> あ、おしゃべりしていたら、もう新橋駅に着きますよ。ゆりかもめに乗り換えましょう！<br>
  <span style="color:var(--text3); font-size:14px;">(Ah, while we were chatting, we're already arriving at Shimbashi station. Let's transfer to the Yurikamome!)</span>
</div>
    `
  }
];

// Reconstruct JLPT_TEXTBOOK by evaluating it
let text = js.substring(js.indexOf('{'));
text = text.trim();
if (text.endsWith(';')) text = text.slice(0, -1);
let obj = eval('(' + text + ')');

// Add to all levels
for (let lvl of ["1", "2", "3", "4", "5"]) {
  if (!obj[lvl]) obj[lvl] = {};
  obj[lvl].conversation = conversationPages;
}

// Convert back to string and save
let newJs = '// AUTO-GENERATED JLPT TEXTBOOK DATABASE\\n// This file contains comprehensive Minna no Nihongo style textbook lessons.\\n\\nconst JLPT_TEXTBOOK = ' + JSON.stringify(obj, null, 2) + ';\\n';
fs.writeFileSync('jlpt_textbook_data.js', newJs);

console.log('Successfully injected conversation data!');
