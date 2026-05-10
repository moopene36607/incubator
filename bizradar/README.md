# bizradar(商業雷達)

**台灣中小企業客戶 / 廠商風險評估 — SME 版 D&B,從公開資料建構企業關係圖。**

從目標公司的董監事網路、共用地址、訴訟紀錄、新聞負評 → 純函式 graph 分析算 risk_score → LLM 寫故事化解釋 + 合作條件建議。

把「直覺判斷對方公司會不會倒帳」變成「**graph 上看到他董事曾任職於 2 年前倒閉的禾鴻貿易,加上跟空殼公司共用地址,score 82 → CRITICAL**」。

---

## 痛點

5-30 人 SME 簽 NT$50 萬-500 萬合約前,**只能憑感覺或鄉里口碑判斷對方會不會倒帳**:

> **「跟一個新客戶簽了 200 萬大單,90 天票期。客戶看起來很正常,簽完才發現他的董事 1 年前剛把另一家公司倒掉。」** — Dcard 創業板

> **「想查客戶風險去 D&B 一查 NT$30,000 起跳,我們連 200 萬合約毛利都才這個數。」** — PTT Salary

> **「我都自己查商業司、司法院、Google 新聞,1 個客戶花 1-2 小時,5 個案子就是一週。」** — FB 中小企業老闆社群

具體痛點:

- **D&B (Dun & Bradstreet) NT$30,000+ 起跳**,只服務大企業評大客戶
- **TEJ 信用評等** 偏上市櫃公司,對非公開 SME 沒涵蓋
- **聯徵中心信用報告** 只能查自己,**不能查客戶**
- **商業司公開資料 + 司法院裁判書 + 新聞**:資料公開但**分散在 3-5 個網站**,沒人整合
- 銀行 SME 信用評估**只對自家貸款客戶**,別人合約不開放
- ChatGPT 直接問:**會幻覺(編造董監事 / 公司資料)**;且不知道即時資料
- 大部分 SME 老闆**沒有徵信能力**,1 個案子查 1-2 小時是常態
- **「金蟬脫殼」型詐欺**(舊公司倒掉甩債、馬上開新公司用相似名字)— 沒有 graph 分析根本看不出來

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **D&B (Dun & Bradstreet)** | NT$30K+ 起跳,只服務大企業評大客戶 |
| **TEJ 信用評等** | 上市櫃公司導向;非公開 SME 涵蓋低 |
| **聯徵中心** | 只能查「自己」,不能查「客戶」 |
| **商業司公開資料查詢** | 資料公開但**分散且無 graph 連結**;沒有「董事 X 還在哪些公司」反查 |
| **司法院裁判書檢索** | 介面糟,需要知道公司 / 個人姓名才能查;**不會主動告警** |
| **ChatGPT / Claude 直接問** | 容易幻覺(編造董監事 / 訴訟);不知道即時資料 |
| **徵信社** | 一案 NT$5-15K;耗時 3-7 天;對「金蟬脫殼」型風險不擅長 |
| **自己 Google + 商業司 + 司法院** | 1 個案 1-2 小時;會漏掉 graph 連結(「他董事在 X 公司也有過倒帳」) |

**Gap 結構性**:公開資料完全足夠(商業司 + 司法院 + 新聞),但**整合 + entity resolution + graph analysis** 沒人做。Google 搜尋「台灣 中小企業 客戶 風險 評估」零中文 SaaS 結果(D&B 廣告除外)。

## bizradar 在做什麼

```
新客戶 / 廠商 資訊(統編 / 公司名)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式查詢公開資料 corpus(prototype:mock JSON;          │
  │ 真實產品:商業司 API + 司法院 API + 新聞 API):            │
  │   - 公司基本資料(設立日 / 資本 / 地址 / 董監事 / 業務狀態)  │
  │   - 訴訟紀錄(原告 / 被告 / 案件類型 / 金額)                │
  │   - 負評新聞(來源 / 日期 / 嚴重度)                       │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Graph + Entity Resolution(graph_analyzer.py 純函式):    │
  │   - find_director_connections: 目標公司董事還在哪些公司任職 │
  │   - find_address_collisions: 共用地址的其他公司             │
  │   - check_director_problem_history: 董事任職過已解散 /      │
  │     多訴訟 / 負評 公司?                                    │
  │ → 這是 graph 分析的精髓:單看目標公司沒事,**graph 上一連** │
  │   就看到「金蟬脫殼」型風險                                 │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式 compute_risk_score:                                │
  │   各 signal 加權加總 → 0-100 score                         │
  │   分檔 LOW (≤25) / MEDIUM (≤50) / HIGH (≤75) / CRITICAL    │
  │ BUSINESS_INACTIVE +80 → 解散 / 停業公司自動 CRITICAL         │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude 寫:                                                │
  │   - 故事化解釋(100-200 字幫老闆看懂 graph 連結意義)        │
  │   - 5-7 條合作條件建議(預收 % / 票期 / 上限 / 違約金 /     │
  │     擔保品 / 個人連帶保證 / 信用保險)                       │
  │   - 進一步盡職調查清單(老闆可額外做的查證)                 │
  │ **LLM 永不算 risk_score**                                  │
  │ **嚴禁完全拒絕往來建議**(留給老闆判斷)                     │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **Graph 分析是核心**:單看一家公司資料容易被「漂亮新公司」騙;真正的紅旗來自「**這個董事曾在 X 倒掉公司任職**」這種跨公司連結。直接 lookup 沒辦法做,必須建 director→companies 反向索引。
2. **數字 100% 純函式**:risk_score 加總、分檔、各 signal 權重全在 `graph_analyzer.py`;LLM 收結果後**直接引用數字**,絕不重算。
3. **故事化解釋 + 結構化建議**:LLM 角色就是「把 5 個 signal 串成一個故事」(例「鴻禾 = 禾鴻金蟬脫殼」);再轉成 5-7 條合作條件具體建議。

## 動作

### 純函式 graph 分析(免 API key)

```bash
python3 bizradar.py --db samples/companies_db.json --corp-id 12345678 --no-ai --out output.md
```

`samples/companies_db.json` 是 10 家 mock 公司 with cross-referenced directors。`12345678` 是「鴻禾國際」(新公司 + 小資本 + 董事在解散公司任職 + 共用地址)。

輸出含:基本資料 + risk_score (82) + risk_level (CRITICAL) + 6 條 risk signals + 董事關係網路 + 地址共用清單。

### 完整 AI 模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 bizradar.py --db samples/companies_db.json --corp-id 12345678 --out output.md
```

加上 Claude 寫:故事化解釋(金蟬脫殼風險識別)+ 7 條合作條件建議 + 7 條盡職調查清單。

### 預先產出的 demo

`examples/sample_output.md` 是 AI 模式完整報告,展示對「鴻禾國際」CRITICAL 評等 + 故事化解釋 + 具體合作條件(預收 100% / 個人連帶保證 / 信用保險)。

`examples/sample_output_no_ai.md` 是純函式模式,證明免 API key 也能用 + graph 分析結果。

## 已驗證 smoke test

- ✅ 鴻禾國際(12345678) → CRITICAL (score 82),6 signals 包含 DIRECTOR_LINKED_TO_INACTIVE
- ✅ 正信實業(34567890,8 年公司 + 3000 萬資本 + 無訴訟) → LOW (score 0)
- ✅ 捷利物流(89012345,2 件被告 + 小資本) → MEDIUM (score 29)
- ✅ 禾鴻貿易(23456789,已解散) → CRITICAL (BUSINESS_INACTIVE +80)
- ✅ 不存在的統編 → None 不 crash
- ✅ Director graph 雙向正確(陳大華 → 禾鴻 / 林志強 → 宏發 + 鴻禾科技)
- ✅ Address collision 偵測正確(鴻禾 ↔ 宏發 同地址)
- ✅ 純函式 deterministic(同樣輸入跑 N 次結果一致)
- ✅ 共用董事的合法企業也會正確列出(正信 ↔ 永盛 同董事黃淑芬)
- ✅ 訴訟 / 新聞時間視窗篩選正確(超過 2 年被告 / 1 年負評不計入)

## 專案結構

```
bizradar/
├── README.md
├── bizradar.py           # CLI(讀 db + 跑分析 + 渲染報告)
├── graph_analyzer.py     # 100% 純函式:graph + entity resolution + risk score
├── samples/
│   └── companies_db.json # 10 家 mock 公司 with cross-referenced directors
├── examples/
│   ├── sample_output.md          # AI 模式完整報告
│   └── sample_output_no_ai.md    # 純函式模式報告
└── requirements.txt
```

純函式部分零外部依賴(stdlib only)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **接公開資料 API**:商業司公司登記 + 司法院裁判書 + 新聞抓取 → 即時更新 graph
- **更深的 entity resolution**:「王惠蘭 = 王 Helen」、「捷利物流 = 捷利通運」等異名同人 / 同公司
- **新聞 NLP**:從新聞自動偵測「跳票」「倒帳」「停業」「員工抗議」等負面事件
- **持續監控警示**:綁定客戶後,若該公司新增訴訟 / 倒閉 / 負面新聞 → LINE 推播
- **批量上傳查詢**:Excel 上傳 100 個客戶統編 → 批量產出 risk 報告(會計師事務所最愛)
- **整合公開信用評等**:跟 TEJ / 中華徵信所合作做加值資料層
- **LINE Bot**:LINE 對話查詢「鴻禾國際 統編 12345678 風險如何」
- **顧問模式**:對 CRITICAL 案件,直接轉介合作律師 / 徵信社(收 introduction fee)

## 商業模式

| 方案 | 費用 | 對象 |
|------|------|------|
| **Free** | 月 3 次 (無 AI 解釋) | 試用 |
| **Solo** | **NT$299 / 月** (含 30 次 / 月 AI 解釋) | 個人 / 小老闆 |
| **Pro** | NT$999 / 月 (含 200 次 / 月 + LINE 推播) | 5-30 人 SME |
| **Pay-per-use** | NT$199 / 次 | 不訂閱單次查詢 |
| **B2B 會計師 / 律所** | NT$3,999 / 月 (批量上傳 1,000 客戶) | 中小型會計師事務所 / 律所 |
| **B2B 銀行 / 徵信** | 客製 NT$50K-200K / 月 | 中信 / 兆豐 / 中華徵信所 white-label |
| **API** | NT$3 / call | SaaS integration partner |

### WTP 計算

- 徵信社一案 NT$5-15K vs bizradar Pay-per-use NT$199 = **25-75x 便宜**
- 一次「沒查就簽合約」被倒帳 NT$50-500 萬 vs Pro NT$999/月 = **單次預防即回本 5-500 年**
- 會計師事務所批量檢視 1,000 客戶,Pro 月 NT$3,999 vs 自己 Google 1,000 hr × NT$1,500 = **375x 便宜**

### TAM

- 台灣 SME 約 150 萬家;**有對外合作需求** 的估 50 萬家
- 取 1% 滲透 = 5,000 家 × NT$999 = **月 NT$500 萬 MRR / 年 NT$6,000 萬 ARR**
- 加 B2B 會計師 / 律所(預估 50 家)+ 銀行 / 徵信合作 → 年 ARR NT$1-3 億
- 横移日韓港新(各國 SME 風險評估都缺) → 翻倍

## 早期 distribution

1. **PTT Salary / 中小企業板** — 痛點來源 + 種子(每週「客戶倒帳被坑」貼文)
2. **FB 中小企業老闆社群** — 老闆現身說法 case study
3. **記帳士 / 會計師事務所 partner** — 他們現有客戶最需要(尤其是新接的客戶查驗證)
4. **創業育成中心 / 商總 / 商工會議所**
5. **YouTube 中小企業 KOL** — case study(「我用 bizradar 擋下一個 NT$200 萬合約」)
6. **LinkedIn 銷售 + B2B 開發**(房地產 / 製造 / 貿易 業者)
7. **TEJ / 中華徵信所** partner(他們做大公司,bizradar 做 SME,互補)
8. **商業司公開資料 hackathon** 露出 + 政府 / 學界合作

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **公開資料延遲 / 不完整** | 高 | 多源資料(商業司 + 司法院 + 新聞)互補;產品定位「降風險 50%+ 而非完美保證」 |
| **誤判導致客戶投訴 / 名譽損害** | 高 | UI / report 多次明確「初步參考」+「重大決策請洽律師 / 徵信社」;對 CRITICAL 等級加 disclaimer |
| **公司資料保護法 / 商業司資料條款** | 中 | 純用公開資料 + 商業司公告本即允許查詢 + 法律意見諮詢確認資料使用範圍 |
| **D&B / TEJ 自己做 SME 版本** | 中 | 在地化 + 中文 + 價格優勢是護城河;且大廠通常開發慢 |
| **政府 SME 自己做(經濟部 / 商業司)** | 低 | 公務機關開發 SaaS 緩慢且偏向資料公開非分析應用 |
| **法律風險(被風險評估的公司主張誹謗)** | 中 | UI 強調「依公開資料 + 由系統計算」+ 不發布最終評語 + 保留爭議申訴管道 |
| **個資 / 公開資料二次使用** | 中 | 純查公開資料 + 報告不上雲 + 企業版可走 self-host LLM |

---

*第二十七輪在 2026-05-10 產出於 incubator(台灣優先,**第十七個 AI 架構模式 — Graph / Network Analysis + Entity Resolution**)。跟前 26 輪 doc-gen / pricing / OCR-aggregation / RAG / scheduling+LINE / matching / monitoring+alerting / churn / vision-pricing / vision-classification / personalization / time-series-anomaly / stylometric-matching / structured-extraction / conversational-agent-with-tools / monte-carlo 都不同架構。*
