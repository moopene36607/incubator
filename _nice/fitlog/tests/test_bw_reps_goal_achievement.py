"""紅色測試 — BW reps 目標達成偵測 (補完 reps 目標的達成記錄 + banner).

round 36-37 加了 BW reps 目標的進度 % 與 ETA,但「達成偵測」還是純重量:
- compute_goal_progress 對 reps 目標不會填 achieved_on_session_no
- find_newly_achieved_goals / 單堂達成 banner 完全不認 reps 目標

本輪補完:reps 目標也能標「達成於第 N 堂」,當堂首次做到也觸發
🎉 目標達成 banner。
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
          code: str, reps: str, weight: float | None) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code=code, sets=3,
                        reps_or_duration=reps, weight_kg=weight, rpe=8)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestRepsGoalAchievementRecord(unittest.TestCase):
    def test_reps_goal_achieved_records_session(self) -> None:
        # 林阿明 第 1 堂 8 下、第 2 堂 10 下;目標 10 下 → 達成於第 2 堂
        s1 = _make("林阿明", 1, "2026-05-01", "PULL_UP", "8", None)
        s2 = _make("林阿明", 2, "2026-05-08", "PULL_UP", "10", None)
        targets = [{"exercise_code": "PULL_UP", "target_reps": 10}]
        bw_prs = {"PULL_UP": AllTimeBwBest(
            exercise_code="PULL_UP", max_reps=10,
            on_session_no=2, on_session_date="2026-05-08")}
        result = compute_goal_progress(
            targets, {}, sessions=[s1, s2], student_name="林阿明",
            bw_prs=bw_prs)
        self.assertEqual(len(result), 1)
        g = result[0]
        self.assertEqual(g.achieved_on_session_no, 2)
        self.assertEqual(g.achieved_on_date, "2026-05-08")

    def test_reps_goal_not_achieved_no_record(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-01", "PULL_UP", "8", None)
        targets = [{"exercise_code": "PULL_UP", "target_reps": 12}]
        bw_prs = {"PULL_UP": AllTimeBwBest(
            exercise_code="PULL_UP", max_reps=8,
            on_session_no=1, on_session_date="2026-05-01")}
        result = compute_goal_progress(
            targets, {}, sessions=[s1], student_name="林阿明",
            bw_prs=bw_prs)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0].achieved_on_session_no)


class TestRepsGoalSessionBanner(unittest.TestCase):
    def test_first_time_reps_goal_triggers_banner(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-01", "PULL_UP", "8", None)
        s2 = _make("林阿明", 2, "2026-05-08", "PULL_UP", "10", None)
        targets = [{"exercise_code": "PULL_UP", "target_reps": 10}]
        achs = find_newly_achieved_goals(s2, [s1, s2], targets)
        self.assertEqual(len(achs), 1)
        self.assertEqual(achs[0].exercise_code, "PULL_UP")
        banner = render_session_goal_banner(achs)
        self.assertIn("目標達成", banner)
        self.assertIn("引體向上", banner)
        self.assertIn("10", banner)
        self.assertIn("下", banner)  # reps 目標用「下」不是 kg

    def test_already_achieved_before_no_banner(self) -> None:
        # 第 1 堂就 10 下,第 2 堂也 10 下 → 第 2 堂不是「首次」
        s1 = _make("林阿明", 1, "2026-05-01", "PULL_UP", "10", None)
        s2 = _make("林阿明", 2, "2026-05-08", "PULL_UP", "10", None)
        targets = [{"exercise_code": "PULL_UP", "target_reps": 10}]
        achs = find_newly_achieved_goals(s2, [s1, s2], targets)
        self.assertEqual(achs, [])

    def test_not_reached_no_banner(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-08", "PULL_UP", "7", None)
        targets = [{"exercise_code": "PULL_UP", "target_reps": 10}]
        achs = find_newly_achieved_goals(s1, [s1], targets)
        self.assertEqual(achs, [])

    def test_weight_goal_banner_still_works(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-08", "BENCH_PRESS", "8", 60.0)
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 55.0}]
        achs = find_newly_achieved_goals(s1, [s1], targets)
        self.assertEqual(len(achs), 1)
        banner = render_session_goal_banner(achs)
        self.assertIn("kg", banner)


class TestCliRepsGoalAchievement(unittest.TestCase):
    def test_session_md_shows_reps_goal_banner(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, reps in enumerate([8, 10], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["student"]["targets"] = [
                    {"exercise_code": "PULL_UP", "target_reps": 10},
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
            s2 = (Path(out_td) / "s2.md").read_text(encoding="utf-8")
            self.assertIn("目標達成", s2)


if __name__ == "__main__":
    unittest.main()
