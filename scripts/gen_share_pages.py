#!/usr/bin/env python3
"""Generate static per-story article pages under share/<id>.html.

Each share/<id>.html is a fully rendered, indexable article page carrying:
- The story's full HTML content (readable by humans and search engines)
- NewsArticle JSON-LD structured data
- Open Graph / Twitter Card meta tags for social link previews

No JS redirect — the share page IS the canonical article page for search.

Regenerated automatically by .github/workflows/gen_share_pages.yml on every
push that touches content.json - no manual step.
"""
import html
import json
import os
import re
import struct
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_JSON = os.path.join(REPO_ROOT, 'content.json')
SHARE_DIR = os.path.join(REPO_ROOT, 'share')
SITE = 'https://vilfintv.com'
DEFAULT_IMAGE = SITE + '/images/vilfintv-logo.jpg'
EXCERPT_LEN = 160
# A default urllib/Python User-Agent gets flat-out blocked (Cloudflare error
# 1010) on this site's Workers domain - confirmed the hard way with the
# antigravity bot. Every outbound fetch here needs a normal-looking UA.
FETCH_UA = 'Mozilla/5.0 (compatible; VilfinTV-ShareGen/1.0)'

TAG_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'\s+')


def fetch_image_info(url):
    """Return (width, height, content_type) for an image URL, or None on any
    failure - dimensions are a nice-to-have for og:image:width/height, never
    worth failing the whole page generation over."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': FETCH_UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
            data = resp.read(1_000_000)
    except Exception:
        return None

    size = _image_size(data)
    if not size:
        return None
    return size[0], size[1], (content_type or 'image/jpeg')


def _image_size(data):
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        w, h = struct.unpack('>II', data[16:24])
        return w, h
    if data[:6] in (b'GIF87a', b'GIF89a') and len(data) >= 10:
        w, h = struct.unpack('<HH', data[6:10])
        return w, h
    if data[:2] == b'\xff\xd8':  # JPEG - walk markers to find the SOF segment
        i = 2
        n = len(data)
        while i + 9 < n:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack('>HH', data[i + 5:i + 9])
                return w, h
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seglen = struct.unpack('>H', data[i + 2:i + 4])[0]
            i += 2 + seglen
        return None
    return None


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


SECTION_LABELS = {
    'trending': 'Trending',
    'global': 'World',
    'india': 'India',
    'stock': 'Markets',
    'malayalam': 'Malayalam',
    'tech': 'Technology',
    'space': 'Space',
    'science': 'Science',
    'movies': 'Entertainment',
    'sports': 'Sports',
    'business': 'Business',
    'food': 'Lifestyle',
    'ml_food': 'Malayalam',
    'education': 'Education',
}


def _format_date(iso_str):
    """Parse an ISO date string and return e.g. 'July 28, 2026'. Returns '' on failure."""
    if not iso_str:
        return ''
    try:
        from datetime import datetime, timezone
        # Handle both 'Z' suffix and offset-aware strings
        s = iso_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        return f'{dt.strftime("%B")} {dt.day}, {dt.year}'
    except Exception:
        return ''


def page_html(item, image_info=None):
    story_id = str(item['id'])
    heading = (item.get('heading') or 'VilfinTV News').strip()
    photo = resolve_photo(item.get('photo'))
    story_html_raw = item.get('story') or ''
    desc = excerpt_of(story_html_raw) or 'Read the full story on VilfinTV News.'
    self_url = f'{SITE}/share/{story_id}.html'
    section_key = (item.get('section') or '').lower()
    section_label = SECTION_LABELS.get(section_key, 'News')
    published_at = item.get('published_at') or ''
    date_display = _format_date(published_at)

    title_esc = html.escape(heading, quote=True)
    desc_esc = html.escape(desc, quote=True)
    photo_esc = html.escape(photo, quote=True)
    self_url_esc = html.escape(self_url, quote=True)
    section_label_esc = html.escape(section_label, quote=True)

    # og:url and rel=canonical point to self — this page IS the article.
    image_extra = ''
    if image_info:
        w, h, ctype = image_info
        image_extra = (
            f'<meta property="og:image:secure_url" content="{photo_esc}"/>\n'
            f'<meta property="og:image:width" content="{w}"/>\n'
            f'<meta property="og:image:height" content="{h}"/>\n'
            f'<meta property="og:image:type" content="{html.escape(ctype, quote=True)}"/>'
        )

    date_line = f'<p class="article-date">{html.escape(date_display)}</p>' if date_display else ''

    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": heading,
        "description": desc,
        "image": photo,
        "datePublished": published_at if published_at else None,
        "url": self_url,
        "publisher": {
            "@type": "Organization",
            "name": "VilfinTV",
            "url": SITE,
            "logo": {
                "@type": "ImageObject",
                "url": f"{SITE}/images/vilfintv-logo.jpg"
            }
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": self_url
        }
    }, ensure_ascii=False, indent=2)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title_esc} — VilfinTV News</title>
<meta name="description" content="{desc_esc}"/>
<meta name="robots" content="index, follow, max-image-preview:large"/>
<link rel="canonical" href="{self_url_esc}"/>

<meta property="og:type" content="article"/>
<meta property="og:site_name" content="VilfinTV News"/>
<meta property="og:locale" content="en_US"/>
<meta property="og:title" content="{title_esc}"/>
<meta property="og:description" content="{desc_esc}"/>
<meta property="og:image" content="{photo_esc}"/>
{image_extra}
<meta property="og:url" content="{self_url_esc}"/>

<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{title_esc}"/>
<meta name="twitter:description" content="{desc_esc}"/>
<meta name="twitter:image" content="{photo_esc}"/>

<script type="application/ld+json">
{json_ld}
</script>

<style>
:root {{
  --page-bg:#0f1117; --card:#1a1f2e; --card2:#1e2436; --card3:#222840; --card4:#282d42;
  --text:#e8edf5; --text2:#b8c4d8; --text3:#8896b0;
  --border:#2a3148; --border2:#333d55;
  --amber:#f59e0b; --burn:#3b82f6; --burn2:#60a5fa; --burn3:#2563eb;
  --gold:#f59e0b; --gold2:#fbbf24; --glow:rgba(59,130,246,.15);
}}
*,*::before,*::after{{box-sizing:border-box}}
html,body{{margin:0;padding:0;background:var(--page-bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:17px;line-height:1.7}}
a{{color:var(--burn2);text-decoration:none}}
a:hover{{text-decoration:underline}}
img{{max-width:100%;height:auto;display:block}}

/* Site header */
.site-header{{background:var(--card);border-bottom:1px solid var(--border);padding:12px 20px;
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}}
.site-header .brand{{display:flex;flex-direction:column}}
.site-header .brand-name{{font-size:20px;font-weight:700;color:var(--text);letter-spacing:-0.3px}}
.site-header .brand-tag{{font-size:11px;color:var(--text3);letter-spacing:.5px;text-transform:uppercase}}
.site-header .back-link{{font-size:13px;color:var(--burn2);white-space:nowrap}}

/* Main layout */
main{{max-width:780px;margin:0 auto;padding:32px 20px 48px}}

/* Section badge */
.section-badge{{display:inline-block;background:var(--burn3);color:#fff;
  font-size:11px;font-weight:600;letter-spacing:.8px;text-transform:uppercase;
  padding:3px 10px;border-radius:4px;margin-bottom:14px}}

/* Headline */
h1{{font-size:clamp(22px,4vw,34px);font-weight:700;line-height:1.25;
  color:var(--text);margin:0 0 10px}}

/* Date */
.article-date{{font-size:13px;color:var(--text3);margin:0 0 20px}}

/* Hero image */
.hero-img{{width:100%;max-height:420px;object-fit:cover;border-radius:8px;
  margin-bottom:28px;background:var(--card2)}}

/* Article body — inherit story HTML styles as-is */
.article-body{{color:var(--text2);font-size:17px;line-height:1.75}}
.article-body p{{margin:0 0 1.1em}}
.article-body h2,.article-body h3,.article-body h4{{color:var(--text);margin:1.4em 0 .6em;line-height:1.3}}
.article-body ul,.article-body ol{{padding-left:1.4em;margin:0 0 1.1em}}
.article-body li{{margin-bottom:.35em}}
.article-body strong,.article-body b{{color:var(--text);font-weight:600}}
.article-body a{{color:var(--burn2)}}
.article-body img{{border-radius:6px;margin:12px 0}}
.article-body blockquote{{border-left:3px solid var(--amber);margin:1em 0;
  padding:.5em 1em;color:var(--text3);font-style:italic}}
.article-body table{{border-collapse:collapse;width:100%;margin:1em 0;font-size:15px}}
.article-body th,.article-body td{{border:1px solid var(--border2);padding:8px 12px;text-align:left}}
.article-body th{{background:var(--card2);color:var(--text)}}

/* Footer */
.site-footer{{border-top:1px solid var(--border);padding:24px 20px;text-align:center;
  color:var(--text3);font-size:14px}}
.site-footer a{{color:var(--burn2);font-weight:500}}

@media(max-width:600px){{
  main{{padding:20px 14px 36px}}
  .site-header{{padding:10px 14px}}
}}
</style>
</head>
<body>

<header class="site-header">
  <a href="{SITE}" style="text-decoration:none">
    <div class="brand">
      <span class="brand-name">VilfinTV</span>
      <span class="brand-tag">News &amp; Markets</span>
    </div>
  </a>
  <a class="back-link" href="{SITE}/news.html">← Back to VilfinTV News</a>
</header>

<main>
  <article>
    <div class="section-badge">{section_label_esc}</div>
    <h1>{title_esc}</h1>
    {date_line}
    <img class="hero-img" src="{photo_esc}" alt="{title_esc}" loading="eager"/>
    <div class="article-body">
{story_html_raw}
    </div>
  </article>
</main>

<footer class="site-footer">
  <a href="{SITE}/news.html">More stories on VilfinTV →</a>
</footer>

</body>
</html>
'''


def main():
    with open(CONTENT_JSON, encoding='utf-8') as f:
        items = json.load(f)

    os.makedirs(SHARE_DIR, exist_ok=True)
    live_ids = set()
    written = 0
    image_cache = {}
    for item in items:
        if not item.get('id') or not item.get('heading'):
            continue
        story_id = str(item['id'])
        live_ids.add(story_id)
        photo_url = resolve_photo(item.get('photo'))
        if photo_url not in image_cache:
            image_cache[photo_url] = fetch_image_info(photo_url)
        path = os.path.join(SHARE_DIR, f'{story_id}.html')
        new_content = page_html(item, image_cache[photo_url])
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
