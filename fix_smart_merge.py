import re

with open('smart_merge_3.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace("jlpt_start = old_html.find('<div id=\"jp-levels-section\" class=\"kana-layout\"')", "jlpt_start = old_html.find('<div id=\"jp-levels-section\"')")
code = code.replace("dict_start = old_html.find('<div id=\"jp-dict-section\" class=\"kana-layout\"')", "dict_start = old_html.find('<div id=\"jp-dict-section\"')")

with open('smart_merge_3.py', 'w', encoding='utf-8') as f:
    f.write(code)
