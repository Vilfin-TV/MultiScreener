"""John's prospective eligibility policy. Missing evidence blocks a purchase.

This version is fixed before the first trade. It does not tune thresholds to a
backtest or promise the 16% target. Historical fundamental inputs must never be
replaced with today's disclosure when evaluating an earlier decision.
"""
from datetime import date, timedelta
import calendar, math, statistics

VERSION='john-2026-10-v1'
START='2026-10-26'
EQUITY_CATEGORIES={'flexi','mid','small','multi','large','largemid','value','contra','focused','multiasset','baf','aggressive'}
PARK_CATEGORIES={'liquid','money','shortdur','meddur','arbitrage'}

def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def age(asof,s):
    try:return (date.fromisoformat(asof)-date.fromisoformat(s)).days
    except (ValueError,TypeError):return 10**6
def month_end(s):
    try:
        y,m=map(int,s.split('-'));return date(y,m,calendar.monthrange(y,m)[1]).isoformat()
    except (ValueError,TypeError,AttributeError):return None

def windows(year,month,is_open):
    """One first-week session and one last-week session; October starts on 26th.

    Holidays roll within their own windows only. No contribution is fabricated
    when an entire window is closed. The monthly amount remains capped at20k.
    """
    n=calendar.monthrange(year,month)[1]
    ds=[date(year,month,d) for d in range(1,n+1) if is_open(date(year,month,d))]
    first=next((d for d in ds if d.day<=7 and d.isoformat()>=START),None)
    last=next((d for d in ds if d.day>=max(22,n-6) and d.isoformat()>=START),None)
    return [(d,10000 if first and last else 20000) for d in (first,last) if d]

def checks(f,detail,p,earnings,context):
    """50 named checks; asset-inapplicable tests are explicitly N/A, not passes."""
    asof=context['asOf'];eq=f.get('sub') not in PARK_CATEGORIES
    info=detail.get('info') or {};risk=detail.get('risk') or {};roll=(detail.get('roll') or {}).get('3') or {}
    e=earnings or {};mix=p.get('mix') or {};credit=dict(p.get('credit') or [])
    results=[]
    def add(key,label,ok,value=None,applicable=True):
        results.append(dict(id=key,label=label,state=('pass' if bool(ok) else 'fail') if applicable else 'na',value=value))
    def rng(v,lo,hi):return number(v) and lo<=v<=hi
    def fresh(s,days):return 0<=age(asof,s)<=days
    add('scheme','Scheme present in the verified screener',bool(f.get('code')))
    add('universe','Verified Direct-Growth universe',context.get('directGrowth') is True)
    add('nav','Positive official NAV',rng(f.get('nav'),.000001,10**9),f.get('nav'))
    add('nav-age','NAV no older than five calendar days',fresh(f.get('navDate'),5),f.get('navDate'))
    add('no-lookahead','All snapshots available by the decision cut-off',context.get('sourceAsOf','9999')<=asof and context.get('sourceAsOf') is not None)
    add('purchase','Fresh lump-sum purchases explicitly permitted','L' in (f.get('buy') or ''),f.get('buy'))
    add('minimum','Proposed purchase meets the verified lump-sum minimum',number(f.get('lumpMin')) and f['lumpMin']>0 and f['lumpMin']<=context.get('amount',0),f.get('lumpMin'))
    add('lock','No mandatory lock-in',f.get('lock')==0,f.get('lock'))
    add('tax','Tax treatment identified',f.get('tax') in ('equity','debt','other'),f.get('tax'))
    add('exit','Exit-load schedule independently parsed',context.get('exitKnown') is True)
    add('history','At least three years of actual scheme history',age(asof,f.get('inc'))>=1095,f.get('inc'))
    add('aum-floor','Fund size at least ₹500 crore',rng(f.get('aum'),500,10**9),f.get('aum'))
    add('capacity','Small-cap size below ₹60,000 crore',f.get('sub')!='small' or rng(f.get('aum'),500,60000),f.get('aum'))
    add('cost','Direct-plan TER within the asset-class limit',rng(f.get('ter'),0,2.25 if eq else .8),f.get('ter'))
    add('cost-date','Expense-ratio disclosure no older than45days',fresh(info.get('terDate'),45),info.get('terDate'))
    add('riskometer','Regulatory risk classification available',rng(f.get('risk'),0,6),f.get('risk'))
    add('volatility','Annualised volatility within policy limit',rng(f.get('std'),0,36 if eq else 6),f.get('std'))
    mdd=(detail.get('mddAll') or {}).get('mdd')
    add('drawdown','Observed historical drawdown within limit',rng(mdd,-65 if eq else -15,0),mdd)
    add('sharpe','Risk-adjusted return above the rejection floor',rng(f.get('sharpe'),-.2,100),f.get('sharpe'))
    add('sortino','Downside-adjusted return non-negative',rng(f.get('sortino'),0,100),f.get('sortino'))
    add('return3','Three-year CAGR above the basic hurdle',rng(f.get('r3y'),6 if eq else 3,100),f.get('r3y'))
    add('return5','Five-year CAGR positive when available',f.get('r5y') is None or rng(f.get('r5y'),0,100),f.get('r5y'))
    add('rolling-sample','At least12 independent three-year rolling observations',rng(roll.get('n'),12,100000),roll.get('n'))
    add('rolling-positive','At least90% of three-year windows positive',rng(roll.get('pos'),90,100),roll.get('pos'))
    tail_floor=-15 if f.get('sub')=='small' else -12 if f.get('sub')=='mid' else -8 if eq else -4
    add('rolling-worst',f'Worst three-year window above the category risk floor ({tail_floor}% CAGR)',rng(roll.get('min'),tail_floor,100),roll.get('min'))
    add('consistency','Consistency score at least35/100',rng(f.get('cons'),35,100),f.get('cons'),eq)
    value_entry=context.get('deepValue') is True and rng(e.get('earningsGrowth'),.001,500)
    add('recency','Recent strength or verified deep value with positive earnings',rng(f.get('rec'),20,100) or value_entry,{'recency':f.get('rec'),'deepValue':value_entry},eq)
    add('benchmark','Three-year benchmark-beating frequency at least40%',rng(f.get('beat3'),40,100),f.get('beat3'),eq)
    add('beta','Market beta within the leverage limit',rng(f.get('beta'),0,1.35),f.get('beta'),eq)
    add('down-capture','Downside capture no greater than120% for a comparable equity mandate',rng(risk.get('downCap'),0,120),risk.get('downCap'),eq and f.get('sub')!='multiasset')
    add('portfolio','Official monthly portfolio present',bool(p.get('nAll')))
    add('portfolio-age','Portfolio month-end no older than62days',fresh(month_end(p.get('asOf')),62),p.get('asOf'))
    weights=[v for v in mix.values() if number(v)]
    add('portfolio-total','Disclosed asset weights reconcile within5%',bool(weights) and 95<=sum(weights)<=105,round(sum(weights),2))
    add('diversification','At least20 disclosed positions',rng(p.get('nAll'),20,100000),p.get('nAll'))
    add('concentration','Top ten equity positions no greater than65%',rng(p.get('top10'),0,65),p.get('top10'),eq)
    sectors=[x[1] for x in p.get('sectors',[]) if len(x)>1 and number(x[1])]
    add('sector','Largest sector no greater than40%',bool(sectors) and max(sectors)<=40,max(sectors) if sectors else None,eq)
    positions=p.get('equityISIN') or []
    add('single-stock','Largest equity holding no greater than12%',bool(positions) and max(x[1] for x in positions)<=12,max((x[1] for x in positions),default=None),eq)
    add('cash-drag','Cash share no greater than30%',rng(mix.get('cashOther'),0,30),mix.get('cashOther'),eq)
    add('foreign','Foreign-equity share within35%',rng(mix.get('overseas',0),0,35),mix.get('overseas',0),eq)
    add('asset-mix','Equity share consistent with the selected mandate',rng(mix.get('equity'),30 if f.get('sub')=='multiasset' else 60,100),mix.get('equity'),eq)
    add('full-holdings','Complete equity disclosure used for fundamentals',e.get('fullDisclosure') is True,applicable=eq)
    add('earnings-coverage','Look-through earnings covers at least75% of equities',rng(e.get('coverage'),75,100),e.get('coverage'),eq)
    add('earnings-date','Current earnings inputs no older than five days',fresh(context.get('earningsAsOf'),5),context.get('earningsAsOf'),eq)
    gap=age(context.get('earningsAsOf',asof),context.get('earningsPriorAsOf'))
    add('earnings-comparison','Comparable annual earnings observation within350–380days',350<=gap<=380,gap,eq)
    add('earnings-growth','Look-through TTM earnings growth positive',rng(e.get('earningsGrowth'),.001,500),e.get('earningsGrowth'),eq)
    add('pe','Positive look-through P/E',rng(e.get('pe'),1,80),e.get('pe'),eq)
    med=context.get('categoryPE')
    add('relative-value','P/E at most125% of its eligible category median',number(med) and number(e.get('pe')) and e['pe']<=med*1.25,e.get('pe'),eq)
    peg=e.get('pe')/max(e.get('earningsGrowth') or 0,.001) if number(e.get('pe')) else None
    add('growth-price','P/E relative to earnings growth no greater than4',rng(peg,0,4),round(peg,3) if peg else None,eq)
    add('earnings-breadth','At least20 stocks have comparable earnings',rng(e.get('positions'),20,10000),e.get('positions'),eq)
    add('actions','Excluded corporate-action weight no greater than20%',rng(e.get('corporateActionExcludedWeight'),0,20),e.get('corporateActionExcludedWeight'),eq)
    assert len(results)==50
    # Parking allocations also require explicit credit-quality evidence, independent
    # of inapplicable equity-earnings tests. Kept outside the50 equity registry.
    if not eq:
        rated=sum(credit.values());safe=sum(v for k,v in credit.items() if k in ('AAA & equivalent','Sovereign','A1+ (money market)'))
        add('parking-credit','At least90% of rated debt in AAA, sovereign orA1+',rated>0 and safe/rated>=.9,round(safe/rated*100,2) if rated else None,f.get('sub')!='arbitrage')
    return {'checks':results,'passed':sum(x['state']=='pass' for x in results),
            'applicable':sum(x['state']!='na' for x in results),'eligible':all(x['state']!='fail' for x in results)}
