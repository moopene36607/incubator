# stayspan(留任跨度)

**台灣 SME 員工 retention 時間分析 — Kaplan-Meier 留任曲線 + cohort hazard 比較,找出最危險 / 最穩定的員工群並給留任行動建議。**

把「**我招的工程師為什麼都做不到 1 年?**」變成「**Engineering 部門 12 月留任率 60%、Low 績效全員 8 個月內離職、Mid 績效員工在 22-24 月時集中流失** — 留任要在這 3 個時點 intervene」。

---

## 痛點

5-30 人 SME 老闆每年招聘 3-10 人,**每位員工招聘 + 培訓 + 流失成本 NT$50-100K**。但完全沒有工具預測 retention:

> **「招了一個工程師月薪 6 萬,做 3 個月就跳槽,等於那 18 萬全白花。」** — Dcard 創業板

> **「想知道我這行業平均員工做多久,問人事顧問要 NT$30K 一份報告。」** — PTT Soft_Job

> **「104 / 1111 給我薪資水準,但不告訴我『我這種公司員工平均做多久』」** — FB 中小企業老闆

具體痛點:

- 5-30 人 SME 一年招 3-10 人,**每位離職成本 NT$50-100K**(招聘廣告 + HR 時間 + 培訓 + 上手期失能 + 重招)
- 老闆**完全不知道「平均留任時間」**;只覺得「**人來來去去**」
- 沒有**早期警示**:不知道哪個 cohort 最容易離職、什麼時點要干預
- 104 / 1111 / 人力銀行**給薪資水準但不做 retention 預測**
- HR 顧問人力資源策略一次 NT$30-50K 太貴
- BambooHR / Workday 偏大企業 + 英文 + 不做 survival analysis
- HR 數據分析需要統計背景(Cox regression / KM curve),**SME 老闆 / HR 沒人懂**
- 學術界 survival analysis 50+ 年歷史成熟,**但沒人做成 SME 老闆可用的 SaaS**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **104 / 1111 / 1111 人資網** | 給薪資中位數,**不做 retention 預測** |
| **BambooHR / Workday** | 偏大企業 + 英文 + UI 複雜 + 不做 survival |
| **EZHR / 行動人事 / 漢方雲** | 排班 / 打卡工具,**完全不做 retention 分析** |
| **HR 顧問報告** | 一次 NT$30-50K;只做一次性研究 |
| **R / Python survival 套件**(lifelines / scikit-survival) | 完全給研究員用;**SME 老闆看不懂 hazard ratio** |
| **Excel 自己算 KM** | 公式繁雜 + 不會做 cohort 比較 |
| **ChatGPT 直接問** | 不能跑 stratified KM;不會處理 censored data |

**Gap 結構性**:Kaplan-Meier 1958 年就有,但 60+ 年來**沒人做成 SME HR 可用的 SaaS**。Google「台灣 中小企業 員工 留任 預測」零中文 SaaS。

## stayspan 在做什麼

```
員工 retention CSV
(employee_id, tenure_months, event_observed,
 department, level, performance_tier)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ survival.py 100% 純函式 stdlib (statistics + dataclass):  │
  │   - compute_kaplan_meier:                                  │
  │     S(t) = ∏(1 - d_i / n_i) for all event times t_i ≤ t   │
  │     處理 right-censored data(在職員工)                    │
  │   - median_tenure: 首個 S(t) ≤ 0.5 的時間                  │
  │   - survival_at(t): S(12), S(24), S(36) 留任率             │
  │   - cohort_survival(by feature): 按部門 / 職級 / 績效分組  │
  │     跑 KM 比較                                              │
  │   - compare_cohorts: 找最危險 vs 最穩定 cohort + hazard 比 │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude HR 顧問寫:                                          │
  │   - Executive Summary(150-200 字現況故事化解釋)            │
  │   - 最危險 cohort(誰最容易離職)+ 預估年度離職成本         │
  │   - 最穩定 cohort(誰留得最久)                              │
  │   - 4-5 條具體留任行動(優先順序排序)                       │
  │   - 早期警示信號(離職前 1-3 月信號)                        │
  │   - 重要 caveats(樣本小 + 不是個人 hazard model)           │
  │ **LLM 永不算 NT$ / 留任率**                                │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **Kaplan-Meier 處理 censored data**:在職員工是 right-censored(只知 tenure ≥ X 但不知何時離職);用 naive 平均會嚴重低估留任時間。**KM 是 standard solution**。
2. **數字 100% 純函式**:S(t) / median / hazard 全在 `survival.py`;LLM 永不算機率。
3. **Cohort 不是個體**:報告強調 cohort 級別趨勢,**避免老闆用 hazard model 「預測 X 員工會離職就開除」**。Survival analysis 是政策設計用,**不是個人開除依據**。

## 動作

### 純函式 KM 分析(免 API key)

```bash
python3 stayspan.py samples/employees.csv --no-ai --out output.md
```

`samples/employees.csv` 是 30 個 SME 員工(10 工程師 / 6 行銷 / 8 業務 / 6 營運),17 已離職 + 13 在職。

輸出含 整體 KM 曲線 + 各部門 / 職級 / 績效的 cohort 比較。

### 完整 AI 模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 stayspan.py samples/employees.csv --out output.md
```

加上 Claude 寫 executive summary + 最危險 / 最穩定 cohort + 5 條留任行動 + 早期警示信號。

### 預先產出的 demo

`examples/sample_output.md` AI 完整報告,展示:
- 整體 median tenure 22 月、12 月留任 73.3%
- 最危險 cohort:Low 績效 + Junior(12 月內 100% 離職,median 8 月)
- 最穩定 cohort:High 績效 + Senior(12 月留任 100%、Ops 12 月留 100%)
- 5 條留任行動 + 4 個 early warning 時點

`examples/sample_output_no_ai.md` 純函式模式輸出。

## 已驗證 smoke test

- ✅ Empty / all-censored / all-events 邊界正確
- ✅ 預設 sample (30 員工) → median 22 月, S(12)=73.3%
- ✅ Engineering S(12)=60% < Ops S(12)=100%
- ✅ Low 績效 S(12)=50% < High S(12)=100%(預測力強)
- ✅ KM 曲線 monotonically non-increasing
- ✅ survival_at 查詢與整體一致
- ✅ Median > 觀察期時 return None
- ✅ Cohort 按 survival 升序排(危險→穩定)
- ✅ 純函式 deterministic

## 專案結構

```
stayspan/
├── README.md
├── stayspan.py            # CLI(讀 CSV + 純函式 KM + LLM HR 顧問)
├── survival.py            # 100% 純函式:KM + median + cohort + hazard
├── samples/
│   └── employees.csv      # 30 員工(17 離職 + 13 在職)
├── examples/
│   ├── sample_output.md          # AI 完整報告
│   └── sample_output_no_ai.md    # 純函式模式
└── requirements.txt
```

純函式部分零外部依賴(stdlib 只用 statistics + dataclass)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **Cox PH model**:同時控制多個 confounders(部門 + 職級 + 績效)算 hazard ratio
- **時間相依 covariates**:加薪 / 升職 / 部門轉移 對 retention 的因果效應
- **預測新員工 hazard**:新進員工依 profile 預測「12 月離職機率」(個人化,但僅給 HR 政策設計用)
- **接 HRMS API**:從 BambooHR / 行動人事 / EZHR 自動拉員工 retention 資料
- **同產業 benchmark**:把貴公司 retention 跟業界中位數比較(資料來源:104 / 1111 跨公司資料)
- **介入效益追蹤**:做了「90 天 review」政策後,新員工 retention 是否上升 → causal lift 估計
- **競爭分析**:從 LinkedIn 看員工去哪了(跳槽到哪家對手 / 還是轉行)
- **匿名化離職原因 NLP**:從離職面談紀錄抽出主因(薪資 / 主管 / 文化 / 升職)
- **Sensitivity analysis**:小樣本(< 50 員工)時的信賴區間 / 置信度顯示

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 1 次 / 員工 ≤ 20 | 試用 |
| **Solo** | **NT$799 / 月** | 5-30 人 SME,基本 KM + cohort + 5 行動建議 |
| **Pro** | NT$2,499 / 月 | 30-100 人,加 Cox PH + 介入效益追蹤 + 月度自動報告 |
| **Enterprise** | NT$8,999 / 月 | 100+ 人,API + HRMS 整合 + 個人化 hazard score(僅 HR 看,**不用於開除**) |
| **B2B 人力顧問** | 客製 NT$30K+ / 月 | 顧問公司 white-label 服務 SME 客戶 |
| **B2B 大型獵頭** | NT$50K-200K / 月 | 獵頭公司用 stayspan 分析候選人「在新公司會做多久」 |

### WTP 計算

- HR 顧問做一次 retention 分析 NT$30-50K vs Pro NT$2,499/月 = **12-20x 便宜**
- 一次擋下「招到 6 月就走的人」(成本 NT$60-80K)vs Solo NT$799/月 = **單次擋下回本 6 年**
- 大型公司 Enterprise NT$8,999/月 vs **prevent 1-2 個高貢獻人才離職 NT$50-200K** = 月度 ROI 6-22x

### TAM

- 台灣 SME 約 150 萬家,5-30 人有正式 HR 概念的核心 SME 約 5 萬家
- 取 1% 滲透 = 500 家 × NT$799 = **月 NT$40 萬 MRR / 年 NT$480 萬 ARR**
- 加 Pro + Enterprise + B2B 顧問 / 獵頭 → 年 ARR **NT$2,000-4,000 萬**
- 横移日韓港新 SME → 翻倍

## 早期 distribution

1. **PTT Salary / 中小企業 / Soft_Job** — 痛點來源 + 種子
2. **FB 中小企業老闆社群** — 老闆痛點集中
3. **HR 社群 / SHRM 台灣分會** — HR 從業者社群
4. **HR 顧問公司 partner** — white-label
5. **創業育成中心 / 中小企業協會 / 商總** — 政府背書
6. **YouTube / LinkedIn HR KOL** — case study
7. **104 / 1111 整合 partner**(可能合作 + 競爭並存)
8. **Cake / Yourator 招募平台** integration — 招募流程 + retention 預測

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **被誤用於開除個別員工** | **極高** | UI 重複明確「**僅給 cohort 趨勢,不用個人開除**」;個人 hazard score 只在 Enterprise + HR 看 |
| **小樣本 (< 30 員工) 結果不穩定** | 高 | UI 顯示信賴區間 + 警告;< 30 員工只能看 trend 不能用 cohort 比較 |
| **歧視疑慮(性別 / 年齡 cohort)** | **極高** | 預設不分析性別 / 年齡;企業版可開啟但**需勞動部背書**;主要看績效 / 部門 / 職級 |
| **HRMS 整合困難** | 中 | 第一階段 CSV 上傳;後期 BambooHR / EZHR 整合 |
| **HR 顧問反感(搶生意)** | 中 | 走 partner 路線 white-label |
| **個資 / 員工資料隱私** | **極高** | stateless;CSV 不上雲;企業版 self-host LLM;**員工資料絕不對外分享** |
| **法規 (個資法 / 勞基法) 合規** | 高 | 與律師合作確認;明確「不做員工監控 / 績效歧視」 |

---

*第三十三輪在 2026-05-10 產出於 incubator(台灣優先,**第二十三個 AI 架構模式 — Survival Analysis / Time-to-Event**)。跟前 32 輪所有 pattern 都不同架構。*
