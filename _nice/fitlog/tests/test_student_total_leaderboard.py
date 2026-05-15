"""紅色測試 — 學員累積訓練量排行 (compute_student_total_leaderboard).

Round 23 加了「單堂訓練量排行」(誰一堂做最多 — 高強度單次訓練者)。
本輪加另一個面向:「學員累積訓練量排行」(誰整批做最多 — 高頻訓練者
+ 訓練量大者的乘積)。兩個排行互補,呈現批次的全貌。

ties 處理:
  1. 累積 tonnage desc 為主排序
  2. 次序: session 數 desc (相同 tonnage 取練比較多堂的)
  3. 末序: 學員姓名字典序 (deterministic)
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
    BatchSummary,
    StudentRanking,
    aggregate_batch,
    compute_student_total_leaderboard,
    render_batch_summary,
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


class TestComputeStudentTotalLeaderboard(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(compute_student_total_leaderboard([]), [])

    def test_single_student_single_session(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_student_total_leaderboard([sess])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].student_name, "林阿明")
        self.assertEqual(result[0].total_tonnage_kg, 1600.0)
        self.assertEqual(result[0].n_sessions, 1)

    def test_single_student_multi_sessions_aggregates(self) -> None:
        a = _make("林阿明", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 50.0)])  # 1600
        b = _make("林阿明", 2, "2026-05-10", [_set("BB_BACK_SQUAT", 4, "10", 70.0)])  # 2800
        result = compute_student_total_leaderboard([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].total_tonnage_kg, 4400.0)
        self.assertEqual(result[0].n_sessions, 2)

    def test_multi_students_sorted_by_total_desc(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])    # 1600
        b = _make("王小華", 1, "2026-05-10", [_set("BB_BACK_SQUAT", 4, "10", 70.0)]) # 2800
        c = _make("陳美玉", 1, "2026-05-10", [_set("ROMANIAN_DL", 3, "10", 60.0)])  # 1800
        result = compute_student_total_leaderboard([a, b, c])
        self.assertEqual([r.student_name for r in result],
                         ["王小華", "陳美玉", "林阿明"])

    def test_top_n_limits(self) -> None:
        sessions = [
            _make(f"S{i}", 1, "2026-05-10",
                  [_set("BENCH_PRESS", 4, "8", float(50 - i))])
            for i in range(10)
        ]
        result = compute_student_total_leaderboard(sessions, top_n=3)
        self.assertEqual(len(result), 3)

    def test_default_top_n_is_five(self) -> None:
        sessions = [
            _make(f"S{i}", 1, "2026-05-10",
                  [_set("BENCH_PRESS", 4, "8", float(50 - i))])
            for i in range(10)
        ]
        result = compute_student_total_leaderboard(sessions)
        self.assertEqual(len(result), 5)

    def test_tie_break_by_session_count_then_name(self) -> None:
        # 兩學員同 tonnage,session 數多的排前
        a = _make("乙", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])  # 1600
        b1 = _make("甲", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 25.0)]) # 800
        b2 = _make("甲", 2, "2026-05-11", [_set("BENCH_PRESS", 4, "8", 25.0)]) # 800
        # 甲: 1600 (2 堂); 乙: 1600 (1 堂) → 甲排前
        result = compute_student_total_leaderboard([a, b1, b2])
        self.assertEqual([r.student_name for r in result], ["甲", "乙"])

    def test_returns_student_ranking_dataclass(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_student_total_leaderboard([sess])
        self.assertIsInstance(result[0], StudentRanking)


class TestAggregateBatchIncludesStudentLeaderboard(unittest.TestCase):
    def test_aggregate_batch_populates_field(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("王小華", 1, "2026-05-10", [_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        result = aggregate_batch([a, b])
        self.assertEqual(len(result.student_total_leaderboard), 2)
        self.assertEqual(result.student_total_leaderboard[0].student_name, "王小華")


class TestRenderBatchSummaryIncludesStudentLeaderboard(unittest.TestCase):
    def test_render_includes_section(self) -> None:
        summary = BatchSummary(
            n_sessions=2,
            total_tonnage_kg=4400.0,
            students={"林阿明": 1, "王小華": 1},
            top_exercises=[("BB_BACK_SQUAT", 2800.0)],
            leaderboard=[],
            student_total_leaderboard=[
                StudentRanking(student_name="王小華",
                               total_tonnage_kg=2800.0, n_sessions=1),
                StudentRanking(student_name="林阿明",
                               total_tonnage_kg=1600.0, n_sessions=1),
            ],
        )
        out = render_batch_summary(summary)
        self.assertIn("學員累積訓練量排行", out)
        self.assertIn("王小華", out)
        self.assertIn("2,800 kg", out)


class TestCliBatchProducesStudentLeaderboard(unittest.TestCase):
    def test_summary_md_contains_student_total_leaderboard(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for stem, name in (("aming", "林阿明"), ("wang", "王小華")):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = name
                (Path(in_td) / f"{stem}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_batch_summary.md").read_text(encoding="utf-8")
            self.assertIn("學員累積訓練量排行", content)


if __name__ == "__main__":
    unittest.main()
