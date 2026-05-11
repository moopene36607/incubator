# crybabel — 台灣繁中嬰幼兒哭聲 Random Forest 分類 + 安撫腳本

**「我家寶寶哭超過 30 分鐘了 — 是餓?累?痛?colic?」** 用 Random Forest (Breiman 2001) 從哭聲特徵 + 情境 (距上次餵奶 / 換尿布 / 小睡時間) 分類 7 類 cry types,給新手父母**5 分鐘內可做的 3 個動作 + 就醫紅旗**。把 ChatterBaby / Cry Translator 英語市場成熟 7-8 年的工具,帶進**繁中 / 日韓母嬰市場**。

## 痛點

台灣每年:
- **新生兒**: 13.5 萬名 (2024 年)
- **0-12 月嬰兒**: ~14 萬個家庭
- **新手父母焦慮高峰**: 0-3 月,90% 母親 / 70% 父親自評「不知道孩子為什麼哭」

**親子王國 / 媽寶 / Dcard 親子 / FB「新手爸媽討論區」** 5-15 萬人社群,每天 100+「寶寶哭不停」貼文:
- 「寶寶剛吃完還在哭, 是還想吃還是 colic?」(每天問)
- 「哭聲突然變很高頻很尖, 是不是身體哪裡卡住?」(急性焦慮)
- 「半夜哭 1 小時, 換尿布也餵了, 怎麼辦?」(疲憊崩潰)

**新生兒科 / 月子中心 / 親子教練 諮詢費**:
- 兒科診所 NT$300-1,500/次, 排隊 1-2 週
- 月子中心 月費 NT$15-30 萬, 限產後 28 天
- 親子教練 / 嬰幼兒按摩 NT$3-8K/次

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(crybabel 補的) |
|---|---|---|
| ChatterBaby (USC), Cry Translator | 英語市場,音訊分類 | **沒繁中版本**,不認識台灣母嬰文化 (月子餐 / 父母輪班結構) |
| 寶寶饗食 / 媽咪愛 APP | 哺乳追蹤 / 育兒紀錄 | 不做哭聲分類 |
| LINE 親子聊天群 | 媽媽互相問答 | 沒系統化, 沒專業, 焦慮放大 |
| 月子中心月嫂 | 一對一指導 | 只限產後 28 天, 之後 11 個月空白 |
| ChatGPT 直接問 | 一次性建議 | 不能持續學習你寶寶的 baseline, 沒 RF 量化分類 |

**Gap 結構性**: Random Forest (Breiman 2001) 學術界成熟 24 年,**沒人做成台灣繁中嬰幼兒哭聲分類 SaaS**。Google「嬰兒哭聲 AI 分類 中文」零本土 SaaS 結果。

## 架構 — Random Forest classification (38th 條 AI pattern)

```
Cry feature input (7 維):
  pitch_mean_hz / duration_s / rhythm_regularity / intensity_slope
  + time_since_feed/diaper/nap (context)
            │
            ▼
┌─────────────────────────────────────────┐
│ Training: 105 labeled samples           │
│ (7 classes × 15 per class)              │
└─────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│ For each of n_trees:                    │
│   1. Bootstrap sample (with replace)    │
│   2. Build CART decision tree           │
│      - At each split: random √F feats  │
│      - Choose split minimizing Gini    │
│      - Recurse until pure / max_depth   │
└─────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│ Predict new event:                      │
│   Each tree votes a class               │
│   Forest = majority vote                │
│   Confidence = winning vote share       │
│   Class probabilities = all shares      │
└─────────────────────────────────────────┘
            │
            ▼
   Pred + confidence + feature importance
```

**100% 純函式 stdlib** (random + math + collections + dataclass):
- `gini_impurity`: 1 - Σp_i² (純度測量)
- `find_best_split`: 隨機 √F features × midpoint thresholds → 找最小 weighted Gini
- `build_tree`: CART recursion, max_depth bound, leaf when pure
- `bootstrap_sample`: 有放回採樣
- `fit_forest`: ensemble bagging
- `predict_one`: majority vote + per-class probabilities
- `feature_importance_simple`: depth-weighted feature usage frequency

**LLM 只負責**: 寫 220-300 字「安撫腳本 + 就醫紅旗 + 情緒支持」
**LLM 絕不負責**: 計算 RF prediction / confidence / class probabilities (數字 100% 來自 RF)

## 使用示例

```bash
# 純函式模式 (無 API key)
python crybabel.py --events samples/cry_events.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python crybabel.py --events samples/cry_events.json

# 自訂樹數 / 深度
python crybabel.py --trees 200 --max-depth 10
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陳小寶 3 月女嬰, 19:00 哭超過 5 分鐘):

| 特徵 | 值 | 直覺意義 |
|---|---|---|
| 主頻率 | **820 Hz** | 高頻 (痛 / colic 嫌疑) |
| 持續 | **210 秒** | 長 (>90 秒) |
| 規律性 | **0.15** | 極不規律 (爆發型) |
| 強度趨勢 | **+0.70** | 快速升強 (急迫) |

**RF 預測**: 💢 **腸絞痛 (colic)** 信心 **90.0%** (72/80 棵樹投這類)

→ 給媽媽具體 3 步驟:包巾側躺 + 白噪音 + 奶嘴吸吮,以及 6 種就醫紅旗 (體溫 38°C+ / 嘔吐墨綠 / 哭聲虛弱)。

## 目標市場

- **TAM**:
  - 0-12 月嬰兒家庭 ~14 萬戶/年
  - 過去 5 年累計 0-5 歲家庭 ~70 萬戶
  - 共 **70-80 萬潛在用戶**
- **WTP 錨點**:
  - 兒科診所 NT$500/次 × 3-5 次焦慮諮詢 = NT$1.5-2.5K vs Solo NT$199/月 = 5-12x 便宜
  - 月嫂 NT$15-30 萬只 28 天, crybabel 持續 12 個月

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 5 次/月 + 基本 4 類分類 | 試用 |
| **Solo** | NT$199/月 | 無限次 + 7 類完整 + LINE 推播 | 個人媽媽 |
| **Family** | NT$399/月 | 多寶寶 (雙胞胎 / 二寶) + 配偶共享 | 多孩家庭 |
| **Confinement** | NT$2,999/月 | 月子中心 white-label 整合 + 多新生兒 | 月子中心 |
| **Hospital** | NT$15,000+/月 | 兒科診所 / 醫院 衛教工具 + EHR API | 醫療機構 |

## Distribution

- **親子王國 / 媽寶 / Dcard 親子 / FB「新手爸媽討論區」** 5-15 萬人社群
- **YouTube 育兒 KOL** (嬰兒友善老師 / 嬰兒按摩 / 親子作家) 案例
- **媽咪愛 / 寶寶饗食** APP 整合 partner
- **月子中心** B2B BD (台灣 200+ 月子中心連鎖)
- **兒科診所 / 大型醫院** B2B (馬偕 / 國泰 / 長庚)
- **媽媽教室 / Lamaze 課程** partner
- **嬰兒博覽會** 台北南港每年 4 月

## TAM

- 1% × 14 萬新生兒家庭 = 1,400 × NT$199 = **月 NT$28 萬**
- + Family 500 × NT$399 = NT$20 萬/月
- + Confinement 50 × NT$2,999 = NT$15 萬/月
- + Hospital 20 × NT$15K = NT$30 萬/月
- 總計 **月 MRR NT$93 萬 / 年 ARR NT$1,100 萬**
- 加滲透 + 橫移日韓港新東南亞母嬰 → 翻倍至 **NT$3,000-5,000 萬 ARR**

## 風險與限制

- **訓練資料 simulated** — prototype 用合成 features, 真實 launch 需 ≥ 1000 件兒科 / 月子中心標註資料
- **哭聲特徵需要 audio extract** — prototype 用數值輸入, 真實 app 需錄音 → MFCC 抽取 (librosa / Claude audio API)
- **個別寶寶差異** — 每個寶寶哭聲 baseline 不同, Pro 版加 per-baby calibration (前 2 週 baseline)
- **多類別不平衡** — colic 比 hungry 罕見, Pro 版用 weighted classes / SMOTE
- **不取代醫師** — 痛 / 異常哭聲永遠優先送醫;UI 必須明顯標就醫紅旗
- **新手父母 anxiety** — anchor 在 AI 給的 prediction 反而忽略其他 signals;UI 上強調「3 個動作試試 + 不見效就重新評估」

---
*crybabel = Breiman 2001 Random Forest × 台灣繁中嬰幼兒哭聲 niche = 把 ChatterBaby 7 年英語成熟 SaaS 帶進母嬰中文市場第一名痛點。*
