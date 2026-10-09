import gzip
import json
import unittest
from datetime import date
from unittest.mock import Mock, patch
from amazon_api import (AdsAPI, SalesAPI, AmazonError, access_token,
                        sales_rows, ads_rows, download_json, request_json, validate_period)

START = date(2026, 1, 1)
END = date(2026, 1, 2)
CONFIG = {prefix + key: 'test-' + key for prefix in ('SP_', 'ADS_')
          for key in ('CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN')}

class AmazonTests(unittest.TestCase):
    def test_parse_sales(self):
        payload = {'salesAndTrafficByDate': [{'date': '2026-01-01',
                   'salesByDate': {'orderedProductSales': {'amount': 100, 'currencyCode': 'USD'}}}]}
        self.assertEqual(sales_rows(payload, START, END), [('2026-01-01', 100)])
        payload['salesAndTrafficByDate'][0]['salesByDate']['orderedProductSales']['currencyCode'] = 'EUR'
        with self.assertRaises(AmazonError):
            sales_rows(payload, START, END)
        with self.assertRaises(AmazonError):
            sales_rows({}, START, END)

    def test_aggregate_campaigns_and_zero_days(self):
        payload = [{'date': '2026-01-01', 'cost': 5, 'sales7d': 10},
                   {'date': '2026-01-01', 'cost': 15, 'sales7d': 30}]
        self.assertEqual(ads_rows(payload, START, END), [('2026-01-01', 20, 40), ('2026-01-02', 0, 0)])
        with self.assertRaises(AmazonError):
            ads_rows([{'date': '2026-01-01', 'cost': float('nan'), 'sales7d': 0}], START, END)
        with self.assertRaises(AmazonError):
            ads_rows([{'date': '2026-01-03', 'cost': 1, 'sales7d': 0}], START, END)

    @patch('amazon_api.request_json')
    def test_oauth_and_create(self, request):
        request.side_effect = [{'access_token': 'fake-access'}, {'reportId': 'sales-id'},
                               {'access_token': 'fake-access'}, {'reportId': 'ads-id'}]
        self.assertEqual(SalesAPI(CONFIG).create(START, END), 'sales-id')
        self.assertEqual(AdsAPI(CONFIG, 123).create(START, END), 'ads-id')
        calls = request.call_args_list
        self.assertEqual(calls[0].kwargs['data']['grant_type'], 'refresh_token')
        self.assertEqual(calls[1].kwargs['json']['reportType'], 'GET_SALES_AND_TRAFFIC_REPORT')
        self.assertEqual(calls[3].kwargs['headers']['Amazon-Advertising-API-Scope'], '123')
        self.assertEqual(calls[3].kwargs['json']['configuration']['columns'], ['date', 'campaignId', 'cost', 'sales7d'])
        with self.assertRaises(AmazonError):
            access_token({}, 'SP_')

    @patch('amazon_api.download_json')
    @patch('amazon_api.request_json')
    def test_pending_and_completed_sales(self, request, download):
        request.side_effect = [{'access_token': 'fake'}, {'processingStatus': 'IN_PROGRESS'},
                               {'processingStatus': 'DONE', 'reportDocumentId': 'doc'},
                               {'url': 'https://example.com/report', 'compressionAlgorithm': 'GZIP'}]
        download.return_value = {'salesAndTrafficByDate': [{'date': '2026-01-01',
                 'salesByDate': {'orderedProductSales': {'amount': 100, 'currencyCode': 'USD'}}}]}
        api = SalesAPI(CONFIG)
        self.assertEqual(api.read('id', START, END), ('IN_PROGRESS', None))
        download.assert_not_called()
        self.assertEqual(api.read('id', START, END), ('DONE', [('2026-01-01', 100)]))
        download.assert_called_once_with('https://example.com/report', True)

    @patch('amazon_api.download_json')
    @patch('amazon_api.request_json')
    def test_completed_and_failed_ads(self, request, download):
        request.side_effect = [{'access_token': 'fake'}, {'status': 'COMPLETED', 'url': 'https://example.com/report'},
                               {'status': 'FAILURE'}]
        download.return_value = []
        api = AdsAPI(CONFIG, 123)
        self.assertEqual(api.read('id', START, END)[1], [('2026-01-01', 0, 0), ('2026-01-02', 0, 0)])
        with self.assertRaises(AmazonError):
            api.read('id', START, END)

    @patch('amazon_api.requests.get')
    def test_download_gzip_no_auth(self, get):
        get.return_value = Mock(ok=True, content=gzip.compress(json.dumps([{'cost': 1}]).encode()))
        self.assertEqual(download_json('https://example.com/report'), [{'cost': 1}])
        get.assert_called_once_with('https://example.com/report', timeout=60)
        with self.assertRaises(AmazonError):
            download_json('http://example.com/report')

    @patch('amazon_api.requests.request')
    def test_error_does_not_disclose_response(self, request):
        request.return_value = Mock(ok=False, status_code=403, text='private-token')
        with self.assertRaises(AmazonError) as raised:
            request_json('GET', 'https://example.com')
        self.assertNotIn('private-token', str(raised.exception))

    def test_date_limits(self):
        with self.assertRaises(AmazonError):
            validate_period(START, date(2026, 2, 1))
        with self.assertRaises(AmazonError):
            validate_period(END, START)
        with self.assertRaises(AmazonError):
            validate_period(date.today(), date.today())
