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
