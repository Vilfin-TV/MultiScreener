with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()
idx = html.find('<iframe')
with open('out.txt', 'w', encoding='utf-8') as f:
    f.write(html[max(0, idx-300):idx+800])
