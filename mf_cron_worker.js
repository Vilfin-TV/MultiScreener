/**
 * India Mutual Fund Screener — exact-time refresh trigger.
 *
 * Fund houses publish each business day's NAV to AMFI by 11 pm IST (overseas
 * fund-of-funds the next morning). GitHub's scheduler is unreliable for this
 * repository, so this Cloudflare cron checks the published data late in the
 * evening and through the early morning, and dispatches mf_screener.yml only
 * when data/mf/screener.json is behind the latest expected NAV date. The
 * workflow's own "due" gate re-checks AMFI, so an early dispatch is cheap.
 *
 * Deployed by .github/workflows/deploy_mf_cron.yml (secret GH_TOKEN with
 * actions:write / workflow scope). No public route (workers_dev = false).
 */

const OWNER = 'Vilfin-TV';
const REPO = 'MultiScreener';
const WORKFLOW = 'mf_screener.yml';
const DATA_URL = `https://raw.githubusercontent.com/${OWNER}/${REPO}/main/data/mf/screener.json`;
const RECENT_RUN_MIN = 40;      // a run started this recently is still in flight
const RETRY_AFTER_MIN = 50;     // after a build, wait before retrying (holiday / late NAVs)

function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GH_TOKEN}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'vilfintv-mf-cron',
    'X-GitHub-Api-Version': '2022-11-28',
  };
}

// Latest NAV date that should be available: today's after 23:00 IST on a
// weekday, otherwise the previous weekday.
function expectedNavDate(now) {
  const ist = new Date(now.getTime() + 330 * 60000);
  const d = new Date(Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate()));
  const day = d.getUTCDay();
  const lateEvening = ist.getUTCHours() >= 23 && day >= 1 && day <= 5;
  if (!lateEvening) {
    do { d.setUTCDate(d.getUTCDate() - 1); } while (d.getUTCDay() === 0 || d.getUTCDay() === 6);
  }
  return d.toISOString().slice(0, 10);
}

async function publishedState() {
  const res = await fetch(`${DATA_URL}?t=${Date.now()}`, { cf: { cacheTtl: 0 } });
  if (!res.ok) return null;
  const d = await res.json();
  return { asOf: d.asOf, generated: d.generated };
}

async function recentRuns(env) {
  const since = new Date(Date.now() - RECENT_RUN_MIN * 60000).toISOString();
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?created=%3E${since}&per_page=5`;
  const res = await fetch(url, { headers: ghHeaders(env) });
  if (!res.ok) return 0;
  const data = await res.json();
  return (data.workflow_runs || []).filter(r => r.status !== 'completed').length;
}

async function dispatch(env) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { ...ghHeaders(env), 'Content-Type': 'application/json' },
    body: JSON.stringify({ ref: 'main' }),
  });
  return res.status; // 204 on success
}

async function run(env, now = new Date()) {
  const expected = expectedNavDate(now);
  const state = await publishedState().catch(() => null);
  if (state && state.asOf >= expected) {
    console.log(`Up to date: NAV ${state.asOf} (expected ${expected}).`);
    return 'up-to-date';
  }
  if (state && state.generated) {
    const ageMin = (now - new Date(state.generated)) / 60000;
    if (ageMin < RETRY_AFTER_MIN) {
      console.log(`Behind (${state.asOf} < ${expected}) but built ${ageMin.toFixed(0)} min ago — waiting.`);
      return 'waiting';
    }
  }
  if (await recentRuns(env) > 0) {
    console.log('A refresh run is already in progress — skipping.');
    return 'in-progress';
  }
  const status = await dispatch(env);
  console.log(`Behind (${state ? state.asOf : 'unknown'} < ${expected}) — dispatched ${WORKFLOW}: HTTP ${status}.`);
  return status === 204 ? 'dispatched' : `dispatch-failed-${status}`;
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env));
  },
};
