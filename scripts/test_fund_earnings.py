import unittest
from build_fund_earnings import portfolio_earnings,excluded_actions
import json
from datetime import date

class EarningsCoverage(unittest.TestCase):
    def test_fixed_current_quantity_earnings(self):
        p={'equityISIN':[['a',60],['b',30]],'mix':{'equity':90},'asOf':'2026-09'}
        n={'a':('A',100),'b':('B',200)};o={'a':('A',80),'b':('B',100)}
        v=portfolio_earnings(p,n,o,{'A':10,'B':20},{'A':10,'B':20},set())
        self.assertAlmostEqual(v['pe'],12)
        self.assertAlmostEqual(v['earningsGrowth'],(7.5/5.55-1)*100,places=2)
        self.assertEqual(v['coverage'],100)
    def test_partial_top_holdings_never_claim_full_coverage(self):
        p={'top':[['A','Sector',30,'a','equity']],'mix':{'equity':90}}
        v=portfolio_earnings(p,{'a':('A',100)},{'a':('A',100)},{'A':10},{'A':10},set())
        self.assertFalse(v['fullDisclosure']);self.assertAlmostEqual(v['coverage'],33.33)
    def test_foreign_equity_is_in_coverage_denominator(self):
        p={'equityISIN':[['a',60]],'mix':{'equity':60,'overseas':20}}
        v=portfolio_earnings(p,{'a':('A',100)},{'a':('A',100)},{'A':10},{'A':10},set())
        self.assertEqual(v['coverage'],75)
    def test_breadth_counts_only_comparable_earnings_positions(self):
        p={'equityISIN':[['a',50],['b',50]],'mix':{'equity':100}}
        v=portfolio_earnings(p,{'a':('A',100),'b':('B',100)},{'a':('A',100)},{'A':10,'B':10},{'A':10},set())
        self.assertEqual(v['positions'],1);self.assertEqual(v['disclosedEquityPositions'],2)
    def test_bonus_and_missing_history_excluded(self):
        p={'equityISIN':[['a',50],['b',50]],'mix':{'equity':100}}
        v=portfolio_earnings(p,{'a':('A',100),'b':('B',100)},{'a':('A',100),'b':('B',100)},{'A':10,'B':10},{'A':10,'B':10},{'a'})
        self.assertEqual(v['coverage'],50);self.assertEqual(v['corporateActionExcludedWeight'],50)
        rows=[{'exDate':'01-Oct-2026','subject':'Bonus 1:1','isin':'a'},{'exDate':'02-Oct-2026','subject':'Dividend','isin':'b'}]
        self.assertEqual(excluded_actions(json.dumps(rows),date(2025,10,23),date(2026,10,23)),{'a'})

if __name__=='__main__':unittest.main()
