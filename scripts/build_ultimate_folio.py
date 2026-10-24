"""Prospective, auditable John model snapshots; no performance-target fitting."""
from pathlib import Path
from datetime import date,datetime,timezone
import argparse,gzip,hashlib,json,statistics
from ultimate_rules import checks,EQUITY_CATEGORIES,PARK_CATEGORIES,VERSION,START,number,age
from ultimate_history import metrics,current_mix
from ultimate_etf import candidates as etf_candidates
from sim_engine import exit_rule

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data'
def read(p,default=None):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except FileNotFoundError:return default
def rank_percent(v,values,high=True):
    if not number(v) or not values:return 0
    return 100*sum(x<=v if high else x>=v for x in values)/len(values)

def mf_candidates(sc,earn,market=None):
    fs=[dict(zip(sc['cols'],r)) for r in sc['rows']]
    details={};portfolios={}
    for sub in {f['sub'] for f in fs if f['sub'] in EQUITY_CATEGORIES|PARK_CATEGORIES}:
        details.update(read(DATA/'mf/d'/f'{sub}.json',{}));portfolios.update(read(DATA/'mf/p'/f'{sub}.json',{}))
    ep=earn['funds'];medians={}
    for sub in EQUITY_CATEGORIES:
        vs=[ep[str(f['code'])]['pe'] for f in fs if f['sub']==sub and str(f['code']) in ep and ep[str(f['code'])].get('fullDisclosure') and ep[str(f['code'])].get('coverage',0)>=75]
        if vs:medians[sub]=statistics.median(vs)
    out=[]
    for f in fs:
        sub=f['sub'];code=str(f['code'])
        if sub not in EQUITY_CATEGORIES|PARK_CATEGORIES:continue
        d=details.get(code) or {};p=portfolios.get(code) or {};e=ep.get(code) or {}
        er=exit_rule((d.get('info') or {}).get('exitLoad'),f.get('exitNil'))
        context=dict(asOf=sc['asOf'],sourceAsOf=sc['asOf'],directGrowth=True,amount=3000 if sub=='small' else 7000 if sub=='flexi' else 5000,exitKnown=er.get('known',False),
                     earningsAsOf=earn['asOf'],earningsPriorAsOf=earn['priorAsOf'],categoryPE=medians.get(sub))
        g=((market or {}).get('gates') or {}).get({'large':'core','multiasset':'flexi'}.get(sub,sub)) or {}
        context['deepValue']=number(g.get('pct')) and g['pct']<=.2 and 0<=age(sc['asOf'],(market or {}).get('valuationAsOf'))<=5
        r=checks(f,d,p,e,context)
        out.append(dict(key=code,name=f['name'],category=sub,amc=f['amc'],tax=f['tax'],min=f['lumpMin'],facts=f,
                        earnings=e,evidence={'f':f,'detail':d,'p':p,'earnings':e,'context':context},**r))
    # Ranking occurs only after eligibility. Lower P/E and stronger comparable
    # earnings share60%; consistency, observed risk and costs share40%.
    for c in out:
        peers=[x for x in out if x['category']==c['category'] and x['eligible']]
        f=c['facts'];e=c['earnings']
        if c['category'] in PARK_CATEGORIES:
            c['score']=round(.55*rank_percent(f.get('r3y'),[x['facts']['r3y'] for x in peers])+ .25*rank_percent(f.get('std'),[x['facts']['std'] for x in peers],False)+.2*rank_percent(f.get('ter'),[x['facts']['ter'] for x in peers],False),3)
        else:
            c['score']=round(.3*rank_percent(e.get('pe'),[x['earnings']['pe'] for x in peers],False)+.3*rank_percent(e.get('earningsGrowth'),[x['earnings']['earningsGrowth'] for x in peers])+.2*rank_percent(f.get('cons'),[x['facts']['cons'] for x in peers])+.1*rank_percent(f.get('std'),[x['facts']['std'] for x in peers],False)+.1*rank_percent(f.get('ter'),[x['facts']['ter'] for x in peers],False),3)
    return sorted(out,key=lambda x:(not x['eligible'],-x['score'],x['key']))

def choose_mf(candidates,market,asof):
    gate=(market.get('gates') or {}).get('core') or {};pct=gate.get('pct')
    if not number(pct) or not 0<=age(asof,market.get('valuationAsOf'))<=5:mode='C'
    elif pct>=.8:mode='B'
    else:mode='A'
    month=(date.fromisoformat(asof).year-2026)*12+date.fromisoformat(asof).month-10
    # Protect a goal approaching its seventh year rather than chasing a return
    # target with higher risk in the final months.
    glide=.6 if month>=72 else .3 if month>=60 else 0
    if mode=='A':desired=[('flexi',35),('mid',25),('small',15),('multiasset',25)]
    elif mode=='B':desired=[('flexi',35),('multiasset',25),('parking',40)]
    else:desired=[('parking',100)]
    if glide and mode in ('A','B'):
        parking=max(glide*100,sum(w for k,w in desired if k=='parking'))
        equity=sum(w for k,w in desired if k!='parking')
        desired=[(k,w*(100-parking)/equity) for k,w in desired if k!='parking']+[('parking',parking)]
    eligible=[x for x in candidates if x['eligible']];chosen=[];amc={};held=set()
    for cat,w in desired:
        pool=[c for c in eligible if (c['category']==cat if cat!='parking' else c['category'] in PARK_CATEGORIES) and c['key'] not in held]
        c=next((x for x in pool if amc.get(x['amc'],0)+w<=60 or cat=='parking'),None)
        if c:
            chosen.append(dict(key=c['key'],name=c['name'],category=c['category'],weight=round(w,4),amc=c['amc'],score=c['score'],checks=c['checks'],earnings=c['earnings'],min=c['min'],tax=c['tax']))
            held.add(c['key']);amc[c['amc']]=amc.get(c['amc'],0)+w
    missing=round(100-sum(x['weight'] for x in chosen),4)
    # A failed sleeve is funded into a verified parking choice or held as cash.
    # Its failed fund is never inserted merely to force three or five positions.
    parking=next((x for x in chosen if x['category'] in PARK_CATEGORIES),None)
    if missing and not parking and len(chosen)<5:
        c=next((x for x in eligible if x['category'] in PARK_CATEGORIES and x['key'] not in held),None)
        if c:
            parking=dict(key=c['key'],name=c['name'],category=c['category'],weight=0,amc=c['amc'],score=c['score'],checks=c['checks'],earnings=c['earnings'],min=c['min'],tax=c['tax']);chosen.append(parking)
    if missing and parking:parking['weight']=round(parking['weight']+missing,4);missing=0
    return dict(mode=mode,valuationPercentile=pct,selected=chosen,cashWeight=missing,
                reason={'A':'Diversified active equity and multi-asset allocation, subject to every applicable check.','B':'Expensive broad-market valuation: reduced equity exposure and verified parking.','C':'Reliable valuation or eligible investment evidence unavailable: verified parking or cash.'}[mode],
                glideToParking=glide)

def observed_histories(sc):
    cache=ROOT/'.mfcache/hist.json.gz'
    if not cache.exists():return {},'Full daily NAV cache is unavailable; historical metrics are not inferred from weekly points.'
    from build_mf_screener import clean_points
    with gzip.open(cache,'rt',encoding='utf-8') as f:raw=json.load(f)
    out={}
    latest={str(r[sc['cols'].index('code')]):(r[sc['cols'].index('navDate')],r[sc['cols'].index('nav')]) for r in sc['rows']}
    for k,p in raw.items():
        if k in latest:
            d,v=latest[k];day=date.fromisoformat(d).toordinal();p=[x for x in p if x[0]!=day]+[[day,v]]
        out[k]=clean_points(p)[0]
    return out,None

def choose_etf(candidates,mode):
    groups=[('core',35),('next50',25),('mid',25),('satellite',15)] if mode=='A' else [('core',30),('next50',20),('defensive-factor',20)] if mode=='B' else []
    eligible=[c for c in candidates if c['eligible']];pools=[]
    for cat,w in groups:
        kinds={'value','quality','momentum','lowvol','small'} if cat=='satellite' else {'quality','lowvol'} if cat=='defensive-factor' else {cat}
        pools.append(([c for c in eligible if c['category'] in kinds][:6],w))
    best=(None,(-1,-1))
    def walk(i,chosen,amcs,filled,score):
        nonlocal best
        if i==len(pools):
            if (filled,score)>best[1]:best=(list(chosen),(filled,score))
            return
        pool,w=pools[i]
        for c in pool:
            if c['key'] in {x[0]['key'] for x in chosen} or amcs.get(c['amc'],0)+w>60:continue
            walk(i+1,chosen+[(c,w)],{**amcs,c['amc']:amcs.get(c['amc'],0)+w},filled+w,score+c['score']*w)
        walk(i+1,chosen,amcs,filled,score)
    walk(0,[],{},0,0)
    selected=[{k:c[k] for k in ('key','name','category','amc','score','checks','earnings','min','tax')}|{'weight':w} for c,w in best[0]]
    return dict(mode=mode,selected=selected,cashWeight=100-sum(x['weight'] for x in selected),
                reason='Broad-market and factor ETFs must pass all50gates. Missing or expensive sleeves remain cash; allocation searches eligible provider combinations within the60%provider cap.')

def etf_histories(selected,asof,download=False):
    path=ROOT/'.mfcache/ultimate_etf_hist.json';cached=read(path,{})
    if download:
        import yfinance as yf
        for c in selected:
            sym=c['key'];frame=yf.Ticker(sym+'.NS').history(start='2000-01-01',auto_adjust=True,actions=True,raise_errors=True)
            points=[(d.date().isoformat(),float(v)) for d,v in frame['Close'].items() if number(float(v)) and v>0 and d.date().isoformat()<=asof]
            if not points or age(asof,points[-1][0])>5:raise ValueError('ETF historical endpoint unavailable: '+sym)
            cached[sym]=points
        path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(cached,separators=(',',':')),encoding='utf-8')
    return cached

def build(download_etf=False):
    sc=read(DATA/'mf/screener.json');ss=read(DATA/'mf/smartsip.json');earn=read(DATA/'mf/fund_earnings.json')
    if not all((sc,ss,earn)):raise ValueError('Verified input snapshots are required')
    candidates=mf_candidates(sc,earn,ss['market']);plan=choose_mf(candidates,ss['market'],sc['asOf'])
    es=read(DATA/'etf_momentum.json');ex=read(DATA/'etf_extras.json');eh=read(DATA/'etf_holdings.json');macro=read(DATA/'mf/macro.json')
    ids={'core':'n50','next50':'nn50','mid':'mid150','small':'sml250','value':'value20','quality':'quality30','momentum':'mom30','lowvol':'lowvol30'}
    gates={k:{'pct':(macro.get('valuation',{}).get(v) or {}).get('pePct'),'fresh':0<=age(es['asOf'],macro.get('valuationAsOf'))<=5} for k,v in ids.items()}
    ec=etf_candidates(es,ex,eh,earn,lambda sym:read(DATA/'etf/d'/f'{sym}.json',{}),gates)
    ep=choose_etf(ec,plan['mode'])
    if plan['glideToParking']:
        for c in ep['selected']:c['weight']=round(c['weight']*(1-plan['glideToParking']),4)
        ep['cashWeight']=round(100-sum(c['weight'] for c in ep['selected']),4)
    ehist=etf_histories(ep['selected'],es['asOf'],download_etf)
    for c in ep['selected']:c['history']=metrics(ehist.get(c['key'],[]),es['asOf'])
    for c in ep['selected']:
        first=next((e.get('first') for e in es['etfs'] if e['s']==c['key']),None)
        c['history']['inceptionVerified']=bool(first and abs(age(c['history']['from'],first))<=7)
    ep['history']=current_mix(ehist,{c['key']:c['weight'] for c in ep['selected']},es['asOf'])
    ep['history']['source']='Yahoo Finance adjusted daily closing prices, including reinvested distributions; not intraday execution prices.'
    histories,warning=observed_histories(sc)
    for c in plan['selected']:c['history']=metrics(histories.get(c['key'],[]),sc['asOf'])
    by_code={str(r[sc['cols'].index('code')]):r[sc['cols'].index('inc')] for r in sc['rows']}
    for c in plan['selected']:
        first=by_code.get(c['key']);c['history']['inceptionVerified']=bool(first and abs(age(c['history']['from'],first))<=7)
    plan['history']=current_mix(histories,{c['key']:c['weight'] for c in plan['selected']},sc['asOf'])
    public=[]
    for cat in sorted(EQUITY_CATEGORIES|PARK_CATEGORIES):
        public += [x for x in candidates if x['category']==cat][:3]
    previous=read(DATA/'sim/john-mf.json',{})
    held={str(x['k']) for x in (previous.get('detail') or {}).get('hold',[])}
    held.update(c['key'] for c in ((previous.get('ultimate') or {}).get('plan') or {}).get('selected',[]))
    public += [c for c in candidates if c['key'] in held and c['key'] not in {x['key'] for x in public}]
    out=dict(v=1,policyVersion=VERSION,asOf=sc['asOf'],start=START,goalYears=7,targetAnnualReturn=16,
             targetNote='Aspirational annualised return target, not a forecast or guarantee. Parking and cash can return much less.',
             availableAt=datetime.now(timezone.utc).isoformat(),budget={'mf':20000,'etf':20000,'costsIncluded':True},
             rules={'monthlyFundLimit':5,'regularWindows':'First and last trading weeks','durationMonths':84,'checkCount':50,
                    'residency':'India resident','otherTaxableIncome':0,'regime':'new','maxAMCEquityWeight':60,'smallCapLimit':20,
                    'equityRankingWeights':{'lowerPE':30,'higherEarningsGrowth':30,'consistency':20,'lowerVolatility':10,'lowerTER':10}},
             mf=plan,etf=ep,candidates={'mf':public,'etf':ec[:30]},coverage={'mfConsidered':len(candidates),'mfEligible':sum(x['eligible'] for x in candidates),'etfConsidered':len(ec),'etfEligible':sum(x['eligible'] for x in ec)},
             historicalWarning=warning,sources={'screenerGenerated':sc['generated'],'earningsAsOf':earn['asOf'],'earningsPriorAsOf':earn['priorAsOf']})
    # Preserve the source facts needed to recompute every selected gate in an
    # independent ledger audit, rather than trusting a stored pass count.
    for product,chosen,pool in [('mf',plan,candidates),('etf',ep,ec)]:
        by={c['key']:c for c in pool}
        for c in chosen['selected']:c['evidence']=by[c['key']]['evidence']
    # Current eligible alternatives support revalidation and tax-aware rotation.
    public=[c for c in candidates if c['eligible']]+[c for c in public if not c['eligible']]
    out['candidates']={'mf':public,'etf':ec}
    from ultimate_execution import digest
    from ultimate_backtest import scenarios
    out['backtest']={'mf':scenarios(histories,{c['key']:c['weight'] for c in plan['selected']},sc['asOf'],'mf'),'etf':scenarios(ehist,{c['key']:c['weight'] for c in ep['selected']},es['asOf'],'etf')}
    out['snapshotHash']=digest(out)
    path=DATA/'ultimate_folio.json';path.write_text(json.dumps(out,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'mfPlan':[(x['name'],x['weight']) for x in plan['selected']],'etfPlan':[(x['key'],x['weight']) for x in ep['selected']],'mode':plan['mode'],'cash':{'mf':plan['cashWeight'],'etf':ep['cashWeight']},'historicalWarning':warning}))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--download-etf-history',action='store_true');args=ap.parse_args();build(args.download_etf_history)
