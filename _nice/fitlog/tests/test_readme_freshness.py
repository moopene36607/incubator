"""紅色測試 — README.md 必須與目前 CLI / exercise_db 同步.

README 是這個原型的對外展示文件,reviewer 第一個讀。它已落後:動作數
還寫 56 (實際 74)、近 10 個 CLI 旗標沒記載 (--batch-csv / --batch-json /
--csv-bom / --out-json / --quiet / --student / --list-exercises / --version)。

本測試鎖住同步性:往後加 CLI 旗標或擴 exercise_db,README 不更新就 RED。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import EXERCISES  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
README = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")


class TestReadmeExerciseCount(unittest.TestCase):
    def test_readme_mentions_current_exercise_count(self) -> None:
        # README 某處要出現目前的動作總數
        self.assertIn(
            str(len(EXERCISES)), README,
            f"README 應提到目前動作數 {len(EXERCISES)}",
        )

    def test_readme_not_stale_56(self) -> None:
        # 「56 動作」這種舊敘述不該還在 (除非真的是 56)
        if len(EXERCISES) != 56:
            self.assertNotIn("56 動作", README,
                             "README 還寫『56 動作』,已過時")


class TestReadmeDocumentsCliFlags(unittest.TestCase):
    def test_all_current_flags_documented(self) -> None:
        flags = [
            "--batch", "--out-dir", "--summary-only", "--batch-html",
            "--batch-csv", "--batch-json", "--out-line", "--csv",
            "--csv-bom", "--html", "--out-json", "--prev", "--voice",
            "--template", "--list-exercises", "--student", "--quiet",
            "--version", "--no-ai",
        ]
        missing = [f for f in flags if f not in README]
        self.assertEqual(missing, [],
                         f"README 沒記載這些 CLI 旗標: {missing}")


class TestReadmeMentionsKeyFeatures(unittest.TestCase):
    def test_mentions_recent_report_sections(self) -> None:
        # 近期新增的報表能力,README 至少各提一次
        features = [
            "強度分數",      # intensity score
            "連續訓練",      # training streak
            "動作多樣性",    # exercise variety
            "工作室週訓練量",  # studio weekly
        ]
        missing = [f for f in features if f not in README]
        self.assertEqual(missing, [],
                         f"README 沒提到這些功能: {missing}")

    def test_mentions_bodyweight_and_relative_strength(self) -> None:
        # round 49-51 的體重 / 相對肌力功能
        for feat in ("相對肌力", "體重"):
            self.assertIn(feat, README, f"README 沒提到 {feat}")

    def test_list_exercises_filter_documented(self) -> None:
        # round 58 的 --list-exercises 篩選功能應記載
        self.assertTrue("篩選" in README or "關鍵字" in README,
                        "README 沒提到 --list-exercises 的篩選能力")

    def test_project_structure_lists_core_modules(self) -> None:
        # 專案結構段應反映目前的模組拆分,不是只有 fitlog.py
        for module in ("aggregate.py", "metrics.py", "voice.py",
                       "exercise_db.py"):
            self.assertIn(module, README,
                          f"README 專案結構沒列出 {module}")

    def test_no_stale_350_lines_claim(self) -> None:
        # 「約 350 行」是早期數字,專案已遠超過
        self.assertNotIn("350 行", README)

    def test_roadmap_reflects_done_features(self) -> None:
        # voice parser / 進度追蹤 / 自動 PR 偵測都已實作,roadmap 段
        # 不該還把它們純列為「沒做」— 應有「已實作」之類標記
        self.assertIn("已實作", README)


if __name__ == "__main__":
    unittest.main()
