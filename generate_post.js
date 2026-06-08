const fs = require('fs');

const imageMap = {
  'Space Development (宇宙開発)': 'img_lineup01.jpg',
  'Drones (ドローン)': 'img_lineup02.jpg',
  'Robotics (ロボット)': 'img_lineup03.jpg',
  'Genetic Engineering (遺伝子工学)': 'img_lineup04.jpg',
  'Virtual Reality (バーチャルリアリティ)': 'img_lineup05.jpg',
  'Nanotechnology (ナノテクノロジー)': 'img_lineup06.jpg',
  'Autonomous Driving (自動運転)': 'img_lineup07.jpg',
  'Wearables (ウェアラブル)': 'img_lineup08.jpg',
  'Fintech (フィンテック)': 'img_lineup09.jpg',
  'Clean Tech (クリーンテック)': 'img_lineup10.jpg',
  'Electric Vehicles (電気自動車)': 'img_lineup11.jpg',
  'Communication DX (コミュニケーションDX)': 'img_lineup12.jpg',
  'AI Technology (AIテクノロジー)': 'img_lineup13.jpg',
  'Hydrogen Economy (水素エコノミー)': 'img_lineup14.jpg'
};

const textFile = fs.readFileSync('THE KENSHO REVOLUTION Inside the AI.txt', 'utf-8');
const lines = textFile.split(/\r?\n/);

let html = '';

html += '<p><strong>By The VILFIN TV Financial Desk</strong> | <strong>Exclusive Report</strong></p>';

let i = 3; // skip first 3 lines (title, author, blank)
while (i < lines.length) {
  const line = lines[i].trim();
  i++;

  if (!line) continue;

  let matchedFund = Object.keys(imageMap).find(k => line.includes(k));

  if (matchedFund) {
    html += '<h3>' + line + '</h3>';
    html += '<img src="images/emaxis/' + imageMap[matchedFund] + '" style="max-width:100%;height:auto;border-radius:8px;margin:16px 0;display:block;">';
  } else if (line.startsWith('The Space & Skies Frontier:') || line.startsWith('The Core Tech Backbone:') || line.startsWith('The Energy Transition:') || line.startsWith('The Physical Automation Wave:') || line.startsWith('Next-Generation Mobility & Reality') || line.startsWith('Deep Science:') || line.startsWith('The Financial Revolution') || line.startsWith('The VILFIN TV Verdict:')) {
    html += '<h2>' + line + '</h2>';
  } else if (line.startsWith('Future Outlook:')) {
    html += '<p><strong>' + line.substring(0, 15) + '</strong>' + line.substring(15) + '</p>';
  } else if (line.startsWith('Disclaimer:')) {
    html += '<p><em>' + line + '</em></p>';
  } else if (line.startsWith('However, VILFIN TV analysts')) {
    html += '<p><strong>' + line + '</strong></p>';
  } else if (line.startsWith('Every single fund')) {
    html += '<p>' + line + '</p>';
  } else if (line.startsWith('If you are buying')) {
    html += '<p>' + line + '</p>';
  } else if (line.startsWith('The Strategy:')) {
    html += '<p><strong>' + line.substring(0, 13) + '</strong>' + line.substring(13) + '</p>';
  } else {
    html += '<p>' + line + '</p>';
  }
}

const contentJson = JSON.parse(fs.readFileSync('content.json', 'utf-8'));
const postIndex = contentJson.findIndex(p => p.heading && p.heading.includes('THE KENSHO REVOLUTION'));

if (postIndex !== -1) {
  contentJson[postIndex].story = html;
  fs.writeFileSync('content.json', JSON.stringify(contentJson, null, 2));
  console.log('Successfully updated content.json');
} else {
  console.log('Post not found!');
}
