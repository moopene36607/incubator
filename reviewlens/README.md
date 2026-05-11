# reviewlens — 台灣電商賣家商品評論 LDA 主題分析

**「我蝦皮店 4.3 ⭐ 看起來還可以,但差評在抱怨什麼?是物流、品質、客服還是某商品出問題?」** 用 Latent Dirichlet Allocation (Blei et al. 2003) 從幾百條繁中評論抽出 5-10 個 latent topics,結合每商品的主題集中度 + 評分,賣家**20 秒看出 5 個商品各自哪邊出問題**。Collapsed Gibbs sampling 學術成熟 20+ 年,**台灣電商賣家市場零中文 SaaS**。

## 痛點

台灣電商生態:
- **蝦皮**: 活躍賣家 ~200,000, 中型 (月 200-2000 訂單) ~30,000
- **露天 / Yahoo / momo 賣家**: 中文電商 ~50,000 加總
- **個人經營占多數**: 沒有 BI tool / 客戶研究團隊

**每月看評論的焦慮**:
- 「整體 4.3⭐ 看起來還可以但生意明顯下滑,差評到底在抱怨什麼?」
- 「200 條評論一條一條看太累,看到一半就麻木了」
- 「明明 5 個商品為什麼有的退貨多有的少,是商品問題還是物流問題?」
- 「ChatGPT 一次貼 50 條會 hallucinate 主題,不可信」

實際情境驗證 (FB「蝦皮賣家交流」社群 5-10 萬人 / PTT e-shopping / Dcard 賣家版):
- 「200 條評論看到眼花是不是有 AI 可以分析」每週重複問
- 「我藍牙耳機評分一直拉不起來,看不出來是哪個 batch 出問題」

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(reviewlens 補的) |
|---|---|---|
| 蝦皮 / 露天 Seller Center | 給星等 + 個別評論 list | 不分主題, 不算 topic 集中度 |
| 海外 Junglescout / Helium 10 | Amazon 賣家用 | 不認識繁中 / 蝦皮文化 / 蝦皮商品結構 |
| 海外 Senuto / ReviewMeta | 評論真偽偵測 | 不做 LDA topic mining |
| Google Sheets + 人工分類 | 自己手動標 | 200 條/月 × 5 分 = 17 小時 admin time |
| ChatGPT 直接貼 | 一次性回答 | 主題會 hallucinate, 沒持續分析多商品, 不重現 |
| BI tools (Tableau / Power BI) | 數據視覺化 | 不做 NLP topic modeling |

**Gap 結構性**: LDA (Blei et al. 2003) + Collapsed Gibbs Sampling (Griffiths & Steyvers 2004) 學術成熟 20+ 年,**沒人做成台灣電商賣家可用 SaaS**。Google「蝦皮 LDA 主題分析」零中文 SaaS 結果。

## 架構 — Latent Dirichlet Allocation / Collapsed Gibbs Sampling (34th 條 AI pattern)

```
Reviews (50-500 條繁中文字)
         │
         ▼
┌──────────────────────────────────────┐
│ 1. Char-bigram tokenize               │
│    (不用 jieba, 純 stdlib)            │
│    + 中文 stopwords 過濾               │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ 2. Build vocabulary (min_df ≥ 2)      │
│    docs → integer ID lists            │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ 3. Init: random z_{d,i} ∈ {0..K-1}   │
│    n_dk, n_kw, n_k counts             │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ 4. Collapsed Gibbs sweep × N iter:    │
│    For each word w_i in each doc d:  │
│      remove z_i from counts          │
│      sample z_i ∝ (n_dk+α)·(n_kw+β)  │
│                  / (n_k + Vβ)        │
│      add z_i to counts               │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ 5. φ[k][w] = topic-word distribution  │
│   θ[d][k] = doc-topic distribution    │
│   Top words per topic                 │
│   Topic concentration per product     │
└──────────────────────────────────────┘
         │
         ▼
Each product → dominant complaint topic
LLM 寫具體 actionable suggestion per product
```

**100% 純函式 stdlib** (random + math + dataclass + collections):
- `tokenize_chinese`: char-bigram + stopword filter (不用 jieba)
- `build_vocabulary`: min_df filter rare tokens
- `init_lda`: random topic assignment + counts
- `gibbs_sweep`: full collapsed Gibbs update
- `fit_lda`: full pipeline with N iterations
- `top_words_per_topic`: φ[k] sorted
- `doc_topic_distribution`: θ[d]
- `topic_concentration_per_group`: aggregate θ per product
- `topic_perplexity`: held-out goodness-of-fit

**LLM 只負責**: 寫 250-350 字「每商品診斷 + 跨商品共通問題 + 風險」
**LLM 絕不負責**: 計算 topic-word / doc-topic 機率 / 主導主題 (數字 100% 來自 Gibbs)

## 使用示例

```bash
# 純函式模式 (無 API key)
python reviewlens.py --seller samples/seller.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python reviewlens.py --seller samples/seller.json

# 調整主題數 K
python reviewlens.py --topics 8

# 跑更久 (more iterations = 更穩定 topic)
python reviewlens.py --iterations 1000
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (海鷗精選 蝦皮賣家 5 商品 × 63 條評論, K=5):

| 商品 | 評分 | 主導主題 | Top words |
|---|---|---|---|
| 藍牙耳機 | 3.0⭐ | T0 | 品質 / 藍牙 / 連線 / 用 |
| T-shirt | 2.8⭐ | T1 | 尺寸 / 出貨 / 號 / 錯 |
| 韓國保養品 | 2.9⭐ | T3 | 包裝 / 多 / 照片 / 物流 |
| 保溫瓶 | 2.6⭐ | T2 | 保溫 / 小時 / 音質 |
| 床包 | 2.7⭐ | T1 | 尺寸 / 出貨 / 號 |

→ **共通痛點是物流 + 包裝 + 尺寸標示**,系統性問題優先解決。

## 目標市場

- **TAM**:
  - 蝦皮中型賣家 (月 200-2000 訂單) ~30,000
  - 露天 / Yahoo / momo 中文中型 ~20,000
  - 個人 LINE 群 / FB 社團賣家 ~50,000+
  - 估計 **80,000+ 中文中型電商賣家**
- **WTP 錨點**:
  - 自己手動看 200 條 × 5 分 = 17 小時/月 × NT$300 機會成本 = NT$5,100/月 vs Solo NT$199 = **25x ROI**
  - 一次找對改善方向多賺 NT$3-10K/月

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 50 評論/月 × 5 商品 | 試用 |
| **Solo** | NT$199/月 | 無限評論 + 8 商品 + 中文 stopwords 自訂 | 個人賣家 |
| **Pro** | NT$499/月 | + 多店鋪比較 + rating-weighted topic + LINE 推播 | 中型賣家 |
| **Studio** | NT$1,999/月 | + 跨平台 (蝦皮 + 露天 + Yahoo) 整合 + API | 多平台店家 |
| **Brand** | NT$8,000+/月 | 品牌方 review brand audit + 競品 LDA 對比 | 品牌商 |

## Distribution

- **FB「蝦皮賣家交流」5-10 萬人社群** SEO + 案例分享
- **PTT e-shopping / Dcard 賣家版** 長尾關鍵字
- **YouTube 電商 KOL** (尼克 Nick / 五金行 / 商業思維學院) 案例合作
- **蝦皮大學 / 露天商學院** 課程贊助 + 推薦工具
- **電商代營運公司 / 跨境電商顧問** B2B BD 白標
- **電商展 / 跨境電商論壇** booth (台灣電商博覽會每年 8 月)

## TAM

- 1% × 80,000 中文中型賣家 = 800 × NT$199 = **月 MRR NT$16 萬**
- + Pro 200 × NT$499 = NT$10 萬/月
- + Studio 50 × NT$1,999 = NT$10 萬/月
- + Brand 30 × NT$8,000 = NT$24 萬/月
- 總計 **月 MRR NT$60 萬 / 年 ARR NT$720 萬**
- 加滲透率提升 + 橫移日韓 / 港澳 + 跨境 Amazon 海外賣家 → 翻倍至 **NT$2,000-3,000 萬 ARR**

## 風險與限制

- **K 必須預先指定** — K 太小主題糊在一起,K 太大主題會分裂;Pro 版加 perplexity-based 自動 K 選擇
- **bag-of-words 忽略順序** — 「不慢」「慢不慢」會被當同義,prototype 限制;Pro 版用 word n-gram (1-3 字)
- **char-bigram 精度有限** — 不用 jieba 適合 prototype,但語意精度低;Pro 版接 jieba / CKIP
- **Gibbs sampling 有隨機性** — 同樣 seed → 同樣結果,但不同 seed 可能略不同;Pro 版多次 run + topic alignment
- **小樣本 risk** — < 50 評論時主題會 overfit;Pro 版需要 ≥ 200 評論才推薦使用
- **LDA 不告訴你嚴重程度** — 只告訴你「在抱怨什麼」,評分結合才知道哪個最痛;Pro 版加 rating-weighted topic

---
*reviewlens = Blei et al. 2003 LDA × 台灣電商賣家評論 niche = 從 200 條繁中 review 自動找出 5-10 個痛點主題 + 每商品診斷,而非逐條看到眼花。*
