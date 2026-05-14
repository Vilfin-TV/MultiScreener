/**
 * rss-proxy-worker.js
 * ════════════════════════════════════════════════════════════════════════
 * Cloudflare Worker — RSS Feed Proxy  (screener-proxy.vilfintv.workers.dev)
 *
 * Strategy: Primary (live RSS) → GitHub Raw XML fallback → JSON 500 error
 *
 * DEPLOY STEPS:
 *  1. Workers & Pages → Create → Worker → paste this file → Save & Deploy
 *  2. No secrets needed — all config is in the CONSTANTS block below.
 *  3. Plug in your PRIMARY_FEED_URL and GITHUB_FALLBACK_URL then deploy.
 *
 * RESPONSE HEADERS on every reply:
 *   Access-Control-Allow-Origin: *
 *   X-Data-Source: live-feed | github-fallback | error
 * ════════════════════════════════════════════════════════════════════════
 */

'use strict';

// ─── ✏️  CONFIGURE THESE TWO URLS BEFORE DEPLOYING ────────────────────────────

/** The live RSS / XML feed you want to proxy. */
const PRIMARY_FEED_URL = 'https://your-rss-feed-source.com/feed.xml';

/**
 * Static GitHub Raw fallback — commit a copy of your feed here.
 * Format: https://raw.githubusercontent.com/USERNAME/REPO/BRANCH/path/feed.xml
 */
const GITHUB_FALLBACK_URL =
  'https://raw.githubusercontent.com/Vilfin-TV/MultiScreener/main/rss_fallback.xml';

// ─── Fetch settings ────────────────────────────────────────────────────────────

/** Milliseconds before the primary fetch is considered timed out. */
const PRIMARY_TIMEOUT_MS = 6000;

/** Browser User-Agent to spoof on primary fetch (bypasses some origin blocks). */
const SPOOF_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
  'AppleWebKit/537.36 (KHTML, like Gecko) ' +
  'Chrome/124.0.0.0 Safari/537.36';

// ─── CORS headers attached to EVERY response ───────────────────────────────────
const CORS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// ══════════════════════════════════════════════════════════════════════════════
// Worker entry-point
// ══════════════════════════════════════════════════════════════════════════════
export default {
  async fetch(request) {
    // ── OPTIONS preflight ─────────────────────────────────────────────────────
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    // ── Only allow GET ────────────────────────────────────────────────────────
    if (request.method !== 'GET') {
      return jsonError(405, 'Method not allowed');
    }

    // ── 1. Try the live primary feed ──────────────────────────────────────────
    try {
      const primaryRes = await fetchWithTimeout(PRIMARY_FEED_URL, {
        headers: {
          'User-Agent': SPOOF_UA,
          'Accept':     'application/rss+xml, application/xml, text/xml, */*',
        },
      }, PRIMARY_TIMEOUT_MS);

      if (primaryRes.ok) {
        const body        = await primaryRes.text();
        const contentType = primaryRes.headers.get('Content-Type') ||
                            'application/xml; charset=utf-8';
        return new Response(body, {
          status: 200,
          headers: {
            ...CORS,
            'Content-Type':  contentType,
            'X-Data-Source': 'live-feed',
            'Cache-Control': 'public, max-age=60',
          },
        });
      }

      // Non-2xx from origin — log and fall through to GitHub
      console.warn(
        `[rss-proxy] Primary returned ${primaryRes.status} — trying GitHub fallback`
      );
    } catch (primaryErr) {
      console.warn(`[rss-proxy] Primary fetch failed: ${primaryErr.message} — trying GitHub fallback`);
    }

    // ── 2. GitHub Raw XML fallback ────────────────────────────────────────────
    try {
      const ghRes = await fetch(GITHUB_FALLBACK_URL, {
        headers: { 'User-Agent': SPOOF_UA },
      });

      if (ghRes.ok) {
        const body = await ghRes.text();
        return new Response(body, {
          status: 200,
          headers: {
            ...CORS,
            'Content-Type':  'application/xml; charset=utf-8',
            'X-Data-Source': 'github-fallback',
            'Cache-Control': 'public, max-age=300',
          },
        });
      }

      throw new Error(`GitHub fallback returned HTTP ${ghRes.status}`);
    } catch (ghErr) {
      console.error(`[rss-proxy] GitHub fallback also failed: ${ghErr.message}`);

      // ── 3. Both failed — return structured JSON error (never a 503) ────────
      return jsonError(500, 'Both primary feed and GitHub fallback failed', {
        primary:  PRIMARY_FEED_URL,
        fallback: GITHUB_FALLBACK_URL,
        detail:   ghErr.message,
      });
    }
  },
};

// ══════════════════════════════════════════════════════════════════════════════
// Helpers
// ══════════════════════════════════════════════════════════════════════════════

/**
 * fetch() with an AbortController timeout.
 * Throws if the request exceeds timeoutMs.
 */
function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer      = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(timer));
}

/**
 * Returns a JSON error response that always includes CORS headers.
 * Never throws — prevents the Worker from returning a 503.
 */
function jsonError(status, message, extra = {}) {
  return new Response(
    JSON.stringify({ ok: false, status, message, ...extra }, null, 2),
    {
      status,
      headers: {
        ...CORS,
        'Content-Type':  'application/json; charset=utf-8',
        'X-Data-Source': 'error',
      },
    }
  );
}
