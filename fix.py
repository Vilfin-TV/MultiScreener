with open('jlpt_textbook_data.js', 'r', encoding='utf-8') as f:
    js = f.read()

if js.endswith(r';\n'):
    js = js[:-2] + ';\n'
    
with open('jlpt_textbook_data.js', 'w', encoding='utf-8') as f:
    f.write(js)
    
print("Fixed end of file!")
