"""紅色測試 — _batch.json 補入教練工作量/分類分布/PR 榜/缺席名單.

build_batch_metrics_json (round 26) 寫於 coach_workload (r22) /
studio_category (r34) / pr_leaderboard (r41) / absent_students (r7)
之前,所以 _batch.json 缺這幾個 section — markdown 的 _batch_summary
有,JSON 沒有,接 dashboard 的人拿不到。本輪補齊。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import build_batch_metrics_json  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(coach: str, student: str, date: str,
          weight: float = 50.0) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=1, session_date=date, duration_min=60,
        coach_name=coach, studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=weight, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestBatchJsonExtraSections(unittest.TestCase):
    def test_json_serializable(self) -> None:
        result = build_batch_metrics_json([_make("C", "A", "2026-05-10")])
        json.dumps(result)

    def test_has_coach_workload(self) -> None:
        sessions = [
            _make("陳教練", "A", "2026-05-10"),
            _make("林教練", "B", "2026-05-11"),
        ]
        result = build_batch_metrics_json(sessions)
        self.assertIn("coach_workload", result)
        coaches = {c["coach_name"] for c in result["coach_workload"]}
        self.assertEqual(coaches, {"陳教練", "林教練"})

    def test_has_category_distribution(self) -> None:
        result = build_batch_metrics_json([_make("C", "A", "2026-05-10")])
        self.assertIn("category_distribution", result)
        # BENCH_PRESS → push
        cats = {row["category"] for row in result["category_distribution"]}
        self.assertIn("push", cats)

    def test_has_pr_leaderboard(self) -> None:
        # A 連續進步 → 上 PR 榜
        sessions = [
            _make("C", "A", "2026-05-01", 45.0),
            _make("C", "A", "2026-05-08", 50.0),
        ]
        result = build_batch_metrics_json(sessions)
        self.assertIn("pr_leaderboard", result)
        names = {r["student"] for r in result["pr_leaderboard"]}
        self.assertIn("A", names)

    def test_has_absent_students(self) -> None:
        # B 最後一堂很久以前 → 缺席
        sessions = [
            _make("C", "A", "2026-05-13"),
            _make("C", "B", "2026-04-01"),
        ]
        result = build_batch_metrics_json(sessions)
        self.assertIn("absent_students", result)
        absent_names = {a["student_name"] for a in result["absent_students"]}
        self.assertIn("B", absent_names)

    def test_existing_fields_still_present(self) -> None:
        result = build_batch_metrics_json([_make("C", "A", "2026-05-10")])
        for key in ("n_sessions", "n_students", "total_tonnage_kg",
                    "students", "top_exercises", "studio_weekly",
                    "day_of_week"):
            self.assertIn(key, result)

    def test_empty_sessions_no_crash(self) -> None:
        result = build_batch_metrics_json([])
        json.dumps(result)
        self.assertEqual(result["coach_workload"], [])
        self.assertEqual(result["absent_students"], [])


class TestCliBatchJsonExtra(unittest.TestCase):
    def test_batch_json_file_has_new_sections(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i in range(1, 3):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = f"Stu{i}"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-1{i}"
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--batch-json"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(
                (Path(out_td) / "_batch.json").read_text(encoding="utf-8"))
            self.assertIn("coach_workload", data)
            self.assertIn("category_distribution", data)
            self.assertIn("pr_leaderboard", data)
            self.assertIn("absent_students", data)


if __name__ == "__main__":
    unittest.main()
