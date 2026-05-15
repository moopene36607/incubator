"""紅色測試 — per-student 多堂進步趨勢 (compute_student_trend + render).

Aggregate 看的是「整批」的圖,but PT 要給單一學員看「你的 4 週」需要按
學員過濾 + 按日期排序的 trend。實際 PT 工作流:每週發一次「個人進步報告」
給學員,這份報告就是這個 function 產出的。

_run_batch 對每位 unique 學員寫一份 _student_<name>.md 跟批次 summary 一起。
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
    StudentTrendPoint,
    compute_student_trend,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make_session(student: str, session_no: int, date: str,
                  sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="test", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestComputeStudentTrend(unittest.TestCase):
    def test_no_sessions_for_student_returns_empty_points(self) -> None:
        result = compute_student_trend([], "林阿明")
        self.assertEqual(result.student_name, "林阿明")
        self.assertEqual(result.points, [])
        self.assertEqual(result.total_tonnage, 0.0)

    def test_single_session(self) -> None:
        sess = _make_session("林阿明", 1, "2026-05-10",
                             [_set("BENCH_PRESS", 4, "8", 50.0)])
        r = compute_student_trend([sess], "林阿明")
        self.assertEqual(len(r.points), 1)
        self.assertEqual(r.total_tonnage, 1600.0)

    def test_filters_other_students(self) -> None:
        a = _make_session("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make_session("王小華", 1, "2026-05-10", [_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        r = compute_student_trend([a, b], "林阿明")
        self.assertEqual(len(r.points), 1)
        self.assertEqual(r.total_tonnage, 1600.0)

    def test_points_sorted_by_date(self) -> None:
        # 即使輸入順序錯亂,points 應由日期早到晚排
        a = _make_session("林阿明", 3, "2026-05-12", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make_session("林阿明", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 50.0)])
        c = _make_session("林阿明", 2, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])
        r = compute_student_trend([a, b, c], "林阿明")
        self.assertEqual([p.date for p in r.points],
                         ["2026-05-08", "2026-05-10", "2026-05-12"])
        self.assertEqual([p.session_no for p in r.points], [1, 2, 3])

    def test_total_tonnage_sums_across_sessions(self) -> None:
        a = _make_session("林阿明", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make_session("林阿明", 2, "2026-05-10", [_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        r = compute_student_trend([a, b], "林阿明")
        self.assertEqual(r.total_tonnage, 1600.0 + 2800.0)

    def test_returns_trend_dataclass(self) -> None:
        sess = _make_session("林阿明", 1, "2026-05-10",
                             [_set("BENCH_PRESS", 4, "8", 50.0)])
        r = compute_student_trend([sess], "林阿明")
        self.assertIsInstance(r, StudentTrend)
        self.assertIsInstance(r.points[0], StudentTrendPoint)


class TestRenderStudentTrend(unittest.TestCase):
    def test_empty_trend_includes_header(self) -> None:
        result = render_student_trend(StudentTrend(
            student_name="林阿明", points=[], total_tonnage=0.0,
        ))
        self.assertIn("林阿明", result)
        self.assertIn("個人訓練趨勢", result)

    def test_trend_includes_per_session_table(self) -> None:
        trend = StudentTrend(
            student_name="林阿明",
            points=[
                StudentTrendPoint(date="2026-05-08", session_no=1, tonnage_kg=1600.0),
                StudentTrendPoint(date="2026-05-10", session_no=2, tonnage_kg=2800.0),
            ],
            total_tonnage=4400.0,
        )
        out = render_student_trend(trend)
        self.assertIn("2026-05-08", out)
        self.assertIn("2026-05-10", out)
        self.assertIn("1,600 kg", out)
        self.assertIn("2,800 kg", out)
        self.assertIn("4,400 kg", out)


class TestCliBatchProducesStudentTrend(unittest.TestCase):
    def test_batch_creates_per_student_md(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for stem, name in (("aming", "林阿明"), ("wang", "王小華")):
                payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
                payload["student"]["name"] = name
                Path(in_td, f"{stem}.json").write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            # 每位學員一份 _student_<name>.md
            self.assertTrue((Path(out_td) / "_student_林阿明.md").exists())
            self.assertTrue((Path(out_td) / "_student_王小華.md").exists())

    def test_student_md_contains_name_and_session_count(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            # 同學員 2 堂
            for i, stem in enumerate(("aming_s1", "aming_s2"), 1):
                payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
                payload["student"]["name"] = "林阿明"
                payload["session"]["session_no"] = i
                payload["session"]["date"] = f"2026-05-0{i}"
                Path(in_td, f"{stem}.json").write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("林阿明", content)
            self.assertIn("2026-05-01", content)
            self.assertIn("2026-05-02", content)


if __name__ == "__main__":
    unittest.main()
