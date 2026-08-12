import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timezone, timedelta
import logging
import requests
import time
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

JST = timezone(timedelta(hours=9))

def jst_today_str():
    return datetime.now(timezone.utc).astimezone(JST).strftime('%Y-%m-%d')

def _valid(x):
    """True if x is a real, usable number."""
    return x is not None and not (isinstance(x, float) and math.isnan(x))

def _minify_html(html):
    """Strip whitespace to stay under Gmail's ~102KB clipping limit."""
    lines = (line.strip() for line in html.splitlines())
    return "\n".join(line for line in lines if line)

_FETCH_CACHE = {}

def fetch_asset_data(ticker_symbol):
    if ticker_symbol in _FETCH_CACHE:
        return _FETCH_CACHE[ticker_symbol]

    RATE_LIMIT_RETRIES = 3
    RATE_LIMIT_BACKOFF_SEC = [5, 15, 30]
    hist = None
    for attempt in range(RATE_LIMIT_RETRIES):
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
            break
        except Exception as e:
            is_rate_limit = 'rate limit' in str(e).lower() or 'too many requests' in str(e).lower()
            if is_rate_limit and attempt < RATE_LIMIT_RETRIES - 1:
                wait_s = RATE_LIMIT_BACKOFF_SEC[attempt]
                logging.warning(f"yfinance rate-limited for {ticker_symbol}, retrying in {wait_s}s (attempt {attempt + 1}/{RATE_LIMIT_RETRIES}): {e}")
                time.sleep(wait_s)
                continue
            logging.warning(f"yfinance failed for {ticker_symbol}: {e}")
            hist = None
            break

    def extract_metrics(hist_df):
        if hist_df is None or hist_df.empty:
            return None
        hist_df = hist_df[hist_df['Close'].notna()]
        if hist_df.empty:
            return None
        
        hist_df.index = hist_df.index.tz_localize(None)
        latest_close = hist_df['Close'].iloc[-1]
        prev_close = hist_df['Close'].iloc[-2] if len(hist_df) > 1 else latest_close
        daily_change = ((latest_close - prev_close) / prev_close) * 100

        ma_50 = hist_df['Close'].rolling(window=50).mean().iloc[-1] if len(hist_df) >= 50 else None
        ma_20 = hist_df['Close'].rolling(window=20).mean().iloc[-1] if len(hist_df) >= 20 else None
        ma_200 = hist_df['Close'].rolling(window=200).mean().iloc[-1] if len(hist_df) >= 200 else None
        five_day_return = None
        if len(hist_df) > 5:
            price_5d_ago = hist_df['Close'].iloc[-6]
            five_day_return = ((latest_close - price_5d_ago) / price_5d_ago) * 100

        current_year = datetime.now().year
        ytd_data = hist_df[hist_df.index.year == current_year]
        ytd_return = None
        if not ytd_data.empty:
            start_of_year_price = ytd_data['Close'].iloc[0]
            ytd_return = ((latest_close - start_of_year_price) / start_of_year_price) * 100

        three_yr_return = None
        three_years_ago_date = datetime.now() - pd.DateOffset(years=3)
        past_data = hist_df[hist_df.index >= three_years_ago_date]
        if not past_data.empty and len(hist_df) > 500:
            three_yr_ago_price = past_data['Close'].iloc[0]
            three_yr_return = ((latest_close - three_yr_ago_price) / three_yr_ago_price) * 100
            
        one_yr_return = None
        one_year_ago_date = datetime.now() - pd.DateOffset(years=1)
        one_yr_data = hist_df[hist_df.index >= one_year_ago_date]
        if not one_yr_data.empty and len(hist_df) > 200:
            one_yr_ago_price = one_yr_data['Close'].iloc[0]
            one_yr_return = ((latest_close - one_yr_ago_price) / one_yr_ago_price) * 100

        volume = hist_df['Volume'].iloc[-1] if 'Volume' in hist_df.columns else None
        avg_volume_20 = hist_df['Volume'].rolling(window=20).mean().iloc[-1] if 'Volume' in hist_df.columns and len(hist_df) >= 20 else None
        
        last_year_data = hist_df.iloc[-252:] if len(hist_df) >= 252 else hist_df
        high_52w = last_year_data['High'].max() if 'High' in last_year_data.columns else last_year_data['Close'].max()
        low_52w = last_year_data['Low'].min() if 'Low' in last_year_data.columns else last_year_data['Close'].min()
        
        rsi_14 = calc_rsi(hist_df['Close'], 14) if len(hist_df) >= 15 else None
        
        daily_returns = hist_df['Close'].pct_change()
        daily_returns_std_20 = daily_returns.rolling(window=20).std().iloc[-1] if len(daily_returns) >= 20 else None
            
        return {
            'price': latest_close,
            'change': daily_change,
            'ma_50': ma_50,
            'ma_20': ma_20,
            'ma_200': ma_200,
            'five_day_return': five_day_return,
            'ytd_return': ytd_return,
            'three_yr_return': three_yr_return,
            'volume': volume,
            'avg_volume_20': avg_volume_20,
            'high_52w': high_52w,
            'low_52w': low_52w,
            'rsi_14': rsi_14,
            'one_yr_return': one_yr_return,
            'daily_returns_std_20': daily_returns_std_20
        }

    try:
        if hist is not None:
            metrics = extract_metrics(hist)
            if metrics:
                _FETCH_CACHE[ticker_symbol] = metrics
                return metrics
    except Exception as e:
        logging.warning(f"yfinance extraction failed for {ticker_symbol}: {e}")

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
                df = df.rename(columns={'1. open': 'Open', '2. high': 'High', '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'})
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df.columns:
                        df[col] = df[col].astype(float)
                df.index = pd.to_datetime(df.index)
                df = df.sort_index()
                
                metrics = extract_metrics(df)
                if metrics:
                    _FETCH_CACHE[ticker_symbol] = metrics
                    return metrics
        except Exception as e:
            logging.error(f"Alpha Vantage fallback failed for {ticker_symbol}: {e}")
            
    logging.error(f"All data fetch methods failed for {ticker_symbol}")
    return None

def fetch_bulk_data(symbols, period='3y'):
    """Bulk fetch using yfinance.download() for efficiency with large symbol lists.
    Returns a dict of {symbol: metrics_dict} where metrics_dict has the same
    fields as fetch_asset_data().
    Uses yf.download() with threads=True for parallel fetching.
    Includes retry logic and NaN handling."""
    RATE_LIMIT_RETRIES = 3
    RATE_LIMIT_BACKOFF_SEC = [5, 15, 30]
    
    results = {}
    if not symbols:
        return results

    symbols_to_fetch = [s for s in symbols if s not in _FETCH_CACHE]
    
    for s in symbols:
        if s in _FETCH_CACHE:
            results[s] = _FETCH_CACHE[s]
            
    if not symbols_to_fetch:
        return results

    df = None
    for attempt in range(RATE_LIMIT_RETRIES):
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                'Accept': '*/*',
            })
            proxy = os.environ.get('YAHOO_PROXY') or os.environ.get('WORKER_URL')
            if proxy:
                session.proxies.update({'http': proxy, 'https': proxy})

            df = yf.download(" ".join(symbols_to_fetch), period=period, threads=True, progress=False, session=session)
            break
        except Exception as e:
            is_rate_limit = 'rate limit' in str(e).lower() or 'too many requests' in str(e).lower()
            if is_rate_limit and attempt < RATE_LIMIT_RETRIES - 1:
                wait_s = RATE_LIMIT_BACKOFF_SEC[attempt]
                logging.warning(f"yfinance bulk rate-limited, retrying in {wait_s}s: {e}")
                time.sleep(wait_s)
                continue
            logging.warning(f"yfinance bulk fetch failed: {e}")
            break

    if df is None or df.empty:
        return results
        
    def extract_metrics(hist_df):
        if hist_df is None or hist_df.empty:
            return None
        hist_df = hist_df[hist_df['Close'].notna()]
        if hist_df.empty:
            return None
        
        hist_df.index = hist_df.index.tz_localize(None)
        latest_close = hist_df['Close'].iloc[-1]
        prev_close = hist_df['Close'].iloc[-2] if len(hist_df) > 1 else latest_close
        daily_change = ((latest_close - prev_close) / prev_close) * 100

        ma_50 = hist_df['Close'].rolling(window=50).mean().iloc[-1] if len(hist_df) >= 50 else None
        ma_20 = hist_df['Close'].rolling(window=20).mean().iloc[-1] if len(hist_df) >= 20 else None
        ma_200 = hist_df['Close'].rolling(window=200).mean().iloc[-1] if len(hist_df) >= 200 else None
        five_day_return = None
        if len(hist_df) > 5:
            price_5d_ago = hist_df['Close'].iloc[-6]
            five_day_return = ((latest_close - price_5d_ago) / price_5d_ago) * 100

        current_year = datetime.now().year
        ytd_data = hist_df[hist_df.index.year == current_year]
        ytd_return = None
        if not ytd_data.empty:
            start_of_year_price = ytd_data['Close'].iloc[0]
            ytd_return = ((latest_close - start_of_year_price) / start_of_year_price) * 100

        three_yr_return = None
        three_years_ago_date = datetime.now() - pd.DateOffset(years=3)
        past_data = hist_df[hist_df.index >= three_years_ago_date]
        if not past_data.empty and len(hist_df) > 500:
            three_yr_ago_price = past_data['Close'].iloc[0]
            three_yr_return = ((latest_close - three_yr_ago_price) / three_yr_ago_price) * 100

        one_yr_return = None
        one_year_ago_date = datetime.now() - pd.DateOffset(years=1)
        one_yr_data = hist_df[hist_df.index >= one_year_ago_date]
        if not one_yr_data.empty and len(hist_df) > 200:
            one_yr_ago_price = one_yr_data['Close'].iloc[0]
            one_yr_return = ((latest_close - one_yr_ago_price) / one_yr_ago_price) * 100

        volume = hist_df['Volume'].iloc[-1] if 'Volume' in hist_df.columns else None
        avg_volume_20 = hist_df['Volume'].rolling(window=20).mean().iloc[-1] if 'Volume' in hist_df.columns and len(hist_df) >= 20 else None
        
        last_year_data = hist_df.iloc[-252:] if len(hist_df) >= 252 else hist_df
        high_52w = last_year_data['High'].max() if 'High' in last_year_data.columns else last_year_data['Close'].max()
        low_52w = last_year_data['Low'].min() if 'Low' in last_year_data.columns else last_year_data['Close'].min()
        
        rsi_14 = calc_rsi(hist_df['Close'], 14) if len(hist_df) >= 15 else None
        
        daily_returns = hist_df['Close'].pct_change()
        daily_returns_std_20 = daily_returns.rolling(window=20).std().iloc[-1] if len(daily_returns) >= 20 else None

        return {
            'price': latest_close,
            'change': daily_change,
            'ma_50': ma_50,
            'ma_20': ma_20,
            'ma_200': ma_200,
            'five_day_return': five_day_return,
            'ytd_return': ytd_return,
            'three_yr_return': three_yr_return,
            'volume': volume,
            'avg_volume_20': avg_volume_20,
            'high_52w': high_52w,
            'low_52w': low_52w,
            'rsi_14': rsi_14,
            'one_yr_return': one_yr_return,
            'daily_returns_std_20': daily_returns_std_20
        }

    is_multi = isinstance(df.columns, pd.MultiIndex)
    
    for s in symbols_to_fetch:
        try:
            if is_multi:
                if s in df.columns.get_level_values(1):
                    hist = df.xs(s, level=1, axis=1)
                else:
                    hist = None
            else:
                if len(symbols_to_fetch) == 1:
                    hist = df
                else:
                    hist = None
                    
            if hist is not None and not hist.empty:
                metrics = extract_metrics(hist)
                if metrics:
                    results[s] = metrics
                    _FETCH_CACHE[s] = metrics
        except Exception as e:
            logging.warning(f"Error processing bulk data for {s}: {e}")
            
    return results

def calc_growth_score(m):
    mult = -1 if m.get('currency') == 'Yield %' else 1
    p50 = mult * (((m.get('price', 0) / m['ma_50']) - 1) * 100 if m.get('ma_50') else 0)
    p20 = mult * (((m.get('price', 0) / m['ma_20']) - 1) * 100 if m.get('ma_20') else 0)
    ytd = mult * (m.get('ytd_return') or 0)
    return (p50 * 0.4) + (p20 * 0.3) + (ytd * 0.3)

def calc_value_score(m):
    mult = -1 if m.get('currency') == 'Yield %' else 1
    p50 = mult * (((m.get('price', 0) / m['ma_50']) - 1) * 100 if m.get('ma_50') else 0)
    ytd = mult * (m.get('ytd_return') or 0)
    daily = mult * (m.get('change') or 0)
    five_day = mult * (m.get('five_day_return') or 0)
    price = m.get('price', 0)
    ma_200 = m.get('ma_200')
    p200 = mult * (((price / ma_200) - 1) * 100) if ma_200 else None
    
    if ytd < -15:
        return -9999
    if ytd < -8 and daily < -2:
        return -9999
    if p50 < -15:
        return -9999
    if p200 is not None and p200 < -25:
        return -9999
    if m.get('five_day_return') is not None and five_day < -5:
        return -9999
    return -p50 + (ytd * 0.1)

def rank_by_lt_score(pool_dict):
    items = list(pool_dict.items())
    n = len(items)
    if n == 0:
        return []
    if n == 1:
        return items

    def mult_of(m):
        return -1 if m.get('currency') == 'Yield %' else 1

    def pct_rank(values):
        order = sorted(range(n), key=lambda i: values[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2 / (n - 1)
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
            i = j + 1
        return ranks

    tyr_vals = [mult_of(m) * (m.get('three_yr_return') or 0) for _, m in items]
    ytd_vals = [mult_of(m) * (m.get('ytd_return') or 0) for _, m in items]
    p50_vals = [mult_of(m) * (((m.get('price', 0) / m['ma_50']) - 1) * 100 if m.get('ma_50') else 0) for _, m in items]

    tyr_ranks = pct_rank(tyr_vals)
    ytd_ranks = pct_rank(ytd_vals)
    p50_ranks = pct_rank(p50_vals)

    blended = [tyr_ranks[i] * 0.5 + ytd_ranks[i] * 0.3 + p50_ranks[i] * 0.2 for i in range(n)]
    return [item for item, _ in sorted(zip(items, blended), key=lambda x: x[1], reverse=True)]

def calc_momentum_score(m):
    mult = -1 if m.get('currency') == 'Yield %' else 1
    p20 = mult * (((m.get('price', 0) / m['ma_20']) - 1) * 100 if m.get('ma_20') else 0)
    daily = mult * (m.get('change') or 0)
    return (p20 * 0.7) + (daily * 0.3)

def calc_quality_score(m):
    mult = -1 if m.get('currency') == 'Yield %' else 1
    price = m.get('price', 0)
    daily = mult * (m.get('change') or 0)
    ytd = mult * (m.get('ytd_return') or 0)
    tyr = mult * (m.get('three_yr_return') or 0)
    p20 = mult * (((price / m['ma_20']) - 1) * 100) if m.get('ma_20') else 0
    p50 = mult * (((price / m['ma_50']) - 1) * 100) if m.get('ma_50') else 0
    signals = [daily, p20, p50, ytd, tyr]
    thresholds = [2, 4, 8, 15, 40]
    return sum(min(20, (s / t) * 20) for s, t in zip(signals, thresholds) if s > 0)

def _quality_alignment_count(m):
    mult = -1 if m.get('currency') == 'Yield %' else 1
    price = m.get('price', 0)
    signals = [
        mult * (m.get('change') or 0),
        mult * (((price / m['ma_20']) - 1) * 100) if m.get('ma_20') else 0,
        mult * (((price / m['ma_50']) - 1) * 100) if m.get('ma_50') else 0,
        mult * (m.get('ytd_return') or 0),
        mult * (m.get('three_yr_return') or 0),
    ]
    return sum(1 for s in signals if s > 0)

def get_quality_pick(asset_dict):
    valid = {name: metrics for name, metrics in asset_dict.items() if metrics and metrics.get('ma_20') and metrics.get('ma_50')}
    if valid:
        ranked = sorted(valid.items(), key=lambda x: calc_quality_score(x[1]), reverse=True)
        top3 = ", ".join(f"{n} ({calc_quality_score(m):.1f})" for n, m in ranked[:3])
        logging.info(f"[Pick debug] Quality candidates (top 3 of {len(ranked)}): {top3}")
        best = ranked[0]
        aligned = _quality_alignment_count(best[1])
        return f"{best[0]} (positive across {aligned}/5 tracked timeframes)"
    return "No clear quality leader"

def calc_rsi(closes, period=14):
    """Calculate RSI (Relative Strength Index) using Wilder's method.
    Takes a pandas Series of close prices. Returns RSI value (0-100)."""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty and pd.notna(rsi.iloc[-1]) else None

def calc_risk_adjusted_return(ytd_return, daily_returns_std_20d):
    """Sharpe-like ratio: YTD return / 20-day volatility.
    Returns None if volatility is zero or data insufficient."""
    if ytd_return is None or daily_returns_std_20d is None or daily_returns_std_20d == 0:
        return None
    return ytd_return / daily_returns_std_20d

def send_email(html_content, subject, from_name='VilfinTV Daily Screener'):
    sender_email = os.environ.get('GMAIL_USER')
    sender_password = os.environ.get('GMAIL_APP_PASSWORD')
    receiver_email = os.environ.get('EMAIL_TO')

    if not all([sender_email, sender_password, receiver_email]):
        logging.error("Email credentials or EMAIL_TO not set in environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = f"{from_name} <{sender_email}>"
    msg['To'] = receiver_email
    msg.add_header('Reply-To', 'noreply@vilfintv.com')

    bcc_emails = []
    sub_file = os.environ.get('SUBSCRIBER_LIST_FILE')
    if sub_file and os.path.exists(sub_file):
        try:
            import json as _json
            bcc_emails = _json.load(open(sub_file))
            bcc_emails = [e for e in bcc_emails if e and e != 'test@vilfintv.com']
            print(f"Loaded {len(bcc_emails)} subscribers from D1 file")
        except Exception as e:
            logging.error(f"Failed to load subscriber file: {e}")
    else:
        try:
            worker_url = os.environ.get('SUBSCRIBER_WORKER_URL')
            worker_secret = os.environ.get('SUBSCRIBER_WORKER_SECRET')
            if worker_url and worker_secret:
                resp = requests.get(f"{worker_url}?action=list", headers={'Authorization': f"Bearer {worker_secret}"})
                if resp.status_code == 200:
                    bcc_emails = resp.json()
                    bcc_emails = [e for e in bcc_emails if e != 'test@vilfintv.com']
                    print(f"Fetched {len(bcc_emails)} subscribers from Worker")
                else:
                    logging.error(f"Failed to fetch subscribers from Worker: {resp.status_code} {resp.text}")
            else:
                logging.warning("SUBSCRIBER_WORKER_URL or SUBSCRIBER_WORKER_SECRET not set.")
        except Exception as e:
            logging.error(f"Exception fetching subscribers from D1 Worker: {e}")

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        all_recipients = [receiver_email] + bcc_emails
        server.sendmail(sender_email, all_recipients, msg.as_string())
        server.quit()
        logging.info("Successfully sent market report email.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
