with open('education.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx = html.find('jlpt-header-title')
print(html[max(0, idx-300):idx+800])
