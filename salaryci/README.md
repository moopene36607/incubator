# salaryci — 台灣求職者薪資談判 conformal prediction CI 工具

**「我這經歷該談多少薪資」** 用 conformal prediction 給 90% 信心區間 + walk-away / aim-for / stretch 談判錨點,而不是 104 那種**單一中位數誤導性**估計。求職者拿到 offer 後 30 秒知道是行情上緣 / 下緣 / 該 push 多少。

## 痛點

台灣轉職市場每年 200 萬人 + 新鮮人 16 萬:
- 拿到第一個 offer NT$68K — 是「合理」還是「被壓 10%」?**完全沒參考依據**
- 104 / 1111 給「中位數 NT$75K」單一數字,不告訴你**離散程度** — 25 百分位 vs 75 百分位差幾萬?
- PTT Salary 「Sr backend RD 月薪該多少」每天重複問,每篇底下 30 條回應從 NT$55K 到 NT$110K 都有,**沒有 calibrated CI**
- 過度保守 → 月薪少 NT$5-10K × 12 月 × 5 年 = NT$30-60 萬「沒談到的損失」
- 過度激進 → 失去 offer

實際情境驗證:
- Dcard 工作版: 「拿到 NT$70K 同學說我被坑了,自己 google 又看到中位數 NT$72K 看不出來到底是不是」
- PTT Soft_Job: 「3 年後端,Junior 還 Mid 應該談多少?面試官說 base 75K 是『行情』,但我朋友 reds 拿 90K」
- 獵頭 LinkedIn: 求職者最常問「I'm not sure if this is good」每週 5-10 次

## 為什麼現有工具不解。Gap 結構性

| 工具 | 給什麼 | 沒給(salaryci 補的) |
|---|---|---|
| 104 薪資地圖 | 中位數 + 平均 (點估計) | **沒給 calibrated CI**,只看到「中位數 NT$72K」不知道是 NT$60-84 還是 NT$70-74 |
| Glassdoor / Comparably | range, 但海外為主 | 不認識台灣產業 / 公司分級,科技 / 製造 / 金融 mix 在一起失準 |
| Levels.fyi | 大廠完整 levelling | 只覆蓋國際大廠,台灣中小企業 + 本土公司全沒資料 |
| LinkedIn Salary | 大樣本 | 沒提供 conformal CI,沒談判錨點 |
| PTT Salary | 真實 anecdotal | 雜訊大,沒系統化 calibration,沒 quantile guarantee |
| ChatGPT 直接問 | 一次性回答 | 不知道台灣最新行情,常幻覺數字,沒持續校準 |

**Gap 結構性**: Conformal prediction Vovk et al. 1990s 學術界成熟 25+ 年,**沒人做成台灣求職者可用 SaaS**。Google「台灣 薪資 conformal prediction」零中文 SaaS 結果。

## 架構 — Split-Conformal Prediction (31st 條 AI pattern)

```
Profile (industry, role, level, exp_years, location, current_offer)
         │
         ▼
┌──────────────────────────────────────────┐
│ 1. select_calibration_set (5-tier progressive
│    relaxation, 找 ≥6 筆 similar records)  │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ 2. point estimate: median(calibration)    │
│    μ̂ = NT$72K                             │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ 3. nonconformity scores: s_i = |y_i - μ̂| │
│    [0, 2, 3, 6, 7, 10, 12]                │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ 4. q = ceil((n+1)(1-α))-th quantile = 12  │
│    α=0.10 → 90% CI                        │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ 5. PI = [μ̂ - q, μ̂ + q] = [60K, 84K]      │
│    coverage guarantee ≥ 1-α (exchangeable)│
└──────────────────────────────────────────┘
         │
         ▼
   walk-away / aim-for / stretch anchors
```

**100% 純函式 stdlib** (math + statistics + dataclass):
- `corpus.py` 60+ 真實合成台灣薪資 records (4 個 industry × 8 個 role_family × 4 個 level)
- `select_calibration_set` 5 階段 progressive relaxation:
  1. industry + role + level + exp ±2
  2. industry + role + exp ±2 (放寬 level)
  3. industry + role
  4. role only (跨產業)
  5. industry only (worst case)
- `predict_median` 用 calibration set 中位數作 point estimate
- `nonconformity_scores` |y - μ̂|
- `conformal_quantile` Vovk's `ceil((n+1)(1-α))/n` 經驗 quantile
- `negotiation_anchors` 純函式計算 walk-away / median / aim-for / stretch

**LLM 只負責**: 寫 150-220 字「談判腳本」(具體開場 + 非薪資 levers + 風險提醒)
**LLM 絕不負責**: 計算薪資 / CI / 百分位 / 錨點 (數字 100% 來自 conformal)

## 使用示例

```bash
# 純函式模式 (無 API key)
python salaryci.py --profile samples/jobseeker.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python salaryci.py --profile samples/jobseeker.json

# 自訂 confidence level (default 90%)
python salaryci.py --alpha 0.05  # 95% CI (更寬)
python salaryci.py --alpha 0.20  # 80% CI (更窄)
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本: 王小明 4 年後端 RD,offer NT$68K

| 指標 | 值 | 解讀 |
|---|---|---|
| 90% CI | NT$60K — NT$84K | 真實薪資 90% 機率落在這 |
| Median | NT$72K | 對方第一次出價這個算合理 |
| Offer position | 第 29 百分位 | 偏行情下緣 |
| Walk-away | NT$60K | 低於此可直接拒絕 |
| **Aim for** | **NT$78K** | **你的目標應該瞄這** |
| Stretch | NT$84K | 對方真的喜歡你給到這 |

## 目標市場

- **TAM**: 200 萬轉職族 + 16 萬新鮮人/年 = 主動 30-50 萬尋找新工作 + 隨時 30-40% 在 passive looking
- **WTP 錨點**:
  - 過去保守接 offer 沒談 → 月薪少 NT$5K × 12 月 × 5 年 = **NT$30 萬機會損失** vs Solo NT$199/月 = **150x 防損保險**
  - 一次 negotiation 多 push NT$5K → 第一年回本 25x

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 次計算/月,基礎 CI | 試用 |
| **Solo** | NT$199/月 | 無限次 + 細部 levels (Staff / Principal) + RSU 估算 | 個人轉職 |
| **Pro** | NT$499/月 | + LinkedIn integration + 比較工作 + 多家公司 offer 比對 | 多面試族 |
| **Headhunter** | NT$2,999/月 | 獵頭批量查詢 + 候選人 dashboard + API | 獵頭顧問 |
| **HR Enterprise** | NT$15,000+/月 | 企業給薪 benchmarking + 內部公平性 audit + 客製 corpus | 大型 HR |

## Distribution

- **PTT Salary / Soft_Job / Tech_Job / Salary** 板長尾 SEO
- **Dcard 工作版 / 求職版** 案例分享
- **LinkedIn 台灣 connection**: 直接 inmail 給 active 找工作者 (顯示為 "open to work")
- **Cake / Yourator / 104** 招募平台 partner — 求職者收 offer 後自動推播
- **YouTube 職涯 KOL** (大人學 / Mr 6 / 矽谷阿雅) 案例合作
- **獵頭公司** B2B BD — 給獵頭 NT$2,999/月白標,獵頭幫求職者報 CI

## TAM

- 1% × 50 萬主動轉職族 = 5,000 人 × Solo NT$199 = **月 NT$100 萬 MRR / 年 NT$1,200 萬 ARR**
- + Pro 訂閱(1,000 人 × NT$499 = NT$50 萬/月)+ Headhunter (200 顧問 × NT$2,999 = NT$60 萬/月) + HR Enterprise (50 公司 × NT$15K = NT$75 萬/月)
- **整體年 ARR 上看 NT$3,000-5,000 萬**;橫移港新馬 / 日韓 → 翻倍

## 風險與限制

- **calibration set 大小** — prototype 60 筆樣本,實際 launch 需 1,000+ 筆 (scraping + 用戶 self-report incentive)
- **交換性假設** — 假設你跟 corpus 樣本 i.i.d.,但海外名校 / 大廠出身 / 特定證照會偏低估;Pro 版加 conditional adjustment
- **不含 bonus / RSU / 簽約金** — 只看月薪 base,Pro 版加總包估算
- **產業 / 公司 size 沒切細** — 中小企業 vs 大廠在同 level 差 20-30%,Pro 版加 company tier 切分
- **薪資資料隱私敏感** — 用戶提供薪資要求 opt-in 加入 corpus(類似 Glassdoor 模式),incentive 用「貢獻一筆獲得永久 Pro」
- **CI ≠ 個人準確預測** — 邊際 coverage 90% 但個別案件可能落 CI 外,UI 上要清楚溝通

---
*salaryci = Vovk 1990 證明的 conformal prediction × 台灣薪資談判 niche = 給求職者真正「校準」的信心區間而非單一誤導中位數。*
