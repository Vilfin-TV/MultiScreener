/**
 * screener-proxy.vilfintv.workers.dev
 * ════════════════════════════════════════════════════════════════════════
 * General-purpose CORS proxy with Primary + GitHub Fallback strategy.
 *
 * Query parameters:
 *   ?url=<encoded-primary-url>          — required, the live feed to fetch
 *   ?fallback=<encoded-github-raw-url>  — optional, used if primary fails
 *
 * Example call from your frontend:
 *   https://screener-proxy.vilfintv.workers.dev
 *     ?url=https://feeds.example.com/rss.xml
 *     &fallback=https://raw.githubusercontent.com/Vilfin-TV/MultiScreener/main/rss_fallback.xml
 *
 * Response headers on every reply:
 *   Access-Control-Allow-Origin: *
 *   X-Data-Source: live-feed | github-fallback | error
 * ════════════════════════════════════════════════════════════════════════
 */

'use strict';

/** Milliseconds before the primary fetch is aborted. */
const PRIMARY_TIMEOUT_MS = 6000;

/** YouTube Data API v3 base. Requires YOUTUBE_API_KEY env var. */
const YT_API = 'https://www.googleapis.com/youtube/v3';

/** Browser User-Agent to bypass origin blocks. */
const SPOOF_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
  'AppleWebKit/537.36 (KHTML, like Gecko) ' +
  'Chrome/124.0.0.0 Safari/537.36';

/** CORS headers attached to every single response. */
const CORS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// ══════════════════════════════════════════════════════════════════════════════
export default {
  async fetch(request, env) {

    // ── OPTIONS preflight ─────────────────────────────────────────────────────
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    // ── Only allow GET ────────────────────────────────────────────────────────
    if (request.method !== 'GET') {
      return jsonError(405, 'Method not allowed. Use GET.');
    }

    const { pathname, searchParams } = new URL(request.url);

    // ── /youtube-live?cid=CHANNEL_ID ─────────────────────────────────────────
    // Resolves the current active live broadcast for a YouTube channel.
    // Requires YOUTUBE_API_KEY env var; returns {live, videoId, title} or {live:false}.
    if (pathname === '/youtube-live') {
      const cid = (searchParams.get('cid') || '').trim();
      if (!cid || !cid.startsWith('UC')) {
        return jsonError(400, 'Invalid or missing cid parameter (must start with UC)');
      }
      if (!env || !env.YOUTUBE_API_KEY) {
        return new Response(JSON.stringify({ live: false, reason: 'API key not configured' }), {
          status: 200,
          headers: { ...CORS, 'Content-Type': 'application/json' },
        });
      }
      try {
        const apiUrl = `${YT_API}/search?part=id,snippet&channelId=${encodeURIComponent(cid)}&eventType=live&type=video&maxResults=1&key=${env.YOUTUBE_API_KEY}`;
        const res = await fetch(apiUrl, { signal: AbortSignal.timeout(7000) });
        if (!res.ok) {
          return new Response(JSON.stringify({ live: false, reason: `API returned ${res.status}` }), {
            status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
          });
        }
        const data = await res.json();
        const item = data.items && data.items[0];
        if (!item) {
          return new Response(JSON.stringify({ live: false }), {
            status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
          });
        }
        return new Response(JSON.stringify({
          live:    true,
          videoId: item.id.videoId,
          title:   item.snippet && item.snippet.title || '',
          thumb:   item.snippet && item.snippet.thumbnails && item.snippet.thumbnails.medium && item.snippet.thumbnails.medium.url || '',
        }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
      } catch (err) {
        return new Response(JSON.stringify({ live: false, reason: err.message }), {
          status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
        });
      }
    }

    // ── /youtube-search?q=QUERY ───────────────────────────────────────────────
    // Returns structured search results (video+playlist) from YouTube Data API.
    // Falls back to empty results if API key not configured.
    if (pathname === '/youtube-search') {
      const q = (searchParams.get('q') || '').trim();
      if (!q) return jsonError(400, 'Missing q parameter');
      if (!env || !env.YOUTUBE_API_KEY) {
        return new Response(JSON.stringify({ items: [], reason: 'API key not configured' }), {
          status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
        });
      }
      try {
        const apiUrl = `${YT_API}/search?part=snippet&q=${encodeURIComponent(q)}&maxResults=15&type=video,playlist&key=${env.YOUTUBE_API_KEY}`;
        const res = await fetch(apiUrl, { signal: AbortSignal.timeout(8000) });
        if (!res.ok) {
          return new Response(JSON.stringify({ items: [] }), {
            status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
          });
        }
        const data = await res.json();
        const items = (data.items || []).map(item => ({
          id:      item.id.videoId || item.id.playlistId,
          type:    item.id.kind === 'youtube#playlist' ? 'playlist' : 'video',
          title:   item.snippet && item.snippet.title || '',
          channel: item.snippet && item.snippet.channelTitle || '',
          thumb:   item.snippet && item.snippet.thumbnails && item.snippet.thumbnails.medium && item.snippet.thumbnails.medium.url || '',
        })).filter(i => i.id);
        return new Response(JSON.stringify({ items }), {
          status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
        });
      } catch (err) {
        return new Response(JSON.stringify({ items: [], reason: err.message }), {
          status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
        });
      }
    }

    // ── Parse query params for generic proxy ──────────────────────────────────
    const targetUrl   = searchParams.get('url');
    const fallbackUrl = searchParams.get('fallback'); // optional

    if (!targetUrl) {
      return jsonError(400, "Missing required query parameter: 'url'");
    }

    // ── 1. Try the primary URL ─────────────────────────────────────────────────
    try {
      const primaryRes = await fetchWithTimeout(targetUrl, {
        headers: {
          'User-Agent': SPOOF_UA,
          'Accept':     'application/rss+xml, application/xml, text/xml, */*',
        },
      }, PRIMARY_TIMEOUT_MS);

      if (primaryRes.ok) {
        // Mirror the original response body + headers, then enforce CORS
        const body       = await primaryRes.arrayBuffer();
        const outHeaders = new Headers(primaryRes.headers);
        applyHeaders(outHeaders, {
          ...CORS,
          'X-Data-Source': 'live-feed',
        });
        return new Response(body, {
          status:  primaryRes.status,
          headers: outHeaders,
        });
      }

      // Non-2xx — log and fall through
      console.warn(
        `[proxy] Primary returned ${primaryRes.status} for ${targetUrl}` +
        (fallbackUrl ? ' — trying fallback' : ' — no fallback provided')
      );
    } catch (primaryErr) {
      console.warn(
        `[proxy] Primary fetch failed (${primaryErr.message}) for ${targetUrl}` +
        (fallbackUrl ? ' — trying fallback' : ' — no fallback provided')
      );
    }

    // ── 2. GitHub Raw XML fallback (only if ?fallback= was provided) ──────────
    if (fallbackUrl) {
      try {
        const ghRes = await fetch(fallbackUrl, {
          headers: { 'User-Agent': SPOOF_UA },
        });

        if (ghRes.ok) {
          const body       = await ghRes.arrayBuffer();
          const outHeaders = new Headers(ghRes.headers);
          applyHeaders(outHeaders, {
            ...CORS,
            'Content-Type':  'application/xml; charset=utf-8',
            'X-Data-Source': 'github-fallback',
            'Cache-Control': 'public, max-age=300',
          });
          return new Response(body, { status: 200, headers: outHeaders });
        }

        throw new Error(`GitHub fallback returned HTTP ${ghRes.status}`);
      } catch (ghErr) {
        console.error(`[proxy] GitHub fallback also failed: ${ghErr.message}`);
        return jsonError(500, 'Both primary and GitHub fallback failed', {
          primary:  targetUrl,
          fallback: fallbackUrl,
          detail:   ghErr.message,
        });
      }
    }

    // ── 3. No fallback provided — return clean JSON error ─────────────────────
    return jsonError(502, 'Primary feed failed and no fallback URL was provided', {
      primary: targetUrl,
    });
  },
};

// ══════════════════════════════════════════════════════════════════════════════
// Helpers
// ══════════════════════════════════════════════════════════════════════════════

/** fetch() with an AbortController timeout. Throws on timeout. */
function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer      = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(timer));
}

/** Set multiple headers on an existing Headers object. */
function applyHeaders(headers, map) {
  for (const [k, v] of Object.entries(map)) headers.set(k, v);
}

/**
 * Returns a JSON error response that always includes CORS headers.
 * Never throws — prevents the Worker from crashing into a 503.
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
