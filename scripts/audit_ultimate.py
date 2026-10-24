"""Independent John ledger constraints and re-evaluation of archived evidence.

Does not import the transaction engine. Policy evaluators are pure shared
definitions; arithmetic, dates, cash and archive provenance are checked here.
"""
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
import calendar,hashlib,json,math
from ultimate_rules import checks as mf_checks
from ultimate_etf import candidate as etf_checks

def audit(A,store,view,cfg,open_day):
    evs=store.get('events',[]);orders={e['oid']:e for e in evs if e['k']=='order'}
    snaps=store.get('ultimateSnapshots',{});archives={e['ref']:e for e in evs if e['k']=='ultimate-snapshot'}
    for ref,record in snaps.items():
        s=record['snapshot'];body={k:v for k,v in s.items() if k not in ('snapshotHash','availableAt','availableOn')}
        h=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        A.check('ultimate',ref==h==s.get('snapshotHash'),'Snapshot hash mismatch')
        A.check('ultimate',ref in archives and archives[ref].get('firstSeenAt')==record.get('firstSeenAt'),'Snapshot receipt has no hash-chain anchor')
        A.check('ultimate',ref in archives and archives[ref].get('availableAt')==s.get('availableAt'),'Snapshot generation time differs from its hash-chain anchor')
        A.check('ultimate',s['budget']=={'mf':20000,'etf':20000,'costsIncluded':True},'Separate monthly budgets changed')
        for prod in ('mf','etf'):
            p=s[prod];selected=p['selected'];w=sum(c['weight'] for c in selected)
            A.check('ultimate',len(selected)<=5 and abs(w+p['cashWeight']-100)<.001 and p['cashWeight']>=0,'Invalid weights or fund count')
            for c in selected:
                x=c.get('evidence') or {}
                try:r=mf_checks(**x) if prod=='mf' else etf_checks(**x)
                except Exception as exc:
                    A.check('ultimate',False,'Cannot rebuild eligibility: '+str(exc));continue
                A.check('ultimate',r['eligible'] and r['checks']==c['checks'],c['key']+': selected gates fail independent recomputation')
    for acc in view['accounts']:
        if acc.get('strategy')!='ultimate':continue
        aid=acc['id'];prod=acc['product'];money=[e for e in evs if e['k']=='instalment' and e['acct']==aid]
        expected=[]
        for n in range(84):
            y=2026+(9+n)//12;m=(9+n)%12+1;last=calendar.monthrange(y,m)[1]
            ds=[date(y,m,d) for d in range(1,last+1) if open_day(date(y,m,d)) and date(y,m,d)>=date(2026,10,26)]
            f=next((d for d in ds if d.day<=7),None);l=next((d for d in ds if d.day>=max(22,last-6)),None)
            expected += [(d.isoformat(),10000 if f and l else 20000) for d in (f,l) if d and d.isoformat()<=view['today']]
        A.check('ultimate',sorted((e['T'],e['amount']) for e in money)==sorted(expected),aid+': funding schedule/cap/start differs')
        cash=0.;buykeys={};monthly={};seenfunds={}
        for e in evs:
            if e['k']=='instalment' and e['acct']==aid:cash+=e['amount']
            if e['k']=='order' and e['acct']==aid:
                T=date.fromisoformat(e['T']);month=e['T'][:7]
                A.check('ultimate',e['T']>='2026-10-26' and e['T']<=view['today'] and open_day(T),e['oid']+': order outside active trading dates')
                if e['side']=='buy':
                    key=str(e.get('code') or e.get('sym'));buykeys.setdefault(month,set()).add(key)
                    A.check('ultimate',len(buykeys[month])<=5,e['oid']+': more than five funds purchased this month')
                    ref=e.get('ref');record=snaps.get(ref) or {};s=record.get('snapshot') or {}
                    cutoff=datetime(T.year,T.month,T.day,14,45 if prod=='mf' else 50,tzinfo=ZoneInfo('Asia/Kolkata'))
                    try:times=[datetime.fromisoformat(x.replace('Z','+00:00')) for x in (s['availableAt'],record['firstSeenAt'])]
                    except Exception:times=[]
                    A.check('ultimate',len(times)==2 and all(t<=cutoff for t in times),e['oid']+': future or unavailable source evidence')
                    A.check('ultimate',bool(s) and 0<=(T-date.fromisoformat(s.get('asOf','1900-01-01'))).days<=5,e['oid']+': stale decision evidence')
                    proof=next((c for c in s.get(prod,{}).get('selected',[])+s.get('candidates',{}).get(prod,[]) if c['key']==key),None)
                    A.check('ultimate',bool(proof) and all(c['state']!='fail' for c in proof['checks']),e['oid']+': fund not eligible in decision snapshot')
                    if not e.get('fromOid'):
                        A.check('ultimate',T.day<=7 or T.day>=max(22,calendar.monthrange(T.year,T.month)[1]-6),e['oid']+': contribution buy outside permitted weeks')
                    else:
                        sale=orders.get(e['fromOid']) or {};d=next((x for x in evs if x['k']=='redeem' and x['oid']==e['fromOid']),{})
                        A.check('ultimate',bool(d) and d['payout']<=e['T'],e['oid']+': replacement before proceeds settle')
                        A.check('ultimate',sale.get('ultimateReplacement')==key,e['oid']+': replacement differs from reviewed target')
                else:
                    dec=e.get('decision') or {};mode=dec.get('mode')
                    A.check('ultimate',mode in ('rotation','gain','loss') and bool(e.get('ultimateReplacement')),e['oid']+': sale has no reviewed decision')
                    if mode in ('gain','loss'):
                        A.check('ultimate',T.month==3 and T.day>=10 and e.get('ultimateReplacement')==str(e.get('code') or e.get('sym')),e['oid']+': incorrect harvest timing or replacement')
                    A.check('ultimate',dec.get('estimatedRoundTripCost',-1)>=0 and (dec.get('savingCeiling',0)>dec.get('estimatedRoundTripCost',0) if mode in ('gain','loss') else True),e['oid']+': harvest benefit does not exceed costs')
            if e['k'] in ('allot','fill','redeem') and orders[e['oid']]['acct']==aid:
                o=orders[e['oid']]
                if e['k']=='redeem':
                    key=str(o.get('code') or o.get('sym'))
                    bought=[(orders[x['oid']],x) for x in evs if x['k'] in ('allot','fill') and orders[x['oid']]['acct']==aid and str(orders[x['oid']].get('code') or orders[x['oid']].get('sym'))==key and x['seq']<e['seq']]
                    A.check('ultimate',sum(x['units'] for _,x in bought if x['credit']<=o['T'])+1e-6>=e['units'],o['oid']+': insufficient settled units')
                    A.check('ultimate',not e['charges'].get('exitLoad'),o['oid']+': unapproved exit load')
                    if (o.get('decision') or {}).get('mode')=='gain':A.check('ultimate',all(g['term']=='LT' for g in e['gains']),o['oid']+': short-term gain harvest')
                    if (o.get('decision') or {}).get('mode')=='loss':A.check('ultimate',sum(g['gain'] for g in e['gains'])<0,o['oid']+': loss harvest has no loss')
                cash += e['net'] if e['k']=='redeem' else -(e['amount'] if e['k']=='allot' else e['gross']+e['charges']['total'])
                A.check('ultimate',cash>=-.011,e['oid']+': negative cash after costs')
        A.check('ultimate',abs(cash-(acc.get('cash') or 0))<.011,aid+': cash ledger differs from statement')
        A.check('ultimate',acc.get('start')=='2026-10-26' and acc.get('horizon')=='h7',aid+': profile horizon/start wrong')
        A.check('ultimate',acc['taxHarvest']['profile'].get('otherIncome')==0 and acc['taxHarvest']['profile'].get('regime')=='new',aid+': incorrect income/tax profile')
