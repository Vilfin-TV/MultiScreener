require('dotenv').config({ path: path.resolve(__dirname, '../.env') });
const fs = require('fs');
const path = require('path');
const { createClient } = require('pexels');
const fetch = require('node-fetch');
const vm = require('vm');

// 1. Setup API Clients
const PEXELS_KEY = process.env.PEXELS_API_KEY;

if (!PEXELS_KEY) {
  console.error("Missing PEXELS_API_KEY. Please check your .env file.");
  process.exit(1);
}

const pexelsClient = createClient(PEXELS_KEY);

// 2. Load Data from .js files
function loadData(filename, variableName) {
  const filePath = path.resolve(__dirname, '..', filename);
  if (!fs.existsSync(filePath)) return null;
  const content = fs.readFileSync(filePath, 'utf-8');
  const sandbox = {};
  vm.createContext(sandbox);
  try {
    vm.runInContext(content, sandbox);
    return sandbox[variableName];
  } catch (e) {
    console.error(`Failed to parse ${filename}:`, e);
    return null;
  }
}

const kanaData = loadData('jlpt_textbook_data.js', 'KANA_DATA');
const kanjiData = loadData('kanji_data.js', 'KANJI_DATA');

// 3. Helper Functions
function ensureDirectoryExists(filePath) {
  const dirname = path.dirname(filePath);
  if (fs.existsSync(dirname)) {
    return true;
  }
  ensureDirectoryExists(dirname);
  fs.mkdirSync(dirname);
}

async function searchAndDownloadImage(keyword, relativePath) {
  if (!keyword) return false;
  
  const absolutePath = path.resolve(__dirname, '..', relativePath);
  
  // Check if we already did this to avoid API spam
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
    
    // Get the medium sized photo
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

// Extract word from formats like: "朝 (asa - morning)"
function extractMeaning(wordStr) {
  if (!wordStr) return null;
  const match = wordStr.match(/^([^\(]+)\s*\((.+?)\)$/);
  if (match) {
    // Second group is something like "asa - morning" or "neko - cat"
    const parts = match[2].split('-');
    if (parts.length > 1) {
      return parts[1].trim();
    }
    return match[2].trim();
  }
  return null;
}

// 4. Main Execution
async function run() {
  console.log("=== Starting Image Automation (Local Storage) ===");
  
  // Process KANA
  if (kanaData) {
    for (let i = 0; i < kanaData.length; i++) {
      const item = kanaData[i];
      if (item.type === 'spacer') continue;
      
      const meaning = extractMeaning(item.word);
      if (meaning) {
        const objectPath = `images/kana/${item.r.toLowerCase()}.jpg`;
        await searchAndDownloadImage(meaning, objectPath);
      }
      // Small delay to respect rate limits
      await new Promise(r => setTimeout(r, 1500));
    }
  }
  
  // Process KANJI
  if (kanjiData) {
    for (let i = 0; i < kanjiData.length; i++) {
      const item = kanjiData[i];
      if (item.meaning) {
        const objectPath = `images/kanji/${item.kanji}.jpg`;
        // Only use the first word of the meaning if it's long (e.g. "one, one radical")
        const primaryMeaning = item.meaning.split(',')[0].trim();
        await searchAndDownloadImage(primaryMeaning, objectPath);
      }
      await new Promise(r => setTimeout(r, 1500));
    }
  }
  
  console.log("=== Automation Complete ===");
}

run();
