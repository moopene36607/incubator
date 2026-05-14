"""紅色測試 — 多堂聚合統計 (aggregate_batch + render_batch_summary).

PT 跑完一週 6-8 節課後,想知道:
- 這週總共做了幾噸 (整體訓練量)
- 每位學員上了幾堂 (出席頻率)
- 哪幾個動作的訓練量最多 (重點分布)

這是 fitness analytics dashboard 的最低要求。--batch 在產出個別 .md 之外,
應該再寫一份 _batch_summary.md 把整批的整體圖呈現給教練看。
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
    aggregate_batch,
    render_batch_summary,
)
from fitlog import SetRecord, parse_payload  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_session(student: str, session_no: int, sets: list[SetRecord]) -> "object":
    # 不從 JSON 走,直接造 SessionInput,讓測試聚焦於聚合邏輯
    from fitlog import SessionInput
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date="2026-05-10", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="test", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


def _load_sample():
    p = PROJECT_ROOT / "samples" / "sample_input.json"
    return parse_payload(json.loads(p.read_text(encoding="utf-8")))


class TestAggregateBatch(unittest.TestCase):
    def test_empty_returns_zero_stats(self) -> None:
        s = aggregate_batch([])
        self.assertEqual(s.n_sessions, 0)
        self.assertEqual(s.total_tonnage_kg, 0.0)
        self.assertEqual(s.students, {})
        self.assertEqual(s.top_exercises, [])

    def test_single_session_reflects_session(self) -> None:
        sess = _make_session("林阿明", 1, [_set("BENCH_PRESS", 4, "8", 50.0)])
        s = aggregate_batch([sess])
        self.assertEqual(s.n_sessions, 1)
        self.assertEqual(s.total_tonnage_kg, 1600.0)
        self.assertEqual(s.students, {"林阿明": 1})
        self.assertEqual(s.top_exercises, [("BENCH_PRESS", 1600.0)])

    def test_multiple_sessions_same_student_counts_correctly(self) -> None:
        a = _make_session("林阿明", 1, [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make_session("林阿明", 2, [_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        s = aggregate_batch([a, b])
        self.assertEqual(s.n_sessions, 2)
        self.assertEqual(s.total_tonnage_kg, 1600.0 + 2800.0)
        self.assertEqual(s.students, {"林阿明": 2})

    def test_multiple_students_counted_separately(self) -> None:
        a = _make_session("林阿明", 1, [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make_session("王小華", 1, [_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        s = aggregate_batch([a, b])
        self.assertEqual(s.students, {"林阿明": 1, "王小華": 1})

    def test_top_exercises_sorted_by_tonnage_desc(self) -> None:
        a = _make_session("A", 1, [
            _set("BENCH_PRESS", 4, "8", 50.0),    # 1600
            _set("BB_BACK_SQUAT", 4, "10", 70.0), # 2800
        ])
        b = _make_session("B", 1, [
            _set("BENCH_PRESS", 4, "8", 50.0),    # +1600
        ])
        s = aggregate_batch([a, b])
        # squat 2800 > bench 3200... wait BENCH 1600+1600=3200 > squat 2800
        self.assertEqual(s.top_exercises[0], ("BENCH_PRESS", 3200.0))
        self.assertEqual(s.top_exercises[1], ("BB_BACK_SQUAT", 2800.0))

    def test_bw_excluded_from_tonnage(self) -> None:
        sess = _make_session("A", 1, [
            _set("PULL_UP", 4, "8", None),
            _set("BENCH_PRESS", 4, "8", 50.0),
        ])
        s = aggregate_batch([sess])
        self.assertEqual(s.total_tonnage_kg, 1600.0)
        # PULL_UP 不該出現在 top_exercises (因為 tonnage = 0)
        codes = [c for c, _ in s.top_exercises]
        self.assertNotIn("PULL_UP", codes)

    def test_returns_batch_summary_dataclass(self) -> None:
        sess = _make_session("A", 1, [_set("BENCH_PRESS", 4, "8", 50.0)])
        self.assertIsInstance(aggregate_batch([sess]), BatchSummary)


class TestRenderBatchSummary(unittest.TestCase):
    def test_empty_summary_includes_header_and_zero_message(self) -> None:
        result = render_batch_summary(BatchSummary(
            n_sessions=0, total_tonnage_kg=0.0, students={}, top_exercises=[],
        ))
        self.assertIn("批次彙總", result)

    def test_summary_includes_session_count_and_tonnage(self) -> None:
        s = BatchSummary(
            n_sessions=3, total_tonnage_kg=15600.0,
            students={"A": 2, "B": 1}, top_exercises=[("BENCH_PRESS", 8000.0)],
        )
        out = render_batch_summary(s)
        self.assertIn("3", out)  # n_sessions
        self.assertIn("15,600 kg", out)  # 千位逗號

    def test_summary_lists_students_with_session_counts(self) -> None:
        s = BatchSummary(
            n_sessions=3, total_tonnage_kg=15600.0,
            students={"A": 2, "B": 1}, top_exercises=[],
        )
        out = render_batch_summary(s)
        self.assertIn("A", out)
        self.assertIn("B", out)
        self.assertIn("2", out)

    def test_summary_lists_top_exercises_with_chinese_names(self) -> None:
        s = BatchSummary(
            n_sessions=2, total_tonnage_kg=8000.0,
            students={"A": 2},
            top_exercises=[("BENCH_PRESS", 5000.0), ("BB_BACK_SQUAT", 3000.0)],
        )
        out = render_batch_summary(s)
        # 中文名 (從 exercise_db)
        self.assertIn("槓鈴臥推", out)
        self.assertIn("槓鈴背蹲舉", out)


class TestCliBatchProducesSummary(unittest.TestCase):
    def test_batch_writes_summary_md(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            base = json.loads((PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8"))
            for stem, name in (("aming", "林阿明"), ("xiaohua", "王小華")):
                payload = json.loads(json.dumps(base))
                payload["student"]["name"] = name
                (d / f"{stem}.json").write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", str(d), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary_path = d / "_batch_summary.md"
            self.assertTrue(summary_path.exists())
            content = summary_path.read_text(encoding="utf-8")
            self.assertIn("批次彙總", content)
            self.assertIn("林阿明", content)
            self.assertIn("王小華", content)


if __name__ == "__main__":
    unittest.main()
