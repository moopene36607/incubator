# rentquant -- 台灣租屋月租 Quantile Regression (P10 / P50 / P90 band)

**「房東開 NT$28K 大安 10 坪套房, 591 跟我說『行情價』, 朋友說『被坑』, 到底誰對?」** 用 Koenker & Bassett 1978 Quantile Regression 從歷史 listings 訓練 5 個 quantile 模型 (P10 / P25 / P50 / P75 / P90), 給每個物件一條 90% 行情 band -- 房東知道天花板, 房客知道議價底線, 雙方都拿到客觀第三方錨點。

## 痛點

台灣租屋市場:
- **租屋族**: ~200 萬戶 (內政部統計)
- **每年新合約**: 50-80 萬份
- **市場規模**: 月租總額約 NT$ 400-600 億 / 月
- **租屋族佔家庭**: 12% (台北市 25%+)

**房客痛點** (PTT home-rent / Dcard 租屋 / 媽寶 / 大學新生 8-9 月 / FB「台灣租屋族」5-10 萬人社群):
- 「找了 5 間房東開價差 NT$10K, 怎麼算合理?」(每週重複)
- 「591 估價只給單一數字, 不知道議價空間」
- 「同一條巷子 3 棟差不多公寓, 一棟開 NT$22K 一棟開 NT$28K 一棟開 NT$32K」
- 「不知道哪個是行情、哪個是被坑、哪個是撿到便宜」

**房東痛點**:
- 不知道自己物件市場行情 → 開太低少收入 / 開太高招租 3-6 個月空租
- 包租代管業者報的「市場行情」常壓低 (要賺管理費)
- 一年漲幅幅度沒參考 (《住宅租賃契約應記載事項》規定年漲幅有限制)

**現有資源**:
- 591 / 樂屋網 / 信義房屋租賃 — listing 平台但**無 quantile band 估價**
- 房東 / 包租代管業者 自報 (利益衝突)
- 「同事都租多少」社群分享 (sample 太小, bias 嚴重)
- 內政部不動產交易實價查詢 (買賣有, 租賃**部分公開** 2021 包租代管制度後才強制)

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(rentquant 補的) |
|---|---|---|
| 591 / 樂屋網 / 信義租賃 | listing + 篩選 | 無 quantile band 估價 / 議價錨點 |
| 591 估價 | 給單一估價數字 (買賣為主) | 不給 P10-P90 範圍, 房東 / 房客沒議價基準 |
| 包租代管 業者 | 媒合 + 收費 | 利益衝突, 不給客觀 band |
| 內政部不動產實價查詢 | 買賣 + 部分租賃 OpenData | UI 糟、不做 quantile regression、不在地化議價建議 |
| ChatGPT 一次問 | 一次性建議 | 不能學歷史 listings, 沒持續分位數模型 |
| Excel + 自己手算 | 純手動 | 沒 pinball loss minimisation, 沒做 quantile 校正 |
| 海外 Zillow / Rentometer | 海外為主 | 不認識台灣 (大安 / 信義 / 板橋) 行政區 + 套房 / 雅房 / 整層 / 分租公寓 文化分類 |

**Gap 結構性**: Quantile Regression (Koenker & Bassett 1978) 學術成熟 47+ 年, **沒人做成台灣租屋族可用 SaaS**。Google「台灣 租屋 quantile regression」零中文 SaaS。租屋月租公允性是「200 萬租屋族每月都關心」但**永遠沒人給客觀統計第三方答案**, 大家憑感覺 / 朋友 / 房東說了算。**跟 leasecheck r24 互補** — r24 審「條款違法性」, rentquant 審「月租公允性」。**跟 propvision r19 不同** — r19 是房屋**買賣**價估算, rentquant 是**租賃**月租估算 (兩個完全不同市場)。

## 架構 -- Quantile Regression with Pinball Loss (48th 條 AI pattern)

```
74+ 歷史 listings (district, property_type, 坪數, 屋齡, 樓層, 電梯, 陽台, 月租)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ FeatureEncoder:                               │
│   numeric: z-score (mean / pstdev)            │
│   categorical: one-hot (drop-first reference) │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Pinball (check) loss per (y, yhat, tau):     │
│   L_tau(y, yhat)                              │
│   = (y - yhat) * tau         if y >= yhat    │
│   = (yhat - y) * (1 - tau)   if y < yhat     │
│                                                │
│ Convex but non-smooth at y = yhat;            │
│ subgradient well-defined.                     │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Train ONE linear model per tau in            │
│   {0.1, 0.25, 0.5, 0.75, 0.9}                │
│ via subgradient descent:                      │
│   for each i:                                 │
│     g_i = -tau   if y_i > yhat_i             │
│         = 1-tau  if y_i < yhat_i             │
│         = 0      if y_i == yhat_i            │
│   db0    = mean(g_i)                          │
│   dbeta_j = mean(g_i * x_ij)                  │
│   b0    -= lr * db0                           │
│   beta  -= lr * dbeta                         │
│                                                │
│ Init b0 to tau-th sample quantile of y.       │
│ Converge on |Δ pinball_loss| < tol.           │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Predict for new x:                            │
│   raw_q[tau] = b0[tau] + dot(beta[tau], x)   │
│   sorted_q = sort(raw_q.values()) ascending   │
│   final_q[tau_i] = sorted_q[i]                │
│   (post-hoc monotonicity guard)              │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Negotiation anchors:                          │
│   walk_away  = P10                            │
│   fair_low   = P25                            │
│   median     = P50                            │
│   fair_high  = P75                            │
│   ceiling    = P90                            │
│ Classify offer to 5 bands with action.        │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + statistics + dataclasses + random + collections):
- `FeatureEncoder`: numeric z-score + categorical one-hot drop-first
- `pinball_loss_one / pinball_loss_mean`: 標準 check loss
- `fit_quantile`: 一 tau 一個 linear model, subgradient GD
- `predict_quantiles`: 5 個 tau 預測 + 排序後處理保證 monotonicity
- `check_coverage / coverage_report`: 訓練集 calibration (應接近 tau)
- `negotiation_anchors`: 5 個議價錨點
- `classify_offer`: 5 種房客判決 (撿到便宜 / 合理偏低 / 行情價區間 / 偏高 / 超出行情)

**LLM 只負責**: 寫 250-330 字 (給房客的議價腳本 OR 給房東的訂價 + 招租建議)
**LLM 絕不負責**: 計算 NT$ / quantile / coverage / classification (數字 100% 來自 QR 純函式)

### 為什麼 Quantile Regression 比 Conformal CI (Round 41 salaryci) 更合適這個 use case

- **salaryci r41 (conformal CI)**: 給 single 90% confidence interval (e.g. [60K, 84K]), distribution-free, exchangeability 假設
- **rentquant r58 (quantile regression)**: 給 5 個獨立 quantile 預測 (P10/P25/P50/P75/P90), 顯式建模條件分布

對議價來說:
- 房客要的不只是「90% 區間」, 而是「P10 是撿到便宜 / P75 是議價空間 / P90 是天花板」5 個錨點各自獨立決策意義
- Quantile band 不對稱: 大安 套房 P10-P50 差距可能跟 P50-P90 差距不同, conformal CI 強制對稱
- 房東訂價需要 P75 (合理偏高) 而非 P50 + width, quantile regression 直接給

## 使用示例

```bash
# 純函式模式 (無 API key)
python rentquant.py --data samples/taipei_rentals.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python rentquant.py --data samples/taipei_rentals.json

# 增加 iter
python rentquant.py --max-iter 8000
```

預期輸出 (詳見 `examples/sample_output.md`):

陳小姐 大安 10 坪 套房 15 年 4F 電梯+陽台, 房東開 NT$28K:

| 分位數 | NT$ |
|---|---|
| P10 (撿到便宜) | 9,536 |
| P25 (議價底線) | 11,580 |
| **P50 (行情中位)** | **18,106** |
| P75 (合理偏高) | 26,070 |
| P90 (超出行情) | 35,010 |

→ NT$28K 落 P75-P90 之間 → **🟠 偏高 → 建議議價 5-10% 或換物件**。給房客一個明確錨點: NT$25K-26K 是合理議價目標, 房東咬死 NT$28K 就 walk-away (大安一個月有充足 listing 流量)。

訓練集 calibration: P10 = 9.5% / P25 = 24.3% / P50 = 51.4% / P75 = 74.3% / P90 = 90.5% (所有 quantile 在 ±2% 內) — 模型 well-calibrated。

## 目標市場

- **TAM 雙邊**:
  - 房客 (B2C): 200 萬租屋族 / 每年 50-80 萬份新合約
  - 房東 (B2B-lite): 50 萬個人房東 + 5,000 包租代管業者 + 10,000 房仲商用部
  - 房仲 (B2B): 60,000 房仲業務員 (永慶 / 信義 / 中信)
- **WTP 錨點**:
  - 房客 NT$99/月 vs 「被開 P90 (overpay NT$5-10K/月)」 = **50-100x 防損保險**
  - 房東 NT$299/月 vs 「空租 3 個月損失 NT$60-100K」 = **200-300x ROI**
  - 房仲 NT$799/月 vs 「議價失敗失客 1 件 NT$10-30K」 = **12-37x ROI**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 次估價/月 | 房客試用 |
| **Solo** | NT$99/月 | 無限次估價 + 議價腳本 + LINE Bot | 個人房客 |
| **Landlord** | NT$299/月 | 無限次 + 訂價建議 + 招租週期估算 + LINE 警示 | 個人房東 |
| **Agent** | NT$799/月 | 房仲業務員 多物件 portfolio + API + 議價腳本批量 | 房仲業務員 |
| **Management** | NT$2,999/月 | 包租代管 5-50 物件管理 + 跨區 benchmark | 包租代管業者 |
| **Brand** | NT$15,000+/月 | 永慶 / 信義 / 中信 white-label + 客製 + 跨平台 API | 房仲品牌 |

## Distribution

- **PTT home-rent / home-sale / Soft_Job** 板長尾 SEO
- **Dcard 租屋 / 住宿 / 大學新生 / 新婚** 板
- **FB「台灣租屋族 / 北漂租屋 / 大安信義租屋」** 5-10 萬人社群案例分享
- **大學新生季 (8-9 月)** Google Ads + 校園社團
- **591 / 樂屋網 / 信義房屋租賃** integration partner (Brand 合作)
- **永慶 / 信義 / 中信房屋 / 台慶不動產** 房仲業務員 B2B BD
- **YouTube 居家 / 房地產 KOL** (Goris Hong / 米爸看房 / 房市觀察家)
- **內政部地政司 / 縣市租賃服務站** partner (公益版)
- **崔媽媽 / 法扶基金會** partner (跟 leasecheck r24 配套, 月租公允性 + 條款合法性 一站式)

## TAM

- 0.5% B2C × 200 萬租屋族 = 10,000 × NT$99 = **月 NT$99 萬**
- + Landlord 2,000 × NT$299 = NT$60 萬/月 (50 萬個人房東 0.4%)
- + Agent 1,000 × NT$799 = NT$80 萬/月 (60,000 房仲 1.7%)
- + Management 100 × NT$2,999 = NT$30 萬/月
- + Brand 5 × NT$15,000 = NT$7.5 萬/月
- 總計 **月 MRR NT$276 萬 / 年 ARR NT$3,300 萬**
- 加滲透 + 橫移港新馬 / 日韓租屋市場 (日本 1700 萬租屋族 + 韓國 1500 萬) → **NT$8,000 萬-1.5 億 ARR**

## 風險與限制

- **74 件 prototype 太小** — 真實 launch 需 ≥ 5,000 件多縣市 / 多月份, 鼓勵房東 / 房客 contribute listings 換取免費 Pro 月
- **線性假設**: Q_τ(Y | X) 假設線性 X, 真實有非線性 (坪數 × 區域 交互), Pro 版用 quantile GBM / quantile forest / kernel quantile regression
- **獨立 τ 模型可能交叉**: 已用排序後處理保證 P10 ≤ P25 ≤ P50 ≤ P75 ≤ P90 monotone 非減, Pro 版可用 simultaneous quantile regression
- **季節 / 通膨未捕捉**: 暑假 vs 平日 + 物價漲跌 + 北市政府租金管制政策, Pro 版加 month / year / 行政區政策 feature
- **不含實地特徵**: 採光 / 噪音 / 鄰居 / 房東個性等價格決定因素無法量化, 工具給統計區間, 個人感受仍需實地看 2-3 次不同時段
- **訂金 / 押金 / 違約金 條款合法性不審**: rentquant 給月租公允性, 但合約條款違法性 (押金上限 2 個月 / 違約金上限 1 個月) 屬 leasecheck (Round 24) 範圍, 兩工具配套使用
- **大安 (參考類別) 預測可能偏保守**: 由於 one-hot drop-first, 反映在 intercept; 大樣本 + 充分 iter 可校正
- **隱私敏感**: rental data 含地址 + 房東聯絡, 雲端版需匿名化 + 房東 / 房客同意 + 資料留存政策 + GDPR / 個資法
- **不取代房仲專業**: 工具給統計區間, 物件議價最終仍需房仲 / 律師 / 自己實地評估

---
*rentquant = Koenker & Bassett 1978 Quantile Regression × 台灣租屋月租公允性 niche = 給每個物件 P10-P90 band 而非單一估價, 房東 + 房客 + 房仲 三方都拿到客觀第三方錨點, 終結「591 給一個數字 / 朋友說被坑 / 房東說行情」的主觀爭執。*
