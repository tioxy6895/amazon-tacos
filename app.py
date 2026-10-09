from pathlib import Path
from datetime import date
import os
import streamlit as st
from analytics import connect, parse_csv, save_rows, daily_rows, metrics
from amazon_ui import render_amazon

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Amazon TACoS', page_icon='📊', layout='wide')
st.title('Amazon 美國站營運分析')
st.caption('連接 Amazon 美國站，或匯入每日 USD 報表，追蹤 TACoS、ACoS 與 ROAS。')
mode = st.sidebar.radio('資料來源', ['Amazon API', 'CSV／範例'])
if mode == 'Amazon API':
    database_path = render_amazon(ROOT)
    db = connect(database_path)
else:
    db = connect(os.environ.get('TACOS_DB_PATH', str(ROOT / 'data' / 'tacos.db')))

    with st.sidebar:
        st.header('匯入資料')
        st.caption('每個日期一列。同日期重新匯入會覆蓋該類報表的金額；請使用相同時區與廣告歸因口徑。')
        for kind, label in [('sales', '銷售'), ('ads', '廣告')]:
            content = (ROOT / 'samples' / f'{kind}.csv').read_bytes()
            st.download_button(f'下載{label}範例', content, f'{kind}.csv', 'text/csv', key=f'download_{kind}')
            uploaded = st.file_uploader(f'上傳{label} CSV', type='csv', key=kind)
            if st.button(f'匯入{label}', key=f'import_{kind}', disabled=uploaded is None):
                try:
                    parsed = parse_csv(uploaded.getvalue(), kind)
                    save_rows(db, kind, parsed)
                    st.success(f'已儲存 {len(parsed)} 天的{label}資料')
                except (ValueError, UnicodeDecodeError) as exc:
                    st.error(str(exc))
        if st.button('載入範例資料'):
            for kind in ('sales', 'ads'):
                save_rows(db, kind, parse_csv((ROOT / 'samples' / f'{kind}.csv').read_bytes(), kind))
            st.success('範例資料已載入；同日期資料已更新。')
rows = daily_rows(db)
db.close()
if not rows:
    st.info('尚無資料。請完成 Amazon 授權並同步報表。' if mode == 'Amazon API' else '請上傳兩份 CSV，或按左側「載入範例資料」開始。')
    st.stop()
period = st.date_input('日期範圍', value=(date.fromisoformat(rows[0][0]), date.fromisoformat(rows[-1][0])))
if len(period) != 2:
    st.info('請選擇開始與結束日期。')
    st.stop()
rows = [r for r in rows if period[0].isoformat() <= r[0] <= period[1].isoformat()]
m = metrics(rows)
if m['missing_days']:
    st.warning(f"{m['missing_days']} 天缺少銷售或廣告報表，未納入指標計算。")
st.caption(f"指標使用 {m['complete_days']} 天兩份報表皆完整的資料。分母為零時顯示 —。")
cols = st.columns(3)
for col, key, label in zip(cols, ['total_sales', 'ad_spend', 'ad_sales'], ['總銷售額', '廣告花費', '廣告歸因銷售額']):
    col.metric(label, f"US$ {m[key]:,.2f}")
cols = st.columns(3)
for col, key, label in zip(cols, ['tacos', 'acos', 'roas'], (['TACoS（僅 SP）', 'ACoS（SP，7 天）', 'ROAS（SP，7 天）'] if mode == 'Amazon API' else ['TACoS', 'ACoS', 'ROAS'])):
    value = m[key]
    col.metric(label, '—' if value is None else (f'{value:.2f} 倍' if key == 'roas' else f'{value:.2%}'))
st.caption('TACoS＝廣告花費／總銷售額 · ACoS＝廣告花費／廣告歸因銷售額 · ROAS＝廣告歸因銷售額／廣告花費')
records = [dict(zip(['日期', '總銷售額', '廣告花費', '廣告歸因銷售額'], r)) for r in rows]
st.subheader('每日趨勢')
if records:
    st.line_chart(records, x='日期', y=['總銷售額', '廣告花費', '廣告歸因銷售額'])
st.subheader('每日資料（USD）')
st.dataframe(records, width='stretch')
