import re

with open('education.html', 'r', encoding='utf-8') as f:
    html = f.read()

academy_idx = html.find('id="academy-video-iframe"')
print("Academy:\n", html[academy_idx-100:academy_idx+500])

kanji_idx = html.find('id="kanji-video-iframe"')
print("\nKanji:\n", html[kanji_idx-100:kanji_idx+500])
