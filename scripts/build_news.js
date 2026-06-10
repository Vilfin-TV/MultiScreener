/**
 * build_news.js — VilfinTV News content generator  v3
 * Runs in GitHub Actions (Node 20). Zero npm dependencies.
 *
 * Pipeline per 6-hour cycle:
 *   1. Fetch RSS + YouTube channel feeds (multi-source)
 *   2. Deduplicate, filter, sort newest-first
 *   3. Groq (llama-3.1-8b-instant) → rewrite every headline (copyright-safe)
 *   4. Gemini 2.0 Flash → write 5-6 paragraph article, multi-source context
 *      └─ Groq llama-3.3-70b-versatile fallback → enhanced RSS multi-source fallback
 *   5. Groq (llama-3.1-8b-instant) → generate image prompt for top story
 *      └─ Pollinations.ai free image URL (no API key needed)
 *   6. Write data/news.json  (items expire after 48 h, new always first)
 *
 * GitHub Secrets required:
 *   GEMINI_API_KEY_2  → passed as GOOGLE_AI_API_KEY env var
 *   GROC_API          → passed as GROQ_API_KEY env var
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
const GROQ_API_KEY      = process.env.GROQ_API_KEY      || '';

// Groq model IDs
const GROQ_MODEL_FAST    = 'llama-3.1-8b-instant';   // headline rewrite, image prompts
const GROQ_MODEL_ARTICLE = 'llama-3.3-70b-versatile'; // article fallback (higher quality)

const BLOCKED_KEYWORDS = [
  'riot', 'genocide', 'lynching', 'hate speech', 'communal violence',
  'mob violence', 'explicit', 'graphic content', 'rape', 'slaughter',
  'massacre', 'pogrom', 'beheading', 'ethnic cleansing'
];

const MAX_ITEMS_PER_SECTION = 16;  // AI sections (trending/global/india) — each story costs an LLM call
const MAX_ITEMS_RSS_ONLY    = 40;  // RSS-only sections (stock/malayalam/ml_*) — no per-story AI cost
const REQUEST_TIMEOUT_MS    = 22000;
// First TWO entries per section are always fetched; rest are randomly sampled.
// 7 feeds → 2 anchors + 5 random from a pool of 30+ for trending = per-cycle variety
const FEEDS_PER_SECTION     = 7;

/* ═══════════════════════════════════════════════════
   SOURCE POOL
   Anchors (positions 0-1) are always included.
   Remaining entries are randomly sampled each run
   so stories rotate and readers get fresh variety.
   YouTube feeds use Atom format — parsed by parseRSS().
═══════════════════════════════════════════════════ */
const SOURCE_POOL = {

  // ── trending ─────────────────────────────────────────────────────────────────
  // Anchors (pos 0-1) always included. 5 random feeds sampled from the rest each run
  // so topics rotate: Politics, AI/Tech, Finance, Health, Entertainment, Energy, etc.
  trending: [
    // ── Anchors (always fetched) ─────────────────────────────────────────────
    { url: 'https://news.google.com/rss/headlines/section/topic/HEADLINES?hl=en-US&gl=US&ceid=US:en', name: 'Google Trending US' },
    { url: 'https://news.google.com/rss/headlines/section/topic/HEADLINES?hl=en-IN&gl=IN&ceid=IN:en', name: 'Google Trending India' },
    // ── Wire services ────────────────────────────────────────────────────────
    { url: 'https://feeds.bbci.co.uk/news/rss.xml',                    name: 'BBC News' },
    { url: 'https://apnews.com/rss',                                    name: 'AP News' },
    { url: 'https://www.aljazeera.com/xml/rss/all.xml',                 name: 'Al Jazeera' },
    { url: 'https://www.axios.com/feeds/feed.rss',                      name: 'Axios' },
    // ── Politics ─────────────────────────────────────────────────────────────
    { url: 'https://news.google.com/rss/headlines/section/topic/POLITICS?hl=en-US&gl=US&ceid=US:en', name: 'Google Politics US' },
    { url: 'https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en',   name: 'Google Politics India' },
    // ── AI & Technology ──────────────────────────────────────────────────────
    { url: 'https://techcrunch.com/feed/',                               name: 'TechCrunch' },
    { url: 'https://www.theverge.com/rss/index.xml',                    name: 'The Verge' },
    { url: 'https://feeds.arstechnica.com/arstechnica/index',           name: 'Ars Technica' },
    { url: 'https://www.wired.com/feed/rss',                            name: 'Wired' },
    { url: 'https://news.google.com/rss/search?q=artificial+intelligence+AI+ChatGPT+LLM&hl=en-US&gl=US&ceid=US:en', name: 'AI News' },
    { url: 'https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en', name: 'Google Tech US' },
    { url: 'https://news.google.com/rss/search?q=AI+machine+learning+OpenAI+Gemini+Claude&hl=en-US&gl=US&ceid=US:en', name: 'AI Models' },
    { url: 'https://news.google.com/rss/search?q=AI+technology+India+Japan+Asia+startup&hl=en-US&gl=US&ceid=US:en', name: 'AI Asia' },
    { url: 'https://news.google.com/rss/search?q=technology+innovation+gadget+semiconductor&hl=en-US&gl=US&ceid=US:en', name: 'Tech Innovation' },
    { url: 'https://www.technologyreview.com/feed/',                    name: 'MIT Tech Review' },
    { url: 'https://feeds.feedburner.com/venturebeat/SZYF',            name: 'VentureBeat AI' },
    // ── Finance: Stock, ETF, Mutual Fund, Forex, Gold, Tax ───────────────────
    { url: 'https://www.cnbc.com/id/100003114/device/rss/rss.html',     name: 'CNBC Top' },
    { url: 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en', name: 'Google Business US' },
    { url: 'https://news.google.com/rss/search?q=ETF+mutual+fund+stock+market+investing&hl=en-US&gl=US&ceid=US:en', name: 'ETF & Funds' },
    { url: 'https://news.google.com/rss/search?q=forex+currency+exchange+rate+dollar&hl=en-US&gl=US&ceid=US:en', name: 'Forex News' },
    { url: 'https://news.google.com/rss/search?q=gold+silver+price+commodities&hl=en-US&gl=US&ceid=US:en', name: 'Gold & Commodities' },
    { url: 'https://news.google.com/rss/search?q=tax+income+tax+GST+policy&hl=en-IN&gl=IN&ceid=IN:en', name: 'Tax News India' },
    { url: 'https://news.google.com/rss/search?q=mutual+fund+SIP+SEBI+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en', name: 'India Mutual Funds' },
    // ── Health ───────────────────────────────────────────────────────────────
    { url: 'https://news.google.com/rss/headlines/section/topic/HEALTH?hl=en-US&gl=US&ceid=US:en', name: 'Google Health' },
    { url: 'https://news.google.com/rss/search?q=health+medicine+cancer+nutrition+wellness&hl=en-US&gl=US&ceid=US:en', name: 'Health & Medicine' },
    // ── Entertainment, Movies, Food ───────────────────────────────────────────
    { url: 'https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=en-US&gl=US&ceid=US:en', name: 'Google Entertainment' },
    { url: 'https://news.google.com/rss/search?q=movies+new+releases+cinema+Hollywood+Bollywood&hl=en-US&gl=US&ceid=US:en', name: 'Movies & Cinema' },
    { url: 'https://news.google.com/rss/search?q=food+recipe+restaurant+cuisine+trends&hl=en-US&gl=US&ceid=US:en', name: 'Food Trends' },
    // ── Energy & Environment ──────────────────────────────────────────────────
    { url: 'https://oilprice.com/rss/main',                             name: 'OilPrice News' },
    { url: 'https://news.google.com/rss/search?q=energy+oil+solar+renewable+nuclear&hl=en-US&gl=US&ceid=US:en', name: 'Energy News' },
    // ── Science & Space ───────────────────────────────────────────────────────
    { url: 'https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-US&gl=US&ceid=US:en', name: 'Google Science' },
    { url: 'https://news.google.com/rss/search?q=space+NASA+SpaceX+rocket+launch+satellite&hl=en-US&gl=US&ceid=US:en', name: 'Space News' },
    { url: 'https://news.google.com/rss/search?q=ISRO+space+mission+India+Japan+ESA&hl=en-US&gl=US&ceid=US:en', name: 'ISRO & ESA Space' },
    { url: 'https://news.google.com/rss/search?q=science+discovery+physics+biology+research&hl=en-US&gl=US&ceid=US:en', name: 'Science Discovery' },
    { url: 'https://news.google.com/rss/search?q=climate+environment+biodiversity+research&hl=en-US&gl=US&ceid=US:en', name: 'Climate Science' },
    { url: 'https://www.nasa.gov/rss/dyn/breaking_news.rss',            name: 'NASA News' },
    { url: 'https://www.sciencedaily.com/rss/top/science.xml',         name: 'Science Daily' },
    // ── Google Trends ─────────────────────────────────────────────────────────
    { url: 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=US', name: 'Google Trends US' },
    { url: 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN', name: 'Google Trends India' },
    { url: 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=JP', name: 'Google Trends Japan' },
    { url: 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB', name: 'Google Trends UK' },
    // ── YouTube News Channels ─────────────────────────────────────────────────
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCNye-wNBqNL5ZzHSJj3l8Bg', name: 'Al Jazeera YT' },
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCVTyTA7-g9nopHeHbeuvpRA', name: 'CNN YT' },
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA', name: 'BBC News YT' },
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCknLrEdhRCp1aegoMqRaCZg', name: 'DW News YT' },
  ],

  // ── global ──────────────────────────────────────────────────────────────────
  global: [
    { url: 'https://news.google.com/rss/headlines/section/topic/WORLD?hl=en&gl=US&ceid=US:en', name: 'Google News World' },
    { url: 'https://feeds.bbci.co.uk/news/world/rss.xml',               name: 'BBC World' },
    { url: 'https://www.aljazeera.com/xml/rss/all.xml',                  name: 'Al Jazeera' },
    { url: 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',     name: 'NY Times World' },
    { url: 'https://www.theguardian.com/international/rss',              name: 'The Guardian' },
    { url: 'https://www.dw.com/rss/rss.xml',                             name: 'DW News' },
    { url: 'https://feeds.bbci.co.uk/news/business/rss.xml',             name: 'BBC Business' },
    { url: 'https://www.nhk.or.jp/rss/news/cat0.xml',                    name: 'NHK World' },
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCknLrEdhRCp1aegoMqRaCZg', name: 'DW News YT' },
  ],

  // ── india ───────────────────────────────────────────────────────────────────
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
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCZFMm1mMw0F81Z37aaEzTUA', name: 'NDTV YT' },
  ],

  // ── stock ───────────────────────────────────────────────────────────────────
  // Anchors (pos 0-1) always included. Rest randomly sampled for variety.
  stock: [
    // ── Anchors ─────────────────────────────────────────────────────────────
    { url: 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en', name: 'Google Finance India' },
    { url: 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en', name: 'Google Finance US' },
    // ── India Markets ────────────────────────────────────────────────────────
    { url: 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',       name: 'ET Markets' },
    { url: 'https://www.livemint.com/rss/markets',                                       name: 'Mint Markets' },
    { url: 'https://economictimes.indiatimes.com/markets/stocks/rss.cms',                name: 'ET Stocks' },
    { url: 'https://www.businessstandard.com/rss/markets-106.rss',                       name: 'Business Standard' },
    { url: 'https://www.moneycontrol.com/rss/MCtopnews.xml',                             name: 'Moneycontrol' },
    // ── Mutual Funds & ETFs (India) ──────────────────────────────────────────
    { url: 'https://news.google.com/rss/search?q=mutual+fund+SIP+SEBI+NAV+India&hl=en-IN&gl=IN&ceid=IN:en', name: 'India Mutual Funds' },
    { url: 'https://news.google.com/rss/search?q=AMFI+mutual+fund+NFO+SIP+returns&hl=en-IN&gl=IN&ceid=IN:en', name: 'AMFI Fund News' },
    { url: 'https://economictimes.indiatimes.com/mutual-funds/rssfeeds/1522278249.cms',  name: 'ET Mutual Funds' },
    { url: 'https://www.moneycontrol.com/rss/mutualfunds.xml',                           name: 'MC Mutual Funds' },
    // ── ETFs (US & Asia) ─────────────────────────────────────────────────────
    { url: 'https://news.google.com/rss/search?q=ETF+fund+flows+US+Asia+Europe+index&hl=en-US&gl=US&ceid=US:en', name: 'ETF Global' },
    { url: 'https://news.google.com/rss/search?q=ETF+Japan+Nikkei+Asia+Pacific+fund&hl=en-US&gl=US&ceid=US:en', name: 'ETF Asia' },
    // ── Bonds & Fixed Income ─────────────────────────────────────────────────
    { url: 'https://news.google.com/rss/search?q=government+bonds+yield+treasury+debt&hl=en-US&gl=US&ceid=US:en', name: 'US Bonds' },
    { url: 'https://news.google.com/rss/search?q=India+bonds+RBI+gilt+debt+market&hl=en-IN&gl=IN&ceid=IN:en',    name: 'India Bonds' },
    { url: 'https://news.google.com/rss/search?q=Japan+bonds+BOJ+JGB+yield+Asia&hl=en-US&gl=US&ceid=US:en',      name: 'Japan Bonds' },
    // ── Commodities ──────────────────────────────────────────────────────────
    { url: 'https://news.google.com/rss/search?q=gold+silver+crude+oil+commodity+price&hl=en-US&gl=US&ceid=US:en', name: 'Commodities Global' },
    { url: 'https://news.google.com/rss/search?q=MCX+India+commodity+gold+crude+copper&hl=en-IN&gl=IN&ceid=IN:en', name: 'MCX India' },
    { url: 'https://news.google.com/rss/search?q=commodity+futures+Asia+Europe+wheat+metal&hl=en-US&gl=US&ceid=US:en', name: 'Commodities Asia-EU' },
    { url: 'https://oilprice.com/rss/main',                                               name: 'OilPrice.com' },
    // ── Trending Stocks ───────────────────────────────────────────────────────
    { url: 'https://news.google.com/rss/search?q=trending+stocks+top+gainers+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en', name: 'NSE Trending Stocks' },
    { url: 'https://news.google.com/rss/search?q=stock+rally+breakout+52+week+high&hl=en-US&gl=US&ceid=US:en',   name: 'Stock Momentum US' },
    { url: 'https://news.google.com/rss/search?q=Nikkei+Japan+stock+market+Tokyo+rally&hl=en-US&gl=US&ceid=US:en', name: 'Japan Stocks' },
    // ── US & Global Finance ───────────────────────────────────────────────────
    { url: 'https://feeds.bbci.co.uk/news/business/rss.xml',                             name: 'BBC Business' },
    { url: 'https://finance.yahoo.com/news/rssindex',                                    name: 'Yahoo Finance' },
    { url: 'https://www.cnbc.com/id/100003114/device/rss/rss.html',                      name: 'CNBC Markets' },
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCIALMKvObZNtJ6AmdCLP7Lg', name: 'Bloomberg YT' },
  ],

  // ── malayalam ───────────────────────────────────────────────────────────────
  malayalam: [
    { url: 'https://news.google.com/rss/headlines/section/geo/India?hl=ml&gl=IN&ceid=IN:ml', name: 'Google News Malayalam' },
    { url: 'https://news.google.com/rss/search?q=kerala+news&hl=ml&gl=IN&ceid=IN:ml',        name: 'Google Kerala Search' },
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCbGkCBm7P6p3a7PGQRmMhsQ',   name: 'Asianet News YT' },
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCyhmnsZTNxF_lFr3lOcGgdQ',   name: 'Manorama News YT' },
    { url: 'https://www.mathrubhumi.com/rss/news.xml',                                        name: 'Mathrubhumi' },
    { url: 'https://www.asianetnews.com/rss',                                                 name: 'Asianet News' },
    { url: 'https://www.manoramaonline.com/news/kerala.rssxml',                               name: 'Manorama Online' },
  ],

  // ── Malayalam Edition sub-categories (RSS-only, Malayalam language) ─────────
  ml_trending: [
    { url: 'https://news.google.com/rss/headlines/section/geo/India/IN-KL?hl=ml&gl=IN&ceid=IN:ml', name: 'Google Kerala' },
    { url: 'https://news.google.com/rss/search?q=kerala+viral+trending&hl=ml&gl=IN&ceid=IN:ml',    name: 'Kerala Trending' },
    { url: 'https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN',                   name: 'Google Trends IN' },
    { url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCbGkCBm7P6p3a7PGQRmMhsQ',        name: 'Asianet YT' },
  ],
  ml_stock: [
    { url: 'https://news.google.com/rss/search?q=site:dhanamonline.com&hl=ml&gl=IN&ceid=IN:ml',                 name: 'Dhanam Online' },
    { url: 'https://news.google.com/rss/search?q=site:malayalam.economictimes.com&hl=ml&gl=IN&ceid=IN:ml',      name: 'ET Malayalam' },
    { url: 'https://news.google.com/rss/search?q=site:manoramaonline.com/business&hl=ml&gl=IN&ceid=IN:ml',      name: 'Manorama Business' },
    { url: 'https://news.google.com/rss/search?q=site:mathrubhumi.com/money&hl=ml&gl=IN&ceid=IN:ml',            name: 'Mathrubhumi Money' },
    { url: 'https://news.google.com/rss/search?q=ഓഹരി+വിപണി+സെൻസെക്സ്+നിഫ്റ്റി&hl=ml&gl=IN&ceid=IN:ml',         name: 'Stock Market ML' },
    { url: 'https://news.google.com/rss/search?q=ബിസിനസ്+നിക്ഷേപം+സ്വർണവില+kerala&hl=ml&gl=IN&ceid=IN:ml',      name: 'Business & Gold ML' },
  ],
  ml_movies: [
    { url: 'https://news.google.com/rss/search?q=malayalam+cinema+film+movie&hl=ml&gl=IN&ceid=IN:ml',       name: 'Malayalam Cinema' },
    { url: 'https://news.google.com/rss/search?q=mollywood+new+movie+release+OTT&hl=ml&gl=IN&ceid=IN:ml',  name: 'Mollywood OTT' },
    { url: 'https://news.google.com/rss/search?q=കേരള+സിനിമ+ചലച്ചിത്രം&hl=ml&gl=IN&ceid=IN:ml',            name: 'Kerala Cinema ML' },
  ],
  ml_music: [
    { url: 'https://news.google.com/rss/search?q=malayalam+music+song+album+singer&hl=ml&gl=IN&ceid=IN:ml', name: 'Malayalam Music' },
    { url: 'https://news.google.com/rss/search?q=kerala+music+album+concert&hl=ml&gl=IN&ceid=IN:ml',        name: 'Kerala Music' },
    { url: 'https://news.google.com/rss/search?q=malayalam+song+new+release&hl=ml&gl=IN&ceid=IN:ml',        name: 'New Songs' },
  ],
  ml_local: [
    { url: 'https://news.google.com/rss/search?q=kerala+district+local+news&hl=ml&gl=IN&ceid=IN:ml',   name: 'Kerala Local' },
    { url: 'https://news.google.com/rss/search?q=thiruvananthapuram+kochi+kozhikode&hl=ml&gl=IN&ceid=IN:ml', name: 'City News' },
    { url: 'https://news.google.com/rss/search?q=kerala+government+panchayath+local+body&hl=ml&gl=IN&ceid=IN:ml', name: 'Local Bodies' },
  ],
  ml_science: [
    { url: 'https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ml&gl=IN&ceid=IN:ml',              name: 'Google Science ML' },
    { url: 'https://news.google.com/rss/search?q=science+research+discovery+ശാസ്ത്രം&hl=ml&gl=IN&ceid=IN:ml', name: 'Science Malayalam' },
    { url: 'https://news.google.com/rss/search?q=kerala+science+technology+innovation&hl=ml&gl=IN&ceid=IN:ml', name: 'Kerala Science' },
  ],
  ml_space: [
    { url: 'https://news.google.com/rss/search?q=ISRO+space+mission+rocket+satellite&hl=ml&gl=IN&ceid=IN:ml',  name: 'ISRO Space' },
    { url: 'https://news.google.com/rss/search?q=NASA+space+planet+ബഹിരാകാശം+chandrayaan&hl=ml&gl=IN&ceid=IN:ml', name: 'Space Malayalam' },
  ],
  ml_sports: [
    { url: 'https://news.google.com/rss/headlines/section/topic/SPORTS?hl=ml&gl=IN&ceid=IN:ml',                 name: 'Google Sports ML' },
    { url: 'https://news.google.com/rss/search?q=cricket+football+sports+kerala+IPL&hl=ml&gl=IN&ceid=IN:ml',   name: 'Kerala Sports' },
    { url: 'https://news.google.com/rss/search?q=കേരള+കായികം+ക്രിക്കറ്റ്+ഫുട്ബോൾ&hl=ml&gl=IN&ceid=IN:ml',     name: 'Sports ML' },
  ],
  ml_health: [
    { url: 'https://news.google.com/rss/headlines/section/topic/HEALTH?hl=ml&gl=IN&ceid=IN:ml',                 name: 'Google Health ML' },
    { url: 'https://news.google.com/rss/search?q=health+ayurveda+wellness+lifestyle+kerala&hl=ml&gl=IN&ceid=IN:ml', name: 'Kerala Health' },
    { url: 'https://news.google.com/rss/search?q=ആരോഗ്യം+ആയുർവേദം+kerala+hospital&hl=ml&gl=IN&ceid=IN:ml',    name: 'Health Malayalam' },
  ],
  ml_food: [
    { url: 'https://news.google.com/rss/search?q=food+agriculture+farming+kerala+rice&hl=ml&gl=IN&ceid=IN:ml',  name: 'Kerala Food & Farm' },
    { url: 'https://news.google.com/rss/search?q=കൃഷി+ഭക്ഷണം+agriculture+food+recipe&hl=ml&gl=IN&ceid=IN:ml', name: 'Food Malayalam' },
    { url: 'https://news.google.com/rss/search?q=kerala+vegetable+fish+price+market&hl=ml&gl=IN&ceid=IN:ml',   name: 'Market Prices' },
  ],
  ml_realestate: [
    { url: 'https://news.google.com/rss/search?q=real+estate+property+kerala+home+flat&hl=ml&gl=IN&ceid=IN:ml',      name: 'Kerala Property' },
    { url: 'https://news.google.com/rss/search?q=kerala+house+construction+apartment+land&hl=ml&gl=IN&ceid=IN:ml',   name: 'Kerala Real Estate' },
    { url: 'https://news.google.com/rss/search?q=interior+home+design+kerala&hl=ml&gl=IN&ceid=IN:ml',                name: 'Home Design' },
  ],
  ml_career: [
    { url: 'https://news.google.com/rss/search?q=job+employment+career+vacancy+Kerala+PSC&hl=ml&gl=IN&ceid=IN:ml',   name: 'Kerala Jobs' },
    { url: 'https://news.google.com/rss/search?q=government+job+recruitment+notification+kerala&hl=ml&gl=IN&ceid=IN:ml', name: 'Govt Recruitment' },
    { url: 'https://news.google.com/rss/search?q=തൊഴിൽ+വേതനം+recruitment+PSC+job&hl=ml&gl=IN&ceid=IN:ml',           name: 'Jobs Malayalam' },
  ],
  ml_tech: [
    { url: 'https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ml&gl=IN&ceid=IN:ml',                  name: 'Google Tech ML' },
    { url: 'https://news.google.com/rss/search?q=technology+smartphone+gadget+kerala+IT&hl=ml&gl=IN&ceid=IN:ml',    name: 'Kerala Tech' },
    { url: 'https://news.google.com/rss/search?q=mobile+phone+computer+app+tech+news+india&hl=ml&gl=IN&ceid=IN:ml', name: 'Tech News' },
  ],
};

const SECTION_META = {
  trending:     { image: 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200&q=80', label: '🔥 Trending Now',      accent: '#ef4444' },
  global:       { image: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&q=80', label: '🌍 Global News',       accent: '#3b82f6' },
  india:        { image: 'https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=1200&q=80', label: '🇮🇳 India News',       accent: '#f97316' },
  stock:        { image: 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1200&q=80', label: '📈 Stock News',        accent: '#10b981' },
  malayalam:    { image: 'https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=1200&q=80', label: '🎭 Malayalam News',    accent: '#8b5cf6' },
  // ── Malayalam Edition sub-categories ──────────────────────────────────────
  ml_trending:  { image: 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200&q=80', label: 'Top Trending Kerala', accent: '#ef4444' },
  ml_stock:     { image: 'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=1200&q=80', label: 'Stocks & Business',   accent: '#059669' },
  ml_movies:    { image: 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1200&q=80', label: 'Movie News',          accent: '#f59e0b' },
  ml_music:     { image: 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=1200&q=80', label: 'Music News',          accent: '#ec4899' },
  ml_local:     { image: 'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1200&q=80', label: 'Local News',          accent: '#06b6d4' },
  ml_science:   { image: 'https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=1200&q=80', label: 'Science News',        accent: '#6366f1' },
  ml_space:     { image: 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1200&q=80', label: 'Space News',          accent: '#1e3a8a' },
  ml_sports:    { image: 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=1200&q=80', label: 'Sports News',         accent: '#16a34a' },
  ml_health:    { image: 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=1200&q=80', label: 'Health & Lifestyle',  accent: '#0ea5e9' },
  ml_food:      { image: 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=1200&q=80', label: 'Food & Agriculture',  accent: '#84cc16' },
  ml_realestate:{ image: 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=1200&q=80', label: 'Home & Real Estate',  accent: '#d97706' },
  ml_career:    { image: 'https://images.unsplash.com/photo-1521791136064-7986c2920216?w=1200&q=80', label: 'Career & Jobs',      accent: '#7c3aed' },
  ml_tech:      { image: 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&q=80', label: 'Technology News',    accent: '#2563eb' },
};

/* ═══════════════════════════════════════════════════
   UTILITIES
═══════════════════════════════════════════════════ */
function sleep(ms) { return new Promise(function(r){ setTimeout(r, ms); }); }

/** Deterministic integer hash — used as stable image seed per headline */
function hashCode(str) {
  var h = 5381;
  for (var i = 0; i < str.length; i++) {
    h = ((h << 5) + h) ^ str.charCodeAt(i);
    h = h >>> 0; // keep unsigned 32-bit
  }
  return h % 999983; // keep under 1M for Pollinations seed
}

// Fisher-Yates shuffle
function shuffle(arr) {
  var a = arr.slice();
  for (var i = a.length - 1; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var t = a[i]; a[i] = a[j]; a[j] = t;
  }
  return a;
}

/* ═══════════════════════════════════════════════════
   HTTP HELPER — GET + POST, follows redirects,
   resolves relative/protocol-relative Location URLs
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
        'User-Agent':      'Mozilla/5.0 (compatible; VilfinNewsBot/3.0; +https://vilfintv.com/bot)',
        'Accept':          'application/rss+xml, application/xml, text/xml, application/atom+xml, */*;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',
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
        if (loc.startsWith('//')) {
          loc = parsedUrl.protocol + loc;
        } else if (loc.startsWith('/')) {
          loc = parsedUrl.protocol + '//' + parsedUrl.host + loc;
        } else if (!/^https?:\/\//i.test(loc)) {
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

/* ═══════════════════════════════════════════════════
   RSS FETCHER — with one retry on failure
═══════════════════════════════════════════════════ */
async function fetchRSS(feedObj) {
  var feedUrl  = feedObj.url  || feedObj;
  var feedName = feedObj.name || (feedUrl.replace(/^https?:\/\//, '').split('/')[0]);
  try {
    console.log('  Fetching:', feedName);
    var xml = await httpsGet(feedUrl);
    var items = parseRSS(xml);
    if (!items.length && xml && xml.length > 200) {
      console.warn('  Feed returned 0 parsed items:', feedName, '(' + xml.length + ' chars received)');
    }
    items.forEach(function(item){ item.sourceName = feedName; });
    return items;
  } catch (e) {
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
   XML PARSER — handles both RSS <item> and Atom <entry>
═══════════════════════════════════════════════════ */
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
    .replace(/&nbsp;/g, ' ').replace(/&hellip;/g, '…').replace(/&mdash;/g, '—').replace(/&ndash;/g, '–')
    .replace(/&#x([0-9a-fA-F]+);/g, function(_, h){ return String.fromCharCode(parseInt(h, 16)); })
    .replace(/&#(\d+);/g,           function(_, n){ return String.fromCharCode(parseInt(n, 10)); });
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

/**
 * Strip trailing " - Source Name" or "| Source" appended by aggregators.
 * Also strips a leading "Source: " prefix pattern.
 */
function cleanHeadline(title) {
  if (!title) return '';
  var cleaned = title
    // Remove trailing " - Source Name" / " – Source" / " | Source"  (Google News style)
    .replace(/\s+[-–—|]\s+[A-Za-z][A-Za-z0-9 &\.\-\']{1,59}$/, '')
    // Remove leading "Source Name: " prefix (some feed generators)
    .replace(/^[A-Za-z][A-Za-z0-9 ]{2,30}:\s+/, '')
    .trim();
  return cleaned.length >= 5 ? cleaned : title.trim();
}

/** Extract image URL from an RSS/Atom item block — tries 4 common patterns */
function extractItemImage(block) {
  // 1. <media:content url="..."> or <media:content url="..." medium="image">
  var m = block.match(/<media:content[^>]+url=["']([^"'\s]+)["'][^>]*>/i);
  if (m && /\.(jpg|jpeg|png|webp|gif)/i.test(m[1])) return m[1];

  // 2. <media:thumbnail url="...">
  m = block.match(/<media:thumbnail[^>]+url=["']([^"'\s]+)["']/i);
  if (m) return m[1];

  // 3. <enclosure type="image/..." url="...">  (either attribute order)
  m = block.match(/<enclosure[^>]+type=["']image\/[^"']+["'][^>]*url=["']([^"'\s]+)["']/i)
   || block.match(/<enclosure[^>]+url=["']([^"'\s]+)["'][^>]*type=["']image\/[^"']+["']/i);
  if (m) return m[1];

  // 4. First <img src="..."> inside content:encoded or description CDATA
  var rawContent = extractTagValue(block, 'content:encoded')
    || extractTagValue(block, 'content')
    || extractTagValue(block, 'description');
  var decoded = decodeEntities(rawContent);
  m = decoded.match(/<img[^>]+src=["']([^"'\s]+)["']/i);
  if (m && /^https?:\/\//i.test(m[1])) return m[1];

  return null;
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

  // Decode entities FIRST so &lt;ol&gt; → <ol>, then strip the decoded tags cleanly
  var description = decodeEntities(
    extractTagValue(block, 'description') || extractTagValue(block, 'summary') ||
    extractTagValue(block, 'media:description') || extractTagValue(block, 'content')
  ).replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().slice(0, 500);

  var pubDate = extractTagValue(block, 'pubDate') || extractTagValue(block, 'published')
    || extractTagValue(block, 'updated') || extractTagValue(block, 'dc:date');

  var publishedAt = null;
  if (pubDate) { try { publishedAt = new Date(pubDate).toISOString(); } catch(e) {} }
  if (!publishedAt) publishedAt = new Date().toISOString();

  var sourceName = 'Source';
  if (link) {
    var dm = link.match(/https?:\/\/(?:www\.)?([^\/]+)/);
    if (dm) {
      var parts = dm[1].split('.');
      var name = parts.length >= 2 ? parts[parts.length - 2] : parts[0];
      sourceName = name.charAt(0).toUpperCase() + name.slice(1);
    }
  }

  var imageUrl = extractItemImage(block);

  items.push({ title, link: link || '', description, publishedAt, sourceName, imageUrl });
}

/* ═══════════════════════════════════════════════════
   CONTENT FILTERS
═══════════════════════════════════════════════════ */
function filterItem(item) {
  if (!item || !item.title) return false;  // guard: skip items with no title
  var text = ((item.title || '') + ' ' + (item.description || '')).toLowerCase();
  for (var i = 0; i < BLOCKED_KEYWORDS.length; i++) {
    if (text.includes(BLOCKED_KEYWORDS[i])) {
      console.log('  [FILTERED]', item.title.slice(0, 60));
      return false;
    }
  }
  return true;
}

/* ═══════════════════════════════════════════════════
   DEDUP — Jaccard similarity on word sets
═══════════════════════════════════════════════════ */
function titleWords(title) {
  if (!title) return new Set();  // guard: undefined/null/'' → empty set
  return new Set(
    title.toLowerCase().replace(/[^a-z0-9ഀ-ൿ ]/g, ' ')
      .split(/\s+/).filter(function(w){ return w.length > 3; })
  );
}

function jaccardSimilarity(a, b) {
  var wa = titleWords(a), wb = titleWords(b);
  var inter = 0;
  wa.forEach(function(w){ if (wb.has(w)) inter++; });
  var union = wa.size + wb.size - inter;
  return union > 0 ? inter / union : 0;
}

function isDuplicate(item, seen) {
  return seen.some(function(s){ return jaccardSimilarity(item.title, s.title) > 0.5; });
}

/* ═══════════════════════════════════════════════════
   CORROBORATION — story found in ≥2 independent sources
═══════════════════════════════════════════════════ */
function isCorroborated(item, allItems) {
  return allItems.some(function(other) {
    return other !== item && jaccardSimilarity(item.title, other.title) > 0.3;
  });
}

/** Collect related descriptions from other sources (for AI multi-source context) */
function gatherRelatedContext(item, allItems) {
  return allItems
    .filter(function(x) { return x !== item && jaccardSimilarity(item.title, x.title) > 0.25; })
    .slice(0, 4)
    .map(function(x) {
      return '[' + (x.sourceName || 'Source') + '] ' + x.title
        + (x.description ? ' — ' + x.description.slice(0, 200) : '');
    })
    .join('\n');
}

/* ═══════════════════════════════════════════════════
   GEMINI API — with 429 / quota retry (1 back-off)
═══════════════════════════════════════════════════ */
async function callGemini(prompt, attempt) {
  if (!GOOGLE_AI_API_KEY) throw new Error('No GOOGLE_AI_API_KEY');

  var body = JSON.stringify({
    contents: [{ parts: [{ text: prompt }] }],
    safetySettings: [
      { category: 'HARM_CATEGORY_HATE_SPEECH',       threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
      { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
      { category: 'HARM_CATEGORY_HARASSMENT',        threshold: 'BLOCK_MEDIUM_AND_ABOVE' }
    ],
    generationConfig: { maxOutputTokens: 2500, temperature: 0.55 }
  });

  var apiUrl = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + GOOGLE_AI_API_KEY;

  var response;
  try {
    response = await httpsGet(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
      body
    });
  } catch (e) {
    if (!attempt && (e.message.includes('429') || e.message.includes('503'))) {
      console.warn('    [Gemini 429/503] Rate limit — waiting 25s then retry');
      await sleep(25000);
      return callGemini(prompt, 1);
    }
    throw e;
  }

  var parsed = JSON.parse(response);
  // Gemini may return 200 with an error body (quota exceeded)
  if (parsed.error) {
    var code = parsed.error.code || 0;
    if (!attempt && (code === 429 || code === 503 || code === 500)) {
      console.warn('    [Gemini error ' + code + '] ' + (parsed.error.message || '') + ' — waiting 25s');
      await sleep(25000);
      return callGemini(prompt, 1);
    }
    throw new Error('Gemini: ' + (parsed.error.message || 'API error ' + code));
  }

  var text = parsed?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error('Gemini: empty or blocked response');
  return text.trim();
}

/* ═══════════════════════════════════════════════════
   GROQ API — article-length (70B model), 429 retry
═══════════════════════════════════════════════════ */
async function callGroq(prompt, attempt) {
  if (!GROQ_API_KEY) throw new Error('No GROQ_API_KEY');

  var body = JSON.stringify({
    model:       GROQ_MODEL_ARTICLE,
    messages:    [{ role: 'user', content: prompt }],
    max_tokens:  2000,
    temperature: 0.55
  });

  var response;
  try {
    response = await httpsGet('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization':  'Bearer ' + GROQ_API_KEY,
        'Content-Type':   'application/json',
        'Content-Length': Buffer.byteLength(body)
      },
      body
    });
  } catch (e) {
    if (!attempt && e.message.includes('429')) {
      console.warn('    [Groq 70B 429] Rate limited — waiting 20s');
      await sleep(20000);
      return callGroq(prompt, 1);
    }
    throw e;
  }

  var parsed = JSON.parse(response);
  if (parsed.error) {
    var isRateLimit = parsed.error.type === 'rate_limit_exceeded'
      || (parsed.error.message || '').toLowerCase().includes('rate');
    if (!attempt && isRateLimit) {
      console.warn('    [Groq 70B rate limit]', parsed.error.message || '' , '— waiting 20s');
      await sleep(20000);
      return callGroq(prompt, 1);
    }
    throw new Error('Groq: ' + (parsed.error.message || 'API error'));
  }

  var text = parsed?.choices?.[0]?.message?.content;
  if (!text) throw new Error('Groq: empty response');
  return text.trim();
}

/* ═══════════════════════════════════════════════════
   GROQ FAST — quick tasks (8B model): headline
   rewriting, image prompts. Handles 429 rate limit.
═══════════════════════════════════════════════════ */
async function callGroqFast(prompt, attempt) {
  if (!GROQ_API_KEY) throw new Error('No GROQ_API_KEY');

  var body = JSON.stringify({
    model:       GROQ_MODEL_FAST,
    messages:    [{ role: 'user', content: prompt }],
    max_tokens:  120,
    temperature: 0.4
  });

  var response;
  try {
    response = await httpsGet('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization':  'Bearer ' + GROQ_API_KEY,
        'Content-Type':   'application/json',
        'Content-Length': Buffer.byteLength(body)
      },
      body
    });
  } catch (e) {
    // Handle rate-limit: retry once after back-off
    if (!attempt && e.message && e.message.includes('429')) {
      console.warn('    [Groq 429] Rate limited — waiting 15s');
      await sleep(15000);
      return callGroqFast(prompt, 1);
    }
    throw e;
  }

  var parsed = JSON.parse(response);
  if (parsed.error) {
    var isRateLimit2 = (parsed.error.type === 'rate_limit_exceeded')
      || ((parsed.error.message || '').toLowerCase().includes('rate'));
    if (!attempt && isRateLimit2) {
      console.warn('    [Groq fast 429] Rate limited — waiting 15s');
      await sleep(15000);
      return callGroqFast(prompt, 1);
    }
    throw new Error('Groq fast: ' + (parsed.error.message || 'API error'));
  }
  var text = parsed?.choices?.[0]?.message?.content;
  if (!text) throw new Error('Groq fast: empty response');
  return text.trim();
}

/* ═══════════════════════════════════════════════════
   HEADLINE REWRITER (Groq fast)
   Produces an original, copyright-safe headline that
   preserves the news value but uses fresh phrasing.
═══════════════════════════════════════════════════ */
async function rewriteHeadline(originalTitle) {
  if (!GROQ_API_KEY) return originalTitle;
  var prompt =
    'Rewrite this news headline into a completely original, copyright-safe version '
    + 'that preserves the core news value but uses entirely different words and structure. '
    + 'Professional journalism style. Maximum 15 words. '
    + 'IMPORTANT: Write in English ONLY — never use Japanese, Hindi, or any other language. '
    + 'Return ONLY the rewritten headline — no quotes, no explanation.\n\n'
    + 'Original: ' + originalTitle;
  try {
    var result = await callGroqFast(prompt);
    // Strip surrounding quotes if model adds them
    result = result.replace(/^["']|["']$/g, '').trim();
    return result.length > 10 ? result : originalTitle;
  } catch (e) {
    console.warn('    [Headline rewrite fail]', e.message);
    return originalTitle;
  }
}

/* ═══════════════════════════════════════════════════
   HERO IMAGE GENERATOR
   Uses Groq to craft a photorealistic image prompt,
   then constructs a free Pollinations.ai URL.
   The browser fetches & caches it at display time.
   Falls back to static Unsplash on any failure.
═══════════════════════════════════════════════════ */
async function generateHeroImage(headline, sectionId) {
  var fallback = SECTION_META[sectionId].image;
  if (!GROQ_API_KEY) return fallback;

  var styleHint = {
    trending:  'dramatic news photography, breaking news atmosphere',
    global:    'aerial world view, international news atmosphere',
    india:     'vibrant Indian scene, editorial photography',
    stock:     'financial markets, trading floor, stock charts, blue tones',
    malayalam: 'Kerala landscape, South Indian culture, editorial'
  }[sectionId] || 'editorial news photography';

  var prompt =
    'Create a concise photorealistic image prompt (under 18 words) for a news article hero image. '
    + 'Style: ' + styleHint + '. No text, no logos, no recognisable faces. '
    + 'Based on: "' + headline + '". '
    + 'Return ONLY the image generation prompt.';

  try {
    var imgPrompt = (await callGroqFast(prompt)).replace(/['"]/g, '').trim();
    if (imgPrompt.length < 8) return fallback;
    var seed = hashCode(headline);
    var pollinationsUrl =
      'https://image.pollinations.ai/prompt/' + encodeURIComponent(imgPrompt)
      + '?width=1200&height=630&nologo=true&seed=' + seed;
    console.log('    [Hero image] prompt:', imgPrompt.slice(0, 60));
    return pollinationsUrl;
  } catch (e) {
    console.warn('    [Hero image fail]', e.message);
    return fallback;
  }
}

/* ═══════════════════════════════════════════════════
   BUILD PROMPT — professional news journalist style
   Produces clean flowing prose paragraphs (inverted
   pyramid) suitable for Trending, Global and India.
═══════════════════════════════════════════════════ */
function buildPrompt(item, relatedContext) {
  var multiSrc = relatedContext
    ? '\n\nADDITIONAL REPORTING from other publications:\n' + relatedContext
    : '';

  return (
    'LANGUAGE REQUIREMENT: You MUST write EXCLUSIVELY in English. '
    + 'Do NOT use Japanese, Hindi, Malayalam, Arabic, or any other language — '
    + 'regardless of the language of the source material. '
    + 'English only, from the first word to the last.\n\n'
    + 'You are a professional news journalist writing for an international wire service.\n'
    + 'Write a complete, factual 5-6 paragraph article in AP / BBC / Reuters style.\n\n'
    + 'PRIMARY HEADLINE: "' + item.title + '"\n'
    + 'SOURCE CONTEXT: ' + (item.description || 'No additional context.') + multiSrc + '\n\n'
    + 'ARTICLE STRUCTURE (inverted pyramid):\n'
    + 'Paragraph 1 — THE LEDE: The single most important fact. Who/What/When/Where in the opening sentence.\n'
    + 'Paragraph 2 — BACKGROUND: Context, history, and why this development matters.\n'
    + 'Paragraph 3 — KEY DETAILS: Specific data, figures, official statements or expert views.\n'
    + 'Paragraph 4 — REACTIONS & IMPACT: How stakeholders, markets or the public are responding.\n'
    + 'Paragraph 5 — WIDER CONTEXT: Related developments, regional or global implications.\n'
    + 'Paragraph 6 — WHAT NEXT: Upcoming decisions, open questions, or what to watch.\n\n'
    + 'CRITICAL RULES:\n'
    + '- ENGLISH ONLY — any non-English output is a critical error\n'
    + '- Begin immediately with the first word of the article — NO title, NO headline, NO byline\n'
    + '- 100% original prose — do NOT copy any phrase from any source verbatim\n'
    + '- SYNTHESISE from ALL provided sources — do not rely on a single source\n'
    + '- FACT-CHECK: only assert facts consistent across multiple provided sources\n'
    + '- Balanced, impartial reporting — no opinion, no speculation\n'
    + '- Each paragraph: 2-4 clear, active-voice sentences\n'
    + '- NO bullet points, NO headers, NO bold text, NO markdown, NO HTML tags in your output\n'
    + '- Separate paragraphs with a blank line only\n'
    + '- Do NOT include a dateline, word count, or source footer\n'
  );
}

/* ═══════════════════════════════════════════════════
   JSON EXTRACTOR — strips markdown code fences and
   isolates the JSON object from AI response text
═══════════════════════════════════════════════════ */
function extractJson(text) {
  // Strip ```json ... ``` or ``` ... ``` wrappers
  var clean = text.replace(/^[\s\S]*?```(?:json)?\s*/i, '').replace(/\s*```[\s\S]*$/i, '').trim();
  if (!clean.startsWith('{')) clean = text.trim(); // if no code fence, use raw
  var start = clean.indexOf('{');
  var end   = clean.lastIndexOf('}');
  if (start === -1 || end === -1) throw new Error('No JSON object found in AI response');
  return clean.slice(start, end + 1);
}

/* ═══════════════════════════════════════════════════
   STORY JSON → HTML  (Axios Smart Brevity renderer)
   Converts the structured JSON object into rich HTML
   that news.html modal renders with dedicated CSS.
═══════════════════════════════════════════════════ */
function storyJsonToHtml(data) {
  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  var html = '';

  // ── Lead paragraph ──────────────────────────────────────────────────────────
  if (data.lead_bold || data.lead_rest) {
    html += '<p class="story-lead">';
    if (data.lead_bold) html += '<strong>' + esc(data.lead_bold) + '</strong> ';
    if (data.lead_rest) html += esc(data.lead_rest);
    html += '</p>';
  }

  // ── Why it matters ──────────────────────────────────────────────────────────
  if (data.why_it_matters) {
    html += '<ul class="story-bullets"><li>'
      + '<strong>Why it matters:</strong> ' + esc(data.why_it_matters)
      + '</li></ul>';
  }

  // ── Zoom in ─────────────────────────────────────────────────────────────────
  if (data.zoom_in) {
    html += '<p class="story-zoom"><strong>Zoom in:</strong> ' + esc(data.zoom_in) + '</p>';
  }

  // ── Numbered sections ───────────────────────────────────────────────────────
  if (Array.isArray(data.sections)) {
    data.sections.forEach(function(sec) {
      if (!sec) return;
      html += '<p class="story-section-item">'
        + '<span class="story-section-emoji">' + esc(sec.emoji || '') + '</span> '
        + '<strong>' + esc(sec.number) + '. ' + esc(sec.label) + ':</strong> '
        + esc(sec.body || '')
        + '</p>';
      if (sec.sub_bold || sec.sub_rest) {
        html += '<ul class="story-sub-bullets"><li>'
          + (sec.sub_bold ? '<strong>' + esc(sec.sub_bold) + '</strong> ' : '')
          + esc(sec.sub_rest || '')
          + '</li></ul>';
      }
    });
  }

  return html || '<p>Story content unavailable.</p>';
}

/* ═══════════════════════════════════════════════════
   GENERATE STORY — journalist prose
   Gemini 2.0 Flash → Groq 70B → RSS multi-source fallback
   Returns { html: string, teaser: string }
   Used ONLY for Trending / Global / India sections.
═══════════════════════════════════════════════════ */
function proseToHtml(text) {
  // Split on blank lines (paragraph breaks), wrap each in <p>
  var paras = text.split(/\n\s*\n/).map(function(p){ return p.trim(); }).filter(Boolean);
  if (!paras.length) paras = [text.trim()];
  return paras.map(function(p) {
    return '<p>' + p.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</p>';
  }).join('');
}

async function generateStory(item, relatedContext) {
  var prompt  = buildPrompt(item, relatedContext);
  var rawText = null;

  // ── 1. Gemini 1.5 Flash ──────────────────────────────────────────────────
  try {
    rawText = await callGemini(prompt);
    console.log('    [Gemini ✓] journalist article');
  } catch (e) {
    console.warn('    [Gemini ✗]', e.message);
  }

  // ── 2. Groq llama-3.3-70b fallback ───────────────────────────────────────
  if (!rawText) {
    try {
      rawText = await callGroq(prompt);
      console.log('    [Groq ✓] journalist article');
    } catch (e) {
      console.warn('    [Groq ✗]', e.message);
    }
  }

  // ── 3. Convert AI prose → HTML paragraphs ────────────────────────────────
  if (rawText && rawText.trim().length > 50) {
    var html   = proseToHtml(rawText.trim());
    var teaser = rawText.replace(/\s+/g, ' ').trim().slice(0, 140);
    if (teaser.length >= 140) teaser = teaser.slice(0, 137) + '…';
    return { html: html, teaser: teaser };
  }

  // ── 4. Enhanced RSS fallback — multi-source synthesis ───────
  // Both AI APIs failed (rate-limited or unavailable). Build a proper
  // multi-paragraph article from the primary RSS description PLUS all
  // related context gathered from other sources.
  // Never show a stub stub message with scheduling promises.
  console.warn('    [RSS fallback - multi-source]', item.title.slice(0, 55));

  var paragraphs = [];

  // Para 1: primary item description
  var mainDesc = (item.description || '').replace(/\s+/g, ' ').trim();
  if (mainDesc.length > 20) paragraphs.push(mainDesc);

  // Additional paragraphs from related context lines.
  // gatherRelatedContext() formats as: "[Source] Title — description"
  if (relatedContext) {
    relatedContext.split('\n').forEach(function(line) {
      var dashIdx = line.indexOf(' — ');
      var ctxText = dashIdx >= 0 ? line.slice(dashIdx + 3).replace(/\s+/g, ' ').trim() : '';
      if (ctxText.length > 40) {
        var alreadyPresent = paragraphs.some(function(p) {
          return jaccardSimilarity(p, ctxText) > 0.55;
        });
        if (!alreadyPresent) paragraphs.push(ctxText);
      }
    });
  }

  // Clean attribution paragraph
  var srcLabel = item.sourceName || 'wire services';
  paragraphs.push('Reporting by ' + srcLabel + '. Read the full story at the original publication.');

  var fallbackHtml = paragraphs.map(function(p) {
    return '<p>' + p.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</p>';
  }).join('');

  var fallbackTeaser = paragraphs[0]
    ? paragraphs[0].slice(0, 137) + (paragraphs[0].length > 137 ? '…' : '')
    : item.title.slice(0, 140);

  return { html: fallbackHtml, teaser: fallbackTeaser };
}

/* ═══════════════════════════════════════════════════
   SOURCE-NAME CLEANER
   Google News RSS aggregation embeds " - Source Name"
   patterns inside descriptions. Strip them so the
   RSS-only story modal looks clean.
═══════════════════════════════════════════════════ */
function cleanRssDescription(desc) {
  if (!desc) return '';
  // Cut the text before the first embedded " - Source Name" attribution
  // (Capitalized Latin words following a dash, common in Google News descriptions)
  var cut = desc.search(/\s[-–—]\s[A-Z][a-zA-Z\s\.]{2,50}(?=\s[-–—]|[A-Z][a-z]|\s*$)/);
  var result = (cut > 40) ? desc.slice(0, cut).trim() : desc;
  return result.replace(/\s{2,}/g, ' ').trim();
}

/* ═══════════════════════════════════════════════════
   RSS STORY BUILDER — stock / malayalam only
   No AI. Uses raw RSS description as the story.
   Returns { html: string, teaser: string, image: string|null }
═══════════════════════════════════════════════════ */

/** Unsplash fallback images keyed by section — used when RSS has no embedded image */
var RSS_FALLBACK_IMAGES = {
  stock:        'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=70',
  malayalam:    'https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=800&q=70',
  ml_trending:  'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&q=70',
  ml_stock:     'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=800&q=70',
  ml_movies:    'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=70',
  ml_music:     'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=70',
  ml_local:     'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=800&q=70',
  ml_science:   'https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=800&q=70',
  ml_space:     'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=800&q=70',
  ml_sports:    'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800&q=70',
  ml_health:    'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=800&q=70',
  ml_food:      'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=800&q=70',
  ml_realestate:'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800&q=70',
  ml_career:    'https://images.unsplash.com/photo-1521791136064-7986c2920216?w=800&q=70',
  ml_tech:      'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=70'
};

function rssStory(item, sectionId) {
  var raw  = (item.description || '').trim();
  var desc = cleanRssDescription(raw) || raw;
  var html = desc
    ? '<p>' + desc.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</p>'
    : '<p>Full story available at the original source.</p>';
  var teaser = desc.slice(0, 140) || item.title.slice(0, 140);
  if (teaser.length >= 140) teaser = teaser.slice(0, 137) + '…';
  // Use RSS-embedded image; fall back to section-themed Unsplash
  var image = item.imageUrl || (sectionId ? (RSS_FALLBACK_IMAGES[sectionId] || null) : null);
  return { html: html, teaser: teaser, image: image };
}

/* ═══════════════════════════════════════════════════
   BUILD SECTION
   isRssOnly: stock + malayalam → raw RSS feed only
   aiSection: trending + global + india → AI headline
              rewrite + journalist article generation
═══════════════════════════════════════════════════ */
async function buildSection(sectionId, feedPool, meta) {
  console.log('\n[Section]', sectionId.toUpperCase());
  var isRssOnly = (sectionId === 'stock' || sectionId === 'malayalam' || sectionId.startsWith('ml_'));

  // Always include first 2 anchored feeds + random extras
  var pool    = feedPool || [];
  var anchors = pool.slice(0, 2);
  var rest    = shuffle(pool.slice(2));
  var chosen  = anchors.concat(rest).slice(0, FEEDS_PER_SECTION);
  console.log('  Sources:', chosen.map(function(f){ return f.name || f.url; }).join(', '));

  var results = await Promise.allSettled(chosen.map(function(f){ return fetchRSS(f); }));
  var allItems = [];
  results.forEach(function(r, i) {
    if (r.status === 'fulfilled') {
      console.log('  Parsed', r.value.length, 'items from', chosen[i].name || chosen[i].url);
      allItems = allItems.concat(r.value);
    }
  });

  allItems = allItems.filter(filterItem);

  var deduped = [];
  allItems.forEach(function(item) {
    if (!isDuplicate(item, deduped)) deduped.push(item);
  });

  deduped.sort(function(a, b) {
    return new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime();
  });

  console.log('  Items after dedup+filter:', deduped.length);
  var selected = deduped.slice(0, isRssOnly ? MAX_ITEMS_RSS_ONLY : MAX_ITEMS_PER_SECTION);

  if (selected.length === 0) {
    console.warn('  No items for', sectionId, '— inserting placeholder');
    return makePlaceholderSection(sectionId, meta);
  }

  // ── Generate dynamic hero image from top story ───────────────────────────
  console.log('  Generating hero image for section:', sectionId);
  var sectionImage = await generateHeroImage(selected[0].title, sectionId);

  // ── Generate stories ─────────────────────────────────────────────────────
  console.log('  Mode:', isRssOnly ? '📰 RSS-only (no AI article)' : '🤖 AI journalist article');

  var outputItems = [];
  for (var j = 0; j < selected.length; j++) {
    var item = selected[j];
    console.log('  Story', (j + 1) + '/' + selected.length + ':', item.title.slice(0, 65));

    var headline, storyResult, relCtxLines;

    if (isRssOnly) {
      // ── Stock + Malayalam: raw RSS headline + RSS description + image ──
      headline    = item.title;                        // no Groq rewrite
      storyResult = rssStory(item, sectionId);         // passes sectionId for fallback image
      relCtxLines = 0;
      console.log('    [RSS only] headline + description' + (storyResult.image ? ' + image' : ''));

    } else {
      // ── Trending + Global + India: AI headline + AI journalist article ──
      var relatedContext = gatherRelatedContext(item, allItems);
      relCtxLines = relatedContext ? relatedContext.split('\n').length : 0;
      if (relCtxLines > 0) console.log('    Cross-refs found:', relCtxLines);

      // Groq fast: copyright-safe headline rewrite
      headline = await rewriteHeadline(item.title);
      console.log('    Headline:', headline.slice(0, 60));

      // Gemini → Groq 70B → RSS: full journalist article
      storyResult = await generateStory(item, relatedContext);
      // AI articles do NOT use RSS images (per task requirement)
      storyResult.image = null;

      // Rate-limit pause: Gemini free tier = 15 RPM (1 call per 4 s on average).
      // With ~2 s API latency + 5 s sleep = ~7 s per item → max ~8.5 RPM — safely under limit.
      if (j < selected.length - 1) await sleep(5000);
    }

    var outItem = {
      id:          sectionId + '-' + Date.now() + '-' + j,
      headline:    headline,
      teaser:      storyResult.teaser,
      story:       storyResult.html,
      source:      item.sourceName,
      sourceUrl:   item.link || '',
      publishedAt: item.publishedAt,
      expiresAt:   new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString(),
      verified:    isCorroborated(item, allItems),
      aiGenerated: !isRssOnly,
      multiSource: relCtxLines >= 2
    };
    if (storyResult.image) outItem.image = storyResult.image;
    outputItems.push(outItem);
  }

  return { image: sectionImage, label: meta.label, accent: meta.accent, items: outputItems };
}

/* ═══════════════════════════════════════════════════
   PLACEHOLDER SECTION (when all feeds fail)
═══════════════════════════════════════════════════ */
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
   MERGE — accumulate stories across 48 h, new first
═══════════════════════════════════════════════════ */
function mergeItems(newItems, existingItems) {
  var TWO_DAYS = 48 * 60 * 60 * 1000;
  var now = Date.now();

  // Purge expired + placeholder items
  var validExisting = (existingItems || []).filter(function(item) {
    if (!item || !item.publishedAt || !item.headline) return false;
    var hl = item.headline.trim().toLowerCase();
    if (hl.startsWith('content updating') || hl === 'placeholder' || hl === 'loading...') return false;
    return now - new Date(item.publishedAt).getTime() < TWO_DAYS;
  });

  // Add new items not already represented.
  // IMPORTANT: output items use .headline (not raw RSS .title), so we compare
  // headlines directly here — isDuplicate() expects raw .title and would crash.
  var toAdd = (newItems || []).filter(function(newItem) {
    if (!newItem || !newItem.headline) return false;
    // Never persist placeholder entries into the rolling archive
    var newHl = newItem.headline.trim().toLowerCase();
    if (newHl.startsWith('content updating') || newHl === 'placeholder' || newHl === 'loading...') return false;
    // Skip if same id already present
    if (validExisting.some(function(e){ return e.id === newItem.id; })) return false;
    // Skip if headline is too similar to an archived story (Jaccard > 0.5)
    return !validExisting.some(function(e) {
      return jaccardSimilarity(newItem.headline || '', e.headline || '') > 0.5;
    });
  });

  console.log('  Merge: +' + toAdd.length + ' new, ' + validExisting.length + ' existing kept');

  // New items first, then existing (both sorted by publishedAt desc)
  var combined = toAdd.concat(validExisting);
  combined.sort(function(a, b) {
    return new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime();
  });

  // Cap the rolling 48 h archive at 40 per section — matches the page's
  // scrollable boxes. AI sections (16 new/run) accumulate to 40 across runs.
  return combined.slice(0, 40);
}

/* ═══════════════════════════════════════════════════
   MAIN
═══════════════════════════════════════════════════ */
async function main() {
  console.log('='.repeat(65));
  console.log('VilfinTV News Builder v3');
  console.log('Started   :', new Date().toISOString());
  console.log('Gemini key:', GOOGLE_AI_API_KEY ? 'present (' + GOOGLE_AI_API_KEY.slice(0,4) + '...)' : '⚠ MISSING');
  console.log('Groq key  :', GROQ_API_KEY      ? 'present (' + GROQ_API_KEY.slice(0,4) + '...)'      : '⚠ MISSING');
  console.log('='.repeat(65));

  var dataDir = path.join(__dirname, '..', 'data');
  var outPath = path.join(dataDir, 'news.json');

  var existingData = null;
  if (fs.existsSync(outPath)) {
    try {
      existingData = JSON.parse(fs.readFileSync(outPath, 'utf8'));
      console.log('Loaded existing news.json for merge');
    } catch(e) {
      console.warn('Could not read existing news.json:', e.message);
    }
  }

  var output = { generated: new Date().toISOString(), sections: {} };
  var sectionIds = Object.keys(SOURCE_POOL);

  for (var i = 0; i < sectionIds.length; i++) {
    var sid = sectionIds[i];
    try {
      var newSection = await buildSection(sid, SOURCE_POOL[sid], SECTION_META[sid]);
      var existingItems = existingData?.sections?.[sid]?.items || [];
      newSection.items = mergeItems(newSection.items, existingItems);
      output.sections[sid] = newSection;
    } catch (e) {
      console.error('Section', sid, 'failed entirely:', e.message);
      output.sections[sid] = makePlaceholderSection(sid, SECTION_META[sid]);
    }

    // After each AI section (trending / global / india), pause 12 s before the next
    // so Gemini's 15 RPM free-tier quota has time to recover between bursts.
    var _isAiSec = (sid === 'trending' || sid === 'global' || sid === 'india');
    if (_isAiSec && i < sectionIds.length - 1) {
      console.log('  [Rate-limit buffer] 12 s pause before next section...');
      await sleep(12000);
    }
  }

  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
    console.log('\nCreated data/ directory');
  }

  fs.writeFileSync(outPath, JSON.stringify(output, null, 2) + '\n', 'utf8');

  var totalItems = 0;
  console.log('\n' + '='.repeat(65));
  console.log('Output:', outPath);
  sectionIds.forEach(function(sid) {
    var count = output.sections[sid]?.items?.length || 0;
    totalItems += count;
    console.log('  ' + sid.padEnd(12) + ':', count, 'stories');
  });
  console.log('  TOTAL       :', totalItems, 'stories');
  console.log('Completed :', new Date().toISOString());
  console.log('='.repeat(65));
}

main().catch(function(e) {
  // Log prominently but do NOT exit(1) — the commit step should still run
  // so any partial data already written makes it to the repo.
  console.error('='.repeat(65));
  console.error('FATAL ERROR (non-zero exit suppressed so commit step runs):');
  console.error(e && e.message ? e.message : String(e));
  console.error('='.repeat(65));
  process.exit(0);
});
