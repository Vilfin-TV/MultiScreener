"""
apply_news_reader_theme.py
Inserts [data-theme="news-reader"] CSS block into index.html and all child pages.
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")

BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_FILE = os.path.join(BASE, "scripts", "_news_reader_theme.css")

with open(CSS_FILE, encoding="utf-8") as f:
    NEW_CSS = f.read().strip()

# ── index.html — insert before the swatch section ──────────────────────────
IDX_ANCHOR = "/* ── Animated theme colour swatches ── */"

idx_path = os.path.join(BASE, "index.html")
with open(idx_path, encoding="utf-8") as f:
    src = f.read()

if "[data-theme=\"news-reader\"]" in src:
    print("SKIP index.html  (news-reader block already present)")
else:
    pos = src.find(IDX_ANCHOR)
    if pos == -1:
        print("ERROR index.html: anchor not found")
    else:
        new_src = src[:pos] + NEW_CSS + "\n\n" + src[pos:]
        with open(idx_path, "w", encoding="utf-8") as f:
            f.write(new_src)
        print(f"OK  index.html  ({len(src):,} -> {len(new_src):,} chars)")

# ── Child pages — append before </style> ───────────────────────────────────
CHILD_PAGES = [
    "blog_intelligence_hub.html",
    "user_manual.html",
    "user_guide.html",
    "trendlyne_screener.html",
    "mf_live_screener.html",
    "mutual_fund_analyser.html",
    "stock_research.html",
    "pre_market_briefing.html",
    "stock_status.html",
    "pine_script_generator.html",
    "screener_query_generator.html",
    "compare_calc.html",
    "allocation_calc.html",
    "sip_calc.html",
    "lumpsum_calc.html",
    "combined_calc.html",
    "html_converter.html",
    "radio-widget.html",
]

# Anchor: the gemini ::selection rule always ends the gemini block — insert after it
ANCHOR = "[data-theme=\"gemini\"] ::selection"

for page in CHILD_PAGES:
    path = os.path.join(BASE, page)
    if not os.path.exists(path):
        print(f"SKIP {page}  (not found)")
        continue

    with open(path, encoding="utf-8") as f:
        src = f.read()

    if "[data-theme=\"news-reader\"]" in src:
        print(f"SKIP {page}  (already present)")
        continue

    pos = src.find(ANCHOR)
    if pos == -1:
        # fallback: insert before the first </style>
        pos2 = src.find("</style>")
        if pos2 == -1:
            print(f"WARN {page}  (no anchor or </style> — skipped)")
            continue
        new_src = src[:pos2] + "\n" + NEW_CSS + "\n" + src[pos2:]
    else:
        # find end of that line, insert after it
        eol = src.find("\n", pos)
        if eol == -1:
            eol = len(src)
        new_src = src[:eol + 1] + "\n" + NEW_CSS + "\n" + src[eol + 1:]

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_src)
    print(f"OK  {page}  ({len(src):,} -> {len(new_src):,} chars)")

print("\nDone.")
