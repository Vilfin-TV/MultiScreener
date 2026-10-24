import copy,unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
import sim_engine as se
import ultimate_review as ur

class Reviews(unittest.TestCase):
    def test_calendar_holding_period_in_a_leap_year(self):
        from sim_tax import holding_term
        self.assertEqual(holding_term('equity','2027-10-26','2028-10-26'),'ST')
        self.assertEqual(holding_term('equity','2027-10-26','2028-10-27'),'LT')
    def test_24month_non_equity_and_specified_debt(self):
        from sim_tax import holding_term
        self.assertEqual(holding_term('other','2027-10-26','2029-10-26'),'slab')
        self.assertEqual(holding_term('other','2027-10-26','2029-10-27'),'LT')
        self.assertEqual(holding_term('debt','2026-10-26','2033-10-27'),'slab')
    def test_rolled_fill_uses_acquisition_date_not_order_date(self):
        evs=[{'k':'instalment','acct':'John-ETF','amount':1000},
             {'k':'order','oid':'x','acct':'John-ETF','T':'2026-10-26','sym':'ABC','strategy':'ultimate'},
             {'k':'fill','oid':'x','tradeDate':'2026-10-27','units':1,'gross':100,'charges':{'total':1},'carry':899,'credit':'2026-10-28'}]
        self.assertEqual(se.replay(evs)['John-ETF']['lots']['ABC'][0]['date'],'2026-10-27')
    def test_tax_year_uses_actual_execution_date(self):
        from sim_tax import annual_gains
        evs=[{'k':'order','oid':'s','acct':'John-MF','T':'2028-03-31'},
             {'k':'redeem','oid':'s','taxDate':'2028-04-01','gains':[{'class':'equity','term':'LT','gain':100}], 'charges':{'total':0}}]
        self.assertEqual(annual_gains({'events':evs},'John','2028-03-31')[0]['eqLT'],0)
        self.assertEqual(annual_gains({'events':evs},'John','2028-04-01')[0]['eqLT'],100)
    def test_actual_redemption_respects_leap_year_anniversary(self):
        eng,s=self.engine(when='2028-10-26')
        for e in eng.store['events']:
            if e['k']=='order':e['T']='2027-10-26'
            if e['k']=='allot':e['credit']='2027-10-28'
        order=se.append(eng.store,'order',oid='leap-sale',acct='John-MF',T='2028-10-26',side='sell',code=1,units=10000,strategy='ultimate',cashAccount=True)
        eng.nav_date_for=lambda *args:(date(2028,10,26),10)
        se.Engine.redeem(eng,order,eng.today,eng.today,eng.accts[0])
        done=eng.store['events'][-1]
        self.assertEqual(done['k'],'redeem');self.assertEqual(done['gains'][0]['term'],'ST');self.assertEqual(done['gains'][0]['days'],366)
    def engine(self,when='2028-03-10',price=10,mode='gain'):
        store={'events':[]};aid='John-MF'
        se.append(store,'instalment',acct=aid,iid=aid+'|2026-10-26',T='2026-10-26',amount=50000,cashAccount=True)
        se.append(store,'order',oid='original',acct=aid,iid='original',T='2026-10-26',side='buy',code=1,amount=50000,cashAccount=True)
        se.append(store,'allot',oid='original',amount=50000,units=10000,nav=5,credit='2026-10-28')
        checks=[{'id':str(i),'state':'pass'} for i in range(50)]
        old={'key':'1','name':'Synthetic old','category':'flexi','score':20,'earnings':{'pe':50,'earningsGrowth':5},'checks':checks}
        if mode=='rotation':old['checks'][0]={'id':'relative-value','state':'fail'}
        new={'key':'2','name':'Synthetic new','category':'flexi','score':90,'earnings':{'pe':10,'earningsGrowth':10},'checks':[{'id':str(i),'state':'pass'} for i in range(50)]}
        snap={'mf':{'selected':[old]},'candidates':{'mf':[old,new]}}
        f={'tax':'equity','lock':0,'lumpMin':1000,'buy':'L'}
        a=next(x for x in se.accounts() if x['id']==aid)
        eng=SimpleNamespace(store=store,today=date.fromisoformat(when),CFG=se.CFG,accts=[a],settle=lambda:None,
            mkt=SimpleNamespace(fund=lambda k:f,exit_rule=lambda k:{'known':True,'tiers':[]},mf_latest=lambda k,T:(T,price),funds={1:f,2:f}))
        return eng,snap
    def test_gain_harvest_uses_john_unused_basic_exemption_and_ltcg_room(self):
        eng,s=self.engine()
        with patch.object(ur,'latest',lambda *a:('synthetic',s)):ur.run(eng)
        orders=[e for e in eng.store['events'] if e['k']=='order' and e['side']=='sell']
        self.assertEqual(len(orders),1);self.assertEqual(orders[0]['decision']['mode'],'gain')
        self.assertEqual(orders[0]['decision']['estimatedTaxIncrease'],0)
    def test_loss_without_realised_taxable_gain_has_no_saving(self):
        eng,s=self.engine(price=4)
        with patch.object(ur,'latest',lambda *a:('synthetic',s)):ur.run(eng)
        self.assertFalse(any(e['k']=='order' and e['side']=='sell' for e in eng.store['events']))
    def test_no_short_term_gain_harvest(self):
        eng,s=self.engine(when='2027-03-10')
        with patch.object(ur,'latest',lambda *a:('synthetic',s)):ur.run(eng)
        self.assertFalse(any(e['k']=='order' and e['side']=='sell' for e in eng.store['events']))
    def test_valuation_rotation_and_settlement_revalidation(self):
        eng,s=self.engine(when='2028-04-03',mode='rotation')
        with patch.object(ur,'latest',lambda *a:('synthetic',s)):ur.run(eng)
        sell=next(e for e in eng.store['events'] if e['k']=='order' and e['side']=='sell')
        self.assertEqual(sell['ultimateReplacement'],'2')
        se.append(eng.store,'redeem',oid=sell['oid'],units=10000,gross=100000,net=99999,payout='2028-04-06',gains=[],charges={'total':1})
        eng.today=date(2028,4,5)
        with patch.object(ur,'latest',lambda *a:('synthetic',s)):ur.run(eng)
        self.assertFalse(any(e['k']=='order' and e.get('fromOid') for e in eng.store['events']))
        eng.today=date(2028,4,6)
        with patch.object(ur,'latest',lambda *a:('synthetic',s)):ur.run(eng)
        self.assertTrue(any(e['k']=='order' and e.get('fromOid')==sell['oid'] for e in eng.store['events']))
    def test_replacement_failing_checks_stays_cash(self):
        eng,s=self.engine(when='2028-04-03',mode='rotation')
        s['candidates']['mf'][1]['checks'][0]['state']='fail'
        with patch.object(ur,'latest',lambda *a:('synthetic',s)):ur.run(eng)
        self.assertFalse(any(e['k']=='order' and e['side']=='sell' for e in eng.store['events']))
if __name__=='__main__':unittest.main()
