"""紅色測試 — 訓練密度跨堂趨勢 sparkline.

Round 29 加 per-session 訓練密度 (tonnage / min)。本輪做歷史曲線:
學員看「我的訓練密度從 95→105 kg/min, +10.5%」就知道訓練變稠 (HIIT 化)
還是變稀 (傳統肌力化)。
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
    StudentTrend,
    compute_student_density_progression,
    render_density_progression,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)
SPARKLINE_BARS = "▁▂▃▄▅▆▇█"


def _make(student: str, session_no: int, date: str, duration: int,
          sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=duration,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestComputeStudentDensityProgression(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_student_density_progression([], "林阿明"), [])

    def test_single_session_one_point(self) -> None:
        # bench 50 × 4 × 8 = 1600;1600/60 = 26.67
        sess = _make("林阿明", 1, "2026-05-10", 60,
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_student_density_progression([sess], "林阿明")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "2026-05-10")
        self.assertAlmostEqual(result[0][1], 1600 / 60, places=2)

    def test_multi_sessions_sorted_by_date(self) -> None:
        # 輸入順序錯亂 → 輸出按 date 排
        c = _make("林阿明", 3, "2026-05-13", 60, [_set("BENCH_PRESS", 4, "8", 50.0)])
        a = _make("林阿明", 1, "2026-04-22", 60, [_set("BENCH_PRESS", 4, "8", 45.0)])
        b = _make("林阿明", 2, "2026-04-29", 60, [_set("BENCH_PRESS", 4, "8", 47.5)])
        result = compute_student_density_progression([c, a, b], "林阿明")
        dates = [d for d, _ in result]
        self.assertEqual(dates, ["2026-04-22", "2026-04-29", "2026-05-13"])

    def test_zero_density_session_skipped(self) -> None:
        # 全 BW (tonnage 0) → density 0 → 跳過
        sess = _make("林阿明", 1, "2026-05-10", 60,
                     [_set("PULL_UP", 4, "8", None)])
        self.assertEqual(compute_student_density_progression([sess], "林阿明"), [])

    def test_zero_duration_session_skipped(self) -> None:
        # 0 時長 → density None → 跳過
        sess = _make("林阿明", 1, "2026-05-10", 0,
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        self.assertEqual(compute_student_density_progression([sess], "林阿明"), [])

    def test_other_students_filtered(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", 60, [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("王小華", 1, "2026-05-10", 60, [_set("BENCH_PRESS", 4, "8", 99.0)])
        result = compute_student_density_progression([a, b], "林阿明")
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0][1], 1600 / 60, places=2)


class TestRenderDensityProgression(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_density_progression([]), "")

    def test_single_point_skipped(self) -> None:
        # 只 1 點 沒進步可顯示 → 整段跳過
        self.assertEqual(render_density_progression([("2026-05-10", 26.67)]), "")

    def test_multi_point_renders_with_sparkline_and_delta(self) -> None:
        points = [
            ("2026-04-22", 90.0),
            ("2026-04-29", 95.0),
            ("2026-05-13", 100.0),
        ]
        result = render_density_progression(points)
        self.assertIn("訓練密度趨勢", result)
        self.assertIn("kg/min", result)
        self.assertIn("+11.1%", result)
        bars = [c for c in result if c in SPARKLINE_BARS]
        self.assertGreaterEqual(len(bars), 3)

    def test_negative_delta_marked(self) -> None:
        points = [("2026-04-22", 100.0), ("2026-05-13", 90.0)]
        result = render_density_progression(points)
        self.assertIn("-10.0%", result)


class TestRenderStudentTrendIncludesDensityProgression(unittest.TestCase):
    def test_with_density_progression_kwarg(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        density = [("2026-04-22", 90.0), ("2026-05-13", 100.0)]
        out = render_student_trend(trend, density_progression=density)
        self.assertIn("訓練密度趨勢", out)


class TestCliBatchProducesDensityProgression(unittest.TestCase):
    def test_student_md_contains_density_trend(self) -> None:
        # 兩堂 (不同 tonnage) → 該出現「訓練密度趨勢」
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for i, w in enumerate([45.0, 50.0], 1):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = "林阿明"
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
            self.assertIn("訓練密度趨勢", content)


if __name__ == "__main__":
    unittest.main()
