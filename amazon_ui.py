"""Streamlit controls for Amazon credentials and asynchronous report jobs."""
import os
from datetime import date, timedelta

import streamlit as st
from analytics import connect, save_rows
from amazon_api import AdsAPI, SalesAPI, AmazonError, validate_period

KEYS = ['SP_CLIENT_ID', 'SP_CLIENT_SECRET', 'SP_REFRESH_TOKEN',
        'ADS_CLIENT_ID', 'ADS_CLIENT_SECRET', 'ADS_REFRESH_TOKEN']


def configuration():
    values = {key: os.environ.get(key, '') for key in KEYS}
    try:
        for key in KEYS:
            if key in st.secrets:
                values[key] = str(st.secrets[key])
    except FileNotFoundError:
        pass
    return values


def render_amazon(root):
    config = configuration()
    st.subheader('Amazon 美國站連線')
    st.caption('銷售：SP-API 每日訂購商品銷售額。廣告：Sponsored Products，7 天歸因。尚未包含 Sponsored Brands／Display。')
    missing = [key for key in KEYS if not config[key]]
    if missing:
        st.info('尚未完成 Amazon 授權。需要先申請 SP-API 與 Ads API 權限，再於應用管理的 Settings → Secrets 設定憑證。請勿在聊天或 GitHub 貼金鑰。')
        with st.expander('查看申請入口與設定名稱'):
            st.markdown('[SP-API 申請說明](https://developer-docs.amazon.com/sp-api/docs/registering-as-a-developer) · [Amazon Ads API 申請](https://advertising.amazon.com/API/docs/en-us/setting-up/step-1-create-lwa-app)')
            st.write('缺少設定：' + '、'.join(missing))
            st.caption('SP-API 應用需要 Selling Partner Insights 報表權限與美國賣家帳號授權。Ads API 應用需獲准並取得該廣告帳號的授權。完整步驟在 GitHub 的 AMAZON_SETUP.md。')
        return root / 'data' / 'amazon_unconfigured.db'
    if st.button('連接 Amazon 廣告帳號'):
        try:
            st.session_state['amazon_profiles'] = AdsAPI(config).profiles()
        except AmazonError as exc:
            st.error(str(exc))
    profiles = st.session_state.get('amazon_profiles', [])
    if not profiles:
        st.info('請點「連接 Amazon 廣告帳號」取得可讀取的美國 USD 廣告帳號。')
        return root / 'data' / 'amazon_unconfigured.db'
    selected = st.selectbox('廣告帳號', profiles, format_func=lambda p: f"{p.get('accountInfo', {}).get('name', 'Amazon')} · {p['profileId']} · {p.get('timezone', '')}")
    profile_id = str(selected['profileId'])
    if not profile_id.isdigit():
        st.error('Amazon 廣告帳號識別碼無效。')
        return root / 'data' / 'amazon_unconfigured.db'
    path = root / 'data' / f'amazon_{profile_id}.db'
    st.caption('請確認這個廣告帳號與 SP-API 授權的賣家相同。API 資料與 CSV／範例資料分開保存。兩種報表的日期口徑可能不同；歸因銷售會持續更新，建議重抓已結束期間。')
    period = st.date_input('同步期間（最多 31 天）', value=(date.today() - timedelta(days=14), date.today() - timedelta(days=1)), key='amazon_period')
    if len(period) != 2:
        st.info('請選擇完整的起訖日期。')
        return path
    start, end = period
    jobs = st.session_state.setdefault('amazon_jobs', {}).setdefault(profile_id, {})
    if st.button('向 Amazon 申請銷售與廣告報表'):
        try:
            validate_period(start, end)
        except AmazonError as exc:
            st.error(str(exc))
            return path
        for kind, api_class in [('sales', SalesAPI), ('ads', AdsAPI)]:
            if kind in jobs and jobs[kind]['status'] not in ('已匯入', '失敗'):
                st.warning(f'{kind} 尚有處理中的報表，請先查詢或放棄。')
                continue
            try:
                api = api_class(config) if kind == 'sales' else api_class(config, profile_id)
                jobs[kind] = dict(id=api.create(start, end), start=start, end=end, status='已申請')
                st.success(('銷售' if kind == 'sales' else '廣告') + '報表已申請，請稍後點「查詢並匯入報表」。')
            except AmazonError as exc:
                st.error(('銷售：' if kind == 'sales' else '廣告：') + str(exc))
    if jobs:
        if st.button('查詢並匯入報表'):
            for kind, job in jobs.items():
                if job['status'] == '已匯入':
                    continue
                try:
                    api = SalesAPI(config) if kind == 'sales' else AdsAPI(config, profile_id)
                    status, rows = api.read(job['id'], job['start'], job['end'])
                    job['status'] = status
                    if rows is not None:
                        db = connect(path)
                        try:
                            save_rows(db, kind, rows)
                        finally:
                            db.close()
                        job['status'] = '已匯入'
                        st.success(('銷售' if kind == 'sales' else '廣告') + f'已匯入 {len(rows)} 天。')
                except AmazonError as exc:
                    st.error(('銷售：' if kind == 'sales' else '廣告：') + str(exc))
        for kind, job in jobs.items():
            st.write(f"{'銷售' if kind == 'sales' else '廣告'}：{job['start']} ～ {job['end']}，{job['status']}")
        if st.button('放棄目前追蹤的報表'):
            jobs.clear()
            st.rerun()
        st.caption('Amazon 報表可能需要數分鐘。查詢按鈕會檢查一次，不會重新申請；網頁工作階段結束後需重新申請。放棄追蹤不會取消 Amazon 已建立的報表。')
    return path
