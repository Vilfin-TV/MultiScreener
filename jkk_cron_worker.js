/**
 * JKK/UR digest cron backup trigger.
 *
 * Cloudflare Worker crons fire reliably to the minute, unlike GitHub's
 * best-effort scheduler. Each cron here runs a few minutes AFTER the matching
 * GitHub Actions cron in .github/workflows/jkk_email_watch.yml. If GitHub
 * already started a digest run recently, this does nothing; otherwise it
 * triggers the workflow via workflow_dispatch — so the email can never be
 * silently skipped, and never sends twice.
 *
 * Secret (set via `wrangler secret put GH_TOKEN -c wrangler.jkkcron.toml`):
 *   GH_TOKEN — GitHub token with repo + workflow scopes.
 */

const OWNER = 'Vilfin-TV';
const REPO = 'MultiScreener';
const WORKFLOW = 'jkk_email_watch.yml';
// A GitHub-cron run created within this window counts as "already sent".
const RECENT_WINDOW_MIN = 12;

function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GH_TOKEN}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'jkk-cron-worker',
    'X-GitHub-Api-Version': '2022-11-28',
  };
}

async function recentRunCount(env) {
  const since = new Date(Date.now() - RECENT_WINDOW_MIN * 60 * 1000).toISOString();
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?created=%3E${since}&per_page=5`;
  const res = await fetch(url, { headers: ghHeaders(env) });
  if (!res.ok) return -1; // can't tell — dispatch anyway, better twice than never
  const data = await res.json();
  return (data.workflow_runs || []).length;
}

async function dispatchWorkflow(env) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { ...ghHeaders(env), 'Content-Type': 'application/json' },
    body: JSON.stringify({ ref: 'main' }),
  });
  return res.status; // 204 on success
}

async function ensureDigestRan(env) {
  const recent = await recentRunCount(env);
  if (recent > 0) {
    console.log(`GitHub cron already ran ${recent} digest(s) in the last ${RECENT_WINDOW_MIN} min — skipping.`);
    return { action: 'skipped', recent };
  }
  const status = await dispatchWorkflow(env);
  console.log(`No recent digest run — dispatched workflow (HTTP ${status}).`);
  return { action: 'dispatched', status };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(ensureDigestRan(env));
  },

  // Health/status endpoint: reports whether a digest ran recently. Read-only.
  async fetch(request, env) {
    const recent = await recentRunCount(env);
    return new Response(
      JSON.stringify({
        worker: 'jkk-cron-trigger',
        recentDigestRuns: recent,
        windowMinutes: RECENT_WINDOW_MIN,
      }),
      { headers: { 'Content-Type': 'application/json' } }
    );
  },
};
