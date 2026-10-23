# VilfinTV Stories — free GitHub + Cloudflare architecture

**No paid server, WordPress installation, or CMS subscription is required.**

## Production reader
- Keep https://vilfintv.com/story.html unchanged.
- The reader requests `/api/stories` and `/api/stories/{slug}` first.
- Until the Cloudflare route is configured, it falls back to same-origin `stories/v1/index.json` and `stories/v1/{slug}.json`.
- No visible "V2" or old-page links.

## Publishing
1. Add/edit a story at `stories/v1/{slug}.json` using GitHub's web editor or pull requests.
2. Add its metadata to `stories/v1/index.json` (future CI automation can generate the index).
3. Merge to `main`; the existing Cloudflare site deployment publishes it.
4. The optional Cloudflare Worker `stories-api-worker.js` serves versioned GitHub content from the public repository with 5-minute edge cache. It needs a route `vilfintv.com/api/stories*` configured on your Cloudflare account. Deploying the Worker is a **separate setup step**; committing this file does not activate it.

## Security and limitations
- Only published, public content goes into `main`; use PR branches for drafts.
- No tokens, passwords, private drafts, or WordPress credentials in browser/Worker code.
- The GitHub raw endpoint is public. Avoid private personal information in story files.
- This is a **headless content workflow** rather than a WordPress admin dashboard. GitHub web editing is the free editorial UI.
- Cloudflare free-tier limits apply; verify your existing account quota and Worker availability.
- Existing legacy catalog entries are still short. Expanding all genres into full-length works is a separate editorial project; no automatic filler or false chapter counts.
