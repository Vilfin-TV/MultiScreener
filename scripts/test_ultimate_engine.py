"""Synthetic end-to-end execution plus the independent full ledger auditor.

Future test prices are explicitly synthetic and never written to production data.
"""
import copy,json,sys,tempfile,unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import sim_engine as se
import audit_sim as au
import ultimate_execution as ue

class EngineIntegration(unittest.TestCase):
    def test_two_product_orders_fills_cash_journal_and_independent_audit(self):
        cfg=copy.deepcopy(se.CFG);cfg['persons']=[p for p in cfg['persons'] if p.get('strategy')=='ultimate']
        dip=copy.deepcopy(se.DIP);dip['persons']=[]
        snap=json.loads((Path(__file__).parent/'fixtures/ultimate_oct2026.json').read_text(encoding='utf8'))
        def register(eng):
            ref=snap['snapshotHash']
            if ref not in eng.store.setdefault('ultimateSnapshots',{}):
                eng.store['ultimateSnapshots'][ref]={'snapshot':copy.deepcopy(snap),'firstSeenAt':'2026-10-24T01:00:00+00:00'}
                se.append(eng.store,'ultimate-snapshot',ref=ref,availableAt=snap['availableAt'],firstSeenAt='2026-10-24T01:00:00+00:00')
        with patch.object(se,'CFG',cfg),patch.object(se,'DIP',dip),patch.object(au,'CFG',cfg),patch.object(au,'DIP',dip),patch.object(ue,'register',register):
            store={'events':[],'days':[]};eng=se.Engine(store,date(2026,10,24),False)
            eng.run();self.assertFalse(any(e['k']=='instalment' for e in store['events']))
            eng.today=date(2026,10,26);eng.mkt.mf_asof=eng.mkt.etf_asof='2026-10-26'
            snap=next(iter(store['ultimateSnapshots'].values()))['snapshot']
            for c in snap['mf']['selected']:
                eng.mkt.funds[int(c['key'])]=copy.deepcopy(c['evidence']['f'])
                key=c['key'];px=eng.mkt.funds[int(key)]['nav'];eng.mkt.c['mf'].setdefault(key,{})['2026-10-26']=px
                eng.mkt.c['amfi'].setdefault('2026-10-26',{})[key]=px
            bench=str(cfg['benchmark']['mf']);eng.mkt.c['mf'].setdefault(bench,{})['2026-10-26']=100
            for key in [c['key'] for c in snap['etf']['selected']]+[cfg['benchmark']['etf']]:eng.mkt.c['etf'].setdefault(key,{})['2026-10-26']=100
            eng.run();view=se.build_view(store,eng)
            self.assertEqual(len(view['accounts']),2)
            for a in view['accounts']:
                self.assertEqual(a['invested'],20000);self.assertGreaterEqual(a['cash'],0)
                self.assertTrue(a['series']);self.assertTrue(any(d.get('a')==a['id'] for d in store['days']))
            count=len(store['events']);eng.run();self.assertEqual(len(store['events']),count)
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
                root=Path(tmp);(root/'s.json').write_text(json.dumps(store),encoding='utf8');(root/'v.json').write_text(json.dumps(view),encoding='utf8')
                with patch.object(sys,'argv',['audit_sim','--store',str(root/'s.json'),'--view',str(root/'v.json'),'--out',str(root/'a.json'),'--today','2026-10-26']):
                    result=au.main()
                report=json.loads((root/'a.json').read_text())
                self.assertEqual(result,0,report['errors'])
            sb=se.scoreboard(view,True);files=se.account_files(store,view,sb)
            self.assertEqual(set(files),{'john-mf','john-etf'})
            for f in files.values():
                self.assertEqual(f['detail']['contributionDates'],['2026-10-26'])
                self.assertEqual(f['detail']['benchmarkAsOf'],'2026-10-26')
                self.assertEqual(f['ultimate']['start'],'2026-10-26')
if __name__=='__main__':unittest.main()
