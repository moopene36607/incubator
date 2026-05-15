"""紅色測試 — Epley 1RM 估算 + per-session 渲染.

Epley 公式 (健身圈最常用): 1RM = weight × (1 + reps/30)
- reps 在 1-12 範圍內可靠;>12 極不準 → 不估
- BW (weight=None) 不估;reps 非純整數 (60 sec) 不估
- per-exercise 取 max estimated 1RM 為該動作代表值

整合進兩 renderer:
- markdown: "**估計 1RM (Epley)**: 槓鈴臥推 ~ 67 kg · 槓鈴背蹲舉 ~ 93 kg"
- LINE: "💪 1RM 估:..."
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coaching import (  # noqa: E402
    compute_session_1rm_estimates,
    estimate_1rm,
    render_1rm_estimates,
)
from fitlog import (  # noqa: E402
    SetRecord,
    parse_payload,
    render_full_report,
    render_line_friendly,
    render_skeleton_body,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _set(code: str, sets: int, reps: str, weight: float | None,
         rpe: int | None = 7) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe)


def _load_sample():
    p = PROJECT_ROOT / "samples" / "sample_input.json"
    return parse_payload(json.loads(p.read_text(encoding="utf-8")))


class TestEstimate1Rm(unittest.TestCase):
    def test_50_reps_10_epley_66_67(self) -> None:
        # 50 × (1 + 10/30) = 50 × 1.3333 = 66.67
        self.assertAlmostEqual(estimate_1rm(50.0, 10), 66.67, places=1)

    def test_47_5_reps_8_epley(self) -> None:
        # 47.5 × (1 + 8/30) = 47.5 × 1.2667 = 60.17
        self.assertAlmostEqual(estimate_1rm(47.5, 8), 60.17, places=1)

    def test_reps_1_returns_close_to_weight(self) -> None:
        # 50 × (1 + 1/30) = 51.67
        self.assertAlmostEqual(estimate_1rm(50.0, 1), 51.67, places=1)

    def test_reps_12_at_boundary_returns_estimate(self) -> None:
        # 50 × (1 + 12/30) = 70
        self.assertAlmostEqual(estimate_1rm(50.0, 12), 70.0, places=1)

    def test_reps_above_12_returns_none(self) -> None:
        # >12 reps Epley 公式不可靠 → 不估
        self.assertIsNone(estimate_1rm(50.0, 13))
        self.assertIsNone(estimate_1rm(50.0, 100))

    def test_reps_zero_returns_none(self) -> None:
        self.assertIsNone(estimate_1rm(50.0, 0))

    def test_negative_weight_returns_none(self) -> None:
        self.assertIsNone(estimate_1rm(-10.0, 5))


class TestComputeSession1RmEstimates(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(compute_session_1rm_estimates([]), {})

    def test_single_weighted_set(self) -> None:
        sets = [_set("BENCH_PRESS", 4, "8", 50.0)]
        result = compute_session_1rm_estimates(sets)
        self.assertIn("BENCH_PRESS", result)
        self.assertAlmostEqual(result["BENCH_PRESS"], estimate_1rm(50.0, 8), places=2)

    def test_takes_max_estimate_across_sets(self) -> None:
        # 同 exercise 不同 set: 取 estimated 1RM 最高那組
        sets = [
            _set("BENCH_PRESS", 1, "10", 40.0),  # 40 × 1.333 = 53.3
            _set("BENCH_PRESS", 1, "5", 50.0),    # 50 × 1.167 = 58.3
            _set("BENCH_PRESS", 1, "3", 52.5),    # 52.5 × 1.1 = 57.75
        ]
        result = compute_session_1rm_estimates(sets)
        # set 2 (50×5) 估 58.3 為 max
        self.assertAlmostEqual(result["BENCH_PRESS"], estimate_1rm(50.0, 5), places=1)

    def test_bw_excluded(self) -> None:
        sets = [_set("PULL_UP", 3, "8", None), _set("BENCH_PRESS", 4, "8", 50.0)]
        result = compute_session_1rm_estimates(sets)
        self.assertNotIn("PULL_UP", result)
        self.assertIn("BENCH_PRESS", result)

    def test_time_based_excluded(self) -> None:
        # PLANK 60 sec 不是純整數 → 不估
        sets = [_set("PLANK", 3, "60 sec", None)]
        self.assertEqual(compute_session_1rm_estimates(sets), {})

    def test_high_reps_excluded(self) -> None:
        # 15 reps 超過 epley 可靠範圍 → 跳過
        sets = [_set("BENCH_PRESS", 4, "15", 50.0)]
        self.assertEqual(compute_session_1rm_estimates(sets), {})


class TestRender1RmEstimates(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(render_1rm_estimates({}))

    def test_single_format(self) -> None:
        result = render_1rm_estimates({"BENCH_PRESS": 60.17})
        self.assertIsNotNone(result)
        self.assertIn("估計 1RM", result)
        self.assertIn("Epley", result)
        self.assertIn("槓鈴臥推", result)

    def test_sorted_by_estimate_desc(self) -> None:
        estimates = {"BENCH_PRESS": 60.0, "BB_BACK_SQUAT": 90.0}
        result = render_1rm_estimates(estimates)
        # squat 90 > bench 60 → 槓鈴背蹲舉 排在前
        self.assertLess(result.find("槓鈴背蹲舉"), result.find("槓鈴臥推"))

    def test_rounded_to_kg(self) -> None:
        # estimate 60.17 → 顯示 "60 kg" 或 "60.2 kg" — 需要乾淨的 kg 顯示
        result = render_1rm_estimates({"BENCH_PRESS": 60.17})
        # 至少含 "60" 與 "kg"
        self.assertIn("60", result)
        self.assertIn("kg", result)


class TestReportIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _load_sample()
        self.body = render_skeleton_body()

    def test_markdown_includes_1rm_when_passed(self) -> None:
        one_rm = render_1rm_estimates(compute_session_1rm_estimates(self.session.sets))
        out = render_full_report(self.session, self.body, one_rm_summary=one_rm)
        self.assertIn("估計 1RM", out)

    def test_line_includes_1rm_when_passed(self) -> None:
        one_rm = render_1rm_estimates(compute_session_1rm_estimates(self.session.sets))
        out = render_line_friendly(self.session, self.body, one_rm_summary=one_rm)
        # LINE 版用「💪 1RM 估」前綴
        self.assertIn("1RM", out)


if __name__ == "__main__":
    unittest.main()
