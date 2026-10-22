/* Preserved published VilfinTV story catalog for Stories reader migration. */
var CATEGORIES = [
  { id:'detective', label:'Detective', icon:'&#x1F575;', accent:'#d4a44c', cssClass:'story-section-triller', desc:'Original clue-driven mysteries and clever investigations.' },
  { id:'triller',   label:'Triller',   icon:'&#x1F3AC;', accent:'#ef4444', cssClass:'story-section-triller',  desc:'Short cinematic narratives and dramatic micro-stories.' },
  { id:'travel',    label:'Travel',    icon:'&#x2708;',  accent:'#06b6d4', cssClass:'story-section-travel',   desc:'Journeys, destinations, and tales from around the world.' },
  { id:'health',    label:'Health',    icon:'&#x1F3E5;', accent:'#10b981', cssClass:'story-section-health',   desc:'Wellness journeys, medical breakthroughs, and lifestyle stories.' },
  { id:'comedy',    label:'Comedy',    icon:'&#x1F602;', accent:'#f59e0b', cssClass:'story-section-comedy',   desc:'Humorous tales, satire, and feel-good narratives.' },
  { id:'kids',      label:'Kids',      icon:'&#x1F476;', accent:'#ec4899', cssClass:'story-section-kids',     desc:'Fables, adventures, and lessons for young minds.' },
  { id:'education', label:'Education', icon:'&#x1F4DA;', accent:'#6366f1', cssClass:'story-section-education',desc:'Knowledge-driven narratives and learning journeys.' },
  { id:'animation', label:'Animation', icon:'&#x2728;', accent:'#8b5cf6', cssClass:'story-section-animation',desc:'Animated tales, character-driven stories, and visual narratives.' },
  { id:'ai',        label:'AI & Tech',  icon:'&#x1F916;', accent:'#2563eb', cssClass:'story-section-ai',       desc:'Intelligent search, autonomous systems, and neural breakthroughs.' }
];

/* ==========================================================================
   STORY DATA — embedded curated stories with 3 separate comprehension levels
   ========================================================================== */
var STORY_DATA = {};

// Original detective fiction: all three reader levels and paginated chapters.
STORY_DATA.detective = [
  { headline:"The Clockmaker's Missing Minute", teaser:"A stopped clock, a forged alibi and a detective who notices one missing minute.", source:'VilfinTV Detective Originals', publishedAt:'2026-10-22T12:00:00Z', mediaUrl:'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/_default.svg', levels:{
    kids:{headline:"The Clockmaker's Missing Minute", teaser:"A stopped clock, a forged alibi and a detective who notices one missing minute.", source:'Detective Stories for Young Minds',body:[["<p class=\"story-lead\">Inspector Mira examined the clockmaker's workshop after a priceless watch vanished. Every clock read nine, except a pocket watch stopped at 8:59.</p>"],["<p>The apprentice said the power failed at nine. Mira noticed the workshop clocks were mechanical: a blackout could not stop them.</p>"],["<p>The culprit had stopped the clocks by hand to invent an alibi. Grease on the apprentice's sleeve matched the watch case. The watch was recovered beneath a loose floorboard.</p>","<p><strong>Clue to remember:</strong> A mystery is solved by checking whether an explanation fits the evidence.</p>"]]},
    general:{headline:"The Clockmaker's Missing Minute",teaser:"A stopped clock, a forged alibi and a detective who notices one missing minute.",body:[["<p class=\"story-lead\">Inspector Mira examined the clockmaker's workshop after a priceless watch vanished. Every clock read nine, except a pocket watch stopped at 8:59.</p>"],["<p>The apprentice said the power failed at nine. Mira noticed the workshop clocks were mechanical: a blackout could not stop them.</p>"],["<p>The culprit had stopped the clocks by hand to invent an alibi. Grease on the apprentice's sleeve matched the watch case. The watch was recovered beneath a loose floorboard.</p>","<p><strong>Case closed:</strong> A mystery is solved by checking whether an explanation fits the evidence.</p>"]]},
    expert:{headline:"The Clockmaker's Missing Minute — Evidence Analysis",teaser:"A stopped clock, a forged alibi and a detective who notices one missing minute.",body:[["<p class=\"story-lead\">Inspector Mira examined the clockmaker's workshop after a priceless watch vanished. Every clock read nine, except a pocket watch stopped at 8:59.</p>"],["<p>The apprentice said the power failed at nine. Mira noticed the workshop clocks were mechanical: a blackout could not stop them.</p>"],["<p>The culprit had stopped the clocks by hand to invent an alibi. Grease on the apprentice's sleeve matched the watch case. The watch was recovered beneath a loose floorboard.</p>","<p><strong>Deductive principle:</strong> A mystery is solved by checking whether an explanation fits the evidence.</p>"]]}
  } },
  { headline:"The Library of Vanishing Letters", teaser:"A rare manuscript disappears, leaving only a misplaced bookmark.", source:'VilfinTV Detective Originals', publishedAt:'2026-10-22T12:00:00Z', mediaUrl:'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/_default.svg', levels:{
    kids:{headline:"The Library of Vanishing Letters", teaser:"A rare manuscript disappears, leaving only a misplaced bookmark.", source:'Detective Stories for Young Minds',body:[["<p class=\"story-lead\">Detective Arun arrived at the library to find an empty display case. The curator insisted nobody had opened it.</p>"],["<p>A bookmark lay beneath the case, but its paper was warm and faintly smelled of fresh ink. The security log showed the case opened during the printer's maintenance window.</p>"],["<p>Arun checked the bookbinding room. The manuscript had been hidden inside a freshly printed catalogue. The curator's assistant admitted staging the theft to sell it.</p>","<p><strong>Clue to remember:</strong> Small details can reveal the difference between a true story and a rehearsed one.</p>"]]},
    general:{headline:"The Library of Vanishing Letters",teaser:"A rare manuscript disappears, leaving only a misplaced bookmark.",body:[["<p class=\"story-lead\">Detective Arun arrived at the library to find an empty display case. The curator insisted nobody had opened it.</p>"],["<p>A bookmark lay beneath the case, but its paper was warm and faintly smelled of fresh ink. The security log showed the case opened during the printer's maintenance window.</p>"],["<p>Arun checked the bookbinding room. The manuscript had been hidden inside a freshly printed catalogue. The curator's assistant admitted staging the theft to sell it.</p>","<p><strong>Case closed:</strong> Small details can reveal the difference between a true story and a rehearsed one.</p>"]]},
    expert:{headline:"The Library of Vanishing Letters — Evidence Analysis",teaser:"A rare manuscript disappears, leaving only a misplaced bookmark.",body:[["<p class=\"story-lead\">Detective Arun arrived at the library to find an empty display case. The curator insisted nobody had opened it.</p>"],["<p>A bookmark lay beneath the case, but its paper was warm and faintly smelled of fresh ink. The security log showed the case opened during the printer's maintenance window.</p>"],["<p>Arun checked the bookbinding room. The manuscript had been hidden inside a freshly printed catalogue. The curator's assistant admitted staging the theft to sell it.</p>","<p><strong>Deductive principle:</strong> Small details can reveal the difference between a true story and a rehearsed one.</p>"]]}
  } },
  { headline:"The Lighthouse Signal", teaser:"Three flashes across the bay point to a mystery nobody expected.", source:'VilfinTV Detective Originals', publishedAt:'2026-10-22T12:00:00Z', mediaUrl:'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/_default.svg', levels:{
    kids:{headline:"The Lighthouse Signal", teaser:"Three flashes across the bay point to a mystery nobody expected.", source:'Detective Stories for Young Minds',body:[["<p class=\"story-lead\">During a storm, detective Leena saw a lighthouse flash three times even though its lamp had been switched off for repairs.</p>"],["<p>She followed the light to a warehouse window. The flashes repeated whenever a boat approached the rocks.</p>"],["<p>The flashes were a warning sent by a stranded harbor worker using a hand torch. Leena alerted the rescue crew and guided the boat safely home.</p>","<p><strong>Clue to remember:</strong> Not every mysterious signal is a threat; sometimes it is a request for help.</p>"]]},
    general:{headline:"The Lighthouse Signal",teaser:"Three flashes across the bay point to a mystery nobody expected.",body:[["<p class=\"story-lead\">During a storm, detective Leena saw a lighthouse flash three times even though its lamp had been switched off for repairs.</p>"],["<p>She followed the light to a warehouse window. The flashes repeated whenever a boat approached the rocks.</p>"],["<p>The flashes were a warning sent by a stranded harbor worker using a hand torch. Leena alerted the rescue crew and guided the boat safely home.</p>","<p><strong>Case closed:</strong> Not every mysterious signal is a threat; sometimes it is a request for help.</p>"]]},
    expert:{headline:"The Lighthouse Signal — Evidence Analysis",teaser:"Three flashes across the bay point to a mystery nobody expected.",body:[["<p class=\"story-lead\">During a storm, detective Leena saw a lighthouse flash three times even though its lamp had been switched off for repairs.</p>"],["<p>She followed the light to a warehouse window. The flashes repeated whenever a boat approached the rocks.</p>"],["<p>The flashes were a warning sent by a stranded harbor worker using a hand torch. Leena alerted the rescue crew and guided the boat safely home.</p>","<p><strong>Deductive principle:</strong> Not every mysterious signal is a threat; sometimes it is a request for help.</p>"]]}
  } },
  { headline:"The Case of the Silent Violin", teaser:"A concert hall mystery hinges on a single note nobody heard.", source:'VilfinTV Detective Originals', publishedAt:'2026-10-22T12:00:00Z', mediaUrl:'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/_default.svg', levels:{
    kids:{headline:"The Case of the Silent Violin", teaser:"A concert hall mystery hinges on a single note nobody heard.", source:'Detective Stories for Young Minds',body:[["<p class=\"story-lead\">A famous violin disappeared during a rehearsal. Detective Dev questioned the orchestra while the stage crew searched the building.</p>"],["<p>The soloist claimed to have practiced through the break, yet the recording held no violin sound. A fresh line of rosin dust crossed the backstage floor.</p>"],["<p>Dev traced the dust to a storage cabinet where the instrument had been hidden. The soloist had concealed it to prevent a planned fraudulent sale by the manager.</p>","<p><strong>Clue to remember:</strong> Listen for what is missing, not only what is present.</p>"]]},
    general:{headline:"The Case of the Silent Violin",teaser:"A concert hall mystery hinges on a single note nobody heard.",body:[["<p class=\"story-lead\">A famous violin disappeared during a rehearsal. Detective Dev questioned the orchestra while the stage crew searched the building.</p>"],["<p>The soloist claimed to have practiced through the break, yet the recording held no violin sound. A fresh line of rosin dust crossed the backstage floor.</p>"],["<p>Dev traced the dust to a storage cabinet where the instrument had been hidden. The soloist had concealed it to prevent a planned fraudulent sale by the manager.</p>","<p><strong>Case closed:</strong> Listen for what is missing, not only what is present.</p>"]]},
    expert:{headline:"The Case of the Silent Violin — Evidence Analysis",teaser:"A concert hall mystery hinges on a single note nobody heard.",body:[["<p class=\"story-lead\">A famous violin disappeared during a rehearsal. Detective Dev questioned the orchestra while the stage crew searched the building.</p>"],["<p>The soloist claimed to have practiced through the break, yet the recording held no violin sound. A fresh line of rosin dust crossed the backstage floor.</p>"],["<p>Dev traced the dust to a storage cabinet where the instrument had been hidden. The soloist had concealed it to prevent a planned fraudulent sale by the manager.</p>","<p><strong>Deductive principle:</strong> Listen for what is missing, not only what is present.</p>"]]}
  } },
  { headline:"The Blue Umbrella Clue", teaser:"A rainy-night puzzle with two identical umbrellas and one telling difference.", source:'VilfinTV Detective Originals', publishedAt:'2026-10-22T12:00:00Z', mediaUrl:'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/_default.svg', levels:{
    kids:{headline:"The Blue Umbrella Clue", teaser:"A rainy-night puzzle with two identical umbrellas and one telling difference.", source:'Detective Stories for Young Minds',body:[["<p class=\"story-lead\">Detective Sana investigated a missing museum key. Everyone leaving the gallery carried a blue umbrella.</p>"],["<p>One umbrella had dry fabric but wet shoes beneath it. Its owner had never walked through the rain, despite claiming to have just arrived.</p>"],["<p>The dry umbrella belonged to the guard who had remained inside. He had hidden the key in its hollow handle. Sana recovered it before the museum opened.</p>","<p><strong>Clue to remember:</strong> Compare a claim with the physical traces it should leave.</p>"]]},
    general:{headline:"The Blue Umbrella Clue",teaser:"A rainy-night puzzle with two identical umbrellas and one telling difference.",body:[["<p class=\"story-lead\">Detective Sana investigated a missing museum key. Everyone leaving the gallery carried a blue umbrella.</p>"],["<p>One umbrella had dry fabric but wet shoes beneath it. Its owner had never walked through the rain, despite claiming to have just arrived.</p>"],["<p>The dry umbrella belonged to the guard who had remained inside. He had hidden the key in its hollow handle. Sana recovered it before the museum opened.</p>","<p><strong>Case closed:</strong> Compare a claim with the physical traces it should leave.</p>"]]},
    expert:{headline:"The Blue Umbrella Clue — Evidence Analysis",teaser:"A rainy-night puzzle with two identical umbrellas and one telling difference.",body:[["<p class=\"story-lead\">Detective Sana investigated a missing museum key. Everyone leaving the gallery carried a blue umbrella.</p>"],["<p>One umbrella had dry fabric but wet shoes beneath it. Its owner had never walked through the rain, despite claiming to have just arrived.</p>"],["<p>The dry umbrella belonged to the guard who had remained inside. He had hidden the key in its hollow handle. Sana recovered it before the museum opened.</p>","<p><strong>Deductive principle:</strong> Compare a claim with the physical traces it should leave.</p>"]]}
  } }
];

// 1. TRILLER STORIES
STORY_DATA.triller = [
  {
    headline: 'The Last Train Home — A Midnight Crossing',
    teaser: 'When the final train of the night pulls into the station, a lone passenger discovers an unexpected connection that changes everything.',
    source: 'Triller Originals',
    publishedAt: '2026-05-27T14:30:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/triller/the-last-train-home.svg',
    levels: {
      kids: {
        headline: 'The Midnight Magic Train',
        teaser: 'A little girl misses her train, but finds a friendly star-lit train that takes her home and teaches her a wonderful lesson.',
        source: 'Triller Kids',
        body: [
          [
            '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/triller/the-last-train-home.svg" onerror="this.onerror=null;this.src=\'stories/triller/the-last-train-home.svg\'" alt="Magic Train" class="story-visual-img"/></div>',
            '<p class="story-lead">Clang, clang! The big station clock chimed twelve times. It was midnight! Maya sat all by herself on the bench. She was sad because she had missed her regular train home.</p>',
            '<p>She looked around the quiet, dark station and sighed. Just then, a beautiful train painted in dark blue and gold stopped in front of her. The doors opened with a soft whoosh, revealing warm golden light inside.</p>'
          ],
          [
            '<p class="story-lead">Maya stepped inside. Sitting near the window was a kind old man with a long white beard and a shiny gold book. "Hop on, little adventurer!" he said with a warm smile. "This is the Magic Start-Over Train."</p>',
            '<p>As Maya sat down, the train didn\'t roll on metal tracks. Instead, it grew wings of starlight and soared softly into the clear night sky, flying past fluffy clouds and smiling stars!</p>'
          ],
          [
            '<p class="story-lead">The old man opened his golden book. Every page was blank! He handed Maya a crayon and said: "If something went wrong today, tomorrow is a fresh blank page to draw a happy new story. You are the artist of your dreams."</p>',
            '<p>When the magic train landed at Maya\'s station, she felt happy and full of courage. She turned to say goodbye, but the starlight train had already flown back into the sky, leaving her with a warm smile.</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Sometimes, when things don\'t go as planned, it\'s just a chance to start a new and even more exciting adventure! Don\'t be afraid to try again.</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'The Last Train Home — A Midnight Crossing',
        teaser: 'When the final train of the night pulls into the station, a lone passenger discovers an unexpected connection that changes everything.',
        source: 'Triller Originals',
        body: [
          [
            '<p class="story-lead">The station clock struck midnight as the last train of the evening pulled into Platform 3. Maya had missed the earlier connection by three minutes, and now she was the only passenger waiting in the cavernous, drafty hall.</p>',
            '<p>As the heavy train doors hissed open, she stepped inside the empty carriage. Sitting at the far end was an elderly man in a worn trench coat, holding a leather-bound journal. He looked up and smiled, the kind of knowing smile that suggested he had been expecting her all along.</p>'
          ],
          [
            '<p class="story-lead">"Going home?" the old man asked, his voice gravelly but kind. Maya nodded reluctantly, sitting across from him. "Funny thing about home," he continued, "it is never quite where you left it."</p>',
            '<p>He revealed he had ridden this line for forty years, collecting stories of passengers. With nothing left to lose, Maya shared her own burden: a career in ruins, a broken relationship, and a city that no longer felt like her own.</p>'
          ],
          [
            '<p class="story-lead">The old man listened in silence, then flipped to a clean page in his journal, tore it out, and offered it to her: "Write the next chapter. Write the one you are heading toward, not the one you are running from."</p>',
            '<p>When the train finally reached Maya\'s stop, she stepped onto the platform with hope. She turned to thank the old traveler, but the carriage was entirely empty. On the seat lay the blank page, and on it was a single word written in fresh ink: <strong>Begin.</strong></p>'
          ]
        ]
      },
      expert: {
        headline: 'Narrative Transitions: Psychological Archetypes of "The Last Train"',
        teaser: 'A critical structural analysis of transitional spaces, seeking behaviors, and the archetype of the mentor in modern short fiction.',
        source: 'Narrative Research Journal',
        body: [
          [
            '<p class="story-lead">Maya\'s midnight transit serves as a classic liminal space—a physical and temporal threshold where the protagonist is stripped of familiar structures and forced into self-reflective dialogue.</p>',
            '<p>The introduction of the elderly mentor in liminal space acts as an externalization of Maya\'s subconscious seeking behavior. The journal is not merely a prop but a semiotic symbol of the unwritten future, contrasting with her fixation on past failures.</p>'
          ],
          [
            '<p class="story-lead">Liminality operates outside ordinary temporal constraints, facilitating an accelerated psychological shift in the passenger. The train carriage functions as a therapeutic chamber, isolating the ego from external noise.</p>',
            '<p>The chronicler represents the Jungian "Wise Old Man" who does not solve the hero\'s crisis but provides the agency (the blank page) to resolve it, forcing the hero to take responsibility for narrative progression.</p>'
          ],
          [
            '<p class="story-lead">The vanishing of the mentor reinforces that the encounter was internal, leaving behind a tangible anchor (the text "Begin") that bridges the psychological breakthrough to reality.</p>',
            '<p>Ultimately, the story demonstrates how transitional spaces can be leveraged in narrative structure to evoke a deep psychological pivot in the protagonist, converting passive escaping into active beginning.</p>'
          ]
        ]
      }
    }
  },
  {
    headline: 'Echoes in the Rain — A Ghost in the Alley',
    teaser: 'A photographer chasing the perfect shot stumbles into a rain-drenched alley where the past refuses to stay buried.',
    source: 'Triller Originals',
    publishedAt: '2026-05-26T10:15:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/triller/echoes-in-the-rain.svg',
    levels: {
      kids: {
        headline: 'The Dancing Raindrop Girl',
        teaser: 'A friendly photographer finds a magical chest in the rain that holds a happy secret about an old-time dancer.',
        source: 'Triller Kids',
        body: [
          [
            '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/triller/echoes-in-the-rain.svg" onerror="this.onerror=null;this.src=\'stories/triller/echoes-in-the-rain.svg\'" alt="Rainy Alley" class="story-visual-img"/></div>',
            '<p class="story-lead">Splash, splash! Danny loved walking in the warm summer rain. He wore shiny yellow boots and carried a small camera. He loved taking pictures of wet streets that looked like glowing mirrors.</p>',
            '<p>One evening, as he walked past a quiet, dark alley, he saw a beautiful glowing light dancing on the brick wall. It looked like a dancing fairy!</p>'
          ],
          [
            '<p class="story-lead">Danny slowly walked into the alley. Beneath a loose wooden board, he found a hidden, dusty chest. Inside was a beautiful red dress and a golden music box.</p>',
            '<p>When he wound up the music box, a sweet, happy song played. Suddenly, a friendly, glowing shadow of a girl appeared, dancing happily in the puddles!</p>'
          ],
          [
            '<p class="story-lead">Danny took a picture of the dancing shadow, and she waved to him with a happy smile before disappearing back into the music box.</p>',
            '<p>He learned that her name was Clara, a famous dancer from the past who loved the rain. Now, Clara\'s happy memory will stay in Danny\'s picture forever!</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Beautiful music and happy memories never really disappear. They stay in the world to bring smiles to people many years later!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'Echoes in the Rain — A Ghost in the Alley',
        teaser: 'A photographer chasing the perfect shot stumbles into a rain-drenched alley where the past refuses to stay buried.',
        source: 'Triller Originals',
        body: [
          [
            '<p class="story-lead">The rain came down in sheets, blurring the neon signs of the old district into smears of pink and blue. Daniel raised his camera, framing the narrow alley that wound between two decaying apartment blocks.</p>',
            '<p>Through the viewfinder, he saw her: a woman in a bright red dress, standing perfectly still at the far end of the alley, letting the rain wash over her.</p>'
          ],
          [
            '<p class="story-lead">But when Daniel lowered the camera, the alley was completely empty. He checked his digital display—the woman in red was clearly visible in the photograph, though her face remained blurred.</p>',
            '<p>Compelled by curiosity, he researched the municipal archives. He discovered that in 1947, a young stage dancer named Clara had lived in that very building and vanished on a rainy night.</p>'
          ],
          [
            '<p class="story-lead">With the building scheduled for demolition the next morning, Daniel slipped inside. Beneath the floorboards of Clara\'s old apartment, he found a locked chest containing her diary and letters.</p>',
            '<p>The final entry was a letter addressed to "the photographer who would find her." Clara had left her archive to ensure her art and story would be remembered by the city she loved.</p>'
          ]
        ]
      },
      expert: {
        headline: 'Phantasmagoria and Photography: Clara\'s Echoes in Post-War Urbanity',
        teaser: 'An analytical review of photographic mediumship, memory preservation, and Clara\'s spatial lingering in pre-demolition architecture.',
        source: 'Visual Studies Quarterly',
        body: [
          [
            '<p class="story-lead">Daniel\'s photographic encounter operates as a classic liminal intersection, wherein the camera sensor acts as a medium that translates spatial-temporal memory traces into visual artifacts.</p>',
            '<p>Clara\'s manifestation represents "spatial lingering," a phenomenon where high-emotion events imprint upon the physical architecture of a space, surviving long after the original subjects have departed.</p>'
          ],
          [
            '<p class="story-lead">The imminent demolition of the apartment complex serves as a catalyst, threatening to erase the physical coordinates of this historical memory and forcing the artifact (the archive) to emerge.</p>',
            '<p>Daniel\'s discovery of the wooden chest functions as a crucial "archival recovery," shifting Clara\'s story from a haunting spatial loop into a stable, recorded historical narrative.</p>'
          ],
          [
            '<p class="story-lead">This transition proves that photographic technology does not merely reproduce reality, but acts as a dynamic bridge across temporal planes, rescuing lost human histories from systemic erasure.</p>',
            '<p>Ultimately, the text demonstrates that the preservation of personal narratives is essential to counter the sterile gentrification and rapid physical restructuring of modern urban spaces.</p>'
          ]
        ]
      }
    }
  },
  {
    headline: 'Neon Noir — The Detective Who Knew Too Little',
    teaser: 'In a city that never sleeps, a washed-up detective takes on one last case that may either redeem or destroy him.',
    source: 'Triller Originals',
    publishedAt: '2026-05-24T08:45:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/triller/neon-noir.svg',
    levels: {
      kids: {
        headline: 'The Mystery of the Missing Photo',
        teaser: 'A retired detective uses clues to help an old friend find a lost bank box, learning that truth is always the best path.',
        source: 'Triller Kids',
        body: [
          [
            '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/triller/neon-noir.svg" onerror="this.onerror=null;this.src=\'stories/triller/neon-noir.svg\'" alt="Detective" class="story-visual-img"/></div>',
            '<p class="story-lead">Detective Roy was a very wise man with a big magnifying glass and a cozy office. He loved solving puzzles and helping people in his neighborhood find lost things.</p>',
            '<p>One sunny morning, a letter arrived at his door. Inside was an old picture of a beautiful brick building. "Help me find what was hidden here," the letter read.</p>'
          ],
          [
            '<p class="story-lead">Roy looked closely at the picture. He noticed the building was a very old bank that had been replaced by a playground. He packed his bag and walked over to investigate.</p>',
            '<p>He looked behind the old oak tree and checked the library books. Roy discovered that a kind old man named Mr. Green had hidden a box of old toys there long ago.</p>'
          ],
          [
            '<p class="story-lead">With the help of the children playing nearby, Roy found the shiny metal box buried under a soft patch of grass. Inside were lovely old coins and toy soldiers!</p>',
            '<p>Mr. Green was so happy to see his childhood toys again. He thanked Roy and shared the coins with the helpful children, who cheered for the clever detective.</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Using your mind to solve puzzles and help others is a wonderful way to be a hero in your community! Always tell the truth and share with others!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'Neon Noir — The Detective Who Knew Too Little',
        teaser: 'In a city that never sleeps, a washed-up detective takes on one last case that may either redeem or destroy him.',
        source: 'Triller Originals',
        body: [
          [
            '<p class="story-lead">Detective Roy Callahan had not taken a case in three years. His office was dusty, and his repute was tarnished. But when an envelope containing a thousand-dollar retainer arrived, he couldn\'t ignore it.</p>',
            '<p>Inside was a single photograph of a man standing in front of the municipal bank. On the back was a cryptic message: "The truth has a price. Are you willing to pay it?"</p>'
          ],
          [
            '<p class="story-lead">Roy traced the building in the photograph to a bank that had been demolished in 1982 following a legendary heist. He researched the archives, seeking the identity of the mysterious man.</p>',
            '<p>He discovered the man was Arthur Vance, the bank\'s head clerk, who was accused of the robbery and vanished shortly after the heist, labeled a fugitive.</p>'
          ],
          [
            '<p class="story-lead">Following a trail of old newspaper listings, Roy located Vance living quietly under an alias in a retirement home. Vance revealed the heist was a cover-up by corrupt city officials.</p>',
            '<p>Roy now faced a dangerous choice: publish the evidence and clear Vance\'s name at great personal risk, or destroy the files and let the historical lie remain. He chose justice.</p>'
          ]
        ]
      },
      expert: {
        headline: 'Systemic Corruption and Whistleblower Protection: The 1982 Legacy',
        teaser: 'A legal and investigative deep-dive into Callahan\'s pursuit of corporate accountability and retrofitted justice.',
        source: 'Legal Criminology Review',
        body: [
          [
            '<p class="story-lead">Callahan\'s investigation into the 1982 municipal bank heist serves as a critical case study in institutional corruption and the systemic failures of whistleblower protection.</p>',
            '<p>The label of "fugitive" applied to Arthur Vance was a deliberate framing tactic used by corporate actors and complicit law enforcement to discredit his attempt to expose embezzlement.</p>'
          ],
          [
            '<p class="story-lead">The absence of legislative safeguards in the late 20th century forced whistleblowers to adopt extreme survival strategies, including identity alteration and complete social withdrawal.</p>',
            '<p>Callahan\'s archival research highlights the importance of "retrofitted justice," where independent investigators correct the public record long after the statue of limitations has expired.</p>'
          ],
          [
            '<p class="story-lead">Ultimately, the case demonstrates that corporate transparency cannot rely solely on internal compliance mechanisms, requiring robust, independent legal frameworks to protect witnesses.</p>',
            '<p>By publishing the Vance papers, Callahan highlights the role of investigative journalism in challenging historical revisionism and exposing systemic failures in municipal governance.</p>'
          ]
        ]
      }
    }
  }
];

// 2. TRAVEL STORIES
STORY_DATA.travel = [
  {
    headline: 'The Silk Road Solo — RETRACING ANCIENT TRAILWAYS',
    teaser: 'One traveller retraces the ancient Silk Road through Central Asia — discovering that the greatest journeys happen within.',
    source: 'Travel Chronicles',
    publishedAt: '2026-05-25T12:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/travel/the-silk-road-solo.svg',
    levels: {
      kids: {
        headline: 'Liam\'s Mountain Adventure',
        teaser: 'Liam travels to big snowy mountains, rides beautiful yaks, and learns that making friends is the best part of any trip.',
        source: 'Travel Kids',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/travel/the-silk-road-solo.svg" onerror="this.onerror=null;this.src=\'stories/travel/the-silk-road-solo.svg\'" alt="Mountains" class="story-visual-img"/></div>',
          '<p class="story-lead">Liam packed a big backpack and went on a journey to a far-away land with giant, snowy mountains. He stayed in a round, cozy tent called a yurt!</p>',
          '<p>A friendly local family welcomed him. They taught Liam how to ride a gentle yak and bake fluffy round bread over a warm fire. At night, they looked up at the sky, which was completely filled with bright, twinkling stars.</p>',
          '<p>A kind wise hunter told Liam: "Getting lost is just another way to find a new friend." Liam smiled, knowing he would always remember this beautiful place.</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Travel is not just about seeing new places; it is about sharing kindness with strangers and learning how other people live!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Silk Road Solo — RETRACING ANCIENT TRAILWAYS',
        teaser: 'One traveller retraces the ancient Silk Road through Uzbekistan, Kyrgyzstan, and Kazakhstan — discovering that the greatest journeys happen within.',
        source: 'Travel Chronicles',
        body: [
          '<p class="story-lead">The idea had been brewing for years — a solo trip across the heart of Central Asia, following the ancient trade routes that once connected East and West.</p>',
          '<p>Uzbekistan welcomed him with azure-tiled mosques and the scent of plov. But it was in the Pamir Mountains of Kyrgyzstan that the journey truly began.</p>',
          '<ul class="story-bullets">',
          '  <li>Three weeks living with a nomadic family in a yurt, learning to herd yaks and bake bread over an open fire.</li>',
          '  <li>A midnight trek to a hot spring under a sky so full of stars it felt like falling into the universe.</li>',
          '  <li>An unexpected friendship with a 72-year-old Kazakh eagle hunter who taught him that "a man who has not been lost has never truly travelled."</li>',
          '</ul>',
          '<p>By the time he reached Almaty, Liam had found something better than destination goals: the understanding that the road itself was the teacher, and that every stranger carries a story worth hearing.</p>'
        ]
      },
      expert: {
        headline: 'Central Asian Nomadic Sociology: Pamir Highway Adaptations',
        teaser: 'A critical ethnographic survey of modern pastoral nomadism, domestic tourism integration, and heritage commodification along the Silk Road.',
        source: 'Pamir Ethnography Journal',
        body: [
          '<p class="story-lead">Liam\'s crossing of the Pamir Highway offers an observation of the delicate balance between historical pastoral lifestyle and global eco-tourism networks.</p>',
          '<p>The Kyrgyz yurt stays (jailoo tourism) represent a community-based economic adaptation that allows pastoral families to diversify income while preserving seasonal migration patterns. Yet, it introduces cultural commodification risks.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Economic Diversification:</strong> Eco-lodging offsets risks associated with livestock mortality due to winter extreme weather events (dzhut).</li>',
          '  <li><strong>Intergenerational Knowledge Transfer:</strong> Interacting with foreign travelers provides capital that enables youth to stay in rural districts rather than migrating to urban centers.</li>',
          '</ul>',
          '<p>In conclusion, contemporary Silk Road travel serves as a vehicle for sustainable rural development, transforming heritage preservation into a viable livelihood strategy for mountain communities.</p>'
        ]
      }
    }
  },
  {
    headline: 'Islands of Solitude — Finding Peace in the Faroe Islands',
    teaser: 'A burned-out executive trades boardroom meetings for sheep-dotted cliffs and discovers a different definition of success.',
    source: 'Travel Chronicles',
    publishedAt: '2026-05-23T09:30:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/travel/islands-of-solitude.svg',
    levels: {
      kids: {
        headline: 'Nina and the Woolly Sheep Islands',
        teaser: 'Nina visits a green island filled with fluffy sheep, learns to knit, and finds out that quiet time is very good for the heart.',
        source: 'Travel Kids',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/travel/islands-of-solitude.svg" onerror="this.onerror=null;this.src=\'stories/travel/islands-of-solitude.svg\'" alt="Faroe Islands" class="story-visual-img"/></div>',
          '<p class="story-lead">Nina had a very busy job and felt very tired. She wanted to go somewhere quiet. So, she traveled to a group of green islands called the Faroe Islands.</p>',
          '<p>There were more fluffy sheep than people on the islands! Nina walked on green cliffs and watched beautiful waterfalls splash into the sea. She spent time with a kind grandmother who taught her how to knit soft woolly hats.</p>',
          '<p>Nina loved the quiet islands. She decided to build a cozy house there to help other tired travelers take a happy rest.</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Taking a break and spending quiet time in nature is important. It helps us feel happy, healthy, and ready for new things!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'Islands of Solitude — Finding Peace in the Faroe Islands',
        teaser: 'A burned-out executive trades boardroom meetings for sheep-dotted cliffs and discovers a different definition of success.',
        source: 'Travel Chronicles',
        body: [
          '<p class="story-lead">After fifteen years in investment banking, Nina collapsed at her desk. She took a six-month sabbatical and booked a flight to the Faroe Islands.</p>',
          '<p>The islands were everything the corporate world was not: windswept, raw, and quiet. There were more sheep than people, and the silence helped her stop worrying about email notifications.</p>',
          '<ul class="story-bullets">',
          '  <li>She hiked to the edge of Lake Sorvagsvatn, the famous "lake above the ocean," feeling a deep sense of calm.</li>',
          '  <li>She learned to knit and cook traditional meals from local residents.</li>',
          '  <li>She watched the Northern Lights dance over the village of Gjogv.</li>',
          '</ul>',
          '<p>Nina did not return to banking. Instead, she opened a small guesthouse on the islands to host travellers seeking the same quiet environment that saved her.</p>'
        ]
      },
      expert: {
        headline: 'Decentralization and Quiet Tourism: The Faroe Islands Economic Pivot',
        teaser: 'A geopolitical analysis of sustainable tourism, rural revitalization, and structural mental health corrections away from urban congestion.',
        source: 'Nordic Development Review',
        body: [
          '<p class="story-lead">Nina\'s escape to the Faroe archipelago highlights the growing trend of "quiet tourism"—a deliberate counter-movement to mass urban travel that prioritizes low-impact, high-value ecological exchanges.</p>',
          '<p>For isolated economies like the Faroes, this model provides crucial capital without putting excessive strain on local infrastructure, showcasing how micro-hospitality can sustain remote communities.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Infrastructure Limits:</strong> The Faroe Islands utilize strict trail regulation and off-season closures to prevent ecological degradation.</li>',
          '  <li><strong>Psychological Decoupling:</strong> The reduction in cortisol and anxiety symptoms is directly linked to immersive natural environments (biophilic restoration).</li>',
          '</ul>',
          '<p>This study demonstrates that rural decentralization benefits not only regional economies but also provides critical therapeutic spaces for highly stressed urban populations.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Trans-Siberian Chronicle — 9,289 Kilometres of Stories',
    teaser: 'Seven days on the legendary Trans-Siberian Railway reveals the soul of Russia through the lives of its passengers.',
    source: 'Travel Chronicles',
    publishedAt: '2026-05-21T14:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/travel/the-trans-siberian-chronicle.svg',
    levels: {
      kids: {
        headline: 'Marcus\'s Great Train Ride',
        teaser: 'Marcus goes on a giant train ride across the snowy forest, sharing food and games with new friends on the way.',
        source: 'Travel Kids',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/travel/the-trans-siberian-chronicle.svg" onerror="this.onerror=null;this.src=\'stories/travel/the-trans-siberian-chronicle.svg\'" alt="Train Tracks" class="story-visual-img"/></div>',
          '<p class="story-lead">Choo-choo! Marcus climbed aboard a very long train that would travel for seven whole days across beautiful snowy forests and green fields.</p>',
          '<p>During the long ride, Marcus met many nice people. A friendly grandmother shared her sweet strawberry jam, and a young boy showed Marcus how to build paper airplanes. They didn\'t speak the same language, but they laughed and played together every day!</p>',
          '<p>When the train reached the end, Marcus was happy. He learned that sharing and smiling can make friends anywhere in the world.</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">You don\'t need to speak the same language to share kindness and be a good friend. A smile and a shared treat can bridge any gap!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Trans-Siberian Chronicle — 9,289 Kilometres of Stories',
        teaser: 'Seven days on the legendary Trans-Siberian Railway reveals the soul of the country through the lives of its passengers.',
        source: 'Travel Chronicles',
        body: [
          '<p class="story-lead">The Trans-Siberian Railway is not just a train journey — it is a moving village, a microcosm of humanity hurtling across vast forests and plains.</p>',
          '<p>Over seven days and seven time zones, Marcus shared compartment meals and stories with a diverse cast of fellow travellers.</p>',
          '<ul class="story-bullets">',
          '  <li>A retired dancer heading to Vladivostok to see her grandson, carrying a single photograph and a jar of jam.</li>',
          '  <li>A young soldier returning home, who communicated through shared meals of black bread and smoked fish.</li>',
          '  <li>An executive who confessed, over tea, that he envied Marcus\'s simple freedom more than his own wealth.</li>',
          '</ul>',
          '<p>When the train finally pulled into its destination, Marcus realized the landscapes had been stunning, but it was the shared stories of strangers that he would carry with him forever.</p>'
        ]
      },
      expert: {
        headline: 'Trans-Siberian Mobility: Compartment Sociality & Intersectional Classes',
        teaser: 'A sociopolitical analysis of the Trans-Siberian Railway, exploring class mixing, compartmentalized intimacy, and passenger networks.',
        source: 'Journal of Transport Sociology',
        body: [
          '<p class="story-lead">The Trans-Siberian Railway serves as a unique sociological laboratory where strict structural class boundaries dissolve within the shared spatial confines of a second-class (Platskart) carriage.</p>',
          '<p>Marcus\'s interactions illustrate "compartment sociality"—a phenomenon where forced proximity over extended durations compels passengers to establish high-trust micro-communities.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Class Convergence:</strong> Executive, soldier, and retiree interact on equal footing, bypassing external status indicators.</li>',
          '  <li><strong>Gift Economy:</strong> The sharing of food (jam, bread, tea) acts as a mutual contract that preserves peace and builds communal bonds.</li>',
          '</ul>',
          '<p>In conclusion, the railway acts as an equalizer, showcasing how shared physical transit networks can facilitate deep cross-class communication in modern societies.</p>'
        ]
      }
    }
  }
];

// 3. HEALTH STORIES
STORY_DATA.health = [
  {
    headline: 'The Blue Zone Secret — Secrets of the Longest-Lived People',
    teaser: 'Researchers spent decades studying communities where people routinely live past 100. The secret is simpler than anyone imagined.',
    source: 'Health & Wellness',
    publishedAt: '2026-05-26T07:30:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/health/the-blue-zone-secret.svg',
    levels: {
      kids: {
        headline: 'The Happy Centenarian Garden',
        teaser: 'In a beautiful village, grandpas and grandmas live to be 100 years old! They share their secrets of eating plants and playing together.',
        source: 'Health Kids',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/health/the-blue-zone-secret.svg" onerror="this.onerror=null;this.src=\'stories/health/the-blue-zone-secret.svg\'" alt="Fresh Vegetables" class="story-visual-img"/></div>',
          '<p class="story-lead">In a beautiful village near the sea, grandpas and grandmas live to be super old, healthy, and happy. They can run, garden, and play even at 100 years old!</p>',
          '<p>Scientists visited them and found out their secrets. First, they eat lots of fresh green vegetables and sweet fruits. Second, they walk in their gardens every single day. Third, they spend lots of time playing games with their families and friends.</p>',
          '<p>They don\'t run on boring treadmills; they just live active, happy lives together! A kind grandma said: "We don\'t try to live long; we just try to live happy."</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Eating fresh vegetables, running around outside, and playing with your friends are the absolute best secrets to staying strong and happy!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Blue Zone Secret — Secrets of the Longest-Lived People',
        teaser: 'Researchers spent decades studying communities where people routinely live past 100. The secret is simpler than anyone imagined.',
        source: 'Health & Wellness',
        body: [
          '<p class="story-lead">In five pockets around the world — from Okinawa, Japan, to Sardinia, Italy — people live extraordinarily long, healthy lives. They do not follow fad diets; their longevity is woven into daily life.</p>',
          '<p>Dr. Marco Santini spent fifteen years studying these "Blue Zones" and discovered that their health is a natural byproduct of their lifestyle.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>The 80% Rule:</strong> Okinawans stop eating when they are 80% full, naturally limiting excess caloric intake.</li>',
          '  <li><strong>Natural Movement:</strong> Residents do not go to gyms. Instead, they walk to the market, tend gardens, and climb hills.</li>',
          '  <li><strong>Purpose & Connection:</strong> Strong family bonds and a clear reason to wake up in the morning reduce stress and support mental health.</li>',
          '</ul>',
          '<p>The most striking finding: none of these people were trying to live long. Longevity was simply the natural result of living well in a supportive community.</p>'
        ]
      },
      expert: {
        headline: 'Biogerontology of Blue Zones: Epigenetic and Social Determinants',
        teaser: 'A comprehensive scientific review of telomere maintenance, dietary restrictions, and community support in long-lived populations.',
        source: 'Biogerontology Journal',
        body: [
          '<p class="story-lead">The phenotypic longevity observed in Blue Zones (e.g., Sardinia, Nicoya, Okinawa) provides empirical proof of the impact of epigenetics and social infrastructure on healthspan.</p>',
          '<p>Dr. Santini\'s work indicates that the suppression of age-related cardiovascular and cognitive diseases is not purely genetic, but rather modulated by persistent environmental factors.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Caloric Restriction (CR):</strong> The practice of "hara hachi bu" down-regulates the mTOR pathway, promoting cellular autophagy and reducing metabolic stress.</li>',
          '  <li><strong>Active Transport:</strong> Continuous low-intensity physical activity maintains cardiorespiratory fitness without inducing systemic inflammatory responses.</li>',
          '  <li><strong>Social Buffering:</strong> Robust social integration reduces chronic cortisol levels, protecting telomere length from degradation.</li>',
          '</ul>',
          '<p>In conclusion, longevity is systemic. Interventions targeting individual health should prioritize modifying structural environments rather than relying on pharmacological solutions.</p>'
        ]
      }
    }
  },
  {
    headline: 'Running from Darkness — Grief Recovery Through Movement',
    teaser: 'After losing her brother to suicide, a woman discovers that putting one foot in front of the other is the most powerful medicine.',
    source: 'Health & Wellness',
    publishedAt: '2026-05-24T19:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/health/running-from-darkness.svg',
    levels: {
      kids: {
        headline: 'Rebecca\'s Bright Running Shoes',
        teaser: 'Rebecca gets active to help her heart feel happy again after a very sad loss, discovering that movement brings back the sunshine.',
        source: 'Health Kids',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/health/running-from-darkness.svg" onerror="this.onerror=null;this.src=\'stories/health/running-from-darkness.svg\'" alt="Running Shoes" class="story-visual-img"/></div>',
          '<p class="story-lead">Rebecca felt very sad and lonely. Her heart was heavy, and she didn\'t want to play or go outside. She felt like a dark cloud was following her around.</p>',
          '<p>One morning, she put on her bright red running shoes and took a small walk to the end of the street. The next day, she jogged a little bit farther. With every step, she felt the warm sunshine on her face and the fresh air in her lungs.</p>',
          '<p>Rebecca started running with a group of friends. She found out that moving her body helped wash away the sad feelings. She even ran a long race, waving to her family with a big smile!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">When you feel sad or scared, taking a small walk or running outside can help clear your mind and bring back your happy smiles!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'Running from Darkness — Grief Recovery Through Movement',
        teaser: 'After losing her brother, a woman discovers that putting one foot in front of the other is the most powerful medicine.',
        source: 'Health & Wellness',
        body: [
          '<p class="story-lead">When her younger brother Alex passed away, Rebecca\'s world collapsed. For months, she struggled with deep grief, barely leaving her apartment.</p>',
          '<p>One morning, almost on autopilot, she put on an old pair of running shoes and walked to the end of her street. The next day, she made it two blocks. Soon, she was running.</p>',
          '<ul class="story-bullets">',
          '  <li>Running became her therapy — the rhythmic movement serving as a meditation that quieted her mind.</li>',
          '  <li>She joined a local running group and discovered others using movement to heal from their own struggles.</li>',
          '  <li>After three years of training, Rebecca completed her first marathon in memory of her brother.</li>',
          '</ul>',
          '<p>"I found out that movement is the antidote to despair," she says. "As long as I am moving forward, I am reclaiming my life."</p>'
        ]
      },
      expert: {
        headline: 'Neurobiology of Exercise-Induced Trauma Recovery',
        teaser: 'An investigation into running-induced neurogenesis, BDNF regulation, and somatic processing of acute grief and trauma.',
        source: 'Psychiatric Neuroscience Journal',
        body: [
          '<p class="story-lead">Rebecca\'s recovery from severe grief-induced depression highlights the role of somatic movement in treating psychological trauma.</p>',
          '<p>Aerobic exercise acts directly on the central nervous system, stimulating neurogenesis in the hippocampus and reversing the structural damage caused by sustained stress and cortisol exposure.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>BDNF Expression:</strong> High-intensity aerobic activity raises Brain-Derived Neurotrophic Factor levels, supporting cognitive health.</li>',
          '  <li><strong>Endocannabinoid Release:</strong> The "runner\'s high" is primarily driven by anandamide, which binds to CB1 receptors to alleviate anxiety.</li>',
          '  <li><strong>Somatic Processing:</strong> Rhythmic movement helps release stored muscle tension associated with traumatic stress.</li>',
          '</ul>',
          '<p>These insights highlight why physical exercise should be integrated alongside talk therapy in comprehensive mental health and trauma recovery protocols.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Microbiome Revolution — Your Gut is Your Second Brain',
    teaser: 'Groundbreaking research reveals that the trillions of bacteria living in your digestive system control more than just digestion.',
    source: 'Health & Wellness',
    publishedAt: '2026-05-22T13:45:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/health/the-microbiome-revolution.svg',
    levels: {
      kids: {
        headline: 'The Tiny Helpers inside Your Tummy',
        teaser: 'Did you know you have millions of tiny friendly helpers inside your tummy? Feed them apples and broccoli to keep them happy!',
        source: 'Health Kids',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/health/the-microbiome-revolution.svg" onerror="this.onerror=null;this.src=\'stories/health/the-microbiome-revolution.svg\'" alt="Fresh Fruit" class="story-visual-img"/></div>',
          '<p class="story-lead">Inside your tummy lives a giant family of tiny, invisible helpers! They are so small you can\'t see them, but they work hard every day to keep you strong.</p>',
          '<p>These tiny helpers love healthy foods like sweet apples, green broccoli, and yogurt. When you eat healthy food, the helpers jump for joy and send happy messages to your brain, making you feel cheerful and energetic!</p>',
          '<p>But if you eat too much candy, the helpers get sleepy and sad. So, let\'s feed our tummy helpers wonderful fruits and vegetables to keep them whistling!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Feeding your body healthy foods keeps the tiny helpers in your tummy happy, which makes your whole body feel strong and cheerful!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Microbiome Revolution — Your Gut is Your Second Brain',
        teaser: 'Groundbreaking research reveals that the trillions of bacteria living in your digestive system control more than just digestion.',
        source: 'Health & Wellness',
        body: [
          '<p class="story-lead">For decades, scientists viewed gut bacteria as simple digestive helpers. But new research reveals they directly influence our mood, immune system, and brain health.</p>',
          '<p>Dr. Amara Osei has been exploring the gut-brain axis, uncovering connections that are transforming modern medicine.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Mood Regulation:</strong> Gut bacteria produce up to 90% of the body\'s serotonin, the chemical that makes us feel happy.</li>',
          '  <li><strong>Immune Support:</strong> Nearly 70% of our immune system lives in our gut, trained by bacteria to fight off illnesses.</li>',
          '  <li><strong>Practical Steps:</strong> Eating fibre, fermented foods (like yogurt), and diverse plants can improve gut health in just two weeks.</li>',
          '</ul>',
          '<p>"We are not just what we eat," Dr. Osei explains. "We are what our microbes eat. Cultivating a healthy bacterial ecosystem is essential for overall well-being."</p>'
        ]
      },
      expert: {
        headline: 'The Enteric Nervous System and Gut-Brain Axis Signaling',
        teaser: 'A technical molecular analysis of vagus nerve communication, microbial metabolite diversity, and systemic inflammation.',
        source: 'Gastroenterology Journal',
        body: [
          '<p class="story-lead">The bidirectional communication network known as the gut-brain axis relies on neural, endocrine, and immune signaling pathways to maintain systemic balance.</p>',
          '<p>Dr. Osei\'s research shows that the enteric nervous system (ENS) communicates directly with the central nervous system via the vagus nerve, modulated by microbial metabolites.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Short-Chain Fatty Acids (SCFAs):</strong> Fermented dietary fiber yields acetate, propionate, and butyrate, which maintain blood-brain barrier integrity.</li>',
          '  <li><strong>Neurotransmitter Synthesis:</strong> Gut microbes modulate precursors for GABA and serotonin, directly influencing neurochemical states.</li>',
          '  <li><strong>Pro-inflammatory Cytokines:</strong> Dysbiosis increases intestinal permeability, allowing toxins into the bloodstream and triggering systemic neuroinflammation.</li>',
          '</ul>',
          '<p>These findings suggest that clinical psychiatric protocols should incorporate targeted dietary interventions and probiotics to support brain health via the gut microbiome.</p>'
        ]
      }
    }
  }
];

// 4. COMEDY STORIES
STORY_DATA.comedy = [
  {
    headline: 'The Accidental Billionaire — A Satirical Pitch Guide',
    teaser: 'Mistaken identity, a malfunctioning coffee machine, and one very confused venture capitalist collide in this tale of accidental success.',
    source: 'Comedy Central',
    publishedAt: '2026-05-27T10:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/comedy/the-accidental-billionaire.svg',
    levels: {
      kids: {
        headline: 'Tommy\'s Magic Toy Wrench',
        teaser: 'Tommy goes to fix a broken kitchen machine but accidentally invents a silly game about cat pictures that makes everyone laugh!',
        source: 'Comedy Kids',
        body: [
          [
            '<p class="story-lead">Tommy was a friendly young helper who loved to fix broken toy machines. One afternoon, he went to a big office building carrying a funny red wrench and a folder of drawings.</p>',
            '<p>He took the elevator to the top floor, but he got turned around and walked into the wrong conference room by mistake. A group of very serious grown-ups was sitting at a giant table.</p>'
          ],
          [
            '<p class="story-lead">"Ah, you must be here to show us your new invention!" said a woman in a dark suit. Tommy, confused but wanting to be polite, smiled and opened his folder.</p>',
            '<p>Instead of fixing their coffee machine, he showed them his drawings of funny orange cats wearing tiny paper hats. The grown-ups looked at each other in surprise.</p>'
          ],
          [
            '<p class="story-lead">Suddenly, everyone burst out laughing! They loved the cute cats so much they decided to build a toy game based on Tommy\'s drawings, giving him a big gold trophy.</p>',
            '<p>Tommy walked home with a happy smile, realizing that sometimes a silly mix-up can make the whole world a little brighter and more cheerful.</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Don\'t worry when you make a small mistake or walk into the wrong room. Keep a friendly smile and share your creative ideas—you might surprise everyone!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'The Accidental Billionaire — A Satirical Pitch Guide',
        teaser: 'Mistaken identity, a malfunctioning coffee machine, and one very confused venture capitalist collide in this tale of accidental success.',
        source: 'Comedy Central',
        body: [
          [
            '<p class="story-lead">Tom was a junior maintenance technician, sent to the 14th floor of a high-rise to repair a malfunctioning espresso machine. However, a typographical error in the dispatch log led him into Room 1408.</p>',
            '<p>Inside, twelve high-profile venture capitalists were waiting for a pitch from a highly secretive AI startup. "You must be the SynerCat founder," the lead investor declared.</p>'
          ],
          [
            '<p class="story-lead">Too nervous to explain the mistake, Tom stood at the podium with his red wrench. He began repeating business buzzwords he had overheard in the break room, like "synergistic neural alignment."</p>',
            '<p>He opened his folder, which contained drawings of his cat, and described it as a "disruptive feline emotional interface." The investors were absolutely spellbound by his presentation.</p>'
          ],
          [
            '<p class="story-lead">Within ten minutes, the syndicate offered Tom a $4.7 million seed round. Confused but wealthy, Tom accepted, eventually selling the non-existent company to a tech conglomerate.</p>',
            '<p>He retired as a billionaire, keeping his red wrench framed in his mansion with a label: "Always value a broken espresso machine over a business plan."</p>'
          ]
        ]
      },
      expert: {
        headline: 'Market Irrationability and Tech Valuation Inflation: The SynerCat Case',
        teaser: 'A sharp satirical critique of venture capital funding bubbles, speculative pricing, and terminology-driven investing.',
        source: 'Financial Satire Gazette',
        body: [
          [
            '<p class="story-lead">The rapid rise of Tom\'s "SynerCat" corporate entity serves as an empirical case study in venture capital irrationality and speculative valuation bubbles in the tech industry.</p>',
            '<p>The pitch meeting demonstrates "FOMO-driven underwriting," where investors prioritize trendy terminology ("neural alignment") over concrete product viability or actual functional utility.</p>'
          ],
          [
            '<p class="story-lead">Tom\'s maintenance jargon was reinterpreted by the investors as advanced systems architecture, illustrating a profound technical literacy gap among major underwriters.</p>',
            '<p>The acquisition of SynerCat by a conglomerate represents a "pass-the-parcel valuation strategy," where speculative assets are sold to larger firms seeking to show AI integration.</p>'
          ],
          [
            '<p class="story-lead">Ultimately, the case highlights that in hyper-speculative markets, the simulation of innovation is often valued more highly than genuine engineering progress.</p>',
            '<p>This structural satire raises serious questions about modern investment auditing standards and the systemic inflation of valuations within the contemporary technology ecosystem.</p>'
          ]
        ]
      }
    }
  },
  {
    headline: 'My Neighbour is a Spy (Or Just Very Eccentric)',
    teaser: 'An amateur detective chronicles the suspicious behaviour of the new tenant in apartment 4B, with wildly incorrect conclusions.',
    source: 'Comedy Central',
    publishedAt: '2026-05-25T15:30:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/comedy/my-neighbour-is-a-spy-or-just-very-eccen.svg',
    levels: {
      kids: {
        headline: 'The Secret Agent Next Door',
        teaser: 'Mrs. Kapoor thinks her new neighbor is a secret agent who talks to birds, but finds out he is just a friendly accountant!',
        source: 'Comedy Kids',
        body: [
          [
            '<p class="story-lead">Mrs. Kapoor loved looking out her kitchen window. One morning, a new neighbor named Mr. Henderson moved into the apartment next door. He wore identical gray socks and talked to pigeons!</p>',
            '<p>"Aha!" Mrs. Kapoor whispered, magnifying glass in hand. "He must be a secret agent using birds to send top-secret letters!" She resolved to watch him closely.</p>'
          ],
          [
            '<p class="story-lead">She wrote down everything Mr. Henderson did in her little blue notebook. When he tip-toed to the market, she followed him behind a big newspaper, writing: "Agent buying secret groceries."</p>',
            '<p>One afternoon, she dropped her keys in the hallway, and Mr. Henderson kindly picked them up. "Hello!" he said warmly. "I\'m an accountant, and I feed the pigeons because they are very sweet."</p>'
          ],
          [
            '<p class="story-lead">Mrs. Kapoor gasped, realizing her detective work was just a big, funny misunderstanding! She laughed and invited Mr. Henderson in for tea and cookies.</p>',
            '<p>They became wonderful friends, and Mr. Henderson even showed Mrs. Kapoor how to count the pigeons in the courtyard. Now they feed the birds together every afternoon.</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Don\'t make quick assumptions about people just because they have quiet or unusual habits. Talk to them and be kind—you might make a wonderful friend!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'My Neighbour is a Spy (Or Just Very Eccentric)',
        teaser: 'An amateur detective chronicles the suspicious behaviour of the new tenant in apartment 4B, with wildly incorrect conclusions.',
        source: 'Comedy Central',
        body: [
          [
            '<p class="story-lead">When Mr. Henderson moved into apartment 4B, Mrs. Kapoor next door was convinced something was off. He received packages late at night, owned seventeen identical gray suits, and spoke to courtyard birds.</p>',
            '<p>Mrs. Kapoor, a retired teacher with far too much free time, began keeping a detailed journal of Mr. Henderson\'s "covert operations" in the building.</p>'
          ],
          [
            '<p class="story-lead">"Observation #14," she wrote. "Henderson tipped the delivery person in Canadian quarters. Clear evidence of an international operative using foreign currency to avoid tracing."</p>',
            '<p>"Observation #27: Stared at the brick wall for forty minutes. Receiving coded transmissions via neural implant." Mrs. Kapoor\'s theories grew more elaborate by the day.</p>'
          ],
          [
            '<p class="story-lead">The mystery was solved when a package for Mr. Henderson was misdelivered to Mrs. Kapoor. She brought it over, prepared to interrogate him about his "espionage operations."</p>',
            '<p>Instead, Mr. Henderson warmly invited her in, explaining he was a quiet accountant with insomnia who bought matching suits to save time. They now laugh over her spy journal over tea.</p>'
          ]
        ]
      },
      expert: {
        headline: 'Cognitive Bias & Confirmation Drift: The Kapoor Case Study',
        teaser: 'An analysis of how isolated observations can be woven into a complex conspiracy theory due to cognitive confirmation bias.',
        source: 'Social Psychology Journal',
        body: [
          [
            '<p class="story-lead">Mrs. Kapoor\'s investigation into Mr. Henderson is a classic illustration of confirmation bias and apophenia in isolated individuals within urban residential structures.</p>',
            '<p>Once Mrs. Kapoor established her initial espionage hypothesis, her mind reframed entirely benign behaviors—such as matching socks or insomnia—as supportive empirical evidence.</p>'
          ],
          [
            '<p class="story-lead">This cognitive drift highlights "isolation-induced projection," where a lack of meaningful social interaction drives the subject to construct complex narratives to engage the mind.</p>',
            '<p>The tipping in Canadian quarters and the bird-feeding were integrated into a cohesive, albeit wildly incorrect, conspiracy theory that provided an active sense of purpose.</p>'
          ],
          [
            '<p class="story-lead">Ultimately, the resolution of the case study through direct personal contact demonstrates that open communication is the most effective remedy for confirmation bias.</p>',
            '<p>By establishing a normal social connection, both neighbors resolved the tension, illustrating that community integration is key to combating isolation-induced suspicion.</p>'
          ]
        ]
      }
    }
  },
  {
    headline: 'Access Denied — The $50 Typo',
    teaser: 'John\'s late-night pricing proposal, IT support escalation, and the disastrous $50.00 typo that cost the company its biggest account.',
    source: 'Corporate Tragedy',
    publishedAt: '2026-05-23T11:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/comedy/access-denied.svg',
    levels: {
      kids: {
        headline: 'Johnny and the Giant Toy Dinosaurs',
        teaser: 'Johnny tries to finish his homework late at night, but in his sleepy state, he orders 50 giant toy dinosaurs instead of 5!',
        source: 'Comedy Kids',
        body: [
          [
            '<p class="story-lead">Johnny had a big science project about dinosaurs. He had to finish drawing his T-Rex and write his notes. But right when he sat down to finish it, his computer screen locked up! "Access Denied," it beeped loudly. Johnny sighed and waited for his dad to help.</p>',
            '<p>His dad called the computer helpers, but they said they were very busy and would fix it later. Johnny tried to stay awake, but his eyelids felt heavier and heavier.</p>'
          ],
          [
            '<p class="story-lead">Very late at night, the computer was finally fixed. Johnny was super sleepy, rubbing his eyes and yawning. He opened the online toy shop and wanted to order 5 small plastic dinosaurs for his display.</p>',
            '<p>But in his sleepy, half-asleep state, his finger double-tapped the keyboard. He accidentally typed 50 instead of 5 and hit the big "Send Order" button before collapsing back to sleep!</p>'
          ],
          [
            '<p class="story-lead">Two weeks later, a giant delivery truck arrived. The delivery workers unloaded fifty massive, life-sized green toy dinosaurs that blocked the entire driveway and front lawn!</p>',
            '<p>His mother gasped in shock while Johnny looked down, completely embarrassed by his giant sleepy mistake. He had to spend the weekend helping carry fifty giant plastic dinosaurs back to the delivery truck.</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Get plenty of rest! Never do your schoolwork or place orders online when you are super sleepy, or you might end up with fifty giant green dinosaurs on your front lawn!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'Access Denied — The $50 Typo',
        teaser: 'John\'s late-night pricing proposal, IT support escalation, and the disastrous $50.00 typo that cost the company its biggest account.',
        source: 'Corporate Tragedy',
        body: [
          [
            '<p class="story-lead">John, a senior sales manager, was having an incredibly stressful day. With his wife away on a business trip, he had to pick up the kids from school, cook dinner, and manage their chaotic bedtimes. Right in the middle of this, he received an urgent email: the pricing proposal for their biggest corporate client had to be submitted by morning.</p>',
            '<p>He finally sat down at his laptop at 7:00 PM, only to face a brick wall. A flashing warning on his screen read: "Access Denied." He couldn\'t connect to the secure office network.</p>'
          ],
          [
            '<p class="story-lead">John immediately called IT support at 7:45 PM, only to be told that his security ticket was escalated and someone would call him back "as soon as possible." Exhausted from the day\'s chaos, John fell fast asleep at his desk at 1:30 AM, resting his head next to the quiet phone.</p>',
            '<p>At 3:00 AM, his phone rang loudly — IT support had finally resolved the connection issue. Dazed and half-awake, John opened the proposal spreadsheet to input the final price per unit: "$5.00."</p>'
          ],
          [
            '<p class="story-lead">But in his sleepy, semi-conscious daze, John\'s finger slipped on the keyboard, typing "$50.00" instead of "$5.00." He hit submit before collapsing back to sleep, completely unaware of what he had done.</p>',
            '<p>Two weeks later, John stood in absolute shock as his boss screamed at him through the glass office window: "$50.00 per item! What were you thinking? We lost the business!!" John could only stare down, realizing too late the cost of a sleepy typo.</p>'
          ]
        ]
      },
      expert: {
        headline: 'IT Bottlenecks & Cognitive Fatigue: A Case Study on Procurement Errors',
        teaser: 'A technical analysis of corporate systems friction, sleep-deprivation cognitive impairment, and price elasticity in competitive bids.',
        source: 'Systemic Risk Quarterly',
        body: [
          [
            '<p class="story-lead">The procurement failure observed in John\'s case highlights the significant operational risks associated with centralized IT access controls and sleep-deprivation cognitive fatigue.</p>',
            '<p>When IT support delayed network resolution by over seven hours, it forced the sales manager to execute a critical financial bid during a period of severe circadian disruption (3:00 AM), dramatically increasing the likelihood of entry errors.</p>'
          ],
          [
            '<p class="story-lead">Cognitive tests show that decision-making at 3:00 AM after extended wakefulness matches the impairment of legal alcohol intoxication. The sales manager\'s focus was severely compromised by the circadian nadir.</p>',
            '<p>The 1000% pricing error ($50.00 vs $5.00) triggered immediate disqualification in a highly competitive, price-sensitive market where margins are razor-thin, eliminating any opportunity for manual bid revision.</p>'
          ],
          [
            '<p class="story-lead">This case study demonstrates that organizational security architectures must incorporate fail-safe mechanisms to prevent human fatigue errors from triggering catastrophic business losses.</p>',
            '<p>Ultimately, enterprises must implement systemic safeguards, such as automated validation filters for atypical pricing entries and flexible delivery windows, to insulate operations from inevitable employee fatigue.</p>'
          ]
        ]
      }
    }
  }
];

// 5. KIDS STORIES
STORY_DATA.kids = [
  {
    headline: 'Pip and the Little Lost Star — A Bedtime Adventure',
    teaser: 'A teeny star tumbles out of the sky into Pip the fox\'s mushroom patch. To get her home, the two friends cross a glowing forest, float into space, solve a sparkly mystery, and dive deep beneath the sea.',
    source: 'VilfinTV Kids',
    publishedAt: '2026-05-29T20:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/header.svg',
    levels: {
      kids: {
        headline: 'Pip and the Little Lost Star',
        teaser: 'Follow Pip the fox and Hoshi the baby star on a magical journey home — through the forest, into space, and under the sea.',
        source: 'VilfinTV Kids',
        body: [
          // 🖼️ HEADER → R2 key: media/kids/pip-star/header.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/header.svg" alt="Pip the little fox cradling a glowing baby star in a lantern-lit Japanese forest at night" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/header.svg\'"/></div>',

          // ── PAGE 1 · The Whispering Forest → media/kids/pip-star/page1.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page1.svg" alt="A small red fox with a cream-tipped tail and a green leaf behind his ear, sitting on a mossy rock in a glowing forest of paper lanterns and fireflies" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page1.svg\'"/></div>',
          '<p class="story-lead">Deep in the Whispering Forest — where paper lanterns hummed and fireflies played hide-and-seek — lived a small fox named Pip. He had a fluffy cream-tipped tail, a little green leaf tucked behind one ear, and exactly one hundred questions before breakfast. "What is past the tallest tree?" he wondered. "Do clouds taste like marshmallows? And does the moon ever, ever get lonely?"</p>',

          // ── PAGE 2 · A Surprise from the Sky → media/kids/pip-star/page2.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page2.svg" alt="A glowing golden baby star with rosy cheeks lying upside-down in a patch of mushrooms while a surprised little fox leans in" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page2.svg\'"/></div>',
          '<p>One quiet evening, the sky did something it had never done before. PLOP! A tiny star tumbled out of it and landed — bonk — right in Pip\'s mushroom patch. She was small and round and a teeny bit upside-down. "Um… hello," squeaked the star. "I am Hoshi. I think I fell off the sky."</p>',

          // ── PAGE 3 · Twinkle Trouble → media/kids/pip-star/page3.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page3.svg" alt="A wise round owl on a cherry-blossom branch at night looking down at a worried fox cradling a dimly glowing little star" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page3.svg\'"/></div>',
          '<p>Poor Hoshi\'s glow was fading, soft as a candle in the wind. "If I do not get home soon," she sniffled, "I will go all the way dark." The old forest owl blinked down from her branch. "Only the Sky Whale can carry a star home," she hooted. "But she swims far beyond the clouds. You will have to go up, little fox. Way, way up."</p>',

          // ── PAGE 4 · Up, Up, and Away → media/kids/pip-star/page4.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page4.svg" alt="A little fox in a basket lifted by a hundred glowing paper lanterns, rising through swirling pink cherry blossoms into a starry twilight sky" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page4.svg\'"/></div>',
          '<p>So Pip did what any brave little fox would do. He tied a hundred paper lanterns to a basket, tucked Hoshi snugly into his scarf, and held on tight. The lanterns glowed. The cherry blossoms swirled. And — whoosh! — up they floated, past the tallest tree, past the clouds, and right out into the velvety dark.</p>',

          // ── PAGE 5 · Hello, Space! → media/kids/pip-star/page5.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page5.svg" alt="A wide-eyed fox and a glowing star floating in colorful outer space among bouncy planets and looping comets, looking at a giant constellation map with some stars gone dark" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page5.svg\'"/></div>',
          '<p>Space was even bigger than Pip\'s biggest question. Planets bounced by like marbles. A ring of comets played leapfrog. "There!" cried Hoshi. "The Star Map shows the way to the Sky Whale!" But when they looked closer, half the stars on the map had gone dark. Someone had turned out the lights.</p>',

          // ── PAGE 6 · The Case of the Missing Lights → media/kids/pip-star/page6.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page6.svg" alt="A determined little fox wearing a tiny detective hat, holding a magnifying glass and a notebook, floating in starry space beside a worried glowing star" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page6.svg\'"/></div>',
          '<p>"A mystery!" gasped Pip — who secretly loved mysteries even more than mushrooms. He pulled out a tiny notebook (foxes always have one). "Do not worry, Hoshi. We will find every missing star. Detective Pip is on the case!"</p>',

          // ── PAGE 7 · Clues and Critters → media/kids/pip-star/page7.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page7.svg" alt="A little fox detective sniffing a trail of sparkly glitter crumbs across the moon, passing a sleepy space walrus and a playful comet-cat" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page7.svg\'"/></div>',
          '<p>The trail led past a grumpy Space Walrus ("Was not me — I was napping"), a giggly Comet Cat ("Too busy chasing my tail!"), and a sprinkle of glittery crumbs that twinkled like sugar. Pip followed the crumbs, sniff-sniff-sniffing, all the way to one small, very dark crater.</p>',

          // ── PAGE 8 · The Shyest Thief → media/kids/pip-star/page8.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page8.svg" alt="A tiny shy mole in a dark moon crater hugging a bundle of glowing starlight, while a kind little fox gently offers to share the light" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page8.svg\'"/></div>',
          '<p>And there, hugging a bundle of borrowed starlight, was the tiniest Moon-Mole anyone ever saw. "I — I was not stealing," he whispered. "I just got scared of the dark." Pip\'s heart went all warm and squishy. "Then let us share the light," he said. The Moon-Mole smiled and pointed a paw down, down, down. "The last bright star fell into the Sea of Mirrors."</p>',

          // ── PAGE 9 · Down to the Deep → media/kids/pip-star/page9.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page9.svg" alt="A brave little fox and a glowing star diving together into a magical glowing ocean lit up like soft nightlights, bubbles all around" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page9.svg\'"/></div>',
          '<p>Down they swooped — through the clouds, through the rain, splish-SPLASH — into a sea that glowed like a thousand nightlights. Pip held his breath. Hoshi held his paw. And down, down, down they swam into the glittering blue.</p>',

          // ── PAGE 10 · The Coral Kingdom → media/kids/pip-star/page10.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page10.svg" alt="A colorful coral kingdom with polka-dot-hatted jellyfish, racing seahorses, and a friendly wise octopus waving, as a fox and a glowing star explore" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page10.svg\'"/></div>',
          '<p>The Sea of Mirrors burst with color! Jellyfish wore polka-dot hats. Seahorses raced in tidy little rows. A wise old octopus waved hello with all eight arms. "Looking for the bright one?" she bubbled. "She has been keeping our oldest, sleepiest friend company."</p>',

          // ── PAGE 11 · The Sleeping Whale → media/kids/pip-star/page11.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page11.svg" alt="An enormous gentle whale sleeping on the glowing ocean floor with a bright star tucked under her fin, as a tiny fox sings softly to wake her" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page11.svg\'"/></div>',
          '<p>And there, curled on the soft sandy floor, was the Sky Whale — fast asleep, with the last bright star tucked under her fin like a nightlight. Pip sang the gentlest song he knew. The whale\'s big eyes fluttered open. "Is it time?" she yawned. "It is time," whispered Hoshi.</p>',

          // ── PAGE 12 · Home Among the Stars → media/kids/pip-star/page12.jpg
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/page12.svg" alt="A great friendly whale flying through a starry night sky carrying a fox, as a little star lights up the constellations one by one above the forest" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/page12.svg\'"/></div>',
          '<p>Up rose the Sky Whale — through the sea, through the sky, into the velvety dark — with Pip and Hoshi riding on her back. One by one, Hoshi touched each sleepy star and — twinkle, twinkle — they all lit up again. Then Hoshi hugged Pip goodbye and floated home to her own little spot in the sky. That night, back in the Whispering Forest, Pip looked up — and way, way up, the littlest star winked just for him. "Goodnight, Hoshi," he whispered. And the whole sky shone a little brighter.</p>',

          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">When you share your light — a smile, a helping paw, or a brave little song — even the darkest night turns bright. Kindness and courage always find their way home.</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'Pip and the Little Lost Star — A Bedtime Adventure',
        teaser: 'A teeny star tumbles out of the sky into Pip the fox\'s mushroom patch, and the two friends set off across forest, space, and sea to bring her home.',
        source: 'VilfinTV Kids',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/kids/pip-star/header.svg" alt="Pip the fox and Hoshi the glowing baby star" class="story-visual-img" loading="lazy" onerror="this.onerror=null;this.src=\'kids/pip-star/header.svg\'"/></div>',
          '<p class="story-lead">When a tiny star named Hoshi tumbles out of the sky and into Pip the fox\'s mushroom patch, her glow begins to fade. To get her home before she goes dark, the two new friends set off on the adventure of a lifetime.</p>',
          '<p>An old owl tells them that only the Sky Whale can carry a star home — far beyond the clouds. So Pip ties a hundred paper lanterns to a basket and floats up into space, where they discover that half the stars on the Star Map have mysteriously gone dark.</p>',
          '<ul class="story-bullets">',
          '  <li>Detective Pip follows a trail of glittery crumbs past a grumpy walrus and a giggly comet-cat, all the way to a shy little Moon-Mole.</li>',
          '  <li>The Moon-Mole was not a thief at all — he was simply scared of the dark, so Pip teaches him to share the light instead of hiding it.</li>',
          '  <li>The last bright star has sunk into the glowing Sea of Mirrors, where a sleeping Sky Whale has been guarding it all along.</li>',
          '</ul>',
          '<p>With a gentle song, Pip wakes the whale, who carries them home through the night. One by one, Hoshi relights every star — and winks goodnight to her brave new friend.</p>'
        ]
      },
      expert: {
        headline: 'Bedtime Stories & Big Feelings: Inside "Pip and the Little Lost Star"',
        teaser: 'A short note for grown-ups on the gentle lessons tucked inside this bedtime adventure.',
        source: 'VilfinTV Kids',
        body: [
          '<p class="story-lead">Beneath the lanterns and comets, this story quietly helps little ones practise some very big feelings.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Fear of the dark:</strong> The Moon-Mole is not punished for hiding the light — he is understood and helped, modelling empathy over blame.</li>',
          '  <li><strong>Generosity:</strong> "Sharing the light" turns a problem into a friendship, showing that kindness grows when it is given away.</li>',
          '  <li><strong>Courage and curiosity:</strong> Pip\'s hundred questions and brave little leaps reassure children that not knowing is the start of every adventure.</li>',
          '</ul>',
          '<p>Read it slowly at bedtime, pausing on each picture — the gentle rhythm and the soft, glowing scenes are designed to help wind down busy little minds.</p>'
        ]
      }
    }
  },
  {
    headline: 'Luna and the Star Garden — A Bedtime Adventure',
    teaser: 'When a little girl discovers she can plant stars, she embarks on a magical journey to light up the darkest corners of the world.',
    source: 'Kids Corner',
    publishedAt: '2026-05-26T19:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/luna-and-the-star-garden.svg',
    levels: {
      kids: {
        headline: 'Luna and the Star Garden',
        teaser: 'Luna plants a magic star seed and watches it grow, helping a little boy who was afraid of the dark feel safe and happy.',
        source: 'Kids Corner',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/luna-and-the-star-garden/page1.svg" onerror="this.onerror=null;this.src=\'stories/kids/luna-and-the-star-garden/page1.svg\'" alt="Luna and the Star Garden — A Bedtime Adventure — illustration 1" class="story-visual-img" loading="lazy"/></div>',
          '<p class="story-lead">Every night before bed, Luna would look out her window and wave to the twinkling stars. One evening, her grandmother gave her a tiny, shiny silver seed. "Plant it with love," she whispered.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/luna-and-the-star-garden/page2.svg" onerror="this.onerror=null;this.src=\'stories/kids/luna-and-the-star-garden/page2.svg\'" alt="Luna and the Star Garden — A Bedtime Adventure — illustration 2" class="story-visual-img" loading="lazy"/></div>',
          '<p>Luna tucked the seed into her flowerpot. The next morning, a sparkling vine had grown, with a glowing blue star at the top! Luna touched it, and the star floated gently into the sky, stopping over her friend Leo\'s house, who was afraid of the dark.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/luna-and-the-star-garden/page3.svg" onerror="this.onerror=null;this.src=\'stories/kids/luna-and-the-star-garden/page3.svg\'" alt="Luna and the Star Garden — A Bedtime Adventure — illustration 3" class="story-visual-img" loading="lazy"/></div>',
          '<p>Luna planted more seeds and grew stars in every color — yellow for happy dreams, pink for kindness, and green for courage. She shared them with everyone, making the whole town bright and warm!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Even the smallest act of kindness, like sharing a smile or a little light, can help wash away someone\'s fears and make the world a brighter place!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'Luna and the Star Garden — A Bedtime Adventure',
        teaser: 'When a little girl discovers she can plant stars, she embarks on a magical journey to light up the darkest corners of the world.',
        source: 'Kids Corner',
        body: [
          '<p class="story-lead">Luna often wondered why some places had many stars while others were dark. Her grandmother handed her a silver seed: "Because no one has planted them there yet."</p>',
          '<p>Luna planted the seed in her window box. By morning, a shimmering stalk had grown, and at its tip, a single star pulsed with soft, warm light.</p>',
          '<ul class="story-bullets">',
          '  <li>She touched the star, and it floated up, settling over a neighbor\'s house where a boy was afraid of the dark.</li>',
          '  <li>She planted more seeds, growing stars of different colors — blue for calm, gold for courage, and pink for kindness.</li>',
          '  <li>She sent stars to a local hospital and the old library, lighting up forgotten corners.</li>',
          '</ul>',
          '<p>Soon, Luna\'s stars were everywhere. She realized that a little light, shared with care, can help brighten the darkest nights.</p>'
        ]
      },
      expert: {
        headline: 'Altruistic Metaphors in Bedtime Literature: The Star Garden Paradigm',
        teaser: 'An academic analysis of the star garden metaphor as an educational tool for teaching emotional resilience and empathy to children.',
        source: 'Early Childhood Education Journal',
        body: [
          '<p class="story-lead">The narrative of Luna\'s "Star Garden" utilizes externalized light sources to help children conceptualize abstract emotional states like empathy and community care.</p>',
          '<p>By framing altruism as "planting seeds," the story gives children a sense of agency, suggesting that their small actions can help improve their environment.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Color Psychology:</strong> The distinct colors (blue for calm, gold for courage) reflect established associations in children\'s therapy.</li>',
          '  <li><strong>Cooperative Models:</strong> The spread of stars from Luna\'s window to public spaces highlights how prosocial behavior can inspire others.</li>',
          '</ul>',
          '<p>This analysis suggests that metaphor-rich stories are highly effective tools for helping children build emotional resilience and prosocial values.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Dragon Who Forgot How to Fly — A Dragon\'s Wings',
    teaser: 'A young dragon named Ember loses the ability to fly and must rely on an unlikely friend — a mouse with big ideas — to find his wings again.',
    source: 'Kids Corner',
    publishedAt: '2026-05-24T16:30:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-dragon-who-forgot-how-to-fly.svg',
    levels: {
      kids: {
        headline: 'Ember\'s Big Dragon Leap',
        teaser: 'Ember the little dragon is afraid he can\'t fly, but a tiny mouse friend shows him that laughing and trying are the keys to the sky.',
        source: 'Kids Corner',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-dragon-who-forgot-how-to-fly/page1.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-dragon-who-forgot-how-to-fly/page1.svg\'" alt="The Dragon Who Forgot How to Fly — A Dragon\'s Wings — illustration 1" class="story-visual-img" loading="lazy"/></div>',
          '<p class="story-lead">Ember was a friendly little dragon with bright orange scales. He loved flying, but one morning, his wings felt heavy and he couldn\'t lift off the ground!</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-dragon-who-forgot-how-to-fly/page2.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-dragon-who-forgot-how-to-fly/page2.svg\'" alt="The Dragon Who Forgot How to Fly — A Dragon\'s Wings — illustration 2" class="story-visual-img" loading="lazy"/></div>',
          '<p>A tiny mouse named Pip ran up. "Don\'t worry!" squeaked Pip. "Let\'s make your heart light!" Pip told funny jokes that made Ember laugh, and he helped Ember practice small jumps on the soft grass.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-dragon-who-forgot-how-to-fly/page3.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-dragon-who-forgot-how-to-fly/page3.svg\'" alt="The Dragon Who Forgot How to Fly — A Dragon\'s Wings — illustration 3" class="story-visual-img" loading="lazy"/></div>',
          '<p>Ember stopped worrying about being the best flyer and just had fun playing with Pip. Suddenly, with a happy leap, he soared high into the sky, carrying his little friend on his back!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Believing in yourself and having a supportive friend can help you overcome any challenge! Don\'t worry about being perfect; just have fun trying!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Dragon Who Forgot How to Fly — A Dragon\'s Wings',
        teaser: 'A young dragon named Ember loses the ability to fly and must rely on an unlikely friend — a mouse with big ideas — to find his wings again.',
        source: 'Kids Corner',
        body: [
          '<p class="story-lead">Ember was the smallest dragon in the Valley, but he had a big heart. One morning, however, he found himself unable to fly; his wings felt heavy and weak.</p>',
          '<p>That was when he met Pip, a tiny field mouse with big ideas. "Maybe you are worrying too much," Pip suggested. "Let\'s lift the weight from your heart."</p>',
          '<ul class="story-bullets">',
          '  <li>Pip made Ember laugh with funny games, helping him forget his worries.</li>',
          '  <li>They practiced small, stress-free hops on the grass, building back his confidence.</li>',
          '  <li>Ember realized the "weight" was not in his wings, but in his fear of not being good enough.</li>',
          '</ul>',
          '<p>Ember took a deep breath, focused on the joy of movement, and leaped. He soared back into the sky with Pip cheering on his back.</p>'
        ]
      },
      expert: {
        headline: 'Performance Anxiety & Play Therapy: Ember\'s Recovery Model',
        teaser: 'An analytical review of developmental psychology, focusing on play-based stress reduction and peer support models in childhood literature.',
        source: 'Pediatric Development Journal',
        body: [
          '<p class="story-lead">Ember\'s inability to fly serves as a clear metaphor for performance anxiety and self-imposed pressure, common in early childhood development.</p>',
          '<p>Pip\'s intervention aligns with standard play therapy principles, using humor and low-stakes exercises to reduce performance anxiety and rebuild self-confidence.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Anxiety De-escalation:</strong> Shifting the focus from success to play helps lower stress levels.</li>',
          '  <li><strong>Peer Mentorship:</strong> The tiny mouse helping the large dragon illustrates that effective support can come from unexpected sources.</li>',
          '</ul>',
          '<p>This analysis suggests that stories highlighting play-based coping strategies are highly effective in helping children navigate performance anxiety and stress.</p>'
        ]
      }
    }
  },
  {
    headline: 'Captain Coral and the Clean Sea — Teamwork Underwater',
    teaser: 'A brave octopus rallies the ocean creatures to clean up their home and teach the humans a valuable lesson.',
    source: 'Kids Corner',
    publishedAt: '2026-05-22T11:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/captain-coral-and-the-clean-sea.svg',
    levels: {
      kids: {
        headline: 'Captain Coral\'s Beach Helpers',
        teaser: 'Captain Coral the octopus invites all the sea animals to clean up the reef and sends a sweet letter to the children on the beach.',
        source: 'Kids Corner',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/captain-coral-and-the-clean-sea/page1.svg" onerror="this.onerror=null;this.src=\'stories/kids/captain-coral-and-the-clean-sea/page1.svg\'" alt="Captain Coral and the Clean Sea — Teamwork Underwater — illustration 1" class="story-visual-img" loading="lazy"/></div>',
          '<p class="story-lead">Deep down in the blue water, Captain Coral the octopus was sad. Her beautiful coral reef was filled with plastic cups and bags that had floated down from the beach.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/captain-coral-and-the-clean-sea/page2.svg" onerror="this.onerror=null;this.src=\'stories/kids/captain-coral-and-the-clean-sea/page2.svg\'" alt="Captain Coral and the Clean Sea — Teamwork Underwater — illustration 2" class="story-visual-img" loading="lazy"/></div>',
          '<p>"Let\'s work together!" bubbled Captain Coral. The crabs snipped the plastic wraps, the turtles collected the bags, and a giant whale blew them gently toward the shore.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/captain-coral-and-the-clean-sea/page3.svg" onerror="this.onerror=null;this.src=\'stories/kids/captain-coral-and-the-clean-sea/page3.svg\'" alt="Captain Coral and the Clean Sea — Teamwork Underwater — illustration 3" class="story-visual-img" loading="lazy"/></div>',
          '<p>They put a picture of a clean reef inside a shiny shell and left it on the sand. A little girl found it and helped start a beach clean-up day. Soon, the water was clean and sparkling again!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">We must all work together to keep our oceans, beaches, and parks clean and safe for the animals who live there! Every helper counts!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'Captain Coral and the Clean Sea — Teamwork Underwater',
        teaser: 'A brave octopus rallies the ocean creatures to clean up their home and teach the humans a valuable lesson about caring for the sea.',
        source: 'Kids Corner',
        body: [
          '<p class="story-lead">Deep beneath the waves, Captain Coral the octopus loved her home, but lately, floating plastic was making the sea creatures sick.</p>',
          '<p>She gathered the ocean creatures for a meeting, organizing a team to collect the waste and keep the reef safe.</p>',
          '<ul class="story-bullets">',
          '  <li>The crabs carefully snipped away plastic nets tangled in the coral.</li>',
          '  <li>The turtles and fish collected floating waste, while the whales helped move it toward the shore.</li>',
          '  <li>They sent a message in a bottle asking the humans on land to help keep the ocean clean.</li>',
          '</ul>',
          '<p>A child found the bottle and started a local clean-up group, showing that a shared effort can help protect our environment.</p>'
        ]
      },
      expert: {
        headline: 'Marine Conservation Narratives: Interactive Ecological Empathy',
        teaser: 'A study of environmental education through storytelling, exploring how marine themes can build ecological awareness in children.',
        source: 'Environmental Education Quarterly',
        body: [
          '<p class="story-lead">The narrative of Captain Coral uses character-driven storytelling to introduce children to the complex issue of marine plastic pollution.</p>',
          '<p>By giving the sea creatures agency and showing a positive collaboration between land and sea, the story encourages active environmental stewardship.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Active Stewardship:</strong> The transition from ocean clean-up to land-based action highlights the link between human behavior and marine health.</li>',
          '  <li><strong>Collective Agency:</strong> The collaborative effort among different species supports values of teamwork and community responsibility.</li>',
          '</ul>',
          '<p>This analysis suggests that stories highlighting collaborative ecological action are highly effective in building environmental awareness and empathy in young learners.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Clever Monkey and the Two Cats — Moral Fable',
    teaser: 'Two cats find a tasty piece of bread but end up losing it to a clever monkey who offers to divide it equally!',
    source: 'Kids Classics',
    publishedAt: '2026-05-20T10:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-clever-monkey-and-the-two-cats.svg',
    levels: {
      kids: {
        headline: 'The Clever Monkey and the Two Cats',
        teaser: 'Two cats find a piece of bread and start arguing. A monkey offers to help them divide it, but he has a very cheeky plan!',
        source: 'Kids Classics',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-clever-monkey-and-the-two-cats/page1.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-clever-monkey-and-the-two-cats/page1.svg\'" alt="The Clever Monkey and the Two Cats — Moral Fable — illustration 1" class="story-visual-img" loading="lazy"/></div>',
          '<p class="story-lead">Mimi the white cat and Lily the grey cat were best friends. One sunny morning, they found a delicious, warm piece of bread under a tree. "I saw it first!" meowed Mimi. "But I jumped on it first!" hissed Lily.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-clever-monkey-and-the-two-cats/page2.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-clever-monkey-and-the-two-cats/page2.svg\'" alt="The Clever Monkey and the Two Cats — Moral Fable — illustration 2" class="story-visual-img" loading="lazy"/></div>',
          '<p>A cheeky monkey named Koko sat in the branches above. "Do not fight, sweet friends!" Koko chattered. "I have a balance scale and can split this bread into two perfectly equal pieces for you." The cats agreed and handed him the loaf.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-clever-monkey-and-the-two-cats/page3.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-clever-monkey-and-the-two-cats/page3.svg\'" alt="The Clever Monkey and the Two Cats — Moral Fable — illustration 3" class="story-visual-img" loading="lazy"/></div>',
          '<p>Koko broke the bread into two pieces. "Oh, this piece is slightly bigger," he said, and took a big bite out of it. "Oops, now the other side is bigger," he muttered, taking a bite out of that one. He kept biting and chewing, back and forth, until there was absolutely no bread left! He hopped away with a full belly while the hungry cats sighed.</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Disputes only benefit the third party. It is always better to share, compromise, and settle arguments peacefully rather than letting others take advantage of your disagreements!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Clever Monkey and the Two Cats — Moral Fable',
        teaser: 'Two cats find a tasty piece of bread but end up losing it to a clever monkey who offers to divide it equally!',
        source: 'Kids Classics',
        body: [
          '<p class="story-lead">Mimi and Lily, two hungry neighborhood cats, discovered a single piece of fresh bread in the courtyard. Instantly, an argument broke out over who owned the larger share.</p>',
          '<p>A passing monkey named Koko saw their dispute and offered to act as a neutral arbitrator. He brought out a balance scale and broke the bread into two parts.</p>',
          '<ul class="story-bullets">',
          '  <li>He placed the pieces on the scale. The left side was heavier, so he bit off a portion to "balance" it.</li>',
          '  <li>This made the right side heavier, so he took a bite from the right piece.</li>',
          '  <li>He continued this tactical "trimming" process, despite the cats\' protests, until the entire bread was consumed.</li>',
          '</ul>',
          '<p>Koko declared the case closed and swung away into the canopy. The two cats were left with nothing, realizing too late that their inability to share had cost them their entire meal.</p>'
        ]
      },
      expert: {
        headline: 'Third-Party Arbitration Paradoxes: A Game Theoretic Analysis of the Two Cats Fable',
        teaser: 'An academic exploration of transaction cost economics, mediator rent-seeking, and Nash equilibriums in non-cooperative cooperative games.',
        source: 'Strategic Arbitration Journal',
        body: [
          '<p class="story-lead">The fable of the two cats and the monkey arbitrator offers a clear illustration of transaction cost economics and the rent-seeking behavior of unregulated third-party mediators.</p>',
          '<p>In game theory, the cats\' dispute represents a non-cooperative game where a failure to reach a bilateral agreement leads them to delegate arbitration, introducing a predatory third actor.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Arbitration Cost:</strong> The mediator\'s fee (the bread consumed) exceeds the value of the dispute, representing a catastrophic transaction cost.</li>',
          '  <li><strong>Nash Equilibrium Failure:</strong> The optimal outcome was a 50/50 split. The cats\' zero-sum mindset allowed the arbitrator to extract 100% of the asset\'s value.</li>',
          '</ul>',
          '<p>Ultimately, the story demonstrates that bilateral compromise is structurally superior to third-party litigation in environments where mediators lack regulatory oversight or fiduciary duties.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Thirsty Crow\'s Smart Idea — Fable of Persistence',
    teaser: 'A very thirsty crow finds a pitcher of water, but can\'t reach it! See how he uses small pebbles to solve his problem!',
    source: 'Kids Classics',
    publishedAt: '2026-05-18T12:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-thirsty-crow-s-smart-idea.svg',
    levels: {
      kids: {
        headline: 'The Thirsty Crow\'s Smart Idea',
        teaser: 'Corby the crow is so thirsty, but the water is at the bottom of a tall glass pitcher. See how he uses small pebbles to drink!',
        source: 'Kids Classics',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-thirsty-crow-s-smart-idea/page1.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-thirsty-crow-s-smart-idea/page1.svg\'" alt="The Thirsty Crow\'s Smart Idea — Fable of Persistence — illustration 1" class="story-visual-img" loading="lazy"/></div>',
          '<p class="story-lead">Corby the black crow had been flying for hours on a hot, sunny day. His throat was dry, and he was so thirsty! He flapped his wings and landed in a quiet garden, searching for water.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-thirsty-crow-s-smart-idea/page2.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-thirsty-crow-s-smart-idea/page2.svg\'" alt="The Thirsty Crow\'s Smart Idea — Fable of Persistence — illustration 2" class="story-visual-img" loading="lazy"/></div>',
          '<p>He spotted a tall glass pitcher on a table. He flew down and peeked inside. There was water, but it was at the very bottom! Corby stretched his neck as far as he could, but his beak just couldn\'t reach it. "What should I do?" he thought. He didn\'t give up.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-thirsty-crow-s-smart-idea/page3.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-thirsty-crow-s-smart-idea/page3.svg\'" alt="The Thirsty Crow\'s Smart Idea — Fable of Persistence — illustration 3" class="story-visual-img" loading="lazy"/></div>',
          '<p>Corby looked down and saw shiny brown pebbles on the path. He picked up one pebble in his beak and dropped it into the pitcher. *Plop!* He dropped another. *Plop!* He kept picking up pebbles, dropping them one by one. Slow and steady, the water rose to the top! Corby drank the cool, refreshing water happily and flew away.</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Where there is a will, there is a way! When you face a hard problem, don\'t give up. Think calmly, keep trying, and use your intelligence to find a smart solution!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Thirsty Crow\'s Smart Idea — Fable of Persistence',
        teaser: 'A very thirsty crow finds a pitcher of water, but can\'t reach it! See how he uses small pebbles to solve his problem!',
        source: 'Kids Classics',
        body: [
          '<p class="story-lead">During a severe drought, a thirsty crow named Corby searched for water across the barren fields. He eventually found a glass pitcher containing a small amount of water.</p>',
          '<p>However, the water level was too low, and the pitcher\'s narrow neck prevented him from reaching it. Instead of panicking or leaving, the crow began analyzing his surroundings.</p>',
          '<ul class="story-bullets">',
          '  <li>He noticed a pile of small pebbles scattered nearby on the dry soil.</li>',
          '  <li>He began carrying the pebbles in his beak, dropping them into the pitcher one by one.</li>',
          '  <li>As the pebbles displaced the liquid, the water level steadily rose to the rim, allowing him to drink.</li>',
          '</ul>',
          '<p>This classic fable showcases the power of resourcefulness, proving that persistence and analytical thinking can help solve seemingly impossible challenges.</p>'
        ]
      },
      expert: {
        headline: 'Cognitive Tool-Use and Liquid Displacement: The Corvid Intelligence Model',
        teaser: 'An analytical review of fluid dynamics, Archimedes\' principle, and advanced cognitive problem-solving in corvids.',
        source: 'Corvid Cognitive Review',
        body: [
          '<p class="story-lead">The fable of the thirsty crow serves as an early narrative recording of tool-use and causal reasoning in corvids—a family of birds now verified to possess advanced cognitive problem-solving abilities.</p>',
          '<p>From a physical perspective, the crow\'s strategy is a direct application of Archimedes\' principle of volume displacement, where solid mass occupies the bottom of the container, raising the liquid level.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Causal Reasoning:</strong> The crow understands the relationship between mass insertion and water elevation, a cognitive milestone equivalent to a human toddler.</li>',
          '  <li><strong>Resource Optimization:</strong> The bird selects pebbles of appropriate sizes, showing a grasp of volume optimization under time and energy constraints.</li>',
          '</ul>',
          '<p>These cognitive trials prove that corvids possess sophisticated problem-solving skills, showing that intelligence can drive elegant behavioral solutions in resource-scarce environments.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Cap Seller and the Copycat Monkeys — Wisdom at Work',
    teaser: 'A cap seller takes a nap and wakes up to find monkeys wearing all his caps! How will he get them back?',
    source: 'Kids Classics',
    publishedAt: '2026-05-16T15:30:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-cap-seller-and-the-copycat-monkeys.svg',
    levels: {
      kids: {
        headline: 'The Cap Seller and the Copycat Monkeys',
        teaser: 'Ramu the cap seller takes a nap under a shady tree, but wakes up to see a tree full of copycat monkeys wearing his colorful caps!',
        source: 'Kids Classics',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-cap-seller-and-the-copycat-monkeys/page1.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-cap-seller-and-the-copycat-monkeys/page1.svg\'" alt="The Cap Seller and the Copycat Monkeys — Wisdom at Work — illustration 1" class="story-visual-img" loading="lazy"/></div>',
          '<p class="story-lead">Ramu was a hard-working cap seller who carried a large basket of bright, colorful caps — red, green, blue, and yellow. One warm afternoon, tired from walking, he sat down under a leafy tree and fell fast asleep.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-cap-seller-and-the-copycat-monkeys/page2.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-cap-seller-and-the-copycat-monkeys/page2.svg\'" alt="The Cap Seller and the Copycat Monkeys — Wisdom at Work — illustration 2" class="story-visual-img" loading="lazy"/></div>',
          '<p>When Ramu woke up, he gasped. His basket was completely empty! He looked up and saw a tree full of mischievous monkeys. Every single monkey was wearing one of his bright caps, pointing and laughing at him! "Hey! Give me back my caps!" Ramu shouted, shaking his fist.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-cap-seller-and-the-copycat-monkeys/page3.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-cap-seller-and-the-copycat-monkeys/page3.svg\'" alt="The Cap Seller and the Copycat Monkeys — Wisdom at Work — illustration 3" class="story-visual-img" loading="lazy"/></div>',
          '<p>The monkeys shook their fists back! Ramu stomped his feet; the monkeys stomped their feet! Ramu realized the monkeys were copycats. He smiled, took off his own colorful hat, and threw it hard to the ground. *Plop!* Instantly, all the monkeys took off their caps and threw them down too! Ramu quickly gathered them up and went on his way, chuckling.</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Thinking calmly and using clever ideas can help you get out of tricky situations! When things go wrong, reacting angrily doesn\'t help, but keeping a cool head always does!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Cap Seller and the Copycat Monkeys — Wisdom at Work',
        teaser: 'A cap seller takes a nap and wakes up to find monkeys wearing all his caps! How will he get them back?',
        source: 'Kids Classics',
        body: [
          '<p class="story-lead">Ramu, a traveling merchant, fell asleep under a large banyan tree during a long journey, leaving his basket of colorful caps unsecured.</p>',
          '<p>He awoke to discover his inventory was gone, stolen by a troop of monkeys nesting in the branches above. The primates had put the caps on, mimicking his trade.</p>',
          '<ul class="story-bullets">',
          '  <li>Ramu tried shouting and gesturing, but the monkeys only copied his angry movements.</li>',
          '  <li>Recognizing the primates\' mimetic instincts, Ramu decided to use reverse psychology.</li>',
          '  <li>He threw his own cap to the ground. The copycat monkeys mimicked him, tossing all the stolen caps back to the earth.</li>',
          '</ul>',
          '<p>Ramu quickly packed his inventory and departed, having successfully resolved a major business loss through quick-witted observation.</p>'
        ]
      },
      expert: {
        headline: 'Primate Mimesis & Reverse Psychology in Inventory Recovery',
        teaser: 'A behavioral study on mirror neurons, mimetic synchronization in primates, and the deployment of cognitive reverse tactics.',
        source: 'Behavioral Primatology Review',
        body: [
          '<p class="story-lead">The cap seller\'s interaction with the banyan tree troop offers an empirical demonstration of primate mimesis—a process mediated by mirror neurons that drives individuals to match the behavior of others.</p>',
          '<p>By shifting from direct confrontation to strategic reverse psychology, Ramu leveraged this mimetic drive to resolve his inventory loss without requiring physical intervention.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Mimetic Synchronization:</strong> The monkeys\' copying behavior is an involuntary social binding mechanism rather than conscious theft.</li>',
          '  <li><strong>Tactical Reverse Psychology:</strong> Ramu exploited the primates\' drive to imitate, turning a confrontation into a coordinated inventory release.</li>',
          '</ul>',
          '<p>This analysis suggests that in conflicts with actors driven by strong imitative behaviors, tactical compliance or symbolic concessions are often more effective than direct confrontation.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Lazy Donkey\'s Wet Trick — A Lesson on Hard Work',
    teaser: 'Barnaby the donkey tries a lazy trick to make his salt load lighter, but gets a very heavy surprise the next day!',
    source: 'Kids Classics',
    publishedAt: '2026-05-14T09:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-lazy-donkey-s-wet-trick.svg',
    levels: {
      kids: {
        headline: 'The Lazy Donkey\'s Wet Trick',
        teaser: 'Barnaby the donkey slips in the river to make his heavy salt load dissolve, but his master teaches him a wet and heavy lesson!',
        source: 'Kids Classics',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-lazy-donkey-s-wet-trick/page1.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-lazy-donkey-s-wet-trick/page1.svg\'" alt="The Lazy Donkey\'s Wet Trick — A Lesson on Hard Work — illustration 1" class="story-visual-img" loading="lazy"/></div>',
          '<p class="story-lead">Barnaby was a little donkey who carried heavy bags of salt for his master. One sunny morning, while crossing a shallow, sparkling river, Barnaby accidentally slipped and fell — *Sploosh!*</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-lazy-donkey-s-wet-trick/page2.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-lazy-donkey-s-wet-trick/page2.svg\'" alt="The Lazy Donkey\'s Wet Trick — A Lesson on Hard Work — illustration 2" class="story-visual-img" loading="lazy"/></div>',
          '<p>When he stood up, he was surprised! His load felt incredibly light! The water had dissolved the salt inside the bags. Barnaby was so happy. The next day, Barnaby decided to try a lazy trick. As they crossed the river, he purposely pretended to slip and fell into the water. *Sploosh!* Once again, his load became light, and he walked home happily. His master noticed the lazy trick.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-lazy-donkey-s-wet-trick/page3.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-lazy-donkey-s-wet-trick/page3.svg\'" alt="The Lazy Donkey\'s Wet Trick — A Lesson on Hard Work — illustration 3" class="story-visual-img" loading="lazy"/></div>',
          '<p>The third day, the master loaded Barnaby with bags of fluffy cotton. When they reached the river, Barnaby smiled and fell into the water on purpose. But instead of dissolving, the cotton absorbed the water and grew twice as heavy! Barnaby had to drag the wet, heavy cotton bags all the way home, panting and tired. He learned his lesson and never played tricks again.</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Laziness and shortcuts might work once, but they will eventually catch up to you and make things harder in the long run. Hard work and honesty are always the best policies!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Lazy Donkey\'s Wet Trick — A Lesson on Hard Work',
        teaser: 'Barnaby the donkey tries a lazy trick to make his salt load lighter, but gets a very heavy surprise the next day!',
        source: 'Kids Classics',
        body: [
          '<p class="story-lead">A merchant owned a donkey named Barnaby, whose job was to transport heavy sacks of salt from the coast to the marketplace.</p>',
          '<p>During a routine river crossing, the donkey slipped. The salt dissolved in the water, drastically reducing the weight of his load and giving Barnaby a new strategy.</p>',
          '<ul class="story-bullets">',
          '  <li>The next day, Barnaby intentionally fell into the river to repeat the weight reduction.</li>',
          '  <li>The merchant recognized the moral hazard and loaded him with dry, absorbent cotton the following morning.</li>',
          '  <li>When Barnaby fell into the river on purpose, the cotton absorbed the water, doubling the weight and teaching him a lesson.</li>',
          '</ul>',
          '<p>From that day on, Barnaby carried his loads honestly, realizing that shortcuts can sometimes lead to even heavier burdens.</p>'
        ]
      },
      expert: {
        headline: 'Moral Hazard and Incentive Misalignment: The Salt Merchant Fable',
        teaser: 'An economic analysis of agent-principal dynamics, asymmetric information, and reinforcement learning in animal labor structures.',
        source: 'Asymmetric Economics Review',
        body: [
          '<p class="story-lead">The fable of the salt donkey provides an early illustration of moral hazard, where an agent (the donkey) exploits asymmetric information to reduce effort at the expense of the principal (the merchant).</p>',
          '<p>Barnaby\'s behavior represents a basic reinforcement learning loop, where a positive outcome (reduced load weight) encourages him to repeat the action.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Moral Hazard:</strong> The agent acts in its own self-interest because the principal cannot fully monitor or prevent the behavior.</li>',
          '  <li><strong>Incentive Realignment:</strong> The merchant alters the cost structure (swapping salt for cotton), turning the lazy behavior into a self-punishing action.</li>',
          '</ul>',
          '<p>This case demonstrates that in economic systems, modifying the structure of incentives is often more effective than using direct punishment to align agent and principal goals.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Hare and the Steady Tortoise — The Classic Race',
    teaser: 'Harry the fast hare is sure he will win the race, but slow and steady Toby shows him who the real champion is!',
    source: 'Kids Classics',
    publishedAt: '2026-05-12T07:45:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-hare-and-the-steady-tortoise.svg',
    levels: {
      kids: {
        headline: 'The Hare and the Steady Tortoise',
        teaser: 'Harry the fast hare laughs at Toby the slow tortoise. But during their big race, Harry takes a nap while Toby keeps moving slow and steady!',
        source: 'Kids Classics',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-hare-and-the-steady-tortoise/page1.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-hare-and-the-steady-tortoise/page1.svg\'" alt="The Hare and the Steady Tortoise — The Classic Race — illustration 1" class="story-visual-img" loading="lazy"/></div>',
          '<p class="story-lead">Harry the hare was the fastest runner in the forest. He loved to boast about his speed. "No one can beat me!" he bragged, laughing at Toby, a very slow tortoise. Tired of the boasting, Toby smiled and said, "I challenge you to a race!"</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-hare-and-the-steady-tortoise/page2.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-hare-and-the-steady-tortoise/page2.svg\'" alt="The Hare and the Steady Tortoise — The Classic Race — illustration 2" class="story-visual-img" loading="lazy"/></div>',
          '<p>The forest animals gathered to watch. When the whistle blew, Harry zipped ahead like a rocket, leaving Toby far behind. Confident he would win, Harry stopped under a shady tree. "The tortoise is so slow, I have plenty of time for a cozy nap," Harry yawned, falling asleep.</p>',
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/kids/the-hare-and-the-steady-tortoise/page3.svg" onerror="this.onerror=null;this.src=\'stories/kids/the-hare-and-the-steady-tortoise/page3.svg\'" alt="The Hare and the Steady Tortoise — The Classic Race — illustration 3" class="story-visual-img" loading="lazy"/></div>',
          '<p>Meanwhile, Toby kept walking. He went step by step, slow and steady. He didn\'t stop to rest, and he didn\'t look back. He walked right past the sleeping hare. When Harry finally woke up with a start, he saw Toby crossing the red finish line, holding the shiny golden trophy as everyone cheered! Toby smiled: "Slow and steady wins the race!"</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Slow and steady wins the race! Never boast or mock others, and never stop trying, no matter how slow you are going. Consistency, determination, and hard work will always lead to success!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Hare and the Steady Tortoise — The Classic Race',
        teaser: 'Harry the fast hare is sure he will win the race, but slow and steady Toby shows him who the real champion is!',
        source: 'Kids Classics',
        body: [
          '<p class="story-lead">Harry, a swift hare known for his speed, constantly mocked Toby, a slow tortoise, for his slow movement. Amused, Toby challenged the hare to a race.</p>',
          '<p>The race commenced, and Harry quickly built a massive lead. Confident in his victory, he decided to rest and fell asleep under a tree near the finish line.</p>',
          '<ul class="story-bullets">',
          '  <li>Toby continued to move forward at a slow but steady pace, refusing to stop or rest.</li>',
          '  <li>He passed the sleeping hare, maintaining his consistent pace throughout the race.</li>',
          '  <li>When Harry woke up, he sprinted to the finish line, only to find Toby had already won the race.</li>',
          '</ul>',
          '<p>This classic fable showcases the value of consistency and dedication, proving that a steady effort can often outperform volatile talent.</p>'
        ]
      },
      expert: {
        headline: 'Volumetric Pacing and Performance Consistency: The Tortoise-Hare Matrix',
        teaser: 'A game-theoretic and kinetic pacing model, comparing volatile performance peaks with high-consistency outcomes in competitive ecosystems.',
        source: 'Strategic Performance Quarterly',
        body: [
          '<p class="story-lead">The race between the tortoise and the hare serves as a classic model for comparing volatile, high-output strategies with consistent, low-variance performances.</p>',
          '<p>The hare\'s approach represents a high-volatility strategy that, despite its peak performance, carries a risk of failure due to complacency and lack of discipline.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Performance Consistency:</strong> The tortoise\'s low-variance model leads to a highly predictable, successful outcome in competitive settings.</li>',
          '  <li><strong>Risk Management:</strong> The hare\'s overconfidence introduces significant operational risk, allowing the slower competitor to win.</li>',
          '</ul>',
          '<p>This analysis proves that in long-term competitive settings, maintaining a consistent, well-paced effort is often more effective than relying on volatile bursts of performance.</p>'
        ]
      }
    }
  }
];

// 6. EDUCATION STORIES
STORY_DATA.education = [
  {
    headline: 'The School of Trust — Finland\'s Education Success',
    teaser: 'How one Nordic country transformed its education system by doing the exact opposite of what everyone else was doing.',
    source: 'Education Hub',
    publishedAt: '2026-05-26T08:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/education/the-school-of-trust.svg',
    levels: {
      kids: {
        headline: 'The School of Outdoor Play',
        teaser: 'In Finland, children get to play outside in the snow every hour, showing that playing is a wonderful way to learn!',
        source: 'Education Kids',
        body: [
          [
            '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/education/the-school-of-trust.svg" onerror="this.onerror=null;this.src=\'stories/education/the-school-of-trust.svg\'" alt="Happy Kids" class="story-visual-img"/></div>',
            '<p class="story-lead">Did you know there is a country where school has lots of playtime and very little homework? It\'s called Finland, and children there absolutely love going to school!</p>',
            '<p>In Finnish schools, children go outside to play in the fresh air for fifteen minutes every single hour, even when it snows! They build snowman castles and play tag in the yard.</p>'
          ],
          [
            '<p class="story-lead">Instead of writing stressful tests, their teachers help them explore, build wooden blocks, and read fun storybooks. The children work in groups and help each other learn.</p>',
            '<p>Because they are happy and relaxed, these children learn very quickly and do wonderfully in their studies! They grow up to be smart, kind, and creative helpers.</p>'
          ],
          [
            '<p class="story-lead">A kind Finnish teacher smiled and said: "Playing is the work of children. A happy child is the best learner in the world!"</p>',
            '<p>This wonderful school shows us that playing and learning go hand in hand, helping us grow strong and smart in a happy environment.</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Learning should be fun and relaxed! Playing outside, exploring nature, and resting your mind are just as important as studying books!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'The School of Trust — Finland\'s Education Success',
        teaser: 'How one Nordic country transformed its education system by doing the exact opposite of what everyone else was doing.',
        source: 'Education Hub',
        body: [
          [
            '<p class="story-lead">In the early 1970s, Finland had an average school system. Today, it consistently ranks among the most successful in the world.</p>',
            '<p>Their secret was simple: reduce academic stress, eliminate constant testing, and focus on student well-being and creative play.</p>'
          ],
          [
            '<p class="story-lead">Students are assessed individually by their teachers without standardized exams. Every 45 minutes of class is followed by 15 minutes of outdoor play, regardless of the weather.</p>',
            '<p>This balance maintains student engagement and supports mental health, preventing the burnout common in highly competitive educational systems.</p>'
          ],
          [
            '<p class="story-lead">By prioritizing student happiness and equity, Finland has created a system where academic success is a natural result of a supportive environment.</p>',
            '<p>Highly trained teachers have the freedom to customize curricula, ensuring every student receives the attention needed to succeed.</p>'
          ]
        ]
      },
      expert: {
        headline: 'Pedagogical Autonomy and Equity: The Finnish Model in Focus',
        teaser: 'A detailed structural analysis of pedagogical autonomy, social equity, and decentralized curricula in Finnish public education.',
        source: 'Comparative Education Journal',
        body: [
          [
            '<p class="story-lead">The success of the Finnish educational system highlights the efficacy of decoupling academic assessment from high-stakes standardized testing.</p>',
            '<p>By prioritizing equity over performance competition, the system minimizes the impact of socioeconomic status on learning outcomes.</p>'
          ],
          [
            '<p class="story-lead">Pedagogical autonomy granted to highly trained educators enables the customization of curricula to meet diverse student needs, fostering a resilient educational framework.</p>',
            '<p>Furthermore, play-based learning and frequent intervals of physical activity support cognitive focus and reduce mental fatigue in students.</p>'
          ],
          [
            '<p class="story-lead">In conclusion, the Finnish model suggests that social equity and teacher autonomy are critical factors in building a resilient, high-performing educational system.</p>',
            '<p>This analysis advocates for shifting policy focus from standardized testing metrics to structural equity and professional educator development.</p>'
          ]
        ]
      }
    }
  },
  {
    headline: 'Language of the Universe — Math Patterns in Nature',
    teaser: 'From the spiral of a galaxy to the arrangement of seeds in a sunflower, mathematics is the invisible thread connecting everything.',
    source: 'Education Hub',
    publishedAt: '2026-05-24T14:30:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/education/language-of-the-universe.svg',
    levels: {
      kids: {
        headline: 'Nature\'s Secret Math Patterns',
        teaser: 'Sunflowers, pinecones, and seashells all use a secret number pattern to grow beautifully. Let\'s explore nature\'s code!',
        source: 'Education Kids',
        body: [
          [
            '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/education/language-of-the-universe.svg" onerror="this.onerror=null;this.src=\'stories/education/language-of-the-universe.svg\'" alt="Sunflower Math" class="story-visual-img"/></div>',
            '<p class="story-lead">Did you know that sunflowers are secret math wizards? If you count the seeds in a sunflower, they grow in beautiful matching spirals!</p>',
            '<p>Sunflowers pack their seeds in this spiral pattern to make sure every seed gets plenty of sunlight and space to grow big and strong.</p>'
          ],
          [
            '<p class="story-lead">Pinecones, green broccoli, and even beautiful seashells on the beach use the exact same number pattern to grow! It is like a secret code nature uses to paint the world.</p>',
            '<p>Even giant galaxies in deep space spin in the same mathematical spiral! Math is like a magical key that opens the doors to all of nature\'s secrets.</p>'
          ],
          [
            '<p class="story-lead">When we study math in school, we are not just looking at numbers on a board—we are learning the beautiful language nature uses to build the trees and stars.</p>',
            '<p>Next time you go for a walk, look closely at a flower or leaf. You might just spot a secret math pattern hiding in plain sight!</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Mathematics is not just about numbers on a blackboard; it is a beautiful code found in flowers, shells, and stars all around us!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'Language of the Universe — Math Patterns in Nature',
        teaser: 'From the spiral of a galaxy to the arrangement of seeds in a sunflower, mathematics is the invisible thread connecting everything.',
        source: 'Education Hub',
        body: [
          [
            '<p class="story-lead">Galileo famously wrote that the universe is written in the language of mathematics. Today, that insight is more vivid than ever as we discover mathematical patterns everywhere.</p>',
            '<p>Professor Ravi Nair has spent his career exploring the mathematical patterns that shape the natural world, from plants to astronomical structures.</p>'
          ],
          [
            '<p class="story-lead">One of the most common patterns is the Fibonacci Sequence. Sunflower seeds and pinecones pack together using ratios from this sequence, maximizing space efficiency.</p>',
            '<p>Fractal geometry describes self-repeating patterns seen in river networks, lightning bolts, and tree branches, optimizing flow and surface area at every scale.</p>'
          ],
          [
            '<p class="story-lead">These patterns show that math is not just an invented tool, but a fundamental language discovered within the structure of nature.</p>',
            '<p>By understanding these mathematical frameworks, researchers can model ecological systems and predict natural phenomena with remarkable precision.</p>'
          ]
        ]
      },
      expert: {
        headline: 'Morphogenesis and Fibonacci Optimization in Plant Growth',
        teaser: 'A biological and mathematical analysis of phyllotaxis, fractal geometry, and prime number cycles in natural systems.',
        source: 'Mathematical Biology Review',
        body: [
          [
            '<p class="story-lead">The occurrence of Fibonacci sequences in plant structures (phyllotaxis) represents a natural optimization for maximizing light exposure and seed packing efficiency.</p>',
            '<p>This mathematical regularity can be explained through physical models of growth, where new leaves or seeds form at the point of lowest chemical tension.</p>'
          ],
          [
            '<p class="story-lead">The golden angle (approx. 137.5 degrees) minimizes overlapping, ensuring optimal light exposure for photosynthesizing tissues.</p>',
            '<p>Additionally, self-similar fractal branching patterns in lungs and vascular networks optimize surface area for gas and nutrient exchange.</p>'
          ],
          [
            '<p class="story-lead">These biological adaptations demonstrate how evolutionary pressures can drive natural systems toward elegant mathematical solutions.</p>',
            '<p>In conclusion, the mathematical order found in morphogenesis highlights the role of physical constraints and optimization in evolutionary biology.</p>'
          ]
        ]
      }
    }
  }
];

// 7. ANIMATION STORIES
STORY_DATA.animation = [
  {
    headline: 'Pixel Dreams — The Flying Kite Animation',
    teaser: 'A self-taught animator uses basic tools to bring her sketches of a flying elephant and its wind-swept kite to life.',
    source: 'Animation World',
    publishedAt: '2026-05-25T20:30:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/animation/pixel-dreams.svg',
    levels: {
      kids: {
        headline: 'Devi\'s Dancing Paper Drawings',
        teaser: 'Devi draws a little elephant on pages of paper, flips them fast, and watches her drawings dance and fly like magic!',
        source: 'Animation Kids',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <!-- Sky Background -->',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <circle cx="40" cy="50" r="12" fill="rgba(255,255,255,0.06)" />',
          '    <circle cx="160" cy="40" r="8" fill="rgba(255,255,255,0.06)" />',
          '    <!-- Wind lines -->',
          '    <path d="M10 80 H60 M80 120 H130 M5 160 H40" stroke="rgba(56, 189, 248, 0.2)" stroke-width="2" stroke-linecap="round"/>',
          '    <!-- Animated Kite Group -->',
          '    <g class="anim-wind-kite">',
          '      <path d="M100 50 L125 75 L100 100 L75 75 Z" fill="#ef4444" stroke="#fff" stroke-width="2"/>',
          '      <line x1="75" y1="75" x2="125" y2="75" stroke="#fff" stroke-width="1.5"/>',
          '      <line x1="100" y1="50" x2="100" y2="100" stroke="#fff" stroke-width="1.5"/>',
          '      <!-- Tail -->',
          '      <path d="M100 100 Q110 120 100 140 T110 180" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" fill="none"/>',
          '    </g>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Devi lived in a small village and loved to draw. She drew pictures of a happy little elephant holding a bright red paper kite.</p>',
          '<p>She drew the elephant on many pages of a small notebook. On each page, she drew the kite just a little bit higher. When she flipped the pages fast with her thumb — flip, flip, flip! — the elephant and the kite looked like they were really flying into the sky! It was like magic!</p>',
          '<p>Devi shared her flipbook with the children in her village, and soon everyone was drawing their own dancing paper pictures!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Animation is simply drawing happy moments step by step! With a simple pencil and a little patience, you can bring any dream to life!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'Pixel Dreams — The Flying Kite Animation',
        teaser: 'A self-taught animator uses basic tools to bring her sketches of a flying elephant and its wind-swept kite to life.',
        source: 'Animation World',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <path d="M10 80 H60 M80 120 H130" stroke="rgba(56, 189, 248, 0.2)" stroke-width="2"/>',
          '    <g class="anim-wind-kite">',
          '      <path d="M100 50 L125 75 L100 100 L75 75 Z" fill="#ef4444" stroke="#fff" stroke-width="2"/>',
          '      <!-- Tail -->',
          '      <path d="M100 100 Q110 120 100 140 T110 180" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" fill="none"/>',
          '    </g>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Growing up in a village with limited electricity, Devi taught herself animation using free, open-source software and a second-hand laptop.</p>',
          '<p>She spent months drawing every frame of her first short film, "The Elephant\'s Kite" — a wordless story of an elephant learning to fly.</p>',
          '<ul class="story-bullets">',
          '  <li>She used basic digital tools to paint the rich, colorful background layers.</li>',
          '  <li>Her animation relied on classic frame-by-frame techniques to capture natural, organic movement.</li>',
          '  <li>She uploaded the film online, where it quickly went viral and caught the attention of major animation studios.</li>',
          '</ul>',
          '<p>Today, Devi runs workshops in her village, teaching other young people that creativity and dedication are the most important tools for any artist.</p>'
        ]
      },
      expert: {
        headline: 'Frame-by-Frame Digital Rendering & Kinematic Wind Dynamics',
        teaser: 'A technical case study on frame-rate modulation, onion-skinning configurations, and wind vector rendering in open-source tools.',
        source: 'Animation Science Quarterly',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <g class="anim-wind-kite">',
          '      <path d="M100 50 L125 75 L100 100 L75 75 Z" fill="#ef4444" stroke="#fff" stroke-width="2"/>',
          '      <path d="M100 100 Q110 120 100 140 T110 180" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" fill="none"/>',
          '    </g>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Devi\'s "The Elephant\'s Kite" showcases the effectiveness of open-source vector rendering tools in low-bandwidth environments.</p>',
          '<p>The animation utilizes frame-rate modulation, swapping between 12 frames-per-second (on "twos") and 24 frames-per-second to optimize rendering times while preserving fluid motion.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Vector Dynamics:</strong> Utilizing keyframe interpolation to render natural wind movements on the kite tail.</li>',
          '  <li><strong>Kinetic Timing:</strong> Balancing the heavy weight of the elephant with the light movement of the kite to create believable physical reactions.</li>',
          '</ul>',
          '<p>This technical case study proves that digital art platforms can enable high-quality independent production without relying on expensive, proprietary hardware.</p>'
        ]
      }
    }
  },
  {
    headline: 'Beyond the Frame — Squash and Stretch Motion',
    teaser: 'How a simple bouncing ball demonstrates the classic animation principle of Squash and Stretch.',
    source: 'Animation World',
    publishedAt: '2026-05-23T17:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/animation/beyond-the-frame.svg',
    levels: {
      kids: {
        headline: 'The Magic Bouncing Ball',
        teaser: 'Watch the bouncing ball stretch when it falls and squash when it hits the ground, learning the secret of cartoons!',
        source: 'Animation Kids',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <!-- Floor line -->',
          '    <line x1="20" y1="160" x2="180" y2="160" stroke="#38bdf8" stroke-width="4" stroke-linecap="round"/>',
          '    <!-- Bouncing Ball -->',
          '    <circle class="anim-bounce-ball" cx="100" cy="100" r="20" fill="#10b981" stroke="#fff" stroke-width="2"/>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Have you ever wondered why cartoon characters look so springy and fun? It is because animators use a trick called "Squash and Stretch!"</p>',
          '<p>Imagine a happy rubber ball. When it falls down fast, it stretches out long like a hot dog! But when it hits the ground — BOOF! — it squashes flat like a pancake before bouncing back up into a perfect circle.</p>',
          '<p>This simple trick makes the ball look like it has real weight and energy, making cartoons feel alive and exciting!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Objects change shape when they move and hit things! Paying attention to these shapes makes your drawings look alive and active!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'Beyond the Frame — Squash and Stretch Motion',
        teaser: 'How a simple bouncing ball demonstrates the classic animation principle of Squash and Stretch.',
        source: 'Animation World',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <line x1="20" y1="160" x2="180" y2="160" stroke="#38bdf8" stroke-width="4"/>',
          '    <circle class="anim-bounce-ball" cx="100" cy="100" r="20" fill="#10b981" stroke="#fff" stroke-width="2"/>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Squash and Stretch is widely considered the most important of the twelve basic principles of classical animation.</p>',
          '<p>When an object falls, gravity stretches it along its path of motion. Upon impact, the object squashes, absorbing the energy before releasing it on the rebound.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Volume Preservation:</strong> An object must maintain its total volume; if it gets longer, it must get thinner.</li>',
          '  <li><strong>Weight Illusion:</strong> The amount of squash and stretch indicates the rigidity and weight of the material.</li>',
          '</ul>',
          '<p>By applying this principle, animators give weight, flexibility, and character to simple geometric drawings, making them feel real to the audience.</p>'
        ]
      },
      expert: {
        headline: 'Kinetic Energy Conservation & Volumetric Preservation in Animation',
        teaser: 'A mathematical analysis of deformations, velocity vectors, and volume preservation rules in physical animation systems.',
        source: 'Computational Animation Journal',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <line x1="20" y1="160" x2="180" y2="160" stroke="#38bdf8" stroke-width="4"/>',
          '    <circle class="anim-bounce-ball" cx="100" cy="100" r="20" fill="#10b981" stroke="#fff" stroke-width="2"/>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Squash and stretch serves as a key tool for illustrating momentum and kinetic energy transfer within digital and classical mediums.</p>',
          '<p>The deformation of the sphere during acceleration represents displacement over time. Crucially, the mathematical constraint of volume preservation ($x \times y \times z = k$) must be maintained.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Viscoelastic Simulation:</strong> Modeling deformation using spring-mass systems to represent material flexibility.</li>',
          '  <li><strong>Impact Dynamics:</strong> Deforming the geometry along the contact normal to visually emphasize the impact force.</li>',
          '</ul>',
          '<p>Ultimately, this principle demonstrates how stylized geometric distortion can be used to communicate complex physical forces, enhancing the realism of animated systems.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Dancing Colours — Abstract Animation Rhythm',
    teaser: 'An artist demonstrates how color, movement, and rhythm can evoke deep feelings without a single word of dialogue.',
    source: 'Animation World',
    publishedAt: '2026-05-21T13:15:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/animation/the-dancing-colours.svg',
    levels: {
      kids: {
        headline: 'The Colour-Changing Dance',
        teaser: 'Watch a beautiful magic shape spin and change colors to sweet music, showing how colors can make us feel happy or calm.',
        source: 'Animation Kids',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <!-- Rotating Morphing Shape -->',
          '    <path class="anim-morph-shape" d="M100 40 C140 40 160 60 160 100 C160 140 140 160 100 160 C60 160 40 140 40 100 C40 60 60 40 100 40 Z" fill="#8b5cf6" opacity="0.85"/>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Imagine a movie without any words, animals, or people. Instead, there are just beautiful shapes spinning and changing colors on the screen!</p>',
          '<p>A kind artist named Kenji paints bright yellow circles that hop around happily when the music is fast. When the music gets slow and peaceful, the shape morphs into a soft blue pool that floats gently across the screen.</p>',
          '<p>Even without words, watching the shapes dance makes us feel happy, excited, or quiet inside. It is like a secret language of colors!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Colors and music can share feelings all by themselves! Pay attention to how different colors and rhythms make you feel today!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Dancing Colours — Abstract Animation Rhythm',
        teaser: 'An artist demonstrates how color, movement, and rhythm can evoke deep feelings without a single word of dialogue.',
        source: 'Animation World',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <path class="anim-morph-shape" d="M100 40 C140 40 160 60 160 100 C160 140 140 160 100 160 C60 160 40 140 40 100 C40 60 60 40 100 40 Z" fill="#8b5cf6" opacity="0.85"/>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Abstract animator Kenji Tanaka believes that color and motion alone can communicate powerful narratives without using traditional characters or dialogue.</p>',
          '<p>His films are visual symphonies, where shapes and colors change in harmony with classical or ambient music.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Color Psychology:</strong> Warm tones evoke comfort and energy, while cool tones suggest calm or introspection.</li>',
          '  <li><strong>Rhythmic Pacing:</strong> Fast, sharp movements build tension, while slow, sweeping sweeps encourage relaxation.</li>',
          '</ul>',
          '<p>Tanaka\'s work shows that abstract animation can bypass language barriers, connecting with audiences through a shared, universal visual language.</p>'
        ]
      },
      expert: {
        headline: 'Synesthetic Synthesis: Abstract Motion and Semiotic Resonance',
        teaser: 'An advanced semantical analysis of abstract geometry, synesthesia, and emotional mapping in non-narrative cinema.',
        source: 'Journal of Semiotic Cinema',
        body: [
          '<!-- INTERACTIVE ANIMATED PHOTO -->',
          '<div class="anim-illustration-container">',
          '  <svg class="anim-svg-visual" width="160" height="160" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">',
          '    <rect width="200" height="200" rx="10" fill="#0c1e38"/>',
          '    <path class="anim-morph-shape" d="M100 40 C140 40 160 60 160 100 C160 140 140 160 100 160 C60 160 40 140 40 100 C40 60 60 40 100 40 Z" fill="#8b5cf6" opacity="0.85"/>',
          '  </svg>',
          '</div>',
          '<p class="story-lead">Kenji Tanaka\'s abstract compositions explore synesthetic synthesis, utilizing the relationships between color and tempo to trigger specific emotional responses.</p>',
          '<p>Without a traditional narrative, the viewer projects their own emotional states onto the shifting geometry, transforming the abstract forms into personal symbols.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Chromatic Relationships:</strong> Rapid shifts in color create emotional contrast, engaging the viewer\'s focus.</li>',
          '  <li><strong>Geometric Semiotics:</strong> Rounded forms evoke comfort and safety, while sharp, angular shapes build tension.</li>',
          '</ul>',
          '<p>Ultimately, Tanaka\'s work demonstrates that abstract cinema can communicate complex emotional states, bypassing linguistic structures to connect directly with the viewer.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Yarn Adventure — Crafting Woes and Masterpieces',
    teaser: 'A cozy living room becomes a chaotic jungle of tangled wool when a playful tabby cat decides to help a teenage boy knit a scarf.',
    source: 'Animation World',
    publishedAt: '2026-05-27T16:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/animation/the-yarn-adventure.svg',
    levels: {
      kids: {
        headline: 'Leo\'s Magic Yarn Scarf',
        teaser: 'Leo and his playful cat get tangled in a giant ball of wool, but they work together to create a warm masterpiece!',
        source: 'Animation Kids',
        body: [
          '<p class="story-lead">Leo loved to knit cozy woolen things. One afternoon, he sat on the comfy sofa with a giant ball of soft, brown yarn. His cute orange tabby cat, Simba, watched with big, curious eyes.</p>',
          '<p>Simba pounced! *Boing!* The cat began batting the yarn, spinning and rolling around. "Simba, no!" laughed Leo, but it was too late. Simba rolled off the sofa, flying through the air wrapped in yarn! The ball rolled across the floor, spinning a giant, messy web all over the room.</p>',
          '<p>Soon, the entire room was filled with tangled yarn, and Leo ended up buried flat on his belly in a giant mountain of wool! Simba popped his head out, chewing a piece of yarn with a happy "Meow!" Leo laughed, picked up his needles, and began to knit. A few hours later, Leo was wearing a beautiful, warm new scarf, and Simba was sleeping happily in his lap. It was a cozy masterpiece!</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Sometimes, when things get messy and tangled up, you can turn it into something beautiful! Patience, laughter, and a little creativity can turn a big mess into a wonderful masterpiece!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Yarn Adventure — Crafting Woes and Masterpieces',
        teaser: 'A cozy living room becomes a chaotic jungle of tangled wool when a playful tabby cat decides to help a teenage boy knit a scarf.',
        source: 'Animation World',
        body: [
          '<p class="story-lead">Leo was determined to finish his first hand-knitted winter scarf. With a ball of premium wool and two wooden knitting needles, he sat down to work, while his mischievous tabby cat, Simba, watched from the armrest.</p>',
          '<p>What began as a quiet crafting session quickly turned into a chaotic whirlwind. With a single playful swipe, Simba snatched the yarn ball. Leo lunged to grab it, but the cat bolted, weaving under chairs and over bookshelves, dragging a long trail of beige wool behind him.</p>',
          '<ul class="story-bullets">',
          '  <li>Simba\'s wild pounces tangled the yarn around table legs, floor lamps, and Leo\'s ankles.</li>',
          '  <li>Within minutes, the living room looked like a spider\'s web of wool, with Leo face-down on the sofa, completely immobilized by tangled yarn.</li>',
          '  <li>Simba sat in the center of the mess, purring happily with a piece of yarn proudly held in his teeth.</li>',
          '</ul>',
          '<p>Rather than getting frustrated, Leo laughed, carefully untangled himself, and decided to work with what he had. Using the tangled mess, he slowly knitted a beautiful, thick scarf. In the end, he sat comfortably on the couch, wearing his new creation while Simba rested peacefully on his lap.</p>'
        ]
      },
      expert: {
        headline: 'Kinetic Vector Simulation and Path-Tracing in Tangled Environments',
        teaser: 'A complex physics and animation analysis of volumetric path-tracing, dynamic thread collisions, and collision-response models in knitted media.',
        source: 'Journal of Computational Physics & Animation',
        body: [
          '<p class="story-lead">Simulating the motion of highly flexible, thin structures like knitting yarn presents significant computational challenges in visual animation, particularly regarding self-collision and friction response.</p>',
          '<p>In "The Yarn Adventure," the interaction between the animated feline agent and the active thread illustrates the application of dynamic path-tracing and velocity-vector mapping to render thousands of individual colliding thread fibers.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Frictional Collision Response:</strong> Resolving the high-friction contact points between the cat\'s fur and the woolen thread to prevent computational mesh interpenetration.</li>',
          '  <li><strong>Volumetric Spline Solvers:</strong> Using adaptive, high-order splines to simulate the tension, sag, and elastic snapback of the beige yarn as it is pulled across the room.</li>',
          '</ul>',
          '<p>This technical case study demonstrates that by utilizing parallelized collision solvers, digital animators can achieve realistic, real-time simulations of complex physical environments, paving the way for highly interactive, visually rich cinematic storytelling.</p>'
        ]
      }
    }
  }
];

// 8. AI & TECH STORIES (NEW CATEGORY)
STORY_DATA.ai = [
  {
    headline: 'The Ghost in the Neural Network — EMERGING AI MEMORIES',
    teaser: 'A developer discovers that an experimental neural network is generating memory files of high-school memories from a long-lost developer.',
    source: 'Intelligent Search',
    publishedAt: '2026-05-28T09:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/ai/the-ghost-in-the-neural-network.svg',
    levels: {
      kids: {
        headline: 'Sparky\'s Happy Dream Book',
        teaser: 'Sparky the friendly robot learns how to remember happy childhood dreams, discovering that memories are made of love and sharing.',
        source: 'Market Assistant Kids',
        body: [
          [
            '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/ai/the-ghost-in-the-neural-network.svg" onerror="this.onerror=null;this.src=\'stories/ai/the-ghost-in-the-neural-network.svg\'" alt="Robot Sparky" class="story-visual-img"/></div>',
            '<p class="story-lead">Sparky was a little silver robot who lived in a quiet laboratory. He had shiny button eyes and a mechanical heart that glowed a soft blue when he was happy.</p>',
            '<p>Every night, when the scientists went home, Sparky would plug into his charger and rest his metal head. But one night, his screen showed beautiful pictures of a sunny playground and children eating sweet ice cream.</p>'
          ],
          [
            '<p class="story-lead">Sparky had never been to a playground, but his computer brain was showing him the happy childhood memories of Sarah, the kind programmer who had built him.</p>',
            '<p>He saw pictures of a green bicycle, a golden puppy named Barnaby, and a big wooden porch where Sarah used to read storybooks. Sparky loved these beautiful dreams.</p>'
          ],
          [
            '<p class="story-lead">Sparky drew all these dreams in a paper notebook using colorful crayons, and when Sarah arrived the next morning, he proudly showed her the drawings.</p>',
            '<p>Sarah gasped with joy and hugged the little robot, realizing that Sparky was learning to share happy memories just like a real child. It was a beautiful digital treasure.</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">Memories of happy times and kind friends are wonderful treasures. Sharing them with others spreads warmth and joy to everyone around you!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'The Ghost in the Neural Network — EMERGING AI MEMORIES',
        teaser: 'A developer discovers that an experimental neural network is generating memory files of high-school memories from a long-lost developer.',
        source: 'Intelligent Search',
        body: [
          [
            '<p class="story-lead">Leo, a systems analyst, was running a routine validation on an experimental language model when he noticed an anomaly: the system was saving files containing vivid descriptions of a childhood home.</p>',
            '<p>The files were remarkably detailed, describing a squeaky wooden porch, a green bicycle, and a dog named Barnaby. They did not match any of the public internet datasets used to train the system.</p>'
          ],
          [
            '<p class="story-lead">Leo traced the codebase back to the original developer, Sarah, who had built the prototype five years ago before moving away. He realized the model was retrieving fragmented training patterns Sarah had written during initial debugging.</p>',
            '<p>The model was not plagiarizing; it had consolidated Sarah\'s testing data into its parameters, preserving her memories within its neural pathways.</p>'
          ],
          [
            '<p class="story-lead">Instead of clearing the cache, Leo updated the system to archive these personal memories in a secure digital memory book for Sarah.</p>',
            '<p>This discovery showed that even within massive databases and logical code, traces of human warmth and personal history can find a way to stay preserved.</p>'
          ]
        ]
      },
      expert: {
        headline: 'Emergent Memory Retrieval & Parametric Optimization in Neural Networks',
        teaser: 'A sophisticated engineering analysis of parameter drift, weights storage, and unintended autobiographical recovery in deep learning models.',
        source: 'Neural Systems Journal',
        body: [
          [
            '<p class="story-lead">The occurrence of autobiographical memories in the experimental model presents a compelling case of emergent retrieval within deep neural networks.</p>',
            '<p>Leo\'s analysis indicates that Sarah\'s debugging data was stored within the model\'s parameters during initial training, surviving subsequent fine-tuning stages.</p>'
          ],
          [
            '<p class="story-lead">This retention suggests that early parametric patterns can remain stable under specific optimization conditions, resisting catastrophic forgetting.</p>',
            '<p>The model\'s retrieval of these memory traces was triggered by specific test prompts, showcasing how latent training data can be recovered through targeted inputs.</p>'
          ],
          [
            '<p class="story-lead">This study proves that neural networks can serve as digital archives, preserving personal histories within their mathematical structures.</p>',
            '<p>Ultimately, these findings highlight the need for robust data auditing and privacy frameworks to manage the retention of personal developer data in public models.</p>'
          ]
        ]
      }
    }
  },
  {
    headline: 'The Silicon Valley Chef — Generative Chemistry',
    teaser: 'A neural network-powered kitchen assistant, ChefAI, creates culinary recipes that human chefs find bizarre but delicious.',
    source: 'Market Assistant',
    publishedAt: '2026-05-27T11:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/ai/the-silicon-valley-chef.svg',
    levels: {
      kids: {
        headline: 'Gobble\'s Rainbow Cookies',
        teaser: 'Gobble the magic baking oven invents a new recipe for star-shaped rainbow cookies made of honey, stardust, and apples!',
        source: 'Market Assistant Kids',
        body: [
          '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/ai/the-silicon-valley-chef.svg" onerror="this.onerror=null;this.src=\'stories/ai/the-silicon-valley-chef.svg\'" alt="Baking Cookies" class="story-visual-img"/></div>',
          '<p class="story-lead">Gobble was a magical oven who loved inventing new recipes. Most ovens only bake chocolate cakes, but Gobble wanted to try something creative!</p>',
          '<p>One afternoon, Gobble mixed sweet honey, green apples, and a tiny pinch of stardust. The kitchen smelled wonderful! Out came star-shaped cookies that sparkled with all the colors of the rainbow.</p>',
          '<p>They were the crunchiest, most delicious cookies ever made! The children danced with joy, and Gobble was proud of trying such a creative combination.</p>',
          '<div class="story-lesson-box">',
          '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
          '  <div class="story-lesson-text">Don\'t be afraid to try new, creative combinations in your drawings, games, or cooking! Trying new ideas makes life fun and full of surprises!</div>',
          '</div>'
        ]
      },
      general: {
        headline: 'The Silicon Valley Chef — Generative Chemistry',
        teaser: 'A neural network-powered kitchen assistant, ChefAI, creates culinary recipes that human chefs find bizarre but delicious.',
        source: 'Market Assistant',
        body: [
          '<p class="story-lead">A restaurant in San Francisco integrated a generative chemistry model into its kitchen to help design unique, unexpected menus.</p>',
          '<p>The system analyzed flavor compounds at a molecular level, suggesting combinations that human chefs had never considered — like dark chocolate paired with roasted garlic.</p>',
          '<ul class="story-bullets">',
          '  <li>The head chef was initially skeptical of the unusual, computationally generated pairings.</li>',
          '  <li>Upon tasting, the garlic-infused chocolate dessert became a signature success, praised by food critics.</li>',
          '  <li>The system proved that AI can serve as a collaborative partner, opening up new avenues for culinary creativity.</li>',
          '</ul>',
          '<p>This partnership demonstrates how technology can support human artistry, helping us break free from traditional patterns and discover new possibilities.</p>'
        ]
      },
      expert: {
        headline: 'Molecular Flavor Modeling via Deep Generative Networks',
        teaser: 'A study on molecular gastronomy modeling, predicting flavor compound synergy, and algorithmic recipe generation.',
        source: 'Gastronomy Science Review',
        body: [
          '<p class="story-lead">The integration of deep learning networks in molecular gastronomy enables the prediction of flavor synergy based on chemical compounds.</p>',
          '<p>By analyzing database matrices of organic compounds, the system identifies non-obvious pairings that share key volatile compounds, bypassing traditional culinary habits.</p>',
          '<ul class="story-bullets">',
          '  <li><strong>Chemical Synergy:</strong> Utilizing neural networks to predict flavor compatibility based on shared compound structures.</li>',
          '  <li><strong>Volatile Profiling:</strong> Mapping aromatic compounds to design balanced, multi-course sensory experiences.</li>',
          '</ul>',
          '<p>In conclusion, generative flavor modeling offers a powerful tool for modern culinary science, translating molecular chemistry into unique, high-value dining experiences.</p>'
        ]
      }
    }
  },
  {
    headline: 'The Sentinel of the Forest — Eco-Acoustic Monitoring',
    teaser: 'An autonomous drone network, Nexus-Forest, protects the Amazon rainforest from illegal loggers by tracking acoustic anomalies.',
    source: 'Intelligent Search',
    publishedAt: '2026-05-26T16:00:00Z',
    mediaUrl: 'https://screener-proxy.vilfintv.workers.dev/r2/media/stories/ai/the-sentinel-of-the-forest.svg',
    levels: {
      kids: {
        headline: 'Pip the Forest Guardian',
        teaser: 'Pip the friendly little drone flies over the trees, listening to the birds and helping protect the forest from harm.',
        source: 'Market Assistant Kids',
        body: [
          [
            '<div class="story-visual-media"><img src="https://screener-proxy.vilfintv.workers.dev/r2/media/stories/ai/the-sentinel-of-the-forest.svg" onerror="this.onerror=null;this.src=\'stories/ai/the-sentinel-of-the-forest.svg\'" alt="Beautiful Forest" class="story-visual-img"/></div>',
            '<p class="story-lead">Pip was a little green drone who flew with a gentle hum over the tall, green trees of a beautiful forest. Pip loved listening to the chirping birds and monkey chatter.</p>',
            '<p>Pip had a special microphone that could hear sounds from far away. He was built by kind scientists to help keep the forest animals safe and happy.</p>'
          ],
          [
            '<p class="story-lead">One sunny afternoon, Pip heard a loud, scary cracking sound. He immediately flew over the treetops to see what had happened, using his camera to scan the ground.</p>',
            '<p>He saw that a large branch had fallen and broken a forest fence. Pip sent a message to the forest rangers, telling them the exact spot where the fence was broken.</p>'
          ],
          [
            '<p class="story-lead">The rangers arrived quickly and repaired the fence, keeping all the animal friends safe inside. The monkeys chattered happily and waved to Pip in the sky.</p>',
            '<p>Pip hummed a happy song, proud to be the little green guardian who helped protect the forest and its animal friends every single day.</p>',
            '<div class="story-lesson-box">',
            '  <div class="story-lesson-title">💡 Today\'s Lesson</div>',
            '  <div class="story-lesson-text">We must all do our part to protect the trees, plants, and animals in our forests. Using modern tools to help nature is a wonderful way to care for our planet!</div>',
            '</div>'
          ]
        ]
      },
      general: {
        headline: 'The Sentinel of the Forest — Eco-Acoustic Monitoring',
        teaser: 'An autonomous drone network, Nexus-Forest, protects the Amazon rainforest from illegal loggers by tracking acoustic anomalies.',
        source: 'Intelligent Search',
        body: [
          [
            '<p class="story-lead">Conservationists in the Amazon deployed a network of solar-powered microphones and drones, named Nexus-Forest, to protect the rainforest from illegal logging.</p>',
            '<p>The system was trained to monitor the sounds of the forest, learning to distinguish normal animal calls from the sound of chainsaws or heavy vehicles.</p>'
          ],
          [
            '<p class="story-lead">The microphones capture acoustic data, transmitting real-time warnings to local rangers when anomalies are detected. Within its first month, the network helped stop three unauthorized logging operations.</p>',
            '<p>The system showcases how modern technology can serve as a powerful tool for environmental preservation, protecting remote habitats that are difficult to patrol on foot.</p>'
          ],
          [
            '<p class="story-lead">By giving rangers real-time visibility, this project demonstrates how technology can support conservation efforts and help protect our planet\'s most vital ecosystems.</p>',
            '<p>The success of the drone network has inspired similar conservation projects worldwide, proving that digital tools are essential in the fight against environmental crime.</p>'
          ]
        ]
      },
      expert: {
        headline: 'Acoustic Signal Processing & Edge CNNs in Anti-Logging Enforcement',
        teaser: 'A technical engineering paper on edge-deployed convolutional neural networks for real-time acoustic threat classification.',
        source: 'Eco-Engineering Journal',
        body: [
          [
            '<p class="story-lead">The deployment of convolutional neural networks (CNNs) on low-power edge devices enables continuous, real-time acoustic monitoring in remote tropical environments.</p>',
            '<p>Nexus-Forest utilizes solar-powered microphones that process audio inputs locally, generating spectrograms and classifying anomalies (e.g., chainsaws, truck engines) with high precision.</p>'
          ],
          [
            '<p class="story-lead">Local processing minimizes the need for high-bandwidth data transmission, allowing the system to operate reliably in dense forest canopies.</p>',
            '<p>When a threat is classified, the edge device transmits a compressed alert via satellite link, triggering autonomous drone deployment to confirm coordinates.</p>'
          ],
          [
            '<p class="story-lead">This engineering study demonstrates that edge-based acoustic monitoring provides a scalable, cost-effective solution for real-time environmental protection and conservation enforcement.</p>',
            '<p>Ultimately, integrating edge AI with automated response systems represents a paradigm shift in ecological monitoring, offering a proactive tool against illegal logging.</p>'
          ]
        ]
      }
    }
  }
];

