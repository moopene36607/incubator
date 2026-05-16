"""紅色測試 — LINE 版補 PR 突破 / 相對肌力里程碑 banner.

new_pr_banner 與 rel_strength_milestone 是學員最愛看的慶祝時刻,但
render_line_friendly 沒帶它們 — LINE 是主要的學員推播管道,慶祝缺席很可惜。
本輪讓 LINE 版也能在頂端秀這兩個 banner。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import (  # noqa: E402
    SessionInput,
    SetRecord,
    render_line_friendly,
    render_skeleton_body,
)


def _session() -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=3, session_date="2026-05-15", duration_min=60,
        coach_name="陳教練", studio_name="S", contact="",
        theme="推系日",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=50.0, rpe=8)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestLineCelebrationBanners(unittest.TestCase):
    def test_pr_banner_in_line(self) -> None:
        sess = _session()
        out = render_line_friendly(
            sess, render_skeleton_body(sess),
            new_pr_banner="🏆 **PR 突破**!: 槓鈴臥推 50 kg (打破歷來最高 45 kg)")
        self.assertIn("PR 突破", out)
        self.assertIn("槓鈴臥推", out)
        # LINE 版去 markdown 粗體
        self.assertNotIn("**", out)

    def test_milestone_banner_in_line(self) -> None:
        sess = _session()
        out = render_line_friendly(
            sess, render_skeleton_body(sess),
            rel_strength_milestone="🏆 **相對肌力里程碑**:槓鈴臥推 突破 1× 自身體重!")
        self.assertIn("相對肌力里程碑", out)
        self.assertNotIn("**", out)

    def test_both_banners(self) -> None:
        sess = _session()
        out = render_line_friendly(
            sess, render_skeleton_body(sess),
            new_pr_banner="🏆 PR 突破!: 槓鈴臥推 50 kg",
            rel_strength_milestone="🏆 相對肌力里程碑:臥推 突破 1× 自身體重!")
        self.assertIn("PR 突破", out)
        self.assertIn("里程碑", out)

    def test_no_banners_backward_compat(self) -> None:
        sess = _session()
        out = render_line_friendly(sess, render_skeleton_body(sess))
        self.assertIn("林阿明", out)
        self.assertIn("課後報告", out)

    def test_banner_appears_before_training_record(self) -> None:
        # 慶祝 banner 應在訓練紀錄前 (顯眼位置)
        sess = _session()
        out = render_line_friendly(
            sess, render_skeleton_body(sess),
            new_pr_banner="🏆 PR 突破!: 槓鈴臥推 50 kg")
        self.assertLess(out.find("PR 突破"), out.find("訓練紀錄"))


if __name__ == "__main__":
    unittest.main()
