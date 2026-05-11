# petfeed -- 台灣寵物飼料 Hierarchical Bayesian shrinkage 推薦

**「PChome 寵物版上 ZiwiPeak 巔峰 5.0 滿分但只有 2 個飼主評 vs 皇家 4.6 但有 80 個飼主評, 我家貴賓敏感腸胃該換哪個?」** 用 Empirical-Bayes Hierarchical Linear Model (James 1961 / Efron-Morris 1973) 把每個 (品種, 品牌) cell 的 raw 評分 **shrink** 向 μ_global, n 小的「驚豔評分」自動被拉回現實 -- 推薦的 Top 飼料不再被 sample bias 帶偏。

## 痛點

台灣寵物市場:
- **登記犬數**: ~233 萬隻 (農業部 2024)
- **登記貓數**: ~91 萬隻
- **每月飼料支出**: 中型犬 NT$1,500-3,000, 小型犬 NT$800-1,800, 貓 NT$1,000-2,500
- **飼料總市場**: ~ NT$120 億/年
- **飼主換糧頻率**: 平均 1-2 年換一次 (出腸胃 / 換階段 / 換廠商)

**飼主痛點** (FB「我愛貴賓狗 / 柴犬 / 黃金獵犬」社群 5-30 萬人 / Dcard pet / PTT dog_cat / Mobile01 寵物板):
- 「PChome 寵物版 5 顆星看起來都一樣, 但有的 80 人評有的只有 2 人評, 不知道誰可信」
- 「上次換飼料 7 天我家貴賓拉肚子 5 天, 浪費 NT$1,500 飼料 + 獸醫 NT$3,000」(每週重複)
- 「FB 社團問哪個飼料好, 同一品牌有人說超讚有人說害狗腎臟出問題, 信誰?」
- 「換錯飼料 = 整袋 (NT$1,500-3,500) 浪費 + 看獸醫 (NT$2,000-5,000)」

**現有資源**:
- 寵物店店員 (主觀 + 受品牌 commission 影響)
- 獸醫處方飼料 (限治療性, 普通保健不會主動推)
- FB 社團問 (sample bias 嚴重)
- PChome / 露天 / momo / 蝦皮 寵物版 (raw star rating 不做 shrinkage)

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(petfeed 補的) |
|---|---|---|
| PChome / 蝦皮 / momo 寵物版 | 顯示 raw 平均星級 + 評論數 | 不做 shrinkage, n=2 的 5.0 排前面 |
| Chewy / Amazon (海外) | Verified review + 篩選 | 不認識台灣品牌組合 / 在地評分習慣 |
| Whistle / Petable (海外) | 寵物穿戴 + 健康追蹤 | 不做飼料統計推薦 |
| 寵物醫院 處方飼料 | 治療性飼料 | 普通保健需求不會主動推, 收費 |
| FB 社群 / Dcard / PTT | 主觀分享 | sample bias 嚴重, 沒做統計校正 |
| ChatGPT 一次問 | 一次性建議 | 不能學歷史 review, 不做 HB shrinkage |
| Excel 自己記 | 純手動 | 沒模型, 100+ 件記憶有限 |

**Gap 結構性**: Empirical-Bayes Hierarchical Bayes (James 1961 / Stein paradox / Efron-Morris 1973) 在學術 / 棒球打擊率 / 教育評鑑 / 流行病學廣泛應用 60+ 年, **沒人做成台灣寵物飼料 review 平台**。Google「寵物飼料 hierarchical Bayesian 評分 中文」零本土 SaaS。電商平台 raw star rating 是業界 default, 全球都被 sample-bias 困擾, petfeed 為這個老問題提供具體可用的解法。

## 架構 -- Empirical-Bayes Hierarchical Linear Model (47th 條 AI pattern)

```
歷史 reviews (breed, brand, rating, age, weight, 敏感腸胃, 無穀, months_fed)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 2-level model:                                │
│   y_{c,i}  ~ Normal(mu_c, sigma_within^2)    │
│   mu_c     ~ Normal(mu_global, tau_between^2)│
│                                                │
│ c = (breed, brand) cell                       │
│ y_{c,i} = i-th review in cell c               │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Empirical-Bayes parameter estimation:         │
│   sigma^2  = pooled within-cell variance      │
│             (cells with n>=2, Bessel-corrected)│
│   mu_global = unweighted avg of cell means    │
│   tau^2    = method-of-moments                │
│              max(0, var(cell_means)           │
│                       - sigma^2 / n_avg)     │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Per-cell posterior:                           │
│   w_c        = n_c * tau^2                    │
│              / (n_c * tau^2 + sigma^2)       │
│   mu_c_hat   = w_c * y_bar_c                  │
│              + (1 - w_c) * mu_global         │
│   var_c_hat  = sigma^2 * tau^2                │
│              / (n_c * tau^2 + sigma^2)       │
│   95% CI     = mu_c_hat ± 1.96 * sqrt(var_c)  │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Recommend for query (breed=貴賓):              │
│   filter cells with breed == query.breed      │
│   sort by mu_c_hat descending                 │
│   tie-break by n_samples                      │
│   return Top-k with raw_mean + shrunk_mean    │
│           + Δ + shrinkage_weight + CI         │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + statistics + dataclasses + collections):
- `fit_hb`: 完整 empirical-Bayes 推估 (3 步驟: pooled sigma, mu_global, tau via MOM)
- `recommend_for_query`: 過濾品種 + 依 shrunk_mean 排序
- `naive_vs_shrunk_table`: side-by-side 對照 raw 與 shrunk -- 揭示哪些 cell 被模型「修正」
- `most_corrected_cells`: 找 |Δ| 最大的 cells (通常是 n 小 + 評分極端)
- `model_summary`: μ_global / σ_within / τ_between / ICC

**LLM 只負責**: 寫 250-330 字「飼主換糧 SOP + 寵物店 SKU 採購邏輯 + 風險提醒」
**LLM 絕不負責**: 計算 shrunk_mean / shrinkage_weight / CI / Δ (數字 100% 來自 HB)

### James-Stein 在這裡為什麼有用

電商 raw star rating 有個老問題: **n=2 的 5.0 排在 n=80 的 4.6 前面**。直觀上不合理, 但平均值不分 n 大小。HB 給出原則性解法:

- n 越大, 模型越信任原始均值 (w → 1) -- 多人說好 = 真的好
- n 越小, 後驗自動拉回 μ_global -- 「我們對這個 cell 知道太少, 不能輕信 outlier 評分」

這就是 **Stein paradox 的實用版**: 用「鄰居 cell」的資訊 (μ_global) 來改進每個 cell 個別估計, 全 cell 的 mean squared error 一定下降。對寵物飼料而言, 「同品種其他品牌的均值」就是這個 prior, 沒見過的新品牌不會憑 1 個飼主的 5.0 就霸榜。

## 使用示例

```bash
# 純函式模式 (無 API key)
python petfeed.py --data samples/pet_reviews.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python petfeed.py --data samples/pet_reviews.json

# 改 Top-k
python petfeed.py --top-k 5
```

預期輸出 (詳見 `examples/sample_output.md`):

陳太太家貴賓 6 歲 4.5 kg 腸胃敏感:

| 品牌 | 後驗均值 | 95% CI | n | shrinkage | raw_mean |
|---|---|---|---|---|---|
| ⭐ **Royal Canin 皇家** | 4.66 | [4.54, 4.77] | 8 | 99% | 4.66 |
| ZiwiPeak 巔峰 | 4.92 | [4.70, 5.14] | 2 | 96% | 4.95 |
| Orijen 渴望 | 4.59 | [4.43, 4.75] | 4 | 98% | 4.60 |

→ ZiwiPeak n=2 後驗排序仍最高但 CI 較寬, 寵物店店長可看 CI 寬度判斷「進貨主推」 vs 「試點小包」。皇家 n=8 後驗 4.66 + CI 窄是穩穩的主推。資料庫累積 200+ reviews 後, n 小的暴衝評分會自然被拉回現實。

## 目標市場

- **TAM**:
  - 寵物店連鎖 (Pets at Home Taipei / 寵物公園 / 全國連鎖 / 巴克貓狗 / 神腦寵物) ~ 5,000 家門市
  - 寵物電商 (PChome / 蝦皮 / momo / 露天 寵物版) 10+ 家平台
  - 飼料品牌 (皇家 / 希爾思 / Orijen / ZiwiPeak / 寶路 / 冠能 / 渴望 / 福爾摩沙 / 福壽 / 統一) 30+ 家
  - 寵物醫院連鎖 (中興 / 茂楷 / 太僕 / 仁愛動物醫院 / 哈寶) 300+ 家
- **C2C TAM**: 233 萬犬主 + 91 萬貓主 = ~ 250 萬潛在 freemium 用戶
- **WTP 錨點**:
  - 換錯飼料一次 = 飼料浪費 NT$1,500 + 獸醫 NT$3,000 = NT$4,500
  - Solo NT$99/月 ≈ 1 個月省下 30 元 = 全年回本 30+ 倍
  - 寵物店主月省 SKU 試錯費 NT$5-30K = 月費 50-300 倍 ROI

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 次推薦/月 | 飼主試用 |
| **Solo** | NT$99/月 | 無限推薦 + 換糧 SOP + 過敏警示 + LINE Bot | 個別飼主 |
| **Pro** | NT$299/月 | + 多寵物 + 健康追蹤 + 自訂 brand pool | 多寵家庭 |
| **Store** | NT$1,499/月 | 寵物店 SKU 採購邏輯 + 進貨建議 + B2B 客戶 ID 庫 | 中小寵物店 |
| **Chain** | NT$4,999/月 | 連鎖 / 多門市 + API + 客製 cell 切片 + dashboard | 連鎖品牌 |
| **Brand** | NT$15,000+/月 | 飼料品牌 review intelligence + 競品比較 + 推薦對沖策略 | 飼料品牌方 |
| **API** | NT$2/call | 第三方平台 (PChome / 蝦皮) 整合 | 電商平台 |

## Distribution

- **FB「我愛貴賓狗 / 柴犬 / 黃金獵犬 / 米克斯 / 米克斯領養」** 5-30 萬人社群分享案例
- **Dcard pet / 寵物 / 動物溝通 / 領養** 板長尾 SEO
- **PTT dog_cat / dog / cat / pet** 板
- **Mobile01 寵物板** (年長飼主社群)
- **YouTube 寵物 KOL** (黃金毛 / 大胃王皮卡丘 / 阿明喵 / 小光 + 小美 / 邊牧維維) 業配
- **PChome / 蝦皮 / momo 寵物版** 整合 (Brand 方案合作)
- **寵物店 B2B BD** (Pets at Home Taipei / 寵物公園 / 神腦寵物連鎖)
- **獸醫師公會 / 寵物用品工會** 合作 (飼料健康宣導)
- **寵物展 / 台北寵物用品大展** (每年 8 月台北南港) booth

## TAM

- 0.5% C2C × 250 萬犬貓主 = 12,500 × Solo NT$99 = **月 NT$124 萬 MRR**
- + Pro 2,000 × NT$299 = NT$60 萬/月 (多寵家庭佔比約 20%)
- + Store 200 × NT$1,499 = NT$30 萬/月 (5,000 寵物店中 4%)
- + Chain 30 × NT$4,999 = NT$15 萬/月
- + Brand 10 × NT$15,000 = NT$15 萬/月 (30 家品牌中 1/3)
- + API enterprise 5 × NT$30K = NT$15 萬/月
- 總計 **月 MRR NT$259 萬 / 年 ARR NT$3,100 萬**
- 加滲透 + 橫移港新馬 / 日韓寵物市場 (日本登記犬數 700 萬隻 + 韓國 500 萬隻) → **NT$8,000 萬-1.2 億 ARR**

## 風險與限制

- **51 件 prototype 太小** -- 真實 launch 需 ≥ 1,000 件多品牌 / 多品種, 鼓勵飼主 contribute review 換取免費 Pro 月
- **常態假設**: rating 1-5 是 ordinal 不是 continuous Normal, Pro 版用 ordinal probit (probit-link) 更精確
- **僅 2-level shrinkage**: (cell ← global), 實務上 (品種 ← 品種屬科 ← 全國) 三層更穩;Pro 版加品種分群 (大型犬 / 小型犬 / 短鼻犬 / 長毛貓 / 短毛貓)
- **方差用 method-of-moments**: 不一定 MLE 最優;大樣本 OK, n_cells < 20 時改用 REML
- **未考慮飼主主觀偏差**: 同一隻狗不同主人打分差 0.5-1.0 顆星, Pro 版加 reviewer-effect random intercept (multilevel)
- **冷啟動弱**: 新品種 / 新品牌 0 review 時退回 μ_global, 仍鼓勵實地試吃 + 寵物醫師意見
- **不取代獸醫專業**: 嚴重腸胃 / 過敏 / 慢性病請先諮詢獸醫, 飼料只是輔助, **腎臟病 / 胰臟炎 / IBD 必須走處方飼料路線**
- **Brand 方案的利益衝突**: 飼料品牌付費就拿到競品 review 數據, 雲端版需嚴格匿名化 + 客戶 opt-in + 不修改公開 review

---
*petfeed = Empirical-Bayes Hierarchical Linear Model (James 1961 / Efron-Morris 1973) × 台灣寵物飼料 niche = 把零碎 (品種, 品牌) 評分 shrink 成穩健後驗推薦, n=2 的 5.0 不會打敗 n=80 的 4.6, 飼主一次選到 sample-bias 小的飼料, 寵物店 SKU 採購不靠 commission 決定。*
