#!/usr/bin/env node
/**
 * Fetches today's sports scores from TheSportsDB (free tier, no API key required)
 * and writes data/sports.json for the GitHub Pages static frontend.
 *
 * TheSportsDB endpoint:
 *   https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=YYYY-MM-DD&s=SPORT
 *
 * Runs via GitHub Actions every 15 minutes (.github/workflows/sports.yml)
 */

'use strict';

const https = require('https');
const fs    = require('fs');
const path  = require('path');

// Sports to fetch — key matches the frontend sport selector values
const SPORTS = [
  { key: 'football',   query: 'Soccer'      },
  { key: 'cricket',    query: 'Cricket'     },
  { key: 'basketball', query: 'Basketball'  },
  { key: 'tennis',     query: 'Tennis'      },
  { key: 'rugby',      query: 'Rugby Union' },
  { key: 'baseball',   query: 'Baseball'    },
  { key: 'hockey',     query: 'Ice Hockey'  },
];

const FINISHED_STATUSES = new Set([
  'Match Finished', 'FT', 'AP', 'AET', 'AOT', 'Full Time',
  'After Extra Time', 'After Penalties',
]);

/* ── HTTP helper ── */
function httpsGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MultiScreener-SportsFetcher/1.0)',
        'Accept': 'application/json',
      },
      timeout: 15000,
    }, res => {
      const chunks = [];
      res.on('data', d => chunks.push(d));
      res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString() }));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/* ── Fetch events for one sport ── */
async function fetchSportEvents(sportQuery, date) {
  const url = `https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=${date}&s=${encodeURIComponent(sportQuery)}`;
  const res = await httpsGet(url);
  if (res.status !== 200) throw new Error(`HTTP ${res.status}`);
  const j = JSON.parse(res.body);
  // TheSportsDB uses 'events' for eventsday endpoint (note: NOT 'event')
  return j.events || j.event || [];
}

/* ── Group raw events into league buckets ── */
function groupByLeague(events) {
  const byLeague = {};
  const order    = [];

  for (const ev of events) {
    const lg = ev.strLeague || 'Unknown';
    if (!byLeague[lg]) { byLeague[lg] = []; order.push(lg); }

    const hs = ev.intHomeScore != null ? String(ev.intHomeScore) : null;
    const as = ev.intAwayScore != null ? String(ev.intAwayScore) : null;
    const isFinished = FINISHED_STATUSES.has(ev.strStatus);
    const isLive     = !isFinished &&
                       !!ev.strStatus &&
                       ev.strStatus !== 'Not Started' &&
                       ev.strStatus !== '';

    byLeague[lg].push({
      home:       ev.strHomeTeam  || '?',
      away:       ev.strAwayTeam  || '?',
      homeScore:  hs,
      awayScore:  as,
      status:     ev.strProgress || ev.strStatus || '',
      isLive,
      isFinished,
    });
  }

  return order.map(name => ({ name, events: byLeague[name] }));
}

/* ── Main ── */
async function main() {
  const date = new Date().toISOString().slice(0, 10); // UTC date: YYYY-MM-DD
  console.log(`Build Sports — date: ${date}\n`);

  const sports = {};

  for (const sport of SPORTS) {
    process.stdout.write(`  ${sport.key.padEnd(12)}: `);
    try {
      const events = await fetchSportEvents(sport.query, date);
      sports[sport.key] = groupByLeague(events);
      const total = events.length;
      const leagues = sports[sport.key].length;
      console.log(`${total} events across ${leagues} league(s)`);
    } catch (e) {
      console.log(`ERROR — ${e.message}`);
      sports[sport.key] = [];
    }
    await sleep(500); // be respectful to TheSportsDB free tier
  }

  const out = {
    generated: new Date().toISOString(),
    date,
    sports,
  };

  const outPath = path.join(__dirname, '..', 'data', 'sports.json');
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2) + '\n', 'utf8');

  console.log(`\n✓ Written → ${outPath}`);
}

main().catch(e => { console.error('\nFATAL:', e.message); process.exit(1); });
