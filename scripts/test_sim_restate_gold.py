import copy
import json
import tempfile
import unittest
from pathlib import Path

import sim_engine as sim
from sim_restate_gold import apply_orders,verify_chain,digest

class RestatementTests(unittest.TestCase):
    def setUp(self):
        self.manifest=json.loads(Path(__file__).with_name('sim_gold_correction.json').read_text(encoding='utf-8'))
        self.store={'events':[],'days':[],'funds':{}}
        for r in self.manifest['orders']:
            sim.append(self.store,'instalment',iid=r['oid'].rsplit('|',1)[0],acct=r['acct'],T=r['date'],amount=r['amount'],ref='original')
            sim.append(self.store,'order',oid=r['oid'],acct=r['acct'],T=r['date'],amount=r['amount'],code=118663,slot='metal',side='buy',name='Nippon Gold',ref='original')
            sim.append(self.store,'allot',oid=r['oid'],amount=r['amount'],navDate=r['date'],nav=57.7448,units=sim.trunc(r['amount']/57.7448,3),stamp=0,net=r['amount'],credit='2026-10-22')
        self.manifest['publishedAnchor']={'events':len(self.store['events']),'head':self.store['events'][-1]['h']}
        self.funds={151745:dict(code=151745,name='WhiteOak Capital Multi Asset Allocation Fund',sub='multiasset',buy='LS',lumpMin=500,inc='2023-05-01'),
                    152056:dict(code=152056,name='DSP Multi Asset Allocation Fund',sub='multiasset',buy='LS',lumpMin=100,inc='2023-09-27')}
        self.navs={'2026-10-19':{'151745':16.1234,'152056':15.4321}}

    def test_exact_fifteen_and_contributions_preserved(self):
        old=copy.deepcopy(self.store)
        fixed,record=apply_orders(self.store,self.manifest,self.funds,self.navs,'archive-digest')
        self.assertEqual(self.store,old)
        self.assertEqual(record['count'],15);self.assertEqual(record['totalAmount'],56450)
        self.assertEqual(len(fixed['events']),len(old['events'])+1);verify_chain(fixed['events'])
        orders={e['oid']:e for e in fixed['events'] if e['k']=='order'}
        allots={e['oid']:e for e in fixed['events'] if e['k']=='allot'}
        for r in self.manifest['orders']:
            self.assertEqual(orders[r['oid']]['amount'],r['amount']);self.assertEqual(orders[r['oid']]['T'],r['date'])
            self.assertEqual(orders[r['oid']]['code'],r['to'])
            stamp=sim.r2(r['amount']*.00005);net=sim.r2(r['amount']-stamp)
            self.assertEqual(allots[r['oid']]['units'],sim.trunc(net/self.navs[r['date']][str(r['to'])],3))
        again,record2=apply_orders(fixed,self.manifest,self.funds,self.navs)
        self.assertIsNone(record2);self.assertEqual(again,fixed)

    def test_missing_official_nav_does_not_modify_source(self):
        old=copy.deepcopy(self.store)
        with self.assertRaises(ValueError): apply_orders(self.store,self.manifest,self.funds,{})
        self.assertEqual(self.store,old)

    def test_changed_contribution_blocks(self):
        bad=copy.deepcopy(self.manifest);bad['orders'][0]['amount']+=1
        with self.assertRaises(ValueError):apply_orders(self.store,bad,self.funds,self.navs)

    def test_minimum_and_closed_fund_block(self):
        for change in [{'lumpMin':1000},{'buy':''}]:
            funds=copy.deepcopy(self.funds);funds[151745].update(change)
            with self.assertRaises(ValueError):apply_orders(self.store,self.manifest,funds,self.navs)

    def test_redemption_blocks(self):
        sim.append(self.store,'order',oid='sell',acct=self.manifest['orders'][0]['acct'],code=118663,side='sell',T='2026-10-23')
        with self.assertRaises(ValueError):apply_orders(self.store,self.manifest,self.funds,self.navs)

    def test_wrong_anchor_and_extra_restricted_order_block(self):
        manifest=copy.deepcopy(self.manifest);manifest['publishedAnchor']['head']='bad'
        with self.assertRaises(ValueError):apply_orders(self.store,manifest,self.funds,self.navs)
        sim.append(self.store,'order',oid='extra',acct='Govind-MF',code=118663,side='buy',T='2026-10-20')
        with self.assertRaises(ValueError):apply_orders(self.store,self.manifest,self.funds,self.navs)

    def test_activation_does_not_change_approved_mapping_digest(self):
        active={**self.manifest,'apply':True}
        self.assertEqual(digest(active),digest(self.manifest))

if __name__=='__main__':unittest.main()
