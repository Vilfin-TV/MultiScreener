/**
 * update-streams.js
 * ─────────────────
 * Runs daily via GitHub Actions (.github/workflows/update-tv.yml).
 * For each channel that has a `channelId`, queries the YouTube Data API
 * to find the current live-stream video ID and updates streams.json.
 *
 * Requires:  YOUTUBE_API_KEY environment variable (set as a GitHub Secret)
 * Usage:     node update-streams.js
 */

'use strict';

const https = require('https');
const fs    = require('fs');
const path  = require('path');

const API_KEY      = process.env.YOUTUBE_API_KEY;
const STREAMS_FILE = path.join(__dirname, 'streams.json');
const DELAY_MS     = 250; // polite delay between API calls to avoid quota issues

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

/**
 * Returns the current live video ID for a YouTube channel, or null.
 * Uses the search.list endpoint with eventType=live.
 */
async function findLiveVideoId(channelId) {
  const url = `https://www.googleapis.com/youtube/v3/search` +
    `?part=id` +
    `&channelId=${encodeURIComponent(channelId)}` +
    `&eventType=live` +
    `&type=video` +
    `&maxResults=1` +
    `&key=${encodeURIComponent(API_KEY)}`;

  try {
    const data = await httpsGet(url);

    if (data.error) {
      const msg = data.error.message || JSON.stringify(data.error);
      // Quota exceeded — stop immediately to preserve remaining quota
      if (data.error.code === 403) {
        console.error(`⚠️  YouTube API quota exceeded. Stopping early.`);
        process.exit(0); // exit 0 so the Action doesn't fail the build
      }
      throw new Error(msg);
    }

    return data.items?.[0]?.id?.videoId ?? null;
  } catch (e) {
    console.warn(`  ⚠️  API error for channel ${channelId}: ${e.message}`);
    return null;
  }
}

// ─── Main ──────────────────────────────────────────────────────────────────

async function main() {
  const raw  = fs.readFileSync(STREAMS_FILE, 'utf8');
  const data = JSON.parse(raw);

  let updatedCount = 0;

  for (const ch of data.channels) {
    if (!ch.channelId) continue; // skip channels without a YouTube channel ID

    console.log(`🔍  Checking: ${ch.label} (channel: ${ch.channelId})`);
    const liveId = await findLiveVideoId(ch.channelId);
    await sleep(DELAY_MS);

    if (!liveId) {
      console.log(`    ↳ No live stream found — keeping existing videoId: ${ch.videoId}`);
      continue;
    }

    if (liveId === ch.videoId) {
      console.log(`    ↳ No change (${ch.videoId})`);
    } else {
      console.log(`    ↳ Updated: ${ch.videoId} → ${liveId}`);
      ch.videoId = liveId;
      updatedCount++;
    }
  }

  if (updatedCount > 0) {
    data.updated = new Date().toISOString();
    fs.writeFileSync(STREAMS_FILE, JSON.stringify(data, null, 2) + '\n', 'utf8');
    console.log(`\n✅  ${updatedCount} stream(s) updated. streams.json written.`);
  } else {
    console.log('\n✔  All stream IDs are current. No changes needed.');
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
