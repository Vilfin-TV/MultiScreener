const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { DOMParser } = require('@xmldom/xmldom');

const PEXELS_API_KEY = process.env.PEXELS_API_KEY;
const DATA_FILE = path.join(__dirname, '../data/breaking_news.json');
const CACHE_FILE = path.join(__dirname, '../data/pexels_cache.json');
// Use direct publisher RSS feeds for requested regions that include images
const FEEDS = [
  { url: 'https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml', name: 'US', id: 'us' },
  { url: 'https://feeds.bbci.co.uk/news/world/europe/rss.xml', name: 'Europe', id: 'eu' },
  { url: 'https://japantoday.com/feed', name: 'Japan', id: 'jp' },
  { url: 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms', name: 'India', id: 'in' },
  { url: 'https://www.thehindu.com/news/national/kerala/feeder/default.rss', name: 'Kerala', id: 'kl' },
  { url: 'https://timesofindia.indiatimes.com/rssfeeds/2950623.cms', name: 'Tamil Nadu', id: 'tn' },
  { url: 'https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms', name: 'Mumbai', id: 'mh' },
  { url: 'https://timesofindia.indiatimes.com/rssfeeds/-2128839598.cms', name: 'Delhi', id: 'dl' },
  { url: 'https://feeds.bbci.co.uk/news/world/asia/rss.xml', name: 'Asia', id: 'as' },
  { url: 'https://feeds.bbci.co.uk/news/world/middle_east/rss.xml', name: 'Middle East', id: 'me' }
];

// Create data dir if not exists
if (!fs.existsSync(path.dirname(DATA_FILE))) {
  fs.mkdirSync(path.dirname(DATA_FILE), { recursive: true });
}

// Load Pexels Cache
let pexelsCache = {};
if (fs.existsSync(CACHE_FILE)) {
  try {
    pexelsCache = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
  } catch(e){}
}
let pexelsCallsThisRun = 0;
const MAX_PEXELS_CALLS = 10; // Keep well under 200/hr limit

// ── Pexels Logic ──
const KEYWORD_MAP = {
  'modi': 'Narendra Modi',
  'trump': 'Donald Trump',
  'satheesan': 'VD Satheesan',
  'pinarayi': 'Pinarayi Vijayan',
  'rahul gandhi': 'Rahul Gandhi',
  'biden': 'Joe Biden',
  'market': 'Stock Market',
  'sensex': 'Stock Market',
  'nifty': 'Stock Market',
  'stocks': 'Stock Market',
  'cricket': 'Cricket Match',
  'football': 'Football Match',
  'israel': 'Israel conflict',
  'gaza': 'Gaza conflict',
  'ukraine': 'Ukraine war',
  'russia': 'Russia',
  'china': 'China Beijing',
  'tech': 'Technology AI',
  'ai': 'Artificial Intelligence',
  'gold': 'Gold bars',
  'crypto': 'Cryptocurrency Bitcoin',
  'bitcoin': 'Bitcoin',
  'kerala': 'Kerala nature'
};

async function fetchPexels(query) {
  if (pexelsCache[query]) return pexelsCache[query];
  if (!PEXELS_API_KEY || pexelsCallsThisRun >= MAX_PEXELS_CALLS) return null;
  
  pexelsCallsThisRun++;
  console.log(`[Pexels] Fetching image for: ${query}`);
  
  return new Promise((resolve) => {
    const opts = {
      hostname: 'api.pexels.com',
      path: '/v1/search?query=' + encodeURIComponent(query) + '&per_page=1&orientation=landscape',
      headers: { 'Authorization': PEXELS_API_KEY }
    };
    https.get(opts, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const j = JSON.parse(data);
          if (j.photos && j.photos.length > 0) {
            const url = j.photos[0].src.large;
            pexelsCache[query] = url;
            resolve(url);
          } else {
            pexelsCache[query] = 'NONE'; // Cache misses so we don't spam
            resolve(null);
          }
        } catch(e) { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });
}

async function getFallbackImage(title) {
  const tl = title.toLowerCase();
  
  // 1. Dictionary match
  for (const [key, searchQ] of Object.entries(KEYWORD_MAP)) {
    if (tl.includes(key)) {
      const img = await fetchPexels(searchQ);
      if (img && img !== 'NONE') return img;
    }
  }
  
  // 2. Generic Pexels search using first 2 capitalized words
  const matches = title.match(/[A-Z][a-z]+/g);
  if (matches && matches.length >= 2) {
    const q = matches.slice(0,2).join(' ');
    const img = await fetchPexels(q);
    if (img && img !== 'NONE') return img;
  }
  
  // 3. Fallback to generic Picsum seed
  let h = 0;
  for (let i = 0; i < title.length; i++) { h = Math.imul(31, h) + title.charCodeAt(i) | 0; }
  return `https://picsum.photos/seed/lnbt${Math.abs(h) % 8999 + 1000}/500/280`;
}

// ── RSS Fetching ──
function fetchRss(url) {
  return new Promise((resolve) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, { timeout: 10000, headers: {'User-Agent': 'VilfinTV-Builder/1.0'} }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        let loc = res.headers.location;
        if (loc.startsWith('/')) {
          const u = new URL(url);
          loc = u.protocol + '//' + u.host + loc;
        }
        return resolve(fetchRss(loc));
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', () => resolve(''));
    req.on('timeout', () => { req.destroy(); resolve(''); });
  });
}

function parseXmlItems(xmlStr) {
  try {
    const xml = new DOMParser().parseFromString(xmlStr, 'text/xml');
    const nodes = Array.from(xml.getElementsByTagName('item'));
    const entries = Array.from(xml.getElementsByTagName('entry'));
    const all = nodes.length ? nodes : entries;
    
    return all.slice(0, 16).map(item => {
      let link = '';
      const linkEl = item.getElementsByTagName('link')[0];
      if (linkEl) {
        link = linkEl.getAttribute('href') || linkEl.textContent || '';
      }
      if (!link) {
        const guidEl = item.getElementsByTagName('guid')[0];
        if (guidEl) link = guidEl.textContent || '';
      }
      link = link.replace(/^<!\[CDATA\[|\]\]>$/g, '').trim() || '#';

      let image = '';
      const mc = item.getElementsByTagName('media:content')[0] || item.getElementsByTagName('media:thumbnail')[0];
      if (mc) image = mc.getAttribute('url') || '';
      if (!image) {
        const enc = item.getElementsByTagName('enclosure')[0];
        if (enc && /^image\//i.test(enc.getAttribute('type') || '')) image = enc.getAttribute('url') || '';
      }
      if (!image) {
        const descRaw = (item.getElementsByTagName('description')[0] || item.getElementsByTagName('summary')[0] || {}).textContent || '';
        const m = descRaw.match(/<img[^>]+src="([^">]+)"/);
        if (m) image = m[1];
      }

      const pubDate = (item.getElementsByTagName('pubDate')[0] || item.getElementsByTagName('published')[0] || {}).textContent || '';
      const title = (item.getElementsByTagName('title')[0] || {}).textContent || '';
      
      const descRaw = (item.getElementsByTagName('description')[0] || item.getElementsByTagName('content:encoded')[0] || item.getElementsByTagName('summary')[0] || {}).textContent || '';
      const snippet = descRaw.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().substring(0, 300);

      return {
        title: title.replace(/^<!\[CDATA\[|\]\]>$/g, '').trim(),
        link: link,
        pubDate: pubDate,
        description: snippet,
        image: image
      };
    }).filter(i => i.title);
  } catch(e) {
    return [];
  }
}

async function run() {
  console.log('Starting Live News Build...');
  
  const sources = FEEDS;
  
  let allItems = [];

  // Process sequentially to respect limits
  for (const src of sources) {
    console.log(`Fetching: ${src.id} (${src.label}) - ${src.url}`);
    
    // We can use the allorigins proxy if direct fails, but node fetch is usually okay.
    // For Google News, direct fetch works.
    let xml = await fetchRss(src.url);
    if (!xml || !xml.includes('<title>')) {
      // Fallback to allorigins if blocked
      const pUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(src.url)}`;
      const pRes = await fetchRss(pUrl);
      try {
        const j = JSON.parse(pRes);
        xml = j.contents || '';
      } catch(e){}
    }
    
    const items = parseXmlItems(xml);
    console.log(`  -> Parsed ${items.length} items`);
    
    // Process images
    for (let i = 0; i < Math.min(items.length, 10); i++) {
      if (!items[i].image) {
        items[i].image = await getFallbackImage(items[i].title);
      }
    }
    
    allItems.push(...items.filter(i => i.image));
  }
  
  
  // Deduplicate
  const seen = new Set();
  const uniqueItems = [];
  for (let item of allItems) {
    const key = item.title.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (!seen.has(key)) {
      seen.add(key);
      uniqueItems.push({
        title: item.title,
        link: item.link,
        description: item.description,
        publishedAt: item.pubDate ? new Date(item.pubDate).getTime() : Date.now(),
        imageUrl: item.image
      });
    }
  }

  // Sort by newest
  uniqueItems.sort((a, b) => b.publishedAt - a.publishedAt);
  const finalItems = uniqueItems.slice(0, 20);

  // Save output
  fs.writeFileSync(DATA_FILE, JSON.stringify(finalItems, null, 2));
  fs.writeFileSync(CACHE_FILE, JSON.stringify(pexelsCache, null, 2));
  console.log('Build complete! Data saved to data/breaking_news.json');

}

run().catch(console.error);
