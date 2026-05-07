const fs = require('fs');
const src = fs.readFileSync('index.html','utf8').split('\n');
const get = (from, to) => src.slice(from-1, to).join('\n');

const css_vars_layout   = get(31, 824);
const css_cf_modal      = get(1166, 1235);
const css_ljson         = get(1788, 1813);
const html_inputPanel   = get(2452, 2779);
const html_resultPanel  = get(2824, 2901);
const html_cfModal      = get(4159, 4248);
const js_state          = get(4719, 4728);
const js_ac             = get(4852, 5034);
const js_theme          = get(5036, 5039);
const js_services       = get(5067, 5261);
const js_directApi      = get(5263, 5313);
const js_freeAI         = get(5320, 5467);
const js_mdToHtml       = get(5469, 5529);
const js_workerQuery    = get(5531, 5583);
const js_loadBalanced   = get(5585, 5658);
const js_generateSend   = get(5690, 5975);
const js_progressBars   = get(5977, 6072);
const js_escHtml        = get(6403, 6403);
const js_selectOpt      = get(11417, 11435);
const js_q1q2           = get(11440, 11608);
const js_summary        = get(11613, 11632);
const js_genQuery       = get(11637, 11695);
const js_refreshCopy    = get(11700, 11767);
const js_paste          = get(11773, 12198);
const js_buildReport    = get(12201, 13315);
const js_download       = get(13316, 13370);
const js_ljson          = get(13374, 13660);
const js_gamma          = get(13663, 14256);

// Adapted switchMain for standalone (ID-based, no DOM order dependency)
const js_switchMain = `
function switchMain(idx, btn) {
  var panelMap = {0:'panel-input', 1:'panel-copy', 2:'panel-paste'};
  document.querySelectorAll('.panel').forEach(function(p) { p.classList.remove('active'); });
  var targetId = panelMap[idx];
  var target = targetId ? document.getElementById(targetId) : null;
  if (target) target.classList.add('active');
  document.querySelectorAll('.main-tab').forEach(function(b) { b.classList.remove('active'); });
  if (btn) {
    btn.classList.add('active');
  } else {
    var tId = idx === 0 ? 'main-tab-0' : 'main-tab-2';
    var t = document.getElementById(tId);
    if (t) t.classList.add('active');
  }
  var activePanel = targetId ? document.getElementById(targetId) : null;
  if (activePanel) setTimeout(function() { activePanel.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 60);
}`;

// No-op stubs for main-page-only functions
const js_stubs = `
function rbUpdateAiStatus(connected) {}
function closeSidePanel() { cfCloseModal(); }
`;

// Theme init + toggle
const js_themeInit = `
(function() {
  var t = localStorage.getItem('viltv_theme') || 'black';
  document.documentElement.setAttribute('data-theme', t);
})();
function toggleTheme() {
  var cur = document.documentElement.getAttribute('data-theme') || 'black';
  setTheme(cur === 'black' ? 'standard' : 'black');
}
`;

// Patch SYMBOLS_URL for 2-level-deep path
const js_acPatched = js_ac.replace(
  "SYMBOLS_URL: 'data/master_symbols.json'",
  "SYMBOLS_URL: '../../data/master_symbols.json'"
);

// Patch Escape key listener
const js_downloadPatched = js_download.replace(
  "document.addEventListener('keydown', e => { if (e.key==='Escape') closeSidePanel(); });",
  "document.addEventListener('keydown', function(e) { if (e.key==='Escape') cfCloseModal(); });"
);

// ljson-panel inside result tab
const html_ljsonPanel = `
  <div id="ljson-panel" style="display:none;margin-bottom:16px;background:var(--card);border:1px solid var(--border2);border-radius:10px;padding:0;overflow:hidden">
    <div style="background:var(--dark3);border-bottom:1px solid var(--border);padding:10px 16px;display:flex;align-items:center;justify-content:space-between">
      <div style="font-size:12px;font-weight:700;color:var(--gold2)">&#x1F4CA; Lossless JSON Report</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        <button onclick="exportLjsonHtml()" class="ljson-export-btn">&#x2B07; Export HTML</button>
        <button onclick="exportLjsonPdf()" class="ljson-export-btn">&#x1F5A8; Export PDF</button>
        <button onclick="generateGammaReport()" class="ljson-export-btn" style="background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff;border-color:#7c3aed">&#x2728; Gamma Style</button>
        <button onclick="copyLjsonRaw()" class="ljson-export-btn">&#x1F4CB; JSON</button>
      </div>
    </div>
    <div id="ljson-content" style="padding:0"></div>
  </div>`;

// Insert ljson-panel above the collapsible paste section in result panel
const html_resultPanelFull = html_resultPanel.replace(
  '  <!-- ── Collapsible paste section (hidden by default) ──',
  html_ljsonPanel + '\n  <!-- ── Collapsible paste section (hidden by default) ──'
);

// Hidden copy-content div for JS query storage
const html_copyContent = '<div id="copy-content" style="display:none!important;position:absolute;visibility:hidden;pointer-events:none" aria-hidden="true"><p>No query generated yet.</p></div>';

const html = [
'<!DOCTYPE html>',
'<html lang="en">',
'<head>',
'<meta charset="UTF-8"/>',
'<meta name="viewport" content="width=device-width,initial-scale=1.0"/>',
'<title>Advanced Multi-Asset Screener — VilfinTV</title>',
'<link rel="preconnect" href="https://fonts.googleapis.com"/>',
'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>',
'<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet"/>',
'<style>',
css_vars_layout,
css_cf_modal,
css_ljson,
'.sa-header{background:linear-gradient(135deg,#0c1b4d 0%,#0f2d6e 35%,#1d4ed8 75%,#2563eb 100%);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid rgba(147,197,253,.5);position:sticky;top:0;z-index:500}',
'.sa-back{display:inline-flex;align-items:center;gap:6px;color:#93c5fd;font-size:12px;font-weight:700;text-decoration:none;letter-spacing:.5px;padding:6px 14px;border:1px solid rgba(147,197,253,.3);border-radius:8px;transition:all .15s;background:rgba(255,255,255,.07)}',
'.sa-back:hover{color:#fff;border-color:rgba(147,197,253,.7);background:rgba(255,255,255,.15)}',
'.sa-title{font-family:"Bebas Neue",sans-serif;font-size:clamp(16px,3vw,24px);color:#fff;letter-spacing:3px;text-shadow:0 0 20px rgba(59,130,246,.4);position:absolute;left:50%;transform:translateX(-50%);white-space:nowrap}',
'.sa-actions{display:flex;align-items:center;gap:8px}',
'.sa-connect-btn{padding:6px 14px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.25);border-radius:8px;color:#fff;font-family:"DM Sans",sans-serif;font-size:11px;font-weight:700;cursor:pointer;transition:all .15s;letter-spacing:.3px;display:flex;align-items:center;gap:6px}',
'.sa-connect-btn:hover{background:rgba(255,255,255,.2);border-color:rgba(147,197,253,.6)}',
'.sa-theme-btn{width:32px;height:32px;border-radius:8px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#fff;cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center;transition:all .15s}',
'.sa-theme-btn:hover{background:rgba(255,255,255,.2)}',
'body{display:block!important}',
'.layout{display:block!important;height:auto!important;overflow:visible!important}',
'.main-content{overflow:visible!important}',
'@keyframes gammaSpin{to{transform:rotate(360deg)}}',
'@keyframes gammaBar{0%{width:0;margin-left:0}50%{width:60%;margin-left:20%}100%{width:0;margin-left:100%}}',
'@keyframes livePulse{0%,100%{opacity:1}50%{opacity:.4}}',
'@keyframes tvBlink{0%,100%{opacity:1}50%{opacity:.3}}',
'</style>',
'</head>',
'<body>',
'<div class="sa-header">',
'  <a class="sa-back" href="../../index.html">&#x2190; Back</a>',
'  <div class="sa-title">Multi-Asset Research</div>',
'  <div class="sa-actions">',
'    <button class="sa-connect-btn" onclick="openServicesModal()">',
'      <span id="cf-dot" class="cf-dot"></span>',
'      <span id="cf-label">Connect AI</span>',
'    </button>',
'    <button class="sa-theme-btn" onclick="toggleTheme()" title="Toggle theme">&#x1F313;</button>',
'  </div>',
'</div>',
'<div class="layout"><div class="main-content">',
'<nav class="main-nav">',
'  <button class="main-tab active" id="main-tab-0" onclick="switchMain(0,this)"><span class="tab-icon">&#x1F4CB;</span> Input Form</button>',
'  <button class="main-tab" id="main-tab-2" onclick="switchMain(2,this)"><span class="tab-icon">&#x1F4CA;</span> Result</button>',
'</nav>',
html_inputPanel,
html_resultPanelFull,
html_copyContent,
'</div></div>',
html_cfModal,
'<script src="../../config.js"><\/script>',
'<script>',
js_themeInit,
js_state,
js_stubs,
js_switchMain,
js_acPatched,
js_theme,
js_services,
js_directApi,
js_freeAI,
js_mdToHtml,
js_workerQuery,
js_loadBalanced,
js_generateSend,
js_progressBars,
js_escHtml,
js_selectOpt,
js_q1q2,
js_summary,
js_genQuery,
js_refreshCopy,
js_paste,
js_buildReport,
js_downloadPatched,
js_ljson,
js_gamma,
"document.addEventListener('DOMContentLoaded', function() { cfLoadSaved(); });",
'<\/script>',
'</body>',
'</html>'
].join('\n');

fs.writeFileSync('file/screener/advanced-standalone-multi-asset-screener.html', html, 'utf8');
console.log('Written:', html.length, 'chars,', Math.round(html.length/1024), 'KB');
