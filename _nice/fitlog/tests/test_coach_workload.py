"""紅色測試 — 多教練工作室的教練工作量統計 in _batch_summary.

連鎖工作室 / 多教練工作室,店長想看「每個教練這批帶了幾堂、幾個學員、
總訓練量多少」做排班與抽成。本輪在 _batch_summary 加教練工作量段。

純函式 compute_coach_workload(sessions) → list[CoachWorkload],
按堂數 desc 排序。只有 1 位教練時 render 回 "" (單教練工作室沒比較意義)。
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
    CoachWorkload,
    compute_coach_workload,
    render_coach_workload,
)
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


class TestComputeCoachWorkload(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(compute_coach_workload([]), [])

    def test_single_coach_single_session(self) -> None:
        sess = _make("陳教練", "林阿明", "2026-05-10", 50.0)
        result = compute_coach_workload([sess])
        self.assertEqual(len(result), 1)
        w = result[0]
        self.assertEqual(w.coach_name, "陳教練")
        self.assertEqual(w.n_sessions, 1)
        self.assertEqual(w.n_students, 1)
        self.assertEqual(w.total_tonnage_kg, 4 * 8 * 50.0)  # 1600

    def test_coach_with_multiple_students(self) -> None:
        sessions = [
            _make("陳教練", "林阿明", "2026-05-10", 50.0),
            _make("陳教練", "王小華", "2026-05-11", 60.0),
            _make("陳教練", "林阿明", "2026-05-12", 55.0),  # 同學員再來
        ]
        result = compute_coach_workload(sessions)
        self.assertEqual(len(result), 1)
        w = result[0]
        self.assertEqual(w.n_sessions, 3)
        self.assertEqual(w.n_students, 2)  # 林阿明 + 王小華,不重複算
        self.assertEqual(w.total_tonnage_kg, 4 * 8 * (50.0 + 60.0 + 55.0))

    def test_multiple_coaches_sorted_by_sessions_desc(self) -> None:
        sessions = [
            _make("陳教練", "A", "2026-05-10"),
            _make("陳教練", "B", "2026-05-11"),
            _make("陳教練", "C", "2026-05-12"),
            _make("林教練", "D", "2026-05-10"),
        ]
        result = compute_coach_workload(sessions)
        self.assertEqual([w.coach_name for w in result],
                         ["陳教練", "林教練"])
        self.assertEqual(result[0].n_sessions, 3)
        self.assertEqual(result[1].n_sessions, 1)

    def test_tie_break_by_coach_name(self) -> None:
        # 同堂數 → 教練名字典序
        sessions = [
            _make("林教練", "A", "2026-05-10"),
            _make("陳教練", "B", "2026-05-10"),
        ]
        result = compute_coach_workload(sessions)
        # 林 (0x6797) < 陳 (0x9673)
        self.assertEqual([w.coach_name for w in result],
                         ["林教練", "陳教練"])


class TestRenderCoachWorkload(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(render_coach_workload([]), "")

    def test_single_coach_returns_empty(self) -> None:
        # 單教練工作室 → 沒比較意義,不渲染
        rows = [CoachWorkload(coach_name="陳教練", n_sessions=5,
                              n_students=3, total_tonnage_kg=8000.0)]
        self.assertEqual(render_coach_workload(rows), "")

    def test_multiple_coaches_renders_section(self) -> None:
        rows = [
            CoachWorkload(coach_name="陳教練", n_sessions=5,
                          n_students=3, total_tonnage_kg=8000.0),
            CoachWorkload(coach_name="林教練", n_sessions=2,
                          n_students=2, total_tonnage_kg=3000.0),
        ]
        out = render_coach_workload(rows)
        self.assertIn("教練工作量", out)
        self.assertIn("陳教練", out)
        self.assertIn("林教練", out)
        self.assertIn("5", out)
        self.assertIn("8,000", out)


class TestCliBatchEmitsCoachWorkload(unittest.TestCase):
    def test_batch_summary_has_coach_section_with_two_coaches(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            cases = [
                ("陳教練", "林阿明", 1),
                ("陳教練", "王小華", 2),
                ("林教練", "陳美玉", 3),
            ]
            for i, (coach, student, sno) in enumerate(cases, 1):
                p = json.loads(json.dumps(base))
                p["coach"]["name"] = coach
                p["student"]["name"] = student
                p["session"]["session_no"] = sno
                p["session"]["date"] = f"2026-05-1{i}"
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_batch_summary.md").read_text(encoding="utf-8")
            self.assertIn("教練工作量", content)
            self.assertIn("陳教練", content)
            self.assertIn("林教練", content)


if __name__ == "__main__":
    unittest.main()
