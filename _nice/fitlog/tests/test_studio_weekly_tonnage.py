"""紅色測試 — Studio (cross-student) 跨週 tonnage 趨勢 in _batch_summary.

per-student weekly tonnage 已存在 (compute_weekly_tonnage),本輪補上工作
室層級的全店匯總:跨所有學員、按 ISO 週分組,看「我這間工作室的整體
週訓練量是上揚還是下滑」。PT 經營角度的核心指標。

純函式 compute_studio_weekly_tonnage(sessions) → list[StudioWeek]
(每筆含 week_start_iso / total_kg / n_sessions / n_students),按 week 排序。
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
    StudioWeek,
    compute_studio_weekly_tonnage,
    render_studio_weekly_tonnage,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, date: str,
          weight: float = 50.0) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=1, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=weight, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeStudioWeeklyTonnage(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(compute_studio_weekly_tonnage([]), [])

    def test_single_session_one_week(self) -> None:
        sess = _make("林阿明", "2026-05-11")  # Mon W20
        result = compute_studio_weekly_tonnage([sess])
        self.assertEqual(len(result), 1)
        w = result[0]
        # week_start 應為週一 (2026-05-11)
        self.assertEqual(w.week_start, "2026-05-11")
        self.assertEqual(w.total_tonnage_kg, 4 * 8 * 50.0)  # 1600
        self.assertEqual(w.n_sessions, 1)
        self.assertEqual(w.n_students, 1)

    def test_multiple_students_same_week_aggregated(self) -> None:
        a = _make("林阿明", "2026-05-11", 50.0)   # 1600
        b = _make("王小華", "2026-05-13", 60.0)   # 1920
        result = compute_studio_weekly_tonnage([a, b])
        self.assertEqual(len(result), 1)
        w = result[0]
        self.assertEqual(w.total_tonnage_kg, 3520.0)
        self.assertEqual(w.n_sessions, 2)
        self.assertEqual(w.n_students, 2)

    def test_same_student_two_sessions_one_week_counted_once_for_students(self) -> None:
        a = _make("林阿明", "2026-05-11", 50.0)
        b = _make("林阿明", "2026-05-13", 55.0)
        result = compute_studio_weekly_tonnage([a, b])
        w = result[0]
        self.assertEqual(w.n_sessions, 2)
        self.assertEqual(w.n_students, 1)

    def test_multi_weeks_sorted_by_week_start(self) -> None:
        # W18 (4/27 Mon) + W20 (5/11 Mon)
        a = _make("林阿明", "2026-04-27", 50.0)
        b = _make("林阿明", "2026-05-11", 50.0)
        result = compute_studio_weekly_tonnage([a, b])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].week_start, "2026-04-27")
        self.assertEqual(result[1].week_start, "2026-05-11")

    def test_session_anywhere_in_week_groups_to_monday(self) -> None:
        # 2026-05-15 是 W20 週五 → 週起為 2026-05-11
        sess = _make("林阿明", "2026-05-15")
        result = compute_studio_weekly_tonnage([sess])
        self.assertEqual(result[0].week_start, "2026-05-11")


class TestRenderStudioWeeklyTonnage(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_studio_weekly_tonnage([]), "")

    def test_renders_section_with_table(self) -> None:
        rows = [
            StudioWeek(week_start="2026-04-27", total_tonnage_kg=8000.0,
                       n_sessions=3, n_students=2),
            StudioWeek(week_start="2026-05-04", total_tonnage_kg=10000.0,
                       n_sessions=4, n_students=3),
        ]
        out = render_studio_weekly_tonnage(rows)
        self.assertIn("工作室週訓練量", out)
        # 週起日期出現
        self.assertIn("2026-04-27", out)
        self.assertIn("2026-05-04", out)
        # 噸位數字格式 (含千分逗號)
        self.assertIn("8,000", out)
        self.assertIn("10,000", out)
        # 堂數 / 學員數
        self.assertIn("3", out)
        self.assertIn("4", out)

    def test_two_plus_weeks_renders_sparkline(self) -> None:
        rows = [
            StudioWeek(week_start="2026-04-27", total_tonnage_kg=8000.0,
                       n_sessions=3, n_students=2),
            StudioWeek(week_start="2026-05-04", total_tonnage_kg=12000.0,
                       n_sessions=5, n_students=3),
            StudioWeek(week_start="2026-05-11", total_tonnage_kg=10000.0,
                       n_sessions=4, n_students=3),
        ]
        out = render_studio_weekly_tonnage(rows)
        # 至少 3 個 sparkline 方塊
        bars = [c for c in out if c in "▁▂▃▄▅▆▇█"]
        self.assertGreaterEqual(len(bars), 3)


class TestCliBatchEmitsStudioWeekly(unittest.TestCase):
    def test_batch_summary_has_studio_weekly_section(self) -> None:
        # 2 學員、3 個不同週 → 應產出工作室週訓練量 section
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            cases = [
                ("林阿明", 1, "2026-04-27"),  # W18
                ("王小華", 1, "2026-05-04"),  # W19
                ("林阿明", 2, "2026-05-11"),  # W20
            ]
            for i, (name, sno, dstr) in enumerate(cases, 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = name
                p["session"]["session_no"] = sno
                p["session"]["date"] = dstr
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_batch_summary.md").read_text(encoding="utf-8")
            self.assertIn("工作室週訓練量", content)
            self.assertIn("2026-04-27", content)


if __name__ == "__main__":
    unittest.main()
