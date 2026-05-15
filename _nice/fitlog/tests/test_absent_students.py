"""紅色測試 — 長期缺席學員警示 (流失早期偵測).

streak 指標看「誰還在來」,但 PT 更怕「誰悄悄不來了」。本輪在
_batch_summary.md 加缺席段:列出超過 N 天 (default 14) 沒進場的學員,
按缺席天數 desc 排序。PT 可直接把名單帶去 LINE 群關懷一下。

純函式:compute_absent_students(sessions, as_of_iso, threshold_days=14)
→ list[AbsentStudent] (sorted by days desc, ties by name asc)。
從沒上過課的人不會在這份名單裡 (因為沒「上次」可比)。
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
    AbsentStudent,
    BatchSummary,
    compute_absent_students,
    render_absent_students,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, session_no: int, date: str) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[
            SetRecord(exercise_code="BENCH_PRESS", sets=1,
                      reps_or_duration="8", weight_kg=50.0, rpe=7),
        ],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeAbsentStudents(unittest.TestCase):
    def test_empty_sessions_returns_empty(self) -> None:
        self.assertEqual(compute_absent_students([], "2026-05-15"), [])

    def test_recent_attender_not_absent(self) -> None:
        # 5 天前剛上過 → 不算缺席 (預設 14 天門檻)
        s = _make("林阿明", 1, "2026-05-10")
        self.assertEqual(compute_absent_students([s], "2026-05-15"), [])

    def test_long_absence_detected(self) -> None:
        # 30 天前最後一堂 → 該上名單
        s = _make("林阿明", 1, "2026-04-15")
        result = compute_absent_students([s], "2026-05-15")
        self.assertEqual(len(result), 1)
        a = result[0]
        self.assertEqual(a.student_name, "林阿明")
        self.assertEqual(a.last_session_date, "2026-04-15")
        self.assertEqual(a.days_since, 30)

    def test_threshold_boundary_exactly_14_days_not_absent(self) -> None:
        # 嚴格 > 14 才算 (= 14 還在 grace)
        s = _make("林阿明", 1, "2026-05-01")
        self.assertEqual(compute_absent_students([s], "2026-05-15"), [])

    def test_threshold_boundary_15_days_absent(self) -> None:
        s = _make("林阿明", 1, "2026-04-30")
        result = compute_absent_students([s], "2026-05-15")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].days_since, 15)

    def test_uses_last_session_per_student(self) -> None:
        # 林阿明 兩堂 取最近;王小華 1 堂 30 天前
        a1 = _make("林阿明", 1, "2026-04-01")
        a2 = _make("林阿明", 2, "2026-05-13")  # 2 天前
        b1 = _make("王小華", 1, "2026-04-15")  # 30 天前
        result = compute_absent_students([a1, a2, b1], "2026-05-15")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].student_name, "王小華")

    def test_sort_by_days_desc_then_name_asc(self) -> None:
        # tie-break by name 走 Python str (Unicode codepoint) 排序;
        # 林 (0x6797) < 王 (0x738B),所以同 30 天時 林阿明 排在 王小華 前。
        a = _make("林阿明", 1, "2026-04-15")  # 30 天
        b = _make("王小華", 1, "2026-04-15")  # 30 天 (同天)
        c = _make("陳美玉", 1, "2026-04-01")  # 44 天
        result = compute_absent_students([a, b, c], "2026-05-15")
        self.assertEqual([r.student_name for r in result],
                         ["陳美玉", "林阿明", "王小華"])

    def test_custom_threshold(self) -> None:
        s = _make("林阿明", 1, "2026-05-08")  # 7 天前
        # 預設 14 天 → 不算
        self.assertEqual(compute_absent_students([s], "2026-05-15"), [])
        # threshold 5 天 → 算
        result = compute_absent_students([s], "2026-05-15", threshold_days=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].days_since, 7)


class TestRenderAbsentStudents(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_absent_students([]), "")

    def test_single_absent_renders_section(self) -> None:
        items = [AbsentStudent(
            student_name="林阿明", last_session_date="2026-04-15",
            days_since=30,
        )]
        out = render_absent_students(items)
        self.assertIn("長期缺席", out)
        self.assertIn("林阿明", out)
        self.assertIn("2026-04-15", out)
        self.assertIn("30", out)
        self.assertIn("天", out)

    def test_multiple_listed(self) -> None:
        items = [
            AbsentStudent(student_name="陳美玉",
                          last_session_date="2026-04-01", days_since=44),
            AbsentStudent(student_name="王小華",
                          last_session_date="2026-04-15", days_since=30),
        ]
        out = render_absent_students(items)
        # 陳美玉 排在 王小華 前 (天數 desc)
        self.assertLess(out.find("陳美玉"), out.find("王小華"))


class TestCliBatchEmitsAbsentSection(unittest.TestCase):
    def test_batch_summary_contains_absent_section(self) -> None:
        # 兩學員一新一舊 → 舊那個應該出現
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, (name, dstr) in enumerate([
                ("林阿明", "2026-05-13"),   # 最近 / 不缺席
                ("王小華", "2026-04-01"),   # 缺席 ~44 天
            ], 1):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = name
                p["session"]["session_no"] = i
                p["session"]["date"] = dstr
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_batch_summary.md").read_text(encoding="utf-8")
            self.assertIn("長期缺席", content)
            self.assertIn("王小華", content)
            # 林阿明 不應在缺席段。但他可能出現在 attendance / leaderboard,
            # 所以只檢查「缺席」段附近沒林阿明 → 用 split
            absent_section = content.split("長期缺席", 1)[1].split("##", 1)[0]
            self.assertNotIn("林阿明", absent_section)


if __name__ == "__main__":
    unittest.main()
