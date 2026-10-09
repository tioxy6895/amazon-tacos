# 直接串接 Amazon

目前程式支援 SP-API 美國站銷售報表，以及 Ads API 的 Sponsored Products 每日廣告報表。
需要 Amazon 核准與帳號授權，無法以 Seller Central 密碼取代 API 授權。

## 先取得 API 權限

1. 使用美國站賣家帳號登入 [Seller Central](https://sellercentral.amazon.com/)。
2. 依 [Amazon 官方開發者註冊說明](https://developer-docs.amazon.com/sp-api/docs/registering-as-a-developer) 申請 SP-API 開發者資格。僅操作自己的帳號時，依官方流程建立私人應用。
3. 申請並確認 **Selling Partner Insights** 角色，以及 `GET_SALES_AND_TRAFFIC_REPORT` 的資格。部分帳號／角色無法取得此報表，須先向 Amazon 確認資格。
4. 在應用管理取得 Login with Amazon Client ID、Client Secret，並由自己的賣家帳號授權取得 Refresh Token。
5. 另外依 [Amazon Ads API 入門](https://advertising.amazon.com/API/docs/en-us/setting-up/step-1-create-lwa-app) 建立 LWA 應用、申請 Ads API 存取。SP-API 權限不會自動提供 Ads API 權限。
6. Ads API 核准後，以 `advertising::campaign_management` scope 完成該廣告帳號的 OAuth 授權，取得對應 Ads Client ID、Client Secret、Refresh Token。

Amazon 的核准時間與資格由 Amazon 決定。不要將登入密碼、Client Secret 或 Refresh Token 貼到聊天或 GitHub。

## 安全設定到已部署應用

在 Streamlit 網頁右下角「管理應用」→ Settings → Secrets，加入下面六個設定。
使用你自己的值；不要直接保留空字串。這些值只應存於 Secrets。

```toml
SP_CLIENT_ID = ""
SP_CLIENT_SECRET = ""
SP_REFRESH_TOKEN = ""
ADS_CLIENT_ID = ""
ADS_CLIENT_SECRET = ""
ADS_REFRESH_TOKEN = ""
```

本機也可由同名環境變數，或未加入版控的 `.streamlit/secrets.toml` 提供。
環境變數必須為真正的授權值；若在代理環境使用佔位值，需確認代理支援對 LWA 表單請求與 Ads Client ID header 的替換，不能把佔位值複製到 Streamlit。
SP-API Refresh Token 和 Ads Refresh Token 不可任意互換。
請將 Streamlit 應用設為私人，並限制到可信任使用者；此程式共用單一賣家授權，沒有多租戶隔離。

## 直接取得資料

1. 開啟應用，選擇「Amazon API」（預設）。
2. 點「連接 Amazon 廣告帳號」，選擇美國 USD 帳號。確認它與 SP-API 授權的賣家相同。
3. 選擇已結束的日期，每次最多 31 天。建議先同步一週。
4. 點「向 Amazon 申請銷售與廣告報表」。Amazon 會非同步產生報表。
5. 等待數分鐘後點「查詢並匯入報表」；如果還未完成，稍後再查詢。這不會重複建立報表。
6. 兩份報表成功匯入後，畫面會顯示指標。未完成、失敗或缺少銷售日期不會當作完整資料計算。

報表追蹤保存在目前網頁工作階段；重啟後可重新申請。重新同步相同日期會覆蓋舊值。
API 資料放在 `data/amazon_<profileId>.db`，不會混入 CSV 與範例資料。

## 指標範圍與限制

- 銷售額為美國市場 `GET_SALES_AND_TRAFFIC_REPORT` 的 `orderedProductSales`，不是淨收入或付款結算。
- 廣告為 Sponsored Products，取 `spCampaigns` 的 `cost` 與 `sales7d`，彙總每日所有 campaigns。
- 尚未含 Sponsored Brands、Sponsored Display。因此 TACoS 目前標示「僅 SP」，不能視為全廣告渠道的 TACoS。
- 完成的廣告報表中沒有列出的日期視為零花費與零歸因銷售；未完成報表不會填零。
- 7 天歸因銷售可能隨時間更新，建議定期重抓過去期間。需核對廣告帳號時區與銷售報表日期口徑。
- SQLite 在 Community Cloud 重建時可能遺失資料，需重新同步；正式長期營運仍需要永久資料庫。

## 連線驗證

程式測試可驗證報表解析、授權請求結構、異常處理與畫面。
沒有真實授權時，不代表 Amazon 已核准或線上連線成功。實際授權後應確認帳號清單、報表申請、完成與匯入結果。
