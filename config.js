// ╔══════════════════════════════════════════════════════════════╗
// ║  VilfinTV MultiScreener — Global Config                      ║
// ║  Worker URL is CORS-locked to vilfin-tv.github.io only       ║
// ╚══════════════════════════════════════════════════════════════╝

const VILTV_CONFIG = {
  // Supabase — public/anon key only (read-only access to public tables)
  SUPABASE_URL: 'https://apmsebmmmvpymewimdpd.supabase.co',
  SUPABASE_KEY: 'sb_publishable_TDT4YVj6UhPqEVFEINaTjQ_GDscLAK1',

  // Default AI model
  DEFAULT_MODEL: 'gemini-2.5-flash',

  // First-party Worker used for AI, scores, and feed proxying
  WORKER_URL: 'https://x9-k2-p30-worker.workers.dev',

  // App version
  VERSION: 'v9.0',
};
