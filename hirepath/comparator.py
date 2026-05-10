"""hirepath — 台灣中小企業「招專員 vs 外包」全週期 ROI 對照(純函式,no I/O, no LLM).

責任:
  - 完整雇用成本(月薪 + 雇主健保 / 勞保 / 勞退提繳 + 三節獎金 + 年終 +
    招聘 + 培訓 + 設備 + 預估離職重招風險)
  - 完整外包成本(月費 + 老闆對接時間機會成本 + 廠商切換風險)
  - 兩方案 12 / 24 / 36 個月全週期比較,以及月化等效成本

設計守則:
  - 100% 純函式 stdlib,不依賴 numpy
  - 所有 NT$ 計算精確;LLM 永不算錢
  - 雇用成本含「員工面 hidden cost」(三節 / 年終 / 重招)— SME 老闆最常漏算
  - 外包成本含「廠商面 hidden cost」(對接時間 / 切換風險)— SME 老闆最常漏算

法定費率(2024-2025 公告值):
  - 健保(雇主負擔):5.17% × 投保薪資(每月最高投保 NT$182,000)
  - 勞保(雇主負擔含就業保險):10.5% × min(月薪, 最高 NT$45,800)
  - 勞退新制(雇主強制提繳):6% × min(月薪, NT$150,000)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ===== 法定費率 =====
NHI_EMPLOYER_RATE = 0.0517
NHI_INSURED_CAP = 182000
LI_EMPLOYER_RATE = 0.105
LI_INSURED_CAP = 45800
PENSION_RATE = 0.06
PENSION_INSURED_CAP = 150000

OWNER_HOURLY_RATE_DEFAULT = 1200  # SME 老闆預估時薪 NT$1,200


# ===== Profile dataclasses =====
@dataclass
class HireProfile:
    role_name: str
    monthly_salary: int
    horizon_years: int = 2
    annual_three_festivals: float = 1.0       # 三節獎金 ≈ 月薪 × N(SME 平均 1)
    annual_year_end: float = 1.5              # 年終 ≈ 月薪 × N(SME 平均 1-2)
    one_time_hire_cost: int = 15000           # 104/Yes123 廣告 + HR 時間
    one_time_training_months: float = 1.5     # 培訓 = 老闆 / 同事 mentor 1.5 月薪
    monthly_equipment_cost: int = 4000        # 筆電 / 軟體 / 工位
    one_year_turnover_rate: float = 0.30      # SME 一年內離職率 ~25-35%
    replacement_cost_months: float = 1.5      # 離職重招 = 1.5 月薪
    paid_leave_days: int = 7                  # 特休天數(影響有效工作天)


@dataclass
class OutsourceProfile:
    role_name: str
    monthly_fee: int                          # 外包基本月費
    horizon_years: int = 2
    management_hours_per_month: float = 4.0   # 老闆 / PM 對接 hours / 月
    owner_hourly_rate: int = OWNER_HOURLY_RATE_DEFAULT
    annual_switch_risk: float = 0.10          # 廠商出問題要換的年機率
    switching_cost_months: float = 2.0        # 切換廠商過渡 = 2 月費
    knowledge_loss_penalty: int = 50000       # 切換時 onbording + 知識遺失


# ===== 純函式計算 =====
def compute_hire_total_cost(p: HireProfile) -> dict:
    months = 12 * p.horizon_years
    salary_total = p.monthly_salary * months

    nhi_total = round(min(p.monthly_salary, NHI_INSURED_CAP) * NHI_EMPLOYER_RATE * months)
    li_total = round(min(p.monthly_salary, LI_INSURED_CAP) * LI_EMPLOYER_RATE * months)
    pension_total = round(min(p.monthly_salary, PENSION_INSURED_CAP) * PENSION_RATE * months)

    bonuses_total = round(p.monthly_salary * (p.annual_three_festivals + p.annual_year_end) * p.horizon_years)

    one_time_total = p.one_time_hire_cost + round(p.monthly_salary * p.one_time_training_months)

    equipment_total = p.monthly_equipment_cost * months

    # 重招風險:評估期內預估離職次數 = 1 年離職率 × 年數;每次重招 = 1.5 月薪 + 招聘成本
    expected_replacements = p.one_year_turnover_rate * p.horizon_years
    replacement_total = round(
        expected_replacements * (p.monthly_salary * p.replacement_cost_months + p.one_time_hire_cost)
    )

    total = (
        salary_total + nhi_total + li_total + pension_total +
        bonuses_total + one_time_total + equipment_total + replacement_total
    )

    return {
        "scheme": "招專員(in-house)",
        "horizon_years": p.horizon_years,
        "total_months": months,
        "breakdown": {
            "salary_base": salary_total,
            "nhi_employer (5.17%)": nhi_total,
            "labor_insurance_employer (10.5%)": li_total,
            "pension_mandatory (6%)": pension_total,
            "festivals_year_end_bonus": bonuses_total,
            "one_time_hire_training": one_time_total,
            "equipment_workstation": equipment_total,
            "expected_replacement_risk": replacement_total,
        },
        "total_cost": total,
        "monthly_effective_cost": round(total / months),
        "expected_replacements_count": round(expected_replacements, 2),
    }


def compute_outsource_total_cost(p: OutsourceProfile) -> dict:
    months = 12 * p.horizon_years
    base_total = p.monthly_fee * months

    management_total = round(p.management_hours_per_month * p.owner_hourly_rate * months)

    # 切換風險:評估期內預估切換次數 = 年切換機率 × 年數
    expected_switches = p.annual_switch_risk * p.horizon_years
    switch_total = round(
        expected_switches * (p.monthly_fee * p.switching_cost_months + p.knowledge_loss_penalty)
    )

    total = base_total + management_total + switch_total

    return {
        "scheme": "外包(outsource)",
        "horizon_years": p.horizon_years,
        "total_months": months,
        "breakdown": {
            "base_fee": base_total,
            "owner_management_time": management_total,
            "expected_switching_risk": switch_total,
        },
        "total_cost": total,
        "monthly_effective_cost": round(total / months),
        "expected_switches_count": round(expected_switches, 2),
    }


# ===== Comparison =====
@dataclass
class Comparison:
    hire_total: int
    outsource_total: int
    delta: int                                  # 正 = 外包貴於招專員;負 = 反之
    cheaper_scheme: str                         # "招專員" / "外包"
    delta_pct: float
    monthly_savings: int
    breakeven_horizon_years: float | None       # 若兩方案 NPV 在 X 年時打平
    qualitative_signals: list[str]              # 純函式產出的非價格警示


def compare(hire_summary: dict, outsource_summary: dict, hire_p: HireProfile, out_p: OutsourceProfile) -> Comparison:
    h = hire_summary["total_cost"]
    o = outsource_summary["total_cost"]
    delta = o - h
    cheaper = "招專員" if h < o else "外包"
    delta_pct = round(abs(delta) / max(h, o) * 100, 1)
    monthly_savings = round(abs(delta) / hire_summary["total_months"])

    # Breakeven:linear approximation — 若一方有大量 one-time cost,另一方 ramps 後可能反轉
    # 簡化:估算「不算 one-time + replacement」每月差距,看 one-time 差需要多久攤平
    hire_monthly_recurring = (
        hire_summary["breakdown"]["salary_base"]
        + hire_summary["breakdown"]["nhi_employer (5.17%)"]
        + hire_summary["breakdown"]["labor_insurance_employer (10.5%)"]
        + hire_summary["breakdown"]["pension_mandatory (6%)"]
        + hire_summary["breakdown"]["festivals_year_end_bonus"]
        + hire_summary["breakdown"]["equipment_workstation"]
    ) / hire_summary["total_months"]
    out_monthly_recurring = (
        outsource_summary["breakdown"]["base_fee"]
        + outsource_summary["breakdown"]["owner_management_time"]
    ) / outsource_summary["total_months"]

    hire_upfront = (
        hire_summary["breakdown"]["one_time_hire_training"]
        + hire_summary["breakdown"]["expected_replacement_risk"]
    )
    out_upfront = outsource_summary["breakdown"]["expected_switching_risk"]
    upfront_diff = hire_upfront - out_upfront
    recurring_diff_per_month = out_monthly_recurring - hire_monthly_recurring  # > 0 = 外包月費更貴

    breakeven_years: float | None = None
    if recurring_diff_per_month != 0 and (upfront_diff * recurring_diff_per_month < 0):
        # 反向才有 breakeven
        breakeven_months = abs(upfront_diff / recurring_diff_per_month)
        breakeven_years = round(breakeven_months / 12, 2)

    # Qualitative signals(純函式邏輯)
    signals: list[str] = []
    if hire_p.monthly_salary > 60000:
        signals.append(
            "雇用高薪職位(NT${} 月薪)→ 雇主負擔 5.17% 健保 + 10.5% 勞保 + 6% 勞退 = 約 22% 額外成本".format(
                hire_p.monthly_salary
            )
        )
    if out_p.management_hours_per_month >= 8:
        signals.append(
            "外包對接時間 {} hr/月 偏高,實際隱性成本 NT${}/月,可能侵蝕外包優勢".format(
                out_p.management_hours_per_month,
                round(out_p.management_hours_per_month * out_p.owner_hourly_rate),
            )
        )
    if hire_p.one_year_turnover_rate > 0.35:
        signals.append(
            "預估離職率 {:.0%} 偏高(SME 平均 25-35%),重招成本佔比可能高於評估"
            .format(hire_p.one_year_turnover_rate)
        )
    if hire_p.monthly_salary > out_p.monthly_fee * 2:
        signals.append(
            "雇用月薪 NT${} 是外包月費 NT${} 的 {:.1f} 倍,純成本應該選外包,但要評估「品質 / 速度 / 機密性」3 個 non-cost factors"
            .format(hire_p.monthly_salary, out_p.monthly_fee, hire_p.monthly_salary / out_p.monthly_fee)
        )
    if out_p.monthly_fee > hire_p.monthly_salary:
        signals.append(
            "外包月費 NT${} 已 ≥ 月薪 NT${},外包不再有成本優勢 — 除非「需要的技能稀有 / 短期需求 / 不想固定 headcount」"
            .format(out_p.monthly_fee, hire_p.monthly_salary)
        )

    return Comparison(
        hire_total=h,
        outsource_total=o,
        delta=delta,
        cheaper_scheme=cheaper,
        delta_pct=delta_pct,
        monthly_savings=monthly_savings,
        breakeven_horizon_years=breakeven_years,
        qualitative_signals=signals,
    )


def horizon_sensitivity(
    hire_p: HireProfile, out_p: OutsourceProfile, horizons: tuple[int, ...] = (1, 2, 3, 5)
) -> list[dict]:
    """跑多個 horizon 看趨勢(短期 vs 長期決策可能不同)。"""
    out: list[dict] = []
    for y in horizons:
        h_copy = HireProfile(**{**hire_p.__dict__, "horizon_years": y})
        o_copy = OutsourceProfile(**{**out_p.__dict__, "horizon_years": y})
        h_sum = compute_hire_total_cost(h_copy)
        o_sum = compute_outsource_total_cost(o_copy)
        c = compare(h_sum, o_sum, h_copy, o_copy)
        out.append({
            "horizon_years": y,
            "hire_total": h_sum["total_cost"],
            "outsource_total": o_sum["total_cost"],
            "cheaper": c.cheaper_scheme,
            "delta": c.delta,
            "delta_pct": c.delta_pct,
        })
    return out
