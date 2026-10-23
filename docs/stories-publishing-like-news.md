# Stories publishing — same pattern as VilfinTV News

News uses `.github/workflows/news.yml` to run `scripts/build_news.js`, commits `data/news.json`, and `news.html` fetches the file from the website.

Stories now follows that same no-cost model:

1. Edit or add `stories/v1/{slug}.json` through GitHub (no WordPress).
2. On a push to `main`, `.github/workflows/publish_stories.yml` validates all story files and rebuilds `stories/v1/index.json`.
3. The existing GitHub-to-Cloudflare publication path serves the updated files.
4. `story.html` fetches `stories/v1/index.json` and the selected story's JSON from the **same origin**, with cache busting.
5. All original embedded genres remain accessible as fallback while being expanded into structured stories.

No new Cloudflare Worker route, token, API subscription, server, or paid CMS is needed.

**Editorial note:** only one story currently has an expanded structured edition; the remaining legacy catalog is not yet full-length. This change is the publishing pipeline, not an automatic expansion of all stories.
