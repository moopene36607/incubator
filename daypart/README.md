# daypart(時段透鏡)

**台灣餐飲店 / 飲料店 / 早午餐 一日銷售型態 EM 分群 — 2D Gaussian Mixture 自動找出 K 個客群 + AI 寫客群名稱 + 個人化時段促銷策略。**

老闆每月看 POS 銷售只有總額 + Top 10 商品,**不知道「我的店有幾種客群」**。daypart 從原始交易資料用 EM 演算法自動找 cluster,告訴你:**早班通勤族 30% / 主婦學生中餐 40%(營收主力 58%)/ 下午茶上班族 30%**,並為每個 cluster 設計具體促銷。

---

## 痛點

台灣餐飲業 ~17 萬家,早午餐 ~2 萬家,飲料店 ~2.5 萬家 = **21 萬家 + POS 但完全沒做 customer segmentation**:

> **「我覺得我的店有早班族 + 中餐主婦 + 下午茶客,但我不確定佔比多少。」** — Dcard 餐飲業老闆

> **「iCHEF 給我看每天營收 + Top 商品,但我想知道**早上跟下午的客人是不是同一群**。」** — PTT restaurant

> **「請行銷顧問做客戶分群一次 NT$30K,我月營收才 NT$15 萬。」** — FB 早午餐老闆社群

具體痛點:

- 餐飲店老闆**完全不知道「我有幾種客群」**;只看時段 / 商品分別的營收
- POS 提供原始 transaction 但**沒做 customer segmentation**
- iCHEF / 沛點 / Cashier / Coffee POS 等台灣 POS 都是**操作工具**,不做客群分析
- 老闆憑直覺設計 happy hour / 早鳥優惠,**常常目標客群錯誤**(e.g.,「下午茶買一送一」但下午茶客都單人消費)
- 行銷顧問做 customer segmentation 一次 NT$30-50K 太貴
- BI / Tableau / Power BI 給大企業,小店學不來
- ChatGPT 無法跑 EM / Mixture 模型
- 學術界 Gaussian Mixture 50 年成熟,**沒人做成小餐廳老闆可用 SaaS**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **iCHEF / 沛點 / Cashier / 點點全店通** | 操作工具不做 segmentation;Top 商品分析無客群維度 |
| **Tableau / Power BI** | 大企業 BI,小店學不來;不會自動分群 |
| **R / Python scikit-learn GMM** | 完全給研究員;老闆看不懂 BIC |
| **行銷顧問報告** | 一次 NT$30-50K;只做一次性分析 |
| **ChatGPT 直接問** | 不能跑 EM iterations;每次重貼資料 |
| **餐飲業 review 文章** | 「客群分析」教學文,**不能用在你的店** |

**Gap 結構性**:Gaussian Mixture EM 1977 年就有,但 50 年來**沒人做成小餐廳老闆可用 SaaS**。Google「台灣 餐飲 客群 分群 EM」零 SaaS。

## daypart 在做什麼

```
POS transactions CSV
  (time, spend_ntd, weekday)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ mixture.py 100% 純函式 stdlib(只用 math + statistics):   │
  │   1. find_best_k:跑 k=2..5 EM,用 BIC 選最佳 k             │
  │      BIC = -2 LL + p × log(N) — 較低 = 更好                │
  │   2. fit_em:                                               │
  │      E-step: γ_nk = π_k × N(x_n | μ_k, Σ_k) / Σ_j(...)    │
  │      M-step: μ_k / σ²_k / π_k 加權更新                     │
  │      用 log-sum-exp 避免數值溢位                            │
  │      用 quantile-based init 取代 random init(可重現)      │
  │   3. assign_transactions: hard assignment 取最高 P(k|x)    │
  │   4. profile_clusters: 每個 cluster 的 mu_time / mu_spend / │
  │      time_range / spend_range / 營收貢獻                    │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude 行銷顧問寫:                                          │
  │   - 每個 cluster 起客群名稱(早班通勤族 / 主婦學生中餐 /     │
  │     下午茶上班族 / 商務午餐 / 晚餐家庭 ...)                  │
  │   - 推測該 cluster 可能買什麼(基於時段 + 客單價)            │
  │   - 為每個 cluster 設計 1 個具體促銷策略 + 預期影響          │
  │   - 對店家整體 1-2 條結構性洞察                              │
  │ **LLM 永不算 cluster 數量 / 機率 / NT$**                     │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **EM 演算法 100% 純函式 stdlib**:不依賴 numpy / scikit-learn;只用 math + statistics + dataclass;對 200-2000 筆 transactions 完全夠用。
2. **BIC 自動選 k**:不要求老闆指定 cluster 數量;用 Bayesian Information Criterion 自動找最佳 k(2-5)。
3. **LLM 角色僅 personification**:LLM 不算分布、不算 BIC、不算 cluster 數量;**純粹幫純函式找出的 cluster 起一個老闆聽得懂的客群名稱 + 推測購買行為 + 設計促銷**。

## 動作

### 純函式 EM 分群(免 API key)

```bash
python3 daypart.py samples/transactions.csv --no-ai --out output.md
```

`samples/transactions.csv` 是 200 筆合成 transactions,**真實設計**包含 3 個 cluster(早班 60 / 中餐 80 / 下午茶 60)。

輸出含 BIC 模型選擇表 + 3 cluster profiles。

### 完整 AI 行銷顧問模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 daypart.py samples/transactions.csv --out output.md
```

加上 Claude 寫客群名稱 + 推測購買 + 促銷策略 + 整體洞察。

### 預先產出的 demo

`examples/sample_output.md` AI 完整報告,展示:
- BIC 正確選擇 k=3(BIC=4179 vs k=2 BIC=4527 vs k=4 BIC=4203)
- 3 客群:**早班通勤族**(7:33, NT$79) / **主婦學生中餐**(11:32, NT$144, 營收主力 58%) / **下午茶上班族**(15:35, NT$63)
- 為每客群設計具體促銷(早鳥套餐 / 中餐升級包 NT$30 / 下午茶第 2 杯半價 + 集點)
- 2 條整體洞察(穩固中餐核心、升級下午茶 segment)

`examples/sample_output_no_ai.md` 純函式模式輸出。

## 已驗證 smoke test

- ✅ 200 筆 sample 載入正確
- ✅ BIC 正確選 k=3(BIC=4180 < k=2 BIC=4527 < k=4 BIC=4203)
- ✅ EM 5 次 iter 內收斂
- ✅ Cluster recovery:detected μ_time (453, 693, 936) vs true (450, 690, 930),誤差 < 6 分鐘
- ✅ Hard assignment 還原 60/60/80 樣本數(誤差 < 5)
- ✅ log_sum_exp 數值穩定(處理 -1000 量級無溢位)
- ✅ Gaussian PDF 中心 max
- ✅ Quantile-based init → deterministic(同 input 跑 N 次結果一致)
- ✅ Empty records 不 crash
- ✅ Profile 按 mu_time 排序

## 專案結構

```
daypart/
├── README.md
├── daypart.py             # CLI(讀 CSV + EM + LLM 行銷顧問)
├── mixture.py             # 100% 純函式 2D Gaussian Mixture EM
├── samples/
│   └── transactions.csv   # 200 筆合成(早班 60 + 中餐 80 + 下午茶 60)
├── examples/
│   ├── sample_output.md          # AI 完整報告(客群命名 + 促銷)
│   └── sample_output_no_ai.md    # 純函式模式
└── requirements.txt
```

純函式部分零外部依賴(stdlib 只用 math + statistics + dataclass + csv)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **接 POS API**:iCHEF / 沛點 / Cashier / Coffee POS 自動拉每月 transactions
- **加 weekday × 時段 維度**:週末 vs 平日的客群可能不同(目前 weekday 欄位未啟用)
- **加 商品類別 維度**:把單品也分群(早餐 / 飲料 / 套餐)→ 客群 × 商品熱度矩陣
- **天氣 / 節慶 confounders**:雨天 / 颱風天 / 雙 11 的 cluster shift
- **多店比較**:5+ 店連鎖比較各店 cluster 異同
- **個人化推薦**:對每位回頭客 預測「他屬於哪 cluster」→ 推送對應促銷
- **AB 測試 cluster 級別**:做完促銷後比較目標 cluster 反應
- **LINE Bot 月度推播**:月初推當月分群結果 + 建議

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 1 次 / ≤ 100 transactions | 試用 |
| **Solo** | **NT$399 / 月** | 單店餐飲 / 飲料 / 早午餐 |
| **Pro** | NT$999 / 月 | 3-5 店連鎖 / 加 weekday + 商品維度 |
| **Studio** | NT$2,999 / 月 | 5-20 店連鎖 + 多店比較 + 月度 LINE 推播 |
| **Enterprise** | NT$9,999 / 月 | 20+ 店 + POS API + 個人化推薦 |
| **B2B 行銷顧問** | NT$30K+ / 月 | 餐飲顧問公司 white-label |

### WTP 計算

- 行銷顧問做一次分群 NT$30-50K vs Solo NT$399/月 = **75-125x 便宜**
- 一次成功的時段促銷帶來月 +NT$5-10K(下午茶第 2 杯半價案例)vs Solo NT$399 = **12-25x ROI**
- 5 店連鎖 Pro NT$999 = 每店 NT$200/月 → 比顧問報告 NT$5-10K/月便宜 25-50x

### TAM

- 台灣餐飲業 ~17 萬 + 飲料店 ~2.5 萬 + 早午餐 ~2 萬 = 21.5 萬家
- 取 1% 滲透 = 2,150 家 × NT$399 = **月 NT$86 萬 MRR / 年 NT$1,030 萬 ARR**
- 加 Pro + Studio + Enterprise 連鎖 → 年 ARR **NT$3,000-6,000 萬**
- 橫移日韓港新東南亞 → 翻倍

## 早期 distribution

1. **FB 餐飲老闆社群**(「台灣餐飲業老闆交流」5-10 萬人)— 痛點來源
2. **PTT restaurant / Dcard 餐飲業** — 老闆集中
3. **iCHEF / 沛點 / Cashier POS integration partner** — 直接接 SDK
4. **餐飲展 / 烘焙展 / 連鎖加盟展** demo
5. **YouTube 餐飲 KOL**(餐廳廚房 / 老饕 / 經營顧問)合作 case study
6. **餐飲業顧問公司 partner**(欣傳媒 / 餐飲業趨勢)— white-label
7. **iCHEF App Store** integration(若有開放)
8. **早午餐 / 咖啡店 LINE 老闆群** — 在地化推廣

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **EM 對極小樣本(< 50)不穩定** | 中-高 | UI 警告 < 100 transactions 不可靠;Solo 版要求 ≥ 200 |
| **客群解讀過度自信** | 高 | 報告強調「Cluster 假設僅統計分布」+ 「不取代實際客戶訪談」 |
| **POS 整合困難** | 中 | 第 1 階段 CSV 上傳;後期接 iCHEF API |
| **促銷誤導(促銷錯客群)** | 中 | 促銷建議標明「實際效果需 A/B 測試確認」 |
| **連鎖店 POS 不一致** | 中 | Pro 版加 schema mapping 工具 |
| **個資 / 客戶資料隱私** | 中 | transaction 不含客戶 ID(匿名);企業版 self-host |
| **大型廠商(iCHEF / 沛點)自己做** | 中 | iCHEF 偏 POS 操作不擅統計;走 partner 路線 |

---

*第三十四輪在 2026-05-11 產出於 incubator(台灣優先,**第二十四個 AI 架構模式 — Mixture Models / EM Algorithm**)。跟前 33 輪所有 pattern 都不同架構。*
