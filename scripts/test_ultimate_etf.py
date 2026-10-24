import copy,json,unittest
from pathlib import Path
from ultimate_etf import candidate

class ETFEligibility(unittest.TestCase):
    def setUp(self):
        s=json.loads((Path(__file__).parent/'fixtures/ultimate_oct2026.json').read_text(encoding='utf8'))
        self.e=copy.deepcopy(s['etf']['selected'][0]['evidence'])
    def states(self):return {x['id']:x['state'] for x in candidate(**self.e)['checks']}
    def test_all_fifty_gates_have_unique_ids(self):
        c=candidate(**self.e);self.assertTrue(c['eligible']);self.assertEqual(len(c['checks']),50);self.assertEqual(len(self.states()),50)
    def test_wrong_declared_benchmark_blocks_fund(self):
        self.e['e']['x']['benchmark']='Nifty Smallcap 250 TRI';self.assertEqual(self.states()['mandate'],'fail')
    def test_missing_volume_and_stale_price_fail_closed(self):
        self.e['bars']['v']=[];self.e['e']['d']='2026-10-01';s=self.states();self.assertEqual(s['volume-history'],'fail');self.assertEqual(s['price-date'],'fail')
    def test_proxy_holdings_never_satisfy_own_portfolio_gate(self):
        self.e['p']['src']='proxy';self.e['earn']['fullDisclosure']=False;s=self.states();self.assertEqual(s['own-holdings'],'fail');self.assertEqual(s['earnings-coverage'],'fail')
    def test_unknown_nav_or_premium_is_not_an_eligible_bargain(self):
        self.e['e']['x']['nav']=None;self.e['e']['prem']=None;s=self.states();self.assertEqual(s['nav'],'fail');self.assertEqual(s['premium'],'fail')
if __name__=='__main__':unittest.main()
