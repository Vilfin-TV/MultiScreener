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
    req.setTimeout(60_000, () => req.destroy(new Error('Request timeout (60s)')));
    req.write(payload);
    req.end();
  });
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
  console.log('');
  console.log('⏳  Requesting market snapshot from Worker…');

  let response;
  try {
    response = await postJson(ENDPOINT, {});
  } catch (err) {
    console.error('❌  Network error:', err.message);
    process.exit(1);
  }

  if (response.status !== 200) {
    console.error(`❌  Worker returned HTTP ${response.status}:`);
    console.error('   ', JSON.stringify(response.body));
    process.exit(1);
  }

  const snap = response.body;

  if (!snap.briefing || snap.briefing.length < 30) {
    console.error('❌  Worker returned an empty or invalid briefing.');
    console.error('   ', JSON.stringify(snap).slice(0, 300));
    process.exit(1);
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
  const preview  = output.briefing.replace(/\n/g, ' ').slice(0, 120);
  const wordCount = output.briefing.split(/\s+/).length;
  console.log('✅  data.json written successfully.');
  console.log(`    Generated : ${output.generated}`);
  console.log(`    Model     : ${output.model}`);
  console.log(`    Words     : ${wordCount}`);
  console.log(`    Preview   : ${preview}${wordCount > 20 ? '…' : ''}`);
  console.log('');
}

main().catch(err => {
  console.error('❌  Build script failed:', err.message);
  process.exit(1);
});
