import re

def run_fix():
    with open('education.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Video Player Controls
    # We will search for the iframe and wrap it with controls.
    old_video_html = r"""      <!-- Academy YouTube Panel -->
      <div class="kana-game-box" style="margin-top:20px; padding:0; overflow:hidden; border:1px solid var(--border2);">
        <div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border2); margin-bottom:0;">
          <span id="academy-video-header">LANGUAGE ACADEMY VIDEOS</span>
        </div>
        <iframe id="academy-video-iframe" 
                style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;" 
                allow="autoplay; encrypted-media; picture-in-picture" 
                allowfullscreen></iframe>
        <div id="academy-video-list" style="max-height:240px; overflow-y:auto; background:var(--card); scrollbar-width:thin;">
          <!-- Dynamically populated by JS -->
        </div>
      </div>"""

    new_video_html = """      <!-- Academy YouTube Panel -->
      <div class="kana-game-box" style="margin-top:20px; padding:0; overflow:hidden; border:1px solid var(--border2);">
        <div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border2); margin-bottom:0;">
          <span id="academy-video-header">LANGUAGE ACADEMY VIDEOS</span>
        </div>
        <div class="video-playlist-container">
          <div id="youtube-player-wrapper" style="position:relative; width:100%; aspect-ratio:16/9; background:#000;">
             <div id="academy-video-iframe"></div>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center; padding:10px; background:var(--card2); border-bottom:1px solid var(--border2);">
            <div style="display:flex; gap:10px; align-items:center;">
              <button onclick="playPrevVideo()" class="widget-btn" style="padding:6px 12px; font-size:12px;">&#9664; Back</button>
              <button onclick="playNextVideo()" class="widget-btn" style="padding:6px 12px; font-size:12px;">Next &#9654;</button>
            </div>
            <div style="display:flex; gap:10px; align-items:center;">
              <button onclick="toggleVideoMute()" id="video-mute-btn" class="widget-btn" style="padding:6px 12px; font-size:12px;">Mute</button>
              <input type="range" id="video-volume" min="0" max="100" value="100" style="width:80px;" onchange="setVideoVolume(this.value)">
            </div>
          </div>
          <div id="academy-video-list" style="max-height:240px; overflow-y:auto; background:var(--card); scrollbar-width:thin;">
            <!-- Dynamically populated by JS -->
          </div>
        </div>
      </div>"""
    
    html = html.replace(old_video_html, new_video_html)

    # 2. Add Youtube API Logic
    youtube_script = """// ACADEMY VIDEO INTEGRATION
var _academyVideos = [
  {id: 'pD1X2a-MvL8', title: 'Japanese Alphabet Hiragana (Part 1)'},
  {id: 'R7Ww4d0v8_Y', title: 'Japanese Alphabet Hiragana (Part 2)'},
  {id: 'Zk3UjQyTfVw', title: 'Japanese Alphabet Katakana'},
  {id: 'r_DMBvPj9Wc', title: 'Japanese Greetings & Basics'},
  {id: 's_R0m4gH58k', title: 'Self Introduction in Japanese'}
];
var _currentVideoIndex = 0;
var player;

// Load YouTube IFrame API
var tag = document.createElement('script');
tag.src = "https://www.youtube.com/iframe_api";
var firstScriptTag = document.getElementsByTagName('script')[0];
firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

function onYouTubeIframeAPIReady() {
  player = new YT.Player('academy-video-iframe', {
    height: '100%',
    width: '100%',
    videoId: _academyVideos[0].id,
    playerVars: {
      'playsinline': 1,
      'autoplay': 0, // NO AUTOPLAY ON START
      'rel': 0
    },
    events: {
      'onReady': onPlayerReady,
      'onStateChange': onPlayerStateChange
    }
  });
}

function onPlayerReady(event) {
  // player is ready
}

function onPlayerStateChange(event) {
  if (event.data == YT.PlayerState.ENDED) {
    playNextVideo();
  }
}

function renderAcademyVideos() {
  var listHtml = '';
  _academyVideos.forEach(function(v, idx) {
    var bg = (idx === _currentVideoIndex) ? 'var(--card3)' : 'transparent';
    var color = (idx === _currentVideoIndex) ? 'var(--gold2)' : 'var(--text2)';
    listHtml += '<div style="padding:10px 16px; border-bottom:1px solid var(--border2); cursor:pointer; background:' + bg + '; color:' + color + ';" onclick="selectAcademyVideo(' + idx + ')">';
    listHtml += '▶ ' + esc(v.title);
    listHtml += '</div>';
  });
  document.getElementById('academy-video-list').innerHTML = listHtml;
}

function selectAcademyVideo(idx) {
  _currentVideoIndex = idx;
  if(player && player.loadVideoById) {
      player.loadVideoById(_academyVideos[idx].id);
  }
  renderAcademyVideos();
}

function playNextVideo() {
  if (_currentVideoIndex < _academyVideos.length - 1) {
    selectAcademyVideo(_currentVideoIndex + 1);
  } else {
    selectAcademyVideo(0); // loop back
  }
}

function playPrevVideo() {
  if (_currentVideoIndex > 0) {
    selectAcademyVideo(_currentVideoIndex - 1);
  } else {
    selectAcademyVideo(_academyVideos.length - 1);
  }
}

function toggleVideoMute() {
  if(!player) return;
  if (player.isMuted()) {
    player.unMute();
    document.getElementById('video-mute-btn').innerText = 'Mute';
  } else {
    player.mute();
    document.getElementById('video-mute-btn').innerText = 'Unmute';
  }
}

function setVideoVolume(val) {
  if(player) {
    player.setVolume(val);
    if(val > 0 && player.isMuted()) {
       player.unMute();
       document.getElementById('video-mute-btn').innerText = 'Mute';
    }
  }
}

// Ensure rendering on load
window.addEventListener('load', function() {
  renderAcademyVideos();
});

// ---"""
    
    old_video_script = r"""// ACADEMY VIDEO INTEGRATION
var _academyVideos = [
  {id: 'pD1X2a-MvL8', title: 'Japanese Alphabet Hiragana (Part 1)'},
  {id: 'R7Ww4d0v8_Y', title: 'Japanese Alphabet Hiragana (Part 2)'},
  {id: 'Zk3UjQyTfVw', title: 'Japanese Alphabet Katakana'},
  {id: 'r_DMBvPj9Wc', title: 'Japanese Greetings & Basics'},
  {id: 's_R0m4gH58k', title: 'Self Introduction in Japanese'}
];
function renderAcademyVideos() {
  var list = document.getElementById('academy-video-list');
  if(!list) return;
  var html = '';
  _academyVideos.forEach(function(v, idx) {
    html += '<div style="padding:10px 16px; border-bottom:1px solid var(--border); cursor:pointer; color:var(--text2);" onclick="playAcademyVideo(\\'' + v.id + '\\')">';
    html += '▶ ' + esc(v.title);
    html += '</div>';
  });
  list.innerHTML = html;
  if (_academyVideos.length > 0) {
    playAcademyVideo(_academyVideos[0].id);
  }
}
function playAcademyVideo(vidId) {
  var ifm = document.getElementById('academy-video-iframe');
  if(ifm) {
    ifm.src = 'https://www.youtube.com/embed/' + vidId + '?autoplay=1&rel=0';
  }
}
// ---"""

    # Replace the JS logic
    html = html.replace(old_video_script, youtube_script)


    # 3. SPLIT KANA GAMES
    # Find the HTML
    old_kana_game_html = """      <!-- Recall Game -->
      <div class="kana-game-box">
        <div class="kana-score-row">
          <span>KANA SOUND RECALL GAME</span>
          <span id="kana-score-display">SCORE: 0 / 0</span>
        </div>
        <div class="kana-game-char" id="kana-game-question">あ</div>
        <p class="study-lead" style="font-size:16px; margin-bottom:8px; text-align:center;">Identify the correct romaji syllable sound:</p>
        <div class="jlpt-options" id="kana-game-options" style="margin-bottom:0;">
        </div>
      </div>"""

    new_kana_game_html = """      <!-- Hiragana Recall Game -->
      <div class="kana-game-box" id="hiragana-game-container">
        <div class="kana-score-row">
          <span>HIRAGANA SOUND RECALL GAME</span>
          <span id="hira-score-display">SCORE: 0 / 0</span>
        </div>
        <div class="kana-game-char" id="hira-game-question">あ</div>
        <p class="study-lead" style="font-size:16px; margin-bottom:8px; text-align:center;">Identify the correct romaji syllable sound:</p>
        <div class="jlpt-options" id="hira-game-options" style="margin-bottom:0;">
        </div>
      </div>
      
      <!-- Katakana Recall Game -->
      <div class="kana-game-box" id="katakana-game-container" style="display:none;">
        <div class="kana-score-row">
          <span>KATAKANA SOUND RECALL GAME</span>
          <span id="kata-score-display">SCORE: 0 / 0</span>
        </div>
        <div class="kana-game-char" id="kata-game-question">ア</div>
        <p class="study-lead" style="font-size:16px; margin-bottom:8px; text-align:center;">Identify the correct romaji syllable sound:</p>
        <div class="jlpt-options" id="kata-game-options" style="margin-bottom:0;">
        </div>
      </div>"""

    html = html.replace(old_kana_game_html, new_kana_game_html)

    # 4. JS for Game
    # The current js has '// Kana Game State'
    old_game_state_js = """// Kana Game State
var _kanaQ = null;
var _kanaScore = 0;
var _kanaTotal = 0;

function renderKanaGame() {
  if (!KANA_DATA || KANA_DATA.length === 0) return;
  // pick a random char
  var rIdx = Math.floor(Math.random() * KANA_DATA.length);
  _kanaQ = KANA_DATA[rIdx];
  
  // Decide if we show Hiragana or Katakana randomly
  var isHira = Math.random() < 0.5;
  var dispChar = isHira ? _kanaQ.hiragana : _kanaQ.katakana;
  if (!dispChar) dispChar = _kanaQ.hiragana;
  
  document.getElementById('kana-game-question').innerText = dispChar;
  
  // Generate 4 options
  var opts = [_kanaQ.romaji];
  while(opts.length < 4) {
    var cIdx = Math.floor(Math.random() * KANA_DATA.length);
    var cand = KANA_DATA[cIdx].romaji;
    if (opts.indexOf(cand) === -1) opts.push(cand);
  }
  opts.sort(function() { return Math.random() - 0.5; });
  
  var html = '';
  opts.forEach(function(o) {
    html += '<button class="widget-btn" style="padding:12px; font-size:16px;" onclick="checkKanaAnswer(\\'' + esc(o) + '\\')">' + esc(o.toUpperCase()) + '</button>';
  });
  document.getElementById('kana-game-options').innerHTML = html;
  
  document.getElementById('kana-score-display').innerText = 'SCORE: ' + _kanaScore + ' / ' + _kanaTotal;
}

function checkKanaAnswer(ans) {
  _kanaTotal++;
  if (ans === _kanaQ.romaji) {
    _kanaScore++;
    // Correct! Wait, visual feedback is better.
    // ...
  }
  renderKanaGame();
}"""

    new_game_state_js = """// Hiragana Game State
var _hiraQ = null;
var _hiraScore = 0;
var _hiraTotal = 0;

function renderHiraGame() {
  if (!KANA_DATA || KANA_DATA.length === 0) return;
  var KANA_ONLY = KANA_DATA.filter(k => k.hiragana);
  var rIdx = Math.floor(Math.random() * KANA_ONLY.length);
  _hiraQ = KANA_ONLY[rIdx];
  
  document.getElementById('hira-game-question').innerText = _hiraQ.hiragana;
  
  var opts = [_hiraQ.romaji];
  while(opts.length < 4) {
    var cIdx = Math.floor(Math.random() * KANA_ONLY.length);
    var cand = KANA_ONLY[cIdx].romaji;
    if (opts.indexOf(cand) === -1) opts.push(cand);
  }
  opts.sort(function() { return Math.random() - 0.5; });
  
  var html = '';
  opts.forEach(function(o) {
    html += '<button class="widget-btn" style="padding:12px; font-size:16px;" onclick="checkHiraAnswer(\\'' + esc(o) + '\\')">' + esc(o.toUpperCase()) + '</button>';
  });
  document.getElementById('hira-game-options').innerHTML = html;
  document.getElementById('hira-score-display').innerText = 'SCORE: ' + _hiraScore + ' / ' + _hiraTotal;
}

function checkHiraAnswer(ans) {
  _hiraTotal++;
  if (ans === _hiraQ.romaji) { _hiraScore++; }
  renderHiraGame();
}

// Katakana Game State
var _kataQ = null;
var _kataScore = 0;
var _kataTotal = 0;

function renderKataGame() {
  if (!KANA_DATA || KANA_DATA.length === 0) return;
  var KANA_ONLY = KANA_DATA.filter(k => k.katakana);
  var rIdx = Math.floor(Math.random() * KANA_ONLY.length);
  _kataQ = KANA_ONLY[rIdx];
  
  document.getElementById('kata-game-question').innerText = _kataQ.katakana;
  
  var opts = [_kataQ.romaji];
  while(opts.length < 4) {
    var cIdx = Math.floor(Math.random() * KANA_ONLY.length);
    var cand = KANA_ONLY[cIdx].romaji;
    if (opts.indexOf(cand) === -1) opts.push(cand);
  }
  opts.sort(function() { return Math.random() - 0.5; });
  
  var html = '';
  opts.forEach(function(o) {
    html += '<button class="widget-btn" style="padding:12px; font-size:16px;" onclick="checkKataAnswer(\\'' + esc(o) + '\\')">' + esc(o.toUpperCase()) + '</button>';
  });
  document.getElementById('kata-game-options').innerHTML = html;
  document.getElementById('kata-score-display').innerText = 'SCORE: ' + _kataScore + ' / ' + _kataTotal;
}

function checkKataAnswer(ans) {
  _kataTotal++;
  if (ans === _kataQ.romaji) { _kataScore++; }
  renderKataGame();
}

// Modify toggleKanaType to switch games
const oldToggleKana = toggleKanaType;
toggleKanaType = function(type) {
    _activeKanaType = type;
    document.getElementById('btn-kana-hira').classList.remove('active');
    document.getElementById('btn-kana-kata').classList.remove('active');
    if (type === 'hiragana') {
        document.getElementById('btn-kana-hira').classList.add('active');
        document.getElementById('hiragana-game-container').style.display = 'block';
        document.getElementById('katakana-game-container').style.display = 'none';
        renderHiraGame();
    } else {
        document.getElementById('btn-kana-kata').classList.add('active');
        document.getElementById('hiragana-game-container').style.display = 'none';
        document.getElementById('katakana-game-container').style.display = 'block';
        renderKataGame();
    }
    renderKanaGrid();
};

window.addEventListener('load', function() {
    renderHiraGame();
    renderKataGame();
});
"""

    html = html.replace(old_game_state_js, new_game_state_js)

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(html)

run_fix()
