#!/usr/bin/env node
/**
 * Fetches live market data from Yahoo Finance and writes data/market_sentiment.json.
 * Uses crumb-based auth (primary) and per-symbol chart API (fallback).
 */

const https = require('https');
const fs    = require('fs');
const path  = require('path');

const MARKETS = [
  {country:'US',        flag:'🇺🇸', index:'S&P 500',    symbol:'^GSPC'},
  {country:'India',     flag:'🇮🇳', index:'NIFTY 50',   symbol:'^NSEI'},
  {country:'Japan',     flag:'🇯🇵', index:'Nikkei 225', symbol:'^N225'},
  {country:'Europe',    flag:'🇪🇺', index:'STOXX 50',   symbol:'^STOXX50E'},
  {country:'China',     flag:'🇨🇳', index:'SSE Comp.',  symbol:'000001.SS'},
  {country:'Korea',     flag:'🇰🇷', index:'KOSPI',      symbol:'^KS11'},
  {country:'Brazil',    flag:'🇧🇷', index:'IBOVESPA',   symbol:'^BVSP'},
  {country:'Australia', flag:'🇦🇺', index:'ASX 200',    symbol:'^AXJO'},
  {country:'Taiwan',    flag:'🇹🇼', index:'TWII',       symbol:'^TWII'},
];

function calcZone(chg) {
  if (chg > 1.5)  return 'Extreme Greed';
  if (chg > 0.5)  return 'Greed';
  if (chg > -0.5) return 'Neutral';
  if (chg > -1.5) return 'Fear';
  return 'Extreme Fear';
}

const BASE_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'en-US,en;q=0.9',
  'Connection': 'keep-alive',
};

function httpsGet(url, extraHeaders = {}) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { ...BASE_HEADERS, ...extraHeaders }, timeout: 12000 }, res => {
      const chunks = [];
      const setCookies = res.headers['set-cookie'] || [];
      res.on('data', d => chunks.push(d));
      res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString(), setCookies }));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/* ── Approach 1: crumb-based quote API ── */
async function fetchWithCrumb() {
  // Get consent cookie
  const init = await httpsGet('https://fc.yahoo.com');
  const cookies = (init.setCookies || []).map(c => c.split(';')[0]).join('; ');

  // Get crumb
  const crumbRes = await httpsGet('https://query1.finance.yahoo.com/v1/test/getcrumb', { Cookie: cookies });
  if (crumbRes.status !== 200) throw new Error(`crumb HTTP ${crumbRes.status}`);
  const crumb = crumbRes.body.trim();
  if (!crumb || crumb.includes('<') || crumb.length > 20) throw new Error('bad crumb: ' + crumb.slice(0, 30));

  const syms = MARKETS.map(m => encodeURIComponent(m.symbol)).join(',');
  const url = `https://query1.finance.yahoo.com/v8/finance/quote?symbols=${syms}&crumb=${encodeURIComponent(crumb)}`;
  const quotesRes = await httpsGet(url, { Cookie: cookies });
  if (quotesRes.status !== 200) throw new Error(`quotes HTTP ${quotesRes.status}`);
  const j = JSON.parse(quotesRes.body);
  const results = j?.quoteResponse?.result;
  if (!results || !results.length) throw new Error('empty result');
  return results;
}

/* ── Approach 2: per-symbol chart API ── */
async function fetchChartPerSymbol() {
  const results = [];
  for (const m of MARKETS) {
    try {
      const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(m.symbol)}?interval=1d&range=5d`;
      const res = await httpsGet(url);
      if (res.status !== 200) { console.warn(`  chart ${m.symbol}: HTTP ${res.status}`); results.push(null); continue; }
      const j = JSON.parse(res.body);
      const meta = j?.chart?.result?.[0]?.meta;
      if (!meta) { console.warn(`  chart ${m.symbol}: no meta`); results.push(null); continue; }
      const price = meta.regularMarketPrice || 0;
      const prev  = meta.previousClose || meta.chartPreviousClose || price;
      const chg   = meta.regularMarketChangePercent || (prev ? (price - prev) / prev * 100 : 0);
      results.push({ symbol: m.symbol, regularMarketPrice: price, regularMarketChangePercent: chg });
      console.log(`  chart OK ${m.symbol}: ${chg.toFixed(2)}%`);
    } catch (e) {
      console.warn(`  chart ${m.symbol}: ${e.message}`);
      results.push(null);
    }
    await sleep(400); // be respectful to Yahoo servers
  }
  return results.filter(Boolean);
}

/* ── Approach 3: query2 v7 (sometimes different CORS behaviour) ── */
async function fetchQuery2() {
  const syms = MARKETS.map(m => encodeURIComponent(m.symbol)).join(',');
  const url = `https://query2.finance.yahoo.com/v7/finance/quote?symbols=${syms}&corsDomain=finance.yahoo.com`;
  const res = await httpsGet(url, { Referer: 'https://finance.yahoo.com/' });
  if (res.status !== 200) throw new Error(`HTTP ${res.status}`);
  const j = JSON.parse(res.body);
  const results = j?.quoteResponse?.result;
  if (!results || !results.length) throw new Error('empty');
  return results;
}

/* ── Fetch full weekly history (last 7 trading days via 10-day chart API) ── */
async function fetchWeeklyHistory() {
  console.log('\nFetching weekly history via chart API…');
  const historyMap = {}; // date → { country → {country, change, zoneCls} }

  for (const m of MARKETS) {
    try {
      const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(m.symbol)}?interval=1d&range=10d`;
      const res = await httpsGet(url);
      if (res.status !== 200) { console.warn(`  ${m.symbol}: HTTP ${res.status}`); continue; }
      const j      = JSON.parse(res.body);
      const result = j?.chart?.result?.[0];
      if (!result) { console.warn(`  ${m.symbol}: no chart result`); continue; }

      const timestamps = result.timestamp || [];
      const closes     = result.indicators?.quote?.[0]?.close || [];

      for (let i = 1; i < timestamps.length; i++) {
        const close    = closes[i];
        const prevClose = closes[i - 1];
        if (close == null || prevClose == null || prevClose === 0) continue;

        const date = new Date(timestamps[i] * 1000).toISOString().slice(0, 10);
        const chg  = Math.round(((close - prevClose) / prevClose) * 10000) / 100;
        const zone = calcZone(chg);

        if (!historyMap[date]) historyMap[date] = {};
        historyMap[date][m.country] = {
          country: m.country,
          change:  chg,
          zoneCls: zone.toLowerCase().replace(/\s+/g, '-'),
        };
      }
      console.log(`  ✓ ${m.symbol}: ${timestamps.length} data points`);
    } catch (e) {
      console.warn(`  ✗ ${m.symbol}: ${e.message}`);
    }
    await sleep(300);
  }

  // Sort dates newest-first; only keep days where ≥5 markets reported (handles market holidays)
  return Object.keys(historyMap)
    .sort()
    .reverse()
    .filter(d => Object.keys(historyMap[d]).length >= 5)
    .slice(0, 7)
    .map(d => ({ date: d, markets: Object.values(historyMap[d]) }));
}

async function main() {
  let results = [];

  console.log('Approach 1: crumb-based quote API…');
  try {
    results = await fetchWithCrumb();
    console.log(`✓ Got ${results.length} quotes via crumb API`);
  } catch (e) {
    console.warn('✗ Crumb API:', e.message);
  }

  if (!results.length) {
    console.log('Approach 2: query2 v7 API…');
    try {
      results = await fetchQuery2();
      console.log(`✓ Got ${results.length} quotes via query2`);
    } catch (e) {
      console.warn('✗ query2:', e.message);
    }
  }

  if (!results.length) {
    console.log('Approach 3: per-symbol chart API…');
    try {
      results = await fetchChartPerSymbol();
      console.log(`✓ Got ${results.length} quotes via chart API`);
    } catch (e) {
      console.error('✗ chart API:', e.message);
    }
  }

  if (!results.length) {
    console.error('All data sources failed — keeping existing JSON.');
    process.exit(1);
  }

  const markets = MARKETS.map(m => {
    const q   = results.find(r => r.symbol === m.symbol) || {};
    const chg = q.regularMarketChangePercent || 0;
    return {
      country: m.country, flag: m.flag, index: m.index, symbol: m.symbol,
      price:   Math.round((q.regularMarketPrice || 0) * 100) / 100,
      change:  Math.round(chg * 100) / 100,
      zone:    calcZone(chg),
      zoneCls: calcZone(chg).toLowerCase().replace(/\s+/g, '-'),
    };
  });

  // ── Build full weekly history from 10-day chart API ──────────────────────
  const outPath = path.join(__dirname, '..', 'data', 'market_sentiment.json');

  let history = [];
  try {
    history = await fetchWeeklyHistory();
    console.log(`✓ History: ${history.length} trading days from chart API`);
  } catch (e) {
    console.warn('✗ Weekly history fetch failed:', e.message);
  }

  // Fallback: if chart history empty, use existing JSON + today's entry
  if (!history.length) {
    console.log('  Falling back to single-day accumulation…');
    let existingHistory = [];
    try {
      const existing = JSON.parse(fs.readFileSync(outPath, 'utf8'));
      if (Array.isArray(existing.history)) existingHistory = existing.history;
    } catch (_) {}
    const todayStr   = new Date().toISOString().slice(0, 10);
    const todayEntry = {
      date:    todayStr,
      markets: markets.map(m => ({ country: m.country, change: m.change, zoneCls: m.zoneCls })),
    };
    history = [todayEntry, ...existingHistory.filter(d => d.date !== todayStr)].slice(0, 7);
  }

  const out = { updated: new Date().toISOString(), source: 'yahoo', markets, history };
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2) + '\n', 'utf8');
  console.log(`\nWritten → ${outPath}`);
  markets.forEach(m => console.log(`  ${m.flag} ${m.country}: ${m.change > 0 ? '+' : ''}${m.change}%  →  ${m.zone}`));
}

main();
