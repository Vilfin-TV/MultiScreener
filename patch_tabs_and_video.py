import re

def main():
    with open('education.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # --- 1. Fix switchJpSubHub ---
    # We will find the function and replace it entirely
    old_switch_func = r'''function switchJpSubHub\(area\) \{
  if \(typeof stopConversation === 'function'\) stopConversation\(\);
  if \(typeof stopDictPage === 'function'\) stopDictPage\(\);
  _activeJpSubHub = area;
  document\.getElementById\('sub-hub-chart'\)\.classList\.remove\('active'\);
  document\.getElementById\('sub-hub-kanji'\)\.classList\.remove\('active'\);
  document\.getElementById\('sub-hub-levels'\)\.classList\.remove\('active'\);
  document\.getElementById\('sub-hub-dict'\)\.classList\.remove\('active'\);
  
  document\.getElementById\('jp-kana-section'\)\.style\.display = 'none';
  document\.getElementById\('jp-kanji-casual-section'\)\.style\.display = 'none';
  document\.getElementById\('jp-levels-section'\)\.style\.display = 'none';
  document\.getElementById\('jp-dict-section'\)\.style\.display = 'none';
  
  if \(area === 'chart'\) \{
    document\.getElementById\('sub-hub-chart'\)\.classList\.add\('active'\);
    document\.getElementById\('jp-kana-section'\)\.style\.display = 'grid';
    renderKanaChart\(\);
  \}
\}'''

    new_switch_func = '''function switchJpSubHub(area) {
  if (typeof stopConversation === 'function') stopConversation();
  if (typeof stopDictPage === 'function') stopDictPage();
  _activeJpSubHub = area;
  document.getElementById('sub-hub-chart').classList.remove('active');
  document.getElementById('sub-hub-kanji').classList.remove('active');
  document.getElementById('sub-hub-levels').classList.remove('active');
  document.getElementById('sub-hub-dict').classList.remove('active');
  
  document.getElementById('jp-kana-section').style.display = 'none';
  document.getElementById('jp-kanji-casual-section').style.display = 'none';
  document.getElementById('jp-levels-section').style.display = 'none';
  document.getElementById('jp-dict-section').style.display = 'none';
  
  if (area === 'chart') {
    document.getElementById('sub-hub-chart').classList.add('active');
    document.getElementById('jp-kana-section').style.display = 'grid';
    renderKanaChart();
  } else if (area === 'kanji') {
    document.getElementById('sub-hub-kanji').classList.add('active');
    document.getElementById('jp-kanji-casual-section').style.display = 'grid';
    renderKanjiHub();
  } else if (area === 'levels') {
    document.getElementById('sub-hub-levels').classList.add('active');
    document.getElementById('jp-levels-section').style.display = 'block';
    renderJlptContent();
  } else if (area === 'dict') {
    document.getElementById('sub-hub-dict').classList.add('active');
    document.getElementById('jp-dict-section').style.display = 'block';
    renderDictionary();
  }
}'''

    html = re.sub(old_switch_func, new_switch_func, html)

    # --- 2. Replace the Kana Video Player UI ---
    # The current one:
    kana_video_ui = r'''<div id="academy-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:8px 16px; background:var\(--card2\); border-top:1px solid var\(--border2\); border-bottom-left-radius:8px; border-bottom-right-radius:8px;">
                <button onclick="playPrevVideo\(\)" style="background:none; border:1px solid var\(--border\); padding:6px 12px; color:var\(--text2\); border-radius:4px; cursor:pointer;">&#9664; Back</button>
                <div style="color:var\(--text3\); font-size:12px;">Controls & Volume are inside video</div>
                <button onclick="playNextVideo\(\)" style="background:none; border:1px solid var\(--border\); padding:6px 12px; color:var\(--text2\); border-radius:4px; cursor:pointer;">Next &#9654;</button>
              </div>'''

    sleek_video_ui_kana = '''<div id="academy-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:10px 16px; background:#0a192f; border-top:1px solid rgba(255,255,255,0.1); border-bottom-left-radius:12px; border-bottom-right-radius:12px; box-shadow:inset 0 1px 0 rgba(255,255,255,0.05);">
                <div style="display:flex; gap:12px; align-items:center;">
                  <button title="Previous Video" onclick="playPrevVideo()" style="background:#112240; border:1px solid rgba(255,255,255,0.1); padding:8px; color:#ccd6f6; border-radius:6px; cursor:pointer; display:flex; align-items:center; transition:0.2s;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
                  </button>
                  <button title="Next Video" onclick="playNextVideo()" style="background:#112240; border:1px solid rgba(255,255,255,0.1); padding:8px; color:#ccd6f6; border-radius:6px; cursor:pointer; display:flex; align-items:center; transition:0.2s;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                  </button>
                  <button title="Toggle Mute (YouTube API required to sync)" onclick="alert('Mute toggle is native to the video player.')" style="background:transparent; border:none; color:#ccd6f6; cursor:pointer; padding:4px;">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
                  </button>
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                  <button title="Save to Favorites" style="background:transparent; border:none; color:#64ffda; cursor:pointer; padding:4px;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
                  </button>
                </div>
              </div>'''

    html = re.sub(kana_video_ui, sleek_video_ui_kana, html)

    # --- 3. Kanji Video Player UI ---
    # The Kanji video player might not even have controls. Let's find its iframe.
    # We will search for Kanji video section.
    # In `kanji_hub.js` or `education.html`?
    # Wait! Kanji Hub is rendered dynamically by `renderKanjiHub()` in JS!
    # Let's patch `renderKanjiHub()` to inject the exact same controls.
    
    # Let's search for the Kanji iframe string in JS
    kanji_iframe_html = r'''<iframe id="kanji-video-iframe" src="https://www.youtube.com/embed/\${kanjiVideos\[0\]\.id}\?rel=0&controls=1" style="width:100%; height:250px; border:none; border-radius:8px; margin-bottom:12px;"></iframe>'''
    
    new_kanji_video_wrapper = '''<div style="background:#0a192f; border-radius:12px; overflow:hidden; border:1px solid var(--border2); margin-bottom:12px; box-shadow:0 8px 24px rgba(0,0,0,0.3);">
            <iframe id="kanji-video-iframe" src="https://www.youtube.com/embed/${kanjiVideos[0].id}?rel=0&controls=1" style="width:100%; aspect-ratio:16/9; border:none; display:block;"></iframe>
            <div id="kanji-video-controls" style="display:flex; justify-content:space-between; align-items:center; padding:10px 16px; background:#0a192f; border-top:1px solid rgba(255,255,255,0.1); box-shadow:inset 0 1px 0 rgba(255,255,255,0.05);">
                <div style="display:flex; gap:12px; align-items:center;">
                  <button title="Previous Video" onclick="playPrevKanjiVideo()" style="background:#112240; border:1px solid rgba(255,255,255,0.1); padding:8px; color:#ccd6f6; border-radius:6px; cursor:pointer; display:flex; align-items:center; transition:0.2s;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
                  </button>
                  <button title="Next Video" onclick="playNextKanjiVideo()" style="background:#112240; border:1px solid rgba(255,255,255,0.1); padding:8px; color:#ccd6f6; border-radius:6px; cursor:pointer; display:flex; align-items:center; transition:0.2s;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                  </button>
                  <button title="Toggle Mute (YouTube API required to sync)" onclick="alert('Mute toggle is native to the video player.')" style="background:transparent; border:none; color:#ccd6f6; cursor:pointer; padding:4px;">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
                  </button>
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                  <button title="Save to Favorites" style="background:transparent; border:none; color:#64ffda; cursor:pointer; padding:4px;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
                  </button>
                </div>
            </div>
          </div>'''
    html = re.sub(kanji_iframe_html, new_kanji_video_wrapper, html)
    
    # Let's add the JS functions for Kanji video next/prev
    js_funcs = '''
let _currentKanjiVideoIdx = 0;
function playNextKanjiVideo() {
  const kanjiVideos = [{id:'nO1N02B7HKE', title:'Kanji Mastery Ep 1'}, {id:'RkQ7pE9A13I', title:'Daily Casual Japanese'}, {id:'tE1cE3xO_o4', title:'Kanji Memory Tricks'}];
  _currentKanjiVideoIdx++;
  if (_currentKanjiVideoIdx >= kanjiVideos.length) _currentKanjiVideoIdx = 0;
  const iframe = document.getElementById('kanji-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + kanjiVideos[_currentKanjiVideoIdx].id + '?rel=0&controls=1';
}
function playPrevKanjiVideo() {
  const kanjiVideos = [{id:'nO1N02B7HKE', title:'Kanji Mastery Ep 1'}, {id:'RkQ7pE9A13I', title:'Daily Casual Japanese'}, {id:'tE1cE3xO_o4', title:'Kanji Memory Tricks'}];
  _currentKanjiVideoIdx--;
  if (_currentKanjiVideoIdx < 0) _currentKanjiVideoIdx = kanjiVideos.length - 1;
  const iframe = document.getElementById('kanji-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + kanjiVideos[_currentKanjiVideoIdx].id + '?rel=0&controls=1';
}
'''
    html = html.replace('// --- TRANSLATOR LOGIC ---', js_funcs + '\n// --- TRANSLATOR LOGIC ---')

    with open('education.html', 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":
    main()
