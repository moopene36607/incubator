# viewdrop — 台灣自媒體創作者流量斷點 BOCPD 偵測工具

**「我頻道流量是哪一天斷的?演算法改了還是內容老化?」** 用 Bayesian Online Changepoint Detection (Adams & MacKay 2007) **精準到天** 找出 YouTube / Threads / IG / TikTok / Podcast 每日 metric 的 changepoint,給創作者**具體日期 + 變化幅度 + 推測原因 + 診斷下一步**。

## 痛點

台灣自媒體生態:
- **YouTuber**: 1 萬訂閱+ ~80,000 創作者,5-50 萬中型 ~5,000 人 (核心 WTP 族群)
- **Threads / Instagram Creator**: 5,000 粉絲+ ~150,000+
- **Podcaster**: 活躍中文 podcast ~3,000 個
- **TikTok 中型創作者**: ~30,000

**每天看 YouTube Studio Analytics 焦慮**:
- 「我這週流量怎麼掉了 30%」(Day 1)
- 「上週可能只是波動」(Day 3)
- 「真的掉了…從哪天開始的?」(Day 7)
- 「演算法改了嗎? 還是我影片不夠好?」(Day 14, 已經 2 週了)

實際情境 (Threads / Dcard 創作者版 / FB「台灣 YouTuber 互助」社群 8000+ 人):
- 「我頻道 4 月開始流量直直下,但 Studio 曲線看不出來確切哪天」每週重複問
- 「同行說 YT 在 4 月初有一波演算法更新,但我也不確定是不是我的問題」
- 「我每天看 dashboard 看到憂鬱,看不出哪天是 turning point」

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(viewdrop 補的) |
|---|---|---|
| YouTube Studio Analytics | 給 KPI + 時間曲線 | 不做 changepoint detection, 不告訴你「哪一天斷的」 |
| SocialBlade / VidIQ | 公開頻道追蹤 | 沒 BOCPD, 只看曲線靠目視判斷 |
| TubeBuddy | SEO / A/B test | 不分析創作者自己的流量斷點 |
| Buffer / Hootsuite | publishing scheduling | 完全不做 analytics changepoint |
| Google Analytics | 網站流量 | 用在創作者 dashboard 太重 + 同樣沒 changepoint |
| ChatGPT 直接問 | 一次性建議 | 沒記住歷史 metric, 沒持續分析 |

**Gap 結構性**: BOCPD (Adams & MacKay 2007) 學術界成熟 18 年,**沒人做成台灣中文創作者可用 SaaS**。Google「自媒體 changepoint detection」零中文 SaaS 結果。

## 架構 — Bayesian Online Changepoint Detection (33rd 條 AI pattern)

```
Daily metric (views / subs / engagement)
         │
         ▼
┌──────────────────────────────────────────────┐
│ For each timestep t:                          │
│   For each run length hypothesis r:           │
│     π_t^{(r)} = P(x_t | recent r obs)         │
│                = Gaussian(emp mean of x_{t-r:t})│
│   Growth:    P(r_t=r+1) ∝ P(r_{t-1}=r) ·     │
│                          π · (1-H)            │
│   Changept: P(r_t=0) = Σ P(r_{t-1}=r) ·       │
│                       π · H  (H = 1/λ)        │
│   Normalize posterior P(r_t | x_{1:t})        │
└──────────────────────────────────────────────┘
         │
         ▼
MAP run-length per timestep
         │
         ▼
Detect changepoints: r drops to small after growing
         │
         ▼
Segment summaries (before/after means)
         │
         ▼
Most-likely changepoint = biggest mean shift
```

**100% 純函式 stdlib** (math + statistics + dataclass):
- `_gaussian_pdf`: standard Gaussian density
- `predictive_prob`: P(x_t | recent r obs) with empirical mean
- `run_bocpd`: full recursive BOCPD with run-length posterior truncation (max 200 to bound memory)
- `estimate_obs_sigma`: rolling-window stdev for noise estimation
- MAP run-length trajectory + segment summaries + most-likely changepoint

**LLM 只負責**: 200-280 字「給創作者讀的解讀 + 3 個推測原因 + 3 個診斷動作 + 風險」
**LLM 絕不負責**: 計算 posterior / 找 changepoint / 算 confidence (數字 100% 來自 BOCPD)

## 使用示例

```bash
# 純函式模式 (無 API key)
python viewdrop.py --creator samples/youtuber.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python viewdrop.py --creator samples/youtuber.json

# 不同 metric
python viewdrop.py --metric subscriptions
python viewdrop.py --metric ctr

# 調整 hazard λ (預期段長,越小越敏感)
python viewdrop.py --hazard-lambda 10
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (阿翔生活實驗 54K 訂閱中型 YouTuber, 60 天 daily views):

| 指標 | 值 | 解讀 |
|---|---|---|
| 偵測到的斷點數 | 1 | 顯著的單一 changepoint |
| 斷點日期 | **2026-04-01** | 精確到天 |
| Before mean | 12,264 views/day | 段 1 (3 月) |
| After mean | 7,890 views/day | 段 2 (4 月) |
| 變化 | **-35.7%** | 顯著下滑 |
| Confidence | **0.99** | 強信心 |

## 目標市場

- **TAM**:
  - YouTuber 1 萬訂閱+ ~80,000 → 中型 5-50 萬 ~5,000 核心
  - Threads / IG / TikTok / Podcast 中文中型 ~30,000+
  - 估計 **40,000+ 中文中型自媒體創作者**
- **WTP 錨點**:
  - 創作者一天少賺 NT$200-2000 (Adsense + 業配, 中型) → 1 個月流量斷沒發現 = NT$6K-60K 損失
  - 顧問 / mentor 一次 NT$3-10K vs viewdrop Solo NT$199/月 = **15-50x 便宜**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 metric × 30 天/月 | 試用 |
| **Solo** | NT$199/月 | 無限 metric + 多平台 + LINE 推播 | 個人創作者 |
| **Pro** | NT$499/月 | + 多變數 BOCPD + 競品對標 + 每日自動掃描 | 中大型創作者 |
| **MCN** | NT$2,999/月 | 多頻道(10-50)+ 經紀人 dashboard + API | 中小 MCN / 經紀公司 |
| **Brand** | NT$15,000+/月 | 業配 KOL 流量盡職調查 + 異常偵測 + API | 品牌 / 廣告代理商 |

## Distribution

- **Threads / Dcard 創作者版 / FB「台灣 YouTuber 互助」5-10K 人社群** SEO + 案例分享
- **YouTube 創作者 KOL** (重點影片 / 啟點文教 / 啾啾鞋 / 啊滴英語 等) 案例合作
- **YouTube Made For Creators** / **VidCon Taiwan** 等活動 booth
- **MCN / 經紀公司** B2B BD (CapCut Studio / 集英社 / 凱爾達 / 圓夢) 給經紀人用
- **業配品牌方** B2B — 業配 KOL 前的流量真實性盡職調查 (對抗刷量)
- **數位行銷 / KOL 行銷代理商** B2B partner
- **TaiwanCreator Conference** 等創作者社群 partner

## TAM

- 1% × 40,000 中型創作者 = 400 × NT$199 = **月 NT$8 萬**
- + Pro 100 大型 × NT$499 = NT$5 萬/月
- + MCN 30 家 × NT$2,999 = NT$9 萬/月
- + Brand 20 家 × NT$15,000 = NT$30 萬/月
- 總計 **月 MRR NT$52 萬 / 年 ARR NT$620 萬**
- 加滲透率提升 + 橫移港新馬 / 日韓中文創作者 + 中英文化 → 翻倍至 **年 NT$1,500-3,000 萬 ARR**

## 風險與限制

- **Gaussian likelihood 假設違反** — 病毒影片爆紅是 heavy-tail outlier,可能誤判為 changepoint;Pro 版用 Student-t likelihood + outlier robust BOCPD
- **季節性 / 週末效應** — 創作者週末流量本來就高 30-50%,單變數 BOCPD 沒處理;Pro 版加 weekly seasonal detrending
- **單變數模型** — 一個 metric 看不全;Pro 版多變數 BOCPD (views + subs + CTR + watch_time 同時看)
- **不告訴你「為什麼」** — BOCPD 只說 when,not why;LLM 給可能原因清單但要創作者自己 trace back
- **hazard λ 是主觀先驗** — 預設 30 (預期每月 1 個斷點);錯估會 over/under detect

---
*viewdrop = Adams & MacKay 2007 BOCPD × 台灣中文自媒體 niche = 從感覺『流量好像怪怪』升級到「精準到天的 changepoint + 推測原因 trace」。*
