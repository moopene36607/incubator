"""motoval — 二手機車估價計算邏輯 (純函式).

估價公式(三層):
  1. base_value = MSRP × (1 - annual_depreciation)^age_years
  2. mileage_adjusted = base_value × mileage_factor
       mileage_factor = 1.0 + ((expected_total_km - actual_km) / expected_total_km) × 0.30
       上下限 [0.55, 1.20] 防止極端值
  3. condition_adjusted = mileage_adjusted × condition_multiplier
  4. final = condition_adjusted × (1 + Σ adjustment_factors)
       adjustment 累加上下限 [-0.30, +0.20]
  5. 市場區間 = final × [0.85, 1.15]  (±15% buyer / seller 議價空間)

所有數字計算純函式,絕不交給 LLM。
LLM 只負責:解析自由文字描述 → 結構化 input;產生估價說明文字。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from motorcycle_db import (
    ADJUSTMENT_FACTORS,
    CONDITION_MULTIPLIERS,
    MotorcycleModel,
)


@dataclass
class ValuationInput:
    model: MotorcycleModel
    year: int                       # 出廠年份
    mileage_km: int
    condition_rating: str           # "excellent" | "good" | "fair" | "poor"
    adjustments: list[str]          # ADJUSTMENT_FACTORS 的 keys
    valuation_year: int = 2026      # 估值參考年份(可指定,通常 == 今年)


@dataclass
class ValuationResult:
    midpoint_twd: int               # 估值中位
    range_low_twd: int              # 區間下限 (-15%)
    range_high_twd: int              # 區間上限 (+15%)
    dealer_acquisition_twd: int     # 車行收購價(扣 20% 利潤)
    dealer_acquisition_high_twd: int
    breakdown: dict[str, float]     # 折舊細節
    adjustment_explanations: list[tuple[str, float, str]]  # (key, delta, label)


# 加分減分 key 對應的中文說明
ADJUSTMENT_LABELS: dict[str, str] = {
    "single_owner":           "單一車主",
    "full_service_book":      "完整保養手冊",
    "dealer_serviced":        "原廠保養紀錄",
    "low_mileage":            "里程顯著低於同款平均",
    "new_tires":              "新胎",
    "minor_paint_damage":     "輕微漆面刮傷",
    "major_paint_damage":     "嚴重漆面 / 多處損傷",
    "engine_noise":           "引擎異音",
    "accident_history":       "事故車紀錄",
    "flooded":                "泡水車",
    "high_mileage":           "里程顯著高於同款平均",
    "missing_keys":           "鑰匙缺失",
    "outdated_inspection":    "行照 / 強制險過期",
}


def _round_to_500(value: float) -> int:
    return int(round(value / 500) * 500)


def calc_valuation(inp: ValuationInput) -> ValuationResult:
    if inp.year > inp.valuation_year:
        raise ValueError(f"year {inp.year} > valuation_year {inp.valuation_year}")
    if inp.mileage_km < 0:
        raise ValueError("mileage_km cannot be negative")
    if inp.condition_rating not in CONDITION_MULTIPLIERS:
        raise ValueError(f"condition {inp.condition_rating!r} not in {list(CONDITION_MULTIPLIERS)}")

    age_years = inp.valuation_year - inp.year

    # ---- step 1: 年份折舊 ----
    msrp = float(inp.model.msrp_twd)
    base_after_age = msrp * ((1.0 - inp.model.annual_depreciation_rate) ** age_years)

    # ---- step 2: 里程修正 ----
    expected_total_km = inp.model.expected_annual_km * max(age_years, 1)
    if expected_total_km > 0:
        delta_ratio = (expected_total_km - inp.mileage_km) / expected_total_km
        mileage_factor = 1.0 + delta_ratio * 0.30
    else:
        mileage_factor = 1.0
    mileage_factor = max(0.55, min(1.20, mileage_factor))
    after_mileage = base_after_age * mileage_factor

    # ---- step 3: 車況等級 ----
    cond_mult = CONDITION_MULTIPLIERS[inp.condition_rating]
    after_condition = after_mileage * cond_mult

    # ---- step 4: 細項加分減分 ----
    explanations: list[tuple[str, float, str]] = []
    total_adjustment = 0.0
    for key in inp.adjustments:
        delta = ADJUSTMENT_FACTORS.get(key)
        if delta is None:
            continue
        total_adjustment += delta
        explanations.append((key, delta, ADJUSTMENT_LABELS.get(key, key)))
    total_adjustment = max(-0.30, min(0.20, total_adjustment))
    final_value = after_condition * (1.0 + total_adjustment)

    # Sanity cap:二手車估值不能超過 MSRP × 0.95
    # (即使近新、保養好,buyer 仍會選擇付差價買新車 + 全新保固)
    final_value = min(final_value, msrp * 0.95)

    # ---- step 5: ±15% 區間 + 車行收購 (扣 20%) ----
    midpoint = _round_to_500(final_value)
    low = _round_to_500(final_value * 0.85)
    high = _round_to_500(final_value * 1.15)
    dealer_low = _round_to_500(final_value * 0.65)
    dealer_high = _round_to_500(final_value * 0.80)

    return ValuationResult(
        midpoint_twd=midpoint,
        range_low_twd=low,
        range_high_twd=high,
        dealer_acquisition_twd=dealer_low,
        dealer_acquisition_high_twd=dealer_high,
        breakdown={
            "msrp": msrp,
            "age_years": float(age_years),
            "annual_depreciation_rate": inp.model.annual_depreciation_rate,
            "after_age_depreciation": _round_to_500(base_after_age),
            "expected_total_km": float(expected_total_km),
            "mileage_factor": round(mileage_factor, 3),
            "after_mileage": _round_to_500(after_mileage),
            "condition_multiplier": cond_mult,
            "after_condition": _round_to_500(after_condition),
            "total_adjustment_pct": round(total_adjustment * 100, 1),
            "final": midpoint,
        },
        adjustment_explanations=explanations,
    )
