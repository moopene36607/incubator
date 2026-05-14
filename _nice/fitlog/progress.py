"""fitlog 跨堂進步追蹤 — 純函式比對 prev vs curr session (no I/O, no LLM).

PT 留學員的招牌話術:
  「上週你 47.5 kg 卡關 3 堂,本週直接 50 kg 完成,這就是 PR」

要做到這點,必須跨 session 比對同一個 exercise_code,計算:
- 重量 PR (curr top weight > prev top weight)
- 噸位 delta (同重量但組數/次數加 → 訓練量上升)

本輪只處理「兩堂課都做過 + 兩邊都有 weight_kg」的情況;BW 動作的進步追蹤
(reps PR for pull-up 等) 留下輪。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from exercise_db import lookup
from metrics import _format_kg, compute_total_tonnage

if TYPE_CHECKING:
    from fitlog import SetRecord


@dataclass(frozen=True)
class ProgressDelta:
    exercise_code: str
    prev_top_weight: float
    curr_top_weight: float
    weight_delta_kg: float
    prev_tonnage: float
    curr_tonnage: float
    tonnage_delta: float
    is_weight_pr: bool


@dataclass(frozen=True)
class BwRepsDelta:
    """Bodyweight 動作 (Pull-up / Dips / Push-up) 的 reps PR 追蹤。
    用 max single-set reps 為基準 (同 exercise 多 set 取最高那組)。"""
    exercise_code: str
    prev_top_reps: int
    curr_top_reps: int
    reps_delta: int
    is_reps_pr: bool


@dataclass(frozen=True)
class DurationDelta:
    """時間/距離型動作 (Plank / Row Erg / Treadmill) 的 PR 追蹤。
    單位限定 sec / min / m / km;同 exercise 取 max value 為 top。"""
    exercise_code: str
    unit: str
    prev_top_value: int
    curr_top_value: int
    delta: int
    is_pr: bool


# 只接受這些單位 (避免把 "5 reps/side" 之類的字串誤當 duration)
_DURATION_UNITS: frozenset[str] = frozenset({"sec", "min", "m", "km"})


def _top_weight(sets: Iterable["SetRecord"], code: str) -> float | None:
    """同 exercise 的 max weight_kg;全 BW 或無此 exercise → None。"""
    weights = [s.weight_kg for s in sets if s.exercise_code == code and s.weight_kg is not None]
    return max(weights) if weights else None


def _exercise_tonnage(sets: Iterable["SetRecord"], code: str) -> float:
    return compute_total_tonnage([s for s in sets if s.exercise_code == code])


def compute_pr_deltas(
    prev_sets: list["SetRecord"],
    curr_sets: list["SetRecord"],
) -> dict[str, ProgressDelta]:
    """跨堂比對。只計算「兩邊都有 + 兩邊都有 weight_kg」的 exercise。"""
    prev_codes = {s.exercise_code for s in prev_sets}
    curr_codes = {s.exercise_code for s in curr_sets}
    overlap = prev_codes & curr_codes

    deltas: dict[str, ProgressDelta] = {}
    for code in overlap:
        pw = _top_weight(prev_sets, code)
        cw = _top_weight(curr_sets, code)
        if pw is None or cw is None:
            # 一邊 BW 一邊加重 → 訓練性質改變,不對比
            continue
        pt = _exercise_tonnage(prev_sets, code)
        ct = _exercise_tonnage(curr_sets, code)
        deltas[code] = ProgressDelta(
            exercise_code=code,
            prev_top_weight=pw,
            curr_top_weight=cw,
            weight_delta_kg=cw - pw,
            prev_tonnage=pt,
            curr_tonnage=ct,
            tonnage_delta=ct - pt,
            is_weight_pr=cw > pw,
        )
    return deltas


def _top_reps_bw(sets: Iterable["SetRecord"], code: str) -> int | None:
    """同 exercise 的 BW set 中,max integer reps;沒任何 BW int-reps set → None。"""
    candidates: list[int] = []
    for s in sets:
        if s.exercise_code != code:
            continue
        if s.weight_kg is not None:
            continue  # 不是 BW
        s_reps = s.reps_or_duration.strip()
        if not s_reps.isdigit():
            continue  # 不是純整數 (時間/距離型跳過)
        candidates.append(int(s_reps))
    return max(candidates) if candidates else None


def compute_bw_reps_deltas(
    prev_sets: list["SetRecord"],
    curr_sets: list["SetRecord"],
) -> dict[str, BwRepsDelta]:
    """Bodyweight reps PR 追蹤。只計算「兩邊都做過 + 兩邊都是 BW int-reps」的 exercise。"""
    overlap = ({s.exercise_code for s in prev_sets}
               & {s.exercise_code for s in curr_sets})
    deltas: dict[str, BwRepsDelta] = {}
    for code in overlap:
        pr = _top_reps_bw(prev_sets, code)
        cr = _top_reps_bw(curr_sets, code)
        if pr is None or cr is None:
            continue
        deltas[code] = BwRepsDelta(
            exercise_code=code,
            prev_top_reps=pr,
            curr_top_reps=cr,
            reps_delta=cr - pr,
            is_reps_pr=cr > pr,
        )
    return deltas


def _parse_duration(raw: str) -> tuple[int, str] | None:
    """'60 sec' → (60, 'sec') / '500 m' → (500, 'm') / '5 reps/side' → None。"""
    parts = raw.strip().split()
    if len(parts) != 2:
        return None
    val_str, unit = parts
    if not val_str.isdigit() or unit not in _DURATION_UNITS:
        return None
    return int(val_str), unit


def _top_duration(sets: Iterable["SetRecord"], code: str) -> tuple[int, str] | None:
    """同 exercise 取 max duration value;單位不一致 → None (避免比較錯)。"""
    seen_unit: str | None = None
    candidates: list[int] = []
    for s in sets:
        if s.exercise_code != code:
            continue
        parsed = _parse_duration(s.reps_or_duration)
        if parsed is None:
            continue
        val, unit = parsed
        if seen_unit is None:
            seen_unit = unit
        elif seen_unit != unit:
            return None  # 單位不一致,放棄
        candidates.append(val)
    if not candidates or seen_unit is None:
        return None
    return max(candidates), seen_unit


def compute_duration_deltas(
    prev_sets: list["SetRecord"],
    curr_sets: list["SetRecord"],
) -> dict[str, DurationDelta]:
    """時間 / 距離型 PR 追蹤。"""
    overlap = ({s.exercise_code for s in prev_sets}
               & {s.exercise_code for s in curr_sets})
    deltas: dict[str, DurationDelta] = {}
    for code in overlap:
        prev = _top_duration(prev_sets, code)
        curr = _top_duration(curr_sets, code)
        if prev is None or curr is None:
            continue
        pv, pu = prev
        cv, cu = curr
        if pu != cu:
            continue  # 跨堂單位不同,不換算 (避免 60 sec vs 1 min 看不懂)
        deltas[code] = DurationDelta(
            exercise_code=code,
            unit=pu,
            prev_top_value=pv,
            curr_top_value=cv,
            delta=cv - pv,
            is_pr=cv > pv,
        )
    return deltas


def _format_weight(value: float) -> str:
    """50.0 → "50";47.5 → "47.5"。"""
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def _format_signed(value: float) -> str:
    """+2.5 / -2.5。整數時不顯示小數。"""
    sign = "+" if value > 0 else ""
    if value == int(value):
        return f"{sign}{int(value)}"
    return f"{sign}{value:.1f}"


def _format_one_bw(d: BwRepsDelta) -> str | None:
    if d.reps_delta == 0:
        return None
    name = (lookup(d.exercise_code).chinese
            if lookup(d.exercise_code) else d.exercise_code)
    suffix = " PR" if d.is_reps_pr else ""
    return (f"{name} {d.prev_top_reps}→{d.curr_top_reps} reps "
            f"({_format_signed(d.reps_delta)} reps{suffix})")


def _format_one_duration(d: DurationDelta) -> str | None:
    if d.delta == 0:
        return None
    name = (lookup(d.exercise_code).chinese
            if lookup(d.exercise_code) else d.exercise_code)
    suffix = " PR" if d.is_pr else ""
    return (f"{name} {d.prev_top_value}→{d.curr_top_value} {d.unit} "
            f"({_format_signed(d.delta)} {d.unit}{suffix})")


def _format_one_delta(d: ProgressDelta) -> str | None:
    """單筆 delta 的顯示。重量持平 + 噸位持平 → 沒進步可講,回 None。"""
    name = (lookup(d.exercise_code).chinese
            if lookup(d.exercise_code) else d.exercise_code)
    if d.weight_delta_kg != 0:
        suffix = " PR" if d.is_weight_pr else ""
        return (f"{name} {_format_weight(d.prev_top_weight)}→"
                f"{_format_weight(d.curr_top_weight)} kg "
                f"({_format_signed(d.weight_delta_kg)} kg{suffix})")
    if d.tonnage_delta != 0:
        return (f"{name} {_format_weight(d.curr_top_weight)} kg ↔ "
                f"(噸位 {_format_signed(d.tonnage_delta)} kg)")
    return None


def render_pr_summary(
    deltas: dict[str, ProgressDelta],
    bw_reps: dict[str, BwRepsDelta] | None = None,
    durations: dict[str, DurationDelta] | None = None,
) -> str | None:
    """**進步亮點**: 加權 PR + BW reps PR + 時間/距離 PR 串接。
    無交集 / 全持平 → None。
    順序:加權 (重量 desc) → BW (reps desc) → 時間/距離 (delta desc)。"""
    bw_reps = bw_reps or {}
    durations = durations or {}
    if not deltas and not bw_reps and not durations:
        return None

    weighted_items = sorted(
        deltas.values(),
        key=lambda d: (-d.weight_delta_kg, -d.tonnage_delta),
    )
    bw_items = sorted(bw_reps.values(), key=lambda d: -d.reps_delta)
    duration_items = sorted(durations.values(), key=lambda d: -d.delta)

    parts: list[str] = []
    for d in weighted_items:
        line = _format_one_delta(d)
        if line:
            parts.append(line)
    for d in bw_items:
        line = _format_one_bw(d)
        if line:
            parts.append(line)
    for d in duration_items:
        line = _format_one_duration(d)
        if line:
            parts.append(line)

    if not parts:
        return None
    return "**進步亮點**: " + " · ".join(parts)
