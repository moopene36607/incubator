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


def _format_weight(value: float) -> str:
    """50.0 → "50";47.5 → "47.5"。"""
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def _format_signed(value: float) -> str:
    """+2.5 / -2.5。整數時不顯示小數。"""
    sign = "+" if value > 0 else ""
    if value == int(value):
        return f"{sign}{int(value)}"
    return f"{sign}{value:.1f}"


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


def render_pr_summary(deltas: dict[str, ProgressDelta]) -> str | None:
    """**進步亮點**: A 47.5→50 kg (+2.5 kg PR) · B 65→70 kg (+5 kg PR)
    無交集 / 全持平 → None。排序: 重量 delta 由大到小,再以噸位 delta 為次序。"""
    if not deltas:
        return None
    items = sorted(
        deltas.values(),
        key=lambda d: (-d.weight_delta_kg, -d.tonnage_delta),
    )
    parts: list[str] = []
    for d in items:
        line = _format_one_delta(d)
        if line:
            parts.append(line)
    if not parts:
        return None
    return "**進步亮點**: " + " · ".join(parts)
