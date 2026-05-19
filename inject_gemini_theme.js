/**
 * inject_gemini_theme.js
 * Injects the full Gemini animated theme into every sub-page HTML file.
 * Run once: node inject_gemini_theme.js
 */
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;

// ── Pages to process (relative to ROOT) ─────────────────────────────────────
const PAGES = [
  'sip_calc.html',
  'lumpsum_calc.html',
  'allocation_calc.html',
  'combined_calc.html',
  'compare_calc.html',
  'html_converter.html',
  'pine_script_generator.html',
  'screener_query_generator.html',
  'blog_intelligence_hub.html',
  'user-setup-guide.html',
  'user_guide.html',
  'user_manual.html',
  'radio-widget.html',
  'pre_market_briefing.html',
  'stock_research.html',
  'stock_status.html',
  'trendlyne_screener.html',
  'mf_live_screener.html',
  'mutual_fund_analyser.html',
  path.join('file', 'screener', 'advanced-standalone-multi-asset-screener.html'),
];

// ── Theme-init script (sets data-theme from localStorage before first paint) ─
const THEME_INIT_SCRIPT = `<script>(function(){var t=localStorage.getItem('viltv_theme');if(t)document.documentElement.setAttribute('data-theme',t);})();</script>`;

// ── Comprehensive Gemini CSS block ───────────────────────────────────────────
const GEMINI_CSS = `
/* ═══════════════════════════════════════════════════════════
   GEMINI ANIMATED THEME  — matches Google Gemini mobile app
   Auto-applied when data-theme="gemini" is set on <html>
   ═══════════════════════════════════════════════════════════ */
@keyframes gemini-flow{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes gemini-glow-pulse{0%,100%{opacity:.55}50%{opacity:1}}
@keyframes gemini-shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(200%)}}

/* CSS variable overrides — cascades to all var() uses automatically */
html[data-theme="gemini"]{
  --burn:#7c4dff;--burn2:#9c6fff;--burn3:#b388ff;
  --gold:#00bcd4;--gold2:#80deea;
  --green:#4caf50;--red:#ef5350;--amber:#ffa726;
  --purple:#7c4dff;--purple2:#5e35b1;
  --dark:rgba(7,4,18,.97);--dark2:rgba(11,7,26,.93);--dark3:rgba(16,10,36,.9);--dark4:rgba(22,14,48,.88);
  --card:rgba(14,9,32,.9);--card2:rgba(20,13,44,.88);--card3:rgba(26,17,54,.85);--card4:rgba(32,22,62,.82);
  --text:#e8eaf6;--text2:#9fa8da;--text3:#5c6bc0;
  --border:rgba(139,92,246,.22);--border2:rgba(139,92,246,.38);--border3:rgba(139,92,246,.5);
  --page-bg:#070412;
  --nav-bg:rgba(8,5,22,.88);--nav-text:#e8eaf6;--nav-border:rgba(139,92,246,.28);
  --glow:rgba(124,77,255,.4);
  --radius:12px;
}

/* ── Animated body ── */
[data-theme="gemini"] body{
  background:linear-gradient(-45deg,#0d1b3e,#1a0a38,#0a2040,#200845,#0b3030,#280a42,#0d2a38)!important;
  background-size:500% 500%!important;
  animation:gemini-flow 18s ease infinite!important;
  color:var(--text)!important;
}

/* ── Top navigation / header bars ── */
[data-theme="gemini"] .top-bar,
[data-theme="gemini"] .top-menubar,
[data-theme="gemini"] .main-nav,
[data-theme="gemini"] nav.nav,
[data-theme="gemini"] .nav-bar{
  background:rgba(8,5,22,.88)!important;
  backdrop-filter:blur(14px)!important;
  -webkit-backdrop-filter:blur(14px)!important;
  border-bottom:1px solid rgba(139,92,246,.3)!important;
  box-shadow:0 2px 20px rgba(0,0,0,.4)!important;
}

/* ── Hero / site header ── */
[data-theme="gemini"] .site-header{
  background:linear-gradient(135deg,rgba(7,4,18,.95) 0%,rgba(20,8,50,.92) 40%,rgba(8,30,60,.9) 70%,rgba(30,10,60,.92) 100%)!important;
  border-bottom:1px solid rgba(139,92,246,.3)!important;
}
[data-theme="gemini"] .site-header::before{
  background:radial-gradient(ellipse at 50% 0%,rgba(124,77,255,.12),transparent 70%)!important;
}
[data-theme="gemini"] .site-header::after{
  background:linear-gradient(90deg,transparent,rgba(124,77,255,.55),rgba(0,188,212,.45),rgba(124,77,255,.55),transparent)!important;
  animation:gemini-glow-pulse 3s ease-in-out infinite!important;
  height:2px!important;
  position:absolute!important;bottom:0!important;left:0!important;right:0!important;content:''!important;
}

/* ── Brand icon ── */
[data-theme="gemini"] .brand-icon{
  background:linear-gradient(135deg,#7c4dff,#00bcd4)!important;
  box-shadow:0 0 12px rgba(124,77,255,.45)!important;
}
[data-theme="gemini"] .brand-name span{color:#80deea!important}

/* ── Back / nav buttons ── */
[data-theme="gemini"] .back-btn{
  background:rgba(124,77,255,.1)!important;
  border-color:rgba(139,92,246,.35)!important;
  color:#b388ff!important;
}
[data-theme="gemini"] .back-btn:hover{
  background:rgba(124,77,255,.2)!important;
  border-color:rgba(139,92,246,.6)!important;
  color:#e8eaf6!important;
}

/* ── Cards / panels ── */
[data-theme="gemini"] .cc,
[data-theme="gemini"] .calc-stat,
[data-theme="gemini"] .card,
[data-theme="gemini"] .panel,
[data-theme="gemini"] .q-block,
[data-theme="gemini"] .mode-card,
[data-theme="gemini"] .signal-card,
[data-theme="gemini"] .news-card,
[data-theme="gemini"] .article-card,
[data-theme="gemini"] .stat-card,
[data-theme="gemini"] .result-card,
[data-theme="gemini"] .info-box,
[data-theme="gemini"] .output-section,
[data-theme="gemini"] .result-box{
  background:rgba(20,13,44,.88)!important;
  border-color:rgba(139,92,246,.25)!important;
}
[data-theme="gemini"] .panel{
  background:linear-gradient(180deg,rgba(14,9,32,.92),rgba(20,13,44,.92))!important;
}
[data-theme="gemini"] .mode-card:hover{
  border-color:rgba(139,92,246,.5)!important;
  background:rgba(124,77,255,.12)!important;
  box-shadow:0 4px 20px rgba(124,77,255,.15)!important;
  transform:translateY(-2px);
}
[data-theme="gemini"] .mode-card.selected{
  border-color:rgba(139,92,246,.7)!important;
  background:rgba(124,77,255,.2)!important;
}

/* ── Step / section headers ── */
[data-theme="gemini"] .step-header{border-bottom-color:rgba(139,92,246,.2)!important}
[data-theme="gemini"] .step-num{background:linear-gradient(135deg,#7c4dff,#00bcd4)!important}
[data-theme="gemini"] .step-title,
[data-theme="gemini"] .cc-title{color:#80deea!important}
[data-theme="gemini"] .cc-title::before{background:#7c4dff!important}

/* ── Form elements ── */
[data-theme="gemini"] .calc-input,
[data-theme="gemini"] .calc-select,
[data-theme="gemini"] .text-input,
[data-theme="gemini"] .paste-area,
[data-theme="gemini"] input:not([type="range"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]),
[data-theme="gemini"] textarea,
[data-theme="gemini"] select{
  background:rgba(14,9,32,.9)!important;
  border-color:rgba(139,92,246,.3)!important;
  color:#e8eaf6!important;
}
[data-theme="gemini"] .calc-input:focus,
[data-theme="gemini"] .text-input:focus,
[data-theme="gemini"] .paste-area:focus,
[data-theme="gemini"] input:focus,
[data-theme="gemini"] textarea:focus,
[data-theme="gemini"] select:focus{
  border-color:rgba(139,92,246,.6)!important;
  outline:none!important;
  box-shadow:0 0 0 2px rgba(124,77,255,.15)!important;
}
[data-theme="gemini"] input[type="range"]{accent-color:#7c4dff!important}
[data-theme="gemini"] .range-val{color:#80deea!important}

/* ── Primary action buttons ── */
[data-theme="gemini"] .action-btn.primary,
[data-theme="gemini"] .copy-btn,
[data-theme="gemini"] .query-ai-btn,
[data-theme="gemini"] .generate-btn,
[data-theme="gemini"] .run-btn,
[data-theme="gemini"] button.primary{
  background:linear-gradient(135deg,#7c4dff,#00bcd4)!important;
  box-shadow:0 4px 16px rgba(124,77,255,.35)!important;
}
[data-theme="gemini"] .action-btn.primary:hover,
[data-theme="gemini"] .query-ai-btn:hover{
  box-shadow:0 4px 24px rgba(124,77,255,.5)!important;
  transform:translateY(-1px);
}
[data-theme="gemini"] .copy-btn.copied{
  background:linear-gradient(135deg,#2e7d32,#43a047)!important;
}

/* ── Secondary buttons ── */
[data-theme="gemini"] .action-btn.secondary{
  background:rgba(20,13,44,.88)!important;
  border-color:rgba(139,92,246,.3)!important;
  color:#9fa8da!important;
}
[data-theme="gemini"] .action-btn.secondary:hover{
  border-color:rgba(139,92,246,.55)!important;
  color:#e8eaf6!important;
}

/* ── Option pills ── */
[data-theme="gemini"] .opt{
  border-color:rgba(139,92,246,.25)!important;
  background:rgba(20,13,44,.7)!important;
  color:#9fa8da!important;
}
[data-theme="gemini"] .opt:hover{
  border-color:rgba(139,92,246,.5)!important;
  color:#e8eaf6!important;
  background:rgba(124,77,255,.12)!important;
}
[data-theme="gemini"] .opt.selected{
  border-color:#7c4dff!important;
  background:rgba(124,77,255,.2)!important;
  color:#b388ff!important;
}

/* ── Tables ── */
[data-theme="gemini"] .alloc-table th,
[data-theme="gemini"] table th{
  background:linear-gradient(135deg,#5c35cc,#7c4dff)!important;
  color:#fff!important;
}
[data-theme="gemini"] .alloc-table td,
[data-theme="gemini"] table td{
  border-bottom-color:rgba(139,92,246,.12)!important;
  color:#9fa8da!important;
}
[data-theme="gemini"] .alloc-table tr:hover td,
[data-theme="gemini"] table tr:hover td{
  background:rgba(124,77,255,.07)!important;
}

/* ── Text/prompt output boxes ── */
[data-theme="gemini"] .prompt-box{
  background:rgba(7,4,18,.92)!important;
  border-color:rgba(139,92,246,.22)!important;
  color:#c5cae9!important;
}

/* ── Stat values ── */
[data-theme="gemini"] .calc-stat-val{color:#80deea!important}
[data-theme="gemini"] .range-val{color:#80deea!important}
[data-theme="gemini"] .q-num{background:#7c4dff!important}

/* ── Blog / hub specific ── */
[data-theme="gemini"] .header-chip{
  background:rgba(124,77,255,.12)!important;
  border-color:rgba(139,92,246,.25)!important;
  color:#b388ff!important;
}
[data-theme="gemini"] .eyebrow{color:#80deea!important}
[data-theme="gemini"] .signal-grid .signal-card,
[data-theme="gemini"] .hero-grid .panel{
  background:linear-gradient(180deg,rgba(14,9,32,.92),rgba(20,13,44,.92))!important;
  border-color:rgba(139,92,246,.2)!important;
}

/* ── Status indicators ── */
[data-theme="gemini"] .cf-dot.connected{
  background:#4caf50!important;
  box-shadow:0 0 6px rgba(76,175,80,.6)!important;
}

/* ── Footer ── */
[data-theme="gemini"] footer{
  background:rgba(7,4,18,.9)!important;
  border-top-color:rgba(139,92,246,.22)!important;
  color:var(--text)!important;
}

/* ── Custom scrollbar ── */
[data-theme="gemini"] ::-webkit-scrollbar{width:6px;height:6px}
[data-theme="gemini"] ::-webkit-scrollbar-track{background:rgba(7,4,18,.5)}
[data-theme="gemini"] ::-webkit-scrollbar-thumb{background:rgba(124,77,255,.4);border-radius:3px}
[data-theme="gemini"] ::-webkit-scrollbar-thumb:hover{background:rgba(124,77,255,.65)}

/* ── Selection highlight ── */
[data-theme="gemini"] ::selection{background:rgba(124,77,255,.35);color:#e8eaf6}
`;

// ── Regex to detect existing gemini/viltv_theme script block ────────────────
const OLD_SCRIPT_RE = /<script>\s*\(function\(\)\{[^<]*viltv_theme[^<]*\}\)\(\);\s*<\/script>/s;

// ── Helper: inject into a single file ───────────────────────────────────────
function processFile(filePath) {
  if (!fs.existsSync(filePath)) {
    console.warn(`  SKIP (not found): ${filePath}`);
    return;
  }

  let html = fs.readFileSync(filePath, 'utf8');
  let changed = false;

  // 1. Replace any existing partial theme init script, or insert after <head>
  if (OLD_SCRIPT_RE.test(html)) {
    html = html.replace(OLD_SCRIPT_RE, THEME_INIT_SCRIPT);
    changed = true;
    console.log(`  [replaced script] ${path.basename(filePath)}`);
  } else if (!html.includes("localStorage.getItem('viltv_theme')")) {
    // Insert after the opening <head> tag
    html = html.replace(/(<head[^>]*>)/, `$1\n${THEME_INIT_SCRIPT}`);
    changed = true;
    console.log(`  [added script] ${path.basename(filePath)}`);
  } else {
    console.log(`  [script ok]  ${path.basename(filePath)}`);
  }

  // 2. Remove any old/partial gemini CSS injection inside the script (already replaced above)
  // 3. Add comprehensive Gemini CSS before the closing </style> tag (first occurrence)
  if (!html.includes('GEMINI ANIMATED THEME  — matches Google Gemini')) {
    // Insert before the first </style>
    if (html.includes('</style>')) {
      html = html.replace('</style>', GEMINI_CSS + '\n</style>');
      changed = true;
      console.log(`  [added CSS]  ${path.basename(filePath)}`);
    } else {
      // No style block — add one in <head>
      html = html.replace('</head>', `<style>${GEMINI_CSS}\n</style>\n</head>`);
      changed = true;
      console.log(`  [added CSS block] ${path.basename(filePath)}`);
    }
  } else {
    console.log(`  [CSS ok]     ${path.basename(filePath)}`);
  }

  if (changed) {
    fs.writeFileSync(filePath, html, 'utf8');
  }
}

// ── Run ──────────────────────────────────────────────────────────────────────
console.log('\n🎨 Gemini Theme Injector — starting…\n');
for (const rel of PAGES) {
  processFile(path.join(ROOT, rel));
}
console.log('\n✅ Done. All pages processed.\n');
