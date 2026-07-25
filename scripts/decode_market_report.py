#!/usr/bin/env python3
"""Decode data/market_sentiment_snapshot.json into a stock-news article and
append it to content.json. Intended to run daily at 10:00 JST via GitHub
Actions, well after market_report.yml's snapshot refresh (07:00 JST target,
08:40 JST hard deadline).

Monday-Friday: a day-over-day decode, comparing today's snapshot to the most
recent prior one, with a 14-factor comparison chart.
Saturday: a weekly decode covering the trailing week's score trajectory,
with a bar chart, since Saturday's snapshot reflects the week's last
trading day (Friday) close.
Sunday: no report - exits cleanly, no new trading data since Saturday.

Usage: python3 scripts/decode_market_report.py [--dry-run]
  --dry-run: generate the article and chart, print/save them, but do not
  modify content.json or upload anything. Chart is saved to /tmp for
  inspection; article HTML/heading are printed to stdout.
"""
import html
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
SNAPSHOT_FILE = 'data/market_sentiment_snapshot.json'
CONTENT_FILE = 'content.json'
HOLIDAYS_FILE = 'data/nse_holidays.json'
HERO_URL = 'https://screener-proxy.vilfintv.workers.dev/r2/media/stock/daily-market-report-2026-07-20-hero.jpg'
R2_BUCKET = 'vilfintv-media'
R2_PREFIX = 'media/stock'
PUBLIC_R2_BASE = 'https://screener-proxy.vilfintv.workers.dev/r2/media/stock'

DRY_RUN = '--dry-run' in sys.argv

TH = 'style="border:1px solid #334155;padding:8px;text-align:left;background:#1e293b;color:#fff;font-size:13px;"'
TD_A = 'style="border:1px solid #cbd5e1;padding:8px;background:#f8fafc;font-size:13.5px;"'
TD_B = 'style="border:1px solid #cbd5e1;padding:8px;background:#ffffff;font-size:13.5px;"'


def table(headers, rows):
    html = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;margin:14px 0;">'
    html += '<thead><tr>' + ''.join(f'<th {TH}>{h}</th>' for h in headers) + '</tr></thead><tbody>'
    for i, row in enumerate(rows):
        td = TD_A if i % 2 == 0 else TD_B
        html += '<tr>' + ''.join(f'<td {td}>{c}</td>' for c in row) + '</tr>'
    html += '</tbody></table></div>'
    return html


def img(url, alt, w=460):
    return (f'<div style="text-align:center;margin:16px 0;">'
            f'<img src="{url}" alt="{alt}" loading="lazy" '
            f'style="max-width:{w}px;width:100%;border-radius:10px;'
            f'box-shadow:0 4px 16px rgba(0,0,0,0.18);"></div>')


def git_show_json(commit, path):
    raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'])
    return json.loads(raw)


def load_holidays():
    """{date_str: holiday_name} for NSE/BSE weekday market closures. See
    data/nse_holidays.json's own _comment for sourcing/confidence notes -
    update that file if a date turns out wrong; takes effect next run."""
    try:
        with open(HOLIDAYS_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith('_')}


def get_recent_snapshots(days_back=10):
    """{date_str: snapshot} for the last `days_back` days, deduped by the
    snapshot's own 'date' field - git log is newest-first, so the first
    commit seen for a given date is that date's final/latest state."""
    try:
        commits = subprocess.check_output(
            ['git', 'log', '--format=%H', f'--since={days_back} days ago', '--', SNAPSHOT_FILE]
        ).decode().split()
    except subprocess.CalledProcessError:
        commits = []
    result = {}
    for c in commits:
        try:
            d = git_show_json(c, SNAPSHOT_FILE)
        except Exception:
            continue
        result.setdefault(d.get('date'), d)
    return result


def regime_rows(today_score):
    bands = [
        (50, 100, 'Bullish Expansion', 'Broad-based strength — most signals agree, risk-taking is rewarded'),
        (10, 49, 'Bullish Leaning / Neutral', 'Reasonably balanced, tilted positive — real opportunities exist but so do genuine cracks'),
        (-10, 9, 'Neutral / Mixed', 'No clear edge either direction — a coin-flip environment'),
        (-50, -11, 'Bearish Contraction', 'Defensive posture warranted — more signals turning negative than positive'),
        (-100, -51, 'Extremely Bearish / Risk-Off', 'Capital preservation mode — most "buy the dip" signals are unreliable here'),
    ]
    rows = []
    for lo, hi, label, desc in bands:
        is_today = lo <= today_score <= hi
        range_str = f'{"+" if lo >= 0 else ""}{lo} to {"+" if hi >= 0 else ""}{hi}'
        desc_final = f'<strong>(Today: {today_score})</strong> {desc}' if is_today else desc
        rows.append([range_str, label, desc_final])
    return rows


def classify_factor(points, delta):
    if points >= 10:
        base = 'Consider'
    elif points > 0:
        base = 'Consider with caution'
    elif points == 0:
        base = 'Ignore for now — neutral reading'
    elif points >= -10:
        base = 'Weigh lightly'
    else:
        base = 'Pay close attention'
    if delta is not None and delta != 0:
        base += f' (was {delta_prev_points(points, delta):+d} last time)'
    return base


def delta_prev_points(points, delta):
    return points - delta


def factor_map(snapshot):
    return {b['label']: b for b in snapshot.get('breakdown', [])}


def build_factor_rows(today, prev):
    tmap = factor_map(today)
    pmap = factor_map(prev) if prev else {}
    ordered = sorted(today.get('breakdown', []), key=lambda b: -b['points'])
    rows = []
    biggest_label, biggest_delta = None, 0
    for b in ordered:
        label, pts, reading = b['label'], b['points'], b['reading']
        prev_b = pmap.get(label)
        delta = (pts - prev_b['points']) if prev_b else None
        if delta is not None and abs(delta) > abs(biggest_delta):
            biggest_delta, biggest_label = delta, label
        note = classify_factor(pts, delta)
        pts_str = f'{pts:+d}' if pts != 0 else '0'
        rows.append([label, reading, pts_str, note])
    return rows, biggest_label, biggest_delta


def picks_rows(picks_section):
    order = ['equity', 'commodity', 'bond', 'currency']
    labels = {'equity': 'Equity', 'commodity': 'Commodity', 'bond': 'Bond', 'currency': 'Currency'}
    rows = []
    for k in order:
        v = picks_section.get(k)
        if not v:
            continue
        rows.append([labels[k], v])
    return rows


def make_chart_weekday(today, prev, out_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    BLUE, ORANGE, INK, SEC_INK, MUTED, GRID, SURFACE = (
        '#2a78d6', '#eb6834', '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#fcfcfb')

    def color_for(v):
        return BLUE if v > 0 else (ORANGE if v < 0 else '#c3c2b7')

    tmap = factor_map(today)
    pmap = factor_map(prev) if prev else {}
    raw_labels = [b['label'] for b in sorted(today.get('breakdown', []), key=lambda b: -b['points'])]
    labels = [html.unescape(l) for l in raw_labels]
    today_vals = [tmap[l]['points'] for l in raw_labels]
    prev_vals = [pmap[l]['points'] if l in pmap else 0 for l in raw_labels]

    n = len(labels)
    fig, ax = plt.subplots(figsize=(9, max(6, n * 0.55)), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    bar_h, gap = 0.32, 0.06
    y_today = list(range(n))
    y_prev = [i + bar_h + gap for i in range(n)]

    ax.barh(y_today, today_vals, height=bar_h, color=[color_for(v) for v in today_vals],
            zorder=3, edgecolor=SURFACE, linewidth=0.6)
    ax.barh(y_prev, prev_vals, height=bar_h, color=[color_for(v) for v in prev_vals],
            alpha=0.45, zorder=3, edgecolor=SURFACE, linewidth=0.6)
    for y, v in zip(y_today, today_vals):
        off = 0.8 if v >= 0 else -0.8
        ax.text(v + off, y, f'{v:+d}' if v != 0 else '0', va='center',
                ha='left' if v >= 0 else 'right', fontsize=9, color=INK, fontweight='bold', zorder=4)
    for y, v in zip(y_prev, prev_vals):
        off = 0.8 if v >= 0 else -0.8
        ax.text(v + off, y, f'{v:+d}' if v != 0 else '0', va='center',
                ha='left' if v >= 0 else 'right', fontsize=8, color=SEC_INK, zorder=4)

    ax.set_yticks([i + (bar_h + gap) / 2 for i in range(n)])
    ax.set_yticklabels(labels, fontsize=9.5, color=INK)
    ax.invert_yaxis()
    ax.axvline(0, color='#c3c2b7', linewidth=1.2, zorder=2)
    lo = min(min(today_vals), min(prev_vals), 0) - 6
    hi = max(max(today_vals), max(prev_vals), 0) + 6
    ax.set_xlim(lo, hi)
    ax.set_xlabel('Points contributed to the daily score', fontsize=10, color=MUTED)
    ax.tick_params(axis='x', colors=MUTED, labelsize=9)
    ax.grid(axis='x', color=GRID, linewidth=0.8, zorder=1)
    for s in ['top', 'right', 'left', 'bottom']:
        ax.spines[s].set_visible(False)

    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor='#9a9a9a', alpha=1.0, edgecolor='none', label=f"Today ({today['date']})"),
        Patch(facecolor='#9a9a9a', alpha=0.45, edgecolor='none',
              label=f"Previous ({prev['date']})" if prev else 'Previous (n/a)'),
    ]
    fig.legend(handles=legend_elems, loc='upper right', bbox_to_anchor=(0.98, 0.965),
               frameon=False, fontsize=10.5, labelcolor=SEC_INK, ncol=2, columnspacing=1.2)
    ax.set_title('14-Factor Score Breakdown — Day-over-Day Comparison', fontsize=13,
                 color=INK, fontweight='bold', loc='left', pad=14)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(out_path, facecolor=SURFACE, bbox_inches='tight')
    plt.close(fig)


def make_chart_weekly(week_rows, out_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    BLUE, ORANGE, GRAY, INK, MUTED, GRID, SURFACE = (
        '#2a78d6', '#eb6834', '#c3c2b7', '#0b0b0b', '#898781', '#e1e0d9', '#fcfcfb')

    def color_for(v):
        if v is None:
            return GRID
        if v >= 50:
            return BLUE
        if v >= 10:
            return '#86b6ef'
        if v >= -10:
            return GRAY
        return ORANGE

    fig, ax = plt.subplots(figsize=(10, 6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    xs = list(range(len(week_rows)))
    vals = [r[1] if r[1] is not None else 0 for r in week_rows]
    colors = [color_for(r[1]) for r in week_rows]
    ax.bar(xs, vals, color=colors, width=0.6, zorder=3, edgecolor=SURFACE, linewidth=1)
    for i, row in enumerate(week_rows):
        label, v = row[0], row[1]
        gap_reason = row[2] if len(row) > 2 else None
        if v is not None:
            off = 3 if v >= 0 else -3
            va = 'bottom' if v >= 0 else 'top'
            ax.text(i, v + off, f'{v}', ha='center', va=va, fontsize=11, fontweight='bold', color=INK, zorder=4)
        else:
            gap_label = 'holiday' if gap_reason == 'holiday' else 'no data'
            ax.text(i, 5, gap_label, ha='center', va='bottom', fontsize=9, color=MUTED,
                    style='italic', rotation=90, zorder=4)
    ax.axhline(0, color=GRID, linewidth=1.2, zorder=1)
    ax.axhline(50, color=BLUE, linewidth=1, linestyle='--', alpha=0.4, zorder=1)
    ax.text(len(week_rows) - 0.4, 52, 'Bullish Expansion starts (50)', fontsize=8.5, color=BLUE, ha='right', alpha=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels([r[0] for r in week_rows], fontsize=9.5, color=INK)
    ax.set_ylim(-105, 115)
    ax.set_ylabel('Daily Score (-100 to +100)', fontsize=10, color=MUTED)
    ax.tick_params(axis='y', colors=MUTED, labelsize=9)
    ax.grid(axis='y', color=GRID, linewidth=0.8, zorder=0)
    for s in ['top', 'right']:
        ax.spines[s].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_color(GRID)
    ax.set_title('One Week: Daily Score Trajectory', fontsize=13, color=INK, fontweight='bold', loc='left', pad=14)
    plt.tight_layout()
    plt.savefig(out_path, facecolor=SURFACE, bbox_inches='tight')
    plt.close(fig)


def build_weekday_article(today, prev, chart_url):
    date_str = today['date']
    score, regime = today['score'], today['regime']
    prev_score = prev['score'] if prev else None
    prev_date = prev['date'] if prev else None
    change_str = f'{score - prev_score:+d}' if prev_score is not None else 'n/a'

    factor_rows_data, biggest_label, biggest_delta = build_factor_rows(today, prev)

    if prev_score is not None:
        intro = (f"Yesterday's report closed at {prev_score} out of 100. Today it's "
                 f"<strong>{score} out of 100</strong> — a {change_str.replace('+','').replace('-','')}-point "
                 f"{'jump' if score > prev_score else ('drop' if score < prev_score else 'move')}. "
                 f"Here's VilfinTV's full decode of the Daily Market Analysis &amp; Sector Report for {_fmt_date(date_str)}.")
    else:
        intro = (f"Today's Daily Market Analysis &amp; Sector Report scored <strong>{score} out of 100</strong>. "
                 f"Here's VilfinTV's full decode for {_fmt_date(date_str)}.")

    mover_sentence = ''
    if biggest_label and biggest_delta:
        mover_sentence = (f'<p>The single biggest mover today: <strong>{biggest_label}</strong>, which shifted '
                           f'{biggest_delta:+d} points from yesterday. Nearly everything else in the table below '
                           f'moved little or not at all — check the "was X yesterday" notes for the full picture.</p>')

    risk_alerts = today.get('risk_alerts', [])
    if risk_alerts:
        risk_html = '<ul style="line-height:1.9;">' + ''.join(f'<li>{r}</li>' for r in risk_alerts) + '</ul>'
    else:
        risk_html = '<p>No risk alerts today — nothing crossed the report\'s momentum or volatility thresholds.</p>'

    trending_rows_data = picks_rows(today.get('picks', {}).get('trending', {}))
    quality_rows_data = picks_rows(today.get('picks', {}).get('quality', {}))

    story = f"""<p>{intro}</p>
<h2>The Headline Number: {score}/100</h2>
{table(["Score Range", "Regime Label", "What It Broadly Means"], regime_rows(score))}
<h2>⚠️ Risk Alerts</h2>
{risk_html}
<h2>What Actually Built Today's Score: 14 Factors</h2>
{img(chart_url, "14-factor score breakdown, day-over-day comparison chart")}
{table(["Factor", "What It Actually Showed", "Points", "Consider or Ignore?"], factor_rows_data)}
{mover_sentence}
<h2>Where the Report Says to Look: Region &amp; Sectors</h2>
<p><strong>Regional pick:</strong> {today.get('regional_rec','n/a')}</p>
<p><strong>Momentum sector:</strong> {today.get('momentum_sector','n/a')} &nbsp;|&nbsp; <strong>Value sector:</strong> {today.get('value_sector','n/a')} &nbsp;|&nbsp; <strong>Long-term pick:</strong> {today.get('long_term_sector','n/a')}</p>
<h2>Trending Picks: What's Moving Right Now</h2>
{table(["Asset Class", "Pick"], trending_rows_data)}
<h2>Quality Picks: What's Been Consistent</h2>
{table(["Asset Class", "Pick"], quality_rows_data)}
<h2>Notable Currency Mover</h2>
<p>{today.get('notable_fx_mover', 'None flagged today.')}</p>
<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:14px 16px;margin:18px 0;"><p style="margin:0;font-size:14px;color:#7c2d12;"><strong>⚠️ Do your own homework first.</strong> Everything above is a data-driven starting point, not a finish line. Verify the numbers yourself and size any position to your own risk tolerance before acting on any pick in this report.</p></div>
<h2>How to Actually Act on This</h2>
<ul style="line-height:1.9;"><li><strong>For Indian market exposure:</strong> <a href="https://zerodha.com/open-account?c=XKQ288">Zerodha</a> or <a href="https://join.dhan.co/?invite=VFZJN04428">Dhan</a>.</li><li><strong>For index funds/ETFs:</strong> <a href="https://kuvera.in/s/wsapp?referral=1T6BH">Kuvera</a>, direct plans, zero commission.</li><li><strong>For frequent trading:</strong> <a href="https://prostocks.com/open-an-account?ref=G1392">ProStocks</a>' flat-fee plan.</li><li><strong>For broader global market access:</strong> <a href="https://www.interactivebrokers.co.jp/en/accounts/what-you-need-jp.php">Interactive Brokers</a>.</li></ul>
<p style="font-size:12.5px;color:#888;"><em>🎁 Using the referral links above benefits you at no extra cost.</em></p>
<h2>Get This Report Every Morning — Completely Free</h2>
<p>This full breakdown lands in your inbox every trading day morning, before 9:00 AM JST. <strong>Subscribing is completely free.</strong></p>
<div style="text-align:center;margin:16px 0;"><a href="https://vilfintv.com/manage_subscription.html?action=subscribe" style="display:inline-block;background:#16a34a;color:#ffffff;font-weight:bold;font-size:15px;padding:12px 28px;border-radius:24px;text-decoration:none;box-shadow:0 4px 12px rgba(22,163,74,0.35);">Subscribe to the Daily Market Analysis &amp; Sector Report →</a></div>
<h2>Conclusion</h2>
<p>Today's {score}/100 sits in the "{regime}" band. As always, the headline number is a summary, not a substitute for reading which specific factors actually moved — that's what the table above is for.</p>
<p style="font-size:12px;color:#999;text-align:center;">Disclaimer: This report is for informational and educational purposes only and does not constitute investment advice. Please consult a licensed financial advisor before making any investment decisions.</p>"""

    heading = f"Decoded: Daily Market Analysis & Sector Report — {_fmt_date(date_str)} (Score: {score}/100, {regime})"
    return heading, story


def build_weekly_article(week_snapshots, today, chart_url, holidays=None):
    holidays = holidays or {}
    dates_sorted = sorted(week_snapshots.keys())
    week_table_rows = []
    prev_score = None
    for d in dates_sorted:
        snap = week_snapshots.get(d)
        wd = datetime.strptime(d, '%Y-%m-%d').strftime('%a')
        if snap:
            change = f'{snap["score"] - prev_score:+d}' if prev_score is not None else '—'
            week_table_rows.append([f'{wd}, {_fmt_date(d)}', str(snap['score']), snap['regime'], change])
            prev_score = snap['score']
        elif d in holidays:
            week_table_rows.append([f'{wd}, {_fmt_date(d)}', f'Market Holiday — {holidays[d]}', '—', '—'])
        else:
            week_table_rows.append([f'{wd}, {_fmt_date(d)}', 'no archived data', '—', '—'])

    score, regime = today['score'], today['regime']
    factor_rows_data, biggest_label, biggest_delta = build_factor_rows(today, None)
    trending_rows_data = picks_rows(today.get('picks', {}).get('trending', {}))
    quality_rows_data = picks_rows(today.get('picks', {}).get('quality', {}))
    risk_alerts = today.get('risk_alerts', [])
    risk_html = ('<ul style="line-height:1.9;">' + ''.join(f'<li>{r}</li>' for r in risk_alerts) + '</ul>') \
        if risk_alerts else '<p>No risk alerts today.</p>'

    story = f"""<p>This week's Daily Market Analysis &amp; Sector Report moved between several regimes. Rather than decode just today in isolation, here's VilfinTV's full weekly view: the trajectory, what moved most recently, and where things stand now.</p>
<h2>The Week at a Glance</h2>
{img(chart_url, "Daily market sentiment score, weekly bar chart")}
{table(["Day", "Score", "Regime", "Change from Previous"], week_table_rows)}
<h2>Today's Headline Number: {score}/100 — "{regime}"</h2>
{table(["Score Range", "Regime Label", "What It Broadly Means"], regime_rows(score))}
<h2>⚠️ Risk Alerts</h2>
{risk_html}
<h2>Today's 14-Factor Breakdown</h2>
{table(["Factor", "What It Actually Showed", "Points", "Consider or Ignore?"], factor_rows_data)}
<h2>Where the Report Says to Look: Region &amp; Sectors</h2>
<p><strong>Regional pick:</strong> {today.get('regional_rec','n/a')}</p>
<p><strong>Momentum sector:</strong> {today.get('momentum_sector','n/a')} &nbsp;|&nbsp; <strong>Value sector:</strong> {today.get('value_sector','n/a')} &nbsp;|&nbsp; <strong>Long-term pick:</strong> {today.get('long_term_sector','n/a')}</p>
<h2>Trending Picks: What's Moving Right Now</h2>
{table(["Asset Class", "Pick"], trending_rows_data)}
<h2>Quality Picks: What's Been Consistent</h2>
{table(["Asset Class", "Pick"], quality_rows_data)}
<h2>Notable Currency Mover</h2>
<p>{today.get('notable_fx_mover', 'None flagged today.')}</p>
<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:14px 16px;margin:18px 0;"><p style="margin:0;font-size:14px;color:#7c2d12;"><strong>⚠️ Do your own homework first.</strong> Everything above is a data-driven starting point, not a finish line. Verify the numbers yourself and size any position to your own risk tolerance before acting on any pick in this report.</p></div>
<h2>How to Actually Act on This</h2>
<ul style="line-height:1.9;"><li><strong>For Indian market exposure:</strong> <a href="https://zerodha.com/open-account?c=XKQ288">Zerodha</a> or <a href="https://join.dhan.co/?invite=VFZJN04428">Dhan</a>.</li><li><strong>For index funds/ETFs:</strong> <a href="https://kuvera.in/s/wsapp?referral=1T6BH">Kuvera</a>, direct plans, zero commission.</li><li><strong>For frequent trading:</strong> <a href="https://prostocks.com/open-an-account?ref=G1392">ProStocks</a>' flat-fee plan.</li><li><strong>For broader global market access:</strong> <a href="https://www.interactivebrokers.co.jp/en/accounts/what-you-need-jp.php">Interactive Brokers</a>.</li></ul>
<p style="font-size:12.5px;color:#888;"><em>🎁 Using the referral links above benefits you at no extra cost.</em></p>
<h2>Get This Report Every Morning — Completely Free</h2>
<p>This full breakdown lands in your inbox every trading day morning, before 9:00 AM JST. <strong>Subscribing is completely free.</strong> Weeks like this one are exactly why reading the report daily, not just once, is what actually shows you whether a move is a trend or a blip.</p>
<div style="text-align:center;margin:16px 0;"><a href="https://vilfintv.com/manage_subscription.html?action=subscribe" style="display:inline-block;background:#16a34a;color:#ffffff;font-weight:bold;font-size:15px;padding:12px 28px;border-radius:24px;text-decoration:none;box-shadow:0 4px 12px rgba(22,163,74,0.35);">Subscribe to the Daily Market Analysis &amp; Sector Report →</a></div>
<h2>Conclusion</h2>
<p>The week closes at {score}/100, "{regime}." Reading the daily reports side by side over the week, rather than glancing at any single day's number, is what actually reveals whether this week's moves reflect a real shift or ordinary day-to-day noise.</p>
<p style="font-size:12px;color:#999;text-align:center;">Disclaimer: This report is for informational and educational purposes only and does not constitute investment advice. Please consult a licensed financial advisor before making any investment decisions.</p>"""

    heading = f"Weekly Decode: Daily Market Analysis & Sector Report — {_fmt_date(today['date'])} (Score: {score}/100, {regime})"
    return heading, story


def _fmt_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%B %d, %Y')


def _fmt_date_short(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%b %d')


def main():
    now_jst = datetime.now(JST)
    weekday = now_jst.weekday()  # Monday=0 ... Sunday=6
    holidays = load_holidays()

    if weekday == 6:
        print('Sunday — no report (Indian/US markets closed since Saturday, no new data). Exiting cleanly.')
        return

    with open(SNAPSHOT_FILE, encoding='utf-8') as f:
        today = json.load(f)

    date_str = today['date']
    is_weekend_report = (weekday == 5)  # Saturday

    if not is_weekend_report and date_str in holidays:
        print(f"{date_str} is an NSE trading holiday ({holidays[date_str]}) — no report. Exiting cleanly.")
        return

    if is_weekend_report:
        week_snapshots = get_recent_snapshots(days_back=8)
        # Ensure exactly the trailing 7 calendar days incl. today are represented,
        # even if some have no archived snapshot (shown as a gap, not fabricated).
        full_week = {}
        for i in range(6, -1, -1):
            d = (now_jst - timedelta(days=i)).strftime('%Y-%m-%d')
            full_week[d] = week_snapshots.get(d)
        chart_path = f'/tmp/weekly_score_chart_{date_str}.png'
        week_rows_for_chart = []
        for d in sorted(full_week.keys()):
            snap = full_week[d]
            wd = datetime.strptime(d, '%Y-%m-%d').strftime('%a')
            gap_reason = 'holiday' if (not snap and d in holidays) else None
            week_rows_for_chart.append((f'{wd}\n{_fmt_date_short(d)}', snap['score'] if snap else None, gap_reason))
        make_chart_weekly(week_rows_for_chart, chart_path)
        chart_key = f'{R2_PREFIX}/weekly-market-report-{date_str}-score-chart.jpg'
        chart_url = f'{PUBLIC_R2_BASE}/weekly-market-report-{date_str}-score-chart.jpg'
        heading, story = build_weekly_article(full_week, today, chart_url, holidays)
    else:
        prev_snapshots = get_recent_snapshots(days_back=5)
        prev_dates = sorted([d for d in prev_snapshots if d < date_str], reverse=True)
        prev = prev_snapshots[prev_dates[0]] if prev_dates else None
        chart_path = f'/tmp/daily_market_report_{date_str}_chart.png'
        make_chart_weekday(today, prev, chart_path)
        chart_key = f'{R2_PREFIX}/daily-market-report-{date_str}-chart.jpg'
        chart_url = f'{PUBLIC_R2_BASE}/daily-market-report-{date_str}-chart.jpg'
        heading, story = build_weekday_article(today, prev, chart_url)

    assert HERO_URL not in story, 'hero photo URL duplicated in story body'

    print(f'CHART_LOCAL_PATH={chart_path}')
    print(f'CHART_R2_KEY={chart_key}')
    print(f'HEADING={heading}')
    print(f'STORY_LENGTH={len(story)}')
    print(f'TABLE_COUNT={story.count("<table")}')

    if DRY_RUN:
        with open(f'/tmp/dry_run_article_{date_str}.html', 'w', encoding='utf-8') as f:
            f.write(f'<h1>{heading}</h1>\n{story}')
        print(f'[DRY RUN] Article saved to /tmp/dry_run_article_{date_str}.html — content.json NOT modified, chart NOT uploaded.')
        return

    with open(CONTENT_FILE, encoding='utf-8') as f:
        data = json.load(f)

    new_item = {
        'id': str(int(time.time() * 1000)),
        'section': 'stock',
        'heading': heading,
        'story': story,
        'photo': HERO_URL,
        'published_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
    }
    assert new_item['photo'] not in new_item['story']
    data.append(new_item)

    with open(CONTENT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f'PUBLISHED_ID={new_item["id"]}')


if __name__ == '__main__':
    main()
