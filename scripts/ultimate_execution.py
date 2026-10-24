"""John's prospective execution. Cash and source availability are ledger facts.

Monthly contributions are fixed; purchases can be deferred when a data feed or
eligibility check fails. A missed run never creates an order using future data.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import calendar, copy, hashlib, json
from pathlib import Path
from ultimate_rules import windows, START, VERSION, age

ROOT=Path(__file__).resolve().parents[1]
IST=ZoneInfo('Asia/Kolkata')

def digest(s):
    return hashlib.sha256(json.dumps({k:v for k,v in s.items() if k not in ('snapshotHash','availableAt','availableOn')},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def eligible(c):
    checks=c.get('checks') or []
    return len(checks) in (50,51) and len({x['id'] for x in checks})==len(checks) and all(x['state'] in ('pass','na') for x in checks)

def available(s,T,product):
    try:
        at=datetime.fromisoformat(s['availableAt'].replace('Z','+00:00')).astimezone(IST)
        cutoff=datetime(T.year,T.month,T.day,14,45 if product=='mf' else 50,tzinfo=IST)
        evidence_dates=[c.get('evidence',{}).get('context',{}).get('asOf',s['asOf']) for c in s[product]['selected']]
        return s['snapshotHash']==digest(s) and s['policyVersion']==VERSION and at<=cutoff and 0<=age(T.isoformat(),s['asOf'])<=5 and all(0<=age(T.isoformat(),d)<=5 for d in evidence_dates)
    except (KeyError,ValueError,TypeError):return False

def schedule(until,is_open):
    out=[]
    for n in range(84):
        y=2026+(9+n)//12;m=(9+n)%12+1
        out.extend((d,a) for d,a in windows(y,m,is_open) if d<=until)
    return out

def in_window(T):
    n=calendar.monthrange(T.year,T.month)[1]
    return T.day<=7 or T.day>=max(22,n-6)

def register(eng):
    from sim_engine import append
    path=ROOT/'data/ultimate_folio.json'
    if not path.exists():return
    s=json.loads(path.read_text(encoding='utf8'))
    if digest(s)!=s.get('snapshotHash'):raise ValueError('Ultimate snapshot hash mismatch')
    snapshots=eng.store.setdefault('ultimateSnapshots',{})
    ref=s['snapshotHash']
    if ref not in snapshots:
        at=datetime.now(timezone.utc).isoformat()
        snapshots[ref]={'snapshot':s,'firstSeenAt':at}
        append(eng.store,'ultimate-snapshot',ref=ref,availableAt=s['availableAt'],firstSeenAt=at)

def latest(eng,product,T):
    candidates=[]
    for ref,v in eng.store.get('ultimateSnapshots',{}).items():
        s=v['snapshot']
        # Archive receipt must precede the order cutoff as well as generation.
        seen=dict(s,availableAt=max(s['availableAt'],v['firstSeenAt']))
        if available(seen,T,product):candidates.append((s['asOf'],v['firstSeenAt'],ref,s))
    return max(candidates,key=lambda x:x[:2])[2:] if candidates else (None,None)

def free_cash(state,T):
    cash=state.get('cash',0)
    by={o['oid']:o for o in state['orders']}
    cash-=sum((o.get('amount') if o.get('amount') is not None else (by.get(o.get('fromOid'),{}).get('done') or {}).get('net',0))
              for o in state['orders'] if o['side']=='buy' and 'done' not in o)
    cash-=sum(x['net'] for x in state['sells'] if x['payout']>T.isoformat() and not x.get('withdraw'))
    return round(max(0,cash),2)

def run(eng):
    from sim_engine import append,replay,is_trading,r2
    register(eng)
    for a in eng.accts:
        if a.get('strategy')!='ultimate':continue
        aid=a['id'];prod=a['product'];T=eng.today;ds=T.isoformat();month=ds[:7]
        # Contributions catch up as CASH, never as retrospective fund orders.
        have={e['T'] for e in eng.store['events'] if e['k']=='instalment' and e['acct']==aid}
        for d,amount in schedule(T,is_trading):
            if d.isoformat() not in have:
                append(eng.store,'instalment',acct=aid,iid=f'{aid}|{d}',T=d.isoformat(),nominal=d.isoformat(),amount=amount,ref='ultimate-cash',cashAccount=True,strategy='ultimate')
        if ds<START or not is_trading(T) or not in_window(T):continue
        if (T.year-2026)*12+T.month-10>=84:continue
        ref,current=latest(eng,prod,T)
        if not current:continue
        state=replay(eng.store['events']).get(aid)
        if not state:continue
        commitments=eng.store.setdefault('ultimateMonths',{})
        mid=aid+'|'+month
        if mid not in commitments:
            prior=max(0,free_cash(state,T)-sum(i['amount'] for i in state['inst'] if i['T'][:7]==month))
            prior_reserve=sum(i['amount'] for i in state['inst'] if i['T'][:7]<month)*current[prod]['cashWeight']/100
            # Carry cash released from a former defensive allocation into the
            # next eligible monthly targets without counting it as new funding.
            extra=max(0,prior-prior_reserve)
            commitments[mid]={'ref':ref,'reinvestCash':r2(extra)}
            append(eng.store,'ultimate-month',acct=aid,month=month,ref=ref,T=ds,reinvestCash=r2(extra))
        frozen=eng.store['ultimateSnapshots'][commitments[mid]['ref']]['snapshot'][prod]
        current_by={c['key']:c for c in current[prod]['selected']}
        # Also allow a frozen fund still eligible in the current candidate set.
        current_by.update({c['key']:c for c in current.get('candidates',{}).get(prod,[])})
        buys=[o for o in state['orders'] if o['side']=='buy' and o['T'][:7]==month]
        keys={str(o.get('code') or o.get('sym')) for o in buys}
        funded=sum(i['amount'] for i in state['inst'] if i['T'][:7]==month)
        # Deliberate cash weight is maintained against total contributions.
        reserve=sum(i['amount'] for i in state['inst'])*frozen['cashWeight']/100
        cash=min(free_cash(state,T),max(0,state['cash']-reserve))
        for c in sorted(frozen['selected'],key=lambda c:(-c['weight'],c['key'])):
            key=c['key'];proof=current_by.get(key)
            if not proof or not eligible(proof) or (key not in keys and len(keys)>=5):continue
            spent=sum(o.get('amount') or 0 for o in buys if str(o.get('code') or o.get('sym'))==key)
            invested_weight=100-frozen['cashWeight']
            target=r2(20000*c['weight']/100+(commitments[mid]['reinvestCash']*c['weight']/invested_weight if invested_weight else 0))
            remaining=r2(target-spent)
            # Whole monthly fund targets avoid splitting a ₹5k minimum into
            # invalid ₹2.5k first/last-week subscriptions.
            if remaining<=0 or remaining>cash+.001:continue
            if prod=='mf':
                f=eng.mkt.funds.get(int(key)) or {}
                if 'L' not in (f.get('buy') or '') or remaining<(f.get('lumpMin') or float('inf')):continue
                eng.mkt.remember(int(key))
            oid=f'{aid}|ultimate|{month}|{key}|{ds}'
            if any(o['oid']==oid for o in state['orders']):continue
            append(eng.store,'order',acct=aid,oid=oid,iid=aid+'|ultimate|'+month,T=ds,side='buy',
                   **({'code':int(key)} if prod=='mf' else {'sym':key}),name=c['name'],slot='ultimate:'+key,label=c['category'],
                   weight=c['weight'],amount=remaining,ref=ref,monthlyRef=commitments[mid]['ref'],cashAccount=True,strategy='ultimate',
                   note='50 applicable eligibility gates; monthly fund target; fees included; missing sleeves retained as cash')
            cash=r2(cash-remaining);keys.add(key)

def public(eng,a):
    ref,s=latest(eng,a['product'],eng.today)
    # Before the start, display the latest proposal without suggesting a trade.
    if not s:
        records=list(eng.store.get('ultimateSnapshots',{}).values())
        if records:s=max(records,key=lambda x:x['firstSeenAt'])['snapshot'];ref=s['snapshotHash']
    if not s:return {'status':'Waiting for verified strategy inputs','start':START}
    return {'start':START,'policyVersion':VERSION,'snapshotHash':ref,'asOf':s['asOf'],'availableAt':s['availableAt'],
            'goalYears':7,'targetAnnualReturn':16,'targetNote':s['targetNote'],'budget':20000,'costsIncluded':True,
            'rules':s['rules'],'plan':s[a['product']],'coverage':s['coverage'],'historicalWarning':s.get('historicalWarning'),
            'backtest':s.get('backtest',{}).get(a['product']),
            'status':'Scheduled; no purchases before 26 October 2026' if eng.today.isoformat()<START else 'Active; buys require current eligible evidence'}
