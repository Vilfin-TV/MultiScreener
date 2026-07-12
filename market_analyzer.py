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
    'Commodities': {'Brent Crude': 'BZ=F', 'Gold': 'GC=F', 'Copper': 'HG=F'},
    'US Indices': {'S&P 500': '^GSPC', 'Nasdaq 100': '^NDX', 'Dow Jones': '^DJI'},
    'Asian Indices': {'Nikkei 225': '^N225', 'TOPIX': '^TOPX', 'Kospi': '^KS11', 'Hang Seng': '^HSI', 'Nifty 50': '^NSEI', 'Nifty 500': 'NIFTY_500.NS'},
    'Currencies': {'EUR/USD': 'EURUSD=X', 'USD/JPY': 'JPY=X', 'USD/INR': 'INR=X', 'USD/CNY': 'CNY=X'}
}

def fetch_asset_data(ticker_symbol):
    """Fetches market data with Cloudflare worker proxy support and Alpha Vantage fallback."""
    # 1. Try yfinance (with optional proxy)
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
            # If the proxy is just a host, make sure it has the scheme, else just pass it
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
            # Alpha Vantage uses different symbols sometimes, strip Yahoo-specific characters
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
    """Collects market data for all configured tickers."""
    all_data = {}
    for category, assets in TICKERS_CONFIG.items():
        all_data[category] = {}
        for name, symbol in assets.items():
            logging.info(f"Fetching data for {name} ({symbol})")
            data = fetch_asset_data(symbol)
            all_data[category][name] = data
            time.sleep(2) # Delay to prevent hitting Yahoo rate limits
    return all_data

def calculate_market_regime(data):
    """
    Calculates a Market Regime Indicator score ranging from -100 to +100.
    """
    score = 0
    risk_alerts = []

    # 1. Volatility Weight (20% -> -20 to +20)
    vix_data = data.get('Volatility', {}).get('VIX')
    if vix_data and vix_data['ma_20']:
        vix_price = vix_data['price']
        if vix_price > 20 or vix_price > vix_data['ma_20']:
            score -= 20
        else:
            score += 20
        
        if vix_price > 25:
            risk_alerts.append(f"High Volatility: VIX is extremely elevated at {vix_price:.2f}.")

    # 2. Bond Yield Curve Weight (20% -> -20 to +20)
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
            score += 0 # Flat

    # 3. Equity Momentum Weight (30% -> -30 to +30)
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

    # 4. Macro Inter-market Signals (30% -> -30 to +30)
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

    # Currency Alerts
    for curr_name, curr_data in data.get('Currencies', {}).items():
        if curr_data and abs(curr_data['change']) > 1.5:
            direction = "surged" if curr_data['change'] > 0 else "dropped"
            risk_alerts.append(f"Currency Volatility: {curr_name} {direction} by {abs(curr_data['change']):.2f}%.")

    # Score clamping
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

    return score, regime_text, risk_alerts

def generate_html_email(data, regime_score, regime_text, risk_alerts):
    """Generates the HTML content for the email report."""
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            h2 {{ color: #0a192f; border-bottom: 2px solid #0a192f; padding-bottom: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ padding: 10px; border: 1px solid #ddd; text-align: right; }}
            th {{ background-color: #f4f4f4; text-align: left; }}
            td:first-child {{ text-align: left; font-weight: bold; }}
            .positive {{ color: green; }}
            .negative {{ color: red; }}
            .score-box {{ padding: 15px; background: #eef2f5; border-left: 5px solid #0a192f; margin-bottom: 20px; }}
            .alerts {{ background: #fff3f3; border-left: 5px solid #d9534f; padding: 15px; }}
        </style>
    </head>
    <body>
        <h2>Market Regime Report - {datetime.now().strftime('%Y-%m-%d')}</h2>
        
        <div class="score-box">
            <h3>Executive Summary</h3>
            <p><strong>Market Sentiment Score:</strong> {regime_score} / 100</p>
            <p><strong>Current Phase:</strong> {regime_text}</p>
        </div>
    """

    if risk_alerts:
        html += "<div class='alerts'><h3>Risk Alerts</h3><ul>"
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
                html += f"<tr><td>{name}</td><td colspan='3' style='text-align:center;'>Data Unavailable</td></tr>"
        html += "</table>"

    html += """
    </body>
    </html>
    """
    return html

def send_email(html_content):
    """Sends the HTML report via Gmail SMTP."""
    sender_email = os.environ.get('GMAIL_USER')
    sender_password = os.environ.get('GMAIL_APP_PASSWORD')
    receiver_email = os.environ.get('EMAIL_TO')

    if not all([sender_email, sender_password, receiver_email]):
        logging.error("Email credentials or EMAIL_TO not set in environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"Daily Market Analysis Report - {datetime.now().strftime('%Y-%m-%d')}"
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
    score, regime, alerts = calculate_market_regime(market_data)
    
    logging.info(f"Calculated Regime Score: {score} ({regime})")
    
    html_report = generate_html_email(market_data, score, regime, alerts)
    send_email(html_report)
    logging.info("Pipeline execution completed.")
