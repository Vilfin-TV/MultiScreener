import unittest
from mf_return_audit import official_base_return

class OfficialReturnDates(unittest.TestCase):
    def test_missing_friday_is_not_replaced_with_thursday(self):
        snapshots={'2021-10-21':{'1':100}}
        self.assertIsNone(official_base_return(1,'2021-10-22',200,5,snapshots))

    def test_same_date_cagr(self):
        snapshots={'2021-10-21':{'1':100},'2021-10-22':{'1':110}}
        expected=((200/110)**.2-1)*100
        self.assertAlmostEqual(official_base_return(1,'2021-10-22',200,5,snapshots),expected)

    def test_absolute_return_and_missing_scheme(self):
        snapshots={'2025-10-23':{'1':100}}
        self.assertAlmostEqual(official_base_return(1,'2025-10-23',110,0,snapshots),10)
        self.assertIsNone(official_base_return(2,'2025-10-23',110,0,snapshots))

if __name__=='__main__':unittest.main()
