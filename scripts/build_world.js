/**
 * build_world.js — VilfinTV World News aggregator  v1
 * Lightweight RSS-only fetch — no AI processing, no API keys required.
 * Fetches from 60+ global news sources, groups by country/language.
 * Runs every 3 hours via GitHub Actions (.github/workflows/world.yml).
 * Output: data/world.json
 */

'use strict';

const https = require('https');
const http  = require('http');
const fs    = require('fs');
const path  = require('path');
const url   = require('url');

const REQUEST_TIMEOUT_MS = 18000;
const MAX_PER_REGION     = 10;
const EXPIRY_HOURS       = 3;  // world news refreshes more frequently

/* ═══════════════════════════════════════════════════
   WORLD REGIONS — sorted by continent/country
   Anchors (pos 0-1) are always fetched; remaining
   feeds are sampled randomly each run.
   accent = pill / highlight colour for that region
═══════════════════════════════════════════════════ */
const WORLD_REGIONS = [
  // ── US & Americas ─────────────────────────────────────────────────────────
  {
    id: 'us-en', flag: '🇺🇸', name: 'US & Americas', language: 'English', accent: '#3b82f6',
    feeds: [
      { url: 'https://www.cnbc.com/id/100003114/device/rss/rss.html',             name: 'CNBC' },
      { url: 'https://finance.yahoo.com/news/rssindex',                            name: 'Yahoo Finance' },
      { url: 'https://feeds.content.dowjones.io/public/rss/mw_topstories',        name: 'MarketWatch' },
      { url: 'https://www.axios.com/feeds/feed.rss',                              name: 'Axios' },
      { url: 'https://feeds.foxbusiness.com/foxbusiness/latest',                  name: 'Fox Business' },
      { url: 'https://feeds.reuters.com/reuters/topNews',                         name: 'Reuters' },
      { url: 'https://feeds.reuters.com/reuters/businessNews',                    name: 'Reuters Business' },
      { url: 'https://en.mercopress.com/rss.xml',                                 name: 'MercoPress' },
    ]
  },
  // ── Canada ─────────────────────────────────────────────────────────────────
  {
    id: 'canada', flag: '🇨🇦', name: 'Canada', language: 'English', accent: '#dc2626',
    feeds: [
      { url: 'https://rss.cbc.ca/lineup/topstories.xml',                          name: 'CBC News' },
      { url: 'https://globalnews.ca/feed/',                                        name: 'Global News' },
      { url: 'https://www.cbc.ca/cmlink/rss-business',                            name: 'CBC Business' },
      { url: 'https://www.ctvnews.ca/rss/ctvnews-ca-top-stories-public-rss-1.822009', name: 'CTV News' },
    ]
  },
  // ── Brazil ─────────────────────────────────────────────────────────────────
  {
    id: 'brazil', flag: '🇧🇷', name: 'Brazil', language: 'Português', accent: '#16a34a',
    feeds: [
      { url: 'https://g1.globo.com/rss/g1/',                                      name: 'G1 News' },
      { url: 'https://oglobo.globo.com/rss.xml',                                  name: 'O Globo' },
    ]
  },
  // ── Argentina ──────────────────────────────────────────────────────────────
  {
    id: 'argentina', flag: '🇦🇷', name: 'Argentina', language: 'Español', accent: '#2563eb',
    feeds: [
      { url: 'https://www.clarin.com/rss/lo-ultimo/',                             name: 'Clarín' },
      { url: 'https://www.lanacion.com.ar/arcio/rss/',                            name: 'La Nación' },
    ]
  },
  // ── Mexico ─────────────────────────────────────────────────────────────────
  {
    id: 'mexico', flag: '🇲🇽', name: 'Mexico', language: 'Español', accent: '#16a34a',
    feeds: [
      { url: 'https://news.google.com/rss/headlines/section/geo/Mexico?hl=es&gl=MX&ceid=MX:es', name: 'Google News MX' },
      { url: 'https://www.excelsior.com.mx/rss',                                  name: 'Excélsior' },
      { url: 'https://news.google.com/rss/search?q=mexico+noticias&hl=es&gl=MX&ceid=MX:es', name: 'Google Noticias MX' },
      { url: 'https://www.proceso.com.mx/rss',                                    name: 'Proceso MX' },
    ]
  },
  // ── United Kingdom ─────────────────────────────────────────────────────────
  {
    id: 'uk', flag: '🇬🇧', name: 'United Kingdom', language: 'English', accent: '#1d4ed8',
    feeds: [
      { url: 'https://feeds.bbci.co.uk/news/rss.xml',                            name: 'BBC News' },
      { url: 'https://feeds.skynews.com/feeds/rss/home.xml',                     name: 'Sky News UK' },
      { url: 'https://feeds.bbci.co.uk/news/business/rss.xml',                   name: 'BBC Business' },
    ]
  },
  // ── France ─────────────────────────────────────────────────────────────────
  {
    id: 'france', flag: '🇫🇷', name: 'France', language: 'Français', accent: '#1e40af',
    feeds: [
      { url: 'https://www.france24.com/en/rss',                                   name: 'France24' },
      { url: 'https://www.lemonde.fr/rss/une.xml',                                name: 'Le Monde' },
      { url: 'https://www.rfi.fr/fr/rss',                                         name: 'RFI' },
    ]
  },
  // ── Switzerland ────────────────────────────────────────────────────────────
  {
    id: 'switzerland', flag: '🇨🇭', name: 'Switzerland', language: 'Deutsch / Français', accent: '#dc2626',
    feeds: [
      { url: 'https://www.srf.ch/news/bnf/rss/1890',                              name: 'SRF News' },
      { url: 'https://www.rts.ch/rss/news.xml',                                   name: 'RTS News' },
    ]
  },
  // ── Europe / Middle East ───────────────────────────────────────────────────
  {
    id: 'europe-me', flag: '🌍', name: 'Europe & Middle East', language: 'English', accent: '#7c3aed',
    feeds: [
      { url: 'https://www.euronews.com/rss?format=mrss&level=theme&name=news',    name: 'Euronews' },
      { url: 'https://www.aljazeera.com/xml/rss/all.xml',                         name: 'Al Jazeera' },
      { url: 'https://www.euronews.com/business/rss',                             name: 'Euronews Business' },
      { url: 'https://www.khaleejtimes.com/feed',                                 name: 'Khaleej Times' },
    ]
  },
  // ── Russia ─────────────────────────────────────────────────────────────────
  {
    id: 'russia', flag: '🇷🇺', name: 'Russia', language: 'Русский', accent: '#dc2626',
    feeds: [
      { url: 'https://tass.com/rss/v2.xml',                                       name: 'TASS' },
      { url: 'https://news.google.com/rss/headlines/section/geo/Russia?hl=ru&gl=RU&ceid=RU:ru', name: 'Google News RU' },
    ]
  },
  // ── India (English) ────────────────────────────────────────────────────────
  {
    id: 'india-en', flag: '🇮🇳', name: 'India', language: 'English', accent: '#f97316',
    feeds: [
      { url: 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms', name: 'ET Markets' },
      { url: 'https://www.moneycontrol.com/rss/MCtopnews.xml',                   name: 'Moneycontrol' },
      { url: 'https://www.thehindu.com/feeder/default.rss',                      name: 'The Hindu' },
      { url: 'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',  name: 'Hindustan Times' },
      { url: 'https://www.livemint.com/rss/markets',                             name: 'Mint Markets' },
      { url: 'https://www.ndtv.com/rss/top-stories',                             name: 'NDTV Top' },
      { url: 'https://www.aninews.in/rss/',                                      name: 'ANI News' },
      { url: 'https://www.onmanorama.com/news/kerala.rssxml',                    name: 'OnManorama' },
    ]
  },
  // ── India (Hindi) ──────────────────────────────────────────────────────────
  {
    id: 'india-hi', flag: '🇮🇳', name: 'India', language: 'हिंदी', accent: '#ea580c',
    feeds: [
      { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=hi&gl=IN&ceid=IN:hi', name: 'Google News हिंदी' },
      { url: 'https://www.indiatvnews.com/rssfeed.xml',                          name: 'India TV' },
      { url: 'https://www.ndtv.com/rss/india',                                   name: 'NDTV India' },
    ]
  },
  // ── India (Malayalam) ──────────────────────────────────────────────────────
  {
    id: 'india-ml', flag: '🇮🇳', name: 'India', language: 'Malayalam', accent: '#8b5cf6',
    feeds: [
      { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=ml&gl=IN&ceid=IN:ml', name: 'Google News' },
      { url: 'https://www.mathrubhumi.com/rss/news.xml',                         name: 'Mathrubhumi' },
      { url: 'https://www.manoramaonline.com/news/kerala.rssxml',                name: 'Manorama' },
      { url: 'https://www.deepika.com/rss.xml',                                  name: 'Deepika' },
      { url: 'https://www.marunadanmalayali.com/rss.xml',                        name: 'Marunadan' },
    ]
  },
  // ── India (Tamil) ──────────────────────────────────────────────────────────
  {
    id: 'india-ta', flag: '🇮🇳', name: 'India', language: 'Tamil', accent: '#10b981',
    feeds: [
      { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=ta&gl=IN&ceid=IN:ta', name: 'Google News Tamil' },
      { url: 'https://www.dailythanthi.com/rss/home/rss.xml',                    name: 'Daily Thanthi' },
      { url: 'https://www.dinamalar.com/rss_main_list.asp',                      name: 'Dinamalar' },
    ]
  },
  // ── India (Kannada) ────────────────────────────────────────────────────────
  {
    id: 'india-kn', flag: '🇮🇳', name: 'India', language: 'Kannada', accent: '#d97706',
    feeds: [
      { url: 'https://www.prajavani.net/feed',                                    name: 'Prajavani' },
      { url: 'https://vijayakarnataka.com/feed/',                                 name: 'Vijaya Karnataka' },
      { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=kn&gl=IN&ceid=IN:kn', name: 'Google News Kannada' },
    ]
  },
  // ── India (Telugu) ─────────────────────────────────────────────────────────
  {
    id: 'india-te', flag: '🇮🇳', name: 'India', language: 'Telugu', accent: '#ef4444',
    feeds: [
      { url: 'https://www.sakshi.com/rss.xml',                                    name: 'Sakshi' },
      { url: 'https://www.eenadu.net/rss.xml',                                    name: 'Eenadu' },
      { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=te&gl=IN&ceid=IN:te', name: 'Google News Telugu' },
    ]
  },
  // ── India (Marathi) ────────────────────────────────────────────────────────
  {
    id: 'india-mr', flag: '🇮🇳', name: 'India', language: 'Marathi', accent: '#6366f1',
    feeds: [
      { url: 'https://maharashtratimes.com/rss.cms',                              name: 'Maharashtra Times' },
      { url: 'https://www.loksatta.com/rss/top-stories.rss',                     name: 'Loksatta' },
      { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=mr&gl=IN&ceid=IN:mr', name: 'Google News Marathi' },
    ]
  },
  // ── India (Bengali) ────────────────────────────────────────────────────────
  {
    id: 'india-bn', flag: '🇮🇳', name: 'India', language: 'Bengali', accent: '#14b8a6',
    feeds: [
      { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=bn&gl=IN&ceid=IN:bn', name: 'Google News Bengali' },
      { url: 'https://www.abpananda.in/feed/',                                    name: 'ABP Ananda' },
    ]
  },
  // ── India (Gujarati) ───────────────────────────────────────────────────────
  {
    id: 'india-gu', flag: '🇮🇳', name: 'India', language: 'Gujarati', accent: '#f59e0b',
    feeds: [
      { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=gu&gl=IN&ceid=IN:gu', name: 'Google News Gujarati' },
      { url: 'https://www.divyabhaskar.co.in/rss/1.rss',                         name: 'Divya Bhaskar' },
    ]
  },
  // ── Japan ──────────────────────────────────────────────────────────────────
  {
    id: 'japan', flag: '🇯🇵', name: 'Japan', language: 'English / 日本語', accent: '#ef4444',
    feeds: [
      { url: 'https://www3.nhk.or.jp/rss/news/cat0.xml',                         name: 'NHK World' },
      { url: 'https://www.japantimes.co.jp/feed/topstories',                     name: 'Japan Times' },
      { url: 'https://news.google.com/rss/headlines/section/geo/Japan?hl=ja&gl=JP&ceid=JP:ja', name: 'Google News Japan' },
    ]
  },
  // ── South Korea ────────────────────────────────────────────────────────────
  {
    id: 'korea', flag: '🇰🇷', name: 'South Korea', language: 'English / 한국어', accent: '#1d4ed8',
    feeds: [
      { url: 'https://www.koreatimes.co.kr/www/rss/rss_main.xml',                name: 'Korea Times' },
      { url: 'https://news.google.com/rss/headlines/section/geo/SouthKorea?hl=ko&gl=KR&ceid=KR:ko', name: 'Google News Korea' },
    ]
  },
  // ── China ──────────────────────────────────────────────────────────────────
  {
    id: 'china', flag: '🇨🇳', name: 'China', language: 'English / 中文', accent: '#dc2626',
    feeds: [
      { url: 'https://www.cgtn.com/subscribe/rss/section/business.xml',          name: 'CGTN Business' },
      { url: 'https://www.chinadaily.com.cn/rss/china_rss.xml',                  name: 'China Daily' },
      { url: 'https://news.google.com/rss/headlines/section/geo/China?hl=zh-CN&gl=CN&ceid=CN:zh-Hans', name: 'Google News China' },
    ]
  },
  // ── Taiwan ─────────────────────────────────────────────────────────────────
  {
    id: 'taiwan', flag: '🇹🇼', name: 'Taiwan', language: 'English / 中文', accent: '#1d4ed8',
    feeds: [
      { url: 'https://www.cna.com.tw/rss/aall.xml',                              name: 'CNA Taiwan' },
      { url: 'https://news.google.com/rss/headlines/section/geo/Taiwan?hl=zh-TW&gl=TW&ceid=TW:zh-Hant', name: 'Google News TW' },
    ]
  },
  // ── Thailand ───────────────────────────────────────────────────────────────
  {
    id: 'thailand', flag: '🇹🇭', name: 'Thailand', language: 'English / ไทย', accent: '#dc143c',
    feeds: [
      { url: 'https://www.bangkokpost.com/rss/data/topstories.xml',              name: 'Bangkok Post' },
      { url: 'https://news.google.com/rss/headlines/section/geo/Thailand?hl=th&gl=TH&ceid=TH:th', name: 'Google News Thai' },
      { url: 'https://www.thaipbsworld.com/feed/',                               name: 'Thai PBS World' },
    ]
  },
  // ── Asia Pacific ───────────────────────────────────────────────────────────
  {
    id: 'asia-pac', flag: '🌏', name: 'Asia Pacific', language: 'English', accent: '#06b6d4',
    feeds: [
      { url: 'https://vir.com.vn/rss/home.rss',                                  name: 'VIR Vietnam' },
      { url: 'https://news.google.com/rss/headlines/section/geo/SoutheastAsia?hl=en&gl=US&ceid=US:en', name: 'Google SEA' },
      { url: 'https://www.straitstimes.com/RSS/Breaking-News.xml',               name: 'Straits Times SG' },
    ]
  },
  // ── Australia & NZ ─────────────────────────────────────────────────────────
  {
    id: 'aus-nz', flag: '🇦🇺', name: 'Australia & NZ', language: 'English', accent: '#059669',
    feeds: [
      { url: 'https://www.abc.net.au/news/feed/51120/rss.xml',                   name: 'ABC News AU' },
      { url: 'https://www.skynews.com.au/rss.xml',                               name: 'Sky News AU' },
      { url: 'https://www.rnz.co.nz/rss/news.xml',                              name: 'RNZ NZ' },
      { url: 'https://www.tvnz.co.nz/content/dam/tvnz/rss/news.rss',            name: 'TVNZ' },
    ]
  },
  // ── Bangladesh ─────────────────────────────────────────────────────────────
  {
    id: 'bangladesh', flag: '🇧🇩', name: 'Bangladesh', language: 'English / বাংলা', accent: '#16a34a',
    feeds: [
      { url: 'https://www.dhakatribune.com/feed',                                 name: 'Dhaka Tribune' },
      { url: 'https://www.thedailystar.net/frontpage/rss.xml',                   name: 'Daily Star BD' },
      { url: 'https://bangla.bdnews24.com/feed/',                                name: 'bdnews24 বাংলা' },
    ]
  },
  // ── Nepal ──────────────────────────────────────────────────────────────────
  {
    id: 'nepal', flag: '🇳🇵', name: 'Nepal', language: 'English / नेपाली', accent: '#dc2626',
    feeds: [
      { url: 'https://english.onlinekhabar.com/feed',                            name: 'Online Khabar' },
      { url: 'https://www.nepalnews.com/rss',                                    name: 'Nepal News' },
      { url: 'https://ekantipur.com/rss',                                        name: 'eKantipur' },
    ]
  },
  // ── UAE ────────────────────────────────────────────────────────────────────
  {
    id: 'uae', flag: '🇦🇪', name: 'UAE', language: 'English', accent: '#b45309',
    feeds: [
      { url: 'https://www.khaleejtimes.com/feed',                                 name: 'Khaleej Times' },
      { url: 'https://news.google.com/rss/headlines/section/geo/UAE?hl=en&gl=AE&ceid=AE:en', name: 'Google News UAE' },
    ]
  },
  // ── South Africa ───────────────────────────────────────────────────────────
  {
    id: 'south-africa', flag: '🇿🇦', name: 'South Africa', language: 'English', accent: '#16a34a',
    feeds: [
      { url: 'https://feeds.news24.com/articles/news24/TopStories/rss',          name: 'News24 SA' },
      { url: 'https://news.google.com/rss/headlines/section/geo/SouthAfrica?hl=en&gl=ZA&ceid=ZA:en', name: 'Google News ZA' },
    ]
  },
  // ── Nigeria ────────────────────────────────────────────────────────────────
  {
    id: 'nigeria', flag: '🇳🇬', name: 'Nigeria', language: 'English', accent: '#16a34a',
    feeds: [
      { url: 'https://punchng.com/feed/',                                         name: 'Punch Nigeria' },
      { url: 'https://dailypost.ng/feed/',                                        name: 'Daily Post NG' },
      { url: 'https://www.vanguardngr.com/feed/',                                name: 'Vanguard NG' },
      { url: 'https://saharareporters.com/rss.xml',                              name: 'Sahara Reporters' },
    ]
  },
];

/* ═══════════════════════════════════════════════════
   HTTP GET (mirrors build_news.js approach)
═══════════════════════════════════════════════════ */
function sleep(ms) { return new Promise(function(r){ setTimeout(r, ms); }); }

function httpsGet(rawUrl) {
  return new Promise(function(resolve, reject) {
    var parsedUrl = url.parse(rawUrl);
    var transport = parsedUrl.protocol === 'https:' ? https : http;
    var reqOptions = {
      hostname: parsedUrl.hostname,
      port:     parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
      path:     parsedUrl.path || '/',
      method:   'GET',
      headers: {
        'User-Agent':      'Mozilla/5.0 (compatible; VilfinWorldBot/1.0; +https://vilfintv.com/bot)',
        'Accept':          'application/rss+xml, application/xml, text/xml, */*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',
        'Cache-Control':   'no-cache',
        'Connection':      'close'
      }
    };

    var req = transport.request(reqOptions, function(res) {
      if ([301,302,303,307,308].includes(res.statusCode) && res.headers.location) {
        var hops = (reqOptions._redirects || 0) + 1;
        if (hops > 5) { reject(new Error('Too many redirects')); res.resume(); return; }
        res.resume();
        var loc = res.headers.location;
        if (loc.startsWith('//'))      loc = parsedUrl.protocol + loc;
        else if (loc.startsWith('/'))  loc = parsedUrl.protocol + '//' + parsedUrl.host + loc;
        else if (!/^https?:\/\//i.test(loc)) {
          var base = (parsedUrl.pathname || '/').replace(/[^/]*$/, '');
          loc = parsedUrl.protocol + '//' + parsedUrl.host + base + loc;
        }
        httpsGet(loc).then(resolve).catch(reject);
        return;
      }
      if (res.statusCode && res.statusCode >= 400) {
        res.resume(); reject(new Error('HTTP ' + res.statusCode)); return;
      }
      var chunks = [];
      res.on('data', function(c){ chunks.push(c); });
      res.on('end',  function(){ resolve(Buffer.concat(chunks).toString('utf8')); });
      res.on('error', reject);
    });
    req.setTimeout(REQUEST_TIMEOUT_MS, function(){ req.destroy(new Error('Timeout: ' + rawUrl)); });
    req.on('error', reject);
    req.end();
  });
}

/* ═══════════════════════════════════════════════════
   HEADLINE & TEASER CLEANERS
   Google News RSS aggregation appends "- Source Name"
   to every headline and embeds source names in
   descriptions. These helpers strip that noise.
═══════════════════════════════════════════════════ */

/**
 * Strip trailing " - Source Name" from Google News aggregated headlines.
 * Only removes the LAST attribution suffix so legitimate em-dashes inside
 * the headline are preserved.
 *   "India jails journalist - The Hindu"  →  "India jails journalist"
 *   "Budget 2026: key points – Economic Times"  →  "Budget 2026: key points"
 */
function cleanHeadline(title) {
  if (!title) return '';
  // Match the very last "[-–—] Source Name" where source name is ≤ 60 Latin chars
  var cleaned = title
    .replace(/\s+[-–—]\s+[A-Za-z][A-Za-z0-9 \.\-&\']{1,59}$/, '')
    .trim();
  return cleaned.length >= 5 ? cleaned : title.trim();
}

/**
 * Strip embedded source attributions from RSS description text.
 * Cuts the text at the first " - SourceName" pattern that looks like
 * a news outlet name (capitalized Latin word(s) with no meaningful content
 * following). Also collapses runs of whitespace.
 */
function cleanTeaser(desc) {
  if (!desc) return '';
  // Cut before "- Capitalized Source-Looking Words" embedded in the text
  var cut = desc.search(/\s[-–—]\s[A-Z][a-zA-Z\s\.]{2,50}(?=\s[-–—]|[A-Z][a-z]|\s*$)/);
  var result = (cut > 40) ? desc.slice(0, cut).trim() : desc;
  return result.replace(/\s{2,}/g, ' ').trim().slice(0, 280);
}

/* ═══════════════════════════════════════════════════
   RSS / ATOM PARSER
═══════════════════════════════════════════════════ */
function decodeEntities(str) {
  if (!str) return '';
  return str
    .replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"')
    .replace(/&#39;/g,"'").replace(/&nbsp;/g,' ')
    .replace(/&#(\d+);/g, function(_,n){ return String.fromCharCode(parseInt(n,10)); });
}

function extractTagValue(block, tag) {
  var cdRe = new RegExp('<' + tag + '[^>]*>\\s*<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>\\s*<\\/' + tag + '>', 'i');
  var plRe = new RegExp('<' + tag + '[^>]*>([\\s\\S]*?)<\\/' + tag + '>', 'i');
  var m = cdRe.exec(block) || plRe.exec(block);
  return m ? m[1].trim() : '';
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

function extractItemImage(block) {
  var m = block.match(/<media:content[^>]+url=["']([^"']+\.(jpg|jpeg|png|webp))[^"']*["']/i);
  if (m) return m[1];
  m = block.match(/<media:thumbnail[^>]+url=["']([^"']+\.(jpg|jpeg|png|webp))[^"']*["']/i);
  if (m) return m[1];
  m = block.match(/<enclosure[^>]+type=["']image\/[^"']*["'][^>]+url=["']([^"']+)["']/i)
    || block.match(/<enclosure[^>]+url=["']([^"']+\.(jpg|jpeg|png|webp))[^"']*["']/i);
  if (m) return m[1];
  m = block.match(/<img[^>]+src=["']([^"']+\.(jpg|jpeg|png|webp))[^"']*["']/i);
  if (m) return m[1];
  return null;
}

function processBlock(block, items) {
  var rawTitle = decodeEntities(extractTagValue(block, 'title').replace(/<[^>]+>/g, ''));
  // Strip "- Source Name" suffix added by Google News aggregation
  var title = cleanHeadline(rawTitle);
  if (!title || title.length < 5) return;

  var link = extractTagValue(block, 'link') || extractTagValue(block, 'guid');
  if (!link) {
    var am = block.match(/<link[^>]+href=["']([^"']+)["']/i);
    if (am) link = am[1];
  }

  // Decode entities FIRST, then strip HTML tags, then clean source attributions
  var rawDesc = extractTagValue(block, 'description') || extractTagValue(block, 'summary')
    || extractTagValue(block, 'media:description') || extractTagValue(block, 'content');
  var description = cleanTeaser(
    decodeEntities(rawDesc).replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim()
  );

  var pubDate = extractTagValue(block, 'pubDate') || extractTagValue(block, 'published')
    || extractTagValue(block, 'updated') || extractTagValue(block, 'dc:date');
  var publishedAt = null;
  if (pubDate) { try { publishedAt = new Date(pubDate).toISOString(); } catch(e){} }
  if (!publishedAt) publishedAt = new Date().toISOString();

  // Discard items that are more than 7 days old — prevents "1403d ago" artifacts
  // from RSS feeds with stale or wrong pubDate values
  var age = Date.now() - new Date(publishedAt).getTime();
  if (age > 7 * 24 * 60 * 60 * 1000) return;

  var imageUrl = extractItemImage(block);
  items.push({ title: title, link: link || '', description: description, publishedAt: publishedAt, imageUrl: imageUrl || null });
}

/* ═══════════════════════════════════════════════════
   FETCH FEED — with single retry
═══════════════════════════════════════════════════ */
async function fetchFeed(feedObj) {
  var feedUrl  = feedObj.url;
  var feedName = feedObj.name || feedUrl;
  try {
    var xml = await httpsGet(feedUrl);
    var items = parseRSS(xml);
    items.forEach(function(i){ i.sourceName = feedName; });
    console.log('  OK (' + items.length + ') ' + feedName);
    return items;
  } catch(e) {
    console.warn('  FAIL (1):', feedName, '-', e.message, '— retrying in 3s');
    await sleep(3000);
    try {
      var xml2 = await httpsGet(feedUrl);
      var items2 = parseRSS(xml2);
      items2.forEach(function(i){ i.sourceName = feedName; });
      console.log('  RETRY OK (' + items2.length + ') ' + feedName);
      return items2;
    } catch(e2) {
      console.warn('  FAIL (2):', feedName, '-', e2.message);
      return [];
    }
  }
}

/* ═══════════════════════════════════════════════════
   TITLE SIMILARITY — simple word overlap for dedup
═══════════════════════════════════════════════════ */
function wordSet(title) {
  return new Set(
    title.toLowerCase().replace(/[^a-z0-9ऀ-ॿഀ-ൿ؀-ۿ ]/g,' ')
      .split(/\s+/).filter(function(w){ return w.length > 3; })
  );
}

function isSimilar(a, b) {
  var wa = wordSet(a), wb = wordSet(b);
  var inter = 0;
  wa.forEach(function(w){ if (wb.has(w)) inter++; });
  var union = wa.size + wb.size - inter;
  return union > 0 && (inter / union) > 0.45;
}

/* ═══════════════════════════════════════════════════
   BUILD REGION
═══════════════════════════════════════════════════ */
async function buildRegion(region) {
  console.log('\n[Region]', region.flag, region.name, '(' + region.language + ')');
  var results = await Promise.allSettled(region.feeds.map(function(f){ return fetchFeed(f); }));

  var all = [];
  results.forEach(function(r){ if (r.status === 'fulfilled') all = all.concat(r.value); });

  // Sort by date, newest first
  all.sort(function(a,b){ return new Date(b.publishedAt) - new Date(a.publishedAt); });

  // Deduplicate within region
  var deduped = [];
  all.forEach(function(item) {
    if (!deduped.some(function(d){ return isSimilar(d.title, item.title); })) {
      deduped.push(item);
    }
  });

  var selected = deduped.slice(0, MAX_PER_REGION);
  console.log('  Selected', selected.length, 'of', deduped.length, 'deduped items');

  return selected.map(function(item) {
    var out = {
      headline:    item.title,
      teaser:      item.description || '',
      source:      item.sourceName || '',
      url:         item.link || '',
      publishedAt: item.publishedAt,
      expiresAt:   new Date(Date.now() + EXPIRY_HOURS * 3600000).toISOString()
    };
    if (item.imageUrl) out.image = item.imageUrl;
    return out;
  });
}

/* ═══════════════════════════════════════════════════
   MAIN
═══════════════════════════════════════════════════ */
async function main() {
  console.log('='.repeat(60));
  console.log('VilfinTV World News Builder v1');
  console.log('Started:', new Date().toISOString());
  console.log('Regions:', WORLD_REGIONS.length);
  console.log('='.repeat(60));

  var dataDir = path.join(__dirname, '..', 'data');
  var outPath = path.join(dataDir, 'world.json');

  var output = { generated: new Date().toISOString(), regions: [] };

  for (var i = 0; i < WORLD_REGIONS.length; i++) {
    var region = WORLD_REGIONS[i];
    try {
      var items = await buildRegion(region);
      if (items.length > 0) {
        output.regions.push({
          id:       region.id,
          flag:     region.flag,
          name:     region.name,
          language: region.language,
          accent:   region.accent,
          items:    items
        });
      } else {
        console.warn('  Skipping', region.id, '— no items fetched');
      }
    } catch(e) {
      console.error('Region', region.id, 'failed:', e.message);
    }
    // Small pause between regions to avoid hammering sources
    if (i < WORLD_REGIONS.length - 1) await sleep(400);
  }

  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(output, null, 2) + '\n', 'utf8');

  var totalItems = output.regions.reduce(function(s,r){ return s + r.items.length; }, 0);
  console.log('\n' + '='.repeat(60));
  console.log('Output:', outPath);
  console.log('Regions saved:', output.regions.length, '/', WORLD_REGIONS.length);
  console.log('Total headlines:', totalItems);
  console.log('Completed:', new Date().toISOString());
  console.log('='.repeat(60));
}

main().catch(function(e){ console.error('FATAL:', e); process.exit(1); });
