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


def validate_session(
    session: "SessionInput",
    today_iso: str | None = None,
) -> list[str]:
    """檢查 session 各欄位合理性,回傳警告 list (空 list = 全通過)。
    today_iso 給定時,session_date > today_iso 視為未來 (年份 typo 預防)。"""
    from exercise_db import lookup
    warnings: list[str] = []

    if not session.sets:
        warnings.append("本堂課沒有任何 set,無法產出有意義的報告")
        return warnings

    if session.duration_min <= 0:
        warnings.append(f"課程時長 {session.duration_min} min 不合理 (應 > 0)")

    # 未來日期警告:純字串比較對 ISO date 安全 (YYYY-MM-DD lexicographic = chronological)
    if today_iso and session.session_date > today_iso:
        warnings.append(
            f"課程日期 {session.session_date} 在未來 "
            f"(今天 {today_iso}),可能是年份 typo"
        )

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
        # RPE 大幅偏離動作典型範圍 (超出 2 分以上) → 疑似 typo;
        # RPE 主觀,只在合法 1-10 範圍內才比,且寬鬆 2 分緩衝
        if (s.rpe is not None and 1 <= s.rpe <= 10):
            _ex = lookup(s.exercise_code)
            if _ex is not None:
                _lo, _hi = _ex.typical_rpe_range
                if s.rpe < _lo - 2 or s.rpe > _hi + 2:
                    warnings.append(
                        f"{prefix}:RPE {s.rpe} 大幅偏離 {s.exercise_code} "
                        f"典型範圍 {_lo}-{_hi},確認是否 typo 或填錯欄位"
                    )

        # 時間/距離型動作填純數字 → 漏單位 (會被當 reps,duration PR 追蹤失效)
        ex = lookup(s.exercise_code)
        if (ex is not None and ex.measure_unit in ("sec", "min", "m")
                and s_reps.isdigit()):
            warnings.append(
                f"{prefix}:{s.exercise_code} 是 {ex.measure_unit} 計量動作,"
                f"但填了純數字 '{s_reps}' — 建議補單位 (例 '{s_reps} {ex.measure_unit}')"
            )

    # RPE 記錄一致性:整堂部分有部分沒 → 高度疑似漏填 (整堂都沒填則視為刻意不追)
    n_with_rpe = sum(1 for s in session.sets if s.rpe is not None)
    if 0 < n_with_rpe < len(session.sets):
        for i, s in enumerate(session.sets, 1):
            if s.rpe is None:
                warnings.append(
                    f"第 {i} set ({s.exercise_code}):沒填 RPE,但同堂其他 set 有 "
                    f"— 疑似漏填,RPE 缺漏會讓下次重量建議 / 強度分析跳過該動作"
                )

    return warnings
