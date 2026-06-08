import re

with open('education.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. ACADEMY VIDEO (Hiragana/Katakana)
# We find the kana-score-row for the video header and replace it until the end of academy-video-list
academy_start = html.find('<div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border); margin-bottom:0;">')
academy_iframe_idx = html.find('id="academy-video-iframe"')

if academy_start != -1 and academy_start < academy_iframe_idx:
    # Find the end of academy-video-list
    list_idx = html.find('id="academy-video-list"', academy_iframe_idx)
    # The div for academy-video-list closes right after
    list_close = html.find('</div>', list_idx) + 6
    
    old_academy_block = html[academy_start:list_close]
    
    new_academy_block = '''<div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border); margin-bottom:0; background:var(--card);">
                <span id="academy-video-header" style="font-weight:bold; color:var(--text); text-transform:uppercase; font-size:12px;">LANGUAGE ACADEMY VIDEOS</span>
              </div>
              <iframe id="academy-video-iframe" src="https://www.youtube.com/embed/s8ZtdgZ7Pms?rel=0&controls=1"
                      style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;" 
                      allow="encrypted-media; picture-in-picture" 
                      allowfullscreen></iframe>
              <div id="academy-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:var(--card); border-bottom:1px solid var(--border);">
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg); cursor:pointer;" onclick="playPrevAcademyVideo()">&#9664; Back</button>
                <div style="font-size:12px; color:var(--text3);">Controls & Volume are inside video</div>
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg); cursor:pointer;" onclick="playNextAcademyVideo()">Next &#9654;</button>
              </div>
              <div id="academy-video-title" style="padding:12px 16px; background:var(--bg); color:var(--text2); font-size:14px; font-weight:500; border-bottom-left-radius:8px; border-bottom-right-radius:8px; text-align:center;">
                Katakana Lesson
              </div>'''
              
    html = html.replace(old_academy_block, new_academy_block)

# 2. KANJI VIDEO
kanji_iframe_idx = html.find('<iframe id="kanji-video-iframe"')
if kanji_iframe_idx != -1:
    iframe_close = html.find('</iframe>', kanji_iframe_idx) + 9
    old_kanji_iframe = html[kanji_iframe_idx:iframe_close]
    
    new_kanji_video = '''<div style="border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px;">
              <div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border); margin-bottom:0; background:var(--card);">
                <span id="kanji-video-header" style="font-weight:bold; color:var(--text); text-transform:uppercase; font-size:12px;">LANGUAGE ACADEMY VIDEOS</span>
              </div>
              <iframe id="kanji-video-iframe" src="https://www.youtube.com/embed/nO1N02B7HKE?rel=0&controls=1" style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;"></iframe>
              <div id="kanji-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:var(--card); border-bottom:1px solid var(--border);">
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg); cursor:pointer;" onclick="playPrevKanjiVideo()">&#9664; Back</button>
                <div style="font-size:12px; color:var(--text3);">Controls & Volume are inside video</div>
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg); cursor:pointer;" onclick="playNextKanjiVideo()">Next &#9654;</button>
              </div>
              <div id="kanji-video-title" style="padding:12px 16px; background:var(--bg); color:var(--text2); font-size:14px; font-weight:500; text-align:center;">
                Kanji Mastery Ep 1
              </div>
            </div>'''
            
    html = html.replace(old_kanji_iframe, new_kanji_video)

# 3. FIX JAVASCRIPT
js_start = html.find('function playNextKanjiVideo')
if js_start != -1:
    js_end = html.find('// --- TRANSLATOR LOGIC ---')
    if js_end != -1:
        old_js = html[js_start:js_end]
        
        new_js = '''let _currentKanjiVideoIdx = 0;
const kanjiVideos = [{id:'nO1N02B7HKE', title:'Kanji Mastery Ep 1'}, {id:'RkQ7pE9A13I', title:'Daily Casual Japanese'}, {id:'tE1cE3xO_o4', title:'Kanji Memory Tricks'}];
function playNextKanjiVideo() {
  _currentKanjiVideoIdx++;
  if (_currentKanjiVideoIdx >= kanjiVideos.length) _currentKanjiVideoIdx = 0;
  const iframe = document.getElementById('kanji-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + kanjiVideos[_currentKanjiVideoIdx].id + '?rel=0&controls=1';
  const title = document.getElementById('kanji-video-title');
  if (title) title.innerText = kanjiVideos[_currentKanjiVideoIdx].title;
}
function playPrevKanjiVideo() {
  _currentKanjiVideoIdx--;
  if (_currentKanjiVideoIdx < 0) _currentKanjiVideoIdx = kanjiVideos.length - 1;
  const iframe = document.getElementById('kanji-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + kanjiVideos[_currentKanjiVideoIdx].id + '?rel=0&controls=1';
  const title = document.getElementById('kanji-video-title');
  if (title) title.innerText = kanjiVideos[_currentKanjiVideoIdx].title;
}

let _currentAcademyVideoIdx = 0;
const academyVideos = [
  {id:'s8ZtdgZ7Pms', title:'Katakana Lesson'},
  {id:'yA8tEEDR-3M', title:'Hiragana Lesson'},
  {id:'nO1N02B7HKE', title:'Japanese Masterclass'}
];
function playNextAcademyVideo() {
  _currentAcademyVideoIdx++;
  if (_currentAcademyVideoIdx >= academyVideos.length) _currentAcademyVideoIdx = 0;
  const iframe = document.getElementById('academy-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + academyVideos[_currentAcademyVideoIdx].id + '?rel=0&controls=1';
  const title = document.getElementById('academy-video-title');
  if (title) title.innerText = academyVideos[_currentAcademyVideoIdx].title;
}
function playPrevAcademyVideo() {
  _currentAcademyVideoIdx--;
  if (_currentAcademyVideoIdx < 0) _currentAcademyVideoIdx = academyVideos.length - 1;
  const iframe = document.getElementById('academy-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + academyVideos[_currentAcademyVideoIdx].id + '?rel=0&controls=1';
  const title = document.getElementById('academy-video-title');
  if (title) title.innerText = academyVideos[_currentAcademyVideoIdx].title;
}

'''
        html = html.replace(old_js, new_js)

# Also remove renderAcademyVideos and renderAcademyVideoList from window load
html = re.sub(r'window\.fetchAcademyVideos.*?\}\(\)\);', '', html, flags=re.DOTALL)
html = re.sub(r'setTimeout\(window\.fetchAcademyVideos, 500\);', '', html)

with open('education.html', 'w', encoding='utf-8') as f:
    f.write(html)
