# Amazon TACoS

Amazon 美國站營運分析系統第一版，使用 Python、Streamlit、SQLite。
支援銷售與廣告 CSV 匯入、日期篩選、每日趨勢與 TACoS／ACoS／ROAS 儀表板。
目前尚未串接 Amazon SP-API 或 Ads API。

## 啟動

需要 Python 3.12。於專案目錄執行：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

在本機瀏覽器開啟 http://localhost:8501，點選「載入範例資料」即可試用。
此版本為單人使用，沒有登入機制，請勿直接公開到網際網路。

## 匯入格式

CSV 使用 UTF-8 編碼、USD 金額、YYYY-MM-DD 日期，每天一列。
銷售檔欄位為 `date,total_sales`；廣告檔為 `date,ad_spend,ad_sales`。
範例在 `samples/`，也可以從介面下載。匯入前請將 Amazon 原始報表彙總為此格式。
兩份報表須使用相同日期時區與歸因口徑。金額必須為有限非負數。
同類報表相同日期再次匯入會覆蓋原值，其他日期會保留。
請將沒有廣告花費的日子明確填為零；缺少任一報表的日期不納入指標。

- TACoS＝廣告花費 ÷ 總銷售額
- ACoS＝廣告花費 ÷ 廣告歸因銷售額
- ROAS＝廣告歸因銷售額 ÷ 廣告花費

指標以所選期間金額合計計算，分母為零顯示「—」。
資料儲存在忽略版控的 `data/tacos.db`，重啟後保留。
可用 `TACOS_DB_PATH` 指定其他 SQLite 路徑。備份時先停止應用再複製資料庫。

## 測試

```bash
.venv/bin/python -m unittest discover -s tests -v
```

涵蓋 CSV 驗證、SQLite 持久化與覆蓋、缺少資料及零分母、Streamlit 儀表板與重新啟動。

## 部署到 Streamlit Community Cloud

1. 開啟 https://share.streamlit.io/ ，使用 GitHub 登入並授權此儲存庫。
2. 選擇 Create app，選取 `tioxy6895/amazon-tacos`。
3. Branch 填 `main`，Main file path 填 `app.py`。
4. 在 Advanced settings 選 Python **3.12**，不需填 Amazon API 金鑰。
5. 點 Deploy，完成後將應用的分享權限設為 **私人／僅限指定使用者**。
6. 打開應用，點「載入範例資料」，預期顯示 TACoS 10%、ACoS 25%、ROAS 4 倍。

Community Cloud 的本機 SQLite 不是可靠的永久儲存；重建或重新部署可能遺失資料。
這種部署適合第一版展示。使用真實營運資料前，應限制存取，並另行加入永久資料庫與备份。
