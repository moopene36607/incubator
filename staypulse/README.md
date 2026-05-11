# staypulse -- 台灣民宿 / B&B 房價彈性 MCMC Bayesian 動態定價

**「花蓮民宿 60 晚資料平日定 2,400 / 週末 3,500, 但連假該定 4,500 還是 5,000?入住率掉幾%還是賺?」** 用 Metropolis & Hastings 1953/1970 Markov Chain Monte Carlo 對 Bayesian logistic 需求模型抽樣 — 從 60 晚歷史資料推論 (alpha, beta_price, beta_weekend, beta_holiday) 後驗分佈, 給「平日 / 週末 / 連假」**每個情境** 最佳定價 + 預期收入 90% 區間, 民宿老闆從「憑感覺」變成 Bayesian decision。

## 痛點

台灣民宿 / B&B 市場:
- **合法民宿**: ~13,000 家 (觀光局 2024 統計)
- **中小型旅館**: ~2,500 家
- **每年觀光客**: 國內 1.7 億人次, 國際 760 萬人次
- **平均住宿支出**: 每人每晚 NT$1,500-4,500
- **市場規模**: 民宿 + 中小旅館 年產值 ~NT$ 400-500 億

**民宿老闆痛點** (PTT TaiwanTour / Dcard 旅遊 / FB「台灣民宿主交流會」3-5 萬人社群 / 民宿協會 LINE 群):
- **80% 是兼職** (退休族 / 第二事業), 沒受過動態定價訓練, 憑感覺定價
- 「平日定 2,400 是不是太便宜?客人都被別家搶走?」(每月重複)
- 「連假漲價怕被罵, 不漲又少賺一年最重要的 8 個檔期」
- 「Airbnb / Booking / Agoda 抽 15-20% 卻不給定價建議」
- **旺季少賺 + 淡季空房**, 一進一出**年損 NT$20-100 萬**

**現有資源**:
- Airbnb / Booking 提供「Smart Pricing / Dynamic Pricing」但是英美中心、**演算法黑盒**、不認識台灣連假
- 大型連鎖 (晶華 / 雲品 / 國賓) 有 RM (Revenue Management) 部門 + 自家系統, 中小民宿用不到
- 民宿協會 / 觀光局訓練講座教觀念, **不給工具**
- AirDNA / Beyond Pricing 是國外 SaaS, 月費 USD$100+, 不認識台灣連假與 OTA 結構
- 民宿 ERP (旅安 / 易遊網 / 速立達) 是訂房管理工具, **無 dynamic pricing 模組**

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(staypulse 補的) |
|---|---|---|
| Airbnb Smart Pricing | 自動建議房價 | **黑盒** 不解釋為什麼, 不認識台灣連假, 民宿主沒判斷依據 |
| Booking Genius Pricing | 平台推銷折扣 | 平台立場利益衝突, 老闆失主動權 |
| AirDNA / Beyond Pricing | 海外 dynamic pricing | USD$100+ / 月, 不在地化 |
| 民宿 ERP (旅安 / 易遊網 / 速立達) | 訂房 / 帳務 / 客戶 | **沒有定價模組** |
| 民宿協會 / 觀光局 講座 | 教觀念 + 補助 | **沒給工具** |
| ChatGPT 一次問 | 一次性建議 | 不知歷史資料 + 不能跑 MCMC + 沒持續學習 |
| Excel + 經驗 | 純手動 | 不算 posterior + 不給信心區間 + 不分情境 |

**Gap 結構性**: Markov Chain Monte Carlo (Metropolis 1953 / Hastings 1970) 學術成熟 50+ 年, **沒人做成台灣繁中民宿可用 SaaS**。Google「台灣 民宿 MCMC 動態定價」零中文 SaaS。民宿主、平台抽 15-20% 卻只給黑盒、海外 SaaS 太貴又不在地化 — 三大條件同時滿足卻**無人產品化**, 經典 niche。**跟 rentquant r58 不同市場** — r58 長租 quantile regression, r61 短租 MCMC Bayesian; **跟 cropforecast r60 不同方法** — r60 GP 時序預測, r61 MCMC 後驗推論。

## 架構 -- Metropolis-Hastings MCMC for Bayesian Logistic Demand (51st 條 AI pattern)

```
60+ 晚每日 booking history: (price, is_weekend, is_holiday, booked)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Bayesian logistic demand model:               │
│   logit P(book_i) = alpha                     │
│                   + beta_price * log(p/p0)    │
│                   + beta_weekend * w_i        │
│                   + beta_holiday * h_i        │
│ Priors (informative):                         │
│   alpha        ~ N(0.0,  2.0)                 │
│   beta_price   ~ N(-2.0, 1.5) (彈性 < 0)     │
│   beta_weekend ~ N(0.8,  0.5)                 │
│   beta_holiday ~ N(1.2,  0.5)                 │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Metropolis-Hastings random-walk sampler:     │
│   for t in 1..N:                              │
│     θ' = θ_t + N(0, σ_prop)  (joint propose) │
│     log α = log π(θ') - log π(θ_t)            │
│     u ~ U(0,1)                                │
│     if log u < log α:  accept θ_{t+1} = θ'    │
│     else:              θ_{t+1} = θ_t          │
│                                                │
│ Burn-in 1,000 + thin 2 + collect 2,000 samples│
│ Target acceptance ~25% (健康範圍 10-50%)      │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Posterior summarisation:                      │
│   • 後驗均值 + SD per parameter               │
│   • 95% credible interval (equal-tailed)      │
│   • β_price 後驗 = 價格彈性 with uncertainty │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Price-sweep revenue optimisation:             │
│   for each candidate price p in grid:         │
│     for each posterior sample (α, β...):      │
│       book_prob = sigmoid(linear combo)       │
│       expected_rev = book_prob × p            │
│     aggregate: mean + 90% credible band       │
│   optimal_price = argmax(mean expected_rev)   │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + random + statistics + dataclasses):
- `NormalPrior`: Gaussian prior log_pdf
- `sigmoid`: numerically-stable logistic
- `logit_predict`: 在 θ 下 P(book) for 單晚
- `log_likelihood / log_prior / log_posterior`: 標準 Bayesian 組合
- `run_mh`: Metropolis-Hastings random-walk, joint proposal, configurable σ_prop / burn-in / thin / seed
- `sweep_prices`: 對 price_grid 各點算 P(book) + EV 後驗均值 + 90% 區間
- `optimal_price`: pick argmax mean EV

**LLM 只負責**: 寫 250-330 字「民宿老闆週工作流 (3 情境定價 SOP + walk-away rule + 颱風 / 鄰居打折風險)」
**LLM 絕不負責**: 計算 NT$ / 後驗 / acceptance rate / β_price (數字 100% 來自 MCMC)

### 為什麼 MCMC 適合這個 use case (vs Logistic Reg r56 / Conformal r41 / GP r60)

- **MCMC**: 給**完整後驗分佈** + **principled uncertainty quantification** + 小樣本下穩健 (60 晚即可訓練)
- **Logistic r56 cramlead**: frequentist 點估 + 信心 CI 用渐近; 不適合直接給「EV 90% 區間」
- **Conformal r41 salaryci**: 給單一對稱 90% CI; 不能給「不同情境 (平日 / 週末 / 連假) 各自最佳價格」
- **GP r60 cropforecast**: 時序回歸不適合「discrete booking 0/1 outcome」, 需要 GP classifier 但實作複雜
- **kNN r54 / Quantile r58**: 不能對「漲一塊 vs 跌一塊 → P(book) 微分」做 principled 統計推論

MCMC 的 unique 優勢:
1. **Principled uncertainty**: β_price 後驗 95% CI 是 calibrated, 非渐近
2. **Composable**: 同一份 posterior samples 可用在多種決策 (最佳定價、收益預測、敏感性分析)
3. **Hierarchical 可擴展**: 多店主未來可加 hierarchical prior, single-store 立刻能跑

## 使用示例

```bash
# 純函式模式 (無 API key)
python3 staypulse.py --data samples/inn.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 staypulse.py --data samples/inn.json

# 自訂 MCMC 參數
python3 staypulse.py --n-iter 10000 --burn-in 2000 --seed 123
```

預期輸出 (詳見 `examples/sample_output.md`):

海風小宿 (花蓮 4 房獨棟) 60 晚資料:

| 情境 | 推薦定價 | 後驗 EV / 晚 | 90% CI |
|---|---|---|---|
| **平日** | NT$ 3,000 | NT$ 1,359 | [949, 1,784] |
| **週末** | NT$ 4,000 | NT$ 2,686 | [1,927, 3,369] |
| **連假** | NT$ 5,400 | NT$ 4,577 | [3,396, 5,203] |

→ MCMC 顯示「連假 + 週末加價效果 (β_weekend +1.19, β_holiday +1.42 都 95% CI 不含 0) 統計顯著」, 但價格彈性 β_price -0.82 95% CI [-2.94, +1.43] 「**還不確定**」, 老闆需要再做 4-8 週「刻意改變定價的 A/B」收集更多資料縮小 CI。

訓練診斷:MCMC acceptance 55% (健康範圍 10-50%, 稍高表示 proposal 略保守); β_weekend / β_holiday 後驗符號跟預期一致。

## 目標市場

- **TAM**: 13,000 民宿 + 2,500 中小旅館 = **15,500 家潛在 B2C 用戶**
- **核心**: 80% 是兼職老闆 (退休族 / 第二事業) 沒系統化定價工具
- **WTP 錨點**:
  - 旺季少賺 NT$ 50K + 淡季空房 NT$ 30K = 年損 NT$ 80K vs Solo NT$ 499/月 (年 NT$6K) = **13x 防虧**
  - 連假定價多賺 NT$2K/晚 × 6 連假 × 3 晚 = NT$36K/年 = **單一檔期回本 5+ 年**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 情境 / 30 晚資料 | 試用 |
| **Solo Inn** | NT$499/月 | 4 情境 + LINE 推播 + 季節重訓 | 個人民宿 |
| **Multi-Inn** | NT$1,499/月 | 多房型 + 多分店 + 競爭者比較 (區域) + Booking / Airbnb API | 中型民宿 5-30 房 |
| **Chain** | NT$4,999/月 | 連鎖 30+ 房 + 跨區 benchmark + RM dashboard | 連鎖民宿集團 |
| **Enterprise** | NT$15,000+/月 | 加 hierarchical 多店 prior + 真實 OTA scrape + 客製 | 觀光集團 / OTA |
| **API** | NT$3/call | 第三方 ERP (旅安 / 速立達) 整合 | 民宿 SaaS |

## Distribution

- **PTT TaiwanTour / Travel** 板長尾 SEO
- **Dcard 旅遊 / 行政院觀光** 板
- **FB「台灣民宿主交流會 / 花蓮民宿主 / 宜蘭民宿主 / 金門民宿主」** 3-5 萬人社群 案例分享
- **民宿協會 partner** (台灣民宿協會 / 各縣市民宿協會)
- **觀光局 / 各縣市政府觀光處** partner (PR + 中小民宿輔導補助)
- **YouTube 旅遊 KOL** (蕾娜女王 / 老虎武 / Mr. Tu)
- **YouTube 民宿經營 KOL** (民宿經營者 / 副業老闆)
- **民宿 ERP integration partner** (旅安 / 速立達 / 易遊網)
- **連鎖民宿 B2B BD** (薆悅酒店集團 / 趣淘漫旅 / 福容大飯店 中小型)
- **觀光博覽會 / 台北國際旅展** (每年 10-11 月南港) booth

## TAM

- 1% × 15,500 = 155 × Solo NT$499 = 月 NT$8 萬
- + Multi-Inn 50 × NT$1,499 = NT$8 萬/月
- + Chain 10 × NT$4,999 = NT$5 萬/月
- + Enterprise 5 × NT$15K = NT$8 萬/月
- 總計 **月 MRR NT$29 萬 / 年 ARR NT$350 萬** (保守)
- 加 0.5% pen + Multi-Inn 比例提升 + API enterprise (10 × NT$50K) → **NT$1,500-3,000 萬 ARR**
- 加滲透 + 橫移日本民宿 / 韓國 Pension / 東南亞 boutique inn → **NT$1-2 億 ARR**

## 風險與限制

- **60 晚 prototype 樣本小** — real launch 需 ≥ 180 晚 (1 年) 才能 capture 完整四季 + 連假, 鼓勵民宿主上傳歷史換取免費 Multi-Inn 月
- **Logit 線性假設**: P(book) 對 log(price) 線性, 真實有非線性 (整數定價心理錨點 / 競品 reference price) + 交互作用, Pro 版加 spline / GP
- **獨立觀察假設**: 假設每晚獨立, 真實連假頭尾相關 + 上週同人有可能回購, Pro 版加 group-level random effects
- **No competitor signal**: 鄰近民宿同期定價也影響訂房, 此 prototype 未捕捉, Pro 版加 hierarchical 區域 prior + scrape Booking / Airbnb 同類房型
- **MCMC convergence**: 接受率應在 20-50% 區間, 過低 / 過高表示 proposal_sigma 該調; Pro 版自動 adaptive MH + 多 chain + Gelman-Rubin 診斷
- **不捕捉重大事件**: 颱風 / 連假取消 / 跨年 / KOL 推薦炸鍋, Pro 版加 explicit dummy + event detector
- **競爭者壓力**: 純 MCMC 給 *單店* 最佳化, 多店搶客 game-theoretic 均衡需 RL / Nash 模型
- **隱性人為干預**: 老闆心情 / 朋友打折 / 平台促銷 噪音未建模, Pro 版加 reviewer-effect / event flag
- **平台合約限制**: Airbnb / Booking 有些國家有「rate parity」條款限制價格不能比直銷低, 不同市場合規需檢
- **不取代實地直覺**: 工具給統計區間, 實際定價仍需 結合當週 / 鄰居 / 天氣 / 颱風 / 連假 / KOL 流量 multi-signal

---
*staypulse = Metropolis & Hastings 1953/1970 MCMC × Bayesian logistic demand × 台灣民宿 / B&B 房價 niche = 從 60+ 晚歷史 sample 後驗 (alpha, beta_price, beta_weekend, beta_holiday), 拆出「平日 / 週末 / 連假」最佳定價 + EV 90% 區間, 民宿老闆從「憑感覺」變「Bayesian decision」。*
