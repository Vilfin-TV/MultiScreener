"""Prospective FIFO rotation and profile-aware harvest, with cash settlement.

P/E alone is not a sell signal. A rotation requires deteriorating earnings or
excess valuation, a verified cheaper replacement, meaningful ranking improvement
and estimated immediate tax plus costs below 1% of the position's value.
"""
from datetime import date
import math
from ultimate_execution import latest,eligible,free_cash
from sim_tax import annual_gains,profile,liability,gain_room,bucket

def run(eng):
    from sim_engine import replay,append,is_trading,tax_class,term_for,load_pct,etf_charges,r2
    T=eng.today;ds=T.isoformat()
    if ds<'2026-10-26' or not is_trading(T):return
    person=next((p for p in eng.CFG['persons'] if p.get('strategy')=='ultimate'),None)
    if not person:return
    taxprofile=profile(person,eng.CFG)
    for a in eng.accts:
        if a.get('strategy')!='ultimate':continue
        aid=a['id'];prod=a['product'];ref,snap=latest(eng,prod,T)
        if not snap:continue
        state=replay(eng.store['events']).get(aid)
        if not state:continue
        pool=snap[prod]['selected']+snap['candidates'][prod];by={c['key']:c for c in pool};valid={k:c for k,c in by.items() if eligible(c)}
        # Complete a previous rotation only once the actual sale has settled,
        # with fresh eligibility evidence for the replacement on today's date.
        for o in state['orders']:
            target=o.get('ultimateReplacement')
            if not target or 'done' not in o or o['done']['payout']>ds:continue
            oid=o['oid']+'|in'
            if any(x['oid']==oid for x in state['orders']):continue
            if target not in valid:continue
            amount=o['done']['net'];c=valid[target]
            keys={str(x.get('code') or x.get('sym')) for x in state['orders'] if x['side']=='buy' and x['T'][:7]==ds[:7]}
            if (target not in keys and len(keys)>=5) or amount>free_cash(state,T)+.001:continue
            if prod=='mf' and amount<(eng.mkt.funds.get(int(target),{}).get('lumpMin') or float('inf')):continue
            append(eng.store,'order',acct=aid,oid=oid,iid=o['iid'],T=ds,side='buy',amount=None,fromOid=o['oid'],
                   **({'code':int(target)} if prod=='mf' else {'sym':target}),name=c['name'],slot='ultimate:'+target,
                   ref=ref,strategy='ultimate',cashAccount=True,level=o.get('level'),note='Revalidated replacement after settlement; all applicable gates pass')
        for key,lots in sorted(state['lots'].items()):
            if not lots or any(o['side']=='sell' and str(o.get('code') or o.get('sym'))==key and 'done' not in o for o in state['orders']):continue
            old=by.get(key);f=eng.mkt.fund(int(key)) if prod=='mf' else None
            if prod=='mf' and not f:continue
            rule=eng.mkt.exit_rule(int(key)) if f else {'known':True,'tiers':[]}
            if not rule.get('known'):continue
            tc=tax_class(f,None if f else key,eng.mkt)
            pd,px=eng.mkt.mf_latest(int(key),T) if prod=='mf' else eng.mkt.etf_latest(key,T)
            if not px or not pd or (T-pd).days>5:continue
            usable=[]
            for l in sorted(lots,key=lambda l:(l['date'],l['oid'])):
                held=(T-date.fromisoformat(l['date'])).days
                if l['credit']>ds or held<365*(f or {}).get('lock',0) or load_pct(rule,held)>0:break
                usable.append(l)
            if not usable:continue
            total_units=sum(l['units'] for l in usable);gross=total_units*px
            realised=annual_gains(eng.store,a['name'],ds)[0]
            before=liability(realised,taxprofile)['tax']
            if before is None:continue
            trial=dict(realised);gain=0
            for l in usable:
                g=l['units']*px-l['cost'];gain+=g
                term=term_for(tc,(T-date.fromisoformat(l['date'])).days)
                trial[bucket({'class':tc,'term':term})]+=g
            after=liability(trial,taxprofile)['tax']
            if after is None:continue
            costs=(gross*(eng.CFG['mfRules']['stampDuty']+eng.CFG['mfRules']['sttRedeemEquity']) if prod=='mf' else
                   etf_charges(gross,'sell','resident',tc=='equity')['total']+etf_charges(gross,'buy','resident',tc=='equity')['total'])
            replacement=None;reason=None;mode=None;units=total_units;saving=0
            if old:
                e=old.get('earnings') or {};fail={c['id'] for c in old['checks'] if c['state']=='fail'}
                danger=(e.get('earningsGrowth') is not None and e['earningsGrowth']<=0) or bool(fail & {'relative-value','pe'})
                alt=next((c for c in valid.values() if c['key']!=key and c['category']==old['category'] and c.get('score',0)>=old.get('score',0)+10
                          and (c.get('earnings',{}).get('pe') or 999)<(e.get('pe') or 0)*.8),None)
                if danger and alt and costs+max(0,after-before)<gross*.01:
                    replacement=alt['key'];reason='Verified cheaper same-category alternative, score improvement ≥10; tax and round-trip costs below1%';mode='rotation'
            # Harvests require a genuine loss tax saving, or long-term gains
            # within the shared profile allowance. They are evaluated in March.
            if not replacement and T.month==3 and T.day>=10 and key in valid and tc=='equity':
                rid=aid+'|ultimate-harvest|'+str(T.year)
                if any(e['k']=='harvest' and e.get('rid')==rid for e in eng.store['events']):continue
                all_lt=all(term_for(tc,(T-date.fromisoformat(l['date'])).days)=='LT' for l in usable)
                room=gain_room(realised,taxprofile) or 0
                # Avoid shared-room overbooking while an earlier sale awaits NAV.
                if any(o.get('level')=='harvest' and 'done' not in o for st in replay(eng.store['events']).values() for o in st['orders'] if o.get('acct','').startswith('John-')):continue
                saving=before-after if gain<0 else gain*taxprofile['ltcgRate']*(1+taxprofile['cess']) if all_lt and gain<=room and after<=before+.01 else 0
                if abs(gain)>=eng.CFG['taxHarvest']['minGain'] and saving>costs:
                    replacement=key;mode='loss' if gain<0 else 'gain';reason='Profile-aware FIFO harvest; future gain-saving ceiling is conditional, not a refund'
            if not replacement:continue
            iid=aid+'|ultimate-review|'+ds+'|'+key
            if any(o['oid']==iid+'|out' for o in state['orders']):continue
            append(eng.store,'order',acct=aid,oid=iid+'|out',iid=iid,T=ds,side='sell',units=round(units,6),
                   **({'code':int(key)} if prod=='mf' else {'sym':key}),strategy='ultimate',cashAccount=True,ref=ref,
                   ultimateReplacement=replacement,reason=reason,level='review' if mode=='rotation' else 'harvest',
                   decision={'mode':mode,'estimatedGain':r2(gain),'estimatedTaxIncrease':r2(after-before),'estimatedRoundTripCost':r2(costs),'savingCeiling':r2(saving)})
            item={'key':key,'units':units,'gain':r2(gain),'cost':r2(costs),'saving':r2(saving),'action':'harvest' if mode!='rotation' else 'sell','mode':mode,'note':reason}
            if mode!='rotation':append(eng.store,'harvest',rid=rid,acct=aid,T=ds,items=[item],exemptLeft=room)
            else:append(eng.store,'review',rid=iid,acct=aid,T=ds,items=[item])
            # Price current sale before evaluating another account's shared tax.
            eng.settle()
