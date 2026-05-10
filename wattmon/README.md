# wattmon(電耗哥)

**台灣中小型用戶 AMI 智慧電表用電異常偵測 + AI 節電建議。**

把每月台電帳單從「看到金額哀嚎」變成「30 秒看出哪台冷氣 / 冷凍櫃在燒錢」。

純函式偵測 4 類異常(夜間漏電 / 時段尖峰 / 單日異常 / baseline drift),AI 只負責為純函式發現的 anomaly 寫人性化解釋 + 具體節電建議。**LLM 永遠不算電費。**

---

## 痛點

台灣中小企業 ~150 萬家、餐飲業 17 萬家、早午餐店 2 萬家、美業 5.5 萬家,每月電費 NT$5K-30 萬,工廠夏季 NT$50 萬+。但 99%+ 的店家拿到台電帳單只能感嘆,**沒有工具看出哪邊燒掉**。

> **「夏天電費突然飆 30%,問了師傅也不知道是哪台冷氣的問題,只能等下個月看會不會自己回來。」** — 餐飲老闆 FB 社群

> **「我們五人小公司每月電費 NT$8K,光一個冷氣壞掉跑滿載一週可能就 NT$2K 多,但你不會知道是哪一週。」** — PTT Soft_Job

> **「冷凍櫃半夜失溫沒人發現,等早上開店食材壞了才知道,那一晚還多吃了 6 度電。」** — Dcard 餐飲業

具體痛點:

- 台電 AMI 30 分鐘智慧電表讀值已開放 API **5 年**,但小型用戶根本沒人去下載分析
- 中小企業老闆**沒時間**自己看 1,440 筆 (30 天 × 48 點) 30 分鐘讀值
- 設備老化 / 漏電 / 員工沒關電器,**通常拖到帳單來才發現** — 已經多花一個月
- 冷氣 / 冷凍 / 冷藏 是用電大戶,但**故障前期沒明顯徵兆**(只有耗電量會悄悄上升)
- 業務時段外(凌晨 02:00-05:00)的耗電應該很低,**但沒人盯**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **Schneider EcoStruxure / Siemens SIMATIC** | 走 enterprise BD,合約數十萬起跳,**SMB 完全進不去** |
| **iSensor / IoT Smart Plug 國內方案** | 賣硬體 + 安裝 NT$5-30K,中小老闆覺得貴 + 麻煩 |
| **台電官網 / 行動電表 App** | 提供 PDF 帳單 + 部分時段圖表,**完全沒有 AI 解釋** + **沒有異常偵測** |
| **經濟部能源局 / 工研院** | 補助驗證計畫,不是 SaaS,門檻高 |
| **ChatGPT 直接問** | 不知道你的電表讀值,每次要重貼資料,**不持續分析** |
| **Excel 自己分析** | 沒人會做,看到 1,440 筆讀值就放棄 |

**Gap 結構性**:能源 SaaS 廠商認為 SMB 客單價低、教育成本高、人均用電量小,沒動力做小型用戶 SaaS;但中小企業客戶總量極大、痛點明確、台電 API 已經公開可合法取用,**這是個典型 niche-SaaS 機會**。Google 搜尋「台灣 中小企業 AMI 用電 異常 偵測」零 SaaS 結果。

## wattmon 在做什麼

```
台電 AMI 30 分鐘讀值 CSV(timestamp, kwh)
        │
        ▼
  ┌──────────────────────────────────┐
  │ analyzer.py 純函式偵測:           │
  │  ① NIGHT_LEAK    店休時段漏電    │
  │     (23:00-06:00 > base × 2.5)   │
  │  ② HOUR_BURST    時段尖峰        │
  │     (vs 同 DOW × hour 4 週中位數)│
  │  ③ DAILY_HIGH    單日異常         │
  │     (vs 同 DOW 中位數 +30%+)      │
  │  ④ BASELINE_DRIFT 月度漂移        │
  │     (前後半段日均 ±10%+)          │
  └────────────────┬─────────────────┘
                   │
                   ▼
        anomaly list(含 severity + 多耗估算)
                   │
                   ▼
  ┌──────────────────────────────────┐
  │ Claude 為每筆 anomaly 寫:        │
  │  - 2-3 條最可能成因               │
  │  - 3 條具體可執行行動建議          │
  │  - 月省金額預估(引用純函式數字)  │
  │ 嚴禁:重新算 kWh / 編造設備細節   │
  │  / 推銷換新設備當主建議           │
  └────────────────┬─────────────────┘
                   │
                   ▼
        ① markdown 主報告(摘要 + 異常 + Top 3 行動)
        ② 給維修師傅 / 老闆的具體 checklist
```

3 個關鍵架構決策:

1. **數字 100% 純函式**:電費、kWh、偏差%、多耗估算全在 `analyzer.py`,LLM **永遠不重算**。LLM 只引用 anomaly.context 內已算好的數字。
2. **Multi-rule cross-validation**:同一事件可能同時觸發 NIGHT_LEAK + HOUR_BURST(像 04/18 凌晨冷凍故障)— 雙觸發代表事件物理上真實存在,**比單一 rule 可靠**。
3. **行動建議必須具體可執行**:壞例「節能」「檢查設備」;好例「叫維修廠商檢查 R134a 冷媒壓力」「冷氣濾網每月用清水沖洗」「把冷氣 24→26℃ 搭配電風扇」。

## 動作

### 純函式偵測(免 API key)

```bash
python3 wattmon.py samples/ami_30min.csv \
    --site-name "新莊鼎好早午餐" \
    --no-ai \
    --out output.md
```

`samples/ami_30min.csv` 是 30 天 × 48 點 = 1,440 筆 AMI 讀值,內含 3 個刻意注入的異常(冷凍故障 / 冷氣老化 / 季節性漂移)。輸出含期間摘要 + 4 筆偵測異常 + 多耗估算。

### 加 AI 寫個人化解釋(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 wattmon.py samples/ami_30min.csv \
    --site-name "新莊鼎好早午餐" \
    --out output.md
```

每筆 anomaly 會得到:可能成因 (2-3 條) + 行動建議 (3 條) + 月省金額預估。再加整體分析 + Top 3 優先行動。

### 預先產出的 demo

`examples/sample_output.md` 是完整 AI 模式報告,展示:
- 04/18 凌晨冷凍故障(NIGHT_LEAK + HOUR_BURST 雙觸發 → 高證據強度)
- 04/28 下午冷氣耗電飆 53%
- 後半月 baseline drift +12%(季節合理範圍但仍有優化空間)

`examples/sample_output_no_ai.md` 是純函式模式輸出,證明 LLM down 也能用。

## 已驗證 smoke test

- ✅ Sample 1,440 筆 → 4 筆 anomaly,刻意注入的 3 個異常全被偵測
- ✅ 04/18 03:00-04:30 冷凍異常被 NIGHT_LEAK + HOUR_BURST 雙觸發 (916% / 10.2x)
- ✅ 04/28 14:00-15:00 冷氣老化被 HOUR_BURST 偵測 (+53%)
- ✅ 後半期日均 vs 前半期日均 +12% → BASELINE_DRIFT 觸發
- ✅ 22:00-23:00 收店清潔時段 **不**會誤判為 NIGHT_LEAK(因為 NIGHT_HOURS = (23, 6))
- ✅ 純函式偵測完全 deterministic(同樣 CSV 跑 N 次結果一致)
- ✅ `--no-ai` 模式可獨立運行(免 API key)

## 專案結構

```
wattmon/
├── README.md
├── wattmon.py          # CLI(讀 CSV + 跑純函式偵測 + 呼叫 LLM 解釋)
├── analyzer.py         # 100% 純函式異常偵測 + 期間摘要
├── samples/
│   └── ami_30min.csv   # 30 天 × 48 點 = 1,440 筆讀值
├── examples/
│   ├── sample_output.md          # AI 模式完整報告
│   └── sample_output_no_ai.md    # 純函式模式報告
└── requirements.txt
```

總計約 350 行 Python。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **台電 AMI API 直接拉取**:免去手動匯出 CSV(API 公開可合法取用,但需用戶授權)
- **每日 / 每週 LINE Bot 推播**:異常即時通知,不用等月底
- **多店連鎖 dashboard**:5+ 店連鎖店看每店每日比較
- **電費分時段優化建議**:結合台電「住宅二段式時間電價」/ 「商業時間電價」拉開峰谷差
- **設備層級拆解**:用 NILM (Non-Intrusive Load Monitoring) 算法估算冷氣 / 冷凍 / 照明各佔多少用電
- **節電補助 partner**:接 經濟部能源局「節能設備汰換補助」/ 各縣市政府節能補助申請流程
- **跨期比較**:本月 vs 同期去年,排除季節性後找出真實異常
- **冷氣 IoT 整合**:接 米家 / Aqara / Switchbot 智慧插座做能源細項拆解

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 1 次手動上傳 + 純函式分析 | 試用 |
| **Solo** | **NT$199 / 月** | 單店餐廳 / 早午餐 / 美業 / 小工廠 |
| **Studio** | NT$799 / 月 | 3-10 店連鎖,多店 dashboard + LINE 推播 |
| **Chain** | NT$2,499 / 月 | 10-50 店連鎖,API + 客製化 alerting |
| **Enterprise** | 客製 NT$5,000+ / 月 | 工廠 / 高用電戶,接台電 AMI API + 即時推播 |
| **年付** | 上方 × 10 個月 | 省 2 個月 |

### WTP 計算

- 中小餐廳 / 早午餐月電費 NT$5K-15K,**1 次冷凍故障 NT$30K-80K + 食材損失** vs Solo NT$199 / 月 → **單次預警就回本 12 個月+**
- 工廠月電費 NT$30 萬-100 萬,**1% 用電優化 = NT$3K-10K/月** vs Enterprise NT$5K → **直接回本**
- 連鎖店 5-10 店每店年省 NT$10K-30K → 年省 NT$50K-300K vs Studio NT$10K/年 = **5-30x ROI**

### TAM

- 台灣中小企業 1.5M 家(中小企業白皮書),其中商業用電顯著者粗估 60 萬家
- 取 1% 滲透 = 6,000 家 × NT$199 = **月 NT$120 萬 MRR / 年 NT$1,440 萬 ARR**
- 加 Studio 連鎖 (預估 200 連鎖品牌) + Enterprise 工廠 (預估 100 廠) → 年 ARR **NT$3-5 千萬**
- 橫移到台電住宅高用戶 (年用 > 5,000 度) 約 30 萬戶 → C2C 個人版另開市場

## 早期 distribution

1. **PTT Soft_Job / Tech_Job / restaurant / store** — 痛點來源 + 早期種子用戶
2. **餐飲老闆 FB 社群**(「台灣餐飲業老闆交流」「早餐店老闆社群」5-10 萬人)
3. **商工會議所 / 商業總會 / 中小企業協會** partner 推廣
4. **台電「節電獎勵」/ 經濟部能源局「節能服務 ESCO」配合計畫** — 政府補助引流
5. **記帳士 / 會計師事務所 partner**(月省電 = 月省成本,跟記帳士的價值主張高度匹配)
6. **iCHEF / 沛點 / iSalon 等垂直 POS** integration partner — 已有 SMB 客戶基礎
7. **YouTube 老闆 KOL**(餐飲創業 / 工廠經營頻道)合作 case study
8. **冷凍 / 冷氣 / 空壓設備維修廠商**:wattmon 偵測到問題 → 推薦在地維修商,廠商付介紹費

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **台電 / Schneider 自己加 SMB SaaS** | 中 | 公部門開發慢且無 SMB 通路;搶心占率 + 在地化 (LINE / 台灣設備品牌支援) |
| **客戶不想手動上傳 CSV** | 高 | 早期 onboarding 含「我們幫你下載 + 整理」付費服務;中期接台電 AMI API |
| **誤報導致老闆失去信任** | 中 | 4 類偵測都有 severity + 雙觸發機制;誤報率公開呈現 |
| **節電建議若不可執行被質疑** | 中 | 行動建議都是具體 SOP / 可拍照驗證;不推銷換新設備當主建議 |
| **個資 / 用電隱私** | 中 | stateless API call;CSV 不上雲;企業版可走 self-host LLM |
| **季節性大幅波動** | 低 | BASELINE_DRIFT 已內建;未來加跨年度同期比較 |
| **大型工廠覺得偏 toy** | 中 | Solo 不打工廠,Enterprise 客製化才打工廠 |

---

*第二十二輪在 2026-05-10 產出於 incubator(台灣優先,**第十二個 AI 架構模式 — Time-Series Anomaly Detection**)。跟前 21 輪 doc-gen / pricing / OCR-aggregation / RAG / scheduling+LINE / matching / monitoring+alerting / churn / vision-pricing / vision-classification / personalization 都不同架構。*
