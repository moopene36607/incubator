"""紅色測試 — per-BW-exercise 跨堂 reps progression sparkline.

已經有「加重動作的 weight progression sparkline」(test_exercise_progression.py)
和 1RM/density/RPE progression sparkline,但 BW 動作 (Pull-up / Push-up / Dips)
只能靠歷來最佳 reps PR 看一個固定數字,**沒有跨堂趨勢圖**。

本輪補上:對每個 BW 動作 (weight_kg is None + reps 是純整數),逐堂取 max reps
畫一條 sparkline,顯示「我這 N 堂 Pull-up 從 5 → 8 → 10 reps」的演進。

時間/距離型 (60 sec / 500 m) 跳過 — 那屬於 duration PR 的範疇,單位不同。
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
    compute_bw_reps_progression,
    render_bw_reps_progressions,
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


class TestComputeBwRepsProgression(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_bw_reps_progression([], "林阿明"), {})

    def test_single_session_single_bw(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("PULL_UP", 3, "5", None)])
        result = compute_bw_reps_progression([sess], "林阿明")
        self.assertEqual(result, {"PULL_UP": [("2026-05-10", 5)]})

    def test_multi_sessions_sorted_by_date(self) -> None:
        # 即使輸入順序錯亂,輸出按 date 排序
        a = _make("林阿明", 3, "2026-05-13", [_set("PULL_UP", 3, "10", None)])
        b = _make("林阿明", 1, "2026-04-22", [_set("PULL_UP", 3, "5", None)])
        c = _make("林阿明", 2, "2026-04-29", [_set("PULL_UP", 3, "7", None)])
        result = compute_bw_reps_progression([a, b, c], "林阿明")
        self.assertEqual(
            result["PULL_UP"],
            [("2026-04-22", 5), ("2026-04-29", 7), ("2026-05-13", 10)],
        )

    def test_takes_top_reps_per_session(self) -> None:
        # 同堂多個 set 不同 reps → 取 max
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PULL_UP", 1, "5", None),
            _set("PULL_UP", 1, "8", None),
            _set("PULL_UP", 1, "6", None),
        ])
        result = compute_bw_reps_progression([sess], "林阿明")
        self.assertEqual(result["PULL_UP"], [("2026-05-10", 8)])

    def test_weighted_excluded(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PULL_UP", 3, "8", None),
            _set("BENCH_PRESS", 4, "8", 50.0),
        ])
        result = compute_bw_reps_progression([sess], "林阿明")
        self.assertIn("PULL_UP", result)
        self.assertNotIn("BENCH_PRESS", result)

    def test_duration_excluded(self) -> None:
        # Plank 60 sec / Treadmill 20 min 不是 reps,跳過
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PLANK", 3, "60 sec", None),
            _set("RUN_TREADMILL", 1, "20 min", None),
            _set("PUSHUP", 3, "12", None),
        ])
        result = compute_bw_reps_progression([sess], "林阿明")
        self.assertNotIn("PLANK", result)
        self.assertNotIn("RUN_TREADMILL", result)
        self.assertIn("PUSHUP", result)

    def test_other_students_filtered(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("PULL_UP", 3, "5", None)])
        b = _make("王小華", 1, "2026-05-10", [_set("PULL_UP", 3, "20", None)])
        result = compute_bw_reps_progression([a, b], "林阿明")
        self.assertEqual(result["PULL_UP"], [("2026-05-10", 5)])


class TestRenderBwRepsProgressions(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_bw_reps_progressions({}), "")

    def test_single_point_exercise_skipped(self) -> None:
        # 只一個 data point 沒「進步」可顯示 → 跳過
        progressions = {"PULL_UP": [("2026-05-10", 5)]}
        self.assertEqual(render_bw_reps_progressions(progressions), "")

    def test_multi_point_renders_sparkline_and_delta(self) -> None:
        progressions = {
            "PULL_UP": [
                ("2026-04-22", 5),
                ("2026-04-29", 7),
                ("2026-05-13", 10),
            ],
        }
        result = render_bw_reps_progressions(progressions)
        self.assertIn("BW reps 跨堂進步", result)
        self.assertIn("引體向上", result)
        self.assertIn("5 → 10 reps", result)
        # +100% growth
        self.assertIn("+100.0%", result)
        bars = [c for c in result if c in SPARKLINE_BARS]
        self.assertGreaterEqual(len(bars), 3)

    def test_sorted_by_max_reps_desc(self) -> None:
        progressions = {
            "PULL_UP": [("2026-04-22", 5), ("2026-05-13", 8)],
            "PUSHUP": [("2026-04-22", 15), ("2026-05-13", 20)],
        }
        result = render_bw_reps_progressions(progressions)
        # Pushup max 20 > Pull-up max 8 → 伏地挺身 排在前
        self.assertLess(result.find("伏地挺身"), result.find("引體向上"))

    def test_flat_progression_renders_mid_bar(self) -> None:
        # 兩堂都 5 reps → 沒進步但有趨勢
        progressions = {
            "PULL_UP": [("2026-04-22", 5), ("2026-05-13", 5)],
        }
        result = render_bw_reps_progressions(progressions)
        self.assertIn("5 → 5 reps", result)
        # 0% delta
        self.assertIn("+0.0%", result)


class TestRenderStudentTrendIncludesBwReps(unittest.TestCase):
    def test_with_bw_progressions_kwarg_renders_section(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        progressions = {
            "PULL_UP": [
                ("2026-04-22", 5), ("2026-05-13", 8),
            ],
        }
        out = render_student_trend(trend, bw_reps_progressions=progressions)
        self.assertIn("BW reps 跨堂進步", out)
        self.assertIn("引體向上", out)


class TestCliBatchProducesBwRepsInStudentMd(unittest.TestCase):
    def test_student_md_includes_bw_reps_section(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            # 製造同學員 3 堂 Pull-up 5 → 7 → 10 reps
            for i, reps in enumerate([5, 7, 10], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                # 替換 sets 為只含 PULL_UP 一筆 BW set
                p["session"]["sets"] = [{
                    "exercise_code": "PULL_UP",
                    "sets": 3,
                    "reps_or_duration": str(reps),
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
            self.assertIn("BW reps 跨堂進步", content)
            self.assertIn("5 → 10 reps", content)


if __name__ == "__main__":
    unittest.main()
