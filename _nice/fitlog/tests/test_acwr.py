"""紅色測試 — 急慢性負荷比 ACWR (acute:chronic workload ratio).

ACWR 是運動科學界廣用的受傷風險指標:
    ACWR = 本週訓練量 (acute, 近 7 天) / 週平均訓練量 (chronic, 近 28 天 / 4)

判讀 (Gabbett 2016 等文獻常見分區):
    < 0.8       訓練量偏低 (detraining)
    0.8 – 1.3   最佳甜蜜區
    1.3 – 1.5   偏高,留意
    > 1.5       過高,受傷風險顯著上升

純數字函式,LLM 不能算。資料不足 (訓練史 < 21 天) → None。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import (  # noqa: E402
    StudentTrend,
    compute_acwr,
    render_acwr,
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


# 4×8×weight tonnage:weight=50 → 1600
class TestComputeAcwr(unittest.TestCase):
    def test_no_sessions_returns_none(self) -> None:
        self.assertIsNone(compute_acwr([], "林阿明", "2026-05-15"))

    def test_insufficient_history_returns_none(self) -> None:
        # 訓練史只有 10 天 (< 21) → 資料不足
        sessions = [
            _make("林阿明", "2026-05-05", 50.0),
            _make("林阿明", "2026-05-15", 50.0),
        ]
        self.assertIsNone(compute_acwr(sessions, "林阿明", "2026-05-15"))

    def test_steady_load_ratio_near_one(self) -> None:
        # 每週 1 堂同樣 tonnage,連續 5 週 → acute ≈ chronic → ACWR ≈ 1.0
        sessions = [
            _make("林阿明", "2026-04-17", 50.0),
            _make("林阿明", "2026-04-24", 50.0),
            _make("林阿明", "2026-05-01", 50.0),
            _make("林阿明", "2026-05-08", 50.0),
            _make("林阿明", "2026-05-15", 50.0),
        ]
        acwr = compute_acwr(sessions, "林阿明", "2026-05-15")
        assert acwr is not None
        # acute = 1 堂 1600;chronic = 近28天 4 堂 6400 / 4 = 1600 → 1.0
        self.assertAlmostEqual(acwr, 1.0, places=2)

    def test_spike_week_high_ratio(self) -> None:
        # 前 4 週各 1 堂輕量,本週爆量 → ACWR 高
        sessions = [
            _make("林阿明", "2026-04-17", 25.0),   # 800
            _make("林阿明", "2026-04-24", 25.0),
            _make("林阿明", "2026-05-01", 25.0),
            _make("林阿明", "2026-05-08", 25.0),
            _make("林阿明", "2026-05-15", 100.0),  # 3200 本週爆量
        ]
        acwr = compute_acwr(sessions, "林阿明", "2026-05-15")
        assert acwr is not None
        self.assertGreater(acwr, 1.5)

    def test_other_students_excluded(self) -> None:
        sessions = [
            _make("王小華", "2026-04-17", 999.0),
            _make("林阿明", "2026-04-17", 50.0),
            _make("林阿明", "2026-04-24", 50.0),
            _make("林阿明", "2026-05-01", 50.0),
            _make("林阿明", "2026-05-15", 50.0),
        ]
        acwr = compute_acwr(sessions, "林阿明", "2026-05-15")
        assert acwr is not None
        self.assertLess(acwr, 3.0)  # 王小華 的爆量不影響


class TestRenderAcwr(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(render_acwr(None))

    def test_sweet_spot_zone(self) -> None:
        out = render_acwr(1.0)
        assert out is not None
        self.assertIn("急慢性負荷比", out)
        self.assertIn("1.0", out)
        self.assertIn("甜蜜區", out)

    def test_high_risk_zone(self) -> None:
        out = render_acwr(1.8)
        assert out is not None
        self.assertIn("⚠️", out)
        self.assertIn("1.8", out)

    def test_low_load_zone(self) -> None:
        out = render_acwr(0.5)
        assert out is not None
        self.assertIn("偏低", out)

    def test_elevated_zone(self) -> None:
        out = render_acwr(1.4)
        assert out is not None
        self.assertIn("偏高", out)


class TestStudentTrendIncludesAcwr(unittest.TestCase):
    def test_kwarg_renders(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend, acwr=1.1)
        self.assertIn("急慢性負荷比", out)


if __name__ == "__main__":
    unittest.main()
