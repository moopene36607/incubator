# quotelab 報價策略 Multi-armed Bandit 報告

**模式**: 純函式 Thompson Sampling + AI 報價顧問

## Freelancer Portfolio

- 陳設計師 / 專長: LOGO_DESIGN / WEB_DESIGN
- 歷史 28 報價 / 成交 19(67.9%)
- 實收 NT$ 442,000

## 新 case

> **LOGO_DESIGN** — 服飾品牌 rebranding,需要新 logo + 應用延伸(名片 / 招牌 / 包裝)
> 客戶 size: 中型(年收 5,000 萬以上) / 截止: 14 天

## 🎯 Bandit 推薦

- **建議報價 tier**: **HIGH**(進階)
- **建議金額**: **NT$ 12,000**
- **期望接受率**: 50.0% / **期望收益**: NT$ 6,000
- **信心度**: 50.8%

### 為什麼這 tier 是好選擇

這個案子是「**中型服飾品牌 rebranding + 應用延伸**」 — 是 HIGH tier 的典型客戶 picture。歷史 HIGH tier 4 筆中 2 筆成交(50%),客戶通常是「**中型零售連鎖 / 公司 rebranding**」這種有預算且需要正式視覺系統的需求。本案的「**名片 / 招牌 / 包裝**」應用延伸更貼合 HIGH 定位(不只 logo 還有 brand system)。**雖然 PREMIUM EV 略低(NT$5K vs NT$6K),但樣本只有 2 筆且都被拒,代表客戶接受 NT$20K 報價在你的案源中尚未發生** — 建議先試 HIGH,等更多 PREMIUM 樣本後 bandit 自然會調整。

## 報價策略

### 開場 pitch

> 您好,謝謝您的詢問。看完您品牌 rebranding 需求(新 logo + 名片 + 招牌 + 包裝)後,我能提供完整的視覺系統設計而非單純 logo。**建議方案 NT$12,000**,**包含 logo 3 版方案 + 應用延伸全套 + 1 次大改 + 2 次微調**,2 週內交付。

### 報價單應包含

- Logo 設計 3 版方案(2 風格選擇 + 1 安全方案)
- 名片設計(雙面)
- 招牌應用延伸(2 種尺寸)
- 包裝視覺主視覺(可延伸標籤 / 包裝紙)
- **1 次大改機會 + 2 次微調**(明文寫明,避免無限改稿地獄)
- **AI / EPS / PNG / PDF 完整檔案**
- 商業使用授權說明
- **付款條件**:訂金 40%(簽約時)+ 期中 30%(初稿)+ 期末 30%(交檔)

### 議價底線

客戶若殺價:
- NT$10,000 可接受(議價空間 NT$2K = 16% 折扣)— 但需減 1 個應用延伸(如去掉包裝)
- NT$8,000 以下: **建議婉拒**,因為這價位是 MID tier 範圍而你的服務內容已屬 HIGH

**Walk-away 價**: NT$ 8,000

## 非價格 levers(提升成交率)

- **附 2 個 mockup 預覽**:Logo 套用在實際招牌 / 名片 / 包裝的擬真圖,讓客戶「看見」最終效果 → 成交率 +15-25%
- **附類似 case 作品集**:過去 HIGH 成交的 2 個 case(Q010 中型零售 / Q011 rebranding)的 portfolio 連結
- **強調「**14 天交付**」**:對方有時效壓力是強需求 → 你保證準時是 differentiator
- **報價有效期 7 天**:創造急迫感,避免對方拖延或同時詢價多家
- **不要急著降價**:第一輪如果對方反應慢,過 3 天再 follow-up 「**有任何疑問都可以問**」,而非主動降價

## LOGO_DESIGN 各 tier bandit 表現

| Tier | 報價 | n | 接受率 | EV |
|---|---|---|---|---|
| 保守 | NT$ 3,000 | 4 | 66.7% | NT$ 2,000 |
| 標準 | NT$ 6,000 | 5 | 71.4% | NT$ 4,286 |
| **進階 ⭐** | **NT$ 12,000** | 4 | **50.0%** | **NT$ 6,000** |
| 頂級 | NT$ 20,000 | 2 | 25.0% | NT$ 5,000 |

## 🧪 Exploration 建議

- **LOGO_DESIGN × PREMIUM 只有 2 筆 reject** — 建議下次遇到「**大型企業 / 知名連鎖品牌 rebranding**」案件主動試 PREMIUM (NT$20K),即使被拒 1-2 次也是有價值的資訊(確認 PREMIUM 在你的客源中不可行)
- **WEB_DESIGN × PREMIUM 已有 1 成交 1 reject**,接受率 50% EV NT$50K — **強烈鼓勵主動接觸「大型電商 / 集團官網**」案件試 PREMIUM,可能是你目前最賺的領域

## 📈 長期策略

陳設計師,看你 28 筆資料:**WEB_DESIGN 實收 NT$385K vs LOGO_DESIGN NT$57K**,差距達 6.7 倍。長期策略應該:**(1) 把 60-70% 時間投在 WEB_DESIGN 接案 / 推廣**(LinkedIn / IG 作品集 / 接案平台),這是你的「**金母牛**」;**(2) LOGO_DESIGN 案件用 MID-HIGH 為主**(MID EV 4286 / HIGH EV 6000),Skip LOW(EV 太低),不值得時間;**(3) 持續探索 PREMIUM 兩個領域**,目標是 1 年內讓 PREMIUM 樣本到 10+ 筆,讓 bandit 信心度大幅提升。月收 NT$80K 目標下:WEB 接 1 個 MID(NT$30K)+ 1 個 HIGH(NT$60K)就達標,LOGO 是 supplemental。

---
*quotelab 是輔助工具,最終報價決策由 freelancer 自行判斷;市場價格隨時變動需定期 calibrate。*
