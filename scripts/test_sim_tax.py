import unittest
from sim_tax import liability,profile,empty_gains,gain_room,fy,new_regime_tax,snapshot,annual_gains
from types import SimpleNamespace

CFG={'tax':{'debtSlab':.3,'ltcgExempt':125000,'stcgEquity':.2,'ltcgEquity':.125,'cess':.04}}

class ProfileTaxes(unittest.TestCase):
    def setUp(self):
        self.john=profile({'name':'John','res':'resident','taxProfile':{'regime':'new','otherIncome':0}},CFG)
        self.resident=profile({'res':'resident'},CFG)
        self.nri=profile({'res':'nri'},CFG)
    def tax(self,p,**kw):return liability(dict(empty_gains(),**kw),p)['tax']
    def test_john_basic_exemption_and_capital_gains(self):
        self.assertEqual(self.tax(self.john,eqLT=525000),0)
        self.assertEqual(self.tax(self.john,eqLT=625000),13000)
        self.assertEqual(self.tax(self.john,eqST=500000),20800)
    def test_zero_other_income_does_not_mean_zero_tax_forever(self):
        self.assertGreater(self.tax(self.john,eqLT=1500000),0)
        self.assertGreater(self.tax(self.john,slabST=1500000),0)
    def test_rebate_only_normal_income(self):
        self.assertEqual(self.tax(self.john,slabST=1000000),0)
        self.assertEqual(self.tax(self.john,eqST=1000000),124800)
    def test_shared_equity_exemption_and_loss_setoff(self):
        self.assertEqual(self.tax(self.resident,eqLT=225000),13000)
        self.assertEqual(self.tax(self.resident,eqLT=225000,eqST=-100000),0)
        self.assertEqual(self.tax(self.resident,eqST=100000,eqLT=-200000),20800)
    def test_nri_has_no_basic_exemption(self):
        self.assertEqual(self.tax(self.nri,eqST=100000),20800)
        self.assertEqual(self.tax(self.nri,eqLT=225000),13000)
    def test_debt_is_normal_slab_and_fiscal_boundary(self):
        self.assertEqual(self.tax(self.resident,slabST=100000),31200)
        self.assertEqual(fy('2027-03-31'),'2026-27')
        self.assertEqual(fy('2027-04-01'),'2027-28')
    def test_room_after_shared_realised_gains(self):
        g=dict(empty_gains(),eqLT=100000)
        self.assertAlmostEqual(gain_room(g,self.resident),25000,delta=.1)
        self.assertAlmostEqual(gain_room(g,self.john),425000,delta=.1)
    def test_progressive_bands(self):
        self.assertEqual(new_regime_tax(400000),0)
        self.assertEqual(new_regime_tax(1200000),60000)
        self.assertEqual(new_regime_tax(2400000),300000)
    def test_room_never_exceeds_exact_exemption(self):
        self.assertLessEqual(gain_room(empty_gains(),self.resident),125000)
        self.assertLessEqual(gain_room(empty_gains(),self.john),525000)
    def test_short_loss_uses_higher_normal_slab_first(self):
        self.assertEqual(self.tax(self.resident,eqST=100000,slabST=100000,eqLT=-1),52000)
        self.assertEqual(self.tax(self.resident,eqST=-50000,slabST=100000),15600)
    def test_high_income_does_not_publish_incomplete_surcharge_estimate(self):
        g=dict(empty_gains(),eqLT=5100000)
        self.assertIsNone(liability(g,self.john)['tax'])
        self.assertIsNone(gain_room(g,self.john))
    def test_realised_shared_across_products_and_fiscal_boundary(self):
        store={'events':[{'k':'order','oid':'a','acct':'X-MF','T':'2026-04-01'},
                         {'k':'order','oid':'b','acct':'X-ETF','T':'2026-03-31'},
                         {'k':'redeem','oid':'a','tds':10,'gains':[{'class':'equity','term':'LT','gain':2000}]},
                         {'k':'redeem','oid':'b','gains':[{'class':'equity','term':'LT','gain':5000}]}]}
        g,tds,_=annual_gains(store,'X','2026-10-24')
        self.assertEqual(g['eqLT'],2000);self.assertEqual(tds,10)
    def test_fifo_short_term_loss_can_be_harvested_but_short_gain_cannot(self):
        cfg={**CFG,'persons':[{'name':'X','res':'resident'}],
             'mfRules':{'stampDuty':.00005,'sttRedeemEquity':.00001},
             'taxHarvest':{'minGain':1000,'nriGainHarvest':False}}
        mkt=SimpleNamespace(fund=lambda _:dict(tax='equity',buy='LS'),exit_rule=lambda _:dict(known=True,tiers=[]))
        eng=SimpleNamespace(CFG=cfg,mkt=mkt)
        a={'id':'X-MF','name':'X','product':'mf','res':'resident','holdings':[
            {'key':'1','name':'Test','price':90,'priceDate':'2026-10-23','lots':[{'date':'2026-05-01','credit':'2026-05-05','units':100,'cost':10000}]}]}
        v={'today':'2026-10-24','accounts':[a]}
        t=snapshot({'events':[]},v,a,eng)
        self.assertEqual(t['opportunities'][0]['eligibleLoss'],1000)
        self.assertEqual(t['opportunities'][0]['currentLossTaxSaving'],0)
        a['holdings'][0]['price']=110
        t=snapshot({'events':[]},v,a,eng)
        self.assertEqual(t['opportunities'][0]['fifoUnits'],0)
        self.assertIsNotNone(t['opportunities'][0]['nextEligible'])

if __name__=='__main__':unittest.main()
