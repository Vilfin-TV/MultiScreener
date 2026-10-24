import unittest,math
from datetime import date,timedelta
from ultimate_history import metrics,current_mix

def series(years=8,rate=.1):
    end=date(2026,10,23);start=end-timedelta(days=round(years*365.25))
    return [(d.isoformat(),100*(1+rate)**((d-start).days/365.25)) for i in range((end-start).days+1) if (d:=start+timedelta(days=i)).weekday()<5]

class ObservedMetrics(unittest.TestCase):
    def test_all_periods_and_since_inception(self):
        x=metrics(series(),'2026-10-23')
        for y in (3,5,7):self.assertAlmostEqual(x['returns'][str(y)],10,places=3)
        self.assertAlmostEqual(x['returns']['1'],10,delta=.1)
        self.assertAlmostEqual(x['sinceInception'],10,places=3)
        self.assertEqual(x['maximumDrawdown'],0)
    def test_short_history_never_backfilled(self):
        x=metrics(series(years=2),'2026-10-23')
        self.assertIsNotNone(x['returns']['1'])
        self.assertTrue(all(x['returns'][str(y)] is None for y in (3,5,7)))
    def test_drawdown_from_actual_peak(self):
        x=metrics([('2026-10-19',100),('2026-10-20',120),('2026-10-21',90),('2026-10-22',110)],'2026-10-23')
        self.assertEqual(x['maximumDrawdown'],-25)
        self.assertIsNone(x['volatility'])
    def test_mix_is_aggregate_values_not_average_cagr(self):
        a=series(rate=.2);b=series(rate=0)
        x=current_mix({'a':a,'b':b},{'a':50,'b':50},'2026-10-23')
        self.assertGreater(x['returns']['7'],10)
        self.assertLess(x['returns']['7'],20)
    def test_missing_fund_history_does_not_drop_the_fund(self):
        x=current_mix({'a':series()},{'a':50,'b':50},'2026-10-23')
        self.assertEqual(x['observations'],0)
    def test_future_prices_excluded(self):
        x=metrics([('2026-10-22',100),('2026-10-23',110),('2026-10-24',1)],'2026-10-23')
        self.assertEqual(x['asOf'],'2026-10-23');self.assertEqual(x['maximumDrawdown'],0)

if __name__=='__main__':unittest.main()
