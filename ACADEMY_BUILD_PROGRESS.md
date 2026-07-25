# VilfinTV Academy — Topic Build Progress

Daily automated build of empty Academy topics in `education.html`.
**Build 2 topics per run. Mark each `[x]` when built, validated, committed and pushed.**

## Conventions (follow exactly — audit against existing lessons first)

- **Canonical pattern:** the AI & Robotics hub. Study `AI_LESSONS` (search `const AI_LESSONS`), `renderAiTOC`, `renderAiLesson`, `openAiLesson`, and the `ai-content-area` div in `education.html` before writing anything.
- **One topic = one unit of 5 lessons** appended to its category's lessons array. Lesson schema:
  `{ unit:'Unit N · <Topic>', icon:'<emoji>', title, lead, points:[5-6 '<strong>…</strong> …' strings], analogy, qa:[{q,a},{q,a}] }`
- Teaching style: clear lead paragraph, concrete numbered facts in points, one real-world analogy, two deep Q&As (interview-depth answers, 4-8 sentences). Match the tone and depth of existing `AI_LESSONS` entries.
- **Wiring:** in the subjects index, replace the topic link's `onclick="return false; alert('Coming Soon');"` with the category opener + the unit's start index (e.g. `onclick="openAiLesson(30); return false;"`). NOTE: link text in HTML uses entities (e.g. `Generative AI &amp; LLMs`) — match exact strings when editing.
- **New categories** (no hub yet): clone the AI hub pattern once — `<CATEGORY>_LESSONS` array, `render<Cat>TOC`, `render<Cat>Lesson`, `open<Cat>Lesson(startIdx)`, a `<cat>-content-area` div alongside `ai-content-area`, and register it in `_hideAllLessonAreas`. Then append units as usual.
- **Validation (required every run):** `node validate_jsdom.js` must pass; then load `education.html` in the browser preview, run `open<Cat>Lesson(<newStartIdx>)` via eval, and confirm the lesson renders with no console errors and the TOC lists the new unit.
- **Commit per run** with message `academy: build <Topic 1> + <Topic 2> lessons`, then `git pull --rebase --autostash origin main && git push origin main`.
- Keep CLAUDE.md copywriting rules: no "Free AI" / "No API key" / "Powered by" anywhere.

## Topic queue (32 topics — build top to bottom, 2 per run)

### AI & Robotics (extend AI_LESSONS — hub already exists)
- [x] Natural Language Processing (NLP)
- [x] Computer Vision
- [x] Reinforcement Learning
- [x] Generative AI & LLMs

### Life Skills (new hub: LIFESKILLS_LESSONS)
- [x] Public Speaking
- [x] Time Management
- [x] Emotional Intelligence
- [x] Stress Management

### Computer Science (new hub: CS_LESSONS)
- [x] Data Science
- [x] Cybersecurity
- [x] Operating System
- [x] Computer Network
- [x] Software Engineering

### Emerging Technologies (new hub: EMTECH_LESSONS)
- [x] Cloud Computing
- [x] Blockchain
- [x] Quantum Computing
- [x] Internet of Things (IoT)

### Aerospace Engineering (new hub: AERO_LESSONS)
- [x] Aerodynamics
- [x] Propulsion Systems
- [x] Orbital Mechanics

### Life Sciences & Biotechnology (new hub: BIO_LESSONS)
- [x] Genetic Engineering
- [x] Bioinformatics
- [ ] Molecular Biology

### Mechanical & Mobility (new hub: MECH_LESSONS)
- [ ] Thermodynamics
- [ ] Electric Vehicle (EV) Technology
- [ ] Drone Technology

### Healthcare Innovation (new hub: HEALTH_LESSONS)
- [ ] CRISPR & Gene Editing
- [ ] Telemedicine & Digital Health

### Energy & Climate (new hub: ENERGY_LESSONS)
- [ ] Renewable Energy (Solar & Wind)
- [ ] Battery Storage Technologies
- [ ] Climate Change Mitigation

### Smart Cities (new hub: CITY_LESSONS)
- [ ] Smart Cities Development

## Run log
<!-- append one line per run: date — topics built — validation result -->
- 2026-06-12 — Natural Language Processing (NLP) + Computer Vision (AI_LESSONS units 7-8, idx 27 & 32) — jsdom pass, preview render pass, 0 console errors
- 2026-07-04 — Reinforcement Learning + Generative AI & LLMs (AI_LESSONS units 9-10, idx 36 & 41) — jsdom pass, preview render pass (both lessons + TOC verified via openAiLesson(36)/openAiLesson(41)), 0 console errors
- 2026-07-26 — retro-sync: found Life Skills, Computer Science, Emerging Technologies and Aerospace Engineering hubs were already fully built and wired in earlier feature commits (0f8776fd, 240fe98b, 1ad24347, 311beb5c) before this queue file existed — ticked all 16 topics to match actual code state, no code changes needed for those
- 2026-07-26 — Genetic Engineering + Bioinformatics (new hub BIO_LESSONS, idx 0 & 1) — jsdom pass, preview render pass (both lessons + TOC verified via openBioLesson(0)/openBioLesson(1), plus a real click on the Bioinformatics index link), 0 console errors
