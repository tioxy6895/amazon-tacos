"""CSV validation, persistent daily totals, and advertising metrics."""
import csv
import io
import math
import sqlite3
from datetime import date
from pathlib import Path


def parse_csv(content: bytes, kind: str):
    fields = {'sales': ['date', 'total_sales'],
              'ads': ['date', 'ad_spend', 'ad_sales']}[kind]
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
    if not set(fields).issubset(reader.fieldnames or []):
        raise ValueError('CSV 必須包含欄位：' + ', '.join(fields))
    rows = []
    seen = set()
    for number, row in enumerate(reader, 2):
        try:
            day = date.fromisoformat(row['date'].strip()).isoformat()
            values = [float(row[key]) for key in fields[1:]]
            if any(not math.isfinite(v) or v < 0 for v in values):
                raise ValueError()
            if day in seen:
                raise ValueError('日期重複；請先彙總為每日一列')
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f'第 {number} 列無效：請使用 YYYY-MM-DD 日期與非負數金額。{exc}') from exc
        seen.add(day)
        rows.append((day, *values))
    if not rows:
        raise ValueError('CSV 沒有資料列')
    return rows


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE IF NOT EXISTS sales (date TEXT PRIMARY KEY, total_sales REAL NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS ads (date TEXT PRIMARY KEY, ad_spend REAL NOT NULL, ad_sales REAL NOT NULL)')
    return db


def save_rows(db, kind, rows):
    statements = {
        'sales': 'INSERT INTO sales VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET total_sales=excluded.total_sales',
        'ads': 'INSERT INTO ads VALUES (?, ?, ?) ON CONFLICT(date) DO UPDATE SET ad_spend=excluded.ad_spend, ad_sales=excluded.ad_sales',
    }
    with db:
        db.executemany(statements[kind], rows)


def daily_rows(db):
    return db.execute('''SELECT dates.date, s.total_sales, a.ad_spend, a.ad_sales
        FROM (SELECT date FROM sales UNION SELECT date FROM ads) dates
        LEFT JOIN sales s ON dates.date=s.date LEFT JOIN ads a ON dates.date=a.date
        ORDER BY dates.date''').fetchall()


def metrics(rows):
    # Only compare dates with both sources to avoid misleading partial ratios.
    complete = [r for r in rows if all(v is not None for v in r[1:])]
    sales, spend, attributed = [sum(r[i] for r in complete) for i in (1, 2, 3)]
    return dict(total_sales=sales, ad_spend=spend, ad_sales=attributed,
                tacos=spend / sales if sales else None,
                acos=spend / attributed if attributed else None,
                roas=attributed / spend if spend else None,
                complete_days=len(complete), missing_days=len(rows)-len(complete))
