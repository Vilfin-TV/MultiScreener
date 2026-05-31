# IPTV + Console Work — COMPLETE

All 11 items done, committed, pushed, and verified live.

## Delivered & live (origin/main)
- ✅ (1) Homepage "VilfinTV IPTV" in News & Media menu + Platform Features footer;
        iptv.html has a site footer matching vilfintv.com. (verified on vilfintv.com)
- ✅ (2) iptv.html login heading → "VilfinTV IPTV login". (verified live)
- ✅ (3) Provider screen: Free IPTV, IPTV Pro, Custom cards (+ Jio/Airtel). (verified live)
- ✅ (4) Console IPTV → Playback settings: per-provider Playlist URL + EPG URL for
        all 5 providers (dynamic rows).
- ✅ (5) Worker fetches+parses M3U from configured URL (30-min KV cache); screener
        /api/iptv/settings persists 5 providers incl. epg.
- ✅ (6) Defaults: Free = iptv-org index.m3u; Pro = Free-TV playlist.m3u8.
        (EPG default cleared — iptv-org hosts no XMLTV; admin-set per provider.)
- ✅ (7) /api/epg backend (XMLTV now/next, cached) + iptv.html NOW/NEXT display.
        Live URL check: iptv-org index.m3u = 12,277 ch; Free-TV = 1,894 ch.
- ✅ (8) Console News → Full Story "Import from document" (PDF/Word/PPT/txt),
        in-browser parse (pdf.js/mammoth/JSZip), fills Headline+Story for review.
- ✅ (9) Validated: live workers return 401 on /api/epg, /api/playlist, /api/iptv/config
        (new code deployed); login returns proper error JSON; Pages HTML has markers.
- ✅ (10) Responsive: flex-wrap + min-width rows, auto-fit footer grid, contrast fixed.
- ✅ (11) Committed + pushed; post-validated against live endpoints.

## Deployment: AUTOMATIC (no manual wrangler needed)
GitHub Actions auto-deploy on push:
  - .github/workflows/deploy_iptv_worker.yml  (on iptv-worker.js / wrangler.iptv.toml)
  - .github/workflows/deploy_screener_proxy.yml (on screener-proxy-worker.js / wrangler.screener.toml)
Both use secrets.CLOUDFLARE_API_TOKEN. Confirmed live: page-iptv + screener-proxy
already serve the new code.

## To start using it
1. link-console.html → IPTV tab → create a viewer login (already supported).
2. IPTV → Playback settings → Free/Pro come pre-filled; add EPG URLs if you have them.
3. Viewers log in at vilfintv.com/iptv.html → pick a provider → watch.

## Notes
- Doc import: legacy .doc/.ppt rejected (save as .docx/.pptx/PDF). Story capped at
  2000 chars (existing field maxlength); longer docs trimmed with a notice.
- EPG "full guide": on-demand per-channel NOW/NEXT (full XMLTV guides are 100s of MB,
  beyond KV's 25 MB value cap) — the realistic approach for this stack.
