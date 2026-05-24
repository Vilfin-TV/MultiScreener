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

