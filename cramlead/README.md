# cramlead — 台灣補習班 / 才藝班招生 Lead Conversion Logistic Regression

**「招生季每月 30-100 通試聽電話, 我櫃台時間有限該先打哪個? 哪個 lead 是浪費時間?」** 用 Logistic Regression with L2 regularization 從 180 件歷史 leads 學「報名 vs 流失」模式, 給每個新 lead 算 P(報名) + **可解釋係數** (試聽過 +2.6× odds / 朋友介紹 +2.2× / 距離 -0.82) → outreach 優先級 + 老學生介紹獎勵金 + 試聽日 SOP。

## 痛點

台灣補教 / 才藝班生態:
- **正規補習班**: ~5,000 家
- **才藝班 / 課後安親**: ~10,000 家
- **線上補教**: ~500 家 + 老師個人接案 ~3 萬人
- **共 ~15,000 家** 需要持續招生

**核心痛點** (PTT TeacherTalk / 補教 / Dcard 教師 / FB「補教老闆交流」3-5 萬人社群):
- **招生季月 30-100 通試聽電話**, 老闆 / 櫃台不知道哪個 lead 該優先 follow-up
- conversion rate 20-35%, 但時間花錯 lead 上常常 20% 收成
- 沒系統化 lead scoring → 浪費資源在低機率 leads
- 廣告砸 NT$5-30K/月 + ROI 看天意, 不知道哪個渠道帶 quality leads

**現有資源**:
- 補教王 / 補習達人 / EduBase 等 CRM 是純記錄 (沒 ML)
- 老闆憑經驗 (主觀, 偏見高)
- 學科顧問付費課程 NT$10K+ (太貴, 小補習班用不起)

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(cramlead 補的) |
|---|---|---|
| 補教王 / 補習達人 CRM | 學生 / 課程 / 收費紀錄 | 純記錄, 不做 ML lead scoring |
| Google Analytics + FB Pixel | 廣告 ROI 追蹤 | 沒個別 lead 後續 conversion 預測 |
| 老闆主觀分配 | 經驗判斷 | 主觀偏見高, 30% lead 被忽略 |
| Excel 簡單分類 | 純手動 | 沒 logistic regression, 沒 coefficient interpretation |
| ChatGPT 一次問 | 一次性建議 | 不能跑 gradient descent, 沒持續 model |

**Gap 結構性**: Logistic Regression (Berkson 1944 / Cox 1958) 學術成熟 65+ 年,但**沒人做成台灣補教 lead scoring SaaS**。Google「補習班招生 Logistic Regression 中文」零本土 SaaS。

## 架構 — Logistic Regression with L2 Regularization (46th 條 AI pattern)

```
Historical 180 leads (features + enrolled label)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Feature engineering:                          │
│   • Numeric features (distance, days_since)   │
│     → z-score standardization                │
│   • Categorical features (referral, grade)    │
│     → one-hot (drop first level)             │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Logistic regression training:                 │
│   Initialize β = 0, b = logit(empirical p)    │
│   For iter in 1..max_iter:                    │
│     logits = Xβ + b                          │
│     preds = sigmoid(logits)                   │
│     grad_β = X^T(preds - y)/n + λβ           │
│     β -= lr × grad_β                          │
│     b -= lr × mean(preds - y)                 │
│   Until ‖Δloss‖ < tol                         │
│   (Loss = -log likelihood + λ/2 ‖β‖²)         │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Predict new lead x:                            │
│   logit = b + Σ β_j × x_j                     │
│   P(enrolled) = sigmoid(logit)                │
│   Feature contributions = β_j × x_j           │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Interpretation:                                │
│   β > 0 → feature predicts enrollment         │
│   β < 0 → feature predicts no-enrollment      │
│   odds_ratio = exp(β)                         │
│   Each β reflects effect ceteris paribus      │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + statistics + dataclass + collections):
- `sigmoid`: numerically stable
- `FeatureEncoder`: numeric standardization + categorical one-hot
- `fit_logreg`: gradient descent on logistic loss + L2 reg
- `predict_proba`: P(y=1 | x) + feature contributions
- `coefficient_summary`: sorted β + odds_ratio + direction
- `accuracy_score / log_loss_score / auc_roc_approx`: evaluation

**LLM 只負責**: 寫 250-330 字「outreach 策略 + 流程改造 + 行動分配 + 風險」
**LLM 絕不負責**: 計算 probabilities / log_loss / AUC / 係數 (數字 100% 來自 LogReg)

## 使用示例

```bash
# 純函式模式 (無 API key)
python cramlead.py --data samples/cram_leads.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python cramlead.py --data samples/cram_leads.json

# 自訂 hyperparams
python cramlead.py --lr 0.5 --l2 0.001 --max-iter 2000
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陽光補習班 台北信義國高中部, 180 件歷史 + 15 upcoming):

| 指標 | 值 |
|---|---|
| Training accuracy | 81.1% |
| AUC-ROC | **0.876** (excellent) |
| Log-loss | 0.4379 |
| Converged | ✓ 393 iterations |

**Top 5 係數 (按 |β|)**:

| 特徵 | β | odds_ratio | 解讀 |
|---|---|---|---|
| 已試聽 | +0.955 | **×2.60** | 試聽是雙王牌之一 |
| 距離 | -0.819 | ×0.44 | 越遠越流失 |
| 朋友介紹 | +0.787 | **×2.20** | 高 trust 預設 |
| 網站表單 | -0.761 | ×0.47 | 隨意填寫者多 |
| 高中1-3 | +0.736 | ×2.09 | 升學壓力 |

→ 15 upcoming leads, top 6 高機率 (L1010 高中朋友介紹試聽 97.3%) 今天就打, 6 個中等 follow-up, 3 個 nurture。

## 目標市場

- **TAM**: 5,000 補習班 + 10,000 才藝班 + 500 線上補教 = **15,000 家招生需求**
- **WTP 錨點**:
  - 招生季月廣告 NT$5-30K + 櫃台時間損失 NT$10-50K
  - 1 個多成交 lead = NT$30-150K/年學費, conversion +10% = 月多 NT$30-150K 營收
  - Solo NT$499/月 vs 月多 NT$30K+ 營收 = **60x ROI**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 50 leads/月 + 基本 score | 試用 |
| **Solo** | NT$499/月 | 無限 leads + AI 腳本 + LINE 推播 | 個人補習班 |
| **Pro** | NT$1,499/月 | 多老師 / 多科目 dashboard + Google Analytics 整合 | 5-10 講師補習班 |
| **Chain** | NT$4,999/月 | 連鎖 (10-50 分校) + 跨校 benchmark | 連鎖補教 (儒林 / 翰林) |
| **Enterprise** | NT$15,000+/月 | EHR + API + 客製模型 + 退費預測 | 大型補教集團 |

## Distribution

- **PTT TeacherTalk / 補教 / Dcard 教師** 板長尾 SEO
- **FB「補教老闆交流」** 3-5 萬人社群 案例分享
- **YouTube 補教 KOL** (葉丙成 / 補習老闆會 / 葉子老師) 案例合作
- **補教王 / 補習達人 / EduBase / 補教大師** 整合 partner
- **教育部 / 縣市教育局** 公益版補習班輔導
- **教育博覽會 / 補教博覽會** 台北 5 月 booth

## TAM

- 1% × 15,000 = 150 × NT$499 = **月 NT$7.5 萬**
- + Pro 100 × NT$1,499 = NT$15 萬/月
- + Chain 30 × NT$4,999 = NT$15 萬/月
- + Enterprise 10 × NT$15K = NT$15 萬/月
- 總計 **月 MRR NT$52 萬 / 年 ARR NT$630 萬**
- 加滲透 + 橫移港新馬 / 日韓補教 → 翻倍至 **NT$1,500-2,500 萬 ARR**

## 風險與限制

- **線性假設**: P(報名) 通過 logit 跟 features 線性,真實有 nonlinear 交互 (e.g. 年級 × 距離) — Pro 版加交互項或 GBDT 比較
- **180 件樣本不大**: 真實 launch 需 ≥ 500 件多季 / 多年資料訓練, 避免 overfit
- **L2 正則化 λ=0.01 是 mild**: Pro 版用 cross-validation 自動選 λ
- **In-sample accuracy 高 ≠ 真實預測力**: 需 train/test split + temporal validation (用 t-1 季訓練, 預測 t 季)
- **季節性未捕捉**: 暑假前 vs 開學後 conversion 差異, Pro 版加 month/seasonality 特徵
- **Self-fulfilling prophecy**: 老闆只 follow-up 高 prob leads → model 自我強化偏見, 偶爾低 prob 也打讓 model 學反例
- **隱私敏感**: lead 資料涉個資 (姓名 / 電話 / 學校), 雲端版需加密 + 客戶同意 + 資料留存政策

---
*cramlead = Logistic Regression with L2 regularization × 台灣補習班招生 lead conversion niche = 從 180 件歷史學報名模式 + 可解釋係數, 老闆 / 櫃台優先 outreach 高機率 lead, conversion 從 30% → 50% + 廣告 ROI 翻 2-3 倍。*
