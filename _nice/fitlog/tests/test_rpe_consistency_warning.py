"""紅色測試 — validate_session 偵測 RPE 記錄不一致 (漏填).

RPE 驅動下次重量建議 / deload 偵測 / 強度分布 / 強度分數。若 PT 整堂課
6 個 set 填了 5 個 RPE、漏了 1 個,那筆 set 會被所有分析靜默跳過。

heuristic:
- 整堂沒任何 set 有 RPE → 不警告 (PT 顯然不追 RPE,是刻意選擇)
- 整堂所有 set 都有 RPE → 不警告 (完整)
- 混合 (部分有部分沒) → 對沒填的 set 各發一個警告 (高度疑似漏填)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SessionInput, SetRecord  # noqa: E402
from validation import validate_session  # noqa: E402


def _session(sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-15", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, rpe: int | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=4, reps_or_duration="8",
                     weight_kg=50.0, rpe=rpe)


def _rpe_warns(session: SessionInput) -> list[str]:
    return [w for w in validate_session(session) if "RPE" in w and "漏" in w]


class TestRpeConsistencyWarning(unittest.TestCase):
    def test_no_rpe_at_all_no_warning(self) -> None:
        # PT 不追 RPE → 不囉嗦
        sess = _session([_set("BENCH_PRESS", None), _set("OHP", None)])
        self.assertEqual(_rpe_warns(sess), [])

    def test_all_rpe_no_warning(self) -> None:
        sess = _session([_set("BENCH_PRESS", 8), _set("OHP", 7)])
        self.assertEqual(_rpe_warns(sess), [])

    def test_mixed_warns_for_missing_one(self) -> None:
        # 2 有 1 沒 → 對沒填的那筆警告
        sess = _session([
            _set("BENCH_PRESS", 8),
            _set("OHP", 7),
            _set("DIPS", None),
        ])
        warns = _rpe_warns(sess)
        self.assertEqual(len(warns), 1)
        self.assertIn("第 3 set", warns[0])

    def test_mixed_warns_for_each_missing(self) -> None:
        sess = _session([
            _set("BENCH_PRESS", 8),
            _set("OHP", None),
            _set("DIPS", None),
        ])
        warns = _rpe_warns(sess)
        self.assertEqual(len(warns), 2)

    def test_warning_mentions_exercise_code(self) -> None:
        sess = _session([
            _set("BENCH_PRESS", 8),
            _set("DIPS", None),
        ])
        warns = _rpe_warns(sess)
        self.assertEqual(len(warns), 1)
        self.assertIn("DIPS", warns[0])


class TestRpeConsistencyDoesNotBreakOthers(unittest.TestCase):
    def test_other_warnings_still_emitted(self) -> None:
        # 重量超標 + RPE 漏填 → 兩種警告都在
        sess = _session([
            SetRecord(exercise_code="BENCH_PRESS", sets=4,
                      reps_or_duration="8", weight_kg=900.0, rpe=8),
            _set("DIPS", None),
        ])
        warns = validate_session(sess)
        self.assertTrue(any("RPE" in w and "漏" in w for w in warns))
        self.assertTrue(any("超過" in w for w in warns))

    def test_clean_all_rpe_session_no_warnings(self) -> None:
        sess = _session([_set("BENCH_PRESS", 8), _set("OHP", 7)])
        self.assertEqual(validate_session(sess), [])


if __name__ == "__main__":
    unittest.main()
