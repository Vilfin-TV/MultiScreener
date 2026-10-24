#!/usr/bin/env python3
"""Prepare a narrowly authorised historical simulation restatement.

The original private ledger is never overwritten by this program. It writes a
candidate, private per-order report and derived view; the workflow backs up the
original and publishes only after the independent audit passes.
"""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sim_engine as sim

MANIFEST = Path(__file__).with_name('sim_gold_correction.json')


def digest(value):
    if isinstance(value,dict) and 'publishedAnchor' in value and 'orders' in value:
        value={k:v for k,v in value.items() if k!='apply'}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def verify_chain(events):
    prev='genesis'
    for i,e in enumerate(events):
        if e['seq']!=i+1 or e['prev']!=prev or sim.ev_hash(e)!=e['h']:
            raise ValueError('Original ledger hash chain does not verify')
        prev=e['h']


def rehash(events):
    prev='genesis'
    for i,e in enumerate(events):
        e.update(seq=i+1,prev=prev)
        e['h']=sim.ev_hash(e); prev=e['h']


def apply_orders(original,manifest,funds,navs,original_file_sha=None):
    """Pure, fail-closed mutation of a copy. NAVs must be independently AMFI-verified."""
    verify_chain(original.get('events',[]))
    existing=[e for e in original['events'] if e.get('k')=='restatement' and e.get('correctionId')==manifest['id']]
    if existing:
        if existing[0].get('manifestSha256')!=digest(manifest):
            raise ValueError('Applied correction manifest changed')
        return copy.deepcopy(original),None
    anchor=manifest['publishedAnchor']; n=anchor['events']
    if len(original['events'])<n or original['events'][n-1]['h']!=anchor['head']:
        raise ValueError('Ledger does not contain the specifically authorised published anchor')
    source_orders={e['oid']:e for e in original['events'] if e['k']=='order'}
    restricted={o['oid'] for o in source_orders.values() if o.get('side')=='buy' and str(o.get('code'))=='118663' and o['T']>='2026-10-16'}
    expected={x['oid'] for x in manifest['orders']}
    if len(expected)!=manifest['expectedCount'] or restricted!=expected:
        raise ValueError('Restricted orders differ from the 15 authorised orders; refusing a partial correction')
    completed={e['oid']:e for e in original['events'] if e['k']=='allot'}
    store=copy.deepcopy(original)
    orders={e['oid']:e for e in store['events'] if e['k']=='order'}
    allots={e['oid']:e for e in store['events'] if e['k']=='allot'}
    changes=[]
    for rule in manifest['orders']:
        old=source_orders[rule['oid']]; done=completed.get(rule['oid'])
        if old['acct']!=rule['acct'] or old['T']!=rule['date'] or old['amount']!=rule['amount'] or old.get('slot')!='metal' or not done:
            raise ValueError('Order amount/date/account/slot/allotment does not match approval: '+rule['oid'])
        if any(o.get('acct')==old['acct'] and str(o.get('code'))=='118663' and o.get('side')=='sell' for o in source_orders.values()):
            raise ValueError('Affected units have a sell order; a dependent-lot correction is required')
        code=rule['to']; f=funds.get(code) or {}
        if code not in (151745,152056) or f.get('sub')!='multiasset' or 'L' not in (f.get('buy') or ''):
            raise ValueError('Replacement is not a currently eligible multi-asset fund')
        if not isinstance(f.get('lumpMin'),(int,float)) or not 0<f['lumpMin']<=old['amount']:
            raise ValueError('Replacement minimum exceeds the unchanged contribution')
        if not f.get('inc') or f['inc']>old['T']:
            raise ValueError('Replacement did not exist on the original order date')
        nav=navs.get(old['T'],{}).get(str(code))
        if not isinstance(nav,(int,float)) or nav<=0:
            raise ValueError('Official AMFI NAV missing on the original trade date')
        o=orders[rule['oid']]; a=allots[rule['oid']]
        o.update(code=code,name=f['name'],label='Multi-asset replacement for paused gold',asset='Hybrid',
            correctionId=manifest['id'],replacesCode=118663,
            note='Historical simulation restatement authorised by the owner: fresh Nippon Gold purchases were suspended. Same contribution and trade date; eligible multi-asset substitute, not a gold-equivalent holding.')
        stamp=sim.r2(o['amount']*sim.CFG['mfRules']['stampDuty']); net=sim.r2(o['amount']-stamp)
        a.update(navDate=o['T'],nav=nav,stamp=stamp,net=net,units=sim.trunc(net/nav,sim.CFG['mfRules']['unitDecimals']),
            credit=sim.add_business(sim.D(o['T']),sim.CFG['mfRules']['creditBusinessDays']).isoformat(),verified=True,correctionId=manifest['id'])
        store.setdefault('funds',{})[str(code)]={k:f.get(k) for k in ('code','name','sub','tax','exitNil','lock','amc')}
        changes.append(dict(oid=o['oid'],acct=o['acct'],date=o['T'],amount=o['amount'],fromCode=118663,toCode=code,
            originalOrderHash=old['h'],originalAllotmentHash=done['h'],originalNav=done['nav'],originalUnits=done['units'],nav=nav,units=a['units']))
    if sim.r2(sum(x['amount'] for x in changes))!=manifest['expectedTotal']:
        raise ValueError('Corrected total differs from the approved total')
    # No deposits, withdrawals, dip decisions, ETF orders, snapshots or other
    # trade bodies may change. Hash links are rebuilt explicitly afterwards.
    targets=expected
    for old,new in zip(original['events'],store['events']):
        if old.get('oid') not in targets and old!=new:
            raise ValueError('An unrelated historical event changed')
    rehash(store['events'])
    record=dict(correctionId=manifest['id'],manifestSha256=digest(manifest),reason=manifest['reason'],
        originalFileSha256=original_file_sha,
        publishedAnchor={k:anchor[k] for k in ('events','head')},
        originalEvents=len(original['events']),originalHead=original['events'][-1]['h'],
        correctedAnchorHead=store['events'][n-1]['h'],correctedPrefixHead=store['events'][-1]['h'],
        count=len(changes),totalAmount=manifest['expectedTotal'],orders=changes)
    sim.append(store,'restatement',**record)
    return store,record


def rebuild_derived(store,eng,affected):
    # Retain every unaffected account/market record. Rebuild only affected
    # account summaries and then their journal hash links.
    store['days']=[e for e in store.get('days',[]) if e.get('a') not in affected]
    for e in store['days']:
        e.pop('_lt',None)
    rehash(store['days'])
    for aid in affected: store.setdefault('series',{})[aid]=[]
    eng.journal()
    for aid in affected:
        days=[e for e in store['days'] if e.get('a')==aid]
        store['series'][aid]=[[e['d'],e['inv'],e['val'],e['bval']] for e in sorted(days,key=lambda e:e['d'])]
    eng.value()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--store',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--view',required=True);ap.add_argument('--report',required=True);ap.add_argument('--no-network',action='store_true')
    args=ap.parse_args(); manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    raw=Path(args.store).read_bytes(); original=json.loads(raw)
    now=datetime.now(sim.IST).date()
    source=copy.deepcopy(original); market=sim.Market(source,not args.no_network)
    applied=any(e.get('k')=='restatement' and e.get('correctionId')==manifest['id'] for e in original.get('events',[]))
    if not applied:
        codes={x['to'] for x in manifest['orders']}
        first=min(sim.D(x['date']) for x in manifest['orders']); end=min(now,sim.D(market.mf_asof))
        # Fetch every relevant NAV day, including intermediate daily prices for
        # the restated returns. No nearest-weekly or invented NAV is permitted.
        market.fetch_amfi([first+timedelta(days=i) for i in range((end-first).days+1)],codes)
    store,record=apply_orders(source,manifest,market.funds,market.c['amfi'],hashlib.sha256(raw).hexdigest())
    eng=sim.Engine(store,now,network=False)
    if record:
        rebuild_derived(store,eng,{x['acct'] for x in record['orders']})
    view=sim.build_view(store,eng)
    recorded=record or next(e for e in store['events'] if e.get('k')=='restatement' and e.get('correctionId')==manifest['id'])
    summary=dict(id=manifest['id'],applied=bool(record),authorisedApply=bool(manifest['apply']),
        alreadyApplied=not bool(record),originalFileSha256=recorded['originalFileSha256'],count=recorded['count'],
        totalAmount=recorded['totalAmount'],privateRecord=recorded)
    Path(args.out).write_text(json.dumps(store,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    Path(args.view).write_text(json.dumps(view,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    Path(args.report).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='privateRecord'}))

if __name__=='__main__':main()
