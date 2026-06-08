with open('education_today_broken.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx1 = html.find('id="jp-levels-section"')
idx2 = html.find('id="jp-dict-section"')

if idx1 != -1 and idx2 != -1:
    print(html[idx1:idx2])
else:
    print(f"idx1: {idx1}, idx2: {idx2}")
