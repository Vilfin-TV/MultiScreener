"""Observed NAV/price histories, never benchmark-filled fund histories."""
from bisect import bisect_right
from datetime import date,timedelta
import math,statistics

def clean(points,asof):
    """Require unique increasing actual dates and positive finite observations."""
    out=[];seen=set()
    for d,v in sorted(points):
        d=date.fromordinal(d).isoformat() if isinstance(d,int) else d
        if d>asof:continue
        if d in seen or not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0:raise ValueError('Invalid price history')
        seen.add(d);out.append((d,float(v)))
    return out

def metrics(points,asof):
    p=clean(points,asof);out={'asOf':p[-1][0] if p else None,'observations':len(p),'from':p[0][0] if p else None,
        'returns':{str(y):None for y in (1,3,5,7)},'sinceInception':None,'volatility':None,'maximumDrawdown':None,'risk10':None}
    if len(p)<2:return out
    ds=[x[0] for x in p];end=date.fromisoformat(ds[-1]);last=p[-1][1]
    for y in (1,3,5,7):
        try:target=end.replace(year=end.year-y)
        except ValueError:target=end.replace(year=end.year-y,day=28)
        i=bisect_right(ds,target.isoformat())-1
        if i>=0 and 0<=(target-date.fromisoformat(ds[i])).days<=7:
            span=(end-date.fromisoformat(ds[i])).days/365.25
            out['returns'][str(y)]=round((last/p[i][1]-1)*100 if y==1 else ((last/p[i][1])**(1/span)-1)*100,4)
    years=(end-date.fromisoformat(ds[0])).days/365.25
    if years>0:out['sinceInception']=round(((last/p[0][1])**(1/years)-1)*100 if years>=1 else (last/p[0][1]-1)*100,4)
    out['sinceAnnualised']=years>=1
    returns=[b[1]/a[1]-1 for a,b in zip(p,p[1:]) if (date.fromisoformat(b[0])-date.fromisoformat(a[0])).days<=7]
    # A daily annualisation is valid only for sufficiently dense daily history.
    dense=len(p)>=.8*years*250 and len(returns)>=60
    vol=statistics.stdev(returns)*math.sqrt(252)*100 if dense else None
    peak=p[0][1];dd=0.
    for _,v in p:peak=max(peak,v);dd=min(dd,(v/peak-1)*100)
    out['volatility']=round(vol,4) if vol is not None else None;out['maximumDrawdown']=round(dd,4)
    if vol is not None:out['risk10']=round(10*(.6*min(vol/25,1)+.4*min(abs(dd)/40,1)),1)
    out['denseDaily']=dense
    return out

def current_mix(histories,weights,asof):
    """Hypothetical buy-and-hold of today's mix from common actual-history start.

    Returns are not weighted averages of CAGR values. Units are fixed at the
    common starting NAV, then the aggregate value is recomputed on each date.
    """
    active={k:w for k,w in weights.items() if w>0};total=sum(active.values())
    if total>100.0001:raise ValueError('Weights exceed100%')
    hs={k:clean(histories.get(k,[]),asof) for k in active}
    if not active or any(len(p)<2 for p in hs.values()):return metrics([],asof)
    start=max(p[0][0] for p in hs.values());end=min(p[-1][0] for p in hs.values())
    days=sorted({d for p in hs.values() for d,_ in p if start<=d<=end});maps={k:dict(p) for k,p in hs.items()}
    units={};last={};lastd={};values=[];cash=100-total
    for d in days:
        for k in active:
            if d in maps[k]:last[k]=maps[k][d];lastd[k]=d
        if len(last)<len(active):continue
        if any((date.fromisoformat(d)-date.fromisoformat(lastd[k])).days>5 for k in active):continue
        if not units:units={k:active[k]/last[k] for k in active}
        values.append((d,cash+sum(units[k]*last[k] for k in active)))
    out=metrics(values,asof);out['basis']='Hypothetical one-time buy-and-hold of the current mix; common observed history only; excludes investor taxes and entry/exit costs. Not John’s live SIP return.'
    return out
