# cleanmate — 台灣家政服務 客戶需求 → 阿姨類型 Naive Bayes 推薦

**「我家養大狗 + 嬰兒 + 老人, 派來的阿姨怕狗 / 不會帶嬰兒, 退服 3 次」** 用 Multinomial Naive Bayes (Bayes 1763) 從 100+ 件歷史成功配對學「家庭 features → 適合 阿姨 specialty」, 客戶填表單後直接推薦 specialty type (深度清潔 / 例行維護 / 嬰幼兒 / 寵物 / 老人 / 重物) → 客戶溝通腳本 + 阿姨篩選 SOP。

## 痛點

台灣家政服務市場:
- **鐘點打掃 / 居家清潔**: 月 100-200 萬 hours 服務 (Hello 阿姨 / 蘭舍 / 居家清潔 / iKnow 等平台)
- **月嫂 / 居家照顧**: 5,000+ 月嫂 + 1.5 萬名居家照顧員
- **小時工市場**: ~10 萬 active 阿姨
- **總交易**: 全台 ~30 萬戶有定期家政服務需求

**核心 pain** (FB「家政服務交流」/「居家清潔分享」3-5 萬人社群 / Dcard 居家版 / PTT WomenTalk):
- 「派來的阿姨怕狗, 我家黃金獵犬 → 退服」(典型)
- 「月嫂不會帶嬰兒 / 老人 / 過敏體質」
- 「阿姨擅長深度清潔但客戶只要快速例行, 雙方都覺得浪費」
- **退服率 25-35%** 因匹配錯誤
- 平台分派靠人工 / 經驗 / 看 profile, 沒系統化

**現有資源**:
- 平台分派員工人工配對 (主觀)
- 阿姨自填 profile (但不細到 specialty type)
- 客戶 5 星評分 (滯後信號 + 已退服)

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(cleanmate 補的) |
|---|---|---|
| Hello 阿姨 / 蘭舍 / 居家清潔 平台 | 媒合 + 收款 + 評價 | 派阿姨靠人工經驗, 不做需求 → specialty 分類 |
| 阿姨自填 profile | 自填擅長項 | 自填主觀 + 不細; 無客戶端對應 |
| ChatGPT 一次問 | 一次性建議 | 不能學歷史 pairing, 沒持續模型 |
| Excel + 人工分配 | 主觀記錄 | 沒 NB 量化, 100+ 件記憶有限 |

**Gap 結構性**: Naive Bayes (Bayes 1763) 學術成熟 260 年,但**沒人做成台灣家政平台 specialty 分類 SaaS**。Google「家政 阿姨 Naive Bayes 中文」零本土 SaaS 結果。

## 架構 — Multinomial Naive Bayes (45th 條 AI pattern)

```
100+ 件歷史 (features, specialty) pairings
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Training:                                     │
│   For each class c (specialty):               │
│     log P(c) = log(count(c) / total)          │
│   For each feature f, value v, class c:       │
│     P(f=v|c) = (count(f=v, c) + α)            │
│              / (count(c) + α × |values|)     │
│   (Laplace smoothing α = 1.0)                 │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Predict new (features = x):                   │
│   For each class c:                           │
│     log P(c | x) = log P(c) + Σ log P(x_i|c) │
│   Predicted class = argmax_c                  │
│   Probabilities via softmax(log_posteriors)   │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Explain:                                      │
│   Top contributing features (highest log P)   │
│   Class-distinctive features                  │
│     (high P(f|c) vs low P(f|other classes))   │
│   LOO cross-validation accuracy               │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + collections + dataclass):
- `fit_naive_bayes`: 訓練 with Laplace smoothing
- `predict_one`: log-space prediction + softmax probabilities + contributing features
- `class_distinctive_features`: 找該 class 最具區別力的 features
- `loo_evaluate`: leave-one-out cross-validation
- `accuracy / confusion_matrix`: in-sample evaluation

**LLM 只負責**: 寫 250-330 字「分派 SOP + 客戶溝通腳本 + 風險」
**LLM 絕不負責**: 計算 probabilities / log_priors / distinctive features (數字 100% 來自 NB)

## 使用示例

```bash
# 純函式模式 (無 API key)
python cleanmate.py --data samples/cleaner_marketplace.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python cleanmate.py --data samples/cleaner_marketplace.json

# 調整 Laplace smoothing
python cleanmate.py --alpha 0.5
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陳太太家: 黃金獵犬 + 4 歲幼童 + 雙重清潔):

| Specialty | 機率 |
|---|---|
| ⭐ **寵物friendly** | **57.8%** |
| 例行維護 | 31.6% |
| 嬰幼兒friendly | 7.4% |
| 深度清潔 | 2.6% |
| 老人照顧friendly | 0.6% |

→ NB 從 100 件成功 pairing 學到 「狗 + 幼童 + 毛髮抗敏」是寵物 specialty 主場, 平台分派員工可直接從寵物 friendly 阿姨池子挑。In-sample 80% / LOO 58% accuracy (5 類)。

## 目標市場

- **TAM**:
  - 家政平台 (Hello 阿姨 / 蘭舍 / 居家清潔 / iKnow / 多力小田) ~30-50 家
  - 10 萬 active 阿姨 + 30 萬戶定期客戶
  - 月 100-200 萬 hours 服務量
- **WTP 錨點**:
  - 退服率從 30% → 10% = 平台月省 NT$30K-200K
  - 客戶不必試 3 次才匹配 = 流失率減半

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 30 件歷史 + 5 預測/月 | 試用 |
| **Solo** | NT$499/月 | 無限件 + 阿姨庫管理 + SOP 模板 | 個人 家政 / 中介 |
| **Pro** | NT$1,999/月 | 多平台 / 多 分公司 + API + 退服分析 dashboard | 中型平台 |
| **Enterprise** | NT$8,000+/月 | 連鎖 (Hello 阿姨 / 蘭舍 規模) + 客製 features + 月嫂版本 | 連鎖平台 |
| **Insurance** | NT$15,000+/月 | 保險 / 公益機構 / 政府社福 long-term care 媒合 | 政府 / NPO |

## Distribution

- **FB「家政服務交流」/「居家清潔分享」** 3-5 萬人社群 案例
- **Hello 阿姨 / 蘭舍 / iKnow / 居家清潔 / 多力小田** 平台 B2B BD
- **PTT WomenTalk / 媽寶 / Dcard 居家** SEO
- **YouTube 家事 / 居家 KOL** (家事女王 / 簡單生活實驗室 / 整理收納師) 案例合作
- **長期照顧管理中心 / 居家服務協會** B2B partner
- **新婚 / 新生兒博覽會** booth (台北 4 月 / 12 月)

## TAM

- 1% × 30 萬戶定期客戶 = 3,000 客戶 (但客戶不直接付費, 平台付)
- 50 個平台 × Solo NT$499 = NT$2.5 萬/月
- + Pro 30 × NT$1,999 = NT$6 萬/月
- + Enterprise 10 × NT$8,000 = NT$8 萬/月
- + Insurance / 政府 5 × NT$15,000 = NT$7.5 萬/月
- 總計 **月 MRR NT$24 萬 / 年 ARR NT$290 萬**
- 加滲透 + 橫移港新馬 / 日韓家政 → 翻倍至 **NT$700 萬-1,200 萬 ARR**

## 風險與限制

- **獨立性假設違反**: 真實上「老人 + 嬰兒」共存有強相關, NB 假設獨立可能 underperform; Pro 版用 TAN (Tree-Augmented NB) 或 Logistic Regression
- **類別不平衡**: 老人照顧 friendly 只 4 件 → 信心區間寬, 容易誤判;Pro 版用 class weight / SMOTE 補正
- **訓練樣本 100 件不足**: 真實 launch 需 ≥ 500 件多平台 + 多 family-validated pairings
- **不取代實地評估**: NB 給 specialty 分類, 具體阿姨還需平台 / 老闆人工二次媒合
- **隱私敏感**: 客戶家庭資料 (老人 / 嬰兒 / 寵物) 涉個資, 雲端版需加密 + 客戶同意 + 資料留存政策

---
*cleanmate = Multinomial Naive Bayes (Bayes 1763) × 台灣家政服務 客戶需求 → 阿姨 specialty 分類 niche = 100+ 件歷史 pairing 學需求模式, 退服率 30% → 10%, 客戶 1 次匹配對 vs 試 3 次。*
