#!/usr/bin/env node
/**
 * Fetches TODAY + YESTERDAY sports data from TheSportsDB (free tier, no API key)
 * and writes data/sports.json with live / today / yesterday buckets.
 *
 * Schema per sport:
 *   { live: [{name, events}], today: [{name, events}], yesterday: [{name, events}], liveCount: N }
 *
 * Runs via GitHub Actions every 5 minutes (.github/workflows/sports.yml)
 */
'use strict';

const https = require('https');
const fs    = require('fs');
const path  = require('path');

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
  'After Extra Time', 'After Penalties', 'Finished', 'Complete',
  'Post', 'Final',
]);

/* ── HTTP helper ── */
function httpsGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MultiScreener-SportsFetcher/1.1)',
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

/* ── Fetch events for one sport on a specific date ── */
async function fetchSportEvents(sportQuery, date) {
  const url = `https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=${date}&s=${encodeURIComponent(sportQuery)}`;
  const res = await httpsGet(url);
  if (res.status !== 200) throw new Error(`HTTP ${res.status}`);
  const j = JSON.parse(res.body);
  return j.events || j.event || [];
}

/* ── Split today's events into live / today (finished + upcoming) ── */
function groupTodayBuckets(events) {
  const liveBuckets  = {};
  const liveOrder    = [];
  const todayBuckets = {};
  const todayOrder   = [];
  let liveCount = 0;

  for (const ev of events) {
    const lg = ev.strLeague || 'Unknown';
    const hs = ev.intHomeScore != null ? String(ev.intHomeScore) : null;
    const as = ev.intAwayScore != null ? String(ev.intAwayScore) : null;

    const isFinished   = FINISHED_STATUSES.has(ev.strStatus);
    const isNotStarted = !ev.strStatus || ev.strStatus === 'Not Started' ||
                         ev.strStatus === '' || ev.strStatus === 'NS' ||
                         ev.strStatus === 'Postponed' || ev.strStatus === 'Cancelled' ||
                         ev.strStatus === 'Abandoned';
    const isLive       = !isFinished && !isNotStarted;

    const match = {
      home:      ev.strHomeTeam  || '?',
      away:      ev.strAwayTeam  || '?',
      homeScore: hs,
      awayScore: as,
      status:    ev.strProgress || ev.strStatus || '',
      isLive,
      isFinished,
    };

    if (isLive) {
      liveCount++;
      if (!liveBuckets[lg]) { liveBuckets[lg] = []; liveOrder.push(lg); }
      liveBuckets[lg].push(match);
    } else {
      if (!todayBuckets[lg]) { todayBuckets[lg] = []; todayOrder.push(lg); }
      todayBuckets[lg].push(match);
    }
  }

  return {
    live:      liveOrder.map(name  => ({ name, events: liveBuckets[name]  })),
    today:     todayOrder.map(name => ({ name, events: todayBuckets[name] })),
    liveCount,
  };
}

/* ── Group yesterday's events by league (all finished) ── */
function groupAllByLeague(events) {
  const buckets = {};
  const order   = [];

  for (const ev of events) {
    const lg = ev.strLeague || 'Unknown';
    if (!buckets[lg]) { buckets[lg] = []; order.push(lg); }

    const hs = ev.intHomeScore != null ? String(ev.intHomeScore) : null;
    const as = ev.intAwayScore != null ? String(ev.intAwayScore) : null;
    const isFinished   = FINISHED_STATUSES.has(ev.strStatus);
    const isNotStarted = !ev.strStatus || ev.strStatus === 'Not Started' ||
                         ev.strStatus === '' || ev.strStatus === 'NS' ||
                         ev.strStatus === 'Postponed' || ev.strStatus === 'Cancelled' ||
                         ev.strStatus === 'Abandoned';
    const isLive       = !isFinished && !isNotStarted;

    buckets[lg].push({
      home:      ev.strHomeTeam  || '?',
      away:      ev.strAwayTeam  || '?',
      homeScore: hs,
      awayScore: as,
      status:    ev.strProgress || ev.strStatus || '',
      isLive,
      isFinished,
    });
  }

  return order.map(name => ({ name, events: buckets[name] }));
}

/* ── Main ── */
async function main() {
  const now = new Date();

  // UTC dates
  const todayStr = now.toISOString().slice(0, 10);
  const yd = new Date(now);
  yd.setUTCDate(yd.getUTCDate() - 1);
  const yestStr = yd.toISOString().slice(0, 10);

  console.log(`Build Sports — today: ${todayStr}  |  yesterday: ${yestStr}\n`);

  const sports = {};

  for (const sport of SPORTS) {
    process.stdout.write(`  ${sport.key.padEnd(12)}: `);
    try {
      // Fetch today and yesterday sequentially (respect free tier rate limits)
      let todayEvents = [];
      let yestEvents  = [];

      try {
        todayEvents = await fetchSportEvents(sport.query, todayStr);
      } catch (e) {
        console.warn(`[today err: ${e.message}]`);
      }
      await sleep(350);

      try {
        yestEvents = await fetchSportEvents(sport.query, yestStr);
      } catch (e) {
        console.warn(`[yesterday err: ${e.message}]`);
      }

      const { live, today, liveCount } = groupTodayBuckets(todayEvents);
      const yesterday = groupAllByLeague(yestEvents);

      sports[sport.key] = { live, today, yesterday, liveCount };

      const todayTotal = todayEvents.length;
      const yestTotal  = yestEvents.length;
      console.log(`${liveCount} live | ${todayTotal - liveCount} today | ${yestTotal} yesterday`);

    } catch (e) {
      console.log(`ERROR — ${e.message}`);
      sports[sport.key] = { live: [], today: [], yesterday: [], liveCount: 0 };
    }

    await sleep(350); // respectful pacing between sports
  }

  const out = {
    generated: new Date().toISOString(),
    date:      todayStr,
    yesterday: yestStr,
    sports,
  };

  const outPath = path.join(__dirname, '..', 'data', 'sports.json');
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2) + '\n', 'utf8');

  console.log(`\n✓ Written → ${outPath}`);
}

main().catch(e => { console.error('\nFATAL:', e.message); process.exit(1); });
