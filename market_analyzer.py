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
    'Volatility': {
        'VIX': {'symbol': '^VIX', 'currency': 'Points'}
    },
    'Bonds': {
        'US 1-Year (SHY)': {'symbol': 'SHY', 'currency': 'USD'},
        'US 13-Week': {'symbol': '^IRX', 'currency': 'Yield %'},
        'US 5Y': {'symbol': '^FVX', 'currency': 'Yield %'},
        'US 10Y': {'symbol': '^TNX', 'currency': 'Yield %'},
        'US 30Y': {'symbol': '^TYX', 'currency': 'Yield %'},
        'Corp Bonds (LQD)': {'symbol': 'LQD', 'currency': 'USD'},
        'High Yield (HYG)': {'symbol': 'HYG', 'currency': 'USD'},
        'Intl Treasury Bonds (IGOV)': {'symbol': 'IGOV', 'currency': 'USD'},
        'Emerging Market Bonds (EMB)': {'symbol': 'EMB', 'currency': 'USD'}
    },
    'Commodities': {
        'Brent Crude': {'symbol': 'BZ=F', 'currency': 'USD'},
        'WTI Crude': {'symbol': 'CL=F', 'currency': 'USD'},
        'Natural Gas': {'symbol': 'NG=F', 'currency': 'USD'},
        'Gold': {'symbol': 'GC=F', 'currency': 'USD'},
        'Silver': {'symbol': 'SI=F', 'currency': 'USD'},
        'Copper': {'symbol': 'HG=F', 'currency': 'USD'},
        'Platinum': {'symbol': 'PL=F', 'currency': 'USD'},
        'Wheat': {'symbol': 'ZW=F', 'currency': 'USD'},
        'Corn': {'symbol': 'ZC=F', 'currency': 'USD'}
    },
    'Global Futures & Proxies': {
        'S&P 500 Futures': {'symbol': 'ES=F', 'currency': 'USD'},
        'Nasdaq 100 Futures': {'symbol': 'NQ=F', 'currency': 'USD'},
        'Dow Jones Futures': {'symbol': 'YM=F', 'currency': 'USD'},
        'Germany Market Proxy (EWG)': {'symbol': 'EWG', 'currency': 'USD'},
        'UK Market Proxy (EWU)': {'symbol': 'EWU', 'currency': 'USD'},
        'Japan Market Proxy (EWJ)': {'symbol': 'EWJ', 'currency': 'USD'}
    },
    'Global Indices': {
        'UK FTSE 100': {'symbol': '^FTSE', 'currency': 'GBP'},
        'France CAC 40': {'symbol': '^FCHI', 'currency': 'EUR'},
        'Germany DAX': {'symbol': '^GDAXI', 'currency': 'EUR'},
        'Italy FTSE MIB': {'symbol': 'FTSEMIB.MI', 'currency': 'EUR'},
        'Canada TSX': {'symbol': '^GSPTSE', 'currency': 'CAD'},
        'Brazil Bovespa': {'symbol': '^BVSP', 'currency': 'BRL'},
        'Turkey BIST 100': {'symbol': 'XU100.IS', 'currency': 'TRY'},
        'Australia ASX 200': {'symbol': '^AXJO', 'currency': 'AUD'},
        'China Shanghai': {'symbol': '000001.SS', 'currency': 'CNY'},
        'Taiwan Weighted': {'symbol': '^TWII', 'currency': 'TWD'}
    },
    'US Indices': {
        'S&P 500': {'symbol': '^GSPC', 'currency': 'USD'}, 
        'Nasdaq 100': {'symbol': '^NDX', 'currency': 'USD'}, 
        'Dow Jones': {'symbol': '^DJI', 'currency': 'USD'}
    },
    'Asian Indices': {
        'Nikkei 225': {'symbol': '^N225', 'currency': 'JPY'}, 
        'TOPIX (ETF)': {'symbol': '1306.T', 'currency': 'JPY'}, 
        'Kospi': {'symbol': '^KS11', 'currency': 'KRW'}, 
        'Hang Seng': {'symbol': '^HSI', 'currency': 'HKD'}, 
        'Sensex': {'symbol': '^BSESN', 'currency': 'INR'}, 
        'Nifty 50': {'symbol': '^NSEI', 'currency': 'INR'}, 
        'BSE 500 (Nifty 500 Proxy)': {'symbol': 'BSE-500.BO', 'currency': 'INR'}, 
        'Nifty Midcap 50': {'symbol': '^NSEMDCP50', 'currency': 'INR'}, 
        'Nifty Next 50 (ETF)': {'symbol': 'JUNIORBEES.NS', 'currency': 'INR'}
    },
    'Sectors & Themes (US ETFs)': {
        'AI Stocks': {'symbol': 'AIQ', 'currency': 'USD'},
        'Semiconductor': {'symbol': 'SMH', 'currency': 'USD'},
        'Technology': {'symbol': 'XLK', 'currency': 'USD'},
        'Health Care': {'symbol': 'XLV', 'currency': 'USD'},
        'Space': {'symbol': 'ARKX', 'currency': 'USD'},
        'Metals & Mining': {'symbol': 'XME', 'currency': 'USD'},
        'Energy': {'symbol': 'XLE', 'currency': 'USD'},
        'Consumer Discretionary': {'symbol': 'XLY', 'currency': 'USD'},
        'Industrials': {'symbol': 'XLI', 'currency': 'USD'},
        'Banking': {'symbol': 'KBE', 'currency': 'USD'},
        'Finance': {'symbol': 'XLF', 'currency': 'USD'},
        'Auto': {'symbol': 'CARZ', 'currency': 'USD'}
    },
    'Top 10 Thematic ETFs': {
        'Semiconductors (SOXX)': {'symbol': 'SOXX', 'currency': 'USD'},
        'Robotics & AI (BOTZ)': {'symbol': 'BOTZ', 'currency': 'USD'},
        'Global Financials (IXG)': {'symbol': 'IXG', 'currency': 'USD'},
        'Broad Commodities (DBC)': {'symbol': 'DBC', 'currency': 'USD'},
        'Autonomous & EVs (DRIV)': {'symbol': 'DRIV', 'currency': 'USD'},
        'Cybersecurity (CIBR)': {'symbol': 'CIBR', 'currency': 'USD'},
        'Clean Energy (ICLN)': {'symbol': 'ICLN', 'currency': 'USD'},
        'Cloud Computing (CLOU)': {'symbol': 'CLOU', 'currency': 'USD'},
        'Global Infrastructure (IGF)': {'symbol': 'IGF', 'currency': 'USD'},
        'Biotechnology (IBB)': {'symbol': 'IBB', 'currency': 'USD'}
    },
    'Currencies': {
        'EUR/USD': {'symbol': 'EURUSD=X', 'currency': 'USD'}, 
        'EUR/INR': {'symbol': 'EURINR=X', 'currency': 'INR'}, 
        'USD/JPY': {'symbol': 'JPY=X', 'currency': 'JPY'}, 
        'JPY/INR': {'symbol': 'JPYINR=X', 'currency': 'INR'}, 
        'USD/INR': {'symbol': 'INR=X', 'currency': 'INR'}, 
        'USD/CNY (Yuan)': {'symbol': 'CNY=X', 'currency': 'CNY'},
        'AUD/USD': {'symbol': 'AUDUSD=X', 'currency': 'USD'},
        'USD/SGD': {'symbol': 'SGD=X', 'currency': 'SGD'}
    }
}

def fetch_asset_data(ticker_symbol):
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
        hist = ticker.history(period="3y")

        if not hist.empty:
            hist.index = hist.index.tz_localize(None)
            latest_close = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else latest_close
            daily_change = ((latest_close - prev_close) / prev_close) * 100
            
            ma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else None
            ma_20 = hist['Close'].rolling(window=20).mean().iloc[-1] if len(hist) >= 20 else None
            
            current_year = datetime.now().year
            ytd_data = hist[hist.index.year == current_year]
            ytd_return = None
            if not ytd_data.empty:
                start_of_year_price = ytd_data['Close'].iloc[0]
                ytd_return = ((latest_close - start_of_year_price) / start_of_year_price) * 100
                
            three_yr_return = None
            three_years_ago_date = datetime.now() - pd.DateOffset(years=3)
            past_data = hist[hist.index >= three_years_ago_date]
            if not past_data.empty and len(hist) > 500:
                three_yr_ago_price = past_data['Close'].iloc[0]
                three_yr_return = ((latest_close - three_yr_ago_price) / three_yr_ago_price) * 100
            
            return {
                'price': latest_close,
                'change': daily_change,
                'ma_50': ma_50,
                'ma_20': ma_20,
                'ytd_return': ytd_return,
                'three_yr_return': three_yr_return
            }
    except Exception as e:
        logging.warning(f"yfinance failed for {ticker_symbol}: {e}")

    av_api_key = os.environ.get('ALPHA_VANTAGE_API_KEY')
    if av_api_key:
        logging.info(f"Attempting Alpha Vantage fallback for {ticker_symbol}")
        try:
            symbol_clean = ticker_symbol.replace('^', '').replace('=F', '').replace('=X', '')
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol_clean}&apikey={av_api_key}&outputsize=full"
            response = requests.get(url)
            data = response.json()
            if "Time Series (Daily)" in data:
                ts = data["Time Series (Daily)"]
                df = pd.DataFrame.from_dict(ts, orient='index')
                df = df.rename(columns={'4. close': 'Close'})
                df['Close'] = df['Close'].astype(float)
                df.index = pd.to_datetime(df.index)
                df.index = df.index.tz_localize(None)
                df = df.sort_index()
                
                if len(df) > 0:
                    latest_close = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[-2] if len(df) > 1 else latest_close
                    daily_change = ((latest_close - prev_close) / prev_close) * 100
                    
                    ma_50 = df['Close'].rolling(window=50).mean().iloc[-1] if len(df) >= 50 else None
                    ma_20 = df['Close'].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else None
                    
                    current_year = datetime.now().year
                    ytd_data = df[df.index.year == current_year]
                    ytd_return = None
                    if not ytd_data.empty:
                        start_of_year_price = ytd_data['Close'].iloc[0]
                        ytd_return = ((latest_close - start_of_year_price) / start_of_year_price) * 100
                        
                    three_yr_return = None
                    three_years_ago_date = datetime.now() - pd.DateOffset(years=3)
                    past_data = df[df.index >= three_years_ago_date]
                    if not past_data.empty and len(df) > 500:
                        three_yr_ago_price = past_data['Close'].iloc[0]
                        three_yr_return = ((latest_close - three_yr_ago_price) / three_yr_ago_price) * 100
                    
                    return {
                        'price': latest_close,
                        'change': daily_change,
                        'ma_50': ma_50,
                        'ma_20': ma_20,
                        'ytd_return': ytd_return,
                        'three_yr_return': three_yr_return
                    }
        except Exception as e:
            logging.error(f"Alpha Vantage fallback failed for {ticker_symbol}: {e}")
            
    logging.error(f"All data fetch methods failed for {ticker_symbol}")
    return None

def fetch_global_news():
    news_items = []
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        proxy = os.environ.get('YAHOO_PROXY') or os.environ.get('WORKER_URL')
        if proxy:
            proxies = {'http': proxy, 'https': proxy}
            session.proxies.update(proxies)
        
        tickers = ['SPY', 'GLD', 'SHY']
        for t in tickers:
            ticker = yf.Ticker(t, session=session)
            n = ticker.news
            if n:
                for item in n:
                    news_items.append({
                        'title': item.get('title', ''),
                        'publisher': item.get('publisher', 'News'),
                        'link': item.get('link', '#'),
                        'time': item.get('providerPublishTime', 0)
                    })
            time.sleep(1)
            
        unique_news = {item['title']: item for item in news_items if item['title']}
        sorted_news = sorted(unique_news.values(), key=lambda x: x['time'], reverse=True)
        return sorted_news[:6]
    except Exception as e:
        logging.warning(f"Failed to fetch news: {e}")
        return []

def collect_market_data():
    all_data = {}
    for category, assets in TICKERS_CONFIG.items():
        all_data[category] = {}
        for name, info in assets.items():
            symbol = info['symbol']
            currency = info['currency']
            logging.info(f"Fetching data for {name} ({symbol})")
            
            data = fetch_asset_data(symbol)
            if data:
                data['currency'] = currency
            all_data[category][name] = data
            
            time.sleep(2) 
    return all_data

def get_executive_summary_analysis(data, regime_score):
    if regime_score <= -50:
        regional_rec = "Safe Havens (Bonds & Gold). Equities are in a severe contraction phase. Cash and fixed income are preferred."
    else:
        us_above_50 = 0
        us_total = 0
        us_avg_dist = 0.0
        us_leaders = []
        for name, metrics in data.get('US Indices', {}).items():
            if metrics and metrics['ma_50']:
                us_total += 1
                dist = ((metrics['price'] / metrics['ma_50']) - 1) * 100
                us_avg_dist += dist
                if dist > 0:
                    us_above_50 += 1
                    us_leaders.append((name, dist))
        if us_total > 0: us_avg_dist /= us_total
        us_leaders.sort(key=lambda x: x[1], reverse=True)

        asia_above_50 = 0
        asia_total = 0
        asia_avg_dist = 0.0
        asia_leaders = []
        for name, metrics in data.get('Asian Indices', {}).items():
            if metrics and metrics['ma_50']:
                asia_total += 1
                dist = ((metrics['price'] / metrics['ma_50']) - 1) * 100
                asia_avg_dist += dist
                if dist > 0:
                    asia_above_50 += 1
                    asia_leaders.append((name, dist))
        if asia_total > 0: asia_avg_dist /= asia_total
        asia_leaders.sort(key=lambda x: x[1], reverse=True)

        us_ratio = (us_above_50 / us_total) if us_total > 0 else 0
        asian_ratio = (asia_above_50 / asia_total) if asia_total > 0 else 0
        
        if regime_score >= 10:
            if us_ratio >= asian_ratio and us_ratio >= 0.5:
                leader_str = f"led by {us_leaders[0][0]} (+{us_leaders[0][1]:.2f}% above MA)" if us_leaders else ""
                regional_rec = f"US Equities. {us_above_50} out of {us_total} tracked US indices are in a confirmed uptrend, {leader_str}. Western markets show strong relative strength with an average premium of {us_avg_dist:.2f}% over their 50-day trendlines."
            elif asian_ratio > us_ratio and asian_ratio >= 0.5:
                leader_str = f"led by {asia_leaders[0][0]} (+{asia_leaders[0][1]:.2f}% above MA)" if asia_leaders else ""
                regional_rec = f"Asian Equities. {asia_above_50} out of {asia_total} Asian indices are trading above their 50-day moving average, {leader_str}. Eastern markets are currently outperforming the West."
            else:
                regional_rec = "Broad Equities. Markets are expanding globally, but momentum is relatively dispersed without a single heavily dominant region."
        else: 
            if us_ratio > 0.6:
                regional_rec = f"Selective US Equities. Market is mixed, but US large-caps hold their trends better than international peers ({us_above_50}/{us_total} in uptrend)."
            elif asian_ratio > 0.6:
                regional_rec = f"Selective Asian Equities. Eastern markets are showing resilience ({asia_above_50}/{asia_total} in uptrend) compared to Western weakness."
            else:
                regional_rec = "Defensive Equities & Commodities (Gold, Silver). Markets lack clear directional momentum. Avoid broad index funds."

    sector_data = data.get('Sectors & Themes (US ETFs)', {})
    valid_sectors = {name: metrics for name, metrics in sector_data.items() if metrics and metrics['ma_50']}
    
    momentum_name = "N/A"
    value_name = "N/A"
    long_term_name = "N/A"
    lt_reason = ""
    
    if valid_sectors:
        momentum_sector = max(valid_sectors.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
        mom_metrics = momentum_sector[1]
        dist_mom = ((mom_metrics['price'] / mom_metrics['ma_50']) - 1) * 100
        ytd_str = f" and an explosive +{mom_metrics['ytd_return']:.2f}% YTD return" if mom_metrics.get('ytd_return') else ""
        momentum_name = f"{momentum_sector[0]}. This sector is displaying extreme relative strength, trading +{dist_mom:.2f}% above its 50-day average{ytd_str}. Capital is heavily rotating here for short-term alpha."
        
        value_names = ['Energy', 'Finance', 'Industrials', 'Banking', 'Metals & Mining']
        value_sectors = {k: v for k, v in valid_sectors.items() if k in value_names}
        if value_sectors:
            best_value = max(value_sectors.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
            dist_val = ((best_value[1]['price'] / best_value[1]['ma_50']) - 1) * 100
            ytd_val_str = f" and {best_value[1]['ytd_return']:.2f}% YTD" if best_value[1].get('ytd_return') else ""
            value_name = f"{best_value[0]}. Accumulating value, trading {dist_val:.2f}% relative to its 50-day MA{ytd_val_str}."
            
        long_term_candidates = ['Semiconductor', 'AI Stocks', 'Technology', 'Health Care', 'Space']
        lt_sectors = {k: v for k, v in valid_sectors.items() if k in long_term_candidates}
        if lt_sectors:
            best_lt = max(lt_sectors.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
            long_term_name = best_lt[0]
            dist_lt = ((best_lt[1]['price'] / best_lt[1]['ma_50']) - 1) * 100
            lt_reason = f"Selected because it is currently trading +{dist_lt:.2f}% above its 50-day moving average, showing the strongest structural uptrend among our tracked secular growth themes (Tech, AI, Health, Space)."

    broad_indices = {}
    broad_indices.update(data.get('US Indices', {}))
    broad_indices.update(data.get('Global Indices', {}))
    broad_indices.update(data.get('Asian Indices', {}))
    valid_broad = {name: metrics for name, metrics in broad_indices.items() if metrics and metrics['ma_50']}
    lt_broad_name = "N/A"
    lt_broad_reason = ""
    if valid_broad:
        best_broad = max(valid_broad.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
        dist_broad = ((best_broad[1]['price'] / best_broad[1]['ma_50']) - 1) * 100
        ytd_str = f" and {best_broad[1]['ytd_return']:.2f}% YTD" if best_broad[1].get('ytd_return') else ""
        lt_broad_name = f"{best_broad[0]} Index Fund"
        lt_broad_reason = f"Selected as the strongest broad-market index globally, trending +{dist_broad:.2f}% above its 50-day moving average{ytd_str}."

    bonds = data.get('Bonds', {})
    valid_bonds = {name: metrics for name, metrics in bonds.items() if metrics and metrics['ma_50']}
    lt_bond_name = "N/A"
    lt_bond_reason = ""
    if valid_bonds:
        best_lt_bond = max(valid_bonds.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
        lt_bond_name = best_lt_bond[0]
        dist_lt_bond = ((best_lt_bond[1]['price'] / best_lt_bond[1]['ma_50']) - 1) * 100
        lt_bond_reason = f"Selected because it is trading +{dist_lt_bond:.2f}% above its 50-day average."

    commodities = data.get('Commodities', {})
    valid_commodities = {name: metrics for name, metrics in commodities.items() if metrics and metrics['ma_50']}
    lt_commodity_name = "N/A"
    lt_commodity_reason = ""
    if valid_commodities:
        best_lt_comm = max(valid_commodities.items(), key=lambda x: x[1]['price'] / x[1]['ma_50'])
        lt_commodity_name = best_lt_comm[0]
        dist_lt_comm = ((best_lt_comm[1]['price'] / best_lt_comm[1]['ma_50']) - 1) * 100
        lt_commodity_reason = f"Selected because it is trading +{dist_lt_comm:.2f}% above its 50-day average."

    def get_short_term_pick(asset_dict):
        valid = {name: metrics for name, metrics in asset_dict.items() if metrics and metrics['ma_20'] and metrics['change'] > 0}
        if valid:
            best = max(valid.items(), key=lambda x: x[1]['price'] / x[1]['ma_20'])
            dist = ((best[1]['price'] / best[1]['ma_20']) - 1) * 100
            return f"{best[0]} (+{dist:.2f}% above 20-Day MA, Up {best[1]['change']:.2f}% Today)"
        return "No clear short-term momentum"

    st_equity = get_short_term_pick(sector_data)
    st_commodity = get_short_term_pick(commodities)
    st_bond = get_short_term_pick(bonds)
    st_currency = get_short_term_pick(data.get('Currencies', {}))

    return regional_rec, momentum_name, value_name, long_term_name, lt_reason, lt_broad_name, lt_broad_reason, lt_bond_name, lt_bond_reason, lt_commodity_name, lt_commodity_reason, st_equity, st_commodity, st_bond, st_currency

def calculate_market_regime(data):
    score = 0
    risk_alerts = []

    vix_data = data.get('Volatility', {}).get('VIX')
    if vix_data and vix_data['ma_20']:
        vix_price = vix_data['price']
        if vix_price < 16 and vix_price < vix_data['ma_20']:
            score += 20  
        elif vix_price <= 20 and vix_price < vix_data['ma_20']:
            score += 10  
        elif vix_price > 20:
            score -= 20  
        if vix_price > 25:
            risk_alerts.append(f"High Volatility: VIX is extremely elevated at {vix_price:.2f}.")

    yield_10y_data = data.get('Bonds', {}).get('US 10Y')
    yield_30y_data = data.get('Bonds', {}).get('US 30Y')
    
    if yield_10y_data and yield_30y_data:
        spread = yield_30y_data['price'] - yield_10y_data['price']
        if spread < 0:
            score -= 20
            risk_alerts.append(f"Yield Curve Inversion: US 10Y > US 30Y (Spread: {spread:.2f}%) - Recession signal.")
        elif spread > 0.8:
            score += 20 
        elif spread > 0.3:
            score += 10 
        else:
            score += 0  

    sp500 = data.get('US Indices', {}).get('S&P 500')
    nikkei = data.get('Asian Indices', {}).get('Nikkei 225')
    nifty = data.get('Asian Indices', {}).get('Nifty 50')
    
    equity_score = 0
    for asset, name in zip([sp500, nikkei, nifty], ['S&P 500', 'Nikkei 225', 'Nifty 50']):
        if asset and asset['ma_50'] and asset['ma_20']:
            if asset['price'] > asset['ma_20'] and asset['price'] > asset['ma_50']:
                equity_score += 10  
            elif asset['price'] > asset['ma_50']:
                equity_score += 5   
            else:
                equity_score -= 10  
                risk_alerts.append(f"Momentum Warning: {name} is trading below its 50-day moving average.")
    score += equity_score

    gold = data.get('Commodities', {}).get('Gold')
    copper = data.get('Commodities', {}).get('Copper')
    
    risk_on_signals = 0
    valid_data_points = 0
    
    if gold: 
        valid_data_points += 1
        if gold['change'] < 0: risk_on_signals += 1 
    if copper:
        valid_data_points += 1
        if copper['change'] > 0: risk_on_signals += 1 
    if sp500:
        valid_data_points += 1
        if sp500['change'] > 0: risk_on_signals += 1 
        
    if valid_data_points >= 2:
        if risk_on_signals == valid_data_points:
            score += 30 
        elif risk_on_signals >= valid_data_points - 1:
            score += 10 
        else:
            score -= 30 

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

    regional_rec, mom_sector, val_sector, lt_sector, lt_reason, lt_broad_name, lt_broad_reason, lt_bond_name, lt_bond_reason, lt_commodity_name, lt_commodity_reason, st_equity, st_commodity, st_bond, st_currency = get_executive_summary_analysis(data, score)

    return score, regime_text, risk_alerts, regional_rec, mom_sector, val_sector, lt_sector, lt_reason, lt_broad_name, lt_broad_reason, lt_bond_name, lt_bond_reason, lt_commodity_name, lt_commodity_reason, st_equity, st_commodity, st_bond, st_currency

def generate_html_email(data, regime_score, regime_text, risk_alerts, regional_rec, mom_sector, val_sector, lt_sector, lt_reason, lt_broad, lt_broad_reason, lt_bond, lt_bond_reason, lt_comm, lt_comm_reason, st_eq, st_comm, st_bond, st_curr, news_items):
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            h2 {{ color: #0a192f; border-bottom: 2px solid #0a192f; padding-bottom: 5px; margin-top: 30px; }}
            h3 {{ color: #1a365d; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.95em; }}
            th, td {{ padding: 8px; border: 1px solid #ddd; text-align: right; }}
            th {{ background-color: #f4f4f4; text-align: left; }}
            th:nth-child(n+3), td:nth-child(n+3) {{ text-align: right; }}
            td:nth-child(1) {{ text-align: left; font-weight: bold; width: 25%; }}
            td:nth-child(2) {{ text-align: center; color: #666; font-size: 0.9em; }}
            .positive {{ color: green; font-weight: bold; }}
            .negative {{ color: red; font-weight: bold; }}
            .score-box {{ padding: 20px; background: #eef2f5; border-left: 5px solid #0a192f; margin-bottom: 20px; }}
            .alerts {{ background: #fff3f3; border-left: 5px solid #d9534f; padding: 15px; }}
            .recommendation {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #16a34a; padding: 15px; margin-top: 15px; }}
            .st-momentum {{ background: #fffbeeb3; border: 1px solid #fde68a; border-left: 5px solid #d97706; padding: 15px; margin-top: 15px; }}
            .summary-item {{ margin-bottom: 8px; }}
            .reasoning {{ font-size: 0.9em; color: #555; margin-left: 20px; }}
        </style>
    </head>
    <body>
        <h2>Market Regime Report - {datetime.now().strftime('%Y-%m-%d')}</h2>
        
        <div class="score-box">
            <h3>Executive Summary</h3>
            <div class="summary-item"><strong>Market Sentiment Score:</strong> {regime_score} / 100</div>
            <div class="summary-item"><strong>Current Phase:</strong> {regime_text}</div>
            
            <div class="recommendation">
                <h4 style="margin-top: 0; margin-bottom: 15px;">Long-Term Strategic Picks & Regional Insights</h4>
                <div class="summary-item"><strong>🌍 Best Region to Buy:</strong> {regional_rec}</div>
                <div class="summary-item"><strong>🚀 Top Equity Sector (Growth):</strong> {mom_sector}</div>
                <div class="summary-item"><strong>⚖️ Top Equity Sector (Value):</strong> {val_sector}</div>
                <div class="summary-item" style="margin-top: 10px;"><strong>🌎 Best Broad-Market Index Fund:</strong> {lt_broad}</div>
                <div class="reasoning"><em>{lt_broad_reason}</em></div>
                <div class="summary-item" style="margin-top: 10px;"><strong>💎 Best Long-Term Thematic Sector:</strong> {lt_sector}</div>
                <div class="reasoning"><em>{lt_reason}</em></div>
                <div class="summary-item" style="margin-top: 10px;"><strong>🏦 Best Long-Term Bond:</strong> {lt_bond}</div>
                <div class="reasoning"><em>{lt_bond_reason}</em></div>
                <div class="summary-item" style="margin-top: 10px;"><strong>⛏️ Best Long-Term Commodity:</strong> {lt_comm}</div>
                <div class="reasoning"><em>{lt_comm_reason}</em></div>
            </div>

            <div class="st-momentum">
                <h4 style="margin-top: 0; margin-bottom: 15px;">Short-Term Momentum / Swing Trades (Strongest 20-Day Trend)</h4>
                <div class="summary-item"><strong>📈 Top Equity Pick:</strong> {st_eq}</div>
                <div class="summary-item"><strong>🪙 Top Commodity Pick:</strong> {st_comm}</div>
                <div class="summary-item"><strong>💵 Top Bond Pick:</strong> {st_bond}</div>
                <div class="summary-item"><strong>💱 Top Currency Pick:</strong> {st_curr}</div>
            </div>
        </div>
    """

    if news_items:
        html += "<div class='score-box' style='background: #f8f9fa; border-left: 5px solid #6c757d;'>"
        html += "<h4 style='margin-top: 0; margin-bottom: 15px;'>📰 What to watch out for this week (Major Events)</h4>"
        html += "<ul style='margin-bottom:0;'>"
        for item in news_items:
            html += f"<li style='margin-bottom: 8px;'><a href='{item['link']}' style='color: #1a0dab; text-decoration: none;'>{item['title']}</a> <span style='color: #666; font-size: 0.85em;'>- {item['publisher']}</span></li>"
        html += "</ul></div>"

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
                <th>Currency</th>
                <th>Current Price</th>
                <th>Daily Change</th>
                <th>50-Day MA</th>
                <th>YTD Return</th>
                <th>3-Year Return</th>
            </tr>
        """
        for name, metrics in assets.items():
            if metrics:
                change_class = "positive" if metrics['change'] >= 0 else "negative"
                change_sign = "+" if metrics['change'] >= 0 else ""
                
                ma_50_str = f"{metrics['ma_50']:.2f}" if metrics['ma_50'] else "N/A"
                currency_str = metrics.get('currency', 'N/A')
                
                ytd_val = metrics.get('ytd_return')
                three_yr_val = metrics.get('three_yr_return')
                
                if ytd_val is not None:
                    ytd_class = "positive" if ytd_val >= 0 else "negative"
                    ytd_sign = "+" if ytd_val >= 0 else ""
                    ytd_str = f"<span class='{ytd_class}'>{ytd_sign}{ytd_val:.2f}%</span>"
                else:
                    ytd_str = "N/A"
                    
                if three_yr_val is not None:
                    three_yr_class = "positive" if three_yr_val >= 0 else "negative"
                    three_yr_sign = "+" if three_yr_val >= 0 else ""
                    three_yr_str = f"<span class='{three_yr_class}'>{three_yr_sign}{three_yr_val:.2f}%</span>"
                else:
                    three_yr_str = "N/A"
                
                html += f"""
                <tr>
                    <td>{name}</td>
                    <td>{currency_str}</td>
                    <td>{metrics['price']:.2f}</td>
                    <td class="{change_class}">{change_sign}{metrics['change']:.2f}%</td>
                    <td>{ma_50_str}</td>
                    <td>{ytd_str}</td>
                    <td>{three_yr_str}</td>
                </tr>
                """
            else:
                html += f"<tr><td>{name}</td><td colspan='6' style='text-align:center; color: #999;'>Data Unavailable</td></tr>"
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
    news_items = fetch_global_news()
    score, regime, alerts, rec_regional, rec_mom, rec_val, rec_lt, lt_reason, lt_broad, lt_broad_reason, lt_bond, lt_bond_reason, lt_comm, lt_comm_reason, st_eq, st_comm, st_bond, st_curr = calculate_market_regime(market_data)
    
    logging.info(f"Calculated Regime Score: {score} ({regime})")
    
    html_report = generate_html_email(market_data, score, regime, alerts, rec_regional, rec_mom, rec_val, rec_lt, lt_reason, lt_broad, lt_broad_reason, lt_bond, lt_bond_reason, lt_comm, lt_comm_reason, st_eq, st_comm, st_bond, st_curr, news_items)
    send_email(html_report)
    logging.info("Pipeline execution completed.")
