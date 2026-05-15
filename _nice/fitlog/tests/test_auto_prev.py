"""紅色測試 — 批次模式自動配對 prev → curr (find_prev_session 純函式 + 整合).

PT 把 4 週的同學員 sessions 丟同一個批次目錄,就是想看「進步」。
本輪 _run_batch 改兩階段:
  1. parse 全部 → 收集 (path, session) 對
  2. 對每堂 session,從同學員的較早 session 找最近一筆當作 prev,
     渲染時帶 pr_summary 進報告

「較早」定義: (date, session_no) tuple 字典序小於 target。同學員多堂同日
靠 session_no 排序。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import find_prev_session  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make_session(student: str, session_no: int, date: str,
                  weight: float = 50.0) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=weight, rpe=8)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestFindPrevSession(unittest.TestCase):
    def test_no_other_sessions_returns_none(self) -> None:
        target = _make_session("林阿明", 1, "2026-05-10")
        self.assertIsNone(find_prev_session(target, [target]))

    def test_only_other_students_returns_none(self) -> None:
        target = _make_session("林阿明", 1, "2026-05-10")
        other = _make_session("王小華", 1, "2026-05-08")
        self.assertIsNone(find_prev_session(target, [target, other]))

    def test_single_prior_returns_it(self) -> None:
        target = _make_session("林阿明", 2, "2026-05-10")
        prior = _make_session("林阿明", 1, "2026-05-08")
        result = find_prev_session(target, [target, prior])
        self.assertIs(result, prior)

    def test_multiple_priors_returns_most_recent(self) -> None:
        target = _make_session("林阿明", 4, "2026-05-15")
        old = _make_session("林阿明", 1, "2026-05-01")
        mid = _make_session("林阿明", 2, "2026-05-05")
        recent = _make_session("林阿明", 3, "2026-05-10")
        result = find_prev_session(target, [old, mid, recent, target])
        self.assertIs(result, recent)

    def test_future_sessions_skipped(self) -> None:
        # 同學員但日期較晚 → 不該被當 prev (避免時序顛倒)
        target = _make_session("林阿明", 2, "2026-05-10")
        future = _make_session("林阿明", 3, "2026-05-15")
        self.assertIsNone(find_prev_session(target, [target, future]))

    def test_same_date_lower_session_no_qualifies_as_prev(self) -> None:
        # 同一天兩堂課,前一堂 (session_no 較小) 也算 prev
        target = _make_session("林阿明", 2, "2026-05-10")
        earlier_same_day = _make_session("林阿明", 1, "2026-05-10")
        result = find_prev_session(target, [target, earlier_same_day])
        self.assertIs(result, earlier_same_day)

    def test_mixed_students_only_picks_target_student(self) -> None:
        target = _make_session("林阿明", 2, "2026-05-10")
        prior_aming = _make_session("林阿明", 1, "2026-05-08", weight=47.5)
        prior_other = _make_session("王小華", 99, "2026-05-09", weight=99.0)
        result = find_prev_session(target, [prior_aming, prior_other, target])
        self.assertIs(result, prior_aming)


class TestCliBatchAutoPair(unittest.TestCase):
    def test_later_session_md_includes_pr_summary(self) -> None:
        """同學員兩堂課 (Bench 47.5 → 50),後者 .md 該含進步亮點。"""
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            base["student"]["name"] = "林阿明"
            # session 1: bench 47.5
            s1 = json.loads(json.dumps(base))
            s1["session"]["session_no"] = 1
            s1["session"]["date"] = "2026-05-08"
            for s in s1["session"]["sets"]:
                if s["exercise_code"] == "BENCH_PRESS":
                    s["weight_kg"] = 47.5
            (Path(in_td) / "s01.json").write_text(
                json.dumps(s1, ensure_ascii=False), encoding="utf-8")
            # session 2: bench 50 (PR)
            s2 = json.loads(json.dumps(base))
            s2["session"]["session_no"] = 2
            s2["session"]["date"] = "2026-05-10"
            (Path(in_td) / "s02.json").write_text(
                json.dumps(s2, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            s2_content = (Path(out_td) / "s02.md").read_text(encoding="utf-8")
            self.assertIn("進步亮點", s2_content)
            self.assertIn("47.5→50 kg", s2_content)
            self.assertIn("PR", s2_content)
            # 第一堂沒有 prev → 不該有進步亮點
            s1_content = (Path(out_td) / "s01.md").read_text(encoding="utf-8")
            self.assertNotIn("進步亮點", s1_content)


if __name__ == "__main__":
    unittest.main()
