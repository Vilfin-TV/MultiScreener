const https = require('https');
const fs = require('fs');
const path = require('path');

const vocab = {
  1: {
    "おはようございます": "Good morning",
    "お疲れ様です": "Good work today",
    "お世話になっております": "Thank you for your continued support",
    "よろしくお願いします": "I look forward to working with you",
    "申し訳ございません": "I am very sorry",
    "ありがとうございます": "Thank you",
    "失礼いたします": "Excuse me",
    "かしこまりました": "Certainly",
    "承知いたしました": "Understood",
    "少々お待ちください": "Please wait a moment",
    "お待たせいたしました": "Sorry to keep you waiting",
    "確認いたします": "I will check",
    "ご対応ありがとうございます": "Thank you for your response",
    "お手数をおかけします": "Sorry to trouble you",
    "恐れ入りますが": "Excuse me, but"
  },
  2: {
    "会社": "Company",
    "仕事": "Work",
    "会議": "Meeting",
    "名刺": "Business card",
    "書類": "Document",
    "資料": "Materials",
    "企画": "Project plan",
    "報告": "Report",
    "連絡": "Contact",
    "相談": "Discussion",
    "上司": "Boss",
    "部下": "Subordinate",
    "同僚": "Colleague",
    "お客様": "Customer",
    "取引先": "Business partner",
    "電話": "Telephone",
    "メール": "Email",
    "パソコン": "PC",
    "予定": "Schedule",
    "納期": "Deadline",
    "見積もり": "Estimate",
    "契約": "Contract",
    "営業": "Sales",
    "人事": "Human Resources",
    "経理": "Accounting"
  },
  3: {
    "します": "To do",
    "行きます": "To go",
    "来ます": "To come",
    "帰ります": "To return home",
    "見ます": "To see",
    "聞きます": "To listen",
    "話します": "To speak",
    "読みます": "To read",
    "書きます": "To write",
    "食べます": "To eat",
    "飲みます": "To drink",
    "買います": "To buy",
    "使います": "To use",
    "作ります": "To make",
    "考えます": "To think",
    "教えます": "To teach",
    "調べます": "To look up",
    "送ります": "To send",
    "もらいます": "To receive",
    "待ちます": "To wait"
  },
  4: {
    "今日": "Today",
    "明日": "Tomorrow",
    "昨日": "Yesterday",
    "今週": "This week",
    "来週": "Next week",
    "先週": "Last week",
    "今年": "This year",
    "来年": "Next year",
    "時間": "Time",
    "分": "Minute",
    "半": "Half past",
    "午前": "AM",
    "午後": "PM",
    "平日": "Weekday",
    "週末": "Weekend",
    "月曜日": "Monday",
    "火曜日": "Tuesday",
    "水曜日": "Wednesday",
    "木曜日": "Thursday",
    "金曜日": "Friday"
  },
  5: {
    "電車": "Train",
    "駅": "Station",
    "切符": "Ticket",
    "定期券": "Commuter pass",
    "家": "Home",
    "店": "Shop",
    "コンビニ": "Convenience store",
    "スーパー": "Supermarket",
    "買い物": "Shopping",
    "お金": "Money",
    "現金": "Cash",
    "クレジットカード": "Credit card",
    "領収書": "Receipt",
    "レシート": "Casual receipt",
    "水": "Water",
    "ご飯": "Meal",
    "病院": "Hospital",
    "薬": "Medicine",
    "右": "Right",
    "左": "Left"
  },
  6: {
    "高い": "Expensive",
    "安い": "Cheap",
    "新しい": "New",
    "古い": "Old",
    "良い": "Good",
    "悪い": "Bad",
    "大きい": "Big",
    "小さい": "Small",
    "難しい": "Difficult",
    "簡単": "Easy",
    "忙しい": "Busy",
    "早い": "Early",
    "遅い": "Late",
    "美味しい": "Delicious",
    "暑い": "Hot weather",
    "寒い": "Cold weather",
    "便利": "Convenient",
    "不便": "Inconvenient",
    "大丈夫": "Okay",
    "本当": "True"
  }
};

// 1 second of silent MP3 (MPEG Audio layer 1/2/3)
const silentMp3Hex = "fff344c4000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000";
const silenceBuf = Buffer.from(silentMp3Hex.repeat(38), 'hex'); // roughly 1 second

function fetchTts(text, lang, speed = 1) {
  return new Promise((resolve, reject) => {
    const spdParam = speed < 1 ? '&ttsspeed=0.24' : ''; 
    const url = `https://translate.googleapis.com/translate_tts?client=gtx&ie=UTF-8&tl=${lang}${spdParam}&q=${encodeURIComponent(text)}`;
    https.get(url, (res) => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => resolve(Buffer.concat(chunks)));
      res.on('error', reject);
    }).on('error', reject);
  });
}

async function buildAudio() {
  for (let group = 1; group <= 6; group++) {
    const dict = vocab[group];
    const words = Object.keys(dict);
    const finalChunks = [];
    console.log(`Generating audio for Category ${group}...`);
    
    for (let i = 0; i < words.length; i++) {
      const jaWord = words[i];
      const enWord = dict[jaWord];
      console.log(`  - Fetching: ${jaWord} (${enWord})`);
      
      try {
        const jaNormal = await fetchTts(jaWord, 'ja', 1);
        const enNormal = await fetchTts(enWord, 'en', 1);
        const jaSlow = await fetchTts(jaWord, 'ja', 0.24); 
        
        // Pattern: JA (Normal) -> pause -> EN -> pause -> JA (Slow) -> pause -> EN -> long pause
        finalChunks.push(jaNormal);
        finalChunks.push(silenceBuf);
        finalChunks.push(enNormal);
        finalChunks.push(silenceBuf);
        finalChunks.push(jaSlow);
        finalChunks.push(silenceBuf);
        finalChunks.push(enNormal);
        finalChunks.push(silenceBuf);
        finalChunks.push(silenceBuf); // extra pause before next word
        
      } catch (err) {
        console.error('Failed to fetch', jaWord, err);
      }
      
      // Delay to avoid rate limits
      await new Promise(r => setTimeout(r, 400));
    }
    
    const finalBuffer = Buffer.concat(finalChunks);
    fs.writeFileSync(`audio_category_${group}_v3.mp3`, finalBuffer);
    console.log(`=> Saved audio_category_${group}_v3.mp3 (${finalBuffer.length} bytes)`);
  }
}

buildAudio();
