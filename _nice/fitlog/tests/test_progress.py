"""紅色測試 — 跨堂進步追蹤 (PR / 噸位 delta) 純函式.

PT 留學員的「招牌話術」是「上週你 47.5 kg 卡關 3 堂,本週直接 50 kg 完成,
這就是 PR」。這在 TrueCoach 是核心留存功能,fitlog 必須有。

核心規則:
- 只比對「兩堂課都做過」的 exercise_code
- 重量 PR = curr top weight > prev top weight
- 同重量但組數/次數加 → 噸位 delta
- BW 動作 (weight_kg=None) 跳過 (本輪只做加權對比;reps PR 留下輪)
- 退步也要顯示 (但不是 PR,要讓教練看到並處理)
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SetRecord  # noqa: E402
from progress import (  # noqa: E402
    ProgressDelta,
    compute_pr_deltas,
    render_pr_summary,
)


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestComputePrDeltas(unittest.TestCase):
    def test_no_overlap_returns_empty(self) -> None:
        prev = [_set("BENCH_PRESS", 4, "8", 50.0)]
        curr = [_set("BB_BACK_SQUAT", 4, "10", 70.0)]
        self.assertEqual(compute_pr_deltas(prev, curr), {})

    def test_empty_prev_returns_empty(self) -> None:
        self.assertEqual(compute_pr_deltas([], [_set("BENCH_PRESS", 4, "8", 50.0)]), {})

    def test_single_overlap_weight_pr(self) -> None:
        prev = [_set("BENCH_PRESS", 4, "8", 47.5)]
        curr = [_set("BENCH_PRESS", 4, "8", 50.0)]
        result = compute_pr_deltas(prev, curr)
        self.assertIn("BENCH_PRESS", result)
        d = result["BENCH_PRESS"]
        self.assertEqual(d.prev_top_weight, 47.5)
        self.assertEqual(d.curr_top_weight, 50.0)
        self.assertAlmostEqual(d.weight_delta_kg, 2.5)
        self.assertTrue(d.is_weight_pr)

    def test_weight_unchanged_tonnage_up(self) -> None:
        # 同重量 50 kg, prev 3×8=1200, curr 4×8=1600 → 噸位 +400
        prev = [_set("BENCH_PRESS", 3, "8", 50.0)]
        curr = [_set("BENCH_PRESS", 4, "8", 50.0)]
        d = compute_pr_deltas(prev, curr)["BENCH_PRESS"]
        self.assertEqual(d.weight_delta_kg, 0.0)
        self.assertFalse(d.is_weight_pr)
        self.assertAlmostEqual(d.tonnage_delta, 400.0)

    def test_weight_regression(self) -> None:
        # 退步: 50 → 47.5
        prev = [_set("BENCH_PRESS", 4, "8", 50.0)]
        curr = [_set("BENCH_PRESS", 4, "8", 47.5)]
        d = compute_pr_deltas(prev, curr)["BENCH_PRESS"]
        self.assertAlmostEqual(d.weight_delta_kg, -2.5)
        self.assertFalse(d.is_weight_pr)

    def test_uses_max_weight_across_multiple_sets(self) -> None:
        # 同 exercise 多 set 不同重量 → 取 max 為 top weight
        prev = [
            _set("BENCH_PRESS", 1, "10", 40.0),
            _set("BENCH_PRESS", 1, "8", 47.5),
            _set("BENCH_PRESS", 1, "5", 50.0),  # top
        ]
        curr = [_set("BENCH_PRESS", 1, "5", 52.5)]
        d = compute_pr_deltas(prev, curr)["BENCH_PRESS"]
        self.assertEqual(d.prev_top_weight, 50.0)
        self.assertEqual(d.curr_top_weight, 52.5)

    def test_bodyweight_only_exercise_skipped(self) -> None:
        # 兩堂都是 BW pull-up → weight delta 算不出來,本輪跳過
        prev = [_set("PULL_UP", 3, "6", None)]
        curr = [_set("PULL_UP", 3, "8", None)]
        self.assertEqual(compute_pr_deltas(prev, curr), {})

    def test_one_side_bw_other_weighted_skipped(self) -> None:
        # prev 是 BW pull-up,curr 加負重 → 不對比 (訓練性質改變)
        prev = [_set("PULL_UP", 3, "8", None)]
        curr = [_set("PULL_UP", 3, "5", 10.0)]
        self.assertEqual(compute_pr_deltas(prev, curr), {})

    def test_returns_progress_delta_dataclass(self) -> None:
        prev = [_set("BENCH_PRESS", 4, "8", 47.5)]
        curr = [_set("BENCH_PRESS", 4, "8", 50.0)]
        d = compute_pr_deltas(prev, curr)["BENCH_PRESS"]
        self.assertIsInstance(d, ProgressDelta)
        self.assertEqual(d.exercise_code, "BENCH_PRESS")


class TestRenderPrSummary(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(render_pr_summary({}))

    def test_single_pr_format(self) -> None:
        d = ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=47.5, curr_top_weight=50.0, weight_delta_kg=2.5,
            prev_tonnage=1520.0, curr_tonnage=1600.0, tonnage_delta=80.0,
            is_weight_pr=True,
        )
        result = render_pr_summary({"BENCH_PRESS": d})
        # 期望:**進步亮點**: 槓鈴臥推 47.5→50 kg (+2.5 kg PR)
        self.assertIsNotNone(result)
        self.assertIn("槓鈴臥推", result)
        self.assertIn("47.5→50 kg", result)
        self.assertIn("+2.5 kg", result)
        self.assertIn("PR", result)

    def test_regression_marked_without_pr_label(self) -> None:
        d = ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=50.0, curr_top_weight=47.5, weight_delta_kg=-2.5,
            prev_tonnage=1600.0, curr_tonnage=1520.0, tonnage_delta=-80.0,
            is_weight_pr=False,
        )
        result = render_pr_summary({"BENCH_PRESS": d})
        self.assertIsNotNone(result)
        self.assertIn("-2.5 kg", result)
        self.assertNotIn("PR", result)

    def test_unchanged_weight_with_tonnage_up_shows_volume_delta(self) -> None:
        d = ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=50.0, curr_top_weight=50.0, weight_delta_kg=0.0,
            prev_tonnage=1200.0, curr_tonnage=1600.0, tonnage_delta=400.0,
            is_weight_pr=False,
        )
        result = render_pr_summary({"BENCH_PRESS": d})
        self.assertIsNotNone(result)
        self.assertIn("噸位", result)
        self.assertIn("+400 kg", result)

    def test_unchanged_everything_skipped(self) -> None:
        # 重量持平 + 噸位持平 → 沒進步可講,跳過 (整個 dict 變空 → None)
        d = ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=50.0, curr_top_weight=50.0, weight_delta_kg=0.0,
            prev_tonnage=1600.0, curr_tonnage=1600.0, tonnage_delta=0.0,
            is_weight_pr=False,
        )
        self.assertIsNone(render_pr_summary({"BENCH_PRESS": d}))

    def test_multiple_sorted_by_weight_delta_desc(self) -> None:
        d_squat = ProgressDelta(
            exercise_code="BB_BACK_SQUAT",
            prev_top_weight=65.0, curr_top_weight=70.0, weight_delta_kg=5.0,
            prev_tonnage=2600.0, curr_tonnage=2800.0, tonnage_delta=200.0,
            is_weight_pr=True,
        )
        d_bench = ProgressDelta(
            exercise_code="BENCH_PRESS",
            prev_top_weight=47.5, curr_top_weight=50.0, weight_delta_kg=2.5,
            prev_tonnage=1520.0, curr_tonnage=1600.0, tonnage_delta=80.0,
            is_weight_pr=True,
        )
        result = render_pr_summary({"BENCH_PRESS": d_bench, "BB_BACK_SQUAT": d_squat})
        # squat (+5) 應該排在 bench (+2.5) 前面
        self.assertLess(result.find("槓鈴背蹲舉"), result.find("槓鈴臥推"))


class TestCliPrevFlag(unittest.TestCase):
    def test_cli_prev_flag_runs_and_includes_pr_in_output(self) -> None:
        import subprocess
        import tempfile
        project_root = Path(__file__).resolve().parent.parent
        # 做一份 prev session: bench 47.5 kg
        prev_payload = json.loads(
            (project_root / "samples" / "sample_input.json").read_text(encoding="utf-8")
        )
        # 把 bench 改成 47.5 kg 模擬「上次卡關」
        for s in prev_payload["session"]["sets"]:
            if s.get("exercise_code") == "BENCH_PRESS":
                s["weight_kg"] = 47.5
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", encoding="utf-8",
                                         delete=False, dir=str(project_root)) as f:
            json.dump(prev_payload, f, ensure_ascii=False)
            prev_path = f.name
        try:
            with tempfile.NamedTemporaryFile(suffix=".md", mode="r", encoding="utf-8",
                                             delete=False) as md:
                out_path = md.name
            result = subprocess.run(
                [sys.executable, "fitlog.py",
                 "samples/sample_input.json",
                 "--no-ai",
                 "--prev", prev_path,
                 "--out", out_path],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = Path(out_path).read_text(encoding="utf-8")
            self.assertIn("進步亮點", content)
            self.assertIn("槓鈴臥推", content)
            self.assertIn("PR", content)
        finally:
            Path(prev_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
