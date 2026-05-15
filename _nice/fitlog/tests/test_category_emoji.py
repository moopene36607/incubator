"""紅色測試 — session table 加分類 emoji 圖示.

每個動作前加分類 emoji (🦵 legs / 💪 push / 🤜 pull / 🧘 mobility /
🏃 cardio / 🎯 core),學員一眼看出今日訓練的肌群分布。

只在「分類已知」時加;exercise_db 找不到的代碼不加 emoji (避免亂顯示)。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SessionInput, SetRecord, render_session_table  # noqa: E402
from metrics import CATEGORY_EMOJI  # noqa: E402


def _make(sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name="X", student_age=30, student_goal="",
        session_no=1, session_date="2026-05-13", duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int = 4, reps: str = "8",
         weight: float | None = 50.0) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=8)


class TestCategoryEmojiConstant(unittest.TestCase):
    def test_six_categories_have_emoji(self) -> None:
        for cat in ("legs", "pull", "push", "core", "cardio", "mobility"):
            self.assertIn(cat, CATEGORY_EMOJI)
            self.assertTrue(CATEGORY_EMOJI[cat].strip())  # 非空


class TestRenderSessionTableWithEmoji(unittest.TestCase):
    def test_legs_exercise_has_legs_emoji(self) -> None:
        sess = _make([_set("BB_BACK_SQUAT")])
        rows = render_session_table(sess)
        # data row (index 2) 該含 legs emoji + 名字
        self.assertIn(CATEGORY_EMOJI["legs"], rows[2])
        self.assertIn("槓鈴背蹲舉", rows[2])

    def test_push_exercise_has_push_emoji(self) -> None:
        sess = _make([_set("BENCH_PRESS")])
        rows = render_session_table(sess)
        self.assertIn(CATEGORY_EMOJI["push"], rows[2])

    def test_pull_exercise_has_pull_emoji(self) -> None:
        sess = _make([_set("PULL_UP", weight=None)])
        rows = render_session_table(sess)
        self.assertIn(CATEGORY_EMOJI["pull"], rows[2])

    def test_unknown_exercise_no_emoji_added(self) -> None:
        # 未知代碼 → 不加 emoji (避免亂顯示;原 fallback 標「代碼未知」仍在)
        sess = _make([_set("XXX_UNKNOWN")])
        rows = render_session_table(sess)
        self.assertIn("代碼未知", rows[2])
        # 不該有任何分類 emoji
        for emoji in CATEGORY_EMOJI.values():
            self.assertNotIn(emoji, rows[2])

    def test_existing_substring_assertions_still_pass(self) -> None:
        # 確認 round 42 既有測試 (對 "槓鈴臥推" / "50.0 kg" 的 assertIn)
        # 仍通過 — emoji prepend 不破既有契約
        sess = _make([_set("BENCH_PRESS")])
        rows = render_session_table(sess)
        self.assertIn("槓鈴臥推", rows[2])
        self.assertIn("50.0 kg", rows[2])


if __name__ == "__main__":
    unittest.main()
