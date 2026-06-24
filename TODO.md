# VilfinTV — Resume / Pending Work

_Last updated: 2026‑06‑25. Paste this into a new session to continue seamlessly._

## How this project deploys (important context)
- Static site = **GitHub Pages** at `https://vilfintv.com` (repo `Vilfin-TV/MultiScreener`, branch `main`). A push → Pages rebuild (~1 min).
- **Two Cloudflare Workers, sharing the SAME KV namespace** (`25437ace…`):
  - `screener-proxy.vilfintv.workers.dev` (`screener-proxy-worker.js`) — news/console API, agent keys, LLM/images/lessons, **and all `/api/iptv/*` management**. Auto-deploys via `.github/workflows/deploy_screener_proxy.yml`.
  - `page-iptv.vilfintv.workers.dev` (`iptv-worker.js`) — the IPTV **player** only (`/api/login`, `/api/settings`, `/api/playlist`, `/api/stream`, `/api/epg`). Auto-deploys via `.github/workflows/deploy_iptv_worker.yml`.
  - **Do NOT confuse them.** Provider/credential MANAGEMENT = screener-proxy; the player READS the shared KV.
- Commit/push workflow: branch is `main`; `git pull --rebase` then push (cron jobs push often). End commit msgs with the Co-Authored-By line.
- Validate before commit: `node --check screener-proxy-worker.js` / `node --check iptv-worker.js`; for HTML, load in the Python preview server and `new Function()`-parse inline scripts (note: JSON‑LD scripts are false positives). Live screenshots time out — use `preview_inspect`/`preview_eval` DOM checks instead.
- The `check-sql-files.py` PostToolUse hook error is unrelated noise — ignore it.

## ✅ Done recently (live)
- **IPTV player fully fixed & restyled (Jun 2026):** (1) Root cause of "providers show but no channels load + menus/remote dead" was the inline player script running during body parse before the trailing `legacy-ui-stubs` existed → first `getElementById` on a not‑yet‑parsed node threw and aborted all init. Fixed by deferring init to `DOMContentLoaded` (`__iptvBoot`), defining the missing `hasAnyFilter()`, and stubbing all retired ids (hero‑remote‑btn, load‑more, now‑card/ni‑*, etc.). (2) **Vertical channel grid** replacing the single horizontal row, responsive for mobile/iPad, with **infinite scroll** (append‑on‑scroll). (3) **Netflix/Fox category‑row browse** (`renderGrouped`): labeled category sections, horizontal rows w/ hover‑scale, "See all →" drills to flat grid; **Rows/Grid toggle** (persisted). Console IPTV tab agent note expanded to a full operator spec. All verified via preview DOM checks (screenshots time out).
- IPTV: fixed refresh auto‑logout (verifyToken no longer rejects unknown‑in‑KV usernames), removed max‑concurrent‑session limit, set VilfinTV logo, added a premium hero on the provider screen.
- Console: per‑tab **🤖 agent notes** on News, Stories, Academy, Links, Home Page, IPTV, **and Settings** (collapsible, with exact endpoint/scope/rules).
- Agent system (built earlier): scoped API keys (publish/edit/delete/llm/images/lessons/operator) + one‑time approval; 2FA (TOTP+QR); login activity/device tracking + revoke; LLM provider config (OpenRouter free/all‑rotate, custom providers like Groq); image sources; academy lessons (additive via `lessons.json`); YouTube in‑story player; iPad mobile layout.

## ⏳ PENDING WORK
1. ~~IPTV — full Netflix/Fox row layout~~ ✅ **DONE** (see Done section): vertical grid + category rows + Rows/Grid toggle, all live.
2. **IPTV play‑test** — needs ONE provider configured with a **real licensed M3U URL** first (Console → IPTV → Add provider). Then verify a channel actually plays (HLS path) and EPG loads. Cannot be done until the user adds a licensed source. NOTE: the front‑end now requests the playlist/stream correctly; if a provider shows the card but **0 channels**, that's the source URL (HTML/login page, geo‑block, empty, or >24 MB), not the app.
3. **(Optional) Seed provider slots** — generate the ready‑to‑POST `providers[]` array for the ~34 category slots the user listed (US, UK, Europe, India, Sports, Kids, Malayalam, etc.) with labels/ids only and **blank** url/epg, so the user/agent fills licensed sources. POST to `screener-proxy /api/iptv/settings`.
4. **End‑to‑end agent verification** (user‑side): create + **approve** scoped keys in console; run `build_litellm.py`; test publish / lesson / image upload / iptv settings round‑trips.
5. **Academy lessons content** — agent can add lessons via `/api/agent/lesson` per hub when the user wants.

## 🚫 Will NOT do (policy)
Sourcing/curating/verifying premium or paywalled m3u/EPG (Fox/Netflix‑style, premium sports, FIFA live) = unauthorized redistribution of copyrighted streams. Framework only; the user supplies their **own licensed** URLs (or legal free FTA like iptv‑org).

## Agent (Hermes) quick reference — all on `https://screener-proxy.vilfintv.workers.dev`, header `Authorization: Bearer vtv.<id>.<secret>`
- First run once: `POST /api/agent/request` → if pending, admin approves in Console → Settings → Agent API keys.
- **publish** scope: `POST /api/agent/publish {section,heading,story(HTML),photo?,days?,youtube?,youtube_play?}`; edit = add `id`. **delete**: `POST /api/agent/delete {id}`.
- **lessons** scope: `POST /api/agent/lesson {hub,lesson}`; `GET /api/agent/lessons` (hubs: finlit finance micro macro ai programming web info career growth).
- **images** scope: `GET /api/agent/images`; upload via `POST /api/upload-image` → use returned url as `photo`.
- **llm** scope: `GET /api/agent/llm` → providers/default/freeModels/allModels.
- **operator** scope (Links/Home Page/IPTV): `GET /api/iptv/config` → modify → `POST /api/iptv/settings {settings:{sessionHours,defaultProvider,providers:[FULL array]}}`; `POST /api/post-link` / `POST /api/update-links {links:[…]}`; `POST /api/update-config {config:{…}}`. **Golden rule: replace endpoints take the FULL array/object — GET current first, modify, POST everything back, or you wipe data.**
- Story HTML: only `<p> <h2> <h3> <strong> <em> <ul><li> <ol><li> <blockquote> <a>`; no inline styles, no base64 images. Fonts auto‑apply.
- 403 → read the JSON `message` (pending approval / expired / missing scope). Never assume "IP block". Use a real browser User‑Agent for outbound fetches; route nothing through `vilfintv.com` (`/api` is on the worker only).
