"""紅色測試 — 本堂訓練量 vs 個人歷史平均對比.

單堂報告現在有總噸位,但學員看到「3,200 kg」沒有參照系 — 不知這算多算少。
本輪加對比:本堂 tonnage 相對該學員「其他所有 session」平均高/低多少 %。

純函式 compare_session_to_average(sessions, student, current) →
(current_kg, avg_kg, pct_diff) 或 None (沒其他 session 可比 / 平均 0)。
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
    compare_session_to_average,
    render_session_vs_average,
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


# 4×8×weight:50→1600
class TestCompareSessionToAverage(unittest.TestCase):
    def test_only_one_session_returns_none(self) -> None:
        s = _make("林阿明", 1, "2026-05-10", 50.0)
        self.assertIsNone(compare_session_to_average([s], "林阿明", s))

    def test_above_average(self) -> None:
        # 其他 2 堂 1600, 2400 → 平均 2000;本堂 3200 → +60%
        s1 = _make("林阿明", 1, "2026-05-01", 50.0)   # 1600
        s2 = _make("林阿明", 2, "2026-05-08", 75.0)   # 2400
        curr = _make("林阿明", 3, "2026-05-15", 100.0)  # 3200
        result = compare_session_to_average([s1, s2, curr], "林阿明", curr)
        assert result is not None
        cur, avg, pct = result
        self.assertEqual(cur, 3200.0)
        self.assertEqual(avg, 2000.0)
        self.assertAlmostEqual(pct, 60.0, places=1)

    def test_below_average(self) -> None:
        s1 = _make("林阿明", 1, "2026-05-01", 100.0)  # 3200
        s2 = _make("林阿明", 2, "2026-05-08", 100.0)  # 3200
        curr = _make("林阿明", 3, "2026-05-15", 50.0)  # 1600
        result = compare_session_to_average([s1, s2, curr], "林阿明", curr)
        assert result is not None
        cur, avg, pct = result
        self.assertEqual(avg, 3200.0)
        self.assertLess(pct, 0)

    def test_other_students_excluded(self) -> None:
        a = _make("王小華", 1, "2026-05-01", 999.0)
        s1 = _make("林阿明", 1, "2026-05-01", 50.0)
        curr = _make("林阿明", 2, "2026-05-15", 50.0)
        result = compare_session_to_average([a, s1, curr], "林阿明", curr)
        assert result is not None
        _, avg, _ = result
        self.assertEqual(avg, 1600.0)  # 只算 林阿明 的 s1

    def test_current_excluded_from_average(self) -> None:
        # 平均不該包含本堂自己
        s1 = _make("林阿明", 1, "2026-05-01", 50.0)   # 1600
        curr = _make("林阿明", 2, "2026-05-15", 100.0)  # 3200
        result = compare_session_to_average([s1, curr], "林阿明", curr)
        assert result is not None
        _, avg, _ = result
        self.assertEqual(avg, 1600.0)


class TestRenderSessionVsAverage(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(render_session_vs_average(None))

    def test_above_renders_plus(self) -> None:
        out = render_session_vs_average((3200.0, 2000.0, 60.0))
        assert out is not None
        self.assertIn("個人平均", out)
        self.assertIn("3,200", out)
        self.assertIn("2,000", out)
        self.assertIn("+60", out)

    def test_below_renders_minus(self) -> None:
        out = render_session_vs_average((1600.0, 3200.0, -50.0))
        assert out is not None
        self.assertIn("-50", out)


class TestCliEmitsSessionVsAverage(unittest.TestCase):
    def test_batch_session_md_has_comparison(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, w in enumerate([45.0, 60.0], 1):
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
            content = (Path(out_td) / "s2.md").read_text(encoding="utf-8")
            self.assertIn("個人平均", content)


if __name__ == "__main__":
    unittest.main()
