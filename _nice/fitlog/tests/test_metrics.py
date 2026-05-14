"""紅色測試 — compute_total_tonnage 純函式計算訓練總噸位 (組數×次數×重量).

訓練 tonnage 是 PT 衡量單堂課訓練量的核心指標。只計算有 weight_kg
且 reps_or_duration 是純整數的紀錄;bodyweight、時間型 (60 sec)、
距離型 (500 m) 一律排除 (這些動作的訓練量需用其他指標,例如時間總和)。

放在 tests/ 是讓專案有正規測試入口;往後新功能都先寫紅色測試。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 讓 tests/ 能 import 同層 fitlog.py / metrics.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SetRecord  # noqa: E402
from metrics import compute_total_tonnage  # noqa: E402


def _set(code: str, sets: int, reps: str, weight: float | None, rpe: int | None = None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe)


class TestComputeTotalTonnage(unittest.TestCase):
    def test_empty_returns_zero(self) -> None:
        self.assertEqual(compute_total_tonnage([]), 0.0)

    def test_single_weighted_set(self) -> None:
        # 1 組 × 10 次 × 50 kg = 500
        self.assertEqual(
            compute_total_tonnage([_set("BENCH_PRESS", 1, "10", 50.0, 8)]),
            500.0,
        )

    def test_multiple_sets_same_exercise(self) -> None:
        # 4 組 × 10 次 × 70 kg = 2800
        self.assertEqual(
            compute_total_tonnage([_set("BB_BACK_SQUAT", 4, "10", 70.0, 7)]),
            2800.0,
        )

    def test_multiple_exercises_summed(self) -> None:
        sets = [
            _set("BENCH_PRESS", 4, "8", 50.0, 8),  # 1600
            _set("BB_ROW", 4, "8", 40.0, 7),       # 1280
        ]
        self.assertEqual(compute_total_tonnage(sets), 1600.0 + 1280.0)

    def test_bodyweight_excluded(self) -> None:
        # PULL_UP 沒外加重量 → weight_kg=None → 不計入
        self.assertEqual(
            compute_total_tonnage([_set("PULL_UP", 4, "8", None, 9)]),
            0.0,
        )

    def test_time_based_excluded(self) -> None:
        # 棒式 60 秒 不是 rep-based → 不計入 tonnage
        self.assertEqual(
            compute_total_tonnage([_set("PLANK", 3, "60 sec", None, 6)]),
            0.0,
        )

    def test_distance_based_excluded(self) -> None:
        # 划船機 500 m 不是 rep-based → 不計入
        self.assertEqual(
            compute_total_tonnage([_set("ROW_ERG", 1, "500 m", None, 7)]),
            0.0,
        )

    def test_mixed_session_only_weighted_rep_volume(self) -> None:
        # 混合課: PULL_UP (BW) + BENCH (加權) + PLANK (時間) → 只有 BENCH 計入
        sets = [
            _set("PULL_UP", 4, "8", None, 9),
            _set("BENCH_PRESS", 4, "8", 50.0, 8),
            _set("PLANK", 3, "60 sec", None, 6),
        ]
        self.assertEqual(compute_total_tonnage(sets), 1600.0)

    def test_handles_fractional_weight(self) -> None:
        # 47.5 kg 槓片是台灣健身房常見 (45+2.5) → 必須支援小數
        # 3 × 8 × 47.5 = 1140
        self.assertAlmostEqual(
            compute_total_tonnage([_set("BENCH_PRESS", 3, "8", 47.5, 8)]),
            1140.0,
        )

    def test_returns_float_not_int(self) -> None:
        # 永遠回 float, 讓下游格式化能統一
        result = compute_total_tonnage([_set("BENCH_PRESS", 1, "1", 50.0, 5)])
        self.assertIsInstance(result, float)


if __name__ == "__main__":
    unittest.main()
