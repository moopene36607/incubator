"""紅色測試 — 歷來最佳 (all-time PR per exercise) 跨多堂追蹤.

學員看「我的 4 個月 Bench 紀錄是 55 kg (第 12 堂, 2026-04-30)」會超有感。
本模組對單一學員的所有 session,逐 exercise 找歷來最重的單組:

- 同重量在不同日子達成 → tie-break 取「最早達成」(歷史意義)
- BW 動作排除 (沒重量可比)
- 其他學員的 session 不影響該學員的 PR

整合進 _student_<name>.md,新增「## 歷來最佳」section 顯示 per-exercise PR。
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
    StudentTrend,
    compute_student_prs,
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


class TestComputeStudentPrs(unittest.TestCase):
    def test_no_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_student_prs([], "林阿明"), {})

    def test_single_session_returns_per_exercise_max(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 4, "8", 50.0),
            _set("BB_BACK_SQUAT", 4, "10", 70.0),
        ])
        result = compute_student_prs([sess], "林阿明")
        self.assertIn("BENCH_PRESS", result)
        self.assertEqual(result["BENCH_PRESS"].max_weight_kg, 50.0)
        self.assertEqual(result["BB_BACK_SQUAT"].max_weight_kg, 70.0)

    def test_multi_sessions_takes_highest_weight(self) -> None:
        a = _make("林阿明", 1, "2026-05-01", [_set("BENCH_PRESS", 4, "8", 47.5)])
        b = _make("林阿明", 2, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 50.0)])
        c = _make("林阿明", 3, "2026-05-15", [_set("BENCH_PRESS", 4, "8", 47.5)])
        result = compute_student_prs([a, b, c], "林阿明")
        self.assertEqual(result["BENCH_PRESS"].max_weight_kg, 50.0)
        self.assertEqual(result["BENCH_PRESS"].on_session_no, 2)
        self.assertEqual(result["BENCH_PRESS"].on_session_date, "2026-05-08")

    def test_tie_break_earliest_date_wins(self) -> None:
        # 同重量兩天達成 → 取最早 (歷史意義)
        a = _make("林阿明", 1, "2026-05-01", [_set("BENCH_PRESS", 4, "8", 50.0)])
        b = _make("林阿明", 2, "2026-05-15", [_set("BENCH_PRESS", 4, "8", 50.0)])
        result = compute_student_prs([a, b], "林阿明")
        self.assertEqual(result["BENCH_PRESS"].on_session_date, "2026-05-01")

    def test_takes_top_set_within_session(self) -> None:
        # 同 session 多 set 不同重 → 取最重那組
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("BENCH_PRESS", 1, "10", 40.0),
            _set("BENCH_PRESS", 1, "8", 47.5),
            _set("BENCH_PRESS", 1, "5", 52.5),  # top
        ])
        result = compute_student_prs([sess], "林阿明")
        self.assertEqual(result["BENCH_PRESS"].max_weight_kg, 52.5)

    def test_bodyweight_exercises_excluded(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", [
            _set("PULL_UP", 3, "8", None),
            _set("BENCH_PRESS", 4, "8", 50.0),
        ])
        result = compute_student_prs([sess], "林阿明")
        self.assertNotIn("PULL_UP", result)
        self.assertIn("BENCH_PRESS", result)

    def test_other_students_filtered_out(self) -> None:
        a = _make("林阿明", 1, "2026-05-01", [_set("BENCH_PRESS", 4, "8", 47.5)])
        b = _make("王小華", 1, "2026-05-08", [_set("BENCH_PRESS", 4, "8", 99.0)])
        result = compute_student_prs([a, b], "林阿明")
        self.assertEqual(result["BENCH_PRESS"].max_weight_kg, 47.5)

    def test_returns_all_time_best_dataclass(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     [_set("BENCH_PRESS", 4, "8", 50.0)])
        d = compute_student_prs([sess], "林阿明")["BENCH_PRESS"]
        self.assertIsInstance(d, AllTimeBest)
        self.assertEqual(d.exercise_code, "BENCH_PRESS")


class TestRenderAllTimePrs(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_all_time_prs({}), "")

    def test_single_pr_format(self) -> None:
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=12, on_session_date="2026-05-10",
        )}
        out = render_all_time_prs(prs)
        self.assertIn("歷來最佳", out)
        self.assertIn("槓鈴臥推", out)
        self.assertIn("50 kg", out)
        self.assertIn("第 12 堂", out)
        self.assertIn("2026-05-10", out)

    def test_multiple_sorted_by_weight_desc(self) -> None:
        prs = {
            "BENCH_PRESS": AllTimeBest(exercise_code="BENCH_PRESS",
                                       max_weight_kg=50.0,
                                       on_session_no=12,
                                       on_session_date="2026-05-10"),
            "BB_BACK_SQUAT": AllTimeBest(exercise_code="BB_BACK_SQUAT",
                                          max_weight_kg=80.0,
                                          on_session_no=10,
                                          on_session_date="2026-05-05"),
        }
        out = render_all_time_prs(prs)
        # Squat 80 kg 該排在 Bench 50 kg 前
        self.assertLess(out.find("槓鈴背蹲舉"), out.find("槓鈴臥推"))


class TestRenderStudentTrendIncludesPrs(unittest.TestCase):
    def test_render_with_prs_includes_section(self) -> None:
        # render_student_trend 加 optional all_time_prs 參數
        trend = StudentTrend(
            student_name="林阿明",
            points=[],
            total_tonnage=0.0,
        )
        prs = {"BENCH_PRESS": AllTimeBest(
            exercise_code="BENCH_PRESS", max_weight_kg=50.0,
            on_session_no=1, on_session_date="2026-05-10",
        )}
        out = render_student_trend(trend, all_time_prs=prs)
        self.assertIn("歷來最佳", out)
        self.assertIn("50 kg", out)

    def test_render_without_prs_no_section(self) -> None:
        # 既有契約: 不傳 all_time_prs 不該出現該 section (向後相容)
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend)
        self.assertNotIn("歷來最佳", out)


class TestCliBatchProducesAllTimePrsInStudentMd(unittest.TestCase):
    def test_student_md_includes_all_time_prs_section(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, w in enumerate([47.5, 50.0], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i+7}"
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
            self.assertIn("歷來最佳", content)
            self.assertIn("50 kg", content)


if __name__ == "__main__":
    unittest.main()
