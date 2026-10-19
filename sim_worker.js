/**
 * sim_worker.js — private Simulator Buy ledger viewer (Cloudflare Worker "vilfintv-sim").
 *
 *   GET /                     the statement page (sim_page.html) — holds no data; asks for the access key
 *   GET /api/view             accounts, transactions, holdings, valuations     ┐ need header x-sim-key
 *   GET /api/audit            latest independent audit                         │ (SHA-256 must equal
 *   GET /api/snapshots        list of the dated permanent copies               │  SIM_KEY_HASH)
 *   GET /api/file?key=…       one dated copy (sim/snapshots/… only)            ┘
 *
 * Data lives only in the private R2 bucket "vilfintv-sim" (binding SIM), written by .github/workflows/sim_ledger.yml.
 * Nothing here is public: every data route needs the key, responses are never cached and pages are not indexed.
 */
import PAGE from "./sim_page.html";

const SEC = {
  "Cache-Control": "no-store",
  "X-Robots-Tag": "noindex, nofollow, noarchive",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

async function sha256hex(s) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
}

function same(a, b) {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { ...SEC, "Content-Type": "application/json; charset=utf-8" } });
}

async function object(env, key) {
  const o = await env.SIM.get(key);
  if (!o) return json({ error: "not found" }, 404);
  return new Response(o.body, {
    headers: { ...SEC, "Content-Type": "application/json; charset=utf-8", "Last-Modified": o.uploaded.toUTCString() },
  });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method !== "GET" && req.method !== "HEAD") return json({ error: "method not allowed" }, 405);

    if (url.pathname === "/" || url.pathname === "/index.html") {
      return new Response(PAGE, {
        headers: {
          ...SEC, "Content-Type": "text/html; charset=utf-8",
          "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:; frame-ancestors https://vilfintv.com https://www.vilfintv.com https://vilfin-tv.github.io; base-uri 'none'; form-action 'none'",
        },
      });
    }
    if (url.pathname === "/robots.txt") return new Response("User-agent: *\nDisallow: /\n", { headers: { ...SEC, "Content-Type": "text/plain" } });
    if (!url.pathname.startsWith("/api/")) return json({ error: "not found" }, 404);

    const key = req.headers.get("x-sim-key") || "";
    if (!env.SIM_KEY_HASH || !key || !same(await sha256hex(key), env.SIM_KEY_HASH)) {
      await new Promise(r => setTimeout(r, 400));              // slow down guessing
      return json({ error: "access key required" }, 401);
    }

    if (url.pathname === "/api/view") return object(env, "sim/view.json");
    if (url.pathname === "/api/audit") return object(env, "sim/audit.json");
    if (url.pathname === "/api/snapshots") {
      const out = [];
      let cursor;
      do {
        const l = await env.SIM.list({ prefix: "sim/snapshots/", cursor, limit: 1000 });
        for (const o of l.objects) out.push({ key: o.key, size: o.size, uploaded: o.uploaded });
        cursor = l.truncated ? l.cursor : undefined;
      } while (cursor);
      return json({ snapshots: out.sort((a, b) => (a.key < b.key ? 1 : -1)) });
    }
    if (url.pathname === "/api/file") {
      const k = url.searchParams.get("key") || "";
      if (!/^sim\/snapshots\/\d{4}-\d{2}-\d{2}\/[a-z]+\.json$/.test(k)) return json({ error: "bad key" }, 400);
      return object(env, k);
    }
    return json({ error: "not found" }, 404);
  },
};
