"""紅色測試 — per-duration-exercise 跨堂 sparkline.

已經有「加重動作 sparkline」(test_exercise_progression.py)、「1RM sparkline」、
「BW reps sparkline」(test_bw_reps_progression.py),但時間/距離型動作
(Plank 60→90 sec, Treadmill 15→20 min, RowErg 500→800 m) **沒有跨堂進步圖**。

本輪補上:對每個 duration 型 exercise (reps_or_duration 是 "N <unit>"),
逐堂取 max value 為當天代表值,畫一條 sparkline。

單位限定 sec/min/m/km (跟 progress.py _DURATION_UNITS 一致)。同 exercise
跨堂單位變了 → 整個 exercise 跳過 (不混 sec vs min)。少於 2 點 → 跳過。
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
    compute_duration_progression,
    render_duration_progressions,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)
SPARKLINE_BARS = "▁▂▃▄▅▆▇█"


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


class TestComputeDurationProgression(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_duration_progression([], "林阿明"), {})

    def test_single_session_plank(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("PLANK", 3, "60 sec", None)])
        result = compute_duration_progression([sess], "林阿明")
        self.assertEqual(result, {"PLANK": ("sec", [("2026-05-10", 60)])})

    def test_multi_sessions_sorted_by_date(self) -> None:
        a = _make("林阿明", 3, "2026-05-13",
                  [_set("PLANK", 3, "90 sec", None)])
        b = _make("林阿明", 1, "2026-04-22",
                  [_set("PLANK", 3, "45 sec", None)])
        c = _make("林阿明", 2, "2026-04-29",
                  [_set("PLANK", 3, "60 sec", None)])
        result = compute_duration_progression([a, b, c], "林阿明")
        unit, points = result["PLANK"]
        self.assertEqual(unit, "sec")
        self.assertEqual(points,
                         [("2026-04-22", 45), ("2026-04-29", 60),
                          ("2026-05-13", 90)])

    def test_takes_top_value_per_session(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PLANK", 1, "30 sec", None),
            _set("PLANK", 1, "60 sec", None),
            _set("PLANK", 1, "45 sec", None),
        ])
        result = compute_duration_progression([sess], "林阿明")
        _, points = result["PLANK"]
        self.assertEqual(points, [("2026-05-10", 60)])

    def test_weighted_and_int_reps_excluded(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("PULL_UP", 3, "8", None),  # BW reps,不是 duration
            _set("PLANK", 3, "60 sec", None),
        ])
        result = compute_duration_progression([sess], "林阿明")
        self.assertIn("PLANK", result)
        self.assertNotIn("BENCH_PRESS", result)
        self.assertNotIn("PULL_UP", result)

    def test_unit_change_across_sessions_skipped(self) -> None:
        # 第一堂 60 sec, 第二堂 1 min — 單位變了,整個 exercise 跳過
        a = _make("林阿明", 1, "2026-05-10",
                  [_set("PLANK", 3, "60 sec", None)])
        b = _make("林阿明", 2, "2026-05-13",
                  [_set("PLANK", 3, "1 min", None)])
        result = compute_duration_progression([a, b], "林阿明")
        self.assertNotIn("PLANK", result)

    def test_other_students_filtered(self) -> None:
        a = _make("林阿明", 1, "2026-05-10",
                  [_set("PLANK", 3, "60 sec", None)])
        b = _make("王小華", 1, "2026-05-10",
                  [_set("PLANK", 3, "120 sec", None)])
        result = compute_duration_progression([a, b], "林阿明")
        _, points = result["PLANK"]
        self.assertEqual(points, [("2026-05-10", 60)])

    def test_multi_units_distinct_exercises(self) -> None:
        # PLANK (sec) 和 RUN_TREADMILL (min) 同學員 同一堂 → 兩個都收
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PLANK", 3, "60 sec", None),
            _set("RUN_TREADMILL", 1, "20 min", None),
        ])
        # 第二堂進步
        sess2 = _make("林阿明", 2, "2026-05-13", [
            _set("PLANK", 3, "75 sec", None),
            _set("RUN_TREADMILL", 1, "25 min", None),
        ])
        result = compute_duration_progression([sess, sess2], "林阿明")
        self.assertEqual(result["PLANK"][0], "sec")
        self.assertEqual(result["RUN_TREADMILL"][0], "min")


class TestRenderDurationProgressions(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_duration_progressions({}), "")

    def test_single_point_exercise_skipped(self) -> None:
        progressions = {"PLANK": ("sec", [("2026-05-10", 60)])}
        self.assertEqual(render_duration_progressions(progressions), "")

    def test_multi_point_renders_sparkline_and_delta(self) -> None:
        progressions = {
            "PLANK": ("sec", [
                ("2026-04-22", 45),
                ("2026-04-29", 60),
                ("2026-05-13", 90),
            ]),
        }
        result = render_duration_progressions(progressions)
        self.assertIn("時間/距離跨堂進步", result)
        self.assertIn("棒式", result)
        self.assertIn("45 → 90 sec", result)
        self.assertIn("+100.0%", result)
        bars = [c for c in result if c in SPARKLINE_BARS]
        self.assertGreaterEqual(len(bars), 3)

    def test_unit_min_displayed(self) -> None:
        progressions = {
            "RUN_TREADMILL": ("min", [
                ("2026-04-22", 15),
                ("2026-05-13", 25),
            ]),
        }
        result = render_duration_progressions(progressions)
        self.assertIn("跑步機", result)
        self.assertIn("15 → 25 min", result)


class TestRenderStudentTrendIncludesDuration(unittest.TestCase):
    def test_with_duration_progressions_kwarg_renders_section(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        progressions = {
            "PLANK": ("sec", [
                ("2026-04-22", 45), ("2026-05-13", 90),
            ]),
        }
        out = render_student_trend(trend, duration_progressions=progressions)
        self.assertIn("時間/距離跨堂進步", out)
        self.assertIn("棒式", out)


class TestCliBatchProducesDurationInStudentMd(unittest.TestCase):
    def test_student_md_includes_duration_section(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, dur in enumerate([45, 60, 90], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                p["session"]["sets"] = [{
                    "exercise_code": "PLANK",
                    "sets": 3,
                    "reps_or_duration": f"{dur} sec",
                    "weight_kg": None,
                    "rpe": None,
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
            self.assertIn("時間/距離跨堂進步", content)
            self.assertIn("45 → 90 sec", content)


if __name__ == "__main__":
    unittest.main()
