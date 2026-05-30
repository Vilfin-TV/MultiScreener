#!/usr/bin/env python3
"""Idempotent, self-validating patch: add IPTV admin routes + PBKDF2 helpers to
screener-proxy-worker.js, matching the file's existing style (pathname routing,
jsonError, requireAuth().error, CORS). Aborts without changes if anchors are not
found exactly. Creates a .bak backup before writing."""
import sys, hashlib, pathlib

F = pathlib.Path("screener-proxy-worker.js")
src = F.read_text(encoding="utf-8")

if "/api/iptv/credentials" in src:
    print("ALREADY PATCHED — no changes made.")
    sys.exit(0)

LOGIN_ANCHOR = (
    "      const now = Math.floor(Date.now() / 1000);\n"
    "      const token = await signJWT({ sub: username, iat: now, exp: now + 86400 }, env.JWT_SECRET);\n"
    "      return new Response(\n"
    "        JSON.stringify({ ok: true, token }),\n"
    "        { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } }\n"
    "      );\n"
    "    }\n"
)
SIGNJWT_ANCHOR = "async function signJWT(payload, secret) {"

errs = []
if src.count(LOGIN_ANCHOR) != 1:
    errs.append(f"login anchor found {src.count(LOGIN_ANCHOR)}x (expected 1)")
if SIGNJWT_ANCHOR not in src:
    errs.append("signJWT anchor not found")
if errs:
    print("ABORT: " + "; ".join(errs) + ". No changes.")
    sys.exit(1)

ROUTES = r"""
    // ── /api/iptv/config  GET — current IPTV login id + settings (auth) ───────
    if (pathname === '/api/iptv/config') {
      if (request.method !== 'GET') return jsonError(405, 'Method not allowed. Use GET for /api/iptv/config.');
      const auth = await requireAuth(request, env);
      if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured. Bind a KV namespace as IPTV_KV.');
      let authObj = null, settings = null;
      try { const r = await env.IPTV_KV.get('iptv_auth');     authObj  = r ? JSON.parse(r) : {}; } catch (e) { authObj = {}; }
      try { const r = await env.IPTV_KV.get('iptv_settings'); settings = r ? JSON.parse(r) : null; } catch (e) {}
      if (!authObj) authObj = {};
      if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
      const accounts = Object.values(authObj).map(a => ({ username: a.username, updatedAt: a.updatedAt }));
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
      const auth = await requireAuth(request, env);
      if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured. Bind a KV namespace as IPTV_KV.');
      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
      const username = (body.username || '').toString().trim();
      const password = (body.password || '').toString();
      if (!username || username.length > 64) return jsonError(400, 'Username is required (max 64 chars).');
      if (!password || password.length < 6)  return jsonError(400, 'Password must be at least 6 characters.');
      const h = await _iptvHashPassword(password);
      const rec = {
        username: username,
        algo: 'pbkdf2-sha256',
        iterations: h.iterations,
        salt: h.salt,
        hash: h.hash,
        updatedAt: new Date().toISOString(),
      };
      let authObj = null;
      try { const r = await env.IPTV_KV.get('iptv_auth'); authObj = r ? JSON.parse(r) : {}; } catch (e) { authObj = {}; }
      if (!authObj) authObj = {};
      if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
      authObj[username] = rec;
      await env.IPTV_KV.put('iptv_auth', JSON.stringify(authObj));
      return _iptvJson({ ok: true, saved: true, username: username });
    }

    // ── /api/iptv/delete-account  POST — delete IPTV login id (auth) ──────────
    if (pathname === '/api/iptv/delete-account') {
      if (request.method !== 'POST') return jsonError(405, 'Method not allowed. Use POST for /api/iptv/delete-account.');
      const auth = await requireAuth(request, env);
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
      const auth = await requireAuth(request, env);
      if (auth.error) return auth.error;
      if (!env.IPTV_KV) return jsonError(503, 'IPTV store not configured. Bind a KV namespace as IPTV_KV.');
      let body;
      try { body = await request.json(); } catch (_) { return jsonError(400, 'Invalid JSON body.'); }
      const s = body.settings || body || {};
      const settings = {
        sessionHours: Math.max(1, Math.min(168, parseInt(s.sessionHours, 10) || 8)),
        defaultProvider: (s.defaultProvider === 'airtel') ? 'airtel' : 'jio',
        providers: {
          jio:    { enabled: s.providers && s.providers.jio    ? !!s.providers.jio.enabled    : true },
          airtel: { enabled: s.providers && s.providers.airtel ? !!s.providers.airtel.enabled : true },
        },
        updatedAt: new Date().toISOString(),
      };
      await env.IPTV_KV.put('iptv_settings', JSON.stringify(settings));
      return _iptvJson({ ok: true, saved: true, settings: settings });
    }
"""

HELPERS = r"""/* ── IPTV credential management (login id/password + settings) for the
      private IPTV console. Stored in KV (binding IPTV_KV) — the SAME namespace
      bound to the page-iptv worker as IPTV_PLAYLIST_KV. ── */
const IPTV_DEFAULT_SETTINGS = {
  sessionHours: 8,
  defaultProvider: 'jio',
  providers: { jio: { enabled: true }, airtel: { enabled: true } },
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

"""

out = src.replace(LOGIN_ANCHOR, LOGIN_ANCHOR + ROUTES, 1)
out = out.replace(SIGNJWT_ANCHOR, HELPERS + SIGNJWT_ANCHOR, 1)

F.with_suffix(".js.bak").write_text(src, encoding="utf-8")
F.write_text(out, encoding="utf-8")

print("PATCHED screener-proxy-worker.js")
print("  routes: /api/iptv/config (GET), /api/iptv/credentials (POST), /api/iptv/settings (POST)")
print("  +bytes:", len(out) - len(src), " sha256:", hashlib.sha256(out.encode('utf-8')).hexdigest()[:16])
