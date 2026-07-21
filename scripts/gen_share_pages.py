#!/usr/bin/env python3
"""Generate static per-story preview pages under share/<id>.html.

news.html renders stories client-side from content.json, so link-preview
crawlers (Facebook, X/Twitter, WhatsApp, Telegram, ...) never see a story's
own headline/photo when a news.html?story=<id> link is pasted - they don't
execute JS, so they only ever read the site's generic default OG tags.

Each generated share/<id>.html is a tiny static page carrying that story's
real Open Graph / Twitter Card tags (title, excerpt, hero photo), so pasted
links unfurl with the correct headline and image. Real visitors are sent on
to the live story instantly via a JS redirect only - deliberately NOT a
<meta http-equiv="refresh">, because Facebook's crawler (and some others)
follows an immediate meta-refresh as if it were a real redirect and scrapes
the target URL's tags instead of this page's, which defeats the whole
point. Crawlers don't execute JS, so they stay put and read these tags.

Regenerated automatically by .github/workflows/gen_share_pages.yml on every
push that touches content.json - no manual step.
"""
import html
import json
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_JSON = os.path.join(REPO_ROOT, 'content.json')
SHARE_DIR = os.path.join(REPO_ROOT, 'share')
SITE = 'https://vilfintv.com'
DEFAULT_IMAGE = SITE + '/images/vilfintv-logo.jpg'
EXCERPT_LEN = 160

TAG_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'\s+')


def resolve_photo(photo):
    if not photo:
        return DEFAULT_IMAGE
    photo = photo.strip()
    if photo.startswith('http://') or photo.startswith('https://'):
        return photo
    if photo.startswith('/'):
        return SITE + photo
    return SITE + '/' + photo


def excerpt_of(story_html):
    text = TAG_RE.sub(' ', story_html or '')
    text = html.unescape(text)
    text = WS_RE.sub(' ', text).strip()
    if not text:
        return ''
    if len(text) <= EXCERPT_LEN:
        return text
    return text[:EXCERPT_LEN].rsplit(' ', 1)[0] + '…'


def page_html(item):
    story_id = str(item['id'])
    heading = (item.get('heading') or 'VilfinTV News').strip()
    photo = resolve_photo(item.get('photo'))
    desc = excerpt_of(item.get('story')) or 'Read the full story on VilfinTV News.'
    target = f'{SITE}/news.html?story={story_id}'

    title_esc = html.escape(heading, quote=True)
    desc_esc = html.escape(desc, quote=True)
    photo_esc = html.escape(photo, quote=True)
    target_esc = html.escape(target, quote=True)
    target_js = json.dumps(target)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0"/>
<title>{title_esc} — VilfinTV News</title>
<meta name="description" content="{desc_esc}"/>
<meta name="robots" content="index, follow, max-image-preview:large"/>
<link rel="canonical" href="{target_esc}"/>

<meta property="og:type" content="article"/>
<meta property="og:site_name" content="VilfinTV News"/>
<meta property="og:locale" content="en_US"/>
<meta property="og:title" content="{title_esc}"/>
<meta property="og:description" content="{desc_esc}"/>
<meta property="og:image" content="{photo_esc}"/>
<meta property="og:url" content="{target_esc}"/>

<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{title_esc}"/>
<meta name="twitter:description" content="{desc_esc}"/>
<meta name="twitter:image" content="{photo_esc}"/>

<script>location.replace({target_js});</script>
<style>
  html,body{{height:100%;margin:0;background:#0a192f;color:#e6edf7;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
  .wrap{{min-height:100%;display:flex;flex-direction:column;align-items:center;
    justify-content:center;text-align:center;padding:32px;box-sizing:border-box}}
  .spin{{width:34px;height:34px;border-radius:50%;
    border:3px solid rgba(230,237,247,.2);border-top-color:#3b82f6;
    animation:sp .8s linear infinite;margin-bottom:18px}}
  @keyframes sp{{to{{transform:rotate(360deg)}}}}
  h1{{font-size:17px;font-weight:600;margin:0 0 8px;max-width:480px}}
  p{{font-size:13px;color:#9fb0c8;margin:0}}
  a{{color:#60a5fa;text-decoration:none}}
</style>
</head>
<body>
<div class="wrap">
  <div class="spin"></div>
  <h1>{title_esc}</h1>
  <p>Opening on VilfinTV News… <a href="{target_esc}">Continue</a></p>
</div>
</body>
</html>
'''


def main():
    with open(CONTENT_JSON, encoding='utf-8') as f:
        items = json.load(f)

    os.makedirs(SHARE_DIR, exist_ok=True)
    live_ids = set()
    written = 0
    for item in items:
        if not item.get('id') or not item.get('heading'):
            continue
        story_id = str(item['id'])
        live_ids.add(story_id)
        path = os.path.join(SHARE_DIR, f'{story_id}.html')
        new_content = page_html(item)
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                if f.read() == new_content:
                    continue
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        written += 1

    pruned = 0
    for fname in os.listdir(SHARE_DIR):
        if not fname.endswith('.html'):
            continue
        if fname[:-5] not in live_ids:
            os.remove(os.path.join(SHARE_DIR, fname))
            pruned += 1

    print(f'Generated/updated {written} share page(s), pruned {pruned} stale page(s), '
          f'{len(live_ids)} total live stories.')


if __name__ == '__main__':
    main()
