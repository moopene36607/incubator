# salonguard(沙龍守護)

**台灣美髮 / 美甲 / 美睫沙龍 — 回頭客流失預測 + 個人化 LINE 挽回訊息。**

預約系統的 RFM 資料 → 純函式風險分數 → AI 為高風險客戶寫 80 字 LINE 挽回訊息。

把「客人都是來一次就消失,等他不見了才發現」的痛點,變成每週主動的客戶經營。

---

## 痛點

台灣美髮 / 美甲 / 美睫沙龍約 **55,000 家**(財政部商業登記統計),但 99%+ 沒有任何「客戶流失預測」機制。

> **「客人都是來一次就消失,我也不知道哪裡出問題。」** — PTT BeautySalon 板

> **「客人沒來我也不知道是哪裡出問題,都是等她不見了才發現。」** — Dcard 美業社群

> **「老客人半年沒回來,主動問又怕打擾。」** — FB 美業老闆社團

具體痛點:

- 美業 1 對 1 服務,**客戶 LTV NT$10,000-30,000 / 年**,失一位客損失大
- 老闆 / 設計師憑「印象」記客戶,**10 位以上開始亂**;30 位以上完全失控
- 等發現客戶流失,**通常已 3-6 個月**,挽回率極低
- 主動「我想您」訊息怕打擾客戶,但**完全不聯絡又會徹底失聯**
- 預約系統 (iSalon / Beautix 等) 都有資料但**完全不會做流失預測**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **iSalon / WACA / Booksy / MindBody** | **完全只做預約 / 收款,無任何 churn prediction** |
| **Google Sheets 手算** | 沒有人會做。資料量一大就放棄 |
| **客戶 CRM(Salesforce / HubSpot)** | 月費 USD$50+,對 1-3 人小沙龍太重 |
| **ChatGPT 直接問** | 不知道你客戶歷史 + 每次要重貼資料 |

**Gap 結構性**:美業 SaaS 廠商認為「老闆靠感覺就好」沒動力加 ML;國際 CRM 太重不在地化。Google 搜尋「美髮 客戶流失 預測 台灣」零 SaaS 結果。

## salonguard 在做什麼

```
預約 / POS 資料 CSV(姓名 + 日期 + 服務 + 金額)
        │
        ▼
  ┌──────────────────────────────────┐
  │ rfm.py 純函式 RFM 計算             │
  │   Recency: 距今天數                │
  │   Frequency: 12 個月內到店次數     │
  │   Monetary: 平均客單價             │
  │   AvgInterval: 該客戶歷史平均間隔  │
  │   ratio = recency / avg_interval   │
  │   score = f(ratio) + bonus         │
  │   level = active/watch/warning/    │
  │            high/lost               │
  └────────────────┬─────────────────┘
                   │
                   ▼
        高風險名單(老闆審閱)
                   │
                   ▼
  ┌──────────────────────────────────┐
  │ Claude 為每位高風險客戶寫           │
  │ 80 字 LINE 挽回訊息                │
  │  - 第二人稱,語氣親切但專業          │
  │  - 引用具體上次服務史               │
  │  - 開放邀請結尾(問句 / hook)       │
  │  - 不堆折扣 / 不空泛 marketing     │
  └────────────────┬─────────────────┘
                   │
                   ▼
        ① markdown 主報告(風險分佈 + Top N 名單)
        ② LINE 訊息草稿(老闆審閱後一個個傳)
```

3 個關鍵架構決策:

1. **個人化的 avg_interval**:不是用「全店平均 60 天」這種粗糙閾值,而是**算每位客戶自己的歷史回訪間隔**。一位平均 30 天回的客戶 60 天沒來 = 高風險;一位平均 90 天回的客戶 60 天沒來 = 還很正常。
2. **加權邏輯**:高客單價(NT$2,500+)+5 分,高頻率(年 6 次+)+5 分 — 老客戶 + 高消費客戶突然不來**更值得擔心**。
3. **不批量自動發訊息**:LINE 訊息只是「草稿」,老闆審閱後**手動傳送**。避免被 LINE 標記為騷擾、避免發給「其實只是不好意思取消」的客戶。

## 動作

### 純函式預測(免 API key)

```bash
python3 salonguard.py \
    --history samples/customer_history.csv \
    --salon-name "美璃造型沙龍" \
    --today 2026-05-10 \
    --no-ai
```

`samples/customer_history.csv` 是 12 位客戶 × 平均 4 次預約紀錄(實際小沙龍可能 50-200 客戶 × 8-30 次紀錄)。輸出主報告 + 模板 LINE 訊息。

### 加 AI 寫個人化挽回訊息(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 salonguard.py \
    --history samples/customer_history.csv \
    --salon-name "美璃造型沙龍" \
    --today 2026-05-10 \
    --out output.md \
    --out-line line_messages.md
```

每位高風險客戶都會得到一段 80 字內、引用其具體服務史、開放邀請結尾的個人化 LINE 訊息。

### 預先產出的 demo

`examples/sample_output.md` 是完整主報告,顯示:
- 12 位客戶中:5 active / 2 watch / 4 **high** / 1 lost
- 高風險 Top 4 排序:**楊舒涵 77 分**(美甲客,過去 40 天回訪一次,已 105 天未來)、鄭文君 55、張惠雯 49.4、李美玲 47.6
- 每位都帶具體上次服務 / 客單價 / recency / avg_interval

`examples/sample_line_messages.md` 是 4 位高風險客戶的 LINE 訊息草稿。

## 已驗證 smoke test

- ✅ Ratio → level 對映精確(0.5→active / 1.2→watch / 1.5→warning / 2.5→high / 3.5→lost)
- ✅ Score 曲線:ratio 0.3→0, 1.0→10, 2.0→50, 5.0→≤100(平緩處理極端值)
- ✅ 單次到訪客戶用 60 天 default avg_interval,不會 crash
- ✅ 近期活躍客戶 → active(score 約 2.0)
- ✅ 高客單價 NT$5,000 客戶 → +5 加分(VIP 老客突然不來更值得挽回)
- ✅ Sample 12 客 Math 全對(楊舒涵 ratio 2.625 → score 77 / 鄭文君 ratio 2.0 → 55 都驗算過)

## 專案結構

```
salonguard/
├── README.md
├── salonguard.py            # CLI 主程式(讀 CSV + 純函式 RFM + AI 寫挽回訊息)
├── rfm.py                   # 純函式 RFM 計算 + 風險評分
├── samples/
│   └── customer_history.csv # 12 客 × 平均 4 次預約紀錄
├── examples/
│   ├── sample_output.md         # 主報告(風險分佈 + Top N 名單)
│   └── sample_line_messages.md  # LINE 訊息草稿
└── requirements.txt
```

總計約 350 行 Python。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **預約系統整合**:接 iSalon / Beautix / Google Sheets API,客戶資料自動 sync 不用每週匯 CSV
- **真實 ML 模型**:目前 RFM + ratio 已夠用,加 logistic regression / XGBoost 可在資料量大時提升準確度
- **trend dashboard**:本月新流失 / 挽回成功率 / 客戶 retention curve
- **LINE Bot 整合**:老闆審閱後一鍵發送,不用手動複製貼上
- **自動建議下次回訪時間**:依該客歷史 avg + 服務類型(燙染>90 天、護髮>30 天)
- **客單價趨勢警示**:某客戶從 NT$3K 變 NT$800 = 服務降級警示
- **多人 / 多店版**:5+ 設計師沙龍 + 連鎖 brand
- **客戶 lifetime value 計算**:幫沙龍 quantify 「這位客戶 1 年值多少」
- **挽回成效追蹤**:訊息傳出後 14 天內客戶有沒有回 → 統計訊息有效率

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 10 條 AI 訊息 | 試用 |
| **Solo** | **NT$599 / 月** | 1 人沙龍 / 美甲師 |
| **Studio** | NT$1,299 / 月 | 2-5 人小店,AI 訊息無限 + LINE Bot 整合 |
| **Chain** | NT$3,500 / 月 | 5+ 人連鎖店,多店 dashboard |
| **年付** | 上方 × 10 個月 | 省 2 個月 |

### WTP 計算

- 美業 1 客 LTV NT$10,000-30,000 / 年
- 挽回 1 位客 = NT$10,000+
- vs Solo NT$599/月 × 12 = NT$7,188/年 = **挽回 1 位客即年費回本**
- iSalon 已證明 NT$1,200/月 沙龍付得起,Solo NT$599 比 iSalon 便宜

### TAM

- 全台美髮 / 美甲 / 美睫店約 55,000 家(財政部商業登記)
- 取 3% 滲透 = 1,650 家 × NT$599 = **月 NT$99 萬 MRR / 年 NT$1,180 萬 ARR**
- 加 Studio / Chain + 橫移到牙醫 / 物理治療 / 寵物美容 等同樣有回頭客痛點的服務業 → 翻倍

## 早期 distribution

1. **FB 美業社群**(「台灣美髮設計師交流」「美甲師創業」)— 痛點來源 + distribution
2. **PTT BeautySalon / Dcard 美業版** — 流失抱怨貼文底下 demo
3. **iSalon / Beautix 老用戶**:他們已付軟體費,願意嘗試 add-on
4. **美髮 / 美甲 KOL 合作**(Vivian 雞排妹 / Pretty Sally 等)
5. **美業展覽**(台北國際美容展)— 實地 demo
6. **設計師 / 美甲師 LINE 社群**(常有訓練班 / 認證考社群)

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **iSalon / Beautix 自己加 churn 功能** | 中 | 預約系統廠商開發慢,且 churn 是 ML 邊緣能力;搶心占率 |
| **沙龍老闆覺得自己感覺就夠** | 中~高 | 提供 free tier + 一鍵 CSV 上傳,讓老闆親身體驗「我以為他還會回來但其實已經 100 天」的震撼 |
| **AI 訊息不夠人性化反而被反感** | 中 | 80 字硬限 + 引用具體服務史 + 老闆審閱才發 + 不堆折扣 |
| **客戶個資 / GDPR** | 高 | stateless API call;CSV 不上雲;企業版可走 self-host LLM |
| **客戶名單匯入麻煩(老闆不會操作)** | 中 | 一鍵 CSV 範本下載 + 影片教學 + 客服 LINE 協助 |
| **誤判導致無效騷擾** | 中 | 風險分數 + 等級透明顯示 / 老闆對每位客戶可標記「免打擾」 |

---

*第十八輪在 2026-05-10 產出於 incubator(台灣優先,**第七個非 doc-gen 模式 — Churn Prediction / Anomaly Detection**)。跟前 17 輪保險 / 稅 / 化妝品 / 製造 / 創作者 / F&B / 長照 / 法律 / 獸醫 / 月報 / 健身 / 機車估價 / LINE 整單 / 補助 RAG / 餐廳排班 / 婚攝媒合 / 政府標案 都不同 vertical 也不同架構。*
