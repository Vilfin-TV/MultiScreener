// ╔══════════════════════════════════════════════════════════════╗
// ║  VilfinTV MultiScreener — Global Config                      ║
// ║  Worker URL is CORS-locked to vilfin-tv.github.io only       ║
// ╚══════════════════════════════════════════════════════════════╝

const VILTV_CONFIG = {
  // Cloudflare Worker proxy (CORS-locked, safe to expose)
  WORKER_URL: 'https://x9-k2-p20-worker.vilfintv.workers.dev',

  // Supabase — public/anon key only (read-only access to public tables)
  SUPABASE_URL: 'https://apmsebmmmvpymewimdpd.supabase.co',
  SUPABASE_KEY: 'sb_publishable_TDT4YVj6UhPqEVFEINaTjQ_GDscLAK1',

  // Default AI model
  DEFAULT_MODEL: 'gemini-2.5-flash',

  // App version
  VERSION: 'v8.9.0',
};

// Auto-register Worker URL into localStorage on load (so all pages can use it)
(function () {
  try {
    const CF_KEY = 'viltv_cf_worker_url';
    if (!localStorage.getItem(CF_KEY) && VILTV_CONFIG.WORKER_URL) {
      localStorage.setItem(CF_KEY, VILTV_CONFIG.WORKER_URL);
    }
  } catch (e) {}
})();
