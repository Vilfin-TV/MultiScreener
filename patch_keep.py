with open('scripts/auto_fetch_images.js', 'r', encoding='utf-8') as f:
    html = f.read()

# Add fs.writeFileSync to create the actual file, not just the directory
old_code = "ensureDirectoryExists(path.resolve(__dirname, '../images/.keep'));"
new_code = """ensureDirectoryExists(path.resolve(__dirname, '../images/.keep'));
    fs.writeFileSync(path.resolve(__dirname, '../images/.keep'), '');"""
html = html.replace(old_code, new_code)

with open('scripts/auto_fetch_images.js', 'w', encoding='utf-8') as f:
    f.write(html)
