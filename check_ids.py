import re

with open('education.html', 'r', encoding='utf-8') as f:
    html = f.read()

ids_to_check = [
    'jp-levels-section',
    'jp-dict-section',
    'jp-kana-section',
    'jp-kanji-casual-section',
    'sub-hub-chart',
    'sub-hub-kanji',
    'sub-hub-levels',
    'sub-hub-dict'
]

for i in ids_to_check:
    print(f"{i} count: {len(re.findall(r'id=\"' + i + r'\"', html))}")
