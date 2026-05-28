/**
 * scripts/extract-channels.js
 * Extracts YT_CHANNELS and NEWS_SOURCES from index.html and writes
 * them to channels-data.json for the admin console to consume.
 *
 * Usage:  node scripts/extract-channels.js
 */

const fs   = require('fs');
const path = require('path');

const ROOT       = path.join(__dirname, '..');
const INDEX_PATH = path.join(ROOT, 'index.html');
const OUT_PATH   = path.join(ROOT, 'channels-data.json');

const html = fs.readFileSync(INDEX_PATH, 'utf8');

// ── Extract YT_CHANNELS ──────────────────────────────────────────────
// Pattern: var YT_CHANNELS = [ ... ];
const ytStart = html.indexOf('var YT_CHANNELS = [');
if (ytStart === -1) { console.error('ERROR: YT_CHANNELS not found'); process.exit(1); }

// Walk forward to find the matching ];
let depth = 0, ytEnd = -1;
for (let i = ytStart + 'var YT_CHANNELS = '.length; i < html.length; i++) {
  if (html[i] === '[') depth++;
  else if (html[i] === ']') {
    depth--;
    if (depth === 0) { ytEnd = i + 1; break; }
  }
}
const ytRaw = html.slice(ytStart + 'var YT_CHANNELS = '.length, ytEnd);
// Use Function constructor (safer than eval)
const ytChannels = (new Function('return ' + ytRaw))();

// ── Extract NEWS_SOURCES ─────────────────────────────────────────────
const nsStart = html.indexOf('const NEWS_SOURCES = [');
if (nsStart === -1) { console.error('ERROR: NEWS_SOURCES not found'); process.exit(1); }

depth = 0; let nsEnd = -1;
for (let i = nsStart + 'const NEWS_SOURCES = '.length; i < html.length; i++) {
  if (html[i] === '[') depth++;
  else if (html[i] === ']') {
    depth--;
    if (depth === 0) { nsEnd = i + 1; break; }
  }
}
const nsRaw = html.slice(nsStart + 'const NEWS_SOURCES = '.length, nsEnd);
const newsSources = (new Function('return ' + nsRaw))();

// ── Extract default Ticker Symbols (desktop) ─────────────────────────
// These are now in _TICKER_DESKTOP_DEFAULTS in the script block
const tdStart = html.indexOf('var _TICKER_DESKTOP_DEFAULTS = [');
let tickerDesktop = [];
if (tdStart !== -1) {
  depth = 0; let tdEnd = -1;
  for (let i = tdStart + 'var _TICKER_DESKTOP_DEFAULTS = '.length; i < html.length; i++) {
    if (html[i] === '[') depth++;
    else if (html[i] === ']') { depth--; if (depth === 0) { tdEnd = i + 1; break; } }
  }
  tickerDesktop = (new Function('return ' + html.slice(tdStart + 'var _TICKER_DESKTOP_DEFAULTS = '.length, tdEnd)))();
}

const tmStart = html.indexOf('var _TICKER_MOBILE_DEFAULTS = [');
let tickerMobile = [];
if (tmStart !== -1) {
  depth = 0; let tmEnd = -1;
  for (let i = tmStart + 'var _TICKER_MOBILE_DEFAULTS = '.length; i < html.length; i++) {
    if (html[i] === '[') depth++;
    else if (html[i] === ']') { depth--; if (depth === 0) { tmEnd = i + 1; break; } }
  }
  tickerMobile = (new Function('return ' + html.slice(tmStart + 'var _TICKER_MOBILE_DEFAULTS = '.length, tmEnd)))();
}

// ── Write output ─────────────────────────────────────────────────────
const out = {
  generated_at: new Date().toISOString(),
  youtube_channels: ytChannels,
  news_sources: newsSources,
  ticker_desktop: tickerDesktop,
  ticker_mobile:  tickerMobile,
};

fs.writeFileSync(OUT_PATH, JSON.stringify(out));

console.log(`✅ channels-data.json written:`);
console.log(`   YouTube channels : ${ytChannels.length}`);
console.log(`   News sources     : ${newsSources.length}`);
console.log(`   Ticker (desktop) : ${tickerDesktop.length}`);
console.log(`   Ticker (mobile)  : ${tickerMobile.length}`);
