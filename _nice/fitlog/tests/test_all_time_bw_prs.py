"""紅色測試 — 歷來最佳 BW reps PR (Pull-up 8 reps 之類的學員里程碑).

上輪 AllTimeBest 只追加重動作的歷史最重。對 BW 為主的初學者 / 街健者,
Pull-up 4→6→8 reps 的進步同樣值得記。本輪加 BW 維度:per-exercise 找
歷來最高 single-set reps,tie-break 同 reps 取最早日 (歷史意義)。

只算 weight_kg=None 且 reps_or_duration 是純整數的 set;time-based
('60 sec' 棒式) 與 weighted (Bench Press) 都跳過。
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
    AllTimeBest,
    AllTimeBwBest,
    StudentTrend,
    compute_student_bw_prs,
    render_all_time_prs,
    render_student_trend,
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


class TestComputeStudentBwPrs(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_student_bw_prs([], "林阿明"), {})

    def test_single_session_pull_up_max_reps(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PULL_UP", 3, "8", None),
        ])
        result = compute_student_bw_prs([sess], "林阿明")
        self.assertIn("PULL_UP", result)
        self.assertEqual(result["PULL_UP"].max_reps, 8)
        self.assertEqual(result["PULL_UP"].on_session_no, 1)
        self.assertEqual(result["PULL_UP"].on_session_date, "2026-05-10")

    def test_multi_sessions_takes_highest(self) -> None:
        a = _make("林阿明", 1, "2026-05-01", [_set("PULL_UP", 3, "4", None)])
        b = _make("林阿明", 2, "2026-05-08", [_set("PULL_UP", 3, "8", None)])
        c = _make("林阿明", 3, "2026-05-15", [_set("PULL_UP", 3, "6", None)])
        result = compute_student_bw_prs([a, b, c], "林阿明")
        self.assertEqual(result["PULL_UP"].max_reps, 8)
        self.assertEqual(result["PULL_UP"].on_session_date, "2026-05-08")

    def test_tie_break_earliest_date(self) -> None:
        a = _make("林阿明", 1, "2026-05-01", [_set("PULL_UP", 3, "8", None)])
        b = _make("林阿明", 2, "2026-05-15", [_set("PULL_UP", 3, "8", None)])
        result = compute_student_bw_prs([a, b], "林阿明")
        self.assertEqual(result["PULL_UP"].on_session_date, "2026-05-01")

    def test_takes_top_set_within_session(self) -> None:
        # 同 session 多 BW set 不同 reps → 取最高
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PULL_UP", 1, "5", None),
            _set("PULL_UP", 1, "8", None),
            _set("PULL_UP", 1, "3", None),
        ])
        result = compute_student_bw_prs([sess], "林阿明")
        self.assertEqual(result["PULL_UP"].max_reps, 8)

    def test_weighted_exercises_excluded(self) -> None:
        # Bench Press 加重 → 不入 BW PR
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("PULL_UP", 3, "6", None),
        ])
        result = compute_student_bw_prs([sess], "林阿明")
        self.assertNotIn("BENCH_PRESS", result)
        self.assertIn("PULL_UP", result)

    def test_time_based_excluded(self) -> None:
        # 棒式 60 sec 不是純整數 reps → 跳過
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PLANK", 3, "60 sec", None),
        ])
        result = compute_student_bw_prs([sess], "林阿明")
        self.assertEqual(result, {})

    def test_other_students_filtered(self) -> None:
        a = _make("林阿明", 1, "2026-05-01", [_set("PULL_UP", 3, "4", None)])
        b = _make("王小華", 1, "2026-05-08", [_set("PULL_UP", 3, "99", None)])
        result = compute_student_bw_prs([a, b], "林阿明")
        self.assertEqual(result["PULL_UP"].max_reps, 4)

    def test_returns_dataclass(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [_set("PULL_UP", 3, "8", None)])
        d = compute_student_bw_prs([sess], "林阿明")["PULL_UP"]
        self.assertIsInstance(d, AllTimeBwBest)
        self.assertEqual(d.exercise_code, "PULL_UP")


class TestRenderAllTimePrsWithBw(unittest.TestCase):
    def test_bw_only_includes_section(self) -> None:
        bw = {"PULL_UP": AllTimeBwBest(
            exercise_code="PULL_UP", max_reps=8,
            on_session_no=1, on_session_date="2026-05-10",
        )}
        out = render_all_time_prs({}, bw)
        self.assertIn("歷來最佳", out)
        self.assertIn("引體向上", out)
        self.assertIn("8 reps", out)

    def test_combined_weighted_and_bw(self) -> None:
        weighted = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=4, on_session_date="2026-05-13",
        )}
        bw = {"PULL_UP": AllTimeBwBest(
            exercise_code="PULL_UP", max_reps=8,
            on_session_no=2, on_session_date="2026-05-08",
        )}
        out = render_all_time_prs(weighted, bw)
        self.assertIn("槓鈴臥推", out)
        self.assertIn("引體向上", out)
        self.assertIn("50 kg", out)
        self.assertIn("8 reps", out)

    def test_existing_signature_still_works(self) -> None:
        # 上輪用法 render_all_time_prs(weighted) 不能破
        weighted = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=4, on_session_date="2026-05-13",
        )}
        out = render_all_time_prs(weighted)
        self.assertIn("50 kg", out)

    def test_both_empty_returns_empty(self) -> None:
        self.assertEqual(render_all_time_prs({}, {}), "")


class TestRenderStudentTrendIncludesBwPrs(unittest.TestCase):
    def test_with_bw_prs_kwarg_renders_section(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        bw = {"PULL_UP": AllTimeBwBest(
            exercise_code="PULL_UP", max_reps=8,
            on_session_no=2, on_session_date="2026-05-08",
        )}
        out = render_student_trend(trend, all_time_bw_prs=bw)
        self.assertIn("引體向上", out)
        self.assertIn("8 reps", out)


class TestCliBatchProducesBwPrInStudentMd(unittest.TestCase):
    def test_student_md_includes_bw_pr_section(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, reps in enumerate([4, 6, 8], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                # 改 PULL_UP 的 reps
                for s in p["session"]["sets"]:
                    if s["exercise_code"] == "PULL_UP":
                        s["reps_or_duration"] = str(reps)
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("引體向上", content)
            self.assertIn("8 reps", content)


if __name__ == "__main__":
    unittest.main()
