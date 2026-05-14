"""fitlog metrics — 純函式計算訓練量化指標 (no I/O, no LLM).

依照專案規範:金錢 / 體重 / 體脂 / 重量 / 訓練量等數字一律由純 Python
函數計算,LLM 絕不能自己「猜一個」訓練 tonnage。

tonnage = Σ (組數 × 次數 × 重量 kg)

只計算 weight_kg 不為 None 且 reps_or_duration 是純整數的紀錄;
bodyweight (e.g. Pull-up) / 時間型 (60 sec) / 距離型 (500 m) 一律排除,
因為它們的訓練量需用其他指標 (時間總和、距離總和) 表達。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from fitlog import SetRecord


def _parse_reps(reps_or_duration: str) -> int | None:
    """純整數字串 → int;其他 (含 '60 sec', '500 m') 一律回 None。"""
    s = reps_or_duration.strip()
    if s.isdigit():
        return int(s)
    return None


def compute_total_tonnage(sets: Iterable["SetRecord"]) -> float:
    """計算本堂課總噸位 (kg)。只算有重量且 reps 是整數的紀錄。"""
    total = 0.0
    for s in sets:
        if s.weight_kg is None:
            continue
        reps = _parse_reps(s.reps_or_duration)
        if reps is None:
            continue
        total += float(s.sets) * float(reps) * float(s.weight_kg)
    return total


def _format_kg(value: float) -> str:
    # 整數值不顯示小數;非整數保留一位小數。永遠加千位逗號。
    if value == int(value):
        return f"{int(value):,} kg"
    return f"{value:,.1f} kg"


def render_volume_summary(sets: Iterable["SetRecord"]) -> str | None:
    """回傳「**訓練總噸位**: X kg」一行字串;若無加權 set 則回 None
    (顯示 0 kg 反而誤導學員以為今天沒練到)。"""
    total = compute_total_tonnage(sets)
    if total <= 0:
        return None
    return f"**訓練總噸位**: {_format_kg(total)}"


# 顯示用的中文分類標籤;與 exercise_db.Exercise.category 對應。
CATEGORY_ZH: dict[str, str] = {
    "legs": "腿系",
    "pull": "拉系",
    "push": "推系",
    "core": "核心",
    "cardio": "心肺",
    "mobility": "活動度",
}


def compute_category_tonnage(sets: Iterable["SetRecord"]) -> dict[str, float]:
    """按 exercise_db 分類加總噸位。未知 exercise_code 直接跳過,不歸到
    "unknown" bucket (避免污染分類顯示)。"""
    from exercise_db import lookup
    breakdown: dict[str, float] = {}
    for s in sets:
        if s.weight_kg is None:
            continue
        reps = _parse_reps(s.reps_or_duration)
        if reps is None:
            continue
        ex = lookup(s.exercise_code)
        if ex is None:
            continue
        v = float(s.sets) * float(reps) * float(s.weight_kg)
        breakdown[ex.category] = breakdown.get(ex.category, 0.0) + v
    return breakdown


def render_category_breakdown(sets: Iterable["SetRecord"]) -> str | None:
    """回傳「**訓練量分解**: 腿系 4,600 kg · 推系 1,600 kg」(由高到低排)。
    無加權 set → None。"""
    breakdown = compute_category_tonnage(sets)
    if not breakdown:
        return None
    items = sorted(breakdown.items(), key=lambda kv: -kv[1])
    parts = [f"{CATEGORY_ZH.get(cat, cat)} {_format_kg(v)}" for cat, v in items]
    return "**訓練量分解**: " + " · ".join(parts)
