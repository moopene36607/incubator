"""紅色測試 — BW (bodyweight) reps PR 跨堂追蹤.

對初學者 / 中階學員,Pull-up 4→6→8 reps 是「最直覺、最有感」的進步。
上輪 PR 追蹤跳過 BW 動作,本輪補上 — 用 max single-set reps 為基準
(同 exercise 多 set,取最高那組的 reps)。

規則:
- 兩堂課都做過該 exercise + 兩邊都是 BW (weight_kg=None) + reps 都是純整數
- 一邊 BW 一邊加重 → 跳過 (訓練性質改變,上輪 weight 模組已處理)
- 時間型 ('60 sec')、距離型 ('500 m') reps → 跳過 (本輪不做時間 PR)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SetRecord  # noqa: E402
from progress import (  # noqa: E402
    BwRepsDelta,
    ProgressDelta,
    compute_bw_reps_deltas,
    render_pr_summary,
)


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestComputeBwRepsDeltas(unittest.TestCase):
    def test_no_overlap_returns_empty(self) -> None:
        prev = [_set("PULL_UP", 3, "6", None)]
        curr = [_set("DIPS", 3, "8", None)]
        self.assertEqual(compute_bw_reps_deltas(prev, curr), {})

    def test_empty_prev_returns_empty(self) -> None:
        curr = [_set("PULL_UP", 3, "6", None)]
        self.assertEqual(compute_bw_reps_deltas([], curr), {})

    def test_pull_up_reps_pr(self) -> None:
        prev = [_set("PULL_UP", 3, "6", None)]
        curr = [_set("PULL_UP", 3, "8", None)]
        result = compute_bw_reps_deltas(prev, curr)
        self.assertIn("PULL_UP", result)
        d = result["PULL_UP"]
        self.assertEqual(d.prev_top_reps, 6)
        self.assertEqual(d.curr_top_reps, 8)
        self.assertEqual(d.reps_delta, 2)
        self.assertTrue(d.is_reps_pr)

    def test_reps_regression(self) -> None:
        prev = [_set("PULL_UP", 3, "8", None)]
        curr = [_set("PULL_UP", 3, "6", None)]
        d = compute_bw_reps_deltas(prev, curr)["PULL_UP"]
        self.assertEqual(d.reps_delta, -2)
        self.assertFalse(d.is_reps_pr)

    def test_uses_max_reps_across_multiple_sets(self) -> None:
        # 多 set 不同 reps → 取最高為 top reps
        prev = [
            _set("PULL_UP", 1, "8", None),
            _set("PULL_UP", 1, "6", None),
            _set("PULL_UP", 1, "4", None),
        ]
        curr = [
            _set("PULL_UP", 1, "10", None),
            _set("PULL_UP", 1, "7", None),
        ]
        d = compute_bw_reps_deltas(prev, curr)["PULL_UP"]
        self.assertEqual(d.prev_top_reps, 8)
        self.assertEqual(d.curr_top_reps, 10)

    def test_weighted_exercise_skipped(self) -> None:
        # 兩邊都加重 → 由 weight 模組處理,本函式跳過
        prev = [_set("BENCH_PRESS", 4, "8", 47.5)]
        curr = [_set("BENCH_PRESS", 4, "8", 50.0)]
        self.assertEqual(compute_bw_reps_deltas(prev, curr), {})

    def test_one_side_bw_other_weighted_skipped(self) -> None:
        # prev BW, curr 加重 → 訓練性質變,跳過
        prev = [_set("PULL_UP", 3, "8", None)]
        curr = [_set("PULL_UP", 3, "5", 10.0)]
        self.assertEqual(compute_bw_reps_deltas(prev, curr), {})

    def test_time_based_reps_skipped(self) -> None:
        # PLANK '60 sec' → 不是純整數,跳過 (留下輪做時間 PR)
        prev = [_set("PLANK", 3, "60 sec", None)]
        curr = [_set("PLANK", 3, "90 sec", None)]
        self.assertEqual(compute_bw_reps_deltas(prev, curr), {})

    def test_returns_bw_reps_delta_dataclass(self) -> None:
        prev = [_set("PULL_UP", 3, "6", None)]
        curr = [_set("PULL_UP", 3, "8", None)]
        d = compute_bw_reps_deltas(prev, curr)["PULL_UP"]
        self.assertIsInstance(d, BwRepsDelta)
        self.assertEqual(d.exercise_code, "PULL_UP")


class TestRenderPrSummaryWithBw(unittest.TestCase):
    def test_bw_only_format(self) -> None:
        bw = {"PULL_UP": BwRepsDelta(
            exercise_code="PULL_UP",
            prev_top_reps=6, curr_top_reps=8, reps_delta=2, is_reps_pr=True,
        )}
        result = render_pr_summary({}, bw)
        self.assertIsNotNone(result)
        self.assertIn("引體向上", result)
        self.assertIn("6→8 reps", result)
        self.assertIn("+2 reps", result)
        self.assertIn("PR", result)

    def test_bw_regression_no_pr_label(self) -> None:
        bw = {"PULL_UP": BwRepsDelta(
            exercise_code="PULL_UP",
            prev_top_reps=8, curr_top_reps=6, reps_delta=-2, is_reps_pr=False,
        )}
        result = render_pr_summary({}, bw)
        self.assertIsNotNone(result)
        self.assertIn("-2 reps", result)
        self.assertNotIn("PR", result)

    def test_bw_unchanged_skipped(self) -> None:
        bw = {"PULL_UP": BwRepsDelta(
            exercise_code="PULL_UP",
            prev_top_reps=6, curr_top_reps=6, reps_delta=0, is_reps_pr=False,
        )}
        self.assertIsNone(render_pr_summary({}, bw))

    def test_combined_weighted_and_bw_both_appear(self) -> None:
        weighted = {"BENCH_PRESS": ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=47.5, curr_top_weight=50.0, weight_delta_kg=2.5,
            prev_tonnage=1520.0, curr_tonnage=1600.0, tonnage_delta=80.0,
            is_weight_pr=True,
        )}
        bw = {"PULL_UP": BwRepsDelta(
            exercise_code="PULL_UP",
            prev_top_reps=6, curr_top_reps=8, reps_delta=2, is_reps_pr=True,
        )}
        result = render_pr_summary(weighted, bw)
        self.assertIsNotNone(result)
        self.assertIn("槓鈴臥推", result)
        self.assertIn("引體向上", result)

    def test_existing_signature_still_works_without_bw_arg(self) -> None:
        # 上輪測試的呼叫方式不能破:render_pr_summary(weighted) 仍可呼叫
        weighted = {"BENCH_PRESS": ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=47.5, curr_top_weight=50.0, weight_delta_kg=2.5,
            prev_tonnage=1520.0, curr_tonnage=1600.0, tonnage_delta=80.0,
            is_weight_pr=True,
        )}
        result = render_pr_summary(weighted)
        self.assertIsNotNone(result)
        self.assertIn("槓鈴臥推", result)

    def test_bw_sorted_by_reps_delta_desc(self) -> None:
        bw = {
            "PULL_UP": BwRepsDelta(exercise_code="PULL_UP",
                                   prev_top_reps=6, curr_top_reps=7,
                                   reps_delta=1, is_reps_pr=True),
            "DIPS": BwRepsDelta(exercise_code="DIPS",
                                prev_top_reps=5, curr_top_reps=10,
                                reps_delta=5, is_reps_pr=True),
        }
        result = render_pr_summary({}, bw)
        # 雙槓臂屈伸 (+5) 應該排在 引體向上 (+1) 前面
        self.assertLess(result.find("雙槓臂屈伸"), result.find("引體向上"))


if __name__ == "__main__":
    unittest.main()
