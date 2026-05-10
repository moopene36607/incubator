"""retiremate — 台灣退休規劃 AI 顧問:純函式 tools(no I/O, no LLM).

每個 function = 一個 agent tool。LLM 在 retiremate.py 用 tool-use API 決定
什麼時候調用哪個 tool;本檔案只負責提供乾淨、可單元測試的計算邏輯。

數據來源(2024-2025 公告值,將於每年 4 月 / 1 月更新):
  - 勞退新制:勞動部勞工退休金條例 第 14, 23 條
  - 勞保老年年金:勞工保險條例 第 58, 65 條;新式公式 1.55%、舊式 0.775% + NT$3,000
  - 國民年金:國民年金法 第 30 條;月投保金額 NT$19,761(2024)
  - 退休後健保:全民健康保險法;第六類地區人口 NT$886/月(2024)
  - 退休生活支出:行政院主計總處家庭收支調查(2023 公布)

設計守則:
  - 數字 100% 純函式;LLM 永不算錢
  - 簡化必要的折扣:不接精算員年金生命表(用平均餘命 / 月數)
  - 所有金額單位 NT$,年期單位「年」
"""

from __future__ import annotations

from dataclasses import dataclass


# ===== 常數(2024 公告值)=====
NPI_INSURANCE_BASE = 19761                    # 國民年金月投保金額
NPI_BASE_PAYMENT = 4049                       # 國民年金 A 式基本保證
LABOR_INSURANCE_MAX_INSURANCE_BASE = 45800    # 勞保最高月投保薪資 (2024)
NHI_RETIREMENT_TIER6_MONTHLY = 886            # 退休後第六類健保月費

LABOR_PENSION_EMPLOYER_RATE = 0.06            # 勞退新制雇主提繳率
DEFAULT_INVESTMENT_RETURN = 0.04              # 勞退基金保證收益率(近年實際 3-5%)
DEFAULT_LIFE_EXPECTANCY = 84                  # 內政部最新國人平均餘命(簡化用 84)


# ===== 退休月支出基準(2024 主計總處家庭收支調查) =====
LIVING_COST_BY_REGION = {
    "雙北": {"single": 35000, "couple": 60000},
    "桃竹": {"single": 28000, "couple": 50000},
    "中部": {"single": 25000, "couple": 45000},
    "南部": {"single": 23000, "couple": 40000},
    "東部 / 離島": {"single": 22000, "couple": 38000},
}


# ===== Tool 1:勞退新制 個人專戶累積估算 =====
def estimate_labor_pension_new(
    avg_monthly_salary: int,
    years_contributed: int,
    self_contribute_rate: float = 0.0,
    annual_return: float = DEFAULT_INVESTMENT_RETURN,
) -> dict:
    """估算勞退新制 60 歲時個人專戶累積金額 + 月領年金額。

    Args:
        avg_monthly_salary: 平均月薪(原始薪資,非提繳工資;函式內部會 cap 至最高提繳工資 150,000)
        years_contributed: 提繳年數
        self_contribute_rate: 員工自願提繳率(0-0.06)
        annual_return: 預期年化報酬率

    Returns: {
        "scheme": "勞退新制",
        "monthly_contribution_employer": ...,
        "monthly_contribution_self": ...,
        "total_account_balance_at_60": ...,
        "estimated_monthly_pension": ...,  # 滿 15 年才可月領;未滿 15 年只能一次領
        "can_monthly_payout": True/False,
        "notes": "...",
    }
    """
    pension_base = min(avg_monthly_salary, 150000)  # 法定最高提繳工資 150,000
    monthly_employer = round(pension_base * LABOR_PENSION_EMPLOYER_RATE)
    monthly_self = round(pension_base * max(0.0, min(0.06, self_contribute_rate)))
    total_monthly = monthly_employer + monthly_self

    # 累積:複利 PMT-FV
    n_months = years_contributed * 12
    r_monthly = annual_return / 12
    if r_monthly > 0:
        future_value = total_monthly * ((1 + r_monthly) ** n_months - 1) / r_monthly
    else:
        future_value = total_monthly * n_months

    can_monthly = years_contributed >= 15
    # 60 歲到 84 歲 = 24 年 = 288 月
    monthly_pension = round(future_value / ((DEFAULT_LIFE_EXPECTANCY - 60) * 12)) if can_monthly else 0

    return {
        "scheme": "勞退新制(個人退休金專戶)",
        "monthly_contribution_employer": monthly_employer,
        "monthly_contribution_self": monthly_self,
        "monthly_contribution_total": total_monthly,
        "years_contributed": years_contributed,
        "annual_return_used": annual_return,
        "total_account_balance_at_60": round(future_value),
        "estimated_monthly_pension": monthly_pension,
        "can_monthly_payout": can_monthly,
        "notes": (
            f"雇主提繳 6% 月薪 = NT${monthly_employer:,};"
            f"{'你自願提繳' if monthly_self > 0 else '若再自願提繳 6% (節稅) 可多 NT$' + str(round(pension_base * 0.06)) + '/月'}"
            f";年化 {annual_return*100:.1f}% 複利 {years_contributed} 年累積至 60 歲約 NT${round(future_value):,}"
            f"。{'已滿 15 年可選擇月領或一次領' if can_monthly else '未滿 15 年只能一次領,無月領資格'}。"
        ),
    }


# ===== Tool 2:勞保老年年金估算 =====
def estimate_labor_insurance_pension(
    avg_monthly_insurance_salary: int,
    years_paid: int,
) -> dict:
    """估算勞保老年年金月領金額(擇優公式)。

    Args:
        avg_monthly_insurance_salary: 最高 60 個月平均月投保薪資(法定上限 NT$45,800/2024)
        years_paid: 加保年資

    Returns: {
        "monthly_pension_formula_a": ... (舊式: 0.775% × 年資 + 3,000),
        "monthly_pension_formula_b": ... (新式: 1.55% × 年資),
        "selected_monthly_pension": max(a, b),
        "eligible": True/False (滿 15 年 + 達法定請領年齡),
        ...
    }
    """
    base = min(avg_monthly_insurance_salary, LABOR_INSURANCE_MAX_INSURANCE_BASE)
    formula_a = round(base * years_paid * 0.00775 + 3000)
    formula_b = round(base * years_paid * 0.0155)
    selected = max(formula_a, formula_b)
    eligible = years_paid >= 15

    return {
        "scheme": "勞保老年年金(社會保險)",
        "avg_monthly_insurance_salary_used": base,
        "years_paid": years_paid,
        "monthly_pension_formula_a_old": formula_a,
        "monthly_pension_formula_b_new": formula_b,
        "selected_monthly_pension": selected if eligible else 0,
        "eligible_for_monthly": eligible,
        "notes": (
            f"加保 {years_paid} 年,平均月投保薪資 NT${base:,};"
            f"擇優取新式 NT${formula_b:,} vs 舊式 NT${formula_a:,} = NT${selected:,}/月。"
            f"{'已符合月領資格' if eligible else '未滿 15 年,只能一次領(計算方式不同)'}。"
        ),
    }


# ===== Tool 3:國民年金估算 =====
def estimate_national_pension(years_paid: int) -> dict:
    """估算國民年金月領金額(A 式 vs B 式擇優)。

    A 式:月投保金額 × 0.65% × 年資 + NT$4,049 (2024)
    B 式:月投保金額 × 1.3% × 年資
    """
    formula_a = round(NPI_INSURANCE_BASE * 0.0065 * years_paid + NPI_BASE_PAYMENT)
    formula_b = round(NPI_INSURANCE_BASE * 0.013 * years_paid)
    selected = max(formula_a, formula_b)

    return {
        "scheme": "國民年金(社會保險)",
        "years_paid": years_paid,
        "monthly_pension_formula_a": formula_a,
        "monthly_pension_formula_b": formula_b,
        "selected_monthly_pension": selected,
        "notes": (
            f"國民年金加保 {years_paid} 年,月投保金額 NT${NPI_INSURANCE_BASE:,};"
            f"A 式 NT${formula_a:,} vs B 式 NT${formula_b:,},擇優 NT${selected:,}/月。"
            f"提醒:國保是「未在勞 / 公 / 軍 / 農保期間」才強制納保,曾在勞保年資已扣除。"
        ),
    }


# ===== Tool 4:個人儲蓄複利成長估算 =====
def project_personal_savings(
    current_balance: int,
    monthly_save: int,
    years_to_retirement: int,
    annual_return: float = 0.05,
) -> dict:
    """估算自儲蓄到退休時複利成長。

    考量保守(0.03)、平均(0.05)、積極(0.07)情境並回傳。
    """
    n_months = years_to_retirement * 12
    scenarios = {}
    for label, r in [("保守 (3%)", 0.03), ("平均 (5%)", 0.05), ("積極 (7%)", 0.07)]:
        r_m = r / 12
        if r_m > 0:
            fv_existing = current_balance * (1 + r_m) ** n_months
            fv_pmt = monthly_save * ((1 + r_m) ** n_months - 1) / r_m
        else:
            fv_existing = current_balance
            fv_pmt = monthly_save * n_months
        scenarios[label] = round(fv_existing + fv_pmt)

    return {
        "current_balance": current_balance,
        "monthly_save": monthly_save,
        "years_to_retirement": years_to_retirement,
        "scenarios_balance_at_retirement": scenarios,
        "primary_scenario": scenarios["平均 (5%)"],
        "notes": (
            f"目前儲蓄 NT${current_balance:,} + 每月再存 NT${monthly_save:,},"
            f"距退休 {years_to_retirement} 年。平均報酬 5% 情境下退休時可累積 NT${scenarios['平均 (5%)']:,}。"
            f"報酬率假設僅供參考,實際依配置不同。"
        ),
    }


# ===== Tool 5:退休月生活費基準 =====
def estimate_monthly_living_cost(region: str, household_type: str = "couple") -> dict:
    """根據地區 + 家庭結構查詢退休月支出基準。

    Args:
        region: 雙北 / 桃竹 / 中部 / 南部 / 東部 / 離島
        household_type: single | couple
    """
    region_data = LIVING_COST_BY_REGION.get(region) or LIVING_COST_BY_REGION["中部"]
    base = region_data.get(household_type, region_data["couple"])
    return {
        "region": region,
        "household_type": household_type,
        "monthly_living_cost_baseline": base,
        "notes": (
            f"{region} {('單人' if household_type == 'single' else '雙人')}退休家庭月支出基準 NT${base:,}"
            f"(主計總處 2023 家庭收支調查推估)。實際視個人習慣 ±20%。"
        ),
    }


# ===== Tool 6:退休後健保費 =====
def estimate_post_retirement_nhi(income_class: str = "tier6") -> dict:
    """退休後健保保費。

    Args:
        income_class: tier6 (地區人口,絕大多數退休者適用)
    """
    if income_class == "tier6":
        monthly = NHI_RETIREMENT_TIER6_MONTHLY
        explain = "第六類地區人口(絕大多數退休勞工 / 自由業)"
    else:
        monthly = NHI_RETIREMENT_TIER6_MONTHLY
        explain = "預設第六類地區人口"
    return {
        "income_class": income_class,
        "monthly_nhi_premium": monthly,
        "notes": f"退休後健保歸屬 {explain},每月 NT${monthly:,}(2024 公告)。",
    }


# ===== Tool 7:退休月所得 vs 支出 缺口分析 =====
def compute_retirement_gap(
    monthly_income_sources: dict,  # {"勞退新制": ..., "勞保老年年金": ..., ...}
    monthly_expenses: int,
    nhi_monthly: int = NHI_RETIREMENT_TIER6_MONTHLY,
) -> dict:
    """計算退休後每月所得來源加總 vs 月支出 + 健保。"""
    income_total = sum(monthly_income_sources.values())
    total_expense = monthly_expenses + nhi_monthly
    gap = income_total - total_expense  # 正 = 有結餘;負 = 缺口
    coverage_pct = round(income_total / total_expense * 100, 1) if total_expense > 0 else 0

    if gap >= 0:
        level = "OK"
        verdict = (
            f"退休所得 NT${income_total:,} ≥ 月支出 NT${total_expense:,},"
            f"每月結餘 NT${gap:,}。財務獨立。"
        )
    elif coverage_pct >= 80:
        level = "MINOR_GAP"
        verdict = (
            f"退休所得 NT${income_total:,} 涵蓋 {coverage_pct}% 月支出 NT${total_expense:,},"
            f"每月缺口 NT${-gap:,}。需動用儲蓄補足。"
        )
    elif coverage_pct >= 60:
        level = "MEDIUM_GAP"
        verdict = (
            f"退休所得 NT${income_total:,} 僅涵蓋 {coverage_pct}% 月支出 NT${total_expense:,},"
            f"每月缺口 NT${-gap:,}。退休前 5 年內需積極補強。"
        )
    else:
        level = "SEVERE_GAP"
        verdict = (
            f"退休所得 NT${income_total:,} 僅涵蓋 {coverage_pct}% 月支出 NT${total_expense:,},"
            f"每月缺口 NT${-gap:,}。**強烈建議**諮詢退休理財顧問,考慮延後退休 / 提高儲蓄。"
        )

    return {
        "monthly_income_sources": monthly_income_sources,
        "monthly_income_total": income_total,
        "monthly_living_cost": monthly_expenses,
        "monthly_nhi_premium": nhi_monthly,
        "monthly_total_expense": total_expense,
        "monthly_gap": gap,
        "coverage_pct": coverage_pct,
        "gap_level": level,
        "verdict": verdict,
    }


# ===== Tool 8:退休缺口需要多少存款補足 =====
def required_savings_for_gap(
    monthly_gap: int,
    years_in_retirement: int,
    annual_return: float = 0.03,
) -> dict:
    """若退休後每月缺 X 元,退休時需要多少儲蓄能撐到平均餘命。"""
    if monthly_gap <= 0:
        return {
            "required_savings": 0,
            "notes": "無月缺口,不需特別準備儲蓄補足。",
        }
    # 等額退休年金現值 (期初付款)
    n_months = years_in_retirement * 12
    r_m = annual_return / 12
    if r_m > 0:
        pv = monthly_gap * (1 - (1 + r_m) ** -n_months) / r_m
    else:
        pv = monthly_gap * n_months
    return {
        "monthly_gap": monthly_gap,
        "years_in_retirement": years_in_retirement,
        "annual_return_used": annual_return,
        "required_savings": round(pv),
        "notes": (
            f"每月缺 NT${monthly_gap:,} × {years_in_retirement} 年,"
            f"以 {annual_return*100:.0f}% 年化保守報酬計算,退休時需備儲蓄 NT${round(pv):,} 補足。"
        ),
    }


# ===== Tool registry (供 LLM tool-use API 使用) =====
TOOL_DEFINITIONS = [
    {
        "name": "estimate_labor_pension_new",
        "description": "估算勞退新制 60 歲時個人專戶累積金額 + 月領年金。輸入平均月薪 + 提繳年數 + 自願提繳率。",
        "input_schema": {
            "type": "object",
            "properties": {
                "avg_monthly_salary": {"type": "integer", "description": "平均月薪(原始薪資)"},
                "years_contributed": {"type": "integer", "description": "提繳年數"},
                "self_contribute_rate": {"type": "number", "description": "員工自願提繳率 0-0.06,預設 0"},
            },
            "required": ["avg_monthly_salary", "years_contributed"],
        },
    },
    {
        "name": "estimate_labor_insurance_pension",
        "description": "估算勞保老年年金月領金額(擇優公式)。輸入最高 60 個月平均投保薪資 + 加保年資。",
        "input_schema": {
            "type": "object",
            "properties": {
                "avg_monthly_insurance_salary": {"type": "integer"},
                "years_paid": {"type": "integer"},
            },
            "required": ["avg_monthly_insurance_salary", "years_paid"],
        },
    },
    {
        "name": "estimate_national_pension",
        "description": "估算國民年金月領金額(A/B 式擇優)。輸入加保年資。",
        "input_schema": {
            "type": "object",
            "properties": {"years_paid": {"type": "integer"}},
            "required": ["years_paid"],
        },
    },
    {
        "name": "project_personal_savings",
        "description": "估算自有儲蓄複利成長到退休時(保守 3% / 平均 5% / 積極 7% 三種情境)。",
        "input_schema": {
            "type": "object",
            "properties": {
                "current_balance": {"type": "integer"},
                "monthly_save": {"type": "integer"},
                "years_to_retirement": {"type": "integer"},
            },
            "required": ["current_balance", "monthly_save", "years_to_retirement"],
        },
    },
    {
        "name": "estimate_monthly_living_cost",
        "description": "查詢退休後每月生活費基準。region 為 雙北 / 桃竹 / 中部 / 南部 / 東部 / 離島;household_type 為 single / couple。",
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {"type": "string"},
                "household_type": {"type": "string", "enum": ["single", "couple"]},
            },
            "required": ["region", "household_type"],
        },
    },
    {
        "name": "estimate_post_retirement_nhi",
        "description": "估算退休後健保月保費。",
        "input_schema": {
            "type": "object",
            "properties": {"income_class": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "compute_retirement_gap",
        "description": "計算退休後月所得加總 vs 月支出 + 健保的缺口。輸入 monthly_income_sources(dict)+ monthly_expenses + nhi_monthly。",
        "input_schema": {
            "type": "object",
            "properties": {
                "monthly_income_sources": {"type": "object"},
                "monthly_expenses": {"type": "integer"},
                "nhi_monthly": {"type": "integer"},
            },
            "required": ["monthly_income_sources", "monthly_expenses"],
        },
    },
    {
        "name": "required_savings_for_gap",
        "description": "若退休後每月缺 X 元,退休時需要多少儲蓄能撐到平均餘命。",
        "input_schema": {
            "type": "object",
            "properties": {
                "monthly_gap": {"type": "integer"},
                "years_in_retirement": {"type": "integer"},
            },
            "required": ["monthly_gap", "years_in_retirement"],
        },
    },
]


# Tool dispatcher (給 retiremate.py 使用)
TOOL_FUNCTIONS = {
    "estimate_labor_pension_new": estimate_labor_pension_new,
    "estimate_labor_insurance_pension": estimate_labor_insurance_pension,
    "estimate_national_pension": estimate_national_pension,
    "project_personal_savings": project_personal_savings,
    "estimate_monthly_living_cost": estimate_monthly_living_cost,
    "estimate_post_retirement_nhi": estimate_post_retirement_nhi,
    "compute_retirement_gap": compute_retirement_gap,
    "required_savings_for_gap": required_savings_for_gap,
}


def call_tool(name: str, args: dict) -> dict:
    """純函式 dispatcher。LLM 用 tool-use API 決定 name + args,本函式直接執行。"""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"未知 tool {name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"tool {name} 參數錯誤: {e}"}
