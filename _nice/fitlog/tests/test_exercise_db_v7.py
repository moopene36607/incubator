"""紅色測試 — exercise_db v7 擴展 (128 → 144+ 動作).

v6 擴到 128。本輪補:安全槓深蹲 / 西班牙蹲 / Kroc 划船 / Larsen 臥推 /
弓箭手伏地挺身 / 腳踏車捲腹 / 藥球砸地 / 翻輪胎 / 死握 等。往 200+ 邁進。

既有 test_exercise_db* 完整性 invariant 自動驗證新條目。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES, by_category, lookup  # noqa: E402


class TestExerciseDbV7Coverage(unittest.TestCase):
    def test_total_at_least_144(self) -> None:
        self.assertGreaterEqual(
            len(EXERCISES), 144,
            f"v7 階段擴到 144+;目前 {len(EXERCISES)}",
        )

    def test_each_category_at_least_16(self) -> None:
        for cat in ("legs", "pull", "push", "core", "cardio", "mobility"):
            count = len(by_category(cat))
            self.assertGreaterEqual(
                count, 16, f"category {cat} 只有 {count} 個 (v7 應 >= 16)",
            )


class TestV7NewExercisesPresent(unittest.TestCase):
    def test_new_legs(self) -> None:
        for code in ("SAFETY_BAR_SQUAT", "SPANISH_SQUAT", "KICKSTAND_RDL"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_pull(self) -> None:
        for code in ("KROC_ROW", "INCLINE_CURL", "DRAG_CURL"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_push(self) -> None:
        for code in ("LARSEN_PRESS", "BRADFORD_PRESS", "ARCHER_PUSHUP"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_core(self) -> None:
        for code in ("BICYCLE_CRUNCH", "V_SIT", "GHD_SITUP"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_cardio(self) -> None:
        for code in ("DEADBALL_SLAM", "TYRE_FLIP", "PROWLER_DRAG"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_mobility(self) -> None:
        for code in ("DEAD_HANG", "ARM_CIRCLES", "SCAPULAR_PULLUP"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_entries_chinese_names(self) -> None:
        for code in ("SAFETY_BAR_SQUAT", "KROC_ROW", "DEADBALL_SLAM"):
            ex = lookup(code)
            assert ex is not None
            self.assertTrue(ex.chinese.strip())
            self.assertNotEqual(ex.chinese, code)


class TestV7IntegrityStillHolds(unittest.TestCase):
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

    def test_all_categories_valid(self) -> None:
        valid = {"legs", "pull", "push", "core", "cardio", "mobility"}
        for e in EXERCISES:
            self.assertIn(e.category, valid, f"{e.code} 未知 category")


if __name__ == "__main__":
    unittest.main()
