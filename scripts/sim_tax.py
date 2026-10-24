"""Profile-aware Indian capital-gains estimates and harvesting disclosures.

Indian estimates only. Existing agents retain their explicit flat-slab model;
John has zero other income under the new regime. No foreign tax credits or
unfiled carry-forward losses are invented. TDS remains a separate cash flow.
"""
from datetime import date
import copy
import math

SOURCES=[
    'https://www.incometaxindia.gov.in/en/sale-of-shares',
    'https://www.incometaxindia.gov.in/w/tax-rates-and-computation',
]

def profile(person, config):
    special=person.get('taxProfile') or {}
    return {'residency':person.get('res','resident'),
            'regime':special.get('regime','existing model'),
            'otherIncome':special.get('otherIncome'),
            'debtSlab':config['tax']['debtSlab'],
            'basicExemption':400000 if special.get('regime')=='new' and person.get('res')!='nri' else 0,
            'ltcgExemption':config['tax']['ltcgExempt'],
            'stcgRate':config['tax']['stcgEquity'],'ltcgRate':config['tax']['ltcgEquity'],
            'cess':config['tax']['cess'],'sources':SOURCES,
            'assumption':'No other taxable income; new regime' if special.get('otherIncome')==0 else 'Existing profile model: 30% normal-income slab; no unused basic exemption assumed',
            'foreignTaxModelled':False,'lossCarryForwardAssumed':False}

def fy(d):
    d=date.fromisoformat(str(d)[:10]) if not isinstance(d,date) else d
    y=d.year-(d.month<4)
    return f'{y}-{str(y+1)[-2:]}'

def bucket(g):
    return 'eqLT' if g['term']=='LT' and g['class']=='equity' else 'otherLT' if g['term']=='LT' else 'eqST' if g['term']=='ST' else 'slabST'

def empty_gains():
    return {'eqLT':0.0,'otherLT':0.0,'eqST':0.0,'slabST':0.0}

def new_regime_tax(income):
    total=0.0
    bands=[(400000,0),(800000,.05),(1200000,.10),(1600000,.15),(2000000,.20),(2400000,.25),(float('inf'),.30)]
    prev=0
    for limit,rate in bands:
        total+=max(0,min(income,limit)-prev)*rate
        prev=limit
        if income<=limit:break
    return total

def liability(gains,p):
    """Same-year loss set-off, resident basic exemption, equity annual LTCG limit.

    Returns the annual liability, not tax deducted at source. Uses the higher
    special rate first when allocating a resident's unused basic exemption.
    """
    x={k:float(gains.get(k,0)) for k in empty_gains()}
    lt_loss=sum(-min(0,x[k]) for k in ('eqLT','otherLT'))
    st_loss=sum(-min(0,x[k]) for k in ('eqST','slabST'))
    x={k:max(0,v) for k,v in x.items()}
    # Long-term capital losses only offset LT; ST losses can offset either term.
    for k in ('otherLT','eqLT'):
        use=min(x[k],lt_loss);x[k]-=use;lt_loss-=use
    st_order=('slabST','eqST') if p.get('otherIncome') is None and p['debtSlab']>p['stcgRate'] else ('eqST','slabST')
    for k in (*st_order,'otherLT','eqLT'):
        use=min(x[k],st_loss);x[k]-=use;st_loss-=use
    other=p.get('otherIncome')
    total_income=(other or 0)+sum(x.values())
    basic=max(0,p['basicExemption']-(other or 0)-x['slabST']) if other is not None and p['residency']=='resident' else 0
    basic_used={}
    for k in ('eqST','otherLT','eqLT'):
        use=min(x[k],basic);x[k]-=use;basic-=use;basic_used[k]=use
    exempt_used=min(x['eqLT'],p['ltcgExemption'])
    taxable_eq_lt=max(0,x['eqLT']-p['ltcgExemption'])
    normal=(new_regime_tax((other or 0)+x['slabST'])-new_regime_tax(other or 0)) if other is not None else x['slabST']*p['debtSlab']
    rebate=0.0
    if other is not None and p['regime']=='new' and p['residency']=='resident':
        # Rebate and marginal relief apply to normal slab tax, never special CG tax.
        if total_income<=1200000:rebate=min(normal,60000)
        else:rebate=max(0,normal-max(0,total_income-1200000))
    normal=max(0,normal-rebate)
    special=x['eqST']*p['stcgRate']+(taxable_eq_lt+x['otherLT'])*p['ltcgRate']
    # High-income marginal surcharge relief needs the full income composition.
    # Do not publish a precise liability or harvest allowance without those inputs.
    supported=total_income<=5000000
    tax=(normal+special)*(1+p['cess'])
    return {'tax':round(tax,2) if supported else None,'supported':supported,
            'limitation':None if supported else 'Income exceeds ₹50 lakh; surcharge and marginal relief require a complete tax computation',
            'rawTax':tax if supported else None,'normalTax':round(normal*(1+p['cess']),2),
            'specialTax':round(special*(1+p['cess']),2),'rebate':round(rebate,2),
            'basicUsed':{k:round(v,2) for k,v in basic_used.items()},'basicLeft':round(basic,2),
            'ltcgExemptionUsed':round(exempt_used,2),'ltcgExemptionLeft':round(max(0,p['ltcgExemption']-x['eqLT']),2),
            'unabsorbedSTLoss':round(st_loss,2),'unabsorbedLTLoss':round(lt_loss,2),'totalIncome':round(total_income,2)}

def gain_room(gains,p):
    """Maximum additional equity LT gain with no material annual tax increase."""
    before=liability(gains,p)['rawTax']
    if before is None:return None
    lo,hi=0.0,p['ltcgExemption']+p['basicExemption']+max(0,-gains.get('eqLT',0))
    for _ in range(55):
        mid=(lo+hi)/2;g=dict(gains);g['eqLT']=g.get('eqLT',0)+mid
        trial=liability(g,p)['rawTax']
        if trial is not None and trial<=before+1e-8:lo=mid
        else:hi=mid
    return math.floor(lo*100)/100

def annual_gains(store,name,asof):
    orders={e['oid']:e for e in store.get('events',[]) if e['k']=='order'}
    g=empty_gains();tds=0.0;charges=0.0
    for e in store.get('events',[]):
        if e['k']!='redeem':continue
        o=orders.get(e['oid'],{})
        if o.get('acct','').rsplit('-',1)[0]!=name or o.get('T','9999')>str(asof)[:10] or fy(o.get('T'))!=fy(asof):continue
        tds+=e.get('tds',0);charges+=(e.get('charges') or {}).get('total',0)
        for lot in e.get('gains',[]):g[bucket(lot)]+=lot['gain']
    return g,round(tds,2),round(charges,2)

def snapshot(store,view,a,eng):
    """FY shared per-person ledger facts plus account-specific FIFO opportunities."""
    people={p['name']:p for p in eng.CFG['persons']} if hasattr(eng,'CFG') else {p['name']:p for p in __import__('sim_engine').CFG['persons']}
    cfg=eng.CFG if hasattr(eng,'CFG') else __import__('sim_engine').CFG
    person=people[a['name']];p=profile(person,cfg);asof=view['today']
    realised,tds,costs=annual_gains(store,a['name'],asof)
    annual=liability(realised,p);room=gain_room(realised,p)
    opportunities=[];today=date.fromisoformat(asof)
    shared=[x['id'] for x in view['accounts'] if x['name']==a['name']]
    from sim_engine import tax_class,term_for,load_pct,etf_charges
    for h in a['holdings']:
        key=h['key'];f=eng.mkt.fund(int(key)) if a['product']=='mf' else None
        tc=tax_class(f,None if f else key,eng.mkt)
        rule=eng.mkt.exit_rule(int(key)) if f else {'known':True,'tiers':[]}
        eligible_gain=eligible_loss=st_loss=lt_loss=units=0.0;next_date=None;reason=''
        price_date=h.get('priceDate')
        price_ok=bool(h.get('price') and h['price']>0 and price_date and 0<=(today-date.fromisoformat(price_date)).days<=5)
        for lot in sorted(h['lots'],key=lambda x:(x['date'],x.get('oid',''))):
            if not price_ok:reason='Latest verified price unavailable or older than five days';break
            age=(today-date.fromisoformat(lot['date'])).days
            earliest=date.fromordinal(date.fromisoformat(lot['date']).toordinal()+366)
            if tc!='equity':reason='Tax harvesting currently covers equity-taxed holdings';break
            if lot['credit']>asof:reason='Awaiting settlement';break
            if not rule.get('known'):reason='Exit load unverified';break
            if (f or {}).get('lock') and age<365*(f or {})['lock']:reason='Units remain locked';break
            if load_pct(rule,age)>0:reason='Exit load still applies';break
            gain=lot['units']*(h['price'] or 0)-lot['cost']
            if age<=365 and gain>=0:reason='FIFO gains have not completed the long-term holding period';next_date=earliest.isoformat();break
            if gain>=0:eligible_gain+=gain
            else:
                eligible_loss-=gain
                if age<=365:st_loss-=gain
                else:lt_loss-=gain
            units+=lot['units']
        value=units*(h['price'] or 0)
        if a['product']=='mf':round_trip=value*(cfg['mfRules']['stampDuty']+cfg['mfRules']['sttRedeemEquity'])
        else:round_trip=etf_charges(value,'sell',a['res'],True)['total']+etf_charges(value,'buy',a['res'],True)['total']
        gain_allowed=min(eligible_gain,room or 0)
        potential=gain_allowed*p['ltcgRate']*(1+p['cess'])
        loss_trial=dict(realised);loss_trial['eqLT']-=lt_loss;loss_trial['eqST']-=st_loss
        trial=liability(loss_trial,p)['tax']
        loss_saving=max(0,annual['tax']-trial) if annual['tax'] is not None and trial is not None else 0
        permitted=p['residency']=='resident' or cfg['taxHarvest'].get('nriGainHarvest',False)
        if f and ('L' not in (f.get('buy') or '') or str(key)=='118663'):
            permitted=False;reason='Fresh lump-sum buy-back unavailable or unverified; choose an eligible replacement before harvesting'
        if not permitted and eligible_gain:reason='NRI gain-harvest policy disabled; TDS cash cost applies'
        action='Review opportunity' if units and ((permitted and potential>round_trip and gain_allowed>=cfg['taxHarvest']['minGain']) or loss_saving>round_trip) else 'No beneficial harvest currently'
        opportunities.append({'key':key,'name':h['name'],'fifoUnits':round(units,6),'eligibleGain':round(eligible_gain,2),
                              'eligibleLoss':round(eligible_loss,2),'gainWithinRoom':round(gain_allowed,2),
                              'roundTripCost':round(round_trip,2),'futureTaxSavingCeiling':round(potential,2),
                              'currentLossTaxSaving':round(loss_saving,2),'netPotential':round(max(potential if permitted else 0,loss_saving)-round_trip,2),
                              'action':action,'reason':reason,'nextEligible':next_date})
    return {'asOf':asof,'financialYear':fy(asof),'profile':p,'sharedAccounts':shared,
            'realised':{k:round(v,2) for k,v in realised.items()},'annualEstimate':annual,'additionalLTCGRoom':room,
            'tdsPaid':tds,'realisedCharges':costs,'opportunities':opportunities,
            'executed':a.get('harvests',[]),'note':'Future tax-saving ceiling assumes the harvested gain would otherwise be taxed in a later financial year at today’s rates. It is not a refund or a guaranteed saving. Losses are credited only against available taxable capital gains. All accounts of one person share exemptions; other investors do not.'}
