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

# Web Development & UI Standards

When generating, modifying, or reviewing web code, you must **always** strictly adhere to the following standards:

*   **Complete, Full-Page Output:** Always write and return complete, fully functional code for the entire page. **Never** use placeholders, brevity omissions (e.g., `// ... rest of the code here`), or partial snippets. Provide the full HTML/CSS/JS structure required for the page to run independently.
*   **Universal Responsiveness:** Every web page must be perfectly optimized for both Mobile Web and Desktop (PC) environments. Utilize modern, responsive CSS techniques (Flexbox, CSS Grid, and well-structured media queries) to ensure seamless transitions between screen sizes. 
*   **Professional UI/UX Quality:** Design layouts that are production-ready and professional. This requires:
    *   Consistent and balanced padding/margins.
    *   Modern, readable, and accessible typography.
    *   Clean, polished styling (e.g., subtle shadows, appropriate hover states, and logical alignment).
    *   Modular and easily maintainable code structure.

---

# Manual Setup Checklist

After deploying, complete these one-time manual steps:

## Google Cloud Console
- [ ] Create a Google Cloud Project (or use existing)
- [ ] Enable the **YouTube Data API v3**
- [ ] Enable the **Google Sheets API**
- [ ] Enable the **Google Drive API** (read-only scope)
- [ ] Create an API Key for YouTube (restrict to YouTube Data API v3)

## Google Sheets Service Account
- [ ] Create a Service Account in IAM & Admin → Service Accounts
- [ ] Generate a JSON key for it and download it
- [ ] Share the Google Sheet (title: `VilfinTV Screener Config`) with the service account email (Editor role)
- [ ] The Sheet must have worksheets named: `LiveTV`, `Tickers`

## GitHub Secrets (Settings → Secrets and variables → Actions)
- [ ] `YOUTUBE_API_KEY` — YouTube Data API v3 key
- [ ] `GSHEET_CREDS_JSON` — Full contents of the downloaded service-account JSON key (all on one line)
- [ ] `GSHEET_DOC_TITLE` — Title of the Google Sheet (default: `VilfinTV Screener Config`)

## Verify Workflows Work
- [ ] Go to Actions tab → select "Daily Monitor & Auto-Fix" → Run workflow (workflow_dispatch)
- [ ] Check the run logs for errors
- [ ] Verify `streams.json` and `radio_stations.json` are updated in the repo

## Google Sheet Structure
The `VilfinTV Screener Config` Google Sheet must have:
- **LiveTV** worksheet: Columns `Label | VideoId | ChannelId | Status | LastChecked`
- **Tickers** worksheet: Columns `Symbol | Exchange | Status`

