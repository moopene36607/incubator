"""紅色測試 — 結構化學員目標 + 達成 % + progress bar 視覺化.

學員 .md 顯示「Bench 50 / 60 kg = 83% ████████░░」這種 progress bar
是 SaaS 健身工具最賣的功能 (TrueCoach / My PT Hub 都有)。本輪在
schema 加 optional `student.targets: list[{exercise_code, target_weight_kg}]`,
純函式算進度,渲染成 progress bar section 進 _student_<name>.md。

達成 100% 時加 ✅ icon。超過 100% (學員自己練超過目標) 不破版。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import (  # noqa: E402
    AllTimeBest,
    GoalProgress,
    StudentTrend,
    compute_goal_progress,
    render_goal_progress,
    render_student_trend,
)
from fitlog import parse_payload  # noqa: E402
from schema import validate_payload_schema  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


class TestSchemaTargets(unittest.TestCase):
    def test_no_targets_field_passes(self) -> None:
        # targets 是 optional → 不存在不該報錯
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"].pop("targets", None)
        self.assertEqual(validate_payload_schema(p), [])

    def test_empty_targets_list_passes(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"]["targets"] = []
        self.assertEqual(validate_payload_schema(p), [])

    def test_valid_targets_passes(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"]["targets"] = [
            {"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0},
            {"exercise_code": "BB_BACK_SQUAT", "target_weight_kg": 100.0},
        ]
        self.assertEqual(validate_payload_schema(p), [])

    def test_targets_not_list_flagged(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"]["targets"] = "not a list"
        result = validate_payload_schema(p)
        self.assertTrue(any("targets" in e for e in result), result)

    def test_target_missing_exercise_code_flagged(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"]["targets"] = [{"target_weight_kg": 60.0}]
        result = validate_payload_schema(p)
        self.assertTrue(any("exercise_code" in e for e in result), result)

    def test_target_missing_weight_flagged(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"]["targets"] = [{"exercise_code": "BENCH_PRESS"}]
        result = validate_payload_schema(p)
        self.assertTrue(any("target_weight_kg" in e for e in result), result)


class TestParsePayloadReadsTargets(unittest.TestCase):
    def test_targets_default_empty_list(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"].pop("targets", None)
        sess = parse_payload(p)
        self.assertEqual(sess.student_targets, [])

    def test_targets_parsed_into_session(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"]["targets"] = [
            {"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0},
        ]
        sess = parse_payload(p)
        self.assertEqual(len(sess.student_targets), 1)
        self.assertEqual(sess.student_targets[0]["exercise_code"], "BENCH_PRESS")


class TestComputeGoalProgress(unittest.TestCase):
    def test_empty_targets_returns_empty(self) -> None:
        self.assertEqual(compute_goal_progress([], {}), [])

    def test_target_with_no_pr_yet_zero_percent(self) -> None:
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        prs: dict[str, AllTimeBest] = {}
        result = compute_goal_progress(targets, prs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].current_kg, 0.0)
        self.assertEqual(result[0].target_kg, 60.0)
        self.assertEqual(result[0].percent, 0.0)

    def test_partial_progress(self) -> None:
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=4, on_session_date="2026-05-13",
        )}
        result = compute_goal_progress(targets, prs)
        self.assertAlmostEqual(result[0].percent, 100 * 50 / 60, places=1)

    def test_achieved_at_exactly_100(self) -> None:
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 50.0}]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=4, on_session_date="2026-05-13",
        )}
        result = compute_goal_progress(targets, prs)
        self.assertEqual(result[0].percent, 100.0)

    def test_exceeded_target(self) -> None:
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 40.0}]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=4, on_session_date="2026-05-13",
        )}
        result = compute_goal_progress(targets, prs)
        self.assertGreater(result[0].percent, 100.0)

    def test_invalid_target_skipped(self) -> None:
        # target_weight_kg=0 不合理 → 跳過 (避免 div by zero)
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 0.0}]
        result = compute_goal_progress(targets, {})
        self.assertEqual(result, [])

    def test_returns_goal_progress_dataclass(self) -> None:
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = compute_goal_progress(targets, {})
        self.assertIsInstance(result[0], GoalProgress)


class TestRenderGoalProgress(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_goal_progress([]), "")

    def test_single_progress_bar_format(self) -> None:
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS",
            current_kg=50.0, target_kg=60.0, percent=83.333,
        )]
        out = render_goal_progress(progress)
        self.assertIn("目標達成進度", out)
        self.assertIn("槓鈴臥推", out)
        self.assertIn("50 kg", out)
        self.assertIn("60 kg", out)
        self.assertIn("83%", out)
        # 至少有方塊填充字元
        self.assertTrue(any(c in out for c in "█░"))

    def test_achieved_marked_with_check_icon(self) -> None:
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS",
            current_kg=60.0, target_kg=60.0, percent=100.0,
        )]
        out = render_goal_progress(progress)
        self.assertIn("✅", out)

    def test_unachieved_no_check_icon(self) -> None:
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS",
            current_kg=50.0, target_kg=60.0, percent=83.333,
        )]
        out = render_goal_progress(progress)
        self.assertNotIn("✅", out)

    def test_sorted_by_percent_desc(self) -> None:
        progress = [
            GoalProgress(exercise_code="BENCH_PRESS",
                         current_kg=50.0, target_kg=60.0, percent=83.0),
            GoalProgress(exercise_code="BB_BACK_SQUAT",
                         current_kg=70.0, target_kg=80.0, percent=87.5),
        ]
        out = render_goal_progress(progress)
        # squat 87.5% 該排在 bench 83% 前
        self.assertLess(out.find("槓鈴背蹲舉"), out.find("槓鈴臥推"))


class TestRenderStudentTrendIncludesGoals(unittest.TestCase):
    def test_with_goals_kwarg_renders_section(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        goals = [GoalProgress(exercise_code="BENCH_PRESS",
                              current_kg=50.0, target_kg=60.0, percent=83.0)]
        out = render_student_trend(trend, goals=goals)
        self.assertIn("目標達成進度", out)
        self.assertIn("83%", out)


class TestCliBatchProducesGoalsInStudentMd(unittest.TestCase):
    def test_student_md_with_targets_includes_goals_section(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            base["student"]["name"] = "林阿明"
            base["student"]["targets"] = [
                {"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0},
            ]
            (Path(in_td) / "s1.json").write_text(
                json.dumps(base, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("目標達成進度", content)
            self.assertIn("60 kg", content)


if __name__ == "__main__":
    unittest.main()
