"""shiftsync — 餐廳排班規則檢查 (純函式,no I/O, no LLM).

責任:
  - 載入本週班表
  - 三類請求驗證:換班 (swap)、請假 (leave)、加班 (extra)
  - 每類驗證輸出統一的 ApprovalResult(approved / needs_replacement / rejected + 原因)

LLM 的責任在另一個檔案(shiftsync.py 的 ai_parse_request),
從非結構化 LINE 文字 → 結構化請求。本檔案完全不碰 LLM,確保
排班規則可單元測試、可重現。

法規依據:勞基法第 30 條 — 每日工作不得超過 12 小時(含加班),
每週工時不得超過 40 小時(常態)。本 prototype 採取保守標準。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


# 法定工時上限(本 prototype 採保守值)
WEEKLY_HOURS_LIMIT = 40.0       # 一般工時(不含彈性加班)
WEEKLY_HOURS_HARD_LIMIT = 48.0  # 含加班絕對上限
DAILY_HOURS_LIMIT = 12.0        # 含加班


@dataclass
class Employee:
    name: str
    role: str                                  # "店長" | "外場" | "內場" | "收銀+外場"
    is_full_time: bool = False
    target_weekly_hours: float = 24.0           # 兼職目標時數
    can_substitute_for: tuple[str, ...] = ()    # 可代班的角色清單


@dataclass
class Shift:
    shift_id: str          # "TUE_LUNCH" / "FRI_DINNER" 等
    day: str               # "週一" ~ "週日"
    start_time: str        # "11:00"
    end_time: str          # "15:00"
    duration_hours: float
    role_required: str     # 必要角色
    assigned_to: str | None = None     # 員工姓名或 None


@dataclass
class ApprovalResult:
    status: str                # "approved" | "approved_with_warning" | "needs_replacement" | "rejected"
    summary: str               # 一句話結論
    reasons: list[str] = field(default_factory=list)
    suggested_replacements: list[str] = field(default_factory=list)
    rule_violations: list[str] = field(default_factory=list)


def _weekly_hours(employee_name: str, shifts: list[Shift]) -> float:
    return sum(s.duration_hours for s in shifts if s.assigned_to == employee_name)


def _shifts_for(employee_name: str, shifts: list[Shift]) -> list[Shift]:
    return [s for s in shifts if s.assigned_to == employee_name]


def _shift_by_id(shifts: list[Shift], shift_id: str) -> Shift | None:
    return next((s for s in shifts if s.shift_id == shift_id), None)


def check_swap(shifts: list[Shift], employees: dict[str, Employee],
               emp_a: str, shift_a_id: str,
               emp_b: str, shift_b_id: str) -> ApprovalResult:
    """檢查 emp_a 的 shift_a 與 emp_b 的 shift_b 是否可換班。"""
    sa = _shift_by_id(shifts, shift_a_id)
    sb = _shift_by_id(shifts, shift_b_id)
    reasons: list[str] = []
    violations: list[str] = []

    if sa is None or sb is None:
        return ApprovalResult(status="rejected", summary="找不到指定的班次",
                              rule_violations=[f"shift_id 無效: {shift_a_id} / {shift_b_id}"])
    if sa.assigned_to != emp_a:
        return ApprovalResult(status="rejected",
                              summary=f"{emp_a} 不在 {shift_a_id} 班次上",
                              rule_violations=[f"{shift_a_id} 是 {sa.assigned_to} 的班"])
    if sb.assigned_to != emp_b:
        return ApprovalResult(status="rejected",
                              summary=f"{emp_b} 不在 {shift_b_id} 班次上",
                              rule_violations=[f"{shift_b_id} 是 {sb.assigned_to} 的班"])

    e_a = employees.get(emp_a)
    e_b = employees.get(emp_b)
    if not (e_a and e_b):
        return ApprovalResult(status="rejected", summary="員工資料不完整",
                              rule_violations=["未註冊員工"])

    # 角色相容檢查 — 換班後對方要能撐另一邊的角色
    if sa.role_required not in (e_b.role, *e_b.can_substitute_for):
        violations.append(f"{emp_b} (角色 {e_b.role}) 不符合 {shift_a_id} 所需的 {sa.role_required}")
    if sb.role_required not in (e_a.role, *e_a.can_substitute_for):
        violations.append(f"{emp_a} (角色 {e_a.role}) 不符合 {shift_b_id} 所需的 {sb.role_required}")

    # 模擬換班後的工時 (淨變動為 0,因為兩人各失去自己原本一班、增加對方的班 — 但時數可能不同)
    new_a_hours = _weekly_hours(emp_a, shifts) - sa.duration_hours + sb.duration_hours
    new_b_hours = _weekly_hours(emp_b, shifts) - sb.duration_hours + sa.duration_hours

    if new_a_hours > WEEKLY_HOURS_HARD_LIMIT:
        violations.append(f"{emp_a} 換後工時 {new_a_hours:.1f}h 超過絕對上限 {WEEKLY_HOURS_HARD_LIMIT}h")
    elif new_a_hours > WEEKLY_HOURS_LIMIT:
        reasons.append(f"⚠️ {emp_a} 換後工時 {new_a_hours:.1f}h 進入加班範圍 (>{WEEKLY_HOURS_LIMIT}h)")

    if new_b_hours > WEEKLY_HOURS_HARD_LIMIT:
        violations.append(f"{emp_b} 換後工時 {new_b_hours:.1f}h 超過絕對上限 {WEEKLY_HOURS_HARD_LIMIT}h")
    elif new_b_hours > WEEKLY_HOURS_LIMIT:
        reasons.append(f"⚠️ {emp_b} 換後工時 {new_b_hours:.1f}h 進入加班範圍 (>{WEEKLY_HOURS_LIMIT}h)")

    # 雙人同日衝突檢查
    a_shifts_after = [s for s in _shifts_for(emp_a, shifts) if s.shift_id != shift_a_id] + [sb]
    b_shifts_after = [s for s in _shifts_for(emp_b, shifts) if s.shift_id != shift_b_id] + [sa]
    for emp_label, after_shifts in (("a", a_shifts_after), ("b", b_shifts_after)):
        emp_name = emp_a if emp_label == "a" else emp_b
        for day in {s.day for s in after_shifts}:
            day_shifts = [s for s in after_shifts if s.day == day]
            if len(day_shifts) <= 1:
                continue
            for i, s1 in enumerate(day_shifts):
                for s2 in day_shifts[i + 1:]:
                    if s1.start_time < s2.end_time and s2.start_time < s1.end_time:
                        violations.append(
                            f"{emp_name} 在 {day} 換後出現同日重疊班 "
                            f"({s1.shift_id} 與 {s2.shift_id})"
                        )
                        break

    if violations:
        return ApprovalResult(status="rejected", summary="換班不符合規則",
                              reasons=reasons, rule_violations=violations)
    if reasons:
        return ApprovalResult(status="approved_with_warning", summary="可換但需注意加班規則",
                              reasons=reasons)
    return ApprovalResult(status="approved", summary=f"{emp_a} 與 {emp_b} 換班核准",
                          reasons=[f"{emp_a} 工時 {new_a_hours:.1f}h",
                                   f"{emp_b} 工時 {new_b_hours:.1f}h"])


def check_leave(shifts: list[Shift], employees: dict[str, Employee],
                emp: str, shift_id: str) -> ApprovalResult:
    """檢查 emp 請假該班 → 找出可代班的人選。"""
    s = _shift_by_id(shifts, shift_id)
    if s is None:
        return ApprovalResult(status="rejected", summary="找不到指定班次",
                              rule_violations=[f"shift_id {shift_id} 無效"])
    if s.assigned_to != emp:
        return ApprovalResult(status="rejected",
                              summary=f"{emp} 不在 {shift_id} 班次上",
                              rule_violations=[f"{shift_id} 是 {s.assigned_to} 的班"])

    # 找:未在該班 + 角色相容 + 加上該班後不超 hard limit
    candidates: list[str] = []
    for name, e in employees.items():
        if name == emp:
            continue
        if s.role_required not in (e.role, *e.can_substitute_for):
            continue
        # 同日已有班 → 跳過(避免重疊)
        same_day = [shift for shift in _shifts_for(name, shifts) if shift.day == s.day]
        if any(s1.start_time < s.end_time and s.start_time < s1.end_time for s1 in same_day):
            continue
        new_hours = _weekly_hours(name, shifts) + s.duration_hours
        if new_hours > WEEKLY_HOURS_HARD_LIMIT:
            continue
        candidates.append(name)

    if not candidates:
        return ApprovalResult(status="rejected",
                              summary=f"{emp} 請假被拒:沒有可代班人選",
                              rule_violations=["所有員工皆衝突或角色不符"])

    return ApprovalResult(status="needs_replacement",
                          summary=f"{emp} 請假已記錄,有 {len(candidates)} 位可代班人選",
                          suggested_replacements=candidates)


def check_extra_shift(shifts: list[Shift], employees: dict[str, Employee],
                      emp: str, shift_id: str) -> ApprovalResult:
    """員工想加班(把空班 / 別人的班接過來)。"""
    s = _shift_by_id(shifts, shift_id)
    if s is None:
        return ApprovalResult(status="rejected", summary="找不到指定班次",
                              rule_violations=[f"shift_id {shift_id} 無效"])
    e = employees.get(emp)
    if not e:
        return ApprovalResult(status="rejected", summary="員工資料不存在",
                              rule_violations=[f"未註冊員工 {emp}"])
    if s.assigned_to is not None and s.assigned_to != emp:
        return ApprovalResult(
            status="rejected",
            summary=f"該班次已由 {s.assigned_to} 排定,需走換班流程",
            rule_violations=[f"{shift_id} 已分配給 {s.assigned_to}"],
        )

    # 角色檢查
    if s.role_required not in (e.role, *e.can_substitute_for):
        return ApprovalResult(
            status="rejected",
            summary=f"{emp} 角色 {e.role} 不符合此班需要的 {s.role_required}",
            rule_violations=[f"角色不相容"],
        )
    # 同日衝突
    same_day = [shift for shift in _shifts_for(emp, shifts) if shift.day == s.day]
    if any(s1.start_time < s.end_time and s.start_time < s1.end_time for s1 in same_day):
        return ApprovalResult(
            status="rejected",
            summary=f"{emp} 在 {s.day} 已有重疊班次",
            rule_violations=["同日重疊"],
        )
    # 工時上限
    new_hours = _weekly_hours(emp, shifts) + s.duration_hours
    reasons: list[str] = []
    if new_hours > WEEKLY_HOURS_HARD_LIMIT:
        return ApprovalResult(
            status="rejected",
            summary=f"{emp} 加班後工時 {new_hours:.1f}h 超過絕對上限 {WEEKLY_HOURS_HARD_LIMIT}h",
            rule_violations=["週工時超過 48h hard limit"],
        )
    if new_hours > WEEKLY_HOURS_LIMIT:
        reasons.append(f"⚠️ 加班後 {new_hours:.1f}h 進入加班範圍 (>{WEEKLY_HOURS_LIMIT}h),需依勞基法計算加班費")
        return ApprovalResult(
            status="approved_with_warning",
            summary=f"{emp} 加班可批,需注意加班費計算",
            reasons=reasons,
        )
    return ApprovalResult(
        status="approved",
        summary=f"{emp} 加班核准 (新週工時 {new_hours:.1f}h)",
        reasons=[f"當前 {_weekly_hours(emp, shifts):.1f}h + 此班 {s.duration_hours}h = {new_hours:.1f}h"],
    )
