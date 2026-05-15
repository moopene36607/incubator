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
    from fitlog import SessionInput, SetRecord


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


# Epley 1RM 估算的 reps 上限 (>12 reps 公式不可靠;業界共識)
_EPLEY_REPS_CAP = 12

# Deload 偵測閾值: 近 N 堂平均 RPE >= threshold → 建議 deload (降量週)
DELOAD_MIN_SESSIONS = 3
DELOAD_RPE_THRESHOLD = 8.5


# 動作分類失衡偵測:近 N 堂 + 單分類占 >= 閾值 → 警告
IMBALANCE_WINDOW = 3
IMBALANCE_THRESHOLD = 0.7

# 偏向某分類時建議補哪些 (基於 push/pull/leg 對抗肌群與大肌群覆蓋邏輯)
_IMBALANCE_SUGGESTIONS = {
    "push": ["pull", "legs"],
    "pull": ["push", "legs"],
    "legs": ["push", "pull"],
    "core": ["legs", "push"],
    "cardio": ["legs", "push"],
    "mobility": ["legs", "push"],
}


@dataclass(frozen=True)
class ImbalanceWarning:
    """近期訓練單一分類占比過高的警示。"""
    dominant_category: str
    dominant_pct: float
    suggested_categories: list[str]


def detect_imbalance_warning(
    sessions: Iterable["SessionInput"],
    student_name: str,
    current_session: "SessionInput",
    window: int = IMBALANCE_WINDOW,
) -> ImbalanceWarning | None:
    """偵測該學員近 N 堂 (含當堂) 訓練分類分布,單一分類占 >= 閾值 → 警告。"""
    from metrics import compute_category_tonnage
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    cur_key = (current_session.session_date, current_session.session_no)
    relevant = [s for s in student_sessions
                if (s.session_date, s.session_no) <= cur_key]
    if len(relevant) < window:
        return None
    recent = relevant[-window:]

    per_cat: dict[str, float] = {}
    for sess in recent:
        for cat, t in compute_category_tonnage(sess.sets).items():
            per_cat[cat] = per_cat.get(cat, 0.0) + t

    total = sum(per_cat.values())
    if total <= 0:
        return None

    dominant_cat, dominant_t = max(per_cat.items(), key=lambda kv: kv[1])
    dominant_pct = dominant_t / total
    if dominant_pct < IMBALANCE_THRESHOLD:
        return None

    return ImbalanceWarning(
        dominant_category=dominant_cat,
        dominant_pct=dominant_pct,
        suggested_categories=_IMBALANCE_SUGGESTIONS.get(dominant_cat, []),
    )


def render_imbalance_warning(w: ImbalanceWarning | None) -> str:
    """產出「⚠️ 動作分類失衡」單段 markdown。None → ""。"""
    if w is None:
        return ""
    from metrics import CATEGORY_ZH
    name = CATEGORY_ZH.get(w.dominant_category, w.dominant_category)
    suggested = " / ".join(
        CATEGORY_ZH.get(c, c) for c in w.suggested_categories
    ) or "其他分類"
    return (f"⚠️ **動作分類失衡**:近 {IMBALANCE_WINDOW} 堂"
            f"{name}佔 {w.dominant_pct:.0%},建議下次補 {suggested}。")


@dataclass(frozen=True)
class DeloadSignal:
    """近期過度訓練訊號 — 建議下次 deload。"""
    avg_rpe: float
    n_recent_sessions: int


def _avg_rpe_for_session(session: "SessionInput") -> float | None:
    """Avg RPE across all sets that have RPE。沒任何 set 有 RPE → None。"""
    rpes = [s.rpe for s in session.sets if s.rpe is not None]
    if not rpes:
        return None
    return sum(rpes) / len(rpes)


def detect_deload_signal(
    sessions: Iterable["SessionInput"],
    student_name: str,
    current_session: "SessionInput",
) -> DeloadSignal | None:
    """看該學員到當堂為止的最近 N 堂 (含當堂),avg RPE >= 閾值 → signal。
    不足 N 堂或低 avg → None。"""
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    cur_key = (current_session.session_date, current_session.session_no)
    relevant = [s for s in student_sessions
                if (s.session_date, s.session_no) <= cur_key]
    if len(relevant) < DELOAD_MIN_SESSIONS:
        return None
    recent = relevant[-DELOAD_MIN_SESSIONS:]
    avg_rpes = [_avg_rpe_for_session(s) for s in recent]
    avg_rpes = [a for a in avg_rpes if a is not None]
    if len(avg_rpes) < DELOAD_MIN_SESSIONS:
        return None
    overall = sum(avg_rpes) / len(avg_rpes)
    if overall < DELOAD_RPE_THRESHOLD:
        return None
    return DeloadSignal(avg_rpe=overall, n_recent_sessions=len(avg_rpes))


def render_deload_banner(signal: DeloadSignal | None) -> str:
    """產出「📉 建議下次 deload」單段 markdown。None → ""。"""
    if signal is None:
        return ""
    return (f"📉 **建議下次 deload**:近 {signal.n_recent_sessions} 堂"
            f"平均 RPE {signal.avg_rpe:.1f},高於建議閾值 "
            f"{DELOAD_RPE_THRESHOLD:.1f},降量讓身體恢復。")


def estimate_1rm(weight_kg: float, reps: int) -> float | None:
    """Epley 公式: 1RM = weight × (1 + reps/30)。
    reps 不在 [1, 12] 或重量 <= 0 → None (公式不可靠 / 無意義)。"""
    if weight_kg <= 0:
        return None
    if reps < 1 or reps > _EPLEY_REPS_CAP:
        return None
    return weight_kg * (1.0 + reps / 30.0)


def compute_session_1rm_estimates(
    sets: Iterable["SetRecord"],
) -> dict[str, float]:
    """每個 weighted exercise 取「最高估計 1RM」的 set 為代表。BW / 時間型
    跳過 (沒重量可估或 reps 不可解析)。"""
    result: dict[str, float] = {}
    for s in sets:
        if s.weight_kg is None:
            continue
        reps_str = s.reps_or_duration.strip()
        if not reps_str.isdigit():
            continue
        est = estimate_1rm(s.weight_kg, int(reps_str))
        if est is None:
            continue
        cur = result.get(s.exercise_code)
        if cur is None or est > cur:
            result[s.exercise_code] = est
    return result


def render_1rm_estimates(estimates: dict[str, float]) -> str | None:
    """**估計 1RM (Epley)**: A ~ 60 kg · B ~ 90 kg。空 → None。
    排序: estimate desc。每筆四捨五入到整數 kg。"""
    if not estimates:
        return None
    items = sorted(estimates.items(), key=lambda kv: -kv[1])
    parts: list[str] = []
    for code, est in items:
        ex = lookup(code)
        name = ex.chinese if ex else code
        parts.append(f"{name} ~ {round(est)} kg")
    return "**估計 1RM (Epley)**: " + " · ".join(parts)


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
