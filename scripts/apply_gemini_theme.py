"""
apply_gemini_theme.py
Replaces the [data-theme="gemini"] CSS block in index.html and all child pages
with the true Google Gemini AI mobile-app palette stored in _gemini_theme_new.css.
"""
import re, os, sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Multi Screener root
CSS_FILE = os.path.join(BASE, "scripts", "_gemini_theme_new.css")

with open(CSS_FILE, encoding="utf-8") as f:
    NEW_CSS = f.read().strip()

# ── index.html ─────────────────────────────────────────────────────────────
# The gemini block lives between these two markers (exclusive of the second).
IDX_START = "/* ══ GEMINI ANIMATED THEME ══ */"
IDX_END   = "/* ── Animated theme colour swatches ── */"

idx_path = os.path.join(BASE, "index.html")
with open(idx_path, encoding="utf-8") as f:
    src = f.read()

i_start = src.find(IDX_START)
i_end   = src.find(IDX_END)

if i_start == -1 or i_end == -1:
    print(f"ERROR index.html: markers not found  start={i_start}  end={i_end}")
else:
    # Replace the gemini block (keep the trailing newline so the next comment butts up cleanly)
    replacement = NEW_CSS + "\n\n"
    new_src = src[:i_start] + replacement + src[i_end:]
    with open(idx_path, "w", encoding="utf-8") as f:
        f.write(new_src)
    print(f"OK  index.html  ({len(src):,} -> {len(new_src):,} chars)")

# ── Child pages ─────────────────────────────────────────────────────────────
# Each child page has a comment block that starts like:
#   /* ...
#      GEMINI ANIMATED THEME ...
#   */
# and the CSS block ends right before </style>.
# We replace from the opening /* of that block through the last character
# before </style>, leaving </style> intact.

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

# Pattern: look for the /* comment that contains "GEMINI ANIMATED THEME",
# then capture everything up to (but not including) </style>
CHILD_PAT = re.compile(
    r"/\*[^*]*GEMINI ANIMATED THEME[^*]*\*/(.*?)(?=</style>)",
    re.DOTALL | re.IGNORECASE,
)

for page in CHILD_PAGES:
    path = os.path.join(BASE, page)
    if not os.path.exists(path):
        print(f"SKIP {page}  (not found)")
        continue

    with open(path, encoding="utf-8") as f:
        src = f.read()

    m = CHILD_PAT.search(src)
    if not m:
        print(f"WARN {page}  (gemini block not found — skipped)")
        continue

    # Replace: from the start of the opening /* to the end of the match (just before </style>)
    block_start = m.start()   # start of the opening /*
    block_end   = m.end()     # end of the content, right before </style>

    new_src = src[:block_start] + "\n" + NEW_CSS + "\n" + src[block_end:]

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_src)
    print(f"OK  {page}  ({len(src):,} -> {len(new_src):,} chars)")

print("\nDone.")
