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
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
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
        return json({ error: 'Service temporarily unavailable. Please retry.' }, CORS, 503);
      }
    }

    return json({ error: 'Not found' }, CORS, 404);
  }
};

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

/** Google Gemini — converts chat messages into a combined text prompt */
async function callGemini(messages, env, maxTokens) {
  if (!env.GEMINI_API_KEY) return null;
  try {
    // Gemini uses a different format — combine system + user into one prompt
    const sysContent  = messages.find(m => m.role === 'system')?.content || '';
    const userContent = messages.find(m => m.role === 'user')?.content   || '';
    const combined    = sysContent ? `${sysContent}\n\n${userContent}` : userContent;

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
  try {
    const sysShort = `Financial Market Assistant. ${new Date().toDateString()}. Use Markdown.`;
    const userMsg  = messages.find(m => m.role === 'user')?.content || '';
    const res = await fetch('https://text.pollinations.ai/openai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model:   'openai-large',
        messages: [
          { role: 'system', content: sysShort },
          { role: 'user',   content: userMsg },
        ],
        stream:  false,
        private: true,
      }),
      signal: AbortSignal.timeout(45000),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content?.trim();
    return (text && text.length > 20) ? text : null;
  } catch (e) { console.warn('Pollinations failed:', e.message); return null; }
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
  const today       = new Date().toDateString();
  const liveContext = await fetchLiveContext(prompt);

  // ── Build messages array ─────────────────────────────────────────────────────
  // If the frontend sent a full conversation history, use it so the AI has
  // multi-turn context. Otherwise fall back to single-turn mode.
  let messages;
  if (historyMsgs && historyMsgs.length > 0) {
    // Inject live market context into the last user message only (not all turns)
    const withContext = historyMsgs.map((m, i) => {
      if (i === historyMsgs.length - 1 && m.role === 'user' && liveContext) {
        return { role: 'user', content: liveContext + m.content };
      }
      return m;
    });
    messages = [
      { role: 'system', content: SYSTEM_PROMPT(today) },
      ...withContext,
    ];
  } else {
    messages = [
      { role: 'system', content: SYSTEM_PROMPT(today) },
      { role: 'user',   content: liveContext + prompt },
    ];
  }

  const provider = (providerHint || '').toLowerCase();

  // ── Honour explicit provider preference ────────────────────────────────────
  if (provider === 'groq') {
    const t = await callGroq(messages, env);
    if (t) return t;
  }
  if (provider === 'gemini') {
    const t = await callGemini(messages, env);
    if (t) return t;
  }
  if (provider === 'openai') {
    const t = await callOpenAI(messages, env);
    if (t) return t;
  }
  if (provider === 'deepseek') {
    const t = await callDeepSeek(messages, env);
    if (t) return t;
  }

  // ── Default cascade: Groq → Gemini → OpenAI → DeepSeek → Pollinations ─────
  const groq     = await callGroq(messages, env);       if (groq)     return groq;
  const gemini   = await callGemini(messages, env);     if (gemini)   return gemini;
  const openai   = await callOpenAI(messages, env);     if (openai)   return openai;
  const deepseek = await callDeepSeek(messages, env);   if (deepseek) return deepseek;
  const poll     = await callPollinations(messages);    if (poll)     return poll;

  throw new Error('All AI providers unavailable');
}

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
