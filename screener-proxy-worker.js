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
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

// ══════════════════════════════════════════════════════════════════════════════
export default {
  async fetch(request, env) {

    // ── OPTIONS preflight ─────────────────────────────────────────────────────
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    const { pathname, searchParams } = new URL(request.url);

    // ── /api/reactions  GET/POST — permanent, anonymous like/dislike counters ──
    // Storage is a single {likes,dislikes} JSON blob per story id, keyed
    // "reactions:<id>" in the existing IPTV_KV store. Deliberately NOT
    // storing anything about WHO reacted (no IP, cookie, device id) per an
    // explicit no-client-data requirement — so there is no server-side way
    // to stop the same visitor voting twice; the page's own localStorage
    // flag is the only (client-side, non-transmitted) guard against that.
    if (pathname === '/api/reactions') {
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      const id = (searchParams.get('id') || '').trim().slice(0, 100);
      const idsParam = (searchParams.get('ids') || '').trim();

      // Batch mode — GET ?ids=a,b,c returns every story's counts in one round
      // trip (used by the console's engagement report so it doesn't fire one
      // request per post). Single-id mode below is unchanged for news.html.
      if (request.method === 'GET' && idsParam) {
        const ids = idsParam.split(',').map(s => s.trim().slice(0, 100)).filter(Boolean).slice(0, 500);
        const counts = {};
        await Promise.all(ids.map(async (storyId) => {
          let c = { likes: 0, dislikes: 0 };
          try {
            const raw = await env.IPTV_KV.get('reactions:' + storyId);
            if (raw) c = { ...c, ...JSON.parse(raw) };
          } catch (e) { /* corrupt/missing entry -> zeros */ }
          counts[storyId] = { likes: c.likes | 0, dislikes: c.dislikes | 0 };
        }));
        return new Response(JSON.stringify({ ok: true, counts }),
          { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
      }

      if (request.method === 'GET') {
        if (!id) return jsonError(400, 'Missing id.');
        let counts = { likes: 0, dislikes: 0 };
        try {
          const raw = await env.IPTV_KV.get('reactions:' + id);
          if (raw) counts = { ...counts, ...JSON.parse(raw) };
        } catch (e) { /* corrupt/missing entry -> serve zeros */ }
        return new Response(JSON.stringify({ ok: true, id, likes: counts.likes|0, dislikes: counts.dislikes|0 }),
          { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
      }

      if (request.method === 'POST') {
        let body; try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
        const bodyId = (body.id || id || '').toString().trim().slice(0, 100);
        // "from"/"to" each describe the visitor's reaction state ('', 'like',
        // or 'dislike') before/after this click, as tracked by THEIR OWN
        // browser (localStorage) - never anything the server itself recorded.
        // This lets one request express every transition: casting a fresh
        // vote ('' -> 'like'), un-voting (toggling the same button off,
        // 'like' -> ''), or switching sides ('like' -> 'dislike') - by just
        // decrementing whichever bucket "from" names and incrementing
        // whichever bucket "to" names.
        const VALID = ['', 'like', 'dislike'];
        const from = (body.from || '').toString().trim();
        const to = (body.to || '').toString().trim();
        if (!bodyId) return jsonError(400, 'Missing id.');
        if (!VALID.includes(from) || !VALID.includes(to)) return jsonError(400, 'from/to must each be "", "like", or "dislike".');
        if (from === to) return jsonError(400, 'from and to must differ.');

        let counts = { likes: 0, dislikes: 0 };
        try {
          const raw = await env.IPTV_KV.get('reactions:' + bodyId);
          if (raw) counts = { ...counts, ...JSON.parse(raw) };
        } catch (e) { /* corrupt entry -> reset to zeros rather than fail the vote */ }
        if (from === 'like') counts.likes = Math.max(0, counts.likes - 1);
        if (from === 'dislike') counts.dislikes = Math.max(0, counts.dislikes - 1);
        if (to === 'like') counts.likes += 1;
        if (to === 'dislike') counts.dislikes += 1;
        await env.IPTV_KV.put('reactions:' + bodyId, JSON.stringify(counts));
        return new Response(JSON.stringify({ ok: true, id: bodyId, likes: counts.likes, dislikes: counts.dislikes }),
          { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
      }

      return jsonError(405, 'Use GET to read or POST to react.');
    }

    // ── /s (alias /share)  GET — story share page with per-story Open Graph ───
    // WhatsApp / Facebook / X scrape this URL (they don't run JS) for the hero
    // photo + heading; human clicks are redirected to the live story.
    if (pathname === '/s' || pathname === '/share') {
      const slug = (searchParams.get('story') || '').trim();
      const target = 'https://vilfintv.com/news.html' + (slug ? ('?story=' + encodeURIComponent(slug)) : '');
      const _ogSlug = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      const _ogEsc  = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      const _SECT_LABELS = {
        trending:'Trending', global:'Global News', india:'India News',
        stock:'Stock News', malayalam:'Malayalam News', ml_trending:'Malayalam Trending',
        ml_movies:'Malayalam Movies', movies:'Movie News', sports:'Sports',
        tech:'Tech News', space:'Space & Science', science:'Science News',
        entertainment:'Entertainment', business:'Business News',
      };
      let title    = 'VilfinTV News';
      let desc     = 'Live news, markets, sports, tech and stories on VilfinTV.';
      let image    = 'https://vilfintv.com/images/vilfintv-logo.jpg';
      let siteName = 'VilfinTV News';
      let found = false;

      if (slug) {
        try {
          // 1) Featured posts (content.json)
          const cRes = await fetch('https://vilfintv.com/content.json', { cf: { cacheTtl: 300 } });
          if (cRes.ok) {
            const arr = await cRes.json();
            const post = (Array.isArray(arr) ? arr : []).find(p => String(p.id) === slug || _ogSlug(p.heading) === slug);
            if (post) {
              found = true;
              title = post.heading || title;
              const _sl = _SECT_LABELS[post.section] || '';
              if (_sl) siteName = 'VilfinTV · ' + _sl;
              const _rawDesc = (post.story || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 180);
              desc = (_sl ? _sl + ' | ' : '') + (_rawDesc || desc);
              if (post.photo) image = post.photo;
            }
          }
          // 2) RSS / generated stories (data/news.json)
          if (!found) {
            const nRes = await fetch('https://vilfintv.com/data/news.json', { cf: { cacheTtl: 300 } });
            if (nRes.ok) {
              const data = await nRes.json();
              const secs = (data && data.sections) ? Object.keys(data.sections) : [];
              for (const k of secs) {
                const items = (data.sections[k] && data.sections[k].items) || [];
                const it = items.find(i => _ogSlug(i.headline) === slug);
                if (it) {
                  found = true;
                  title = it.headline || title;
                  desc  = (it.teaser || '').replace(/\s+/g, ' ').trim().slice(0, 200) || desc;
                  if (it.image) image = it.image;
                  break;
                }
              }
            }
          }
        } catch (_) { /* fall back to brand defaults */ }
      }

      const html = '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        + '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + '<title>' + _ogEsc(title) + '</title>'
        + '<meta property="og:type" content="article">'
        + '<meta property="og:site_name" content="' + _ogEsc(siteName) + '">'
        + '<meta property="og:title" content="' + _ogEsc(title) + '">'
        + '<meta property="og:description" content="' + _ogEsc(desc) + '">'
        + '<meta property="og:image" content="' + _ogEsc(image) + '">'
        + '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
        + '<meta property="og:url" content="' + _ogEsc(target) + '">'
        + '<meta name="twitter:card" content="summary_large_image">'
        + '<meta name="twitter:title" content="' + _ogEsc(title) + '">'
        + '<meta name="twitter:description" content="' + _ogEsc(desc) + '">'
        + '<meta name="twitter:image" content="' + _ogEsc(image) + '">'
        + '<meta http-equiv="refresh" content="0; url=' + _ogEsc(target) + '">'
        + '<link rel="canonical" href="' + _ogEsc(target) + '">'
        + '</head><body style="font-family:system-ui,sans-serif;background:#0a192f;color:#e2eeff;text-align:center;padding:40px">'
        + '<p>Opening <a style="color:#7db1ff" href="' + _ogEsc(target) + '">' + _ogEsc(title) + '</a>…</p>'
        + '<script>location.replace(' + JSON.stringify(target) + ');</script>'
        + '</body></html>';
      return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=300', 'Access-Control-Allow-Origin': '*' } });
    }

    // ── /feedback  POST — Bug reports, feature requests, user feedback ────────
    // Email is sent via Web3Forms (web3forms.com — free, no domain verification needed).
    // Required env var in Cloudflare Workers dashboard:
    //   WEB3FORMS_KEY  = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    //   (get your free key at https://web3forms.com — enter vilfintv123@gmail.com as destination)
    if (pathname === '/feedback') {
      if (request.method !== 'POST') {
        return jsonError(405, 'Method not allowed. Use POST for /feedback.');
      }

      if (!env || !env.FORMSPREE_FORM_ID) {
        return jsonError(503, 'Feedback service not configured. Add FORMSPREE_FORM_ID to Worker environment variables.');
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

      // Send via Formspree (free, no domain verification required)
      try {
        const formRes = await fetch(`https://formspree.io/f/${env.FORMSPREE_FORM_ID.trim()}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept':        'application/json',
          },
          body: JSON.stringify({
            subject:       subject,
            message:       body,
            _subject:      subject,
            _replyto:      'no-reply@formspree.io',
            'Report Type': type,
            'Platform':    'vilfintv.com',
            'Timestamp':   new Date().toUTCString(),
          }),
        });

        const result = await formRes.json().catch(() => ({}));

        if (formRes.ok) {
          return new Response(
            JSON.stringify({ ok: true, message: 'Feedback received. Thank you!' }),
            { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } }
          );
        }

        const reason = (result.errors && result.errors.map(e => e.message).join(', ')) || `HTTP ${formRes.status}`;
        console.error(`[feedback] Formspree error: ${reason}`);
        return jsonError(502, `Failed to send feedback: ${reason}`);

      } catch (err) {
        console.error(`[feedback] Exception: ${err.message}`);
        return jsonError(500, 'Unexpected error sending feedback.');
      }
    }

    // ── /api/login  POST — issue a JWT session token ──────────────────────────
    if (pathname === '/api/login') {
      if (request.method !== 'POST') {
        return jsonError(405, 'Method not allowed. Use POST for /api/login.');
      }
      let body;
      try { body = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const { username, password } = body || {};
      if (!env.ADMIN_USERNAME || !env.LINK_CONSOLE_PASSWORD || !env.JWT_SECRET) {
        return jsonError(503, 'Auth not configured. Set ADMIN_USERNAME, LINK_CONSOLE_PASSWORD and JWT_SECRET in Worker environment.');
      }
      const now = Math.floor(Date.now() / 1000);
      const exp = now + 86400;
      const device = (body.device || '').toString();
      // 1) Admin via environment credentials → full access (with optional 2FA).
      if (username && password && username === env.ADMIN_USERNAME && password === env.LINK_CONSOLE_PASSWORD) {
        const tfa = await _2faGet(env);
        if (tfa.enabled) {
          const code = (body.code || '').toString().trim();
          if (!code)                                  return _rbacJson({ ok:false, need2fa:true, message:'Enter the 6-digit code from your authenticator app.' });
          if (!(await _totpVerify(tfa.secret, code))) return _rbacJson({ ok:false, need2fa:true, message:'Invalid 2FA code — try the current code.' });
        }
        const jti = _iptvHexFromBytes(crypto.getRandomValues(new Uint8Array(12)));
        await _sessRecord(env, request, jti, username, 'admin', exp, device);
        const token = await signJWT({ sub: username, role: 'admin', perms: null, jti, iat: now, exp }, env.JWT_SECRET);
        return _rbacJson({ ok: true, token, role: 'admin', username: username });
      }
      // 2) Operator/Auditor via KV accounts.
      if (username && password && env.IPTV_KV) {
        let authObj = null;
        try { const r = await env.IPTV_KV.get('iptv_auth'); authObj = r ? JSON.parse(r) : {}; } catch(e){ authObj = {}; }
        if (!authObj) authObj = {};
        if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
        const op = authObj[username];
        if (op && op.hash) {
          if (op.disabled) return jsonError(403, 'This account is disabled. Contact the administrator.');
          if (op.expireDate && Date.now() > new Date(op.expireDate).getTime()) return jsonError(403, 'Account has expired.');
          
          const h = await _iptvHashPassword(password, op.salt, op.iterations);
          if (h.hash === op.hash) {
            if (device && op.maxBoundDevices) {
              op.devices = op.devices || {};
              if (!op.devices[device] && Object.keys(op.devices).length >= op.maxBoundDevices) {
                return jsonError(403, 'Maximum bound devices limit reached.');
              }
            }
            if (op.maxActiveSessions) {
              const allSess = await _sessAll(env);
              let activeCount = 0;
              const nowMs = Date.now();
              for (const k of Object.keys(allSess)) {
                if (allSess[k] && allSess[k].username === username && allSess[k].exp * 1000 > nowMs) activeCount++;
              }
              if (activeCount >= op.maxActiveSessions) return jsonError(403, 'Maximum concurrent active sessions reached.');
            }
            
            op.loginCount = (op.loginCount || 0) + 1;
            if (device) {
              op.devices = op.devices || {};
              op.devices[device] = {
                ip: request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For') || '',
                ua: (request.headers.get('User-Agent') || '').slice(0,300),
                lastSeen: new Date().toISOString()
              };
            }
            await env.IPTV_KV.put('iptv_auth', JSON.stringify(authObj));
            
            const jti = _iptvHexFromBytes(crypto.getRandomValues(new Uint8Array(12)));
            await _sessRecord(env, request, jti, username, op.role || 'operator', exp, device);
            const token = await signJWT({ sub: username, role: op.role || 'operator', perms: op.perms || {}, jti, iat: now, exp }, env.JWT_SECRET);
            return _rbacJson({ ok: true, token, role: op.role || 'operator', username: username, perms: op.perms || {} });
          }
        }
      }
      return jsonError(401, 'Invalid credentials.');
    }

    // ══ Admin 2FA (TOTP) management (admin only) ═══════════════════════════════
    // ── /api/2fa/status  GET — is 2FA enabled? ─────────────────────────────────
    if (pathname === '/api/2fa/status' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      const tfa = await _2faGet(env);
      return _rbacJson({ ok:true, enabled: tfa.enabled });
    }
    // ── /api/2fa/setup  POST — start enrolment: mint a secret + otpauth URI ─────
    if (pathname === '/api/2fa/setup' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      const tfa = await _2faGet(env);
      if (tfa.enabled) return jsonError(400, '2FA is already enabled. Disable it first to re-enrol.');
      const secret = _b32encode(crypto.getRandomValues(new Uint8Array(20)));
      await _2faPut(env, { enabled:false, secret:'', pending:secret });
      const label = encodeURIComponent('VilfinTV Console:' + (env.ADMIN_USERNAME || 'admin'));
      const otpauth = `otpauth://totp/${label}?secret=${secret}&issuer=VilfinTV&algorithm=SHA1&digits=6&period=30`;
      return _rbacJson({ ok:true, secret, otpauth });
    }
    // ── /api/2fa/enable  POST — confirm a code → turn 2FA on ────────────────────
    if (pathname === '/api/2fa/enable' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const tfa = await _2faGet(env);
      if (!tfa.pending) return jsonError(400, 'Run setup first.');
      if (!(await _totpVerify(tfa.pending, b.code))) return jsonError(400, 'That code did not match. Make sure your device clock is correct and try the current code.');
      await _2faPut(env, { enabled:true, secret:tfa.pending, pending:'' });
      return _rbacJson({ ok:true, enabled:true });
    }
    // ── /api/2fa/disable  POST — verify a code → turn 2FA off ───────────────────
    if (pathname === '/api/2fa/disable' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const tfa = await _2faGet(env);
      if (!tfa.enabled) return _rbacJson({ ok:true, enabled:false });
      if (!(await _totpVerify(tfa.secret, b.code))) return jsonError(400, 'Invalid code — 2FA not disabled.');
      await _2faPut(env, { enabled:false, secret:'', pending:'' });
      return _rbacJson({ ok:true, enabled:false });
    }

    // ══ Login sessions / device activity (admin only) ═════════════════════════
    // ── /api/sessions  GET — list active sign-in sessions ──────────────────────
    if (pathname === '/api/sessions' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      const all = await _sessAll(env);
      const nowMs = Date.now(); const mine = (auth.payload||{}).jti || '';
      const sessions = Object.values(all)
        .filter(s => !s.exp || s.exp*1000 > nowMs)
        .sort((a,b) => (b.lastSeen||0) - (a.lastSeen||0))
        .map(s => ({ jti:s.jti, username:s.username, role:s.role, ip:s.ip, ua:s.ua, device:s.device,
          loc:s.loc, org:s.org, createdAt:s.createdAt, lastSeen:s.lastSeen, current: s.jti === mine }));
      return _rbacJson({ ok:true, sessions });
    }
    // ── /api/sessions/revoke  POST — sign out a device by jti (admin only) ─────
    if (pathname === '/api/sessions/revoke' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const all = await _sessAll(env);
      if (b.others) { const keep = (auth.payload||{}).jti; Object.keys(all).forEach(k => { if (k !== keep) delete all[k]; }); }
      else { const jti = (b.jti||'').toString(); if (all[jti]) delete all[jti]; }
      await _sessPut(env, all);
      return _rbacJson({ ok:true });
    }

    // ── /format-story POST — Formatting raw text into HTML ─────────
    if (pathname === '/format-story' && request.method === 'POST') {
      let body;
      try { body = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      if (!body.text) return jsonError(400, 'No text provided.');
      
      const prompt = `You are an expert editor for VilfinTV, a premium financial news platform.
Format the following plain text story into professional HTML.
Use <h3> for subtitles, <p> for paragraphs, <strong> for emphasis, and <ul>/<li> for lists if needed.
DO NOT use <h1> or <h2>, as the main heading is handled separately.
DO NOT wrap the response in markdown code blocks like \`\`\`html.
CRITICAL: DO NOT summarize, shorten, or omit any content. You MUST format and return the ENTIRE story from beginning to end, no matter how long it is.
Return ONLY raw HTML.

Story:
${body.text}`;
      
      let html = '';
      
      // 1. Try Free Version (Pollinations)
      try {
        const pollRes = await fetchWithTimeout('https://text.pollinations.ai/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: 'mistral',
            messages: [{ role: 'user', content: prompt }],
            stream: false, private: true, max_tokens: 8192
          })
        }, 30000);
        if (pollRes.ok) {
          const raw = await pollRes.text();
          try {
             const pd = JSON.parse(raw);
             html = pd?.choices?.[0]?.message?.content || pd?.text || raw;
          } catch(e) { html = raw; }
          html = html.trim();
        }
      } catch (e) { /* ignore and fallback */ }

      // 2. Fallback to Gemini (via GitHub Secret)
      if (!html || html.length < 50) {
        const apiKey = env.GEMINI_API_KEY || env.Gemini_API_KEY_1;
        if (!apiKey) return jsonError(503, 'AI format failed and no fallback API key configured.');
        
        try {
          const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
          const resG = await fetchWithTimeout(geminiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contents: [{ parts: [{ text: prompt }] }],
              generationConfig: { maxOutputTokens: 8192, temperature: 0.2 },
            })
          }, 30000);
          
          if (!resG.ok) {
            let errText = 'AI generation failed.';
            try { const errData = await resG.json(); errText = errData.error?.message || JSON.stringify(errData); } catch(e) {}
            return jsonError(502, 'AI API Error: ' + errText);
          }
          const dataG = await resG.json();
          html = dataG.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || '';
        } catch (e) { return jsonError(500, 'Error calling fallback AI: ' + e.message); }
      }

      if (!html) return jsonError(502, 'AI returned empty response.');
      return new Response(JSON.stringify({ ok: true, html }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
    }

    // ── /api/generate-photo POST — Generating a photo from text using AI ──────
    if (pathname === '/api/generate-photo' && request.method === 'POST') {
      const auth = await _authOperator(request, env); if (auth.error) return auth.error;
      let body;
      try { body = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      if (!body.text || !body.heading) return jsonError(400, 'Missing heading or text.');

      const promptStr = `You are an expert AI image prompt engineer. Based on this news article heading, write a highly descriptive, visual, 15-word prompt for an AI image generator to create a perfect thumbnail. It must conceptually combine the key subjects (e.g., NRI, India, Bonds) into a single cohesive scene. Do NOT include any intro text, just the prompt itself. Make it realistic, cinematic, and professional.\n\nHeading: ${body.heading}`;

      let generatedKeywords = '';
      const apiKey = env.GEMINI_API_KEY || env.Gemini_API_KEY_1;
      const groqKey = env.GROQ_API_KEY;
      
      // 1. Try Groq first for super fast keyword extraction
      if (groqKey) {
        try {
          const resGroq = await fetchWithTimeout('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${groqKey}` },
            body: JSON.stringify({
              model: 'llama-3.1-8b-instant',
              messages: [{ role: 'user', content: promptStr }]
            })
          }, 10000);
          if (resGroq.ok) {
            const dataGroq = await resGroq.json();
            generatedKeywords = dataGroq.choices?.[0]?.message?.content?.trim() || '';
          }
        } catch(e) {}
      }
      
      // 2. Fallback to Gemini for keyword extraction
      if (!generatedKeywords && apiKey) {
        try {
           const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
           const resG = await fetchWithTimeout(geminiUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ contents: [{ parts: [{ text: promptStr }] }] })
           }, 15000);
           if (resG.ok) {
              const dataG = await resG.json();
              generatedKeywords = dataG.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || '';
           }
        } catch (e) {}
      }
      
      if (!generatedKeywords) generatedKeywords = 'finance business';
      
      // 3. Try Gemini Imagen 3 for Image Generation
      let imgBuffer = null;
      let geminiError = '';
      
      if (apiKey) {
         try {
           const imagenUrl = `https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key=${apiKey}`;
           const imgRes = await fetchWithTimeout(imagenUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                instances: [{ prompt: generatedKeywords + " , high quality professional stock photo, no text" }],
                parameters: { sampleCount: 1, aspectRatio: "16:9" }
              })
           }, 25000);
           
           if (imgRes.ok) {
              const imgData = await imgRes.json();
              if (imgData.predictions && imgData.predictions[0] && imgData.predictions[0].bytesBase64Encoded) {
                 const bin = atob(imgData.predictions[0].bytesBase64Encoded);
                 imgBuffer = Uint8Array.from(bin, c => c.charCodeAt(0));
              } else {
                 geminiError = 'Invalid response format from Gemini';
              }
           } else {
              geminiError = `HTTP ${imgRes.status}`;
           }
         } catch(e) {
           geminiError = e.message;
         }
      }
      
      // 4. Fallback to Pexels API
      if (!imgBuffer) {
        if (!env.PEXELS_API_KEY) return jsonError(503, `AI Photo Gen Failed: Gemini Imagen (${geminiError}) AND PEXELS_API_KEY is not configured.`);
        
        try {
           const pexelsUrl = `https://api.pexels.com/v1/search?query=${encodeURIComponent(generatedKeywords)}&per_page=1&orientation=landscape`;
           const pRes = await fetchWithTimeout(pexelsUrl, {
              headers: { 'Authorization': env.PEXELS_API_KEY }
           }, 15000);
           
           if (!pRes.ok) return jsonError(502, `Gemini (${geminiError}) | Pexels search failed: HTTP ${pRes.status}`);
           
           const pData = await pRes.json();
           if (!pData.photos || pData.photos.length === 0) {
               return jsonError(404, `No photos found on Pexels for keywords: ${generatedKeywords}`);
           }
           
           const imgUrl = pData.photos[0].src.large2x || pData.photos[0].src.large;
           const downRes = await fetchWithTimeout(imgUrl, { headers: { 'User-Agent': 'CloudflareWorker' } }, 20000);
           if (!downRes.ok) return jsonError(502, 'Failed to download the selected Pexels photo.');
           
           imgBuffer = await downRes.arrayBuffer();
        } catch (e) {
           return jsonError(500, 'Error processing Pexels fallback: ' + e.message);
        }
      }
      
      // 5. Save to R2
      try {
         const rand = Math.random().toString(36).slice(2, 10);
         const ym = new Date().toISOString().slice(0, 7);
         const key = `media/${ym}/stock-${Date.now()}-${rand}.jpg`;

         await env.MEDIA.put(key, imgBuffer, { httpMetadata: { contentType: 'image/jpeg' } });
         const url = `${new URL(request.url).origin}/r2/${key}`;

         return new Response(JSON.stringify({ ok: true, prompt: generatedKeywords, url, key }), { 
           status: 200, 
           headers: { ...CORS, 'Content-Type': 'application/json' } 
         });
         
      } catch (e) {
         return jsonError(500, 'Error uploading image to R2: ' + e.message);
      }
    }

    // ── /api/me  GET — return the caller's role + permissions ─────────────────
    if (pathname === '/api/me') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      const p = auth.payload || {};
      return _rbacJson({ ok: true, username: p.sub, role: p.role || 'operator', perms: (p.role === 'admin' ? null : (p.perms || {})) });
    }

    // ── /api/operators  GET — list operator accounts (admin only) ─────────────
    if (pathname === '/api/operators' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Account store not configured (IPTV_KV).');
      const all = await _opAll(env);
      const list = Object.values(all).map(function(o){ return { username:o.username, role:o.role, perms:o.perms||{}, disabled:!!o.disabled, updatedAt:o.updatedAt }; });
      return _rbacJson({ ok:true, operators:list });
    }

    // ── /api/operators/save  POST — create/update operator (admin only) ───────
    if (pathname === '/api/operators/save' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Account store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const uname = (b.username||'').toString().trim();
      if (!uname || uname.length > 64) return jsonError(400, 'Username is required (max 64 chars).');
      if (uname === env.ADMIN_USERNAME) return jsonError(400, 'That name is reserved for the admin.');
      const role = ['operator','auditor','admin'].indexOf(b.role) !== -1 ? b.role : 'operator';
      const perms = (b.perms && typeof b.perms === 'object') ? b.perms : {};
      const all = await _opAll(env);
      const existing = all[uname] || {};
      let salt = existing.salt, hash = existing.hash, iterations = existing.iterations;
      if (b.password) {
        if (b.password.length < 6) return jsonError(400, 'Password must be at least 6 characters.');
        const h = await _iptvHashPassword(b.password); salt = h.salt; hash = h.hash; iterations = h.iterations;
      }
      if (!hash) return jsonError(400, 'A password is required for a new account.');
      all[uname] = { username:uname, role:role, perms:perms, salt:salt, hash:hash, iterations:iterations,
        disabled: !!b.disabled, updatedAt: new Date().toISOString() };
      await env.IPTV_KV.put('console_operators', JSON.stringify(all));
      return _rbacJson({ ok:true, saved:true, username:uname });
    }

    // ── /api/operators/delete  POST — remove operator (admin only) ────────────
    if (pathname === '/api/operators/delete' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Account store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const uname = (b.username||'').toString().trim();
      const all = await _opAll(env);
      if (all[uname]) { delete all[uname]; await env.IPTV_KV.put('console_operators', JSON.stringify(all)); }
      return _rbacJson({ ok:true, deleted:true, username:uname });
    }

    // ══ Agent API keys (admin-managed; for the Hermes automation) ══════════════
    // ── /api/agent/keys  GET — list agent keys (admin only) ───────────────────
    if (pathname === '/api/agent/keys' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Agent store not configured (IPTV_KV).');
      const all = await _agAll(env);
      return _rbacJson({ ok:true, keys: Object.values(all).map(_agPublic) });
    }

    // ── /api/agent/keys/create  POST — mint a scoped agent key (admin only) ────
    if (pathname === '/api/agent/keys/create' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Agent store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const label = (b.label||'').toString().trim().slice(0,80) || 'Agent';
      let expiresAt = null;
      if (b.expiresAt) { const t = new Date(b.expiresAt); if (isNaN(t.getTime())) return jsonError(400, 'Invalid expiry date.'); expiresAt = t.toISOString(); }
      const scope = { publish: b.scope ? !!b.scope.publish : true, edit: b.scope ? !!b.scope.edit : false,
        delete: b.scope ? !!b.scope.delete : false, llm: b.scope ? !!b.scope.llm : false,
        images: b.scope ? !!b.scope.images : false, lessons: b.scope ? !!b.scope.lessons : false,
        operator: b.scope ? !!b.scope.operator : false };
      if (!scope.publish && !scope.edit && !scope.delete && !scope.llm && !scope.images && !scope.lessons && !scope.operator) scope.publish = true;
      const id     = _iptvHexFromBytes(crypto.getRandomValues(new Uint8Array(6)));
      const secret = _iptvHexFromBytes(crypto.getRandomValues(new Uint8Array(24)));
      const h = await _iptvHashPassword(secret);
      const all = await _agAll(env);
      all[id] = { id, label, scope, status:'pending', expiresAt,
        secretHash:h.hash, salt:h.salt, iterations:h.iterations,
        createdAt:new Date().toISOString(), requestedAt:null, lastUsedAt:null, disabled:false };
      await _agPut(env, all);
      // The full API key is returned ONCE here and never again.
      return _rbacJson({ ok:true, apiKey:`vtv.${id}.${secret}`, key:_agPublic(all[id]) });
    }

    // ── /api/agent/keys/approve  POST — activate a pending key (admin only) ────
    if (pathname === '/api/agent/keys/approve' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Agent store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const all = await _agAll(env); const k = all[(b.id||'').toString()];
      if (!k) return jsonError(404, 'Agent key not found.');
      k.status = 'active'; k.disabled = false; k.approvedAt = new Date().toISOString();
      await _agPut(env, all);
      return _rbacJson({ ok:true, key:_agPublic(k) });
    }

    // ── /api/agent/keys/revoke  POST — delete an agent key (admin only) ────────
    if (pathname === '/api/agent/keys/revoke' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Agent store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const id = (b.id||'').toString();
      const all = await _agAll(env);
      if (all[id]) { delete all[id]; await _agPut(env, all); }
      return _rbacJson({ ok:true, deleted:true, id });
    }

    // ── /api/agent/keys/update  POST — change label/expiry/scope (admin only) ──
    // Lets the admin grant new permissions (delete, llm) to an already-issued key
    // without regenerating its secret.
    if (pathname === '/api/agent/keys/update' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Agent store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const all = await _agAll(env); const k = all[(b.id||'').toString()];
      if (!k) return jsonError(404, 'Agent key not found.');
      if (typeof b.label === 'string' && b.label.trim()) k.label = b.label.trim().slice(0,80);
      if ('expiresAt' in b) {
        if (b.expiresAt) { const t = new Date(b.expiresAt); if (isNaN(t.getTime())) return jsonError(400, 'Invalid expiry date.'); k.expiresAt = t.toISOString(); }
        else k.expiresAt = null;
      }
      if (b.scope && typeof b.scope === 'object') {
        k.scope = { publish:!!b.scope.publish, edit:!!b.scope.edit, delete:!!b.scope.delete, llm:!!b.scope.llm, images:!!b.scope.images, lessons:!!b.scope.lessons, operator:!!b.scope.operator };
        if (!k.scope.publish && !k.scope.edit && !k.scope.delete && !k.scope.llm && !k.scope.images && !k.scope.lessons && !k.scope.operator) k.scope.publish = true;
      }
      await _agPut(env, all);
      return _rbacJson({ ok:true, key:_agPublic(k) });
    }

    // ── /api/agent/request  POST — agent asks to be activated (key auth) ───────
    // Records the activation request so the admin sees it in the console. If the
    // key is already active this just confirms status.
    if (pathname === '/api/agent/request' && request.method === 'POST') {
      const a = await _agentAuth(request, env); if (a.error) return a.error;
      const all = a.all, k = all[a.agent.id];
      k.requestedAt = new Date().toISOString();
      k.lastUsedAt  = k.requestedAt;
      await _agPut(env, all);
      return _rbacJson({ ok:true, status:k.status, scope:k.scope,
        message: k.status === 'active' ? 'Agent is active and may publish.' : 'Activation requested — awaiting administrator approval.' });
    }

    // ── /api/agent/publish  POST — scoped content publish/edit (key auth) ──────
    if (pathname === '/api/agent/publish' && request.method === 'POST') {
      const a = await _agentAuth(request, env); if (a.error) return a.error;
      const agent = a.agent;
      if (agent.status !== 'active') return jsonError(403, 'Agent not yet approved. Ask the administrator to activate this key in the console.');
      if (!env.GITHUB_TOKEN) return jsonError(503, 'GitHub not configured.');
      let body; try { body = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON.'); }
      const { id, section, heading, story, photo, link_url, days, photo_pos, photo_zoom, youtube, youtube_play } = body || {};
      const isEdit = !!id;
      const scope = agent.scope || {};
      if (isEdit && !scope.edit)   return jsonError(403, 'This agent key does not have edit permission.');
      if (!isEdit && !scope.publish) return jsonError(403, 'This agent key does not have publish permission.');
      const VALID_SECTIONS = ['trending','global','india','stock','malayalam',
        'ml_trending','ml_movies','ml_music','ml_local','ml_science','ml_space',
        'ml_sports','ml_health','ml_food','ml_realestate','ml_career','ml_tech',
        'sports','tech','space','science','fashion','movies','food','automobile','home','business',
        'story_triller','story_travel','story_health','story_comedy',
        'story_kids','story_education','story_animation','story_ai',
        'academy_notice','academy_cbse','academy_jlpt'];
      if (!section || !VALID_SECTIONS.includes(section)) return jsonError(400, 'Invalid section.');
      if (!heading || typeof heading !== 'string' || !heading.trim()) return jsonError(400, 'heading is required.');
      if (!story   || typeof story   !== 'string' || !story.trim())   return jsonError(400, 'story is required.');
      // Friendlier than the human console: silently strip any genuine inline
      // base64 image instead of failing the whole upload, then enforce the cap.
      let cleanStory = _sanitizeStory(story);
      if (!cleanStory.trim()) return jsonError(400, 'story is empty after sanitising.');
      let daysInt = parseInt(days); if (!daysInt || daysInt < 1 || daysInt > 365) daysInt = 30;

      const now = new Date();
      const expiresAt = new Date(now.getTime() + daysInt * 86400000).toISOString();

      function applyOptionalFields(o){
        if (photo && typeof photo === 'string' && photo.trim().startsWith('http')) {
          o.photo = photo.trim().slice(0,500);
        } else {
          // Callers (e.g. an AI agent) sometimes embed an <img> directly in
          // the story HTML instead of also passing photo_url - without a
          // top-level "photo" field, WhatsApp/social sharing (which reads
          // post.photo, not the story body) has nothing to share. Fall back
          // to the first embedded image so sharing still gets a picture.
          // The reader also gets that image as the top-of-story hero banner
          // (post.photo), so drop the embedded copy (and its caption <p>, if
          // any) from the body - otherwise the same photo shows twice.
          const imgMatch = cleanStory.match(/<p[^>]*>\s*<img[^>]+src=["']([^"']+)["'][^>]*>\s*<\/p>\s*(?:<p[^>]*>\s*<em>[\s\S]*?<\/em>\s*<\/p>\s*)?|<img[^>]+src=["']([^"']+)["'][^>]*>/i);
          const imgUrl = imgMatch && (imgMatch[1] || imgMatch[2]);
          if (imgUrl && imgUrl.startsWith('http')) {
            o.photo = imgUrl.slice(0,500);
            // o.story was already sliced from cleanStory at the call site
            // before this function ran, so strip the same match out of it
            // directly (not just out of cleanStory).
            const stripped = cleanStory.slice(0, imgMatch.index) + cleanStory.slice(imgMatch.index + imgMatch[0].length);
            cleanStory = stripped;
            if (typeof o.story === 'string') o.story = o.story.replace(imgMatch[0], '').trim();
          }
        }
        if (link_url && typeof link_url === 'string' && link_url.trim().startsWith('http')) o.link_url = link_url.trim().slice(0,500);
        if (photo_pos && typeof photo_pos === 'string') o.photo_pos = photo_pos.trim().slice(0,20);
        if (photo_zoom && !isNaN(parseFloat(photo_zoom))) o.photo_zoom = Math.min(Math.max(parseFloat(photo_zoom), 1), 4);
        const ytVid = _ytId(youtube); if (ytVid) { o.youtube = ytVid; o.youtube_play = youtube_play !== false; }
        return o;
      }

      // Computed once, outside the retry loop below: applyOptionalFields has a
      // one-time side effect (stripping an embedded <img> out of cleanStory),
      // so it must not run more than once even if the write below retries.
      const withOptional = applyOptionalFields({ section, heading: heading.trim().slice(0,200),
        story: cleanStory.trim().slice(0,MAX_STORY), published_at: now.toISOString(), expires_at: expiresAt });

      const computeFn = (freshItems) => {
        const items = freshItems.filter(i => i && (!i.expires_at || new Date(i.expires_at) > now));
        if (isEdit) {
          const idx = items.findIndex(i => String(i.id) === String(id));
          if (idx === -1) return _CONTENT_NOT_FOUND;
          const resultId = items[idx].id;
          items[idx] = { ...withOptional, id: resultId };
          return { items, message: `feat(content): agent edit ${section} [${agent.label}]`, meta: { resultId } };
        } else {
          const resultId = String(Date.now());
          items.push({ ...withOptional, id: resultId });
          return { items, message: `feat(content): agent publish ${section} [${agent.label}]`, meta: { resultId } };
        }
      };
      let written;
      try { written = await _ghWriteContentSafe(env, computeFn); }
      catch (e) { return jsonError(502, e.message); }
      if (written === _CONTENT_NOT_FOUND) return jsonError(404, 'Post to edit not found (it may have expired).');
      const resultId = written.meta.resultId;

      // record usage
      try { const all = await _agAll(env); if (all[agent.id]) { all[agent.id].lastUsedAt = now.toISOString(); await _agPut(env, all); } } catch(_){}
      return new Response(JSON.stringify({ ok:true, id:resultId, edited:isEdit, expires_at:expiresAt,
        url:`https://vilfintv.com/news.html?story=${resultId}` }), { status:200, headers:{ ...CORS, 'Content-Type':'application/json' } });
    }

    // ── /api/agent/delete  POST — remove a published story by id (key auth) ────
    if (pathname === '/api/agent/delete' && request.method === 'POST') {
      const a = await _agentAuth(request, env); if (a.error) return a.error;
      const agent = a.agent;
      if (agent.status !== 'active') return jsonError(403, 'Agent not yet approved.');
      if (!(agent.scope && agent.scope.delete)) return jsonError(403, 'This agent key does not have delete permission.');
      if (!env.GITHUB_TOKEN) return jsonError(503, 'GitHub not configured.');
      let body; try { body = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON.'); }
      const delId = (body.id||'').toString().trim();
      if (!delId) return jsonError(400, 'id is required.');
      const computeFn = (freshItems) => {
        const before = freshItems.length;
        const items = freshItems.filter(i => String(i.id) !== delId);
        if (items.length === before) return _CONTENT_NOT_FOUND;
        return { items, message: `chore(content): agent delete ${delId} [${agent.label}]`, meta: { delId } };
      };
      let written;
      try { written = await _ghWriteContentSafe(env, computeFn); }
      catch (e) { return jsonError(502, e.message); }
      if (written === _CONTENT_NOT_FOUND) return jsonError(404, 'Story not found (already removed or expired).');

      try { const all = await _agAll(env); if (all[agent.id]) { all[agent.id].lastUsedAt = new Date().toISOString(); await _agPut(env, all); } } catch(_){}
      return new Response(JSON.stringify({ ok:true, deleted:delId }), { status:200, headers:{ ...CORS, 'Content-Type':'application/json' } });
    }

    // ── /api/agent/llm  GET — agent reads the LLM config (key auth, llm scope) ─
    // Returns the FULL provider config (incl. API keys) so the agent can build its
    // LiteLLM config on its own server. Requires the 'llm' scope.
    if (pathname === '/api/agent/llm' && request.method === 'GET') {
      const a = await _agentAuth(request, env); if (a.error) return a.error;
      const agent = a.agent;
      if (agent.status !== 'active') return jsonError(403, 'Agent not yet approved.');
      if (!(agent.scope && agent.scope.llm)) return jsonError(403, 'This agent key does not have LLM-config permission.');
      const cfg = await _llmAll(env);
      const def = cfg.providers.find(p => p.isDefault) || cfg.providers[0] || null;
      // Attach the live catalogue for any rotate sentinel: "<provider>/free-rotate"
      // → free models only; "<provider>/all-rotate" → every model incl. paid.
      // Each entry carries {id,provider,image,free} so the agent filters by the
      // chosen provider (or all, for "openrouter/...") and by text/image.
      let freeModels = [], allModels = [];
      const needFree = cfg.providers.some(p => /\/free-rotate$/.test(p.model || ''));
      const needAll  = cfg.providers.some(p => /\/all-rotate$/.test(p.model || ''));
      if (needFree || needAll) {
        const cat = (await _orModels(env)).map(m => ({ id: m.id, provider: m.provider, image: !!m.image, free: !!m.free }));
        if (needFree) freeModels = cat.filter(m => m.free);
        if (needAll)  allModels  = cat;
      }
      try { const all = await _agAll(env); if (all[agent.id]) { all[agent.id].lastUsedAt = new Date().toISOString(); await _agPut(env, all); } } catch(_){}
      return new Response(JSON.stringify({ ok:true, providers: cfg.providers, default: def ? def.id : null, freeModels: freeModels, allModels: allModels }),
        { status:200, headers:{ ...CORS, 'Content-Type':'application/json' } });
    }

    // ── /api/agent/images  GET — agent reads image-source keys (images scope) ──
    if (pathname === '/api/agent/images' && request.method === 'GET') {
      const a = await _agentAuth(request, env); if (a.error) return a.error;
      const agent = a.agent;
      if (agent.status !== 'active') return jsonError(403, 'Agent not yet approved.');
      if (!(agent.scope && agent.scope.images)) return jsonError(403, 'This agent key does not have image-source permission.');
      const cfg = await _imgAll(env);
      const def = cfg.sources.find(s => s.isDefault) || cfg.sources[0] || null;
      try { const all = await _agAll(env); if (all[agent.id]) { all[agent.id].lastUsedAt = new Date().toISOString(); await _agPut(env, all); } } catch(_){}
      return new Response(JSON.stringify({ ok:true, sources: cfg.sources, default: def ? def.id : null }),
        { status:200, headers:{ ...CORS, 'Content-Type':'application/json' } });
    }

    // ══ Image-repository sources (admin-managed) ═══════════════════════════════
    if (pathname === '/api/images/config' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      const cfg = await _imgAll(env);
      return _rbacJson({ ok:true, sources: cfg.sources.map(_imgPublic) });
    }
    if (pathname === '/api/images/save' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const name = (b.name||'').toString().trim().slice(0,80);
      const provider = (b.provider||'').toString().trim().slice(0,40);
      if (!name)     return jsonError(400, 'Source name is required.');
      if (!provider) return jsonError(400, 'Provider is required.');
      const cfg = await _imgAll(env);
      let entry;
      if (b.id) { entry = cfg.sources.find(s => s.id === String(b.id)); if (!entry) return jsonError(404, 'Source not found.'); }
      else { entry = { id: _iptvHexFromBytes(crypto.getRandomValues(new Uint8Array(5))), createdAt: new Date().toISOString() }; cfg.sources.push(entry); }
      entry.name = name; entry.provider = provider;
      if (typeof b.apiKey === 'string' && b.apiKey.trim()) entry.apiKey = b.apiKey.trim().slice(0,400);
      if (b.isDefault) { cfg.sources.forEach(s => { s.isDefault = (s === entry); }); }
      else if (cfg.sources.length === 1) entry.isDefault = true;
      await _imgPut(env, cfg);
      return _rbacJson({ ok:true, source: _imgPublic(entry) });
    }
    if (pathname === '/api/images/delete' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const cfg = await _imgAll(env);
      const removed = cfg.sources.find(s => s.id === String(b.id));
      cfg.sources = cfg.sources.filter(s => s.id !== String(b.id));
      if (removed && removed.isDefault && cfg.sources.length) cfg.sources[0].isDefault = true;
      await _imgPut(env, cfg);
      return _rbacJson({ ok:true, deleted: String(b.id||'') });
    }
    if (pathname === '/api/images/default' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const cfg = await _imgAll(env);
      let found = false; cfg.sources.forEach(s => { s.isDefault = (s.id === String(b.id)); if (s.isDefault) found = true; });
      if (!found) return jsonError(404, 'Source not found.');
      await _imgPut(env, cfg);
      return _rbacJson({ ok:true });
    }

    // ── /api/subscribers  GET — list mailing-list subscribers (admin only) ──────
    // Proxies to the vilfintv-subscribe-worker D1 endpoint so the SUBSCRIBER_WORKER_URL
    // and SUBSCRIBER_WORKER_SECRET are never exposed in client-side code.
    if (pathname === '/api/subscribers' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      const subUrl    = (env.SUBSCRIBER_WORKER_URL || '').trim();
      const subSecret = (env.SUBSCRIBER_WORKER_SECRET || '').trim();
      if (!subUrl || !subSecret) return jsonError(503, 'Subscriber worker not configured (set SUBSCRIBER_WORKER_URL and SUBSCRIBER_WORKER_SECRET secrets).');
      let emails;
      try {
        const r = await fetch(subUrl + '?action=list', { headers: { Authorization: 'Bearer ' + subSecret } });
        if (!r.ok) return jsonError(502, 'Subscriber worker returned ' + r.status + ': ' + await r.text());
        emails = await r.json();
      } catch (e) { return jsonError(502, 'Failed to reach subscriber worker: ' + e.message); }
      return new Response(JSON.stringify({ ok: true, count: emails.length, subscribers: emails }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
    }

    // ── /api/subscribers/remove  POST — remove an email (admin only) ──────────
    if (pathname === '/api/subscribers/remove' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      const subUrl    = (env.SUBSCRIBER_WORKER_URL || '').trim();
      const subSecret = (env.SUBSCRIBER_WORKER_SECRET || '').trim();
      if (!subUrl || !subSecret) return jsonError(503, 'Subscriber worker not configured.');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const email = (b.email||'').trim();
      if (!email || !email.includes('@')) return jsonError(400, 'Valid email required.');
      try {
        const r = await fetch(subUrl + '?action=unsubscribe&email=' + encodeURIComponent(email), { method: 'POST', headers: { Authorization: 'Bearer ' + subSecret } });
        if (!r.ok) return jsonError(502, 'Subscriber worker returned ' + r.status);
      } catch (e) { return jsonError(502, 'Failed to reach subscriber worker: ' + e.message); }
      return new Response(JSON.stringify({ ok: true, removed: email }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
    }

    // ══ Academy lessons (lessons.json — appended to education.html hubs) ═══════
    // ── /api/agent/lessons  GET — agent reads current lessons (lessons scope) ──
    if (pathname === '/api/agent/lessons' && request.method === 'GET') {
      const a = await _agentAuth(request, env); if (a.error) return a.error;
      if (a.agent.status !== 'active') return jsonError(403, 'Agent not yet approved.');
      if (!(a.agent.scope && a.agent.scope.lessons)) return jsonError(403, 'This agent key does not have lessons permission.');
      let read; try { read = await _ghReadJsonFile(env, 'lessons.json'); } catch (e) { return jsonError(502, e.message); }
      return new Response(JSON.stringify({ ok:true, hubs: LESSON_HUBS, lessons: read.data }),
        { status:200, headers:{ ...CORS, 'Content-Type':'application/json' } });
    }

    // ── /api/agent/lesson  POST — append a lesson to a hub (lessons scope) ─────
    if (pathname === '/api/agent/lesson' && request.method === 'POST') {
      const a = await _agentAuth(request, env); if (a.error) return a.error;
      const agent = a.agent;
      if (agent.status !== 'active') return jsonError(403, 'Agent not yet approved.');
      if (!(agent.scope && agent.scope.lessons)) return jsonError(403, 'This agent key does not have lessons permission.');
      if (!env.GITHUB_TOKEN) return jsonError(503, 'GitHub not configured.');
      let body; try { body = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON.'); }
      const hub = (body.hub||'').toString().trim();
      const lesson = body.lesson;
      if (LESSON_HUBS.indexOf(hub) === -1) return jsonError(400, 'Invalid hub. Use one of: ' + LESSON_HUBS.join(', '));
      if (!lesson || typeof lesson !== 'object' || Array.isArray(lesson)) return jsonError(400, 'lesson must be an object.');
      if (!lesson.title || !String(lesson.title).trim()) return jsonError(400, 'lesson.title is required.');
      if (JSON.stringify(lesson).length > 20000) return jsonError(413, 'Lesson too large (max ~20KB).');
      let read; try { read = await _ghReadJsonFile(env, 'lessons.json'); } catch (e) { return jsonError(502, e.message); }
      const data = read.data; if (!Array.isArray(data[hub])) data[hub] = [];
      lesson._id = _iptvHexFromBytes(crypto.getRandomValues(new Uint8Array(5)));
      lesson._added = new Date().toISOString();
      data[hub].push(lesson);
      try { await _ghWriteJsonFile(env, 'lessons.json', data, read.sha, `feat(lessons): agent add ${hub} lesson [${agent.label}]`); }
      catch (e) { return jsonError(502, e.message); }
      try { const all = await _agAll(env); if (all[agent.id]) { all[agent.id].lastUsedAt = new Date().toISOString(); await _agPut(env, all); } } catch(_){}
      return new Response(JSON.stringify({ ok:true, id:lesson._id, hub:hub, count:data[hub].length }),
        { status:200, headers:{ ...CORS, 'Content-Type':'application/json' } });
    }

    // ── /api/lessons  GET — list all agent-added lessons (admin only) ──────────
    if (pathname === '/api/lessons' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      let read; try { read = await _ghReadJsonFile(env, 'lessons.json'); } catch (e) { return jsonError(502, e.message); }
      return _rbacJson({ ok:true, hubs: LESSON_HUBS, lessons: read.data });
    }

    // ── /api/lessons/save  POST — add/replace a lesson in a hub (admin only) ───
    if (pathname === '/api/lessons/save' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.GITHUB_TOKEN) return jsonError(503, 'GitHub not configured.');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const hub = (b.hub||'').toString().trim();
      const lesson = b.lesson;
      if (LESSON_HUBS.indexOf(hub) === -1) return jsonError(400, 'Invalid hub.');
      if (!lesson || typeof lesson !== 'object' || Array.isArray(lesson)) return jsonError(400, 'lesson must be an object.');
      if (!lesson.title || !String(lesson.title).trim()) return jsonError(400, 'lesson.title is required.');
      if (JSON.stringify(lesson).length > 20000) return jsonError(413, 'Lesson too large (max ~20KB).');
      let read; try { read = await _ghReadJsonFile(env, 'lessons.json'); } catch (e) { return jsonError(502, e.message); }
      const data = read.data; if (!Array.isArray(data[hub])) data[hub] = [];
      if (b.id) { const idx = data[hub].findIndex(l => l._id === String(b.id)); if (idx === -1) return jsonError(404, 'Lesson not found.'); lesson._id = String(b.id); lesson._added = data[hub][idx]._added || new Date().toISOString(); data[hub][idx] = lesson; }
      else { lesson._id = _iptvHexFromBytes(crypto.getRandomValues(new Uint8Array(5))); lesson._added = new Date().toISOString(); data[hub].push(lesson); }
      try { await _ghWriteJsonFile(env, 'lessons.json', data, read.sha, `chore(lessons): admin save ${hub} lesson`); }
      catch (e) { return jsonError(502, e.message); }
      return _rbacJson({ ok:true, id:lesson._id, hub:hub });
    }

    // ── /api/lessons/delete  POST — remove a lesson from a hub (admin only) ────
    if (pathname === '/api/lessons/delete' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.GITHUB_TOKEN) return jsonError(503, 'GitHub not configured.');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const hub = (b.hub||'').toString().trim();
      if (LESSON_HUBS.indexOf(hub) === -1) return jsonError(400, 'Invalid hub.');
      let read; try { read = await _ghReadJsonFile(env, 'lessons.json'); } catch (e) { return jsonError(502, e.message); }
      const data = read.data; if (!Array.isArray(data[hub])) return jsonError(404, 'No lessons for that hub.');
      const before = data[hub].length;
      data[hub] = data[hub].filter(l => l._id !== String(b.id));
      if (data[hub].length === before) return jsonError(404, 'Lesson not found.');
      try { await _ghWriteJsonFile(env, 'lessons.json', data, read.sha, `chore(lessons): admin delete ${hub} lesson`); }
      catch (e) { return jsonError(502, e.message); }
      return _rbacJson({ ok:true, deleted:String(b.id||''), hub:hub });
    }

    // ══ LLM / LiteLLM provider config (admin-managed) ══════════════════════════
    // ── /api/llm/config  GET — list providers (keys masked) (admin only) ───────
    if (pathname === '/api/llm/config' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      const cfg = await _llmAll(env);
      return _rbacJson({ ok:true, providers: cfg.providers.map(_llmPublic) });
    }

    // ── /api/llm/save  POST — add or update a provider (admin only) ────────────
    if (pathname === '/api/llm/save' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const name = (b.name||'').toString().trim().slice(0,80);
      const provider = (b.provider||'').toString().trim().slice(0,40);
      const model = (b.model||'').toString().trim().slice(0,120);
      if (!name)     return jsonError(400, 'AI name is required.');
      if (!provider) return jsonError(400, 'Provider is required.');
      if (!model)    return jsonError(400, 'Default model is required.');
      const cfg = await _llmAll(env);
      let entry;
      if (b.id) { entry = cfg.providers.find(p => p.id === String(b.id)); if (!entry) return jsonError(404, 'Provider entry not found.'); }
      else { entry = { id: _iptvHexFromBytes(crypto.getRandomValues(new Uint8Array(5))), createdAt: new Date().toISOString() }; cfg.providers.push(entry); }
      entry.name = name; entry.provider = provider; entry.model = model;
      entry.apiBase = (b.apiBase||'').toString().trim().slice(0,200);
      // keep the existing key when the field is left blank on edit
      if (typeof b.apiKey === 'string' && b.apiKey.trim()) entry.apiKey = b.apiKey.trim().slice(0,400);
      if (b.isDefault) { cfg.providers.forEach(p => { p.isDefault = (p === entry); }); }
      else if (cfg.providers.length === 1) entry.isDefault = true;
      await _llmPut(env, cfg);
      return _rbacJson({ ok:true, provider: _llmPublic(entry) });
    }

    // ── /api/llm/delete  POST — remove a provider (admin only) ─────────────────
    if (pathname === '/api/llm/delete' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const cfg = await _llmAll(env);
      const was = cfg.providers.length;
      const removed = cfg.providers.find(p => p.id === String(b.id));
      cfg.providers = cfg.providers.filter(p => p.id !== String(b.id));
      // if we removed the default, promote the first remaining one
      if (removed && removed.isDefault && cfg.providers.length) cfg.providers[0].isDefault = true;
      if (cfg.providers.length !== was) await _llmPut(env, cfg);
      return _rbacJson({ ok:true, deleted: String(b.id||'') });
    }

    // ── /api/llm/default  POST — set the default provider (admin only) ─────────
    if (pathname === '/api/llm/default' && request.method === 'POST') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
      const cfg = await _llmAll(env);
      let found = false; cfg.providers.forEach(p => { p.isDefault = (p.id === String(b.id)); if (p.isDefault) found = true; });
      if (!found) return jsonError(404, 'Provider entry not found.');
      await _llmPut(env, cfg);
      return _rbacJson({ ok:true });
    }

    // ── /api/llm/models  GET — OpenRouter catalogue for the dropdowns (admin) ──
    // Server-side fetch (no CORS issues) of the public OpenRouter model list, then
    // simplified to {id,name,provider,free}. Cached for an hour at the edge.
    if (pathname === '/api/llm/models' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      const models = await _orModels(env);
      return new Response(JSON.stringify({ ok:true, models }), { status:200,
        headers:{ ...CORS, 'Content-Type':'application/json', 'Cache-Control':'public, max-age=3600' } });
    }

    // ── /api/admin/profile  GET/POST — admin display profile (admin only) ─────
    if (pathname === '/api/admin/profile') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      if (!env.IPTV_KV) return jsonError(503, 'Store not configured (IPTV_KV).');
      if (request.method === 'GET') {
        let prof = {}; try { const r = await env.IPTV_KV.get('console_admin_profile'); prof = r ? JSON.parse(r) : {}; } catch(e){}
        return _rbacJson({ ok:true, profile: prof, username: auth.payload.sub });
      }
      if (request.method === 'POST') {
        let b; try { b = await request.json(); } catch(_) { return jsonError(400, 'Invalid JSON body.'); }
        const prof = { displayName:(b.displayName||'').toString().slice(0,80), org:(b.org||'').toString().slice(0,80),
          email:(b.email||'').toString().slice(0,120), timezone:(b.timezone||'').toString().slice(0,60), updatedAt:new Date().toISOString() };
        await env.IPTV_KV.put('console_admin_profile', JSON.stringify(prof));
        return _rbacJson({ ok:true, saved:true, profile:prof });
      }
      return jsonError(405, 'Use GET or POST.');
    }

    // ── /api/status-report  GET — multi-source site status (admin only) ───────
    if (pathname === '/api/status-report' && request.method === 'GET') {
      const auth = await requireAuth(request, env); if (auth.error) return auth.error;
      if ((auth.payload||{}).role !== 'admin') return jsonError(403, 'Admin only.');
      const report = await buildStatusReport(env);
      return _rbacJson({ ok:true, report });
    }

    // ── /api/iptv/config  GET — current IPTV login id + settings (auth) ───────
    if (pathname === '/api/iptv/config') {
      if (request.method !== 'GET') return jsonError(405, 'Method not allowed. Use GET for /api/iptv/config.');
      const auth = await _authOperator(request, env);
      if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured. Bind a KV namespace as IPTV_KV.');
      let authObj = null, settings = null;
      try { const r = await env.IPTV_KV.get('iptv_auth');     authObj  = r ? JSON.parse(r) : {}; } catch (e) { authObj = {}; }
      try { const r = await env.IPTV_KV.get('iptv_settings'); settings = r ? JSON.parse(r) : null; } catch (e) {}
      if (!authObj) authObj = {};
      if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
      const accounts = Object.values(authObj).filter(a => a && typeof a === 'object').map(a => ({
        username: a.username,
        updatedAt: a.updatedAt,
        expireDate: a.expireDate,
        maxBoundDevices: a.maxBoundDevices,
        maxActiveSessions: a.maxActiveSessions,
        loginCount: a.loginCount,
        devices: a.devices ? Object.keys(a.devices).length : 0
      }));
      return _iptvJson({
        ok: true,
        accounts: accounts,
        credentialsSet: accounts.length > 0,
        settings:  settings || IPTV_DEFAULT_SETTINGS,
      });
    }

    // ── /api/iptv/credentials  POST — set IPTV login id + password (auth) ─────
    if (pathname === '/api/iptv/credentials') {
      if (request.method !== 'POST') return jsonError(405, 'Method not allowed. Use POST for /api/iptv/credentials.');
      const auth = await _authOperator(request, env);
      if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured. Bind a KV namespace as IPTV_KV.');
      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
      const username = (body.username || '').toString().trim();
      const password = (body.password || '').toString();
      if (!username || username.length > 64) return jsonError(400, 'Username is required (max 64 chars).');
      
      let authObj = null;
      try { const r = await env.IPTV_KV.get('iptv_auth'); authObj = r ? JSON.parse(r) : {}; } catch (e) { authObj = {}; }
      if (!authObj) authObj = {};
      if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
      
      const existing = authObj[username];
      if (!existing && (!password || password.length < 6)) return jsonError(400, 'Password must be at least 6 characters for a new account.');
      if (password && password.length > 0 && password.length < 6) return jsonError(400, 'Password must be at least 6 characters.');
      
      const rec = existing || { username: username, loginCount: 0, devices: {} };
      if (password) {
        const h = await _iptvHashPassword(password);
        rec.algo = 'pbkdf2-sha256';
        rec.iterations = h.iterations;
        rec.salt = h.salt;
        rec.hash = h.hash;
      }
      
      rec.expireDate = body.expireDate ? body.expireDate : null;
      rec.maxBoundDevices = body.maxBoundDevices ? parseInt(body.maxBoundDevices) : null;
      rec.maxActiveSessions = body.maxActiveSessions ? parseInt(body.maxActiveSessions) : null;
      rec.updatedAt = new Date().toISOString();
      
      authObj[username] = rec;
      await env.IPTV_KV.put('iptv_auth', JSON.stringify(authObj));
      return _iptvJson({ ok: true, saved: true, username: username });
    }

    // ── /api/iptv/clear-devices  POST — clear bound devices for an account ─────
    if (pathname === '/api/iptv/clear-devices') {
      if (request.method !== 'POST') return jsonError(405, 'Method not allowed.');
      const auth = await _authOperator(request, env); if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured.');
      let body; try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
      const username = (body.username || '').toString().trim();
      if (!username) return jsonError(400, 'Username is required.');
      let authObj = null; try { const r = await env.IPTV_KV.get('iptv_auth'); authObj = r ? JSON.parse(r) : {}; } catch (e) { authObj = {}; }
      if (!authObj) authObj = {};
      if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
      if (authObj[username]) {
        authObj[username].devices = {};
        await env.IPTV_KV.put('iptv_auth', JSON.stringify(authObj));
      }
      return _iptvJson({ ok: true, cleared: true, username: username });
    }

    // ── /api/iptv/kill-sessions  POST — kill active sessions for an account ────
    if (pathname === '/api/iptv/kill-sessions') {
      if (request.method !== 'POST') return jsonError(405, 'Method not allowed.');
      const auth = await _authOperator(request, env); if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured.');
      let body; try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
      const username = (body.username || '').toString().trim();
      if (!username) return jsonError(400, 'Username is required.');
      
      const allSess = await _sessAll(env);
      let killed = 0;
      for (const k of Object.keys(allSess)) {
        if (allSess[k] && allSess[k].username === username) {
          delete allSess[k];
          killed++;
        }
      }
      if (killed > 0) await _sessPut(env, allSess);
      return _iptvJson({ ok: true, killed: killed, username: username });
    }

    // ── /api/iptv/delete-account  POST — delete IPTV login id (auth) ──────────
    if (pathname === '/api/iptv/delete-account') {
      if (request.method !== 'POST') return jsonError(405, 'Method not allowed. Use POST for /api/iptv/delete-account.');
      const auth = await _authOperator(request, env);
      if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured.');
      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
      const username = (body.username || '').toString().trim();
      if (!username) return jsonError(400, 'Username is required.');
      let authObj = null;
      try { const r = await env.IPTV_KV.get('iptv_auth'); authObj = r ? JSON.parse(r) : {}; } catch (e) { authObj = {}; }
      if (!authObj) authObj = {};
      if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
      if (authObj[username]) {
        delete authObj[username];
        await env.IPTV_KV.put('iptv_auth', JSON.stringify(authObj));
      }
      return _iptvJson({ ok: true, deleted: true, username: username });
    }

    // ── /api/iptv/settings  POST — update IPTV console settings (auth) ────────
    if (pathname === '/api/iptv/settings') {
      if (request.method !== 'POST') return jsonError(405, 'Method not allowed. Use POST for /api/iptv/settings.');
      const auth = await _authOperator(request, env);
      if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured. Bind a KV namespace as IPTV_KV.');
      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
      const s = body.settings || body || {};
      let parsedProviders = [];
      if (Array.isArray(s.providers)) {
        for (const p of s.providers) {
          parsedProviders.push({
            id: (p.id || '').toString().trim() || 'prov_' + Math.random().toString(36).substr(2, 9),
            name: (p.name || 'Unnamed').toString().trim(),
            icon: (p.icon || '').toString().trim(),
            group: (p.group || '').toString().trim(),
            region: (p.region || '').toString().trim(),
            enabled: p.enabled === undefined ? true : !!p.enabled,
            url: (p.url || '').toString().trim(),
            epg: (p.epg || '').toString().trim()
          });
        }
      } else {
        const IPTV_PROV = [
          {id: 'jio', name: 'Jio IPTV', icon: 'J'},
          {id: 'airtel', name: 'Airtel IPTV', icon: 'A'},
          {id: 'free', name: 'Free IPTV', icon: 'F'},
          {id: 'pro', name: 'IPTV Pro', icon: 'P'},
          {id: 'custom', name: 'Custom', icon: 'C'}
        ];
        for (const p of IPTV_PROV) {
          const sp = (s.providers && s.providers[p.id]) || {};
          parsedProviders.push({
            id: p.id,
            name: p.name,
            icon: p.icon,
            enabled: sp.enabled === undefined ? true : !!sp.enabled,
            url: (sp.url || '').toString().trim(),
            epg: (sp.epg || '').toString().trim()
          });
        }
      }
      // Manually-added single channels (name + direct .m3u8 URL), capped at 500.
      let customChannels = [];
      if (Array.isArray(s.customChannels)) {
        for (const c of s.customChannels) {
          const url = (c && c.url || '').toString().trim();
          const name = (c && c.name || '').toString().trim();
          if (!url || !name) continue;
          customChannels.push({ name: name.slice(0, 180), url: url.slice(0, 2000), category: (c && c.category || 'Custom').toString().trim().slice(0, 80) });
          if (customChannels.length >= 500) break;
        }
      }
      const settings = {
        sessionHours: Math.max(1, Math.min(168, parseInt(s.sessionHours, 10) || 8)),
        defaultProvider: s.defaultProvider || 'free',
        providers: parsedProviders,
        customChannels: customChannels,
        updatedAt: new Date().toISOString(),
      };
      await env.IPTV_KV.put('iptv_settings', JSON.stringify(settings));
      // Adding/removing a custom channel should show right away — drop the merged-all cache.
      try { await env.IPTV_KV.delete('cache_merge_all'); } catch (e) {}
      return _iptvJson({ ok: true, saved: true, settings: settings });
    }

    // ── /api/jio/auth  GET/POST — Bridging Jio OTP for local server ──
    if (pathname === '/api/jio/auth') {
      const bridgeAuth = request.headers.get("X-Jio-Bridge");
      if (bridgeAuth !== "vilfin-secret-jio") {
        const auth = await _authOperator(request, env);
        if (auth.error) return auth.error;
      }

      if (request.method === 'POST') {
        let body;
        try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
        
        if (body.action === "save_m3u" && body.m3u) {
            if (env.IPTV_CACHE) {
              await env.IPTV_CACHE.put('jio_playlist', body.m3u, { customMetadata: { expires: String(Date.now() + 31536000000) } });
            }
            if (!env.IPTV_KV) return jsonError(503, "KV not configured");
            await env.IPTV_KV.put('jio_playlist', body.m3u);
            return _iptvJson({ ok: true });
          }
          
          if (body.action === "save_epg" && body.epg) {
            if (env.IPTV_CACHE) {
              await env.IPTV_CACHE.put('jio_epg', body.epg, { customMetadata: { expires: String(Date.now() + 31536000000) } });
            }
            if (!env.IPTV_KV) return jsonError(503, "KV not configured");
            await env.IPTV_KV.put('jio_epg', body.epg);
            return _iptvJson({ ok: true });
          }

          if (body.action === "save_auth" && body.auth) {
          if (!env.IPTV_KV) return jsonError(503, "KV not configured");
          await env.IPTV_KV.put('jio_auth_creds', JSON.stringify(body.auth));
          if (body.tunnel_url) {
            await env.IPTV_KV.put('jio_tunnel_url', body.tunnel_url);
          }
          return _iptvJson({ ok: true, saved: true });
        }

        // Polled every few seconds by jio_bridge.py while an OTP flow is in
        // progress — stored in R2 (not KV) since KV's free tier is a hard
        // 100k-reads/day cap that this poll alone was burning through; R2's
        // free tier (10M Class B ops/month) has plenty of headroom for it.
        if (!env.IPTV_CACHE) return jsonError(503, "R2 cache not configured");
        await env.IPTV_CACHE.put('jio_auth_request', JSON.stringify({ ...body, ts: Date.now() }));
        return _iptvJson({ ok: true, saved: true });
      } else if (request.method === 'GET') {
        if (!env.IPTV_CACHE) return jsonError(503, "R2 cache not configured");
        const obj = await env.IPTV_CACHE.get('jio_auth_request');
        const current = obj ? await obj.text() : null;
        return _iptvJson({ ok: true, data: current ? JSON.parse(current) : null });
      }
      return jsonError(405, 'Method not allowed.');
    }

    // ── /api/jio/proxy  GET ──
    if (pathname === '/api/jio/proxy') {
      const targetUrl = searchParams.get('url');
      if (!targetUrl) return jsonError(400, 'Missing url parameter');
      try {
        const resp = await fetch(targetUrl, {
          method: request.method,
          headers: { 'User-Agent': request.headers.get('User-Agent') || 'okhttp/4.9.0' },
          body: request.method === 'POST' ? await request.text() : undefined
        });
        const data = await resp.arrayBuffer();
        const headers = new Headers(resp.headers);
        headers.set('Access-Control-Allow-Origin', '*');
        return new Response(data, { status: resp.status, headers });
      } catch(e) { return jsonError(500, String(e)); }
    }

    // ── /api/post-link  POST — append an external link to links.json via GitHub API ──
    if (pathname === '/api/post-link') {
      if (request.method !== 'POST') {
        return jsonError(405, 'Method not allowed. Use POST for /api/post-link.');
      }

      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }

      const { url, days, name, description } = body || {};

      const auth = await _authOperator(request, env);
      if (auth.error) return auth.error;

      if (!url || typeof url !== 'string') {
        return jsonError(400, 'Missing or invalid url.');
      }
      try { new URL(url); } catch (_) { return jsonError(400, 'url is not a valid URL.'); }
      const daysInt = parseInt(days);
      if (!daysInt || daysInt < 1 || daysInt > 90) {
        return jsonError(400, 'days must be an integer between 1 and 90.');
      }
      if (!env || !env.GITHUB_TOKEN) {
        return jsonError(503, 'GitHub integration not configured. Set GITHUB_TOKEN in Worker environment.');
      }

      const REPO      = 'Vilfin-TV/MultiScreener';
      const FILE_PATH = 'links.json';
      const BRANCH    = 'main';
      const GH_API    = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;
      const GH_HEADERS = {
        'Authorization': `token ${env.GITHUB_TOKEN}`,
        'Accept':        'application/vnd.github.v3+json',
        'User-Agent':    'vilfintv-screener-proxy',
        'Content-Type':  'application/json',
      };

      // 1. GET current file
      let sha   = null;
      let links = [];
      try {
        const ghGet = await fetch(`${GH_API}?ref=${BRANCH}`, { headers: GH_HEADERS });
        if (ghGet.ok) {
          const fileData = await ghGet.json();
          sha = fileData.sha;
          const decoded = _b64DecodeUnicode(fileData.content.replace(/\n/g, ''));
          links = JSON.parse(decoded);
          if (!Array.isArray(links)) links = [];
        } else if (ghGet.status !== 404) {
          const err = await ghGet.text();
          return jsonError(502, `GitHub GET failed: HTTP ${ghGet.status}`, { detail: err.slice(0, 200) });
        }
      } catch (err) {
        return jsonError(502, `GitHub GET error: ${err.message}`);
      }

      // 2. Remove already-expired entries, then append the new link
      const now       = new Date();
      const expiresAt = new Date(now.getTime() + daysInt * 86400000).toISOString();
      links = links.filter(l => l && l.expires_at && new Date(l.expires_at) > now);
      const newLink = { url, expires_at: expiresAt };
      if (name && typeof name === 'string' && name.trim()) newLink.name = name.trim().slice(0, 80);
      if (description && typeof description === 'string' && description.trim()) newLink.description = description.trim().slice(0, 160);
      links.push(newLink);

      // 3. PUT updated file back to GitHub
      const putPayload = {
        message: `feat(links): add ${new URL(url).hostname}`,
        content: _b64EncodeUnicode(JSON.stringify(links, null, 2)),
        branch:  BRANCH,
      };
      if (sha) putPayload.sha = sha;

      try {
        const ghPut = await fetch(GH_API, {
          method:  'PUT',
          headers: GH_HEADERS,
          body:    JSON.stringify(putPayload),
        });
        if (!ghPut.ok) {
          const err = await ghPut.text();
          return jsonError(502, `GitHub PUT failed: HTTP ${ghPut.status}`, { detail: err.slice(0, 200) });
        }
      } catch (err) {
        return jsonError(502, `GitHub PUT error: ${err.message}`);
      }

      return new Response(
        JSON.stringify({ ok: true, message: 'Link added successfully.', expires_at: expiresAt }),
        { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } }
      );
    }

    // ── /api/update-links  POST — replace entire links.json via GitHub API ──────
    if (pathname === '/api/update-links') {
      if (request.method !== 'POST') {
        return jsonError(405, 'Method not allowed. Use POST for /api/update-links.');
      }

      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }

      const { links } = body || {};

      const auth = await _authOperator(request, env);
      if (auth.error) return auth.error;

      if (!Array.isArray(links)) {
        return jsonError(400, 'links must be an array.');
      }
      for (const link of links) {
        if (!link || typeof link.url !== 'string') {
          return jsonError(400, 'Each link must have a url string.');
        }
        try { new URL(link.url); } catch (_) {
          return jsonError(400, `Invalid URL in links: ${String(link.url).slice(0, 60)}`);
        }
      }
      if (!env || !env.GITHUB_TOKEN) {
        return jsonError(503, 'GitHub integration not configured. Set GITHUB_TOKEN in Worker environment.');
      }

      const REPO      = 'Vilfin-TV/MultiScreener';
      const FILE_PATH = 'links.json';
      const BRANCH    = 'main';
      const GH_API    = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;
      const GH_HEADERS = {
        'Authorization': `token ${env.GITHUB_TOKEN}`,
        'Accept':        'application/vnd.github.v3+json',
        'User-Agent':    'vilfintv-screener-proxy',
        'Content-Type':  'application/json',
      };

      // 1. GET current sha (required for the PUT)
      let sha = null;
      try {
        const ghGet = await fetch(`${GH_API}?ref=${BRANCH}`, { headers: GH_HEADERS });
        if (ghGet.ok) {
          sha = (await ghGet.json()).sha;
        } else if (ghGet.status !== 404) {
          const err = await ghGet.text();
          return jsonError(502, `GitHub GET failed: HTTP ${ghGet.status}`, { detail: err.slice(0, 200) });
        }
      } catch (err) {
        return jsonError(502, `GitHub GET error: ${err.message}`);
      }

      // 2. Strip to known fields only (preserve name + description), then PUT
      const cleanLinks = links.map(l => {
        const out = { url: l.url };
        if (l.expires_at) out.expires_at = l.expires_at;
        if (l.name && typeof l.name === 'string') out.name = l.name.slice(0, 80);
        if (l.description && typeof l.description === 'string') out.description = l.description.slice(0, 160);
        return out;
      });

      const putPayload = {
        message: 'chore(links): update via management console',
        content: _b64EncodeUnicode(JSON.stringify(cleanLinks, null, 2)),
        branch:  BRANCH,
      };
      if (sha) putPayload.sha = sha;

      try {
        const ghPut = await fetch(GH_API, {
          method:  'PUT',
          headers: GH_HEADERS,
          body:    JSON.stringify(putPayload),
        });
        if (!ghPut.ok) {
          const err = await ghPut.text();
          return jsonError(502, `GitHub PUT failed: HTTP ${ghPut.status}`, { detail: err.slice(0, 200) });
        }
      } catch (err) {
        return jsonError(502, `GitHub PUT error: ${err.message}`);
      }

      return new Response(
        JSON.stringify({ ok: true, message: 'Links updated successfully.' }),
        { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } }
      );
    }

    // ── /api/post-content  POST — append a custom content post to content.json ─
    if (pathname === '/api/post-content') {
      if (request.method !== 'POST') return jsonError(405, 'Use POST.');
      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON.'); }
      const auth = await requireAuth(request, env);
      if (auth.error) return auth.error;

      const { section, heading, story, photo, link_url, days, photo_pos, photo_zoom, youtube, youtube_play } = body || {};
      const VALID_SECTIONS = ['trending','global','india','stock','malayalam',
        'ml_trending','ml_movies','ml_music','ml_local','ml_science','ml_space',
        'ml_sports','ml_health','ml_food','ml_realestate','ml_career','ml_tech',
        /* Global Edition standalone sessions (news.html) */
        'sports','tech','space','science','fashion','movies','food','automobile','home','business',
        /* story.html pinned categories */
        'story_triller','story_travel','story_health','story_comedy',
        'story_kids','story_education','story_animation','story_ai',
        /* education.html notices */
        'academy_notice','academy_cbse','academy_jlpt'];
      if (!section || !VALID_SECTIONS.includes(section)) return jsonError(400, 'Invalid section.');
      if (!heading || typeof heading !== 'string' || !heading.trim()) return jsonError(400, 'heading is required.');
      if (!story   || typeof story   !== 'string' || !story.trim())   return jsonError(400, 'story is required.');
      if (_hasInlineBase64Image(story)) return jsonError(413, 'Embedded image detected. Add pictures with the image button (or paste/drag) so they upload as links — pasting an image inline bloats the post and it gets cut off.');
      if (story.trim().length > MAX_STORY) return jsonError(413, `Story is too large (${story.trim().length} chars; max ${MAX_STORY}). Use uploaded image URLs, not embedded images.`);
      // days is optional for automated posters (e.g. the Hermes agent): default
      // to 30 instead of failing the whole upload.
      let daysInt = parseInt(days);
      if (!daysInt || daysInt < 1 || daysInt > 365) daysInt = 30;
      if (!env.GITHUB_TOKEN) return jsonError(503, 'GitHub not configured.');

      // Uses the same _ghReadContent/_ghWriteContentSafe helpers as the agent
      // publish endpoint (this used to be an independent, older copy of the
      // read/write logic that never got the >1MB GitHub Contents API fallback
      // fix, and had no race-condition guard - both fixed by sharing the code).
      const now = new Date();
      const expiresAt = new Date(now.getTime() + daysInt * 86400000).toISOString();

      const newItemBase = { section, heading: heading.trim().slice(0,200), story: story.trim().slice(0,MAX_STORY), published_at: now.toISOString(), expires_at: expiresAt };
      if (photo && typeof photo === 'string' && photo.trim().startsWith('http')) newItemBase.photo = photo.trim().slice(0,500);
      if (link_url && typeof link_url === 'string' && link_url.trim().startsWith('http')) newItemBase.link_url = link_url.trim().slice(0,500);
      if (photo_pos && typeof photo_pos === 'string') newItemBase.photo_pos = photo_pos.trim().slice(0,20);
      if (photo_zoom && !isNaN(parseFloat(photo_zoom))) newItemBase.photo_zoom = Math.min(Math.max(parseFloat(photo_zoom), 1), 4);
      const ytVid = _ytId(youtube);
      if (ytVid) { newItemBase.youtube = ytVid; newItemBase.youtube_play = youtube_play !== false; }

      const computeFn = (freshItems) => {
        const items = freshItems.filter(i => i && (!i.expires_at || new Date(i.expires_at) > now));
        const resultId = String(Date.now());
        items.push({ ...newItemBase, id: resultId });
        return { items, message: `feat(content): publish ${section} post`, meta: { resultId } };
      };
      let written;
      try { written = await _ghWriteContentSafe(env, computeFn); }
      catch (e) { return jsonError(502, e.message); }
      return new Response(JSON.stringify({ ok: true, id: written.meta.resultId, expires_at: expiresAt }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
    }

    // ── /api/update-content  POST — replace entire content.json ─────────────
    if (pathname === '/api/update-content') {
      if (request.method !== 'POST') return jsonError(405, 'Use POST.');
      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON.'); }
      const auth = await requireAuth(request, env);
      if (auth.error) return auth.error;

      const { items } = body || {};
      if (!Array.isArray(items)) return jsonError(400, 'items must be an array.');
      if (!env.GITHUB_TOKEN) return jsonError(503, 'GitHub not configured.');

      const REPO = 'Vilfin-TV/MultiScreener', FILE_PATH = 'content.json', BRANCH = 'main';
      const GH_API = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;
      const GH_H = { 'Authorization': `token ${env.GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'vilfintv-proxy', 'Content-Type': 'application/json' };

      let sha = null;
      try {
        const r = await fetch(`${GH_API}?ref=${BRANCH}`, { headers: GH_H });
        if (r.ok) sha = (await r.json()).sha;
        else if (r.status !== 404) return jsonError(502, `GitHub GET failed: ${r.status}`);
      } catch (e) { return jsonError(502, `GitHub GET error: ${e.message}`); }

      const clean = items.map(i => { const o = { id: String(i.id||Date.now()), section: String(i.section||''), heading: String(i.heading||'').slice(0,200), story: _sanitizeStory(i.story), published_at: i.published_at||new Date().toISOString(), expires_at: i.expires_at||'' }; if (i.photo) o.photo = String(i.photo).slice(0,500); if (i.link_url) o.link_url = String(i.link_url).slice(0,500); if (i.photo_pos) o.photo_pos = String(i.photo_pos).slice(0,20); if (i.photo_zoom && !isNaN(parseFloat(i.photo_zoom))) o.photo_zoom = Math.min(Math.max(parseFloat(i.photo_zoom), 1), 4); const yt = _ytId(i.youtube); if (yt) { o.youtube = yt; o.youtube_play = i.youtube_play !== false; } return o; });
      const put = { message: 'chore(content): update via console', content: _b64EncodeUnicode(JSON.stringify(clean, null, 2)), branch: BRANCH };
      if (sha) put.sha = sha;
      try {
        const r = await fetch(GH_API, { method: 'PUT', headers: GH_H, body: JSON.stringify(put) });
        if (!r.ok) { const e = await r.text(); return jsonError(502, `GitHub PUT failed: ${r.status}`, { detail: e.slice(0,200) }); }
      } catch (e) { return jsonError(502, `GitHub PUT error: ${e.message}`); }
      return new Response(JSON.stringify({ ok: true, message: 'Content updated.' }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
    }

    // ── /api/update-config  POST — replace config.json (YouTube, News, Ticker) ─
    if (pathname === '/api/update-config') {
      if (request.method !== 'POST') return jsonError(405, 'Use POST.');
      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON.'); }
      const auth = await _authOperator(request, env);
      if (auth.error) return auth.error;

      const { config } = body || {};
      if (!config || typeof config !== 'object') return jsonError(400, 'config object required.');
      if (!env.GITHUB_TOKEN) return jsonError(503, 'GitHub not configured.');

      // ── YouTube channel overrides (map: no → patch) ─────────────────────────
      const rawYTOv = (config.youtube_overrides && typeof config.youtube_overrides === 'object' && !Array.isArray(config.youtube_overrides)) ? config.youtube_overrides : {};
      const cleanYTOv = {};
      for (const [no, patch] of Object.entries(rawYTOv)) {
        if (!patch || typeof patch !== 'object') continue;
        const p = {};
        if (patch.name !== undefined) p.name = String(patch.name).trim().slice(0, 80);
        if (patch.cid  !== undefined) p.cid  = String(patch.cid).trim().slice(0, 50);
        if (patch.v1   !== undefined) p.v1   = String(patch.v1).trim().slice(0, 20);
        if (patch.v2   !== undefined) p.v2   = String(patch.v2).trim().slice(0, 20);
        if (Object.keys(p).length) cleanYTOv[no] = p;
      }

      // ── Custom YouTube channels (additions) ───────────────────────────────
      const cleanYT = (Array.isArray(config.youtube_channels) ? config.youtube_channels : [])
        .map(ch => ({
          name:     String(ch.name     || '').trim().slice(0, 80),
          cid:      String(ch.cid      || '').trim().slice(0, 50),
          v1:       String(ch.v1       || '').trim().slice(0, 20),
          v2:       String(ch.v2       || '').trim().slice(0, 20),
          country:  String(ch.country  || '').trim().slice(0, 40),
          category: String(ch.category || '').trim().slice(0, 40),
          lang:     String(ch.lang     || '').trim().slice(0, 30),
        })).filter(ch => ch.name);

      // ── News source overrides (map: id → patch) ────────────────────────────
      const rawNsOv = (config.news_overrides && typeof config.news_overrides === 'object' && !Array.isArray(config.news_overrides)) ? config.news_overrides : {};
      const cleanNsOv = {};
      for (const [id, patch] of Object.entries(rawNsOv)) {
        if (!patch || typeof patch !== 'object') continue;
        const p = {};
        if (patch.label !== undefined) p.label = String(patch.label).trim().slice(0, 80);
        if (patch.url   !== undefined) p.url   = String(patch.url).trim().slice(0, 500);
        if (patch.color !== undefined) p.color = String(patch.color).trim().slice(0, 10);
        if (Object.keys(p).length) cleanNsOv[id] = p;
      }

      // ── Custom news channels (additions) ──────────────────────────────────
      const cleanNews = (Array.isArray(config.news_channels) ? config.news_channels : [])
        .map(ch => ({
          id:    String(ch.id    || '').trim().slice(0, 30),
          flag:  String(ch.flag  || '').trim().slice(0, 10),
          label: String(ch.label || '').trim().slice(0, 80),
          lang:  String(ch.lang  || '').trim().slice(0, 30),
          group: String(ch.group || '').trim().slice(0, 60),
          color: String(ch.color || '#888888').trim().slice(0, 10),
          url:   String(ch.url   || '').trim().slice(0, 500),
        })).filter(ch => ch.label && ch.url);

      // ── Ticker symbols (full replacement lists) ────────────────────────────
      const cleanTicker = (Array.isArray(config.ticker_symbols) ? config.ticker_symbols : [])
        .map(s => ({ proName: String(s.proName || '').trim().slice(0, 50), title: String(s.title || '').trim().slice(0, 40) }))
        .filter(s => s.proName);
      const cleanTickerMobile = (Array.isArray(config.ticker_symbols_mobile) ? config.ticker_symbols_mobile : [])
        .map(s => ({ proName: String(s.proName || '').trim().slice(0, 50), title: String(s.title || '').trim().slice(0, 40) }))
        .filter(s => s.proName);

      // ── Markets watchlist groups ───────────────────────────────────────────
      const cleanMkts = (Array.isArray(config.markets_groups) ? config.markets_groups : [])
        .map(g => ({
          name:    String(g.name || '').trim().slice(0, 60),
          symbols: (Array.isArray(g.symbols) ? g.symbols : [])
            .map(s => ({
              name:        String(s.name        || '').trim().toUpperCase().slice(0, 60),
              displayName: String(s.displayName || '').trim().slice(0, 60),
            }))
            .filter(s => s.name),
        }))
        .filter(g => g.name);

      // ── Academy video playlists (Hiragana / Katakana / Kanji) ──────────────
      const cleanAcademy = (arr) => (Array.isArray(arr) ? arr : [])
        .map(v => {
          const o = {
            id:    String((v && v.id)    || '').trim().slice(0, 40),
            title: String((v && v.title) || '').trim().slice(0, 120),
          };
          if (v && v.playlist) o.playlist = String(v.playlist).trim().slice(0, 60);
          return o;
        })
        .filter(v => v.id || v.playlist);

      // ── NFO offerings (New Fund Offerings board: US / Japan / India) ───────
      const cleanNfo = (Array.isArray(config.nfo_offerings) ? config.nfo_offerings : [])
        .map(o => ({
          name:       String((o && o.name)       || '').trim().slice(0, 140),
          country:    String((o && o.country)    || '').trim().toLowerCase().slice(0, 16),
          fund_house: String((o && o.fund_house) || '').trim().slice(0, 80),
          type:       String((o && o.type)       || '').trim().slice(0, 60),
          open_date:  String((o && o.open_date)  || '').trim().slice(0, 24),
          close_date: String((o && o.close_date) || '').trim().slice(0, 24),
          url:        String((o && o.url)        || '').trim().slice(0, 300),
        }))
        .filter(o => o.name && o.country);

      const cleanConfig = {
        youtube_overrides:     cleanYTOv,
        youtube_channels:      cleanYT,
        news_overrides:        cleanNsOv,
        news_channels:         cleanNews,
        ticker_symbols:        cleanTicker,
        ticker_symbols_mobile: cleanTickerMobile,
        markets_groups:        cleanMkts,
        academy_hiragana:      cleanAcademy(config.academy_hiragana),
        academy_katakana:      cleanAcademy(config.academy_katakana),
        academy_kanji:         cleanAcademy(config.academy_kanji),
        nfo_offerings:         cleanNfo,
      };

      const REPO = 'Vilfin-TV/MultiScreener', FILE_PATH = 'config.json', BRANCH = 'main';
      const GH_API = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;
      const GH_H = { 'Authorization': `token ${env.GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'vilfintv-proxy', 'Content-Type': 'application/json' };

      let sha = null;
      try {
        const r = await fetch(`${GH_API}?ref=${BRANCH}`, { headers: GH_H });
        if (r.ok) sha = (await r.json()).sha;
        else if (r.status !== 404) return jsonError(502, `GitHub GET failed: ${r.status}`);
      } catch (e) { return jsonError(502, `GitHub GET error: ${e.message}`); }

      const put = { message: 'chore(config): update via console', content: _b64EncodeUnicode(JSON.stringify(cleanConfig, null, 2)), branch: BRANCH };
      if (sha) put.sha = sha;
      try {
        const r = await fetch(GH_API, { method: 'PUT', headers: GH_H, body: JSON.stringify(put) });
        if (!r.ok) { const e = await r.text(); return jsonError(502, `GitHub PUT failed: ${r.status}`, { detail: e.slice(0,200) }); }
      } catch (e) { return jsonError(502, `GitHub PUT error: ${e.message}`); }
      return new Response(JSON.stringify({ ok: true, message: 'Config updated.' }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
    }

    // ── /api/upload-image  POST — store an image in R2, return a public URL ────
    // Accepts multipart/form-data (field "file") OR JSON { dataUrl, filename }.
    // Auth required. The returned URL is served back through this Worker at
    // /r2/<key> — no public bucket or custom domain needed.
    if (pathname === '/api/upload-image') {
      if (request.method !== 'POST') return jsonError(405, 'Use POST.');
      // Accept EITHER an admin/operator JWT session OR an approved agent API key
      // (with publish scope), so the Hermes automation can upload story images.
      const jwtAuth = await requireAuth(request, env);
      if (jwtAuth.error) {
        const ag = await _agentAuth(request, env);
        if (ag.error) return jwtAuth.error;
        if (ag.agent.status !== 'active') return jsonError(403, 'Agent not yet approved.');
        if (!(ag.agent.scope && ag.agent.scope.publish)) return jsonError(403, 'This agent key lacks publish scope.');
      }
      if (!env || !env.MEDIA) return jsonError(503, 'Image storage not configured. Bind an R2 bucket as MEDIA in the Worker.');

      const MAX_BYTES = 8 * 1024 * 1024; // 8 MB cap
      let bytes = null, contentType = '', origName = '';
      try {
        const ct = request.headers.get('Content-Type') || '';
        if (ct.includes('multipart/form-data')) {
          const form = await request.formData();
          const file = form.get('file');
          if (!file || typeof file === 'string') return jsonError(400, 'No file field in form data.');
          contentType = file.type || '';
          origName = file.name || '';
          bytes = new Uint8Array(await file.arrayBuffer());
        } else {
          const body = await request.json();
          const dataUrl = String(body.dataUrl || '');
          origName = String(body.filename || '');
          const m = dataUrl.match(/^data:([^;]+);base64,(.+)$/);
          if (!m) return jsonError(400, 'dataUrl must be a base64 data URI.');
          contentType = m[1];
          const bin = atob(m[2]);
          bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
        }
      } catch (e) {
        return jsonError(400, `Could not read image: ${e.message}`);
      }

      if (!bytes || !bytes.length) return jsonError(400, 'Empty image.');
      if (bytes.length > MAX_BYTES) return jsonError(413, 'Image too large (max 8 MB).');
      if (!/^image\/(jpeg|png|gif|webp|avif|svg\+xml)$/i.test(contentType)) {
        return jsonError(415, 'Unsupported image type. Use JPEG, PNG, GIF, WebP, AVIF or SVG.');
      }

      const extMap = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/gif': 'gif', 'image/webp': 'webp', 'image/avif': 'avif', 'image/svg+xml': 'svg' };
      let ext = extMap[contentType.toLowerCase()] || '';
      if (!ext && origName.includes('.')) ext = origName.split('.').pop().toLowerCase().slice(0, 5);
      const rand = Math.random().toString(36).slice(2, 10);
      const ym = new Date().toISOString().slice(0, 7); // YYYY-MM
      const key = `media/${ym}/${Date.now()}-${rand}${ext ? '.' + ext : ''}`;

      try {
        await env.MEDIA.put(key, bytes, { httpMetadata: { contentType } });
      } catch (e) {
        return jsonError(502, `R2 upload failed: ${e.message}`);
      }

      const url = `${new URL(request.url).origin}/r2/${key}`;
      return new Response(JSON.stringify({ ok: true, key, url }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      });
    }

    // ── /api/delete-image  POST — remove an object from R2 ────────────────────
    // Accepts JSON { key } or { url } (any /r2/<key> URL served by this Worker).
    if (pathname === '/api/delete-image') {
      if (request.method !== 'POST') return jsonError(405, 'Use POST.');
      const auth = await requireAuth(request, env);
      if (auth.error) return auth.error;
      if (!env || !env.MEDIA) return jsonError(503, 'Image storage not configured.');

      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON.'); }
      let key = String(body.key || '').trim();
      if (!key && body.url) {
        const u = String(body.url);
        const i = u.indexOf('/r2/');
        if (i !== -1) { try { key = decodeURIComponent(u.slice(i + 4)); } catch (_) { key = u.slice(i + 4); } }
      }
      if (!key || !key.startsWith('media/')) return jsonError(400, 'Invalid or missing R2 key.');

      try {
        await env.MEDIA.delete(key);
      } catch (e) {
        return jsonError(502, `R2 delete failed: ${e.message}`);
      }
      return new Response(JSON.stringify({ ok: true, key }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      });
    }

    // ── /api/subscribers  GET — list email subscribers (admin only) ─────────
    if (pathname === '/api/subscribers' && request.method === 'GET') {
      const auth = await requireAuth(request, env);
      if (auth.error) return auth.error;
      if ((auth.payload || {}).role !== 'admin') return jsonError(403, 'Admin only.');
      const subUrl = env.SUBSCRIBER_WORKER_URL;
      const subSecret = env.SUBSCRIBER_WORKER_SECRET;
      if (!subUrl || !subSecret) return jsonError(503, 'Subscriber worker not configured (set SUBSCRIBER_WORKER_URL and SUBSCRIBER_WORKER_SECRET secrets).');
      try {
        const res = await fetch(`${subUrl}?action=list`, { headers: { 'Authorization': `Bearer ${subSecret}` } });
        const data = await res.json();
        return new Response(JSON.stringify({ ok: true, subscribers: Array.isArray(data) ? data : [] }), {
          status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
        });
      } catch (e) {
        return jsonError(502, `Subscriber fetch failed: ${e.message}`);
      }
    }

    // ── Only allow GET for all other routes ──────────────────────────────────
    if (request.method !== 'GET') {
      return jsonError(405, 'Method not allowed. Use GET.');
    }

    // ── /r2/<key>  GET — serve an image stored in R2 (public, cached) ─────────
    // Supports HTTP Range requests (206 Partial Content) - some link-preview
    // crawlers and CDNs fetch just an image's header bytes first to validate
    // format/dimensions before committing to a full download, and treat a
    // plain 200-with-full-body response to a Range request as unexpected.
    if (pathname.startsWith('/r2/')) {
      if (!env || (!env.MEDIA && !env.STORY)) return jsonError(503, 'Image storage not configured.');
      let key;
      try { key = decodeURIComponent(pathname.slice(4)); } catch (_) { key = pathname.slice(4); }
      if (!key || !key.startsWith('media/')) return jsonError(400, 'Invalid image key.');
      try {
        let r2Range;
        const rangeHeader = request.headers.get('Range');
        if (rangeHeader) {
          const m = /^bytes=(\d+)-(\d*)$/.exec(rangeHeader.trim());
          if (m) {
            const offset = parseInt(m[1], 10);
            r2Range = m[2] ? { offset, length: parseInt(m[2], 10) - offset + 1 } : { offset };
          }
        }
        // Serve from the primary media bucket, then fall back to the story bucket.
        let obj = env.MEDIA ? await env.MEDIA.get(key, r2Range ? { range: r2Range } : undefined) : null;
        if (!obj && env.STORY) obj = await env.STORY.get(key, r2Range ? { range: r2Range } : undefined);
        if (!obj) return jsonError(404, 'Image not found.');
        const headers = new Headers(CORS);
        headers.set('Content-Type', (obj.httpMetadata && obj.httpMetadata.contentType) || 'application/octet-stream');
        headers.set('Cache-Control', 'public, max-age=31536000, immutable');
        headers.set('Accept-Ranges', 'bytes');
        if (obj.httpEtag) headers.set('ETag', obj.httpEtag);
        if (r2Range && obj.range) {
          const total = obj.size;
          const start = obj.range.offset || 0;
          const len = obj.range.length !== undefined ? obj.range.length : (total - start);
          headers.set('Content-Range', `bytes ${start}-${start + len - 1}/${total}`);
          headers.set('Content-Length', String(len));
          return new Response(obj.body, { status: 206, headers });
        }
        return new Response(obj.body, { status: 200, headers });
      } catch (e) {
        return jsonError(502, `R2 read failed: ${e.message}`);
      }
    }

    // ── /img?url=<encoded>  GET — CORS image proxy for the share-card canvas ──
    // Lets the client composite any story photo onto a <canvas> without tainting
    // it. Used only internally by share-card generation; never shown to users.
    if (pathname === '/img') {
      const target = searchParams.get('url') || '';
      if (!/^https?:\/\//i.test(target)) return jsonError(400, 'Invalid url.');
      try {
        const up = await fetch(target, {
          headers: { 'User-Agent': 'Mozilla/5.0 (VilfinTV share-card)', 'Accept': 'image/*,*/*' },
          cf: { cacheTtl: 86400, cacheEverything: true },
        });
        if (!up.ok) return jsonError(502, 'Upstream image failed.');
        const ct = up.headers.get('Content-Type') || 'image/jpeg';
        if (!/^image\//i.test(ct)) return jsonError(415, 'Not an image.');
        const headers = new Headers(CORS);
        headers.set('Content-Type', ct);
        headers.set('Cache-Control', 'public, max-age=86400');
        return new Response(up.body, { status: 200, headers });
      } catch (e) {
        return jsonError(502, 'Image proxy error.');
      }
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
/* ── UTF-8 Base64 Helpers ── */
function _b64EncodeUnicode(str) {
  return btoa(unescape(encodeURIComponent(str)));
}
function _b64DecodeUnicode(str) {
  return decodeURIComponent(escape(atob(str)));
}

/* ── Story body limits ──────────────────────────────────────────────────────
   Stories are long-form (10–20 "pages") and may carry many images. Images must
   be stored as uploaded R2/HTTP URLs (~80 chars each), NOT inline base64 (one
   pasted screenshot is ~400–600KB). With URL-based images even a very long
   multi-page feature stays well under this cap. */
const MAX_STORY = 2000000; // 2,000,000 chars (~2MB) — generous headroom for long features

// Does the story contain a *genuine* inline base64 <img> — the thing that bloats
// and truncates posts? We require an actual `;base64,` payload of meaningful
// length, with a lazy [^>]* that cannot bridge unrelated text. This avoids false
// positives on long prose (e.g. Malayalam features) that merely contain the
// words "img"/"image"/"data" near each other but no real embedded picture.
function _hasInlineBase64Image(s) {
  return /<img\b[^>]*?\bsrc\s*=\s*["']?\s*data:image\/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=\s]{200,}/i.test(String(s || ''));
}

// Extract an 11-char YouTube video id from any common URL form (watch?v=,
// youtu.be/, embed/, shorts/, live/) or a bare id. Returns '' if none.
function _ytId(url) {
  if (!url) return '';
  const s = String(url).trim();
  if (/^[A-Za-z0-9_-]{11}$/.test(s)) return s;
  const m = s.match(/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : '';
}

// Clean a story for safe storage: strip inline base64 images (incl. a trailing
// unterminated/truncated one) and cap at MAX_STORY. Used on the update path so a
// pre-existing broken post can't lock the admin out of editing other posts.
function _sanitizeStory(s, max = MAX_STORY) {
  s = String(s || '');
  s = s.replace(/<img\b[^>]*?\bsrc\s*=\s*["']?\s*data:image\/[a-z0-9.+-]+;base64,[^>]*>/gi, '');   // complete base64 tags
  s = s.replace(/<img\b[^>]*?\bsrc\s*=\s*["']?\s*data:image\/[a-z0-9.+-]+;base64,[\s\S]*$/i, '');  // trailing truncated base64 tag
  if (s.length > max) s = s.slice(0, max);
  return s;
}

/* ── JWT (HS256) using Web Crypto API ── */
function _b64urlEncode(data) {
  const b64 = (typeof data === 'string')
    ? btoa(unescape(encodeURIComponent(data)))
    : btoa(String.fromCharCode(...new Uint8Array(data)));
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function _b64urlDecodeStr(str) {
  const b64 = str.replace(/-/g, '+').replace(/_/g, '/');
  return decodeURIComponent(escape(atob(b64.padEnd(b64.length + (4 - b64.length % 4) % 4, '='))));
}
function _b64urlDecodeBytes(str) {
  const b64 = str.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(b64.padEnd(b64.length + (4 - b64.length % 4) % 4, '='));
  return Uint8Array.from(binary, c => c.charCodeAt(0));
}
async function _hmacKey(secret, usage) {
  return crypto.subtle.importKey('raw', new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, [usage]);
}
/* ── IPTV credential management (login id/password + settings) for the
      private IPTV console. Stored in KV (binding IPTV_KV) — the SAME namespace
      bound to the page-iptv worker as IPTV_PLAYLIST_KV. ── */
const IPTV_DEFAULT_SETTINGS = {
  sessionHours: 8,
  defaultProvider: 'free',
  providers: {
    jio:    { enabled: true, url: "", epg: "" },
    airtel: { enabled: true, url: "", epg: "" },
    free:   { enabled: true, url: "https://iptv-org.github.io/iptv/index.m3u", epg: "https://epg.pw/xmltv/epg_IN.xml" },
    pro:    { enabled: true, url: "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", epg: "" },
    custom: { enabled: true, url: "", epg: "" },
  },
};
function _iptvJson(obj) {
  return new Response(JSON.stringify(obj), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
}
function _iptvHexFromBytes(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i++) s += bytes[i].toString(16).padStart(2, '0');
  return s;
}
async function _iptvHashPassword(password, saltHex, iterations) {
  const iter = iterations || 100000;
  const salt = saltHex
    ? Uint8Array.from(saltHex.match(/.{1,2}/g).map(function (b) { return parseInt(b, 16); }))
    : crypto.getRandomValues(new Uint8Array(16));
  const km = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', salt: salt, iterations: iter, hash: 'SHA-256' }, km, 256);
  return { salt: _iptvHexFromBytes(salt), hash: _iptvHexFromBytes(new Uint8Array(bits)), iterations: iter };
}

/* ── Console RBAC + status report helpers ── */
function _rbacJson(obj){ return new Response(JSON.stringify(obj), { status:200, headers:{ ...CORS, 'Content-Type':'application/json' } }); }
async function _opAll(env){
  if (!env.IPTV_KV) return {};
  try { const r = await env.IPTV_KV.get('console_operators'); return r ? JSON.parse(r) : {}; } catch(e){ return {}; }
}
async function _opGet(env, username){ const all = await _opAll(env); return all[username] || null; }

/* ── Admin 2FA (TOTP, RFC 6238 — Google Authenticator compatible) ───────────── */
const _B32A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
function _b32encode(bytes){ let bits=0,val=0,out=''; for(const b of bytes){ val=(val<<8)|b; bits+=8; while(bits>=5){ out+=_B32A[(val>>>(bits-5))&31]; bits-=5; } } if(bits>0) out+=_B32A[(val<<(5-bits))&31]; return out; }
function _b32decode(s){ s=String(s||'').replace(/=+$/,'').toUpperCase().replace(/\s/g,''); let bits=0,val=0,out=[]; for(const c of s){ const i=_B32A.indexOf(c); if(i<0) continue; val=(val<<5)|i; bits+=5; if(bits>=8){ out.push((val>>>(bits-8))&0xff); bits-=8; } } return new Uint8Array(out); }
async function _totp(secretB32, counter){
  const key=_b32decode(secretB32); const buf=new ArrayBuffer(8); const dv=new DataView(buf);
  dv.setUint32(0, Math.floor(counter/0x100000000)); dv.setUint32(4, counter>>>0);
  const ck=await crypto.subtle.importKey('raw', key, {name:'HMAC',hash:'SHA-1'}, false, ['sign']);
  const sig=new Uint8Array(await crypto.subtle.sign('HMAC', ck, buf));
  const off=sig[sig.length-1]&0xf;
  const code=((sig[off]&0x7f)<<24)|((sig[off+1]&0xff)<<16)|((sig[off+2]&0xff)<<8)|(sig[off+3]&0xff);
  return String(code%1000000).padStart(6,'0');
}
async function _totpVerify(secretB32, token, window){
  token=String(token||'').replace(/\s/g,''); if(!/^\d{6}$/.test(token)) return false;
  const step=Math.floor(Date.now()/1000/30), w=(window==null?1:window);
  for(let i=-w;i<=w;i++){ if(await _totp(secretB32, step+i)===token) return true; }
  return false;
}
async function _2faGet(env){
  if(!env.IPTV_KV) return { enabled:false };
  try{ const r=await env.IPTV_KV.get('admin_2fa'); const o=r?JSON.parse(r):{}; return { enabled:!!o.enabled, secret:o.secret||'', pending:o.pending||'' }; }
  catch(e){ return { enabled:false }; }
}
async function _2faPut(env, o){ await env.IPTV_KV.put('admin_2fa', JSON.stringify(o)); }

/* ── Console login sessions (device / IP tracking + revocation) ─────────────── */
async function _sessAll(env){
  if(!env.IPTV_KV) return {};
  try{ const r=await env.IPTV_KV.get('console_sessions'); return r?JSON.parse(r):{}; }catch(e){ return {}; }
}
async function _sessPut(env, all){ await env.IPTV_KV.put('console_sessions', JSON.stringify(all)); }
// Record a freshly-issued session (called from /api/login). jti links it to the JWT.
async function _sessRecord(env, request, jti, username, role, exp, device){
  if(!env.IPTV_KV) return;
  try{
    const all = await _sessAll(env);
    const now = Date.now();
    for(const k of Object.keys(all)){ if(all[k] && all[k].exp && all[k].exp*1000 < now) delete all[k]; } // prune expired
    const cf = request.cf || {};
    all[jti] = { jti, username, role,
      ip: request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For') || '',
      ua: (request.headers.get('User-Agent') || '').slice(0,300),
      device: (device || '').toString().slice(0,80),
      loc: [cf.city, cf.region, cf.country].filter(Boolean).join(', '),
      org: (cf.asOrganization || '').toString().slice(0,80),
      createdAt: now, lastSeen: now, exp };
    await _sessPut(env, all);
  }catch(e){}
}

/* ── Agent API keys (Hermes / automation) ──────────────────────────────────────
   Stored in IPTV_KV under 'agent_keys' as { [id]: {…} }. Each key is scoped to
   content publish/edit only — never admin. A key is created in 'pending' state;
   the admin must Approve it once before it can publish (one-time activation).
   The plaintext secret is shown to the admin exactly once at creation; only a
   PBKDF2 hash is stored. The API key string handed to the agent is:
        vtv.<id>.<secret>
   where <id> identifies the record and <secret> is verified against the hash. */
async function _agAll(env){
  if (!env.IPTV_KV) return {};
  try { const r = await env.IPTV_KV.get('agent_keys'); return r ? JSON.parse(r) : {}; } catch(e){ return {}; }
}
async function _agPut(env, all){ await env.IPTV_KV.put('agent_keys', JSON.stringify(all)); }

/* ── LLM / LiteLLM provider config (admin-managed; agent reads with 'llm' scope) */
async function _llmAll(env){
  if (!env.IPTV_KV) return { providers: [] };
  try { const r = await env.IPTV_KV.get('llm_config'); const o = r ? JSON.parse(r) : {}; return { providers: Array.isArray(o.providers) ? o.providers : [] }; }
  catch(e){ return { providers: [] }; }
}
async function _llmPut(env, cfg){ await env.IPTV_KV.put('llm_config', JSON.stringify(cfg)); }
// Sentinel model ids for the OpenRouter dropdown (expanded by the agent).
const OR_FREE_ROTATE = 'openrouter/free-rotate';
// Fetch + simplify the public OpenRouter catalogue (cached 1h at the edge).
async function _orModels(env){
  try {
    const r = await fetch('https://openrouter.ai/api/v1/models', {
      headers: { 'User-Agent': 'vilfintv-console', 'Accept': 'application/json' },
      cf: { cacheTtl: 3600, cacheEverything: true }, signal: AbortSignal.timeout(12000) });
    if (!r.ok) return [];
    const data = await r.json();
    return (data.data || []).map(m => {
      const pp = m.pricing || {};
      const free = (parseFloat(pp.prompt || '0') === 0 && parseFloat(pp.completion || '0') === 0) || /:free$/.test(m.id || '');
      const arch = m.architecture || {};
      const outs = Array.isArray(arch.output_modalities) ? arch.output_modalities
                 : (typeof arch.modality === 'string' ? [arch.modality.split('->').pop()] : ['text']);
      const image = outs.indexOf('image') !== -1;   // image-generation model (e.g. "Nano Banana")
      return { id: m.id, name: m.name || m.id, provider: String(m.id || '').split('/')[0], free: free, image: image };
    }).filter(m => m.id);
  } catch(e){ return []; }
}
// Admin-facing view of a provider — the secret key is masked.
function _llmPublic(p){
  const key = p.apiKey || '';
  return { id:p.id, name:p.name, provider:p.provider, model:p.model, apiBase:p.apiBase||'',
    isDefault:!!p.isDefault, hasKey:!!key, keyMasked: key ? ('••••••' + key.slice(-4)) : '', createdAt:p.createdAt };
}

/* ── Image-repository sources (Pexels / Pixabay / Unsplash …) ──────────────────
   Admin-managed; the agent reads them with the 'images' scope to fetch stock
   photos for stories. */
async function _imgAll(env){
  if (!env.IPTV_KV) return { sources: [] };
  try { const r = await env.IPTV_KV.get('img_sources'); const o = r ? JSON.parse(r) : {}; return { sources: Array.isArray(o.sources) ? o.sources : [] }; }
  catch(e){ return { sources: [] }; }
}
async function _imgPut(env, cfg){ await env.IPTV_KV.put('img_sources', JSON.stringify(cfg)); }
function _imgPublic(s){
  const key = s.apiKey || '';
  return { id:s.id, name:s.name, provider:s.provider, isDefault:!!s.isDefault,
    hasKey:!!key, keyMasked: key ? ('••••••' + key.slice(-4)) : '', createdAt:s.createdAt };
}
// Public view of a key record (no secret material)
function _agPublic(k){
  return { id:k.id, label:k.label, status:k.status, scope:k.scope||{publish:true,edit:false},
    expiresAt:k.expiresAt||null, createdAt:k.createdAt, requestedAt:k.requestedAt||null,
    lastUsedAt:k.lastUsedAt||null, disabled:!!k.disabled };
}
function _agExpired(k){ return !!(k.expiresAt && Date.now() > new Date(k.expiresAt).getTime()); }
// Authenticate an agent request by its Bearer API key. Returns { agent, all }
// on success, or { error } (a Response) on failure. Records lastUsedAt lazily.
async function _agentAuth(request, env){
  if (!env.IPTV_KV) return { error: jsonError(503, 'Agent store not configured (IPTV_KV).') };
  if (!env.JWT_SECRET) return { error: jsonError(503, 'Auth not configured.') };
  const auth = request.headers.get('Authorization') || '';
  const raw = auth.startsWith('Bearer ') ? auth.slice(7).trim() : '';
  const parts = raw.split('.');
  if (parts.length !== 3 || parts[0] !== 'vtv') return { error: jsonError(401, 'Missing or malformed agent API key.') };
  const id = parts[1], secret = parts[2];
  const all = await _agAll(env);
  const k = all[id];
  if (!k) return { error: jsonError(401, 'Unknown agent API key.') };
  if (k.disabled) return { error: jsonError(403, 'This agent key is disabled.') };
  if (_agExpired(k)) return { error: jsonError(403, 'This agent key has expired. Ask the administrator to issue a new one.') };
  const h = await _iptvHashPassword(secret, k.salt, k.iterations);
  if (h.hash !== k.secretHash) return { error: jsonError(401, 'Invalid agent API key.') };
  return { agent: k, all };
}

// Gate for operator-level endpoints (links, home page config, IPTV): accepts an
// admin/operator JWT OR an approved agent key with the "operator" scope. Admin-only
// endpoints keep their own requireAuth + role check, so agents can never reach them.
async function _authOperator(request, env){
  const j = await requireAuth(request, env);
  if (!j.error) return { payload: j.payload, isAdmin: (j.payload||{}).role === 'admin' };
  const a = await _agentAuth(request, env);
  if (!a.error){
    if (a.agent.status !== 'active') return { error: jsonError(403, 'Agent not yet approved.') };
    if (!(a.agent.scope && a.agent.scope.operator)) return { error: jsonError(403, 'This agent key lacks operator access (links, home page, IPTV).') };
    return { agent: a.agent, isAdmin: false };
  }
  return { error: j.error };
}

/* ── Shared content.json GitHub read / write ───────────────────────────────────
   Used by /api/post-content and the agent publish endpoint so both follow the
   exact same commit path. */
const _CONTENT_REPO = 'Vilfin-TV/MultiScreener', _CONTENT_FILE = 'content.json', _CONTENT_BRANCH = 'main';
function _ghHeaders(env){ return { 'Authorization': `token ${env.GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'vilfintv-proxy', 'Content-Type': 'application/json' }; }
/* ── Git Data API read: HEAD ref → commit → tree → blob ────────────────────
   Uses the Git Data API (not the Contents API) for every step.
   Each object is sha-addressed and immutable, so no caching layer can serve
   stale bytes. The only potentially-stale call is GET refs/heads/main, but
   that's OK: if we read a slightly old HEAD, our PATCH in _ghWriteContentGit
   will fail with 422 (non-fast-forward) and we retry cleanly from scratch.
   Returns { headCommitSha, treeSha, items }. */
async function _ghReadContentGit(env){
  const h = _ghHeaders(env), base = `https://api.github.com/repos/${_CONTENT_REPO}`;
  const cf = { cacheTtl: -1, cacheEverything: false };

  const refR = await fetch(`${base}/git/refs/heads/${_CONTENT_BRANCH}`, { headers:h, cf });
  if (!refR.ok) throw new Error(`git refs read failed: ${refR.status}`);
  const headCommitSha = (await refR.json()).object.sha;

  const commitR = await fetch(`${base}/git/commits/${headCommitSha}`, { headers:h, cf });
  if (!commitR.ok) throw new Error(`git commit read failed: ${commitR.status}`);
  const treeSha = (await commitR.json()).tree.sha;

  const treeR = await fetch(`${base}/git/trees/${treeSha}`, { headers:h, cf });
  if (!treeR.ok) throw new Error(`git tree read failed: ${treeR.status}`);
  const entry = (await treeR.json()).tree.find(e => e.path === _CONTENT_FILE && e.type === 'blob');
  if (!entry) return { headCommitSha, treeSha, items:[] };

  const blobR = await fetch(`${base}/git/blobs/${entry.sha}`, { headers:h, cf });
  if (!blobR.ok) throw new Error(`git blob read failed: ${blobR.status}`);
  const bd = await blobR.json();
  let items; try { items = JSON.parse(_b64DecodeUnicode((bd.content||'').replace(/\n/g,''))); } catch(e){ items=[]; }
  if (!Array.isArray(items)) items = [];
  return { headCommitSha, treeSha, items };
}

/* ── Git Data API write: blob → tree → commit → ref PATCH (atomic CAS) ────
   The PATCH refs step with force:false succeeds only if our new commit is a
   fast-forward from the current HEAD (i.e. our headCommitSha is still HEAD).
   If another writer pushed in between, PATCH returns 422 → caller retries.
   This is a true compare-and-swap: concurrent writers can never silently
   overwrite each other. */
async function _ghWriteContentGit(env, items, headCommitSha, treeSha, message){
  const h = _ghHeaders(env), base = `https://api.github.com/repos/${_CONTENT_REPO}`;

  const blobR = await fetch(`${base}/git/blobs`, { method:'POST', headers:h,
    body: JSON.stringify({ content: _b64EncodeUnicode(JSON.stringify(items, null, 2)), encoding:'base64' }) });
  if (!blobR.ok){ const e=await blobR.text(); throw new Error(`git create blob failed: ${blobR.status} ${e.slice(0,160)}`); }
  const newBlobSha = (await blobR.json()).sha;

  const newTreeR = await fetch(`${base}/git/trees`, { method:'POST', headers:h,
    body: JSON.stringify({ base_tree: treeSha,
      tree: [{ path: _CONTENT_FILE, mode:'100644', type:'blob', sha: newBlobSha }] }) });
  if (!newTreeR.ok){ const e=await newTreeR.text(); throw new Error(`git create tree failed: ${newTreeR.status} ${e.slice(0,160)}`); }
  const newTreeSha = (await newTreeR.json()).sha;

  const newCommitR = await fetch(`${base}/git/commits`, { method:'POST', headers:h,
    body: JSON.stringify({ message, tree: newTreeSha, parents: [headCommitSha] }) });
  if (!newCommitR.ok){ const e=await newCommitR.text(); throw new Error(`git create commit failed: ${newCommitR.status} ${e.slice(0,160)}`); }
  const newCommitSha = (await newCommitR.json()).sha;

  // Non-force PATCH: fails with 422 if HEAD moved since our read → retry loop catches it
  const refR = await fetch(`${base}/git/refs/heads/${_CONTENT_BRANCH}`, { method:'PATCH', headers:h,
    body: JSON.stringify({ sha: newCommitSha, force: false }) });
  if (!refR.ok){ const e=await refR.text(); throw new Error(`git update ref failed: ${refR.status} ${e.slice(0,160)}`); }
  return true;
}

/* ── Race-safe content.json read/compute/write ──────────────────────────────
   Uses the Git Data API (blob → tree → commit → ref PATCH) instead of the
   Contents API PUT. The ref PATCH with force:false is a true atomic CAS:
   it succeeds only if our new commit fast-forwards from the current HEAD.
   If any concurrent writer pushed between our read and our PATCH, we get a
   422 and retry the full read-compute-write cycle from scratch, so we never
   silently overwrite another writer's changes.

   computeFn(freshItems) -> { items, message, meta } | _CONTENT_NOT_FOUND
     (_CONTENT_NOT_FOUND = genuine business-logic miss, e.g. delete target
      not found — never retried.) */
const _CONTENT_NOT_FOUND = Symbol('content_not_found');
function _sleep(ms){ return new Promise(resolve => setTimeout(resolve, ms)); }
async function _ghWriteContentSafe(env, computeFn, maxAttempts = 5){
  let lastErr;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    let read;
    try { read = await _ghReadContentGit(env); }
    catch (e) { lastErr = e; await _sleep(300 * attempt); continue; }

    const computed = computeFn(read.items);
    if (computed === _CONTENT_NOT_FOUND) return _CONTENT_NOT_FOUND;

    try {
      await _ghWriteContentGit(env, computed.items, read.headCommitSha, read.treeSha, computed.message);
    } catch (e) {
      lastErr = e;
      // 422 = HEAD moved (CAS conflict) → retry immediately with a short jitter
      // Other errors (network, GitHub 5xx) → back off before retry
      const isConflict = e.message && e.message.includes('422');
      await _sleep(isConflict ? 100 + attempt * 50 : 400 * attempt);
      continue;
    }

    return { items: computed.items, meta: computed.meta };
  }
  throw lastErr || new Error('_ghWriteContentSafe: exhausted retries');
}
// Generic JSON-file read/write in the same repo (used for lessons.json).
async function _ghReadJsonFile(env, file){
  const api = `https://api.github.com/repos/${_CONTENT_REPO}/contents/${file}`;
  // Same cache-busting as _ghReadContent - see the comment there.
  const r = await fetch(`${api}?ref=${_CONTENT_BRANCH}&_cb=${Date.now()}`, {
    headers: _ghHeaders(env), cf: { cacheTtl: -1, cacheEverything: false }
  });
  if (r.ok) {
    const d = await r.json();
    let data = {};
    try {
      // Same >1MB Contents-API fallback as _ghReadContent - this file is
      // tiny today but this prevents the identical 502 recurring here later.
      // Uses the Git Blobs API (immutable, sha-addressed), not download_url
      // (raw.githubusercontent.com), which has its own CDN cache that a
      // cache-busting query string doesn't reliably defeat - see the longer
      // comment in _ghReadContent for the confirmed incident.
      let text;
      if (d.content) text = _b64DecodeUnicode(d.content.replace(/\n/g,''));
      else if (d.sha) {
        const blobApi = `https://api.github.com/repos/${_CONTENT_REPO}/git/blobs/${d.sha}`;
        const blob = await fetch(blobApi, { headers: _ghHeaders(env), cf: { cacheTtl: -1, cacheEverything: false } });
        if (blob.ok) {
          const bd = await blob.json();
          text = _b64DecodeUnicode((bd.content || '').replace(/\n/g,''));
        }
      }
      if (text) data = JSON.parse(text);
    } catch(e){ data = {}; }
    return { sha: d.sha, data: (data && typeof data === 'object') ? data : {} };
  }
  if (r.status === 404) return { sha: null, data: {} };
  throw new Error(`GitHub GET ${file} failed: ${r.status}`);
}
async function _ghWriteJsonFile(env, file, data, sha, message){
  const api = `https://api.github.com/repos/${_CONTENT_REPO}/contents/${file}`;
  const put = { message, content: _b64EncodeUnicode(JSON.stringify(data, null, 2)), branch: _CONTENT_BRANCH };
  if (sha) put.sha = sha;
  const r = await fetch(api, { method:'PUT', headers:_ghHeaders(env), body: JSON.stringify(put) });
  if (!r.ok) { const e = await r.text(); throw new Error(`GitHub PUT ${file} failed: ${r.status} ${e.slice(0,160)}`); }
  return true;
}
// Academy lesson hubs that education.html appends from lessons.json
const LESSON_HUBS = ['finance','micro','macro','ai','programming','web','info','finlit','career','growth'];

const STATUS_PAGES = [
  'https://vilfintv.com/','https://vilfintv.com/iptv.html','https://vilfintv.com/news.html',
  'https://vilfintv.com/story.html','https://vilfintv.com/education.html','https://vilfintv.com/link-console.html',
  'https://vilfintv.com/content.json'
];
const GH_OWNER = 'Vilfin-TV', GH_REPO = 'MultiScreener';

async function _fetchJson(url, headers){
  try { const r = await fetch(url, { headers: headers||{} }); const t = await r.text();
    let j=null; try{ j=JSON.parse(t); }catch(e){}
    return { ok:r.ok, status:r.status, json:j, text:t }; } catch(e){ return { ok:false, status:0, error:String(e&&e.message||e) }; }
}

async function buildStatusReport(env){
  const out = { generatedAt:new Date().toISOString(), pages:[], github:null, cloudflare:null, summary:{} };

  // 1) Page uptime checks (with size, content-type, cache + cf-cache info)
  const pageChecks = await Promise.all(STATUS_PAGES.map(async function(u){
    const t0 = Date.now();
    try { const r = await fetch(u, { method:'GET', cf:{ cacheTtl:0 } });
      const buf = await r.arrayBuffer();
      return { url:u, status:r.status, ok:r.ok, ms: Date.now()-t0,
        bytes: buf.byteLength,
        type: (r.headers.get('content-type')||'').split(';')[0],
        server: r.headers.get('server')||'',
        cache: r.headers.get('cache-control')||'',
        cfCache: r.headers.get('cf-cache-status')||'',
        lastModified: r.headers.get('last-modified')||'' }; }
    catch(e){ return { url:u, status:0, ok:false, ms: Date.now()-t0, error:String(e&&e.message||e) }; }
  }));
  out.pages = pageChecks;

  // 2) GitHub: repo info, workflows, security alerts
  if (env.GITHUB_TOKEN){
    const H = { 'Authorization':'token '+env.GITHUB_TOKEN, 'Accept':'application/vnd.github+json', 'User-Agent':'vilfintv-status' };
    const base = 'https://api.github.com/repos/'+GH_OWNER+'/'+GH_REPO;
    const repo = await _fetchJson(base, H);
    const runs = await _fetchJson(base+'/actions/runs?per_page=12', H);
    const dependabot = await _fetchJson(base+'/dependabot/alerts?state=open&per_page=50', H);
    const codescan = await _fetchJson(base+'/code-scanning/alerts?state=open&per_page=50', H);
    const gh = { configured:true };
    if (repo.json){ gh.sizeKB = repo.json.size; gh.private = repo.json.private; gh.pushedAt = repo.json.pushed_at; gh.defaultBranch = repo.json.default_branch; }
    if (runs.json && runs.json.workflow_runs){
      gh.workflows = runs.json.workflow_runs.slice(0,12).map(function(w){ return { name:w.name, status:w.status, conclusion:w.conclusion, event:w.event, at:w.created_at, url:w.html_url }; });
      gh.failedWorkflows = gh.workflows.filter(function(w){ return w.conclusion && w.conclusion!=='success' && w.conclusion!=='skipped' && w.conclusion!=='neutral'; }).length;
    }
    gh.dependabotOpen = (dependabot.json && Array.isArray(dependabot.json)) ? dependabot.json.length : (dependabot.status===403?'no-access':'n/a');
    gh.codeScanningOpen = (codescan.json && Array.isArray(codescan.json)) ? codescan.json.length : (codescan.status===403||codescan.status===404?'not-enabled':'n/a');
    if (dependabot.json && Array.isArray(dependabot.json)){
      gh.dependabotBySeverity = dependabot.json.reduce(function(a,x){ var s=(x.security_advisory&&x.security_advisory.severity)||'unknown'; a[s]=(a[s]||0)+1; return a; }, {});
    }
    out.github = gh;
  } else { out.github = { configured:false, note:'GITHUB_TOKEN not set on the worker.' }; }

  // 3) Cloudflare: security, storage (space), workers, zones/SSL, web analytics
  if (env.CLOUDFLARE_API_TOKEN){
    const H = { 'Authorization':'Bearer '+env.CLOUDFLARE_API_TOKEN, 'Content-Type':'application/json' };
    const cf = { configured:true };
    const verify = await _fetchJson('https://api.cloudflare.com/client/v4/user/tokens/verify', H);
    cf.tokenValid = !!(verify.json && verify.json.success);
    if (verify.json && verify.json.result && verify.json.result.expires_on) cf.tokenExpires = verify.json.result.expires_on;
    let accountId = env.CLOUDFLARE_ACCOUNT_ID || '';
    if (!accountId){ const accts = await _fetchJson('https://api.cloudflare.com/client/v4/accounts', H);
      if (accts.json && accts.json.result && accts.json.result[0]){ accountId = accts.json.result[0].id; cf.accountName = accts.json.result[0].name; } }
    cf.accountId = accountId ? (accountId.slice(0,8)+'…') : null;

    if (accountId){
      const ab = 'https://api.cloudflare.com/client/v4/accounts/'+accountId;

      // KV namespaces + per-namespace key counts (storage footprint signal)
      const kv = await _fetchJson(ab+'/storage/kv/namespaces?per_page=100', H);
      if (kv.json && kv.json.result){
        cf.kv = [];
        for (const ns of kv.json.result){
          let keys = 'n/a';
          const kr = await _fetchJson(ab+'/storage/kv/namespaces/'+ns.id+'/keys?limit=1000', H);
          if (kr.json && Array.isArray(kr.json.result)) keys = kr.json.result.length + (kr.json.result_info && kr.json.result_info.cursor ? '+' : '');
          cf.kv.push({ title:ns.title, keys:keys });
        }
      } else if (kv.status===403){ cf.kv = 'no-access'; }

      // R2 buckets + size/object usage per bucket
      const r2 = await _fetchJson(ab+'/r2/buckets', H);
      if (r2.json && r2.json.result && r2.json.result.buckets){
        cf.r2 = [];
        for (const b of r2.json.result.buckets){
          const usage = await _fetchJson(ab+'/r2/buckets/'+encodeURIComponent(b.name)+'/usage', H);
          let sizeBytes=null, objects=null;
          if (usage.json && usage.json.result){ sizeBytes = usage.json.result.payloadSize!=null?usage.json.result.payloadSize:usage.json.result.metadataSize; objects = usage.json.result.objectCount; }
          cf.r2.push({ name:b.name, sizeBytes:sizeBytes, objects:objects });
        }
        cf.r2TotalBytes = cf.r2.reduce(function(a,x){ return a + (x.sizeBytes||0); }, 0);
      } else if (r2.status===403){ cf.r2 = 'no-access'; }

      // Workers scripts deployed
      const ws = await _fetchJson(ab+'/workers/scripts', H);
      if (ws.json && Array.isArray(ws.json.result)) cf.workers = ws.json.result.map(function(s){ return s.id; });
      else if (ws.status===403) cf.workers = 'no-access';
    }

    // Zones: SSL mode, status, security level, plan, + Web Analytics availability
    const zones = await _fetchJson('https://api.cloudflare.com/client/v4/zones?per_page=50', H);
    if (zones.json && Array.isArray(zones.json.result) && zones.json.result.length){
      cf.zones = [];
      for (const z of zones.json.result){
        const zb = 'https://api.cloudflare.com/client/v4/zones/'+z.id;
        const ssl = await _fetchJson(zb+'/settings/ssl', H);
        const sec = await _fetchJson(zb+'/settings/security_level', H);
        cf.zones.push({ name:z.name, status:z.status, plan:(z.plan&&z.plan.name)||'',
          ssl:(ssl.json&&ssl.json.result&&ssl.json.result.value)||'n/a',
          securityLevel:(sec.json&&sec.json.result&&sec.json.result.value)||'n/a' });
      }
    } else if (zones.status===403){ cf.zones = 'no-access (add Zone:Read to the token to show SSL/DNS/analytics)'; }
    else { cf.zones = 'none (vilfintv.com is not proxied through Cloudflare on this account)'; }

    // Web Analytics (visitor counts) — only if the zone is on Cloudflare with analytics
    if (accountId && Array.isArray(cf.zones) && cf.zones.length){
      const since = new Date(Date.now()-7*86400000).toISOString();
      const gql = { query: '{ viewer { accounts(filter:{accountTag:"'+accountId+'"}) { rumPageloadEventsAdaptiveGroups(limit:20, filter:{datetime_geq:"'+since+'"}, orderBy:[count_DESC]) { count dimensions { requestPath } } } } }' };
      const an = await fetch('https://api.cloudflare.com/client/v4/graphql', { method:'POST', headers:H, body:JSON.stringify(gql) });
      try { const aj = await an.json();
        const grp = aj && aj.data && aj.data.viewer && aj.data.viewer.accounts && aj.data.viewer.accounts[0] && aj.data.viewer.accounts[0].rumPageloadEventsAdaptiveGroups;
        if (grp && grp.length){ cf.analytics = { rangeDays:7, topPages: grp.map(function(g){ return { path:g.dimensions.requestPath, views:g.count }; }) }; cf.analytics.totalViews = grp.reduce(function(a,g){ return a+g.count; },0); }
        else { cf.analytics = { note:'No Web Analytics data. Enable Cloudflare Web Analytics for vilfintv.com (free) — needs the site proxied through Cloudflare, and Account Analytics:Read on the token.' }; }
      } catch(e){ cf.analytics = { note:'Web Analytics unavailable (needs Account Analytics:Read + Cloudflare-proxied site).' }; }
    } else { cf.analytics = { note:'Visitor analytics require vilfintv.com to be served through Cloudflare (it currently resolves to GitHub Pages). Enable Cloudflare Web Analytics to collect per-page visits.' }; }

    out.cloudflare = cf;
  } else { out.cloudflare = { configured:false, note:'Add CLOUDFLARE_API_TOKEN (read-only) to the worker to include Cloudflare security, storage & analytics.' }; }

  // 4) Summary
  const down = out.pages.filter(function(p){ return !p.ok; }).length;
  const totalBytes = out.pages.reduce(function(a,p){ return a + (p.bytes||0); }, 0);
  out.summary = {
    pagesTotal: out.pages.length, pagesDown: down, pagesTotalBytes: totalBytes,
    avgLatencyMs: Math.round(out.pages.reduce(function(a,p){ return a+(p.ms||0); },0) / (out.pages.length||1)),
    githubFailedWorkflows: out.github && out.github.failedWorkflows || 0,
    githubDependabotOpen: out.github ? out.github.dependabotOpen : 'n/a',
    r2TotalBytes: (out.cloudflare && out.cloudflare.r2TotalBytes) || 0,
    status: (down===0 && (!(out.github&&out.github.failedWorkflows))) ? 'healthy' : (down>0 ? 'attention' : 'warnings')
  };
  return out;
}

async function signJWT(payload, secret) {
  const h = _b64urlEncode(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const p = _b64urlEncode(JSON.stringify(payload));
  const input = `${h}.${p}`;
  const key = await _hmacKey(secret, 'sign');
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(input));
  return `${input}.${_b64urlEncode(sig)}`;
}
async function verifyJWT(token, secret) {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Malformed token.');
  const [h, p, s] = parts;
  const key = await _hmacKey(secret, 'verify');
  const ok = await crypto.subtle.verify('HMAC', key, _b64urlDecodeBytes(s),
    new TextEncoder().encode(`${h}.${p}`));
  if (!ok) throw new Error('Invalid signature.');
  const payload = JSON.parse(_b64urlDecodeStr(p));
  if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) throw new Error('Token expired.');
  return payload;
}
async function requireAuth(request, env) {
  if (!env || !env.JWT_SECRET) return { error: jsonError(503, 'JWT_SECRET not configured in Worker environment.') };
  const auth = request.headers.get('Authorization') || '';
  if (!auth.startsWith('Bearer ')) return { error: jsonError(401, 'Missing Bearer token. Please sign in.') };
  try {
    const payload = await verifyJWT(auth.slice(7), env.JWT_SECRET);
    // Session revocation: tokens minted with a jti must still have a live session
    // record. (Tokens issued before this feature have no jti → allowed until they
    // expire.) Fail-open on a KV error so a transient outage can't lock the admin out.
    if (payload && payload.jti && env.IPTV_KV) {
      try {
        if (payload.role !== 'admin' && payload.sub) {
          const op = await _opGet(env, payload.sub);
          if (op && op.expireDate && Date.now() > new Date(op.expireDate).getTime()) {
            return { error: jsonError(401, 'Account has expired.') };
          }
        }
        const all = await _sessAll(env);
        const s = all[payload.jti];
        if (!s) return { error: jsonError(401, 'This device was signed out. Please sign in again.') };
        const nowMs = Date.now();
        if (!s.lastSeen || nowMs - s.lastSeen > 600000) { s.lastSeen = nowMs; await _sessPut(env, all); }
      } catch(e) { /* fail-open */ }
    }
    return { payload };
  } catch(err) {
    return { error: jsonError(401, 'Session expired or invalid. Please sign in again.') };
  }
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
              To action this report, copy the <strong style="color:${cfg.colour}">AI Fix Query</strong> block above directly into Claude Code, GitHub Copilot, or VS Code Copilot Chat.
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
