"""紅色測試 — 學員 avg RPE 跨堂趨勢 sparkline.

學員 .md 已有 tonnage / density / 1RM / per-exercise 各自 sparkline。
本輪加 avg RPE 跨堂趨勢:看學員訓練強度演變 (越來越緊 vs 越來越輕鬆)。

Per-session avg RPE: 該堂所有有 RPE 的 set 平均。
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
    compute_student_rpe_progression,
    render_rpe_progression,
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


def _set(code: str, sets: int, reps: str, weight: float | None,
         rpe: int | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe)


class TestComputeStudentRpeProgression(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_student_rpe_progression([], "林阿明"), [])

    def test_single_session_avg_rpe(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 4, "8", 50.0, 7),
            _set("OHP", 4, "8", 30.0, 9),
        ])
        result = compute_student_rpe_progression([sess], "林阿明")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "2026-05-10")
        self.assertEqual(result[0][1], 8.0)  # (7+9)/2

    def test_multi_sessions_sorted_by_date(self) -> None:
        c = _make("林阿明", 3, "2026-05-13", [_set("BENCH_PRESS", 4, "8", 50.0, 9)])
        a = _make("林阿明", 1, "2026-04-22", [_set("BENCH_PRESS", 4, "8", 50.0, 7)])
        b = _make("林阿明", 2, "2026-04-29", [_set("BENCH_PRESS", 4, "8", 50.0, 8)])
        result = compute_student_rpe_progression([c, a, b], "林阿明")
        dates = [d for d, _ in result]
        self.assertEqual(dates, ["2026-04-22", "2026-04-29", "2026-05-13"])
        rpes = [r for _, r in result]
        self.assertEqual(rpes, [7.0, 8.0, 9.0])

    def test_no_rpe_session_skipped(self) -> None:
        # 全 set 沒 RPE → 該堂無 avg → 跳過 (不要 0 誤導)
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0, None)])
        self.assertEqual(compute_student_rpe_progression([sess], "林阿明"), [])

    def test_partial_rpe_uses_only_set_with_rpe(self) -> None:
        # 一些 set 有 RPE, 一些沒 → 只算有 RPE 的
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 4, "8", 50.0, 8),
            _set("OHP", 4, "8", 30.0, None),
        ])
        result = compute_student_rpe_progression([sess], "林阿明")
        self.assertEqual(result[0][1], 8.0)

    def test_other_students_filtered(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0, 7)])
        b = _make("王小華", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 99.0, 10)])
        result = compute_student_rpe_progression([a, b], "林阿明")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 7.0)


class TestRenderRpeProgression(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(render_rpe_progression([]), "")

    def test_single_point_skipped(self) -> None:
        # 只 1 點 沒進步可講 → ""
        self.assertEqual(render_rpe_progression([("2026-05-10", 7.0)]), "")

    def test_multi_point_renders_sparkline_and_delta(self) -> None:
        points = [
            ("2026-04-22", 7.0),
            ("2026-04-29", 8.0),
            ("2026-05-13", 9.0),
        ]
        result = render_rpe_progression(points)
        self.assertIn("RPE", result)
        self.assertIn("7.0", result)
        self.assertIn("9.0", result)
        bars = [c for c in result if c in SPARKLINE_BARS]
        self.assertGreaterEqual(len(bars), 3)


class TestRenderStudentTrendIncludesRpeProgression(unittest.TestCase):
    def test_with_rpe_progression_kwarg(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        rpe = [("2026-04-22", 7.0), ("2026-05-13", 9.0)]
        out = render_student_trend(trend, rpe_progression=rpe)
        self.assertIn("RPE", out)


class TestCliBatchProducesRpeProgression(unittest.TestCase):
    def test_student_md_includes_rpe_trend(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for i, rpe in enumerate([7, 8, 9], 1):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                for s in p["session"]["sets"]:
                    if s.get("rpe") is not None:
                        s["rpe"] = rpe
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("RPE", content)
            # 至少 RPE 7 → 9 progression 該被反映
            self.assertIn("9.0", content)


if __name__ == "__main__":
    unittest.main()
