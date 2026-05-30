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

const IPTV_DEFAULT_SETTINGS = {
  sessionHours: DEFAULT_SESSION_HOURS,
  defaultProvider: "jio",
  providers: { jio: { enabled: true }, airtel: { enabled: true } },
};

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
  if (!kv) return { ...IPTV_DEFAULT_SETTINGS };
  const raw = await kv.get("iptv_settings");
  if (!raw) return { ...IPTV_DEFAULT_SETTINGS };
  try {
    const s = JSON.parse(raw);
    return {
      sessionHours: Math.max(1, Math.min(168, parseInt(s.sessionHours, 10) || DEFAULT_SESSION_HOURS)),
      defaultProvider: s.defaultProvider === "airtel" ? "airtel" : "jio",
      providers: {
        jio: { enabled: s.providers && s.providers.jio ? !!s.providers.jio.enabled : true },
        airtel: { enabled: s.providers && s.providers.airtel ? !!s.providers.airtel.enabled : true },
      },
    };
  } catch (e) {
    return { ...IPTV_DEFAULT_SETTINGS };
  }
}

/* ----------------------------- tokens ----------------------------- */

async function issueToken(username, env, ttlSeconds) {
  const secret = env.IPTV_TOKEN_SECRET || env.IPTV_SECRET_PASS; // a dedicated secret is recommended
  const ttl = ttlSeconds || DEFAULT_SESSION_HOURS * 3600;
  const payload = {
    sub: username,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + ttl,
  };
  const body = b64urlEncode(enc.encode(JSON.stringify(payload)));
  const sig = await hmacSign(body, secret);
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

async function handlePlaylist(request, env, url) {
  const auth = await requireAuth(request, env, url);
  if (!auth) return json({ error: "Unauthorized" }, 401);

  const provider = (url.searchParams.get("provider") || "").toLowerCase();
  if (!/^[a-z0-9_-]{1,32}$/.test(provider)) return json({ error: "Invalid provider" }, 400);

  // Respect the per-provider enable toggle from settings.
  const settings = await loadSettings(env);
  if (settings.providers[provider] && settings.providers[provider].enabled === false) {
    return json({ error: "Provider is disabled" }, 403);
  }

  if (!env.IPTV_PLAYLIST_KV) return json({ error: "Playlist store not configured" }, 503);

  const raw = await env.IPTV_PLAYLIST_KV.get(provider + "_playlist");
  if (!raw) return json({ error: "No playlist found for provider" }, 404);

  const channels = parseM3U(raw);
  return json({ provider, count: channels.length, channels });
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
    const line = lines[i].trim();
    if (!line) continue;

    if (line.startsWith("#EXTINF")) {
      cur = {
        name: extractTitle(line),
        logo: attr(line, "tvg-logo") || attr(line, "logo") || "",
        category: attr(line, "group-title") || "General",
        language: attr(line, "tvg-language") || attr(line, "language") || "",
        quality: guessQuality(line),
        url: "",
      };
    } else if (line.startsWith("#EXTGRP") && cur) {
      cur.category = line.split(":")[1] ? line.split(":")[1].trim() : cur.category;
    } else if (!line.startsWith("#")) {
      if (cur) { cur.url = line; channels.push(cur); cur = null; }
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
