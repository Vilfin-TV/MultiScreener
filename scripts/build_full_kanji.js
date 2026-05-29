const https = require('https');
const fs = require('fs');
const path = require('path');

const url = 'https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json';

https.get(url, (res) => {
    let rawData = '';
    res.on('data', (chunk) => { rawData += chunk; });
    res.on('end', () => {
        try {
            const kanjiDb = JSON.parse(rawData);
            const KANJI_LEVEL_DATA = { 5: [], 4: [], 3: [], 2: [], 1: [] };

            for (const [kanji, data] of Object.entries(kanjiDb)) {
                let jlpt = data.jlpt_new || data.jlpt_old;
                if (!jlpt && data.grade >= 1 && data.grade <= 6) {
                  jlpt = 1;
                }
                
                if (jlpt >= 1 && jlpt <= 5) {
                    const item = {
                        k: kanji,
                        s: data.strokes + ' strokes',
                        m: (data.meanings || []).slice(0, 3).join(', '),
                        r: [...(data.readings_on || []), ...(data.readings_kun || [])].slice(0, 4).join(', ')
                    };
                    KANJI_LEVEL_DATA[jlpt].push(item);
                }
            }

            for (let i = 1; i <= 5; i++) {
                if (KANJI_LEVEL_DATA[i].length === 0) {
                    KANJI_LEVEL_DATA[i].push({ k: '?', s: '?', m: 'No data', r: '?' });
                }
            }

            const outputFilePath = path.join(__dirname, '..', 'kanji_data.js');
            let jsContent = `// Auto-generated Kanji Database for N5-N1 (Full Set)\n`;
            jsContent += `const KANJI_LEVEL_DATA = ${JSON.stringify(KANJI_LEVEL_DATA, null, 2)};\n`;
            jsContent += `\n// Make available globally\nif (typeof window !== 'undefined') window.KANJI_LEVEL_DATA = KANJI_LEVEL_DATA;\n`;

            fs.writeFileSync(outputFilePath, jsContent, 'utf8');
            console.log('✅ Successfully generated kanji_data.js with ' + 
                Object.values(KANJI_LEVEL_DATA).reduce((sum, arr) => sum + arr.length, 0) + ' Kanji entries!');

        } catch (e) {
            console.error(e.message);
        }
    });
}).on('error', (e) => {
    console.error(`Got error: ${e.message}`);
});
