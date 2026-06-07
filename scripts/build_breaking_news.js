'use strict';

const https = require('https');
const http  = require('http');
const fs    = require('fs');
const path  = require('path');
const url   = require('url');

const REQUEST_TIMEOUT_MS = 22000;

// Use direct publisher RSS feeds that usually include images via <media:content> or embedded <img>
const FEEDS = [
  { url: 'https://feeds.bbci.co.uk/news/world/rss.xml', name: 'BBC World' },
  { url: 'https://www.aljazeera.com/xml/rss/all.xml', name: 'Al Jazeera' },
  { url: 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml', name: 'NYT World' },
  { url: 'https://www.dw.com/rss/rss.xml', name: 'DW News' },
  { url: 'https://www.thehindu.com/feeder/default.rss', name: 'The Hindu' },
  { url: 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms', name: 'Times of India' },
  { url: 'https://indianexpress.com/feed/', name: 'Indian Express' },
  { url: 'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml', name: 'Hindustan Times' },
  { url: 'https://www.livemint.com/rss/news', name: 'Mint' },
  { url: 'https://feeds.bbci.co.uk/news/business/rss.xml', name: 'BBC Business' }
];

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
        'User-Agent':      'Mozilla/5.0 (compatible; VilfinNewsBot/3.0; +https://vilfintv.com/bot)',
        'Accept':          'application/rss+xml, application/xml, text/xml, application/atom+xml, */*;q=0.9'
      }, options.headers || {})
    };

    var req = transport.request(reqOptions, function(res) {
      if ([301,302,303,307,308].includes(res.statusCode) && res.headers.location) {
        var hops = (options._redirects || 0) + 1;
        if (hops > 5) { reject(new Error('Too many redirects')); res.resume(); return; }
        res.resume();
        var loc = res.headers.location;
        if (loc.startsWith('//')) loc = parsedUrl.protocol + loc;
        else if (loc.startsWith('/')) loc = parsedUrl.protocol + '//' + parsedUrl.host + loc;
        else if (!/^https?:\/\//i.test(loc)) loc = parsedUrl.protocol + '//' + parsedUrl.host + (parsedUrl.pathname || '/').replace(/[^/]*$/, '') + loc;
        
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

function extractTagValue(block, tag) {
  var cdRe = new RegExp('<' + tag + '[^>]*>\\s*<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>\\s*<\\/' + tag + '>', 'i');
  var plRe = new RegExp('<' + tag + '[^>]*>([\\s\\S]*?)<\\/' + tag + '>', 'i');
  var m = cdRe.exec(block) || plRe.exec(block);
  return m ? m[1].trim() : '';
}

function decodeEntities(str) {
  return str
    .replace(/&amp;/g,  '&').replace(/&lt;/g,  '<').replace(/&gt;/g,  '>')
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&#x([0-9a-fA-F]+);/g, function(_, h){ return String.fromCharCode(parseInt(h, 16)); })
    .replace(/&#(\d+);/g,           function(_, n){ return String.fromCharCode(parseInt(n, 10)); });
}

function cleanHeadline(title) {
  if (!title) return '';
  var cleaned = title.replace(/\s+[-–—|]\s+[A-Za-z][A-Za-z0-9 &\.\-\']{1,59}$/, '').replace(/^[A-Za-z][A-Za-z0-9 ]{2,30}:\s+/, '').trim();
  return cleaned.length >= 5 ? cleaned : title.trim();
}

function extractItemImage(block) {
  var m = block.match(/<media:content[^>]+url=["']([^"'\s]+)["'][^>]*>/i);
  if (m && /\.(jpg|jpeg|png|webp|gif)/i.test(m[1])) return m[1];

  m = block.match(/<media:thumbnail[^>]+url=["']([^"'\s]+)["']/i);
  if (m) return m[1];

  m = block.match(/<enclosure[^>]+type=["']image\/[^"']+["'][^>]*url=["']([^"'\s]+)["']/i)
   || block.match(/<enclosure[^>]+url=["']([^"'\s]+)["'][^>]*type=["']image\/[^"']+["']/i);
  if (m) return m[1];

  var rawContent = extractTagValue(block, 'content:encoded') || extractTagValue(block, 'content') || extractTagValue(block, 'description');
  var decoded = decodeEntities(rawContent);
  m = decoded.match(/<img[^>]+src=["']([^"'\s]+)["']/i);
  if (m && /^https?:\/\//i.test(m[1])) return m[1];

  return null;
}

function parseRSS(xml) {
  if (!xml) return [];
  var items = [];
  var blockRe = /<item[\s>]([\s\S]*?)<\/item>/gi;
  var m; var found = false;
  while ((m = blockRe.exec(xml)) !== null) { found = true; processBlock(m[1], items); }
  if (!found) {
    var entryRe = /<entry[\s>]([\s\S]*?)<\/entry>/gi;
    while ((m = entryRe.exec(xml)) !== null) { processBlock(m[1], items); }
  }
  return items;
}

function processBlock(block, items) {
  var rawTitle = decodeEntities(extractTagValue(block, 'title').replace(/<[^>]+>/g, ''));
  var title = cleanHeadline(rawTitle);
  if (!title || title.length < 5) return;

  var link = extractTagValue(block, 'link') || extractTagValue(block, 'guid');
  if (!link) {
    var am = block.match(/<link[^>]+href=["']([^"']+)["']/i);
    if (am) link = am[1];
  }

  var description = decodeEntities(
    extractTagValue(block, 'description') || extractTagValue(block, 'summary') || extractTagValue(block, 'content')
  ).replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().slice(0, 300);

  var pubDate = extractTagValue(block, 'pubDate') || extractTagValue(block, 'published') || extractTagValue(block, 'updated');
  var publishedAt = pubDate ? new Date(pubDate).getTime() : Date.now();

  var imageUrl = extractItemImage(block);

  // Requirement: Skip items without images.
  if (!imageUrl) return;

  items.push({ title, link: link || '', description, publishedAt, imageUrl });
}

async function fetchFeed(feedObj) {
  try {
    var xml = await httpsGet(feedObj.url);
    var items = parseRSS(xml);
    return items;
  } catch (e) {
    console.warn(`Feed failed: ${feedObj.name} - ${e.message}`);
    return [];
  }
}

async function main() {
  let allItems = [];
  
  // Fetch all feeds in parallel
  const results = await Promise.all(FEEDS.map(f => fetchFeed(f)));
  
  for (let feedItems of results) {
    allItems.push(...feedItems);
  }

  // Deduplicate by title
  const seen = new Set();
  const uniqueItems = [];
  for (let item of allItems) {
    const key = item.title.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (!seen.has(key)) {
      seen.add(key);
      uniqueItems.push(item);
    }
  }

  // Sort by newest
  uniqueItems.sort((a, b) => b.publishedAt - a.publishedAt);
  
  // We only need top 15-20 for the UI
  const finalItems = uniqueItems.slice(0, 20);

  const outPath = path.join(__dirname, '..', 'data', 'breaking_news.json');
  fs.writeFileSync(outPath, JSON.stringify(finalItems, null, 2));
  console.log(`Saved ${finalItems.length} breaking news items to ${outPath}`);
}

main().catch(console.error);
