"""紅色測試 — 週訓練量分布 (per-week tonnage table for periodization).

PT 看 periodization 時最關心「每週做了多少」。本輪在學員 .md 加一張
週訓練量 table:Week starting / 堂數 / 訓練量。

ISO week (週一為起始) 為分組鍵。同週多堂 → 加總。
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
    WeeklyTonnage,
    compute_weekly_tonnage,
    render_student_trend,
    render_weekly_tonnage,
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


class TestComputeWeeklyTonnage(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_weekly_tonnage([], "林阿明"), [])

    def test_single_session_one_week(self) -> None:
        # 2026-05-13 → ISO week 20 of 2026 (週一 5/11)
        sess = _make("林阿明", 1, "2026-05-13",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_weekly_tonnage([sess], "林阿明")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].n_sessions, 1)
        self.assertEqual(result[0].total_tonnage_kg, 1600.0)

    def test_same_week_multiple_sessions_aggregated(self) -> None:
        # 2026-05-11 (Mon) 與 2026-05-13 (Wed) 同 ISO week
        a = _make("林阿明", 1, "2026-05-11", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("林阿明", 2, "2026-05-13", [_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        result = compute_weekly_tonnage([a, b], "林阿明")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].n_sessions, 2)
        self.assertEqual(result[0].total_tonnage_kg, 1600.0 + 2800.0)

    def test_multi_weeks_sorted(self) -> None:
        # 三週各一堂,輸入順序錯亂 → 輸出按 week 排序
        b = _make("林阿明", 2, "2026-05-06", [_set("BENCH_PRESS", 4, "8", 50.0)])
        c = _make("林阿明", 3, "2026-05-13", [_set("BENCH_PRESS", 4, "8", 50.0)])
        a = _make("林阿明", 1, "2026-04-29", [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_weekly_tonnage([b, c, a], "林阿明")
        self.assertEqual(len(result), 3)
        # week_start 該由早到晚 (Monday of each week)
        starts = [w.week_start for w in result]
        self.assertEqual(sorted(starts), starts)

    def test_week_start_is_monday(self) -> None:
        # 2026-04-29 (Wed) → 該週週一是 2026-04-27
        sess = _make("林阿明", 1, "2026-04-29",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_weekly_tonnage([sess], "林阿明")
        self.assertEqual(result[0].week_start, "2026-04-27")

    def test_other_students_filtered(self) -> None:
        a = _make("林阿明", 1, "2026-05-13", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("王小華", 1, "2026-05-13", [_set("BENCH_PRESS", 4, "8", 99.0)])
        result = compute_weekly_tonnage([a, b], "林阿明")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].total_tonnage_kg, 1600.0)

    def test_returns_dataclass(self) -> None:
        sess = _make("林阿明", 1, "2026-05-13",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_weekly_tonnage([sess], "林阿明")
        self.assertIsInstance(result[0], WeeklyTonnage)


class TestRenderWeeklyTonnage(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(render_weekly_tonnage([]), "")

    def test_single_week_skipped(self) -> None:
        # 只一週 沒分布可講 → 跳過
        weekly = [WeeklyTonnage(week_start="2026-05-11",
                                total_tonnage_kg=1600.0, n_sessions=1)]
        self.assertEqual(render_weekly_tonnage(weekly), "")

    def test_multi_weeks_renders_table(self) -> None:
        weekly = [
            WeeklyTonnage(week_start="2026-04-27", total_tonnage_kg=5640.0, n_sessions=1),
            WeeklyTonnage(week_start="2026-05-04", total_tonnage_kg=5920.0, n_sessions=1),
            WeeklyTonnage(week_start="2026-05-11", total_tonnage_kg=6200.0, n_sessions=1),
        ]
        result = render_weekly_tonnage(weekly)
        self.assertIn("週訓練量", result)
        self.assertIn("2026-04-27", result)
        self.assertIn("5,640 kg", result)
        self.assertIn("6,200 kg", result)


class TestRenderStudentTrendIncludesWeekly(unittest.TestCase):
    def test_with_weekly_kwarg(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        weekly = [
            WeeklyTonnage(week_start="2026-04-27", total_tonnage_kg=5640.0, n_sessions=1),
            WeeklyTonnage(week_start="2026-05-04", total_tonnage_kg=5920.0, n_sessions=1),
        ]
        out = render_student_trend(trend, weekly_tonnage=weekly)
        self.assertIn("週訓練量", out)


class TestCliBatchProducesWeeklyTonnage(unittest.TestCase):
    def test_student_md_includes_weekly_section(self) -> None:
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
            self.assertIn("週訓練量", content)


if __name__ == "__main__":
    unittest.main()
