with open('education_backup.html', 'r', encoding='utf-8') as f:
    html = f.read()
print('jp-dict-section:', html.find('id="jp-dict-section"'))
print('<!-- Dictionary -->:', html.find('<!-- Dictionary -->'))
print('jp-levels-section:', html.find('id="jp-levels-section"'))
