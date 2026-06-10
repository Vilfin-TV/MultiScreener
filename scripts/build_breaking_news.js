const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { DOMParser } = require('@xmldom/xmldom');

const DATA_FILE = path.join(__dirname, '../data/breaking_news.json');
const CACHE_FILE = path.join(__dirname, '../data/pexels_cache.json');
const PEXELS_API_KEY = process.env.PEXELS_API_KEY;

// ── TWO-TIER FEEDS ──
const FEEDS = {
  "India": {
    "National": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "Kerala": "https://www.thehindu.com/news/national/kerala/feeder/default.rss",
    "Tamil Nadu": "https://timesofindia.indiatimes.com/rssfeeds/2950623.cms",
    "Karnataka": "https://timesofindia.indiatimes.com/rssfeeds/-2128833038.cms",
    "Maharashtra": "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms",
    "Delhi": "https://news.google.com/rss/search?q=delhi+news&hl=en-IN&gl=IN&ceid=IN:en",
    "Gujarat": "https://news.google.com/rss/search?q=gujarat+news&hl=en-IN&gl=IN&ceid=IN:en",
    "West Bengal": "https://news.google.com/rss/search?q=west+bengal+news&hl=en-IN&gl=IN&ceid=IN:en",
    "Uttar Pradesh": "https://news.google.com/rss/search?q=uttar+pradesh+news&hl=en-IN&gl=IN&ceid=IN:en",
    "Punjab": "https://news.google.com/rss/search?q=punjab+news&hl=en-IN&gl=IN&ceid=IN:en",
    "Rajasthan": "https://news.google.com/rss/search?q=rajasthan+news&hl=en-IN&gl=IN&ceid=IN:en",
    "Bihar": "https://news.google.com/rss/search?q=bihar+news&hl=en-IN&gl=IN&ceid=IN:en"
  },
  "Asia": {
    "Asia General": "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
    "Japan": "https://japantoday.com/feed",
    "China": "https://news.google.com/rss/search?q=china+news+english&hl=en&gl=US&ceid=US:en",
    "Singapore": "https://news.google.com/rss/search?q=singapore+news&hl=en-SG&gl=SG&ceid=SG:en",
    "Thailand": "https://news.google.com/rss/search?q=thailand+news&hl=en&gl=US&ceid=US:en",
    "Vietnam": "https://news.google.com/rss/search?q=vietnam+news+english&hl=en&gl=US&ceid=US:en",
    "Malaysia": "https://news.google.com/rss/search?q=malaysia+news&hl=en-MY&gl=MY&ceid=MY:en",
    "Taiwan": "https://news.google.com/rss/search?q=taiwan+news+english&hl=en&gl=US&ceid=US:en",
    "Bangladesh": "https://www.thedailystar.net/frontpage/rss.xml",
    "Sri Lanka": "https://news.google.com/rss/search?q=sri+lanka+news&hl=en&gl=US&ceid=US:en",
    "Afghanistan": "https://news.google.com/rss/search?q=afghanistan+news&hl=en&gl=US&ceid=US:en"
  },
  "North America": {
    "US": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
    "Canada": "https://www.cbc.ca/webfeed/rss/rss-canada",
    "Mexico": "https://news.google.com/rss/search?q=mexico+news+english&hl=en&gl=US&ceid=US:en"
  },
  "South America": {
    "Brazil": "https://news.google.com/rss/search?q=brazil+news+english&hl=en&gl=US&ceid=US:en",
    "Argentina": "https://news.google.com/rss/search?q=argentina+news+english&hl=en&gl=US&ceid=US:en",
    "Colombia": "https://news.google.com/rss/search?q=colombia+news+english&hl=en&gl=US&ceid=US:en",
    "Chile": "https://news.google.com/rss/search?q=chile+news+english&hl=en&gl=US&ceid=US:en",
    "Peru": "https://news.google.com/rss/search?q=peru+news+english&hl=en&gl=US&ceid=US:en"
  },
  "Europe": {
    "Europe General": "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
    "UK": "https://feeds.bbci.co.uk/news/uk/rss.xml",
    "France": "https://www.france24.com/en/rss",
    "Germany": "https://rss.dw.com/rdf/rss-en-all",
    "Italy": "https://news.google.com/rss/search?q=italy+news+english&hl=en&gl=US&ceid=US:en",
    "Spain": "https://news.google.com/rss/search?q=spain+news+english&hl=en&gl=US&ceid=US:en",
    "Netherlands": "https://news.google.com/rss/search?q=netherlands+news+english&hl=en&gl=US&ceid=US:en",
    "Switzerland": "https://news.google.com/rss/search?q=switzerland+news+english&hl=en&gl=US&ceid=US:en",
    "Sweden": "https://news.google.com/rss/search?q=sweden+news+english&hl=en&gl=US&ceid=US:en",
    "Poland": "https://news.google.com/rss/search?q=poland+news+english&hl=en&gl=US&ceid=US:en",
    "Ireland": "https://news.google.com/rss/search?q=ireland+news&hl=en-IE&gl=IE&ceid=IE:en",
    "Russia": "https://www.themoscowtimes.com/rss/news",
    "Ukraine": "https://kyivindependent.com/rss/"
  },
  "Middle East": {
    "Middle East General": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "UAE": "https://www.khaleejtimes.com/rss",
    "Saudi Arabia": "https://www.arabnews.com/rss.xml",
    "Israel": "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
    "Qatar": "https://www.aljazeera.com/xml/rss/all.xml",
    "Egypt": "https://news.google.com/rss/search?q=egypt+news+english&hl=en&gl=US&ceid=US:en",
    "Turkey": "https://news.google.com/rss/search?q=turkey+news+english&hl=en&gl=US&ceid=US:en",
    "Lebanon": "https://news.google.com/rss/search?q=lebanon+news+english&hl=en&gl=US&ceid=US:en",
    "Iran": "https://www.tehrantimes.com/rss"
  },
  "Australia": {
    "Australia": "https://www.abc.net.au/news/feed/51120/rss.xml",
    "New Zealand": "https://news.google.com/rss/search?q=new+zealand+news&hl=en-NZ&gl=NZ&ceid=NZ:en"
  },
  "Africa": {
    "Africa": "https://feeds.bbci.co.uk/news/world/africa/rss.xml",
    "South Africa": "https://news.google.com/rss/search?q=south+africa+news&hl=en-ZA&gl=ZA&ceid=ZA:en",
    "Nigeria": "https://news.google.com/rss/search?q=nigeria+news&hl=en-NG&gl=NG&ceid=NG:en",
    "Kenya": "https://news.google.com/rss/search?q=kenya+news&hl=en-KE&gl=KE&ceid=KE:en",
    "Ghana": "https://news.google.com/rss/search?q=ghana+news&hl=en-GH&gl=GH&ceid=GH:en",
    "Morocco": "https://news.google.com/rss/search?q=morocco+news+english&hl=en&gl=US&ceid=US:en"
  }
};

if (!fs.existsSync(path.dirname(DATA_FILE))) {
  fs.mkdirSync(path.dirname(DATA_FILE), { recursive: true });
}

let pexelsCache = {};
if (fs.existsSync(CACHE_FILE)) {
  try {
    pexelsCache = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
  } catch(e){}
}
let pexelsCallsThisRun = 0;
const MAX_PEXELS_CALLS = 10;

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
            pexelsCache[query] = 'NONE';
            resolve(null);
          }
        } catch(e) { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });
}

async function getFallbackImage(title) {
  const tl = title.toLowerCase();
  for (const [key, searchQ] of Object.entries(KEYWORD_MAP)) {
    if (tl.includes(key)) {
      const img = await fetchPexels(searchQ);
      if (img && img !== 'NONE') return img;
    }
  }
  const matches = title.match(/[A-Z][a-z]+/g);
  if (matches && matches.length >= 2) {
    const q = matches.slice(0,2).join(' ');
    const img = await fetchPexels(q);
    if (img && img !== 'NONE') return img;
  }
  let h = 0;
  for (let i = 0; i < title.length; i++) { h = Math.imul(31, h) + title.charCodeAt(i) | 0; }
  return `https://picsum.photos/seed/lnbt${Math.abs(h) % 8999 + 1000}/500/280`;
}

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
    
    return all.slice(0, 30).map(item => {
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

      // Upscale images for better clarity
      if (image) {
        if (image.includes('ichef.bbci.co.uk') && image.includes('/standard/')) {
          image = image.replace(/\/standard\/\d+\//, '/standard/1024/');
        } else if (image.includes('googleusercontent') || image.includes('gstatic')) {
          image = image.replace(/-w\d+-h\d+-c/g, '-w1024-h576-c').replace(/=s\d+-/g, '=s1024-');
        } else if (image.includes('toiimg.com') && image.includes('imgsize-')) {
          image = image.replace(/,imgsize-\d+/, '');
        }
      }

      const pubDate = (item.getElementsByTagName('pubDate')[0] || item.getElementsByTagName('published')[0] || {}).textContent || '';
      const title = (item.getElementsByTagName('title')[0] || {}).textContent || '';
      
      const descRaw = (item.getElementsByTagName('description')[0] || item.getElementsByTagName('content:encoded')[0] || item.getElementsByTagName('summary')[0] || {}).textContent || '';
      const snippet = descRaw.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().substring(0, 300);

      // We need to parse publisher info from description/title if applicable
      let publisher = '';
      const sourceEl = item.getElementsByTagName('source')[0];
      if (sourceEl) publisher = sourceEl.textContent || '';

      return {
        title: title.replace(/^<!\[CDATA\[|\]\]>$/g, '').trim(),
        link: link,
        pubDate: pubDate,
        description: snippet,
        image: image,
        source: publisher
      };
    }).filter(i => i.title);
  } catch(e) {
    return [];
  }
}

async function run() {
  console.log('Starting Live News Build...');
  
  const outputData = {};

  for (const [continent, regions] of Object.entries(FEEDS)) {
    outputData[continent] = {};
    for (const [regionName, url] of Object.entries(regions)) {
      console.log(`Fetching: ${continent} -> ${regionName} - ${url}`);
      
      let xml = await fetchRss(url);
      if (!xml || !xml.includes('<title>')) {
        const pUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(url)}`;
        const pRes = await fetchRss(pUrl);
        try {
          const j = JSON.parse(pRes);
          xml = j.contents || '';
        } catch(e){}
      }
      
      let items = parseXmlItems(xml);
      console.log(`  -> Parsed ${items.length} items`);
      
      // Process images for top 5 items per region to save Pexels credits
      for (let i = 0; i < Math.min(items.length, 5); i++) {
        if (!items[i].image) {
          items[i].image = await getFallbackImage(items[i].title);
        }
      }
      
      items = items.filter(i => i.image).map(item => ({
        title: item.title,
        link: item.link,
        description: item.description,
        publishedAt: item.pubDate ? new Date(item.pubDate).getTime() : Date.now(),
        imageUrl: item.image,
        source: item.source || regionName
      }));
      
      // Sort and take top 16 — side column scrolls on the page
      items.sort((a, b) => b.publishedAt - a.publishedAt);
      outputData[continent][regionName] = items.slice(0, 16);
    }
  }

  fs.writeFileSync(DATA_FILE, JSON.stringify(outputData, null, 2));
  fs.writeFileSync(CACHE_FILE, JSON.stringify(pexelsCache, null, 2));
  console.log('Build complete! Data saved to data/breaking_news.json');
}

run().catch(console.error);
