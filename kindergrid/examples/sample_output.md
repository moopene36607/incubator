# kindergrid — 陳家 幼兒園挑選 Hierarchical Clustering 報告

**Marketplace**: 30 家幼兒園 / 托嬰中心
**Features**: 10 維 (學費 (K NTD/月), 班級人數, 英文比例 (%), 戶外時間 (小時/天), 蒙特梭利程度 ...)
**Hierarchical merges**: 29 (Ward linkage)
**Cut to**: 5 clusters

## 🎯 家長偏好

_陳小婷 (台北雙薪 30 歲 媽媽), 想找預算月 NT$25-35K 的幼兒園, 重視英文 (希望 ≥ 60%) + 適量戶外 + 老師親師溝通頻繁_

| 偏好 | 數值 |
|---|---|
| 學費 (K NTD/月) | 32 |
| 班級人數 | 18 |
| 英文比例 (%) | 70 |
| 戶外時間 (小時/天) | 1.5 |
| 蒙特梭利程度 | 4 |
| 華德福程度 | 2 |
| 開放探索程度 | 4 |
| 傳統結構程度 | 5 |
| 作業量 | 3 |
| 親師溝通頻率 | 8 |

## 🏫 推薦 cluster: C54

**這個 cluster 的主導特徵**:
- `英文比例 (%)`: 74.05
- `學費 (K NTD/月)`: 41.65
- `傳統結構程度`: 6.22

### Top 4 推薦帶看清單 (cluster 內按距離排)

| # | 學校 | 真實風格 (對比) | 距離家長偏好 |
|---|---|---|---|
| 1 | 幼兒園 #17 (K017) | 全美 / 雙語 bilingual | 4.41 |
| 2 | 幼兒園 #15 (K015) | 全美 / 雙語 bilingual | 7.22 |
| 3 | 幼兒園 #18 (K018) | 全美 / 雙語 bilingual | 19.09 |
| 4 | 幼兒園 #16 (K016) | 全美 / 雙語 bilingual | 19.72 |

## 📊 所有 cluster 摘要

| Cluster | 規模 | 主導特徵 | 樣本學校 |
|---|---|---|---|
| C53 | 12 | `waldorf_score` 6.6, `outdoor_hr_per_day` 2.3 | 開放探索 open, 開放探索 open, 開放探索 open |
| C48 | 6 | `montessori_score` 8.9, `tuition_NT_K` 23.9 | 蒙特梭利 montessori, 蒙特梭利 montessori, 蒙特梭利 montessori |
| C52 | 6 | `homework_load` 6.2, `traditional_score` 7.9 | 傳統結構 traditional, 傳統結構 traditional, 傳統結構 traditional |
| C54 | 4 | `english_pct` 74.0, `tuition_NT_K` 41.6 | 全美 / 雙語 bilingual, 全美 / 雙語 bilingual, 全美 / 雙語 bilingual |
| C50 | 2 | `english_pct` 93.1, `tuition_NT_K` 39.8 | 全美 / 雙語 bilingual, 全美 / 雙語 bilingual |

## 🔍 DBSCAN 噪聲偵測 (找出風格 outlier)

- DBSCAN with ε=12, min_pts=2 → **1** dense cluster + **6** noise points
- Noise / unique 學校 (跟主流不一樣):
  - 幼兒園 #13 (全美 / 雙語 bilingual)
  - 幼兒園 #14 (全美 / 雙語 bilingual)
  - 幼兒園 #15 (全美 / 雙語 bilingual)
  - 幼兒園 #16 (全美 / 雙語 bilingual)
  - 幼兒園 #17 (全美 / 雙語 bilingual)
- **Pro 用法**: noise points 是「特色園所」, 適合有特殊需求家庭 (e.g., 雙語+體育 / 蒙特梭利+早療)

## 🌳 Dendrogram 高度視覺

```
merge → C 44 (n= 4): h=    30.6 
merge → C 45 (n= 2): h=    32.1 
merge → C 46 (n= 2): h=    41.5 
merge → C 47 (n= 4): h=    45.3 
merge → C 48 (n= 6): h=    59.3 
merge → C 49 (n= 5): h=    62.5 
merge → C 50 (n= 2): h=    65.0 
merge → C 51 (n= 8): h=   124.4 
merge → C 52 (n= 6): h=   147.5 
merge → C 53 (n=12): h=   286.1 
merge → C 54 (n= 4): h=   300.6 
merge → C 55 (n= 6): h=   500.4 █
merge → C 56 (n=18): h=   558.4 █
merge → C 57 (n=24): h=  1051.3 ██
merge → C 58 (n=30): h= 18871.5 ████████████████████████████████████████
```
- 高度跳躍處 (e.g., 從 h=1000 → h=18000) = 自然 cluster boundary

## ⚠️ Hierarchical Clustering 模型假設與限制

- **Ward linkage 假設特徵單位可比**: 學費 (千元) vs class_size (人) vs 分數 (0-10) 量級不同,Pro 版加 z-score 標準化
- **n_clusters 是先驗**: prototype 設 5, Pro 版用 silhouette / elbow / gap statistic 自動選
- **30 家 prototype 太小**: 真實 launch 需爬蟲 ≥ 500 家 + family-validated feature labels
- **DBSCAN ε 是超參數**: 需要對 dataset 調 (12 = 1.2 std), Pro 版自動 k-distance 圖法找
- **特徵 hand-crafted**: 蒙特梭利 / 華德福 程度由人工 annotate, 真實 launch 用 NLP 從學校描述自動抽取
- **不取代實地參訪**: 推薦清單 = 帶看候選, 最後決策仍需家長自己感受教學環境 / 老師氣質

---
*kindergrid = Ward 1963 Hierarchical Clustering + Ester 1996 DBSCAN × 台灣 0-6 歲家長挑園 niche = 從 30 家自動分 5 教育理念 cluster + 對家長偏好推薦帶看清單。*

## 🤖 AI 兒童教育顧問建議

陳媽媽,**C54 cluster 是「中高價位雙語園」**,英文比例 74% + 學費 NT$42K 中位 + 班級 17 人,符合你的「英文 ≥ 60% + 中等班級」核心需求。Top 4 都是真正全美/雙語園, K017 (距離 4.4) 跟你偏好最貼合 — 應該第一個看。

**3 個帶看時必問的問題**:① **「英文老師是 native speaker 嗎? 流動率多高?」** 雙語園最大坑是「掛羊頭賣狗肉」,老師都是台籍英文老師且每年大換血;② **「親師溝通實際用什麼工具? 多久一次? 老師回覆速度?」** 你重視 parent_engage 8 但很多雙語園其實老師很忙,LINE 訊息 3 天才回;③ **「戶外時間 1.5h 是『公園+教室陽台』還是『校園草地+真正運動』?」**雙語園校地通常小,戶外時間常常打折扣。

**2 個你的偏好沒被滿足、要妥協的點**:① **預算上限 NT$35K, 但 C54 中位 NT$42K** — 你預算偏低於這 cluster, 可能要拉到 NT$40K 或往 C50 / C53 看;② **作業量** — 雙語園為了證明 ROI 通常 homework_load 6+,比你期望的 3 高一倍,孩子放學後可能還要 30-45 min 寫作業。

⚠️ **不要只看 4 家就決定**。雙語園「樣品教室」跟「實際運作」可能差很多, 建議每家**未約預約 surprise visit** 看真實情況, 並跟現有家長私下聊。記住:孩子個性 (內向 / 外向 / 敏感) 跟園所文化的契合,比品牌名氣重要 10 倍。
