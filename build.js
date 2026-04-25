/**
 * VilfinTV — Market Data Build Script
 * ─────────────────────────────────────────────────────────────────────────────
 * PURPOSE:
 *   Calls the Cloudflare Worker to generate a fresh daily market briefing,
 *   then saves the result as data.json for the frontend to consume at runtime.
 *
 * SECURITY:
 *   The WORKER_URL is read EXCLUSIVELY from:
 *     • Local development:  .env file  (git-ignored, never committed)
 *     • GitHub Actions CI:  ${{ secrets.WORKER_URL }}  (stored as a GitHub Secret)
 *   The WORKER_URL is NEVER hardcoded, imported, or referenced in any
 *   frontend HTML, CSS, or client-side JavaScript file.
 *
 * USAGE:
 *   Local:          node build.js
 *   GitHub Actions: WORKER_URL=<secret> node build.js
 *
 * OUTPUT:
 *   data.json  — committed to the repo, read by the frontend on every page load
 */

'use strict';

const fs    = require('fs');
const path  = require('path');
const https = require('https');
const http  = require('http');

// ─── Load .env (local dev only — CI uses environment variables directly) ───
const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  const lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx < 1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim().replace(/^['"]|['"]$/g, '');
    if (key && !process.env[key]) process.env[key] = val;
  }
}

// ─── Validate required environment variable ────────────────────────────────
const WORKER_URL = (process.env.WORKER_URL || '').replace(/\/+$/, '');
if (!WORKER_URL) {
  console.error('\n❌  WORKER_URL is not set.\n');
  console.error('    For local development, create a .env file containing:');
  console.error('    WORKER_URL=https://x9-k2-p30-worker.vilfintv.workers.dev\n');
  console.error('    For GitHub Actions, add WORKER_URL as a repository Secret.\n');
  process.exit(1);
}

const OUTPUT_FILE = path.join(__dirname, 'data.json');
const ENDPOINT    = WORKER_URL + '/snapshot';

// ─── Configuration ─────────────────────────────────────────────────────────
const TIMEOUT_MS  = 90_000;   // 90 s — generous for cold Worker starts in CI
const MAX_RETRIES = 3;
const RETRY_BASE  = 4_000;    // 4 s, 8 s, 16 s back-off

// ─── HTTP/S request helper ─────────────────────────────────────────────────
function postJson(url, body) {
  return new Promise((resolve, reject) => {
    const parsed   = new URL(url);
    const lib      = parsed.protocol === 'https:' ? https : http;
    const payload  = JSON.stringify(body);

    const req = lib.request({
      hostname: parsed.hostname,
      port:     parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path:     parsed.pathname + parsed.search,
      method:   'POST',
      headers: {
        'Content-Type':   'application/json',
        'Content-Length': Buffer.byteLength(payload),
        'User-Agent':     'VilfinTV-BuildScript/1.0',
      },
    }, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch (e) {
          reject(new Error(
            `JSON parse error (HTTP ${res.statusCode}): ${e.message}\nBody: ${data.slice(0, 300)}`
          ));
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(TIMEOUT_MS, () => req.destroy(new Error(`Request timeout (${TIMEOUT_MS / 1000}s)`)));
    req.write(payload);
    req.end();
  });
}

// ─── Sleep helper ──────────────────────────────────────────────────────────
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ─── Fetch with exponential back-off retry ─────────────────────────────────
async function fetchWithRetry() {
  let lastErr;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      console.log(`  ⏳  Attempt ${attempt}/${MAX_RETRIES} → ${ENDPOINT}`);
      const response = await postJson(ENDPOINT, {});

      if (response.status !== 200) {
        throw new Error(
          `Worker returned HTTP ${response.status}: ${JSON.stringify(response.body).slice(0, 200)}`
        );
      }

      const snap = response.body;
      if (!snap.briefing || snap.briefing.length < 30) {
        throw new Error(
          `Worker returned empty/invalid briefing: ${JSON.stringify(snap).slice(0, 200)}`
        );
      }

      return snap;   // ✅ success
    } catch (err) {
      lastErr = err;
      console.warn(`  ⚠️   Attempt ${attempt} failed: ${err.message}`);
      if (attempt < MAX_RETRIES) {
        const delay = RETRY_BASE * Math.pow(2, attempt - 1);
        console.log(`  ↩️   Retrying in ${delay / 1000}s…`);
        await sleep(delay);
      }
    }
  }
  throw lastErr;
}

// ─── Graceful fallback data.json ───────────────────────────────────────────
function writeFallback(reason) {
  const existing = (() => {
    try { return JSON.parse(fs.readFileSync(OUTPUT_FILE, 'utf8')); } catch { return null; }
  })();

  if (existing && existing.briefing && existing.briefing.length > 30) {
    // Preserve the last successful briefing; just update the note
    existing._fallback_reason = reason;
    existing._fallback_time   = new Date().toISOString();
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(existing, null, 2) + '\n', 'utf8');
    console.log('ℹ️   Preserved previous data.json (Worker unreachable — stale data kept).');
  } else {
    // No previous data — write a minimal placeholder
    const placeholder = {
      generated: new Date().toISOString(),
      model:     'fallback',
      briefing: [
        '## Market Data Temporarily Unavailable',
        '',
        'The daily market briefing could not be retrieved at this time.',
        'Live data will resume on the next scheduled update.',
        '',
        '_Use the AI Assistant for real-time market analysis._',
      ].join('\n'),
      version:          '1.0',
      _fallback_reason: reason,
    };
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(placeholder, null, 2) + '\n', 'utf8');
    console.log('ℹ️   Wrote placeholder data.json (no previous data available).');
  }
}

// ─── Main ──────────────────────────────────────────────────────────────────
async function main() {
  console.log('');
  console.log('══════════════════════════════════════');
  console.log('  VilfinTV Market Data Build Script   ');
  console.log('══════════════════════════════════════');
  console.log(`  Date:     ${new Date().toUTCString()}`);
  console.log(`  Endpoint: /snapshot`);
  console.log(`  Output:   data.json`);
  console.log(`  Retries:  ${MAX_RETRIES}  |  Timeout: ${TIMEOUT_MS / 1000}s`);
  console.log('');

  let snap;
  try {
    snap = await fetchWithRetry();
  } catch (err) {
    // All retries exhausted — write fallback and exit 0 so CI does not fail
    console.error(`❌  All ${MAX_RETRIES} attempts failed: ${err.message}`);
    console.error('    Writing fallback data.json to avoid breaking the deployment.');
    writeFallback(err.message);
    console.log('');
    console.log('⚠️   Build completed with fallback — check Worker health.');
    console.log('');
    process.exit(0);   // 👈 exit 0 — CI keeps green, site stays functional
  }

  // ── Write data.json ──────────────────────────────────────────────────────
  const output = {
    generated: snap.generated || new Date().toISOString(),
    model:     snap.model     || 'unknown',
    briefing:  snap.briefing,
    version:   '1.0',
  };

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2) + '\n', 'utf8');

  // ── Summary ───────────────────────────────────────────────────────────────
  const preview   = output.briefing.replace(/\n/g, ' ').slice(0, 120);
  const wordCount = output.briefing.split(/\s+/).length;
  console.log('✅  data.json written successfully.');
  console.log(`    Generated : ${output.generated}`);
  console.log(`    Model     : ${output.model}`);
  console.log(`    Words     : ${wordCount}`);
  console.log(`    Preview   : ${preview}${wordCount > 20 ? '…' : ''}`);
  console.log('');
}

main().catch(err => {
  console.error('❌  Unexpected build script error:', err.message);
  // Even on unexpected errors — write fallback so site doesn't break
  try { writeFallback(err.message); } catch { /* ignore */ }
  process.exit(0);
});
