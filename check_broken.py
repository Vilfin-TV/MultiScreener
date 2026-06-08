import re
with open('education_today_broken.html', 'r', encoding='utf-8') as f:
    html = f.read()
print('levels count:', len(re.findall(r'id="jp-levels-section"', html)))
print('footer count:', len(re.findall(r'<footer', html)))
