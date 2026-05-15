"""紅色測試 — 學員訓練頻率分析 (avg sessions per week + adherence).

學員 .md 顯示「平均 1.3 次/週 (4 堂 / 21 天)」,PT 一眼判斷學員是否
符合處方頻率。例如 PT 開「每週 3 次」,學員實際 1 次/週 → adherence 差。

純 datetime 計算,無 LLM。spans 0 天 (單堂或同日多堂) → 0 次/週。
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
    StudentFrequency,
    StudentTrend,
    compute_student_session_frequency,
    render_session_frequency,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, session_no: int, date: str) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=50.0, rpe=8)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeStudentSessionFrequency(unittest.TestCase):
    def test_no_sessions_returns_none(self) -> None:
        self.assertIsNone(compute_student_session_frequency([], "林阿明"))

    def test_single_session_zero_frequency(self) -> None:
        result = compute_student_session_frequency(
            [_make("林阿明", 1, "2026-05-10")], "林阿明",
        )
        self.assertEqual(result.total_sessions, 1)
        self.assertEqual(result.span_days, 0)
        self.assertEqual(result.sessions_per_week, 0.0)

    def test_4_sessions_in_21_days(self) -> None:
        # 2026-04-22 → 2026-05-13 = 21 days, 4 堂 → 4 * 7 / 21 = 1.333
        sessions = [
            _make("林阿明", 1, "2026-04-22"),
            _make("林阿明", 2, "2026-04-29"),
            _make("林阿明", 3, "2026-05-06"),
            _make("林阿明", 4, "2026-05-13"),
        ]
        result = compute_student_session_frequency(sessions, "林阿明")
        self.assertEqual(result.total_sessions, 4)
        self.assertEqual(result.span_days, 21)
        self.assertAlmostEqual(result.sessions_per_week, 4 * 7 / 21, places=2)

    def test_3_sessions_per_week_steady(self) -> None:
        # 7 天內 3 堂 → 3 次/週
        sessions = [
            _make("林阿明", 1, "2026-05-01"),
            _make("林阿明", 2, "2026-05-04"),
            _make("林阿明", 3, "2026-05-08"),  # +7 days from s1
        ]
        result = compute_student_session_frequency(sessions, "林阿明")
        self.assertAlmostEqual(result.sessions_per_week, 3.0, places=2)

    def test_same_day_multi_sessions_zero_span(self) -> None:
        # 同一天兩堂 → span 0 → freq 0 (不能 div0)
        sessions = [
            _make("林阿明", 1, "2026-05-10"),
            _make("林阿明", 2, "2026-05-10"),
        ]
        result = compute_student_session_frequency(sessions, "林阿明")
        self.assertEqual(result.span_days, 0)
        self.assertEqual(result.sessions_per_week, 0.0)

    def test_other_students_filtered(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-05-01"),
            _make("王小華", 1, "2026-05-04"),
            _make("林阿明", 2, "2026-05-08"),
        ]
        result = compute_student_session_frequency(sessions, "林阿明")
        self.assertEqual(result.total_sessions, 2)

    def test_returns_dataclass(self) -> None:
        sessions = [_make("林阿明", 1, "2026-05-10")]
        result = compute_student_session_frequency(sessions, "林阿明")
        self.assertIsInstance(result, StudentFrequency)


class TestRenderSessionFrequency(unittest.TestCase):
    def test_none_returns_empty(self) -> None:
        self.assertEqual(render_session_frequency(None), "")

    def test_single_session_skip(self) -> None:
        # 單堂 freq 0 → 不出 (沒進步可講)
        f = StudentFrequency(total_sessions=1, span_days=0, sessions_per_week=0.0)
        self.assertEqual(render_session_frequency(f), "")

    def test_typical_format(self) -> None:
        f = StudentFrequency(total_sessions=4, span_days=21, sessions_per_week=1.33)
        result = render_session_frequency(f)
        self.assertIn("訓練頻率", result)
        self.assertIn("1.3", result)
        self.assertIn("4 堂", result)
        self.assertIn("21 天", result)


class TestRenderStudentTrendIncludesFrequency(unittest.TestCase):
    def test_with_frequency_kwarg(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        f = StudentFrequency(total_sessions=4, span_days=21, sessions_per_week=1.33)
        out = render_student_trend(trend, frequency=f)
        self.assertIn("訓練頻率", out)


class TestCliBatchProducesFrequency(unittest.TestCase):
    def test_student_md_includes_frequency(self) -> None:
        # timeline_demo 有 4 堂 (4/22 → 5/13) → 該出現訓練頻率
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for i, date in enumerate(["2026-04-22", "2026-04-29",
                                       "2026-05-06", "2026-05-13"], 1):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = date
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("訓練頻率", content)


if __name__ == "__main__":
    unittest.main()
