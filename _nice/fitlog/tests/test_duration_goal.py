"""紅色測試 — 時間/距離型目標 (target_duration).

goal 已支援 target_weight_kg (重量) 與 target_reps (BW 次數)。第三型:
時間/距離動作的目標 — 「棒式撐 120 秒」「划船機 2000 m」。本輪加
target_duration:current = 該學員歷來該動作最高 duration 值。

schema 驗證 + GoalProgress unit 用該動作的計量單位 (sec/min/m)。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import GoalProgress, compute_goal_progress, render_goal_progress  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402
from schema import validate_payload_schema  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, sno: int, date: str, code: str,
          reps: str) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code=code, sets=3,
                        reps_or_duration=reps, weight_kg=None, rpe=6)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeGoalProgressDuration(unittest.TestCase):
    def test_duration_goal_progress(self) -> None:
        # 棒式歷來最高 90 sec;目標 120 sec → 75%
        s1 = _make("林阿明", 1, "2026-05-01", "PLANK", "60 sec")
        s2 = _make("林阿明", 2, "2026-05-08", "PLANK", "90 sec")
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        result = compute_goal_progress(
            targets, {}, sessions=[s1, s2], student_name="林阿明")
        self.assertEqual(len(result), 1)
        g = result[0]
        self.assertEqual(g.exercise_code, "PLANK")
        self.assertEqual(g.unit, "sec")
        self.assertEqual(g.current_kg, 90.0)
        self.assertEqual(g.target_kg, 120.0)
        self.assertAlmostEqual(g.percent, 75.0, places=1)

    def test_duration_goal_no_data_zero_current(self) -> None:
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        result = compute_goal_progress(
            targets, {}, sessions=[], student_name="林阿明")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].current_kg, 0.0)

    def test_distance_goal_unit_m(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-08", "ROW_ERG", "1500 m")
        targets = [{"exercise_code": "ROW_ERG", "target_duration": 2000}]
        result = compute_goal_progress(
            targets, {}, sessions=[s1], student_name="林阿明")
        self.assertEqual(result[0].unit, "m")
        self.assertEqual(result[0].current_kg, 1500.0)

    def test_zero_target_duration_skipped(self) -> None:
        targets = [{"exercise_code": "PLANK", "target_duration": 0}]
        result = compute_goal_progress(
            targets, {}, sessions=[], student_name="林阿明")
        self.assertEqual(result, [])

    def test_weight_and_duration_goals_together(self) -> None:
        from aggregate import AllTimeBest
        s1 = _make("林阿明", 1, "2026-05-08", "PLANK", "100 sec")
        targets = [
            {"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0},
            {"exercise_code": "PLANK", "target_duration": 120},
        ]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=55.0,
            on_session_no=1, on_session_date="2026-05-08")}
        result = compute_goal_progress(
            targets, prs, sessions=[s1], student_name="林阿明")
        units = {g.exercise_code: g.unit for g in result}
        self.assertEqual(units["BENCH_PRESS"], "kg")
        self.assertEqual(units["PLANK"], "sec")


class TestRenderDurationGoal(unittest.TestCase):
    def test_renders_duration_unit(self) -> None:
        progress = [GoalProgress(
            exercise_code="PLANK", current_kg=90.0, target_kg=120.0,
            percent=75.0, unit="sec")]
        out = render_goal_progress(progress)
        self.assertIn("棒式", out)
        self.assertIn("90 / 120 sec", out)


class TestSchemaDurationTarget(unittest.TestCase):
    def test_target_duration_passes_schema(self) -> None:
        p = json.loads(json.dumps(SAMPLE_PAYLOAD))
        p["student"]["targets"] = [
            {"exercise_code": "PLANK", "target_duration": 120}]
        self.assertEqual(validate_payload_schema(p), [])

    def test_non_int_target_duration_rejected(self) -> None:
        p = json.loads(json.dumps(SAMPLE_PAYLOAD))
        p["student"]["targets"] = [
            {"exercise_code": "PLANK", "target_duration": "long"}]
        errors = validate_payload_schema(p)
        self.assertTrue(any("target_duration" in e for e in errors))


class TestCliDurationGoal(unittest.TestCase):
    def test_student_md_shows_duration_goal(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, dur in enumerate([60, 90], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["student"]["targets"] = [
                    {"exercise_code": "PLANK", "target_duration": 120}]
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                p["session"]["sets"] = [{
                    "exercise_code": "PLANK", "sets": 3,
                    "reps_or_duration": f"{dur} sec",
                    "weight_kg": None, "rpe": 6}]
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("90 / 120 sec", content)


if __name__ == "__main__":
    unittest.main()
