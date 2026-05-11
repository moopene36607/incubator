# cropforecast -- 台灣蔬果批發價 Gaussian Process 14 天預測

**「高麗菜這兩個月從 NT$18 漲到 NT$36, 下週還會漲嗎? 我該不該現在出貨 / 進貨?」** 用 Rasmussen & Williams 2006 Gaussian Process Regression with RBF kernel 對歷史每日批發價建模, 給未來 14 天「**後驗均值 + 95% 信心區間 + 不確定性遞增曲線**」, 農民決策出貨時機, 量販 / 餐廳 / 加工業者決策採購時機, 三方拿到客觀統計數據。

## 痛點

台灣農產批發市場:
- **農戶**: 全台 64 萬戶 (農委會 2024)
- **蔬果批發市場**: 13 家公設拍賣市場 (台北一二果菜 / 三重 / 新北 / 桃園 / 台中 / 嘉義 / 高雄 / 屏東 等)
- **每日交易**: 蔬菜約 3,000 公噸 / 水果約 1,800 公噸
- **年產值**: 蔬菜 NT$ 700 億 + 水果 NT$ 850 億
- **下游**: 量販 (家樂福 / 全聯 / 全家) / 連鎖餐飲 (鼎泰豐 / 八方雲集 / 王品集團) / 學校 / 軍隊 / 加工 (食品廠)

**農民痛點** (PTT Farming / Dcard 農業 / FB「農民互助會」/「蔬果批發行情」5-10 萬人社群):
- 「今天送貨還是等三天再送, 多花 NT$ 10萬 油費 + 工費」
- 「老農說颱風前該搶送, 但我不知道颱風會不會來, 也不知道幾天會回穩」
- 「拍賣市場資訊不對稱 -- 大盤商有情報, 小農憑感覺」
- 「合約農想簽 3 個月期, 但不知道該鎖什麼價」

**採購端痛點** (餐飲 / 量販 / 加工業者):
- 「現在進貨 vs 等下週降價, 沒人能算每週能省多少」
- 「便當店每天進貨 30-50 kg, 1 元/kg 差距 = 月省 NT$ 1,500」
- 「全聯 / 家樂福 合約採購 需要 14 天預期區間做議價」

**現有資源**:
- 農委會 / 各拍賣市場 公布**昨日**成交價 (回顧性,不是預測)
- 部分學術論文做台灣蔬果價格預測 (但都在學術圈、未產品化)
- 老農經驗 (主觀, 同一品項不同人說法差很大)
- 大盤商 / 中盤商 (利益衝突, 不會公開預測模型)

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(cropforecast 補的) |
|---|---|---|
| 農委會 OpenData (台北農產 / 各拍賣市場) | 公布昨日成交價 + 數量 | **不做預測 / 不給信心區間** |
| AI 預測學術論文 (中興 / 台大 / 中研院) | 模型研究 | 沒產品化, 農民 / 採購用不到 |
| 老農 / 中盤經驗 | 主觀預測 | 落差大, 沒信心區間, 利益衝突 |
| 海外 USDA / EU agri-forecast | 美國 / 歐洲品種 | 不認識台灣高麗菜 / 鳳梨 / 釋迦 等品種 + 在地拍賣市場結構 |
| ChatGPT 一次問 | 一次性建議 | 不知歷史價、不能跑 GP、常 hallucinate |
| Excel 趨勢線 | 純線性 | 不給後驗 + 不給信心區間 + 不處理 GP 平滑 |
| **cropscan r20** (本 incubator) | 病蟲害 vision 分類 | 完全不同問題 (生產端 vs 行情端) |

**Gap 結構性**: Gaussian Process Regression (Rasmussen & Williams 2006) 學術界成熟 20+ 年, **沒人做成台灣蔬果批發價飼料 SaaS**。Google「台灣 蔬果 GP 預測」零本土 SaaS。批發價公開 OpenData 公益可合法取用、農民 / 採購雙邊都急需、學術 GP 工具現成 — 三大條件同時滿足卻**沒人做產品化**, 就是 niche。

## 架構 -- Gaussian Process Regression with RBF Kernel (50th 條 AI pattern)

```
60+ 天每日批發價 [day_t, price_t]
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 1. Centre y -> y_c = y - mean(y)              │
│ 2. Auto-tune hyperparameters (heuristic):    │
│    sigma_f = stdev(y)                         │
│    ell     = (max(X) - min(X)) / 10           │
│    sigma_n = 0.10 * stdev(y)                  │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Squared-Exponential (RBF) kernel:             │
│   k(x, x') = sigma_f^2 *                      │
│              exp(-(x-x')^2 / (2*ell^2))      │
│ Compute K = kernel_matrix(X, X)               │
│ K_noise = K + sigma_n^2 * I                   │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Solve: K_noise * alpha = y_c                  │
│   (via Gauss-Jordan partial pivoting)         │
│ Cache K_noise^-1 for fast prediction          │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Predict for new x*:                           │
│   k_star = [k(x*, x_i)]_i                     │
│   post_mean = y_mean + k_star^T alpha         │
│   post_var  = k(x*, x*) -                     │
│               k_star^T K_inv k_star          │
│   95% CI = post_mean ± 1.96 sqrt(post_var)   │
│   80% CI = post_mean ± 1.28 sqrt(post_var)   │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Diagnostics:                                  │
│   • Training RMSE                             │
│   • Log marginal likelihood (LML)             │
│   • Empirical CI coverage (hold-out)          │
│   • Mean band width relative to avg actual    │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + statistics + dataclasses):
- `rbf_kernel / kernel_matrix`: 平滑函數先驗的 RBF kernel
- `gauss_jordan_solve`: partial-pivoting linear solve (避免顯式 K_noise^-1 用於 alpha; 但 cache 一次 K_inv 給 variance 預測)
- `fit_gp`: 自動 hyperparameter heuristic + alpha + K_inv 預計算
- `predict_gp`: 後驗均值 + variance + 80% / 95% credible intervals
- `log_marginal_likelihood`: LML 用 LU forward pass 算 |K_noise| determinant (hyperparameter 調校診斷)
- `empirical_coverage`: hold-out CI 校正驗證
- `rmse / mean_band_width`: training fit + uncertainty 量化

**LLM 只負責**: 寫 250-330 字「給農民 + 採購方 + 加工業者 三類使用者兩週行動建議 + 颱風 / 政策風險提醒」
**LLM 絕不負責**: 計算 NT$ / variance / CI / LML (數字 100% 來自 GP)

### 為什麼 GP 適合這個 use case (vs Quantile r58 / Conformal r41 / kNN r54)

- **GP**: Bayesian nonparametric, 給**整條 posterior 曲線** + uncertainty 自然遞增 (D+1 σ=0.74 → D+14 σ=5.47), **小樣本表現好** (60 天即可訓練)
- **Quantile r58 rentquant**: 5 個獨立 quantile 模型, 適合**橫斷面** (每個物件給 quantile band), 不適合**時序預測** (沒 day index 順序假設)
- **Conformal r41 salaryci**: 給單一 90% interval, 不給時序遞增不確定性
- **kNN r54 constsim**: 找最相似歷史 case, 適合靜態 lookup, 不適合 trajectory forecasting

GP 的關鍵優勢: **不確定性 (CI 寬度) 隨預測距離平滑遞增**, 這是時序預測該有的數學保證 — D+14 比 D+1 不確定是常識, GP 直接給數字。

## 使用示例

```bash
# 純函式模式 (無 API key)
python3 cropforecast.py --data samples/wholesale_prices.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 cropforecast.py --data samples/wholesale_prices.json

# 自訂 hyperparameter
python3 cropforecast.py --sigma-f 8.0 --ell 14.0 --sigma-n 0.3
```

預期輸出 (詳見 `examples/sample_output.md`):

過去 60 天高麗菜從 NT$18 漲到 NT$36, 未來 14 天 GP 預測:

| D+ | 後驗均值 | 95% CI | 不確定性 σ |
|---|---|---|---|
| D+1 | NT$35.5 | [34.1, 37.0] | ±0.74 |
| D+7 | NT$31.1 | [23.3, 38.9] | ±3.99 |
| **D+14** | **NT$26.9** | **[16.1, 37.6]** | **±5.47** |

→ GP 看出近兩個月強漲是「青黃不接」效應, 預測二期菜進場後兩週內回落到 NT$27 區間;但 95% 區間 D+14 已寬達 NT$16-37, 反映**遠期不確定性大** (颱風 / 政策補貼 隨時改變)。

訓練 RMSE = NT$0.60/kg (60 天歷史 fit 很緊), LML = -92.2 (合理範圍, 適合此 hyperparameter)。

## 目標市場

- **TAM**:
  - 農戶 (B2C): 64 萬戶, 其中 5-30 公頃 中型農場 ~8 萬戶 (核心 WTP)
  - 拍賣市場 / 中盤商 (B2B): 13 家拍賣市場 + ~3,000 中盤商
  - 量販 / 餐飲採購 (B2B): 全聯 / 家樂福 / 全家 / 王品 / 八方雲集 / 鼎泰豐 等連鎖採購部
  - 加工業者: 罐頭 / 醬料 / 即食食品廠 ~500 家
  - 政府 / 公益: 農委會 / 各縣市農業處 / 農會 + 學校營養午餐採購
- **WTP 錨點**:
  - 農民: 一次「該不該出貨」決策若 1 公頃 高麗菜 NT$ 30 萬產值, 1% 價差 = NT$3,000, 月省幾次 = NT$5-30K
  - 採購: 全聯月採購高麗菜 NT$ 1-5 千萬, 0.5% 議價空間 = NT$5-25 萬/月
  - 加工業者: 月採購 NT$ 500 萬, 提前 14 天鎖價 vs spot 平均省 2-5% = NT$10-25 萬/月

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 商品 / 7 天預測 | 試用 |
| **Solo Farmer** | NT$299/月 | 3 商品 + 14 天 + LINE 推播 | 個人農戶 |
| **Pro Farm** | NT$1,499/月 | 10 商品 + 28 天 + 自訂 hyperparameter | 中型農場 |
| **Buyer** | NT$2,999/月 | 多商品 + 議價模板 + 採購預警 | 餐飲 / 量販採購部 |
| **Enterprise** | NT$15,000+/月 | 全品項 + API + 颱風 alert + 客製 | 全聯 / 家樂福 / 八方 |
| **Government** | 公益 | 農委會 / 縣市農業處 公益版 | 政府 |

## Distribution

- **FB「農民互助會 / 蔬果批發 / 農藝家」5-10 萬人社群** 案例分享
- **PTT Farming / Agriculture / Salary 板** 長尾 SEO
- **農會 / 產銷班** B2B BD (全台 300+ 農會 / 5,000+ 產銷班)
- **農委會 / 各縣市農業處 partner** (公益版 + PR)
- **YouTube 農業 KOL** (台灣那邊一群 / 城市農夫 / 上下游 News & Market)
- **拍賣市場 partner**: 台北農產 / 三重 / 桃園 拍賣市場 整合顯示
- **量販採購部 B2B BD**: 全聯 / 家樂福 / 全家 採購部 (Enterprise 試用)
- **餐飲連鎖 B2B**: 王品 / 八方 / 鼎泰豐 / 路易莎 採購部
- **農業展 / 食品展** (台中世貿 / 台北南港 每年 3 月) booth

## TAM

- 1% × 8 萬中型農場 = 800 × Solo NT$299 = **月 NT$24 萬 MRR**
- + Pro Farm 100 × NT$1,499 = NT$15 萬/月
- + Buyer 200 × NT$2,999 = NT$60 萬/月 (連鎖採購部多家、便當店、學校、軍隊)
- + Enterprise 20 × NT$15,000 = NT$30 萬/月 (全聯 / 家樂福 / 王品)
- 總計 **月 MRR NT$129 萬 / 年 ARR NT$1,550 萬**
- 加滲透 + 橫移日韓 (日本 JA 全農 / 韓國 농협 體系) → **NT$5,000 萬-1 億 ARR**

## 風險與限制

- **60 天 prototype 太短** -- real launch 需 ≥ 2-3 年歷史才能 capture 年度季節性 + 颱風事件;鼓勵農戶 / 拍賣市場 contribute data
- **RBF kernel 假設 smooth**: 真實有颱風 / 政策 / 出口管制 跳變, Pro 版加 white-noise kernel + 變點 detector;颱風前 / 後 GP 完全失效 (需 explicit 重訓)
- **單變數 day-index**: 此 prototype 只用 day 作 input; 真實需加 weather / 颱風 7 天窗口 / DOW / 連假 多 features (multi-dim GP)
- **homoscedastic 噪音**: σ_n 假設恆定, 真實週末 / 颱風 noise 大很多, Pro 版用 heteroscedastic GP
- **不適合突變後立即預測**: 颱風剛過 / 政策剛改, GP 仍按平滑歷史推, **必須 explicit 重訓** 並標示「模型失效」警告
- **隱性人為干預未捕捉**: 拍賣市場進場量被預期心理影響, GP 假設 stationarity 在這層失效
- **政府介入訊號未納入**: 農委會緊急進口 / 出口管制 / 補貼 政策能瞬間改變供需, GP 無從預知
- **不適合長期投資建議**: GP 看 14 天合適, > 30 天 95% 區間會擴到 ±50% 變得無實用價值; 此時應該用 ARIMA / VAR / 結構模型
- **不取代產地經驗**: 工具給統計區間, 實際出貨 timing 仍須 結合產地 / 物流 / 個別品質判斷

---
*cropforecast = Rasmussen & Williams 2006 Gaussian Process Regression × RBF kernel × 台灣蔬果批發價 niche = "agricultural OpenData + GP smoothing + uncertainty band" 三位一體, 終結批發市場「老農 vs 大盤 vs 採購」三角資訊不對稱, 100% 純函式 stdlib 即可訓練 + 預測 14 天 + 給後驗 + 95% CI。*
