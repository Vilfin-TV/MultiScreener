# VilfinTV Stories long-form expansion plan

## Scope
Preserve all original catalog titles and genre identifiers, including legacy `triller` URLs. Convert each legacy story to its own `stories/v1/{slug}.json` edition, retaining the original premise and intended kids/general/expert reading levels.

## Editorial length standards
- 10 pages: approximately 2,500–3,000 words (screen/page length varies).
- 40 pages: approximately 10,000–12,000 words.
- 100 pages: approximately 25,000–30,000 words.
- Prefer 8–30 substantial chapters per title, with complete scenes, character arcs, coherent plots, revision and continuity review.
- Count words rather than claiming a fixed number of pages; reading-mode pagination depends on screen width and font size.
- No auto-repeating paragraphs or inflated chapters. Add one title at a time, review it, then publish via GitHub Actions.

## Release sequence
1. Shared navigation, footer, and theme parity with other VilfinTV pages.
2. Expand original Detective, Thriller, Kids, and Adventure/Travel titles first.
3. Continue across Comedy, Health, Education, Animation, and AI.
4. Introduce a visible word count, estimated reading time, per-story reading progress, and editorial completeness status.
5. QA desktop and mobile, plus all genres and chapter navigation.

**Current state:** UI/theme parity work is implemented; long-form expansion of all existing titles is NOT complete. The existing Clockmaker edition is approximately 2,765 words across 12 short chapters.
