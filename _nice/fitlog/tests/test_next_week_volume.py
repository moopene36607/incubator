"""紅色測試 — 下週建議訓練量區間 (從 ACWR 甜蜜區反推).

ACWR (round 39) 是回顧性指標。本輪做前瞻性處方:既然 ACWR 0.8–1.3 是
受傷風險最低的甜蜜區,而 ACWR = 下週 acute / chronic 週平均,反推下週
acute 應落在 [0.8 × chronic_weekly, 1.3 × chronic_weekly]。

純數字函式 recommend_next_week_tonnage(sessions, student, as_of)
→ (low_kg, high_kg) 或 None (訓練史 < 21 天)。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import (  # noqa: E402
    StudentTrend,
    recommend_next_week_tonnage,
    render_next_week_tonnage,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402


def _make(student: str, date: str, weight: float) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=1, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=weight, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


# 4×8×weight:weight=50 → 1600
class TestRecommendNextWeekTonnage(unittest.TestCase):
    def test_no_sessions_returns_none(self) -> None:
        self.assertIsNone(
            recommend_next_week_tonnage([], "林阿明", "2026-05-15"))

    def test_insufficient_history_returns_none(self) -> None:
        sessions = [
            _make("林阿明", "2026-05-10", 50.0),
            _make("林阿明", "2026-05-15", 50.0),
        ]
        self.assertIsNone(
            recommend_next_week_tonnage(sessions, "林阿明", "2026-05-15"))

    def test_steady_load_range(self) -> None:
        # 近 28 天 4 堂各 1600 → chronic weekly = 1600
        # 建議下週 [0.8×1600, 1.3×1600] = [1280, 2080]
        sessions = [
            _make("林阿明", "2026-04-17", 50.0),
            _make("林阿明", "2026-04-24", 50.0),
            _make("林阿明", "2026-05-01", 50.0),
            _make("林阿明", "2026-05-08", 50.0),
            _make("林阿明", "2026-05-15", 50.0),
        ]
        result = recommend_next_week_tonnage(sessions, "林阿明", "2026-05-15")
        assert result is not None
        low, high = result
        self.assertAlmostEqual(low, 1280.0, places=1)
        self.assertAlmostEqual(high, 2080.0, places=1)

    def test_low_less_than_high(self) -> None:
        sessions = [
            _make("林阿明", "2026-04-17", 50.0),
            _make("林阿明", "2026-04-24", 60.0),
            _make("林阿明", "2026-05-01", 55.0),
            _make("林阿明", "2026-05-15", 50.0),
        ]
        result = recommend_next_week_tonnage(sessions, "林阿明", "2026-05-15")
        assert result is not None
        self.assertLess(result[0], result[1])

    def test_other_students_excluded(self) -> None:
        sessions = [
            _make("王小華", "2026-04-17", 999.0),
            _make("林阿明", "2026-04-17", 50.0),
            _make("林阿明", "2026-04-24", 50.0),
            _make("林阿明", "2026-05-01", 50.0),
            _make("林阿明", "2026-05-15", 50.0),
        ]
        result = recommend_next_week_tonnage(sessions, "林阿明", "2026-05-15")
        assert result is not None
        # 王小華 不影響 → high 不會爆大
        self.assertLess(result[1], 5000.0)


class TestRenderNextWeekTonnage(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(render_next_week_tonnage(None))

    def test_renders_range(self) -> None:
        out = render_next_week_tonnage((1280.0, 2080.0))
        assert out is not None
        self.assertIn("下週建議訓練量", out)
        self.assertIn("1,280", out)
        self.assertIn("2,080", out)


class TestStudentTrendIncludesNextWeek(unittest.TestCase):
    def test_kwarg_renders(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend, next_week_tonnage=(1280.0, 2080.0))
        self.assertIn("下週建議訓練量", out)


if __name__ == "__main__":
    unittest.main()
