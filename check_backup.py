with open('education_backup.html', 'r', encoding='utf-8') as f:
    html = f.read()

print('jp-levels-section in backup:', 'jp-levels-section' in html)
print('jp-dict-section in backup:', 'jp-dict-section' in html)
