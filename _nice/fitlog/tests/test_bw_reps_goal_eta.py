"""紅色測試 — BW reps 目標的達成日預估 (補完 goal ETA 對稱性).

round 9 加了重量目標的線性外推 ETA;round 36 加了 BW reps 目標。但
compute_goal_etas 還只看 target_weight_kg。本輪讓它也吃 target_reps,
用 bw_reps_progression 跑線性外推。

純函式;沿用既有 project_goal_eta (value 用 reps 數即可)。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import compute_goal_etas  # noqa: E402


class TestComputeGoalEtasReps(unittest.TestCase):
    def test_reps_target_projects_eta(self) -> None:
        # Pull-up 每 7 天 +1 reps;5→6→7→8,today 2026-05-15
        # 從 8 → target 12 需要 4 reps → 28 天 → 2026-06-12
        targets = [{"exercise_code": "PULL_UP", "target_reps": 12}]
        bw_reps_progressions = {
            "PULL_UP": [
                ("2026-04-22", 5), ("2026-04-29", 6),
                ("2026-05-06", 7), ("2026-05-13", 8),
            ],
        }
        result = compute_goal_etas(
            targets, {}, "2026-05-15",
            bw_reps_progressions=bw_reps_progressions,
        )
        self.assertIn("PULL_UP", result)
        self.assertEqual(result["PULL_UP"], "2026-06-12")

    def test_reps_target_already_achieved_skipped(self) -> None:
        targets = [{"exercise_code": "PULL_UP", "target_reps": 8}]
        bw_reps_progressions = {
            "PULL_UP": [("2026-04-22", 6), ("2026-05-13", 8)],
        }
        result = compute_goal_etas(
            targets, {}, "2026-05-15",
            bw_reps_progressions=bw_reps_progressions,
        )
        self.assertEqual(result, {})

    def test_reps_target_no_progression_skipped(self) -> None:
        targets = [{"exercise_code": "PULL_UP", "target_reps": 12}]
        result = compute_goal_etas(
            targets, {}, "2026-05-15", bw_reps_progressions={},
        )
        self.assertEqual(result, {})

    def test_reps_target_no_progress_skipped(self) -> None:
        # 持平 → slope 0 → 無 ETA
        targets = [{"exercise_code": "PULL_UP", "target_reps": 12}]
        bw_reps_progressions = {
            "PULL_UP": [("2026-04-22", 8), ("2026-05-13", 8)],
        }
        result = compute_goal_etas(
            targets, {}, "2026-05-15",
            bw_reps_progressions=bw_reps_progressions,
        )
        self.assertEqual(result, {})

    def test_weight_and_reps_targets_together(self) -> None:
        targets = [
            {"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0},
            {"exercise_code": "PULL_UP", "target_reps": 12},
        ]
        weight_prog = {
            "BENCH_PRESS": [
                ("2026-04-22", 50.0), ("2026-04-29", 52.0),
                ("2026-05-06", 54.0), ("2026-05-13", 56.0),
            ],
        }
        bw_reps_prog = {
            "PULL_UP": [
                ("2026-04-22", 5), ("2026-04-29", 6),
                ("2026-05-06", 7), ("2026-05-13", 8),
            ],
        }
        result = compute_goal_etas(
            targets, weight_prog, "2026-05-15",
            bw_reps_progressions=bw_reps_prog,
        )
        self.assertIn("BENCH_PRESS", result)
        self.assertIn("PULL_UP", result)

    def test_backward_compat_no_bw_arg(self) -> None:
        # 不傳 bw_reps_progressions → 重量目標照常運作
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        weight_prog = {
            "BENCH_PRESS": [
                ("2026-04-22", 50.0), ("2026-05-13", 56.0),
            ],
        }
        result = compute_goal_etas(targets, weight_prog, "2026-05-15")
        self.assertIn("BENCH_PRESS", result)


if __name__ == "__main__":
    unittest.main()
