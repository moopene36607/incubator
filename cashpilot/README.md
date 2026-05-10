# cashpilot(現金駕駛員)

**台灣中小企業現金流 Monte-Carlo 風險試算 — 純函式跑 2000 次模擬,LLM 寫人話建議。**

老闆把公司財務 profile 輸入(起始現金、月營收、應收天數、固定 / 變動成本、大客戶倒帳機率、可選的「接大單」情境)→ cashpilot 跑 2000 次 12 月模擬 → 給出「現金破洞機率」+ P10/P50/P90 餘額 + 接大單決策建議。

把「直覺判斷接不接得起這個 200 萬大單」變成「**2000 個模擬世界裡有 9.8% 你會撐不住,但加 3 件事(拆款 / 信用額度 / 砍變動成本)可以降到 3%**」。

---

## 痛點

台灣中小企業約 **150 萬家**(中小企業白皮書),其中 5-30 人規模佔 70%+。老闆**最焦慮的問題從來不是「夠不夠賺」而是「下個月發得出薪水嗎」**:

> **「接到上市公司大單,200 萬,90 天票期 — 接還是不接?問會計師她說『這要看現金流』,她又不算給我看,只給我看歷史 P&L。」** — 5 人軟體外包公司老闆,FB 中小企業老闆社團

> **「明明 P&L 賺錢但每個月底發薪水都心臟亂跳,因為錢都卡在應收。」** — PTT Salary

> **「想找會計師做 cash flow projection,他開價 30 萬說要做 3 個月。但我只是想知道接不接得起這單。」** — Dcard 創業板

具體痛點:

- 5-30 人 SME 老闆**自己沒財務專業**,會計師看「歷史 P&L」**不做前瞻 cash flow simulation**
- 接大單票期 60-120 天,**短期現金壓力 vs 長期利潤**權衡沒工具
- 應收回收延遲、大客戶倒帳、變動成本波動 — 這些**機率事件**老闆自己沒辦法估計
- 銀行貸款專員幫忙評估時偏「線性 best case」,**沒模擬尾端風險**
- 倒帳發生時通常已經來不及 — **70% 中小企業倒閉是「現金流問題」**,不是「不賺錢」
- **沒人做中文 Monte-Carlo cash flow tool** — 海外的 Float / FreeAgent / Pulse 都是英文 + 設定複雜

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **Xero / QuickBooks** | 有 cash flow 報告但**簡單線性預估**,沒做不確定性 Monte-Carlo;偏歐美中小企業 |
| **Float / Pulse / Cashflow Frog** | 海外英文 SaaS,**完全不認識台灣**(銀行 / 票期 / 商業慣例) |
| **iCHEF / 沛點 / Cashier** | 是 POS / 開票,**完全沒 cash flow projection** |
| **會計師事務所** | **看過去 P&L 不做前瞻**;客製 cash flow 報告 NT$5-30 萬一份且耗時 1-3 個月 |
| **銀行貸款專員** | 偏「線性 best case」做信用評估;**無 Monte-Carlo 尾端風險**;且要先取得銀行關係 |
| **Excel 自己做** | Monte-Carlo 模型門檻太高;DAX / VBA 寫一個 simulation 老闆做不到 |
| **ChatGPT 直接問** | 不能跑模擬只能講概念;每次數字會幻覺 |

**Gap 結構性**:中小企業老闆需要快速、輕量、中文、本地化的現金流壓力測試 — 大型會計事務所 / 銀行做不到輕量、海外 SaaS 不在地化、Excel 太複雜。Google 搜尋「台灣 中小企業 現金流 模擬」零中文 SaaS 結果。

## cashpilot 在做什麼

```
公司 profile JSON
(起始現金 / 月營收均值+std / 固定成本 / 變動成本比 /
 應收平均天數+std / 大客戶倒帳機率 / 可選:大單情境)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ simulator.py 純函式 Monte-Carlo(2000 次,seed=42):       │
  │   每次模擬 12 個月 → 抽:                                  │
  │     - 月營收 ~ Normal(μ, σ)                               │
  │     - 應收回收延遲 ~ Normal(60 days ± 15)                 │
  │     - 大客戶倒帳事件 ~ Bernoulli(monthly_prob)            │
  │     - 變動成本 = 營收 × ratio                              │
  │   每月計算 cash = prev_cash + collected - expense          │
  │ **LLM 永不算機率 / NT$**                                   │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式統計:                                               │
  │   - prob_cash_negative_any_month(主指標)                  │
  │   - P10 / P50 / P90 最低餘額 + 年底餘額                    │
  │   - 逐月累積破洞機率(看哪幾月最危險)                       │
  │   - 最壞月份分布(哪個月最容易出問題)                       │
  │ classify_risk → LOW / MEDIUM / HIGH / **CRITICAL**         │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 若 profile 含 big_deal_amount > 0:                       │
  │   再跑一次「接大單後」Monte-Carlo                          │
  │   compare_scenarios → 接 vs 不接 對 cash 的差異            │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude 寫:                                                │
  │   - baseline 解釋(< 100 字)                              │
  │   - 大單決策(推薦 / 條件式推薦 / 不推薦 + 理由)            │
  │   - 3-5 條具體可執行建議(應收 / 信用額度 / 變動成本)        │
  │   - 警覺訊號(未來 3 月若看到 X → 採取 Y)                  │
  │ **嚴禁推銷特定銀行 / 保險 / SaaS 商品**                     │
  │ **不建議 IPO / VC 募資**(中小企業可立即執行的事)           │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **Monte-Carlo 而非線性預估**:單一「最樂觀」/「最悲觀」估算對中小企業沒幫助;**真正有用的是「在 2000 個世界裡破洞機率是多少」**,並能看尾端風險(P10 最低餘額)。
2. **數字 100% 純函式**:模擬邏輯、機率、百分位數、風險等級全在 `simulator.py`;LLM 收到統計結果後**直接引用數字**,絕不重算。
3. **大單情境並排對照**:不是「接 vs 不接」二選一,而是**量化 3 件配套措施(拆款 / 信用額度 / 砍變動成本)能把 9.8% → 3%**,讓老闆做 informed decision。

## 動作

### 純函式 Monte-Carlo(免 API key)

```bash
python3 cashpilot.py samples/profile.json --no-ai --out output.md
```

`samples/profile.json` 是 8 人軟體外包公司,起始現金 NT$180 萬 + 接 NT$200 萬大單 90 天票期。輸出含 baseline (LOW 3.5%) + 接大單後 (MEDIUM 9.8%) + 對照差異。

### 加 AI 顧問(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 cashpilot.py samples/profile.json --out output.md
```

Claude 會解釋 baseline 風險、給接大單決策建議、列 3-5 條具體行動方案 + 警覺訊號。

### 預先產出的 demo

`examples/sample_output.md` 是完整 AI 模式報告,展示「LOW → MEDIUM 風險升級」+「條件式推薦接大單(拆款 / 信用額度 / 砍變動成本 3 件配套)」+ 具體行動建議。

`examples/sample_output_no_ai.md` 是純函式模式輸出 — 證明免 API key 也能用,且模擬結果完全 deterministic。

## 已驗證 smoke test

- ✅ 預設 sample (NT$180 萬起始 + NT$200 萬 90 天大單) → baseline LOW (3.5%) → 接大單 MEDIUM (9.8%)
- ✅ Healthy profile (高現金 + 短應收 + 低變動) → LOW
- ✅ Sick profile (低現金 + 長應收 + 高變動) → CRITICAL (100%)
- ✅ 確定性:同 seed 跑 N 次結果一致
- ✅ prob_cash_negative_by_month 月遞增單調
- ✅ P10 ≤ P50 ≤ P90 percentile 順序正確
- ✅ 大單增加 avg_end_cash(長期 +NT$170 萬)同時增加短期破洞風險
- ✅ 應收天數加長(30 → 90 天)→ 破洞機率增加
- ✅ 純函式 deterministic 可審計

## 專案結構

```
cashpilot/
├── README.md
├── cashpilot.py        # CLI(讀 profile + 跑模擬 + 渲染報告)
├── simulator.py        # 100% 純函式 Monte-Carlo + classify_risk + compare_scenarios
├── samples/
│   └── profile.json    # 8 人軟體外包公司 + NT$200 萬大單 90 天票期
├── examples/
│   ├── sample_output.md          # AI 模式完整報告
│   └── sample_output_no_ai.md    # 純函式模式報告(完整模擬統計表)
└── requirements.txt
```

純函式部分零外部依賴(stdlib 只用 `random` + `statistics`)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **接會計軟體 API**:從 Sage / Xero / 工研院 EZ 帳直接拉去年 12 月 P&L → 自動推 profile,免手動填
- **Sensitivity dashboard**:拖拉 slider 看「應收延遲 +10 天會怎樣」「變動成本 +5% 會怎樣」
- **多情境並排對照**:同時跑 4 個情境(現狀 / 接大單 / 砍人 / 提價)看哪個風險最低
- **季節性 / 週期性**:目前假設月均一樣,實際零售 / B2B 有強烈季節性,加 monthly_revenue_seasonality multiplier
- **同業 benchmark**:把你的應收 60 天跟「軟體外包同業中位數 45 天」並列,鼓勵改進
- **LINE Bot 推播**:每月初自動跑,若 risk 升級 → 推播警示
- **連動信用額度申請**:接中信銀 / 兆豐 SME API,risk MEDIUM+ 直接提供申請連結

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 1 次 baseline 模擬 | 試用 |
| **Solo** | **NT$399 / 月** | 1-5 人公司,baseline + 情境對照,月跑 3 次 |
| **Pro** | NT$999 / 月 | 5-30 人公司,無限模擬 + LINE 警示 + 多情境並排 |
| **Enterprise** | NT$2,999 / 月 | 30+ 人公司,API + 會計軟體整合 + 月度報告 |
| **B2B 銀行 / 會計師** | 客製 NT$50K+/月 | 銀行幫客戶評信用、會計師事務所幫 SME 做 cash projection 工具 |

### WTP 計算

- 會計師客製 cash flow projection NT$5-30 萬 vs cashpilot Pro NT$999/月 = **5-30x 便宜 + 即時更新**
- 一次「接錯大單」現金破洞 = 員工延遲發薪 / 信用受損 = **損失難以估計**;NT$999/月 預防
- 銀行貸款專員若用 cashpilot 評估 SME 客戶信用,能更精準分配額度 → 銀行付得起 NT$50K+/月

### TAM

- 台灣 SME 約 150 萬家,5-30 人規模約 30 萬家
- 取 1% 滲透 = 3,000 家 × NT$999 = **月 NT$300 萬 MRR / 年 NT$3,600 萬 ARR**
- 加 Enterprise + B2B 銀行 / 會計師(預估 10 家) → 年 ARR NT$1-2 億
- 橫移日韓港新中小企業 → 翻倍

## 早期 distribution

1. **PTT Salary / 中小企業 / Bz 板** — 痛點來源 + 第一波種子(每週都有「接這單會不會死」貼文)
2. **FB 中小企業老闆社群**(「中小企業老闆交流」「創業老闆」5-10 萬人)
3. **記帳士 / 會計師事務所 partner** — 他們現有客戶想要 cash flow projection 但他們做不到輕量化,可 white-label
4. **中信銀 SME LOC / 兆豐 SME / 國泰世華 SME** partner — 銀行貸款專員用 cashpilot 評估客戶信用
5. **創業育成中心 / 中小企業協會 / 商總**
6. **YouTube / Threads 中小企業 KOL**(夏振邦 / 葉啟政 等)合作 case study
7. **中小企業財務 podcast** — 邀請會計師 / CFO 上節目 demo
8. **iCHEF / Cashier 等垂直 POS** integration partner — 已有 SME 客戶基礎

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **模型假設與實際公司不符** | 中-高 | UI 提示「請依貴公司實際情況微調 std」;Pro 版可上傳過去 12 月實際數字校準 |
| **老闆不會自己填 profile** | 高 | 早期 onboarding 含「我們幫你填」服務;接會計軟體 API 自動拉資料 |
| **Monte-Carlo 結果讓老闆過度恐慌** | 中 | UI / AI 顧問同時強調「baseline LOW 表示體質健康」;不只看 prob_neg 也看 P50 餘額 |
| **銀行 / 會計師反感(被搶飯碗)** | 中 | 走 partner 路線(B2B 銀行 / 會計師 white-label)而非競爭 |
| **個資 / 公司財務隱私** | 高 | stateless API call;profile 不上雲;企業版 self-host LLM |
| **Excel / 國產 SaaS 進入此市場** | 低 | 結構性差異(中文 + Monte-Carlo + 在地建議);多年才有對手 |

---

*第二十六輪在 2026-05-10 產出於 incubator(台灣優先,**第十六個 AI 架構模式 — Simulation / Monte-Carlo**)。跟前 25 輪 doc-gen / pricing / OCR-aggregation / RAG / scheduling+LINE / matching / monitoring+alerting / churn / vision-pricing / vision-classification / personalization / time-series-anomaly / stylometric-matching / structured-extraction / conversational-agent-with-tools 都不同架構。*
