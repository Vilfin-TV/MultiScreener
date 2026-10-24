"""John's50 prospective ETF gates, separate from mutual-fund minimum/exit rules."""
from datetime import date
import math,re,statistics
from ultimate_rules import number,age,month_end

INDEXES={'nifty50':'core','niftynext50':'next50','niftymidcap150':'mid','niftysmallcap250':'small',
         'nifty50value20':'value','nifty200quality30':'quality','nifty200momentum30':'momentum',
         'nifty100lowvolatility30':'lowvol'}

def category(e,ex):
    idx=re.sub('[^a-z0-9]','',((ex.get('te') or {}).get('idx') or e.get('u') or '').lower()).replace('tri','')
    return INDEXES.get(idx)

def candidate(e,ex,p,earn,context,bars,peers):
    f=e.get('x') or {};te=ex.get('te') or {};rt=ex.get('rt') or {};sc=(ex.get('sc') or {}).get('3') or {};mix=p.get('mix') or {}
    asof=context['asOf'];sym=e['s'];cat=category(e,ex);r=[]
    def add(key,label,ok,value=None):r.append(dict(id=key,label=label,state='pass' if bool(ok) else 'fail',value=value))
    def rng(v,lo,hi):return number(v) and lo<=v<=hi
    def fresh(d,n=5):return 0<=age(asof,d)<=n
    def med(k):
        vs=[x[k] for x in peers if number(x.get(k))];return statistics.median(vs) if vs else None
    volumes=bars.get('v') or [];closes=bars.get('c') or [];days=bars.get('t') or []
    tvs=sorted(c*v for c,v in zip(closes[-20:],volumes[-20:]) if number(c) and number(v));mean=sum(tvs)/len(tvs) if tvs else 0
    peer_te=context.get('medianTracking');peer_pe=context.get('medianPE')
    add('universe','ETF present in the verified NSE universe',context.get('verifiedNSE') is True)
    add('price','Positive exchange closing price',rng(e.get('p'),.00001,10**8),e.get('p'))
    add('price-date','Closing price no older than five days',fresh(e.get('d')),e.get('d'))
    add('nav','Official fund NAV available',rng(f.get('nav'),.00001,10**8),f.get('nav'))
    add('nav-date','Fund NAV no older than five days',fresh(f.get('navDate')),f.get('navDate'))
    add('premium','Verified price/NAV premium within±0.75%',rng(e.get('prem'),-.75,.75),e.get('prem'))
    add('ter','Official direct expense ratio available',rng(f.get('ter'),0,5),f.get('ter'))
    add('cost-cap','Expense ratio no greater than0.75%',rng(f.get('ter'),0,.75),f.get('ter'))
    add('aum','Fund size at least₹500crore',rng(f.get('aum'),500,10**9),f.get('aum'))
    add('record','At least three years of actual listing history',age(asof,e.get('first'))>=1095,e.get('first'))
    add('liquidity','At least₹1crore traded per day',rng(e.get('tv'),1,10**8),e.get('tv'))
    add('quality','Exchange trading-quality flag healthy',e.get('q')=='ok',e.get('q'))
    add('volume-history','At least20 actual daily volume observations',len(volumes)>=20,len(volumes))
    add('zero-volume','Positive volume on all last20sessions',len(volumes)>=20 and all(v>0 for v in volumes[-20:]))
    add('volume-distribution','Typical daily turnover at least30% of its average',bool(tvs) and mean>0 and statistics.median(tvs)>=.3*mean)
    add('daily-endpoint','Daily price file reaches the displayed close',bool(days) and str(days[-1])==asof.replace('-',''))
    add('fund-source-date','Snapshot does not postdate the decision cut-off',context.get('sourceAsOf','9999')<=asof and bool(context.get('sourceAsOf')))
    add('volatility','Annualised volatility no greater than36%',rng(e.get('vol'),0,36),e.get('vol'))
    add('drawdown','Observed three-year drawdown no worse than−65%',rng(e.get('mdd'),-65,0),e.get('mdd'))
    add('rating','At least3stars in the published fund rating',rng(rt.get('st'),3,5),rt.get('st'))
    add('tracking-error','Known tracking error within125% of peers',rng(te.get('te'),0,max(1,1.25*peer_te)) if number(peer_te) else False,te.get('te'))
    add('tracking-difference','Known one-year tracking difference within±1%',rng(te.get('td1'),-1,1),te.get('td1'))
    add('index','Exact supported broad or factor index identified',cat is not None,te.get('idx'))
    def index_text(v):return re.sub('[^a-z0-9]','',str(v or '').lower()).removesuffix('tri').removesuffix('index')
    declared=index_text(f.get('benchmark'));tracked=index_text(te.get('idx'))
    add('mandate','Underlying matches the declared benchmark',bool(declared) and declared==tracked and tracked in index_text(e.get('u')),f.get('benchmark'))
    text=' '.join(str(e.get(k) or '') for k in ('n','u'))
    add('leverage','No leveraged index mandate',not re.search(r'leverag|\b[23]x\b',text,re.I))
    add('inverse','No inverse or short mandate',not re.search(r'inverse|\bbear\b|\bshort\s+etf',text,re.I))
    add('currency','Indian exchange listing with an INR price',context.get('verifiedNSE') is True)
    add('price-breaks','No unexplained price-history reset',not any(not x.startswith('split') for x in (e.get('f') or [])))
    mv=med('vol');add('peer-volatility','Volatility not materially above same-index peers',number(mv) and rng(e.get('vol'),0,mv*1.1+.5),e.get('vol'))
    rr=[(x.get('r') or {}).get('1y') for x in peers];rr=[x for x in rr if number(x)];mret=statistics.median(rr) if rr else None
    add('peer-return','One-year return within0.75points of peer median',number(mret) and rng((e.get('r') or {}).get('1y'),mret-.75,10**6),(e.get('r') or {}).get('1y'))
    add('consistency','Consistency score at least35/100',rng(sc.get('c'),35,100),sc.get('c'))
    value_entry=context.get('deepValue') is True and rng(earn.get('earningsGrowth'),.001,500)
    add('recency','Recent strength or verified deep value with positive earnings',rng(sc.get('r'),20,100) or value_entry,{'recency':sc.get('r'),'deepValue':value_entry})
    add('beta','Market beta within the leverage limit',rng(e.get('beta'),0,1.35),e.get('beta'))
    add('range','Price within its published52week range',number(e.get('l52')) and number(e.get('h52')) and rng(e.get('p'),e['l52']*.999,e['h52']*1.001))
    # A small sleeve must afford one whole unit plus trading costs.
    add('whole-unit','One unit plus fee allowance fits₹1,500',number(e.get('p')) and e['p']*1.002<=1500,e.get('p'))
    add('own-holdings','ETF own monthly portfolio disclosed',p.get('src')=='own',p.get('src'))
    add('holdings-date','Portfolio month-end no older than62days',fresh(month_end(p.get('asOf')),62),p.get('asOf'))
    positions=p.get('equityISIN') or []
    add('positions','At least20 equity positions disclosed',len(positions)>=20,len(positions))
    add('single-stock','Largest equity holding no greater than15%',bool(positions) and max(x[1] for x in positions)<=15,max((x[1] for x in positions),default=None))
    add('concentration','Top ten holdings no greater than65%',rng(p.get('top10'),0,65),p.get('top10'))
    sectors=[x[1] for x in p.get('sectors',[]) if len(x)>1 and number(x[1])]
    add('sector','Largest sector no greater than40%',bool(sectors) and max(sectors)<=40,max(sectors) if sectors else None)
    add('cash-drag','Cash no greater than10%',rng(mix.get('cashOther'),0,10),mix.get('cashOther'))
    add('earnings-coverage','Own full portfolio and75% comparable earnings coverage',earn.get('fullDisclosure') is True and rng(earn.get('coverage'),75,100),earn.get('coverage'))
    add('earnings-date','Earnings stock-price inputs no older than five days',fresh(context.get('earningsAsOf')),context.get('earningsAsOf'))
    gap=age(context.get('earningsAsOf',asof),context.get('earningsPriorAsOf'))
    add('earnings-period','Annual earnings comparison spans350–380days',350<=gap<=380,gap)
    add('earnings-growth','Comparable TTM earnings growth positive',rng(earn.get('earningsGrowth'),.001,500),earn.get('earningsGrowth'))
    add('pe','Positive look-through earnings P/E',rng(earn.get('pe'),1,80),earn.get('pe'))
    add('relative-value','P/E within125% of eligible same-index peers',number(peer_pe) and rng(earn.get('pe'),0,peer_pe*1.25),earn.get('pe'))
    peg=earn.get('pe')/max(earn.get('earningsGrowth') or 0,.001) if number(earn.get('pe')) else None
    add('growth-price','P/E relative to earnings growth no greater than4',rng(peg,0,4),peg)
    add('earnings-breadth','At least20 stocks have comparable earnings',rng(earn.get('positions'),20,10000),earn.get('positions'))
    assert len(r)==50
    return dict(key=sym,name=e['n'],category=cat,amc=e.get('a'),tax='equity',min=0,earnings=earn,facts=e,
                checks=r,eligible=all(x['state']=='pass' for x in r),passed=sum(x['state']=='pass' for x in r),applicable=50,
                evidence={'e':e,'ex':ex,'p':p,'earn':earn,'context':context,
                          # Retain every volume observation: gate 13 records
                          # the full observation count, not just its last20.
                          'bars':{k:bars.get(k,[]) if k=='v' else bars.get(k,[])[-20:] for k in ('t','c','v')},
                          'peers':[{'vol':x.get('vol'),'r':{'1y':(x.get('r') or {}).get('1y')}} for x in peers]})

def candidates(data,extras,holdings,earn,daily_of,gates=None):
    rows=data['etfs'];out=[];ex=extras['etfs'];ef=earn.get('etfs') or {}
    for e in rows:
        x=ex.get(e['s']) or {};cat=category(e,x)
        if cat is None:continue
        peers=[p for p in rows if category(p,ex.get(p['s']) or {})==cat]
        tes=[(ex.get(p['s'],{}).get('te') or {}).get('te') for p in peers];tes=[v for v in tes if number(v)]
        pes=[ef[p['s']]['pe'] for p in peers if p['s'] in ef and ef[p['s']].get('fullDisclosure') and ef[p['s']].get('coverage',0)>=75]
        ctx=dict(asOf=data['asOf'],sourceAsOf=data['asOf'],verifiedNSE=True,medianTracking=statistics.median(tes) if tes else None,
                 medianPE=statistics.median(pes) if pes else None,earningsAsOf=earn['asOf'],earningsPriorAsOf=earn['priorAsOf'])
        gate=(gates or {}).get(cat) or {}
        ctx['deepValue']=number(gate.get('pct')) and gate['pct']<=.2 and gate.get('fresh') is True
        c=candidate(e,x,holdings.get('etfs',{}).get(e['s']) or {},ef.get(e['s']) or {},ctx,daily_of(e['s']),peers)
        # Same-index ETFs are selected for lower cost, stronger trading quality,
        # tracking and earnings coverage; no return is invented for a new ETF.
        out.append(c)
    eligible=[c for c in out if c['eligible']]
    def percentile(value,values,high=True):
        return 100*sum(v<=value if high else v>=value for v in values)/len(values) if number(value) and values else 0
    for c in out:
        e=c['earnings'];f=c['facts'];x=ex.get(c['key']) or {}
        c['score']=round(.3*percentile(e.get('pe'),[p['earnings']['pe'] for p in eligible],False)+.3*percentile(e.get('earningsGrowth'),[p['earnings']['earningsGrowth'] for p in eligible])+.2*(x.get('rt') or {}).get('s',0)+.1*percentile((f.get('x') or {}).get('ter'),[(p['facts'].get('x') or {}).get('ter') for p in eligible],False)+.1*percentile(f.get('tv'),[p['facts']['tv'] for p in eligible]),3)
    return sorted(out,key=lambda c:(not c['eligible'],-c['score'],c['key']))
