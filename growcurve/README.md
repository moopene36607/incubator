# growcurve — 台灣 0-24 月嬰幼兒每日體重 Kalman filter 平滑 + WHO 百分位 + 異常警示

**「我家 4 個月寶寶每天量體重起伏 200-400 g, 看不出『真實趨勢』vs『量秤誤差』」** 用 Kalman filter (1960) + RTS smoother (1965) 把 daily noise 過濾掉, 還原 underlying weight trajectory + velocity (g/day), 結合 WHO 0-24 月生長標準 (P3/P15/P50/P85/P97) → 自動偵測「成長遲緩」「平台期」「rapid loss」並提早警示。

## 痛點

台灣每年:
- **新生兒**: 13.5 萬名
- **0-24 月嬰幼兒家庭**: ~28-30 萬戶
- **過去 2 年累計 0-2 歲家庭**: ~30 萬戶 (核心 WTP 族群)

**新手父母焦慮排行 #1 = 「寶寶體重正不正常」** (媽寶 / 親子王國 / Dcard 親子 / FB「新手爸媽討論區」每天 100+ 貼文):
- 「4 個月 6.5 kg 是不是太輕?」(每天問)
- 「為什麼這週體重沒長?是不是奶量不夠?」(焦慮)
- 「家裡體重計每天差 300 g, 到底哪個是真的?」(噪音問題)
- 「健兒門診 6 個月才一次, 中間怎麼追?」(無工具)

**現有資源**:
- 兒科診所健兒門診: 6 個月才看一次, 中間沒工具
- 衛福部 / WHO 0-2 歲生長曲線: 給 P3/P50/P97 圖表, 但 daily variance 大難判讀
- 家用體重計: ±100-300 g 誤差
- 第三方育兒 APP (媽咪愛 / 寶寶饗食): 紀錄但不平滑 + 不警示

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(growcurve 補的) |
|---|---|---|
| 衛福部 / WHO 生長曲線圖 | 給 P3/P50/P97 reference | 不平滑你家 noisy data,不算 velocity g/day |
| 媽咪愛 / 寶寶饗食 APP | 紀錄 daily 體重 | 純圖表, 不做 Kalman filtering, 不警示 |
| 兒科診所 6-mo 健兒 | 專業檢查 | 中間 6 個月空白, 無工具 |
| Excel + 趨勢線 | 線性回歸 | 不處理 obs noise model, 不分 underlying state |
| ChatGPT 直接問 | 一次性建議 | 不能跑 Kalman recursive, 沒持續分析 |

**Gap 結構性**: Kalman filter (1960) 學術成熟 65 年,**沒人做成台灣繁中嬰幼兒生長監控 SaaS**。Google「嬰兒體重 Kalman filter」零本土 SaaS 結果。

## 架構 — Kalman filter + RTS smoother (41st 條 AI pattern)

```
Noisy daily weight measurements (±100-300 g)
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Forward filter (k = 1..T):                  │
│   Predict: x̂_{k|k-1} = F × x̂_{k-1|k-1}     │
│            P_{k|k-1}  = F × P × F^T + Q     │
│   Update:  K_k = P_{k|k-1} × H^T / S        │
│            x̂_{k|k} = x̂ + K × (y - H × x̂)   │
│            P_{k|k} = (I - K × H) × P        │
└─────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ RTS smoother backward (k = T-1..0):         │
│   G_k = P_{k|k} × F^T × P_{k+1|k}^-1        │
│   x̂_{k|T} = x̂_{k|k} + G_k × (x̂_{k+1|T}     │
│             - x̂_{k+1|k})                   │
└─────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Output:                                      │
│  • Smoothed weight trajectory                │
│  • Smoothed velocity (g/day)                 │
│  • WHO percentile at current age             │
│  • Anomaly flags (urgent/moderate)           │
└─────────────────────────────────────────────┘
                  │
                  ▼
                LLM
   (餵食建議 + 就醫紅旗 + 情緒安撫)
```

**State**: x = [weight_kg, velocity_kg_per_day]^T  ·  **F** = [[1, dt], [0, 1]]  ·  **H** = [1, 0]

**100% 純函式 stdlib** (math + dataclass), 2×2 matrix operations 手刻:
- `mat2x2_mul / transpose / inv / add / sub`: 2x2 matrix algebra
- `kalman_forward`: Kalman filter + 完整 state + covariance history
- `rts_smoother`: backward smoother
- `kalman_pipeline`: full forward + backward + result extraction
- `WHO_BOY_P50_KG / WHO_GIRL_P50_KG`: 0-24 月參考值 (12 月齡點)
- `interpolate_who`: linear interp between months
- `who_percentile`: z-score → percentile via standard normal CDF (math.erf)
- `detect_anomalies`: velocity_below_normal / plateau / rapid_loss / below_p3

**LLM 只負責**: 220-300 字「餵食建議 + 就醫紅旗 + 情緒安撫」
**LLM 絕不負責**: 計算 Kalman state / percentile / velocity / anomaly thresholds (數字 100% 來自純函式)

## 使用示例

```bash
# 純函式模式 (無 API key)
python growcurve.py --log samples/baby_log.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python growcurve.py --log samples/baby_log.json
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陳小寶 4 個月男嬰, 21 天):

| 指標 | 起始 | 目前 | 變化 |
|---|---|---|---|
| Smoothed 體重 | 6.447 kg | **6.624 kg** | +177 g |
| WHO 百分位 | P~20 | **P~24** (P15-50 低標) | — |
| Smoothed 增重速率 | — | **8.4 g/day** | — |
| Raw min/max | — | 6.26 / 6.79 (530 g 噪音) | — |
| Smoothed range | — | 6.45 / 6.62 (170 g 真實) | — |

→ **Kalman 過濾掉 360 g 噪音**, 還原 underlying 8.4 g/day 增重速率, **觸發 urgent velocity_below_normal flag** (4 月齡正常 18 g/day, 此寶 < 50%)。

## 目標市場

- **TAM**:
  - 0-24 月嬰幼兒家庭 ~30 萬戶
  - 加上 0-5 歲累計 ~80-100 萬戶
- **WTP 錨點**:
  - 兒科自費門診 NT$500-1,500/次 × 5-10 次焦慮諮詢 = NT$3-15K vs Solo NT$199/月 = **5-25x 便宜**
  - 早期發現成長遲緩 (failure to thrive) 介入, 避免 6 個月後才發現的代價 (智力 / 身高 影響不可逆)

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 7 天 + 基本平滑 | 試用 |
| **Solo** | NT$199/月 | 無限天 + WHO 對照 + LINE 警示 | 個人家庭 |
| **Family** | NT$399/月 | 多寶寶 + 配偶共享 + 月度兒科報告 | 多孩家庭 |
| **Pro Pediatric** | NT$1,999/月 | 兒科醫師 client dashboard + EHR API | 兒科診所 |
| **Hospital** | NT$15,000+/月 | 大型醫院 NICU / 早產兒中心 EHR 整合 | 馬偕 / 國泰 / 長庚 |

## Distribution

- **媽寶 / 親子王國 / Dcard 親子 / FB「新手爸媽討論區」** 5-15 萬人社群案例分享
- **YouTube 兒科 KOL** (阿包醫生 / 黃瑽寧醫師 / 巫漢盟醫師) 案例合作
- **媽咪愛 / 寶寶饗食 / 育兒寶** APP 整合 partner
- **月子中心** B2B BD (~200 連鎖) — 月嫂用作交班工具
- **兒科診所 / 大型醫院** B2B (馬偕 / 國泰 / 長庚) 健兒門診工具
- **媽媽教室 / Lamaze 課程** partner
- **嬰兒博覽會** 台北南港每年 4 月 booth

## TAM

- 1% × 30 萬 = 3,000 × NT$199 = **月 NT$60 萬**
- + Family 1,000 × NT$399 = NT$40 萬/月
- + Pro Pediatric 100 × NT$1,999 = NT$20 萬/月
- + Hospital 20 × NT$15K = NT$30 萬/月
- 總計 **月 MRR NT$150 萬 / 年 ARR NT$1,800 萬**
- 加滲透 + 橫移日韓港新東南亞母嬰 → 翻倍至 **NT$4,000-6,000 萬 ARR**

## 風險與限制

- **Linear-Gaussian 假設**: 真實生長有 nonlinear 成分 (e.g., 出生後 weight loss 5-7 天再上升);Pro 版可用 EKF / UKF
- **Process noise σ² 是 prior**: 預設保守, 個別寶寶可調 (e.g., 早產兒高 process noise)
- **觀察 noise**: 家用體重計 ~100-200g 噪音, 醫院級電子秤可調低
- **WHO 是全球標準**: 台灣寶寶平均體型較亞洲基準, Pro 版用 CDC / 台灣兒科 NHI 標準
- **量秤條件統一性**: 餵奶前 vs 餵奶後可差 200-500 g;UI 必須提示「每天固定時段量」
- **不取代兒科醫師**: 工具 = 監控 + 警示,確診 / 治療仍需專業評估
- **隱私敏感**: 嬰兒體重 / 性別涉個資 + 醫療性質, 雲端版需加密 + 家長同意 + 資料留存政策

---
*growcurve = Kalman 1960 filter + Rauch-Tung-Striebel 1965 smoother × 台灣繁中 0-24 月嬰幼兒生長監控 niche = 把 daily ±200g 量秤噪音過濾, 還原真實 weight trajectory + 即時 percentile + 異常警示。*
