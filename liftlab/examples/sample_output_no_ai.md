# liftlab 行銷 ROI 因果分析報告

**模式**: 純函式 Pearl backdoor adjustment(免 API key)

## 資料概況

- **月度資料**: 24 個月
- **Treatment 定義**: ad_spend ≥ NT$ 30,000(以下稱「高 ads 月」)
- **Confounders(共因)**: 旺季、節慶 / 大檔促銷、新品上市

## 1. Naive 估計(老闆通常會這樣想)

- 高 ads 月平均營收: **NT$ 459,642** (14 個月)
- 低 ads 月平均營收: **NT$ 270,000** (10 個月)
- **Naive ATE**: NT$ 189,642 / 月
- 看起來廣告每月多賺 NT$ 189,642,但這**包含 confounders 偏差**。

## 2. Backdoor-adjusted 估計(真實因果)

- **Adjusted ATE**: **NT$ 83,174 / 月**
- **Inflation factor**(naïve / adjusted): **2.28x**
- **可用 strata**: 3 / 8

### 各 stratum 細節

| 情境 | n (T+C) | T mean | C mean | Stratum ATE | weight |
|---|---|---|---|---|---|
| 淡季 / 無檔期 / 無新品 | 3+8 | NT$ 333,333 | NT$ 248,125 | NT$ 85,208 | 0.4583 |
| 淡季 / 有檔期 / 無新品 | 1+1 | NT$ 420,000 | NT$ 345,000 | NT$ 75,000 | 0.0833 |
| 旺季 / 無檔期 / 無新品 | 3+1 | NT$ 451,666 | NT$ 370,000 | NT$ 81,666 | 0.1667 |

## 3. Confounder Bias 拆解

Naive ATE 比 Adjusted ATE 多出 NT$ 106468 的偏差,由以下 confounders 貢獻:

| Confounder | 偏差 NT$ | 解釋 |
|---|---|---|
| 旺季 | +109,230 | 高 ads 月**比**低 ads 月**多** 54% 在 is_peak_season=True 的時段;is_peak_season=True 月份營收*... |
| 節慶 / 大檔促銷 | +73,125 | 高 ads 月**比**低 ads 月**多** 40% 在 is_holiday_promo=True 的時段;is_holiday_promo=True 月... |
| 新品上市 | +1,816 | 高 ads 月**比**低 ads 月**多** 7% 在 launched_new_product=True 的時段;launched_new_product... |

> ⚠️ 因為 confounders 彼此相關(旺季常含節慶),個別 bias 加總**不等於**總 inflation。

## 4. 純函式結論

⚠️ Naive ATE 顯示高 ads 月多賺 NT$ 189,642/月,但 backdoor-adjusted ATE 只有 NT$ 83,174/月 (2.3x inflation)。**老闆過去 24 個月** 以為廣告貢獻很大,實際 confounders(季節 / 節慶 / 新品)貢獻了大半。

---
*純函式模式無 AI 行銷建議。AI 模式會給故事化解釋 + 4-5 條具體 action items。*
*liftlab 提供因果推斷指引,不取代行銷顧問。實際決策請結合產業經驗。*