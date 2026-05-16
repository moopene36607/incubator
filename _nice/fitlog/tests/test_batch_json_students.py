"""紅色測試 — _batch.json 加 per-student 摘要列.

build_batch_metrics_json 的 students 只是 {姓名: 堂數}。dashboard 想做
「每學員一列」表格,需要每人的 headline 數字 (堂數 / 總訓練量 / streak /
PR 次數)。本輪加 student_summaries 列表。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import build_batch_metrics_json  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402


def _make(student: str, sno: int, date: str, weight: float) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=weight, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestBatchJsonStudentSummaries(unittest.TestCase):
    def test_field_present(self) -> None:
        result = build_batch_metrics_json([_make("林阿明", 1, "2026-05-10", 50.0)])
        self.assertIn("student_summaries", result)
        json.dumps(result)

    def test_empty_sessions(self) -> None:
        result = build_batch_metrics_json([])
        self.assertEqual(result["student_summaries"], [])

    def test_per_student_headline_numbers(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-05-01", 45.0),
            _make("林阿明", 2, "2026-05-08", 50.0),
        ]
        result = build_batch_metrics_json(sessions)
        summaries = {s["name"]: s for s in result["student_summaries"]}
        self.assertIn("林阿明", summaries)
        s = summaries["林阿明"]
        self.assertEqual(s["n_sessions"], 2)
        # 4×8×45 + 4×8×50 = 1440 + 1600 = 3040
        self.assertEqual(s["total_tonnage_kg"], 3040.0)
        self.assertIn("pr_count", s)
        self.assertIn("training_streak", s)

    def test_pr_count_reflects_progress(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-05-01", 45.0),
            _make("林阿明", 2, "2026-05-08", 50.0),  # PR
        ]
        result = build_batch_metrics_json(sessions)
        s = {x["name"]: x for x in result["student_summaries"]}["林阿明"]
        self.assertEqual(s["pr_count"], 1)

    def test_multiple_students_sorted_by_name(self) -> None:
        sessions = [
            _make("王小華", 1, "2026-05-01", 50.0),
            _make("林阿明", 1, "2026-05-01", 50.0),
        ]
        result = build_batch_metrics_json(sessions)
        names = [s["name"] for s in result["student_summaries"]]
        self.assertEqual(names, sorted(names))

    def test_students_count_map_still_present(self) -> None:
        # 既有 students 欄位不可退化
        result = build_batch_metrics_json([_make("林阿明", 1, "2026-05-10", 50.0)])
        self.assertEqual(result["students"]["林阿明"], 1)


if __name__ == "__main__":
    unittest.main()
