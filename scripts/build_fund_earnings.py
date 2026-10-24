#!/usr/bin/env python3
"""Look-through earnings of the CURRENT disclosed equity portfolio.

NSE closing price / NSE symbol P/E gives trailing earnings per share. The
year-on-year comparison holds today's disclosed share quantities constant.
It is not a mutual fund's own EPS and is not historical portfolio performance.
Exclude unit-changing corporate actions rather than invent split adjustments.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import argparse
import csv
import io
import json
import re
import zipfile
import requests

ROOT=Path(__file__).resolve().parent.parent
MF=ROOT/'data/mf'
BASE='https://nsearchives.nseindia.com/content'
HEADERS={'User-Agent':'Mozilla/5.0','Referer':'https://www.nseindia.com/'}

def download(url):
    r=requests.get(url,headers=HEADERS,timeout=45)
    r.raise_for_status()
    return r.content

def pe_rows(blob):
    out={}
    for r in csv.DictReader(io.StringIO(blob.decode('utf-8-sig'))):
        try:
            v=float(r['SYMBOL P/E'])
            if 0<v<1000:out[r['SYMBOL'].strip()]=v
        except (ValueError,KeyError):pass
    if len(out)<500:raise ValueError('P/E file has insufficient valid observations')
    return out

def closing_rows(blob, expected):
    out={}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=[n for n in z.namelist() if n.endswith('.csv')]
        if len(names)!=1 or z.getinfo(names[0]).file_size>30000000:raise ValueError('Invalid price archive')
        for r in csv.DictReader(io.TextIOWrapper(z.open(names[0]),encoding='utf-8-sig')):
            if r.get('SctySrs')!='EQ':continue
            if r.get('TradDt','')[:10]!=expected:raise ValueError('Wrong closing-price date')
            try:
                px=float(r['ClsPric'])
                if px>0:out[r['ISIN']]=(r['TckrSymb'].strip(),px)
            except (ValueError,KeyError):pass
    if len(out)<1000:raise ValueError('Closing-price file has insufficient securities')
    return out

def excluded_actions(blob,start,end):
    rows=json.loads(blob)
    if not isinstance(rows,list):raise ValueError('Corporate-action source changed')
    excluded=set()
    for r in rows:
        if not isinstance(r,dict) or not r.get('exDate'):raise ValueError('Invalid corporate-action row')
        d=datetime.strptime(r['exDate'],'%d-%b-%Y').date()
        if start<d<=end and re.search(r'bonus|split|sub.division|face value|rights|amalgam|merger|demerger|consolidation|scheme.*arrangement',r.get('subject',''),re.I):
            excluded.add(r.get('isin'))
    return excluded

def portfolio_earnings(p,now,old,pe_now,pe_old,excluded):
    weights={}
    full='equityISIN' in p
    if full:
        for isin,w in p['equityISIN']:weights[isin]=weights.get(isin,0)+w
    else:
        for h in p.get('top',[]):
            if len(h)>=5 and h[4]=='equity':weights[h[3]]=weights.get(h[3],0)+h[2]
    equity=((p.get('mix') or {}).get('equity') or 0)+((p.get('mix') or {}).get('overseas') or 0)
    if equity<=0:return None
    covered=current=previous=0.0
    comparable=0
    affected=0.0
    for isin,w in weights.items():
        if isin in excluded:
            affected+=w
            continue
        if isin not in now or isin not in old:continue
        sym,px=now[isin]; psym,ppx=old[isin]
        if sym not in pe_now or psym not in pe_old:continue
        # Quantity per rupee of today's fund portfolio = disclosed weight / price.
        current+=w/pe_now[sym]
        previous+=(w/px)*(ppx/pe_old[psym])
        covered+=w
        comparable+=1
    if covered<=0 or current<=0 or previous<=0:return None
    return {'pe':round(covered/current,3),'earningsGrowth':round((current/previous-1)*100,3),
            'coverage':round(100*covered/equity,2),'coveredFundWeight':round(covered,2),
            'equityWeight':equity,'corporateActionExcludedWeight':round(affected,2),
            'portfolioAsOf':p.get('asOf'),'fullDisclosure':full,'positions':comparable,'disclosedEquityPositions':len(weights)}

def build(fixtures=None):
    sc=json.loads((MF/'screener.json').read_text(encoding='utf8'))
    day=date.fromisoformat(sc['asOf'])
    target=day.replace(year=day.year-1) if (day.month,day.day)!=(2,29) else date(day.year-1,2,28)
    def files(d,tag):
        if fixtures:
            pe=Path(fixtures,f'pe_{tag}.txt').read_bytes(); px=Path(fixtures,f'prices_{tag}.zip').read_bytes()
            return d,pe_rows(pe),closing_rows(px,d.isoformat())
        for n in range(8):
            x=d-timedelta(days=n)
            try:
                pe=download(f'{BASE}/equities/peDetail/PE_{x:%d%m%y}.csv')
                px=download(f'{BASE}/cm/BhavCopy_NSE_CM_0_0_0_{x:%Y%m%d}_F_0000.csv.zip')
                return x,pe_rows(pe),closing_rows(px,x.isoformat())
            except Exception:
                if n==7:raise
        raise ValueError('No price date')
    nd,np,npx=files(day,'now'); od,op,opx=files(target,'old')
    url=f'https://www.nseindia.com/api/corporates-corporateActions?index=equities&from_date={od:%d-%m-%Y}&to_date={nd:%d-%m-%Y}'
    actions=Path(fixtures,'actions.txt').read_bytes() if fixtures else download(url)
    excluded=excluded_actions(actions,od,nd)
    funds={}
    for path in (MF/'p').glob('*.json'):
        if path.name.startswith('_'):continue
        for code,p in json.loads(path.read_text(encoding='utf8')).items():
            v=portfolio_earnings(p,npx,opx,np,op,excluded)
            if v:funds[code]=v
    if len(funds)<100:raise ValueError('Insufficient fund coverage; retain the last verified snapshot')
    etfs={}
    holdings=MF.parent/'etf_holdings.json'
    if holdings.exists():
        for ticker,p in json.loads(holdings.read_text(encoding='utf8')).get('etfs',{}).items():
            v=portfolio_earnings(p,npx,opx,np,op,excluded)
            if v:
                v['holdingsSource']=p.get('src')
                # A same-index proxy is disclosed in the screener, but is not
                # evidence of this ETF's own complete equity portfolio.
                v['fullDisclosure']=v['fullDisclosure'] and p.get('src')=='own'
                etfs[ticker]=v
    out={'v':1,'asOf':nd.isoformat(),'priorAsOf':od.isoformat(),
         'generated':datetime.now(timezone.utc).isoformat(),'funds':funds,'etfs':etfs,
         'method':'Current disclosed equity quantities held constant; TTM EPS inferred from NSE closing price / symbol P/E. Corporate-action-affected securities excluded. This is look-through earnings growth, not fund EPS or a forecast.',
         'sources':{'prices':BASE+'/cm/','pe':BASE+'/equities/peDetail/','actions':url},
         'audit':{'funds':len(funds),'fullDisclosureFunds':sum(x['fullDisclosure'] for x in funds.values()),'etfs':len(etfs),'fullDisclosureETFs':sum(x['fullDisclosure'] for x in etfs.values()),'excludedISINs':len(excluded)}}
    dest=MF/'fund_earnings.json';tmp=dest.with_suffix('.tmp')
    tmp.write_text(json.dumps(out,separators=(',',':')),encoding='utf8');tmp.replace(dest)
    print(json.dumps(out['audit']))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--fixtures');a=ap.parse_args();build(a.fixtures)
