"""紅色測試 — per-exercise 跨堂 weight progression sparkline.

學員看 _student_<name>.md 知道「歷來最佳是 50 kg」,但不知道「我這 4
週 Bench 怎麼從 45 漲到 50」。本輪對每個加重動作畫一條 sparkline
顯示跨堂 top weight 的演變。

只算 weighted exercise (BW 排除)。每堂 session 該動作取 max weight
為當天代表值;少於 2 點的 exercise 跳過 (沒「進步」可看)。
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
    compute_exercise_progression,
    render_exercise_progressions,
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


class TestComputeExerciseProgression(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_exercise_progression([], "林阿明"), {})

    def test_single_session_single_exercise(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_exercise_progression([sess], "林阿明")
        self.assertEqual(result, {"BENCH_PRESS": [("2026-05-10", 50.0)]})

    def test_multi_sessions_sorted_by_date(self) -> None:
        # 即使輸入順序錯亂,輸出按 date 排序
        a = _make("林阿明", 3, "2026-05-13", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("林阿明", 1, "2026-04-22", [_set("BENCH_PRESS", 4, "8", 45.0)])
        c = _make("林阿明", 2, "2026-04-29", [_set("BENCH_PRESS", 4, "8", 47.5)])
        result = compute_exercise_progression([a, b, c], "林阿明")
        self.assertEqual(
            result["BENCH_PRESS"],
            [("2026-04-22", 45.0), ("2026-04-29", 47.5), ("2026-05-13", 50.0)],
        )

    def test_takes_top_weight_per_session(self) -> None:
        # 同一堂多個 set 不同重量 → 取 max
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 1, "10", 40.0),
            _set("BENCH_PRESS", 1, "8", 47.5),
            _set("BENCH_PRESS", 1, "5", 52.5),
        ])
        result = compute_exercise_progression([sess], "林阿明")
        self.assertEqual(result["BENCH_PRESS"], [("2026-05-10", 52.5)])

    def test_bw_excluded(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PULL_UP", 3, "8", None),
            _set("BENCH_PRESS", 4, "8", 50.0),
        ])
        result = compute_exercise_progression([sess], "林阿明")
        self.assertNotIn("PULL_UP", result)
        self.assertIn("BENCH_PRESS", result)

    def test_other_students_filtered(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("王小華", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 99.0)])
        result = compute_exercise_progression([a, b], "林阿明")
        self.assertEqual(result["BENCH_PRESS"], [("2026-05-10", 50.0)])


class TestRenderExerciseProgressions(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_exercise_progressions({}), "")

    def test_single_point_exercise_skipped(self) -> None:
        # 只一個 data point 沒「進步」可顯示 → 跳過
        progressions = {"BENCH_PRESS": [("2026-05-10", 50.0)]}
        result = render_exercise_progressions(progressions)
        # 全跳 → 空字串 (caller 不渲染 section)
        self.assertEqual(result, "")

    def test_multi_point_renders_sparkline_and_delta(self) -> None:
        progressions = {
            "BENCH_PRESS": [
                ("2026-04-22", 45.0),
                ("2026-04-29", 47.5),
                ("2026-05-13", 50.0),
            ],
        }
        result = render_exercise_progressions(progressions)
        self.assertIn("主要動作進度", result)
        self.assertIn("槓鈴臥推", result)
        self.assertIn("45 kg → 50 kg", result)
        self.assertIn("+11.1%", result)
        # 至少 3 個方塊字元
        bars = [c for c in result if c in SPARKLINE_BARS]
        self.assertGreaterEqual(len(bars), 3)

    def test_sorted_by_max_weight_desc(self) -> None:
        progressions = {
            "BENCH_PRESS": [("2026-04-22", 45.0), ("2026-05-13", 50.0)],
            "BB_BACK_SQUAT": [("2026-04-22", 60.0), ("2026-05-13", 70.0)],
        }
        result = render_exercise_progressions(progressions)
        # squat (70) > bench (50) → 槓鈴背蹲舉 排在前
        self.assertLess(result.find("槓鈴背蹲舉"), result.find("槓鈴臥推"))


class TestRenderStudentTrendIncludesProgressions(unittest.TestCase):
    def test_with_progressions_kwarg_renders_section(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        progressions = {
            "BENCH_PRESS": [
                ("2026-04-22", 45.0), ("2026-05-13", 50.0),
            ],
        }
        out = render_student_trend(trend, progressions=progressions)
        self.assertIn("主要動作進度", out)
        self.assertIn("槓鈴臥推", out)


class TestCliBatchProducesProgressionsInStudentMd(unittest.TestCase):
    def test_student_md_includes_per_exercise_section(self) -> None:
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
            self.assertIn("主要動作進度", content)
            self.assertIn("45 kg → 50 kg", content)


if __name__ == "__main__":
    unittest.main()
