"""紅色測試 — --list-exercises 支援分類 / 關鍵字篩選.

92 個動作一次全印太長。本輪讓 --list-exercises 接 optional 參數:
- 分類名 (legs / pull / 腿系 ...) → 只列該分類
- 其他關鍵字 → 對 中文 / 英文 / code 做子字串搜尋

不帶參數 → 維持全列 (向後相容)。
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import render_exercise_listing  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestRenderExerciseListingFilter(unittest.TestCase):
    def test_no_filter_lists_all(self) -> None:
        out = render_exercise_listing()
        self.assertIn("BB_BACK_SQUAT", out)
        self.assertIn("BENCH_PRESS", out)

    def test_filter_by_english_category(self) -> None:
        out = render_exercise_listing("legs")
        self.assertIn("BB_BACK_SQUAT", out)   # legs
        self.assertNotIn("BENCH_PRESS", out)  # push

    def test_filter_by_chinese_category(self) -> None:
        out = render_exercise_listing("腿系")
        self.assertIn("BB_BACK_SQUAT", out)
        self.assertNotIn("BENCH_PRESS", out)

    def test_filter_by_chinese_name_substring(self) -> None:
        out = render_exercise_listing("臥推")
        self.assertIn("BENCH_PRESS", out)        # 槓鈴臥推
        self.assertNotIn("BB_BACK_SQUAT", out)   # 槓鈴背蹲舉

    def test_filter_by_code_substring(self) -> None:
        out = render_exercise_listing("SQUAT")
        self.assertIn("BB_BACK_SQUAT", out)
        self.assertIn("GOBLET_SQUAT", out)
        self.assertNotIn("BENCH_PRESS", out)

    def test_filter_by_english_name_case_insensitive(self) -> None:
        out = render_exercise_listing("bench")
        self.assertIn("BENCH_PRESS", out)

    def test_no_match_reports_clearly(self) -> None:
        out = render_exercise_listing("不存在的動作xyz")
        self.assertIn("找不到", out)

    def test_filter_count_in_header(self) -> None:
        out = render_exercise_listing("legs")
        # header 該反映篩選後數量,不是 92
        self.assertNotIn("(92", out)


class TestCliListExercisesFilter(unittest.TestCase):
    def test_cli_no_arg_lists_all(self) -> None:
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--list-exercises"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("BENCH_PRESS", r.stdout)
        self.assertIn("BB_BACK_SQUAT", r.stdout)

    def test_cli_category_filter(self) -> None:
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--list-exercises", "legs"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("BB_BACK_SQUAT", r.stdout)
        self.assertNotIn("BENCH_PRESS", r.stdout)

    def test_cli_keyword_filter(self) -> None:
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--list-exercises", "划船"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("BB_ROW", r.stdout)


if __name__ == "__main__":
    unittest.main()
