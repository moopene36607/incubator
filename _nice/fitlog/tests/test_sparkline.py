"""紅色測試 — 學員 trend ASCII sparkline (Unicode 方塊字元視覺化).

學員打開個人 .md 報告,看到一行字串 ▆▇▇█ 比看一個表格更有「進步感」。
本輪用 8-level Unicode 方塊字元 (▁▂▃▄▅▆▇█) 把 4 週 tonnage 趨勢畫成
一行 sparkline,加上 first → last delta %。
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
    StudentTrendPoint,
    render_student_trend,
    render_tonnage_sparkline,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)

SPARKLINE_BARS = "▁▂▃▄▅▆▇█"


def _pt(date: str, sno: int, tonnage: float) -> StudentTrendPoint:
    return StudentTrendPoint(date=date, session_no=sno, tonnage_kg=tonnage)


class TestRenderTonnageSparkline(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(render_tonnage_sparkline([]), "")

    def test_single_point_one_bar(self) -> None:
        result = render_tonnage_sparkline([_pt("2026-05-10", 1, 5640.0)])
        # 至少一個方塊字元在輸出
        self.assertTrue(any(b in result for b in SPARKLINE_BARS), result)
        self.assertIn("5,640 kg", result)

    def test_ascending_uses_first_bar_lowest_last_bar_highest(self) -> None:
        # 上升序列 → 最後一個 bar 比第一個高
        points = [
            _pt("2026-04-22", 1, 5000.0),
            _pt("2026-04-29", 2, 6000.0),
            _pt("2026-05-06", 3, 7000.0),
            _pt("2026-05-13", 4, 8000.0),
        ]
        result = render_tonnage_sparkline(points)
        # 抓出 sparkline 那段 (連續方塊字元)
        bars_section = "".join(c for c in result if c in SPARKLINE_BARS)
        self.assertEqual(len(bars_section), 4)
        # 第一個 = 最低 (▁), 最後一個 = 最高 (█)
        self.assertEqual(bars_section[0], "▁")
        self.assertEqual(bars_section[-1], "█")

    def test_constant_values_uniform_bars(self) -> None:
        # 全持平 → 所有 bar 一致 (取中間 ▅)
        points = [_pt(f"2026-05-{d:02d}", i, 5000.0)
                  for i, d in enumerate([8, 10, 12], 1)]
        result = render_tonnage_sparkline(points)
        bars_section = "".join(c for c in result if c in SPARKLINE_BARS)
        self.assertEqual(len(bars_section), 3)
        self.assertEqual(len(set(bars_section)), 1, f"bars not uniform: {bars_section}")

    def test_includes_first_to_last_range(self) -> None:
        points = [_pt("2026-04-22", 1, 5640.0), _pt("2026-05-13", 4, 6200.0)]
        result = render_tonnage_sparkline(points)
        self.assertIn("5,640", result)
        self.assertIn("6,200", result)

    def test_includes_percentage_delta(self) -> None:
        # 5640 → 6200 = +9.9%
        points = [_pt("2026-04-22", 1, 5640.0), _pt("2026-05-13", 4, 6200.0)]
        result = render_tonnage_sparkline(points)
        self.assertIn("+9.9%", result)

    def test_negative_delta_marked(self) -> None:
        points = [_pt("2026-04-22", 1, 6000.0), _pt("2026-05-13", 2, 5000.0)]
        result = render_tonnage_sparkline(points)
        self.assertIn("-16.7%", result)

    def test_zero_first_value_no_division_error(self) -> None:
        # 邊界:第一筆 0 (BW only),不該炸
        points = [_pt("2026-04-22", 1, 0.0), _pt("2026-05-13", 2, 5000.0)]
        result = render_tonnage_sparkline(points)
        self.assertIsInstance(result, str)


class TestRenderStudentTrendIncludesSparkline(unittest.TestCase):
    def test_trend_with_multi_points_shows_sparkline(self) -> None:
        trend = StudentTrend(
            student_name="林阿明",
            points=[
                _pt("2026-04-22", 1, 5640.0),
                _pt("2026-04-29", 2, 5920.0),
                _pt("2026-05-06", 3, 6020.0),
                _pt("2026-05-13", 4, 6200.0),
            ],
            total_tonnage=23780.0,
        )
        out = render_student_trend(trend)
        # 至少出現一個方塊字元
        self.assertTrue(any(b in out for b in SPARKLINE_BARS), out)
        self.assertIn("+9.9%", out)

    def test_trend_with_empty_points_no_sparkline(self) -> None:
        trend = StudentTrend(student_name="林阿明", points=[], total_tonnage=0.0)
        out = render_student_trend(trend)
        # 沒 points → 不該有方塊字元
        self.assertFalse(any(b in out for b in SPARKLINE_BARS), out)


class TestCliBatchProducesSparklineInStudentMd(unittest.TestCase):
    def test_student_md_contains_sparkline(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i, w in enumerate([45.0, 47.5, 50.0], 1):
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
            self.assertTrue(any(b in content for b in SPARKLINE_BARS), content)


if __name__ == "__main__":
    unittest.main()
