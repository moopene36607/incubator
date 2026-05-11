# salaryci 薪資談判 conformal prediction 報告

**求職者**: 王小明 (4 年後端 RD, 中型 SaaS → 跳槽中型電商)
**目標職位**: SOFTWARE / BACKEND / MID / 4 年經驗 / TAIPEI

## 🎯 90% 信心區間 (conformal prediction interval)

### NT$ **60 K — 84 K** / 月

- **中位數估計**: NT$72K / 月
- **nonconformity quantile q**: 12.0 (90% 殘差)
- **CI 寬度**: ±NT$12K (相當於 ±17%)
- **覆蓋率保證**: 在交換性 (exchangeability) 假設下,真實薪資落入此區間機率 ≥ 90%

## Calibration Set (純函式 nearest-cluster 比對)

- **匹配筆數**: 7 筆同質性記錄
- **過濾條件**: `industry=SOFTWARE + role=BACKEND + level=MID + exp ±2`
- **corpus 分布**: P10=60K, P50=72K, P90=82K
- **排序的殘差**: [0.0, 2.0, 3.0, 6.0, 7.0, 10.0, 12.0]

ℹ️ calibration set 7 筆 — 樣本中等,90% CI 為合理估計但可能稍寬。

## 你的 offer 在 corpus 中的位置

- **目前 offer**: NT$68K / 月
- **vs 中位數**: -5.6%
- **在 calibration set 中**: 第 29 百分位
- 🟡 **偏行情下緣** — 可以爭取到 median 附近

## 純函式談判錨點

- **walk-away (90% CI 下限)**: NT$60K — 低於此可直接 walk away
- **median anchor**: NT$72K — 對方第一次出價這個算合理
- **aim for (median 與上限之間)**: NT$78K — 你的目標應該瞄這裡
- **stretch target (90% CI 上限)**: NT$84K — 對方真的喜歡你會給到這

## ⚠️ 模型限制

- **不含 bonus / RSU / 簽約金 / 加班費** — 只看月薪 base
- **calibration set 是 prototype 樣本** — 真實 launch 版會用 1,000+ 筆 PTT Salary + 104 + Yourator 資料
- **conformal coverage 是邊際 (marginal)**,個別案件可能落 CI 外 — 但長期 90% 群體會落內
- **交換性假設**: 假設樣本與你 i.i.d.,如果你有特殊背景(海外名校 / 大廠出身 / 特定證照),CI 會偏低估

---
*salaryci = conformal prediction × 台灣薪資談判 = 信心區間 +談判錨點 而非單一中位數猜測。*

## 🤖 AI 獵頭談判腳本

NT$68K 在你這群「4 年後端 RD」中只在 29 百分位,等於 100 個同經歷的人裡有 70+ 個拿比你高 — 是**偏低**不是「合理」。HR 第一次出價通常會壓 5-10% 試水溫,你有空間 push 到 median NT$72K 不會折損 offer。

**建議開場**:「謝謝這份 offer。我做過台灣後端 4-5 年薪資的 cross-check,中位數落在 NT$72K 附近,我這 4 年自己帶過兩個 production migration、寫過 2 篇技術 blog,所以我希望我們可以再對齊一下 base — 我心目中是 NT$78K,如果這個數字超過 budget,**NT$75K 加上 6 個月後 review 條款**也可以接受。」

**非薪資槓桿同時談**:① 試用期能縮到 2 個月嗎(縮短你風險)② RSU / 簽約金條件 ③ WFH 政策(中型電商通常彈性大)④ 年假 14 天 vs 法定 7 天。

⚠️ **不要在電話裡當場 push**,寫 email 給 HR 留書面記錄;若公司給你 24 小時 deadline 反而是壓力測試,你可以說「我需要 48 小時跟另一個 pipeline 對齊」— 你的 walk-away 是 NT$60K,低於此這 offer 不值得接(在行情 P10 以下了)。
