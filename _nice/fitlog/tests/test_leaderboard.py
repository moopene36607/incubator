"""紅色測試 — 跨學員單堂訓練量排行 (compute_session_leaderboard).

PT 跑批次想看「這週誰練最重」(motivation / 健身房文化的 healthy
competition)。本輪在 _batch_summary.md 加一段 Top 5 單堂訓練量排行,
列出 學員 + session_no + date + tonnage。

ties 處理: 同 tonnage 取 (date, session_no, student_name) 字典序較小者
為前 (deterministic 排序)。
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
    SessionRanking,
    aggregate_batch,
    compute_session_leaderboard,
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


class TestComputeSessionLeaderboard(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(compute_session_leaderboard([]), [])

    def test_single_session_one_entry(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_session_leaderboard([sess])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].student_name, "林阿明")
        self.assertEqual(result[0].tonnage_kg, 1600.0)

    def test_sorted_by_tonnage_desc(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])    # 1600
        b = _make("王小華", 1, "2026-05-10", [_set("BB_BACK_SQUAT", 4, "10", 70.0)]) # 2800
        c = _make("陳美玉", 1, "2026-05-10", [_set("ROMANIAN_DL", 3, "10", 60.0)])  # 1800
        result = compute_session_leaderboard([a, b, c])
        self.assertEqual([r.student_name for r in result], ["王小華", "陳美玉", "林阿明"])

    def test_top_n_limits_results(self) -> None:
        sessions = [
            _make(f"S{i}", 1, "2026-05-10",
                  [_set("BENCH_PRESS", 4, "8", float(50 - i))])
            for i in range(10)
        ]
        result = compute_session_leaderboard(sessions, top_n=3)
        self.assertEqual(len(result), 3)

    def test_default_top_n_is_five(self) -> None:
        sessions = [
            _make(f"S{i}", 1, "2026-05-10",
                  [_set("BENCH_PRESS", 4, "8", float(50 - i))])
            for i in range(10)
        ]
        result = compute_session_leaderboard(sessions)
        self.assertEqual(len(result), 5)

    def test_tie_break_by_date_then_session_no_then_name(self) -> None:
        # 同 tonnage,(date, session_no, name) 字典序小者為前 (deterministic)
        a = _make("乙", 2, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("甲", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_session_leaderboard([a, b])
        # b 日期較早 → 排第一
        self.assertEqual(result[0].student_name, "甲")
        self.assertEqual(result[1].student_name, "乙")

    def test_returns_session_ranking_dataclass(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_session_leaderboard([sess])
        self.assertIsInstance(result[0], SessionRanking)


class TestAggregateBatchIncludesLeaderboard(unittest.TestCase):
    def test_aggregate_batch_populates_leaderboard(self) -> None:
        a = _make("林阿明", 1, "2026-05-10", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("王小華", 1, "2026-05-10", [_set("BB_BACK_SQUAT", 4, "10", 70.0)])
        result = aggregate_batch([a, b])
        # leaderboard 該存在且 sorted by tonnage desc
        self.assertEqual(len(result.leaderboard), 2)
        self.assertEqual(result.leaderboard[0].student_name, "王小華")


class TestRenderBatchSummaryIncludesLeaderboard(unittest.TestCase):
    def test_summary_renders_leaderboard_section(self) -> None:
        summary = BatchSummary(
            n_sessions=2,
            total_tonnage_kg=4400.0,
            students={"林阿明": 1, "王小華": 1},
            top_exercises=[("BB_BACK_SQUAT", 2800.0), ("BENCH_PRESS", 1600.0)],
            leaderboard=[
                SessionRanking(student_name="王小華", session_no=1,
                               session_date="2026-05-10", tonnage_kg=2800.0),
                SessionRanking(student_name="林阿明", session_no=1,
                               session_date="2026-05-10", tonnage_kg=1600.0),
            ],
        )
        out = render_batch_summary(summary)
        self.assertIn("單堂訓練量排行", out)
        self.assertIn("王小華", out)
        self.assertIn("2,800 kg", out)


class TestCliBatchProducesLeaderboardInSummary(unittest.TestCase):
    def test_summary_md_contains_leaderboard(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for stem, name in (("aming", "林阿明"), ("wang", "王小華")):
                p = json.loads(json.dumps(base))
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
            self.assertIn("單堂訓練量排行", content)


if __name__ == "__main__":
    unittest.main()
