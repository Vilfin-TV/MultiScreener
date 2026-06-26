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

// All providers the console understands. free/pro ship with working open-source
// defaults; jio/airtel/custom are URL-driven (set in the admin console).
const IPTV_PROVIDERS = ["jio", "airtel", "free", "pro", "custom"];

const IPTV_PROVIDER_DEFAULTS = {
  jio:    { enabled: true, url: "", epg: "" },
  airtel: { enabled: true, url: "", epg: "" },
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
  "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
  "Access-Control-Max-Age": "86400",
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const { pathname } = url;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

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
      if (request.method === "GET" && pathname === "/api/playlist") {
        return handlePlaylist(request, env, url);
      }
      if (request.method === "GET" && pathname === "/api/epg") {
        return handleEpg(request, env, url);
      }
      if (request.method === "GET" && pathname === "/api/stream") {
        return handleStream(request, env, url);
      }
      return json({ error: "Not found" }, 404);
    } catch (err) {
      return json({ error: "Server error", detail: String(err && err.message || err) }, 500);
    }
  },
};

/* ----------------------------- helpers ----------------------------- */

function json(obj, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS_HEADERS, ...extraHeaders },
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
    if (a === 192 && b === 168) return true;
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
  const raw = await kv.get("iptv_settings");
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
      language: "", quality: guessQuality(String(c && c.name || "")), url: url, source: "My Channels",
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
      const r = await env.IPTV_PLAYLIST_KV.get('iptv_sessions_revoked');
      const revoked = r ? JSON.parse(r) : {};
      if (revoked[payload.jti]) return null;
    } catch (e) {}
  }
  if (env.IPTV_PLAYLIST_KV && payload.sub) {
    try {
      const rawAuth = await env.IPTV_PLAYLIST_KV.get('iptv_auth');
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
    const raw = await kv.get("iptv_auth");
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
          await env.IPTV_PLAYLIST_KV.put("iptv_auth", JSON.stringify(authObj));

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

/** Fetch the raw M3U text for one provider id (remote URL w/ KV cache, then
 *  synced {id}_playlist fallback). Returns "" when nothing is available. */
async function loadProviderRaw(env, providerId, pconf) {
  const kv = env.IPTV_PLAYLIST_KV;
  if (!kv) return "";
  let raw = "";
  const srcUrl = (pconf && pconf.url || "").trim();
  if (srcUrl) {
    const cacheKey = "cache_playlist_" + providerId;
    raw = (await kv.get(cacheKey)) || "";
    if (!raw) {
      try {
        const resp = await fetch(srcUrl, { headers: { "User-Agent": "Mozilla/5.0 (compatible; IPTVConsole/1.0)" }, redirect: "follow" });
        if (resp.ok) {
          raw = await resp.text();
          if (raw && raw.length < 24 * 1024 * 1024) {
            try { await kv.put(cacheKey, raw, { expirationTtl: PLAYLIST_CACHE_TTL }); } catch (e) {}
          }
        }
      } catch (e) {
        console.warn("Failed to fetch playlist URL for " + providerId + ": " + e);
      }
    }
  }
  if (!raw) raw = (await kv.get(providerId + "_playlist")) || "";
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
  const kv = env.IPTV_PLAYLIST_KV;

  const members = Object.keys(settings.providers)
    .map((id) => Object.assign({ id }, settings.providers[id]))
    .filter((p) => p.enabled !== false && String(p.region || "").trim() === region);
  if (!members.length) return json({ error: "No sources in this region" }, 404);

  const cacheKey = "cache_region_" + region;
  if (kv) {
    const cached = await kv.get(cacheKey);
    if (cached) {
      try { const obj = JSON.parse(cached); return json(obj); } catch (e) {}
    }
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
  if (kv && channels.length) {
    try { await kv.put(cacheKey, JSON.stringify(out), { expirationTtl: REGION_CACHE_TTL }); } catch (e) {}
  }
  return json(out);
}

const MERGE_MAX_SOURCES = 60;
const MERGE_MAX_CHANNELS = 15000;
function _shortHash(s) { let h = 0; for (let i = 0; i < s.length; i++) { h = ((h << 5) - h + s.charCodeAt(i)) | 0; } return (h >>> 0).toString(36); }

/** ?providers=a,b,c  or  ?all=1 — merge the selected sources into one list.
 *  Duplicate m3u URLs are removed at the source level (so the same playlist is
 *  never fetched/listed twice). Channels are kept even when names repeat across
 *  different sources (only EXACT same stream URL is de-duplicated); each channel
 *  is tagged with `source`. Fetches run in parallel and the merge is cached. */
async function handleMergePlaylist(request, env, url) {
  const settings = await loadSettings(env);
  const kv = env.IPTV_PLAYLIST_KV;
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
  if (kv) {
    const cached = await kv.get(cacheKey);
    if (cached) { try { const o = JSON.parse(cached); channels = o.channels; used = o.sources || 0; } catch (e) {} }
  }
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
        const key = ch.url;
        if (!key || seenStream[key]) continue; // drop only EXACT same stream
        seenStream[key] = 1;
        ch.source = members[i].name || members[i].id;
        channels.push(ch);
        if (channels.length >= MERGE_MAX_CHANNELS) break;
      }
      if (channels.length >= MERGE_MAX_CHANNELS) break;
    }
    if (kv && channels.length) { try { await kv.put(cacheKey, JSON.stringify({ channels, sources: used }), { expirationTtl: REGION_CACHE_TTL }); } catch (e) {} }
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
 * GET /api/epg?provider=<p>&channel=<tvg-id>
 * Returns { now, next, programs:[{start,stop,title,desc}] } — never the whole guide.
 */
async function handleEpg(request, env, url) {
  const auth = await requireAuth(request, env, url);
  if (!auth) return json({ error: "Unauthorized" }, 401);

  const provider = (url.searchParams.get("provider") || "").toLowerCase();
  const channel = (url.searchParams.get("channel") || "").trim();
  const settings = await loadSettings(env);
  if (!settings.providers[provider]) return json({ error: "Invalid provider" }, 400);
  if (!channel) return json({ error: "Missing channel id" }, 400);
  const epgUrl = ((settings.providers[provider] || {}).epg || "").trim();
  if (!epgUrl) return json({ programs: [], now: null, next: null, note: "No EPG configured" });

  const kv = env.IPTV_PLAYLIST_KV;
  const cacheKey = "cache_epg_" + provider;
  let xml = kv ? (await kv.get(cacheKey)) || "" : "";
  if (!xml) {
    try {
      const resp = await fetch(epgUrl, { headers: { "User-Agent": "Mozilla/5.0 (compatible; IPTVConsole/1.0)" }, redirect: "follow" });
      if (resp.ok) {
        xml = await resp.text();
        if (kv && xml && xml.length < 24 * 1024 * 1024) {
          try { await kv.put(cacheKey, xml, { expirationTtl: EPG_CACHE_TTL }); } catch (e) {}
        }
      }
    } catch (e) {
      return json({ programs: [], now: null, next: null, error: "EPG fetch failed" });
    }
  }
  if (!xml) return json({ programs: [], now: null, next: null, error: "EPG unavailable" });

  const programs = parseEpgForChannel(xml, channel);
  const nowMs = Date.now();
  let now = null, next = null;
  for (let i = 0; i < programs.length; i++) {
    const p = programs[i];
    if (p.startMs <= nowMs && nowMs < p.stopMs) { now = p; next = programs[i + 1] || null; break; }
    if (p.startMs > nowMs) { next = p; break; }
  }
  return json({ channel, count: programs.length, now, next, programs: programs.slice(0, 12) });
}

/**
 * Generic CORS-safe relay. Forwards Range, relays Content-Type/Range, adds CORS.
 * Does NOT spoof any provider's mobile-app identity.
 */
async function handleStream(request, env, url) {
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

  // Forward only the headers a media relay legitimately needs.
  const fwdHeaders = new Headers();
  const range = request.headers.get("Range");
  if (range) fwdHeaders.set("Range", range);
  // Normal browser identity — no provider impersonation.
  fwdHeaders.set("User-Agent", request.headers.get("User-Agent") || "Mozilla/5.0 (compatible; IPTVConsole/1.0)");
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
  copyHeader(upstream, respHeaders, "Cache-Control");

  if (looksManifest) {
    const text = await upstream.text();
    const rewritten = rewriteManifest(text, upstreamUrl, url, bearerFrom(request, url));
    respHeaders.set("Content-Type", "application/vnd.apple.mpegurl");
    return new Response(rewritten, { status: upstream.status, headers: respHeaders });
  }

  return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
}

function copyHeader(from, to, name) {
  const v = from.headers.get(name);
  if (v) to.set(name, v);
}

/**
 * Rewrite an HLS manifest so every variant/segment/key URL is routed back
 * through /api/stream (preserving CORS and the auth token).
 */
function rewriteManifest(text, baseUrl, selfUrl, token) {
  const proxyBase = selfUrl.origin + "/api/stream?token=" + encodeURIComponent(token) + "&url=";
  const toAbs = (ref) => {
    try { return new URL(ref, baseUrl).toString(); } catch (e) { return ref; }
  };
  const wrap = (ref) => proxyBase + encodeURIComponent(toAbs(ref));

  return text.split("\n").map((line) => {
    const trimmed = line.trim();
    if (!trimmed) return line;
    if (trimmed.startsWith("#")) {
      return line.replace(/URI="([^"]+)"/g, (m, uri) => 'URI="' + wrap(uri) + '"');
    }
    return wrap(trimmed);
  }).join("\n");
}

/* ----------------------------- M3U parser ----------------------------- */

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
        url: "",
      };
    } else if (line.startsWith("#EXTGRP") && cur) {
      cur.category = line.split(":")[1] ? line.split(":")[1].trim() : cur.category;
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
