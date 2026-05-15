"""紅色測試 — `--list-exercises` CLI 子命令.

PT 在寫 JSON 想找正確 exercise_code 時,目前要翻 exercise_db.py 的 56 筆
資料,UX 很差。本輪加 `--list-exercises` 旗標,直接印出 grouped-by-category
的可讀清單:

  ## 腿系
  - BB_BACK_SQUAT   槓鈴背蹲舉 (Barbell Back Squat)
  - DUMBBELL_LUNGE  啞鈴弓步蹲 (Dumbbell Lunge)
  ...

純 render 函式 + CLI hook,不會碰 LLM 也不需要輸入檔。
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES, by_category  # noqa: E402
from fitlog import render_exercise_listing  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestRenderExerciseListing(unittest.TestCase):
    def test_returns_non_empty_string(self) -> None:
        out = render_exercise_listing()
        self.assertTrue(out)
        self.assertGreater(len(out), 100)

    def test_includes_all_known_codes(self) -> None:
        out = render_exercise_listing()
        for ex in EXERCISES:
            self.assertIn(ex.code, out, f"missing {ex.code}")

    def test_includes_chinese_and_english_names(self) -> None:
        out = render_exercise_listing()
        # 抽查幾個
        self.assertIn("槓鈴背蹲舉", out)
        self.assertIn("Barbell Back Squat", out)
        self.assertIn("引體向上", out)
        self.assertIn("Pull-up", out)

    def test_grouped_by_category(self) -> None:
        # 每個 category 都應有一個小標題 (找中文 category 標籤)
        out = render_exercise_listing()
        self.assertIn("腿系", out)
        self.assertIn("拉系", out)
        self.assertIn("推系", out)
        self.assertIn("核心", out)
        self.assertIn("心肺", out)
        self.assertIn("活動度", out)

    def test_legs_section_contains_legs_exercises(self) -> None:
        out = render_exercise_listing()
        # 切到 "腿系" 段 (下一個 "##" 之前) 應該含全部 legs codes
        legs_section = out.split("腿系", 1)[1].split("##", 1)[0]
        for ex in by_category("legs"):
            self.assertIn(ex.code, legs_section)

    def test_total_count_in_header(self) -> None:
        out = render_exercise_listing()
        # 至少要說有 N 個動作
        self.assertIn(str(len(EXERCISES)), out)


class TestCliListExercisesFlag(unittest.TestCase):
    def test_flag_prints_listing_and_exits_zero(self) -> None:
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--list-exercises"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        # 印到 stdout
        self.assertIn("BB_BACK_SQUAT", r.stdout)
        self.assertIn("槓鈴背蹲舉", r.stdout)
        self.assertIn("PULL_UP", r.stdout)

    def test_flag_works_without_input_file(self) -> None:
        # 沒有 input.json 也要正常運作 (純資訊指令)
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--list-exercises"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
