"""紅色測試 — validation 偵測時間/距離型動作填純數字 (漏單位).

exercise_db 每個動作有 measure_unit (rep/sec/min/m)。PLANK 是 sec、
RUN_TREADMILL 是 min。若 PT 把 PLANK 的 reps_or_duration 填純數字 "60"
(而非 "60 sec"),系統會把它當 reps,duration PR 追蹤就抓不到。

本輪在 validate_session 加檢查:exercise measure_unit 是 sec/min/m,
但該 set 填了純數字 → 警告建議補單位。
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


def _unit_warns(session: SessionInput) -> list[str]:
    return [w for w in validate_session(session) if "單位" in w]


class TestMeasureUnitValidation(unittest.TestCase):
    def test_plank_bare_number_warns(self) -> None:
        # PLANK measure_unit=sec;填 "60" 純數字 → 警告
        sess = _session([
            SetRecord("PLANK", 3, "60", None, 6),
        ])
        warns = _unit_warns(sess)
        self.assertEqual(len(warns), 1)
        self.assertIn("PLANK", warns[0])

    def test_plank_with_sec_unit_no_warning(self) -> None:
        sess = _session([SetRecord("PLANK", 3, "60 sec", None, 6)])
        self.assertEqual(_unit_warns(sess), [])

    def test_treadmill_bare_number_warns(self) -> None:
        # RUN_TREADMILL measure_unit=min
        sess = _session([SetRecord("RUN_TREADMILL", 1, "20", None, 6)])
        self.assertEqual(len(_unit_warns(sess)), 1)

    def test_treadmill_with_min_no_warning(self) -> None:
        sess = _session([SetRecord("RUN_TREADMILL", 1, "20 min", None, 6)])
        self.assertEqual(_unit_warns(sess), [])

    def test_rep_exercise_bare_number_ok(self) -> None:
        # BENCH_PRESS measure_unit=rep → 純數字 "8" 正確,不警告
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 8)])
        self.assertEqual(_unit_warns(sess), [])

    def test_unknown_exercise_no_unit_warning(self) -> None:
        # 不在 db 的動作沒有 measure_unit 可參照 → 不發單位警告
        sess = _session([SetRecord("NOT_A_CODE", 3, "60", None, 6)])
        self.assertEqual(_unit_warns(sess), [])

    def test_row_erg_distance_bare_number_warns(self) -> None:
        # ROW_ERG measure_unit=m
        sess = _session([SetRecord("ROW_ERG", 1, "500", None, 7)])
        self.assertEqual(len(_unit_warns(sess)), 1)

    def test_warning_has_set_prefix(self) -> None:
        sess = _session([
            SetRecord("BENCH_PRESS", 4, "8", 50.0, 8),
            SetRecord("PLANK", 3, "60", None, 6),
        ])
        warns = _unit_warns(sess)
        self.assertEqual(len(warns), 1)
        self.assertIn("第 2 set", warns[0])


class TestDoesNotBreakOtherValidation(unittest.TestCase):
    def test_clean_session_no_warnings(self) -> None:
        sess = _session([
            SetRecord("BENCH_PRESS", 4, "8", 50.0, 8),
            SetRecord("PLANK", 3, "60 sec", None, 6),
        ])
        self.assertEqual(validate_session(sess), [])


if __name__ == "__main__":
    unittest.main()
