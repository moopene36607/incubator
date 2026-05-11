# constsim — 台灣中小型裝潢 / 建築工程 k-NN 估價工具

**「我家衛浴翻修 6 坪 標準等級, 找了 3 家報價 NT$28-180 萬差 6 倍, 哪個合理?」** 用 k-Nearest Neighbors (Cover & Hart 1967) 從 40+ 歷史工程案例 (project_type / 坪數 / 屋齡 / 材料 / 工期 / 地區 / 水電遷移) 找最相似 k 件 → 報價區間 (mean ± std) + 對照案例 + 防偷工問題 + 議價腳本。

## 痛點

台灣裝潢 / 建築工程市場:
- **中小型裝潢公司 / 工程行**: ~5,000 家 (1-30 人)
- **個人工頭 / 設計師接案**: ~30 萬
- **每年裝潢需求**: 全台 ~30 萬戶換屋 / 新婚 / 中年翻修
- **核心 pain group**: 一般家庭業主每 5-10 年裝潢一次,非專業根本不會估價

**業主痛點** (PTT home-sale / home-rent / Dcard 居家 / FB「裝潢交流」5-10 萬人社群):
- 「找 3 家報價, 差距 NT$50-200 萬」(每週問)
- 「設計師說 NT$200 萬 / 工頭說 NT$120 萬 / 親戚介紹說 NT$80 萬, 信誰?」
- 「不知道哪邊在加價 / 哪邊在偷工」
- 「業主簽約後才發現拆除費、垃圾清運另計, 預算超支 20-40%」

**業者痛點** (裝潢公司 / 工頭):
- 自己內部 quote 也常憑感覺, 偶爾接到「賠錢工」
- 沒系統化資料庫, 每次案件從頭算

**現有資源**:
- 591 / 設計家 listing 沒估價
- 工頭憑經驗 (主觀, 落差大)
- 設計師收費 NT$5,000+ 一次估算 (太貴, 小工程不划算)
- 比價平台 (PromoteIT / 統包 100) 只媒合不估價

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(constsim 補的) |
|---|---|---|
| 591 設計裝潢 / 設計家 listing | 照片 + 案例展示 | 不算估價區間, 沒同類比對 |
| 設計師 / 工頭 自己 quote | 主觀估價 | 落差大 / 偏高或偏低 / 無依據 |
| 比價平台 (PromoteIT) | 媒合多家報價 | 純收 quote, 不分析合理性 |
| Excel 自己記 | 純手動 | 沒 kNN, 樣本不夠 |
| ChatGPT 一次問 | 一次性建議 | 不能跑 weighted kNN, 沒持續 case database |
| 房屋估價 (591 估價) | 房價, 非裝潢 | 不同 use case |

**Gap 結構性**: k-NN regression (Cover & Hart 1967) 學術成熟 58 年,**沒人做成台灣裝潢 / 建築估價 SaaS**。Google「裝潢估價 k-NN 中文」零本土 SaaS。

## 架構 — Weighted k-NN Regression (44th 條 AI pattern)

```
40+ 歷史 cases (features + final_quote)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Custom distance metric:                       │
│   d(query, case) = sqrt(                      │
│     Σ_numeric w_i × ((q-c)/scale_i)²          │
│     + Σ_categorical w_j × (q ≠ c)             │
│   )                                            │
│ auto_scale: scale = pop stdev per numeric     │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ k-NN regression:                              │
│   sort cases by distance                      │
│   top-k → weighted average                    │
│     wᵢ = 1 / (dᵢ + ε)                        │
│     pred = Σ wᵢ × target_i / Σ wᵢ             │
│   confidence band = mean ± std(targets)       │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Diagnostics:                                  │
│   • LOO cross-validation (MAE / MAPE / RMSE)  │
│   • Pearson correlation (numeric features)    │
│   • Per-category mean (categorical features)  │
│   • Per-feature distance contribution         │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + statistics + dataclass + collections):
- `FeatureSpec`: declare each feature's kind (numeric/categorical), weight, scale
- `auto_scale`: set scale = population stdev per numeric feature
- `weighted_distance`: Euclidean (numeric) + Hamming (categorical) hybrid
- `knn_predict`: distance-weighted aggregation + std-based confidence band
- `loo_evaluate`: leave-one-out CV for honest accuracy estimate
- `numeric_feature_correlations`: Pearson r per numeric feature
- `categorical_feature_mean_diff`: per-category target mean diagnostics

**LLM 只負責**: 寫 250-330 字「估價解讀 + 防偷工問題 + 議價腳本 + 風險」
**LLM 絕不負責**: 計算 prediction / confidence band / distances (數字 100% 來自 k-NN)

## 使用示例

```bash
# 純函式模式 (無 API key)
python constsim.py --data samples/construction_quotes.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python constsim.py --data samples/construction_quotes.json

# k 鄰居數 (預設 5)
python constsim.py --k 7
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陳家衛浴翻修 6坪 標準 台北 18年 4週 含水電):

| 指標 | 值 |
|---|---|
| **預估** | NT$1,163 K (中位估價) |
| **不確定性** | ±NT$433 K |
| **合理區間** | NT$731K — NT$1,596K |
| LOO MAPE | 55.9% (40 件 prototype 樣本小) |

**Top 5 近鄰**:
| Case | dist | 類型 / 坪 / 等級 / 工期 | NT$ K |
|---|---|---|---|
| C036 | 1.83 | 衛浴翻修 3坪 標準 8w | 650 |
| C019 | 2.57 | 衛浴翻修 6坪 經濟 4w | 913 |
| C020 | 2.61 | 衛浴翻修 5坪 高級 8w | 1550 |
| C015 | 2.96 | 衛浴翻修 6坪 高級 12w | 1676 |
| C028 | 3.10 | 廚房改造 4坪 標準 4w | 1334 |

→ 4/5 都是衛浴翻修, 業主可拿 NT$73-160 萬作議價區間 + 報價超出 NT$192 萬以上算偏高 / 低於 NT$51 萬算可能偷工。

## 目標市場

- **TAM**:
  - 中小型裝潢 / 建築工程業 ~5,000 家公司 + 30 萬個人工頭 / 設計師
  - 每年 ~30 萬戶業主有裝潢需求 = 60 萬潛在用戶 (業主 + 業者雙邊)
- **WTP 錨點**:
  - 設計師估價 NT$5,000+ 一次 vs Solo NT$199/月 = **25-50x 便宜**
  - 業主簽錯約損失 NT$30-100 萬, 工具一次 NT$199 = 1500-5000x 防損
  - 業者一次接賠錢工 NT$10-50 萬, Solo NT$499 = 200-1000x 防虧

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 5 估價/月 | 業主試用 |
| **Solo** | NT$199/月 | 無限估價 + 對照案例 + 議價腳本 | 個人業主 |
| **Contractor** | NT$499/月 | 內部 case DB + 多人協作 + 客戶報價輸出 | 工頭 / 設計師 |
| **Studio** | NT$1,999/月 | 設計公司 5-30 案管理 + 案例匯入 + API | 中小設計公司 |
| **Brand** | NT$8,000+/月 | 連鎖建設 / 系統家具品牌 + 跨區域 benchmark | 系統家具 / 連鎖建設 |

## Distribution

- **PTT home-sale / home-rent / Decoration / Soft_Job (工程)** 板長尾關鍵字
- **Dcard 居家 / 室內設計 / 工程**
- **FB「裝潢交流」5-10 萬人社群** 案例分享
- **YouTube 居家 KOL** (沼澤工作室 / 家空間 Honger / 設計家陳新建築) 案例
- **591 / 設計家 / 100 室內設計** 整合 partner
- **室內設計師公會 / 建築師公會** B2B BD
- **建材展 / 居家裝潢展** (台北 9 月) booth

## TAM

- 1% × 30 萬業主 = 3,000 × NT$199 = **月 NT$60 萬**
- + Contractor 1,000 × NT$499 = NT$50 萬/月 (30 萬個人工頭中 0.3%)
- + Studio 300 × NT$1,999 = NT$60 萬/月
- + Brand 50 × NT$8K = NT$40 萬/月
- 總計 **月 MRR NT$210 萬 / 年 ARR NT$2,520 萬**
- 加滲透 + 橫移港新馬 / 日韓裝潢 → 翻倍至 **NT$5,000 萬-1 億 ARR**

## 風險與限制

- **40 件 prototype 太小** — 真實 launch 需 ≥ 300 件多區域 / 年份 / 風格, 鼓勵設計公司 / 業者 contribute case 換取免費
- **Feature weights hand-tuned** — project_type 8.0 / grade 4.0 是 prototype, Pro 版用 cross-validated grid search
- **不考慮通膨 / 物料漲跌** — 2024 vs 2026 報價需 year-month feature 調整
- **業主隱性需求未量化** — 風格 / 偏好品牌 / 趕工 / 老人 / 寵物在家
- **不取代專業估價** — 工具給合理區間, 詳細報價需實地丈量 + 設計圖 + 材料清單
- **k-NN 易被 outlier 拖累** — 1 件高 / 低價案會偏移, Pro 版加 outlier rejection (median k-NN)
- **隱私敏感** — 客戶報價含預算 + 地址, 雲端版需匿名化 + 業者同意 + 資料留存政策

---
*constsim = Cover & Hart 1967 k-Nearest Neighbors × 台灣裝潢 / 建築估價 niche = 從 40 件歷史找最相似 k 件 → 業主合理區間 + 議價腳本, 業者內部 quote 防虧本錨點。*
