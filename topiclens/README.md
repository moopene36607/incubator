# topiclens -- 台灣國高中 / 補習班 題庫 Spectral Clustering 找概念群

**「30 人 8 班這次數學考很差, 但到底是哪個概念群崩了?」** 用 Shi-Malik 2000 + Ng-Jordan-Weiss 2002 Spectral Clustering 從學生答題 co-error pattern 找出「題目-題目」社群, 純函式 Jacobi 對稱矩陣 eigendecomposition + k-means → 自動把考卷題目分成 4-5 個概念群 + 每位學生 × 概念群錯誤率交叉表 + 補救教學優先順序, 比 Excel 看「錯題單獨統計」多一個維度。

## 痛點

台灣國高中 / 補習班 教師生態:
- **國高中數學 / 國文 / 英文 老師**: ~12 萬人 (含公立 + 私立)
- **補習班 / 才藝班 老師 / 家教**: ~10 萬人
- **每月測驗**: 1-4 次 (平時考 / 段考 / 模擬考)
- **每次測驗**: 20-50 題 × 30-50 學生
- **痛點密度**: 每位老師每月 1-2 次「補救教學該從哪邊開始」決策

**老師痛點** (PTT C_Education / Dcard 教師版 / FB「補教老闆交流」5-10 萬人社群 / 教師研習工作坊):
- 「30 人 8 班這次考不好, 是哪個概念群崩了?」(每次月考重複)
- 「我看 Excel 統計只能看出『哪題錯多少 %』, **不能看出『哪些題目同一群學生錯』**」
- 「補救教學 4 節課該怎麼分? 全部講一遍效率太低」
- 「家長問『我小孩數學弱在哪』, 我只能說『代數比較弱 (我感覺)』, 沒客觀依據」
- **每月 2-4 小時** 手工分析錯題 + 設計補救教材

**現有資源**:
- 教育部「因材網」/ 學習吧 / 均一平台 / PaGamO 提供題庫 + 練習, **不做題目-題目 spectral clustering**
- 補教王 / 補習達人 / EduBase 是 CRM 不做學科分析
- Excel 統計只能算「題目錯誤率」+「學生錯題數」, **無 cross-relation 矩陣分析**
- 家教 / 補習班顧問 訪談 NT$3-5K/次 + 主觀經驗
- R / Python scikit-learn 學術工具不適合中小學老師

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(topiclens 補的) |
|---|---|---|
| 教育部「因材網」/ 學習吧 / 均一 / PaGamO | 題庫 + 練習 + 統計 | **不做 spectral clustering**, 無「題目-題目共錯」分析 |
| 補教王 / 補習達人 / EduBase CRM | 學生 / 課程管理 | 完全不分析學科內容 |
| Excel 手算錯誤率 | 純題目 / 學生 單變數統計 | 沒 cross-relation 矩陣 + spectral 角度 |
| 家教 / 補習顧問 訪談 NT$3-5K/次 | 主觀經驗 | 落差大, 沒客觀依據 |
| ChatGPT 一次問 | 一次性建議 | 不能跑 spectral clustering, 沒持續資料 |
| R / Python scikit-learn | 學術強大 | 中小學老師學不會, 太重 |
| **examready r40** (本 incubator) | 升學考前 MDP 排程 | 完全不同問題: 排程 vs 概念分析 |
| **cramlead r56** | 補習班招生 lead 預測 | 完全不同問題: 招生 vs 教學 |
| **stylescan r23** | 作文 AI 代筆偵測 | 完全不同問題: 作弊 vs 學科分析 |

**Gap 結構性**: Spectral Clustering (Shi-Malik 2000 + Ng-Jordan-Weiss 2002) 學術成熟 25+ 年, **沒人做成台灣繁中國高中 / 補習班教師可用 SaaS**。Google「題目 spectral clustering 中文」零本土 SaaS。**跟 examready r40 / cramlead r56 / stylescan r23 / monthrep r10 / teachsay r31 教育 vertical 互補但完全不同問題** — 排程 / 招生 / 作弊 / 月報 / 親師溝通 全都不做概念群分析。

## 架構 -- Spectral Clustering with Jacobi Eigendecomposition (53rd 條 AI pattern)

```
30+ 學生 × 20+ 題 答題 0/1 矩陣
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 1. 建構 co-error affinity matrix W:           │
│    S_i = {students wrong on question i}      │
│    W[i][j] = Jaccard(S_i, S_j)               │
│            = |S_i ∩ S_j| / |S_i ∪ S_j|       │
│    對角 = 0 (graph 慣例)                       │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 2. Normalised affinity:                       │
│    D = diag(row sums of W)                    │
│    L_aff = D^{-1/2} W D^{-1/2}                │
│    (the normalised graph affinity matrix)     │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 3. Jacobi rotation eigendecomposition:        │
│    For symmetric matrix L_aff, repeatedly:    │
│      find largest off-diagonal element        │
│      compute rotation angle θ                 │
│      apply Givens rotation R^T L R           │
│    Until off-diagonal < tol                   │
│    Returns: eigenvalues + eigenvectors        │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 4. Ng-Jordan-Weiss embedding:                 │
│    Take TOP-k eigenvectors (largest λ)        │
│    Stack into n × k embedding matrix Y        │
│    Row-normalise rows to unit length          │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 5. k-means on row-embedded points:           │
│    kmeans++ init + 5 random restarts          │
│    Lloyd iterations until convergence         │
│    Returns: cluster label per question        │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Diagnostics:                                  │
│   • Eigenvalue spectrum (eigengap heuristic) │
│   • Silhouette score (cluster cleanliness)    │
│   • Topic tag frequency per cluster           │
│   • Per-student × per-cluster error rate      │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + random + statistics + dataclasses + collections):
- `jaccard_similarity / build_coerror_affinity`: 共錯 Jaccard graph
- `jacobi_eigendecomp`: Givens rotation 對稱矩陣 eigendecomp, sweep until convergence
- `normalised_laplacian / spectral_cluster`: NJW pipeline
- `kmeans`: Lloyd + kmeans++ + multi-restart 純函式
- `silhouette_score`: cluster 乾淨度
- `cluster_centroid_topics`: 用每群最常見 tag 給概念群命名建議

**LLM 只負責**: 寫 280-340 字「給導師 / 學科老師 / 家長 的補救教學行動 + 真不會 vs 粗心訊號 + 風險」
**LLM 絕不負責**: 計算 clustering / eigenvalues / silhouette / cluster membership (數字 100% 來自 spectral 純函式)

### 為什麼 Spectral Clustering 適合這個 use case (vs HAC r52 / DBSCAN r52 / EM r34)

- **Spectral**: 用 graph Laplacian 的 spectral 結構 (NJW 2002), 對「非凸 cluster shape」最 robust, 並且 silhouette 通常 > 0.9 表示分群乾淨
- **HAC r52 kindergrid**: ward linkage 樹狀分群, 適合層級結構 (人物 / 機構 / 教室類), 不適合用 co-error graph
- **DBSCAN r52**: 適合 noise + 密度差異大的 case, 不適合題目-題目稠密 graph
- **EM Gaussian Mixture r34 daypart**: 假設高斯分布, 適合連續特徵 (時間 × 金額), 不適合 graph affinity

Spectral 獨特優勢:
1. **Graph-native**: 從題目共錯 Jaccard 直接 graph spectral 分析, 不假設特徵歐式距離
2. **可解釋**: Eigenvectors 對應 graph 的「partition 方向」, 物理直覺清楚
3. **小樣本即可**: 30 學生 × 20 題就能跑出 silhouette 0.97 乾淨分群

## 使用示例

```bash
# 純函式模式 (無 API key)
python3 topiclens.py --data samples/exam_responses.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 topiclens.py --data samples/exam_responses.json

# 改 cluster 數量
python3 topiclens.py -k 5
```

預期輸出 (詳見 `examples/sample_output.md`):

明心國中 8 班 30 人 × 20 題期末考 (k=4):

| 概念群 | 題數 | 主要 tag | 平均錯誤率 |
|---|---|---|---|
| ⭐ **Cluster 0** | 5 | **代數** | **21.3%** |
| Cluster 1 | 5 | 幾何 | 18.7% |
| Cluster 2 | 5 | 機率 | 16.0% |
| Cluster 3 | 5 | 數列 | 13.3% |

→ **輪廓係數 0.977** (perfect cluster separation). 模型自動識別 4 個概念群完美對齊出題人原始 tag (代數 / 幾何 / 機率 / 數列), **沒用到任何標籤** (純函式僅基於共錯 pattern)。

→ 補救教學優先順序: 代數 (S09-S15 共 7 人弱) > 幾何 (S16-S21 共 6 人) > 機率 (S22-S26 共 5 人) > 數列 (S27-S30 共 4 人)

## 目標市場

- **TAM**:
  - 國高中老師: 12 萬人 (公立 + 私立)
  - 補習班 / 才藝班 / 家教: 10 萬人
  - 教育部 / 各縣市教育局 (B2G 公益)
  - 教育出版社 / 試題庫廠商 (康軒 / 翰林 / 南一 / 龍騰) B2B
- **WTP 錨點**:
  - 老師月省 2-4 hr × NT$500/hr = NT$1-2K/月 vs Solo NT$199/月 = **5-10x ROI**
  - 補習班月省 NT$5-10K (顧問 + 教材設計) vs Pro NT$1,499 = **3-7x ROI**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 次測驗 / 月 | 個別老師試用 |
| **Solo** | NT$199/月 | 無限測驗 + 學生個人化追蹤 + LINE 推播 | 個別老師 / 家教 |
| **Pro** | NT$1,499/月 | 多班 + 多老師 + 學期累積 + 跨班 benchmark | 補習班 / 才藝班 |
| **School** | NT$4,999/月 | 整校 + 跨年級 + Google Classroom / 因材網 integration | 學校 |
| **District** | NT$15,000+/月 | 縣市教育局 + 跨校 anonymized 比較 + 政策制定 | 教育局 |
| **Publisher** | NT$30,000+/月 | 出版社 / 試題庫 商 整合 + API + 題目品質分析 | 康軒 / 翰林 / 南一 |

## Distribution

- **PTT C_Education / Dcard 教師版 / FB「補教老闆交流」** 5-10 萬人社群 案例分享
- **教師研習工作坊** (各縣市教育局每年 3-4 次)
- **補習班分校 BD** (跟補教王 / 補習達人互補, 不衝突)
- **YouTube 教學 KOL** (葉丙成 / 王政忠 / 葉子老師)
- **教育部 / 各縣市教育局 partner** (公益版 + PR + 配合 108 課綱 / 12 年國教 評量素養)
- **教育出版社 partner** (康軒 / 翰林 / 南一 / 龍騰) -- 出版題庫附 spectral analysis
- **PaGamO / 均一 / 因材網 / 學習吧** integration partner
- **學測 / 會考 / 統測 倒數節點 (8-9 月開學 / 12-1 月模擬考)** Google Ads

## TAM

- 0.5% × 22 萬老師 = 1,100 × Solo NT$199 = 月 NT$22 萬
- + Pro 300 × NT$1,499 = NT$45 萬/月 (補習班連鎖)
- + School 100 × NT$4,999 = NT$50 萬/月
- + District 20 × NT$15K = NT$30 萬/月
- + Publisher 5 × NT$30K = NT$15 萬/月
- 總計 **月 MRR NT$162 萬 / 年 ARR NT$1,940 萬**
- 加滲透 + 橫移港新馬 / 日韓 中文教育 + 各縣市教育局 → **NT$5,000 萬-1 億 ARR**

## 風險與限制

- **30 學生 prototype 太小** -- real launch 需 ≥ 100 學生 + 多次測驗才能穩定; 鼓勵學校 contribute data 換取免費 School 月
- **共錯 ≠ 同概念**: 兩題都錯可能因「概念不熟」也可能「粗心 / 時間不夠 / 看錯題目」; Pro 版加 IRT (Item Response Theory) latent estimation 區分 ability vs guessing
- **Jaccard 對小樣本敏感**: 全班只 30 學生時 Jaccard 估計變異大; Pro 版加 Bayesian smoothing 或改用 cosine similarity
- **k 需先指定**: 自動選 k 用 eigengap heuristic, prototype 預設 k=4; Pro 版加 eigengap + silhouette 自動掃 k
- **不含題目難度**: 太簡單 / 太困難題目錯誤率近 0% / 100%, Jaccard 失效; Pro 版加 IRT 難度過濾
- **不取代教師判斷**: cluster 是統計分群, 真實「概念」歸屬還需出題老師 / 學科主任人工 review
- **概念群名稱靠 LLM 解釋**: 純函式只給統計群集, 「這 cluster 是什麼概念」LLM 寫但**仍需老師覆核**
- **不能 label 學生**: 切勿告訴學生「你是代數弱組」, 應強調這是「目前 weak point, 兩週可以追回來」的可變 state
- **隱私敏感**: 學生答題資料涉個資 + 教育記錄, 雲端版需匿名化 + 學校 / 家長同意 + 教育資料保護法合規

---
*topiclens = Shi-Malik 2000 / Ng-Jordan-Weiss 2002 Spectral Clustering × Jacobi eigendecomp × 台灣國高中 / 補習班題庫 niche = "30 學生 × 20 題 co-error Jaccard graph → 4 個概念群 + silhouette 0.97" 純函式可重現, 補老師 / 補習班 / 家長「補救教學優先順序」這個過去靠 Excel 看不出的洞察。*
