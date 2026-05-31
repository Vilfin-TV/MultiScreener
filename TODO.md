# IPTV + Console Work — TODO

Tracking the 11-item batch. Status: ✅ done · 🟡 in progress · ⬜ not started

## Phase 0 — unblock visibility
- ✅ Fix IPTV console panel contrast (light text). Pushed `1103e3e` → live. Needs hard-refresh.

## Phase 1 — iptv.html self-contained
- ⬜ (2) Rename login heading "IPTV Console" → "VilfinTV IPTV login".
- ⬜ (3) After login, add 3 provider cards: **Free IPTV**, **IPTV Pro**, **Custom** (under "Choose a provider").
- ⬜ (1b) Add the same footer as vilfintv.com homepage to iptv.html.

## Phase 2 — homepage integration (needs index.html)
- ⬜ (1a) Add iptv.html to homepage **Top menu → News & Media** and **footer → Platform Features**, label "VilfinTV IPTV" with a styled icon.

## Phase 3 — playlist sources (console + worker)
- ⬜ (4) link-console IPTV → Playback settings: add per-provider **playlist URL** inputs.
  (worker already supports `providers.{name}.url` per recent edits — verify + finish console UI.)
- ⬜ (5) Backend: when an M3U URL is set, /api/playlist fetches+parses it (KV cache).
- ⬜ (6) Pre-fill **Free IPTV** = https://iptv-org.github.io/iptv/index.m3u, EPG = https://github.com/iptv-org/epg
       **Free-TV** = https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8
- ⬜ EPG support (XMLTV) — LARGER feature; program-guide parse + UI. Flag for its own pass.

## Phase 4 — testing
- ⬜ (7) Verify both playlists load in iptv.html (iptv-org index.m3u, Free-TV playlist.m3u8) + EPG.

## Phase 5 — news document upload (needs news.html + backend)
- ⬜ (8) link-console News → Full story: upload button (PDF/PPT/Word/txt) → parse → format → news.html.
       LARGER feature: needs document text extraction. Decide client-lib vs worker parse.

## Phase 6 — finish
- ⬜ (10) Mobile responsiveness pass on console + iptv.html.
- ⬜ (9) Pre-validate in preview panel.
- ⬜ (11) Commit + post-validate.

## Notes / decisions needed
- EPG (#6/#7): full electronic program guide is a big addition. Confirm whether you want
  just the playlists working now, with EPG as a follow-up.
- Doc upload (#8): PDF/PPT/Word text extraction — confirm approach (in-browser libraries
  like pdf.js/mammoth/JSZip, vs. a worker-side parser).
