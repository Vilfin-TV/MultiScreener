#!/usr/bin/env python3
"""Writes FAQPage structured data (JSON-LD) into the screener pages from their own FAQ cards.

Every question / answer of the page's FAQ section (#faq: <details><summary>Q</summary>A</details>) becomes one entry,
with the answer as plain text, so search engines read exactly what visitors see. The block sits between the markers
<!-- faq-jsonld --> … <!-- /faq-jsonld --> just before </head>. Re-run after editing any FAQ:

    python3 scripts/gen_faq_jsonld.py
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["india_mf_screener.html", "etf_momentum.html", "global_etf_momentum.html"]
START, END = "<!-- faq-jsonld -->", "<!-- /faq-jsonld -->"


def text(fragment):
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</(p|li|tr|h\d)>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def faq_section(s):
    m = re.search(r'<(section|div)[^>]*\bid="faq"[^>]*>', s)
    if not m:
        return ""
    tag, i, depth = m.group(1), m.end(), 1
    for t in re.finditer(r"<(/?)(section|div)\b[^>]*>", s[i:]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return s[i:i + t.start()]
    return s[i:]


def build(page):
    p = ROOT / page
    s = p.read_text()
    items = []
    for m in re.finditer(r"<details\b[^>]*>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>", faq_section(s), re.S):
        q, a = text(m.group(1)), text(m.group(2))
        if q and len(a) > 20:
            items.append({"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}})
    if not items:
        print(f"{page}: no FAQ found — left unchanged")
        return
    block = START + '\n<script type="application/ld+json">\n' + json.dumps(
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items}, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/") + "\n</script>\n" + END
    if START in s:
        s = s[:s.index(START)] + block + s[s.index(END) + len(END):]
    else:
        h = s.index("</head>")
        s = s[:h] + block + "\n" + s[h:]
    p.write_text(s)
    print(f"{page}: {len(items)} questions")


if __name__ == "__main__":
    for pg in sys.argv[1:] or PAGES:
        build(pg)
