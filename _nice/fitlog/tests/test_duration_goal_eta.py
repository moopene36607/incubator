"""紅色測試 — 時間/距離型目標達成日預估.

compute_goal_etas 已支援 target_weight_kg (round 9) 與 target_reps
(round 37) 的線性外推。round 73-74 加了 target_duration。本輪補上
duration 目標的 ETA — 用 duration_progressions 跑線性外推。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import compute_goal_etas  # noqa: E402


class TestComputeGoalEtasDuration(unittest.TestCase):
    def test_duration_target_projects_eta(self) -> None:
        # 棒式每 7 天 +10 sec;60→70→80→90,today 2026-05-15
        # 90 → target 120 需 30 sec → 21 天 → 2026-06-05
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        duration_progressions = {
            "PLANK": ("sec", [
                ("2026-04-22", 60), ("2026-04-29", 70),
                ("2026-05-06", 80), ("2026-05-13", 90),
            ]),
        }
        result = compute_goal_etas(
            targets, {}, "2026-05-15",
            duration_progressions=duration_progressions,
        )
        self.assertIn("PLANK", result)
        self.assertEqual(result["PLANK"], "2026-06-05")

    def test_duration_already_achieved_skipped(self) -> None:
        targets = [{"exercise_code": "PLANK", "target_duration": 90}]
        duration_progressions = {
            "PLANK": ("sec", [("2026-04-22", 70), ("2026-05-13", 90)]),
        }
        result = compute_goal_etas(
            targets, {}, "2026-05-15",
            duration_progressions=duration_progressions,
        )
        self.assertEqual(result, {})

    def test_duration_no_progression_skipped(self) -> None:
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        result = compute_goal_etas(
            targets, {}, "2026-05-15", duration_progressions={})
        self.assertEqual(result, {})

    def test_duration_no_progress_skipped(self) -> None:
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        duration_progressions = {
            "PLANK": ("sec", [("2026-04-22", 90), ("2026-05-13", 90)]),
        }
        result = compute_goal_etas(
            targets, {}, "2026-05-15",
            duration_progressions=duration_progressions,
        )
        self.assertEqual(result, {})

    def test_backward_compat_no_duration_arg(self) -> None:
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        weight_prog = {
            "BENCH_PRESS": [("2026-04-22", 50.0), ("2026-05-13", 56.0)],
        }
        result = compute_goal_etas(targets, weight_prog, "2026-05-15")
        self.assertIn("BENCH_PRESS", result)


if __name__ == "__main__":
    unittest.main()
