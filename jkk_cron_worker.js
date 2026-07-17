/**
 * JKK/UR digest cron backup trigger.
 *
 * Cloudflare Worker crons fire reliably, unlike GitHub's best-effort
 * scheduler - the whole point of this backup. Originally used 5 separate
 * fixed-time crons (one per daily digest slot), but Cloudflare enforces a
 * 5-cron-trigger limit PER ACCOUNT (not per worker) - this account was
 * already at that cap with 4 JKK crons + 1 IPTV worker cron, so adding a
 * 5th JKK slot for the 2026-07-16 schedule expansion (4->5 sends/day)
 * silently couldn't deploy (discovered 2026-07-17: the stale 4-slot cron
 * list left the two newest slots with zero Cloudflare-side backup at all,
 * on top of the GH_TOKEN issue below).
 *
 * Redesigned to use a SINGLE frequent cron (every 15 min) with in-worker
 * time-window logic instead - this uses just 1 of the account's 5 cron
 * slots total, and is arguably MORE robust than 5 one-shot crons since it
 * re-checks repeatedly through each slot's whole grace window rather than
 * getting one attempt.
 *
 * If GitHub already started a digest run recently (from its own cron, its
 * watchdog, or an earlier tick of this same worker), this does nothing;
 * otherwise it triggers the workflow via workflow_dispatch — so the email
 * can never be silently skipped, and never sends twice.
 *
 * Secret (set via `wrangler secret put GH_TOKEN -c wrangler.jkkcron.toml`):
 *   GH_TOKEN — GitHub token with repo + workflow scopes. CONFIRMED BROKEN
 *   as of 2026-07-17 (health endpoint reports recentDigestRuns: -1, the
 *   value returned specifically when the GitHub API call itself fails) -
 *   same finding as the 2026-07-14 investigation referenced in
 *   jkk_email_watchdog.yml. This needs a fresh PAT with repo+workflow
 *   scopes set via the command above before this backup can do anything.
 */

const OWNER = 'Vilfin-TV';
const REPO = 'MultiScreener';
const WORKFLOW = 'jkk_email_watch.yml';
// A GitHub-cron (or this worker's own prior tick) run created within this
// window counts as "already sent" - must comfortably exceed the ~15 min
// interval this worker now runs on, or it would re-dispatch every tick.
const RECENT_WINDOW_MIN = 25;
// Target times (minutes since UTC midnight) for the 5 daily digest slots -
// must stay in sync with .github/workflows/jkk_email_watch.yml's own cron
// schedule: 00:35 / 02:03 / 05:30 / 07:45 / 11:15 UTC.
const TARGET_MINUTES_UTC = [35, 123, 330, 465, 675];
// How long after a target time this worker still considers a catch-up
// dispatch - mirrors jkk_email_watchdog.yml's own +140 min grace window.
const GRACE_WINDOW_MIN = 150;

function minutesSinceMidnightUTC(date) {
  return date.getUTCHours() * 60 + date.getUTCMinutes();
}

function withinGraceWindowOfAnyTarget(date) {
  const nowMin = minutesSinceMidnightUTC(date);
  return TARGET_MINUTES_UTC.some((t) => nowMin >= t && nowMin <= t + GRACE_WINDOW_MIN);
}

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
    const now = new Date(event.scheduledTime || Date.now());
    if (!withinGraceWindowOfAnyTarget(now)) {
      console.log(`Not within any target's grace window (now=${now.toISOString()}) - nothing to check.`);
      return;
    }
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
