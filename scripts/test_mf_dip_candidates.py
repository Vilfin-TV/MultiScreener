"""Regression tests for dip triggers, restrictions, selection and 37-check integrity."""
import copy
import json
import unittest
from pathlib import Path

import dip_rules as d
import mf_dip_candidates as m

ROOT=Path(__file__).resolve().parent.parent
def read(name): return json.loads((ROOT/name).read_text(encoding='utf-8'))

class Rules(unittest.TestCase):
    def test_amounts_unchanged(self):
        self.assertEqual(d.RULE['tiers'],[[15,20000],[10,10000],[5,5000]])
        self.assertEqual(d.SIM_START,'2026-10-19')
        for fall,want in [(4.99,(0,0)),(5,(5,5000)),(10,(10,10000)),(15,(15,20000))]: self.assertEqual(d.tier_of(fall),want)

    def walk(self, tail, second=True):
        from datetime import date,timedelta
        prices=[100.0]*65+tail
        rows=[((date(2026,7,1)+timedelta(days=i)).isoformat(),p) for i,p in enumerate(prices)]
        return d.walk(rows,dict(rows) if second else {})

    def test_two_closes_not_one(self):
        x=self.walk([94,100]); self.assertFalse(x[-2]['signal']);self.assertFalse(x[-1]['signal'])
        x=self.walk([94,94]); self.assertTrue(x[-1]['signal']); self.assertEqual(x[-1]['tier'],5)

    def test_new_tier_once(self):
        x=self.walk([94,94,94,89,89,89])
        self.assertEqual([v['tier'] for v in x if v['signal']],[5,10])
        self.assertEqual(self.walk([90,90])[-1]['tier'],10)

    def test_confirmation_and_crash(self):
        self.assertFalse(any(v['signal'] for v in self.walk([94,94],False)))
        self.assertFalse(self.walk([100,89])[-1]['signal'])

    def test_restrictions_override_stale_positive(self):
        self.assertFalse(d.mf_purchase({'code':118663,'buy':'LS'})['lump'])
        self.assertFalse(d.mf_purchase({'code':1,'buy':None})['lump'])
        self.assertFalse(d.mf_purchase({'code':1,'buy':'S'})['lump'])
        self.assertTrue(d.mf_purchase({'code':1,'buy':'L'})['lump'])

    def test_unknown_minimum_exit_future_nav_fail(self):
        f=dict(code=1,buy='LS',navDate='2026-10-25',status='Accelerating')
        ck=d.mf_fund_checks({'checks':[['x',True,'']]},f,[f],{'known':False},5000,'2026-10-23')
        self.assertEqual(len(ck),15)
        for label in ['Lump-sum minimum ≤ ₹5,000','Exit load ≤ 1% and within 12 months','NAV up to date']:
            self.assertFalse(next(x[1] for x in ck if x[0]==label))

    def test_real_block_integrity(self):
        sip=read('data/mf/smartsip.json'); b=sip['dip']; x=b['extra']
        self.assertEqual(set(x['segments']),{'next50','value','quality','momentum','lowvol','best'})
        for pid,entries in x['plans'].items():
            self.assertEqual(len(entries),6)
            for seg,e in entries.items():
                c=x['cands'][e['c']]; checks=x['segments'][seg]['checks']+c['checks']
                self.assertEqual(len(checks),37)
                self.assertEqual(e['passed'],sum(z[1] for z in checks))
                self.assertEqual(e['ok'],all(z[1] for z in checks))
                self.assertEqual(c['fundOk'],all(z[1] for z in c['checks'][:-1]))
                if seg!='best': self.assertEqual(m.index_id(c['name']),m.INDEXES[seg]['ident'])
                if e['ok']: self.assertTrue(c['purchase']['lump'])
                if pid=='h1c': self.assertFalse(e['ok'])
        gold=[c for c in b['cands']+list(b.get('alts',{}).values()) if c['code']==118663]
        for c in gold:
            self.assertFalse(c['purchase']['lump']); self.assertFalse(c['fundOk'])
            self.assertFalse(next(z[1] for z in c['checks'] if z[0]=='Open for lump-sum purchases'))

    def test_best_metrics_and_no_duplicate_fund(self):
        sip=read('data/mf/smartsip.json'); x=sip['dip']['extra']
        for pid,entries in x['plans'].items():
            best=x['cands'][entries['best']['c']]
            if entries['best']['ok']:
                self.assertTrue(best['metrics']['valid'])
                self.assertGreater(best['metrics']['epsGrowth'],0)
            self.assertNotIn(best['code'],{s['code'] for s in sip['plans'][pid]['slots']})

    def test_missing_eps_and_stale_pe_block(self):
        f={'code':1}; cfg=m.INDEXES['next50']
        metric=m.portfolio_metric(f,{'asOf':'2020-01-01','funds':{'1':[12,100,'2026-09']}},'2026-10-23',{},cfg)
        self.assertFalse(metric['valid'])

if __name__=='__main__': unittest.main()
