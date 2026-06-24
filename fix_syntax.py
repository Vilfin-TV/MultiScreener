import sys

def fix_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the incorrectly escaped quotes inside single-quoted strings
    content = content.replace("\\\\'", "\\'")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
        
fix_file('generate_web_data.js')
fix_file('generate_info_data.js')
print("Fixed both files")
