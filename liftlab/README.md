# liftlab(因果效應實驗室)

**台灣 SME 行銷投放真實因果 ROI 評估 — 用 Pearl backdoor adjustment 從廣告 vs 季節 / 節慶 / 新品的 confounders 中切出純廣告因果效應。**

把「**我這個月投了 NT$80K 廣告,營收多賺 NT$190K,ROI 2.4x!**」修正成「**廣告真實貢獻 NT$83K,另外 NT$107K 是旺季 + 雙 11 + 新品本來就會帶來的,真實 ROI 1.05x → 毛利 30% 後淨 ROI 只有 0.32x**」。

---

## 痛點

5-30 人 SME 每月投 NT$30K-200K 廣告(IG / FB / Google),**最痛的問題是「真的有用嗎?」**:

> **「我這 6 個月每月投 5 萬廣告,營收成長 30%,看起來廣告很有用。但停廣告 1 個月測試,營收只跌 10%。誰才是對的?」** — Dcard 創業板

> **「廣告代理商給我看 ROAS 7x 的報告,但我自己算月底剩多少現金,根本沒多賺。」** — FB 中小企業老闆

> **「Google Analytics 給我 attribution,但它不會跟我說『其中多少是季節?』」** — PTT marketing

具體痛點:

- 老闆用 **naive ROI = (高 ads 月 - 低 ads 月) / 廣告費** 算,**完全忽略 confounders**
- 老闆通常把廣告**剛好投在旺季 / 大檔 / 新品月** → 那些月份本來就會多賺
- **這種 selection bias 會把廣告效應高估 2-3 倍**
- Google Analytics / Mixpanel **提供 attribution 但不做因果調整**
- HubSpot / Salesforce 看 lead 但不做 backdoor adjustment
- 行銷代理商提供 ROAS 報告但**有意 / 無意忽略 confounders**(他們希望你續約)
- 學術界 Pearl 因果推斷 1995 年就有,但**沒有人做成 SME 老闆可用的 SaaS**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **Google Analytics / Mixpanel** | 提供 last-click attribution **不做因果調整**;旺季多投廣告就以為廣告有效 |
| **HubSpot / Salesforce attribution** | Lead-based 而非 revenue-based;不控制 confounders |
| **行銷代理商月度報告** | **有利益衝突**(要你續約)— 通常用 ROAS 偏 naive |
| **Excel 自己算** | Pearl backdoor adjustment 公式繁雜;老闆完全沒統計背景 |
| **R / Python causal-inference 套件**(DoWhy / CausalNex) | 完全給研究員用;**老闆看不懂 DAG** |
| **學術論文 / 顧問報告** | 一次 NT$30-100K;只做一次性分析,不是 SaaS |
| **ChatGPT / Claude 直接問** | 不能跑 stratified ATE;每次重貼資料 |

**Gap 結構性**:Pearl 因果推斷在學術界成熟 30 年,但**沒有人把 backdoor adjustment 做成老闆可用的 SaaS**。Google「台灣 行銷 因果 ROI」零中文 SaaS 結果。

## liftlab 在做什麼

```
24+ 個月行銷 + 營收 CSV
  (month, ad_spend_ntd, revenue_ntd, is_peak_season,
   is_holiday_promo, launched_new_product)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式 compute_naive_ate (causal.py):                     │
  │   ATE_naive = E[Y | T=1] - E[Y | T=0]                      │
  │   = 高 ads 月平均營收 - 低 ads 月平均營收                   │
  │   (老闆通常的看法,**包含 confounder bias**)                │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式 compute_backdoor_adjusted_ate (Pearl 1995):        │
  │   DAG 假設:                                               │
  │     旺季 ─┐                                               │
  │     節慶 ─┼─> ad_spend ──> revenue                         │
  │     新品 ─┘            └──> revenue (直接)                 │
  │     旺季 / 節慶 / 新品 ───────────> revenue (confounder paths) │
  │                                                            │
  │   adjustment:Σ_z [E[Y|T=1,Z=z] - E[Y|T=0,Z=z]] × P(Z=z)   │
  │   把資料按 (peak, holiday, new) 分 8 個 strata,            │
  │   在每個 stratum 內計算 ATE,再加權平均                     │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式 compute_confounder_bias:                            │
  │   對每個 confounder Z:                                     │
  │     bias_Z ≈ (P(Z=1|T=1) - P(Z=1|T=0)) × (E[Y|Z=1] - E[Y|Z=0]) │
  │   拆解 naive ATE - adjusted ATE 由哪個 confounder 貢獻      │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude 寫:                                                │
  │   - Executive Summary(200 字故事化解釋為什麼真實 ROI 跟你想的不同)│
  │   - Confounder 翻譯(把「is_peak_season bias +NT$109K」翻成「旺季本身會自帶 NT$120K 營收」)│
  │   - 真實 ROI 計算(adjusted ATE / avg ad spend × 毛利率)    │
  │   - 4-5 條 action items(維持 / 加碼 / 砍 / 換 channel)    │
  │   - 警示 caveats(只控制 3 個 confounders 等)              │
  │ **LLM 永不算 NT$ / ATE**                                   │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **Backdoor adjustment 而非簡單 attribution**:Google Analytics 給的 last-click attribution 完全沒控制 confounders;**stratified backdoor 才能切出真實因果效應**。
2. **數字 100% 純函式**:naive ATE / adjusted ATE / strata weights / confounder bias 全在 `causal.py`;LLM 永不算機率或 NT$。
3. **誠實面對 caveats**:本工具僅控制 3 個 confounders(旺季 / 節慶 / 新品),真實世界還有(對手活動 / 經濟景氣 / 天氣)未抓進來。報告底部明確告訴老闆**這是「**比 naive 好的近似**」而非絕對真相**。

## 動作

### 純函式因果分析(免 API key)

```bash
python3 liftlab.py samples/marketing_history.csv --no-ai --out output.md
```

`samples/marketing_history.csv` 是 24 個月合成資料,**真實設計**的因果效應是 NT$80K/月,但 selection bias 把 naive ATE 推到 NT$190K。

輸出含 naive vs adjusted 對照 + 各 stratum 細節 + confounder bias 拆解。

### 完整 AI 行銷顧問模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 liftlab.py samples/marketing_history.csv --out output.md
```

加上 Claude 寫故事化 executive summary + confounder 翻譯 + 真實 ROI 計算 + 4-5 條 action items + caveats。

### 預先產出的 demo

`examples/sample_output.md` AI 完整報告,展示:
- Naive NT$190K vs Adjusted NT$83K(2.3x inflation)
- 旺季貢獻 NT$109K bias / 節慶貢獻 NT$73K bias
- 真實 ROI 1.05x → 毛利 30% 後淨 ROI 0.32x
- 5 條 action items 含「不要因 naive ATE 看高就加碼」「Stratified A/B 測試」「拆 channel 因果分析」

`examples/sample_output_no_ai.md` 純函式模式,證明免 API key 也能用。

## 已驗證 smoke test

- ✅ Treatment threshold(NT$30K)邊界正確
- ✅ 預設 sample → naive NT$190K, adjusted NT$83K, inflation 2.28x(設計值 80K 驗證精準)
- ✅ 空資料 → 0 不 crash
- ✅ 全部 treated 無 control → naive ATE = 0
- ✅ 隨機指派(無 confounding) → naive ≈ adjusted ≈ 80K(設計真值)
- ✅ 純函式 deterministic
- ✅ Strata weights 加總 = 1.0
- ✅ Bias decomposition 找出 peak_season 為最大 bias 來源

## 專案結構

```
liftlab/
├── README.md
├── liftlab.py             # CLI(讀 CSV + 純函式 causal + LLM 解釋)
├── causal.py              # 100% 純函式:Pearl backdoor adjustment
├── samples/
│   └── marketing_history.csv   # 24 月合成資料(true ATE 80K, naive 190K)
├── examples/
│   ├── sample_output.md          # AI 完整報告
│   └── sample_output_no_ai.md    # 純函式模式
└── requirements.txt
```

純函式部分零外部依賴(stdlib 只用 statistics + dataclass + itertools)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **接 Google Ads / Meta Ads API**:自動拉每日 ad spend / impressions / clicks
- **接會計軟體 API(Sage / Xero / 工研院 EZ 帳)**:自動拉每月營收
- **更多 confounders**:對手活動(從 Google Trends + 對手社群)、經濟景氣、天氣(中央氣象局 API)、媒體報導
- **Channel 拆解**:Google / FB / IG / TikTok / KOL 分別跑因果
- **連續 treatment**:目前 binary high/low,真實 ad spend 是連續變數
- **Sensitivity analysis**:Pearl 教科書的 E-value;告訴老闆「要有多大 unmeasured confounder 才會推翻結論」
- **Difference-in-differences**:當有 quasi-experiment 機會(e.g., 對手暫停廣告)
- **Bayesian 不確定性**:給 ATE 信賴區間(目前是 point estimate)
- **LINE Bot 月度報告**:每月初推 active learning 更新 + 警示

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 1 次 14 月以下分析 | 試用 |
| **Solo** | **NT$499 / 月** | 1-5 人 SME,3 channel + 24-48 月分析 |
| **Pro** | NT$1,499 / 月 | 5-30 人 SME,多 channel + sensitivity + LINE 推播 |
| **Enterprise** | NT$4,999 / 月 | 30+ 人 + Google Ads / Meta Ads API 整合 |
| **B2B 行銷代理商** | NT$8,000 / 月 | 代理商 white-label 給客戶月報 |
| **B2B 顧問** | 客製 NT$30K+/月 | 行銷顧問公司用因果分析做 case |

### WTP 計算

- 行銷顧問做一次因果分析 NT$30-100K vs liftlab Pro NT$1,499/月 = **20-66x 便宜**
- 老闆過去以為廣告貢獻 NT$190K → 加碼到 NT$120K/月廣告;**liftlab 揭示真實 ROI 1.05x** → 老闆**省下 NT$ 40K/月浪費的廣告 budget** → 一個月就回本 27x
- B2B 代理商 NT$8K/月 給 30 個客戶 + 自動月報 = 每客戶成本 NT$267 → 代理商收 NT$2-5K/月很划算

### TAM

- 台灣 SME 約 150 萬家,5-30 人投廣告的核心 SME 約 5 萬家
- 取 1% 滲透 = 500 家 × NT$1,499 = **月 NT$75 萬 MRR / 年 NT$900 萬 ARR**
- 加 Enterprise + B2B 代理商(預估 50 家)+ 顧問 → 年 ARR NT$2,000-4,000 萬
- 横移日韓港新 → 翻倍

## 早期 distribution

1. **FB 中小企業老闆社群** — 痛點來源 + 種子
2. **PTT marketing / Soft_Job / SOHO** — SME 行銷集中
3. **Threads / IG 中小企業 KOL**(姚仁祿 / 葉啟政)合作 case study
4. **行銷代理商 partner**(凱絡 / Foundry / 數位時代)— B2B white-label
5. **數位時代 / Inside / 經理人雜誌** 內容合作 — 用 case study 文章
6. **Google Ads / Meta 廣告主訓練課程** partner — 大型 customer base
7. **創業育成中心 / 商總 / 商工會議所**

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **資料品質 / Confounder 遺漏** | **極高** | 報告底部多次強調「只控制 N 個 confounders」+ Pro 版加 E-value sensitivity 分析 |
| **行銷代理商反感(會少接案)** | 高 | 走 partner 路線 white-label;讓他們交付的報告更專業(誠實 ROI)反而續約率提升 |
| **老闆看不懂 "ATE" / "backdoor"** | 高 | UI 完全避免術語;用「真實多賺」「廣告 vs 季節分開算」這種日常語言 |
| **小樣本(< 24 月)結果不穩定** | 高 | 程式檢查 + 顯示警告;Solo 版要求 ≥ 24 月才能跑 |
| **個資 / 公司財務隱私** | 高 | stateless;CSV 不上雲;企業版 self-host LLM |
| **競爭(Mixpanel / Amplitude 自己做 causal)** | 中 | 在地化(中文 + 台灣 holiday calendar)+ SME 客單低銷售壓力大廠不易 |

---

*第三十二輪在 2026-05-10 產出於 incubator(台灣優先,**第二十二個 AI 架構模式 — Causal Inference / Pearl do-calculus**)。跟前 31 輪所有 pattern 都不同架構。*
