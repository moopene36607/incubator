# retiremate(退休伴侶)

**台灣 50-60 歲族群退休規劃 AI 顧問 — 中立、不收佣金、不推銷投資商品。**

LLM 用 Anthropic tool-use API 自主決定何時調用哪個純函式 tool(勞退新制 / 勞保 / 國保 / 個人儲蓄 / 月支出 / 健保 / 缺口分析 / 補足儲蓄),最後組合成完整退休規劃報告。

把「快退休了不知該不該擔心、各家銀行業務員都要賣保單」變成「30 秒看到自己 65 歲的所得、支出、缺口、可動用儲蓄」。

---

## 痛點

台灣已進入超高齡社會,**50-60 歲族群超過 600 萬人**,每月 ~10 萬人退休。但退休規劃工具現況極差:

> **「年金改革吵了 10 年我還是看不懂我退休後一個月領多少。」** — 55 歲新北上班族,FB 退休理財社團

> **「跑去問銀行,理專一直推終身險,我只是想知道我夠不夠退休。」** — Dcard 25-up 板

> **「勞動部勞退試算頁面像 2005 年的網站,跟勞保試算又是另一頁要重填。」** — PTT Salary

具體痛點:

- 勞退新制 + 勞保老年年金 + 國民年金 + 個人儲蓄 + 健保 — **5 個獨立系統,沒有整合工具**
- 勞動部勞工保險局網站介面糟,**單獨試算可以但無法整合**
- 銀行 robo-advisor 偏「銷售投資 / 保險商品」(球員兼裁判),客戶不信任
- 律師 / 會計師諮詢 NT$3-5K/次 且不專精退休規劃
- 獨立財務規劃師 (CFP) 在台灣稀有,且收費高 NT$10-30K/次
- ChatGPT 直接問會幻覺(編造勞退公式 / 弄錯月投保薪資上限)
- 50-60 歲族群通常**第一次認真想退休**,沒系統工具的協助難以決策(延後 1 年退休? 多存 5 千? 自願提繳 6%?)

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **勞動部勞退試算 / 勞保試算** | 單獨試算可以;**沒整合**勞退 + 勞保 + 國保 + 個人儲蓄 + 健保;UI 是 2005 年水準 |
| **銀行 robo-advisor / 理專** | 球員兼裁判,推銷導向;不算社會保險月領 |
| **獨立財務規劃師 (CFP)** | 稀有 + 一次 NT$10-30K |
| **ChatGPT / Claude / Gemini 直接問** | 容易幻覺(編造公式或老資料);無 tool 連 + 無法 deterministic 計算 |
| **保險業務員「退休計畫」** | 主要在賣保單,non-生活費 / 健保等具體現金流不算 |
| **Excel 自己算** | 公式繁雜(複利 + 年金 + cap)+ 法規一改就要重新查 |

**Gap 結構性**:5 個系統的合一試算需要多 tool 整合 + 中立第三方立場 + 易用介面 — 銀行不做(會壓縮自己銷售空間)、政府不做(各部會不整合)、CFP 不做(產業太分散)。Google 搜尋「台灣 退休規劃 整合 試算」零中立 SaaS。

## retiremate 在做什麼

```
用戶 profile JSON (年齡 / 月薪 / 勞退年資 / 勞保年資 / 國保年資 /
                  自有儲蓄 / 月儲蓄 / 居住地 / 家庭結構 / 目標退休年齡)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude(tool-use API)自主決定調用順序:                    │
  │   1. estimate_labor_pension_new                            │
  │   2. estimate_labor_insurance_pension                      │
  │   3. estimate_national_pension(若有國保年資)              │
  │   4. project_personal_savings                              │
  │   5. estimate_monthly_living_cost                          │
  │   6. estimate_post_retirement_nhi                          │
  │   7. compute_retirement_gap                                │
  │   8. required_savings_for_gap                              │
  │ 純函式精算(tools.py)— LLM 永不算 NT$                      │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
        Claude 組合報告:
          - 執行摘要(2-3 句)
          - 各項所得來源(逐項月領 NT$)
          - 月支出 + 健保 + 缺口分析(等級分檔)
          - 儲蓄成長預測 vs 需要儲蓄(自有錢能否補足)
          - 3-5 條具體建議(嚴禁推銷保險 / 投資商品)
          - 重要提醒 + 對照官方試算系統 URL
```

3 個關鍵架構決策:

1. **多 tool 整合 + LLM 自主規劃**:5 個獨立社會保險系統 + 個人儲蓄 + 月支出 + 健保需要 8 個 tool 串連調用。LLM 看到 profile → 決定用哪些 tool + 用什麼參數 → 收到結果 → 決定下一步。這就是 standard "agent with tools" pattern。
2. **數字 100% 純函式,LLM 永不算錢**:勞退複利 / 勞保新式 vs 舊式擇優 / 國民年金 A 式 vs B 式擇優 / 個人儲蓄三情境(3% / 5% / 7%)/ 缺口分檔(OK / MINOR / MEDIUM / SEVERE)— 全部在 `tools.py` 純函式;LLM 收到 tool result 後**直接引用數字**,絕不重算。
3. **中立第三方立場**:System prompt 嚴禁推銷特定保險 / 投資商品;建議都是「自願提繳 6% 節稅」/「延後 1-2 年退休的影響」/「勞保展延請領 +4%」這類**政策可動的 lever**,以及 0050 / 006208 等大盤 ETF(全網查得到、無業務員介紹費)。

## 動作

### 確定性試算(免 API key)

```bash
python3 retiremate.py samples/profile.json --no-ai --out output.md
```

`samples/profile.json` 是 55 歲雙北上班族(月薪 75K / 勞退 22 年 / 勞保 30 年 / 儲蓄 350 萬 / 月存 2 萬)。輸出含 8 個 tool 的試算結果 + 缺口分析。

### Claude tool-use agent 模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 retiremate.py samples/profile.json --out output.md
```

Claude 會自主決定 tool 調用順序、組合最終報告。Tool 調用紀錄全部透明列出(讓使用者 / 審計者可重現)。

### 預先產出的 demo

`examples/sample_output.md` 是完整 AI 模式報告,展示 Claude 自主用 8 個 tool 計算後寫的報告 + Top 4 具體可執行建議 + 完整 tool log 透明化。

`examples/sample_output_no_ai.md` 是純函式模式輸出,證明免 API key 也能用。

## 已驗證 smoke test

- ✅ 預設 profile (55 歲雙北上班族) → 月所得 NT$27,894,月缺口 NT$32,992,SEVERE_GAP,但儲蓄能補
- ✅ 勞保 < 15 年 → eligible_for_monthly=False, selected_monthly_pension=0
- ✅ 勞退新制 < 15 年 → can_monthly_payout=False, estimated_monthly_pension=0
- ✅ 月薪 > 150,000 → 自動 cap 至最高提繳工資 150,000
- ✅ 投保薪資 > 45,800 → 自動 cap 至 2024 上限 45,800
- ✅ Gap 等級分檔(OK / MINOR / MEDIUM / SEVERE)邊界正確
- ✅ Tool dispatcher 收到錯誤 args → 回 error 不 crash
- ✅ project_personal_savings 三情境(3% / 5% / 7%)合理
- ✅ 國保 0 年仍回 A 式基本保證 NT$4,049

## 專案結構

```
retiremate/
├── README.md
├── retiremate.py        # CLI(讀 profile + 純函式模擬 / Claude tool-use agent)
├── tools.py             # 100% 純函式:8 個退休規劃 tool + TOOL_DEFINITIONS schema
├── samples/
│   └── profile.json     # 55 歲雙北上班族範例
├── examples/
│   ├── sample_output.md          # AI mode 完整報告 + tool log
│   └── sample_output_no_ai.md    # 純函式試算
└── requirements.txt
```

純函式部分零外部依賴(stdlib only)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **接勞動部 API**:用戶授權 → 自動拉「勞工保險局個人專戶」資料,免手動填年資
- **每年 4 月 / 1 月自動更新公告值**:勞工保險局每年調整投保薪資上限 / 國民年金月投保金額 / 健保費等
- **動態通膨調整**:選 2% / 2.5% / 3% 通膨情境,5 / 10 / 20 年後實質購買力
- **延後退休 sensitivity 分析**:64-70 歲各延後 1 年的整體影響(目前是 LLM 推算)
- **配偶合併規劃**:夫妻雙方數字合併、家庭層級看缺口
- **健康老化情境**:80 歲後可能需 NT$30K+/月的長照費,加進缺口分析
- **遺產 / 繼承基本規劃**:結合贈與稅 / 遺產稅試算
- **conversational UI**:LINE Bot 用對話介面引導 50-60 歲使用者填 profile
- **CFP 顧問轉介**:retiremate 給初步試算 → 嚴重缺口轉介 CFP 收 introduction fee

## 商業模式

| 方案 | 月費 / 單次費 | 對象 |
|------|--------------|------|
| **Free** | 1 次完整試算 | 試用 |
| **Solo** | **NT$199 / 月** | 個人會員,每月可重新試算 + 通膨 / 延後退休模擬 |
| **Pro** | NT$499 / 月 | 加配偶合併規劃 + LINE Bot 提醒 + 月變化追蹤 |
| **Pay-per-use** | NT$499 / 次 | 不訂閱單次完整試算 + AI 顧問建議 |
| **B2B 銀行** | 客製 NT$50K-200K/月 | 銀行 / 投信 / 證券買來給高端客戶用,但客戶看到的是 retiremate 中立品牌(企業白標) |
| **B2B 政府 / 公益** | 免費(政府買單) | 縣市政府退休服務站 / 勞工教育中心 / 銀髮 NPO |

### WTP 計算

- CFP 諮詢一次 NT$10-30K vs retiremate Solo NT$199/月 = **50-150x 便宜**
- 一個延後退休決策對退休生活年期的影響可達 NT$50-150 萬;一次自願提繳 6% 啟動 10 年後省 NT$60 萬
- B2B 銀行客戶 retention:50+ 歲高資產客戶,單次方案 NT$50K-200K/月,銀行如能因此 retain 1 個 NT$1000 萬資產的客戶就回本

### TAM

- 50-60 歲族群 600 萬人,55-60 歲(退休前 5 年)約 200 萬最關鍵
- 取 1% 滲透 = 2 萬人 × NT$199 = **月 NT$400 萬 MRR / 年 NT$4,800 萬 ARR**
- 加 Pro + Pay-per-use + B2B 銀行(預估 5-10 家簽約)→ 年 ARR NT$1-2 億
- 横移到 60-70 歲已退休族群(退休後規劃 / 用藥 / 醫療 / 長照)→ TAM 翻倍

## 早期 distribution

1. **退休前公務員 / 軍教 / 國營事業員工社團**(政府機關退休前 1-2 年規劃需求最強)
2. **企業 HR 員工福利**(50+ 員工 retain 工具,大型企業可能買單做員工退休教育)
3. **FB 退休理財 / 退休生活 社團**(「樂齡生活」「中年理財」5-15 萬人)
4. **PTT Salary / 中年板 / Bz** — 退休規劃文章下方 demo
5. **Threads 中年理財 KOL / Podcaster**(夏韻芬 / 雷皓明 等)合作
6. **退休理財 podcast / YouTube** — 邀請 CFP / 律師上節目展示 retiremate 用法
7. **勞動部 / 勞保局 / 國民年金 partner** — 政府部會宣導合作
8. **第二人生 / 退休學校 / 樂齡學習中心** — 中央 / 縣市政府銀髮機構合作

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **法規 / 公告值改變** | 中 | tools.py 常數獨立區塊,每年 4 月 / 1 月可定期 review;自動 alert |
| **退休規劃結果讓使用者沮喪** | 中 | UI / 報告語氣積極 + 強調 4 個可動 lever;嚴重缺口轉介 CFP |
| **保險業 / 銀行業 反感** | 中 | retiremate 不取代他們,而是「客戶到他們之前的中立試算」;可走 partner 路線 |
| **個人試算個資 / 隱私** | 高 | stateless API call;profile 不上雲;企業版可走 self-host LLM |
| **試算結果與勞保局實際差異** | 中 | 多處 disclaimer 強調「初步試算」+ 對照官方 URL;準確度只到 ±10% |
| **使用者高估個人儲蓄報酬** | 中 | 預設「平均 (5%)」是中位數;同時呈現保守 (3%) / 積極 (7%) 三情境;不偏頗任何一個 |
| **CFP / 理財規劃師反彈** | 低 | 反而是補強他們:retiremate 做完初步試算後再找 CFP 深入規劃,合作關係而非競爭 |

---

*第二十五輪在 2026-05-10 產出於 incubator(台灣優先,**第十五個 AI 架構模式 — Conversational Agent with Tools**)。跟前 24 輪 doc-gen / pricing / OCR-aggregation / RAG / scheduling+LINE / matching / monitoring+alerting / churn / vision-pricing / vision-classification / personalization / time-series-anomaly / stylometric-matching / structured-extraction 都不同架構。*
