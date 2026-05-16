"""紅色測試 — exercise_db v6 擴展 (110 → 126+ 動作).

v5 擴到 110。本輪再補:Zercher 蹲 / 胸靠划船 / 牧師椅彎舉 / 滑輪交叉 /
雪橇推 / 農夫走路 / 哥本哈根棒式 等。持續往 200+ 邁進。

既有 test_exercise_db* 完整性 invariant 自動驗證新條目。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES, by_category, lookup  # noqa: E402


class TestExerciseDbV6Coverage(unittest.TestCase):
    def test_total_at_least_126(self) -> None:
        self.assertGreaterEqual(
            len(EXERCISES), 126,
            f"v6 階段擴到 126+;目前 {len(EXERCISES)}",
        )

    def test_each_category_at_least_14(self) -> None:
        for cat in ("legs", "pull", "push", "core", "cardio", "mobility"):
            count = len(by_category(cat))
            self.assertGreaterEqual(
                count, 14, f"category {cat} 只有 {count} 個 (v6 應 >= 14)",
            )


class TestV6NewExercisesPresent(unittest.TestCase):
    def test_new_legs(self) -> None:
        for code in ("ZERCHER_SQUAT", "SEATED_CALF_RAISE",
                     "TERMINAL_KNEE_EXT"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_pull(self) -> None:
        for code in ("CHEST_SUPPORTED_ROW", "PREACHER_CURL", "REVERSE_FLY"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_push(self) -> None:
        for code in ("CABLE_CROSSOVER", "BENCH_DIP", "HANDSTAND_PUSHUP"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_core(self) -> None:
        for code in ("SUITCASE_CARRY", "COPENHAGEN_PLANK", "JACKKNIFE"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_cardio(self) -> None:
        for code in ("SLED_PUSH", "FARMERS_WALK", "HILL_SPRINT"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_mobility(self) -> None:
        for code in ("THREAD_THE_NEEDLE", "FROG_STRETCH",
                     "HAMSTRING_STRETCH"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_entries_chinese_names(self) -> None:
        for code in ("ZERCHER_SQUAT", "SLED_PUSH", "PREACHER_CURL"):
            ex = lookup(code)
            assert ex is not None
            self.assertTrue(ex.chinese.strip())
            self.assertNotEqual(ex.chinese, code)


class TestV6IntegrityStillHolds(unittest.TestCase):
    def test_no_duplicate_codes(self) -> None:
        codes = [e.code for e in EXERCISES]
        dups = sorted({c for c in codes if codes.count(c) > 1})
        self.assertEqual(dups, [], f"重複 code: {dups}")

    def test_all_rpe_ranges_valid(self) -> None:
        for e in EXERCISES:
            low, high = e.typical_rpe_range
            self.assertLessEqual(low, high, f"{e.code} RPE 顛倒")
            self.assertGreaterEqual(low, 1, f"{e.code} RPE < 1")
            self.assertLessEqual(high, 10, f"{e.code} RPE > 10")

    def test_all_units_valid(self) -> None:
        for e in EXERCISES:
            self.assertIn(e.measure_unit, ("rep", "sec", "min", "m"),
                          f"{e.code} 用了未知 unit")


if __name__ == "__main__":
    unittest.main()
