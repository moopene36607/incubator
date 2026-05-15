"""紅色測試 — 目標達成歷史記錄 (achieved_on_session_no / date).

學員 .md 看到 ✅ 達標 icon 但不知「哪一堂達成」是個遺憾 — 達成那一刻
是 PT/學員都該紀念的時刻 (TrueCoach 也會記)。本輪在 GoalProgress 加
兩個 optional 欄位記錄第一次達標的 session_no + date,渲染顯示
「✅ 達成於第 N 堂 (date)」。

「達成」定義: 該動作在某 session 出現過 weight >= target 的 set。
取最早達成的那一堂 (歷史意義)。
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
    AllTimeBest,
    GoalProgress,
    compute_goal_progress,
    render_goal_progress,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, session_no: int, date: str,
          sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestComputeGoalProgressAchievement(unittest.TestCase):
    def test_no_sessions_no_achievement_filled(self) -> None:
        # 不傳 sessions/student → 兩欄為 None (向後相容上輪測試)
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = compute_goal_progress(targets, {})
        self.assertIsNone(result[0].achieved_on_session_no)
        self.assertIsNone(result[0].achieved_on_date)

    def test_unachieved_target_no_date(self) -> None:
        # 給 sessions 但學員沒達標 → 仍為 None
        sessions = [_make("林阿明", 1, "2026-05-10",
                          [_set("BENCH_PRESS", 4, "8", 50.0)])]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=1, on_session_date="2026-05-10",
        )}
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = compute_goal_progress(targets, prs, sessions, "林阿明")
        self.assertIsNone(result[0].achieved_on_session_no)

    def test_achieved_target_records_session_and_date(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 47.5)]),
            _make("林阿明", 2, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)]),
        ]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=2, on_session_date="2026-05-10",
        )}
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 50.0}]
        result = compute_goal_progress(targets, prs, sessions, "林阿明")
        self.assertEqual(result[0].achieved_on_session_no, 2)
        self.assertEqual(result[0].achieved_on_date, "2026-05-10")

    def test_takes_earliest_achievement_date(self) -> None:
        # 達標兩次 (s2 達 50, s5 達 55 也 >= 50) → 取最早 s2
        sessions = [
            _make("林阿明", 1, "2026-05-01", [_set("BENCH_PRESS", 4, "8", 45.0)]),
            _make("林阿明", 2, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 50.0)]),
            _make("林阿明", 5, "2026-05-22", [_set("BENCH_PRESS", 4, "8", 55.0)]),
        ]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=55.0,
            on_session_no=5, on_session_date="2026-05-22",
        )}
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 50.0}]
        result = compute_goal_progress(targets, prs, sessions, "林阿明")
        self.assertEqual(result[0].achieved_on_session_no, 2)
        self.assertEqual(result[0].achieved_on_date, "2026-05-08")

    def test_other_students_sessions_ignored(self) -> None:
        # 王小華 s1 達標 → 不該影響林阿明的 achievement
        sessions = [
            _make("王小華", 1, "2026-05-01", [_set("BENCH_PRESS", 4, "8", 60.0)]),
            _make("林阿明", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 45.0)]),
        ]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=45.0,
            on_session_no=1, on_session_date="2026-05-08",
        )}
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 50.0}]
        result = compute_goal_progress(targets, prs, sessions, "林阿明")
        self.assertIsNone(result[0].achieved_on_session_no)

    def test_takes_max_weight_within_session(self) -> None:
        # 同 session 多 set 不同重 → 用 max 比 target
        sessions = [_make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 1, "5", 45.0),
            _set("BENCH_PRESS", 1, "3", 60.0),  # this counts
        ])]
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=60.0,
            on_session_no=1, on_session_date="2026-05-10",
        )}
        targets = [{"exercise_code": "BENCH_PRESS", "target_weight_kg": 60.0}]
        result = compute_goal_progress(targets, prs, sessions, "林阿明")
        self.assertEqual(result[0].achieved_on_session_no, 1)


class TestRenderGoalProgressShowsAchievement(unittest.TestCase):
    def test_achieved_shows_date_and_session_no(self) -> None:
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS",
            current_kg=60.0, target_kg=60.0, percent=100.0,
            achieved_on_session_no=12, achieved_on_date="2026-05-10",
        )]
        out = render_goal_progress(progress)
        self.assertIn("達成於第 12 堂", out)
        self.assertIn("2026-05-10", out)
        self.assertIn("✅", out)

    def test_unachieved_no_achievement_text(self) -> None:
        progress = [GoalProgress(
            exercise_code="BENCH_PRESS",
            current_kg=50.0, target_kg=60.0, percent=83.0,
        )]
        out = render_goal_progress(progress)
        self.assertNotIn("達成於", out)
        self.assertNotIn("✅", out)


class TestCliBatchProducesAchievementInGoals(unittest.TestCase):
    def test_student_md_shows_achievement_when_target_hit(self) -> None:
        # bench 50 target,2 堂中第 2 堂達成 → 該段含「達成於第 2 堂」
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for i, w in enumerate([45.0, 50.0], 1):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = "林阿明"
                p["student"]["targets"] = [
                    {"exercise_code": "BENCH_PRESS", "target_weight_kg": 50.0},
                ]
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                for s in p["session"]["sets"]:
                    if s["exercise_code"] == "BENCH_PRESS":
                        s["weight_kg"] = w
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("達成於第 2 堂", content)
            self.assertIn("2026-05-02", content)


if __name__ == "__main__":
    unittest.main()
