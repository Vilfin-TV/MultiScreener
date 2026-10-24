import copy,json,unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sim_engine as se
import ultimate_execution as ue
from audit_ultimate import audit
from ultimate_backtest import scenarios

ROOT=Path(__file__).resolve().parents[1]

class Execution(unittest.TestCase):
    def setUp(self):
        self.snapshot=json.loads((ROOT/'scripts/fixtures/ultimate_oct2026.json').read_text(encoding='utf8'))
        self.snapshot['availableAt']='2026-10-24T00:00:00+00:00';self.snapshot['snapshotHash']=ue.digest(self.snapshot)
    def engine(self,today='2026-10-26'):
        s=copy.deepcopy(self.snapshot)
        # Fixed synthetic execution fixture, independent of tomorrow's fund
        # selection and source coverage. Never used by a production ledger.
        def c(k,w,m=0):return {'key':k,'name':'Synthetic '+k,'category':'core','weight':w,'min':m,'checks':[{'id':str(i),'state':'pass'} for i in range(50)]}
        s['mf']={'selected':[c('1',35,1000),c('2',25,1000),c('3',15,1000),c('4',25,1000)],'cashWeight':0}
        s['etf']={'selected':[c('A',35),c('B',25),c('C',25)],'cashWeight':15}
        s['candidates']={'mf':[],'etf':[]};s['asOf']='2026-10-23';s['snapshotHash']=ue.digest(s);ref=s['snapshotHash']
        store={'events':[],'ultimateSnapshots':{ref:{'snapshot':s,'firstSeenAt':'2026-10-24T01:00:00+00:00'}}}
        p=next(p for p in se.CFG['persons'] if p['name']=='John')
        accts=[a for a in se.accounts() if a['name']=='John']
        funds={}
        for c in s['mf']['selected']:funds[int(c['key'])]={'buy':'LS','lumpMin':c['min'],'name':c['name']}
        return SimpleNamespace(store=store,today=date.fromisoformat(today),accts=accts,mkt=SimpleNamespace(funds=funds,remember=lambda code:None))
    def invoke(self,eng):
        with patch.object(ue,'register',lambda e:None):ue.run(eng)
    def test_no_funding_or_orders_before_start(self):
        eng=self.engine('2026-10-23');self.invoke(eng);self.assertEqual(eng.store['events'],[])
    def test_october_separate_budget_fees_and_idempotence(self):
        eng=self.engine();self.invoke(eng);n=len(eng.store['events']);self.invoke(eng);self.assertEqual(n,len(eng.store['events']))
        for aid in ('John-MF','John-ETF'):
            events=[e for e in eng.store['events'] if e.get('acct')==aid]
            self.assertEqual(sum(e['amount'] for e in events if e['k']=='instalment'),20000)
            orders=[e for e in events if e['k']=='order'];self.assertLessEqual(len(orders),5)
            budget=sum(o['amount'] for o in orders)
            self.assertEqual(budget,20000 if aid.endswith('MF') else 17000)
            for o in orders:
                if aid.endswith('ETF'):
                    n,ch=se.etf_units_for(o['amount'],123.45,'resident',True)
                    self.assertLessEqual(n*123.45+ch['total'],o['amount']+.001)
    def test_future_receipt_defers_as_cash_without_backdating(self):
        eng=self.engine();next(iter(eng.store['ultimateSnapshots'].values()))['firstSeenAt']='2026-10-27T00:00:00+00:00'
        self.invoke(eng)
        self.assertFalse(any(e['k']=='order' for e in eng.store['events']))
        self.assertEqual(se.replay(eng.store['events'])['John-MF']['cash'],20000)
    def test_unknown_lump_status_blocks_mf_buy(self):
        eng=self.engine()
        for f in eng.mkt.funds.values():f['buy']='S'
        self.invoke(eng)
        self.assertFalse(any(e['k']=='order' and e['acct']=='John-MF' for e in eng.store['events']))
    def test_source_corruption_is_not_available(self):
        s=copy.deepcopy(self.snapshot);s['mf']['cashWeight']=99
        self.assertFalse(ue.available(s,date(2026,10,26),'mf'))
    def test_stale_snapshot_holds_cash(self):
        eng=self.engine('2026-11-02');self.invoke(eng)
        self.assertFalse(any(e['k']=='order' for e in eng.store['events']))
        self.assertEqual(se.replay(eng.store['events'])['John-MF']['cash'],30000)
    def test_explicit_pending_switch_reserves_cash(self):
        state={'cash':10000,'sells':[{'net':5000,'payout':'2026-10-27'}],'orders':[{'oid':'s','side':'sell','done':{'net':5000}},{'oid':'b','side':'buy','fromOid':'s','amount':None}]}
        self.assertEqual(ue.free_cash(state,date(2026,10,26)),0)
    def test_84months_only(self):
        ss=ue.schedule(date(2035,1,1),lambda d:d.weekday()<5)
        self.assertEqual(sum(x[1] for x in ss),84*20000)
        self.assertTrue(all(date(2026,10,26)<=d<=date(2033,9,30) for d,_ in ss))
    def test_snapshot_gate_recomputation_and_tamper_detection(self):
        from audit_sim import Audit
        eng=self.engine('2026-10-24');ref=next(iter(eng.store['ultimateSnapshots']))
        eng.store['ultimateSnapshots']={self.snapshot['snapshotHash']:{'snapshot':copy.deepcopy(self.snapshot),'firstSeenAt':'2026-10-24T01:00:00+00:00'}};ref=self.snapshot['snapshotHash']
        se.append(eng.store,'ultimate-snapshot',ref=ref,availableAt=self.snapshot['availableAt'],firstSeenAt='2026-10-24T01:00:00+00:00')
        v={'accounts':[],'today':'2026-10-24'};a=Audit();audit(a,eng.store,v,se.CFG,se.is_trading);self.assertEqual(a.errors,[])
        eng.store['ultimateSnapshots'][ref]['snapshot']['mf']['selected'][0]['checks'][0]['state']='fail'
        a=Audit();audit(a,eng.store,v,se.CFG,se.is_trading);self.assertTrue(a.errors)
    def test_historical_scenario_has_exactly_twelve_deposits_per_year(self):
        from datetime import timedelta
        p=[((date(2024,1,1)+timedelta(days=i)).isoformat(),100.) for i in range(732)]
        b=scenarios({'x':p},{'x':100},'2026-01-01','mf')
        self.assertEqual(b['cases'][0]['contributed'],240000)
        self.assertFalse(b['pointInTimeStrategyValidated'])
if __name__=='__main__':unittest.main()
