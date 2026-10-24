import unittest
from build_institutional_flows import amount, vector, aggregate, archive, latest

class FlowTests(unittest.TestCase):
    def test_exact_money_and_invalid_values(self):
        self.assertEqual(amount('14,445.54'),1444554)
        for value in ('NaN','Infinity','1.001'):
            with self.assertRaises(ValueError): amount(value)

    def test_net_and_gross_guards(self):
        self.assertEqual(vector(['10','12','-2','9','4','5']),[1000,1200,-200,900,400,500])
        for v in ([10,12,2,9,4,5],[-10,12,-22,9,4,5]):
            with self.assertRaises(ValueError): vector(v)

    def test_calendar_week_year_boundary(self):
        rows={'2025-12-31':[100,20,80,200,30,170], '2026-01-02':[10,40,-30,20,50,-30], '2026-01-05':[7,5,2,6,2,4]}
        w=aggregate(rows,'weekly')
        self.assertEqual([g['period'] for g in w],['2026-01-05','2025-12-29'])
        self.assertEqual(w[1]['values'],[110,60,50,220,80,140])
        self.assertEqual(w[1]['sessions'],2)
        self.assertEqual(aggregate(rows,'yearly')[0]['values'],[17,45,-28,26,52,-26])
        self.assertEqual(len(aggregate(rows,'monthly')),2)

    def test_archive_month_and_total_guards(self):
        def tr(day,v):return '<tr>'+''.join('<td>'+str(x)+'</td>' for x in [day]+v)+'</tr>'
        v=['1.10','2.00','-0.90','5','3','2']
        text=tr('Total',v)+tr('23-Oct-2026',v)
        self.assertEqual(len(archive(text,2026,10)[0]),1)
        for bad in [text.replace('Total','Other'),text+tr('23-Oct-2026',v),text.replace('23-Oct','23-Sep'),tr('Total',['2.20','4','-1.80','10','6','4'])+tr('23-Oct-2026',v)]:
            with self.assertRaises(ValueError):archive(bad,2026,10)

    def test_published_aggregates_independently(self):
        import json
        from build_institutional_flows import OUT
        j=json.loads(OUT.read_text(encoding='utf8'))
        daily={r['date']:r['values'] for r in j['daily']}
        for p in ('daily','weekly','monthly','yearly'):
            self.assertEqual(j['periods'][p],aggregate(daily,p))
        for month, m in j['reconciledMonths'].items():
            rows=[v for d,v in daily.items() if d.startswith(month)]
            self.assertEqual(m['sessions'],len(rows))
            self.assertEqual(m['total'],[sum(v[i] for v in rows) for i in range(6)])
        self.assertEqual(j['daily'][-1]['date'],j['asOf'])

if __name__=='__main__':unittest.main()
