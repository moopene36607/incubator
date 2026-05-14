"""紅色測試 — exercise_db 擴展至 50+ 動作 + 完整性 invariants.

prototype 30 個動作只能涵蓋 80% 的 1 對 1 PT 課程,缺機械式 (hack squat /
hip thrust)、街健 / cardio (burpee / kettlebell swing)、瑜珈/活動度
(cat-cow / cossack squat)。本輪擴到 50+,並建立 schema 完整性測試確保
往後新增條目時不會漏欄位 / 重複 code / RPE range 不合理。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES, by_category, lookup  # noqa: E402


VALID_CATEGORIES = ("legs", "pull", "push", "core", "cardio", "mobility")
VALID_UNITS = ("rep", "sec", "min", "m")


class TestExerciseDbCoverage(unittest.TestCase):
    def test_total_at_least_50(self) -> None:
        self.assertGreaterEqual(
            len(EXERCISES), 50,
            f"prototype 階段擴到 50+;目前 {len(EXERCISES)}",
        )

    def test_each_category_has_at_least_5(self) -> None:
        for cat in VALID_CATEGORIES:
            count = len(by_category(cat))
            self.assertGreaterEqual(
                count, 5, f"category {cat} 只有 {count} 個動作 (應 >= 5)",
            )


class TestExerciseDbIntegrity(unittest.TestCase):
    def test_no_duplicate_codes(self) -> None:
        codes = [e.code for e in EXERCISES]
        self.assertEqual(len(codes), len(set(codes)),
                         f"代碼有重複: {[c for c in codes if codes.count(c) > 1]}")

    def test_all_codes_uppercase_and_underscore(self) -> None:
        for e in EXERCISES:
            self.assertEqual(e.code, e.code.upper().replace("-", "_"),
                             f"代碼非全大寫_: {e.code}")
            self.assertNotIn(" ", e.code, f"代碼含空白: {e.code}")

    def test_all_required_fields_populated(self) -> None:
        for e in EXERCISES:
            self.assertTrue(e.chinese.strip(), f"{e.code} 中文名空")
            self.assertTrue(e.english.strip(), f"{e.code} 英文名空")
            self.assertTrue(e.target_muscles.strip(), f"{e.code} target_muscles 空")

    def test_categories_in_whitelist(self) -> None:
        for e in EXERCISES:
            self.assertIn(e.category, VALID_CATEGORIES,
                          f"{e.code} 用了未知 category: {e.category}")

    def test_units_in_whitelist(self) -> None:
        for e in EXERCISES:
            self.assertIn(e.measure_unit, VALID_UNITS,
                          f"{e.code} 用了未知 unit: {e.measure_unit}")

    def test_rpe_range_valid(self) -> None:
        for e in EXERCISES:
            low, high = e.typical_rpe_range
            self.assertLessEqual(low, high,
                                 f"{e.code} RPE range 顛倒: {e.typical_rpe_range}")
            self.assertGreaterEqual(low, 1,
                                    f"{e.code} RPE 低於 1: {low}")
            self.assertLessEqual(high, 10,
                                 f"{e.code} RPE 高於 10: {high}")


class TestNewExercisesPresent(unittest.TestCase):
    """確認本輪新增的關鍵動作 lookup 成功 (覆蓋常見機械式 / 街健 / 瑜珈)。"""

    def test_machine_legs(self) -> None:
        self.assertIsNotNone(lookup("HACK_SQUAT"), "hack squat 機")
        self.assertIsNotNone(lookup("HIP_THRUST"), "臀推")
        self.assertIsNotNone(lookup("LEG_EXTENSION"), "腿伸機")
        self.assertIsNotNone(lookup("LEG_CURL"), "腿彎舉機")

    def test_machine_upper(self) -> None:
        self.assertIsNotNone(lookup("CABLE_ROW"), "坐姿划船")
        self.assertIsNotNone(lookup("LATERAL_RAISE"), "側平舉")
        self.assertIsNotNone(lookup("MACHINE_CHEST_PRESS"), "蝴蝶機臥推")

    def test_street_workout(self) -> None:
        self.assertIsNotNone(lookup("CHIN_UP"), "反握引體")
        self.assertIsNotNone(lookup("BURPEE"), "波比跳")
        self.assertIsNotNone(lookup("KETTLEBELL_SWING"), "壺鈴擺盪")

    def test_core_additions(self) -> None:
        self.assertIsNotNone(lookup("AB_WHEEL"), "健腹輪")
        self.assertIsNotNone(lookup("V_UP"), "V 字仰臥")

    def test_mobility_additions(self) -> None:
        self.assertIsNotNone(lookup("CAT_COW"), "貓牛式")
        self.assertIsNotNone(lookup("COSSACK_SQUAT"), "哥薩克深蹲")


class TestLookupCaseInsensitive(unittest.TestCase):
    """既有契約:lookup 接 mixed case (寫 'bench_press' 也該找得到)。"""

    def test_lowercase_input(self) -> None:
        self.assertIsNotNone(lookup("bench_press"))

    def test_mixed_case_input(self) -> None:
        self.assertIsNotNone(lookup("Bench_Press"))


if __name__ == "__main__":
    unittest.main()
