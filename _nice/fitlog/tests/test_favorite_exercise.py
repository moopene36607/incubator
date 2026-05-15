"""紅色測試 — 學員最愛動作 (favorite exercise badge) 個性化亮點.

每位學員 _student_<name>.md 頂端可以加一個個性化亮點:
  🌟 **最常練**:槓鈴臥推 1,200 kg (23% 累積訓練量)

純函式 compute_favorite_exercise(sessions, student_name) 找該學員累積
tonnage 最大的 exercise + 占比。全 BW (tonnage 0) → None。
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
    FavoriteExercise,
    StudentTrend,
    compute_favorite_exercise,
    render_favorite_exercise,
    render_student_trend,
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


class TestComputeFavoriteExercise(unittest.TestCase):
    def test_no_sessions_returns_none(self) -> None:
        self.assertIsNone(compute_favorite_exercise([], "林阿明"))

    def test_other_students_excluded(self) -> None:
        a = _make("林阿明", 1, "2026-05-10",
                  [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("王小華", 1, "2026-05-11",
                  [_set("BB_BACK_SQUAT", 5, "5", 100.0)])
        # 林阿明 只做了 BENCH_PRESS
        result = compute_favorite_exercise([a, b], "林阿明")
        assert result is not None
        self.assertEqual(result.exercise_code, "BENCH_PRESS")

    def test_picks_highest_cumulative_tonnage(self) -> None:
        # 跨堂相同 exercise 累積。
        # session 1: BENCH 4×8×50 = 1600;SQUAT 5×5×60 = 1500
        # session 2: BENCH 4×8×55 = 1760;SQUAT 5×5×65 = 1625
        # BENCH 累積 3360 > SQUAT 累積 3125
        a = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("BB_BACK_SQUAT", 5, "5", 60.0),
        ])
        b = _make("林阿明", 2, "2026-05-13", [
            _set("BENCH_PRESS", 4, "8", 55.0),
            _set("BB_BACK_SQUAT", 5, "5", 65.0),
        ])
        result = compute_favorite_exercise([a, b], "林阿明")
        assert result is not None
        self.assertEqual(result.exercise_code, "BENCH_PRESS")
        self.assertEqual(result.total_tonnage_kg, 3360.0)

    def test_percent_correct(self) -> None:
        # 該學員總 tonnage = BENCH 1600 + SQUAT 1500 = 3100;BENCH 占 51.6%
        a = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("BB_BACK_SQUAT", 5, "5", 60.0),
        ])
        result = compute_favorite_exercise([a], "林阿明")
        assert result is not None
        self.assertEqual(result.exercise_code, "BENCH_PRESS")
        self.assertAlmostEqual(result.pct, 1600 / 3100 * 100, places=1)

    def test_all_bw_returns_none(self) -> None:
        # 全 BW (tonnage = 0) → None (沒「最愛 weighted exercise」可講)
        a = _make("林阿明", 1, "2026-05-10", [
            _set("PULL_UP", 3, "8", None),
            _set("PUSHUP", 3, "12", None),
        ])
        self.assertIsNone(compute_favorite_exercise([a], "林阿明"))


class TestRenderFavoriteExercise(unittest.TestCase):
    def test_none_returns_none_string(self) -> None:
        self.assertIsNone(render_favorite_exercise(None))

    def test_renders_chinese_name_and_pct(self) -> None:
        fav = FavoriteExercise(
            exercise_code="BENCH_PRESS", total_tonnage_kg=1600.0, pct=51.6,
        )
        line = render_favorite_exercise(fav)
        assert line is not None
        self.assertIn("🌟", line)
        self.assertIn("最常練", line)
        self.assertIn("槓鈴臥推", line)
        self.assertIn("1,600 kg", line)
        self.assertIn("52%", line)


class TestStudentTrendIncludesFavorite(unittest.TestCase):
    def test_kwarg_renders_in_trend(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        fav = FavoriteExercise(
            exercise_code="BENCH_PRESS", total_tonnage_kg=1600.0, pct=52.0,
        )
        out = render_student_trend(trend, favorite_exercise=fav)
        self.assertIn("最常練", out)
        self.assertIn("槓鈴臥推", out)


class TestCliEmitsFavorite(unittest.TestCase):
    def test_student_md_contains_favorite_line(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i in range(1, 3):
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
            self.assertIn("最常練", content)


if __name__ == "__main__":
    unittest.main()
