import csv
import io
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from analytics import connect, save_rows
from report_search import search_rows, export_csv, row_status

ROWS = [('2026-10-01', 1000, 100, 400), ('2026-10-02', 2000, 50, 100),
        ('2026-10-03', 500, None, None), ('2026-10-04', None, 0, 0)]
START, END = date(2026, 10, 1), date(2026, 10, 4)

class SearchTests(unittest.TestCase):
    def test_keywords_date_and_status(self):
        self.assertEqual(search_rows(ROWS, START, END, '2026-10 1,000'), [ROWS[0]])
        self.assertEqual(search_rows(ROWS, START, END, '缺少廣告'), [ROWS[2]])
        self.assertEqual(search_rows(ROWS, START, END, status='缺少銷售'), [ROWS[3]])
        self.assertEqual(search_rows(ROWS, date(2026, 10, 2), date(2026, 10, 2)), [ROWS[1]])
        self.assertEqual(search_rows(ROWS, START, END, 'not-found'), [])
        self.assertEqual(row_status(ROWS[3]), '缺少銷售')
        self.assertEqual(row_status(('2026-10-05', 0, 0, 0)), '完整')

    def test_sort_missing_last_and_export(self):
        self.assertEqual(search_rows(ROWS, START, END, sort='銷售額（高到低）'), [ROWS[1], ROWS[0], ROWS[2], ROWS[3]])
        exported = list(csv.DictReader(io.StringIO(export_csv(ROWS).decode('utf-8-sig'))))
        self.assertEqual(exported[2]['ad_spend'], '')
        self.assertEqual(exported[3]['ad_spend'], '0.00')
        self.assertEqual(exported[3]['data_status'], '缺少銷售')

    def test_date_interval_updates_metrics_and_search_is_independent(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'TACOS_DB_PATH': str(Path(folder) / 'test.db')}):
            db = connect(Path(folder) / 'test.db')
            save_rows(db, 'sales', [(r[0], r[1]) for r in ROWS if r[1] is not None])
            save_rows(db, 'ads', [(r[0], r[2], r[3]) for r in ROWS if r[2] is not None])
            db.close()
            app = AppTest.from_file('app.py').run()
            self.assertFalse(app.exception)
            period = next(d for d in app.date_input if d.label == '開始日期 — 結束日期')
            period.set_value((date(2026, 10, 2), date(2026, 10, 2))).run()
            self.assertFalse(app.exception)
            self.assertEqual([m.value for m in app.metric], ['US$ 2,000.00', 'US$ 50.00', 'US$ 100.00', '2.50%', '50.00%', '2.00 倍'])
            self.assertEqual(len(next(d.value for d in app.dataframe if '資料狀態' not in d.value.columns)), 1)
            app.text_input[0].set_value('缺少廣告').run()
            self.assertFalse(app.exception)
            self.assertEqual(next(d.value for d in app.dataframe if '資料狀態' in d.value.columns).iloc[0]['日期'], '2026-10-03')
            self.assertEqual(app.metric[0].value, 'US$ 2,000.00')
            next(d for d in app.date_input if d.label == '開始日期 — 結束日期').set_value((date(2026, 9, 1), date(2026, 9, 2))).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 0)
            self.assertTrue(any('沒有資料' in i.value for i in app.info))

    def test_pagination_can_return_to_one_page(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'TACOS_DB_PATH': str(Path(folder) / 'test.db')}):
            from datetime import timedelta
            db = connect(Path(folder) / 'test.db')
            save_rows(db, 'sales', [((START + timedelta(days=i)).isoformat(), float(i)) for i in range(60)])
            db.close()
            app = AppTest.from_file('app.py').run()
            self.assertFalse(app.exception)
            app.number_input[0].set_value(2).run()
            self.assertEqual(len(next(d.value for d in app.dataframe if '資料狀態' in d.value.columns)), 10)
            app.text_input[0].set_value('2026-10-01').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.number_input[0].value, 1)
            self.assertEqual(len(next(d.value for d in app.dataframe if '資料狀態' in d.value.columns)), 1)
