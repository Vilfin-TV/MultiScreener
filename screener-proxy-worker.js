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

    const { pathname, searchParams } = new URL(request.url);

    // ── /feedback  POST — Bug reports, feature requests, user feedback ────────
    // Destination email is stored securely in FEEDBACK_EMAIL env var (never in frontend).
    // Email is sent via Resend API (RESEND_API_KEY env var).
    // Required env vars in Cloudflare Workers dashboard:
    //   FEEDBACK_EMAIL  = vilfintv123@gmail.com
    //   RESEND_API_KEY  = re_xxxxxxxxxxxx  (from resend.com — free tier)
    if (pathname === '/feedback') {
      if (request.method !== 'POST') {
        return jsonError(405, 'Method not allowed. Use POST for /feedback.');
      }

      // Validate env vars are configured
      if (!env || !env.FEEDBACK_EMAIL || !env.RESEND_API_KEY) {
        return jsonError(503, 'Feedback service not configured. Please set FEEDBACK_EMAIL and RESEND_API_KEY in Worker environment variables.');
      }

      let payload;
      try {
        payload = await request.json();
      } catch (_) {
        return jsonError(400, 'Invalid JSON body.');
      }

      const { type, subject, body } = payload || {};
      if (!type || !subject || !body) {
        return jsonError(400, 'Missing required fields: type, subject, body.');
      }

      // Build rich HTML email from the AI-query formatted markdown body
      const htmlBody = buildFeedbackEmailHtml(type, subject, body);

      // Send via Resend API  (https://resend.com — free: 100 emails/day)
      try {
        const emailRes = await fetch('https://api.resend.com/emails', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${env.RESEND_API_KEY}`,
            'Content-Type':  'application/json',
          },
          body: JSON.stringify({
            from:    'VilfinTV Feedback <feedback@vilfintv.com>',
            to:      [env.FEEDBACK_EMAIL],
            subject: subject,
            html:    htmlBody,
            text:    body,   // plain-text fallback
          }),
        });

        if (emailRes.ok) {
          return new Response(
            JSON.stringify({ ok: true, message: 'Feedback received. Thank you!' }),
            { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } }
          );
        }

        // Resend returned an error — log it, return generic failure
        const errText = await emailRes.text().catch(() => '');
        console.error(`[feedback] Resend error ${emailRes.status}: ${errText}`);
        return jsonError(502, 'Failed to send feedback email. Please try again later.');

      } catch (emailErr) {
        console.error(`[feedback] Email send exception: ${emailErr.message}`);
        return jsonError(500, 'Unexpected error sending feedback.');
      }
    }

    // ── Only allow GET for all other routes ──────────────────────────────────
    if (request.method !== 'GET') {
      return jsonError(405, 'Method not allowed. Use GET.');
    }

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

/**
 * Builds a styled HTML email body from the AI-query markdown string.
 * The output is readable in any email client and copy-pasteable into
 * Claude / GitHub Copilot / VS Code as a ready-made fix/implement query.
 */
function buildFeedbackEmailHtml(type, subject, markdownBody) {
  const typeConfig = {
    bug:      { label: 'Bug Report',       colour: '#7c4dff', emoji: '🐞' },
    feature:  { label: 'Feature Request',  colour: '#f59e0b', emoji: '💡' },
    feedback: { label: 'User Feedback',    colour: '#10b981', emoji: '💬' },
  };
  const cfg   = typeConfig[type] || typeConfig.bug;
  const ts    = new Date().toUTCString();

  // Convert very basic markdown → HTML (tables, headings, code blocks, bold)
  const htmlContent = markdownBody
    // fenced code blocks
    .replace(/```[\s\S]*?```/g, m => {
      const inner = m.replace(/^```[^\n]*\n?/, '').replace(/\n?```$/, '');
      return `<pre style="background:#1e1e1e;color:#d4d4d4;padding:16px 20px;border-radius:8px;font-family:'Courier New',monospace;font-size:12.5px;line-height:1.7;overflow-x:auto;border-left:3px solid ${cfg.colour};margin:12px 0">${escHtml(inner)}</pre>`;
    })
    // h2
    .replace(/^## (.+)$/gm, `<h2 style="color:${cfg.colour};font-size:14px;font-weight:700;margin:20px 0 6px;letter-spacing:.4px;text-transform:uppercase">$1</h2>`)
    // h1
    .replace(/^# (.+)$/gm, `<h1 style="color:#ffffff;font-size:20px;font-weight:700;margin:0 0 4px">$1</h1>`)
    // markdown table (simple 2-col | Key | Value |)
    .replace(/^\|(.+)\|\s*\n\|[-| ]+\|\s*\n((?:\|.+\|\s*\n?)*)/gm, (_, hdr, rows) => {
      const ths = hdr.split('|').filter(Boolean).map(c => `<th style="padding:8px 14px;background:#2d2d3a;color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:.5px;text-align:left">${c.trim()}</th>`).join('');
      const trs = rows.trim().split('\n').map(row => {
        const tds = row.split('|').filter(Boolean).map(c => `<td style="padding:8px 14px;border-bottom:1px solid #2d2d3a;color:#e2e8f0;font-size:13px">${c.trim()}</td>`).join('');
        return `<tr>${tds}</tr>`;
      }).join('');
      return `<table style="width:100%;border-collapse:collapse;background:#1a1a2e;border-radius:8px;overflow:hidden;margin:8px 0"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
    })
    // horizontal rule
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #2d2d3a;margin:20px 0"/>')
    // bold
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#e2e8f0">$1</strong>')
    // inline code
    .replace(/`([^`]+)`/g, '<code style="background:#2d2d3a;color:#80deea;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:12px">$1</code>')
    // newlines → <br> (outside block elements)
    .replace(/\n/g, '<br>');

  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0d0d1a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d0d1a;padding:32px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#13131f;border-radius:14px;overflow:hidden;border:1px solid #2d2d3a">

        <!-- Header bar -->
        <tr>
          <td style="background:linear-gradient(135deg,${cfg.colour},#00bcd4);padding:24px 28px">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <div style="font-size:28px;margin-bottom:6px">${cfg.emoji}</div>
                  <div style="color:#fff;font-size:22px;font-weight:700;letter-spacing:.5px">${cfg.label}</div>
                  <div style="color:rgba(255,255,255,.75);font-size:12px;margin-top:4px">vilfintv.com &nbsp;·&nbsp; ${ts}</div>
                </td>
                <td align="right" style="vertical-align:top">
                  <div style="background:rgba(255,255,255,.15);border-radius:8px;padding:8px 14px;color:#fff;font-size:11px;font-weight:700;letter-spacing:.6px;text-transform:uppercase">VilfinTV</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Subject -->
        <tr>
          <td style="padding:18px 28px 0">
            <div style="background:#1e1e2e;border-left:3px solid ${cfg.colour};border-radius:0 6px 6px 0;padding:10px 16px">
              <div style="color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.6px;margin-bottom:3px">Subject</div>
              <div style="color:#e2e8f0;font-size:14px;font-weight:600">${escHtml(subject)}</div>
            </div>
          </td>
        </tr>

        <!-- Body content -->
        <tr>
          <td style="padding:22px 28px;color:#c9d1d9;font-size:13.5px;line-height:1.7">
            ${htmlContent}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 28px 24px;border-top:1px solid #2d2d3a">
            <div style="color:#4b5563;font-size:11px;line-height:1.6">
              This report was submitted via the feedback form on <strong style="color:#6b7280">vilfintv.com</strong>.<br>
              The sender's email address is not collected. Reply is not possible from this message.<br>
              To action this report, copy the <strong style="color:${cfg.colour}>AI Fix Query</strong> block above directly into Claude Code, GitHub Copilot, or VS Code Copilot Chat.
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>`;
}

/** Escape HTML special characters for safe inline use. */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
