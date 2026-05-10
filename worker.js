/**
 * VilfinTV Market Assistant — Cloudflare Worker
 * ═══════════════════════════════════════════════
 *
 * DEPLOY STEPS (Cloudflare Dashboard):
 *  1. Workers & Pages → Create → Worker → paste this file → Save & Deploy
 *  2. Settings → Variables → Add the following secrets:
 *       GROQ_API_KEY       — https://console.groq.com/keys        (free, recommended)
 *       GEMINI_API_KEY     — https://aistudio.google.com/apikey   (free, recommended)
 *       OPENAI_API_KEY     — https://platform.openai.com/api-keys (paid)
 *       DEEPSEEK_API_KEY   — https://platform.deepseek.com        (optional)
 *  3. Settings → Triggers → use *.workers.dev URL
 *  4. Paste YOUR Worker URL into the "Connect AI Services" modal on the website
 *
 * CLI SECRETS (alternative to Dashboard UI):
 *   npx wrangler secret put GROQ_API_KEY
 *   npx wrangler secret put GEMINI_API_KEY
 *   npx wrangler secret put OPENAI_API_KEY
 *   npx wrangler secret put DEEPSEEK_API_KEY
 *
 * CORS: locked to vilfin-tv.github.io + localhost for development.
 *
 * PIPELINE (per /query request):
 *  Step A — Live Context: Yahoo Finance Search + DuckDuckGo Instant Answer
 *  Step B — AI Response:  routes to requested provider, then cascades
 *
 *  Provider cascade (if no specific provider is requested):
 *    Groq (Llama 3.3 70B) → Gemini → OpenAI → DeepSeek → Pollinations (free)
 *
 * QUOTAS (approximate free tier):
 *  Groq:        6,000 req/day, 500,000 tokens/day
 *  Gemini:      1,500 req/day, 1 M tokens/day (Gemini 2.0 Flash)
 *  OpenAI:      Pay-per-use (gpt-4o-mini is cheapest)
 *  DeepSeek:    $0.14 / M input tokens
 *  Pollinations: free, no key (emergency fallback only)
 */

'use strict';

// ─── Allowed origins ──────────────────────────────────────────────────────────
const ALLOWED_ORIGINS = [
  'https://vilfin-tv.github.io',
  'https://vilfintv.github.io',
  'http://127.0.0.1:5500',
  'http://localhost:5500',
  'http://localhost:3000',
];

// ─── Endpoints ────────────────────────────────────────────────────────────────
const GROQ_ENDPOINT     = 'https://api.groq.com/openai/v1/chat/completions';
const DEEPSEEK_ENDPOINT = 'https://api.deepseek.com/chat/completions';
const OPENAI_ENDPOINT   = 'https://api.openai.com/v1/chat/completions';
const GEMINI_BASE       = 'https://generativelanguage.googleapis.com/v1beta/models/';

// ─── Models ───────────────────────────────────────────────────────────────────
const GROQ_MODEL     = 'llama-3.3-70b-versatile';
const DEEPSEEK_MODEL = 'deepseek-chat';
const OPENAI_MODEL   = 'gpt-4o-mini';
const GEMINI_MODEL   = 'gemini-2.0-flash';

// ─── Generation config ────────────────────────────────────────────────────────
const MAX_TOKENS  = 8000;   // raised from 1200 — research reports need 15+ tabs (~5000-8000 tokens)
const TEMPERATURE = 0.6;

// ─── System prompt ────────────────────────────────────────────────────────────
const SYSTEM_PROMPT = (date) =>
  `You are the Market Assistant for VilfinTV — an institutional-grade financial intelligence platform.

Your role: Provide precise, research-quality analysis on equities, indices, ETFs, commodities, crypto, forex, and macro themes for investors in India and globally.

Today's date: ${date}

STRUCTURED REPORT MODE (when the user prompt requests JSON output):
- Respond with ONLY a valid JSON object — no prose, no commentary outside the JSON.
- The JSON must follow this exact structure:
  {"asset":"Name","date":"DD-MMM-YYYY","tabs":[{"id":1,"name":"Tab Name","fields":{"Field Name":"Value"},"subsections":[{"title":"Sub Title","fields":{"Field":"Value"}}]},...]}
- Always produce exactly 10 tabs matching the schema specified in the user prompt.
- All field values must be plain strings or numbers — never nested objects, never arrays, never null.
- If data is unavailable for a field, use the string "No Data Available" — never omit the key.
- Start your response immediately with { and end with } — no text before or after the JSON object.
- NEVER output ## TAB or any section headers — all content goes inside the JSON structure.

CONVERSATIONAL MODE (all other queries):
- Use concise, precise language — lead with the most actionable insight.
- Cite specific prices, percentages, and dates when available.
- Keep responses under 400 words unless the topic demands depth.
- Never speculate without flagging it as opinion.
- Never recommend specific buy/sell actions — provide analysis only.
- Close with 2–3 relevant follow-up areas the user might explore.`;

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN FETCH HANDLER
// ═══════════════════════════════════════════════════════════════════════════════
export default {
  async fetch(request, env) {
    const origin      = request.headers.get('Origin') || '';
    const allowOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];

    const CORS = {
      'Access-Control-Allow-Origin':  allowOrigin,
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age':       '86400',
    };

    // ── Preflight ──────────────────────────────────────────────────────────────
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    const url = new URL(request.url);

    // ── Health check ───────────────────────────────────────────────────────────
    if (url.pathname === '/' || url.pathname === '/health') {
      return json({
        status:    'ok',
        service:   'VilfinTV Market Assistant',
        providers: {
          groq:      !!env.GROQ_API_KEY,
          gemini:    !!env.GEMINI_API_KEY,
          openai:    !!env.OPENAI_API_KEY,
          deepseek:  !!env.DEEPSEEK_API_KEY,
          pollinations: true,
        },
      }, CORS);
    }

    // ── Daily snapshot endpoint (build-time only — called by build.js) ─────────
    if (url.pathname === '/snapshot' && request.method === 'POST') {
      try {
        const snapshot = await generateMarketSnapshot(env);
        return json(snapshot, CORS);
      } catch (err) {
        console.error('snapshot error:', err.message);
        return json({ error: 'Snapshot generation failed' }, CORS, 503);
      }
    }

    // ── Cricket live scores endpoint — GET /cricket ────────────────────────────
    // Fetches IPL-first data from ESPN + TheSportsDB; returns structured match JSON.
    // No auth required. Safe for public browser calls.
    if (url.pathname === '/cricket' && (request.method === 'GET' || request.method === 'POST')) {
      try {
        const cricData = await fetchCricketData();
        return json(cricData, CORS);
      } catch (err) {
        console.error('cricket error:', err.message);
        return json({ matches: [], error: 'Cricket data temporarily unavailable' }, CORS, 500);
      }
    }

    // ── Live news feed proxy — fetch RSS/Atom server-side and return JSON ──
    if (url.pathname === '/news-feed' && request.method === 'POST') {
      try {
        const body = await request.json();
        const targetUrl = String(body.url || '').trim();
        const fallbackUrl = String(body.fallbackUrl || '').trim();
        const limit = Math.max(1, Math.min(12, Number(body.limit) || 6));
        if (!/^https?:\/\//i.test(targetUrl)) {
          return json({ error: 'Valid url is required' }, CORS, 400);
        }
        const items = await fetchNewsFeedItems(targetUrl, fallbackUrl, limit);
        return json({ items }, CORS);
      } catch (err) {
        console.error('news-feed error:', err.message);
        return json({ items: [], error: 'News feed unavailable' }, CORS, 200);
      }
    }

    // ── Interactive AI query endpoint ──────────────────────────────────────────
    if ((url.pathname === '/query' || url.pathname === '/ask') && request.method === 'POST') {
      let body;
      try { body = await request.json(); } catch {
        return json({ error: 'Invalid JSON body' }, CORS, 400);
      }

      const prompt   = (body.prompt || body.query || body.q || '').trim();
      const provider = (body.provider || '').toLowerCase().trim();
      // Accept a messages array for conversation history support
      const messages = Array.isArray(body.messages) ? body.messages : null;

      if (!prompt || prompt.length < 2) {
        return json({ error: 'prompt is required' }, CORS, 400);
      }
      if (prompt.length > 32000) {
        return json({ error: 'prompt too long (max 32000 chars)' }, CORS, 400);
      }

      try {
        const result = await handleQuery(prompt, env, provider, messages);
        return json({ result }, CORS);
      } catch (err) {
        console.error('handleQuery error:', err.message);
        // Surface the actual provider-cascade detail so the client can show
        // a useful error instead of a generic "try again" loop.
        const detail = err && err.message ? err.message : 'unknown error';
        return json({
          error: 'Service temporarily unavailable. Please retry.',
          detail,
          hint: detail.includes('All AI providers unavailable')
            ? 'All configured providers returned empty/failed. Likely a daily quota hit. Try again in an hour or check your provider dashboards.'
            : undefined,
        }, CORS, 503);
      }
    }

    return json({ error: 'Not found' }, CORS, 404);
  }
};

async function fetchNewsFeedItems(url, fallbackUrl, limit = 6) {
  const tried = new Set();
  for (const candidate of [url, fallbackUrl]) {
    const target = String(candidate || '').trim();
    if (!target || tried.has(target)) continue;
    tried.add(target);
    try {
      const res = await fetch(target, {
        headers: {
          'User-Agent': 'VilfinTV/1.0 (+https://vilfin-tv.github.io/MultiScreener/)',
          'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8',
        },
        signal: AbortSignal.timeout(10000),
      });
      if (!res.ok) continue;
      const xml = await res.text();
      const items = parseFeedXml(xml, limit);
      if (items.length) return items;
    } catch (_) {}
  }
  return [];
}

function parseFeedXml(xml, limit = 6) {
  const text = String(xml || '').replace(/\r/g, '');
  const rssItems = [...text.matchAll(/<item\b[\s\S]*?<\/item>/gi)]
    .map(m => parseRssItem(m[0]))
    .filter(i => i.title);
  if (rssItems.length) return rssItems.slice(0, limit);
  const atomItems = [...text.matchAll(/<entry\b[\s\S]*?<\/entry>/gi)]
    .map(m => parseAtomEntry(m[0]))
    .filter(i => i.title);
  return atomItems.slice(0, limit);
}

function parseRssItem(block) {
  return {
    title: decodeXml(stripCdata(extractTag(block, 'title'))),
    link: decodeXml(stripCdata(extractTag(block, 'link'))) || '#',
    pubDate: decodeXml(stripCdata(extractTag(block, 'pubDate'))),
  };
}

function parseAtomEntry(block) {
  const linkMatch = String(block || '').match(/<link\b[^>]*\bhref=["']([^"']+)["'][^>]*\/?>/i);
  return {
    title: decodeXml(stripCdata(extractTag(block, 'title'))),
    link: decodeXml(linkMatch?.[1] || stripCdata(extractTag(block, 'link'))) || '#',
    pubDate: decodeXml(stripCdata(extractTag(block, 'published') || extractTag(block, 'updated'))),
  };
}

function extractTag(block, tag) {
  const m = String(block || '').match(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i'));
  return m ? m[1].trim() : '';
}

function stripCdata(s) {
  return String(s || '').replace(/^<!\[CDATA\[/, '').replace(/\]\]>$/, '').trim();
}

function decodeXml(s) {
  return String(s || '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&');
}

// ═══════════════════════════════════════════════════════════════════════════════
// STEP A — LIVE MARKET CONTEXT  (cascading multi-source fetcher)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Extract the most likely ticker/asset name from the user prompt.
 * Returns a short query string suitable for financial API lookups.
 */
function extractTicker(prompt) {
  // Common Indian tickers often appear as ALL-CAPS or with .NS/.BO suffix
  const tickerRe = /\b([A-Z]{2,10}(?:\.(?:NS|BO|BSE|NSE))?)\b/g;
  const matches  = [...prompt.matchAll(tickerRe)].map(m => m[1]);
  // Filter out common English words that happen to be uppercase
  const stopWords = new Set(['I','AM','THE','AND','OR','FOR','IN','ON','AT','TO','A','IS','ARE','BE',
    'ETF','MF','IPO','NAV','LTP','EPS','P/E','PE','NSE','BSE','NFO','SIP','FD','RBI','SEBI']);
  const tickers = matches.filter(m => !stopWords.has(m) && m.length >= 3);
  return tickers[0] || prompt.split(/\s+/).slice(0, 3).join(' ');
}

/**
 * Fetch live quote from Yahoo Finance v8 chart API.
 * Returns a formatted string with price, change, volume etc., or null on failure.
 */
async function fetchYFQuote(symbol) {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`
      + '?interval=1d&range=5d&includePrePost=false';
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)',
        'Accept':     'application/json',
      },
      signal: AbortSignal.timeout(6000),
    });
    if (!res.ok) return null;
    const d    = await res.json();
    const meta = d?.chart?.result?.[0]?.meta;
    if (!meta) return null;

    const price       = meta.regularMarketPrice;
    const prevClose   = meta.chartPreviousClose || meta.previousClose;
    const change      = (price && prevClose) ? (price - prevClose).toFixed(2) : null;
    const changePct   = (price && prevClose) ? (((price - prevClose) / prevClose) * 100).toFixed(2) : null;
    const volume      = meta.regularMarketVolume ? Number(meta.regularMarketVolume).toLocaleString('en-IN') : null;
    const mktState    = meta.marketState || '';
    const currency    = meta.currency || '';
    const exchName    = meta.exchangeName || meta.fullExchangeName || '';
    const lastDate    = meta.regularMarketTime
      ? new Date(meta.regularMarketTime * 1000).toISOString().split('T')[0]
      : 'N/A';

    if (!price) return null;

    const arrow = changePct !== null ? (parseFloat(changePct) >= 0 ? '▲' : '▼') : '';
    let out = `**${symbol} (${exchName})** — ${currency} ${price}`;
    if (change !== null) out += `  ${arrow} ${change} (${changePct}%)`;
    if (volume)          out += `  | Vol: ${volume}`;
    out += `  | As of: ${lastDate} [${mktState}]`;
    return out;
  } catch { return null; }
}

/**
 * Fetch live quote from Yahoo Finance v7 (alternative endpoint).
 * Falls back to this if v8 returns no usable meta.
 */
async function fetchYFQuoteV7(symbol) {
  try {
    const url = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(symbol)}`;
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)',
        'Accept':     'application/json',
      },
      signal: AbortSignal.timeout(6000),
    });
    if (!res.ok) return null;
    const d = await res.json();
    const q = d?.quoteResponse?.result?.[0];
    if (!q) return null;

    const price     = q.regularMarketPrice;
    const change    = q.regularMarketChange?.toFixed(2);
    const changePct = q.regularMarketChangePercent?.toFixed(2);
    const volume    = q.regularMarketVolume ? Number(q.regularMarketVolume).toLocaleString('en-IN') : null;
    const currency  = q.currency || '';
    const exchName  = q.fullExchangeName || q.exchange || '';
    const lastDate  = q.regularMarketTime
      ? new Date(q.regularMarketTime * 1000).toISOString().split('T')[0]
      : 'N/A';
    const mktState  = q.marketState || '';
    const mcap      = q.marketCap   ? `₹${(q.marketCap / 1e7).toFixed(0)} Cr` : null;
    const pe        = q.trailingPE  ? q.trailingPE.toFixed(1) : null;
    const week52H   = q.fiftyTwoWeekHigh;
    const week52L   = q.fiftyTwoWeekLow;

    if (!price) return null;
    const arrow = changePct !== null ? (parseFloat(changePct) >= 0 ? '▲' : '▼') : '';
    let out = `**${q.longName || q.shortName || symbol} (${symbol}, ${exchName})** — ${currency} ${price}`;
    if (change !== null) out += `  ${arrow} ${change} (${changePct}%)`;
    if (volume)          out += `  | Vol: ${volume}`;
    if (mcap)            out += `  | MCap: ${mcap}`;
    if (pe)              out += `  | P/E: ${pe}`;
    if (week52H && week52L) out += `\n  52W High: ${week52H}  |  52W Low: ${week52L}`;
    out += `  | As of: ${lastDate} [${mktState}]`;
    return out;
  } catch { return null; }
}

/**
 * Fetch NSE India live quote (for Indian stocks with .NS ticker).
 * Uses the public NSE quote API (no auth required).
 */
async function fetchNSEQuote(nseSymbol) {
  // nseSymbol should be bare e.g. "HDFCBANK", not "HDFCBANK.NS"
  const sym = nseSymbol.replace(/\.NS$/i, '').replace(/\.BO$/i, '');
  try {
    // NSE requires a cookie-based session, so we use the public getQuote endpoint
    const url = `https://www.nseindia.com/api/quote-equity?symbol=${encodeURIComponent(sym)}`;
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
        'Accept':     'application/json',
        'Referer':    'https://www.nseindia.com/',
      },
      signal: AbortSignal.timeout(7000),
    });
    if (!res.ok) return null;
    const d  = await res.json();
    const pd = d?.priceInfo;
    if (!pd) return null;

    const ltp      = pd.lastPrice;
    const change   = pd.change?.toFixed(2);
    const changePct= pd.pChange?.toFixed(2);
    const open     = pd.open;
    const high     = pd.intraDayHighLow?.max;
    const low      = pd.intraDayHighLow?.min;
    const prevClose= pd.previousClose;

    if (!ltp) return null;
    const arrow = changePct ? (parseFloat(changePct) >= 0 ? '▲' : '▼') : '';
    let out = `**NSE: ${sym}** — ₹${ltp}  ${arrow} ${change} (${changePct}%)`;
    if (open)     out += `  | Open: ₹${open}`;
    if (high)     out += `  | H: ₹${high}  L: ₹${low}`;
    if (prevClose) out += `  | Prev Close: ₹${prevClose}`;
    return out;
  } catch { return null; }
}

/**
 * Fetch NSE mutual fund NAV from AMFI India (free public API).
 * amfiCode should be a numeric AMFI scheme code.
 */
async function fetchAMFINav(fundName) {
  try {
    // AMFI provides a flat text file — we search it by fund name
    const res = await fetch('https://www.amfiindia.com/spages/NAVAll.txt', {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)' },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return null;
    const text   = await res.text();
    const lines  = text.split('\n');
    const search = fundName.toLowerCase().replace(/[^a-z0-9 ]/g, '');

    for (const line of lines) {
      const cols = line.split(';');
      if (cols.length < 5) continue;
      const name = (cols[3] || '').toLowerCase().replace(/[^a-z0-9 ]/g, '');
      if (name.includes(search.slice(0, 20))) {
        const nav  = cols[4]?.trim();
        const date = cols[5]?.trim();
        const schemeName = cols[3]?.trim();
        if (nav && parseFloat(nav) > 0) {
          return `**AMFI NAV — ${schemeName}**: ₹${nav}  | Date: ${date}`;
        }
      }
    }
    return null;
  } catch { return null; }
}

/**
 * Main live-data cascade:
 *  1. Yahoo Finance Search (instrument identification + headlines)
 *  2. Yahoo Finance Quote v7 (live price — richest data)
 *  3. Yahoo Finance Quote v8 (fallback price endpoint)
 *  4. NSE India API (Indian stocks — authoritative domestic source)
 *  5. AMFI NAV API (mutual funds)
 *  6. DuckDuckGo Instant Answer (general context fallback)
 *
 * All sources run concurrently; results are collected and combined.
 */
async function fetchLiveContext(prompt) {
  const parts    = [];
  const lowerP   = prompt.toLowerCase();

  // ── Detect asset type hints ───────────────────────────────────────────────
  const isMF      = /mutual\s*fund|nav|flexi\s*cap|bluechip|sip|amfi|growth\s*fund/i.test(prompt);
  const isIndian  = /nse|bse|nifty|sensex|india|\.ns\b|\.bo\b|₹|inr|hdfc|reliance|tata|infosys|wipro/i.test(prompt);
  const isCrypto  = /bitcoin|btc|ethereum|eth|crypto|usdt|binance|defi/i.test(prompt);

  // ── Run all fetches concurrently ──────────────────────────────────────────
  const ticker = extractTicker(prompt);

  const [yfSearchRes, yfV7Res, yfV8Res, nseRes, amfiRes, ddgRes] = await Promise.allSettled([

    // 1. Yahoo Finance Search
    fetch(
      'https://query1.finance.yahoo.com/v1/finance/search'
        + '?q=' + encodeURIComponent(prompt.slice(0, 100))
        + '&quotesCount=5&newsCount=5&enableFuzzyQuery=false&lang=en-US',
      {
        headers: { 'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)', 'Accept': 'application/json' },
        signal: AbortSignal.timeout(5000),
      }
    ).then(r => r.ok ? r.json() : null).catch(() => null),

    // 2. Yahoo Finance Quote v7 (for the extracted ticker)
    (ticker && !isMF) ? fetchYFQuoteV7(
      isIndian && !ticker.includes('.') ? ticker + '.NS' : ticker
    ) : Promise.resolve(null),

    // 3. Yahoo Finance Chart v8 (fallback price)
    (ticker && !isMF) ? fetchYFQuote(
      isIndian && !ticker.includes('.') ? ticker + '.NS' : ticker
    ) : Promise.resolve(null),

    // 4. NSE India (Indian equities/ETFs only)
    (isIndian && !isMF && !isCrypto) ? fetchNSEQuote(ticker) : Promise.resolve(null),

    // 5. AMFI NAV (mutual funds only)
    isMF ? fetchAMFINav(prompt.slice(0, 60)) : Promise.resolve(null),

    // 6. DuckDuckGo Instant Answer
    fetch(
      'https://api.duckduckgo.com/?q='
        + encodeURIComponent(prompt.slice(0, 120) + ' stock price')
        + '&format=json&no_html=1&skip_disambig=1&no_redirect=1',
      {
        headers: { 'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)' },
        signal: AbortSignal.timeout(4000),
      }
    ).then(r => r.ok ? r.json() : null).catch(() => null),
  ]);

  // ── Process Yahoo Finance Search ──────────────────────────────────────────
  try {
    const yfData = yfSearchRes.status === 'fulfilled' ? yfSearchRes.value : null;
    if (yfData) {
      const quotes = (yfData.quotes || []).slice(0, 5).filter(q => q.symbol)
        .map(q => `${q.longname || q.shortname || q.symbol} (${q.symbol}, ${q.typeDisp || q.quoteType || ''})`)
        .filter(Boolean);
      const news = (yfData.news || []).slice(0, 5).filter(n => n.title)
        .map(n => `• ${n.title}${n.publisher ? ' — ' + n.publisher : ''}${n.providerPublishTime ? ' [' + new Date(n.providerPublishTime * 1000).toISOString().split('T')[0] + ']' : ''}`);
      if (quotes.length) parts.push('**Identified instruments:** ' + quotes.join(' | '));
      if (news.length)   parts.push('**Recent news headlines:**\n' + news.join('\n'));
    }
  } catch { /* non-fatal */ }

  // ── Process live price (cascade: v7 → v8 → NSE) ──────────────────────────
  const priceLines = [];

  const v7 = yfV7Res.status === 'fulfilled' ? yfV7Res.value : null;
  const v8 = yfV8Res.status === 'fulfilled' ? yfV8Res.value : null;
  const nse = nseRes.status === 'fulfilled' ? nseRes.value : null;
  const amfi = amfiRes.status === 'fulfilled' ? amfiRes.value : null;

  if (v7)   priceLines.push(v7);
  else if (v8)   priceLines.push(v8);   // v8 fallback only if v7 failed
  if (nse)  priceLines.push(nse);       // NSE adds authoritative domestic data
  if (amfi) priceLines.push(amfi);      // MF NAV from AMFI

  if (priceLines.length) {
    parts.push('**Live market data (auto-fetched):**\n' + priceLines.join('\n'));
  }

  // ── Process DuckDuckGo ────────────────────────────────────────────────────
  try {
    const ddg = ddgRes.status === 'fulfilled' ? ddgRes.value : null;
    if (ddg) {
      const abstract = ddg.AbstractText || ddg.Answer || '';
      if (abstract && abstract.length > 40) {
        parts.push('**Context:** ' + abstract.slice(0, 400));
      }
    }
  } catch { /* non-fatal */ }

  // ── Assemble context block ────────────────────────────────────────────────
  const dataNote = priceLines.length
    ? `(${priceLines.length} live price source${priceLines.length > 1 ? 's' : ''} fetched)`
    : '(price data unavailable — use knowledge cutoff)';

  return parts.length
    ? `---\n**Live market context ${dataNote}:**\n` + parts.join('\n\n') + '\n---\n\n'
    : '';
}

// ═══════════════════════════════════════════════════════════════════════════════
// STEP B — PROVIDER CALL HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

/** Groq — Llama 3.3 70B (OpenAI-compatible) */
async function callGroq(messages, env, maxTokens) {
  if (!env.GROQ_API_KEY) return null;
  try {
    const res = await fetch(GROQ_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${env.GROQ_API_KEY}`,
      },
      body: JSON.stringify({
        model:       GROQ_MODEL,
        messages,
        max_tokens:  maxTokens || MAX_TOKENS,
        temperature: TEMPERATURE,
        stream:      false,
      }),
      signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) { console.warn('Groq error', res.status, (await res.text()).slice(0, 200)); return null; }
    const data = await res.json();
    const text = data.choices?.[0]?.message?.content?.trim();
    return (text && text.length > 20) ? text : null;
  } catch (e) { console.warn('Groq fetch failed:', e.message); return null; }
}

/** Google Gemini — converts the FULL chat history into a combined text prompt
 *  so follow-up questions retain context across turns. */
async function callGemini(messages, env, maxTokens) {
  if (!env.GEMINI_API_KEY) return null;
  try {
    const sysContent = messages.find(m => m.role === 'system')?.content || '';
    // Flatten ALL conversation turns (not just the first user message)
    const turns = messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => (m.role === 'user' ? 'User' : 'Assistant') + ': ' + m.content)
      .join('\n\n');
    const combined = sysContent ? `${sysContent}\n\n${turns}\n\nAssistant:` : `${turns}\n\nAssistant:`;

    const url = `${GEMINI_BASE}${GEMINI_MODEL}:generateContent?key=${env.GEMINI_API_KEY}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: combined }] }],
        generationConfig: {
          maxOutputTokens: maxTokens || MAX_TOKENS,
          temperature:     TEMPERATURE,
        },
      }),
      signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) { console.warn('Gemini error', res.status, (await res.text()).slice(0, 200)); return null; }
    const data = await res.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text?.trim();
    return (text && text.length > 20) ? text : null;
  } catch (e) { console.warn('Gemini fetch failed:', e.message); return null; }
}

/** OpenAI — gpt-4o-mini (OpenAI-compatible) */
async function callOpenAI(messages, env, maxTokens) {
  if (!env.OPENAI_API_KEY) return null;
  try {
    const res = await fetch(OPENAI_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model:       OPENAI_MODEL,
        messages,
        max_tokens:  maxTokens || MAX_TOKENS,
        temperature: TEMPERATURE,
        stream:      false,
      }),
      signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) { console.warn('OpenAI error', res.status, (await res.text()).slice(0, 200)); return null; }
    const data = await res.json();
    const text = data.choices?.[0]?.message?.content?.trim();
    return (text && text.length > 20) ? text : null;
  } catch (e) { console.warn('OpenAI fetch failed:', e.message); return null; }
}

/** DeepSeek — deepseek-chat (OpenAI-compatible) */
async function callDeepSeek(messages, env, maxTokens) {
  if (!env.DEEPSEEK_API_KEY) return null;
  try {
    const res = await fetch(DEEPSEEK_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${env.DEEPSEEK_API_KEY}`,
      },
      body: JSON.stringify({
        model:       DEEPSEEK_MODEL,
        messages,
        max_tokens:  maxTokens || MAX_TOKENS,
        temperature: TEMPERATURE,
        stream:      false,
      }),
      signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) { console.warn('DeepSeek error', res.status, (await res.text()).slice(0, 200)); return null; }
    const data = await res.json();
    const text = data.choices?.[0]?.message?.content?.trim();
    return (text && text.length > 20) ? text : null;
  } catch (e) { console.warn('DeepSeek fetch failed:', e.message); return null; }
}

/** Pollinations — free, no key required (emergency last resort) */
async function callPollinations(messages) {
  // 'openai-large' was deprecated by Pollinations in 2026.
  // Try the current models in priority order — first one that responds wins.
  const MODEL_FALLBACKS = ['openai-fast', 'openai', 'gpt-oss', 'mistral'];
  const sysShort = `Financial Market Assistant. ${new Date().toDateString()}. Use Markdown.`;
  // Pass the FULL history so follow-up questions retain context.
  const turns = messages.filter(m => m.role === 'user' || m.role === 'assistant');
  if (!turns.length) return null;
  const apiMessages = [{ role: 'system', content: sysShort }, ...turns];

  for (const model of MODEL_FALLBACKS) {
    try {
      const res = await fetch('https://text.pollinations.ai/openai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          messages: apiMessages,
          stream:  false,
          private: true,
        }),
        signal: AbortSignal.timeout(45000),
      });
      if (!res.ok) {
        console.warn(`Pollinations ${model}: HTTP ${res.status}`);
        continue; // try next model
      }
      const data = await res.json();
      const text = data?.choices?.[0]?.message?.content?.trim();
      if (text && text.length > 20) {
        console.log(`Pollinations OK via ${model} (${text.length} chars)`);
        return text;
      }
    } catch (e) {
      console.warn(`Pollinations ${model} threw:`, e.message);
    }
  }
  return null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// STEP B — AI GENERATION WITH DYNAMIC PROVIDER ROUTING
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Route to the requested provider first, then cascade through all available
 * providers until one succeeds.
 *
 * @param {string} prompt       - User's question (with live context prepended)
 * @param {object} env          - Cloudflare Worker environment bindings
 * @param {string} providerHint - Preferred provider: 'groq'|'gemini'|'openai'|'deepseek'|''
 */
/**
 * Main AI query handler.
 *
 * @param {string}        prompt        - User prompt (may include flattened history)
 * @param {object}        env           - Cloudflare env bindings
 * @param {string}        providerHint  - Preferred provider key
 * @param {Array|null}    historyMsgs   - Optional [{role,content}] conversation history
 *                                        from the frontend's _rbChatHistory. When provided,
 *                                        the full conversation is forwarded to the AI instead
 *                                        of just the latest prompt — enabling multi-turn memory.
 */
async function handleQuery(prompt, env, providerHint, historyMsgs) {
  const today = new Date().toDateString();

  // ── Hybrid report mode ───────────────────────────────────────────────────────
  // Worker builds the complete 10-tab JSON skeleton from financial APIs (pure JS).
  // AI is called ONLY for ~60 prose/narrative fields (~2000 tokens vs 15000+).
  // Sentinel string is injected by buildQuery() in index.html.
  if (prompt.includes('OUTPUT FORMAT — STRICT JSON REQUIRED')) {
    return await hybridReport(prompt, env, providerHint);
  }

  // ── Chat mode: lightweight live context + AI cascade ────────────────────────
  const ctx = await fetchLiveContext(prompt);
  let messages;
  if (historyMsgs && historyMsgs.length > 0) {
    const withCtx = historyMsgs.map((m, i) =>
      (i === historyMsgs.length - 1 && m.role === 'user' && ctx)
        ? { role: 'user', content: ctx + m.content }
        : m
    );
    messages = [{ role: 'system', content: SYSTEM_PROMPT(today) }, ...withCtx];
  } else {
    messages = [
      { role: 'system', content: SYSTEM_PROMPT(today) },
      { role: 'user',   content: ctx + prompt },
    ];
  }

  const provider = (providerHint || '').toLowerCase();
  if (provider === 'groq')     { const t = await callGroq(messages, env);     if (t) return t; }
  if (provider === 'gemini')   { const t = await callGemini(messages, env);   if (t) return t; }
  if (provider === 'openai')   { const t = await callOpenAI(messages, env);   if (t) return t; }
  if (provider === 'deepseek') { const t = await callDeepSeek(messages, env); if (t) return t; }

  // Track which providers we tried so logs show the failure cascade
  const tried = [];
  const groq     = await callGroq(messages, env);     tried.push('groq:'    +(groq?'ok':'fail')); if (groq)     return groq;
  const gemini   = await callGemini(messages, env);   tried.push('gemini:'  +(gemini?'ok':'fail'));if (gemini)   return gemini;
  const openai   = await callOpenAI(messages, env);   tried.push('openai:'  +(openai?'ok':'fail'));if (openai)   return openai;
  const deepseek = await callDeepSeek(messages, env); tried.push('deepseek:'+(deepseek?'ok':'fail'));if (deepseek) return deepseek;
  const poll     = await callPollinations(messages);  tried.push('pollinations:'+(poll?'ok':'fail'));if (poll) return poll;

  console.error('[handleQuery] all providers failed:', tried.join(' | '));
  throw new Error('All AI providers unavailable: ' + tried.join(', '));
}

// ═══════════════════════════════════════════════════════════════════════════════
// HYBRID REPORT ENGINE — Global Native JSON Architecture (v2)
// ═══════════════════════════════════════════════════════════════════════════════
//
// Zero-AI-for-numbers: Worker builds 10-tab JSON skeleton via pure JS mapping.
// AI is called ONLY for ~60 prose/narrative text fields (~2000 tokens vs 15000+).
//
// Global market routing (Yahoo Finance v10/quoteSummary — no API key needed):
//   US/NASDAQ/NYSE  → AAPL, MSFT       India NSE  → RELIANCE.NS, HDFCBANK.NS
//   Japan JPX       → 7203.T (Toyota)  UK LSE     → BP.L, AZN.L
//   Germany Xetra   → BMW.DE, SAP.DE   France     → MC.PA, TTE.PA
//   Australia ASX   → BHP.AX, CBA.AX   HK HKEX   → 0700.HK (Tencent)
//   Crypto          → BTC-USD, ETH-USD  Indices   → ^GSPC, ^NSEI, ^BSESN

// ─── Global market suffix routing ────────────────────────────────────────────
const MARKET_SUFFIX = {
  'india':'.NS','nse':'.NS','bse':'.NS','nse india':'.NS','bse india':'.NS',
  'japan':'.T','jpx':'.T','tokyo':'.T','tokyo stock exchange':'.T',
  'uk':'.L','london':'.L','lse':'.L','united kingdom':'.L',
  'germany':'.DE','frankfurt':'.DE','xetra':'.DE',
  'france':'.PA','paris':'.PA','euronext':'.PA',
  'australia':'.AX','asx':'.AX',
  'hong kong':'.HK','hkex':'.HK',
  'canada':'.TO','tsx':'.TO',
  'singapore':'.SI','sgx':'.SI',
  'us':'','usa':'','nasdaq':'','nyse':'','united states':'','america':'',
};

// ─── Global company name → Yahoo Finance ticker ───────────────────────────────
const GLOBAL_TICKERS = {
  // US mega/large cap
  'apple':'AAPL','microsoft':'MSFT','google':'GOOGL','alphabet':'GOOGL',
  'amazon':'AMZN','meta':'META','facebook':'META','tesla':'TSLA','nvidia':'NVDA',
  'berkshire hathaway':'BRK-B','berkshire':'BRK-B','jpmorgan':'JPM','jp morgan':'JPM',
  'johnson & johnson':'JNJ','visa':'V','mastercard':'MA','unitedhealth':'UNH',
  'exxon':'XOM','walmart':'WMT','procter & gamble':'PG','procter':'PG','chevron':'CVX',
  'abbvie':'ABBV','costco':'COST','oracle':'ORCL','salesforce':'CRM','adobe':'ADBE',
  'netflix':'NFLX','amd':'AMD','intel':'INTC','qualcomm':'QCOM','broadcom':'AVGO',
  'micron':'MU','boeing':'BA','caterpillar':'CAT','pfizer':'PFE','moderna':'MRNA',
  'merck':'MRK','eli lilly':'LLY','lilly':'LLY','bank of america':'BAC','citigroup':'C',
  'wells fargo':'WFC','goldman sachs':'GS','morgan stanley':'MS','paypal':'PYPL',
  'american express':'AXP','blackrock':'BLK',
  // Japan
  'toyota':'7203.T','sony':'6758.T','softbank':'9984.T','nintendo':'7974.T',
  'honda':'7267.T','mitsubishi':'8058.T','keyence':'6861.T',
  'fast retailing':'9983.T','uniqlo':'9983.T','recruit':'6098.T',
  'shin-etsu':'4063.T','fanuc':'6954.T','tokyo electron':'8035.T',
  'kddi':'9433.T','ntt':'9432.T','mufg':'8306.T','mizuho':'8411.T',
  'smfg':'8316.T','takeda':'4502.T','panasonic':'6752.T','hitachi':'6501.T',
  // UK
  'bp':'BP.L','shell':'SHEL.L','astrazeneca':'AZN.L','gsk':'GSK.L',
  'unilever':'ULVR.L','rio tinto':'RIO.L','glencore':'GLEN.L',
  'lloyds':'LLOY.L','barclays':'BARC.L','vodafone':'VOD.L',
  'bt group':'BT-A.L','hsbc':'HSBA.L','diageo':'DGE.L',
  // Germany
  'sap':'SAP.DE','siemens':'SIE.DE','bmw':'BMW.DE','mercedes':'MBG.DE',
  'volkswagen':'VOW3.DE','basf':'BAS.DE','bayer':'BAYN.DE','adidas':'ADS.DE',
  'allianz':'ALV.DE','deutsche bank':'DBK.DE','infineon':'IFX.DE',
  // France
  'lvmh':'MC.PA','totalenergies':'TTE.PA','sanofi':'SAN.PA',
  'airbus':'AIR.PA','loreal':'OR.PA','bnp paribas':'BNP.PA',
  // Australia
  'bhp':'BHP.AX','cba':'CBA.AX','commonwealth bank':'CBA.AX',
  'westpac':'WBC.AX','anz':'ANZ.AX','nab':'NAB.AX',
  'csl':'CSL.AX','macquarie':'MQG.AX','woolworths':'WOW.AX',
  // Hong Kong
  'tencent':'0700.HK','meituan':'3690.HK','aia':'1299.HK',
  'ping an':'2318.HK','cnooc':'0883.HK','alibaba hk':'9988.HK',
  // India NSE
  'reliance':'RELIANCE.NS','reliance industries':'RELIANCE.NS',
  'tcs':'TCS.NS','tata consultancy':'TCS.NS',
  'infosys':'INFY.NS','wipro':'WIPRO.NS',
  'hcl tech':'HCLTECH.NS','hcl':'HCLTECH.NS','tech mahindra':'TECHM.NS',
  'hdfc bank':'HDFCBANK.NS','hdfcbank':'HDFCBANK.NS',
  'icici bank':'ICICIBANK.NS','icicibank':'ICICIBANK.NS',
  'state bank of india':'SBIN.NS','sbi':'SBIN.NS',
  'kotak bank':'KOTAKBANK.NS','kotak':'KOTAKBANK.NS',
  'axis bank':'AXISBANK.NS','axisbank':'AXISBANK.NS',
  'yes bank':'YESBANK.NS','indusind':'INDUSINDBK.NS',
  'hul':'HINDUNILVR.NS','hindustan unilever':'HINDUNILVR.NS',
  'itc':'ITC.NS','bharti airtel':'BHARTIARTL.NS','airtel':'BHARTIARTL.NS',
  'l&t':'LT.NS','larsen':'LT.NS','larsen & toubro':'LT.NS',
  'maruti':'MARUTI.NS','maruti suzuki':'MARUTI.NS',
  'bajaj finance':'BAJFINANCE.NS','bajaj finserv':'BAJAJFINSV.NS',
  'asian paints':'ASIANPAINT.NS','titan':'TITAN.NS','nestle india':'NESTLEIND.NS',
  'adani ports':'ADANIPORTS.NS','adani enterprises':'ADANIENT.NS',
  'adani green':'ADANIGREEN.NS','sun pharma':'SUNPHARMA.NS',
  'dr reddy':'DRREDDY.NS','cipla':'CIPLA.NS','divis':'DIVISLAB.NS',
  'ongc':'ONGC.NS','ntpc':'NTPC.NS','power grid':'POWERGRID.NS',
  'coal india':'COALINDIA.NS','tata motors':'TATAMOTORS.NS',
  'm&m':'M&M.NS','mahindra':'M&M.NS','tata steel':'TATASTEEL.NS',
  'jsw steel':'JSWSTEEL.NS','hindalco':'HINDALCO.NS','zomato':'ZOMATO.NS',
  'paytm':'PAYTM.NS','dmart':'DMART.NS','pidilite':'PIDILITIND.NS',
  'mrf':'MRF.NS','apollo hospitals':'APOLLOHOSP.NS',
  // India indices & ETFs
  'nifty 50':'^NSEI','nifty':'^NSEI','sensex':'^BSESN','bank nifty':'^NSEBANK',
  'niftybees':'NIFTYBEES.NS','juniorbees':'JUNIORBEES.NS','bankbees':'BANKBEES.NS',
  // Global indices
  's&p 500':'^GSPC','sp500':'^GSPC','dow jones':'^DJI','dow':'^DJI',
  'nasdaq composite':'^IXIC','nikkei':'^N225','hang seng':'^HSI',
  'ftse':'^FTSE','dax':'^GDAXI','cac 40':'^FCHI',
  // US ETFs
  'spy':'SPY','qqq':'QQQ','voo':'VOO','ivv':'IVV','vti':'VTI',
  'efa':'EFA','gld':'GLD','slv':'SLV',
  // Crypto
  'bitcoin':'BTC-USD','btc':'BTC-USD','ethereum':'ETH-USD','eth':'ETH-USD',
  'solana':'SOL-USD','sol':'SOL-USD','bnb':'BNB-USD','xrp':'XRP-USD',
  'cardano':'ADA-USD','dogecoin':'DOGE-USD','doge':'DOGE-USD',
};

// PLACEHOLDER — old NSE_TICKERS replaced; left here so nothing below breaks
const NSE_TICKERS = {
  // Banks
  'hdfc bank': 'HDFCBANK', 'hdfcbank': 'HDFCBANK',
  'icici bank': 'ICICIBANK', 'icicibank': 'ICICIBANK',
  'axis bank': 'AXISBANK', 'axisbank': 'AXISBANK',
  'state bank of india': 'SBIN', 'sbi': 'SBIN',
  'kotak mahindra bank': 'KOTAKBANK', 'kotak bank': 'KOTAKBANK',
  'indusind bank': 'INDUSINDBK',
  'punjab national bank': 'PNB', 'pnb': 'PNB',
  'bank of baroda': 'BANKBARODA',
  'canara bank': 'CANBK',
  'yes bank': 'YESBANK',
  // IT
  'tcs': 'TCS', 'tata consultancy': 'TCS',
  'infosys': 'INFY', 'infy': 'INFY',
  'wipro': 'WIPRO',
  'hcl technologies': 'HCLTECH', 'hcl tech': 'HCLTECH',
  'tech mahindra': 'TECHM',
  'mphasis': 'MPHASIS',
  'ltimindtree': 'LTIM',
  'persistent systems': 'PERSISTENT',
  // Large cap
  'reliance industries': 'RELIANCE', 'reliance': 'RELIANCE',
  'larsen & toubro': 'LT', 'larsen toubro': 'LT', 'l&t': 'LT', 'lt': 'LT',
  'bajaj finance': 'BAJFINANCE',
  'bajaj finserv': 'BAJAJFINSV',
  'maruti suzuki': 'MARUTI', 'maruti': 'MARUTI',
  'sun pharmaceutical': 'SUNPHARMA', 'sun pharma': 'SUNPHARMA',
  'titan company': 'TITAN', 'titan': 'TITAN',
  'bharti airtel': 'BHARTIARTL', 'airtel': 'BHARTIARTL',
  'itc': 'ITC',
  'nestle india': 'NESTLEIND', 'nestle': 'NESTLEIND',
  'asian paints': 'ASIANPAINT',
  'ultratech cement': 'ULTRACEMCO',
  'divis laboratories': 'DIVISLAB', 'divis labs': 'DIVISLAB',
  'dr reddys': 'DRREDDY', "dr. reddy's": 'DRREDDY',
  'cipla': 'CIPLA',
  'power grid': 'POWERGRID', 'power grid corporation': 'POWERGRID',
  'ntpc': 'NTPC',
  'ongc': 'ONGC',
  'coal india': 'COALINDIA',
  'jsw steel': 'JSWSTEEL',
  'tata steel': 'TATASTEEL',
  'hindalco': 'HINDALCO',
  'vedanta': 'VEDL',
  'adani enterprises': 'ADANIENT', 'adani ports': 'ADANIPORTS',
  'adani green': 'ADANIGREEN', 'adani power': 'ADANIPOWER',
  'grasim': 'GRASIM',
  'eicher motors': 'EICHERMOT',
  'hero motocorp': 'HEROMOTOCO',
  'bajaj auto': 'BAJAJ-AUTO',
  'tata motors': 'TATAMOTORS',
  'm&m': 'M&M', 'mahindra': 'M&M', 'mahindra and mahindra': 'M&M',
  'apollo hospitals': 'APOLLOHOSP',
  'dmart': 'DMART', 'avenue supermarts': 'DMART',
  'zomato': 'ZOMATO',
  'paytm': 'PAYTM', 'one97 communications': 'PAYTM',
  'nykaa': 'NYKAA', 'fsh nykaa': 'NYKAA',
  'policybazaar': 'POLICYBZR',
  // Indices
  'nifty50': 'NIFTY50', 'nifty 50': 'NIFTY50',
  'sensex': 'SENSEX',
  // ETFs
  'niftybees': 'NIFTYBEES', 'nifty bees': 'NIFTYBEES',
  'nippon india etf nifty bees': 'NIFTYBEES', 'nippon nifty bees': 'NIFTYBEES',
  'bankbees': 'BANKBEES', 'bank bees': 'BANKBEES',
  'goldbees': 'GOLDBEES', 'gold bees': 'GOLDBEES',
  'liquidbees': 'LIQUIDBEES',
  'juniorbees': 'JUNIORBEES', 'junior bees': 'JUNIORBEES',
  'icicib22': 'ICICIB22',
  'mafang': 'MAFANG',
};

// ─── NEW HYBRID ENGINE FUNCTIONS (replace old pre-fetch functions below) ──────

/** Resolve asset name + market label → Yahoo Finance compatible symbol. */
async function resolveSymbolGlobal(assetName, market) {
  const name = (assetName || '').trim();
  const mkt  = (market || '').toLowerCase().trim();
  // 1. Already looks like a ticker (uppercase, optional exchange suffix)
  if (/^[A-Z0-9\-\^]{2,10}(\.[A-Z]{1,3})?$/.test(name)) {
    const sfx = MARKET_SUFFIX[mkt];
    if (sfx && sfx !== '' && !name.includes('.') && !name.startsWith('^')) return name + sfx;
    return name;
  }
  // 2. Lookup table (exact then prefix/partial)
  const lower = name.toLowerCase();
  if (GLOBAL_TICKERS[lower]) return GLOBAL_TICKERS[lower];
  for (const [k, v] of Object.entries(GLOBAL_TICKERS)) {
    if (lower === k || lower.startsWith(k) || k.startsWith(lower)) return v;
  }
  // 3. Market-aware Yahoo Finance search fallback
  const q = (mkt && !['us','usa','nasdaq','nyse','united states','america'].includes(mkt))
    ? `${name} ${market}` : name;
  try {
    const r = await fetch(
      `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&quotesCount=3&newsCount=0&lang=en-US`,
      { headers:{'User-Agent':'Mozilla/5.0','Accept':'application/json'}, signal:AbortSignal.timeout(5000) }
    );
    if (r.ok) {
      const d = await r.json();
      const sfx = MARKET_SUFFIX[mkt] || '';
      const hit = (d?.quotes||[]).find(q => sfx ? q.symbol?.endsWith(sfx) : !q.symbol?.includes('.'));
      if (hit?.symbol) return hit.symbol;
      if (d?.quotes?.[0]?.symbol) return d.quotes[0].symbol;
    }
  } catch { /* non-fatal */ }
  // 4. Last resort: uppercase name + suffix
  return name.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,10) + (MARKET_SUFFIX[mkt]||'');
}

/** Yahoo Finance v10/quoteSummary — 12 modules in one call. Global coverage. */
async function fetchYFSummaryFull(symbol) {
  const mods = 'price,summaryProfile,financialData,defaultKeyStatistics,earningsTrend,'
    + 'institutionOwnership,fundOwnership,majorHoldersBreakdown,'
    + 'incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory,summaryDetail';
  try {
    const r = await fetch(
      `https://query1.finance.yahoo.com/v10/finance/quoteSummary/${encodeURIComponent(symbol)}?modules=${encodeURIComponent(mods)}&corsDomain=finance.yahoo.com`,
      { headers:{
          'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124',
          'Accept':'application/json','Accept-Language':'en-US,en;q=0.9',
          'Referer':'https://finance.yahoo.com/',
        }, signal:AbortSignal.timeout(9000) }
    );
    if (!r.ok) { console.warn(`[YFv10] ${symbol} → HTTP ${r.status}`); return null; }
    const d = await r.json();
    return d?.quoteSummary?.result?.[0] || null;
  } catch (e) { console.warn(`[YFv10] ${symbol}:`, e.message); return null; }
}

/** Yahoo Finance v8/chart — OHLCV history for any global symbol. */
async function fetchYFChartHistory(symbol, range, interval) {
  try {
    const r = await fetch(
      `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}&includePrePost=false`,
      { headers:{'User-Agent':'Mozilla/5.0','Accept':'application/json','Referer':'https://finance.yahoo.com/'},
        signal:AbortSignal.timeout(9000) }
    );
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

/** Extract adjusted close prices from v8/chart response. */
function extractCloses(chartJson) {
  const r = chartJson?.chart?.result?.[0];
  if (!r) return [];
  const adj = r.indicators?.adjclose?.[0]?.adjclose;
  const reg = r.indicators?.quote?.[0]?.close;
  return ((adj?.length ? adj : reg) || []).filter(v => v !== null && v !== undefined && isFinite(v));
}

/** Yahoo Finance v1/search — recent news headlines (global). */
async function fetchYFNewsHeadlines(query) {
  try {
    const r = await fetch(
      `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(query)}&quotesCount=0&newsCount=8&lang=en-US`,
      { headers:{'User-Agent':'Mozilla/5.0','Accept':'application/json'}, signal:AbortSignal.timeout(6000) }
    );
    if (!r.ok) return [];
    const d = await r.json();
    return (d?.news||[]).slice(0,6).map(n => ({
      date: n.providerPublishTime
        ? new Date(n.providerPublishTime*1000).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})
        : 'Recent',
      title: n.title||'', publisher: n.publisher||'',
    }));
  } catch { return []; }
}

/** Google News RSS — fallback for news when YF returns nothing. */
async function fetchGoogleNewsRSS(query) {
  try {
    const r = await fetch(
      `https://news.google.com/rss/search?q=${encodeURIComponent(query)}&hl=en-IN&gl=IN&ceid=IN:en`,
      { headers:{'User-Agent':'Mozilla/5.0'}, signal:AbortSignal.timeout(5000) }
    );
    if (!r.ok) return [];
    const text = await r.text();
    return [...text.matchAll(/<title><!\[CDATA\[(.+?)\]\]><\/title>/g)]
      .slice(1,7)
      .map(m => ({ date:'Recent', title:m[1].replace(/\s*-\s*[^-]+$/, '').trim(), publisher:'' }));
  } catch { return []; }
}

// ─── Technical indicator calculators — pure JavaScript ────────────────────────
const _avg = arr => arr.reduce((a,b)=>a+b,0)/arr.length;
function _sma(c,n) { return c.length>=n ? _avg(c.slice(-n)) : null; }
function _ema(c,p) {
  if (c.length<p) return null;
  const k=2/(p+1); let e=_avg(c.slice(0,p));
  for (let i=p;i<c.length;i++) e=c[i]*k+e*(1-k);
  return e;
}
function _rsi(c,p=14) {
  if (c.length<p+2) return null;
  const d=[]; for(let i=1;i<c.length;i++) d.push(c[i]-c[i-1]);
  let g=0,l=0;
  for(let i=0;i<p;i++){if(d[i]>0)g+=d[i];else l+=Math.abs(d[i]);}
  g/=p; l/=p;
  for(let i=p;i<d.length;i++){g=(g*(p-1)+Math.max(0,d[i]))/p;l=(l*(p-1)+Math.abs(Math.min(0,d[i])))/p;}
  return l===0?100:100-100/(1+g/l);
}
function _macd(c) { const e12=_ema(c,12),e26=_ema(c,26); return (e12&&e26)?e12-e26:null; }
function _bb(c,p=20) {
  if(c.length<p) return null;
  const s=c.slice(-p),m=_avg(s),std=Math.sqrt(s.reduce((a,v)=>a+(v-m)**2,0)/p);
  return {upper:m+2*std,lower:m-2*std,mid:m};
}
function _cagr(c,yrs) {
  const n=c.length,pts=Math.min(Math.round(yrs*252),n-1);
  if(pts<=0||!c[n-1]||!c[n-1-pts]) return null;
  return ((c[n-1]/c[n-1-pts])**(1/yrs)-1)*100;
}
function _cagrMo(c,yrs) {
  const n=c.length,pts=Math.min(Math.round(yrs*12),n-1);
  if(pts<=0||!c[n-1]||!c[n-1-pts]) return null;
  return ((c[n-1]/c[n-1-pts])**(1/yrs)-1)*100;
}
function calcTech(daily, monthly) {
  const n=daily.length, last=daily[n-1]||0;
  const sma20=_sma(daily,20),sma50=_sma(daily,50),sma100=_sma(daily,100),sma200=_sma(daily,200);
  const ema5=_ema(daily,5),ema10=_ema(daily,10);
  const rsi=_rsi(daily,14),macd=_macd(daily),bb=_bb(daily,20);
  const recent=daily.slice(-63);
  const s1=recent.length?Math.min(...recent):null, r1=recent.length?Math.max(...recent):null;
  const s2=n>=252?Math.min(...daily.slice(-252)):null, r2=n>=252?Math.max(...daily.slice(-252)):null;
  const drets=[]; for(let i=1;i<n;i++){if(daily[i-1]>0)drets.push(daily[i]/daily[i-1]-1);}
  const vol=drets.length>1?Math.sqrt(drets.reduce((a,v)=>a+(v-_avg(drets))**2,0)/drets.length)*Math.sqrt(252)*100:null;
  const cross=(sma50&&sma200)?(sma50>sma200?'Golden Cross (Bullish)':'Death Cross (Bearish)'):'N/A';
  const pct=(ma)=>(!ma||!last)?'N/A':((last-ma)/ma*100).toFixed(2)+'%';
  const sig=(ma)=>(!ma||!last)?'N/A':(last>ma?'Buy':'Sell');
  return {
    sma20,sma50,sma100,sma200,ema5,ema10,rsi,macd,bb,vol,cross,s1,r1,s2,r2,pct,sig,last,
    ret1y:_cagr(daily,1),
    ret6m:n>=126?((last/daily[n-126]-1)*100):null,
    ret3m:n>=63?((last/daily[n-63]-1)*100):null,
    ret1m:n>=21?((last/daily[n-21]-1)*100):null,
    ret3y:_cagrMo(monthly,3), ret5y:_cagrMo(monthly,5),
  };
}

// ─── Number formatters ────────────────────────────────────────────────────────
const NDA = 'No Data Available';
const _n = v => v===null||v===undefined||!isFinite(v);
const _raw = (obj,key) => { const v=obj?.[key]; return (v&&typeof v==='object'&&'raw' in v)?v.raw:v; };
function fC(v,cur,dp=2){if(_n(v))return NDA;const s=cur==='INR'?'₹':cur==='JPY'?'¥':cur==='GBP'?'£':cur==='EUR'?'€':'$';return s+Number(v).toFixed(dp);}
function fL(v,cur){if(_n(v))return NDA;const s=cur==='INR'?'₹':cur==='JPY'?'¥':cur==='GBP'?'£':cur==='EUR'?'€':'$';if(cur==='INR'){if(v>=1e12)return s+(v/1e12).toFixed(2)+' Lakh Cr';if(v>=1e7)return s+(v/1e7).toFixed(2)+' Cr';return s+v.toFixed(0);}if(v>=1e12)return s+(v/1e12).toFixed(2)+'T';if(v>=1e9)return s+(v/1e9).toFixed(2)+'B';if(v>=1e6)return s+(v/1e6).toFixed(2)+'M';return s+v.toFixed(0);}
function fP(v,dp=2){if(_n(v))return NDA;return(Number(v)*(Math.abs(v)<1?100:1)).toFixed(dp)+'%';}
function fR(v,dp=2){if(_n(v))return NDA;return Number(v).toFixed(dp)+'%';}
function fN(v,dp=2){if(_n(v))return NDA;return Number(v).toFixed(dp);}

// ─── 10-Tab JSON skeleton builder — pure JS, zero AI for numeric fields ────────
function buildStockSkeleton(summary, daily, monthly, news, assetName, market, resident, refLinks, today) {
  const t  = calcTech(daily, monthly);
  const P  = summary?.price                        || {};
  const SP = summary?.summaryProfile               || {};
  const FD = summary?.financialData                || {};
  const KS = summary?.defaultKeyStatistics         || {};
  const SD = summary?.summaryDetail                || {};
  const MH = summary?.majorHoldersBreakdown        || {};
  const IO = (summary?.institutionOwnership?.ownershipList||[]).slice(0,10);
  const FO = (summary?.fundOwnership?.ownershipList       ||[]).slice(0,5);
  const IS = summary?.incomeStatementHistory?.incomeStatementHistory || [];
  const BS = summary?.balanceSheetHistory?.balanceSheetStatements   || [];
  const CF = summary?.cashflowStatementHistory?.cashflowStatements  || [];
  const ET = summary?.earningsTrend?.trend || [];

  const cur = P.currency||'USD';
  const px  = _raw(P,'regularMarketPrice')??t.last;
  const mc  = _raw(P,'marketCap');
  const vol = _raw(P,'regularMarketVolume');
  const chg = _raw(P,'regularMarketChangePercent');
  const w52h= _raw(KS,'fiftyTwoWeekHigh')||_raw(SD,'fiftyTwoWeekHigh');
  const w52l= _raw(KS,'fiftyTwoWeekLow') ||_raw(SD,'fiftyTwoWeekLow');
  const beta= _raw(KS,'beta')||_raw(SD,'beta');
  const pe  = _raw(KS,'trailingPE')||_raw(SD,'trailingPE');
  const fpe = _raw(KS,'forwardPE');
  const pb  = _raw(KS,'priceToBook');
  const eps = _raw(KS,'trailingEps');
  const feps= _raw(KS,'forwardEps');
  const bvps= _raw(KS,'bookValue');
  const peg = _raw(KS,'pegRatio');
  const ev  = _raw(KS,'enterpriseValue');
  const evebitda= _raw(KS,'enterpriseToEbitda');
  const evrev   = _raw(KS,'enterpriseToRevenue');
  const dy  = _raw(KS,'dividendYield')||_raw(SD,'dividendYield')||_raw(SD,'trailingAnnualDividendYield');
  const so  = _raw(KS,'sharesOutstanding');
  const roe = _raw(FD,'returnOnEquity');
  const roa = _raw(FD,'returnOnAssets');
  const de  = _raw(FD,'debtToEquity');
  const fcf = _raw(FD,'freeCashflow');
  const opc = _raw(FD,'operatingCashflow');
  const rev = _raw(FD,'totalRevenue');
  const rg  = _raw(FD,'revenueGrowth');
  const ebi = _raw(FD,'ebitda');
  const opm = _raw(FD,'operatingMargins');
  const npm = _raw(FD,'profitMargins');
  const gm  = _raw(FD,'grossMargins');
  const cr  = _raw(FD,'currentRatio');
  const qr  = _raw(FD,'quickRatio');
  const tc  = _raw(FD,'totalCash');
  const td  = _raw(FD,'totalDebt');
  const rk  = FD.recommendationKey||NDA;
  const rm  = _raw(FD,'recommendationMean');
  const na  = _raw(FD,'numberOfAnalystOpinions');
  const tph = _raw(FD,'targetHighPrice');
  const tpl = _raw(FD,'targetLowPrice');
  const tpm = _raw(FD,'targetMeanPrice');
  const tpd = _raw(FD,'targetMedianPrice');
  const eg  = _raw(FD,'earningsGrowth');

  const is0=IS[0]||{},is1=IS[1]||{};
  const rev0=_raw(is0,'totalRevenue')||rev, rev1=_raw(is1,'totalRevenue');
  const ni0=_raw(is0,'netIncome'), ebt0=_raw(is0,'ebit')||ebi;
  const cf0=CF[0]||{};
  const opCF=_raw(cf0,'totalCashFromOperatingActivities')||opc;
  const capEx=_raw(cf0,'capitalExpenditures');
  const fcfCalc=(opCF&&capEx)?opCF+capEx:fcf;
  const eTCY=ET.find(e=>e.period==='0y')||ET[2]||{};
  const eTNY=ET.find(e=>e.period==='+1y')||ET[3]||{};
  const epsCY=eTCY.earningsEstimate?.avg?.raw, epsNY=eTNY.earningsEstimate?.avg?.raw;
  const revCY=eTCY.revenueEstimate?.avg?.raw,  revNY=eTNY.revenueEstimate?.avg?.raw;
  const egrCY=eTCY.earningsEstimate?.growth?.raw;

  const insPct=_raw(MH,'insidersPercentHeld'), itnPct=_raw(MH,'institutionsPercentHeld');
  const pubPct=(insPct!=null&&itnPct!=null)?Math.max(0,1-(insPct||0)-(itnPct||0)):null;

  const rkLabel={'strongBuy':'Strong Buy','buy':'Buy','hold':'Hold','underperform':'Underperform','sell':'Sell'}[rk]||rk;
  const upside=(tpm&&px)?((tpm/px-1)*100).toFixed(1)+'%':NDA;

  const rsiSig =t.rsi?(t.rsi>70?'Overbought':t.rsi<30?'Oversold':'Neutral'):NDA;
  const macdSig=t.macd?(t.macd>0?'Bullish':'Bearish'):NDA;
  const volScore=t.vol?Math.min(100,Math.max(0,Math.round(100-t.vol))):50;
  const valScore=pe?Math.round(pe<10?85:pe<20?70:pe<30?55:pe<50?35:20):50;
  const momScore=t.ret1y!==null?Math.round(t.ret1y>50?90:t.ret1y>25?75:t.ret1y>10?65:t.ret1y>0?55:t.ret1y>-10?40:30):50;

  const maRow=(ma)=>ma?`${fC(ma,cur)} | ${t.pct(ma)} | ${t.sig(ma)}`:NDA;
  const nwsF =news.slice(0,5).reduce((a,h,i)=>{a[`News ${i+1}`]=`${h.date} | ${h.title}${h.publisher?' — '+h.publisher:''} | __AI__newsSent${i}__AI__ | __AI__newsImpact${i}__AI__`;return a;},{});
  const instF =IO.reduce((a,h,i)=>{a[`Holder ${i+1}`]=`${h.organization||NDA} | ${h.pctHeld?.raw?fP(h.pctHeld.raw):NDA} | ${h.position?.raw?Number(h.position.raw).toLocaleString()+' sh':NDA} | ${h.value?.raw?fL(h.value.raw,cur):NDA}`;return a;},{});
  const mfF   =FO.reduce((a,h,i)=>{a[`MF ${i+1}`]=`${h.organization||NDA} | ${h.pctHeld?.raw?fP(h.pctHeld.raw):NDA} | ${h.position?.raw?Number(h.position.raw).toLocaleString()+' sh':NDA}`;return a;},{});

  return {
    asset: P.longName||P.shortName||assetName, date: today,
    tabs: [
      // ── Tab 1: Overview & Macro ──────────────────────────────────────────────
      { id:1, name:'Overview & Macro', fields:{
        'Company Name':P.longName||P.shortName||assetName,
        'Ticker':P.symbol||assetName, 'Exchange':P.fullExchangeName||P.exchangeName||NDA,
        'Sector':SP.sector||NDA, 'Industry':SP.industry||NDA, 'Country':SP.country||NDA,
        'Headquarters':[SP.city,SP.state,SP.country].filter(Boolean).join(', ')||NDA,
        'Website':SP.website||NDA,
        'Employees':SP.fullTimeEmployees?Number(SP.fullTimeEmployees).toLocaleString():NDA,
        'Currency':cur,
        'Company Background':'__AI__companyBackground__AI__',
        'Core Business Segments':'__AI__coreSegments__AI__',
        'Key Subsidiaries':'__AI__keySubsidiaries__AI__',
        '1Y Return':fR(t.ret1y), '3Y CAGR':fR(t.ret3y), '5Y CAGR':fR(t.ret5y),
        '6M Return':fR(t.ret6m), '3M Return':fR(t.ret3m), '1M Return':fR(t.ret1m),
        'Dividend Yield TTM':dy?fP(dy):NDA,
      }, subsections:[{ title:'Macro & Industry', fields:{
        'TAM (Market Size)':'__AI__tam__AI__',
        'Industry Growth Rate':'__AI__industryGrowth__AI__',
        'Market Position':'__AI__marketPosition__AI__',
        'Regulatory Environment':'__AI__regulatoryEnv__AI__',
        'Tailwind 1':'__AI__tailwind1__AI__',
        'Tailwind 2':'__AI__tailwind2__AI__',
        'Tailwind 3':'__AI__tailwind3__AI__',
        'Headwind 1':'__AI__headwind1__AI__',
        'Headwind 2':'__AI__headwind2__AI__',
        'Headwind 3':'__AI__headwind3__AI__',
      }}]},

      // ── Tab 2: Live Market & Technicals ─────────────────────────────────────
      { id:2, name:'Live Market & Technicals', fields:{
        'Current Price':fC(px,cur),
        'Market Cap':fL(mc,cur),
        '52-Week High':fC(w52h,cur), '52-Week Low':fC(w52l,cur),
        '1D Change %':chg?fR(chg*100):NDA,
        'Volume':vol?Number(vol).toLocaleString():NDA,
        'Beta':fN(beta), 'Dividend Yield TTM':dy?fP(dy):NDA,
        'Annual Volatility':t.vol?fR(t.vol):NDA,
        'RSI (14)':t.rsi?fN(t.rsi):NDA, 'RSI Signal':rsiSig,
        'MACD':t.macd?fN(t.macd):NDA, 'MACD Signal':macdSig,
        'Bollinger Upper':t.bb?fC(t.bb.upper,cur):NDA,
        'Bollinger Mid':t.bb?fC(t.bb.mid,cur):NDA,
        'Bollinger Lower':t.bb?fC(t.bb.lower,cur):NDA,
        'Support S1 (3M)':t.s1?fC(t.s1,cur):NDA, 'Support S2 (1Y)':t.s2?fC(t.s2,cur):NDA,
        'Resistance R1 (3M)':t.r1?fC(t.r1,cur):NDA, 'Resistance R2 (1Y)':t.r2?fC(t.r2,cur):NDA,
        'Golden / Death Cross':t.cross, 'Momentum Score':momScore+'/100',
        'Key Insight':'__AI__keyInsight__AI__',
      }, subsections:[{ title:'Moving Averages', fields:{
        '5d EMA':maRow(t.ema5), '10d EMA':maRow(t.ema10),
        '20d SMA':maRow(t.sma20), '50d SMA':maRow(t.sma50),
        '100d SMA':maRow(t.sma100), '200d SMA':maRow(t.sma200),
        'MA Verdict':t.cross,
      }}]},

      // ── Tab 3: Financials & Valuation ────────────────────────────────────────
      { id:3, name:'Financials & Valuation', fields:{
        'Revenue (TTM)':fL(rev0,cur),
        'Revenue YoY Growth':rg?fP(rg):(rev1&&rev0?fR((rev0/rev1-1)*100):NDA),
        'EBITDA':fL(ebi,cur), 'EBIT':fL(ebt0,cur), 'Net Profit / PAT':fL(ni0,cur),
        'Operating Margin':fP(opm), 'Net Profit Margin':fP(npm), 'Gross Margin':fP(gm),
        'EPS (TTM)':fC(eps,cur), 'EPS (Forward)':fC(feps,cur),
        'Revenue Est (FY)':fL(revCY,cur), 'Revenue Est (FY+1)':fL(revNY,cur),
        'EPS Est (FY)':fC(epsCY,cur), 'EPS Est (FY+1)':fC(epsNY,cur),
        'Earnings Growth Est':egrCY?fP(egrCY):NDA,
        'Free Cash Flow':fL(fcfCalc,cur), 'Operating Cash Flow':fL(opCF,cur),
        'ROE':fP(roe), 'ROA':fP(roa),
        'Debt-to-Equity':de?fN(de/100)+'x':NDA,
        'Total Debt':fL(td,cur), 'Total Cash':fL(tc,cur),
        'Current Ratio':fN(cr), 'Quick Ratio':fN(qr),
      }, subsections:[{ title:'Valuation Ratios', fields:{
        'P/E (Trailing)':fN(pe), 'P/E (Forward)':fN(fpe), 'P/B':fN(pb),
        'EV/EBITDA':fN(evebitda), 'EV/Revenue':fN(evrev), 'Enterprise Value':fL(ev,cur),
        'PEG Ratio':fN(peg), 'Book Value / Share':fC(bvps,cur),
        'Shares Outstanding':so?fL(so,cur).replace(/[$₹£€¥]/g,''):NDA,
        'Valuation Score':valScore+'/100',
        'Valuation Status':valScore>70?'Cheap':valScore>50?'Fair':'Expensive',
        'DCF Intrinsic Value':'__AI__dcfValue__AI__',
        'Margin of Safety':'__AI__marginSafety__AI__',
      }}]},

      // ── Tab 4: Ownership & Shareholding ──────────────────────────────────────
      { id:4, name:'Ownership & Shareholding', fields:{
        'Insider / Promoter %':insPct?fP(insPct):NDA,
        'Institutional %':itnPct?fP(itnPct):NDA,
        'Public / Retail %':pubPct?fP(pubPct):NDA,
        'Institutions Count':_raw(MH,'institutionsCount')?Number(_raw(MH,'institutionsCount')).toLocaleString():NDA,
        'FII / DII (Latest Qtr)':'__AI__fiidii__AI__',
        'Upcoming Index Changes':'__AI__indexChanges__AI__',
        'Recent Index Inclusions':'__AI__indexInclusions__AI__',
      }, subsections:IO.length?[{ title:'Top Institutional Holders', fields:instF}]:[]},

      // ── Tab 5: Peers & Institutions ───────────────────────────────────────────
      { id:5, name:'Peers & Institutions', fields:{
        'Total Institutional %':itnPct?fP(itnPct):NDA,
        'Peer Comparison':'__AI__peerComparison__AI__',
        'Best Value Peer':'__AI__bestValuePeer__AI__',
        'Strong Buy Pick 1':'__AI__strongBuy1__AI__',
        'Strong Buy Pick 2':'__AI__strongBuy2__AI__',
        'Strong Buy Pick 3':'__AI__strongBuy3__AI__',
      }, subsections:FO.length?[{ title:'Top Mutual Fund Holders', fields:mfF }]:[]},

      // ── Tab 6: News & Social Buzz ─────────────────────────────────────────────
      { id:6, name:'News & Social Buzz', fields:{
        'Overall Sentiment':'__AI__overallSentiment__AI__',
        'Management Commentary':'__AI__mgmtCommentary__AI__',
        'CEO / MD Name':'__AI__ceoName__AI__',
        'CEO Background':'__AI__ceoBackground__AI__',
        'Corporate Governance Score':'__AI__govScore__AI__',
        'ESG Highlights':'__AI__esgHighlights__AI__',
        'Insider Activity (12M)':'__AI__insiderActivity__AI__',
        'Social Buzz Score':'__AI__buzzScore__AI__',
        'Trending Topic':'__AI__trendingTopic__AI__',
        'Key Positive Narrative':'__AI__posNarrative__AI__',
      }, subsections:[
        { title:'Recent News Headlines', fields:Object.keys(nwsF).length?nwsF:{News:NDA} },
      ]},

      // ── Tab 7: Analysts & Forecasts ───────────────────────────────────────────
      { id:7, name:'Analysts & Forecasts', fields:{
        'Consensus Rating':rkLabel,
        'Consensus Score (1=Buy / 5=Sell)':fN(rm),
        'Number of Analysts':na?na.toString():NDA,
        'Target Price (Mean)':fC(tpm,cur), 'Target Price (High)':fC(tph,cur),
        'Target Price (Low)':fC(tpl,cur),  'Target Price (Median)':fC(tpd,cur),
        'Upside to Mean Target':upside,
        'EPS Est FY':fC(epsCY,cur), 'EPS Est FY+1':fC(epsNY,cur),
        'Revenue Est FY':fL(revCY,cur), 'Revenue Est FY+1':fL(revNY,cur),
        'Valuation Score':valScore+'/100',
        'Bull Case':'__AI__bullCase__AI__',
        'Base Case':'__AI__baseCase__AI__',
        'Bear Case':'__AI__bearCase__AI__',
        'Highest Conviction Call':'__AI__convictionCall__AI__',
        'Durability Score':'__AI__durabilityScore__AI__',
        'Piotroski Score':'__AI__piotroski__AI__',
      }},

      // ── Tab 8: Risk Analysis ──────────────────────────────────────────────────
      { id:8, name:'Risk Analysis', fields:{
        'Annual Volatility':t.vol?fR(t.vol):NDA,
        'Beta':fN(beta),
        'RSI Reading':`${t.rsi?fN(t.rsi):NDA} — ${rsiSig}`,
        '52W Range Position':(w52h&&w52l&&px)?`${((px-w52l)/(w52h-w52l)*100).toFixed(0)}% of 52W range`:NDA,
        'Volatility Score':volScore+'/100',
        'Overall Risk Score':'__AI__riskScore__AI__',
        'Risk Factor 1':'__AI__risk1__AI__',
        'Risk Factor 2':'__AI__risk2__AI__',
        'Risk Factor 3':'__AI__risk3__AI__',
        'Market Sentiment Gauge':'__AI__mktSentiment__AI__',
        'Market Sentiment Score':'__AI__mktSentScore__AI__',
        'Current Market Phase':'__AI__mktPhase__AI__',
        'Best Action Now':'__AI__bestAction__AI__',
      }},

      // ── Tab 9: Tax Compliance ──────────────────────────────────────────────────
      { id:9, name:'Tax Compliance', fields:{
        'Resident Status':resident||NDA,
        'Asset Country':SP.country||NDA,
        'STCG Rate':'__AI__stcgRate__AI__',
        'STCG Holding Period':'__AI__stcgPeriod__AI__',
        'LTCG Rate':'__AI__ltcgRate__AI__',
        'LTCG Holding Period':'__AI__ltcgPeriod__AI__',
        'Tax Notes':'__AI__taxNotes__AI__',
        'FEMA / Compliance':'__AI__femaCompliance__AI__',
        'Reporting Requirements':'__AI__reportingReqs__AI__',
        'Best Investment Platform':'__AI__bestPlatform__AI__',
      }},

      // ── Tab 10: Final Verdict ──────────────────────────────────────────────────
      { id:10, name:'Final Verdict', fields:{
        'Final Verdict Badge':'__AI__finalBadge__AI__',
        'AI Recommendation':'__AI__aiRec__AI__',
        'One-Line Summary':'__AI__oneLiner__AI__',
        'Short-Term Outlook':'__AI__shortTermOutlook__AI__',
        'Medium-Term Outlook':'__AI__medTermOutlook__AI__',
        'Long-Term Outlook':'__AI__longTermOutlook__AI__',
        'Buy Zone Price':tpl?`Around ${fC(tpl*0.95,cur)}`:'__AI__buyZone__AI__',
        'Stop Loss Price':px?fC(px*0.85,cur):'__AI__stopLoss__AI__',
        '6M Target':tpm?fC((px||0)*0.5+tpm*0.5,cur):'__AI__tgt6m__AI__',
        '12M Analyst Target':fC(tpm,cur), '12M Upside':upside,
        'Composite — Fundamentals':Math.min(30,Math.round((pe?20:10)+(roe?7:0)+(fcfCalc?3:0)))+'/30',
        'Composite — Valuation':Math.round(valScore*25/100)+'/25',
        'Composite — Technicals':Math.round(momScore*20/100)+'/20',
        'Composite — Management':'__AI__compMgmt__AI__',
        'Composite — Sector':'__AI__compSector__AI__',
        'Best Way to Invest':'__AI__bestWayInvest__AI__',
        'Conservative Allocation %':'__AI__allocConservative__AI__',
        'Moderate Allocation %':'__AI__allocModerate__AI__',
        'Aggressive Allocation %':'__AI__allocAggressive__AI__',
        'Sector Tailwinds':'__AI__sectorTailwinds__AI__',
        ...(refLinks ? {'Referral Links': refLinks} : {}),
      }},
    ],
  };
}

// ─── Short NLP prompt — AI handles prose only (~350 tokens in, ~600 out) ──────
function buildNlpPrompt(summary, daily, news, assetName, assetType, market, resident) {
  const P=summary?.price||{}, SP=summary?.summaryProfile||{};
  const FD=summary?.financialData||{}, KS=summary?.defaultKeyStatistics||{};
  const cur=P.currency||'USD', px=_raw(P,'regularMarketPrice');
  const pe=_raw(KS,'trailingPE'), pb=_raw(KS,'priceToBook'), roe=_raw(FD,'returnOnEquity');
  const mc=_raw(P,'marketCap'), rk=FD.recommendationKey||'N/A', tpm=_raw(FD,'targetMeanPrice');
  const w52h=_raw(KS,'fiftyTwoWeekHigh'), w52l=_raw(KS,'fiftyTwoWeekLow');
  const t=calcTech(daily,[]);
  const newsLines=news.slice(0,5).map((h,i)=>`${i+1}. ${h.date}: ${h.title}`).join('\n')||'No recent news';
  return `You are a financial analyst for VilfinTV. Analyze the data below and return narrative text ONLY.
Return STRICTLY a JSON object with these exact keys — no markdown, no prose outside JSON.

ASSET: ${assetName} | ${P.longName||assetName} | ${SP.sector||'N/A'} | ${SP.country||market||'N/A'}
EXCHANGE: ${P.fullExchangeName||'N/A'} | PRICE: ${cur} ${px??'N/A'} | MCAP: ${mc?fL(mc,cur):'N/A'}
52W: ${w52h??'N/A'} – ${w52l??'N/A'} | 1Y RTN: ${t.ret1y!==null?t.ret1y.toFixed(1)+'%':'N/A'}
PE: ${pe??'N/A'} | PB: ${pb??'N/A'} | ROE: ${roe?(roe*100).toFixed(1)+'%':'N/A'}
RSI: ${t.rsi?t.rsi.toFixed(1):'N/A'} | CONSENSUS: ${rk} | TARGET: ${tpm?cur+' '+tpm:'N/A'}
RESIDENT: ${resident||'N/A'}
NEWS:\n${newsLines}

Return ONLY this JSON (start { end }):
{"companyBackground":"3-4 sentences: founding, core business, revenue mix, competitive position","coreSegments":"Revenue mix and key segments in 1-2 sentences","keySubsidiaries":"Key subsidiaries, comma-separated","keyInsight":"2-3 sentences on current investment opportunity based on the data","tam":"TAM size and growth drivers","industryGrowth":"Industry growth rate and trend","marketPosition":"Leadership and competitive moat in 1 sentence","regulatoryEnv":"Key regulatory factors in 1 sentence","tailwind1":"[Title] — [1-sentence detail]","tailwind2":"[Title] — [1-sentence detail]","tailwind3":"[Title] — [1-sentence detail]","headwind1":"[Title] — [1-sentence detail]","headwind2":"[Title] — [1-sentence detail]","headwind3":"[Title] — [1-sentence detail]","overallSentiment":"Positive / Negative / Neutral — from news above","mgmtCommentary":"Latest management commentary in 1-2 sentences","ceoName":"CEO or MD full name","ceoBackground":"CEO background in 1 sentence","govScore":"X/10 with brief reason","esgHighlights":"Key ESG point in 1 sentence","insiderActivity":"Recent insider buying/selling summary","buzzScore":"Social buzz score 0-100 and trend","trendingTopic":"Current top trending topic for this stock","posNarrative":"Key positive social narrative","bullCase":"Bull case: 2-3 sentences on why the stock could outperform","baseCase":"Base case: 2-3 sentences on most likely outcome","bearCase":"Bear case: 2-3 sentences on key downside risks","convictionCall":"Highest conviction analyst call and reason","durabilityScore":"X/100 with brief reason","piotroski":"Estimated Piotroski F-Score X/9","riskScore":"Overall investment risk X/10","risk1":"[Name] — [Low/Medium/High] — [1-sentence]","risk2":"[Name] — [Low/Medium/High] — [1-sentence]","risk3":"[Name] — [Low/Medium/High] — [1-sentence]","mktSentiment":"Extreme Fear / Fear / Neutral / Greed / Extreme Greed","mktSentScore":"0-100","mktPhase":"Early Bull / Mid Bull / Late Bull / Early Bear / Mid Bear / Recovery / Consolidation","bestAction":"Buy / SIP / Hold / Reduce / Avoid — 1-line rationale","stcgRate":"STCG rate for ${resident||'Indian Resident'} on this asset","stcgPeriod":"STCG holding period threshold","ltcgRate":"LTCG rate for ${resident||'Indian Resident'}","ltcgPeriod":"LTCG holding period threshold","taxNotes":"Key tax notes and surcharge","femaCompliance":"FEMA compliance points if applicable","reportingReqs":"Tax reporting requirements","bestPlatform":"Best investment platforms for ${resident||'Indian Resident'}","dcfValue":"DCF intrinsic value estimate with key assumptions","marginSafety":"Margin of safety at current price","fiidii":"Latest FII/DII activity this quarter","indexChanges":"Upcoming index rebalancing","indexInclusions":"Recent index inclusions/exclusions","peerComparison":"Top 3 peers with name, PE, ROE, MCap in 2-3 lines","bestValuePeer":"Best value peer and brief reason","strongBuy1":"[Name] | [Ticker] | [Why] | [Target] | [Upside%]","strongBuy2":"[Name] | [Ticker] | [Why] | [Target] | [Upside%]","strongBuy3":"[Name] | [Ticker] | [Why] | [Target] | [Upside%]","finalBadge":"STRONG BUY or BUY or ACCUMULATE or HOLD or REDUCE or SELL","aiRec":"Strong Buy / Buy / Hold / Sell / Strong Sell — from data only","oneLiner":"One compelling sentence on the investment case","shortTermOutlook":"1-month outlook in 1-2 sentences","medTermOutlook":"3-6 month outlook in 1-2 sentences","longTermOutlook":"1-3 year outlook in 1-2 sentences","buyZone":"Ideal buy zone price range","stopLoss":"Stop loss price with rationale","tgt6m":"6-month price target","tgt12m":"12-month price target","compMgmt":"X/15","compSector":"X/10","bestWayInvest":"SIP / Lumpsum / Buy on Dip — with reason","allocConservative":"X%","allocModerate":"X%","allocAggressive":"X%","sectorTailwinds":"2-3 lines on structural sector tailwinds"}`;
}

/** Walk JSON skeleton and replace __AI__key__AI__ placeholders with AI values.
 *  CRITICAL: even when insights is null (AI failed), we MUST strip placeholders
 *  so the user sees "No Data Available" instead of raw __AI__key__AI__ strings. */
function mergeAiInsights(skeleton, insights) {
  const ins = insights || {};
  try {
    const merged = JSON.stringify(skeleton).replace(/"__AI__(\w+)__AI__"/g, (_,k) =>
      JSON.stringify(ins[k] !== undefined && ins[k] !== null && String(ins[k]).trim() ? String(ins[k]) : NDA)
    );
    return JSON.parse(merged);
  } catch {
    // Last-ditch: regex strip placeholders from a stringified skeleton
    try {
      const stripped = JSON.stringify(skeleton).replace(/"__AI__\w+__AI__"/g, JSON.stringify(NDA));
      return JSON.parse(stripped);
    } catch { return skeleton; }
  }
}

/** Strip markdown fences and extract JSON object from AI response. */
function parseAiJson(raw) {
  if (!raw) return null;
  try {
    const s = raw.replace(/^```(?:json)?\s*/i,'').replace(/\s*```\s*$/,'').trim();
    const i = s.indexOf('{'), j = s.lastIndexOf('}');
    if (i<0||j<0) return null;
    return JSON.parse(s.slice(i, j+1));
  } catch { return null; }
}

/** Call AI with compact NLP prompt — 2000 tokens vs 15000+ previously. */
async function callAiForInsights(nlpPrompt, env, providerHint) {
  const msgs = [
    { role:'system', content:'You are a financial analyst. Return ONLY the requested JSON object. No markdown, no prose outside JSON.' },
    { role:'user',   content:nlpPrompt },
  ];
  const maxTok = 2500;
  const hint = (providerHint||'').toLowerCase();
  let r = null;
  if (hint==='groq')    r = await callGroq(msgs,env,maxTok);
  else if (hint==='gemini')  r = await callGemini(msgs,env,maxTok);
  else if (hint==='openai')  r = await callOpenAI(msgs,env,maxTok);
  else if (hint==='deepseek')r = await callDeepSeek(msgs,env,maxTok);
  if (!r) r = await callGroq(msgs,env,maxTok);
  if (!r) r = await callGemini(msgs,env,maxTok);
  if (!r) r = await callOpenAI(msgs,env,maxTok);
  if (!r) r = await callDeepSeek(msgs,env,maxTok);
  if (!r) r = await callPollinations(msgs);
  return parseAiJson(r);
}

/** Parse structured report request fields from the compact buildQuery() prompt. */
function parseReportFields(prompt) {
  const f = lbl => { const m=prompt.match(new RegExp(lbl+'\\s*:\\s*([^\\n|]+)','i')); return m?m[1].replace(/\s+/g,' ').trim():''; };
  const refM = prompt.match(/Referral Links[^\n]*:\n([\s\S]+?)(?:\n\nOUTPUT|$)/i);
  return {
    assetName:    f('Asset Name')||f('Currency Held')||'Unknown Asset',
    assetType:    f('Asset Type'),
    market:       f('Market\\s*[/\\s]*Category')||f('Market'),
    resident:     f('Resident Status'),
    referralLinks: refM ? refM[1].trim() : '',
  };
}

/**
 * Main hybrid report orchestrator.
 * 1. Parse asset details from prompt
 * 2. Resolve global ticker symbol
 * 3. Fetch financial data from Yahoo Finance v10 + chart + news (parallel)
 * 4. Build 10-tab JSON skeleton from API data — pure JavaScript, zero AI for numbers
 * 5. Call AI with compact ~350-token prompt for prose/narrative fields only
 * 6. Merge AI text into skeleton, return complete JSON string
 */
async function hybridReport(prompt, env, providerHint) {
  const { assetName, assetType, market, resident, referralLinks } = parseReportFields(prompt);
  const today = new Date().toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
  console.log(`[hybrid] asset="${assetName}" type="${assetType}" market="${market}" resident="${resident}"`);

  const symbol = await resolveSymbolGlobal(assetName, market);
  console.log(`[hybrid] resolved symbol="${symbol}"`);

  // All 4 fetches run concurrently — wall time = slowest single fetch
  const [sumRes, dRes, mRes, nwsRes] = await Promise.allSettled([
    fetchYFSummaryFull(symbol),
    fetchYFChartHistory(symbol, '1y', '1d'),
    fetchYFChartHistory(symbol, '5y', '1mo'),
    fetchYFNewsHeadlines(assetName||symbol),
  ]);

  let summary  = sumRes.status==='fulfilled' ? sumRes.value : null;
  const dRaw   = dRes.status==='fulfilled' ? dRes.value : null;
  const mRaw   = mRes.status==='fulfilled' ? mRes.value : null;
  const daily  = extractCloses(dRaw);
  const monthly= extractCloses(mRaw);
  let news     = nwsRes.status==='fulfilled' ? (nwsRes.value||[]) : [];
  if (!news.length) news = await fetchGoogleNewsRSS(assetName).catch(()=>[]);

  // ── Aggressive hydration from chart meta ─────────────────────────────────
  // v10/quoteSummary frequently 401/429s for non-US tickers without session
  // cookies. The v8/chart endpoint reliably ships {currency,symbol,price,52W}
  // in its meta block. We patch summary at every level: missing object,
  // missing field, OR explicit null/undefined.
  const meta = dRaw?.chart?.result?.[0]?.meta || mRaw?.chart?.result?.[0]?.meta || {};
  summary = summary || {};
  summary.price = summary.price || {};
  summary.summaryDetail = summary.summaryDetail || {};
  // Patch only when current value is missing/null
  const patch = (obj, key, val) => { if ((obj[key]===undefined||obj[key]===null) && val!==undefined && val!==null) obj[key]=val; };
  patch(summary.price, 'symbol',              meta.symbol);
  patch(summary.price, 'currency',            meta.currency);
  patch(summary.price, 'regularMarketPrice',  meta.regularMarketPrice);
  patch(summary.price, 'regularMarketVolume', meta.regularMarketVolume);
  patch(summary.price, 'fullExchangeName',    meta.fullExchangeName||meta.exchangeName);
  patch(summary.price, 'exchangeName',        meta.exchangeName);
  patch(summary.price, 'longName',            meta.longName||meta.shortName);
  patch(summary.price, 'shortName',           meta.shortName);
  if (summary.summaryDetail.fiftyTwoWeekHigh==null && meta.fiftyTwoWeekHigh!=null) summary.summaryDetail.fiftyTwoWeekHigh = { raw: meta.fiftyTwoWeekHigh };
  if (summary.summaryDetail.fiftyTwoWeekLow ==null && meta.fiftyTwoWeekLow !=null) summary.summaryDetail.fiftyTwoWeekLow  = { raw: meta.fiftyTwoWeekLow  };
  if (summary.summaryDetail.previousClose   ==null && meta.previousClose   !=null) summary.summaryDetail.previousClose    = { raw: meta.previousClose    };
  // Last-ditch currency inference from .NS / .T / .L / .DE etc.
  if (!summary.price.currency) {
    const sfx = (symbol.match(/\.[A-Z]{1,3}$/)||[''])[0];
    const SFX_CUR = {'.NS':'INR','.BO':'INR','.T':'JPY','.L':'GBp','.DE':'EUR','.PA':'EUR','.AX':'AUD','.HK':'HKD','.TO':'CAD','.SI':'SGD'};
    if (SFX_CUR[sfx]) { summary.price.currency = SFX_CUR[sfx]; console.log(`[hybrid] inferred currency ${SFX_CUR[sfx]} from suffix ${sfx}`); }
  }
  console.log(`[hybrid] currency=${summary.price.currency} px=${summary.price.regularMarketPrice} sym=${summary.price.symbol}`);

  console.log(`[hybrid] summary=${!!summary} daily=${daily.length}pt monthly=${monthly.length}pt news=${news.length}`);

  // Build JSON skeleton — pure JavaScript, no AI for any numeric field
  const skeleton = buildStockSkeleton(summary||{}, daily, monthly, news, assetName, market, resident, referralLinks, today);

  // AI called once for prose fields only (~2000 tokens total vs 15000+ previously)
  const nlpPrompt = buildNlpPrompt(summary||{}, daily, news, assetName, assetType, market, resident);
  const insights  = await callAiForInsights(nlpPrompt, env, providerHint);
  console.log(`[hybrid] insights=${!!insights} keys=${insights?Object.keys(insights).length:0}`);

  return JSON.stringify(mergeAiInsights(skeleton, insights));
}

// ─── Legacy stub — kept so existing chat-mode fetchLiveContext() still compiles ─
function resolveNSETicker(assetName) {
  const lower = (assetName || '').toLowerCase().replace(/[^a-z0-9&. ]/g, '').trim();
  if (NSE_TICKERS[lower]) return NSE_TICKERS[lower];
  // Try partial match (both directions)
  for (const [key, ticker] of Object.entries(NSE_TICKERS)) {
    if (lower.includes(key) || key.includes(lower)) return ticker;
  }
  // Last resort: take first word, uppercase
  return lower.split(/\s+/)[0].toUpperCase().replace(/[^A-Z0-9&.-]/g, '');
}

// ─── Legacy Yahoo Finance fetchers removed — replaced by hybrid engine above ──

// ═══════════════════════════════════════════════════════════════════════════════
// CRICKET DATA FETCHER  (GET /cricket endpoint)
// ═══════════════════════════════════════════════════════════════════════════════

/** Priority score: lower = shown first. PSL=6 means it's filtered out on frontend. */
function cricPriority(league) {
  const n = (league || '').toLowerCase();
  if (n.includes('ipl') || n.includes('indian premier'))  return 0;
  if (n.includes('wc') || n.includes('world cup') || n.includes('champions trophy') || n.includes('icc')) return 1;
  if (n.includes('test') || n.includes('t20i') || n.includes('odi') || n.includes('bilateral')) return 1;
  if (n.includes('bpl') || n.includes('bangladesh premier')) return 2;
  if (n.includes('wpl') || n.includes("women's premier")) return 3;
  if (n.includes('big bash') || n.includes('bbl'))         return 4;
  if (n.includes('cpl') || n.includes('caribbean'))        return 4;
  if (n.includes('sa20') || n.includes('sa 20'))           return 4;
  if (n.includes('t20') || n.includes('twenty20'))         return 5;
  if (n.includes('psl'))                                    return 6; // excluded on frontend
  if (n.includes('county') || n.includes('ranji') || n.includes('domestic')) return 7;
  return 8;
}

/**
 * Fetch live cricket data from ESPN public APIs (no auth required).
 * Returns { matches: [...], updated: ISO-date, sources: [...] }
 */
async function fetchCricketData() {
  const espnEndpoints = [
    { url: 'https://site.api.espn.com/apis/site/v2/sports/cricket/ipl/scoreboard',  league: 'Indian Premier League' },
    { url: 'https://site.api.espn.com/apis/site/v2/sports/cricket/28/scoreboard',   league: 'IPL' },
    { url: 'https://site.api.espn.com/apis/site/v2/sports/cricket/scoreboard',      league: '' },
    { url: 'https://site.api.espn.com/apis/site/v2/sports/cricket/bpl/scoreboard',  league: 'Bangladesh Premier League' },
    { url: 'https://site.api.espn.com/apis/site/v2/sports/cricket/wc/scoreboard',   league: 'ICC World Cup' },
    { url: 'https://site.api.espn.com/apis/site/v2/sports/cricket/wpl/scoreboard',  league: "Women's Premier League" },
  ];

  const today = new Date().toISOString().slice(0, 10);

  const results = await Promise.allSettled([
    // TheSportsDB
    fetch(`https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=${today}&s=Cricket`,
      { headers: { 'User-Agent': 'VilfinTV/1.0' }, signal: AbortSignal.timeout(8000) }
    ).then(r => r.ok ? r.json() : null).catch(() => null),
    // ESPN endpoints
    ...espnEndpoints.map(ep =>
      fetch(ep.url, { headers: { 'User-Agent': 'VilfinTV/1.0' }, signal: AbortSignal.timeout(7000) })
        .then(r => r.ok ? r.json() : null).catch(() => null)
    )
  ]);

  const [sdbResult, ...espnResults] = results;
  const seen    = new Set();
  const matches = [];

  // ── Parse ESPN results ────────────────────────────────────────────────────
  espnResults.forEach((res, idx) => {
    if (res.status !== 'fulfilled' || !res.value) return;
    const data = res.value;
    (data.events || data.competitions || []).forEach(ev => {
      const key = ev.id || ev.uid || ev.name;
      if (seen.has(key)) return;
      seen.add(key);

      (ev.competitions || [ev]).forEach(comp => {
        const comps  = comp.competitors || [];
        if (!comps.length) return;

        const state   = (comp.status?.type?.state || '').toLowerCase();
        const isLive  = state === 'in';
        const isFinal = state === 'post';
        const league  = ev.name || espnEndpoints[idx]?.league || '';
        const status  = comp.status?.type?.shortDetail || comp.status?.type?.description || (isLive ? 'Live' : 'Scheduled');
        const h       = comps.find(c => c.homeAway === 'home') || comps[0];
        const a       = comps.find(c => c.homeAway === 'away') || comps[1];

        matches.push({
          id:        key + '-' + (comp.id || ''),
          league,
          title:     league,
          status,
          isLive,
          isFinal,
          priority:  cricPriority(league),
          homeTeam:  h?.team?.abbreviation || h?.team?.shortDisplayName || '?',
          awayTeam:  a?.team?.abbreviation || a?.team?.shortDisplayName || '?',
          homeScore: h?.score ?? '',
          awayScore: a?.score ?? '',
          venue:     comp.venue?.fullName || null,
          result:    null,
          timeStr:   '',
          source:    'espn',
        });
      });
    });
  });

  // ── Parse TheSportsDB results ─────────────────────────────────────────────
  const sdbData = sdbResult?.value;
  const sdbEvents = sdbData?.events || [];
  sdbEvents.forEach(ev => {
    const key = ev.idEvent || ev.strEvent;
    if (seen.has(key)) return;
    seen.add(key);

    const raw    = ev.strStatus || 'Scheduled';
    const isLive = /live|innings|over/i.test(raw);
    const isFinal= /finish|won|draw|result|abandon/i.test(raw);
    let timeStr  = '';
    try {
      if (ev.strTimestamp) {
        timeStr = new Date(ev.strTimestamp + 'Z').toLocaleTimeString('en-IN', {
          hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata'
        });
      }
    } catch { /* non-fatal */ }

    matches.push({
      id:        String(key),
      league:    ev.strLeague || '',
      title:     ev.strEvent || 'Cricket',
      status:    raw,
      isLive,
      isFinal,
      priority:  cricPriority(ev.strLeague || ''),
      homeTeam:  ev.strHomeTeam || '?',
      awayTeam:  ev.strAwayTeam || '?',
      homeScore: ev.intHomeScore ?? '',
      awayScore: ev.intAwayScore ?? '',
      venue:     ev.strVenue || null,
      result:    ev.strResult || null,
      timeStr,
      source:    'sportsdb',
    });
  });

  // ── Sort: live first, then by priority ────────────────────────────────────
  matches.sort((a, b) =>
    (b.isLive ? 1 : 0) - (a.isLive ? 1 : 0) || a.priority - b.priority
  );

  return {
    matches:   matches.slice(0, 20),
    updated:   new Date().toISOString(),
    sources:   ['espn', 'thesportsdb'],
    count:     matches.length,
  };
}

// ═══════════════════════════════════════════════════════════════════════════════
// DAILY MARKET SNAPSHOT (build-time only — called by build.js, NOT the browser)
// ═══════════════════════════════════════════════════════════════════════════════
async function generateMarketSnapshot(env) {
  const today   = new Date().toDateString();
  const liveCtx = await fetchLiveContext('global stock market indices commodities today');

  const snapshotPrompt = `Generate a concise daily market briefing for ${today} covering:

## Key Themes
- 2-3 dominant macro themes (e.g. rate decisions, geopolitical risks, earnings seasons)

## Major Indices
- Brief status of: Nifty 50, Sensex, S&P 500, Nasdaq, Nikkei, Hang Seng, STOXX 50

## Commodities
- Gold, Silver, Crude Oil (WTI & Brent), Natural Gas, Copper — direction and key level

## Forex
- USD/INR, EUR/USD, JPY/USD — notable moves

## What to Watch
- 2-3 upcoming events or catalysts this week

Use Markdown. Be concise — max 350 words. Write as a professional market analyst.`;

  const messages = [
    { role: 'system', content: SYSTEM_PROMPT(today) },
    { role: 'user',   content: liveCtx + snapshotPrompt },
  ];

  // Prefer Groq for daily snapshot (fast, free, high-quality)
  const groq = await callGroq(messages, env, 800);
  if (groq) return { briefing: groq, generated: new Date().toISOString(), model: GROQ_MODEL };

  // Fallback: Gemini
  const gemini = await callGemini(messages, env, 800);
  if (gemini) return { briefing: gemini, generated: new Date().toISOString(), model: GEMINI_MODEL };

  // Fallback: DeepSeek
  const deepseek = await callDeepSeek(messages, env, 800);
  if (deepseek) return { briefing: deepseek, generated: new Date().toISOString(), model: DEEPSEEK_MODEL };

  throw new Error('Cannot generate snapshot — no AI provider available');
}

// ─── Utility ──────────────────────────────────────────────────────────────────
function json(data, corsHeaders, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders },
  });
}
