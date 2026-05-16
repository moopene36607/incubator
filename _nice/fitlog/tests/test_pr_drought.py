"""紅色測試 — PR 停滯偵測 (連續 N 堂沒破紀錄 → plateau 提示).

PR tally (round 28) 數「破了幾次」,本輪做反向訊號:學員曾經有進步,
但最近連續幾堂都沒突破任何 all-time 紀錄 → 訓練刺激可能該變化了。

heuristic:只有「曾經破過 PR」的學員才算停滯 (剛開始的學員不算);
drought = 最後一次破 PR 之後的堂數。render 門檻 3 堂才提示。
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
    compute_pr_drought,
    render_pr_drought,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


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


class TestComputePrDrought(unittest.TestCase):
    def test_no_sessions_zero(self) -> None:
        self.assertEqual(compute_pr_drought([], "林阿明"), 0)

    def test_never_pr_returns_zero(self) -> None:
        # 從沒破過 PR (持平) → 不算停滯,只是還沒建立 baseline
        sessions = [
            _make("林阿明", 1, "2026-04-22", 50.0),
            _make("林阿明", 2, "2026-04-29", 50.0),
            _make("林阿明", 3, "2026-05-06", 50.0),
        ]
        self.assertEqual(compute_pr_drought(sessions, "林阿明"), 0)

    def test_pr_last_session_no_drought(self) -> None:
        # 最後一堂剛破 PR → drought 0
        sessions = [
            _make("林阿明", 1, "2026-04-22", 45.0),
            _make("林阿明", 2, "2026-04-29", 50.0),  # PR
        ]
        self.assertEqual(compute_pr_drought(sessions, "林阿明"), 0)

    def test_drought_after_last_pr(self) -> None:
        # 第 2 堂破 PR,之後 3 堂持平 → drought 3
        sessions = [
            _make("林阿明", 1, "2026-04-22", 45.0),
            _make("林阿明", 2, "2026-04-29", 50.0),  # PR
            _make("林阿明", 3, "2026-05-06", 50.0),
            _make("林阿明", 4, "2026-05-13", 50.0),
            _make("林阿明", 5, "2026-05-20", 50.0),
        ]
        self.assertEqual(compute_pr_drought(sessions, "林阿明"), 3)

    def test_other_students_excluded(self) -> None:
        sessions = [
            _make("王小華", 1, "2026-04-22", 45.0),
            _make("王小華", 2, "2026-04-29", 99.0),
            _make("林阿明", 1, "2026-04-22", 45.0),
            _make("林阿明", 2, "2026-04-29", 50.0),  # PR
            _make("林阿明", 3, "2026-05-06", 50.0),
        ]
        self.assertEqual(compute_pr_drought(sessions, "林阿明"), 1)

    def test_pr_resets_drought(self) -> None:
        # 破→停→停→破→停 → 最後一次破在第 4 堂,drought 1
        sessions = [
            _make("林阿明", 1, "2026-04-22", 45.0),
            _make("林阿明", 2, "2026-04-29", 50.0),  # PR
            _make("林阿明", 3, "2026-05-06", 50.0),
            _make("林阿明", 4, "2026-05-13", 55.0),  # PR
            _make("林阿明", 5, "2026-05-20", 55.0),
        ]
        self.assertEqual(compute_pr_drought(sessions, "林阿明"), 1)


class TestRenderPrDrought(unittest.TestCase):
    def test_below_threshold_returns_none(self) -> None:
        self.assertIsNone(render_pr_drought(0))
        self.assertIsNone(render_pr_drought(2))

    def test_at_threshold_renders(self) -> None:
        out = render_pr_drought(3)
        assert out is not None
        self.assertIn("PR 停滯", out)
        self.assertIn("3", out)

    def test_high_drought_renders(self) -> None:
        out = render_pr_drought(6)
        assert out is not None
        self.assertIn("6", out)


class TestStudentTrendIncludesDrought(unittest.TestCase):
    def test_kwarg_renders(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend, pr_drought=4)
        self.assertIn("PR 停滯", out)

    def test_low_drought_no_section(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend, pr_drought=1)
        self.assertNotIn("PR 停滯", out)


class TestCliEmitsDrought(unittest.TestCase):
    def test_student_md_shows_drought(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            # 第 1 堂 45、第 2 堂 50 (PR)、之後 3 堂持平 50
            for i, w in enumerate([45.0, 50.0, 50.0, 50.0, 50.0], 1):
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
            self.assertIn("PR 停滯", content)


if __name__ == "__main__":
    unittest.main()
