with open('education_today_broken.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx = html.find('id="academy-video-controls"')
print(html[idx-300:idx+800])
