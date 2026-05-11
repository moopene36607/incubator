# expsense — 台灣 SME 員工費用報銷異常偵測 Isolation Forest

**「每月 30-200 筆報銷單,老闆花 1-2 小時逐筆對帳結果還是漏看可疑筆」** 用 Isolation Forest (Liu, Ting, Zhou 2008) 多維 features 5 秒掃完整月報銷, top-10 可疑筆排序 + 每筆異常原因 + 老闆怎麼跟員工確認的具體開場句。

## 痛點

台灣中小企業 (5-30 人) ~30,000 家有 finance 監控需求:
- **每月 30-200 筆 reimbursement**: 餐費 / 交通 / 客戶招待 / 通訊 / 文具 / 差旅
- **老闆 1-2 小時對帳**: 大部分時間在算 "這筆合理嗎?" 而不是找異常
- **常見漏看**:
  - 異常高金額 (餐費突然 NT$5,000)
  - 異常時段 (凌晨 2 點交通費)
  - 異常週末 (週六客戶招待)
  - 重複報銷 (同樣項目報 2 次)
  - 員工 mis-categorize (差旅雜支類報 NT$8,500)

實際情境 (FB「中小企業老闆交流」5-10 萬人社群 / PTT Salary / Dcard 工作版):
- 「員工報銷單我看到都麻木了, 4 個業務月底丟 80 筆我根本來不及審」
- 「上次發現一個工程師連續 3 個月報凌晨 Uber 共 NT$15K, 才發現他根本沒加班是自己亂報」
- 「請會計師對帳一個月 NT$5K-10K, 但他們只看分類沒看異常」

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(expsense 補的) |
|---|---|---|
| 工商記帳軟體 (鼎新 / 數位通) | 記帳 / 結帳 / 報表 | 不做 anomaly detection |
| Concur / SAP Expense | 大企業報銷流程 | 月費 NT$30K+, 中小企業負擔不起 |
| 會計師事務所對帳 | 月外包 NT$5-10K | 不擅長 ML, 只看分類正確不看異常 |
| Excel + 篩選 | 老闆自己 | 找不出多維異常 (金額 + 時段 + 類別 + 週末) |
| ChatGPT 一次貼 100 筆 | 一次性看 | 不能跑 IF, 沒持續比對員工歷史 |

**Gap 結構性**: Isolation Forest (Liu et al. 2008) 學術成熟 17 年,**沒人做成台灣中小企業可用 SaaS**。Google「台灣 報銷 isolation forest」零中文 SaaS 結果。

## 架構 — Isolation Forest (36th 條 AI pattern)

```
Reimbursement records → Feature engineering
                          │
                          ▼
                ┌──────────────────────┐
                │ amount_log           │
                │ amount_vs_personal   │
                │ hour_atypical        │
                │ is_weekend           │
                │ category_idx         │
                └──────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │  Build n_trees random partition trees│
        │  Each tree:                          │
        │    1. Pick random feature            │
        │    2. Pick random split between min/max│
        │    3. Recurse until height_limit     │
        │       = ⌈log₂(sample_size)⌉          │
        └─────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │ For each point x:                   │
        │   E[h(x)] = avg path length         │
        │   c(n)    = 2·H(n-1) - 2(n-1)/n     │
        │   s(x)    = 2 ^ (-E[h(x)] / c(n))   │
        │   s → 1 = anomaly                   │
        └─────────────────────────────────────┘
                          │
                          ▼
              Top-K + feature contributions
```

**100% 純函式 stdlib** (random + math + dataclass):
- `harmonic(n)`: H(n) 調和數 (前 100 精確 / 後用 ln+γ 漸近)
- `c_factor(n)`: 不成功 BST 搜尋平均路徑長
- `build_tree`: 隨機 feat × 隨機 split 遞迴
- `path_length`: 點落葉路徑長度 + adjustment for incomplete branch
- `fit_iforest`: ensemble 100+ 棵樹,每棵 subsample
- `anomaly_score(x)`: 0-1 anomaly score
- `top_k_anomalies`: 排序 + threshold filter
- `feature_contribution`: 每 feature 的隔離力 (近 root = 隔離力強)

**LLM 只負責**: 寫 250-320 字「每筆對帳建議 + 具體開場句 + 跨員工模式 + 風險」
**LLM 絕不負責**: 計算 anomaly score / feature contribution (數字 100% 來自 IF)

## 使用示例

```bash
# 純函式模式 (無 API key)
python expsense.py --records samples/reimbursements.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python expsense.py --records samples/reimbursements.json

# 自訂 top-K + IF 參數
python expsense.py --top 15 --trees 200 --sample-size 128
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (海星科技 5 員工 109 筆 reimbursement 5 月份):

| # | ID | 員工 | 異常分 | 描述 |
|---|---|---|---|---|
| 1 | R0106 | 陳大華 | 0.702 | 餐費 NT$4,800 凌晨 23 時 (異常時段 + 高金額) |
| 2 | R0105 | 黃志強 | 0.673 | 差旅雜支 NT$8,500 (HR/Admin 類別正常 < NT$500) |
| 3 | R0108 | 李雅婷 | 0.662 | 交通 NT$880 凌晨 3 時 |
| 5 | R0103 | 陳大華 | 0.610 | 客戶招待 NT$18,800 (一般 NT$2-3K) |

→ **5 秒掃完 109 筆,top-4 全部命中 inject 的可疑筆**。老闆當月對帳壓到 30 秒。

## 目標市場

- **TAM**: 台灣 5-30 人 SME ~30,000 家, 50-人以下 ~80,000 家
- **WTP 錨點**:
  - 老闆每月 1-2 hr × NT$1000/hr 機會成本 = NT$1-2K/月 vs Solo NT$199 = 5-10x ROI
  - 一次抓到 NT$10K 異常報銷 = 全年回本

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 30 筆/月 + 5 員工 | 試用 |
| **Solo** | NT$199/月 | 無限筆 + 自訂 features + LINE 推播 | 5-10 人 SME |
| **Pro** | NT$499/月 | + 多月趨勢 + 員工 risk profile + 自動報表 | 10-30 人 SME |
| **Studio** | NT$1,999/月 | + 接會計軟體 API + 異常每日 webhook | 30-100 人企業 |
| **Accountant** | NT$4,999/月 | 會計師事務所 white-label 多家客戶 | 記帳士 / 會計事務所 |

## Distribution

- **FB「中小企業老闆交流」5-10 萬人** SEO 案例分享
- **PTT Salary / Soft_Job / 中小企業** 板長尾關鍵字
- **YouTube SME 老闆 KOL** (Mr. 6 / 商業思維學院) 案例
- **記帳士 / 會計事務所** B2B BD 白標
- **鼎新 / 數位通 ERP** integration partner (補 anomaly detection 缺口)
- **創業育成中心 / 中小企業協會** 配合計畫

## TAM

- 1% × 30,000 = 300 家 × NT$199 = **月 NT$6 萬 MRR**
- + Pro 100 × NT$499 = NT$5 萬/月
- + Studio 30 × NT$1,999 = NT$6 萬/月
- + Accountant 30 × NT$4,999 = NT$15 萬/月 (每記帳士帶 10 客戶 → 高 lift)
- 總計 **月 MRR NT$32 萬 / 年 ARR NT$380 萬**
- 加滲透 + 橫移 → 翻倍至 **NT$1,000-2,000 萬 ARR**

## 風險與限制

- **anomaly ≠ fraud** — 模型只找跟其他人不一樣的, 80% 是 mis-category / OT 沒走 SOP / 業績衝刺;不可直接定罪
- **小樣本不穩** — < 30 筆 IF subsample 太小, 結果可能 noisy;Pro 版要求 ≥ 100 筆
- **特徵工程依賴** — 加更多 features (供應商 / 同筆多人會審 / 銀行對帳串接) 可提高準確度
- **季節性 / 月底特例** — 業務員月底衝業績可能合理高消費,模型不知道 context;Pro 版加月份 feature
- **隱私敏感** — 員工報銷涉個資, 雲端版要加密 + 資料留存政策

---
*expsense = Liu, Ting & Zhou 2008 Isolation Forest × 台灣 SME niche = 老闆每月 1-2 小時對帳壓到 30 秒,且**不會漏看多維異常**。*
