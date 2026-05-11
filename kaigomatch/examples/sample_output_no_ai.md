# kaigomatch -- あおぞら訪問介護事業所 (板橋区, 訪問介護) schedule matching

**Staff (ヘルパー / 介護職員)**: 10 名
**利用者**: 15 名
**過去 assignment edges**: 47 件
**Random walks**: 15 per node × length 10 = 375 walks
**Co-occurrence window**: 5
**Walk diversity**: 0.66 (1.0 = no revisits)
**PPMI coverage**: 25 / 25 nodes (100%), 250 非零 PPMI pairs

## 🎯 マッチング対象: C03 (利用者)

_鈴木和夫 78 歳 男 / 認知症 中度 / 週 3 回 / 板橋区_

## 🔮 Top 5 ヘルパー 候補 (cosine on PPMI + direct PPMI 結合)

| 順位 | ID | Cosine 類似度 | Direct PPMI | 結合スコア | 詳細 |
|---|---|---|---|---|---|
| 1 | **S01** | 0.743 | 1.08 | **0.763** | 田中花子 7 年 / 認知症対応 OK / 女性 / 朝-夕勤務 / 板橋区 |
| 2 | **S02** | 0.639 | 1.09 | **0.702** | 佐藤太郎 6 年 / 認知症対応 OK / 男性 / 朝-夕勤務 / 板橋区 |
| 3 | **S05** | 0.586 | 1.01 | **0.658** | 高橋真理 8 年 / 認知症対応 OK / 女性 / 朝-夕 / 豊島区 |
| 4 | **S03** | 0.256 | 0.00 | **0.154** | 山田美咲 5 年 / 認知症対応 OK / 女性 / 全日 / 練馬区 |
| 5 | **S04** | 0.091 | 0.00 | **0.055** | 鈴木健一 6 年 / 重度介護 OK / 男性 / 全日 / 練馬区 |

### 💡 Top 推薦解讀

- **S01** 與 C03 **直接** 過去有 assignment 紀錄 (PPMI = 1.08), 表示既有合作經驗 → 安心 routing

## 🔬 Graph embedding 直覺

DeepWalk 風格 random walks 在 staff-client 二分圖上跑, 透過 PPMI 加權後:
- **Cosine 類似度** = 兩個節點在 graph 上「鄰居模式」相似度 (鄰居模式相似 → 適合接同一群人)
- **Direct PPMI** = 兩個節點是否在 walks 中常常共同出現 (高 = 直接共現經驗強)
- **結合スコア** = 0.6 × cosine + 0.4 × tanh(PPMI)

## ⚠️ Graph Embedding / Link Prediction 模型假設與限制

- **過去配對偏差**: 模型只從歷史 assignment 學, 若過去 staff A 從未被指派 client X, 兩者可能 PPMI=0 但其實非常適合 (cold-start). Pro 版加 staff/client metadata side-information
- **Random walk 隨機性**: walk seed 改變排序略有差異; prototype 用固定 seed 確保可重現
- **Bipartite 限制**: 無法捕捉「ヘルパー之間 / 利用者之間」直接連結 (e.g. 同班朋友的偏好), Pro 版加 tripartite (staff / client / shift)
- **權重對 walks 的影響**: edge weight (visit 次數) 高時 walk 更常停留, low-frequency staff 易被埋沒. Pro 版加 importance sampling
- **PPMI 對 sparse 敏感**: 樣本不大 (< 100 edges) 時 PPMI 估計變異大;真實 launch 需 ≥ 500-1000 條 history
- **不取代人工確認**: graph 推薦是 starting point, 排班 manager 仍需 review 安全 / 排班 conflict / 個性
- **隱私敏感**: 利用者 + ヘルパー 個資 + 健康狀態 涉介護保険法 / 個人情報保護法, 雲端版需匿名化 + 加密 + 介護事業所同意

---
*kaigomatch = DeepWalk-style random walks + PPMI + cosine link prediction × 日本介護事業所 staff-利用者 matching niche = 從過去 assignment 歷史學 graph embedding, 排班 manager 月省 40-60 小時手動排班 + 提高 staff-client 適配度 → 利用者滿意度 + ヘルパー留任率雙升。*
