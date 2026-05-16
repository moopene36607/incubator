"""紅色測試 — RPE 大幅偏離動作典型範圍警示.

exercise_db 每個動作有 typical_rpe_range (例 PLANK (4,7)、活動度動作 (1,3))。
若 PT 填的 RPE 大幅落在典型範圍外 (例:活動度暖身動作填 RPE 9),極可能
是 typo 或填錯欄位。本輪在 validate_session 加一個寬鬆檢查:RPE 超出
典型範圍 2 分以上才警告 (RPE 主觀,範圍只是參考,不嚴格擋)。
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


def _range_warns(session: SessionInput) -> list[str]:
    return [w for w in validate_session(session) if "典型" in w]


class TestRpeRangeValidation(unittest.TestCase):
    def test_rpe_within_typical_no_warning(self) -> None:
        # BENCH_PRESS typical (6,9);RPE 8 在範圍內
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 8)])
        self.assertEqual(_range_warns(sess), [])

    def test_rpe_slightly_over_no_warning(self) -> None:
        # BENCH_PRESS (6,9);RPE 10 = 只超 1,寬鬆範圍內不警告
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 10)])
        self.assertEqual(_range_warns(sess), [])

    def test_mobility_drill_high_rpe_warns(self) -> None:
        # HIP_OPENER typical (1,3);RPE 9 遠超 → 警告
        sess = _session([SetRecord("HIP_OPENER", 2, "8", None, 9)])
        warns = _range_warns(sess)
        self.assertEqual(len(warns), 1)
        self.assertIn("HIP_OPENER", warns[0])

    def test_rpe_far_below_warns(self) -> None:
        # PULL_UP typical (7,10);RPE 2 遠低於 → 警告
        sess = _session([SetRecord("PULL_UP", 3, "8", None, 2)])
        self.assertEqual(len(_range_warns(sess)), 1)

    def test_unknown_exercise_no_range_warning(self) -> None:
        sess = _session([SetRecord("NOT_A_CODE", 3, "8", 50.0, 10)])
        self.assertEqual(_range_warns(sess), [])

    def test_no_rpe_no_warning(self) -> None:
        sess = _session([SetRecord("HIP_OPENER", 2, "8", None, None)])
        self.assertEqual(_range_warns(sess), [])

    def test_out_of_1_10_rpe_not_double_flagged(self) -> None:
        # RPE 15 已被既有「超出 1-10」抓;不該也報典型範圍 (避免重複洗版)
        sess = _session([SetRecord("BENCH_PRESS", 4, "8", 50.0, 15)])
        # 典型範圍警告不該出現 (15 不是合法 RPE,交給既有檢查)
        self.assertEqual(_range_warns(sess), [])

    def test_warning_has_set_prefix(self) -> None:
        sess = _session([
            SetRecord("BENCH_PRESS", 4, "8", 50.0, 8),
            SetRecord("HIP_OPENER", 2, "8", None, 9),
        ])
        warns = _range_warns(sess)
        self.assertEqual(len(warns), 1)
        self.assertIn("第 2 set", warns[0])


class TestRpeRangeDoesNotBreakOthers(unittest.TestCase):
    def test_clean_session_no_warnings(self) -> None:
        sess = _session([
            SetRecord("BENCH_PRESS", 4, "8", 50.0, 8),
            SetRecord("HIP_OPENER", 2, "8", None, 2),
        ])
        self.assertEqual(validate_session(sess), [])


if __name__ == "__main__":
    unittest.main()
