# VilfinTV Stories V2 — Headless WordPress Architecture (Draft)

Status: **prototype / not deployed**. Applies to PR #169 only. Existing `story.html`, production domain, RSS, and Cloudflare workers remain unchanged.

## Decisions
- **Reader/frontend:** static HTML/CSS/JavaScript served from the existing VilfinTV frontend and cached at Cloudflare. Keep the current dual-mode reader (scroll + chapter pages), responsive typography, theme and local progress.
- **Editorial CMS:** a **separately hosted, secured WordPress installation** used only for authoring, editorial review and publishing. No WordPress PHP, admin, or theme assets are loaded by public readers.
- **Content delivery:** publish validated, versioned JSON files to the existing static/CDN pipeline. Browser fetches same-origin static JSON. Avoid cross-origin WordPress calls from every reader session.
- **Go:** optional content pipeline/API if measured needs justify a persistent service. Do not introduce a server dependency for simple static chapters.
- **Rust:** optional later for indexing or heavy text processing after profiling; not on the initial request path.

## Proposed publication flow

Editor → WordPress custom post types → authenticated export job → schema validation + sanitization → JSON snapshots → GitHub review/CI → Cloudflare-cached static delivery → Stories V2 reader.

WordPress is the source of editorial truth; the static JSON snapshot is the public runtime source. This separates publishing risk from reader availability and makes CDN caching predictable.

## WordPress data model

- `viltv_story` (custom post type): stable `slug`, title, synopsis, genre IDs, audience levels, language, cover image/alt text, author, editorial status, published/updated timestamps, estimated reading minutes, content warnings, and canonical URL.
- `viltv_chapter` (custom post type): parent story ID, stable chapter ID, chapter number/order, title, body, optional illustration/alt, language, audience level, and publication state.
- Taxonomies: `story_genre`, `reading_level`, and `story_language`.
- Preserve legacy IDs and genre mapping when importing the existing `STORY_DATA`. Do not discard original text.

### Public JSON contract (v1)

`stories/v1/index.json`: `{ "schemaVersion": 1, "generatedAt": "ISO-8601", "stories": [{ "id": "...", "slug": "...", "title": "...", "genreIds": ["detective"], "levels": ["general"], "chapterCount": 12, "estimatedMinutes": 25, "cover": { "src": "...", "alt": "..." } }] }`

`stories/v1/{slug}.json`: `{ "schemaVersion": 1, "id": "...", "slug": "...", "title": "...", "chapters": [{ "id": "...", "number": 1, "title": "...", "paragraphs": ["..."] }] }`

Required: schema version, stable IDs, unique chapter ordering, nonempty title and chapter text, valid genre and audience level, safe text. Do not trust WordPress HTML as executable content. Reject scripts, event handlers, unsafe URLs and unexpected fields. Limit payload sizes; strip draft/private content from export.

## Performance and accessibility targets

- Serve compressed JSON with `ETag`/`Cache-Control`, CDN caching and explicit purge/versioning at publish time.
- Fetch only the selected story; defer optional covers and prefetch next chapter when appropriate.
- Maintain readable line length (~65–80 characters), minimum 44px touch targets, keyboard navigation, visible focus, semantic headings, reduced-motion support and contrast checks.
- Save progress keyed by **stable story ID + level + content revision**, not one global chapter number.
- Page mode must not break chapters into tiny arbitrary screens; chapter mode and scroll mode should preserve the reader's place on switch.
- Content target: 10–40 **substantial chapters/pages** per requested story length; assess actual word count, plot and editorial quality instead of artificially padding.

## Security / operations

- WordPress admin on a separate hostname; TLS, MFA, least-privilege editorial accounts, core/plugin updates, backups and restricted API credentials.
- The export job uses server-side credentials stored as secrets. **Never embed WordPress application passwords or private endpoints in client-side JS.**
- Only published, approved material exported; no WordPress admin/API write access from the browser.
- Editorial workflow: draft → review → approved → published; validation and content checks in CI.
- Rollback: restore previous immutable JSON snapshot; the old `story.html` remains intact until explicit launch approval.
- Hosting/domain, WordPress provider, export credentials, publishing workflow and CDN purge mechanism are **not yet configured**.

## Implementation milestones

1. Define JSON schema and build local static sample, migrate the first detective story into separate content.
2. Change `stories_v2_preview.html` to load same-origin JSON with offline/error fallback.
3. Implement and test WordPress post types and export adapter **without connecting to a live CMS**.
4. Import existing genres and stories with content QA and stable IDs; expand long-form content.
5. Test mobile/desktop, keyboard, mode switching, resume, slow network, content security and cache behavior.
6. Obtain separate CMS hosting details, set up a staging preview, validate, then request explicit approval for production migration.

## Deployment caveat

The repository's `.github/workflows/deploy-pages.yml` is manually triggered and documents GitHub Pages legacy branch publishing. Do not assume a PR branch is automatically published to Cloudflare or that `stories_v2_preview.html` is live. Use a verified staging URL before asking for UI approval.
