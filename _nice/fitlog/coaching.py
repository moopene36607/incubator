"""fitlog 教練建議 — 純函式根據 RPE 推算下次該加多少重量 (no LLM, no I/O).

PT 招牌可主動的事是「我幫你決定下次重量」。本模組根據台灣 / 國際健身圈
通用的「線性 RPE 推進」法則,純函式推算每個動作下次建議重量:

  RPE ≤ 6 (太輕鬆)    → +5 kg
  RPE 7  (尚有餘裕)   → +2.5 kg
  RPE 8-9 (剛好/略吃力) → 維持
  RPE 10 (力竭)       → deload -5 kg

設計準則:
- 純整數 RPE,沒填就跳過 (沒判斷依據,LLM 也不該瞎猜)
- BW 動作不適用 (BW 的進步靠 reps,不靠加重)
- 取每個 exercise 的最重 set 為基準 (PT 通常以最重組決定下次)
- 不負重 (deload 後不會變負值)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from exercise_db import lookup

if TYPE_CHECKING:
    from fitlog import SetRecord


@dataclass(frozen=True)
class WeightSuggestion:
    exercise_code: str
    curr_top_weight: float
    suggested_weight: float
    delta: float
    rationale: str


def suggest_next_weight(curr_weight_kg: float, rpe: int) -> float:
    """RPE-based 線性推進。回傳建議重量 (kg);不會回負值。"""
    if rpe <= 6:
        return curr_weight_kg + 5.0
    if rpe == 7:
        return curr_weight_kg + 2.5
    if rpe in (8, 9):
        return curr_weight_kg
    # RPE 10+ → deload
    return max(0.0, curr_weight_kg - 5.0)


def _rationale_for(rpe: int) -> str:
    if rpe <= 6:
        return f"RPE {rpe} 太輕鬆 → +5kg"
    if rpe == 7:
        return f"RPE {rpe} 尚有餘裕 → +2.5kg"
    if rpe in (8, 9):
        return f"RPE {rpe} 目標區 → 維持"
    return f"RPE {rpe} 力竭 → deload -5kg"


def suggest_next_session_weights(
    sets: Iterable["SetRecord"],
) -> dict[str, WeightSuggestion]:
    """每個 weighted exercise 取「重量最大且有 RPE 標記」的 set 為基準,推算下次。"""
    by_code: dict[str, list["SetRecord"]] = {}
    for s in sets:
        by_code.setdefault(s.exercise_code, []).append(s)
    suggestions: dict[str, WeightSuggestion] = {}
    for code, items in by_code.items():
        candidates = [s for s in items
                      if s.weight_kg is not None and s.rpe is not None]
        if not candidates:
            continue
        top = max(candidates, key=lambda s: s.weight_kg or 0.0)
        rpe = top.rpe  # type: ignore[assignment]
        curr_w = top.weight_kg  # type: ignore[assignment]
        suggested = suggest_next_weight(curr_w, rpe)
        suggestions[code] = WeightSuggestion(
            exercise_code=code,
            curr_top_weight=curr_w,
            suggested_weight=suggested,
            delta=suggested - curr_w,
            rationale=_rationale_for(rpe),
        )
    return suggestions


def _format_weight(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def render_next_weight_suggestions(
    suggestions: dict[str, WeightSuggestion],
) -> str | None:
    """**下次建議重量**: A 47.5→50 kg (RPE 7 ...) · B 50 kg 維持 (RPE 8 ...)"""
    if not suggestions:
        return None
    items = sorted(suggestions.values(), key=lambda s: -s.delta)
    parts: list[str] = []
    for s in items:
        name = (lookup(s.exercise_code).chinese
                if lookup(s.exercise_code) else s.exercise_code)
        if s.delta == 0:
            parts.append(f"{name} {_format_weight(s.curr_top_weight)} kg 維持 ({s.rationale})")
        else:
            parts.append(f"{name} {_format_weight(s.curr_top_weight)}→"
                         f"{_format_weight(s.suggested_weight)} kg ({s.rationale})")
    return "**下次建議重量**: " + " · ".join(parts)
