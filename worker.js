/**
 * VilfinTV Market Assistant — Cloudflare Worker
 * ═══════════════════════════════════════════════
 *
 * DEPLOY STEPS (Cloudflare Dashboard):
 *  1. Workers & Pages → Create → Worker → paste this file → Save & Deploy
 *  2. Settings → Variables → Secret → add GROQ_API_KEY  (your Groq key)
 *  3. Optional: add DEEPSEEK_API_KEY as fallback
 *  4. Settings → Triggers → add custom domain or use *.workers.dev URL
 *  5. Paste the Worker URL into config.js → WORKER_URL
 *
 * CORS: locked to vilfin-tv.github.io in production.
 *       Wildcard (*) is active during testing — tighten before going live.
 *
 * PIPELINE (per request):
 *  Step A — Live Context: Yahoo Finance Search + DuckDuckGo Instant Answer
 *  Step B — AI Response:  Groq (Llama 3.3 70B) → DeepSeek fallback → Pollinations
 *
 * QUOTA:
 *  Groq free tier:  6,000 requests/day, 500,000 tokens/day
 *  DeepSeek:        $0.14 / M input tokens (cache hit: $0.014)
 *  Pollinations:    free, no key needed (emergency fallback)
 */

'use strict';

// ─── Allowed origins (add your custom domain here if needed) ──────────────
const ALLOWED_ORIGINS = [
  'https://vilfin-tv.github.io',
  'https://vilfintv.github.io',
  'http://127.0.0.1:5500',   // local dev (Live Server)
  'http://localhost:5500',
  'http://localhost:3000',
];

// ─── AI Model config ──────────────────────────────────────────────────────
const GROQ_ENDPOINT     = 'https://api.groq.com/openai/v1/chat/completions';
const DEEPSEEK_ENDPOINT = 'https://api.deepseek.com/chat/completions';
const GROQ_MODEL        = 'llama-3.3-70b-versatile';
const DEEPSEEK_MODEL    = 'deepseek-chat';
const MAX_TOKENS        = 1200;
const TEMPERATURE       = 0.6;

// ─── System prompt ────────────────────────────────────────────────────────
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

// ═══════════════════════════════════════════════════════════════════════════
// MAIN FETCH HANDLER
// ═══════════════════════════════════════════════════════════════════════════
export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const allowOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];

    const CORS = {
      'Access-Control-Allow-Origin':  allowOrigin,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age':       '86400',
    };

    // ── Preflight ──────────────────────────────────────────────────────────
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    const url = new URL(request.url);

    // ── Health check ───────────────────────────────────────────────────────
    if (url.pathname === '/' || url.pathname === '/health') {
      return json({ status: 'ok', service: 'VilfinTV Market Assistant' }, CORS);
    }

    // ── Main AI query endpoint ─────────────────────────────────────────────
    if ((url.pathname === '/query' || url.pathname === '/ask') && request.method === 'POST') {
      let body;
      try { body = await request.json(); } catch {
        return json({ error: 'Invalid JSON body' }, CORS, 400);
      }

      const prompt = (body.prompt || body.query || body.q || '').trim();
      if (!prompt || prompt.length < 2) {
        return json({ error: 'prompt is required' }, CORS, 400);
      }
      if (prompt.length > 2000) {
        return json({ error: 'prompt too long (max 2000 chars)' }, CORS, 400);
      }

      try {
        const result = await handleQuery(prompt, env);
        return json({ result }, CORS);
      } catch (err) {
        console.error('handleQuery error:', err.message);
        return json({ error: 'Service temporarily unavailable. Please retry.' }, CORS, 503);
      }
    }

    return json({ error: 'Not found' }, CORS, 404);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// STEP A — LIVE MARKET CONTEXT
// ═══════════════════════════════════════════════════════════════════════════
async function fetchLiveContext(prompt) {
  const parts = [];

  // ── Yahoo Finance search (quotes + recent news headlines) ──────────────
  try {
    const yfUrl = 'https://query1.finance.yahoo.com/v1/finance/search'
      + '?q=' + encodeURIComponent(prompt.slice(0, 100))
      + '&quotesCount=4&newsCount=4&enableFuzzyQuery=false&lang=en-US';

    const yfRes = await fetch(yfUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)',
        'Accept': 'application/json',
      },
      signal: AbortSignal.timeout(5000),
    });

    if (yfRes.ok) {
      const yfData = await yfRes.json();

      // Quoted symbols
      const quotes = (yfData.quotes || [])
        .slice(0, 4)
        .filter(q => q.symbol)
        .map(q => `${q.longname || q.shortname || q.symbol} (${q.symbol}, ${q.typeDisp || q.quoteType || ''})`)
        .filter(Boolean);

      // News headlines with publisher
      const news = (yfData.news || [])
        .slice(0, 4)
        .filter(n => n.title)
        .map(n => `• ${n.title}${n.publisher ? ' — ' + n.publisher : ''}`);

      if (quotes.length) parts.push('**Relevant instruments:** ' + quotes.join(', '));
      if (news.length)   parts.push('**Recent headlines:**\n' + news.join('\n'));
    }
  } catch { /* non-fatal */ }

  // ── DuckDuckGo Instant Answer (definitions / factual snippets) ─────────
  try {
    const ddgUrl = 'https://api.duckduckgo.com/?q='
      + encodeURIComponent(prompt.slice(0, 120) + ' stock market')
      + '&format=json&no_html=1&skip_disambig=1&no_redirect=1';

    const ddgRes = await fetch(ddgUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; VilfinTV/1.0)' },
      signal: AbortSignal.timeout(4000),
    });

    if (ddgRes.ok) {
      const ddg = await ddgRes.json();
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

// ═══════════════════════════════════════════════════════════════════════════
// STEP B — AI GENERATION
// ═══════════════════════════════════════════════════════════════════════════
async function handleQuery(prompt, env) {
  const today       = new Date().toDateString();
  const liveContext = await fetchLiveContext(prompt);

  const messages = [
    { role: 'system', content: SYSTEM_PROMPT(today) },
    { role: 'user',   content: liveContext + prompt },
  ];

  // ── Provider 1: Groq (Llama 3.3 70B — free tier, high quota) ──────────
  if (env.GROQ_API_KEY) {
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
          max_tokens:  MAX_TOKENS,
          temperature: TEMPERATURE,
          stream:      false,
        }),
        signal: AbortSignal.timeout(30000),
      });

      if (res.ok) {
        const data = await res.json();
        const text = data.choices?.[0]?.message?.content?.trim();
        if (text && text.length > 20) return text;
      } else {
        const errBody = await res.text();
        console.warn('Groq error', res.status, errBody.slice(0, 200));
      }
    } catch (e) {
      console.warn('Groq fetch failed:', e.message);
    }
  }

  // ── Provider 2: DeepSeek (cheap, high quality) ──────────────────────────
  if (env.DEEPSEEK_API_KEY) {
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
          max_tokens:  MAX_TOKENS,
          temperature: TEMPERATURE,
          stream:      false,
        }),
        signal: AbortSignal.timeout(30000),
      });

      if (res.ok) {
        const data = await res.json();
        const text = data.choices?.[0]?.message?.content?.trim();
        if (text && text.length > 20) return text;
      }
    } catch (e) {
      console.warn('DeepSeek fetch failed:', e.message);
    }
  }

  // ── Provider 3: Pollinations (free, no key — emergency fallback) ────────
  try {
    const sysShort = `Financial Market Assistant. ${today}. Use Markdown.`;
    const res = await fetch('https://text.pollinations.ai/openai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'openai-large',
        messages: [
          { role: 'system', content: sysShort },
          { role: 'user',   content: liveContext + prompt },
        ],
        stream:  false,
        private: true,
      }),
      signal: AbortSignal.timeout(45000),
    });

    if (res.ok) {
      const data = await res.json();
      const text = data?.choices?.[0]?.message?.content?.trim();
      if (text && text.length > 20) return text;
    }
  } catch (e) {
    console.warn('Pollinations fallback failed:', e.message);
  }

  throw new Error('All AI providers unavailable');
}

// ─── Utility ──────────────────────────────────────────────────────────────
function json(data, corsHeaders, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders },
  });
}
