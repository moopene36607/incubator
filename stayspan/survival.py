"""stayspan — 員工 retention 時間分析 (Kaplan-Meier + cohort hazard) 純函式 / no I/O / no LLM.

責任:
  - 從員工 retention 紀錄(tenure_months + event_observed)算 Kaplan-Meier 留任曲線
  - 中位數留任期間(median tenure)
  - 12 / 18 / 24 / 36 月留任率
  - 各 cohort(部門 / 職級 / 績效)的 KM 比較 + 一年留任率
  - 找出「最危險 cohort」(12 月留任率最低)+「最穩定 cohort」

100% stdlib(只用 statistics + dataclass)。
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class EmployeeRecord:
    employee_id: str
    tenure_months: int                  # 任職月數(離職員工=任職總長;在職員工=至今)
    event_observed: bool                # True = 已離職;False = 在職(censored)
    department: str                     # Engineering / Marketing / Sales / Ops
    level: str                          # Junior / Mid / Senior
    performance_tier: str               # Low / Mid / High


def load_csv(path: str) -> list[EmployeeRecord]:
    records: list[EmployeeRecord] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(EmployeeRecord(
                employee_id=row["employee_id"].strip(),
                tenure_months=int(row["tenure_months"]),
                event_observed=row["event_observed"].strip().lower() in ("true", "1", "y", "yes"),
                department=row["department"].strip(),
                level=row["level"].strip(),
                performance_tier=row["performance_tier"].strip(),
            ))
    return records


# ===== Kaplan-Meier curve =====
@dataclass
class KMPoint:
    """KM 曲線上的一個點。"""
    time_months: int
    n_at_risk: int
    n_events: int
    n_censored_since_last: int
    survival_prob: float


def compute_kaplan_meier(records: list[EmployeeRecord]) -> list[KMPoint]:
    """計算 Kaplan-Meier 留任曲線。

    KM estimator: S(t) = ∏ (1 - d_i / n_i) for all event times t_i ≤ t
    where d_i = events at time t_i, n_i = at risk just before t_i.
    """
    if not records:
        return []

    # 收集所有 unique event times(只在 event 時間更新 S)
    event_times = sorted(set(r.tenure_months for r in records if r.event_observed))

    # 對每個 event time 計算
    points: list[KMPoint] = [KMPoint(time_months=0, n_at_risk=len(records), n_events=0,
                                      n_censored_since_last=0, survival_prob=1.0)]
    last_time = 0
    s = 1.0
    for t in event_times:
        n_at_risk = sum(1 for r in records if r.tenure_months >= t)
        n_events = sum(1 for r in records if r.tenure_months == t and r.event_observed)
        n_censored_since_last = sum(1 for r in records
                                     if last_time < r.tenure_months < t and not r.event_observed)
        if n_at_risk == 0:
            break
        s = s * (n_at_risk - n_events) / n_at_risk
        points.append(KMPoint(
            time_months=t,
            n_at_risk=n_at_risk,
            n_events=n_events,
            n_censored_since_last=n_censored_since_last,
            survival_prob=round(s, 4),
        ))
        last_time = t
    return points


def survival_at(points: list[KMPoint], t: int) -> float:
    """查詢時刻 t 的存活率(對應「在公司 t 月以上」的機率)。"""
    if not points:
        return 0.0
    s = 1.0
    for p in points:
        if p.time_months <= t:
            s = p.survival_prob
        else:
            break
    return s


def median_tenure(points: list[KMPoint]) -> int | None:
    """中位數留任 = 首個 S(t) ≤ 0.5 的時間。"""
    for p in points:
        if p.survival_prob <= 0.5:
            return p.time_months
    return None  # 留任率始終 > 0.5,中位數 > 觀察期(censored)


# ===== Cohort analysis =====
@dataclass
class CohortSurvival:
    feature: str                        # 'department' / 'level' / 'performance_tier'
    group_value: str                    # e.g. 'Engineering' / 'Junior' / 'Low'
    n_employees: int
    n_left: int
    n_still: int
    survival_12mo: float                # 12 月留任率
    survival_24mo: float                # 24 月留任率
    median_tenure: int | None           # 中位數留任(可能 None)
    points: list[KMPoint] = field(default_factory=list)


def cohort_survival(records: list[EmployeeRecord], feature: str) -> list[CohortSurvival]:
    """按 feature(department / level / performance_tier)分群跑 KM。"""
    groups: dict[str, list[EmployeeRecord]] = {}
    for r in records:
        groups.setdefault(getattr(r, feature), []).append(r)

    out: list[CohortSurvival] = []
    for value, group_records in groups.items():
        if not group_records:
            continue
        points = compute_kaplan_meier(group_records)
        out.append(CohortSurvival(
            feature=feature,
            group_value=value,
            n_employees=len(group_records),
            n_left=sum(1 for r in group_records if r.event_observed),
            n_still=sum(1 for r in group_records if not r.event_observed),
            survival_12mo=round(survival_at(points, 12), 4),
            survival_24mo=round(survival_at(points, 24), 4),
            median_tenure=median_tenure(points),
            points=points,
        ))
    # 排序 by survival_12mo(最低先 = 最危險)
    out.sort(key=lambda c: c.survival_12mo)
    return out


# ===== Hazard ratio (簡化) =====
@dataclass
class HazardComparison:
    feature: str
    group_high_risk: str                # 12 月留任率最低
    group_low_risk: str                 # 12 月留任率最高
    survival_high_risk_12mo: float
    survival_low_risk_12mo: float
    hazard_ratio: float                 # (1 - S_high) / (1 - S_low) — 簡化版 hazard ratio
    interpretation: str


def compare_cohorts(cohorts: list[CohortSurvival]) -> HazardComparison | None:
    """從 cohorts 找最高 vs 最低 risk 對比。"""
    if len(cohorts) < 2:
        return None
    high_risk = cohorts[0]      # 最低 12 月 survival = 最高離職風險
    low_risk = cohorts[-1]      # 最高 12 月 survival = 最低離職風險

    p_left_high = 1 - high_risk.survival_12mo
    p_left_low = 1 - low_risk.survival_12mo
    if p_left_low == 0:
        hazard_ratio = float("inf") if p_left_high > 0 else 1.0
    else:
        hazard_ratio = round(p_left_high / p_left_low, 2)

    feature_zh = {"department": "部門", "level": "職級", "performance_tier": "績效"}.get(
        high_risk.feature, high_risk.feature)
    interp = (
        f"在「{feature_zh}」維度,{high_risk.group_value} 員工 12 月離職機率"
        f"({p_left_high*100:.0f}%)是 {low_risk.group_value} ({p_left_low*100:.0f}%) "
        f"的 {hazard_ratio}x。"
    )
    return HazardComparison(
        feature=high_risk.feature,
        group_high_risk=high_risk.group_value,
        group_low_risk=low_risk.group_value,
        survival_high_risk_12mo=high_risk.survival_12mo,
        survival_low_risk_12mo=low_risk.survival_12mo,
        hazard_ratio=hazard_ratio,
        interpretation=interp,
    )


# ===== Top-level analysis =====
@dataclass
class SurvivalAnalysis:
    n_total: int
    n_left: int
    n_still: int
    overall_km: list[KMPoint]
    overall_median_tenure: int | None
    overall_survival_12mo: float
    overall_survival_24mo: float
    overall_survival_36mo: float
    by_department: list[CohortSurvival]
    by_level: list[CohortSurvival]
    by_performance: list[CohortSurvival]
    dept_hazard: HazardComparison | None
    level_hazard: HazardComparison | None
    perf_hazard: HazardComparison | None


def analyze(records: list[EmployeeRecord]) -> SurvivalAnalysis:
    points = compute_kaplan_meier(records)
    by_dept = cohort_survival(records, "department")
    by_level = cohort_survival(records, "level")
    by_perf = cohort_survival(records, "performance_tier")

    return SurvivalAnalysis(
        n_total=len(records),
        n_left=sum(1 for r in records if r.event_observed),
        n_still=sum(1 for r in records if not r.event_observed),
        overall_km=points,
        overall_median_tenure=median_tenure(points),
        overall_survival_12mo=round(survival_at(points, 12), 4),
        overall_survival_24mo=round(survival_at(points, 24), 4),
        overall_survival_36mo=round(survival_at(points, 36), 4),
        by_department=by_dept,
        by_level=by_level,
        by_performance=by_perf,
        dept_hazard=compare_cohorts(by_dept),
        level_hazard=compare_cohorts(by_level),
        perf_hazard=compare_cohorts(by_perf),
    )
