#!/usr/bin/env python3
"""Cash-market flows only. NSE latest; Moneycontrol dated archive for backfill.

Never splice NSDL primary-market/debt series into exchange cash figures.
Decimal arithmetic, daily net identities, monthly reconciliation and independent
Groww overlap checks precede an atomic replacement. Failed builds preserve data.
"""
import argparse
import concurrent.futures
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from html import unescape
import json
from pathlib import Path
import re
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data/mf/institutional_flows.json'
NSE = 'https://www.nseindia.com/api/fiidiiTradeReact'
MC = 'https://www.moneycontrol.com/techmvc/responsive/fiidii/'
GROWW = 'https://groww.in/fii-dii-data'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json,text/html,*/*'}

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=45)
    r.raise_for_status()
    return r.text

def amount(value):
    x = Decimal(str(value).replace(',', '').strip())
    if not x.is_finite() or x != x.quantize(Decimal('.01')):
        raise ValueError('Invalid monetary precision')
    return int(x * 100)  # hundredths of a crore, exact integer aggregation

def vector(values):
    v = [amount(x) for x in values]
    if len(v) != 6 or any(v[i] < 0 for i in (0, 1, 3, 4)):
        raise ValueError('Invalid gross cash flow')
    if v[0] - v[1] != v[2] or v[3] - v[4] != v[5]:
        raise ValueError('Buy minus sell does not equal net')
    return v

def cells(text):
    return [unescape(re.sub('<[^>]*>', '', c)).strip() for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', text, re.S | re.I)]

def archive(text, year, month):
    days, total = {}, None
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', text, re.S | re.I):
        c = cells(tr)
        if len(c) != 7:
            continue
        if c[0] == 'Total':
            total = vector(c[1:])
        elif re.fullmatch(r'\d{2}-[A-Za-z]{3}-\d{4}', c[0]):
            d = datetime.strptime(c[0], '%d-%b-%Y').date()
            if (d.year, d.month) != (year, month) or d.isoformat() in days:
                raise ValueError('Wrong month or duplicate archive date')
            days[d.isoformat()] = vector(c[1:])
    if not days or total is None:
        raise ValueError('Empty or changed cash archive')
    summed = [sum(v[i] for v in days.values()) for i in range(6)]
    if summed != total:
        raise ValueError(f'{year}-{month:02}: daily totals differ from archive total')
    return days, total

def latest(text):
    j = json.loads(text)
    by = {x['category']: x for x in j}
    if len(j) != 2 or set(by) != {'DII', 'FII/FPI'} or len({x['date'] for x in j}) != 1:
        raise ValueError('NSE must provide both participants for one session')
    d = datetime.strptime(j[0]['date'], '%d-%b-%Y').date()
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    if not 0 <= (today - d).days <= 5:
        raise ValueError('NSE session is stale or in the future')
    return d, vector([by[k][f] for k in ('FII/FPI', 'DII') for f in ('buyValue', 'sellValue', 'netValue')])

def aggregate(rows, period):
    groups = {}
    for day, values in sorted(rows.items()):
        d = date.fromisoformat(day)
        key = day if period == 'daily' else (d - timedelta(days=d.weekday())).isoformat() if period == 'weekly' else day[:7] if period == 'monthly' else day[:4]
        g = groups.setdefault(key, {'period': key, 'from': day, 'to': day, 'sessions': 0, 'values': [0]*6})
        g['to'] = day
        g['sessions'] += 1
        g['values'] = [a+b for a, b in zip(g['values'], values)]
    return list(reversed(list(groups.values())))

def build(start_year):
    d, nv = latest(fetch(NSE))
    old = json.loads(OUT.read_text(encoding='utf8')) if OUT.exists() else None
    rows = {r['date']: r['values'] for r in (old or {}).get('daily', [])}
    # Reconcile all months on first build; refresh current and previous months
    # thereafter so exchange corrections replace complete monthly snapshots.
    months = [(y, m) for y in range(start_year, d.year+1) for m in range(1, 13) if date(y, m, 1) <= d]
    if old:
        cutoff = (d.replace(day=1) - timedelta(days=1)).replace(day=1)
        months = [(y,m) for y,m in months if date(y,m,1) >= cutoff or f'{y}-{m:02}' not in old.get('reconciledMonths', {})]
    reconciled = (old or {}).get('reconciledMonths', {}).copy()
    def month_data(ym):
        y,m = ym
        u = f'{MC}monthly?month={m}&year={y}&section=cash&sub_section='
        return y,m,*archive(fetch(u),y,m)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for y,m,days,total in pool.map(month_data, months):
            prefix = f'{y}-{m:02}'
            if any(day > d.isoformat() for day in days):
                raise ValueError('Archive ahead of official NSE session')
            rows = {k:v for k,v in rows.items() if not k.startswith(prefix)}
            rows.update(days)
            reconciled[prefix] = {'sessions': len(days), 'total': total}
    if rows.get(d.isoformat()) != nv:
        raise ValueError('Latest archive figures differ from official NSE')
    for day, values in rows.items():
        if date.fromisoformat(day) > d or len(values) != 6 or not all(type(v) is int and abs(v) < 2**53 for v in values):
            raise ValueError('Invalid retained daily record')
        if any(values[i] < 0 or values[i+1] < 0 or values[i]-values[i+1] != values[i+2] for i in (0,3)):
            raise ValueError('Retained cash flow does not reconcile')
    # Independent distributor overlap; require >=10 common sessions, all six fields.
    text = fetch(GROWW)
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    other = json.loads(match[1])['props']['pageProps']['initialData'] if match else []
    overlap = 0
    for r in other:
        if r['date'] in rows:
            v = vector([r[k][f] for k in ('fii','dii') for f in ('grossBuy','grossSell','netBuySell')])
            if rows[r['date']] != v:
                raise ValueError('Historical overlap differs from Groww')
            overlap += 1
    if overlap < 10:
        raise ValueError('Insufficient independent history overlap')
    periods = {p: aggregate(rows,p) for p in ('daily','weekly','monthly','yearly')}
    ownership = json.loads((ROOT/'scripts/institutional_ownership.json').read_text(encoding='utf8'))
    if date.fromisoformat(ownership['asOf']) > d or not all(0 <= ownership[k] <= 100 for k in ('fii','dii')) or ownership['fii']+ownership['dii'] > 100:
        raise ValueError('Invalid ownership snapshot')
    out = {'v':1,'asOf':d.isoformat(),'generated':datetime.now(timezone.utc).isoformat(),
           'unit':'INR crore / 100','scope':'NSE, BSE and MSEI combined equity cash market; provisional',
           'sources':{'latest':NSE,'archive':MC+'monthly','crosscheck':GROWW},
           'historyFrom':min(rows),'daily':[{'date':k,'values':v} for k,v in sorted(rows.items())],
           'periods':periods,'reconciledMonths':reconciled,'ownership':ownership,
           'audit':{'errors':0,'dailyIdentities':len(rows)*2,'monthsReconciled':len(reconciled),'independentSessions':overlap,'officialLatestMatch':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    tmp = OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    tmp.replace(OUT)
    print(f'{len(rows)} sessions; {len(reconciled)} monthly reconciliations; {overlap} independent matches; official latest {d}')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--start-year',type=int,default=2026)
    build(ap.parse_args().start_year)
