# kindergrid — 台灣 0-6 歲家長挑幼兒園 Hierarchical Clustering 推薦工具

**「我家小孩明年要上幼兒園,看了 8 家還是不知道怎麼選,每家都自稱蒙特梭利 / 雙語 / 開放探索」** 用 Ward (1963) Hierarchical Agglomerative Clustering + Ester et al. (1996) DBSCAN 從 30+ 園所 10 維 feature 自動分成 5 個教育理念 cluster,結合家長偏好向量推薦 cluster + within-cluster 帶看清單 + AI 寫帶看 checklist。

## 痛點

台灣 0-6 歲家庭挑園:
- **公托 / 公幼**: ~6,000 家 (公定價, 抽籤)
- **私立托嬰中心**: ~8,000 家 (NT$25-50K/月)
- **私立幼兒園**: ~10,000 家 (NT$8-30K/月)
- **共計 ~24,000 家**, 每年新增 ~14 萬 0 歲嬰兒需 0-6 歲解決方案
- **0-6 歲家庭 ~50 萬戶** 都在每階段挑園

**核心痛點** (親子王國 / 媽寶 / Dcard 親子 / FB「0-6 歲家長交流」5-15 萬人社群):
- 「看了 8 家還是不知道怎麼選」(典型)
- 「每家都說自己蒙特梭利, 怎麼分真假?」
- 「全美 NT$45K 真的值得嗎?vs 雙語 NT$25K vs 中文+ 英文課 NT$15K」(價格焦慮)
- 「想找華德福但全台只有 3 家在我可接送範圍」(地理 + 風格雙重限制)
- 「比較表怎麼做? Excel 列 8 家 10 個 features 看到眼花」

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(kindergrid 補的) |
|---|---|---|
| 衛福部全國公私立幼兒園查詢 | 名單 / 立案 / 地址 | 不分析教育理念風格,不做 clustering |
| BabyHome / 1111人力銀行 兒童版 | 名單 + 家長評論 | 純列表, 無風格分群 |
| 親子天下 / 兒童雜誌 排行 | 每年「百大幼兒園」 | 主觀評選, 不個人化配對 |
| 自己 Excel 比較 | 純手動 | 30 家 × 10 features 主觀記錯 |
| 兒童教育顧問 NT$5-15K | 一對一諮詢 | 太貴 + 限定區域 |
| ChatGPT 直接問 | 一次性建議 | 不能跑 Hierarchical clustering, 沒個人化偏好向量 |

**Gap 結構性**: HAC (Ward 1963) + DBSCAN (Ester 1996) 學術成熟 30-60 年,**沒人做成台灣 0-6 歲家長挑園 SaaS**。Google「幼兒園 hierarchical clustering 中文」零本土 SaaS 結果。

## 架構 — Hierarchical Agglomerative Clustering + DBSCAN (42nd 條 AI pattern)

```
30 schools × 10-dim features (教育理念向量)
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Hierarchical Agglomerative (Ward):          │
│   1. Start each school as own cluster       │
│   2. Find pair minimizing ΔESS              │
│      = (n_i × n_j)/(n_i + n_j) × d²(μ,μ)    │
│   3. Merge, update Lance-Williams           │
│   4. Repeat until 1 cluster (29 merges)     │
│   5. Cut dendrogram at k clusters           │
└─────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Characterize clusters:                      │
│   centroid, dominant features (rel to       │
│   global mean), size                        │
└─────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ DBSCAN (parallel):                          │
│   ε-radius + min_pts → core / border / noise│
│   Noise = unique-style schools (特色)        │
└─────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Recommendation:                              │
│   Family preference vector → closest cluster │
│   Top-N within cluster by Euclidean         │
└─────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + dataclass + collections):
- `euclidean / squared_euclidean / cosine_similarity`: distance metrics
- `hac_ward`: full HAC with Ward linkage + 完整 merge history + snapshots
- `cut_dendrogram`: flat clustering at any k
- `dbscan`: density-based clustering with noise points
- `characterize_clusters`: per-cluster centroid + dominant features (rel to global mean)
- `recommend_from_clusters`: family-vector → closest cluster + top-N within

**LLM 只負責**: 寫 250-330 字「帶看 checklist + 必問 3 問題 + 妥協點 + 風險」
**LLM 絕不負責**: 計算 distance / centroid / clusters (數字 100% 來自純函式)

## 使用示例

```bash
# 純函式模式 (無 API key)
python kindergrid.py --data samples/kindergartens.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python kindergrid.py --data samples/kindergartens.json

# 切到 6 群 + top 8 推薦
python kindergrid.py --n-clusters 6 --top 8
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陳家媽媽預算 NT$32K + 英文 70%):

5-cluster 自動歸類 (30 家 × 5 cluster):

| Cluster | 規模 | 主導特徵 | 真實風格 (對比) |
|---|---|---|---|
| C48 | 6 | 蒙特梭利 8.9 / 學費 24K | 蒙特梭利 6/6 ✓ |
| C50 | 2 | 英文 93% / 學費 40K | 全美 2/2 ✓ |
| C52 | 6 | 作業量 6.3 / 班級 25 | 傳統 6/6 ✓ |
| C53 | 12 | 華德福 6.6 / 戶外 2.3h | 華德福+開放 12/12 (合併) |
| C54 | 4 | 英文 74% / 學費 42K | 雙語 4/4 ✓ |

**家長推薦**: C54 (中高雙語) Top 4 都是真實雙語園, K017 距離 4.4 最佳。

## 目標市場

- **TAM**:
  - 0-6 歲家庭 ~50 萬戶 × 平均 2 次轉園 (托嬰 → 幼兒園) = 100 萬挑園 events
  - 30% 高關注家庭 (預算 NT$20K+) = 30 萬潛在用戶
- **WTP 錨點**:
  - 兒童教育顧問 NT$5-15K 一對一 vs Solo NT$199/月 = **25-75x 便宜**
  - 簽錯園所換校麻煩 + 孩子轉換期 = 經濟 + 情緒成本

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 10 家比較 / 月 + Top 3 | 試用 |
| **Solo** | NT$199/月 或一次性 NT$799/挑園週期 | 無限家 + Top 10 + 偏好調整 + LINE 推播 | 個人家庭 |
| **Family** | NT$399/月 | 多孩 (大寶 + 二寶) + 配偶共識 + 月度追蹤 | 多孩家庭 |
| **Consultant** | NT$2,999/月 | 兒童教育顧問 client dashboard + 批量 | 親職顧問 |
| **District** | NT$15,000+/月 | 縣市教育局 + 公托抽籤輔助 + 數據 | 政府 |

## Distribution

- **親子王國 / 媽寶 / Dcard 親子 / FB「0-6 歲家長交流」5-15 萬人** 社群案例分享
- **YouTube 親子 KOL** (Roxy 媽媽 / 阿包醫生 / 親職作家陳安儀) 案例合作
- **媽咪愛 / 寶寶饗食 / 育兒寶** APP 整合 partner
- **兒童教育顧問** B2B BD
- **0-6 歲博覽會 / 嬰兒博覽會** 台北 4 月 / 12 月 booth
- **公托抽籤季** (11-12 月) 縣市政府 partner
- **大學職涯中心 / 新婚博覽會** partner

## TAM

- 1% × 30 萬 = 3,000 × NT$799 一次性 = 年 NT$240 萬 + Solo 月訂閱
- + Solo 2,000 × NT$199 × 3 月 = 月 NT$40 萬 (挑園期 3-6 月)
- + Family 800 × NT$399 = NT$32 萬/月
- + Consultant 100 × NT$2,999 = NT$30 萬/月
- + District 10 × NT$15K = NT$15 萬/月
- 總計 **年 ARR NT$2,000-4,000 萬**
- 加滲透 + 橫移港新馬 / 日韓 → 翻倍至 **NT$5,000 萬-1 億 ARR**

## 風險與限制

- **Ward linkage 假設特徵單位可比** — 學費 (千元) vs class_size (人) vs 分數 (0-10) 量級不同, Pro 版加 z-score 標準化
- **n_clusters 是先驗** — prototype 設 5, Pro 版用 silhouette / elbow / gap statistic 自動選
- **30 家 prototype 太小** — 真實 launch 需爬蟲 ≥ 500 家 + family-validated feature labels (公托 / 私立 / 教育部官方資料)
- **DBSCAN ε 是超參數** — 需要對 dataset 調, Pro 版用 k-distance 圖法自動找
- **特徵 hand-crafted** — 蒙特梭利 / 華德福 程度由人工 annotate, 真實 launch 用 NLP 從學校官網描述自動抽取
- **不取代實地參訪** — 推薦清單 = 帶看候選, 最後決策仍需家長自己感受教學環境 / 老師氣質 / 與孩子個性契合
- **公托抽籤是制度約束** — 工具可以推薦但不能保證抽中, 須搭配 backup 私立方案

---
*kindergrid = Ward 1963 Hierarchical Clustering + Ester 1996 DBSCAN × 台灣 0-6 歲家長挑園 niche = 30+ 家自動分 5 教育理念 cluster + 個人偏好向量推薦帶看清單 + 自動找出特色 outlier 園所。*
