"""fitlog input validation — 純函式檢查 PT JSON 輸入合理性 (no I/O, no LLM).

PT 在 CLI 餵 JSON 時最常出錯的:
- 重量 typo (50.0 → 500.0 — 漏小數點)
- 動作代碼拼錯 (BB_BACK_SQT vs BB_BACK_SQUAT)
- 組數忘填或填 0
- RPE 超出 1–10 範圍
- 課程時長 < 0 或 0

把上述問題列為人類可讀的警告 list,讓 CLI 印到 stderr 後仍繼續產報告
(允許 PT 邊修邊用,而不是用 hard error 擋)。

警告每筆都帶「第 N set」前綴,讓教練知道要修哪一筆。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fitlog import SessionInput

# 重量上限 — 世界臥推紀錄 ~487 kg、硬舉 ~501 kg。設 500 kg 即警告 typo。
MAX_REASONABLE_WEIGHT_KG: float = 500.0
# 單組次數上限 — 一般訓練 3-30 reps;>100 大概是 typo
MAX_REASONABLE_REPS: int = 100
# 同動作組數上限 — 一般 3-6 組;>20 大概是 typo
MAX_REASONABLE_SETS: int = 20


def validate_session(session: "SessionInput") -> list[str]:
    """檢查 session 各欄位合理性,回傳警告 list (空 list = 全通過)。"""
    from exercise_db import lookup
    warnings: list[str] = []

    if not session.sets:
        warnings.append("本堂課沒有任何 set,無法產出有意義的報告")
        return warnings

    if session.duration_min <= 0:
        warnings.append(f"課程時長 {session.duration_min} min 不合理 (應 > 0)")

    for i, s in enumerate(session.sets, 1):
        prefix = f"第 {i} set ({s.exercise_code})"

        if lookup(s.exercise_code) is None:
            warnings.append(f"{prefix}:動作代碼不在 exercise_db,請確認拼寫")

        if s.sets < 1:
            warnings.append(f"{prefix}:組數 {s.sets} 不合理 (應 >= 1)")
        elif s.sets > MAX_REASONABLE_SETS:
            warnings.append(
                f"{prefix}:組數 {s.sets} 偏高 (>{MAX_REASONABLE_SETS}),可能是 typo"
            )

        if s.weight_kg is not None:
            if s.weight_kg < 0:
                warnings.append(
                    f"{prefix}:重量 {s.weight_kg} kg 為負,不合理"
                )
            elif s.weight_kg > MAX_REASONABLE_WEIGHT_KG:
                warnings.append(
                    f"{prefix}:重量 {s.weight_kg} kg 超過 {MAX_REASONABLE_WEIGHT_KG} kg,可能是 typo"
                )

        # reps_or_duration 是字串,只在純整數時做數值檢查
        s_reps = s.reps_or_duration.strip()
        if s_reps.isdigit():
            r = int(s_reps)
            if r < 1:
                warnings.append(f"{prefix}:次數 {r} 不合理 (應 >= 1)")
            elif r > MAX_REASONABLE_REPS:
                warnings.append(
                    f"{prefix}:次數 {r} 偏高 (>{MAX_REASONABLE_REPS}),可能是 typo"
                )

        if s.rpe is not None and (s.rpe < 1 or s.rpe > 10):
            warnings.append(f"{prefix}:RPE {s.rpe} 超出 1–10 範圍")

    return warnings
