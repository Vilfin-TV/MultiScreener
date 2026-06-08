import re

with open('education.html', 'r', encoding='utf-8') as f:
    html = f.read()

bad_str = r"""}, {id:'RkQ7pE9A13I', title:'Daily Casual Japanese'}, {id:'tE1cE3xO_o4', title:'Kanji Memory Tricks'}];
  _currentKanjiVideoIdx--;
  if (_currentKanjiVideoIdx < 0) _currentKanjiVideoIdx = kanjiVideos.length - 1;
  const iframe = document.getElementById('kanji-video-iframe');
  if (iframe) iframe.src = 'https://www.youtube.com/embed/' + kanjiVideos[_currentKanjiVideoIdx].id + '?rel=0&controls=1';
}"""

html = html.replace(bad_str, "")

with open('education.html', 'w', encoding='utf-8') as f:
    f.write(html)
