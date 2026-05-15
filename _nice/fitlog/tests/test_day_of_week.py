"""紅色測試 — _batch_summary 加「開課日分布」(週幾最熱) bar chart.

PT 排班最常問:「我這週是不是排太多週一了?」之前的 batch summary 只
告訴他學員/動作/單堂排行,看不出工作室哪天最熱、哪天最空。本輪加一個
Mon-Sun bar chart,用全形方塊 (▏▎▍▌▋▊▉█) 視覺化分布。

純函式 compute_day_of_week_distribution(sessions) → dict[int(0=Mon..6=Sun), int]。
render_day_of_week_distribution(dist) → markdown section。
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
    compute_day_of_week_distribution,
    render_day_of_week_distribution,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(date: str, student: str = "A") -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=1, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=1,
                        reps_or_duration="8", weight_kg=50.0, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestComputeDayOfWeekDistribution(unittest.TestCase):
    def test_empty_returns_seven_zeros(self) -> None:
        result = compute_day_of_week_distribution([])
        # 7 個 key (0-6), 全 0
        self.assertEqual(set(result.keys()), set(range(7)))
        self.assertTrue(all(v == 0 for v in result.values()))

    def test_single_session_monday(self) -> None:
        # 2026-05-11 是 Monday
        sess = _make("2026-05-11")
        result = compute_day_of_week_distribution([sess])
        self.assertEqual(result[0], 1)
        for d in range(1, 7):
            self.assertEqual(result[d], 0)

    def test_sunday_indexed_as_six(self) -> None:
        # 2026-05-17 是 Sunday → key=6
        sess = _make("2026-05-17")
        result = compute_day_of_week_distribution([sess])
        self.assertEqual(result[6], 1)

    def test_multi_sessions_counted(self) -> None:
        sessions = [
            _make("2026-05-11", "A"),  # Mon
            _make("2026-05-11", "B"),  # Mon
            _make("2026-05-13", "A"),  # Wed
            _make("2026-05-15", "A"),  # Fri
            _make("2026-05-15", "B"),  # Fri
            _make("2026-05-15", "C"),  # Fri
        ]
        result = compute_day_of_week_distribution(sessions)
        self.assertEqual(result[0], 2)   # Mon
        self.assertEqual(result[1], 0)
        self.assertEqual(result[2], 1)   # Wed
        self.assertEqual(result[4], 3)   # Fri


class TestRenderDayOfWeekDistribution(unittest.TestCase):
    def test_empty_renders_empty(self) -> None:
        # 沒任何 sessions → 不渲染 section (避免空表)
        empty = {d: 0 for d in range(7)}
        self.assertEqual(render_day_of_week_distribution(empty), "")

    def test_renders_section_header(self) -> None:
        dist = {0: 3, 1: 0, 2: 1, 3: 0, 4: 2, 5: 0, 6: 0}
        out = render_day_of_week_distribution(dist)
        self.assertIn("開課日分布", out)
        # 7 個中文週幾
        for label in ("週一", "週二", "週三", "週四", "週五", "週六", "週日"):
            self.assertIn(label, out)
        # 數字 count 顯示
        self.assertIn("3", out)
        self.assertIn("2", out)

    def test_bar_chart_visible(self) -> None:
        dist = {0: 5, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        out = render_day_of_week_distribution(dist)
        # 最大值 (5) 行應該有最長的 bar (█ 系列方塊)
        self.assertTrue(any(ch in out for ch in "▏▎▍▌▋▊▉█"))


class TestCliBatchEmitsDayOfWeek(unittest.TestCase):
    def test_batch_summary_has_day_of_week_section(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            # 3 堂在不同日:Mon Wed Fri
            for i, dstr in enumerate(
                ["2026-05-11", "2026-05-13", "2026-05-15"], 1
            ):
                p = json.loads(json.dumps(base))
                p["session"]["session_no"] = i
                p["session"]["date"] = dstr
                p["student"]["name"] = f"Stu{i}"
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            content = (Path(out_td) / "_batch_summary.md").read_text(encoding="utf-8")
            self.assertIn("開課日分布", content)


if __name__ == "__main__":
    unittest.main()
