"""Historical current-mix scenarios, not a point-in-time strategy backtest.

Historical fund-selection disclosures and EPS snapshots do not exist for every
past decision. Explicitly avoid applying today's 50 gates to yesterday's buys.
"""
from datetime import date
from bisect import bisect_right
from ultimate_history import clean

def scenarios(histories,weights,asof,product):
    hs={k:clean(histories.get(k,[]),asof) for k,w in weights.items() if w>0}
    note='Historical illustration of today’s selected funds, with hindsight selection and survivorship bias. Not a backtest of the 50-check adaptive strategy. Historical portfolio/EPS snapshots are unavailable; no claim that the 16% target was achieved by this strategy.'
    out={'basis':note,'pointInTimeStrategyValidated':False,'monthlyContribution':20000,'cases':[]}
    if not hs or any(len(x)<2 for x in hs.values()):out['unavailable']='Complete daily histories unavailable';return out
    maps={k:dict(p) for k,p in hs.items()};days=sorted(set.intersection(*[set(m) for m in maps.values()]))
    if not days:return out
    for years in (1,3,5,7):
        end=days[-1];e=date.fromisoformat(end)
        try:start=e.replace(year=e.year-years).isoformat()
        except ValueError:start=e.replace(year=e.year-years,day=28).isoformat()
        if days[0]>start:continue
        period=[d for d in days if start<=d<=end]
        units={k:0. for k in hs};cash=0.;paid=0.;flows=[];lastmonth=None;values=[];peak=0.;dd=0.
        for d in period:
            month=d[:7]
            if month!=lastmonth and len(flows)<years*12:
                lastmonth=month;paid+=20000;cash+=20000;flows.append((date.fromisoformat(d),-20000))
                for k,w in weights.items():
                    if k not in units:continue
                    budget=20000*w/100;px=maps[k][d]
                    if product=='mf':u=int(round(budget-budget*.00005,2)/px*1000)/1000;cost=budget
                    else:
                        from sim_engine import etf_units_for
                        u,ch=etf_units_for(budget,px,'resident',True);cost=u*px+ch['total']
                    units[k]+=u;cash-=cost
            val=cash+sum(units[k]*maps[k][d] for k in units)
            # Flow-adjusted unitisation measures drawdown without treating
            # monthly contributions as investment gains.
            if values:
                added=20000 if d==flows[-1][0].isoformat() else 0
                index=values[-1][2]*(val-added)/values[-1][1] if values[-1][1] else 100
            else:index=100
            peak=max(peak,index);dd=min(dd,(index/peak-1)*100);values.append((d,val,index))
        from sim_engine import xirr
        terminal=values[-1][1];ret=xirr(flows+[(date.fromisoformat(end),terminal)])
        out['cases'].append({'years':years,'from':period[0],'to':end,'contributed':paid,'terminalValue':round(terminal,2),
                             'xirr':round(ret*100,3) if ret is not None else None,'maximumDrawdown':round(dd,3),
                             'costs':'MF stamp duty or model ETF entry charges included. No sales, exit costs or investor taxes. ETF adjusted prices include distributions and approximate whole-unit history.'})
    return out
