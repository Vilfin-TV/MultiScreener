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
- [ ] Natural Language Processing (NLP)
- [ ] Computer Vision
- [ ] Reinforcement Learning
- [ ] Generative AI & LLMs

### Life Skills (new hub: LIFESKILLS_LESSONS)
- [ ] Public Speaking
- [ ] Time Management
- [ ] Emotional Intelligence
- [ ] Stress Management

### Computer Science (new hub: CS_LESSONS)
- [ ] Data Science
- [ ] Cybersecurity
- [ ] Operating System
- [ ] Computer Network
- [ ] Software Engineering

### Emerging Technologies (new hub: EMTECH_LESSONS)
- [ ] Cloud Computing
- [ ] Blockchain
- [ ] Quantum Computing
- [ ] Internet of Things (IoT)

### Aerospace Engineering (new hub: AERO_LESSONS)
- [ ] Aerodynamics
- [ ] Propulsion Systems
- [ ] Orbital Mechanics

### Life Sciences & Biotechnology (new hub: BIO_LESSONS)
- [ ] Genetic Engineering
- [ ] Bioinformatics
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
