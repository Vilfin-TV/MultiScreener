# -*- coding: utf-8 -*-
"""Wire generated covers into story.html:
  A. insert top-level mediaUrl (cover) after every story headline
  B. replace inline Unsplash <img src> with the story's cover (+ local onerror)
  C. enhance the auto-prepend template with a local onerror fallback
  D. make the hero card use the story's mediaUrl
  E. blanket-replace any remaining Unsplash URL with the default cover
"""
import re

R2 = 'https://screener-proxy.vilfintv.workers.dev/r2/media/'
DEFAULT = R2 + 'stories/_default.svg'

def slugify(t):
    t = re.split(r'—| - ', t)[0]
    t = re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')
    return t[:40]

src = open('story.html', encoding='utf-8').read()
lines = src.split('\n')
out = []
genre = None
in_data = False
inserted = 0
replaced_inline = 0

def cover_for(genre, title):
    if title.startswith('Pip and the Little Lost Star'):
        return R2 + 'kids/pip-star/header.svg', 'kids/pip-star/header.svg'
    slug = slugify(title)
    return R2 + f'stories/{genre}/{slug}.svg', f'stories/{genre}/{slug}.svg'

cur_cover = None
cur_local = None
has_media = False
for ln in lines:
    m = re.match(r'STORY_DATA\.(\w+)\s*=\s*\[', ln)
    if m:
        genre = m.group(1); in_data = True; out.append(ln); continue
    if in_data and re.match(r'^\];?\s*$', ln):
        in_data = False; genre = None; out.append(ln); continue

    if in_data:
        hm = re.match(r"^    headline:\s*['\"](.+?)['\"]\s*,?\s*$", ln)
        if hm:
            title = hm.group(1)
            cur_cover, cur_local = cover_for(genre, title)
            has_media = False
            out.append(ln)
            continue
        # replace an existing top-level mediaUrl with the cover
        if re.match(r"^    mediaUrl:\s*", ln) and cur_cover and not has_media:
            out.append(f"    mediaUrl: '{cur_cover}',")
            has_media = True; inserted += 1; continue
        # otherwise insert mediaUrl just before the levels block
        if re.match(r"^    levels:\s*\{", ln) and cur_cover and not has_media:
            out.append(f"    mediaUrl: '{cur_cover}',")
            has_media = True; inserted += 1
            out.append(ln); continue
        # inline unsplash replacement (uses current story cover)
        if 'images.unsplash.com' in ln and cur_cover:
            new = re.sub(
                r'src="https://images\.unsplash\.com/[^"]*"',
                'src="' + cur_cover + '" onerror="this.onerror=null;this.src=' + "\\'" + cur_local + "\\'" + '"',
                ln)
            if new != ln:
                replaced_inline += ln.count('images.unsplash.com')
            out.append(new); continue
    out.append(ln)

src = '\n'.join(out)

# C. enhance auto-prepend template
old_tpl = ("var imgHtml = '<div class=\"story-visual-media featured-header-media\">'\n"
           "        + '<img src=\"' + mediaUrl + '\" alt=\"' + escAttr(content.headline) + '\" class=\"story-visual-img featured-header-img\"/>'\n"
           "        + '</div>';")
new_tpl = ("var localFb = (mediaUrl && mediaUrl.indexOf('/r2/media/') > -1) ? mediaUrl.split('/r2/media/')[1] : mediaUrl;\n"
           "      var imgHtml = '<div class=\"story-visual-media featured-header-media\">'\n"
           "        + '<img src=\"' + mediaUrl + '\" data-local=\"' + localFb + '\" alt=\"' + escAttr(content.headline) + '\" class=\"story-visual-img featured-header-img\" onerror=\"this.onerror=null;if(this.dataset.local)this.src=this.dataset.local\"/>'\n"
           "        + '</div>';")
if old_tpl in src:
    src = src.replace(old_tpl, new_tpl); print('C: prepend template enhanced')
else:
    print('C: WARN template not found (manual check needed)')

# D. hero card uses story mediaUrl
old_hero = "+ '<img src=\"' + defaultHeroBg + '\" class=\"story-hero-img\" alt=\"Featured Background\"/>'"
new_hero = ("+ '<img src=\"' + (heroContent.mediaUrl || hero.mediaUrl || defaultHeroBg) + '\" "
            "data-local=\"' + ((heroContent.mediaUrl || hero.mediaUrl || defaultHeroBg).split('/r2/media/')[1] || '') + '\" "
            "class=\"story-hero-img\" alt=\"Featured Background\" "
            "onerror=\"this.onerror=null;if(this.dataset.local)this.src=this.dataset.local\"/>'")
if old_hero in src:
    src = src.replace(old_hero, new_hero); print('D: hero img source updated')
else:
    print('D: WARN hero img not found')

# E. blanket replace any remaining unsplash URL with default cover
remaining = len(re.findall(r'https://images\.unsplash\.com/[^"\'\s]*', src))
src = re.sub(r'https://images\.unsplash\.com/[^"\'\s]*', DEFAULT, src)
print('E: replaced', remaining, 'remaining unsplash URLs with default cover')

open('story.html', 'w', encoding='utf-8').write(src)
print('mediaUrl inserted:', inserted, '| inline unsplash replaced:', replaced_inline)
print('unsplash left:', src.count('images.unsplash.com'))
