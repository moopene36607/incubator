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


if __name__ == "__main__":
    unittest.main()
