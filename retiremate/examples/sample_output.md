# retiremate 退休規劃 — 陳大哥

**模式**: AI agent + tool-use(Claude 自主規劃 + 純函式精算)

## AI 顧問報告

陳大哥您好,這份是您 65 歲退休的初步規劃。先說結論:**社會保險(勞退 + 勞保)月領金額僅 NT$27,894 確實偏低,但您 350 萬儲蓄 + 每月再存 2 萬,平均報酬下退休時可累積 887 萬,扣除月缺口仍有 314 萬餘額**,屬於「公保不夠 + 自備補足」的典型案例,整體財務可承受退休生活,但若想更從容,還有 4 個具體 lever 可操作。

### 各項所得來源(月領 / 60-65 歲後)

| 來源 | 月領 NT$ | 計算依據 |
|---|---|---|
| 勞退新制(雇主 6% 提繳 22 年) | 6,597 | 60 歲帳戶累積 NT$1,899,955 / 24 年期年金 |
| 勞保老年年金(30 年新式擇優) | 21,297 | 月投保 NT$45,800 × 30 × 1.55% |
| **合計月所得** | **27,894** | |

### 月支出與缺口

| 項目 | 金額 NT$ |
|---|---|
| 雙北雙人家庭月支出基準 | 60,000 |
| 退休後健保(第六類地區人口) | 886 |
| **月支出加總** | **60,886** |
| **每月缺口(所得 - 支出)** | **-32,992** |
| 缺口等級 | 🔴 SEVERE_GAP(覆蓋率 45.8%) |

### 儲蓄成長預測 vs 需要儲蓄

| 項目 | 金額 NT$ |
|---|---|
| 目前儲蓄 | 3,500,000 |
| 每月再存 | 20,000 |
| 距退休 | 10 年 |
| 65 歲累積(保守 3%) | 7,517,566 |
| 65 歲累積(平均 5%) | 8,870,179 |
| 65 歲累積(積極 7%) | 10,495,511 |
| **退休後 19 年補足月缺口需備** | **5,728,363** |
| **餘額(平均情境)** | **+3,141,816 ✓** |

### 4 個具體建議(由近到遠的影響力排序)

1. **立即啟動「勞退新制自願提繳 6%」** — 您目前自提 0%,但自願提繳是「節稅 + 強迫儲蓄 + 政府保證收益(近年實際 3-5%)」三贏。以您月薪 NT$75,000 計算,自提 6% 等於每月再存 NT$4,500 (但**不計入綜合所得稅**,以您稅率 12% 推算等於每月省 NT$540 的稅)。10 年下來退休帳戶可多累積約 NT$66 萬。如果你考慮再存錢,**自提帳戶應該優先於投資帳戶**(報酬保證 + 稅務優惠 + 強迫儲蓄)。

2. **延後 1-2 年退休的影響超乎想像** — 若 65 → 67 歲退休:① 勞保多 2 年加保 + 平均薪資推升,月領預估從 NT$21,297 → 約 NT$23,300;② 勞退多 2 年提繳 + 複利,累積帳戶從 NT$190 萬 → 約 NT$220 萬;③ 個人儲蓄多 2 年複利 + 多 48 萬月存,平均情境累積從 887 萬 → 約 1,030 萬;④ 退休後生活年期從 19 年縮為 17 年。**綜合下來月缺口從 NT$32,992 縮為約 NT$27,000**,需要儲蓄從 573 萬縮為約 425 萬,**安全餘裕從 314 萬擴大到約 605 萬**。

3. **勞保「展延請領」每多 1 年 +4%** — 法定 65 歲可請領,若延到 66 歲為「展延 1 年 +4%」(月領 NT$22,149)、67 歲為 +8%(NT$23,001)、最多 70 歲 +20%(NT$25,556)。**這個加碼是終身的**,跟「實際多繳 1 年」是兩回事(可同時做)。如果您 67 歲才退休 + 同時展延勞保 2 年,月領可拉到約 NT$25K。

4. **儲蓄配置簡化檢視** — 您 350 萬儲蓄目前在哪?如果全在定存(年化 1.5-2%)會跑輸我這份試算的 5% 平均情境。建議拆成三層:① 緊急備用 6 個月生活費 NT$36 萬放高利活儲;② 中短期 NT$100 萬放台幣定存或債券型 ETF (3-4%);③ 長期 NT$214 萬可考慮 0050 / 006208 等台股大盤 ETF(歷史平均 7-8%)。**這不是推銷任何特定商品** — 0050 / 006208 全網都查得到,任何券商都能買,費用最低。

### 重要提醒

- 本試算採用 2024 年勞動部公告值(平均月投保薪資上限 NT$45,800、勞退提繳率 6%、平均餘命 84 歲)+ 主計總處 2023 家庭收支調查
- **勞保官方試算**: 勞動部勞工保險局「個人勞保資料查詢 + 老年年金試算」https://edesk.bli.gov.tw/me/
- **勞退官方試算**: 勞動部「勞工退休金個人試算」https://www.bli.gov.tw/0011905.html
- 通膨假設:本試算未調整通膨。若考慮 2% 通膨,10 年後 NT$60,886 月支出實際應約 NT$74,200。建議重新檢視
- 如果家中有重大事件預期(子女結婚 / 換購房 / 醫療),需另外計入

---

## Agent tool 調用紀錄(透明化)

### Step 1: `estimate_labor_pension_new`
- args: `{"avg_monthly_salary": 75000, "years_contributed": 22, "self_contribute_rate": 0.0}`
- result: `{"scheme": "勞退新制(個人退休金專戶)", "monthly_contribution_employer": 4500, "monthly_contribution_self": 0, "monthly_contribution_total": 4500, "years_contributed": 22, "annual_return_used": 0.04, "total_account_balance_at_60": 1899955, "estimated_monthly_pension": 6597, "can_monthly_payout": true, ...}`

### Step 2: `estimate_labor_insurance_pension`
- args: `{"avg_monthly_insurance_salary": 45800, "years_paid": 30}`
- result: `{"scheme": "勞保老年年金(社會保險)", "avg_monthly_insurance_salary_used": 45800, "years_paid": 30, "monthly_pension_formula_a_old": 13648, "monthly_pension_formula_b_new": 21297, "selected_monthly_pension": 21297, "eligible_for_monthly": true, ...}`

### Step 3: `estimate_national_pension` — skipped (no national pension years)

### Step 4: `project_personal_savings`
- args: `{"current_balance": 3500000, "monthly_save": 20000, "years_to_retirement": 10}`
- result: `{"scenarios_balance_at_retirement": {"保守 (3%)": 7517566, "平均 (5%)": 8870179, "積極 (7%)": 10495511}, "primary_scenario": 8870179, ...}`

### Step 5: `estimate_monthly_living_cost`
- args: `{"region": "雙北", "household_type": "couple"}`
- result: `{"region": "雙北", "household_type": "couple", "monthly_living_cost_baseline": 60000, ...}`

### Step 6: `estimate_post_retirement_nhi`
- args: `{}`
- result: `{"income_class": "tier6", "monthly_nhi_premium": 886, ...}`

### Step 7: `compute_retirement_gap`
- args: `{"monthly_income_sources": {"勞退新制(個人退休金專戶)": 6597, "勞保老年年金(社會保險)": 21297}, "monthly_expenses": 60000, "nhi_monthly": 886}`
- result: `{"monthly_income_total": 27894, "monthly_total_expense": 60886, "monthly_gap": -32992, "coverage_pct": 45.8, "gap_level": "SEVERE_GAP", "verdict": "退休所得 NT$27,894 僅涵蓋 45.8% 月支出 NT$60,886,每月缺口 NT$32,992。**強烈建議**諮詢退休理財顧問..."}`

### Step 8: `required_savings_for_gap`
- args: `{"monthly_gap": 32992, "years_in_retirement": 19}`
- result: `{"monthly_gap": 32992, "years_in_retirement": 19, "annual_return_used": 0.03, "required_savings": 5728363, "notes": "每月缺 NT$32,992 × 19 年..."}`

---
*重要提醒:本試算僅供參考,實際請對照勞動部「勞工保險局個人專戶資料查詢」與「勞退新制試算」官網。*
