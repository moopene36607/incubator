"""紅色測試 — 學員體重跨堂趨勢 sparkline.

round 49 加了 session.bodyweight_kg。本輪補上時序視角:學員體重跨堂
sparkline,讓 PT 看增肌/減脂進程。只有有記體重的 session 進圖。

純函式 compute_bodyweight_progression(sessions, student) → list[(date, kg)]。
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
    compute_bodyweight_progression,
    render_bodyweight_progression,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)
SPARKLINE_BARS = "▁▂▃▄▅▆▇█"


def _make(student: str, sno: int, date: str,
          bw: float | None) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=50.0, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
        student_bodyweight_kg=bw,
    )


class TestComputeBodyweightProgression(unittest.TestCase):
    def test_no_sessions_empty(self) -> None:
        self.assertEqual(compute_bodyweight_progression([], "林阿明"), [])

    def test_sessions_without_bodyweight_skipped(self) -> None:
        sessions = [_make("林阿明", 1, "2026-05-10", None)]
        self.assertEqual(compute_bodyweight_progression(sessions, "林阿明"), [])

    def test_single_session(self) -> None:
        sessions = [_make("林阿明", 1, "2026-05-10", 72.0)]
        self.assertEqual(
            compute_bodyweight_progression(sessions, "林阿明"),
            [("2026-05-10", 72.0)],
        )

    def test_multi_sorted_by_date(self) -> None:
        sessions = [
            _make("林阿明", 3, "2026-05-13", 70.0),
            _make("林阿明", 1, "2026-04-22", 73.0),
            _make("林阿明", 2, "2026-05-01", 71.5),
        ]
        self.assertEqual(
            compute_bodyweight_progression(sessions, "林阿明"),
            [("2026-04-22", 73.0), ("2026-05-01", 71.5),
             ("2026-05-13", 70.0)],
        )

    def test_mixed_some_without_bodyweight(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-04-22", 73.0),
            _make("林阿明", 2, "2026-05-01", None),
            _make("林阿明", 3, "2026-05-13", 71.0),
        ]
        result = compute_bodyweight_progression(sessions, "林阿明")
        self.assertEqual(result, [("2026-04-22", 73.0), ("2026-05-13", 71.0)])

    def test_other_students_excluded(self) -> None:
        sessions = [
            _make("王小華", 1, "2026-04-22", 99.0),
            _make("林阿明", 1, "2026-04-22", 70.0),
        ]
        self.assertEqual(
            compute_bodyweight_progression(sessions, "林阿明"),
            [("2026-04-22", 70.0)],
        )

    def test_zero_bodyweight_skipped(self) -> None:
        sessions = [_make("林阿明", 1, "2026-05-10", 0.0)]
        self.assertEqual(compute_bodyweight_progression(sessions, "林阿明"), [])


class TestRenderBodyweightProgression(unittest.TestCase):
    def test_less_than_two_points_empty(self) -> None:
        self.assertEqual(render_bodyweight_progression([]), "")
        self.assertEqual(
            render_bodyweight_progression([("2026-05-10", 72.0)]), "")

    def test_renders_sparkline_and_delta(self) -> None:
        points = [
            ("2026-04-22", 73.0),
            ("2026-05-01", 71.5),
            ("2026-05-13", 70.0),
        ]
        out = render_bodyweight_progression(points)
        self.assertIn("體重趨勢", out)
        bars = [c for c in out if c in SPARKLINE_BARS]
        self.assertGreaterEqual(len(bars), 3)
        self.assertIn("73", out)
        self.assertIn("70", out)
        # 73 → 70 是 -4.1%
        self.assertIn("-4.1%", out)

    def test_flat_progression(self) -> None:
        points = [("2026-04-22", 70.0), ("2026-05-13", 70.0)]
        out = render_bodyweight_progression(points)
        self.assertIn("+0.0%", out)


class TestStudentTrendIncludesBodyweight(unittest.TestCase):
    def test_kwarg_renders(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        points = [("2026-04-22", 73.0), ("2026-05-13", 70.0)]
        out = render_student_trend(trend, bodyweight_progression=points)
        self.assertIn("體重趨勢", out)


class TestCliEmitsBodyweightProgression(unittest.TestCase):
    def test_student_md_has_bodyweight_trend(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, bw in enumerate([73.0, 72.0, 71.0], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                p["session"]["bodyweight_kg"] = bw
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("體重趨勢", content)


if __name__ == "__main__":
    unittest.main()
