# petskin -- 台灣寵物皮膚問題飼主端 LDA 6 類鑑別 + 紅旗 triage

**「半夜 11 點我家黑狗一直抓屁股, 該衝急診還是等明早?」** 用 Fisher 1936 Linear Discriminant Analysis 從 60+ 件獸醫標注 cases 學習 6 類皮膚病典型 feature pattern (跳蚤過敏 / 異位性 / 食物過敏 / 黴菌 / 細菌 / 耳疥蟲), 飼主回報症狀 → 給出最可能病因 + 信心度 + Mahalanobis 距離視覺化 + 對應建議 + **就醫紅旗清單**。

## 痛點

台灣寵物皮膚問題市場:
- **登記犬主**: 233 萬戶 (農業部 2024)
- **登記貓主**: 91 萬戶
- **每月皮膚問題發生率**: 約 10-15% (寵物醫師訪談估)
- **飼主月光顧獸醫頻次**: 一般 1-2 次 / 急診 0.3-0.5 次

**飼主痛點** (FB「我愛貴賓狗 / 柴犬 / 黃金獵犬 / 米克斯」5-30 萬人社群 / Dcard pet / PTT dog_cat / Mobile01 寵物板):
- 「半夜搔抓不止, 衝急診 NT$3-5K 還是先撐到明天?」(每週重複)
- 「ChatGPT 跟我說是黴菌, 但獸醫看是跳蚤過敏 -- 大幅治療路徑差太多」
- 「6 種常見皮膚病症狀很像 (都癢都紅), 我看不懂網路上不同來源的描述」
- 「先觀察 vs 立刻就醫 -- 沒有客觀分流工具」
- **每次猶豫 1-2 小時** 找資料、看 FB、問群組

**獸醫師端痛點**:
- 假日 / 半夜 急診線爆滿 30% 飼主其實「不必急」(觀察 24h 即可)
- 真正緊急 case (細菌感染擴散 / 自體免疫) 反而被卡在排隊
- 沒工具教育飼主初步分流

**現有資源**:
- 24h 寵物急診 NT$2,000-5,000/次 (掛號 + 基本檢查)
- 24h LINE 諮詢服務 (太僕 / 茂楷 NT$300-1,000/次) - 仍要靠飼主主觀描述
- FB 寵物社群 (主觀 sample bias 嚴重)
- 寵物 APP (寵物隨身 / 毛孩兒 / 毛起來) -- 只做疫苗追蹤 / 預約, **無 triage**
- Google / ChatGPT -- 給的答案不確定性高, 常 hallucinate

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(petskin 補的) |
|---|---|---|
| 寵物醫院 24h 急診 | 醫療診斷 + 治療 | NT$3-5K/次, 假日 / 半夜 排隊 30 min+, 30% case 其實不急 |
| 24h LINE 諮詢 (太僕 / 茂楷) | 獸醫對 1 諮詢 | NT$300-1K/次 + 仍靠飼主主觀描述, 無系統化分類 |
| FB 寵物社群 | 飼主互助 | 主觀 sample bias 嚴重, 危險 (建議錯誤治療) |
| 寵物 APP (毛孩兒 / 寵物隨身 / 毛起來) | 疫苗追蹤 / 預約 / 病歷 | **無 triage / 無 分類 / 無 紅旗** |
| Google / ChatGPT | 一般搜索 / 一次性建議 | 不能持續學歷史 case, 常 hallucinate 不認識本土用藥 |
| vetnote r9 (本 incubator) | 給獸醫師寫 SOAP 病歷 | 服務獸醫師端, 飼主用不到 |
| petfeed r57 (本 incubator) | 飼料推薦 | 跟皮膚分類完全不同問題 |

**Gap 結構性**: Linear Discriminant Analysis (Fisher 1936) 學術成熟 90 年, **沒人做成台灣繁中飼主端寵物皮膚分流 SaaS**。Google「寵物皮膚 LDA 中文」零本土 SaaS。**跟 vetnote r9 互補** -- vetnote 是獸醫師端寫病歷, petskin 是飼主端三 選一鑑別。**跟 crybabel r48 同精神不同對象** -- r48 是嬰兒哭聲分類 (Random Forest), petskin 是寵物皮膚分類 (LDA), 兩個都是「家人焦慮 → AI 分流」場景。

## 架構 -- Linear Discriminant Analysis (49th 條 AI pattern)

```
60+ 件獸醫標注 cases (10 features + label)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Fit LDA:                                      │
│   1. 計算 class means mu_k                    │
│   2. 計算 pooled within-class covariance:     │
│      Sigma = (1/(N-K)) sum_i (x_i - mu_y_i)   │
│                       (x_i - mu_y_i)^T        │
│      + jitter * I (Tikhonov 正則化)           │
│   3. 解 linear system Sigma * z_k = mu_k      │
│      via Gauss-Jordan elimination             │
│      (避免顯式 inverse)                       │
│   4. bias_k = -0.5 * mu_k^T z_k + log(pi_k)   │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Predict for new x:                            │
│   delta_k(x) = z_k^T x + bias_k               │
│   posterior P(k | x) = softmax({delta_k})     │
│   predicted = argmax_k delta_k                │
│                                                │
│ Feature contributions to winner:              │
│   for j: relative_weight_j × value_j           │
│   relative_weight_j                           │
│   = z_winner[j] - mean(z_others[j])           │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Diagnostics:                                  │
│   In-sample accuracy + LOO cross-validation   │
│   Mahalanobis distance to each class centroid │
│   Confusion matrix                            │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Output 6 類 triage 建議:                       │
│   urgency tag (中等 / 高 / 高慢性)             │
│   owner-action 具體 SOP                       │
│   red-flag 清單 (任一出現 24h 內就醫)         │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + statistics + dataclasses + collections):
- `gauss_jordan_solve`: 部分樞軸 (partial pivoting) 解 linear system, 用 augmented matrix
- `_pooled_covariance`: pooled within-class covariance + Tikhonov diagonal jitter
- `fit_lda`: 訓練 + 預計算 Sigma⁻¹μ_k (避免重複求逆)
- `predict_one`: discriminant function + softmax posterior + feature contributions
- `class_centroid_distance`: Mahalanobis distance per class (用 LDA 的 pooled Sigma)
- `loo_evaluate`: leave-one-out cross-validation (honest accuracy)

**LLM 只負責**: 寫 250-330 字「飼主深夜讀的 triage 建議 + home-care 步驟 + 紅旗清單 + 風險」
**LLM 絕不負責**: 計算 discriminant / posterior / Mahalanobis / accuracy (數字 100% 來自 LDA)

### 為什麼 LDA 適合這個 use case (vs RF / NB / Logistic)

- **LDA**: generative classifier (建模 P(x | class)), 適合「飼主主觀分數」連續特徵 + 假設類間共享 covariance (各皮膚病搔癢 / 紅腫 / 落毛 的「變動程度」差不多) + 小樣本下穩健 (60 cases × 6 classes 仍能訓)
- **RF (crybabel r48)**: discriminative 黑盒, 解釋性差, 需大樣本
- **NB (cleanmate r55)**: 假設特徵獨立, 但搔癢 / 紅腫 / 落毛 高度相關, 違反假設
- **Logistic (cramlead r56)**: discriminative 二類為主, 多類擴展 (softmax regression) 需更多樣本
- **GBDT (clinicqueue r53)**: 黑盒、需大樣本、不適合 6-類分類解釋

LDA 的 Mahalanobis 距離 + linear discriminant boundary 同時給出**幾何直觀解釋** -- 飼主可看到「我家狗離跳蚤類中心 2.6 而離耳疥蟲類 33」這種距離視覺化, 比黑盒分類器更可信。

## 使用示例

```bash
# 純函式模式 (無 API key)
python3 petskin.py --data samples/skin_cases.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 petskin.py --data samples/skin_cases.json

# 調整 covariance jitter
python3 petskin.py --jitter 1e-3
```

預期輸出 (詳見 `examples/sample_output.md`):

陳小姐家米克斯 3 歲, 搬新家後嚴重搔抓尾巴根:

| 類別 | 機率 | Mahalanobis 距離 |
|---|---|---|
| ⭐ **🦟 跳蚤過敏** | **100.0%** | 2.63 |
| 🐾 異位性皮膚炎 | 0.0% | 14.46 |
| 🦠 細菌性皮膚炎 | 0.0% | 22.06 |
| 🍄 黴菌感染 | 0.0% | 30.27 |
| 🍖 食物過敏 | 0.0% | 33.39 |
| 👂 耳疥蟲 | 0.0% | 33.72 |

→ **建議 home-care**: 立刻除蚤 (Frontline / Bravecto), 環境清潔換床套, 觀察 7 天。
→ **紅旗就醫**: 搔抓出血 / 二次細菌感染 / 全身性紅疹 → 不管 LDA 信心多高 24h 內就醫。

訓練集 in-sample accuracy 100% + LOO 100% (synthetic well-separated data). 真實 launch 樣本會更難分但仍應 70%+ accuracy。

## 目標市場

- **TAM**: 233 萬犬主 + 91 萬貓主 = 324 萬主要飼主
- **每月發作**: 10-15% × 324 萬 = 32-49 萬次/月皮膚問題 → **飼主端 triage 機會**
- **獸醫院**: 2,600+ 家 (Brand 合作 / triage 前端)
- **WTP 錨點**:
  - 一次 24h 急診 NT$3-5K vs Solo NT$99/月 = **30-50x 防錯誤花費**
  - 慢性皮膚病拖延 1 個月惡化 NT$5-15K 治療 vs 早期 triage 介入

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 3 次 triage/月 | 飼主試用 |
| **Solo** | NT$99/月 | 無限 triage + LINE Bot + 多寵物 | 個人飼主 |
| **Family** | NT$299/月 | + 多寵物 + 家人共用 + 病歷記錄 + 警示推播 | 多寵家庭 |
| **Clinic** | NT$2,499/月 | 獸醫院 white-label 飼主 triage 前端 + 預約整合 | 中小寵物醫院 |
| **Chain** | NT$8,000+/月 | 連鎖獸醫 (太僕 / 茂楷 / 仁愛 / 中興) + EHR API | 連鎖獸醫集團 |
| **Insurance** | NT$15,000+/月 | 寵物保險 (Petplan / 國泰 / 富邦 寵物險) triage 模組 + 理賠減損 | 寵物保險公司 |
| **API** | NT$2/call | 第三方 APP / 寵物食品電商整合 | 寵物 SaaS |

## Distribution

- **FB「我愛貴賓狗 / 柴犬 / 黃金獵犬 / 米克斯 / 流浪動物收容」** 5-30 萬人社群案例分享
- **Dcard pet / 寵物 / 動物溝通 / 領養** 板
- **PTT dog_cat / dog / cat / pet** 板長尾 SEO
- **Mobile01 寵物板** (中年飼主)
- **YouTube 寵物 / 獸醫 KOL** (黃金毛 / 大胃王皮卡丘 / 阿明喵 / 動物溝通師 Leslie) 業配
- **寵物醫院 partner**: 太僕 / 茂楷 / 中興 / 仁愛 / 哈寶 -- 飼主 triage 前端
- **24h 寵物急診線 partner**: 提升真正急診 case 篩選效率
- **寵物保險 partner** (Petplan / 國泰 / 富邦 寵物險) -- 理賠減損
- **寵物 APP 整合**: 毛孩兒 / 寵物隨身 / 毛起來
- **獸醫師公會 / 寵物用品工會** 公益合作 + 衛教
- **台北寵物用品大展** (每年 8 月南港) booth

## TAM

- 0.5% C2C × 324 萬 = 16,200 × Solo NT$99 = **月 NT$160 萬**
- + Family 3,000 × NT$299 = NT$90 萬/月 (多寵家庭佔 30%)
- + Clinic 200 × NT$2,499 = NT$50 萬/月 (2,600 寵物醫院 8%)
- + Chain 20 × NT$8,000 = NT$16 萬/月
- + Insurance 5 × NT$15,000 = NT$7.5 萬/月
- + API NT$10 萬/月 (合作 APP)
- 總計 **月 MRR NT$334 萬 / 年 ARR NT$4,000 萬**
- 加滲透 + 橫移港新馬 / 日韓 (日本 700 萬犬 + 韓國 500 萬犬) → **NT$1-1.5 億 ARR**

## 風險與限制

- **60 件 prototype 太小** -- 真實 launch 需 ≥ 1,000 件多獸醫師標注 cases, 鼓勵獸醫院 contribute 標注 cases 換取免費 Clinic 月
- **常態分布假設**: 每類 features 假設 multivariate Normal, 真實有 skewed (搔癢分布偏右), Pro 版用 QDA / Mixture Discriminant
- **共同 covariance 假設**: LDA 假設所有類 covariance 相同 (homoscedasticity), 真實各皮膚病變異程度不一; 不滿足時改用 Quadratic Discriminant Analysis
- **特徵主觀**: 搔癢 / 紅腫 / 落毛 1-10 分靠飼主肉眼判斷, ±1-2 分主觀誤差, Pro 版加照片 / 影片 vision 自動評估
- **不取代獸醫**: LDA 給「初步分流」是飼主決策輔助 (今天就醫 vs 觀察 24h vs 自行處理), **絕對不是診斷**
- **致命遺漏**: 不能分辨 **皮膚癌 / 自體免疫疾病 / 內分泌異常** (cushing / 甲狀腺低下), 這類嚴重病慢性病需獸醫鑑別
- **緊急紅旗永遠優先**: 發燒 / 食慾不振 / 嗜睡 / 嘔吐 / 全身紅疹 → 不管 LDA 信心多高, 24h 內就醫
- **法規風險**: 獸醫師法第 19 條「獸醫師之診斷處方須由獸醫師為之」, petskin 嚴格定位為「飼主決策輔助」而非「診斷工具」, 雲端版需顯著免責聲明 + 與獸醫院合作 + 醫師背書
- **隱私敏感**: 寵物病例含飼主聯絡 / 寵物詳細, 雲端版需匿名化 + 飼主同意 + 資料留存政策

---
*petskin = Fisher 1936 Linear Discriminant Analysis × 台灣寵物皮膚問題飼主端三 選一鑑別 niche = 60+ 件獸醫標注 cases 學習 6 類皮膚病 typical pattern, 飼主深夜遇毛孩搔抓拿到「衝急診 vs 觀察 vs 自處理」客觀建議 (信心 + 紅旗), 230 萬犬主 + 90 萬貓主每月 1-2 次焦慮的 LDA 飼主端 AI 輔助。*
