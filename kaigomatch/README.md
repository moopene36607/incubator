# kaigomatch -- 日本訪問介護事業所 staff-利用者 schedule matching with graph embedding

**「S01 田中さん来週インフルで休む, 鈴木さんに代理派遣する場合誰がベスト?」** 用 DeepWalk-style random walks + PPMI 加權 + cosine 在 staff-利用者 二分圖上學嵌入, 純函式 graph embedding + link prediction 從過去 assignment 履歷推薦最適配の代理 staff, 排班 manager 月省 40-60 小時手動排班 + 提高 staff-利用者 適配度 → 利用者滿意度 + ヘルパー留任率雙升。

## 痛點

日本訪問介護 (在宅介護サービス) 市場:
- **65 歲以上人口**: 3,640 萬人 (人口 36%, 超高齢社会)
- **介護保険給付**: 11 兆円 / 年
- **介護事業所**: ~5 萬家 (訪問介護 + 訪問看護 + デイサービス)
- **每事業所**: 10-30 ヘルパー × 30-100 利用者 = 300-3,000 月間訪問
- **サービス提供責任者**: 月 40-60 小時手動排班

**排班痛點** (介護経営者 ブログ / 介護労働安定センター 調査):
- 「ヘルパー希望 (時段 / 通勤距離 / 苦手な利用者) vs 利用者要望 (女性 / 経験 / 個性) 排班 conflict 多」
- 「ベテラン 1 名休 → サブ誰? 経験で適当に派 → クレーム」
- 「新 ヘルパー 適性 不明, 試行錯誤 3-6 個月才知道適合誰」
- **「ヘルパー離職率 16-20%」** (全産業平均 14%), 排班不合 = 早期離職主因
- 既有ツール (ジョブカン介護 / カイポケ / e-care) **沒做 graph-based matching**, 都是 record-keeping + 簡單排班 UI

**現有資源**:
- ジョブカン介護 / カイポケ / e-care / 介舟ファミリー: 介護記録 + 請求書 + 簡單排班, **沒 ML matching**
- 介護コンサル: 月 5-30 万円, 排班 advice + 経営支援, 中小事業所負担難
- ベテラン サ責 個人経驗: 主觀 + 人事更替時 know-how 流失
- ChatGPT 一次問: 不知道事業所 history + 沒持續學習

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(kaigomatch 補的) |
|---|---|---|
| ジョブカン介護 / カイポケ / e-care | 介護記録 + 請求 + 簡單排班 UI | **沒 ML matching**, 排班全靠人工 |
| 介護コンサル (月 5-30 万) | 排班 advice + 経営支援 | 太貴 + 主觀, 中小事業所負担難 |
| ベテラン サ責 | 經驗排班 | 個人 know-how + 人事更替時流失 |
| ChatGPT 一次問 | 一次性建議 | 不能持續學歷史 assignment |
| Excel 手動 | 純人工 | 沒 graph matching, 20 ヘルパー × 50 利用者 = 1,000 配對人工搞不定 |
| **carepen r7** (本 incubator) | Taiwan 居服員 SOAP records | 完全不同問題: 文書 vs 排班 |
| **shiftsync r15** | Taiwan 餐廳排班 LINE bot | 餐飲不同行業 |
| **weddingmatch r16** | 婚攝 12-dim feature cosine | 不同: feature similarity vs graph history |

**Gap 結構性**: DeepWalk / node2vec (Perozzi 2014 / Grover-Leskovec 2016) 學術成熟 10+ 年, PPMI factorisation (Levy & Goldberg 2014) 也已 11 年, **沒人做成日本介護事業所可用 SaaS**。Google「介護 graph embedding」零本土 SaaS。**跟 weddingmatch r16 互補但不同** — r16 用預定義 12-dim style 向量 cosine, r67 從 graph **歷史 assignment** 學 latent embeddings (不需 hand-crafted features)。

## 架構 -- Graph Embedding via DeepWalk-style Random Walks + PPMI + Cosine Link Prediction (57th 條 AI pattern)

```
過去 assignment edges (staff_id, client_id, weight)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Bipartite weighted graph G = (V, E):          │
│   V = staff ∪ client nodes                    │
│   E = past assignments with weight (visits)   │
│   無向 (undirected)                            │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Random walks (DeepWalk-style):                │
│   For each node v ∈ V:                        │
│     For walk_i in 1..K:                       │
│       Walk length L, weighted-neighbour       │
│       sampling at each step                   │
│   Total walks = K × |V|                       │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Co-occurrence (sliding window W):             │
│   For each walk, for each position i:         │
│     For j in [i-W, i+W], j ≠ i:               │
│       pair_count[(w[i], w[j])] += 1           │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ PPMI (Levy & Goldberg 2014):                  │
│   PMI(i, j)  = log(n_ij × N / (n_i × n_j))    │
│   PPMI(i, j) = max(0, PMI(i, j))              │
│                                                │
│ Each node's PPMI row = sparse embedding       │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Link prediction:                              │
│   cosine_score   = cos(emb_u, emb_v)          │
│   direct_ppmi    = PPMI(u, v)                 │
│   combined_score = 0.6·cosine + 0.4·tanh(PPMI)│
│   Rank candidates by combined_score           │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + random + statistics + dataclasses + collections):
- `WeightedGraph` + `build_bipartite_graph`: 鄰接表 + 邊權重
- `random_walk + generate_walks`: 加權鄰居 sampling (cumulative weight binary-search)
- `cooccurrence_counts`: sliding window count
- `compute_ppmi`: PMI shift-adjusted positive part (Levy-Goldberg)
- `cosine_dict`: dictionary-based 稀疏 cosine (省記憶體)
- `top_k_neighbours`: cosine + tanh(PPMI) 結合 ranking
- `coverage / avg_walk_diversity`: 診斷

**LLM 只負責**: 寫 250-330 字「給サ責的代理派遣建議 + 安排前確認步驟 + 何時違反 graph 推薦 + 経営層洞察」
**LLM 絕不負責**: 計算 cosine / PPMI / link prediction (數字 100% 來自 graph embedding)

### 為什麼 DeepWalk + PPMI 適合這個 use case (vs cosine on features r16 / SOM r64 / CF r47)

- **DeepWalk + PPMI**: 從**歷史互動 graph 結構**學 latent embeddings, 不需事前定義 feature dimensions
- **weddingmatch r16**: 用 hand-crafted 12-dim feature vector cosine, 需要事先定義所有重要維度 (新加 ヘルパー 需要重新校正 features)
- **careermap r64 SOM**: 用個性 features → 2D 拓樸 map, 適合「視覺化分群」但不直接給 link prediction
- **furnimatch r47 CF**: item-item collaborative filtering, 適合「買 X 也買 Y」, 但 staff-client 不是 item 共購是 service 配對

DeepWalk 獨特優勢:
1. **不需 hand-crafted features**: 介護事業所 staff / client 千百種屬性, graph 自動學重要的
2. **Cold-start partial coverage**: 新 staff 只要 1-2 個歷史 edge 就能納入 walk 學 embedding
3. **Multi-hop similarity**: 2 staff 從未配同 client 但都配相似的 client → graph 仍能捕捉 indirect similarity

## 使用示例

```bash
# 純函式模式 (無 API key)
python3 kaigomatch.py --data samples/jigyousho.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 kaigomatch.py --data samples/jigyousho.json

# 調整 random walks / window
python3 kaigomatch.py --n-walks 30 --walk-length 15 --window 8
```

預期輸出 (詳見 `examples/sample_output.md`):

あおぞら訪問介護事業所 (10 ヘルパー × 15 利用者 × 47 assignment edges) で
鈴木さん (C03, 認知症中度) の代理派遣 query:

| Rank | Staff ID | Cosine | Direct PPMI | 結合 |
|---|---|---|---|---|
| 1 | **S01 田中花子** (現役) | 0.743 | 1.08 | 0.763 |
| 2 | **S02 佐藤太郎** (代理候補) | 0.639 | 1.09 | 0.702 |
| 3 | **S05 高橋真理** (バックアップ) | 0.586 | 1.01 | 0.658 |
| 4 | S03 山田美咲 | 0.256 | 0.00 | 0.154 |
| 5 | S04 鈴木健一 | 0.091 | 0.00 | 0.055 |

→ 系統正確識別 S02 是 S01 休假時の最佳代理 (cosine 0.64 + direct PPMI 1.09 = 過去合作經驗強)

訓練診斷: 25 nodes 全部有 PPMI rows (100% coverage), 250 非零 PPMI pairs, walk diversity 0.66 (合理層級).

## 目標市場

- **TAM**:
  - 日本訪問介護事業所: ~50,000 家
  - 介護老人保健施設: ~4,500 家
  - 特別養護老人ホーム: ~10,000 家
  - サービス付き高齢者向け住宅: ~7,000 家
  - 介護コンサル: ~500 家 (B2B2C)
- **WTP 錨點**:
  - サ責 月 40-60 小時 × ¥3,000/時 = ¥120,000-180,000 機會成本 vs Solo ¥9,800/月 = **15-25x ROI**
  - ヘルパー離職率降 20% → 16% = 月省採用成本 ¥200,000-500,000

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | ¥0 | 1 query/月 | 試用 |
| **Solo** | ¥9,800/月 | 1 事業所 + 50 利用者 + LINE/メール通知 | 中小事業所 |
| **Pro** | ¥29,800/月 | 5 事業所 + 200 利用者 + 経営 dashboard + API | 中規模法人 |
| **Enterprise** | ¥98,000+/月 | 無制限 + 多法人 + 介護記録 ERP 連携 (カイポケ / ジョブカン) | 大手介護法人 |
| **Consultant** | ¥30,000+/月 | 介護コンサル white-label | 介護経営コンサル |
| **API** | ¥500/call | 介護 ERP integration | カイポケ / ジョブカン / e-care |

## Distribution

- **介護労働安定センター / 各都道府県介護協議会** partner (公益版 + PR)
- **介護経営者向け雑誌 / メディア** (シルバー新報 / シルバー産業新聞 / 介護ビジョン)
- **Facebook「介護経営者交流会 / 訪問介護サ責の会」** 数万人グループ
- **介護 ERP partner** (カイポケ / ジョブカン介護 / e-care / 介舟ファミリー) integration
- **介護コンサル B2B BD** (船井総合研究所 / シェアダイン / カイゴジョブ)
- **YouTube 介護経営 KOL** (介護のお仕事 / ケアマネジャー / 介護福祉士チャンネル)
- **介護福祉士国家試験 後コミュニティ** (新人 ヘルパー 入口)
- **東京ケアウィーク / 国際福祉機器展** (毎年 9 月) booth
- **跨境輸出**: 台灣 (carepen r7 互補) / 韓國 / 中港 高齢化市場

## TAM

- 0.5% × 50,000 訪問介護 = 250 × Solo ¥9,800 = **月 ¥245 萬** (≈ NT$ 53 萬)
- + Pro 100 × ¥29,800 = ¥298 萬/月
- + Enterprise 20 × ¥98,000 = ¥196 萬/月
- + Consultant 30 × ¥30,000 = ¥90 萬/月
- + API 5 × ¥100,000 = ¥50 萬/月
- 總計 **月 MRR ¥880 萬 / 年 ARR ¥1 億** (≈ NT$ 2,200 萬)
- 加滲透 + 橫移台灣 (carepen 路線) / 韓國 (요양 시장) / 中港 高齢化市場 → **¥5-10 億 ARR** (NT$ 1-2 億)

## 風險與限制

- **47 件 prototype 太小** -- real launch 需 ≥ 500 件多月份 assignment 歴史, 鼓勵事業所 contribute history 換 SaaS subsidy
- **過去配對偏差 / Cold-start**: 模型只從歷史 assignment 學, 新 staff / 新 利用者 PPMI=0; Pro 版加 metadata side-information (年資 / 専門分野 / 通勤距離 / 性別 / 認知症対応資格)
- **Bipartite 限制**: 無法捕捉「ヘルパー之間」「利用者之間」直接連結 (e.g. 仲良し同僚), Pro 版加 tripartite (staff / client / shift) or homogeneous graph projection
- **Random walk 隨機性**: walk seed 改變排序略有差異; prototype 固定 seed 確保可重現
- **Walk weight 偏差**: 高頻 staff 在 walks 中過度 represented; 低頻 staff 易被埋沒, Pro 版加 importance sampling
- **PPMI 對 sparse 敏感**: 樣本小時 PPMI 估計變異大; 真實 launch 需 ≥ 500-1000 條 history
- **介護法令制約**: 介護保険法 + 個人情報保護法, 雲端版需匿名化 + 加密 + 介護事業所同意 + 利用者 + 家族双重同意
- **不取代サ責専業判斷**: graph 推薦是 starting point, サ責 仍需 review 安全 / 排班 conflict / 利用者個性 / 家族意向
- **介護労働環境変動**: ヘルパー流動率高 + 利用者 物故 / 入院 = 模型需定期重訓 (建議月 1 次)
- **政策變動風險**: 介護保険報酬改定 (3 年 1 度) / 認知症対応加算 規定變更 → 排班邏輯需調整

---
*kaigomatch = DeepWalk + PPMI + cosine link prediction × 日本訪問介護事業所 staff-利用者 schedule matching niche = "過去 assignment 歴史 → graph embedding → 自動代理派遣 / 新人 onboarding マッチング", サ責 月 40-60 小時手動排班 → 5-10 小時 review graph 推薦, ヘルパー離職率 20% → 16%, 利用者満足度 + ヘルパー留任率 雙升。*
