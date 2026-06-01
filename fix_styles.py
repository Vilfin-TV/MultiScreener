with open('education.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix Translator Text Area height
css_input = """.trans-input {
  width: 100%;
  height: 120px;"""
css_input_fixed = """.trans-input {
  width: 100%;
  height: 280px;"""

css_output = """.trans-output {
  width: 100%;
  height: 120px;"""
css_output_fixed = """.trans-output {
  width: 100%;
  height: 280px;"""

html = html.replace(css_input, css_input_fixed)
html = html.replace(css_output, css_output_fixed)

# Fix Next button escaping
bad_next = r"onclick=""nextLessonPage(\\\'' + _activeLessonTab + '\\\')"""
good_next = r"onclick=""nextLessonPage(\'' + _activeLessonTab + '\')"""

html = html.replace(bad_next, good_next)

with open('education.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed!')
