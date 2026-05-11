# quotelab 報價策略 Multi-armed Bandit 報告

**模式**: 純函式 Thompson Sampling(免 API key)

## 自由工作者 Portfolio

- **Freelancer**: 陳設計師
- **專長**: LOGO_DESIGN / WEB_DESIGN
- **接案年資**: 3 年
- **目標月收**: NT$ 80,000
- **歷史報價**: 28 筆 / 成交: 19(67.9%)
- **歷史實收**: NT$ 442,000
- **最賺領域**: WEB_DESIGN (NT$ 385,000)

## 新 case

- **Case ID**: Q-NEW-001
- **類型**: LOGO_DESIGN
- **描述**: 服飾品牌 rebranding,需要新 logo + 應用延伸(名片 / 招牌 / 包裝)
- **客戶 size**: 中型(年收 5,000 萬以上)
- **截止**: 14 天

## Thompson Sampling 推薦 tier

- **推薦 tier**: **HIGH** (進階)
- **建議報價**: **NT$ 12,000**
- **期望接受率**: 50.0%
- **期望收益(EV)**: NT$ 6,000
- **信心度**: 50.8%(在 1000 次 Thompson sampling 中該 tier 勝出比例)
- **第 2 名 tier**: PREMIUM (EV NT$ 5,000)

**推薦理由**: 在 1000 次 Thompson sampling 中,HIGH tier 勝出 508 次 (50.8%);其期望收益 NT$ 6,000 = 接受率 50.0% × 價格 NT$ 12,000。 ⚠️ 該 tier 樣本數僅 4,結果不確定性高,建議多試驗幾次再判斷。

## LOGO_DESIGN 各 tier 表現

| Tier | 報價 | n_quoted | 接受率(均) | 95% CI | 期望收益 |
|---|---|---|---|---|---|
| 保守 | NT$ 3,000 | 4 | 66.7% | [32-100%] | NT$ 2,000 |
| 標準 | NT$ 6,000 | 5 | 71.4% | [40-100%] | NT$ 4,286 |
| 進階 ⭐ | NT$ 12,000 | 4 | 50.0% | [13-87%] | NT$ 6,000 |
| 頂級 | NT$ 20,000 | 2 | 25.0% | [0-63%] | NT$ 5,000 |

## ⚠️ Exploration warnings(樣本不足的 tier)

- LOGO_DESIGN × PREMIUM 只有 2 筆 — bandit 需更多 exploration
- WEB_DESIGN × PREMIUM 只有 2 筆 — bandit 需更多 exploration

---
*純函式模式無 AI 配套策略。AI 模式會給報價文案開場 + 議價底線 + 配套建議 + 長期策略。*
*quotelab 是輔助工具,最終報價決策由 freelancer 自行判斷;市場價格隨時變動需定期 calibrate。*