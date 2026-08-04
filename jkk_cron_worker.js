/**
 * JKK/UR digest cron exact-time trigger.
 *
 * Cloudflare Worker crons fire reliably to the minute, unlike GitHub's
 * best-effort scheduler. This worker is now the PRIMARY trigger to ensure
 * exact JST time delivery. It dispatches the jkk_email_watch.yml workflow
 * via workflow_dispatch so the email is sent precisely when scheduled.
 *
 * If this worker fails (e.g. GH_TOKEN expires), jkk_email_watchdog.yml
 * acts as a backup and will dispatch the workflow ~20 minutes late.
 *
 * Secret (set via `wrangler secret put GH_TOKEN -c wrangler.jkkcron.toml`):
 *   GH_TOKEN — GitHub token with repo + workflow scopes.
 */

const OWNER = 'Vilfin-TV';
const REPO = 'MultiScreener';
const WORKFLOW = 'jkk_email_watch.yml';

// Nifty screener — fired once at the 00:35 UTC slot on Mon–Fri (09:35 AM JST)
const NIFTY_REPO = 'nifty-screener';
const NIFTY_WORKFLOW = 'daily-screener.yml';
const NIFTY_CRON_SLOT = '35 0 * * *';

// A GitHub-cron run created within this window counts as "already sent".
const RECENT_WINDOW_MIN = 12;

function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GH_TOKEN}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'cloudflare-cron-trigger',
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

async function dispatchNiftyScreener(env) {
  const url = `https://api.github.com/repos/${OWNER}/${NIFTY_REPO}/actions/workflows/${NIFTY_WORKFLOW}/dispatches`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { ...ghHeaders(env), 'Content-Type': 'application/json' },
    body: JSON.stringify({ ref: 'main' }),
  });
  const status = res.status;
  if (status === 204) {
    console.log('Nifty screener workflow dispatched successfully.');
  } else {
    const body = await res.text().catch(() => '');
    console.error(`Nifty screener dispatch failed: HTTP ${status} — ${body}`);
  }
  return status;
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

    // Trigger nifty screener only at the 00:35 UTC weekday slot (09:35 AM JST Mon–Fri)
    if (event.cron === NIFTY_CRON_SLOT) {
      const day = new Date(event.scheduledTime).getUTCDay(); // 0=Sun…6=Sat
      if (day >= 1 && day <= 5) {
        ctx.waitUntil(dispatchNiftyScreener(env));
      }
    }
  },

  // Health/status endpoint: reports whether a digest ran recently. Read-only.
  async fetch(request, env) {
    const recent = await recentRunCount(env);
    return new Response(
      JSON.stringify({
        worker: 'cron-trigger',
        recentDigestRuns: recent,
        windowMinutes: RECENT_WINDOW_MIN,
      }),
      { headers: { 'Content-Type': 'application/json' } }
    );
  },
};
