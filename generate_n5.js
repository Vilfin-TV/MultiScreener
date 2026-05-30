const fs = require('fs');

const data = JSON.parse(fs.readFileSync('jlpt_n5.json', 'utf8'));

// Procedural JLPT N5 Question Generator
const newQuestions = [];

// Template 1: Particles
const subjects = ['わたし', 'せんせい', 'ともだち', 'いぬ', 'ねこ', 'あに', 'いもうと'];
const objects = ['りんご', 'ごはん', 'パン', 'おにぎり', 'すし'];
const verbs = ['たべます', 'かいます', 'つくります'];

for (let s of subjects) {
    for (let o of objects) {
        newQuestions.push({
            q: `${s} は ${o}（　　）たべます。`,
            options: ['を', 'が', 'に', 'で'],
            answer: 0,
            explain: `The particle を (o) marks the direct object of the verb たべます (to eat).`
        });
        newQuestions.push({
            q: `${s}（　　） ${o} を たべます。`,
            options: ['は', 'を', 'に', 'へ'],
            answer: 0,
            explain: `The particle は (wa) marks the topic/subject of the sentence.`
        });
    }
}

// Template 2: Time/Location Particles
const locations = ['がっこう', 'としょかん', 'デパート', 'えき', 'スーパー'];
const goVerbs = ['いきます', 'きます', 'かえります'];

for (let l of locations) {
    for (let v of goVerbs) {
        newQuestions.push({
            q: `わたし は ${l}（　　）${v}。`,
            options: ['へ', 'を', 'が', 'や'],
            answer: 0,
            explain: `The particle へ (e) or に (ni) indicates the direction/destination of movement.`
        });
    }
}

// Template 3: Time
const times = ['あした', 'きょう', 'あさ', 'きのう'];
for (let t of times) {
    for (let l of locations) {
        newQuestions.push({
            q: `${t}、${l} へ いきます。`,
            options: ['Time particle not needed', 'に', 'は', 'を'],
            answer: 0,
            explain: `Relative time words like ${t} do not take the particle に in Japanese.`
        });
    }
}

// Ensure unique options if needed, but since it's a generator, the JSON output is direct.
// We will only take 105 questions to reach 305 total.
const toAdd = newQuestions.slice(0, 105);

data.quizzes = data.quizzes.concat(toAdd);
fs.writeFileSync('jlpt_n5.json', JSON.stringify(data, null, 2));

console.log(`Added ${toAdd.length} procedurally generated N5 questions. Total is now ${data.quizzes.length}`);
