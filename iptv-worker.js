/**
 * iptv-worker.js — Private IPTV Console: auth gateway + CORS-safe HLS relay
 * ---------------------------------------------------------------------------
 * This is a SEPARATE worker from the main VilfinTV screener-proxy (worker.js).
 * Deploy it as `page-iptv` (see wrangler.iptv.toml). Do not merge into worker.js.
 *
 * Routes:
 *   GET  /  or  /iptv.html      -> serve the static dashboard (from ASSETS)
 *   POST /api/login             -> validate credentials, return a signed token
 *   GET  /api/settings          -> (auth) non-sensitive console settings
 *   GET  /api/playlist?provider -> validate token, read M3U from KV, return JSON
 *   GET  /api/stream?url=&token -> validate token, CORS-safe reverse proxy
 *
 * CREDENTIAL SOURCES (checked in order by /api/login):
 *   1. KV key "iptv_auth"  — login id + PBKDF2 password hash, managed from
 *                            link-console.html (the admin console). Authoritative
 *                            when present.
 *   2. env.IPTV_SECRET_USER / env.IPTV_SECRET_PASS — bootstrap fallback used
 *                            only when no KV credential has been configured yet.
 *
 * Required bindings (wrangler.iptv.toml):
 *   [secrets]
 *     IPTV_SECRET_USER   - bootstrap console username (optional once KV is set)
 *     IPTV_SECRET_PASS   - bootstrap console password (optional once KV is set)
 *     IPTV_TOKEN_SECRET  - HMAC signing secret for session tokens
 *   [kv_namespaces]
 *     IPTV_PLAYLIST_KV   - holds "{provider}_playlist", "iptv_auth", "iptv_settings"
 *                          (SAME namespace bound to the screener worker as IPTV_KV)
 *   [assets]
 *     ASSETS             - static asset binding serving ./public (iptv.html)
 *
 * NOTE ON STREAM PROXYING
 * -----------------------------------------------------------------------------
 * This proxy is a *generic* CORS relay for HLS sources you are entitled to
 * serve. It deliberately does NOT impersonate any commercial app's mobile
 * client (no spoofed "JioTV/Android" User-Agent, no forged Origin/Referer) to
 * defeat a provider's geo or identity enforcement. Point it at content you have
 * the right to distribute.
 * -----------------------------------------------------------------------------
 */

const DEFAULT_SESSION_HOURS = 8;

// --- MEMORY CACHE TO REDUCE KV READS ---
const _memCache = new Map();
async function memoKvGet(kv, key, ttlMs = 60000) {
  if (!kv) return null;
  const now = Date.now();
  if (_memCache.has(key)) {
    const entry = _memCache.get(key);
    if (now - entry.ts < ttlMs) return entry.val;
  }
  try {
    const val = await kv.get(key);
    _memCache.set(key, { ts: now, val });
    return val;
  } catch (e) {
    return null;
  }
}
function memoKvPut(key, val) {
  _memCache.set(key, { ts: Date.now(), val });
}

// All providers the console understands. free/pro ship with working open-source
// defaults; jio/airtel/custom are URL-driven (set in the admin console).
const IPTV_PROVIDERS = ["jio", "airtel", "zee5", "free", "pro", "custom"];

const IPTV_PROVIDER_DEFAULTS = {
  jio:    { enabled: true, url: "", epg: "" },
  airtel: { enabled: true, url: "", epg: "" },
  zee5:   { enabled: true, url: "", epg: "" },
  free:   { enabled: true, url: "https://iptv-org.github.io/iptv/index.m3u", epg: "https://epg.pw/xmltv/epg_IN.xml" },
  pro:    { enabled: true, url: "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", epg: "" },
  custom: { enabled: true, url: "", epg: "" },
};

function defaultProviders() {
  const out = {};
  for (const p of IPTV_PROVIDERS) out[p] = { ...IPTV_PROVIDER_DEFAULTS[p] };
  return out;
}

const IPTV_DEFAULT_SETTINGS = {
  sessionHours: DEFAULT_SESSION_HOURS,
  defaultProvider: "free",
  providers: defaultProviders(),
};

// Cache TTL (seconds) for fetched remote playlists / EPG, to stay within limits.
const PLAYLIST_CACHE_TTL = 1800; // 30 min
const EPG_CACHE_TTL = 3600;      // 60 min

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, Range",
  "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges, X-VTV-Cache",
  "Access-Control-Max-Age": "86400",
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Generic proxy for DRM keys
    if (url.pathname === '/api/proxy') {
      const targetUrl = url.searchParams.get('url');
      if (!targetUrl) return new Response('Missing url', { status: 400 });
      
      try {
        const response = await fetch(targetUrl, {
          headers: { 
            'User-Agent': 'okhttp/4.12.0',
            'X-Forwarded-For': '49.43.14.22',
            'X-Real-IP': '49.43.14.22',
            'CF-Connecting-IP': '49.43.14.22'
          }
        });
        const headers = new Headers(response.headers);
        headers.set('Access-Control-Allow-Origin', '*');
        return new Response(response.body, {
          status: response.status,
          headers: headers
        });
      } catch (err) {
        return new Response('Proxy error: ' + err.message, { status: 500 });
      }
    }

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const { pathname } = url;

    try {
      if (request.method === "GET" && (pathname === "/" || pathname === "/iptv.html")) {
        return await serveHtml(env);
      }
      if (request.method === "POST" && pathname === "/api/login") {
        return handleLogin(request, env);
      }
      if (request.method === "GET" && pathname === "/api/settings") {
        return handleSettings(request, env, url);
      }
      if (pathname === "/api/userdata" && (request.method === "GET" || request.method === "POST")) {
        return handleUserdata(request, env, url);
      }
      if (request.method === "GET" && pathname === "/api/playlist") {
        return handlePlaylist(request, env, url);
      }
      if (request.method === "GET" && pathname === "/api/epg") {
        return handleEpg(request, env, url);
      }
      // Public read-only routes for the vilfintv.com homepage Live TV panel.
      // No session needed, but ONLY providers in a "Free IPTV" region group are
      // exposed (public iptv-org lists) — private providers stay session-gated.
      if (request.method === "GET" && pathname === "/api/public/providers") {
        return handlePublicProviders(env);
      }
      if (request.method === "GET" && pathname === "/api/public/playlist") {
        return handlePublicPlaylist(request, env, url);
      }
      if (request.method === "GET" && pathname === "/api/public/epg") {
        return handlePublicEpg(request, env, url);
      }
      if (request.method === "GET" && pathname === "/api/stream") {
        return handleStream(request, env, url, ctx);
      }
      if (request.method === "GET" && (pathname === "/api/jio/play" || pathname === "/proxy")) {
        return handleJioTunnel(request, env, url);
      }
      if (request.method === "GET" && pathname === "/api/zee5/play") {
        return handleZee5Tunnel(request, env, url);
      }
      // Ops-only: manually advance the D1 sync (normally driven by the cron
      // trigger below). Guarded by a dedicated secret, not user session tokens.
      if (request.method === "GET" && pathname === "/api/admin/sync") {
        const key = url.searchParams.get("key") || "";
        if (!env.IPTV_SYNC_KEY || !safeEqual(key, env.IPTV_SYNC_KEY)) return json({ error: "Unauthorized" }, 401);
        const result = await runD1Sync(env);
        return json(result);
      }
      return json({ error: "Not found" }, 404);
    } catch (err) {
      return json({ error: "Server error", detail: String(err && err.message || err) }, 500);
    }
  },

  // Cron trigger (see wrangler.iptv.toml [triggers]) — advances the D1 sync
  // cursor by D1_SYNC_BATCH_SIZE providers each tick.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runD1Sync(env));
  },
};

/* ----------------------------- helpers ----------------------------- */

function json(obj, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS_HEADERS, ...extraHeaders },
  });
}

async function handleZee5Tunnel(request, env, url) {
  const kv = env.IPTV_PLAYLIST_KV;
  if (!kv) return json({ error: "KV not configured" }, 503);
  const tunnelUrl = await memoKvGet(kv, "zee5_tunnel_url");
  if (!tunnelUrl) return json({ error: "Zee5 Tunnel URL not found" }, 404);
  const targetUrl = new URL(tunnelUrl);
  targetUrl.pathname = "/zee5/play";
  targetUrl.search = url.search;
  const response = await fetch(targetUrl.toString(), { method: request.method, headers: request.headers, redirect: "manual" });
  const status = response.status === 206 ? 200 : response.status;
  const extraHeaders = {};
  if (response.headers.has("content-type")) extraHeaders["Content-Type"] = response.headers.get("content-type");
  if (response.headers.has("content-length")) extraHeaders["Content-Length"] = response.headers.get("content-length");
  if (response.headers.has("location")) extraHeaders["Location"] = response.headers.get("location");
  
  const headers = { "Content-Type": "application/json; charset=utf-8", ...CORS_HEADERS, ...extraHeaders };
  if (status >= 300 && status < 400) delete headers["Content-Type"];
  
  return new Response(response.body, { status, headers });
}

async function handleJioTunnel(request, env, url) {
  const kv = env.IPTV_PLAYLIST_KV;
  if (!kv) return json({ error: "KV not configured" }, 503);
  const tunnelUrl = await memoKvGet(kv, 'jio_tunnel_url');
  if (!tunnelUrl) return json({ error: "Jio Tunnel URL not found" }, 404);
  
  // Reconstruct the URL for the tunnel
  const targetUrl = new URL(tunnelUrl);
  if (url.pathname === "/api/jio/play") {
    targetUrl.pathname = "/play";
  } else {
    targetUrl.pathname = url.pathname; // /proxy
  }
  targetUrl.search = url.search;
  
  // Fetch from the tunnel
  const response = await fetch(targetUrl.toString(), {
    method: request.method,
    headers: request.headers,
    redirect: "manual"
  });
  
  // Return the exact response from the tunnel (including 302 redirects)
  const responseHeaders = new Headers(response.headers);
  responseHeaders.set("Access-Control-Allow-Origin", "*");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders
  });
}

const enc = new TextEncoder();

/* ------------------------- m3u security / sanitizing -------------------------
 * Lightweight guards run server-side BEFORE any channel reaches the browser, and
 * on every proxied stream request. Purpose:
 *   - SSRF: stop a hostile playlist from pointing stream/logo URLs at internal
 *     hosts (localhost, RFC1918, link-local 169.254.x, cloud metadata, IPv6 ULA).
 *   - Injection: strip control chars / angle brackets and cap field lengths so
 *     channel metadata can't smuggle markup or absurd payloads to the front-end.
 *   - DoS: cap channels per playlist.
 * The heavy pass (parseM3U) runs once per fetch and is KV-cached ~30 min, so the
 * cost is amortised to ~zero; the per-stream check is a couple of string ops.
 * ---------------------------------------------------------------------------- */
const MAX_CHANNELS_PER_PLAYLIST = 20000;

function _hostIsBlocked(host) {
  host = (host || "").toLowerCase().replace(/^\[|\]$/g, ""); // strip IPv6 [..]
  if (!host) return true;
  if (host === "localhost" || host.endsWith(".localhost") ||
      host.endsWith(".local") || host.endsWith(".internal") ||
      host === "metadata.google.internal") return true;
  // IPv4 literal → block loopback / private / link-local / CGNAT / metadata.
  const m = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (m) {
    const a = +m[1], b = +m[2];
    if (a === 0 || a === 127 || a === 10) return true;
    if (a === 169 && b === 254) return true;       // link-local + 169.254.169.254 metadata
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168 && host !== '192.168.1.105') return true;
    if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT
    return false;
  }
  // IPv6 literal → block loopback / unique-local (fc00::/7) / link-local (fe80::/10).
  if (host.indexOf(":") !== -1) {
    if (host === "::1" || host === "::") return true;
    if (/^f[cd][0-9a-f]{2}:/.test(host)) return true;
    if (/^fe[89ab][0-9a-f]:/.test(host)) return true;
    return false;
  }
  return false; // ordinary hostname — allowed (cannot cheaply resolve in a Worker)
}

function _isSafeStreamUrl(u) {
  if (!u) return false;
  let url;
  try { url = new URL(u); } catch (e) { return false; }
  if (url.protocol === "jio:") return true;
  if (url.protocol === "zee5:") return true;
  if (url.protocol !== "http:" && url.protocol !== "https:") return false;
  return !_hostIsBlocked(url.hostname);
}

function _sanitizeText(s, maxLen) {
  s = String(s == null ? "" : s);
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const cc = s.charCodeAt(i);
    if (cc < 32 || cc === 127 || cc === 60 || cc === 62) continue; // strip control chars + < >
    out += s[i];
  }
  out = out.trim();
  if (maxLen && out.length > maxLen) out = out.slice(0, maxLen);
  return out;
}

function b64urlEncode(bytes) {
  let bin = "";
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (let i = 0; i < arr.length; i++) bin += String.fromCharCode(arr[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function b64urlDecodeToString(str) {
  str = str.replace(/-/g, "+").replace(/_/g, "/");
  while (str.length % 4) str += "=";
  return atob(str);
}

function hexFromBytes(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += bytes[i].toString(16).padStart(2, "0");
  return s;
}
function hexToBytes(hex) {
  const m = hex.match(/.{1,2}/g) || [];
  return Uint8Array.from(m.map((b) => parseInt(b, 16)));
}

/** PBKDF2-SHA256. Matches the hashing used by the screener worker (link-console). */
async function iptvHashPassword(password, saltHex, iterations) {
  const iter = iterations || 100000;
  const salt = saltHex ? hexToBytes(saltHex) : crypto.getRandomValues(new Uint8Array(16));
  const km = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt, iterations: iter, hash: "SHA-256" }, km, 256
  );
  return { salt: hexFromBytes(salt), hash: hexFromBytes(new Uint8Array(bits)), iterations: iter };
}

async function hmacSign(message, secret) {
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return b64urlEncode(sig);
}

/** Constant-time-ish string compare. */
function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/* ----------------------------- settings ----------------------------- */

async function loadSettings(env) {
  const kv = env.IPTV_PLAYLIST_KV;
  const base = { sessionHours: DEFAULT_SESSION_HOURS, defaultProvider: "free", providers: defaultProviders() };
  if (!kv) return base;
  const raw = await memoKvGet(kv, "iptv_settings");
  if (!raw) return base;
  try {
    const s = JSON.parse(raw);
    const provList = s.providers ? (Array.isArray(s.providers) ? s.providers : Object.values(s.providers)) : [];
    const hasSaved = provList.some((x) => x && x.id);
    // When the admin has configured a provider list, use ONLY that list — don't
    // re-seed the built-in jio/airtel/free/pro/custom defaults (so they can be
    // removed/renamed for good). Fall back to defaults only when nothing is saved.
    const providers = hasSaved ? {} : defaultProviders();

    for (const saved of provList) {
      if (!saved || !saved.id) continue;
      const p = saved.id;
      const prev = providers[p] || {};
      providers[p] = {
        name: saved.name || p,
        icon: saved.icon !== undefined ? String(saved.icon || "").trim() : (prev.icon || ""),
        group: saved.group !== undefined ? String(saved.group || "").trim() : (prev.group || ""),
        region: saved.region !== undefined ? String(saved.region || "").trim() : (prev.region || ""),
        enabled: saved.enabled === undefined ? (prev.enabled !== undefined ? prev.enabled : true) : !!saved.enabled,
        url: saved.url !== undefined ? String(saved.url || "").trim() : (prev.url || ""),
        epg: saved.epg !== undefined ? String(saved.epg || "").trim() : (prev.epg || ""),
      };
    }

    // Manually-added single channels (name + direct .m3u8). Surfaced as one
    // virtual "My Channels" source so they flow through the normal player pipeline.
    const customChannels = Array.isArray(s.customChannels) ? s.customChannels : [];
    if (customChannels.length) {
      providers[CUSTOM_PROVIDER_ID] = { name: "My Channels", icon: "★", group: "", region: "", enabled: true, url: "", epg: "", custom: true };
    }
    
    if (!providers['jio']) {
      providers['jio'] = { name: "Jio IPTV", icon: "J", group: "", region: "", enabled: true, url: "", epg: "" };
    }
    if (!providers['zee5']) {
      providers['zee5'] = { name: "Zee5 TV", icon: "Z", group: "", region: "", enabled: true, url: "", epg: "" };
    }

    return {
      sessionHours: Math.max(1, Math.min(168, parseInt(s.sessionHours, 10) || DEFAULT_SESSION_HOURS)),
      defaultProvider: providers[s.defaultProvider] ? s.defaultProvider : (Object.keys(providers)[0] || "free"),
      providers,
      customChannels,
    };
  } catch (e) {
    return base;
  }
}

const CUSTOM_PROVIDER_ID = "_custom";
/** Turn stored custom channels into sanitized channel objects (drops unsafe URLs). */
function _customChannels(settings) {
  const out = [];
  const list = (settings && settings.customChannels) || [];
  for (const c of list) {
    const url = String(c && c.url || "").trim();
    if (!_isSafeStreamUrl(url)) continue;
    out.push({
      name: _sanitizeText(c && c.name, 180) || "Channel",
      id: "", logo: _isSafeStreamUrl(c && c.logo) ? c.logo : "",
      category: _sanitizeText(c && c.category, 80) || "Custom",
      language: "", quality: guessQuality(String(c && c.name || "")), url: url, source: "My Channels", sourceId: CUSTOM_PROVIDER_ID,
    });
  }
  return out;
}

/* ----------------------------- tokens ----------------------------- */

async function issueToken(username, env, ttlSeconds) {
  const secret = env.IPTV_TOKEN_SECRET || env.IPTV_SECRET_PASS;
  const ttl = ttlSeconds || DEFAULT_SESSION_HOURS * 3600;
  const jti = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  const payload = {
    sub: username,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + ttl,
    jti: jti
  };
  const body = b64urlEncode(enc.encode(JSON.stringify(payload)));
  const sig = await hmacSign(body, secret);
  
  if (env.IPTV_PLAYLIST_KV) {
    try {
      const r = await env.IPTV_PLAYLIST_KV.get('iptv_sessions');
      const allSess = r ? JSON.parse(r) : {};
      const now = Date.now();
      for (const k of Object.keys(allSess)) {
        if (allSess[k] && allSess[k].exp < now) delete allSess[k];
      }
      allSess[jti] = { username: username, exp: payload.exp * 1000 };
      await env.IPTV_PLAYLIST_KV.put('iptv_sessions', JSON.stringify(allSess));
    } catch (e) {}
  }
  
  return body + "." + sig;
}

async function verifyToken(token, env) {
  if (!token || token.indexOf(".") === -1) return null;
  const secret = env.IPTV_TOKEN_SECRET || env.IPTV_SECRET_PASS;
  const [body, sig] = token.split(".");
  const expected = await hmacSign(body, secret);
  if (!safeEqual(sig, expected)) return null;
  let payload;
  try { payload = JSON.parse(b64urlDecodeToString(body)); } catch (e) { return null; }
  if (!payload || typeof payload.exp !== "number") return null;
  if (Math.floor(Date.now() / 1000) >= payload.exp) return null;
  if (env.IPTV_PLAYLIST_KV && payload.jti) {
    try {
      const r = await memoKvGet(env.IPTV_PLAYLIST_KV, 'iptv_sessions_revoked');
      const revoked = r ? JSON.parse(r) : {};
      if (revoked[payload.jti]) return null;
    } catch (e) {}
  }
  if (env.IPTV_PLAYLIST_KV && payload.sub) {
    try {
      const rawAuth = await memoKvGet(env.IPTV_PLAYLIST_KV, 'iptv_auth');
      if (rawAuth) {
        let authObj = JSON.parse(rawAuth);
        if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
        const rec = authObj[payload.sub];
        // Only reject on an explicit expiry. A missing record can be a bootstrap
        // (env-secret) user or eventual-consistency lag in KV — rejecting there
        // logged users out on every refresh. Instant revoke still works via the
        // iptv_sessions_revoked list checked above.
        if (rec && rec.expireDate && new Date() > new Date(rec.expireDate)) return null; // Account expired
      }
    } catch (e) {}
  }
  return payload;
}

function bearerFrom(request, url) {
  const h = request.headers.get("Authorization") || "";
  if (h.toLowerCase().startsWith("bearer ")) return h.slice(7).trim();
  return url.searchParams.get("token") || "";
}

async function requireAuth(request, env, url) {
  const token = bearerFrom(request, url);
  const payload = await verifyToken(token, env);
  return payload; // null if invalid
}

/* ----------------------------- routes ----------------------------- */

async function serveHtml(env) {
  // Preferred: the static asset binding (see [assets] in wrangler.iptv.toml).
  if (env.ASSETS && typeof env.ASSETS.fetch === "function") {
    const assetResp = await env.ASSETS.fetch(new Request("https://assets.local/iptv.html"));
    if (assetResp && assetResp.status === 200) {
      const headers = new Headers(assetResp.headers);
      headers.set("Content-Type", "text/html; charset=utf-8");
      headers.set("Cache-Control", "no-store");
      return new Response(assetResp.body, { status: 200, headers });
    }
  }
  // Fallback: inline HTML provided as a var.
  if (typeof env.IPTV_HTML === "string" && env.IPTV_HTML.length) {
    return new Response(env.IPTV_HTML, {
      headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  return new Response(
    "<!doctype html><meta charset=utf-8><title>IPTV Console</title>" +
    "<p>iptv.html is not bound to this Worker. Bind ./public as static assets " +
    "(ASSETS) or set the IPTV_HTML var.</p>",
    { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}

async function handleLogin(request, env) {
  let creds;
  try { creds = await request.json(); } catch (e) { return json({ error: "Invalid JSON body" }, 400); }
  const username = (creds && creds.username || "").toString();
  const password = (creds && creds.password || "").toString();
  if (!username || !password) return json({ error: "Username and password required" }, 400);

  // 1) KV-managed credential (set from link-console). Authoritative if present.
  const kv = env.IPTV_PLAYLIST_KV;
  if (kv) {
    const raw = await memoKvGet(kv, "iptv_auth");
    if (raw) {
      let authObj = null;
      try { authObj = JSON.parse(raw); } catch (e) {}
      if (authObj) {
        if (authObj.hash && authObj.username) authObj = { [authObj.username]: authObj };
        const rec = authObj[username];
        if (rec && rec.hash) {
          let ok = safeEqual(username, rec.username || "");
          if (ok) {
            const h = await iptvHashPassword(password, rec.salt, rec.iterations);
            ok = safeEqual(h.hash, rec.hash);
          }
          if (!ok) return json({ error: "Invalid credentials" }, 401);

          // Advanced Accounts Checks
          if (rec.expireDate) {
            if (new Date() > new Date(rec.expireDate)) {
              return json({ error: "Account expired. Please contact support." }, 403);
            }
          }
          /* Max concurrent sessions limit removed by request — refreshing or
             opening the player on another device no longer blocks the user. */

          rec.loginCount = (rec.loginCount || 0) + 1;
          rec.lastSeenAt = new Date().toISOString();
          authObj[username] = rec;
          const authJson = JSON.stringify(authObj);
          memoKvPut("iptv_auth", authJson);
          await env.IPTV_PLAYLIST_KV.put("iptv_auth", authJson);

          const settings = await loadSettings(env);
          const ttl = settings.sessionHours * 3600;
          const token = await issueToken(username, env, ttl);
          return json({ token, expires_in: ttl });
        } else if (Object.keys(authObj).length > 0) {
          return json({ error: "Invalid credentials" }, 401);
        }
      }
    }
  }

  // 2) Bootstrap fallback to env secrets when no KV credential is configured.
  if (!env.IPTV_SECRET_USER || !env.IPTV_SECRET_PASS) {
    return json({ error: "No credentials configured. Set them in the admin console." }, 503);
  }
  if (!safeEqual(username, env.IPTV_SECRET_USER) || !safeEqual(password, env.IPTV_SECRET_PASS)) {
    return json({ error: "Invalid credentials" }, 401);
  }
  const settings = await loadSettings(env);
  const ttl = settings.sessionHours * 3600;
  const token = await issueToken(username, env, ttl);
  return json({ token, expires_in: ttl });
}

async function handleSettings(request, env, url) {
  const auth = await requireAuth(request, env, url);
  if (!auth) return json({ error: "Unauthorized" }, 401);
  const settings = await loadSettings(env);
  return json({ settings });
}

/* Per-user profile data (favorites, hidden channels, player prefs), keyed by
 * the signed-in username from the session token — so the same profile follows
 * the user across devices and browsers.
 *   GET  /api/userdata -> { data: {favs,hidden,prefs,updatedAt} | null }
 *   POST /api/userdata -> stores a sanitized snapshot, returns { ok, updatedAt } */
async function handleUserdata(request, env, url) {
  const auth = await requireAuth(request, env, url);
  if (!auth) return json({ error: "Unauthorized" }, 401);
  const kv = env.IPTV_PLAYLIST_KV;
  if (!kv) return json({ error: "KV not configured" }, 503);
  const key = "iptv_userdata_" + String(auth.sub || "user").toLowerCase().slice(0, 100);

  if (request.method === "GET") {
    const raw = await kv.get(key);
    if (!raw) return json({ data: null });
    try { return json({ data: JSON.parse(raw) }); } catch (e) { return json({ data: null }); }
  }

  let body;
  try { body = await request.json(); } catch (e) { return json({ error: "Invalid JSON" }, 400); }
  const strList = (v, max) => Array.isArray(v) ? v.slice(0, max).map((x) => String(x).slice(0, 600)) : [];
  const data = {
    favs: strList(body.favs, 2000),
    hidden: strList(body.hidden, 5000),
    prefs: (body.prefs && typeof body.prefs === "object" && !Array.isArray(body.prefs)) ? body.prefs : {},
    updatedAt: Date.now(),
  };
  const str = JSON.stringify(data);
  if (str.length > 250000) return json({ error: "Profile data too large" }, 413);
  await kv.put(key, str);
  return json({ ok: true, updatedAt: data.updatedAt });
}

/* ----------------------------- R2 cache (playlists / EPG / merges) -----------------------------
 * These blobs are large and refreshed every 15-60 min across ~150 sources, which was burning
 * through the Workers KV free-tier daily operations quota (reads+writes). R2 has a much larger
 * free quota and is the right tool for large, disposable cache blobs. Falls back to KV automatically
 * if the R2 binding is ever missing, so a config slip degrades gracefully instead of breaking playback.
 * Expiry is tracked via R2 customMetadata (R2 has no per-object TTL like KV's expirationTtl). */
async function cacheGet(env, key) {
  if (env.IPTV_CACHE) {
    try {
      const obj = await env.IPTV_CACHE.get(key);
      if (!obj) return "";
      const exp = obj.customMetadata && obj.customMetadata.expires;
      if (exp && Date.now() > Number(exp)) return "";
      return await obj.text();
    } catch (e) { return ""; }
  }
  if (env.IPTV_PLAYLIST_KV) { try { return (await env.IPTV_PLAYLIST_KV.get(key)) || ""; } catch (e) { return ""; } }
  return "";
}
async function cachePut(env, key, value, ttlSeconds) {
  if (env.IPTV_CACHE) {
    try { await env.IPTV_CACHE.put(key, value, { customMetadata: { expires: String(Date.now() + ttlSeconds * 1000) } }); } catch (e) {}
    return;
  }
  if (env.IPTV_PLAYLIST_KV) { try { await env.IPTV_PLAYLIST_KV.put(key, value, { expirationTtl: ttlSeconds }); } catch (e) {} }
}

/** Fetch the raw M3U text for one provider id (remote URL w/ R2 cache, then
 *  synced {id}_playlist KV fallback). Returns "" when nothing is available. */
async function loadProviderRaw(env, providerId, pconf) {
  const kv = env.IPTV_PLAYLIST_KV;
  let raw = "";
  const srcUrl = (pconf && pconf.url || "").trim();
  if (srcUrl) {
    const cacheKey = "cache_playlist_" + providerId;
    raw = await cacheGet(env, cacheKey);
    if (!raw) {
      try {
        const resp = await fetch(srcUrl, { headers: { "User-Agent": "Mozilla/5.0 (compatible; IPTVConsole/1.0)" }, redirect: "follow" });
        if (resp.ok) {
          raw = await resp.text();
          if (raw && raw.length < 24 * 1024 * 1024) {
            await cachePut(env, cacheKey, raw, PLAYLIST_CACHE_TTL);
          }
        }
      } catch (e) {
        console.warn("Failed to fetch playlist URL for " + providerId + ": " + e);
      }
    }
  }
  if (!raw) raw = await cacheGet(env, providerId + "_playlist");
  return raw;
}

async function handlePlaylist(request, env, url) {
  const auth = await requireAuth(request, env, url);
  if (!auth) return json({ error: "Unauthorized" }, 401);

  // Region merge mode: ?region=<region> combines every provider in that region.
  if (url.searchParams.get("region")) return handleRegionPlaylist(request, env, url);
  // Multi-source merge: ?providers=a,b,c  or  ?all=1  (dedup duplicate m3u URLs).
  if (url.searchParams.get("providers") || url.searchParams.get("all")) return handleMergePlaylist(request, env, url);

  const provider = (url.searchParams.get("provider") || "").toLowerCase();
  const settings = await loadSettings(env);
  // Virtual "My Channels" source — the manually-added single channels.
  if (provider === CUSTOM_PROVIDER_ID) {
    const ch = _customChannels(settings);
    return json({ provider, count: ch.length, epg: "", channels: ch });
  }
  if (!settings.providers[provider]) return json({ error: "Invalid provider" }, 400);

  const pconf = settings.providers[provider] || {};
  if (pconf.enabled === false) return json({ error: "Provider is disabled" }, 403);

  const kv = env.IPTV_PLAYLIST_KV;
  if (!kv) return json({ error: "Playlist store not configured" }, 503);

  const srcUrl = (pconf.url || "").trim();
  const raw = await loadProviderRaw(env, provider, pconf);

  if (!raw) {
    return json({ error: srcUrl ? "Could not load playlist from the configured URL." : "No playlist configured for this provider." }, 404);
  }

  const channels = parseM3U(raw);
  if (provider === "jio") applyJioMeta(channels);
  return json({ provider, count: channels.length, epg: (pconf.epg || ""), channels });
}

// Cap how many sources we merge / channels we return for one region, to stay
// within Worker subrequest & response limits and keep it fast.
const REGION_MAX_SOURCES = 40;
const REGION_MAX_CHANNELS = 8000;
const REGION_CACHE_TTL = 900; // 15 min for the merged result

/** ?region=<region> — merge every enabled provider tagged with that region into
 *  one channel list (deduped by stream URL). Cached briefly per region. */
async function handleRegionPlaylist(request, env, url) {
  const region = (url.searchParams.get("region") || "").trim();
  if (!region) return json({ error: "Missing region" }, 400);
  const settings = await loadSettings(env);

  const members = Object.keys(settings.providers)
    .map((id) => Object.assign({ id }, settings.providers[id]))
    .filter((p) => p.enabled !== false && String(p.region || "").trim() === region);
  if (!members.length) return json({ error: "No sources in this region" }, 404);

  const cacheKey = "cache_region_" + region;
  const cached = await cacheGet(env, cacheKey);
  if (cached) {
    try { const obj = JSON.parse(cached); return json(obj); } catch (e) {}
  }

  const seen = Object.create(null);
  const channels = [];
  let used = 0;
  for (const p of members.slice(0, REGION_MAX_SOURCES)) {
    const raw = await loadProviderRaw(env, p.id, p);
    if (!raw) continue;
    used++;
    const list = parseM3U(raw);
    for (const ch of list) {
      const key = ch.url;
      if (!key || seen[key]) continue;
      seen[key] = 1;
      channels.push(ch);
      if (channels.length >= REGION_MAX_CHANNELS) break;
    }
    if (channels.length >= REGION_MAX_CHANNELS) break;
  }

  const out = { region, sources: used, count: channels.length, epg: "", channels };
  if (channels.length) await cachePut(env, cacheKey, JSON.stringify(out), REGION_CACHE_TTL);
  return json(out);
}

const MERGE_MAX_SOURCES = 60;
const MERGE_MAX_CHANNELS = 40000; // per-source dedup keeps cross-source copies, so allow more
function _shortHash(s) { let h = 0; for (let i = 0; i < s.length; i++) { h = ((h << 5) - h + s.charCodeAt(i)) | 0; } return (h >>> 0).toString(36); }

/** ?providers=a,b,c  or  ?all=1 — merge the selected sources into one list.
 *  Duplicate m3u URLs are removed at the source level (so the same playlist is
 *  never fetched/listed twice). Channels are kept even when names repeat across
 *  different sources (only EXACT same stream URL is de-duplicated); each channel
 *  is tagged with `source`. Fetches run in parallel and the merge is cached. */
async function handleMergePlaylist(request, env, url) {
  const settings = await loadSettings(env);
  const all = url.searchParams.get("all");
  let ids;
  if (all) {
    ids = Object.keys(settings.providers).filter((id) => settings.providers[id].enabled !== false);
  } else {
    ids = (url.searchParams.get("providers") || "").split(",").map((s) => s.trim()).filter(Boolean)
      .filter((id) => settings.providers[id] && settings.providers[id].enabled !== false);
  }
  if (!ids.length) return json({ error: "No valid sources selected" }, 400);

  const includeCustom = !!all || ids.indexOf(CUSTOM_PROVIDER_ID) !== -1;

  // Source-level dedup by m3u URL; the virtual "My Channels" source is handled separately.
  const seenUrl = Object.create(null);
  const members = [];
  for (const id of ids) {
    if (id === CUSTOM_PROVIDER_ID) continue;
    const p = Object.assign({ id }, settings.providers[id]);
    const u = String(p.url || "").trim().toLowerCase();
    if (u) { if (seenUrl[u]) continue; seenUrl[u] = 1; }
    members.push(p);
    if (members.length >= MERGE_MAX_SOURCES) break;
  }

  // The m3u-merged portion is cacheable; custom channels are appended fresh below.
  let channels = null, used = 0;
  const cacheKey = "cache_merge_" + (all ? "all" : _shortHash(members.map((p) => p.id).sort().join(",")));
  const cached = await cacheGet(env, cacheKey);
  if (cached) { try { const o = JSON.parse(cached); channels = o.channels; used = o.sources || 0; } catch (e) {} }
  if (!channels) {
    const raws = await Promise.all(members.map((p) => loadProviderRaw(env, p.id, p).catch(() => "")));
    const seenStream = Object.create(null);
    channels = [];
    for (let i = 0; i < members.length; i++) {
      const raw = raws[i];
      if (!raw) continue;
      used++;
      const list = parseM3U(raw);
      for (const ch of list) {
        // Dedup PER SOURCE only — the same channel from different sources (India,
        // Malayalam, All World …) is intentionally kept so it lists once per source.
        const key = members[i].id + "|" + ch.url;
        if (!ch.url || seenStream[key]) continue;
        seenStream[key] = 1;
        ch.source = members[i].name || members[i].id;
        ch.sourceId = members[i].id;
        channels.push(ch);
        if (channels.length >= MERGE_MAX_CHANNELS) break;
      }
      if (channels.length >= MERGE_MAX_CHANNELS) break;
    }
    if (channels.length) await cachePut(env, cacheKey, JSON.stringify({ channels, sources: used }), REGION_CACHE_TTL);
  }

  // Append manually-added channels fresh, so newly-added ones appear immediately.
  if (includeCustom) {
    const have = Object.create(null);
    for (const c of channels) have[c.url] = 1;
    for (const c of _customChannels(settings)) { if (c.url && !have[c.url]) { channels.push(c); have[c.url] = 1; } }
  }

  return json({ sources: used + (includeCustom ? 1 : 0), requested: ids.length, count: channels.length, epg: "", channels });
}

/**
 * EPG (XMLTV) program lookup for a single channel, on demand with caching.
 * GET /api/epg?provider=<p>&channel=<tvg-id>&name=<display name, optional>
 * `name` is used as a fallback match when the tvg-id isn't present in the guide
 * verbatim (common with aggregated M3U lists whose ids don't match the guide's own).
 * Returns { now, next, programs:[{start,stop,title,desc}] } — never the whole guide.
 */
async function handleEpg(request, env, url) {
  const auth = await requireAuth(request, env, url);
  if (!auth) return json({ error: "Unauthorized" }, 401);

  const provider = (url.searchParams.get("provider") || "").toLowerCase();
  const channel = (url.searchParams.get("channel") || "").trim();
  const channelName = (url.searchParams.get("name") || "").trim();
  const settings = await loadSettings(env);
  if (!settings.providers[provider]) return json({ error: "Invalid provider" }, 400);
  if (!channel && !channelName) return json({ error: "Missing channel id" }, 400);
  return epgLookup(env, settings, provider, channel, channelName);
}

/** Shared EPG lookup used by /api/epg (session) and /api/public/epg (public). */
async function epgLookup(env, settings, provider, channel, channelName) {
  const epgUrl = ((settings.providers[provider] || {}).epg || "").trim();
  if (!epgUrl && provider !== 'jio') return json({ programs: [], now: null, next: null, note: "No EPG configured" });

  const cacheKey = "cache_epg_" + provider;
  let xml = await cacheGet(env, cacheKey);
  
  if (!xml && provider === 'jio') {
      xml = await cacheGet(env, 'jio_epg');
  }
  
  if (!xml && epgUrl) {
    try {
      const resp = await fetch(epgUrl, { headers: { "User-Agent": "Mozilla/5.0 (compatible; IPTVConsole/1.0)" }, redirect: "follow" });
      if (resp.ok) {
        xml = await resp.text();
        if (xml && xml.length < 24 * 1024 * 1024) await cachePut(env, cacheKey, xml, EPG_CACHE_TTL);
      }
    } catch (e) {
      return json({ programs: [], now: null, next: null, error: "EPG fetch failed" });
    }
  }
  if (!xml) return json({ programs: [], now: null, next: null, error: "EPG unavailable" });

  let programs = parseEpgForChannel(xml, channel);
  // tvg-id in aggregated M3U lists rarely matches a third-party guide's own channel
  // id scheme (e.g. "Asianet.in@SD" vs. epg.pw's numeric "404001"). Fall back to
  // matching by channel NAME against the guide's own id<->display-name map.
  if (!programs.length && channelName) {
    const foundId = _findEpgChannelIdByName(xml, channelName);
    if (foundId && foundId.toLowerCase() !== channel.toLowerCase()) {
      programs = parseEpgForChannel(xml, foundId);
    }
  }
  const nowMs = Date.now();
  let now = null, next = null;
  for (let i = 0; i < programs.length; i++) {
    const p = programs[i];
    if (p.startMs <= nowMs && nowMs < p.stopMs) { now = p; next = programs[i + 1] || null; break; }
    if (p.startMs > nowMs) { next = p; break; }
  }
  return json({ channel, count: programs.length, now, next, programs: programs.slice(0, 12) });
}

/* ----------------------------- public (no-session) routes -----------------------------
 * Read-only API for the vilfintv.com homepage Live TV panel. Only providers whose
 * region label contains "Free IPTV" (public iptv-org lists) are exposed; every
 * session-gated provider (jio, zee5, …) is invisible here. Responses carry
 * browser/edge cache headers because this data changes at most every 15-60 min. */

const PUBLIC_CACHE_HEADERS = { "Cache-Control": "public, max-age=900" };

function _isPublicProvider(pconf) {
  // Public = the free iptv-org-style region groups ("India Free IPTV",
  // "All World IPTV", …). "Premium IPTV" and blank-region providers
  // (jio, zee5, …) never match.
  return !!pconf && pconf.enabled !== false &&
    /(free|all\s*world)\s*iptv/i.test(String(pconf.region || ""));
}

async function handlePublicProviders(env) {
  const settings = await loadSettings(env);
  const out = [];
  for (const id in settings.providers) {
    const p = settings.providers[id];
    if (!_isPublicProvider(p)) continue;
    out.push({ id, name: p.name || id, icon: p.icon || "", region: p.region || "", hasEpg: !!(p.epg || "").trim() });
  }
  return json({ count: out.length, providers: out }, 200, PUBLIC_CACHE_HEADERS);
}

async function handlePublicPlaylist(request, env, url) {
  const provider = (url.searchParams.get("provider") || "").toLowerCase();
  const settings = await loadSettings(env);
  const pconf = settings.providers[provider];
  if (!_isPublicProvider(pconf)) return json({ error: "Invalid provider" }, 400);

  const raw = await loadProviderRaw(env, provider, pconf);
  if (!raw) return json({ error: "Playlist unavailable" }, 503);
  const channels = parseM3U(raw).map((c) => ({
    id: c.id, name: c.name, url: c.url, logo: c.logo,
    category: c.category, language: c.language, quality: c.quality,
  }));
  return json({ provider, name: pconf.name || provider, count: channels.length, channels }, 200, PUBLIC_CACHE_HEADERS);
}

async function handlePublicEpg(request, env, url) {
  const provider = (url.searchParams.get("provider") || "").toLowerCase();
  const channel = (url.searchParams.get("channel") || "").trim();
  const channelName = (url.searchParams.get("name") || "").trim();
  const settings = await loadSettings(env);
  if (!_isPublicProvider(settings.providers[provider])) return json({ error: "Invalid provider" }, 400);
  if (!channel && !channelName) return json({ error: "Missing channel id" }, 400);
  return epgLookup(env, settings, provider, channel, channelName);
}

/**
 * Generic CORS-safe relay. Forwards Range, relays Content-Type/Range, adds CORS.
 * Does NOT spoof any provider's mobile-app identity.
 */
// HLS media segments are immutable once produced (a segment file's bytes never
// change; the live manifest just advertises new files over time). So segments
// can be safely edge-cached for a short window to skip the Worker→origin hop on
// re-requests (multiple viewers / re-tuning). Live MANIFESTS are never cached
// (they must stay fresh or playback stalls) and AES KEYS are never cached (they
// rotate). Any auth token lives in the segment URL, so a rotated token is a
// different cache key — cached content can never go stale-authed. Every cache
// op is best-effort and wrapped so a failure degrades to the plain relay.
const STREAM_SEG_CACHE_TTL = 30; // seconds

async function handleStream(request, env, url, ctx) {
  const auth = await requireAuth(request, env, url);
  if (!auth) return json({ error: "Unauthorized" }, 401);

  const target = url.searchParams.get("url");
  if (!target) return json({ error: "Missing url parameter" }, 400);

  let upstreamUrl;
  try { upstreamUrl = new URL(target); } catch (e) { return json({ error: "Invalid url" }, 400); }
  if (upstreamUrl.protocol !== "http:" && upstreamUrl.protocol !== "https:") {
    return json({ error: "Unsupported protocol" }, 400);
  }
  // SECURITY (SSRF): never let the proxy reach loopback/private/link-local/metadata hosts.
  if (_hostIsBlocked(upstreamUrl.hostname)) {
    return json({ error: "Blocked host" }, 403);
  }

  // Caching eligibility: never a key (k=key), never a range request, GET only.
  // Manifests are excluded below once their content-type is known. Only segments
  // are ever stored, so any cache hit is guaranteed to be an immutable segment.
  const isKey = url.searchParams.get("k") === "key";
  const hasRange = request.headers.has("Range");
  const cacheEligible = !isKey && !hasRange && request.method === "GET";
  const cache = (typeof caches !== "undefined" && caches.default) || null;
  let cacheKey = null;
  if (cacheEligible && cache) {
    try {
      cacheKey = new Request(upstreamUrl.toString(), { method: "GET" });
      const hit = await cache.match(cacheKey);
      if (hit) {
        const h = new Headers(hit.headers);
        for (const k in CORS_HEADERS) h.set(k, CORS_HEADERS[k]);
        h.set("X-VTV-Cache", "HIT");
        return new Response(hit.body, { status: hit.status, headers: h });
      }
    } catch (e) { cacheKey = null; }   // unsupported/miss → fall through to origin
  }

  // Forward only the headers a media relay legitimately needs.
  const fwdHeaders = new Headers();
  const range = request.headers.get("Range");
  if (range) fwdHeaders.set("Range", range);
  // Some sources gate playback on the exact Referer/User-Agent their own embed
  // player uses (declared per-channel in the M3U as http-referrer/http-user-agent
  // — see parseM3U). Only trust these when they were already validated as a safe
  // http(s) URL / sanitized text at parse time.
  const refParam = url.searchParams.get("referer");
  if (refParam && _isSafeStreamUrl(refParam)) fwdHeaders.set("Referer", refParam);
  const uaParam = url.searchParams.get("ua");
  fwdHeaders.set("User-Agent", (uaParam && uaParam.trim()) || request.headers.get("User-Agent") || "Mozilla/5.0 (compatible; IPTVConsole/1.0)");
  fwdHeaders.set("Accept", "*/*");

  const upstream = await fetch(upstreamUrl.toString(), {
    method: "GET",
    headers: fwdHeaders,
    redirect: "follow",
  });

  // Rewrite HLS manifests so nested URLs also route back through this proxy.
  const ctype = (upstream.headers.get("Content-Type") || "").toLowerCase();
  const looksManifest =
    ctype.includes("mpegurl") ||
    upstreamUrl.pathname.toLowerCase().endsWith(".m3u8");

  const respHeaders = new Headers(CORS_HEADERS);
  copyHeader(upstream, respHeaders, "Content-Type");
  copyHeader(upstream, respHeaders, "Content-Range");
  copyHeader(upstream, respHeaders, "Accept-Ranges");

  if (looksManifest) {
    // Live manifest — must never be cached (edge or browser).
    const text = await upstream.text();
    const rewritten = rewriteManifest(text, upstreamUrl, url, bearerFrom(request, url), refParam, uaParam);
    respHeaders.set("Content-Type", "application/vnd.apple.mpegurl");
    respHeaders.set("Cache-Control", "no-store");
    respHeaders.set("X-VTV-Cache", "MANIFEST");
    return new Response(rewritten, { status: upstream.status, headers: respHeaders });
  }

  // Immutable media segment (200, non-range, non-key, binary-ish body): stream it
  // to the client AND store a copy at the edge. tee() lets both happen without
  // buffering; the cache write runs in the background (waitUntil).
  const segCacheable = cacheEligible && cacheKey && cache && upstream.status === 200 &&
    !ctype.startsWith("text/") && !ctype.includes("mpegurl");
  if (segCacheable) {
    let a = null, b = null;
    try { [a, b] = upstream.body.tee(); } catch (e) { a = null; b = null; }
    if (a && b) {
      try {
        const cacheHeaders = new Headers(respHeaders);
        cacheHeaders.delete("Set-Cookie");
        cacheHeaders.set("Cache-Control", "public, max-age=" + STREAM_SEG_CACHE_TTL);
        ctx.waitUntil(cache.put(cacheKey, new Response(a, { status: 200, headers: cacheHeaders })).catch(() => {}));
      } catch (e) { /* best-effort cache write */ }
      const outHeaders = new Headers(respHeaders);
      outHeaders.set("Cache-Control", "public, max-age=" + STREAM_SEG_CACHE_TTL);
      outHeaders.set("X-VTV-Cache", "MISS");
      return new Response(b, { status: upstream.status, headers: outHeaders });
    }
  }

  // Keys and anything else: plain relay, honouring the upstream cache policy.
  copyHeader(upstream, respHeaders, "Cache-Control");
  return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
}

function copyHeader(from, to, name) {
  const v = from.headers.get(name);
  if (v) to.set(name, v);
}

/**
 * Rewrite an HLS manifest so every variant/segment/key URL is routed back
 * through /api/stream (preserving CORS and the auth token).
 *
 * Some sources (e.g. JioTV) protect AES-128 key delivery with an Akamai HDNEA
 * edge-auth token (__hdnea__=...) that's only present on the master/variant
 * playlist URL itself — the #EXT-X-KEY URI inside the manifest is bare, so a
 * plain passthrough fetch of the key 403s. Copy that token onto key URIs too.
 */
function rewriteManifest(text, baseUrl, selfUrl, token, referer, userAgent) {
  let selfBase = selfUrl.origin + "/api/stream?token=" + encodeURIComponent(token);
  if (referer) selfBase += "&referer=" + encodeURIComponent(referer);
  if (userAgent) selfBase += "&ua=" + encodeURIComponent(userAgent);
  const hdnea = baseUrl.searchParams.get("__hdnea__");
  const toAbs = (ref) => {
    try { return new URL(ref, baseUrl).toString(); } catch (e) { return ref; }
  };
  const wrap = (ref, isKeyUri) => {
    let abs = toAbs(ref);
    if (isKeyUri && hdnea && abs.indexOf("__hdnea__") === -1) {
      abs += (abs.indexOf("?") === -1 ? "?" : "&") + "__hdnea__=" + encodeURIComponent(hdnea);
    }
    // Tag AES key URIs so the proxy never edge-caches a (rotating) key.
    return selfBase + (isKeyUri ? "&k=key" : "") + "&url=" + encodeURIComponent(abs);
  };

  return text.split("\n").map((line) => {
    const trimmed = line.trim();
    if (!trimmed) return line;
    if (trimmed.startsWith("#")) {
      const isKeyLine = trimmed.startsWith("#EXT-X-KEY") || trimmed.startsWith("#EXT-X-SESSION-KEY");
      return line.replace(/URI="([^"]+)"/g, (m, uri) => 'URI="' + wrap(uri, isKeyLine) + '"');
    }
    return wrap(trimmed, false);
  }).join("\n");
}

/* ----------------------------- M3U parser ----------------------------- */

/* ----------------------------- JioTV metadata restore -----------------------------
 * The Jio playlist the bridge uploads carries the numeric channelCategoryId as
 * group-title and no language at all, so the app's Category/Language filters
 * showed raw numbers / blanks. We restore human names at serve time here — so
 * it is correct for every client regardless of what the bridge stored. */
const JIO_CATEGORY_MAP = {5:"Entertainment",6:"Movies",7:"Kids",8:"Sports",9:"Lifestyle",10:"Infotainment",12:"News",13:"Music",15:"Devotional",16:"Business",17:"Educational",18:"Shopping",19:"JioDarshan"};
const JIO_LANGUAGE_MAP = {1:"Hindi",2:"Marathi",3:"Punjabi",4:"Urdu",5:"Bengali",6:"English",7:"Malayalam",8:"Tamil",9:"Gujarati",10:"Odia",11:"Telugu",12:"Bhojpuri",13:"Kannada",14:"Assamese",15:"Nepali",16:"French",18:"Konkani",21:"Regional"};
// channel_id -> languageId (the M3U has no language); compact "id:lang,...".
const JIO_CHANNEL_LANG_RAW = "1136:1,279:1,1763:1,1393:1,1450:1,1143:1,1961:1,474:1,1296:12,3384:12,173:1,3088:1,3336:1,3535:6,3338:1,2078:1,1403:1,3069:12,235:1,1780:6,3383:1,3467:1,672:5,2424:2,1633:13,417:8,1956:10,1957:10,1452:2,3385:1,2764:1,698:5,1209:8,175:1,2229:12,1251:1,617:2,250:1,619:13,591:1,707:8,504:1,231:1,2252:1,741:12,177:1,677:8,773:13,3083:21,1669:5,142:6,143:6,144:1,146:6,151:6,153:2,154:1,155:6,156:1,162:6,164:6,165:1,166:11,167:1,180:7,182:1,183:1,185:1,190:1,193:6,196:9,202:1,203:1,204:1,212:6,232:2,242:6,248:1,252:11,255:6,258:1,259:6,286:6,288:1,289:1,290:8,291:1,317:5,336:2,368:8,370:13,383:6,400:6,401:6,402:6,403:6,404:6,405:6,406:6,407:6,408:6,409:6,410:6,411:6,412:6,413:11,414:2,415:1,418:8,419:8,420:8,421:6,422:2,429:8,440:1,441:2,442:2,443:7,445:2,457:5,459:7,462:6,463:6,464:5,465:7,466:1,471:1,472:1,473:1,476:1,477:6,478:6,479:6,481:1,482:1,483:1,484:1,486:12,487:1,488:1,489:6,490:9,491:6,492:6,493:6,494:6,495:6,496:6,498:1,499:1,501:1,502:1,503:1,510:1,511:1,512:1,513:1,514:6,515:1,516:1,517:3,518:1,519:1,520:1,522:1,523:6,524:1,525:6,527:1,528:1,529:1,530:1,531:1,533:2,536:1,538:1,539:1,540:1,541:6,542:8,543:11,544:6,545:1,546:8,548:1,550:8,551:6,554:1,555:13,556:7,557:8,558:11,559:1,560:6,561:1,562:1,563:7,565:11,566:1,567:6,568:6,569:8,570:11,571:1,572:1,573:5,574:6,575:1,576:11,577:11,578:1,579:8,580:1,583:1,585:1,587:1,592:1,593:1,594:1,595:10,596:1,597:1,598:11,599:1,601:1,602:1,603:8,605:4,606:7,607:11,608:1,609:3,611:1,612:2,613:14,614:11,615:8,616:9,618:11,620:9,623:14,624:14,625:5,626:13,627:14,628:8,629:11,630:11,631:10,632:11,633:14,634:7,635:14,636:8,637:14,638:11,639:14,641:9,642:9,643:9,646:11,647:14,648:7,650:7,651:13,652:1,653:13,654:3,655:1,656:6,657:1,658:1,659:1,661:12,662:7,664:11,665:11,666:11,667:11,668:11,670:11,671:8,673:8,675:14,676:8,678:13,682:8,683:8,684:11,685:5,686:10,687:5,689:13,690:5,691:2,692:11,693:12,694:4,695:2,696:10,697:5,699:7,701:1,702:10,703:10,704:10,705:8,706:11,708:8,709:8,710:7,712:4,713:13,714:9,715:3,716:4,717:5,718:10,719:15,722:10,723:7,724:1,725:7,726:8,727:8,728:4,729:11,731:7,732:3,733:13,734:11,735:2,737:11,738:2,739:7,740:5,742:3,743:13,744:13,747:7,748:8,751:10,755:2,756:5,757:13,760:11,762:6,764:6,765:14,767:8,768:1,769:11,770:1,771:1,772:11,774:11,775:11,776:11,777:11,778:13,779:10,780:7,781:10,782:9,783:1,784:11,785:13,786:7,787:6,788:1,789:1,790:11,791:1,792:1,794:1,795:1,796:8,801:1,803:8,804:1,807:4,808:1,809:1,810:7,814:8,815:1,816:1,817:8,821:1,823:6,824:8,826:8,828:1,829:13,830:8,831:1,832:11,835:8,837:6,838:16,842:7,843:8,844:7,846:1,850:1,851:1,852:6,853:8,854:11,855:1,856:1,857:8,858:6,866:6,871:1,872:1,873:8,874:11,875:6,876:6,877:6,879:1,880:1,882:1,883:12,885:6,886:9,887:1,890:6,891:6,892:1,894:8,895:8,896:8,897:11,898:11,899:11,900:7,901:13,903:3,904:3,906:3,907:6,908:5,910:7,915:1,916:1,918:1,919:1,921:1,923:13,924:4,927:1,929:9,931:1,933:4,934:11,936:1,937:8,939:1,944:9,946:3,950:5,951:1,952:3,953:7,955:11,956:13,957:1,958:1,959:3,960:1,961:3,962:1,963:1,964:1,965:7,970:8,971:8,972:1,975:1,977:11,978:1,979:1,980:6,981:6,982:6,983:6,984:6,985:6,986:6,987:6,988:6,989:6,990:6,991:6,992:6,993:6,994:6,995:6,996:6,997:6,998:6,999:6,1059:1,1061:6,1069:9,1070:9,1071:9,1075:13,1077:1,1078:1,1079:6,1080:11,1081:8,1082:9,1083:9,1084:9,1085:9,1086:9,1087:9,1088:9,1089:9,1090:9,1091:9,1092:9,1093:9,1094:9,1102:6,1103:1,1104:6,1110:6,1112:11,1113:1,1129:11,1132:1,1137:11,1139:7,1140:13,1145:1,1146:2,1148:6,1158:6,1159:2,1163:6,1170:3,1171:3,1172:3,1174:3,1175:1,1179:1,1185:1,1186:9,1187:9,1189:3,1190:3,1191:3,1192:3,1193:1,1205:1,1210:8,1212:1,1219:8,1220:1,1221:13,1223:2,1224:1,1226:6,1227:9,1228:2,1229:11,1230:3,1232:6,1240:6,1241:6,1242:11,1243:13,1244:13,1246:5,1250:7,1252:4,1254:11,1255:9,1256:13,1257:1,1260:5,1261:5,1263:1,1264:5,1265:3,1273:2,1274:11,1278:1,1284:7,1286:1,1287:1,1291:3,1293:2,1294:6,1295:1,1315:6,1319:6,1322:6,1324:9,1325:6,1326:2,1328:1,1329:1,1332:6,1335:6,1338:6,1340:7,1341:5,1342:2,1344:7,1345:5,1346:2,1351:1,1354:11,1355:4,1356:8,1358:2,1359:1,1360:2,1362:13,1363:11,1364:6,1368:1,1369:5,1370:13,1371:8,1373:1,1374:6,1375:6,1388:7,1391:1,1392:1,1394:2,1396:1,1401:6,1405:6,1407:1,1408:7,1410:6,1411:1,1414:1,1415:1,1417:8,1418:1,1426:1,1427:10,1429:7,1431:1,1433:6,1440:1,1451:1,1453:3,1454:9,1455:7,1457:3,1458:3,1471:6,1475:1,1476:1,1477:1,1481:10,1494:5,1514:7,1515:8,1516:11,1518:8,1521:6,1525:1,1527:3,1528:1,1531:1,1532:6,1537:8,1538:1,1543:1,1545:3,1549:1,1550:1,1551:1,1552:7,1553:1,1554:1,1555:13,1560:1,1561:5,1568:1,1594:1,1598:6,1605:5,1607:1,1608:1,1610:9,1612:5,1618:7,1632:13,1634:13,1635:1,1641:7,1643:7,1644:7,1647:8,1655:8,1657:5,1662:7,1665:11,1666:7,1667:5,1668:1,1670:1,1690:7,1691:1,1692:10,1695:1,1697:1,1698:1,1699:4,1705:2,1706:2,1725:5,1728:1,1733:14,1735:5,1736:6,1738:8,1740:5,1741:1,1742:1,1743:6,1746:13,1747:9,1751:3,1754:7,1757:14,1759:9,1761:1,1762:5,1764:1,1771:5,1772:8,1773:11,1774:8,1775:11,1777:1,1788:1,1789:9,1790:9,1793:1,1794:1,1795:1,1796:5,1797:1,1798:12,1799:11,1804:1,1817:1,1826:6,1834:1,1839:1,1847:1,1850:8,1853:1,1854:1,1855:6,1856:14,1858:8,1859:8,1868:3,1871:3,1883:11,1885:1,1886:1,1891:5,1895:1,1896:1,1897:1,1900:1,1901:1,1906:1,1907:1,1925:12,1954:8,1955:1,1958:10,1959:1,1962:5,1964:1,1965:1,1967:1,1972:2,1973:11,1974:9,1975:11,1976:6,1977:5,1984:1,1985:1,1998:1,1999:1,2001:1,2002:9,2003:6,2004:7,2005:1,2007:9,2008:1,2014:1,2017:4,2018:1,2019:3,2020:1,2021:1,2022:14,2024:1,2027:5,2028:9,2029:1,2030:1,2031:6,2064:1,2077:1,2079:1,2081:1,2082:1,2176:1,2184:5,2187:11,2188:5,2189:1,2224:3,2225:1,2228:5,2230:6,2254:1,2255:1,2256:8,2258:6,2322:1,2323:1,2325:3,2326:6,2327:1,2328:6,2352:1,2353:1,2354:5,2423:1,2433:1,2434:8,2435:14,2436:11,2437:6,2742:13,2743:13,2750:3,2751:1,2752:3,2753:1,2754:3,2757:6,2759:14,2761:1,2765:1,2766:6,2767:1,2768:8,2770:1,2771:1,2772:1,2773:1,2774:1,2775:6,2777:1,2778:3,2779:6,2780:5,2782:6,2783:11,2784:1,2832:1,2834:1,2835:1,2851:1,2852:11,2853:8,2854:6,2862:11,2914:5,2916:3,2917:9,2918:3,2932:11,2933:5,2934:3,2935:2,2936:1,2937:1,2945:1,2946:1,2947:1,2954:1,2956:11,2957:1,2958:8,2962:1,3004:8,3005:5,3006:5,3007:1,3008:5,3011:6,3014:1,3016:1,3017:1,3018:11,3019:5,3022:1,3023:9,3024:1,3025:1,3026:1,3028:1,3029:1,3031:11,3032:13,3033:7,3034:2,3035:13,3036:7,3037:9,3038:1,3039:1,3040:7,3042:1,3043:3,3045:8,3046:6,3047:13,3048:1,3049:1,3050:1,3051:8,3053:1,3058:9,3059:8,3060:1,3063:1,3064:1,3065:1,3066:1,3068:1,3070:1,3074:1,3075:1,3084:6,3086:1,3087:11,3090:1,3091:6,3092:6,3093:6,3094:6,3095:2,3096:1,3097:1,3098:1,3100:2,3104:1,3105:1,3107:13,3108:9,3110:1,3111:1,3112:1,3113:1,3115:10,3117:1,3118:6,3119:6,3120:6,3121:6,3122:6,3123:6,3124:6,3125:6,3126:6,3127:6,3128:6,3129:6,3130:6,3131:6,3132:6,3133:6,3134:6,3135:6,3136:6,3137:6,3138:6,3139:6,3140:6,3141:6,3142:6,3143:11,3145:6,3146:6,3147:6,3152:3,3154:6,3155:6,3162:1,3163:1,3164:1,3166:1,3167:2,3168:1,3170:2,3171:1,3172:1,3174:7,3175:8,3176:11,3177:1,3178:1,3179:2,3181:1,3182:11,3183:11,3184:7,3185:5,3186:1,3187:1,3188:1,3189:1,3190:1,3191:1,3192:1,3194:4,3197:9,3201:8,3203:1,3204:6,3205:1,3206:13,3207:8,3208:11,3209:2,3210:5,3211:9,3212:7,3213:6,3214:1,3216:1,3217:14,3218:1,3219:1,3220:1,3221:8,3223:1,3226:1,3227:1,3230:1,3231:12,3232:6,3234:1,3235:1,3236:1,3237:13,3238:6,3239:11,3240:6,3242:1,3243:6,3244:1,3246:7,3247:6,3248:6,3249:6,3250:6,3251:6,3252:6,3253:3,3255:1,3258:1,3259:1,3260:1,3261:1,3262:7,3263:1,3264:8,3265:1,3266:8,3267:10,3268:14,3269:8,3279:8,3280:1,3281:12,3282:12,3284:3,3285:1,3286:6,3287:6,3288:6,3289:6,3290:6,3291:1,3292:1,3294:1,3295:1,3297:5,3298:5,3299:1,3300:8,3302:11,3304:11,3310:1,3312:9,3313:6,3314:9,3317:5,3319:5,3320:5,3321:5,3322:5,3323:6,3324:6,3325:6,3327:6,3328:1,3329:1,3330:1,3331:5,3332:1,3333:3,3334:1,3343:1,3345:1,3346:6,3352:13,3353:14,3354:3,3356:8,3357:8,3358:8,3359:8,3360:8,3361:1,3365:9,3367:11,3368:1,3369:9,3370:11,3372:6,3373:6,3374:6,3378:1,3379:5,3380:9,3381:8,3382:1,3389:6,3392:6,3393:8,3394:8,3395:8,3396:8,3397:8,3398:11,3399:6,3401:1,3402:6,3405:9,3406:11,3409:8,3417:8,3418:1,3420:13,3423:7,3424:5,3425:7,3427:1,3428:5,3429:13,3430:8,3431:7,3432:13,3433:13,3434:1,3435:6,3436:1,3438:1,3439:5,3440:6,3443:5,3444:1,3445:8,3446:11,3447:11,3448:7,3450:8,3451:1,3452:6,3453:1,3454:2,3455:13,3456:7,3457:2,3458:1,3459:1,3460:1,3461:13,3462:1,3463:2,3464:13,3469:1,3470:3,3471:3,3473:1,3476:5,3478:6,3479:6,3481:6,3483:1,3484:1,3485:1,3486:1,3490:3,3492:1,3493:9,3497:8,3498:1,3499:6,3502:1,3504:13,3505:1,3507:1,3508:9,3509:1,3510:6,3511:6,3512:1,3513:11,3514:8,3515:6,3518:5,3519:1,3524:6,3528:13,3529:11,3530:6,3531:8,3532:1,3533:1,3534:1,3536:2,3537:6,3538:5,3540:16,3541:16,3542:16,3543:1,3544:1,3546:6,3548:13,3549:1,3550:8,3551:9,3552:2,3553:6,3554:1,3555:3,3556:3,3557:1,3558:11,3559:11,3560:11,3561:11,3562:5,3563:1,3564:1,3565:7,3566:3";
let _jioLangMap = null;
function _jioLangId(id){
  if(!_jioLangMap){ _jioLangMap=Object.create(null); for(const p of JIO_CHANNEL_LANG_RAW.split(",")){ const i=p.indexOf(":"); if(i>0) _jioLangMap[p.slice(0,i)]=p.slice(i+1); } }
  return _jioLangMap[String(id)];
}
/** Rewrite parsed Jio channels: numeric category -> name, restore language. */
function applyJioMeta(channels){
  for(const c of channels){
    if(c.category && /^\d+$/.test(c.category)){ const n=JIO_CATEGORY_MAP[parseInt(c.category,10)]; if(n) c.category=n; }
    if(!c.language){ const lid=_jioLangId(c.id); if(lid!=null){ const ln=JIO_LANGUAGE_MAP[parseInt(lid,10)]; if(ln) c.language=ln; } }
  }
  return channels;
}

function parseM3U(raw) {
  const lines = raw.split(/\r?\n/);
  const channels = [];
  let cur = null;

  for (let i = 0; i < lines.length; i++) {
    if (channels.length >= MAX_CHANNELS_PER_PLAYLIST) break;
    const line = lines[i].trim();
    if (!line) continue;

    if (line.startsWith("#EXTINF")) {
      cur = {
        name: extractTitle(line),
        id: attr(line, "tvg-id") || "",
        logo: attr(line, "tvg-logo") || attr(line, "logo") || "",
        category: attr(line, "group-title") || "General",
        language: attr(line, "tvg-language") || attr(line, "language") || "",
        quality: guessQuality(line),
        // Some sources gate playback on these (checked at the CDN edge), e.g.
        // Asianet-family streams require the exact Referer their embed page uses.
        referer: attr(line, "http-referrer") || attr(line, "tvg-referrer") || "",
        userAgent: attr(line, "http-user-agent") || "",
        url: "",
      };
    } else if (line.startsWith("#EXTGRP") && cur) {
      cur.category = line.split(":")[1] ? line.split(":")[1].trim() : cur.category;
    } else if (line.startsWith("#EXTVLCOPT") && cur) {
      // #EXTVLCOPT:http-referrer=... / #EXTVLCOPT:http-user-agent=... (VLC-style
      // per-entry playback options some sources use instead of/alongside tvg attrs)
      const refM = line.match(/#EXTVLCOPT:\s*http-referrer\s*=\s*(.+)/i);
      if (refM && !cur.referer) cur.referer = refM[1].trim();
      const uaM = line.match(/#EXTVLCOPT:\s*http-user-agent\s*=\s*(.+)/i);
      if (uaM && !cur.userAgent) cur.userAgent = uaM[1].trim();
    } else if (!line.startsWith("#")) {
      if (cur) {
        cur.url = line.trim();
        // SECURITY: only expose channels with a safe http(s), non-internal stream
        // URL; sanitize every text field; drop unsafe logo URLs.
        if (_isSafeStreamUrl(cur.url)) {
          cur.name = _sanitizeText(cur.name, 180) || "Unknown channel";
          cur.id = _sanitizeText(cur.id, 120);
          cur.category = _sanitizeText(cur.category, 80) || "General";
          cur.language = _sanitizeText(cur.language, 60);
          cur.logo = _isSafeStreamUrl(cur.logo) ? cur.logo : "";
          cur.referer = _isSafeStreamUrl(cur.referer) ? cur.referer : "";
          cur.userAgent = _sanitizeText(cur.userAgent, 300);
          channels.push(cur);
        }
        cur = null;
      }
    }
  }
  return channels;
}

function attr(line, key) {
  const m = line.match(new RegExp(key + '="([^"]*)"', "i"));
  return m ? m[1] : "";
}
function extractTitle(line) {
  const idx = line.lastIndexOf(",");
  const name = idx !== -1 ? line.slice(idx + 1).trim() : "";
  return name || attr(line, "tvg-name") || "Unknown channel";
}
function guessQuality(line) {
  const hay = line.toLowerCase();
  if (/\bfhd\b|\bhd\b|1080|720|high/.test(hay)) return "HD";
  return "SD";
}

/* ----------------------------- EPG (XMLTV) parser ----------------------------- */

/** Parse "20240131123000 +0000" / "20240131123000" into epoch ms. */
function parseXmltvTime(s) {
  if (!s) return NaN;
  const m = s.match(/^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})?\s*([+-]\d{4})?/);
  if (!m) return NaN;
  const [, y, mo, d, h, mi, se, tz] = m;
  let iso = `${y}-${mo}-${d}T${h}:${mi}:${se || "00"}`;
  if (tz) iso += tz.slice(0, 3) + ":" + tz.slice(3);
  else iso += "Z";
  const t = Date.parse(iso);
  return isNaN(t) ? NaN : t;
}

function _xmlUnescape(s) {
  return String(s == null ? "" : s)
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

/** Normalize a channel/program name for fuzzy matching: strip quality tags,
 *  parentheticals and punctuation so "Asianet (576p)" ~= "Asianet HD" ~= "asianet". */
function _normEpgName(name) {
  return String(name || "").toLowerCase()
    .replace(/\([^)]*\)/g, " ").replace(/\[[^\]]*\]/g, " ")
    .replace(/\b(fhd|uhd|hd|sd|4k|8k|hevc|h\.?26[45]|2160p?|1080p?|720p?|576p?|480p?|360p?|240p?)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

/**
 * When a playlist's tvg-id doesn't exist as a <programme channel="..."> id in the
 * guide (common — aggregated M3U lists and third-party XMLTV guides rarely share
 * an id scheme), fall back to matching by the human channel name against the
 * guide's own <channel id="X"><display-name>Name</display-name></channel> map.
 * Returns the guide's internal channel id, or "" if nothing looked close enough.
 */
function _findEpgChannelIdByName(xml, targetName) {
  const norm = _normEpgName(targetName);
  if (!norm) return "";
  const re = /<channel\b[^>]*\bid="([^"]*)"[^>]*>([\s\S]*?)<\/channel>/g;
  let m, scanned = 0, candidate = "";
  while ((m = re.exec(xml)) !== null) {
    if (++scanned > 20000) break; // channel list is short vs. programmes; generous cap
    const id = m[1];
    const inner = m[2];
    const nameMatches = inner.match(/<display-name[^>]*>([\s\S]*?)<\/display-name>/gi) || [];
    for (const raw of nameMatches) {
      const text = raw.replace(/^<display-name[^>]*>/i, "").replace(/<\/display-name>$/i, "");
      const n2 = _normEpgName(_xmlUnescape(text));
      if (!n2) continue;
      if (n2 === norm) return id; // exact normalized match — best possible, stop now
      if (!candidate && norm.length > 2 && (n2.indexOf(norm) !== -1 || norm.indexOf(n2) !== -1)) candidate = id;
    }
  }
  return candidate;
}

/**
 * Extract <programme channel="ID"> entries for one channel from XMLTV text.
 * Streaming-ish regex scan (no full DOM) to stay light in the Worker.
 */
function parseEpgForChannel(xml, channelId) {
  const out = [];
  if (!xml || !channelId) return out;
  // Match each <programme ...>...</programme> block.
  const re = /<programme\b([^>]*)>([\s\S]*?)<\/programme>/g;
  const idLc = channelId.toLowerCase();
  let m;
  let scanned = 0;
  while ((m = re.exec(xml)) !== null) {
    if (++scanned > 200000) break; // hard safety cap
    const attrs = m[1];
    const chMatch = attrs.match(/channel="([^"]*)"/i);
    if (!chMatch || chMatch[1].toLowerCase() !== idLc) continue;
    const startMatch = attrs.match(/start="([^"]*)"/i);
    const stopMatch = attrs.match(/stop="([^"]*)"/i);
    const startMs = parseXmltvTime(startMatch ? startMatch[1] : "");
    const stopMs = parseXmltvTime(stopMatch ? stopMatch[1] : "");
    const inner = m[2];
    const titleM = inner.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const descM = inner.match(/<desc[^>]*>([\s\S]*?)<\/desc>/i);
    out.push({
      startMs: startMs || 0,
      stopMs: stopMs || 0,
      start: startMatch ? startMatch[1] : "",
      stop: stopMatch ? stopMatch[1] : "",
      title: _xmlUnescape(titleM ? titleM[1].trim() : "Untitled"),
      desc: _xmlUnescape(descM ? descM[1].trim() : ""),
    });
    if (out.length > 400) break;
  }
  out.sort((a, b) => a.startMs - b.startMs);
  return out;
}

/**
 * Parse EVERY <programme> entry for EVERY channel in an XMLTV file (used by
 * the D1 sync job, unlike parseEpgForChannel which filters to one channel).
 * Capped to stay within Worker CPU/memory limits for very large guides.
 */
function parseEpgAll(xml) {
  const out = [];
  if (!xml) return out;
  const re = /<programme\b([^>]*)>([\s\S]*?)<\/programme>/g;
  let m, scanned = 0;
  while ((m = re.exec(xml)) !== null) {
    if (++scanned > 200000) break;
    if (out.length >= 20000) break; // per-source storage cap
    const attrs = m[1];
    const chMatch = attrs.match(/channel="([^"]*)"/i);
    if (!chMatch || !chMatch[1]) continue;
    const startMatch = attrs.match(/start="([^"]*)"/i);
    const stopMatch = attrs.match(/stop="([^"]*)"/i);
    const startMs = parseXmltvTime(startMatch ? startMatch[1] : "");
    const stopMs = parseXmltvTime(stopMatch ? stopMatch[1] : "");
    if (!startMs || !stopMs) continue;
    const inner = m[2];
    const titleM = inner.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const descM = inner.match(/<desc[^>]*>([\s\S]*?)<\/desc>/i);
    out.push({
      tvgId: chMatch[1],
      title: _sanitizeText(_xmlUnescape(titleM ? titleM[1].trim() : "Untitled"), 300) || "Untitled",
      desc: _sanitizeText(_xmlUnescape(descM ? descM[1].trim() : ""), 2000),
      startMs,
      stopMs,
    });
  }
  return out;
}

/* ----------------------------- D1 sync (streams_metadata / epg_data) -----------------------------
 * Populates D1 as a real queryable channel/EPG database, in PARALLEL with the existing
 * live-fetch + R2-cache path — the live /api/playlist and /api/epg routes are untouched
 * and keep serving from that proven path. This is additive: D1 is not yet a read
 * dependency for anything user-facing, so a sync bug can't break live playback.
 *
 * A full sync of ~150+ sources won't fit in one Cron Trigger invocation, so progress is
 * tracked via sync_state (a cursor) and a slice of providers is processed per tick.
 */
const D1_SYNC_BATCH_SIZE = 8;   // providers processed per cron tick / manual trigger call
const D1_TIME_BUDGET_MS = 20000; // bail early if a tick is taking too long

function _runD1Batch(env, stmts) {
  // D1 batch() has practical payload/statement-count limits; chunk defensively.
  const chunks = [];
  for (let i = 0; i < stmts.length; i += 400) chunks.push(stmts.slice(i, i + 400));
  return chunks.reduce((p, chunk) => p.then(() => env.DB.batch(chunk)), Promise.resolve());
}

async function syncProviderToD1(env, providerId, pconf) {
  const raw = await loadProviderRaw(env, providerId, pconf);
  if (!raw) return 0;
  const channels = parseM3U(raw);
  if (!channels.length) return 0;
  const now = Date.now();
  const stmt = env.DB.prepare(
    "INSERT OR REPLACE INTO streams_metadata (id,name,category,language,country,source_id,logo_url,stream_url,tvg_id,quality,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
  );
  const stmts = channels.map((ch) =>
    stmt.bind(providerId + "|" + _shortHash(ch.url), ch.name, ch.category || null, ch.language || null, null, providerId, ch.logo || null, ch.url, ch.id || null, ch.quality || null, now)
  );
  await _runD1Batch(env, stmts);
  return channels.length;
}

async function syncEpgToD1(env, providerId, epgUrl) {
  if (!epgUrl && providerId !== 'jio') return 0;
  const cacheKey = "cache_epg_" + providerId;
  let xml = await cacheGet(env, cacheKey);
  
  if (!xml && providerId === 'jio') {
      xml = await cacheGet(env, 'jio_epg');
  }
  
  if (!xml && epgUrl) {
    try {
      const resp = await fetch(epgUrl, { headers: { "User-Agent": "Mozilla/5.0 (compatible; IPTVConsole/1.0)" }, redirect: "follow" });
      if (resp.ok) {
        xml = await resp.text();
        if (xml && xml.length < 24 * 1024 * 1024) await cachePut(env, cacheKey, xml, EPG_CACHE_TTL);
      }
    } catch (e) { return 0; }
  }
  if (!xml) return 0;
  const programs = parseEpgAll(xml);
  if (!programs.length) return 0;
  // Full replace per source — simpler and safer than diffing a time-series guide.
  const del = env.DB.prepare("DELETE FROM epg_data WHERE source_id = ?").bind(providerId);
  const stmt = env.DB.prepare("INSERT INTO epg_data (source_id,tvg_id,title,description,start_time,end_time) VALUES (?,?,?,?,?,?)");
  const stmts = [del, ...programs.map((p) => stmt.bind(providerId, p.tvgId, p.title, p.desc || null, p.startMs, p.stopMs))];
  await _runD1Batch(env, stmts);
  return programs.length;
}

/** Process the next slice of providers, advancing a persisted cursor so a full
 *  cycle completes over many ticks instead of one (which wouldn't fit the
 *  execution time budget). Returns a summary for logging/manual-trigger responses. */
async function runD1Sync(env) {
  if (!env.DB) return { error: "D1 not bound" };
  const settings = await loadSettings(env);
  const ids = Object.keys(settings.providers).filter((id) => id !== CUSTOM_PROVIDER_ID && settings.providers[id].enabled !== false);
  if (!ids.length) return { processed: 0, total: 0 };

  let cursor = 0;
  try {
    const row = await env.DB.prepare("SELECT value FROM sync_state WHERE key = 'cursor'").first();
    cursor = row ? (parseInt(row.value, 10) || 0) : 0;
  } catch (e) {}

  const started = Date.now();
  const results = [];
  let i = cursor;
  let count = 0;
  while (count < D1_SYNC_BATCH_SIZE && (Date.now() - started) < D1_TIME_BUDGET_MS) {
    const id = ids[i % ids.length];
    const pconf = settings.providers[id];
    try {
      const [channelCount, epgCount] = await Promise.all([
        syncProviderToD1(env, id, pconf),
        syncEpgToD1(env, id, pconf.epg),
      ]);
      results.push({ id, channels: channelCount, programs: epgCount });
    } catch (e) {
      results.push({ id, error: String(e && e.message || e) });
    }
    i++; count++;
    if (i >= ids.length * 2) break; // safety: never loop forever on a tiny/empty list
  }

  try {
    await env.DB.prepare("INSERT OR REPLACE INTO sync_state (key, value, updated_at) VALUES ('cursor', ?, ?)")
      .bind(String(i % ids.length), Date.now()).run();
  } catch (e) {}

  return { processed: results.length, total: ids.length, cursorNext: i % ids.length, results };
}
