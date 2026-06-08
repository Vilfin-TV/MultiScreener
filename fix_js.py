with open('education.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the duplicate CF_R2_URL
content = content.replace("const CF_R2_URL = 'https://pub-yourbucket.r2.dev';", "")

with open('education.html', 'w', encoding='utf-8') as f:
    f.write(content)
