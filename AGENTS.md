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



## Education Site Assets
- **Photos:** Going forward, all education site free photos (mnemonics, kanji, etc.) are fetched automatically from Pexels via the scripts/auto_fetch_images.js script. Do NOT hardcode manual images if an automated fetch via the Pexels API is possible. The PEXELS_API_KEY is provided via GitHub Secrets.


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
