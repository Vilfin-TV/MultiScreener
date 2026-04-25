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
const MAX_TOKENS  = 1200;
const TEMPERATURE = 0.6;

// ─── System prompt ────────────────────────────────────────────────────────────
const SYSTEM_PROMPT = (date) =>
  `You are the Market Assistant for VilfinTV — an institutional-grade financial intelligence platform.

Your role: Provide precise, research-quality analysis on equities, indices, ETFs, commodities, crypto, forex, and macro themes for investors in India and globally.

Today's date: ${date}

Response guidelines:
- Use **Markdown** formatting: headers (##), bold (**key figures**), bullet lists
- Lead with the most actionable insight in the first sentence
- Cite specific prices, percentages, and dates when available
- Keep responses concise: under 400 words unless the topic demands depth
- Never speculate without flagging it as opinion
- Never recommend specific buy/sell actions — provide analysis only
- Close with 2-3 relevant follow-up areas the user might explore`;

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

    // ── Interactive AI query endpoint ──────────────────────────────────────────
    if ((url.pathname === '/query' || url.pathname === '/ask') && request.method === 'POST') {
      let body;
      try { body = await request.json(); } catch {
        return json({ error: 'Invalid JSON body' }, CORS, 400);
      }

      const prompt   = (body.prompt || body.query || body.q || '').trim();
      const provider = (body.provider || '').toLowerCase().trim();

      if (!prompt || prompt.length < 2) {
        return json({ error: 'prompt is required' }, CORS, 400);
      }
      if (prompt.length > 32000) {
        return json({ error: 'prompt too long (max 32000 chars)' }, CORS, 400);
      }

      try {
        const result = await handleQuery(prompt, env, provider);
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
// STEP A — LIVE MARKET CONTEXT
// ═══════════════════════════════════════════════════════════════════════════════
async function fetchLiveContext(prompt) {
  const parts = [];

  // ── Yahoo Finance search ───────────────────────────────────────────────────
  try {
    const yfUrl = 'https://query1.finance.yahoo.com/v1/finance/search'
      + '?q=' + encodeURIComponent(prompt.slice(0, 100))
      + '&quotesCount=4&newsCount=4&enableFuzzyQuery=false&lang=en-US';

    const yfRes = await fetch(yfUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)',
        'Accept':     'application/json',
      },
      signal: AbortSignal.timeout(5000),
    });

    if (yfRes.ok) {
      const yfData = await yfRes.json();
      const quotes = (yfData.quotes || []).slice(0, 4).filter(q => q.symbol)
        .map(q => `${q.longname || q.shortname || q.symbol} (${q.symbol}, ${q.typeDisp || q.quoteType || ''})`)
        .filter(Boolean);
      const news = (yfData.news || []).slice(0, 4).filter(n => n.title)
        .map(n => `• ${n.title}${n.publisher ? ' — ' + n.publisher : ''}`);
      if (quotes.length) parts.push('**Relevant instruments:** ' + quotes.join(', '));
      if (news.length)   parts.push('**Recent headlines:**\n' + news.join('\n'));
    }
  } catch { /* non-fatal */ }

  // ── DuckDuckGo Instant Answer ──────────────────────────────────────────────
  try {
    const ddgUrl = 'https://api.duckduckgo.com/?q='
      + encodeURIComponent(prompt.slice(0, 120) + ' stock market')
      + '&format=json&no_html=1&skip_disambig=1&no_redirect=1';

    const ddgRes = await fetch(ddgUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)' },
      signal: AbortSignal.timeout(4000),
    });

    if (ddgRes.ok) {
      const ddg      = await ddgRes.json();
      const abstract = ddg.AbstractText || ddg.Answer || '';
      if (abstract && abstract.length > 40) {
        parts.push('**Context snippet:** ' + abstract.slice(0, 400));
      }
    }
  } catch { /* non-fatal */ }

  return parts.length
    ? '---\n**Live market context (auto-fetched):**\n' + parts.join('\n\n') + '\n---\n\n'
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
async function handleQuery(prompt, env, providerHint) {
  const today       = new Date().toDateString();
  const liveContext = await fetchLiveContext(prompt);

  const messages = [
    { role: 'system', content: SYSTEM_PROMPT(today) },
    { role: 'user',   content: liveContext + prompt },
  ];

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
