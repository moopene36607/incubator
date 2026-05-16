"""紅色測試 — 時間/距離型目標達成偵測.

round 73 加了 target_duration 的進度 %,但達成偵測 (find_newly_achieved_goals
+ compute_goal_progress 的 achieved_on) 還只認重量 / BW 次數。本輪補完:
duration 目標也標「達成於第 N 堂」+ 當堂首次達標觸發 🎉 banner。
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
    compute_goal_progress,
    find_newly_achieved_goals,
    render_session_goal_banner,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, sno: int, date: str,
          code: str, reps: str) -> SessionInput:
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


class TestDurationGoalAchievementRecord(unittest.TestCase):
    def test_achieved_records_session(self) -> None:
        # 棒式 第1堂 90秒、第2堂 120秒;目標 120 → 達成於第 2 堂
        s1 = _make("林阿明", 1, "2026-05-01", "PLANK", "90 sec")
        s2 = _make("林阿明", 2, "2026-05-08", "PLANK", "120 sec")
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        result = compute_goal_progress(
            targets, {}, sessions=[s1, s2], student_name="林阿明")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].achieved_on_session_no, 2)
        self.assertEqual(result[0].achieved_on_date, "2026-05-08")

    def test_not_achieved_no_record(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-01", "PLANK", "90 sec")
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        result = compute_goal_progress(
            targets, {}, sessions=[s1], student_name="林阿明")
        self.assertIsNone(result[0].achieved_on_session_no)


class TestDurationGoalSessionBanner(unittest.TestCase):
    def test_first_time_triggers_banner(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-01", "PLANK", "90 sec")
        s2 = _make("林阿明", 2, "2026-05-08", "PLANK", "120 sec")
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        achs = find_newly_achieved_goals(s2, [s1, s2], targets)
        self.assertEqual(len(achs), 1)
        self.assertEqual(achs[0].exercise_code, "PLANK")
        banner = render_session_goal_banner(achs)
        self.assertIn("目標達成", banner)
        self.assertIn("棒式", banner)
        self.assertIn("120", banner)

    def test_already_achieved_before_no_banner(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-01", "PLANK", "120 sec")
        s2 = _make("林阿明", 2, "2026-05-08", "PLANK", "130 sec")
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        self.assertEqual(find_newly_achieved_goals(s2, [s1, s2], targets), [])

    def test_not_reached_no_banner(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-08", "PLANK", "80 sec")
        targets = [{"exercise_code": "PLANK", "target_duration": 120}]
        self.assertEqual(find_newly_achieved_goals(s1, [s1], targets), [])

    def test_distance_goal_banner(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-08", "ROW_ERG", "2200 m")
        targets = [{"exercise_code": "ROW_ERG", "target_duration": 2000}]
        achs = find_newly_achieved_goals(s1, [s1], targets)
        self.assertEqual(len(achs), 1)
        banner = render_session_goal_banner(achs)
        self.assertIn("划船機", banner)


class TestCliDurationGoalAchievement(unittest.TestCase):
    def test_session_md_shows_duration_goal_banner(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, dur in enumerate([90, 120], 1):
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
            s2 = (Path(out_td) / "s2.md").read_text(encoding="utf-8")
            self.assertIn("目標達成", s2)


if __name__ == "__main__":
    unittest.main()
