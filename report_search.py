"""Search daily imported reports without changing their stored values."""
import csv
import io
from math import ceil
from datetime import date


def row_status(row):
    if row[1] is None and row[2] is None:
        return '缺少銷售與廣告'
    if row[1] is None:
        return '缺少銷售'
    if row[2] is None or row[3] is None:
        return '缺少廣告'
    return '完整'


def search_rows(rows, start, end, keyword='', status='全部', sort='日期（新到舊）'):
    terms = keyword.casefold().split()
    result = []
    for row in rows:
        if not start.isoformat() <= row[0] <= end.isoformat():
            continue
        state = row_status(row)
        if status != '全部' and state != status:
            continue
        words = [row[0], state]
        for value in row[1:]:
            if value is not None:
                words.extend([str(value), f'{value:.2f}', f'{value:,.2f}'])
        text = ' '.join(words).casefold()
        if all(term in text for term in terms):
            result.append(row)
    if sort in ('日期（新到舊）', '日期（舊到新）'):
        result.sort(key=lambda row: row[0], reverse=sort == '日期（新到舊）')
    else:
        field = {'銷售額（高到低）': 1, '廣告花費（高到低）': 2, '廣告銷售額（高到低）': 3}[sort]
        result.sort(key=lambda row: (row[field] is None, -(row[field] or 0), row[0]))
    return result


def export_csv(rows):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['date', 'total_sales', 'ad_spend', 'ad_sales', 'data_status'])
    for row in rows:
        writer.writerow([row[0], *('' if v is None else f'{v:.2f}' for v in row[1:]), row_status(row)])
    return output.getvalue().encode('utf-8-sig')


def render_search(rows, source):
    import streamlit as st
    st.subheader('搜尋已匯入報表')
    st.caption(f'資料來源：{source}。搜尋日期、USD 金額與資料狀態；多個關鍵字以空格分隔，須全部符合。')
    if not rows:
        st.info('此資料來源尚未匯入報表。')
        return
    period = st.date_input('搜尋日期範圍', value=(date.fromisoformat(min(r[0] for r in rows)), date.fromisoformat(max(r[0] for r in rows))), key='report_search_period')
    keyword = st.text_input('搜尋關鍵字', placeholder='例如：2026-10、1200、缺少廣告', key='report_search_keyword')
    col1, col2 = st.columns(2)
    status = col1.selectbox('資料完整度', ['全部', '完整', '缺少銷售', '缺少廣告'], key='report_search_status')
    sort = col2.selectbox('排序方式', ['日期（新到舊）', '日期（舊到新）', '銷售額（高到低）', '廣告花費（高到低）', '廣告銷售額（高到低）'], key='report_search_sort')
    if len(period) != 2:
        st.info('請選擇開始與結束日期。')
        return
    result = search_rows(rows, *period, keyword, status, sort)
    st.write(f'找到 {len(result)} 筆每日資料（此來源共 {len(rows)} 筆）。')
    if not result:
        st.info('沒有符合條件的資料，請調整日期或關鍵字。')
        return
    st.download_button('下載搜尋結果 CSV', export_csv(result), 'report_search_results.csv', 'text/csv', key='download_report_search')
    pages = ceil(len(result) / 50)
    signature = (source, tuple(period), keyword, status, sort, tuple(result))
    if st.session_state.get('report_search_signature') != signature:
        st.session_state['report_search_signature'] = signature
        st.session_state['report_search_page'] = 1
    page = int(st.number_input('結果頁碼（每頁 50 筆）', min_value=1, max_value=pages, step=1, key='report_search_page'))
    st.caption(f'第 {page}／{pages} 頁；下載包含全部符合條件的資料。空白金額表示缺少報表，0 表示已匯入零金額。')
    selected = result[(page - 1) * 50:page * 50]
    records = [dict(zip(['日期', '總銷售額', '廣告花費', '廣告歸因銷售額', '資料狀態'], [*row, row_status(row)])) for row in selected]
    st.dataframe(records, width='stretch', hide_index=True)
