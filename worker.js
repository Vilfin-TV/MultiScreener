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
  const today = new Date().toDateString();

  // ── Detect structured report mode ───────────────────────────────────────────
  // Report requests contain the sentinel string injected by buildQuery().
  // For reports: use pre-fetch engine (fast, reliable market data).
  // For chat:    use fetchLiveContext (lightweight YF quote + DDG snippet).
  const isReportMode = prompt.includes('OUTPUT FORMAT — STRICT JSON REQUIRED');

  let contextBlock = '';
  if (isReportMode) {
    // Pre-fetch all financial data concurrently; returns a structured text block.
    // If all sources fail, returns '' — AI falls back to training knowledge.
    contextBlock = await prefetchMarketData(prompt);
  } else {
    contextBlock = await fetchLiveContext(prompt);
  }

  // ── Build messages array ─────────────────────────────────────────────────────
  // If the frontend sent a full conversation history, use it so the AI has
  // multi-turn context. Otherwise fall back to single-turn mode.
  let messages;
  if (historyMsgs && historyMsgs.length > 0) {
    // Inject context into the last user message only (not all turns)
    const withContext = historyMsgs.map((m, i) => {
      if (i === historyMsgs.length - 1 && m.role === 'user' && contextBlock) {
        // For report mode: append context at the END (after all prompt instructions)
        // For chat mode:   prepend context so AI sees it first
        return {
          role: 'user',
          content: isReportMode ? (m.content + contextBlock) : (contextBlock + m.content),
        };
      }
      return m;
    });
    messages = [
      { role: 'system', content: SYSTEM_PROMPT(today) },
      ...withContext,
    ];
  } else {
    const userContent = isReportMode
      ? (prompt + contextBlock)      // append after prompt instructions
      : (contextBlock + prompt);     // prepend for chat
    messages = [
      { role: 'system', content: SYSTEM_PROMPT(today) },
      { role: 'user',   content: userContent },
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
// PRE-FETCH MARKET DATA ENGINE  (for structured report /query requests)
// ═══════════════════════════════════════════════════════════════════════════════
//
// Cloudflare Workers cannot use npm packages (no Node.js runtime).
// All data is fetched via the Web Fetch API from free public endpoints:
//   • Yahoo Finance v7/quote  — live price, MCap, P/E, P/B, EPS, 52W, beta, MAs
//   • Yahoo Finance v8/chart  — daily closes (1y) for SMA/RSI, monthly (5y) for CAGR
//   • Yahoo Finance v1/search — recent news headlines
//   • NSE India public API    — authoritative Indian live price
//   • AMFI India              — mutual fund NAV
//
// Result: a `rawMarketContext` string appended to the AI prompt so the AI
// formats pre-fetched numbers into JSON — no LLM web-searching needed.

// ─── NSE ticker lookup table ──────────────────────────────────────────────────
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

/** Resolve an Indian asset name to its NSE ticker symbol */
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

/**
 * Parse the structured "Asset Name / Asset Type / Market" fields that
 * buildQuery() embeds in the prompt. Falls back to empty string for missing.
 */
function parsePromptFields(prompt) {
  const get = (key) => {
    const m = prompt.match(new RegExp(String(key) + '\\s*:\\s*([^\\n]+)', 'i'));
    return m ? m[1].trim() : '';
  };
  return {
    assetName: get('Asset Name'),
    assetType: get('Asset Type'),
    market:    get('Market \\/ Category'),
    resident:  get('Resident Status'),
  };
}

// ─── Yahoo Finance fetchers ───────────────────────────────────────────────────

/** Fetch comprehensive live quote from Yahoo Finance v7 */
async function fetchYFQuoteFull(symbol) {
  const FIELDS = [
    'regularMarketPrice','regularMarketChange','regularMarketChangePercent',
    'regularMarketVolume','regularMarketOpen','regularMarketDayHigh','regularMarketDayLow',
    'regularMarketPreviousClose','marketCap','trailingPE','forwardPE','priceToBook',
    'trailingEps','dividendYield','fiftyTwoWeekHigh','fiftyTwoWeekLow',
    'fiftyDayAverage','twoHundredDayAverage','beta',
    'longName','shortName','sector','industry','currency','exchange',
    'regularMarketTime','marketState','averageVolume','averageVolume10days',
  ].join(',');
  try {
    const res = await fetch(
      `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(symbol)}&fields=${FIELDS}`,
      {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
          'Accept': 'application/json',
          'Accept-Language': 'en-US,en;q=0.9',
        },
        signal: AbortSignal.timeout(9000),
      }
    );
    if (!res.ok) return null;
    const data = await res.json();
    return data?.quoteResponse?.result?.[0] || null;
  } catch { return null; }
}

/**
 * Fetch OHLCV chart data from Yahoo Finance v8.
 * @param {string} symbol - e.g. "HDFCBANK.NS"
 * @param {string} range  - "1y" | "5y" | "2y"
 * @param {string} interval - "1d" | "1wk" | "1mo"
 */
async function fetchYFChartData(symbol, range, interval) {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`
      + `?interval=${interval}&range=${range}&includePrePost=false`;
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)',
        'Accept': 'application/json',
      },
      signal: AbortSignal.timeout(12000),
    });
    return res.ok ? res.json() : null;
  } catch { return null; }
}

/** Fetch recent news from Yahoo Finance search */
async function fetchYFSearchNews(query) {
  try {
    const url = 'https://query1.finance.yahoo.com/v1/finance/search'
      + '?q=' + encodeURIComponent(query)
      + '&quotesCount=2&newsCount=6&enableFuzzyQuery=false&lang=en-US';
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)',
        'Accept': 'application/json',
      },
      signal: AbortSignal.timeout(7000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.news || [])
      .filter(n => n.title)
      .slice(0, 6)
      .map(n => {
        const d = n.providerPublishTime
          ? new Date(n.providerPublishTime * 1000).toISOString().split('T')[0]
          : '';
        return `• ${n.title}${n.publisher ? ' — ' + n.publisher : ''}${d ? ' [' + d + ']' : ''}`;
      });
  } catch { return []; }
}

/** Try Google News RSS as a news fallback (simple XML parse, no DOM needed) */
async function fetchGoogleNewsRSS(query) {
  try {
    const url = `https://news.google.com/rss/search?q=${encodeURIComponent(query + ' stock NSE')}&hl=en-IN&gl=IN&ceid=IN:en`;
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)' },
      signal: AbortSignal.timeout(7000),
    });
    if (!res.ok) return [];
    const xml = await res.text();
    const items = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].slice(0, 6);
    return items.map(m => {
      const title  = (m[1].match(/<title><!\[CDATA\[(.*?)\]\]><\/title>/) || m[1].match(/<title>(.*?)<\/title>/) || [])[1] || '';
      const source = (m[1].match(/<source[^>]*>(.*?)<\/source>/) || [])[1] || '';
      return title ? `• ${title}${source ? ' — ' + source : ''}` : null;
    }).filter(Boolean);
  } catch { return []; }
}

// ─── Technical calculation helpers ───────────────────────────────────────────

/** Extract clean close prices from a Yahoo Finance v8 chart response */
function getChartCloses(chartJson) {
  const result = chartJson?.chart?.result?.[0];
  if (!result) return [];
  const adj   = result.indicators?.adjclose?.[0]?.adjclose || [];
  const plain = result.indicators?.quote?.[0]?.close       || [];
  const src   = adj.length ? adj : plain;
  return src.filter(c => c !== null && c !== undefined && !isNaN(c));
}

/** Simple Moving Average of the last `n` closes */
function calcSMA(closes, n) {
  if (!closes || closes.length < n) return null;
  const slice = closes.slice(-n);
  return +(slice.reduce((a, b) => a + b, 0) / n).toFixed(2);
}

/**
 * RSI (14) — Wilder's smoothing.
 * Needs at least period+1 closes.
 */
function calcRSI(closes, period = 14) {
  if (!closes || closes.length < period + 1) return null;
  const src = closes.slice(-(period + 30)); // extra buffer for smoothing
  let gains = 0, losses = 0;
  // Initial average
  for (let i = 1; i <= period; i++) {
    const d = src[i] - src[i - 1];
    if (d >= 0) gains += d; else losses -= d;
  }
  let avgG = gains / period, avgL = losses / period;
  // Wilder smoothing for remaining bars
  for (let i = period + 1; i < src.length; i++) {
    const d = src[i] - src[i - 1];
    avgG = (avgG * (period - 1) + (d > 0 ? d : 0)) / period;
    avgL = (avgL * (period - 1) + (d < 0 ? -d : 0)) / period;
  }
  if (avgL === 0) return 100;
  return +(100 - 100 / (1 + avgG / avgL)).toFixed(1);
}

/**
 * Calculate percentage return over `periods` data points from end.
 * Works for both daily (periods = trading days) and monthly (periods = months).
 */
function calcReturnPct(closes, periods) {
  if (!closes || closes.length < 2) return null;
  const cur  = closes[closes.length - 1];
  const idx  = closes.length - 1 - periods;
  if (idx < 0 || !closes[idx]) return null;
  return +((cur - closes[idx]) / closes[idx] * 100).toFixed(1);
}

/** Convert a simple total return to CAGR given number of years */
function toCagr(totalReturnPct, years) {
  if (totalReturnPct === null || !years) return null;
  return +(((Math.pow(1 + totalReturnPct / 100, 1 / years)) - 1) * 100).toFixed(1);
}

// ─── Context compiler ─────────────────────────────────────────────────────────

/**
 * Assembles all fetched data into a single structured text block
 * that the AI model maps directly into the JSON schema fields.
 */
function compileRawMarketContext({ symbol, assetName, assetType, quote, dailyCloses, monthlyCloses, news, nseData, amfiData }) {
  const lines = [];
  const isMF  = /mutual\s*fund/i.test(assetType);
  const isETF = /etf/i.test(assetType);
  const cur   = quote?.currency === 'INR' ? '₹' : (quote?.currency ? quote.currency + ' ' : '');
  const p     = (v, d = 2) => (v !== null && v !== undefined && !isNaN(v)) ? +parseFloat(v).toFixed(d) : null;
  const fv    = (v, prefix = '', suffix = '') => (v !== null && v !== undefined) ? `${prefix}${v}${suffix}` : 'No Data Available';
  const fmtCr = (v) => v ? `₹${(v / 1e7).toFixed(0)} Cr` : 'No Data Available';
  const fpct  = (v) => v !== null ? `${v >= 0 ? '+' : ''}${v}%` : 'No Data Available';
  const fdate = (epoch) => epoch ? new Date(epoch * 1000).toISOString().split('T')[0] : 'N/A';

  // ── LIVE PRICE ───────────────────────────────────────────────────────────────
  if (quote) {
    lines.push('=== LIVE PRICE DATA (Yahoo Finance ✓live) ===');
    lines.push(`Current Price: ${fv(p(quote.regularMarketPrice), cur)} ✓live`);
    if (quote.regularMarketChange !== undefined) {
      const sign = quote.regularMarketChange >= 0 ? '+' : '';
      lines.push(`Day Change: ${sign}${p(quote.regularMarketChange)} (${sign}${p(quote.regularMarketChangePercent)}%) ✓live`);
    }
    lines.push(`Day Open: ${fv(p(quote.regularMarketOpen), cur)}`);
    lines.push(`Day High: ${fv(p(quote.regularMarketDayHigh), cur)}`);
    lines.push(`Day Low: ${fv(p(quote.regularMarketDayLow), cur)}`);
    lines.push(`Previous Close: ${fv(p(quote.regularMarketPreviousClose), cur)}`);
    if (quote.regularMarketVolume) {
      lines.push(`Volume (today): ${Number(quote.regularMarketVolume).toLocaleString('en-IN')} ✓live`);
      lines.push(`Avg Volume (3m): ${Number(quote.averageVolume || 0).toLocaleString('en-IN')}`);
    }
    lines.push(`Market Cap: ${fmtCr(quote.marketCap)} ✓live`);
    lines.push(`52-Week High: ${fv(p(quote.fiftyTwoWeekHigh), cur)}`);
    lines.push(`52-Week Low: ${fv(p(quote.fiftyTwoWeekLow), cur)}`);
    if (quote.dividendYield) lines.push(`Dividend Yield: ${p(quote.dividendYield * 100, 2)}%`);
    lines.push(`Exchange: ${quote.exchange || 'NSE'}`);
    lines.push(`Market State: ${quote.marketState || 'N/A'}`);
    lines.push(`Price As Of: ${fdate(quote.regularMarketTime)}`);
    lines.push('');
  }

  // ── FUNDAMENTALS ─────────────────────────────────────────────────────────────
  if (quote && !isMF) {
    lines.push('=== FUNDAMENTAL METRICS ===');
    lines.push(`P/E Ratio (TTM): ${fv(p(quote.trailingPE, 1))}`);
    lines.push(`Forward P/E: ${fv(p(quote.forwardPE, 1))}`);
    lines.push(`P/B Ratio: ${fv(p(quote.priceToBook, 2))}`);
    lines.push(`EPS (TTM): ${fv(p(quote.trailingEps, 2), cur)}`);
    lines.push(`Beta: ${fv(p(quote.beta, 2))}`);
    lines.push(`50-Day MA (Yahoo): ${fv(p(quote.fiftyDayAverage, 2), cur)}`);
    lines.push(`200-Day MA (Yahoo): ${fv(p(quote.twoHundredDayAverage, 2), cur)}`);
    if (quote.sector)   lines.push(`Sector: ${quote.sector}`);
    if (quote.industry) lines.push(`Industry: ${quote.industry}`);
    if (quote.longName) lines.push(`Full Name: ${quote.longName}`);
    lines.push('');
  }

  // ── TECHNICALS (calculated from 1-year daily closes) ─────────────────────────
  if (dailyCloses && dailyCloses.length >= 20) {
    const last    = dailyCloses[dailyCloses.length - 1];
    const sma20   = calcSMA(dailyCloses, 20);
    const sma50   = calcSMA(dailyCloses, Math.min(50,  dailyCloses.length));
    const sma200  = calcSMA(dailyCloses, Math.min(200, dailyCloses.length));
    const rsi     = calcRSI(dailyCloses, 14);
    const vs = (ma) => ma ? fpct(+((last - ma) / ma * 100).toFixed(1)) : 'N/A';
    const trend   = (sma20 && last > sma20 && sma50 && last > sma50) ? 'Bullish'
                  : (sma20 && last < sma20 && sma50 && last < sma50) ? 'Bearish' : 'Mixed';
    const cross   = (sma50 && sma200)
                  ? (sma50 > sma200 ? 'Golden Cross (50D > 200D — bullish)' : 'Death Cross (50D < 200D — bearish)')
                  : 'No Data Available';

    lines.push('=== TECHNICAL INDICATORS (calculated from Yahoo Finance 1-year daily price history) ===');
    lines.push(`Current Price: ${fv(p(last, 2), cur)}`);
    if (sma20)  lines.push(`20-Day SMA: ${cur}${sma20} | Price vs 20D SMA: ${vs(sma20)}`);
    if (sma50)  lines.push(`50-Day SMA: ${cur}${sma50} | Price vs 50D SMA: ${vs(sma50)}`);
    if (sma200) lines.push(`200-Day SMA: ${cur}${sma200} | Price vs 200D SMA: ${vs(sma200)}`);
    lines.push(`RSI (14): ${fv(rsi)} | Signal: ${rsi === null ? 'N/A' : rsi > 70 ? 'Overbought' : rsi < 30 ? 'Oversold' : 'Neutral'}`);
    lines.push(`MA Trend: ${trend}`);
    lines.push(`50D vs 200D Cross: ${cross}`);
    lines.push('');
  }

  // ── HISTORICAL RETURNS (calculated from 5-year monthly closes) ───────────────
  if (monthlyCloses && monthlyCloses.length >= 6) {
    const r1y   = calcReturnPct(monthlyCloses, Math.min(12, monthlyCloses.length - 1));
    const r3y   = calcReturnPct(monthlyCloses, Math.min(36, monthlyCloses.length - 1));
    const r5y   = calcReturnPct(monthlyCloses, Math.min(60, monthlyCloses.length - 1));
    const c3y   = toCagr(r3y, 3);
    const c5y   = toCagr(r5y, 5);

    lines.push('=== HISTORICAL RETURNS (calculated from Yahoo Finance monthly price history) ===');
    lines.push(`1-Year Return: ${r1y !== null ? fpct(r1y) : 'No Data Available'}`);
    lines.push(`3-Year CAGR: ${c3y !== null ? fpct(c3y) : 'No Data Available'}`);
    lines.push(`5-Year CAGR: ${c5y !== null ? fpct(c5y) : 'No Data Available'}`);
    lines.push('Note: Based on adjusted monthly close prices from Yahoo Finance.');
    lines.push('');
  }

  // ── MF-specific ───────────────────────────────────────────────────────────────
  if (amfiData) {
    lines.push('=== MUTUAL FUND NAV (AMFI India) ===');
    lines.push(amfiData);
    lines.push('');
  }

  // ── NSE authoritative quote ───────────────────────────────────────────────────
  if (nseData) {
    lines.push('=== NSE INDIA LIVE QUOTE (authoritative domestic source) ===');
    lines.push(nseData);
    lines.push('');
  }

  // ── News ─────────────────────────────────────────────────────────────────────
  if (news && news.length) {
    lines.push('=== RECENT NEWS HEADLINES ===');
    news.forEach(n => lines.push(n));
    lines.push('');
  }

  if (!lines.length) return '';
  return lines.join('\n');
}

/**
 * Master pre-fetch orchestrator for structured report requests.
 * Parses the asset name from the prompt, resolves ticker, fires concurrent
 * fetches, and returns a formatted `rawMarketContext` string.
 */
async function prefetchMarketData(prompt) {
  const { assetName, assetType, market } = parsePromptFields(prompt);

  const isMF     = /mutual\s*fund/i.test(assetType) || /fund/i.test(market);
  const isETF    = /etf/i.test(assetType);
  const isIndian = /india|nse|bse|₹|inr/i.test((market + ' ' + assetType + ' ' + prompt).slice(0, 600));

  // Resolve ticker
  let ticker = '';
  if (isIndian && !isMF) {
    const nse = resolveNSETicker(assetName);
    ticker = nse + '.NS';
  } else if (isMF) {
    // MF — use AMFI; try YF search for ETF sub-types
    ticker = isETF ? (resolveNSETicker(assetName) + '.NS') : '';
  } else {
    // Non-Indian: extract uppercase word (crypto, global ETF, etc.)
    ticker = extractTicker(prompt);
  }

  console.log(`[prefetch] asset="${assetName}" type="${assetType}" market="${market}" ticker="${ticker}" isMF=${isMF} isETF=${isETF}`);

  // ── Concurrent fetches ────────────────────────────────────────────────────────
  const [quoteRes, dailyRes, monthlyRes, newsRes, nseRes, amfiRes] = await Promise.allSettled([

    // 1. YF v7 full quote (price, fundamentals, MA, 52W, sector)
    ticker ? fetchYFQuoteFull(ticker) : Promise.resolve(null),

    // 2. Daily 1y chart (SMA/RSI calculations, 1Y return)
    (ticker && !isMF) ? fetchYFChartData(ticker, '1y', '1d') : Promise.resolve(null),

    // 3. Monthly 5y chart (3Y/5Y CAGR)
    ticker ? fetchYFChartData(ticker, '5y', '1mo') : Promise.resolve(null),

    // 4. News: try YF search first
    fetchYFSearchNews(assetName || ticker),

    // 5. NSE India (authoritative Indian live price)
    (isIndian && !isMF) ? fetchNSEQuote(assetName) : Promise.resolve(null),

    // 6. AMFI NAV (mutual funds)
    isMF ? fetchAMFINav(assetName) : Promise.resolve(null),
  ]);

  const quote        = quoteRes.status   === 'fulfilled' ? quoteRes.value   : null;
  const dailyChart   = dailyRes.status   === 'fulfilled' ? dailyRes.value   : null;
  const monthlyChart = monthlyRes.status === 'fulfilled' ? monthlyRes.value : null;
  let   news         = newsRes.status    === 'fulfilled' ? (newsRes.value  || []) : [];
  const nseData      = nseRes.status     === 'fulfilled' ? nseRes.value     : null;
  const amfiData     = amfiRes.status    === 'fulfilled' ? amfiRes.value    : null;

  const dailyCloses   = getChartCloses(dailyChart);
  const monthlyCloses = getChartCloses(monthlyChart);

  // ── News fallback: Google News RSS if YF returned nothing ────────────────────
  if (!news.length && assetName) {
    news = await fetchGoogleNewsRSS(assetName);
  }

  console.log(`[prefetch] quote=${quote ? 'OK' : 'FAIL'} daily=${dailyCloses.length}pt monthly=${monthlyCloses.length}pt news=${news.length} nse=${!!nseData} amfi=${!!amfiData}`);

  const ctx = compileRawMarketContext({
    symbol: ticker, assetName, assetType,
    quote, dailyCloses, monthlyCloses,
    news, nseData, amfiData,
  });

  if (!ctx) {
    console.warn('[prefetch] Context is empty — all sources failed. AI will use knowledge only.');
    return '';
  }

  return '\n\n### RAW MARKET CONTEXT (pre-fetched by server — map these values directly into the JSON fields):\n'
    + ctx
    + '### END RAW MARKET CONTEXT\n\n';
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
