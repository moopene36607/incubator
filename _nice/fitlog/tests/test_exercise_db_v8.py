"""紅色測試 — exercise_db v8 擴展 (146 → 162+ 動作).

v7 擴到 146。本輪補:雪橇蹲變化 / 大猩猩划船 / JM 臥推 / 雨刷 / 跳箱 /
天蠍式 等。持續往 200+ 邁進。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES, by_category, lookup  # noqa: E402


class TestExerciseDbV8Coverage(unittest.TestCase):
    def test_total_at_least_162(self) -> None:
        self.assertGreaterEqual(
            len(EXERCISES), 162,
            f"v8 階段擴到 162+;目前 {len(EXERCISES)}",
        )

    def test_each_category_at_least_18(self) -> None:
        for cat in ("legs", "pull", "push", "core", "cardio", "mobility"):
            count = len(by_category(cat))
            self.assertGreaterEqual(
                count, 18, f"category {cat} 只有 {count} 個 (v8 應 >= 18)",
            )


class TestV8NewExercisesPresent(unittest.TestCase):
    def test_new_legs(self) -> None:
        for code in ("SISSY_SQUAT", "ATG_SPLIT_SQUAT", "BOX_JUMP"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_pull(self) -> None:
        for code in ("GORILLA_ROW", "ZOTTMAN_CURL", "CABLE_PULLOVER"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_push(self) -> None:
        for code in ("JM_PRESS", "PIKE_PUSHUP", "SVEND_PRESS"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_core(self) -> None:
        for code in ("WINDSHIELD_WIPER", "FLUTTER_KICK", "L_SIT"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_cardio(self) -> None:
        for code in ("ROWING_SPRINT", "AIRDYNE_SPRINT", "STAIR_RUN"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_mobility(self) -> None:
        for code in ("SCORPION_STRETCH", "ANKLE_ROCK", "NECK_CARS"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_entries_chinese_names(self) -> None:
        for code in ("SISSY_SQUAT", "GORILLA_ROW", "BOX_JUMP"):
            ex = lookup(code)
            assert ex is not None
            self.assertTrue(ex.chinese.strip())
            self.assertNotEqual(ex.chinese, code)


class TestV8IntegrityStillHolds(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
