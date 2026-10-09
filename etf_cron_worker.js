/**
 * ETF Momentum Mode — exact-time refresh trigger.
 *
 * GitHub's scheduler throttles this repository heavily (even 5–30 minute crons
 * fire only a few times a day), so etf_momentum.yml's own schedule cannot
 * guarantee a daily refresh. Cloudflare crons fire on time: this worker
 * checks the published data after NSE close and dispatches the workflow
 * only when data/etf_momentum.json is behind the latest completed session.
 *
 * Deployed by .github/workflows/deploy_etf_cron.yml (secret GH_TOKEN with
 * actions:write / workflow scope). No public route (workers_dev = false).
 */

const OWNER = 'Vilfin-TV';
const REPO = 'MultiScreener';
const WORKFLOW = 'etf_momentum.yml';
const DATA_URL = `https://raw.githubusercontent.com/${OWNER}/${REPO}/main/data/etf_momentum.json`;
const RECENT_RUN_MIN = 25;      // a run started this recently is still in flight
const RETRY_AFTER_MIN = 90;     // after a build, wait before retrying (holidays / source lag)

function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GH_TOKEN}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'vilfintv-etf-cron',
    'X-GitHub-Api-Version': '2022-11-28',
  };
}

// Latest NSE session that should be published: today after 16:15 IST on a
// weekday, otherwise the previous weekday.
function expectedSession(now) {
  const ist = new Date(now.getTime() + 330 * 60000);
  const day = ist.getUTCDay();
  const mins = ist.getUTCHours() * 60 + ist.getUTCMinutes();
  const d = new Date(Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate()));
  const afterClose = day >= 1 && day <= 5 && mins >= 16 * 60 + 15;
  if (!afterClose) {
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
  const expected = expectedSession(now);
  const state = await publishedState().catch(() => null);
  // A build made before that session's close (10:15 UTC = 15:45 IST) holds intraday prices.
  const final = state ? new Date(`${state.asOf}T10:15:00Z`) : null;
  const complete = state && state.generated && new Date(state.generated) >= final;
  if (state && state.asOf >= expected && complete) {
    console.log(`Up to date: asOf ${state.asOf} (expected ${expected}).`);
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
  const why = state && state.asOf >= expected ? `${state.asOf} was built before the close` : `behind (${state ? state.asOf : 'unknown'} < ${expected})`;
  console.log(`${why} — dispatched ${WORKFLOW}: HTTP ${status}.`);
  return status === 204 ? 'dispatched' : `dispatch-failed-${status}`;
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env));
  },
};
