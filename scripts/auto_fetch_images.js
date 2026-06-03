require('dotenv').config({ path: require('path').resolve(__dirname, '../.env') });
const fs = require('fs');
const path = require('path');
const { createClient } = require('pexels');
// const fetch = require('node-fetch');
const vm = require('vm');

const PEXELS_KEY = process.env.PEXELS_API_KEY;

if (!PEXELS_KEY) {
  console.error("Missing PEXELS_API_KEY. Please check your .env file.");
  process.exit(1);
}

const pexelsClient = createClient(PEXELS_KEY);

function ensureDirectoryExists(filePath) {
  const dirname = path.dirname(filePath);
  if (fs.existsSync(dirname)) return true;
  ensureDirectoryExists(dirname);
  fs.mkdirSync(dirname);
}

async function searchAndDownloadImage(keyword, relativePath) {
  if (!keyword) return false;
  const absolutePath = path.resolve(__dirname, '..', relativePath);
  if (fs.existsSync(absolutePath)) {
    console.log(`[SKIP] Already exists locally: ${relativePath}`);
    return true;
  }
  console.log(`[PEXELS] Searching for: ${keyword}`);
  try {
    const res = await pexelsClient.photos.search({ query: keyword, per_page: 1 });
    if (!res || !res.photos || res.photos.length === 0) {
      console.log(`   -> No photos found for ${keyword}`);
      return false;
    }
    const photoUrl = res.photos[0].src.medium;
    const imgRes = await fetch(photoUrl);
    const buffer = await imgRes.buffer();
    ensureDirectoryExists(absolutePath);
    fs.writeFileSync(absolutePath, buffer);
    console.log(`[SAVED] Saved to: ${relativePath}`);
    return true;
  } catch (err) {
    console.error(`   -> Error processing ${keyword}:`, err.message);
    return false;
  }
}

function extractMeaning(wordStr) {
  if (!wordStr) return null;
  const match = wordStr.match(/^([^\(]+)\s*\((.+?)\)$/);
  if (match) {
    const parts = match[2].split('-');
    if (parts.length > 1) return parts[1].trim();
    return match[2].trim();
  }
  return null;
}

// Extract KANA_DATA from education.html
let kanaData = [];
try {
  const htmlContent = fs.readFileSync(path.resolve(__dirname, '../education.html'), 'utf-8');
  const match = htmlContent.match(/const KANA_DATA = (\[[\s\S]*?\]);/);
  if (match) {
    kanaData = eval(match[1]);
  }
} catch (e) {
  console.error("Failed to parse KANA_DATA from education.html", e);
}

// Extract KANJI_LEVEL_DATA from kanji_data.js
let kanjiData = [];
try {
  const kanjiContent = fs.readFileSync(path.resolve(__dirname, '../kanji_data.js'), 'utf-8');
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(kanjiContent, sandbox);
  if (sandbox.KANJI_LEVEL_DATA) {
    for (const level in sandbox.KANJI_LEVEL_DATA) {
      kanjiData = kanjiData.concat(sandbox.KANJI_LEVEL_DATA[level]);
    }
  }
} catch (e) {
  console.error("Failed to parse KANJI_LEVEL_DATA from kanji_data.js", e);
}

async function run() {
  console.log("=== Starting Image Automation (Local Storage) ===");
  let fetchedCount = 0;
  
  if (kanaData && kanaData.length > 0) {
    for (let i = 0; i < kanaData.length; i++) {
      const item = kanaData[i];
      if (item.type === 'spacer') continue;
      const meaning = extractMeaning(item.word);
      if (meaning) {
        const objectPath = `images/kana/${item.r.toLowerCase()}.jpg`;
        const fetched = await searchAndDownloadImage(meaning, objectPath);
        if (fetched) fetchedCount++;
      }
      await new Promise(r => setTimeout(r, 1500));
    }
  }
  
  if (kanjiData && kanjiData.length > 0) {
    for (let i = 0; i < kanjiData.length; i++) {
      const item = kanjiData[i];
      if (item.meaning) {
        const objectPath = `images/kanji/${item.kanji}.jpg`;
        const primaryMeaning = item.meaning.split(',')[0].trim();
        const fetched = await searchAndDownloadImage(primaryMeaning, objectPath);
        if (fetched) fetchedCount++;
      }
      await new Promise(r => setTimeout(r, 1500));
    }
  }
  
  if (fetchedCount === 0) {
    // If we didn't fetch anything (e.g. they all exist), ensure images directory exists so git add doesn't fail
    ensureDirectoryExists(path.resolve(__dirname, '../images/.keep'));
    fs.writeFileSync(path.resolve(__dirname, '../images/.keep'), '');
  }
  
  console.log("=== Automation Complete ===");
}

run();
