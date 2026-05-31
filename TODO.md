# IPTV + Console Work — Status

✅ done & pushed · ⚠️ needs your action · ⬜ todo

## Done & pushed to origin/main (head 3508a9d)
- ✅ (1) Homepage "VilfinTV IPTV" in News & Media menu + Platform Features footer.
- ✅ (1) iptv.html: site footer matching vilfintv.com.
- ✅ (2) iptv.html login heading → "VilfinTV IPTV login".
- ✅ (3) Provider screen: Free IPTV, IPTV Pro, Custom cards (+ Jio/Airtel).
- ✅ (4) Console IPTV → Playback settings: per-provider Playlist URL + EPG URL
        for all 5 providers (dynamic rows).
- ✅ (5) Worker fetches+parses M3U from configured URL (30-min KV cache);
        screener /api/iptv/settings persists 5 providers incl. epg.
- ✅ (6) Defaults: Free = iptv-org index.m3u; Pro = Free-TV playlist.m3u8.
        (EPG default cleared — iptv-org has no hosted XMLTV; admin-set per provider.)
- ✅ (7) /api/epg backend (XMLTV now/next, cached) + iptv.html NOW/NEXT display.
        Live URL check: iptv-org index.m3u = 12,277 ch; Free-TV = 1,894 ch (OK).
- ✅ (8) Console News → Full Story: "Import from document" (PDF/Word/PPT/txt),
        in-browser parse (pdf.js/mammoth/JSZip), fills Headline+Story for review.

## ⚠️ REQUIRED — redeploy both workers (only you can; needs Cloudflare auth)
    npx wrangler deploy --config wrangler.iptv.toml
    npx wrangler deploy --config wrangler.screener.toml
All HTML is on GitHub Pages already. Free/Pro/Custom playback, the URL/EPG
settings, and EPG NOW/NEXT only go live after this redeploy.

## Remaining
- ⬜ (9) Full live validation in browser — needs redeployed workers to exercise
        login → playlist → stream → EPG, and a real doc import test in console.
        Static validation done: all JS blocks pass node --check; markers present.
- ⬜ (10) Mobile: new layouts use flex-wrap + min-width + auto-fit grids
        (responsive by construction). Final visual spot-check still advised.
- ⬜ (11) Post-validate after redeploy.

## Notes
- Doc import: legacy .doc/.ppt rejected (save as .docx/.pptx/PDF). Story field
  capped at 2000 chars (existing maxlength) — long docs are trimmed with notice.
- Cleanup later: scripts/_patch_*.py, *.bak.
