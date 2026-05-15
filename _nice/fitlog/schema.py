"""fitlog JSON payload schema 結構驗證 — 純函式 (no I/O, no LLM).

PT 餵 JSON 漏一個欄位會在 parse_payload 噴 KeyError stack trace,對成熟
產品是 UX 致命傷。本模組在進 parse_payload 前先檢查結構,給出
path-prefixed 人話錯誤 (例:'session.sets[0].exercise_code: 缺失')。

vs validation.validate_session 的分工:
- 本模組:結構 / 型別 (KeyError 預防)
- validation.validate_session:業務合理性 (重量 typo / 動作代碼存在性)

允許 int(...) / float(...) 可轉的字串 (與 parse_payload 行為一致),
讓 PT 從 Excel 匯出的 JSON 也能直接吃。
"""
from __future__ import annotations

from typing import Any


def _is_int_like(v: Any) -> bool:
    if isinstance(v, bool):
        return False  # bool 是 int 子類型,但語義上不是
    if isinstance(v, int):
        return True
    if isinstance(v, str):
        try:
            int(v.strip())
            return True
        except ValueError:
            return False
    return False


def _is_float_like(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v.strip())
            return True
        except ValueError:
            return False
    return False


def _check_str(parent: dict, key: str, path: str, errors: list[str]) -> None:
    if key not in parent:
        errors.append(f"{path}.{key}: 缺失")
        return
    v = parent[key]
    if not isinstance(v, str) or not v.strip():
        errors.append(f"{path}.{key}: 應為非空字串 (got {type(v).__name__})")


def _check_int_like(parent: dict, key: str, path: str, errors: list[str]) -> None:
    if key not in parent:
        errors.append(f"{path}.{key}: 缺失")
        return
    if not _is_int_like(parent[key]):
        errors.append(f"{path}.{key}: 應為整數 (got {type(parent[key]).__name__})")


def validate_payload_schema(payload: Any) -> list[str]:
    """檢查 JSON payload 結構;回傳人話錯誤 list (空 list = 全通過)。"""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"payload: 應為 JSON object (got {type(payload).__name__})"]

    # ----- student -----
    student = payload.get("student")
    if student is None:
        errors.append("student: 缺失")
    elif not isinstance(student, dict):
        errors.append("student: 應為 object")
    else:
        _check_str(student, "name", "student", errors)
        # targets 是 optional list of {exercise_code: str, target_weight_kg: number}
        if "targets" in student:
            targets = student["targets"]
            if not isinstance(targets, list):
                errors.append(
                    f"student.targets: 應為 list (got {type(targets).__name__})"
                )
            else:
                for i, t in enumerate(targets):
                    prefix = f"student.targets[{i}]"
                    if not isinstance(t, dict):
                        errors.append(f"{prefix}: 應為 object")
                        continue
                    _check_str(t, "exercise_code", prefix, errors)
                    if "target_weight_kg" not in t:
                        errors.append(f"{prefix}.target_weight_kg: 缺失")
                    elif not _is_float_like(t["target_weight_kg"]):
                        errors.append(f"{prefix}.target_weight_kg: 應為數字")

    # ----- coach -----
    coach = payload.get("coach")
    if coach is None:
        errors.append("coach: 缺失")
    elif not isinstance(coach, dict):
        errors.append("coach: 應為 object")
    else:
        _check_str(coach, "name", "coach", errors)
        _check_str(coach, "studio_name", "coach", errors)

    # ----- session -----
    sess = payload.get("session")
    if sess is None:
        errors.append("session: 缺失")
        return errors
    if not isinstance(sess, dict):
        errors.append("session: 應為 object")
        return errors

    _check_int_like(sess, "session_no", "session", errors)
    _check_int_like(sess, "duration_min", "session", errors)
    _check_str(sess, "date", "session", errors)
    _check_str(sess, "theme", "session", errors)

    # ----- session.sets -----
    sets = sess.get("sets")
    if sets is None:
        errors.append("session.sets: 缺失")
        return errors
    if not isinstance(sets, list):
        errors.append("session.sets: 應為 list")
        return errors
    if not sets:
        errors.append("session.sets: 不可為空 list")
        return errors

    for i, s in enumerate(sets):
        prefix = f"session.sets[{i}]"
        if not isinstance(s, dict):
            errors.append(f"{prefix}: 應為 object")
            continue
        _check_str(s, "exercise_code", prefix, errors)
        _check_str(s, "reps_or_duration", prefix, errors)
        _check_int_like(s, "sets", prefix, errors)
        # weight_kg / rpe / note 都是 optional
        if "weight_kg" in s and s["weight_kg"] is not None and not _is_float_like(s["weight_kg"]):
            errors.append(f"{prefix}.weight_kg: 應為數字或 null (got {type(s['weight_kg']).__name__})")
        if "rpe" in s and s["rpe"] is not None and not _is_int_like(s["rpe"]):
            errors.append(f"{prefix}.rpe: 應為整數或 null")

    return errors
