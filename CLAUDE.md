\# MultiScreener Core Directives

\- \*\*Design Language:\*\* Strictly emulate the Dhan ScanX Screener aesthetic. Premium financial UI: deep navy blues (`#0a192f` or similar), crisp whites, subtle gray borders, high contrast. 

\- \*\*Copywriting:\*\* Institutional-grade only. \*\*CRITICAL:\*\* NEVER use terms like "Free AI", "No API key", "Powered by", or mention backend/serverless mechanics. Use terms like "Market Assistant" or "Intelligent Search".

\- \*\*Session Management:\*\* If nearing context limits, automatically summarize remaining tasks and write them to a `TODO.md` file so work can be resumed seamlessly in the next session.

\- \*\*Environment:\*\* Hosted on GitHub Pages (Static HTML/CSS/JS). Use GitHub Actions for automated backend-like cron jobs.

## Automated Build & Data Security Rules
- **Secure Fetching:** Write or execute a Node.js build script to fetch the required JSON data from the Cloudflare Worker.
- **Environment Variables:** The Worker URL must ONLY be read from the local `.env` file using the `WORKER_URL` variable.
- **Local Storage:** Save the fetched JSON response locally as `data.json` inside the project folder before the frontend build runs.
- **Static Integration:** Configure the frontend website to read ONLY from the local `data.json` file.
- **CRITICAL SECURITY CONSTRAINT:** NEVER hardcode, import, or expose the `WORKER_URL` directly into any frontend HTML, CSS, or client-side JavaScript. The URL is strictly for backend build scripts and must remain 100% hidden from the final public GitHub Pages deployment.

## Story Illustrations & R2 (`vilfintv-story`) — Automatic, Zero Manual Upload
The `story.html` Stories hub must use **original, Claude-designed cover art** for every story — NEVER stock photos (no Unsplash/picsum in story covers). Art is generated as code (SVG), version-controlled, auto-uploaded to R2, and served via the Worker. This pipeline is fully automatic — no manual uploads from the user, ever.

**Asset layout (committed to the repo):**
- Per-story cover: `stories/<genre>/<slug>.svg` (800×520, framed title plate, genre-appropriate motif). `<slug>` = lowercased title before the `—`, non-alphanumerics → `-`, max 40 chars.
- Full per-page illustrated stories: `kids/<story-slug>/header.svg` + `pageN.svg` (e.g. `kids/pip-star/`), or `stories/kids/<slug>/pageN.svg` for the 8 Kids stories (one illustration interleaved before each paragraph).
- Brand fallback cover: `stories/_default.svg`.

**Generation tooling (the "design agent"):**
- `scripts/gen_story_covers.py` — emits all cover SVGs from a per-story spec (palette + motif + title). Add a new entry to `SPECS` to create a new cover, then run it.
- `scripts/wire_story_covers.py` — rewrites `story.html`: gives every story a top-level `mediaUrl` cover, replaces any inline image `src` with the cover, makes the hero card use `mediaUrl`, and guarantees zero stock-photo URLs remain.
- `scripts/gen_kids_pages.py` + `scripts/wire_kids_pages.py` — generate per-page picture-book illustrations for the Kids stories and interleave one before each paragraph in the `kids` reading level.

**R2 storage & serving:**
- Bucket **`vilfintv-story`** (binding `STORY` in `wrangler.screener.toml`). The Worker `/r2/<key>` route serves from `MEDIA` then falls back to `STORY`.
- GitHub Action **`.github/workflows/upload_story_images.yml`** auto-uploads everything under `kids/**` and `stories/**` to `vilfintv-story` under the `media/` key prefix on every push (and `workflow_dispatch`), using `CLOUDFLARE_API_TOKEN` (needs *Workers R2 Storage: Edit*) + `CLOUDFLARE_ACCOUNT_ID`.
- Public URL pattern: `https://screener-proxy.vilfintv.workers.dev/r2/media/stories/<genre>/<slug>.svg`.

**Referencing rule in `story.html`:** every story image `src` (and the story object's `mediaUrl`) points at the **R2 URL**, with the committed local SVG as the `onerror` fallback (`data-local` on the hero/prepend `<img>`), so a story is never broken even before R2 propagates.

**To add a future story (fully automatic):** add the story to `STORY_DATA.<genre>`, add its cover spec to `scripts/gen_story_covers.py` and run it (or hand-author `stories/<genre>/<slug>.svg`), run `scripts/wire_story_covers.py`, then commit + push — the Action uploads the art to R2 and GitHub Pages goes live. No manual R2 upload step.

## Image & Attribution Standards

### Fallback Images
- Use **Unsplash** (`images.unsplash.com/photo-{id}`) for generic fallback images — no attribution required under the Unsplash License.
- **No duplicate Unsplash photos** across channels, tabs, or page sections. Maintain the `_LNB_FALLBACKS` map and `_ML_IMG_POOLS` so every group/section uses a unique photo ID.
- Prefer `picsum.photos` (seeded by headline hash) in World News cards for deterministic, per-story variety without duplication.

### Official Government / Public Figure Images
- Images of political leaders may be sourced from **official government portals** where they are explicitly released for public use:
  - **Indian PM (Modi):** https://www.pmindia.gov.in/en/image-gallery/ → Attribution: `Image via pmindia.gov.in`
  - **US President (Trump):** https://www.whitehouse.gov/media/ → Attribution: `Image via whitehouse.gov`
  - **Kerala Government:** https://www.kerala.gov.in → Attribution: `Image via kerala.gov.in`
  - **European Council:** https://www.consilium.europa.eu/en/media/ → Attribution: `Image via consilium.europa.eu`
- When using official-source images, always display a clearly visible attribution line beneath the image, e.g.: `Source: Image via pmindia.gov.in`
- **NEVER** use paparazzi, commercial stock, or watermarked images of public figures.
- When in doubt, fall back to the region-specific Unsplash image — never risk a copyright issue.

### No-Duplicate Rule (Strict)
- Every fallback/placeholder image shown simultaneously on any single page must be unique.
- Within `_LNB_FALLBACKS`: one distinct Unsplash photo per channel group.
- Within `_ML_IMG_POOLS`: one distinct Unsplash photo per pool slot.
- In World News (`renderWorldSection`): use `_wCardImgUrl(headline)` (picsum seeded by headline hash) — this guarantees per-story uniqueness automatically.

## Live News Standards
- **Channel name stripping:** Always apply `_cleanNewsTitle()` to every RSS headline before display. This strips "- Source Name" suffixes that Google News RSS appends.
- **Source IDs:** Every entry in `NEWS_SOURCES` must have a **unique `id`** string. Never duplicate IDs; use distinct prefixes (jp3, jp4, kr1, kr2, cn1, cn2, th1, th2, uk1, uk2 …).
- **Default grid:** 9 channels max (`NEWS_MAX = 9`) in a 3×3 grid. Each channel box shows a hero card (full-width image + full headline) + up to 8 smaller cards.
- **Sentiment panel:** `_mktSentRenderMain` and `_mktSentRenderPanel` must always have null-guards for `m`. Cycle index uses `_mktSentData.length`, never `_MKTS_SENT_MARKETS.length`.

# Web Development & UI Standards

When generating, modifying, or reviewing web code, you must **always** strictly adhere to the following standards:

*   **Complete, Full-Page Output:** Always write and return complete, fully functional code for the entire page. **Never** use placeholders, brevity omissions (e.g., `// ... rest of the code here`), or partial snippets. Provide the full HTML/CSS/JS structure required for the page to run independently.
*   **Universal Responsiveness:** Every web page must be perfectly optimized for both Mobile Web and Desktop (PC) environments. Utilize modern, responsive CSS techniques (Flexbox, CSS Grid, and well-structured media queries) to ensure seamless transitions between screen sizes. 
*   **Professional UI/UX Quality:** Design layouts that are production-ready and professional. This requires:
    *   Consistent and balanced padding/margins.
    *   Modern, readable, and accessible typography.
    *   Clean, polished styling (e.g., subtle shadows, appropriate hover states, and logical alignment).
    *   Modular and easily maintainable code structure.



## Story Generation: Broker Referral Links
Whenever creating, publishing, or editing a "stock" or "mutual fund" story, you MUST automatically append the "Best Brokers & Apps" button and the direct referral links to the end of the story HTML. Do not wait for the user to ask.

Use the following exact HTML snippet at the very end of the story content:
```html
<p style="text-align: center;">
  <a href="https://vilfintv.com/market_sentiment_score.html" style="color: #e94560; text-decoration: none; font-weight: bold; font-size: 1.1em;">💼 Best Brokers &amp; Apps</a>
</p>
<ul style="list-style: none; padding: 0; text-align: center; line-height: 1.8; font-size: 0.95em; margin-bottom: 20px;">
  <li>🟢 <a href="https://zerodha.com/open-account?c=XKQ288" style="color:#1a73e8;text-decoration:none;">Zerodha (India)</a></li>
  <li>🔥 <a href="https://join.dhan.co/?invite=VFZJN04428" style="color:#1a73e8;text-decoration:none;">Dhan (India + US)</a></li>
  <li>💹 <a href="https://prostocks.com/open-an-account?ref=G1392" style="color:#1a73e8;text-decoration:none;">ProStocks (Flat-fee)</a></li>
  <li>🌐 <a href="https://www.interactivebrokers.co.jp/en/accounts/what-you-need-jp.php" style="color:#1a73e8;text-decoration:none;">Interactive Brokers (Global)</a></li>
  <li>🚀 <a href="https://kuvera.in/s/wsapp?referral=1T6BH" style="color:#1a73e8;text-decoration:none;">Kuvera (Mutual Funds)</a></li>
</ul>
```


## Story Generation: Financial Disclaimers
Whenever creating, publishing, or editing a "stock" or "mutual fund" story (in any language), you MUST automatically append a strict financial disclaimer to the end of the story HTML, immediately following the broker links. Do not wait for the user to ask.

For Malayalam stories, use this exact HTML snippet:
```html
<p style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107; font-size: 0.9em; color: #555; line-height: 1.6;">
  <strong>ഡിസ്‌ക്ലൈമർ (Disclaimer):</strong> മ്യൂച്വൽ ഫണ്ട്, ഓഹരി വിപണി നിക്ഷേപങ്ങൾ വിപണിയിലെ നഷ്ടസാധ്യതകൾക്ക് വിധേയമാണ്. നിക്ഷേപിക്കുന്നതിന് മുൻപ് സ്കീം സംബന്ധിച്ച രേഖകൾ പൂർണ്ണമായും ശ്രദ്ധാപൂർവ്വം വായിക്കുക. ഈ ലേഖനത്തിൽ നൽകിയിട്ടുള്ള വിവരങ്ങൾ തികച്ചും വിദ്യാഭ്യാസ പരമായ ആവശ്യങ്ങൾക്ക് (Educational purposes only) മാത്രമുള്ളതാണ്. ഞങ്ങൾ SEBI രജിസ്റ്റർ ചെയ്ത നിക്ഷേപ ഉപദേശകരല്ല (Not SEBI registered advisors). നിങ്ങളുടെ സാമ്പത്തിക ലക്ഷ്യങ്ങൾക്കും റിസ്ക് എടുക്കാനുള്ള കഴിവിനും അനുസരിച്ച് സ്വന്തമായി തീരുമാനങ്ങൾ എടുക്കുകയോ, അംഗീകൃത സാമ്പത്തിക ഉപദേശകന്റെ സഹായം തേടുകയോ ചെയ്യുക.
</p>
```

For English stories, use this exact HTML snippet:
```html
<p style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107; font-size: 0.9em; color: #555; line-height: 1.6;">
  <strong>Disclaimer:</strong> Mutual fund and stock market investments are subject to market risks. Please read all scheme-related documents carefully before investing. The information provided in this article is strictly for educational and informational purposes only. We are not SEBI registered investment advisors. Please conduct your own research or consult with a certified financial advisor before making any investment decisions based on your personal risk tolerance and financial goals.
</p>
```
