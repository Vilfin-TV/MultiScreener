import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import yfinance as yf
import pandas as pd
from datetime import datetime
import logging
import requests
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration for Tickers
TICKERS_CONFIG = {
    'Volatility': {'VIX': '^VIX'},
    'Bonds': {'US 10Y': '^TNX', 'US 30Y': '^TYX'},
    'Commodities': {'Brent Crude': 'BZ=F', 'Gold': 'GC=F', 'Silver': 'SI=F', 'Copper': 'HG=F'},
    'US Futures': {'S&P 500 Futures': 'ES=F', 'Nasdaq 100 Futures': 'NQ=F', 'Dow Jones Futures': 'YM=F'},
    'Global Indices': {
        'Germany DAX': '^GDAXI',
        'Brazil Bovespa': '^BVSP',
        'Turkey BIST 100': 'XU100.IS',
        'Australia ASX 200': '^AXJO',
        'Taiwan Weighted': '^TWII'
    },
    'US Indices': {'S&P 500': '^GSPC', 'Nasdaq 100': '^NDX', 'Dow Jones': '^DJI'},
    'Asian Indices': {
        'Nikkei 225': '^N225', 
        'TOPIX': '^TOPX', 
        'Kospi': '^KS11', 
        'Hang Seng': '^HSI', 
        'Sensex': '^BSESN', 
        'Nifty 50': '^NSEI', 
        'BSE 500 (Nifty 500 Proxy)': 'BSE-500.BO', 
        'Nifty Midcap 50': '^NSEMDCP50', 
        'Nifty Next 50 (ETF)': 'JUNIORBEES.NS'
    },
    'Sectors & Themes': {
        'AI Stocks': 'AIQ',
        'Semiconductor': 'SMH',
        'Technology': 'XLK',
        'Health Care': 'XLV',
        'Space': 'ARKX',
        'Metals & Mining': 'XME',
        'Energy': 'XLE',
        'Consumer Discretionary': 'XLY',
        'Industrials': 'XLI',
        'Banking': 'KBE',
        'Finance': 'XLF',
        'Auto': 'CARZ'
    },
    'Currencies': {
        'EUR/USD': 'EURUSD=X', 
        'EUR/INR': 'EURINR=X', 
        'USD/JPY': 'JPY=X', 
        'JPY/INR': 'JPYINR=X', 
        'USD/INR': 'INR=X', 
        'USD/CNY': 'CNY=X'
    }
}

def fetch_asset_data(ticker_symbol):
    """Fetches market data with Cloudflare worker proxy support and Alpha Vantage fallback."""
    # 1. Try yfinance
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        })
        
        proxy = os.environ.get('YAHOO_PROXY') or os.environ.get('WORKER_URL')
        if proxy:
            proxies = {'http': proxy, 'https': proxy}
            session.proxies.update(proxies)
            
        ticker = yf.Ticker(ticker_symbol, session=session)
        hist = ticker.history(period="3mo")

        if not hist.empty:
            latest_close = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else latest_close
            daily_change = ((latest_close - prev_close) / prev_close) * 100
            
            ma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else None
            ma_20 = hist['Close'].rolling(window=20).mean().iloc[-1] if len(hist) >= 20 else None
            
            return {
                'price': latest_close,
                'change': daily_change,
                'ma_50': ma_50,
                'ma_20': ma_20
            }
    except Exception as e:
        logging.warning(f"yfinance failed for {ticker_symbol}: {e}")

    # 2. Alpha Vantage Fallback
    av_api_key = os.environ.get('ALPHA_VANTAGE_API_KEY')
    if av_api_key:
        logging.info(f"Attempting Alpha Vantage fallback for {ticker_symbol}")
        try:
            symbol_clean = ticker_symbol.replace('^', '').replace('=F', '').replace('=X', '')
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol_clean}&apikey={av_api_key}&outputsize=compact"
            response = requests.get(url)
            data = response.json()
            if "Time Series (Daily)" in data:
                ts = data["Time Series (Daily)"]
                df = pd.DataFrame.from_dict(ts, orient='index')
                df = df.rename(columns={'4. close': 'Close'})
                df['Close'] = df['Close'].astype(float)
                df.index = pd.to_datetime(df.index)
                df = df.sort_index()
                
                if len(df) > 0:
                    latest_close = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[-2] if len(df) > 1 else latest_close
                    daily_change = ((latest_close - prev_close) / prev_close) * 100
                    
                    ma_50 = df['Close'].rolling(window=50).mean().iloc[-1] if len(df) >= 50 else None
                    ma_20 = df['Close'].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else None
                    
                    return {
                        'price': latest_close,
                        'change': daily_change,
                        'ma_50': ma_50,
                        'ma_20': ma_20
                    }
        except Exception as e:
            logging.error(f"Alpha Vantage fallback failed for {ticker_symbol}: {e}")
            
    logging.error(f"All data fetch methods failed for {ticker_symbol}")
    return None

def collect_market_data():
    all_data = {}
    for category, assets in TICKERS_CONFIG.items():
        all_data[category] = {}
        for name, symbol in assets.items():
            logging.info(f"Fetching data for {name} ({symbol})")
            data = fetch_asset_data(symbol)
            all_data[category][name] = data
            time.sleep(2) # Prevent Yahoo Finance rate limits
    return all_data

def get_executive_summary_analysis(data, regime_score):
    # 1. Regional Recommendation
    if regime_score <= -50:
        regional_rec = "Safe Havens (Bonds & Gold). Equities are in a severe contraction phase. Cash and fixed income are preferred."
    else:
        scores = {'US Equities': 0, 'Asian Equities': 0, 'Global Indices': 0}
        counts = {'US Equities': 0, 'Asian Equities': 0, 'Global Indices': 0}
        
        for name, metrics in data.get('US Indices', {}).items():
            if metrics:
                counts['US Equities'] += 1
                if metrics['ma_50'] and metrics['price'] > metrics['ma_50']:
                    scores['US Equities'] += 1
                    
        for name, metrics in data.get('Asian Indices', {}).items():
            if metrics:
                counts['Asian Equities'] += 1
                if metrics['ma_50'] and metrics['price'] > metrics['ma_50']:
                    scores['Asian Equities'] += 1
                    
        us_ratio = (scores['US Equities'] / counts['US Equities']) if counts['US Equities'] > 0 else 0
        asian_ratio = (scores['Asian Equities'] / counts['Asian Equities']) if counts['Asian Equities'] > 0 else 0
        
        if regime_score >= 50:
            if us_ratio >= asian_ratio and us_ratio >= 0.5:
                regional_rec = "US Equities (S&P 500, Nasdaq). Momentum is exceptionally strong in Western markets."
            elif asian_ratio > us_ratio and asian_ratio >= 0.5:
                regional_rec = "Asian Equities (Nifty, Sensex). Eastern markets are showing leading relative strength."
            else:
                regional_rec = "Broad Equities. Markets are expanding globally."
        else: 
            if us_ratio > 0.6:
                regional_rec = "Selective US Equities. Market is mixed, but US large-caps hold their trends."
            elif asian_ratio > 0.6:
                regional_rec = "Selective Asian Equities (Midcaps). Eastern markets are outperforming."
            else:
                regional_rec = "Defensive Equities & Commodities (Gold, Silver). Markets lack clear directional momentum."

    # 2. Sector Analysis
    sector_data = data.get('Sectors & Themes', {})
    valid_sectors = {name: metrics for name, metrics in sector_data.items() if metrics and metrics['ma_50']}
    
    momentum_name = "N/A"
    value_name = "N/A"
    long_term_name = "N/A"
    
    if valid_sectors:
        # Momentum: Sector trading furthest above 50-day MA
        momentum_sector = max(valid_sectors.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
        momentum_name = f"{momentum_sector[0]} (+{momentum_sector[1]['change']:.2f}%)"
        
        # Value: Energy, Finance, Industrials, Banking, Metals
        value_names = ['Energy', 'Finance', 'Industrials', 'Banking', 'Metals & Mining']
        value_sectors = {k: v for k, v in valid_sectors.items() if k in value_names}
        if value_sectors:
            best_value = max(value_sectors.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
            value_name = best_value[0]
            
        # Long Term: Thematic/Tech that is showing steady growth
        long_term_candidates = ['Semiconductor', 'AI Stocks', 'Technology', 'Health Care', 'Space']
        lt_sectors = {k: v for k, v in valid_sectors.items() if k in long_term_candidates}
        if lt_sectors:
            best_lt = max(lt_sectors.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
            long_term_name = best_lt[0]

    return regional_rec, momentum_name, value_name, long_term_name

def calculate_market_regime(data):
    score = 0
    risk_alerts = []

    vix_data = data.get('Volatility', {}).get('VIX')
    if vix_data and vix_data['ma_20']:
        vix_price = vix_data['price']
        if vix_price > 20 or vix_price > vix_data['ma_20']:
            score -= 20
        else:
            score += 20
        if vix_price > 25:
            risk_alerts.append(f"High Volatility: VIX is extremely elevated at {vix_price:.2f}.")

    yield_10y_data = data.get('Bonds', {}).get('US 10Y')
    yield_30y_data = data.get('Bonds', {}).get('US 30Y')
    
    if yield_10y_data and yield_30y_data:
        spread = yield_30y_data['price'] - yield_10y_data['price']
        if spread < 0:
            score -= 20
            risk_alerts.append("Yield Curve Inversion: US 10Y yield > US 30Y yield (Recession signal).")
        elif spread > 0.5:
            score += 20
        else:
            score += 0 

    sp500 = data.get('US Indices', {}).get('S&P 500')
    nikkei = data.get('Asian Indices', {}).get('Nikkei 225')
    nifty = data.get('Asian Indices', {}).get('Nifty 50')
    
    equity_score = 0
    for asset, name in zip([sp500, nikkei, nifty], ['S&P 500', 'Nikkei 225', 'Nifty 50']):
        if asset and asset['ma_50']:
            if asset['price'] > asset['ma_50']:
                equity_score += 10
            else:
                equity_score -= 10
                risk_alerts.append(f"Momentum Warning: {name} is trading below its 50-day moving average.")
    score += equity_score

    gold = data.get('Commodities', {}).get('Gold')
    copper = data.get('Commodities', {}).get('Copper')
    
    risk_off_count = 0
    if gold and gold['change'] > 0: risk_off_count += 1
    if copper and copper['change'] < 0: risk_off_count += 1
    if sp500 and sp500['change'] < 0: risk_off_count += 1
    
    if risk_off_count >= 2:
        score -= 30
    elif risk_off_count == 1:
        score += 10
    else:
        score += 30

    for curr_name, curr_data in data.get('Currencies', {}).items():
        if curr_data and abs(curr_data['change']) > 1.5:
            direction = "surged" if curr_data['change'] > 0 else "dropped"
            risk_alerts.append(f"Currency Volatility: {curr_name} {direction} by {abs(curr_data['change']):.2f}%.")

    score = max(min(score, 100), -100)
    
    if score >= 50:
        regime_text = "Bullish Expansion"
    elif score >= 10:
        regime_text = "Bullish Leaning / Neutral"
    elif score >= -10:
        regime_text = "Neutral / Mixed"
    elif score >= -50:
        regime_text = "Bearish Contraction"
    else:
        regime_text = "Extremely Bearish / Risk-Off"

    regional_rec, mom_sector, val_sector, lt_sector = get_executive_summary_analysis(data, score)

    return score, regime_text, risk_alerts, regional_rec, mom_sector, val_sector, lt_sector

def generate_html_email(data, regime_score, regime_text, risk_alerts, regional_rec, mom_sector, val_sector, lt_sector):
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            h2 {{ color: #0a192f; border-bottom: 2px solid #0a192f; padding-bottom: 5px; margin-top: 30px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ padding: 10px; border: 1px solid #ddd; text-align: right; }}
            th {{ background-color: #f4f4f4; text-align: left; }}
            td:first-child {{ text-align: left; font-weight: bold; width: 35%; }}
            .positive {{ color: green; font-weight: bold; }}
            .negative {{ color: red; font-weight: bold; }}
            .score-box {{ padding: 20px; background: #eef2f5; border-left: 5px solid #0a192f; margin-bottom: 20px; }}
            .alerts {{ background: #fff3f3; border-left: 5px solid #d9534f; padding: 15px; }}
            .recommendation {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #16a34a; padding: 15px; margin-top: 15px; }}
            .summary-item {{ margin-bottom: 8px; }}
        </style>
    </head>
    <body>
        <h2>Market Regime Report - {datetime.now().strftime('%Y-%m-%d')}</h2>
        
        <div class="score-box">
            <h3>Executive Summary</h3>
            <div class="summary-item"><strong>Market Sentiment Score:</strong> {regime_score} / 100</div>
            <div class="summary-item"><strong>Current Phase:</strong> {regime_text}</div>
            
            <div class="recommendation">
                <h4 style="margin-top: 0;">Market & Sector Insights</h4>
                <div class="summary-item"><strong>🌍 Best Region to Buy:</strong> {regional_rec}</div>
                <div class="summary-item"><strong>🚀 Top Momentum Sector:</strong> {mom_sector} <em>(Trading furthest above 50-day average)</em></div>
                <div class="summary-item"><strong>⚖️ Top Value Sector:</strong> {val_sector} <em>(Strongest among classic value plays like Energy/Financials/Industrials)</em></div>
                <div class="summary-item"><strong>💎 Best for Long-Term:</strong> {lt_sector} <em>(Leading structural growth theme)</em></div>
            </div>
        </div>
    """

    if risk_alerts:
        html += "<div class='alerts'><h3 style='margin-top:0;'>Risk Alerts</h3><ul style='margin-bottom:0;'>"
        for alert in risk_alerts:
            html += f"<li>{alert}</li>"
        html += "</ul></div>"

    html += "<h2>Asset Dashboard</h2>"
    for category, assets in data.items():
        html += f"<h3>{category}</h3>"
        html += """
        <table>
            <tr>
                <th>Asset</th>
                <th>Current Price</th>
                <th>Daily Change</th>
                <th>50-Day MA</th>
            </tr>
        """
        for name, metrics in assets.items():
            if metrics:
                change_class = "positive" if metrics['change'] >= 0 else "negative"
                change_sign = "+" if metrics['change'] >= 0 else ""
                ma_50_str = f"{metrics['ma_50']:.2f}" if metrics['ma_50'] else "N/A"
                
                html += f"""
                <tr>
                    <td>{name}</td>
                    <td>{metrics['price']:.2f}</td>
                    <td class="{change_class}">{change_sign}{metrics['change']:.2f}%</td>
                    <td>{ma_50_str}</td>
                </tr>
                """
            else:
                html += f"<tr><td>{name}</td><td colspan='3' style='text-align:center; color: #999;'>Data Unavailable</td></tr>"
        html += "</table>"

    html += """
    </body>
    </html>
    """
    return html

def send_email(html_content):
    sender_email = os.environ.get('GMAIL_USER')
    sender_password = os.environ.get('GMAIL_APP_PASSWORD')
    receiver_email = os.environ.get('EMAIL_TO')

    if not all([sender_email, sender_password, receiver_email]):
        logging.error("Email credentials or EMAIL_TO not set in environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"Daily Market Analysis & Sector Report - {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = sender_email
    msg['To'] = receiver_email

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        logging.info("Successfully sent market report email.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

if __name__ == "__main__":
    logging.info("Starting Market Analyzer Pipeline")
    market_data = collect_market_data()
    score, regime, alerts, rec_regional, rec_mom, rec_val, rec_lt = calculate_market_regime(market_data)
    
    logging.info(f"Calculated Regime Score: {score} ({regime})")
    
    html_report = generate_html_email(market_data, score, regime, alerts, rec_regional, rec_mom, rec_val, rec_lt)
    send_email(html_report)
    logging.info("Pipeline execution completed.")
