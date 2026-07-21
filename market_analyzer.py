import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timezone, timedelta
import logging

# GitHub Actions runners are UTC. This workflow's whole schedule (target
# ~7:00 AM JST, watchdog grace window through 08:40 JST) is built around
# Japan time, but every previous "today's date" in the email/report used
# naive datetime.now() - i.e. the UTC calendar date. Since the run fires at
# 22:00-23:40 UTC, which is already 07:00-08:40 the NEXT day in JST, every
# email was stamping itself with YESTERDAY's date relative to the JST
# reader actually opening it (caught 2026-07-21: an email delivered at
# 07:35 AM JST on the 21st was headered "2026-07-20"). jst_today_str() is
# the fix - always convert through UTC first, then to JST, before taking
# the date, rather than relying on the runner's local system clock.
JST = timezone(timedelta(hours=9))

def jst_today_str():
    return datetime.now(timezone.utc).astimezone(JST).strftime('%Y-%m-%d')
import requests
import time
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _valid(x):
    """True if x is a real, usable number - guards against NaN slipping
    through the `is not None` checks (NaN is never None, so those checks
    alone let 'nan%' leak straight into the report)."""
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _minify_html(html):
    """Strip leading/trailing whitespace and blank lines from the
    generated report. This is plain HTML/CSS email (no <pre>/<script>
    blocks with significant whitespace), so this is purely cosmetic in
    the source and has zero effect on how it renders - but it typically
    cuts the source ~30% smaller, which matters because Gmail clips any
    message whose HTML source exceeds ~102KB ("[Message clipped] View
    entire message"), hiding everything past that point."""
    lines = (line.strip() for line in html.splitlines())
    return "\n".join(line for line in lines if line)

# Configuration for Tickers
TICKERS_CONFIG = {
    'Volatility': {
        'VIX': {'symbol': '^VIX', 'currency': 'Points'},
        'VIX 3-Month': {'symbol': '^VIX3M', 'currency': 'Points'}
    },
    'Bonds': {
        'US 1-Year (SHY)': {'symbol': 'SHY', 'currency': 'USD'},
        'US 13-Week': {'symbol': '^IRX', 'currency': 'USD'},
        'US 5Y': {'symbol': '^FVX', 'currency': 'USD'},
        'US 10Y': {'symbol': '^TNX', 'currency': 'USD'},
        'US 30Y': {'symbol': '^TYX', 'currency': 'USD'},
        'Japan Govt Bonds': {'symbol': '2561.T', 'currency': 'JPY'},
        'Europe/Intl Bonds (BNDX)': {'symbol': 'BNDX', 'currency': 'USD'},
        'UK Govt Bonds': {'symbol': 'IGLT.L', 'currency': 'GBP'},
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
        'Corn': {'symbol': 'ZC=F', 'currency': 'USD'},
        # No raw futures/spot ticker exists on Yahoo for uranium, hydrogen,
        # or lithium/cobalt/nickel (unlike GC=F/HG=F-style continuous
        # futures) - these three are the standard, verified, currently-live
        # ETF proxies used across the industry for that exposure, same
        # "ETF Proxy" pattern already used for Chile/Vietnam/UAE above.
        'Uranium (URA ETF Proxy)': {'symbol': 'URA', 'currency': 'USD'},
        'Battery Metals (LIT ETF Proxy)': {'symbol': 'LIT', 'currency': 'USD'},
        # HDRO trades thin (~70K shares/day vs LIT's ~470K) - its single-day
        # % change is noisier than the other commodities here. Included for
        # coverage, but flagged in the email/site copy rather than treated
        # as equally reliable signal.
        'Hydrogen Economy (HDRO ETF Proxy, thin volume)': {'symbol': 'HDRO', 'currency': 'USD'}
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
        'Spain IBEX 35': {'symbol': '^IBEX', 'currency': 'EUR'},
        'Euro Stoxx 50': {'symbol': '^STOXX50E', 'currency': 'EUR'},
        'STOXX Europe 600': {'symbol': '^STOXX', 'currency': 'EUR'},
        'Switzerland SMI': {'symbol': '^SSMI', 'currency': 'CHF'},
        'Netherlands AEX': {'symbol': '^AEX', 'currency': 'EUR'},
        'Canada TSX': {'symbol': '^GSPTSE', 'currency': 'CAD'},
        'Mexico IPC': {'symbol': '^MXX', 'currency': 'MXN'},
        # ^IPSA has almost no historical data via yfinance (Yahoo only
        # returns 1 row regardless of period requested), so daily
        # change/moving averages could never be computed - this ETF
        # proxy (iShares MSCI Chile) has full, reliable history instead,
        # same pattern already used for Vietnam via the VNM ETF below.
        'Chile IPSA (ETF Proxy)': {'symbol': 'ECH', 'currency': 'USD'},
        'Brazil Bovespa': {'symbol': '^BVSP', 'currency': 'BRL'},
        'Argentina Merval (Buenos Aires)': {'symbol': '^MERV', 'currency': 'ARS'},
        'Turkey BIST 100': {'symbol': 'XU100.IS', 'currency': 'TRY'},
        'Australia ASX 200': {'symbol': '^AXJO', 'currency': 'AUD'},
        'Saudi Arabia TASI': {'symbol': '^TASI.SR', 'currency': 'SAR'},
        'UAE (ETF Proxy)': {'symbol': 'UAE', 'currency': 'USD'},
    },
    'US Indices': {
        'S&P 500': {'symbol': '^GSPC', 'currency': 'USD'},
        'Nasdaq 100': {'symbol': '^NDX', 'currency': 'USD'},
        'Nasdaq Composite': {'symbol': '^IXIC', 'currency': 'USD'},
        'Dow Jones': {'symbol': '^DJI', 'currency': 'USD'},
        'Russell 2000': {'symbol': '^RUT', 'currency': 'USD'},
        'US Total Market (VTI)': {'symbol': 'VTI', 'currency': 'USD'}
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
        'Nifty Midcap 150 (ETF)': {'symbol': 'MID150BEES.NS', 'currency': 'INR'}, 
        'Nifty Smallcap 250 (ETF)': {'symbol': 'HDFCSML250.NS', 'currency': 'INR'},
        'Nifty Next 50 (ETF)': {'symbol': 'JUNIORBEES.NS', 'currency': 'INR'}, 
        'Taiwan Weighted': {'symbol': '^TWII', 'currency': 'TWD'}, 
        'China Shanghai': {'symbol': '000001.SS', 'currency': 'CNY'},
        'Vietnam Index Proxy (VNM)': {'symbol': 'VNM', 'currency': 'USD'},
        'Philippines PSEi': {'symbol': 'PSEI.PS', 'currency': 'PHP'}
    },
    'Top 10 US Stocks': {
        'Apple (AAPL)': {'symbol': 'AAPL', 'currency': 'USD'},
        'Microsoft (MSFT)': {'symbol': 'MSFT', 'currency': 'USD'},
        'Nvidia (NVDA)': {'symbol': 'NVDA', 'currency': 'USD'},
        'Alphabet (GOOGL)': {'symbol': 'GOOGL', 'currency': 'USD'},
        'Amazon (AMZN)': {'symbol': 'AMZN', 'currency': 'USD'},
        'Meta (META)': {'symbol': 'META', 'currency': 'USD'},
        'Tesla (TSLA)': {'symbol': 'TSLA', 'currency': 'USD'},
        'Berkshire (BRK-B)': {'symbol': 'BRK-B', 'currency': 'USD'},
        'Eli Lilly (LLY)': {'symbol': 'LLY', 'currency': 'USD'},
        'Broadcom (AVGO)': {'symbol': 'AVGO', 'currency': 'USD'}
    },
    'Top 10 Asian Stocks': {
        'TSMC (Taiwan)': {'symbol': 'TSM', 'currency': 'USD'},
        'Tencent (China)': {'symbol': 'TCEHY', 'currency': 'USD'},
        'Samsung (Korea)': {'symbol': '005930.KS', 'currency': 'KRW'},
        'Toyota (Japan)': {'symbol': 'TM', 'currency': 'USD'},
        'Alibaba (China)': {'symbol': 'BABA', 'currency': 'USD'},
        'Reliance (India)': {'symbol': 'RELIANCE.NS', 'currency': 'INR'},
        'HDFC Bank (India)': {'symbol': 'HDB', 'currency': 'USD'},
        'Sony (Japan)': {'symbol': 'SONY', 'currency': 'USD'},
        'Keyence (Japan)': {'symbol': '6861.T', 'currency': 'JPY'},
        'ICBC (China)': {'symbol': '1398.HK', 'currency': 'HKD'}
    },
    'Liquidity & Sovereign Risk Indicators (High Weight)': {
        'US 10-Year Yield': {'symbol': '^TNX', 'currency': 'Yield'},
        'US 13-Week Yield': {'symbol': '^IRX', 'currency': 'Yield'},
        'US 30-Year Yield': {'symbol': '^TYX', 'currency': 'Yield'},
        'US Dollar Index': {'symbol': 'DX-Y.NYB', 'currency': 'USD'}
    },
    'Inflation & Input Cost Pressures (Medium Weight)': {
        'Brent Crude Oil': {'symbol': 'BZ=F', 'currency': 'USD'},
        'WTI Crude Oil': {'symbol': 'CL=F', 'currency': 'USD'},
        'Copper Futures': {'symbol': 'HG=F', 'currency': 'USD'},
        'Gold Futures': {'symbol': 'GC=F', 'currency': 'USD'}
    },
    'Macroeconomic Health & Sentiment (High Weight)': {
        'Inflation ETF Proxy (INFL)': {'symbol': 'INFL', 'currency': 'USD'},
        'Industrial ETF Proxy (XLI)': {'symbol': 'XLI', 'currency': 'USD'},
        'Consumer Discretionary (XLY)': {'symbol': 'XLY', 'currency': 'USD'}
    },
    'Supply Chain & Geopolitical Geodesics (Alternative Data)': {
        'Baltic Dry Index Proxy (BDRY)': {'symbol': 'BDRY', 'currency': 'USD'},
        'Volatility Index (VIX)': {'symbol': '^VIX', 'currency': 'Index'},
        'Corn Futures': {'symbol': 'ZC=F', 'currency': 'USD'},
        'Wheat Futures': {'symbol': 'ZW=F', 'currency': 'USD'},
        'Soybean Futures': {'symbol': 'ZS=F', 'currency': 'USD'}
    },
    'Digital Assets & Global Liquidity Barometers': {
        'Bitcoin': {'symbol': 'BTC-USD', 'currency': 'USD'},
        'Ethereum': {'symbol': 'ETH-USD', 'currency': 'USD'}
    },
    'Credit Stress Indicators (Junk Bonds vs Treasuries)': {
        'High Yield Corp Bonds (HYG)': {'symbol': 'HYG', 'currency': 'USD'},
        '7-10 Year Treasuries (IEF)': {'symbol': 'IEF', 'currency': 'USD'}
    },
    'Real Estate & Housing Health': {
        'Real Estate ETF (VNQ)': {'symbol': 'VNQ', 'currency': 'USD'},
        'US Home Construction (ITB)': {'symbol': 'ITB', 'currency': 'USD'}
    },
    'Sectors & Themes (US ETFs)': {
        'AI Stocks': {'symbol': 'AIQ', 'currency': 'USD'},
        'Semiconductor': {'symbol': 'SMH', 'currency': 'USD'},
        'Technology (Information Technology)': {'symbol': 'XLK', 'currency': 'USD'},
        'Health Care': {'symbol': 'XLV', 'currency': 'USD'},
        'Space': {'symbol': 'ARKX', 'currency': 'USD'},
        'Metals & Mining': {'symbol': 'XME', 'currency': 'USD'},
        'Energy': {'symbol': 'XLE', 'currency': 'USD'},
        'Consumer Discretionary': {'symbol': 'XLY', 'currency': 'USD'},
        'Industrials': {'symbol': 'XLI', 'currency': 'USD'},
        'Banking': {'symbol': 'KBE', 'currency': 'USD'},
        'Finance': {'symbol': 'XLF', 'currency': 'USD'},
        'Auto': {'symbol': 'CARZ', 'currency': 'USD'},
        'Communication Services': {'symbol': 'XLC', 'currency': 'USD'},
        'Robotics & Automation': {'symbol': 'BOTZ', 'currency': 'USD'},
        'Consumer Staples': {'symbol': 'XLP', 'currency': 'USD'},
        'Materials': {'symbol': 'XLB', 'currency': 'USD'},
        'Utilities': {'symbol': 'XLU', 'currency': 'USD'},
        'Real Estate': {'symbol': 'XLRE', 'currency': 'USD'},
        'Blockchain': {'symbol': 'BLOK', 'currency': 'USD'},
        'Datacenter': {'symbol': 'SRVR', 'currency': 'USD'}
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
    'Top 10 Broad Market ETFs': {
        'Invesco QQQ (Nasdaq 100)': {'symbol': 'QQQ', 'currency': 'USD'},
        'SPDR S&P 500 (SPY)': {'symbol': 'SPY', 'currency': 'USD'},
        'iShares Russell 2000 (IWM)': {'symbol': 'IWM', 'currency': 'USD'},
        'Vanguard Total Stock (VTI)': {'symbol': 'VTI', 'currency': 'USD'},
        'Vanguard Growth (VUG)': {'symbol': 'VUG', 'currency': 'USD'},
        'Vanguard Value (VTV)': {'symbol': 'VTV', 'currency': 'USD'},
        'SPDR Dow Jones (DIA)': {'symbol': 'DIA', 'currency': 'USD'},
        'ARK Innovation (ARKK)': {'symbol': 'ARKK', 'currency': 'USD'},
        'iShares Emerging Markets (EEM)': {'symbol': 'EEM', 'currency': 'USD'},
        'iShares Developed Markets (EFA)': {'symbol': 'EFA', 'currency': 'USD'},
        'Equal-Weight S&P 500 (RSP)': {'symbol': 'RSP', 'currency': 'USD'}
    },
    'Currencies': {
        'EUR/USD': {'symbol': 'EURUSD=X', 'currency': 'USD'},
        'GBP/USD': {'symbol': 'GBPUSD=X', 'currency': 'USD'},
        'EUR/INR': {'symbol': 'EURINR=X', 'currency': 'INR'},
        'USD/JPY': {'symbol': 'JPY=X', 'currency': 'JPY'},
        'JPY/INR': {'symbol': 'JPYINR=X', 'currency': 'INR'},
        'USD/INR': {'symbol': 'INR=X', 'currency': 'INR'},
        'USD/CNY (Yuan)': {'symbol': 'CNY=X', 'currency': 'CNY'},
        'USD/CHF (Swiss Franc)': {'symbol': 'CHF=X', 'currency': 'CHF'},
        'USD/CAD (Canadian Dollar)': {'symbol': 'CAD=X', 'currency': 'CAD'},
        'AUD/USD': {'symbol': 'AUDUSD=X', 'currency': 'USD'},
        'NZD/USD': {'symbol': 'NZDUSD=X', 'currency': 'USD'},
        'USD/SGD': {'symbol': 'SGD=X', 'currency': 'SGD'},
        'USD/HKD (Hong Kong Dollar)': {'symbol': 'HKD=X', 'currency': 'HKD'},
        'USD/MXN (Mexican Peso)': {'symbol': 'MXN=X', 'currency': 'MXN'},
        'USD/CLP (Chilean Peso)': {'symbol': 'CLP=X', 'currency': 'CLP'},
        'USD/ARS (Argentine Peso)': {'symbol': 'ARS=X', 'currency': 'ARS'}
    }
}

# 'Bonds' mixes real, buyable instruments (SHY, LQD, HYG, BNDX...) with raw
# Treasury YIELD-index tickers (^IRX/^FVX/^TNX/^TYX). Module-level so both
# get_executive_summary_analysis() and the pick-confidence calculation in
# main() filter these out identically rather than risking two definitions
# drifting apart.
YIELD_INDEX_NAMES = {'US 13-Week', 'US 5Y', 'US 10Y', 'US 30Y'}

def fetch_asset_data(ticker_symbol):
    # yfinance occasionally rate-limits a ticker fetched early in the run
    # ("Too Many Requests. Rate limited.") even though the exact same
    # symbol succeeds a few minutes later elsewhere in the same pipeline
    # run (observed 2026-07-17 with ^VIX) - a short retry-with-backoff
    # here resolves most of these without needing the Alpha Vantage
    # fallback, which doesn't support index symbols like ^VIX anyway.
    RATE_LIMIT_RETRIES = 3
    RATE_LIMIT_BACKOFF_SEC = [5, 15, 30]
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

    try:
        if hist is None:
            raise ValueError("yfinance history unavailable after retries")
        # Some tickers (thinly-traded ETFs, exchanges in other timezones,
        # holiday-affected sessions) return a trailing row with a NaN Close
        # before the exchange's data has fully settled. Drop those rows so
        # .iloc[-1] always lands on a real, usable price instead of NaN
        # propagating into every downstream calculation (and into the
        # report as literal "nan%").
        if not hist.empty:
            hist = hist[hist['Close'].notna()]

        if not hist.empty:
            hist.index = hist.index.tz_localize(None)
            latest_close = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else latest_close
            daily_change = ((latest_close - prev_close) / prev_close) * 100

            ma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else None
            ma_20 = hist['Close'].rolling(window=20).mean().iloc[-1] if len(hist) >= 20 else None
            # 200-day MA and 5-day return are both derivable from the SAME
            # 3-year history already being fetched here - zero extra network
            # calls, used by the Value pick's falling-knife guard below.
            ma_200 = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
            five_day_return = None
            if len(hist) > 5:
                price_5d_ago = hist['Close'].iloc[-6]
                five_day_return = ((latest_close - price_5d_ago) / price_5d_ago) * 100

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
                'ma_200': ma_200,
                'five_day_return': five_day_return,
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
                df = df[df['Close'].notna()]

                if len(df) > 0:
                    latest_close = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[-2] if len(df) > 1 else latest_close
                    daily_change = ((latest_close - prev_close) / prev_close) * 100
                    
                    ma_50 = df['Close'].rolling(window=50).mean().iloc[-1] if len(df) >= 50 else None
                    ma_20 = df['Close'].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else None
                    ma_200 = df['Close'].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else None
                    five_day_return = None
                    if len(df) > 5:
                        price_5d_ago = df['Close'].iloc[-6]
                        five_day_return = ((latest_close - price_5d_ago) / price_5d_ago) * 100

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
                        'ma_200': ma_200,
                        'five_day_return': five_day_return,
                        'ytd_return': ytd_return,
                        'three_yr_return': three_yr_return
                    }
        except Exception as e:
            logging.error(f"Alpha Vantage fallback failed for {ticker_symbol}: {e}")
            
    logging.error(f"All data fetch methods failed for {ticker_symbol}")
    return None

import xml.etree.ElementTree as ET

def fetch_global_news():
    news_items = []
    try:
        url = 'https://news.google.com/rss/search?q=stock+market+economy+finance&hl=en-US&gl=US&ceid=US:en'
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        for item in items[:6]:
            news_items.append({
                'title': item.find('title').text,
                'link': item.find('link').text,
                'publisher': item.find('source').text if item.find('source') is not None else 'Google News',
                'time': 0
            })
        unique_news = {item['link']: item for item in news_items}
        return list(unique_news.values())[:6]
    except Exception as e:
        logging.warning(f"Failed to fetch news: {e}")
        return []

# Tickers fetched under more than one TICKERS_CONFIG category (e.g. ^VIX
# appears under both 'Volatility' and the alternative-data pool) shouldn't
# have to survive a rate-limit fight twice in the same run - once a symbol
# fetches successfully, later occurrences in this same run reuse it. A
# failed attempt is NOT cached, so a later occurrence still gets its own
# fresh try (this is exactly how ^VIX recovered on 2026-07-17: it failed
# early in the run but a later independent fetch of the same symbol
# succeeded once the rate limit had cleared).
_FETCH_CACHE = {}

# Tickers important enough to the score that losing them for a day
# shouldn't silently zero out a whole scoring signal - see
# _load_last_known_good() below for how the fallback value is sourced.
CRITICAL_FALLBACK_SYMBOLS = {'^VIX', '^VIX3M'}

def _load_last_known_good(symbol):
    """Last-resort fallback for CRITICAL_FALLBACK_SYMBOLS: reads yesterday's
    (or the most recent) committed data/market_sentiment_snapshot.json for a
    previously-fetched price/ma_20 when today's live fetch (yfinance +
    retries + Alpha Vantage) has genuinely failed. Returns a metrics dict
    with is_stale=True/stale_since set so callers can flag it visibly
    instead of silently treating stale data as fresh, or None if no
    previous snapshot/value is available."""
    try:
        with open("data/market_sentiment_snapshot.json") as f:
            prev = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    cache = prev.get("raw_fallback_cache", {})
    entry = cache.get(symbol)
    if not entry or not _valid(entry.get('price')):
        return None
    return {
        'price': entry['price'],
        'change': 0,
        'ma_50': entry.get('ma_50'),
        'ma_20': entry.get('ma_20'),
        'ma_200': entry.get('ma_200'),
        'five_day_return': None,
        'ytd_return': None,
        'three_yr_return': None,
        'is_stale': True,
        'stale_since': prev.get('date'),
    }

def collect_market_data():
    all_data = {}
    for category, assets in TICKERS_CONFIG.items():
        all_data[category] = {}
        for name, info in assets.items():
            symbol = info['symbol']
            currency = info['currency']
            logging.info(f"Fetching data for {name} ({symbol})")

            data = _FETCH_CACHE.get(symbol)
            if data is None:
                data = fetch_asset_data(symbol)
                if data:
                    _FETCH_CACHE[symbol] = data
                elif symbol in CRITICAL_FALLBACK_SYMBOLS:
                    fallback = _load_last_known_good(symbol)
                    if fallback:
                        logging.warning(f"Using last-known-good fallback for {name} ({symbol}) from {fallback['stale_since']} - live fetch failed")
                        data = fallback
                        _FETCH_CACHE[symbol] = data

            if data:
                data = {**data, 'currency': currency}
            all_data[category][name] = data

            time.sleep(2)
    return all_data

# Liquid, actively-traded FX pairs NOT already in the permanent 'Currencies'
# dashboard above - verified live Yahoo Finance tickers as of 2026-07.
# Scanned separately each run (see find_notable_fx_mover) so a pair having
# an unusually large day gets surfaced automatically, even though nobody
# manually added it to the ~16 pairs tracked every day.
FX_CANDIDATE_POOL = {
    'USD/ZAR (South African Rand)': {'symbol': 'ZAR=X', 'currency': 'ZAR'},
    'USD/TRY (Turkish Lira)': {'symbol': 'TRY=X', 'currency': 'TRY'},
    'USD/BRL (Brazilian Real)': {'symbol': 'BRL=X', 'currency': 'BRL'},
    'EUR/JPY': {'symbol': 'EURJPY=X', 'currency': 'JPY'},
    'GBP/JPY': {'symbol': 'GBPJPY=X', 'currency': 'JPY'},
}

def find_notable_fx_mover(tracked_currencies):
    """Scans FX_CANDIDATE_POOL (pairs NOT already in the main Currencies
    table) and returns (name, data_dict) for whichever pair had the
    biggest absolute daily move - or (None, None) if nothing usable came
    back. The caller merges this into data['Currencies'] before scoring,
    so it automatically flows through the same momentum/value/long-term/
    quality picks and the Asset Dashboard table as every other tracked
    pair, just clearly labeled as auto-detected in the display layer."""
    best_name, best_data, best_abs_change = None, None, -1
    for name, info in FX_CANDIDATE_POOL.items():
        if name in tracked_currencies:
            continue  # already manually tracked under this exact name - skip
        data = fetch_asset_data(info['symbol'])
        time.sleep(2)
        if data and _valid(data.get('change')):
            data['currency'] = info['currency']
            if abs(data['change']) > best_abs_change:
                best_name, best_data, best_abs_change = name, data, abs(data['change'])
    return best_name, best_data

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
    # Falling-knife guards, layered - a single YTD cutoff alone has real
    # gaps a straight -15% YTD threshold misses: an asset 20% below its
    # 50-day MA but only -14% YTD would otherwise score an attractive-
    # looking 20 - 1.4 = 18.6 here (a concrete example that exposed this).
    if ytd < -15:
        return -9999
    if ytd < -8 and daily < -2:
        return -9999
    # An asset can't be "washed out, stabilizing" value if it's THIS far
    # below its own 50-day average - that's still an extended decline, not
    # a dip. Matches the exact gap above (p50 -20% would now be excluded
    # regardless of YTD).
    if p50 < -15:
        return -9999
    # If we have enough history for a 200-day MA, being deeply below it too
    # (not just the shorter 50-day) is additional confirmation of a real
    # structural decline rather than a short-term dip.
    if p200 is not None and p200 < -25:
        return -9999
    # Require some sign of stabilization when the 5-day window is available
    # - still actively falling over the last week isn't "washed out" yet.
    if m.get('five_day_return') is not None and five_day < -5:
        return -9999
    return -p50 + (ytd * 0.1)

def rank_by_lt_score(pool_dict):
    """Long-Term pick ranking, by PERCENTILE RANK rather than raw weighted
    value. Raw 3-year returns run 5-10x larger in magnitude than YTD or
    50-day premium figures (e.g. a themed ETF up 300% over 3 years
    contributes 150 points from that term alone at a nominal 50% weight,
    before any other consideration) - a fixed cap helps but is still an
    arbitrary number. Percentile rank is always bounded 0-1 regardless of
    the underlying value's scale, so being the single best 3-year
    performer in the pool is worth the same whether it's by 300% or by
    30% - one extreme outlier can no longer silently dominate the blend.
    Returns (name, metrics) tuples sorted winner-first, same shape callers
    previously got from max(pool.items(), key=calc_lt_score)."""
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
    """Not a fundamentals factor - no earnings/balance-sheet data flows
    through this pipeline, only price series. 'Quality' here means
    technical CONSISTENCY: is this asset positive across every timeframe
    we track at once (today, 20-day, 50-day, YTD, 3-year), or is it just
    one recent spike propping up an otherwise mixed picture? An asset up
    big today but underwater on its longer averages scores LOWER here
    than a steady all-round performer - the opposite of what Momentum
    rewards, which is exactly the point of having both."""
    mult = -1 if m.get('currency') == 'Yield %' else 1
    price = m.get('price', 0)
    daily = mult * (m.get('change') or 0)
    ytd = mult * (m.get('ytd_return') or 0)
    tyr = mult * (m.get('three_yr_return') or 0)
    p20 = mult * (((price / m['ma_20']) - 1) * 100) if m.get('ma_20') else 0
    p50 = mult * (((price / m['ma_50']) - 1) * 100) if m.get('ma_50') else 0
    signals = [daily, p20, p50, ytd, tyr]
    # Each signal earns UP TO 20 points, scaled by how strongly positive it
    # is relative to a "genuinely strong" reference magnitude for that
    # timeframe (a barely-positive +0.01% shouldn't earn the same credit as
    # a robust move) - capped at 20 so a single extreme outlier still can't
    # dominate the way a flat per-signal count would have let alignment
    # alone do. Reference magnitudes scale with the timeframe: a "strong"
    # single day is a much smaller % than a "strong" 3-year run.
    thresholds = [2, 4, 8, 15, 40]  # daily, 20-day, 50-day, YTD, 3-year
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
    """Best-quality pick for one session/category: the asset trading
    positively across the most timeframes at once (see calc_quality_score),
    used the same way get_short_term_pick() is used for momentum below."""
    valid = {name: metrics for name, metrics in asset_dict.items() if metrics and metrics.get('ma_20') and metrics.get('ma_50')}
    if valid:
        ranked = sorted(valid.items(), key=lambda x: calc_quality_score(x[1]), reverse=True)
        top3 = ", ".join(f"{n} ({calc_quality_score(m):.1f})" for n, m in ranked[:3])
        logging.info(f"[Pick debug] Quality candidates (top 3 of {len(ranked)}): {top3}")
        best = ranked[0]
        aligned = _quality_alignment_count(best[1])
        return f"{best[0]} (positive across {aligned}/5 tracked timeframes)"
    return "No clear quality leader"

# Static, pick-TYPE-level risk/invalidation framing for the JSON snapshot
# (the website's data consumer, not the size-constrained email). This is
# honest about what a purely mechanical, price-only pick can and can't
# tell you - not a fabricated per-instance narrative, since this pipeline
# has no fundamentals data and no backtested per-pick-type hit rate yet.
PICK_TYPE_META = {
    "trending": {
        "risk": "Short-term price momentum can reverse quickly, especially around news events or earnings.",
        "invalidation": "If the asset closes back below its 20-day moving average, the trending thesis is invalidated.",
    },
    "value": {
        "risk": "A washed-out asset can keep falling further before it recovers (\"catching a falling knife\").",
        "invalidation": "Automatically disqualified on the next run if YTD return drops below -15%, or below -8% combined with a sharp same-day drop.",
    },
    "long_term": {
        "risk": "Past 3-year outperformance doesn't guarantee the next 3 years will look the same.",
        "invalidation": "If the 3-year return materially deteriorates on a future run, the structural case weakens.",
    },
    "quality": {
        "risk": "Being positive across every timeframe doesn't mean the moves are large - this measures consistency, not magnitude.",
        "invalidation": "If two or more of the 5 tracked timeframes turn negative, the consistency case breaks down.",
    },
}

def summarize_pick_confidence(asset_dict, calc_fn, require_positive_change=False):
    """Qualitative confidence for a pick, based on how clearly the winner
    separates from the runner-up and how many candidates were even in the
    running - a pick chosen from a close 2-way field is a much weaker
    signal than one that clearly leads a wide one. Re-ranks the same
    candidate pool get_short_term_pick/get_quality_pick already use,
    without touching those functions' tested string-return contract that
    the email directly depends on."""
    if require_positive_change:
        valid = {n: m for n, m in asset_dict.items() if m and m.get('ma_20') and m.get('change') is not None and m['change'] > 0}
    else:
        valid = {n: m for n, m in asset_dict.items() if m and m.get('ma_20') and m.get('ma_50')}
    if len(valid) < 2:
        return "Low (fewer than 2 comparable candidates)"
    ranked = sorted(valid.items(), key=lambda x: calc_fn(x[1]), reverse=True)
    top_score = calc_fn(ranked[0][1])
    second_score = calc_fn(ranked[1][1])
    denom = abs(top_score) if top_score else 1
    gap_pct = abs(top_score - second_score) / denom * 100
    if len(ranked) >= 5 and gap_pct > 20:
        return "High"
    elif gap_pct > 10:
        return "Medium"
    return "Low"

def build_pick_bundle(pick_type, reason_text, confidence, generated_at_iso):
    """Attach the shared reason/risk/invalidation/confidence/timestamp
    structure used throughout the JSON snapshot's 'picks' section."""
    meta = PICK_TYPE_META.get(pick_type, {})
    return {
        "reason": reason_text,
        "risk": meta.get("risk", ""),
        "invalidation": meta.get("invalidation", ""),
        "confidence": confidence,
        "timestamp": generated_at_iso,
    }

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
                leader_str = f"led by {us_leaders[0][0]} ({us_leaders[0][1]:+.2f}% above MA)" if us_leaders else ""
                regional_rec = f"US Equities. {us_above_50} out of {us_total} tracked US indices are in a confirmed uptrend, {leader_str}. US markets show strong relative strength with an average premium of {us_avg_dist:.2f}% over their 50-day trendlines."
            elif asian_ratio > us_ratio and asian_ratio >= 0.5:
                leader_str = f"led by {asia_leaders[0][0]} ({asia_leaders[0][1]:+.2f}% above MA)" if asia_leaders else ""
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
        momentum_sector = max(valid_sectors.items(), key=lambda x: calc_growth_score(x[1]))
        mom_metrics = momentum_sector[1]
        dist_mom = ((mom_metrics['price'] / mom_metrics['ma_50']) - 1) * 100
        ytd_str = f" and an explosive {mom_metrics['ytd_return']:+.2f}% YTD return" if mom_metrics.get('ytd_return') else ""
        mom_direction = "above" if dist_mom >= 0 else "below"
        momentum_name = f"{momentum_sector[0]}. This sector currently shows the strongest relative momentum among tracked sectors, trading {abs(dist_mom):.2f}% {mom_direction} its 50-day average{ytd_str}."
        
        value_names = ['Energy', 'Finance', 'Industrials', 'Banking', 'Metals & Mining']
        value_sectors = {k: v for k, v in valid_sectors.items() if k in value_names}
        if value_sectors:
            ranked_val = sorted(value_sectors.items(), key=lambda x: calc_value_score(x[1]), reverse=True)
            logging.info(f"[Pick debug] Value candidates: {', '.join(f'{n} ({calc_value_score(m):.1f})' for n, m in ranked_val)}")
            best_value = ranked_val[0]
            dist_val = ((best_value[1]['price'] / best_value[1]['ma_50']) - 1) * 100
            ytd_val_str = f" and {best_value[1]['ytd_return']:.2f}% YTD" if best_value[1].get('ytd_return') else ""
            value_name = f"{best_value[0]}. Accumulating value, trading {dist_val:.2f}% relative to its 50-day MA{ytd_val_str}."

        long_term_candidates = ['Semiconductor', 'AI Stocks', 'Technology', 'Health Care', 'Space']
        lt_sectors = {k: v for k, v in valid_sectors.items() if k in long_term_candidates}
        if lt_sectors:
            ranked_lt = rank_by_lt_score(lt_sectors)
            logging.info(f"[Pick debug] Long-Term sector candidates (percentile-ranked, winner first): {', '.join(n for n, _ in ranked_lt)}")
            best_lt = ranked_lt[0]
            long_term_name = best_lt[0]
            tyr = best_lt[1].get('three_yr_return', 0) or 0
            ytd = best_lt[1].get('ytd_return', 0) or 0
            lt_reason = f"Selected based on our multi-factor model. It boasts a powerful {tyr:+.2f}% 3-Year Return and {ytd:+.2f}% YTD, showing the strongest structural uptrend among our tracked secular growth themes."

    broad_indices = {}
    broad_indices.update(data.get('US Indices', {}))
    broad_indices.update(data.get('Global Indices', {}))
    broad_indices.update(data.get('Asian Indices', {}))
    broad_indices.update(data.get('Top 10 Broad Market ETFs', {}))
    valid_broad = {name: metrics for name, metrics in broad_indices.items() if metrics and metrics['ma_50']}
    lt_broad_name = "N/A"
    lt_broad_reason = ""
    if valid_broad:
        best_broad = rank_by_lt_score(valid_broad)[0]
        tyr = best_broad[1].get('three_yr_return', 0) or 0
        ytd = best_broad[1].get('ytd_return', 0) or 0
        lt_broad_name = f"{best_broad[0]} Index"
        lt_broad_reason = f"Selected as the strongest long-term broad-market index globally based on its blended structural performance ({tyr:+.2f}% 3-Year, {ytd:+.2f}% YTD)."

    # 'Bonds' mixes real, buyable instruments (SHY, LQD, HYG, BNDX...) with
    # raw Treasury YIELD-index tickers (^IRX/^FVX/^TNX/^TYX, e.g. "US 30Y"
    # is the 30-year yield level, not a tradable bond). A rising yield
    # generally means falling bond PRICES - the opposite of what "strong
    # momentum" should mean for a bond pick - and there's no real action a
    # reader could take on "buy US 30Y" anyway, so these are excluded from
    # both bond-pick rankings below rather than scored as if investable.
    bonds = {name: metrics for name, metrics in data.get('Bonds', {}).items() if name not in YIELD_INDEX_NAMES}
    valid_bonds = {name: metrics for name, metrics in bonds.items() if metrics and metrics['ma_50']}
    lt_bond_name = "N/A"
    lt_bond_reason = ""
    if valid_bonds:
        best_lt_bond = rank_by_lt_score(valid_bonds)[0]
        lt_bond_name = best_lt_bond[0]
        tyr = best_lt_bond[1].get('three_yr_return', 0) or 0
        ytd = best_lt_bond[1].get('ytd_return', 0) or 0
        lt_bond_reason = f"Selected because it demonstrates massive multi-year strength ({tyr:+.2f}% 3-Year Return, {ytd:+.2f}% YTD) alongside solid current momentum."

    commodities = data.get('Commodities', {})
    valid_commodities = {name: metrics for name, metrics in commodities.items() if metrics and metrics['ma_50']}
    lt_commodity_name = "N/A"
    lt_commodity_reason = ""
    if valid_commodities:
        best_lt_comm = rank_by_lt_score(valid_commodities)[0]
        lt_commodity_name = best_lt_comm[0]
        tyr = best_lt_comm[1].get('three_yr_return', 0) or 0
        ytd = best_lt_comm[1].get('ytd_return', 0) or 0
        lt_commodity_reason = f"Selected because it demonstrates massive multi-year strength ({tyr:+.2f}% 3-Year Return, {ytd:+.2f}% YTD) alongside solid current momentum."

    def get_short_term_pick(asset_dict):
        # Eligibility requires BOTH today's change positive AND the asset
        # actually trading above its own 20-day average - previously only
        # today's change was required, so on a broadly weak day where every
        # eligible candidate happened to still be below its 20-day MA, a
        # merely +0.01%-today asset with no real trend behind it could
        # still win. Requiring p20 > 0 too means "trending" always implies
        # an actual established uptrend, not just a single green tick.
        valid = {
            name: metrics for name, metrics in asset_dict.items()
            if metrics and metrics['ma_20'] and metrics['change'] > 0
            and metrics['price'] > metrics['ma_20']
        }
        if valid:
            ranked = sorted(valid.items(), key=lambda x: calc_momentum_score(x[1]), reverse=True)
            top3 = ", ".join(f"{n} ({calc_momentum_score(m):.1f})" for n, m in ranked[:3])
            logging.info(f"[Pick debug] Trending candidates (top 3 of {len(ranked)}): {top3}")
            best = ranked[0]
            dist = ((best[1]['price'] / best[1]['ma_20']) - 1) * 100
            return f"{best[0]} ({dist:+.2f}% above 20-Day MA, Up {best[1]['change']:+.2f}% latest session)"
        return "No clear short-term momentum"


    st_equity = get_short_term_pick(sector_data)
    st_commodity = get_short_term_pick(commodities)
    st_bond = get_short_term_pick(bonds)
    st_currency = get_short_term_pick(data.get('Currencies', {}))

    qual_equity = get_quality_pick(sector_data)
    qual_commodity = get_quality_pick(commodities)
    qual_bond = get_quality_pick(bonds)
    qual_currency = get_quality_pick(data.get('Currencies', {}))

    return regional_rec, momentum_name, value_name, long_term_name, lt_reason, lt_broad_name, lt_broad_reason, lt_bond_name, lt_bond_reason, lt_commodity_name, lt_commodity_reason, st_equity, st_commodity, st_bond, st_currency, qual_equity, qual_commodity, qual_bond, qual_currency


def get_regime_note(score):
    """Regime-aware framing for the Picks section: how much weight to put
    on Trending/Quality/Value/Long-Term picks changes with the overall
    market regime, even though the underlying calculations themselves
    don't change. This is an interpretive note only - it never filters,
    hides, or re-ranks the actual picks, it just explains which of them
    tend to be more or less reliable in the current environment."""
    if score >= 50:
        return "Bullish Expansion: Trending picks are most reliable here, with a broad tailwind behind them. Quality and Long-Term picks remain solid. Value picks are naturally scarcer in a strong uptrend - fewer assets are genuinely washed out."
    elif score >= 10:
        return "Bullish Leaning: A reasonably balanced environment. Trending picks are gaining conviction, Quality is a solid middle-ground choice, and Value can still be found in laggard sectors that haven't joined the move yet."
    elif score >= -10:
        return "Neutral / Mixed: No strong directional edge across signals, so Trending picks have less confirming behind them than usual. Quality (consistency across timeframes) and Long-Term (structural performance) tend to be the more durable reads in this band."
    elif score >= -50:
        return "Bearish Contraction: Treat Trending/momentum picks with extra caution - an \"up\" mover in a contraction is more likely to be a short-lived bounce. Quality and Value picks carry more relative weight here, though Value's falling-knife guard matters more than ever."
    else:
        return "Extremely Bearish / Risk-Off: Trending picks are least reliable in this band - most short-term \"up\" moves are dead-cat bounces, not real reversals. Quality (consistency) and Long-Term (structural) picks provide more ballast; Value picks need extra scrutiny given how many assets are under genuine stress market-wide."


def get_asset_class_recommendation(score):
    """Maps the final capped Market Sentiment Score to the Asset Class
    Playbook shown on the methodology page - the same 5 score bands used
    for regime_text/the SIP strategy table, just framed as which asset
    classes are favored rather than how to invest via SIP."""
    if score >= 50:
        return "Growth Stocks, Small Caps, Industrial Commodities"
    elif score >= 10:
        return "Broad-Market Indices, High-Yield Bonds"
    elif score >= -10:
        return "Dividend Yielders, Short-Term Bonds, Cash"
    elif score >= -50:
        return "Long-Term Treasuries, Gold, Defensive Stocks"
    else:
        return "US Dollars (Cash), Short Positions, Gold"


def get_global_capital_flow_note(data):
    """Cross-border capital flow read, using data already fetched for the
    scored signals above (no new tickers needed): (a) which of S&P 500 /
    Nikkei 225 / Nifty 50 has the highest premium over its own 50-day
    moving average, as a proxy for where capital is currently
    concentrating, and (b) whether the Dollar Index (DXY) sits above or
    below its own 20-day average, since a strong dollar tends to keep
    capital anchored in US assets while a weak one favors international/EM
    inflows. Returns (flow_alert_str_or_None, dxy_note_str_or_None)."""
    tracked = {
        'S&P 500': data.get('US Indices', {}).get('S&P 500'),
        'Nikkei 225': data.get('Asian Indices', {}).get('Nikkei 225'),
        'Nifty 50': data.get('Asian Indices', {}).get('Nifty 50'),
    }
    valid = {
        name: m for name, m in tracked.items()
        if m and _valid(m.get('price')) and _valid(m.get('ma_50')) and m['ma_50']
    }
    flow_alert = None
    if valid:
        def premium(m):
            return (m['price'] / m['ma_50']) - 1
        best_name, best_metrics = max(valid.items(), key=lambda x: premium(x[1]))
        dist = premium(best_metrics) * 100
        flow_alert = f"🌍 Global Flow Alert: {best_name} is showing the strongest regional momentum, trading {dist:+.2f}% above its 50-day trendline."

    dxy_note = None
    dxy = data.get('Liquidity & Sovereign Risk Indicators (High Weight)', {}).get('US Dollar Index')
    if dxy and _valid(dxy.get('price')) and _valid(dxy.get('ma_20')) and dxy['ma_20']:
        if dxy['price'] < dxy['ma_20']:
            dxy_note = "With the Dollar (DXY) trending lower, conditions are favorable for international and emerging market inflows."
        else:
            dxy_note = "A strong Dollar (DXY) is currently keeping global capital anchored in US assets."

    return flow_alert, dxy_note


def calculate_market_regime(data, fred_extras=None):
    # The 14-signal breakdown (build_score_breakdown) is the single source of
    # truth for both the score and the risk alerts - keeping one definition
    # instead of two avoids the two functions silently drifting apart, which
    # is exactly what happened before this was consolidated.
    breakdown, risk_alerts = build_score_breakdown(data, fred_extras)
    score = sum(item["points"] for item in breakdown)

    # Currency volatility is a pure alert, not a scored signal, so it lives
    # here rather than in the breakdown.
    for curr_name, curr_data in data.get('Currencies', {}).items():
        if curr_data and _valid(curr_data.get('change')) and abs(curr_data['change']) > 1.5:
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

    regional_rec, mom_sector, val_sector, lt_sector, lt_reason, lt_broad_name, lt_broad_reason, lt_bond_name, lt_bond_reason, lt_commodity_name, lt_commodity_reason, st_equity, st_commodity, st_bond, st_currency, qual_equity, qual_commodity, qual_bond, qual_currency = get_executive_summary_analysis(data, score)

    return score, regime_text, risk_alerts, regional_rec, mom_sector, val_sector, lt_sector, lt_reason, lt_broad_name, lt_broad_reason, lt_bond_name, lt_bond_reason, lt_commodity_name, lt_commodity_reason, st_equity, st_commodity, st_bond, st_currency, qual_equity, qual_commodity, qual_bond, qual_currency

def build_score_breakdown(data, fred_extras=None):
    """Structured, JSON-serializable version of the 14 signal checks behind
    the Market Sentiment Score - the single source of truth used by both
    calculate_market_regime() (for the actual score) and the live 'today's
    real report' example on market_sentiment_score.html, so the two can
    never silently drift apart. Returns (breakdown_list, risk_alerts_list)."""
    breakdown = []
    risk_alerts = []
    fred_extras = fred_extras or {}

    vix_data = data.get('Volatility', {}).get('VIX')
    if vix_data and _valid(vix_data.get('ma_20')) and _valid(vix_data.get('price')):
        vix_price = vix_data['price']
        vix_ma20 = vix_data['ma_20']
        if vix_price < 16 and vix_price < vix_ma20:
            pts, note = 20, f"{vix_price:.2f}, below its 20-day average ({vix_ma20:.2f}) — calm (&lt;16)"
        elif vix_price <= 20 and vix_price < vix_ma20:
            pts, note = 10, f"{vix_price:.2f}, below its 20-day average ({vix_ma20:.2f}) — in the 16-20 calm zone"
        elif vix_price > 20:
            pts, note = -20, f"{vix_price:.2f}, above the 20 threshold — elevated fear"
        else:
            pts, note = 0, f"{vix_price:.2f}, above its 20-day average ({vix_ma20:.2f}) — no clear signal"
        if vix_data.get('is_stale'):
            note += f" (⚠️ last known value from {vix_data.get('stale_since', 'a previous day')} — live VIX data was unavailable today)"
        breakdown.append({"label": "VIX (Fear Index)", "reading": note, "points": pts})
        if vix_price > 25:
            risk_alerts.append(f"High Volatility: VIX is extremely elevated at {vix_price:.2f}.")

    y10 = data.get('Bonds', {}).get('US 10Y')
    y30 = data.get('Bonds', {}).get('US 30Y')
    if y10 and y30 and _valid(y10.get('price')) and _valid(y30.get('price')):
        spread = y30['price'] - y10['price']
        if spread < 0:
            pts = -20
        elif spread > 0.8:
            pts = 20
        elif spread > 0.3:
            pts = 10
        else:
            pts = 0
        breakdown.append({
            "label": "Yield Curve — 30Y vs 10Y",
            "reading": f"30Y {y30['price']:.2f}% − 10Y {y10['price']:.2f}% = {spread:+.2f}% spread",
            "points": pts,
        })
        if spread < 0:
            risk_alerts.append(f"Yield Curve Inversion: US 10Y > US 30Y (Spread: {spread:.2f}%) - Recession signal.")

    liq_dict = data.get('Liquidity & Sovereign Risk Indicators (High Weight)', {})
    new_10y = liq_dict.get('US 10-Year Yield')
    new_3m = liq_dict.get('US 13-Week Yield')
    if new_10y and new_3m and _valid(new_10y.get('price')) and _valid(new_3m.get('price')):
        spread_10y_3m = new_10y['price'] - new_3m['price']
        # 10Y-3M inversion is historically the single most reliable
        # recession predictor of any yield-curve pair tracked here, but
        # previously it was fully binary in BOTH directions: any inversion
        # at all scored the same -30 regardless of depth, and any
        # non-inverted spread scored a flat 0 regardless of how healthy.
        # Now graded on both sides - a deep inversion is treated as more
        # severe than a razor-thin one, and a steep healthy curve earns
        # more credit than one sitting right at zero - while keeping the
        # inversion side's penalties larger than the steepening side's
        # rewards on purpose (asymmetric: this curve is watched far more
        # for inversion risk than rewarded for steepness).
        if spread_10y_3m < -0.3:
            pts = -30
        elif spread_10y_3m < 0:
            pts = -15
        elif spread_10y_3m >= 1.2:
            pts = 15
        elif spread_10y_3m >= 0.5:
            pts = 5
        else:
            pts = 0
        depth_note = ""
        if spread_10y_3m < 0:
            depth_note = " (deep inversion)" if spread_10y_3m < -0.3 else " (slight inversion)"
        breakdown.append({
            "label": "Yield Curve — 10Y vs 3-Month",
            "reading": f"10Y {new_10y['price']:.2f}% − 3-month {new_3m['price']:.2f}% = {spread_10y_3m:+.2f}% ({'inverted' if spread_10y_3m < 0 else 'not inverted'}{depth_note})",
            "points": pts,
        })
        if spread_10y_3m < 0:
            risk_alerts.append(f"CRITICAL Yield Curve Inversion: US 13-Week > US 10-Year (Spread: {spread_10y_3m:.2f}%) - Imminent Recession Signal.")

    credit_dict = data.get('Credit Stress Indicators (Junk Bonds vs Treasuries)', {})
    hyg = credit_dict.get('High Yield Corp Bonds (HYG)')
    ief = credit_dict.get('7-10 Year Treasuries (IEF)')
    if hyg and ief and _valid(hyg.get('change')) and _valid(ief.get('change')):
        stressed = hyg['change'] < -1.0 and ief['change'] > 0.5
        # Was binary (-20 or flat 0) - a confirmed absence of stress got no
        # more credit than a borderline reading right at the edge of the
        # stress threshold. Graded to mirror how the other credit/yield
        # checks reward a genuinely healthy state, not just "not stressed".
        risk_on_credit = hyg['change'] > 0.3 and ief['change'] < 0
        if stressed:
            pts = -20
            reading_note = "stress pattern"
        elif risk_on_credit:
            pts = 10
            reading_note = "strong risk-on credit behavior (junk bonds up, safe treasuries down)"
        else:
            pts = 0
            reading_note = "no stress pattern"
        breakdown.append({
            "label": "Credit Stress",
            "reading": f"HYG {hyg['change']:+.2f}%, IEF {ief['change']:+.2f}% same day — {reading_note}",
            "points": pts,
        })
        if stressed:
            risk_alerts.append("Credit Stress Alert: Junk Bonds (HYG) falling while Safe Treasuries (IEF) rally. Liquidity freezing.")

    sp500 = data.get('US Indices', {}).get('S&P 500')
    nikkei = data.get('Asian Indices', {}).get('Nikkei 225')
    nifty = data.get('Asian Indices', {}).get('Nifty 50')
    eq_parts = []
    eq_total = 0
    for asset, name in zip([sp500, nikkei, nifty], ['S&P 500', 'Nikkei', 'Nifty 50']):
        if asset and _valid(asset.get('ma_50')) and _valid(asset.get('ma_20')) and _valid(asset.get('price')):
            if asset['price'] > asset['ma_20'] and asset['price'] > asset['ma_50']:
                p = 10; eq_parts.append(f"{name} above both MAs (+10)")
            elif asset['price'] > asset['ma_50']:
                p = 5; eq_parts.append(f"{name} above 50-day only (+5)")
            else:
                p = -10; eq_parts.append(f"{name} below 50-day (-10)")
                risk_alerts.append(f"Momentum Warning: {name} is trading below its 50-day moving average.")
            eq_total += p
    if eq_parts:
        breakdown.append({"label": "Equity Momentum", "reading": ", ".join(eq_parts), "points": eq_total})

    gold = data.get('Commodities', {}).get('Gold')
    copper = data.get('Commodities', {}).get('Copper')
    risk_on_signals, valid_data_points, ra_parts = 0, 0, []
    if gold and _valid(gold.get('change')):
        valid_data_points += 1
        agree = gold['change'] < 0
        if agree: risk_on_signals += 1
        ra_parts.append(f"Gold {gold['change']:+.2f}% ({'risk-on' if agree else 'risk-off'})")
    if copper and _valid(copper.get('change')):
        valid_data_points += 1
        agree = copper['change'] > 0
        if agree: risk_on_signals += 1
        ra_parts.append(f"Copper {copper['change']:+.2f}% ({'risk-on' if agree else 'risk-off'})")
    if sp500 and _valid(sp500.get('change')):
        valid_data_points += 1
        agree = sp500['change'] > 0
        if agree: risk_on_signals += 1
        ra_parts.append(f"S&P {sp500['change']:+.2f}% ({'risk-on' if agree else 'risk-off'})")
    if valid_data_points >= 2:
        risk_off_signals = valid_data_points - risk_on_signals
        # Symmetric by design: unanimous agreement in either direction is
        # the strongest signal (±30), a clear majority is a moderate signal
        # (±10), and only an exact tie nets to 0. The previous version
        # collapsed "majority risk-off" (e.g. 2 of 3) into the same -30 as
        # unanimous risk-off, while "majority risk-on" correctly got the
        # softer +10 - fixed so both directions are scored the same way.
        if risk_on_signals == valid_data_points:
            pts = 30
        elif risk_off_signals == valid_data_points:
            pts = -30
        elif risk_on_signals > risk_off_signals:
            pts = 10
        elif risk_off_signals > risk_on_signals:
            pts = -10
        else:
            pts = 0
        breakdown.append({
            "label": "Risk Appetite",
            "reading": f"{', '.join(ra_parts)} — {risk_on_signals} of {valid_data_points} signals agreed",
            "points": pts,
        })

    # 7. Market Participation: equal-weight S&P 500 (RSP) vs cap-weight
    # (SPY). If RSP keeps pace with or beats SPY, gains are broad-based; if
    # RSP lags meaningfully, the rally is narrow (a handful of mega-caps
    # carrying it). Deliberately NOT called "breadth" - true breadth is
    # % of stocks above their 200-day average, advance/decline lines, or
    # new-highs-vs-new-lows, none of which are freely available per-stock
    # via this pipeline's data sources. This is a related but distinct
    # relative-strength proxy, labeled as such in the reading text.
    broad_etfs = data.get('Top 10 Broad Market ETFs', {})
    rsp = broad_etfs.get('Equal-Weight S&P 500 (RSP)')
    spy = broad_etfs.get('SPDR S&P 500 (SPY)')
    if rsp and spy and _valid(rsp.get('change')) and _valid(spy.get('change')):
        gap = rsp['change'] - spy['change']
        if gap > 0.1:
            pts = 10
        elif gap < -0.1:
            pts = -10
        else:
            pts = 0
        display_gap = round(rsp['change'], 2) - round(spy['change'], 2)
        breakdown.append({
            "label": "Equal-Weight Participation (Proxy)",
            "reading": f"Equal-weight S&amp;P (RSP) {rsp['change']:+.2f}% vs cap-weight (SPY) {spy['change']:+.2f}% ({display_gap:+.2f}pp gap) — proxy for breadth, not a true advance/decline reading",
            "points": pts,
        })

    # 8. Credit Spread: the ICE BofA US High Yield Index Option-Adjusted
    # Spread (FRED series BAMLH0A0HYM2) - a genuine daily credit-risk-pricing
    # figure (basis points over Treasuries), not a same-day ETF price
    # comparison. Scored primarily on the ABSOLUTE level against
    # widely-recognized credit-cycle bands (below ~3% is historically tight/
    # healthy, above ~6% is genuine stress territory) rather than only its
    # own short-term trailing average - a 10-day average is too easily
    # already-elevated during a slow-building stress episode to reward
    # "still tight relative to itself." A sharp widening move on top of
    # that gets an extra penalty, since the RATE of change matters too.
    credit_spread = fred_extras.get('credit_spread')
    if credit_spread:
        cs_val, cs_date, cs_trailing = credit_spread
        cs_avg = sum(cs_trailing) / len(cs_trailing) if cs_trailing else cs_val
        if cs_val < 3.0:
            pts = 15
        elif cs_val < 4.5:
            pts = 0
        elif cs_val < 6.0:
            pts = -15
        else:
            pts = -25
        widening_fast = cs_val > cs_avg * 1.05
        if widening_fast and pts > -25:
            pts -= 10
        breakdown.append({
            "label": "Credit Spread (HY OAS)",
            "reading": f"ICE BofA US High Yield OAS {cs_val:.2f}% for {cs_date} (recent average {cs_avg:.2f}%) — {'tight, healthy credit market' if cs_val < 3.0 else 'normal range' if cs_val < 4.5 else 'elevated stress' if cs_val < 6.0 else 'severe stress'}{', widening fast' if widening_fast else ''}",
            "points": pts,
        })
        if cs_val >= 6.0 or widening_fast and cs_val >= 4.5:
            risk_alerts.append(f"Credit Spread Warning: High-yield OAS at {cs_val:.2f}% — {'severe stress territory' if cs_val >= 6.0 else 'elevated and widening fast'}, a genuine credit-stress signal.")

    # 9. Labor Market: US initial jobless claims (FRED series ICSA), a
    # genuine weekly labor-market release, not a market-price proxy.
    # Compared to its own recent trailing average since claims are noisy
    # week to week. Weighted more heavily on the downside (rising claims)
    # than the upside, consistent with the other recession-warning signals.
    labor = fred_extras.get('labor_claims')
    if labor:
        latest_val, latest_date, trailing = labor
        avg = sum(trailing) / len(trailing) if trailing else latest_val
        if latest_val < avg * 0.985:
            pts = 10
        elif latest_val > avg * 1.015:
            pts = -20
        else:
            pts = 0
        breakdown.append({
            "label": "Labor Market (Jobless Claims)",
            "reading": f"{latest_val:,.0f} claims for the week of {latest_date} vs {avg:,.0f} recent average",
            "points": pts,
        })
        if latest_val > avg * 1.15:
            risk_alerts.append(f"Labor Market Warning: Initial jobless claims ({latest_val:,.0f}) are spiking well above their recent average ({avg:,.0f}).")

    # 10. Liquidity & Financial Conditions: Chicago Fed National Financial
    # Conditions Index (FRED series NFCI) - the standard professional
    # composite for how loose/tight financial conditions are. Negative =
    # looser than average, positive = tighter than average.
    fin_cond = fred_extras.get('financial_conditions')
    if fin_cond:
        nfci_val, nfci_date, _trailing = fin_cond
        if nfci_val < -0.5:
            pts = 10
        elif nfci_val < 0:
            pts = 5
        elif nfci_val < 0.5:
            pts = -5
        else:
            pts = -15
        breakdown.append({
            "label": "Liquidity &amp; Financial Conditions",
            "reading": f"Chicago Fed NFCI {nfci_val:+.3f} for the week of {nfci_date} — {'looser' if nfci_val < 0 else 'tighter'} than average",
            "points": pts,
        })
        if nfci_val > 0.5:
            risk_alerts.append(f"Financial Conditions Warning: Chicago Fed NFCI at {nfci_val:+.3f} — tighter than average, a genuine stress signal.")

    # 11. Volatility Term Structure: spot VIX vs 3-month VIX (VIX3M).
    # Contango (spot below VIX3M) is the normal, calm state; backwardation
    # (spot above VIX3M) means near-term fear has spiked above longer-term
    # expectations - a classic acute-stress signal.
    vix3m_data = data.get('Volatility', {}).get('VIX 3-Month')
    if vix_data and vix3m_data and _valid(vix_data.get('price')) and _valid(vix3m_data.get('price')) and vix3m_data['price']:
        vt_ratio = vix_data['price'] / vix3m_data['price']
        if vt_ratio < 0.9:
            pts = 15
        elif vt_ratio < 1.0:
            pts = 5
        elif vt_ratio < 1.1:
            pts = -10
        else:
            pts = -20
        vt_reading = f"VIX {vix_data['price']:.2f} vs VIX3M {vix3m_data['price']:.2f} (ratio {vt_ratio:.2f}) — {'contango, calm' if vt_ratio < 1 else 'backwardation, stress'}"
        if vix_data.get('is_stale') or vix3m_data.get('is_stale'):
            vt_reading += " (⚠️ using last known value for one or both legs — live data was unavailable today)"
        breakdown.append({
            "label": "Volatility Term Structure",
            "reading": vt_reading,
            "points": pts,
        })
        if vt_ratio > 1.1:
            risk_alerts.append(f"Volatility Term Structure Warning: VIX ({vix_data['price']:.2f}) above VIX3M ({vix3m_data['price']:.2f}) — backwardation signals acute near-term stress.")

    # 12. Dollar Strength: US Dollar Index (DXY) vs its own 20-day average.
    # A strengthening dollar typically pressures EM assets and commodities
    # (risk-off); a weakening dollar is usually risk-on/liquidity-friendly.
    dxy = data.get('Liquidity & Sovereign Risk Indicators (High Weight)', {}).get('US Dollar Index')
    if dxy and _valid(dxy.get('price')) and _valid(dxy.get('ma_20')):
        if dxy['price'] < dxy['ma_20'] * 0.995:
            pts = 10
        elif dxy['price'] > dxy['ma_20'] * 1.005:
            pts = -10
        else:
            pts = 0
        breakdown.append({
            "label": "Dollar Strength",
            "reading": f"DXY {dxy['price']:.2f} vs its 20-day average {dxy['ma_20']:.2f}",
            "points": pts,
        })

    # 13. Growth vs Defensive Leadership: Consumer Discretionary (XLY) vs
    # Consumer Staples (XLP). Genuine forward-earnings-revision data isn't
    # freely available, so this is deliberately NOT called an "earnings"
    # signal - it's a well-known market-based sector-rotation proxy for
    # growth optimism vs defensive positioning, nothing more. Weighted
    # lightly (not a hard economic release) and reduced from its initial
    # weight since it overlaps with Risk Appetite and Commodities Ratio -
    # a single risk-on/risk-off day can move all three together, so no one
    # of them should swing the score as much as an independent signal would.
    sectors_dict = data.get('Sectors & Themes (US ETFs)', {})
    xly = sectors_dict.get('Consumer Discretionary')
    xlp = sectors_dict.get('Consumer Staples')
    if xly and xlp and _valid(xly.get('change')) and _valid(xlp.get('change')):
        earn_gap = xly['change'] - xlp['change']
        if earn_gap > 0.2:
            pts = 10
        elif earn_gap < -0.2:
            pts = -10
        else:
            pts = 0
        display_earn_gap = round(xly['change'], 2) - round(xlp['change'], 2)
        breakdown.append({
            "label": "Growth vs Defensive Leadership",
            "reading": f"Consumer Discretionary (XLY) {xly['change']:+.2f}% vs Staples (XLP) {xlp['change']:+.2f}% ({display_earn_gap:+.2f}pp gap) — sector-rotation proxy, not an earnings/EPS figure",
            "points": pts,
        })

    # 14. Commodities Ratio: Copper vs Gold ("Dr. Copper" vs the safe-haven
    # metal) - a classic growth-optimism-vs-fear signal. Copper and Gold
    # also feed the Risk Appetite check above, but via DIFFERENT logic:
    # Risk Appetite scores each metal's own ABSOLUTE direction (is gold
    # falling, is copper rising), while this checks their RELATIVE spread.
    # These can genuinely diverge on the same day - e.g. gold -2% and
    # copper -1% both falling reads as risk-off on their own absolute
    # moves, but copper falling LESS than gold is a relatively
    # growth-optimistic spread. That divergence is real, informative
    # information (not a bug to be forced into agreement), which is why
    # this is deliberately weighted lighter (±10 vs Risk Appetite's ±30)
    # as a secondary, relative-only confirmation rather than independent
    # primary evidence.
    if gold and copper and _valid(gold.get('change')) and _valid(copper.get('change')):
        comm_gap = copper['change'] - gold['change']
        if comm_gap > 0.5:
            pts = 10
        elif comm_gap < -0.5:
            pts = -10
        else:
            pts = 0
        display_comm_gap = round(copper['change'], 2) - round(gold['change'], 2)
        reading = f"Copper {copper['change']:+.2f}% vs Gold {gold['change']:+.2f}% ({display_comm_gap:+.2f}pp gap)"
        # Flag it explicitly when this signal's relative-spread read
        # disagrees in direction with both metals simply moving the same
        # absolute way, so the divergence is visible rather than hidden.
        if copper['change'] > 0 and gold['change'] > 0 and pts < 0:
            reading += " — both up, but copper lagging gold (relatively risk-off despite both rising)"
        elif copper['change'] < 0 and gold['change'] < 0 and pts > 0:
            reading += " — both down, but copper falling less than gold (relatively risk-on despite both falling)"
        breakdown.append({
            "label": "Commodities Ratio (Copper vs Gold)",
            "reading": reading,
            "points": pts,
        })

    return breakdown, risk_alerts


def fetch_fred_series(series_id, lookback=8):
    """Fetch a public FRED economic series via its no-auth CSV export
    (https://fred.stlouisfed.org/graph/fredgraph.csv?id=<series>) - no API
    key required, unlike the Alpha Vantage macro data below. Returns
    (latest_value, latest_date_str, trailing_values) or None on failure."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        lines = [l for l in resp.text.strip().split("\n") if l]
        rows = [l.split(",") for l in lines[1:]]  # skip header row
        rows = [(d, v) for d, v in rows if v not in ("", ".")]
        if not rows:
            return None
        trailing = [float(v) for _, v in rows[-lookback:]]
        latest_date, latest_val = rows[-1][0], float(rows[-1][1])
        return latest_val, latest_date, trailing
    except Exception as e:
        logging.warning(f"FRED fetch failed for {series_id}: {e}")
        return None


def fetch_fred_change(series_id, months_back, lookback_months=18):
    """Fetch a monthly FRED series and compute the change from
    `months_back` months ago to the latest value, matched by actual
    calendar date rather than list position - FRED occasionally omits a
    month before revising it in later (e.g. CPIAUCSL has a gap around
    2025-10), so a fixed-position offset would silently compare the wrong
    months. Returns (latest_value, latest_date, prior_value) - the caller
    computes either a percent change (for CPI YoY inflation) or an
    absolute difference (for payrolls MoM), whichever is conventional for
    that series. Returns None on failure or if no data point near the
    target month exists."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        lines = [l for l in resp.text.strip().split("\n") if l]
        rows = [l.split(",") for l in lines[1:]]
        rows = [(d, float(v)) for d, v in rows if v not in ("", ".")]
        if not rows:
            return None
        rows = rows[-lookback_months:]
        latest_date, latest_val = rows[-1]
        latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
        target_year = latest_dt.year
        target_month = latest_dt.month - months_back
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        target_dt = latest_dt.replace(year=target_year, month=target_month)
        prior_candidates = [r for r in rows[:-1]]
        if not prior_candidates:
            return None
        prior_date, prior_val = min(
            prior_candidates,
            key=lambda r: abs((datetime.strptime(r[0], "%Y-%m-%d") - target_dt).days),
        )
        if abs((datetime.strptime(prior_date, "%Y-%m-%d") - target_dt).days) > 45:
            return None  # no data point close enough to the target month
        return latest_val, latest_date, prior_val
    except Exception as e:
        logging.warning(f"FRED change fetch failed for {series_id}: {e}")
        return None


def build_fred_macro_text(fred_extras):
    """Format all FRED-sourced macro data (labor claims, financial
    conditions, CPI, payrolls) into '• <b>Label:</b> value<br>' lines for
    the email. Everything here uses FRED's no-auth CSV export, so unlike
    the old Alpha-Vantage-gated version of this section, it doesn't depend
    on ALPHA_VANTAGE_API_KEY being set or valid - which was unverifiable
    from this pipeline (no success-path logging existed, so a silently
    missing/invalid key and a working one were indistinguishable) and that
    endpoint's response was also being displayed with a unit bug: Alpha
    Vantage's NONFARM_PAYROLL returns a cumulative employment LEVEL (~159
    million, in thousands), not a monthly change, so labeling it "Non-Farm
    Payrolls: <level> thousand" read like a monthly jobs-added figure when
    it was nothing of the kind. CPI here is now a proper year-over-year
    inflation rate and payrolls a proper month-over-month change, both
    matched by calendar date so a gap in the source series (FRED
    occasionally omits a month before revising it in) can't silently
    compare the wrong two months."""
    text = ""
    labor = fred_extras.get('labor_claims')
    if labor:
        latest_val, latest_date, trailing = labor
        avg = sum(trailing) / len(trailing) if trailing else latest_val
        text += f"• <b>Initial Jobless Claims (Labor Market):</b> {latest_val:,.0f} for the week of {latest_date}, vs {avg:,.0f} recent average<br>"
    fin_cond = fred_extras.get('financial_conditions')
    if fin_cond:
        nfci_val, nfci_date, _trailing = fin_cond
        text += f"• <b>Chicago Fed Financial Conditions Index:</b> {nfci_val:+.3f} for the week of {nfci_date} ({'looser' if nfci_val < 0 else 'tighter'} than average)<br>"
    cpi = fred_extras.get('cpi_yoy')
    if cpi and cpi[2]:
        cpi_val, cpi_date, cpi_prior_val = cpi
        cpi_yoy_pct = (cpi_val - cpi_prior_val) / cpi_prior_val * 100
        text += f"• <b>Consumer Price Index (CPI), YoY:</b> {cpi_yoy_pct:+.1f}% for {cpi_date} (index level {cpi_val:.1f})<br>"
    payrolls = fred_extras.get('payrolls_mom')
    if payrolls:
        pay_val, pay_date, pay_prior_val = payrolls
        pay_mom_change = pay_val - pay_prior_val
        text += f"• <b>Non-Farm Payrolls, MoM change:</b> {pay_mom_change:+,.0f}K jobs for {pay_date} (total employed {pay_val/1000:.1f}M)<br>"
    net_liq = fred_extras.get('net_liquidity')
    if net_liq:
        walcl, tga, rrp = net_liq
        # All three are FRED series in different native units (WALCL and
        # WTREGEN are millions of dollars, RRPONTSYD is billions) - converted
        # to a common $B basis here. WALCL/WTREGEN update weekly (Wednesdays)
        # and RRPONTSYD daily, so their "latest" dates won't always match;
        # each is labeled with its own date rather than implying same-day data.
        walcl_val, walcl_date, _ = walcl
        tga_val, tga_date, _ = tga
        rrp_val, rrp_date, _ = rrp
        net_liquidity_b = (walcl_val / 1000) - (tga_val / 1000) - rrp_val
        text += f"• <b>Fed Net Liquidity (Balance Sheet − TGA − Reverse Repo):</b> ${net_liquidity_b:,.0f}B (balance sheet {walcl_date}, TGA {tga_date}, reverse repo {rrp_date}) — a rising figure has historically coincided with looser system-wide liquidity for risk assets<br>"
    return text

def generate_html_email(data, regime_score, regime_text, risk_alerts, macro_text, news_items, regional_rec, mom_sector, val_sector, lt_sector, lt_reason, lt_broad, lt_broad_reason, lt_bond, lt_bond_reason, lt_comm, lt_comm_reason, st_eq, st_comm, st_bond, st_curr, qual_eq, qual_comm, qual_bond, qual_curr, notable_fx=None):
    html = f"""<html><head><style>\nbody {{ font-family: Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}\nh2 {{ color: #0a192f; margin-top: 30px; }}\nh3 {{ color: #1a365d; }}\ntable {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.95em; }}\nth, td {{ padding: 8px; border: 1px solid #ddd; text-align: center; }}\nth {{ background-color: #f4f4f4; }}\n.l {{ text-align: left; }}\n.c {{ text-align: center; }}\n.a {{ text-align: left; font-weight: bold; width: 25%; }}\n.u {{ text-align: center; color: #666; font-size: 0.9em; }}\n.p {{ color: green; font-weight: bold; }}\n.n {{ color: red; font-weight: bold; }}\n.score-box {{ padding: 20px; background: #eef2f5; border-left: 5px solid #0a192f; margin-bottom: 20px; }}\n.alerts {{ background: #fff3f3; border-left: 5px solid #d9534f; padding: 15px; }}\n.recommendation {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #16a34a; padding: 15px; margin-top: 15px; }}\n.st-momentum {{ background: #fffbeeb3; border: 1px solid #fde68a; border-left: 5px solid #d97706; padding: 15px; margin-top: 15px; }}\n.summary-item {{ margin-bottom: 8px; }}\n.reasoning {{ font-size: 0.9em; color: #555; margin-left: 20px; }}\n</style></head><body>"""
    html += f"""<div style="display: flex; align-items: center; border-bottom: 2px solid #0a192f; padding-bottom: 15px; margin-top: 20px; margin-bottom: 20px;"><img src="https://vilfintv.com/images/vilfintv-logo.jpg" alt="VilfinTV" style="width: 50px; height: 50px; border-radius: 50%; margin-right: 15px; box-shadow: 0 0 8px rgba(59,130,246,0.45); object-fit: cover;"><div style="flex-grow: 1;"><h2 style="margin: 0; color: #0a192f; border: none; padding: 0;">Market Regime Report</h2><div style="color: #555; font-size: 0.95em; margin-top: 5px;">Executive Summary by <strong>VilfinTV.com</strong></div></div><div style="color: #666; font-size: 0.9em; text-align: right; font-weight: bold;">{jst_today_str()}</div></div>"""
    html += f"""
        <div class="score-box">
            <h3 style="margin-top: 0;">Executive Summary</h3>
            <div class="summary-item"><strong>Market Sentiment Score:</strong> {regime_score} / 100</div>
            <div class="summary-item"><strong>Current Phase:</strong> {regime_text}</div>
            <div class="summary-item" style="margin-top:12px;">
                <a href="https://vilfintv.com/market_sentiment_score.html" target="_blank" style="display:inline-block; background:linear-gradient(135deg,#14bf96,#0ea885); color:#04241c; font-weight:bold; font-size:0.92em; padding:10px 18px; border-radius:8px; text-decoration:none; box-shadow:0 4px 12px rgba(20,191,150,0.35);">📊 What does this score mean? Read the full breakdown &rarr;</a>
            </div>

            <div class="recommendation">
                <h4 style="margin-top: 0; margin-bottom: 15px;">Long-Term Strategic Picks & Regional Insights</h4>
                <div class="summary-item"><strong>🌍 Strongest Region Today:</strong> {regional_rec}</div>
                <div class="summary-item"><strong>🚀 Top Equity Sector (Growth):</strong> {mom_sector}</div>
                <div class="summary-item"><strong>⚖️ Top Equity Sector (Value):</strong> {val_sector}</div>
                <div class="summary-item" style="margin-top: 10px;"><strong>🌎 Best Broad-Market Index:</strong> {lt_broad}</div>
                <div class="reasoning"><em>{lt_broad_reason}</em></div>
                <div class="summary-item" style="margin-top: 10px;"><strong>💎 Best Long-Term Thematic Sector:</strong> {lt_sector}</div>
                <div class="reasoning"><em>{lt_reason}</em></div>
                <div class="summary-item" style="margin-top: 10px;"><strong>🏦 Best Long-Term Bond:</strong> {lt_bond}</div>
                <div class="reasoning"><em>{lt_bond_reason}</em></div>
                <div class="summary-item" style="margin-top: 10px;"><strong>⛏️ Best Long-Term Commodity:</strong> {lt_comm}</div>
                <div class="reasoning"><em>{lt_comm_reason}</em></div>
            </div>

            <div class="reasoning" style="background:#f8fafc; border:1px solid #e2e8f0; border-left:4px solid #64748b; padding:10px 14px; margin-top:15px; font-style:normal;"><strong>📋 Regime-aware read on the Picks below:</strong> {get_regime_note(regime_score)}</div>

            <div class="st-momentum">
                <h4 style="margin-top: 0; margin-bottom: 15px;">Trending Now / Swing Trades (Strongest 20-Day Trend)</h4>
                <div class="summary-item"><strong>📈 Top Equity Pick:</strong> {st_eq}</div>
                <div class="summary-item"><strong>🪙 Top Commodity Pick:</strong> {st_comm}</div>
                <div class="summary-item"><strong>💵 Top Bond Pick:</strong> {st_bond}</div>
                <div class="summary-item"><strong>💱 Top Currency Pick:</strong> {st_curr}</div>
            </div>

            <div class="st-momentum" style="background:#eff6ff; border-color:#bfdbfe; border-left-color:#2563eb;">
                <h4 style="margin-top: 0; margin-bottom: 15px;">Best Quality (Consistent Across Every Timeframe)</h4>
                <div class="summary-item"><strong>📈 Equities:</strong> {qual_eq}</div>
                <div class="summary-item"><strong>🪙 Commodities:</strong> {qual_comm}</div>
                <div class="summary-item"><strong>💵 Bonds:</strong> {qual_bond}</div>
                <div class="summary-item"><strong>💱 Currencies:</strong> {qual_curr}</div>
                <div class="reasoning" style="margin-top:8px;">"Quality" here means trading positively across today's session, the 20-day, 50-day, YTD and 3-year windows all at once - a steady all-round performer, not a single recent spike. See "How We Pick These" on the methodology page for the full explanation of Momentum/Trending, Value, Long-Term and Quality.</div>
            </div>
            {"<div class='summary-item' style='margin-top:15px; padding:10px; background:#fef9c3; border-left:4px solid #ca8a04;'><strong>🆕 Notable FX Mover (auto-detected):</strong> " + notable_fx + " - not one of the regularly tracked pairs above, surfaced automatically because it moved the most today.</div>" if notable_fx else ""}
        </div>
    """

    asset_class_rec = get_asset_class_recommendation(regime_score)
    flow_alert, dxy_note = get_global_capital_flow_note(data)
    html += "<div class='score-box' style='background: #f0f9ff; border-left: 5px solid #0284c7;'>"
    html += "<h4 style='margin-top: 0; margin-bottom: 15px; color: #075985;'>🌐 Global Capital Flows &amp; Asset Positioning</h4>"
    html += f"<div class='summary-item'><strong>Actionable Asset Class:</strong> {asset_class_rec}</div>"
    if flow_alert:
        html += f"<div class='summary-item' style='margin-top: 8px;'>{flow_alert}</div>"
    if dxy_note:
        html += f"<div class='summary-item' style='margin-top: 8px;'>{dxy_note}</div>"
    html += "</div>"

    if news_items:
        html += "<div class='score-box' style='background: #fdfdfd; border-left: 5px solid #0056b3;'>"
        html += "<h4 style='margin-top: 0; margin-bottom: 15px; color: #0056b3;'>📰 What to Watch Out for This Week (Major Events)</h4>"
        html += "<ul style='margin-bottom:0;'>"
        for item in news_items:
            html += f"<li style='margin-bottom: 8px;'><a href='{item['link']}' style='color: #1a0dab; text-decoration: none;'>{item['title']}</a> <span style='color: #666; font-size: 0.85em;'>- {item['publisher']}</span></li>"
        html += "</ul></div>"

    html += "<div class='score-box' style='background: #fff3f3; border-left: 5px solid #d9534f;'>"
    html += "<h4 style='margin-top: 0; margin-bottom: 15px; color: #d9534f;'>🚨 Automated Risk Alerts</h4>"
    if risk_alerts:
        html += "<ul style='margin-bottom:0; color: #b91c1c;'>"
        for alert in risk_alerts:
            html += f"<li style='margin-bottom: 8px;'><strong>{alert}</strong></li>"
        html += "</ul></div>"
    else:
        html += "<p style='margin:0; color: #b91c1c;'>✅ No extreme risk events detected today.</p></div>"

    if macro_text:
        html += "<div class='score-box' style='background: #e2e8f0; border-left: 5px solid #64748b;'>"
        html += "<h4 style='margin-top: 0; margin-bottom: 15px; color: #0f172a;'>🏛 Macroeconomic Health & Labor</h4>"
        html += "<p style='color: #334155; margin: 0; line-height: 1.6;'>"
        html += macro_text
        html += "</p></div>"

    html += "<h2>Asset Dashboard</h2>"
    for category, assets in data.items():
        html += f"<h3>{category}</h3>"
        html += """
        <table>
            <tr>
                <th class="l" style="width: 25%;">Asset</th>
                <th class="c">Currency</th>
                <th class="c">Price / Yield</th>
                <th class="c">Daily Change</th>
                <th class="c">50-Day MA</th>
                <th class="c">YTD Return</th>
                <th class="c">3-Year Return</th>
            </tr>
        """
        for name, metrics in assets.items():
            if metrics and _valid(metrics.get('price')) and _valid(metrics.get('change')):
                change_class = "p" if metrics['change'] >= 0 else "n"
                change_sign = "+" if metrics['change'] >= 0 else ""

                ma_50 = metrics.get('ma_50')
                ma_50_str = f"{ma_50:.2f}" if _valid(ma_50) else "N/A"
                currency_str = metrics.get('currency', 'N/A')
                price_str = f"{metrics['price']:.2f}"

                ytd_val = metrics.get('ytd_return')
                three_yr_val = metrics.get('three_yr_return')

                if _valid(ytd_val):
                    ytd_class = "p" if ytd_val >= 0 else "n"
                    ytd_sign = "+" if ytd_val >= 0 else ""
                    ytd_str = f"<span class='{ytd_class}'>{ytd_sign}{ytd_val:.2f}%</span>"
                else:
                    ytd_str = "N/A"

                if _valid(three_yr_val):
                    three_yr_class = "p" if three_yr_val >= 0 else "n"
                    three_yr_sign = "+" if three_yr_val >= 0 else ""
                    three_yr_str = f"<span class='{three_yr_class}'>{three_yr_sign}{three_yr_val:.2f}%</span>"
                else:
                    three_yr_str = "N/A"

                name_str = name
                if metrics.get('is_stale'):
                    stale_since_str = metrics.get('stale_since') or 'a previous day'
                    name_str += f" <span style='color:#b45309;font-size:0.85em' title='Live data unavailable today - showing last known value from {stale_since_str}'>⚠️ stale</span>"
                html += f"<tr><td class='a'>{name_str}</td><td class='u'>{currency_str}</td><td class='c'>{price_str}</td><td class='c {change_class}'>{change_sign}{metrics['change']:.2f}%</td><td class='c'>{ma_50_str}</td><td class='c'>{ytd_str}</td><td class='c'>{three_yr_str}</td></tr>"
            else:
                html += f"<tr><td class='a'>{name}</td><td colspan='6' class='c' style='color:#999;'>Data Unavailable</td></tr>"
        html += "</table>"


        if "Stocks" in category:
            html += """
            <div style="text-align: right; margin-top: -10px; margin-bottom: 20px; font-size: 0.85em;">
                <a href="https://www.marketscreener.com/top-records/price-change/" style="color: #1a0dab; text-decoration: none; margin-left: 15px; font-weight: bold;">📊 Top Price Changers</a>
                <a href="https://www.marketscreener.com/top-records/valuation/" style="color: #1a0dab; text-decoration: none; margin-left: 15px; font-weight: bold;">💰 Top Valuations</a>
            </div>
            """

        if category == "Volatility":
            vix_price = None
            vix_is_stale = False
            vix_stale_since = None
            for name, metrics in assets.items():
                if "VIX" in name.upper() and metrics:
                    vix_price = metrics['price']
                    vix_is_stale = bool(metrics.get('is_stale'))
                    vix_stale_since = metrics.get('stale_since')
                    break

            if vix_price:
                month_move = vix_price / 3.464
                
                v_range = "High (Fear / Stress)"
                v_color = "red"
                if vix_price < 15:
                    v_range = "Low (Complacency)"
                    v_color = "green"
                elif vix_price <= 20:
                    v_range = "Normal (Standard Market)"
                    v_color = "#d97706"
                
                html += f"""
                <div style="background: #fdfdfd; border: 1px solid #e0e0e0; border-left: 5px solid #0a192f; padding: 15px; margin-bottom: 20px; margin-top: 10px;">
                    <h4 style="margin-top: 0; margin-bottom: 10px; color: #1a365d;">💡 How to read the VIX (Volatility Index)</h4>
                    <ul style="margin-top: 0; margin-bottom: 15px; color: #555;">
                        <li><strong style="color: green;">Below 15:</strong> Low Volatility (Market Complacency)</li>
                        <li><strong style="color: #d97706;">15 - 20:</strong> Normal Volatility (Standard Market Conditions)</li>
                        <li><strong style="color: red;">Above 20:</strong> High Volatility (Market Fear / Stress)</li>
                    </ul>
                    <div style="font-size: 0.95em;">
                        Current VIX is <strong style="color: {v_color};">{vix_price:.2f}</strong> ({v_range}).<br>
                        <strong>Expected Market Move (Per Month):</strong> ± {month_move:.1f}% <em>(Calculated as VIX ÷ √12)</em>
                    </div>
                    {'<div style="font-size: 0.85em; color: #b45309; margin-top: 8px;">⚠️ Live VIX data was unavailable today - showing the last known value from ' + (vix_stale_since or 'a previous day') + '.</div>' if vix_is_stale else ''}
                </div>
                """
        elif category != "Volatility":
            valid_assets = {n: m for n, m in assets.items() if m}
            if valid_assets:
                st_eq = "N/A"
                val_eq = "N/A"
                lt_eq = "N/A"
                
                valid_st = {n: m for n, m in valid_assets.items() if m.get('ma_20') and m.get('change') is not None and m['change'] > 0}
                if valid_st:
                    best = max(valid_st.items(), key=lambda x: calc_momentum_score(x[1]))
                    dist = ((best[1]['price'] / best[1]['ma_20']) - 1) * 100
                    st_eq = f"{best[0]} ({dist:+.2f}% vs 20D MA)"
                
                valid_val = {n: m for n, m in valid_assets.items() if m.get('ma_50')}
                if valid_val:
                    best_val = max(valid_val.items(), key=lambda x: calc_value_score(x[1]))
                    dist_val = ((best_val[1]['price'] / best_val[1]['ma_50']) - 1) * 100
                    if dist_val < 0:
                        val_eq = f"{best_val[0]} ({abs(dist_val):.2f}% below 50D MA)"
                    else:
                        val_eq = f"{best_val[0]} (Lowest premium: {dist_val:+.2f}% vs 50D MA)"
                
                valid_lt = {n: m for n, m in valid_assets.items() if m.get('three_yr_return')}
                if valid_lt:
                    best_lt = rank_by_lt_score(valid_lt)[0]
                    lt_eq = f"{best_lt[0]} ({best_lt[1]['three_yr_return']:+.2f}% 3-Year)"

                qual_eq_cat = get_quality_pick(valid_assets)

                html += f"""
                <div style="background: #fdfdfd; border: 1px solid #e0e0e0; border-left: 5px solid #1a365d; padding: 15px; margin-bottom: 20px; margin-top: 10px;">
                    <h4 style="margin-top: 0; margin-bottom: 10px; color: #1a365d;">🏆 Top Picks from {category}</h4>
                    <div style="font-size: 0.95em;">
                        <strong>📈 Best Momentum / Trending (Short Term):</strong> {st_eq}<br>
                        <strong>⚖️ Best Value (Oversold):</strong> {val_eq}<br>
                        <strong>💎 Best Long-Term (3-Year):</strong> {lt_eq}<br>
                        <strong>🛡️ Best Quality (Consistent):</strong> {qual_eq_cat}
                    </div>
                    <div style="font-size:0.82em; color:#888; margin-top:8px;">How these are picked: <a href="https://vilfintv.com/market_sentiment_score.html#methodology" style="color:#0056b3;">see the methodology breakdown &rarr;</a></div>
                </div>
                """

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
        <h3 style="margin-top: 0; color: #0a192f;">Explore More In-Depth Details</h3>
        <p style="margin-bottom: 20px; color: #555;">Check out our full web platforms for real-time market data and breaking news coverage:</p>
        <div style="margin-bottom: 15px;">
            <a href="https://vilfintv.com/index.html" style="display: inline-block; padding: 12px 24px; margin: 5px 10px; background-color: #0a192f; color: white; text-decoration: none; border-radius: 6px; font-weight: bold;">📊 Market Dashboard</a>
            <a href="https://vilfintv.com/news.html" style="display: inline-block; padding: 12px 24px; margin: 5px 10px; background-color: #0a192f; color: white; text-decoration: none; border-radius: 6px; font-weight: bold;">📰 Live News Feed</a>
        </div>
        <p style="margin-bottom: 10px; color: #555; font-size: 0.95em; font-weight: bold;">Global Market Rankings & Regional Indices:</p>
        <div style="margin-bottom: 20px; font-size: 0.9em;">
            <a href="https://www.marketscreener.com/stock-exchange/indexes/ranking/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🏆 Top Rankings</a> |
            <a href="https://www.marketscreener.com/stock-exchange/indexes/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🌐 World Indices</a> |
            <a href="https://www.marketscreener.com/stock-exchange/indexes/europe/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🇪🇺 Europe</a> |
            <a href="https://www.marketscreener.com/stock-exchange/indexes/africa/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🌍 Africa</a> |
            <a href="https://www.marketscreener.com/stock-exchange/indexes/asia/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🌏 Asia</a>
        </div>
        <p style="margin-bottom: 10px; color: #555; font-size: 0.95em; font-weight: bold;">Indian Market Screeners & Discoveries:</p>
        <div style="margin-bottom: 20px; font-size: 0.85em; line-height: 1.6;">
            <a href="https://dhan.co/all-etfs/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">📈 All ETFs</a> |
            <a href="https://dhan.co/mutual-funds/equity-funds/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🏦 Equity MFs</a> |
            <a href="https://dhan.co/stock-market-live/top-gainers-today/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🚀 Top Gainers</a> |
            <a href="https://dhan.co/stocks/market/multibagger-stocks/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">💎 Multibaggers</a> <br>
            <a href="https://dhan.co/stocks/market/most-active-stocks-this-week/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🔥 Most Active</a> |
            <a href="https://dhan.co/stocks/market/uptrend-stocks/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">↗️ Uptrend</a> |
            <a href="https://dhan.co/stocks/market/high-growth-stocks/" style="color: #1a0dab; text-decoration: none; margin: 0 8px; font-weight: bold;">🌱 High Growth</a>
        </div>
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

def send_email(html_content):
    sender_email = os.environ.get('GMAIL_USER')
    sender_password = os.environ.get('GMAIL_APP_PASSWORD')
    receiver_email = os.environ.get('EMAIL_TO')

    if not all([sender_email, sender_password, receiver_email]):
        logging.error("Email credentials or EMAIL_TO not set in environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"Daily Market Analysis & Sector Report - {jst_today_str()}"
    # Format the sender to look professional
    msg['From'] = f"VilfinTV Daily Screener <{sender_email}>"
    msg['To'] = receiver_email
    # Set Reply-To so users replying will bounce
    msg.add_header('Reply-To', 'noreply@vilfintv.com')

    # Fetch automated subscriber list from D1 database via Worker
    bcc_emails = []
    try:
        worker_url = os.environ.get('SUBSCRIBER_WORKER_URL')
        worker_secret = os.environ.get('SUBSCRIBER_WORKER_SECRET')
        if worker_url and worker_secret:
            resp = requests.get(f"{worker_url}?action=list", headers={'Authorization': f"Bearer {worker_secret}"})
            if resp.status_code == 200:
                bcc_emails = resp.json()
                bcc_emails = [e for e in bcc_emails if e != 'test@vilfintv.com']
                print(f"Fetched {len(bcc_emails)} subscribers")
            else:
                logging.error(f"Failed to fetch subscribers from Worker: {resp.status_code} {resp.text}")
        else:
            logging.warning("SUBSCRIBER_WORKER_URL or SUBSCRIBER_WORKER_SECRET not set.")
    except Exception as e:
        logging.error(f"Exception fetching subscribers from D1 Worker: {e}")

    if bcc_emails:
        msg['Bcc'] = ", ".join(bcc_emails)

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

if __name__ == "__main__":
    logging.info("Starting Market Analyzer Pipeline")
    market_data = collect_market_data()

    # Auto-detect the biggest mover among FX pairs NOT already in the
    # permanent Currencies table, and merge it in before scoring so it
    # flows through the dashboard table + momentum/value/long-term/quality
    # picks automatically, clearly labeled as auto-detected downstream.
    notable_fx_name, notable_fx_data = find_notable_fx_mover(market_data.get('Currencies', {}))
    notable_fx_summary = None
    if notable_fx_name and notable_fx_data:
        market_data.setdefault('Currencies', {})[notable_fx_name] = notable_fx_data
        chg = notable_fx_data.get('change')
        chg_str = f"{chg:+.2f}%" if _valid(chg) else "N/A"
        notable_fx_summary = f"{notable_fx_name} ({chg_str} today)"
        logging.info(f"Notable FX mover auto-detected: {notable_fx_summary}")

    # Genuine macro data for the Labor Market, Liquidity & Financial
    # Conditions, and Credit Spread signals - fetched once and passed into
    # both scoring calls so a network hiccup on one doesn't need refetching
    # for the other.
    fred_extras = {}
    labor_claims = fetch_fred_series("ICSA", lookback=8)
    if labor_claims:
        fred_extras['labor_claims'] = labor_claims
    financial_conditions = fetch_fred_series("NFCI", lookback=4)
    if financial_conditions:
        fred_extras['financial_conditions'] = financial_conditions
    credit_spread = fetch_fred_series("BAMLH0A0HYM2", lookback=10)
    if credit_spread:
        fred_extras['credit_spread'] = credit_spread
    cpi_yoy = fetch_fred_change("CPIAUCSL", months_back=12)
    if cpi_yoy:
        fred_extras['cpi_yoy'] = cpi_yoy
    payrolls_mom = fetch_fred_change("PAYEMS", months_back=1)
    if payrolls_mom:
        fred_extras['payrolls_mom'] = payrolls_mom
    walcl = fetch_fred_series("WALCL", lookback=4)
    tga = fetch_fred_series("WTREGEN", lookback=4)
    rrp = fetch_fred_series("RRPONTSYD", lookback=4)
    if walcl and tga and rrp:
        fred_extras['net_liquidity'] = (walcl, tga, rrp)

    score, regime, alerts, rec_regional, rec_mom, rec_val, rec_lt, lt_reason, lt_broad, lt_broad_reason, lt_bond, lt_bond_reason, lt_comm, lt_comm_reason, st_eq, st_comm, st_bond, st_curr, qual_eq, qual_comm, qual_bond, qual_curr = calculate_market_regime(market_data, fred_extras)

    logging.info(f"Calculated Regime Score: {score} ({regime})")

    news_items = fetch_global_news()
    macro_text = build_fred_macro_text(fred_extras)
    html_report = generate_html_email(market_data, score, regime, alerts, macro_text, news_items, rec_regional, rec_mom, rec_val, rec_lt, lt_reason, lt_broad, lt_broad_reason, lt_bond, lt_bond_reason, lt_comm, lt_comm_reason, st_eq, st_comm, st_bond, st_curr, qual_eq, qual_comm, qual_bond, qual_curr, notable_fx_summary)
    send_email(html_report)

    # Publish a JSON snapshot of today's real score + signal breakdown so
    # market_sentiment_score.html's "live example" section can fetch and
    # render it client-side instead of staying frozen on a hand-edited date.
    try:
        generated_at_iso = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        # Reconstruct the same session pools get_executive_summary_analysis
        # ranks from, so confidence can be computed here without changing
        # get_short_term_pick/get_quality_pick's tested string-return
        # contract that the email directly depends on.
        sector_data = market_data.get('Sectors & Themes (US ETFs)', {})
        commodities_pool = market_data.get('Commodities', {})
        bonds_pool = {n: m for n, m in market_data.get('Bonds', {}).items() if n not in YIELD_INDEX_NAMES}
        currencies_pool = market_data.get('Currencies', {})

        def trending_bundle(pool):
            conf = summarize_pick_confidence(pool, calc_momentum_score, require_positive_change=True)
            return build_pick_bundle("trending", None, conf, generated_at_iso)

        def quality_bundle(pool):
            conf = summarize_pick_confidence(pool, calc_quality_score)
            return build_pick_bundle("quality", None, conf, generated_at_iso)

        picks_meta = {
            "trending": {
                "equity": {**trending_bundle(sector_data), "reason": st_eq},
                "commodity": {**trending_bundle(commodities_pool), "reason": st_comm},
                "bond": {**trending_bundle(bonds_pool), "reason": st_bond},
                "currency": {**trending_bundle(currencies_pool), "reason": st_curr},
            },
            "quality": {
                "equity": {**quality_bundle(sector_data), "reason": qual_eq},
                "commodity": {**quality_bundle(commodities_pool), "reason": qual_comm},
                "bond": {**quality_bundle(bonds_pool), "reason": qual_bond},
                "currency": {**quality_bundle(currencies_pool), "reason": qual_curr},
            },
            "value": {**build_pick_bundle("value", rec_val, "N/A (single sector-level pick, not ranked here)", generated_at_iso)},
            "long_term": {**build_pick_bundle("long_term", rec_lt, "N/A (single sector-level pick, not ranked here)", generated_at_iso)},
        }

        # Carry forward the last-known-good raw cache (see
        # CRITICAL_FALLBACK_SYMBOLS / _load_last_known_good above), only
        # overwriting an entry when TODAY's value is itself fresh - so a
        # stale fallback used today doesn't get re-persisted as if it were
        # new, and a run that fails multiple days in a row still has the
        # last genuinely-live value to fall back on rather than losing it.
        try:
            with open("data/market_sentiment_snapshot.json") as f:
                raw_fallback_cache = json.load(f).get("raw_fallback_cache", {})
        except (FileNotFoundError, json.JSONDecodeError):
            raw_fallback_cache = {}
        for vol_name, vol_metrics in market_data.get('Volatility', {}).items():
            if vol_metrics and not vol_metrics.get('is_stale') and _valid(vol_metrics.get('price')):
                vol_symbol = TICKERS_CONFIG['Volatility'][vol_name]['symbol']
                raw_fallback_cache[vol_symbol] = {
                    'price': vol_metrics['price'],
                    'ma_20': vol_metrics.get('ma_20'),
                    'ma_50': vol_metrics.get('ma_50'),
                    'ma_200': vol_metrics.get('ma_200'),
                }

        snapshot = {
            "date": jst_today_str(),
            "generated_at_utc": generated_at_iso,
            "score": score,
            "regime": regime,
            "risk_alerts": alerts,
            "breakdown": build_score_breakdown(market_data, fred_extras)[0],
            "regional_rec": rec_regional,
            "momentum_sector": rec_mom,
            "value_sector": rec_val,
            "long_term_sector": rec_lt,
            "picks": {
                "trending": {"equity": st_eq, "commodity": st_comm, "bond": st_bond, "currency": st_curr},
                "quality": {"equity": qual_eq, "commodity": qual_comm, "bond": qual_bond, "currency": qual_curr},
            },
            "picks_meta": picks_meta,
            "notable_fx_mover": notable_fx_summary,
            "regime_note": get_regime_note(score),
            "raw_fallback_cache": raw_fallback_cache,
        }
        with open("data/market_sentiment_snapshot.json", "w") as f:
            json.dump(snapshot, f, indent=2)
        logging.info("Wrote data/market_sentiment_snapshot.json")
    except Exception as e:
        logging.error(f"Failed to write market sentiment snapshot: {e}")

    logging.info("Pipeline execution completed.")
