#!/usr/bin/env python3
"""Generate sitemap.xml and news-sitemap.xml for vilfintv.com.

sitemap.xml      — all static pages + every story share page
news-sitemap.xml — only stories published in the last 48 hours (Google News)

Run automatically by .github/workflows/gen_share_pages.yml after share pages
are regenerated, so the sitemap always reflects the current content.json.
"""
import html
import json
import os
from datetime import datetime, timezone, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_JSON = os.path.join(REPO_ROOT, 'content.json')
SITEMAP_OUT = os.path.join(REPO_ROOT, 'sitemap.xml')
NEWS_SITEMAP_OUT = os.path.join(REPO_ROOT, 'news-sitemap.xml')
SITE = 'https://vilfintv.com'

STATIC_PAGES = [
    (f'{SITE}/', '1.0', 'daily'),
    (f'{SITE}/news.html', '1.0', 'daily'),
    (f'{SITE}/story.html', '1.0', 'daily'),
    (f'{SITE}/education.html', '0.9', 'daily'),
    (f'{SITE}/blog_intelligence_hub.html', '0.9', 'daily'),
    (f'{SITE}/market_sentiment_score.html', '0.8', 'monthly'),
    (f'{SITE}/screener_query_generator.html', '0.8', 'monthly'),
    (f'{SITE}/stock_research.html', '0.8', 'daily'),
    (f'{SITE}/mutual_fund_analyser.html', '0.8', 'daily'),
    (f'{SITE}/mf_live_screener.html', '0.8', 'daily'),
    (f'{SITE}/pre_market_briefing.html', '0.8', 'daily'),
    (f'{SITE}/sip_calc.html', '0.7', 'monthly'),
    (f'{SITE}/lumpsum_calc.html', '0.7', 'monthly'),
    (f'{SITE}/combined_calc.html', '0.7', 'monthly'),
    (f'{SITE}/compare_calc.html', '0.7', 'monthly'),
    (f'{SITE}/allocation_calc.html', '0.7', 'monthly'),
    (f'{SITE}/trendlyne_screener.html', '0.7', 'monthly'),
    (f'{SITE}/pine_script_generator.html', '0.7', 'monthly'),
    (f'{SITE}/manage_subscription.html', '0.6', 'monthly'),
    (f'{SITE}/user_manual.html', '0.6', 'monthly'),
    (f'{SITE}/user_guide.html', '0.6', 'monthly'),
    (f'{SITE}/user-setup-guide.html', '0.6', 'monthly'),
    (f'{SITE}/html_converter.html', '0.6', 'monthly'),
    (f'{SITE}/legal.html', '0.3', 'yearly'),
]

# Sections that get a higher priority in the sitemap
HIGH_PRIORITY_SECTIONS = {'stock', 'business', 'global', 'india'}

# Language for Google News sitemap per section
MALAYALAM_SECTIONS = {'malayalam', 'ml_food'}


def _story_priority(section):
    return '0.7' if (section or '').lower() in HIGH_PRIORITY_SECTIONS else '0.6'


def _parse_iso(iso_str):
    """Parse an ISO 8601 string to a timezone-aware datetime. Returns None on failure."""
    if not iso_str:
        return None
    try:
        s = iso_str.replace('Z', '+00:00')
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _lastmod_date(iso_str, today_str):
    """Return YYYY-MM-DD for sitemap lastmod: use published_at date or today."""
    dt = _parse_iso(iso_str)
    if dt:
        return dt.strftime('%Y-%m-%d')
    return today_str


def _xml_escape(s):
    return html.escape(str(s), quote=True)


def main():
    now = datetime.now(timezone.utc)
    today_str = now.strftime('%Y-%m-%d')
    cutoff = now - timedelta(hours=48)

    with open(CONTENT_JSON, encoding='utf-8') as f:
        items = json.load(f)

    # Filter out items without id/heading
    stories = [it for it in items if it.get('id') and it.get('heading')]

    # ── Main sitemap ──────────────────────────────────────────────────────────
    url_blocks = []

    for loc, priority, changefreq in STATIC_PAGES:
        if changefreq == 'daily':
            lastmod = today_str
        else:
            lastmod = '2026-01-01'
        url_blocks.append(
            f'  <url>\n'
            f'    <loc>{_xml_escape(loc)}</loc>\n'
            f'    <lastmod>{lastmod}</lastmod>\n'
            f'    <changefreq>{changefreq}</changefreq>\n'
            f'    <priority>{priority}</priority>\n'
            f'  </url>'
        )

    for item in stories:
        story_id = str(item['id'])
        section = (item.get('section') or '').lower()
        published_at = item.get('published_at') or ''
        loc = f'{SITE}/share/{story_id}.html'
        lastmod = _lastmod_date(published_at, today_str)
        priority = _story_priority(section)
        url_blocks.append(
            f'  <url>\n'
            f'    <loc>{_xml_escape(loc)}</loc>\n'
            f'    <lastmod>{lastmod}</lastmod>\n'
            f'    <changefreq>never</changefreq>\n'
            f'    <priority>{priority}</priority>\n'
            f'  </url>'
        )

    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(url_blocks)
        + '\n</urlset>\n'
    )

    # ── News sitemap (last 48 hours) ──────────────────────────────────────────
    news_blocks = []

    for item in stories:
        published_at = item.get('published_at') or ''
        dt = _parse_iso(published_at)
        if dt is None or dt < cutoff:
            continue

        story_id = str(item['id'])
        section = (item.get('section') or '').lower()
        heading = (item.get('heading') or '').strip()
        loc = f'{SITE}/share/{story_id}.html'
        language = 'ml' if section in MALAYALAM_SECTIONS else 'en'
        # Use the raw ISO string for news:publication_date
        pub_date_esc = _xml_escape(published_at)
        title_esc = _xml_escape(heading)

        news_blocks.append(
            f'  <url>\n'
            f'    <loc>{_xml_escape(loc)}</loc>\n'
            f'    <news:news>\n'
            f'      <news:publication>\n'
            f'        <news:name>VilfinTV News</news:name>\n'
            f'        <news:language>{language}</news:language>\n'
            f'      </news:publication>\n'
            f'      <news:publication_date>{pub_date_esc}</news:publication_date>\n'
            f'      <news:title>{title_esc}</news:title>\n'
            f'    </news:news>\n'
            f'  </url>'
        )

    news_sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n'
        + ('\n'.join(news_blocks) if news_blocks else '')
        + '\n</urlset>\n'
    )

    with open(SITEMAP_OUT, 'w', encoding='utf-8') as f:
        f.write(sitemap_xml)

    with open(NEWS_SITEMAP_OUT, 'w', encoding='utf-8') as f:
        f.write(news_sitemap_xml)

    total_urls = len(STATIC_PAGES) + len(stories)
    print(
        f'Sitemap: {total_urls} URLs ({len(STATIC_PAGES)} static + {len(stories)} stories). '
        f'News sitemap: {len(news_blocks)} article(s) in last 48h.'
    )


if __name__ == '__main__':
    main()
