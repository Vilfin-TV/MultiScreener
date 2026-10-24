import unittest
from datetime import date
from ultimate_rules import windows,checks,age

class UltimatePolicy(unittest.TestCase):
    def test_first_contribution_never_precedes_oct26(self):
        self.assertEqual(windows(2026,10,lambda d:d.weekday()<5),[(date(2026,10,26),20000)])
        self.assertEqual(windows(2026,9,lambda d:d.weekday()<5),[])
    def test_monthly_cap_and_two_windows(self):
        for month in range(1,13):
            w=windows(2027,month,lambda d:d.weekday()<5)
            self.assertEqual(sum(x[1] for x in w),20000)
            self.assertTrue(w[0][0].day<=7)
            self.assertTrue(w[1][0].day>=22)
    def test_holiday_does_not_roll_into_middle_week(self):
        w=windows(2027,1,lambda d:d.day>7 and d.weekday()<5)
        self.assertEqual(len(w),1);self.assertGreaterEqual(w[0][0].day,22)
    def test_missing_data_fails_closed_and_all_fifty_checks_named(self):
        r=checks({}, {}, {}, {},dict(asOf='2026-10-23'))
        self.assertEqual(len(r['checks']),50)
        self.assertEqual(len({x['id'] for x in r['checks']}),50)
        self.assertFalse(r['eligible'])
        self.assertTrue(all(x['state']!='pass' for x in r['checks'] if x['id'] in ('universe','nav','purchase','earnings-coverage')))
    def test_cash_replay_preserves_unspent_contribution(self):
        from sim_engine import replay
        events=[dict(k='instalment',acct='John-MF',cashAccount=True,amount=20000),
                dict(k='order',oid='a',acct='John-MF',cashAccount=True,code=1,T='2026-10-26'),
                dict(k='allot',oid='a',amount=5000,units=500,nav=10,credit='2026-10-28')]
        s=replay(events)['John-MF']
        self.assertEqual(s['cash'],15000)
        self.assertEqual(s['cash']+s['lots']['1'][0]['cost'],20000)
        events += [dict(k='order',oid='b',acct='John-MF',cashAccount=True,code=1,T='2026-11-26'),
                   dict(k='redeem',oid='b',units=100,net=1099,gross=1100,payout='2026-11-30')]
        s=replay(events)['John-MF'];self.assertEqual(s['cash'],16099)
        self.assertEqual(s['lots']['1'][0]['units'],400)

if __name__=='__main__':unittest.main()
