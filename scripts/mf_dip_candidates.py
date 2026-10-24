"""Optional MF dip candidates, separate from regular allocations and the agents' reserve ledger.

Exact benchmark cohorts only. The same 8 + 14 + 15 checks apply. A displayed
candidate is not a buy: missing inputs and unsuitable horizons fail closed.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date

import dip_rules as d
from sim_engine import exit_rule

INDEXES = {
    'next50': dict(label='Nifty Next 50', index='Nifty Next 50', ident='niftynext50', val='nn50', trk='JUNIORBEES', trk2='NEXT50IETF'),
    'value': dict(label='Value satellite', index='Nifty50 Value 20', ident='nifty50value20', val='value20', trk='NV20BEES', trk2='NV20IETF'),
    'quality': dict(label='Quality satellite', index='Nifty200 Quality 30', ident='nifty200quality30', val='quality30', trk='QUAL30IETF', trk2='NIFTYQLITY'),
    'momentum': dict(label='Momentum satellite', index='Nifty200 Momentum 30', ident='nifty200momentum30', val='momentum30', trk='MOM30IETF', trk2='MOMENTUM'),
    'lowvol': dict(label='Low-volatility satellite', index='Nifty100 Low Volatility 30', ident='nifty100lowvolatility30', val='lowvol30', trk='LOWVOLIETF', trk2='LOWVOL1'),
}
BROAD = {
    'large': dict(label='Best overall · P/E & EPS', index='Nifty 50', ident='nifty50', val='n50', trk='NIFTYBEES', trk2='SETFNIF50'),
    'next50': INDEXES['next50'],
    'mid': dict(label='Best overall · P/E & EPS', index='Nifty Midcap 150', ident='niftymidcap150', val='mid150', trk='MIDCAPETF', trk2='MIDCAPIETF'),
    'small': dict(label='Best overall · P/E & EPS', index='Nifty Smallcap 250', ident='niftysmallcap250', val='sml250', trk='HDFCSML250', trk2='MOSMALL250'),
}


def index_id(name):
    m = re.search(r'\bnifty\s*(.*?)(?=\s+(?:index|etf|fund|fof)\b|$)', name or '', re.I)
    return re.sub(r'[^a-z0-9]', '', m.group(0).lower()) if m else ''


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def state(cfg, asof):
    closes = [x for x in d.load_closes(cfg['trk']) if x[0] <= asof]
    second = {dt:c for dt,c in d.load_closes(cfg['trk2']) if dt <= asof}
    walked = d.walk(closes, second)
    if walked:
        st = walked[-1]
        st['epBeforeStart'] = bool(st['ep'] and (st['epDate'] or '') < d.SIM_START)
        st.update(d.trend(closes))
        st['checks'] = d.trigger_checks(st, asof)
        st['checks'][1][1] = 0 <= (date.fromisoformat(asof)-date.fromisoformat(st['d'])).days <= 5
        # Never offer a pre-launch signal as today's new action.
        st['checks'][7][1] = st['checks'][7][1] and st['d'] >= d.SIM_START
    else:
        st = dict(d='', fall=0, raw=0, tier=0, amount=0, ep=0, signal=False, conf=False, sane=False)
        st['checks'] = [[label,False,'Insufficient official tracker history; no signal.'] for label in
                        ['Fall from 3-month high','Official close up to date','Fall held for two closes',
                         'Second tracker confirmation','Not a crash-day print','Fall in range','Dip level and amount','New level in this fall']]
    return {**st,'label':cfg['label'],'index':cfg['index'],'trk':cfg['trk'],'trk2':cfg['trk2'],'extra':True}


def portfolio_metric(f, fpe, asof, macro, cfg):
    p = (fpe.get('funds') or {}).get(str(f['code'])) or []
    pe, cover, month = (p + [None,None,None])[:3]
    try:
        stock_age = (date.fromisoformat(asof)-date.fromisoformat(fpe['asOf'])).days
        portfolio_age = (date.fromisoformat(asof)-date.fromisoformat(month+'-01')).days
        fresh = 0 <= stock_age <= 5 and 0 <= portfolio_age <= 93
    except (ValueError,TypeError,KeyError):
        fresh = False
    eps = ((macro.get('growth') or {}).get('earnings') or {}).get(cfg['val']) or {}
    valid = fresh and number(pe) and pe > 0 and number(cover) and cover >= 75 and number(eps.get('g1'))
    return dict(pe=pe,coverPct=cover,portfolioAsOf=month,priceAsOf=fpe.get('asOf'),
                epsGrowth=eps.get('g1'),epsIndex=cfg['index'],valid=bool(valid))


def selection_checks(f, peers, cfg, detail, metric, best=False):
    """Subchecks behind check 24, published separately for inspection."""
    r = [p['r3y'] for p in peers if p['code'] != f['code'] and number(p.get('r3y'))]
    tracking = number(f.get('r3y')) and bool(r) and abs(f['r3y']-d._med(r)) <= .6
    checks = [
        ['Exact index mandate',index_id(f.get('name')) == cfg['ident'],cfg['index']+'; mixed-factor and different-index funds excluded'],
        ['Comparable tracking record',tracking,'3Y return within 0.6 percentage points of same-index peers' if r else 'No comparable 3Y same-index peer record'],
        ['Known exit-load terms',bool(detail.get('known')),'Published scheme terms parsed' if detail.get('known') else 'Missing or unparsed scheme terms'],
    ]
    if best:
        checks += [
            ['Current portfolio P/E with adequate coverage',metric['valid'],f"P/E {metric['pe']}; {metric['coverPct']}% of disclosed equity covered; portfolio {metric['portfolioAsOf']}; stock prices {metric['priceAsOf']}"],
            ['Positive benchmark EPS growth',number(metric['epsGrowth']) and metric['epsGrowth']>0,f"{cfg['index']} implied index EPS growth {metric['epsGrowth']}% over 12 months; not fund NAV growth or fund-level EPS"],
        ]
    return checks


def build(plans, rows, macro, fpe, details, asof):
    """Same shape as the main dip block, isolated so optional rows cannot change agent orders."""
    out = dict(asOf=asof,segments={},cands=[],plans={pid:{} for pid in plans},alts={})
    states, seen = {}, {}
    def get_state(cfg):
        key = cfg['ident']
        if key not in states:
            states[key] = state(cfg,asof)
        return states[key]
    pools = {cfg['ident']:[f for f in rows if f.get('sub','').startswith('idx_') or f.get('sub')=='eqfof'
                          if index_id(f.get('name')) == cfg['ident']]
             for cfg in [*INDEXES.values(),*BROAD.values()]}
    for seg in [*INDEXES,'best']:
        configs = list(BROAD.values()) if seg=='best' else [INDEXES[seg]]
        candidates=[]
        for cfg0 in configs:
            cfg={**cfg0,'label':'Best overall · P/E & EPS' if seg=='best' else cfg0['label'],'eyGapMin':-5.5}
            st=get_state(cfg)
            peers=pools[cfg['ident']]
            for f in peers:
                if seg == 'best' and f['code'] in ({s['code'] for p in plans.values() for s in p['slots']} | {c['code'] for c in out['cands']}):
                    continue
                det=details(f['code'])
                er=exit_rule((det.get('info') or {}).get('exitLoad'),f.get('exitNil'))
                metric=portfolio_metric(f,fpe,asof,macro,cfg)
                sc=selection_checks(f,peers,cfg,er,metric,seg=='best')
                slot=dict(label=cfg['label'],checks=sc)
                fundchecks=d.mf_fund_checks(slot,f,peers,er,st['amount'],asof)
                fundchecks[0]=['Suitable optional sleeve',True,'Horizon/risk eligibility is applied separately for the selected plan.']
                fundchecks[1]=['Passes candidate selection checks',all(x[1] for x in sc),f'{sum(x[1] for x in sc)} of {len(sc)} selection checks; expand the candidate notes.']
                v=(macro.get('valuation') or {}).get(cfg['val']) or {}
                v_age=(date.fromisoformat(asof)-date.fromisoformat(macro['valuationAsOf'])).days if macro.get('valuationAsOf') else 999
                extra=('Current same-index valuation and earnings',0<=v_age<=5 and bool(v),f"{cfg['index']} valuation date {macro.get('valuationAsOf')}; no proxy index substituted")
                market=d.valuation_checks(seg,macro,None,None,extra,st,config=cfg)
                # Disclose the actual history length of younger factor indices.
                for check in market:
                    check[0]=check[0].replace('10-year median','available-history median (up to 10 years)')
                    check[2]=check[2].replace('of 10 years',f"of {v.get('years', 'unknown')} available years (up to 10)")
                full=market+fundchecks
                # Prefer fully eligible market/fund candidates. Display the closest
                # candidate with failures when no eligible fund exists.
                fit=all(c[1] for c in full[:-1])
                candidates.append(dict(seg=seg,slot=seg,code=f['code'],name=f['name'],checks=full,
                    purchase=d.mf_purchase(f),selection=sc,metrics=metric,scope='extra',fit=fit,
                    cfg=cfg,peerCount=len(peers),fundPassed=sum(c[1] for c in fundchecks[:-1])))
        # "Best overall" ranks low portfolio P/E and high benchmark EPS growth equally.
        ranked_metrics=[c for c in candidates if c['metrics']['valid'] and (c['metrics']['epsGrowth'] or 0)>0]
        for c in candidates:
            m=c['metrics']; score=0.
            if seg=='best' and m['valid'] and (m['epsGrowth'] or 0)>0:
                n=len(ranked_metrics)
                score=50*sum(x['metrics']['pe']>=m['pe'] for x in ranked_metrics)/n+50*sum(x['metrics']['epsGrowth']<=m['epsGrowth'] for x in ranked_metrics)/n
            c['rankScore']=round(score,2)
        def rank(c):
            f=next(f for f in rows if f['code']==c['code'])
            return (not c['fit'], not c['purchase']['lump'], (f.get('aum') or 0)<500, f.get('r3y') is None,
                    -(c['rankScore'] if seg=='best' else c['fundPassed']),
                    -c['fundPassed'],f['ter'] if number(f.get('ter')) else 999,-(f.get('aum') or 0),c['code'])
        candidates.sort(key=rank)
        if not candidates:
            cfg={**configs[0],'label':'Best overall · P/E & EPS' if seg=='best' else configs[0]['label']}
            out['segments'][seg]=get_state(cfg)
            continue
        selected=candidates[0]; cfg=selected['cfg']; st={**get_state(cfg),'label':cfg['label']}
        out['segments'][seg]=st
        for pid,p in plans.items():
            c={k:v for k,v in selected.items() if k not in ('cfg','fit','fundPassed')}
            c['checks']=[list(x) for x in c['checks']]
            years=p.get('years') or 0; risk=p.get('risk')
            suitable=(years>=5 and risk in ('Balanced','Aggressive','Very aggressive')) if seg=='next50' else (years>=7 and risk in ('Aggressive','Very aggressive'))
            c['checks'][d.N_MKT]=['Suitable optional sleeve',suitable,
                ('5+ years; balanced/aggressive/very aggressive' if seg=='next50' else '7+ years; aggressive/very aggressive')+f"; selected plan: {years} years, {risk}"]
            c['fundOk']=all(x[1] for x in c['checks'][:-1])
            ci=d._add(out['cands'],seen,c)
            out['plans'][pid][seg]=d._plan_entry(out['segments'],seg,ci,c)
    return out
