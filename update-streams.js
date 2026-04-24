/**
 * update-streams.js
 * ─────────────────
 * Runs daily via GitHub Actions (.github/workflows/update-tv.yml).
 *
 * Strategy (two-step, quota-efficient):
 *  1. videos.list  — check if the existing videoId is still live RIGHT NOW.
 *                    Cost: 1 unit per call. Handles 24/7 persistent streams
 *                    (Al Jazeera, BBC, Sky News, etc.) without a search.
 *  2. search.list  — only called when step 1 says the video is offline.
 *                    Cost: 100 units per call. Finds the replacement live ID.
 *
 * Requires:  YOUTUBE_API_KEY environment variable (set as a GitHub Secret).
 * Usage:     node update-streams.js
 */

'use strict';

const https = require('https');
const fs    = require('fs');
const path  = require('path');

const API_KEY      = process.env.YOUTUBE_API_KEY;
const STREAMS_FILE = path.join(__dirname, 'streams.json');
const DELAY_MS     = 200; // polite gap between API calls

if (!API_KEY) {
  console.error('❌  YOUTUBE_API_KEY is not set. Add it as a GitHub Secret.');
  process.exit(1);
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function httpsGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error('JSON parse error: ' + e.message)); }
      });
    }).on('error', reject);
  });
}

function checkQuota(data) {
  if (data.error) {
    const msg = data.error.message || JSON.stringify(data.error);
    if (data.error.code === 403) {
      console.error('⚠️  YouTube API quota exceeded. Stopping early.');
      process.exit(0); // exit 0 — don't fail the build over quota
    }
    throw new Error(msg);
  }
}

/**
 * Step 1 — videos.list (cost: 1 unit)
 * Returns true if the given videoId is currently live.
 */
async function isVideoCurrentlyLive(videoId) {
  const url = `https://www.googleapis.com/youtube/v3/videos` +
    `?part=snippet` +
    `&id=${encodeURIComponent(videoId)}` +
    `&key=${encodeURIComponent(API_KEY)}`;

  const data = await httpsGet(url);
  checkQuota(data);
  // liveBroadcastContent: 'live' | 'upcoming' | 'none'
  return data.items?.[0]?.snippet?.liveBroadcastContent === 'live';
}

/**
 * Step 2 — search.list (cost: 100 units)
 * Only called when the existing video is offline.
 * Returns a replacement live videoId for the channel, or null.
 */
async function findLiveVideoId(channelId) {
  const url = `https://www.googleapis.com/youtube/v3/search` +
    `?part=id` +
    `&channelId=${encodeURIComponent(channelId)}` +
    `&eventType=live` +
    `&type=video` +
    `&maxResults=1` +
    `&key=${encodeURIComponent(API_KEY)}`;

  const data = await httpsGet(url);
  checkQuota(data);
  return data.items?.[0]?.id?.videoId ?? null;
}

// ─── Main ──────────────────────────────────────────────────────────────────

async function main() {
  const raw  = fs.readFileSync(STREAMS_FILE, 'utf8');
  const data = JSON.parse(raw);

  let updatedCount = 0;

  for (const ch of data.channels) {
    if (!ch.channelId) continue; // no channel ID → nothing to check

    process.stdout.write(`🔍  ${ch.label} … `);

    try {
      // ── Step 1: is the current video still live? ──────────────────────
      const stillLive = await isVideoCurrentlyLive(ch.videoId);
      await sleep(DELAY_MS);

      if (stillLive) {
        console.log(`✔ still live (${ch.videoId})`);
        continue; // nothing to do — keep existing ID
      }

      // ── Step 2: video offline — search for a replacement ──────────────
      console.log(`offline. Searching for replacement…`);
      const newId = await findLiveVideoId(ch.channelId);
      await sleep(DELAY_MS);

      if (!newId) {
        console.log(`    ↳ No live stream on channel right now — keeping ${ch.videoId}`);
        continue;
      }

      if (newId === ch.videoId) {
        console.log(`    ↳ Same ID returned by search — no change`);
      } else {
        console.log(`    ↳ Updated: ${ch.videoId} → ${newId}`);
        ch.videoId = newId;
        updatedCount++;
      }

    } catch (e) {
      console.log(`    ⚠️  Error: ${e.message} — skipping`);
    }
  }

  if (updatedCount > 0) {
    data.updated = new Date().toISOString();
    fs.writeFileSync(STREAMS_FILE, JSON.stringify(data, null, 2) + '\n', 'utf8');
    console.log(`\n✅  ${updatedCount} stream(s) updated. streams.json written.`);
  } else {
    console.log('\n✔  All streams current. No changes to commit.');
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
