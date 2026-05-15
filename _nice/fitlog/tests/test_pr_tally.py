"""紅色測試 — 學員本期 PR 突破累計次數 (motivating tally).

detect_new_prs 已能偵測「某堂打破歷來最佳」,但學員 trend 報告沒有一個
「這期間你總共突破了幾次紀錄」的累計數字。本輪加 count_student_prs:
逐堂跑 detect_new_prs 對歷史,加總 PR 數,在 trend 報告頂端秀。

純函式;組裝既有 detect_new_prs,no LLM。
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
    count_student_prs,
    render_pr_tally,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, sno: int, date: str,
          sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=1, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


class TestCountStudentPrs(unittest.TestCase):
    def test_no_sessions_returns_zero(self) -> None:
        self.assertEqual(count_student_prs([], "林阿明"), 0)

    def test_single_session_no_history_zero(self) -> None:
        # 第一堂沒歷史可破 → 0
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", "8", 50.0)])
        self.assertEqual(count_student_prs([sess], "林阿明"), 0)

    def test_two_sessions_one_pr(self) -> None:
        a = _make("林阿明", 1, "2026-04-22", [_set("BENCH_PRESS", "8", 45.0)])
        b = _make("林阿明", 2, "2026-04-29", [_set("BENCH_PRESS", "8", 50.0)])
        # 第二堂打破 45 → 1 次 PR
        self.assertEqual(count_student_prs([a, b], "林阿明"), 1)

    def test_progressive_sessions_accumulate(self) -> None:
        # 每堂都進步 → 每堂 1 PR (第一堂不算)
        sessions = [
            _make("林阿明", 1, "2026-04-22", [_set("BENCH_PRESS", "8", 45.0)]),
            _make("林阿明", 2, "2026-04-29", [_set("BENCH_PRESS", "8", 47.5)]),
            _make("林阿明", 3, "2026-05-06", [_set("BENCH_PRESS", "8", 50.0)]),
            _make("林阿明", 4, "2026-05-13", [_set("BENCH_PRESS", "8", 52.5)]),
        ]
        self.assertEqual(count_student_prs(sessions, "林阿明"), 3)

    def test_plateau_sessions_no_pr(self) -> None:
        # 都做一樣重 → 沒 PR
        sessions = [
            _make("林阿明", 1, "2026-04-22", [_set("BENCH_PRESS", "8", 50.0)]),
            _make("林阿明", 2, "2026-04-29", [_set("BENCH_PRESS", "8", 50.0)]),
            _make("林阿明", 3, "2026-05-06", [_set("BENCH_PRESS", "8", 50.0)]),
        ]
        self.assertEqual(count_student_prs(sessions, "林阿明"), 0)

    def test_multiple_exercises_pr_in_same_session_counted_separately(self) -> None:
        a = _make("林阿明", 1, "2026-04-22", [
            _set("BENCH_PRESS", "8", 45.0),
            _set("BB_BACK_SQUAT", "5", 60.0),
        ])
        b = _make("林阿明", 2, "2026-04-29", [
            _set("BENCH_PRESS", "8", 50.0),    # PR
            _set("BB_BACK_SQUAT", "5", 70.0),  # PR
        ])
        self.assertEqual(count_student_prs([a, b], "林阿明"), 2)

    def test_other_students_excluded(self) -> None:
        a = _make("王小華", 1, "2026-04-22", [_set("BENCH_PRESS", "8", 45.0)])
        b = _make("王小華", 2, "2026-04-29", [_set("BENCH_PRESS", "8", 99.0)])
        c = _make("林阿明", 1, "2026-04-22", [_set("BENCH_PRESS", "8", 45.0)])
        self.assertEqual(count_student_prs([a, b, c], "林阿明"), 0)


class TestRenderPrTally(unittest.TestCase):
    def test_zero_returns_none(self) -> None:
        # 0 次不洗版
        self.assertIsNone(render_pr_tally(0))

    def test_positive_renders(self) -> None:
        line = render_pr_tally(5)
        assert line is not None
        self.assertIn("PR 突破", line)
        self.assertIn("5", line)

    def test_starts_bolded(self) -> None:
        line = render_pr_tally(3)
        assert line is not None
        self.assertIn("**", line)


class TestStudentTrendIncludesPrTally(unittest.TestCase):
    def test_kwarg_renders(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend, pr_tally=4)
        self.assertIn("PR 突破", out)
        self.assertIn("4", out)

    def test_zero_tally_no_section(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend, pr_tally=0)
        self.assertNotIn("PR 突破", out)


class TestCliEmitsPrTally(unittest.TestCase):
    def test_student_md_contains_pr_tally(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, w in enumerate([45.0, 47.5, 50.0], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                for s in p["session"]["sets"]:
                    if s["exercise_code"] == "BENCH_PRESS":
                        s["weight_kg"] = w
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("PR 突破", content)


if __name__ == "__main__":
    unittest.main()
