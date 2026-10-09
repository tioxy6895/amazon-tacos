import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from analytics import connect, parse_csv, save_rows, daily_rows, metrics

class AnalyticsTests(unittest.TestCase):
    def test_import_persistence_and_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.db'
            db = connect(path)
            save_rows(db, 'sales', parse_csv(b'date,total_sales\n2026-10-01,1000\n', 'sales'))
            save_rows(db, 'ads', parse_csv(b'date,ad_spend,ad_sales\n2026-10-01,100,400\n', 'ads'))
            db.close()
            db = connect(path)
            result = metrics(daily_rows(db))
            self.assertEqual((result['tacos'], result['acos'], result['roas']), (.1, .25, 4))
            save_rows(db, 'sales', [('2026-10-01', 2000)])
            self.assertEqual(len(daily_rows(db)), 1)
            self.assertEqual(metrics(daily_rows(db))['tacos'], .05)
            db.close()

    def test_invalid_csv(self):
        for data in [b'date,total_sales\n', b'date,total_sales\nwrong,1\n',
                     b'date,total_sales\n2026-10-01,-1\n',
                     b'date,total_sales\n2026-10-01,nan\n',
                     b'date,total_sales\n2026-10-01,1\n2026-10-01,2\n', b'foo\n1\n']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_csv(data, 'sales')

    def test_missing_and_zero(self):
        result = metrics([('2026-10-01', 0, 0, 0), ('2026-10-02', 100, None, None)])
        self.assertEqual(result['missing_days'], 1)
        self.assertIsNone(result['tacos'])
        self.assertIsNone(result['acos'])
        self.assertIsNone(result['roas'])

    def test_dashboard_sample_and_restart(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'TACOS_DB_PATH': str(Path(folder) / 'app.db')}):
            app = AppTest.from_file('app.py').run()
            self.assertFalse(app.exception)
            next(b for b in app.button if b.label == '載入範例資料').click().run()
            self.assertFalse(app.exception)
            self.assertEqual([m.value for m in app.metric][-3:], ['10.00%', '25.00%', '4.00 倍'])
            restarted = AppTest.from_file('app.py').run()
            self.assertFalse(restarted.exception)
            self.assertEqual(len(restarted.metric), 6)

if __name__ == '__main__':
    unittest.main()
