# VilfinTV Stories — Hybrid Cinematic + Literary Editorial Release Gate

Status: in development. Do not merge or deploy solely on this checklist.

## Source of truth
- Canonical public URL: /story.html, including existing ?genre= links.
- Preserve legacy story catalog and story_old.html rollback archive.
- Keep the current working navigation, themes, footer, reader modes, and mobile layout.
- PR #169 is an early prototype; later migration and reader fixes take precedence.

## Rewrite acceptance criteria
1. Audit every published title and each kids/general/expert reading level.
2. Preserve each story's recognizable premise, cast, and genre unless a continuity fix requires a documented change.
3. Rebuild cause-and-effect across setup, inciting incident, rising complications, midpoint reversal, crisis, climax, and resolution.
4. Establish character motivations, credible stakes, distinctive dialogue, and scene transitions.
5. Add foreshadowing and earned revelations; avoid artificial cliffhangers and repeated filler.
6. Aim for substantial 10–40 screen-length reading experiences when narratively justified; measure actual word counts and reading time, not fabricated pages.
7. Kids level must be age-appropriate; expert level must add meaningful complexity rather than relabel the same text.
8. No unresolved contradictions, abrupt endings, missing chapters, duplicated passages, or unsupported factual assertions in educational/health stories.
9. Editorial review each story for readability, tension, emotional resonance, and satisfying closure.

## Release gates
- Inventory and count all published stories and level variants.
- Verify rewritten content renders without JavaScript errors or broken markup.
- Check chapter table of contents, continuous and paginated modes, resume progress, and theme contrast.
- Verify desktop and narrow-mobile widths, keyboard navigation, and accessibility.
- Verify every existing story link and ?genre= deep link remains valid.
- Obtain a reviewed staging preview and record tests before merging to main.
- After deployment, run production smoke checks and be prepared to roll back.

## Deployment rule
Do not mark production complete until the rewritten catalog is committed, reviewed, tested, merged, and the live site verified.
