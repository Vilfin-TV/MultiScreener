
/* ═══════════════════════════════════════════════════════════
   FEEDBACK MODAL — Logic
   ═══════════════════════════════════════════════════════════ */
(function(){
  var _fbType   = 'bug';
  var _fbRating = 0;

  function initChips(groupId) {
    var chips = document.querySelectorAll('#' + groupId + ' .fb-chip');
    chips.forEach(function(c){
      c.addEventListener('click', function(){
        chips.forEach(function(x){ x.classList.remove('active'); });
        c.classList.add('active');
      });
    });
  }
  initChips('fb-bug-severity');
  initChips('fb-feat-priority');
  initChips('fb-fb-recommend');

  window.fbStarHover = function(v){
    document.querySelectorAll('#fb-stars .fb-star').forEach(function(s){
      s.classList.toggle('lit', v > 0 ? parseInt(s.dataset.v) <= v : parseInt(s.dataset.v) <= _fbRating);
    });
  };
  window.fbStarPick = function(v){ _fbRating = v; fbStarHover(v); };

  window.openFeedbackModal = function(type){
    _fbType = type; _fbRating = 0;
    document.querySelectorAll('#fb-stars .fb-star').forEach(function(s){ s.classList.remove('lit'); });
    var cfg = {
      bug:      {icon:'🐞', cls:'fb-icon-bug',     title:'Report a Bug',      sub:'Help us identify and fix issues on vilfintv.com',   lbl:'Send Bug Report'},
      feature:  {icon:'💡', cls:'fb-icon-feature',  title:'Request a Feature', sub:'Tell us what you would like to see added',           lbl:'Send Request'},
      feedback: {icon:'💬', cls:'fb-icon-feedback', title:'Share Feedback',    sub:'Your thoughts help us improve the platform',         lbl:'Send Feedback'}
    };
    var c = cfg[type] || cfg.bug;
    var ic = document.getElementById('fb-icon');
    ic.textContent = c.icon; ic.className = 'fb-icon ' + c.cls;
    document.getElementById('fb-title').textContent    = c.title;
    document.getElementById('fb-subtitle').textContent = c.sub;
    document.getElementById('fb-send-label').textContent = c.lbl;
    ['bug','feature','feedback'].forEach(function(t){
      document.getElementById('fb-body-' + t).style.display = (t === type) ? 'block' : 'none';
    });
    var ov = document.getElementById('fb-overlay');
    ov.style.display = 'flex';
    requestAnimationFrame(function(){ ov.classList.add('show'); });
    document.body.style.overflow = 'hidden';
  };

  window.closeFeedbackModal = function(){
    var ov = document.getElementById('fb-overlay');
    ov.classList.remove('show');
    setTimeout(function(){ ov.style.display = 'none'; }, 280);
    document.body.style.overflow = '';
  };

  function getChip(id){ var a = document.querySelector('#'+id+' .fb-chip.active'); return a ? a.dataset.val : ''; }

  function buildAIQuery(type, f){
    var ts    = new Date().toISOString();
    var theme = (localStorage.getItem('viltv_theme') || 'default').toUpperCase();
    var ua    = navigator.userAgent;
    if (type === 'bug') {
      return ['# Bug Report — vilfintv.com','**Submitted:** '+ts,'**Theme:** '+theme,'',
        '## Issue Details','| Field | Value |','|-------|-------|',
        '| Page / Feature | '+(f.page||'N/A')+' |','| Severity | '+(f.severity||'Medium')+' |',
        '| Device | '+(f.device||'Unknown')+' |','| Browser | '+(f.browser||'Unknown')+' |','',
        '## What Went Wrong',f.desc||'(not provided)','',
        '## Expected Behaviour',f.expected||'(not provided)','',
        '## Additional Context',f.extra||'(none)','',
        '---','## 🤖 AI Fix Query (Claude / Copilot / VS Code)','```',
        'You are reviewing a bug report for vilfintv.com (GitHub Pages, static HTML/CSS/JS).',
        'The user reports the following issue on the "'+( f.page||'unknown')+'" page/feature:','',
        'PROBLEM: '+(f.desc||'').replace(/\n/g,' '),
        'EXPECTED: '+(f.expected||'').replace(/\n/g,' '),
        'SEVERITY: '+(f.severity||'Medium'),
        'DEVICE: '+(f.device||'')+' / '+(f.browser||''),'',
        'Please investigate the relevant code in the repository, identify the root cause,',
        'and provide a specific fix with the file name, line reference, and corrected code.',
        '```','','**User Agent:** `'+ua+'`'].join('\n');
    }
    if (type === 'feature') {
      return ['# Feature Request — vilfintv.com','**Submitted:** '+ts,'**Theme:** '+theme,'',
        '## Request Details','| Field | Value |','|-------|-------|',
        '| Area | '+(f.area||'N/A')+' |','| Priority | '+(f.priority||'Nice to have')+' |','',
        '## Feature Description',f.desc||'(not provided)','',
        '## Use Case / Why Needed',f.why||'(not provided)','',
        '## References / Examples',f.ref||'(none)','',
        '---','## 🤖 AI Implementation Query (Claude / Copilot / VS Code)','```',
        'You are helping implement a new feature for vilfintv.com (GitHub Pages, static HTML/CSS/JS).',
        'Feature area: "'+( f.area||'unknown')+'"','',
        'FEATURE: '+(f.desc||'').replace(/\n/g,' '),
        'USE CASE: '+(f.why||'').replace(/\n/g,' '),
        'PRIORITY: '+(f.priority||'Nice to have'),'',
        'Please suggest an implementation plan: which files to modify, the approach,',
        'and provide the key code changes. Keep within static HTML/CSS/JS constraints.',
        '```'].join('\n');
    }
    var stars = '★'.repeat(_fbRating)+'☆'.repeat(5-_fbRating);
    return ['# User Feedback — vilfintv.com','**Submitted:** '+ts,'**Theme:** '+theme,'',
      '## Summary','| Field | Value |','|-------|-------|',
      '| Rating | '+stars+' ('+_fbRating+'/5) |',
      '| Would Recommend | '+(f.recommend||'N/A')+' |','',
      '## What They Like',f.like||'(not provided)','',
      '## What Can Be Improved',f.improve||'(not provided)','',
      '## Additional Comments',f.other||'(none)','',
      '---','## 🤖 Improvement Query (Claude / Copilot / VS Code)','```',
      'You are reviewing user feedback for vilfintv.com. Rating: '+_fbRating+'/5.','',
      'LIKES: '+(f.like||'').replace(/\n/g,' '),
      'IMPROVE: '+(f.improve||'').replace(/\n/g,' '),'',
      'Suggest the top 3 actionable improvements for the codebase.',
      '```'].join('\n');
  }

  function collectFields(type){
    if (type==='bug') return {
      page:f('fb-bug-page'), desc:f('fb-bug-desc'), expected:f('fb-bug-expected'),
      severity:getChip('fb-bug-severity'), device:f('fb-bug-device'), browser:f('fb-bug-browser'), extra:f('fb-bug-extra')
    };
    if (type==='feature') return {
      area:f('fb-feat-area'), desc:f('fb-feat-desc'), why:f('fb-feat-why'),
      priority:getChip('fb-feat-priority'), ref:f('fb-feat-ref')
    };
    return { rating:_fbRating, like:f('fb-fb-like'), improve:f('fb-fb-improve'),
             recommend:getChip('fb-fb-recommend'), other:f('fb-fb-other') };
  }
  function f(id){ var el=document.getElementById(id); return el ? el.value : ''; }

  function validate(type, fields){
    if (type==='bug'){
      if (!fields.page) return 'Please select the affected page or feature.';
      if (!fields.desc || fields.desc.trim().length < 10) return 'Please describe the bug (at least 10 characters).';
    }
    if (type==='feature'){
      if (!fields.area) return 'Please select the area for the feature.';
      if (!fields.desc || fields.desc.trim().length < 10) return 'Please describe the feature (at least 10 characters).';
    }
    if (type==='feedback' && !_fbRating) return 'Please select a star rating.';
    return null;
  }

  function showToast(msg, cls){
    var t = document.getElementById('fb-toast');
    t.textContent = msg; t.className = 'fb-toast ' + (cls||'');
    t.classList.add('show');
    setTimeout(function(){ t.classList.remove('show'); }, 4500);
  }

  window.submitFeedback = function(){
    var type   = _fbType;
    var fields = collectFields(type);
    var err    = validate(type, fields);
    if (err){ showToast('⚠ '+err,'error'); return; }

    var btn = document.getElementById('fb-send-btn');
    var sp  = document.getElementById('fb-spinner');
    var lbl = document.getElementById('fb-send-label');
    btn.disabled=true; sp.style.display='block'; lbl.textContent='Sending…';

    var labels  = {bug:'Bug Report', feature:'Feature Request', feedback:'User Feedback'};
    var subject = '[VilfinTV '+( labels[type]||type)+'] '+new Date().toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'});
    var aiQuery = buildAIQuery(type, fields);

    fetch('https://screener-proxy.vilfintv.workers.dev/feedback', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({type:type, subject:subject, body:aiQuery})
    })
    .then(function(r){ return r.json(); })
    .then(function(data){
      btn.disabled=false; sp.style.display='none';
      if (data && data.ok){
        lbl.textContent='✓ Sent!';
        showToast('✅ Thank you! Your '+(labels[type]||'report')+' has been received.','success');
        setTimeout(function(){
          closeFeedbackModal();
          var defaults={bug:'Send Bug Report',feature:'Send Request',feedback:'Send Feedback'};
          lbl.textContent = defaults[type]||'Send Report';
        },1800);
      } else {
        lbl.textContent='Send Report';
        showToast('❌ '+(data&&data.message||'Failed to send. Please try again.'),'error');
      }
    })
    .catch(function(){
      btn.disabled=false; sp.style.display='none'; lbl.textContent='Send Report';
      showToast('❌ Network error. Please check your connection.','error');
    });
  };

  document.addEventListener('keydown',function(e){ if(e.key==='Escape') closeFeedbackModal(); });
})();
