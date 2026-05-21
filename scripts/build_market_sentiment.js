#!/usr/bin/env node
/**
 * Fetches live market data from Yahoo Finance and writes data/market_sentiment.json.
 * Run by GitHub Actions every 30 minutes. No API key required.
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

function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    const opts = {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MarketSentimentBot/1.0)',
        'Accept': 'application/json',
      },
      timeout: 10000,
    };
    https.get(url, opts, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(body);
        } else {
          reject(new Error(`HTTP ${res.statusCode}`));
        }
      });
    }).on('error', reject).on('timeout', () => reject(new Error('Timeout')));
  });
}

async function main() {
  const syms = MARKETS.map(m => encodeURIComponent(m.symbol)).join(',');
  const url  = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${syms}&corsDomain=finance.yahoo.com`;

  let results = [];
  try {
    const raw  = await fetchUrl(url);
    const json = JSON.parse(raw);
    results = json?.quoteResponse?.result || [];
  } catch (err) {
    console.error('Yahoo Finance fetch failed:', err.message);
    process.exit(1);
  }

  const markets = MARKETS.map(m => {
    const q    = results.find(r => r.symbol === m.symbol) || {};
    const chg  = q.regularMarketChangePercent || 0;
    return {
      country: m.country,
      flag:    m.flag,
      index:   m.index,
      symbol:  m.symbol,
      price:   Math.round((q.regularMarketPrice || 0) * 100) / 100,
      change:  Math.round(chg * 100) / 100,
      zone:    calcZone(chg),
    };
  });

  const out = {
    updated: new Date().toISOString(),
    source:  'yahoo',
    markets,
  };

  const outPath = path.join(__dirname, '..', 'data', 'market_sentiment.json');
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2) + '\n', 'utf8');
  console.log(`Written ${outPath} — ${new Date().toISOString()}`);
  markets.forEach(m => console.log(`  ${m.flag} ${m.country}: ${m.change > 0 ? '+' : ''}${m.change}% → ${m.zone}`));
}

main();
