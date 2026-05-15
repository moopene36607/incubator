"""紅色測試 — 學員近 N 堂肌群分類覆蓋率.

imbalance warning 只在「單一分類占 >70%」時才響,但「核心 / 心肺從沒練過」
這種疏漏它抓不到。本輪加 coverage:近 N 堂 (default 4) 6 大分類各有沒有
被碰過,一眼看出缺口。

純函式 compute_category_coverage(sessions, student, window=4)
→ dict[category, bool]。沒任何 session → None。
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
    compute_category_coverage,
    render_category_coverage,
    render_student_trend,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)
CATEGORIES = ("legs", "pull", "push", "core", "cardio", "mobility")


def _make(student: str, sno: int, date: str,
          codes: list[str]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code=c, sets=1, reps_or_duration="8",
                        weight_kg=50.0, rpe=7) for c in codes],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeCategoryCoverage(unittest.TestCase):
    def test_no_sessions_returns_none(self) -> None:
        self.assertIsNone(compute_category_coverage([], "林阿明"))

    def test_all_six_keys_always_present(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", ["BENCH_PRESS"])
        result = compute_category_coverage([sess], "林阿明")
        assert result is not None
        self.assertEqual(set(result.keys()), set(CATEGORIES))

    def test_single_push_session(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", ["BENCH_PRESS", "OHP"])
        result = compute_category_coverage([sess], "林阿明")
        assert result is not None
        self.assertTrue(result["push"])
        self.assertFalse(result["legs"])
        self.assertFalse(result["core"])

    def test_multi_category_session(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10",
                     ["BENCH_PRESS", "BB_BACK_SQUAT", "PLANK"])
        result = compute_category_coverage([sess], "林阿明")
        assert result is not None
        self.assertTrue(result["push"])
        self.assertTrue(result["legs"])
        self.assertTrue(result["core"])
        self.assertFalse(result["cardio"])

    def test_window_limits_to_recent(self) -> None:
        # 第 1 堂練腿,之後 4 堂全推 → window=4 看不到腿
        sessions = [
            _make("林阿明", 1, "2026-04-01", ["BB_BACK_SQUAT"]),
            _make("林阿明", 2, "2026-04-08", ["BENCH_PRESS"]),
            _make("林阿明", 3, "2026-04-15", ["OHP"]),
            _make("林阿明", 4, "2026-04-22", ["DIPS"]),
            _make("林阿明", 5, "2026-04-29", ["INCLINE_PRESS"]),
        ]
        result = compute_category_coverage(sessions, "林阿明", window=4)
        assert result is not None
        self.assertFalse(result["legs"])  # 腿在 window 外
        self.assertTrue(result["push"])

    def test_other_students_excluded(self) -> None:
        a = _make("王小華", 1, "2026-05-10", ["BB_BACK_SQUAT"])
        b = _make("林阿明", 1, "2026-05-10", ["BENCH_PRESS"])
        result = compute_category_coverage([a, b], "林阿明")
        assert result is not None
        self.assertFalse(result["legs"])
        self.assertTrue(result["push"])

    def test_unknown_exercise_code_ignored(self) -> None:
        sess = _make("林阿明", 1, "2026-05-10", ["NOT_A_REAL_CODE"])
        result = compute_category_coverage([sess], "林阿明")
        assert result is not None
        self.assertFalse(any(result.values()))


class TestRenderCategoryCoverage(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(render_category_coverage(None))

    def test_renders_check_and_cross(self) -> None:
        cov = {"legs": True, "pull": True, "push": True,
               "core": False, "cardio": False, "mobility": True}
        out = render_category_coverage(cov)
        assert out is not None
        self.assertIn("肌群覆蓋", out)
        self.assertIn("✓", out)
        self.assertIn("✗", out)
        # 中文分類標籤
        self.assertIn("腿", out)
        self.assertIn("核心", out)

    def test_all_covered(self) -> None:
        cov = {c: True for c in CATEGORIES}
        out = render_category_coverage(cov)
        assert out is not None
        self.assertNotIn("✗", out)


class TestStudentTrendIncludesCoverage(unittest.TestCase):
    def test_kwarg_renders(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        cov = {"legs": True, "pull": False, "push": True,
               "core": False, "cardio": False, "mobility": False}
        out = render_student_trend(trend, category_coverage=cov)
        self.assertIn("肌群覆蓋", out)


class TestCliEmitsCoverage(unittest.TestCase):
    def test_student_md_has_coverage_line(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i in range(1, 3):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-1{i}"
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_student_林阿明.md").read_text(encoding="utf-8")
            self.assertIn("肌群覆蓋", content)


if __name__ == "__main__":
    unittest.main()
