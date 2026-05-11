# quotelab(報價實驗室)

**台灣 SOHO / 自由工作者報價策略 Multi-armed Bandit 最佳化 — 每個 case_type 是一個 bandit,Thompson Sampling 從接案歷史學最佳 tier。**

把「**接案不知道報多少**」變成「**LOGO 中型品牌 rebranding → 推薦 HIGH 報 NT$12,000,期望收益 NT$6,000,信心 51%**」。

---

## 痛點

台灣 freelancer 約 80 萬 + 接案族 200 萬,每接新 case **不知道報多少**:
- 報太低 → 虧錢 / 客戶覺得不專業
- 報太高 → 客戶拒絕 / 流失機會
- 每月 5-15 case,**長期下來「報價策略」差 10-30% 直接決定收入**

Upwork / Fiverr 海外不認識台灣產業;PTT SOHO「**接案不知道怎麼報**」每週重複;**沒人做針對台灣 freelancer 的報價最佳化 SaaS**。

## 架構

**Multi-armed Bandit / Thompson Sampling** — `bandit.py` 100% 純函式 stdlib(random + math + statistics + dataclass):

- 每個 `(case_type, tier)` 組合是一個 arm
- 觀察:歷次該 tier 是否成交(accepted/rejected)
- 信念:**Beta(1 + n_accepted, 1 + n_rejected)** 接受機率 posterior
- 預期報酬:`tier 價格 × posterior 接受機率`
- 決策:**Thompson Sampling 1000 次**,選最常勝出的 tier

LLM 不算 EV / 機率,只寫:
- 為什麼這 tier 是好選擇
- 報價策略(開場 / 報價單內容 / 議價底線 / walk-away 價)
- 非價格 levers(mockup / portfolio / 急迫感)
- Exploration 建議(樣本不足的 tier 該不該主動試)
- 長期策略(哪個 case_type 最賺)

## 動作

```bash
# 純函式 bandit(免 API key)
python3 quotelab.py samples/quote_history.json --no-ai --out output.md

# 完整 AI 報價顧問
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 quotelab.py samples/quote_history.json --out output.md
```

## Smoke test (10 cases passed)

- Beta posterior(0/0 uniform、10/0、0/10 邊界)
- Sample 15 LOGO_DESIGN history → 4 arms 正確
- Thompson sampling deterministic(same seed)
- Portfolio summary(28 quotes / 19 成交 / NT$442K 實收)
- LOW accept_rate 67% > PREMIUM 25%(高 reject 率正確)
- 95% CI lower ≤ mean ≤ upper
- Empty history → 推 PREMIUM(高 EV 主導)
- 新 case_type → all arms Beta(1,1) mean=0.5

## Sample(陳設計師 28 quotes 歷史)

- 整體成交率 **67.9%** / 實收 **NT$442K**
- 最賺領域:**WEB_DESIGN NT$385K**(LOGO_DESIGN 才 NT$57K = 1/6.7)
- 新 case「中型服飾品牌 rebranding」(LOGO_DESIGN):
  - Bandit 推薦 **HIGH @ NT$12,000**(EV NT$6,000,信心 50.8%)
  - 比較:LOW EV NT$2K / MID EV NT$4.3K / **HIGH EV NT$6K ⭐** / PREMIUM EV NT$5K(只 2 reject 樣本)
- 議價底線 NT$10,000(空間 16%),walk-away NT$8,000
- 長期策略:**WEB 是金母牛**,60-70% 時間應投在 WEB_DESIGN

## 商業模式

| 方案 | 月費 | 對象 |
|---|---|---|
| **Free** | 月 5 case 推薦 | 試用 |
| **Solo** | **NT$199 / 月** | 個人 freelancer 無限推薦 |
| **Pro** | NT$499 / 月 | 加 portfolio dashboard + 議價腳本 + 趨勢分析 |
| **Studio** | NT$1,499 / 月 | 3-5 人小型接案 team |
| **B2B 接案平台** | 客製 NT$30K+ / 月 | 104 外包 / Tasker / Tasker Wanted white-label |

**WTP**:freelancer 月接 8 case,每 case 報價提升 5-10% = 月多賺 NT$3-8K vs Solo NT$199 = **15-40x ROI**。

**TAM**:80 萬 freelancer × 1% 滲透 × NT$199 = **月 NT$160 萬 MRR / 年 NT$1,900 萬 ARR**;加 Pro + B2B 平台 → 年 ARR NT$3,000-5,000 萬。

## Distribution

1. PTT SOHO / Soft_Job / Salary 板
2. Dcard 接案版 / 創業版
3. FB 自由工作者社群(設計 / 翻譯 / 程式 / 行銷 各 3-10 萬人)
4. 104 外包 / Tasker / PRO360 integration
5. YouTube SOHO KOL(瓦基 / 雞蛋麵 / 阿璇)合作
6. 接案教學課程 partner

## 風險評估

| 風險 | 評估 | 緩解 |
|---|---|---|
| **Tier 價格隨市場變動** | 中 | Pro 版每季校準;接案平台 partner 拿即時 market data |
| **客戶 size 不同 tier 接受率不同** | 中 | 加 contextual bandit(client_size 為 context) |
| **早期樣本太少 bandit 不穩** | 中 | Beta(1,1) prior + 強調 exploration;UI 顯示「樣本不足」警告 |
| **Freelancer 全押 high tier 流失機會** | 高 | 多次強調「**Bandit 是輔助不是決定**」+ exploration 平衡 |
| **接案平台 (Upwork / 104) 自己做** | 低-中 | 在地化 + 台灣 freelancer 文化是護城河 |

---

*第三十八輪 2026-05-11,**第二十八個 AI 架構模式 — Multi-armed Bandit / Thompson Sampling**。跟前 37 輪所有 pattern 都不同。*
