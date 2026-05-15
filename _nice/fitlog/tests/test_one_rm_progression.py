"""紅色測試 — per-exercise 估計 1RM 跨堂進步追蹤.

Round 28 加 1RM 估算 (per-session) + Round 21 加 weight progression。
本輪結合: 對每個加重動作畫一條 1RM sparkline,讓學員看「估計 1RM 從
53→63 kg, +18.3%」更直觀「真實力量」上升曲線。

per-session: 取該動作中估計 1RM 最高的 set (通常是最重那組,但不一定 —
50×5 比 50×3 估更高 1RM 因 reps 多)。
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
    compute_student_1rm_progression,
    render_1rm_progressions,
    render_student_trend,
)
from coaching import estimate_1rm  # noqa: E402
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


class TestComputeStudent1RmProgression(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_student_1rm_progression([], "林阿明"), {})

    def test_single_session_single_exercise(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_student_1rm_progression([sess], "林阿明")
        self.assertIn("BENCH_PRESS", result)
        # 只一筆: estimate_1rm(50, 8) = 60.17
        self.assertEqual(len(result["BENCH_PRESS"]), 1)
        self.assertAlmostEqual(result["BENCH_PRESS"][0][1],
                               estimate_1rm(50.0, 8), places=2)

    def test_multi_sessions_sorted_by_date(self) -> None:
        a = _make("林阿明", 3, "2026-05-13", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("林阿明", 1, "2026-04-22", [_set("BENCH_PRESS", 4, "8", 45.0)])
        c = _make("林阿明", 2, "2026-04-29", [_set("BENCH_PRESS", 4, "8", 47.5)])
        result = compute_student_1rm_progression([a, b, c], "林阿明")
        dates = [d for d, _ in result["BENCH_PRESS"]]
        self.assertEqual(dates, ["2026-04-22", "2026-04-29", "2026-05-13"])

    def test_takes_max_estimate_per_session(self) -> None:
        # 同 session 多 set: 50×8 (60.17) vs 52.5×3 (57.75) → 取 50×8 的 1RM
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 1, "3", 52.5),
            _set("BENCH_PRESS", 1, "8", 50.0),
        ])
        result = compute_student_1rm_progression([sess], "林阿明")
        self.assertAlmostEqual(result["BENCH_PRESS"][0][1],
                               estimate_1rm(50.0, 8), places=2)

    def test_bw_excluded(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PULL_UP", 3, "8", None),
            _set("BENCH_PRESS", 4, "8", 50.0),
        ])
        result = compute_student_1rm_progression([sess], "林阿明")
        self.assertNotIn("PULL_UP", result)
        self.assertIn("BENCH_PRESS", result)

    def test_high_reps_excluded(self) -> None:
        # 15 reps 超過 epley 範圍 → estimate_1rm 回 None
        sess = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "15", 50.0)])
        self.assertEqual(compute_student_1rm_progression([sess], "林阿明"), {})

    def test_other_students_filtered(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("王小華", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 99.0)])
        result = compute_student_1rm_progression([a, b], "林阿明")
        self.assertAlmostEqual(result["BENCH_PRESS"][0][1],
                               estimate_1rm(50.0, 8), places=2)


class TestRender1RmProgressions(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_1rm_progressions({}), "")

    def test_single_point_skipped(self) -> None:
        progressions = {"BENCH_PRESS": [("2026-05-10", 60.17)]}
        # 只 1 點 沒進步可顯示 → 整個 section 跳過
        self.assertEqual(render_1rm_progressions(progressions), "")

    def test_multi_point_renders_with_sparkline(self) -> None:
        progressions = {
            "BENCH_PRESS": [
                ("2026-04-22", 53.4),
                ("2026-04-29", 57.0),
                ("2026-05-13", 63.3),
            ],
        }
        result = render_1rm_progressions(progressions)
        self.assertIn("估計 1RM", result)
        self.assertIn("槓鈴臥推", result)
        bars = [c for c in result if c in SPARKLINE_BARS]
        self.assertGreaterEqual(len(bars), 3)

    def test_sorted_by_max_estimate_desc(self) -> None:
        progressions = {
            "BENCH_PRESS": [("2026-04-22", 53.4), ("2026-05-13", 63.3)],
            "BB_BACK_SQUAT": [("2026-04-22", 80.0), ("2026-05-13", 93.0)],
        }
        result = render_1rm_progressions(progressions)
        # squat (93) > bench (63) → 槓鈴背蹲舉 排前
        self.assertLess(result.find("槓鈴背蹲舉"), result.find("槓鈴臥推"))


class TestRenderStudentTrendIncludes1RmProgressions(unittest.TestCase):
    def test_with_one_rm_progressions_kwarg(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        progressions = {
            "BENCH_PRESS": [
                ("2026-04-22", 53.4), ("2026-05-13", 63.3),
            ],
        }
        out = render_student_trend(trend, one_rm_progressions=progressions)
        self.assertIn("估計 1RM", out)
        self.assertIn("槓鈴臥推", out)


class TestCliBatchProduces1RmProgression(unittest.TestCase):
    def test_student_md_includes_section(self) -> None:
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
            self.assertIn("估計 1RM 跨堂進步", content)


if __name__ == "__main__":
    unittest.main()
