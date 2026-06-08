import re

with open('education.html', 'r', encoding='utf-8') as f:
    html = f.read()

# We will use regex to find the Kanji player inserted by patch_tabs_and_video.py
# The start is: <div style="background:#0a192f; border-radius:12px; overflow:hidden; border:1px solid var(--border2); margin-bottom:12px; box-shadow:0 8px 24px rgba(0,0,0,0.3);">
# And it ends after a bunch of </div>
pattern = r'<div style="background:#0a192f; border-radius:12px; overflow:hidden; border:1px solid var\(--border2\); margin-bottom:12px; box-shadow:0 8px 24px rgba\(0,0,0,0\.3\);">.*?</div>\s*</div>\s*</div>\s*</div>\s*</div>'

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

html = re.sub(pattern, new_kanji_video, html, flags=re.DOTALL)

with open('education.html', 'w', encoding='utf-8') as f:
    f.write(html)
