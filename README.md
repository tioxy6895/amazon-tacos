# Amazon TACoS

Amazon 美國站營運分析系統第一版，使用 Python、Streamlit、SQLite。
支援銷售與廣告 CSV 匯入、日期篩選、每日趨勢與 TACoS／ACoS／ROAS 儀表板。
已加入 Amazon SP-API 與 Ads API 報表同步功能；實際使用需要 Amazon 核准與帳號授權。設定方式見 [AMAZON_SETUP.md](AMAZON_SETUP.md)。廣告目前僅支援 Sponsored Products。

## 啟動

需要 Python 3.12。於專案目錄執行：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

在本機瀏覽器開啟 http://localhost:8501。預設為「CSV／範例」頁面；點選「載入範例資料」即可試用。取得授權後可切換「Amazon API」。
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
6. 打開應用，選擇「CSV／範例」並點「載入範例資料」，預期顯示 TACoS 10%、ACoS 25%、ROAS 4 倍。

Community Cloud 的本機 SQLite 不是可靠的永久儲存；重建或重新部署可能遺失資料。
這種部署適合第一版展示。使用真實營運資料前，應限制存取，並另行加入永久資料庫與備份。

## 計算日期與報表搜尋

匯入資料後，在頁面上方「資料計算日期區間」選擇開始日與結束日。
總銷售額、廣告花費、廣告歸因銷售額、TACoS、ACoS、ROAS、趨勢圖與每日資料會立即依同一區間更新，包含開始與結束當日。
未選完兩個日期或區間沒有資料時，不會顯示誤導性的指標。

「搜尋報表」分頁可獨立指定搜尋日期範圍、關鍵字、資料完整度與排序。
關鍵字搜尋日期、金額與「完整／缺少銷售／缺少廣告」狀態；多個關鍵字以空格分隔，須全部符合。
目前報表不包含 ASIN、SKU 或商品名稱，不能搜尋商品。
結果每頁最多 50 筆，「下載搜尋結果 CSV」會下載全部符合條件的資料，使用 UTF-8 BOM 方便 Excel 開啟。
CSV 與 Amazon API 資料各自搜尋，不會混合；空白金額代表未匯入，零金額代表明確的 0。
搜尋條件不會改變儀表板的計算日期，也不會改寫資料庫。
