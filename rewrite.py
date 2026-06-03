import re

def rewrite_education():
    with open("education_backup.html", "r", encoding="utf-8") as f:
        content = f.read()

    # Find where the JS scripts start
    script_start_idx = content.find('<script src="kanji_data.js"></script>')
    if script_start_idx == -1:
        print("Could not find script start!")
        return

    scripts_block = content[script_start_idx:]

    new_html = """<!DOCTYPE html>
<html lang="en" data-theme="khan">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>VilfinTV Academy | Education</title>
<meta name="description" content="VilfinTV Academy — Premium Interactive Learning Hubs."/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600;700&family=Bebas+Neue&family=Inter:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
/* ==========================================================================
   KHAN ACADEMY STYLE RESET & BASE
   ========================================================================== */
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', 'DM Sans', sans-serif;
  background-color: #ffffff;
  color: #21242c;
  line-height: 1.5;
  padding-bottom: 60px;
}
a { color: inherit; text-decoration: none; transition: color 0.2s ease; }
button { font-family: inherit; cursor: pointer; transition: all 0.2s ease; }

/* Top Navbar */
.top-menubar {
  position: sticky; top: 0; z-index: 1000;
  height: 60px; background-color: #ffffff;
  border-bottom: 1px solid #e2e2e2;
}
.nav-inner {
  max-width: 1200px; margin: 0 auto; height: 100%;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px;
}
.nav-brand-group { display: flex; align-items: center; gap: 24px; }
.nav-brand {
  display: flex; align-items: center; gap: 8px;
  font-size: 20px; font-weight: 700; color: #14bf96;
}
.nav-links {
  display: flex; align-items: center; gap: 16px; font-weight: 600; color: #3b3e46; font-size: 15px;
}
.nav-links a:hover { color: #14bf96; }

/* Hero Section */
.hero-section {
  max-width: 1200px; margin: 48px auto; padding: 0 20px;
  display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: center;
}
@media(max-width: 900px) {
  .hero-section { grid-template-columns: 1fr; text-align: center; }
}
.hero-title {
  font-size: 42px; font-weight: 700; color: #21242c; margin-bottom: 16px; line-height: 1.1;
  font-family: 'Playfair Display', serif;
}
.hero-subtitle {
  font-size: 18px; color: #3b3e46; margin-bottom: 32px;
}
.hero-cards-container {
  display: flex; flex-direction: column; gap: 12px;
}
.hero-card-title {
  font-size: 22px; font-weight: 700; margin-bottom: 16px;
}
.user-card {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border: 2px solid #e2e2e2; border-radius: 4px;
  font-weight: 600; font-size: 16px; color: #1865f2;
}
.user-card:hover {
  background-color: #f7f7f8; border-color: #1865f2;
}

/* Subjects Grid Section */
.subjects-section {
  background-color: #f7f7f8;
  padding: 48px 20px; border-top: 1px solid #e2e2e2;
}
.subjects-inner {
  max-width: 1200px; margin: 0 auto;
}
.subjects-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 32px;
}
.subject-card {
  display: flex; flex-direction: column;
}
.subject-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
  padding-bottom: 8px; border-bottom: 2px solid #e2e2e2;
}
.subject-icon {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; color: white; flex-shrink: 0;
}
.subject-title {
  font-size: 18px; font-weight: 700; color: #21242c;
}
.subject-links {
  display: flex; flex-direction: column; gap: 12px;
}
.subject-links a {
  font-size: 15px; color: #1865f2; font-weight: 600;
  display: flex; justify-content: space-between; align-items: center;
}
.subject-links a:hover {
  text-decoration: underline;
}

/* Colors for Subject Icons */
.icon-social { background: #d92916; }
.icon-econ { background: #e07d10; }
.icon-math-hs { background: #db4d8b; }
.icon-math-pk { background: #ff9200; }
.icon-language { background: #9059ff; }
.icon-life { background: #00a699; }
.icon-science { background: #14bf96; }
.icon-cs { background: #1865f2; }

/* Lesson View Container */
.lesson-view-container {
  display: none; max-width: 1200px; margin: 40px auto; padding: 0 20px;
}
.back-btn {
  background: transparent; border: 1px solid #1865f2; color: #1865f2;
  font-weight: 600; padding: 8px 16px; border-radius: 4px; margin-bottom: 24px;
}
.back-btn:hover { background: #1865f2; color: white; }
.lesson-content-wrapper {
  background: white; border: 1px solid #e2e2e2; border-radius: 8px; padding: 32px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

/* Reused Classes from original */
.class-selector-bar, .subject-tab-bar { display: none; } /* Hide the old tabs in new view */
.study-lead { font-size: 18px; font-weight: 700; color: #1865f2; margin-bottom: 12px; }
.study-bullets { margin-left: 20px; margin-bottom: 16px; }
.study-bullets li { margin-bottom: 8px; }
.qa-item { border-bottom: 1px solid #e2e2e2; padding: 12px 0; }
.qa-question { font-weight: 600; cursor: pointer; color: #21242c; }
.qa-answer { display: none; margin-top: 8px; color: #3b3e46; border-left: 3px solid #14bf96; padding-left: 12px; }
.qa-item.active .qa-answer { display: block; }
.section-headline { font-size: 24px; font-weight: 700; margin-bottom: 16px; border-bottom: 1px solid #e2e2e2; padding-bottom: 8px; }
.option-btn { border: 1px solid #e2e2e2; padding: 10px; border-radius: 4px; background: #fff; margin-bottom: 8px; display: block; width: 100%; text-align: left; }
.option-btn:hover { background: #f7f7f8; }
.option-btn.correct { background: #e0f6e6; border-color: #14bf96; }
.option-btn.incorrect { background: #fce2e2; border-color: #d92916; }

/* JLPT specifics */
.sub-hub-bar { display: flex; gap: 12px; margin-bottom: 24px; border-bottom: 1px solid #e2e2e2; padding-bottom: 12px; overflow-x: auto; }
.sub-hub-btn { background: #f7f7f8; border: 1px solid #e2e2e2; padding: 8px 16px; border-radius: 16px; font-weight: 600; font-size: 14px; }
.sub-hub-btn.active { background: #1865f2; color: white; border-color: #1865f2; }
.kana-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.kana-card { border: 1px solid #e2e2e2; border-radius: 8px; text-align: center; padding: 12px; cursor: pointer; }
.kana-card:hover { border-color: #1865f2; }
.kana-card.active { background: #ebf2ff; border-color: #1865f2; }
.kana-char { font-size: 24px; font-weight: 700; }
.kana-layout { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }
@media(max-width:800px){ .kana-layout { grid-template-columns: 1fr; } }
.kana-details-box { border: 1px solid #e2e2e2; padding: 20px; border-radius: 8px; }
</style>
</head>
<body>

<!-- Top Navigation -->
<nav class="top-menubar">
  <div class="nav-inner">
    <div class="nav-brand-group">
      <div class="nav-brand">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>
        VilfinTV Academy
      </div>
      <div class="nav-links">
        <a href="index.html">Dashboard</a>
        <a href="news.html">News</a>
        <a href="story.html">Stories</a>
      </div>
    </div>
  </div>
</nav>

<!-- Hero Section -->
<div class="hero-section" id="hero-section">
  <div>
    <h1 class="hero-title">VilfinTV Academy boosts scores!</h1>
    <p class="hero-subtitle">Learn with structured courses, tackling practice problems, and exploring robust educational content.</p>
    <!-- Placeholder for Hero Image -->
    <div style="width:100%; height:250px; background: #e2e2e2; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #888;">
      [ Hero Image Placeholder ]
    </div>
  </div>
  <div>
    <h2 class="hero-card-title">Start learning today!</h2>
    <div class="hero-cards-container">
      <a href="#" class="user-card" onclick="return false;">
        I'm a learner <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
      </a>
      <a href="#" class="user-card" onclick="return false;">
        I'm a teacher <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
      </a>
      <a href="#" class="user-card" onclick="return false;">
        I'm a parent <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
      </a>
    </div>
    <div style="margin-top: 16px; font-size: 14px;">
      Already have a VilfinTV account? <a href="#" style="color:#1865f2; font-weight: 600;">Log in</a>
    </div>
  </div>
</div>

<!-- Subjects Grid Section -->
<div class="subjects-section" id="subjects-section">
  <div class="subjects-inner">
    <div class="subjects-grid">
      
      <!-- Math: Pre-K - 8th grade -->
      <div class="subject-card">
        <div class="subject-header">
          <div class="subject-icon icon-math-pk">1</div>
          <div class="subject-title">Math: Pre-K - 8th grade</div>
        </div>
        <div class="subject-links">
          <a href="#" onclick="openCbseLesson('math', 1); return false;">Class 1 Math</a>
          <a href="#" onclick="openCbseLesson('math', 2); return false;">Class 2 Math</a>
          <a href="#" onclick="openCbseLesson('math', 3); return false;">Class 3 Math</a>
          <a href="#" onclick="openCbseLesson('math', 4); return false;">Class 4 Math</a>
          <a href="#" onclick="openCbseLesson('math', 5); return false;">Class 5 Math</a>
          <a href="#" onclick="openCbseLesson('math', 6); return false;">Class 6 Math</a>
          <a href="#" onclick="openCbseLesson('math', 7); return false;">Class 7 Math</a>
          <a href="#" onclick="openCbseLesson('math', 8); return false;">Class 8 Math</a>
        </div>
      </div>

      <!-- Math: High school & College -->
      <div class="subject-card">
        <div class="subject-header">
          <div class="subject-icon icon-math-hs">Σ</div>
          <div class="subject-title">Math: High school & College</div>
        </div>
        <div class="subject-links">
          <a href="#" onclick="openCbseLesson('math', 9); return false;">Class 9 Math</a>
          <a href="#" onclick="openCbseLesson('math', 10); return false;">Class 10 Math</a>
          <a href="#" onclick="return false; alert('Coming Soon');">High School Geometry</a>
          <a href="#" onclick="return false; alert('Coming Soon');">Calculus</a>
        </div>
      </div>

      <!-- Science -->
      <div class="subject-card">
        <div class="subject-header">
          <div class="subject-icon icon-science">🔬</div>
          <div class="subject-title">Science</div>
        </div>
        <div class="subject-links">
          <a href="#" onclick="openCbseLesson('science', 3); return false;">Class 3 Science</a>
          <a href="#" onclick="openCbseLesson('science', 4); return false;">Class 4 Science</a>
          <a href="#" onclick="openCbseLesson('science', 5); return false;">Class 5 Science</a>
          <a href="#" onclick="openCbseLesson('science', 6); return false;">Class 6 Science</a>
          <a href="#" onclick="openCbseLesson('science', 7); return false;">Class 7 Science</a>
          <a href="#" onclick="openCbseLesson('science', 8); return false;">Class 8 Science</a>
          <a href="#" onclick="openCbseLesson('science', 9); return false;">Class 9 Science</a>
          <a href="#" onclick="openCbseLesson('science', 10); return false;">Class 10 Science</a>
        </div>
      </div>

      <!-- Social Studies -->
      <div class="subject-card">
        <div class="subject-header">
          <div class="subject-icon icon-social">🌍</div>
          <div class="subject-title">Social Studies</div>
        </div>
        <div class="subject-links">
          <a href="#" onclick="openCbseLesson('social', 5); return false;">Class 5 Social Science</a>
          <a href="#" onclick="openCbseLesson('social', 6); return false;">Class 6 Social Science</a>
          <a href="#" onclick="openCbseLesson('social', 7); return false;">Class 7 Social Science</a>
          <a href="#" onclick="openCbseLesson('social', 8); return false;">Class 8 Social Science</a>
          <a href="#" onclick="openCbseLesson('social', 9); return false;">Class 9 Social Science</a>
          <a href="#" onclick="openCbseLesson('social', 10); return false;">Class 10 Social Science</a>
        </div>
      </div>

      <!-- Language -->
      <div class="subject-card">
        <div class="subject-header">
          <div class="subject-icon icon-language">Aあ</div>
          <div class="subject-title">Language</div>
        </div>
        <div class="subject-links">
          <a href="#" onclick="openCbseLesson('english', 5); return false;">Class 5 English</a>
          <a href="#" onclick="openCbseLesson('english', 10); return false;">Class 10 English</a>
          <a href="#" onclick="openCbseLesson('hindi', 5); return false;">Class 5 Hindi</a>
          <a href="#" onclick="openCbseLesson('hindi', 10); return false;">Class 10 Hindi</a>
          <a href="#" onclick="openJlpt(5); return false;">Japanese JLPT N5</a>
          <a href="#" onclick="openJlpt(4); return false;">Japanese JLPT N4</a>
          <a href="#" onclick="openJlpt(3); return false;">Japanese JLPT N3</a>
          <a href="#" onclick="openJlpt(2); return false;">Japanese JLPT N2</a>
          <a href="#" onclick="openJlpt(1); return false;">Japanese JLPT N1</a>
        </div>
      </div>

      <!-- Economics -->
      <div class="subject-card">
        <div class="subject-header">
          <div class="subject-icon icon-econ">📈</div>
          <div class="subject-title">Economics</div>
        </div>
        <div class="subject-links">
          <a href="#" onclick="return false; alert('Coming Soon');">Microeconomics</a>
          <a href="#" onclick="return false; alert('Coming Soon');">Macroeconomics</a>
          <a href="#" onclick="return false; alert('Coming Soon');">Finance and capital markets</a>
        </div>
      </div>

      <!-- Life Skills -->
      <div class="subject-card">
        <div class="subject-header">
          <div class="subject-icon icon-life">🌱</div>
          <div class="subject-title">Life Skills</div>
        </div>
        <div class="subject-links">
          <a href="#" onclick="return false; alert('Coming Soon');">Financial Literacy</a>
          <a href="#" onclick="return false; alert('Coming Soon');">Career Development</a>
          <a href="#" onclick="return false; alert('Coming Soon');">Growth Mindset</a>
        </div>
      </div>

      <!-- Computer Science -->
      <div class="subject-card">
        <div class="subject-header">
          <div class="subject-icon icon-cs">💻</div>
          <div class="subject-title">Computer Science</div>
        </div>
        <div class="subject-links">
          <a href="#" onclick="return false; alert('Coming Soon');">Programming Basics</a>
          <a href="#" onclick="return false; alert('Coming Soon');">Web Development</a>
          <a href="#" onclick="return false; alert('Coming Soon');">Information Theory</a>
        </div>
      </div>

    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════
     DYNAMIC LESSON VIEW
     ========================================== -->
<div class="lesson-view-container" id="lesson-view-container">
  <button class="back-btn" onclick="closeLessonView()">
    <svg style="vertical-align: middle; margin-right: 4px;" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
    Back to Subjects
  </button>
  
  <div class="lesson-content-wrapper" id="lesson-content-wrapper">
    <!-- Dynamic CBSE/JLPT content goes here -->
    
    <!-- We will inject the existing cbse-container or jlpt-container content structure inside here dynamically -->
    
    <div id="cbse-content-area" style="display:none;">
      <h2 id="cbse-header-title" style="margin-bottom: 24px; font-size: 28px;">CBSE Lesson</h2>
      <div class="lesson-card" id="cbse-lesson-card"></div>
      <div style="margin-top: 24px;">
        <div class="qa-card" id="cbse-qa-card"></div>
        <div class="widget-card" id="cbse-widget-card" style="display:none;"></div>
      </div>
    </div>
    
    <div id="jlpt-content-area" style="display:none;">
      <h2 id="jlpt-header-title" style="margin-bottom: 24px; font-size: 28px;">JLPT Hub</h2>
      <div class="jlpt-container" id="jlpt-container" style="display:block;">
        <div class="sub-hub-bar">
          <button class="sub-hub-btn active" id="sub-hub-chart" onclick="switchJpSubHub('chart')">Hiragana & Katakana Hub</button>
          <button class="sub-hub-btn" id="sub-hub-kanji" onclick="switchJpSubHub('kanji')">Kanji & Casual Japanese</button>
          <button class="sub-hub-btn" id="sub-hub-levels" onclick="switchJpSubHub('levels')">JLPT Exam Center</button>
          <button class="sub-hub-btn" id="sub-hub-dict" onclick="switchJpSubHub('dict')">Dictionary</button>
        </div>

        <div id="jp-kana-section" class="kana-layout">
          <div>
            <div class="sub-hub-bar" style="border-bottom:none; margin-bottom:12px; padding-bottom:0;">
              <button class="sub-hub-btn active" id="btn-kana-hira" onclick="toggleKanaType('hiragana')">Hiragana</button>
              <button class="sub-hub-btn" id="btn-kana-kata" onclick="toggleKanaType('katakana')">Katakana</button>
            </div>
            <div class="kana-grid" id="kana-grid-area"></div>
          </div>
          <div class="kana-sidebar">
            <div class="kana-details-box" id="kana-details-box">Click a card</div>
            <div class="kana-game-box">
              <div class="kana-score-row"><span>RECALL GAME</span><span id="kana-score-display">SCORE: 0 / 0</span></div>
              <div class="kana-char" id="kana-game-question" style="text-align:center; margin:16px 0;">あ</div>
              <div id="kana-game-options"></div>
            </div>
          </div>
        </div>

        <div id="jp-kanji-casual-section" class="kana-layout" style="display:none;">
          <div>
            <div class="sub-hub-bar" style="border-bottom:none; margin-bottom:12px; padding-bottom:0;">
              <button class="sub-hub-btn active" id="btn-jp-kanji" onclick="toggleJpCasualArea('kanji')">Kanji Database</button>
              <button class="sub-hub-btn" id="btn-jp-casual" onclick="toggleJpCasualArea('casual')">Casual Phrases</button>
            </div>
            <div id="jp-kanji-area-container">
              <div class="sub-hub-bar" style="border-bottom:none; margin-bottom:12px; padding-bottom:0;">
                <button class="sub-hub-btn" id="btn-kanji-5" onclick="switchKanjiLevel(5)">N5</button>
                <button class="sub-hub-btn" id="btn-kanji-4" onclick="switchKanjiLevel(4)">N4</button>
                <button class="sub-hub-btn" id="btn-kanji-3" onclick="switchKanjiLevel(3)">N3</button>
                <button class="sub-hub-btn" id="btn-kanji-2" onclick="switchKanjiLevel(2)">N2</button>
                <button class="sub-hub-btn" id="btn-kanji-1" onclick="switchKanjiLevel(1)">N1</button>
              </div>
              <div class="kana-grid" id="jp-kanji-list-area"></div>
            </div>
            <div id="jp-casual-phrases-area" style="display:none;"></div>
          </div>
          <div class="kana-sidebar" id="kanji-sidebar-wrapper">
            <div class="kana-details-box" id="kanji-details-box">Click a Kanji</div>
            <div class="kana-game-box" id="kanji-game-box">
              <div class="kana-score-row"><span>KANJI RECALL</span><span id="kanji-score-display">SCORE: 0 / 0</span></div>
              <div class="kana-char" id="kanji-game-question" style="text-align:center; margin:16px 0;">日</div>
              <div id="kanji-game-options"></div>
            </div>
          </div>
        </div>

        <div id="jp-levels-section" style="display:none;">
          <div class="lesson-card" id="jlpt-lesson-card"></div>
          <div class="qa-card" id="jlpt-quiz-card" style="margin-top: 24px;"></div>
        </div>

        <div id="jp-dict-section" style="display:none;">
           <h3>JAP-ENG Dictionary</h3>
           <p>Feature placeholder.</p>
        </div>

      </div>
    </div>
    
  </div>
</div>

<!-- Navigation Logic -->
<script>
function openCbseLesson(subject, classNum) {
  document.getElementById('hero-section').style.display = 'none';
  document.getElementById('subjects-section').style.display = 'none';
  document.getElementById('lesson-view-container').style.display = 'block';
  
  document.getElementById('jlpt-content-area').style.display = 'none';
  document.getElementById('cbse-content-area').style.display = 'block';
  
  _activeHub = 'cbse';
  _activeSubject = subject;
  _activeClass = classNum;
  
  // Format Title
  const subName = subject.charAt(0).toUpperCase() + subject.slice(1);
  document.getElementById('cbse-header-title').innerText = "Class " + classNum + " " + subName;
  
  // Reuse existing render functions
  if (typeof renderCbseContent === 'function') {
    renderCbseContent();
  }
}

function openJlpt(level) {
  document.getElementById('hero-section').style.display = 'none';
  document.getElementById('subjects-section').style.display = 'none';
  document.getElementById('lesson-view-container').style.display = 'block';
  
  document.getElementById('cbse-content-area').style.display = 'none';
  document.getElementById('jlpt-content-area').style.display = 'block';
  
  _activeHub = 'jlpt';
  _activeJlptLevel = level;
  document.getElementById('jlpt-header-title').innerText = "Japanese JLPT N" + level + " Hub";
  
  // Activate JLPT section components
  if (typeof switchJlptLevel === 'function') {
    switchJlptLevel(level);
  }
  // Make sure to show the levels tab by default for a specific level
  if (typeof switchJpSubHub === 'function') {
    switchJpSubHub('levels');
  }
}

function closeLessonView() {
  document.getElementById('lesson-view-container').style.display = 'none';
  document.getElementById('hero-section').style.display = 'grid';
  document.getElementById('subjects-section').style.display = 'block';
}
</script>

"""

    final_html = new_html + scripts_block

    with open("education.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("education.html rewritten successfully!")

rewrite_education()
