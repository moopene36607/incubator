"""紅色測試 — exercise_db v3 擴展 (56 → 72+ 動作).

第 a86e671 輪把 db 從 30 擴到 56,但仍缺很多台灣健身房常見處方:
- legs: 前蹲舉 / 相撲硬舉 / 登階 / 臀橋 / 北歐腿彎舉
- pull: Pendlay 划船 / 直臂下拉 / 高拉
- push: 阿諾肩推 / 三頭下壓 / 窄握臥推 / Landmine 推
- core: 俄羅斯轉體 / 鳥狗式
- cardio: 衝刺間歇 / 滑雪機
- mobility: 沙發伸展 / 下犬式

本輪擴到 72+。既有 test_exercise_db.py 的完整性 invariant 會自動驗證新條目
(無重複 code / 欄位齊全 / category & unit 在白名單 / RPE range 合理)。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES, by_category, lookup  # noqa: E402


class TestExerciseDbV3Coverage(unittest.TestCase):
    def test_total_at_least_72(self) -> None:
        self.assertGreaterEqual(
            len(EXERCISES), 72,
            f"v3 階段擴到 72+;目前 {len(EXERCISES)}",
        )

    def test_each_category_has_at_least_8(self) -> None:
        for cat in ("legs", "pull", "push", "core", "cardio", "mobility"):
            count = len(by_category(cat))
            self.assertGreaterEqual(
                count, 8, f"category {cat} 只有 {count} 個動作 (v3 應 >= 8)",
            )


class TestV3NewExercisesPresent(unittest.TestCase):
    def test_new_legs(self) -> None:
        for code in ("FRONT_SQUAT", "SUMO_DEADLIFT", "STEP_UP",
                     "GLUTE_BRIDGE", "NORDIC_CURL"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_pull(self) -> None:
        for code in ("PENDLAY_ROW", "STRAIGHT_ARM_PULLDOWN", "HIGH_PULL"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_push(self) -> None:
        for code in ("ARNOLD_PRESS", "TRICEP_PUSHDOWN", "CLOSE_GRIP_BENCH",
                     "LANDMINE_PRESS"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_core(self) -> None:
        for code in ("RUSSIAN_TWIST", "BIRD_DOG"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_cardio(self) -> None:
        for code in ("SPRINT_INTERVAL", "SKI_ERG"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_mobility(self) -> None:
        for code in ("COUCH_STRETCH", "DOWNWARD_DOG"):
            self.assertIsNotNone(lookup(code), f"缺 {code}")

    def test_new_entries_have_chinese_names(self) -> None:
        # 抽查幾個新動作中文名正確 (非空 + 不是 code 本身)
        for code in ("FRONT_SQUAT", "ARNOLD_PRESS", "RUSSIAN_TWIST"):
            ex = lookup(code)
            assert ex is not None
            self.assertTrue(ex.chinese.strip())
            self.assertNotEqual(ex.chinese, code)


class TestV3IntegrityStillHolds(unittest.TestCase):
    """v3 新增後完整性不破 (重複本檢一次,不依賴另一檔)。"""

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
            self.assertIn(e.category, valid, f"{e.code} 用了未知 category")


if __name__ == "__main__":
    unittest.main()
