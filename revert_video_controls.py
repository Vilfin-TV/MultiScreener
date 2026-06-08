import re

with open('education.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. FIX ACADEMY VIDEO (Hiragana/Katakana)
old_academy_block = r'''<div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var\(--border\); margin-bottom:0;">\s*<span id="academy-video-header">LANGUAGE ACADEMY VIDEOS</span>\s*</div>\s*<iframe id="academy-video-iframe"[\s\S]*?allowfullscreen></iframe>\s*<div id="academy-video-controls"[\s\S]*?</div>\s*<div id="academy-video-list"[\s\S]*?</div>'''

new_academy_block = '''<div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border); margin-bottom:0; background:var(--card);">
                <span id="academy-video-header" style="font-weight:bold; color:var(--text); text-transform:uppercase; font-size:12px;">LANGUAGE ACADEMY VIDEOS</span>
              </div>
              <iframe id="academy-video-iframe" 
                      style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;" 
                      allow="encrypted-media; picture-in-picture" 
                      allowfullscreen></iframe>
              <div id="academy-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:var(--card); border-bottom:1px solid var(--border);">
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg);" onclick="playPrevAcademyVideo()">&#9664; Back</button>
                <div style="font-size:12px; color:var(--text3);">Controls & Volume are inside video</div>
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg);" onclick="playNextAcademyVideo()">Next &#9654;</button>
              </div>
              <div id="academy-video-title" style="padding:12px 16px; background:var(--bg); color:var(--text2); font-size:14px; font-weight:500;">
                Katakana Lesson
              </div>'''

html = re.sub(old_academy_block, new_academy_block, html)

# 2. FIX KANJI VIDEO
kanji_iframe_html = r'''<iframe id="kanji-video-iframe" src="https://www.youtube.com/embed/\${kanjiVideos\[0\]\.id}\?rel=0&controls=1" style="width:100%; height:250px; border:none; border-radius:8px; margin-bottom:12px;"></iframe>'''

new_kanji_video_wrapper = '''<div style="border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px;">
              <div class="kana-score-row" style="padding:12px 16px; border-bottom:1px solid var(--border); margin-bottom:0; background:var(--card);">
                <span id="kanji-video-header" style="font-weight:bold; color:var(--text); text-transform:uppercase; font-size:12px;">KANJI ACADEMY VIDEOS</span>
              </div>
              <iframe id="kanji-video-iframe" src="https://www.youtube.com/embed/${kanjiVideos[0].id}?rel=0&controls=1" style="width:100%; aspect-ratio:16/9; border:none; display:block; background:#000;"></iframe>
              <div id="kanji-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:var(--card); border-bottom:1px solid var(--border);">
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg);" onclick="playPrevKanjiVideo()">&#9664; Back</button>
                <div style="font-size:12px; color:var(--text3);">Controls & Volume are inside video</div>
                <button class="option-btn" style="width:auto; padding:6px 12px; font-size:13px; margin:0; border-radius:4px; border:1px solid var(--border); background:var(--bg);" onclick="playNextKanjiVideo()">Next &#9654;</button>
              </div>
              <div id="kanji-video-title" style="padding:12px 16px; background:var(--bg); color:var(--text2); font-size:14px; font-weight:500;">
                ${kanjiVideos[0].title}
              </div>
            </div>'''

html = re.sub(kanji_iframe_html, new_kanji_video_wrapper, html)

# Replace Javascript logic for playPrevKanjiVideo / playNextKanjiVideo to update title too
old_kanji_js = r'''function playNextKanjiVideo\(\).*?\}\s*function playPrevKanjiVideo\(\).*?\}'''
new_kanji_js = '''let _currentKanjiVideoIdx = 0;
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
}'''

html = re.sub(old_kanji_js, new_kanji_js, html, flags=re.DOTALL)

# Add Javascript logic for playPrevAcademyVideo / playNextAcademyVideo since they are missing
academy_js = '''
let _currentAcademyVideoIdx = 0;
const academyVideos = [
  {id:'s8ZtdgZ7Pms', title:'Katakana Lesson (JapanesePod101)'},
  {id:'yA8tEEDR-3M', title:'Hiragana Lesson (JapanesePod101)'},
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

if 'playNextAcademyVideo' not in html:
    html = html.replace('// --- TRANSLATOR LOGIC ---', academy_js + '\n// --- TRANSLATOR LOGIC ---')


with open('education.html', 'w', encoding='utf-8') as f:
    f.write(html)
