import os

def apply_fixes():
    with open('education.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update Video Controls in HTML
    old_video_html = """              <iframe id="academy-video-iframe" 
                      style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;" 
                      allow="autoplay; encrypted-media; picture-in-picture" 
                      allowfullscreen></iframe>
              <div id="academy-video-list\""""
              
    new_video_html = """              <iframe id="academy-video-iframe" 
                      style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;" 
                      allow="encrypted-media; picture-in-picture" 
                      allowfullscreen></iframe>
              <div id="academy-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:8px 16px; background:var(--card); border-bottom:1px solid var(--border);">
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px;" onclick="playPrevAcademyVideo()">&#9664; Back</button>
                <div style="font-size:12px; color:var(--text3);">Controls & Volume are inside video</div>
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px;" onclick="playNextAcademyVideo()">Next &#9654;</button>
              </div>
              <div id="academy-video-list\""""
              
    content = content.replace(old_video_html, new_video_html)

    # 2. Update playAcademyVideo and add next/prev functions
    old_play = """  window.playAcademyVideo = function(id) {
    const iframe = document.getElementById('academy-video-iframe');
    if (iframe) {
      iframe.src = 'https://www.youtube.com/embed/' + id + '?autoplay=1&rel=0';
    }
  };"""

    new_play = """  window.playAcademyVideo = function(id) {
    const iframe = document.getElementById('academy-video-iframe');
    if (iframe) {
      // Removed autoplay=1, explicitly added controls=1 so the native volume/mute bar is visible.
      iframe.src = 'https://www.youtube.com/embed/' + id + '?rel=0&controls=1';
    }
  };

  window.playNextAcademyVideo = function() {
    const kanaType = typeof _activeKanaType !== 'undefined' ? _activeKanaType : 'hiragana';
    const videos = kanaType === 'hiragana' ? _academyHiragana : _academyKatakana;
    if (!videos || !videos.length) return;
    const iframe = document.getElementById('academy-video-iframe');
    const src = iframe ? iframe.src : '';
    const match = src.match(/embed\\/([^?]+)/);
    const curId = match ? match[1] : null;
    let idx = videos.findIndex(v => v.id === curId);
    if (idx === -1 || idx === videos.length - 1) idx = 0;
    else idx++;
    window.playAcademyVideo(videos[idx].id);
  };

  window.playPrevAcademyVideo = function() {
    const kanaType = typeof _activeKanaType !== 'undefined' ? _activeKanaType : 'hiragana';
    const videos = kanaType === 'hiragana' ? _academyHiragana : _academyKatakana;
    if (!videos || !videos.length) return;
    const iframe = document.getElementById('academy-video-iframe');
    const src = iframe ? iframe.src : '';
    const match = src.match(/embed\\/([^?]+)/);
    const curId = match ? match[1] : null;
    let idx = videos.findIndex(v => v.id === curId);
    if (idx === -1 || idx === 0) idx = videos.length - 1;
    else idx--;
    window.playAcademyVideo(videos[idx].id);
  };"""

    content = content.replace(old_play, new_play)

    # 3. Separate Scores
    old_score_vars = """var _recallScoreCorrect = 0;
var _recallScoreTotal = 0;"""
    new_score_vars = """var _hiraScoreCorrect = 0;
var _hiraScoreTotal = 0;
var _kataScoreCorrect = 0;
var _kataScoreTotal = 0;"""
    content = content.replace(old_score_vars, new_score_vars)

    old_score_update = """  _recallScoreTotal++;
  if (isCorrect) _recallScoreCorrect++;
  
  document.getElementById('kana-score-display').textContent = 'SCORE: ' + _recallScoreCorrect + ' / ' + _recallScoreTotal;"""
    
    new_score_update = """  if (_activeKanaType === 'hiragana') {
    _hiraScoreTotal++;
    if (isCorrect) _hiraScoreCorrect++;
    document.getElementById('kana-score-display').textContent = 'SCORE: ' + _hiraScoreCorrect + ' / ' + _hiraScoreTotal;
  } else {
    _kataScoreTotal++;
    if (isCorrect) _kataScoreCorrect++;
    document.getElementById('kana-score-display').textContent = 'SCORE: ' + _kataScoreCorrect + ' / ' + _kataScoreTotal;
  }"""
    content = content.replace(old_score_update, new_score_update)
    
    old_toggle_kana = """  if (type === 'hiragana') {
    document.getElementById('btn-kana-hira').classList.add('active');
    if (titleEl) titleEl.innerText = 'HIRAGANA SOUND RECALL GAME';
  } else {
    document.getElementById('btn-kana-kata').classList.add('active');
    if (titleEl) titleEl.innerText = 'KATAKANA SOUND RECALL GAME';
  }"""
    
    new_toggle_kana = """  if (type === 'hiragana') {
    document.getElementById('btn-kana-hira').classList.add('active');
    if (titleEl) titleEl.innerText = 'HIRAGANA SOUND RECALL GAME';
    const scoreEl = document.getElementById('kana-score-display');
    if (scoreEl) scoreEl.textContent = 'SCORE: ' + _hiraScoreCorrect + ' / ' + _hiraScoreTotal;
  } else {
    document.getElementById('btn-kana-kata').classList.add('active');
    if (titleEl) titleEl.innerText = 'KATAKANA SOUND RECALL GAME';
    const scoreEl = document.getElementById('kana-score-display');
    if (scoreEl) scoreEl.textContent = 'SCORE: ' + _kataScoreCorrect + ' / ' + _kataScoreTotal;
  }"""
    content = content.replace(old_toggle_kana, new_toggle_kana)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(content)

apply_fixes()
