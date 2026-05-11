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
