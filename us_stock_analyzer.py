import os
import json
import logging
import pandas as pd
from datetime import datetime
from screener_shared import (
    jst_today_str,
    _valid,
    _minify_html,
    fetch_asset_data,
    fetch_bulk_data,
    calc_growth_score,
    calc_value_score,
    calc_momentum_score,
    calc_quality_score,
    _quality_alignment_count,
    rank_by_lt_score,
    get_quality_pick,
    calc_rsi,
    calc_risk_adjusted_return,
    send_email
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_sp500_symbols():
    """Fetch S&P 500 constituents from Wikipedia with JSON fallback."""
    try:
        tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = tables[0]
        symbols = []
        for _, row in df.iterrows():
            sym = row['Symbol'].replace('.', '-')
            symbols.append({
                'symbol': sym,
                'name': row['Security'],
                'sector': row['GICS Sector'],
                'sub_industry': row['GICS Sub-Industry']
            })
        logging.info(f"Fetched {len(symbols)} S&P 500 symbols from Wikipedia")
        return symbols
    except Exception as e:
        logging.warning(f"Wikipedia fetch failed: {e}, using fallback")
        try:
            with open('data/sp500_symbols.json') as f:
                symbols = json.load(f)
                logging.info(f"Fetched {len(symbols)} S&P 500 symbols from fallback JSON")
                return symbols
        except Exception as ex:
            logging.error(f"Both Wikipedia and fallback failed: {ex}")
            return []

def get_top_gainers(data, n=10):
    valid = {k: v for k, v in data.items() if _valid(v.get('change'))}
    return sorted(valid.items(), key=lambda x: x[1]['change'], reverse=True)[:n]

def get_top_losers(data, n=10):
    valid = {k: v for k, v in data.items() if _valid(v.get('change'))}
    return sorted(valid.items(), key=lambda x: x[1]['change'])[:n]

def get_momentum_leaders(data, n=5):
    valid = {}
    for k, v in data.items():
        if _valid(v.get('change')) and _valid(v.get('price')) and _valid(v.get('ma_20')):
            if v['change'] > 0 and v['price'] > v['ma_20']:
                valid[k] = v
    ranked = sorted(valid.items(), key=lambda x: calc_momentum_score(x[1]), reverse=True)
    return ranked[:n]

def get_value_opportunities(data, n=5):
    valid = {}
    for k, v in data.items():
        score = calc_value_score(v)
        if score > -9999:
            valid[k] = v
    ranked = sorted(valid.items(), key=lambda x: calc_value_score(x[1]), reverse=True)
    return ranked[:n]

def get_quality_champions(data, n=5):
    valid = {k: v for k, v in data.items() if _valid(v.get('ma_20')) and _valid(v.get('ma_50'))}
    ranked = sorted(valid.items(), key=lambda x: calc_quality_score(x[1]), reverse=True)
    return ranked[:n]

def get_long_term_winners(data, n=5):
    ranked = rank_by_lt_score(data)
    return ranked[:n]

def get_rsi_alerts(data):
    alerts = {'overbought': [], 'oversold': []}
    for k, v in data.items():
        rsi = v.get('rsi_14')
        if _valid(rsi):
            if rsi > 70:
                alerts['overbought'].append((k, v))
            elif rsi < 30:
                alerts['oversold'].append((k, v))
    alerts['overbought'] = sorted(alerts['overbought'], key=lambda x: x[1]['rsi_14'], reverse=True)
    alerts['oversold'] = sorted(alerts['oversold'], key=lambda x: x[1]['rsi_14'])
    return alerts

def get_volume_surges(data, n=10):
    valid = {}
    for k, v in data.items():
        vol = v.get('volume')
        avg_vol = v.get('avg_volume_20')
        if _valid(vol) and _valid(avg_vol) and avg_vol > 0:
            if vol > 2 * avg_vol:
                valid[k] = v
    ranked = sorted(valid.items(), key=lambda x: x[1]['volume'] / x[1]['avg_volume_20'], reverse=True)
    return ranked[:n]

def get_52w_breakouts(data, n=10):
    valid = {}
    for k, v in data.items():
        price = v.get('price')
        high52 = v.get('high_52w')
        if _valid(price) and _valid(high52) and high52 > 0:
            if price >= high52 * 0.98:
                valid[k] = v
    ranked = sorted(valid.items(), key=lambda x: (x[1]['price'] / x[1]['high_52w']), reverse=True)
    return ranked[:n]

def get_sector_rotation(data):
    sectors = {}
    for k, v in data.items():
        sector = v.get('sector', 'Unknown')
        change = v.get('change')
        if _valid(change):
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(change)
    
    avg_perf = []
    for sector, changes in sectors.items():
        avg = sum(changes) / len(changes)
        avg_perf.append((sector, avg))
        
    return sorted(avg_perf, key=lambda x: x[1], reverse=True)

def get_relative_strength(data, n=10):
    valid = {}
    for k, v in data.items():
        price = v.get('price')
        ma_50 = v.get('ma_50')
        if _valid(price) and _valid(ma_50) and ma_50 > 0:
            rs = ((price / ma_50) - 1) * 100
            valid[k] = v
    ranked = sorted(valid.items(), key=lambda x: ((x[1]['price'] / x[1]['ma_50']) - 1) * 100, reverse=True)
    return ranked[:n]

def get_market_overview(data):
    overview = {
        'advancers': 0,
        'decliners': 0,
        'unchanged': 0,
        'sp500_level': None,
        'sp500_change': None
    }
    
    for k, v in data.items():
        change = v.get('change')
        if _valid(change):
            if change > 0:
                overview['advancers'] += 1
            elif change < 0:
                overview['decliners'] += 1
            else:
                overview['unchanged'] += 1
                
    sp500 = fetch_asset_data('^GSPC')
    if sp500:
        overview['sp500_level'] = sp500.get('price')
        overview['sp500_change'] = sp500.get('change')
        
    return overview

def generate_html_email(overview, gainers, losers, momentum, value, quality, lt_winners, rsi_alerts, vol_surges, breakouts, sector_rot, rel_strength, stock_data):
    html = f"""<html><head><style>
body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
h2 {{ color: #0a192f; margin-top: 30px; }}
h3 {{ color: #1a365d; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.95em; background-color: white; }}
th, td {{ padding: 8px; border: 1px solid #ddd; text-align: center; }}
th {{ background-color: #f4f4f4; }}
.l {{ text-align: left; }}
.c {{ text-align: center; }}
.a {{ text-align: left; font-weight: bold; width: 25%; }}
.u {{ text-align: center; color: #666; font-size: 0.9em; }}
.p {{ color: green; font-weight: bold; }}
.n {{ color: red; font-weight: bold; }}
.score-box {{ padding: 20px; background: #eef2f5; border-left: 5px solid #0a192f; margin-bottom: 20px; }}
.alerts {{ background: #fff3f3; border-left: 5px solid #d9534f; padding: 15px; }}
.recommendation {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #16a34a; padding: 15px; margin-top: 15px; }}
.st-momentum {{ background: #fffbeeb3; border: 1px solid #fde68a; border-left: 5px solid #d97706; padding: 15px; margin-top: 15px; }}
.summary-item {{ margin-bottom: 8px; }}
.reasoning {{ font-size: 0.9em; color: #555; margin-left: 20px; }}
.bar-wrap {{ width: 100%; background-color: #eee; border-radius: 4px; overflow: hidden; height: 10px; margin-top: 5px; }}
.bar-fill {{ height: 100%; }}
</style></head><body>

<div style="text-align: center; margin-bottom: 20px;">
    <h1 style="color: #0a192f; margin: 0;">VilfinTV S&P 500 Daily Stock Report</h1>
    <div style="color: #666; font-size: 1.1em; margin-top: 5px;">{jst_today_str()} (JST)</div>
</div>

<div class="score-box">
    <h2 style="margin-top: 0;">Market Overview</h2>
"""
    
    if _valid(overview.get('sp500_level')):
        lvl = overview['sp500_level']
        chg = overview['sp500_change']
        c_class = 'p' if chg > 0 else 'n'
        c_sign = '+' if chg > 0 else ''
        html += f"""
        <div style="font-size: 1.5em; font-weight: bold; margin-bottom: 15px;">
            S&P 500: {lvl:,.2f} <span class="{c_class}">({c_sign}{chg:.2f}%)</span>
        </div>
        """

    total = overview['advancers'] + overview['decliners'] + overview['unchanged']
    if total > 0:
        adv_pct = (overview['advancers'] / total) * 100
        dec_pct = (overview['decliners'] / total) * 100
        html += f"""
        <div>
            <strong>Market Breadth (S&P 500):</strong> {overview['advancers']} Advancers / {overview['decliners']} Decliners
            <div style="width: 100%; height: 20px; background-color: #eee; display: flex; border-radius: 4px; overflow: hidden; margin-top: 8px;">
                <div style="width: {adv_pct}%; background-color: #28a745;" title="Advancers"></div>
                <div style="width: {dec_pct}%; background-color: #dc3545;" title="Decliners"></div>
            </div>
        </div>
        """
        
    html += "</div>"
    
    # Gainers & Losers
    html += """
    <table style="border: none; background: transparent;"><tr>
    <td style="vertical-align: top; border: none; padding: 0 10px 0 0; width: 50%;">
        <h3>Top 10 Gainers</h3>
        <table>
            <tr><th>Symbol</th><th>Name</th><th>Price</th><th>Change</th></tr>
    """
    for sym, m in gainers:
        chg = m.get('change', 0)
        c_class = 'p' if chg > 0 else 'n'
        c_sign = '+' if chg > 0 else ''
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:20]}</td><td>{m.get('price', 0):.2f}</td><td class='{c_class}'>{c_sign}{chg:.2f}%</td></tr>"
    
    html += """
        </table>
    </td>
    <td style="vertical-align: top; border: none; padding: 0 0 0 10px; width: 50%;">
        <h3>Top 10 Losers</h3>
        <table>
            <tr><th>Symbol</th><th>Name</th><th>Price</th><th>Change</th></tr>
    """
    for sym, m in losers:
        chg = m.get('change', 0)
        c_class = 'p' if chg > 0 else 'n'
        c_sign = '+' if chg > 0 else ''
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:20]}</td><td>{m.get('price', 0):.2f}</td><td class='{c_class}'>{c_sign}{chg:.2f}%</td></tr>"
    html += "</table></td></tr></table>"

    # Momentum Leaders
    html += """<h2>Momentum Leaders</h2>
    <table><tr><th>Symbol</th><th>Name</th><th>Score</th><th>Price</th><th>Change</th><th>vs 20MA</th></tr>"""
    for sym, m in momentum:
        score = calc_momentum_score(m)
        chg = m.get('change', 0)
        c_class = 'p' if chg > 0 else 'n'
        c_sign = '+' if chg > 0 else ''
        vs_20 = ((m.get('price', 0) / m.get('ma_20', 1)) - 1) * 100
        v_class = 'p' if vs_20 > 0 else 'n'
        v_sign = '+' if vs_20 > 0 else ''
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:25]}</td><td>{score:.1f}</td><td>{m.get('price', 0):.2f}</td><td class='{c_class}'>{c_sign}{chg:.2f}%</td><td class='{v_class}'>{v_sign}{vs_20:.2f}%</td></tr>"
    html += "</table>"
    
    # Value Opportunities
    html += """<h2>Value Opportunities</h2>
    <table><tr><th>Symbol</th><th>Name</th><th>Score</th><th>Price</th><th>Change</th><th>vs 50MA</th></tr>"""
    for sym, m in value:
        score = calc_value_score(m)
        chg = m.get('change', 0)
        c_class = 'p' if chg > 0 else 'n'
        c_sign = '+' if chg > 0 else ''
        vs_50 = ((m.get('price', 0) / m.get('ma_50', 1)) - 1) * 100
        v_class = 'p' if vs_50 > 0 else 'n'
        v_sign = '+' if vs_50 > 0 else ''
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:25]}</td><td>{score:.1f}</td><td>{m.get('price', 0):.2f}</td><td class='{c_class}'>{c_sign}{chg:.2f}%</td><td class='{v_class}'>{v_sign}{vs_50:.2f}%</td></tr>"
    html += "</table>"
    
    # Quality Champions
    html += """<h2>Quality Champions</h2>
    <table><tr><th>Symbol</th><th>Name</th><th>Score</th><th>Alignment</th><th>Price</th><th>YTD</th></tr>"""
    for sym, m in quality:
        score = calc_quality_score(m)
        aligned = _quality_alignment_count(m)
        ytd = m.get('ytd_return') or 0
        y_class = 'p' if ytd > 0 else 'n'
        y_sign = '+' if ytd > 0 else ''
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:25]}</td><td>{score:.1f}</td><td>{aligned}/5</td><td>{m.get('price', 0):.2f}</td><td class='{y_class}'>{y_sign}{ytd:.2f}%</td></tr>"
    html += "</table>"
    
    # Long Term Winners
    html += """<h2>Long-Term Winners</h2>
    <table><tr><th>Symbol</th><th>Name</th><th>Price</th><th>YTD</th><th>3Y Return</th></tr>"""
    for sym, m in lt_winners:
        ytd = m.get('ytd_return') or 0
        y_class = 'p' if ytd > 0 else 'n'
        y_sign = '+' if ytd > 0 else ''
        tyr = m.get('three_yr_return') or 0
        t_class = 'p' if tyr > 0 else 'n'
        t_sign = '+' if tyr > 0 else ''
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:25]}</td><td>{m.get('price', 0):.2f}</td><td class='{y_class}'>{y_sign}{ytd:.2f}%</td><td class='{t_class}'>{t_sign}{tyr:.2f}%</td></tr>"
    html += "</table>"

    # Relative Strength
    html += """<h2>Relative Strength (vs 50MA proxy)</h2>
    <table><tr><th>Symbol</th><th>Name</th><th>Price</th><th>vs 50MA</th></tr>"""
    for sym, m in rel_strength:
        rs = ((m.get('price', 0) / m.get('ma_50', 1)) - 1) * 100
        r_class = 'p' if rs > 0 else 'n'
        r_sign = '+' if rs > 0 else ''
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:25]}</td><td>{m.get('price', 0):.2f}</td><td class='{r_class}'>{r_sign}{rs:.2f}%</td></tr>"
    html += "</table>"
    
    # RSI Alerts
    html += """<h2>RSI Alerts</h2>
    <div style="display: flex; gap: 20px;">
    <div style="flex: 1;">
        <h3 style="color: #d9534f;">Overbought (RSI > 70)</h3>
        <table><tr><th>Symbol</th><th>RSI</th></tr>"""
    for sym, m in rsi_alerts['overbought'][:10]:
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td>{m.get('rsi_14', 0):.1f}</td></tr>"
    html += """</table>
    </div>
    <div style="flex: 1;">
        <h3 style="color: #16a34a;">Oversold (RSI < 30)</h3>
        <table><tr><th>Symbol</th><th>RSI</th></tr>"""
    for sym, m in rsi_alerts['oversold'][:10]:
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td>{m.get('rsi_14', 0):.1f}</td></tr>"
    html += """</table>
    </div>
    </div>"""

    # Volume Surges
    html += """<h2>Volume Surges</h2>
    <table><tr><th>Symbol</th><th>Name</th><th>Price</th><th>Change</th><th>Volume vs Avg</th></tr>"""
    for sym, m in vol_surges:
        chg = m.get('change', 0)
        c_class = 'p' if chg > 0 else 'n'
        c_sign = '+' if chg > 0 else ''
        vol_ratio = m.get('volume', 0) / m.get('avg_volume_20', 1)
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:25]}</td><td>{m.get('price', 0):.2f}</td><td class='{c_class}'>{c_sign}{chg:.2f}%</td><td>{vol_ratio:.1f}x</td></tr>"
    html += "</table>"

    # 52W Breakouts
    html += """<h2>52-Week Breakout Candidates</h2>
    <table><tr><th>Symbol</th><th>Name</th><th>Price</th><th>52W High</th><th>Distance</th></tr>"""
    for sym, m in breakouts:
        p = m.get('price', 0)
        h = m.get('high_52w', 1)
        dist = ((p / h) - 1) * 100
        html += f"<tr><td class='l'><strong>{sym}</strong></td><td class='l'>{m.get('name', '')[:25]}</td><td>{p:.2f}</td><td>{h:.2f}</td><td>{dist:.2f}%</td></tr>"
    html += "</table>"

    # Sector Rotation
    html += """<h2>Sector Rotation Heatmap</h2>
    <table><tr><th>Sector</th><th>Avg Change %</th><th>Trend</th></tr>"""
    for sec, chg in sector_rot:
        c_class = 'p' if chg > 0 else 'n'
        c_sign = '+' if chg > 0 else ''
        bar_color = '#28a745' if chg > 0 else '#dc3545'
        bar_width = min(100, abs(chg) * 20)
        html += f"""<tr>
            <td class='l'>{sec}</td>
            <td class='{c_class}'>{c_sign}{chg:.2f}%</td>
            <td class='l'>
                <div style='width: 100px; height: 12px; background: #eee; border-radius: 2px; overflow: hidden;'>
                    <div style='width: {bar_width}px; height: 100%; background: {bar_color}; {"margin-left: 0;" if chg > 0 else "float: right;"}'></div>
                </div>
            </td>
        </tr>"""
    html += "</table>"
    
    # Full Dashboard grouped by Sector
    html += "<h2>Full S&P 500 Dashboard</h2>"
    
    # Group stocks by sector
    by_sector = {}
    for sym, m in stock_data.items():
        sec = m.get('sector', 'Unknown')
        if sec not in by_sector:
            by_sector[sec] = []
        by_sector[sec].append((sym, m))
        
    for sec in sorted(by_sector.keys()):
        html += f"<h3>{sec}</h3>"
        html += """<table>
        <tr><th>Stock</th><th>Symbol</th><th>Price</th><th>Change</th><th>50MA</th><th>RSI</th><th>YTD%</th><th>3Y%</th></tr>"""
        
        sec_stocks = sorted(by_sector[sec], key=lambda x: x[1].get('change', 0), reverse=True)
        for sym, m in sec_stocks:
            chg = m.get('change', 0)
            c_class = 'p' if chg > 0 else 'n'
            c_sign = '+' if chg > 0 else ''
            
            ytd = m.get('ytd_return') or 0
            y_class = 'p' if ytd > 0 else 'n'
            y_sign = '+' if ytd > 0 else ''
            
            tyr = m.get('three_yr_return') or 0
            t_class = 'p' if tyr > 0 else 'n'
            t_sign = '+' if tyr > 0 else ''
            
            html += f"""<tr>
                <td class='l'>{m.get('name', '')[:20]}</td>
                <td><strong>{sym}</strong></td>
                <td>{m.get('price', 0):.2f}</td>
                <td class='{c_class}'>{c_sign}{chg:.2f}%</td>
                <td>{m.get('ma_50', 0):.2f}</td>
                <td>{m.get('rsi_14') or 0:.1f}</td>
                <td class='{y_class}'>{y_sign}{ytd:.2f}%</td>
                <td class='{t_class}'>{t_sign}{tyr:.2f}%</td>
            </tr>"""
        html += "</table>"

    # Broker Links and footer
    html += """
    <div style="margin-top: 40px; padding: 20px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; font-family: sans-serif;">
        <h3 style="margin-top: 0; color: #16a34a; text-align: center;">🌐 International Money Transfer Apps</h3>
        <p style="margin-bottom: 20px; color: #555; text-align: center; font-size: 0.95em;">🎁 Sign up via these referral links for bonus rates, cashback, or rewards at no extra cost.</p>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.85em;">
            <tr>
                <td style="width: 33.3%; padding: 14px; vertical-align: top; background: white; border-radius: 6px 0 0 6px;">
                    <div style="font-weight: bold; color: #0a192f; font-size: 1.05em; margin-bottom: 4px;">🌍 Revolut</div>
                    <div style="color: #888; font-size: 0.85em; margin-bottom: 10px;">All-in-one: banking, investing &amp; travel</div>
                    <div style="line-height: 1.9; color: #333;">
                        ✅ Currency exchange (36+ currencies)<br>
                        ✅ Debit card (free Standard plan)<br>
                        ✅ Digital gold &amp; silver (from $1)<br>
                        ✅ Built-in eSIM for travel data<br>
                        ✅ Cashback up to 1%
                    </div>
                    <a href="https://revolut.com/referral/?referral-code=vilfingeorge!APR1-26-AR-JP-H1&geo-redirect" style="display: inline-block; margin-top: 12px; color: #16a34a; font-weight: bold; text-decoration: none;">Join Revolut →</a>
                </td>
                <td style="width: 33.3%; padding: 14px; vertical-align: top; background: white; border-left: 1px solid #eee;">
                    <div style="font-weight: bold; color: #0a192f; font-size: 1.05em; margin-bottom: 4px;">💚 Wise (TransferWise)</div>
                    <div style="color: #888; font-size: 0.85em; margin-bottom: 10px;">Best true mid-market exchange rate</div>
                    <div style="line-height: 1.9; color: #333;">
                        ✅ Currency exchange (40+ currencies, ~0% markup)<br>
                        ✅ Debit card (Apple/Google Pay)<br>
                        ❌ No digital gold/silver<br>
                        ❌ No eSIM<br>
                        ❌ No cashback program
                    </div>
                    <a href="https://wise.com/invite/ihpc/vilfinm" style="display: inline-block; margin-top: 12px; color: #16a34a; font-weight: bold; text-decoration: none;">Join Wise →</a>
                </td>
                <td style="width: 33.3%; padding: 14px; vertical-align: top; background: white; border-left: 1px solid #eee; border-radius: 0 6px 6px 0;">
                    <div style="font-weight: bold; color: #0a192f; font-size: 1.05em; margin-bottom: 4px;">⚡ Instarem</div>
                    <div style="color: #888; font-size: 0.85em; margin-bottom: 10px;">Straightforward remittances, strong Asia rates</div>
                    <div style="line-height: 1.9; color: #333;">
                        ✅ Currency exchange (60+ countries)<br>
                        ✅ Amaze debit card (11 currencies)<br>
                        ❌ No digital gold/silver<br>
                        ❌ No eSIM<br>
                        ✅ InstaPoints on every transfer
                    </div>
                    <a href="https://referral-link.onelink.me/gbf1/a43c48ca?deep_link_sub1=referral&deep_link_value=cWkMb3" style="display: inline-block; margin-top: 12px; color: #16a34a; font-weight: bold; text-decoration: none;">Join Instarem →</a> <span style="font-size: 0.8em; color: #888;">(code cWkMb3)</span>
                </td>
            </tr>
        </table>
    </div>

    <div style="margin-top: 24px; padding: 20px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; font-family: sans-serif;">
        <h3 style="margin-top: 0; color: #16a34a; text-align: center;">📈 Stock Brokers</h3>
        <p style="margin-bottom: 20px; color: #555; text-align: center; font-size: 0.95em;">🎁 Using the referral links below benefits you at no extra cost.</p>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.85em;">
            <tr>
                <td style="width: 33.3%; padding: 14px; vertical-align: top; background: white; border-radius: 6px 0 0 6px;">
                    <div style="font-weight: bold; color: #0a192f; font-size: 1.05em; margin-bottom: 4px;">🟢 Zerodha</div>
                    <div style="color: #888; font-size: 0.85em; margin-bottom: 10px;">India's largest broker</div>
                    <div style="line-height: 1.9; color: #333;">
                        ✅ Stocks (India), ETFs, Bonds<br>
                        ✅ Commodities (MCX) &amp; currency derivatives<br>
                        ✅ Mutual funds — Coin, 2000+ direct funds<br>
                        ✅ Market reports — free Varsity research<br>
                        🔜 US stocks — announced, not yet live
                    </div>
                    <a href="https://zerodha.com/open-account?c=XKQ288" style="display: inline-block; margin-top: 12px; color: #16a34a; font-weight: bold; text-decoration: none;">Open Zerodha →</a>
                </td>
                <td style="width: 33.3%; padding: 14px; vertical-align: top; background: white; border-left: 1px solid #eee;">
                    <div style="font-weight: bold; color: #0a192f; font-size: 1.05em; margin-bottom: 4px;">🔥 Dhan</div>
                    <div style="color: #888; font-size: 0.85em; margin-bottom: 10px;">India + US in one account</div>
                    <div style="line-height: 1.9; color: #333;">
                        ✅ Stocks — India, plus live US stocks (GIFT City)<br>
                        ✅ ETFs, Bonds/NCDs, Commodities &amp; currency derivatives<br>
                        ✅ Mutual funds — direct, 0% commission<br>
                        ✅ Market reports — Pre/Post-Market Insights
                    </div>
                    <a href="https://join.dhan.co/?invite=VFZJN04428" style="display: inline-block; margin-top: 12px; color: #16a34a; font-weight: bold; text-decoration: none;">Open Dhan →</a>
                </td>
                <td style="width: 33.3%; padding: 14px; vertical-align: top; background: white; border-left: 1px solid #eee; border-radius: 0 6px 6px 0;">
                    <div style="font-weight: bold; color: #0a192f; font-size: 1.05em; margin-bottom: 4px;">💹 ProStocks</div>
                    <div style="color: #888; font-size: 0.85em; margin-bottom: 10px;">India's flat-fee specialist — cheapest for high-volume traders</div>
                    <div style="line-height: 1.9; color: #333;">
                        ✅ Stocks, ETFs, Bonds/Debt &amp; currency derivatives<br>
                        ✅ ₹0 delivery, ₹15/order flat, or ₹899/month unlimited equity+F&amp;O<br>
                        ✅ ₹0 AMC for life · NRI accounts (₹100/order PIS, ₹40/order NRO)<br>
                        ✅ Mutual funds — can be held via demat (no direct purchase platform)<br>
                        ❌ No commodities (MCX/NCDEX), no research/market reports
                    </div>
                    <a href="https://prostocks.com/open-an-account?ref=G1392" style="display: inline-block; margin-top: 12px; color: #16a34a; font-weight: bold; text-decoration: none;">Open ProStocks →</a>
                </td>
            </tr>
        </table>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.85em; margin-top: 10px;">
            <tr>
                <td style="padding: 14px; vertical-align: top; background: white; border-radius: 6px;">
                    <div style="font-weight: bold; color: #0a192f; font-size: 1.05em; margin-bottom: 4px;">🌐 Interactive Brokers</div>
                    <div style="color: #888; font-size: 0.85em; margin-bottom: 10px;">Global markets, incl. Japan NISA</div>
                    <div style="line-height: 1.9; color: #333;">
                        ✅ Stocks/ETFs/Bonds/Funds — 170 markets, 40 countries<br>
                        ✅ Commodities/futures &amp; currency exchange (100+ pairs)<br>
                        ✅ Japan NISA (IBKR Securities Japan, since 2025)<br>
                        ✅ English interface · GlobalAnalyst/Morningstar/Zacks
                    </div>
                    <a href="https://www.interactivebrokers.co.jp/en/accounts/what-you-need-jp.php" style="display: inline-block; margin-top: 12px; color: #16a34a; font-weight: bold; text-decoration: none;">Open IBKR →</a>
                </td>
            </tr>
        </table>
    </div>

    <div style="margin-top: 24px; padding: 20px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; font-family: sans-serif;">
        <h3 style="margin-top: 0; color: #16a34a; text-align: center;">🏦 Bonds, Mutual Funds &amp; Digital Gold</h3>
        <table style="width: 100%; border: none; font-size: 0.9em; background: transparent;">
            <tr>
                <td style="width: 50%; padding: 10px; vertical-align: top; border: none; text-align: left;">
                    <div style="background: white; padding: 15px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <strong style="color: #0a192f;">🏦 Bonds & Mutual Funds (India)</strong><br><br>
                        • <a href="https://kuvera.in/s/wsapp?referral=1T6BH" style="color: #16a34a; text-decoration: none; font-weight: bold;">Kuvera MFs</a> (Code: <strong>1T6BH</strong> — 2000+ direct funds, 0% commission)<br>
                        • <a href="https://www.indiabonds.com/referral/CiY7ZAAt" style="color: #16a34a; text-decoration: none; font-weight: bold;">IndiaBonds</a><br>
                        • <a href="https://goldenpi.com/sign-up?referrer=SRVL1503290" style="color: #16a34a; text-decoration: none; font-weight: bold;">GoldenPi</a> (bonds up to ~14% p.a.)<br>
                        • <a href="https://www.wintwealth.com/bonds/referral/invite?referralCode=3AC7AF" style="color: #16a34a; text-decoration: none; font-weight: bold;">Wint Wealth</a>
                    </div>
                </td>
                <td style="width: 50%; padding: 10px; vertical-align: top; border: none; text-align: left;">
                    <div style="background: white; padding: 15px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <strong style="color: #0a192f;">💰 Digital Gold, Silver, UPI &amp; Mutual Funds</strong><br><br>
                        • <a href="https://m.navi.com/X7g9gpUzoKb" style="color: #16a34a; text-decoration: none; font-weight: bold;">Navi</a> (own direct low-cost MF + Digital Gold only, no silver)<br>
                        • <a href="https://phon.pe/772mkuqo" style="color: #16a34a; text-decoration: none; font-weight: bold;">PhonePe</a> (Gold &amp; Silver + Regular MF, not direct)
                    </div>
                </td>
            </tr>
        </table>
    </div>

    <div style="margin-top: 40px; padding: 20px; background-color: #f8f9fa; border-top: 2px solid #e9ecef; border-radius: 8px; text-align: center; font-family: sans-serif;">
        <div style="margin-top: 25px; padding-top: 20px; border-top: 1px solid #dee2e6;">
            <a href="https://vilfintv.com/manage_subscription.html?action=subscribe" style="color: #1a0dab; text-decoration: none; margin: 0 15px; font-size: 0.9em;">Subscribe to this Newsletter</a>
            <a href="https://vilfintv.com/manage_subscription.html?action=unsubscribe" style="color: #6c757d; text-decoration: none; margin: 0 15px; font-size: 0.9em;">Unsubscribe</a>
        </div>
    </div>
    <div style="margin-top: 30px; padding: 15px; text-align: center; font-size: 0.8em; color: #888; border-top: 1px dashed #ccc;">
        <p style="margin: 0;">
            <strong>Disclaimer:</strong> The information provided in this email is for general informational and educational purposes only and does not constitute financial, investment, or trading advice. Market data may be delayed and is subject to change without notice. Always conduct your own research or consult with a licensed financial advisor before making any investment decisions. VilfinTV is not responsible for any financial losses incurred based on this report.
        </p>
    </div>
    </body>
    </html>
    """
    
    return _minify_html(html)

if __name__ == '__main__':
    logging.info('Starting S&P 500 Stock Analyzer Pipeline')
    symbols_data = fetch_sp500_symbols()
    if not symbols_data:
        logging.error('No symbols to process')
        exit(1)
    
    # Bulk fetch all symbols
    all_symbols = [s['symbol'] for s in symbols_data]
    bulk_data = fetch_bulk_data(all_symbols)
    
    # Merge symbol metadata
    stock_data = {}
    sym_meta = {s['symbol']: s for s in symbols_data}
    for sym, metrics in bulk_data.items():
        if metrics and _valid(metrics.get('price')):
            meta = sym_meta.get(sym, {})
            stock_data[sym] = {
                **metrics, 
                'name': meta.get('name', sym), 
                'sector': meta.get('sector', 'Unknown'), 
                'sub_industry': meta.get('sub_industry', '')
            }
    
    logging.info(f'Successfully fetched data for {len(stock_data)}/{len(all_symbols)} stocks')
    
    # Generate all screenings
    overview = get_market_overview(stock_data)
    gainers = get_top_gainers(stock_data)
    losers = get_top_losers(stock_data)
    momentum = get_momentum_leaders(stock_data)
    value = get_value_opportunities(stock_data)
    quality = get_quality_champions(stock_data)
    lt_winners = get_long_term_winners(stock_data)
    rsi_alerts = get_rsi_alerts(stock_data)
    vol_surges = get_volume_surges(stock_data)
    breakouts = get_52w_breakouts(stock_data)
    sector_rot = get_sector_rotation(stock_data)
    rel_strength = get_relative_strength(stock_data)
    
    html = generate_html_email(
        overview, gainers, losers, momentum, value, quality, 
        lt_winners, rsi_alerts, vol_surges, breakouts, 
        sector_rot, rel_strength, stock_data
    )
    
    send_email(html, f'📊 S&P 500 Daily Stock Report — {jst_today_str()}', 'VilfinTV US Equities')
    logging.info('Pipeline completed.')
