"""紅色測試 — 訓練強度分數跨堂 sparkline trend.

上輪加了單堂 intensity_score (tonnage × avg_rpe/10),本輪補上跨堂
sparkline。已有 tonnage / density / RPE / 1RM / weight / BW reps / duration
等 progression sparkline 系列,intensity 是該系列最後缺的一塊。

純函式 compute_student_intensity_progression(sessions, student_name)
→ list[(date, score)]。沒 tonnage 或無 RPE 的堂跳過 (None 不能進 sparkline)。
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
    compute_student_intensity_progression,
    render_intensity_progression,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)
SPARKLINE_BARS = "▁▂▃▄▅▆▇█"


def _make(student: str, sno: int, date: str,
          sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(reps: str, weight: float | None, rpe: int | None) -> SetRecord:
    return SetRecord(exercise_code="BENCH_PRESS", sets=1,
                     reps_or_duration=reps, weight_kg=weight, rpe=rpe)


class TestComputeStudentIntensityProgression(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(
            compute_student_intensity_progression([], "林阿明"), []
        )

    def test_other_students_excluded(self) -> None:
        a = _make("王小華", 1, "2026-05-10", [_set("8", 50.0, 8)])
        self.assertEqual(
            compute_student_intensity_progression([a], "林阿明"), []
        )

    def test_single_session_score(self) -> None:
        # 1×8×50=400, RPE 8 → score 400×0.8 = 320
        sess = _make("林阿明", 1, "2026-05-10", [_set("8", 50.0, 8)])
        result = compute_student_intensity_progression([sess], "林阿明")
        self.assertEqual(result, [("2026-05-10", 320.0)])

    def test_multi_sessions_sorted_by_date(self) -> None:
        a = _make("林阿明", 3, "2026-05-13", [_set("8", 50.0, 9)])  # 360
        b = _make("林阿明", 1, "2026-04-22", [_set("8", 45.0, 7)])  # 252
        c = _make("林阿明", 2, "2026-04-29", [_set("8", 47.5, 8)])  # 304
        result = compute_student_intensity_progression([a, b, c], "林阿明")
        # 浮點乘法可能有 1e-13 級精度誤差,逐項用 assertAlmostEqual
        self.assertEqual([r[0] for r in result],
                         ["2026-04-22", "2026-04-29", "2026-05-13"])
        for actual, expected in zip([r[1] for r in result],
                                    [252.0, 304.0, 360.0]):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_all_bw_session_skipped(self) -> None:
        # 全 BW → tonnage 0 → score None → 跳過此堂
        a = _make("林阿明", 1, "2026-05-10",
                  [SetRecord(exercise_code="PULL_UP", sets=3,
                             reps_or_duration="8", weight_kg=None, rpe=7)])
        b = _make("林阿明", 2, "2026-05-13", [_set("8", 50.0, 8)])
        result = compute_student_intensity_progression([a, b], "林阿明")
        # 只剩第二堂
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "2026-05-13")

    def test_no_rpe_session_skipped(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("8", 50.0, None)])
        b = _make("林阿明", 2, "2026-05-13", [_set("8", 50.0, 8)])
        result = compute_student_intensity_progression([a, b], "林阿明")
        self.assertEqual(len(result), 1)


class TestRenderIntensityProgression(unittest.TestCase):
    def test_less_than_two_points_returns_empty(self) -> None:
        self.assertEqual(render_intensity_progression([]), "")
        self.assertEqual(
            render_intensity_progression([("2026-05-10", 320.0)]), ""
        )

    def test_multi_points_renders_sparkline_and_delta(self) -> None:
        points = [
            ("2026-04-22", 252.0),
            ("2026-04-29", 304.0),
            ("2026-05-13", 360.0),
        ]
        out = render_intensity_progression(points)
        self.assertIn("訓練強度分數趨勢", out)
        bars = [c for c in out if c in SPARKLINE_BARS]
        self.assertGreaterEqual(len(bars), 3)
        # 252 → 360 是 +42.9%
        self.assertIn("+42.9%", out)
        self.assertIn("252", out)
        self.assertIn("360", out)

    def test_flat_progression_renders_mid_bar(self) -> None:
        points = [("2026-04-22", 320.0), ("2026-05-13", 320.0)]
        out = render_intensity_progression(points)
        self.assertIn("+0.0%", out)


class TestStudentTrendIncludesIntensityProgression(unittest.TestCase):
    def test_kwarg_renders_in_trend(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        points = [("2026-04-22", 252.0), ("2026-05-13", 360.0)]
        out = render_student_trend(trend, intensity_progression=points)
        self.assertIn("訓練強度分數趨勢", out)


class TestCliEmitsIntensityProgression(unittest.TestCase):
    def test_student_md_contains_intensity_trend(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, w in enumerate([45.0, 47.5, 50.0], 1):
                p = json.loads(json.dumps(base))
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
            self.assertIn("訓練強度分數趨勢", content)


if __name__ == "__main__":
    unittest.main()
