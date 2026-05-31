# IPTV + Console Work — Status

✅ done & pushed · ⚠️ needs your action · ⬜ todo

## Done & pushed to origin/main (latest 2f6f5f9)
- ✅ (1) Homepage "VilfinTV IPTV" link in News & Media menu + Platform Features footer.
- ✅ (1) iptv.html: site footer matching vilfintv.com.
- ✅ (2) iptv.html login heading → "VilfinTV IPTV login".
- ✅ (3) Provider screen: Free IPTV, IPTV Pro, Custom cards (+ Jio/Airtel).
- ✅ (4) link-console IPTV → Playback settings: per-provider Playlist URL + EPG URL
        inputs for all 5 providers (dynamic rows).
- ✅ (5) Worker fetches+parses M3U from configured URL (30-min KV cache); screener
        /api/iptv/settings persists 5 providers incl. epg.
- ✅ (6) Defaults: Free = iptv-org index.m3u (EPG in.xml); Pro = Free-TV playlist.
- ✅ (7) /api/epg backend (on-demand XMLTV now/next, 60-min cache) + iptv.html
        NOW/NEXT guide display for channels with tvg-id.

## ⚠️ REQUIRED — redeploy both workers (only you can; needs CLOUDFLARE auth)
    npx wrangler deploy --config wrangler.iptv.toml
    npx wrangler deploy --config wrangler.screener.toml
HTML is already on GitHub Pages. Free/Pro/Custom playback, URL settings, and EPG
go live only after this redeploy.

## Remaining
- ⬜ (8) link-console News → Full story: PDF/PPT/Word/txt upload → format into
        news.html. NOT STARTED. Needs your decision on parsing approach (below).
- ⬜ (9) Live preview validation — after redeploy, exercise login→playlist→stream→EPG.
- ⬜ (10) Mobile pass (console rows + iptv footer are responsive by construction;
        visual check pending).
- ⬜ (11) Final post-validate.

## Decision needed for #8 (doc upload)
Cloudflare Workers have NO native unzip or PDF parser. Honest options:
  A. In-browser parse in link-console using pdf.js + mammoth (docx) + JSZip (pptx)
     + plain txt. Reliable on GitHub Pages, no worker limits. (Recommended.)
  B. Worker-side: must bundle libraries; .docx/.pptx/.pdf are heavy/fragile in a
     Worker. Higher risk of failure.
Earlier you picked worker-side; I recommend reconsidering A for reliability.

Also confirm: how should the parsed document map to a news post in news.html?
(title = filename? first heading? and which content.json section/tab?)

## Cleanup later: scripts/_patch_*.py, *.bak
