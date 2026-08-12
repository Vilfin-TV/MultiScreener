import logging
import time
import math
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
    rank_by_lt_score,
    send_email
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ETF_UNIVERSE = {
    'Sector SPDR': {
        'XLK': {'name': 'Technology Select Sector', 'category': 'Sector SPDR'},
        'XLV': {'name': 'Health Care Select Sector', 'category': 'Sector SPDR'},
        'XLF': {'name': 'Financial Select Sector', 'category': 'Sector SPDR'},
        'XLE': {'name': 'Energy Select Sector', 'category': 'Sector SPDR'},
        'XLI': {'name': 'Industrial Select Sector', 'category': 'Sector SPDR'},
        'XLY': {'name': 'Consumer Discretionary Select', 'category': 'Sector SPDR'},
        'XLP': {'name': 'Consumer Staples Select', 'category': 'Sector SPDR'},
        'XLB': {'name': 'Materials Select Sector', 'category': 'Sector SPDR'},
        'XLU': {'name': 'Utilities Select Sector', 'category': 'Sector SPDR'},
        'XLRE': {'name': 'Real Estate Select Sector', 'category': 'Sector SPDR'},
        'XLC': {'name': 'Communication Services Select', 'category': 'Sector SPDR'},
    },
    'Thematic': {
        'SOXX': {'name': 'iShares Semiconductor', 'category': 'Thematic'},
        'SMH': {'name': 'VanEck Semiconductor', 'category': 'Thematic'},
        'AIQ': {'name': 'Global X AI & Technology', 'category': 'Thematic'},
        'BOTZ': {'name': 'Global X Robotics & AI', 'category': 'Thematic'},
        'CIBR': {'name': 'First Trust Cybersecurity', 'category': 'Thematic'},
        'ICLN': {'name': 'iShares Clean Energy', 'category': 'Thematic'},
        'ARKK': {'name': 'ARK Innovation', 'category': 'Thematic'},
        'ARKG': {'name': 'ARK Genomic Revolution', 'category': 'Thematic'},
        'ARKX': {'name': 'ARK Space Exploration', 'category': 'Thematic'},
        'IBB': {'name': 'iShares Biotechnology', 'category': 'Thematic'},
        'CLOU': {'name': 'Global X Cloud Computing', 'category': 'Thematic'},
        'DRIV': {'name': 'Global X Autonomous & EVs', 'category': 'Thematic'},
        'BLOK': {'name': 'Amplify Blockchain', 'category': 'Thematic'},
        'SRVR': {'name': 'Pacer Data & Infrastructure', 'category': 'Thematic'},
        'LIT': {'name': 'Global X Lithium & Battery', 'category': 'Thematic'},
        'URA': {'name': 'Global X Uranium', 'category': 'Thematic'},
        'TAN': {'name': 'Invesco Solar', 'category': 'Thematic'},
        'HACK': {'name': 'ETFMG Prime Cyber Security', 'category': 'Thematic'},
        'ROBO': {'name': 'ROBO Global Robotics', 'category': 'Thematic'},
    },
    'Broad Market': {
        'SPY': {'name': 'SPDR S&P 500', 'category': 'Broad Market'},
        'QQQ': {'name': 'Invesco Nasdaq 100', 'category': 'Broad Market'},
        'DIA': {'name': 'SPDR Dow Jones', 'category': 'Broad Market'},
        'IWM': {'name': 'iShares Russell 2000', 'category': 'Broad Market'},
        'VTI': {'name': 'Vanguard Total Stock', 'category': 'Broad Market'},
        'VUG': {'name': 'Vanguard Growth', 'category': 'Broad Market'},
        'VTV': {'name': 'Vanguard Value', 'category': 'Broad Market'},
        'RSP': {'name': 'Invesco Equal-Weight S&P 500', 'category': 'Broad Market'},
        'SPLG': {'name': 'SPDR Portfolio S&P 500', 'category': 'Broad Market'},
        'MDY': {'name': 'SPDR S&P MidCap 400', 'category': 'Broad Market'},
        'IJR': {'name': 'iShares S&P SmallCap 600', 'category': 'Broad Market'},
        'IOO': {'name': 'iShares Global 100', 'category': 'Broad Market'},
    },
    'Factor': {
        'MTUM': {'name': 'iShares MSCI USA Momentum', 'category': 'Factor'},
        'VLUE': {'name': 'iShares MSCI USA Value', 'category': 'Factor'},
        'QUAL': {'name': 'iShares MSCI USA Quality', 'category': 'Factor'},
        'SIZE': {'name': 'iShares MSCI USA Size', 'category': 'Factor'},
        'SPLV': {'name': 'Invesco S&P 500 Low Volatility', 'category': 'Factor'},
        'MOAT': {'name': 'VanEck Morningstar Wide Moat', 'category': 'Factor'},
        'COWZ': {'name': 'Pacer US Cash Cows 100', 'category': 'Factor'},
        'DGRW': {'name': 'WisdomTree US Quality Dividend Growth', 'category': 'Factor'},
        'SCHD': {'name': 'Schwab US Dividend Equity', 'category': 'Factor'},
        'DGRO': {'name': 'iShares Core Dividend Growth', 'category': 'Factor'},
    },
    'Bond / Fixed Income': {
        'AGG': {'name': 'iShares Core US Aggregate Bond', 'category': 'Bond / Fixed Income'},
        'BND': {'name': 'Vanguard Total Bond Market', 'category': 'Bond / Fixed Income'},
        'TLT': {'name': 'iShares 20+ Year Treasury', 'category': 'Bond / Fixed Income'},
        'IEF': {'name': 'iShares 7-10 Year Treasury', 'category': 'Bond / Fixed Income'},
        'SHY': {'name': 'iShares 1-3 Year Treasury', 'category': 'Bond / Fixed Income'},
        'LQD': {'name': 'iShares Investment Grade Corporate', 'category': 'Bond / Fixed Income'},
        'HYG': {'name': 'iShares High Yield Corporate', 'category': 'Bond / Fixed Income'},
        'EMB': {'name': 'iShares JP Morgan EM Bond', 'category': 'Bond / Fixed Income'},
        'BNDX': {'name': 'Vanguard Total International Bond', 'category': 'Bond / Fixed Income'},
        'TIP': {'name': 'iShares TIPS Bond', 'category': 'Bond / Fixed Income'},
        'MUB': {'name': 'iShares National Muni Bond', 'category': 'Bond / Fixed Income'},
        'VCSH': {'name': 'Vanguard Short-Term Corporate', 'category': 'Bond / Fixed Income'},
    },
    'Commodity': {
        'GLD': {'name': 'SPDR Gold Shares', 'category': 'Commodity'},
        'SLV': {'name': 'iShares Silver Trust', 'category': 'Commodity'},
        'IAU': {'name': 'iShares Gold Trust', 'category': 'Commodity'},
        'DBC': {'name': 'Invesco DB Commodity Index', 'category': 'Commodity'},
        'USO': {'name': 'United States Oil Fund', 'category': 'Commodity'},
        'UNG': {'name': 'United States Natural Gas', 'category': 'Commodity'},
        'PDBC': {'name': 'Invesco Optimum Yield Commodity', 'category': 'Commodity'},
        'COPX': {'name': 'Global X Copper Miners', 'category': 'Commodity'},
        'WEAT': {'name': 'Teucrium Wheat Fund', 'category': 'Commodity'},
        'CORN': {'name': 'Teucrium Corn Fund', 'category': 'Commodity'},
        'CPER': {'name': 'United States Copper Index', 'category': 'Commodity'},
    },
    'International': {
        'EFA': {'name': 'iShares MSCI EAFE', 'category': 'International'},
        'EEM': {'name': 'iShares MSCI Emerging Markets', 'category': 'International'},
        'VWO': {'name': 'Vanguard FTSE Emerging Markets', 'category': 'International'},
        'IEMG': {'name': 'iShares Core MSCI Emerging', 'category': 'International'},
        'VEA': {'name': 'Vanguard FTSE Developed Markets', 'category': 'International'},
        'INDA': {'name': 'iShares MSCI India', 'category': 'International'},
        'FXI': {'name': 'iShares China Large-Cap', 'category': 'International'},
        'EWJ': {'name': 'iShares MSCI Japan', 'category': 'International'},
        'EWZ': {'name': 'iShares MSCI Brazil', 'category': 'International'},
        'EWT': {'name': 'iShares MSCI Taiwan', 'category': 'International'},
        'EWG': {'name': 'iShares MSCI Germany', 'category': 'International'},
        'EWU': {'name': 'iShares MSCI United Kingdom', 'category': 'International'},
        'KWEB': {'name': 'KraneShares CSI China Internet', 'category': 'International'},
    },
    'Real Estate': {
        'VNQ': {'name': 'Vanguard Real Estate', 'category': 'Real Estate'},
        'IYR': {'name': 'iShares US Real Estate', 'category': 'Real Estate'},
        'RWR': {'name': 'SPDR Dow Jones REIT', 'category': 'Real Estate'},
        'RWX': {'name': 'SPDR Dow Jones Intl Real Estate', 'category': 'Real Estate'},
        'MORT': {'name': 'VanEck Mortgage REIT Income', 'category': 'Real Estate'},
        'REET': {'name': 'iShares Global REIT', 'category': 'Real Estate'},
    },
    'Dividend': {
        'VIG': {'name': 'Vanguard Dividend Appreciation', 'category': 'Dividend'},
        'DVY': {'name': 'iShares Select Dividend', 'category': 'Dividend'},
        'HDV': {'name': 'iShares Core High Dividend', 'category': 'Dividend'},
        'SDY': {'name': 'SPDR S&P Dividend', 'category': 'Dividend'},
        'NOBL': {'name': 'ProShares S&P 500 Dividend Aristocrats', 'category': 'Dividend'},
        'SPHD': {'name': 'Invesco S&P 500 High Dividend Low Vol', 'category': 'Dividend'},
        'FVD': {'name': 'First Trust Value Line Dividend', 'category': 'Dividend'},
    },
    'Leveraged / Inverse': {
        'TQQQ': {'name': 'ProShares UltraPro QQQ', 'category': 'Leveraged / Inverse'},
        'SQQQ': {'name': 'ProShares UltraPro Short QQQ', 'category': 'Leveraged / Inverse'},
        'SPXL': {'name': 'Direxion Daily S&P 500 Bull 3X', 'category': 'Leveraged / Inverse'},
        'SPXS': {'name': 'Direxion Daily S&P 500 Bear 3X', 'category': 'Leveraged / Inverse'},
        'SOXL': {'name': 'Direxion Daily Semiconductor Bull 3X', 'category': 'Leveraged / Inverse'},
        'SOXS': {'name': 'Direxion Daily Semiconductor Bear 3X', 'category': 'Leveraged / Inverse'},
        'UVXY': {'name': 'ProShares Ultra VIX Short-Term', 'category': 'Leveraged / Inverse'},
        'SVXY': {'name': 'ProShares Short VIX Short-Term', 'category': 'Leveraged / Inverse'},
    },
    'Currency': {
        'UUP': {'name': 'Invesco DB US Dollar Index', 'category': 'Currency'},
        'FXE': {'name': 'Invesco CurrencyShares Euro', 'category': 'Currency'},
        'FXY': {'name': 'Invesco CurrencyShares Japanese Yen', 'category': 'Currency'},
        'FXB': {'name': 'Invesco CurrencyShares British Pound', 'category': 'Currency'},
        'FXA': {'name': 'Invesco CurrencyShares Australian Dollar', 'category': 'Currency'},
        'FXC': {'name': 'Invesco CurrencyShares Canadian Dollar', 'category': 'Currency'},
    },
    'Crypto': {
        'BITO': {'name': 'ProShares Bitcoin Strategy', 'category': 'Crypto'},
        'IBIT': {'name': 'iShares Bitcoin Trust', 'category': 'Crypto'},
        'FBTC': {'name': 'Fidelity Wise Origin Bitcoin', 'category': 'Crypto'},
        'ETHA': {'name': 'iShares Ethereum Trust', 'category': 'Crypto'},
    },
}

def fmt_pct(val):
    if not _valid(val): return "-"
    color = "green" if val >= 0 else "red"
    sign = "+" if val > 0 else ""
    return f"<span style='color: {color};'>{sign}{val:.2f}%</span>"

def fmt_val(val, prefix="$", decimals=2):
    if not _valid(val): return "-"
    return f"{prefix}{val:,.{decimals}f}"

def get_market_context(data):
    context = []
    for sym in ['SPY', 'QQQ', 'IWM']:
        if sym in data:
            d = data[sym]
            context.append({
                'symbol': sym,
                'name': d.get('name', sym),
                'price': d.get('price'),
                'change': d.get('change'),
                'ytd_return': d.get('ytd_return'),
                'one_yr_return': d.get('one_yr_return')
            })
    return context

def get_top_gainers(data, n=10):
    valid_data = {k: v for k, v in data.items() if _valid(v.get('change')) and 'Leveraged' not in v.get('category', '')}
    return sorted(valid_data.items(), key=lambda x: x[1]['change'], reverse=True)[:n]

def get_top_losers(data, n=10):
    valid_data = {k: v for k, v in data.items() if _valid(v.get('change')) and 'Leveraged' not in v.get('category', '')}
    return sorted(valid_data.items(), key=lambda x: x[1]['change'])[:n]

def get_momentum_leaders(data, n=5):
    valid_data = {k: v for k, v in data.items() if 'Leveraged' not in v.get('category', '')}
    scored = [(k, v, calc_momentum_score(v)) for k, v in valid_data.items()]
    scored = [x for x in scored if x[2] is not None]
    return sorted(scored, key=lambda x: x[2], reverse=True)[:n]

def get_value_opportunities(data, n=5):
    valid_data = {k: v for k, v in data.items() if 'Leveraged' not in v.get('category', '')}
    scored = [(k, v, calc_value_score(v)) for k, v in valid_data.items()]
    scored = [x for x in scored if x[2] is not None]
    return sorted(scored, key=lambda x: x[2], reverse=True)[:n]

def get_quality_champions(data, n=5):
    valid_data = {k: v for k, v in data.items() if 'Leveraged' not in v.get('category', '')}
    scored = [(k, v, calc_quality_score(v)) for k, v in valid_data.items()]
    scored = [x for x in scored if x[2] is not None]
    return sorted(scored, key=lambda x: x[2], reverse=True)[:n]

def get_long_term_winners(data, n=5):
    ranked = rank_by_lt_score(data)
    valid = [x for x in ranked if 'Leveraged' not in data[x[0]].get('category', '')]
    return valid[:n]

def get_rsi_alerts(data):
    overbought = []
    oversold = []
    for k, v in data.items():
        if 'Leveraged' in v.get('category', ''): continue
        rsi = v.get('rsi_14')
        if _valid(rsi):
            if rsi > 70:
                overbought.append((k, v))
            elif rsi < 30:
                oversold.append((k, v))
    overbought = sorted(overbought, key=lambda x: x[1]['rsi_14'], reverse=True)
    oversold = sorted(oversold, key=lambda x: x[1]['rsi_14'])
    return overbought[:5], oversold[:5]

def get_volume_surges(data, n=10):
    surges = []
    for k, v in data.items():
        if _valid(v.get('volume')) and _valid(v.get('avg_volume_20')) and v['avg_volume_20'] > 0:
            ratio = v['volume'] / v['avg_volume_20']
            if ratio > 1.5:
                surges.append((k, v, ratio))
    return sorted(surges, key=lambda x: x[2], reverse=True)[:n]

def get_52w_breakouts(data, n=10):
    breakouts = []
    for k, v in data.items():
        if _valid(v.get('price')) and _valid(v.get('high_52w')) and v['high_52w'] > 0:
            dist = (v['high_52w'] - v['price']) / v['high_52w']
            if dist <= 0.02 and dist >= -0.05:
                breakouts.append((k, v, dist))
    return sorted(breakouts, key=lambda x: x[2])[:n]

def get_category_champions(data):
    champions = {}
    for k, v in data.items():
        cat = v.get('category', 'Other')
        if 'Leveraged' in cat: continue
        score = calc_momentum_score(v)
        if score is None: continue
        if cat not in champions or score > champions[cat][2]:
            champions[cat] = (k, v, score)
    return champions

def get_flow_proxy(data, n=10):
    flows = []
    for k, v in data.items():
        if _valid(v.get('volume')) and _valid(v.get('avg_volume_20')) and v['avg_volume_20'] > 0:
            ratio = v['volume'] / v['avg_volume_20']
            flows.append((k, v, ratio))
    return sorted(flows, key=lambda x: x[2], reverse=True)[:n]

def get_risk_adjusted_rankings(data, n=10):
    ranked = []
    for k, v in data.items():
        if 'Leveraged' in v.get('category', ''): continue
        ytd = v.get('ytd_return')
        std = v.get('daily_returns_std_20')
        if _valid(ytd) and _valid(std) and std > 0:
            ratio = ytd / (std * math.sqrt(252) * 100) # approx annualized vol
            ranked.append((k, v, ratio))
    return sorted(ranked, key=lambda x: x[2], reverse=True)[:n]

def get_sector_etf_heatmap(data):
    sectors = {k: v for k, v in data.items() if v.get('category') == 'Sector SPDR'}
    return sorted(sectors.items(), key=lambda x: x[1].get('change', 0), reverse=True)

def get_thematic_spotlight(data):
    thematic = {k: v for k, v in data.items() if v.get('category') == 'Thematic'}
    return sorted(thematic.items(), key=lambda x: x[1].get('change', 0), reverse=True)


def generate_html_email(context, cat_champs, gainers, losers, momentum, value, quality, lt_winners, rsi, vol_surges, breakouts, sector_heat, thematic, risk_adj, flow, full_data):
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: #f4f7f6;
                color: #333333;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background-color: #ffffff;
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            }}
            .header {{
                background-color: #0a192f;
                color: #ffffff;
                padding: 30px 40px;
                text-align: center;
                border-bottom: 4px solid #112240;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            .header p {{
                margin: 10px 0 0 0;
                font-size: 14px;
                color: #8892b0;
            }}
            .section {{
                padding: 30px 40px;
                border-bottom: 1px solid #eeeeee;
            }}
            .section-title {{
                color: #0a192f;
                font-size: 20px;
                font-weight: 600;
                margin-top: 0;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
            }}
            .card-container {{
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
            }}
            .card {{
                flex: 1;
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 15px;
                text-align: center;
            }}
            .card-title {{
                font-size: 14px;
                font-weight: 600;
                color: #64748b;
                margin-bottom: 5px;
            }}
            .card-value {{
                font-size: 22px;
                font-weight: 700;
                color: #0f172a;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
                font-size: 13px;
            }}
            th {{
                background-color: #f1f5f9;
                color: #475569;
                font-weight: 600;
                text-align: left;
                padding: 10px 12px;
                border-bottom: 2px solid #cbd5e1;
            }}
            td {{
                padding: 10px 12px;
                border-bottom: 1px solid #e2e8f0;
                color: #1e293b;
            }}
            tr:last-child td {{
                border-bottom: none;
            }}
            .row-split {{
                display: flex;
                gap: 20px;
            }}
            .col-half {{
                flex: 1;
            }}
            .sym {{
                font-weight: 700;
                color: #0ea5e9;
            }}
            .heat-green {{ background-color: rgba(34, 197, 94, 0.15); }}
            .heat-red {{ background-color: rgba(239, 68, 68, 0.15); }}
            .footer {{
                background-color: #0f172a;
                color: #94a3b8;
                padding: 30px 40px;
                font-size: 12px;
                text-align: center;
                line-height: 1.5;
            }}
            .footer a {{
                color: #38bdf8;
                text-decoration: none;
            }}
            .brokers {{
                background-color: #f8fafc;
                padding: 20px 40px;
                text-align: center;
                border-top: 1px solid #e2e8f0;
            }}
            .brokers h3 {{
                color: #334155;
                font-size: 14px;
                margin-top: 0;
            }}
            .brokers a {{
                display: inline-block;
                margin: 5px 10px;
                color: #0284c7;
                text-decoration: none;
                font-weight: 600;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>VilfinTV</h1>
                <h2>US ETF Daily Report</h2>
                <p>Institutional-Grade ETF Screening & Analysis | {jst_today_str()}</p>
            </div>
            
            <div class="section">
                <h2 class="section-title">Market Context</h2>
                <div class="card-container">
    """
    
    for ctx in context:
        html += f"""
                    <div class="card">
                        <div class="card-title">{ctx['symbol']} ({ctx['name']})</div>
                        <div class="card-value">{fmt_val(ctx['price'])}</div>
                        <div>Day: {fmt_pct(ctx['change'])} | YTD: {fmt_pct(ctx['ytd_return'])}</div>
                    </div>
        """
        
    html += """
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">Category Champions (Momentum Leaders)</h2>
                <table>
                    <tr>
                        <th>Category</th>
                        <th>Symbol</th>
                        <th>Name</th>
                        <th>Day Chg</th>
                        <th>YTD Return</th>
                        <th>Mom Score</th>
                    </tr>
    """
    for cat, (sym, d, score) in cat_champs.items():
        html += f"""
                    <tr>
                        <td>{cat}</td>
                        <td class="sym">{sym}</td>
                        <td>{d.get('name', '')}</td>
                        <td>{fmt_pct(d.get('change'))}</td>
                        <td>{fmt_pct(d.get('ytd_return'))}</td>
                        <td>{score:.2f}</td>
                    </tr>
        """
        
    html += """
                </table>
            </div>

            <div class="section">
                <div class="row-split">
                    <div class="col-half">
                        <h2 class="section-title">Top 10 Gainers</h2>
                        <table>
                            <tr><th>Symbol</th><th>Name</th><th>Change</th></tr>
    """
    for sym, d in gainers:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')[:20]}</td><td>{fmt_pct(d.get('change'))}</td></tr>"
        
    html += """
                        </table>
                    </div>
                    <div class="col-half">
                        <h2 class="section-title">Top 10 Losers</h2>
                        <table>
                            <tr><th>Symbol</th><th>Name</th><th>Change</th></tr>
    """
    for sym, d in losers:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')[:20]}</td><td>{fmt_pct(d.get('change'))}</td></tr>"

    html += """
                        </table>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">Sector ETF Heatmap (SPDR)</h2>
                <table>
                    <tr>
                        <th>Symbol</th>
                        <th>Sector</th>
                        <th>Day Chg</th>
                        <th>1M Ret</th>
                        <th>YTD Ret</th>
                    </tr>
    """
    for sym, d in sector_heat:
        chg = d.get('change', 0)
        cls = 'heat-green' if chg > 0 else 'heat-red' if chg < 0 else ''
        html += f"""
                    <tr class="{cls}">
                        <td class="sym">{sym}</td>
                        <td>{d.get('name', '')}</td>
                        <td>{fmt_pct(d.get('change'))}</td>
                        <td>{fmt_pct(d.get('one_month_return', 0))}</td>
                        <td>{fmt_pct(d.get('ytd_return'))}</td>
                    </tr>
        """
        
    html += """
                </table>
            </div>

            <div class="section">
                <h2 class="section-title">Thematic ETF Spotlight</h2>
                <table>
                    <tr>
                        <th>Symbol</th>
                        <th>Theme</th>
                        <th>Day Chg</th>
                        <th>YTD Ret</th>
                    </tr>
    """
    for sym, d in thematic[:10]:
        html += f"""
                    <tr>
                        <td class="sym">{sym}</td>
                        <td>{d.get('name', '')}</td>
                        <td>{fmt_pct(d.get('change'))}</td>
                        <td>{fmt_pct(d.get('ytd_return'))}</td>
                    </tr>
        """
        
    html += """
                </table>
            </div>

            <div class="section">
                <h2 class="section-title">Momentum Leaders</h2>
                <table>
                    <tr><th>Symbol</th><th>Name</th><th>YTD</th><th>Score</th></tr>
    """
    for sym, d, score in momentum:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')}</td><td>{fmt_pct(d.get('ytd_return'))}</td><td>{score:.2f}</td></tr>"
        
    html += """
                </table>
            </div>

            <div class="section">
                <h2 class="section-title">Value Opportunities (Oversold/Discount)</h2>
                <table>
                    <tr><th>Symbol</th><th>Name</th><th>RSI 14</th><th>Score</th></tr>
    """
    for sym, d, score in value:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')}</td><td>{d.get('rsi_14', 0):.1f}</td><td>{score:.2f}</td></tr>"

    html += """
                </table>
            </div>
            
            <div class="section">
                <h2 class="section-title">Quality Consistent ETFs</h2>
                <table>
                    <tr><th>Symbol</th><th>Name</th><th>YTD</th><th>Score</th></tr>
    """
    for sym, d, score in quality:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')}</td><td>{fmt_pct(d.get('ytd_return'))}</td><td>{score:.2f}</td></tr>"

    html += """
                </table>
            </div>

            <div class="section">
                <h2 class="section-title">Long-Term Winners</h2>
                <table>
                    <tr><th>Symbol</th><th>Name</th><th>3Y Ret</th><th>Score</th></tr>
    """
    for item in lt_winners:
        sym = item[0]
        d = full_data.get(sym, {})
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')}</td><td>{fmt_pct(d.get('three_yr_return'))}</td><td>{item[1]:.2f}</td></tr>"

    html += """
                </table>
            </div>

            <div class="section">
                <div class="row-split">
                    <div class="col-half">
                        <h2 class="section-title">Overbought Alerts (RSI > 70)</h2>
                        <table>
                            <tr><th>Symbol</th><th>RSI</th></tr>
    """
    ob, os = rsi
    for sym, d in ob:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('rsi_14', 0):.1f}</td></tr>"
        
    html += """
                        </table>
                    </div>
                    <div class="col-half">
                        <h2 class="section-title">Oversold Alerts (RSI < 30)</h2>
                        <table>
                            <tr><th>Symbol</th><th>RSI</th></tr>
    """
    for sym, d in os:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('rsi_14', 0):.1f}</td></tr>"

    html += """
                        </table>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">Volume Surges (Flow Proxy)</h2>
                <table>
                    <tr><th>Symbol</th><th>Name</th><th>Vol Ratio (vs 20d)</th></tr>
    """
    for sym, d, ratio in vol_surges:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')}</td><td>{ratio:.2f}x</td></tr>"
        
    html += """
                </table>
            </div>

            <div class="section">
                <h2 class="section-title">52-Week Breakouts (Near Highs)</h2>
                <table>
                    <tr><th>Symbol</th><th>Name</th><th>Dist to 52W High</th></tr>
    """
    for sym, d, dist in breakouts:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')}</td><td>{fmt_pct(dist * 100)}</td></tr>"
        
    html += """
                </table>
            </div>

            <div class="section">
                <h2 class="section-title">Risk-Adjusted Rankings</h2>
                <table>
                    <tr><th>Symbol</th><th>Name</th><th>YTD</th><th>Risk Adj Score</th></tr>
    """
    for sym, d, score in risk_adj:
        html += f"<tr><td class='sym'>{sym}</td><td>{d.get('name', '')}</td><td>{fmt_pct(d.get('ytd_return'))}</td><td>{score:.2f}</td></tr>"
        
    html += """
                </table>
            </div>
            
            <div class="brokers">
                <h3>Recommended Platforms</h3>
                <a href="https://zerodha.com/?c=YOUR_CODE" target="_blank">Zerodha</a> | 
                <a href="https://join.dhan.co/?invite=YOUR_CODE" target="_blank">Dhan</a> | 
                <a href="https://prostocks.com" target="_blank">ProStocks</a> | 
                <a href="https://www.interactivebrokers.com" target="_blank">IBKR</a> | 
                <a href="https://kuvera.in" target="_blank">Kuvera</a><br>
                <a href="https://revolut.com" target="_blank">Revolut</a> | 
                <a href="https://wise.com" target="_blank">Wise</a> | 
                <a href="https://instarem.com" target="_blank">Instarem</a>
            </div>
            
            <div class="footer">
                <p><strong>Disclaimer:</strong> This report is strictly for informational and educational purposes only. It is not financial advice, and does not constitute a recommendation to buy or sell any securities.</p>
                <p><a href="#">Subscribe</a> | <a href="#">Unsubscribe</a></p>
                <p>&copy; 2026 VilfinTV. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return _minify_html(html)

if __name__ == '__main__':
    logging.info('Starting US ETF Analyzer Pipeline')
    all_symbols = []
    symbol_meta = {}
    for cat_name, etfs in ETF_UNIVERSE.items():
        for sym, info in etfs.items():
            all_symbols.append(sym)
            symbol_meta[sym] = info
            
    bulk_data = fetch_bulk_data(all_symbols, period='3y')
    
    etf_data = {}
    for sym, metrics in bulk_data.items():
        if metrics and _valid(metrics.get('price')):
            meta = symbol_meta.get(sym, {})
            etf_data[sym] = {**metrics, 'name': meta.get('name', sym), 'category': meta.get('category', 'Other')}
            
    # Individual fallback for failed symbols
    for sym in all_symbols:
        if sym not in etf_data:
            data = fetch_asset_data(sym)
            if data and _valid(data.get('price')):
                meta = symbol_meta.get(sym, {})
                etf_data[sym] = {**data, 'name': meta.get('name', sym), 'category': meta.get('category', 'Other')}
            time.sleep(0.5)
            
    logging.info(f'Successfully fetched data for {len(etf_data)}/{len(all_symbols)} ETFs')
    
    context = get_market_context(etf_data)
    cat_champs = get_category_champions(etf_data)
    gainers = get_top_gainers(etf_data)
    losers = get_top_losers(etf_data)
    momentum = get_momentum_leaders(etf_data)
    value = get_value_opportunities(etf_data)
    quality = get_quality_champions(etf_data)
    lt_winners = get_long_term_winners(etf_data)
    rsi = get_rsi_alerts(etf_data)
    vol_surges = get_volume_surges(etf_data)
    breakouts = get_52w_breakouts(etf_data)
    sector_heat = get_sector_etf_heatmap(etf_data)
    thematic = get_thematic_spotlight(etf_data)
    risk_adj = get_risk_adjusted_rankings(etf_data)
    flow = get_flow_proxy(etf_data)
    
    html = generate_html_email(
        context, cat_champs, gainers, losers, momentum, value, quality, 
        lt_winners, rsi, vol_surges, breakouts, sector_heat, thematic, risk_adj, flow, etf_data
    )
    
    subject = f'📊 US ETF Daily Report — {jst_today_str()}'
    send_email(html, subject, 'VilfinTV US ETFs')
    logging.info('Pipeline completed.')
