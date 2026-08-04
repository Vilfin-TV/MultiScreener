/**
 * QVM Screener cron exact-time trigger.
 *
 * Cloudflare Worker crons fire reliably to the minute, unlike GitHub's
 * best-effort scheduler. This worker is the PRIMARY trigger to ensure
 * exact JST time delivery of the Daily QVM Screener email.
 *
 * Target: 09:30 JST = 00:30 UTC daily
 * Repo:   Vilfin-TV/nifty-screener
 * Workflow: daily-screener.yml
 *
 * Deploy:
 *   npx wrangler deploy --config wrangler.qvmcron.toml
 *
 * Secret (one-time, GitHub PAT with repo + workflow scopes):
 *   npx wrangler secret put GH_TOKEN --config wrangler.qvmcron.toml
 */

const OWNER    = 'Vilfin-TV';
const REPO     = 'nifty-screener';
const WORKFLOW = 'daily-screener.yml';

// A run created within this window counts as "already sent" — prevents
// a double-dispatch if GitHub's own cron fires just before this worker.
const RECENT_WINDOW_MIN = 15;

function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GH_TOKEN}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'cloudflare-qvm-cron-trigger',
    'X-GitHub-Api-Version': '2022-11-28',
  };
}

async function recentRunCount(env) {
  const since = new Date(Date.now() - RECENT_WINDOW_MIN * 60 * 1000).toISOString();
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?created=%3E${encodeURIComponent(since)}&per_page=5`;
  const res = await fetch(url, { headers: ghHeaders(env) });
  if (!res.ok) {
    console.error(`GitHub API error ${res.status} checking recent runs — dispatching anyway (fail-open).`);
    return -1; // -1 = unknown; caller dispatches to be safe
  }
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

async function ensureScreenerRan(env) {
  const recent = await recentRunCount(env);
  if (recent > 0) {
    console.log(`GitHub cron already ran ${recent} screener run(s) in the last ${RECENT_WINDOW_MIN} min — skipping.`);
    return { action: 'skipped', recent };
  }
  const status = await dispatchWorkflow(env);
  console.log(`No recent screener run — dispatched workflow (HTTP ${status}).`);
  return { action: 'dispatched', status };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(ensureScreenerRan(env));
  },

  // Health/status endpoint — read-only, safe to expose.
  async fetch(request, env) {
    const recent = await recentRunCount(env);
    return new Response(
      JSON.stringify({
        worker:         'qvm-cron-trigger',
        repo:           `${OWNER}/${REPO}`,
        workflow:       WORKFLOW,
        recentRuns:     recent,
        windowMinutes:  RECENT_WINDOW_MIN,
        checkedAt:      new Date().toISOString(),
      }),
      { headers: { 'Content-Type': 'application/json' } },
    );
  },
};
