/**
 * build_news.js — VilfinTV News content generator
 * Runs in GitHub Actions (Node 20). Zero npm dependencies.
 * Fetches RSS feeds, parses XML with regex, generates AI summaries,
 * writes data/news.json (48h expiry per item).
 *
 * Env vars: GOOGLE_AI_API_KEY, GROQ_API_KEY  (GitHub Secrets)
 */

'use strict';

const https = require('https');
const http  = require('http');
const fs    = require('fs');
const path  = require('path');
const url   = require('url');

/* ═══════════════════════════════════════════════════
   CONFIGURATION
═══════════════════════════════════════════════════ */
const GOOGLE_AI_API_KEY = process.env.GOOGLE_AI_API_KEY || '';
const GROQ_API_KEY      = process.env.GROQ_API_KEY || '';

const BLOCKED_KEYWORDS = [
  'riot', 'genocide', 'lynching', 'hate speech', 'communal violence',
  'mob violence', 'explicit', 'graphic content', 'rape', 'slaughter',
  'massacre', 'pogrom', 'beheading', 'ethnic cleansing'
];

const MAX_ITEMS_PER_SECTION = 6;
const REQUEST_TIMEOUT_MS    = 22000;
// How many feeds to randomly pick from each section's pool each run
// (first two entries in each pool are always included + random extras)
const FEEDS_PER_SECTION     = 5;

// ── Source pool ──────────────────────────────────────────────────────────────
// Each section has a larger pool; FEEDS_PER_SECTION are picked at random each
// run so stories rotate and readers get fresh variety on every 6-hour cycle.
// Google Trends RSS (geo=IN / geo=US) surfaces what millions of people are
// actively searching — ideal as a "trending" signal.
const SOURCE_POOL = {

  // ── trending: Google News top-headlines as position-0 (always fetched) ──────
  trending: [
    { url: 'https://news.google.com/rss/headlines/section/topic/HEADLINES?hl=en-US&gl=US&ceid=US:en', name: 'Google News US' },
    { url: 'https://news.google.com/rss/headlines/section/topic/HEADLINES?hl=en-IN&gl=IN&ceid=IN:en', name: 'Google News India' },
    { url: 'https://feeds.bbci.co.uk/news/rss.xml',                    name: 'BBC News' },
    { url: 'https://apnews.com/rss',                                    name: 'AP News' },
    { url: 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml', name: 'NY Times' },
    { url: 'https://www.theguardian.com/world/rss',                     name: 'The Guardian' },
    { url: 'https://www.axios.com/feeds/feed.rss',                      name: 'Axios' },
    { url: 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=US', name: 'Google Trends US' },
    { url: 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN', name: 'Google Trends India' },
  ],

  // ── global: reliable world-news RSS, Google News world as anchor ────────────
  global: [
    { url: 'https://news.google.com/rss/headlines/section/topic/WORLD?hl=en&gl=US&ceid=US:en', name: 'Google News World' },
    { url: 'https://feeds.bbci.co.uk/news/world/rss.xml',               name: 'BBC World' },
    { url: 'https://apnews.com/rss',                                     name: 'AP News' },
    { url: 'https://www.aljazeera.com/xml/rss/all.xml',                  name: 'Al Jazeera' },
    { url: 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',     name: 'NY Times World' },
    { url: 'https://www.theguardian.com/international/rss',              name: 'The Guardian' },
    { url: 'https://www.dw.com/rss/rss.xml',                             name: 'DW News' },
    { url: 'https://feeds.bbci.co.uk/news/business/rss.xml',             name: 'BBC Business' },
    { url: 'https://www.nhk.or.jp/rss/news/cat0.xml',                    name: 'NHK World' },
  ],

  // ── india: Google India news as anchor, Indian publications as pool ──────────
  india: [
    { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=en-IN&gl=IN&ceid=IN:en', name: 'Google News India' },
    { url: 'https://www.thehindu.com/feeder/default.rss',                                name: 'The Hindu' },
    { url: 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms',                 name: 'Times of India' },
    { url: 'https://indianexpress.com/feed/',                                            name: 'Indian Express' },
    { url: 'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',            name: 'Hindustan Times' },
    { url: 'https://www.livemint.com/rss/news',                                          name: 'Mint' },
    { url: 'https://economictimes.indiatimes.com/news/india/rssfeeds/1466318837.cms',    name: 'ET India' },
    { url: 'https://www.ndtv.com/rss/india',                                             name: 'NDTV India' },
    { url: 'https://www.ndtv.com/rss/top-stories',                                      name: 'NDTV Top' },
  ],

  // ── stock: Google Finance/Business as anchor, financial publications as pool ─
  stock: [
    { url: 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en', name: 'Google Finance India' },
    { url: 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en', name: 'Google Finance US' },
    { url: 'https://feeds.bbci.co.uk/news/business/rss.xml',                             name: 'BBC Business' },
    { url: 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',       name: 'ET Markets' },
    { url: 'https://www.livemint.com/rss/markets',                                       name: 'Mint Markets' },
    { url: 'https://economictimes.indiatimes.com/markets/stocks/rss.cms',                name: 'ET Stocks' },
    { url: 'https://www.businessstandard.com/rss/markets-106.rss',                       name: 'Business Standard' },
    { url: 'https://www.moneycontrol.com/rss/MCtopnews.xml',                             name: 'Moneycontrol' },
    { url: 'https://finance.yahoo.com/news/rssindex',                                    name: 'Yahoo Finance' },
  ],

  // ── malayalam: Mathrubhumi is most reliable, rest as pool ───────────────────
  malayalam: [
    { url: 'https://www.mathrubhumi.com/rss/news.xml',                name: 'Mathrubhumi' },
    { url: 'https://www.manoramaonline.com/news/kerala.rssxml',       name: 'Manorama Online' },
    { url: 'https://www.asianetnews.com/rss',                         name: 'Asianet News' },
    { url: 'https://www.madhyamam.com/rss.xml',                       name: 'Madhyamam' },
    { url: 'https://www.deepika.com/rss.xml',                         name: 'Deepika Malayalam' },
    { url: 'https://www.marunadanmalayali.com/rss.xml',               name: 'Marunadan Malayali' },
  ],
};

const SECTION_META = {
  trending: {
    image:  'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200&q=80',
    label:  '🔥 Trending Now',
    accent: '#ef4444'
  },
  global: {
    image:  'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&q=80',
    label:  '🌍 Global News',
    accent: '#3b82f6'
  },
  india: {
    image:  'https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=1200&q=80',
    label:  '🇮🇳 India News',
    accent: '#f97316'
  },
  stock: {
    image:  'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1200&q=80',
    label:  '📈 Stock News',
    accent: '#10b981'
  },
  malayalam: {
    image:  'https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=1200&q=80',
    label:  '🎭 Malayalam News',
    accent: '#8b5cf6'
  }
};

/* ═══════════════════════════════════════════════════
   HTTP HELPER — supports GET and POST, follows redirects
   Returns Promise<string> (response body)
═══════════════════════════════════════════════════ */
function httpsGet(rawUrl, options) {
  return new Promise(function(resolve, reject) {
    options = options || {};
    var parsedUrl = url.parse(rawUrl);
    var transport = parsedUrl.protocol === 'https:' ? https : http;

    var reqOptions = {
      hostname: parsedUrl.hostname,
      port:     parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
      path:     parsedUrl.path || '/',
      method:   options.method || 'GET',
      headers:  Object.assign({
        'User-Agent':      'Mozilla/5.0 (compatible; VilfinNewsBot/2.1; +https://vilfintv.com/bot)',
        'Accept':          'application/rss+xml, application/xml, text/xml, application/atom+xml, */*;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',   // explicitly request no compression
        'Cache-Control':   'no-cache',
        'Connection':      'close'
      }, options.headers || {})
    };

    var req = transport.request(reqOptions, function(res) {
      // Follow redirects (max 5 hops), resolving relative Location URLs
      if ([301,302,303,307,308].includes(res.statusCode) && res.headers.location) {
        var hops = (options._redirects || 0) + 1;
        if (hops > 5) { reject(new Error('Too many redirects')); res.resume(); return; }
        res.resume();
        var loc = res.headers.location;
        // Resolve protocol-relative (//host/path) and absolute-path (/path) redirects
        if (loc.startsWith('//')) {
          loc = parsedUrl.protocol + loc;
        } else if (loc.startsWith('/')) {
          loc = parsedUrl.protocol + '//' + parsedUrl.host + loc;
        } else if (!/^https?:\/\//i.test(loc)) {
          // Relative path — resolve against base
          var base = (parsedUrl.pathname || '/').replace(/[^/]*$/, '');
          loc = parsedUrl.protocol + '//' + parsedUrl.host + base + loc;
        }
        httpsGet(loc, Object.assign({}, options, { _redirects: hops, method: 'GET', body: undefined }))
          .then(resolve).catch(reject);
        return;
      }
      if (res.statusCode && res.statusCode >= 400) {
        res.resume();
        reject(new Error('HTTP ' + res.statusCode + ' for ' + rawUrl));
        return;
      }
      var chunks = [];
      res.on('data', function(c) { chunks.push(c); });
      res.on('end',  function()  { resolve(Buffer.concat(chunks).toString('utf8')); });
      res.on('error', reject);
    });

    req.setTimeout(REQUEST_TIMEOUT_MS, function() {
      req.destroy(new Error('Request timeout: ' + rawUrl));
    });

    if (options.body) req.write(options.body);
    req.on('error', reject);
    req.end();
  });
}

function sleep(ms) { return new Promise(function(r){ setTimeout(r, ms); }); }

// Fisher-Yates shuffle — used to randomise feed selection each run
function shuffle(arr) {
  var a = arr.slice();
  for (var i = a.length - 1; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var t = a[i]; a[i] = a[j]; a[j] = t;
  }
  return a;
}

/* ═══════════════════════════════════════════════════
   RSS FETCHER — accepts {url, name} feed object
   Returns array of parsed items tagged with sourceName
═══════════════════════════════════════════════════ */
async function fetchRSS(feedObj) {
  var feedUrl  = feedObj.url  || feedObj;
  var feedName = feedObj.name || (feedUrl.replace(/^https?:\/\//, '').split('/')[0]);
  try {
    console.log('  Fetching:', feedName);
    var xml = await httpsGet(feedUrl);
    var items = parseRSS(xml);
    if (!items.length && xml && xml.length > 200) {
      // Possibly got HTML bot-detection page or empty feed — log but don't retry
      console.warn('  Feed returned 0 parsed items:', feedName, '(response', xml.length, 'chars)');
    }
    items.forEach(function(item){ item.sourceName = feedName; });
    return items;
  } catch (e) {
    // Single retry after a short back-off (helps with transient network hiccups)
    console.warn('  Feed failed (attempt 1):', feedName, '-', e.message, '— retrying in 3s');
    await sleep(3000);
    try {
      var xml2 = await httpsGet(feedUrl);
      var items2 = parseRSS(xml2);
      items2.forEach(function(item){ item.sourceName = feedName; });
      console.log('  Retry OK:', feedName, '(' + items2.length + ' items)');
      return items2;
    } catch (e2) {
      console.warn('  Feed failed (attempt 2):', feedName, '-', e2.message);
      return [];
    }
  }
}

/* ═══════════════════════════════════════════════════
   XML PARSER — regex-based, no xml2js
═══════════════════════════════════════════════════ */
function extractTagValue(block, tag) {
  // CDATA variant
  var cdRe = new RegExp('<' + tag + '[^>]*>\\s*<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>\\s*<\\/' + tag + '>', 'i');
  // Plain variant
  var plRe = new RegExp('<' + tag + '[^>]*>([\\s\\S]*?)<\\/' + tag + '>', 'i');
  var m = cdRe.exec(block) || plRe.exec(block);
  return m ? m[1].trim() : '';
}

function decodeEntities(str) {
  return str
    .replace(/&amp;/g,  '&')
    .replace(/&lt;/g,   '<')
    .replace(/&gt;/g,   '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g,  "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&#(\d+);/g, function(_, n){ return String.fromCharCode(parseInt(n,10)); });
}

function parseRSS(xml) {
  if (!xml) return [];
  var items = [];

  // Try <item> blocks, fall back to <entry> (Atom)
  var blockRe = /<item[\s>]([\s\S]*?)<\/item>/gi;
  var m;
  var found = false;
  while ((m = blockRe.exec(xml)) !== null) {
    found = true;
    processBlock(m[1], items);
  }
  if (!found) {
    var entryRe = /<entry[\s>]([\s\S]*?)<\/entry>/gi;
    while ((m = entryRe.exec(xml)) !== null) {
      processBlock(m[1], items);
    }
  }
  return items;
}

function processBlock(block, items) {
  var title = decodeEntities(extractTagValue(block, 'title').replace(/<[^>]+>/g,''));
  if (!title || title.length < 5) return;

  var link = extractTagValue(block, 'link') || extractTagValue(block, 'guid');
  // Atom <link href="..."/>
  if (!link) {
    var am = block.match(/<link[^>]+href=["']([^"']+)["']/i);
    if (am) link = am[1];
  }

  var description = decodeEntities(
    (extractTagValue(block, 'description') || extractTagValue(block, 'summary') || extractTagValue(block, 'content'))
      .replace(/<[^>]+>/g, '')
      .replace(/\s+/g, ' ')
      .trim()
  ).slice(0, 500);

  var pubDate = extractTagValue(block, 'pubDate')
    || extractTagValue(block, 'published')
    || extractTagValue(block, 'updated')
    || extractTagValue(block, 'dc:date');

  var publishedAt = null;
  if (pubDate) {
    try { publishedAt = new Date(pubDate).toISOString(); } catch(e) {}
  }
  if (!publishedAt) publishedAt = new Date().toISOString();

  // Infer source name from link domain
  var sourceName = 'Source';
  if (link) {
    var dm = link.match(/https?:\/\/(?:www\.)?([^\/]+)/);
    if (dm) {
      var parts = dm[1].split('.');
      // "economictimes.indiatimes.com" → "Economictimes"
      // "bbc.co.uk" → "Bbc"
      var name = parts.length >= 2 ? parts[parts.length - 2] : parts[0];
      sourceName = name.charAt(0).toUpperCase() + name.slice(1);
    }
  }

  items.push({
    title:       title,
    link:        link || '',
    description: description,
    publishedAt: publishedAt,
    sourceName:  sourceName
  });
}

/* ═══════════════════════════════════════════════════
   CONTENT FILTER
═══════════════════════════════════════════════════ */
function filterItem(item) {
  var text = (item.title + ' ' + item.description).toLowerCase();
  for (var i = 0; i < BLOCKED_KEYWORDS.length; i++) {
    if (text.includes(BLOCKED_KEYWORDS[i])) {
      console.log('  [FILTERED]', item.title.slice(0, 60));
      return false;
    }
  }
  return true;
}

/* ═══════════════════════════════════════════════════
   DEDUP — Jaccard on word sets
═══════════════════════════════════════════════════ */
function titleWords(title) {
  return new Set(
    title.toLowerCase()
      .replace(/[^a-z0-9ഀ-ൿ ]/g, ' ')
      .split(/\s+/)
      .filter(function(w){ return w.length > 3; })
  );
}

function isDuplicate(item, seen) {
  var words = titleWords(item.title);
  for (var i = 0; i < seen.length; i++) {
    var sw = titleWords(seen[i].title);
    var intersection = 0;
    words.forEach(function(w){ if (sw.has(w)) intersection++; });
    var union = words.size + sw.size - intersection;
    if (union > 0 && intersection / union > 0.5) return true;
  }
  return false;
}

/* ═══════════════════════════════════════════════════
   CORROBORATION — story appears in ≥1 source
═══════════════════════════════════════════════════ */
function isCorroborated(item, otherItems) {
  var words = titleWords(item.title);
  for (var i = 0; i < otherItems.length; i++) {
    if (otherItems[i] === item) continue;
    var sw = titleWords(otherItems[i].title);
    var intersection = 0;
    words.forEach(function(w){ if (sw.has(w)) intersection++; });
    var union = words.size + sw.size - intersection;
    if (union > 0 && intersection / union > 0.3) return true;
  }
  return false;
}

/* ═══════════════════════════════════════════════════
   GEMINI API CALL
═══════════════════════════════════════════════════ */
async function callGemini(prompt) {
  if (!GOOGLE_AI_API_KEY) throw new Error('No GOOGLE_AI_API_KEY');

  var body = JSON.stringify({
    contents: [{ parts: [{ text: prompt }] }],
    safetySettings: [
      { category: 'HARM_CATEGORY_HATE_SPEECH',       threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
      { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
      { category: 'HARM_CATEGORY_HARASSMENT',        threshold: 'BLOCK_MEDIUM_AND_ABOVE' }
    ],
    generationConfig: { maxOutputTokens: 1400, temperature: 0.55 }
  });

  var apiUrl = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=' + GOOGLE_AI_API_KEY;
  var response = await httpsGet(apiUrl, {
    method: 'POST',
    headers: {
      'Content-Type':   'application/json',
      'Content-Length': Buffer.byteLength(body)
    },
    body: body
  });

  var parsed = JSON.parse(response);
  var text = parsed
    && parsed.candidates
    && parsed.candidates[0]
    && parsed.candidates[0].content
    && parsed.candidates[0].content.parts
    && parsed.candidates[0].content.parts[0].text;
  if (!text) throw new Error('Gemini: empty or blocked response');
  return text.trim();
}

/* ═══════════════════════════════════════════════════
   GROQ API CALL (fallback)
═══════════════════════════════════════════════════ */
async function callGroq(prompt) {
  if (!GROQ_API_KEY) throw new Error('No GROQ_API_KEY');

  var body = JSON.stringify({
    model:       'llama-3.1-8b-instant',
    messages:    [{ role: 'user', content: prompt }],
    max_tokens:  1400,
    temperature: 0.55
  });

  var response = await httpsGet('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + GROQ_API_KEY,
      'Content-Type':  'application/json',
      'Content-Length': Buffer.byteLength(body)
    },
    body: body
  });

  var parsed = JSON.parse(response);
  var text = parsed
    && parsed.choices
    && parsed.choices[0]
    && parsed.choices[0].message
    && parsed.choices[0].message.content;
  if (!text) throw new Error('Groq: empty response');
  return text.trim();
}

/* ═══════════════════════════════════════════════════
   BUILD PROMPT — full 4-5 paragraph article
═══════════════════════════════════════════════════ */
function buildPrompt(item, isMalayalam) {
  var base = 'You are a senior journalist at an international news publication. '
    + 'Write a complete, factual, well-researched news article of 4 to 5 paragraphs '
    + '(450 to 600 words) about this story: "' + item.title + '"\n\n'
    + 'Source context: ' + (item.description || 'No additional context available.') + '\n\n'
    + 'Article structure:\n'
    + '* Paragraph 1 — The lede: the single most important fact, with who/what/when/where\n'
    + '* Paragraph 2 — Background and context that explains why this matters\n'
    + '* Paragraph 3 — Key details, relevant data, expert viewpoints or official statements\n'
    + '* Paragraph 4 — Broader impact, public reaction, or wider implications\n'
    + '* Paragraph 5 — What happens next, open questions, or conclusion\n\n'
    + 'Style rules:\n'
    + '- BBC / Reuters journalism standard: factual, balanced, impartial\n'
    + '- Cross-check the facts stated in the context before writing\n'
    + '- Do NOT copy source text verbatim\n'
    + '- Do NOT use bullet points, headers, or markdown formatting\n'
    + '- Write in plain flowing prose paragraphs only\n'
    + '- Do NOT include a byline, dateline, or "Source:" footer\n'
    + '- Separate each paragraph with a blank line\n';

  if (isMalayalam) {
    return base + '- Write ENTIRELY in Malayalam script (not transliteration). Every single word must be in Malayalam.';
  }
  return base;
}

/* ═══════════════════════════════════════════════════
   GENERATE STORY — Gemini → Groq → RSS fallback
═══════════════════════════════════════════════════ */
async function generateStory(item, isMalayalam) {
  var prompt = buildPrompt(item, isMalayalam);
  var story  = null;

  try {
    story = await callGemini(prompt);
    console.log('    [Gemini OK]', item.title.slice(0, 55));
  } catch (e) {
    console.warn('    [Gemini FAIL]', e.message);
  }

  if (!story) {
    try {
      story = await callGroq(prompt);
      console.log('    [Groq OK]', item.title.slice(0, 55));
    } catch (e) {
      console.warn('    [Groq FAIL]', e.message);
    }
  }

  if (!story) {
    // No-AI fallback: compose a clean article from the RSS headline + description
    var desc = (item.description || '').trim();
    var src  = item.sourceName ? ' via ' + item.sourceName : '';
    story = item.title + '.\n\n'
      + (desc ? desc + '\n\n' : '')
      + 'This story was sourced' + src + '. Full editorial coverage will be available at the next scheduled update.';
    console.warn('    [RSS fallback]', item.title.slice(0, 55));
  }

  return story.trim();
}

/* ═══════════════════════════════════════════════════
   BUILD SECTION
   feedPool — array of {url, name} objects (full pool)
═══════════════════════════════════════════════════ */
async function buildSection(sectionId, feedPool, meta) {
  console.log('\n[Section]', sectionId.toUpperCase());
  var isMalayalam = sectionId === 'malayalam';

  // Randomly pick FEEDS_PER_SECTION from the pool so stories rotate each run.
  // Always include the first TWO anchored entries + random extras for variety.
  var pool    = feedPool || [];
  var anchors = pool.slice(0, 2);
  var rest    = shuffle(pool.slice(2));
  var chosen  = anchors.concat(rest).slice(0, FEEDS_PER_SECTION);
  console.log('  Sources chosen:', chosen.map(function(f){ return f.name || f.url; }).join(', '));

  // Fetch all chosen feeds in PARALLEL for speed
  var results = await Promise.allSettled(chosen.map(function(f){ return fetchRSS(f); }));
  var allItems = [];
  results.forEach(function(r, i) {
    if (r.status === 'fulfilled') {
      console.log('  Parsed', r.value.length, 'items from', chosen[i].name || chosen[i].url);
      allItems = allItems.concat(r.value);
    }
  });

  // Filter blocked content
  allItems = allItems.filter(filterItem);

  // Deduplicate
  var deduped = [];
  allItems.forEach(function(item) {
    if (!isDuplicate(item, deduped)) deduped.push(item);
  });

  // Sort newest first
  deduped.sort(function(a, b) {
    return new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime();
  });

  console.log('  Items after dedup+filter:', deduped.length);
  var selected = deduped.slice(0, MAX_ITEMS_PER_SECTION);

  // Placeholder if empty
  if (selected.length === 0) {
    console.warn('  No items for', sectionId, '— inserting placeholder');
    return makePlaceholderSection(sectionId, meta);
  }

  // Generate stories
  var outputItems = [];
  for (var j = 0; j < selected.length; j++) {
    var item = selected[j];
    console.log('  Generating', (j + 1) + '/' + selected.length + ':', item.title.slice(0, 65));

    var storyText = await generateStory(item, isMalayalam);

    // Wrap paragraphs
    var storyHtml = storyText
      .split('\n')
      .filter(function(l){ return l.trim(); })
      .map(function(l){
        return '<p>' + l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</p>';
      })
      .join('');

    var teaser = storyText.replace(/<[^>]+>/g, '').slice(0, 120).trim();
    if (teaser.length === 120) teaser += '…';

    var id = sectionId + '-' + Date.now() + '-' + j;

    outputItems.push({
      id:          id,
      headline:    item.title,
      teaser:      teaser,
      story:       storyHtml,
      source:      item.sourceName,
      sourceUrl:   item.link || '',
      publishedAt: item.publishedAt,
      expiresAt:   new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString(),
      verified:    isCorroborated(item, allItems),
      aiGenerated: true
    });

    // Gentle rate-limit pause between AI calls (longer for extended content)
    if (j < selected.length - 1) await sleep(1000);
  }

  return {
    image:  meta.image,
    label:  meta.label,
    accent: meta.accent,
    items:  outputItems
  };
}

function makePlaceholderSection(sectionId, meta) {
  return {
    image:  meta.image,
    label:  meta.label,
    accent: meta.accent,
    items: [{
      id:          sectionId + '-placeholder-' + Date.now(),
      headline:    'Content updating…',
      teaser:      'New stories will appear at the next scheduled refresh.',
      story:       '<p>New stories will appear at the next scheduled refresh. Please check back shortly.</p>',
      source:      'VilfinTV',
      sourceUrl:   'https://vilfintv.com/news.html',
      publishedAt: new Date().toISOString(),
      expiresAt:   new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
      verified:    false,
      aiGenerated: false
    }]
  };
}

/* ═══════════════════════════════════════════════════
   MERGE ITEMS — accumulate stories across runs, keep 48h
   newItems     — freshly generated items from this run
   existingItems — items already in data/news.json
═══════════════════════════════════════════════════ */
function mergeItems(newItems, existingItems) {
  var TWO_DAYS = 48 * 60 * 60 * 1000;
  var now = Date.now();

  // Purge existing items older than 48 hours AND strip any placeholder items
  // so real stories can always replace them on the next successful fetch
  var validExisting = (existingItems || []).filter(function(item) {
    if (!item || !item.publishedAt || !item.headline) return false;
    var hl = item.headline.trim().toLowerCase();
    if (hl.startsWith('content updating') || hl === 'placeholder' || hl === 'loading...') return false;
    return now - new Date(item.publishedAt).getTime() < TWO_DAYS;
  });

  // Add new items that aren't already represented (by ID or title similarity)
  var toAdd = (newItems || []).filter(function(newItem) {
    // Skip if same ID already exists
    var idMatch = validExisting.some(function(e) { return e.id === newItem.id; });
    if (idMatch) return false;
    // Skip if title is too similar (dedup)
    return !isDuplicate(newItem, validExisting);
  });

  console.log('  Merge: +' + toAdd.length + ' new stories, ' + validExisting.length + ' existing kept');

  // Newest first: new items before existing, then sort by publishedAt descending
  var combined = toAdd.concat(validExisting);
  combined.sort(function(a, b) {
    return new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime();
  });

  // Cap at 20 per section to keep JSON size manageable
  return combined.slice(0, 20);
}

/* ═══════════════════════════════════════════════════
   MAIN
═══════════════════════════════════════════════════ */
async function main() {
  console.log('='.repeat(60));
  console.log('VilfinTV News Builder v2');
  console.log('Started   :', new Date().toISOString());
  console.log('Gemini key:', GOOGLE_AI_API_KEY ? 'present (' + GOOGLE_AI_API_KEY.slice(0,4) + '...)' : 'MISSING');
  console.log('Groq key  :', GROQ_API_KEY      ? 'present (' + GROQ_API_KEY.slice(0,4) + '...)'      : 'MISSING');
  console.log('='.repeat(60));

  // ── Load existing JSON to accumulate stories over 48 hours ───────────────
  var dataDir = path.join(__dirname, '..', 'data');
  var outPath = path.join(dataDir, 'news.json');
  var existingData = null;
  if (fs.existsSync(outPath)) {
    try {
      existingData = JSON.parse(fs.readFileSync(outPath, 'utf8'));
      console.log('Loaded existing news.json for accumulation merge');
    } catch(e) {
      console.warn('Could not read existing news.json:', e.message);
    }
  }

  var output = {
    generated: new Date().toISOString(),
    sections:  {}
  };

  var sectionIds = Object.keys(SOURCE_POOL);

  for (var i = 0; i < sectionIds.length; i++) {
    var sid = sectionIds[i];
    try {
      var newSection = await buildSection(sid, SOURCE_POOL[sid], SECTION_META[sid]);

      // Merge new items with surviving existing items (within 48h window)
      var existingItems = existingData
        && existingData.sections
        && existingData.sections[sid]
        && existingData.sections[sid].items
        ? existingData.sections[sid].items
        : [];
      newSection.items = mergeItems(newSection.items, existingItems);
      output.sections[sid] = newSection;
    } catch (e) {
      console.error('Section', sid, 'failed entirely:', e.message);
      output.sections[sid] = makePlaceholderSection(sid, SECTION_META[sid]);
    }
  }

  // Ensure data directory exists
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
    console.log('\nCreated data/ directory');
  }

  fs.writeFileSync(outPath, JSON.stringify(output, null, 2) + '\n', 'utf8');

  // Summary
  var totalItems = 0;
  console.log('\n' + '='.repeat(60));
  console.log('Output:', outPath);
  sectionIds.forEach(function(sid) {
    var count = output.sections[sid] && output.sections[sid].items
      ? output.sections[sid].items.length : 0;
    totalItems += count;
    console.log('  ' + sid.padEnd(12) + ':', count, 'items');
  });
  console.log('  TOTAL       :', totalItems, 'items');
  console.log('Completed :', new Date().toISOString());
  console.log('='.repeat(60));
}

main().catch(function(e) {
  console.error('FATAL:', e);
  process.exit(1);
});
