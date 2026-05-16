"""紅色測試 — exercise_db v4 擴展 (74 → 90+ 動作).

v3 擴到 74。仍缺常見處方:早安式 / 後弓步 / 聳肩 / 二頭彎舉 / 推舉 /
碎顱者 / 蝴蝶機 / 反向捲腹 / 登山者 / 橢圓機 / 鴿式 等。本輪擴到 90+。

既有 test_exercise_db* 的完整性 invariant 會自動驗證新條目。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES, by_category, lookup  # noqa: E402


class TestExerciseDbV4Coverage(unittest.TestCase):
    def test_total_at_least_90(self) -> None:
        self.assertGreaterEqual(
            len(EXERCISES), 90,
            f"v4 階段擴到 90+;目前 {len(EXERCISES)}",
        )

    def test_each_category_at_least_10(self) -> None:
        for cat in ("legs", "pull", "push", "core", "cardio", "mobility"):
            count = len(by_category(cat))
            self.assertGreaterEqual(
                count, 10, f"category {cat} 只有 {count} 個 (v4 應 >= 10)",
            )


class TestV4NewExercisesPresent(unittest.TestCase):
    def test_new_legs(self) -> None:
        for code in ("GOOD_MORNING", "REVERSE_LUNGE", "BOX_SQUAT",
                     "SINGLE_LEG_RDL"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_pull(self) -> None:
        for code in ("SHRUG", "BICEP_CURL", "HAMMER_CURL", "RACK_PULL"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_push(self) -> None:
        for code in ("PUSH_PRESS", "SKULL_CRUSHER", "PEC_DECK",
                     "MACHINE_SHOULDER_PRESS"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_core(self) -> None:
        for code in ("REVERSE_CRUNCH", "MOUNTAIN_CLIMBER"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_cardio(self) -> None:
        for code in ("ELLIPTICAL", "SHADOW_BOXING"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_mobility(self) -> None:
        for code in ("PIGEON_POSE", "WALL_SLIDE"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_entries_chinese_names(self) -> None:
        for code in ("GOOD_MORNING", "BICEP_CURL", "PUSH_PRESS"):
            ex = lookup(code)
            assert ex is not None
            self.assertTrue(ex.chinese.strip())
            self.assertNotEqual(ex.chinese, code)


class TestV4IntegrityStillHolds(unittest.TestCase):
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
        valid = {"rep", "sec", "min", "m"}
        for e in EXERCISES:
            self.assertIn(e.measure_unit, valid,
                          f"{e.code} 用了未知 unit {e.measure_unit}")


if __name__ == "__main__":
    unittest.main()
