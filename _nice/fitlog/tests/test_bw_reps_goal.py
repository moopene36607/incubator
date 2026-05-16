"""紅色測試 — BW reps 目標 (學員設「引體向上 10 下」這類非重量目標).

現有 goal 只支援 target_weight_kg。但很多學員的目標是 bodyweight 動作的
次數里程碑:「做到 10 下引體向上」「連續 20 下伏地挺身」。本輪讓
student.targets 也接受 target_reps,goal progress 用該學員歷來最高 BW
reps 算進度。

純函式:compute_goal_progress 多吃一個 bw_prs 參數;GoalProgress 加
unit 欄位 ("kg" | "reps");render 按 unit 顯示。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import (  # noqa: E402
    AllTimeBwBest,
    GoalProgress,
    compute_goal_progress,
    render_goal_progress,
)
from schema import validate_payload_schema  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


class TestComputeGoalProgressReps(unittest.TestCase):
    def test_reps_goal_with_bw_pr(self) -> None:
        targets = [{"exercise_code": "PULL_UP", "target_reps": 10}]
        bw_prs = {"PULL_UP": AllTimeBwBest(
            exercise_code="PULL_UP", max_reps=8,
            on_session_no=3, on_session_date="2026-05-10")}
        result = compute_goal_progress(targets, {}, bw_prs=bw_prs)
        self.assertEqual(len(result), 1)
        g = result[0]
        self.assertEqual(g.exercise_code, "PULL_UP")
        self.assertEqual(g.unit, "reps")
        self.assertEqual(g.current_kg, 8.0)
        self.assertEqual(g.target_kg, 10.0)
        self.assertAlmostEqual(g.percent, 80.0, places=1)

    def test_reps_goal_no_pr_yet_zero_current(self) -> None:
        targets = [{"exercise_code": "PULL_UP", "target_reps": 10}]
        result = compute_goal_progress(targets, {}, bw_prs={})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].current_kg, 0.0)
        self.assertEqual(result[0].percent, 0.0)

    def test_weight_goal_still_works(self) -> None:
        from aggregate import AllTimeBest
        targets = [{"exercise_code": "BENCH_PRESS",
                    "target_weight_kg": 60.0}]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=2, on_session_date="2026-05-01")}
        result = compute_goal_progress(targets, prs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].unit, "kg")
        self.assertEqual(result[0].current_kg, 50.0)

    def test_mixed_weight_and_reps_goals(self) -> None:
        from aggregate import AllTimeBest
        targets = [
            {"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0},
            {"exercise_code": "PULL_UP", "target_reps": 12},
        ]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=55.0,
            on_session_no=2, on_session_date="2026-05-01")}
        bw_prs = {"PULL_UP": AllTimeBwBest(
            exercise_code="PULL_UP", max_reps=6,
            on_session_no=2, on_session_date="2026-05-01")}
        result = compute_goal_progress(targets, prs, bw_prs=bw_prs)
        self.assertEqual(len(result), 2)
        units = {g.exercise_code: g.unit for g in result}
        self.assertEqual(units["BENCH_PRESS"], "kg")
        self.assertEqual(units["PULL_UP"], "reps")

    def test_zero_target_reps_skipped(self) -> None:
        targets = [{"exercise_code": "PULL_UP", "target_reps": 0}]
        self.assertEqual(compute_goal_progress(targets, {}, bw_prs={}), [])


class TestRenderGoalProgressReps(unittest.TestCase):
    def test_reps_goal_renders_reps_unit(self) -> None:
        progress = [GoalProgress(
            exercise_code="PULL_UP", current_kg=8.0, target_kg=10.0,
            percent=80.0, unit="reps")]
        out = render_goal_progress(progress)
        self.assertIn("引體向上", out)
        self.assertIn("8 / 10 reps", out)
        self.assertIn("80%", out)

    def test_weight_goal_renders_kg_unit(self) -> None:
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS", current_kg=50.0, target_kg=60.0,
            percent=83.0, unit="kg")]
        out = render_goal_progress(progress)
        self.assertIn("kg", out)
        self.assertNotIn("reps", out)


class TestSchemaAcceptsTargetReps(unittest.TestCase):
    def test_target_reps_passes_schema(self) -> None:
        payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
        payload["student"]["targets"] = [
            {"exercise_code": "PULL_UP", "target_reps": 10},
        ]
        errors = validate_payload_schema(payload)
        self.assertEqual(errors, [], f"target_reps 應通過 schema: {errors}")

    def test_target_with_neither_weight_nor_reps_fails(self) -> None:
        payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
        payload["student"]["targets"] = [
            {"exercise_code": "PULL_UP"},
        ]
        errors = validate_payload_schema(payload)
        self.assertTrue(errors, "target 沒 weight 也沒 reps 應該報錯")


class TestCliRepsGoal(unittest.TestCase):
    def test_student_md_shows_reps_goal(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, reps in enumerate([5, 8], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["student"]["targets"] = [
                    {"exercise_code": "PULL_UP", "target_reps": 12},
                ]
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                p["session"]["sets"] = [{
                    "exercise_code": "PULL_UP", "sets": 3,
                    "reps_or_duration": str(reps),
                    "weight_kg": None, "rpe": 8,
                }]
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("8 / 12 reps", content)


if __name__ == "__main__":
    unittest.main()
