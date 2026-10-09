"""Read-only Amazon US report integration; secrets are supplied by the host."""
import gzip
import json
import math
from datetime import date, timedelta
from urllib.parse import urlsplit

import requests

SP_BASE = 'https://sellingpartnerapi-na.amazon.com'
ADS_BASE = 'https://advertising-api.amazon.com'
MARKETPLACE = 'ATVPDKIKX0DER'


class AmazonError(Exception):
    """Safe to display: never includes response bodies, tokens or signed URLs."""


def request_json(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=30, **kwargs)
        if not response.ok:
            if response.status_code in (401, 403):
                raise AmazonError('Amazon 拒絕授權；請檢查應用權限、帳號授權與憑證。')
            if response.status_code == 429:
                raise AmazonError('Amazon 請求次數達到限制，請稍後再試。')
            raise AmazonError(f'Amazon 請求失敗（HTTP {response.status_code}）。請稍後重試或檢查報表權限。')
        return response.json()
    except (requests.RequestException, ValueError):
        raise AmazonError('Amazon 連線失敗或回傳格式無效，請稍後再試。') from None


def access_token(config, prefix):
    values = [config.get(prefix + suffix) for suffix in ('CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN')]
    if not all(values):
        raise AmazonError('尚未設定 Amazon 憑證，請在 Streamlit 的 Secrets 安全設定。')
    result = request_json('POST', 'https://api.amazon.com/auth/o2/token', data={
        'grant_type': 'refresh_token', 'client_id': values[0],
        'client_secret': values[1], 'refresh_token': values[2],
    })
    if not isinstance(result, dict) or not isinstance(result.get('access_token'), str) or not result['access_token']:
        raise AmazonError('Amazon 沒有回傳有效授權，請重新授權。')
    return result['access_token']


def validate_period(start, end):
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise AmazonError('請選擇有效的日期範圍。')
    if (end - start).days >= 31:
        raise AmazonError('每次同步最多 31 天。')
    if end >= date.today():
        raise AmazonError('請選擇已結束的日期，最晚為昨天。')


def download_json(url, compressed=False):
    # Report URLs are signed by Amazon. Never attach API/OAuth headers to them.
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise AmazonError('Amazon 報表下載網址無效。')
    try:
        response = requests.get(url, timeout=60)
        if not response.ok:
            raise AmazonError('報表下載失敗或連結已過期，請重新查詢報表。')
        payload = response.content
        if compressed or payload.startswith(b'\x1f\x8b'):
            payload = gzip.decompress(payload)
        return json.loads(payload)
    except (requests.RequestException, ValueError, OSError, EOFError):
        raise AmazonError('報表下載或解壓縮失敗，請重新查詢報表。') from None


def amount(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AmazonError('Amazon 報表金額格式無效。') from None
    if not math.isfinite(number) or number < 0:
        raise AmazonError('Amazon 報表含無效金額，未寫入資料庫。')
    return number


def sales_rows(payload, start, end):
    data = payload.get('salesAndTrafficByDate') if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise AmazonError('銷售報表缺少每日資料。')
    result = []
    seen = set()
    for row in data:
        try:
            day = date.fromisoformat(row['date'])
            sales = row['salesByDate']['orderedProductSales']
            if sales['currencyCode'] != 'USD':
                raise AmazonError('僅支援 USD 銷售報表。')
            if not start <= day <= end or day in seen:
                raise AmazonError('銷售報表日期重複或超出同步範圍。')
            result.append((day.isoformat(), amount(sales['amount'])))
            seen.add(day)
        except (KeyError, TypeError, ValueError):
            raise AmazonError('銷售報表欄位格式無效。') from None
    if not result:
        raise AmazonError('銷售報表沒有資料，未更新資料庫。')
    return result


def ads_rows(payload, start, end):
    if not isinstance(payload, list):
        raise AmazonError('廣告報表格式無效。')
    totals = {}
    day = start
    while day <= end:
        totals[day.isoformat()] = [0.0, 0.0]
        day += timedelta(days=1)
    for row in payload:
        try:
            day = date.fromisoformat(row['date']).isoformat()
            if day not in totals:
                raise AmazonError('廣告報表日期超出同步範圍。')
            totals[day][0] += amount(row['cost'])
            totals[day][1] += amount(row['sales7d'])
        except (KeyError, TypeError, ValueError):
            raise AmazonError('廣告報表缺少 date、cost 或 sales7d 欄位。') from None
    return [(day, amount(values[0]), amount(values[1])) for day, values in sorted(totals.items())]


class SalesAPI:
    def __init__(self, config):
        self.headers = {'x-amz-access-token': access_token(config, 'SP_')}

    def create(self, start, end):
        validate_period(start, end)
        result = request_json('POST', SP_BASE + '/reports/2021-06-30/reports', headers=self.headers, json={
            'reportType': 'GET_SALES_AND_TRAFFIC_REPORT', 'marketplaceIds': [MARKETPLACE],
            'dataStartTime': start.isoformat() + 'T00:00:00Z',
            'dataEndTime': end.isoformat() + 'T23:59:59Z',
            'reportOptions': {'dateGranularity': 'DAY', 'asinGranularity': 'CHILD'},
        })
        if not isinstance(result, dict) or not isinstance(result.get('reportId'), str):
            raise AmazonError('Amazon 沒有回傳有效報表識別碼。')
        return result['reportId']

    def read(self, report_id, start, end):
        report = request_json('GET', SP_BASE + '/reports/2021-06-30/reports/' + report_id, headers=self.headers)
        status = report.get('processingStatus')
        if status in ('FATAL', 'CANCELLED'):
            raise AmazonError('銷售報表產生失敗或已取消；請檢查 Selling Partner Insights 報表權限。')
        if status != 'DONE':
            return status or 'UNKNOWN', None
        document = request_json('GET', SP_BASE + '/reports/2021-06-30/documents/' + report['reportDocumentId'], headers=self.headers)
        return status, sales_rows(download_json(document['url'], document.get('compressionAlgorithm') == 'GZIP'), start, end)


class AdsAPI:
    def __init__(self, config, profile_id=None):
        self.headers = {'Authorization': 'Bearer ' + access_token(config, 'ADS_'),
                        'Amazon-Advertising-API-ClientId': config['ADS_CLIENT_ID']}
        if profile_id:
            self.headers['Amazon-Advertising-API-Scope'] = str(profile_id)

    def profiles(self):
        data = request_json('GET', ADS_BASE + '/v2/profiles', headers=self.headers)
        if not isinstance(data, list):
            raise AmazonError('Amazon 廣告帳號清單格式無效。')
        return [p for p in data if isinstance(p, dict) and p.get('profileId') and p.get('countryCode') == 'US' and p.get('currencyCode') == 'USD']

    def create(self, start, end):
        validate_period(start, end)
        result = request_json('POST', ADS_BASE + '/reporting/reports', headers={
            **self.headers, 'Content-Type': 'application/vnd.createasyncreportrequest.v3+json'}, json={
            'name': f'Amazon TACoS SP {start} {end}',
            'startDate': start.isoformat(), 'endDate': end.isoformat(),
            'configuration': {'adProduct': 'SPONSORED_PRODUCTS', 'groupBy': ['campaign'],
                              'columns': ['date', 'campaignId', 'cost', 'sales7d'],
                              'reportTypeId': 'spCampaigns', 'timeUnit': 'DAILY', 'format': 'GZIP_JSON'},
        })
        if not isinstance(result, dict) or not isinstance(result.get('reportId'), str):
            raise AmazonError('Amazon 沒有回傳有效報表識別碼。')
        return result['reportId']

    def read(self, report_id, start, end):
        report = request_json('GET', ADS_BASE + '/reporting/reports/' + report_id, headers=self.headers)
        status = report.get('status')
        if status == 'FAILURE':
            raise AmazonError('廣告報表產生失敗，請重新建立報表。')
        if status != 'COMPLETED':
            return status or 'UNKNOWN', None
        if not report.get('url'):
            raise AmazonError('廣告報表下載連結不可用，請重新建立報表。')
        return status, ads_rows(download_json(report['url']), start, end)
