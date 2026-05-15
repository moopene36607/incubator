"""紅色測試 — 學員動作多樣性 (exercise variety) 指標.

PT 看學員 trend 時想知道「他最近是在重複老 routine 還是有探索新動作?」
- 過低 → 訓練 stagnation,該換 programming
- 過高 → 沒專注,進步難量化

本輪算:
  - recent_unique:過去 N=4 堂用了幾種不同 exercise_code
  - all_time_unique:該學員歷來用過幾種不同 exercise_code

純函式 compute_exercise_variety(sessions, student_name, window=4) → ExerciseVariety | None。
< 1 堂 → None。Render 一行 "🎨 動作多樣性"。
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
    ExerciseVariety,
    StudentTrend,
    compute_exercise_variety,
    render_exercise_variety,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, sno: int, date: str,
          codes: list[str]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[
            SetRecord(exercise_code=c, sets=1, reps_or_duration="8",
                      weight_kg=50.0, rpe=7)
            for c in codes
        ],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeExerciseVariety(unittest.TestCase):
    def test_no_sessions_returns_none(self) -> None:
        self.assertIsNone(compute_exercise_variety([], "林阿明"))

    def test_other_students_excluded(self) -> None:
        a = _make("王小華", 1, "2026-05-10", ["BENCH_PRESS", "PULL_UP"])
        self.assertIsNone(compute_exercise_variety([a], "林阿明"))

    def test_single_session_counts_unique(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     ["BENCH_PRESS", "PULL_UP", "BENCH_PRESS"])
        result = compute_exercise_variety([sess], "林阿明")
        assert result is not None
        self.assertEqual(result.recent_unique, 2)
        self.assertEqual(result.all_time_unique, 2)
        self.assertEqual(result.window_sessions, 1)

    def test_recent_window_caps_at_n(self) -> None:
        # 5 堂,window=4 → 看最後 4 堂
        sessions = [
            _make("林阿明", 1, "2026-04-01", ["DEADLIFT"]),  # 不在 recent window
            _make("林阿明", 2, "2026-04-08", ["BENCH_PRESS"]),
            _make("林阿明", 3, "2026-04-15", ["PULL_UP"]),
            _make("林阿明", 4, "2026-04-22", ["BB_BACK_SQUAT"]),
            _make("林阿明", 5, "2026-04-29", ["PUSHUP"]),
        ]
        result = compute_exercise_variety(sessions, "林阿明", window=4)
        assert result is not None
        # recent 4 堂用了 BENCH_PRESS / PULL_UP / SQUAT / PUSHUP = 4 種
        self.assertEqual(result.recent_unique, 4)
        # all-time = 5 種
        self.assertEqual(result.all_time_unique, 5)
        self.assertEqual(result.window_sessions, 4)

    def test_fewer_than_window_returns_full_count(self) -> None:
        # 只 2 堂 < window 4 → recent = 2 堂的 unique 數,window_sessions=2
        sessions = [
            _make("林阿明", 1, "2026-04-08", ["BENCH_PRESS", "PULL_UP"]),
            _make("林阿明", 2, "2026-04-15", ["BENCH_PRESS", "DEADLIFT"]),
        ]
        result = compute_exercise_variety(sessions, "林阿明", window=4)
        assert result is not None
        # 2 堂 unique = BENCH_PRESS / PULL_UP / DEADLIFT = 3
        self.assertEqual(result.recent_unique, 3)
        self.assertEqual(result.all_time_unique, 3)
        self.assertEqual(result.window_sessions, 2)

    def test_sessions_sorted_by_date_for_recent_window(self) -> None:
        # 即使輸入順序亂,recent 取「最近 N 堂」
        sessions = [
            _make("林阿明", 5, "2026-04-29", ["X1"]),
            _make("林阿明", 1, "2026-04-01", ["Y1"]),  # 應被排在最前
            _make("林阿明", 4, "2026-04-22", ["X2"]),
            _make("林阿明", 2, "2026-04-08", ["Y2"]),
            _make("林阿明", 3, "2026-04-15", ["Y3"]),
        ]
        result = compute_exercise_variety(sessions, "林阿明", window=2)
        assert result is not None
        # last 2 = 2026-04-22 (X2) + 2026-04-29 (X1) → 2 種
        self.assertEqual(result.recent_unique, 2)
        self.assertEqual(result.all_time_unique, 5)


class TestRenderExerciseVariety(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(render_exercise_variety(None))

    def test_renders_with_emoji_and_counts(self) -> None:
        v = ExerciseVariety(
            recent_unique=8, all_time_unique=12, window_sessions=4,
        )
        out = render_exercise_variety(v)
        assert out is not None
        self.assertIn("🎨", out)
        self.assertIn("動作多樣性", out)
        self.assertIn("8", out)
        self.assertIn("12", out)
        self.assertIn("4", out)


class TestStudentTrendIncludesVariety(unittest.TestCase):
    def test_kwarg_appears_in_trend(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        v = ExerciseVariety(
            recent_unique=5, all_time_unique=8, window_sessions=4,
        )
        out = render_student_trend(trend, exercise_variety=v)
        self.assertIn("動作多樣性", out)


class TestCliEmitsVariety(unittest.TestCase):
    def test_student_md_contains_variety_line(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i in range(1, 4):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-1{i}"
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("動作多樣性", content)


if __name__ == "__main__":
    unittest.main()
