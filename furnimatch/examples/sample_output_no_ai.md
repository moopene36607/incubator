# furnimatch — 陳新婚 (新北中和 25 坪租屋) 二手家具個人化推薦

**Marketplace**: 30 listings × 60 buyers favorite history
**Similarity 矩陣**: 390 pairs (89.7% dense)
**Average user 收藏**: 7.03 件

## 🎯 買家 profile

**已收藏 (3 件)**:
- 💛 日系木質 沙發 (#01) (日系木質, NT$5,148)
- 💛 日系木質 衣櫥 (#03) (日系木質, NT$4,858)
- 💛 北歐簡約 沙發 (#06) (北歐簡約, NT$2,369)

**Hard filters**:
- 預算上限: NT$10,000
- 地區: 台北, 新北
- 類別: 不限
- 偏好風格 (soft hint): 日系木質, 北歐簡約

## 🛋️ Top 8 推薦 listings

| # | 商品 | 風格 | 價格 | 地區 | 狀態 | CF score | 因為你愛 |
|---|---|---|---|---|---|---|---|
| 1 | 日系木質 餐桌 (#02) | 日系木質 | NT$9,524 | 新北 | GOOD | **1.197** | 日系木質 衣櫥 (#03), 日系木質 沙發 (#01) |
| 2 | 日系木質 茶几 (#05) | 日系木質 | NT$4,570 | 新北 | GOOD | **1.195** | 日系木質 衣櫥 (#03), 日系木質 沙發 (#01) |
| 3 | 北歐簡約 茶几 (#10) | 北歐簡約 | NT$6,594 | 新北 | GOOD | **0.944** | 北歐簡約 沙發 (#06), 日系木質 衣櫥 (#03) |
| 4 | 中式古典 沙發 (#16) | 中式古典 | NT$7,800 | 台北 | GOOD | **0.692** | 日系木質 沙發 (#01), 日系木質 衣櫥 (#03) |
| 5 | 韓系少女 餐桌 (#22) | 韓系少女 | NT$7,107 | 新北 | GOOD | **0.536** | 日系木質 沙發 (#01), 日系木質 衣櫥 (#03) |
| 6 | 中式古典 衣櫥 (#18) | 中式古典 | NT$9,128 | 台北 | FAIR | **0.458** | 北歐簡約 沙發 (#06), 日系木質 沙發 (#01) |
| 7 | 工業風 沙發 (#11) | 工業風 | NT$4,849 | 台北 | FAIR | **0.399** | 日系木質 衣櫥 (#03), 日系木質 沙發 (#01) |
| 8 | 韓系少女 茶几 (#25) | 韓系少女 | NT$9,005 | 台北 | GOOD | **0.374** | 日系木質 衣櫥 (#03), 日系木質 沙發 (#01) |

## 📊 推薦邏輯透明化 (純函式 cosine similarity)

### #1 日系木質 餐桌 (#02) (CF score 1.197)

**為什麼推薦這件**: 因為你已 favorite 的下列物件,其他買家也常 favorite 這件 →
  - 「日系木質 衣櫥 (#03)」co-favorite 相似度 0.471
  - 「日系木質 沙發 (#01)」co-favorite 相似度 0.462
  - 「北歐簡約 沙發 (#06)」co-favorite 相似度 0.215

### #2 日系木質 茶几 (#05) (CF score 1.195)

**為什麼推薦這件**: 因為你已 favorite 的下列物件,其他買家也常 favorite 這件 →
  - 「日系木質 衣櫥 (#03)」co-favorite 相似度 0.537
  - 「日系木質 沙發 (#01)」co-favorite 相似度 0.526
  - 「北歐簡約 沙發 (#06)」co-favorite 相似度 0.082

### #3 北歐簡約 茶几 (#10) (CF score 0.944)

**為什麼推薦這件**: 因為你已 favorite 的下列物件,其他買家也常 favorite 這件 →
  - 「北歐簡約 沙發 (#06)」co-favorite 相似度 0.690
  - 「日系木質 衣櫥 (#03)」co-favorite 相似度 0.130
  - 「日系木質 沙發 (#01)」co-favorite 相似度 0.074

## 統計

Top 5 最熱門 listings (整個 marketplace):

- IKEA實用 餐桌 (#27): 18 人收藏
- 日系木質 衣櫥 (#03): 17 人收藏
- 韓系少女 茶几 (#25): 17 人收藏
- 中式古典 沙發 (#16): 17 人收藏
- 工業風 茶几 (#15): 17 人收藏

## ⚠️ CF 模型假設與限制

- **Cold start**: 新買家 < 3 個 seed favorites,CF score 不穩定;Pro 版加 content-based fallback (style 強制 + 圖片相似度)
- **Popularity bias**: 熱門 listings 容易被推到所有買家面前,小眾 listings 看不見;Pro 版加 inverse-popularity weighting
- **無語意理解**: CF 不知道「沙發跟茶几是搭配」,只看 user co-favorite 模式;與 content-based hybrid 較好
- **二手家具特性**: 一件物品一個 owner,賣掉就消失,跟 Netflix/Amazon 不一樣;需要 churn-aware re-ranking
- **小樣本**: < 50 users CF 不穩定;Pro 版要求 ≥ 200 active users

---
*furnimatch = Sarwar et al. 2001 Item-Item CF × 台灣二手家具 niche = 從 30 件 listings 給買家 top 8 個人化推薦 + 透明 why-recommended。*
