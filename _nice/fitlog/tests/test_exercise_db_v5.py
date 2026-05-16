"""紅色測試 — exercise_db v5 擴展 (92 → 108+ 動作).

v4 擴到 92。本輪再補常見處方:腰帶深蹲 / 單腿蹲 / 海豹划船 / 地板臥推 /
鑽石伏地挺身 / 懸體 / 龍旗 / 階梯機 / 帶子分開 等。往 200+ 邁進。

既有 test_exercise_db* 完整性 invariant 會自動驗證新條目。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES, by_category, lookup  # noqa: E402


class TestExerciseDbV5Coverage(unittest.TestCase):
    def test_total_at_least_108(self) -> None:
        self.assertGreaterEqual(
            len(EXERCISES), 108,
            f"v5 階段擴到 108+;目前 {len(EXERCISES)}",
        )

    def test_each_category_at_least_12(self) -> None:
        for cat in ("legs", "pull", "push", "core", "cardio", "mobility"):
            count = len(by_category(cat))
            self.assertGreaterEqual(
                count, 12, f"category {cat} 只有 {count} 個 (v5 應 >= 12)",
            )


class TestV5NewExercisesPresent(unittest.TestCase):
    def test_new_legs(self) -> None:
        for code in ("BELT_SQUAT", "PISTOL_SQUAT", "JUMP_SQUAT"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_pull(self) -> None:
        for code in ("SEAL_ROW", "CABLE_CURL", "MUSCLE_UP"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_push(self) -> None:
        for code in ("FLOOR_PRESS", "DIAMOND_PUSHUP", "OVERHEAD_TRICEP_EXT"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_core(self) -> None:
        for code in ("HOLLOW_HOLD", "CABLE_CRUNCH", "DRAGON_FLAG"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_cardio(self) -> None:
        for code in ("VERSACLIMBER", "INCLINE_WALK", "JACOBS_LADDER"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_mobility(self) -> None:
        for code in ("BAND_PULL_APART", "JEFFERSON_CURL", "FOAM_ROLL"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_entries_chinese_names(self) -> None:
        for code in ("BELT_SQUAT", "SEAL_ROW", "DRAGON_FLAG"):
            ex = lookup(code)
            assert ex is not None
            self.assertTrue(ex.chinese.strip())
            self.assertNotEqual(ex.chinese, code)


class TestV5IntegrityStillHolds(unittest.TestCase):
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

    def test_all_codes_underscore_uppercase(self) -> None:
        for e in EXERCISES:
            self.assertEqual(e.code, e.code.upper())
            self.assertNotIn(" ", e.code)


if __name__ == "__main__":
    unittest.main()
