"""紅色測試 — 時間 / 距離型 PR 跨堂追蹤.

完成 PR 三部曲最後一塊。除了重量與 BW reps,還有時間型動作 (Plank,
Treadmill 跑步分鐘數) 與距離型動作 (Row Erg 公尺數) 的進步要追蹤。

核心規則:
- 兩堂課都做過該 exercise + 兩邊 reps_or_duration 都解析得出來 + 同單位
- 單位限定 whitelist: sec / min / m / km (避免把 "5 reps/side" 誤當距離)
- 同 exercise 多 set → 取 max value (撐最久 / 跑最遠)
- 同 session 內單位不一致 (一組 60 sec 一組 1 min) → 跳過
- 兩堂單位不同 (prev sec 但 curr min) → 跳過 (沒換算)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SetRecord  # noqa: E402
from progress import (  # noqa: E402
    BwRepsDelta,
    DurationDelta,
    ProgressDelta,
    compute_duration_deltas,
    render_pr_summary,
)


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestComputeDurationDeltas(unittest.TestCase):
    def test_no_overlap_returns_empty(self) -> None:
        prev = [_set("PLANK", 3, "60 sec", None)]
        curr = [_set("ROW_ERG", 1, "500 m", None)]
        self.assertEqual(compute_duration_deltas(prev, curr), {})

    def test_empty_prev_returns_empty(self) -> None:
        curr = [_set("PLANK", 3, "60 sec", None)]
        self.assertEqual(compute_duration_deltas([], curr), {})

    def test_plank_seconds_pr(self) -> None:
        prev = [_set("PLANK", 3, "60 sec", None)]
        curr = [_set("PLANK", 3, "90 sec", None)]
        d = compute_duration_deltas(prev, curr)["PLANK"]
        self.assertEqual(d.unit, "sec")
        self.assertEqual(d.prev_top_value, 60)
        self.assertEqual(d.curr_top_value, 90)
        self.assertEqual(d.delta, 30)
        self.assertTrue(d.is_pr)

    def test_plank_regression(self) -> None:
        prev = [_set("PLANK", 3, "90 sec", None)]
        curr = [_set("PLANK", 3, "60 sec", None)]
        d = compute_duration_deltas(prev, curr)["PLANK"]
        self.assertEqual(d.delta, -30)
        self.assertFalse(d.is_pr)

    def test_uses_max_value_across_multiple_sets(self) -> None:
        prev = [
            _set("PLANK", 1, "30 sec", None),
            _set("PLANK", 1, "60 sec", None),
            _set("PLANK", 1, "45 sec", None),
        ]
        curr = [
            _set("PLANK", 1, "75 sec", None),
            _set("PLANK", 1, "60 sec", None),
        ]
        d = compute_duration_deltas(prev, curr)["PLANK"]
        self.assertEqual(d.prev_top_value, 60)
        self.assertEqual(d.curr_top_value, 75)

    def test_row_erg_distance_progression(self) -> None:
        prev = [_set("ROW_ERG", 1, "500 m", None)]
        curr = [_set("ROW_ERG", 1, "700 m", None)]
        d = compute_duration_deltas(prev, curr)["ROW_ERG"]
        self.assertEqual(d.unit, "m")
        self.assertEqual(d.delta, 200)
        self.assertTrue(d.is_pr)

    def test_treadmill_minutes(self) -> None:
        prev = [_set("RUN_TREADMILL", 1, "20 min", None)]
        curr = [_set("RUN_TREADMILL", 1, "30 min", None)]
        d = compute_duration_deltas(prev, curr)["RUN_TREADMILL"]
        self.assertEqual(d.unit, "min")
        self.assertEqual(d.delta, 10)

    def test_different_units_between_sessions_skipped(self) -> None:
        # prev 60 sec, curr 1 min — 不換算,跳過
        prev = [_set("PLANK", 3, "60 sec", None)]
        curr = [_set("PLANK", 3, "1 min", None)]
        self.assertEqual(compute_duration_deltas(prev, curr), {})

    def test_inconsistent_units_within_session_skipped(self) -> None:
        # 同 session PLANK 一組 60 sec 一組 1 min → 跳過該 exercise
        prev = [
            _set("PLANK", 1, "60 sec", None),
            _set("PLANK", 1, "1 min", None),
        ]
        curr = [_set("PLANK", 3, "90 sec", None)]
        self.assertEqual(compute_duration_deltas(prev, curr), {})

    def test_numeric_reps_skipped(self) -> None:
        # "10" 是純整數 reps,不是 duration → 跳過
        prev = [_set("BENCH_PRESS", 4, "10", 50.0)]
        curr = [_set("BENCH_PRESS", 4, "10", 50.0)]
        self.assertEqual(compute_duration_deltas(prev, curr), {})

    def test_reps_per_side_string_skipped(self) -> None:
        # "5 reps/side" 不在 whitelist (sec/min/m/km),跳過
        prev = [_set("WORLDS_GREATEST", 2, "5 reps/side", None)]
        curr = [_set("WORLDS_GREATEST", 2, "8 reps/side", None)]
        self.assertEqual(compute_duration_deltas(prev, curr), {})

    def test_returns_duration_delta_dataclass(self) -> None:
        prev = [_set("PLANK", 3, "60 sec", None)]
        curr = [_set("PLANK", 3, "90 sec", None)]
        d = compute_duration_deltas(prev, curr)["PLANK"]
        self.assertIsInstance(d, DurationDelta)
        self.assertEqual(d.exercise_code, "PLANK")


class TestRenderPrSummaryWithDurations(unittest.TestCase):
    def test_duration_only_format(self) -> None:
        durs = {"PLANK": DurationDelta(
            exercise_code="PLANK", unit="sec",
            prev_top_value=60, curr_top_value=90, delta=30, is_pr=True,
        )}
        result = render_pr_summary({}, {}, durs)
        self.assertIsNotNone(result)
        self.assertIn("棒式", result)
        self.assertIn("60→90 sec", result)
        self.assertIn("+30 sec", result)
        self.assertIn("PR", result)

    def test_duration_regression_no_pr(self) -> None:
        durs = {"PLANK": DurationDelta(
            exercise_code="PLANK", unit="sec",
            prev_top_value=90, curr_top_value=60, delta=-30, is_pr=False,
        )}
        result = render_pr_summary({}, {}, durs)
        self.assertIsNotNone(result)
        self.assertIn("-30 sec", result)
        self.assertNotIn("PR", result)

    def test_duration_unchanged_skipped(self) -> None:
        durs = {"PLANK": DurationDelta(
            exercise_code="PLANK", unit="sec",
            prev_top_value=60, curr_top_value=60, delta=0, is_pr=False,
        )}
        self.assertIsNone(render_pr_summary({}, {}, durs))

    def test_all_three_categories_combined(self) -> None:
        weighted = {"BENCH_PRESS": ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=47.5, curr_top_weight=50.0, weight_delta_kg=2.5,
            prev_tonnage=1520.0, curr_tonnage=1600.0, tonnage_delta=80.0,
            is_weight_pr=True,
        )}
        bw = {"PULL_UP": BwRepsDelta(
            exercise_code="PULL_UP", prev_top_reps=4, curr_top_reps=6,
            reps_delta=2, is_reps_pr=True,
        )}
        durs = {"PLANK": DurationDelta(
            exercise_code="PLANK", unit="sec",
            prev_top_value=45, curr_top_value=60, delta=15, is_pr=True,
        )}
        result = render_pr_summary(weighted, bw, durs)
        self.assertIsNotNone(result)
        for substring in ("槓鈴臥推", "引體向上", "棒式"):
            self.assertIn(substring, result)

    def test_output_order_weighted_then_bw_then_duration(self) -> None:
        weighted = {"BENCH_PRESS": ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=47.5, curr_top_weight=50.0, weight_delta_kg=2.5,
            prev_tonnage=1520.0, curr_tonnage=1600.0, tonnage_delta=80.0,
            is_weight_pr=True,
        )}
        bw = {"PULL_UP": BwRepsDelta(
            exercise_code="PULL_UP", prev_top_reps=4, curr_top_reps=6,
            reps_delta=2, is_reps_pr=True,
        )}
        durs = {"PLANK": DurationDelta(
            exercise_code="PLANK", unit="sec",
            prev_top_value=45, curr_top_value=60, delta=15, is_pr=True,
        )}
        r = render_pr_summary(weighted, bw, durs)
        # 順序: 槓鈴臥推 < 引體向上 < 棒式
        self.assertLess(r.find("槓鈴臥推"), r.find("引體向上"))
        self.assertLess(r.find("引體向上"), r.find("棒式"))

    def test_one_arg_call_still_works(self) -> None:
        # 向後相容:只傳 weighted (上上輪測試的呼叫方式)
        weighted = {"BENCH_PRESS": ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=47.5, curr_top_weight=50.0, weight_delta_kg=2.5,
            prev_tonnage=1520.0, curr_tonnage=1600.0, tonnage_delta=80.0,
            is_weight_pr=True,
        )}
        result = render_pr_summary(weighted)
        self.assertIsNotNone(result)
        self.assertIn("槓鈴臥推", result)

    def test_two_arg_call_still_works(self) -> None:
        # 向後相容:傳 weighted + bw (上輪測試的呼叫方式)
        bw = {"PULL_UP": BwRepsDelta(
            exercise_code="PULL_UP", prev_top_reps=4, curr_top_reps=6,
            reps_delta=2, is_reps_pr=True,
        )}
        result = render_pr_summary({}, bw)
        self.assertIsNotNone(result)
        self.assertIn("引體向上", result)

    def test_durations_sorted_by_delta_desc(self) -> None:
        durs = {
            "PLANK": DurationDelta(exercise_code="PLANK", unit="sec",
                                   prev_top_value=60, curr_top_value=75,
                                   delta=15, is_pr=True),
            "ROW_ERG": DurationDelta(exercise_code="ROW_ERG", unit="m",
                                     prev_top_value=500, curr_top_value=700,
                                     delta=200, is_pr=True),
        }
        r = render_pr_summary({}, {}, durs)
        # 划船機 (+200) 應排在棒式 (+15) 前面
        self.assertLess(r.find("划船機"), r.find("棒式"))


if __name__ == "__main__":
    unittest.main()
