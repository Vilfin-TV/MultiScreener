# -*- coding: utf-8 -*-
"""Interleave the 3 per-page illustrations into each Kids story's `kids` level
body in story.html (replace the single cover image; add one illustration before
each of the 3 paragraphs). Skips Pip (already paginated)."""
import re

R2 = 'https://screener-proxy.vilfintv.workers.dev/r2/media/'
SKIP = 'pip-and-the-little-lost-star'
PAGED = {
 'luna-and-the-star-garden','the-dragon-who-forgot-how-to-fly','captain-coral-and-the-clean-sea',
 'the-clever-monkey-and-the-two-cats','the-thirsty-crow-s-smart-idea','the-cap-seller-and-the-copycat-monkeys',
 'the-lazy-donkey-s-wet-trick','the-hare-and-the-steady-tortoise'}

def slugify(t):
    t = re.split(r'—| - ', t)[0]
    t = re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')
    return t[:40]

def img_line(slug, n, title):
    r2 = f'{R2}stories/kids/{slug}/page{n}.svg'
    loc = f'stories/kids/{slug}/page{n}.svg'
    alt = f'{title} — illustration {n}'
    alt = alt.replace('"', '')
    return ("          '<div class=\"story-visual-media\"><img src=\"" + r2 +
            "\" onerror=\"this.onerror=null;this.src=\\'" + loc + "\\'\" alt=\"" + alt +
            "\" class=\"story-visual-img\" loading=\"lazy\"/></div>',")

lines = open('story.html', encoding='utf-8').read().split('\n')
out = []
in_kids_genre = False
slug = None
title = None
in_kids_level = False
cover_done = False
para_n = 0
changed = 0

for ln in lines:
    if re.match(r'STORY_DATA\.kids\s*=\s*\[', ln):
        in_kids_genre = True; out.append(ln); continue
    if in_kids_genre and re.match(r'^\];?\s*$', ln):
        in_kids_genre = False; in_kids_level = False; out.append(ln); continue

    if in_kids_genre:
        hm = re.match(r"^    headline:\s*['\"](.+?)['\"]\s*,?\s*$", ln)
        if hm:
            title = hm.group(1); slug = slugify(title)
            in_kids_level = False
            out.append(ln); continue
        if re.match(r"^      kids:\s*\{", ln):
            in_kids_level = (slug in PAGED and slug != SKIP)
            cover_done = False; para_n = 0
            out.append(ln); continue
        if re.match(r"^      (general|expert):\s*\{", ln):
            in_kids_level = False
            out.append(ln); continue

        if in_kids_level:
            # replace the single cover image with page1
            if not cover_done and 'story-visual-media' in ln:
                out.append(img_line(slug, 1, title)); cover_done = True; changed += 1; continue
            # insert page2/page3 before the 2nd/3rd paragraph
            if re.match(r"^\s*'<p", ln):
                para_n += 1
                if para_n == 2:
                    out.append(img_line(slug, 2, title)); changed += 1
                elif para_n == 3:
                    out.append(img_line(slug, 3, title)); changed += 1
                out.append(ln); continue
    out.append(ln)

open('story.html', 'w', encoding='utf-8').write('\n'.join(out))
print('image lines inserted/replaced:', changed, '(expect 24 = 8 stories x 3)')
