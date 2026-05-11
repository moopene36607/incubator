# furnimatch — 台灣二手家具 Item-Item Collaborative Filtering 媒合

**「我新婚 / 新租屋 / 開新辦公室,FB「二手家具買賣」滑了 200 個 listings 不知道該收哪幾件」** 用 Item-Item Collaborative Filtering (Sarwar et al. 2001) 從買家**已收藏 3-5 件** + budget / location 硬條件 → 5 秒給 Top 8 個人化推薦 + 透明的「為什麼推薦」+ AI 採買順序建議。

## 痛點

台灣二手家具買賣生態:
- **FB「二手家具買賣 / 大樓裝潢出清」社群**: 30-50 萬人
- **蝦皮二手家具**: 月新 listings ~30,000
- **露天拍賣 / 591 二手家具**: ~10,000 active listings
- **預估年買賣交易**: ~100 萬筆

**買家痛點** (PTT home-rent / Dcard 租屋 / FB 媽寶與新婚社群):
- 新婚 / 新租屋 / SOHO 一次要買 5-10 件家具,**滑 listing 滑到眼花**
- 「我這個風格 + 預算」沒個人化 filter
- 找到一件喜歡的 → 同風格其他 listings 哪些值得看?
- 物流 / 自取距離複雜,跨縣市運費吃光便宜

**估計 TAM 買家**:
- 每年新婚 ~14 萬對
- 每年新租屋族 ~30 萬戶
- 每年 SOHO 新辦公室 ~10 萬間
- 共 **50 萬+ 潛在 buyers** 集中採購家具

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(furnimatch 補的) |
|---|---|---|
| 蝦皮 / 露天 / Yahoo 拍賣 | listing + 關鍵字搜尋 | 不做 CF 個人化推薦, 同風格其他 listings 推不出來 |
| 591 二手家具 | listing + 地區篩選 | 同上,只有靜態 filter |
| FB「二手家具買賣」 | 社群 listing | 無演算法 + 滑到無止盡 |
| IKEA / 宜家家居 | 新品配套建議 | 只賣新品,不認識二手 marketplace |
| 居家設計師 NT$5-30K | 風格 + 採購清單 | 太貴, 個人租屋族 access 不到 |
| ChatGPT 直接問 | 一次性建議 | 沒看 listing 資料 + 沒持續 state |

**Gap 結構性**: Item-Item CF (Sarwar et al. 2001) 學術界成熟 24+ 年,Amazon / Netflix 主用,**沒人做成台灣二手家具市場 SaaS**。Google「二手家具 collaborative filtering」零中文 SaaS 結果。

## 架構 — Item-Item Collaborative Filtering (37th 條 AI pattern)

```
User favorites history (60 users × 30 items)
                │
                ▼
┌──────────────────────────────────────────┐
│ 1. Build item-user index                  │
│    For each item i, set U_i of users who  │
│    favorited it                           │
└──────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│ 2. Item-item cosine similarity            │
│    sim(i, j) = |U_i ∩ U_j| /              │
│                sqrt(|U_i| × |U_j|)        │
└──────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│ 3. For new user with seed favorites F:    │
│    For each candidate k not in F:         │
│      score(k) = Σ_{i in F} sim(i, k)      │
│    Apply hard filters (budget/location)   │
└──────────────────────────────────────────┘
                │
                ▼
            Top-N + 透明 contributing favorites
            + cold-start fallback by style
```

**100% 純函式 stdlib** (math + dataclass + collections):
- `cosine_similarity_binary`: |A ∩ B| / sqrt(|A| × |B|)
- `jaccard_similarity`: |A ∩ B| / |A ∪ B| (alternative)
- `build_item_user_index`: item → set of users
- `compute_item_similarities`: sparse item-item sim dict
- `recommend_for_profile`: Σ-sim scoring + hard filters + soft style bonus
- `style_based_fallback`: cold-start when seed too few
- `item_popularity`: 全 marketplace 熱門 items
- `coverage_stats`: sparsity diagnostics

**LLM 只負責**: 寫 200-280 字「採買順序 + 風格 family 解釋 + 二手家具風險」
**LLM 絕不負責**: 計算 cosine sim / score / contributing favorites (數字 100% 來自 CF)

## 使用示例

```bash
# 純函式模式 (無 API key)
python furnimatch.py --marketplace samples/marketplace.json --profile samples/buyer.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python furnimatch.py

# 切換相似度 metric
python furnimatch.py --metric jaccard
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陳新婚 新北中和 25 坪租屋, 預算 NT$10K, 已收藏 2 日系木質 + 1 北歐簡約 沙發):

| # | 商品 | 風格 | 價格 | CF score |
|---|---|---|---|---|
| 1 | 日系木質 餐桌 #02 | 日系木質 | NT$9,524 | **1.197** |
| 2 | 日系木質 茶几 #05 | 日系木質 | NT$4,570 | **1.195** |
| 3 | 北歐簡約 茶几 #10 | 北歐簡約 | NT$6,594 | **0.944** |
| 4 | 中式古典 沙發 #16 | 中式古典 | NT$7,800 | 0.692 |

→ **Top-3 全在買家偏好 family (日系木質 + 北歐簡約)**,符合直覺;#4 中式古典 是 CF 從 user co-favorite 學到的弱 crossover signal (some 日系 buyer 也愛樸實風)。

## 目標市場

- **TAM**:
  - 每年新婚 14 萬對 + 新租屋 30 萬戶 + SOHO 10 萬間 = **50 萬+ 集中採購 buyers**
  - 加上汰換 / 喬遷 / 升級族群每年 ~30 萬,**80 萬潛在用戶**
- **WTP 錨點**:
  - 一次成交家具總價 NT$3-30K,推薦多 1-2 件 = 賣家平台抽 5-10% commission 自然收
  - 居家設計師 NT$5-30K vs 工具一次 NT$199 = 25-150x 便宜

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 query/月 + Top 5 推薦 | 試用 |
| **Solo** | NT$99/月 (或一次性 NT$299/家具搜尋週期) | 無限 query + Top 20 + 風格分析 | 個人買家 |
| **Pro** | NT$299/月 | + LINE 推播新 listings + 多買家共評 (家庭) | 新婚 / 家庭 |
| **Marketplace** | 平台抽佣 5-10% 成交價 | 內建在 FB 社群 / 蝦皮 / 露天的個人化推薦 | 平台 |
| **Designer** | NT$2,999/月 | 室內設計師批量為客戶找 listings + API | 居家設計師 |

## Distribution

- **FB「二手家具買賣 / 大樓裝潢出清」社群** 30-50 萬人 → SEO 案例 + bot 在 listing 下回覆推薦
- **PTT home-rent / Dcard 租屋 / 媽寶 / 新婚家庭**
- **YouTube 居家 KOL** (家空間 Honger / 沼澤工作室 / 紳閱家居) 案例合作
- **蝦皮 / 露天 / 591 二手家具** 平台整合 API (B2B2C 內建推薦引擎)
- **室內設計師公會** B2B BD
- **新婚博覽會 / 婚博會** booth (每年 7 月)
- **大學新生開學季** (8-9 月) 校園推廣

## TAM

- 1% × 50 萬 = 5,000 × NT$299 一次性 = **年 NT$150 萬 + Solo 月訂閱**
- Solo 月訂閱 2,000 × NT$99 × 2.5 月 = NT$50 萬/季
- + Pro + Designer + 平台抽佣 → 年 ARR NT$2,000-4,000 萬
- 加滲透 + 橫移日韓港新二手家具 → 翻倍至 NT$5,000-8,000 萬 ARR

## 風險與限制

- **Cold start**: 新買家 < 3 seed favorites,CF score 不穩定;fallback 用 style + hard filter
- **Popularity bias**: 熱門 listings 容易被推到所有買家面前,小眾 listings 看不見;Pro 版加 inverse-popularity 重新加權
- **無語意理解**: CF 不知道「沙發跟茶几是搭配」,只看 user co-favorite 模式;Pro 版加 content-based hybrid (CLIP 圖片相似度)
- **二手家具一物一賣**: 一件物品一個 owner,賣掉就消失,跟 Netflix/Amazon 不一樣;需要 churn-aware re-ranking
- **小樣本**: < 50 active users CF 不穩定;Pro 版要求 ≥ 200 active users
- **二手家具品質風險**: 推薦只能推 listing,實際品質要 buyer 自己試坐 / 議價

---
*furnimatch = Sarwar et al. 2001 Item-Item Collaborative Filtering × 台灣二手家具 niche = 從 200 條 FB listings 給買家個人化 Top-N + 為什麼推薦完全透明。*
